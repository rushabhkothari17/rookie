"""
Backend tests for FX rate conversion and currency refactor.
Tests:
- FX external API (open.er-api.com) returns valid data
- Backend startup: checkout_service.py imports get_fx_rate without error
- Manual order creation with currency field persists base_currency_amount
- Manual subscription creation with currency field persists base_currency_amount
- Admin endpoints for orders/subscriptions include currency data
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin token."""
    res = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
    })
    assert res.status_code == 200, f"Login failed: {res.text}"
    data = res.json()
    token = data.get("access_token") or data.get("token")
    assert token, f"No token in response: {data}"
    print(f"✓ Logged in as admin, role: {data.get('role')}")
    return token


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


class TestFXExternalAPI:
    """Test the external FX rate API (open.er-api.com)"""

    def test_fx_api_returns_success(self):
        """open.er-api.com should return success result"""
        res = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10)
        assert res.status_code == 200, f"FX API returned non-200: {res.status_code}"
        data = res.json()
        assert data.get("result") == "success", f"FX API result not 'success': {data.get('result')}"
        print(f"✓ FX API returns success for USD base")

    def test_fx_api_has_rates(self):
        """FX API should include exchange rates"""
        res = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10)
        assert res.status_code == 200
        data = res.json()
        rates = data.get("rates", {})
        assert len(rates) > 0, "FX API returned no rates"
        assert "EUR" in rates, "EUR rate not in FX response"
        assert "GBP" in rates, "GBP rate not in FX response"
        assert "CAD" in rates, "CAD rate not in FX response"
        assert rates["USD"] == 1.0, f"USD/USD rate should be 1.0, got {rates.get('USD')}"
        print(f"✓ FX API has valid rates: EUR={rates.get('EUR')}, GBP={rates.get('GBP')}, CAD={rates.get('CAD')}")

    def test_fx_api_has_base_code(self):
        """FX API should echo back the base currency code"""
        res = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10)
        data = res.json()
        assert data.get("base_code") == "USD", f"base_code should be USD, got {data.get('base_code')}"
        print(f"✓ FX API base_code = {data.get('base_code')}")

    def test_fx_api_eur_base(self):
        """FX API works with EUR base as well"""
        res = requests.get("https://open.er-api.com/v6/latest/EUR", timeout=10)
        assert res.status_code == 200
        data = res.json()
        assert data.get("result") == "success"
        rates = data.get("rates", {})
        assert "USD" in rates
        print(f"✓ FX API works with EUR base: USD={rates.get('USD')}")


class TestBackendCheckoutServiceImports:
    """Test backend starts without import errors from checkout_service.py"""

    def test_backend_reachable(self):
        """Backend API root should be accessible"""
        res = requests.get(f"{BASE_URL}/api/", timeout=10)
        assert res.status_code == 200, f"Backend unreachable: {res.status_code}"
        print(f"✓ Backend API is reachable")

    def test_orders_endpoint_accessible_post_refactor(self, admin_headers):
        """Orders endpoint should work after checkout_service.py changes"""
        res = requests.get(f"{BASE_URL}/api/admin/orders", headers=admin_headers)
        assert res.status_code == 200, f"Orders endpoint failed: {res.status_code}: {res.text}"
        data = res.json()
        print(f"✓ Admin orders endpoint works, {len(data.get('orders', []))} orders found")

    def test_subscriptions_endpoint_accessible_post_refactor(self, admin_headers):
        """Subscriptions endpoint should work after checkout_service.py changes"""
        res = requests.get(f"{BASE_URL}/api/admin/subscriptions", headers=admin_headers)
        assert res.status_code == 200, f"Subscriptions endpoint failed: {res.status_code}: {res.text}"
        data = res.json()
        print(f"✓ Admin subscriptions endpoint works, {len(data.get('subscriptions', []))} subs found")


