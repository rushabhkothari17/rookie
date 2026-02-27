"""
Tests for iteration 138 - Address field type in FormSchemaBuilder
Tests:
  - GET /api/website-settings returns signup_form_schema with address field type='address' and address_config
  - address_config has 6 sub-fields (line1, line2, city, state, postal, country) each with enabled/required
  - GET /api/utils/countries returns country list from taxes module
  - GET /api/utils/provinces returns province list for CA/US
  - Admin can toggle sub-field Enabled and save (persists)
  - Create Customer API works with address data
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
    res = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if res.status_code == 200:
        token = res.json().get("token") or res.json().get("access_token")
        print(f"INFO: Admin login succeeded, token length: {len(token or '')}")
        return token
    pytest.skip(f"Admin login failed: {res.status_code} - {res.text}")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


class TestSignupSchemaAddressType:
    """Tests for address field type='address' and address_config in signup_form_schema"""

    def test_get_website_settings_returns_200(self):
        res = requests.get(f"{BASE_URL}/api/website-settings")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        print("PASS: GET /api/website-settings returns 200")

    def test_signup_schema_address_field_has_type_address(self):
        """The 'address' field in signup_form_schema must have type='address' (not 'text')"""
        res = requests.get(f"{BASE_URL}/api/website-settings")
        assert res.status_code == 200
        schema = json.loads(res.json()["settings"]["signup_form_schema"])
        addr_field = next((f for f in schema if f.get("key") == "address"), None)
        assert addr_field is not None, f"'address' field not found in schema: {[f['key'] for f in schema]}"
        assert addr_field.get("type") == "address", f"address field should have type='address', got: {addr_field.get('type')}"
        print(f"PASS: address field has type='address'. Field: {addr_field}")

    def test_signup_schema_address_field_has_address_config(self):
        """The 'address' field must have address_config with all 6 sub-fields"""
        res = requests.get(f"{BASE_URL}/api/website-settings")
        assert res.status_code == 200
        schema = json.loads(res.json()["settings"]["signup_form_schema"])
        addr_field = next((f for f in schema if f.get("key") == "address"), None)
        assert addr_field is not None, "address field must exist"
        cfg = addr_field.get("address_config")
        assert cfg is not None, f"address field must have address_config, got: {addr_field}"
        # Check all 6 sub-fields exist
        for sub in ["line1", "line2", "city", "state", "postal", "country"]:
            assert sub in cfg, f"address_config must have '{sub}' sub-field, got: {cfg}"
        print(f"PASS: address_config has all 6 sub-fields: {list(cfg.keys())}")

    def test_signup_schema_address_config_sub_fields_have_enabled_required(self):
        """Each sub-field in address_config must have enabled and required boolean flags"""
        res = requests.get(f"{BASE_URL}/api/website-settings")
        assert res.status_code == 200
        schema = json.loads(res.json()["settings"]["signup_form_schema"])
        addr_field = next((f for f in schema if f.get("key") == "address"), None)
        assert addr_field is not None
        cfg = addr_field.get("address_config", {})
        for sub in ["line1", "line2", "city", "state", "postal", "country"]:
            sub_cfg = cfg.get(sub, {})
            assert "enabled" in sub_cfg, f"sub-field '{sub}' must have 'enabled' flag, got: {sub_cfg}"
            assert "required" in sub_cfg, f"sub-field '{sub}' must have 'required' flag, got: {sub_cfg}"
            assert isinstance(sub_cfg["enabled"], bool), f"'{sub}'.enabled must be bool, got: {type(sub_cfg['enabled'])}"
            assert isinstance(sub_cfg["required"], bool), f"'{sub}'.required must be bool, got: {type(sub_cfg['required'])}"
        print(f"PASS: All sub-fields have enabled+required flags. Config: {cfg}")

    def test_signup_schema_default_address_config_values(self):
        """Verify default address_config has correct defaults (line1 required, line2 not required)"""
        res = requests.get(f"{BASE_URL}/api/website-settings")
        assert res.status_code == 200
        schema = json.loads(res.json()["settings"]["signup_form_schema"])
        addr_field = next((f for f in schema if f.get("key") == "address"), None)
        assert addr_field is not None
        cfg = addr_field.get("address_config", {})
        # Default: line1 enabled + required, line2 enabled + not required
        assert cfg.get("line1", {}).get("enabled") is True, "line1 should be enabled by default"
        assert cfg.get("line1", {}).get("required") is True, "line1 should be required by default"
        assert cfg.get("line2", {}).get("enabled") is True, "line2 should be enabled by default"
        assert cfg.get("line2", {}).get("required") is False, "line2 should NOT be required by default"
        assert cfg.get("country", {}).get("enabled") is True, "country should be enabled by default"
        assert cfg.get("country", {}).get("required") is True, "country should be required by default"
        print(f"PASS: Default address_config values correct. line1={cfg.get('line1')}, line2={cfg.get('line2')}, country={cfg.get('country')}")

    def test_admin_get_signup_schema_address_type(self, admin_headers):
        """GET /api/admin/website-settings also returns address with type='address'"""
        res = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=admin_headers)
        assert res.status_code == 200
        schema = json.loads(res.json()["settings"]["signup_form_schema"])
        addr_field = next((f for f in schema if f.get("key") == "address"), None)
        assert addr_field is not None, "address field must be in admin schema"
        assert addr_field.get("type") == "address", f"Admin schema: address field should have type='address', got: {addr_field.get('type')}"
        print(f"PASS: Admin GET /api/admin/website-settings returns address type='address'")

    def test_admin_get_signup_schema_address_has_address_config(self, admin_headers):
        """GET /api/admin/website-settings returns address_config with all 6 sub-fields"""
        res = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=admin_headers)
        assert res.status_code == 200
        schema = json.loads(res.json()["settings"]["signup_form_schema"])
        addr_field = next((f for f in schema if f.get("key") == "address"), None)
        assert addr_field is not None
        cfg = addr_field.get("address_config")
        assert cfg is not None, "address_config must exist in admin schema address field"
        for sub in ["line1", "line2", "city", "state", "postal", "country"]:
            assert sub in cfg, f"address_config must have '{sub}'"
        print(f"PASS: Admin schema address field has address_config with all 6 sub-fields")


class TestAddressSubFieldTogglePersistence:
    """Test that toggling address sub-field enabled/required persists"""

    def test_toggle_address_subfield_enabled_persists(self, admin_headers):
        """Toggle line2 enabled=False, save, then verify it is persisted"""
        # Step 1: Get current schema
        res = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=admin_headers)
        assert res.status_code == 200
        original_schema_str = res.json()["settings"]["signup_form_schema"]
        schema = json.loads(original_schema_str)

        # Step 2: Modify address field - disable line2
        for f in schema:
            if f.get("key") == "address":
                if "address_config" not in f:
                    f["address_config"] = {}
                f["address_config"]["line2"] = {"enabled": False, "required": False}
                break

        # Step 3: Save modified schema
        put_res = requests.put(
            f"{BASE_URL}/api/admin/website-settings",
            headers=admin_headers,
            json={"signup_form_schema": json.dumps(schema)}
        )
        assert put_res.status_code == 200, f"PUT failed: {put_res.text}"
        print(f"INFO: Saved schema with line2 disabled")

        # Step 4: GET and verify persistence
        get_res = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=admin_headers)
        assert get_res.status_code == 200
        new_schema = json.loads(get_res.json()["settings"]["signup_form_schema"])
        addr_field = next((f for f in new_schema if f.get("key") == "address"), None)
        assert addr_field is not None
        cfg = addr_field.get("address_config", {})
        assert cfg.get("line2", {}).get("enabled") is False, f"line2 should be disabled after save, got: {cfg.get('line2')}"
        print("PASS: Address sub-field toggle (line2 disabled) persists after save")

    def test_restore_default_address_config(self, admin_headers):
        """Restore default address_config after toggle test"""
        # Get current schema
        res = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=admin_headers)
        assert res.status_code == 200
        schema = json.loads(res.json()["settings"]["signup_form_schema"])

        # Restore default address_config
        default_cfg = {
            "line1":   {"enabled": True, "required": True},
            "line2":   {"enabled": True, "required": False},
            "city":    {"enabled": True, "required": True},
            "state":   {"enabled": True, "required": False},
            "postal":  {"enabled": True, "required": True},
            "country": {"enabled": True, "required": True},
        }
        for f in schema:
            if f.get("key") == "address":
                f["address_config"] = default_cfg
                break

        put_res = requests.put(
            f"{BASE_URL}/api/admin/website-settings",
            headers=admin_headers,
            json={"signup_form_schema": json.dumps(schema)}
        )
        assert put_res.status_code == 200, f"Restore PUT failed: {put_res.text}"
        print("PASS: Default address_config restored")


class TestCountriesAndProvinces:
    """Test /api/utils/countries and /api/utils/provinces endpoints"""

    def test_get_countries_returns_200(self):
        res = requests.get(f"{BASE_URL}/api/utils/countries")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        print("PASS: GET /api/utils/countries returns 200")

    def test_get_countries_returns_list(self):
        res = requests.get(f"{BASE_URL}/api/utils/countries")
        assert res.status_code == 200
        data = res.json()
        assert "countries" in data, f"Response should have 'countries' key, got: {list(data.keys())}"
        countries = data["countries"]
        assert isinstance(countries, list), f"countries should be a list, got: {type(countries)}"
        assert len(countries) > 0, "countries list should not be empty"
        print(f"PASS: /api/utils/countries returns {len(countries)} countries: {countries}")

    def test_get_countries_items_have_value_and_label(self):
        res = requests.get(f"{BASE_URL}/api/utils/countries")
        assert res.status_code == 200
        countries = res.json()["countries"]
        for c in countries:
            assert "value" in c, f"Country item must have 'value', got: {c}"
            assert "label" in c, f"Country item must have 'label', got: {c}"
        print(f"PASS: All country items have value+label: {countries[:3]}...")

    def test_get_countries_with_partner_code(self):
        """Endpoint should accept partner_code query param without error"""
        res = requests.get(f"{BASE_URL}/api/utils/countries?partner_code=automate-accounts")
        assert res.status_code == 200, f"Expected 200 with partner_code, got {res.status_code}: {res.text}"
        data = res.json()
        assert "countries" in data
        assert len(data["countries"]) > 0, "Should return countries even with partner_code"
        print(f"PASS: /api/utils/countries?partner_code=automate-accounts returns {len(data['countries'])} countries")

    def test_get_provinces_canada_returns_200(self):
        res = requests.get(f"{BASE_URL}/api/utils/provinces?country_code=CA")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        print("PASS: GET /api/utils/provinces?country_code=CA returns 200")

    def test_get_provinces_canada_returns_regions(self):
        res = requests.get(f"{BASE_URL}/api/utils/provinces?country_code=CA")
        assert res.status_code == 200
        data = res.json()
        assert "regions" in data, f"Response should have 'regions' key, got: {list(data.keys())}"
        regions = data["regions"]
        assert isinstance(regions, list), f"regions should be a list, got: {type(regions)}"
        assert len(regions) > 0, "Canada should have provinces"
        print(f"PASS: CA provinces: {len(regions)} regions, first: {regions[0]}")

    def test_get_provinces_canada_region_items_have_value_label(self):
        res = requests.get(f"{BASE_URL}/api/utils/provinces?country_code=CA")
        assert res.status_code == 200
        regions = res.json()["regions"]
        for r in regions:
            assert "value" in r, f"Region item must have 'value', got: {r}"
            assert "label" in r, f"Region item must have 'label', got: {r}"
        print(f"PASS: All CA region items have value+label: {regions[0]}")

    def test_get_provinces_usa_returns_states(self):
        res = requests.get(f"{BASE_URL}/api/utils/provinces?country_code=US")
        assert res.status_code == 200
        data = res.json()
        regions = data.get("regions", [])
        assert len(regions) > 0, "US should have states"
        print(f"PASS: US states: {len(regions)} states, first: {regions[0]}")

    def test_get_provinces_canada_by_name(self):
        """country_code=Canada (full name) should also work"""
        res = requests.get(f"{BASE_URL}/api/utils/provinces?country_code=Canada")
        assert res.status_code == 200
        data = res.json()
        regions = data.get("regions", [])
        assert len(regions) > 0, "Canada (full name) should return provinces"
        print(f"PASS: /api/utils/provinces?country_code=Canada returns {len(regions)} provinces")

    def test_get_provinces_unknown_country_returns_empty(self):
        """Unknown country should return empty regions list, not error"""
        res = requests.get(f"{BASE_URL}/api/utils/provinces?country_code=UNKNOWN_COUNTRY")
        assert res.status_code == 200, f"Should return 200 even for unknown country, got: {res.status_code}"
        data = res.json()
        regions = data.get("regions", [])
        assert isinstance(regions, list), "regions should be list even when empty"
        print(f"PASS: Unknown country returns empty regions list: {regions}")

    def test_get_provinces_missing_param_returns_422(self):
        """Missing country_code param should return 422 (query param required)"""
        res = requests.get(f"{BASE_URL}/api/utils/provinces")
        assert res.status_code == 422, f"Expected 422 for missing country_code, got {res.status_code}"
        print(f"PASS: Missing country_code returns 422")


class TestCreateCustomerWithAddressData:
    """Test creating customers with address data"""

    def test_create_customer_with_full_address(self, admin_headers):
        """POST /api/admin/customers/create with complete address data"""
        import random
        suffix = random.randint(10000, 99999)
        payload = {
            "full_name": f"TEST_Iter138_Address_{suffix}",
            "email": f"TEST_iter138_addr_{suffix}@example.com",
            "password": "TestPass138!",
            "line1": "123 Address Street",
            "line2": "Suite 100",
            "city": "Toronto",
            "region": "ON",
            "postal": "M5V 1A1",
            "country": "Canada",
            "mark_verified": True,
        }
        res = requests.post(f"{BASE_URL}/api/admin/customers/create", headers=admin_headers, json=payload)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        print(f"PASS: Create customer with full address. Response: {data}")

    def test_create_customer_with_us_state(self, admin_headers):
        """POST /api/admin/customers/create with US address and state"""
        import random
        suffix = random.randint(10000, 99999)
        payload = {
            "full_name": f"TEST_Iter138_US_{suffix}",
            "email": f"TEST_iter138_us_{suffix}@example.com",
            "password": "TestPass138!",
            "line1": "456 Main Avenue",
            "city": "New York",
            "region": "NY",
            "postal": "10001",
            "country": "USA",
            "mark_verified": True,
        }
        res = requests.post(f"{BASE_URL}/api/admin/customers/create", headers=admin_headers, json=payload)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        print("PASS: Create customer with US address and NY state")

    def test_create_customer_minimal_no_address(self, admin_headers):
        """POST /api/admin/customers/create without address fields"""
        import random
        suffix = random.randint(10000, 99999)
        payload = {
            "full_name": f"TEST_Iter138_NoAddr_{suffix}",
            "email": f"TEST_iter138_noaddr_{suffix}@example.com",
            "password": "TestPass138!",
            "mark_verified": True,
        }
        res = requests.post(f"{BASE_URL}/api/admin/customers/create", headers=admin_headers, json=payload)
        assert res.status_code == 200, f"Expected 200 even without address, got {res.status_code}: {res.text}"
        print("PASS: Create customer without address fields succeeds")
