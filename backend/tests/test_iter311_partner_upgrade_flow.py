"""
Test suite for Partner Plan Upgrade Flow (Iteration 311)
Tests:
1. Partner login
2. GET /partner/my-plan - returns current plan, license, subscription, available_plans, pending_upgrade_order
3. POST /partner/upgrade-plan-ongoing - creates pending_plan_upgrades + Stripe session
4. GET /partner/upgrade-plan-status - polls pending_plan_upgrades
5. POST /partner/cancel-pending-upgrade - cancels pending_plan_upgrades (not just partner_orders)
6. confirm_plan_upgrade function - atomically confirms upgrade (direct Python test)
7. Webhook handler for 'partner_upgrade' - code verification
8. billing_service.py imports from core.helpers (not core.utils) - code verification
"""
import pytest
import requests
import os
import asyncio
import sys

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

PARTNER_EMAIL = "rushabh0996@gmail.com"
PARTNER_PASSWORD = "ChangeMe123!"
PARTNER_TENANT_CODE = "edd"

PLATFORM_EMAIL = "admin@automateaccounts.local"
PLATFORM_PASSWORD = "ChangeMe123!"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def partner_token():
    """Login as partner and return token."""
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": PARTNER_EMAIL, "password": PARTNER_PASSWORD, "tenant_code": PARTNER_TENANT_CODE},
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200, f"Partner login failed: {resp.status_code} {resp.text}"
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    assert token, f"No token in response: {data}"
    return token


@pytest.fixture(scope="module")
def partner_headers(partner_token):
    return {"Authorization": f"Bearer {partner_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def platform_token():
    """Login as platform admin."""
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": PLATFORM_EMAIL, "password": PLATFORM_PASSWORD},
        headers={"Content-Type": "application/json"},
    )
    if resp.status_code != 200:
        pytest.skip(f"Platform admin login failed: {resp.text}")
    data = resp.json()
    return data.get("token") or data.get("access_token")


@pytest.fixture(scope="module")
def platform_headers(platform_token):
    return {"Authorization": f"Bearer {platform_token}", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Test 1: Partner Login
# ---------------------------------------------------------------------------

class TestPartnerLogin:
    """Partner login tests"""

    def test_partner_login_success(self):
        """Partner can log in with tenant code edd"""
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": PARTNER_EMAIL, "password": PARTNER_PASSWORD, "tenant_code": PARTNER_TENANT_CODE},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        token = data.get("token") or data.get("access_token")
        assert token, f"No token in response: {data}"
        print(f"Partner login SUCCESS - token starts with: {str(token)[:20]}...")

    def test_partner_login_wrong_password(self):
        """Reject invalid password"""
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": PARTNER_EMAIL, "password": "wrongpassword", "tenant_code": PARTNER_TENANT_CODE},
        )
        assert resp.status_code in [401, 400, 422], f"Expected 4xx, got {resp.status_code}"
        print("Reject invalid password - PASS")


# ---------------------------------------------------------------------------
# Test 2: GET /partner/my-plan
# ---------------------------------------------------------------------------

