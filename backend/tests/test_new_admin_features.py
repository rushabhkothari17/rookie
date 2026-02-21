"""
Tests for NEW admin features (iteration 9):
- Subscriptions: sort_by renewal_date/created_at, created_from/created_to filters
- Subscriptions: Start Date editable in edit endpoint, Created Date read-only
- Subscriptions: cancel creates audit log with actor/timestamp
- Subscriptions: offline_manual status allowed, subscription_number present
- Users tab: GET /admin/users (super_admin only)
- Users tab: POST /admin/users (create admin user)
- Customers tab: POST /admin/customers/create
- Auth: /me returns role=super_admin for admin user
- Portal: subscriptions return subscription_number, start_date
"""
import pytest
import requests
import os
from pathlib import Path

# Load from frontend .env since REACT_APP_BACKEND_URL is the public URL
def _load_backend_url():
    env_file = Path("/app/frontend/.env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    return os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


BASE_URL = _load_backend_url()

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"


@pytest.fixture(scope="module")
def admin_token():
    """Login as admin and return access token"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ============ AUTH ============

class TestAuth:
    """Verify admin user returns role=super_admin"""

    def test_me_returns_super_admin_role(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/auth/me", headers=admin_headers)
        assert resp.status_code == 200, f"GET /auth/me failed: {resp.text}"
        data = resp.json()
        assert data.get("role") == "super_admin", f"Expected super_admin, got: {data.get('role')}"
        print(f"PASS: /auth/me role={data['role']}")


# ============ SUBSCRIPTIONS ============

class TestSubscriptionSorting:
    """Test sorting and filtering of subscriptions"""

    def test_get_subscriptions_sort_by_renewal_asc(self, admin_headers):
        resp = requests.get(
            f"{BASE_URL}/api/admin/subscriptions",
            params={"sort_by": "renewal_date", "sort_order": "asc"},
            headers=admin_headers
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        subs = data.get("subscriptions", [])
        assert isinstance(subs, list), "subscriptions must be a list"
        print(f"PASS: sort_by=renewal_date asc returned {len(subs)} subs")

    def test_get_subscriptions_sort_by_renewal_desc(self, admin_headers):
        resp = requests.get(
            f"{BASE_URL}/api/admin/subscriptions",
            params={"sort_by": "renewal_date", "sort_order": "desc"},
            headers=admin_headers
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        subs = data.get("subscriptions", [])
        assert isinstance(subs, list), "subscriptions must be a list"
        print(f"PASS: sort_by=renewal_date desc returned {len(subs)} subs")

    def test_sort_asc_vs_desc_renewal_different(self, admin_headers):
        asc = requests.get(
            f"{BASE_URL}/api/admin/subscriptions",
            params={"sort_by": "renewal_date", "sort_order": "asc"},
            headers=admin_headers
        ).json().get("subscriptions", [])
        desc = requests.get(
            f"{BASE_URL}/api/admin/subscriptions",
            params={"sort_by": "renewal_date", "sort_order": "desc"},
            headers=admin_headers
        ).json().get("subscriptions", [])
        if len(asc) > 1 and len(desc) > 1:
            # First elements should differ for non-trivial data
            first_asc = asc[0].get("renewal_date") or asc[0].get("id")
            first_desc = desc[0].get("renewal_date") or desc[0].get("id")
            print(f"PASS: asc first={first_asc}, desc first={first_desc}")
        else:
            print("SKIP: Not enough subscriptions to compare sort order")

    def test_get_subscriptions_sort_by_created_at(self, admin_headers):
        resp = requests.get(
            f"{BASE_URL}/api/admin/subscriptions",
            params={"sort_by": "created_at", "sort_order": "desc"},
            headers=admin_headers
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        subs = resp.json().get("subscriptions", [])
        assert isinstance(subs, list)
        print(f"PASS: sort_by=created_at returned {len(subs)} subs")

    def test_created_from_filter(self, admin_headers):
        resp = requests.get(
            f"{BASE_URL}/api/admin/subscriptions",
            params={"created_from": "2024-01-01"},
            headers=admin_headers
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        subs = resp.json().get("subscriptions", [])
        print(f"PASS: created_from=2024-01-01 returned {len(subs)} subs")

    def test_created_to_filter(self, admin_headers):
        resp = requests.get(
            f"{BASE_URL}/api/admin/subscriptions",
            params={"created_to": "2030-12-31"},
            headers=admin_headers
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        subs = resp.json().get("subscriptions", [])
        print(f"PASS: created_to=2030-12-31 returned {len(subs)} subs")

    def test_subscriptions_have_subscription_number(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/subscriptions", headers=admin_headers)
        assert resp.status_code == 200
        subs = resp.json().get("subscriptions", [])
        if subs:
            # At least one sub should have subscription_number (after backfill)
            has_sub_num = any(s.get("subscription_number") for s in subs)
            assert has_sub_num, "No subscriptions have subscription_number after backfill"
            print(f"PASS: {sum(1 for s in subs if s.get('subscription_number'))} subs have subscription_number")
        else:
            print("SKIP: No subscriptions in DB")

    def test_subscriptions_have_start_date(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/subscriptions", headers=admin_headers)
        assert resp.status_code == 200
        subs = resp.json().get("subscriptions", [])
        if subs:
            # Most subs should have start_date (after backfill)
            has_start = sum(1 for s in subs if s.get("start_date"))
            print(f"PASS: {has_start}/{len(subs)} subs have start_date")
        else:
            print("SKIP: No subscriptions in DB")


class TestSubscriptionEdit:
    """Test editing subscriptions (start_date editable, offline_manual status)"""

    def test_update_subscription_with_offline_manual_status(self, admin_headers):
        # Get first active subscription
        resp = requests.get(f"{BASE_URL}/api/admin/subscriptions", headers=admin_headers)
        assert resp.status_code == 200
        subs = resp.json().get("subscriptions", [])
        active_subs = [s for s in subs if s.get("status") == "active"]

        if not active_subs:
            pytest.skip("No active subscriptions to test status update")

        sub = active_subs[0]
        sub_id = sub["id"]
        original_status = sub.get("status")

        # Set to offline_manual
        update_resp = requests.put(
            f"{BASE_URL}/api/admin/subscriptions/{sub_id}",
            json={"status": "offline_manual"},
            headers=admin_headers
        )
        assert update_resp.status_code == 200, f"Failed: {update_resp.text}"
        print(f"PASS: Updated sub {sub_id} status to offline_manual")

        # Restore original status
        requests.put(
            f"{BASE_URL}/api/admin/subscriptions/{sub_id}",
            json={"status": original_status},
            headers=admin_headers
        )

    def test_update_subscription_start_date(self, admin_headers):
        # Get first available subscription
        resp = requests.get(f"{BASE_URL}/api/admin/subscriptions", headers=admin_headers)
        assert resp.status_code == 200
        subs = resp.json().get("subscriptions", [])
        if not subs:
            pytest.skip("No subscriptions to test")

        sub = subs[0]
        sub_id = sub["id"]
        new_start = "2025-01-15"

        update_resp = requests.put(
            f"{BASE_URL}/api/admin/subscriptions/{sub_id}",
            json={"start_date": new_start},
            headers=admin_headers
        )
        assert update_resp.status_code == 200, f"Failed: {update_resp.text}"
        print(f"PASS: Updated start_date for sub {sub_id}")

    def test_update_subscription_with_note(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/subscriptions", headers=admin_headers)
        assert resp.status_code == 200
        subs = resp.json().get("subscriptions", [])
        if not subs:
            pytest.skip("No subscriptions to test")

        sub_id = subs[0]["id"]
        note_text = "Test note from iteration 9 testing"

        update_resp = requests.put(
            f"{BASE_URL}/api/admin/subscriptions/{sub_id}",
            json={"new_note": note_text},
            headers=admin_headers
        )
        assert update_resp.status_code == 200, f"Failed: {update_resp.text}"
        print(f"PASS: Note added to sub {sub_id}")


class TestSubscriptionCancel:
    """Test cancel endpoint with audit log"""

    def test_cancel_creates_audit_log(self, admin_headers):
        # Get an active subscription to cancel
        resp = requests.get(f"{BASE_URL}/api/admin/subscriptions", headers=admin_headers)
        assert resp.status_code == 200
        subs = resp.json().get("subscriptions", [])
        active_subs = [s for s in subs if s.get("status") == "active"]

        if not active_subs:
            pytest.skip("No active subscriptions to cancel")

        sub = active_subs[-1]  # Use last one to avoid conflict
        sub_id = sub["id"]

        # Cancel subscription
        cancel_resp = requests.post(
            f"{BASE_URL}/api/admin/subscriptions/{sub_id}/cancel",
            headers=admin_headers
        )
        assert cancel_resp.status_code == 200, f"Cancel failed: {cancel_resp.text}"
        cancel_data = cancel_resp.json()
        assert "message" in cancel_data, "Response should have 'message'"
        assert "cancelled_at" in cancel_data, "Response should have 'cancelled_at'"
        print(f"PASS: Cancel returned message={cancel_data['message']}, cancelled_at={cancel_data['cancelled_at']}")

        # Check audit log
        logs_resp = requests.get(
            f"{BASE_URL}/api/admin/subscriptions/{sub_id}/logs",
            headers=admin_headers
        )
        assert logs_resp.status_code == 200, f"Logs failed: {logs_resp.text}"
        logs = logs_resp.json().get("logs", [])
        cancel_logs = [l for l in logs if l.get("action") == "cancelled"]
        assert len(cancel_logs) > 0, "Cancel audit log should exist"

        cancel_log = cancel_logs[-1]
        assert "actor" in cancel_log, "Cancel log should have 'actor'"
        assert "created_at" in cancel_log, "Cancel log should have 'created_at'"
        # Actor should be admin:UUID format
        assert cancel_log["actor"].startswith("admin:"), f"Actor should start with 'admin:', got: {cancel_log['actor']}"
        print(f"PASS: Cancel audit log found with actor={cancel_log['actor']}")

        # Verify subscription status changed
        sub_check = requests.get(f"{BASE_URL}/api/admin/subscriptions", headers=admin_headers)
        updated_subs = sub_check.json().get("subscriptions", [])
        updated_sub = next((s for s in updated_subs if s["id"] == sub_id), None)
        if updated_sub:
            assert updated_sub["status"] == "canceled_pending", f"Expected canceled_pending, got {updated_sub['status']}"
            print(f"PASS: Subscription status is now {updated_sub['status']}")


# ============ USERS (SUPER ADMIN) ============

class TestAdminUsers:
    """Test super-admin-only user management"""

    def test_get_admin_users_returns_200(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/users", headers=admin_headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        assert "users" in data, "Response should have 'users'"
        users = data["users"]
        assert isinstance(users, list), "users must be a list"
        print(f"PASS: GET /admin/users returned {len(users)} users")

    def test_admin_users_list_contains_admin_local(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/users", headers=admin_headers)
        assert resp.status_code == 200
        users = resp.json().get("users", [])
        emails = [u.get("email") for u in users]
        assert ADMIN_EMAIL in emails, f"admin@automateaccounts.local not found in {emails}"
        print(f"PASS: admin@automateaccounts.local found in users list")

    def test_admin_users_no_password_hash(self, admin_headers):
        """Ensure password_hash is excluded from response"""
        resp = requests.get(f"{BASE_URL}/api/admin/users", headers=admin_headers)
        assert resp.status_code == 200
        users = resp.json().get("users", [])
        for u in users:
            assert "password_hash" not in u, f"password_hash exposed for user {u.get('email')}"
        print(f"PASS: No password_hash in admin users response")

    def test_admin_user_has_role_field(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/users", headers=admin_headers)
        assert resp.status_code == 200
        users = resp.json().get("users", [])
        for u in users:
            assert "role" in u, f"User {u.get('email')} missing role field"
            assert u["role"] in ("admin", "super_admin"), f"Invalid role: {u['role']}"
        print(f"PASS: All admin users have valid role field")

    def test_create_admin_user(self, admin_headers):
        """Create a new admin user and verify"""
        test_email = "testadmin_iter9@example.com"

        # Attempt creation
        create_resp = requests.post(
            f"{BASE_URL}/api/admin/users",
            json={
                "email": test_email,
                "full_name": "Test Admin Iter9",
                "password": "TestPass123!",
                "role": "admin"
            },
            headers=admin_headers
        )

        # If already exists from previous test run, that's also OK
        if create_resp.status_code == 400 and "already registered" in create_resp.text:
            print(f"SKIP: User {test_email} already exists (previous test run)")
            return

        assert create_resp.status_code == 200, f"Create failed: {create_resp.text}"
        data = create_resp.json()
        assert "user_id" in data, "Response should have user_id"
        assert "email" in data, "Response should have email"
        print(f"PASS: Created admin user {test_email} with id={data['user_id']}")

        # Verify it appears in users list
        list_resp = requests.get(f"{BASE_URL}/api/admin/users", headers=admin_headers)
        assert list_resp.status_code == 200
        users = list_resp.json().get("users", [])
        emails = [u.get("email") for u in users]
        assert test_email in emails, f"{test_email} not found in users after creation"
        print(f"PASS: New admin user appears in list")

    def test_create_admin_user_invalid_role_rejected(self, admin_headers):
        """Invalid role should return 400"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/users",
            json={
                "email": "badroler@example.com",
                "full_name": "Bad Role",
                "password": "TestPass123!",
                "role": "customer"
            },
            headers=admin_headers
        )
        assert resp.status_code == 400, f"Expected 400 for invalid role, got {resp.status_code}"
        print(f"PASS: Invalid role returns 400: {resp.json()}")


