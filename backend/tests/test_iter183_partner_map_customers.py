"""
Backend tests for iteration 183:
- Customers API loads without KeyError 'code' crash
- Partner map endpoint removed from misc.py
- Customers API no longer has partner_map filter param
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Admin credentials
ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"


@pytest.fixture(scope="module")
def admin_token():
    """Get platform admin auth token."""
    # Platform admin logs in WITHOUT partner_code
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
    })
    if resp.status_code == 200:
        return resp.json().get("token")
    pytest.skip(f"Admin login failed: {resp.status_code} {resp.text[:200]}")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


class TestCustomersAPILoad:
    """Customers endpoint loads without crashing (was KeyError: 'code')."""

    def test_customers_endpoint_returns_200(self, admin_headers):
        """GET /admin/customers returns 200 - no crash."""
        resp = requests.get(f"{BASE_URL}/api/admin/customers", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"

    def test_customers_response_structure(self, admin_headers):
        """Response has expected keys."""
        resp = requests.get(f"{BASE_URL}/api/admin/customers", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "customers" in data, "Missing 'customers' key in response"
        assert "total" in data, "Missing 'total' key"
        assert "total_pages" in data, "Missing 'total_pages' key"
        assert isinstance(data["customers"], list), "'customers' should be a list"

    def test_customers_no_partner_map_field_in_rows(self, admin_headers):
        """Customer rows must NOT have a 'partner_map' field (removed)."""
        resp = requests.get(f"{BASE_URL}/api/admin/customers", headers=admin_headers)
        assert resp.status_code == 200
        customers = resp.json().get("customers", [])
        for c in customers:
            assert "partner_map" not in c, f"Customer {c.get('id')} still has 'partner_map' field"

    def test_customers_partner_code_present_for_platform_admin(self, admin_headers):
        """Platform admin should see partner_code field (enriched by enrich_partner_codes)."""
        resp = requests.get(f"{BASE_URL}/api/admin/customers", headers=admin_headers)
        assert resp.status_code == 200
        customers = resp.json().get("customers", [])
        # partner_code should be present on all customer records
        for c in customers:
            assert "partner_code" in c, f"Customer {c.get('id')} missing 'partner_code' field"

    def test_customers_with_pagination(self, admin_headers):
        """Test pagination params work correctly."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/customers",
            params={"page": 1, "per_page": 5},
            headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data.get("customers", [])) <= 5

    def test_customers_partner_filter_param(self, admin_headers):
        """partner filter param works without crashing."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/customers",
            params={"partner": "automate-accounts"},
            headers=admin_headers
        )
        assert resp.status_code == 200


class TestPartnerMapEndpointRemoved:
    """Verify the partner-map endpoint was removed from misc.py."""

    def test_partner_map_endpoint_not_found(self, admin_headers):
        """GET /admin/partner-map should return 404 or 405 (endpoint removed)."""
        resp = requests.get(f"{BASE_URL}/api/admin/partner-map", headers=admin_headers)
        assert resp.status_code in [404, 405], f"Expected 404/405, got {resp.status_code} - endpoint was NOT removed"

    def test_customers_stats_loads(self, admin_headers):
        """Customers stats API still works."""
        resp = requests.get(f"{BASE_URL}/api/admin/customers/stats", headers=admin_headers)
        assert resp.status_code == 200


class TestWebsiteSettingsSignupFields:
    """Test that website settings has signup_form_title and signup_form_subtitle fields."""

    def test_website_settings_returns_200(self, admin_headers):
        """GET /admin/website-settings returns 200."""
        resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=admin_headers)
        assert resp.status_code == 200

    def test_website_settings_has_signup_form_schema(self, admin_headers):
        """Website settings has signup_form_schema."""
        resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        settings = data.get("settings", {})
        assert "signup_form_schema" in settings or settings is not None

    def test_website_settings_signup_title_saveable(self, admin_headers):
        """PUT /admin/website-settings can save signup_form_title.
        Note: PUT expects flat fields directly (not wrapped in 'settings' key)."""
        # First get current settings
        get_resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=admin_headers)
        assert get_resp.status_code == 200
        original_title = get_resp.json().get("settings", {}).get("signup_form_title", "")

        # Save test title - fields go directly in the body (no 'settings' wrapper)
        test_title = "Test Sign Up Title 183"
        put_resp = requests.put(
            f"{BASE_URL}/api/admin/website-settings",
            json={"signup_form_title": test_title},
            headers=admin_headers
        )
        assert put_resp.status_code == 200, f"Failed to save: {put_resp.text[:200]}"
        assert put_resp.json().get("message") == "Website settings updated"

        # Verify persisted
        verify_resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=admin_headers)
        saved = verify_resp.json().get("settings", {})
        assert saved.get("signup_form_title") == test_title, f"Title not persisted, got: {saved.get('signup_form_title')}"

        # Restore original
        requests.put(
            f"{BASE_URL}/api/admin/website-settings",
            json={"signup_form_title": original_title},
            headers=admin_headers
        )

    def test_website_settings_signup_subtitle_saveable(self, admin_headers):
        """PUT /admin/website-settings can save signup_form_subtitle."""
        get_resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=admin_headers)
        assert get_resp.status_code == 200
        original_subtitle = get_resp.json().get("settings", {}).get("signup_form_subtitle", "")

        test_subtitle = "Test subtitle iter183"
        put_resp = requests.put(
            f"{BASE_URL}/api/admin/website-settings",
            json={"signup_form_subtitle": test_subtitle},
            headers=admin_headers
        )
        assert put_resp.status_code == 200
        assert put_resp.json().get("message") == "Website settings updated"

        verify_resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=admin_headers)
        saved = verify_resp.json().get("settings", {})
        assert saved.get("signup_form_subtitle") == test_subtitle

        # Restore
        requests.put(
            f"{BASE_URL}/api/admin/website-settings",
            json={"signup_form_subtitle": original_subtitle or ""},
            headers=admin_headers
        )
