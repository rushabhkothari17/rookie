"""Stripe webhook handler."""
from __future__ import annotations

from fastapi import APIRouter, Request

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


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url="")
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
        stripe_invoice_id = webhook_response.metadata.get("stripe_invoice_id") or f"inv_{webhook_response.event_id}"
        existing_renewal = await db.orders.find_one({"stripe_invoice_id": stripe_invoice_id}, {"_id": 0})
        if not existing_renewal and order_id:
            original_order = await db.orders.find_one({"id": order_id}, {"_id": 0})
            if original_order and original_order.get("type") == "subscription_start":
                subscription = await db.subscriptions.find_one(
                    {"order_id": order_id, "status": "active"}, {"_id": 0}
                )
                if subscription:
                    renewal_order_id = make_id()
                    renewal_order_number = f"AA-{renewal_order_id.split('-')[0].upper()}"
                    renewal_amount = subscription.get("amount", 0)
                    fee_rate = float(await SettingsService.get("service_fee_rate", SERVICE_FEE_RATE))
                    renewal_fee = round_cents(renewal_amount * fee_rate)
                    renewal_total = round_cents(renewal_amount + renewal_fee)
                    renewal_doc = {
                        "id": renewal_order_id,
                        "order_number": renewal_order_number,
                        "customer_id": original_order["customer_id"],
                        "type": "subscription_renewal",
                        "status": "paid",
                        "subtotal": renewal_amount,
                        "discount_amount": 0.0,
                        "fee": renewal_fee,
                        "total": renewal_total,
                        "currency": original_order.get("currency"),
                        "payment_method": "card",
                        "stripe_invoice_id": stripe_invoice_id,
                        "subscription_id": subscription["id"],
                        "subscription_number": subscription.get("subscription_number", ""),
                        "created_at": now_iso(),
                    }
                    await db.orders.insert_one(renewal_doc)
                    await create_audit_log(
                        entity_type="order",
                        entity_id=renewal_order_id,
                        action="created_renewal",
                        actor="stripe_webhook",
                        details={"subscription_id": subscription["id"], "stripe_invoice_id": stripe_invoice_id, "amount": renewal_total},
                    )
                    original_items = await db.order_items.find({"order_id": order_id}, {"_id": 0}).to_list(100)
                    for item in original_items:
                        await db.order_items.insert_one({
                            "id": make_id(),
                            "order_id": renewal_order_id,
                            "product_id": item["product_id"],
                            "quantity": item["quantity"],
                            "metadata_json": item["metadata_json"],
                            "unit_price": item["unit_price"],
                            "line_total": item["line_total"],
                        })
                    await db.zoho_sync_logs.insert_one({
                        "id": make_id(),
                        "entity_type": "subscription_renewal",
                        "entity_id": renewal_order_id,
                        "status": "Sent",
                        "last_error": None,
                        "attempts": 1,
                        "created_at": now_iso(),
                        "mocked": True,
                    })
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

    return {"status": "ok"}
