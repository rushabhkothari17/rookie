"""Backend tests for Global Tax & Invoicing System (iteration 128).
Tests: Tax Settings, Rate Table, Override Rules, Tax Calculation, Orders Tax column.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Admin credentials
ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_token():
    """Get platform admin JWT token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    assert token, "No token in login response"
    return token


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def created_override_rule_id(admin_headers):
    """Create an override rule and return its ID. Clean up after module."""
    payload = {
        "name": "TEST_Zero-rate exports",
        "conditions": [{"field": "country", "operator": "not_equals", "value": "CA"}],
        "tax_rate": 0.0,
        "tax_name": "Zero-rated",
        "priority": 10
    }
    resp = requests.post(f"{BASE_URL}/api/admin/taxes/overrides", json=payload, headers=admin_headers)
    assert resp.status_code == 200, f"Failed to create override rule: {resp.text}"
    rule_id = resp.json()["rule"]["id"]
    yield rule_id
    # Cleanup
    requests.delete(f"{BASE_URL}/api/admin/taxes/overrides/{rule_id}", headers=admin_headers)


# ── Tax Settings ──────────────────────────────────────────────────────────────

class TestTaxSettings:
    """Tax Settings endpoint tests"""

    def test_get_tax_settings_returns_200(self, admin_headers):
        """GET /api/admin/taxes/settings returns 200 with tax_settings key."""
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/settings", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "tax_settings" in data, "Response missing 'tax_settings' key"

    def test_update_tax_settings_enable_ca_on(self, admin_headers):
        """PUT /api/admin/taxes/settings - enable tax with country=CA, state=ON."""
        payload = {"enabled": True, "country": "CA", "state": "ON"}
        resp = requests.put(f"{BASE_URL}/api/admin/taxes/settings", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("tax_settings", {}).get("enabled") is True
        assert data.get("tax_settings", {}).get("country") == "CA"
        assert data.get("tax_settings", {}).get("state") == "ON"

    def test_tax_settings_persist_after_update(self, admin_headers):
        """Verify settings are actually persisted by doing GET after PUT."""
        # First set known values
        payload = {"enabled": True, "country": "CA", "state": "ON"}
        requests.put(f"{BASE_URL}/api/admin/taxes/settings", json=payload, headers=admin_headers)
        # Then verify
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/settings", headers=admin_headers)
        assert resp.status_code == 200
        settings = resp.json()["tax_settings"]
        assert settings.get("enabled") is True
        assert settings.get("country") == "CA"


# ── Tax Rate Table ─────────────────────────────────────────────────────────────

class TestTaxRateTable:
    """Tax rate table endpoint tests"""

    def test_get_tax_tables_returns_all(self, admin_headers):
        """GET /api/admin/taxes/tables returns all entries (no filter)."""
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/tables", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "entries" in data, "Missing 'entries' key"
        entries = data["entries"]
        assert len(entries) > 0, "No entries returned"

    def test_get_ca_tax_tables_returns_13_entries(self, admin_headers):
        """GET /api/admin/taxes/tables?country_code=CA should return exactly 13 Canadian provinces."""
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/tables?country_code=CA", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        entries = data.get("entries", [])
        assert len(entries) == 13, f"Expected 13 CA entries, got {len(entries)}"
        # Verify all are CA
        for entry in entries:
            assert entry["country_code"] == "CA"

    def test_ca_entries_have_required_fields(self, admin_headers):
        """CA entries should have country_code, state_code, state_name, rate, label."""
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/tables?country_code=CA", headers=admin_headers)
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        for entry in entries:
            assert "country_code" in entry
            assert "state_code" in entry
            assert "state_name" in entry
            assert "rate" in entry
            assert "label" in entry
            assert isinstance(entry["rate"], float)

    def test_ca_on_province_has_hst_13_percent(self, admin_headers):
        """Ontario (ON) should have 13% HST."""
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/tables?country_code=CA", headers=admin_headers)
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        on_entry = next((e for e in entries if e["state_code"] == "ON"), None)
        assert on_entry is not None, "Ontario (ON) not found in CA entries"
        assert abs(on_entry["rate"] - 0.13) < 0.001, f"Expected 13% HST for ON, got {on_entry['rate']}"
        assert "HST" in on_entry["label"]

    def test_update_tax_table_entry(self, admin_headers):
        """PUT /api/admin/taxes/tables/{country_code}/{state_code} updates the rate."""
        # Get current ON rate first
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/tables?country_code=CA", headers=admin_headers)
        entries = resp.json()["entries"]
        on_entry = next((e for e in entries if e["state_code"] == "ON"), None)
        assert on_entry is not None

        # Update it (minor tweak to test, restore it back)
        update_resp = requests.put(
            f"{BASE_URL}/api/admin/taxes/tables/CA/ON",
            json={"rate": 0.13, "label": "HST"},
            headers=admin_headers
        )
        assert update_resp.status_code == 200, f"Update failed: {update_resp.text}"
        assert "updated" in update_resp.json().get("message", "").lower()

    def test_unauthenticated_tax_tables_returns_401(self):
        """Tax tables endpoint requires auth."""
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/tables")
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"


# ── Override Rules ─────────────────────────────────────────────────────────────

class TestOverrideRules:
    """Tax override rules CRUD tests"""

    def test_get_overrides_returns_rules_array(self, admin_headers):
        """GET /api/admin/taxes/overrides returns rules array."""
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/overrides", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "rules" in data, "Missing 'rules' key"
        assert isinstance(data["rules"], list), "Rules should be a list"

    def test_create_override_rule_succeeds(self, admin_headers):
        """POST /api/admin/taxes/overrides creates a new override rule."""
        payload = {
            "name": "TEST_Zero-rate exports inline",
            "conditions": [{"field": "country", "operator": "not_equals", "value": "CA"}],
            "tax_rate": 0.0,
            "tax_name": "Zero-rated",
            "priority": 10
        }
        resp = requests.post(f"{BASE_URL}/api/admin/taxes/overrides", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Create override rule failed: {resp.text}"
        data = resp.json()
        assert "rule" in data
        rule = data["rule"]
        assert rule["name"] == "TEST_Zero-rate exports inline"
        assert rule["tax_name"] == "Zero-rated"
        assert rule["priority"] == 10
        assert "id" in rule
        # Store for cleanup
        rule_id = rule["id"]
        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/taxes/overrides/{rule_id}", headers=admin_headers)

    def test_override_rule_appears_in_list(self, admin_headers, created_override_rule_id):
        """After creating, rule should appear in GET list."""
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/overrides", headers=admin_headers)
        assert resp.status_code == 200
        rules = resp.json()["rules"]
        rule_ids = [r["id"] for r in rules]
        assert created_override_rule_id in rule_ids, f"Created rule {created_override_rule_id} not found in list"

    def test_update_override_rule(self, admin_headers, created_override_rule_id):
        """PUT /api/admin/taxes/overrides/{rule_id} updates the rule."""
        update_payload = {
            "name": "TEST_Zero-rate exports UPDATED",
            "conditions": [{"field": "country", "operator": "not_equals", "value": "CA"}],
            "tax_rate": 0.0,
            "tax_name": "Zero-rated",
            "priority": 15
        }
        resp = requests.put(
            f"{BASE_URL}/api/admin/taxes/overrides/{created_override_rule_id}",
            json=update_payload,
            headers=admin_headers
        )
        assert resp.status_code == 200, f"Update failed: {resp.text}"

    def test_delete_override_rule(self, admin_headers):
        """DELETE /api/admin/taxes/overrides/{rule_id} removes the rule."""
        # Create a rule to delete
        payload = {
            "name": "TEST_Rule to delete",
            "conditions": [],
            "tax_rate": 0.05,
            "tax_name": "Test Tax",
            "priority": 1
        }
        create_resp = requests.post(f"{BASE_URL}/api/admin/taxes/overrides", json=payload, headers=admin_headers)
        assert create_resp.status_code == 200
        rule_id = create_resp.json()["rule"]["id"]

        # Delete it
        del_resp = requests.delete(f"{BASE_URL}/api/admin/taxes/overrides/{rule_id}", headers=admin_headers)
        assert del_resp.status_code == 200, f"Delete failed: {del_resp.text}"

        # Verify it's gone
        list_resp = requests.get(f"{BASE_URL}/api/admin/taxes/overrides", headers=admin_headers)
        rules = list_resp.json()["rules"]
        assert rule_id not in [r["id"] for r in rules], "Deleted rule still in list"

    def test_delete_nonexistent_rule_returns_404(self, admin_headers):
        """DELETE with non-existent ID should return 404."""
        resp = requests.delete(
            f"{BASE_URL}/api/admin/taxes/overrides/nonexistent-id-12345",
            headers=admin_headers
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"


# ── Calculate Tax (unauthenticated) ───────────────────────────────────────────

class TestCalculateTax:
    """Tax calculation endpoint tests"""

    def test_calculate_tax_without_auth_returns_401(self):
        """POST /api/checkout/calculate-tax without auth should return 401."""
        resp = requests.post(f"{BASE_URL}/api/checkout/calculate-tax", json={"subtotal": 100.0})
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"

    def test_calculate_tax_invalid_token_returns_401(self):
        """POST /api/checkout/calculate-tax with invalid token returns 401."""
        headers = {"Authorization": "Bearer invalid.token.here", "Content-Type": "application/json"}
        resp = requests.post(
            f"{BASE_URL}/api/checkout/calculate-tax",
            json={"subtotal": 100.0},
            headers=headers
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"


# ── Customer Tax-Exempt Toggle ────────────────────────────────────────────────

class TestCustomerTaxExempt:
    """Customer tax-exempt PATCH endpoint tests"""

    def test_tax_exempt_requires_auth(self):
        """PATCH /api/admin/customers/{id}/tax-exempt without auth returns 401."""
        resp = requests.patch(
            f"{BASE_URL}/api/admin/customers/some-id/tax-exempt",
            json={"tax_exempt": True}
        )
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"

    def test_tax_exempt_nonexistent_customer_returns_404(self, admin_headers):
        """PATCH with non-existent customer ID returns 404."""
        resp = requests.patch(
            f"{BASE_URL}/api/admin/customers/nonexistent-customer-id-12345/tax-exempt",
            json={"tax_exempt": True},
            headers=admin_headers
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"


# ── Health / Router registration check ────────────────────────────────────────

class TestTaxRouterRegistration:
    """Verify tax routes are registered in the app."""

    def test_tax_settings_route_exists(self, admin_headers):
        """Tax settings route exists and is accessible."""
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/settings", headers=admin_headers)
        assert resp.status_code != 404, "Tax settings route not found (404)"

    def test_tax_tables_route_exists(self, admin_headers):
        """Tax tables route exists and is accessible."""
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/tables", headers=admin_headers)
        assert resp.status_code != 404, "Tax tables route not found (404)"

    def test_tax_overrides_route_exists(self, admin_headers):
        """Tax overrides route exists and is accessible."""
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/overrides", headers=admin_headers)
        assert resp.status_code != 404, "Tax overrides route not found (404)"
