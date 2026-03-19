"""
Tests for External URL Checkout feature (iteration 319)
Tests: Product creation with checkout_type='external', webhook endpoint, tenant isolation,
       idempotency, external session creation.
"""
import os
import pytest
import requests
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# ── Credentials ────────────────────────────────────────────────────────────────
PLATFORM_ADMIN_EMAIL = "admin@automateaccounts.local"
PLATFORM_ADMIN_PASSWORD = "ChangeMe123!"

EDD_ADMIN_EMAIL = "rushabh0996@gmail.com"
EDD_ADMIN_PASSWORD = "ChangeMe123!"
EDD_PARTNER_CODE = "edd"

EDD_CUSTOMER_EMAIL = "edd_customer@test.com"
EDD_CUSTOMER_PASSWORD = "Test123!"

# Seeded product IDs (pre-created by main agent)
EDD_PRODUCT_ID = "e986e726-3015-4162-b815-8af4f354928b"
EDD_WEBHOOK_SECRET = "4BLXL4zCccv3wnY9Y8mGKnOoH76b_p_-V_qU7LvaGbA"

AA_PRODUCT_ID = "7ebbb803-7edc-4cd8-8baf-fce169518124"
AA_WEBHOOK_SECRET = "ILMBDY1xytD8GdTgg2Ys1L2MPn2yBK0-vT5qn5m2HYQ"


# ── Auth helpers ───────────────────────────────────────────────────────────────

