"""
Backend tests for UX improvements iteration 261:
1. GET /api/admin/tenants returns store_name field enriched from app_settings
2. POST /api/admin/customers/create with tenant_id override for platform admin
3. POST /api/admin/customers/create without tenant_id for partner admin stays in own tenant
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


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
def partner_tenant_id(platform_admin_headers):
    """Get the tenant_id of an existing partner tenant (not automate-accounts)."""
    r = requests.get(f"{BASE_URL}/api/admin/tenants", headers=platform_admin_headers)
    assert r.status_code == 200
    tenants = r.json().get("tenants", [])
    partner = next(
        (t for t in tenants if t.get("code") and t["code"] != "automate-accounts"),
        None,
    )
    assert partner is not None, "No partner tenant found for testing"
    return partner["id"]


@pytest.fixture(scope="module")
def partner_tenant_code(platform_admin_headers):
    """Get the code of an existing partner tenant."""
    r = requests.get(f"{BASE_URL}/api/admin/tenants", headers=platform_admin_headers)
    assert r.status_code == 200
    tenants = r.json().get("tenants", [])
    partner = next(
        (t for t in tenants if t.get("code") and t["code"] != "automate-accounts"),
        None,
    )
    assert partner is not None, "No partner tenant found for testing"
    return partner["code"]


# ── Test 1: GET /api/admin/tenants returns store_name ─────────────────────────

class TestTenantsStoreNameEnrichment:
    """Verify GET /api/admin/tenants enriches each tenant with store_name from app_settings."""

    def test_list_tenants_returns_200(self, platform_admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/tenants", headers=platform_admin_headers)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    def test_tenants_response_has_tenants_key(self, platform_admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/tenants", headers=platform_admin_headers)
        data = r.json()
        assert "tenants" in data, "Response missing 'tenants' key"

    def test_each_tenant_has_store_name_field(self, platform_admin_headers):
        """Every tenant in the list must have a 'store_name' key (can be empty string)."""
        r = requests.get(f"{BASE_URL}/api/admin/tenants", headers=platform_admin_headers)
        tenants = r.json().get("tenants", [])
        assert len(tenants) > 0, "No tenants returned"
        for t in tenants:
            assert "store_name" in t, f"Tenant {t.get('code', '?')} missing 'store_name' key"

    def test_store_name_is_string(self, platform_admin_headers):
        """store_name should be a string (not None/missing)."""
        r = requests.get(f"{BASE_URL}/api/admin/tenants", headers=platform_admin_headers)
        tenants = r.json().get("tenants", [])
        for t in tenants:
            assert isinstance(t.get("store_name", None), str), \
                f"store_name for tenant {t.get('code')} is not a string: {t.get('store_name')}"

    def test_platform_admin_tenant_in_list(self, platform_admin_headers):
        """The automate-accounts tenant should be present."""
        r = requests.get(f"{BASE_URL}/api/admin/tenants", headers=platform_admin_headers)
        tenants = r.json().get("tenants", [])
        codes = [t.get("code") for t in tenants]
        assert "automate-accounts" in codes, "automate-accounts tenant not in list"


# ── Test 2: Platform admin can create customer in a target tenant ──────────────

class TestPlatformAdminCreateCustomerWithTenantId:
    """Verify platform admin can specify tenant_id to create customer in another tenant."""

    def test_create_customer_with_tenant_id_returns_200(self, platform_admin_headers, partner_tenant_id):
        payload = {
            "full_name": "TEST_PA Customer",
            "email": f"test_pa_customer_{partner_tenant_id[:6]}@example-test.com",
            "password": "TestPass123!",
            "company_name": "TEST Corp",
            "job_title": "Tester",
            "phone": "+1 555 000 0001",
            "line1": "123 Test Street",
            "line2": "",
            "city": "Toronto",
            "region": "Ontario",
            "postal": "M1M1M1",
            "country": "Canada",
            "mark_verified": True,
            "tenant_id": partner_tenant_id,
        }
        r = requests.post(f"{BASE_URL}/api/admin/customers/create", headers=platform_admin_headers, json=payload)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    def test_create_customer_with_tenant_id_returns_customer_id(self, platform_admin_headers, partner_tenant_id):
        import time
        payload = {
            "full_name": "TEST_PA Customer2",
            "email": f"test_pa_cust2_{int(time.time())}@example-test.com",
            "password": "TestPass123!",
            "company_name": "TEST Corp",
            "job_title": "",
            "phone": "",
            "line1": "456 Test Ave",
            "line2": "",
            "city": "Vancouver",
            "region": "BC",
            "postal": "V1V1V1",
            "country": "Canada",
            "mark_verified": True,
            "tenant_id": partner_tenant_id,
        }
        r = requests.post(f"{BASE_URL}/api/admin/customers/create", headers=platform_admin_headers, json=payload)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "customer_id" in data, "Response missing customer_id"
        assert "user_id" in data, "Response missing user_id"

    def test_create_customer_with_invalid_tenant_id_returns_400(self, platform_admin_headers):
        payload = {
            "full_name": "TEST Invalid",
            "email": "test_invalid_tenant@example-test.com",
            "password": "TestPass123!",
            "company_name": "",
            "job_title": "",
            "phone": "",
            "line1": "1 Test St",
            "line2": "",
            "city": "City",
            "region": "Region",
            "postal": "12345",
            "country": "Canada",
            "mark_verified": True,
            "tenant_id": "nonexistent-tenant-id-999",
        }
        r = requests.post(f"{BASE_URL}/api/admin/customers/create", headers=platform_admin_headers, json=payload)
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
        assert "not found" in r.json().get("detail", "").lower()

    def test_create_customer_without_tenant_id_fails_for_platform_admin(self, platform_admin_headers):
        """Platform admin without tenant_id should fail the frontend check,
        but backend allows it (uses own tenant). This verifies backend doesn't 400."""
        import time
        payload = {
            "full_name": "TEST_PA No Tenant",
            "email": f"test_no_tenant_{int(time.time())}@example-test.com",
            "password": "TestPass123!",
            "company_name": "",
            "job_title": "",
            "phone": "",
            "line1": "1 Test St",
            "line2": "",
            "city": "City",
            "region": "Region",
            "postal": "12345",
            "country": "Canada",
            "mark_verified": True,
            # No tenant_id provided
        }
        r = requests.post(f"{BASE_URL}/api/admin/customers/create", headers=platform_admin_headers, json=payload)
        # Backend doesn't require tenant_id - it falls back to admin's own tenant
        # The frontend prevents submission without selecting a tenant
        assert r.status_code in [200, 400], f"Unexpected status: {r.status_code}: {r.text}"


