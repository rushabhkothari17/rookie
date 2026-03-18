"""
Pro-rata and billing-cycle helpers for partner and customer subscriptions.

Rules:
- Platform-level partner billing: always on the 1st of the month.
- First bill is always pro-rated (days remaining in month / days in month × monthly fee).
- Mid-month upgrades: pro-rata on the *difference* between old and new monthly fee.
- Partner admins can choose per-product either:
    billing_mode = "prorated"  → first bill pro-rated, then 1st of each month
    billing_mode = "monthly"   → no proration, billing day = start day each month
"""
from __future__ import annotations

import calendar
from datetime import date, datetime
from typing import Tuple


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def _ensure_date(d: date | datetime | str) -> date:
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, str):
        return datetime.fromisoformat(d[:10]).date()
    return d


def next_first_of_month(from_date: date | datetime | str | None = None) -> date:
    """Return the 1st of the month following *from_date* (or today)."""
    ref = _ensure_date(from_date) if from_date else date.today()
    if ref.month == 12:
        return date(ref.year + 1, 1, 1)
    return date(ref.year, ref.month + 1, 1)


def days_remaining_in_month(from_date: date | datetime | str | None = None) -> Tuple[int, int]:
    """
    Returns (days_remaining, days_in_month) from *from_date* (inclusive) to end of its month.

    Example: from_date = 2026-03-15 in a 31-day month
      → days_remaining = 17  (15, 16, … 31)
      → days_in_month  = 31
    """
    ref = _ensure_date(from_date) if from_date else date.today()
    dim = calendar.monthrange(ref.year, ref.month)[1]   # days in month
    remaining = dim - ref.day + 1                       # inclusive of today
    return remaining, dim


def calculate_prorata(
    monthly_amount: float,
    from_date: date | datetime | str | None = None,
) -> dict:
    """
    Calculate the pro-rated first charge for a monthly subscription starting on *from_date*.

    Returns a dict with:
      prorata_amount    – rounded to 2 dp
      days_remaining    – days from start_date to end of month (inclusive)
      days_in_month     – total calendar days in that month
      next_billing_date – ISO string of the 1st of the following month
      daily_rate        – monthly_amount / days_in_month
    """
    remaining, dim = days_remaining_in_month(from_date)
    daily = monthly_amount / dim
    amount = round(daily * remaining, 2)
    nbd = next_first_of_month(from_date)
    return {
        "prorata_amount": amount,
        "days_remaining": remaining,
        "days_in_month": dim,
        "next_billing_date": nbd.isoformat(),
        "daily_rate": round(daily, 6),
    }


def calculate_upgrade_prorata(
    old_monthly_amount: float,
    new_monthly_amount: float,
    upgrade_date: date | datetime | str | None = None,
) -> dict:
    """
    Calculate the pro-rata *difference* charge when upgrading mid-month.

    The partner pays the difference between the new and old plan for the
    remaining days of the current month.
    """
    diff = max(new_monthly_amount - old_monthly_amount, 0.0)
    remaining, dim = days_remaining_in_month(upgrade_date)
    daily_diff = diff / dim
    amount = round(daily_diff * remaining, 2)
    nbd = next_first_of_month(upgrade_date)
    return {
        "prorata_amount": amount,
        "days_remaining": remaining,
        "days_in_month": dim,
        "next_billing_date": nbd.isoformat(),
        "old_monthly_amount": old_monthly_amount,
        "new_monthly_amount": new_monthly_amount,
        "daily_diff_rate": round(daily_diff, 6),
    }


def calculate_upgrade_flat(old_monthly: float, new_monthly: float) -> float:
    """Flat monthly-difference charge for ongoing plan upgrades.
    Returns the positive difference, or 0 if the new plan is cheaper/same.
    """
    return round(max(0.0, new_monthly - old_monthly), 2)


def advance_billing_date(current_date: "date | datetime | str", billing_interval: str = "monthly") -> str:
    """
    Advance a billing date by one billing interval.

    weekly    → +7 days
    monthly   → +1 month  (1st of next month)
    quarterly → +3 months (1st of month 3 months later)
    biannual  → +6 months
    annual    → +12 months (1st of same month next year)
    """
    ref = _ensure_date(current_date)
    if billing_interval == "weekly":
        from datetime import timedelta as _td
        return (ref + _td(days=7)).isoformat()
    _INTERVAL_MONTHS = {"monthly": 1, "quarterly": 3, "biannual": 6, "annual": 12}
    months = _INTERVAL_MONTHS.get(billing_interval, 1)
    new_month = ref.month + months
    new_year = ref.year + (new_month - 1) // 12
    new_month = (new_month - 1) % 12 + 1
    return date(new_year, new_month, 1).isoformat()


