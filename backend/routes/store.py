"""Public store routes: categories, products, pricing, orders, subscriptions, scope requests."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Header

from core.helpers import make_id, now_iso, round_cents, _deep_merge
from core.security import get_current_user, optional_get_current_user
from core.tenant import DEFAULT_TENANT_ID, resolve_api_key_tenant, is_platform_admin
from db.session import db
from models import (
    PricingCalcRequest, OrderPreviewRequest, CancelSubscriptionBody,
    ScopeRequestBody, ScopeRequestWithForm, ApplyPromoRequest,
)
from services.pricing_service import calculate_price
from services.checkout_service import build_order_items
from services.settings_service import SettingsService
from services.audit_service import create_audit_log
from core.constants import SERVICE_FEE_RATE

router = APIRouter(prefix="/api", tags=["store"])


async def get_stripe_fee_rate(tenant_id: str) -> float:
    """Get Stripe fee rate from oauth_connections, fallback to SERVICE_FEE_RATE."""
    conn = await db.oauth_connections.find_one(
        {"tenant_id": tenant_id, "provider": "stripe", "is_validated": True},
        {"_id": 0, "settings": 1}
    )
    if conn:
        settings = conn.get("settings", {})
        return float(settings.get("fee_rate", SERVICE_FEE_RATE))
    return SERVICE_FEE_RATE


async def _resolve_tenant_id(user: Optional[Dict[str, Any]] = None, partner_code: Optional[str] = None, x_view_as_tenant: Optional[str] = None, api_key_tid: Optional[str] = None) -> str:
    """Resolve tenant_id: X-View-As-Tenant (platform_admin) > user JWT > API key > partner_code lookup > default."""
    if x_view_as_tenant and user and user.get("role") == "platform_admin":
        return x_view_as_tenant
    if user and user.get("tenant_id"):
        return user["tenant_id"]
    if api_key_tid:
        return api_key_tid
    if partner_code:
        # Look up tenant by code to get actual tenant_id
        tenant = await db.tenants.find_one({"code": partner_code.lower()}, {"_id": 0, "id": 1})
        if tenant:
            return tenant["id"]
    return DEFAULT_TENANT_ID


async def _resolve_store_tenant_id(user: Optional[Dict[str, Any]] = None, partner_code: Optional[str] = None, api_key_tid: Optional[str] = None) -> Optional[str]:
    """Resolve tenant_id for public store listing pages.
    Returns None for platform admins (no tenant filter = show all).
    Intentionally ignores X-View-As-Tenant so the admin impersonation header does not
    bleed into public-facing store queries."""
    if user and is_platform_admin(user):
        return None  # platform admin sees all data across all tenants
    if user and user.get("tenant_id"):
        return user["tenant_id"]
    if api_key_tid:
        return api_key_tid
    if partner_code:
        tenant = await db.tenants.find_one({"code": partner_code.lower()}, {"_id": 0, "id": 1})
        if tenant:
            return tenant["id"]
    return DEFAULT_TENANT_ID


@router.get("/categories")
async def get_categories(
    partner_code: Optional[str] = None,
    user: Optional[Dict[str, Any]] = Depends(optional_get_current_user),
    x_view_as_tenant: Optional[str] = Header(default=None, alias="X-View-As-Tenant"),
    api_key_tid: Optional[str] = Depends(resolve_api_key_tenant),
):
    tid = await _resolve_store_tenant_id(user, partner_code, api_key_tid)
    tf: Dict[str, Any] = {"tenant_id": tid} if tid else {}
    inactive_cats = await db.categories.find({**tf, "is_active": False}, {"_id": 0, "name": 1}).to_list(500)
    inactive_names = {c["name"] for c in inactive_cats}
    all_cats = await db.categories.find({**tf, "is_active": True}, {"_id": 0, "name": 1, "description": 1}).to_list(500)
    cat_map = {c["name"]: c.get("description", "") for c in all_cats}
    products = await db.products.find({**tf, "is_active": True}, {"_id": 0, "category": 1}).to_list(1000)
    categories = sorted({
        p["category"] for p in products
        if p.get("category") and p["category"] not in inactive_names
    })
    blurbs = {name: cat_map.get(name, "") for name in categories}
    return {"categories": categories, "category_blurbs": blurbs}


@router.get("/products")
def _eval_product_conditions(rule_set: dict, customer: dict) -> bool:
    """Evaluate ProductVisRuleSet conditions against a customer document."""
    conditions = rule_set.get("conditions") or []
    if not conditions:
        return True
    logic = rule_set.get("logic", "AND")
    results = []
    for cond in conditions:
        field = cond.get("field", "")
        operator = cond.get("operator", "equals")
        expected = str(cond.get("value", "") or "")
        actual = (customer or {}).get(field)
        actual_str = str(actual or "").lower() if actual is not None else ""
        if operator == "equals":
            r = actual_str == expected.lower()
        elif operator == "not_equals":
            r = actual_str != expected.lower()
        elif operator == "contains":
            r = expected.lower() in actual_str
        elif operator == "not_contains":
            r = expected.lower() not in actual_str
        elif operator == "empty":
            r = not actual or actual in ("", [], {})
        elif operator == "not_empty":
            r = bool(actual) and actual not in ("", [], {})
        else:
            r = True
        results.append(r)
    return any(results) if logic == "OR" else all(results)


async def get_products(
    partner_code: Optional[str] = None,
    user: Optional[Dict[str, Any]] = Depends(optional_get_current_user),
    x_view_as_tenant: Optional[str] = Header(default=None, alias="X-View-As-Tenant"),
    api_key_tid: Optional[str] = Depends(resolve_api_key_tenant),
):
    tid = await _resolve_store_tenant_id(user, partner_code, api_key_tid)
    tf: Dict[str, Any] = {"tenant_id": tid} if tid else {}
    inactive_cats = await db.categories.find({**tf, "is_active": False}, {"_id": 0, "name": 1}).to_list(500)
    inactive_cat_names = {c["name"] for c in inactive_cats}
    query: Dict[str, Any] = {**tf, "is_active": True}
    if inactive_cat_names:
        query["category"] = {"$nin": list(inactive_cat_names)}
    all_products = await db.products.find(query, {"_id": 0}).to_list(1000)

    if user:
        customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
        customer_id = customer["id"] if customer else None
        # Admins always see all active products
        is_admin = user.get("is_admin", False)
    else:
        customer = None
        customer_id = None
        is_admin = False

    def is_visible(p: Dict) -> bool:
        # Admins see everything
        if is_admin:
            return True
        whitelist = p.get("visible_to_customers", [])
        blacklist = p.get("restricted_to", [])
        vis_cond = p.get("visibility_conditions")
        # Whitelist mode: show only to specific customers
        if whitelist:
            return customer_id in whitelist if customer_id else False
        # Blacklist mode: hide from specific customers
        if blacklist:
            return customer_id not in blacklist
        # Conditional mode: evaluate customer-field conditions
        if vis_cond and vis_cond.get("conditions"):
            cust_doc = (customer or {}) if customer else {}
            return _eval_product_conditions(vis_cond, cust_doc)
        # Default: visible to everyone
        return True

    products = [p for p in all_products if is_visible(p)]
    return {"products": products}


@router.get("/products/{product_id}")
async def get_product(
    product_id: str,
    user: Optional[Dict[str, Any]] = Depends(optional_get_current_user),
    x_view_as_tenant: Optional[str] = Header(default=None, alias="X-View-As-Tenant"),
):
    tid = await _resolve_store_tenant_id(user, None)
    tf: Dict[str, Any] = {"tenant_id": tid} if tid else {}
    product = await db.products.find_one({**tf, "id": product_id, "is_active": True}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    # Enforce visibility rules
    if user:
        customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
        cid = customer["id"] if customer else None
        is_admin = user.get("is_admin", False)
        if not is_admin:
            whitelist = product.get("visible_to_customers", [])
            blacklist = product.get("restricted_to", [])
            vis_cond = product.get("visibility_conditions")
            if whitelist and (not cid or cid not in whitelist):
                raise HTTPException(status_code=404, detail="Product not found")
            if blacklist and cid and cid in blacklist:
                raise HTTPException(status_code=404, detail="Product not found")
            if vis_cond and vis_cond.get("conditions") and not whitelist and not blacklist:
                cust_doc = customer or {}
                if not _eval_product_conditions(vis_cond, cust_doc):
                    raise HTTPException(status_code=404, detail="Product not found")
    return {"product": product}


@router.post("/pricing/calc")
async def pricing_calc(
    payload: PricingCalcRequest,
    user: Dict[str, Any] = Depends(get_current_user),
    x_view_as_tenant: Optional[str] = Header(default=None, alias="X-View-As-Tenant"),
):
    tid = await _resolve_store_tenant_id(user, None)
    tf: Dict[str, Any] = {"tenant_id": tid} if tid else {}
    product = await db.products.find_one({**tf, "id": payload.product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    # Product page shows base price without card processing fee
    # (fee is only added at checkout when user selects card payment)
    result = calculate_price(product, payload.inputs, fee_rate=0.0)
    return {"product_id": product["id"], **result}


@router.get("/terms")
async def get_all_terms(
    partner_code: Optional[str] = None,
    user: Optional[Dict[str, Any]] = Depends(optional_get_current_user),
    x_view_as_tenant: Optional[str] = Header(default=None, alias="X-View-As-Tenant"),
    api_key_tid: Optional[str] = Depends(resolve_api_key_tenant),
):
    tid = await _resolve_tenant_id(user, partner_code, x_view_as_tenant, api_key_tid)
    terms = await db.terms_and_conditions.find({"tenant_id": tid}, {"_id": 0}).to_list(100)
    return {"terms": terms}


@router.get("/terms/default")
async def get_default_terms(
    partner_code: Optional[str] = None,
    user: Optional[Dict[str, Any]] = Depends(optional_get_current_user),
    x_view_as_tenant: Optional[str] = Header(default=None, alias="X-View-As-Tenant"),
    api_key_tid: Optional[str] = Depends(resolve_api_key_tenant),
):
    """Get the default terms and conditions for the current tenant."""
    tid = await _resolve_tenant_id(user, partner_code, x_view_as_tenant, api_key_tid)
    terms = await db.terms_and_conditions.find_one(
        {"tenant_id": tid, "is_default": True, "status": "active"}, 
        {"_id": 0}
    )
    if not terms:
        raise HTTPException(status_code=404, detail="Terms not found")
    return terms


@router.get("/terms/{terms_id}")
async def get_single_terms(
    terms_id: str,
    user: Optional[Dict[str, Any]] = Depends(optional_get_current_user),
    x_view_as_tenant: Optional[str] = Header(default=None, alias="X-View-As-Tenant"),
):
    tid = await _resolve_tenant_id(user, None, x_view_as_tenant)
    terms = await db.terms_and_conditions.find_one({"tenant_id": tid, "id": terms_id}, {"_id": 0})
    if not terms:
        raise HTTPException(status_code=404, detail="Terms not found")
    return {"terms": terms}


@router.post("/promo-codes/validate")
async def validate_promo_code(
    payload: ApplyPromoRequest,
    user: Dict[str, Any] = Depends(get_current_user),
):
    tid = user.get("tenant_id") or DEFAULT_TENANT_ID
    code = await db.promo_codes.find_one({"tenant_id": tid, "code": payload.code.upper()}, {"_id": 0})
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
    # Check product-scope restriction
    if code.get("applies_to_products") == "selected" and payload.product_ids:
        eligible_ids = code.get("product_ids", [])
        if not all(pid in eligible_ids for pid in payload.product_ids):
            raise HTTPException(status_code=400, detail="Promo code is not valid for one or more products in your cart")
    is_sponsored = "ZOHOR" in code["code"].upper() or bool(code.get("promo_note"))
    note = code.get("promo_note") or ("This order was placed using a sponsored promo code." if is_sponsored else None)
    return {
        "valid": True,
        "code": code["code"],
        "discount_type": code["discount_type"],
        "discount_value": code["discount_value"],
        "is_sponsored": is_sponsored,
        "promo_note": note,
        "promo": {
            "id": code["id"],
            "code": code["code"],
            "discount_type": code["discount_type"],
            "discount_value": code["discount_value"],
            "is_sponsored": is_sponsored,
            "promo_note": note,
        },
    }


@router.post("/orders/preview")
async def orders_preview(
    payload: OrderPreviewRequest,
    user: Dict[str, Any] = Depends(get_current_user),
):
    tid = user.get("tenant_id") or DEFAULT_TENANT_ID
    # Use stripe_fee_rate from oauth_connections for card payment preview
    fee_rate = await get_stripe_fee_rate(tid)
    customer = await db.customers.find_one({"tenant_id": tid, "user_id": user["id"]}, {"_id": 0})
    customer_id = customer["id"] if customer else None
    results = []
    for item in payload.items:
        product = await db.products.find_one({"tenant_id": tid, "id": item.product_id}, {"_id": 0})
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        pricing = calculate_price(product, item.inputs, fee_rate=fee_rate)
        # If a price_override is set (e.g. from scope ID unlock), use it
        if item.price_override is not None:
            pricing["subtotal"] = item.price_override
            pricing["total"] = item.price_override
            pricing["fee"] = 0.0
            pricing["is_enquiry"] = pricing.get("is_enquiry", False)
        # Include nested product and pricing objects so Cart.tsx can access item.product.pricing_type
        # and item.pricing.is_scope_request etc.
        results.append({
            "product_id": item.product_id,
            "product_name": product["name"],
            "product": product,
            "pricing": pricing,
            **pricing,  # keep flat keys for backward compatibility
        })
    return {"items": results}


@router.post("/orders/scope-request")
async def scope_request(
    payload: ScopeRequestBody,
    user: Dict[str, Any] = Depends(get_current_user),
):
    customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    tenant_id = customer.get("tenant_id", "") or user.get("tenant_id") or DEFAULT_TENANT_ID
    order_items = await build_order_items(payload.items, tenant_id)
    scope_items = [i for i in order_items if i["pricing"].get("is_scope_request")]
    if not scope_items:
        raise HTTPException(status_code=400, detail="No scope request items found")

    order_id = make_id()
    order_number = f"AA-{order_id.split('-')[0].upper()}"
    subtotal = sum(i["pricing"]["subtotal"] for i in scope_items)
    order_doc = {
        "id": order_id,
        "tenant_id": user.get("tenant_id") or DEFAULT_TENANT_ID,
        "order_number": order_number,
        "customer_id": customer["id"],
        "type": "scope_request",
        "status": "scope_requested",
        "subtotal": round_cents(subtotal),
        "fee": 0.0,
        "total": round_cents(subtotal),
        "currency": scope_items[0]["product"].get("currency", "USD") if scope_items else "USD",
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
    await create_audit_log(entity_type="order", entity_id=order_id, action="scope_request_created", actor=user["email"], details={"order_number": order_number, "product_count": len(scope_items)})

    # Email notifications for cart-based scope request
    try:
        from services.email_service import EmailService
        # Gather product names
        scope_product_names = []
        for si in scope_items:
            p = await db.products.find_one({"id": si.get("product", {}).get("id")}, {"_id": 0, "name": 1})
            if p:
                scope_product_names.append(p.get("name", ""))
        products_str = ", ".join(scope_product_names) if scope_product_names else "—"
        tenant_id = user.get("tenant_id") or DEFAULT_TENANT_ID

        admin_email = await SettingsService.get("admin_notification_email", "")
        if admin_email:
            await EmailService.send(
                trigger="scope_request_admin",
                recipient=admin_email,
                tenant_id=tenant_id,
                variables={
                    "order_number": order_number,
                    "customer_name": user.get("full_name", "Customer"),
                    "customer_email": user.get("email", ""),
                    "company": customer.get("company_name", "—"),
                    "phone": "—",
                    "products": products_str,
                    "message": "—",
                    "project_summary": "—",
                    "desired_outcomes": "—",
                    "apps_involved": "—",
                    "timeline_urgency": "—",
                    "budget_range": "—",
                    "additional_notes": "—",
                },
                db=db,
            )
        customer_email_addr = user.get("email", "")
        if customer_email_addr:
            await EmailService.send(
                trigger="enquiry_customer",
                recipient=customer_email_addr,
                tenant_id=tenant_id,
                variables={
                    "order_number": order_number,
                    "customer_name": user.get("full_name", "Customer"),
                    "customer_email": customer_email_addr,
                    "products": products_str,
                    "summary": f"Scope enquiry for: {products_str}",
                },
                db=db,
            )
    except Exception:
        pass  # Don't fail the order creation if email fails

    return {"message": "Enquiry submitted", "order_id": order_id, "order_number": order_number}


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
    first_product_currency = "USD"
    for item in payload.items:
        product = await db.products.find_one({"id": item.product_id}, {"_id": 0})
        if not product:
            continue
        if first_product_currency == "USD":
            first_product_currency = product.get("currency", "USD")
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
        "tenant_id": user.get("tenant_id") or DEFAULT_TENANT_ID,
        "order_number": order_number,
        "customer_id": customer["id"],
        "type": "scope_request",
        "status": "scope_pending",
        "subtotal": 0,
        "fee": 0,
        "total": 0,
        "currency": first_product_currency,
        "payment_method": None,
        "scope_form_data": {
            "project_summary": payload.form_data.project_summary or "",
            "desired_outcomes": payload.form_data.desired_outcomes or "",
            "apps_involved": payload.form_data.apps_involved or "",
            "timeline_urgency": payload.form_data.timeline_urgency or "",
            "budget_range": payload.form_data.budget_range or "",
            "additional_notes": payload.form_data.additional_notes or "",
            "name": payload.form_data.name or "",
            "email": payload.form_data.email or "",
            "company": payload.form_data.company or "",
            "phone": payload.form_data.phone or "",
            "message": payload.form_data.message or "",
        },
        "notes_json": _deep_merge(
            {
                "product_intake": {item.product_id: dict(item.inputs) for item in payload.items},
                "payment": {"method": "scope_request_form"},
                "system_metadata": {"user_id": user["id"], "customer_id": customer["id"], "timestamp": now_iso()},
            },
            {
                "scope_form": {
                    "project_summary": payload.form_data.project_summary or "",
                    "desired_outcomes": payload.form_data.desired_outcomes or "",
                    "apps_involved": payload.form_data.apps_involved or "",
                    "timeline_urgency": payload.form_data.timeline_urgency or "",
                    "budget_range": payload.form_data.budget_range or "",
                    "additional_notes": payload.form_data.additional_notes or "",
                    "name": payload.form_data.name or "",
                    "email": payload.form_data.email or "",
                    "company": payload.form_data.company or "",
                    "phone": payload.form_data.phone or "",
                    "message": payload.form_data.message or "",
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

    products_str = ", ".join(product_names) if product_names else "—"
    fd = payload.form_data
    # Build a readable summary for the customer confirmation email
    summary_parts = []
    if fd.project_summary:
        summary_parts.append(fd.project_summary)
    if fd.message:
        summary_parts.append(fd.message)
    if fd.desired_outcomes:
        summary_parts.append(f"Outcomes: {fd.desired_outcomes}")
    if fd.additional_notes:
        summary_parts.append(fd.additional_notes)
    summary_str = " | ".join(summary_parts) if summary_parts else "—"

    from services.email_service import EmailService
    tenant_id = user.get("tenant_id") or DEFAULT_TENANT_ID

    # Admin notification
    admin_email = await SettingsService.get("admin_notification_email", "")
    if admin_email:
        await EmailService.send(
            trigger="scope_request_admin",
            recipient=admin_email,
            tenant_id=tenant_id,
            variables={
                "order_number": order_number,
                "customer_name": user.get("full_name", "Customer"),
                "customer_email": user.get("email", ""),
                "company": fd.company or customer.get("company_name", "") or "—",
                "phone": fd.phone or "—",
                "products": products_str,
                "message": fd.message or "—",
                "project_summary": fd.project_summary or "—",
                "desired_outcomes": fd.desired_outcomes or "—",
                "apps_involved": fd.apps_involved or "—",
                "timeline_urgency": fd.timeline_urgency or "—",
                "budget_range": fd.budget_range or "—",
                "additional_notes": fd.additional_notes or "—",
            },
            db=db,
        )

    # Customer confirmation email
    customer_email_addr = user.get("email", "")
    if customer_email_addr:
        await EmailService.send(
            trigger="enquiry_customer",
            recipient=customer_email_addr,
            tenant_id=tenant_id,
            variables={
                "order_number": order_number,
                "customer_name": user.get("full_name", "Customer"),
                "customer_email": customer_email_addr,
                "products": products_str,
                "summary": summary_str,
            },
            db=db,
        )

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
    await create_audit_log(entity_type="order", entity_id=order_id, action="scope_request_form_created", actor=user["email"], details={"order_number": order_number})
    return {
        "message": "Enquiry submitted",
        "order_id": order_id,
        "order_number": order_number,
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
    customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Order not found")
    # IDOR check: ensure order belongs to this customer within this tenant
    order = await db.orders.find_one(
        {"id": order_id, "customer_id": customer["id"]}, {"_id": 0}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    items = await db.order_items.find({"order_id": order_id}, {"_id": 0}).to_list(200)
    
    # Include terms of service if applicable
    terms = None
    if order.get("terms_id"):
        terms = await db.terms_and_conditions.find_one(
            {"id": order["terms_id"]},
            {"_id": 0, "id": 1, "title": 1, "content": 1}
        )
    elif order.get("tenant_id"):
        # Get default terms for tenant
        terms = await db.terms_and_conditions.find_one(
            {"tenant_id": order["tenant_id"], "is_default": True, "status": "active"},
            {"_id": 0, "id": 1, "title": 1, "content": 1}
        )
    
    return {"order": order, "items": items, "terms": terms}


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
    customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Subscription not found")
    # IDOR check: ensure subscription belongs to this customer
    subscription = await db.subscriptions.find_one(
        {"id": subscription_id, "customer_id": customer["id"]}, {"_id": 0}
    )
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    await db.subscriptions.update_one(
        {"id": subscription_id},
        {"$set": {"cancel_at_period_end": True, "status": "canceled_pending", "canceled_at": now_iso()}},
    )
    await create_audit_log(entity_type="subscription", entity_id=subscription_id, action="cancellation_requested", actor=user["email"], details={"reason": getattr(payload, "reason", None), "initiated_by": "customer"})
    from services.email_service import EmailService
    await EmailService.send(
        trigger="subscription_cancellation",
        recipient=user["email"],
        variables={"customer_name": user.get("full_name", ""), "customer_email": user["email"]},
        db=db,
    )
    return {"message": "Cancellation scheduled"}
