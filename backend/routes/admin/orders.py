"""Admin: Order management routes."""
from __future__ import annotations

import asyncio
import re as _re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.helpers import make_id, now_iso, round_cents
from core.tenant import get_tenant_filter, set_tenant_id, tenant_id_of, get_tenant_admin, is_platform_admin, enrich_partner_codes
from core.constants import ALLOWED_ORDER_STATUSES
from db.session import db
from models import OrderUpdate, OrderDelete, ManualOrderCreate
from services.audit_service import create_audit_log
from routes.admin.permissions import has_permission as _has_perm

_MODULE = "orders"

async def _check(admin: Dict[str, Any], action: str):
    if not await _has_perm(admin, _MODULE, action):
        raise HTTPException(403, f"No {action} access to {_MODULE} module")

from services.webhook_service import dispatch_event
from services.zoho_service import auto_sync_to_zoho_crm, auto_sync_to_zoho_books
from gocardless_helper import create_payment

from services.checkout_service import get_fx_rate, get_tenant_base_currency

router = APIRouter(prefix="/api", tags=["admin-orders"])

# X-3: sort field alias mapping (colKey → MongoDB field name)
_ORDER_SORT_ALIASES: Dict[str, str] = {
    "date": "created_at",
    "sub_number": "subscription_number",
    "pay_date": "payment_date",
    "method": "payment_method",
    "partner": "partner_code",
    "tax": "tax_amount",
}
_ORDER_SORTABLE_FIELDS = {
    "created_at", "order_number", "subscription_number", "payment_date",
    "payment_method", "partner_code", "tax_amount", "total", "subtotal",
    "fee", "status", "currency", "processor_id", "updated_at",
}


