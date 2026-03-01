"""
Backend tests for iter158 - Partner Subscriptions new features:
1. billing_service.advance_billing_date (monthly/quarterly/annual)
2. POST /api/partner/billing-portal
3. GET /api/partner/upgrade-plan-status (unknown session → 404)
4. Admin partner subscription CRUD with expiry date
"""
import os
import sys
import pytest
import requests
from datetime import date

# Add backend to path for unit testing billing_service
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


# ---------------------------------------------------------------------------
# Unit tests for billing_service.advance_billing_date
# ---------------------------------------------------------------------------

class TestAdvanceBillingDate:
    """Direct unit tests for billing_service.advance_billing_date"""

    def test_monthly_advance(self):
        """Monthly: 2026-05-01 → 2026-06-01"""
        from services.billing_service import advance_billing_date
        result = advance_billing_date("2026-05-01", "monthly")
        assert result == "2026-06-01", f"Expected 2026-06-01, got {result}"
        print(f"PASS: monthly advance 2026-05-01 → {result}")

    def test_quarterly_advance(self):
        """Quarterly: 2026-04-01 → 2026-07-01"""
        from services.billing_service import advance_billing_date
        result = advance_billing_date("2026-04-01", "quarterly")
        assert result == "2026-07-01", f"Expected 2026-07-01, got {result}"
        print(f"PASS: quarterly advance 2026-04-01 → {result}")

    def test_annual_advance(self):
        """Annual: 2026-04-01 → 2027-04-01"""
        from services.billing_service import advance_billing_date
        result = advance_billing_date("2026-04-01", "annual")
        assert result == "2027-04-01", f"Expected 2027-04-01, got {result}"
        print(f"PASS: annual advance 2026-04-01 → {result}")

    def test_monthly_year_boundary(self):
        """Monthly: 2026-12-01 → 2027-01-01 (year boundary)"""
        from services.billing_service import advance_billing_date
        result = advance_billing_date("2026-12-01", "monthly")
        assert result == "2027-01-01", f"Expected 2027-01-01, got {result}"
        print(f"PASS: monthly year boundary 2026-12-01 → {result}")

    def test_quarterly_year_boundary(self):
        """Quarterly: 2026-11-01 → 2027-02-01"""
        from services.billing_service import advance_billing_date
        result = advance_billing_date("2026-11-01", "quarterly")
        assert result == "2027-02-01", f"Expected 2027-02-01, got {result}"
        print(f"PASS: quarterly year boundary 2026-11-01 → {result}")

    def test_advance_default_monthly(self):
        """Default interval (no arg) → monthly"""
        from services.billing_service import advance_billing_date
        result = advance_billing_date("2026-01-01")
        assert result == "2026-02-01", f"Expected 2026-02-01, got {result}"
        print(f"PASS: default (monthly) advance 2026-01-01 → {result}")

    def test_advance_result_always_first_of_month(self):
        """advance_billing_date always returns 1st of month regardless of input day"""
        from services.billing_service import advance_billing_date
        # Start from a mid-month date
        result = advance_billing_date("2026-03-15", "monthly")
        # Result should land on 1st of next month
        d = date.fromisoformat(result)
        assert d.day == 1, f"Expected day=1, got day={d.day}"
        print(f"PASS: advance_billing_date returns 1st of month: {result}")


