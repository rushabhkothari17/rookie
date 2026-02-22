"""Articles routes: admin CRUD + public browsing + scope validation."""
from __future__ import annotations

import asyncio
import os
import re as _re
from typing import Any, Dict, Optional

import resend
from fastapi import APIRouter, Depends, HTTPException

from core.constants import ARTICLE_CATEGORIES, SCOPE_FINAL_CATEGORIES
from core.helpers import make_id, now_iso, _slugify
from core.security import get_current_user, require_admin
from db.session import db
from models import ArticleCreate, ArticleEmailRequest, ArticleUpdate
from services.audit_service import AuditService, create_audit_log
from services.settings_service import SettingsService

router = APIRouter(prefix="/api", tags=["articles"])


@router.get("/articles/admin/list")
async def list_articles_admin(
    page: int = 1,
    per_page: int = 20,
    category: Optional[str] = None,
    search: Optional[str] = None,
    created_from: Optional[str] = None,
    created_to: Optional[str] = None,
    admin: Dict[str, Any] = Depends(require_admin),
):
    query: Dict[str, Any] = {"deleted_at": {"$exists": False}}
    if category:
        query["category"] = category
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"id": {"$regex": search, "$options": "i"}},
        ]
    if created_from:
        query.setdefault("created_at", {})["$gte"] = created_from
    if created_to:
        query.setdefault("created_at", {})["$lte"] = created_to + "T23:59:59"

    total = await db.articles.count_documents(query)
    skip = (page - 1) * per_page
    articles = (
        await db.articles.find(query, {"_id": 0, "content": 0})
        .sort("created_at", -1)
        .skip(skip)
        .limit(per_page)
        .to_list(per_page)
    )
    return {
        "articles": articles,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": max(1, (total + per_page - 1) // per_page),
    }


@router.get("/articles/public")
async def list_articles_public(
    category: Optional[str] = None,
    user: Dict[str, Any] = Depends(get_current_user),
):
    customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
    customer_id = customer["id"] if customer else None
    query: Dict[str, Any] = {"deleted_at": {"$exists": False}}
    if category:
        query["category"] = category
    articles = await db.articles.find(query, {"_id": 0, "content": 0}).sort("updated_at", -1).to_list(500)
    visible = []
    for a in articles:
        if a.get("visibility") == "all" or not a.get("restricted_to"):
            visible.append(a)
        elif customer_id and customer_id in a.get("restricted_to", []):
            visible.append(a)
    return {"articles": visible}


