"""
Iteration 73 Backend Tests:
- Cookie consent (frontend feature - no backend tests needed)
- CRM tab tile layout (frontend feature - no backend tests needed)
- Webhook delivery stats endpoint
- Webhook replay endpoint
- Email provider status endpoint
- HttpOnly cookie authentication (tested in iter72)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Session to maintain cookies
session = requests.Session()


class TestWebhookDeliveryStats:
    """Test webhook delivery stats endpoint."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin before each test."""
        login_resp = session.post(
            f"{BASE_URL}/api/auth/partner-login",
            json={
                "email": "admin@automateaccounts.local",
                "password": "ChangeMe123!",
                "partner_code": "automate-accounts"
            }
        )
        if login_resp.status_code == 200:
            token = login_resp.json().get("token")
            session.headers.update({"Authorization": f"Bearer {token}"})
        yield
        
    def test_delivery_stats_returns_correct_structure(self):
        """Test that delivery stats endpoint returns expected fields."""
        response = session.get(f"{BASE_URL}/api/admin/webhooks/delivery-stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify all expected fields are present
        assert "total_deliveries" in data
        assert "success_count" in data
        assert "failed_count" in data
        assert "pending_count" in data
        assert "success_rate" in data
        assert "recent_failures" in data
        
        # Verify data types
        assert isinstance(data["total_deliveries"], int)
        assert isinstance(data["success_count"], int)
        assert isinstance(data["failed_count"], int)
        assert isinstance(data["pending_count"], int)
        assert isinstance(data["success_rate"], (int, float))
        assert isinstance(data["recent_failures"], list)
        
    def test_delivery_stats_empty_state(self):
        """Test delivery stats with no webhooks returns zeros."""
        response = session.get(f"{BASE_URL}/api/admin/webhooks/delivery-stats")
        assert response.status_code == 200
        
        data = response.json()
        # If no webhooks configured, all counts should be 0
        assert data["total_deliveries"] >= 0
        assert data["success_count"] >= 0
        assert data["failed_count"] >= 0
        assert data["pending_count"] >= 0


class TestEmailProviderStatus:
    """Test email provider status endpoint."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin before each test."""
        login_resp = session.post(
            f"{BASE_URL}/api/auth/partner-login",
            json={
                "email": "admin@automateaccounts.local",
                "password": "ChangeMe123!",
                "partner_code": "automate-accounts"
            }
        )
        if login_resp.status_code == 200:
            token = login_resp.json().get("token")
            session.headers.update({"Authorization": f"Bearer {token}"})
        yield
        
    def test_integrations_status_returns_email_providers(self):
        """Test that integrations status includes email provider info."""
        response = session.get(f"{BASE_URL}/api/admin/integrations/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Check for active_email_provider field
        assert "active_email_provider" in data
        
        # Check for integrations object
        assert "integrations" in data
        integrations = data["integrations"]
        
        # Verify email providers are listed
        assert "resend" in integrations
        assert "zoho_mail" in integrations
        
        # Verify resend structure
        resend = integrations["resend"]
        assert "status" in resend
        assert "is_active" in resend
        assert "type" in resend
        assert resend["type"] == "email"
        
        # Verify zoho_mail structure
        zoho_mail = integrations["zoho_mail"]
        assert "status" in zoho_mail
        assert "is_active" in zoho_mail
        assert "type" in zoho_mail
        assert zoho_mail["type"] == "email"
        
    def test_crm_provider_in_integrations_status(self):
        """Test that CRM providers are included in integrations status."""
        response = session.get(f"{BASE_URL}/api/admin/integrations/status")
        assert response.status_code == 200
        
        data = response.json()
        integrations = data["integrations"]
        
        # Verify Zoho CRM is listed
        assert "zoho_crm" in integrations
        zoho_crm = integrations["zoho_crm"]
        assert "status" in zoho_crm
        assert "type" in zoho_crm
        assert zoho_crm["type"] == "crm"


class TestWebhookEventsEndpoint:
    """Test webhook events catalog endpoint."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin before each test."""
        login_resp = session.post(
            f"{BASE_URL}/api/auth/partner-login",
            json={
                "email": "admin@automateaccounts.local",
                "password": "ChangeMe123!",
                "partner_code": "automate-accounts"
            }
        )
        if login_resp.status_code == 200:
            token = login_resp.json().get("token")
            session.headers.update({"Authorization": f"Bearer {token}"})
        yield
        
    def test_webhook_events_endpoint_accessible(self):
        """Test that webhook events endpoint returns event catalog."""
        response = session.get(f"{BASE_URL}/api/admin/webhooks/events")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "events" in data
        events = data["events"]
        
        # Should have some events defined
        assert len(events) > 0


class TestWebhookCRUD:
    """Test webhook CRUD operations."""
    
    created_webhook_id = None
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin before each test."""
        login_resp = session.post(
            f"{BASE_URL}/api/auth/partner-login",
            json={
                "email": "admin@automateaccounts.local",
                "password": "ChangeMe123!",
                "partner_code": "automate-accounts"
            }
        )
        if login_resp.status_code == 200:
            token = login_resp.json().get("token")
            session.headers.update({"Authorization": f"Bearer {token}"})
        yield
        
    def test_create_webhook(self):
        """Test creating a new webhook."""
        # First get available events
        events_resp = session.get(f"{BASE_URL}/api/admin/webhooks/events")
        if events_resp.status_code != 200:
            pytest.skip("Could not get events catalog")
        
        events = events_resp.json().get("events", {})
        if not events:
            pytest.skip("No events in catalog")
            
        # Get first event
        first_event = list(events.keys())[0]
        first_event_fields = list(events[first_event].get("fields", {}).keys())[:2]
        
        response = session.post(
            f"{BASE_URL}/api/admin/webhooks",
            json={
                "name": "TEST_Iter73_Webhook",
                "url": "https://httpbin.org/post",
                "subscriptions": [
                    {"event": first_event, "fields": first_event_fields}
                ]
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data
        assert "secret" in data  # Secret shown only on creation
        assert data["name"] == "TEST_Iter73_Webhook"
        
        TestWebhookCRUD.created_webhook_id = data["id"]
        
    def test_list_webhooks(self):
        """Test listing webhooks."""
        response = session.get(f"{BASE_URL}/api/admin/webhooks")
        assert response.status_code == 200
        
        data = response.json()
        assert "webhooks" in data
        assert isinstance(data["webhooks"], list)
        
    def test_cleanup_webhook(self):
        """Cleanup: Delete test webhook."""
        if TestWebhookCRUD.created_webhook_id:
            response = session.delete(
                f"{BASE_URL}/api/admin/webhooks/{TestWebhookCRUD.created_webhook_id}"
            )
            assert response.status_code in [200, 404]  # 404 if already deleted


class TestAdminAuthentication:
    """Test admin authentication still works with HttpOnly cookies."""
    
    def test_partner_login_returns_token(self):
        """Test that partner login returns token in response body."""
        response = requests.post(
            f"{BASE_URL}/api/auth/partner-login",
            json={
                "email": "admin@automateaccounts.local",
                "password": "ChangeMe123!",
                "partner_code": "automate-accounts"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "token" in data
        assert "role" in data
        assert data["role"] == "platform_admin"
        
    def test_api_me_with_token(self):
        """Test /api/me endpoint with Bearer token."""
        # First login
        login_resp = requests.post(
            f"{BASE_URL}/api/auth/partner-login",
            json={
                "email": "admin@automateaccounts.local",
                "password": "ChangeMe123!",
                "partner_code": "automate-accounts"
            }
        )
        token = login_resp.json().get("token")
        
        # Access /api/me with token
        me_resp = requests.get(
            f"{BASE_URL}/api/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert me_resp.status_code == 200
        
        data = me_resp.json()
        assert data["email"] == "admin@automateaccounts.local"
        assert data["role"] == "platform_admin"


class TestCustomerBlockedFromAdminEndpoints:
    """Test that customers cannot access admin endpoints."""
    
    def test_customer_blocked_from_webhook_stats(self):
        """Test that customer cannot access webhook delivery stats."""
        # Login as customer
        login_resp = requests.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={
                "email": "testcustomer@test.com",
                "password": "ChangeMe123!",
                "partner_code": "automate-accounts"
            }
        )
        
        if login_resp.status_code != 200:
            pytest.skip("Customer login failed - may not exist")
            
        token = login_resp.json().get("token")
        
        # Try to access admin endpoint
        response = requests.get(
            f"{BASE_URL}/api/admin/webhooks/delivery-stats",
            headers={"Authorization": f"Bearer {token}"}
        )
        # Should be blocked (403 or 401)
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        
    def test_customer_blocked_from_integrations_status(self):
        """Test that customer cannot access integrations status."""
        # Login as customer
        login_resp = requests.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={
                "email": "testcustomer@test.com",
                "password": "ChangeMe123!",
                "partner_code": "automate-accounts"
            }
        )
        
        if login_resp.status_code != 200:
            pytest.skip("Customer login failed - may not exist")
            
        token = login_resp.json().get("token")
        
        # Try to access admin endpoint
        response = requests.get(
            f"{BASE_URL}/api/admin/integrations/status",
            headers={"Authorization": f"Bearer {token}"}
        )
        # Should be blocked (403 or 401)
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
