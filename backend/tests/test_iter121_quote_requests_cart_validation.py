"""
Iteration 121 — Quote Requests Cleanup & Cart Validation
Tests:
1. integrations.py: webapp_modules has NO quote_requests
2. imports.py: POST /api/admin/import/quote-requests returns 400 (not in ENTITY_COLLECTIONS)
3. imports.py: POST /api/admin/import/override-codes returns 400 (removed from ENTITY_COLLECTIONS)
4. Valid entities still work
"""

import io
import pytest
import requests
import os

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"
PARTNER_CODE = "automate-accounts"


def get_base_url():
    url = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
    if not url:
        pytest.skip("REACT_APP_BACKEND_URL not set")
    return url


@pytest.fixture(scope="module")
def base_url():
    return get_base_url()


@pytest.fixture(scope="module")
def admin_token(base_url):
    """Login as tenant admin and return JWT token."""
    resp = requests.post(
        f"{base_url}/api/auth/login",
        json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
            "partner_code": PARTNER_CODE,
        },
    )
    if resp.status_code != 200:
        pytest.skip(f"Admin login failed ({resp.status_code}): {resp.text}")
    data = resp.json()
    token = data.get("access_token") or data.get("token")
    if not token:
        pytest.skip("No token in login response")
    print(f"Logged in as admin, token starts with: {token[:20]}...")
    return token


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ─── CRM Mappings: webapp_modules should NOT include quote_requests ───────────

