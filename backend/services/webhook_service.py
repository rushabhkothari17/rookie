"""Webhook dispatch service — HMAC-signed, async delivery with retries."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import socket
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

from core.helpers import make_id, now_iso
from db.session import db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SSRF Protection — blocked IP ranges
# ---------------------------------------------------------------------------

_BLOCKED_NETWORKS = [
    # IPv4 private / reserved
    ipaddress.ip_network("127.0.0.0/8"),       # Loopback
    ipaddress.ip_network("10.0.0.0/8"),         # Private class A
    ipaddress.ip_network("172.16.0.0/12"),      # Private class B
    ipaddress.ip_network("192.168.0.0/16"),     # Private class C
    ipaddress.ip_network("169.254.0.0/16"),     # Link-local (AWS metadata: 169.254.169.254)
    ipaddress.ip_network("0.0.0.0/8"),          # Unspecified
    ipaddress.ip_network("100.64.0.0/10"),      # Shared address space (CGN)
    ipaddress.ip_network("192.0.0.0/24"),       # IETF protocol assignments
    ipaddress.ip_network("192.0.2.0/24"),       # Documentation TEST-NET-1
    ipaddress.ip_network("198.18.0.0/15"),      # Network benchmarking
    ipaddress.ip_network("198.51.100.0/24"),    # Documentation TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),     # Documentation TEST-NET-3
    ipaddress.ip_network("240.0.0.0/4"),        # Reserved
    ipaddress.ip_network("255.255.255.255/32"), # Broadcast
    # IPv6 private / reserved
    ipaddress.ip_network("::1/128"),            # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),           # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),          # IPv6 link-local
    ipaddress.ip_network("::/128"),             # IPv6 unspecified
]


def _validate_webhook_url(url: str) -> None:
    """
    Guard against Server-Side Request Forgery (SSRF) by validating the
    webhook URL before any outbound HTTP request is made.

    Checks:
      1. URL scheme must be http or https.
      2. Hostname must be present and resolvable.
      3. Every resolved IP must be a publicly routable address — all
         private, loopback, link-local, and reserved ranges are blocked.

    Raises ValueError if validation fails.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"Webhook URL must use http:// or https:// scheme, got: '{parsed.scheme}'"
        )

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Webhook URL has no hostname")

    try:
        addr_infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ValueError(f"Cannot resolve webhook hostname '{hostname}': {exc}")

    if not addr_infos:
        raise ValueError(f"Webhook hostname '{hostname}' did not resolve to any address")

    for addr_info in addr_infos:
        ip_str = addr_info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        for network in _BLOCKED_NETWORKS:
            if ip in network:
                raise ValueError(
                    f"Webhook URL resolves to a blocked IP address ({ip}) in reserved "
                    f"range {network}. Internal/private network access is not permitted."
                )


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
    # SSRF check — validate URL once before any retry attempts
    try:
        _validate_webhook_url(url)
    except ValueError as exc:
        err_msg = f"SSRF_BLOCKED: {exc}"
        logger.warning("Security: blocked webhook delivery to '%s': %s", url, exc)
        await db.webhook_deliveries.update_one(
            {"id": delivery_id},
            {
                "$set": {
                    "attempts": 1,
                    "last_attempt_at": now_iso(),
                    "status": "failed",
                    "response_status": 0,
                    "response_body": "",
                    "error": err_msg[:300],
                }
            },
        )
        return

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
