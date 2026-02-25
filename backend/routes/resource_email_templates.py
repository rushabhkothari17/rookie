"""Resource Email Templates routes: CRUD for reusable email templates when sending articles."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from core.helpers import make_id, now_iso
from core.tenant import get_tenant_filter, set_tenant_id, tenant_id_of, DEFAULT_TENANT_ID, get_tenant_admin
from core.security import require_admin
from db.session import db
from models import ResourceEmailTemplateCreate, ResourceEmailTemplateUpdate
from services.audit_service import create_audit_log

router = APIRouter(prefix="/api", tags=["resource-email-templates"])


@router.get("/resource-email-templates")
async def list_article_email_templates(
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    templates = await db.resource_email_templates.find(
        tf, {"_id": 0}
    ).sort("created_at", 1).to_list(200)
    return {"templates": templates}


@router.post("/resource-email-templates")
async def create_article_email_template(
    payload: ResourceEmailTemplateCreate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Template name is required")
    tid = tenant_id_of(admin)
    now = now_iso()
    doc = {
        "id": make_id(),
        "tenant_id": tid,
        "name": payload.name.strip(),
        "subject": payload.subject,
        "html_body": payload.html_body,
        "description": payload.description or "",
        "created_at": now,
        "updated_at": now,
    }
    await db.resource_email_templates.insert_one(doc)
    doc.pop("_id", None)
    await create_audit_log(entity_type="resource_email_template", entity_id=doc["id"], action="created", actor=admin.get("email", "admin"), details={"name": doc["name"]})
    return {"template": doc}


@router.put("/resource-email-templates/{template_id}")
async def update_article_email_template(
    template_id: str,
    payload: ResourceEmailTemplateUpdate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    tpl = await db.resource_email_templates.find_one({**tf, "id": template_id}, {"_id": 0})
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    updates: Dict[str, Any] = {"updated_at": now_iso()}
    if payload.name is not None:
        updates["name"] = payload.name.strip()
    if payload.subject is not None:
        updates["subject"] = payload.subject
    if payload.html_body is not None:
        updates["html_body"] = payload.html_body
    if payload.description is not None:
        updates["description"] = payload.description
    await db.resource_email_templates.update_one({"id": template_id}, {"$set": updates})
    updated = await db.resource_email_templates.find_one({"id": template_id}, {"_id": 0})
    await create_audit_log(entity_type="resource_email_template", entity_id=template_id, action="updated", actor=admin.get("email", "admin"), details={"fields": list(updates.keys())})
    return {"template": updated}


@router.delete("/resource-email-templates/{template_id}")
async def delete_article_email_template(
    template_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    tpl = await db.resource_email_templates.find_one({**tf, "id": template_id}, {"_id": 0})
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    await db.resource_email_templates.delete_one({"id": template_id})
    await create_audit_log(entity_type="resource_email_template", entity_id=template_id, action="deleted", actor=admin.get("email", "admin"), details={"name": tpl.get("name")})
    return {"message": "Template deleted"}


@router.get("/resource-email-templates/{template_id}/logs")
async def get_article_email_template_logs(
    template_id: str,
    page: int = 1,
    limit: int = 20,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    tpl = await db.resource_email_templates.find_one({**tf, "id": template_id}, {"_id": 0, "id": 1})
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    flt = {"entity_type": "article_email_template", "entity_id": template_id}
    total = await db.audit_logs.count_documents(flt)
    skip = (page - 1) * limit
    logs = await db.audit_logs.find(flt, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"logs": logs, "total": total, "page": page, "limit": limit, "pages": max(1, (total + limit - 1) // limit)}
