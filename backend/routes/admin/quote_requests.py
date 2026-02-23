"""Admin: Quote requests routes."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.helpers import make_id, now_iso
from core.security import require_admin, get_current_user
from core.tenant import get_tenant_filter, set_tenant_id, tenant_id_of, get_tenant_admin
from db.session import db
from models import QuoteRequest
from services.audit_service import AuditService, create_audit_log

router = APIRouter(prefix="/api", tags=["quote-requests"])


@router.post("/products/request-quote")
async def request_quote(
    payload: QuoteRequest,
    user: Dict[str, Any] = Depends(get_current_user),
):
    quote: Dict[str, Any] = {
        "id": make_id(),
        "tenant_id": user.get("tenant_id") or DEFAULT_TENANT_ID,
        "product_id": payload.product_id,
        "product_name": payload.product_name,
        "name": payload.name,
        "email": payload.email,
        "company": payload.company,
        "phone": payload.phone,
        "message": payload.message,
        "user_id": user["id"],
        "created_at": now_iso(),
        "status": "pending",
    }
    await db.quote_requests.insert_one(quote)
    quote.pop("_id", None)
    await AuditService.log(
        action="QUOTE_REQUEST_SUBMITTED",
        description=f"Quote request submitted for '{payload.product_name}' by {payload.email}",
        entity_type="QuoteRequest",
        entity_id=quote["id"],
        actor_type="user",
        actor_email=user.get("email"),
        source="customer_ui",
        meta_json={"product_id": payload.product_id, "company": payload.company},
    )
    await db.audit_logs.insert_one({"id": make_id(), "entity_type": "quote_request", "entity_id": quote["id"], "action": "submitted", "actor": user.get("email", ""), "details": {"product_name": payload.product_name, "company": payload.company}, "created_at": now_iso()})
    return {"message": "Quote request submitted. We will be in touch shortly.", "quote_id": quote["id"]}


@router.get("/admin/quote-requests")
async def admin_list_quote_requests(
    page: int = 1,
    per_page: int = 20,
    status: Optional[str] = None,
    email: Optional[str] = None,
    product: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    query: Dict[str, Any] = {**tf}
    if status:
        query["status"] = status
    if email:
        query["email"] = {"$regex": email, "$options": "i"}
    if product:
        query["product_name"] = {"$regex": product, "$options": "i"}
    if date_from:
        query.setdefault("created_at", {})["$gte"] = date_from
    if date_to:
        query.setdefault("created_at", {})["$lte"] = date_to + "T23:59:59"

    total = await db.quote_requests.count_documents(query)
    skip = (page - 1) * per_page
    quotes = await db.quote_requests.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(per_page).to_list(per_page)
    return {
        "quotes": quotes,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": max(1, (total + per_page - 1) // per_page),
    }


@router.post("/admin/quote-requests")
async def admin_create_quote_request(
    payload: Dict[str, Any],
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    quote: Dict[str, Any] = {
        "id": make_id(),
        "tenant_id": tenant_id_of(admin),
        "product_id": payload.get("product_id", ""),
        "product_name": payload.get("product_name", ""),
        "name": payload.get("name", ""),
        "email": payload.get("email", ""),
        "company": payload.get("company"),
        "phone": payload.get("phone"),
        "message": payload.get("message"),
        "user_id": payload.get("user_id", ""),
        "created_at": payload.get("created_at") or now_iso(),
        "status": payload.get("status", "pending"),
        "created_by_admin": True,
    }
    await db.quote_requests.insert_one(quote)
    quote.pop("_id", None)
    await AuditService.log(
        action="QUOTE_REQUEST_CREATED",
        description=f"Admin created quote request for '{quote.get('product_name')}' ({quote.get('email')})",
        entity_type="QuoteRequest",
        entity_id=quote["id"],
        actor_type="admin",
        actor_email=admin.get("email"),
        source="admin_ui",
        meta_json={"created_by_admin": True},
    )
    await db.audit_logs.insert_one({"id": make_id(), "entity_type": "quote_request", "entity_id": quote["id"], "action": "created", "actor": admin.get("email", "admin"), "details": {"product_name": quote.get("product_name"), "created_by_admin": True}, "created_at": now_iso()})
    return {"quote": quote}


@router.put("/admin/quote-requests/{quote_id}")
async def admin_update_quote_request(
    quote_id: str,
    payload: Dict[str, Any],
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    quote = await db.quote_requests.find_one({"id": quote_id})
    if not quote:
        raise HTTPException(status_code=404, detail="Quote request not found")
    allowed = ["product_id", "product_name", "name", "email", "company", "phone", "message", "status", "user_id"]
    update = {k: v for k, v in payload.items() if k in allowed}
    if update:
        await db.quote_requests.update_one({"id": quote_id}, {"$set": update})
    quote.update(update)
    quote.pop("_id", None)
    await AuditService.log(
        action="QUOTE_REQUEST_UPDATED",
        description=f"Quote request '{quote_id}' updated by admin",
        entity_type="QuoteRequest",
        entity_id=quote_id,
        actor_type="admin",
        actor_email=admin.get("email"),
        source="admin_ui",
        after_json=update,
    )
    await db.audit_logs.insert_one({"id": make_id(), "entity_type": "quote_request", "entity_id": quote_id, "action": "updated", "actor": admin.get("email", "admin"), "details": update, "created_at": now_iso()})
    return {"quote": quote}


@router.get("/admin/quote-requests/{quote_id}/logs")
async def get_quote_request_logs(quote_id: str, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    logs = await db.audit_logs.find({"entity_type": "quote_request", "entity_id": quote_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"logs": logs}

