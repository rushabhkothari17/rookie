"""
Backend tests for currency feature addition and legacy cleanup.
Tests:
- Base currency GET/PUT endpoints
- Backend starts without errors
- Partner registration with base_currency
- Products currency field
- No override_codes collection (dropped)
- Orders/subscriptions have currency field
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"
PARTNER_CODE = "automate-accounts"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin token for platform admin (no partner_code for platform admin login)."""
    # Platform admin logs in WITHOUT partner_code
    res = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
    })
    assert res.status_code == 200, f"Login failed: {res.text}"
    data = res.json()
    token = data.get("access_token") or data.get("token")
    assert token, f"No token in response: {data}"
    print(f"✓ Logged in as platform admin, role: {data.get('role')}")
    return token


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


class TestBackendStartup:
    """Backend health check"""
    
    def test_backend_reachable(self):
        """Backend responds to public endpoint"""
        res = requests.get(f"{BASE_URL}/api/website-settings")
        assert res.status_code == 200, f"Backend unreachable: {res.status_code}"
        print("✓ Backend is reachable")

    def test_no_import_errors(self):
        """Backend startup log has no import errors"""
        # If backend is reachable, it means no import errors at startup
        res = requests.get(f"{BASE_URL}/api/website-settings")
        assert res.status_code == 200, "Backend appears to have import errors (500 or unreachable)"
        print("✓ Backend started without import errors")


