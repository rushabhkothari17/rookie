"""Checkout-related shared services."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from core.constants import PARTNER_TAG_RESPONSES
from core.helpers import make_id, now_iso
from db.session import db
from services.audit_service import create_audit_log
from services.pricing_service import calculate_price
from services.settings_service import SettingsService
from core.constants import SERVICE_FEE_RATE


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

    blob: dict = {
        "product_intake": product_intake,
        "checkout_intake": {
            "zoho_subscription_type": getattr(payload, "zoho_subscription_type", None),
            "current_zoho_product": getattr(payload, "current_zoho_product", None),
            "zoho_account_access": getattr(payload, "zoho_account_access", None),
            "partner_tag_response": getattr(payload, "partner_tag_response", None),
            "promo_code": getattr(payload, "promo_code", None),
            "sponsorship_note": "This order was placed using a sponsored promo code." if (getattr(payload, "promo_code", None) or "") and "ZOHOR" in (getattr(payload, "promo_code", None) or "").upper() else None,
            "terms_accepted": getattr(payload, "terms_accepted", False),
            "override_code_used": bool(getattr(payload, "override_code", None)),
        },
        "payment": {"method": payment_method},
        "system_metadata": {"user_id": user_id, "customer_id": customer_id, "timestamp": now_iso()},
    }
    if scope_unlocks:
        blob["scope_unlocks"] = scope_unlocks
    return blob


async def validate_and_consume_partner_tag(
    customer_id: str,
    partner_tag_response: Optional[str],
    override_code: Optional[str],
    order_id: Optional[str] = None,
) -> Optional[str]:
    """Validate partner tag response and override code. Returns override_code_id if consumed."""
    VALID_RESPONSES = PARTNER_TAG_RESPONSES
    if not partner_tag_response or partner_tag_response not in VALID_RESPONSES:
        raise HTTPException(
            status_code=400,
            detail="Please select whether you have tagged us as your Zoho Partner before proceeding."
        )

    override_code_id = None

    if partner_tag_response == "Not yet":
        if not override_code or not override_code.strip():
            await create_audit_log(
                entity_type="checkout", entity_id=customer_id,
                action="checkout_blocked_no_override_code", actor="system",
                details={"reason": "No override code provided", "partner_tag": partner_tag_response}
            )
            raise HTTPException(
                status_code=400,
                detail="An override code is required to proceed without tagging us as your Zoho Partner."
            )

        oc = await db.override_codes.find_one({"code": override_code.strip()}, {"_id": 0})
        if not oc:
            await create_audit_log(
                entity_type="checkout", entity_id=customer_id,
                action="checkout_blocked_invalid_override_code", actor="system",
                details={"reason": "Override code not found", "code": override_code}
            )
            raise HTTPException(status_code=400, detail="Invalid override code.")

        if oc.get("customer_id") != customer_id:
            await create_audit_log(
                entity_type="checkout", entity_id=customer_id,
                action="checkout_blocked_override_code_mismatch", actor="system",
                details={"reason": "Code not assigned to customer", "code": override_code}
            )
            raise HTTPException(status_code=400, detail="This override code is not valid for your account.")

        expires_at = oc.get("expires_at")
        if expires_at:
            try:
                exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) > exp_dt:
                    await create_audit_log(
                        entity_type="override_code", entity_id=oc["id"],
                        action="override_code_expired_at_checkout", actor="system",
                        details={"customer_id": customer_id, "expires_at": expires_at}
                    )
                    raise HTTPException(status_code=400, detail="This override code has expired. Please contact admin for a new one.")
            except HTTPException:
                raise
            except Exception:
                pass

        if oc.get("status") != "active":
            raise HTTPException(status_code=400, detail="This override code is no longer active.")

        override_code_id = oc["id"]

    pending_value = f"{partner_tag_response} - Pending Verification"
    await db.customers.update_one({"id": customer_id}, {"$set": {"partner_map": pending_value}})
    await create_audit_log(
        entity_type="customer", entity_id=customer_id,
        action="partner_map_updated", actor="system",
        details={"partner_map": pending_value, "order_id": order_id, "trigger": "checkout"}
    )

    if override_code_id and override_code:
        note_text = f"Override code used: {override_code.strip()} at {now_iso()}"
        if order_id:
            note_text += f" for Order {order_id}"
        await db.customers.update_one(
            {"id": customer_id},
            {"$push": {"notes": {"text": note_text, "timestamp": now_iso(), "actor": "system"}}}
        )
        await create_audit_log(
            entity_type="customer", entity_id=customer_id,
            action="customer_note_appended", actor="system",
            details={"note": note_text, "override_code_id": override_code_id}
        )
        await db.override_codes.update_one(
            {"id": override_code_id},
            {"$set": {"status": "inactive", "used_at": now_iso(), "used_for_order_id": order_id}}
        )
        await create_audit_log(
            entity_type="override_code", entity_id=override_code_id,
            action="override_code_used", actor="system",
            details={"customer_id": customer_id, "order_id": order_id, "code": override_code.strip()}
        )

    return override_code_id


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
