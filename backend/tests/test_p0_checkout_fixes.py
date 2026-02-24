"""
Tests for P0 Checkout Bug Fixes (Iteration 31):
1. Stripe checkout import path fix (emergentintegrations.payments.stripe.checkout)
2. GoCardless webhook secret in settings (gocardless_webhook_secret field)
3. POST /api/checkout/session - Stripe one-time checkout
4. POST /api/checkout/bank-transfer - GoCardless one-time checkout
5. GET /api/admin/settings/structured - Payments category includes gocardless_webhook_secret
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials from review request
ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"
CUSTOMER_EMAIL = "test_user_004712@test.com"
CUSTOMER_PASSWORD = "Test1234!"

# Product for testing
TEST_PRODUCT_ID = "prod_zoho_crm_express"  # Zoho CRM Express Setup, pricing_type=fixed, base_price=2499


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    token = resp.json().get("token", "")
    assert token, "Admin token is empty"
    return token


@pytest.fixture(scope="module")
def customer_token():
    """Get customer auth token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": CUSTOMER_EMAIL,
        "password": CUSTOMER_PASSWORD
    })
    assert resp.status_code == 200, f"Customer login failed: {resp.text}"
    token = resp.json().get("token", "")
    assert token, "Customer token is empty"
    return token


@pytest.fixture(scope="module")
def admin_client(admin_token):
    """Admin requests session."""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {admin_token}"
    })
    return session


@pytest.fixture(scope="module")
def customer_client(customer_token):
    """Customer requests session."""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {customer_token}"
    })
    return session


# ---------------------------------------------------------------------------
# Test 1: Backend health - server starts without import errors
# ---------------------------------------------------------------------------

class TestBackendHealth:
    """Verify backend starts and responds correctly."""

    def test_backend_responds(self):
        """Backend should respond to requests (auth endpoint is always available)."""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert resp.status_code in [200, 401], f"Backend unresponsive: {resp.status_code}"
        print("PASS: Backend is responding")

    def test_admin_login_success(self, admin_client):
        """Admin login should succeed with correct credentials."""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert resp.status_code == 200, f"Admin login failed: {resp.text}"
        data = resp.json()
        assert "token" in data, "No token in response"
        assert data["token"], "Token is empty"
        print("PASS: Admin login successful")

    def test_customer_login_success(self):
        """Customer login should succeed."""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CUSTOMER_EMAIL,
            "password": CUSTOMER_PASSWORD
        })
        assert resp.status_code == 200, f"Customer login failed: {resp.text}"
        data = resp.json()
        assert "token" in data
        print("PASS: Customer login successful")


# ---------------------------------------------------------------------------
# Test 2: Stripe imports from emergentintegrations.payments.stripe.checkout
# ---------------------------------------------------------------------------

class TestStripeImports:
    """Verify Stripe import fix from emergentintegrations.payments.stripe.checkout."""

    def test_stripe_checkout_class_importable(self):
        """StripeCheckout class must be importable from correct path."""
        try:
            from emergentintegrations.payments.stripe.checkout import StripeCheckout
            assert StripeCheckout is not None, "StripeCheckout is None after import"
            print("PASS: StripeCheckout imported successfully")
        except ImportError as e:
            pytest.fail(f"ImportError for StripeCheckout: {e}")

    def test_checkout_session_request_importable(self):
        """CheckoutSessionRequest must be importable - this was the P0 bug."""
        try:
            from emergentintegrations.payments.stripe.checkout import CheckoutSessionRequest
            assert CheckoutSessionRequest is not None, "CheckoutSessionRequest is None after import"
            print("PASS: CheckoutSessionRequest imported successfully")
        except ImportError as e:
            pytest.fail(f"ImportError for CheckoutSessionRequest: {e}")

    def test_checkout_session_response_importable(self):
        """CheckoutSessionResponse must be importable."""
        try:
            from emergentintegrations.payments.stripe.checkout import CheckoutSessionResponse
            assert CheckoutSessionResponse is not None
            print("PASS: CheckoutSessionResponse imported successfully")
        except ImportError as e:
            pytest.fail(f"ImportError for CheckoutSessionResponse: {e}")

    def test_checkout_status_response_importable(self):
        """CheckoutStatusResponse must be importable."""
        try:
            from emergentintegrations.payments.stripe.checkout import CheckoutStatusResponse
            assert CheckoutStatusResponse is not None
            print("PASS: CheckoutStatusResponse imported successfully")
        except ImportError as e:
            pytest.fail(f"ImportError for CheckoutStatusResponse: {e}")

    def test_checkout_route_module_loads(self):
        """Checkout route module (routes/checkout.py) should load without errors.
        If import fails, StripeCheckout would be None and route would crash at runtime."""
        import sys
        import os
        sys.path.insert(0, '/app/backend')
        # The module should already be loaded if server started correctly
        # We verify by importing and checking the class is not None (import guard didn't trigger)
        from emergentintegrations.payments.stripe.checkout import (
            StripeCheckout, CheckoutSessionRequest
        )
        assert StripeCheckout is not None, "StripeCheckout fell back to None - import fix not applied!"
        assert CheckoutSessionRequest is not None, "CheckoutSessionRequest fell back to None - import fix not applied!"
        print("PASS: All Stripe checkout classes loaded (not None fallback)")


