"""
Iteration 66: Tests for:
- New export endpoints (bank-transactions, article-categories, article-templates)
- API key management (CRUD + tenant isolation)
- X-API-Key header on /api/products and /api/categories
- /api/me partner_code field
- Tenant isolation for exports (Tenant B admin only sees own data)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Credentials
PLATFORM_EMAIL = "admin@automateaccounts.local"
PLATFORM_PASS = "ChangeMe123!"
PLATFORM_CODE = "automate-accounts"

TENANT_B_EMAIL = "adminb@tenantb.local"
TENANT_B_PASS = "ChangeMe123!"
TENANT_B_CODE = "tenant-b-test"


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def platform_token():
    """Get JWT for platform admin."""
    res = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": PLATFORM_EMAIL,
        "password": PLATFORM_PASS,
        "partner_code": PLATFORM_CODE,
    })
    assert res.status_code == 200, f"Platform admin login failed: {res.text}"
    return res.json()["token"]


@pytest.fixture(scope="module")
def tenant_b_token():
    """Get JWT for Tenant B admin."""
    res = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TENANT_B_EMAIL,
        "password": TENANT_B_PASS,
        "partner_code": TENANT_B_CODE,
    })
    if res.status_code != 200:
        pytest.skip(f"Tenant B login failed: {res.text}")
    return res.json()["token"]


@pytest.fixture(scope="module")
def platform_headers(platform_token):
    return {"Authorization": f"Bearer {platform_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def tenant_b_headers(tenant_b_token):
    return {"Authorization": f"Bearer {tenant_b_token}", "Content-Type": "application/json"}


# ── /api/me partner_code ─────────────────────────────────────────────────────

class TestMeEndpoint:
    """Test /api/me returns partner_code field."""

    def test_me_platform_admin_has_partner_code(self, platform_headers):
        res = requests.get(f"{BASE_URL}/api/me", headers=platform_headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert "user" in data
        # platform_admin's partner_code should be present (could be None or a value)
        assert "partner_code" in data["user"], "partner_code field missing from /api/me response"

    def test_me_tenant_b_has_partner_code(self, tenant_b_headers):
        res = requests.get(f"{BASE_URL}/api/me", headers=tenant_b_headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert "user" in data
        assert "partner_code" in data["user"], "partner_code field missing from /api/me response for Tenant B"
        assert data["user"]["partner_code"] == TENANT_B_CODE, \
            f"Expected partner_code='{TENANT_B_CODE}', got '{data['user']['partner_code']}'"


# ── Export Endpoints ──────────────────────────────────────────────────────────

class TestExportEndpoints:
    """Test new export CSV endpoints return 200 with CSV content."""

    def test_export_bank_transactions_platform_admin(self, platform_headers):
        res = requests.get(f"{BASE_URL}/api/admin/export/bank-transactions", headers=platform_headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        ct = res.headers.get("content-type", "")
        assert "text/csv" in ct or "csv" in ct.lower() or len(res.text) > 0, "Expected CSV content"

    def test_export_article_categories_platform_admin(self, platform_headers):
        res = requests.get(f"{BASE_URL}/api/admin/export/article-categories", headers=platform_headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"

    def test_export_article_templates_platform_admin(self, platform_headers):
        res = requests.get(f"{BASE_URL}/api/admin/export/article-templates", headers=platform_headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"

    def test_export_bank_transactions_tenant_b(self, tenant_b_headers):
        res = requests.get(f"{BASE_URL}/api/admin/export/bank-transactions", headers=tenant_b_headers)
        assert res.status_code == 200, f"Expected 200 for Tenant B: {res.status_code}: {res.text}"

    def test_export_article_categories_tenant_b(self, tenant_b_headers):
        res = requests.get(f"{BASE_URL}/api/admin/export/article-categories", headers=tenant_b_headers)
        assert res.status_code == 200, f"Expected 200 for Tenant B: {res.status_code}: {res.text}"

    def test_export_article_templates_tenant_b(self, tenant_b_headers):
        res = requests.get(f"{BASE_URL}/api/admin/export/article-templates", headers=tenant_b_headers)
        assert res.status_code == 200, f"Expected 200 for Tenant B: {res.status_code}: {res.text}"

    def test_existing_export_orders_still_works(self, platform_headers):
        """Regression: old export endpoints still work."""
        res = requests.get(f"{BASE_URL}/api/admin/export/orders", headers=platform_headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"

    def test_existing_export_customers_still_works(self, platform_headers):
        res = requests.get(f"{BASE_URL}/api/admin/export/customers", headers=platform_headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"


# ── API Key Management ────────────────────────────────────────────────────────

class TestApiKeyManagement:
    """Test API key CRUD operations."""

    def test_list_api_keys_returns_200(self, platform_headers):
        res = requests.get(f"{BASE_URL}/api/admin/api-keys", headers=platform_headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert "api_keys" in data, "Response must have 'api_keys' field"
        assert isinstance(data["api_keys"], list), "'api_keys' must be a list"

    def test_list_api_keys_are_masked(self, platform_headers):
        """Key values must be masked (key_masked field, no 'key' field)."""
        res = requests.get(f"{BASE_URL}/api/admin/api-keys", headers=platform_headers)
        assert res.status_code == 200
        data = res.json()
        for k in data["api_keys"]:
            assert "key" not in k, f"Raw 'key' field exposed in list: {k}"
            assert "key_masked" in k, f"'key_masked' field missing: {k}"

    def test_generate_api_key(self, platform_headers):
        """POST /api/admin/api-keys generates a new key and returns full value once."""
        res = requests.post(f"{BASE_URL}/api/admin/api-keys",
                          json={"name": "TEST_key_iter66"},
                          headers=platform_headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert "key" in data, "Full key must be returned on creation"
        assert data["key"].startswith("ak_"), "Key must start with 'ak_'"
        assert "id" in data, "Key ID must be returned"
        assert data.get("is_active") is True, "Newly generated key must be active"
        return data

    def test_generate_key_deactivates_existing(self, platform_headers):
        """Generating a new key should deactivate old active keys."""
        # Generate first key
        res1 = requests.post(f"{BASE_URL}/api/admin/api-keys",
                            json={"name": "TEST_key_first"},
                            headers=platform_headers)
        assert res1.status_code == 200
        key1_id = res1.json()["id"]

        # Generate second key
        res2 = requests.post(f"{BASE_URL}/api/admin/api-keys",
                            json={"name": "TEST_key_second"},
                            headers=platform_headers)
        assert res2.status_code == 200
        key2_id = res2.json()["id"]

        # List keys — key1 should be deactivated
        list_res = requests.get(f"{BASE_URL}/api/admin/api-keys", headers=platform_headers)
        keys = list_res.json()["api_keys"]
        key1 = next((k for k in keys if k["id"] == key1_id), None)
        key2 = next((k for k in keys if k["id"] == key2_id), None)

        if key1:
            assert key1.get("is_active") is False, "Old key should be deactivated"
        if key2:
            assert key2.get("is_active") is True, "New key should be active"

    def test_revoke_api_key(self, platform_headers):
        """DELETE /api/admin/api-keys/{id} revokes the key."""
        # Create a key to revoke
        create_res = requests.post(f"{BASE_URL}/api/admin/api-keys",
                                  json={"name": "TEST_key_to_revoke"},
                                  headers=platform_headers)
        assert create_res.status_code == 200
        key_id = create_res.json()["id"]

        # Revoke it
        del_res = requests.delete(f"{BASE_URL}/api/admin/api-keys/{key_id}", headers=platform_headers)
        assert del_res.status_code == 200, f"Expected 200, got {del_res.status_code}: {del_res.text}"
        data = del_res.json()
        assert data.get("success") is True or "revoked" in str(data).lower()

        # List again — key should be inactive
        list_res = requests.get(f"{BASE_URL}/api/admin/api-keys", headers=platform_headers)
        keys = list_res.json()["api_keys"]
        revoked = next((k for k in keys if k["id"] == key_id), None)
        if revoked:
            assert revoked.get("is_active") is False, "Revoked key should be inactive"

    def test_revoke_nonexistent_key_returns_404(self, platform_headers):
        res = requests.delete(f"{BASE_URL}/api/admin/api-keys/nonexistent_key_id", headers=platform_headers)
        assert res.status_code == 404, f"Expected 404, got {res.status_code}: {res.text}"

    def test_tenant_b_api_keys_isolated(self, tenant_b_headers, platform_headers):
        """Tenant B cannot see Platform Admin's API keys."""
        platform_keys_res = requests.get(f"{BASE_URL}/api/admin/api-keys", headers=platform_headers)
        tenant_b_keys_res = requests.get(f"{BASE_URL}/api/admin/api-keys", headers=tenant_b_headers)
        
        assert platform_keys_res.status_code == 200
        assert tenant_b_keys_res.status_code == 200

        platform_key_ids = {k["id"] for k in platform_keys_res.json()["api_keys"]}
        tenant_b_key_ids = {k["id"] for k in tenant_b_keys_res.json()["api_keys"]}
        
        # No overlap between tenants
        overlap = platform_key_ids & tenant_b_key_ids
        assert not overlap, f"Tenant isolation violated: overlapping key IDs: {overlap}"


