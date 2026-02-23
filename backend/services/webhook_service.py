"""Webhook dispatch service — HMAC-signed, async delivery with retries."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from core.helpers import make_id, now_iso
from db.session import db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Event + Field Catalog (single source of truth for frontend field picker)
# ---------------------------------------------------------------------------
EVENT_CATALOG: Dict[str, Dict[str, Any]] = {
    # --- Orders ---
    "order.created": {
        "label": "Order Created",
        "category": "Orders",
        "fields": {
            "id": "Order ID",
            "order_number": "Order Number",
            "status": "Status",
            "total": "Total Amount",
            "currency": "Currency",
            "customer_email": "Customer Email",
            "customer_name": "Customer Name",
            "product_names": "Product Names",
            "items_count": "Items Count",
            "payment_method": "Payment Method",
            "created_at": "Created At",
        },
    },
    "order.updated": {
        "label": "Order Updated",
        "category": "Orders",
        "fields": {
            "id": "Order ID",
            "order_number": "Order Number",
            "status": "Status",
            "total": "Total Amount",
            "currency": "Currency",
            "customer_email": "Customer Email",
            "customer_name": "Customer Name",
            "updated_at": "Updated At",
        },
    },
    "order.status_changed": {
        "label": "Order Status Changed",
        "category": "Orders",
        "fields": {
            "id": "Order ID",
            "order_number": "Order Number",
            "previous_status": "Previous Status",
            "new_status": "New Status",
            "customer_email": "Customer Email",
            "customer_name": "Customer Name",
            "changed_at": "Changed At",
        },
    },
    # --- Subscriptions ---
    "subscription.created": {
        "label": "Subscription Created",
        "category": "Subscriptions",
        "fields": {
            "id": "Subscription ID",
            "subscription_number": "Subscription Number",
            "plan_name": "Plan Name",
            "status": "Status",
            "amount": "Amount",
            "currency": "Currency",
            "billing_frequency": "Billing Frequency",
            "customer_email": "Customer Email",
            "customer_name": "Customer Name",
            "start_date": "Start Date",
            "created_at": "Created At",
        },
    },
    "subscription.cancelled": {
        "label": "Subscription Cancelled",
        "category": "Subscriptions",
        "fields": {
            "id": "Subscription ID",
            "subscription_number": "Subscription Number",
            "plan_name": "Plan Name",
            "cancel_reason": "Cancellation Reason",
            "cancel_at_period_end": "Cancel at Period End",
            "customer_email": "Customer Email",
            "customer_name": "Customer Name",
            "cancelled_at": "Cancelled At",
        },
    },
    "subscription.renewed": {
        "label": "Subscription Renewed",
        "category": "Subscriptions",
        "fields": {
            "id": "Subscription ID",
            "subscription_number": "Subscription Number",
            "plan_name": "Plan Name",
            "amount": "Amount",
            "currency": "Currency",
            "customer_email": "Customer Email",
            "next_billing_date": "Next Billing Date",
            "renewed_at": "Renewed At",
        },
    },
    # --- Customers ---
    "customer.registered": {
        "label": "Customer Registered",
        "category": "Customers",
        "fields": {
            "id": "Customer ID",
            "email": "Email",
            "full_name": "Full Name",
            "company": "Company",
            "phone": "Phone",
            "country": "Country",
            "created_at": "Registered At",
        },
    },
    "customer.updated": {
        "label": "Customer Updated",
        "category": "Customers",
        "fields": {
            "id": "Customer ID",
            "email": "Email",
            "full_name": "Full Name",
            "company": "Company",
            "phone": "Phone",
            "updated_at": "Updated At",
        },
    },
    # --- Payments ---
    "payment.succeeded": {
        "label": "Payment Succeeded",
        "category": "Payments",
        "fields": {
            "id": "Payment ID",
            "amount": "Amount",
            "currency": "Currency",
            "processor": "Processor",
            "processor_id": "Processor Transaction ID",
            "order_id": "Order ID",
            "order_number": "Order Number",
            "customer_email": "Customer Email",
            "paid_at": "Paid At",
        },
    },
    "payment.failed": {
        "label": "Payment Failed",
        "category": "Payments",
        "fields": {
            "id": "Payment ID",
            "amount": "Amount",
            "currency": "Currency",
            "processor": "Processor",
            "error_code": "Error Code",
            "error_message": "Error Message",
            "order_id": "Order ID",
            "customer_email": "Customer Email",
            "failed_at": "Failed At",
        },
    },
    "payment.refunded": {
        "label": "Payment Refunded",
        "category": "Payments",
        "fields": {
            "id": "Refund ID",
            "amount": "Refunded Amount",
            "currency": "Currency",
            "processor": "Processor",
            "order_id": "Order ID",
            "order_number": "Order Number",
            "customer_email": "Customer Email",
            "refunded_at": "Refunded At",
        },
    },
    # --- Quote Requests ---
    "quote_request.submitted": {
        "label": "Quote Request Submitted",
        "category": "Quote Requests",
        "fields": {
            "id": "Request ID",
            "email": "Email",
            "company": "Company",
            "product_name": "Product Name",
            "message": "Message",
            "phone": "Phone",
            "submitted_at": "Submitted At",
        },
    },
}

_DEFAULT_FIELDS: Dict[str, List[str]] = {
    event: list(info["fields"].keys())
    for event, info in EVENT_CATALOG.items()
}

# Retry delays in seconds: attempt 1→5s, attempt 2→30s, attempt 3→120s
_RETRY_DELAYS = [5, 30, 120]
_MAX_ATTEMPTS = 3
_TIMEOUT = 15.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sign_payload(secret: str, body: bytes) -> str:
    """Return HMAC-SHA256 hex digest for signing webhook payloads."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _filter_payload(event: str, data: Dict[str, Any], fields: Optional[List[str]]) -> Dict[str, Any]:
    """Return only the selected fields from the event data."""
    allowed = fields if fields else _DEFAULT_FIELDS.get(event, list(data.keys()))
    return {k: data[k] for k in allowed if k in data}


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------

