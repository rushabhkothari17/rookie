"""Admin: Currency override, sync logs, partner map."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from core.security import require_admin
from core.tenant import get_tenant_filter, set_tenant_id, tenant_id_of, get_tenant_admin
from core.helpers import now_iso
from db.session import db
from models import CurrencyOverrideRequest, CustomerPartnerMapUpdate
from services.audit_service import create_audit_log

router = APIRouter(prefix="/api", tags=["admin-misc"])


@router.post("/admin/currency-override")
async def admin_currency_override(
    payload: CurrencyOverrideRequest,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    user = await db.users.find_one({"email": payload.customer_email.lower()}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    await db.customers.update_one({"id": customer["id"]}, {"$set": {"currency": payload.currency, "currency_locked": True}})
    await create_audit_log(
        entity_type="customer",
        entity_id=customer["id"],
        action="currency_override",
        actor=f"admin:{admin.get('email', admin['id'])}",
        details={"currency": payload.currency, "email": payload.customer_email},
    )
    return {"message": "Currency overridden"}


@router.get("/admin/sync-logs")
async def admin_sync_logs(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    logs = await db.zoho_sync_logs.find(tf, {"_id": 0}).to_list(500)
    return {"logs": logs}


@router.post("/admin/sync-logs/{log_id}/retry")
async def admin_retry_sync(log_id: str, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    log_entry = await db.zoho_sync_logs.find_one({"id": log_id}, {"_id": 0})
    await db.zoho_sync_logs.update_one(
        {"id": log_id},
        {"$set": {"status": "Sent", "last_error": None}, "$inc": {"attempts": 1}},
    )
    await create_audit_log(entity_type="sync_log", entity_id=log_id, action="sync_retry", actor=admin["email"], details={"entity_type": log_entry.get("entity_type") if log_entry else None})
    return {"message": "Retry queued", "mocked": True}


@router.put("/admin/customers/{customer_id}/partner-map")
async def admin_update_customer_partner_map(
    customer_id: str,
    payload: CustomerPartnerMapUpdate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    existing = await db.customers.find_one({**tf, "id": customer_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Customer not found")
    await db.customers.update_one({"id": customer_id}, {"$set": {"partner_map": payload.partner_map}})
    await create_audit_log(
        entity_type="customer",
        entity_id=customer_id,
        action="partner_map_updated",
        actor=f"admin:{admin.get('email', admin['id'])}",
        details={"partner_map": payload.partner_map},
    )
    return {"message": "Partner map updated"}


@router.get("/admin/customers/{customer_id}/notes")
async def admin_get_customer_notes(customer_id: str, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    customer = await db.customers.find_one({**tf, "id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return {"notes": customer.get("notes", [])}


@router.post("/admin/customers/{customer_id}/notes")
async def admin_add_customer_note(
    customer_id: str,
    payload: Dict[str, Any],
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    customer = await db.customers.find_one({**tf, "id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    note = {"text": payload.get("text", ""), "timestamp": now_iso(), "actor": admin.get("email", "admin")}
    await db.customers.update_one({"id": customer_id}, {"$push": {"notes": note}})
    await create_audit_log(
        entity_type="customer",
        entity_id=customer_id,
        action="note_added",
        actor=f"admin:{admin.get('email', admin['id'])}",
        details={"note_preview": payload.get("text", "")[:100]},
    )
    return {"message": "Note added"}
