"""Admin: User management routes (super admin only)."""
from __future__ import annotations

import re as _re
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from core.helpers import make_id, now_iso
from core.security import require_super_admin, require_admin, pwd_context
from core.tenant import get_tenant_filter, set_tenant_id, tenant_id_of, PLATFORM_ROLE, get_tenant_admin, get_tenant_super_admin, is_platform_admin, enrich_partner_codes
from db.session import db
from models import AdminCreateUserRequest
from services.audit_service import create_audit_log

router = APIRouter(prefix="/api", tags=["admin-users"])


@router.get("/admin/users")
async def admin_list_users(
    page: int = 1,
    per_page: int = 20,
    search: Optional[str] = None,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    # Show admin/partner users scoped to tenant (platform admin sees all)
    query: Dict[str, Any] = {**tf, "is_admin": True}
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
    from routes.admin.permissions import has_permission, PRESET_ROLES
    # Enforce permission check — only users with 'users' module create rights can add users
    if not await has_permission(admin, "users", "create"):
        raise HTTPException(status_code=403, detail="You don't have permission to create users")

    tid = tenant_id_of(admin)
    valid_roles = ("partner_super_admin", "partner_admin", "partner_staff", "admin", "super_admin")
    if payload.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Role must be one of: {valid_roles}")

    # Validate password complexity
    import re as _re2
    def _pw_ok(pw: str):
        if len(pw) < 10: return "Password must be at least 10 characters"
        if not _re2.search(r'[A-Z]', pw): return "Password must contain at least one uppercase letter"
        if not _re2.search(r'[a-z]', pw): return "Password must contain at least one lowercase letter"
        if not _re2.search(r'\d', pw): return "Password must contain at least one number"
        if not _re2.search(r'[!@#$%^&*()\-_=+\[\]{}|;:,.<>?/~`"]', pw): return "Password must contain at least one special character"
        return None
    pw_err = _pw_ok(payload.password)
    if pw_err:
        raise HTTPException(status_code=400, detail=pw_err)

    # Enforce: only one partner_super_admin per tenant
    if payload.role == "partner_super_admin":
        existing_super = await db.users.find_one({**get_tenant_filter(admin), "role": "partner_super_admin"}, {"_id": 0, "id": 1})
        if existing_super:
            raise HTTPException(status_code=400, detail="A super admin already exists for this tenant. Only one super admin is allowed per tenant.")

    # Enforce: only one super_admin per tenant
    if payload.role == "super_admin":
        existing_super = await db.users.find_one({**get_tenant_filter(admin), "role": "super_admin"}, {"_id": 0, "id": 1})
        if existing_super:
            raise HTTPException(status_code=400, detail="A super admin already exists for this tenant. Only one super admin is allowed per tenant.")

    tf = get_tenant_filter(admin)
    existing = await db.users.find_one({**tf, "email": payload.email.lower()}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # License: check user limit
    from services.license_service import check_limit as _check_limit
    _limit_check = await _check_limit(tid, "users")
    if not _limit_check["allowed"]:
        raise HTTPException(
            status_code=403,
            detail=f"User limit reached ({_limit_check['current']}/{_limit_check['limit']}). Please contact your platform administrator to upgrade your plan."
        )

    # Handle preset roles for permissions
    access_level = payload.access_level or "full_access"
    modules = payload.modules or []
    
    if payload.preset_role:
        from routes.admin.permissions import PRESET_ROLES, ADMIN_MODULES
        if payload.preset_role in PRESET_ROLES:
            preset = PRESET_ROLES[payload.preset_role]
            access_level = preset["access_level"]
            modules = preset["modules"]
    
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
        "access_level": access_level,
        "permissions": {"modules": modules},
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
    from routes.admin.permissions import has_permission
    tf = get_tenant_filter(admin)
    user = await db.users.find_one({**tf, "id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Only super admins or users with 'users' module edit rights can update admin users
    if not await has_permission(admin, "users", "edit"):
        raise HTTPException(status_code=403, detail="You don't have permission to edit users")

    allowed_roles = ("admin", "super_admin", "partner_super_admin", "partner_admin", "partner_staff")
    updates: Dict[str, Any] = {"updated_at": now_iso()}
    
    if "full_name" in payload and payload["full_name"]:
        updates["full_name"] = payload["full_name"].strip()
    if "role" in payload:
        if payload["role"] not in allowed_roles:
            raise HTTPException(status_code=400, detail=f"Role must be one of: {allowed_roles}")
        # Enforce: only one super_admin per tenant (skip if user already is super_admin)
        if payload["role"] == "super_admin" and user.get("role") != "super_admin":
            existing_super = await db.users.find_one(
                {**tf, "role": "super_admin", "id": {"$ne": user_id}}, {"_id": 0, "id": 1}
            )
            if existing_super:
                raise HTTPException(status_code=400, detail="A super admin already exists for this tenant. Only one super admin is allowed per tenant.")
        updates["role"] = payload["role"]
    
    # Handle permission updates
    if "access_level" in payload:
        if payload["access_level"] not in ("full_access", "read_only"):
            raise HTTPException(status_code=400, detail="access_level must be 'full_access' or 'read_only'")
        updates["access_level"] = payload["access_level"]
    
    if "modules" in payload:
        from routes.admin.permissions import ADMIN_MODULES
        invalid = [m for m in payload["modules"] if m not in ADMIN_MODULES]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Invalid modules: {', '.join(invalid)}")
        updates["permissions.modules"] = payload["modules"]
        updates["role"] = "custom"  # Reset to custom when modules manually changed
    
    if "is_active" in payload:
        # Can't deactivate self
        if user_id == admin.get("id") and not payload["is_active"]:
            raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
        updates["is_active"] = payload["is_active"]

    if "is_verified" in payload:
        updates["is_verified"] = bool(payload["is_verified"])

    if len(updates) > 1:  # More than just updated_at
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
    # SECURITY FIX: Apply tenant filter to prevent cross-tenant user manipulation
    tf = get_tenant_filter(admin)
    user = await db.users.find_one({**tf, "id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    old_state = user.get("is_active", True)

    # Orphan protection: block deactivating the only active partner_super_admin in a tenant
    if not active and user.get("role") in ("partner_super_admin", "super_admin"):
        active_supers = await db.users.count_documents({
            **tf,
            "role": user["role"],
            "is_active": True,
            "id": {"$ne": user_id},
        })
        if active_supers == 0:
            raise HTTPException(
                status_code=400,
                detail="Cannot deactivate the only active super admin. Please assign another super admin first."
            )

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
    # SECURITY FIX: Verify user belongs to admin's tenant before returning logs
    tf = get_tenant_filter(admin)
    user = await db.users.find_one({**tf, "id": user_id}, {"_id": 0, "id": 1})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    flt = {"entity_type": "user", "entity_id": user_id}
    total = await db.audit_logs.count_documents(flt)
    skip = (page - 1) * limit
    logs = await db.audit_logs.find(flt, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"logs": logs, "total": total, "page": page, "limit": limit, "pages": max(1, (total + limit - 1) // limit)}


@router.post("/admin/users/{user_id}/unlock")
async def admin_unlock_user(
    user_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """Admin override: unlock a brute-force locked account and reset failed login attempts."""
    tf = get_tenant_filter(admin)
    user = await db.users.find_one({**tf, "id": user_id}, {"_id": 0, "id": 1, "email": 1})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"failed_login_attempts": 0, "lockout_until": None}},
    )
    await create_audit_log(
        entity_type="user",
        entity_id=user_id,
        action="admin_unlock",
        actor=admin.get("email", "admin"),
        details={"email": user.get("email"), "unlocked_by": admin.get("email")},
    )
    return {"message": "User account unlocked successfully", "user_id": user_id}

