"""Admin: User management routes — super admins only for create/deactivate."""
from __future__ import annotations

import re as _re
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from core.helpers import make_id, now_iso
from core.security import pwd_context
from core.tenant import get_tenant_filter, tenant_id_of, get_tenant_admin, get_tenant_super_admin, is_platform_admin, enrich_partner_codes
from db.session import db
from models import AdminCreateUserRequest
from services.audit_service import create_audit_log

router = APIRouter(prefix="/api", tags=["admin-users"])

SUPER_ADMIN_ROLES = {"platform_super_admin", "partner_super_admin"}


def _is_super_admin(admin: Dict[str, Any]) -> bool:
    return admin.get("role") in SUPER_ADMIN_ROLES


def _pw_ok(pw: str) -> Optional[str]:
    if len(pw) < 10:
        return "Password must be at least 10 characters"
    if not _re.search(r'[A-Z]', pw):
        return "Password must contain at least one uppercase letter"
    if not _re.search(r'[a-z]', pw):
        return "Password must contain at least one lowercase letter"
    if not _re.search(r'\d', pw):
        return "Password must contain at least one number"
    if not _re.search(r'[!@#$%^&*()\-_=+\[\]{}|;:,.<>?/~`"]', pw):
        return "Password must contain at least one special character"
    return None