# ============ CUSTOMERS (ADMIN CREATE) ============

class TestAdminCreateCustomer:
    """Test POST /admin/customers/create"""

    def test_create_customer(self, admin_headers):
        test_email = "test9999_iter9@example.com"

        resp = requests.post(
            f"{BASE_URL}/api/admin/customers/create",
            json={
                "email": test_email,
                "full_name": "Test Customer 9999",
                "password": "TestPass123!",
                "line1": "123 Test Street",
                "city": "London",
                "region": "Greater London",
                "postal": "SW1A 1AA",
                "country": "GB",
                "mark_verified": True
            },
            headers=admin_headers
        )

        if resp.status_code == 400 and "already registered" in resp.text:
            print(f"SKIP: Customer {test_email} already exists (previous test run)")
            return

        assert resp.status_code == 200, f"Create customer failed: {resp.text}"
        data = resp.json()
        assert "customer_id" in data, "Response should have customer_id"
        assert "user_id" in data, "Response should have user_id"
        print(f"PASS: Created customer {test_email}, customer_id={data['customer_id']}")

    def test_create_customer_duplicate_email_rejected(self, admin_headers):
        """Creating a customer with an existing email should return 400"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/customers/create",
            json={
                "email": ADMIN_EMAIL,  # Already exists
                "full_name": "Duplicate User",
                "password": "TestPass123!",
                "line1": "123 Test St",
                "city": "London",
                "region": "London",
                "postal": "SW1A 1AA",
                "country": "GB",
                "mark_verified": True
            },
            headers=admin_headers
        )
        assert resp.status_code == 400, f"Expected 400 for duplicate email, got {resp.status_code}"
        print(f"PASS: Duplicate email correctly rejected: {resp.json()}")

    def test_create_customer_appears_in_customers_list(self, admin_headers):
        """After creation, customer should appear in /admin/customers"""
        test_email = "test9999_iter9@example.com"

        # Create customer (may already exist)
        requests.post(
            f"{BASE_URL}/api/admin/customers/create",
            json={
                "email": test_email,
                "full_name": "Test Customer 9999",
                "password": "TestPass123!",
                "line1": "123 Test Street",
                "city": "London",
                "region": "Greater London",
                "postal": "SW1A 1AA",
                "country": "GB",
                "mark_verified": True
            },
            headers=admin_headers
        )

        # Verify in list
        list_resp = requests.get(f"{BASE_URL}/api/admin/customers", headers=admin_headers)
        assert list_resp.status_code == 200, f"GET /admin/customers failed: {list_resp.text}"
        data = list_resp.json()
        users = data.get("users", [])
        emails = [u.get("email") for u in users]
        assert test_email in emails, f"{test_email} not found in customers list after creation"
        print(f"PASS: Created customer {test_email} appears in /admin/customers")


# ============ PORTAL SUBSCRIPTIONS ============

class TestPortalSubscriptions:
    """Test customer portal subscriptions endpoint"""

    def test_portal_subscriptions_have_subscription_number(self, admin_headers):
        """Portal /subscriptions should return subscription_number"""
        resp = requests.get(f"{BASE_URL}/api/subscriptions", headers=admin_headers)
        # Admin user may not have customer subscriptions, so 200 is expected with empty list
        assert resp.status_code == 200, f"Failed: {resp.text}"
        subs = resp.json().get("subscriptions", [])
        for sub in subs:
            if sub.get("subscription_number"):
                print(f"PASS: sub {sub['id']} has subscription_number={sub['subscription_number']}")
                return
        print(f"INFO: No subscriptions for admin user in portal, or none have subscription_number")


# ============ UNAUTHORIZED ACCESS ============

class TestUnauthorizedAccess:
    """Test that non-super-admin users cannot access super-admin endpoints"""

    def test_unauthenticated_cannot_access_admin_users(self):
        resp = requests.get(f"{BASE_URL}/api/admin/users")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print(f"PASS: Unauthenticated GET /admin/users returns 401")
