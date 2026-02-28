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
from datetime import date, datetime, timedelta, timezone
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


def calculate_next_billing_date(
    from_date: date | datetime | str | None,
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
