"""Article Categories routes: CRUD for article category management."""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.helpers import make_id, now_iso
from core.security import require_admin, get_current_user
from core.tenant import get_tenant_filter, set_tenant_id, tenant_id_of, DEFAULT_TENANT_ID, get_tenant_admin
from db.session import db
from models import ArticleCategoryCreate, ArticleCategoryUpdate
from services.audit_service import create_audit_log

router = APIRouter(prefix="/api", tags=["article-categories"])


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


@router.get("/article-categories")
async def list_article_categories(
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    cats = await db.article_categories.find(tf, {"_id": 0}).sort("name", 1).to_list(200)
    return {"categories": cats}


@router.get("/article-categories/public")
async def list_article_categories_public(partner_code: Optional[str] = None):
    """Public endpoint for customer-facing category lists."""
    from core.tenant import resolve_tenant, get_tenant_admin
    if partner_code:
        try:
            tenant = await resolve_tenant(partner_code)
            tid = tenant["id"]
        except Exception:
            tid = DEFAULT_TENANT_ID
    else:
        tid = DEFAULT_TENANT_ID
    cats = await db.article_categories.find({"tenant_id": tid}, {"_id": 0}).sort("name", 1).to_list(200)
    return {"categories": cats}


@router.post("/article-categories")
async def create_article_category(
    payload: ArticleCategoryCreate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    tid = tenant_id_of(admin)
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Category name is required")
    existing = await db.article_categories.find_one({**tf, "name": payload.name.strip()}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Category with this name already exists")
    now = now_iso()
    doc = {
        "id": make_id(),
        "tenant_id": tid,
        "name": payload.name.strip(),
        "slug": _slugify(payload.name.strip()),
        "description": payload.description or "",
        "color": payload.color or "",
        "is_scope_final": bool(payload.is_scope_final),
        "created_at": now,
        "updated_at": now,
    }
    await db.article_categories.insert_one(doc)
    doc.pop("_id", None)
    await create_audit_log(entity_type="article_category", entity_id=doc["id"], action="created", actor=admin.get("email", "admin"), details={"name": doc["name"]})
    return {"category": doc}


@router.put("/article-categories/{category_id}")
async def update_article_category(
    category_id: str,
    payload: ArticleCategoryUpdate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    cat = await db.article_categories.find_one({**tf, "id": category_id}, {"_id": 0})
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    updates: Dict[str, Any] = {"updated_at": now_iso()}
    if payload.name is not None:
        updates["name"] = payload.name.strip()
        updates["slug"] = _slugify(payload.name.strip())
    if payload.description is not None:
        updates["description"] = payload.description
    if payload.color is not None:
        updates["color"] = payload.color
    if payload.is_scope_final is not None:
        updates["is_scope_final"] = payload.is_scope_final
    await db.article_categories.update_one({"id": category_id}, {"$set": updates})
    updated = await db.article_categories.find_one({"id": category_id}, {"_id": 0})
    await create_audit_log(entity_type="article_category", entity_id=category_id, action="updated", actor=admin.get("email", "admin"), details={"fields": list(updates.keys())})
    return {"category": updated}


@router.delete("/article-categories/{category_id}")
async def delete_article_category(
    category_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    cat = await db.article_categories.find_one({**tf, "id": category_id}, {"_id": 0})
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    article_count = await db.articles.count_documents({**tf, "category": cat["name"], "deleted_at": {"$exists": False}})
    if article_count > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete: {article_count} article(s) use this category")
    await db.article_categories.delete_one({"id": category_id})
    await create_audit_log(entity_type="article_category", entity_id=category_id, action="deleted", actor=admin.get("email", "admin"), details={"name": cat.get("name")})
    return {"message": "Category deleted"}


@router.get("/article-categories/{category_id}/logs")
async def get_article_category_logs(
    category_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    cat = await db.article_categories.find_one({**tf, "id": category_id}, {"_id": 0, "id": 1})
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    logs = await db.audit_logs.find(
        {"entity_type": "article_category", "entity_id": category_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return {"logs": logs}
