"""Checkout routes: Stripe session, bank transfer, checkout status."""
from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request

from core.helpers import make_id, now_iso, round_cents
from core.security import get_current_user
from core.config import STRIPE_API_KEY
from db.session import db
from models import CheckoutSessionRequestBody, BankTransferCheckoutRequest
from services.audit_service import create_audit_log
from services.checkout_service import (
    build_order_items,
    build_checkout_notes_json,
    resolve_terms_tags,
)
from services.settings_service import SettingsService
from core.constants import SERVICE_FEE_RATE

try:
    from emergentintegrations.payments.stripe.checkout import (
        StripeCheckout,
        CheckoutSessionRequest,
        CheckoutSessionResponse,
        CheckoutStatusResponse,
    )
    import stripe as stripe_sdk
except ImportError:
    StripeCheckout = CheckoutSessionRequest = CheckoutSessionResponse = None  # type: ignore
    CheckoutStatusResponse = None  # type: ignore
    stripe_sdk = None  # type: ignore

try:
    from gocardless_helper import (
        create_gocardless_customer,
        create_redirect_flow,
    )
except ImportError:
    create_gocardless_customer = create_redirect_flow = None  # type: ignore

router = APIRouter(prefix="/api", tags=["checkout"])


async def get_gocardless_creds(tenant_id: str) -> Tuple[Optional[str], str]:
    """Get GoCardless credentials from oauth_connections."""
    conn = await db.oauth_connections.find_one(
        {"tenant_id": tenant_id, "provider": {"$in": ["gocardless", "gocardless_sandbox"]}, "is_validated": True},
        {"_id": 0, "credentials": 1, "provider": 1}
    )
    if not conn:
        return None, "sandbox"
    creds = conn.get("credentials", {})
    token = creds.get("access_token", "")
    env = "sandbox" if conn.get("provider") == "gocardless_sandbox" else "live"
    return token, env


async def get_stripe_creds(tenant_id: str) -> Tuple[Optional[str], Optional[str], float]:
    """Get Stripe credentials and settings from oauth_connections.
    
    Returns: (api_key, publishable_key, fee_rate)
    """
    conn = await db.oauth_connections.find_one(
        {"tenant_id": tenant_id, "provider": "stripe", "is_validated": True},
        {"_id": 0, "credentials": 1, "settings": 1}
    )
    if not conn:
        return STRIPE_API_KEY, None, SERVICE_FEE_RATE
    creds = conn.get("credentials", {})
    settings = conn.get("settings", {})
    api_key = creds.get("api_key") or STRIPE_API_KEY
    publishable_key = creds.get("publishable_key")
    fee_rate = float(settings.get("fee_rate", SERVICE_FEE_RATE))
    return api_key, publishable_key, fee_rate


async def is_stripe_enabled(tenant_id: str) -> bool:
    """Check if Stripe is connected and validated from oauth_connections."""
    conn = await db.oauth_connections.find_one(
        {"tenant_id": tenant_id, "provider": "stripe", "is_validated": True},
        {"_id": 0}
    )
    return conn is not None


async def is_gocardless_enabled(tenant_id: str) -> bool:
    """Check if GoCardless is connected and validated from oauth_connections."""
    conn = await db.oauth_connections.find_one(
        {"tenant_id": tenant_id, "provider": {"$in": ["gocardless", "gocardless_sandbox"]}, "is_validated": True},
        {"_id": 0}
    )
    return conn is not None


async def get_tenant_base_currency(tenant_id: str) -> str:
    """Get the tenant's base currency, defaulting to USD."""
    if not tenant_id:
        return "USD"
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0, "base_currency": 1})
    return tenant.get("base_currency", "USD") if tenant else "USD"


