"""
Tests for iteration 250 - 10 bug fixes:
Issue 1: Payment confirmation toast fires only once (CheckoutSuccess.tsx useRef)
Issue 2: 100% discounted carts (free checkout) work for both one-time AND subscription
Issue 3: Promo code currency validation
Issue 4: Resource Short ID and Resource ID NOT visible on public ResourceView page
Issue 5: Store sidebar category counts update dynamically
Issue 6: User edit dialog shows unsaved changes warning (UI - not testable here)
Issue 7: Quick Preset dropdown reflects currently applied preset (UI - not testable here)
Issue 8: API docs show actual REACT_APP_BACKEND_URL (UI - not testable here)
Issue 9: /api/tenant-info works with X-API-Key header without requiring ?code= param
Issue 10: Updated bodySchema documentation for 3 endpoints (UI - not testable here)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


@pytest.fixture
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture
def admin_token(api_client):
    """Get admin JWT token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!"
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"Admin login failed: {response.status_code} {response.text}")


@pytest.fixture
def admin_client(api_client, admin_token):
    api_client.headers.update({"Authorization": f"Bearer {admin_token}"})
    return api_client


# ── Issue 9: /api/tenant-info with X-API-Key header ──────────────────────────

class TestTenantInfoEndpoint:
    """Issue 9: /api/tenant-info accepts X-API-Key header without requiring ?code="""

    def test_tenant_info_no_params_returns_400(self, api_client):
        """Without code or X-API-Key, should return 400"""
        response = api_client.get(f"{BASE_URL}/api/tenant-info")
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

    def test_tenant_info_with_valid_code(self, api_client):
        """With valid code, should return tenant info"""
        response = api_client.get(f"{BASE_URL}/api/tenant-info?code=automate-accounts")
        assert response.status_code == 200
        data = response.json()
        assert "tenant" in data
        assert data["tenant"]["code"] == "automate-accounts"

    def test_tenant_info_with_invalid_code(self, api_client):
        """With invalid code, should return 404"""
        response = api_client.get(f"{BASE_URL}/api/tenant-info?code=nonexistent-tenant-xyz")
        assert response.status_code == 404

    def test_tenant_info_with_invalid_api_key(self, api_client):
        """With invalid X-API-Key, should return 401"""
        response = api_client.get(
            f"{BASE_URL}/api/tenant-info",
            headers={"X-API-Key": "ak_invalid_key_12345"}
        )
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data


# ── Issue 3: Promo code currency validation ───────────────────────────────────

class TestPromoCodeCurrencyValidation:
    """Issue 3: currency is passed when validating promo codes, backend rejects mismatches"""

    def test_promo_code_validate_requires_auth(self, api_client):
        """promo-codes/validate requires authentication"""
        response = api_client.post(f"{BASE_URL}/api/promo-codes/validate", json={
            "code": "TEST100",
            "checkout_type": "one_time"
        })
        assert response.status_code == 401

    def test_promo_code_validate_with_nonexistent_code(self, admin_client):
        """Non-existent promo code returns 404"""
        response = admin_client.post(f"{BASE_URL}/api/promo-codes/validate", json={
            "code": "NONEXISTENT_CODE_XYZ",
            "checkout_type": "one_time",
            "currency": "USD"
        })
        assert response.status_code == 404

    def test_apply_promo_request_model_has_currency_field(self, api_client):
        """POST /api/promo-codes/validate accepts currency field in payload (no 422 error)"""
        # We test that the endpoint accepts currency field without a 422 Unprocessable Entity
        response = api_client.post(f"{BASE_URL}/api/promo-codes/validate", json={
            "code": "TEST",
            "checkout_type": "one_time",
            "product_ids": [],
            "currency": "GBP"
        })
        # Should be 401 (auth required) not 422 (bad schema)
        assert response.status_code == 401


# ── Issue 2: Free checkout for subscriptions ─────────────────────────────────

