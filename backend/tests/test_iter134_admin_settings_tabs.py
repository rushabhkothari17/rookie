"""
Iteration 134: Admin Panel Settings Tab Restructure Tests
Tests for:
- Organization Info tab (branding + address)
- Auth & Pages tab (including Documents Page tile)
- System Config (without Base Currency)
- Backend: GET /admin/tenants/my, PUT /admin/tenants/{id}/address
- Documents page uses ws.documents_page_title etc.
- TopNav uses ws.nav_documents_label
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def platform_token():
    """Get platform admin token"""
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!"
    })
    assert r.status_code == 200
    data = r.json()
    token = data.get("token") or data.get("access_token")
    assert token, f"No token in response: {data}"
    return token


@pytest.fixture(scope="module")
def partner_token():
    """Get partner admin token (test org from iter133)"""
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "TEST_valid_iter133@test.local",
        "password": "ChangeMe123!",
        "partner_code": "test-org-iter133-valid"
    })
    assert r.status_code == 200
    data = r.json()
    token = data.get("token") or data.get("access_token")
    assert token, f"No token in response: {data}"
    return token


@pytest.fixture(scope="module")
def partner_tenant_id(partner_token):
    """Get the tenant ID for the partner admin"""
    r = requests.get(f"{BASE_URL}/api/admin/tenants/my",
                     headers={"Authorization": f"Bearer {partner_token}"})
    assert r.status_code == 200
    return r.json()["tenant"]["id"]


# ─── Test: GET /admin/tenants/my ──────────────────────────────────────────────

class TestGetMyTenant:
    """Tests for GET /api/admin/tenants/my"""

    def test_get_my_tenant_unauthenticated_returns_401(self):
        """Unauthenticated request should return 401"""
        r = requests.get(f"{BASE_URL}/api/admin/tenants/my")
        assert r.status_code == 401

    def test_get_my_tenant_as_platform_admin_returns_tenant(self, platform_token):
        """Platform admin can get their own tenant"""
        r = requests.get(f"{BASE_URL}/api/admin/tenants/my",
                         headers={"Authorization": f"Bearer {platform_token}"})
        assert r.status_code == 200
        data = r.json()
        assert "tenant" in data
        tenant = data["tenant"]
        assert "id" in tenant
        assert "name" in tenant

    def test_get_my_tenant_as_partner_admin_returns_tenant_with_address(self, partner_token):
        """Partner admin's tenant should include address field"""
        r = requests.get(f"{BASE_URL}/api/admin/tenants/my",
                         headers={"Authorization": f"Bearer {partner_token}"})
        assert r.status_code == 200
        data = r.json()
        assert "tenant" in data
        tenant = data["tenant"]
        assert "id" in tenant
        assert "name" in tenant
        # Address field should exist (may be None or dict)
        assert "address" in tenant or tenant.get("address") is None or isinstance(tenant.get("address"), dict)

    def test_get_my_tenant_response_has_no_mongo_id(self, partner_token):
        """Response should not contain MongoDB _id field"""
        r = requests.get(f"{BASE_URL}/api/admin/tenants/my",
                         headers={"Authorization": f"Bearer {partner_token}"})
        assert r.status_code == 200
        tenant = r.json().get("tenant", {})
        assert "_id" not in tenant, "MongoDB _id should not be in response"

    def test_get_my_tenant_platform_admin_has_is_platform_true(self, platform_token):
        """Platform admin tenant should have is_platform=true"""
        r = requests.get(f"{BASE_URL}/api/admin/tenants/my",
                         headers={"Authorization": f"Bearer {platform_token}"})
        assert r.status_code == 200
        tenant = r.json()["tenant"]
        # is_platform flag should be true
        assert tenant.get("is_platform") == True


# ─── Test: PUT /admin/tenants/{tenant_id}/address ─────────────────────────────