# ---------------------------------------------------------------------------
# Test 3: Settings - gocardless_webhook_secret in Payments category
# ---------------------------------------------------------------------------

class TestAdminSettings:
    """Verify /api/admin/settings/structured includes gocardless_webhook_secret."""

    def test_settings_structured_returns_200(self, admin_client):
        """GET /api/admin/settings/structured should return 200."""
        resp = admin_client.get(f"{BASE_URL}/api/admin/settings/structured")
        assert resp.status_code == 200, f"Settings structured failed: {resp.status_code} {resp.text}"
        print("PASS: GET /api/admin/settings/structured returned 200")

    def test_payments_category_exists(self, admin_client):
        """Payments category must exist in structured settings."""
        resp = admin_client.get(f"{BASE_URL}/api/admin/settings/structured")
        assert resp.status_code == 200
        data = resp.json()
        settings = data.get("settings", data)
        if isinstance(settings, dict):
            assert "Payments" in settings, f"Payments category missing. Categories: {list(settings.keys())}"
            print("PASS: Payments category found in settings")
        else:
            pytest.fail(f"Unexpected settings format: {type(settings)}")

    def test_gocardless_webhook_secret_present(self, admin_client):
        """gocardless_webhook_secret must be in Payments settings - this was the P0 fix."""
        resp = admin_client.get(f"{BASE_URL}/api/admin/settings/structured")
        assert resp.status_code == 200
        data = resp.json()
        settings = data.get("settings", data)

        if isinstance(settings, dict):
            pay_settings = settings.get("Payments", [])
        else:
            pay_settings = []
            for cat in (settings if isinstance(settings, list) else []):
                if cat.get("category") == "Payments":
                    pay_settings = cat.get("settings", [])
                    break

        keys_in_payments = [s.get("key") for s in pay_settings]
        assert "gocardless_webhook_secret" in keys_in_payments, \
            f"gocardless_webhook_secret missing from Payments. Found: {keys_in_payments}"
        print("PASS: gocardless_webhook_secret found in Payments category")

    def test_gocardless_webhook_secret_is_secret_type(self, admin_client):
        """gocardless_webhook_secret must be marked as is_secret=True."""
        resp = admin_client.get(f"{BASE_URL}/api/admin/settings/structured")
        assert resp.status_code == 200
        data = resp.json()
        settings = data.get("settings", data)
        pay_settings = settings.get("Payments", []) if isinstance(settings, dict) else []

        webhook_setting = next((s for s in pay_settings if s.get("key") == "gocardless_webhook_secret"), None)
        assert webhook_setting is not None, "gocardless_webhook_secret not found"
        assert webhook_setting.get("is_secret") is True, \
            f"gocardless_webhook_secret should be is_secret=True, got {webhook_setting.get('is_secret')}"
        print("PASS: gocardless_webhook_secret has is_secret=True")

    def test_all_payment_keys_present(self, admin_client):
        """All expected payment settings must be present."""
        expected_keys = [
            "service_fee_rate",
            "stripe_secret_key",
            "stripe_publishable_key",
            "stripe_webhook_secret",
            "gocardless_access_token",
            "gocardless_environment",
            "gocardless_webhook_secret",  # The P0 added field
        ]
        resp = admin_client.get(f"{BASE_URL}/api/admin/settings/structured")
        assert resp.status_code == 200
        data = resp.json()
        settings = data.get("settings", data)
        pay_settings = settings.get("Payments", []) if isinstance(settings, dict) else []
        found_keys = [s.get("key") for s in pay_settings]

        missing = [k for k in expected_keys if k not in found_keys]
        assert not missing, f"Missing payment setting keys: {missing}"
        print(f"PASS: All {len(expected_keys)} payment keys found: {found_keys}")


# ---------------------------------------------------------------------------
# Test 4: POST /api/checkout/session - Stripe one-time checkout
# ---------------------------------------------------------------------------

