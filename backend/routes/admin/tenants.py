"""Admin: Tenant (Partner Organization) management — platform super admin only."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from core.helpers import make_id, now_iso
from core.security import pwd_context
from core.tenant import require_platform_admin, DEFAULT_TENANT_ID
from db.session import db
from models import TenantCreate, TenantUpdate, CreatePartnerAdminRequest

router = APIRouter(prefix="/api", tags=["admin-tenants"])


@router.get("/admin/tenants")
async def list_tenants(admin: Dict[str, Any] = Depends(require_platform_admin)):
    tenants = await db.tenants.find({}, {"_id": 0}).to_list(500)
    return {"tenants": tenants}


@router.post("/admin/tenants")
async def create_tenant(payload: TenantCreate, admin: Dict[str, Any] = Depends(require_platform_admin)):
    code = payload.code.lower().strip().replace(" ", "-")
    existing = await db.tenants.find_one({"code": code})
    if existing:
        raise HTTPException(status_code=400, detail="Partner code already in use")

    tenant_id = make_id()
    doc = {
        "id": tenant_id,
        "name": payload.name,
        "code": code,
        "status": payload.status,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    # Insert a copy so MongoDB _id mutation doesn't pollute our response dict
    await db.tenants.insert_one({**doc})

    # Seed default website_settings and app_settings for the new tenant
    existing_ws = await db.website_settings.find_one({"tenant_id": DEFAULT_TENANT_ID}, {"_id": 0})
    if existing_ws:
        new_ws = {k: v for k, v in existing_ws.items() if k != "_id"}
        new_ws["tenant_id"] = tenant_id
        await db.website_settings.insert_one(new_ws)

    existing_app = await db.app_settings.find_one(
        {"key": {"$exists": False}, "tenant_id": DEFAULT_TENANT_ID}, {"_id": 0}
    )
    if existing_app:
        new_app = {k: v for k, v in existing_app.items() if k != "_id"}
        new_app["tenant_id"] = tenant_id
        await db.app_settings.insert_one(new_app)

    return {"tenant": doc}


@router.put("/admin/tenants/{tenant_id}")
async def update_tenant(tenant_id: str, payload: TenantUpdate, admin: Dict[str, Any] = Depends(require_platform_admin)):
    tenant = await db.tenants.find_one({"id": tenant_id})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    updates: Dict[str, Any] = {"updated_at": now_iso()}
    if payload.name is not None:
        updates["name"] = payload.name
    if payload.status is not None:
        if payload.status not in ("active", "inactive"):
            raise HTTPException(status_code=400, detail="status must be 'active' or 'inactive'")
        updates["status"] = payload.status

    await db.tenants.update_one({"id": tenant_id}, {"$set": updates})
    updated = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    return {"tenant": updated}


@router.post("/admin/tenants/{tenant_id}/activate")
async def activate_tenant(tenant_id: str, admin: Dict[str, Any] = Depends(require_platform_admin)):
    result = await db.tenants.update_one(
        {"id": tenant_id},
        {"$set": {"status": "active", "updated_at": now_iso()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return {"message": "Tenant activated"}


@router.post("/admin/tenants/{tenant_id}/deactivate")
async def deactivate_tenant(tenant_id: str, admin: Dict[str, Any] = Depends(require_platform_admin)):
    if tenant_id == DEFAULT_TENANT_ID:
        raise HTTPException(status_code=400, detail="Cannot deactivate the default tenant")
    result = await db.tenants.update_one(
        {"id": tenant_id},
        {"$set": {"status": "inactive", "updated_at": now_iso()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return {"message": "Tenant deactivated"}


@router.post("/admin/tenants/{tenant_id}/create-admin")
async def create_partner_admin(
    tenant_id: str,
    payload: CreatePartnerAdminRequest,
    admin: Dict[str, Any] = Depends(require_platform_admin),
):
    """Create a partner_super_admin (or partner_admin) user for a tenant."""
    tenant = await db.tenants.find_one({"id": tenant_id})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    existing = await db.users.find_one({"email": payload.email.lower(), "tenant_id": tenant_id})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered for this tenant")

    valid_roles = ("partner_super_admin", "partner_admin", "partner_staff")
    if payload.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Role must be one of: {valid_roles}")

    user_id = make_id()
    hashed = pwd_context.hash(payload.password)
    user_doc = {
        "id": user_id,
        "email": payload.email.lower(),
        "password_hash": hashed,
        "full_name": payload.full_name,
        "company_name": "",
        "job_title": "",
        "phone": "",
        "is_verified": True,  # Platform admin creates verified users
        "is_admin": True,
        "role": payload.role,
        "tenant_id": tenant_id,
        "is_active": True,
        "created_at": now_iso(),
    }
    await db.users.insert_one(user_doc)
    return {
        "message": f"{payload.role} created for tenant {tenant['name']}",
        "user_id": user_id,
    }


@router.get("/admin/tenants/{tenant_id}/users")
async def list_tenant_users(tenant_id: str, admin: Dict[str, Any] = Depends(require_platform_admin)):
    users = await db.users.find(
        {"tenant_id": tenant_id},
        {"_id": 0, "password_hash": 0, "verification_code": 0},
    ).to_list(500)
    return {"users": users}