async def _deliver_once(
    url: str,
    headers: Dict[str, str],
    payload_bytes: bytes,
) -> tuple[int, str]:
    """Single HTTP POST attempt. Returns (status_code, response_body)."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(url, content=payload_bytes, headers=headers)
        return resp.status_code, resp.text[:500]


async def _dispatch_with_retries(
    delivery_id: str,
    webhook_id: str,
    tenant_id: str,
    url: str,
    secret: str,
    event: str,
    payload: Dict[str, Any],
):
    """Fire webhook with exponential backoff retries. Updates delivery log."""
    payload_bytes = json.dumps(payload, ensure_ascii=False, default=str).encode()
    sig = _sign_payload(secret, payload_bytes)
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Event": event,
        "X-Webhook-Signature": f"sha256={sig}",
        "X-Webhook-Delivery": delivery_id,
        "User-Agent": "AutomateAccounts-Webhook/1.0",
    }

    last_status, last_body, last_error = 0, "", ""
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            status, body = await _deliver_once(url, headers, payload_bytes)
            last_status, last_body = status, body
            last_error = ""
            success = 200 <= status < 300
        except Exception as exc:
            last_error = str(exc)[:300]
            last_status, last_body = 0, ""
            success = False

        await db.webhook_deliveries.update_one(
            {"id": delivery_id},
            {
                "$set": {
                    "attempts": attempt,
                    "last_attempt_at": now_iso(),
                    "status": "success" if success else ("pending" if attempt < _MAX_ATTEMPTS else "failed"),
                    "response_status": last_status,
                    "response_body": last_body,
                    "error": last_error,
                    **({"delivered_at": now_iso()} if success else {}),
                }
            },
        )
        if success:
            logger.info("Webhook %s delivered (attempt %d/%d)", event, attempt, _MAX_ATTEMPTS)
            return

        if attempt < _MAX_ATTEMPTS:
            delay = _RETRY_DELAYS[attempt - 1]
            logger.warning("Webhook %s failed (attempt %d/%d), retrying in %ds", event, attempt, _MAX_ATTEMPTS, delay)
            await asyncio.sleep(delay)

    logger.error("Webhook %s permanently failed after %d attempts", event, _MAX_ATTEMPTS)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def dispatch_event(
    event: str,
    data: Dict[str, Any],
    tenant_id: str,
) -> None:
    """
    Look up all active webhooks for this tenant subscribed to `event`,
    filter data to configured fields, and schedule async delivery.
    Safe to call from any route — failures never propagate.
    """
    try:
        webhooks = await db.webhooks.find(
            {"tenant_id": tenant_id, "is_active": True}, {"_id": 0}
        ).to_list(50)

        for webhook in webhooks:
            subs = {s["event"]: s.get("fields") for s in webhook.get("subscriptions", [])}
            if event not in subs:
                continue

            fields = subs[event]
            filtered = _filter_payload(event, data, fields)
            payload = {
                "event": event,
                "webhook_id": webhook["id"],
                "tenant_id": tenant_id,
                "timestamp": now_iso(),
                "data": filtered,
            }

            delivery_id = make_id()
            await db.webhook_deliveries.insert_one({
                "id": delivery_id,
                "webhook_id": webhook["id"],
                "tenant_id": tenant_id,
                "event": event,
                "payload": payload,
                "attempts": 0,
                "status": "pending",
                "response_status": None,
                "response_body": None,
                "error": None,
                "created_at": now_iso(),
                "last_attempt_at": None,
                "delivered_at": None,
            })

            asyncio.create_task(
                _dispatch_with_retries(
                    delivery_id=delivery_id,
                    webhook_id=webhook["id"],
                    tenant_id=tenant_id,
                    url=webhook["url"],
                    secret=webhook.get("secret", ""),
                    event=event,
                    payload=payload,
                )
            )
    except Exception as exc:
        logger.exception("Error dispatching webhook event %s: %s", event, exc)
