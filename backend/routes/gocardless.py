"""GoCardless redirect completion route."""
from __future__ import annotations

import os
from typing import Any, Dict

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


@router.post("/gocardless/complete-redirect")
async def complete_gocardless_redirect(
    payload: CompleteGoCardlessRedirect,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Complete GoCardless redirect flow and update order/subscription status."""
    try:
        redirect_flow = complete_redirect_flow(
            payload.redirect_flow_id, session_token=payload.session_token or ""
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

        payment_id = None

        if payload.order_id:
            order = await db.orders.find_one({"id": payload.order_id}, {"_id": 0})
            if order and mandate_id:
                payment = create_payment(
                    amount=order["total"],
                    currency=order.get("currency", "USD"),
                    mandate_id=mandate_id,
                    description=f"Payment for Order {order['order_number']}",
                    metadata={"order_id": order["id"], "order_number": order["order_number"]},
                )
                if payment:
                    payment_id = payment["id"]
                    await db.orders.update_one(
                        {"id": payload.order_id},
                        {"$set": {"status": "pending_payment", "gocardless_mandate_id": mandate_id, "gocardless_payment_id": payment_id, "updated_at": now_iso()}},
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
                    payment_status = get_payment_status(payment_id)
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
                    currency="USD",
                    mandate_id=mandate_id,
                    description=f"Subscription Payment - {subscription['plan_name']}",
                    metadata={"subscription_id": subscription["id"]},
                    charge_date=charge_date,
                )
                if payment:
                    payment_id = payment["id"]
                    await db.subscriptions.update_one(
                        {"id": payload.subscription_id},
                        {"$set": {"status": "pending_payment", "gocardless_mandate_id": mandate_id, "gocardless_payment_id": payment_id, "updated_at": now_iso()}},
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
                    payment_status = get_payment_status(payment_id)
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