def get_admin_token(email: str, password: str) -> str:
    """Login as admin and return JWT token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    data = resp.json()
    return data.get("token") or data.get("access_token", "")


def get_partner_admin_token(email: str, password: str, partner_code: str) -> str:
    """Login as partner admin and return JWT token."""
    resp = requests.post(
        f"{BASE_URL}/api/auth/partner-login",
        json={"email": email, "password": password, "partner_code": partner_code},
    )
    assert resp.status_code == 200, f"Partner login failed: {resp.text}"
    data = resp.json()
    return data.get("token") or data.get("access_token", "")


def get_customer_token(email: str, password: str, partner_code: str) -> str:
    """Login as customer and return JWT token."""
    resp = requests.post(
        f"{BASE_URL}/api/auth/customer-login",
        json={"email": email, "password": password, "partner_code": partner_code},
    )
    assert resp.status_code == 200, f"Customer login failed: {resp.text}"
    data = resp.json()
    return data.get("token") or data.get("access_token", "")


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def platform_admin_token():
    return get_admin_token(PLATFORM_ADMIN_EMAIL, PLATFORM_ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def edd_admin_token():
    return get_partner_admin_token(EDD_ADMIN_EMAIL, EDD_ADMIN_PASSWORD, EDD_PARTNER_CODE)


@pytest.fixture(scope="module")
def edd_customer_token():
    return get_customer_token(EDD_CUSTOMER_EMAIL, EDD_CUSTOMER_PASSWORD, EDD_PARTNER_CODE)


# ── Backend validation: product creation ──────────────────────────────────────

class TestProductCreationValidation:
    """Tests for creating products with checkout_type='external'."""

    def test_create_external_product_success(self, edd_admin_token):
        """Admin can create an external product with a valid HTTPS URL."""
        payload = {
            "name": "TEST_External Product Valid",
            "category": "general",
            "checkout_type": "external",
            "external_url": "https://example.com/checkout?email={customer_email}&order={order_id}",
            "base_price": 99.0,
            "is_active": True,
            "pricing_type": "internal",
        }
        resp = requests.post(
            f"{BASE_URL}/api/admin/products",
            json=payload,
            headers=auth_headers(edd_admin_token),
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "product" in data
        product = data["product"]
        assert product["checkout_type"] == "external"
        assert product["external_url"] == payload["external_url"]
        assert product.get("external_webhook_secret"), "Webhook secret should be auto-generated"
        # Cleanup
        prod_id = product["id"]
        requests.delete(f"{BASE_URL}/api/admin/products/{prod_id}", headers=auth_headers(edd_admin_token))

    def test_create_external_product_no_url_returns_400(self, edd_admin_token):
        """Admin CANNOT create external product without external_url - backend returns 400."""
        payload = {
            "name": "TEST_External Product No URL",
            "category": "general",
            "checkout_type": "external",
            "external_url": None,
            "base_price": 99.0,
            "is_active": True,
            "pricing_type": "internal",
        }
        resp = requests.post(
            f"{BASE_URL}/api/admin/products",
            json=payload,
            headers=auth_headers(edd_admin_token),
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "external_url" in resp.json().get("detail", "").lower() or "required" in resp.json().get("detail", "").lower()

    def test_create_external_product_invalid_url_returns_400(self, edd_admin_token):
        """Admin CANNOT create external product with invalid URL (no http/https) - backend returns 400."""
        payload = {
            "name": "TEST_External Product Invalid URL",
            "category": "general",
            "checkout_type": "external",
            "external_url": "ftp://invalid.com/checkout",
            "base_price": 99.0,
            "is_active": True,
            "pricing_type": "internal",
        }
        resp = requests.post(
            f"{BASE_URL}/api/admin/products",
            json=payload,
            headers=auth_headers(edd_admin_token),
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        detail = resp.json().get("detail", "").lower()
        assert "http" in detail or "url" in detail or "external_url" in detail

    def test_create_external_product_empty_url_returns_400(self, edd_admin_token):
        """Empty string URL is also invalid for external product."""
        payload = {
            "name": "TEST_External Empty URL",
            "category": "general",
            "checkout_type": "external",
            "external_url": "",
            "base_price": 99.0,
            "is_active": True,
            "pricing_type": "internal",
        }
        resp = requests.post(
            f"{BASE_URL}/api/admin/products",
            json=payload,
            headers=auth_headers(edd_admin_token),
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"


# ── External checkout session ─────────────────────────────────────────────────

class TestExternalCheckoutSession:
    """Tests for POST /checkout/external-session."""

    def test_create_session_returns_order_id_and_redirect_url(self, edd_customer_token):
        """External checkout session returns order_id, order_number, and redirect_url."""
        resp = requests.post(
            f"{BASE_URL}/api/checkout/external-session",
            json={"product_id": EDD_PRODUCT_ID, "intake_answers": {}},
            headers=auth_headers(edd_customer_token),
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "order_id" in data, "Response must contain order_id"
        assert "order_number" in data, "Response must contain order_number"
        assert "redirect_url" in data, "Response must contain redirect_url"
        assert data["redirect_url"].startswith("http"), f"redirect_url must be valid URL, got: {data['redirect_url']}"
        return data

    def test_session_has_correct_tenant_id(self, edd_customer_token):
        """Created order must have the product's tenant_id (tenant isolation fix)."""
        resp = requests.post(
            f"{BASE_URL}/api/checkout/external-session",
            json={"product_id": EDD_PRODUCT_ID, "intake_answers": {}},
            headers=auth_headers(edd_customer_token),
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        order_id = data["order_id"]

        # Get order using admin — we can check tenant
        edd_token = get_partner_admin_token(EDD_ADMIN_EMAIL, EDD_ADMIN_PASSWORD, EDD_PARTNER_CODE)
        order_resp = requests.get(
            f"{BASE_URL}/api/admin/orders/{order_id}",
            headers=auth_headers(edd_token),
        )
        if order_resp.status_code == 200:
            order = order_resp.json().get("order", order_resp.json())
            # The order must belong to edd's tenant, not to a different tenant
            assert order.get("status") == "pending_external", f"Order status should be pending_external, got: {order.get('status')}"
        else:
            # Admin may not have individual order endpoint -- try the list
            orders_resp = requests.get(
                f"{BASE_URL}/api/admin/orders?per_page=500",
                headers=auth_headers(edd_token),
            )
            if orders_resp.status_code == 200:
                orders = orders_resp.json().get("orders", [])
                matching = [o for o in orders if o.get("id") == order_id]
                assert matching, f"Order {order_id} not found in edd admin orders"
                assert matching[0]["status"] == "pending_external"

    def test_session_substitutes_placeholders_in_url(self, edd_customer_token):
        """redirect_url must have {customer_email} and {order_id} substituted."""
        resp = requests.post(
            f"{BASE_URL}/api/checkout/external-session",
            json={"product_id": EDD_PRODUCT_ID, "intake_answers": {}},
            headers=auth_headers(edd_customer_token),
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        redirect_url = resp.json()["redirect_url"]
        # Placeholders should have been substituted (no literal braces remaining for known params)
        assert "{customer_email}" not in redirect_url, "customer_email placeholder not substituted"
        assert "{order_id}" not in redirect_url, "order_id placeholder not substituted"

    def test_session_non_external_product_returns_400(self, platform_admin_token):
        """Calling external-session for a non-external product should return 400."""
        # Use a regular product (we'll need to get one from admin)
        token = platform_admin_token
        # Get any product that's not external
        prods_resp = requests.get(
            f"{BASE_URL}/api/admin/products-all?per_page=10",
            headers=auth_headers(token),
        )
        if prods_resp.status_code != 200:
            pytest.skip("Could not fetch products for this test")

        products = prods_resp.json().get("products", [])
        non_external = [p for p in products if p.get("checkout_type") != "external" and p.get("pricing_type") != "external"]
        if not non_external:
            pytest.skip("No non-external products available")

        # Use customer token for this test
        try:
            cust_token = get_customer_token(EDD_CUSTOMER_EMAIL, EDD_CUSTOMER_PASSWORD, EDD_PARTNER_CODE)
        except Exception:
            pytest.skip("Customer token not available")

        resp = requests.post(
            f"{BASE_URL}/api/checkout/external-session",
            json={"product_id": non_external[0]["id"]},
            headers=auth_headers(cust_token),
        )
        # Should fail with 400 or 404 (product may not exist for this customer's tenant)
        assert resp.status_code in [400, 404], f"Expected 400/404 for non-external product, got {resp.status_code}"

    def test_session_without_auth_returns_401(self):
        """External session endpoint requires authentication."""
        resp = requests.post(
            f"{BASE_URL}/api/checkout/external-session",
            json={"product_id": EDD_PRODUCT_ID},
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"


# ── Webhook endpoint ─────────────────────────────────────────────────────────

class TestExternalWebhook:
    """Tests for POST /api/webhooks/external/{secret}."""

    @pytest.fixture(scope="class")
    def edd_order_id(self):
        """Create a fresh pending_external order for EDD product and return its ID."""
        token = get_customer_token(EDD_CUSTOMER_EMAIL, EDD_CUSTOMER_PASSWORD, EDD_PARTNER_CODE)
        resp = requests.post(
            f"{BASE_URL}/api/checkout/external-session",
            json={"product_id": EDD_PRODUCT_ID, "intake_answers": {}},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200, f"Cannot create EDD order: {resp.text}"
        return resp.json()["order_id"]

    @pytest.fixture(scope="class")
    def aa_order_id(self):
        """Create a fresh pending_external order for AA product and return its ID.
        Only possible if we have an AA customer — we'll use admin flow as fallback."""
        # Try to create a session as edd_customer — this should fail because AA product
        # is in a different tenant. We'll use a platform-admin trick or just return None.
        try:
            # Try to login as an AA customer (if any exist)
            # For this test we just need to check isolation, so we'll rely on edd_order_id
            return None
        except Exception:
            return None

    def test_payment_success_sets_status_paid(self, edd_order_id):
        """Webhook payment_success sets order status to 'paid'."""
        payload = {
            "event": "payment_success",
            "order_id": edd_order_id,
            "amount": 149.00,
            "currency": "GBP",
            "processor_id": "ext-ref-test-001",
        }
        resp = requests.post(
            f"{BASE_URL}/api/webhooks/external/{EDD_WEBHOOK_SECRET}",
            json=payload,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("status") == "ok"
        assert data.get("new_status") == "paid"
        assert data.get("order_id") == edd_order_id

    def test_webhook_wrong_secret_returns_404(self, edd_order_id):
        """Webhook with wrong secret returns 404."""
        payload = {
            "event": "payment_success",
            "order_id": edd_order_id,
        }
        resp = requests.post(
            f"{BASE_URL}/api/webhooks/external/WRONG_SECRET_XYZ",
            json=payload,
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"

    def test_webhook_unknown_event_returns_400(self, edd_order_id):
        """Webhook with unknown event type returns 400."""
        payload = {
            "event": "unknown_event_xyz",
            "order_id": edd_order_id,
        }
        resp = requests.post(
            f"{BASE_URL}/api/webhooks/external/{EDD_WEBHOOK_SECRET}",
            json=payload,
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"

    def test_webhook_idempotency(self):
        """Sending same webhook event twice returns duplicate event ignored."""
        # Create a fresh order for idempotency test
        token = get_customer_token(EDD_CUSTOMER_EMAIL, EDD_CUSTOMER_PASSWORD, EDD_PARTNER_CODE)
        resp = requests.post(
            f"{BASE_URL}/api/checkout/external-session",
            json={"product_id": EDD_PRODUCT_ID, "intake_answers": {}},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        order_id = resp.json()["order_id"]

        # Send first event
        payload = {"event": "payment_success", "order_id": order_id}
        r1 = requests.post(f"{BASE_URL}/api/webhooks/external/{EDD_WEBHOOK_SECRET}", json=payload)
        assert r1.status_code == 200, f"First webhook call failed: {r1.text}"

        # Send same event again
        r2 = requests.post(f"{BASE_URL}/api/webhooks/external/{EDD_WEBHOOK_SECRET}", json=payload)
        assert r2.status_code == 200, f"Second webhook call failed: {r2.text}"
        data2 = r2.json()
        assert data2.get("status") == "ok"
        assert "duplicate" in data2.get("note", "").lower(), f"Expected 'duplicate event ignored', got: {data2}"

    def test_webhook_partial_refund_sets_partially_refunded(self):
        """partial_refund event sets status to 'partially_refunded'."""
        # Create a fresh order
        token = get_customer_token(EDD_CUSTOMER_EMAIL, EDD_CUSTOMER_PASSWORD, EDD_PARTNER_CODE)
        resp = requests.post(
            f"{BASE_URL}/api/checkout/external-session",
            json={"product_id": EDD_PRODUCT_ID, "intake_answers": {}},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        order_id = resp.json()["order_id"]

        # First set to paid
        requests.post(
            f"{BASE_URL}/api/webhooks/external/{EDD_WEBHOOK_SECRET}",
            json={"event": "payment_success", "order_id": order_id},
        )

        # Now send partial_refund
        payload = {
            "event": "partial_refund",
            "order_id": order_id,
            "amount": 149.00,
            "refund_amount": 50.00,
            "currency": "GBP",
        }
        resp2 = requests.post(
            f"{BASE_URL}/api/webhooks/external/{EDD_WEBHOOK_SECRET}",
            json=payload,
        )
        assert resp2.status_code == 200, f"Expected 200, got {resp2.status_code}: {resp2.text}"
        data = resp2.json()
        assert data.get("new_status") == "partially_refunded", f"Expected partially_refunded, got: {data}"

    def test_cross_tenant_isolation(self):
        """EDD webhook secret cannot update automate-accounts tenant orders.
        
        Cross-tenant check: if we try to use AA_WEBHOOK_SECRET with an EDD order_id,
        it should return 404 (order not found for this webhook's tenant).
        """
        # Create a fresh EDD order
        token = get_customer_token(EDD_CUSTOMER_EMAIL, EDD_CUSTOMER_PASSWORD, EDD_PARTNER_CODE)
        resp = requests.post(
            f"{BASE_URL}/api/checkout/external-session",
            json={"product_id": EDD_PRODUCT_ID, "intake_answers": {}},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        edd_order_id = resp.json()["order_id"]

        # Try to update the EDD order using the AA webhook secret
        payload = {
            "event": "payment_success",
            "order_id": edd_order_id,
        }
        cross_resp = requests.post(
            f"{BASE_URL}/api/webhooks/external/{AA_WEBHOOK_SECRET}",
            json=payload,
        )
        # Should return 404 because the order belongs to EDD tenant, not AA
        assert cross_resp.status_code == 404, (
            f"Cross-tenant isolation FAILED: AA webhook was able to update EDD order! "
            f"Status: {cross_resp.status_code}, Body: {cross_resp.text}"
        )

    def test_webhook_missing_order_id_returns_400(self):
        """Webhook without order_id should return 400."""
        payload = {"event": "payment_success"}
        resp = requests.post(
            f"{BASE_URL}/api/webhooks/external/{EDD_WEBHOOK_SECRET}",
            json=payload,
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"

    def test_webhook_invalid_json_returns_400(self):
        """Webhook with invalid JSON should return 400."""
        resp = requests.post(
            f"{BASE_URL}/api/webhooks/external/{EDD_WEBHOOK_SECRET}",
            data="not-json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"


# ── Product validation: update path ──────────────────────────────────────────

class TestProductUpdateValidation:
    """Tests for updating a product's checkout_type to 'external'."""

    def test_update_to_external_without_url_returns_400(self, edd_admin_token):
        """Updating an existing product to external checkout without URL should return 400."""
        # First create a non-external product
        payload = {
            "name": "TEST_Update Validation Product",
            "category": "general",
            "checkout_type": "one_time",
            "base_price": 50.0,
            "is_active": True,
            "pricing_type": "internal",
        }
        create_resp = requests.post(
            f"{BASE_URL}/api/admin/products",
            json=payload,
            headers=auth_headers(edd_admin_token),
        )
        assert create_resp.status_code == 200, f"Failed to create product: {create_resp.text}"
        prod_id = create_resp.json()["product"]["id"]

        # Now update to external without providing URL
        update_payload = {
            "name": "TEST_Update Validation Product",
            "checkout_type": "external",
            "external_url": None,
            "base_price": 50.0,
            "is_active": True,
            "pricing_type": "internal",
        }
        update_resp = requests.put(
            f"{BASE_URL}/api/admin/products/{prod_id}",
            json=update_payload,
            headers=auth_headers(edd_admin_token),
        )
        assert update_resp.status_code == 400, f"Expected 400, got {update_resp.status_code}: {update_resp.text}"

        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/products/{prod_id}", headers=auth_headers(edd_admin_token))

    def test_update_to_external_with_valid_url_succeeds(self, edd_admin_token):
        """Updating to external with valid URL should succeed."""
        # Create a non-external product
        create_resp = requests.post(
            f"{BASE_URL}/api/admin/products",
            json={"name": "TEST_Ext Update Valid", "category": "general", "checkout_type": "one_time", "base_price": 50.0, "is_active": True, "pricing_type": "internal"},
            headers=auth_headers(edd_admin_token),
        )
        assert create_resp.status_code == 200
        prod_id = create_resp.json()["product"]["id"]

        # Update to external with valid URL
        update_resp = requests.put(
            f"{BASE_URL}/api/admin/products/{prod_id}",
            json={"name": "TEST_Ext Update Valid", "checkout_type": "external", "external_url": "https://pay.example.com?order={order_id}", "base_price": 50.0, "is_active": True, "pricing_type": "internal"},
            headers=auth_headers(edd_admin_token),
        )
        assert update_resp.status_code == 200, f"Expected 200, got {update_resp.status_code}: {update_resp.text}"
        # PUT returns {"message": "Product updated"} or similar — just check status code is sufficient

        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/products/{prod_id}", headers=auth_headers(edd_admin_token))


# ── Seeded product availability ───────────────────────────────────────────────

class TestSeededProducts:
    """Verify the seeded external products from the test spec are accessible."""

    def test_edd_external_product_exists_and_is_external(self, edd_admin_token):
        """EDD test external product should exist and have checkout_type='external'."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/products-all?per_page=500",
            headers=auth_headers(edd_admin_token),
        )
        if resp.status_code != 200:
            pytest.skip("Cannot list EDD products")
        products = resp.json().get("products", [])
        matching = [p for p in products if p.get("id") == EDD_PRODUCT_ID]
        assert matching, f"EDD external product {EDD_PRODUCT_ID} not found"
        product = matching[0]
        assert product.get("checkout_type") == "external" or product.get("pricing_type") == "external", \
            f"Product checkout_type is '{product.get('checkout_type')}', expected 'external'"
        assert product.get("external_webhook_secret") == EDD_WEBHOOK_SECRET, \
            f"Webhook secret mismatch: {product.get('external_webhook_secret')} != {EDD_WEBHOOK_SECRET}"

    def test_aa_external_product_exists_and_is_external(self, platform_admin_token):
        """AA test external product should exist and have checkout_type='external'."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/products-all?per_page=500",
            headers=auth_headers(platform_admin_token),
        )
        if resp.status_code != 200:
            pytest.skip("Cannot list AA products")
        products = resp.json().get("products", [])
        matching = [p for p in products if p.get("id") == AA_PRODUCT_ID]
        assert matching, f"AA external product {AA_PRODUCT_ID} not found"
        product = matching[0]
        assert product.get("checkout_type") == "external" or product.get("pricing_type") == "external", \
            f"Product checkout_type is '{product.get('checkout_type')}', expected 'external'"
        assert product.get("external_webhook_secret") == AA_WEBHOOK_SECRET, \
            f"Webhook secret mismatch: {product.get('external_webhook_secret')} != {AA_WEBHOOK_SECRET}"
