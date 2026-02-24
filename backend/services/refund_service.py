"""Refund service for processing refunds via Stripe and GoCardless."""
from __future__ import annotations

import os
from typing import Any, Dict, Optional
import httpx

from db.session import db
from core.helpers import make_id, now_iso, round_cents
from services.settings_service import SettingsService

# Stripe API
STRIPE_API_URL = "https://api.stripe.com/v1"


async def get_stripe_secret_key(tenant_id: str) -> Optional[str]:
    """Get Stripe secret key for tenant."""
    setting = await db.settings.find_one(
        {"tenant_id": tenant_id, "key": "stripe_secret_key"},
        {"_id": 0, "value_json": 1}
    )
    return setting.get("value_json") if setting else None


async def get_gocardless_credentials(tenant_id: str) -> Optional[Dict[str, str]]:
    """Get GoCardless credentials for tenant from oauth_connections."""
    conn = await db.oauth_connections.find_one(
        {"tenant_id": tenant_id, "provider": {"$in": ["gocardless", "gocardless_sandbox"]}, "is_validated": True},
        {"_id": 0, "credentials": 1, "provider": 1}
    )
    if not conn:
        return None
    creds = conn.get("credentials", {})
    return {
        "access_token": creds.get("access_token", ""),
        "environment": "sandbox" if conn.get("provider") == "gocardless_sandbox" else "live",
    }


async def process_stripe_refund(
    tenant_id: str,
    payment_intent_id: str,
    amount_cents: Optional[int] = None,
    reason: str = "requested_by_customer"
) -> Dict[str, Any]:
    """
    Process a refund via Stripe.
    
    Args:
        tenant_id: Tenant ID for getting API key
        payment_intent_id: Stripe PaymentIntent ID (pi_xxx) or Charge ID (ch_xxx)
        amount_cents: Amount to refund in cents. None for full refund.
        reason: Refund reason (duplicate, fraudulent, requested_by_customer)
    
    Returns:
        Dict with success status and refund details
    """
    secret_key = await get_stripe_secret_key(tenant_id)
    if not secret_key:
        return {"success": False, "error": "Stripe not configured for this tenant"}
    
    # Build refund payload
    payload = {
        "reason": reason,
    }
    
    # Determine if it's a payment_intent or charge
    if payment_intent_id.startswith("pi_"):
        payload["payment_intent"] = payment_intent_id
    elif payment_intent_id.startswith("ch_"):
        payload["charge"] = payment_intent_id
    else:
        return {"success": False, "error": "Invalid payment ID format. Must start with 'pi_' or 'ch_'"}
    
    if amount_cents:
        payload["amount"] = amount_cents
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{STRIPE_API_URL}/refunds",
                data=payload,
                auth=(secret_key, ""),
                timeout=30.0
            )
            
            if resp.status_code == 200:
                refund_data = resp.json()
                return {
                    "success": True,
                    "refund_id": refund_data.get("id"),
                    "amount": refund_data.get("amount"),
                    "currency": refund_data.get("currency"),
                    "status": refund_data.get("status"),
                    "provider": "stripe"
                }
            else:
                error_data = resp.json()
                return {
                    "success": False,
                    "error": error_data.get("error", {}).get("message", "Stripe refund failed"),
                    "code": error_data.get("error", {}).get("code")
                }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def process_gocardless_refund(
    tenant_id: str,
    payment_id: str,
    amount_cents: Optional[int] = None,
    reference: str = ""
) -> Dict[str, Any]:
    """
    Process a refund via GoCardless.
    
    Args:
        tenant_id: Tenant ID for getting API token
        payment_id: GoCardless Payment ID (PM_xxx)
        amount_cents: Amount to refund in cents. None for full refund.
        reference: Internal reference for the refund
    
    Returns:
        Dict with success status and refund details
    """
    gc_creds = await get_gocardless_credentials(tenant_id)
    if not gc_creds or not gc_creds.get("access_token"):
        return {"success": False, "error": "GoCardless not configured for this tenant"}
    
    token = gc_creds["access_token"]
    env = gc_creds.get("environment", "sandbox")
    api_url = "https://api.gocardless.com" if env == "live" else "https://api-sandbox.gocardless.com"
    
    # Build refund payload
    payload = {
        "refunds": {
            "links": {
                "payment": payment_id
            }
        }
    }
    
    if amount_cents:
        payload["refunds"]["amount"] = amount_cents
    if reference:
        payload["refunds"]["reference"] = reference
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{api_url}/refunds",
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "GoCardless-Version": "2015-07-06",
                    "Content-Type": "application/json"
                },
                timeout=30.0
            )
            
            if resp.status_code in (200, 201):
                refund_data = resp.json().get("refunds", {})
                return {
                    "success": True,
                    "refund_id": refund_data.get("id"),
                    "amount": refund_data.get("amount"),
                    "currency": refund_data.get("currency"),
                    "status": refund_data.get("status"),
                    "provider": "gocardless"
                }
            else:
                error_data = resp.json()
                error_msg = error_data.get("error", {}).get("message", "GoCardless refund failed")
                if "errors" in error_data.get("error", {}):
                    error_msg = error_data["error"]["errors"][0].get("message", error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "code": error_data.get("error", {}).get("type")
                }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def record_refund(
    tenant_id: str,
    order_id: str,
    amount_cents: int,
    reason: str,
    provider: str,
    provider_refund_id: Optional[str] = None,
    processed_by: str = "system"
) -> Dict[str, Any]:
    """
    Record a refund in the database.
    
    Creates a refund record and updates the order's refund totals.
    """
    refund_id = make_id()
    
    refund_doc = {
        "id": refund_id,
        "tenant_id": tenant_id,
        "order_id": order_id,
        "amount": amount_cents,
        "reason": reason,
        "provider": provider,
        "provider_refund_id": provider_refund_id,
        "status": "completed" if provider_refund_id else "recorded",
        "processed_by": processed_by,
        "created_at": now_iso()
    }
    
    await db.refunds.insert_one(refund_doc)
    
    # Update order with refund info
    order = await db.orders.find_one({"id": order_id, "tenant_id": tenant_id}, {"_id": 0})
    if order:
        current_refunded = order.get("refunded_amount", 0)
        new_refunded = current_refunded + amount_cents
        
        # Determine new status
        total = order.get("total", 0)
        new_status = order.get("status")
        if new_refunded >= total:
            new_status = "refunded"
        elif new_refunded > 0:
            new_status = "partially_refunded"
        
        await db.orders.update_one(
            {"id": order_id},
            {"$set": {
                "refunded_amount": new_refunded,
                "status": new_status,
                "last_refund_at": now_iso()
            }}
        )
    
    return {
        "refund_id": refund_id,
        "amount": amount_cents,
        "status": refund_doc["status"]
    }