@router.post("/checkout/bank-transfer")
async def checkout_bank_transfer(
    payload: BankTransferCheckoutRequest,
    user: Dict[str, Any] = Depends(get_current_user),
):
    if not payload.terms_accepted:
        raise HTTPException(status_code=400, detail="You must accept the Terms & Conditions to proceed")

    customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    tenant_id = customer.get("tenant_id", "")
    gocardless_globally_enabled = await is_gocardless_enabled(tenant_id)
    if not gocardless_globally_enabled:
        raise HTTPException(status_code=400, detail="Bank transfer payments are currently not available.")

    if not customer.get("allow_bank_transfer", True):
        raise HTTPException(status_code=403, detail="Bank transfer not enabled")

    order_items = await build_order_items(payload.items, tenant_id)
    base_currency = await get_tenant_base_currency(tenant_id)

    checkout_type = payload.checkout_type
    if checkout_type not in ["one_time", "subscription"]:
        raise HTTPException(status_code=400, detail="Invalid checkout type")

    promo_code_data = None  # initialised early — subscription branch also references it in notes_json

    if checkout_type == "subscription":
        subscription_items = [i for i in order_items if i["pricing"].get("is_subscription")]
        if len(subscription_items) != len(order_items):
            raise HTTPException(status_code=400, detail="Subscription checkout must include only subscription items")
        if len(subscription_items) != 1:
            raise HTTPException(status_code=400, detail="Subscription checkout supports one plan at a time")

        product = subscription_items[0]["product"]
        subtotal = subscription_items[0]["pricing"]["subtotal"]
        if not terms_id:
            default_terms = await db.terms_and_conditions.find_one({"is_default": True, "status": "active"}, {"_id": 0})
            terms_id = default_terms["id"] if default_terms else None

        rendered_terms_text = ""
        if terms_id:
            terms = await db.terms_and_conditions.find_one({"id": terms_id}, {"_id": 0})
            if terms:
                address = await db.addresses.find_one({"user_id": user["id"]}, {"_id": 0})
                rendered_terms_text = resolve_terms_tags(terms["content"], user, address or {}, product["name"])

        period_start = datetime.now(timezone.utc)
        requested_start = None
        if payload.start_date:
            try:
                sd = datetime.fromisoformat(payload.start_date)
                if sd.tzinfo is None:
                    sd = sd.replace(tzinfo=timezone.utc)
                if sd > datetime.now(timezone.utc):
                    period_start = sd
                    requested_start = payload.start_date
            except Exception:
                pass
        period_end = period_start + timedelta(days=30)
        contract_end = period_start + timedelta(days=365)
        sub_id = make_id()

        gocardless_redirect_url = None
        gc_customer_id = customer.get("gocardless_customer_id")
        redirect_flow_id = None

        # Get GoCardless credentials from Connected Services
        gc_token, gc_env = await get_gocardless_creds(customer.get("tenant_id", ""))

        if not gc_customer_id and create_gocardless_customer and gc_token:
            name_parts = user.get("full_name", "Customer User").split()
            gc_customer = create_gocardless_customer(
                email=user["email"],
                given_name=name_parts[0],
                family_name=name_parts[-1] if len(name_parts) > 1 else "User",
                company_name=user.get("company_name", ""),
                gc_token=gc_token,
                gc_env=gc_env,
            )
            if gc_customer:
                gc_customer_id = gc_customer["id"]
                await db.customers.update_one({"id": customer["id"]}, {"$set": {"gocardless_customer_id": gc_customer_id}})

        if gc_customer_id and create_redirect_flow and gc_token:
            session_token = make_id()
            frontend_url = os.environ.get("FRONTEND_URL", os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:3000").replace("/api", ""))
            success_url = f"{frontend_url}/gocardless/callback?session_token={session_token}&subscription_id={sub_id}"
            redirect_flow = create_redirect_flow(
                session_token=session_token,
                success_redirect_url=success_url,
                description=f"Direct Debit for {product['name']}",
                gc_token=gc_token,
                gc_env=gc_env,
            )
            if redirect_flow:
                redirect_flow_id = redirect_flow["id"]
                gocardless_redirect_url = redirect_flow["redirect_url"]

        sub_number = f"SUB-{sub_id.split('-')[0].upper()}"
        await db.subscriptions.insert_one({
            "id": sub_id,
            "subscription_number": sub_number,
            "order_id": None,
            "customer_id": customer["id"],
            "product_id": product["id"],
            "plan_name": product["name"],
            "status": "pending_direct_debit_setup",
            "stripe_subscription_id": None,
            "processor_id": redirect_flow_id,
            "gocardless_customer_id": gc_customer_id,
            "gocardless_redirect_flow_id": redirect_flow_id,
            "current_period_start": period_start.isoformat(),
            "current_period_end": period_end.isoformat(),
            "cancel_at_period_end": False,
            "canceled_at": None,
            "amount": subtotal,
            "currency": product.get("currency", "USD"),
            "base_currency": base_currency,
            "payment_method": "bank_transfer",
            "terms_id_used": terms_id,
            "rendered_terms_text": rendered_terms_text,
            "terms_accepted_at": now_iso(),
            "start_date": requested_start or period_start.isoformat(),
            "renewal_date": period_end.isoformat(),
            "contract_end_date": contract_end.isoformat(),

            "notes_json": build_checkout_notes_json(order_items, payload, user["id"], customer["id"], payment_method="bank_transfer", promo_data=promo_code_data),
            "internal_note": "",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        })
        await create_audit_log(
            entity_type="subscription", entity_id=sub_id,
            action="created", actor="customer",
            details={"status": "pending_direct_debit_setup", "payment_method": "bank_transfer", "currency": product.get("currency", "USD"), "base_currency": base_currency},
        )
        await db.zoho_sync_logs.insert_one({
            "id": make_id(), "entity_type": "subscription_request", "entity_id": sub_id,
            "status": "Not Sent", "last_error": None, "attempts": 0, "created_at": now_iso(), "mocked": True,
        })

        if not gocardless_redirect_url:
            raise HTTPException(status_code=500, detail="Failed to create GoCardless redirect flow. Please contact support or try card payment.")

        return {
            "message": "Subscription request created. Please complete Direct Debit setup.",
            "subscription_id": sub_id,
            "status": "pending_direct_debit_setup",
            "gocardless_customer_id": gc_customer_id,
            "gocardless_redirect_url": gocardless_redirect_url,
            "redirect_flow_id": redirect_flow_id,
        }

    # One-time bank transfer
    subtotal = sum(i["pricing"]["subtotal"] for i in order_items)
    promo_code_data = None
    discount_amount = 0.0
    if payload.promo_code:
        promo = await db.promo_codes.find_one({"code": payload.promo_code.upper()}, {"_id": 0})
        if promo and promo.get("enabled"):
            now_str = datetime.now(timezone.utc).isoformat()
            is_expired = promo.get("expiry_date") and promo["expiry_date"] < now_str
            max_reached = promo.get("max_uses") and promo.get("usage_count", 0) >= promo["max_uses"]
            applies_to = promo.get("applies_to", "both")
            type_matches = applies_to == "both" or applies_to == "one-time"
            product_eligible = True
            if promo.get("applies_to_products") == "selected":
                eligible_ids = promo.get("product_ids", [])
                cart_ids = [i["product"]["id"] for i in order_items]
                if not all(pid in eligible_ids for pid in cart_ids):
                    product_eligible = False
            if not is_expired and not max_reached and type_matches and product_eligible:
                if promo["discount_type"] == "percent":
                    discount_amount = round_cents(subtotal * promo["discount_value"] / 100)
                else:
                    discount_amount = min(round_cents(promo["discount_value"]), subtotal)
                promo_code_data = promo

    total = round_cents(subtotal - discount_amount)

    primary_product = order_items[0]["product"]
    terms_id = payload.terms_id if payload.terms_id else primary_product.get("terms_id")
    if not terms_id:
        default_terms = await db.terms_and_conditions.find_one({"is_default": True, "status": "active"}, {"_id": 0})
        terms_id = default_terms["id"] if default_terms else None

    rendered_terms_text = ""
    if terms_id:
        terms = await db.terms_and_conditions.find_one({"id": terms_id}, {"_id": 0})
        if terms:
            address = await db.addresses.find_one({"user_id": user["id"]}, {"_id": 0})
            rendered_terms_text = resolve_terms_tags(terms["content"], user, address or {}, primary_product["name"])

    order_id = make_id()
    order_number = f"AA-{order_id.split('-')[0].upper()}"

    gocardless_redirect_url = None
    gc_customer_id = customer.get("gocardless_customer_id")
    redirect_flow_id = None

    # Get GoCardless credentials from Connected Services
    gc_token, gc_env = await get_gocardless_creds(customer.get("tenant_id", ""))

    if not gc_customer_id and create_gocardless_customer and gc_token:
        name_parts = user.get("full_name", "Customer User").split()
        gc_customer = create_gocardless_customer(
            email=user["email"],
            given_name=name_parts[0],
            family_name=name_parts[-1] if len(name_parts) > 1 else "User",
            company_name=user.get("company_name", ""),
            gc_token=gc_token,
            gc_env=gc_env,
        )
        if gc_customer:
            gc_customer_id = gc_customer["id"]
            await db.customers.update_one({"id": customer["id"]}, {"$set": {"gocardless_customer_id": gc_customer_id}})

    if gc_customer_id and create_redirect_flow and gc_token:
        session_token = make_id()
        frontend_url = os.environ.get("FRONTEND_URL", os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:3000").replace("/api", ""))
        success_url = f"{frontend_url}/gocardless/callback?session_token={session_token}&order_id={order_id}"
        redirect_flow = create_redirect_flow(
            session_token=session_token,
            success_redirect_url=success_url,
            description=f"Payment for Order {order_number}",
            gc_token=gc_token,
            gc_env=gc_env,
        )
        if redirect_flow:
            redirect_flow_id = redirect_flow["id"]
            gocardless_redirect_url = redirect_flow["redirect_url"]

    order_doc = {
        "id": order_id, "order_number": order_number,
        "customer_id": customer["id"], "type": "one_time",
        "status": "pending_direct_debit_setup",
        "subtotal": round_cents(subtotal), "discount_amount": discount_amount,
        "promo_code": promo_code_data["code"] if promo_code_data else None,
        "fee": 0.0, "total": total, "currency": order_items[0]["product"].get("currency", "USD"),
        "base_currency": base_currency,
        "payment_method": "bank_transfer",
        "gocardless_redirect_flow_id": redirect_flow_id,
        "terms_id_used": terms_id, "rendered_terms_text": rendered_terms_text,
        "terms_accepted_at": now_iso(),
        "notes_json": build_checkout_notes_json(order_items, payload, user["id"], customer["id"], payment_method="bank_transfer", promo_data=promo_code_data),
        "extra_fields": payload.extra_fields or {},
        "created_at": now_iso(),
    }
    await db.orders.insert_one(order_doc)
    await create_audit_log(
        entity_type="order", entity_id=order_id, action="created", actor="customer",
        details={"status": "pending_direct_debit_setup", "payment_method": "bank_transfer", "total": total, "currency": order_items[0]["product"].get("currency", "USD"), "base_currency": base_currency, "extra_fields": list((payload.extra_fields or {}).keys())},
    )
    if promo_code_data:
        await db.promo_codes.update_one({"id": promo_code_data["id"]}, {"$inc": {"usage_count": 1}})

    for item in order_items:
        product = item["product"]
        await db.order_items.insert_one({
            "id": make_id(), "order_id": order_id, "product_id": product["id"],
            "quantity": item["quantity"], "metadata_json": item["inputs"],
            "unit_price": item["pricing"]["subtotal"], "line_total": item["pricing"]["subtotal"],
        })
        # ── Audit: log intake question answers per item ───────────────────
        intake_answers = item.get("inputs") or {}
        if intake_answers:
            await create_audit_log(
                entity_type="order", entity_id=order_id, action="intake_submitted",
                actor="customer",
                details={
                    "product_id": product["id"],
                    "product_name": product.get("name", ""),
                    "intake_answers": intake_answers,
                    "order_number": order_number,
                },
            )

    await db.invoices.insert_one({
        "id": make_id(), "order_id": order_id, "subscription_id": None,
        "stripe_invoice_id": None, "zoho_books_invoice_id": None,
        "amount_paid": 0.0, "status": "unpaid",
    })
    await db.zoho_sync_logs.insert_one({
        "id": make_id(), "entity_type": "deal", "entity_id": order_id,
        "status": "Not Sent", "last_error": None, "attempts": 0, "created_at": now_iso(), "mocked": True,
    })
    if rendered_terms_text:
        await db.email_outbox.insert_one({
            "id": make_id(), "to": user["email"],
            "subject": f"Terms & Conditions for Order {order_number}",
            "body": rendered_terms_text, "type": "terms_and_conditions",
            "status": "MOCKED", "created_at": now_iso(),
        })

    if not gocardless_redirect_url:
        raise HTTPException(status_code=500, detail="Failed to create GoCardless redirect flow. Please contact support or try card payment.")

    return {
        "message": "Order created. Please complete Direct Debit setup.",
        "order_id": order_id, "order_number": order_number,
        "gocardless_redirect_url": gocardless_redirect_url,
        "redirect_flow_id": redirect_flow_id,
        "status": "pending_direct_debit_setup",
    }


@router.post("/checkout/session")
async def create_checkout_session(
    payload: CheckoutSessionRequestBody,
    request: Request,
    user: Dict[str, Any] = Depends(get_current_user),
):
    if not payload.terms_accepted:
        raise HTTPException(status_code=400, detail="You must accept the Terms & Conditions to proceed")

    customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    tenant_id = customer.get("tenant_id", "")
    if not payload.zoho_subscription_type:
        raise HTTPException(status_code=400, detail="Please select your current Zoho subscription type.")
    if not payload.current_zoho_product:
        raise HTTPException(status_code=400, detail="Please select your current Zoho product.")
    if not payload.zoho_account_access:
        raise HTTPException(status_code=400, detail="Please indicate whether you have provided Zoho account access.")

    order_items = await build_order_items(payload.items, tenant_id)
    base_currency = await get_tenant_base_currency(tenant_id)

    checkout_type = payload.checkout_type
    if checkout_type not in ["one_time", "subscription"]:
        raise HTTPException(status_code=400, detail="Invalid checkout type")

    if checkout_type == "subscription":
        subscription_items = [i for i in order_items if i["pricing"].get("is_subscription")]
        if len(subscription_items) != len(order_items):
            raise HTTPException(status_code=400, detail="Subscription checkout must include only subscription items")
        if len(subscription_items) != 1:
            raise HTTPException(status_code=400, detail="Subscription checkout supports one plan at a time")
        product = subscription_items[0]["product"]
        subtotal = subscription_items[0]["pricing"]["subtotal"]
        if not subtotal or subtotal <= 0:
            raise HTTPException(status_code=400, detail="Subscription pricing not configured. Please contact support.")
        if not customer.get("allow_card_payment", False):
            raise HTTPException(status_code=403, detail="Card payment is not enabled for your account. Please contact support or use Bank Transfer.")
        tenant_id = customer.get("tenant_id", "")
        stripe_globally_enabled = await is_stripe_enabled(tenant_id)
        if not stripe_globally_enabled:
            raise HTTPException(status_code=400, detail="Card payments are currently not available.")
        stripe_price_id = product.get("stripe_price_id")
        if not stripe_price_id:
            raise HTTPException(status_code=400, detail=f"Subscription product '{product.get('name')}' is not configured for card payment. Missing Stripe Price ID.")

    if checkout_type == "one_time":
        tenant_id = customer.get("tenant_id", "")
        stripe_globally_enabled = await is_stripe_enabled(tenant_id)
        if not stripe_globally_enabled:
            raise HTTPException(status_code=400, detail="Card payments are currently not available.")
        if not customer.get("allow_card_payment", False):
            raise HTTPException(status_code=403, detail="Card payment is not enabled for your account. Please contact support or use Bank Transfer.")
        for item in order_items:
            if item["pricing"].get("is_subscription"):
                raise HTTPException(status_code=400, detail="One-time checkout cannot include subscriptions")
            if item["pricing"].get("is_enquiry") or item["product"].get("pricing_type") in ["external", "enquiry"]:
                raise HTTPException(status_code=400, detail="Checkout not supported for this item")

    subtotal = sum(i["pricing"]["subtotal"] for i in order_items)
    promo_code_data = None
    discount_amount = 0.0
    if payload.promo_code:
        promo = await db.promo_codes.find_one({"code": payload.promo_code.upper()}, {"_id": 0})
        if promo and promo.get("enabled"):
            now_str = datetime.now(timezone.utc).isoformat()
            is_expired = promo.get("expiry_date") and promo["expiry_date"] < now_str
            max_reached = promo.get("max_uses") and promo.get("usage_count", 0) >= promo["max_uses"]
            applies_to = promo.get("applies_to", "both")
            type_matches = applies_to == "both" or \
                (applies_to == "one-time" and checkout_type == "one_time") or \
                (applies_to == "subscription" and checkout_type == "subscription")
            product_eligible = True
            if promo.get("applies_to_products") == "selected":
                eligible_ids = promo.get("product_ids", [])
                cart_ids = [i["product"]["id"] for i in order_items]
                if not all(pid in eligible_ids for pid in cart_ids):
                    product_eligible = False
            if not is_expired and not max_reached and type_matches and product_eligible:
                if promo["discount_type"] == "percent":
                    discount_amount = round_cents(subtotal * promo["discount_value"] / 100)
                else:
                    discount_amount = min(round_cents(promo["discount_value"]), subtotal)
                promo_code_data = promo

    _stripe_api_key, _, _fee_rate = await get_stripe_creds(tenant_id)
    discounted_subtotal = subtotal - discount_amount
    fee = round_cents(discounted_subtotal * _fee_rate)
    total = round_cents(discounted_subtotal + fee)

    primary_product = order_items[0]["product"]
    terms_id = payload.terms_id if payload.terms_id else primary_product.get("terms_id")
    if not terms_id:
        default_terms = await db.terms_and_conditions.find_one({"is_default": True, "status": "active"}, {"_id": 0})
        terms_id = default_terms["id"] if default_terms else None

    rendered_terms_text = ""
    if terms_id:
        terms = await db.terms_and_conditions.find_one({"id": terms_id}, {"_id": 0})
        if terms:
            address = await db.addresses.find_one({"user_id": user["id"]}, {"_id": 0})
            rendered_terms_text = resolve_terms_tags(terms["content"], user, address or {}, primary_product["name"])

    order_id = make_id()
    order_number = f"AA-{order_id.split('-')[0].upper()}"
    order_doc = {
        "id": order_id, "order_number": order_number,
        "customer_id": customer["id"],
        "type": "subscription_start" if checkout_type == "subscription" else "one_time",
        "status": "pending",
        "subtotal": round_cents(subtotal), "discount_amount": discount_amount,
        "promo_code": promo_code_data["code"] if promo_code_data else None,
        "fee": fee, "total": total, "currency": order_items[0]["product"].get("currency", "USD"),
        "base_currency": base_currency,
        "payment_method": "card",
        "terms_id_used": terms_id, "rendered_terms_text": rendered_terms_text,
        "terms_accepted_at": now_iso(),
        "notes_json": build_checkout_notes_json(order_items, payload, user["id"], customer["id"], payment_method="card", promo_data=promo_code_data),
        "extra_fields": payload.extra_fields or {},
        "created_at": now_iso(),
    }
    await db.orders.insert_one(order_doc)
    await create_audit_log(
        entity_type="order", entity_id=order_id, action="created", actor="system",
        details={"checkout_type": checkout_type, "payment_method": "card", "total": total, "currency": order_items[0]["product"].get("currency", "USD"), "base_currency": base_currency, "extra_fields": list((payload.extra_fields or {}).keys())},
    )

    for item in order_items:
        product = item["product"]
        await db.order_items.insert_one({
            "id": make_id(), "order_id": order_id, "product_id": product["id"],
            "quantity": item["quantity"], "metadata_json": item["inputs"],
            "unit_price": item["pricing"]["subtotal"], "line_total": item["pricing"]["subtotal"],
        })
        # ── Audit: log intake question answers ────────────────────────────
        intake_answers = item.get("inputs") or {}
        if intake_answers:
            await create_audit_log(
                entity_type="order", entity_id=order_id, action="intake_submitted",
                actor="customer",
                details={
                    "product_id": product["id"],
                    "product_name": product.get("name", ""),
                    "intake_answers": intake_answers,
                    "order_number": order_number,
                },
            )
    
    host_url = payload.origin_url.rstrip("/")
    success_url = f"{host_url}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{host_url}/cart"
    stripe_checkout = StripeCheckout(api_key=_stripe_api_key, webhook_url=f"{host_url}/api/webhook/stripe")
    metadata = {
        "order_id": order_id, "order_number": order_number,
        "customer_id": customer["id"], "checkout_type": checkout_type,
        "promo_code": promo_code_data["code"] if promo_code_data else "",
        "discount_amount": str(discount_amount),
    }

    if checkout_type == "subscription":
        product = order_items[0]["product"]
        stripe_price_id = product.get("stripe_price_id")
        try:
            stripe_sdk.api_key = _stripe_api_key
            subscription_data: Dict[str, Any] = {"metadata": metadata}
            requested_start_date = payload.start_date
            if requested_start_date:
                try:
                    sd = datetime.fromisoformat(requested_start_date)
                    if sd.tzinfo is None:
                        sd = sd.replace(tzinfo=timezone.utc)
                    min_future = datetime.now(timezone.utc) + timedelta(days=3)
                    if sd > min_future:
                        subscription_data["trial_end"] = int(sd.timestamp())
                        subscription_data["trial_settings"] = {"end_behavior": {"missing_payment_method": "pause"}}
                        metadata["start_date"] = requested_start_date
                    elif sd > datetime.now(timezone.utc):
                        raise HTTPException(status_code=400, detail="Subscription start date must be at least 3 days in the future")
                except HTTPException:
                    raise
                except Exception:
                    pass
            session = stripe_sdk.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{"price": stripe_price_id, "quantity": order_items[0]["quantity"]}],
                mode="subscription",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata,
                customer_email=user["email"],
                subscription_data=subscription_data,
            )
            session_response = CheckoutSessionResponse(session_id=session.id, url=session.url)
        except stripe_sdk.error.StripeError as e:
            raise HTTPException(status_code=400, detail=f"Stripe subscription checkout error: {str(e)}")
    else:
        checkout_request = CheckoutSessionRequest(
            amount=float(total),
            currency=order_items[0]["product"].get("currency", "USD").lower(),
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata,
        )
        try:
            session_response: CheckoutSessionResponse = await stripe_checkout.create_checkout_session(checkout_request)
        except Exception as e:
            error_msg = str(e)
            if "price" in error_msg.lower():
                raise HTTPException(status_code=400, detail=f"Stripe Price configuration error: {error_msg}")
            elif "currency" in error_msg.lower():
                raise HTTPException(status_code=400, detail=f"Currency mismatch: {error_msg}")
            else:
                raise HTTPException(status_code=500, detail=f"Checkout session creation failed: {error_msg}")

    await db.payment_transactions.insert_one({
        "id": make_id(), "session_id": session_response.session_id,
        "payment_status": "initiated", "amount": float(total),
        "currency": order_items[0]["product"].get("currency", "USD"), "metadata": metadata,
        "user_id": user["id"], "order_id": order_id,
        "created_at": now_iso(), "updated_at": now_iso(),
    })
    return {"url": session_response.url, "session_id": session_response.session_id, "order_id": order_id}


