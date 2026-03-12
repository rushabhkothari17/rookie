"""
Tests for the new admin-protected POST /api/admin/tenants/create-partner endpoint
and partner login via /api/auth/partner-login with the returned partner_code.
Iteration 260 — Bug fix verification: partner org creation from admin panel.
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestAdminCreatePartnerOrg:
    """Tests for POST /api/admin/tenants/create-partner endpoint"""

    @pytest.fixture(scope="class")
    def admin_token(self):
        """Authenticate as platform admin via /auth/login (no partner_code for platform admins)."""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@automateaccounts.local",
            "password": "ChangeMe123!",
        })
        assert resp.status_code == 200, f"Admin login failed: {resp.status_code} {resp.text}"
        return resp.json().get("token")

    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}"}

    def test_admin_login_success(self, admin_token):
        """Platform admin can log in with automate-accounts partner code."""
        assert admin_token, "Token should be returned on successful login"
        print("PASS: Platform admin logged in successfully")

    def test_create_partner_returns_partner_code(self, auth_headers):
        """POST /admin/tenants/create-partner returns partner_code and tenant_id."""
        ts = int(time.time())
        payload = {
            "name": f"TEST_Partner Corp {ts}",
            "admin_name": "TEST Admin User",
            "admin_email": f"test_partner_admin_{ts}@testcorp.example.com",
            "admin_password": "TestPass123!",
            "base_currency": "USD",
        }
        resp = requests.post(
            f"{BASE_URL}/api/admin/tenants/create-partner",
            json=payload,
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "partner_code" in data, f"Response missing partner_code: {data}"
        assert "tenant_id" in data, f"Response missing tenant_id: {data}"
        assert data["partner_code"], "partner_code should not be empty"
        assert data["tenant_id"], "tenant_id should not be empty"
        print(f"PASS: Partner org created, partner_code={data['partner_code']}, tenant_id={data['tenant_id']}")

    def test_create_partner_generates_slug_from_name(self, auth_headers):
        """partner_code is auto-generated from org name (slug)."""
        ts = int(time.time())
        org_name = f"TEST Acme Corporation {ts}"
        payload = {
            "name": org_name,
            "admin_name": "Acme Admin",
            "admin_email": f"acme_admin_{ts}@acme.example.com",
            "admin_password": "AcmePass123!",
        }
        resp = requests.post(
            f"{BASE_URL}/api/admin/tenants/create-partner",
            json=payload,
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        # Code should be slug-like (no spaces, lowercase)
        code = data["partner_code"]
        assert " " not in code, f"partner_code should have no spaces: {code}"
        assert code == code.lower(), f"partner_code should be lowercase: {code}"
        print(f"PASS: Partner code auto-generated: '{code}' from org name '{org_name}'")

    def test_create_partner_without_auth_returns_401(self):
        """Endpoint requires admin authentication."""
        ts = int(time.time())
        payload = {
            "name": f"TEST_UnAuth Org {ts}",
            "admin_name": "Admin",
            "admin_email": f"unauth_{ts}@test.example.com",
            "admin_password": "TestPass123!",
        }
        resp = requests.post(
            f"{BASE_URL}/api/admin/tenants/create-partner",
            json=payload,
            # No auth headers
        )
        assert resp.status_code in [401, 403], f"Expected 401 or 403 without auth, got {resp.status_code}: {resp.text}"
        print(f"PASS: Endpoint correctly blocked without auth ({resp.status_code})")

    def test_create_partner_missing_fields_returns_400(self, auth_headers):
        """Missing required fields returns 400."""
        resp = requests.post(
            f"{BASE_URL}/api/admin/tenants/create-partner",
            json={"name": "TEST_Incomplete Org"},  # Missing admin_name, admin_email, admin_password
            headers=auth_headers,
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        print(f"PASS: Missing fields correctly returns 400")

    def test_create_partner_duplicate_email_returns_400(self, auth_headers):
        """Cannot create partner with an already-registered email."""
        ts = int(time.time())
        email = f"dupe_test_{ts}@dupe.example.com"
        payload = {
            "name": f"TEST_Dupe Org A {ts}",
            "admin_name": "Admin A",
            "admin_email": email,
            "admin_password": "TestPass123!",
        }
        # Create first
        r1 = requests.post(f"{BASE_URL}/api/admin/tenants/create-partner", json=payload, headers=auth_headers)
        assert r1.status_code == 200, f"First create failed: {r1.status_code} {r1.text}"
        # Attempt duplicate
        payload2 = {
            "name": f"TEST_Dupe Org B {ts}",
            "admin_name": "Admin B",
            "admin_email": email,  # Same email
            "admin_password": "TestPass123!",
        }
        r2 = requests.post(f"{BASE_URL}/api/admin/tenants/create-partner", json=payload2, headers=auth_headers)
        assert r2.status_code == 400, f"Expected 400 for duplicate email, got {r2.status_code}: {r2.text}"
        data2 = r2.json()
        assert "already registered" in data2.get("detail", "").lower(), f"Error msg should mention 'already registered': {data2}"
        print("PASS: Duplicate email correctly returns 400")

    def test_create_partner_weak_password_returns_400(self, auth_headers):
        """Weak password fails validation."""
        ts = int(time.time())
        payload = {
            "name": f"TEST_WeakPass Org {ts}",
            "admin_name": "Admin",
            "admin_email": f"weakpass_{ts}@weak.example.com",
            "admin_password": "weak",  # Too short, no complexity
        }
        resp = requests.post(
            f"{BASE_URL}/api/admin/tenants/create-partner",
            json=payload,
            headers=auth_headers,
        )
        assert resp.status_code == 400, f"Expected 400 for weak password, got {resp.status_code}: {resp.text}"
        print("PASS: Weak password correctly returns 400")


class TestPartnerLoginAfterAdminCreate:
    """Test that a partner_super_admin created via admin endpoint can log in."""

    @pytest.fixture(scope="class")
    def created_partner(self):
        """Create a partner org via admin endpoint and return credentials."""
        # First get admin token via /auth/login (no partner_code for platform admins)
        admin_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@automateaccounts.local",
            "password": "ChangeMe123!",
        })
        assert admin_resp.status_code == 200, f"Admin login failed: {admin_resp.text}"
        admin_token = admin_resp.json().get("token")

        ts = int(time.time()) % 100000  # Keep timestamp short
        partner_email = f"plogin_{ts}@tst.co"
        partner_password = "PartnerPass123!"
        org_name = f"TEST_PartnerCorp {ts}"

        create_resp = requests.post(
            f"{BASE_URL}/api/admin/tenants/create-partner",
            json={
                "name": org_name,
                "admin_name": "Partner Admin",
                "admin_email": partner_email,
                "admin_password": partner_password,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert create_resp.status_code == 200, f"Failed to create partner: {create_resp.text}"
        data = create_resp.json()
        return {
            "partner_code": data["partner_code"],
            "tenant_id": data["tenant_id"],
            "email": partner_email,
            "password": partner_password,
        }

    def test_partner_can_login_with_returned_code(self, created_partner):
        """Partner_super_admin can login via /api/auth/partner-login with the returned partner_code."""
        resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": created_partner["partner_code"],
            "email": created_partner["email"],
            "password": created_partner["password"],
        })
        assert resp.status_code == 200, f"Partner login failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "token" in data, f"Missing token in response: {data}"
        assert data["role"] in ("partner_super_admin", "partner_admin", "admin"), f"Unexpected role: {data.get('role')}"
        assert data["tenant_id"] == created_partner["tenant_id"], f"Tenant ID mismatch: {data.get('tenant_id')} vs {created_partner['tenant_id']}"
        print(f"PASS: Partner login succeeded — role={data['role']}, tenant_id={data['tenant_id']}")

    def test_partner_login_wrong_password_returns_401(self, created_partner):
        """Wrong password returns 401."""
        resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": created_partner["partner_code"],
            "email": created_partner["email"],
            "password": "WrongPassword!99",
        })
        assert resp.status_code == 401, f"Expected 401 for wrong password, got {resp.status_code}"
        print("PASS: Wrong password returns 401")

    def test_partner_login_wrong_code_returns_4xx(self, created_partner):
        """Invalid partner code returns error."""
        resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": "nonexistent-partner-code-xyz123",
            "email": created_partner["email"],
            "password": created_partner["password"],
        })
        assert resp.status_code in [400, 401, 404], f"Expected 4xx for wrong code, got {resp.status_code}"
        print(f"PASS: Invalid partner code returns {resp.status_code}")

    def test_partner_tenant_appears_in_admin_list(self, created_partner):
        """The newly created tenant appears in GET /admin/tenants list."""
        admin_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@automateaccounts.local",
            "password": "ChangeMe123!",
        })
        admin_token = admin_resp.json().get("token")

        list_resp = requests.get(
            f"{BASE_URL}/api/admin/tenants",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert list_resp.status_code == 200, f"Failed to list tenants: {list_resp.text}"
        tenants = list_resp.json().get("tenants", [])
        tenant_ids = [t["id"] for t in tenants]
        assert created_partner["tenant_id"] in tenant_ids, (
            f"Newly created tenant {created_partner['tenant_id']} not found in admin tenant list"
        )
        print(f"PASS: New tenant appears in admin tenant list (total: {len(tenants)} tenants)")
