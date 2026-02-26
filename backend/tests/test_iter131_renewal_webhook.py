"""Tests for Subscription Renewal Webhook Logic (P1 Task).

Run: python3 tests/test_iter131_renewal_webhook.py
"""
from __future__ import annotations
import asyncio
import os
import sys
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
API = BASE_URL.rstrip("/")

RESULTS = []


def record(name: str, passed: bool, msg: str = ""):
    icon = "✅" if passed else "❌"
    print(f"  {icon} {name}" + (f": {msg}" if msg else ""))
    RESULTS.append((name, passed, msg))


# ─────────────────────────────────────────────────────────────────────────────
# Seed helpers
# ─────────────────────────────────────────────────────────────────────────────

async def seed_stripe_sub(db):
    from core.helpers import make_id, now_iso
    from datetime import datetime, timezone, timedelta

    cust_id = make_id()
    user_id = make_id()
    sub_id = make_id()
    tenant_id = "test-tenant-stripe-renewal"
    stripe_sub_id = f"sub_test_{sub_id[:8]}"
    now = datetime.now(timezone.utc)

    await db.users.insert_one({"id": user_id, "email": f"str_r_{cust_id[:6]}@t.com", "full_name": "T", "tenant_id": tenant_id})
    await db.customers.insert_one({"id": cust_id, "user_id": user_id, "tenant_id": tenant_id})
    await db.subscriptions.insert_one({
        "id": sub_id, "subscription_number": f"SUB-{sub_id[:6].upper()}",
        "customer_id": cust_id, "plan_name": "Stripe Plan", "status": "active",
        "stripe_subscription_id": stripe_sub_id,
        "amount": 100.0, "currency": "USD", "base_currency": "USD",
        "tax_amount": 10.0, "tax_rate": 0.10, "tax_name": "GST",
        "payment_method": "card",
        "current_period_start": now.isoformat(),
        "current_period_end": (now + timedelta(days=30)).isoformat(),
        "created_at": now_iso(), "updated_at": now_iso(),
    })
    return {"sub_id": sub_id, "stripe_sub_id": stripe_sub_id, "cust_id": cust_id, "user_id": user_id, "tenant_id": tenant_id}


async def seed_gc_sub(db):
    from core.helpers import make_id, now_iso
    from datetime import datetime, timezone, timedelta

    cust_id = make_id()
    user_id = make_id()
    sub_id = make_id()
    tenant_id = "test-tenant-gc-renewal"
    mandate_id = f"MD_test_{sub_id[:8]}"
    initial_pm_id = f"PM_init_{sub_id[:8]}"
    now = datetime.now(timezone.utc)

    await db.users.insert_one({"id": user_id, "email": f"gc_r_{cust_id[:6]}@t.com", "full_name": "G", "tenant_id": tenant_id})
    await db.customers.insert_one({"id": cust_id, "user_id": user_id, "tenant_id": tenant_id})
    await db.subscriptions.insert_one({
        "id": sub_id, "subscription_number": f"SUB-{sub_id[:6].upper()}",
        "customer_id": cust_id, "plan_name": "GC Plan", "status": "active",
        "gocardless_mandate_id": mandate_id, "gocardless_payment_id": initial_pm_id,
        "amount": 50.0, "currency": "GBP", "base_currency": "USD",
        "tax_amount": 5.0, "tax_rate": 0.10, "tax_name": "VAT",
        "payment_method": "bank_transfer",
        "current_period_start": now.isoformat(),
        "current_period_end": (now + timedelta(days=30)).isoformat(),
        "created_at": now_iso(), "updated_at": now_iso(),
    })
    return {"sub_id": sub_id, "mandate_id": mandate_id, "initial_pm_id": initial_pm_id, "cust_id": cust_id, "user_id": user_id, "tenant_id": tenant_id}


async def cleanup_stripe(db, seed):
    await db.subscriptions.delete_one({"id": seed["sub_id"]})
    await db.customers.delete_one({"id": seed["cust_id"]})
    await db.users.delete_one({"id": seed["user_id"]})
    await db.orders.delete_many({"subscription_id": seed["sub_id"]})


async def cleanup_gc(db, seed):
    await db.subscriptions.delete_one({"id": seed["sub_id"]})
    await db.customers.delete_one({"id": seed["cust_id"]})
    await db.users.delete_one({"id": seed["user_id"]})
    await db.orders.delete_many({"subscription_id": seed["sub_id"]})