@router.get("/checkout/status/{session_id}")
async def checkout_status(
    session_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
    tenant_id = customer.get("tenant_id", "") if customer else ""
    stripe_api_key, _, _ = await get_stripe_creds(tenant_id)
    stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url="")
    status: CheckoutStatusResponse = await stripe_checkout.get_checkout_status(session_id)
    transaction = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if transaction:
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {"payment_status": status.payment_status, "status": status.status, "updated_at": now_iso()}},
        )
    if status.payment_status == "paid" and transaction:
        order = await db.orders.find_one({"id": transaction.get("order_id")}, {"_id": 0})
        if order and order.get("status") != "paid":
            # --- Resolve actual Stripe payment intent ID ---
            payment_intent_id = session_id  # fallback to session id
            stripe_sub_id = None
            try:
                stripe_sdk.api_key = stripe_api_key
                session_obj = stripe_sdk.checkout.Session.retrieve(
                    session_id, expand=["payment_intent", "subscription"]
                )
                if session_obj.get("payment_intent"):
                    pi = session_obj["payment_intent"]
                    payment_intent_id = pi["id"] if isinstance(pi, dict) else getattr(pi, "id", session_id)
                if session_obj.get("subscription"):
                    sub_obj = session_obj["subscription"]
                    stripe_sub_id = sub_obj["id"] if isinstance(sub_obj, dict) else getattr(sub_obj, "id", None)
                    if stripe_sub_id and not session_obj.get("payment_intent"):
                        # For subscriptions get PI from latest invoice
                        try:
                            sub_detail = stripe_sdk.Subscription.retrieve(stripe_sub_id)
                            if sub_detail.get("latest_invoice"):
                                inv = stripe_sdk.Invoice.retrieve(
                                    sub_detail["latest_invoice"], expand=["payment_intent"]
                                )
                                pi = inv.get("payment_intent")
                                if pi:
                                    payment_intent_id = pi["id"] if isinstance(pi, dict) else getattr(pi, "id", session_id)
                        except Exception:
                            pass
            except Exception:
                pass

            await db.orders.update_one(
                {"id": order["id"]},
                {"$set": {
                    "status": "paid",
                    "processor_id": payment_intent_id,
                    "payment_date": now_iso(),
                    "updated_at": now_iso(),
                }},
            )
            await create_audit_log(
                entity_type="order",
                entity_id=order["id"],
                action="payment_confirmed",
                actor="stripe",
                details={
                    "session_id": session_id,
                    "payment_intent_id": payment_intent_id,
                    "amount": order.get("total"),
                    "currency": order.get("currency"),
                    "payment_method": "card",
                    "previous_status": order.get("status"),
                },
            )
            await db.invoices.insert_one({
                "id": make_id(), "order_id": order["id"], "subscription_id": None,
                "stripe_invoice_id": None, "zoho_books_invoice_id": None,
                "amount_paid": order.get("total"), "status": "paid",
            })
            if order.get("type") == "subscription_start":
                existing_sub = await db.subscriptions.find_one({"order_id": order["id"]}, {"_id": 0})
                if not existing_sub:
                    items = await db.order_items.find({"order_id": order["id"]}, {"_id": 0}).to_list(5)
                    product_name = "Subscription"
                    product_id = None
                    if items:
                        product = await db.products.find_one({"id": items[0]["product_id"]}, {"_id": 0})
                        if product:
                            product_name = product["name"]
                            product_id = product["id"]
                    period_start = datetime.now(timezone.utc)
                    period_end = period_start + timedelta(days=30)
                    contract_end = period_start + timedelta(days=365)
                    sub_id = make_id()
                    sub_number = f"SUB-{sub_id.split('-')[0].upper()}"
                    await db.subscriptions.insert_one({
                        "id": sub_id,
                        "subscription_number": sub_number,
                        "order_id": order["id"],
                        "customer_id": order["customer_id"],
                        "product_id": product_id,
                        "plan_name": product_name,
                        "status": "active",
                        "stripe_subscription_id": stripe_sub_id,
                        "processor_id": payment_intent_id,
                        "current_period_start": period_start.isoformat(),
                        "current_period_end": period_end.isoformat(),
                        "start_date": period_start.isoformat(),
                        "renewal_date": period_end.isoformat(),
                        "contract_end_date": contract_end.isoformat(),
                        "cancel_at_period_end": False,
                        "canceled_at": None,
                        "amount": order.get("subtotal"),
                        "currency": order.get("currency", "USD"),
                        "base_currency": order.get("base_currency", "USD"),
                        "payment_method": "card",
                        "notes": [],
                        "internal_note": "",

                        "created_at": now_iso(),
                        "updated_at": now_iso(),
                    })
                    # Back-fill order with subscription linkage
                    await db.orders.update_one(
                        {"id": order["id"]},
                        {"$set": {"subscription_id": sub_id, "subscription_number": sub_number}},
                    )
                    await create_audit_log(
                        entity_type="subscription",
                        entity_id=sub_id,
                        action="created",
                        actor="stripe",
                        details={
                            "plan_name": product_name,
                            "status": "active",
                            "payment_method": "card",
                            "currency": order.get("currency", "USD"),
                            "base_currency": order.get("base_currency", "USD"),
                            "order_id": order["id"],
                            "session_id": session_id,
                            "payment_intent_id": payment_intent_id,
                            "stripe_subscription_id": stripe_sub_id,
                        },
                    )
                    await db.email_outbox.insert_one({
                        "id": make_id(), "to": user["email"],
                        "subject": "Subscription started",
                        "body": f"Your subscription {product_name} is active.",
                        "type": "subscription_started", "status": "MOCKED", "created_at": now_iso(),
                    })

            
            # Send order confirmation email with ToS PDF attachment
            from services.email_service import EmailService
            from services.pdf_service import generate_order_tos_pdf
            
            attachments = []
            try:
                # Generate ToS PDF if available
                tos_pdf = await generate_order_tos_pdf(
                    tenant_id=order.get("tenant_id", "automate-accounts"),
                    order_id=order["id"],
                    db=db
                )
                if tos_pdf:
                    attachments.append({
                        "filename": f"terms-and-conditions-{order['order_number']}.pdf",
                        "content": tos_pdf,
                        "content_type": "application/pdf"
                    })
            except Exception as pdf_err:
                # Log error but don't fail the order
                import logging
                logging.warning(f"Failed to generate ToS PDF for order {order['id']}: {pdf_err}")
            
            await EmailService.send(
                trigger="order_placed",
                recipient=user["email"],
                variables={
                    "customer_name": user.get("full_name", ""),
                    "customer_email": user["email"],
                    "order_number": order["order_number"],
                    "order_total": f"{order.get('total', 0):.2f}",
                    "order_currency": order.get("currency", "USD"),
                },
                db=db,
                attachments=attachments if attachments else None,
                tenant_id=order.get("tenant_id")
            )
    return {
        "status": status.status,
        "payment_status": status.payment_status,
        "amount_total": status.amount_total,
        "currency": status.currency,
        "metadata": status.metadata,
    }



