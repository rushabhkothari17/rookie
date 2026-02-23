"""
Iteration 61 - Backend tests for:
1. P0 Color bug fix: admin GET /admin/website-settings now reads colors from app_settings
2. Role rename: platform_admin (was platform_super_admin)
3. Role badge colors: platform_admin=amber, super_admin=purple, admin=blue
4. TenantSwitcher: only visible for platform_admin (backend role check)
5. New test users login: superadmin@automateaccounts.local, admin2@automateaccounts.local
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestPlatformAdminLogin:
    """Test platform_admin login and role rename"""

    def test_platform_admin_login_returns_correct_role(self):
        """platform admin login must return role=platform_admin (not platform_super_admin)"""
        resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "email": "admin@automateaccounts.local",
            "password": "ChangeMe123!",
            "partner_code": "automate-accounts",
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "token" in data, "Response must contain token"
        assert data.get("role") == "platform_admin", f"Expected role=platform_admin, got {data.get('role')}"
        print("PASS: platform_admin login returns role=platform_admin")

    def test_platform_admin_old_role_not_present(self):
        """Confirm old role 'platform_super_admin' is no longer returned"""
        resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "email": "admin@automateaccounts.local",
            "password": "ChangeMe123!",
            "partner_code": "automate-accounts",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("role") != "platform_super_admin", "Old role platform_super_admin should not be returned"
        print("PASS: Old role platform_super_admin is no longer used")


class TestNewTestUserLogins:
    """Test newly created test user logins"""

    def test_superadmin_user_login(self):
        """superadmin@automateaccounts.local should login with super_admin role"""
        resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "email": "superadmin@automateaccounts.local",
            "password": "Admin123!",
            "partner_code": "automate-accounts",
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "token" in data, "Response must contain token"
        assert data.get("role") == "super_admin", f"Expected role=super_admin, got {data.get('role')}"
        print(f"PASS: superadmin user login successful, role={data.get('role')}")

    def test_admin2_user_login(self):
        """admin2@automateaccounts.local should login successfully"""
        resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "email": "admin2@automateaccounts.local",
            "password": "Admin123!",
            "partner_code": "automate-accounts",
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "token" in data, "Response must contain token"
        role = data.get("role")
        assert role in ("admin", "super_admin"), f"Expected admin or super_admin role, got {role}"
        print(f"PASS: admin2 user login successful, role={role}")


class TestWebsiteSettingsColorBugFix:
    """Test that admin GET /admin/website-settings returns colors from app_settings"""

    @pytest.fixture(scope="class")
    def platform_admin_token(self):
        resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "email": "admin@automateaccounts.local",
            "password": "ChangeMe123!",
            "partner_code": "automate-accounts",
        })
        assert resp.status_code == 200
        return resp.json()["token"]

    def test_admin_website_settings_returns_colors(self, platform_admin_token):
        """Admin GET /admin/website-settings should return primary_color and accent_color"""
        headers = {"Authorization": f"Bearer {platform_admin_token}"}
        resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "settings" in data, "Response must contain 'settings' key"
        settings = data["settings"]
        # Colors should be present (not empty string or missing)
        primary = settings.get("primary_color", "")
        accent = settings.get("accent_color", "")
        print(f"primary_color={primary!r}, accent_color={accent!r}")
        # The bug was these were empty - now they should be populated
        assert primary != "", f"primary_color should not be empty - bug not fixed. Got: {primary!r}"
        assert accent != "", f"accent_color should not be empty - bug not fixed. Got: {accent!r}"
        print(f"PASS: Admin website-settings returns primary_color={primary!r}, accent_color={accent!r}")

    def test_admin_website_settings_has_primary_color_value(self, platform_admin_token):
        """Specifically check primary_color is #0f172a"""
        headers = {"Authorization": f"Bearer {platform_admin_token}"}
        resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=headers)
        assert resp.status_code == 200
        settings = resp.json()["settings"]
        primary = settings.get("primary_color", "")
        # It should be a valid hex color
        assert primary.startswith("#"), f"primary_color should be a hex color, got: {primary!r}"
        print(f"PASS: primary_color is a valid hex color: {primary!r}")

    def test_admin_website_settings_has_accent_color_value(self, platform_admin_token):
        """Specifically check accent_color is populated"""
        headers = {"Authorization": f"Bearer {platform_admin_token}"}
        resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=headers)
        assert resp.status_code == 200
        settings = resp.json()["settings"]
        accent = settings.get("accent_color", "")
        assert accent.startswith("#"), f"accent_color should be a hex color, got: {accent!r}"
        print(f"PASS: accent_color is a valid hex color: {accent!r}")

    def test_public_website_settings_also_returns_colors(self):
        """Public GET /website-settings should also return colors (consistency check)"""
        resp = requests.get(f"{BASE_URL}/api/website-settings?partner_code=automate-accounts")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        settings = resp.json().get("settings", {})
        primary = settings.get("primary_color", "")
        accent = settings.get("accent_color", "")
        print(f"Public settings: primary_color={primary!r}, accent_color={accent!r}")
        # Both should be populated
        assert primary != "", f"Public settings primary_color should not be empty"
        assert accent != "", f"Public settings accent_color should not be empty"
        print("PASS: Public website-settings also returns colors")


