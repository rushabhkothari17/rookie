"""APScheduler-based background job service.

Currently implements:
- Daily renewal reminder emails (30 days before renewal_date) for both
  customer subscriptions and partner subscriptions.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


async def send_renewal_reminders() -> None:
    """Daily job: send renewal reminders 30 days before renewal_date."""
    logger.info("[Scheduler] Running renewal reminder job…")
    from db.session import db
    from services.email_service import EmailService
    from core.tenant import DEFAULT_TENANT_ID

    today = datetime.now(timezone.utc).date()
    target_date = today + timedelta(days=30)
    target_str = target_date.isoformat()  # "YYYY-MM-DD"

    # ── Customer subscriptions ───────────────────────────────────────────────
    cursor = db.subscriptions.find(
        {
            "status": "active",
            "reminder_sent_30d": {"$ne": True},
            "renewal_date": {"$regex": f"^{target_str}"},
        },
        {"_id": 0},
    )
    async for sub in cursor:
        try:
            customer = await db.customers.find_one({"id": sub.get("customer_id")}, {"_id": 0}) or {}
            user = await db.users.find_one({"id": customer.get("user_id", "")}, {"_id": 0}) or {}
            email = user.get("email") or customer.get("email")
            if not email:
                continue

            tenant_id = sub.get("tenant_id", DEFAULT_TENANT_ID)
            await EmailService.send(
                trigger="subscription_renewal_reminder",
                recipient=email,
                variables={
                    "customer_name": customer.get("full_name") or user.get("full_name") or email,
                    "subscription_number": sub.get("subscription_number", ""),
                    "plan_name": sub.get("plan_name", ""),
                    "amount": f"{sub.get('amount', 0):.2f}",
                    "currency": sub.get("currency", ""),
                    "renewal_date": target_str,
                },
                db=db,
                tenant_id=tenant_id,
            )
            await db.subscriptions.update_one(
                {"id": sub["id"]},
                {"$set": {"reminder_sent_30d": True}},
            )
            logger.info(f"[Scheduler] Sent renewal reminder to {email} for sub {sub.get('subscription_number')}")
        except Exception as exc:
            logger.error(f"[Scheduler] Failed to send reminder for sub {sub.get('id')}: {exc}")

    # ── Partner subscriptions ────────────────────────────────────────────────
    partner_cursor = db.partner_subscriptions.find(
        {
            "status": "active",
            "reminder_sent_30d": {"$ne": True},
            "next_billing_date": {"$regex": f"^{target_str}"},
        },
        {"_id": 0},
    )
    async for psub in partner_cursor:
        try:
            partner_admin = await db.users.find_one(
                {"tenant_id": psub.get("partner_id"), "role": {"$in": ["partner_super_admin", "partner_admin"]}},
                {"_id": 0, "email": 1, "full_name": 1},
            ) or {}
            email = partner_admin.get("email")
            if not email:
                continue

            await EmailService.send(
                trigger="partner_subscription_renewal_reminder",
                recipient=email,
                variables={
                    "partner_name": psub.get("partner_name", ""),
                    "subscription_number": psub.get("subscription_number", ""),
                    "plan_name": psub.get("plan_name", "—"),
                    "amount": f"{psub.get('amount', 0):.2f}",
                    "currency": psub.get("currency", ""),
                    "renewal_date": target_str,
                    "billing_interval": psub.get("billing_interval", ""),
                },
                db=db,
                tenant_id=DEFAULT_TENANT_ID,
            )
            await db.partner_subscriptions.update_one(
                {"id": psub["id"]},
                {"$set": {"reminder_sent_30d": True}},
            )
            logger.info(f"[Scheduler] Sent partner renewal reminder to {email} for sub {psub.get('subscription_number')}")
        except Exception as exc:
            logger.error(f"[Scheduler] Failed to send partner reminder for sub {psub.get('id')}: {exc}")

    logger.info("[Scheduler] Renewal reminder job complete.")


def start_scheduler() -> None:
    """Register and start the APScheduler background jobs."""
    scheduler = get_scheduler()
    if scheduler.running:
        return

    # Daily at 09:00 UTC
    scheduler.add_job(
        send_renewal_reminders,
        trigger="cron",
        hour=9,
        minute=0,
        id="renewal_reminders",
        replace_existing=True,
        misfire_grace_time=3600,  # 1 hour grace window
    )

    scheduler.start()
    logger.info("[Scheduler] APScheduler started — renewal_reminders job registered (daily at 09:00 UTC).")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[Scheduler] APScheduler stopped.")