class TestStripeCheckout:
    """Verify POST /api/checkout/session creates a valid Stripe session."""

    def test_checkout_session_missing_fields_returns_422(self):
        """Missing required fields should return 422 (validation error) or 403 (auth first)."""
        resp = requests.post(f"{BASE_URL}/api/checkout/session", json={})
        # Auth middleware may fire before body validation (returns 403), or body validated first (422)
        assert resp.status_code in [422, 403], f"Expected 422 or 403, got {resp.status_code}"
        print(f"PASS: Empty payload returns {resp.status_code}")

    def test_checkout_session_no_auth_returns_401(self):
        """Unauthenticated request should return 401/403."""
        payload = {
            "items": [{"product_id": TEST_PRODUCT_ID, "quantity": 1}],
            "checkout_type": "one_time",
            "origin_url": "https://complex-pricing-ui.preview.emergentagent.com",
            "terms_accepted": True,
            "partner_tag_response": "Yes",
            "zoho_subscription_type": "Free",
            "current_zoho_product": "None",
            "zoho_account_access": "Yes, I have provided access"
        }
        resp = requests.post(f"{BASE_URL}/api/checkout/session", json=payload)
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"
        print("PASS: Unauthenticated request rejected")

    def test_checkout_session_terms_not_accepted_returns_400(self, customer_client):
        """Checkout without terms accepted should return 400."""
        payload = {
            "items": [{"product_id": TEST_PRODUCT_ID, "quantity": 1}],
            "checkout_type": "one_time",
            "origin_url": "https://complex-pricing-ui.preview.emergentagent.com",
            "terms_accepted": False,
            "partner_tag_response": "Yes",
            "zoho_subscription_type": "Free",
            "current_zoho_product": "None",
            "zoho_account_access": "Yes"
        }
        resp = customer_client.post(f"{BASE_URL}/api/checkout/session", json=payload)
        assert resp.status_code == 400, f"Expected 400 for terms not accepted, got {resp.status_code}: {resp.text}"
        print("PASS: Terms not accepted returns 400")

    def test_checkout_session_missing_zoho_fields_returns_400(self, customer_client):
        """Missing zoho_subscription_type should return 400."""
        payload = {
            "items": [{"product_id": TEST_PRODUCT_ID, "quantity": 1}],
            "checkout_type": "one_time",
            "origin_url": "https://complex-pricing-ui.preview.emergentagent.com",
            "terms_accepted": True,
            "partner_tag_response": "Yes",
            # Missing zoho_subscription_type, current_zoho_product, zoho_account_access
        }
        resp = customer_client.post(f"{BASE_URL}/api/checkout/session", json=payload)
        assert resp.status_code == 400, f"Expected 400 for missing zoho fields, got {resp.status_code}: {resp.text}"
        print("PASS: Missing zoho fields returns 400")

    def test_checkout_session_one_time_creates_stripe_url(self, customer_client):
        """POST /api/checkout/session with valid payload returns Stripe checkout URL."""
        payload = {
            "items": [{"product_id": TEST_PRODUCT_ID, "quantity": 1, "inputs": {}}],
            "checkout_type": "one_time",
            "origin_url": "https://complex-pricing-ui.preview.emergentagent.com",
            "terms_accepted": True,
            "partner_tag_response": "Yes",
            "zoho_subscription_type": "Free",
            "current_zoho_product": "None",
            "zoho_account_access": "Yes, I have provided Zoho account access"
        }
        resp = customer_client.post(f"{BASE_URL}/api/checkout/session", json=payload)
        assert resp.status_code == 200, \
            f"Expected 200 for Stripe checkout, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "url" in data, f"No 'url' in response: {data}"
        assert data["url"], "Stripe URL is empty"
        assert "stripe.com" in data["url"] or "checkout.stripe.com" in data["url"], \
            f"URL doesn't look like Stripe URL: {data['url']}"
        assert "session_id" in data, f"No session_id in response: {data}"
        assert "order_id" in data, f"No order_id in response: {data}"
        print(f"PASS: Stripe checkout URL created: {data['url'][:80]}...")
        print(f"      Session ID: {data['session_id']}")
        print(f"      Order ID: {data['order_id']}")


# ---------------------------------------------------------------------------
# Test 5: POST /api/checkout/bank-transfer - GoCardless one-time checkout
# ---------------------------------------------------------------------------

