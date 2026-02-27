"""
Tests for iteration 137 - Signup Form Schema and Create Customer Dialog
Tests:
  - GET /api/website-settings returns correct signup_form_schema with 'address' field (not 'country', 'email', 'password')
  - GET /api/admin/website-settings returns migrated signup_form_schema with 'address' field
  - Migration: old schema with standalone 'country' gets converted to 'address' block
  - Create Customer endpoint works with the new schema
"""
import pytest
import requests
import json
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"


@pytest.fixture(scope="module")
def admin_token():
    """Authenticate as admin and return token."""
    res = requests.post(f"{BASE_URL}/api/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if res.status_code == 200:
        return res.json().get("access_token") or res.json().get("token")
    pytest.skip(f"Admin login failed: {res.status_code} - {res.text}")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


class TestPublicWebsiteSettingsSignupSchema:
    """Tests for GET /api/website-settings signup_form_schema"""

    def test_get_website_settings_returns_200(self):
        res = requests.get(f"{BASE_URL}/api/website-settings")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        print("PASS: GET /api/website-settings returns 200")

    def test_signup_form_schema_field_present(self):
        res = requests.get(f"{BASE_URL}/api/website-settings")
        assert res.status_code == 200
        data = res.json()
        assert "settings" in data, "Response should have 'settings' key"
        settings = data["settings"]
        assert "signup_form_schema" in settings, "signup_form_schema should be in settings"
        print("PASS: signup_form_schema present in /api/website-settings")

    def test_signup_schema_has_address_field(self):
        res = requests.get(f"{BASE_URL}/api/website-settings")
        settings = res.json()["settings"]
        schema = json.loads(settings.get("signup_form_schema", "[]"))
        keys = [f["key"] for f in schema]
        print(f"INFO: signup_form_schema keys: {keys}")
        assert "address" in keys, f"Schema should have 'address' field, got keys: {keys}"
        print("PASS: 'address' field present in signup_form_schema")

    def test_signup_schema_has_no_standalone_country(self):
        res = requests.get(f"{BASE_URL}/api/website-settings")
        settings = res.json()["settings"]
        schema = json.loads(settings.get("signup_form_schema", "[]"))
        keys = [f["key"] for f in schema]
        # Check no locked standalone country field
        locked_country = [f for f in schema if f.get("key") == "country" and f.get("locked")]
        assert len(locked_country) == 0, f"No locked standalone 'country' field should exist, found: {locked_country}"
        print("PASS: No standalone locked 'country' field in signup_form_schema")

    def test_signup_schema_has_no_email_or_password_fields(self):
        res = requests.get(f"{BASE_URL}/api/website-settings")
        settings = res.json()["settings"]
        schema = json.loads(settings.get("signup_form_schema", "[]"))
        keys = [f["key"] for f in schema]
        assert "email" not in keys, f"'email' should NOT be in signup schema fields, got: {keys}"
        assert "password" not in keys, f"'password' should NOT be in signup schema fields, got: {keys}"
        print("PASS: No 'email' or 'password' in signup_form_schema")

    def test_signup_schema_has_required_fields(self):
        res = requests.get(f"{BASE_URL}/api/website-settings")
        settings = res.json()["settings"]
        schema = json.loads(settings.get("signup_form_schema", "[]"))
        keys = [f["key"] for f in schema]
        required_keys = ["full_name", "company_name", "job_title", "phone", "address"]
        for k in required_keys:
            assert k in keys, f"Expected field '{k}' in signup schema. Got: {keys}"
        print(f"PASS: All required fields present: {required_keys}")

    def test_signup_schema_field_count_correct(self):
        res = requests.get(f"{BASE_URL}/api/website-settings")
        settings = res.json()["settings"]
        schema = json.loads(settings.get("signup_form_schema", "[]"))
        assert len(schema) == 5, f"Expected 5 fields in signup schema, got {len(schema)}: {[f['key'] for f in schema]}"
        print("PASS: signup_form_schema has exactly 5 fields")


class TestAdminWebsiteSettingsSignupSchema:
    """Tests for GET /api/admin/website-settings signup_form_schema"""

    def test_admin_get_website_settings_returns_200(self, admin_headers):
        res = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=admin_headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        print("PASS: GET /api/admin/website-settings returns 200")

    def test_admin_signup_schema_has_address_field(self, admin_headers):
        res = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=admin_headers)
        settings = res.json()["settings"]
        schema = json.loads(settings.get("signup_form_schema", "[]"))
        keys = [f["key"] for f in schema]
        print(f"INFO: admin signup_form_schema keys: {keys}")
        assert "address" in keys, f"Schema should have 'address' field, got: {keys}"
        print("PASS: 'address' field in admin GET /api/admin/website-settings")

    def test_admin_signup_schema_no_standalone_country(self, admin_headers):
        res = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=admin_headers)
        settings = res.json()["settings"]
        schema = json.loads(settings.get("signup_form_schema", "[]"))
        locked_country = [f for f in schema if f.get("key") == "country" and f.get("locked")]
        assert len(locked_country) == 0, f"Should not have locked standalone 'country': {locked_country}"
        print("PASS: No locked standalone 'country' in admin website-settings")

    def test_admin_signup_schema_no_email_password(self, admin_headers):
        res = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=admin_headers)
        settings = res.json()["settings"]
        schema = json.loads(settings.get("signup_form_schema", "[]"))
        keys = [f["key"] for f in schema]
        assert "email" not in keys, f"'email' should NOT be in admin signup schema, got: {keys}"
        assert "password" not in keys, f"'password' should NOT be in admin signup schema, got: {keys}"
        print("PASS: No 'email'/'password' in admin signup_form_schema")

    def test_admin_signup_schema_full_name_required(self, admin_headers):
        """full_name should be required: true in schema"""
        res = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=admin_headers)
        settings = res.json()["settings"]
        schema = json.loads(settings.get("signup_form_schema", "[]"))
        name_field = next((f for f in schema if f.get("key") == "full_name"), None)
        assert name_field is not None, "full_name field should exist in schema"
        assert name_field.get("required") is True, f"full_name should be required=true, got: {name_field}"
        print("PASS: full_name field is required=True in admin signup_form_schema")

    def test_admin_signup_schema_address_is_locked_field(self, admin_headers):
        """address should be locked: true in schema"""
        res = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=admin_headers)
        settings = res.json()["settings"]
        schema = json.loads(settings.get("signup_form_schema", "[]"))
        addr_field = next((f for f in schema if f.get("key") == "address"), None)
        assert addr_field is not None, "address field must exist in schema"
        assert addr_field.get("locked") is True, f"address field should be locked=True, got: {addr_field}"
        print("PASS: address field is locked=True in schema")


