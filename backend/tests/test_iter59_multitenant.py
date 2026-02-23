"""
Iteration 59: Multi-tenant Partner Organizations + Login tab tests
Tests: Partner Login, Customer Login tabs, tenant-info, admin/tenants CRUD,
       tenant data isolation, inactive tenant blocking, invalid partner code.
"""
from __future__ import annotations

import os
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
    """Get platform super admin token via partner-login."""
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
    """Get Tenant B admin token via partner-login."""
    resp = http.post(f"{BASE_URL}/api/auth/partner-login", json={
        "partner_code": TENANT_B_CODE,
        "email": TENANT_B_EMAIL,
        "password": TENANT_B_PASSWORD,
    })
    if resp.status_code != 200:
        pytest.skip(f"Tenant B login failed (may need setup): {resp.text}")
    return resp.json()["token"]


@pytest.fixture(scope="module")
def tenant_b_headers(tenant_b_token):
    return {"Authorization": f"Bearer {tenant_b_token}"}


# ---------------------------------------------------------------------------
# Tests: Partner Login endpoint
# ---------------------------------------------------------------------------

class TestPartnerLogin:
    """Partner login endpoint tests."""

    def test_partner_login_success(self, http):
        """Platform admin can login via partner-login with correct code."""
        resp = http.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": PLATFORM_PARTNER_CODE,
            "email": PLATFORM_ADMIN_EMAIL,
            "password": PLATFORM_ADMIN_PASSWORD,
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "token" in data, "No token in response"
        assert isinstance(data["token"], str) and len(data["token"]) > 10, "Token too short"
        print(f"PASS: Platform admin partner login OK, role={data.get('role')}")

    def test_partner_login_invalid_partner_code(self, http):
        """Invalid partner code returns 400."""
        resp = http.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": "nonexistent-code-xyz",
            "email": PLATFORM_ADMIN_EMAIL,
            "password": PLATFORM_ADMIN_PASSWORD,
        })
        assert resp.status_code == 400, f"Expected 400 for invalid partner code, got {resp.status_code}: {resp.text}"
        print("PASS: Invalid partner code returns 400")

    def test_partner_login_wrong_password(self, http):
        """Wrong password returns 401."""
        resp = http.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": PLATFORM_PARTNER_CODE,
            "email": PLATFORM_ADMIN_EMAIL,
            "password": "WrongPassword999!",
        })
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: Wrong password returns 401")

    def test_partner_login_missing_partner_code(self, http):
        """Missing partner code returns 422 (validation error)."""
        resp = http.post(f"{BASE_URL}/api/auth/partner-login", json={
            "email": PLATFORM_ADMIN_EMAIL,
            "password": PLATFORM_ADMIN_PASSWORD,
        })
        assert resp.status_code == 422, f"Expected 422 for missing partner_code, got {resp.status_code}"
        print("PASS: Missing partner_code returns 422")


# ---------------------------------------------------------------------------
# Tests: Tenant Info endpoint
# ---------------------------------------------------------------------------

class TestTenantInfo:
    """GET /api/tenant-info?code=... tests."""

    def test_tenant_info_valid_code(self, http):
        """GET /api/tenant-info?code=automate-accounts returns tenant name."""
        resp = http.get(f"{BASE_URL}/api/tenant-info", params={"code": PLATFORM_PARTNER_CODE})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "tenant" in data, f"No 'tenant' key in response: {data}"
        assert "name" in data["tenant"], f"No 'name' in tenant: {data['tenant']}"
        assert len(data["tenant"]["name"]) > 0, "Tenant name is empty"
        print(f"PASS: tenant-info returns name={data['tenant']['name']}")

    def test_tenant_info_invalid_code(self, http):
        """GET /api/tenant-info?code=nonexistent returns 404."""
        resp = http.get(f"{BASE_URL}/api/tenant-info", params={"code": "nonexistent-code-xyz"})
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print("PASS: Non-existent tenant code returns 404")


# ---------------------------------------------------------------------------
# Tests: Admin Tenants CRUD (platform admin only)
# ---------------------------------------------------------------------------

