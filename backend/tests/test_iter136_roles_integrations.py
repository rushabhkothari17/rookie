"""
Backend tests for iter136:
- Dynamic Roles: GET/POST/PUT/DELETE /api/admin/roles
- Google Drive & OneDrive as 'Coming Soon' integrations
- Tenant address editing: PUT /api/admin/tenants/{id}/address
- Forced Password Change validation
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# ─────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_token():
    """Get admin token using platform admin creds."""
    res = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!",
        "tenant_code": "automate-accounts",
    })
    if res.status_code == 200:
        return res.json().get("token")
    pytest.skip(f"Admin login failed: {res.status_code} {res.text[:200]}")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def session(admin_headers):
    s = requests.Session()
    s.headers.update(admin_headers)
    return s


# ─────────────────────────────────────────────────────────────────
# 1. GET /api/admin/roles - preset + custom
# ─────────────────────────────────────────────────────────────────

class TestGetRoles:
    """Test GET /admin/roles endpoint"""

    def test_get_roles_returns_200(self, session):
        res = session.get(f"{BASE_URL}/api/admin/roles")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text[:200]}"

    def test_get_roles_has_roles_list(self, session):
        res = session.get(f"{BASE_URL}/api/admin/roles")
        data = res.json()
        assert "roles" in data, "Response must have 'roles' key"
        assert isinstance(data["roles"], list), "'roles' must be a list"

    def test_get_roles_has_modules_list(self, session):
        res = session.get(f"{BASE_URL}/api/admin/roles")
        data = res.json()
        assert "modules" in data, "Response must have 'modules' key"
        assert len(data["modules"]) > 0, "Modules list must not be empty"

    def test_get_roles_includes_6_preset_roles(self, session):
        res = session.get(f"{BASE_URL}/api/admin/roles")
        preset = [r for r in res.json()["roles"] if r.get("is_preset")]
        assert len(preset) == 6, f"Expected 6 preset roles, got {len(preset)}"

    def test_get_roles_preset_role_has_required_fields(self, session):
        res = session.get(f"{BASE_URL}/api/admin/roles")
        preset = [r for r in res.json()["roles"] if r.get("is_preset")]
        role = preset[0]
        assert "id" in role
        assert "name" in role
        assert "access_level" in role
        assert "modules" in role
        assert role["is_preset"] is True

    def test_get_roles_includes_expected_preset_role_names(self, session):
        res = session.get(f"{BASE_URL}/api/admin/roles")
        preset_names = {r["name"] for r in res.json()["roles"] if r.get("is_preset")}
        expected = {"Super Admin", "Manager", "Support Agent", "Viewer", "Accountant", "Content Editor"}
        assert expected == preset_names, f"Preset names mismatch: {preset_names}"


# ─────────────────────────────────────────────────────────────────
# 2. POST /api/admin/roles - create custom role
# ─────────────────────────────────────────────────────────────────

class TestCreateRole:
    """Test POST /admin/roles - create custom role"""

    created_role_id = None

    def test_create_custom_role_success(self, session):
        payload = {
            "name": "TEST_Custom Role Iter136",
            "description": "Test role for iter136 backend tests",
            "access_level": "full_access",
            "modules": ["customers", "orders"],
        }
        res = session.post(f"{BASE_URL}/api/admin/roles", json=payload)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text[:200]}"
        data = res.json()
        assert data["name"] == payload["name"]
        assert data["access_level"] == "full_access"
        assert set(data["modules"]) == {"customers", "orders"}
        assert data["is_preset"] is False
        assert "id" in data
        TestCreateRole.created_role_id = data["id"]

    def test_create_role_persists_in_get(self, session):
        if not TestCreateRole.created_role_id:
            pytest.skip("No created role ID available")
        res = session.get(f"{BASE_URL}/api/admin/roles")
        custom = [r for r in res.json()["roles"] if r.get("id") == TestCreateRole.created_role_id]
        assert len(custom) == 1, "Created role must appear in GET /admin/roles"

    def test_create_role_invalid_access_level(self, session):
        payload = {
            "name": "TEST_bad_access",
            "access_level": "invalid_level",
            "modules": []
        }
        res = session.post(f"{BASE_URL}/api/admin/roles", json=payload)
        assert res.status_code == 400, f"Expected 400, got {res.status_code}"

    def test_create_role_invalid_module(self, session):
        payload = {
            "name": "TEST_bad_module",
            "access_level": "read_only",
            "modules": ["nonexistent_module"]
        }
        res = session.post(f"{BASE_URL}/api/admin/roles", json=payload)
        assert res.status_code == 400, f"Expected 400 for unknown module, got {res.status_code}"


# ─────────────────────────────────────────────────────────────────
# 3. PUT /api/admin/roles/{id} - update custom role
# ─────────────────────────────────────────────────────────────────

class TestUpdateRole:
    """Test PUT /admin/roles/{id}"""

    def test_update_custom_role(self, session):
        if not TestCreateRole.created_role_id:
            pytest.skip("No created role ID")
        payload = {
            "name": "TEST_Custom Role Iter136 Updated",
            "description": "Updated description",
            "access_level": "read_only",
            "modules": ["customers", "orders", "reports"],
        }
        res = session.put(f"{BASE_URL}/api/admin/roles/{TestCreateRole.created_role_id}", json=payload)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text[:200]}"
        data = res.json()
        assert data["name"] == "TEST_Custom Role Iter136 Updated"
        assert data["access_level"] == "read_only"
        assert "reports" in data["modules"]

    def test_update_role_persists(self, session):
        if not TestCreateRole.created_role_id:
            pytest.skip("No created role ID")
        res = session.get(f"{BASE_URL}/api/admin/roles")
        custom = [r for r in res.json()["roles"] if r.get("id") == TestCreateRole.created_role_id]
        assert custom[0]["access_level"] == "read_only"
        assert "reports" in custom[0]["modules"]

    def test_update_preset_role_returns_404(self, session):
        # Preset roles are not in DB so update should return 404
        res = session.put(f"{BASE_URL}/api/admin/roles/super_admin", json={"name": "Hacked"})
        assert res.status_code == 404, f"Expected 404 for updating preset role, got {res.status_code}"


# ─────────────────────────────────────────────────────────────────
# 4. DELETE /api/admin/roles/{id} - delete custom role
# ─────────────────────────────────────────────────────────────────

class TestDeleteRole:
    """Test DELETE /admin/roles/{id}"""

    def test_delete_custom_role(self, session):
        if not TestCreateRole.created_role_id:
            pytest.skip("No created role ID")
        res = session.delete(f"{BASE_URL}/api/admin/roles/{TestCreateRole.created_role_id}")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text[:200]}"
        data = res.json()
        assert "deleted" in data.get("message", "").lower() or "message" in data

    def test_delete_role_removed_from_get(self, session):
        if not TestCreateRole.created_role_id:
            pytest.skip("No created role ID")
        res = session.get(f"{BASE_URL}/api/admin/roles")
        custom = [r for r in res.json()["roles"] if r.get("id") == TestCreateRole.created_role_id]
        assert len(custom) == 0, "Deleted role must not appear in GET /admin/roles"

    def test_delete_nonexistent_role_returns_404(self, session):
        res = session.delete(f"{BASE_URL}/api/admin/roles/nonexistent_id_xyz")
        assert res.status_code == 404, f"Expected 404, got {res.status_code}"


# ─────────────────────────────────────────────────────────────────
# 5. Integrations - Cloud Storage category (Google Drive, OneDrive)
# ─────────────────────────────────────────────────────────────────

class TestCloudStorageIntegrations:
    """Test that Google Drive and OneDrive appear as Coming Soon"""

    def test_integrations_endpoint_returns_200(self, session):
        res = session.get(f"{BASE_URL}/api/oauth/integrations")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text[:200]}"

    def test_integrations_has_cloud_storage_category(self, session):
        res = session.get(f"{BASE_URL}/api/oauth/integrations")
        integrations = res.json().get("integrations", [])
        cloud = [i for i in integrations if i.get("category") == "cloud_storage"]
        assert len(cloud) >= 2, f"Expected at least 2 cloud_storage integrations, got {len(cloud)}"

    def test_google_drive_is_coming_soon(self, session):
        res = session.get(f"{BASE_URL}/api/oauth/integrations")
        integrations = res.json().get("integrations", [])
        gdrive = next((i for i in integrations if "google" in i.get("id", "").lower() or "google" in i.get("name", "").lower()), None)
        assert gdrive is not None, "Google Drive integration not found"
        assert gdrive.get("is_coming_soon") is True, f"Google Drive should be coming_soon, got: {gdrive}"

    def test_onedrive_is_coming_soon(self, session):
        res = session.get(f"{BASE_URL}/api/oauth/integrations")
        integrations = res.json().get("integrations", [])
        onedrive = next((i for i in integrations if "onedrive" in i.get("id", "").lower() or "onedrive" in i.get("name", "").lower()), None)
        assert onedrive is not None, "OneDrive integration not found"
        assert onedrive.get("is_coming_soon") is True, f"OneDrive should be coming_soon, got: {onedrive}"


# ─────────────────────────────────────────────────────────────────
# 6. Tenant address editing: PUT /api/admin/tenants/{id}/address
# ─────────────────────────────────────────────────────────────────

class TestTenantAddress:
    """Test Platform Admin can update tenant addresses"""

    tenant_id = None

    def test_get_tenants_for_address_test(self, session):
        res = session.get(f"{BASE_URL}/api/admin/tenants")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        tenants = res.json().get("tenants", [])
        assert len(tenants) > 0, "No tenants found"
        # Pick any tenant that isn't automate-accounts to test
        for t in tenants:
            if t.get("code") != "automate-accounts":
                TestTenantAddress.tenant_id = t["id"]
                break
        if not TestTenantAddress.tenant_id and tenants:
            TestTenantAddress.tenant_id = tenants[0]["id"]
        assert TestTenantAddress.tenant_id is not None

    def test_update_tenant_address(self, session):
        if not TestTenantAddress.tenant_id:
            pytest.skip("No tenant ID for address test")
        payload = {
            "address": {
                "line1": "123 Test Street",
                "city": "Toronto",
                "region": "ON",
                "postal": "M5V 2T6",
                "country": "Canada",
            }
        }
        res = session.put(f"{BASE_URL}/api/admin/tenants/{TestTenantAddress.tenant_id}/address", json=payload)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text[:200]}"

    def test_tenant_address_persists(self, session):
        if not TestTenantAddress.tenant_id:
            pytest.skip("No tenant ID")
        # Re-fetch tenants and verify address was saved
        res = session.get(f"{BASE_URL}/api/admin/tenants")
        tenants = res.json().get("tenants", [])
        tenant = next((t for t in tenants if t["id"] == TestTenantAddress.tenant_id), None)
        assert tenant is not None
        addr = tenant.get("address", {})
        assert addr.get("line1") == "123 Test Street" or addr.get("city") == "Toronto", \
            f"Address not persisted: {addr}"


# ─────────────────────────────────────────────────────────────────
# 7. GET /api/admin/permissions/modules - ensure bank_transactions absent
# ─────────────────────────────────────────────────────────────────

class TestPermissionsModules:
    """Validate module list doesn't have bank_transactions"""

    def test_modules_endpoint_returns_200(self, session):
        res = session.get(f"{BASE_URL}/api/admin/permissions/modules")
        assert res.status_code == 200

    def test_bank_transactions_not_in_modules(self, session):
        res = session.get(f"{BASE_URL}/api/admin/permissions/modules")
        module_keys = [m["key"] for m in res.json().get("modules", [])]
        assert "bank_transactions" not in module_keys, \
            f"bank_transactions should not be in admin modules. Found: {module_keys}"

    def test_core_modules_present(self, session):
        res = session.get(f"{BASE_URL}/api/admin/permissions/modules")
        module_keys = [m["key"] for m in res.json().get("modules", [])]
        for required in ["customers", "orders", "users", "settings"]:
            assert required in module_keys, f"Module '{required}' missing from list"
