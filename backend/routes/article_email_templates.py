"""Article Email Templates routes: CRUD for reusable email templates when sending articles."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from core.helpers import make_id, now_iso
from core.tenant import get_tenant_filter, set_tenant_id, tenant_id_of, DEFAULT_TENANT_ID, get_tenant_admin
from core.security import require_admin
from db.session import db
from models import ArticleEmailTemplateCreate, ArticleEmailTemplateUpdate

router = APIRouter(prefix="/api", tags=["article-email-templates"])


@router.get("/article-email-templates")
async def list_article_email_templates(
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    templates = await db.article_email_templates.find(
        {}, {"_id": 0}
    ).sort("created_at", 1).to_list(200)
    return {"templates": templates}


@router.post("/article-email-templates")
async def create_article_email_template(
    payload: ArticleEmailTemplateCreate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Template name is required")
    now = now_iso()
    doc = {
        "id": make_id(),
        "name": payload.name.strip(),
        "subject": payload.subject,
        "html_body": payload.html_body,
        "description": payload.description or "",
        "created_at": now,
        "updated_at": now,
    }
    await db.article_email_templates.insert_one(doc)
    doc.pop("_id", None)
    return {"template": doc}


@router.put("/article-email-templates/{template_id}")
async def update_article_email_template(
    template_id: str,
    payload: ArticleEmailTemplateUpdate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tpl = await db.article_email_templates.find_one({"id": template_id}, {"_id": 0})
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
    await db.article_email_templates.update_one({"id": template_id}, {"$set": updates})
    updated = await db.article_email_templates.find_one({"id": template_id}, {"_id": 0})
    return {"template": updated}


@router.delete("/article-email-templates/{template_id}")
async def delete_article_email_template(
    template_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tpl = await db.article_email_templates.find_one({"id": template_id}, {"_id": 0})
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    await db.article_email_templates.delete_one({"id": template_id})
    return {"message": "Template deleted"}
