"""
Intake Forms — admin and portal routes.
Collections: intake_forms, intake_form_records
"""
from __future__ import annotations
import asyncio
import re
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core.helpers import make_id, now_iso
from core.tenant import (
    get_tenant_admin, get_tenant_filter, is_platform_admin,
    tenant_id_of, enrich_partner_codes,
)
from core.security import get_current_user
from db.session import db
from services.audit_service import create_audit_log

router = APIRouter(prefix="/api", tags=["admin-intake-forms"])


# ── Pydantic models ────────────────────────────────────────────────────────────

class IntakeFormCreate(BaseModel):
    name: str
    description: Optional[str] = None
    form_schema: str = "[]"
    is_enabled: bool = True
    auto_approve: bool = False
    allow_skip_signature: bool = False
    customer_ids: Optional[List[str]] = None         # direct targeting
    visibility_conditions: Optional[Dict] = None     # profile-based grouped conditions

    class Config:
        populate_by_name = True


class IntakeFormUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    form_schema: Optional[str] = None
    is_enabled: Optional[bool] = None
    auto_approve: Optional[bool] = None
    allow_skip_signature: Optional[bool] = None
    customer_ids: Optional[List[str]] = None
    visibility_conditions: Optional[Dict] = None


class RecordNote(BaseModel):
    text: str


class RecordNoteUpdate(BaseModel):
    text: str


class RecordStatusUpdate(BaseModel):
    status: str
    rejection_reason: Optional[str] = None


class AdminRecordCreate(BaseModel):
    intake_form_id: str
    customer_id: str
    skip_signature: bool = False


class AdminRecordUpdate(BaseModel):
    responses: Optional[Dict[str, Any]] = None
    signature_data_url: Optional[str] = None
    signature_name: Optional[str] = None
    skip_signature: Optional[bool] = None


class PortalSubmitRecord(BaseModel):
    responses: Dict[str, Any]
    signature_data_url: Optional[str] = None
    signature_name: Optional[str] = None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _eval_cond(cval: str, op: str, target: str) -> bool:
    cv, tv = cval.lower(), target.lower()
    if op == "equals":       return cv == tv
    if op == "not_equals":   return cv != tv
    if op == "contains":     return tv in cv
    if op == "not_contains": return tv not in cv
    if op == "not_empty":    return bool(cv)
    if op == "empty":        return not cv
    if op == "in":           return cv in [v.strip().lower() for v in tv.split(",")]
    return True


def _eval_vis_conditions(customer: Dict, vc: Optional[Dict]) -> bool:
    """Evaluate grouped visibility conditions (ProductVisRuleSet) against a customer."""
    if not vc or not vc.get("groups"):
        return True
    def eval_group(g: Dict) -> bool:
        logic = g.get("logic", "AND")
        results = [
            _eval_cond(str(customer.get(c.get("field", ""), "") or ""), c.get("operator", "equals"), str(c.get("value", "")))
            for c in g.get("conditions", [])
        ]
        return all(results) if logic == "AND" else any(results)
    top = vc.get("top_logic", "AND")
    group_results = [eval_group(g) for g in vc["groups"]]
    return all(group_results) if top == "AND" else any(group_results)


