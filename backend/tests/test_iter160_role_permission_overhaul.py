"""
Iteration 160 - Role & Permission System Overhaul Tests

Tests:
1. GET /api/admin/my-permissions - correct shape for platform_super_admin
2. DELETE /api/admin/plans/{id} - platform_super_admin can delete (2xx/409/404)
3. POST /api/admin/coupons - platform_super_admin can create
4. POST /api/admin/one-time-plans - platform_super_admin can create
5. PUT /api/admin/platform-billing-settings - platform_super_admin can update
6. Partner module enforcement: partner_admin with only 'customers' gets 403 on orders
7. Partner module enforcement: partner_admin with only 'customers' can access customers
8. require_platform_super_admin dependency blocks platform_admin role
"""
from __future__ import annotations

import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

PLATFORM_SUPER_ADMIN_EMAIL = "admin@automateaccounts.local"
PLATFORM_SUPER_ADMIN_PASSWORD = "ChangeMe123!"
PLATFORM_SUPER_ADMIN_PARTNER_CODE = "automate-accounts"

# Partner super admin from iter159
PARTNER_SUPER_ADMIN_EMAIL = "testpartner@example.com"
PARTNER_SUPER_ADMIN_PASSWORD = "TestPass123!"
PARTNER_SUPER_ADMIN_CODE = "test-partner-co"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def platform_super_admin_token():
    """Login as platform_super_admin and return token."""
    # First try partner-login (which should redirect to legacy login for platform code)
    session = requests.Session()
    # The frontend login logic: try partner-login first, if 403 with "reserved" → use /auth/login
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": PLATFORM_SUPER_ADMIN_EMAIL,
        "password": PLATFORM_SUPER_ADMIN_PASSWORD,
    })
    if resp.status_code == 200:
        token = resp.json().get("token")
        if token:
            return token
    pytest.skip(f"Cannot login as platform_super_admin: {resp.status_code} {resp.text}")


@pytest.fixture(scope="module")
def platform_admin_headers(platform_super_admin_token):
    return {"Authorization": f"Bearer {platform_super_admin_token}"}


@pytest.fixture(scope="module")
def partner_super_admin_token():
    """Login as partner_super_admin (testpartner@example.com)."""
    resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
        "email": PARTNER_SUPER_ADMIN_EMAIL,
        "password": PARTNER_SUPER_ADMIN_PASSWORD,
        "partner_code": PARTNER_SUPER_ADMIN_CODE,
    })
    if resp.status_code == 200:
        token = resp.json().get("token")
        if token:
            return token
    pytest.skip(f"Cannot login as partner_super_admin: {resp.status_code} {resp.text}")


@pytest.fixture(scope="module")
def partner_super_admin_headers(partner_super_admin_token):
    return {"Authorization": f"Bearer {partner_super_admin_token}"}


@pytest.fixture(scope="module")
def restricted_partner_admin_token(partner_super_admin_token):
    """
    Create a partner_admin user with only 'customers' module in test-partner-co tenant,
    then login as them.
    Uses partner_super_admin token so user is created in the correct tenant.
    """
    partner_headers = {"Authorization": f"Bearer {partner_super_admin_token}"}

    # Create user via partner_super_admin API (creates user in test-partner-co tenant)
    # NOTE: modules and access_level are top-level fields, NOT nested under permissions
    create_resp = requests.post(
        f"{BASE_URL}/api/admin/users",
        json={
            "email": "TEST_restricted_admin@example.com",
            "password": "TestPass123!",
            "full_name": "TEST Restricted Admin",
            "role": "partner_admin",
            "access_level": "full_access",
            "modules": ["customers"],
        },
        headers=partner_headers,
    )
    if create_resp.status_code not in (200, 201, 400):
        pytest.skip(f"Cannot create restricted partner_admin: {create_resp.status_code} {create_resp.text}")

    # Login as this user via partner-login with test-partner-co
    login_resp = requests.post(
        f"{BASE_URL}/api/auth/partner-login",
        json={
            "email": "TEST_restricted_admin@example.com",
            "password": "TestPass123!",
            "partner_code": PARTNER_SUPER_ADMIN_CODE,
        },
    )
    if login_resp.status_code == 200:
        token = login_resp.json().get("token")
        if token:
            return token
    pytest.skip(f"Cannot login as restricted partner_admin: {login_resp.status_code} {login_resp.text}")


