"""
Iteration 81: Zoho CRM & Books Module Mapping UI Tests

Tests the new mapping panel backend endpoints:
- GET /api/oauth/zoho_crm/modules - fetch live modules from Zoho CRM
- GET /api/oauth/zoho_books/modules - return 5 hardcoded modules
- POST /api/oauth/zoho_crm/bulk-sync - bulk sync via saved mappings
- GET /api/admin/integrations/crm-mappings?provider=zoho_crm - filtered mappings
- GET /api/admin/integrations/crm-mappings?provider=zoho_books - books mappings
- POST /api/admin/integrations/crm-mappings - create mapping
- DELETE /api/admin/integrations/crm-mappings/{id} - delete mapping
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

PLATFORM_ADMIN = {
    "email": "admin@automateaccounts.local",
    "password": "ChangeMe123!",
    "partner_code": "automate-accounts"
}


@pytest.fixture(scope="module")
def auth_session():
    """Create a session with auth token for platform admin."""
    session = requests.Session()
    resp = session.post(f"{BASE_URL}/api/auth/login", json=PLATFORM_ADMIN)
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json().get("token")
    if token:
        session.headers.update({"Authorization": f"Bearer {token}"})
    return session


class TestZohoCRMModulesEndpoint:
    """Test GET /api/oauth/zoho_crm/modules - fetch live CRM modules"""

    def test_crm_modules_returns_200(self, auth_session):
        """Verified Zoho CRM should return modules list."""
        resp = auth_session.get(f"{BASE_URL}/api/oauth/zoho_crm/modules")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print(f"PASS: GET /api/oauth/zoho_crm/modules returned 200")

    def test_crm_modules_returns_list(self, auth_session):
        """Should return a list of modules."""
        resp = auth_session.get(f"{BASE_URL}/api/oauth/zoho_crm/modules")
        assert resp.status_code == 200
        data = resp.json()
        assert "modules" in data, f"Missing 'modules' key: {data}"
        modules = data["modules"]
        assert isinstance(modules, list), f"modules should be a list, got {type(modules)}"
        print(f"PASS: Returned {len(modules)} CRM modules")

    def test_crm_modules_have_required_fields(self, auth_session):
        """Each module should have api_name and plural_label."""
        resp = auth_session.get(f"{BASE_URL}/api/oauth/zoho_crm/modules")
        assert resp.status_code == 200
        modules = resp.json().get("modules", [])
        assert len(modules) > 0, "No modules returned - CRM may not be validated"
        for module in modules[:5]:  # Check first 5
            assert "api_name" in module, f"Missing api_name in module: {module}"
            assert "plural_label" in module, f"Missing plural_label in module: {module}"
        print(f"PASS: First 5 modules have required fields")

    def test_crm_modules_count(self, auth_session):
        """Expect many modules (at least 10 from live Zoho CRM)."""
        resp = auth_session.get(f"{BASE_URL}/api/oauth/zoho_crm/modules")
        assert resp.status_code == 200
        modules = resp.json().get("modules", [])
        assert len(modules) >= 10, f"Expected at least 10 CRM modules, got {len(modules)}"
        print(f"PASS: CRM returned {len(modules)} modules (expected 64 from live API)")

    def test_crm_modules_requires_auth(self):
        """Endpoint requires authentication."""
        resp = requests.get(f"{BASE_URL}/api/oauth/zoho_crm/modules")
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"


class TestZohoBooksModulesEndpoint:
    """Test GET /api/oauth/zoho_books/modules - 5 hardcoded modules"""

    def test_books_modules_returns_200(self, auth_session):
        """Should return 200 for validated Zoho Books."""
        resp = auth_session.get(f"{BASE_URL}/api/oauth/zoho_books/modules")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print(f"PASS: GET /api/oauth/zoho_books/modules returned 200")

    def test_books_modules_returns_exactly_5(self, auth_session):
        """Should return exactly 5 hardcoded modules."""
        resp = auth_session.get(f"{BASE_URL}/api/oauth/zoho_books/modules")
        assert resp.status_code == 200
        data = resp.json()
        assert "modules" in data, f"Missing 'modules' key: {data}"
        modules = data["modules"]
        assert len(modules) == 5, f"Expected exactly 5 Books modules, got {len(modules)}: {modules}"
        print(f"PASS: Returned exactly 5 Books modules")

    def test_books_modules_correct_names(self, auth_session):
        """Should contain contacts, invoices, estimates, bills, recurringinvoices."""
        resp = auth_session.get(f"{BASE_URL}/api/oauth/zoho_books/modules")
        assert resp.status_code == 200
        modules = resp.json().get("modules", [])
        api_names = [m["api_name"] for m in modules]
        expected = {"contacts", "invoices", "estimates", "bills", "recurringinvoices"}
        assert set(api_names) == expected, f"Unexpected modules: {api_names}"
        print(f"PASS: Books modules are correct: {api_names}")

    def test_books_modules_have_labels(self, auth_session):
        """Each module should have plural_label and singular_label."""
        resp = auth_session.get(f"{BASE_URL}/api/oauth/zoho_books/modules")
        assert resp.status_code == 200
        for module in resp.json().get("modules", []):
            assert "api_name" in module
            assert "plural_label" in module
            assert "singular_label" in module
        print("PASS: All Books modules have api_name, plural_label, singular_label")


class TestCRMMappingsEndpoint:
    """Test GET & POST /api/admin/integrations/crm-mappings"""

    def test_get_crm_mappings_returns_200(self, auth_session):
        """GET /api/admin/integrations/crm-mappings should return 200."""
        resp = auth_session.get(f"{BASE_URL}/api/admin/integrations/crm-mappings")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print("PASS: GET /api/admin/integrations/crm-mappings returned 200")

    def test_get_crm_mappings_with_provider_filter_zoho_crm(self, auth_session):
        """Filter by provider=zoho_crm should work."""
        resp = auth_session.get(f"{BASE_URL}/api/admin/integrations/crm-mappings?provider=zoho_crm")
        assert resp.status_code == 200
        data = resp.json()
        assert "mappings" in data, f"Missing 'mappings' key: {data}"
        assert "webapp_modules" in data, f"Missing 'webapp_modules' key: {data}"
        print(f"PASS: CRM mappings filter by zoho_crm returned {len(data['mappings'])} mappings")

    def test_get_crm_mappings_with_provider_filter_zoho_books(self, auth_session):
        """Filter by provider=zoho_books should work."""
        resp = auth_session.get(f"{BASE_URL}/api/admin/integrations/crm-mappings?provider=zoho_books")
        assert resp.status_code == 200
        data = resp.json()
        assert "mappings" in data
        assert "webapp_modules" in data
        print(f"PASS: CRM mappings filter by zoho_books returned {len(data['mappings'])} mappings")

    def test_get_crm_mappings_webapp_modules_structure(self, auth_session):
        """webapp_modules should contain 4 modules with correct structure."""
        resp = auth_session.get(f"{BASE_URL}/api/admin/integrations/crm-mappings?provider=zoho_crm")
        assert resp.status_code == 200
        webapp_modules = resp.json().get("webapp_modules", [])
        assert len(webapp_modules) == 4, f"Expected 4 webapp_modules, got {len(webapp_modules)}"
        module_names = [m["name"] for m in webapp_modules]
        expected_names = {"customers", "orders", "subscriptions", "quote_requests"}
        assert set(module_names) == expected_names, f"Unexpected modules: {module_names}"
        for wm in webapp_modules:
            assert "name" in wm
            assert "label" in wm
            assert "fields" in wm
            assert len(wm["fields"]) > 0
        print(f"PASS: webapp_modules correct: {module_names}")

    def test_create_crm_mapping(self, auth_session):
        """POST /api/admin/integrations/crm-mappings creates a new mapping."""
        payload = {
            "webapp_module": "customers",
            "crm_module": "Leads",
            "field_mappings": [
                {"webapp_field": "email", "crm_field": "Email"},
                {"webapp_field": "full_name", "crm_field": "Last_Name"}
            ],
            "sync_on_create": True,
            "sync_on_update": True,
            "is_active": True,
            "provider": "zoho_crm"
        }
        resp = auth_session.post(f"{BASE_URL}/api/admin/integrations/crm-mappings", json=payload)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        # Should return some success indicator or the mapping data
        print(f"PASS: POST /api/admin/integrations/crm-mappings returned 200: {data}")
        return data

    def test_create_and_retrieve_mapping(self, auth_session):
        """Create a mapping then verify it appears in GET."""
        # Create test mapping
        create_resp = auth_session.post(
            f"{BASE_URL}/api/admin/integrations/crm-mappings",
            json={
                "webapp_module": "orders",
                "crm_module": "Deals",
                "field_mappings": [{"webapp_field": "order_number", "crm_field": "Deal_Name"}],
                "sync_on_create": True,
                "sync_on_update": False,
                "is_active": True,
                "provider": "zoho_crm"
            }
        )
        assert create_resp.status_code == 200

        # GET to verify persistence
        get_resp = auth_session.get(f"{BASE_URL}/api/admin/integrations/crm-mappings?provider=zoho_crm")
        assert get_resp.status_code == 200
        mappings = get_resp.json().get("mappings", [])
        found = any(m.get("webapp_module") == "orders" and m.get("crm_module") == "Deals" for m in mappings)
        assert found, f"Created mapping not found in list: {mappings}"
        print("PASS: Created mapping persisted and retrieved correctly")

    def test_delete_crm_mapping(self, auth_session):
        """DELETE /api/admin/integrations/crm-mappings/{id} removes the mapping."""
        # First create a mapping to delete
        create_resp = auth_session.post(
            f"{BASE_URL}/api/admin/integrations/crm-mappings",
            json={
                "webapp_module": "quote_requests",
                "crm_module": "Leads",
                "field_mappings": [{"webapp_field": "email", "crm_field": "Email"}],
                "sync_on_create": True,
                "sync_on_update": True,
                "is_active": True,
                "provider": "zoho_crm"
            }
        )
        assert create_resp.status_code == 200

        # Get all mappings to find the ID
        get_resp = auth_session.get(f"{BASE_URL}/api/admin/integrations/crm-mappings?provider=zoho_crm")
        mappings = get_resp.json().get("mappings", [])
        to_delete = next((m for m in mappings if m.get("webapp_module") == "quote_requests"), None)
        assert to_delete, "Could not find the newly created mapping"

        mapping_id = to_delete.get("id")
        assert mapping_id, "Mapping has no id field"

        # Delete it
        del_resp = auth_session.delete(f"{BASE_URL}/api/admin/integrations/crm-mappings/{mapping_id}")
        assert del_resp.status_code == 200, f"Delete failed: {del_resp.text}"
        
        # Verify it's gone
        verify_resp = auth_session.get(f"{BASE_URL}/api/admin/integrations/crm-mappings?provider=zoho_crm")
        remaining = verify_resp.json().get("mappings", [])
        still_exists = any(m.get("id") == mapping_id for m in remaining)
        assert not still_exists, "Mapping was not deleted"
        print(f"PASS: Mapping {mapping_id} deleted and verified removed")


class TestBulkSyncEndpoint:
    """Test POST /api/oauth/zoho_crm/bulk-sync"""

    def test_bulk_sync_no_mappings_returns_appropriate_response(self, auth_session):
        """Bulk sync with no active mappings returns a message (not an error)."""
        # Clean up test mappings first
        get_resp = auth_session.get(f"{BASE_URL}/api/admin/integrations/crm-mappings?provider=zoho_crm")
        mappings = get_resp.json().get("mappings", [])
        for m in mappings:
            mid = m.get("id")
            if mid:
                auth_session.delete(f"{BASE_URL}/api/admin/integrations/crm-mappings/{mid}")

        resp = auth_session.post(f"{BASE_URL}/api/oauth/zoho_crm/bulk-sync")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "success" in data, f"Missing 'success' key: {data}"
        assert "message" in data, f"Missing 'message' key: {data}"
        # Should return success=False with no mappings, not crash
        if data.get("success") == False:
            assert "mapping" in data["message"].lower() or "no" in data["message"].lower()
        print(f"PASS: Bulk sync with no mappings returned: {data}")

    def test_bulk_sync_with_active_mapping(self, auth_session):
        """Bulk sync with an active mapping completes (may sync 0 if no records)."""
        # Create a test mapping
        auth_session.post(
            f"{BASE_URL}/api/admin/integrations/crm-mappings",
            json={
                "webapp_module": "customers",
                "crm_module": "Leads",
                "field_mappings": [
                    {"webapp_field": "email", "crm_field": "Email"},
                    {"webapp_field": "full_name", "crm_field": "Last_Name"}
                ],
                "sync_on_create": True,
                "sync_on_update": True,
                "is_active": True,
                "provider": "zoho_crm"
            }
        )

        resp = auth_session.post(f"{BASE_URL}/api/oauth/zoho_crm/bulk-sync")
        assert resp.status_code == 200, f"Bulk sync failed: {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "success" in data
        assert "message" in data
        # May have synced, or may have errors — but endpoint should respond
        print(f"PASS: Bulk sync with mapping returned: success={data.get('success')}, message={data.get('message')}")

    def test_bulk_sync_requires_auth(self):
        """Bulk sync endpoint requires authentication."""
        resp = requests.post(f"{BASE_URL}/api/oauth/zoho_crm/bulk-sync")
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"


class TestIntegrationStatusForZoho:
    """Verify Zoho CRM and Books are validated in the integrations list"""

    def test_zoho_crm_is_validated(self, auth_session):
        """Zoho CRM integration should show is_validated=True."""
        resp = auth_session.get(f"{BASE_URL}/api/oauth/integrations")
        assert resp.status_code == 200
        integrations = {i["id"]: i for i in resp.json()["integrations"]}
        crm = integrations.get("zoho_crm")
        assert crm, "zoho_crm not found in integrations list"
        assert crm.get("is_validated") == True, f"zoho_crm not validated: {crm}"
        print(f"PASS: zoho_crm is_validated=True, status={crm.get('status')}")

    def test_zoho_books_is_validated(self, auth_session):
        """Zoho Books integration should show is_validated=True."""
        resp = auth_session.get(f"{BASE_URL}/api/oauth/integrations")
        assert resp.status_code == 200
        integrations = {i["id"]: i for i in resp.json()["integrations"]}
        books = integrations.get("zoho_books")
        assert books, "zoho_books not found in integrations list"
        assert books.get("is_validated") == True, f"zoho_books not validated: {books}"
        print(f"PASS: zoho_books is_validated=True, status={books.get('status')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
