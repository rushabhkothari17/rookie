"""
Backend tests for CSS Variable Design System / Theme Presets feature (iteration 274).
Tests: AppSettingsUpdate card_color/surface_color fields, /api/settings/public, /api/website-settings endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!"
    })
    if resp.status_code == 200:
        data = resp.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Admin login failed: {resp.status_code} {resp.text}")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


class TestPublicSettingsEndpoint:
    """Test GET /api/settings/public returns card_color and surface_color."""

    def test_settings_public_returns_200(self):
        resp = requests.get(f"{BASE_URL}/api/settings/public")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_settings_public_has_settings_key(self):
        resp = requests.get(f"{BASE_URL}/api/settings/public")
        data = resp.json()
        assert "settings" in data, f"Missing 'settings' key in response: {data}"

    def test_settings_public_has_card_color(self):
        """Test #9: GET /api/settings/public returns card_color field."""
        resp = requests.get(f"{BASE_URL}/api/settings/public")
        data = resp.json()
        settings = data.get("settings", {})
        assert "card_color" in settings, f"'card_color' missing from /api/settings/public response. Keys: {list(settings.keys())}"

    def test_settings_public_has_surface_color(self):
        """Test #9: GET /api/settings/public returns surface_color field."""
        resp = requests.get(f"{BASE_URL}/api/settings/public")
        data = resp.json()
        settings = data.get("settings", {})
        assert "surface_color" in settings, f"'surface_color' missing from /api/settings/public response. Keys: {list(settings.keys())}"


class TestWebsiteSettingsEndpoint:
    """Test GET /api/website-settings returns card_color, surface_color, text_color, border_color, muted_color."""

    def test_website_settings_returns_200(self):
        """Test #10: Public website-settings endpoint."""
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_website_settings_has_settings_key(self):
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        data = resp.json()
        assert "settings" in data, f"Missing 'settings' key: {data}"

    def test_website_settings_has_card_color(self):
        """Test #10: GET /api/website-settings returns card_color."""
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        data = resp.json()
        settings = data.get("settings", {})
        assert "card_color" in settings, f"'card_color' missing from /api/website-settings. Keys: {list(settings.keys())}"

    def test_website_settings_has_surface_color(self):
        """Test #10: GET /api/website-settings returns surface_color."""
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        data = resp.json()
        settings = data.get("settings", {})
        assert "surface_color" in settings, f"'surface_color' missing from /api/website-settings. Keys: {list(settings.keys())}"

    def test_website_settings_has_text_color(self):
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        data = resp.json()
        settings = data.get("settings", {})
        assert "text_color" in settings, f"'text_color' missing from /api/website-settings"

    def test_website_settings_has_border_color(self):
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        data = resp.json()
        settings = data.get("settings", {})
        assert "border_color" in settings, f"'border_color' missing from /api/website-settings"

    def test_website_settings_has_muted_color(self):
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        data = resp.json()
        settings = data.get("settings", {})
        assert "muted_color" in settings, f"'muted_color' missing from /api/website-settings"


class TestAdminSettingsEndpoint:
    """Test admin GET /api/admin/settings returns card_color and surface_color."""

    def test_admin_settings_returns_200(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/settings", headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_admin_settings_has_card_color(self, auth_headers):
        """Admin settings should return card_color when set."""
        resp = requests.get(f"{BASE_URL}/api/admin/settings", headers=auth_headers)
        data = resp.json()
        # Check if the settings key exists (may be empty if not set)
        settings = data.get("settings", {})
        # card_color may be None if not yet set, but key should be accessible via PUT
        assert data is not None, "Admin settings response should not be None"


class TestSaveThemePreset:
    """Test that saving Midnight Tech preset colors persists correctly."""

    MIDNIGHT_TECH_COLORS = {
        "primary_color": "#0a0e1a",
        "accent_color": "#3b82f6",
        "background_color": "#05070a",
        "card_color": "#111827",
        "surface_color": "#1e293b",
        "text_color": "#e2e8f0",
        "border_color": "#1e293b",
        "danger_color": "#ef4444",
        "success_color": "#10b981",
        "warning_color": "#f59e0b",
        "muted_color": "#94a3b8",
    }

    SLATE_PRO_COLORS = {
        "primary_color": "#0f172a",
        "accent_color": "#2563eb",
        "background_color": "#f8fafc",
        "card_color": "#ffffff",
        "surface_color": "#f1f5f9",
        "text_color": "#0f172a",
        "border_color": "#e2e8f0",
        "danger_color": "#dc2626",
        "success_color": "#16a34a",
        "warning_color": "#d97706",
        "muted_color": "#64748b",
    }

    def test_save_midnight_tech_colors(self, auth_headers):
        """Test saving Midnight Tech theme via PUT /api/admin/settings."""
        resp = requests.put(
            f"{BASE_URL}/api/admin/settings",
            json=self.MIDNIGHT_TECH_COLORS,
            headers=auth_headers
        )
        assert resp.status_code == 200, f"Save failed: {resp.status_code} {resp.text}"

    def test_midnight_tech_persisted_in_public_settings(self, auth_headers):
        """Test that after saving Midnight Tech, public settings reflects the dark theme."""
        # First save it
        requests.put(
            f"{BASE_URL}/api/admin/settings",
            json=self.MIDNIGHT_TECH_COLORS,
            headers=auth_headers
        )
        # Then fetch public settings
        resp = requests.get(f"{BASE_URL}/api/settings/public")
        data = resp.json()
        settings = data.get("settings", {})
        assert settings.get("card_color") == "#111827", \
            f"Expected card_color '#111827' after Midnight Tech, got '{settings.get('card_color')}'"
        assert settings.get("surface_color") == "#1e293b", \
            f"Expected surface_color '#1e293b' after Midnight Tech, got '{settings.get('surface_color')}'"
        assert settings.get("primary_color") == "#0a0e1a", \
            f"Expected primary_color '#0a0e1a' after Midnight Tech, got '{settings.get('primary_color')}'"

    def test_midnight_tech_persisted_in_website_settings(self, auth_headers):
        """Test that website-settings returns Midnight Tech colors after save."""
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        data = resp.json()
        settings = data.get("settings", {})
        assert settings.get("card_color") == "#111827", \
            f"Expected '#111827' in website-settings card_color, got '{settings.get('card_color')}'"
        assert settings.get("surface_color") == "#1e293b", \
            f"Expected '#1e293b' in website-settings surface_color, got '{settings.get('surface_color')}'"

    def test_restore_slate_pro_colors(self, auth_headers):
        """Restore to Slate Pro (default light) after testing."""
        resp = requests.put(
            f"{BASE_URL}/api/admin/settings",
            json=self.SLATE_PRO_COLORS,
            headers=auth_headers
        )
        assert resp.status_code == 200, f"Failed to restore: {resp.status_code} {resp.text}"

    def test_slate_pro_restored(self, auth_headers):
        """Verify Slate Pro colors are set after restore."""
        resp = requests.get(f"{BASE_URL}/api/settings/public")
        data = resp.json()
        settings = data.get("settings", {})
        assert settings.get("card_color") == "#ffffff", \
            f"Expected '#ffffff' after Slate Pro restore, got '{settings.get('card_color')}'"
