"""Stripe and GoCardless webhook handlers."""
from __future__ import annotations

import hmac
import hashlib
import json
import os

from fastapi import APIRouter, HTTPException, Request

from core.helpers import make_id, now_iso, round_cents
from db.session import db
from services.audit_service import AuditService, create_audit_log
from services.settings_service import SettingsService
from core.constants import SERVICE_FEE_RATE
from core.config import STRIPE_API_KEY

try:
    from emergentintegrations.payments.stripe import StripeCheckout
except ImportError:
    StripeCheckout = None  # type: ignore

from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/api", tags=["webhooks"])


async def get_stripe_key_for_webhook() -> str:
    """Get Stripe key - check oauth_connections first, fallback to env.
    
    For webhooks, we use the first validated Stripe connection we find,
    or fallback to the environment variable since webhooks need to work
    even if no connection is explicitly configured.
    """
    conn = await db.oauth_connections.find_one(
        {"provider": "stripe", "is_validated": True},
        {"_id": 0, "credentials": 1}
    )
    if conn:
        return conn.get("credentials", {}).get("api_key") or STRIPE_API_KEY
    return STRIPE_API_KEY


async def get_stripe_fee_rate_for_tenant(tenant_id: str) -> float:
    """Get Stripe fee rate from oauth_connections."""
    conn = await db.oauth_connections.find_one(
        {"tenant_id": tenant_id, "provider": "stripe", "is_validated": True},
        {"_id": 0, "settings": 1}
    )
    if conn:
        return float(conn.get("settings", {}).get("fee_rate", SERVICE_FEE_RATE))
    return SERVICE_FEE_RATE


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    _stripe_key = await get_stripe_key_for_webhook()
    stripe_checkout = StripeCheckout(api_key=_stripe_key, webhook_url="")
    body = await request.body()
    webhook_response = await stripe_checkout.handle_webhook(body, request.headers.get("Stripe-Signature"))

    existing = await db.audit_logs.find_one(
        {"action": "stripe_event", "payload.event_id": webhook_response.event_id},
        {"_id": 0},
    )
    if existing:
        return {"status": "ignored"}

    await db.audit_logs.insert_one({
        "id": make_id(),
        "actor": "stripe",
        "action": "stripe_event",
        "payload": {
            "event_id": webhook_response.event_id,
            "event_type": webhook_response.event_type,
            "session_id": webhook_response.session_id,
            "payment_status": webhook_response.payment_status,
            "metadata": webhook_response.metadata,
        },
        "created_at": now_iso(),
    })
    await AuditService.log(
        action=f"WEBHOOK_STRIPE_{webhook_response.event_type.upper().replace('.', '_')}",
        description=f"Stripe webhook received: {webhook_response.event_type}",
        entity_type="Payment",
        entity_id=webhook_response.session_id,
        actor_type="webhook",
        actor_id="stripe",
        source="webhook",
        meta_json={
            "event_id": webhook_response.event_id,
            "event_type": webhook_response.event_type,
            "payment_status": webhook_response.payment_status,
            "metadata": webhook_response.metadata,
        },
    )

    metadata = webhook_response.metadata or {}
    order_id = metadata.get("order_id")
    email_target = None
    if order_id:
        order = await db.orders.find_one({"id": order_id}, {"_id": 0})
        if order:
            customer = await db.customers.find_one({"id": order.get("customer_id")}, {"_id": 0})
            if customer:
                user = await db.users.find_one({"id": customer["user_id"]}, {"_id": 0})
                if user:
                    email_target = user["email"]

    if webhook_response.event_type == "invoice.paid":
        # Parse raw Stripe event body for subscription renewal data.
        # Renewal invoices do NOT carry the original order metadata, so we
        # must look up our subscription via stripe_subscription_id instead.
        try:
            raw_event = json.loads(body)
            invoice_obj = raw_event.get("data", {}).get("object", {})
            stripe_invoice_id = invoice_obj.get("id") or f"inv_{webhook_response.event_id}"
            stripe_sub_id = invoice_obj.get("subscription")
            billing_reason = invoice_obj.get("billing_reason", "")
        except Exception:
            stripe_invoice_id = f"inv_{webhook_response.event_id}"
            stripe_sub_id = None
            billing_reason = ""

        # "subscription_create" is the initial payment — already handled by checkout_status.
        # Only process renewals (subscription_cycle) or any other reason except subscription_create.
        if billing_reason != "subscription_create" and stripe_sub_id:
            existing_renewal = await db.orders.find_one({"stripe_invoice_id": stripe_invoice_id}, {"_id": 0})
            if not existing_renewal:
                subscription = await db.subscriptions.find_one(
                    {"stripe_subscription_id": stripe_sub_id}, {"_id": 0}
                )
                if subscription:
                    customer_for_fee = await db.customers.find_one(
                        {"id": subscription["customer_id"]}, {"_id": 0}
                    )
                    tenant_id = customer_for_fee.get("tenant_id", "") if customer_for_fee else ""
                    fee_rate = await get_stripe_fee_rate_for_tenant(tenant_id)

                    renewal_amount = subscription.get("amount", 0)
                    renewal_tax = subscription.get("tax_amount", 0.0)
                    renewal_fee = round_cents(renewal_amount * fee_rate)
                    renewal_total = round_cents(renewal_amount + renewal_fee + renewal_tax)
                    renewal_order_id = make_id()
                    renewal_order_number = f"AA-{renewal_order_id.split('-')[0].upper()}"

                    renewal_doc = {
                        "id": renewal_order_id,
                        "order_number": renewal_order_number,
                        "tenant_id": tenant_id,
                        "customer_id": subscription["customer_id"],
                        "type": "subscription_renewal",
                        "status": "paid",
                        "subtotal": renewal_amount,
                        "discount_amount": 0.0,
                        "fee": renewal_fee,
                        "total": renewal_total,
                        "tax_amount": renewal_tax,
                        "tax_rate": subscription.get("tax_rate", 0.0),
                        "tax_name": subscription.get("tax_name"),
                        "currency": subscription.get("currency"),
                        "base_currency": subscription.get("base_currency"),
                        "base_currency_amount": renewal_total,
                        "payment_method": "card",
                        "stripe_invoice_id": stripe_invoice_id,
                        "subscription_id": subscription["id"],
                        "subscription_number": subscription.get("subscription_number", ""),
                        "payment_date": now_iso(),
                        "created_at": now_iso(),
                    }
                    await db.orders.insert_one(renewal_doc)
                    await create_audit_log(
                        entity_type="order",
                        entity_id=renewal_order_id,
                        action="created_renewal",
                        actor="stripe_webhook",
                        details={
                            "subscription_id": subscription["id"],
                            "stripe_invoice_id": stripe_invoice_id,
                            "stripe_subscription_id": stripe_sub_id,
                            "amount": renewal_total,
                            "billing_reason": billing_reason,
                        },
                    )

                    # Copy order items from the original subscription_start order
                    original_order_for_items = await db.orders.find_one(
                        {"subscription_id": subscription["id"], "type": "subscription_start"},
                        {"_id": 0, "id": 1}
                    )
                    if original_order_for_items:
                        original_items = await db.order_items.find(
                            {"order_id": original_order_for_items["id"]}, {"_id": 0}
                        ).to_list(100)
                        for item in original_items:
                            await db.order_items.insert_one({
                                "id": make_id(),
                                "order_id": renewal_order_id,
                                "product_id": item["product_id"],
                                "quantity": item["quantity"],
                                "metadata_json": item.get("metadata_json"),
                                "unit_price": item["unit_price"],
                                "line_total": item["line_total"],
                            })

                    await db.zoho_sync_logs.insert_one({
                        "id": make_id(),
                        "entity_type": "subscription_renewal",
                        "entity_id": renewal_order_id,
                        "status": "Not Sent",
                        "last_error": None,
                        "attempts": 0,
                        "created_at": now_iso(),
                        "mocked": True,
                    })

                    # Resolve email target from subscription customer
                    if not email_target and customer_for_fee:
                        renewal_user = await db.users.find_one(
                            {"id": customer_for_fee["user_id"]}, {"_id": 0}
                        )
                        if renewal_user:
                            email_target = renewal_user["email"]

                    # Dispatch subscription.renewed webhook event
                    from services.webhook_service import dispatch_event as _dispatch
                    await _dispatch(
                        event="subscription.renewed",
                        data={
                            "id": subscription["id"],
                            "subscription_number": subscription.get("subscription_number", ""),
                            "plan_name": subscription.get("plan_name", ""),
                            "amount": renewal_amount,
                            "currency": subscription.get("currency", ""),
                            "customer_email": email_target or "",
                            "next_billing_date": subscription.get("renewal_date", ""),
                            "renewed_at": now_iso(),
                        },
                        tenant_id=tenant_id,
                    )

                    # Send renewal email notification
                    if email_target:
                        await db.email_outbox.insert_one({
                            "id": make_id(),
                            "to": email_target,
                            "subject": "Subscription renewal paid",
                            "body": "Your subscription renewal has been paid successfully.",
                            "type": "subscription_renewal",
                            "status": "MOCKED",
                            "created_at": now_iso(),
                        })

    if webhook_response.event_type == "payment_intent.payment_failed" and email_target:
        await db.email_outbox.insert_one({
            "id": make_id(),
            "to": email_target,
            "subject": "Payment failed",
            "body": "Your payment failed. Please update your payment method.",
            "type": "payment_failed",
            "status": "MOCKED",
            "created_at": now_iso(),
        })

    # ------------------------------------------------------------------
    # Partner Billing — handle Stripe events for partner subscriptions/orders
    # ------------------------------------------------------------------
    try:
        raw_event = json.loads(body)
        event_obj = raw_event.get("data", {}).get("object", {})
        event_meta = event_obj.get("metadata", {})

        if event_meta.get("type") == "partner_subscription":
            partner_sub_id = event_meta.get("partner_subscription_id")
            if partner_sub_id and webhook_response.event_type in (
                "checkout.session.completed",
                "invoice.paid",
                "customer.subscription.updated",
                "customer.subscription.deleted",
            ):
                psub = await db.partner_subscriptions.find_one({"id": partner_sub_id}, {"_id": 0})
                if psub:
                    if webhook_response.event_type == "checkout.session.completed":
                        stripe_sub_id = event_obj.get("subscription")
                        await db.partner_subscriptions.update_one(
                            {"id": partner_sub_id},
                            {"$set": {
                                "status": "active",
                                "stripe_subscription_id": stripe_sub_id,
                                "updated_at": now_iso(),
                            }},
                        )
                        await create_audit_log(
                            entity_type="partner_subscription", entity_id=partner_sub_id,
                            action="activated_via_stripe", actor="stripe_webhook",
                            details={"stripe_subscription_id": stripe_sub_id},
                        )
                    elif webhook_response.event_type == "invoice.paid":
                        stripe_sub_id = event_obj.get("subscription")
                        billing_reason = event_obj.get("billing_reason", "")
                        if billing_reason != "subscription_create":
                            # Renewal — create a partner_order record
                            renewal_id = make_id()
                            count = await db.partner_orders.count_documents({})
                            renewal_number = f"PO-{__import__('datetime').datetime.now().strftime('%Y')}-{(count + 1):04d}"
                            await db.partner_orders.insert_one({
                                "id": renewal_id,
                                "order_number": renewal_number,
                                "partner_id": psub["partner_id"],
                                "partner_name": psub.get("partner_name", ""),
                                "plan_id": psub.get("plan_id"),
                                "plan_name": psub.get("plan_name"),
                                "description": f"Subscription renewal — {psub.get('plan_name') or psub.get('description', '')}",
                                "amount": psub.get("amount", 0),
                                "currency": psub.get("currency", "GBP"),
                                "status": "paid",
                                "payment_method": "card",
                                "processor_id": stripe_sub_id,
                                "invoice_date": now_iso()[:10],
                                "paid_at": now_iso(),
                                "internal_note": "Auto-created from Stripe renewal",
                                "created_by": "stripe_webhook",
                                "created_at": now_iso(),
                                "updated_at": now_iso(),
                            })
                            await create_audit_log(
                                entity_type="partner_order", entity_id=renewal_id,
                                action="created_renewal", actor="stripe_webhook",
                                details={"subscription_id": partner_sub_id, "stripe_sub_id": stripe_sub_id},
                            )
                    elif webhook_response.event_type == "customer.subscription.deleted":
                        await db.partner_subscriptions.update_one(
                            {"id": partner_sub_id},
                            {"$set": {"status": "cancelled", "cancelled_at": now_iso(), "updated_at": now_iso()}},
                        )

        elif event_meta.get("type") == "partner_order":
            partner_order_id = event_meta.get("partner_order_id")
            if partner_order_id and webhook_response.event_type == "checkout.session.completed":
                await db.partner_orders.update_one(
                    {"id": partner_order_id},
                    {"$set": {"status": "paid", "paid_at": now_iso(), "updated_at": now_iso()}},
                )
                await create_audit_log(
                    entity_type="partner_order", entity_id=partner_order_id,
                    action="paid_via_stripe", actor="stripe_webhook", details={},
                )

        elif event_meta.get("billing_type") == "partner":
            # ------------------------------------------------------------------
            # New-style partner billing: platform admin sets billing_type=partner
            # + partner_id (and optionally plan_id, description) in Stripe metadata.
            # This lets Stripe-native subscriptions/payments auto-create partner records.
            # ------------------------------------------------------------------
            partner_id = event_meta.get("partner_id")
            if not partner_id:
                pass  # Cannot route without partner_id
            elif webhook_response.event_type == "checkout.session.completed":
                stripe_payment_intent = event_obj.get("payment_intent")
                stripe_sub_id = event_obj.get("subscription")
                amount_total = event_obj.get("amount_total", 0) / 100  # Stripe amounts are in cents

                tenant = await db.tenants.find_one({"id": partner_id}, {"_id": 0, "name": 1, "code": 1}) or {}
                plan_id = event_meta.get("plan_id")
                plan_name = event_meta.get("plan_name", "")
                description = event_meta.get("description", "Stripe payment")
                currency = event_obj.get("currency", "gbp").upper()

                if stripe_sub_id:
                    # Stripe subscription created — make a partner_subscription record
                    count = await db.partner_subscriptions.count_documents({})
                    sub_number = f"PS-{__import__('datetime').datetime.now().strftime('%Y')}-{(count + 1):04d}"
                    new_sub_id = make_id()
                    await db.partner_subscriptions.insert_one({
                        "id": new_sub_id,
                        "subscription_number": sub_number,
                        "partner_id": partner_id,
                        "partner_name": tenant.get("name", ""),
                        "plan_id": plan_id,
                        "plan_name": plan_name,
                        "description": description,
                        "amount": round(amount_total, 2),
                        "currency": currency,
                        "billing_interval": event_meta.get("billing_interval", "monthly"),
                        "status": "active",
                        "payment_method": "card",
                        "stripe_subscription_id": stripe_sub_id,
                        "start_date": now_iso()[:10],
                        "next_billing_date": None,
                        "cancelled_at": None,
                        "internal_note": "Auto-created via Stripe webhook (billing_type=partner)",
                        "created_by": "stripe_webhook",
                        "payment_url": None,
                        "created_at": now_iso(),
                        "updated_at": now_iso(),
                    })
                    await create_audit_log(
                        entity_type="partner_subscription", entity_id=new_sub_id,
                        action="created_via_stripe_webhook", actor="stripe_webhook",
                        details={"stripe_subscription_id": stripe_sub_id, "partner_id": partner_id},
                    )
                else:
                    # One-time payment — make a partner_order record
                    count = await db.partner_orders.count_documents({})
                    order_number = f"PO-{__import__('datetime').datetime.now().strftime('%Y')}-{(count + 1):04d}"
                    new_order_id = make_id()
                    await db.partner_orders.insert_one({
                        "id": new_order_id,
                        "order_number": order_number,
                        "partner_id": partner_id,
                        "partner_name": tenant.get("name", ""),
                        "plan_id": plan_id,
                        "plan_name": plan_name,
                        "description": description,
                        "amount": round(amount_total, 2),
                        "currency": currency,
                        "status": "paid",
                        "payment_method": "card",
                        "processor_id": stripe_payment_intent,
                        "invoice_date": now_iso()[:10],
                        "paid_at": now_iso(),
                        "internal_note": "Auto-created via Stripe webhook (billing_type=partner)",
                        "created_by": "stripe_webhook",
                        "created_at": now_iso(),
                        "updated_at": now_iso(),
                    })
                    await create_audit_log(
                        entity_type="partner_order", entity_id=new_order_id,
                        action="created_via_stripe_webhook", actor="stripe_webhook",
                        details={"stripe_payment_intent": stripe_payment_intent, "partner_id": partner_id},
                    )

            elif webhook_response.event_type == "customer.subscription.deleted":
                stripe_sub_id = event_obj.get("id")
                if stripe_sub_id:
                    await db.partner_subscriptions.update_many(
                        {"stripe_subscription_id": stripe_sub_id},
                        {"$set": {"status": "cancelled", "cancelled_at": now_iso(), "updated_at": now_iso()}},
                    )
    except Exception:
        pass  # Never let partner billing processing break the main webhook response

    return {"status": "ok"}


