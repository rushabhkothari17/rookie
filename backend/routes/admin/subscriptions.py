"""Admin: Subscription management routes."""
from __future__ import annotations

import asyncio
import re as _re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.helpers import make_id, now_iso
from core.security import require_admin
from core.tenant import get_tenant_filter, set_tenant_id, tenant_id_of, get_tenant_admin, is_platform_admin, enrich_partner_codes
from core.constants import ALLOWED_SUBSCRIPTION_STATUSES, ALLOWED_PAYMENT_METHODS, ALLOWED_ORDER_STATUSES, ALLOWED_BANK_TRANSACTION_STATUSES
from db.session import db
from models import SubscriptionUpdate, ManualSubscriptionCreate
from services.audit_service import create_audit_log
from services.webhook_service import dispatch_event
from services.zoho_service import auto_sync_to_zoho_crm, auto_sync_to_zoho_books

router = APIRouter(prefix="/api", tags=["admin-subscriptions"])


@router.get("/admin/filter-options")
async def get_filter_options(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Single source of truth for all admin filter dropdowns."""
    return {
        "order_statuses": ALLOWED_ORDER_STATUSES,
        "subscription_statuses": ALLOWED_SUBSCRIPTION_STATUSES,
        "payment_methods": ALLOWED_PAYMENT_METHODS,
        "bank_transaction_statuses": ALLOWED_BANK_TRANSACTION_STATUSES,
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
    query: Dict[str, Any] = {**tf}
    if status:
        query["status"] = status
    if payment:
        query["payment_method"] = payment
    if sub_number:
        query["subscription_number"] = {"$regex": _re.escape(sub_number), "$options": "i"}
    if processor_id_filter:
        query["processor_id"] = {"$regex": _re.escape(processor_id_filter), "$options": "i"}
    if plan_name_filter:
        query["plan_name"] = {"$regex": _re.escape(plan_name_filter), "$options": "i"}
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
    
    # Add email filter if provided
    if email:
        pipeline.append({
            "$match": {
                "user_data.email": {"$regex": _re.escape(email), "$options": "i"}
            }
        })
    
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
    
    # Add sort and pagination
    pipeline.append({"$sort": {sort_by: sort_dir}})
    skip = (page - 1) * per_page
    pipeline.append({"$skip": skip})
    pipeline.append({"$limit": per_page})
    
    subs = await enrich_partner_codes(list(subs), is_platform_admin(admin))

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
    user = await db.users.find_one({**tf, "email": payload.customer_email.lower()}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Customer not found")

    customer = await db.customers.find_one({**tf, "user_id": user["id"]}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer record not found")

    product = await db.products.find_one({**tf, "id": payload.product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

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
        "payment_method": "offline",
        "amount": payload.amount,
        "renewal_date": renewal_date_dt.isoformat(),
        "start_date": payload.start_date or now_iso(),
        "cancel_at_period_end": False,
        "canceled_at": None,
        "internal_note": payload.internal_note or "",
        "notes": [],
        "created_at": now_iso(),
        "created_by_admin": admin["id"],
        "is_manual": True,
        "contract_end_date": (
            datetime.fromisoformat(
                (payload.start_date or now_iso()).replace("Z", "+00:00")
            ).replace(tzinfo=timezone.utc) + timedelta(days=365)
        ).isoformat(),
    }
    await db.subscriptions.insert_one(sub_doc)

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
        "currency": "USD",
        "payment_method": subscription.get("payment_method", "manual"),
        "created_at": now_iso(),
        "created_by_admin": admin["id"],
    }
    await db.orders.insert_one(order_doc)

    current_renewal = datetime.fromisoformat(subscription["renewal_date"].replace("Z", "+00:00"))
    next_renewal = current_renewal + timedelta(days=30)

    await db.subscriptions.update_one(
        {"id": subscription_id},
        {"$set": {"renewal_date": next_renewal.isoformat(), "updated_at": now_iso()}},
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
        "next_renewal_date": next_renewal.isoformat(),
    }


@router.put("/admin/subscriptions/{subscription_id}")
async def update_subscription(
    subscription_id: str,
    payload: SubscriptionUpdate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    subscription = await db.subscriptions.find_one({**tf, "id": subscription_id}, {"_id": 0})
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    update_fields: Dict[str, Any] = {}
    changes: Dict[str, Any] = {}

    if payload.renewal_date is not None:
        update_fields["renewal_date"] = payload.renewal_date
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

    if payload.processor_id is not None:
        update_fields["processor_id"] = payload.processor_id
        changes["processor_id"] = {"old": subscription.get("processor_id"), "new": payload.processor_id}

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
    subscription = await db.subscriptions.find_one({**tf, "id": subscription_id}, {"_id": 0})
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

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
    await dispatch_event("subscription.cancelled", {
        "id": subscription_id,
        "subscription_number": subscription.get("subscription_number", ""),
        "plan_name": subscription.get("plan_name", ""),
        "cancel_reason": "Admin cancelled",
        "cancel_at_period_end": True,
        "customer_email": customer.get("email", ""),
        "customer_name": customer.get("full_name", ""),
        "cancelled_at": cancelled_at,
    }, tenant_id_of(admin))
    return {"message": "Subscription cancellation scheduled", "cancelled_at": cancelled_at}
