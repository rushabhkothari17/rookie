"""Admin: API key management for tenant integrations."""
from __future__ import annotations

import secrets
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from core.helpers import make_id, now_iso
from core.tenant import get_tenant_admin, get_tenant_filter, tenant_id_of
from db.session import db

router = APIRouter(prefix="/api", tags=["admin-api-keys"])


def _generate_key() -> str:
    return f"ak_{secrets.token_hex(24)}"


def _mask_key(key: str) -> str:
    if len(key) <= 12:
        return key[:4] + "•" * (len(key) - 4)
    return key[:8] + "•" * 20 + key[-4:]


@router.get("/admin/api-keys")
async def list_api_keys(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """List all API keys for the current tenant (key value masked)."""
    tf = get_tenant_filter(admin)
    keys = await db.api_keys.find(tf, {"_id": 0}).sort("created_at", -1).to_list(100)
    # Mask the key value for security
    for k in keys:
        if k.get("key"):
            k["key_masked"] = _mask_key(k["key"])
            del k["key"]
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
        "key": new_key,
        "name": name,
        "is_active": True,
        "created_at": now_iso(),
        "last_used_at": None,
    }
    await db.api_keys.insert_one(doc)
    # Return full key ONCE — client must copy it now
    return {
        "id": doc["id"],
        "key": new_key,
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
    return {"success": True, "message": "API key revoked"}


async def get_tenant_from_api_key(x_api_key: Optional[str]) -> Optional[str]:
    """Resolve tenant_id from an API key. Returns None if not found/invalid."""
    if not x_api_key:
        return None
    key_doc = await db.api_keys.find_one(
        {"key": x_api_key, "is_active": True}, {"_id": 0, "tenant_id": 1, "id": 1}
    )
    if not key_doc:
        return None
    # Fire-and-forget last_used update (non-blocking)
    await db.api_keys.update_one(
        {"id": key_doc["id"]},
        {"$set": {"last_used_at": now_iso()}},
    )
    return key_doc["tenant_id"]
