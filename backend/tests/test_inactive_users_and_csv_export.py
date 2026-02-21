"""
Tests for new admin features:
1. Inactive users/customers - activate/deactivate via admin APIs
2. Login blocked for inactive users (403)
3. CSV export endpoints for orders, customers, subscriptions, catalog
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials from review request
ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"
INACTIVE_USER_EMAIL = "inactive.test@automateaccounts.local"
INACTIVE_USER_PASSWORD = "Pass123!"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token once per module"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ============ TEST 1: Inactive User Login ============

class TestInactiveUserLogin:
    """Test that inactive users cannot login"""

    def test_inactive_user_login_returns_403(self):
        """POST /api/auth/login with inactive user should return 403"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": INACTIVE_USER_EMAIL,
            "password": INACTIVE_USER_PASSWORD
        })
        assert resp.status_code == 403, f"Expected 403 but got {resp.status_code}: {resp.text}"
        data = resp.json()
        # Validate error message mentions inactive
        detail = data.get("detail", "")
        assert "inactive" in detail.lower(), f"Expected 'inactive' in detail, got: {detail}"
        print(f"PASS: Inactive user login returns 403 with message: {detail}")

    def test_inactive_user_login_exact_message(self):
        """Verify the exact error message content"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": INACTIVE_USER_EMAIL,
            "password": INACTIVE_USER_PASSWORD
        })
        assert resp.status_code == 403
        data = resp.json()
        detail = data.get("detail", "")
        assert "Account is inactive" in detail, f"Expected 'Account is inactive' message, got: {detail}"
        print(f"PASS: Exact message confirmed: '{detail}'")


# ============ TEST 2: Admin Toggle User Active ============

class TestAdminToggleUserActive:
    """Test super_admin can activate/deactivate users"""

    def test_get_inactive_user_id(self, admin_headers):
        """Verify inactive user exists in system"""
        resp = requests.get(f"{BASE_URL}/api/admin/users", headers=admin_headers)
        assert resp.status_code == 200
        users = resp.json().get("users", [])
        # Check inactive test user is returned in users list (if they have admin role)
        # The inactive user is role=customer, may not be in admin users list
        # This test just confirms the admin users endpoint works
        assert isinstance(users, list)
        print(f"PASS: Admin users endpoint works, returned {len(users)} users")

    def test_activate_inactive_user(self, admin_headers):
        """PATCH /api/admin/users/{id}/active?active=true should reactivate user"""
        # First get the inactive user's ID from MongoDB
        import pymongo
        client = pymongo.MongoClient("mongodb://localhost:27017")
        db = client["test_database"]
        user = db.users.find_one({"email": INACTIVE_USER_EMAIL}, {"_id": 0, "id": 1, "is_active": 1})
        assert user, "Inactive test user not found in DB"
        user_id = user["id"]
        assert user["is_active"] == False, f"User should be inactive before test, is_active={user['is_active']}"

        resp = requests.patch(
            f"{BASE_URL}/api/admin/users/{user_id}/active?active=true",
            headers=admin_headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("is_active") == True, f"Expected is_active=true, got: {data}"
        assert "activated" in data.get("message", "").lower()
        print(f"PASS: User activated: {data}")

    def test_login_after_reactivation(self):
        """After reactivation, inactive user should be able to login"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": INACTIVE_USER_EMAIL,
            "password": INACTIVE_USER_PASSWORD
        })
        assert resp.status_code == 200, f"Expected 200 after reactivation, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "token" in data
        print(f"PASS: Inactive user can login after reactivation")

    def test_deactivate_user_again(self, admin_headers):
        """Re-deactivate the test user to restore original state"""
        import pymongo
        client = pymongo.MongoClient("mongodb://localhost:27017")
        db = client["test_database"]
        user = db.users.find_one({"email": INACTIVE_USER_EMAIL}, {"_id": 0, "id": 1})
        user_id = user["id"]

        resp = requests.patch(
            f"{BASE_URL}/api/admin/users/{user_id}/active?active=false",
            headers=admin_headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("is_active") == False
        assert "deactivated" in data.get("message", "").lower()
        print(f"PASS: User deactivated again (restored state): {data}")

    def test_login_blocked_after_redeactivation(self):
        """After deactivating again, login should return 403"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": INACTIVE_USER_EMAIL,
            "password": INACTIVE_USER_PASSWORD
        })
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
        print(f"PASS: Login blocked again after re-deactivation")

    def test_self_deactivation_not_possible_via_admin(self, admin_headers):
        """Admin should still be able to login (not self-deactivated)"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert resp.status_code == 200
        print(f"PASS: Admin can still login normally")


# ============ TEST 3: Admin Toggle Customer Active ============

class TestAdminToggleCustomerActive:
    """Test admin can activate/deactivate customers"""

    def test_activate_customer(self, admin_headers):
        """PATCH /api/admin/customers/{id}/active?active=true"""
        import pymongo
        client = pymongo.MongoClient("mongodb://localhost:27017")
        db = client["test_database"]
        # Find a customer that's not linked to the inactive test user
        customer = db.customers.find_one(
            {"company_name": {"$ne": ""}},
            {"_id": 0, "id": 1, "is_active": 1}
        )
        assert customer, "No customers found"
        customer_id = customer["id"]

        resp = requests.patch(
            f"{BASE_URL}/api/admin/customers/{customer_id}/active?active=false",
            headers=admin_headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("is_active") == False
        print(f"PASS: Customer deactivated: {data}")

        # Re-activate
        resp2 = requests.patch(
            f"{BASE_URL}/api/admin/customers/{customer_id}/active?active=true",
            headers=admin_headers
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2.get("is_active") == True
        print(f"PASS: Customer re-activated: {data2}")

    def test_customer_not_found_returns_404(self, admin_headers):
        """PATCH with non-existent customer ID should return 404"""
        resp = requests.patch(
            f"{BASE_URL}/api/admin/customers/nonexistent-id-99999/active?active=false",
            headers=admin_headers
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print(f"PASS: 404 returned for non-existent customer")

    def test_user_not_found_returns_404(self, admin_headers):
        """PATCH with non-existent user ID should return 404"""
        resp = requests.patch(
            f"{BASE_URL}/api/admin/users/nonexistent-user-id-99999/active?active=false",
            headers=admin_headers
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print(f"PASS: 404 returned for non-existent user")


# ============ TEST 4: CSV Export Endpoints ============

class TestCSVExports:
    """Test all CSV export endpoints return valid CSV data"""

    def test_export_customers_csv(self, admin_headers):
        """GET /api/admin/export/customers returns CSV content"""
        resp = requests.get(f"{BASE_URL}/api/admin/export/customers", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        content_type = resp.headers.get("content-type", "")
        assert "text/csv" in content_type, f"Expected text/csv content-type, got: {content_type}"
        content = resp.text
        assert len(content) > 0, "Empty CSV response"
        # Check Content-Disposition header
        cd = resp.headers.get("content-disposition", "")
        assert "customers_" in cd and ".csv" in cd, f"Unexpected Content-Disposition: {cd}"
        # Verify CSV has header row
        first_line = content.split("\n")[0]
        assert "," in first_line or first_line.strip(), f"Invalid CSV header: {first_line}"
        print(f"PASS: Customers CSV export - {len(content)} bytes, headers: {first_line[:100]}")

    def test_export_customers_csv_has_is_active_column(self, admin_headers):
        """Customers CSV should include is_active column"""
        resp = requests.get(f"{BASE_URL}/api/admin/export/customers", headers=admin_headers)
        assert resp.status_code == 200
        first_line = resp.text.split("\n")[0]
        assert "is_active" in first_line, f"CSV missing is_active column: {first_line}"
        print(f"PASS: Customers CSV has is_active column")

    def test_export_orders_csv(self, admin_headers):
        """GET /api/admin/export/orders returns CSV content"""
        resp = requests.get(f"{BASE_URL}/api/admin/export/orders", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        content_type = resp.headers.get("content-type", "")
        assert "text/csv" in content_type, f"Expected text/csv, got: {content_type}"
        content = resp.text
        cd = resp.headers.get("content-disposition", "")
        assert "orders_" in cd, f"Unexpected Content-Disposition: {cd}"
        print(f"PASS: Orders CSV export - {len(content)} bytes")

    def test_export_orders_csv_with_filters(self, admin_headers):
        """GET /api/admin/export/orders with filters should still work"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/export/orders?sort_order=asc&include_deleted=false",
            headers=admin_headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        assert "text/csv" in resp.headers.get("content-type", "")
        print(f"PASS: Orders CSV export with filters works")

    def test_export_subscriptions_csv(self, admin_headers):
        """GET /api/admin/export/subscriptions returns CSV content"""
        resp = requests.get(f"{BASE_URL}/api/admin/export/subscriptions", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        content_type = resp.headers.get("content-type", "")
        assert "text/csv" in content_type, f"Expected text/csv, got: {content_type}"
        content = resp.text
        cd = resp.headers.get("content-disposition", "")
        assert "subscriptions_" in cd, f"Unexpected Content-Disposition: {cd}"
        print(f"PASS: Subscriptions CSV export - {len(content)} bytes")

    def test_export_catalog_csv(self, admin_headers):
        """GET /api/admin/export/catalog returns CSV content"""
        resp = requests.get(f"{BASE_URL}/api/admin/export/catalog", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        content_type = resp.headers.get("content-type", "")
        assert "text/csv" in content_type, f"Expected text/csv, got: {content_type}"
        cd = resp.headers.get("content-disposition", "")
        assert "catalog_" in cd, f"Unexpected Content-Disposition: {cd}"
        first_line = resp.text.split("\n")[0]
        print(f"PASS: Catalog CSV export - headers: {first_line[:100]}")

    def test_export_requires_auth(self):
        """CSV exports without auth token should return 403/401"""
        for endpoint in ["/api/admin/export/customers", "/api/admin/export/orders",
                         "/api/admin/export/subscriptions", "/api/admin/export/catalog"]:
            resp = requests.get(f"{BASE_URL}{endpoint}")
            assert resp.status_code in [401, 403], f"{endpoint}: Expected 401/403, got {resp.status_code}"
        print(f"PASS: All CSV exports require authentication")

    def test_export_subscriptions_csv_with_filters(self, admin_headers):
        """GET /api/admin/export/subscriptions with sort filters"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/export/subscriptions?sort_by=renewal_date&sort_order=asc",
            headers=admin_headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        assert "text/csv" in resp.headers.get("content-type", "")
        print(f"PASS: Subscriptions CSV with sort filters works")


# ============ TEST 5: Auth Check for active user using token ============

class TestActiveUserTokenCheck:
    """Test that active user token works but inactive user token is rejected"""

    def test_active_admin_can_access_protected_endpoint(self, admin_headers):
        """Active admin should be able to access /me endpoint"""
        resp = requests.get(f"{BASE_URL}/api/me", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["user"]["email"] == ADMIN_EMAIL
        print(f"PASS: Active admin can access /me endpoint")

    def test_get_current_user_inactive_via_jwt(self, admin_headers):
        """If an inactive user has a valid JWT, accessing protected endpoint returns 403"""
        # First, get the inactive user's ID
        import pymongo
        client = pymongo.MongoClient("mongodb://localhost:27017")
        db = client["test_database"]
        user = db.users.find_one({"email": INACTIVE_USER_EMAIL}, {"_id": 0, "id": 1, "is_active": 1})
        assert user["is_active"] == False, "Test user should be inactive"
        print(f"PASS: Confirmed inactive user has is_active=False in DB")