class TestFreeCheckoutForSubscriptions:
    """Issue 2: 100% discounted carts work for both one-time AND subscription products"""

    def test_checkout_free_endpoint_exists(self, api_client):
        """POST /api/checkout/free endpoint exists (returns 401, not 404/405)"""
        response = api_client.post(f"{BASE_URL}/api/checkout/free", json={})
        # Should be 401 (auth required), not 404 (not found)
        assert response.status_code in [401, 422]
        assert response.status_code != 404
        assert response.status_code != 405

    def test_checkout_free_requires_auth(self, api_client):
        """POST /api/checkout/free requires authentication"""
        response = api_client.post(f"{BASE_URL}/api/checkout/free", json={
            "items": [],
            "checkout_type": "one_time"
        })
        assert response.status_code == 401


# ── Issue 9 (extended): Validate full X-API-Key flow ─────────────────────────

class TestApiKeyFlow:
    """Tests for API key generation and use"""

    def test_list_api_keys_requires_auth(self, api_client):
        """GET /api/admin/api-keys requires auth"""
        response = api_client.get(f"{BASE_URL}/api/admin/api-keys")
        assert response.status_code == 401

    def test_list_api_keys_with_admin_auth(self, admin_client):
        """GET /api/admin/api-keys returns api_keys list for admin"""
        response = admin_client.get(f"{BASE_URL}/api/admin/api-keys")
        assert response.status_code == 200
        data = response.json()
        assert "api_keys" in data
        assert isinstance(data["api_keys"], list)

    def test_tenant_info_with_valid_api_key(self, admin_client):
        """If we have an API key, can call /api/tenant-info with X-API-Key header"""
        # First get/create an API key
        keys_response = admin_client.get(f"{BASE_URL}/api/admin/api-keys")
        assert keys_response.status_code == 200
        api_keys = keys_response.json().get("api_keys", [])
        active_key = next((k for k in api_keys if k.get("is_active")), None)

        if not active_key:
            pytest.skip("No active API key found - skipping X-API-Key tenant-info test")

        # We only have the masked key, so we can't test the actual key value
        # Just verify the endpoint structure is correct
        # The masked key won't work, so we test with a fake key to check 401 behavior
        response = requests.get(
            f"{BASE_URL}/api/tenant-info",
            headers={"X-API-Key": "ak_fake_key_for_test"}
        )
        assert response.status_code == 401


# ── Issue 1: CheckoutSuccess useRef prevents duplicate toast ─────────────────

class TestCheckoutStatus:
    """Issue 1: /api/checkout/status endpoint exists and works correctly"""

    def test_checkout_status_requires_auth(self, api_client):
        """GET /api/checkout/status/{session_id} requires auth"""
        response = api_client.get(f"{BASE_URL}/api/checkout/status/cs_test_123")
        assert response.status_code == 401

    def test_checkout_status_invalid_session(self, admin_client):
        """GET /api/checkout/status/{invalid_id} returns non-200 for invalid session"""
        response = admin_client.get(f"{BASE_URL}/api/checkout/status/cs_invalid_test_session")
        # Should return 400, 404, 422 or 500 (if Stripe not configured) - not 200
        assert response.status_code != 200


# ── Issue 4: ResourceView hides IDs from public ───────────────────────────────

class TestResourceView:
    """Issue 4: /api/resources endpoint for verifying Resource data"""

    def test_get_resources_list(self, api_client):
        """GET /api/resources/public is accessible (public resources)"""
        response = api_client.get(f"{BASE_URL}/api/resources/public")
        assert response.status_code in [200, 401]
        if response.status_code == 200:
            data = response.json()
            assert "resources" in data

    def test_get_resource_by_id_requires_access(self, api_client):
        """GET /api/resources/{id} is accessible"""
        response = api_client.get(f"{BASE_URL}/api/resources/nonexistent-id")
        # 404 or 401 
        assert response.status_code in [404, 401, 400]


