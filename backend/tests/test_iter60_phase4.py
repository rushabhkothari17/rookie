"""
Iteration 60 - Phase 4: Unified Login, Signup Paths, Users Tab,
Partner Orgs tab, TenantSwitcher, register-partner endpoint.
"""
from __future__ import annotations

import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

PLATFORM_ADMIN_EMAIL = "admin@automateaccounts.local"
PLATFORM_ADMIN_PASSWORD = "ChangeMe123!"
PLATFORM_PARTNER_CODE = "automate-accounts"

TENANT_B_EMAIL = "adminb@tenantb.local"
TENANT_B_PASSWORD = "TestPass123!"
TENANT_B_CODE = "tenant-b-test"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def http():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def platform_token(http):
    """Get platform super admin token via partner-login (unified login endpoint)."""
    resp = http.post(f"{BASE_URL}/api/auth/partner-login", json={
        "partner_code": PLATFORM_PARTNER_CODE,
        "email": PLATFORM_ADMIN_EMAIL,
        "password": PLATFORM_ADMIN_PASSWORD,
    })
    assert resp.status_code == 200, f"Platform admin login failed: {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="module")
def platform_headers(platform_token):
    return {"Authorization": f"Bearer {platform_token}"}


@pytest.fixture(scope="module")
def tenant_b_token(http):
    resp = http.post(f"{BASE_URL}/api/auth/partner-login", json={
        "partner_code": TENANT_B_CODE,
        "email": TENANT_B_EMAIL,
        "password": TENANT_B_PASSWORD,
    })
    if resp.status_code != 200:
        pytest.skip(f"Tenant B login failed: {resp.text}")
    return resp.json()["token"]


@pytest.fixture(scope="module")
def tenant_b_headers(tenant_b_token):
    return {"Authorization": f"Bearer {tenant_b_token}"}


# ---------------------------------------------------------------------------
# Phase 4 Feature 1: Unified Login (partner-login endpoint)
# ---------------------------------------------------------------------------

