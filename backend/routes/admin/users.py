"""Admin: User management routes (super admin only)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from core.helpers import make_id, now_iso
from core.security import require_super_admin, require_admin, pwd_context
from core.tenant import get_tenant_filter, set_tenant_id, tenant_id_of, PLATFORM_ROLE, get_tenant_admin, get_tenant_super_admin
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
            {"email": {"$regex": search, "$options": "i"}},
            {"full_name": {"$regex": search, "$options": "i"}},
        ]
    total = await db.users.count_documents(query)
    skip = (page - 1) * per_page
    users = await db.users.find(query, {"_id": 0, "password_hash": 0}).skip(skip).limit(per_page).to_list(per_page)
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
    tid = tenant_id_of(admin)
    valid_roles = ("partner_super_admin", "partner_admin", "partner_staff", "admin", "super_admin")
    if payload.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Role must be one of: {valid_roles}")

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
        "role": payload.role,
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
    tf = get_tenant_filter(admin)
    user = await db.users.find_one({**tf, "id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    allowed_roles = ("admin", "super_admin")
    updates: Dict[str, Any] = {}
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

    if updates:
        await db.users.update_one({"id": user_id}, {"$set": updates})
        await create_audit_log(
            entity_type="user",
            entity_id=user_id,
            action="admin_user_updated",
            actor=f"admin:{admin['id']}",
            details=updates,
        )

    user.update(updates)
    user.pop("password_hash", None)
    user.pop("_id", None)
    return {"message": "User updated", "user": user}


@router.patch("/admin/users/{user_id}/active")
async def admin_set_user_active(
    user_id: str,
    active: bool,
    admin: Dict[str, Any] = Depends(get_tenant_super_admin),
):
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    old_state = user.get("is_active", True)
    await db.users.update_one({"id": user_id}, {"$set": {"is_active": active, "updated_at": now_iso()}})

    await create_audit_log(
        entity_type="user",
        entity_id=user_id,
        action="set_active" if active else "set_inactive",
        actor=f"admin:{admin['id']}",
        details={"is_active": {"old": old_state, "new": active}, "email": user.get("email")},
    )
    return {"message": f"User {'activated' if active else 'deactivated'}", "is_active": active}


@router.get("/admin/users/{user_id}/logs")
async def get_user_logs(user_id: str, admin: Dict[str, Any] = Depends(get_tenant_super_admin)):
    logs = await db.audit_logs.find({"entity_type": "user", "entity_id": user_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"logs": logs}

