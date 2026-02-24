"""GoCardless redirect completion route."""
from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException

from core.helpers import make_id, now_iso
from core.security import get_current_user
from core.config import GOCARDLESS_ACCESS_TOKEN, GOCARDLESS_ENVIRONMENT
from db.session import db
from models import CompleteGoCardlessRedirect
from services.audit_service import create_audit_log
from services.settings_service import SettingsService

try:
    from gocardless_helper import (
        complete_redirect_flow,
        create_payment,
        get_payment_status,
        create_gocardless_customer,
        create_redirect_flow,
    )
except ImportError:
    complete_redirect_flow = create_payment = get_payment_status = None  # type: ignore
    create_gocardless_customer = create_redirect_flow = None  # type: ignore

from datetime import datetime, timezone

router = APIRouter(prefix="/api", tags=["gocardless"])


async def get_gocardless_creds_for_tenant(tenant_id: str) -> Tuple[str, str]:
    """Get GoCardless credentials from oauth_connections for tenant."""
    conn = await db.oauth_connections.find_one(
        {"tenant_id": tenant_id, "provider": {"$in": ["gocardless", "gocardless_sandbox"]}, "is_validated": True},
        {"_id": 0, "credentials": 1, "provider": 1}
    )
    if not conn:
        return GOCARDLESS_ACCESS_TOKEN, GOCARDLESS_ENVIRONMENT
    creds = conn.get("credentials", {})
    token = creds.get("access_token") or GOCARDLESS_ACCESS_TOKEN
    env = "sandbox" if conn.get("provider") == "gocardless_sandbox" else "live"
    return token, env


