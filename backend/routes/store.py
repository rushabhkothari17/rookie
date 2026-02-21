"""Public store routes: categories, products, pricing, orders, subscriptions, scope requests."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.helpers import make_id, now_iso, round_cents, _deep_merge
from core.security import get_current_user, optional_get_current_user
from db.session import db
from models import (
    PricingCalcRequest, OrderPreviewRequest, CancelSubscriptionBody,
    ScopeRequestBody, ScopeRequestWithForm, ApplyPromoRequest,
)
from services.pricing_service import calculate_price
from services.checkout_service import build_order_items
from services.settings_service import SettingsService
from core.constants import SERVICE_FEE_RATE

router = APIRouter(prefix="/api", tags=["store"])


@router.get("/categories")
async def get_categories():
    inactive_cats = await db.categories.find({"is_active": False}, {"_id": 0, "name": 1}).to_list(500)
    inactive_names = {c["name"] for c in inactive_cats}
    all_cats = await db.categories.find({"is_active": True}, {"_id": 0, "name": 1, "description": 1}).to_list(500)
    cat_map = {c["name"]: c.get("description", "") for c in all_cats}
    products = await db.products.find({"is_active": True}, {"_id": 0, "category": 1}).to_list(1000)
    categories = sorted({
        p["category"] for p in products
        if p.get("category") and p["category"] not in inactive_names
    })
    blurbs = {name: cat_map.get(name, "") for name in categories}
    return {"categories": categories, "category_blurbs": blurbs}


@router.get("/products")
async def get_products(user: Optional[Dict[str, Any]] = Depends(optional_get_current_user)):
    inactive_cats = await db.categories.find({"is_active": False}, {"_id": 0, "name": 1}).to_list(500)
    inactive_cat_names = {c["name"] for c in inactive_cats}
    query: Dict[str, Any] = {"is_active": True}
    if inactive_cat_names:
        query["category"] = {"$nin": list(inactive_cat_names)}
    all_products = await db.products.find(query, {"_id": 0}).to_list(1000)

    if user:
        customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
        customer_id = customer["id"] if customer else None
    else:
        customer_id = None

    def is_visible(p: Dict) -> bool:
        vis = p.get("visible_to_customers", [])
        if not vis:
            return True
        return customer_id in vis if customer_id else False

    products = [p for p in all_products if is_visible(p)]
    return {"products": products}


@router.get("/products/{product_id}")
async def get_product(product_id: str):
    product = await db.products.find_one({"id": product_id, "is_active": True}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"product": product}


@router.post("/pricing/calc")
async def pricing_calc(
    payload: PricingCalcRequest,
    user: Dict[str, Any] = Depends(get_current_user),
):
    product = await db.products.find_one({"id": payload.product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    result = calculate_price(product, payload.inputs)
    return {"product_id": product["id"], **result}


@router.get("/terms")
async def get_all_terms():
    terms = await db.terms_and_conditions.find({}, {"_id": 0}).to_list(100)
    return {"terms": terms}


@router.get("/terms/{terms_id}")
async def get_single_terms(terms_id: str):
    terms = await db.terms_and_conditions.find_one({"id": terms_id}, {"_id": 0})
    if not terms:
        raise HTTPException(status_code=404, detail="Terms not found")
    return {"terms": terms}


@router.post("/promo-codes/validate")
async def validate_promo_code(
    payload: ApplyPromoRequest,
    user: Dict[str, Any] = Depends(get_current_user),
):
    code = await db.promo_codes.find_one({"code": payload.code.upper()}, {"_id": 0})
    if not code:
        raise HTTPException(status_code=404, detail="Invalid promo code")
    if not code.get("enabled"):
        raise HTTPException(status_code=400, detail="Promo code is not active")
    now_str = datetime.now(timezone.utc).isoformat()
    if code.get("expiry_date") and code["expiry_date"] < now_str:
        raise HTTPException(status_code=400, detail="Promo code has expired")
    if code.get("max_uses") and code.get("usage_count", 0) >= code["max_uses"]:
        raise HTTPException(status_code=400, detail="Promo code usage limit reached")
    checkout_type = payload.checkout_type
    applies_to = code.get("applies_to", "both")
    if applies_to == "one-time" and checkout_type == "subscription":
        raise HTTPException(status_code=400, detail="Promo code only valid for one-time purchases")
    if applies_to == "subscription" and checkout_type == "one_time":
        raise HTTPException(status_code=400, detail="Promo code only valid for subscriptions")
    if code.get("one_time_code"):
        customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
        if customer:
            used = await db.orders.find_one({"customer_id": customer["id"], "promo_code": code["code"]}, {"_id": 0})
            if used:
                raise HTTPException(status_code=400, detail="You have already used this promo code")
    return {"valid": True, "code": code["code"], "discount_type": code["discount_type"], "discount_value": code["discount_value"]}


@router.post("/orders/preview")
async def orders_preview(
    payload: OrderPreviewRequest,
    user: Dict[str, Any] = Depends(get_current_user),
):
    fee_rate = float(await SettingsService.get("service_fee_rate", SERVICE_FEE_RATE))
    customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
    customer_id = customer["id"] if customer else None
    results = []
    for item in payload.items:
        product = await db.products.find_one({"id": item.product_id}, {"_id": 0})
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        pricing = calculate_price(product, item.inputs, fee_rate=fee_rate)
        results.append({"product_id": item.product_id, "product_name": product["name"], **pricing})
    return {"items": results}


@router.post("/orders/scope-request")
async def scope_request(
    payload: ScopeRequestBody,
    user: Dict[str, Any] = Depends(get_current_user),
):
    customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    order_items = await build_order_items(payload.items)
    scope_items = [i for i in order_items if i["pricing"].get("is_scope_request")]
    if not scope_items:
        raise HTTPException(status_code=400, detail="No scope request items found")

    order_id = make_id()
    order_number = f"AA-{order_id.split('-')[0].upper()}"
    subtotal = sum(i["pricing"]["subtotal"] for i in scope_items)
    order_doc = {
        "id": order_id,
        "order_number": order_number,
        "customer_id": customer["id"],
        "type": "scope_request",
        "status": "scope_requested",
        "subtotal": round_cents(subtotal),
        "fee": 0.0,
        "total": round_cents(subtotal),
        "currency": customer.get("currency"),
        "payment_method": "scope_request",
        "notes_json": {
            "product_intake": {item["product"]["id"]: item.get("inputs", {}) for item in scope_items},
            "payment": {"method": "scope_request"},
            "system_metadata": {"user_id": user["id"], "customer_id": customer["id"], "timestamp": now_iso()},
        },
        "created_at": now_iso(),
    }
    await db.orders.insert_one(order_doc)
    for item in scope_items:
        product = item["product"]
        await db.order_items.insert_one({
            "id": make_id(),
            "order_id": order_id,
            "product_id": product["id"],
            "quantity": item["quantity"],
            "metadata_json": item["inputs"],
            "unit_price": item["pricing"]["subtotal"],
            "line_total": item["pricing"]["subtotal"],
        })
    await db.zoho_sync_logs.insert_one({
        "id": make_id(),
        "entity_type": "deal",
        "entity_id": order_id,
        "status": "Not Sent",
        "last_error": None,
        "attempts": 0,
        "created_at": now_iso(),
        "mocked": True,
    })
    return {"message": "Scope request created", "order_id": order_id, "order_number": order_number}


@router.post("/orders/scope-request-form")
async def create_scope_request_with_form(
    payload: ScopeRequestWithForm,
    user: Dict[str, Any] = Depends(get_current_user),
):
    customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    order_id = make_id()
    order_number = f"AA-{order_id[:8].upper()}"
    order_items = []
    for item in payload.items:
        product = await db.products.find_one({"id": item.product_id}, {"_id": 0})
        if not product:
            continue
        order_items.append({
            "id": make_id(),
            "order_id": order_id,
            "product_id": item.product_id,
            "quantity": item.quantity,
            "inputs": item.inputs,
            "unit_price": 0,
            "subtotal": 0,
        })
    order = {
        "id": order_id,
        "order_number": order_number,
        "customer_id": customer["id"],
        "type": "scope_request",
        "status": "scope_pending",
        "subtotal": 0,
        "fee": 0,
        "total": 0,
        "currency": customer.get("currency", "USD"),
        "payment_method": None,
        "scope_form_data": {
            "project_summary": payload.form_data.project_summary,
            "desired_outcomes": payload.form_data.desired_outcomes,
            "apps_involved": payload.form_data.apps_involved,
            "timeline_urgency": payload.form_data.timeline_urgency,
            "budget_range": payload.form_data.budget_range or "",
            "additional_notes": payload.form_data.additional_notes or "",
        },
        "notes_json": _deep_merge(
            {
                "product_intake": {item.product_id: dict(item.inputs) for item in payload.items},
                "payment": {"method": "scope_request_form"},
                "system_metadata": {"user_id": user["id"], "customer_id": customer["id"], "timestamp": now_iso()},
            },
            {
                "scope_form": {
                    "project_summary": payload.form_data.project_summary,
                    "desired_outcomes": payload.form_data.desired_outcomes,
                    "apps_involved": payload.form_data.apps_involved,
                    "timeline_urgency": payload.form_data.timeline_urgency,
                    "budget_range": payload.form_data.budget_range or "",
                    "additional_notes": payload.form_data.additional_notes or "",
                }
            },
        ),
        "created_at": now_iso(),
    }
    await db.orders.insert_one(order)
    for item in order_items:
        await db.order_items.insert_one(item)

    product_names = []
    for item in payload.items:
        p = await db.products.find_one({"id": item.product_id}, {"_id": 0})
        if p:
            product_names.append(p.get("name", item.product_id))

    email_body = f"""
