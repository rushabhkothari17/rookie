"""
Backend tests for iteration 166 - Users Tab Features:
1. GET /admin/users returns tenant_name field
2. POST /admin/users requires target_tenant_id for partner roles from platform admin
3. POST /admin/users blocks adding 2nd partner super admin
4. GET /admin/permissions/modules returns all_module_keys and partner_module_keys
5. Role dropdown options for platform super admin
6. Only ONE platform_super_admin in users list
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

PLATFORM_SUPER_ADMIN_EMAIL = "admin@automateaccounts.local"
PLATFORM_SUPER_ADMIN_PASS = "ChangeMe123!"
PARTNER_CODE = "automate-accounts"
PARTNER_ADMIN_LIGER_EMAIL = "admin@ligerinc.local"
PARTNER_ADMIN_LIGER_PASS = "ChangeMe123!"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def platform_super_admin_token(session):
    """Login as platform super admin."""
    r = session.post(f"{BASE_URL}/api/auth/admin-login", json={
        "partner_code": PARTNER_CODE,
        "email": PLATFORM_SUPER_ADMIN_EMAIL,
        "password": PLATFORM_SUPER_ADMIN_PASS,
    })
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.cookies.get("admin_access_token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def auth_session(session, platform_super_admin_token):
    """Session with platform super admin auth cookie."""
    if platform_super_admin_token:
        session.cookies.set("admin_access_token", platform_super_admin_token)
    return session


class TestGetAdminUsers:
    """Test GET /admin/users endpoint."""

    def test_get_users_returns_200(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/admin/users")
        assert r.status_code == 200, f"Failed: {r.text}"
        data = r.json()
        assert "users" in data
        print(f"PASS: GET /admin/users returns 200, found {len(data['users'])} users")

    def test_get_users_has_tenant_name_field(self, auth_session):
        """Verify tenant_name field is present in user objects."""
        r = auth_session.get(f"{BASE_URL}/api/admin/users")
        assert r.status_code == 200
        users = r.json()["users"]
        # At least check that the field exists (value could be None for platform users)
        for u in users:
            assert "tenant_name" in u, f"tenant_name missing for user {u.get('email')}"
        print(f"PASS: tenant_name field present in all {len(users)} users")

    def test_get_users_partner_users_have_tenant_name(self, auth_session):
        """Verify partner users have non-null tenant_name."""
        r = auth_session.get(f"{BASE_URL}/api/admin/users")
        assert r.status_code == 200
        users = r.json()["users"]
        partner_users = [u for u in users if u.get("role") in ("partner_admin", "partner_staff", "partner_super_admin")]
        if partner_users:
            found_with_name = [u for u in partner_users if u.get("tenant_name")]
            assert len(found_with_name) > 0, "Expected at least one partner user to have a tenant_name"
            print(f"PASS: {len(found_with_name)}/{len(partner_users)} partner users have tenant_name")
        else:
            print("SKIP: No partner users found in response")

    def test_get_users_has_pagination_fields(self, auth_session):
        """Verify pagination fields are present."""
        r = auth_session.get(f"{BASE_URL}/api/admin/users")
        assert r.status_code == 200
        data = r.json()
        assert "total" in data
        assert "total_pages" in data
        assert "page" in data
        print(f"PASS: Pagination fields present - total={data['total']}, pages={data['total_pages']}")

    def test_only_one_platform_super_admin(self, auth_session):
        """Verify only ONE platform_super_admin exists."""
        r = auth_session.get(f"{BASE_URL}/api/admin/users", params={"per_page": 100})
        assert r.status_code == 200
        users = r.json()["users"]
        psa_users = [u for u in users if u.get("role") == "platform_super_admin"]
        # Only active ones
        active_psa = [u for u in psa_users if u.get("is_active")]
        assert len(active_psa) == 1, f"Expected exactly 1 active platform_super_admin, got {len(active_psa)}: {[u['email'] for u in active_psa]}"
        assert active_psa[0]["email"] == PLATFORM_SUPER_ADMIN_EMAIL
        print(f"PASS: Exactly 1 active platform_super_admin: {active_psa[0]['email']}")

    def test_no_password_hash_in_response(self, auth_session):
        """Verify password_hash is not in response."""
        r = auth_session.get(f"{BASE_URL}/api/admin/users")
        assert r.status_code == 200
        for u in r.json()["users"]:
            assert "password_hash" not in u, f"password_hash leaked for {u.get('email')}"
        print("PASS: No password_hash in any user response")


class TestGetPermissionsModules:
    """Test GET /admin/permissions/modules endpoint."""

    def test_modules_endpoint_returns_200(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/admin/permissions/modules")
        assert r.status_code == 200, f"Failed: {r.text}"
        data = r.json()
        assert "modules" in data
        print(f"PASS: GET /admin/permissions/modules returns 200 with {len(data['modules'])} modules")

    def test_modules_has_partner_module_keys(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/admin/permissions/modules")
        assert r.status_code == 200
        data = r.json()
        assert "partner_module_keys" in data, "partner_module_keys missing from response"
        partner_keys = data["partner_module_keys"]
        expected_partner_modules = ["customers", "orders", "subscriptions", "products", "promo_codes", "content", "integrations", "webhooks", "settings", "users", "reports", "logs"]
        for key in expected_partner_modules:
            assert key in partner_keys, f"Expected partner module '{key}' in partner_module_keys"
        print(f"PASS: partner_module_keys present with {len(partner_keys)} keys")

    def test_modules_has_all_module_keys(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/admin/permissions/modules")
        assert r.status_code == 200
        data = r.json()
        assert "all_module_keys" in data, "all_module_keys missing from response"
        all_keys = data["all_module_keys"]
        # Should include both platform and partner modules
        platform_modules = ["partner_orgs", "plans", "billing_settings", "currencies"]
        for key in platform_modules:
            assert key in all_keys, f"Expected platform module '{key}' in all_module_keys"
        print(f"PASS: all_module_keys present with {len(all_keys)} keys (platform + partner)")

    def test_modules_platform_admin_sees_all_modules(self, auth_session):
        """Platform super admin should see all modules (platform + partner)."""
        r = auth_session.get(f"{BASE_URL}/api/admin/permissions/modules")
        assert r.status_code == 200
        data = r.json()
        module_keys = [m["key"] for m in data["modules"]]
        # Should include both platform and partner modules
        assert "partner_orgs" in module_keys, "partner_orgs (platform module) should be visible"
        assert "customers" in module_keys, "customers (partner module) should be visible"
        print(f"PASS: Platform super admin sees all {len(module_keys)} modules")

    def test_modules_has_preset_roles(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/admin/permissions/modules")
        assert r.status_code == 200
        data = r.json()
        assert "preset_roles" in data
        assert len(data["preset_roles"]) > 0
        print(f"PASS: preset_roles present with {len(data['preset_roles'])} presets")

    def test_partner_modules_not_include_platform_modules(self, auth_session):
        """Verify partner_module_keys does NOT include platform-only modules."""
        r = auth_session.get(f"{BASE_URL}/api/admin/permissions/modules")
        assert r.status_code == 200
        data = r.json()
        partner_keys = data["partner_module_keys"]
        platform_only = ["partner_orgs", "plans", "billing_settings", "currencies"]
        for key in platform_only:
            assert key not in partner_keys, f"Platform-only module '{key}' should NOT be in partner_module_keys"
        print(f"PASS: partner_module_keys does not contain platform-only modules")


class TestCreateUser:
    """Test POST /admin/users endpoint."""

    def test_create_partner_role_without_tenant_id_fails(self, auth_session):
        """Platform super admin creating a partner role without target_tenant_id should fail."""
        r = auth_session.post(f"{BASE_URL}/api/admin/users", json={
            "email": "TEST_nodest@example.com",
            "password": "TestPass123!",
            "role": "partner_admin",
            # no target_tenant_id
        })
        assert r.status_code in (400, 422), f"Expected 400/422, got {r.status_code}: {r.text}"
        print(f"PASS: Creating partner_admin without target_tenant_id returns {r.status_code}")

    def test_cannot_create_platform_super_admin(self, auth_session):
        """Platform super admin cannot be created manually."""
        r = auth_session.post(f"{BASE_URL}/api/admin/users", json={
            "email": "TEST_newsuperadmin@example.com",
            "password": "TestPass123!",
            "role": "platform_super_admin",
        })
        assert r.status_code in (400, 403), f"Expected 400/403, got {r.status_code}: {r.text}"
        print(f"PASS: Cannot create platform_super_admin manually - returns {r.status_code}")

    def test_partner_admin_role_is_valid_to_create(self, auth_session):
        """Verify partner_admin is in the list of creatable roles for platform super admin."""
        # We test this by checking the roles list is correct via the validate/roles concept
        # We know from the code that platform_super_admin can create: platform_admin, partner_super_admin, partner_admin, partner_staff
        # We can't easily test this without a valid target_tenant_id, but we can check the error message
        r = auth_session.post(f"{BASE_URL}/api/admin/users", json={
            "email": "TEST_partneradmin@example.com",
            "password": "TestPass123!",
            "role": "partner_admin",
            "target_tenant_id": "nonexistent-org-12345",
        })
        # Should fail with 404 (org not found) not 400 (invalid role)
        assert r.status_code in (400, 404), f"Unexpected status: {r.status_code}: {r.text}"
        # If 400, should NOT say "invalid roles"
        if r.status_code == 400:
            # Check it's NOT a role validation error
            detail = r.json().get("detail", "")
            assert "partner_admin" not in detail or "invalid" not in detail.lower()
        print(f"PASS: partner_admin role is recognized as valid (org not found = {r.status_code})")

    def test_create_partner_admin_with_invalid_tenant_returns_404(self, auth_session):
        """Creating a partner role user with nonexistent tenant_id returns 404."""
        r = auth_session.post(f"{BASE_URL}/api/admin/users", json={
            "email": "TEST_notenant@example.com",
            "password": "TestPass123!",
            "role": "partner_admin",
            "target_tenant_id": "nonexistent-tenant-xyz-999",
        })
        assert r.status_code == 404, f"Expected 404 for nonexistent tenant, got {r.status_code}: {r.text}"
        print(f"PASS: partner_admin with nonexistent tenant returns 404")

    def test_cannot_create_duplicate_partner_super_admin(self, auth_session):
        """Creating a 2nd partner_super_admin for the same org should fail."""
        # First, get the tenant that already has a super admin
        # Liger Inc should already have cadrashtishah@gmail.com or cadrashtishah1@gmail.com as partner_super_admin
        # We need to find the Liger Inc tenant ID
        r = auth_session.get(f"{BASE_URL}/api/admin/tenants", params={"search": "Liger"})
        assert r.status_code == 200
        tenants = r.json().get("tenants", [])
        liger_tenant = next((t for t in tenants if "liger" in t.get("name", "").lower()), None)
        
        if not liger_tenant:
            print("SKIP: Liger Inc tenant not found, skipping duplicate super admin test")
            pytest.skip("Liger Inc tenant not found")
        
        liger_id = liger_tenant["id"]
        
        # Try to create another partner_super_admin for Liger Inc
        r = auth_session.post(f"{BASE_URL}/api/admin/users", json={
            "email": "TEST_ligersuperadmin2@example.com",
            "password": "TestPass123!",
            "role": "partner_super_admin",
            "target_tenant_id": liger_id,
        })
        # Should fail with 400 - already has a super admin
        assert r.status_code == 400, f"Expected 400 for duplicate super admin, got {r.status_code}: {r.text}"
        detail = r.json().get("detail", "")
        assert "already has a partner super admin" in detail or "partner super admin" in detail.lower()
        print(f"PASS: Duplicate partner_super_admin blocked - {detail[:100]}")


class TestEditUser:
    """Test PUT /admin/users/{user_id} endpoint."""

    def test_edit_platform_super_admin_is_blocked(self, auth_session):
        """Platform super admin cannot be edited."""
        # Get platform super admin user ID
        r = auth_session.get(f"{BASE_URL}/api/admin/users", params={"per_page": 100})
        assert r.status_code == 200
        users = r.json()["users"]
        psa = next((u for u in users if u.get("role") == "platform_super_admin"), None)
        if not psa:
            pytest.skip("No platform_super_admin found")
        
        r = auth_session.put(f"{BASE_URL}/api/admin/users/{psa['id']}", json={"full_name": "Hacked"})
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
        print(f"PASS: Editing platform_super_admin returns 403")

    def test_edit_user_role_change_supported(self, auth_session):
        """Verify role change field is accepted in PUT /admin/users."""
        # Get a partner_admin user to edit
        r = auth_session.get(f"{BASE_URL}/api/admin/users", params={"per_page": 100})
        assert r.status_code == 200
        users = r.json()["users"]
        partner_admin = next((u for u in users if u.get("role") == "partner_admin" and u.get("is_active")), None)
        if not partner_admin:
            pytest.skip("No active partner_admin found to test role change")
        
        # Try to change role (we'll just see if the endpoint accepts it; change to partner_staff and back)
        original_role = partner_admin["role"]
        new_role = "partner_staff"
        
        r = auth_session.put(f"{BASE_URL}/api/admin/users/{partner_admin['id']}", json={
            "full_name": partner_admin.get("full_name", "Test User"),
            "role": new_role,
        })
        assert r.status_code == 200, f"Role change failed: {r.text}"
        updated = r.json().get("user", {})
        assert updated.get("role") == new_role, f"Role not updated: {updated.get('role')}"
        
        # Revert
        auth_session.put(f"{BASE_URL}/api/admin/users/{partner_admin['id']}", json={
            "full_name": partner_admin.get("full_name", "Test User"),
            "role": original_role,
        })
        print(f"PASS: Role change from {original_role} to {new_role} and back works")
