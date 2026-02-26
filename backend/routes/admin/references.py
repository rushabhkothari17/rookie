"""Admin: Website References CRUD routes."""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.helpers import make_id, now_iso
from core.security import require_admin, optional_get_current_user
from core.tenant import get_tenant_filter, set_tenant_id, tenant_id_of, get_tenant_admin, is_platform_admin, enrich_partner_codes, DEFAULT_TENANT_ID
from db.session import db
from services.audit_service import create_audit_log

router = APIRouter(prefix="/api", tags=["references"])


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


# ── Public endpoint ─────────────────────────────────────────────────────────

@router.get("/references")
async def list_references_public(
    partner_code: Optional[str] = None,
    user: Optional[Dict[str, Any]] = Depends(optional_get_current_user),
):
    """Return all references for use in frontend editors."""
    if user and user.get("tenant_id"):
        tid = user["tenant_id"]
    else:
        tid = DEFAULT_TENANT_ID
    refs = await db.website_references.find({"tenant_id": tid}, {"_id": 0}).sort("label", 1).to_list(500)
    return {"references": refs}


# ── Admin endpoints ──────────────────────────────────────────────────────────

@router.get("/admin/references")
async def list_references(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    refs = await db.website_references.find(tf, {"_id": 0}).sort("label", 1).to_list(500)
    refs = await enrich_partner_codes(refs, is_platform_admin(admin))
    return {"references": refs}


@router.post("/admin/references")
async def create_reference(payload: Dict[str, Any], admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    tid = tenant_id_of(admin)
    label = (payload.get("label") or "").strip()
    key = (payload.get("key") or _slugify(label)).strip()
    value = (payload.get("value") or "").strip()
    ref_type = (payload.get("type") or "text").strip()
    description = (payload.get("description") or "").strip()

    if not key or not label:
        raise HTTPException(status_code=400, detail="label and key are required")

    existing = await db.website_references.find_one({**tf, "key": key}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail=f"A reference with key '{key}' already exists")

    doc = {
        "id": make_id(),
        "tenant_id": tid,
        "key": key,
        "label": label,
        "type": ref_type,
        "value": value,
        "description": description,
        "system": False,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.website_references.insert_one(doc)
    await create_audit_log(entity_type="reference", entity_id=doc["id"], action="created", actor=admin.get("email", "admin"), details={"key": key, "type": ref_type}, tenant_id=tid)
    return {"reference": {k: v for k, v in doc.items() if k != "_id"}}


@router.put("/admin/references/{ref_id}")
async def update_reference(ref_id: str, payload: Dict[str, Any], admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    ref = await db.website_references.find_one({**tf, "id": ref_id}, {"_id": 0})
    if not ref:
        raise HTTPException(status_code=404, detail="Reference not found")

    update: Dict[str, Any] = {"updated_at": now_iso()}
    for field in ["label", "value", "type", "description"]:
        if field in payload:
            update[field] = payload[field]
    if not ref.get("system") and "key" in payload:
        new_key = (payload["key"] or "").strip()
        if new_key and new_key != ref["key"]:
            existing = await db.website_references.find_one({**tf, "key": new_key, "id": {"$ne": ref_id}}, {"_id": 0})
            if existing:
                raise HTTPException(status_code=400, detail=f"Key '{new_key}' is already in use")
            update["key"] = new_key

    await db.website_references.update_one({"id": ref_id}, {"$set": update})
    updated = await db.website_references.find_one({"id": ref_id}, {"_id": 0})
    await create_audit_log(entity_type="reference", entity_id=ref_id, action="updated", actor=admin.get("email", "admin"), details={"fields": list(update.keys())}, tenant_id=tenant_id_of(admin))
    return {"reference": updated}


@router.delete("/admin/references/{ref_id}")
async def delete_reference(ref_id: str, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    ref = await db.website_references.find_one({**tf, "id": ref_id}, {"_id": 0})
    if not ref:
        raise HTTPException(status_code=404, detail="Reference not found")
    if ref.get("system"):
        raise HTTPException(status_code=403, detail="System references cannot be deleted")
    await db.website_references.delete_one({"id": ref_id})
    await create_audit_log(entity_type="reference", entity_id=ref_id, action="deleted", actor=admin.get("email", "admin"), details={"key": ref.get("key")}, tenant_id=tenant_id_of(admin))
    return {"message": "Deleted"}
