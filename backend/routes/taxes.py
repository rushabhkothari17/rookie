"""Tax management routes: settings, global table, partner override rules."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.helpers import make_id, now_iso
from core.tenant import get_tenant_admin, tenant_id_of
from db.session import db
from models import TaxSettingsUpdate, TaxOverrideRuleCreate
from services.tax_tables import get_seed_tax_table

router = APIRouter(prefix="/api", tags=["taxes"])


# ── Tax Settings ─────────────────────────────────────────────────────────────

@router.get("/admin/taxes/settings")
async def get_tax_settings(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tid = tenant_id_of(admin)
    tenant = await db.tenants.find_one({"id": tid}, {"_id": 0, "tax_settings": 1})
    return {"tax_settings": (tenant or {}).get("tax_settings") or {}}


@router.put("/admin/taxes/settings")
async def update_tax_settings(
    payload: TaxSettingsUpdate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tid = tenant_id_of(admin)
    update = {k: v for k, v in payload.dict().items() if v is not None}
    if payload.enabled is not None:
        update["enabled"] = payload.enabled  # preserve False

    if not update:
        return {"message": "Nothing to update"}

    tenant = await db.tenants.find_one({"id": tid}, {"_id": 0, "tax_settings": 1})
    merged = {**(tenant or {}).get("tax_settings") or {}, **update}
    await db.tenants.update_one({"id": tid}, {"$set": {"tax_settings": merged}})
    return {"message": "Tax settings updated", "tax_settings": merged}


# ── Tax Table ─────────────────────────────────────────────────────────────────

async def _ensure_tax_table_seeded():
    """Seed the tax_tables collection from static data if it is empty."""
    count = await db.tax_tables.count_documents({})
    if count == 0:
        entries = get_seed_tax_table()
        if entries:
            await db.tax_tables.insert_many(entries)


@router.get("/admin/taxes/tables")
async def get_tax_tables(
    country_code: Optional[str] = None,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    await _ensure_tax_table_seeded()
    query: Dict[str, Any] = {}
    if country_code:
        query["country_code"] = country_code.upper()
    entries = await db.tax_tables.find(query, {"_id": 0}).sort(
        [("country_code", 1), ("state_code", 1)]
    ).to_list(600)
    return {"entries": entries}


@router.put("/admin/taxes/tables/{country_code}/{state_code}")
async def update_tax_table_entry(
    country_code: str,
    state_code: str,
    payload: Dict[str, Any],
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    rate = payload.get("rate")
    if rate is None:
        raise HTTPException(status_code=400, detail="rate is required")

    update: Dict[str, Any] = {"rate": float(rate)}
    if payload.get("label"):
        update["label"] = payload["label"]

    await _ensure_tax_table_seeded()
    await db.tax_tables.update_one(
        {"country_code": country_code.upper(), "state_code": state_code.upper()},
        {"$set": update},
        upsert=True,
    )
    return {"message": "Tax table entry updated"}


# ── Override Rules ────────────────────────────────────────────────────────────

@router.get("/admin/taxes/overrides")
async def get_tax_overrides(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tid = tenant_id_of(admin)
    rules = await db.tax_override_rules.find(
        {"tenant_id": tid}, {"_id": 0}
    ).sort("priority", -1).to_list(100)
    return {"rules": rules}


@router.post("/admin/taxes/overrides")
async def create_tax_override(
    payload: TaxOverrideRuleCreate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tid = tenant_id_of(admin)
    rule_id = make_id()
    rule = {
        "id": rule_id,
        "tenant_id": tid,
        "name": payload.name,
        "conditions": payload.conditions,
        "tax_rate": float(payload.tax_rate),
        "tax_name": payload.tax_name,
        "priority": payload.priority,
        "enabled": True,
        "created_at": now_iso(),
    }
    await db.tax_override_rules.insert_one(rule)
    rule.pop("_id", None)
    return {"rule": rule}


@router.put("/admin/taxes/overrides/{rule_id}")
async def update_tax_override(
    rule_id: str,
    payload: TaxOverrideRuleCreate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tid = tenant_id_of(admin)
    existing = await db.tax_override_rules.find_one(
        {"id": rule_id, "tenant_id": tid}, {"_id": 0}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Override rule not found")

    await db.tax_override_rules.update_one(
        {"id": rule_id, "tenant_id": tid},
        {"$set": {
            "name": payload.name,
            "conditions": payload.conditions,
            "tax_rate": float(payload.tax_rate),
            "tax_name": payload.tax_name,
            "priority": payload.priority,
            "updated_at": now_iso(),
        }},
    )
    return {"message": "Override rule updated"}


@router.delete("/admin/taxes/overrides/{rule_id}")
async def delete_tax_override(
    rule_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tid = tenant_id_of(admin)
    result = await db.tax_override_rules.delete_one({"id": rule_id, "tenant_id": tid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Override rule not found")
    return {"message": "Override rule deleted"}


# ── Customer tax-exempt toggle ─────────────────────────────────────────────────

@router.patch("/admin/customers/{customer_id}/tax-exempt")
async def set_customer_tax_exempt(
    customer_id: str,
    payload: Dict[str, Any],
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    from core.tenant import get_tenant_filter
    tf = get_tenant_filter(admin)
    customer = await db.customers.find_one({**tf, "id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    tax_exempt = bool(payload.get("tax_exempt", False))
    await db.customers.update_one(
        {"id": customer_id},
        {"$set": {"tax_exempt": tax_exempt}},
    )
    return {"message": "Customer tax-exempt status updated", "tax_exempt": tax_exempt}
