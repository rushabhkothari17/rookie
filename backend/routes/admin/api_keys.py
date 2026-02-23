"""Admin: API key management for tenant integrations."""
from __future__ import annotations

import hashlib
import secrets
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from core.helpers import make_id, now_iso
from core.tenant import get_tenant_admin, get_tenant_filter, tenant_id_of
from db.session import db
from services.audit_service import create_audit_log

router = APIRouter(prefix="/api", tags=["admin-api-keys"])


def _generate_key() -> str:
    return f"ak_{secrets.token_hex(24)}"


def _hash_key(key: str) -> str:
    """SHA-256 hash of the API key. Only the hash is stored in DB."""
    return hashlib.sha256(key.encode()).hexdigest()


def _mask_key(suffix: str) -> str:
    """Display mask using stored suffix — never the raw key."""
    return "ak_" + "•" * 20 + suffix[-4:]


@router.get("/admin/api-keys")
async def list_api_keys(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """List only active API keys for the current tenant (key value masked)."""
    tf = get_tenant_filter(admin)
    keys = await db.api_keys.find({**tf, "is_active": True}, {"_id": 0, "key": 0, "key_hash": 0}).sort("created_at", -1).to_list(10)
    for k in keys:
        suffix = k.pop("key_suffix", "????")
        k["key_masked"] = _mask_key(suffix)
    return {"api_keys": keys}


@router.post("/admin/api-keys")
async def create_api_key(
    payload: Dict[str, Any],
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """Generate a new API key. Deactivates any existing active key for this tenant."""
    tid = tenant_id_of(admin)
    tf = get_tenant_filter(admin)

    name = (payload.get("name") or "Default Key").strip()[:80]

    # Deactivate all existing active keys for this tenant
    await db.api_keys.update_many(
        {**tf, "is_active": True},
        {"$set": {"is_active": False, "deactivated_at": now_iso()}},
    )

    new_key = _generate_key()
    doc = {
        "id": make_id(),
        "tenant_id": tid,
        "key_hash": _hash_key(new_key),   # Only the hash persists
        "key_suffix": new_key[-8:],        # Last 8 chars for display masking
        "name": name,
        "is_active": True,
        "created_at": now_iso(),
        "last_used_at": None,
    }
    await db.api_keys.insert_one(doc)
    await create_audit_log(
        entity_type="api_key",
        entity_id=doc["id"],
        action="api_key_created",
        actor=admin.get("email", "admin"),
        details={"name": name, "tenant_id": tid},
    )
    # Return full key ONCE — client must copy it now; only the hash is stored
    return {
        "id": doc["id"],
        "key": new_key,
        "key_masked": _mask_key(new_key[-8:]),
        "name": name,
        "is_active": True,
        "created_at": doc["created_at"],
        "message": "Copy this key now — it will not be shown again in full.",
    }


@router.delete("/admin/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """Revoke (deactivate) an API key."""
    tf = get_tenant_filter(admin)
    result = await db.api_keys.update_one(
        {**tf, "id": key_id},
        {"$set": {"is_active": False, "deactivated_at": now_iso()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="API key not found")
    await create_audit_log(
        entity_type="api_key",
        entity_id=key_id,
        action="api_key_revoked",
        actor=admin.get("email", "admin"),
        details={"key_id": key_id, "tenant_id": tenant_id_of(admin)},
    )
    return {"success": True, "message": "API key revoked"}
