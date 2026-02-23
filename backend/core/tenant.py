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
    Platform super admins can optionally pass view_as to impersonate a tenant.
    """
    if is_platform_admin(user):
        if view_as:
            return {"tenant_id": view_as}
        return {}  # See all data by default
    tenant_id = user.get("tenant_id") or DEFAULT_TENANT_ID
    return {"tenant_id": tenant_id}


def set_tenant_id(doc: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
    """Inject tenant_id into a document dict before inserting."""
    if not is_platform_admin(user):
        doc["tenant_id"] = user.get("tenant_id") or DEFAULT_TENANT_ID
    else:
        if "tenant_id" not in doc:
            doc["tenant_id"] = DEFAULT_TENANT_ID
    return doc


def tenant_id_of(user: Dict[str, Any], view_as: Optional[str] = None) -> str:
    """Return the tenant_id for a user (platform admins default to DEFAULT_TENANT_ID)."""
    if is_platform_admin(user) and view_as:
        return view_as
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

