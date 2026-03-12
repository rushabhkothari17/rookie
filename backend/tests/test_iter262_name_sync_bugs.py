"""
Backend tests for Bug 1: PUT /api/admin/tenants/{id} name change should sync
app_settings.store_name for that tenant.

Verify:
1. Platform admin updates tenant name → tenant.name changes in list
2. After name update → store_name in GET /api/admin/tenants matches new name
3. After name update → partner admin's /api/admin/settings shows updated store_name
4. Partner admin changes store_name in their own settings → their /api/admin/settings reflects it
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
PARTNER_CODE = "test-partner-corp"
PARTNER_EMAIL = "alice@testpartner.com"
PARTNER_PASSWORD = "TestPass123!"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def platform_admin_token():
    """Login as platform admin (no partner_code)."""
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!",
    })
    assert r.status_code == 200, f"Platform admin login failed: {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def platform_admin_headers(platform_admin_token):
    return {"Authorization": f"Bearer {platform_admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def test_partner_corp_tenant_id(platform_admin_headers):
    """Get the tenant_id for test-partner-corp."""
    r = requests.get(f"{BASE_URL}/api/admin/tenants", headers=platform_admin_headers)
    assert r.status_code == 200, f"Failed to list tenants: {r.text}"
    tenants = r.json().get("tenants", [])
    partner = next(
        (t for t in tenants if t.get("code") == PARTNER_CODE),
        None,
    )
    if partner is None:
        # Fallback: pick any non-platform partner tenant
        partner = next(
            (t for t in tenants if t.get("code") and t["code"] != "automate-accounts"),
            None,
        )
    assert partner is not None, f"Could not find tenant with code '{PARTNER_CODE}'"
    return partner["id"]


@pytest.fixture(scope="module")
def partner_admin_token():
    """Login as alice@testpartner.com using partner-login endpoint."""
    r = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
        "partner_code": PARTNER_CODE,
        "email": PARTNER_EMAIL,
        "password": PARTNER_PASSWORD,
    })
    if r.status_code != 200:
        pytest.skip(f"Partner admin login failed: {r.text}")
    return r.json()["token"]


@pytest.fixture(scope="module")
def partner_admin_headers(partner_admin_token):
    return {"Authorization": f"Bearer {partner_admin_token}", "Content-Type": "application/json"}


# ── Bug 1: Platform admin name update syncs store_name ────────────────────────

class TestPlatformAdminTenantNameSyncsStoreName:
    """Bug 1: PUT /api/admin/tenants/{id} name change must update app_settings.store_name"""

    def test_get_tenant_list_returns_store_name(self, platform_admin_headers, test_partner_corp_tenant_id):
        """Prerequisite: GET /api/admin/tenants should include store_name field."""
        r = requests.get(f"{BASE_URL}/api/admin/tenants", headers=platform_admin_headers)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        tenants = r.json().get("tenants", [])
        target = next((t for t in tenants if t.get("id") == test_partner_corp_tenant_id), None)
        assert target is not None, "Target tenant not found in list"
        assert "store_name" in target, f"Tenant missing store_name field: {target}"
        print(f"✓ Tenant found: name={target.get('name')}, store_name={target.get('store_name')}")

    def test_update_tenant_name_returns_200(self, platform_admin_headers, test_partner_corp_tenant_id):
        """PUT /api/admin/tenants/{id} with name update should return 200."""
        new_name = f"Test Partner Corp UPDATED {int(time.time()) % 10000}"
        r = requests.put(
            f"{BASE_URL}/api/admin/tenants/{test_partner_corp_tenant_id}",
            headers=platform_admin_headers,
            json={"name": new_name},
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "tenant" in data
        assert data["tenant"]["name"] == new_name, f"tenant.name mismatch: {data['tenant']['name']}"
        print(f"✓ Tenant name updated to: {new_name}")

    def test_after_name_update_store_name_matches_in_list(self, platform_admin_headers, test_partner_corp_tenant_id):
        """After name update, GET /api/admin/tenants should show matching store_name."""
        # First, update the name
        unique_name = f"StoreName Sync Test {int(time.time()) % 100000}"
        put_r = requests.put(
            f"{BASE_URL}/api/admin/tenants/{test_partner_corp_tenant_id}",
            headers=platform_admin_headers,
            json={"name": unique_name},
        )
        assert put_r.status_code == 200, f"PUT failed: {put_r.text}"

        # Then verify in the list
        list_r = requests.get(f"{BASE_URL}/api/admin/tenants", headers=platform_admin_headers)
        assert list_r.status_code == 200
        tenants = list_r.json().get("tenants", [])
        target = next((t for t in tenants if t.get("id") == test_partner_corp_tenant_id), None)
        assert target is not None, "Tenant not found after update"
        assert target.get("name") == unique_name, f"tenant.name mismatch: expected {unique_name}, got {target.get('name')}"
        assert target.get("store_name") == unique_name, (
            f"BUG 1: store_name not synced! "
            f"Expected '{unique_name}', got '{target.get('store_name')}'"
        )
        print(f"✓ Bug 1 verified: store_name '{target.get('store_name')}' matches tenant.name '{target.get('name')}'")

    def test_after_name_update_partner_settings_reflects_new_store_name(
        self, platform_admin_headers, partner_admin_headers, test_partner_corp_tenant_id
    ):
        """After platform admin updates name, partner's own /api/admin/settings should show new store_name."""
        # Set a distinctive name
        distinctive_name = f"OrganizationInfo SyncTest {int(time.time()) % 100000}"
        put_r = requests.put(
            f"{BASE_URL}/api/admin/tenants/{test_partner_corp_tenant_id}",
            headers=platform_admin_headers,
            json={"name": distinctive_name},
        )
        assert put_r.status_code == 200, f"PUT failed: {put_r.text}"

        # Partner admin fetches their own settings
        settings_r = requests.get(f"{BASE_URL}/api/admin/settings", headers=partner_admin_headers)
        assert settings_r.status_code == 200, f"Partner settings fetch failed: {settings_r.text}"
        settings = settings_r.json().get("settings", {})
        actual_store_name = settings.get("store_name", "")
        assert actual_store_name == distinctive_name, (
            f"BUG 1: Partner's app_settings.store_name not synced after platform admin name update! "
            f"Expected '{distinctive_name}', got '{actual_store_name}'"
        )
        print(f"✓ Bug 1 end-to-end: partner's store_name='{actual_store_name}' matches platform admin set name='{distinctive_name}'")

    def test_name_and_store_name_are_consistent_after_multiple_updates(
        self, platform_admin_headers, test_partner_corp_tenant_id
    ):
        """Multiple name updates should keep store_name in sync."""
        names_to_test = [
            f"MultiUpdate Test A {int(time.time()) % 1000}",
            f"MultiUpdate Test B {int(time.time()) % 1000 + 1}",
        ]
        for name in names_to_test:
            put_r = requests.put(
                f"{BASE_URL}/api/admin/tenants/{test_partner_corp_tenant_id}",
                headers=platform_admin_headers,
                json={"name": name},
            )
            assert put_r.status_code == 200, f"PUT failed for name '{name}': {put_r.text}"

        # Check final state
        list_r = requests.get(f"{BASE_URL}/api/admin/tenants", headers=platform_admin_headers)
        assert list_r.status_code == 200
        tenants = list_r.json().get("tenants", [])
        target = next((t for t in tenants if t.get("id") == test_partner_corp_tenant_id), None)
        assert target is not None
        assert target.get("store_name") == names_to_test[-1], (
            f"store_name not updated to last value: expected '{names_to_test[-1]}', got '{target.get('store_name')}'"
        )
        print(f"✓ Multiple updates: store_name correctly shows '{target.get('store_name')}'")


