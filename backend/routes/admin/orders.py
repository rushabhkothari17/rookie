"""Admin: Order management routes."""
from __future__ import annotations

import re as _re
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.helpers import make_id, now_iso, round_cents
from core.security import require_admin
from core.tenant import get_tenant_filter, set_tenant_id, tenant_id_of, get_tenant_admin
from core.constants import ALLOWED_ORDER_STATUSES
from db.session import db
from models import OrderUpdate, OrderDelete, ManualOrderCreate
from services.audit_service import create_audit_log
from services.webhook_service import dispatch_event
from gocardless_helper import create_payment

router = APIRouter(prefix="/api", tags=["admin-orders"])


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
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    skip = (page - 1) * per_page
    tf = get_tenant_filter(admin)
    query: Dict[str, Any] = {**tf}
    if not include_deleted:
        query["deleted_at"] = {"$exists": False}
    if order_number_filter:
        query["order_number"] = {"$regex": _re.escape(order_number_filter), "$options": "i"}
    if status_filter:
        query["status"] = status_filter
    if sub_number_filter:
        query["subscription_number"] = {"$regex": _re.escape(sub_number_filter), "$options": "i"}
    if processor_id_filter:
        query["processor_id"] = {"$regex": _re.escape(processor_id_filter), "$options": "i"}
    if payment_method_filter:
        query["payment_method"] = payment_method_filter
    if pay_date_from:
        query.setdefault("payment_date", {})["$gte"] = pay_date_from
    if pay_date_to:
        query.setdefault("payment_date", {})["$lte"] = pay_date_to + "T23:59:59"

    sort_direction = -1 if sort_order == "desc" else 1
    orders = await db.orders.find(query, {"_id": 0}).sort(sort_by, sort_direction).skip(skip).limit(per_page).to_list(per_page)

    if product_filter:
        order_ids = [o["id"] for o in orders]
        items = await db.order_items.find({"order_id": {"$in": order_ids}}, {"_id": 0}).to_list(1000)
        products = await db.products.find(tf, {"_id": 0}).to_list(1000)
        product_ids_matching = [p["id"] for p in products if product_filter.lower() in p.get("name", "").lower()]
        matching_order_ids = {i["order_id"] for i in items if i["product_id"] in product_ids_matching}
        orders = [o for o in orders if o["id"] in matching_order_ids]

    all_order_ids = [o["id"] for o in orders]
    items = await db.order_items.find({"order_id": {"$in": all_order_ids}}, {"_id": 0}).to_list(1000)
    total_count = await db.orders.count_documents(query)

    return {
        "orders": orders,
        "items": items,
        "page": page,
        "per_page": per_page,
        "total": total_count,
        "total_pages": max(1, (total_count + per_page - 1) // per_page),
    }


@router.get("/admin/orders/{order_id}/logs")
async def get_order_logs(order_id: str, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    order = await db.orders.find_one({**tf, "id": order_id}, {"_id": 0, "id": 1})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    logs = await db.audit_logs.find(
        {"entity_type": "order", "entity_id": order_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return {"logs": logs}


@router.post("/admin/orders/manual")
async def create_manual_order(
    payload: ManualOrderCreate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    tid = tenant_id_of(admin)
    user = await db.users.find_one({**tf, "email": payload.customer_email.lower()}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Customer not found")

    customer = await db.customers.find_one({**tf, "user_id": user["id"]}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer record not found")

    product = await db.products.find_one({**tf, "id": payload.product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    order_id = make_id()
    order_number = f"AA-{order_id.split('-')[0].upper()}"
    total = round_cents(payload.subtotal - payload.discount + payload.fee)

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
        "currency": customer.get("currency", "USD"),
        "payment_method": "offline",
        "internal_note": payload.internal_note or "",
        "created_at": now_iso(),
        "created_by_admin": admin["id"],
    }
    await db.orders.insert_one(order_doc)

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
        details={"status": payload.status, "total": total, "payment_method": "offline"},
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
        "payment_method": "offline",
        "created_at": order_doc["created_at"],
    }, tenant_id_of(admin))

    return {"message": "Manual order created", "order_id": order_id, "order_number": order_number}


@router.put("/admin/orders/{order_id}")
async def update_order(
    order_id: str,
    payload: OrderUpdate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
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
    if payload.fee is not None:
        update_fields["fee"] = payload.fee
    if payload.total is not None:
        update_fields["total"] = payload.total

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
    if not _cust_email and customer.get("user_id"):
        _user = await db.users.find_one({"id": customer["user_id"]}, {"_id": 0, "email": 1}) or {}
        _cust_email = _user.get("email", "")
    
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
    
    return {
        "message": "Refund processed successfully",
        "refund_id": refund_result["refund_id"],
        "amount": refund_amount_cents / 100,
        "provider": payload.provider,
        "provider_refund_id": provider_refund_id
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
