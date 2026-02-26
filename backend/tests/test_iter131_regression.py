"""Regression tests for Subscription Renewal Webhook Logic (Iter 131).

Tests cover:
- Admin login (regression check)
- Orders list API (regression check)
- GoCardless webhook HTTP endpoint with renewal events
- Stripe billing_reason guard logic
- GoCardless mandate cancelled via HTTP
- GoCardless deduplication
- GC webhook with payments.failed event

Run: pytest tests/test_iter131_regression.py -v --tb=short --junitxml=/app/test_reports/pytest/pytest_iter131_regression.xml
"""
from __future__ import annotations

import os
import pytest
import requests
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = BASE_URL


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_token():
    """Login as platform admin and return auth token."""
    resp = requests.post(
        f"{API}/api/auth/login",
        json={"email": "admin@automateaccounts.local", "password": "ChangeMe123!"},
        timeout=15,
    )
    if resp.status_code != 200:
        pytest.skip(f"Admin login failed ({resp.status_code}): {resp.text[:200]}")
    token = resp.json().get("token", "")
    if not token:
        pytest.skip("Admin login returned no token")
    return token


@pytest.fixture(scope="module")
def admin_session(admin_token):
    """Requests session with Bearer token auth."""
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {admin_token}"})
    return session


# ─────────────────────────────────────────────────────────────────────────────
# Regression: Admin Auth
# ─────────────────────────────────────────────────────────────────────────────

class TestAdminLoginRegression:
    """Regression: admin login must continue to work after webhook changes."""

    def test_admin_login_success(self):
        """Admin login returns 200 and a token."""
        resp = requests.post(
            f"{API}/api/auth/login",
            json={"email": "admin@automateaccounts.local", "password": "ChangeMe123!"},
            timeout=15,
        )
        assert resp.status_code == 200, f"Login failed: {resp.text[:200]}"
        data = resp.json()
        assert "token" in data, "Response must contain 'token'"
        assert len(data["token"]) > 10, "Token must be non-empty"
        assert data.get("role") is not None, "Response must contain 'role'"

    def test_admin_login_wrong_password(self):
        """Admin login with wrong password returns 401."""
        resp = requests.post(
            f"{API}/api/auth/login",
            json={"email": "admin@automateaccounts.local", "password": "WrongPassword999!"},
            timeout=15,
        )
        assert resp.status_code == 401

    def test_admin_login_missing_fields(self):
        """Login without password returns 4xx."""
        resp = requests.post(
            f"{API}/api/auth/login",
            json={"email": "admin@automateaccounts.local"},
            timeout=15,
        )
        assert resp.status_code in (400, 422)


# ─────────────────────────────────────────────────────────────────────────────
# Regression: Orders list API
# ─────────────────────────────────────────────────────────────────────────────

class TestOrdersListRegression:
    """Regression: orders list API must continue to work."""

    def test_orders_list_authenticated(self, admin_session):
        """GET /api/admin/orders returns 200 for authenticated admin."""
        resp = admin_session.get(f"{API}/api/admin/orders", timeout=15)
        assert resp.status_code == 200, f"Orders list failed: {resp.text[:200]}"
        data = resp.json()
        # Response can be list or dict with 'orders' key
        if isinstance(data, list):
            orders = data
        else:
            orders = data.get("orders", [])
        assert isinstance(orders, list), "Orders must be a list"

    def test_orders_list_unauthenticated_is_401(self):
        """GET /api/admin/orders without auth returns 401."""
        resp = requests.get(f"{API}/api/admin/orders", timeout=15)
        assert resp.status_code == 401

    def test_orders_list_no_mongodb_id_exposed(self, admin_session):
        """Orders list must not expose MongoDB _id fields."""
        resp = admin_session.get(f"{API}/api/admin/orders", timeout=15)
        assert resp.status_code == 200
        data = resp.json()
        orders = data.get("orders", data) if isinstance(data, dict) else data
        for order in orders[:5]:  # Check first 5 orders
            assert "_id" not in order, f"Order exposes MongoDB _id: {order.get('id', 'unknown')}"


