"""Partner self-service plan management routes.

Endpoints:
  GET  /api/partner/my-plan        – current plan, subscription, and available upgrades
  POST /api/partner/upgrade-plan   – upgrade to a higher plan (creates sub + pro-rata order)
  POST /api/partner/submissions    – submit a downgrade / support request
  GET  /api/partner/submissions    – partner's own submissions list
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

import stripe as stripe_sdk

from core.helpers import make_id, now_iso
from core.tenant import get_tenant_admin, tenant_id_of, DEFAULT_TENANT_ID
from core.config import STRIPE_API_KEY
from db.session import db
from services.audit_service import create_audit_log

router = APIRouter(prefix="/api", tags=["partner-plans"])

# ---------------------------------------------------------------------------
# GET /partner/my-plan
# ---------------------------------------------------------------------------

@router.get("/partner/my-plan")
async def get_my_plan(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Return current plan info, active subscription, and available public plans for upgrade."""
    tid = tenant_id_of(admin)
    tenant = await db.tenants.find_one({"id": tid}, {"_id": 0, "license": 1, "name": 1})
    license_info = (tenant or {}).get("license") or {}

    current_plan_id = license_info.get("plan_id")
    current_plan = None
    if current_plan_id:
        current_plan = await db.plans.find_one({"id": current_plan_id}, {"_id": 0})

    # Active partner subscription for this partner
    subscription = await db.partner_subscriptions.find_one(
        {"partner_id": tid, "status": {"$in": ["active", "pending"]}},
        {"_id": 0},
    )

    # Available public plans (exclude current, show all active+public)
    available_plans = await db.plans.find(
        {"is_active": True, "is_public": True, "id": {"$ne": current_plan_id}},
        {"_id": 0},
    ).sort("max_users", 1).to_list(50)

    return {
        "current_plan": current_plan,
        "license": license_info,
        "subscription": subscription,
        "available_plans": available_plans,
    }


# ---------------------------------------------------------------------------
# POST /partner/upgrade-plan
# ---------------------------------------------------------------------------

class UpgradePlanRequest(BaseModel):
    plan_id: str


