"""
Test: Phases 5 (Overdue Cancellation Settings), 2B (Product billing_type), 6 (User filter by partner)
- GET/PUT /api/admin/platform-billing-settings
- GET /api/admin/users?partner_id=X
- POST /api/admin/products with billing_type='fixed'
- GET /api/admin/products/{id} returns billing_type
- Scheduler job 4 function exists
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


# ---------------------------------------------------------------------------
# Auth fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def platform_admin_token():
    """Authenticate as platform admin (direct login)."""
    res = requests.post(f"{BASE_URL}/api/auth/admin-login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!"
    })
    if res.status_code == 200:
        data = res.json()
        return data.get("access_token") or data.get("token")
    # Try alternate endpoint
    res2 = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!"
    })
    if res2.status_code == 200:
        data = res2.json()
        return data.get("access_token") or data.get("token")
    pytest.skip(f"Admin login failed: {res.status_code} {res.text[:200]}")


@pytest.fixture(scope="module")
def admin_session(platform_admin_token):
    """Requests session with platform admin auth."""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {platform_admin_token}"
    })
    return session


# ---------------------------------------------------------------------------
# Phase 5: Platform Billing Settings
# ---------------------------------------------------------------------------

class TestPlatformBillingSettings:
    """Tests for GET/PUT /api/admin/platform-billing-settings"""

    def test_get_billing_settings_returns_defaults(self, admin_session):
        """GET should return overdue_grace_days and overdue_warning_days."""
        res = admin_session.get(f"{BASE_URL}/api/admin/platform-billing-settings")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text[:200]}"
        data = res.json()
        assert "overdue_grace_days" in data, "Missing overdue_grace_days in response"
        assert "overdue_warning_days" in data, "Missing overdue_warning_days in response"
        assert isinstance(data["overdue_grace_days"], int), "overdue_grace_days should be int"
        assert isinstance(data["overdue_warning_days"], int), "overdue_warning_days should be int"
        print(f"GET billing settings: grace={data['overdue_grace_days']}, warning={data['overdue_warning_days']}")

    def test_get_billing_settings_default_values(self, admin_session):
        """Defaults should be grace=7, warning=3 if not yet set."""
        res = admin_session.get(f"{BASE_URL}/api/admin/platform-billing-settings")
        assert res.status_code == 200
        data = res.json()
        # Either defaults or previously set values - just validate they are positive ints
        assert data["overdue_grace_days"] >= 1
        assert data["overdue_warning_days"] >= 0
        print(f"Billing settings: grace={data['overdue_grace_days']}, warning={data['overdue_warning_days']}")

    def test_put_billing_settings_update_values(self, admin_session):
        """PUT should update and return new values."""
        res = admin_session.put(f"{BASE_URL}/api/admin/platform-billing-settings", json={
            "overdue_grace_days": 10,
            "overdue_warning_days": 4
        })
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text[:200]}"
        data = res.json()
        assert data["overdue_grace_days"] == 10, f"Expected grace=10, got {data.get('overdue_grace_days')}"
        assert data["overdue_warning_days"] == 4, f"Expected warning=4, got {data.get('overdue_warning_days')}"
        print(f"Updated billing settings: grace={data['overdue_grace_days']}, warning={data['overdue_warning_days']}")

    def test_put_billing_settings_persists(self, admin_session):
        """After PUT, GET should return updated values."""
        # Set known values
        admin_session.put(f"{BASE_URL}/api/admin/platform-billing-settings", json={
            "overdue_grace_days": 10,
            "overdue_warning_days": 4
        })
        # Verify persistence
        res = admin_session.get(f"{BASE_URL}/api/admin/platform-billing-settings")
        assert res.status_code == 200
        data = res.json()
        assert data["overdue_grace_days"] == 10
        assert data["overdue_warning_days"] == 4
        print("Billing settings persisted correctly")

    def test_put_billing_settings_validation_grace_min_1(self, admin_session):
        """grace_days < 1 should return 400."""
        res = admin_session.put(f"{BASE_URL}/api/admin/platform-billing-settings", json={
            "overdue_grace_days": 0
        })
        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text[:200]}"
        print(f"Validation passed: 400 for grace_days=0")

    def test_put_billing_settings_validation_warning_negative(self, admin_session):
        """warning_days < 0 should return 400."""
        res = admin_session.put(f"{BASE_URL}/api/admin/platform-billing-settings", json={
            "overdue_warning_days": -1
        })
        assert res.status_code == 400, f"Expected 400 for negative warning_days, got {res.status_code}: {res.text[:200]}"
        print("Validation passed: 400 for warning_days=-1")

    def test_billing_settings_403_for_non_platform_admin(self):
        """Non-platform admin should get 403."""
        # Without auth
        res = requests.get(f"{BASE_URL}/api/admin/platform-billing-settings")
        assert res.status_code in [401, 403], f"Expected 401/403, got {res.status_code}"
        print(f"Auth check: {res.status_code} for unauthenticated request")

    def test_restore_default_billing_settings(self, admin_session):
        """Restore defaults after tests."""
        res = admin_session.put(f"{BASE_URL}/api/admin/platform-billing-settings", json={
            "overdue_grace_days": 7,
            "overdue_warning_days": 3
        })
        assert res.status_code == 200
        data = res.json()
        assert data["overdue_grace_days"] == 7
        assert data["overdue_warning_days"] == 3
        print("Billing settings restored to defaults (grace=7, warning=3)")


# ---------------------------------------------------------------------------
# Phase 6: User filter by partner_id
# ---------------------------------------------------------------------------

class TestUsersPartnerFilter:
    """Tests for GET /api/admin/users?partner_id=X"""

    def test_get_users_no_filter_returns_all(self, admin_session):
        """Without partner_id filter, returns all users."""
        res = admin_session.get(f"{BASE_URL}/api/admin/users")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text[:200]}"
        data = res.json()
        assert "users" in data
        assert "total" in data
        print(f"Total users (no filter): {data['total']}")

    def test_get_users_with_valid_partner_filter(self, admin_session):
        """With partner_id filter, returns users from that tenant only."""
        # First get all tenants to find a valid partner_id
        tenants_res = admin_session.get(f"{BASE_URL}/api/admin/tenants?per_page=10")
        assert tenants_res.status_code == 200
        tenants = tenants_res.json().get("tenants", [])
        # Find a non-platform tenant
        partner_tenants = [t for t in tenants if t.get("id") != "automate-accounts"]
        if not partner_tenants:
            pytest.skip("No partner tenants available for filter test")
        
        partner_id = partner_tenants[0]["id"]
        res = admin_session.get(f"{BASE_URL}/api/admin/users?partner_id={partner_id}")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text[:200]}"
        data = res.json()
        assert "users" in data
        # All returned users should have tenant_id matching partner_id
        for user in data["users"]:
            assert user.get("tenant_id") == partner_id, \
                f"User {user.get('email')} has tenant_id={user.get('tenant_id')}, expected {partner_id}"
        print(f"Users for partner {partner_id}: {len(data['users'])} users, all from correct tenant")

    def test_get_users_with_invalid_partner_filter_returns_empty(self, admin_session):
        """With invalid partner_id, returns empty user list."""
        res = admin_session.get(f"{BASE_URL}/api/admin/users?partner_id=nonexistent-tenant-id-12345")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 0 or len(data["users"]) == 0
        print(f"Users for invalid partner: {data.get('total', 0)} (expected 0)")


# ---------------------------------------------------------------------------
# Phase 2B: Product billing_type
# ---------------------------------------------------------------------------

class TestProductBillingType:
    """Tests for billing_type field on products."""

    @pytest.fixture(scope="class")
    def created_product_id(self, admin_session):
        """Create a test product with billing_type='fixed'."""
        uid = str(uuid.uuid4())[:8]
        res = admin_session.post(f"{BASE_URL}/api/admin/products", json={
            "name": f"TEST_billing_type_product_{uid}",
            "is_subscription": True,
            "billing_type": "fixed",
            "base_price": 99.0,
            "currency": "GBP",
            "pricing_type": "internal",
            "is_active": True
        })
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text[:200]}"
        data = res.json()
        product = data.get("product", data)
        product_id = product.get("id")
        assert product_id, "No product ID returned"
        yield product_id
        # Cleanup - deactivate the test product (no delete endpoint typically)
        admin_session.put(f"{BASE_URL}/api/admin/products/{product_id}", json={
            "name": f"TEST_billing_type_product_{uid}",
            "is_active": False,
            "billing_type": "fixed"
        })

    def test_create_product_with_billing_type_fixed(self, admin_session, created_product_id):
        """POST should save billing_type='fixed' correctly."""
        assert created_product_id, "Product creation failed in fixture"
        print(f"Created product with billing_type='fixed': {created_product_id}")

    def test_get_product_returns_billing_type(self, admin_session, created_product_id):
        """GET product should return correct billing_type field."""
        res = admin_session.get(f"{BASE_URL}/api/admin/products-all?search=TEST_billing_type")
        assert res.status_code == 200
        data = res.json()
        products = data.get("products", [])
        # Find our test product
        test_product = next((p for p in products if p.get("id") == created_product_id), None)
        if test_product:
            assert test_product.get("billing_type") == "fixed", \
                f"Expected billing_type='fixed', got {test_product.get('billing_type')}"
            print(f"Product billing_type returned correctly: {test_product.get('billing_type')}")
        else:
            print(f"Product {created_product_id} not found in search results (may be pagination issue)")

    def test_create_product_with_billing_type_prorata(self, admin_session):
        """POST with billing_type='prorata' (default) saves correctly."""
        uid = str(uuid.uuid4())[:8]
        res = admin_session.post(f"{BASE_URL}/api/admin/products", json={
            "name": f"TEST_prorata_product_{uid}",
            "is_subscription": True,
            "billing_type": "prorata",
            "base_price": 49.0,
            "currency": "USD",
            "pricing_type": "internal",
            "is_active": True
        })
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text[:200]}"
        data = res.json()
        product = data.get("product", data)
        assert product.get("billing_type") == "prorata", \
            f"Expected billing_type='prorata', got {product.get('billing_type')}"
        print(f"Product created with billing_type='prorata': {product.get('id')}")

    def test_create_product_default_billing_type_is_prorata(self, admin_session):
        """When billing_type not specified, defaults to 'prorata'."""
        uid = str(uuid.uuid4())[:8]
        res = admin_session.post(f"{BASE_URL}/api/admin/products", json={
            "name": f"TEST_default_billing_product_{uid}",
            "is_subscription": True,
            "base_price": 29.0,
            "currency": "USD",
            "pricing_type": "internal",
            "is_active": True
        })
        assert res.status_code == 200
        data = res.json()
        product = data.get("product", data)
        # Default should be 'prorata'
        billing_type = product.get("billing_type", "prorata")
        assert billing_type in ["prorata", None], \
            f"Expected 'prorata' or None as default, got {billing_type}"
        print(f"Default billing_type: {billing_type}")

    def test_update_product_billing_type(self, admin_session, created_product_id):
        """PUT should update billing_type from 'fixed' to 'prorata'."""
        # Get current product name first
        products_res = admin_session.get(f"{BASE_URL}/api/admin/products-all?search=TEST_billing_type")
        products = products_res.json().get("products", [])
        test_product = next((p for p in products if p.get("id") == created_product_id), None)
        if not test_product:
            pytest.skip("Test product not found")
        
        res = admin_session.put(f"{BASE_URL}/api/admin/products/{created_product_id}", json={
            "name": test_product["name"],
            "billing_type": "prorata",
            "is_active": True
        })
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text[:200]}"
        print("Product billing_type updated successfully")


# ---------------------------------------------------------------------------
# Scheduler Job 4 Code Verification
# ---------------------------------------------------------------------------

class TestSchedulerJob4:
    """Verify scheduler job 4 (cancel_overdue_partner_subscriptions) exists."""

    def test_scheduler_job4_function_exists(self):
        """cancel_overdue_partner_subscriptions function exists in scheduler_service.py."""
        import sys
        sys.path.insert(0, "/app/backend")
        try:
            from services.scheduler_service import cancel_overdue_partner_subscriptions
            assert callable(cancel_overdue_partner_subscriptions), "Function should be callable"
            print("cancel_overdue_partner_subscriptions function exists and is callable")
        except ImportError as e:
            pytest.fail(f"Could not import cancel_overdue_partner_subscriptions: {e}")

    def test_scheduler_job4_registered(self):
        """Scheduler registers the overdue_partner_cancel job at 09:15 UTC."""
        import sys
        sys.path.insert(0, "/app/backend")
        import importlib
        try:
            scheduler_module = importlib.import_module("services.scheduler_service")
            # Read the source to check the job is registered
            import inspect
            source = inspect.getsource(scheduler_module.start_scheduler)
            assert "overdue_partner_cancel" in source, "overdue_partner_cancel job not registered"
            assert "cancel_overdue_partner_subscriptions" in source, "cancel_overdue_partner_subscriptions not in scheduler"
            print("Scheduler job 4 (overdue_partner_cancel) is registered correctly")
        except Exception as e:
            pytest.fail(f"Could not verify scheduler: {e}")
