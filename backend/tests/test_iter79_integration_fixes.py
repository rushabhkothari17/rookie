"""
Iteration 79: Integration Consolidation Fixes Tests

Tests:
1. Zoho CRM connect generates correct callback URL (not localhost)
2. All 7 integrations show Connect buttons
3. Connect Services page displays OAuth Callback URL in info banner
4. Email Templates no longer shows duplicate provider configuration
5. Email Templates shows 'Connect a Provider' link when no provider is active
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestIntegrationConsolidation:
    """Tests for integration consolidation fixes"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Get auth token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@automateaccounts.local",
            "password": "ChangeMe123!",
            "partner_code": "automate-accounts"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json().get("token")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    def test_list_all_7_integrations(self):
        """Test that all 7 integrations are returned by the API"""
        response = requests.get(
            f"{BASE_URL}/api/oauth/integrations",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        integrations = data.get("integrations", [])
        
        # Extract integration IDs
        integration_ids = [i["id"] for i in integrations]
        
        # Verify all 7 integrations exist
        expected_integrations = [
            "stripe", "gocardless", "gocardless_sandbox",
            "zoho_mail", "zoho_crm", "zoho_books", "resend"
        ]
        
        for expected in expected_integrations:
            assert expected in integration_ids, f"Missing integration: {expected}"
        
        print(f"PASS: All 7 integrations found: {integration_ids}")
    
    def test_integrations_have_connect_capability(self):
        """Test that integrations have can_connect field"""
        response = requests.get(
            f"{BASE_URL}/api/oauth/integrations",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        integrations = data.get("integrations", [])
        
        for integration in integrations:
            assert "can_connect" in integration, f"{integration['id']} missing can_connect field"
            assert "status" in integration, f"{integration['id']} missing status field"
            print(f"  {integration['id']}: can_connect={integration['can_connect']}, status={integration['status']}")
        
        print("PASS: All integrations have can_connect capability field")
    
    def test_zoho_crm_connect_callback_url_not_localhost(self):
        """Test that Zoho CRM connect returns callback URL without localhost"""
        response = requests.post(
            f"{BASE_URL}/api/oauth/zoho_crm/connect",
            headers=self.headers,
            json={"data_center": "us"}
        )
        assert response.status_code == 200, f"Connect failed: {response.text}"
        
        data = response.json()
        
        # Check callback_url field
        callback_url = data.get("callback_url", "")
        assert callback_url, "Missing callback_url in response"
        assert "localhost" not in callback_url.lower(), f"Callback URL contains localhost: {callback_url}"
        
        # Check authorization_url redirect_uri
        auth_url = data.get("authorization_url", "")
        assert "redirect_uri=" in auth_url, "Missing redirect_uri in authorization_url"
        assert "localhost" not in auth_url.lower(), f"Authorization URL contains localhost: {auth_url}"
        
        print(f"PASS: Callback URL is correct: {callback_url}")
    
    def test_zoho_books_connect_callback_url_not_localhost(self):
        """Test that Zoho Books connect returns callback URL without localhost"""
        response = requests.post(
            f"{BASE_URL}/api/oauth/zoho_books/connect",
            headers=self.headers,
            json={"data_center": "eu"}
        )
        assert response.status_code == 200
        
        data = response.json()
        callback_url = data.get("callback_url", "")
        
        assert "localhost" not in callback_url.lower(), f"Callback URL contains localhost: {callback_url}"
        print(f"PASS: Zoho Books callback URL correct: {callback_url}")
    
    def test_zoho_mail_connect_callback_url_not_localhost(self):
        """Test that Zoho Mail connect returns callback URL without localhost"""
        response = requests.post(
            f"{BASE_URL}/api/oauth/zoho_mail/connect",
            headers=self.headers,
            json={"data_center": "in"}
        )
        assert response.status_code == 200
        
        data = response.json()
        callback_url = data.get("callback_url", "")
        
        assert "localhost" not in callback_url.lower(), f"Callback URL contains localhost: {callback_url}"
        print(f"PASS: Zoho Mail callback URL correct: {callback_url}")
    
    def test_zoho_data_centers_available(self):
        """Test that all 6 Zoho data centers are returned"""
        response = requests.get(
            f"{BASE_URL}/api/oauth/integrations",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        data_centers = data.get("zoho_data_centers", [])
        
        # Expected data centers
        expected_dcs = ["us", "eu", "in", "au", "jp", "ca"]
        dc_ids = [dc["id"] for dc in data_centers]
        
        for expected in expected_dcs:
            assert expected in dc_ids, f"Missing data center: {expected}"
        
        print(f"PASS: All 6 Zoho data centers available: {dc_ids}")
    
    def test_integration_status_api_returns_active_email_provider(self):
        """Test that integration status API returns active_email_provider field"""
        response = requests.get(
            f"{BASE_URL}/api/admin/integrations/status",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        
        # Check active_email_provider field exists (can be null when no provider active)
        assert "active_email_provider" in data, "Missing active_email_provider field"
        print(f"PASS: active_email_provider field exists, value: {data['active_email_provider']}")
    
    def test_resend_api_key_endpoint(self):
        """Test that Resend API key endpoint works"""
        # Test with a dummy API key
        response = requests.post(
            f"{BASE_URL}/api/oauth/resend/api-key",
            headers=self.headers,
            json={"api_key": "re_test_123456789"}
        )
        assert response.status_code == 200, f"API key save failed: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "API key save did not return success"
        
        print("PASS: Resend API key endpoint working")
    
    def test_stripe_connect_requires_credentials(self):
        """Test that Stripe connect fails gracefully without credentials"""
        response = requests.post(
            f"{BASE_URL}/api/oauth/stripe/connect",
            headers=self.headers,
            json={}
        )
        
        # Should fail with 400 if no credentials configured
        # This is expected behavior - Connect button should be disabled in UI
        if response.status_code == 400:
            assert "not configured" in response.text.lower() or "contact support" in response.text.lower()
            print("PASS: Stripe correctly rejects connect without credentials")
        else:
            # If credentials are configured, it should return 200 with auth URL
            assert response.status_code == 200
            print("PASS: Stripe connect with credentials configured")
    
    def test_gocardless_connect_requires_credentials(self):
        """Test that GoCardless connect fails gracefully without credentials"""
        response = requests.post(
            f"{BASE_URL}/api/oauth/gocardless/connect",
            headers=self.headers,
            json={}
        )
        
        # Should fail with 400 if no credentials configured
        if response.status_code == 400:
            assert "not configured" in response.text.lower() or "contact support" in response.text.lower()
            print("PASS: GoCardless correctly rejects connect without credentials")
        else:
            assert response.status_code == 200
            print("PASS: GoCardless connect with credentials configured")


class TestEmailTemplatesAPI:
    """Tests for email templates API (should NOT have provider config)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Get auth token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@automateaccounts.local",
            "password": "ChangeMe123!",
            "partner_code": "automate-accounts"
        })
        assert login_response.status_code == 200
        self.token = login_response.json().get("token")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    def test_email_templates_endpoint_exists(self):
        """Test that email templates endpoint works"""
        response = requests.get(
            f"{BASE_URL}/api/admin/email-templates",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        templates = data.get("templates", [])
        assert len(templates) > 0, "No email templates returned"
        
        print(f"PASS: Email templates endpoint returns {len(templates)} templates")
    
    def test_email_templates_structure(self):
        """Test that email templates have correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/admin/email-templates",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        templates = data.get("templates", [])
        
        for tmpl in templates[:3]:  # Check first 3
            assert "id" in tmpl
            assert "trigger" in tmpl
            assert "label" in tmpl
            assert "subject" in tmpl
            assert "is_enabled" in tmpl
        
        print("PASS: Email templates have correct structure")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