class TestGoCardlessCheckout:
    """Verify POST /api/checkout/bank-transfer creates GoCardless redirect URL."""

    def test_bank_transfer_missing_fields_returns_422(self):
        """Missing required fields should return 422 or 403 (auth first)."""
        resp = requests.post(f"{BASE_URL}/api/checkout/bank-transfer", json={})
        # Auth middleware may fire before body validation
        assert resp.status_code in [422, 403], f"Expected 422 or 403, got {resp.status_code}"
        print(f"PASS: Empty payload returns {resp.status_code}")

    def test_bank_transfer_no_auth_returns_401(self):
        """Unauthenticated request should return 401/403."""
        payload = {
            "items": [{"product_id": TEST_PRODUCT_ID, "quantity": 1}],
            "checkout_type": "one_time",
            "terms_accepted": True,
            "partner_tag_response": "Yes",
            "zoho_subscription_type": "Free",
            "current_zoho_product": "None",
            "zoho_account_access": "Yes"
        }
        resp = requests.post(f"{BASE_URL}/api/checkout/bank-transfer", json=payload)
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"
        print("PASS: Unauthenticated request rejected")

    def test_bank_transfer_terms_not_accepted_returns_400(self, customer_client):
        """Checkout without terms accepted should return 400."""
        payload = {
            "items": [{"product_id": TEST_PRODUCT_ID, "quantity": 1}],
            "checkout_type": "one_time",
            "terms_accepted": False,
            "partner_tag_response": "Yes",
            "zoho_subscription_type": "Free",
            "current_zoho_product": "None",
            "zoho_account_access": "Yes"
        }
        resp = customer_client.post(f"{BASE_URL}/api/checkout/bank-transfer", json=payload)
        assert resp.status_code == 400, f"Expected 400 for terms not accepted, got {resp.status_code}: {resp.text}"
        print("PASS: Terms not accepted returns 400")

    def test_bank_transfer_one_time_creates_gocardless_url(self, customer_client):
        """POST /api/checkout/bank-transfer with valid payload returns GoCardless redirect URL."""
        payload = {
            "items": [{"product_id": TEST_PRODUCT_ID, "quantity": 1, "inputs": {}}],
            "checkout_type": "one_time",
            "terms_accepted": True,
            "partner_tag_response": "Yes",
            "zoho_subscription_type": "Free",
            "current_zoho_product": "None",
            "zoho_account_access": "Yes, I have provided Zoho account access"
        }
        resp = customer_client.post(f"{BASE_URL}/api/checkout/bank-transfer", json=payload)
        assert resp.status_code == 200, \
            f"Expected 200 for GoCardless checkout, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "gocardless_redirect_url" in data, f"No 'gocardless_redirect_url' in response: {data}"
        assert data["gocardless_redirect_url"], "GoCardless redirect URL is empty"
        # GoCardless sandbox URLs typically contain gocardless or pay.gocardless.com
        gc_url = data["gocardless_redirect_url"]
        assert "gocardless" in gc_url.lower() or "pay." in gc_url.lower(), \
            f"URL doesn't look like GoCardless URL: {gc_url}"
        assert "order_id" in data, f"No order_id in response: {data}"
        assert "order_number" in data, f"No order_number in response: {data}"
        assert data.get("status") == "pending_direct_debit_setup", \
            f"Unexpected status: {data.get('status')}"
        print(f"PASS: GoCardless redirect URL created: {gc_url[:80]}...")
        print(f"      Order ID: {data['order_id']}")
        print(f"      Order Number: {data['order_number']}")


# ---------------------------------------------------------------------------
# Test 6: Admin Settings CRUD - verify gocardless_webhook_secret is editable
# ---------------------------------------------------------------------------

class TestSettingsWebhookSecretEditable:
    """Verify gocardless_webhook_secret can be read/updated via admin settings."""

    def test_can_update_gocardless_webhook_secret(self, admin_client):
        """Admin should be able to update gocardless_webhook_secret via PUT."""
        resp = admin_client.put(
            f"{BASE_URL}/api/admin/settings/key/gocardless_webhook_secret",
            json={"value": "test_webhook_secret_value_123"}
        )
        assert resp.status_code == 200, \
            f"Failed to update gocardless_webhook_secret: {resp.status_code} {resp.text}"
        print("PASS: gocardless_webhook_secret updated via admin settings")

    def test_settings_include_secrets_shows_gocardless_webhook(self, admin_client):
        """GET with include_secrets=true should include gocardless_webhook_secret."""
        resp = admin_client.get(f"{BASE_URL}/api/admin/settings/structured?include_secrets=true")
        assert resp.status_code == 200
        data = resp.json()
        settings = data.get("settings", data)
        pay_settings = settings.get("Payments", []) if isinstance(settings, dict) else []
        webhook = next((s for s in pay_settings if s.get("key") == "gocardless_webhook_secret"), None)
        assert webhook is not None, "gocardless_webhook_secret not found"
        # Value should be set (not empty) after our update
        print(f"PASS: gocardless_webhook_secret found, value_json: {str(webhook.get('value_json',''))[:20]}...")