def calculate_next_billing_date(
    from_date: "date | datetime | str | None",
    billing_mode: str = "prorated",
) -> str:
    """
    Return the next billing date based on the billing_mode:

    'prorated' (default / platform admin):
        Always the 1st of the month AFTER from_date.

    'monthly':
        Same day-of-month as from_date, one month later.
        Clamped to last day of month if needed (e.g., Jan 31 → Feb 28).
    """
    ref = _ensure_date(from_date) if from_date else date.today()
    if billing_mode == "monthly":
        # Same day next month, clamped to last day of month
        if ref.month == 12:
            next_m = date(ref.year + 1, 1, ref.day)
        else:
            next_dim = calendar.monthrange(ref.year, ref.month + 1)[1]
            next_m = date(ref.year, ref.month + 1, min(ref.day, next_dim))
        return next_m.isoformat()
    # default: prorated → 1st of next month
    return next_first_of_month(ref).isoformat()


# ---------------------------------------------------------------------------
# Plan upgrade confirmation (called after Stripe payment confirmed)
# ---------------------------------------------------------------------------

async def confirm_plan_upgrade(pending: dict, partner_id: str) -> bool:
    """
    Atomically confirms a pending plan upgrade after Stripe payment is verified.

    - Marks pending_plan_upgrades doc as "completed" (atomic, idempotent)
    - Creates a partner_order with status "paid"
    - Updates the partner subscription
    - Updates the tenant license

    Returns True if the upgrade was applied, False if already processed.
    """
    from db.session import db
    from core.helpers import now_iso, make_id
    from services.audit_service import create_audit_log

    # Atomic idempotency: only process once
    old = await db.pending_plan_upgrades.find_one_and_update(
        {"id": pending["id"], "status": "pending"},
        {"$set": {"status": "completed", "completed_at": now_iso()}},
    )
    if old is None:
        return False  # Already processed

    plan_id = pending.get("plan_id")
    sub_id = pending.get("sub_id")
    amount = pending.get("amount", 0)
    currency = pending.get("currency", "GBP")
    partner_name = pending.get("partner_name", "")
    plan_name = pending.get("plan_name", "")
    coupon_id = pending.get("coupon_id", "")
    coupon_code = pending.get("coupon_code", "")
    stripe_session_id = pending.get("stripe_session_id", "")
    order_number = pending.get("order_number", "")
    now = now_iso()
    today_str = now[:10]

    # Create confirmed partner_order
    order_id = make_id()
    await db.partner_orders.insert_one({
        "id": order_id, "order_number": order_number,
        "subscription_id": sub_id or "",
        "partner_id": partner_id, "partner_name": partner_name,
        "plan_id": plan_id or "", "plan_name": plan_name,
        "description": f"Plan upgrade to {plan_name}",
        "amount": amount, "currency": currency,
        "base_amount": pending.get("base_amount", amount),
        "discount_amount": pending.get("discount_amount", 0),
        "coupon_code": coupon_code, "coupon_id": coupon_id,
        "status": "paid", "payment_method": "card",
        "invoice_date": today_str, "due_date": today_str,
        "paid_at": now, "order_type": "ongoing_upgrade",
        "stripe_session_id": stripe_session_id,
        "created_at": now, "created_by": "stripe_payment",
    })

    # Update partner subscription plan
    if sub_id and plan_id:
        plan_doc = await db.plans.find_one({"id": plan_id}, {"_id": 0})
        if plan_doc:
            await db.partner_subscriptions.update_one(
                {"id": sub_id},
                {"$set": {
                    "status": "active", "payment_method": "card",
                    "plan_id": plan_id, "plan_name": plan_doc.get("name", plan_name),
                    "amount": plan_doc.get("monthly_price", amount),
                    "updated_at": now,
                }},
            )

    # Upgrade tenant license
    if plan_id:
        plan_doc = await db.plans.find_one({"id": plan_id}, {"_id": 0})
        if plan_doc:
            limits = {k: v for k, v in plan_doc.items() if k.startswith("max_")}
            await db.tenants.update_one(
                {"id": partner_id},
                {"$set": {"license": {
                    "plan_id": plan_doc["id"], "plan_name": plan_doc["name"],
                    "assigned_at": now, **limits,
                }}},
            )
            await create_audit_log(
                entity_type="tenant", entity_id=partner_id,
                action="plan_upgraded_via_stripe", actor="stripe_payment",
                details={"plan_id": plan_id, "order_id": order_id, "session_id": stripe_session_id},
            )

    # Record coupon usage if a coupon was applied
    if coupon_id:
        await db.coupons.update_one(
            {"id": coupon_id},
            {"$inc": {"usage_count": 1}, "$addToSet": {"used_by_orgs": partner_id}},
        )

    return True

