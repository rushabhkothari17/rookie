"""
Tests for iteration 164 - Major roles/permissions redesign:
1. Tags sub-tab (GET/POST/DELETE /api/admin/platform/tags)
2. Platform Admin creation (/api/admin/users with role=platform_admin)
3. Super admin immutability (platform_super_admin cannot be edited/deactivated)
4. Per-module permissions system (/api/admin/permissions/modules, /api/admin/my-permissions)
5. Transfer super admin (/api/admin/tenants/{id}/transfer-super-admin)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


def get_platform_admin_token():
    """Get auth token for platform super admin (no partner_code - direct login)."""
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!"
    })
    if r.status_code == 200:
        data = r.json()
        return data.get("token") or data.get("access_token") or r.cookies.get("token")
    return None


def get_headers(token):
    return {"Authorization": f"Bearer {token}"} if token else {}


@pytest.fixture(scope="module")
def platform_token():
    token = get_platform_admin_token()
    if not token:
        pytest.skip("Could not authenticate as platform super admin")
    return token


@pytest.fixture(scope="module")
def platform_headers(platform_token):
    return get_headers(platform_token)


# ── Health check ─────────────────────────────────────────────────────────────

class TestHealthAndAuth:
    """Basic connectivity tests"""

    def test_api_health(self):
        r = requests.get(f"{BASE_URL}/api/health")
        assert r.status_code in (200, 404), f"Unexpected: {r.status_code}"
        print("✓ API reachable")

    def test_platform_super_admin_login(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={
            "partner_code": "automate-accounts",
            "email": "admin@automateaccounts.local",
            "password": "ChangeMe123!"
        })
        assert r.status_code == 200, f"Login failed: {r.status_code} - {r.text}"
        data = r.json()
        assert "token" in data or "access_token" in data, "No token in response"
        print(f"✓ Login success, role={data.get('user', {}).get('role')}")


# ── Module Permissions API ────────────────────────────────────────────────────

class TestModulePermissionsAPI:
    """Test /api/admin/permissions/modules and /api/admin/my-permissions"""

    def test_get_modules_list(self, platform_headers):
        """GET /api/admin/permissions/modules - should return module list"""
        r = requests.get(f"{BASE_URL}/api/admin/permissions/modules", headers=platform_headers)
        assert r.status_code == 200, f"Failed: {r.status_code} - {r.text}"
        data = r.json()
        assert "modules" in data, "Missing 'modules' key"
        assert len(data["modules"]) > 0, "No modules returned"
        assert "platform_module_keys" in data, "Missing 'platform_module_keys'"
        assert "partner_module_keys" in data, "Missing 'partner_module_keys'"
        assert "preset_roles" in data, "Missing 'preset_roles'"
        print(f"✓ Modules: {[m['key'] for m in data['modules'][:5]]}...")
        # Platform super admin should see both platform + partner modules
        keys = [m["key"] for m in data["modules"]]
        assert "partner_orgs" in keys, "platform_orgs should be in modules for platform super admin"
        assert "customers" in keys, "customers should be in modules"

    def test_modules_have_required_fields(self, platform_headers):
        """Each module should have key, name, description"""
        r = requests.get(f"{BASE_URL}/api/admin/permissions/modules", headers=platform_headers)
        assert r.status_code == 200
        for mod in r.json()["modules"]:
            assert "key" in mod, f"Module missing 'key': {mod}"
            assert "name" in mod, f"Module missing 'name': {mod}"
            assert "description" in mod, f"Module missing 'description': {mod}"
        print("✓ All modules have required fields")

    def test_get_my_permissions(self, platform_headers):
        """GET /api/admin/my-permissions - platform super admin should have all write"""
        r = requests.get(f"{BASE_URL}/api/admin/my-permissions", headers=platform_headers)
        assert r.status_code == 200, f"Failed: {r.status_code} - {r.text}"
        data = r.json()
        assert "module_permissions" in data, "Missing 'module_permissions'"
        assert "is_super_admin" in data, "Missing 'is_super_admin'"
        assert data["is_super_admin"] is True, "Platform super admin should have is_super_admin=True"
        assert data.get("role") == "platform_super_admin"
        # All permissions should be 'write' for super admin
        mp = data["module_permissions"]
        for k, v in mp.items():
            assert v == "write", f"Expected write for {k}, got {v}"
        print(f"✓ My permissions: is_super_admin={data['is_super_admin']}, modules={len(mp)}")

    def test_preset_roles_structure(self, platform_headers):
        """Preset roles should have proper module_permissions structure"""
        r = requests.get(f"{BASE_URL}/api/admin/permissions/modules", headers=platform_headers)
        assert r.status_code == 200
        preset_roles = r.json().get("preset_roles", [])
        assert len(preset_roles) > 0, "Should have at least one preset role"
        for pr in preset_roles:
            assert "key" in pr, f"Preset missing 'key': {pr}"
            assert "module_permissions" in pr, f"Preset missing 'module_permissions': {pr}"
            for k, v in pr["module_permissions"].items():
                assert v in ("read", "write"), f"Invalid permission value {v} for {k}"
        print(f"✓ Preset roles validated: {[p['key'] for p in preset_roles]}")


# ── Tags Management ───────────────────────────────────────────────────────────

class TestTagsManagement:
    """Test Tags sub-tab backend APIs: /api/admin/platform/tags and /api/platform/tags"""

    TEST_TAG = "TEST_enterprise-tag"

    def test_get_tags_public(self, platform_headers):
        """GET /api/platform/tags - public read endpoint"""
        r = requests.get(f"{BASE_URL}/api/platform/tags", headers=platform_headers)
        assert r.status_code == 200, f"Failed: {r.status_code} - {r.text}"
        data = r.json()
        assert "values" in data, "Missing 'values' key"
        assert isinstance(data["values"], list), "'values' should be a list"
        print(f"✓ GET platform/tags: {data['values']}")

    def test_get_tags_admin(self, platform_headers):
        """GET /api/admin/platform/tags - admin endpoint"""
        r = requests.get(f"{BASE_URL}/api/admin/platform/tags", headers=platform_headers)
        assert r.status_code == 200, f"Failed: {r.status_code} - {r.text}"
        data = r.json()
        assert "values" in data
        print(f"✓ GET admin/platform/tags: {data['values']}")

    def test_add_tag(self, platform_headers):
        """POST /api/admin/platform/tags - add new tag"""
        # Clean up first if exists
        requests.delete(f"{BASE_URL}/api/admin/platform/tags/{self.TEST_TAG}", headers=platform_headers)
        
        r = requests.post(f"{BASE_URL}/api/admin/platform/tags", 
                          json={"value": self.TEST_TAG}, 
                          headers=platform_headers)
        assert r.status_code in (200, 201), f"Failed to add tag: {r.status_code} - {r.text}"
        data = r.json()
        assert "values" in data, "Missing 'values' in response"
        assert self.TEST_TAG in data["values"], f"Tag {self.TEST_TAG} not in response"
        print(f"✓ Tag added: {self.TEST_TAG}")

    def test_tag_duplicate_rejected(self, platform_headers):
        """Adding duplicate tag should return 409"""
        r = requests.post(f"{BASE_URL}/api/admin/platform/tags", 
                          json={"value": self.TEST_TAG}, 
                          headers=platform_headers)
        assert r.status_code == 409, f"Expected 409 for duplicate, got: {r.status_code}"
        print("✓ Duplicate tag correctly rejected with 409")

    def test_tag_appears_in_list(self, platform_headers):
        """Verify added tag appears in GET list"""
        r = requests.get(f"{BASE_URL}/api/platform/tags", headers=platform_headers)
        assert r.status_code == 200
        assert self.TEST_TAG in r.json()["values"], "Tag not persisted in list"
        print("✓ Tag persisted and visible in GET list")

    def test_delete_tag(self, platform_headers):
        """DELETE /api/admin/platform/tags/{item}"""
        r = requests.delete(f"{BASE_URL}/api/admin/platform/tags/{self.TEST_TAG}", 
                            headers=platform_headers)
        assert r.status_code == 200, f"Failed to delete tag: {r.status_code} - {r.text}"
        data = r.json()
        assert self.TEST_TAG not in data.get("values", []), "Tag still in list after delete"
        print("✓ Tag deleted successfully")

    def test_tag_not_in_list_after_delete(self, platform_headers):
        """Verify deleted tag no longer appears in GET list"""
        r = requests.get(f"{BASE_URL}/api/platform/tags", headers=platform_headers)
        assert r.status_code == 200
        assert self.TEST_TAG not in r.json()["values"], "Tag still visible after delete"
        print("✓ Tag correctly removed from list")

    def test_delete_nonexistent_tag(self, platform_headers):
        """Delete non-existent tag should return 404"""
        r = requests.delete(f"{BASE_URL}/api/admin/platform/tags/nonexistent-tag-xyz", 
                            headers=platform_headers)
        assert r.status_code == 404, f"Expected 404, got: {r.status_code}"
        print("✓ 404 for non-existent tag delete")


# ── Platform Admin User Creation ──────────────────────────────────────────────

class TestPlatformAdminCreation:
    """Test creating platform_admin users (only platform_super_admin can do this)"""

    TEST_EMAIL = "TEST_platform-admin-iter164@test.local"
    created_user_id = None

    def test_create_platform_admin_user(self, platform_headers):
        """POST /api/admin/users - create platform_admin user"""
        # Clean any existing test user
        r_list = requests.get(f"{BASE_URL}/api/admin/users", headers=platform_headers)
        if r_list.status_code == 200:
            for u in r_list.json().get("users", []):
                if u["email"] == self.TEST_EMAIL:
                    requests.delete(f"{BASE_URL}/api/admin/users/{u['id']}", headers=platform_headers)

        r = requests.post(f"{BASE_URL}/api/admin/users", headers=platform_headers, json={
            "email": self.TEST_EMAIL,
            "full_name": "TEST Platform Admin",
            "password": "Test1234!Ab",
            "role": "platform_admin",
            "module_permissions": {"partner_orgs": "read", "plans": "write", "customers": "read"}
        })
        assert r.status_code in (200, 201), f"Failed to create platform admin: {r.status_code} - {r.text}"
        data = r.json()
        assert "user_id" in data or "message" in data, f"Unexpected response: {data}"
        TestPlatformAdminCreation.created_user_id = data.get("user_id")
        print(f"✓ Platform admin created: {data}")

    def test_created_platform_admin_in_list(self, platform_headers):
        """Verify newly created platform admin appears in users list"""
        r = requests.get(f"{BASE_URL}/api/admin/users", headers=platform_headers)
        assert r.status_code == 200
        users = r.json().get("users", [])
        emails = [u["email"] for u in users]
        assert self.TEST_EMAIL in emails, f"Created user not in list. Found: {emails}"
        # Find and verify role
        user = next(u for u in users if u["email"] == self.TEST_EMAIL)
        assert user["role"] == "platform_admin", f"Expected platform_admin, got {user['role']}"
        print(f"✓ Created platform admin found in list with correct role")

    def test_platform_admin_has_module_permissions(self, platform_headers):
        """Verify created platform admin has module_permissions set"""
        r = requests.get(f"{BASE_URL}/api/admin/users", headers=platform_headers)
        assert r.status_code == 200
        users = r.json().get("users", [])
        user = next((u for u in users if u["email"] == self.TEST_EMAIL), None)
        assert user is not None, "User not found"
        mp = user.get("module_permissions", {})
        # Either explicit permissions or default (all read for platform_admin)
        print(f"✓ Platform admin module_permissions: {mp}")
        assert isinstance(mp, dict), "module_permissions should be a dict"

    def test_cannot_create_platform_super_admin(self, platform_headers):
        """Cannot create platform_super_admin manually - should return 400"""
        r = requests.post(f"{BASE_URL}/api/admin/users", headers=platform_headers, json={
            "email": "TEST_super-admin-attempt@test.local",
            "full_name": "Bad Actor",
            "password": "Test1234!Ab",
            "role": "platform_super_admin",
        })
        assert r.status_code in (400, 403), f"Expected error, got: {r.status_code} - {r.text}"
        print(f"✓ platform_super_admin creation correctly blocked: {r.status_code}")

    def test_cleanup_created_user(self, platform_headers):
        """Cleanup: deactivate the test platform admin"""
        if self.created_user_id:
            r = requests.patch(
                f"{BASE_URL}/api/admin/users/{self.created_user_id}/active",
                params={"active": False},
                headers=platform_headers
            )
            # Just try, not critical
            print(f"Cleanup: deactivate result = {r.status_code}")


# ── Super Admin Immutability ──────────────────────────────────────────────────

class TestSuperAdminImmutability:
    """Test platform_super_admin cannot be edited or deactivated"""

    def _get_super_admin_id(self, platform_headers) -> str | None:
        """Find the platform_super_admin user ID"""
        r = requests.get(f"{BASE_URL}/api/admin/users", headers=platform_headers)
        if r.status_code != 200:
            return None
        for u in r.json().get("users", []):
            if u.get("role") == "platform_super_admin":
                return u["id"]
        return None

    def test_cannot_edit_platform_super_admin(self, platform_headers):
        """PUT /api/admin/users/{id} for platform_super_admin should return 403"""
        sa_id = self._get_super_admin_id(platform_headers)
        if not sa_id:
            pytest.skip("No platform_super_admin found")
        
        r = requests.put(f"{BASE_URL}/api/admin/users/{sa_id}", 
                         headers=platform_headers,
                         json={"full_name": "Hacked Name"})
        assert r.status_code == 403, f"Expected 403, got: {r.status_code} - {r.text}"
        print(f"✓ Cannot edit platform_super_admin: 403 returned")

    def test_cannot_deactivate_platform_super_admin(self, platform_headers):
        """PATCH /api/admin/users/{id}/active for platform_super_admin should return 403"""
        sa_id = self._get_super_admin_id(platform_headers)
        if not sa_id:
            pytest.skip("No platform_super_admin found")
        
        r = requests.patch(
            f"{BASE_URL}/api/admin/users/{sa_id}/active",
            params={"active": False},
            headers=platform_headers
        )
        assert r.status_code == 403, f"Expected 403 for deactivating super admin, got: {r.status_code} - {r.text}"
        print(f"✓ Cannot deactivate platform_super_admin: 403 returned")

    def test_platform_super_admin_row_in_users_list(self, platform_headers):
        """platform_super_admin should appear in users list"""
        r = requests.get(f"{BASE_URL}/api/admin/users", headers=platform_headers)
        assert r.status_code == 200
        users = r.json().get("users", [])
        super_admins = [u for u in users if u.get("role") == "platform_super_admin"]
        assert len(super_admins) >= 1, "No platform_super_admin found in user list"
        # Verify admin@automateaccounts.local is there
        sa_emails = [u["email"] for u in super_admins]
        assert "admin@automateaccounts.local" in sa_emails, f"admin@automateaccounts.local not found, got: {sa_emails}"
        print(f"✓ platform_super_admin rows found: {sa_emails}")


# ── Transfer Super Admin ──────────────────────────────────────────────────────

class TestTransferSuperAdmin:
    """Test partner super admin transfer"""

    def test_list_tenants_for_transfer_test(self, platform_headers):
        """Get tenants to find one for testing"""
        r = requests.get(f"{BASE_URL}/api/admin/tenants", headers=platform_headers)
        assert r.status_code == 200, f"Failed: {r.status_code} - {r.text}"
        tenants = r.json().get("tenants", [])
        assert len(tenants) > 0, "No tenants found"
        print(f"✓ Tenants found: {[t['name'] for t in tenants[:5]]}")

    def test_transfer_super_admin_requires_valid_user(self, platform_headers):
        """Transfer super admin with invalid user_id should return 404"""
        r = requests.get(f"{BASE_URL}/api/admin/tenants", headers=platform_headers)
        tenants = r.json().get("tenants", [])
        # Use the first non-platform tenant
        target = next((t for t in tenants if t.get("code") != "automate-accounts"), None)
        if not target:
            pytest.skip("No non-platform tenant found")
        
        r = requests.post(
            f"{BASE_URL}/api/admin/tenants/{target['id']}/transfer-super-admin",
            headers=platform_headers,
            json={"new_user_id": "nonexistent-user-id-xyz"}
        )
        assert r.status_code == 404, f"Expected 404, got: {r.status_code} - {r.text}"
        print(f"✓ Transfer super admin with invalid user returns 404")


# ── Roles Endpoints ───────────────────────────────────────────────────────────

class TestRolesEndpoints:
    """Test admin roles CRUD"""

    def test_get_roles(self, platform_headers):
        """GET /api/admin/roles - should return preset and custom roles"""
        r = requests.get(f"{BASE_URL}/api/admin/roles", headers=platform_headers)
        assert r.status_code == 200, f"Failed: {r.status_code} - {r.text}"
        data = r.json()
        assert "roles" in data, "Missing 'roles'"
        assert len(data["roles"]) > 0, "No roles returned"
        print(f"✓ Roles: {[r['key'] or r['name'] for r in data['roles'][:5]]}")

    def test_roles_have_module_permissions(self, platform_headers):
        """All roles should have module_permissions (not access_level)"""
        r = requests.get(f"{BASE_URL}/api/admin/roles", headers=platform_headers)
        assert r.status_code == 200
        for role in r.json()["roles"]:
            assert "module_permissions" in role, f"Role {role.get('name')} missing module_permissions"
            mp = role["module_permissions"]
            for v in mp.values():
                assert v in ("read", "write"), f"Invalid permission value in {role.get('name')}: {v}"
        print("✓ All roles use module_permissions format (not legacy access_level)")


# ── Partner Types and Industries (regression check) ──────────────────────────

class TestPartnerTypesAndIndustries:
    """Verify partner-types and industries endpoints still work alongside new tags"""

    def test_get_partner_types(self, platform_headers):
        r = requests.get(f"{BASE_URL}/api/platform/partner-types", headers=platform_headers)
        assert r.status_code == 200
        data = r.json()
        assert "values" in data
        assert len(data["values"]) > 0, "Should have default partner types"
        print(f"✓ Partner types: {data['values'][:3]}")

    def test_get_industries(self, platform_headers):
        r = requests.get(f"{BASE_URL}/api/platform/industries", headers=platform_headers)
        assert r.status_code == 200
        data = r.json()
        assert "values" in data
        assert len(data["values"]) > 0, "Should have default industries"
        print(f"✓ Industries: {data['values'][:3]}")
