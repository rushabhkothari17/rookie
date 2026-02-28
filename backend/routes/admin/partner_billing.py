"""Partner Billing — platform admin manages B2B billing for partner organisations.

Partner orders: one-time fees (onboarding, add-ons, overages).
Partner subscriptions: recurring SaaS plan fees (monthly/annual).

Supports:
  - Manual creation by platform admin
  - Stripe hosted checkout (for card payments)
  - Bank transfer / offline payment methods
  - Stripe webhook auto-renewal via webhooks.py
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from core.config import STRIPE_API_KEY, APP_URL
from core.helpers import make_id, now_iso
from core.tenant import require_platform_admin, get_tenant_admin, tenant_id_of, DEFAULT_TENANT_ID
from db.session import db
from services.audit_service import create_audit_log

router = APIRouter(prefix="/api", tags=["partner-billing"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PARTNER_ORDER_STATUSES = ["pending", "unpaid", "paid", "cancelled", "refunded"]
PARTNER_SUB_STATUSES = ["pending", "active", "unpaid", "paused", "cancelled"]
BILLING_INTERVALS = ["monthly", "quarterly", "annual"]
PAYMENT_METHODS = ["card", "bank_transfer", "manual", "offline"]


async def _get_platform_stripe_key() -> Optional[str]:
    """Use the platform (automate-accounts) tenant's Stripe credentials, falling back to env key."""
    conn = await db.oauth_connections.find_one(
        {"tenant_id": DEFAULT_TENANT_ID, "provider": "stripe", "is_validated": True},
        {"_id": 0, "credentials": 1},
    )
    if conn:
        return conn.get("credentials", {}).get("api_key") or STRIPE_API_KEY
    return STRIPE_API_KEY or None


def _next_order_number(prefix: str, seq: int) -> str:
    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y')}-{seq:04d}"


async def _gen_order_number() -> str:
    count = await db.partner_orders.count_documents({})
    return f"PO-{datetime.now(timezone.utc).strftime('%Y')}-{(count + 1):04d}"


async def _gen_sub_number() -> str:
    count = await db.partner_subscriptions.count_documents({})
    return f"PS-{datetime.now(timezone.utc).strftime('%Y')}-{(count + 1):04d}"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class PartnerOrderCreate(BaseModel):
    partner_id: str
    plan_id: Optional[str] = None
    description: str
    amount: float
    currency: str = "GBP"
    status: str = "unpaid"
    payment_method: str = "manual"
    processor_id: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    paid_at: Optional[str] = None
    internal_note: Optional[str] = None


class PartnerOrderUpdate(BaseModel):
    description: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    status: Optional[str] = None
    payment_method: Optional[str] = None
    processor_id: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    paid_at: Optional[str] = None
    internal_note: Optional[str] = None


class PartnerSubscriptionCreate(BaseModel):
    partner_id: str
    plan_id: Optional[str] = None
    description: Optional[str] = None
    amount: float
    currency: str = "GBP"
    billing_interval: str = "monthly"
    status: str = "pending"
    payment_method: str = "manual"
    processor_id: Optional[str] = None
    start_date: Optional[str] = None
    next_billing_date: Optional[str] = None
    internal_note: Optional[str] = None
    term_months: Optional[int] = None  # None/0 = cancel anytime; 1-999 = locked term
    auto_cancel_on_termination: bool = False
    reminder_days: Optional[int] = None  # None = use org default


class PartnerSubscriptionUpdate(BaseModel):
    description: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    billing_interval: Optional[str] = None
    status: Optional[str] = None
    payment_method: Optional[str] = None
    processor_id: Optional[str] = None
    start_date: Optional[str] = None
    next_billing_date: Optional[str] = None
    internal_note: Optional[str] = None
    term_months: Optional[int] = None  # -1 sentinel to clear term
    auto_cancel_on_termination: Optional[bool] = None
    reminder_days: Optional[int] = None  # -1 to clear (set to null)


class PartnerCheckoutRequest(BaseModel):
    """Initiate Stripe hosted checkout for a partner subscription/order."""
    partner_subscription_id: Optional[str] = None  # for subscriptions
    partner_order_id: Optional[str] = None          # for one-time orders


# ---------------------------------------------------------------------------
# Partner Orders — Stats
# ---------------------------------------------------------------------------

