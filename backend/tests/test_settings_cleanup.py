"""
Backend tests for Settings tab cleanup - iteration 23
Tests: /api/settings/public, /api/admin/settings/structured,
       PUT /api/admin/settings/key/{key}
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"


@pytest.fixture(scope="module")
def admin_token():
    """Obtain admin JWT token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json().get("token") or resp.json().get("access_token")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ---- Public Settings ---------------------------------------------------

class TestPublicSettings:
    """GET /api/settings/public - zoho + branding keys returned"""

    def test_public_settings_status(self):
        resp = requests.get(f"{BASE_URL}/api/settings/public")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_public_settings_zoho_reseller_signup_us(self):
        resp = requests.get(f"{BASE_URL}/api/settings/public")
        data = resp.json().get("settings", {})
        assert "zoho_reseller_signup_us" in data, f"Missing zoho_reseller_signup_us. Keys: {list(data.keys())}"
        assert data["zoho_reseller_signup_us"], "zoho_reseller_signup_us is empty"

    def test_public_settings_zoho_reseller_signup_ca(self):
        resp = requests.get(f"{BASE_URL}/api/settings/public")
        data = resp.json().get("settings", {})
        assert "zoho_reseller_signup_ca" in data, f"Missing zoho_reseller_signup_ca. Keys: {list(data.keys())}"
        assert data["zoho_reseller_signup_ca"], "zoho_reseller_signup_ca is empty"

    def test_public_settings_zoho_partner_tag_us(self):
        resp = requests.get(f"{BASE_URL}/api/settings/public")
        data = resp.json().get("settings", {})
        assert "zoho_partner_tag_us" in data, f"Missing zoho_partner_tag_us. Keys: {list(data.keys())}"

    def test_public_settings_zoho_partner_tag_ca(self):
        resp = requests.get(f"{BASE_URL}/api/settings/public")
        data = resp.json().get("settings", {})
        assert "zoho_partner_tag_ca" in data, f"Missing zoho_partner_tag_ca. Keys: {list(data.keys())}"

    def test_public_settings_zoho_access_instructions_url(self):
        resp = requests.get(f"{BASE_URL}/api/settings/public")
        data = resp.json().get("settings", {})
        assert "zoho_access_instructions_url" in data, f"Missing zoho_access_instructions_url. Keys: {list(data.keys())}"

    def test_public_settings_website_url(self):
        resp = requests.get(f"{BASE_URL}/api/settings/public")
        data = resp.json().get("settings", {})
        assert "website_url" in data, f"Missing website_url. Keys: {list(data.keys())}"

    def test_public_settings_contact_email(self):
        resp = requests.get(f"{BASE_URL}/api/settings/public")
        data = resp.json().get("settings", {})
        assert "contact_email" in data, f"Missing contact_email. Keys: {list(data.keys())}"


# ---- Structured Admin Settings ----------------------------------------

