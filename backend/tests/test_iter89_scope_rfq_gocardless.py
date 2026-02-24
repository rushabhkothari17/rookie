"""
Backend tests for iteration 89:
1. Scope ID Flow: Product page CTA behavior for zero-price products
2. Cart Quote Request: /api/products/request-quote endpoint
3. GoCardless: scheme_currency_map & currency fix (code logic verification)
4. GoCardless retry: mandate stored on failure for retry
5. Regression: Admin portal, store, cart checkout
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_CREDENTIALS = {
    "email": "admin@automateaccounts.local",
    "password": "ChangeMe123!",
    "partner_code": "automate-accounts",
}
CUSTOMER_CREDENTIALS = {
    "email": "testcustomer@test.com",
    "password": "ChangeMe123!",
    "partner_code": "automate-accounts",
}
# The test RFQ product with base_price=0
RFQ_PRODUCT_ID = "1d8c7a75-a957-435d-92d3-c0809a94b36d"


@pytest.fixture(scope="module")
def admin_token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDENTIALS)
    if resp.status_code == 200:
        data = resp.json()
        return data.get("access_token") or data.get("token")
    pytest.skip(f"Admin login failed: {resp.status_code} {resp.text}")


@pytest.fixture(scope="module")
def customer_token():
    resp = requests.post(
        f"{BASE_URL}/api/auth/customer-login", json=CUSTOMER_CREDENTIALS
    )
    if resp.status_code == 200:
        data = resp.json()
        return data.get("access_token") or data.get("token")
    pytest.skip(f"Customer login failed: {resp.status_code} {resp.text}")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def customer_headers(customer_token):
    return {"Authorization": f"Bearer {customer_token}"}


# ── Auth Tests ─────────────────────────────────────────────────────────────

class TestCustomerAuth:
    """Test customer login endpoint."""

    def test_customer_login_with_partner_code(self):
        """Customer can login with partner_code=automate-accounts."""
        resp = requests.post(
            f"{BASE_URL}/api/auth/customer-login", json=CUSTOMER_CREDENTIALS
        )
        assert resp.status_code == 200, f"Customer login failed: {resp.status_code} {resp.text}"
        data = resp.json()
        token = data.get("access_token") or data.get("token")
        assert token, "No token returned from customer login"
        print(f"PASS: Customer login success, token prefix: {token[:20]}...")

    def test_customer_login_wrong_credentials(self):
        """Customer login fails with wrong password."""
        resp = requests.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={"email": "testcustomer@test.com", "password": "wrongpass", "partner_code": "automate-accounts"},
        )
        assert resp.status_code in [401, 400], f"Expected 401/400, got {resp.status_code}"
        print(f"PASS: Wrong credentials returns {resp.status_code}")


# ── Product Detail (RFQ Product) Tests ────────────────────────────────────

class TestRFQProductDetail:
    """Test RFQ product API - zero-price product behavior."""

    def test_rfq_product_exists(self, customer_headers):
        """Test that the RFQ product exists and has base_price=0."""
        resp = requests.get(
            f"{BASE_URL}/api/products/{RFQ_PRODUCT_ID}",
            headers=customer_headers,
        )
        assert resp.status_code == 200, f"Product not found: {resp.status_code} {resp.text}"
        data = resp.json()
        product = data.get("product", {})
        assert product.get("id") == RFQ_PRODUCT_ID
        base_price = product.get("base_price")
        pricing_type = product.get("pricing_type")
        print(f"PASS: Product found - name='{product.get('name')}', base_price={base_price}, pricing_type={pricing_type}")
        # For the RFQ flow, we need base_price=0 (or pricing_type=fixed with 0 price)
        assert base_price == 0.0 or base_price == 0, f"Expected base_price=0, got {base_price}"

    def test_rfq_product_pricing_calc(self, customer_headers):
        """Pricing calc should return total=0 for zero-price product."""
        resp = requests.post(
            f"{BASE_URL}/api/pricing/calc",
            json={"product_id": RFQ_PRODUCT_ID, "inputs": {}},
            headers=customer_headers,
        )
        assert resp.status_code == 200, f"Pricing calc failed: {resp.status_code} {resp.text}"
        data = resp.json()
        total = data.get("total", -1)
        is_scope_request = data.get("is_scope_request", False)
        print(f"PASS: Pricing calc - total={total}, is_scope_request={is_scope_request}")
        # For the isRFQ condition to be true: pricing.total === 0 and !is_scope_request
        assert total == 0, f"Expected total=0 for RFQ product, got {total}"
        assert not is_scope_request, "RFQ product should not have is_scope_request=true"


# ── Cart Preview RFQ Bucket Tests ─────────────────────────────────────────

class TestCartPreviewRFQ:
    """Test cart preview groups zero-price items into RFQ bucket."""

    def test_cart_preview_with_rfq_item(self, customer_headers):
        """Cart preview includes RFQ bucket for zero-price fixed items."""
        resp = requests.post(
            f"{BASE_URL}/api/orders/preview",
            json={
                "items": [
                    {"product_id": RFQ_PRODUCT_ID, "quantity": 1, "inputs": {}}
                ]
            },
            headers=customer_headers,
        )
        assert resp.status_code == 200, f"Preview failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "items" in data, "Preview response should have 'items'"
        items = data["items"]
        assert len(items) >= 1, "Preview should have at least one item"
        # Check the RFQ item
        rfq_item = next((i for i in items if i["product"]["id"] == RFQ_PRODUCT_ID), None)
        assert rfq_item is not None, f"RFQ product not found in preview items"
        pricing = rfq_item.get("pricing", {})
        subtotal = pricing.get("subtotal", -1)
        is_scope_request = pricing.get("is_scope_request", False)
        print(f"PASS: RFQ item in preview - subtotal={subtotal}, is_scope_request={is_scope_request}")
        # For the grouped.rfq bucket: subtotal === 0 AND !inputs._scope_unlock AND !is_scope_request
        assert subtotal == 0, f"RFQ item should have subtotal=0, got {subtotal}"
        assert not is_scope_request, "Should not be scope_request"


# ── Quote Request API Tests ──────────────────────────────────────────────

class TestQuoteRequestAPI:
    """Test /api/products/request-quote endpoint."""

    def test_request_quote_requires_auth(self):
        """Quote request endpoint requires authentication."""
        resp = requests.post(
            f"{BASE_URL}/api/products/request-quote",
            json={
                "product_id": RFQ_PRODUCT_ID,
                "product_name": "Test Product",
                "name": "John Doe",
                "email": "john@test.com",
            },
        )
        assert resp.status_code in [401, 403], f"Expected auth error, got {resp.status_code}"
        print(f"PASS: Quote request requires auth - {resp.status_code}")

    def test_request_quote_success(self, customer_headers):
        """Customer can submit a quote request for a zero-price product."""
        resp = requests.post(
            f"{BASE_URL}/api/products/request-quote",
            json={
                "product_id": RFQ_PRODUCT_ID,
                "product_name": "TEST_RFQ Product Quote",
                "name": "TEST_John Doe",
                "email": "TEST_john@test.com",
                "company": "TEST_Company",
                "phone": "+1 555 000 0000",
                "message": "TEST_Please quote for this product",
            },
            headers=customer_headers,
        )
        assert resp.status_code == 200, f"Quote request failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "quote_id" in data or "message" in data, f"Unexpected response: {data}"
        print(f"PASS: Quote request submitted - {data.get('message', '')[:60]}")

    def test_request_quote_missing_name(self, customer_headers):
        """Quote request fails with missing required fields (Pydantic validation)."""
        resp = requests.post(
            f"{BASE_URL}/api/products/request-quote",
            json={
                "product_id": RFQ_PRODUCT_ID,
                "product_name": "Test Product",
                # name is missing - but may be optional in Pydantic model
                "email": "test@test.com",
            },
            headers=customer_headers,
        )
        # Depends on QuoteRequest model - may be 200 or 422
        print(f"INFO: Quote request missing name - {resp.status_code}: {resp.text[:100]}")
        assert resp.status_code in [200, 422], f"Unexpected status: {resp.status_code}"


# ── GoCardless Currency Fix Tests ─────────────────────────────────────────

class TestGoCardlessCurrencyFix:
    """Verify GoCardless currency fix code logic."""

    def test_gocardless_route_file_has_scheme_currency_map(self):
        """Verify gocardless.py has the scheme_currency_map dictionary."""
        with open("/app/backend/routes/gocardless.py", "r") as f:
            content = f.read()
        assert "scheme_currency_map" in content, "scheme_currency_map not found in gocardless.py"
        assert '"pad": "CAD"' in content or "'pad': 'CAD'" in content, "pad->CAD mapping missing"
        assert '"bacs": "GBP"' in content or "'bacs': 'GBP'" in content, "bacs->GBP mapping missing"
        assert '"ach": "USD"' in content or "'ach': 'USD'" in content, "ach->USD mapping missing"
        print("PASS: scheme_currency_map exists with pad=CAD, bacs=GBP, ach=USD")

    def test_gocardless_payment_currency_uses_scheme_map(self):
        """Verify payment_currency is derived from scheme map, not order currency."""
        with open("/app/backend/routes/gocardless.py", "r") as f:
            content = f.read()
        # Check that payment_currency is derived from scheme_currency_map, not from order directly
        assert "payment_currency = scheme_currency_map.get(scheme" in content, \
            "payment_currency should use scheme_currency_map.get(scheme, ...)"
        # Check it uses scheme map for subscription too
        assert "scheme_currency_map.get(scheme," in content, \
            "Subscription should also use scheme_currency_map"
        print("PASS: payment_currency correctly uses scheme_currency_map.get(scheme, ...)")

    def test_gocardless_retry_logic_on_failed_redirect(self):
        """Verify retry logic when redirect_flow returns None."""
        with open("/app/backend/routes/gocardless.py", "r") as f:
            content = f.read()
        # Check for retry logic
        assert "stored_mandate_id" in content, "Retry logic: stored_mandate_id variable missing"
        assert "gocardless_scheme" in content, "Retry logic: should store gocardless_scheme"
        assert 'redirect_flow = {"links": {"mandate": stored_mandate_id}' in content, \
            "Retry should reconstruct redirect_flow from stored mandate"
        print("PASS: Retry logic present - checks stored mandate_id when redirect_flow returns None")

    def test_gocardless_complete_redirect_requires_auth(self):
        """GoCardless complete-redirect requires authentication."""
        resp = requests.post(
            f"{BASE_URL}/api/gocardless/complete-redirect",
            json={
                "redirect_flow_id": "RE_FAKE",
                "session_token": "fake",
                "order_id": "ORD-FAKE",
            },
        )
        assert resp.status_code in [401, 403, 422], f"Expected auth error, got {resp.status_code}"
        print(f"PASS: GoCardless complete-redirect requires auth - {resp.status_code}")

    def test_gocardless_idempotency_check_exists(self):
        """Verify idempotency check is present in gocardless.py."""
        with open("/app/backend/routes/gocardless.py", "r") as f:
            content = f.read()
        assert "gocardless_payment_id" in content, "Idempotency check: gocardless_payment_id check missing"
        assert "payment_created" in content, "Idempotency response should include payment_created"
        print("PASS: Idempotency check for gocardless_payment_id is present")


# ── Regression Tests ─────────────────────────────────────────────────────

class TestRegression:
    """Regression tests for store page, admin portal, and cart checkout."""

    def test_store_products_load(self, customer_headers):
        """Store products API returns valid products list."""
        resp = requests.get(f"{BASE_URL}/api/products", headers=customer_headers)
        assert resp.status_code == 200, f"Products list failed: {resp.status_code}"
        data = resp.json()
        assert "products" in data
        products = data["products"]
        assert len(products) > 0, "Expected at least one product in store"
        print(f"PASS: Store has {len(products)} products")

    def test_admin_portal_loads(self, admin_headers):
        """Admin portal API endpoints work."""
        resp = requests.get(f"{BASE_URL}/api/admin/customers", headers=admin_headers)
        assert resp.status_code == 200, f"Admin customers failed: {resp.status_code}"
        print(f"PASS: Admin portal - customers endpoint working")

    def test_cart_checkout_priced_item_bank_transfer(self, customer_headers):
        """Checkout with priced item (bank transfer) should not return 500."""
        # Get a priced product
        resp = requests.get(f"{BASE_URL}/api/products", headers=customer_headers)
        products = resp.json().get("products", [])
        priced = next(
            (p for p in products if p.get("pricing_type") == "fixed" and (p.get("base_price") or 0) > 0),
            None,
        )
        if not priced:
            pytest.skip("No priced fixed product found")

        # Test preview (not actual checkout - no terms to accept)
        resp2 = requests.post(
            f"{BASE_URL}/api/orders/preview",
            json={"items": [{"product_id": priced["id"], "quantity": 1, "inputs": {}}]},
            headers=customer_headers,
        )
        assert resp2.status_code == 200, f"Preview failed: {resp2.status_code}"
        data = resp2.json()
        items = data.get("items", [])
        # Find our item
        priced_item = next((i for i in items if i["product"]["id"] == priced["id"]), None)
        assert priced_item is not None
        subtotal = priced_item["pricing"]["subtotal"]
        assert subtotal > 0, f"Expected non-zero subtotal, got {subtotal}"
        print(f"PASS: Priced item '{priced['name']}' preview - subtotal=${subtotal}")

    def test_orders_preview_empty_cart(self, customer_headers):
        """Empty cart preview returns 400 or empty."""
        resp = requests.post(
            f"{BASE_URL}/api/orders/preview",
            json={"items": []},
            headers=customer_headers,
        )
        assert resp.status_code in [200, 400], f"Unexpected: {resp.status_code}"
        print(f"PASS: Empty cart preview - {resp.status_code}")

    def test_request_quote_accessible_for_customers(self, customer_headers):
        """Request-quote endpoint accessible for authenticated customers."""
        resp = requests.post(
            f"{BASE_URL}/api/products/request-quote",
            json={
                "product_id": RFQ_PRODUCT_ID,
                "product_name": "TEST_Regression Quote",
                "name": "TEST_Regression User",
                "email": "TEST_regression@test.com",
            },
            headers=customer_headers,
        )
        assert resp.status_code == 200, f"Quote request failed: {resp.status_code} {resp.text}"
        print(f"PASS: Quote request accessible for customers - {resp.status_code}")