New Scope Request from {user.get('full_name', 'Unknown')}

Customer: {user.get('full_name', 'Unknown')}
Email: {user.get('email', 'Unknown')}
Company: {customer.get('company_name', 'Unknown')}

Products: {', '.join(product_names)}

PROJECT DETAILS:
----------------
Project Summary: {payload.form_data.project_summary}

Desired Outcomes: {payload.form_data.desired_outcomes}

Apps Involved: {payload.form_data.apps_involved}

Timeline/Urgency: {payload.form_data.timeline_urgency}

Budget Range: {payload.form_data.budget_range or 'Not specified'}

Additional Notes: {payload.form_data.additional_notes or 'None'}

Order/Deal ID: {order_number}
"""
    await db.email_outbox.insert_one({
        "id": make_id(),
        "to": "rushabh@automateaccounts.com",
        "subject": f"New Scope Request: {order_number} from {user.get('full_name', 'Customer')}",
        "body": email_body,
        "type": "scope_request",
        "status": "MOCKED",
        "created_at": now_iso(),
    })
    await db.zoho_sync_logs.insert_one({
        "id": make_id(),
        "entity_type": "scope_request",
        "entity_id": order_id,
        "action": "create_deal",
        "status": "Sent",
        "last_error": None,
        "attempts": 1,
        "created_at": now_iso(),
        "mocked": True,
    })
    return {
        "message": "Scope request submitted",
        "order_id": order_id,
        "order_number": order_number,
        "email_sent_to": "rushabh@automateaccounts.com",
        "email_delivery": "MOCKED",
    }


@router.get("/orders")
async def get_orders(user: Dict[str, Any] = Depends(get_current_user)):
    customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    orders = await db.orders.find({"customer_id": customer["id"]}, {"_id": 0}).to_list(500)
    order_ids = [o["id"] for o in orders]
    items = await db.order_items.find({"order_id": {"$in": order_ids}}, {"_id": 0}).to_list(1000)
    return {"orders": orders, "items": items}


@router.get("/orders/{order_id}")
async def get_order(order_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    items = await db.order_items.find({"order_id": order_id}, {"_id": 0}).to_list(200)
    return {"order": order, "items": items}


@router.get("/subscriptions")
async def get_subscriptions(user: Dict[str, Any] = Depends(get_current_user)):
    customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    subs = await db.subscriptions.find({"customer_id": customer["id"]}, {"_id": 0}).to_list(200)
    return {"subscriptions": subs}


@router.post("/subscriptions/{subscription_id}/cancel")
async def cancel_subscription(
    subscription_id: str,
    payload: CancelSubscriptionBody,
    user: Dict[str, Any] = Depends(get_current_user),
):
    subscription = await db.subscriptions.find_one({"id": subscription_id}, {"_id": 0})
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    await db.subscriptions.update_one(
        {"id": subscription_id},
        {"$set": {"cancel_at_period_end": True, "status": "canceled_pending", "canceled_at": now_iso()}},
    )
    await db.email_outbox.insert_one({
        "id": make_id(),
        "to": user["email"],
        "subject": "Cancellation requested",
        "body": "Your subscription will cancel at the end of the billing period.",
        "type": "cancellation",
        "status": "MOCKED",
        "created_at": now_iso(),
    })
    return {"message": "Cancellation scheduled"}