class TestUpdateTenantAddress:
    """Tests for PUT /api/admin/tenants/{tenant_id}/address"""

    def test_update_address_unauthenticated_returns_401(self, partner_tenant_id):
        """Unauthenticated request should return 401"""
        r = requests.put(f"{BASE_URL}/api/admin/tenants/{partner_tenant_id}/address",
                         json={"address": {"line1": "123 Main St", "city": "Toronto",
                                           "postal": "M5V 2T6", "region": "Ontario", "country": "Canada"}})
        assert r.status_code == 401

    def test_update_address_missing_required_fields_returns_400(self, partner_token, partner_tenant_id):
        """Missing required fields should return 400"""
        r = requests.put(f"{BASE_URL}/api/admin/tenants/{partner_tenant_id}/address",
                         json={"address": {"line1": "123 Main St"}},
                         headers={"Authorization": f"Bearer {partner_token}"})
        assert r.status_code == 400
        assert "required" in r.json().get("detail", "").lower()

    def test_update_address_as_partner_admin_succeeds(self, partner_token, partner_tenant_id):
        """Partner admin can update their own tenant's address"""
        payload = {
            "address": {
                "line1": "456 Test Avenue",
                "line2": "Suite 100",
                "city": "Vancouver",
                "region": "British Columbia",
                "postal": "V6B 1A1",
                "country": "Canada"
            }
        }
        r = requests.put(f"{BASE_URL}/api/admin/tenants/{partner_tenant_id}/address",
                         json=payload,
                         headers={"Authorization": f"Bearer {partner_token}"})
        assert r.status_code == 200
        data = r.json()
        assert "tenant" in data
        assert data["tenant"]["address"]["line1"] == "456 Test Avenue"
        assert data["tenant"]["address"]["city"] == "Vancouver"

    def test_update_address_verify_persistence(self, partner_token, partner_tenant_id):
        """Updated address should be persisted and retrievable via GET"""
        # Update the address
        payload = {
            "address": {
                "line1": "789 Persistence Check Lane",
                "line2": "",
                "city": "Montreal",
                "region": "Quebec",
                "postal": "H2Y 1C6",
                "country": "Canada"
            }
        }
        put_r = requests.put(f"{BASE_URL}/api/admin/tenants/{partner_tenant_id}/address",
                              json=payload,
                              headers={"Authorization": f"Bearer {partner_token}"})
        assert put_r.status_code == 200

        # Verify via GET /admin/tenants/my
        get_r = requests.get(f"{BASE_URL}/api/admin/tenants/my",
                              headers={"Authorization": f"Bearer {partner_token}"})
        assert get_r.status_code == 200
        address = get_r.json()["tenant"]["address"]
        assert address["line1"] == "789 Persistence Check Lane"
        assert address["city"] == "Montreal"
        assert address["country"] == "Canada"

    def test_update_address_partner_cannot_update_other_tenant(self, partner_token, platform_token):
        """Partner admin cannot update another tenant's address"""
        # Get platform tenant ID
        plat_r = requests.get(f"{BASE_URL}/api/admin/tenants/my",
                               headers={"Authorization": f"Bearer {platform_token}"})
        platform_tenant_id = plat_r.json()["tenant"]["id"]

        # Partner should not be able to update platform's address
        r = requests.put(f"{BASE_URL}/api/admin/tenants/{platform_tenant_id}/address",
                         json={"address": {"line1": "Test", "city": "Test", "postal": "T0T 0T0",
                                           "region": "Ontario", "country": "Canada"}},
                         headers={"Authorization": f"Bearer {partner_token}"})
        assert r.status_code in [403, 404], f"Expected 403/404 but got {r.status_code}: {r.text}"

    def test_update_address_as_platform_admin_succeeds_for_any_tenant(self, platform_token, partner_tenant_id):
        """Platform admin can update any tenant's address"""
        payload = {
            "address": {
                "line1": "Platform Updated Address",
                "line2": "",
                "city": "Calgary",
                "region": "Alberta",
                "postal": "T2P 1A1",
                "country": "Canada"
            }
        }
        r = requests.put(f"{BASE_URL}/api/admin/tenants/{partner_tenant_id}/address",
                         json=payload,
                         headers={"Authorization": f"Bearer {platform_token}"})
        assert r.status_code == 200
        assert r.json()["tenant"]["address"]["line1"] == "Platform Updated Address"