# ---------------------------------------------------------------------------
# Auth fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def platform_admin_token():
    """Login as platform admin and return token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!"
    })
    if resp.status_code == 200:
        token = resp.json().get("token") or resp.json().get("access_token")
        print(f"Platform admin login: OK, token={token[:20]}...")
        return token
    pytest.skip(f"Platform admin login failed: {resp.status_code} {resp.text}")


@pytest.fixture(scope="module")
def partner_admin_token():
    """Login as partner admin (testpartner@example.com) and return token."""
    # Try direct login first
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "testpartner@example.com",
        "password": "TestPass123!"
    })
    if resp.status_code == 200:
        token = resp.json().get("token") or resp.json().get("access_token")
        print(f"Partner admin login (direct): OK")
        return token
    # Try partner login with partner code
    resp2 = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
        "partner_code": "test-partner-co",
        "email": "testpartner@example.com",
        "password": "TestPass123!"
    })
    if resp2.status_code == 200:
        token = resp2.json().get("token") or resp2.json().get("access_token")
        print(f"Partner admin login (partner-login): OK")
        return token
    pytest.skip(f"Partner admin login failed: {resp.status_code} / {resp2.status_code}")


# ---------------------------------------------------------------------------
# Backend API tests: Admin Partner Subscriptions
# ---------------------------------------------------------------------------

class TestAdminPartnerSubscriptions:
    """Tests for admin partner-subscriptions endpoints (platform admin)"""

    def test_list_partner_subscriptions(self, platform_admin_token):
        """GET /api/admin/partner-subscriptions returns list"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/partner-subscriptions",
            headers={"Authorization": f"Bearer {platform_admin_token}"}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "subscriptions" in data
        assert "total" in data
        print(f"PASS: List partner subs: {data['total']} total")

    def test_list_partner_subscriptions_stats(self, platform_admin_token):
        """GET /api/admin/partner-subscriptions/stats returns stats"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/partner-subscriptions/stats",
            headers={"Authorization": f"Bearer {platform_admin_token}"}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "total" in data
        assert "active" in data
        print(f"PASS: Stats: total={data['total']}, active={data['active']}")

    def test_create_partner_subscription_with_expiry(self, platform_admin_token):
        """POST create subscription with contract_end_date (expiry)"""
        # First get a valid partner ID
        tenants_resp = requests.get(
            f"{BASE_URL}/api/admin/tenants",
            headers={"Authorization": f"Bearer {platform_admin_token}"}
        )
        if tenants_resp.status_code != 200:
            pytest.skip("Cannot list tenants")
        tenants = tenants_resp.json().get("tenants", [])
        # Filter out platform admin tenant
        partner_tenants = [t for t in tenants if t.get("code") != "automate-accounts"]
        if not partner_tenants:
            pytest.skip("No partner tenants available")
        partner_id = partner_tenants[0]["id"]

        payload = {
            "partner_id": partner_id,
            "description": "TEST_ITER158 subscription with expiry",
            "amount": 99.0,
            "currency": "GBP",
            "billing_interval": "monthly",
            "status": "pending",
            "payment_method": "manual",
            "start_date": "2026-04-01",
            "next_billing_date": "2026-05-01",
            "term_months": 12,
            "contract_end_date": "2027-04-01",
            "auto_cancel_on_termination": False,
        }
        resp = requests.post(
            f"{BASE_URL}/api/admin/partner-subscriptions",
            json=payload,
            headers={"Authorization": f"Bearer {platform_admin_token}"}
        )
        assert resp.status_code in [200, 201], f"Expected 200/201, got {resp.status_code}: {resp.text}"
        data = resp.json()
        sub = data.get("subscription") or data
        assert sub.get("contract_end_date") == "2027-04-01" or sub.get("contract_end_date", "").startswith("2027-04-01"), \
            f"contract_end_date not set correctly: {sub.get('contract_end_date')}"
        print(f"PASS: Created subscription with expiry: {sub.get('subscription_number')}, expiry={sub.get('contract_end_date')}")
        return sub.get("id") or sub.get("subscription_number")

    def test_partner_subscription_currency_field(self, platform_admin_token):
        """Verify currency field is stored correctly (ISO currency)"""
        tenants_resp = requests.get(
            f"{BASE_URL}/api/admin/tenants",
            headers={"Authorization": f"Bearer {platform_admin_token}"}
        )
        if tenants_resp.status_code != 200:
            pytest.skip("Cannot list tenants")
        tenants = tenants_resp.json().get("tenants", [])
        partner_tenants = [t for t in tenants if t.get("code") != "automate-accounts"]
        if not partner_tenants:
            pytest.skip("No partner tenants available")
        partner_id = partner_tenants[0]["id"]

        for currency in ["GBP", "USD", "EUR"]:
            payload = {
                "partner_id": partner_id,
                "description": f"TEST_ITER158 currency test {currency}",
                "amount": 50.0,
                "currency": currency,
                "billing_interval": "quarterly",
                "status": "pending",
                "payment_method": "manual",
            }
            resp = requests.post(
                f"{BASE_URL}/api/admin/partner-subscriptions",
                json=payload,
                headers={"Authorization": f"Bearer {platform_admin_token}"}
            )
            assert resp.status_code in [200, 201], f"Failed for {currency}: {resp.status_code}"
            data = resp.json()
            sub = data.get("subscription") or data
            assert sub.get("currency") == currency, f"Expected {currency}, got {sub.get('currency')}"
            print(f"PASS: Currency {currency} stored correctly")


# ---------------------------------------------------------------------------
# Backend API tests: Partner Billing Portal
# ---------------------------------------------------------------------------

class TestPartnerBillingPortal:
    """Tests for POST /api/partner/billing-portal"""

    def test_billing_portal_requires_auth(self):
        """POST /api/partner/billing-portal without auth → 401/403"""
        resp = requests.post(f"{BASE_URL}/api/partner/billing-portal")
        assert resp.status_code in [401, 403, 422], \
            f"Expected 401/403/422, got {resp.status_code}: {resp.text}"
        print(f"PASS: billing-portal without auth → {resp.status_code}")

    def test_billing_portal_platform_admin_forbidden(self, platform_admin_token):
        """Platform admin calling billing-portal → 403 (partner-scoped endpoint)"""
        resp = requests.post(
            f"{BASE_URL}/api/partner/billing-portal",
            headers={"Authorization": f"Bearer {platform_admin_token}"}
        )
        assert resp.status_code == 403, \
            f"Expected 403 for platform admin, got {resp.status_code}: {resp.text}"
        print(f"PASS: Platform admin gets 403 on partner billing-portal")

    def test_billing_portal_partner_auth(self, partner_admin_token):
        """Partner calling billing-portal → either portal_url (202/200) or Stripe error (502)"""
        resp = requests.post(
            f"{BASE_URL}/api/partner/billing-portal",
            headers={"Authorization": f"Bearer {partner_admin_token}"}
        )
        # Acceptable outcomes:
        # 200 with portal_url (Stripe configured)
        # 502 Stripe error (Stripe not configured in test env)
        assert resp.status_code in [200, 502, 400], \
            f"Unexpected status {resp.status_code}: {resp.text}"
        if resp.status_code == 200:
            data = resp.json()
            assert "portal_url" in data, "Missing portal_url in response"
            print(f"PASS: billing-portal returned portal_url: {data['portal_url'][:50]}...")
        else:
            # Stripe error expected in test env
            data = resp.json()
            print(f"PASS (expected Stripe error): billing-portal → {resp.status_code}: {data.get('detail', '')[:100]}")


# ---------------------------------------------------------------------------
# Backend API tests: Partner upgrade-plan-status
# ---------------------------------------------------------------------------

class TestUpgradePlanStatus:
    """Tests for GET /api/partner/upgrade-plan-status"""

    def test_unknown_session_returns_404(self, partner_admin_token):
        """GET /api/partner/upgrade-plan-status?session_id=unknown → 404"""
        resp = requests.get(
            f"{BASE_URL}/api/partner/upgrade-plan-status?session_id=cs_test_unknown_fake_session_123",
            headers={"Authorization": f"Bearer {partner_admin_token}"}
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "detail" in data
        print(f"PASS: Unknown session → 404: {data['detail']}")

    def test_upgrade_status_requires_auth(self):
        """Without auth → 401/403"""
        resp = requests.get(f"{BASE_URL}/api/partner/upgrade-plan-status?session_id=test_sess")
        assert resp.status_code in [401, 403, 422], \
            f"Expected 401/403/422, got {resp.status_code}: {resp.text}"
        print(f"PASS: upgrade-plan-status without auth → {resp.status_code}")


# ---------------------------------------------------------------------------
# Backend API tests: Partner My Subscriptions
# ---------------------------------------------------------------------------

class TestPartnerMySubscriptions:
    """Tests for GET /api/partner/my-subscriptions"""

    def test_partner_my_subscriptions_list(self, partner_admin_token):
        """GET /api/partner/my-subscriptions returns list"""
        resp = requests.get(
            f"{BASE_URL}/api/partner/my-subscriptions",
            headers={"Authorization": f"Bearer {partner_admin_token}"}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "subscriptions" in data
        assert "total" in data
        print(f"PASS: my-subscriptions list: {data['total']} items")

    def test_platform_admin_cannot_access_partner_subs(self, platform_admin_token):
        """Platform admin → 403 on partner my-subscriptions"""
        resp = requests.get(
            f"{BASE_URL}/api/partner/my-subscriptions",
            headers={"Authorization": f"Bearer {platform_admin_token}"}
        )
        assert resp.status_code == 403, \
            f"Expected 403, got {resp.status_code}: {resp.text}"
        print(f"PASS: platform admin gets 403 on /partner/my-subscriptions")
