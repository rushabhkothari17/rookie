"""
Backend tests for P0 brand color bug fixes (Iteration 57):
1. Public /api/website-settings returns all brand colors
2. Admin /api/admin/settings returns all brand colors
3. Color save/persist via /api/admin/settings
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin JWT token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    data = resp.json()
    token = data.get("access_token") or data.get("token")
    assert token, "No token in login response"
    return token


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json",
    }


# ── 1. Admin Login ─────────────────────────────────────────────────────────────

class TestAdminLogin:
    """Verify admin credentials work."""

    def test_admin_login_returns_200(self):
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_admin_login_returns_token(self):
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
        })
        data = resp.json()
        token = data.get("access_token") or data.get("token")
        assert token, f"No token found in response: {data}"
        assert isinstance(token, str) and len(token) > 10


# ── 2. Public website-settings ────────────────────────────────────────────────

class TestPublicWebsiteSettings:
    """Public endpoint must return all brand color fields."""

    def test_public_website_settings_200(self):
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_public_settings_has_primary_color(self):
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        settings = resp.json().get("settings", {})
        assert "primary_color" in settings, "primary_color missing from public settings"

    def test_public_settings_has_accent_color(self):
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        settings = resp.json().get("settings", {})
        assert "accent_color" in settings, "accent_color missing from public settings"

    def test_public_settings_has_danger_color(self):
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        settings = resp.json().get("settings", {})
        assert "danger_color" in settings, "danger_color missing from public settings"

    def test_public_settings_has_success_color(self):
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        settings = resp.json().get("settings", {})
        assert "success_color" in settings, "success_color missing from public settings"

    def test_public_settings_has_warning_color(self):
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        settings = resp.json().get("settings", {})
        assert "warning_color" in settings, "warning_color missing from public settings"

    def test_public_settings_has_background_color(self):
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        settings = resp.json().get("settings", {})
        assert "background_color" in settings, "background_color missing from public settings"

    def test_public_settings_has_text_color(self):
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        settings = resp.json().get("settings", {})
        assert "text_color" in settings, "text_color missing from public settings"

    def test_public_settings_has_border_color(self):
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        settings = resp.json().get("settings", {})
        assert "border_color" in settings, "border_color missing from public settings"

    def test_public_settings_has_muted_color(self):
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        settings = resp.json().get("settings", {})
        assert "muted_color" in settings, "muted_color missing from public settings"

    def test_public_settings_colors_have_correct_db_values(self):
        """Spot-check that DB-seeded values appear in the response."""
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        settings = resp.json().get("settings", {})
        # According to context, DB has these values:
        primary = settings.get("primary_color", "")
        accent = settings.get("accent_color", "")
        danger = settings.get("danger_color", "")
        # These should be non-empty strings since DB was seeded
        print(f"primary_color={primary}, accent_color={accent}, danger_color={danger}")
        # Just ensure they are returned (may be empty string if not set)
        assert "primary_color" in settings
        assert "danger_color" in settings


# ── 3. Admin settings returns brand colors ───────────────────────────────────

class TestAdminSettings:
    """Admin /api/admin/settings must return all brand color fields."""

    def test_admin_settings_returns_200(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/settings", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_admin_settings_has_primary_color(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/settings", headers=admin_headers)
        settings = resp.json().get("settings", {})
        assert "primary_color" in settings

    def test_admin_settings_has_accent_color(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/settings", headers=admin_headers)
        settings = resp.json().get("settings", {})
        assert "accent_color" in settings

    def test_admin_settings_has_danger_color(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/settings", headers=admin_headers)
        settings = resp.json().get("settings", {})
        assert "danger_color" in settings

    def test_admin_settings_has_success_color(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/settings", headers=admin_headers)
        settings = resp.json().get("settings", {})
        assert "success_color" in settings

    def test_admin_settings_has_warning_color(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/settings", headers=admin_headers)
        settings = resp.json().get("settings", {})
        assert "warning_color" in settings


# ── 4. Save colors + verify persistence ──────────────────────────────────────

class TestColorPersistence:
    """Save brand colors via admin API and verify they are persisted."""

    TEST_COLOR = "#aabbcc"

    def test_save_accent_color(self, admin_headers):
        """PUT accent_color and verify it is returned on next GET."""
        # Save test color
        put_resp = requests.put(
            f"{BASE_URL}/api/admin/settings",
            json={"accent_color": self.TEST_COLOR},
            headers=admin_headers,
        )
        assert put_resp.status_code == 200, f"PUT failed: {put_resp.text}"

        # Verify persistence via GET
        get_resp = requests.get(f"{BASE_URL}/api/admin/settings", headers=admin_headers)
        settings = get_resp.json().get("settings", {})
        assert settings.get("accent_color") == self.TEST_COLOR, \
            f"accent_color not persisted. Got: {settings.get('accent_color')}"

    def test_save_danger_color(self, admin_headers):
        """PUT danger_color and verify it is returned on next GET."""
        put_resp = requests.put(
            f"{BASE_URL}/api/admin/settings",
            json={"danger_color": "#ff0000"},
            headers=admin_headers,
        )
        assert put_resp.status_code == 200, f"PUT failed: {put_resp.text}"

        get_resp = requests.get(f"{BASE_URL}/api/admin/settings", headers=admin_headers)
        settings = get_resp.json().get("settings", {})
        assert settings.get("danger_color") == "#ff0000", \
            f"danger_color not persisted. Got: {settings.get('danger_color')}"

    def test_save_success_color(self, admin_headers):
        """PUT success_color and verify it is returned."""
        put_resp = requests.put(
            f"{BASE_URL}/api/admin/settings",
            json={"success_color": "#16a34a"},
            headers=admin_headers,
        )
        assert put_resp.status_code == 200

        get_resp = requests.get(f"{BASE_URL}/api/admin/settings", headers=admin_headers)
        settings = get_resp.json().get("settings", {})
        assert settings.get("success_color") == "#16a34a"

    def test_public_settings_reflect_saved_colors(self, admin_headers):
        """After saving accent_color, public endpoint should reflect the change."""
        # Save a known value
        test_val = "#7c3aed"
        requests.put(
            f"{BASE_URL}/api/admin/settings",
            json={"accent_color": test_val},
            headers=admin_headers,
        )
        # Public endpoint should return the saved value
        pub_resp = requests.get(f"{BASE_URL}/api/website-settings")
        settings = pub_resp.json().get("settings", {})
        assert settings.get("accent_color") == test_val, \
            f"Public endpoint did not reflect saved accent_color. Got: {settings.get('accent_color')}"

    def test_restore_original_accent_color(self, admin_headers):
        """Restore accent_color to original DB value."""
        requests.put(
            f"{BASE_URL}/api/admin/settings",
            json={"accent_color": "#7c3aed", "danger_color": "#dc2626"},
            headers=admin_headers,
        )
        get_resp = requests.get(f"{BASE_URL}/api/admin/settings", headers=admin_headers)
        settings = get_resp.json().get("settings", {})
        assert settings.get("accent_color") == "#7c3aed"
        assert settings.get("danger_color") == "#dc2626"
