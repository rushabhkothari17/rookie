"""Admin: Email templates management routes."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from core.helpers import now_iso
from core.security import require_admin
from core.tenant import get_tenant_filter, set_tenant_id, tenant_id_of, get_tenant_admin
from db.session import db
from services.audit_service import create_audit_log
from services.email_service import EmailService

router = APIRouter(prefix="/api", tags=["email-templates"])


@router.get("/admin/email-templates")
async def list_templates(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    tid = tenant_id_of(admin)
    await EmailService.ensure_seeded(db, tid)
    templates = await db.email_templates.find(tf, {"_id": 0}).sort("trigger", 1).to_list(100)
    return {"templates": templates}


@router.put("/admin/email-templates/{template_id}")
async def update_template(template_id: str, payload: Dict[str, Any], admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    tmpl = await db.email_templates.find_one({**tf, "id": template_id}, {"_id": 0})
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")

    update: Dict[str, Any] = {"updated_at": now_iso()}
    for field in ["subject", "html_body", "is_enabled"]:
        if field in payload:
            update[field] = payload[field]

    await db.email_templates.update_one({"id": template_id}, {"$set": update})
    updated = await db.email_templates.find_one({"id": template_id}, {"_id": 0})
    await create_audit_log(entity_type="email_template", entity_id=template_id, action="updated", actor=admin.get("email", "admin"), details={"trigger": tmpl.get("trigger"), "fields": list(update.keys())})
    return {"template": updated}


@router.get("/admin/email-logs")
async def list_email_logs(limit: int = 50, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    logs = await db.email_logs.find(tf, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return {"logs": logs}