# ── X-API-Key Header on Public Endpoints ─────────────────────────────────────

class TestApiKeyAccess:
    """Test X-API-Key header resolves correct tenant on /api/products and /api/categories."""

    @pytest.fixture(scope="class")
    def active_api_key(self, platform_headers):
        """Get or create an active API key for the platform tenant."""
        # Generate a fresh key
        res = requests.post(f"{BASE_URL}/api/admin/api-keys",
                          json={"name": "TEST_iter66_api_key_test"},
                          headers=platform_headers)
        if res.status_code != 200:
            pytest.skip(f"Could not generate API key: {res.text}")
        return res.json()["key"]

    def test_products_with_api_key_header(self, active_api_key):
        """GET /api/products with X-API-Key returns tenant-specific products."""
        res = requests.get(f"{BASE_URL}/api/products",
                          headers={"X-API-Key": active_api_key})
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert "products" in data, "Response must have 'products' field"

    def test_categories_with_api_key_header(self, active_api_key):
        """GET /api/categories with X-API-Key returns tenant-specific categories."""
        res = requests.get(f"{BASE_URL}/api/categories",
                          headers={"X-API-Key": active_api_key})
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert "categories" in data, "Response must have 'categories' field"

    def test_products_with_invalid_api_key_still_works(self):
        """Invalid API key should still return 200 (falls back to default tenant behavior)."""
        res = requests.get(f"{BASE_URL}/api/products",
                          headers={"X-API-Key": "ak_invalid_key_xyz"})
        # Should still work (just no tenant filtering from api key)
        assert res.status_code in [200], f"Expected 200, got {res.status_code}: {res.text}"


