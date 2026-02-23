"""Articles routes: admin CRUD + public browsing + scope validation."""
from __future__ import annotations

import asyncio
import os
import re as _re
from typing import Any, Dict, Optional

import resend
from fastapi import APIRouter, Depends, HTTPException

from core.constants import ARTICLE_CATEGORIES, SCOPE_FINAL_CATEGORIES


async def _get_valid_categories(tenant_id: str = DEFAULT_TENANT_ID) -> set:
    """Get valid categories from DB, falling back to hardcoded constants."""
    db_cats = await db.article_categories.find({"tenant_id": tenant_id}, {"_id": 0, "name": 1}).to_list(200)
    if db_cats:
        return {c["name"] for c in db_cats}
    return set(ARTICLE_CATEGORIES)
from core.helpers import make_id, now_iso, _slugify
from core.security import get_current_user, require_admin
from core.tenant import get_tenant_filter, set_tenant_id, tenant_id_of, DEFAULT_TENANT_ID
from db.session import db
from models import ArticleCreate, ArticleEmailRequest, ArticleUpdate, ArticleSendEmailRequest
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
    tf = get_tenant_filter(admin)
    query: Dict[str, Any] = {**tf, "deleted_at": {"$exists": False}}
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


@router.get("/articles/{article_id}/download")
async def download_article(
    article_id: str,
    format: str = "pdf",
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Download an article as PDF or DOCX."""
    from fastapi.responses import Response
    from services.document_service import generate_pdf, generate_docx

    article = await db.articles.find_one(
        {"$or": [{"id": article_id}, {"slug": article_id}], "deleted_at": {"$exists": False}},
        {"_id": 0},
    )
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    if article.get("visibility") != "all" and article.get("restricted_to"):
        customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
        is_admin = user.get("role") in ("admin", "super_admin")
        if not is_admin and (not customer or customer["id"] not in article.get("restricted_to", [])):
            raise HTTPException(status_code=403, detail="You don't have access to this article")

    # Resolve author email
    author_user = await db.users.find_one({"id": user["id"]}, {"_id": 0, "email": 1, "full_name": 1})
    author = (author_user or {}).get("full_name") or (author_user or {}).get("email") or "—"

    title = article.get("title", "Article")
    content = article.get("content") or ""
    created_at = article.get("created_at", "")
    updated_at = article.get("updated_at", "")
    safe_name = _re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]

    # Fetch store branding from website settings
    ws = await db.website_settings.find_one({}, {"_id": 0, "store_name": 1, "accent_color": 1}) or {}
    store_name = str(ws.get("store_name") or "")
    accent_color = str(ws.get("accent_color") or "#0f172a")

    if format == "docx":
        data = generate_docx(title, author, created_at, updated_at, content, store_name=store_name)
        return Response(
            content=data,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}.docx"'},
        )
    else:
        data = generate_pdf(title, author, created_at, updated_at, content, store_name=store_name, accent_hex=accent_color)
        return Response(
            content=data,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}.pdf"'},
        )


@router.post("/articles")
async def create_article(
    payload: ArticleCreate,
    admin: Dict[str, Any] = Depends(require_admin),
):
    if payload.category not in await _get_valid_categories():
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
        if payload.category not in await _get_valid_categories():
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
        await db.audit_logs.insert_one({"id": make_id(), "entity_type": "article", "entity_id": article_id, "action": "updated", "actor": admin.get("email", "admin"), "details": changes, "created_at": now_iso()})

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
    await db.audit_logs.insert_one({"id": make_id(), "entity_type": "article", "entity_id": article_id, "action": "deleted", "actor": admin.get("email", "admin"), "details": {"title": article.get("title")}, "created_at": now_iso()})
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

    customers = await db.customers.find({"id": {"$in": payload.customer_ids}}, {"_id": 0}).to_list(50)
    if not customers:
        raise HTTPException(status_code=404, detail="No customers found")

    user_ids = [c["user_id"] for c in customers if c.get("user_id")]
    users = await db.users.find({"id": {"$in": user_ids}}, {"_id": 0}).to_list(50)
    user_email_map = {u["id"]: u["email"] for u in users}

    app_url = os.environ.get("REACT_APP_BACKEND_URL", "").replace("/api", "").rstrip("/")
    article_url = f"{app_url}/articles/{article.get('slug') or article_id}"
    web_s = await db.website_settings.find_one({}, {"_id": 0}) or {}
    subject_tpl = web_s.get("email_article_subject_template") or "{{article_title}} — from {{store_name}}"
    subject = payload.subject or subject_tpl.replace("{{article_title}}", article["title"])
    cta_text = web_s.get("email_article_cta_text") or "View Article"
    footer_text = web_s.get("email_article_footer_text") or ""

    from services.email_service import EmailService
    sent = []
    errors = []
    now = now_iso()

    for customer in customers:
        email_addr = user_email_map.get(customer.get("user_id"))
        if not email_addr:
            continue
        result = await EmailService.send(
            trigger="article_email",
            recipient=email_addr,
            variables={
                "article_title": article["title"],
                "article_category": article.get("category", ""),
                "article_url": article_url,
                "article_message": payload.message or "",
                "article_price": f"${article['price']}" if article.get("price") else "",
                "cta_text": cta_text,
                "footer_text": footer_text,
                "customer_name": "",
            },
            db=db,
        )
        if result.get("status") in ("sent", "mocked"):
            sent.append(email_addr)
            await db.article_logs.insert_one({
                "id": make_id(),
                "article_id": article_id,
                "action": "email_sent",
                "actor": admin.get("email", "admin"),
                "details": {"to": email_addr, "customer_id": customer["id"], "subject": subject},
                "created_at": now,
            })
        else:
            errors.append({"email": email_addr, "error": result.get("error") or result.get("reason", "unknown")})

    if sent:
        await create_audit_log(entity_type="article", entity_id=article_id, action="email_sent", actor=admin.get("email", "admin"), details={"recipients": sent, "subject": subject, "sent_count": len(sent)})
    return {"sent": sent, "errors": errors, "message": f"Sent to {len(sent)} recipient(s)"}


@router.post("/articles/{article_id}/send-email")
async def send_article_email(
    article_id: str,
    payload: ArticleSendEmailRequest,
    admin: Dict[str, Any] = Depends(require_admin),
):
    """Send article to arbitrary email addresses (To/CC/BCC) with optional PDF attachment."""
    article = await db.articles.find_one({"id": article_id, "deleted_at": {"$exists": False}}, {"_id": 0})
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    if not payload.to:
        raise HTTPException(status_code=400, detail="At least one recipient (To) is required")

    # Fetch branding
    ws = await db.website_settings.find_one({}, {"_id": 0, "store_name": 1, "accent_color": 1}) or {}
    store_name = str(ws.get("store_name") or "")
    accent_color = str(ws.get("accent_color") or "#0f172a")

    provider_enabled = await SettingsService.get("email_provider_enabled", False)
    resend_key = await SettingsService.get("resend_api_key", "")
    from_name = await SettingsService.get("email_from_name", "") or store_name
    from_email = await SettingsService.get("resend_sender_email", "noreply@example.com")

    now = now_iso()
    sent = []
    errors = []

    # Generate PDF attachment if requested
    attachment_data = None
    if payload.attach_pdf:
        try:
            from services.document_service import generate_pdf
            author_user = await db.users.find_one({"id": admin.get("id", "")}, {"_id": 0, "email": 1, "full_name": 1})
            author = (author_user or {}).get("full_name") or (author_user or {}).get("email") or admin.get("email", "admin")
            pdf_bytes = generate_pdf(
                title=article.get("title", "Article"),
                author=author,
                created_at=article.get("created_at", ""),
                updated_at=article.get("updated_at", ""),
                html_content=article.get("content") or "",
                store_name=store_name,
                accent_hex=accent_color,
            )
            safe_name = _re.sub(r"[^a-z0-9]+", "-", article.get("title", "article").lower()).strip("-")[:60]
            attachment_data = {
                "filename": f"{safe_name}.pdf",
                "content": list(pdf_bytes),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {exc}")

    log_entry: Dict[str, Any] = {
        "id": make_id(),
        "trigger": "article_email_direct",
        "recipient": ", ".join(payload.to),
        "subject": payload.subject,
        "status": "pending",
        "provider": "mocked",
        "created_at": now,
    }

    if provider_enabled and resend_key:
        log_entry["provider"] = "resend"
        try:
            import resend as resend_sdk
            resend_sdk.api_key = resend_key
            params: Dict[str, Any] = {
                "from": f"{from_name} <{from_email}>" if from_name else from_email,
                "to": payload.to,
                "subject": payload.subject,
                "html": payload.html_body,
            }
            if payload.cc:
                params["cc"] = payload.cc
            if payload.bcc:
                params["bcc"] = payload.bcc
            if attachment_data:
                params["attachments"] = [attachment_data]
            await asyncio.to_thread(resend_sdk.Emails.send, params)
            log_entry["status"] = "sent"
            sent = payload.to
        except Exception as exc:
            log_entry["status"] = "failed"
            log_entry["error_message"] = str(exc)
            await db.email_logs.insert_one(log_entry)
            raise HTTPException(status_code=500, detail=f"Failed to send email: {exc}")
    else:
        # Mocked
        log_entry["status"] = "mocked"
        sent = payload.to
        await db.email_outbox.insert_one({
            "id": make_id(),
            "to": payload.to,
            "cc": payload.cc or [],
            "bcc": payload.bcc or [],
            "subject": payload.subject,
            "body": payload.html_body,
            "type": "article_email_direct",
            "has_attachment": bool(attachment_data),
            "status": "MOCKED",
            "created_at": now,
        })

    await db.email_logs.insert_one(log_entry)

    # Log the send action on the article
    await db.article_logs.insert_one({
        "id": make_id(),
        "article_id": article_id,
        "action": "email_sent",
        "actor": admin.get("email", "admin"),
        "details": {
            "to": payload.to,
            "cc": payload.cc or [],
            "bcc": payload.bcc or [],
            "subject": payload.subject,
            "has_attachment": bool(attachment_data),
        },
        "created_at": now,
    })
    await create_audit_log(
        entity_type="article",
        entity_id=article_id,
        action="email_sent",
        actor=admin.get("email", "admin"),
        details={"recipients": payload.to, "subject": payload.subject, "sent_count": len(sent)},
    )

    return {
        "sent": sent,
        "errors": errors,
        "message": f"Sent to {len(sent)} recipient(s)" + (" (mocked)" if not (provider_enabled and resend_key) else ""),
        "mocked": not (provider_enabled and resend_key),
    }