@router.get("/admin/partner-orders/stats")
async def partner_orders_stats(admin: Dict[str, Any] = Depends(require_platform_admin)):
    pipeline = [
        {"$facet": {
            "total": [{"$count": "n"}],
            "by_status": [{"$group": {"_id": "$status", "count": {"$sum": 1}}}],
            "by_method": [{"$group": {"_id": "$payment_method", "count": {"$sum": 1}}}],
            "revenue_paid": [
                {"$match": {"status": "paid"}},
                {"$group": {"_id": "$currency", "total": {"$sum": "$amount"}}},
            ],
            "this_month": [
                {"$match": {"created_at": {"$gte": datetime.now(timezone.utc).strftime("%Y-%m")}}},
                {"$count": "n"},
            ],
        }}
    ]
    result = await db.partner_orders.aggregate(pipeline).to_list(1)
    r = result[0] if result else {}
    return {
        "total": (r.get("total") or [{}])[0].get("n", 0),
        "this_month": (r.get("this_month") or [{}])[0].get("n", 0),
        "by_status": {x["_id"]: x["count"] for x in r.get("by_status", []) if x["_id"]},
        "by_method": {x["_id"]: x["count"] for x in r.get("by_method", []) if x["_id"]},
        "revenue_paid": {x["_id"]: round(x["total"], 2) for x in r.get("revenue_paid", []) if x["_id"]},
    }


# ---------------------------------------------------------------------------
# Partner Orders — CRUD
# ---------------------------------------------------------------------------