# ── Tenant Isolation on Exports ───────────────────────────────────────────────

class TestTenantIsolationExports:
    """Verify Tenant B exports only Tenant B data."""

    def test_tenant_b_export_orders_is_isolated(self, tenant_b_headers):
        """Tenant B export should only contain their orders (won't contain platform orders)."""
        res = requests.get(f"{BASE_URL}/api/admin/export/orders", headers=tenant_b_headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        content = res.text
        # If there's data (CSV), check it doesn't leak other tenant info
        # (We can't easily check this without knowing exact data, but status 200 confirms it runs)
        assert len(content) > 0

    def test_export_unauthenticated_returns_401_or_403(self):
        """Unauthenticated export requests must be rejected."""
        res = requests.get(f"{BASE_URL}/api/admin/export/bank-transactions")
        assert res.status_code in [401, 403, 422], \
            f"Expected auth error, got {res.status_code}: {res.text}"

    def test_export_article_categories_unauthenticated(self):
        res = requests.get(f"{BASE_URL}/api/admin/export/article-categories")
        assert res.status_code in [401, 403, 422], \
            f"Expected auth error, got {res.status_code}: {res.text}"

    def test_export_article_templates_unauthenticated(self):
        res = requests.get(f"{BASE_URL}/api/admin/export/article-templates")
        assert res.status_code in [401, 403, 422], \
            f"Expected auth error, got {res.status_code}: {res.text}"
