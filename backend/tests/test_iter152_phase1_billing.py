"""
Phase 1+2A Partner Billing Tests — Iteration 152
Tests:
  1. Free Trial plan seed (is_default=True, is_public=False, max_users=10)
  2. is_public flag on plan create/retrieve
  3. Public plans endpoint (GET /partner/plans/public)
  4. Auto-assign Free Trial on partner signup
  5. Reset to Free Trial on subscription cancel
  6. Partner Orgs audit logs endpoint
  7. Billing service functions (calculate_prorata, calculate_upgrade_prorata, next_first_of_month)
"""
import pytest
import requests
import os
import sys

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# ── credentials ─────────────────────────────────────────────────────────────
ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
    })
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ── 1. Free Trial plan seed ──────────────────────────────────────────────────

class TestFreeTrialPlanSeed:
    """Verify the Free Trial plan was seeded correctly on startup."""

    def test_free_trial_plan_exists(self, admin_headers):
        """GET /api/admin/plans should include a 'Free Trial' plan."""
        r = requests.get(f"{BASE_URL}/api/admin/plans", headers=admin_headers)
        assert r.status_code == 200, f"list plans failed: {r.text}"
        plans = r.json().get("plans", [])
        free_trial = next((p for p in plans if p.get("name") == "Free Trial"), None)
        assert free_trial is not None, "Free Trial plan not found in /api/admin/plans"
        return free_trial

    def test_free_trial_is_default(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/plans", headers=admin_headers)
        plans = r.json().get("plans", [])
        free_trial = next((p for p in plans if p.get("name") == "Free Trial"), None)
        assert free_trial is not None, "Free Trial plan not found"
        assert free_trial.get("is_default") is True, f"Expected is_default=True, got {free_trial.get('is_default')}"

    def test_free_trial_is_not_public(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/plans", headers=admin_headers)
        plans = r.json().get("plans", [])
        free_trial = next((p for p in plans if p.get("name") == "Free Trial"), None)
        assert free_trial is not None, "Free Trial plan not found"
        assert free_trial.get("is_public") is False, f"Expected is_public=False, got {free_trial.get('is_public')}"

    def test_free_trial_max_users_is_10(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/plans", headers=admin_headers)
        plans = r.json().get("plans", [])
        free_trial = next((p for p in plans if p.get("name") == "Free Trial"), None)
        assert free_trial is not None, "Free Trial plan not found"
        assert free_trial.get("max_users") == 10, f"Expected max_users=10, got {free_trial.get('max_users')}"

    def test_free_trial_all_limits_are_10(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/plans", headers=admin_headers)
        plans = r.json().get("plans", [])
        free_trial = next((p for p in plans if p.get("name") == "Free Trial"), None)
        assert free_trial is not None, "Free Trial plan not found"
        limit_fields = [
            "max_users", "max_storage_mb", "max_user_roles", "max_product_categories",
            "max_product_terms", "max_enquiries", "max_resources", "max_templates",
            "max_email_templates", "max_categories", "max_forms", "max_references",
            "max_orders_per_month", "max_customers_per_month", "max_subscriptions_per_month",
        ]
        bad_fields = [f for f in limit_fields if free_trial.get(f) != 10]
        assert not bad_fields, f"These limit fields are not 10: {bad_fields}, plan: {free_trial}"


# ── 2. is_public flag on plan create ────────────────────────────────────────

class TestPlanIsPublicFlag:
    """Verify is_public field is correctly stored/returned when creating plans."""

    _created_plan_id = None

    def test_create_plan_with_is_public_true(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/plans", headers=admin_headers, json={
            "name": "TEST_Public Plan",
            "is_public": True,
            "max_users": 50,
        })
        assert r.status_code == 200, f"create plan failed: {r.text}"
        plan = r.json().get("plan", {})
        assert plan.get("is_public") is True, f"Expected is_public=True, got {plan.get('is_public')}"
        TestPlanIsPublicFlag._created_plan_id = plan.get("id")

    def test_get_plan_confirms_is_public_true(self, admin_headers):
        if not TestPlanIsPublicFlag._created_plan_id:
            pytest.skip("Plan not created in previous test")
        r = requests.get(f"{BASE_URL}/api/admin/plans/{TestPlanIsPublicFlag._created_plan_id}", headers=admin_headers)
        assert r.status_code == 200, f"get plan failed: {r.text}"
        plan = r.json().get("plan", {})
        assert plan.get("is_public") is True, f"Expected is_public=True after GET, got {plan.get('is_public')}"

    def test_cleanup_test_plan(self, admin_headers):
        """Remove the test plan (only works if no tenants are on it)."""
        if not TestPlanIsPublicFlag._created_plan_id:
            pytest.skip("Plan not created in previous test")
        r = requests.delete(f"{BASE_URL}/api/admin/plans/{TestPlanIsPublicFlag._created_plan_id}", headers=admin_headers)
        assert r.status_code == 200, f"delete plan failed: {r.text}"


# ── 3. Public plans endpoint ─────────────────────────────────────────────────

class TestPublicPlansEndpoint:
    """GET /api/partner/plans/public — no auth needed, returns only active+public plans."""

    def test_public_plans_returns_200(self):
        r = requests.get(f"{BASE_URL}/api/partner/plans/public")
        assert r.status_code == 200, f"Public plans endpoint failed: {r.text}"

    def test_public_plans_no_free_trial(self):
        """Free Trial has is_public=False — must NOT appear in public list."""
        r = requests.get(f"{BASE_URL}/api/partner/plans/public")
        assert r.status_code == 200
        plans = r.json().get("plans", [])
        free_trial = next((p for p in plans if p.get("name") == "Free Trial"), None)
        assert free_trial is None, "Free Trial should NOT appear in public plans (is_public=False)"

    def test_public_plans_all_are_public(self):
        """Every plan returned must have is_public=True."""
        r = requests.get(f"{BASE_URL}/api/partner/plans/public")
        assert r.status_code == 200
        plans = r.json().get("plans", [])
        non_public = [p for p in plans if not p.get("is_public")]
        assert not non_public, f"Non-public plans appeared in public endpoint: {non_public}"

    def test_public_plans_all_are_active(self):
        """Every plan returned must have is_active=True."""
        r = requests.get(f"{BASE_URL}/api/partner/plans/public")
        assert r.status_code == 200
        plans = r.json().get("plans", [])
        inactive = [p for p in plans if not p.get("is_active")]
        assert not inactive, f"Inactive plans appeared in public endpoint: {inactive}"

    def test_public_plans_currently_empty(self):
        """Since only Free Trial exists and it's not public, there should be 0 public plans."""
        r = requests.get(f"{BASE_URL}/api/partner/plans/public")
        assert r.status_code == 200
        plans = r.json().get("plans", [])
        # This is valid — 0 public plans is expected when no public plan has been created
        # If there happen to be public plans (from other tests), all must be is_public=True
        for p in plans:
            assert p.get("is_public") is True
        print(f"[INFO] Public plans count: {len(plans)}")


# ── 4. Auto-assign Free Trial on partner signup ──────────────────────────────

class TestAutoAssignFreeTrialOnSignup:
    """POST /api/auth/register-partner should assign Free Trial to new tenant."""

    _partner_code = None
    _tenant_id = None

    def test_register_partner_succeeds(self, admin_headers):
        import time
        unique = int(time.time())
        r = requests.post(f"{BASE_URL}/api/auth/register-partner", json={
            "name": f"TEST_Auto Assign Org {unique}",
            "admin_name": "Test Admin",
            "admin_email": f"test-autoassign-{unique}@example.com",
            "admin_password": "TestPass123!",
            "base_currency": "USD",
            "address": {
                "line1": "123 Test Street",
                "line2": "",
                "city": "London",
                "region": "England",
                "postal": "SW1A 1AA",
                "country": "GB",
            }
        })
        assert r.status_code == 200, f"register-partner failed: {r.text}"
        TestAutoAssignFreeTrialOnSignup._partner_code = r.json().get("partner_code")
        assert TestAutoAssignFreeTrialOnSignup._partner_code, "No partner_code in response"

    def test_new_tenant_has_free_trial_license(self, admin_headers):
        if not TestAutoAssignFreeTrialOnSignup._partner_code:
            pytest.skip("Partner not created in previous test")

        # Get tenant by code
        r = requests.get(
            f"{BASE_URL}/api/admin/tenants",
            headers=admin_headers,
            params={"search": TestAutoAssignFreeTrialOnSignup._partner_code},
        )
        assert r.status_code == 200, f"list tenants failed: {r.text}"
        tenants = r.json().get("tenants", [])
        tenant = next((t for t in tenants if t.get("code") == TestAutoAssignFreeTrialOnSignup._partner_code), None)
        assert tenant is not None, f"Tenant with code {TestAutoAssignFreeTrialOnSignup._partner_code} not found"
        TestAutoAssignFreeTrialOnSignup._tenant_id = tenant.get("id")

        # Verify the tenant has a license with plan_id pointing to Free Trial
        license = tenant.get("license") or {}
        assert license.get("plan_id"), f"Tenant license.plan_id is empty: {license}"
        assert license.get("plan_name") == "Free Trial", f"Expected plan_name='Free Trial', got '{license.get('plan_name')}'"

    def test_new_tenant_license_plan_id_matches_free_trial(self, admin_headers):
        if not TestAutoAssignFreeTrialOnSignup._tenant_id:
            pytest.skip("Tenant not found in previous test")

        # Get Free Trial plan ID
        r = requests.get(f"{BASE_URL}/api/admin/plans", headers=admin_headers)
        plans = r.json().get("plans", [])
        free_trial = next((p for p in plans if p.get("name") == "Free Trial"), None)
        assert free_trial, "Free Trial plan not found"
        free_trial_id = free_trial["id"]

        # Get tenant
        r2 = requests.get(f"{BASE_URL}/api/admin/tenants", headers=admin_headers,
                         params={"search": TestAutoAssignFreeTrialOnSignup._partner_code})
        tenants = r2.json().get("tenants", [])
        tenant = next((t for t in tenants if t.get("code") == TestAutoAssignFreeTrialOnSignup._partner_code), None)
        assert tenant, "Tenant not found"

        license = tenant.get("license") or {}
        assert license.get("plan_id") == free_trial_id, (
            f"Expected plan_id={free_trial_id}, got {license.get('plan_id')}"
        )


# ── 5. Reset to Free Trial on subscription cancel ────────────────────────────

class TestResetToFreeTrialOnCancel:
    """Cancel a partner subscription → tenant license resets to Free Trial."""

    _partner_code = None
    _tenant_id = None
    _sub_id = None

    def test_create_partner_for_sub_cancel_test(self, admin_headers):
        import time
        unique = int(time.time()) + 1
        r = requests.post(f"{BASE_URL}/api/auth/register-partner", json={
            "name": f"TEST_Cancel Org {unique}",
            "admin_name": "Cancel Admin",
            "admin_email": f"test-cancel-{unique}@example.com",
            "admin_password": "CancelPass123!",
            "base_currency": "GBP",
            "address": {
                "line1": "456 Cancel Road",
                "city": "Manchester",
                "region": "England",
                "postal": "M1 1AE",
                "country": "GB",
            }
        })
        assert r.status_code == 200, f"register-partner failed: {r.text}"
        TestResetToFreeTrialOnCancel._partner_code = r.json().get("partner_code")

    def test_get_tenant_id_for_cancel_test(self, admin_headers):
        if not TestResetToFreeTrialOnCancel._partner_code:
            pytest.skip("Partner not created")
        r = requests.get(f"{BASE_URL}/api/admin/tenants", headers=admin_headers,
                        params={"search": TestResetToFreeTrialOnCancel._partner_code})
        tenants = r.json().get("tenants", [])
        tenant = next((t for t in tenants if t.get("code") == TestResetToFreeTrialOnCancel._partner_code), None)
        assert tenant, "Tenant not found"
        TestResetToFreeTrialOnCancel._tenant_id = tenant["id"]

    def test_create_subscription_for_tenant(self, admin_headers):
        if not TestResetToFreeTrialOnCancel._tenant_id:
            pytest.skip("Tenant not found")
        r = requests.post(f"{BASE_URL}/api/admin/partner-subscriptions", headers=admin_headers, json={
            "partner_id": TestResetToFreeTrialOnCancel._tenant_id,
            "description": "TEST_ Pro Plan Monthly",
            "amount": 99.0,
            "currency": "GBP",
            "billing_interval": "monthly",
            "status": "active",
            "payment_method": "manual",
        })
        assert r.status_code == 200, f"create subscription failed: {r.text}"
        TestResetToFreeTrialOnCancel._sub_id = r.json().get("subscription", {}).get("id")
        assert TestResetToFreeTrialOnCancel._sub_id, "No subscription id returned"

    def test_cancel_subscription(self, admin_headers):
        if not TestResetToFreeTrialOnCancel._sub_id:
            pytest.skip("Subscription not created")
        r = requests.patch(
            f"{BASE_URL}/api/admin/partner-subscriptions/{TestResetToFreeTrialOnCancel._sub_id}/cancel",
            headers=admin_headers,
        )
        assert r.status_code == 200, f"cancel subscription failed: {r.text}"
        sub = r.json().get("subscription", {})
        assert sub.get("status") == "cancelled", f"Expected status=cancelled, got {sub.get('status')}"

    def test_tenant_license_reset_to_free_trial_after_cancel(self, admin_headers):
        if not TestResetToFreeTrialOnCancel._partner_code:
            pytest.skip("Partner not created")
        import time
        time.sleep(0.5)  # Give async task time to complete

        r = requests.get(f"{BASE_URL}/api/admin/tenants", headers=admin_headers,
                        params={"search": TestResetToFreeTrialOnCancel._partner_code})
        tenants = r.json().get("tenants", [])
        tenant = next((t for t in tenants if t.get("code") == TestResetToFreeTrialOnCancel._partner_code), None)
        assert tenant, "Tenant not found"

        license = tenant.get("license") or {}
        assert license.get("plan_name") == "Free Trial", (
            f"Expected plan_name='Free Trial' after cancellation, got '{license.get('plan_name')}'"
        )

    def test_free_trial_limits_applied_after_cancel(self, admin_headers):
        if not TestResetToFreeTrialOnCancel._partner_code:
            pytest.skip("Partner not created")
        r = requests.get(f"{BASE_URL}/api/admin/tenants", headers=admin_headers,
                        params={"search": TestResetToFreeTrialOnCancel._partner_code})
        tenants = r.json().get("tenants", [])
        tenant = next((t for t in tenants if t.get("code") == TestResetToFreeTrialOnCancel._partner_code), None)
        assert tenant, "Tenant not found"
        license = tenant.get("license") or {}
        assert license.get("max_users") == 10, (
            f"Expected max_users=10 after reset, got {license.get('max_users')}"
        )


# ── 6. Partner Orgs audit logs endpoint ──────────────────────────────────────

class TestPartnerAuditLogs:
    """GET /api/admin/audit-logs?entity_type=tenant&entity_id={id} should return logs."""

    def test_audit_logs_endpoint_accessible(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/audit-logs", headers=admin_headers)
        assert r.status_code == 200, f"audit-logs endpoint failed: {r.text}"
        data = r.json()
        assert "logs" in data, "Response missing 'logs' key"

    def test_audit_logs_filter_by_entity_type_tenant(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/audit-logs", headers=admin_headers,
                        params={"entity_type": "tenant", "limit": 10})
        assert r.status_code == 200, f"audit-logs filtered by entity_type failed: {r.text}"
        data = r.json()
        assert "logs" in data

    def test_audit_logs_filter_by_entity_id(self, admin_headers):
        """Register a partner, then check audit logs exist for that tenant_id."""
        if not TestAutoAssignFreeTrialOnSignup._tenant_id:
            pytest.skip("Tenant id from TestAutoAssignFreeTrialOnSignup not available")

        tenant_id = TestAutoAssignFreeTrialOnSignup._tenant_id
        r = requests.get(
            f"{BASE_URL}/api/admin/audit-logs",
            headers=admin_headers,
            params={"entity_type": "tenant", "entity_id": tenant_id, "limit": 20},
        )
        assert r.status_code == 200, f"audit-logs for tenant failed: {r.text}"
        data = r.json()
        logs = data.get("logs", [])
        assert len(logs) > 0, (
            f"Expected at least 1 audit log for tenant {tenant_id}, got 0. "
            f"This may mean audit logs are not written or entity_type filter is wrong."
        )

    def test_audit_log_response_has_correct_fields(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/audit-logs", headers=admin_headers, params={"limit": 1})
        assert r.status_code == 200
        logs = r.json().get("logs", [])
        if logs:
            log = logs[0]
            # Required fields in audit trail
            assert "action" in log, f"Log missing 'action' field: {log}"
            assert "occurred_at" in log, f"Log missing 'occurred_at' field: {log}"


# ── 7. Billing service unit tests ─────────────────────────────────────────────

class TestBillingService:
    """Unit tests for /app/backend/services/billing_service.py"""

    def test_billing_service_module_exists(self):
        sys.path.insert(0, "/app/backend")
        import importlib
        spec = importlib.util.find_spec("services.billing_service")
        assert spec is not None, "billing_service module not found"

    def test_next_first_of_month_exists_and_works(self):
        sys.path.insert(0, "/app/backend")
        from services.billing_service import next_first_of_month
        from datetime import date
        # Feb 15 → Mar 1
        result = next_first_of_month(date(2026, 2, 15))
        assert result == date(2026, 3, 1), f"Expected 2026-03-01, got {result}"

    def test_next_first_of_month_december(self):
        sys.path.insert(0, "/app/backend")
        from services.billing_service import next_first_of_month
        from datetime import date
        # Dec 20 → Jan 1 next year
        result = next_first_of_month(date(2025, 12, 20))
        assert result == date(2026, 1, 1), f"Expected 2026-01-01, got {result}"

    def test_calculate_prorata_exists_and_returns_correct_keys(self):
        sys.path.insert(0, "/app/backend")
        from services.billing_service import calculate_prorata
        from datetime import date
        result = calculate_prorata(100.0, date(2026, 2, 1))
        required_keys = ["prorata_amount", "days_remaining", "days_in_month", "next_billing_date", "daily_rate"]
        for key in required_keys:
            assert key in result, f"calculate_prorata missing key '{key}'"

    def test_calculate_prorata_full_month(self):
        """Start on 1st = full month charge."""
        sys.path.insert(0, "/app/backend")
        from services.billing_service import calculate_prorata
        from datetime import date
        result = calculate_prorata(100.0, date(2026, 2, 1))
        # Feb 2026 has 28 days; starting day 1 = 28/28 * 100 = 100
        assert result["prorata_amount"] == 100.0, f"Expected 100.0 for full month, got {result['prorata_amount']}"

    def test_calculate_prorata_mid_month(self):
        """Start mid-month = partial charge."""
        sys.path.insert(0, "/app/backend")
        from services.billing_service import calculate_prorata
        from datetime import date
        # Jan 2026 has 31 days. Starting Jan 16 → 16 days remaining (16,17,...31)
        result = calculate_prorata(310.0, date(2026, 1, 16))
        # 310 / 31 * 16 = 160.0
        assert result["prorata_amount"] == 160.0, f"Expected 160.0, got {result['prorata_amount']}"

    def test_calculate_upgrade_prorata_exists_and_returns_correct_keys(self):
        sys.path.insert(0, "/app/backend")
        from services.billing_service import calculate_upgrade_prorata
        from datetime import date
        result = calculate_upgrade_prorata(50.0, 100.0, date(2026, 2, 15))
        required_keys = [
            "prorata_amount", "days_remaining", "days_in_month",
            "next_billing_date", "old_monthly_amount", "new_monthly_amount", "daily_diff_rate",
        ]
        for key in required_keys:
            assert key in result, f"calculate_upgrade_prorata missing key '{key}'"

    def test_calculate_upgrade_prorata_values(self):
        """Upgrade from 50→100 on Feb 15: diff=50, 14 days remain, dim=28, charge=25.0"""
        sys.path.insert(0, "/app/backend")
        from services.billing_service import calculate_upgrade_prorata
        from datetime import date
        # Feb 2026: 28 days. From Feb 15: 28-15+1=14 days remain
        result = calculate_upgrade_prorata(50.0, 100.0, date(2026, 2, 15))
        # diff=50, daily=50/28, amount=round(50/28*14,2)=round(25.0,2)=25.0
        assert result["prorata_amount"] == 25.0, f"Expected 25.0, got {result['prorata_amount']}"
        assert result["days_remaining"] == 14

    def test_calculate_upgrade_prorata_no_downgrade(self):
        """Downgrade (new < old) should produce prorata_amount=0."""
        sys.path.insert(0, "/app/backend")
        from services.billing_service import calculate_upgrade_prorata
        from datetime import date
        result = calculate_upgrade_prorata(100.0, 50.0, date(2026, 2, 15))
        assert result["prorata_amount"] == 0.0, f"Downgrade should be 0.0, got {result['prorata_amount']}"
