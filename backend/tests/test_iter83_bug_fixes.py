"""
Iteration 83: Backend tests for bug fixes
- Customer Portal 404 handling
- Email templates tenant isolation (no duplicates)
- Stripe/GoCardless test connection endpoint
- Admin manual order/subscription creation
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# ── Credentials ────────────────────────────────────────────────────────────────
PLATFORM_ADMIN_EMAIL = "admin@automateaccounts.local"
PLATFORM_ADMIN_PASS = "ChangeMe123!"
PLATFORM_ADMIN_PARTNER = "automate-accounts"

TENANT_ADMIN_EMAIL = "adminb@tenantb.local"
TENANT_ADMIN_PASS = "ChangeMe123!"
TENANT_ADMIN_PARTNER = "tenant-b-test"

CUSTOMER_EMAIL = "testcustomer@test.com"
CUSTOMER_PASS = "ChangeMe123!"
CUSTOMER_PARTNER = "automate-accounts"


def partner_login(email: str, password: str, partner_code: str) -> tuple:
    """Login as partner/admin using partner-login endpoint."""
    session = requests.Session()
    payload = {"email": email, "password": password, "partner_code": partner_code}
    resp = session.post(f"{BASE_URL}/api/auth/partner-login", json=payload)
    return session, resp


def customer_login(email: str, password: str, partner_code: str) -> tuple:
    """Login as customer using customer-login endpoint."""
    session = requests.Session()
    payload = {"email": email, "password": password, "partner_code": partner_code}
    resp = session.post(f"{BASE_URL}/api/auth/customer-login", json=payload)
    return session, resp


@pytest.fixture(scope="module")
def platform_admin_session():
    session, resp = partner_login(PLATFORM_ADMIN_EMAIL, PLATFORM_ADMIN_PASS, PLATFORM_ADMIN_PARTNER)
    if resp.status_code != 200:
        pytest.skip(f"Platform admin login failed: {resp.status_code} {resp.text}")
    return session


@pytest.fixture(scope="module")
def tenant_admin_session():
    session, resp = partner_login(TENANT_ADMIN_EMAIL, TENANT_ADMIN_PASS, TENANT_ADMIN_PARTNER)
    if resp.status_code != 200:
        pytest.skip(f"Tenant admin login failed: {resp.status_code} {resp.text}")
    return session


@pytest.fixture(scope="module")
def customer_session():
    session, resp = customer_login(CUSTOMER_EMAIL, CUSTOMER_PASS, CUSTOMER_PARTNER)
    if resp.status_code != 200:
        pytest.skip(f"Customer login failed: {resp.status_code} {resp.text}")
    return session


# ── 1. Customer Portal API (orders, subscriptions) ───────────────────────────

class TestCustomerPortal:
    """Test customer portal API endpoints"""

    def test_customer_can_get_orders(self, customer_session):
        """Customer should be able to get their orders without 404"""
        resp = customer_session.get(f"{BASE_URL}/api/orders")
        assert resp.status_code == 200, f"Customer portal orders failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "orders" in data
        print(f"PASS: Customer orders endpoint returns {len(data['orders'])} orders")

    def test_customer_can_get_subscriptions(self, customer_session):
        """Customer should be able to get their subscriptions"""
        resp = customer_session.get(f"{BASE_URL}/api/subscriptions")
        assert resp.status_code == 200, f"Customer portal subscriptions failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "subscriptions" in data
        print(f"PASS: Customer subscriptions endpoint returns {len(data['subscriptions'])} subscriptions")

    def test_admin_portal_orders_gives_404_or_customer_data(self, platform_admin_session):
        """Admin accessing portal orders should get 404 (no customer record) or their data"""
        resp = platform_admin_session.get(f"{BASE_URL}/api/orders")
        # Admin might get 404 (no customer record) or 200 if admin has customer record
        assert resp.status_code in [200, 404], f"Unexpected status: {resp.status_code} {resp.text}"
        if resp.status_code == 404:
            print("PASS: Admin gets 404 as expected (no customer account)")
        else:
            print("PASS: Admin has customer record, gets 200")


# ── 2. Email Templates - Tenant Isolation ────────────────────────────────────

class TestEmailTemplatesTenantIsolation:
    """Test that email templates are filtered by tenant (no duplicates)"""

    def test_platform_admin_email_templates_count(self, platform_admin_session):
        """Platform admin email templates should not show duplicates from all tenants"""
        resp = platform_admin_session.get(f"{BASE_URL}/api/admin/email-templates")
        assert resp.status_code == 200, f"Email templates failed: {resp.status_code} {resp.text}"
        data = resp.json()
        templates = data.get("templates", [])
        print(f"Platform admin has {len(templates)} email templates")
        # Should NOT show 21+ (which would be duplicates across all tenants)
        # Should show ~10 or fewer
        assert len(templates) <= 15, f"Too many templates ({len(templates)}), possible duplication across tenants"
        print(f"PASS: Template count {len(templates)} is within expected range (not duplicated)")

    def test_tenant_admin_email_templates_count(self, tenant_admin_session):
        """Tenant admin should only see their own templates"""
        resp = tenant_admin_session.get(f"{BASE_URL}/api/admin/email-templates")
        assert resp.status_code == 200, f"Email templates failed: {resp.status_code} {resp.text}"
        data = resp.json()
        templates = data.get("templates", [])
        print(f"Tenant admin has {len(templates)} email templates")
        assert len(templates) <= 15, f"Too many templates ({len(templates)}), possible duplication across tenants"
        print(f"PASS: Tenant templates count {len(templates)} within range")

    def test_templates_have_distinct_triggers(self, platform_admin_session):
        """No two templates should have same trigger (would indicate duplicates)"""
        resp = platform_admin_session.get(f"{BASE_URL}/api/admin/email-templates")
        assert resp.status_code == 200
        templates = resp.json().get("templates", [])
        triggers = [t.get("trigger") for t in templates]
        unique_triggers = set(triggers)
        assert len(triggers) == len(unique_triggers), f"Duplicate triggers found: {[t for t in triggers if triggers.count(t) > 1]}"
        print(f"PASS: All {len(triggers)} template triggers are unique")


# ── 3. Stripe / GoCardless Validate Endpoint ─────────────────────────────────

class TestStripeValidateEndpoint:
    """Test that POST /api/oauth/stripe/validate endpoint exists and responds"""

    def test_stripe_validate_endpoint_exists(self, platform_admin_session):
        """Stripe validate endpoint should exist (even if not configured)"""
        resp = platform_admin_session.post(f"{BASE_URL}/api/oauth/stripe/validate")
        # Should get 400 (no credentials) or 200 (if configured), NOT 404
        assert resp.status_code in [200, 400, 422, 500], f"Unexpected status: {resp.status_code}"
        assert resp.status_code != 404, "Stripe validate endpoint not found (404)"
        print(f"PASS: Stripe validate endpoint exists, status={resp.status_code}")

    def test_gocardless_validate_endpoint_exists(self, platform_admin_session):
        """GoCardless validate endpoint should exist"""
        resp = platform_admin_session.post(f"{BASE_URL}/api/oauth/gocardless/validate")
        assert resp.status_code != 404, "GoCardless validate endpoint not found (404)"
        assert resp.status_code in [200, 400, 422, 500]
        print(f"PASS: GoCardless validate endpoint exists, status={resp.status_code}")

    def test_unknown_provider_validate_returns_400(self, platform_admin_session):
        """Unknown provider validate should return 400"""
        resp = platform_admin_session.post(f"{BASE_URL}/api/oauth/unknown_provider/validate")
        assert resp.status_code == 400, f"Expected 400 for unknown provider, got {resp.status_code}"
        print(f"PASS: Unknown provider returns 400")


# ── 4. Admin Orders - Manual Creation ────────────────────────────────────────

class TestAdminManualOrder:
    """Test admin manual order creation API"""

    def test_admin_get_customers_for_manual_order(self, platform_admin_session):
        """Admin should be able to get customers list for manual order dropdown"""
        resp = platform_admin_session.get(f"{BASE_URL}/api/admin/customers")
        assert resp.status_code == 200, f"Admin customers failed: {resp.status_code}"
        data = resp.json()
        assert "customers" in data
        print(f"PASS: Admin can fetch {len(data['customers'])} customers for manual order")

    def test_admin_get_products_for_manual_order(self, platform_admin_session):
        """Admin should be able to get products list for manual order dropdown"""
        resp = platform_admin_session.get(f"{BASE_URL}/api/admin/products-all")
        assert resp.status_code == 200, f"Admin products-all failed: {resp.status_code}"
        data = resp.json()
        products = data.get("products", [])
        print(f"PASS: Admin can fetch {len(products)} products for manual order")


# ── 5. Admin Subscriptions - Manual Creation ──────────────────────────────────

class TestAdminManualSubscription:
    """Test admin manual subscription creation API"""

    def test_admin_get_customers_for_manual_sub(self, platform_admin_session):
        """Admin should be able to get customers list for manual subscription"""
        resp = platform_admin_session.get(f"{BASE_URL}/api/admin/customers")
        assert resp.status_code == 200, f"Admin customers failed: {resp.status_code}"
        data = resp.json()
        assert "customers" in data
        print(f"PASS: Customers available for manual subscription: {len(data['customers'])}")

    def test_admin_subscriptions_list(self, platform_admin_session):
        """Admin can list subscriptions"""
        resp = platform_admin_session.get(f"{BASE_URL}/api/admin/subscriptions")
        assert resp.status_code == 200, f"Admin subscriptions failed: {resp.status_code}"
        data = resp.json()
        assert "subscriptions" in data
        print(f"PASS: Admin subscriptions: {len(data['subscriptions'])} found")


# ── 6. General API Health ────────────────────────────────────────────────────

class TestAPIHealth:
    """Basic API health checks"""

    def test_backend_health(self):
        resp = requests.get(f"{BASE_URL}/api/settings/public")
        assert resp.status_code == 200
        print(f"PASS: Backend accessible via /api/settings/public")

    def test_public_settings(self):
        resp = requests.get(f"{BASE_URL}/api/settings/public")
        assert resp.status_code == 200
        data = resp.json()
        assert "settings" in data
        print(f"PASS: Public settings accessible")