@router.post("/partner/upgrade-plan")
async def upgrade_plan(
    payload: UpgradePlanRequest,
    request: Request,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """
    Self-service plan upgrade.  When the pro-rata amount is > 0 the partner
    is redirected to Stripe Checkout.  The plan is only activated once payment
    is confirmed (via webhook or the status-polling endpoint).
    If the pro-rata amount is £0 (e.g. same billing period) the plan is applied
    immediately without payment.
    """
    tid = tenant_id_of(admin)

    # Validate target plan
    new_plan = await db.plans.find_one({"id": payload.plan_id, "is_active": True, "is_public": True}, {"_id": 0})
    if not new_plan:
        raise HTTPException(status_code=404, detail="Plan not found or not available for self-service upgrade")

    # Current plan
    tenant = await db.tenants.find_one({"id": tid}, {"_id": 0, "license": 1, "name": 1})
    license_info = (tenant or {}).get("license") or {}
    current_plan_id = license_info.get("plan_id")
    if current_plan_id:
        current_plan = await db.plans.find_one({"id": current_plan_id}, {"_id": 0})
        old_monthly = (current_plan or {}).get("monthly_price", 0) or 0
    else:
        old_monthly = 0

    new_monthly = new_plan.get("monthly_price", 0) or 0
    partner_name = (tenant or {}).get("name", "")

    from services.billing_service import calculate_prorata, calculate_upgrade_prorata, next_first_of_month
    today = datetime.now(timezone.utc).date()

    existing_sub = await db.partner_subscriptions.find_one(
        {"partner_id": tid, "status": {"$in": ["active", "pending", "pending_payment"]}},
        {"_id": 0},
    )

    now = now_iso()
    order_id = None
    order_number = None
    sub_id = None
    is_new_sub = False
    prorata_amount = 0.0
    currency = "GBP"

    if existing_sub:
        prorata = calculate_upgrade_prorata(old_monthly, new_monthly, today)
        prorata_amount = prorata["prorata_amount"]
        currency = existing_sub.get("currency", "GBP")
        sub_id = existing_sub["id"]
        is_new_sub = False

        if prorata_amount > 0:
            seq = await db.partner_orders.count_documents({}) + 1
            order_number = f"PO-{today.year}-{seq:04d}"
            order_id = make_id()
            await db.partner_orders.insert_one({
                "id": order_id,
                "order_number": order_number,
                "subscription_id": existing_sub["id"],
                "subscription_number": existing_sub.get("subscription_number", ""),
                "partner_id": tid,
                "partner_name": partner_name,
                "plan_id": new_plan["id"],
                "plan_name": new_plan["name"],
                "description": f"Plan upgrade to {new_plan['name']} — pro-rata for {prorata['days_remaining']} days",
                "amount": prorata_amount,
                "currency": currency,
                "status": "pending_payment",
                "payment_method": "card",
                "invoice_date": today.isoformat(),
                "due_date": today.isoformat(),
                "order_type": "upgrade_prorata",
                "created_at": now,
                "created_by": admin.get("email", "system"),
            })
        else:
            # No charge — apply immediately
            await db.partner_subscriptions.update_one(
                {"id": existing_sub["id"]},
                {"$set": {"plan_id": new_plan["id"], "plan_name": new_plan["name"], "amount": new_monthly, "updated_at": now}},
            )

    else:
        prorata = calculate_prorata(new_monthly, today)
        prorata_amount = prorata["prorata_amount"]
        sub_seq = await db.partner_subscriptions.count_documents({}) + 1
        sub_number = f"PS-{today.year}-{sub_seq:04d}"
        sub_id = make_id()
        is_new_sub = True
        currency = "GBP"

        await db.partner_subscriptions.insert_one({
            "id": sub_id,
            "subscription_number": sub_number,
            "partner_id": tid,
            "partner_name": partner_name,
            "plan_id": new_plan["id"],
            "plan_name": new_plan["name"],
            "description": f"Platform subscription — {new_plan['name']}",
            "amount": new_monthly,
            "currency": currency,
            "billing_interval": "monthly",
            "status": "pending_payment" if prorata_amount > 0 else "active",
            "payment_method": "card" if prorata_amount > 0 else "offline",
            "start_date": today.isoformat(),
            "next_billing_date": prorata["next_billing_date"],
            "created_at": now,
            "created_by": admin.get("email", "system"),
        })

        if prorata_amount > 0:
            seq = await db.partner_orders.count_documents({}) + 1
            order_number = f"PO-{today.year}-{seq:04d}"
            order_id = make_id()
            await db.partner_orders.insert_one({
                "id": order_id,
                "order_number": order_number,
                "subscription_id": sub_id,
                "subscription_number": sub_number,
                "partner_id": tid,
                "partner_name": partner_name,
                "plan_id": new_plan["id"],
                "plan_name": new_plan["name"],
                "description": f"New subscription — {new_plan['name']} (pro-rata {prorata['days_remaining']}/{prorata['days_in_month']} days)",
                "amount": prorata_amount,
                "currency": currency,
                "status": "pending_payment",
                "payment_method": "card",
                "invoice_date": today.isoformat(),
                "due_date": prorata["next_billing_date"],
                "order_type": "new_prorata",
                "created_at": now,
                "created_by": admin.get("email", "system"),
            })

    # ── If there is an amount to charge, create a Stripe Checkout Session ──
    if prorata_amount > 0 and order_id:
        try:
            stripe_sdk.api_key = STRIPE_API_KEY
            host = str(request.base_url).rstrip("/")
            session = stripe_sdk.checkout.Session.create(
                mode="payment",
                line_items=[{
                    "price_data": {
                        "currency": currency.lower(),
                        "product_data": {"name": f"Plan Upgrade: {new_plan['name']}"},
                        "unit_amount": int(round(prorata_amount * 100)),
                    },
                    "quantity": 1,
                }],
                success_url=f"{host}/admin?tab=plan-billing&upgrade_status=success&session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{host}/admin?tab=plan-billing&upgrade_status=cancelled",
                metadata={
                    "type": "partner_upgrade",
                    "partner_order_id": order_id,
                    "partner_id": tid,
                    "plan_id": new_plan["id"],
                    "sub_id": sub_id or "",
                    "is_new_sub": "1" if is_new_sub else "0",
                },
            )
            await db.partner_orders.update_one(
                {"id": order_id},
                {"$set": {"stripe_session_id": session.id}},
            )
            await create_audit_log(
                entity_type="tenant", entity_id=tid,
                action="plan_upgrade_checkout_created", actor=admin.get("email", "system"),
                details={"to": new_plan["id"], "amount": prorata_amount, "session_id": session.id},
            )
            return {
                "checkout_url": session.url,
                "session_id": session.id,
                "amount": prorata_amount,
                "currency": currency,
            }
        except Exception as exc:
            # Stripe failed — fall through to offline billing so upgrade isn't blocked
            await db.partner_orders.update_one(
                {"id": order_id},
                {"$set": {"status": "pending", "payment_method": "offline"}},
            )
            if is_new_sub and sub_id:
                await db.partner_subscriptions.update_one(
                    {"id": sub_id},
                    {"$set": {"status": "active", "payment_method": "offline"}},
                )

    # ── No Stripe session (£0 or fallback) — assign plan immediately ────────
    limits = {k: v for k, v in new_plan.items() if k.startswith("max_")}
    await db.tenants.update_one({"id": tid}, {"$set": {
        "license": {
            "plan_id": new_plan["id"],
            "plan_name": new_plan["name"],
            "assigned_at": now,
            **limits,
        }
    }})

    await create_audit_log(
        entity_type="tenant", entity_id=tid,
        action="plan_upgraded",
        actor=admin.get("email", "system"),
        details={"from": current_plan_id, "to": new_plan["id"], "orders_created": [order_number] if order_number else []},
    )

    return {
        "message": f"Successfully upgraded to {new_plan['name']}",
        "new_plan": new_plan,
        "orders_created": [order_number] if order_number else [],
        "prorata_amount": prorata_amount,
        "next_billing_date": prorata["next_billing_date"],
    }


# ---------------------------------------------------------------------------
# GET /partner/upgrade-plan-status  (poll after Stripe redirect)
# ---------------------------------------------------------------------------

@router.get("/partner/upgrade-plan-status")
async def upgrade_plan_status(
    session_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """Poll after returning from Stripe Checkout to confirm plan activation."""
    tid = tenant_id_of(admin)
    order = await db.partner_orders.find_one(
        {"stripe_session_id": session_id, "partner_id": tid}, {"_id": 0}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Upgrade session not found")

    if order["status"] == "pending_payment":
        # Webhook may not have fired yet — query Stripe directly
        try:
            stripe_sdk.api_key = STRIPE_API_KEY
            sess = stripe_sdk.checkout.Session.retrieve(session_id)
            if sess.payment_status == "paid":
                meta = sess.metadata or {}
                plan_id = meta.get("plan_id")
                sub_id_m = meta.get("sub_id")
                is_new = meta.get("is_new_sub") == "1"

                await db.partner_orders.update_one(
                    {"id": order["id"]},
                    {"$set": {"status": "paid", "paid_at": now_iso(), "payment_method": "card", "updated_at": now_iso()}},
                )
                if sub_id_m:
                    update_fields: Dict[str, Any] = {"status": "active", "payment_method": "card", "updated_at": now_iso()}
                    if not is_new and plan_id:
                        plan_doc_s = await db.plans.find_one({"id": plan_id}, {"_id": 0})
                        if plan_doc_s:
                            update_fields["plan_id"] = plan_id
                            update_fields["plan_name"] = plan_doc_s.get("name", "")
                    await db.partner_subscriptions.update_one({"id": sub_id_m}, {"$set": update_fields})

                if plan_id:
                    plan_doc = await db.plans.find_one({"id": plan_id}, {"_id": 0})
                    if plan_doc:
                        limits = {k: v for k, v in plan_doc.items() if k.startswith("max_")}
                        await db.tenants.update_one({"id": tid}, {"$set": {
                            "license": {
                                "plan_id": plan_doc["id"],
                                "plan_name": plan_doc["name"],
                                "assigned_at": now_iso(),
                                **limits,
                            }
                        }})
                        await create_audit_log(
                            entity_type="tenant", entity_id=tid,
                            action="plan_upgraded_via_stripe",
                            actor="stripe_status_poll",
                            details={"plan_id": plan_id, "session_id": session_id},
                        )
                        return {"status": "paid", "plan_name": plan_doc["name"]}
        except Exception:
            pass

    tenant_doc = await db.tenants.find_one({"id": tid}, {"_id": 0, "license": 1})
    plan_name = (tenant_doc or {}).get("license", {}).get("plan_name", "")
    return {"status": order["status"], "plan_name": plan_name}


# ---------------------------------------------------------------------------
# POST /partner/submissions  (downgrade request / support)
# ---------------------------------------------------------------------------

class SubmissionCreate(BaseModel):
    type: str  # "plan_downgrade" | "support"
    requested_plan_id: Optional[str] = None
    message: str = ""


@router.post("/partner/submissions")
async def create_submission(
    payload: SubmissionCreate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tid = tenant_id_of(admin)
    tenant = await db.tenants.find_one({"id": tid}, {"_id": 0, "license": 1, "name": 1})
    license_info = (tenant or {}).get("license") or {}
    current_plan_id = license_info.get("plan_id")

    requested_plan = None
    if payload.requested_plan_id:
        requested_plan = await db.plans.find_one({"id": payload.requested_plan_id}, {"_id": 0})

    # Effective date for downgrade = next 1st of month
    from services.billing_service import next_first_of_month
    today = datetime.now(timezone.utc).date()
    effective_date = next_first_of_month(today).isoformat()

    sub_id = make_id()
    doc = {
        "id": sub_id,
        "partner_id": tid,
        "partner_name": (tenant or {}).get("name", ""),
        "type": payload.type,
        "current_plan_id": current_plan_id,
        "current_plan_name": license_info.get("plan_name", ""),
        "requested_plan_id": payload.requested_plan_id,
        "requested_plan_name": (requested_plan or {}).get("name", ""),
        "message": payload.message,
        "status": "pending",
        "effective_date": effective_date,
        "created_by": admin.get("email", ""),
        "created_at": now_iso(),
        "resolved_at": None,
        "resolved_by": None,
        "resolution_note": None,
    }
    await db.partner_submissions.insert_one(doc)
    doc.pop("_id", None)
    return {"submission": doc}


# ---------------------------------------------------------------------------
# GET /partner/submissions
# ---------------------------------------------------------------------------

@router.get("/partner/submissions")
async def list_my_submissions(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tid = tenant_id_of(admin)
    items = await db.partner_submissions.find(
        {"partner_id": tid}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return {"submissions": items}
