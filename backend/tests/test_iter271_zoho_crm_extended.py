"""
Iteration 271: Extended Zoho CRM integration tests.
Tests: 13 webapp_modules, products 19 fields, multiple mappings per module.
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"

EXPECTED_MODULES = [
    "customers", "orders", "subscriptions", "products", "enquiries",
    "invoices", "resources", "plans", "categories", "terms",
    "promo_codes", "refunds", "addresses"
]

EXPECTED_PRODUCT_FIELDS = [
    "name", "card_tag", "card_description", "description", "category", "base_price",
    "is_subscription", "is_active", "currency", "pricing_type", "billing_type",
    "default_term_months", "display_layout", "visible_to_customers", "show_price_breakdown",
    "intake_questions_count", "intake_questions_labels", "intake_questions_json", "created_at"
]

# Created mapping IDs to clean up after tests
_created_mapping_ids = []


@pytest.fixture(scope="module")
def admin_token():
    """Authenticate as platform admin and return JWT token."""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    token = response.json().get("token") or response.json().get("access_token")
    assert token, f"No token in response: {response.json()}"
    return token


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


class TestBackendHealth:
    """Verify backend starts and responds"""

    def test_health_check(self):
        resp = requests.get(f"{BASE_URL}/api/health", timeout=5)
        assert resp.status_code in [200, 404], f"Backend unreachable: {resp.status_code}"
        print("Backend health check passed")

    def test_admin_login(self, admin_token):
        assert admin_token, "Admin token should be non-empty"
        print(f"Admin login successful, token present: {bool(admin_token)}")


class TestCRMMappingsAPI:
    """Test GET /api/admin/integrations/crm-mappings for 13 webapp_modules"""

    def test_crm_mappings_returns_200(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/integrations/crm-mappings", headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200 got {resp.status_code}: {resp.text}"
        print("GET /api/admin/integrations/crm-mappings returned 200 OK")

    def test_crm_mappings_has_webapp_modules_key(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/integrations/crm-mappings", headers=auth_headers)
        data = resp.json()
        assert "webapp_modules" in data, f"Missing 'webapp_modules' key in response: {list(data.keys())}"
        print(f"Response keys: {list(data.keys())}")

    def test_crm_mappings_has_exactly_13_modules(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/integrations/crm-mappings", headers=auth_headers)
        data = resp.json()
        modules = data.get("webapp_modules", [])
        module_names = [m["name"] for m in modules]
        print(f"Found {len(modules)} webapp_modules: {module_names}")
        assert len(modules) == 13, f"Expected 13 webapp_modules, got {len(modules)}: {module_names}"

    def test_crm_mappings_all_expected_modules_present(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/integrations/crm-mappings", headers=auth_headers)
        data = resp.json()
        modules = data.get("webapp_modules", [])
        module_names = [m["name"] for m in modules]
        missing = [m for m in EXPECTED_MODULES if m not in module_names]
        assert not missing, f"Missing modules: {missing}. Found: {module_names}"
        print(f"All 13 expected modules present: {module_names}")

    def test_products_module_has_19_fields(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/integrations/crm-mappings", headers=auth_headers)
        data = resp.json()
        modules = data.get("webapp_modules", [])
        products_mod = next((m for m in modules if m["name"] == "products"), None)
        assert products_mod is not None, "Products module not found in webapp_modules"
        fields = products_mod.get("fields", [])
        print(f"Products module fields ({len(fields)}): {fields}")
        assert len(fields) == 19, f"Expected 19 fields for products, got {len(fields)}: {fields}"

    def test_products_module_has_intake_fields(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/integrations/crm-mappings", headers=auth_headers)
        data = resp.json()
        modules = data.get("webapp_modules", [])
        products_mod = next((m for m in modules if m["name"] == "products"), None)
        assert products_mod is not None, "Products module not found"
        fields = products_mod.get("fields", [])
        # Check the 3 derived intake fields
        for intake_field in ["intake_questions_count", "intake_questions_labels", "intake_questions_json"]:
            assert intake_field in fields, f"Missing intake field '{intake_field}' in products. Found: {fields}"
        print("All 3 intake fields present: intake_questions_count, intake_questions_labels, intake_questions_json")

    def test_products_module_exact_fields_match(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/integrations/crm-mappings", headers=auth_headers)
        data = resp.json()
        modules = data.get("webapp_modules", [])
        products_mod = next((m for m in modules if m["name"] == "products"), None)
        assert products_mod is not None
        fields = set(products_mod.get("fields", []))
        expected_set = set(EXPECTED_PRODUCT_FIELDS)
        missing = expected_set - fields
        extra = fields - expected_set
        assert not missing, f"Products missing fields: {missing}"
        if extra:
            print(f"Products has extra fields (OK): {extra}")
        print(f"Products exact fields match verified: {sorted(fields)}")

    def test_all_modules_have_label_and_fields(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/integrations/crm-mappings", headers=auth_headers)
        data = resp.json()
        modules = data.get("webapp_modules", [])
        for mod in modules:
            assert "name" in mod, f"Module missing 'name': {mod}"
            assert "label" in mod, f"Module '{mod.get('name')}' missing 'label'"
            assert "fields" in mod, f"Module '{mod.get('name')}' missing 'fields'"
            assert len(mod["fields"]) > 0, f"Module '{mod.get('name')}' has no fields"
        print("All modules have name, label, fields")

    def test_response_has_mappings_key(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/integrations/crm-mappings", headers=auth_headers)
        data = resp.json()
        assert "mappings" in data, f"Response missing 'mappings' key: {list(data.keys())}"
        assert isinstance(data["mappings"], list), "mappings should be a list"
        print(f"mappings key present, count: {len(data['mappings'])}")


class TestMultipleMappingsPerModule:
    """
    Test that multiple mappings can be created for the same webapp_module
    (customers→Leads AND customers→Contacts) without error.
    """

    def _create_mapping(self, auth_headers, webapp_module, crm_module):
        unique_id = str(uuid.uuid4())
        resp = requests.post(
            f"{BASE_URL}/api/admin/integrations/crm-mappings",
            json={
                "webapp_module": webapp_module,
                "crm_module": crm_module,
                "field_mappings": [
                    {"webapp_field": "email", "crm_field": "Email"},
                    {"webapp_field": "full_name", "crm_field": "Last_Name"},
                ],
                "sync_on_create": True,
                "sync_on_update": True,
                "is_active": True,
                "provider": "zoho_crm",
            },
            headers=auth_headers,
        )
        return resp

    def test_create_first_mapping_customers_leads(self, auth_headers):
        resp = self._create_mapping(auth_headers, "customers", "TEST_Leads_271")
        assert resp.status_code == 200, f"Failed to create mapping: {resp.text}"
        data = resp.json()
        assert data.get("success") is True, f"Expected success=True: {data}"
        mapping = data.get("mapping", {})
        mapping_id = mapping.get("id")
        if mapping_id:
            _created_mapping_ids.append(mapping_id)
        print(f"First mapping (customers→TEST_Leads_271) created, id={mapping_id}")

    def test_create_second_mapping_customers_contacts(self, auth_headers):
        """Second mapping for same webapp_module but different CRM module."""
        resp = self._create_mapping(auth_headers, "customers", "TEST_Contacts_271")
        assert resp.status_code == 200, f"Failed to create second mapping: {resp.text}"
        data = resp.json()
        assert data.get("success") is True, f"Expected success=True: {data}"
        mapping = data.get("mapping", {})
        mapping_id = mapping.get("id")
        if mapping_id:
            _created_mapping_ids.append(mapping_id)
        print(f"Second mapping (customers→TEST_Contacts_271) created, id={mapping_id}")

    def test_both_mappings_exist_in_list(self, auth_headers):
        """Verify both customers→TEST_Leads_271 and customers→TEST_Contacts_271 are returned."""
        resp = requests.get(f"{BASE_URL}/api/admin/integrations/crm-mappings", headers=auth_headers)
        assert resp.status_code == 200
        mappings = resp.json().get("mappings", [])
        customer_mappings = [m for m in mappings if m["webapp_module"] == "customers"]
        crm_modules_for_customers = [m["crm_module"] for m in customer_mappings]
        print(f"Customer mappings found: {crm_modules_for_customers}")
        assert "TEST_Leads_271" in crm_modules_for_customers, \
            f"TEST_Leads_271 mapping not found. Found: {crm_modules_for_customers}"
        assert "TEST_Contacts_271" in crm_modules_for_customers, \
            f"TEST_Contacts_271 mapping not found. Found: {crm_modules_for_customers}"
        print(f"Multiple mappings for 'customers' module verified: {crm_modules_for_customers}")

    def test_cleanup_test_mappings(self, auth_headers):
        """Delete test mappings created during this test run."""
        # Get all mappings and find TEST_ ones
        resp = requests.get(f"{BASE_URL}/api/admin/integrations/crm-mappings", headers=auth_headers)
        if resp.status_code != 200:
            return
        mappings = resp.json().get("mappings", [])
        test_mappings = [m for m in mappings if "TEST_" in m.get("crm_module", "")]
        deleted = 0
        for m in test_mappings:
            mid = m.get("id")
            if mid:
                del_resp = requests.delete(
                    f"{BASE_URL}/api/admin/integrations/crm-mappings/{mid}",
                    headers=auth_headers
                )
                if del_resp.status_code == 200:
                    deleted += 1
        print(f"Cleaned up {deleted} test mappings")


class TestCRMMappingsCRUD:
    """Basic CRUD for CRM mappings"""

    def test_create_products_mapping(self, auth_headers):
        resp = requests.post(
            f"{BASE_URL}/api/admin/integrations/crm-mappings",
            json={
                "webapp_module": "products",
                "crm_module": "TEST_Products_271",
                "field_mappings": [
                    {"webapp_field": "name", "crm_field": "Product_Name"},
                    {"webapp_field": "intake_questions_count", "crm_field": "Qty_in_Stock"},
                    {"webapp_field": "intake_questions_labels", "crm_field": "Description"},
                    {"webapp_field": "intake_questions_json", "crm_field": "CF_Intake"},
                ],
                "sync_on_create": True,
                "sync_on_update": True,
                "is_active": True,
                "provider": "zoho_crm",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"Failed to create products mapping: {resp.text}"
        data = resp.json()
        assert data.get("success") is True
        mapping = data.get("mapping", {})
        assert mapping.get("webapp_module") == "products"
        assert mapping.get("crm_module") == "TEST_Products_271"
        _created_mapping_ids.append(mapping.get("id"))
        print(f"Products mapping with intake fields created: {mapping.get('id')}")

    def test_delete_products_mapping(self, auth_headers):
        """Cleanup the products test mapping."""
        resp = requests.get(f"{BASE_URL}/api/admin/integrations/crm-mappings", headers=auth_headers)
        mappings = resp.json().get("mappings", [])
        test_m = next((m for m in mappings if m.get("crm_module") == "TEST_Products_271"), None)
        if not test_m:
            print("Products test mapping already cleaned up")
            return
        mid = test_m.get("id")
        del_resp = requests.delete(
            f"{BASE_URL}/api/admin/integrations/crm-mappings/{mid}",
            headers=auth_headers,
        )
        assert del_resp.status_code == 200, f"Delete failed: {del_resp.text}"
        data = del_resp.json()
        assert data.get("success") is True
        print(f"Products test mapping deleted: {mid}")

    def test_delete_nonexistent_mapping_returns_not_success(self, auth_headers):
        """Deleting a non-existent mapping should return success=False."""
        fake_id = str(uuid.uuid4())
        resp = requests.delete(
            f"{BASE_URL}/api/admin/integrations/crm-mappings/{fake_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is False, f"Expected success=False for non-existent: {data}"
        print("Non-existent mapping delete returns success=False as expected")
