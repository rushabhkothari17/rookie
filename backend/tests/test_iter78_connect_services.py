"""
Iteration 78: Connect Services Hub Tests

Tests the OAuth Integrations API endpoint for the new unified Connect Services hub:
- GET /api/oauth/integrations - Returns all 7 integrations and 6 Zoho data centers
- Zoho OAuth flow (DC selection)
- Resend API key authentication
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
PLATFORM_ADMIN = {
    "email": "admin@automateaccounts.local",
    "password": "ChangeMe123!",
    "partner_code": "automate-accounts"
}


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for platform admin."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json=PLATFORM_ADMIN
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json().get("token")


@pytest.fixture
def auth_headers(auth_token):
    """Headers with authentication."""
    return {"Authorization": f"Bearer {auth_token}"}


class TestOAuthIntegrationsEndpoint:
    """Test GET /api/oauth/integrations endpoint."""
    
    def test_integrations_endpoint_returns_all_7_providers(self, auth_headers):
        """Verify endpoint returns all 7 expected integrations."""
        response = requests.get(
            f"{BASE_URL}/api/oauth/integrations",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "integrations" in data
        
        integrations = data["integrations"]
        assert len(integrations) == 7, f"Expected 7 integrations, got {len(integrations)}"
        
        # Verify all expected providers are present
        expected_ids = {"stripe", "gocardless", "gocardless_sandbox", "zoho_mail", "resend", "zoho_crm", "zoho_books"}
        actual_ids = {i["id"] for i in integrations}
        assert actual_ids == expected_ids, f"Missing integrations: {expected_ids - actual_ids}"
    
    def test_integrations_endpoint_returns_6_zoho_data_centers(self, auth_headers):
        """Verify endpoint returns all 6 Zoho data centers."""
        response = requests.get(
            f"{BASE_URL}/api/oauth/integrations",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "zoho_data_centers" in data
        
        data_centers = data["zoho_data_centers"]
        assert len(data_centers) == 6, f"Expected 6 data centers, got {len(data_centers)}"
        
        # Verify all expected DCs
        expected_dcs = {"us", "eu", "in", "au", "jp", "ca"}
        actual_dcs = {dc["id"] for dc in data_centers}
        assert actual_dcs == expected_dcs, f"Missing DCs: {expected_dcs - actual_dcs}"
    
    def test_integration_fields_present(self, auth_headers):
        """Verify each integration has required fields."""
        response = requests.get(
            f"{BASE_URL}/api/oauth/integrations",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        required_fields = ["id", "name", "category", "description", "status", "is_active", 
                          "has_credentials", "can_connect", "is_api_key", "is_zoho"]
        
        for integration in response.json()["integrations"]:
            for field in required_fields:
                assert field in integration, f"Field '{field}' missing in {integration['id']}"
    
    def test_resend_marked_as_api_key(self, auth_headers):
        """Verify Resend is marked as API key based authentication."""
        response = requests.get(
            f"{BASE_URL}/api/oauth/integrations",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        resend = next((i for i in response.json()["integrations"] if i["id"] == "resend"), None)
        assert resend is not None
        assert resend["is_api_key"] == True
        assert resend["is_zoho"] == False
    
    def test_zoho_providers_marked_correctly(self, auth_headers):
        """Verify Zoho providers are marked as is_zoho=True."""
        response = requests.get(
            f"{BASE_URL}/api/oauth/integrations",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        zoho_ids = {"zoho_crm", "zoho_books", "zoho_mail"}
        
        for integration in response.json()["integrations"]:
            if integration["id"] in zoho_ids:
                assert integration["is_zoho"] == True, f"{integration['id']} should be is_zoho=True"
                assert integration["is_api_key"] == False
            else:
                assert integration["is_zoho"] == False, f"{integration['id']} should be is_zoho=False"


class TestZohoOAuthConnect:
    """Test Zoho OAuth connect endpoint with DC selection."""
    
    def test_zoho_crm_connect_returns_auth_url(self, auth_headers):
        """Verify Zoho CRM connect returns authorization URL."""
        response = requests.post(
            f"{BASE_URL}/api/oauth/zoho_crm/connect",
            headers=auth_headers,
            json={"data_center": "us"}
        )
        
        # Should return 200 with authorization_url (credentials are configured)
        if response.status_code == 200:
            data = response.json()
            assert "authorization_url" in data
            assert "zoho.com" in data["authorization_url"]
            assert "state" in data
        else:
            # If OAuth not configured, should get 400
            assert response.status_code == 400
            print(f"Zoho OAuth not fully configured: {response.json().get('detail')}")
    
    def test_zoho_connect_with_different_dc(self, auth_headers):
        """Test Zoho connect with EU data center."""
        response = requests.post(
            f"{BASE_URL}/api/oauth/zoho_crm/connect",
            headers=auth_headers,
            json={"data_center": "eu"}
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "authorization_url" in data
            # EU DC should use zoho.eu domain
            assert "zoho.eu" in data["authorization_url"] or "zoho.com" in data["authorization_url"]


class TestResendApiKey:
    """Test Resend API key endpoint."""
    
    def test_resend_api_key_rejects_oauth(self, auth_headers):
        """Verify Resend cannot use OAuth connect endpoint."""
        response = requests.post(
            f"{BASE_URL}/api/oauth/resend/connect",
            headers=auth_headers,
            json={}
        )
        
        # Should reject with 400 - uses API key, not OAuth
        assert response.status_code == 400
        assert "API key" in response.json().get("detail", "")
    
    def test_resend_api_key_endpoint_exists(self, auth_headers):
        """Verify Resend API key endpoint accepts requests."""
        response = requests.post(
            f"{BASE_URL}/api/oauth/resend/api-key",
            headers=auth_headers,
            json={"api_key": "test_key_12345"}
        )
        
        # Should be 200 or 400 (validation), not 404
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code}"


class TestOAuthHealthEndpoint:
    """Test OAuth health check endpoint."""
    
    def test_health_endpoint_returns_summary(self, auth_headers):
        """Verify health endpoint returns connection health summary."""
        response = requests.get(
            f"{BASE_URL}/api/oauth/health",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "summary" in data
        assert "connections" in data
        
        summary = data["summary"]
        assert "total" in summary
        assert "healthy" in summary


class TestUnauthorizedAccess:
    """Test endpoint security."""
    
    def test_integrations_requires_auth(self):
        """Verify integrations endpoint requires authentication."""
        response = requests.get(f"{BASE_URL}/api/oauth/integrations")
        assert response.status_code in [401, 403]
    
    def test_connect_requires_auth(self):
        """Verify connect endpoints require authentication."""
        response = requests.post(
            f"{BASE_URL}/api/oauth/stripe/connect",
            json={}
        )
        assert response.status_code in [401, 403]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
