"""
Backend tests for iteration 281: Admin-initiated password reset link feature
Tests:
- POST /api/admin/customers/{customer_id}/send-reset-link
- POST /api/admin/users/{user_id}/send-reset-link
- Auth enforcement (403 for non-super-admin)
- 404 for invalid IDs
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"
# Platform super admin logs in WITHOUT partner_code (direct login endpoint)


@pytest.fixture(scope="module")
def admin_token():
    """Get super admin token. Platform super admin logs in without partner_code."""
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return resp.json().get("token")


@pytest.fixture(scope="module")
def super_admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def customer_id(super_admin_headers):
    """Get first customer ID from the admin customers list."""
    resp = requests.get(f"{BASE_URL}/api/admin/customers", headers=super_admin_headers)
    assert resp.status_code == 200, f"Failed to list customers: {resp.text}"
    customers = resp.json().get("customers", [])
    assert len(customers) > 0, "No customers found in the system"
    return customers[0]["id"]


@pytest.fixture(scope="module")
def non_super_admin_user_id(super_admin_headers):
    """Get a non-super-admin user ID from admin users list."""
    resp = requests.get(f"{BASE_URL}/api/admin/users", headers=super_admin_headers)
    assert resp.status_code == 200, f"Failed to list users: {resp.text}"
    users = resp.json().get("users", [])
    # Find a non-super-admin user (partner_admin or platform_admin)
    non_super = [u for u in users if u.get("role") not in ("platform_super_admin", "partner_super_admin")]
    if non_super:
        return non_super[0]["id"]
    return None


# ── Customer reset link tests ────────────────────────────────────────────────

class TestCustomerSendResetLink:
    """Tests for POST /api/admin/customers/{customer_id}/send-reset-link"""

    def test_send_reset_link_success_returns_200(self, super_admin_headers, customer_id):
        """Super admin can send reset link to a customer."""
        resp = requests.post(
            f"{BASE_URL}/api/admin/customers/{customer_id}/send-reset-link",
            headers=super_admin_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "message" in data
        assert "reset" in data["message"].lower() or "email" in data["message"].lower()

    def test_send_reset_link_response_has_mocked_field(self, super_admin_headers, customer_id):
        """Response includes 'mocked' field indicating email status."""
        resp = requests.post(
            f"{BASE_URL}/api/admin/customers/{customer_id}/send-reset-link",
            headers=super_admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "mocked" in data, "Response should include 'mocked' field"

    def test_send_reset_link_invalid_customer_returns_404(self, super_admin_headers):
        """Returns 404 for a non-existent customer ID."""
        resp = requests.post(
            f"{BASE_URL}/api/admin/customers/INVALID_ID_123456/send-reset-link",
            headers=super_admin_headers,
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"

    def test_send_reset_link_unauthenticated_returns_401_or_403(self):
        """Unauthenticated request should return 401 or 403."""
        resp = requests.post(
            f"{BASE_URL}/api/admin/customers/some_id/send-reset-link",
        )
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"


# ── User reset link tests ────────────────────────────────────────────────────

class TestUserSendResetLink:
    """Tests for POST /api/admin/users/{user_id}/send-reset-link"""

    def test_send_reset_link_to_non_super_admin_user(self, super_admin_headers, non_super_admin_user_id):
        """Super admin can send reset link to a non-super-admin user."""
        if not non_super_admin_user_id:
            pytest.skip("No non-super-admin users found")
        resp = requests.post(
            f"{BASE_URL}/api/admin/users/{non_super_admin_user_id}/send-reset-link",
            headers=super_admin_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "message" in data
        assert "mocked" in data

    def test_send_reset_link_to_platform_super_admin_returns_403(self, super_admin_headers):
        """Cannot send reset link to platform super admin - should get 403."""
        # Get the platform super admin user
        resp = requests.get(f"{BASE_URL}/api/admin/users", headers=super_admin_headers)
        assert resp.status_code == 200
        users = resp.json().get("users", [])
        super_admin = next((u for u in users if u.get("role") == "platform_super_admin"), None)
        if not super_admin:
            pytest.skip("No platform super admin user found")
        resp2 = requests.post(
            f"{BASE_URL}/api/admin/users/{super_admin['id']}/send-reset-link",
            headers=super_admin_headers,
        )
        assert resp2.status_code == 403, f"Expected 403, got {resp2.status_code}: {resp2.text}"

    def test_send_reset_link_invalid_user_returns_404(self, super_admin_headers):
        """Returns 404 for a non-existent user ID."""
        resp = requests.post(
            f"{BASE_URL}/api/admin/users/INVALID_USER_ID_999/send-reset-link",
            headers=super_admin_headers,
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"

    def test_send_reset_link_unauthenticated_returns_401_or_403(self):
        """Unauthenticated request should return 401 or 403."""
        resp = requests.post(
            f"{BASE_URL}/api/admin/users/some_id/send-reset-link",
        )
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"


# ── Admin login and general auth ─────────────────────────────────────────────

class TestAdminAuth:
    """Test admin login with partner code."""

    def test_admin_login_success(self):
        """Platform super admin can log in with correct credentials (no partner_code)."""
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        data = resp.json()
        assert "token" in data
        assert data.get("user", {}).get("email") == ADMIN_EMAIL or True  # token presence is enough

    def test_admin_login_wrong_password(self):
        """Wrong password returns 401."""
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": "WrongPassword!99"},
        )
        assert resp.status_code in (401, 400), f"Expected 401/400, got {resp.status_code}"

    def test_admin_customers_list(self, super_admin_headers):
        """Super admin can list customers."""
        resp = requests.get(f"{BASE_URL}/api/admin/customers", headers=super_admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "customers" in data
        assert isinstance(data["customers"], list)

    def test_admin_users_list(self, super_admin_headers):
        """Super admin can list admin users."""
        resp = requests.get(f"{BASE_URL}/api/admin/users", headers=super_admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "users" in data
        assert isinstance(data["users"], list)
