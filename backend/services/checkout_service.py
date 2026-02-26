"""Checkout-related shared services."""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import HTTPException
from core.helpers import make_id, now_iso
from db.session import db
from services.pricing_service import calculate_price
from services.settings_service import SettingsService
from core.constants import SERVICE_FEE_RATE

logger = logging.getLogger(__name__)

# ── FX rate cache (1-hour TTL) ─────────────────────────────────────────────
_fx_cache: Dict[str, Tuple[float, float]] = {}  # key -> (rate, timestamp)
_FX_CACHE_TTL = 3600  # seconds


async def get_fx_rate(from_currency: str, to_currency: str) -> float:
    """Fetch real-time FX rate via open.er-api.com (free, no key required).
    Results are cached for 1 hour.  Returns 1.0 on any failure."""
    from_currency = (from_currency or "USD").upper()
    to_currency = (to_currency or "USD").upper()
    if from_currency == to_currency:
        return 1.0

    cache_key = f"{from_currency}:{to_currency}"
    cached = _fx_cache.get(cache_key)
    if cached:
        rate, ts = cached
        if time.time() - ts < _FX_CACHE_TTL:
            return rate

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"https://open.er-api.com/v6/latest/{from_currency}",
                headers={"Accept": "application/json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                rates = data.get("rates", {})
                rate = rates.get(to_currency)
                if rate:
                    _fx_cache[cache_key] = (float(rate), time.time())
                    return float(rate)
    except Exception as exc:
        logger.warning("FX rate fetch failed (%s→%s): %s — using 1:1 fallback", from_currency, to_currency, exc)
    return 1.0


def resolve_terms_tags(content: str, user: Dict[str, Any], address: Dict[str, Any], product_name: str) -> str:
    """Resolve dynamic tags in T&C content."""
    resolved = content
    resolved = resolved.replace("{product_name}", product_name)
    resolved = resolved.replace("{user_name}", user.get("full_name", ""))
    resolved = resolved.replace("{company_name}", user.get("company_name", ""))
    resolved = resolved.replace("{user_company_name}", user.get("company_name", ""))
    resolved = resolved.replace("{user_job_title}", user.get("job_title", ""))
    resolved = resolved.replace("{user_email}", user.get("email", ""))
    resolved = resolved.replace("{user_phone}", user.get("phone", ""))
    if address:
        resolved = resolved.replace("{user_address_line1}", address.get("line1", ""))
        resolved = resolved.replace("{user_city}", address.get("city", ""))
        resolved = resolved.replace("{user_state}", address.get("region", ""))
        resolved = resolved.replace("{user_postal}", address.get("postal", ""))
        resolved = resolved.replace("{user_country}", address.get("country", ""))
    return resolved


def build_checkout_notes_json(
    order_items: list,
    payload: Any,
    user_id: str,
    customer_id: str,
    payment_method: str = "unknown",
    promo_data: Optional[dict] = None,
) -> dict:
    """Build JSON blob capturing all checkout inputs for order/subscription notes."""
    product_intake = {}
    scope_unlocks = {}
    for item in order_items:
        pid = item["product"]["id"]
        raw_inputs = dict(item.get("inputs") or {})
        if "_scope_unlock" in raw_inputs:
            scope_unlocks[pid] = raw_inputs.pop("_scope_unlock")
        product_intake[pid] = raw_inputs

    promo_code_str = getattr(payload, "promo_code", None) or ""
    is_zohor = "ZOHOR" in promo_code_str.upper()
    is_sponsored = bool(promo_data and promo_data.get("promo_note")) or (bool(promo_data and promo_data.get("is_sponsored")) if promo_data else is_zohor)
    promo_note = (
        (promo_data.get("promo_note") if promo_data else None)
        or ("This order was placed using a sponsored promo code." if (is_zohor or is_sponsored) else None)
    )

    blob: dict = {
        "product_intake": product_intake,
        "checkout_intake": {
            "zoho_subscription_type": getattr(payload, "zoho_subscription_type", None),
            "current_zoho_product": getattr(payload, "current_zoho_product", None),
            "zoho_account_access": getattr(payload, "zoho_account_access", None),
            "promo_code": promo_code_str or None,
            "promo_note": promo_note,
            "terms_accepted": getattr(payload, "terms_accepted", False),
        },
        "payment": {"method": payment_method},
        "system_metadata": {"user_id": user_id, "customer_id": customer_id, "timestamp": now_iso()},
    }
    if scope_unlocks:
        blob["scope_unlocks"] = scope_unlocks
    return blob


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


async def build_order_items(items: list, tenant_id: str = "") -> List[Dict[str, Any]]:
    """Build enriched order items with pricing from cart items."""
    fee_rate = await get_stripe_fee_rate(tenant_id) if tenant_id else SERVICE_FEE_RATE
    order_items = []
    for item in items:
        product = await db.products.find_one({"id": item.product_id}, {"_id": 0})
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        pricing = calculate_price(product, item.inputs, fee_rate=fee_rate)
        # If a price_override is set (e.g. from scope ID unlock), use it
        if hasattr(item, "price_override") and item.price_override is not None:
            pricing["subtotal"] = item.price_override
            pricing["total"] = item.price_override
            pricing["fee"] = 0.0
            pricing["is_scope_request"] = False
        order_items.append({
            "id": make_id(),
            "product": product,
            "quantity": item.quantity,
            "pricing": pricing,
            "inputs": item.inputs,
        })
    return order_items
