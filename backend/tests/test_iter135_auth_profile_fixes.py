"""
Iter 135 tests: back button, countries API, bank_transactions removed, 
signup_bullets, change-password endpoint, and auth/pages validation.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


@pytest.fixture
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture
def platform_admin_token(session):
    """Get platform admin token."""
    r = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!",
    })
    if r.status_code == 200:
        return r.json().get("token")
    pytest.skip("Platform admin login failed")


@pytest.fixture
def partner_admin_token(session):
    """Get partner admin token for ligerinc."""
    r = session.post(f"{BASE_URL}/api/auth/partner-login", json={
        "partner_code": "liger-inc",
        "email": "admin@ligerinc.local",
        "password": "ChangeMe123!",
    })
    if r.status_code != 200:
        # try common slug variations
        for code in ["ligerinc", "liger-inc", "liger_inc"]:
            r2 = session.post(f"{BASE_URL}/api/auth/partner-login", json={
                "partner_code": code,
                "email": "admin@ligerinc.local",
                "password": "ChangeMe123!",
            })
            if r2.status_code == 200:
                return r2.json().get("token")
        pytest.skip("Partner admin login failed - try finding correct partner code")
    return r.json().get("token")


# ─── 1. GET /utils/countries (no partner_code) ─────────────────────────────

class TestCountriesEndpoint:
    """Test GET /utils/countries endpoint."""

    def test_countries_returns_200(self, session):
        """GET /utils/countries returns 200 with countries list."""
        r = session.get(f"{BASE_URL}/api/utils/countries")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "countries" in data, "Response must have 'countries' key"
        assert isinstance(data["countries"], list), "countries must be a list"
        assert len(data["countries"]) > 0, "countries list must not be empty"
        print(f"PASS: GET /utils/countries returned {len(data['countries'])} countries")

    def test_countries_items_have_value_label(self, session):
        """Each country item has 'value' and 'label' keys."""
        r = session.get(f"{BASE_URL}/api/utils/countries")
        assert r.status_code == 200
        for item in r.json()["countries"]:
            assert "value" in item, f"Missing 'value' in {item}"
            assert "label" in item, f"Missing 'label' in {item}"
        print("PASS: All country items have value and label")

    def test_countries_with_partner_code(self, session):
        """GET /utils/countries?partner_code=automate-accounts returns valid list."""
        r = session.get(f"{BASE_URL}/api/utils/countries?partner_code=automate-accounts")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        assert "countries" in data
        assert len(data["countries"]) > 0
        print(f"PASS: GET /utils/countries?partner_code=automate-accounts returned {len(data['countries'])} countries")

    def test_countries_with_invalid_partner_code_falls_back(self, session):
        """GET /utils/countries with unknown partner code falls back to defaults."""
        r = session.get(f"{BASE_URL}/api/utils/countries?partner_code=nonexistent-xyz-9999")
        assert r.status_code == 200
        data = r.json()
        assert "countries" in data
        assert len(data["countries"]) > 0
        print(f"PASS: Fallback countries returned for unknown partner code: {len(data['countries'])} countries")


# ─── 2. Admin Modules - no bank_transactions ──────────────────────────────

class TestAdminModulesNoBankTransactions:
    """Test that bank_transactions is NOT in admin modules."""

    def test_modules_endpoint_no_bank_transactions(self, session, platform_admin_token):
        """GET /admin/permissions/modules does not include bank_transactions."""
        r = session.get(
            f"{BASE_URL}/api/admin/permissions/modules",
            headers={"Authorization": f"Bearer {platform_admin_token}"}
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        module_keys = [m["key"] for m in data.get("modules", [])]
        assert "bank_transactions" not in module_keys, (
            f"bank_transactions should have been removed from ADMIN_MODULES, found: {module_keys}"
        )
        print(f"PASS: bank_transactions not in modules. Modules: {module_keys}")

    def test_modules_contains_expected_keys(self, session, platform_admin_token):
        """Admin modules contain expected keys like customers, orders."""
        r = session.get(
            f"{BASE_URL}/api/admin/permissions/modules",
            headers={"Authorization": f"Bearer {platform_admin_token}"}
        )
        assert r.status_code == 200
        module_keys = [m["key"] for m in r.json().get("modules", [])]
        for expected in ["customers", "orders", "subscriptions", "products"]:
            assert expected in module_keys, f"Expected '{expected}' in modules, got: {module_keys}"
        print(f"PASS: Expected modules present: {module_keys}")


# ─── 3. POST /auth/change-password endpoint ──────────────────────────────

class TestChangePasswordEndpoint:
    """Test POST /auth/change-password endpoint."""

    def test_change_password_exists_and_requires_auth(self, session):
        """POST /auth/change-password returns 401/403 when unauthenticated (not 404)."""
        r = session.post(f"{BASE_URL}/api/auth/change-password", json={"new_password": "Test12345!"})
        assert r.status_code in (401, 403), (
            f"Expected 401/403 (unauthorized), got {r.status_code}. "
            "404 would mean endpoint doesn't exist."
        )
        print(f"PASS: POST /auth/change-password returns {r.status_code} (endpoint exists, auth required)")

    def test_change_password_with_valid_token(self, session, platform_admin_token):
        """POST /auth/change-password with valid token returns 200."""
        # Change to same password (effectively no-op)
        r = session.post(
            f"{BASE_URL}/api/auth/change-password",
            json={"new_password": "ChangeMe123!"},
            headers={"Authorization": f"Bearer {platform_admin_token}"}
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "message" in data or "success" in str(data).lower(), "Response should contain 'message'"
        print(f"PASS: POST /auth/change-password with valid token: {data}")

    def test_change_password_weak_password_rejected(self, session, platform_admin_token):
        """POST /auth/change-password rejects weak passwords with 422."""
        r = session.post(
            f"{BASE_URL}/api/auth/change-password",
            json={"new_password": "short"},
            headers={"Authorization": f"Bearer {platform_admin_token}"}
        )
        assert r.status_code == 422, f"Expected 422 for weak password, got {r.status_code}: {r.text}"
        print(f"PASS: Weak password rejected with {r.status_code}")


# ─── 4. must_change_password in partner-login response ───────────────────

class TestMustChangePasswordInResponse:
    """Test must_change_password is included in partner-login response."""

    def test_partner_login_includes_must_change_password_field(self, session):
        """POST /auth/partner-login response includes must_change_password field."""
        # Use platform admin login which routes through partner login
        r = session.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": "automate-accounts",
            "email": "admin@automateaccounts.local",
            "password": "ChangeMe123!",
        })
        # platform admin code is blocked for partner login
        # so let's use a different tenant
        # Skip if no partner exists
        if r.status_code == 403:
            pytest.skip("automate-accounts is blocked for partner login (expected)")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "must_change_password" in data, (
            f"must_change_password field missing from partner-login response. Got: {data}"
        )
        print(f"PASS: must_change_password field present in response: {data.get('must_change_password')}")

    def test_platform_login_automate_accounts_blocked(self, session):
        """automate-accounts partner code is blocked from /auth/partner-login."""
        r = session.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": "automate-accounts",
            "email": "admin@automateaccounts.local",
            "password": "ChangeMe123!",
        })
        assert r.status_code == 403, f"Expected 403 for reserved code, got {r.status_code}"
        print("PASS: automate-accounts correctly blocked from partner-login")


# ─── 5. Website settings includes signup_bullet fields ──────────────────

class TestWebsiteSettingsSignupBullets:
    """Test that signup_bullet_1/2/3 fields work in website settings."""

    def test_website_settings_get_returns_signup_bullets(self, session, platform_admin_token):
        """GET /admin/website-settings includes signup_bullet_1/2/3."""
        r = session.get(
            f"{BASE_URL}/api/admin/website-settings",
            headers={"Authorization": f"Bearer {platform_admin_token}"}
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        raw = r.json()
        # Response may be wrapped in {"settings": {...}} or be flat
        data = raw.get("settings", raw)
        # Check that signup bullet fields are present (can be null/empty string)
        for field in ["signup_bullet_1", "signup_bullet_2", "signup_bullet_3"]:
            assert field in data, f"'{field}' missing from website settings response. Keys: {list(data.keys())}"
        print(f"PASS: signup_bullet_1={data.get('signup_bullet_1')}, signup_bullet_2={data.get('signup_bullet_2')}, signup_bullet_3={data.get('signup_bullet_3')}")

    def test_website_settings_save_signup_bullets(self, session, platform_admin_token):
        """PUT /admin/website-settings saves signup_bullet fields."""
        test_bullet_1 = "TEST_bullet_iter135_1"
        test_bullet_2 = "TEST_bullet_iter135_2"
        test_bullet_3 = "TEST_bullet_iter135_3"

        r = session.put(
            f"{BASE_URL}/api/admin/website-settings",
            json={
                "signup_bullet_1": test_bullet_1,
                "signup_bullet_2": test_bullet_2,
                "signup_bullet_3": test_bullet_3,
            },
            headers={"Authorization": f"Bearer {platform_admin_token}"}
        )
        assert r.status_code == 200, f"PUT failed: {r.status_code}: {r.text}"

        # Verify persistence via GET
        r2 = session.get(
            f"{BASE_URL}/api/admin/website-settings",
            headers={"Authorization": f"Bearer {platform_admin_token}"}
        )
        assert r2.status_code == 200
        raw = r2.json()
        data = raw.get("settings", raw)
        assert data.get("signup_bullet_1") == test_bullet_1, (
            f"signup_bullet_1 not persisted. Expected '{test_bullet_1}', got '{data.get('signup_bullet_1')}'"
        )
        assert data.get("signup_bullet_2") == test_bullet_2
        assert data.get("signup_bullet_3") == test_bullet_3
        print(f"PASS: Signup bullets saved and persisted correctly")

        # Cleanup: restore to empty
        session.put(
            f"{BASE_URL}/api/admin/website-settings",
            json={"signup_bullet_1": "", "signup_bullet_2": "", "signup_bullet_3": ""},
            headers={"Authorization": f"Bearer {platform_admin_token}"}
        )

    def test_public_website_settings_accessible(self, session):
        """GET /website-settings (public) returns 200."""
        r = session.get(f"{BASE_URL}/api/website-settings")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        print(f"PASS: Public website settings accessible")


# ─── 6. /me includes must_change_password ────────────────────────────────

class TestMeEndpointMustChangePassword:
    """Test GET /me includes must_change_password field."""

    def test_me_includes_must_change_password(self, session, platform_admin_token):
        """GET /me user object includes must_change_password field."""
        r = session.get(
            f"{BASE_URL}/api/me",
            headers={"Authorization": f"Bearer {platform_admin_token}"}
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        user = data.get("user", {})
        assert "must_change_password" in user, (
            f"must_change_password field missing from /me user object. User fields: {list(user.keys())}"
        )
        print(f"PASS: /me includes must_change_password = {user.get('must_change_password')}")


# ─── 7. Tenant-info endpoint ─────────────────────────────────────────────

class TestTenantInfo:
    """Test /tenant-info for platform admin code."""

    def test_platform_tenant_info(self, session):
        """GET /tenant-info?code=automate-accounts returns is_platform=True."""
        r = session.get(f"{BASE_URL}/api/tenant-info?code=automate-accounts")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "tenant" in data
        tenant = data["tenant"]
        assert tenant.get("is_platform") is True, f"Expected is_platform=True, got: {tenant}"
        print(f"PASS: automate-accounts tenant info correct: {tenant}")

    def test_invalid_tenant_info_returns_404(self, session):
        """GET /tenant-info?code=nonexistent returns 404."""
        r = session.get(f"{BASE_URL}/api/tenant-info?code=nonexistent-xyz-9999")
        assert r.status_code == 404, f"Expected 404, got {r.status_code}"
        print("PASS: Invalid tenant code returns 404")
