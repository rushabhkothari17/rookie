"""Admin: Bank transactions routes."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from core.helpers import make_id, now_iso
from core.security import require_admin
from core.tenant import get_tenant_filter, set_tenant_id, tenant_id_of
from db.session import db
from models import BankTransactionCreate, BankTransactionUpdate
from services.audit_service import AuditService, create_audit_log

router = APIRouter(prefix="/api", tags=["admin-bank-transactions"])


@router.get("/admin/bank-transactions")
async def list_bank_transactions(
    page: int = 1,
    per_page: int = 20,
    source: Optional[str] = None,
    status: Optional[str] = None,
    type: Optional[str] = None,
    linked_order_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    admin: Dict[str, Any] = Depends(require_admin),
):
    tf = get_tenant_filter(admin)
    query: Dict[str, Any] = {**tf}
    if source:
        query["source"] = source
    if status:
        query["status"] = status
    if type:
        query["type"] = type
    if linked_order_id:
        query["linked_order_id"] = linked_order_id
    if date_from:
        query.setdefault("date", {})["$gte"] = date_from
    if date_to:
        query.setdefault("date", {})["$lte"] = date_to + "T23:59:59"

    total = await db.bank_transactions.count_documents(query)
    skip = (page - 1) * per_page
    txns = await db.bank_transactions.find(query, {"_id": 0}).sort("date", -1).skip(skip).limit(per_page).to_list(per_page)
    return {
        "transactions": txns,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": max(1, (total + per_page - 1) // per_page),
    }


@router.post("/admin/bank-transactions")
async def create_bank_transaction(
    payload: BankTransactionCreate,
    admin: Dict[str, Any] = Depends(require_admin),
):
    txn_id = make_id()
    net = payload.net_amount if payload.net_amount is not None else round(payload.amount - (payload.fees or 0.0), 2)
    txn = {
        "id": txn_id,
        "tenant_id": tenant_id_of(admin),
        "date": payload.date,
        "source": payload.source,
        "transaction_id": payload.transaction_id,
        "type": payload.type,
        "amount": payload.amount,
        "fees": payload.fees or 0.0,
        "net_amount": net,
        "currency": payload.currency or "USD",
        "status": payload.status,
        "description": payload.description,
        "linked_order_id": payload.linked_order_id,
        "internal_notes": payload.internal_notes,
        "logs": [{"timestamp": now_iso(), "action": "created", "actor": admin["email"], "details": {}}],
        "created_at": now_iso(),
        "created_by": admin["email"],
    }
    await db.bank_transactions.insert_one(txn)
    txn.pop("_id", None)
    await AuditService.log(
        action="BANK_TXN_CREATED",
        description=f"Bank transaction created: {payload.transaction_id} ({payload.type}) {payload.amount} {payload.currency}",
        entity_type="BankTransaction",
        entity_id=txn_id,
        actor_type="admin",
        actor_email=admin.get("email"),
        source="admin_ui",
        after_json={"amount": payload.amount, "type": payload.type, "source": payload.source, "status": payload.status},
    )
    await db.audit_logs.insert_one({"id": make_id(), "entity_type": "bank_transaction", "entity_id": txn_id, "action": "created", "actor": admin.get("email", "admin"), "details": {"amount": payload.amount, "type": payload.type, "currency": payload.currency}, "created_at": now_iso()})
    return {"transaction": txn}


@router.put("/admin/bank-transactions/{txn_id}")
async def update_bank_transaction(
    txn_id: str,
    payload: BankTransactionUpdate,
    admin: Dict[str, Any] = Depends(require_admin),
):
    tf = get_tenant_filter(admin)
    txn = await db.bank_transactions.find_one({**tf, "id": txn_id}, {"_id": 0})
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    updates = {k: v for k, v in payload.dict(exclude_unset=True).items() if v is not None}
    if "amount" in updates or "fees" in updates:
        amt = updates.get("amount", txn.get("amount", 0))
        fees = updates.get("fees", txn.get("fees", 0))
        updates["net_amount"] = round(amt - fees, 2)

    if updates:
        log_entry = {"timestamp": now_iso(), "action": "updated", "actor": admin["email"], "details": updates}
        await db.bank_transactions.update_one(
            {"id": txn_id},
            {"$set": {**updates, "updated_at": now_iso()}, "$push": {"logs": log_entry}},
        )

    updated = await db.bank_transactions.find_one({"id": txn_id}, {"_id": 0})
    await AuditService.log(
        action="BANK_TXN_UPDATED",
        description=f"Bank transaction {txn_id} updated",
        entity_type="BankTransaction",
        entity_id=txn_id,
        actor_type="admin",
        actor_email=admin.get("email"),
        source="admin_ui",
        after_json=updates,
    )
    await db.audit_logs.insert_one({"id": make_id(), "entity_type": "bank_transaction", "entity_id": txn_id, "action": "updated", "actor": admin.get("email", "admin"), "details": updates, "created_at": now_iso()})
    return {"transaction": updated}


@router.delete("/admin/bank-transactions/{txn_id}")
async def delete_bank_transaction(
    txn_id: str,
    admin: Dict[str, Any] = Depends(require_admin),
):
    result = await db.bank_transactions.delete_one({"id": txn_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Transaction not found")
    await AuditService.log(
        action="BANK_TXN_DELETED",
        description=f"Bank transaction {txn_id} deleted",
        entity_type="BankTransaction",
        entity_id=txn_id,
        actor_type="admin",
        actor_email=admin.get("email"),
        source="admin_ui",
    )
    await db.audit_logs.insert_one({"id": make_id(), "entity_type": "bank_transaction", "entity_id": txn_id, "action": "deleted", "actor": admin.get("email", "admin"), "details": {}, "created_at": now_iso()})
    return {"message": "Deleted"}


@router.get("/admin/bank-transactions/{txn_id}/logs")
async def get_bank_transaction_logs(
    txn_id: str,
    admin: Dict[str, Any] = Depends(require_admin),
):
    txn = await db.bank_transactions.find_one({"id": txn_id}, {"_id": 0})
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    inline_logs = txn.get("logs", [])
    audit_logs = await db.audit_logs.find({"entity_type": "bank_transaction", "entity_id": txn_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
    merged = sorted(inline_logs + audit_logs, key=lambda x: x.get("created_at", ""), reverse=True)
    return {"logs": merged}


@router.get("/admin/export/bank-transactions")
async def export_bank_transactions(
    admin: Dict[str, Any] = Depends(require_admin),
):
    txns = await db.bank_transactions.find({}, {"_id": 0}).sort("date", -1).to_list(5000)
    output = io.StringIO()
    fieldnames = [
        "id", "date", "source", "transaction_id", "type", "amount", "fees",
        "net_amount", "currency", "status", "description", "linked_order_id",
        "internal_notes", "created_at", "created_by",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(txns)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=bank_transactions_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.csv"},
    )
