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
from db.session import db
from models import BankTransactionCreate, BankTransactionUpdate
from services.audit_service import AuditService

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
    query: Dict[str, Any] = {}
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
    return {"transaction": txn}


@router.put("/admin/bank-transactions/{txn_id}")
async def update_bank_transaction(
    txn_id: str,
    payload: BankTransactionUpdate,
    admin: Dict[str, Any] = Depends(require_admin),
):
    txn = await db.bank_transactions.find_one({"id": txn_id}, {"_id": 0})
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
    return {"transaction": updated}


@router.delete("/admin/bank-transactions/{txn_id}")
async def delete_bank_transaction(
    txn_id: str,
    admin: Dict[str, Any] = Depends(require_admin),
):
    result = await db.bank_transactions.delete_one({"id": txn_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {"message": "Deleted"}


@router.get("/admin/bank-transactions/{txn_id}/logs")
async def get_bank_transaction_logs(
    txn_id: str,
    admin: Dict[str, Any] = Depends(require_admin),
):
    txn = await db.bank_transactions.find_one({"id": txn_id}, {"_id": 0})
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {"logs": txn.get("logs", [])}


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