@router.get("/admin/orders/stats")
async def admin_orders_stats(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """KPI dashboard stats for the Orders tab."""
    tf = get_tenant_filter(admin)
    tid = tenant_id_of(admin)
    base_currency = await get_tenant_base_currency(tid)

    now = datetime.now(timezone.utc)
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d")
    last_month_start = (now.replace(day=1) - timedelta(days=1)).replace(day=1).strftime("%Y-%m-%d")
    base_flt = {**tf, "deleted_at": {"$exists": False}}

    async def _total():
        return await db.orders.count_documents(base_flt)

    async def _this_month():
        return await db.orders.count_documents({**base_flt, "created_at": {"$gte": this_month_start}})

    async def _last_month():
        return await db.orders.count_documents({**base_flt, "created_at": {"$gte": last_month_start, "$lt": this_month_start}})

    async def _by_status():
        pipeline = [{"$match": base_flt}, {"$group": {"_id": "$status", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]
        results = await db.orders.aggregate(pipeline).to_list(20)
        return {(r["_id"] or "unknown"): r["count"] for r in results}

    async def _by_payment_method():
        pipeline = [{"$match": base_flt}, {"$group": {"_id": "$payment_method", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]
        results = await db.orders.aggregate(pipeline).to_list(20)
        return {(r["_id"] or "unknown"): r["count"] for r in results}

    async def _revenue_by_currency():
        pipeline = [
            {"$match": {**base_flt, "status": {"$in": ["paid", "completed"]}}},
            {"$group": {"_id": "$currency", "total": {"$sum": "$total"}}},
        ]
        return await db.orders.aggregate(pipeline).to_list(20)

    async def _this_month_revenue_by_currency():
        pipeline = [
            {"$match": {**base_flt, "status": {"$in": ["paid", "completed"]}, "created_at": {"$gte": this_month_start}}},
            {"$group": {"_id": "$currency", "total": {"$sum": "$total"}}},
        ]
        return await db.orders.aggregate(pipeline).to_list(20)

    total, this_month, last_month, by_status, by_method, rev_by_cur, this_month_rev = await asyncio.gather(
        _total(), _this_month(), _last_month(), _by_status(), _by_payment_method(),
        _revenue_by_currency(), _this_month_revenue_by_currency(),
    )

    # Convert all currencies to base
    async def _to_base(rows):
        result = 0.0
        for row in rows:
            cur = (row.get("_id") or "USD").upper()
            rate = await get_fx_rate(cur, base_currency)
            result += round((row.get("total") or 0) * rate, 2)
        return round(result, 2)

    revenue_base, this_month_revenue_base = await asyncio.gather(
        _to_base(rev_by_cur), _to_base(this_month_rev),
    )

    return {
        "total": total,
        "this_month": this_month,
        "last_month": last_month,
        "base_currency": base_currency,
        "revenue_base": revenue_base,
        "this_month_revenue_base": this_month_revenue_base,
        "by_status": by_status,
        "by_payment_method": by_method,
    }


@router.get("/admin/orders")
async def admin_orders(
    page: int = 1,
    per_page: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    include_deleted: bool = False,
    product_filter: Optional[str] = None,
    order_number_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    sub_number_filter: Optional[str] = None,
    processor_id_filter: Optional[str] = None,
    payment_method_filter: Optional[str] = None,
    pay_date_from: Optional[str] = None,
    pay_date_to: Optional[str] = None,
    partner_filter: Optional[str] = None,
    email_filter: Optional[str] = None,           # X-2: server-side email filter
    customer_name_filter: Optional[str] = None,   # X-2: server-side customer name filter
    created_from: Optional[str] = None,            # X-1: server-side creation date filter
    created_to: Optional[str] = None,              # X-1: server-side creation date filter
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    skip = (page - 1) * per_page
    tf = get_tenant_filter(admin)
    await _check(admin, "view")
    query: Dict[str, Any] = {**tf}
    if not include_deleted:
        query["deleted_at"] = {"$exists": False}

    # H-3: multi-value support via $in for all token filters
    if order_number_filter:
        nums = [n.strip() for n in order_number_filter.split(",") if n.strip()]
        query["order_number"] = {"$in": nums} if len(nums) > 1 else {"$regex": _re.escape(nums[0]), "$options": "i"}
    if status_filter:
        statuses = [s.strip() for s in status_filter.split(",") if s.strip()]
        query["status"] = {"$in": statuses} if len(statuses) > 1 else statuses[0]
    if sub_number_filter:
        subs = [s.strip() for s in sub_number_filter.split(",") if s.strip()]
        query["subscription_number"] = {"$in": subs} if len(subs) > 1 else {"$regex": _re.escape(subs[0]), "$options": "i"}
    if processor_id_filter:
        pids = [p.strip() for p in processor_id_filter.split(",") if p.strip()]
        query["processor_id"] = {"$in": pids} if len(pids) > 1 else {"$regex": _re.escape(pids[0]), "$options": "i"}
    if payment_method_filter:
        methods = [m.strip() for m in payment_method_filter.split(",") if m.strip()]
        query["payment_method"] = {"$in": methods} if len(methods) > 1 else methods[0]

    if pay_date_from:
        query.setdefault("payment_date", {})["$gte"] = pay_date_from
    if pay_date_to:
        query.setdefault("payment_date", {})["$lte"] = pay_date_to + "T23:59:59"

    # X-1: server-side creation date filter
    if created_from:
        query.setdefault("created_at", {})["$gte"] = created_from
    if created_to:
        query.setdefault("created_at", {})["$lte"] = created_to + "T23:59:59"

    # Partner filter: resolve partner codes → tenant IDs (platform admin only)
    if partner_filter and is_platform_admin(admin):
        codes = [c.strip().lower() for c in partner_filter.split(",") if c.strip()]
        if codes:
            partner_tenants = await db.tenants.find({"code": {"$in": codes}}, {"_id": 0, "id": 1}).to_list(200)
            partner_tenant_ids = [t["id"] for t in partner_tenants]
            query["tenant_id"] = {"$in": partner_tenant_ids} if partner_tenant_ids else {"$in": []}

    # X-2: server-side email/customer-name filter via customer lookup
    customer_id_constraints: Optional[set] = None
    if email_filter:
        emails = [e.strip().lower() for e in email_filter.split(",") if e.strip()]
        email_q = {"email": {"$in": emails} if len(emails) > 1 else {"$regex": _re.escape(emails[0]), "$options": "i"}}
        matching_users = await db.users.find(email_q, {"_id": 0, "id": 1}).to_list(500)
        mids = [u["id"] for u in matching_users]
        custs = await db.customers.find({"user_id": {"$in": mids}}, {"_id": 0, "id": 1}).to_list(500)
        customer_id_constraints = {c["id"] for c in custs}
    if customer_name_filter:
        names = [n.strip() for n in customer_name_filter.split(",") if n.strip()]
        name_q = {"full_name": {"$in": names} if len(names) > 1 else {"$regex": _re.escape(names[0]), "$options": "i"}}
        matching_users = await db.users.find(name_q, {"_id": 0, "id": 1}).to_list(500)
        mids = [u["id"] for u in matching_users]
        custs = await db.customers.find({"user_id": {"$in": mids}}, {"_id": 0, "id": 1}).to_list(500)
        name_cids = {c["id"] for c in custs}
        customer_id_constraints = (customer_id_constraints & name_cids) if customer_id_constraints is not None else name_cids
    if customer_id_constraints is not None:
        query["customer_id"] = {"$in": list(customer_id_constraints)}

    # C-2: product filter pre-pagination — add to query before count/skip/limit
    if product_filter:
        product_names = [n.strip() for n in product_filter.split(",") if n.strip()]
        products_all = await db.products.find(tf, {"_id": 0, "id": 1, "name": 1}).to_list(2000)
        product_ids_matching = [
            p["id"] for p in products_all
            if any(pn.lower() in p.get("name", "").lower() for pn in product_names)
        ]
        if product_ids_matching:
            matching_items = await db.order_items.find(
                {"product_id": {"$in": product_ids_matching}}, {"_id": 0, "order_id": 1}
            ).to_list(10000)
            matching_order_ids = list({i["order_id"] for i in matching_items})
            query["id"] = {"$in": matching_order_ids}
        else:
            query["id"] = {"$in": []}  # No matching products → empty result

    # X-3: normalise sort field (colKey alias → MongoDB field; fallback for un-sortable cols)
    sort_field = _ORDER_SORT_ALIASES.get(sort_by, sort_by)
    if sort_field not in _ORDER_SORTABLE_FIELDS:
        sort_field = "created_at"
    sort_direction = -1 if sort_order == "desc" else 1

    total_count = await db.orders.count_documents(query)
    orders = await db.orders.find(query, {"_id": 0}).sort(sort_field, sort_direction).skip(skip).limit(per_page).to_list(per_page)

    all_order_ids = [o["id"] for o in orders]
    items = await db.order_items.find({"order_id": {"$in": all_order_ids}}, {"_id": 0}).to_list(1000)

    orders = await enrich_partner_codes(orders, is_platform_admin(admin))
    return {
        "orders": orders,
        "items": items,
        "page": page,
        "per_page": per_page,
        "total": total_count,
        "total_pages": max(1, (total_count + per_page - 1) // per_page),
    }


@router.get("/admin/orders/{order_id}/logs")
async def get_order_logs(order_id: str, page: int = 1, limit: int = 20, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    order = await db.orders.find_one({**tf, "id": order_id}, {"_id": 0, "id": 1})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    flt = {"entity_type": "order", "entity_id": order_id}
    total = await db.audit_logs.count_documents(flt)
    skip = (page - 1) * limit
    logs = await db.audit_logs.find(flt, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"logs": logs, "total": total, "page": page, "limit": limit, "pages": max(1, (total + limit - 1) // limit)}


@router.post("/admin/orders/manual")
async def create_manual_order(
    payload: ManualOrderCreate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    tid = tenant_id_of(admin)
    await _check(admin, "create")
    user = await db.users.find_one({**tf, "email": payload.customer_email.lower()}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Customer not found")

    customer = await db.customers.find_one({**tf, "user_id": user["id"]}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer record not found")

    product = await db.products.find_one({**tf, "id": payload.product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # License enforcement: check monthly order limit
    from services.license_service import check_limit as _check_limit, increment_monthly as _inc_monthly
    _ord_check = await _check_limit(tid, "orders")
    if not _ord_check["allowed"]:
        raise HTTPException(
            status_code=403,
            detail=f"This organization has reached its monthly order limit ({_ord_check['current']}/{_ord_check['limit']}). Please contact support.",
        )

    order_id = make_id()
    order_number = f"AA-{order_id.split('-')[0].upper()}"
    # Tax amount: prefer explicitly provided value, fall back to calculated
    tax_amount = round_cents(payload.tax_amount) if payload.tax_amount is not None else (
        round_cents(payload.subtotal * float(payload.tax_rate) / 100) if payload.tax_rate else 0
    )
    total = round_cents(payload.subtotal - payload.discount + payload.fee + tax_amount)

    order_doc = {
        "id": order_id,
        "order_number": order_number,
        "customer_id": customer["id"],
        "tenant_id": tid,
        "type": "manual",
        "status": payload.status,
        "subtotal": round_cents(payload.subtotal),
        "discount_amount": round_cents(payload.discount),
        "fee": round_cents(payload.fee),
        "total": total,
        "currency": payload.currency or "USD",
        "payment_method": "manual",
        "internal_note": payload.internal_note or "",
        "tax_rate": payload.tax_rate,
        "tax_name": payload.tax_name,
        "tax_amount": round_cents(payload.tax_amount) if payload.tax_amount is not None else None,
        "order_date": payload.order_date,
        "payment_date": payload.payment_date,
        "created_at": now_iso(),
        "created_by_admin": admin["id"],
    }
    await db.orders.insert_one(order_doc)
    await _inc_monthly(tid, "orders")

    await db.order_items.insert_one({
        "id": make_id(),
        "order_id": order_id,
        "product_id": payload.product_id,
        "quantity": payload.quantity,
        "metadata_json": payload.inputs,
        "unit_price": round_cents(payload.subtotal / payload.quantity),
        "line_total": round_cents(payload.subtotal),
    })

    await db.zoho_sync_logs.insert_one({
        "id": make_id(),
        "entity_type": "manual_order",
        "entity_id": order_id,
        "status": "Sent" if payload.status == "paid" else "Pending",
        "last_error": None,
        "attempts": 1,
        "created_at": now_iso(),
        "mocked": True,
    })

    await create_audit_log(
        entity_type="order",
        entity_id=order_id,
        action="created_manual",
        actor=f"admin:{admin['id']}",
        details={"status": payload.status, "total": total, "payment_method": "manual"},
    )

    # Webhook: order.created
    customer = await db.customers.find_one({"id": order_doc["customer_id"]}, {"_id": 0}) or {}
    # email may live on users record; look it up as fallback
    _cust_email = customer.get("email", "")
    if not _cust_email and customer.get("user_id"):
        _user = await db.users.find_one({"id": customer["user_id"]}, {"_id": 0, "email": 1}) or {}
        _cust_email = _user.get("email", "")
    await dispatch_event("order.created", {
        "id": order_id,
        "order_number": order_doc["order_number"],
        "status": order_doc["status"],
        "total": total,
        "currency": order_doc["currency"],
        "customer_email": _cust_email,
        "customer_name": customer.get("full_name", ""),
        "product_names": product.get("name", payload.product_id) if product else payload.product_id,
        "items_count": 1,
        "payment_method": "manual",
        "created_at": order_doc["created_at"],
    }, tenant_id_of(admin))

    # Auto-sync to Zoho CRM (fire and forget)
    asyncio.create_task(auto_sync_to_zoho_crm(tid, "orders", order_doc, "create"))
    asyncio.create_task(auto_sync_to_zoho_books(tid, "orders", order_doc, "create"))

    return {"message": "Manual order created", "order_id": order_id, "order_number": order_number}


@router.put("/admin/orders/{order_id}")
async def update_order(
    order_id: str,
    payload: OrderUpdate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    await _check(admin, "edit")
    order = await db.orders.find_one({**tf, "id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if payload.status and payload.status not in ALLOWED_ORDER_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Allowed: {', '.join(ALLOWED_ORDER_STATUSES)}",
        )

    changes: Dict[str, Any] = {}
    update_fields: Dict[str, Any] = {}

    if payload.customer_id is not None:
        # Validate customer belongs to same tenant
        new_customer = await db.customers.find_one({**tf, "id": payload.customer_id}, {"_id": 0})
        if not new_customer:
            raise HTTPException(status_code=400, detail="Invalid customer_id - customer not found in your tenant")
        update_fields["customer_id"] = payload.customer_id
        changes["customer_id"] = {"old": order.get("customer_id"), "new": payload.customer_id}
    if payload.status is not None:
        update_fields["status"] = payload.status
        changes["status"] = {"old": order.get("status"), "new": payload.status}
    if payload.payment_method is not None:
        update_fields["payment_method"] = payload.payment_method
        changes["payment_method"] = {"old": order.get("payment_method"), "new": payload.payment_method}
    if payload.order_date is not None:
        update_fields["created_at"] = payload.order_date
        changes["order_date"] = {"old": order.get("created_at"), "new": payload.order_date}
    if payload.payment_date is not None:
        update_fields["payment_date"] = payload.payment_date
        changes["payment_date"] = {"old": order.get("payment_date"), "new": payload.payment_date}

    if payload.subtotal is not None:
        update_fields["subtotal"] = payload.subtotal
        # Auto-recalculate tax_amount when subtotal changes (preserves existing tax_rate)
        existing_tax_rate = order.get("tax_rate")
        if existing_tax_rate is not None:
            new_tax = round_cents(payload.subtotal * float(existing_tax_rate) / 100)
            update_fields["tax_amount"] = new_tax
    if payload.fee is not None:
        update_fields["fee"] = payload.fee
    if payload.total is not None:
        update_fields["total"] = payload.total
    if payload.currency is not None:
        update_fields["currency"] = payload.currency
        changes["currency"] = {"old": order.get("currency"), "new": payload.currency}

    if payload.subscription_id is not None:
        update_fields["subscription_id"] = payload.subscription_id
        changes["subscription_id"] = {"old": order.get("subscription_id"), "new": payload.subscription_id}
        # Auto-resolve subscription_number when subscription_id is set (tenant-scoped)
        if payload.subscription_id:
            linked_sub = await db.subscriptions.find_one({**tf, "id": payload.subscription_id}, {"_id": 0})
            if linked_sub and linked_sub.get("subscription_number"):
                update_fields["subscription_number"] = linked_sub["subscription_number"]

    if payload.processor_id is not None:
        update_fields["processor_id"] = payload.processor_id
        changes["processor_id"] = {"old": order.get("processor_id"), "new": payload.processor_id}

    if payload.product_id is not None:
        await db.order_items.update_one(
            {"order_id": order_id},
            {"$set": {"product_id": payload.product_id}},
        )
        changes["product_id"] = {"old": "previous", "new": payload.product_id}

    if payload.internal_note is not None:
        existing_note = order.get("internal_note", "")
        new_note = f"{existing_note}\n[{now_iso()}] {payload.internal_note}" if existing_note else payload.internal_note
        update_fields["internal_note"] = new_note

    if update_fields:
        update_fields["updated_at"] = now_iso()
        await db.orders.update_one({"id": order_id}, {"$set": update_fields})
        await create_audit_log(
            entity_type="order",
            entity_id=order_id,
            action="updated",
            actor=f"admin:{admin['id']}",
            details={"changes": changes},
        )
        # Webhook: order.updated + order.status_changed
        updated_order = await db.orders.find_one({"id": order_id}, {"_id": 0}) or {}
        customer = await db.customers.find_one({"id": updated_order.get("customer_id", "")}, {"_id": 0}) or {}
        await dispatch_event("order.updated", {
            "id": order_id,
            "order_number": updated_order.get("order_number", ""),
            "status": updated_order.get("status", ""),
            "total": updated_order.get("total", 0),
            "currency": updated_order.get("currency", ""),
            "customer_email": customer.get("email", ""),
            "customer_name": customer.get("full_name", ""),
            "updated_at": update_fields.get("updated_at", ""),
        }, tenant_id_of(admin))
        if "status" in changes:
            await dispatch_event("order.status_changed", {
                "id": order_id,
                "order_number": updated_order.get("order_number", ""),
                "previous_status": changes["status"]["old"],
                "new_status": changes["status"]["new"],
                "customer_email": customer.get("email", ""),
                "customer_name": customer.get("full_name", ""),
                "changed_at": update_fields.get("updated_at", ""),
            }, tenant_id_of(admin))
        
        # Auto-sync to Zoho CRM on update (fire and forget)
        asyncio.create_task(auto_sync_to_zoho_crm(tenant_id_of(admin), "orders", updated_order, "update"))
        asyncio.create_task(auto_sync_to_zoho_books(tenant_id_of(admin), "orders", updated_order, "update"))

    if payload.new_note:
        note_entry = {"text": payload.new_note, "timestamp": now_iso(), "actor": f"admin:{admin['id']}"}
        await db.orders.update_one({"id": order_id}, {"$push": {"notes": note_entry}})
        await create_audit_log(
            entity_type="order",
            entity_id=order_id,
            action="note_added",
            actor=f"admin:{admin['id']}",
            details={"note": payload.new_note},
        )

    return {"message": "Order updated successfully"}


@router.delete("/admin/orders/{order_id}")
async def delete_order(
    order_id: str,
    payload: OrderDelete,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    await _check(admin, "delete")
    order = await db.orders.find_one({**tf, "id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    await db.orders.update_one(
        {"id": order_id},
        {"$set": {"deleted_at": now_iso(), "deleted_by": admin["id"]}},
    )
    await create_audit_log(
        entity_type="order",
        entity_id=order_id,
        action="deleted",
        actor=f"admin:{admin['id']}",
        details={"reason": payload.reason or "No reason provided"},
    )
    return {"message": "Order deleted successfully"}


# ---------------------------------------------------------------------------
# Refunds
# ---------------------------------------------------------------------------

from pydantic import BaseModel
from services.refund_service import process_stripe_refund, process_gocardless_refund, record_refund


class RefundRequest(BaseModel):
    amount: Optional[float] = None  # Amount in currency units (e.g., 10.50). None = full refund
    reason: str = "requested_by_customer"
    provider: str  # "stripe", "gocardless", or "manual"
    process_via_provider: bool = True  # If True, actually process refund via provider


@router.post("/admin/orders/{order_id}/refund")
async def refund_order(
    order_id: str,
    payload: RefundRequest,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """
    Process a refund for an order.
    
    - provider: "stripe", "gocardless", or "manual"
    - amount: Amount to refund in currency units. Leave empty for full refund.
    - process_via_provider: If True, actually processes refund via payment provider.
                           If False, just records the refund locally.
    """
    tf = get_tenant_filter(admin)
    tid = tenant_id_of(admin)
    
    order = await db.orders.find_one({**tf, "id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.get("status") not in ("paid", "partially_refunded"):
        raise HTTPException(status_code=400, detail="Can only refund paid orders")
    
    # Calculate refund amount
    total_cents = int(order.get("total", 0) * 100)
    already_refunded_cents = int(order.get("refunded_amount", 0))
    available_to_refund = total_cents - already_refunded_cents
    
    if available_to_refund <= 0:
        raise HTTPException(status_code=400, detail="Order has already been fully refunded")
    
    if payload.amount:
        refund_amount_cents = int(payload.amount * 100)
        if refund_amount_cents > available_to_refund:
            raise HTTPException(
                status_code=400,
                detail=f"Refund amount exceeds available balance. Max refundable: {available_to_refund / 100:.2f}"
            )
    else:
        refund_amount_cents = available_to_refund
    
    provider_refund_id = None
    provider_response = None
    
    # Process via payment provider if requested
    if payload.process_via_provider and payload.provider != "manual":
        if payload.provider == "stripe":
            # Get Stripe payment ID from order
            processor_id = order.get("processor_id") or order.get("stripe_payment_intent_id")
            if not processor_id:
                raise HTTPException(
                    status_code=400,
                    detail="No Stripe payment ID found on this order. Use manual refund instead."
                )
            
            result = await process_stripe_refund(
                tenant_id=tid,
                payment_intent_id=processor_id,
                amount_cents=refund_amount_cents,
                reason=payload.reason
            )
            
            if not result["success"]:
                raise HTTPException(status_code=400, detail=result.get("error", "Stripe refund failed"))
            
            provider_refund_id = result.get("refund_id")
            provider_response = {
                "provider": "stripe",
                "refund_id": result.get("refund_id"),
                "status": result.get("status"),
                "message": f"Stripe refund {result.get('status', 'processed')} - ID: {result.get('refund_id', 'N/A')}"
            }
            
        elif payload.provider == "gocardless":
            # Get GoCardless payment ID from order
            gc_payment_id = order.get("gocardless_payment_id") or order.get("processor_id")
            if not gc_payment_id or not gc_payment_id.startswith("PM"):
                raise HTTPException(
                    status_code=400,
                    detail="No GoCardless payment ID found on this order. Use manual refund instead."
                )
            
            result = await process_gocardless_refund(
                tenant_id=tid,
                payment_id=gc_payment_id,
                amount_cents=refund_amount_cents,
                reference=f"Refund for order {order.get('order_number')}"
            )
            
            if not result["success"]:
                raise HTTPException(status_code=400, detail=result.get("error", "GoCardless refund failed"))
            
            provider_refund_id = result.get("refund_id")
            provider_response = {
                "provider": "gocardless",
                "refund_id": result.get("refund_id"),
                "status": result.get("status"),
                "message": f"GoCardless refund {result.get('status', 'submitted')} - ID: {result.get('refund_id', 'N/A')}"
            }
    
    # Record the refund
    refund_result = await record_refund(
        tenant_id=tid,
        order_id=order_id,
        amount_cents=refund_amount_cents,
        reason=payload.reason,
        provider=payload.provider,
        provider_refund_id=provider_refund_id,
        processed_by=f"admin:{admin['id']}"
    )
    
    # Audit log
    await create_audit_log(
        entity_type="order",
        entity_id=order_id,
        action="refunded",
        actor=f"admin:{admin['id']}",
        details={
            "amount": refund_amount_cents / 100,
            "reason": payload.reason,
            "provider": payload.provider,
            "provider_refund_id": provider_refund_id,
            "processed_via_provider": payload.process_via_provider
        }
    )
    
    # Dispatch webhook
    customer = await db.customers.find_one({"id": order["customer_id"]}, {"_id": 0}) or {}
    _cust_email = customer.get("email", "")
    _cust_name = ""
    if customer.get("user_id"):
        _user = await db.users.find_one({"id": customer["user_id"]}, {"_id": 0, "email": 1, "full_name": 1}) or {}
        _cust_email = _user.get("email", "") or _cust_email
        _cust_name = _user.get("full_name", "")
    
    await dispatch_event("order.refunded", {
        "id": order_id,
        "order_number": order.get("order_number", ""),
        "refund_amount": refund_amount_cents / 100,
        "total_refunded": (already_refunded_cents + refund_amount_cents) / 100,
        "reason": payload.reason,
        "provider": payload.provider,
        "customer_email": _cust_email,
        "refunded_at": now_iso()
    }, tid)
    
    # Send refund notification email to customer
    if _cust_email:
        from services.email_service import EmailService
        
        # Determine processing time based on provider
        processing_times = {
            "stripe": "5-10 business days",
            "gocardless": "3-5 business days",
            "manual": "As communicated by our support team"
        }
        processing_time = processing_times.get(payload.provider, "5-10 business days")
        
        # Format reason for display
        reason_labels = {
            "requested_by_customer": "Requested by customer",
            "duplicate": "Duplicate payment",
            "fraudulent": "Fraudulent transaction",
            "other": "Other"
        }
        
        await EmailService.send(
            trigger="refund_processed",
            recipient=_cust_email,
            variables={
                "customer_name": _cust_name or "Customer",
                "customer_email": _cust_email,
                "order_number": order.get("order_number", ""),
                "refund_amount": f"{refund_amount_cents / 100:.2f}",
                "refund_currency": order.get("currency", "$"),
                "refund_reason": reason_labels.get(payload.reason, payload.reason),
                "processing_time": processing_time,
                "payment_method": payload.provider.title()
            },
            db=db,
            tenant_id=tid
        )
    
    return {
        "message": "Refund processed successfully",
        "refund_id": refund_result["refund_id"],
        "amount": refund_amount_cents / 100,
        "provider": payload.provider,
        "provider_refund_id": provider_refund_id,
        "provider_response": provider_response
    }


@router.get("/admin/orders/{order_id}/refunds")
async def get_order_refunds(
    order_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """Get all refunds for an order."""
    tf = get_tenant_filter(admin)
    order = await db.orders.find_one({**tf, "id": order_id}, {"_id": 0, "id": 1})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    refunds = await db.refunds.find(
        {"order_id": order_id, "tenant_id": tenant_id_of(admin)},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    return {"refunds": refunds}


@router.get("/admin/orders/{order_id}/refund-providers")
async def get_refund_providers(
    order_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """
    Get available refund providers for an order.
    
    Returns providers based on:
    1. The original payment method used for the order
    2. Whether that payment provider is still active for the tenant
    """
    tf = get_tenant_filter(admin)
    order = await db.orders.find_one({**tf, "id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Get active payment settings
    app_settings = await db.app_settings.find(
        {"key": {"$in": ["stripe_enabled", "gocardless_enabled"]}},
        {"_id": 0, "key": 1, "value_json": 1}
    ).to_list(10)
    
    settings_map = {s["key"]: s.get("value_json", False) for s in app_settings}
    stripe_enabled = settings_map.get("stripe_enabled", False)
    gocardless_enabled = settings_map.get("gocardless_enabled", False)
    
    # Determine original payment method
    payment_method = order.get("payment_method", "")
    processor_id = order.get("processor_id", "") or ""
    gc_payment_id = order.get("gocardless_payment_id", "") or ""
    
    providers = []
    
    # Always allow manual refund
    providers.append({
        "id": "manual",
        "name": "Manual (Record Only)",
        "description": "Record refund without processing through payment provider",
        "available": True,
        "is_original": False
    })
    
    # Check if originally paid via Stripe
    is_stripe_order = (
        payment_method == "card" or
        processor_id.startswith("pi_") or
        processor_id.startswith("ch_") or
        order.get("stripe_payment_intent_id")
    )
    
    if is_stripe_order:
        providers.append({
            "id": "stripe",
            "name": "Stripe",
            "description": "Refund via Stripe API" if stripe_enabled else "Stripe is currently disabled",
            "available": stripe_enabled,
            "is_original": True,
            "processor_id": processor_id or order.get("stripe_payment_intent_id")
        })
    
    # Check if originally paid via GoCardless
    is_gocardless_order = (
        payment_method == "bank_transfer" or
        processor_id.startswith("PM") or
        gc_payment_id.startswith("PM")
    )
    
    if is_gocardless_order:
        providers.append({
            "id": "gocardless",
            "name": "GoCardless",
            "description": "Refund via GoCardless API" if gocardless_enabled else "GoCardless is currently disabled",
            "available": gocardless_enabled,
            "is_original": True,
            "processor_id": gc_payment_id or processor_id
        })
    
    # If neither Stripe nor GoCardless, it's likely a manual/offline order
    if not is_stripe_order and not is_gocardless_order:
        providers[0]["is_original"] = True  # Manual is original for offline orders
    
    return {
        "order_id": order_id,
        "original_payment_method": payment_method,
        "providers": providers
    }



@router.post("/admin/orders/{order_id}/auto-charge")
async def auto_charge_order(
    order_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    order = await db.orders.find_one({**get_tenant_filter(admin), "id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.get("status") == "paid":
        raise HTTPException(status_code=400, detail="Order is already paid")

    customer = await db.customers.find_one({**get_tenant_filter(admin), "id": order["customer_id"]}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    payment_method = order.get("payment_method")
    result: Dict[str, Any] = {"success": False, "message": ""}

    try:
        if payment_method == "card":
            result["message"] = "Card payment auto-charge requires Stripe Payment Intent setup. Please process manually or contact customer."
        elif payment_method == "bank_transfer":
            mandate_id = order.get("gocardless_mandate_id")
            if not mandate_id:
                result["message"] = "No GoCardless mandate found. Customer must complete Direct Debit setup first."
            else:
                payment = create_payment(
                    amount=order["total"],
                    currency=order.get("currency", "USD"),
                    mandate_id=mandate_id,
                    description=f"Auto-charge for Order {order['order_number']}",
                    metadata={"order_id": order["id"], "order_number": order["order_number"]},
                )
                if payment:
                    await db.orders.update_one(
                        {"id": order_id},
                        {"$set": {"status": "pending_payment", "gocardless_payment_id": payment["id"], "updated_at": now_iso()}},
                    )
                    result["success"] = True
                    result["message"] = f"Payment initiated with GoCardless. Payment ID: {payment['id']}"
                    result["payment_id"] = payment["id"]
                else:
                    result["message"] = "Failed to create GoCardless payment"
        else:
            result["message"] = f"Auto-charge not supported for payment method: {payment_method}"

        await create_audit_log(
            entity_type="order",
            entity_id=order_id,
            action="auto_charge_attempt",
            actor=f"admin:{admin['id']}",
            details={"result": result, "payment_method": payment_method},
        )
        return result

    except Exception as e:
        await create_audit_log(
            entity_type="order",
            entity_id=order_id,
            action="auto_charge_failed",
            actor=f"admin:{admin['id']}",
            details={"error": str(e), "payment_method": payment_method},
        )
        raise HTTPException(status_code=500, detail=f"Auto-charge failed: {str(e)}")


# ── Enquiries (scope requests) ────────────────────────────────────────────────

ENQUIRY_STATUSES = ["scope_pending", "scope_requested", "responded", "closed"]


@router.get("/admin/enquiries")
async def admin_enquiries(
    page: int = 1,
    per_page: int = 20,
    status_filter: Optional[str] = None,
    email_filter: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    query: Dict[str, Any] = {**tf, "type": "scope_request"}
    if status_filter:
        query["status"] = status_filter
    if date_from:
        query.setdefault("created_at", {})["$gte"] = date_from
    if date_to:
        query.setdefault("created_at", {})["$lte"] = date_to + "T23:59:59"

    # Push email filter down to MongoDB via customer lookup
    if email_filter:
        matching_users = await db.users.find(
            {"email": {"$regex": _re.escape(email_filter), "$options": "i"}},
            {"_id": 0, "id": 1},
        ).to_list(500)
        matching_user_ids = [u["id"] for u in matching_users]
        matching_customers = await db.customers.find(
            {"user_id": {"$in": matching_user_ids}},
            {"_id": 0, "id": 1},
        ).to_list(500)
        matching_customer_ids = [c["id"] for c in matching_customers]
        query["customer_id"] = {"$in": matching_customer_ids}

    total = await db.orders.count_documents(query)
    skip = (page - 1) * per_page
    orders_raw = await db.orders.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(per_page).to_list(per_page)

    # Enrich with customer/user data and order items
    customer_ids = list({o["customer_id"] for o in orders_raw if o.get("customer_id")})
    all_order_ids = [o["id"] for o in orders_raw]

    customers_list = await db.customers.find({"id": {"$in": customer_ids}}, {"_id": 0}).to_list(len(customer_ids) + 1)
    customer_map = {c["id"]: c for c in customers_list}

    user_ids = list({c.get("user_id") for c in customers_list if c.get("user_id")})
    users_list = await db.users.find({"id": {"$in": user_ids}}, {"_id": 0, "id": 1, "email": 1, "full_name": 1}).to_list(len(user_ids) + 1)
    user_map = {u["id"]: u for u in users_list}

    items_list = await db.order_items.find({"order_id": {"$in": all_order_ids}}, {"_id": 0}).to_list(per_page * 10)
    items_by_order: Dict[str, list] = {}
    for it in items_list:
        items_by_order.setdefault(it["order_id"], []).append(it)

    product_ids = list({it["product_id"] for it in items_list if it.get("product_id")})
    products_list = await db.products.find({"id": {"$in": product_ids}}, {"_id": 0, "id": 1, "name": 1}).to_list(len(product_ids) + 1)
    product_name_map = {p["id"]: p.get("name", p["id"]) for p in products_list}

    enquiries = []
    for o in orders_raw:
        cust = customer_map.get(o.get("customer_id", ""), {})
        usr = user_map.get(cust.get("user_id", ""), {})
        oi = items_by_order.get(o["id"], [])
        product_names = [product_name_map.get(i.get("product_id", ""), i.get("product_id", "")) for i in oi]

        enquiries.append({
            **o,
            "customer_email": usr.get("email", ""),
            "customer_name": usr.get("full_name") or cust.get("company_name", ""),
            "products": product_names,
            "partner_code": cust.get("partner_code") if is_platform_admin(admin) else None,
        })

    enquiries = await enrich_partner_codes(enquiries, is_platform_admin(admin))

    return {
        "enquiries": enquiries,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": max(1, (total + per_page - 1) // per_page),
    }


@router.patch("/admin/enquiries/{order_id}/status")
async def update_enquiry_status(
    order_id: str,
    payload: Dict[str, Any],
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    order = await db.orders.find_one({**tf, "id": order_id, "type": "scope_request"}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Enquiry not found")
    new_status = payload.get("status")
    if not new_status:
        raise HTTPException(status_code=400, detail="status is required")
    await db.orders.update_one({"id": order_id}, {"$set": {"status": new_status, "updated_at": now_iso()}})
    await create_audit_log(
        entity_type="order",
        entity_id=order_id,
        action="enquiry_status_updated",
        actor=admin.get("email", "admin"),
        details={"new_status": new_status, "order_number": order.get("order_number")},
    )
    updated_enq = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if updated_enq:
        asyncio.ensure_future(auto_sync_to_zoho_crm(order.get("tenant_id", ""), "enquiries", updated_enq, "update"))
    return {"message": "Status updated", "status": new_status}


@router.delete("/admin/enquiries/{order_id}")
async def delete_enquiry(order_id: str, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    order = await db.orders.find_one({**tf, "id": order_id, "type": "scope_request"}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Enquiry not found")
    await db.orders.delete_one({"id": order_id})
    await db.order_items.delete_many({"order_id": order_id})
    await create_audit_log(
        entity_type="order",
        entity_id=order_id,
        action="enquiry_deleted",
        actor=admin.get("email", "admin"),
        details={"order_number": order.get("order_number")},
    )
    return {"message": "Enquiry deleted"}


class ManualEnquiryCreate(BaseModel):
    customer_id: str
    product_id: Optional[str] = None
    form_id: Optional[str] = None
    form_data: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


@router.post("/admin/enquiries/manual")
async def create_manual_enquiry(
    payload: ManualEnquiryCreate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    # Resolve customer by id
    customer = await db.customers.find_one({**tf, "id": payload.customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Resolve user for email/name
    user = await db.users.find_one({"id": customer.get("user_id", "")}, {"_id": 0}) if customer.get("user_id") else None

    customer_email = (user or {}).get("email") or customer.get("email", "")
    customer_name = (user or {}).get("full_name") or customer.get("company_name", "")

    order_id = make_id()
    count = await db.orders.count_documents({**tf, "type": "scope_request"})
    order_number = f"ENQ-{(count + 1):04d}"

    product_name = None
    product_names: list = []
    if payload.product_id:
        product = await db.products.find_one({**tf, "id": payload.product_id}, {"_id": 0, "name": 1})
        if product:
            product_name = product.get("name")
            product_names = [product_name]

    # Build scope_form_data from submitted form values
    scope_form_data: Dict[str, Any] = {}
    if payload.form_data:
        scope_form_data.update(payload.form_data)
    if payload.notes:
        scope_form_data["notes"] = payload.notes

    doc = {
        "id": order_id,
        "order_number": order_number,
        "type": "scope_request",
        "pricing_type": "enquiry",
        "customer_id": customer.get("id"),
        "customer_email": customer_email,
        "customer_name": customer_name,
        "product_id": payload.product_id,
        "product_name": product_name,
        "products": product_names,
        "form_id": payload.form_id,
        "status": "scope_pending",
        "scope_form_data": scope_form_data,
        "notes": payload.notes or "",
        "created_at": now_iso(),
        "created_by": admin.get("email"),
        "manually_created": True,
    }
    set_tenant_id(doc, admin)
    await db.orders.insert_one(doc)
    doc.pop("_id", None)

    # Create order items if a product is linked
    if payload.product_id:
        await db.order_items.insert_one({
            "id": make_id(),
            "order_id": order_id,
            "product_id": payload.product_id,
            "quantity": 1,
            "unit_price": 0,
            "line_total": 0,
            "metadata_json": {},
        })

    await create_audit_log(
        entity_type="order",
        entity_id=order_id,
        action="manual_enquiry_created",
        actor=admin.get("email", "admin"),
        details={"order_number": order_number, "customer_id": payload.customer_id},
    )
    import asyncio as _asyncio
    _asyncio.ensure_future(auto_sync_to_zoho_crm(tenant_id_of(admin), "enquiries", doc, "create"))
    return {"message": "Enquiry created", "id": order_id, "order_number": order_number}