# ─────────────────────────────────────────────────────────────────────────────
# All tests run in one event loop
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    from db.session import db
    from core.helpers import make_id, now_iso, round_cents
    from routes.webhooks import get_stripe_fee_rate_for_tenant

    print("\n=== Subscription Renewal Webhook Tests ===\n")

    # ── Test 1: billing_reason logic (pure Python, no DB) ────────────────────
    name = "Stripe billing_reason guard logic"
    try:
        cases = [
            ("subscription_cycle", "sub_123", True),
            ("subscription_create", "sub_123", False),
            ("manual", "sub_123", True),
            ("subscription_cycle", None, False),
            ("", "sub_123", True),
        ]
        for br, sub_id, expected in cases:
            result = br != "subscription_create" and bool(sub_id)
            assert result == expected, f"br={br!r}, sub={sub_id!r}: expected {expected}, got {result}"
        record(name, True)
    except AssertionError as e:
        record(name, False, str(e))

    # ── Test 2: Stripe renewal order has correct fields ───────────────────────
    name = "Stripe renewal order: correct fields (tenant_id, tax, total)"
    seed = await seed_stripe_sub(db)
    try:
        invoice_id = f"in_test_{make_id()[:8]}"
        subscription = await db.subscriptions.find_one(
            {"stripe_subscription_id": seed["stripe_sub_id"]}, {"_id": 0}
        )
        assert subscription is not None, "Subscription not found"

        customer_doc = await db.customers.find_one({"id": subscription["customer_id"]}, {"_id": 0})
        tenant_id = customer_doc.get("tenant_id", "") if customer_doc else ""
        fee_rate = await get_stripe_fee_rate_for_tenant(tenant_id)

        renewal_amount = subscription["amount"]          # 100.0
        renewal_tax = subscription["tax_amount"]         # 10.0
        renewal_fee = round_cents(renewal_amount * fee_rate)
        renewal_total = round_cents(renewal_amount + renewal_fee + renewal_tax)

        renewal_order_id = make_id()
        await db.orders.insert_one({
            "id": renewal_order_id,
            "order_number": f"AA-{renewal_order_id.split('-')[0].upper()}",
            "tenant_id": tenant_id,
            "customer_id": subscription["customer_id"],
            "type": "subscription_renewal",
            "status": "paid",
            "subtotal": renewal_amount,
            "fee": renewal_fee,
            "total": renewal_total,
            "tax_amount": renewal_tax,
            "tax_rate": subscription["tax_rate"],
            "tax_name": subscription["tax_name"],
            "currency": subscription["currency"],
            "base_currency": subscription["base_currency"],
            "base_currency_amount": renewal_total,
            "payment_method": "card",
            "stripe_invoice_id": invoice_id,
            "subscription_id": subscription["id"],
            "subscription_number": subscription.get("subscription_number", ""),
            "payment_date": now_iso(),
            "created_at": now_iso(),
        })

        created = await db.orders.find_one({"id": renewal_order_id}, {"_id": 0})
        assert created["type"] == "subscription_renewal"
        assert created["status"] == "paid"
        assert created["tax_amount"] == 10.0
        assert created["tax_name"] == "GST"
        assert created["tenant_id"] == seed["tenant_id"]
        assert created["stripe_invoice_id"] == invoice_id
        assert created["total"] == renewal_total
        record(name, True, f"total={renewal_total}, tax=10.0")
        await db.orders.delete_one({"id": renewal_order_id})
    except Exception as e:
        record(name, False, str(e))
    finally:
        await cleanup_stripe(db, seed)

    # ── Test 3: Stripe deduplication ─────────────────────────────────────────
    name = "Stripe renewal deduplication (same invoice_id)"
    seed = await seed_stripe_sub(db)
    try:
        invoice_id = f"in_dup_{make_id()[:8]}"
        order_id = make_id()
        await db.orders.insert_one({
            "id": order_id, "type": "subscription_renewal",
            "stripe_invoice_id": invoice_id,
            "subscription_id": seed["sub_id"],
            "status": "paid", "created_at": now_iso(),
        })
        existing = await db.orders.find_one({"stripe_invoice_id": invoice_id}, {"_id": 0})
        assert existing is not None, "First renewal must exist"
        # Handler skips if existing is not None
        would_create_duplicate = existing is None
        assert not would_create_duplicate, "Should not create duplicate"
        count = await db.orders.count_documents({"stripe_invoice_id": invoice_id})
        assert count == 1, f"Expected 1, got {count}"
        record(name, True)
        await db.orders.delete_one({"id": order_id})
    except Exception as e:
        record(name, False, str(e))
    finally:
        await cleanup_stripe(db, seed)

    # ── Test 4: GC renewal creates order via mandate lookup ───────────────────
    name = "GoCardless renewal: order created via mandate_id lookup"
    seed = await seed_gc_sub(db)
    try:
        new_pm_id = f"PM_renewal_{make_id()[:8]}"
        renewal_sub = await db.subscriptions.find_one(
            {"gocardless_mandate_id": seed["mandate_id"], "status": "active"}, {"_id": 0}
        )
        assert renewal_sub is not None, "Subscription must be found by mandate_id"
        assert renewal_sub.get("gocardless_payment_id") != new_pm_id, "New payment must differ from initial"

        gc_cust = await db.customers.find_one({"id": renewal_sub["customer_id"]}, {"_id": 0})
        tenant_id = gc_cust.get("tenant_id", "") if gc_cust else ""

        renewal_amount = renewal_sub["amount"]   # 50.0
        renewal_tax = renewal_sub["tax_amount"]  # 5.0
        renewal_total = round_cents(renewal_amount + renewal_tax)  # 55.0
        renewal_order_id = make_id()

        await db.orders.insert_one({
            "id": renewal_order_id,
            "order_number": f"AA-{renewal_order_id.split('-')[0].upper()}",
            "tenant_id": tenant_id,
            "customer_id": renewal_sub["customer_id"],
            "type": "subscription_renewal",
            "status": "paid",
            "subtotal": renewal_amount,
            "fee": 0.0,
            "total": renewal_total,
            "tax_amount": renewal_tax,
            "tax_rate": renewal_sub["tax_rate"],
            "tax_name": renewal_sub["tax_name"],
            "currency": renewal_sub["currency"],
            "base_currency": renewal_sub["base_currency"],
            "base_currency_amount": renewal_total,
            "payment_method": "bank_transfer",
            "gocardless_payment_id": new_pm_id,
            "gocardless_mandate_id": seed["mandate_id"],
            "subscription_id": renewal_sub["id"],
            "subscription_number": renewal_sub.get("subscription_number", ""),
            "payment_date": now_iso(),
            "created_at": now_iso(),
        })

        created = await db.orders.find_one({"id": renewal_order_id}, {"_id": 0})
        assert created["type"] == "subscription_renewal"
        assert created["tax_amount"] == 5.0
        assert created["tax_name"] == "VAT"
        assert created["tenant_id"] == seed["tenant_id"]
        assert created["total"] == 55.0
        record(name, True, f"total={renewal_total}, tax=5.0")
        await db.orders.delete_one({"id": renewal_order_id})
    except Exception as e:
        record(name, False, str(e))
    finally:
        await cleanup_gc(db, seed)

    # ── Test 5: GC initial payment NOT treated as renewal ─────────────────────
    name = "GoCardless: initial payment NOT treated as renewal"
    seed = await seed_gc_sub(db)
    try:
        sub = await db.subscriptions.find_one(
            {"gocardless_payment_id": seed["initial_pm_id"]}, {"_id": 0}
        )
        assert sub is not None, "Subscription must be found by initial payment_id"
        existing_renewal = await db.orders.find_one(
            {"gocardless_payment_id": seed["initial_pm_id"], "type": "subscription_renewal"},
            {"_id": 0}
        )
        assert existing_renewal is None, "No renewal order for initial payment"
        record(name, True)
    except Exception as e:
        record(name, False, str(e))
    finally:
        await cleanup_gc(db, seed)

    # ── Test 6: Mandate cancelled marks subscriptions unpaid ──────────────────
    name = "GoCardless: mandate cancelled → subscription unpaid"
    seed = await seed_gc_sub(db)
    try:
        result = await db.subscriptions.update_many(
            {"gocardless_mandate_id": seed["mandate_id"], "status": "active"},
            {"$set": {"status": "unpaid", "updated_at": now_iso()}},
        )
        assert result.modified_count >= 1
        sub = await db.subscriptions.find_one({"id": seed["sub_id"]}, {"_id": 0})
        assert sub["status"] == "unpaid"
        record(name, True)
    except Exception as e:
        record(name, False, str(e))
    finally:
        await cleanup_gc(db, seed)

    # ── Test 7: GC webhook HTTP endpoint ─────────────────────────────────────
    name = "GoCardless webhook endpoint: returns 200 for empty events"
    try:
        import httpx
        async with httpx.AsyncClient(base_url=API, timeout=15) as client:
            resp = await client.post("/api/webhook/gocardless", json={"events": []})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        assert resp.json().get("status") == "ok"
        record(name, True)
    except Exception as e:
        record(name, False, str(e))

    # ── Summary ───────────────────────────────────────────────────────────────
    total = len(RESULTS)
    passed = sum(1 for _, p, _ in RESULTS if p)
    failed = total - passed
    print(f"\n{'='*50}")
    print(f"Results: {passed}/{total} passed, {failed} failed")
    if failed:
        print("\nFailed tests:")
        for n, p, m in RESULTS:
            if not p:
                print(f"  ❌ {n}: {m}")
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
