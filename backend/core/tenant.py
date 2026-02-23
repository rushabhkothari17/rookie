"""Tenant (multi-tenancy) helpers for Automate Accounts."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException

from core.security import require_admin, get_current_user
from db.session import db

DEFAULT_TENANT_ID = "automate-accounts"
PLATFORM_ROLE = "platform_super_admin"


def is_platform_admin(user: Dict[str, Any]) -> bool:
    return user.get("role") == PLATFORM_ROLE


def get_tenant_filter(user: Dict[str, Any]) -> Dict[str, Any]:
    """Return a MongoDB filter dict scoped to the user's tenant.
    Platform super admins receive an empty filter (see all tenants).
    """
    if is_platform_admin(user):
        return {}
    tenant_id = user.get("tenant_id") or DEFAULT_TENANT_ID
    return {"tenant_id": tenant_id}


def set_tenant_id(doc: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
    """Inject tenant_id into a document dict before inserting."""
    if not is_platform_admin(user):
        doc["tenant_id"] = user.get("tenant_id") or DEFAULT_TENANT_ID
    else:
        # Platform admins creating resources must explicitly pass tenant_id
        if "tenant_id" not in doc:
            doc["tenant_id"] = DEFAULT_TENANT_ID
    return doc


def tenant_id_of(user: Dict[str, Any]) -> str:
    """Return the tenant_id for a user (platform admins default to DEFAULT_TENANT_ID)."""
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
