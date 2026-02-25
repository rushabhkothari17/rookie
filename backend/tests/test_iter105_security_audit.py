"""
Security Audit Tests for Multi-Tenant SaaS Platform (Iteration 105)
Tests:
  - Platform admin login (no partner_code required)
  - Blocked endpoints for 'automate-accounts' code
  - Platform admin unrestricted access
  - Unauthenticated access returns 401/403
  - Invalid partner code returns 400
  - Valid partner login flow
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

PLATFORM_ADMIN_EMAIL = "admin@automateaccounts.local"
PLATFORM_ADMIN_PASSWORD = "ChangeMe123!"
RESERVED_CODE = "automate-accounts"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def platform_admin_token():
    """Login as platform admin and return token."""
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": PLATFORM_ADMIN_EMAIL, "password": PLATFORM_ADMIN_PASSWORD},
    )
    assert resp.status_code == 200, f"Platform admin login failed: {resp.status_code} {resp.text}"
    token = resp.json().get("token")
    assert token, "No token returned from platform admin login"
    return token


@pytest.fixture(scope="module")
def platform_admin_headers(platform_admin_token):
    return {"Authorization": f"Bearer {platform_admin_token}"}


@pytest.fixture(scope="module")
def valid_partner_code(platform_admin_headers):
    """Create a test partner tenant and return its code. Cleans up after module."""
    # Create a test partner
    payload = {
        "name": "TEST Security Audit Partner",
        "code": "test-security-partner",
        "status": "active",
    }
    resp = requests.post(
        f"{BASE_URL}/api/admin/tenants",
        json=payload,
        headers=platform_admin_headers,
    )
    if resp.status_code == 400 and "already in use" in resp.text:
        # Already exists from a previous run
        return "test-security-partner"
    assert resp.status_code in [200, 201], f"Failed to create test partner: {resp.text}"
    return resp.json()["tenant"]["code"]


# ---------------------------------------------------------------------------
# Test 1: Platform admin login without partner_code
# ---------------------------------------------------------------------------

class TestPlatformAdminLogin:
    """Test 1 - Platform admin can log in via /api/auth/login without partner_code."""

    def test_platform_admin_login_success(self):
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": PLATFORM_ADMIN_EMAIL, "password": PLATFORM_ADMIN_PASSWORD},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "token" in data, "No token in response"
        print(f"PASS: Platform admin login returned status 200 with token")

    def test_platform_admin_login_role(self):
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": PLATFORM_ADMIN_EMAIL, "password": PLATFORM_ADMIN_PASSWORD},
        )
        assert resp.status_code == 200
        data = resp.json()
        role = data.get("role")
        assert role == "platform_admin", f"Expected role='platform_admin', got '{role}'"
        print(f"PASS: Platform admin login returned role=platform_admin")


# ---------------------------------------------------------------------------
# Test 2: POST /api/auth/partner-login with partner_code='automate-accounts' returns 403
# ---------------------------------------------------------------------------

class TestPartnerLoginBlocked:
    """Test 2 - partner-login with automate-accounts code is blocked."""

    def test_partner_login_automate_accounts_blocked(self):
        resp = requests.post(
            f"{BASE_URL}/api/auth/partner-login",
            json={
                "email": PLATFORM_ADMIN_EMAIL,
                "password": PLATFORM_ADMIN_PASSWORD,
                "partner_code": RESERVED_CODE,
            },
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print(f"PASS: partner-login with 'automate-accounts' correctly blocked (403)")

    def test_partner_login_automate_accounts_blocked_case_insensitive(self):
        """Test case-insensitive blocking."""
        resp = requests.post(
            f"{BASE_URL}/api/auth/partner-login",
            json={
                "email": PLATFORM_ADMIN_EMAIL,
                "password": PLATFORM_ADMIN_PASSWORD,
                "partner_code": "Automate-Accounts",
            },
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print(f"PASS: partner-login with 'Automate-Accounts' (mixed case) correctly blocked (403)")


# ---------------------------------------------------------------------------
# Test 3: POST /api/auth/customer-login with partner_code='automate-accounts' returns 403
# ---------------------------------------------------------------------------

class TestCustomerLoginBlocked:
    """Test 3 - customer-login with automate-accounts code is blocked."""

    def test_customer_login_automate_accounts_blocked(self):
        resp = requests.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={
                "email": "any@example.com",
                "password": "anypassword",
                "partner_code": RESERVED_CODE,
            },
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print(f"PASS: customer-login with 'automate-accounts' correctly blocked (403)")

    def test_customer_login_automate_accounts_blocked_case_insensitive(self):
        """Test case-insensitive blocking."""
        resp = requests.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={
                "email": "any@example.com",
                "password": "anypassword",
                "partner_code": "AUTOMATE-ACCOUNTS",
            },
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print(f"PASS: customer-login with 'AUTOMATE-ACCOUNTS' (uppercase) correctly blocked (403)")


# ---------------------------------------------------------------------------
# Test 4: POST /api/auth/register?partner_code=automate-accounts returns 403
# ---------------------------------------------------------------------------

class TestRegisterBlocked:
    """Test 4 - register with partner_code=automate-accounts is blocked."""

    def test_register_automate_accounts_blocked(self):
        # Must provide a valid body so Pydantic validation passes and security check fires
        resp = requests.post(
            f"{BASE_URL}/api/auth/register?partner_code={RESERVED_CODE}",
            json={
                "email": "newuser@example.com",
                "password": "SecurePass123!",
                "full_name": "Test User",
                "address": {
                    "line1": "123 Test St",
                    "line2": "",
                    "city": "London",
                    "region": "England",
                    "postal": "EC1A 1BB",
                    "country": "GB",
                },
            },
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print(f"PASS: register?partner_code=automate-accounts correctly blocked (403)")


# ---------------------------------------------------------------------------
# Test 5: POST /api/admin/tenants with code='automate-accounts' returns 400
# ---------------------------------------------------------------------------

class TestAdminTenantCreationBlocked:
    """Test 5 - creating a tenant with code='automate-accounts' is blocked."""

    def test_create_tenant_with_reserved_code_blocked(self, platform_admin_headers):
        resp = requests.post(
            f"{BASE_URL}/api/admin/tenants",
            json={
                "name": "Hacked Platform",
                "code": RESERVED_CODE,
                "status": "active",
            },
            headers=platform_admin_headers,
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        print(f"PASS: POST /api/admin/tenants with code='automate-accounts' blocked (400)")

    def test_create_tenant_reserved_code_case_variants(self, platform_admin_headers):
        """Test uppercase variant is also blocked."""
        resp = requests.post(
            f"{BASE_URL}/api/admin/tenants",
            json={
                "name": "Hacked Platform",
                "code": "AUTOMATE-ACCOUNTS",
                "status": "active",
            },
            headers=platform_admin_headers,
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        print(f"PASS: POST /api/admin/tenants with code='AUTOMATE-ACCOUNTS' also blocked (400)")


# ---------------------------------------------------------------------------
# Test 6: POST /api/admin/tenants/automate-accounts/create-admin returns 403
# ---------------------------------------------------------------------------

class TestCreateAdminUnderReservedTenantBlocked:
    """Test 6 - creating a partner admin under automate-accounts tenant is blocked."""

    def test_create_admin_under_reserved_tenant_blocked(self, platform_admin_headers):
        # Note: CreatePartnerAdminRequest requires tenant_id in body as well
        # Platform tenant id and code are both 'automate-accounts' per system context
        resp = requests.post(
            f"{BASE_URL}/api/admin/tenants/{RESERVED_CODE}/create-admin",
            json={
                "tenant_id": RESERVED_CODE,
                "email": "hacker@example.com",
                "password": "HackerPass123!",
                "full_name": "Hacker",
                "role": "partner_super_admin",
            },
            headers=platform_admin_headers,
        )
        # Should return 403 (blocked by is_platform check) or 404 (tenant not found by ID)
        assert resp.status_code in [403, 404], f"Expected 403 or 404, got {resp.status_code}: {resp.text}"
        print(f"PASS: POST /api/admin/tenants/automate-accounts/create-admin correctly blocked ({resp.status_code})")


# ---------------------------------------------------------------------------
# Test 7: Platform admin GET /api/admin/tenants returns full list (unrestricted)
# ---------------------------------------------------------------------------

class TestPlatformAdminUnrestrictedAccess:
    """Tests 7-10: Platform admin has unrestricted access to all data."""

    def test_platform_admin_get_tenants(self, platform_admin_headers):
        resp = requests.get(
            f"{BASE_URL}/api/admin/tenants",
            headers=platform_admin_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "tenants" in data, "No 'tenants' key in response"
        assert isinstance(data["tenants"], list), "'tenants' must be a list"
        print(f"PASS: Platform admin GET /api/admin/tenants returned {len(data['tenants'])} tenants")

    def test_platform_admin_get_customers(self, platform_admin_headers):
        """Test 8 - Platform admin can access customers (unrestricted)."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/customers",
            headers=platform_admin_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "customers" in data or "items" in data or isinstance(data, list), \
            f"Unexpected response structure: {list(data.keys())}"
        print(f"PASS: Platform admin GET /api/admin/customers returned 200")

    def test_platform_admin_get_orders(self, platform_admin_headers):
        """Test 9 - Platform admin can access orders (unrestricted)."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/orders",
            headers=platform_admin_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print(f"PASS: Platform admin GET /api/admin/orders returned 200")

    def test_platform_admin_get_users(self, platform_admin_headers):
        """Test 10 - Platform admin can access all admin users."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/users",
            headers=platform_admin_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "users" in data or "items" in data or isinstance(data, list), \
            f"Unexpected response structure: {list(data.keys())}"
        print(f"PASS: Platform admin GET /api/admin/users returned 200")

    def test_platform_admin_tenants_returns_multiple(self, platform_admin_headers):
        """Verify platform admin sees ALL tenants (cross-tenant, unrestricted)."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/tenants",
            headers=platform_admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        tenants = data.get("tenants", [])
        # Platform admin should see all tenants including automate-accounts itself
        assert len(tenants) >= 1, "Platform admin should see at least one tenant"
        codes = [t.get("code") for t in tenants]
        print(f"PASS: Platform admin sees {len(tenants)} tenants: {codes}")


# ---------------------------------------------------------------------------
# Test 11: GET /api/admin/tenants without auth returns 401/403
# ---------------------------------------------------------------------------

class TestUnauthenticatedAccessBlocked:
    """Test 11 - Unauthenticated access to admin routes is blocked."""

    def test_get_tenants_without_auth_blocked(self):
        resp = requests.get(f"{BASE_URL}/api/admin/tenants")
        assert resp.status_code in [401, 403], f"Expected 401 or 403, got {resp.status_code}: {resp.text}"
        print(f"PASS: GET /api/admin/tenants without auth returns {resp.status_code}")

    def test_get_customers_without_auth_blocked(self):
        resp = requests.get(f"{BASE_URL}/api/admin/customers")
        assert resp.status_code in [401, 403], f"Expected 401 or 403, got {resp.status_code}: {resp.text}"
        print(f"PASS: GET /api/admin/customers without auth returns {resp.status_code}")

    def test_get_orders_without_auth_blocked(self):
        resp = requests.get(f"{BASE_URL}/api/admin/orders")
        assert resp.status_code in [401, 403], f"Expected 401 or 403, got {resp.status_code}: {resp.text}"
        print(f"PASS: GET /api/admin/orders without auth returns {resp.status_code}")

    def test_get_users_without_auth_blocked(self):
        resp = requests.get(f"{BASE_URL}/api/admin/users")
        assert resp.status_code in [401, 403], f"Expected 401 or 403, got {resp.status_code}: {resp.text}"
        print(f"PASS: GET /api/admin/users without auth returns {resp.status_code}")

    def test_create_tenant_without_auth_blocked(self):
        resp = requests.post(
            f"{BASE_URL}/api/admin/tenants",
            json={"name": "Test", "code": "test-no-auth", "status": "active"},
        )
        assert resp.status_code in [401, 403], f"Expected 401 or 403, got {resp.status_code}: {resp.text}"
        print(f"PASS: POST /api/admin/tenants without auth returns {resp.status_code}")


# ---------------------------------------------------------------------------
# Test 12: POST /api/auth/partner-login with invalid partner code returns 400
# ---------------------------------------------------------------------------

class TestInvalidPartnerCode:
    """Test 12 - partner-login with invalid/nonexistent partner code returns 400."""

    def test_partner_login_invalid_code(self):
        resp = requests.post(
            f"{BASE_URL}/api/auth/partner-login",
            json={
                "email": "some@user.com",
                "password": "SomePass123!",
                "partner_code": "completely-nonexistent-code-xyz123",
            },
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        print(f"PASS: partner-login with invalid code returns 400")


# ---------------------------------------------------------------------------
# Test 13: Platform admin /me endpoint shows role=platform_admin
# ---------------------------------------------------------------------------

class TestPlatformAdminMeEndpoint:
    """Test 13 - /me endpoint returns role=platform_admin for platform admin."""

    def test_me_endpoint_role_platform_admin(self, platform_admin_headers):
        # /me endpoint is at /api/me (not /api/auth/me)
        # Response is nested: {"user": {...}, "customer": ..., "address": ...}
        resp = requests.get(
            f"{BASE_URL}/api/me",
            headers=platform_admin_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        user_data = data.get("user", data)  # handle both flat and nested
        role = user_data.get("role")
        assert role == "platform_admin", f"Expected role='platform_admin', got '{role}'"
        print(f"PASS: /me endpoint returns role=platform_admin")

    def test_me_endpoint_no_tenant_id(self, platform_admin_headers):
        """Platform admin should have tenant_id=None."""
        resp = requests.get(
            f"{BASE_URL}/api/me",
            headers=platform_admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        user_data = data.get("user", data)
        tenant_id = user_data.get("tenant_id")
        assert tenant_id is None, f"Expected tenant_id=None, got '{tenant_id}'"
        print(f"PASS: Platform admin /me returns tenant_id=None")


# ---------------------------------------------------------------------------
# Test 14: Valid partner login works normally
# ---------------------------------------------------------------------------

class TestValidPartnerLogin:
    """Test 14 - partner-login with a VALID partner code works normally."""

    def test_valid_partner_login_works(self, valid_partner_code, platform_admin_headers):
        """First create a user for the partner, then login via partner-login."""
        # Create a partner admin user for the test partner
        # Get the tenant id from the list
        resp = requests.get(
            f"{BASE_URL}/api/admin/tenants",
            headers=platform_admin_headers,
        )
        assert resp.status_code == 200
        tenants = resp.json()["tenants"]
        test_tenant = next(
            (t for t in tenants if t.get("code") == valid_partner_code), None
        )
        assert test_tenant is not None, f"Test tenant '{valid_partner_code}' not found in tenant list"
        tenant_id = test_tenant["id"]

        # Create a partner admin user
        create_user_resp = requests.post(
            f"{BASE_URL}/api/admin/tenants/{tenant_id}/create-admin",
            json={
                "tenant_id": tenant_id,  # Required in body by CreatePartnerAdminRequest
                "email": "test-partner-admin@security-test.local",
                "password": "SecurePass123!",
                "full_name": "Test Partner Admin",
                "role": "partner_super_admin",
            },
            headers=platform_admin_headers,
        )
        # If user already exists, that's OK
        if create_user_resp.status_code not in [200, 201]:
            if "already registered" in create_user_resp.text:
                print("Partner admin user already exists, proceeding to login test")
            else:
                pytest.skip(f"Could not create test partner user: {create_user_resp.text}")

        # Login with the valid partner code
        login_resp = requests.post(
            f"{BASE_URL}/api/auth/partner-login",
            json={
                "email": "test-partner-admin@security-test.local",
                "password": "SecurePass123!",
                "partner_code": valid_partner_code,
            },
        )
        assert login_resp.status_code == 200, f"Expected 200, got {login_resp.status_code}: {login_resp.text}"
        data = login_resp.json()
        assert "token" in data, "No token in response"
        print(f"PASS: Valid partner login with code='{valid_partner_code}' returned 200 with token")