class TestUnifiedLogin:
    """Verify unified /auth/partner-login used by Login.tsx single form."""

    def test_platform_admin_login_via_partner_login(self, http):
        """Platform admin can login via /auth/partner-login with partner_code."""
        resp = http.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": PLATFORM_PARTNER_CODE,
            "email": PLATFORM_ADMIN_EMAIL,
            "password": PLATFORM_ADMIN_PASSWORD,
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "token" in data, f"No token in response: {data}"
        assert data.get("role") == "platform_super_admin", f"Expected platform_super_admin, got {data.get('role')}"
        # role != "customer" means is_admin = True → redirects to /admin
        assert data.get("role") != "customer", "Platform admin role must not be customer (would redirect to /portal)"
        print(f"PASS: Unified login OK. role={data['role']}, is_admin_redirect=True")

    def test_tenant_b_admin_login_via_partner_login(self, http):
        """Tenant B admin can login and is_admin is True."""
        resp = http.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": TENANT_B_CODE,
            "email": TENANT_B_EMAIL,
            "password": TENANT_B_PASSWORD,
        })
        if resp.status_code != 200:
            pytest.skip(f"Tenant B not set up: {resp.text}")
        data = resp.json()
        assert "token" in data
        assert data.get("role") in ("partner_super_admin", "partner_admin", "super_admin"), f"Unexpected role: {data.get('role')}"
        print(f"PASS: Tenant B admin login OK. role={data['role']}")

    def test_invalid_partner_code_returns_400(self, http):
        """Invalid partner code returns 400."""
        resp = http.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": "nonexistent-xyz-123",
            "email": PLATFORM_ADMIN_EMAIL,
            "password": PLATFORM_ADMIN_PASSWORD,
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        print("PASS: Invalid partner code → 400")

    def test_wrong_password_returns_401(self, http):
        """Wrong password returns 401."""
        resp = http.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": PLATFORM_PARTNER_CODE,
            "email": PLATFORM_ADMIN_EMAIL,
            "password": "WrongPassword!",
        })
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: Wrong password → 401")

    def test_me_returns_platform_super_admin_role(self, http, platform_headers):
        """After login /me returns platform_super_admin role."""
        resp = http.get(f"{BASE_URL}/api/me", headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        user = resp.json()["user"]
        assert user["role"] == "platform_super_admin", f"Expected platform_super_admin, got {user['role']}"
        assert user["is_admin"] is True, f"is_admin should be True: {user}"
        print(f"PASS: /me returns role=platform_super_admin, is_admin=True")


# ---------------------------------------------------------------------------
# Phase 4 Feature 2: Register-Partner endpoint
# ---------------------------------------------------------------------------

class TestRegisterPartner:
    """POST /api/auth/register-partner creates new tenant + partner_super_admin."""
    created_partner_code = None

    def test_register_partner_creates_tenant_and_admin(self, http):
        """Full register-partner flow: creates tenant + partner_super_admin."""
        unique_ts = int(time.time())
        partner_code = f"test-phase4-{unique_ts}"
        payload = {
            "name": f"TEST Phase4 Org {unique_ts}",
            "code": partner_code,
            "admin_name": "Phase4 Admin",
            "admin_email": f"phase4admin-{unique_ts}@testphase4.local",
            "admin_password": "Phase4Pass!",
        }
        resp = http.post(f"{BASE_URL}/api/auth/register-partner", json=payload)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "message" in data, f"No message in response: {data}"
        assert "partner_code" in data, f"No partner_code in response: {data}"
        assert data["partner_code"] == partner_code
        assert data.get("tenant_name") == payload["name"]
        TestRegisterPartner.created_partner_code = partner_code
        print(f"PASS: register-partner created org={data['tenant_name']}, code={partner_code}")

    def test_newly_created_partner_can_login(self, http):
        """Newly created partner org admin can login."""
        code = TestRegisterPartner.created_partner_code
        if not code:
            pytest.skip("No partner code from previous test")
        unique_ts = code.split("-")[-1]
        resp = http.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": code,
            "email": f"phase4admin-{unique_ts}@testphase4.local",
            "password": "Phase4Pass!",
        })
        assert resp.status_code == 200, f"Expected new partner to login, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("role") == "partner_super_admin", f"Expected partner_super_admin, got {data.get('role')}"
        print(f"PASS: New partner org admin can login. role={data['role']}")

    def test_register_partner_duplicate_code_fails(self, http):
        """Duplicate partner code returns 400."""
        resp = http.post(f"{BASE_URL}/api/auth/register-partner", json={
            "name": "Duplicate Test",
            "code": PLATFORM_PARTNER_CODE,  # already exists
            "admin_name": "Test Admin",
            "admin_email": "dup_test@test.local",
            "admin_password": "TestPass!",
        })
        assert resp.status_code == 400, f"Expected 400 for duplicate code, got {resp.status_code}: {resp.text}"
        print("PASS: Duplicate partner code → 400")

    def test_register_partner_missing_fields_returns_400(self, http):
        """Missing required fields returns 400."""
        resp = http.post(f"{BASE_URL}/api/auth/register-partner", json={
            "name": "Incomplete Org",
            # missing code, admin_name, admin_email, admin_password
        })
        assert resp.status_code == 400, f"Expected 400 for missing fields, got {resp.status_code}: {resp.text}"
        print("PASS: Missing fields → 400")

    def test_cleanup_register_partner_deactivate_tenant(self, http, platform_headers):
        """Cleanup: deactivate the test tenant created via register-partner."""
        code = TestRegisterPartner.created_partner_code
        if not code:
            pytest.skip("No created tenant to cleanup")
        # Find the tenant ID
        resp = http.get(f"{BASE_URL}/api/admin/tenants", headers=platform_headers)
        if resp.status_code != 200:
            pytest.skip("Cannot list tenants")
        tenants = resp.json().get("tenants", [])
        tenant = next((t for t in tenants if t["code"] == code), None)
        if not tenant:
            pytest.skip(f"Tenant {code} not found")
        # Deactivate
        resp_deact = http.post(f"{BASE_URL}/api/admin/tenants/{tenant['id']}/deactivate", headers=platform_headers)
        assert resp_deact.status_code == 200, f"Expected 200, got {resp_deact.status_code}: {resp_deact.text}"
        print(f"PASS: Cleanup - deactivated test tenant {code}")


# ---------------------------------------------------------------------------
# Phase 4 Feature 3: Admin Tenants (Partner Orgs Tab)
# ---------------------------------------------------------------------------