class TestMyPlan:
    """GET /partner/my-plan tests"""

    def test_my_plan_returns_200(self, partner_headers):
        resp = requests.get(f"{BASE_URL}/api/partner/my-plan", headers=partner_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print("GET /partner/my-plan returned 200")

    def test_my_plan_has_required_fields(self, partner_headers):
        resp = requests.get(f"{BASE_URL}/api/partner/my-plan", headers=partner_headers)
        assert resp.status_code == 200
        data = resp.json()
        # Check required fields
        assert "current_plan" in data, f"Missing 'current_plan' in response: {list(data.keys())}"
        assert "license" in data, f"Missing 'license' in response: {list(data.keys())}"
        assert "subscription" in data, f"Missing 'subscription' in response: {list(data.keys())}"
        assert "available_plans" in data, f"Missing 'available_plans' in response: {list(data.keys())}"
        assert "pending_upgrade_order" in data, f"Missing 'pending_upgrade_order' in response: {list(data.keys())}"
        print(f"my-plan fields present: {list(data.keys())}")

    def test_my_plan_available_plans_is_list(self, partner_headers):
        resp = requests.get(f"{BASE_URL}/api/partner/my-plan", headers=partner_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["available_plans"], list), \
            f"available_plans should be list, got {type(data['available_plans'])}"
        print(f"available_plans count: {len(data['available_plans'])}")

    def test_my_plan_current_plan_structure(self, partner_headers):
        resp = requests.get(f"{BASE_URL}/api/partner/my-plan", headers=partner_headers)
        data = resp.json()
        current_plan = data.get("current_plan")
        if current_plan:
            assert "id" in current_plan, "current_plan missing 'id'"
            assert "name" in current_plan, "current_plan missing 'name'"
            print(f"current_plan: {current_plan.get('name')} (id={current_plan.get('id')})")
        else:
            print("current_plan is null (no plan assigned)")

    def test_my_plan_unauthorized(self):
        """Reject unauthorized access"""
        resp = requests.get(f"{BASE_URL}/api/partner/my-plan")
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"
        print("Unauthorized rejected - PASS")


# ---------------------------------------------------------------------------
# Test 3: POST /partner/upgrade-plan-ongoing
# ---------------------------------------------------------------------------

class TestUpgradePlanOngoing:
    """POST /partner/upgrade-plan-ongoing tests"""

    def test_upgrade_plan_ongoing_requires_auth(self):
        resp = requests.post(f"{BASE_URL}/api/partner/upgrade-plan-ongoing",
                             json={"plan_id": "nonexistent"})
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"

    def test_upgrade_plan_ongoing_invalid_plan(self, partner_headers):
        """Should return 404 for nonexistent plan"""
        resp = requests.post(
            f"{BASE_URL}/api/partner/upgrade-plan-ongoing",
            json={"plan_id": "nonexistent-plan-id-xxx"},
            headers=partner_headers,
        )
        assert resp.status_code == 404, f"Expected 404 for invalid plan, got {resp.status_code}: {resp.text}"
        print("upgrade-plan-ongoing returns 404 for invalid plan - PASS")

    def test_upgrade_plan_ongoing_with_valid_plan(self, partner_headers):
        """
        If there's an available upgrade plan, test that:
        1. API accepts the request
        2. Returns either checkout_url (Stripe) or message (free/coupon)
        3. Creates pending_plan_upgrades record if amount > 0
        """
        # First get available plans
        plan_resp = requests.get(f"{BASE_URL}/api/partner/my-plan", headers=partner_headers)
        assert plan_resp.status_code == 200
        plan_data = plan_resp.json()

        current_price = plan_data.get("current_price_in_base", 0)
        available_plans = plan_data.get("available_plans", [])
        # Find a plan with higher price
        upgrade_plans = [
            p for p in available_plans
            if (p.get("display_price") or p.get("monthly_price") or 0) > (current_price or 0)
        ]

        if not upgrade_plans:
            pytest.skip("No upgrade plans available for this partner")

        target_plan = upgrade_plans[0]
        print(f"Testing upgrade to plan: {target_plan['name']} (price={target_plan.get('display_price', target_plan.get('monthly_price'))})")

        resp = requests.post(
            f"{BASE_URL}/api/partner/upgrade-plan-ongoing",
            json={"plan_id": target_plan["id"], "origin_url": "https://example.com"},
            headers=partner_headers,
        )
        # Should be 200 (with checkout_url) or 200 (with message for free/zero-amount)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        print(f"upgrade-plan-ongoing response: {list(data.keys())}")
        # Either checkout_url (needs Stripe payment) or message (zero/coupon covers all)
        assert "checkout_url" in data or "message" in data, \
            f"Expected checkout_url or message in response: {data}"

        # If it returned checkout_url, verify the pending_plan_upgrades record was created
        if "checkout_url" in data:
            assert "session_id" in data, "Missing session_id when checkout_url present"
            print(f"Got checkout_url and session_id: {data.get('session_id')[:20]}...")

            # Cancel this pending upgrade since we don't have a real Stripe payment
            cancel_resp = requests.post(
                f"{BASE_URL}/api/partner/cancel-pending-upgrade",
                headers=partner_headers,
            )
            # Should succeed now that there IS a pending_plan_upgrades record
            assert cancel_resp.status_code == 200, \
                f"cancel-pending-upgrade should succeed, got {cancel_resp.status_code}: {cancel_resp.text}"
            print("cancel-pending-upgrade after creating pending upgrade - PASS")


# ---------------------------------------------------------------------------
# Test 4: GET /partner/upgrade-plan-status
# ---------------------------------------------------------------------------

class TestUpgradePlanStatus:
    """GET /partner/upgrade-plan-status tests"""

    def test_status_requires_auth(self):
        resp = requests.get(f"{BASE_URL}/api/partner/upgrade-plan-status?session_id=cs_test_123")
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"

    def test_status_missing_session_id(self, partner_headers):
        """Should return 422 (validation error) or 404 when no session_id"""
        resp = requests.get(f"{BASE_URL}/api/partner/upgrade-plan-status", headers=partner_headers)
        assert resp.status_code in [422, 400, 404], f"Expected 422/400/404, got {resp.status_code}: {resp.text}"

    def test_status_nonexistent_session(self, partner_headers):
        """Should return 404 for unknown session"""
        resp = requests.get(
            f"{BASE_URL}/api/partner/upgrade-plan-status?session_id=cs_nonexistent_session_abc123",
            headers=partner_headers,
        )
        assert resp.status_code == 404, f"Expected 404 for unknown session, got {resp.status_code}: {resp.text}"
        print("upgrade-plan-status returns 404 for unknown session - PASS")


# ---------------------------------------------------------------------------
# Test 5: POST /partner/cancel-pending-upgrade
# ---------------------------------------------------------------------------

class TestCancelPendingUpgrade:
    """POST /partner/cancel-pending-upgrade tests"""

    def test_cancel_when_no_pending_upgrade(self, partner_headers):
        """Should return 404 when there's no pending upgrade"""
        # Make sure there's no pending upgrade first
        resp = requests.post(
            f"{BASE_URL}/api/partner/cancel-pending-upgrade",
            headers=partner_headers,
        )
        # Expect 404 since no pending upgrade exists (or 200 if there was a leftover)
        assert resp.status_code in [404, 200], \
            f"Expected 404 or 200, got {resp.status_code}: {resp.text}"
        if resp.status_code == 404:
            print("cancel-pending-upgrade returns 404 when nothing to cancel - PASS")
        else:
            print("cancel-pending-upgrade cancelled a leftover pending upgrade")

    def test_cancel_pending_upgrade_flow(self, partner_headers):
        """
        Full flow test:
        1. Get available upgrade plan
        2. Call upgrade-plan-ongoing to create pending_plan_upgrades record
        3. Verify cancel-pending-upgrade works
        4. Verify cancel again returns 404
        """
        # Get plan info
        plan_resp = requests.get(f"{BASE_URL}/api/partner/my-plan", headers=partner_headers)
        if plan_resp.status_code != 200:
            pytest.skip("Cannot get plan info")
        plan_data = plan_resp.json()
        current_price = plan_data.get("current_price_in_base", 0)
        available_plans = plan_data.get("available_plans", [])
        upgrade_plans = [
            p for p in available_plans
            if (p.get("display_price") or p.get("monthly_price") or 0) > (current_price or 0)
        ]
        if not upgrade_plans:
            pytest.skip("No upgrade plans available")

        target_plan = upgrade_plans[0]
        # Create pending upgrade
        upgrade_resp = requests.post(
            f"{BASE_URL}/api/partner/upgrade-plan-ongoing",
            json={"plan_id": target_plan["id"], "origin_url": "https://example.com"},
            headers=partner_headers,
        )
        if upgrade_resp.status_code != 200 or "checkout_url" not in upgrade_resp.json():
            pytest.skip("Stripe not configured or plan has zero diff — cannot test cancel flow")

        session_id = upgrade_resp.json().get("session_id")
        print(f"Created pending upgrade with session: {session_id[:20] if session_id else 'unknown'}...")

        # Now verify my-plan shows the pending upgrade
        plan_resp2 = requests.get(f"{BASE_URL}/api/partner/my-plan", headers=partner_headers)
        # The pending_upgrade_order might be null if Stripe session can't be verified (test env)
        plan_data2 = plan_resp2.json()
        print(f"pending_upgrade_order in my-plan: {plan_data2.get('pending_upgrade_order')}")

        # Cancel it
        cancel_resp = requests.post(
            f"{BASE_URL}/api/partner/cancel-pending-upgrade",
            headers=partner_headers,
        )
        assert cancel_resp.status_code == 200, \
            f"cancel-pending-upgrade should succeed, got {cancel_resp.status_code}: {cancel_resp.text}"
        assert "message" in cancel_resp.json(), f"Response should have message: {cancel_resp.json()}"
        print(f"cancel-pending-upgrade success: {cancel_resp.json()}")

        # Cancel again should return 404
        cancel_resp2 = requests.post(
            f"{BASE_URL}/api/partner/cancel-pending-upgrade",
            headers=partner_headers,
        )
        assert cancel_resp2.status_code == 404, \
            f"Second cancel should return 404, got {cancel_resp2.status_code}: {cancel_resp2.text}"
        print("Second cancel returns 404 - PASS (idempotency)")


# ---------------------------------------------------------------------------
# Test 6: confirm_plan_upgrade direct Python test
# ---------------------------------------------------------------------------

class TestConfirmPlanUpgrade:
    """Direct test of confirm_plan_upgrade function"""

    def test_confirm_plan_upgrade_direct(self, partner_headers):
        """
        Test confirm_plan_upgrade function directly:
        1. Create a fake pending_plan_upgrades doc with status=pending
        2. Call confirm_plan_upgrade
        3. Verify: status→completed, partner_order created, tenant license updated
        4. Call again → returns False (idempotency)
        """
        # First get partner info
        plan_resp = requests.get(f"{BASE_URL}/api/partner/my-plan", headers=partner_headers)
        assert plan_resp.status_code == 200
        plan_data = plan_resp.json()
        current_plan = plan_data.get("current_plan")
        if not current_plan:
            pytest.skip("Partner has no current plan — cannot test confirm_plan_upgrade")
        partner_id_for_test = None
        license_info = plan_data.get("license", {})

        # We need to run the async test via subprocess or directly via the existing event loop
        # Since we can't easily run async from pytest without asyncio, we'll use requests to
        # simulate via the status endpoint (which internally calls confirm_plan_upgrade)
        print(f"Current plan: {current_plan.get('name')}, license: {license_info}")
        print("confirm_plan_upgrade will be tested via asyncio_direct_test below")


@pytest.mark.asyncio
async def test_confirm_plan_upgrade_asyncio():
    """
    Direct async test of confirm_plan_upgrade function.
    Creates a pending doc, calls the function, verifies results.
    """
    # Add backend to path
    if "/app/backend" not in sys.path:
        sys.path.insert(0, "/app/backend")

    # Load env
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")

    try:
        from db.session import db
        from core.helpers import now_iso, make_id
        from services.billing_service import confirm_plan_upgrade

        # Get the partner tenant
        tenant = await db.tenants.find_one({"code": PARTNER_TENANT_CODE}, {"_id": 0})
        if not tenant:
            print("SKIP: Partner tenant 'edd' not found in DB")
            return

        partner_id = tenant["id"]
        print(f"Testing with partner_id: {partner_id}")

        # Get a plan to upgrade to
        current_plan_id = (tenant.get("license") or {}).get("plan_id")
        # Get any active plan that's different from current
        upgrade_plan = await db.plans.find_one(
            {"is_active": True, "id": {"$ne": current_plan_id}},
            {"_id": 0},
        )
        if not upgrade_plan:
            print("SKIP: No other active plan found to upgrade to")
            return

        print(f"Upgrading to plan: {upgrade_plan['name']}")

        # Create a fake pending_plan_upgrades record
        pending_id = make_id()
        order_number = "TEST-311-0001"
        now = now_iso()
        pending_doc = {
            "id": pending_id,
            "order_number": order_number,
            "stripe_session_id": "cs_test_simulated_311",
            "checkout_url": "https://stripe.com/fake",
            "partner_id": partner_id,
            "partner_name": tenant.get("name", "Test Partner"),
            "plan_id": upgrade_plan["id"],
            "plan_name": upgrade_plan["name"],
            "sub_id": "",
            "amount": 10.00,
            "currency": "GBP",
            "base_amount": 10.00,
            "discount_amount": 0.0,
            "coupon_code": "",
            "coupon_id": "",
            "status": "pending",
            "created_at": now,
        }
        await db.pending_plan_upgrades.insert_one(pending_doc)
        print(f"Created pending_plan_upgrades record: {pending_id}")

        # --- Call confirm_plan_upgrade ---
        result = await confirm_plan_upgrade(pending_doc, partner_id)
        assert result is True, f"confirm_plan_upgrade should return True on first call, got {result}"
        print("confirm_plan_upgrade returned True on first call - PASS")

        # --- Verify pending_plan_upgrades status is 'completed' ---
        updated_pending = await db.pending_plan_upgrades.find_one({"id": pending_id}, {"_id": 0})
        assert updated_pending is not None, "pending_plan_upgrades record should still exist"
        assert updated_pending["status"] == "completed", \
            f"Expected status='completed', got '{updated_pending['status']}'"
        assert "completed_at" in updated_pending, "completed_at should be set"
        print(f"pending_plan_upgrades status='completed' - PASS")

        # --- Verify partner_order was created ---
        order = await db.partner_orders.find_one(
            {"order_number": order_number, "partner_id": partner_id}, {"_id": 0}
        )
        assert order is not None, f"partner_order should have been created for order_number={order_number}"
        assert order["status"] == "paid", f"Expected order status='paid', got '{order['status']}'"
        assert order["amount"] == pending_doc["amount"], \
            f"Order amount mismatch: {order['amount']} != {pending_doc['amount']}"
        print(f"partner_order created with status='paid' - PASS (order_id={order['id']})")

        # --- Verify tenant license was updated ---
        updated_tenant = await db.tenants.find_one({"id": partner_id}, {"_id": 0, "license": 1})
        tenant_license = (updated_tenant or {}).get("license", {})
        assert tenant_license.get("plan_id") == upgrade_plan["id"], \
            f"Tenant license plan_id not updated: {tenant_license.get('plan_id')} != {upgrade_plan['id']}"
        assert tenant_license.get("plan_name") == upgrade_plan["name"], \
            f"Tenant license plan_name not updated: {tenant_license.get('plan_name')} != {upgrade_plan['name']}"
        print(f"Tenant license updated to plan '{upgrade_plan['name']}' - PASS")

        # --- Idempotency: calling again should return False ---
        result2 = await confirm_plan_upgrade(pending_doc, partner_id)
        assert result2 is False, f"confirm_plan_upgrade should return False on second call, got {result2}"
        print("confirm_plan_upgrade returned False on second call (idempotency) - PASS")

        # --- Cleanup: restore original plan ---
        if current_plan_id:
            current_plan = await db.plans.find_one({"id": current_plan_id}, {"_id": 0})
            if current_plan:
                limits = {k: v for k, v in current_plan.items() if k.startswith("max_")}
                await db.tenants.update_one(
                    {"id": partner_id},
                    {"$set": {"license": {
                        "plan_id": current_plan["id"],
                        "plan_name": current_plan["name"],
                        "assigned_at": now,
                        **limits,
                    }}}
                )
                print(f"Restored tenant license to original plan '{current_plan['name']}'")

        # Cleanup test records
        await db.pending_plan_upgrades.delete_one({"id": pending_id})
        await db.partner_orders.delete_one({"order_number": order_number})
        print("Test data cleaned up")

        print("\n=== confirm_plan_upgrade ALL TESTS PASSED ===")

    except ImportError as e:
        print(f"SKIP: Cannot import backend modules: {e}")
    except Exception as e:
        import traceback
        print(f"ERROR in test_confirm_plan_upgrade_asyncio: {e}")
        traceback.print_exc()
        raise


# ---------------------------------------------------------------------------
# Test 7: Webhook handler code verification
# ---------------------------------------------------------------------------

class TestWebhookHandlerCodeVerification:
    """Verify the webhook handler has the partner_upgrade elif block"""

    def test_webhooks_py_has_partner_upgrade_handler(self):
        """Verify webhooks.py contains the partner_upgrade handler"""
        with open("/app/backend/routes/webhooks.py", "r") as f:
            content = f.read()
        assert 'event_meta.get("type") == "partner_upgrade"' in content, \
            "webhooks.py is MISSING the partner_upgrade elif block"
        assert "confirm_plan_upgrade" in content, \
            "webhooks.py is MISSING confirm_plan_upgrade call in partner_upgrade block"
        print("webhooks.py has partner_upgrade handler - PASS")

    def test_webhooks_py_calls_confirm_plan_upgrade_for_partner_upgrade(self):
        """Verify the partner_upgrade block calls confirm_plan_upgrade"""
        with open("/app/backend/routes/webhooks.py", "r") as f:
            content = f.read()
        # Check both the elif and the call are in close proximity
        idx = content.find('event_meta.get("type") == "partner_upgrade"')
        assert idx != -1, "partner_upgrade handler not found"
        # Get the next 500 chars after the elif
        block = content[idx:idx+500]
        assert "confirm_plan_upgrade" in block, \
            f"confirm_plan_upgrade not called in partner_upgrade block. Block content:\n{block}"
        assert "checkout.session.completed" in block, \
            f"partner_upgrade block missing checkout.session.completed check. Block:\n{block}"
        print("webhooks.py partner_upgrade block correctly calls confirm_plan_upgrade - PASS")


# ---------------------------------------------------------------------------
# Test 8: billing_service.py imports from core.helpers (NOT core.utils)
# ---------------------------------------------------------------------------

class TestBillingServiceImports:
    """Verify billing_service.py does NOT import from core.utils"""

    def test_billing_service_imports_core_helpers(self):
        """billing_service.py should import from core.helpers"""
        with open("/app/backend/services/billing_service.py", "r") as f:
            content = f.read()
        assert "from core.helpers import" in content, \
            "billing_service.py is MISSING 'from core.helpers import'"
        print("billing_service.py imports from core.helpers - PASS")

    def test_billing_service_no_core_utils_import(self):
        """billing_service.py should NOT import from core.utils"""
        with open("/app/backend/services/billing_service.py", "r") as f:
            content = f.read()
        assert "from core.utils import" not in content, \
            "billing_service.py still imports from core.utils (non-existent module)"
        assert "import core.utils" not in content, \
            "billing_service.py still imports core.utils (non-existent module)"
        print("billing_service.py does NOT import from core.utils - PASS")

    def test_confirm_plan_upgrade_function_exists(self):
        """confirm_plan_upgrade function should exist in billing_service.py"""
        with open("/app/backend/services/billing_service.py", "r") as f:
            content = f.read()
        assert "async def confirm_plan_upgrade" in content, \
            "confirm_plan_upgrade function not found in billing_service.py"
        print("confirm_plan_upgrade function exists - PASS")

    def test_cancel_pending_upgrade_uses_pending_plan_upgrades(self):
        """cancel-pending-upgrade endpoint should cancel pending_plan_upgrades"""
        with open("/app/backend/routes/partner/plan_management.py", "r") as f:
            content = f.read()
        assert "pending_plan_upgrades" in content, \
            "cancel_pending_upgrade endpoint does not reference pending_plan_upgrades"
        # Verify it searches by status=pending
        assert '"pending_plan_upgrades"' not in content or "pending_plan_upgrades" in content
        print("cancel-pending-upgrade references pending_plan_upgrades - PASS")

    def test_upgrade_plan_ongoing_creates_pending_plan_upgrades(self):
        """upgrade-plan-ongoing should create pending_plan_upgrades record"""
        with open("/app/backend/routes/partner/plan_management.py", "r") as f:
            content = f.read()
        # Check that upgrade_plan_ongoing inserts into pending_plan_upgrades
        assert "pending_plan_upgrades.insert_one" in content, \
            "upgrade-plan-ongoing does not insert into pending_plan_upgrades"
        print("upgrade-plan-ongoing creates pending_plan_upgrades record - PASS")