@router.get("/articles/{article_id}/validate-scope")
async def validate_scope_article(
    article_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    article = await db.articles.find_one(
        {
            "$or": [
                {"id": article_id},
                {"id": {"$regex": f"^{_re.escape(article_id.lower())}"}},
            ],
            "deleted_at": {"$exists": False},
        },
        {"_id": 0, "content": 0},
    )
    if not article:
        raise HTTPException(status_code=404, detail="Invalid Scope Id")
    if not article.get("category", "").startswith("Scope - Final"):
        raise HTTPException(status_code=400, detail="Invalid Scope Id")
    if not article.get("price"):
        raise HTTPException(status_code=400, detail="Invalid Scope Id")
    return {
        "valid": True,
        "article_id": article["id"],
        "title": article["title"],
        "price": article["price"],
        "slug": article.get("slug"),
        "category": article["category"],
    }


@router.get("/articles/{article_id}/logs")
async def get_article_logs(
    article_id: str,
    admin: Dict[str, Any] = Depends(require_admin),
):
    logs = await db.article_logs.find({"article_id": article_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"logs": logs}


@router.get("/articles/{article_id}")
async def get_article_by_id(
    article_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    article = await db.articles.find_one(
        {"$or": [{"id": article_id}, {"slug": article_id}], "deleted_at": {"$exists": False}},
        {"_id": 0},
    )
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    if article.get("visibility") != "all" and article.get("restricted_to"):
        customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
        if not customer or customer["id"] not in article.get("restricted_to", []):
            raise HTTPException(status_code=403, detail="You don't have access to this article")
    return {"article": article}


@router.post("/articles")
async def create_article(
    payload: ArticleCreate,
    admin: Dict[str, Any] = Depends(require_admin),
):
    if payload.category not in ARTICLE_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid category")
    if payload.category in SCOPE_FINAL_CATEGORIES and not payload.price:
        raise HTTPException(status_code=400, detail="Price is required for Scope - Final articles")

    slug = payload.slug or _slugify(payload.title)
    existing = await db.articles.find_one({"slug": slug, "deleted_at": {"$exists": False}})
    if existing:
        slug = f"{slug}-{make_id()[:4]}"

    article_id = make_id()
    now = now_iso()
    doc = {
        "id": article_id,
        "title": payload.title,
        "slug": slug,
        "category": payload.category,
        "price": payload.price if payload.category in SCOPE_FINAL_CATEGORIES else None,
        "content": payload.content,
        "visibility": payload.visibility,
        "restricted_to": payload.restricted_to,
        "created_at": now,
        "updated_at": now,
    }
    await db.articles.insert_one(doc)
    await db.article_logs.insert_one({
        "id": make_id(),
        "article_id": article_id,
        "action": "created",
        "actor": admin.get("email", "admin"),
        "details": {"title": payload.title, "category": payload.category},
        "created_at": now,
    })
    await AuditService.log(
        action="ARTICLE_CREATED",
        description=f"Article '{payload.title}' created",
        entity_type="Article",
        entity_id=article_id,
        actor_type="admin",
        actor_email=admin.get("email"),
        source="admin_ui",
        after_json={"title": payload.title, "category": payload.category, "visibility": payload.visibility},
    )
    await db.audit_logs.insert_one({"id": make_id(), "entity_type": "article", "entity_id": article_id, "action": "created", "actor": admin.get("email", "admin"), "details": {"title": payload.title, "category": payload.category}, "created_at": now_iso()})
    doc.pop("_id", None)
    return {"article": doc}


@router.put("/articles/{article_id}")
async def update_article(
    article_id: str,
    payload: ArticleUpdate,
    admin: Dict[str, Any] = Depends(require_admin),
):
    article = await db.articles.find_one({"id": article_id, "deleted_at": {"$exists": False}}, {"_id": 0})
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    updates: Dict[str, Any] = {"updated_at": now_iso()}
    changes: Dict[str, Any] = {}

    if payload.title is not None:
        updates["title"] = payload.title
        changes["title"] = payload.title
    if payload.slug is not None:
        existing = await db.articles.find_one(
            {"slug": payload.slug, "id": {"$ne": article_id}, "deleted_at": {"$exists": False}}
        )
        if existing:
            raise HTTPException(status_code=400, detail="Slug already in use")
        updates["slug"] = payload.slug
        changes["slug"] = payload.slug

    effective_category = payload.category if payload.category is not None else article.get("category")
    if payload.category is not None:
        if payload.category not in ARTICLE_CATEGORIES:
            raise HTTPException(status_code=400, detail="Invalid category")
        updates["category"] = payload.category
        changes["category"] = payload.category

    if payload.price is not None:
        updates["price"] = payload.price
        changes["price"] = payload.price
    elif effective_category not in SCOPE_FINAL_CATEGORIES:
        updates["price"] = None

    if payload.content is not None:
        updates["content"] = payload.content
    if payload.visibility is not None:
        updates["visibility"] = payload.visibility
        changes["visibility"] = payload.visibility
    if payload.restricted_to is not None:
        updates["restricted_to"] = payload.restricted_to
        changes["restricted_to_count"] = len(payload.restricted_to)

    await db.articles.update_one({"id": article_id}, {"$set": updates})

    if changes:
        await db.article_logs.insert_one({
            "id": make_id(),
            "article_id": article_id,
            "action": "updated",
            "actor": admin.get("email", "admin"),
            "details": changes,
            "created_at": now_iso(),
        })
        await AuditService.log(
            action="ARTICLE_UPDATED",
            description=f"Article '{article.get('title')}' updated",
            entity_type="Article",
            entity_id=article_id,
            actor_type="admin",
            actor_email=admin.get("email"),
            source="admin_ui",
            after_json=changes,
        )

    updated = await db.articles.find_one({"id": article_id}, {"_id": 0})
    updated.pop("_id", None)
    return {"article": updated}


@router.delete("/articles/{article_id}")
async def delete_article(
    article_id: str,
    admin: Dict[str, Any] = Depends(require_admin),
):
    article = await db.articles.find_one({"id": article_id, "deleted_at": {"$exists": False}}, {"_id": 0})
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    now = now_iso()
    await db.articles.update_one({"id": article_id}, {"$set": {"deleted_at": now}})
    await db.article_logs.insert_one({
        "id": make_id(),
        "article_id": article_id,
        "action": "deleted",
        "actor": admin.get("email", "admin"),
        "details": {"title": article.get("title")},
        "created_at": now,
    })
    await AuditService.log(
        action="ARTICLE_DELETED",
        description=f"Article '{article.get('title')}' deleted",
        entity_type="Article",
        entity_id=article_id,
        actor_type="admin",
        actor_email=admin.get("email"),
        source="admin_ui",
        before_json={"title": article.get("title"), "category": article.get("category")},
    )
    return {"message": "Article deleted"}


@router.post("/articles/{article_id}/email")
async def email_article(
    article_id: str,
    payload: ArticleEmailRequest,
    admin: Dict[str, Any] = Depends(require_admin),
):
    article = await db.articles.find_one({"id": article_id, "deleted_at": {"$exists": False}}, {"_id": 0, "content": 0})
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    app_settings = await db.app_settings.find_one({}, {"_id": 0})
    resend_key = await SettingsService.get("resend_api_key") or (app_settings or {}).get("resend_api_key")
    if not resend_key:
        raise HTTPException(status_code=400, detail="Resend API key not configured. Please add it in Admin > Settings.")
    resend.api_key = resend_key

    customers = await db.customers.find({"id": {"$in": payload.customer_ids}}, {"_id": 0}).to_list(50)
    if not customers:
        raise HTTPException(status_code=404, detail="No customers found")

    user_ids = [c["user_id"] for c in customers if c.get("user_id")]
    users = await db.users.find({"id": {"$in": user_ids}}, {"_id": 0}).to_list(50)
    user_email_map = {u["id"]: u["email"] for u in users}

    app_url = os.environ.get("REACT_APP_BACKEND_URL", "").replace("/api", "").rstrip("/")
    article_url = f"{app_url}/articles/{article.get('slug') or article_id}"
    subject = payload.subject or f"Article: {article['title']}"
    sent = []
    errors = []
    now = now_iso()

    for customer in customers:
        email_addr = user_email_map.get(customer.get("user_id"))
        if not email_addr:
            continue
        message_body = payload.message or ""
        price_line = f"<p style='color:#475569;'>Price: <strong>${article['price']}</strong></p>" if article.get("price") else ""
        html_body = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
          <h2 style="color:#1e293b;">{article['title']}</h2>
          {"<p style='color:#475569;'>" + message_body + "</p>" if message_body else ""}
          <p style="color:#475569;">Category: <strong>{article['category']}</strong></p>
          {price_line}
          <a href="{article_url}" style="display:inline-block;background:#1e293b;color:white;padding:12px 24px;text-decoration:none;border-radius:6px;margin-top:16px;">
            View Article
          </a>
          <p style="color:#94a3b8;font-size:12px;margin-top:24px;">Your consultant has shared this document with you.</p>
        </div>"""
        try:
            params = {"from": "noreply@automateaccounts.com", "to": [email_addr], "subject": subject, "html": html_body}
            await asyncio.to_thread(resend.Emails.send, params)
            sent.append(email_addr)
            await db.article_logs.insert_one({
                "id": make_id(),
                "article_id": article_id,
                "action": "email_sent",
                "actor": admin.get("email", "admin"),
                "details": {"to": email_addr, "customer_id": customer["id"], "subject": subject},
                "created_at": now,
            })
        except Exception as e:
            errors.append({"email": email_addr, "error": str(e)})

    return {"sent": sent, "errors": errors, "message": f"Sent to {len(sent)} recipient(s)"}