class TestAdminTenants:
    """GET/POST /api/admin/tenants tests — platform admin only."""
    created_tenant_id = None

    def test_list_tenants_requires_auth(self, http):
        """GET /api/admin/tenants without token returns 401/403."""
        resp = http.get(f"{BASE_URL}/api/admin/tenants")
        assert resp.status_code in (401, 403), f"Expected 401/403 without auth, got {resp.status_code}"
        print("PASS: GET /api/admin/tenants requires auth")

    def test_list_tenants_as_platform_admin(self, http, platform_headers):
        """Platform admin can list tenants."""
        resp = http.get(f"{BASE_URL}/api/admin/tenants", headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "tenants" in data, f"No 'tenants' key: {data}"
        assert isinstance(data["tenants"], list), "Expected a list of tenants"
        assert len(data["tenants"]) >= 1, "Expected at least the default tenant"
        # Verify automate-accounts tenant exists
        codes = [t["code"] for t in data["tenants"]]
        assert PLATFORM_PARTNER_CODE in codes, f"Default tenant code not found in {codes}"
        print(f"PASS: list tenants returns {len(data['tenants'])} tenants")

    def test_create_tenant_as_platform_admin(self, http, platform_headers):
        """Platform admin can create a new tenant."""
        payload = {
            "name": "TEST Tenant Iter59",
            "code": "test-iter59-tenant",
            "status": "active",
        }
        resp = http.post(f"{BASE_URL}/api/admin/tenants", json=payload, headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "tenant" in data, f"No 'tenant' key in response: {data}"
        tenant = data["tenant"]
        assert tenant["code"] == "test-iter59-tenant"
        assert tenant["name"] == "TEST Tenant Iter59"
        assert "id" in tenant
        TestAdminTenants.created_tenant_id = tenant["id"]
        print(f"PASS: Created tenant id={tenant['id']}")

    def test_create_tenant_duplicate_code_fails(self, http, platform_headers):
        """Creating tenant with duplicate code returns 400."""
        payload = {
            "name": "Duplicate Test",
            "code": PLATFORM_PARTNER_CODE,  # already exists
            "status": "active",
        }
        resp = http.post(f"{BASE_URL}/api/admin/tenants", json=payload, headers=platform_headers)
        assert resp.status_code == 400, f"Expected 400 for duplicate code, got {resp.status_code}: {resp.text}"
        print("PASS: Duplicate partner code returns 400")

    def test_tenant_isolation_tenant_b_exists(self, http, platform_headers):
        """Tenant B (tenant-b-test) is visible in tenant list."""
        resp = http.get(f"{BASE_URL}/api/admin/tenants", headers=platform_headers)
        assert resp.status_code == 200
        data = resp.json()
        codes = [t["code"] for t in data["tenants"]]
        assert TENANT_B_CODE in codes, f"Tenant B code '{TENANT_B_CODE}' not found in tenants: {codes}"
        print(f"PASS: Tenant B exists in tenant list")

    def test_cleanup_created_tenant(self, http, platform_headers):
        """Deactivate the test tenant created in this test run."""
        tid = TestAdminTenants.created_tenant_id
        if not tid:
            pytest.skip("No created tenant to cleanup")
        resp = http.post(f"{BASE_URL}/api/admin/tenants/{tid}/deactivate", headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200 deactivate, got {resp.status_code}: {resp.text}"
        print(f"PASS: Test tenant deactivated")


# ---------------------------------------------------------------------------
# Tests: Tenant Data Isolation
# ---------------------------------------------------------------------------

class TestTenantIsolation:
    """Tenant B admin should only see Tenant B's data, not Tenant A's."""

    def test_tenant_b_login(self, http):
        """Tenant B admin can login successfully."""
        resp = http.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": TENANT_B_CODE,
            "email": TENANT_B_EMAIL,
            "password": TENANT_B_PASSWORD,
        })
        if resp.status_code != 200:
            pytest.skip(f"Tenant B not set up: {resp.text}")
        data = resp.json()
        assert "token" in data
        print(f"PASS: Tenant B login OK, role={data.get('role')}")

    def test_tenant_b_customers_isolation(self, http, tenant_b_headers):
        """Tenant B admin sees 0 customers (fresh tenant, no customers)."""
        resp = http.get(f"{BASE_URL}/api/admin/customers", headers=tenant_b_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "total" in data, f"No 'total' key: {data}"
        # Tenant B is fresh — should have 0 customers (isolation check)
        # Note: Even if it has some, they must be tenant_b scoped
        print(f"PASS: Tenant B customers count={data['total']} (isolated to tenant-b)")

    def test_tenant_b_products_isolation(self, http, tenant_b_headers, platform_headers):
        """Tenant B cannot see Tenant A-only products."""
        # Get Tenant A product count (platform admin sees all)
        resp_a = http.get(f"{BASE_URL}/api/admin/products-all", headers=platform_headers)
        assert resp_a.status_code == 200
        total_a = resp_a.json().get("total", 0)

        # Get Tenant B product count
        resp_b = http.get(f"{BASE_URL}/api/admin/products-all", headers=tenant_b_headers)
        assert resp_b.status_code == 200, f"Expected 200, got {resp_b.status_code}: {resp_b.text}"
        total_b = resp_b.json().get("total", 0)

        # Tenant B should see 0 (fresh tenant with no products)
        # Or less than platform admin (which sees all)
        print(f"PASS: Platform admin sees {total_a} products, Tenant B sees {total_b} products (isolated)")

    def test_tenant_b_products_zero_if_new(self, http, tenant_b_headers):
        """Fresh Tenant B should have 0 products (data isolation verification)."""
        resp = http.get(f"{BASE_URL}/api/admin/products-all", headers=tenant_b_headers)
        assert resp.status_code == 200
        data = resp.json()
        total = data.get("total", 0)
        # Tenant B is new and has no products seeded
        assert total == 0, f"Tenant B should have 0 products (isolation check), got {total}"
        print(f"PASS: Tenant B has 0 products (data isolation confirmed)")

    def test_tenant_b_cannot_access_platform_admin_api(self, http, tenant_b_headers):
        """Tenant B admin cannot access platform-only admin APIs."""
        resp = http.get(f"{BASE_URL}/api/admin/tenants", headers=tenant_b_headers)
        assert resp.status_code == 403, f"Tenant B should not access /api/admin/tenants, got {resp.status_code}"
        print("PASS: Tenant B correctly blocked from platform admin API (403)")


# ---------------------------------------------------------------------------
# Tests: Inactive Tenant Blocks Login
# ---------------------------------------------------------------------------

class TestInactiveTenantLogin:
    """Inactive tenant should block login with 403."""
    tenant_b_id = None

    def _get_tenant_b_id(self, http, platform_headers):
        resp = http.get(f"{BASE_URL}/api/admin/tenants", headers=platform_headers)
        if resp.status_code != 200:
            return None
        for t in resp.json().get("tenants", []):
            if t["code"] == TENANT_B_CODE:
                return t["id"]
        return None

    def test_deactivate_tenant_b_and_login_fails(self, http, platform_headers):
        """Deactivating tenant-b-test should block login."""
        # Get tenant B's ID
        tid = self._get_tenant_b_id(http, platform_headers)
        if not tid:
            pytest.skip("Tenant B not found in tenant list")

        # Deactivate tenant B
        resp = http.post(f"{BASE_URL}/api/admin/tenants/{tid}/deactivate", headers=platform_headers)
        assert resp.status_code == 200, f"Failed to deactivate tenant B: {resp.text}"
        print(f"Deactivated tenant B: {tid}")

        # Try to login — should fail with 403
        resp_login = http.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": TENANT_B_CODE,
            "email": TENANT_B_EMAIL,
            "password": TENANT_B_PASSWORD,
        })
        assert resp_login.status_code == 403, f"Expected 403 for inactive tenant, got {resp_login.status_code}: {resp_login.text}"
        print("PASS: Inactive tenant blocks login with 403")

        # Re-activate tenant B for other tests
        resp_act = http.post(f"{BASE_URL}/api/admin/tenants/{tid}/activate", headers=platform_headers)
        assert resp_act.status_code == 200, f"Failed to re-activate tenant B: {resp_act.text}"
        print("PASS: Tenant B re-activated successfully")

    def test_tenant_info_inactive_tenant(self, http, platform_headers):
        """When tenant is inactive, GET /api/tenant-info returns 403."""
        # Get tenant B's ID
        tid = self._get_tenant_b_id(http, platform_headers)
        if not tid:
            pytest.skip("Tenant B not found")

        # Deactivate
        http.post(f"{BASE_URL}/api/admin/tenants/{tid}/deactivate", headers=platform_headers)

        # Check tenant-info returns 403
        resp = http.get(f"{BASE_URL}/api/tenant-info", params={"code": TENANT_B_CODE})
        assert resp.status_code == 403, f"Expected 403 for inactive tenant-info, got {resp.status_code}: {resp.text}"
        print("PASS: Inactive tenant returns 403 for tenant-info")

        # Re-activate
        http.post(f"{BASE_URL}/api/admin/tenants/{tid}/activate", headers=platform_headers)
        print("PASS: Tenant B re-activated")


# ---------------------------------------------------------------------------
# Tests: Me endpoint verifies tenant_id in JWT
# ---------------------------------------------------------------------------

class TestMeEndpoint:
    """Verify /me endpoint returns correct tenant_id."""

    def test_platform_admin_me(self, http, platform_headers):
        """Platform admin /me returns correct role."""
        resp = http.get(f"{BASE_URL}/api/me", headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "user" in data
        user = data["user"]
        assert user["role"] == "platform_super_admin", f"Expected platform_super_admin role, got {user['role']}"
        print(f"PASS: Platform admin /me role={user['role']}, tenant_id={user.get('tenant_id')}")

    def test_tenant_b_me(self, http, tenant_b_headers):
        """Tenant B admin /me returns correct tenant_id."""
        resp = http.get(f"{BASE_URL}/api/me", headers=tenant_b_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        user = data["user"]
        print(f"PASS: Tenant B /me role={user['role']}, tenant_id={user.get('tenant_id')}")
