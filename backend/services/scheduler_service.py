"""APScheduler-based background job service.

Jobs registered (all run daily at 09:00 UTC):
1. send_renewal_reminders  — configurable reminder_days per subscription / tenant
2. auto_cancel_subscriptions — cancel subs at contract term end
3. create_renewal_orders   — create pending orders for manual-payment subs on billing day
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


# ---------------------------------------------------------------------------
# Job 1: Configurable renewal reminders
# ---------------------------------------------------------------------------

async def send_renewal_reminders() -> None:
    """Daily job: send renewal reminders based on per-subscription or per-tenant reminder_days.

    Resolution order:
      1. subscription.reminder_days  (explicit override)
      2. tenant.default_reminder_days (org-level default)
      3. None → skip (no reminder sent)
    """
    logger.info("[Scheduler] Running renewal reminder job…")
    from db.session import db
    from services.email_service import EmailService
    from core.tenant import DEFAULT_TENANT_ID
    from core.helpers import now_iso

    today = datetime.now(timezone.utc).date()
    tenant_cache: dict = {}  # tid -> Optional[int]

    async def _tenant_reminder_days(tid: str) -> Optional[int]:
        if tid not in tenant_cache:
            t = await db.tenants.find_one({"id": tid}, {"_id": 0, "default_reminder_days": 1})
            tenant_cache[tid] = (t.get("default_reminder_days") if t else None)
        return tenant_cache[tid]

    # ── Customer subscriptions ───────────────────────────────────────────────
    cursor = db.subscriptions.find({"status": "active"}, {"_id": 0})
    async for sub in cursor:
        try:
            renewal_str = (sub.get("renewal_date") or "")[:10]
            if not renewal_str:
                continue
            # Skip if already sent for this renewal date
            if sub.get("reminder_sent_for_renewal_date") == renewal_str:
                continue

            # Effective reminder_days
            reminder_days = sub.get("reminder_days")
            if reminder_days is None:
                tid = sub.get("tenant_id", DEFAULT_TENANT_ID)
                reminder_days = await _tenant_reminder_days(tid)
            if reminder_days is None:
                continue  # no reminder configured

            try:
                renewal_date = datetime.fromisoformat(renewal_str).date()
            except Exception:
                continue
            if (renewal_date - today).days != reminder_days:
                continue

            # Fetch recipient
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
                    "renewal_date": renewal_str,
                },
                db=db,
                tenant_id=tenant_id,
            )
            await db.subscriptions.update_one(
                {"id": sub["id"]},
                {"$set": {"reminder_sent_for_renewal_date": renewal_str}},
            )
            logger.info(f"[Scheduler] Sent renewal reminder to {email} for sub {sub.get('subscription_number')}")
        except Exception as exc:
            logger.error(f"[Scheduler] Failed to send reminder for sub {sub.get('id')}: {exc}")

    # ── Partner subscriptions ────────────────────────────────────────────────
    partner_cursor = db.partner_subscriptions.find({"status": "active"}, {"_id": 0})
    async for psub in partner_cursor:
        try:
            renewal_str = (psub.get("next_billing_date") or "")[:10]
            if not renewal_str:
                continue
            if psub.get("reminder_sent_for_renewal_date") == renewal_str:
                continue

            # Partner subs use their own reminder_days, then platform tenant default
            reminder_days = psub.get("reminder_days")
            if reminder_days is None:
                reminder_days = await _tenant_reminder_days(DEFAULT_TENANT_ID)
            if reminder_days is None:
                continue

            try:
                renewal_date = datetime.fromisoformat(renewal_str).date()
            except Exception:
                continue
            if (renewal_date - today).days != reminder_days:
                continue

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
                    "renewal_date": renewal_str,
                    "billing_interval": psub.get("billing_interval", ""),
                },
                db=db,
                tenant_id=DEFAULT_TENANT_ID,
            )
            await db.partner_subscriptions.update_one(
                {"id": psub["id"]},
                {"$set": {"reminder_sent_for_renewal_date": renewal_str}},
            )
            logger.info(f"[Scheduler] Sent partner renewal reminder to {email} for sub {psub.get('subscription_number')}")
        except Exception as exc:
            logger.error(f"[Scheduler] Failed to send partner reminder for sub {psub.get('id')}: {exc}")

    logger.info("[Scheduler] Renewal reminder job complete.")


# ---------------------------------------------------------------------------
# Job 2: Auto-cancel subscriptions at contract term end
# ---------------------------------------------------------------------------

async def auto_cancel_subscriptions() -> None:
    """Daily job: cancel subscriptions where contract_end_date <= today and auto_cancel_on_termination is True."""
    logger.info("[Scheduler] Running auto-cancel job…")
    from db.session import db
    from services.email_service import EmailService
    from core.tenant import DEFAULT_TENANT_ID
    from core.helpers import now_iso, make_id

    today = datetime.now(timezone.utc).date()
    tomorrow_str = (today + timedelta(days=1)).isoformat()

    # ── Customer subscriptions ───────────────────────────────────────────────
    cursor = db.subscriptions.find(
        {
            "status": "active",
            "auto_cancel_on_termination": True,
            "contract_end_date": {"$lt": tomorrow_str, "$gt": ""},
        },
        {"_id": 0},
    )
    async for sub in cursor:
        try:
            cancelled_at = now_iso()
            await db.subscriptions.update_one(
                {"id": sub["id"]},
                {"$set": {"status": "cancelled", "cancelled_at": cancelled_at, "updated_at": cancelled_at}},
            )
            logger.info(f"[Scheduler] Auto-cancelled customer sub {sub.get('subscription_number')}")

            # Send cancellation email
            customer = await db.customers.find_one({"id": sub.get("customer_id")}, {"_id": 0}) or {}
            user = await db.users.find_one({"id": customer.get("user_id", "")}, {"_id": 0}) or {}
            email = user.get("email") or customer.get("email")
            if email:
                await EmailService.send(
                    trigger="subscription_terminated",
                    recipient=email,
                    variables={
                        "recipient_name": customer.get("full_name") or user.get("full_name") or email,
                        "subscription_number": sub.get("subscription_number", ""),
                        "plan_name": sub.get("plan_name", "—"),
                        "cancelled_at": cancelled_at[:10],
                        "cancel_reason": "Contract term ended — automatic cancellation",
                    },
                    db=db,
                    tenant_id=sub.get("tenant_id", DEFAULT_TENANT_ID),
                )
        except Exception as exc:
            logger.error(f"[Scheduler] Failed to auto-cancel sub {sub.get('id')}: {exc}")

    # ── Partner subscriptions ────────────────────────────────────────────────
    partner_cursor = db.partner_subscriptions.find(
        {
            "status": "active",
            "auto_cancel_on_termination": True,
            "contract_end_date": {"$lt": tomorrow_str, "$gt": ""},
        },
        {"_id": 0},
    )
    async for psub in partner_cursor:
        try:
            cancelled_at = now_iso()
            await db.partner_subscriptions.update_one(
                {"id": psub["id"]},
                {"$set": {"status": "cancelled", "cancelled_at": cancelled_at, "updated_at": cancelled_at}},
            )
            logger.info(f"[Scheduler] Auto-cancelled partner sub {psub.get('subscription_number')}")

            # Send cancellation email to partner admin
            partner_admin = await db.users.find_one(
                {"tenant_id": psub.get("partner_id"), "role": {"$in": ["partner_super_admin", "partner_admin"]}},
                {"_id": 0, "email": 1, "full_name": 1},
            ) or {}
            email = partner_admin.get("email")
            if email:
                await EmailService.send(
                    trigger="subscription_terminated",
                    recipient=email,
                    variables={
                        "recipient_name": psub.get("partner_name", ""),
                        "subscription_number": psub.get("subscription_number", ""),
                        "plan_name": psub.get("plan_name", "—"),
                        "cancelled_at": cancelled_at[:10],
                        "cancel_reason": "Contract term ended — automatic cancellation",
                    },
                    db=db,
                    tenant_id=DEFAULT_TENANT_ID,
                )
        except Exception as exc:
            logger.error(f"[Scheduler] Failed to auto-cancel partner sub {psub.get('id')}: {exc}")

    logger.info("[Scheduler] Auto-cancel job complete.")


# ---------------------------------------------------------------------------
# Job 3: Auto-create renewal orders for manual-payment subscriptions
# ---------------------------------------------------------------------------

async def create_renewal_orders() -> None:
    """Daily job: create a pending renewal order for active manual-payment subscriptions
    whose billing date is today.

    Only applies to payment_method in {offline, bank_transfer, manual}.
    Stripe and GoCardless subscriptions auto-renew via webhooks — excluded.
    """
    logger.info("[Scheduler] Running auto renewal-order job…")
    from db.session import db
    from services.email_service import EmailService
    from core.tenant import DEFAULT_TENANT_ID
    from core.helpers import now_iso, make_id

    today = datetime.now(timezone.utc).date()
    today_str = today.isoformat()
    manual_methods = ["offline", "bank_transfer", "manual"]

    # ── Customer subscriptions ───────────────────────────────────────────────
    cursor = db.subscriptions.find(
        {
            "status": "active",
            "payment_method": {"$in": manual_methods},
            "renewal_date": {"$regex": f"^{today_str}"},
            "auto_renewal_order_date": {"$ne": today_str},
        },
        {"_id": 0},
    )
    async for sub in cursor:
        try:
            order_id = make_id()
            order_number = f"AA-{order_id.split('-')[0].upper()}"
            order_doc = {
                "id": order_id,
                "tenant_id": sub.get("tenant_id"),
                "order_number": order_number,
                "customer_id": sub.get("customer_id"),
                "subscription_id": sub["id"],
                "subscription_number": sub.get("subscription_number", ""),
                "type": "subscription_renewal",
                "status": "pending",
                "subtotal": sub.get("amount", 0),
                "discount_amount": 0.0,
                "fee": 0.0,
                "total": sub.get("amount", 0),
                "currency": sub.get("currency", "USD"),
                "payment_method": sub.get("payment_method", "offline"),
                "created_at": now_iso(),
                "created_by": "scheduler",
            }
            await db.orders.insert_one(order_doc)
            await db.subscriptions.update_one(
                {"id": sub["id"]},
                {"$set": {"auto_renewal_order_date": today_str}},
            )
            logger.info(f"[Scheduler] Created renewal order {order_number} for sub {sub.get('subscription_number')}")
        except Exception as exc:
            logger.error(f"[Scheduler] Failed to create renewal order for sub {sub.get('id')}: {exc}")

    # ── Partner subscriptions ────────────────────────────────────────────────
    partner_cursor = db.partner_subscriptions.find(
        {
            "status": "active",
            "payment_method": {"$in": manual_methods},
            "next_billing_date": {"$regex": f"^{today_str}"},
            "auto_renewal_order_date": {"$ne": today_str},
        },
        {"_id": 0},
    )
    order_seq = await db.partner_orders.count_documents({})
    async for psub in partner_cursor:
        try:
            order_seq += 1
            order_number = f"PO-{datetime.now(timezone.utc).strftime('%Y')}-{order_seq:04d}"
            order_id = make_id()
            order_doc = {
                "id": order_id,
                "order_number": order_number,
                "partner_id": psub.get("partner_id"),
                "partner_name": psub.get("partner_name", ""),
                "plan_id": psub.get("plan_id"),
                "description": f"Subscription renewal — {psub.get('subscription_number', '')}",
                "amount": round(psub.get("amount", 0), 2),
                "currency": psub.get("currency", "GBP"),
                "status": "pending",
                "payment_method": psub.get("payment_method", "offline"),
                "invoice_date": today_str,
                "subscription_id": psub["id"],
                "subscription_number": psub.get("subscription_number", ""),
                "created_at": now_iso(),
                "created_by": "scheduler",
            }
            await db.partner_orders.insert_one(order_doc)
            await db.partner_subscriptions.update_one(
                {"id": psub["id"]},
                {"$set": {"auto_renewal_order_date": today_str}},
            )

            # Notify partner admin
            partner_admin = await db.users.find_one(
                {"tenant_id": psub.get("partner_id"), "role": {"$in": ["partner_super_admin", "partner_admin"]}},
                {"_id": 0, "email": 1, "full_name": 1},
            ) or {}
            email = partner_admin.get("email")
            if email:
                await EmailService.send(
                    trigger="partner_order_created",
                    recipient=email,
                    variables={
                        "partner_name": psub.get("partner_name", ""),
                        "order_number": order_number,
                        "description": f"Subscription renewal — {psub.get('subscription_number', '')}",
                        "amount": f"{psub.get('amount', 0):.2f}",
                        "currency": psub.get("currency", "GBP"),
                        "invoice_date": today_str,
                        "due_date": today_str,
                        "payment_method": psub.get("payment_method", "offline").replace("_", " ").title(),
                        "payment_link_section": "",
                    },
                    db=db,
                    tenant_id=DEFAULT_TENANT_ID,
                )
            logger.info(f"[Scheduler] Created partner renewal order {order_number} for sub {psub.get('subscription_number')}")
        except Exception as exc:
            logger.error(f"[Scheduler] Failed to create partner renewal order for sub {psub.get('id')}: {exc}")

    logger.info("[Scheduler] Auto renewal-order job complete.")


# ---------------------------------------------------------------------------
# Scheduler lifecycle
# ---------------------------------------------------------------------------

def start_scheduler() -> None:
    """Register and start the APScheduler background jobs."""
    scheduler = get_scheduler()
    if scheduler.running:
        return

    # All jobs run daily at 09:00 UTC
    scheduler.add_job(
        send_renewal_reminders,
        trigger="cron", hour=9, minute=0,
        id="renewal_reminders", replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        auto_cancel_subscriptions,
        trigger="cron", hour=9, minute=5,
        id="auto_cancel_subs", replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        create_renewal_orders,
        trigger="cron", hour=9, minute=10,
        id="renewal_orders", replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.start()
    logger.info("[Scheduler] APScheduler started — 3 jobs registered (renewal_reminders, auto_cancel_subs, renewal_orders).")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[Scheduler] APScheduler stopped.")