def _customer_matches_rules(customer: Dict, customer_ids: List[str], visibility_conditions: Optional[Dict] = None) -> bool:
    """Return True if customer should complete this intake form."""
    # Mode 1: specific customer IDs
    if customer_ids:
        return customer.get("id") in customer_ids
    # Mode 2: profile-based conditions
    if visibility_conditions:
        return _eval_vis_conditions(customer, visibility_conditions)
    # Mode 3: all customers
    return True


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN — Intake Form Definitions
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/admin/intake-forms")
async def list_intake_forms(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    forms = await db.intake_forms.find(tf, {"_id": 0}).to_list(500)
    if is_platform_admin(admin):
        forms = await enrich_partner_codes(forms, True)
    return {"forms": forms}


@router.post("/admin/intake-forms")
async def create_intake_form(
    payload: IntakeFormCreate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tid = tenant_id_of(admin)
    now = now_iso()
    doc = {
        "id": make_id(),
        "tenant_id": tid,
        "name": payload.name,
        "description": payload.description or "",
        "schema": payload.form_schema,
        "is_enabled": payload.is_enabled,
        "auto_approve": payload.auto_approve,
        "allow_skip_signature": payload.allow_skip_signature,
        "customer_ids": payload.customer_ids or [],
        "visibility_conditions": payload.visibility_conditions or None,
        "created_by": admin.get("email", "admin"),
        "created_at": now,
        "updated_at": now,
    }
    await db.intake_forms.insert_one(doc)
    await create_audit_log(
        entity_type="intake_form", entity_id=doc["id"],
        action="created", actor=admin.get("email", "admin"),
        details={"name": payload.name},
    )
    del doc["_id"]
    return {"form": doc}


@router.get("/admin/intake-forms/{form_id}")
async def get_intake_form(form_id: str, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    form = await db.intake_forms.find_one({**tf, "id": form_id}, {"_id": 0})
    if not form:
        raise HTTPException(404, "Intake form not found")
    return {"form": form}


@router.put("/admin/intake-forms/{form_id}")
async def update_intake_form(
    form_id: str,
    payload: IntakeFormUpdate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    form = await db.intake_forms.find_one({**tf, "id": form_id})
    if not form:
        raise HTTPException(404, "Intake form not found")
    updates: Dict[str, Any] = {"updated_at": now_iso()}
    for field in ["name", "description", "is_enabled", "auto_approve", "allow_skip_signature", "customer_ids"]:
        val = getattr(payload, field)
        if val is not None:
            updates[field] = val
    if payload.form_schema is not None:
        updates["schema"] = payload.form_schema
    if payload.visibility_conditions is not None:
        updates["visibility_conditions"] = payload.visibility_conditions
    elif hasattr(payload, "visibility_conditions") and payload.visibility_conditions is None:
        # Explicitly cleared
        updates["visibility_conditions"] = None
    await db.intake_forms.update_one({"id": form_id}, {"$set": updates})
    await create_audit_log(
        entity_type="intake_form", entity_id=form_id,
        action="updated", actor=admin.get("email", "admin"),
        details=updates,
    )
    return {"message": "Updated"}


@router.delete("/admin/intake-forms/{form_id}")
async def delete_intake_form(form_id: str, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    res = await db.intake_forms.delete_one({**tf, "id": form_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Intake form not found")
    await create_audit_log(entity_type="intake_form", entity_id=form_id, action="deleted",
                           actor=admin.get("email", "admin"), details={})
    return {"message": "Deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN — Intake Form Records
# ══════════════════════════════════════════════════════════════════════════════

_SORTABLE_COLS = {"customer_name", "intake_form_name", "status", "submitted_at", "version", "created_at"}

@router.get("/admin/intake-form-records")
async def list_intake_form_records(
    admin: Dict[str, Any] = Depends(get_tenant_admin),
    page: int = 1,
    limit: int = 25,
    status: Optional[str] = Query(None),
    form_id: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_dir: Optional[str] = Query("desc"),
):
    tf = get_tenant_filter(admin)
    query: Dict[str, Any] = {**tf}
    if status:
        query["status"] = status
    if form_id:
        query["intake_form_id"] = form_id
    if customer_id:
        query["customer_id"] = customer_id
    if search:
        safe_search = re.escape(search)
        query["$or"] = [
            {"customer_name": {"$regex": safe_search, "$options": "i"}},
            {"customer_email": {"$regex": safe_search, "$options": "i"}},
            {"intake_form_name": {"$regex": safe_search, "$options": "i"}},
        ]
    if date_from or date_to:
        df: Dict[str, Any] = {}
        if date_from:
            df["$gte"] = date_from
        if date_to:
            df["$lte"] = date_to + "T23:59:59Z"
        query["submitted_at"] = df

    sort_field = sort_by if sort_by in _SORTABLE_COLS else "created_at"
    sort_order = 1 if sort_dir == "asc" else -1

    total = await db.intake_form_records.count_documents(query)
    records = await db.intake_form_records.find(
        query, {"_id": 0, "versions": 0}
    ).sort(sort_field, sort_order).skip((page - 1) * limit).limit(limit).to_list(limit)

    if is_platform_admin(admin):
        records = await enrich_partner_codes(records, True)

    return {"records": records, "total": total, "page": page, "limit": limit}


@router.post("/admin/intake-form-records")
async def admin_create_record(
    payload: AdminRecordCreate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tid = tenant_id_of(admin)
    tf = get_tenant_filter(admin)

    form = await db.intake_forms.find_one({**tf, "id": payload.intake_form_id}, {"_id": 0})
    if not form:
        raise HTTPException(404, "Intake form not found")

    customer = await db.users.find_one(
        {"tenant_id": tid, "id": payload.customer_id, "role": "customer"}, {"_id": 0}
    )
    if not customer:
        raise HTTPException(404, "Customer not found")

    # Check if record already exists
    existing = await db.intake_form_records.find_one({
        "tenant_id": tid,
        "intake_form_id": payload.intake_form_id,
        "customer_id": payload.customer_id,
    })
    if existing:
        raise HTTPException(400, "A record already exists for this customer and form. Use edit instead.")

    now = now_iso()
    skip_sig = payload.skip_signature and form.get("allow_skip_signature", False)
    doc = {
        "id": make_id(),
        "tenant_id": tid,
        "intake_form_id": payload.intake_form_id,
        "intake_form_name": form["name"],
        "customer_id": payload.customer_id,
        "customer_name": customer.get("full_name") or customer.get("name", ""),
        "customer_email": customer.get("email", ""),
        "responses": {},
        "signature_data_url": None,
        "signature_name": None,
        "status": "pending",
        "version": 0,
        "admin_created": True,
        "signature_skipped": skip_sig,
        "submitted_at": None,
        "reviewed_at": None,
        "reviewed_by": None,
        "rejection_reason": None,
        "versions": [],
        "notes": [],
        "created_by": admin.get("email", "admin"),
        "created_at": now,
        "updated_at": now,
    }
    await db.intake_form_records.insert_one(doc)
    del doc["_id"]
    await create_audit_log(entity_type="intake_form_record", entity_id=doc["id"],
                           action="admin_created", actor=admin.get("email", "admin"),
                           details={"customer_id": payload.customer_id, "form_id": payload.intake_form_id})
    return {"record": doc}


@router.get("/admin/intake-form-records/{record_id}")
async def get_intake_form_record(record_id: str, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    record = await db.intake_form_records.find_one({**tf, "id": record_id}, {"_id": 0})
    if not record:
        raise HTTPException(404, "Record not found")
    return {"record": record}


@router.put("/admin/intake-form-records/{record_id}")
async def admin_update_record(
    record_id: str,
    payload: AdminRecordUpdate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    record = await db.intake_form_records.find_one({**tf, "id": record_id})
    if not record:
        raise HTTPException(404, "Record not found")

    now = now_iso()
    # Archive current version before updating
    current_version = {
        "version": record.get("version", 1),
        "responses": record.get("responses", {}),
        "signature_data_url": record.get("signature_data_url"),
        "signature_name": record.get("signature_name"),
        "status": record.get("status"),
        "submitted_at": record.get("submitted_at"),
        "edited_by": admin.get("email", "admin"),
        "archived_at": now,
    }

    updates: Dict[str, Any] = {
        "updated_at": now,
        "version": record.get("version", 1) + 1,
        "status": "submitted",
    }
    if payload.responses is not None:
        updates["responses"] = payload.responses
    if payload.signature_data_url is not None:
        updates["signature_data_url"] = payload.signature_data_url
    if payload.signature_name is not None:
        updates["signature_name"] = payload.signature_name
    if payload.skip_signature is not None:
        form = await db.intake_forms.find_one({"id": record["intake_form_id"]}, {"_id": 0})
        if form and form.get("allow_skip_signature"):
            updates["signature_skipped"] = payload.skip_signature
    if updates.get("signature_data_url") or updates.get("signature_skipped"):
        updates["submitted_at"] = now

    # Check auto-approve
    form = await db.intake_forms.find_one({"id": record["intake_form_id"]}, {"_id": 0})
    if form and form.get("auto_approve"):
        updates["status"] = "approved"
        updates["reviewed_at"] = now
        updates["reviewed_by"] = "system (auto-approved)"

    await db.intake_form_records.update_one(
        {"id": record_id},
        {"$set": updates, "$push": {"versions": current_version}},
    )
    await create_audit_log(entity_type="intake_form_record", entity_id=record_id,
                           action="admin_updated", actor=admin.get("email", "admin"),
                           details={"version": updates.get("version")})
    return {"message": "Updated"}


@router.get("/admin/intake-form-records/{record_id}/versions")
async def get_record_versions(record_id: str, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    record = await db.intake_form_records.find_one({**tf, "id": record_id}, {"_id": 0, "versions": 1})
    if not record:
        raise HTTPException(404, "Record not found")
    return {"versions": record.get("versions", [])}


@router.put("/admin/intake-form-records/{record_id}/status")
async def update_record_status(
    record_id: str,
    payload: RecordStatusUpdate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    valid = {"submitted", "under_review", "approved", "rejected"}
    if payload.status not in valid:
        raise HTTPException(400, f"Invalid status. Must be one of: {', '.join(valid)}")
    if payload.status == "rejected" and not (payload.rejection_reason or "").strip():
        raise HTTPException(400, "A rejection reason is required when rejecting a submission.")
    tf = get_tenant_filter(admin)
    record = await db.intake_form_records.find_one({**tf, "id": record_id})
    if not record:
        raise HTTPException(404, "Record not found")
    now = now_iso()
    updates: Dict[str, Any] = {
        "status": payload.status,
        "reviewed_at": now,
        "reviewed_by": admin.get("email", "admin"),
        "updated_at": now,
    }
    if payload.status == "rejected" and payload.rejection_reason:
        updates["rejection_reason"] = payload.rejection_reason
    if payload.status == "approved":
        updates["rejection_reason"] = None
    await db.intake_form_records.update_one({"id": record_id}, {"$set": updates})
    await create_audit_log(
        entity_type="intake_form_record", entity_id=record_id,
        action=f"status_changed_to_{payload.status}", actor=admin.get("email", "admin"),
        details={"reason": payload.rejection_reason or ""},
    )

    # ── Send email notification for approved/rejected status changes ───────────
    if payload.status in {"approved", "rejected"}:
        try:
            from services.email_service import EmailService
            customer_email = record.get("customer_email", "")
            if customer_email:
                frontend_url = os.environ.get("FRONTEND_URL", os.environ.get("REACT_APP_BACKEND_URL", "")).replace("/api", "")
                intake_url = f"{frontend_url}/intake-form" if frontend_url else "/intake-form"
                rejection_block = ""
                if payload.status == "rejected" and payload.rejection_reason:
                    rejection_block = (
                        f'<div style="background:#fef2f2;border-left:4px solid #ef4444;border-radius:0 6px 6px 0;padding:12px 16px;margin:16px 0">'
                        f'<p style="color:#991b1b;font-size:13px;font-weight:600;margin:0 0 4px">Reason for rejection</p>'
                        f'<p style="color:#b91c1c;font-size:13px;margin:0">{payload.rejection_reason}</p>'
                        f'</div>'
                    )
                asyncio.create_task(EmailService.send(
                    trigger="intake_form_status_changed",
                    recipient=customer_email,
                    variables={
                        "customer_name": record.get("customer_name", ""),
                        "customer_email": customer_email,
                        "intake_form_name": record.get("intake_form_name", ""),
                        "intake_form_status": payload.status,
                        "intake_form_url": intake_url,
                        "rejection_reason_block": rejection_block,
                    },
                    db=db,
                    tenant_id=record.get("tenant_id"),
                ))
        except Exception:
            pass  # Email failure should not block the status update response

    return {"message": "Status updated"}


# ── Notes ──────────────────────────────────────────────────────────────────────

@router.post("/admin/intake-form-records/{record_id}/notes")
async def add_record_note(
    record_id: str,
    payload: RecordNote,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    record = await db.intake_form_records.find_one({**tf, "id": record_id})
    if not record:
        raise HTTPException(404, "Record not found")
    note = {
        "id": make_id(),
        "text": payload.text,
        "author": admin.get("email", "admin"),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.intake_form_records.update_one({"id": record_id}, {"$push": {"notes": note}})
    await create_audit_log(entity_type="intake_form_record", entity_id=record_id,
                           action="note_added", actor=admin.get("email", "admin"),
                           details={"note_id": note["id"]})
    return {"note": note}


@router.put("/admin/intake-form-records/{record_id}/notes/{note_id}")
async def update_record_note(
    record_id: str,
    note_id: str,
    payload: RecordNoteUpdate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    record = await db.intake_form_records.find_one({**tf, "id": record_id})
    if not record:
        raise HTTPException(404, "Record not found")
    await db.intake_form_records.update_one(
        {"id": record_id, "notes.id": note_id},
        {"$set": {"notes.$.text": payload.text, "notes.$.updated_at": now_iso()}},
    )
    await create_audit_log(entity_type="intake_form_record", entity_id=record_id,
                           action="note_updated", actor=admin.get("email", "admin"),
                           details={"note_id": note_id})
    return {"message": "Note updated"}


@router.delete("/admin/intake-form-records/{record_id}/notes/{note_id}")
async def delete_record_note(
    record_id: str,
    note_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    record = await db.intake_form_records.find_one({**tf, "id": record_id})
    if not record:
        raise HTTPException(404, "Record not found")
    await db.intake_form_records.update_one(
        {"id": record_id},
        {"$pull": {"notes": {"id": note_id}}},
    )
    await create_audit_log(entity_type="intake_form_record", entity_id=record_id,
                           action="note_deleted", actor=admin.get("email", "admin"),
                           details={"note_id": note_id})
    return {"message": "Note deleted"}


@router.get("/admin/intake-forms/{form_id}/logs")
async def get_intake_form_def_logs(form_id: str, page: int = 1, limit: int = 20,
                                    admin: Dict[str, Any] = Depends(get_tenant_admin)):
    flt = {"entity_type": "intake_form", "entity_id": form_id}
    total = await db.audit_logs.count_documents(flt)
    logs = await db.audit_logs.find(flt, {"_id": 0}).sort("timestamp", -1).skip((page - 1) * limit).limit(limit).to_list(limit)
    return {"logs": logs, "total": total}


# ── Logs ───────────────────────────────────────────────────────────────────────

@router.get("/admin/intake-form-records/{record_id}/logs")
async def get_record_logs(
    record_id: str,
    page: int = 1,
    limit: int = 20,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    record = await db.intake_form_records.find_one({**tf, "id": record_id}, {"_id": 0, "id": 1})
    if not record:
        raise HTTPException(404, "Record not found")
    query = {"entity_type": "intake_form_record", "entity_id": record_id}
    total = await db.audit_logs.count_documents(query)
    logs = await db.audit_logs.find(query, {"_id": 0}).sort("timestamp", -1).skip((page - 1) * limit).limit(limit).to_list(limit)
    return {"logs": logs, "total": total}


# ══════════════════════════════════════════════════════════════════════════════
# PORTAL — Customer-facing endpoints
# ══════════════════════════════════════════════════════════════════════════════

async def _get_customer_user(user: Dict[str, Any]) -> Dict[str, Any]:
    if user.get("role") != "customer":
        raise HTTPException(403, "Customer access only")
    return user


@router.get("/portal/intake-forms")
async def portal_get_intake_forms(user: Dict[str, Any] = Depends(get_current_user)):
    await _get_customer_user(user)
    tid = user["tenant_id"]
    customer_id = user["id"]

    # Get all enabled intake forms for this tenant
    forms = await db.intake_forms.find(
        {"tenant_id": tid, "is_enabled": True}, {"_id": 0}
    ).to_list(200)

    # Get customer profile for visibility rule evaluation
    customer = await db.users.find_one({"id": customer_id}, {"_id": 0}) or {}

    result = []
    for form in forms:
        rules = form.get("visibility_rules", [])
        c_ids = form.get("customer_ids", [])
        if not _customer_matches_rules(customer, c_ids, form.get("visibility_conditions")):
            continue

        # Get or create record
        record = await db.intake_form_records.find_one(
            {"tenant_id": tid, "intake_form_id": form["id"], "customer_id": customer_id},
            {"_id": 0, "versions": 0},
        )
        result.append({
            "form": form,
            "record": record,
        })

    return {"intake_forms": result}


@router.get("/portal/intake-forms/pending-check")
async def portal_check_pending(user: Dict[str, Any] = Depends(get_current_user)):
    """Returns list of forms that block checkout (pending or rejected)."""
    await _get_customer_user(user)
    tid = user["tenant_id"]
    customer_id = user["id"]

    forms = await db.intake_forms.find(
        {"tenant_id": tid, "is_enabled": True}, {"_id": 0}
    ).to_list(200)

    customer = await db.users.find_one({"id": customer_id}, {"_id": 0}) or {}
    blocking = []

    for form in forms:
        rules = form.get("visibility_rules", [])
        c_ids = form.get("customer_ids", [])
        if not _customer_matches_rules(customer, c_ids, form.get("visibility_conditions")):
            continue

        record = await db.intake_form_records.find_one(
            {"tenant_id": tid, "intake_form_id": form["id"], "customer_id": customer_id},
            {"_id": 0, "status": 1, "rejection_reason": 1},
        )
        status = record.get("status") if record else "pending"

        # Block if: no record, pending, rejected, submitted (waiting approval), under_review
        # Allow only: approved
        if status != "approved":
            blocking.append({
                "form_id": form["id"],
                "form_name": form["name"],
                "status": status or "pending",
                "rejection_reason": record.get("rejection_reason") if record else None,
            })

    return {"blocking": blocking, "all_clear": len(blocking) == 0}


@router.post("/portal/intake-forms/{form_id}/submit")
async def portal_submit_form(
    form_id: str,
    payload: PortalSubmitRecord,
    user: Dict[str, Any] = Depends(get_current_user),
):
    await _get_customer_user(user)
    tid = user["tenant_id"]
    customer_id = user["id"]

    form = await db.intake_forms.find_one({"tenant_id": tid, "id": form_id, "is_enabled": True}, {"_id": 0})
    if not form:
        raise HTTPException(404, "Intake form not found")

    now = now_iso()
    status = "approved" if form.get("auto_approve") else "submitted"

    existing = await db.intake_form_records.find_one({
        "tenant_id": tid, "intake_form_id": form_id, "customer_id": customer_id,
    })

    if existing:
        # Archive current version and bump version
        current_version = {
            "version": existing.get("version", 1),
            "responses": existing.get("responses", {}),
            "signature_data_url": existing.get("signature_data_url"),
            "signature_name": existing.get("signature_name"),
            "status": existing.get("status"),
            "submitted_at": existing.get("submitted_at"),
            "archived_at": now,
        }
        await db.intake_form_records.update_one(
            {"id": existing["id"]},
            {
                "$set": {
                    "responses": payload.responses,
                    "signature_data_url": payload.signature_data_url,
                    "signature_name": payload.signature_name,
                    "status": status,
                    "version": existing.get("version", 1) + 1,
                    "submitted_at": now,
                    "rejection_reason": None,
                    "updated_at": now,
                    **({"reviewed_at": now, "reviewed_by": "system (auto-approved)"} if form.get("auto_approve") else {}),
                },
                "$push": {"versions": current_version},
            },
        )
        await create_audit_log(entity_type="intake_form_record", entity_id=existing["id"],
                               action="customer_resubmitted", actor=customer_id,
                               details={"version": existing.get("version", 1) + 1, "status": status},
                               tenant_id=tid)
        return {"message": "Form updated", "status": status}
    else:
        doc = {
            "id": make_id(),
            "tenant_id": tid,
            "intake_form_id": form_id,
            "intake_form_name": form["name"],
            "customer_id": customer_id,
            "customer_name": user.get("full_name") or user.get("name", ""),
            "customer_email": user.get("email", ""),
            "responses": payload.responses,
            "signature_data_url": payload.signature_data_url,
            "signature_name": payload.signature_name,
            "status": status,
            "version": 1,
            "admin_created": False,
            "signature_skipped": False,
            "submitted_at": now,
            "reviewed_at": now if form.get("auto_approve") else None,
            "reviewed_by": "system (auto-approved)" if form.get("auto_approve") else None,
            "rejection_reason": None,
            "versions": [],
            "notes": [],
            "created_by": customer_id,
            "created_at": now,
            "updated_at": now,
        }
        await db.intake_form_records.insert_one(doc)
        del doc["_id"]
        await create_audit_log(entity_type="intake_form_record", entity_id=doc["id"],
                               action="customer_submitted", actor=customer_id,
                               details={"form_id": form_id, "status": status},
                               tenant_id=tid)
        return {"message": "Form submitted", "status": status, "record": doc}