class TestStructuredSettings:
    """GET /api/admin/settings/structured - 6 categories, no obsolete keys"""

    def test_structured_settings_status(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/settings/structured", headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_structured_settings_has_expected_categories(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/settings/structured", headers=auth_headers)
        data = resp.json().get("settings", {})
        expected_cats = {"Payments", "Operations", "Email", "Zoho", "Branding", "FeatureFlags"}
        actual_cats = set(data.keys())
        missing = expected_cats - actual_cats
        assert not missing, f"Missing categories: {missing}. Actual: {actual_cats}"

    def test_structured_settings_no_stripe_keys(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/settings/structured", headers=auth_headers)
        data = resp.json().get("settings", {})
        all_keys = [item["key"] for cat in data.values() for item in cat]
        obsolete = ["stripe_publishable_key", "stripe_secret_key", "stripe_webhook_secret"]
        found = [k for k in obsolete if k in all_keys]
        assert not found, f"Obsolete stripe keys still present: {found}"

    def test_structured_settings_no_gocardless_keys(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/settings/structured", headers=auth_headers)
        data = resp.json().get("settings", {})
        all_keys = [item["key"] for cat in data.values() for item in cat]
        obsolete = ["gocardless_access_token", "gocardless_environment"]
        found = [k for k in obsolete if k in all_keys]
        assert not found, f"Obsolete gocardless keys still present: {found}"

    def test_structured_settings_no_logo_url_key(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/settings/structured", headers=auth_headers)
        data = resp.json().get("settings", {})
        all_keys = [item["key"] for cat in data.values() for item in cat]
        assert "logo_url" not in all_keys, f"Obsolete logo_url key still in structured settings"

    def test_structured_settings_no_old_zoho_partner_links(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/settings/structured", headers=auth_headers)
        data = resp.json().get("settings", {})
        all_keys = [item["key"] for cat in data.values() for item in cat]
        obsolete = ["zoho_partner_link_aus", "zoho_partner_link_nz", "zoho_partner_link_global"]
        found = [k for k in obsolete if k in all_keys]
        assert not found, f"Old Zoho partner links still present: {found}"

    def test_structured_settings_zoho_category_has_5_items(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/settings/structured", headers=auth_headers)
        data = resp.json().get("settings", {})
        zoho_items = data.get("Zoho", [])
        expected_zoho_keys = {
            "zoho_reseller_signup_us", "zoho_reseller_signup_ca",
            "zoho_partner_tag_us", "zoho_partner_tag_ca",
            "zoho_access_instructions_url"
        }
        actual_zoho_keys = {item["key"] for item in zoho_items}
        missing = expected_zoho_keys - actual_zoho_keys
        assert not missing, f"Missing Zoho keys: {missing}"

    def test_structured_settings_branding_category(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/settings/structured", headers=auth_headers)
        data = resp.json().get("settings", {})
        branding_items = data.get("Branding", [])
        branding_keys = {item["key"] for item in branding_items}
        assert "website_url" in branding_keys, "website_url missing from Branding"
        assert "contact_email" in branding_keys, "contact_email missing from Branding"

    def test_structured_settings_operations_has_override_code_expiry(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/settings/structured", headers=auth_headers)
        data = resp.json().get("settings", {})
        ops_items = data.get("Operations", [])
        ops_keys = {item["key"] for item in ops_items}
        assert "override_code_expiry_hours" in ops_keys, f"override_code_expiry_hours missing from Operations. Got: {ops_keys}"

    def test_structured_settings_payments_has_service_fee(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/settings/structured", headers=auth_headers)
        data = resp.json().get("settings", {})
        pay_items = data.get("Payments", [])
        pay_keys = {item["key"] for item in pay_items}
        assert "service_fee_rate" in pay_keys, f"service_fee_rate missing from Payments. Got: {pay_keys}"

    def test_structured_settings_feature_flags_partner_tagging(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/settings/structured", headers=auth_headers)
        data = resp.json().get("settings", {})
        ff_items = data.get("FeatureFlags", [])
        ff_keys = {item["key"] for item in ff_items}
        assert "partner_tagging_enabled" in ff_keys, f"partner_tagging_enabled missing from FeatureFlags. Got: {ff_keys}"

    def test_structured_settings_partner_tagging_is_bool_type(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/settings/structured", headers=auth_headers)
        data = resp.json().get("settings", {})
        ff_items = data.get("FeatureFlags", [])
        pt = next((item for item in ff_items if item["key"] == "partner_tagging_enabled"), None)
        assert pt is not None
        assert pt["value_type"] == "bool", f"Expected bool, got {pt['value_type']}"


# ---- Update Setting by Key -------------------------------------------

class TestUpdateSettingByKey:
    """PUT /api/admin/settings/key/{key}"""

    def test_update_service_fee_rate(self, auth_headers):
        """Set service_fee_rate to 0.08 and verify"""
        resp = requests.put(
            f"{BASE_URL}/api/admin/settings/key/service_fee_rate",
            json={"value": 0.08},
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "message" in data or "updated" in str(data).lower()

    def test_verify_service_fee_rate_updated(self, auth_headers):
        """Verify service_fee_rate was updated to 0.08"""
        resp = requests.get(f"{BASE_URL}/api/admin/settings/structured", headers=auth_headers)
        data = resp.json().get("settings", {})
        pay_items = data.get("Payments", [])
        fee = next((item for item in pay_items if item["key"] == "service_fee_rate"), None)
        assert fee is not None
        assert float(fee["value_json"]) == pytest.approx(0.08), f"Expected 0.08, got {fee['value_json']}"

    def test_update_override_code_expiry_hours(self, auth_headers):
        """Set override_code_expiry_hours to 72 and verify"""
        resp = requests.put(
            f"{BASE_URL}/api/admin/settings/key/override_code_expiry_hours",
            json={"value": 72},
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_verify_override_code_expiry_hours_updated(self, auth_headers):
        """Verify override_code_expiry_hours was updated to 72"""
        resp = requests.get(f"{BASE_URL}/api/admin/settings/structured", headers=auth_headers)
        data = resp.json().get("settings", {})
        ops_items = data.get("Operations", [])
        item = next((i for i in ops_items if i["key"] == "override_code_expiry_hours"), None)
        assert item is not None
        assert int(item["value_json"]) == 72, f"Expected 72, got {item['value_json']}"

    def test_update_setting_missing_value_returns_400(self, auth_headers):
        """PUT without value should return 400"""
        resp = requests.put(
            f"{BASE_URL}/api/admin/settings/key/service_fee_rate",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"

    def test_reset_service_fee_rate_to_default(self, auth_headers):
        """Reset service_fee_rate back to 0.05"""
        resp = requests.put(
            f"{BASE_URL}/api/admin/settings/key/service_fee_rate",
            json={"value": 0.05},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_reset_override_code_expiry_hours_to_default(self, auth_headers):
        """Reset override_code_expiry_hours back to 48"""
        resp = requests.put(
            f"{BASE_URL}/api/admin/settings/key/override_code_expiry_hours",
            json={"value": 48},
            headers=auth_headers,
        )
        assert resp.status_code == 200
