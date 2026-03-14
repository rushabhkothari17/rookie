"""Tenant (multi-tenancy) helpers for Automate Accounts."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Header

from core.security import require_admin, require_super_admin, get_current_user
from db.session import db


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

DEFAULT_TENANT_ID = "automate-accounts"
PLATFORM_ROLES = {"platform_admin", "platform_super_admin"}
PLATFORM_ROLE = "platform_super_admin"  # canonical super-admin role


def is_platform_admin(user: Dict[str, Any]) -> bool:
    return user.get("role") in PLATFORM_ROLES


def get_tenant_filter(user: Dict[str, Any]) -> Dict[str, Any]:
    """Return a MongoDB filter dict scoped to the user's tenant.
    Platform admins see all data (no tenant filter).
    """
    if is_platform_admin(user):
        return {}  # See all data across all tenants
    tenant_id = user.get("tenant_id") or DEFAULT_TENANT_ID
    return {"tenant_id": tenant_id}


def set_tenant_id(doc: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
    """Inject tenant_id into a document dict before inserting."""
    if not is_platform_admin(user):
        doc["tenant_id"] = user.get("tenant_id") or DEFAULT_TENANT_ID
    else:
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


async def require_platform_super_admin(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """FastAPI dependency: only platform_super_admin may proceed.
    Regular platform_admin is explicitly blocked — use for destructive/sensitive actions."""
    if user.get("role") != "platform_super_admin":
        raise HTTPException(
            status_code=403,
            detail="This action requires platform super admin access. Contact your platform owner.",
        )
    return user


async def resolve_tenant(partner_code: str) -> Dict[str, Any]:
    """Look up a tenant by code/slug. Raises 400 if not found, 403 if inactive."""
    tenant = await db.tenants.find_one({"code": partner_code.lower()}, {"_id": 0})
    if not tenant:
        raise HTTPException(status_code=400, detail="Invalid partner code")
    if tenant.get("status") != "active":
        raise HTTPException(status_code=403, detail="This organization is inactive. Contact your administrator.")
    return tenant


async def resolve_tenant_by_domain(domain: str) -> Optional[Dict[str, Any]]:
    """
    Look up a tenant by custom domain.
    
    Partners can configure custom domains (e.g., billing.company.com) to serve their
    customers without requiring a partner_code in login forms.
    
    Returns None if no tenant matches the domain.
    """
    if not domain:
        return None
    
    # Normalize domain (lowercase, remove port)
    domain = domain.lower().split(":")[0]
    
    # Look up by custom_domain field
    tenant = await db.tenants.find_one(
        {"custom_domains": domain, "status": "active"},
        {"_id": 0}
    )
    
    if not tenant:
        # Also check custom_domain (singular) for backwards compatibility
        tenant = await db.tenants.find_one(
            {"custom_domain": domain, "status": "active"},
            {"_id": 0}
        )
    
    return tenant


class TenantContext:
    """Dependency that extracts tenant filter from request headers + JWT."""
    def __init__(self, admin: Dict[str, Any]):
        self.admin = admin
        self.filter = get_tenant_filter(admin)
        self.tenant_id = tenant_id_of(admin)


async def get_tenant_ctx(
    admin: Dict[str, Any] = Depends(require_admin),
) -> TenantContext:
    """FastAPI dependency returning TenantContext with filter + tenant_id."""
    return TenantContext(admin=admin)


async def get_tenant_admin(
    admin: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Drop-in replacement for require_admin. Sets request-scoped tenant context for audit log scoping."""
    from services.audit_service import set_audit_tenant
    tid = admin.get("tenant_id") or (None if is_platform_admin(admin) else DEFAULT_TENANT_ID)
    set_audit_tenant(tid)
    return admin


async def get_tenant_super_admin(
    admin: Dict[str, Any] = Depends(require_super_admin),
) -> Dict[str, Any]:
    """Same as get_tenant_admin but requires super_admin or platform_admin role."""
    return admin


async def resolve_api_key_tenant(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> Optional[str]:
    """FastAPI dependency: resolve tenant_id from X-API-Key header.
    Looks up by SHA-256 hash only. Plaintext fallback removed (security hardening).
    Returns None if header missing; raises 401 if key invalid/inactive."""
    import hashlib
    if not x_api_key:
        return None

    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    key_doc = await db.api_keys.find_one(
        {"key_hash": key_hash, "is_active": True}, {"_id": 0, "tenant_id": 1, "id": 1}
    )
    if not key_doc:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")
    # Update last_used_at
    await db.api_keys.update_one(
        {"id": key_doc["id"]}, {"$set": {"last_used_at": _now_iso()}}
    )
    return key_doc["tenant_id"]



async def enrich_partner_codes(records: list, is_platform: bool) -> list:
    """Add partner_code field to each record when viewed by platform admin.
    Looks up tenant code from tenant_id. Records without tenant_id get '—'."""
    if not is_platform or not records:
        return records
    tenant_ids = {r.get("tenant_id") for r in records if r.get("tenant_id")}
    if not tenant_ids:
        return records
    tenants = await db.tenants.find(
        {"id": {"$in": list(tenant_ids)}},
        {"_id": 0, "id": 1, "code": 1}
    ).to_list(500)
    code_map = {t["id"]: t.get("code", "—") for t in tenants}
    for r in records:
        r["partner_code"] = code_map.get(r.get("tenant_id"), "—")
    return records
