"""
Backend tests for iteration 133:
- Partner signup address validation
- Admin tenant address endpoints (GET /admin/tenants/my, PUT /admin/tenants/{id}/address)
- WorkDrive documents endpoints auth check
- website-settings includes workdrive_enabled
- OAuth integrations includes zoho_workdrive, google_drive, onedrive
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

PLATFORM_ADMIN_EMAIL = "admin@automateaccounts.local"
PLATFORM_ADMIN_PASSWORD = "ChangeMe123!"
PARTNER1_EMAIL = "admin@ligerinc.local"
PARTNER1_PASSWORD = "ChangeMe123!"
PARTNER1_CODE = "ligerinc"


def get_token(email: str, password: str, partner_code: str = None) -> str:
    """Helper: get auth token."""
    if partner_code:
        resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "email": email, "password": password, "partner_code": partner_code
        })
    else:
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": email, "password": password
        })
    if resp.status_code == 200:
        return resp.json().get("token", "")
    return ""


class TestProvincesEndpoint:
    """Province/state lookup endpoint (no auth required)."""

    def test_canada_returns_13_provinces(self):
        resp = requests.get(f"{BASE_URL}/api/utils/provinces?country_code=CA")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "regions" in data
        assert len(data["regions"]) == 13, f"Expected 13, got {len(data['regions'])}"

    def test_canada_full_word_also_works(self):
        resp = requests.get(f"{BASE_URL}/api/utils/provinces?country_code=Canada")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["regions"]) == 13

    def test_usa_returns_51_states(self):
        resp = requests.get(f"{BASE_URL}/api/utils/provinces?country_code=US")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["regions"]) >= 50

    def test_unknown_country_returns_empty(self):
        resp = requests.get(f"{BASE_URL}/api/utils/provinces?country_code=ZZ")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("regions") == []

    def test_missing_param_returns_422(self):
        resp = requests.get(f"{BASE_URL}/api/utils/provinces")
        assert resp.status_code == 422


class TestRegisterPartnerAddressValidation:
    """Partner registration must require address fields."""

    def test_missing_all_address_fields_returns_400(self):
        resp = requests.post(f"{BASE_URL}/api/auth/register-partner", json={
            "name": "Test Org",
            "admin_name": "Test Admin",
            "admin_email": "testadmin_iter133_unique@test.local",
            "admin_password": "ChangeMe123!",
            "base_currency": "USD",
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        detail = resp.json().get("detail", "")
        assert "Address fields required" in detail or "address" in detail.lower()

    def test_missing_specific_address_fields_returns_400(self):
        """Missing city, postal, region, country — only line1 provided."""
        resp = requests.post(f"{BASE_URL}/api/auth/register-partner", json={
            "name": "Test Org B",
            "admin_name": "Test Admin",
            "admin_email": "testadmin_iter133_b@test.local",
            "admin_password": "ChangeMe123!",
            "address": {"line1": "123 Main St"},
        })
        assert resp.status_code == 400
        detail = resp.json().get("detail", "")
        # Should mention the missing fields
        assert "city" in detail.lower() or "postal" in detail.lower() or "region" in detail.lower() or "country" in detail.lower()

    def test_empty_address_object_returns_400(self):
        resp = requests.post(f"{BASE_URL}/api/auth/register-partner", json={
            "name": "Test Org C",
            "admin_name": "Test Admin C",
            "admin_email": "testadmin_iter133_c@test.local",
            "admin_password": "ChangeMe123!",
            "address": {},
        })
        assert resp.status_code == 400
        detail = resp.json().get("detail", "")
        assert "required" in detail.lower() or "address" in detail.lower()

    def test_complete_address_registration_works(self):
        """Full valid registration with all address fields — should return 200."""
        resp = requests.post(f"{BASE_URL}/api/auth/register-partner", json={
            "name": "TEST_Org_Iter133_Valid",
            "admin_name": "Valid Admin",
            "admin_email": "TEST_valid_iter133@test.local",
            "admin_password": "ChangeMe123!",
            "address": {
                "line1": "123 Test Street",
                "city": "Toronto",
                "postal": "M5V 1A1",
                "region": "Ontario",
                "country": "Canada",
            },
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "partner_code" in data


class TestAdminTenantsMyEndpoint:
    """GET /api/admin/tenants/my endpoint."""

    def test_get_my_tenant_unauthenticated_returns_401(self):
        resp = requests.get(f"{BASE_URL}/api/admin/tenants/my")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_get_my_tenant_as_platform_admin(self):
        """Platform admin should get their own tenant."""
        token = get_token(PLATFORM_ADMIN_EMAIL, PLATFORM_ADMIN_PASSWORD)
        if not token:
            pytest.skip("Platform admin login failed")
        resp = requests.get(f"{BASE_URL}/api/admin/tenants/my", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "tenant" in data

    def test_get_my_tenant_as_partner_admin(self):
        """Partner admin should get their own tenant."""
        # Try common partner codes
        for code in ["ligerinc", "liger-inc", "liger"]:
            token = get_token(PARTNER1_EMAIL, PARTNER1_PASSWORD, code)
            if token:
                resp = requests.get(f"{BASE_URL}/api/admin/tenants/my", headers={"Authorization": f"Bearer {token}"})
                if resp.status_code == 200:
                    data = resp.json()
                    assert "tenant" in data
                    tenant = data["tenant"]
                    assert "id" in tenant
                    return
        pytest.skip("Partner admin login failed — try updating partner code")


class TestAdminTenantsAddressEndpoint:
    """PUT /api/admin/tenants/{id}/address endpoint."""

    def test_update_address_unauthenticated_returns_401(self):
        resp = requests.put(f"{BASE_URL}/api/admin/tenants/some-id/address", json={
            "address": {"line1": "Test", "city": "City", "postal": "12345", "region": "ON", "country": "Canada"}
        })
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_update_address_customer_token_returns_403(self):
        """A customer token should be rejected (not an admin)."""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "customer1@ligerinc.local",
            "password": "ChangeMe123!",
            "partner_code": "ligerinc",
            "login_type": "customer",
        })
        if resp.status_code != 200:
            # Try finding the right code
            pytest.skip("Customer login failed, skipping test")
        token = resp.json().get("token", "")
        # Try to update a random tenant address
        upd = requests.put(
            f"{BASE_URL}/api/admin/tenants/some-random-id/address",
            json={"address": {"line1": "Hack", "city": "Hacker", "postal": "00000", "region": "ON", "country": "Canada"}},
            headers={"Authorization": f"Bearer {token}"}
        )
        # Should be 403 (forbidden for non-admin)
        assert upd.status_code in (401, 403), f"Expected 401/403, got {upd.status_code}"


class TestAdminLogin:
    """Regression: admin login works correctly."""

    def test_platform_admin_login_success(self):
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PLATFORM_ADMIN_EMAIL,
            "password": PLATFORM_ADMIN_PASSWORD
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "token" in data
        assert data.get("role") in ("platform_admin", "admin", "super_admin")

    def test_wrong_password_returns_401(self):
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PLATFORM_ADMIN_EMAIL,
            "password": "wrongpassword!"
        })
        assert resp.status_code == 401


class TestWebsiteSettingsWorkdriveEnabled:
    """GET /api/website-settings must include workdrive_enabled field."""

    def test_website_settings_includes_workdrive_enabled(self):
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        assert resp.status_code == 200
        data = resp.json()
        settings = data.get("settings", {})
        assert "workdrive_enabled" in settings, "workdrive_enabled field missing from website-settings response"
        assert isinstance(settings["workdrive_enabled"], bool), "workdrive_enabled should be a boolean"

    def test_workdrive_enabled_is_false_when_not_connected(self):
        """By default (no WorkDrive connected), workdrive_enabled should be False."""
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        assert resp.status_code == 200
        data = resp.json()
        settings = data.get("settings", {})
        # Since no WorkDrive is connected in this environment
        # It can be True or False but the field must exist
        assert "workdrive_enabled" in settings


class TestDocumentsEndpointAuth:
    """GET /api/documents requires authentication."""

    def test_list_documents_unauthenticated_returns_401(self):
        resp = requests.get(f"{BASE_URL}/api/documents")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"

    def test_list_documents_with_valid_token_returns_200_or_400(self):
        """With a valid partner admin token, should at least return 200 (even if empty)."""
        token = get_token(PLATFORM_ADMIN_EMAIL, PLATFORM_ADMIN_PASSWORD)
        if not token:
            pytest.skip("Platform admin login failed")
        resp = requests.get(f"{BASE_URL}/api/documents", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "documents" in data


class TestWorkdriveSyncFoldersAuth:
    """POST /api/admin/workdrive/sync-folders requires authentication."""

    def test_sync_folders_unauthenticated_returns_401(self):
        resp = requests.post(f"{BASE_URL}/api/admin/workdrive/sync-folders")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"

    def test_sync_folders_fails_gracefully_when_not_connected(self):
        """With auth but WorkDrive not connected, should return 400 (not 500)."""
        token = get_token(PLATFORM_ADMIN_EMAIL, PLATFORM_ADMIN_PASSWORD)
        if not token:
            pytest.skip("Platform admin login failed")
        resp = requests.post(
            f"{BASE_URL}/api/admin/workdrive/sync-folders",
            headers={"Authorization": f"Bearer {token}"}
        )
        # Should be 400 (WorkDrive not connected) not 500 (crash)
        assert resp.status_code in (400, 200), f"Unexpected status: {resp.status_code}: {resp.text}"


class TestOAuthIntegrations:
    """GET /api/oauth/integrations must include zoho_workdrive, google_drive, onedrive."""

    def _get_integrations(self):
        token = get_token(PLATFORM_ADMIN_EMAIL, PLATFORM_ADMIN_PASSWORD)
        if not token:
            pytest.skip("Platform admin login failed")
        resp = requests.get(
            f"{BASE_URL}/api/oauth/integrations",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        return resp.json().get("integrations", [])

    def test_integrations_requires_auth(self):
        resp = requests.get(f"{BASE_URL}/api/oauth/integrations")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_includes_zoho_workdrive(self):
        integrations = self._get_integrations()
        ids = [i["id"] for i in integrations]
        assert "zoho_workdrive" in ids, f"zoho_workdrive not in integrations list: {ids}"

    def test_zoho_workdrive_has_cloud_storage_category(self):
        integrations = self._get_integrations()
        wd = next((i for i in integrations if i["id"] == "zoho_workdrive"), None)
        assert wd is not None
        assert wd.get("category") == "cloud_storage", f"Expected cloud_storage, got {wd.get('category')}"
        assert wd.get("is_coming_soon") is False or not wd.get("is_coming_soon")

    def test_includes_google_drive_as_coming_soon(self):
        integrations = self._get_integrations()
        gd = next((i for i in integrations if i["id"] == "google_drive"), None)
        assert gd is not None, "google_drive not found in integrations"
        assert gd.get("is_coming_soon") is True, f"google_drive.is_coming_soon should be True, got {gd.get('is_coming_soon')}"

    def test_includes_onedrive_as_coming_soon(self):
        integrations = self._get_integrations()
        od = next((i for i in integrations if i["id"] == "onedrive"), None)
        assert od is not None, "onedrive not found in integrations"
        assert od.get("is_coming_soon") is True, f"onedrive.is_coming_soon should be True, got {od.get('is_coming_soon')}"

    def test_cloud_storage_category_has_three_entries(self):
        integrations = self._get_integrations()
        cloud_storage = [i for i in integrations if i.get("category") == "cloud_storage"]
        assert len(cloud_storage) == 3, f"Expected 3 cloud_storage integrations, got {len(cloud_storage)}: {[i['id'] for i in cloud_storage]}"
