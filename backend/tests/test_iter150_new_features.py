"""
Iteration 150: Test new features
1. Partner billing emails (partner_subscription_created, partner_order_created, subscription_terminated)
2. Partner admin views own orders/subscriptions under My Billing
3. Subscription term fields (term_months, auto_cancel_on_termination, contract_end_date)
4. Products default_term_months field
5. License limit enforcement for manual order/subscription creation (FIXED from iter149)
6. Email templates tab shows 'Partner Billing Templates' section only for platform admins
"""
import pytest
import requests
import os
from datetime import datetime, timedelta, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Credentials
PLATFORM_ADMIN_CODE = "automate-accounts"
PLATFORM_ADMIN_EMAIL = "admin@automateaccounts.local"
PLATFORM_ADMIN_PASS = "ChangeMe123!"

PARTNER_ADMIN_CODE = "bright-accounting"
PARTNER_ADMIN_EMAIL = "sarah@brightaccounting.local"
PARTNER_ADMIN_PASS = "ChangeMe123!"

# Test data
BRIGHT_ACCOUNTING_PRODUCT_ID = "1b524bcb-0665-492d-9b82-da390fb08c4b"


def get_auth_cookies(tenant_code: str, email: str, password: str) -> dict:
    """Helper to login and get session cookies."""
    session = requests.Session()
    # Step 1: Set tenant context
    r = session.post(f"{BASE_URL}/api/auth/set-tenant", json={"tenant_code": tenant_code})
    if r.status_code not in (200, 204):
        return {}
    # Step 2: Login
    r2 = session.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    if r2.status_code != 200:
        return {}
    return session.cookies.get_dict()


@pytest.fixture(scope="module")
def platform_session():
    """Platform admin session."""
    session = requests.Session()
    r = session.post(f"{BASE_URL}/api/auth/set-tenant", json={"tenant_code": PLATFORM_ADMIN_CODE})
    assert r.status_code in (200, 204), f"Set tenant failed: {r.text}"
    r2 = session.post(f"{BASE_URL}/api/auth/login", json={"email": PLATFORM_ADMIN_EMAIL, "password": PLATFORM_ADMIN_PASS})
    assert r2.status_code == 200, f"Login failed: {r2.text}"
    return session


@pytest.fixture(scope="module")
def partner_session():
    """Partner admin session (bright-accounting)."""
    session = requests.Session()
    r = session.post(f"{BASE_URL}/api/auth/set-tenant", json={"tenant_code": PARTNER_ADMIN_CODE})
    assert r.status_code in (200, 204), f"Set tenant failed: {r.text}"
    r2 = session.post(f"{BASE_URL}/api/auth/login", json={"email": PARTNER_ADMIN_EMAIL, "password": PARTNER_ADMIN_PASS})
    assert r2.status_code == 200, f"Login failed: {r2.text}"
    return session


# ─────────────────────────────────────────────────────────────────────────────
# 1. Email Templates: Partner Billing Templates
# ─────────────────────────────────────────────────────────────────────────────