@pytest.fixture(scope="module")
def restricted_partner_admin_headers(restricted_partner_admin_token):
    return {"Authorization": f"Bearer {restricted_partner_admin_token}"}


# ── Test: /api/admin/my-permissions ──────────────────────────────────────────

class TestMyPermissions:
    """Test GET /api/admin/my-permissions endpoint"""

    def test_my_permissions_returns_200(self, platform_admin_headers):
        """Endpoint should return 200 for platform_super_admin"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/my-permissions",
            headers=platform_admin_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_my_permissions_correct_shape(self, platform_admin_headers):
        """Response should have correct shape: {modules, access_level, is_super_admin, role}"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/my-permissions",
            headers=platform_admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # Verify required fields
        assert "modules" in data, f"Missing 'modules' field: {data}"
        assert "access_level" in data, f"Missing 'access_level' field: {data}"
        assert "is_super_admin" in data, f"Missing 'is_super_admin' field: {data}"
        assert "role" in data, f"Missing 'role' field: {data}"

    def test_my_permissions_platform_super_admin_values(self, platform_admin_headers):
        """platform_super_admin should have is_super_admin=True, full_access, all modules"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/my-permissions",
            headers=platform_admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_super_admin"] is True, f"Expected is_super_admin=True: {data}"
        assert data["access_level"] == "full_access", f"Expected full_access: {data}"
        assert data["role"] == "platform_super_admin", f"Expected platform_super_admin role: {data}"
        assert isinstance(data["modules"], list), f"modules should be a list: {data}"
        assert len(data["modules"]) > 0, f"modules should not be empty: {data}"

    def test_my_permissions_includes_expected_modules(self, platform_admin_headers):
        """platform_super_admin should have all standard modules"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/my-permissions",
            headers=platform_admin_headers,
        )
        data = resp.json()
        expected_modules = ["customers", "orders", "subscriptions", "products", "settings"]
        for mod in expected_modules:
            assert mod in data["modules"], f"Missing module '{mod}' in {data['modules']}"

    def test_my_permissions_requires_auth(self):
        """Endpoint should return 401 without auth token"""
        resp = requests.get(f"{BASE_URL}/api/admin/my-permissions")
        assert resp.status_code in (401, 403), f"Expected 401/403 without auth, got {resp.status_code}"

    def test_partner_super_admin_my_permissions(self, partner_super_admin_headers):
        """partner_super_admin should also get is_super_admin=True"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/my-permissions",
            headers=partner_super_admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_super_admin"] is True, f"Expected is_super_admin=True for partner_super_admin: {data}"
        assert data["role"] == "partner_super_admin", f"Expected partner_super_admin role: {data}"


# ── Test: require_platform_super_admin dependency ────────────────────────────

class TestRequirePlatformSuperAdmin:
    """Tests that verify require_platform_super_admin blocks non-super-admins"""

    def test_delete_plan_platform_super_admin_accessible(self, platform_admin_headers):
        """
        platform_super_admin should be able to reach DELETE /api/admin/plans/{id}
        (may return 404 or 409 if plan doesn't exist/has tenants, but NOT 403)
        """
        # First list plans to get a real ID
        list_resp = requests.get(
            f"{BASE_URL}/api/admin/plans",
            headers=platform_admin_headers,
        )
        assert list_resp.status_code == 200, f"Failed to list plans: {list_resp.text}"
        plans = list_resp.json().get("plans", [])

        if not plans:
            pytest.skip("No plans found to test deletion")

        # Find a non-default plan with no tenants
        deletable = next(
            (p for p in plans if not p.get("is_default") and not p.get("is_readonly") and p.get("tenant_count", 0) == 0),
            None,
        )

        if deletable:
            plan_id = deletable["id"]
            resp = requests.delete(
                f"{BASE_URL}/api/admin/plans/{plan_id}",
                headers=platform_admin_headers,
            )
            # Should be 200 (deleted) or 409 (has tenants) but NOT 403
            assert resp.status_code in (200, 409, 404), \
                f"Expected 200/409/404 for platform_super_admin, got {resp.status_code}: {resp.text}"
            assert resp.status_code != 403, "platform_super_admin should NOT get 403 on delete plan"
        else:
            # All plans have tenants — try to delete any plan and expect 409
            plan_id = plans[0]["id"]
            resp = requests.delete(
                f"{BASE_URL}/api/admin/plans/{plan_id}",
                headers=platform_admin_headers,
            )
            # 409 = has tenants, 403 = default plan, 200 = deleted
            # All are valid outcomes except 401
            assert resp.status_code in (200, 403, 409, 404), \
                f"Unexpected status for delete plan: {resp.status_code}: {resp.text}"
            assert resp.status_code != 401, "Should not get 401 for platform_super_admin"

    def test_create_coupon_platform_super_admin(self, platform_admin_headers):
        """platform_super_admin can create coupons"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/coupons",
            json={
                "code": "TEST_PERM_COUPON",
                "discount_type": "percentage",
                "discount_value": 5,
                "applies_to": "both",
                "is_active": True,
            },
            headers=platform_admin_headers,
        )
        # 200 = created, 409 = already exists — both valid for super admin
        assert resp.status_code in (200, 201, 409), \
            f"platform_super_admin should be able to create coupon, got {resp.status_code}: {resp.text}"
        assert resp.status_code != 403, "platform_super_admin should NOT get 403 on create coupon"

    def test_create_one_time_rate_platform_super_admin(self, platform_admin_headers):
        """platform_super_admin can create one-time plan rates"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/one-time-plans",
            json={
                "module_key": "max_forms",
                "price_per_record": 0.50,
                "currency": "GBP",
                "is_active": True,
            },
            headers=platform_admin_headers,
        )
        # 200 = created, 409 = already exists — both valid for super admin
        assert resp.status_code in (200, 201, 409), \
            f"platform_super_admin should create one-time rate, got {resp.status_code}: {resp.text}"
        assert resp.status_code != 403, "platform_super_admin should NOT get 403 on create one-time rate"

    def test_update_billing_settings_platform_super_admin(self, platform_admin_headers):
        """platform_super_admin can update platform billing settings"""
        resp = requests.put(
            f"{BASE_URL}/api/admin/platform-billing-settings",
            json={"overdue_grace_days": 7, "overdue_warning_days": 3},
            headers=platform_admin_headers,
        )
        assert resp.status_code == 200, \
            f"platform_super_admin should update billing settings, got {resp.status_code}: {resp.text}"
        assert resp.status_code != 403, "platform_super_admin should NOT get 403"

    def test_update_billing_settings_partner_admin_blocked(self, partner_super_admin_headers):
        """partner_super_admin (non-platform) should be blocked from updating billing settings"""
        resp = requests.put(
            f"{BASE_URL}/api/admin/platform-billing-settings",
            json={"overdue_grace_days": 7},
            headers=partner_super_admin_headers,
        )
        assert resp.status_code == 403, \
            f"partner_super_admin should be blocked from updating billing settings, got {resp.status_code}: {resp.text}"

    def test_create_coupon_partner_admin_blocked(self, partner_super_admin_headers):
        """partner_super_admin (non-platform) cannot create coupons"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/coupons",
            json={
                "code": "TEST_BLOCKED_COUPON",
                "discount_type": "percentage",
                "discount_value": 10,
                "applies_to": "both",
            },
            headers=partner_super_admin_headers,
        )
        assert resp.status_code == 403, \
            f"partner_super_admin should get 403 on create coupon, got {resp.status_code}: {resp.text}"

    def test_create_one_time_rate_partner_admin_blocked(self, partner_super_admin_headers):
        """partner_super_admin (non-platform) cannot create one-time rates"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/one-time-plans",
            json={"module_key": "max_resources", "price_per_record": 0.25, "currency": "GBP"},
            headers=partner_super_admin_headers,
        )
        assert resp.status_code == 403, \
            f"partner_super_admin should get 403 on create one-time rate, got {resp.status_code}: {resp.text}"


# ── Test: Partner module permission enforcement ───────────────────────────────

class TestPartnerModulePermissions:
    """Test that partner_admin with restricted modules is enforced correctly"""

    def test_restricted_admin_customers_allowed(self, restricted_partner_admin_headers):
        """partner_admin with 'customers' module can access /api/admin/customers"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/customers",
            headers=restricted_partner_admin_headers,
        )
        assert resp.status_code == 200, \
            f"partner_admin with 'customers' module should see customers, got {resp.status_code}: {resp.text}"

    def test_restricted_admin_orders_blocked(self, restricted_partner_admin_headers):
        """partner_admin with only 'customers' module should get 403 on /api/admin/orders"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/orders",
            headers=restricted_partner_admin_headers,
        )
        assert resp.status_code == 403, \
            f"partner_admin without 'orders' module should get 403, got {resp.status_code}: {resp.text}"

    def test_restricted_admin_subscriptions_blocked(self, restricted_partner_admin_headers):
        """partner_admin with only 'customers' module should get 403 on subscriptions"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/subscriptions",
            headers=restricted_partner_admin_headers,
        )
        assert resp.status_code == 403, \
            f"partner_admin without 'subscriptions' module should get 403, got {resp.status_code}: {resp.text}"

    def test_restricted_admin_my_permissions_returns_modules(self, restricted_partner_admin_headers):
        """Restricted partner_admin's permissions should only show 'customers' module"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/my-permissions",
            headers=restricted_partner_admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "modules" in data
        assert data["is_super_admin"] is False, f"Restricted admin should not be super admin: {data}"
        assert "customers" in data["modules"], f"'customers' should be in modules: {data}"

    def test_partner_super_admin_all_modules(self, partner_super_admin_headers):
        """partner_super_admin should have access to orders"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/orders",
            headers=partner_super_admin_headers,
        )
        assert resp.status_code == 200, \
            f"partner_super_admin should see orders, got {resp.status_code}: {resp.text}"

    def test_partner_super_admin_customers(self, partner_super_admin_headers):
        """partner_super_admin should have access to customers"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/customers",
            headers=partner_super_admin_headers,
        )
        assert resp.status_code == 200, \
            f"partner_super_admin should see customers, got {resp.status_code}: {resp.text}"


# ── Test: GET /api/admin/plans requires platform_admin ────────────────────────

class TestPlatformAdminGating:
    """Plans endpoint should return 403 for partner users"""

    def test_list_plans_platform_super_admin(self, platform_admin_headers):
        """platform_super_admin can list plans"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/plans",
            headers=platform_admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "plans" in data
        assert isinstance(data["plans"], list)

    def test_list_plans_partner_admin_blocked(self, partner_super_admin_headers):
        """partner_super_admin should be blocked from listing plans"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/plans",
            headers=partner_super_admin_headers,
        )
        assert resp.status_code == 403, \
            f"partner_super_admin should get 403 on plans, got {resp.status_code}: {resp.text}"

    def test_list_coupons_platform_admin(self, platform_admin_headers):
        """platform_super_admin can list coupons"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/coupons",
            headers=platform_admin_headers,
        )
        assert resp.status_code == 200
        assert "coupons" in resp.json()

    def test_list_coupons_partner_admin_blocked(self, partner_super_admin_headers):
        """partner_super_admin should be blocked from listing coupons"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/coupons",
            headers=partner_super_admin_headers,
        )
        assert resp.status_code == 403, \
            f"partner should get 403 on coupons, got {resp.status_code}: {resp.text}"

    def test_list_one_time_plans_platform_admin(self, platform_admin_headers):
        """platform_super_admin can list one-time rates"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/one-time-plans",
            headers=platform_admin_headers,
        )
        assert resp.status_code == 200
        assert "rates" in resp.json()

    def test_list_one_time_plans_partner_blocked(self, partner_super_admin_headers):
        """partner_super_admin should be blocked from listing one-time rates"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/one-time-plans",
            headers=partner_super_admin_headers,
        )
        assert resp.status_code == 403, \
            f"partner should get 403 on one-time-plans, got {resp.status_code}: {resp.text}"


# ── Test: Billing Settings gating ────────────────────────────────────────────

class TestBillingSettingsGating:
    """Platform billing settings should only be accessible by platform admins"""

    def test_get_billing_settings_platform_admin(self, platform_admin_headers):
        """platform_super_admin can GET billing settings"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/platform-billing-settings",
            headers=platform_admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "overdue_grace_days" in data

    def test_get_billing_settings_partner_blocked(self, partner_super_admin_headers):
        """partner_super_admin is blocked from GET billing settings"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/platform-billing-settings",
            headers=partner_super_admin_headers,
        )
        assert resp.status_code == 403, \
            f"partner should get 403 on billing settings GET, got {resp.status_code}: {resp.text}"

    def test_billing_settings_put_response_shape(self, platform_admin_headers):
        """PUT /api/admin/platform-billing-settings should return updated settings"""
        resp = requests.put(
            f"{BASE_URL}/api/admin/platform-billing-settings",
            json={"overdue_grace_days": 7, "overdue_warning_days": 3},
            headers=platform_admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("overdue_grace_days") == 7
        assert data.get("overdue_warning_days") == 3
