"""Admin: Website References CRUD routes."""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.helpers import make_id, now_iso
from core.security import require_admin
from db.session import db
from services.audit_service import create_audit_log
from services.settings_service import SettingsService

router = APIRouter(prefix="/api", tags=["references"])

ZOHO_SEED_REFS = [
    {"key": "zoho_reseller_signup_us", "label": "Zoho Reseller Signup (US)", "description": "Zoho Reseller Customer Signup link shown at checkout (US data center)", "type": "url"},
    {"key": "zoho_reseller_signup_ca", "label": "Zoho Reseller Signup (Canada)", "description": "Zoho Reseller Customer Signup link shown at checkout (Canada data center)", "type": "url"},
    {"key": "zoho_partner_tag_us", "label": "Zoho Partner Tag (US)", "description": "Partner tagging link shown at checkout (US data center)", "type": "url"},
    {"key": "zoho_partner_tag_ca", "label": "Zoho Partner Tag (Canada)", "description": "Partner tagging link shown at checkout (Canada data center)", "type": "url"},
    {"key": "zoho_access_instructions_url", "label": "Zoho Access Instructions URL", "description": "URL explaining how customers should provide Zoho account access", "type": "url"},
]


async def _seed_zoho_refs() -> None:
    """Seed Zoho links as regular (deletable) references if they don't already exist."""
    existing_keys = {r["key"] for r in await db.website_references.find({}, {"key": 1, "_id": 0}).to_list(500)}
    settings = await SettingsService.get_all(db)
    settings_map = {s["key"]: s.get("value_json", "") for s in settings}
    for seed in ZOHO_SEED_REFS:
        if seed["key"] in existing_keys:
            continue
        doc = {
            "id": make_id(),
            "key": seed["key"],
            "label": seed["label"],
            "type": seed["type"],
            "value": str(settings_map.get(seed["key"]) or ""),
            "description": seed["description"],
            "system": False,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        await db.website_references.insert_one(doc)


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


# ── Public endpoint ─────────────────────────────────────────────────────────

@router.get("/references")
async def list_references_public():
    """Return all references for use in frontend editors."""
    refs = await db.website_references.find({}, {"_id": 0}).sort("label", 1).to_list(500)
    return {"references": refs}


# ── Admin endpoints ──────────────────────────────────────────────────────────

@router.get("/admin/references")
async def list_references(admin: Dict[str, Any] = Depends(require_admin)):
    refs = await db.website_references.find({}, {"_id": 0}).sort("label", 1).to_list(500)
    return {"references": refs}


@router.post("/admin/references")
async def create_reference(payload: Dict[str, Any], admin: Dict[str, Any] = Depends(require_admin)):
    label = (payload.get("label") or "").strip()
    key = (payload.get("key") or _slugify(label)).strip()
    value = (payload.get("value") or "").strip()
    ref_type = (payload.get("type") or "text").strip()
    description = (payload.get("description") or "").strip()

    if not key or not label:
        raise HTTPException(status_code=400, detail="label and key are required")

    existing = await db.website_references.find_one({"key": key}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail=f"A reference with key '{key}' already exists")

    doc = {
        "id": make_id(),
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
    await create_audit_log(entity_type="reference", entity_id=doc["id"], action="created", actor=admin.get("email", "admin"), details={"key": key, "type": ref_type})
    return {"reference": {k: v for k, v in doc.items() if k != "_id"}}


@router.put("/admin/references/{ref_id}")
async def update_reference(ref_id: str, payload: Dict[str, Any], admin: Dict[str, Any] = Depends(require_admin)):
    ref = await db.website_references.find_one({"id": ref_id}, {"_id": 0})
    if not ref:
        raise HTTPException(status_code=404, detail="Reference not found")

    update: Dict[str, Any] = {"updated_at": now_iso()}
    for field in ["label", "value", "type", "description"]:
        if field in payload:
            update[field] = payload[field]
    # Allow key update only for non-system refs
    if not ref.get("system") and "key" in payload:
        new_key = (payload["key"] or "").strip()
        if new_key and new_key != ref["key"]:
            existing = await db.website_references.find_one({"key": new_key, "id": {"$ne": ref_id}}, {"_id": 0})
            if existing:
                raise HTTPException(status_code=400, detail=f"Key '{new_key}' is already in use")
            update["key"] = new_key

    await db.website_references.update_one({"id": ref_id}, {"$set": update})
    updated = await db.website_references.find_one({"id": ref_id}, {"_id": 0})
    await create_audit_log(entity_type="reference", entity_id=ref_id, action="updated", actor=admin.get("email", "admin"), details={"fields": list(update.keys())})
    return {"reference": updated}


@router.delete("/admin/references/{ref_id}")
async def delete_reference(ref_id: str, admin: Dict[str, Any] = Depends(require_admin)):
    ref = await db.website_references.find_one({"id": ref_id}, {"_id": 0})
    if not ref:
        raise HTTPException(status_code=404, detail="Reference not found")
    if ref.get("system"):
        raise HTTPException(status_code=403, detail="System references cannot be deleted")
    await db.website_references.delete_one({"id": ref_id})
    await create_audit_log(entity_type="reference", entity_id=ref_id, action="deleted", actor=admin.get("email", "admin"), details={"key": ref.get("key")})
    return {"message": "Deleted"}