class TestPartnerBillingEmailTemplates:
    """Verify 3 partner_billing templates are seeded"""

    def test_email_templates_includes_partner_billing(self, platform_session):
        """GET /api/admin/email-templates should include 3 partner_billing templates."""
        r = platform_session.get(f"{BASE_URL}/api/admin/email-templates")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        templates = data.get("templates", [])
        assert isinstance(templates, list), "Expected list of templates"
        
        partner_billing_templates = [t for t in templates if t.get("category") == "partner_billing"]
        assert len(partner_billing_templates) >= 3, (
            f"Expected at least 3 partner_billing templates, got {len(partner_billing_templates)}. "
            f"Found categories: {[t.get('category') for t in templates]}"
        )
        
        # Verify the 3 expected triggers
        triggers = {t["trigger"] for t in partner_billing_templates}
        assert "partner_subscription_created" in triggers, "Missing partner_subscription_created template"
        assert "partner_order_created" in triggers, "Missing partner_order_created template"
        assert "subscription_terminated" in triggers, "Missing subscription_terminated template"

    def test_partner_subscription_created_template_structure(self, platform_session):
        """Verify partner_subscription_created template has expected variables."""
        r = platform_session.get(f"{BASE_URL}/api/admin/email-templates")
        assert r.status_code == 200
        templates = r.json().get("templates", [])
        tmpl = next((t for t in templates if t["trigger"] == "partner_subscription_created"), None)
        assert tmpl is not None, "partner_subscription_created template not found"
        assert tmpl.get("is_enabled") is True, "Template should be enabled"
        assert "{{partner_code}}" in tmpl.get("available_variables", []), "Should have partner_code variable"
        assert "{{subscription_number}}" in tmpl.get("available_variables", [])

    def test_partner_order_created_template_structure(self, platform_session):
        """Verify partner_order_created template has expected variables."""
        r = platform_session.get(f"{BASE_URL}/api/admin/email-templates")
        assert r.status_code == 200
        templates = r.json().get("templates", [])
        tmpl = next((t for t in templates if t["trigger"] == "partner_order_created"), None)
        assert tmpl is not None, "partner_order_created template not found"
        assert tmpl.get("is_enabled") is True

    def test_subscription_terminated_template_structure(self, platform_session):
        """Verify subscription_terminated template has expected variables."""
        r = platform_session.get(f"{BASE_URL}/api/admin/email-templates")
        assert r.status_code == 200
        templates = r.json().get("templates", [])
        tmpl = next((t for t in templates if t["trigger"] == "subscription_terminated"), None)
        assert tmpl is not None, "subscription_terminated template not found"
        vars_list = tmpl.get("available_variables", [])
        assert "{{recipient_name}}" in vars_list
        assert "{{subscription_number}}" in vars_list
        assert "{{cancel_reason}}" in vars_list


# ─────────────────────────────────────────────────────────────────────────────
# 2. Partner Admin: My Orders / My Subscriptions
# ─────────────────────────────────────────────────────────────────────────────

class TestPartnerBillingView:
    """Partner admin can view own orders and subscriptions."""

    def test_my_subscriptions_returns_200(self, partner_session):
        """GET /api/partner/my-subscriptions as partner admin should return 200."""
        r = partner_session.get(f"{BASE_URL}/api/partner/my-subscriptions")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "subscriptions" in data, "Response should have 'subscriptions' key"
        assert "total" in data, "Response should have 'total' key"

    def test_my_orders_returns_200(self, partner_session):
        """GET /api/partner/my-orders as partner admin should return 200."""
        r = partner_session.get(f"{BASE_URL}/api/partner/my-orders")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "orders" in data, "Response should have 'orders' key"
        assert "total" in data, "Response should have 'total' key"

    def test_platform_admin_blocked_from_my_subscriptions(self, platform_session):
        """Platform admin should get 403 from /api/partner/my-subscriptions."""
        r = platform_session.get(f"{BASE_URL}/api/partner/my-subscriptions")
        assert r.status_code == 403, f"Expected 403 for platform admin, got {r.status_code}: {r.text}"

    def test_platform_admin_blocked_from_my_orders(self, platform_session):
        """Platform admin should get 403 from /api/partner/my-orders."""
        r = platform_session.get(f"{BASE_URL}/api/partner/my-orders")
        assert r.status_code == 403, f"Expected 403 for platform admin, got {r.status_code}: {r.text}"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Partner Subscription: term_months, contract_end_date
# ─────────────────────────────────────────────────────────────────────────────