class TestCRMMappingsNoQuoteRequests:
    """integrations.py — webapp_modules cleanup"""

    def test_crm_mappings_returns_200(self, base_url, admin_headers):
        """GET /api/admin/integrations/crm-mappings should return 200."""
        resp = requests.get(
            f"{base_url}/api/admin/integrations/crm-mappings",
            headers=admin_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print("PASS: /api/admin/integrations/crm-mappings returns 200")

    def test_webapp_modules_structure(self, base_url, admin_headers):
        """Response must include webapp_modules key with a list."""
        resp = requests.get(
            f"{base_url}/api/admin/integrations/crm-mappings",
            headers=admin_headers,
        )
        data = resp.json()
        assert "webapp_modules" in data, f"Missing webapp_modules key in response: {list(data.keys())}"
        assert isinstance(data["webapp_modules"], list), "webapp_modules should be a list"
        print(f"PASS: webapp_modules is a list with {len(data['webapp_modules'])} entries")

    def test_webapp_modules_no_quote_requests(self, base_url, admin_headers):
        """webapp_modules must NOT contain quote_requests entry."""
        resp = requests.get(
            f"{base_url}/api/admin/integrations/crm-mappings",
            headers=admin_headers,
        )
        data = resp.json()
        module_names = [m.get("name") for m in data.get("webapp_modules", [])]
        assert "quote_requests" not in module_names, (
            f"quote_requests still present in webapp_modules: {module_names}"
        )
        print(f"PASS: quote_requests NOT in webapp_modules. Modules: {module_names}")

    def test_webapp_modules_contains_expected_modules(self, base_url, admin_headers):
        """webapp_modules should still have customers, orders, subscriptions."""
        resp = requests.get(
            f"{base_url}/api/admin/integrations/crm-mappings",
            headers=admin_headers,
        )
        data = resp.json()
        module_names = [m.get("name") for m in data.get("webapp_modules", [])]
        for expected in ["customers", "orders", "subscriptions"]:
            assert expected in module_names, f"Expected module '{expected}' missing: {module_names}"
        print(f"PASS: All expected modules present: {module_names}")


# ─── Imports: quote-requests entity should be rejected ────────────────────────

class TestImportsQuoteRequestsRemoved:
    """imports.py — quote-requests removed from ENTITY_COLLECTIONS"""

    def test_import_quote_requests_returns_400(self, base_url, admin_headers):
        """POST /api/admin/import/quote-requests should return 400 (unknown entity)."""
        csv_content = b"email,full_name\nlead@example.com,Test Lead\n"
        files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
        headers_no_ct = {k: v for k, v in admin_headers.items() if k != "Content-Type"}
        resp = requests.post(
            f"{base_url}/api/admin/import/quote-requests",
            headers=headers_no_ct,
            files=files,
        )
        assert resp.status_code in [400, 404, 422], (
            f"Expected 400/404/422 for invalid entity 'quote-requests', got {resp.status_code}: {resp.text}"
        )
        print(f"PASS: POST /api/admin/import/quote-requests returns {resp.status_code}")

    def test_import_quote_requests_error_message(self, base_url, admin_headers):
        """Error response should mention 'Unknown entity' or similar."""
        csv_content = b"email,full_name\nlead@example.com,Test Lead\n"
        files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
        headers_no_ct = {k: v for k, v in admin_headers.items() if k != "Content-Type"}
        resp = requests.post(
            f"{base_url}/api/admin/import/quote-requests",
            headers=headers_no_ct,
            files=files,
        )
        body = resp.text.lower()
        assert any(kw in body for kw in ["unknown", "valid", "not found", "invalid"]), (
            f"Expected error message about unknown entity, got: {resp.text}"
        )
        print(f"PASS: Error message about unknown entity: {resp.text[:200]}")

    def test_import_override_codes_returns_400(self, base_url, admin_headers):
        """POST /api/admin/import/override-codes should return 400 (removed from ENTITY_COLLECTIONS)."""
        csv_content = b"code,type,value\nOVERRIDE123,discount,50\n"
        files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
        headers_no_ct = {k: v for k, v in admin_headers.items() if k != "Content-Type"}
        resp = requests.post(
            f"{base_url}/api/admin/import/override-codes",
            headers=headers_no_ct,
            files=files,
        )
        assert resp.status_code in [400, 404, 422], (
            f"Expected 400/404/422 for 'override-codes', got {resp.status_code}: {resp.text}"
        )
        print(f"PASS: POST /api/admin/import/override-codes returns {resp.status_code}")

    def test_import_valid_entity_still_works(self, base_url, admin_headers):
        """POST /api/admin/import/categories with valid CSV should work (not unknown entity)."""
        csv_content = b"name,description,is_active,display_order\nTEST_Iter121_Category,Test Category for iter121,true,99\n"
        files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
        headers_no_ct = {k: v for k, v in admin_headers.items() if k != "Content-Type"}
        resp = requests.post(
            f"{base_url}/api/admin/import/categories",
            headers=headers_no_ct,
            files=files,
        )
        assert resp.status_code == 200, (
            f"Expected 200 for valid entity 'categories', got {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        assert "created" in data or "updated" in data, f"Unexpected response: {data}"
        print(f"PASS: Valid entity import works: {data}")


# ─── Verify ENTITY_COLLECTIONS completeness ──────────────────────────────────

class TestEntityCollectionsIntegrity:
    """Verify imports endpoint rejects removed entities while accepting valid ones."""

    @pytest.mark.parametrize("entity", ["customers", "orders", "subscriptions", "articles", "catalog"])
    def test_valid_entities_recognized(self, base_url, admin_headers, entity):
        """Valid entities should NOT get 'Unknown entity' 400 error."""
        # Minimal CSV with just headers, no rows
        minimal_csv = b"id,name\n"
        files = {"file": ("test.csv", io.BytesIO(minimal_csv), "text/csv")}
        headers_no_ct = {k: v for k, v in admin_headers.items() if k != "Content-Type"}
        resp = requests.post(
            f"{base_url}/api/admin/import/{entity}",
            headers=headers_no_ct,
            files=files,
        )
        # Should not be 400 with "Unknown entity"
        if resp.status_code == 400:
            body = resp.text.lower()
            assert "unknown entity" not in body, (
                f"Entity '{entity}' incorrectly rejected as unknown: {resp.text}"
            )
        print(f"PASS: Entity '{entity}' recognized (status={resp.status_code})")