@router.post("/gocardless/complete-redirect")
async def complete_gocardless_redirect(
    payload: CompleteGoCardlessRedirect,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Complete GoCardless redirect flow and update order/subscription status."""
    try:
        # Idempotency check — if the flow has already been processed for this order/subscription,
        # return success immediately to handle page refreshes gracefully
        if payload.order_id:
            existing_order = await db.orders.find_one(
                {"id": payload.order_id},
                {"_id": 0, "gocardless_payment_id": 1, "gocardless_mandate_id": 1}
            )
            if existing_order and existing_order.get("gocardless_payment_id"):
                return {
                    "message": "Direct Debit setup already completed.",
                    "mandate_id": existing_order.get("gocardless_mandate_id"),
                    "payment_id": existing_order.get("gocardless_payment_id"),
                    "payment_created": True,
                }

        if payload.subscription_id:
            existing_sub = await db.subscriptions.find_one(
                {"id": payload.subscription_id},
                {"_id": 0, "gocardless_payment_id": 1, "gocardless_mandate_id": 1}
            )
            if existing_sub and existing_sub.get("gocardless_payment_id"):
                return {
                    "message": "Direct Debit setup already completed.",
                    "mandate_id": existing_sub.get("gocardless_mandate_id"),
                    "payment_id": existing_sub.get("gocardless_payment_id"),
                    "payment_created": True,
                }

        # Get tenant_id from customer/user
        customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0, "tenant_id": 1})
        tenant_id = customer.get("tenant_id", "") if customer else ""
        gc_token, gc_env = await get_gocardless_creds_for_tenant(tenant_id)

        redirect_flow = complete_redirect_flow(
            payload.redirect_flow_id, session_token=payload.session_token or "",
            gc_token=gc_token, gc_env=gc_env,
        )
        if not redirect_flow:
            await create_audit_log(
                entity_type="system",
                entity_id=payload.order_id or payload.subscription_id or "unknown",
                action="gocardless_redirect_failed",
                actor="system",
                details={"error": "Failed to complete redirect flow", "redirect_flow_id": payload.redirect_flow_id},
            )
            raise HTTPException(
                status_code=400,
                detail="Failed to complete the Direct Debit setup. The payment link may have expired or been used already. Please return to checkout and try again.",
            )

        mandate_id = redirect_flow.get("links", {}).get("mandate")
        if not mandate_id:
            await create_audit_log(
                entity_type="system",
                entity_id=payload.order_id or payload.subscription_id or "unknown",
                action="gocardless_mandate_missing",
                actor="system",
                details={"error": "No mandate ID in redirect flow response", "redirect_flow_id": payload.redirect_flow_id},
            )
            raise HTTPException(status_code=400, detail="No mandate ID found in GoCardless response")

        # Derive the correct payment currency from the mandate scheme, not the order currency.
        # GoCardless mandates are scheme-specific: PAD=CAD, BACS=GBP, SEPA=EUR, ACH=USD, etc.
        scheme = redirect_flow.get("scheme", "bacs")
        scheme_currency_map = {
            "bacs": "GBP",
            "sepa_core": "EUR",
            "sepa_cor1": "EUR",
            "pad": "CAD",
            "ach": "USD",
            "becs": "AUD",
            "becs_nz": "NZD",
            "betalingsservice": "DKK",
            "autogiro": "SEK",
            "pay_to": "AUD",
        }

        payment_id = None

        if payload.order_id:
            order = await db.orders.find_one({"id": payload.order_id}, {"_id": 0})
            if order and mandate_id:
                payment_currency = scheme_currency_map.get(scheme, order.get("currency", "GBP"))
                payment = create_payment(
                    amount=order["total"],
                    currency=payment_currency,
                    mandate_id=mandate_id,
                    description=f"Payment for Order {order['order_number']}",
                    metadata={"order_id": order["id"], "order_number": order["order_number"]},
                    gc_token=gc_token, gc_env=gc_env,
                )
                if payment:
                    payment_id = payment["id"]
                    await db.orders.update_one(
                        {"id": payload.order_id},
                        {"$set": {"status": "pending_payment", "processor_id": mandate_id, "gocardless_mandate_id": mandate_id, "gocardless_payment_id": payment_id, "updated_at": now_iso()}},
                    )
                    await create_audit_log(
                        entity_type="order",
                        entity_id=payload.order_id,
                        action="payment_initiated",
                        actor="customer",
                        details={"mandate_id": mandate_id, "payment_id": payment_id, "amount": order["total"]},
                    )
                    import time
                    time.sleep(2)
                    payment_status = get_payment_status(payment_id, gc_token=gc_token, gc_env=gc_env)
                    if payment_status:
                        status = payment_status.get("status")
                        await create_audit_log(
                            entity_type="order",
                            entity_id=payload.order_id,
                            action="payment_status_checked",
                            actor="system",
                            details={"payment_status": status, "payment_id": payment_id},
                        )
                        if status in ["confirmed", "paid_out", "submitted"]:
                            await db.orders.update_one(
                                {"id": payload.order_id},
                                {"$set": {"status": "paid", "payment_date": now_iso(), "updated_at": now_iso()}},
                            )
                            await create_audit_log(
                                entity_type="order",
                                entity_id=payload.order_id,
                                action="payment_confirmed",
                                actor="gocardless",
                                details={"payment_status": status, "payment_id": payment_id},
                            )
                else:
                    await create_audit_log(
                        entity_type="order",
                        entity_id=payload.order_id,
                        action="payment_creation_failed",
                        actor="system",
                        details={"mandate_id": mandate_id, "error": "Payment creation returned None"},
                    )
                    raise HTTPException(status_code=500, detail="Failed to create payment with GoCardless. Please contact support with your order number.")

        if payload.subscription_id:
            subscription = await db.subscriptions.find_one({"id": payload.subscription_id}, {"_id": 0})
            if subscription and mandate_id:
                charge_date = None
                sub_start = subscription.get("start_date")
                if sub_start:
                    try:
                        sd = datetime.fromisoformat(sub_start.replace("Z", "+00:00"))
                        if sd > datetime.now(timezone.utc):
                            charge_date = sd.strftime("%Y-%m-%d")
                    except Exception:
                        pass
                payment = create_payment(
                    amount=subscription["amount"],
                    currency=scheme_currency_map.get(scheme, subscription.get("currency", "GBP")),
                    mandate_id=mandate_id,
                    description=f"Subscription Payment - {subscription['plan_name']}",
                    metadata={"subscription_id": subscription["id"]},
                    charge_date=charge_date,
                    gc_token=gc_token, gc_env=gc_env,
                )
                if payment:
                    payment_id = payment["id"]
                    await db.subscriptions.update_one(
                        {"id": payload.subscription_id},
                        {"$set": {"status": "pending_payment", "processor_id": mandate_id, "gocardless_mandate_id": mandate_id, "gocardless_payment_id": payment_id, "updated_at": now_iso()}},
                    )
                    await create_audit_log(
                        entity_type="subscription",
                        entity_id=payload.subscription_id,
                        action="payment_initiated",
                        actor="customer",
                        details={"mandate_id": mandate_id, "payment_id": payment_id},
                    )
                    import time
                    time.sleep(2)
                    payment_status = get_payment_status(payment_id, gc_token=gc_token, gc_env=gc_env)
                    if payment_status and payment_status.get("status") in ["confirmed", "paid_out", "submitted"]:
                        await db.subscriptions.update_one(
                            {"id": payload.subscription_id},
                            {"$set": {"status": "active", "updated_at": now_iso()}},
                        )
                        await create_audit_log(
                            entity_type="subscription",
                            entity_id=payload.subscription_id,
                            action="payment_confirmed",
                            actor="gocardless",
                            details={"payment_status": payment_status.get("status")},
                        )

        return {
            "message": "Direct Debit setup completed. Payment initiated.",
            "mandate_id": mandate_id,
            "payment_id": payment_id,
            "payment_created": payment_id is not None,
        }
    except HTTPException:
        raise
    except Exception as e:
        await create_audit_log(
            entity_type="system",
            entity_id=payload.order_id or payload.subscription_id or "unknown",
            action="gocardless_callback_error",
            actor="system",
            details={"error": str(e), "redirect_flow_id": payload.redirect_flow_id},
        )
        raise HTTPException(status_code=500, detail=f"An error occurred processing your payment setup: {str(e)}")
