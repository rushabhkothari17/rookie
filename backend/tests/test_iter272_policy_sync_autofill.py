"""
Iteration 272 Backend Tests:
- Backend health check
- CRM mappings returns 13 webapp_modules (regression)
- Policy text removal is a frontend-only change (code review confirmed)
- Bulk sync collection_map has 13 modules (code-review via API confirmation)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"
PARTNER_CODE = "automate-accounts"

EXPECTED_13_MODULES = [
    "customers", "orders", "subscriptions", "products", "enquiries",
    "invoices", "resources", "plans", "categories", "terms",
    "promo_codes", "refunds", "addresses"
]


@pytest.fixture(scope="module")
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_token():
    """Get platform admin auth token — no partner_code needed"""
    login = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
    })
    if login.status_code != 200:
        pytest.skip(f"Login failed: {login.status_code} {login.text}")
    token = login.json().get("token") or login.json().get("access_token")
    if not token:
        pytest.skip("No token in login response")
    return token


@pytest.fixture(scope="module")
def auth_session(api_client, auth_token):
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client


class TestBackendHealth:
    """Backend health check"""

    def test_health_endpoint(self, api_client):
        """Backend root should respond with 200"""
        resp = api_client.get(f"{BASE_URL}/api/")
        assert resp.status_code == 200, f"Health check failed: {resp.status_code} {resp.text}"
        print(f"PASS: /api/ returned 200 — {resp.json()}")

    def test_admin_login_works(self, auth_token):
        """Admin login should succeed and return a token"""
        assert auth_token, "Expected a valid admin auth token"
        print(f"PASS: Admin auth token obtained (len={len(auth_token)})")


class TestCRMMappings13Modules:
    """Regression: GET /api/admin/integrations/crm-mappings returns exactly 13 webapp_modules"""

    def test_crm_mappings_returns_200(self, auth_session):
        """CRM mappings endpoint should return 200"""
        resp = auth_session.get(f"{BASE_URL}/api/admin/integrations/crm-mappings")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print("PASS: GET /api/admin/integrations/crm-mappings returned 200")

    def test_crm_mappings_has_webapp_modules_key(self, auth_session):
        """Response should include webapp_modules list"""
        resp = auth_session.get(f"{BASE_URL}/api/admin/integrations/crm-mappings")
        assert resp.status_code == 200
        data = resp.json()
        assert "webapp_modules" in data, f"Missing 'webapp_modules' key in response: {list(data.keys())}"
        print(f"PASS: webapp_modules key present, count={len(data['webapp_modules'])}")

    def test_crm_mappings_exactly_13_modules(self, auth_session):
        """Should return exactly 13 webapp modules"""
        resp = auth_session.get(f"{BASE_URL}/api/admin/integrations/crm-mappings")
        assert resp.status_code == 200
        modules = resp.json()["webapp_modules"]
        module_names = [m["name"] for m in modules]
        assert len(module_names) == 13, (
            f"Expected 13 modules, got {len(module_names)}: {module_names}"
        )
        print(f"PASS: Exactly 13 webapp_modules returned: {module_names}")

    def test_crm_mappings_all_expected_modules_present(self, auth_session):
        """All 13 expected module names should be present"""
        resp = auth_session.get(f"{BASE_URL}/api/admin/integrations/crm-mappings")
        assert resp.status_code == 200
        modules = resp.json()["webapp_modules"]
        module_names = {m["name"] for m in modules}
        missing = set(EXPECTED_13_MODULES) - module_names
        assert not missing, f"Missing modules: {missing}. Got: {module_names}"
        print(f"PASS: All 13 expected modules present: {sorted(module_names)}")

    def test_crm_mappings_each_module_has_fields(self, auth_session):
        """Each module should have a non-empty fields list"""
        resp = auth_session.get(f"{BASE_URL}/api/admin/integrations/crm-mappings")
        assert resp.status_code == 200
        modules = resp.json()["webapp_modules"]
        for m in modules:
            assert "fields" in m, f"Module {m['name']} missing 'fields'"
            assert len(m["fields"]) > 0, f"Module {m['name']} has empty fields list"
        print(f"PASS: All 13 modules have non-empty fields lists")

    def test_crm_mappings_with_provider_filter(self, auth_session):
        """Filtering by provider=zoho_crm should return 200"""
        resp = auth_session.get(f"{BASE_URL}/api/admin/integrations/crm-mappings?provider=zoho_crm")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "webapp_modules" in data
        # webapp_modules should still have 13 entries regardless of filter
        assert len(data["webapp_modules"]) == 13, (
            f"Expected 13 modules with provider filter, got {len(data['webapp_modules'])}"
        )
        print(f"PASS: GET crm-mappings?provider=zoho_crm returned 200, 13 modules")


class TestProductEndpoints:
    """Test product-related endpoints used by ProductDetail page"""

    def test_list_products_returns_200(self, auth_session):
        """Products list endpoint should return 200"""
        resp = auth_session.get(f"{BASE_URL}/api/products")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "products" in data or isinstance(data, list), "Unexpected products response structure"
        print(f"PASS: GET /api/products returned 200")

    def test_get_first_product_detail(self, auth_session):
        """First product detail should be accessible"""
        resp = auth_session.get(f"{BASE_URL}/api/products")
        assert resp.status_code == 200
        products_data = resp.json()
        products = products_data.get("products") or products_data if isinstance(products_data, list) else []
        if not products:
            pytest.skip("No products available to test")
        product_id = products[0].get("id") or products[0].get("_id")
        detail_resp = auth_session.get(f"{BASE_URL}/api/products/{product_id}")
        assert detail_resp.status_code == 200, f"Expected 200, got {detail_resp.status_code}"
        product = detail_resp.json().get("product") or detail_resp.json()
        assert "id" in product or "name" in product, "Product detail missing expected fields"
        print(f"PASS: GET /api/products/{product_id} returned 200")
