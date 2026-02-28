"""
Tests for Partner Licensing System (Iteration 146)
Coverage:
- License endpoints (get, update, null limits, reset)
- Notes endpoints (list, create, delete)
- Partner usage endpoint
- License enforcement (403 on limit exceeded)
- Auth enforcement (platform admin only for license/notes)
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

TEST_TENANT_ID = "cb9c6337-4c59-4e74-a165-6f218354630d"

PLATFORM_ADMIN_EMAIL = "admin@automateaccounts.local"
PLATFORM_ADMIN_PASSWORD = "ChangeMe123!"

PARTNER_ADMIN_EMAIL = "sarah@brightaccounting.local"
PARTNER_ADMIN_PASSWORD = "ChangeMe123!"
PARTNER_CODE = "bright-accounting"


# ---------------------------------------------------------------------------
# Auth Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def platform_admin_token():
    """Login as platform admin and return token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": PLATFORM_ADMIN_EMAIL,
        "password": PLATFORM_ADMIN_PASSWORD,
    })
    assert resp.status_code == 200, f"Platform admin login failed: {resp.text}"
    data = resp.json()
    token = data.get("access_token") or data.get("token")
    assert token, f"No token in login response: {data}"
    return token


@pytest.fixture(scope="module")
def partner_admin_token():
    """Login as partner admin and return token (uses partner-login endpoint)."""
    resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
        "email": PARTNER_ADMIN_EMAIL,
        "password": PARTNER_ADMIN_PASSWORD,
        "partner_code": PARTNER_CODE,
    })
    assert resp.status_code == 200, f"Partner admin login failed: {resp.text}"
    data = resp.json()
    token = data.get("access_token") or data.get("token")
    assert token, f"No token in login response: {data}"
    return token


