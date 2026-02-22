"""Checkout routes: Stripe session, bank transfer, checkout status."""
from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from core.helpers import make_id, now_iso, round_cents
from core.security import get_current_user
from core.config import STRIPE_API_KEY, GOCARDLESS_ACCESS_TOKEN, GOCARDLESS_ENVIRONMENT
from db.session import db
from models import CheckoutSessionRequestBody, BankTransferCheckoutRequest
from services.audit_service import create_audit_log
from services.checkout_service import (
    build_order_items,
    build_checkout_notes_json,
    validate_and_consume_partner_tag,
    resolve_terms_tags,
)
from services.settings_service import SettingsService
from core.constants import SERVICE_FEE_RATE

try:
    from emergentintegrations.payments.stripe import (
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
    if not customer.get("allow_bank_transfer", True):
        raise HTTPException(status_code=403, detail="Bank transfer not enabled")

    await validate_and_consume_partner_tag(
        customer_id=customer["id"],
        partner_tag_response=payload.partner_tag_response,
        override_code=payload.override_code,
        order_id=None,
    )

    order_items = await build_order_items(payload.items)

    if any(i["product"].get("sku") == "MIG-CRM" for i in order_items) and any(
        i["product"].get("sku") == "START-ZOHO-CRM-EXP" for i in order_items
    ):
        raise HTTPException(status_code=400, detail="CRM data migration is included in CRM Express Setup")

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

        terms_id = payload.terms_id if payload.terms_id else product.get("terms_id")
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

        if not gc_customer_id and create_gocardless_customer:
            name_parts = user.get("full_name", "Customer User").split()
            gc_customer = create_gocardless_customer(
                email=user["email"],
                given_name=name_parts[0],
                family_name=name_parts[-1] if len(name_parts) > 1 else "User",
                company_name=user.get("company_name", ""),
                gc_token=await SettingsService.get("gocardless_access_token") or GOCARDLESS_ACCESS_TOKEN,
                gc_env=await SettingsService.get("gocardless_environment", GOCARDLESS_ENVIRONMENT),
            )
            if gc_customer:
                gc_customer_id = gc_customer["id"]
                await db.customers.update_one({"id": customer["id"]}, {"$set": {"gocardless_customer_id": gc_customer_id}})

        if gc_customer_id and create_redirect_flow:
            session_token = make_id()
            frontend_url = os.environ.get("FRONTEND_URL", os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:3000").replace("/api", ""))
            success_url = f"{frontend_url}/gocardless/callback?session_token={session_token}&subscription_id={sub_id}"
            redirect_flow = create_redirect_flow(
                session_token=session_token,
                success_redirect_url=success_url,
                description=f"Direct Debit for {product['name']}",
                gc_token=await SettingsService.get("gocardless_access_token") or GOCARDLESS_ACCESS_TOKEN,
                gc_env=await SettingsService.get("gocardless_environment", GOCARDLESS_ENVIRONMENT),
            )
            if redirect_flow:
                redirect_flow_id = redirect_flow["id"]
                gocardless_redirect_url = redirect_flow["redirect_url"]

        await db.subscriptions.insert_one({
            "id": sub_id,
            "order_id": None,
            "customer_id": customer["id"],
            "plan_name": product["name"],
            "status": "pending_direct_debit_setup",
            "stripe_subscription_id": None,
            "gocardless_customer_id": gc_customer_id,
            "gocardless_redirect_flow_id": redirect_flow_id,
            "current_period_start": period_start.isoformat(),
            "current_period_end": period_end.isoformat(),
            "cancel_at_period_end": False,
            "canceled_at": None,
            "amount": subtotal,
            "payment_method": "bank_transfer",
            "terms_id_used": terms_id,
            "rendered_terms_text": rendered_terms_text,
            "terms_accepted_at": now_iso(),
            "start_date": requested_start or period_start.isoformat(),
            "contract_end_date": contract_end.isoformat(),
            "partner_tag_response": payload.partner_tag_response,
            "override_code_id": None,
            "partner_tag_timestamp": now_iso(),
            "notes_json": build_checkout_notes_json(order_items, payload, user["id"], customer["id"], payment_method="bank_transfer"),
        })
        await create_audit_log(
            entity_type="subscription", entity_id=sub_id,
            action="created", actor="customer",
            details={"status": "pending_direct_debit_setup", "payment_method": "bank_transfer"},
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

    if not gc_customer_id and create_gocardless_customer:
        name_parts = user.get("full_name", "Customer User").split()
        gc_customer = create_gocardless_customer(
            email=user["email"],
            given_name=name_parts[0],
            family_name=name_parts[-1] if len(name_parts) > 1 else "User",
            company_name=user.get("company_name", ""),
            gc_token=await SettingsService.get("gocardless_access_token") or GOCARDLESS_ACCESS_TOKEN,
            gc_env=await SettingsService.get("gocardless_environment", GOCARDLESS_ENVIRONMENT),
        )
        if gc_customer:
            gc_customer_id = gc_customer["id"]
            await db.customers.update_one({"id": customer["id"]}, {"$set": {"gocardless_customer_id": gc_customer_id}})

    if gc_customer_id and create_redirect_flow:
        session_token = make_id()
        frontend_url = os.environ.get("FRONTEND_URL", os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:3000").replace("/api", ""))
        success_url = f"{frontend_url}/gocardless/callback?session_token={session_token}&order_id={order_id}"
        redirect_flow = create_redirect_flow(
            session_token=session_token,
            success_redirect_url=success_url,
            description=f"Payment for Order {order_number}",
            gc_token=await SettingsService.get("gocardless_access_token") or GOCARDLESS_ACCESS_TOKEN,
            gc_env=await SettingsService.get("gocardless_environment", GOCARDLESS_ENVIRONMENT),
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
        "fee": 0.0, "total": total, "currency": customer.get("currency"),
        "payment_method": "bank_transfer",
        "gocardless_redirect_flow_id": redirect_flow_id,
        "terms_id_used": terms_id, "rendered_terms_text": rendered_terms_text,
        "terms_accepted_at": now_iso(), "partner_tag_response": payload.partner_tag_response,
        "override_code_id": None, "partner_tag_timestamp": now_iso(),
        "notes_json": build_checkout_notes_json(order_items, payload, user["id"], customer["id"], payment_method="bank_transfer"),
        "created_at": now_iso(),
    }
    await db.orders.insert_one(order_doc)
    await create_audit_log(
        entity_type="order", entity_id=order_id, action="created", actor="customer",
        details={"status": "pending_direct_debit_setup", "payment_method": "bank_transfer", "total": total},
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
    if customer.get("currency") not in ["USD", "CAD"]:
        raise HTTPException(status_code=400, detail="Purchases not supported in your region yet")

    if not payload.zoho_subscription_type:
        raise HTTPException(status_code=400, detail="Please select your current Zoho subscription type.")
    if not payload.current_zoho_product:
        raise HTTPException(status_code=400, detail="Please select your current Zoho product.")
    if not payload.zoho_account_access:
        raise HTTPException(status_code=400, detail="Please indicate whether you have provided Zoho account access.")

    await validate_and_consume_partner_tag(
        customer_id=customer["id"],
        partner_tag_response=payload.partner_tag_response,
        override_code=payload.override_code,
        order_id=None,
    )

    order_items = await build_order_items(payload.items)

    if any(i["product"].get("sku") == "MIG-CRM" for i in order_items) and any(
        i["product"].get("sku") == "START-ZOHO-CRM-EXP" for i in order_items
    ):
        raise HTTPException(status_code=400, detail="CRM data migration is included in CRM Express Setup")

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
        stripe_price_id = product.get("stripe_price_id")
        if not stripe_price_id:
            raise HTTPException(status_code=400, detail=f"Subscription product '{product.get('name')}' is not configured for card payment. Missing Stripe Price ID.")

    if checkout_type == "one_time":
        for item in order_items:
            if item["pricing"].get("is_subscription"):
                raise HTTPException(status_code=400, detail="One-time checkout cannot include subscriptions")
            if item["pricing"].get("is_scope_request") or item["product"].get("pricing_type") in ["external", "inquiry"]:
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

    _fee_rate = float(await SettingsService.get("service_fee_rate", SERVICE_FEE_RATE))
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
        "fee": fee, "total": total, "currency": customer.get("currency"),
        "payment_method": "card",
        "terms_id_used": terms_id, "rendered_terms_text": rendered_terms_text,
        "terms_accepted_at": now_iso(), "partner_tag_response": payload.partner_tag_response,
        "override_code_id": None, "partner_tag_timestamp": now_iso(),
        "notes_json": build_checkout_notes_json(order_items, payload, user["id"], customer["id"], payment_method="card"),
        "created_at": now_iso(),
    }
    await db.orders.insert_one(order_doc)
    await create_audit_log(
        entity_type="order", entity_id=order_id, action="created", actor="system",
        details={"checkout_type": checkout_type, "payment_method": "card", "total": total},
    )

    for item in order_items:
        product = item["product"]
        await db.order_items.insert_one({
            "id": make_id(), "order_id": order_id, "product_id": product["id"],
            "quantity": item["quantity"], "metadata_json": item["inputs"],
            "unit_price": item["pricing"]["subtotal"], "line_total": item["pricing"]["subtotal"],
        })

    host_url = payload.origin_url.rstrip("/")
    success_url = f"{host_url}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{host_url}/cart"
    _stripe_key = await SettingsService.get("stripe_secret_key") or STRIPE_API_KEY
    stripe_checkout = StripeCheckout(api_key=_stripe_key, webhook_url=f"{host_url}/api/webhook/stripe")
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
            stripe_sdk.api_key = STRIPE_API_KEY
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
            currency=customer.get("currency", "USD").lower(),
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
        "currency": customer.get("currency"), "metadata": metadata,
        "user_id": user["id"], "order_id": order_id,
        "created_at": now_iso(), "updated_at": now_iso(),
    })
    return {"url": session_response.url, "session_id": session_response.session_id, "order_id": order_id}


@router.get("/checkout/status/{session_id}")
async def checkout_status(
    session_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url="")
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
            await db.orders.update_one({"id": order["id"]}, {"$set": {"status": "paid"}})
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
                    if items:
                        product = await db.products.find_one({"id": items[0]["product_id"]}, {"_id": 0})
                        if product:
                            product_name = product["name"]
                    period_start = datetime.now(timezone.utc)
                    period_end = period_start + timedelta(days=30)
                    sub_id = make_id()
                    await db.subscriptions.insert_one({
                        "id": sub_id, "order_id": order["id"], "customer_id": order["customer_id"],
                        "plan_name": product_name, "status": "active",
                        "stripe_subscription_id": None,
                        "current_period_start": period_start.isoformat(),
                        "current_period_end": period_end.isoformat(),
                        "cancel_at_period_end": False, "canceled_at": None,
                        "amount": order.get("total"), "payment_method": "card",
                        "partner_tag_response": order.get("partner_tag_response"),
                        "override_code_id": order.get("override_code_id"),
                        "partner_tag_timestamp": order.get("partner_tag_timestamp"),
                    })
                    await db.email_outbox.insert_one({
                        "id": make_id(), "to": user["email"],
                        "subject": "Subscription started",
                        "body": f"Your subscription {product_name} is active.",
                        "type": "subscription_started", "status": "MOCKED", "created_at": now_iso(),
                    })
            customer = await db.customers.find_one({"id": order["customer_id"]}, {"_id": 0})
            if customer and not customer.get("currency_locked"):
                await db.customers.update_one({"id": customer["id"]}, {"$set": {"currency_locked": True}})
            await db.email_outbox.insert_one({
                "id": make_id(), "to": user["email"],
                "subject": "Order confirmation",
                "body": f"Your order {order['order_number']} is confirmed.",
                "type": "order_confirmation", "status": "MOCKED", "created_at": now_iso(),
            })
    return {
        "status": status.status,
        "payment_status": status.payment_status,
        "amount_total": status.amount_total,
        "currency": status.currency,
        "metadata": status.metadata,
    }
