"""Admin: Integration request submissions and management."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.helpers import make_id, now_iso
from core.security import get_current_user
from core.tenant import get_tenant_admin, is_platform_admin, get_tenant_filter, tenant_id_of
from db.session import db
from services.audit_service import create_audit_log

router = APIRouter(prefix="/api", tags=["integration-requests"])

STATUS_OPTIONS = ["Pending", "Not Started", "Working", "Future", "Rejected", "Completed"]


# ── Pydantic models ──────────────────────────────────────────────────────────

class IntegrationRequestCreate(BaseModel):
    integration_name: str
    description: Optional[str] = None
    contact_email: str
    contact_phone: Optional[str] = None
    phone_country_code: Optional[str] = "+1"


class IntegrationRequestStatusUpdate(BaseModel):
    status: str


class NoteAdd(BaseModel):
    text: str


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/integration-requests")
async def submit_integration_request(
    payload: IntegrationRequestCreate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """Any partner admin can submit an integration request."""
    if is_platform_admin(admin):
        raise HTTPException(status_code=403, detail="Platform admins cannot submit requests")

    tid = admin.get("tenant_id") or ""
    # Fetch tenant info for partner name / code
    tenant = await db.tenants.find_one({"id": tid}, {"_id": 0, "name": 1, "partner_code": 1}) or {}

    doc = {
        "id": make_id(),
        "tenant_id": tid,
        "partner_code": tenant.get("partner_code") or tid,
        "partner_name": tenant.get("name") or "",
        "submitted_by_user_id": admin.get("id") or admin.get("user_id") or "",
        "submitted_by_name": admin.get("full_name") or admin.get("name") or "",
        "contact_email": payload.contact_email,
        "contact_phone": payload.contact_phone or "",
        "phone_country_code": payload.phone_country_code or "+1",
        "integration_name": payload.integration_name,
        "description": payload.description or "",
        "status": "Pending",
        "notes": [],
        "created_at": now_iso(),
        "updated_at": None,
    }
    await db.integration_requests.insert_one(doc)
    doc.pop("_id", None)
    await create_audit_log(
        entity_type="integration_request", entity_id=doc["id"], action="submitted",
        actor=admin.get("email", "partner_admin"),
        details={"integration_name": payload.integration_name, "partner_code": doc["partner_code"]},
        tenant_id=tid,
    )
    return {"integration_request": doc}


@router.get("/integration-requests")
async def list_integration_requests(
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Platform admin: list all integration requests."""
    if not is_platform_admin(user):
        raise HTTPException(status_code=403, detail="Platform admin access required")
    requests = await db.integration_requests.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return {"integration_requests": requests}


@router.put("/integration-requests/{request_id}/status")
async def update_request_status(
    request_id: str,
    payload: IntegrationRequestStatusUpdate,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Platform admin: update the status of an integration request."""
    if not is_platform_admin(user):
        raise HTTPException(status_code=403, detail="Platform admin access required")
    if payload.status not in STATUS_OPTIONS:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of {STATUS_OPTIONS}")
    result = await db.integration_requests.find_one_and_update(
        {"id": request_id},
        {"$set": {"status": payload.status, "updated_at": now_iso()}},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Request not found")
    result.pop("_id", None)
    await create_audit_log(
        entity_type="integration_request", entity_id=request_id, action="status_updated",
        actor=user.get("email", "platform_admin"),
        details={"new_status": payload.status},
    )
    return {"integration_request": result}


@router.post("/integration-requests/{request_id}/notes")
async def add_note(
    request_id: str,
    payload: NoteAdd,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Platform admin: add a note to an integration request."""
    if not is_platform_admin(user):
        raise HTTPException(status_code=403, detail="Platform admin access required")
    note = {
        "id": make_id(),
        "text": payload.text,
        "created_at": now_iso(),
        "created_by_name": user.get("full_name") or user.get("email") or "Admin",
    }
    result = await db.integration_requests.find_one_and_update(
        {"id": request_id},
        {"$push": {"notes": note}, "$set": {"updated_at": now_iso()}},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Request not found")
    result.pop("_id", None)
    await create_audit_log(
        entity_type="integration_request", entity_id=request_id, action="note_added",
        actor=user.get("email", "platform_admin"),
        details={"note_text": payload.text[:100]},
    )
    return {"integration_request": result}