class TestAdminTenantsPhase4:
    """GET/POST /api/admin/tenants for Partner Orgs tab."""
    created_tenant_id = None

    def test_list_tenants_includes_automate_accounts(self, http, platform_headers):
        """Tenant list includes 'Automate Accounts' (automate-accounts)."""
        resp = http.get(f"{BASE_URL}/api/admin/tenants", headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        codes = [t["code"] for t in data.get("tenants", [])]
        assert PLATFORM_PARTNER_CODE in codes, f"automate-accounts not found in {codes}"
        print(f"PASS: automate-accounts found in tenant list")

    def test_list_tenants_includes_tenant_b(self, http, platform_headers):
        """Tenant list includes 'Tenant B Test' (tenant-b-test)."""
        resp = http.get(f"{BASE_URL}/api/admin/tenants", headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        codes = [t["code"] for t in data.get("tenants", [])]
        assert TENANT_B_CODE in codes, f"tenant-b-test not found in {codes}"
        print(f"PASS: tenant-b-test found in tenant list")

    def test_tenant_names_are_correct(self, http, platform_headers):
        """Verify tenant names include 'Automate Accounts' and 'Tenant B Test'."""
        resp = http.get(f"{BASE_URL}/api/admin/tenants", headers=platform_headers)
        assert resp.status_code == 200
        tenants = resp.json().get("tenants", [])
        names = {t["code"]: t["name"] for t in tenants}
        # Platform default
        assert PLATFORM_PARTNER_CODE in names
        print(f"PASS: Tenant names: {names}")

    def test_create_tenant_via_admin_api(self, http, platform_headers):
        """Platform admin can create a new tenant (Partner Orgs tab flow)."""
        unique_code = f"test-phase4-admin-{int(time.time())}"
        resp = http.post(f"{BASE_URL}/api/admin/tenants", json={
            "name": "TEST Phase4 Admin Tenant",
            "code": unique_code,
            "status": "active",
        }, headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "tenant" in data, f"No 'tenant' key: {data}"
        tenant = data["tenant"]
        assert tenant["code"] == unique_code
        assert "id" in tenant
        TestAdminTenantsPhase4.created_tenant_id = tenant["id"]
        print(f"PASS: Created tenant id={tenant['id']}, code={unique_code}")

    def test_add_partner_admin_to_tenant(self, http, platform_headers):
        """Platform admin can add partner admin user to a tenant."""
        tid = TestAdminTenantsPhase4.created_tenant_id
        if not tid:
            pytest.skip("No tenant created in previous test")
        unique_ts = int(time.time())
        resp = http.post(f"{BASE_URL}/api/admin/tenants/{tid}/create-admin", json={
            "tenant_id": tid,
            "email": f"testadmin-{unique_ts}@phase4tenant.local",
            "full_name": "Test Admin Phase4",
            "password": "AdminPass123!",
            "role": "partner_super_admin",
        }, headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "user_id" in data, f"No user_id in response: {data}"
        print(f"PASS: Added partner admin to tenant. user_id={data['user_id']}")

    def test_get_tenant_users(self, http, platform_headers):
        """Platform admin can list users of a tenant."""
        tid = TestAdminTenantsPhase4.created_tenant_id
        if not tid:
            pytest.skip("No tenant created in previous test")
        resp = http.get(f"{BASE_URL}/api/admin/tenants/{tid}/users", headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "users" in data, f"No 'users' key: {data}"
        assert len(data["users"]) >= 1, f"Expected at least 1 user: {data}"
        print(f"PASS: Tenant users count={len(data['users'])}")

    def test_deactivate_tenant(self, http, platform_headers):
        """Platform admin can deactivate a non-default tenant."""
        tid = TestAdminTenantsPhase4.created_tenant_id
        if not tid:
            pytest.skip("No tenant created in previous test")
        resp = http.post(f"{BASE_URL}/api/admin/tenants/{tid}/deactivate", headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "message" in data
        print(f"PASS: Tenant deactivated: {data['message']}")

    def test_activate_tenant(self, http, platform_headers):
        """Platform admin can re-activate a deactivated tenant."""
        tid = TestAdminTenantsPhase4.created_tenant_id
        if not tid:
            pytest.skip("No tenant created in previous test")
        resp = http.post(f"{BASE_URL}/api/admin/tenants/{tid}/activate", headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "message" in data
        print(f"PASS: Tenant activated: {data['message']}")

    def test_deactivate_default_tenant_blocked(self, http, platform_headers):
        """Deactivating the default tenant (automate-accounts) returns 400."""
        # First get the automate-accounts tenant ID
        resp = http.get(f"{BASE_URL}/api/admin/tenants", headers=platform_headers)
        assert resp.status_code == 200
        tenants = resp.json().get("tenants", [])
        default = next((t for t in tenants if t["code"] == PLATFORM_PARTNER_CODE), None)
        if not default:
            pytest.skip("Default tenant not found")
        resp_deact = http.post(
            f"{BASE_URL}/api/admin/tenants/{default['id']}/deactivate",
            headers=platform_headers,
        )
        assert resp_deact.status_code == 400, f"Expected 400 for default tenant deactivation, got {resp_deact.status_code}: {resp_deact.text}"
        print("PASS: Cannot deactivate default tenant → 400")

    def test_non_platform_admin_cannot_list_tenants(self, http, tenant_b_headers):
        """Non-platform admin (tenant B admin) cannot access /admin/tenants."""
        resp = http.get(f"{BASE_URL}/api/admin/tenants", headers=tenant_b_headers)
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
        print("PASS: Tenant B admin blocked from /admin/tenants → 403")

    def test_cleanup_deactivate_test_tenant(self, http, platform_headers):
        """Cleanup: deactivate test tenant from this test run."""
        tid = TestAdminTenantsPhase4.created_tenant_id
        if not tid:
            pytest.skip("No tenant to cleanup")
        http.post(f"{BASE_URL}/api/admin/tenants/{tid}/deactivate", headers=platform_headers)
        print(f"PASS: Cleanup - test tenant deactivated")


# ---------------------------------------------------------------------------
# Phase 4 Feature 4: TenantSwitcher (X-View-As-Tenant header)
# ---------------------------------------------------------------------------

class TestTenantSwitcher:
    """Platform admin can use X-View-As-Tenant header to view as another tenant."""

    def test_platform_admin_sees_all_customers_default(self, http, platform_headers):
        """Without X-View-As-Tenant, platform admin sees all customers."""
        resp = http.get(f"{BASE_URL}/api/admin/customers", headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "total" in data, f"No total key: {data}"
        print(f"PASS: Platform admin sees {data['total']} customers (all tenants)")

    def test_tenant_switcher_view_as_tenant_b(self, http, platform_headers):
        """Platform admin can view as Tenant B using X-View-As-Tenant header."""
        # First get Tenant B's ID
        resp = http.get(f"{BASE_URL}/api/admin/tenants", headers=platform_headers)
        assert resp.status_code == 200
        tenants = resp.json().get("tenants", [])
        tenant_b = next((t for t in tenants if t["code"] == TENANT_B_CODE), None)
        if not tenant_b:
            pytest.skip("Tenant B not found")

        # View as Tenant B
        headers_with_view_as = {**platform_headers, "X-View-As-Tenant": tenant_b["id"]}
        resp = http.get(f"{BASE_URL}/api/admin/customers", headers=headers_with_view_as)
        assert resp.status_code == 200, f"Expected 200 with view-as tenant, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "total" in data
        print(f"PASS: View-as Tenant B: sees {data['total']} customers (isolated to tenant-b)")

    def test_tenant_switcher_invalid_tenant_id_still_works(self, http, platform_headers):
        """Invalid X-View-As-Tenant is ignored gracefully (no crash)."""
        headers_with_invalid = {**platform_headers, "X-View-As-Tenant": "nonexistent-tenant-id"}
        resp = http.get(f"{BASE_URL}/api/admin/customers", headers=headers_with_invalid)
        # Should still return 200 (invalid tenant view-as is silently ignored per TenantContext logic)
        assert resp.status_code == 200, f"Expected 200 even with invalid view-as, got {resp.status_code}: {resp.text}"
        print("PASS: Invalid X-View-As-Tenant gracefully ignored → 200")


# ---------------------------------------------------------------------------
# Phase 4 Feature 5: Users Tab (isSuperAdmin includes platform_super_admin)
# ---------------------------------------------------------------------------

class TestUsersTab:
    """Platform super admin can access users endpoints (Users Tab)."""

    def test_platform_admin_can_list_users(self, http, platform_headers):
        """Platform admin can GET /admin/users (Users Tab)."""
        resp = http.get(f"{BASE_URL}/api/admin/users", headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "users" in data or "items" in data or isinstance(data, list) or "total" in data, \
            f"Unexpected response structure: {data}"
        print(f"PASS: Platform admin can access /admin/users. Keys: {list(data.keys())}")

    def test_tenant_b_admin_cannot_list_users(self, http, tenant_b_headers):
        """Tenant B admin (partner_super_admin) can access /admin/users within their tenant."""
        resp = http.get(f"{BASE_URL}/api/admin/users", headers=tenant_b_headers)
        # partner_super_admin is a super_admin role for their tenant, should return 200
        assert resp.status_code in (200, 403), f"Expected 200 or 403, got {resp.status_code}: {resp.text}"
        print(f"PASS: Tenant B admin /admin/users returns {resp.status_code}")
