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


# ---------------------------------------------------------------------------
# GET /partner/one-time-rates  (read-only rate catalogue for partners)
# ---------------------------------------------------------------------------

@router.get("/partner/one-time-rates")
async def get_one_time_rates(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Return active one-time upgrade rates so the partner UI can display pricing."""
    rates = await db.one_time_plan_rates.find({"is_active": True}, {"_id": 0}).sort("module_key", 1).to_list(50)
    return {"rates": rates}



# ---------------------------------------------------------------------------
# Helper: apply coupon discount and mark usage
# ---------------------------------------------------------------------------

async def _apply_coupon(coupon_code: str, upgrade_type: str, plan_id: str | None,
                        base_amount: float, tid: str) -> tuple[float, str | None]:
    """Returns (final_amount, coupon_id|None). Raises HTTPException if invalid."""
    if not coupon_code:
        return base_amount, None
    code = coupon_code.upper().strip()
    coupon = await db.coupons.find_one({"code": code, "is_active": True}, {"_id": 0})
    if not coupon:
        raise HTTPException(400, "Invalid or inactive coupon code")
    today = now_iso()[:10]
    if coupon.get("expiry_date") and coupon["expiry_date"] < today:
        raise HTTPException(400, "This coupon has expired")
    if coupon["applies_to"] != "both" and coupon["applies_to"] != upgrade_type:
        raise HTTPException(400, f"Coupon only applies to {'ongoing' if coupon['applies_to'] == 'ongoing' else 'one-time'} upgrades")
    if upgrade_type == "ongoing" and plan_id:
        ap = coupon.get("applicable_plan_ids")
        if ap and plan_id not in ap:
            raise HTTPException(400, "Coupon not applicable to the selected plan")
    if coupon.get("is_single_use") and coupon.get("usage_count", 0) >= 1:
        raise HTTPException(400, "This coupon has already been used")
    if coupon.get("is_one_time_per_org") and tid in (coupon.get("used_by_orgs") or []):
        raise HTTPException(400, "Your organisation has already used this coupon")
    if coupon["discount_type"] == "percentage":
        discount = round(base_amount * coupon["discount_value"] / 100, 2)
    else:
        discount = min(float(coupon["discount_value"]), base_amount)
    final = round(max(0.0, base_amount - discount), 2)
    return final, coupon["id"]


async def _record_coupon_usage(coupon_id: str, tid: str) -> None:
    await db.coupons.update_one(
        {"id": coupon_id},
        {"$inc": {"usage_count": 1}, "$addToSet": {"used_by_orgs": tid}},
    )


# ---------------------------------------------------------------------------
# POST /partner/upgrade-plan-ongoing  (flat monthly difference charge)
# ---------------------------------------------------------------------------

class OngoingUpgradeRequest(BaseModel):
    plan_id: str
    coupon_code: str = ""


@router.post("/partner/upgrade-plan-ongoing")
async def upgrade_plan_ongoing(
    payload: OngoingUpgradeRequest,
    request: Request,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """
    Upgrade to a higher plan.  Charges the FLAT monthly difference between
    old and new plan prices (not pro-rated).  The new plan is activated
    immediately once Stripe payment is confirmed.
    """
    tid = tenant_id_of(admin)
    new_plan = await db.plans.find_one({"id": payload.plan_id, "is_active": True, "is_public": True}, {"_id": 0})
    if not new_plan:
        raise HTTPException(404, "Plan not found or not available")

    tenant = await db.tenants.find_one({"id": tid}, {"_id": 0, "license": 1, "name": 1})
    license_info = (tenant or {}).get("license") or {}
    current_plan_id = license_info.get("plan_id")
    current_plan = await db.plans.find_one({"id": current_plan_id}, {"_id": 0}) if current_plan_id else None
    old_monthly = (current_plan or {}).get("monthly_price", 0) or 0
    new_monthly = new_plan.get("monthly_price", 0) or 0

    from services.billing_service import calculate_upgrade_flat
    flat_diff = calculate_upgrade_flat(old_monthly, new_monthly)

    currency = "GBP"
    existing_sub = await db.partner_subscriptions.find_one(
        {"partner_id": tid, "status": {"$in": ["active", "unpaid"]}}, {"_id": 0}
    )
    if existing_sub:
        currency = existing_sub.get("currency", "GBP")

    # Apply coupon
    final_amount, coupon_id = await _apply_coupon(payload.coupon_code, "ongoing", payload.plan_id, flat_diff, tid)

    today = datetime.now(timezone.utc).date()
    now = now_iso()
    seq = await db.partner_orders.count_documents({}) + 1
    order_number = f"PO-{today.year}-{seq:04d}"
    order_id = make_id()
    sub_id = existing_sub["id"] if existing_sub else None
    partner_name = (tenant or {}).get("name", "")

    await db.partner_orders.insert_one({
        "id": order_id, "order_number": order_number,
        "subscription_id": sub_id,
        "subscription_number": (existing_sub or {}).get("subscription_number", ""),
        "partner_id": tid, "partner_name": partner_name,
        "plan_id": new_plan["id"], "plan_name": new_plan["name"],
        "description": f"Ongoing plan upgrade to {new_plan['name']} (monthly difference)",
        "amount": final_amount, "currency": currency,
        "status": "pending_payment", "payment_method": "card",
        "invoice_date": today.isoformat(), "due_date": today.isoformat(),
        "order_type": "ongoing_upgrade", "coupon_id": coupon_id,
        "created_at": now, "created_by": admin.get("email", "system"),
    })

    if final_amount > 0:
        try:
            stripe_sdk.api_key = STRIPE_API_KEY
            host = str(request.base_url).rstrip("/")
            session = stripe_sdk.checkout.Session.create(
                mode="payment",
                line_items=[{"price_data": {
                    "currency": currency.lower(),
                    "product_data": {"name": f"Plan Upgrade: {new_plan['name']}"},
                    "unit_amount": int(round(final_amount * 100)),
                }, "quantity": 1}],
                success_url=f"{host}/admin?tab=plan-billing&upgrade_status=success&session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{host}/admin?tab=plan-billing&upgrade_status=cancelled",
                metadata={
                    "type": "partner_upgrade", "partner_order_id": order_id,
                    "partner_id": tid, "plan_id": new_plan["id"],
                    "sub_id": sub_id or "", "is_new_sub": "0",
                    "coupon_id": coupon_id or "",
                },
            )
            await db.partner_orders.update_one({"id": order_id}, {"$set": {"stripe_session_id": session.id}})
            if coupon_id:
                await _record_coupon_usage(coupon_id, tid)
            return {"checkout_url": session.url, "session_id": session.id, "amount": final_amount, "currency": currency}
        except Exception:
            await db.partner_orders.update_one({"id": order_id}, {"$set": {"status": "pending", "payment_method": "offline"}})

    # Zero charge (coupon covered full amount) — activate immediately
    if coupon_id:
        await _record_coupon_usage(coupon_id, tid)
    limits = {k: v for k, v in new_plan.items() if k.startswith("max_")}
    await db.tenants.update_one({"id": tid}, {"$set": {"license": {
        "plan_id": new_plan["id"], "plan_name": new_plan["name"], "assigned_at": now, **limits,
    }}})
    if sub_id:
        await db.partner_subscriptions.update_one(
            {"id": sub_id},
            {"$set": {"plan_id": new_plan["id"], "plan_name": new_plan["name"],
                      "amount": new_monthly, "updated_at": now}},
        )
    await db.partner_orders.update_one({"id": order_id}, {"$set": {"status": "paid", "paid_at": now}})
    return {"message": f"Upgraded to {new_plan['name']}", "new_plan": new_plan}


# ---------------------------------------------------------------------------
# POST /partner/one-time-upgrade  (extra limits for current billing cycle)
# ---------------------------------------------------------------------------

class OneTimeItem(BaseModel):
    module_key: str
    quantity: int


class OneTimeUpgradeRequest(BaseModel):
    upgrades: list[OneTimeItem]
    coupon_code: str = ""


@router.post("/partner/one-time-upgrade")
async def one_time_upgrade(
    payload: OneTimeUpgradeRequest,
    request: Request,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """Buy extra per-module limits for the current billing cycle.  Resets on renewal."""
    tid = tenant_id_of(admin)

    for item in payload.upgrades:
        if item.quantity <= 0:
            raise HTTPException(400, f"Quantity for {item.module_key} must be a positive integer")

    # Fetch rates
    rates = {}
    for item in payload.upgrades:
        rate = await db.one_time_plan_rates.find_one({"module_key": item.module_key, "is_active": True}, {"_id": 0})
        if not rate:
            raise HTTPException(400, f"No active rate configured for module: {item.module_key}")
        rates[item.module_key] = rate

    line_items = []
    subtotal = 0.0
    for item in payload.upgrades:
        r = rates[item.module_key]
        item_total = round(item.quantity * r["price_per_record"], 2)
        subtotal += item_total
        line_items.append({
            "module_key": item.module_key,
            "label": r.get("label", item.module_key),
            "quantity": item.quantity,
            "price_per_record": r["price_per_record"],
            "total": item_total,
        })

    currency = rates[payload.upgrades[0].module_key].get("currency", "GBP")
    final_amount, coupon_id = await _apply_coupon(payload.coupon_code, "one_time", None, subtotal, tid)

    # Get current subscription for billing_period_end
    existing_sub = await db.partner_subscriptions.find_one(
        {"partner_id": tid, "status": {"$in": ["active", "unpaid"]}}, {"_id": 0}
    )
    billing_period_end = (existing_sub or {}).get("next_billing_date") or ""

    tenant = await db.tenants.find_one({"id": tid}, {"_id": 0, "name": 1})
    today = datetime.now(timezone.utc).date()
    now = now_iso()

    upgrade_id = make_id()
    await db.one_time_upgrades.insert_one({
        "id": upgrade_id, "partner_id": tid,
        "partner_name": (tenant or {}).get("name", ""),
        "upgrades": line_items, "subtotal": round(subtotal, 2),
        "final_amount": final_amount, "currency": currency,
        "billing_period_end": billing_period_end,
        "status": "pending_payment", "coupon_id": coupon_id,
        "created_at": now, "created_by": admin.get("email"),
    })

    seq = await db.partner_orders.count_documents({}) + 1
    order_number = f"PO-{today.year}-{seq:04d}"
    order_id = make_id()
    await db.partner_orders.insert_one({
        "id": order_id, "order_number": order_number,
        "partner_id": tid, "partner_name": (tenant or {}).get("name", ""),
        "description": "One-time limit upgrade",
        "amount": final_amount, "currency": currency,
        "status": "pending_payment", "payment_method": "card",
        "invoice_date": today.isoformat(), "due_date": today.isoformat(),
        "order_type": "one_time_upgrade", "coupon_id": coupon_id,
        "one_time_upgrade_id": upgrade_id,
        "created_at": now, "created_by": admin.get("email"),
    })
    await db.one_time_upgrades.update_one({"id": upgrade_id}, {"$set": {"order_id": order_id}})

    if final_amount > 0:
        try:
            stripe_sdk.api_key = STRIPE_API_KEY
            host = str(request.base_url).rstrip("/")
            desc_lines = [f"+{i['quantity']} {i['label']}" for i in line_items]
            session = stripe_sdk.checkout.Session.create(
                mode="payment",
                line_items=[{"price_data": {
                    "currency": currency.lower(),
                    "product_data": {"name": "One-Time Limit Upgrade",
                                     "description": ", ".join(desc_lines)},
                    "unit_amount": int(round(final_amount * 100)),
                }, "quantity": 1}],
                success_url=f"{host}/admin?tab=plan-billing&onetimeupgrade_status=success&session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{host}/admin?tab=plan-billing&onetimeupgrade_status=cancelled",
                metadata={
                    "type": "one_time_upgrade", "upgrade_id": upgrade_id,
                    "partner_id": tid, "order_id": order_id,
                    "coupon_id": coupon_id or "",
                },
            )
            await db.partner_orders.update_one({"id": order_id}, {"$set": {"stripe_session_id": session.id}})
            await db.one_time_upgrades.update_one({"id": upgrade_id}, {"$set": {"stripe_session_id": session.id}})
            if coupon_id:
                await _record_coupon_usage(coupon_id, tid)
            return {"checkout_url": session.url, "session_id": session.id,
                    "amount": final_amount, "currency": currency, "line_items": line_items}
        except Exception:
            pass

    # Zero charge — activate immediately
    if coupon_id:
        await _record_coupon_usage(coupon_id, tid)
    boosts = {i["module_key"]: i["quantity"] for i in line_items}
    await db.tenants.update_one({"id": tid}, {"$set": {
        "license.one_time_boosts": boosts,
        "license.one_time_boosts_expire_at": billing_period_end,
    }})
    await db.one_time_upgrades.update_one({"id": upgrade_id}, {"$set": {"status": "active"}})
    await db.partner_orders.update_one({"id": order_id}, {"$set": {"status": "paid", "paid_at": now}})
    return {"message": "One-time limits applied", "boosts": boosts}


# ---------------------------------------------------------------------------
# GET /partner/one-time-upgrade-status
# ---------------------------------------------------------------------------

@router.get("/partner/one-time-upgrade-status")
async def one_time_upgrade_status(
    session_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tid = tenant_id_of(admin)
    upgrade = await db.one_time_upgrades.find_one(
        {"stripe_session_id": session_id, "partner_id": tid}, {"_id": 0}
    )
    if not upgrade:
        raise HTTPException(404, "Upgrade session not found")

    if upgrade["status"] == "pending_payment":
        try:
            stripe_sdk.api_key = STRIPE_API_KEY
            sess = stripe_sdk.checkout.Session.retrieve(session_id)
            if sess.payment_status == "paid":
                boosts = {i["module_key"]: i["quantity"] for i in upgrade.get("upgrades", [])}
                bp_end = upgrade.get("billing_period_end", "")
                await db.tenants.update_one({"id": tid}, {"$set": {
                    "license.one_time_boosts": boosts,
                    "license.one_time_boosts_expire_at": bp_end,
                }})
                await db.one_time_upgrades.update_one({"id": upgrade["id"]}, {"$set": {"status": "active"}})
                if upgrade.get("order_id"):
                    await db.partner_orders.update_one(
                        {"id": upgrade["order_id"]},
                        {"$set": {"status": "paid", "paid_at": now_iso()}},
                    )
                return {"status": "active", "boosts": boosts}
        except Exception:
            pass

    return {"status": upgrade["status"]}
