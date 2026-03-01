"""One-Time Plans — rate table that drives per-record limit upgrade pricing."""
from __future__ import annotations
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from core.helpers import make_id, now_iso
from core.tenant import require_platform_admin, require_platform_super_admin
from db.session import db
from services.audit_service import create_audit_log

router = APIRouter(prefix="/api", tags=["admin-one-time-plans"])

# Canonical module keys that map to plan limit fields
ONE_TIME_MODULES = {
    "max_orders_per_month":       {"label": "Orders / month",      "description": "Extra orders per month"},
    "max_customers_per_month":    {"label": "Customers / month",   "description": "Extra customers per month"},
    "max_subscriptions_per_month":{"label": "Subscriptions / month","description": "Extra subscriptions per month"},
    "max_users":                  {"label": "Admin Users",         "description": "Extra admin user seats"},
    "max_storage_mb":             {"label": "Storage (MB)",        "description": "Extra storage in MB"},
    "max_resources":              {"label": "Resources",           "description": "Extra resource records"},
    "max_enquiries":              {"label": "Enquiries",           "description": "Extra enquiry records"},
    "max_templates":              {"label": "Templates",           "description": "Extra templates"},
    "max_email_templates":        {"label": "Email Templates",     "description": "Extra email templates"},
    "max_forms":                  {"label": "Forms",               "description": "Extra form records"},
}


class OTPRateCreate(BaseModel):
    module_key: str
    price_per_record: float
    currency: str = "GBP"
    is_active: bool = True


class OTPRateUpdate(BaseModel):
    price_per_record: Optional[float] = None
    currency: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/admin/one-time-plans")
async def list_rates(admin: Dict[str, Any] = Depends(require_platform_admin)):
    rates = await db.one_time_plan_rates.find({}, {"_id": 0}).sort("module_key", 1).to_list(100)
    return {"rates": rates, "modules": [{"key": k, **v} for k, v in ONE_TIME_MODULES.items()]}


@router.post("/admin/one-time-plans")
async def create_rate(body: OTPRateCreate, admin: Dict[str, Any] = Depends(require_platform_admin)):
    if body.module_key not in ONE_TIME_MODULES:
        raise HTTPException(400, f"Unknown module_key: {body.module_key}")
    existing = await db.one_time_plan_rates.find_one({"module_key": body.module_key})
    if existing:
        raise HTTPException(409, "Rate for this module already exists. Use PUT to update.")
    doc = {
        "id": make_id(), "module_key": body.module_key,
        "label": ONE_TIME_MODULES[body.module_key]["label"],
        "price_per_record": body.price_per_record,
        "currency": body.currency, "is_active": body.is_active,
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.one_time_plan_rates.insert_one(doc)
    doc.pop("_id", None)
    await create_audit_log(entity_type="one_time_rate", entity_id=doc["id"],
                           action="created", actor=admin.get("email"), details=doc)
    return doc


@router.put("/admin/one-time-plans/{rate_id}")
async def update_rate(rate_id: str, body: OTPRateUpdate, admin: Dict[str, Any] = Depends(require_platform_admin)):
    rate = await db.one_time_plan_rates.find_one({"id": rate_id}, {"_id": 0})
    if not rate:
        raise HTTPException(404, "Rate not found")
    updates = {k: v for k, v in body.dict(exclude_unset=True).items()}
    updates["updated_at"] = now_iso()
    await db.one_time_plan_rates.update_one({"id": rate_id}, {"$set": updates})
    await create_audit_log(entity_type="one_time_rate", entity_id=rate_id,
                           action="updated", actor=admin.get("email"), details=updates)
    return {**rate, **updates}


@router.delete("/admin/one-time-plans/{rate_id}")
async def delete_rate(rate_id: str, admin: Dict[str, Any] = Depends(require_platform_admin)):
    rate = await db.one_time_plan_rates.find_one({"id": rate_id}, {"_id": 0, "id": 1})
    if not rate:
        raise HTTPException(404, "Rate not found")
    await db.one_time_plan_rates.delete_one({"id": rate_id})
    return {"message": "Deleted"}
