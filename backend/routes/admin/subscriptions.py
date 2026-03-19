"""Admin: Subscription management routes."""
from __future__ import annotations

import asyncio
import re as _re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException

from core.helpers import make_id, now_iso
from core.tenant import get_tenant_filter, tenant_id_of, get_tenant_admin, is_platform_admin, enrich_partner_codes
from core.constants import ALLOWED_SUBSCRIPTION_STATUSES, ALLOWED_PAYMENT_METHODS, ALLOWED_ORDER_STATUSES
from db.session import db
from models import SubscriptionUpdate, ManualSubscriptionCreate
from services.audit_service import create_audit_log
from routes.admin.permissions import has_permission as _has_perm

_MODULE = "subscriptions"

async def _check(admin: Dict[str, Any], action: str):
    if not await _has_perm(admin, _MODULE, action):
        raise HTTPException(403, f"No {action} access to {_MODULE} module")

from services.webhook_service import dispatch_event
from services.zoho_service import auto_sync_to_zoho_crm, auto_sync_to_zoho_books

from services.checkout_service import get_fx_rate, get_tenant_base_currency

router = APIRouter(prefix="/api", tags=["admin-subscriptions"])


def _add_months(dt: datetime, months: int) -> datetime:
    """Add calendar months to a datetime using proper month arithmetic (M-11)."""
    return dt + relativedelta(months=months)


# X-3: sort field alias mapping (colKey → MongoDB / aggregation field name)
_SUB_SORT_ALIASES: Dict[str, str] = {
    "sub_number": "subscription_number",
    "email": "customer_email",
    "plan": "plan_name",
    "tax": "tax_amount",
    "payment": "payment_method",
}
_SUB_SORTABLE_FIELDS = {
    "created_at", "subscription_number", "customer_email", "plan_name", "tax_amount",
    "payment_method", "amount", "currency", "renewal_date", "start_date",
    "contract_end_date", "status", "processor_id", "updated_at",
}


