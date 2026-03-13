"""
Test iter280: Admin panel improvements
- Verify website-settings API returns signup_form_schema with email and password keys
- Verify partner_signup_form_schema has admin_email and admin_password keys
- Verify admin login and API access
"""
import pytest
import requests
import os
import json

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


@pytest.fixture(scope="module")
def admin_token():
    """Get admin JWT token via login."""
    resp = requests.post(f"{BASE_URL}/api/auth/admin/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!",
        "partner_code": "AA",
    })
    if resp.status_code == 200:
        data = resp.json()
        token = data.get("token") or data.get("access_token") or (data.get("data") or {}).get("token")
        if token:
            return token
    # Try alternative login endpoint
    resp2 = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!",
    })
    if resp2.status_code == 200:
        data2 = resp2.json()
        return data2.get("token") or data2.get("access_token") or (data2.get("data") or {}).get("token")
    pytest.skip(f"Admin login failed: {resp.status_code} {resp.text[:300]}")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


class TestAdminWebsiteSettings:
    """Test website settings API - signup schema migration"""

    def test_get_admin_website_settings_status(self, auth_headers):
        """GET /api/admin/website-settings should return 200"""
        resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"

    def test_signup_form_schema_has_email_key(self, auth_headers):
        """signup_form_schema should contain 'email' field"""
        resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=auth_headers)
        assert resp.status_code == 200
        settings = resp.json().get("settings", {})
        schema_str = settings.get("signup_form_schema", "[]")
        schema = json.loads(schema_str)
        keys = [f.get("key") for f in schema]
        assert "email" in keys, f"'email' not found in signup_form_schema keys: {keys}"

    def test_signup_form_schema_has_password_key(self, auth_headers):
        """signup_form_schema should contain 'password' field"""
        resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=auth_headers)
        assert resp.status_code == 200
        settings = resp.json().get("settings", {})
        schema_str = settings.get("signup_form_schema", "[]")
        schema = json.loads(schema_str)
        keys = [f.get("key") for f in schema]
        assert "password" in keys, f"'password' not found in signup_form_schema keys: {keys}"

    def test_signup_form_schema_email_is_locked(self, auth_headers):
        """email field in signup_form_schema should be locked=True"""
        resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=auth_headers)
        assert resp.status_code == 200
        settings = resp.json().get("settings", {})
        schema_str = settings.get("signup_form_schema", "[]")
        schema = json.loads(schema_str)
        email_fields = [f for f in schema if f.get("key") == "email"]
        assert email_fields, "No email field found"
        assert email_fields[0].get("locked") is True, f"Email field locked={email_fields[0].get('locked')}"

    def test_signup_form_schema_password_is_locked(self, auth_headers):
        """password field in signup_form_schema should be locked=True"""
        resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=auth_headers)
        assert resp.status_code == 200
        settings = resp.json().get("settings", {})
        schema_str = settings.get("signup_form_schema", "[]")
        schema = json.loads(schema_str)
        password_fields = [f for f in schema if f.get("key") == "password"]
        assert password_fields, "No password field found"
        assert password_fields[0].get("locked") is True, f"Password field locked={password_fields[0].get('locked')}"

    def test_partner_signup_schema_has_admin_email(self, auth_headers):
        """partner_signup_form_schema should contain 'admin_email' field"""
        resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=auth_headers)
        assert resp.status_code == 200
        settings = resp.json().get("settings", {})
        schema_str = settings.get("partner_signup_form_schema", "[]")
        schema = json.loads(schema_str)
        keys = [f.get("key") for f in schema]
        assert "admin_email" in keys, f"'admin_email' not found in partner_signup_form_schema keys: {keys}"

    def test_partner_signup_schema_has_admin_password(self, auth_headers):
        """partner_signup_form_schema should contain 'admin_password' field"""
        resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=auth_headers)
        assert resp.status_code == 200
        settings = resp.json().get("settings", {})
        schema_str = settings.get("partner_signup_form_schema", "[]")
        schema = json.loads(schema_str)
        keys = [f.get("key") for f in schema]
        assert "admin_password" in keys, f"'admin_password' not found in partner_signup_form_schema keys: {keys}"

    def test_partner_signup_schema_admin_email_locked(self, auth_headers):
        """admin_email in partner_signup_form_schema should be locked=True"""
        resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=auth_headers)
        assert resp.status_code == 200
        settings = resp.json().get("settings", {})
        schema_str = settings.get("partner_signup_form_schema", "[]")
        schema = json.loads(schema_str)
        fields = [f for f in schema if f.get("key") == "admin_email"]
        assert fields, "No admin_email field found"
        assert fields[0].get("locked") is True, f"admin_email locked={fields[0].get('locked')}"

    def test_partner_signup_schema_admin_password_locked(self, auth_headers):
        """admin_password in partner_signup_form_schema should be locked=True"""
        resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=auth_headers)
        assert resp.status_code == 200
        settings = resp.json().get("settings", {})
        schema_str = settings.get("partner_signup_form_schema", "[]")
        schema = json.loads(schema_str)
        fields = [f for f in schema if f.get("key") == "admin_password"]
        assert fields, "No admin_password field found"
        assert fields[0].get("locked") is True, f"admin_password locked={fields[0].get('locked')}"

    def test_public_website_settings_signup_schema(self):
        """Public endpoint also migrates signup_form_schema correctly"""
        resp = requests.get(f"{BASE_URL}/api/website-settings?partner_code=AA")
        assert resp.status_code == 200
        settings = resp.json().get("settings", {})
        schema_str = settings.get("signup_form_schema", "[]")
        schema = json.loads(schema_str)
        keys = [f.get("key") for f in schema]
        assert "email" in keys, f"Public endpoint: 'email' missing from signup_form_schema keys: {keys}"
        assert "password" in keys, f"Public endpoint: 'password' missing from signup_form_schema keys: {keys}"

    def test_public_website_settings_partner_signup_schema(self):
        """Public endpoint also migrates partner_signup_form_schema correctly"""
        resp = requests.get(f"{BASE_URL}/api/website-settings?partner_code=AA")
        assert resp.status_code == 200
        settings = resp.json().get("settings", {})
        schema_str = settings.get("partner_signup_form_schema", "[]")
        schema = json.loads(schema_str)
        keys = [f.get("key") for f in schema]
        assert "admin_email" in keys, f"Public endpoint: 'admin_email' missing from partner_signup_form_schema: {keys}"
        assert "admin_password" in keys, f"Public endpoint: 'admin_password' missing from partner_signup_form_schema: {keys}"