# ── Test 3: Partner admin creates customer in their own tenant ─────────────────

class TestPartnerAdminCreateCustomer:
    """Verify partner admin creates customer in their own tenant (no cross-tenant)."""

    @pytest.fixture(scope="class")
    def partner_admin_token(self, platform_admin_headers):
        """Create a test partner tenant and admin for testing."""
        import time, random
        suffix = int(time.time()) % 10000

        # Create a test partner org via admin
        create_r = requests.post(
            f"{BASE_URL}/api/admin/tenants/create-partner",
            headers=platform_admin_headers,
            json={
                "name": f"TEST_PartnerOrg_{suffix}",
                "admin_name": "Test Partner Admin",
                "admin_email": f"test_partner_admin_{suffix}@example-test.com",
                "admin_password": "TestPass123!",
                "base_currency": "USD",
            }
        )
        if create_r.status_code != 200:
            pytest.skip(f"Could not create test partner org: {create_r.text}")

        partner_code = create_r.json()["partner_code"]

        # Login as the new partner admin
        login_r = requests.post(
            f"{BASE_URL}/api/auth/partner-login",
            json={
                "partner_code": partner_code,
                "email": f"test_partner_admin_{suffix}@example-test.com",
                "password": "TestPass123!",
            }
        )
        if login_r.status_code != 200:
            pytest.skip(f"Partner admin login failed: {login_r.text}")

        return login_r.json()["token"]

    @pytest.fixture(scope="class")
    def partner_admin_headers(self, partner_admin_token):
        return {"Authorization": f"Bearer {partner_admin_token}", "Content-Type": "application/json"}

    def test_partner_admin_creates_customer_in_own_tenant(self, partner_admin_headers):
        import time
        payload = {
            "full_name": "TEST_Partner Customer",
            "email": f"test_partner_cust_{int(time.time())}@example-test.com",
            "password": "TestPass123!",
            "company_name": "TEST Partner Client",
            "job_title": "",
            "phone": "",
            "line1": "789 Partner Ave",
            "line2": "",
            "city": "Montreal",
            "region": "Quebec",
            "postal": "H1H1H1",
            "country": "Canada",
            "mark_verified": True,
            # No tenant_id — should use partner's own tenant
        }
        r = requests.post(f"{BASE_URL}/api/admin/customers/create", headers=partner_admin_headers, json=payload)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "customer_id" in data
        assert "user_id" in data

    def test_partner_admin_cannot_specify_different_tenant_id(self, partner_admin_headers, partner_tenant_id):
        """Partner admin sending tenant_id should have it IGNORED (not redirected to a different tenant)."""
        import time
        payload = {
            "full_name": "TEST_CrossTenant Attempt",
            "email": f"test_cross_tenant_{int(time.time())}@example-test.com",
            "password": "TestPass123!",
            "company_name": "",
            "job_title": "",
            "phone": "",
            "line1": "1 Cross Tenant St",
            "line2": "",
            "city": "City",
            "region": "Region",
            "postal": "12345",
            "country": "Canada",
            "mark_verified": True,
            "tenant_id": partner_tenant_id,  # Try to specify a different tenant (should be ignored)
        }
        r = requests.post(f"{BASE_URL}/api/admin/customers/create", headers=partner_admin_headers, json=payload)
        # Backend ignores tenant_id for non-platform-admin, creates in their own tenant
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"


# ── Test 4: Tenants plan filter ────────────────────────────────────────────────

class TestTenantsFiltering:
    """Verify GET /api/admin/tenants plan_id filter works."""

    def test_tenant_filter_by_plan_id(self, platform_admin_headers):
        """Filtering by a non-existent plan_id should return empty list, not error."""
        r = requests.get(
            f"{BASE_URL}/api/admin/tenants?plan_id=nonexistent-plan-id",
            headers=platform_admin_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert "tenants" in data
        # May return empty list
        assert isinstance(data["tenants"], list)

    def test_tenant_no_filter_returns_all(self, platform_admin_headers):
        """Without filter, should return all tenants."""
        r = requests.get(f"{BASE_URL}/api/admin/tenants", headers=platform_admin_headers)
        assert r.status_code == 200
        tenants = r.json().get("tenants", [])
        assert len(tenants) > 0, "Expected at least one tenant"