@router.get("/admin/subscriptions/stats")
async def admin_subscriptions_stats(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """KPI dashboard stats for the Subscriptions tab."""
    tf = get_tenant_filter(admin)
    tid = tenant_id_of(admin)
    base_currency = await get_tenant_base_currency(tid)

    now = datetime.now(timezone.utc)
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d")
    next_month_start = f"{now.year + 1}-01-01" if now.month == 12 else f"{now.year}-{now.month + 1:02d}-01"
    base_flt = {**tf}

    async def _total():
        return await db.subscriptions.count_documents(base_flt)

    async def _by_status():
        pipeline = [{"$match": base_flt}, {"$group": {"_id": "$status", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]
        results = await db.subscriptions.aggregate(pipeline).to_list(20)
        return {(r["_id"] or "unknown"): r["count"] for r in results}

    async def _by_payment_method():
        pipeline = [{"$match": base_flt}, {"$group": {"_id": "$payment_method", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]
        results = await db.subscriptions.aggregate(pipeline).to_list(20)
        return {(r["_id"] or "unknown"): r["count"] for r in results}

    async def _mrr_by_currency():
        """Sum normalized monthly amounts for active subscriptions, grouped by currency."""
        pipeline = [
            {"$match": {**base_flt, "status": "active"}},
            {"$addFields": {
                "monthly_amount": {"$switch": {
                    "branches": [
                        {"case": {"$eq": ["$billing_interval", "weekly"]},    "then": {"$multiply": ["$amount", 4.333]}},
                        {"case": {"$eq": ["$billing_interval", "monthly"]},   "then": "$amount"},
                        {"case": {"$eq": ["$billing_interval", "quarterly"]}, "then": {"$divide": ["$amount", 3]}},
                        {"case": {"$eq": ["$billing_interval", "biannual"]},  "then": {"$divide": ["$amount", 6]}},
                        {"case": {"$eq": ["$billing_interval", "annual"]},    "then": {"$divide": ["$amount", 12]}},
                    ],
                    "default": "$amount",
                }},
            }},
            {"$group": {"_id": "$currency", "total": {"$sum": "$monthly_amount"}}},
        ]
        return await db.subscriptions.aggregate(pipeline).to_list(20)

    async def _new_this_month():
        return await db.subscriptions.count_documents({**base_flt, "created_at": {"$gte": this_month_start, "$lt": next_month_start}})

    async def _churned_this_month():
        return await db.subscriptions.count_documents({
            **base_flt,
            "status": {"$in": ["cancelled", "canceled"]},
            "canceled_at": {"$gte": this_month_start, "$lt": next_month_start},
        })

    async def _active_count():
        return await db.subscriptions.count_documents({**base_flt, "status": "active"})

    total, by_status, by_method, mrr_by_cur, new_this_month, churned_this_month, active_count = await asyncio.gather(
        _total(), _by_status(), _by_payment_method(), _mrr_by_currency(),
        _new_this_month(), _churned_this_month(), _active_count(),
    )

    mrr_base = 0.0
    for row in mrr_by_cur:
        cur = (row.get("_id") or "USD").upper()
        rate = await get_fx_rate(cur, base_currency)
        mrr_base += round((row.get("total") or 0) * rate, 2)
    mrr_base = round(mrr_base, 2)

    return {
        "total": total,
        "active": active_count,
        "new_this_month": new_this_month,
        "churned_this_month": churned_this_month,
        "base_currency": base_currency,
        "mrr_base": mrr_base,
        "by_status": by_status,
        "by_payment_method": by_method,
    }


@router.get("/admin/filter-options")
async def get_filter_options(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Single source of truth for all admin filter dropdowns."""
    return {
        "order_statuses": ALLOWED_ORDER_STATUSES,
        "subscription_statuses": ALLOWED_SUBSCRIPTION_STATUSES,
        "payment_methods": ALLOWED_PAYMENT_METHODS,
    }


@router.get("/admin/subscriptions")
async def admin_subscriptions(
    page: int = 1,
    per_page: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    status: Optional[str] = None,
    payment: Optional[str] = None,
    email: Optional[str] = None,
    sub_number: Optional[str] = None,
    processor_id_filter: Optional[str] = None,
    plan_name_filter: Optional[str] = None,
    currency: Optional[str] = None,
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    amount_currency: Optional[str] = None,
    tax_min: Optional[float] = None,
    tax_max: Optional[float] = None,
    tax_currency: Optional[str] = None,
    renewal_from: Optional[str] = None,
    renewal_to: Optional[str] = None,
    created_from: Optional[str] = None,
    created_to: Optional[str] = None,
    start_from: Optional[str] = None,
    start_to: Optional[str] = None,
    contract_end_from: Optional[str] = None,
    contract_end_to: Optional[str] = None,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    await _check(admin, "view")
    query: Dict[str, Any] = {**tf}
    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        query["status"] = {"$in": statuses} if len(statuses) > 1 else statuses[0]
    if payment:
        payments = [p.strip() for p in payment.split(",") if p.strip()]
        query["payment_method"] = {"$in": payments} if len(payments) > 1 else payments[0]
    if sub_number:
        sub_numbers = [s.strip() for s in sub_number.split(",") if s.strip()]
        query["subscription_number"] = {"$in": sub_numbers} if len(sub_numbers) > 1 else {"$regex": _re.escape(sub_numbers[0]), "$options": "i"}
    if processor_id_filter:
        pids = [p.strip() for p in processor_id_filter.split(",") if p.strip()]
        query["processor_id"] = {"$in": pids} if len(pids) > 1 else {"$regex": _re.escape(pids[0]), "$options": "i"}
    if plan_name_filter:
        plans = [p.strip() for p in plan_name_filter.split(",") if p.strip()]
        query["plan_name"] = {"$in": plans} if len(plans) > 1 else {"$regex": _re.escape(plans[0]), "$options": "i"}
    if currency:
        currencies_list = [c.strip() for c in currency.split(",") if c.strip()]
        query["currency"] = {"$in": currencies_list} if len(currencies_list) > 1 else currencies_list[0]
    if amount_min is not None:
        query.setdefault("amount", {})["$gte"] = amount_min
    if amount_max is not None:
        query.setdefault("amount", {})["$lte"] = amount_max
    if tax_min is not None:
        query.setdefault("tax_amount", {})["$gte"] = tax_min
    if tax_max is not None:
        query.setdefault("tax_amount", {})["$lte"] = tax_max
    # M-9: merge amount_currency and tax_currency into the same currency filter
    #       instead of overwriting query["currency"] multiple times
    _extra_currencies: set = set()
    if amount_currency:
        _extra_currencies.add(amount_currency.strip())
    if tax_currency:
        _extra_currencies.add(tax_currency.strip())
    if _extra_currencies:
        existing_cur = query.get("currency")
        if existing_cur:
            # Combine with existing currency constraint
            existing_set = set(existing_cur["$in"]) if isinstance(existing_cur, dict) else {existing_cur}
            merged = list(existing_set & _extra_currencies) or list(existing_set | _extra_currencies)
        else:
            merged = list(_extra_currencies)
        query["currency"] = {"$in": merged} if len(merged) > 1 else merged[0]
    if renewal_from:
        query.setdefault("renewal_date", {})["$gte"] = renewal_from
    if renewal_to:
        query.setdefault("renewal_date", {})["$lte"] = renewal_to + "T23:59:59"
    if created_from:
        query.setdefault("created_at", {})["$gte"] = created_from
    if created_to:
        query.setdefault("created_at", {})["$lte"] = created_to + "T23:59:59"
    if start_from:
        query.setdefault("start_date", {})["$gte"] = start_from
    if start_to:
        query.setdefault("start_date", {})["$lte"] = start_to + "T23:59:59"
    if contract_end_from:
        query.setdefault("contract_end_date", {})["$gte"] = contract_end_from
    if contract_end_to:
        query.setdefault("contract_end_date", {})["$lte"] = contract_end_to + "T23:59:59"

    sort_dir = -1 if sort_order == "desc" else 1
    
    # Use aggregation pipeline for efficient customer/user lookups (avoid N+1)
    pipeline: list = [
        {"$match": query},
    ]
    
    # Join with customers to get user_id
    pipeline.append({
        "$lookup": {
            "from": "customers",
            "localField": "customer_id",
            "foreignField": "id",
            "as": "customer_data"
        }
    })
    pipeline.append({"$unwind": {"path": "$customer_data", "preserveNullAndEmptyArrays": True}})
    
    # Join with users to get email
    pipeline.append({
        "$lookup": {
            "from": "users",
            "localField": "customer_data.user_id",
            "foreignField": "id",
            "as": "user_data"
        }
    })
    pipeline.append({"$unwind": {"path": "$user_data", "preserveNullAndEmptyArrays": True}})
    
    # Add email filter if provided — Fix #10: support multi-email comma-separated
    if email:
        emails = [e.strip().lower() for e in email.split(",") if e.strip()]
        if len(emails) > 1:
            pipeline.append({"$match": {"user_data.email": {"$in": emails}}})
        else:
            pipeline.append({"$match": {"user_data.email": {"$regex": _re.escape(emails[0]), "$options": "i"}}})
    
    # Project the fields we need (include customer email for frontend)
    pipeline.append({
        "$addFields": {
            "customer_email": "$user_data.email",
            "customer_name": "$user_data.full_name"
        }
    })
    
    # Remove joined data and _id
    pipeline.append({
        "$project": {
            "_id": 0,
            "customer_data": 0,
            "user_data": 0
        }
    })
    
    # Count total before pagination
    count_pipeline = pipeline + [{"$count": "total"}]
    count_result = await db.subscriptions.aggregate(count_pipeline).to_list(1)
    total = count_result[0]["total"] if count_result else 0
    
    # X-3: normalise sort field (colKey alias → MongoDB/aggregation field name)
    _sort_field = _SUB_SORT_ALIASES.get(sort_by, sort_by)
    if _sort_field not in _SUB_SORTABLE_FIELDS:
        _sort_field = "created_at"
    pipeline.append({"$sort": {_sort_field: sort_dir}})
    skip = (page - 1) * per_page
    pipeline.append({"$skip": skip})
    pipeline.append({"$limit": per_page})
    
    subs = await db.subscriptions.aggregate(pipeline).to_list(per_page)
    subs = await enrich_partner_codes(subs, is_platform_admin(admin))

    return {
        "subscriptions": subs,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": max(1, (total + per_page - 1) // per_page),
    }


@router.get("/admin/subscriptions/{subscription_id}/logs")
async def get_subscription_logs(subscription_id: str, page: int = 1, limit: int = 20, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    sub = await db.subscriptions.find_one({**tf, "id": subscription_id}, {"_id": 0, "id": 1})
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    flt = {"entity_type": "subscription", "entity_id": subscription_id}
    total = await db.audit_logs.count_documents(flt)
    skip = (page - 1) * limit
    logs = await db.audit_logs.find(flt, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"logs": logs, "total": total, "page": page, "limit": limit, "pages": max(1, (total + limit - 1) // limit)}


@router.post("/admin/subscriptions/manual")
async def create_manual_subscription(
    payload: ManualSubscriptionCreate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    await _check(admin, "create")
    user = await db.users.find_one({**tf, "email": payload.customer_email.lower()}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Customer not found")

    customer = await db.customers.find_one({**tf, "user_id": user["id"]}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer record not found")

    if customer.get("deleted_at"):
        raise HTTPException(status_code=400, detail="Cannot create a subscription for a deleted customer.")

    product = await db.products.find_one({**tf, "id": payload.product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # License enforcement: check monthly subscription limit
    from services.license_service import check_limit as _check_limit, increment_monthly as _inc_monthly
    _tid = tenant_id_of(admin)
    _sub_check = await _check_limit(_tid, "subscriptions")
    if not _sub_check["allowed"]:
        raise HTTPException(
            status_code=403,
            detail=f"This organization has reached its monthly subscription limit ({_sub_check['current']}/{_sub_check['limit']}). Please contact support.",
        )

    sub_id = make_id()
    sub_number = f"SUB-{sub_id.split('-')[0].upper()}"

    try:
        renewal_date_dt = datetime.fromisoformat(payload.renewal_date.replace("Z", "+00:00"))
    except Exception:
        renewal_date_dt = datetime.now(timezone.utc) + timedelta(days=30)

    sub_doc = {
        "id": sub_id,
        "tenant_id": tenant_id_of(admin),
        "subscription_number": sub_number,
        "customer_id": customer["id"],
        "plan_name": product["name"],
        "product_id": product["id"],
        "status": payload.status,
        "payment_method": payload.payment_method,           # Fix #8
        "billing_interval": payload.billing_interval,       # Fix #4
        "amount": payload.amount,
        "currency": payload.currency or product.get("currency", "USD"),
        "renewal_date": renewal_date_dt.isoformat(),
        "start_date": payload.start_date or now_iso(),
        "cancel_at_period_end": False,
        "canceled_at": None,
        "internal_note": payload.internal_note or "",
        "notes": [],
        "term_months": payload.term_months if payload.term_months and payload.term_months > 0 else None,
        "auto_cancel_on_termination": payload.auto_cancel_on_termination,
        "reminder_days": payload.reminder_days,
        "created_at": now_iso(),
        "created_by_admin": admin["id"],
        "is_manual": True,
        # Fix #3: only set contract_end_date when term_months > 0 (M-11: use calendar months)
        "contract_end_date": _add_months(
            datetime.fromisoformat(
                (payload.start_date or now_iso()).replace("Z", "+00:00")
            ).replace(tzinfo=timezone.utc),
            payload.term_months
        ).isoformat() if payload.term_months and payload.term_months > 0 else None,
    }
    await db.subscriptions.insert_one(sub_doc)
    await _inc_monthly(_tid, "subscriptions")

    await create_audit_log(
        entity_type="subscription",
        entity_id=sub_id,
        action="created_manual",
        actor=f"admin:{admin['id']}",
        details={"status": payload.status, "amount": payload.amount, "renewal_date": renewal_date_dt.isoformat()},
    )

    # Webhook: subscription.created (customer scoped by tenant)
    customer = await db.customers.find_one({**get_tenant_filter(admin), "id": sub_doc.get("customer_id", "")}, {"_id": 0}) or {}
    await dispatch_event("subscription.created", {
        "id": sub_id,
        "subscription_number": sub_number,
        "plan_name": sub_doc.get("plan_name", ""),
        "status": sub_doc.get("status", ""),
        "amount": sub_doc.get("amount", 0),
        "currency": sub_doc.get("currency", ""),
        "billing_frequency": sub_doc.get("billing_frequency", ""),
        "customer_email": customer.get("email", ""),
        "customer_name": customer.get("full_name", ""),
        "start_date": sub_doc.get("start_date", ""),
        "created_at": sub_doc.get("created_at", ""),
    }, tenant_id_of(admin))

    # Auto-sync to Zoho CRM (fire and forget)
    asyncio.create_task(auto_sync_to_zoho_crm(tenant_id_of(admin), "subscriptions", sub_doc, "create"))
    asyncio.create_task(auto_sync_to_zoho_books(tenant_id_of(admin), "subscriptions", sub_doc, "create"))

    return {
        "message": "Manual subscription created",
        "subscription_id": sub_id,
        "subscription_number": sub_number,
    }


@router.post("/admin/subscriptions/{subscription_id}/renew-now")
async def renew_subscription_now(
    subscription_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    subscription = await db.subscriptions.find_one({**tf, "id": subscription_id}, {"_id": 0})
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    order_id = make_id()
    order_number = f"AA-{order_id.split('-')[0].upper()}"

    order_doc = {
        "id": order_id,
        "tenant_id": tenant_id_of(admin),
        "order_number": order_number,
        "customer_id": subscription["customer_id"],
        "subscription_id": subscription_id,
        "subscription_number": subscription.get("subscription_number", ""),
        "type": "subscription_renewal",
        "status": "unpaid",
        "subtotal": subscription["amount"],
        "discount_amount": 0.0,
        "fee": 0.0,
        "total": subscription["amount"],
        "currency": subscription.get("currency", "USD"),    # Fix #1
        "payment_method": subscription.get("payment_method", "offline"),
        "created_at": now_iso(),
        "created_by_admin": admin["id"],
    }
    await db.orders.insert_one(order_doc)

    # Fix #2: advance renewal date by actual billing interval
    from services.billing_service import advance_billing_date
    billing_interval = subscription.get("billing_interval", "monthly")
    current_renewal = datetime.fromisoformat(subscription["renewal_date"].replace("Z", "+00:00"))
    next_renewal_str = advance_billing_date(current_renewal.date(), billing_interval)

    await db.subscriptions.update_one(
        {"id": subscription_id},
        {"$set": {"renewal_date": next_renewal_str, "updated_at": now_iso()}},
    )

    await create_audit_log(
        entity_type="subscription",
        entity_id=subscription_id,
        action="renewed",
        actor=f"admin:{admin['id']}",
        details={"order_id": order_id, "order_number": order_number, "amount": subscription["amount"]},
    )
    await create_audit_log(
        entity_type="order",
        entity_id=order_id,
        action="created_renewal",
        actor=f"admin:{admin['id']}",
        details={"subscription_id": subscription_id, "status": "unpaid"},
    )

    return {
        "message": "Renewal order created",
        "order_id": order_id,
        "order_number": order_number,
        "next_renewal_date": next_renewal_str,
    }


@router.put("/admin/subscriptions/{subscription_id}")
async def update_subscription(
    subscription_id: str,
    payload: SubscriptionUpdate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    await _check(admin, "edit")
    subscription = await db.subscriptions.find_one({**tf, "id": subscription_id}, {"_id": 0})
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    update_fields: Dict[str, Any] = {}
    changes: Dict[str, Any] = {}
    if payload.renewal_date is not None:
        update_fields["renewal_date"] = payload.renewal_date         # Fix #5
        changes["renewal_date"] = {"old": subscription.get("renewal_date"), "new": payload.renewal_date}
    if payload.start_date is not None:
        update_fields["start_date"] = payload.start_date
        changes["start_date"] = {"old": subscription.get("start_date"), "new": payload.start_date}
    if payload.contract_end_date is not None:
        update_fields["contract_end_date"] = payload.contract_end_date
        changes["contract_end_date"] = {"old": subscription.get("contract_end_date"), "new": payload.contract_end_date}
    if payload.amount is not None:
        update_fields["amount"] = payload.amount
        changes["amount"] = {"old": subscription.get("amount"), "new": payload.amount}
    if payload.status is not None:
        if payload.status not in ALLOWED_SUBSCRIPTION_STATUSES:
            raise HTTPException(status_code=400, detail=f"Invalid status '{payload.status}'.")
        update_fields["status"] = payload.status
        changes["status"] = {"old": subscription.get("status"), "new": payload.status}
    if payload.plan_name is not None:
        update_fields["plan_name"] = payload.plan_name
        changes["plan_name"] = {"old": subscription.get("plan_name"), "new": payload.plan_name}
    if payload.customer_id is not None:
        # Validate customer belongs to same tenant
        new_customer = await db.customers.find_one({**tf, "id": payload.customer_id}, {"_id": 0})
        if not new_customer:
            raise HTTPException(status_code=400, detail="Invalid customer_id - customer not found in your tenant")
        update_fields["customer_id"] = payload.customer_id
        changes["customer_id"] = {"old": subscription.get("customer_id"), "new": payload.customer_id}
    if payload.payment_method is not None:
        update_fields["payment_method"] = payload.payment_method
        changes["payment_method"] = {"old": subscription.get("payment_method"), "new": payload.payment_method}
    if payload.billing_interval is not None:                          # Fix #9
        update_fields["billing_interval"] = payload.billing_interval
        changes["billing_interval"] = {"old": subscription.get("billing_interval"), "new": payload.billing_interval}
    if payload.currency is not None:                                  # Fix #9
        update_fields["currency"] = payload.currency
        changes["currency"] = {"old": subscription.get("currency"), "new": payload.currency}
    if payload.processor_id is not None:
        update_fields["processor_id"] = payload.processor_id
        changes["processor_id"] = {"old": subscription.get("processor_id"), "new": payload.processor_id}

    if payload.term_months is not None:
        new_term = None if payload.term_months <= 0 else payload.term_months
        update_fields["term_months"] = new_term
        changes["term_months"] = {"old": subscription.get("term_months"), "new": new_term}
        # Recalculate contract_end_date when term_months changes
        if new_term:
            start = subscription.get("start_date") or subscription.get("created_at", now_iso())
            try:
                start_dt = datetime.fromisoformat(start.replace("Z", "+00:00")).replace(tzinfo=timezone.utc)
            except Exception:
                start_dt = datetime.now(timezone.utc)
            new_contract_end = _add_months(start_dt, new_term).isoformat()  # M-11: calendar months
            update_fields["contract_end_date"] = new_contract_end
            changes["contract_end_date"] = {"old": subscription.get("contract_end_date"), "new": new_contract_end}
        else:
            update_fields["contract_end_date"] = None
            changes["contract_end_date"] = {"old": subscription.get("contract_end_date"), "new": None}

    if payload.auto_cancel_on_termination is not None:
        update_fields["auto_cancel_on_termination"] = payload.auto_cancel_on_termination
        changes["auto_cancel_on_termination"] = {"old": subscription.get("auto_cancel_on_termination"), "new": payload.auto_cancel_on_termination}

    if payload.reminder_days is not None:
        new_reminder = None if payload.reminder_days <= 0 else payload.reminder_days
        update_fields["reminder_days"] = new_reminder
        changes["reminder_days"] = {"old": subscription.get("reminder_days"), "new": new_reminder}

    # Reset reminder tracking when renewal_date changes
    if "renewal_date" in update_fields:
        update_fields["reminder_sent_for_renewal_date"] = None

    if update_fields:
        update_fields["updated_at"] = now_iso()
        await db.subscriptions.update_one({"id": subscription_id}, {"$set": update_fields})
        await create_audit_log(
            entity_type="subscription",
            entity_id=subscription_id,
            action="updated",
            actor=f"admin:{admin['id']}",
            details={"changes": changes},
        )

    if payload.new_note:
        note_entry = {"text": payload.new_note, "timestamp": now_iso(), "actor": f"admin:{admin['id']}"}
        await db.subscriptions.update_one({"id": subscription_id}, {"$push": {"notes": note_entry}})
        await create_audit_log(
            entity_type="subscription",
            entity_id=subscription_id,
            action="note_added",
            actor=f"admin:{admin['id']}",
            details={"note": payload.new_note},
        )

    # Auto-sync to Zoho CRM on update (fire and forget)
    updated_sub = await db.subscriptions.find_one({"id": subscription_id}, {"_id": 0})
    if updated_sub:
        asyncio.create_task(auto_sync_to_zoho_crm(tenant_id_of(admin), "subscriptions", updated_sub, "update"))
        asyncio.create_task(auto_sync_to_zoho_books(tenant_id_of(admin), "subscriptions", updated_sub, "update"))

    return {"message": "Subscription updated"}


@router.post("/admin/subscriptions/{subscription_id}/cancel")
async def admin_cancel_subscription(
    subscription_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    await _check(admin, "edit")   # Fix #11: cancel is an edit action, not delete
    subscription = await db.subscriptions.find_one({**tf, "id": subscription_id}, {"_id": 0})
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    term_months = subscription.get("term_months")
    contract_end = subscription.get("contract_end_date")
    if term_months and term_months > 0 and contract_end:
        try:
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

    old_status = subscription.get("status")
    cancelled_at = now_iso()

    await db.subscriptions.update_one(
        {"id": subscription_id},
        {"$set": {
            "cancel_at_period_end": True,
            "status": "canceled_pending",
            "canceled_at": cancelled_at,
            "updated_at": cancelled_at,
        }},
    )
    await create_audit_log(
        entity_type="subscription",
        entity_id=subscription_id,
        action="cancelled",
        actor=f"admin:{admin['id']}",
        details={"changes": {"status": {"old": old_status, "new": "canceled_pending"}}, "cancelled_at": cancelled_at},
    )
    # Webhook: subscription.cancelled (tenant-scoped customer lookup)
    customer = await db.customers.find_one({**tf, "id": subscription.get("customer_id", "")}, {"_id": 0}) or {}
    # M-12: look up email via user record once (remove duplicate fetch below)
    user = await db.users.find_one({"id": customer.get("user_id", "")}, {"_id": 0}) or {}
    cancel_email = user.get("email") or customer.get("email", "")
    await dispatch_event("subscription.cancelled", {
        "id": subscription_id,
        "subscription_number": subscription.get("subscription_number", ""),
        "plan_name": subscription.get("plan_name", ""),
        "cancel_reason": "Admin cancelled",
        "cancel_at_period_end": True,
        "customer_email": cancel_email,
        "customer_name": user.get("full_name") or customer.get("full_name", ""),
        "cancelled_at": cancelled_at,
    }, tenant_id_of(admin))
    if cancel_email:
        from services.email_service import EmailService
        asyncio.create_task(EmailService.send(
            trigger="subscription_terminated",
            recipient=cancel_email,
            variables={
                "recipient_name": customer.get("full_name") or user.get("full_name") or cancel_email,
                "subscription_number": subscription.get("subscription_number", ""),
                "plan_name": subscription.get("plan_name", ""),
                "cancelled_at": cancelled_at[:10],
                "cancel_reason": "Subscription cancelled by administrator",
            },
            db=db,
            tenant_id=tenant_id_of(admin),
        ))

    return {"message": "Subscription cancellation scheduled", "cancelled_at": cancelled_at}


@router.post("/admin/subscriptions/{subscription_id}/send-reminder")
async def send_subscription_reminder(
    subscription_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """Immediately send a renewal reminder email for the given subscription (admin test action)."""
    tf = get_tenant_filter(admin)
    subscription = await db.subscriptions.find_one({**tf, "id": subscription_id}, {"_id": 0})
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    renewal_str = (subscription.get("renewal_date") or "")[:10]
    if not renewal_str:
        raise HTTPException(status_code=400, detail="Subscription has no renewal date set")

    customer = await db.customers.find_one({**tf, "id": subscription.get("customer_id", "")}, {"_id": 0}) or {}
    user = await db.users.find_one({"id": customer.get("user_id", "")}, {"_id": 0}) or {}
    email = user.get("email") or customer.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="No email address found for this subscription's customer")

    from services.email_service import EmailService
    await EmailService.send(
        trigger="subscription_renewal_reminder",
        recipient=email,
        variables={
            "customer_name": customer.get("full_name") or user.get("full_name") or email,
            "subscription_number": subscription.get("subscription_number", ""),
            "plan_name": subscription.get("plan_name", ""),
            "amount": f"{subscription.get('amount', 0):.2f}",
            "currency": subscription.get("currency", ""),
            "renewal_date": renewal_str,
        },
        db=db,
        tenant_id=tenant_id_of(admin),
    )
    return {"message": f"Renewal reminder sent to {email}"}