@pytest.fixture(scope="module")
def platform_client(platform_admin_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {platform_admin_token}"})
    return s


@pytest.fixture(scope="module")
def partner_client(partner_admin_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {partner_admin_token}"})
    return s


# ---------------------------------------------------------------------------
# 1. GET /api/admin/tenants/{tenant_id}/license
# ---------------------------------------------------------------------------

class TestGetLicense:
    """License GET endpoint tests"""

    def test_get_license_returns_200(self, platform_client):
        """Platform admin can get license snapshot"""
        resp = platform_client.get(f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_get_license_has_period(self, platform_client):
        """License snapshot contains a period field"""
        resp = platform_client.get(f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license")
        assert resp.status_code == 200
        data = resp.json()
        assert "period" in data, f"'period' missing from response: {data.keys()}"
        # period should be YYYY-MM format
        period = data["period"]
        assert period and len(period) == 7, f"Period format unexpected: {period}"
        assert period[4] == "-", f"Period format unexpected: {period}"

    def test_get_license_has_license_key(self, platform_client):
        """License snapshot contains a license dict"""
        resp = platform_client.get(f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license")
        data = resp.json()
        assert "license" in data, f"'license' missing from response"
        assert isinstance(data["license"], dict), "license should be a dict"

    def test_get_license_has_usage_key(self, platform_client):
        """License snapshot contains a usage dict"""
        resp = platform_client.get(f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license")
        data = resp.json()
        assert "usage" in data, f"'usage' missing from response"
        usage = data["usage"]
        assert isinstance(usage, dict), "usage should be a dict"
        # Verify key usage metrics are present
        expected_keys = ["users", "orders_this_month", "customers_this_month"]
        for k in expected_keys:
            assert k in usage, f"Usage key '{k}' missing from response"

    def test_get_license_usage_entry_structure(self, platform_client):
        """Each usage entry has required fields"""
        resp = platform_client.get(f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license")
        data = resp.json()
        users_usage = data["usage"].get("users", {})
        for field in ["current", "limit", "pct", "warning", "blocked"]:
            assert field in users_usage, f"Field '{field}' missing from usage.users"

    def test_get_license_platform_admin_only_403_no_auth(self):
        """Unauthenticated request returns 401 or 403"""
        resp = requests.get(f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"

    def test_get_license_partner_admin_forbidden(self, partner_client):
        """Partner admin cannot access another tenant's license — should get 403"""
        resp = partner_client.get(f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license")
        assert resp.status_code == 403, f"Expected 403 for partner admin, got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# 2. PUT /api/admin/tenants/{tenant_id}/license
# ---------------------------------------------------------------------------

class TestUpdateLicense:
    """License PUT endpoint tests"""

    def test_update_license_returns_200(self, platform_client):
        """Platform admin can update license"""
        resp = platform_client.put(
            f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license",
            json={"plan": "starter", "max_users": 50}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_update_license_response_has_license(self, platform_client):
        """Update license response contains 'license' key"""
        resp = platform_client.put(
            f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license",
            json={"plan": "growth", "max_users": 100}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "license" in data, f"'license' missing from response: {data.keys()}"

    def test_update_license_persists(self, platform_client):
        """Updated limit values persist when re-fetched"""
        # Set a specific limit
        platform_client.put(
            f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license",
            json={"plan": "TEST_plan_iter146", "max_users": 42}
        )
        # Verify it was saved
        get_resp = platform_client.get(f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license")
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["license"]["plan"] == "TEST_plan_iter146", f"Plan not persisted: {data['license'].get('plan')}"
        assert data["license"]["max_users"] == 42, f"max_users not persisted: {data['license'].get('max_users')}"

    def test_update_license_null_clears_limit(self, platform_client):
        """Sending null for a limit field sets it to unlimited"""
        # First set max_users to a value
        platform_client.put(
            f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license",
            json={"max_users": 10}
        )
        # Now clear it by sending null
        resp = platform_client.put(
            f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license",
            json={"max_users": None}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["license"]["max_users"] is None, f"max_users should be None (unlimited), got: {data['license'].get('max_users')}"

    def test_update_license_null_persists_on_get(self, platform_client):
        """Null limit persists on subsequent GET"""
        # Set null
        platform_client.put(
            f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license",
            json={"max_users": None}
        )
        # Verify
        get_resp = platform_client.get(f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license")
        data = get_resp.json()
        assert data["license"]["max_users"] is None, f"max_users should be None, got: {data['license'].get('max_users')}"


# ---------------------------------------------------------------------------
# 3. Notes Endpoints
# ---------------------------------------------------------------------------

class TestNotes:
    """Tenant notes endpoints"""
    
    _created_note_id = None

    def test_list_notes_returns_200(self, platform_client):
        """GET notes returns 200"""
        resp = platform_client.get(f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/notes")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_list_notes_has_notes_key(self, platform_client):
        """GET notes returns 'notes' list"""
        resp = platform_client.get(f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/notes")
        data = resp.json()
        assert "notes" in data, f"'notes' key missing from response: {data.keys()}"
        assert isinstance(data["notes"], list), "notes should be a list"

    def test_create_note_returns_201_or_200(self, platform_client):
        """POST note returns 200/201"""
        resp = platform_client.post(
            f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/notes",
            json={"text": "TEST_NOTE_iter146: Integration test note"}
        )
        assert resp.status_code in (200, 201), f"Expected 200/201, got {resp.status_code}: {resp.text}"

    def test_create_note_response_structure(self, platform_client):
        """Create note response has expected fields"""
        resp = platform_client.post(
            f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/notes",
            json={"text": "TEST_NOTE_iter146: Structure test"}
        )
        data = resp.json()
        assert "note" in data, f"'note' missing from response: {data.keys()}"
        note = data["note"]
        for field in ["id", "text", "created_by", "created_at"]:
            assert field in note, f"Field '{field}' missing from note: {note.keys()}"
        TestNotes._created_note_id = note["id"]

    def test_create_note_persists_in_list(self, platform_client):
        """Created note appears in list"""
        # Create a note
        create_resp = platform_client.post(
            f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/notes",
            json={"text": "TEST_NOTE_iter146: Persistence test"}
        )
        assert create_resp.status_code in (200, 201)
        note_id = create_resp.json()["note"]["id"]
        
        # Verify it appears in list
        list_resp = platform_client.get(f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/notes")
        notes = list_resp.json()["notes"]
        note_ids = [n["id"] for n in notes]
        assert note_id in note_ids, f"Created note {note_id} not found in notes list"
        
        # Cleanup
        platform_client.delete(f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/notes/{note_id}")

    def test_delete_note_returns_200(self, platform_client):
        """DELETE note returns 200"""
        # Create a note first
        create_resp = platform_client.post(
            f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/notes",
            json={"text": "TEST_NOTE_iter146: Delete test"}
        )
        note_id = create_resp.json()["note"]["id"]
        
        # Delete it
        resp = platform_client.delete(
            f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/notes/{note_id}"
        )
        assert resp.status_code in (200, 204), f"Expected 200/204, got {resp.status_code}: {resp.text}"

    def test_delete_note_removes_from_list(self, platform_client):
        """Deleted note no longer appears in list"""
        # Create
        create_resp = platform_client.post(
            f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/notes",
            json={"text": "TEST_NOTE_iter146: Remove test"}
        )
        note_id = create_resp.json()["note"]["id"]
        
        # Delete
        platform_client.delete(f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/notes/{note_id}")
        
        # Verify gone
        list_resp = platform_client.get(f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/notes")
        notes = list_resp.json()["notes"]
        note_ids = [n["id"] for n in notes]
        assert note_id not in note_ids, "Deleted note still appears in list"

    def test_delete_nonexistent_note_404(self, platform_client):
        """DELETE non-existent note returns 404"""
        resp = platform_client.delete(
            f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/notes/nonexistent-note-id"
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"

    def test_notes_require_platform_admin(self, partner_client):
        """Partner admin cannot access notes — 403"""
        resp = partner_client.get(f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/notes")
        assert resp.status_code == 403, f"Expected 403 for partner admin, got {resp.status_code}"


# ---------------------------------------------------------------------------
# 4. Partner Usage Endpoint (/api/admin/usage)
# ---------------------------------------------------------------------------

class TestPartnerUsage:
    """Partner usage endpoint tests"""

    def test_partner_usage_returns_200(self, partner_client):
        """Partner admin can access own usage"""
        resp = partner_client.get(f"{BASE_URL}/api/admin/usage")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_partner_usage_has_snapshot_fields(self, partner_client):
        """Partner usage response has period, license, usage fields"""
        resp = partner_client.get(f"{BASE_URL}/api/admin/usage")
        data = resp.json()
        for field in ["period", "license", "usage"]:
            assert field in data, f"'{field}' missing from partner usage response"

    def test_partner_usage_has_correct_structure(self, partner_client):
        """Partner usage entries have correct structure"""
        resp = partner_client.get(f"{BASE_URL}/api/admin/usage")
        data = resp.json()
        usage = data["usage"]
        assert isinstance(usage, dict), "usage should be a dict"
        # Check a specific entry
        if "users" in usage:
            entry = usage["users"]
            for field in ["current", "limit", "pct", "warning", "blocked"]:
                assert field in entry, f"Field '{field}' missing from usage.users"

    def test_platform_admin_can_also_access_usage(self, platform_client):
        """Platform admin can also access /admin/usage (it uses get_tenant_admin)"""
        resp = platform_client.get(f"{BASE_URL}/api/admin/usage")
        # Should return 200 - platform admin is a valid tenant admin
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# 5. Usage Reset Endpoint
# ---------------------------------------------------------------------------

class TestUsageReset:
    """Monthly usage reset endpoint tests"""

    def test_reset_usage_returns_200(self, platform_client):
        """Platform admin can reset usage counters"""
        resp = platform_client.post(f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/usage/reset")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_reset_usage_response_has_period(self, platform_client):
        """Reset response has period field"""
        resp = platform_client.post(f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/usage/reset")
        data = resp.json()
        assert "period" in data, f"'period' missing from reset response: {data.keys()}"
        assert "message" in data, f"'message' missing from reset response: {data.keys()}"

    def test_reset_usage_clears_counters(self, platform_client):
        """After reset, monthly counters are 0"""
        platform_client.post(f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/usage/reset")
        # Verify in license snapshot
        get_resp = platform_client.get(f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license")
        data = get_resp.json()
        orders = data["usage"].get("orders_this_month", {})
        assert orders.get("current") == 0, f"orders_this_month.current should be 0 after reset, got: {orders.get('current')}"

    def test_reset_requires_platform_admin(self, partner_client):
        """Partner admin cannot reset usage — 403"""
        resp = partner_client.post(f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/usage/reset")
        assert resp.status_code == 403, f"Expected 403 for partner admin, got {resp.status_code}"


# ---------------------------------------------------------------------------
# 6. License Enforcement (403 on limit exceeded)
# ---------------------------------------------------------------------------

class TestLicenseEnforcement:
    """License enforcement tests — 403 when limit is hit"""

    def test_user_creation_blocked_when_max_users_zero(self, platform_client, partner_client):
        """Creating a user when max_users=0 returns 403"""
        # Set max_users to 0
        set_resp = platform_client.put(
            f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license",
            json={"max_users": 0}
        )
        assert set_resp.status_code == 200, f"Failed to set limit: {set_resp.text}"
        
        # Attempt to create a user as partner admin
        create_resp = partner_client.post(
            f"{BASE_URL}/api/admin/users",
            json={
                "email": "TEST_blocked_user@brightaccounting.local",
                "full_name": "TEST Blocked User",
                "password": "TestPass123!",
                "role": "partner_staff"
            }
        )
        assert create_resp.status_code == 403, f"Expected 403 when max_users=0, got {create_resp.status_code}: {create_resp.text}"
        
        # Cleanup: Remove the limit
        platform_client.put(
            f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license",
            json={"max_users": None}
        )

    def test_license_response_after_clearing_limit(self, platform_client):
        """After clearing max_users limit, the usage entry shows limit=null"""
        # Clear the limit
        platform_client.put(
            f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license",
            json={"max_users": None}
        )
        # Verify
        get_resp = platform_client.get(f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license")
        data = get_resp.json()
        users_usage = data["usage"].get("users", {})
        assert users_usage.get("limit") is None, f"limit should be None (unlimited), got: {users_usage.get('limit')}"
        assert users_usage.get("blocked") is False, "Should not be blocked when limit is None"


# ---------------------------------------------------------------------------
# 7. Auth Enforcement
# ---------------------------------------------------------------------------

class TestAuthEnforcement:
    """Auth enforcement tests"""

    def test_license_requires_auth(self):
        """Unauthenticated request to license endpoint returns 401/403"""
        resp = requests.get(f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"

    def test_notes_requires_auth(self):
        """Unauthenticated request to notes endpoint returns 401/403"""
        resp = requests.get(f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/notes")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"

    def test_usage_reset_requires_auth(self):
        """Unauthenticated request to usage reset returns 401/403"""
        resp = requests.post(f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/usage/reset")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"

    def test_partner_admin_forbidden_from_license(self, partner_client):
        """Partner admin gets 403 when accessing any tenant's license"""
        resp = partner_client.get(f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license")
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"

    def test_partner_admin_forbidden_from_notes(self, partner_client):
        """Partner admin gets 403 when accessing any tenant's notes"""
        resp = partner_client.get(f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/notes")
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"

    def test_partner_admin_forbidden_from_usage_reset(self, partner_client):
        """Partner admin gets 403 when resetting usage"""
        resp = partner_client.post(f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/usage/reset")
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