@router.post("/checkout/free")
async def checkout_free(
    payload: BankTransferCheckoutRequest,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Handle checkout for free products (total = $0).
    Bypasses payment processors and creates order directly with 'paid' status.
    """
    if not payload.terms_accepted:
        raise HTTPException(status_code=400, detail="You must accept the Terms & Conditions to proceed")

    customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    tenant_id = customer.get("tenant_id", "")

    order_items = await build_order_items(payload.items, tenant_id)
    base_currency = await get_tenant_base_currency(tenant_id)
    
    # Calculate total and verify it's actually free
    subtotal = sum(i["pricing"]["subtotal"] for i in order_items)
    
    # Apply promo code if any
    promo_code_data = None
    discount_amount = 0.0
    if payload.promo_code:
        promo = await db.promo_codes.find_one({"code": payload.promo_code.upper()}, {"_id": 0})
        if promo and promo.get("enabled"):
            now_str = datetime.now(timezone.utc).isoformat()
            is_expired = promo.get("expiry_date") and promo["expiry_date"] < now_str
            max_reached = promo.get("max_uses") and promo.get("usage_count", 0) >= promo["max_uses"]
            if not is_expired and not max_reached:
                if promo["discount_type"] == "percent":
                    discount_amount = round_cents(subtotal * promo["discount_value"] / 100)
                else:
                    discount_amount = min(round_cents(promo["discount_value"]), subtotal)
                promo_code_data = promo
    
    total = round_cents(subtotal - discount_amount)
    
    # Ensure total is 0 or very close (within rounding tolerance)
    if total > 0.01:
        raise HTTPException(status_code=400, detail="This checkout endpoint is only for free products. Please use the regular checkout for paid items.")

    primary_product = order_items[0]["product"]
    terms_id = payload.terms_id if payload.terms_id else primary_product.get("terms_id")
    if not terms_id:
        default_terms = await db.terms_and_conditions.find_one({"is_default": True, "status": "active"}, {"_id": 0})
        terms_id = default_terms["id"] if default_terms else None

    rendered_terms_text = ""
    if terms_id:
        terms = await db.terms_and_conditions.find_one({"id": terms_id}, {"_id": 0})
        if terms:
            address = await db.addresses.find_one({"user_id": user["id"]}, {"_id": 0})
            rendered_terms_text = resolve_terms_tags(terms["content"], user, address or {}, primary_product["name"])

    order_id = make_id()
    order_number = f"AA-{order_id.split('-')[0].upper()}"

    order_doc = {
        "id": order_id,
        "order_number": order_number,
        "tenant_id": tenant_id,
        "customer_id": customer["id"],
        "type": "one_time",
        "status": "paid",  # Free orders are immediately marked as paid
        "subtotal": round_cents(subtotal),
        "discount_amount": discount_amount,
        "promo_code": promo_code_data["code"] if promo_code_data else None,
        "fee": 0.0,
        "total": 0.0,  # Free!
        "currency": order_items[0]["product"].get("currency", "USD"),
        "base_currency": base_currency,
        "payment_method": "free",
        "terms_id_used": terms_id,
        "rendered_terms_text": rendered_terms_text,
        "terms_accepted_at": now_iso(),

        "notes_json": build_checkout_notes_json(order_items, payload, user["id"], customer["id"], payment_method="free", promo_data=promo_code_data),
        "extra_fields": payload.extra_fields or {},
        "payment_date": now_iso(),
        "created_at": now_iso(),
    }
    await db.orders.insert_one(order_doc)
    await create_audit_log(
        entity_type="order",
        entity_id=order_id,
        action="created",
        actor="customer",
        details={"status": "paid", "payment_method": "free", "total": 0.0, "currency": order_items[0]["product"].get("currency", "USD"), "base_currency": base_currency},
    )
    
    if promo_code_data:
        await db.promo_codes.update_one({"id": promo_code_data["id"]}, {"$inc": {"usage_count": 1}})

    for item in order_items:
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
        # Log intake question answers
        intake_answers = item.get("inputs") or {}
        if intake_answers:
            await create_audit_log(
                entity_type="order",
                entity_id=order_id,
                action="intake_submitted",
                actor="customer",
                details={
                    "product_id": product["id"],
                    "product_name": product.get("name", ""),
                    "intake_answers": intake_answers,
                    "order_number": order_number,
                },
            )

    await db.invoices.insert_one({
        "id": make_id(),
        "order_id": order_id,
        "subscription_id": None,
        "stripe_invoice_id": None,
        "zoho_books_invoice_id": None,
        "amount_paid": 0.0,
        "status": "paid",
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
    
    # Send confirmation email
    from services.email_service import EmailService
    await EmailService.send(
        trigger="order_placed",
        recipient=user["email"],
        variables={
            "customer_name": user.get("full_name", ""),
            "customer_email": user["email"],
            "order_number": order_number,
            "order_total": "0.00",
            "order_currency": order_items[0]["product"].get("currency", "USD"),
        },
        db=db,
        tenant_id=tenant_id
    )

    return {
        "message": "Order completed successfully",
        "order_id": order_id,
        "order_number": order_number,
        "status": "paid",
        "total": 0.0,
    }
