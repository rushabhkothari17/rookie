"""
Test suite for P0 UI bug fixes:
1. Customer (non-admin) should NOT see Admin tab - validated via is_admin field
2. Partner code (partner_id) should display correctly in user profile

Tests verify:
- /auth/customer-login endpoint works for customers
- /auth/partner-login endpoint works for admins
- /me endpoint returns correct is_admin and partner_code values
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
CUSTOMER_CREDS = {
    "email": "testcustomer@test.com",
    "password": "ChangeMe123!",
    "partner_code": "automate-accounts"
}
ADMIN_CREDS = {
    "email": "admin@automateaccounts.local",
    "password": "ChangeMe123!",
    "partner_code": "automate-accounts"
}


class TestCustomerLogin:
    """Tests for customer login flow and is_admin=false"""
    
    def test_customer_login_via_customer_endpoint(self):
        """Customer should be able to login via /auth/customer-login"""
        response = requests.post(f"{BASE_URL}/api/auth/customer-login", json=CUSTOMER_CREDS)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "token" in data
        assert data["role"] == "customer"
        print(f"PASS: Customer login successful, role={data['role']}")
    
    def test_customer_partner_login_returns_403(self):
        """Customer should get 403 when trying partner-login (wrong login type)"""
        response = requests.post(f"{BASE_URL}/api/auth/partner-login", json=CUSTOMER_CREDS)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        
        data = response.json()
        assert "Access denied" in data.get("detail", "")
        print("PASS: Customer correctly rejected from partner-login with 403")
    
    def test_customer_is_admin_false(self):
        """Customer's /me response should have is_admin=false"""
        # Login first
        login_resp = requests.post(f"{BASE_URL}/api/auth/customer-login", json=CUSTOMER_CREDS)
        assert login_resp.status_code == 200
        token = login_resp.json()["token"]
        
        # Get /me
        me_resp = requests.get(f"{BASE_URL}/api/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200
        
        user = me_resp.json()["user"]
        assert user["is_admin"] == False, f"Expected is_admin=false, got {user['is_admin']}"
        assert user["role"] == "customer"
        print(f"PASS: Customer is_admin={user['is_admin']}, role={user['role']}")
    
    def test_customer_partner_code_in_profile(self):
        """Customer's /me response should include partner_code"""
        # Login first
        login_resp = requests.post(f"{BASE_URL}/api/auth/customer-login", json=CUSTOMER_CREDS)
        assert login_resp.status_code == 200
        token = login_resp.json()["token"]
        
        # Get /me
        me_resp = requests.get(f"{BASE_URL}/api/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200
        
        user = me_resp.json()["user"]
        assert user.get("partner_code") == "automate-accounts", f"Expected partner_code='automate-accounts', got {user.get('partner_code')}"
        print(f"PASS: Customer partner_code='{user['partner_code']}'")


class TestAdminLogin:
    """Tests for admin login flow and is_admin=true"""
    
    def test_admin_login_via_partner_endpoint(self):
        """Admin should be able to login via /auth/partner-login"""
        response = requests.post(f"{BASE_URL}/api/auth/partner-login", json=ADMIN_CREDS)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "token" in data
        assert data["role"] in ["platform_admin", "partner_super_admin", "partner_admin", "admin"]
        print(f"PASS: Admin login successful, role={data['role']}")
    
    def test_admin_is_admin_true(self):
        """Admin's /me response should have is_admin=true"""
        # Login first
        login_resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json=ADMIN_CREDS)
        assert login_resp.status_code == 200
        token = login_resp.json()["token"]
        
        # Get /me
        me_resp = requests.get(f"{BASE_URL}/api/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200
        
        user = me_resp.json()["user"]
        assert user["is_admin"] == True, f"Expected is_admin=true, got {user['is_admin']}"
        print(f"PASS: Admin is_admin={user['is_admin']}, role={user['role']}")


class TestLoginFallback:
    """Tests for the unified login fallback from partner-login to customer-login"""
    
    def test_customer_can_login_unified_flow(self):
        """
        Simulates the frontend flow: try partner-login first, if 403 with 'Access denied',
        fall back to customer-login. This matches AuthContext.tsx behavior.
        """
        # First try partner-login
        partner_resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json=CUSTOMER_CREDS)
        
        if partner_resp.status_code == 403 and "Access denied" in partner_resp.json().get("detail", ""):
            # Fallback to customer-login (expected path for customers)
            customer_resp = requests.post(f"{BASE_URL}/api/auth/customer-login", json=CUSTOMER_CREDS)
            assert customer_resp.status_code == 200
            assert customer_resp.json()["role"] == "customer"
            print("PASS: Unified login fallback works - customer logged in via fallback")
        else:
            pytest.fail(f"Expected partner-login to return 403 for customer, got {partner_resp.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