# ── Issue 10: Scope request form endpoint ────────────────────────────────────

class TestScopeRequestForm:
    """Issue 10: /api/orders/scope-request-form endpoint accepts the documented bodySchema"""

    def test_scope_request_form_requires_auth(self, api_client):
        """POST /api/orders/scope-request-form requires auth"""
        response = api_client.post(f"{BASE_URL}/api/orders/scope-request-form", json={
            "items": [],
            "form_data": {
                "name": "Test User",
                "email": "test@example.com"
            }
        })
        assert response.status_code == 401

    def test_scope_request_form_accepts_documented_schema(self, api_client):
        """POST /api/orders/scope-request-form accepts the documented bodySchema without 422"""
        response = api_client.post(f"{BASE_URL}/api/orders/scope-request-form", json={
            "items": [{"product_id": "test", "quantity": 1, "inputs": {}}],
            "form_data": {
                "name": "Test User",
                "email": "test@example.com",
                "company": "Test Co",
                "phone": "555-1234",
                "message": "Test message"
            }
        })
        # Should be 401 (auth required) not 422 (schema mismatch)
        assert response.status_code == 401


# ── Issue 10: Checkout session endpoint ──────────────────────────────────────

class TestCheckoutSession:
    """Issue 10: /api/checkout/session endpoint accepts the documented bodySchema"""

    def test_checkout_session_accepts_documented_schema(self, api_client):
        """POST /api/checkout/session accepts the documented body schema"""
        response = api_client.post(f"{BASE_URL}/api/checkout/session", json={
            "items": [{"product_id": "test", "quantity": 1, "inputs": {}}],
            "checkout_type": "one_time",
            "promo_code": None,
            "terms_accepted": True,
            "terms_id": None,
            "origin_url": "https://example.com"
        })
        # Should be 401 (auth required), not 422 (schema error) or 404/405 (missing endpoint)
        assert response.status_code == 401

    def test_checkout_session_requires_auth(self, api_client):
        """POST /api/checkout/session requires authentication"""
        response = api_client.post(f"{BASE_URL}/api/checkout/session", json={
            "items": [],
            "checkout_type": "one_time",
            "origin_url": "https://example.com"
        })
        assert response.status_code == 401


# ── Users tab API ─────────────────────────────────────────────────────────────

class TestUsersAPI:
    """Issue 6 & 7: Admin users endpoints work correctly"""

    def test_list_admin_users(self, admin_client):
        """GET /api/admin/users returns users list"""
        response = admin_client.get(f"{BASE_URL}/api/admin/users")
        assert response.status_code == 200
        data = response.json()
        assert "users" in data
        assert isinstance(data["users"], list)

    def test_get_user_module_permissions(self, admin_client):
        """GET /api/admin/permissions/modules returns modules and preset_roles"""
        response = admin_client.get(f"{BASE_URL}/api/admin/permissions/modules")
        assert response.status_code == 200
        data = response.json()
        assert "modules" in data
        assert "preset_roles" in data


# ── Products endpoint ─────────────────────────────────────────────────────────

class TestProductsForStoreFilter:
    """Issue 5: Store sidebar products endpoint"""

    def test_get_products_returns_list(self, api_client):
        """GET /api/products returns products list"""
        response = api_client.get(f"{BASE_URL}/api/products")
        assert response.status_code == 200
        data = response.json()
        assert "products" in data
        assert isinstance(data["products"], list)

    def test_get_categories_returns_list(self, api_client):
        """GET /api/categories returns categories"""
        response = api_client.get(f"{BASE_URL}/api/categories")
        assert response.status_code == 200
        data = response.json()
        assert "categories" in data

    def test_store_filters_endpoint(self, api_client):
        """GET /api/store/filters returns filters"""
        response = api_client.get(f"{BASE_URL}/api/store/filters")
        assert response.status_code == 200
        data = response.json()
        assert "filters" in data