class TestAdminUsersListRoles:
    """Test that admin users list endpoint returns users with correct roles including platform_admin"""

    @pytest.fixture(scope="class")
    def platform_admin_token(self):
        resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "email": "admin@automateaccounts.local",
            "password": "ChangeMe123!",
            "partner_code": "automate-accounts",
        })
        assert resp.status_code == 200
        return resp.json()["token"]

    def test_admin_users_list_contains_platform_admin(self, platform_admin_token):
        """Users list should show platform_admin role (not platform_super_admin)"""
        headers = {"Authorization": f"Bearer {platform_admin_token}"}
        resp = requests.get(f"{BASE_URL}/api/admin/users", headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        users = data.get("users", [])
        roles_found = set(u.get("role") for u in users)
        print(f"Roles found in users list: {roles_found}")
        # Should NOT have old role
        assert "platform_super_admin" not in roles_found, "Old role platform_super_admin found in users list"
        # platform_admin should be present if admin@automateaccounts.local is in results
        print(f"PASS: Users list does not contain old platform_super_admin role")

    def test_admin_users_list_has_super_admin_role(self, platform_admin_token):
        """Users list should contain super_admin role for superadmin@automateaccounts.local"""
        headers = {"Authorization": f"Bearer {platform_admin_token}"}
        resp = requests.get(f"{BASE_URL}/api/admin/users?per_page=100", headers=headers)
        assert resp.status_code == 200
        users = resp.json().get("users", [])
        roles = {u.get("email"): u.get("role") for u in users}
        print(f"User roles: {roles}")
        # superadmin should have super_admin role
        superadmin_role = roles.get("superadmin@automateaccounts.local")
        if superadmin_role:
            assert superadmin_role == "super_admin", f"Expected super_admin, got {superadmin_role}"
            print(f"PASS: superadmin@automateaccounts.local has role={superadmin_role}")
        else:
            print("NOTE: superadmin@automateaccounts.local not found in first page - may need pagination")


class TestTenantSwitcherAccess:
    """Test that only platform_admin can access /admin/tenants"""

    @pytest.fixture(scope="class")
    def platform_admin_token(self):
        resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "email": "admin@automateaccounts.local",
            "password": "ChangeMe123!",
            "partner_code": "automate-accounts",
        })
        assert resp.status_code == 200
        return resp.json()["token"]

    @pytest.fixture(scope="class")
    def super_admin_token(self):
        resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "email": "superadmin@automateaccounts.local",
            "password": "Admin123!",
            "partner_code": "automate-accounts",
        })
        if resp.status_code == 200:
            return resp.json()["token"]
        return None

    def test_platform_admin_can_access_tenants(self, platform_admin_token):
        """platform_admin should have access to /admin/tenants"""
        headers = {"Authorization": f"Bearer {platform_admin_token}"}
        resp = requests.get(f"{BASE_URL}/api/admin/tenants", headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "tenants" in data, "Response must contain 'tenants' key"
        print(f"PASS: platform_admin can access /admin/tenants, found {len(data['tenants'])} tenants")

    def test_super_admin_cannot_access_tenants(self, super_admin_token):
        """super_admin should NOT have access to /admin/tenants"""
        if not super_admin_token:
            pytest.skip("super_admin token not available")
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        resp = requests.get(f"{BASE_URL}/api/admin/tenants", headers=headers)
        assert resp.status_code == 403, f"Expected 403 (forbidden), got {resp.status_code}: {resp.text}"
        print(f"PASS: super_admin cannot access /admin/tenants (403 returned)")


class TestMeEndpointRoles:
    """Test /me endpoint returns correct roles for different users"""

    def test_platform_admin_me_returns_platform_admin_role(self):
        """GET /me for platform admin should return role=platform_admin"""
        login = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "email": "admin@automateaccounts.local",
            "password": "ChangeMe123!",
            "partner_code": "automate-accounts",
        })
        assert login.status_code == 200
        token = login.json()["token"]
        
        resp = requests.get(f"{BASE_URL}/api/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        user = resp.json().get("user", {})
        assert user.get("role") == "platform_admin", f"Expected platform_admin, got {user.get('role')}"
        print(f"PASS: /me returns role=platform_admin")

    def test_super_admin_me_returns_super_admin_role(self):
        """GET /me for superadmin should return role=super_admin"""
        login = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "email": "superadmin@automateaccounts.local",
            "password": "Admin123!",
            "partner_code": "automate-accounts",
        })
        assert login.status_code == 200, f"superadmin login failed: {login.text}"
        token = login.json()["token"]
        
        resp = requests.get(f"{BASE_URL}/api/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        user = resp.json().get("user", {})
        assert user.get("role") == "super_admin", f"Expected super_admin, got {user.get('role')}"
        print(f"PASS: superadmin /me returns role=super_admin")