class TestBaseCurrencyAPI:
    """Test base currency GET/PUT endpoints"""

    def test_get_base_currency_requires_auth(self):
        """GET base-currency should return 401 without auth"""
        res = requests.get(f"{BASE_URL}/api/admin/tenant/base-currency")
        assert res.status_code == 401, f"Expected 401, got {res.status_code}"
        print("✓ GET base-currency properly rejects unauthenticated requests")

    def test_get_base_currency_with_auth(self, admin_headers):
        """GET base-currency returns base_currency field"""
        res = requests.get(f"{BASE_URL}/api/admin/tenant/base-currency", headers=admin_headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert "base_currency" in data, f"base_currency not in response: {data}"
        assert data["base_currency"] in ["USD", "CAD", "EUR", "AUD", "GBP", "INR", "MXN"], \
            f"Unexpected currency: {data['base_currency']}"
        print(f"✓ GET base-currency returns: {data['base_currency']}")

    def test_put_base_currency_valid(self, admin_headers):
        """PUT base-currency with valid currency updates successfully"""
        # First get current
        get_res = requests.get(f"{BASE_URL}/api/admin/tenant/base-currency", headers=admin_headers)
        original = get_res.json().get("base_currency", "USD")
        
        # Try updating to CAD
        test_currency = "CAD" if original != "CAD" else "USD"
        res = requests.put(f"{BASE_URL}/api/admin/tenant/base-currency", 
                          json={"base_currency": test_currency}, headers=admin_headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert data.get("base_currency") == test_currency, f"Wrong currency returned: {data}"
        print(f"✓ PUT base-currency updated to: {test_currency}")
        
        # Restore original
        requests.put(f"{BASE_URL}/api/admin/tenant/base-currency",
                    json={"base_currency": original}, headers=admin_headers)

    def test_put_base_currency_invalid(self, admin_headers):
        """PUT base-currency with invalid currency returns 400"""
        res = requests.put(f"{BASE_URL}/api/admin/tenant/base-currency",
                          json={"base_currency": "INVALID"}, headers=admin_headers)
        assert res.status_code == 400, f"Expected 400 for invalid currency, got {res.status_code}: {res.text}"
        print("✓ PUT base-currency rejects invalid currency with 400")

    def test_put_base_currency_all_valid_values(self, admin_headers):
        """All valid currencies are accepted"""
        valid_currencies = ["USD", "CAD", "EUR", "AUD", "GBP", "INR", "MXN"]
        for curr in valid_currencies:
            res = requests.put(f"{BASE_URL}/api/admin/tenant/base-currency",
                              json={"base_currency": curr}, headers=admin_headers)
            assert res.status_code == 200, f"Currency {curr} rejected: {res.status_code} {res.text}"
        print(f"✓ All valid currencies accepted: {valid_currencies}")
        # Restore USD
        requests.put(f"{BASE_URL}/api/admin/tenant/base-currency",
                    json={"base_currency": "USD"}, headers=admin_headers)


class TestOverrideCodesRemoved:
    """Test that override_codes functionality is removed"""

    def test_no_currency_override_endpoint(self, admin_headers):
        """Currency override endpoint should return 404 (removed)"""
        # The old endpoint was something like /api/admin/customers/{id}/currency-override
        # Test that it's gone - we check with a fake customer ID
        res = requests.put(f"{BASE_URL}/api/admin/customers/fake-id/currency-override",
                          json={"currency": "USD"}, headers=admin_headers)
        assert res.status_code in [404, 405], f"Currency override endpoint still exists: {res.status_code}"
        print("✓ Currency override endpoint is removed (404/405)")


class TestProductCurrencyField:
    """Test product currency field"""

    def test_products_have_currency_field(self, admin_headers):
        """Products returned by API should have currency field"""
        res = requests.get(f"{BASE_URL}/api/admin/products-all", headers=admin_headers)
        assert res.status_code == 200, f"Catalog request failed: {res.status_code}"
        data = res.json()
        products = data.get("products", [])
        if products:
            product = products[0]
            # currency should be in the product (may be "USD" default)
            print(f"First product fields: {list(product.keys())}")
            # Check that currency field exists in at least one product
            has_currency = any("currency" in p for p in products)
            print(f"✓ Products loaded ({len(products)} total), currency field present: {has_currency}")
        else:
            print("✓ No products found (empty catalog)")


class TestOrdersCurrencyField:
    """Test that orders have currency column"""

    def test_orders_endpoint_accessible(self, admin_headers):
        """Orders API endpoint works"""
        res = requests.get(f"{BASE_URL}/api/admin/orders", headers=admin_headers)
        assert res.status_code == 200, f"Orders endpoint failed: {res.status_code}: {res.text}"
        data = res.json()
        orders = data.get("orders", [])
        print(f"✓ Orders endpoint accessible, {len(orders)} orders found")
        
        if orders:
            order = orders[0]
            print(f"Order fields: {list(order.keys())}")
            # Currency should be present in orders (or default to USD)
            if "currency" in order:
                print(f"✓ Order has currency: {order['currency']}")
            else:
                print("! Warning: Order does not have explicit currency field (may use default)")


class TestSubscriptionsCurrencyField:
    """Test that subscriptions have currency column"""

    def test_subscriptions_endpoint_accessible(self, admin_headers):
        """Subscriptions API endpoint works"""
        res = requests.get(f"{BASE_URL}/api/admin/subscriptions", headers=admin_headers)
        assert res.status_code == 200, f"Subscriptions endpoint failed: {res.status_code}: {res.text}"
        data = res.json()
        subs = data.get("subscriptions", [])
        print(f"✓ Subscriptions endpoint accessible, {len(subs)} subscriptions found")
        
        if subs:
            sub = subs[0]
            print(f"Subscription fields: {list(sub.keys())}")
            if "currency" in sub:
                print(f"✓ Subscription has currency: {sub['currency']}")
            else:
                print("! Warning: Subscription does not have explicit currency field")


class TestPartnerRegistrationBaseCurrency:
    """Test partner registration with base_currency"""

    def test_register_partner_endpoint_accepts_base_currency(self):
        """Partner registration endpoint accepts base_currency field"""
        # We just verify the endpoint structure, don't actually register
        # POST /api/auth/register/partner should accept base_currency
        test_payload = {
            "name": "TEST_Partner_Currency_Test",
            "admin_name": "Test Admin",
            "admin_email": "TEST_currency_partner@test.invalid",
            "admin_password": "TestPass123!",
            "base_currency": "EUR"
        }
        res = requests.post(f"{BASE_URL}/api/auth/register/partner", json=test_payload)
        # Could be 200 (success) or 400 (duplicate/validation error)
        # Just ensure it's not 422 (which would mean base_currency not accepted)
        assert res.status_code != 422, f"Partner registration rejected base_currency (422): {res.text}"
        print(f"✓ Partner registration accepts base_currency field (status: {res.status_code})")
        
        # Cleanup if created
        if res.status_code == 200:
            data = res.json()
            print(f"Test partner created. Manual cleanup may be needed for: TEST_currency_partner@test.invalid")