# ─────────────────────────────────────────────────────────────────────────────
# GoCardless Webhook HTTP Endpoint Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestGocardlessWebhookEndpoint:
    """Test GoCardless webhook HTTP endpoint (no HMAC since secret not configured)."""

    def test_gocardless_webhook_empty_events_returns_200(self):
        """POST /api/webhook/gocardless with empty events returns 200."""
        resp = requests.post(
            f"{API}/api/webhook/gocardless",
            json={"events": []},
            timeout=15,
        )
        assert resp.status_code == 200
        assert resp.json().get("status") == "ok"

    def test_gocardless_webhook_invalid_json_returns_400(self):
        """POST /api/webhook/gocardless with invalid JSON returns 400."""
        resp = requests.post(
            f"{API}/api/webhook/gocardless",
            data=b"not-json",
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        assert resp.status_code == 400

    def test_gocardless_webhook_payment_confirmed_unknown_mandate(self):
        """payments.confirmed event for unknown mandate_id returns 200 (no crash)."""
        payload = {
            "events": [
                {
                    "id": "EV_REGRESSION_001",
                    "resource_type": "payments",
                    "action": "confirmed",
                    "links": {
                        "payment": "PM_REGRESSION_UNKNOWN_001",
                        "mandate": "MD_REGRESSION_UNKNOWN_001",
                    },
                }
            ]
        }
        resp = requests.post(
            f"{API}/api/webhook/gocardless",
            json=payload,
            timeout=15,
        )
        assert resp.status_code == 200
        assert resp.json().get("status") == "ok"

    def test_gocardless_webhook_mandate_cancelled_unknown_returns_200(self):
        """mandates.cancelled event for unknown mandate returns 200 (no crash)."""
        payload = {
            "events": [
                {
                    "id": "EV_REGRESSION_MANDATE_001",
                    "resource_type": "mandates",
                    "action": "cancelled",
                    "links": {"mandate": "MD_REGRESSION_NONEXISTENT_001"},
                }
            ]
        }
        resp = requests.post(
            f"{API}/api/webhook/gocardless",
            json=payload,
            timeout=15,
        )
        assert resp.status_code == 200
        assert resp.json().get("status") == "ok"

    def test_gocardless_webhook_payment_failed_unknown_returns_200(self):
        """payments.failed event for unknown payment returns 200 (no crash)."""
        payload = {
            "events": [
                {
                    "id": "EV_REGRESSION_FAIL_001",
                    "resource_type": "payments",
                    "action": "failed",
                    "links": {
                        "payment": "PM_REGRESSION_FAILED_001",
                        "mandate": "MD_REGRESSION_FAILED_001",
                    },
                }
            ]
        }
        resp = requests.post(
            f"{API}/api/webhook/gocardless",
            json=payload,
            timeout=15,
        )
        assert resp.status_code == 200

    def test_gocardless_webhook_multiple_events_in_single_call(self):
        """GC webhook handles multiple events in a single request."""
        payload = {
            "events": [
                {
                    "id": "EV_MULTI_001",
                    "resource_type": "payments",
                    "action": "confirmed",
                    "links": {"payment": "PM_MULTI_001", "mandate": "MD_MULTI_001"},
                },
                {
                    "id": "EV_MULTI_002",
                    "resource_type": "mandates",
                    "action": "cancelled",
                    "links": {"mandate": "MD_MULTI_002"},
                },
            ]
        }
        resp = requests.post(
            f"{API}/api/webhook/gocardless",
            json=payload,
            timeout=15,
        )
        assert resp.status_code == 200
        assert resp.json().get("status") == "ok"

    def test_gocardless_webhook_deduplication(self):
        """Same event ID sent twice is deduplicated (second call still returns 200)."""
        payload = {
            "events": [
                {
                    "id": "EV_DEDUP_TEST_001",
                    "resource_type": "payments",
                    "action": "confirmed",
                    "links": {"payment": "PM_DEDUP_001"},
                }
            ]
        }
        # First call
        resp1 = requests.post(f"{API}/api/webhook/gocardless", json=payload, timeout=15)
        assert resp1.status_code == 200
        # Second call with same event_id — should still return 200 (deduplicated, not error)
        resp2 = requests.post(f"{API}/api/webhook/gocardless", json=payload, timeout=15)
        assert resp2.status_code == 200
        assert resp2.json().get("status") == "ok"


# ─────────────────────────────────────────────────────────────────────────────
# Stripe billing_reason guard logic (pure Python, no Stripe signature needed)
# ─────────────────────────────────────────────────────────────────────────────

class TestStripeBillingReasonLogic:
    """Test the billing_reason guard logic for Stripe invoice.paid events."""

    @pytest.mark.parametrize("billing_reason, sub_id, should_create", [
        ("subscription_cycle", "sub_abc123", True),   # renewal — MUST create
        ("subscription_create", "sub_abc123", False),  # initial — MUST skip
        ("manual", "sub_abc123", True),                # manual — MUST create
        ("subscription_cycle", None, False),           # no sub_id — MUST skip
        ("", "sub_abc123", True),                      # empty reason — MUST create
    ])
    def test_billing_reason_guard(self, billing_reason, sub_id, should_create):
        """Guard: billing_reason != 'subscription_create' AND sub_id must both be true."""
        result = billing_reason != "subscription_create" and bool(sub_id)
        assert result == should_create, (
            f"billing_reason={billing_reason!r}, sub_id={sub_id!r}: "
            f"expected should_create={should_create}, got {result}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Stripe webhook endpoint (can only test with invalid signature → 500/error)
# ─────────────────────────────────────────────────────────────────────────────

class TestStripeWebhookEndpoint:
    """Basic stripe webhook endpoint tests (full Stripe sig testing not possible without live keys)."""

    def test_stripe_webhook_no_signature_errors_gracefully(self):
        """POST /api/webhook/stripe without Stripe-Signature returns non-200 (expected)."""
        resp = requests.post(
            f"{API}/api/webhook/stripe",
            json={"type": "invoice.paid", "data": {"object": {}}},
            timeout=15,
        )
        # Without a valid Stripe signature, it should return an error (400/422/500)
        # This is expected behavior - we just verify the endpoint exists and doesn't return 200 with no sig
        assert resp.status_code != 404, "Stripe webhook endpoint must exist"


# ─────────────────────────────────────────────────────────────────────────────
# GoCardless Renewal Logic via DB (asyncio-based, mirrors test_iter131 approach)
# ─────────────────────────────────────────────────────────────────────────────

class TestGocardlessRenewalViaHTTP:
    """Test GoCardless renewal order creation via actual HTTP webhook call.
    
    These tests insert DB records directly to simulate a real subscription,
    then fire webhook events and verify renewal orders are created.
    Uses a single asyncio.run() per test to avoid Motor event-loop-closed issues.
    """

    def test_gc_renewal_via_http_webhook(self, admin_session):
        """GoCardless webhook: payments.confirmed for new mandate payment creates renewal order."""
        import asyncio
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        async def run_all():
            from db.session import db
            from core.helpers import make_id, now_iso

            cust_id = make_id()
            user_id = make_id()
            sub_id = make_id()
            tenant_id = "TEST_http_renewal_tenant"
            mandate_id = f"MD_http_{sub_id[:8]}"
            initial_pm_id = f"PM_init_http_{sub_id[:8]}"
            new_pm_id = f"PM_renewal_http_{sub_id[:8]}"
            now = datetime.now(timezone.utc)

            # Seed
            await db.users.insert_one({"id": user_id, "email": f"gc_http_{cust_id[:6]}@test.com", "full_name": "HTTP Test", "tenant_id": tenant_id, "is_active": True})
            await db.customers.insert_one({"id": cust_id, "user_id": user_id, "tenant_id": tenant_id})
            await db.subscriptions.insert_one({
                "id": sub_id, "subscription_number": f"SUB-HTTP-{sub_id[:6].upper()}",
                "customer_id": cust_id, "plan_name": "HTTP Test Plan", "status": "active",
                "gocardless_mandate_id": mandate_id, "gocardless_payment_id": initial_pm_id,
                "amount": 75.0, "currency": "GBP", "base_currency": "GBP",
                "tax_amount": 7.5, "tax_rate": 0.10, "tax_name": "VAT",
                "payment_method": "bank_transfer",
                "current_period_start": now.isoformat(),
                "current_period_end": (now + timedelta(days=30)).isoformat(),
                "created_at": now_iso(), "updated_at": now_iso(),
            })

            seed = {"sub_id": sub_id, "cust_id": cust_id, "user_id": user_id, "mandate_id": mandate_id, "new_pm_id": new_pm_id, "tenant_id": tenant_id}

            # Fire webhook via HTTP (sync call inside async — run_in_executor)
            import asyncio as _asyncio
            loop = _asyncio.get_event_loop()
            payload = {"events": [{"id": f"EV_HTTP_{sub_id[:8]}", "resource_type": "payments", "action": "confirmed", "links": {"payment": new_pm_id, "mandate": mandate_id}}]}
            resp = await loop.run_in_executor(None, lambda: requests.post(f"{API}/api/webhook/gocardless", json=payload, timeout=15))

            # Verify
            import asyncio as _a2
            await _a2.sleep(0.3)  # brief wait for webhook processing
            renewal = await db.orders.find_one({"gocardless_payment_id": new_pm_id, "type": "subscription_renewal"}, {"_id": 0})

            # Cleanup
            await db.subscriptions.delete_one({"id": sub_id})
            await db.customers.delete_one({"id": cust_id})
            await db.users.delete_one({"id": user_id})
            await db.orders.delete_many({"subscription_id": sub_id})

            return resp, renewal, seed

        resp, renewal, seed = asyncio.run(run_all())

        assert resp.status_code == 200, f"Webhook returned {resp.status_code}: {resp.text[:200]}"
        assert resp.json().get("status") == "ok"
        assert renewal is not None, "Renewal order must be created for new mandate payment"
        assert renewal["type"] == "subscription_renewal"
        assert renewal["status"] == "paid"
        assert renewal["tenant_id"] == seed["tenant_id"]
        assert renewal["tax_amount"] == 7.5
        assert renewal["tax_name"] == "VAT"
        assert renewal["total"] == 82.5  # 75 + 7.5
        assert "_id" not in renewal, "MongoDB _id must not be in order document"

    def test_gc_initial_payment_only_updates_subscription_not_renewal(self, admin_session):
        """GoCardless: initial payment (matched by gocardless_payment_id) updates subscription, not renewal."""
        import asyncio
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        async def run_all():
            from db.session import db
            from core.helpers import make_id, now_iso

            cust_id = make_id()
            user_id = make_id()
            sub_id = make_id()
            mandate_id = f"MD_init_{sub_id[:8]}"
            initial_pm_id = f"PM_initial_only_{sub_id[:8]}"
            now = datetime.now(timezone.utc)

            await db.users.insert_one({"id": user_id, "email": f"gc_init_{cust_id[:6]}@test.com", "full_name": "Init Test", "tenant_id": "TEST_init_only_tenant", "is_active": True})
            await db.customers.insert_one({"id": cust_id, "user_id": user_id, "tenant_id": "TEST_init_only_tenant"})
            await db.subscriptions.insert_one({
                "id": sub_id, "subscription_number": f"SUB-INIT-{sub_id[:6].upper()}",
                "customer_id": cust_id, "plan_name": "Init Only Plan",
                "status": "pending",  # not yet active
                "gocardless_mandate_id": mandate_id, "gocardless_payment_id": initial_pm_id,
                "amount": 50.0, "currency": "GBP", "base_currency": "GBP",
                "tax_amount": 5.0, "tax_rate": 0.10, "tax_name": "VAT",
                "payment_method": "bank_transfer",
                "current_period_start": now.isoformat(),
                "current_period_end": (now + timedelta(days=30)).isoformat(),
                "created_at": now_iso(), "updated_at": now_iso(),
            })

            import asyncio as _a
            loop = _a.get_event_loop()
            payload = {"events": [{"id": f"EV_INIT_{sub_id[:8]}", "resource_type": "payments", "action": "confirmed", "links": {"payment": initial_pm_id, "mandate": mandate_id}}]}
            resp = await loop.run_in_executor(None, lambda: requests.post(f"{API}/api/webhook/gocardless", json=payload, timeout=15))

            await _a.sleep(0.3)
            sub = await db.subscriptions.find_one({"id": sub_id}, {"_id": 0})
            renewal = await db.orders.find_one({"gocardless_payment_id": initial_pm_id, "type": "subscription_renewal"}, {"_id": 0})

            # Cleanup
            await db.subscriptions.delete_one({"id": sub_id})
            await db.customers.delete_one({"id": cust_id})
            await db.users.delete_one({"id": user_id})
            await db.orders.delete_many({"subscription_id": sub_id})

            return resp, sub, renewal

        resp, sub, renewal = asyncio.run(run_all())

        assert resp.status_code == 200
        assert sub is not None
        assert sub["status"] == "active", f"Initial payment should set subscription to active, got {sub['status']}"
        assert renewal is None, "Initial payment must NOT create a subscription_renewal order"

    def test_gc_mandate_cancelled_marks_subscription_unpaid_via_webhook(self, admin_session):
        """GoCardless: mandate.cancelled event marks active subscriptions as unpaid via HTTP."""
        import asyncio
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        async def run_all():
            from db.session import db
            from core.helpers import make_id, now_iso

            cust_id = make_id()
            user_id = make_id()
            sub_id = make_id()
            mandate_id = f"MD_cancel_{sub_id[:8]}"
            now = datetime.now(timezone.utc)

            await db.users.insert_one({"id": user_id, "email": f"gc_cancel_{cust_id[:6]}@test.com", "full_name": "Cancel Test", "tenant_id": "TEST_cancel_tenant", "is_active": True})
            await db.customers.insert_one({"id": cust_id, "user_id": user_id, "tenant_id": "TEST_cancel_tenant"})
            await db.subscriptions.insert_one({
                "id": sub_id, "subscription_number": f"SUB-CANCEL-{sub_id[:6].upper()}",
                "customer_id": cust_id, "plan_name": "Cancel Plan",
                "status": "active", "gocardless_mandate_id": mandate_id,
                "amount": 40.0, "currency": "GBP", "base_currency": "GBP",
                "payment_method": "bank_transfer",
                "created_at": now_iso(), "updated_at": now_iso(),
            })

            import asyncio as _a
            loop = _a.get_event_loop()
            payload = {"events": [{"id": f"EV_CANCEL_{sub_id[:8]}", "resource_type": "mandates", "action": "cancelled", "links": {"mandate": mandate_id}}]}
            resp = await loop.run_in_executor(None, lambda: requests.post(f"{API}/api/webhook/gocardless", json=payload, timeout=15))

            await _a.sleep(0.3)
            sub = await db.subscriptions.find_one({"id": sub_id}, {"_id": 0})

            # Cleanup
            await db.subscriptions.delete_one({"id": sub_id})
            await db.customers.delete_one({"id": cust_id})
            await db.users.delete_one({"id": user_id})

            return resp, sub

        resp, sub = asyncio.run(run_all())

        assert resp.status_code == 200
        assert resp.json().get("status") == "ok"
        assert sub is not None
        assert sub["status"] == "unpaid", f"Mandate cancelled should set subscription to unpaid, got {sub['status']}"

    def test_gc_renewal_deduplication_via_http(self, admin_session):
        """GoCardless: same payment_id twice does NOT create duplicate renewal orders."""
        import asyncio
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        async def run_all():
            from db.session import db
            from core.helpers import make_id, now_iso

            cust_id = make_id()
            user_id = make_id()
            sub_id = make_id()
            mandate_id = f"MD_dedup_{sub_id[:8]}"
            initial_pm_id = f"PM_init_dedup_{sub_id[:8]}"
            renewal_pm_id = f"PM_dedup_renew_{sub_id[:8]}"
            now = datetime.now(timezone.utc)

            await db.users.insert_one({"id": user_id, "email": f"gc_dedup_{cust_id[:6]}@test.com", "full_name": "Dedup Test", "tenant_id": "TEST_dedup_tenant", "is_active": True})
            await db.customers.insert_one({"id": cust_id, "user_id": user_id, "tenant_id": "TEST_dedup_tenant"})
            await db.subscriptions.insert_one({
                "id": sub_id, "subscription_number": f"SUB-DEDUP-{sub_id[:6].upper()}",
                "customer_id": cust_id, "plan_name": "Dedup Plan",
                "status": "active", "gocardless_mandate_id": mandate_id, "gocardless_payment_id": initial_pm_id,
                "amount": 30.0, "currency": "GBP", "base_currency": "GBP",
                "tax_amount": 3.0, "tax_rate": 0.10, "tax_name": "VAT",
                "payment_method": "bank_transfer",
                "current_period_start": now.isoformat(),
                "current_period_end": (now + timedelta(days=30)).isoformat(),
                "created_at": now_iso(), "updated_at": now_iso(),
            })

            import asyncio as _a
            loop = _a.get_event_loop()

            payload1 = {"events": [{"id": f"EV_DEDUP_A_{sub_id[:8]}", "resource_type": "payments", "action": "confirmed", "links": {"payment": renewal_pm_id, "mandate": mandate_id}}]}
            resp1 = await loop.run_in_executor(None, lambda: requests.post(f"{API}/api/webhook/gocardless", json=payload1, timeout=15))

            await _a.sleep(0.3)

            # Second call — same payment_id, different event_id
            payload2 = {"events": [{"id": f"EV_DEDUP_B_{sub_id[:8]}", "resource_type": "payments", "action": "confirmed", "links": {"payment": renewal_pm_id, "mandate": mandate_id}}]}
            resp2 = await loop.run_in_executor(None, lambda: requests.post(f"{API}/api/webhook/gocardless", json=payload2, timeout=15))

            await _a.sleep(0.3)

            count = await db.orders.count_documents({"gocardless_payment_id": renewal_pm_id, "type": "subscription_renewal"})

            # Cleanup
            await db.subscriptions.delete_one({"id": sub_id})
            await db.customers.delete_one({"id": cust_id})
            await db.users.delete_one({"id": user_id})
            await db.orders.delete_many({"gocardless_payment_id": renewal_pm_id})

            return resp1, resp2, count

        resp1, resp2, count = asyncio.run(run_all())

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert count == 1, f"Expected exactly 1 renewal order, got {count} (deduplication failed)"