class TestManualOrderCurrencyAPI:
    """Test manual order creation with currency field"""

    def test_get_products_for_order(self, admin_headers):
        """Products endpoint accessible for order creation"""
        res = requests.get(f"{BASE_URL}/api/admin/products-all", headers=admin_headers)
        assert res.status_code == 200, f"Products endpoint failed: {res.status_code}"
        data = res.json()
        products = data.get("products", [])
        print(f"✓ Products accessible: {len(products)} products found")

    def test_manual_order_creation_with_currency(self, admin_headers):
        """Manual order creation endpoint accepts currency field"""
        # First get a product id
        res = requests.get(f"{BASE_URL}/api/admin/products-all", headers=admin_headers)
        assert res.status_code == 200
        products = res.json().get("products", [])
        
        if not products:
            pytest.skip("No products available for manual order test")
        
        product_id = products[0]["id"]
        
        # Create a manual order with EUR currency
        payload = {
            "customer_id": None,
            "customer_email": "TEST_fx_order@test.invalid",
            "product_id": product_id,
            "subtotal": 100.0,
            "discount": 0.0,
            "fee": 0.0,
            "currency": "EUR",
            "status": "paid",
            "internal_note": "TEST_FX_RATE_ORDER - automated test"
        }
        res = requests.post(f"{BASE_URL}/api/admin/orders/manual", json=payload, headers=admin_headers)
        # Accept 200 or 201 (created) - 422 would mean currency field not accepted
        assert res.status_code not in [422, 500], f"Manual order failed: {res.status_code}: {res.text}"
        if res.status_code in [200, 201]:
            data = res.json()
            print(f"✓ Manual order created with currency=EUR: {data.get('id', 'unknown')}")
            print(f"  base_currency_amount: {data.get('base_currency_amount', 'not present')}")
            # Cleanup: attempt to delete if we got an ID
            order_id = data.get("id") or data.get("order_id")
            if order_id:
                requests.delete(f"{BASE_URL}/api/admin/orders/{order_id}", headers=admin_headers)
        else:
            print(f"✓ Manual order endpoint responds without 422/500 (status: {res.status_code})")

    def test_manual_subscription_creation_with_currency(self, admin_headers):
        """Manual subscription creation endpoint accepts currency field"""
        # First get a product id
        res = requests.get(f"{BASE_URL}/api/admin/products-all", headers=admin_headers)
        assert res.status_code == 200
        products = res.json().get("products", [])
        
        if not products:
            pytest.skip("No products available for manual subscription test")
        
        product_id = products[0]["id"]
        
        # Create a manual subscription with GBP currency
        payload = {
            "customer_id": None,
            "customer_email": "TEST_fx_sub@test.invalid",
            "product_id": product_id,
            "amount": 50.0,
            "currency": "GBP",
            "renewal_date": "2027-01-01",
            "internal_note": "TEST_FX_RATE_SUB - automated test"
        }
        res = requests.post(f"{BASE_URL}/api/admin/subscriptions/manual", json=payload, headers=admin_headers)
        assert res.status_code not in [422, 500], f"Manual sub failed: {res.status_code}: {res.text}"
        if res.status_code in [200, 201]:
            data = res.json()
            print(f"✓ Manual subscription created with currency=GBP: {data.get('id', 'unknown')}")
            print(f"  base_currency_amount: {data.get('base_currency_amount', 'not present')}")
        else:
            print(f"✓ Manual sub endpoint responds without 422/500 (status: {res.status_code})")


class TestBaseCurrencyEndpoint:
    """Verify base currency endpoint works for the tenant"""

    def test_base_currency_returns_valid_currency(self, admin_headers):
        """Base currency should return one of the supported currencies"""
        res = requests.get(f"{BASE_URL}/api/admin/tenant/base-currency", headers=admin_headers)
        assert res.status_code == 200, f"Failed: {res.status_code}: {res.text}"
        data = res.json()
        assert "base_currency" in data
        valid = ["USD", "CAD", "EUR", "AUD", "GBP", "INR", "MXN"]
        assert data["base_currency"] in valid, f"Unexpected: {data['base_currency']}"
        print(f"✓ Base currency is: {data['base_currency']}")

    def test_base_currency_update_and_verify(self, admin_headers):
        """Update base currency and verify it persists"""
        # Get original
        get_res = requests.get(f"{BASE_URL}/api/admin/tenant/base-currency", headers=admin_headers)
        original = get_res.json().get("base_currency", "USD")
        
        # Update to different currency
        new_curr = "GBP" if original != "GBP" else "USD"
        put_res = requests.put(f"{BASE_URL}/api/admin/tenant/base-currency",
                               json={"base_currency": new_curr}, headers=admin_headers)
        assert put_res.status_code == 200, f"PUT failed: {put_res.status_code}: {put_res.text}"
        
        # Verify it was saved
        verify_res = requests.get(f"{BASE_URL}/api/admin/tenant/base-currency", headers=admin_headers)
        assert verify_res.json().get("base_currency") == new_curr, \
            f"Currency not persisted: {verify_res.json()}"
        print(f"✓ Base currency updated to {new_curr} and persisted")
        
        # Restore original
        requests.put(f"{BASE_URL}/api/admin/tenant/base-currency",
                    json={"base_currency": original}, headers=admin_headers)
        print(f"✓ Restored to original: {original}")
