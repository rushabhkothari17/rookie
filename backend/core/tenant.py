"""Tenant (multi-tenancy) helpers for Automate Accounts."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Header, Request

from core.security import require_admin, require_super_admin, get_current_user
from db.session import db

DEFAULT_TENANT_ID = "automate-accounts"
PLATFORM_ROLE = "platform_admin"


def is_platform_admin(user: Dict[str, Any]) -> bool:
    return user.get("role") == PLATFORM_ROLE


def get_tenant_filter(user: Dict[str, Any], view_as: Optional[str] = None) -> Dict[str, Any]:
    """Return a MongoDB filter dict scoped to the user's tenant.
    Platform admins can optionally pass view_as (or have _view_as injected) to impersonate a tenant.
    """
    effective_view_as = view_as or user.get("_view_as")
    if is_platform_admin(user):
        if effective_view_as:
            return {"tenant_id": effective_view_as}
        return {}  # See all data by default
    tenant_id = user.get("tenant_id") or DEFAULT_TENANT_ID
    return {"tenant_id": tenant_id}


def set_tenant_id(doc: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
    """Inject tenant_id into a document dict before inserting."""
    effective_view_as = user.get("_view_as")
    if not is_platform_admin(user):
        doc["tenant_id"] = user.get("tenant_id") or DEFAULT_TENANT_ID
    else:
        doc["tenant_id"] = effective_view_as or DEFAULT_TENANT_ID
    return doc


def tenant_id_of(user: Dict[str, Any], view_as: Optional[str] = None) -> str:
    """Return the tenant_id for a user (platform admins default to DEFAULT_TENANT_ID)."""
    effective_view_as = view_as or user.get("_view_as")
    if is_platform_admin(user) and effective_view_as:
        return effective_view_as
    if is_platform_admin(user):
        return DEFAULT_TENANT_ID
    return user.get("tenant_id") or DEFAULT_TENANT_ID


async def require_platform_admin(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """FastAPI dependency: only platform super admins may proceed."""
    if not is_platform_admin(user):
        raise HTTPException(status_code=403, detail="Platform admin access required")
    return user


async def resolve_tenant(partner_code: str) -> Dict[str, Any]:
    """Look up a tenant by code/slug. Raises 400 if not found, 403 if inactive."""
    tenant = await db.tenants.find_one({"code": partner_code.lower()}, {"_id": 0})
    if not tenant:
        raise HTTPException(status_code=400, detail="Invalid partner code")
    if tenant.get("status") != "active":
        raise HTTPException(status_code=403, detail="This organization is inactive. Contact your administrator.")
    return tenant


class TenantContext:
    """Dependency that extracts tenant filter from request headers + JWT.
    Platform admins can send X-View-As-Tenant header to impersonate a tenant.
    """
    def __init__(self, admin: Dict[str, Any], view_as: Optional[str]):
        self.admin = admin
        self.view_as = view_as
        self.filter = get_tenant_filter(admin, view_as)
        self.tenant_id = tenant_id_of(admin, view_as)


async def get_tenant_ctx(
    admin: Dict[str, Any] = Depends(require_admin),
    x_view_as_tenant: Optional[str] = Header(default=None, alias="X-View-As-Tenant"),
) -> TenantContext:
    """FastAPI dependency returning TenantContext with filter + tenant_id."""
    view_as = None
    if x_view_as_tenant and is_platform_admin(admin):
        # Validate the target tenant exists
        t = await db.tenants.find_one({"id": x_view_as_tenant}, {"_id": 0})
        if t:
            view_as = x_view_as_tenant
    return TenantContext(admin=admin, view_as=view_as)


async def get_tenant_admin(
    admin: Dict[str, Any] = Depends(require_admin),
    x_view_as_tenant: Optional[str] = Header(default=None, alias="X-View-As-Tenant"),
) -> Dict[str, Any]:
    """Drop-in replacement for require_admin that injects _view_as for platform admins.
    All get_tenant_filter / tenant_id_of calls will automatically respect it.
    Sets request-scoped tenant context for automatic audit log scoping.
    """
    from services.audit_service import set_audit_tenant
    if x_view_as_tenant and is_platform_admin(admin):
        t = await db.tenants.find_one({"id": x_view_as_tenant}, {"_id": 0})
        if t:
            set_audit_tenant(x_view_as_tenant)
            return {**admin, "_view_as": x_view_as_tenant}
    # Set tenant_id from the user's own tenant
    tid = admin.get("tenant_id") or (None if is_platform_admin(admin) else DEFAULT_TENANT_ID)
    set_audit_tenant(tid)
    return admin


async def get_tenant_super_admin(
    admin: Dict[str, Any] = Depends(require_super_admin),
    x_view_as_tenant: Optional[str] = Header(default=None, alias="X-View-As-Tenant"),
) -> Dict[str, Any]:
    """Same as get_tenant_admin but requires super_admin or platform_admin role."""
    if x_view_as_tenant and is_platform_admin(admin):
        t = await db.tenants.find_one({"id": x_view_as_tenant}, {"_id": 0})
        if t:
            return {**admin, "_view_as": x_view_as_tenant}
    return admin