# ── Bug 2: Partner admin store_name save - settings endpoint works ─────────────

class TestPartnerAdminStoreNameSave:
    """Bug 2 (backend side): Partner admin PUT /api/admin/settings with store_name should persist."""

    def test_partner_admin_can_get_settings(self, partner_admin_headers):
        """Partner admin can fetch their own settings."""
        r = requests.get(f"{BASE_URL}/api/admin/settings", headers=partner_admin_headers)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "settings" in data
        print(f"✓ Partner admin settings fetched: store_name='{data['settings'].get('store_name', '')}'")

    def test_partner_admin_can_update_store_name(self, partner_admin_headers):
        """Partner admin PUT /api/admin/settings updates store_name successfully."""
        new_store_name = f"Partner Store {int(time.time()) % 10000}"
        r = requests.put(
            f"{BASE_URL}/api/admin/settings",
            headers=partner_admin_headers,
            json={"store_name": new_store_name},
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        print(f"✓ Partner store_name update returned 200 for '{new_store_name}'")

    def test_partner_store_name_persists_after_save(self, partner_admin_headers):
        """After PUT, GET should return the updated store_name."""
        unique_name = f"Partner Test Store {int(time.time()) % 100000}"
        # Save
        put_r = requests.put(
            f"{BASE_URL}/api/admin/settings",
            headers=partner_admin_headers,
            json={"store_name": unique_name},
        )
        assert put_r.status_code == 200, f"PUT failed: {put_r.text}"

        # Verify
        get_r = requests.get(f"{BASE_URL}/api/admin/settings", headers=partner_admin_headers)
        assert get_r.status_code == 200
        saved = get_r.json().get("settings", {}).get("store_name", "")
        assert saved == unique_name, f"store_name not persisted: expected '{unique_name}', got '{saved}'"
        print(f"✓ Partner store_name persisted correctly: '{saved}'")

    def test_partner_admin_single_save_updates_settings(self, partner_admin_headers):
        """Verify a single call to /api/admin/settings is sufficient to save store_name (Bug 2 backend check)."""
        test_name = f"SingleSave Test {int(time.time()) % 10000}"
        # ONE single save call
        r = requests.put(
            f"{BASE_URL}/api/admin/settings",
            headers=partner_admin_headers,
            json={"store_name": test_name},
        )
        assert r.status_code == 200, f"Single save failed: {r.text}"

        # Immediately verify it was saved
        get_r = requests.get(f"{BASE_URL}/api/admin/settings", headers=partner_admin_headers)
        assert get_r.status_code == 200
        saved = get_r.json().get("settings", {}).get("store_name", "")
        assert saved == test_name, (
            f"BUG 2 (backend): Single save NOT sufficient! "
            f"Expected '{test_name}', got '{saved}'"
        )
        print(f"✓ Bug 2 (backend): Single save sufficient — store_name='{saved}'")


# ── Verify status-only update doesn't break store_name ────────────────────────

class TestTenantStatusUpdateDoesNotBreakStoreName:
    """Updating tenant status only should not change store_name."""

    def test_status_update_preserves_store_name(self, platform_admin_headers, test_partner_corp_tenant_id):
        """Setting name first, then updating status — store_name should stay."""
        # First set a known name
        known_name = f"StatusTest Name {int(time.time()) % 10000}"
        put_r = requests.put(
            f"{BASE_URL}/api/admin/tenants/{test_partner_corp_tenant_id}",
            headers=platform_admin_headers,
            json={"name": known_name},
        )
        assert put_r.status_code == 200

        # Now update only status
        status_r = requests.put(
            f"{BASE_URL}/api/admin/tenants/{test_partner_corp_tenant_id}",
            headers=platform_admin_headers,
            json={"status": "active"},
        )
        assert status_r.status_code == 200

        # store_name in list should still match known_name
        list_r = requests.get(f"{BASE_URL}/api/admin/tenants", headers=platform_admin_headers)
        tenants = list_r.json().get("tenants", [])
        target = next((t for t in tenants if t.get("id") == test_partner_corp_tenant_id), None)
        assert target is not None
        assert target.get("store_name") == known_name, (
            f"Status update changed store_name! "
            f"Expected '{known_name}', got '{target.get('store_name')}'"
        )
        print(f"✓ Status-only update preserved store_name: '{target.get('store_name')}'")