@router.get("/admin/partner-orders")
async def list_partner_orders(
    partner_id: Optional[str] = None,
    status: Optional[str] = None,
    payment_method: Optional[str] = None,
    plan_id: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    admin: Dict[str, Any] = Depends(require_platform_admin),
):
    query: Dict[str, Any] = {}
    if partner_id:
        query["partner_id"] = partner_id
    if status:
        query["status"] = status
    if payment_method:
        query["payment_method"] = payment_method
    if plan_id:
        query["plan_id"] = plan_id
    if search:
        query["$or"] = [
            {"partner_name": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
            {"order_number": {"$regex": search, "$options": "i"}},
        ]

    skip = (page - 1) * limit
    total = await db.partner_orders.count_documents(query)
    orders = await db.partner_orders.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"orders": orders, "total": total, "page": page, "limit": limit, "pages": max(1, (total + limit - 1) // limit)}


@router.post("/admin/partner-orders")
async def create_partner_order(
    payload: PartnerOrderCreate,
    admin: Dict[str, Any] = Depends(require_platform_admin),
):
    tenant = await db.tenants.find_one({"id": payload.partner_id}, {"_id": 0, "id": 1, "name": 1})
    if tenant is None:
        raise HTTPException(status_code=404, detail="Partner not found")

    if payload.status not in PARTNER_ORDER_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Allowed: {PARTNER_ORDER_STATUSES}")
    if payload.payment_method not in PAYMENT_METHODS:
        raise HTTPException(status_code=400, detail=f"Invalid payment method. Allowed: {PAYMENT_METHODS}")

    # Resolve plan name if plan_id provided
    plan_name = None
    if payload.plan_id:
        plan = await db.plans.find_one({"id": payload.plan_id}, {"_id": 0, "name": 1})
        plan_name = plan.get("name") if plan else None

    order_id = make_id()
    order_number = await _gen_order_number()
    doc: Dict[str, Any] = {
        "id": order_id,
        "order_number": order_number,
        "partner_id": payload.partner_id,
        "partner_name": tenant.get("name", ""),
        "plan_id": payload.plan_id,
        "plan_name": plan_name,
        "description": payload.description.strip(),
        "amount": round(payload.amount, 2),
        "currency": payload.currency.upper(),
        "status": payload.status,
        "payment_method": payload.payment_method,
        "processor_id": payload.processor_id,
        "invoice_date": payload.invoice_date or now_iso()[:10],
        "due_date": payload.due_date,
        "paid_at": payload.paid_at,
        "internal_note": payload.internal_note or "",
        "created_by": admin.get("email", "admin"),
        "payment_url": None,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.partner_orders.insert_one({**doc})
    await create_audit_log(
        entity_type="partner_order", entity_id=order_id, action="created",
        actor=admin.get("email", "admin"),
        details={"order_number": order_number, "partner": tenant.get("name"), "amount": payload.amount, "currency": payload.currency},
    )

    # Send partner_order_created email to partner's primary admin
    partner_admin = await db.users.find_one(
        {"tenant_id": payload.partner_id, "role": {"$in": ["partner_super_admin", "partner_admin"]}},
        {"_id": 0, "email": 1, "full_name": 1},
    )
    if partner_admin and partner_admin.get("email"):
        payment_link_html = ""
        if doc.get("payment_url"):
            payment_link_html = f'<div style="margin:16px 0"><a href="{doc["payment_url"]}" style="display:inline-block;background:#1e293b;color:white;padding:12px 24px;text-decoration:none;border-radius:6px;font-weight:600">Pay Now</a></div>'
        from services.email_service import EmailService
        import asyncio as _asyncio
        _asyncio.create_task(EmailService.send(
            trigger="partner_order_created",
            recipient=partner_admin["email"],
            variables={
                "partner_name": tenant.get("name", ""),
                "order_number": order_number,
                "description": payload.description.strip(),
                "amount": f"{payload.amount:.2f}",
                "currency": payload.currency.upper(),
                "invoice_date": payload.invoice_date or now_iso()[:10],
                "due_date": payload.due_date or "—",
                "payment_method": payload.payment_method.replace("_", " ").title(),
                "payment_link_section": payment_link_html,
            },
            db=db,
            tenant_id=DEFAULT_TENANT_ID,
        ))

    return {"order": doc}


@router.get("/admin/partner-orders/{order_id}")
async def get_partner_order(order_id: str, admin: Dict[str, Any] = Depends(require_platform_admin)):
    order = await db.partner_orders.find_one({"id": order_id}, {"_id": 0})
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    logs = await db.audit_logs.find({"entity_type": "partner_order", "entity_id": order_id}, {"_id": 0}).sort("created_at", -1).limit(20).to_list(20)
    return {"order": order, "logs": logs}


@router.put("/admin/partner-orders/{order_id}")
async def update_partner_order(
    order_id: str,
    payload: PartnerOrderUpdate,
    admin: Dict[str, Any] = Depends(require_platform_admin),
):
    order = await db.partner_orders.find_one({"id": order_id}, {"_id": 0, "id": 1})
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    updates = {k: v for k, v in payload.dict(exclude_unset=True).items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    updates["updated_at"] = now_iso()

    await db.partner_orders.update_one({"id": order_id}, {"$set": updates})
    await create_audit_log(
        entity_type="partner_order", entity_id=order_id, action="updated",
        actor=admin.get("email", "admin"), details=updates,
    )
    order = await db.partner_orders.find_one({"id": order_id}, {"_id": 0})
    return {"order": order}


@router.delete("/admin/partner-orders/{order_id}")
async def delete_partner_order(order_id: str, admin: Dict[str, Any] = Depends(require_platform_admin)):
    order = await db.partner_orders.find_one({"id": order_id}, {"_id": 0, "id": 1, "order_number": 1})
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    await db.partner_orders.update_one({"id": order_id}, {"$set": {"deleted_at": now_iso(), "updated_at": now_iso()}})
    await create_audit_log(
        entity_type="partner_order", entity_id=order_id, action="deleted",
        actor=admin.get("email", "admin"), details={"order_number": order.get("order_number")},
    )
    return {"message": "Order deleted"}


# ---------------------------------------------------------------------------
# Partner Subscriptions — Stats
# ---------------------------------------------------------------------------

@router.get("/admin/partner-subscriptions/stats")
async def partner_subscriptions_stats(admin: Dict[str, Any] = Depends(require_platform_admin)):
    pipeline = [
        {"$facet": {
            "total": [{"$count": "n"}],
            "active": [{"$match": {"status": "active"}}, {"$count": "n"}],
            "by_status": [{"$group": {"_id": "$status", "count": {"$sum": 1}}}],
            "by_interval": [{"$group": {"_id": "$billing_interval", "count": {"$sum": 1}}}],
            "mrr": [
                {"$match": {"status": "active", "billing_interval": "monthly"}},
                {"$group": {"_id": "$currency", "total": {"$sum": "$amount"}}},
            ],
            "arr": [
                {"$match": {"status": "active", "billing_interval": "annual"}},
                {"$group": {"_id": "$currency", "total": {"$sum": "$amount"}}},
            ],
            "new_this_month": [
                {"$match": {"created_at": {"$gte": datetime.now(timezone.utc).strftime("%Y-%m")}}},
                {"$count": "n"},
            ],
        }}
    ]
    result = await db.partner_subscriptions.aggregate(pipeline).to_list(1)
    r = result[0] if result else {}
    return {
        "total": (r.get("total") or [{}])[0].get("n", 0),
        "active": (r.get("active") or [{}])[0].get("n", 0),
        "new_this_month": (r.get("new_this_month") or [{}])[0].get("n", 0),
        "by_status": {x["_id"]: x["count"] for x in r.get("by_status", []) if x["_id"]},
        "by_interval": {x["_id"]: x["count"] for x in r.get("by_interval", []) if x["_id"]},
        "mrr": {x["_id"]: round(x["total"], 2) for x in r.get("mrr", []) if x["_id"]},
        "arr": {x["_id"]: round(x["total"], 2) for x in r.get("arr", []) if x["_id"]},
    }


# ---------------------------------------------------------------------------
# Partner Subscriptions — CRUD
# ---------------------------------------------------------------------------

@router.get("/admin/partner-subscriptions")
async def list_partner_subscriptions(
    partner_id: Optional[str] = None,
    status: Optional[str] = None,
    payment_method: Optional[str] = None,
    plan_id: Optional[str] = None,
    billing_interval: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    admin: Dict[str, Any] = Depends(require_platform_admin),
):
    query: Dict[str, Any] = {"deleted_at": {"$exists": False}}
    if partner_id:
        query["partner_id"] = partner_id
    if status:
        query["status"] = status
    if payment_method:
        query["payment_method"] = payment_method
    if plan_id:
        query["plan_id"] = plan_id
    if billing_interval:
        query["billing_interval"] = billing_interval
    if search:
        query["$or"] = [
            {"partner_name": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
            {"subscription_number": {"$regex": search, "$options": "i"}},
        ]

    skip = (page - 1) * limit
    total = await db.partner_subscriptions.count_documents(query)
    subs = await db.partner_subscriptions.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"subscriptions": subs, "total": total, "page": page, "limit": limit, "pages": max(1, (total + limit - 1) // limit)}


@router.post("/admin/partner-subscriptions")
async def create_partner_subscription(
    payload: PartnerSubscriptionCreate,
    admin: Dict[str, Any] = Depends(require_platform_admin),
):
    tenant = await db.tenants.find_one({"id": payload.partner_id}, {"_id": 0, "id": 1, "name": 1})
    if tenant is None:
        raise HTTPException(status_code=404, detail="Partner not found")

    if payload.billing_interval not in BILLING_INTERVALS:
        raise HTTPException(status_code=400, detail=f"Invalid billing_interval. Allowed: {BILLING_INTERVALS}")
    if payload.status not in PARTNER_SUB_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Allowed: {PARTNER_SUB_STATUSES}")
    if payload.payment_method not in PAYMENT_METHODS:
        raise HTTPException(status_code=400, detail=f"Invalid payment_method. Allowed: {PAYMENT_METHODS}")

    plan_name = None
    if payload.plan_id:
        plan = await db.plans.find_one({"id": payload.plan_id}, {"_id": 0, "name": 1})
        plan_name = plan.get("name") if plan else None

    sub_id = make_id()
    sub_number = await _gen_sub_number()
    term_months_val = payload.term_months if payload.term_months and payload.term_months > 0 else None
    start_str = payload.start_date or now_iso()[:10]
    # Calculate contract_end_date from term_months
    contract_end_date: Optional[str] = None
    if term_months_val:
        from datetime import timedelta
        try:
            start_dt = datetime.fromisoformat(start_str)
        except Exception:
            start_dt = datetime.now(timezone.utc)
        contract_end_date = (start_dt + timedelta(days=30 * term_months_val)).strftime("%Y-%m-%d")

    doc: Dict[str, Any] = {
        "id": sub_id,
        "subscription_number": sub_number,
        "partner_id": payload.partner_id,
        "partner_name": tenant.get("name", ""),
        "plan_id": payload.plan_id,
        "plan_name": plan_name,
        "description": (payload.description or "").strip(),
        "amount": round(payload.amount, 2),
        "currency": payload.currency.upper(),
        "billing_interval": payload.billing_interval,
        "status": payload.status,
        "payment_method": payload.payment_method,
        "processor_id": payload.processor_id,
        "stripe_subscription_id": None,
        "start_date": start_str,
        "next_billing_date": payload.next_billing_date,
        "term_months": term_months_val,
        "auto_cancel_on_termination": payload.auto_cancel_on_termination,
        "contract_end_date": contract_end_date,
        "cancelled_at": None,
        "internal_note": payload.internal_note or "",
        "created_by": admin.get("email", "admin"),
        "payment_url": None,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.partner_subscriptions.insert_one({**doc})
    await create_audit_log(
        entity_type="partner_subscription", entity_id=sub_id, action="created",
        actor=admin.get("email", "admin"),
        details={"sub_number": sub_number, "partner": tenant.get("name"), "amount": payload.amount, "interval": payload.billing_interval, "term_months": term_months_val},
    )

    # Send partner_subscription_created email to partner's primary admin
    partner_admin = await db.users.find_one(
        {"tenant_id": payload.partner_id, "role": {"$in": ["partner_super_admin", "partner_admin"]}},
        {"_id": 0, "email": 1, "full_name": 1},
    )
    if partner_admin and partner_admin.get("email"):
        partner_tenant = await db.tenants.find_one({"id": payload.partner_id}, {"_id": 0, "code": 1})
        partner_code = partner_tenant.get("code", "") if partner_tenant else ""
        from services.email_service import EmailService
        import asyncio as _asyncio
        _asyncio.create_task(EmailService.send(
            trigger="partner_subscription_created",
            recipient=partner_admin["email"],
            variables={
                "partner_name": tenant.get("name", ""),
                "partner_code": partner_code,
                "subscription_number": sub_number,
                "plan_name": plan_name or "—",
                "amount": f"{payload.amount:.2f}",
                "currency": payload.currency.upper(),
                "billing_interval": payload.billing_interval,
                "start_date": start_str,
                "next_billing_date": payload.next_billing_date or "—",
            },
            db=db,
            tenant_id=DEFAULT_TENANT_ID,
        ))

    return {"subscription": doc}


@router.get("/admin/partner-subscriptions/{sub_id}")
async def get_partner_subscription(sub_id: str, admin: Dict[str, Any] = Depends(require_platform_admin)):
    sub = await db.partner_subscriptions.find_one({"id": sub_id}, {"_id": 0})
    if sub is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    logs = await db.audit_logs.find({"entity_type": "partner_subscription", "entity_id": sub_id}, {"_id": 0}).sort("created_at", -1).limit(20).to_list(20)
    return {"subscription": sub, "logs": logs}


@router.put("/admin/partner-subscriptions/{sub_id}")
async def update_partner_subscription(
    sub_id: str,
    payload: PartnerSubscriptionUpdate,
    admin: Dict[str, Any] = Depends(require_platform_admin),
):
    sub = await db.partner_subscriptions.find_one({"id": sub_id}, {"_id": 0, "id": 1, "start_date": 1, "term_months": 1})
    if sub is None:
        raise HTTPException(status_code=404, detail="Subscription not found")

    updates = {k: v for k, v in payload.dict(exclude_unset=True).items() if v is not None}
    # Handle term_months: -1 or 0 sentinel clears the term
    if "term_months" in payload.dict(exclude_unset=True):
        raw_term = payload.term_months
        new_term = None if (raw_term is None or raw_term <= 0) else raw_term
        updates["term_months"] = new_term
        if new_term:
            from datetime import timedelta
            start_str = (payload.dict(exclude_unset=True).get("start_date") or sub.get("start_date") or now_iso()[:10])
            try:
                start_dt = datetime.fromisoformat(start_str)
            except Exception:
                start_dt = datetime.now(timezone.utc)
            updates["contract_end_date"] = (start_dt + timedelta(days=30 * new_term)).strftime("%Y-%m-%d")
        else:
            updates["contract_end_date"] = None
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    updates["updated_at"] = now_iso()

    await db.partner_subscriptions.update_one({"id": sub_id}, {"$set": updates})
    await create_audit_log(
        entity_type="partner_subscription", entity_id=sub_id, action="updated",
        actor=admin.get("email", "admin"), details=updates,
    )
    sub = await db.partner_subscriptions.find_one({"id": sub_id}, {"_id": 0})
    return {"subscription": sub}


@router.patch("/admin/partner-subscriptions/{sub_id}/cancel")
async def cancel_partner_subscription(sub_id: str, admin: Dict[str, Any] = Depends(require_platform_admin)):
    sub = await db.partner_subscriptions.find_one({"id": sub_id}, {"_id": 0})
    if sub is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    if sub.get("status") == "cancelled":
        raise HTTPException(status_code=400, detail="Subscription is already cancelled")

    # Check contract term — block early cancellation
    term_months = sub.get("term_months")
    contract_end = sub.get("contract_end_date")
    if term_months and term_months > 0 and contract_end:
        try:
            from datetime import timedelta as _td
            end_dt = datetime.fromisoformat(contract_end.replace("Z", "+00:00")).replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) < end_dt:
                end_fmt = end_dt.strftime("%d %b %Y")
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot cancel: contract term runs until {end_fmt}. To override, update term_months to 0 first.",
                )
        except HTTPException:
            raise
        except Exception:
            pass

    # If Stripe subscription, cancel it there too
    if sub.get("stripe_subscription_id"):
        try:
            import stripe as stripe_sdk  # type: ignore
            stripe_key = await _get_platform_stripe_key()
            if stripe_key:
                stripe_sdk.api_key = stripe_key
                stripe_sdk.Subscription.modify(
                    sub["stripe_subscription_id"],
                    cancel_at_period_end=True,
                )
        except Exception:
            pass  # Don't fail if Stripe cancel fails

    cancelled_at = now_iso()
    await db.partner_subscriptions.update_one(
        {"id": sub_id},
        {"$set": {"status": "cancelled", "cancelled_at": cancelled_at, "updated_at": cancelled_at}},
    )
    await create_audit_log(
        entity_type="partner_subscription", entity_id=sub_id, action="cancelled",
        actor=admin.get("email", "admin"), details={"cancelled_at": cancelled_at},
    )

    # Send subscription_terminated email to partner admin
    partner_admin = await db.users.find_one(
        {"tenant_id": sub.get("partner_id"), "role": {"$in": ["partner_super_admin", "partner_admin"]}},
        {"_id": 0, "email": 1, "full_name": 1},
    )
    if partner_admin and partner_admin.get("email"):
        from services.email_service import EmailService
        import asyncio as _asyncio
        _asyncio.create_task(EmailService.send(
            trigger="subscription_terminated",
            recipient=partner_admin["email"],
            variables={
                "recipient_name": sub.get("partner_name", ""),
                "subscription_number": sub.get("subscription_number", ""),
                "plan_name": sub.get("plan_name", "—"),
                "cancelled_at": cancelled_at[:10],
                "cancel_reason": "Subscription cancelled by platform administrator",
            },
            db=db,
            tenant_id=DEFAULT_TENANT_ID,
        ))

    sub = await db.partner_subscriptions.find_one({"id": sub_id}, {"_id": 0})
    return {"subscription": sub}


# ---------------------------------------------------------------------------
# Stripe Hosted Checkout — for partner subscriptions & one-time orders
# ---------------------------------------------------------------------------

@router.post("/admin/partner-billing/stripe-checkout")
async def create_partner_stripe_checkout(
    payload: PartnerCheckoutRequest,
    request: Request,
    admin: Dict[str, Any] = Depends(require_platform_admin),
):
    """
    Generate a Stripe Checkout URL for a partner subscription or one-time order.
    The platform admin can share this link with the partner to complete payment.
    """
    try:
        import stripe as stripe_sdk  # type: ignore
    except ImportError:
        raise HTTPException(status_code=500, detail="Stripe SDK not installed")

    stripe_key = await _get_platform_stripe_key()
    if not stripe_key:
        raise HTTPException(status_code=400, detail="Stripe is not configured for the platform. Add Stripe under Connected Services.")

    stripe_sdk.api_key = stripe_key

    host_url = str(request.base_url).rstrip("/")
    # Use app URL from env if available (handles reverse proxy)
    if APP_URL:
        host_url = APP_URL

    success_url = f"{host_url}/partner-billing/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{host_url}/partner-billing/cancelled"

    if payload.partner_subscription_id:
        sub = await db.partner_subscriptions.find_one({"id": payload.partner_subscription_id}, {"_id": 0})
        if sub is None:
            raise HTTPException(status_code=404, detail="Subscription not found")
        if sub.get("payment_method") != "card":
            raise HTTPException(status_code=400, detail="Subscription payment method must be 'card' to use Stripe checkout")

        interval_map = {"monthly": "month", "annual": "year", "quarterly": None}
        stripe_interval = interval_map.get(sub.get("billing_interval", "monthly"), "month")
        if not stripe_interval:
            raise HTTPException(status_code=400, detail="Quarterly billing is not supported for Stripe recurring. Use monthly or annual.")

        # Create ad-hoc Stripe Price
        price = stripe_sdk.Price.create(
            unit_amount=int(round(sub["amount"] * 100)),
            currency=sub.get("currency", "GBP").lower(),
            recurring={"interval": stripe_interval},
            product_data={"name": f"Platform Subscription — {sub.get('plan_name') or sub.get('description', 'Platform Access')}"},
        )

        session = stripe_sdk.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price.id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "type": "partner_subscription",
                "partner_subscription_id": sub["id"],
                "partner_id": sub["partner_id"],
            },
            subscription_data={
                "metadata": {
                    "partner_subscription_id": sub["id"],
                    "partner_id": sub["partner_id"],
                }
            },
        )
        payment_url = session.url
        await db.partner_subscriptions.update_one(
            {"id": sub["id"]},
            {"$set": {"payment_url": payment_url, "stripe_session_id": session.id, "updated_at": now_iso()}},
        )
        await create_audit_log(
            entity_type="partner_subscription", entity_id=sub["id"],
            action="stripe_checkout_created", actor=admin.get("email", "admin"),
            details={"session_id": session.id},
        )
        return {"url": payment_url, "session_id": session.id}

    elif payload.partner_order_id:
        order = await db.partner_orders.find_one({"id": payload.partner_order_id}, {"_id": 0})
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")
        if order.get("payment_method") != "card":
            raise HTTPException(status_code=400, detail="Order payment method must be 'card' to use Stripe checkout")

        session = stripe_sdk.checkout.Session.create(
            mode="payment",
            line_items=[{
                "price_data": {
                    "currency": order.get("currency", "GBP").lower(),
                    "unit_amount": int(round(order["amount"] * 100)),
                    "product_data": {"name": order.get("description", "Platform Fee")},
                },
                "quantity": 1,
            }],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "type": "partner_order",
                "partner_order_id": order["id"],
                "partner_id": order["partner_id"],
            },
        )
        payment_url = session.url
        await db.partner_orders.update_one(
            {"id": order["id"]},
            {"$set": {"payment_url": payment_url, "stripe_session_id": session.id, "updated_at": now_iso()}},
        )
        await create_audit_log(
            entity_type="partner_order", entity_id=order["id"],
            action="stripe_checkout_created", actor=admin.get("email", "admin"),
            details={"session_id": session.id},
        )
        return {"url": payment_url, "session_id": session.id}

    raise HTTPException(status_code=400, detail="Provide partner_subscription_id or partner_order_id")


# ---------------------------------------------------------------------------
# Partner self-service billing view (partner admin)
# ---------------------------------------------------------------------------

@router.get("/partner/billing/current")
async def get_partner_billing_overview(
    admin_user: Dict[str, Any] = Depends(get_tenant_admin),
):
    """Partner admin views their own active subscriptions and recent orders."""
    tid = tenant_id_of(admin_user)
    subscriptions = await db.partner_subscriptions.find(
        {"partner_id": tid, "deleted_at": {"$exists": False}}, {"_id": 0}
    ).sort("created_at", -1).to_list(20)
    orders = await db.partner_orders.find(
        {"partner_id": tid, "deleted_at": {"$exists": False}}, {"_id": 0}
    ).sort("created_at", -1).limit(10).to_list(10)
    return {"subscriptions": subscriptions, "orders": orders}