@router.post("/webhook/gocardless")
async def gocardless_webhook(request: Request):
    """Handle GoCardless webhook events (payments, mandates)."""
    body = await request.body()
    signature = request.headers.get("Webhook-Signature", "")

    # Verify HMAC-SHA256 signature
    gc_webhook_secret = await SettingsService.get("gocardless_webhook_secret") or os.environ.get("GOCARDLESS_WEBHOOK_SECRET", "")
    if gc_webhook_secret and signature:
        expected = hmac.new(gc_webhook_secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise HTTPException(status_code=498, detail="Invalid webhook signature")

    try:
        payload = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    events = payload.get("events", [])

    for event in events:
        resource_type = event.get("resource_type", "")  # "payments", "mandates"
        action = event.get("action", "")
        links = event.get("links", {})
        payment_id = links.get("payment")
        mandate_id = links.get("mandate")
        event_id = event.get("id", make_id())

        # Deduplicate
        existing = await db.audit_logs.find_one(
            {"action": "gocardless_event", "entity_id": event_id}, {"_id": 0}
        )
        if existing:
            continue

        await db.audit_logs.insert_one({
            "id": make_id(),
            "actor": "gocardless_webhook",
            "action": "gocardless_event",
            "entity_type": resource_type,
            "entity_id": event_id,
            "details": {"resource_type": resource_type, "action": action, "links": links},
            "created_at": now_iso(),
        })

        if resource_type == "payments" and payment_id:
            # Check orders
            order = await db.orders.find_one({"gocardless_payment_id": payment_id}, {"_id": 0})
            if order:
                if action == "confirmed":
                    await db.orders.update_one(
                        {"id": order["id"]},
                        {"$set": {"status": "paid", "payment_date": now_iso(), "updated_at": now_iso()}},
                    )
                    await create_audit_log(
                        entity_type="order", entity_id=order["id"],
                        action="payment_confirmed", actor="gocardless_webhook",
                        details={"payment_id": payment_id, "gocardless_event": action},
                    )
                elif action in ("failed", "charged_back"):
                    await db.orders.update_one(
                        {"id": order["id"]},
                        {"$set": {"status": "unpaid", "updated_at": now_iso()}},
                    )
                    await create_audit_log(
                        entity_type="order", entity_id=order["id"],
                        action="payment_failed", actor="gocardless_webhook",
                        details={"payment_id": payment_id, "gocardless_event": action},
                    )

            # Check subscriptions — by initial payment_id first
            sub = await db.subscriptions.find_one({"gocardless_payment_id": payment_id}, {"_id": 0})
            if sub:
                if action == "confirmed":
                    await db.subscriptions.update_one(
                        {"id": sub["id"]},
                        {"$set": {"status": "active", "updated_at": now_iso()}},
                    )
                    await create_audit_log(
                        entity_type="subscription", entity_id=sub["id"],
                        action="payment_confirmed", actor="gocardless_webhook",
                        details={"payment_id": payment_id, "gocardless_event": action},
                    )
                elif action in ("failed", "charged_back"):
                    await db.subscriptions.update_one(
                        {"id": sub["id"]},
                        {"$set": {"status": "unpaid", "updated_at": now_iso()}},
                    )
                    await create_audit_log(
                        entity_type="subscription", entity_id=sub["id"],
                        action="payment_failed", actor="gocardless_webhook",
                        details={"payment_id": payment_id, "gocardless_event": action},
                    )
            elif action == "confirmed" and mandate_id:
                # Not the initial payment — check if this mandate belongs to an active subscription.
                # If so, this is a renewal payment created against the same mandate.
                renewal_sub = await db.subscriptions.find_one(
                    {"gocardless_mandate_id": mandate_id, "status": "active"}, {"_id": 0}
                )
                if renewal_sub:
                    existing_renewal = await db.orders.find_one(
                        {"gocardless_payment_id": payment_id, "type": "subscription_renewal"},
                        {"_id": 0}
                    )
                    if not existing_renewal:
                        gc_customer_doc = await db.customers.find_one(
                            {"id": renewal_sub["customer_id"]}, {"_id": 0}
                        )
                        tenant_id = gc_customer_doc.get("tenant_id", "") if gc_customer_doc else ""

                        renewal_amount = renewal_sub.get("amount", 0)
                        renewal_tax = renewal_sub.get("tax_amount", 0.0)
                        renewal_total = round_cents(renewal_amount + renewal_tax)
                        renewal_order_id = make_id()
                        renewal_order_number = f"AA-{renewal_order_id.split('-')[0].upper()}"

                        gc_renewal_doc = {
                            "id": renewal_order_id,
                            "order_number": renewal_order_number,
                            "tenant_id": tenant_id,
                            "customer_id": renewal_sub["customer_id"],
                            "type": "subscription_renewal",
                            "status": "paid",
                            "subtotal": renewal_amount,
                            "discount_amount": 0.0,
                            "fee": 0.0,
                            "total": renewal_total,
                            "tax_amount": renewal_tax,
                            "tax_rate": renewal_sub.get("tax_rate", 0.0),
                            "tax_name": renewal_sub.get("tax_name"),
                            "currency": renewal_sub.get("currency"),
                            "base_currency": renewal_sub.get("base_currency"),
                            "base_currency_amount": renewal_total,
                            "payment_method": "bank_transfer",
                            "gocardless_payment_id": payment_id,
                            "gocardless_mandate_id": mandate_id,
                            "subscription_id": renewal_sub["id"],
                            "subscription_number": renewal_sub.get("subscription_number", ""),
                            "payment_date": now_iso(),
                            "created_at": now_iso(),
                        }
                        await db.orders.insert_one(gc_renewal_doc)
                        await create_audit_log(
                            entity_type="order",
                            entity_id=renewal_order_id,
                            action="created_renewal",
                            actor="gocardless_webhook",
                            details={
                                "subscription_id": renewal_sub["id"],
                                "payment_id": payment_id,
                                "mandate_id": mandate_id,
                                "amount": renewal_total,
                            },
                        )
                        await db.zoho_sync_logs.insert_one({
                            "id": make_id(),
                            "entity_type": "subscription_renewal",
                            "entity_id": renewal_order_id,
                            "status": "Not Sent",
                            "last_error": None,
                            "attempts": 0,
                            "created_at": now_iso(),
                            "mocked": True,
                        })

                        # Dispatch subscription.renewed event
                        from services.webhook_service import dispatch_event as _dispatch_gc
                        if gc_customer_doc:
                            gc_user = await db.users.find_one(
                                {"id": gc_customer_doc["user_id"]}, {"_id": 0, "email": 1}
                            )
                            gc_email = gc_user["email"] if gc_user else ""
                        else:
                            gc_email = ""
                        await _dispatch_gc(
                            event="subscription.renewed",
                            data={
                                "id": renewal_sub["id"],
                                "subscription_number": renewal_sub.get("subscription_number", ""),
                                "plan_name": renewal_sub.get("plan_name", ""),
                                "amount": renewal_amount,
                                "currency": renewal_sub.get("currency", ""),
                                "customer_email": gc_email,
                                "next_billing_date": renewal_sub.get("renewal_date", ""),
                                "renewed_at": now_iso(),
                            },
                            tenant_id=tenant_id,
                        )

                        # Renewal email notification
                        if gc_email:
                            await db.email_outbox.insert_one({
                                "id": make_id(),
                                "to": gc_email,
                                "subject": "Subscription renewal paid",
                                "body": "Your subscription renewal has been paid successfully.",
                                "type": "subscription_renewal",
                                "status": "MOCKED",
                                "created_at": now_iso(),
                            })

        elif resource_type == "mandates" and mandate_id:
            if action in ("cancelled", "failed", "expired"):
                # Mark any active subscriptions with this mandate as unpaid
                await db.subscriptions.update_many(
                    {"gocardless_mandate_id": mandate_id, "status": "active"},
                    {"$set": {"status": "unpaid", "updated_at": now_iso()}},
                )
                await create_audit_log(
                    entity_type="subscription", entity_id=mandate_id,
                    action=f"mandate_{action}", actor="gocardless_webhook",
                    details={"mandate_id": mandate_id, "gocardless_event": action},
                )

    return {"status": "ok"}
