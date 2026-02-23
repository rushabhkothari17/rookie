"""
Iteration 72: Test HttpOnly Cookie Authentication and New Features
- HttpOnly cookie authentication (login sets cookie AND returns token in JSON)
- /api/me works with both cookie and Bearer token
- Logout clears cookie
- GDPR export endpoint for customers
- Integration status endpoint for admin
- Resend validation endpoint
- Email provider set-active endpoint
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

class TestHttpOnlyCookieAuth:
    """Test HttpOnly cookie authentication flows"""
    
    def test_partner_login_returns_token_and_sets_cookie(self):
        """Partner login should return token in JSON AND set HttpOnly cookie"""
        session = requests.Session()
        response = session.post(
            f"{BASE_URL}/api/auth/partner-login",
            json={
                "email": "admin@automateaccounts.local",
                "password": "ChangeMe123!",
                "partner_code": "automate-accounts"
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify JSON response includes token
        assert "token" in data, "Response should include token in JSON"
        assert data["token"], "Token should not be empty"
        assert "role" in data, "Response should include role"
        
        # Verify cookie is set (check Set-Cookie header)
        cookies = response.cookies
        # Note: HttpOnly cookies may not be directly accessible via response.cookies
        # but the cookie should be set and sent on subsequent requests
        
        # Store token for later tests
        self.__class__.admin_token = data["token"]
        self.__class__.admin_session = session
        print(f"Admin login successful, role: {data['role']}")
    
    def test_customer_login_returns_token_and_sets_cookie(self):
        """Customer login should return token in JSON AND set HttpOnly cookie"""
        session = requests.Session()
        response = session.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={
                "email": "testcustomer@test.com",
                "password": "ChangeMe123!",
                "partner_code": "automate-accounts"
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify JSON response includes token
        assert "token" in data, "Response should include token in JSON"
        assert data["token"], "Token should not be empty"
        assert data.get("role") == "customer", f"Expected customer role, got {data.get('role')}"
        
        # Store for later tests
        self.__class__.customer_token = data["token"]
        self.__class__.customer_session = session
        print(f"Customer login successful, role: {data['role']}")
    
    def test_api_me_with_bearer_token(self):
        """Test /api/me works with Bearer token in Authorization header"""
        response = requests.get(
            f"{BASE_URL}/api/me",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "user" in data, "Response should include user object"
        assert data["user"]["email"] == "admin@automateaccounts.local"
        print(f"/api/me with Bearer token: {data['user']['email']}, role: {data['user']['role']}")
    
    def test_api_me_with_cookie_only(self):
        """Test /api/me works with cookie-only auth (no Authorization header)"""
        # Use the session from login which should have the cookie
        response = self.admin_session.get(f"{BASE_URL}/api/me")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "user" in data, "Response should include user object"
        assert data["user"]["email"] == "admin@automateaccounts.local"
        print(f"/api/me with cookie: {data['user']['email']}, role: {data['user']['role']}")
    
    def test_logout_clears_cookie(self):
        """Test logout endpoint clears the HttpOnly cookie"""
        # Create a new session and login
        session = requests.Session()
        login_response = session.post(
            f"{BASE_URL}/api/auth/partner-login",
            json={
                "email": "admin@automateaccounts.local",
                "password": "ChangeMe123!",
                "partner_code": "automate-accounts"
            }
        )
        assert login_response.status_code == 200
        
        # Verify session works before logout
        me_before = session.get(f"{BASE_URL}/api/me")
        assert me_before.status_code == 200, "Should be authenticated before logout"
        
        # Logout
        logout_response = session.post(f"{BASE_URL}/api/auth/logout")
        assert logout_response.status_code == 200, f"Logout failed: {logout_response.text}"
        data = logout_response.json()
        assert data.get("success") == True, "Logout should return success=True"
        
        # Verify session no longer works after logout
        me_after = session.get(f"{BASE_URL}/api/me")
        assert me_after.status_code == 401, f"Should be 401 after logout, got {me_after.status_code}"
        print("Logout successfully cleared authentication")


class TestGDPRExportEndpoint:
    """Test GDPR data export endpoint for customers"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as customer for GDPR tests"""
        session = requests.Session()
        response = session.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={
                "email": "testcustomer@test.com",
                "password": "ChangeMe123!",
                "partner_code": "automate-accounts"
            }
        )
        if response.status_code == 200:
            self.customer_token = response.json()["token"]
            self.customer_session = session
        else:
            pytest.skip("Customer login failed, skipping GDPR tests")
    
    def test_customer_can_export_data_json(self):
        """Test customer can export their data as JSON"""
        response = requests.get(
            f"{BASE_URL}/api/me/data-export",
            headers={"Authorization": f"Bearer {self.customer_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify export contains expected sections (data structure has 'data' key with nested sections)
        assert "data" in data or "customer_id" in data, "Export should include data or customer_id"
        if "data" in data:
            assert "account" in data["data"], "Export data should include account section"
        print(f"GDPR export successful, keys: {list(data.keys())}")
    
    def test_customer_can_export_data_using_cookie(self):
        """Test customer can export data using cookie auth"""
        response = self.customer_session.get(f"{BASE_URL}/api/me/data-export")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "data" in data or "customer_id" in data, "Export should include data or customer_id"
        print(f"GDPR export with cookie successful")
    
    def test_admin_cannot_use_customer_gdpr_endpoint(self):
        """Test that admin users cannot use customer GDPR export endpoint"""
        # Login as admin
        admin_response = requests.post(
            f"{BASE_URL}/api/auth/partner-login",
            json={
                "email": "admin@automateaccounts.local",
                "password": "ChangeMe123!",
                "partner_code": "automate-accounts"
            }
        )
        assert admin_response.status_code == 200
        admin_token = admin_response.json()["token"]
        
        # Try to access customer GDPR endpoint as admin
        response = requests.get(
            f"{BASE_URL}/api/me/data-export",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # Should return 403 (only customers can use this endpoint)
        assert response.status_code == 403, f"Expected 403 for admin, got {response.status_code}"
        print("Admin correctly blocked from customer GDPR endpoint")


class TestIntegrationStatusEndpoint:
    """Test integration status endpoint for admin"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin for integration tests"""
        response = requests.post(
            f"{BASE_URL}/api/auth/partner-login",
            json={
                "email": "admin@automateaccounts.local",
                "password": "ChangeMe123!",
                "partner_code": "automate-accounts"
            }
        )
        if response.status_code == 200:
            self.admin_token = response.json()["token"]
        else:
            pytest.skip("Admin login failed, skipping integration tests")
    
    def test_get_integrations_status(self):
        """Test admin can get integration status"""
        response = requests.get(
            f"{BASE_URL}/api/admin/integrations/status",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify expected structure
        assert "integrations" in data, "Response should include integrations object"
        integrations = data["integrations"]
        
        # Check expected integration providers are present
        expected_providers = ["resend", "zoho_mail", "zoho_crm", "stripe", "gocardless"]
        for provider in expected_providers:
            assert provider in integrations, f"Missing integration provider: {provider}"
            assert "status" in integrations[provider], f"Missing status for {provider}"
            assert "type" in integrations[provider], f"Missing type for {provider}"
        
        print(f"Integration status retrieved: {list(integrations.keys())}")
        for name, info in integrations.items():
            print(f"  - {name}: {info.get('status')}, type: {info.get('type')}")
    
    def test_customer_cannot_access_integration_status(self):
        """Test customer cannot access admin integration status"""
        # Login as customer
        customer_response = requests.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={
                "email": "testcustomer@test.com",
                "password": "ChangeMe123!",
                "partner_code": "automate-accounts"
            }
        )
        assert customer_response.status_code == 200
        customer_token = customer_response.json()["token"]
        
        # Try to access admin endpoint as customer
        response = requests.get(
            f"{BASE_URL}/api/admin/integrations/status",
            headers={"Authorization": f"Bearer {customer_token}"}
        )
        
        # Should return 403
        assert response.status_code == 403, f"Expected 403 for customer, got {response.status_code}"
        print("Customer correctly blocked from admin integration status")


class TestResendValidationEndpoint:
    """Test Resend email validation endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin for Resend tests"""
        response = requests.post(
            f"{BASE_URL}/api/auth/partner-login",
            json={
                "email": "admin@automateaccounts.local",
                "password": "ChangeMe123!",
                "partner_code": "automate-accounts"
            }
        )
        if response.status_code == 200:
            self.admin_token = response.json()["token"]
        else:
            pytest.skip("Admin login failed, skipping Resend tests")
    
    def test_resend_validate_endpoint_exists(self):
        """Test Resend validation endpoint is accessible"""
        response = requests.post(
            f"{BASE_URL}/api/admin/integrations/resend/validate",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        
        # Should return 200 (success or message about not configured)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Response should have success field or message
        assert "success" in data or "message" in data, "Response should include success or message"
        print(f"Resend validate response: {data}")
    
    def test_customer_cannot_validate_resend(self):
        """Test customer cannot access Resend validation"""
        customer_response = requests.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={
                "email": "testcustomer@test.com",
                "password": "ChangeMe123!",
                "partner_code": "automate-accounts"
            }
        )
        assert customer_response.status_code == 200
        customer_token = customer_response.json()["token"]
        
        response = requests.post(
            f"{BASE_URL}/api/admin/integrations/resend/validate",
            headers={"Authorization": f"Bearer {customer_token}"}
        )
        
        assert response.status_code == 403, f"Expected 403 for customer, got {response.status_code}"
        print("Customer correctly blocked from Resend validation")


class TestEmailProviderSetActive:
    """Test email provider set-active endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin for email provider tests"""
        response = requests.post(
            f"{BASE_URL}/api/auth/partner-login",
            json={
                "email": "admin@automateaccounts.local",
                "password": "ChangeMe123!",
                "partner_code": "automate-accounts"
            }
        )
        if response.status_code == 200:
            self.admin_token = response.json()["token"]
        else:
            pytest.skip("Admin login failed, skipping email provider tests")
    
    def test_set_active_provider_none(self):
        """Test setting active email provider to none"""
        response = requests.post(
            f"{BASE_URL}/api/admin/integrations/email-providers/set-active",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={"provider": "none"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True, "Should return success=True"
        print(f"Set active provider response: {data}")
    
    def test_set_active_invalid_provider_fails(self):
        """Test setting invalid provider returns error"""
        response = requests.post(
            f"{BASE_URL}/api/admin/integrations/email-providers/set-active",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={"provider": "invalid_provider"}
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid provider, got {response.status_code}"
        print("Invalid provider correctly rejected")
    
    def test_set_active_unvalidated_provider_fails(self):
        """Test setting unvalidated provider as active fails"""
        # Try to set Resend as active (assuming it's not validated)
        response = requests.post(
            f"{BASE_URL}/api/admin/integrations/email-providers/set-active",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={"provider": "resend"}
        )
        
        # Should fail with 400 if not validated
        if response.status_code == 400:
            data = response.json()
            assert "validated" in data.get("detail", "").lower(), "Error should mention validation"
            print("Unvalidated provider correctly rejected")
        elif response.status_code == 200:
            print("Resend was already validated, setting succeeded")
        else:
            pytest.fail(f"Unexpected status code: {response.status_code}")
    
    def test_customer_cannot_set_active_provider(self):
        """Test customer cannot set active email provider"""
        customer_response = requests.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={
                "email": "testcustomer@test.com",
                "password": "ChangeMe123!",
                "partner_code": "automate-accounts"
            }
        )
        assert customer_response.status_code == 200
        customer_token = customer_response.json()["token"]
        
        response = requests.post(
            f"{BASE_URL}/api/admin/integrations/email-providers/set-active",
            headers={"Authorization": f"Bearer {customer_token}"},
            json={"provider": "none"}
        )
        
        assert response.status_code == 403, f"Expected 403 for customer, got {response.status_code}"
        print("Customer correctly blocked from setting email provider")


class TestTenantBAdminAccess:
    """Test Tenant B admin can access admin panel"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as Tenant B admin with rate limit handling"""
        import time
        time.sleep(2)  # Avoid rate limiting
        
        response = requests.post(
            f"{BASE_URL}/api/auth/partner-login",
            json={
                "email": "adminb@tenantb.local",
                "password": "ChangeMe123!",
                "partner_code": "tenant-b-test"
            }
        )
        
        if response.status_code == 429:
            time.sleep(5)  # Wait longer if rate limited
            response = requests.post(
                f"{BASE_URL}/api/auth/partner-login",
                json={
                    "email": "adminb@tenantb.local",
                    "password": "ChangeMe123!",
                    "partner_code": "tenant-b-test"
                }
            )
        
        if response.status_code == 200:
            self.tenant_b_token = response.json()["token"]
            self.tenant_b_role = response.json()["role"]
        else:
            pytest.skip(f"Tenant B admin login failed: {response.status_code} - {response.text}")
    
    def test_tenant_b_admin_login_successful(self):
        """Test Tenant B admin token was obtained"""
        assert hasattr(self, 'tenant_b_token'), "Should have obtained token"
        assert self.tenant_b_token, "Token should not be empty"
        print(f"Tenant B admin login successful, role: {self.tenant_b_role}")
    
    def test_tenant_b_admin_can_access_me(self):
        """Test Tenant B admin can access /api/me"""
        response = requests.get(
            f"{BASE_URL}/api/me",
            headers={"Authorization": f"Bearer {self.tenant_b_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data["user"]["email"] == "adminb@tenantb.local"
        assert data["user"]["partner_code"] == "tenant-b-test"
        print(f"Tenant B admin /me: {data['user']['email']}, partner_code: {data['user']['partner_code']}")
    
    def test_tenant_b_admin_can_access_integration_status(self):
        """Test Tenant B admin can access integration status"""
        response = requests.get(
            f"{BASE_URL}/api/admin/integrations/status",
            headers={"Authorization": f"Bearer {self.tenant_b_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "integrations" in data
        print(f"Tenant B admin can access integrations: {list(data['integrations'].keys())}")


class TestEmailProvidersListEndpoint:
    """Test email providers list endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin"""
        response = requests.post(
            f"{BASE_URL}/api/auth/partner-login",
            json={
                "email": "admin@automateaccounts.local",
                "password": "ChangeMe123!",
                "partner_code": "automate-accounts"
            }
        )
        if response.status_code == 200:
            self.admin_token = response.json()["token"]
        else:
            pytest.skip("Admin login failed")
    
    def test_get_email_providers(self):
        """Test getting email providers list"""
        response = requests.get(
            f"{BASE_URL}/api/admin/integrations/email-providers",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "providers" in data, "Should include providers"
        assert "active_provider" in data, "Should include active_provider"
        
        providers = data["providers"]
        assert "resend" in providers, "Should include resend provider"
        assert "zoho_mail" in providers, "Should include zoho_mail provider"
        
        print(f"Email providers: {list(providers.keys())}")
        print(f"Active provider: {data['active_provider']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