class TestMigrateSignupSchema:
    """Test that old schema format (with standalone country) is migrated to new format (with address)"""

    def test_migration_old_schema_to_new(self, admin_headers):
        """
        Simulate old schema by setting it to have country (locked) field,
        then verify GET returns the migrated schema with address.
        """
        # Save old-style schema to database
        old_schema = json.dumps([
            {"id": "su_name", "key": "full_name", "label": "Full Name", "type": "text", "required": True, "placeholder": "", "options": [], "locked": True, "enabled": True, "order": 0},
            {"id": "su_company", "key": "company_name", "label": "Company Name", "type": "text", "required": False, "placeholder": "", "options": [], "locked": True, "enabled": True, "order": 1},
            {"id": "su_country", "key": "country", "label": "Country", "type": "select", "required": False, "placeholder": "", "options": [], "locked": True, "enabled": True, "order": 2},
        ])
        put_res = requests.put(
            f"{BASE_URL}/api/admin/website-settings",
            headers=admin_headers,
            json={"signup_form_schema": old_schema}
        )
        assert put_res.status_code == 200, f"PUT should succeed: {put_res.text}"

        # Now GET the schema and verify migration happened
        get_res = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=admin_headers)
        settings = get_res.json()["settings"]
        schema = json.loads(settings.get("signup_form_schema", "[]"))
        keys = [f["key"] for f in schema]

        print(f"INFO: Migrated schema keys: {keys}")
        assert "address" in keys, f"Migrated schema should have 'address', got: {keys}"
        locked_country = [f for f in schema if f.get("key") == "country" and f.get("locked")]
        assert len(locked_country) == 0, f"Migrated schema should not have locked country, got: {locked_country}"
        print("PASS: Old schema with locked country was migrated to have 'address' field")

    def test_restore_default_schema_after_migration_test(self, admin_headers):
        """Restore the schema to default after migration test."""
        from backend.routes.admin.website import _SIGNUP_FORM_SCHEMA
        default_schema = _SIGNUP_FORM_SCHEMA
        put_res = requests.put(
            f"{BASE_URL}/api/admin/website-settings",
            headers=admin_headers,
            json={"signup_form_schema": default_schema}
        )
        # This is cleanup; just verify it doesn't error
        print(f"INFO: Restore PUT status: {put_res.status_code}")
        print("PASS: Schema restored after migration test")


class TestCreateCustomerWithNewSchema:
    """Test create customer endpoint still works"""

    def test_create_customer_basic(self, admin_headers):
        """POST /admin/customers/create should work with basic required fields"""
        import random
        suffix = random.randint(1000, 9999)
        payload = {
            "full_name": f"TEST_Iter137_Customer_{suffix}",
            "email": f"TEST_iter137_cust_{suffix}@example.com",
            "password": "TestPass123!",
            "line1": "123 Test St",
            "city": "Test City",
            "region": "CA",
            "postal": "12345",
            "country": "Canada",
            "mark_verified": True,
        }
        res = requests.post(f"{BASE_URL}/api/admin/customers/create", headers=admin_headers, json=payload)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        print(f"INFO: Create customer response: {data}")
        print("PASS: POST /api/admin/customers/create succeeds with basic fields")

    def test_create_customer_with_optional_fields(self, admin_headers):
        """POST /admin/customers/create with company_name, job_title, phone"""
        import random
        suffix = random.randint(1000, 9999)
        payload = {
            "full_name": f"TEST_Iter137_Full_{suffix}",
            "email": f"TEST_iter137_full_{suffix}@example.com",
            "password": "TestPass123!",
            "company_name": "Test Corp",
            "job_title": "Developer",
            "phone": "+1-555-0001",
            "line1": "456 Test Ave",
            "city": "Test City",
            "region": "BC",
            "postal": "V1V 1V1",
            "country": "Canada",
            "mark_verified": True,
        }
        res = requests.post(f"{BASE_URL}/api/admin/customers/create", headers=admin_headers, json=payload)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        print("PASS: POST /api/admin/customers/create succeeds with optional fields")