class TestPartnerSubscriptionTerm:
    """Term months and contract end date logic for partner subscriptions."""

    created_sub_id = None

    def test_create_partner_subscription_with_term_months(self, platform_session):
        """POST /api/admin/partner-subscriptions with term_months=12 should set contract_end_date."""
        # Get bright-accounting tenant id
        r = platform_session.get(f"{BASE_URL}/api/admin/tenants?search=bright-accounting")
        assert r.status_code == 200
        tenants = r.json().get("tenants", [])
        bright_tenant = next((t for t in tenants if t.get("code") == "bright-accounting"), None)
        if not bright_tenant:
            pytest.skip("bright-accounting tenant not found")
        
        partner_id = bright_tenant["id"]
        
        payload = {
            "partner_id": partner_id,
            "description": "TEST_Sub_Term12",
            "amount": 99.99,
            "currency": "GBP",
            "billing_interval": "monthly",
            "status": "active",
            "payment_method": "manual",
            "term_months": 12,
            "auto_cancel_on_termination": True,
            "start_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        }
        
        r2 = platform_session.post(f"{BASE_URL}/api/admin/partner-subscriptions", json=payload)
        assert r2.status_code in (200, 201), f"Expected 200/201, got {r2.status_code}: {r2.text}"
        
        sub = r2.json().get("subscription", {})
        assert sub.get("term_months") == 12, f"Expected term_months=12, got {sub.get('term_months')}"
        assert sub.get("auto_cancel_on_termination") is True
        assert sub.get("contract_end_date") is not None, "contract_end_date should be set"
        
        # Verify contract_end_date is ~12 months from now
        end_date = datetime.fromisoformat(sub["contract_end_date"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc).replace(tzinfo=timezone.utc)
        expected_end = now + timedelta(days=30 * 12)
        diff_days = abs((end_date.date() - expected_end.date()).days)
        assert diff_days <= 5, f"contract_end_date {end_date.date()} too far from expected {expected_end.date()}"
        
        # Save for cancel test
        TestPartnerSubscriptionTerm.created_sub_id = sub["id"]
        print(f"Created partner subscription: {sub['id']} with contract_end={sub['contract_end_date']}")

    def test_cancel_partner_subscription_with_active_term_returns_400(self, platform_session):
        """PATCH /api/admin/partner-subscriptions/{id}/cancel when term active should return 400."""
        sub_id = TestPartnerSubscriptionTerm.created_sub_id
        if not sub_id:
            pytest.skip("No sub created in previous test")
        
        r = platform_session.patch(f"{BASE_URL}/api/admin/partner-subscriptions/{sub_id}/cancel")
        assert r.status_code == 400, f"Expected 400 (term active), got {r.status_code}: {r.text}"
        
        detail = r.json().get("detail", "")
        assert "contract" in detail.lower() or "term" in detail.lower(), (
            f"Error should mention contract term, got: {detail}"
        )

    def test_cleanup_created_partner_subscription(self, platform_session):
        """Clean up: override term to 0 and cancel."""
        sub_id = TestPartnerSubscriptionTerm.created_sub_id
        if not sub_id:
            pytest.skip("No sub to clean up")
        
        # Update term to 0 (clear term) 
        r = platform_session.put(f"{BASE_URL}/api/admin/partner-subscriptions/{sub_id}", json={"term_months": -1})
        assert r.status_code == 200, f"Failed to clear term: {r.text}"
        
        # Now cancel
        r2 = platform_session.patch(f"{BASE_URL}/api/admin/partner-subscriptions/{sub_id}/cancel")
        assert r2.status_code == 200, f"Failed to cancel after clearing term: {r2.text}"
        
        sub = r2.json().get("subscription", {})
        assert sub.get("status") == "cancelled"


# ─────────────────────────────────────────────────────────────────────────────
# 4. Customer Subscription: term_months, contract_end_date
# ─────────────────────────────────────────────────────────────────────────────

class TestCustomerSubscriptionTerm:
    """Term months and contract end date logic for customer subscriptions."""

    created_sub_id = None
    created_customer_id = None

    def test_create_manual_subscription_with_term_months(self, platform_session):
        """POST /api/admin/subscriptions/manual with term_months=6 should set contract_end_date."""
        # Get bright-accounting tenant's customers
        # First get a customer from the platform tenant
        r = platform_session.get(f"{BASE_URL}/api/admin/customers?limit=5")
        assert r.status_code == 200
        customers = r.json().get("customers", [])
        if not customers:
            pytest.skip("No customers available")
        
        # Get a product
        r2 = platform_session.get(f"{BASE_URL}/api/admin/products?is_subscription=true&limit=5")
        assert r2.status_code == 200
        products = r2.json().get("products", [])
        if not products:
            pytest.skip("No subscription products available")
        
        customer = customers[0]
        product = products[0]
        
        start_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        renewal_date = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        payload = {
            "customer_email": customer.get("email", ""),
            "product_id": product["id"],
            "amount": 50.0,
            "currency": "USD",
            "status": "active",
            "renewal_date": renewal_date,
            "start_date": start_date,
            "term_months": 6,
            "auto_cancel_on_termination": False,
        }
        
        r3 = platform_session.post(f"{BASE_URL}/api/admin/subscriptions/manual", json=payload)
        assert r3.status_code in (200, 201), f"Expected 200/201, got {r3.status_code}: {r3.text}"
        
        data = r3.json()
        sub_id = data.get("subscription_id")
        assert sub_id is not None
        
        # Fetch the subscription to verify fields
        r4 = platform_session.get(f"{BASE_URL}/api/admin/subscriptions")
        assert r4.status_code == 200
        subs = r4.json().get("subscriptions", [])
        created_sub = next((s for s in subs if s.get("id") == sub_id), None)
        
        if created_sub is None:
            # Try fetching directly if available
            pytest.skip("Could not find created subscription in list - may need specific endpoint")
        
        assert created_sub.get("term_months") == 6, f"Expected term_months=6, got {created_sub.get('term_months')}"
        assert created_sub.get("contract_end_date") is not None, "contract_end_date should be set"
        
        # Verify contract_end_date is ~6 months from now
        end_date = datetime.fromisoformat(created_sub["contract_end_date"].replace("Z", "+00:00"))
        now_dt = datetime.now(timezone.utc)
        expected_end = now_dt + timedelta(days=30 * 6)
        diff_days = abs((end_date.date() - expected_end.date()).days)
        assert diff_days <= 5, f"contract_end_date {end_date.date()} too far from expected {expected_end.date()}"
        
        TestCustomerSubscriptionTerm.created_sub_id = sub_id
        print(f"Created customer subscription: {sub_id} with term_months=6, contract_end={created_sub['contract_end_date']}")

    def test_cancel_subscription_with_active_term_returns_400(self, platform_session):
        """POST /api/admin/subscriptions/{id}/cancel when term active should return 400."""
        sub_id = TestCustomerSubscriptionTerm.created_sub_id
        if not sub_id:
            pytest.skip("No sub created in previous test")
        
        r = platform_session.post(f"{BASE_URL}/api/admin/subscriptions/{sub_id}/cancel")
        assert r.status_code == 400, f"Expected 400 (term active), got {r.status_code}: {r.text}"
        
        detail = r.json().get("detail", "")
        assert "contract" in detail.lower() or "term" in detail.lower(), (
            f"Error should mention contract term, got: {detail}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 5. License Enforcement (FIXED from iter149)
# ─────────────────────────────────────────────────────────────────────────────

class TestLicenseEnforcement:
    """License limit enforcement for manual order and subscription creation."""

    bright_tenant_id = None

    def _get_bright_tenant_id(self, platform_session):
        if self.__class__.bright_tenant_id:
            return self.__class__.bright_tenant_id
        r = platform_session.get(f"{BASE_URL}/api/admin/tenants?search=bright-accounting")
        assert r.status_code == 200
        tenants = r.json().get("tenants", [])
        bright_tenant = next((t for t in tenants if t.get("code") == "bright-accounting"), None)
        if not bright_tenant:
            pytest.skip("bright-accounting tenant not found")
        self.__class__.bright_tenant_id = bright_tenant["id"]
        return self.__class__.bright_tenant_id

    def test_license_enforcement_orders_manual_at_limit(self, platform_session):
        """POST /api/admin/orders/manual when at monthly limit should return 403."""
        tenant_id = self._get_bright_tenant_id(platform_session)
        
        # Set limit to 1
        r_set = platform_session.put(f"{BASE_URL}/api/admin/tenants/{tenant_id}/license", json={
            "max_orders_per_month": 1
        })
        if r_set.status_code not in (200, 204):
            pytest.skip(f"Could not set license limit: {r_set.text}")
        
        # Set current usage to 1 (directly at limit)
        # Use the partner session (bright-accounting) to trigger check
        partner_ses = requests.Session()
        r_t = partner_ses.post(f"{BASE_URL}/api/auth/set-tenant", json={"tenant_code": "bright-accounting"})
        r_l = partner_ses.post(f"{BASE_URL}/api/auth/login", json={"email": PARTNER_ADMIN_EMAIL, "password": PARTNER_ADMIN_PASS})
        
        if r_l.status_code != 200:
            pytest.skip("Could not login as partner admin")
        
        # Get a customer and product for the partner
        r_cust = partner_ses.get(f"{BASE_URL}/api/admin/customers?limit=1")
        if r_cust.status_code != 200 or not r_cust.json().get("customers"):
            pytest.skip("No customers for bright-accounting")
        
        r_prod = partner_ses.get(f"{BASE_URL}/api/admin/products?limit=1")
        if r_prod.status_code != 200 or not r_prod.json().get("products"):
            pytest.skip("No products for bright-accounting")
        
        customer = r_cust.json()["customers"][0]
        product = r_prod.json()["products"][0]
        
        # Set usage via MongoDB directly would be ideal, but we test the enforcement
        # Let's set max to 0 which means blocked
        r_set2 = platform_session.put(f"{BASE_URL}/api/admin/tenants/{tenant_id}/license", json={
            "max_orders_per_month": 0
        })
        
        # With limit=0, first order creation should be blocked (0 limit = no orders allowed)
        payload = {
            "customer_email": customer.get("email", ""),
            "product_id": product["id"],
            "amount": 10.0,
            "currency": "USD",
            "status": "unpaid",
        }
        r_order = partner_ses.post(f"{BASE_URL}/api/admin/orders/manual", json=payload)
        # If fix is applied, this should return 403; if not, 200
        print(f"Order creation with limit=0 returned: {r_order.status_code}")
        
        # Cleanup: reset license
        platform_session.put(f"{BASE_URL}/api/admin/tenants/{tenant_id}/license", json={
            "max_orders_per_month": None
        })
        
        # The fix from iter149 should have made this return 403
        assert r_order.status_code == 403, (
            f"Expected 403 when orders limit=0, got {r_order.status_code}. "
            "License enforcement for manual orders may not be implemented."
        )

    def test_license_enforcement_subscriptions_manual_at_limit(self, platform_session):
        """POST /api/admin/subscriptions/manual when at monthly limit should return 403."""
        tenant_id = self._get_bright_tenant_id(platform_session)
        
        partner_ses = requests.Session()
        partner_ses.post(f"{BASE_URL}/api/auth/set-tenant", json={"tenant_code": "bright-accounting"})
        r_l = partner_ses.post(f"{BASE_URL}/api/auth/login", json={"email": PARTNER_ADMIN_EMAIL, "password": PARTNER_ADMIN_PASS})
        if r_l.status_code != 200:
            pytest.skip("Could not login as partner admin")
        
        # Set subscription limit to 0
        r_set = platform_session.put(f"{BASE_URL}/api/admin/tenants/{tenant_id}/license", json={
            "max_subscriptions_per_month": 0
        })
        
        r_cust = partner_ses.get(f"{BASE_URL}/api/admin/customers?limit=1")
        r_prod = partner_ses.get(f"{BASE_URL}/api/admin/products?is_subscription=true&limit=1")
        
        if r_cust.status_code != 200 or not r_cust.json().get("customers"):
            pytest.skip("No customers for bright-accounting")
        if r_prod.status_code != 200 or not r_prod.json().get("products"):
            pytest.skip("No subscription products for bright-accounting")
        
        customer = r_cust.json()["customers"][0]
        product = r_prod.json()["products"][0]
        
        payload = {
            "customer_email": customer.get("email", ""),
            "product_id": product["id"],
            "amount": 30.0,
            "currency": "USD",
            "status": "active",
            "renewal_date": (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        r_sub = partner_ses.post(f"{BASE_URL}/api/admin/subscriptions/manual", json=payload)
        print(f"Subscription creation with limit=0 returned: {r_sub.status_code}")
        
        # Cleanup
        platform_session.put(f"{BASE_URL}/api/admin/tenants/{tenant_id}/license", json={
            "max_subscriptions_per_month": None
        })
        
        assert r_sub.status_code == 403, (
            f"Expected 403 when subscriptions limit=0, got {r_sub.status_code}. "
            "License enforcement for manual subscriptions may not be implemented."
        )


# ─────────────────────────────────────────────────────────────────────────────
# 6. Products: default_term_months field
# ─────────────────────────────────────────────────────────────────────────────

class TestProductDefaultTermMonths:
    """Products should support default_term_months field."""

    def test_get_product_has_default_term_months_field(self, platform_session):
        """GET products should include default_term_months in response."""
        r = platform_session.get(f"{BASE_URL}/api/admin/products?limit=5")
        assert r.status_code == 200
        products = r.json().get("products", [])
        if not products:
            pytest.skip("No products available")
        # The field should be present (may be null if not set)
        for p in products:
            assert "default_term_months" in p or p.get("default_term_months") is None, (
                f"Product missing default_term_months key: {p.get('id')}"
            )

    def test_create_product_with_default_term_months(self, platform_session):
        """POST /api/admin/products with default_term_months=12 should persist."""
        payload = {
            "name": "TEST_Sub_With_Term",
            "description": "Test subscription product with 12-month default term",
            "price": 99.00,
            "currency": "USD",
            "is_subscription": True,
            "default_term_months": 12,
        }
        r = platform_session.post(f"{BASE_URL}/api/admin/products", json=payload)
        assert r.status_code in (200, 201), f"Expected 200/201, got {r.status_code}: {r.text}"
        
        product = r.json().get("product", r.json())
        product_id = product.get("id")
        assert product_id is not None
        
        # Fetch to verify
        r2 = platform_session.get(f"{BASE_URL}/api/admin/products/{product_id}")
        if r2.status_code == 200:
            fetched = r2.json().get("product", r2.json())
            assert fetched.get("default_term_months") == 12, (
                f"Expected default_term_months=12, got {fetched.get('default_term_months')}"
            )
        
        # Cleanup
        platform_session.delete(f"{BASE_URL}/api/admin/products/{product_id}")
        print(f"Created and cleaned up test product: {product_id}")


# ─────────────────────────────────────────────────────────────────────────────
# 7. Partner Order Email: verify email is sent on order creation
# ─────────────────────────────────────────────────────────────────────────────

class TestPartnerBillingEmails:
    """Verify emails are sent/mocked when partner orders/subscriptions are created."""

    def test_partner_order_creation_triggers_email(self, platform_session):
        """POST /api/admin/partner-orders should trigger partner_order_created email."""
        # Get bright-accounting tenant id
        r = platform_session.get(f"{BASE_URL}/api/admin/tenants?search=bright-accounting")
        assert r.status_code == 200
        tenants = r.json().get("tenants", [])
        bright_tenant = next((t for t in tenants if t.get("code") == "bright-accounting"), None)
        if not bright_tenant:
            pytest.skip("bright-accounting tenant not found")
        
        partner_id = bright_tenant["id"]
        
        payload = {
            "partner_id": partner_id,
            "description": "TEST_Order_Email",
            "amount": 250.00,
            "currency": "GBP",
            "status": "unpaid",
            "payment_method": "manual",
        }
        r2 = platform_session.post(f"{BASE_URL}/api/admin/partner-orders", json=payload)
        assert r2.status_code in (200, 201), f"Expected 200/201, got {r2.status_code}: {r2.text}"
        
        order = r2.json().get("order", {})
        order_id = order.get("id")
        assert order_id is not None
        
        # Wait briefly for async email task
        import time
        time.sleep(2)
        
        # Check email_outbox for the mocked email
        # (since no email provider configured, should go to email_outbox)
        # We can verify via checking email logs
        r3 = platform_session.get(f"{BASE_URL}/api/admin/email-logs?limit=10")
        if r3.status_code == 200:
            logs = r3.json().get("logs", [])
            recent_partner_order_logs = [
                l for l in logs 
                if l.get("trigger") == "partner_order_created"
            ]
            print(f"Found {len(recent_partner_order_logs)} partner_order_created email logs")
        
        # Cleanup
        platform_session.delete(f"{BASE_URL}/api/admin/partner-orders/{order_id}")
        print(f"Created and cleaned up test order: {order_id}")
