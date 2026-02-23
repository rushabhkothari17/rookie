"""Admin: Order management routes."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.helpers import make_id, now_iso, round_cents
from core.security import require_admin
from core.tenant import get_tenant_filter, set_tenant_id, tenant_id_of
from core.constants import ALLOWED_ORDER_STATUSES
from db.session import db
from models import OrderUpdate, OrderDelete, ManualOrderCreate
from services.audit_service import create_audit_log
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
    admin: Dict[str, Any] = Depends(require_admin),
):
    skip = (page - 1) * per_page
    tf = get_tenant_filter(admin)
    query: Dict[str, Any] = {**tf}
    if not include_deleted:
        query["deleted_at"] = {"$exists": False}
    if order_number_filter:
        query["order_number"] = {"$regex": order_number_filter, "$options": "i"}
    if status_filter:
        query["status"] = status_filter
    if sub_number_filter:
        query["subscription_number"] = {"$regex": sub_number_filter, "$options": "i"}
    if processor_id_filter:
        query["processor_id"] = {"$regex": processor_id_filter, "$options": "i"}
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
async def get_order_logs(order_id: str, admin: Dict[str, Any] = Depends(require_admin)):
    logs = await db.audit_logs.find(
        {"entity_type": "order", "entity_id": order_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return {"logs": logs}


@router.post("/admin/orders/manual")
async def create_manual_order(
    payload: ManualOrderCreate,
    admin: Dict[str, Any] = Depends(require_admin),
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

    return {"message": "Manual order created", "order_id": order_id, "order_number": order_number}


@router.put("/admin/orders/{order_id}")
async def update_order(
    order_id: str,
    payload: OrderUpdate,
    admin: Dict[str, Any] = Depends(require_admin),
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
        # Auto-resolve subscription_number when subscription_id is set
        if payload.subscription_id:
            linked_sub = await db.subscriptions.find_one({"id": payload.subscription_id}, {"_id": 0})
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
    admin: Dict[str, Any] = Depends(require_admin),
):
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
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


@router.post("/admin/orders/{order_id}/auto-charge")
async def auto_charge_order(
    order_id: str,
    admin: Dict[str, Any] = Depends(require_admin),
):
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.get("status") == "paid":
        raise HTTPException(status_code=400, detail="Order is already paid")

    customer = await db.customers.find_one({"id": order["customer_id"]}, {"_id": 0})
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