@router.get("/admin/users")
async def admin_list_users(
    page: int = 1,
    per_page: int = 20,
    search: Optional[str] = None,
    partner_id: Optional[str] = None,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    query: Dict[str, Any] = {**tf, "is_admin": True}
    if partner_id and is_platform_admin(admin):
        query["tenant_id"] = partner_id
    if search:
        query["$or"] = [
            {"email": {"$regex": _re.escape(search), "$options": "i"}},
            {"full_name": {"$regex": _re.escape(search), "$options": "i"}},
        ]
    total = await db.users.count_documents(query)
    skip = (page - 1) * per_page
    users = await db.users.find(query, {"_id": 0, "password_hash": 0}).skip(skip).limit(per_page).to_list(per_page)
    users = await enrich_partner_codes(users, is_platform_admin(admin))
    return {
        "users": users,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": max(1, (total + per_page - 1) // per_page),
    }


@router.post("/admin/users")
async def admin_create_admin_user(
    payload: AdminCreateUserRequest,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    from routes.admin.permissions import ADMIN_MODULES, PARTNER_MODULES, PRESET_ROLES

    # Only super admins can create users
    if not _is_super_admin(admin):
        raise HTTPException(403, "Only super admins can create users")

    tid = tenant_id_of(admin)
    caller_role = admin.get("role", "")

    # Determine which roles the caller can create
    if caller_role == "platform_super_admin":
        valid_roles = ("platform_admin", "partner_admin", "partner_staff")
    elif caller_role == "partner_super_admin":
        valid_roles = ("partner_admin", "partner_staff")
    else:
        raise HTTPException(403, "Insufficient privileges to create users")

    if payload.role not in valid_roles:
        raise HTTPException(400, f"You can only create users with roles: {valid_roles}")

    # Enforce only one platform_super_admin ever
    if payload.role == "platform_super_admin":
        raise HTTPException(400, "Platform super admin cannot be created manually")

    pw_err = _pw_ok(payload.password)
    if pw_err:
        raise HTTPException(400, pw_err)

    tf = get_tenant_filter(admin)
    existing = await db.users.find_one({**tf, "email": payload.email.lower()}, {"_id": 0})
    if existing:
        raise HTTPException(400, "Email already registered")

    # License check
    from services.license_service import check_limit as _check_limit
    _limit_check = await _check_limit(tid, "users")
    if not _limit_check["allowed"]:
        raise HTTPException(
            403,
            f"User limit reached ({_limit_check['current']}/{_limit_check['limit']}). "
            "Please contact your platform administrator to upgrade your plan."
        )

    # Build module_permissions
    module_permissions = _resolve_module_permissions(payload, caller_role, ADMIN_MODULES, PARTNER_MODULES, PRESET_ROLES)

    user_id = make_id()
    hashed = pwd_context.hash(payload.password)
    user_doc = {
        "id": user_id,
        "email": payload.email.lower(),
        "password_hash": hashed,
        "full_name": payload.full_name,
        "company_name": payload.company_name or "",
        "job_title": payload.job_title or "",
        "phone": payload.phone or "",
        "is_admin": True,
        "is_verified": True,
        "is_active": True,
        "role": payload.role,
        "module_permissions": module_permissions,
        "tenant_id": tid,
        "must_change_password": True,
        "created_at": now_iso(),
        "created_by_admin": admin["id"],
    }
    await db.users.insert_one(user_doc)

    await create_audit_log(
        entity_type="user",
        entity_id=user_id,
        action="admin_user_created",
        actor=f"admin:{admin['id']}",
        details={"email": payload.email, "role": payload.role, "full_name": payload.full_name},
    )
    return {"message": "Admin user created", "user_id": user_id, "email": payload.email}


@router.put("/admin/users/{user_id}")
async def admin_update_user(
    user_id: str,
    payload: Dict[str, Any] = Body(...),
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    from routes.admin.permissions import ADMIN_MODULES, has_permission as _has_perm

    tf = get_tenant_filter(admin)
    user = await db.users.find_one({**tf, "id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(404, "User not found")

    # Platform super admin is immutable — nobody can edit them
    if user.get("role") == "platform_super_admin":
        raise HTTPException(403, "Platform super admin cannot be edited")

    # Only super admins can edit users
    if not _is_super_admin(admin):
        raise HTTPException(403, "Only super admins can edit users")

    updates: Dict[str, Any] = {"updated_at": now_iso()}

    if "full_name" in payload and payload["full_name"]:
        updates["full_name"] = payload["full_name"].strip()

    # Handle module_permissions update (new format)
    if "module_permissions" in payload:
        mp = payload["module_permissions"] or {}
        invalid_keys = [m for m in mp if m not in ADMIN_MODULES]
        if invalid_keys:
            raise HTTPException(400, f"Invalid modules: {', '.join(invalid_keys)}")
        invalid_vals = [v for v in mp.values() if v not in ("read", "write")]
        if invalid_vals:
            raise HTTPException(400, "Module permission values must be 'read' or 'write'")
        updates["module_permissions"] = mp
        # Clear legacy fields to avoid confusion
        updates["permissions"] = {"modules": list(mp.keys())}
        updates["access_level"] = "full_access"  # legacy compat field

    if "is_active" in payload:
        if user_id == admin.get("id") and not payload["is_active"]:
            raise HTTPException(400, "You cannot deactivate your own account")
        updates["is_active"] = payload["is_active"]

    if "is_verified" in payload:
        updates["is_verified"] = bool(payload["is_verified"])

    if len(updates) > 1:
        await db.users.update_one({"id": user_id}, {"$set": updates})
        await create_audit_log(
            entity_type="user",
            entity_id=user_id,
            action="admin_user_updated",
            actor=f"admin:{admin['id']}",
            details={k: v for k, v in updates.items() if k != "updated_at"},
        )

    updated_user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    return {"message": "User updated", "user": updated_user}


@router.patch("/admin/users/{user_id}/active")
async def admin_set_user_active(
    user_id: str,
    active: bool,
    admin: Dict[str, Any] = Depends(get_tenant_super_admin),
):
    tf = get_tenant_filter(admin)
    user = await db.users.find_one({**tf, "id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(404, "User not found")

    if user.get("role") == "platform_super_admin":
        raise HTTPException(403, "Platform super admin cannot be deactivated")

    old_state = user.get("is_active", True)

    if not active and user.get("role") == "partner_super_admin":
        active_supers = await db.users.count_documents({
            **tf, "role": "partner_super_admin", "is_active": True, "id": {"$ne": user_id},
        })
        if active_supers == 0:
            raise HTTPException(400, "Cannot deactivate the only active partner super admin.")

    await db.users.update_one({**tf, "id": user_id}, {"$set": {"is_active": active, "updated_at": now_iso()}})
    await create_audit_log(
        entity_type="user",
        entity_id=user_id,
        action="set_active" if active else "set_inactive",
        actor=f"admin:{admin['id']}",
        details={"is_active": {"old": old_state, "new": active}, "email": user.get("email")},
    )
    return {"message": f"User {'activated' if active else 'deactivated'}", "is_active": active}


@router.get("/admin/users/{user_id}/logs")
async def get_user_logs(user_id: str, page: int = 1, limit: int = 20, admin: Dict[str, Any] = Depends(get_tenant_super_admin)):
    tf = get_tenant_filter(admin)
    user = await db.users.find_one({**tf, "id": user_id}, {"_id": 0, "id": 1})
    if not user:
        raise HTTPException(404, "User not found")
    flt = {"entity_type": "user", "entity_id": user_id}
    total = await db.audit_logs.count_documents(flt)
    skip = (page - 1) * limit
    logs = await db.audit_logs.find(flt, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"logs": logs, "total": total, "page": page, "limit": limit, "pages": max(1, (total + limit - 1) // limit)}


@router.post("/admin/users/{user_id}/unlock")
async def admin_unlock_user(user_id: str, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    user = await db.users.find_one({**tf, "id": user_id}, {"_id": 0, "id": 1, "email": 1})
    if not user:
        raise HTTPException(404, "User not found")
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"failed_login_attempts": 0, "lockout_until": None}},
    )
    await create_audit_log(
        entity_type="user", entity_id=user_id, action="admin_unlock",
        actor=admin.get("email", "admin"),
        details={"email": user.get("email"), "unlocked_by": admin.get("email")},
    )
    return {"message": "User account unlocked successfully", "user_id": user_id}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _resolve_module_permissions(
    payload: AdminCreateUserRequest,
    caller_role: str,
    all_modules: Dict,
    partner_modules: Dict,
    preset_roles: Dict,
) -> Dict[str, str]:
    """Build module_permissions dict from payload, with sensible defaults."""

    # Explicit module_permissions in payload takes priority
    if payload.module_permissions:
        return {k: v for k, v in payload.module_permissions.items() if k in all_modules and v in ("read", "write")}

    # Preset role
    if payload.preset_role and payload.preset_role in preset_roles:
        return preset_roles[payload.preset_role]["module_permissions"]

    # platform_admin default: all modules with read
    if payload.role == "platform_admin":
        return {k: "read" for k in all_modules}

    # Legacy modules + access_level conversion
    if payload.modules:
        level = "write" if payload.access_level == "full_access" else "read"
        return {m: level for m in payload.modules if m in all_modules}

    # Default: no access (empty dict)
    return {}
