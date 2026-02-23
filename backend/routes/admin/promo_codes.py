"""Admin: Promo code management."""
from __future__ import annotations

import re as _re
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.helpers import make_id, now_iso
from core.security import require_admin
from core.tenant import get_tenant_filter, set_tenant_id, tenant_id_of, get_tenant_admin
from db.session import db
from models import PromoCodeCreate, PromoCodeUpdate
from services.audit_service import create_audit_log

router = APIRouter(prefix="/api", tags=["admin-promo-codes"])


@router.get("/admin/promo-codes")
async def admin_list_promo_codes(
    page: int = 1,
    per_page: int = 20,
    search: Optional[str] = None,
    enabled: Optional[str] = None,
    created_from: Optional[str] = None,
    created_to: Optional[str] = None,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    query: Dict[str, Any] = {**tf}
    if search:
        query["code"] = {"$regex": _re.escape(search), "$options": "i"}
    if enabled is not None:
        query["enabled"] = enabled == "true"
    if created_from:
        query.setdefault("created_at", {})["$gte"] = created_from
    if created_to:
        query.setdefault("created_at", {})["$lte"] = created_to + "T23:59:59"
    total = await db.promo_codes.count_documents(query)
    skip = (page - 1) * per_page
    codes = await db.promo_codes.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(per_page).to_list(per_page)
    return {"promo_codes": codes, "page": page, "per_page": per_page, "total": total, "total_pages": max(1, (total + per_page - 1) // per_page)}


@router.post("/admin/promo-codes")
async def admin_create_promo_code(payload: PromoCodeCreate, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    tid = tenant_id_of(admin)
    existing = await db.promo_codes.find_one({**tf, "code": payload.code.upper()}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Promo code already exists")
    code_id = make_id()
    doc = {
        "id": code_id, "tenant_id": tid, "code": payload.code.upper(),
        "discount_type": payload.discount_type, "discount_value": payload.discount_value,
        "applies_to": payload.applies_to, "applies_to_products": payload.applies_to_products,
        "product_ids": payload.product_ids, "expiry_date": payload.expiry_date,
        "max_uses": payload.max_uses, "one_time_code": payload.one_time_code,
        "enabled": payload.enabled, "usage_count": 0, "created_at": now_iso(),
    }
    await db.promo_codes.insert_one(doc)
    await create_audit_log(
        entity_type="promo_code",
        entity_id=code_id,
        action="created",
        actor=f"admin:{admin.get('email', admin['id'])}",
        details={"code": payload.code.upper(), "discount_type": payload.discount_type, "discount_value": payload.discount_value, "applies_to": payload.applies_to},
    )
    return {"message": "Promo code created", "id": code_id}


@router.put("/admin/promo-codes/{code_id}")
async def admin_update_promo_code(code_id: str, payload: PromoCodeUpdate, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    existing = await db.promo_codes.find_one({**tf, "id": code_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Promo code not found")
    update: Dict[str, Any] = {}
    for field in ["discount_type", "discount_value", "applies_to", "applies_to_products", "product_ids", "expiry_date", "max_uses", "one_time_code", "enabled"]:
        val = getattr(payload, field, None)
        if val is not None:
            update[field] = val
    if update:
        await db.promo_codes.update_one({"id": code_id}, {"$set": update})
    await create_audit_log(
        entity_type="promo_code",
        entity_id=code_id,
        action="updated",
        actor=f"admin:{admin.get('email', admin['id'])}",
        details={"changes": update},
    )
    return {"message": "Promo code updated"}


@router.delete("/admin/promo-codes/{code_id}")
async def admin_delete_promo_code(code_id: str, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    existing = await db.promo_codes.find_one({**tf, "id": code_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Promo code not found")
    await db.promo_codes.delete_one({"id": code_id})
    await create_audit_log(
        entity_type="promo_code",
        entity_id=code_id,
        action="deleted",
        actor=f"admin:{admin.get('email', admin['id'])}",
        details={"code": existing.get("code")},
    )
    return {"message": "Promo code deleted"}


@router.get("/admin/promo-codes/{promo_id}/logs")
async def get_promo_code_logs(promo_id: str, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    logs = await db.audit_logs.find({"entity_type": "promo_code", "entity_id": promo_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"logs": logs}