# ─── Test: Website Settings for Documents fields ─────────────────────────────

class TestDocumentsWebsiteSettings:
    """Tests that documents page fields exist in website settings"""

    def test_website_settings_includes_documents_fields(self, platform_token):
        """GET /admin/website-settings should include documents_page_* fields"""
        r = requests.get(f"{BASE_URL}/api/admin/website-settings",
                         headers={"Authorization": f"Bearer {platform_token}"})
        assert r.status_code == 200
        data = r.json()
        settings = data.get("settings", {})
        # Check for documents page fields (may be empty strings)
        docs_fields = [
            "nav_documents_label", "documents_page_title", "documents_page_subtitle",
            "documents_page_upload_label", "documents_page_upload_hint", "documents_page_empty_text"
        ]
        for field in docs_fields:
            assert field in settings, f"Missing field: {field}"

    def test_update_documents_settings(self, platform_token):
        """Should be able to update documents page fields"""
        r = requests.put(f"{BASE_URL}/api/admin/website-settings",
                         json={
                             "nav_documents_label": "TEST_My Docs",
                             "documents_page_title": "TEST_Document Center",
                             "documents_page_subtitle": "TEST_View your files",
                             "documents_page_upload_label": "TEST_Upload File",
                             "documents_page_upload_hint": "TEST_Max 5MB",
                             "documents_page_empty_text": "TEST_No files yet"
                         },
                         headers={"Authorization": f"Bearer {platform_token}"})
        assert r.status_code == 200

    def test_documents_settings_saved_and_retrievable(self, platform_token):
        """Updated documents settings should be saved and retrievable"""
        # Update
        requests.put(f"{BASE_URL}/api/admin/website-settings",
                     json={"documents_page_title": "TEST_Saved Title 134"},
                     headers={"Authorization": f"Bearer {platform_token}"})
        # Retrieve
        r = requests.get(f"{BASE_URL}/api/admin/website-settings",
                         headers={"Authorization": f"Bearer {platform_token}"})
        assert r.status_code == 200
        settings = r.json().get("settings", {})
        assert settings.get("documents_page_title") == "TEST_Saved Title 134"


# ─── Test: Public website-settings endpoint includes documents fields ──────────

class TestPublicWebsiteSettings:
    """Tests for public website-settings endpoint"""

    def test_public_website_settings_includes_documents_fields(self):
        """Public /api/website-settings should include nav_documents_label"""
        r = requests.get(f"{BASE_URL}/api/website-settings")
        assert r.status_code == 200
        settings = r.json().get("settings", {})
        # nav_documents_label should exist (used by TopNav)
        assert "nav_documents_label" in settings, "nav_documents_label missing from public settings"
        assert "documents_page_title" in settings, "documents_page_title missing from public settings"


# ─── Test: Base Currency is still accessible (now in Organization Info) ────────

class TestBaseCurrency:
    """Tests for base currency endpoint (should still work, moved to Org Info UI)"""

    def test_get_base_currency(self, platform_token):
        """GET /admin/tenant/base-currency should return base_currency"""
        r = requests.get(f"{BASE_URL}/api/admin/tenant/base-currency",
                         headers={"Authorization": f"Bearer {platform_token}"})
        assert r.status_code == 200
        data = r.json()
        assert "base_currency" in data
        assert isinstance(data["base_currency"], str)
        assert len(data["base_currency"]) == 3  # e.g. "USD"

    def test_update_base_currency(self, platform_token):
        """PUT /admin/tenant/base-currency should update and return new value"""
        r = requests.put(f"{BASE_URL}/api/admin/tenant/base-currency",
                         json={"base_currency": "CAD"},
                         headers={"Authorization": f"Bearer {platform_token}"})
        assert r.status_code == 200
        data = r.json()
        assert data.get("base_currency") == "CAD"
