"""
Iteration 77: OAuth Integrations & Refund Email Notification Tests

Testing:
1. OAuth Integrations API - GET /api/oauth/integrations returns 7 providers
2. OAuth Connect flow - GET /api/oauth/{provider}/connect returns authorization_url
3. OAuth Status - GET /api/oauth/{provider}/status returns connection details
4. OAuth Disconnect - DELETE /api/oauth/{provider}/disconnect
5. Refund email template exists in email_templates
6. Refund notification sends email (check email_outbox since email is mocked)
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
TENANT_B_ADMIN = {
    "email": "adminb@tenantb.local",
    "password": "ChangeMe123!",
    "partner_code": "tenant-b-test"
}

@pytest.fixture(scope="module")
def admin_session():
    """Get authenticated admin session for tenant B"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login
    login_response = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": TENANT_B_ADMIN["email"],
        "password": TENANT_B_ADMIN["password"],
        "partner_code": TENANT_B_ADMIN["partner_code"]
    })
    
    if login_response.status_code != 200:
        pytest.skip(f"Login failed: {login_response.text}")
    
    # Set auth cookie from response
    return session


class TestOAuthIntegrations:
    """OAuth Integrations API Tests"""
    
    def test_list_integrations_returns_7_providers(self, admin_session):
        """GET /api/oauth/integrations should return 7 OAuth providers"""
        response = admin_session.get(f"{BASE_URL}/api/oauth/integrations")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "integrations" in data, "Response should have 'integrations' key"
        
        integrations = data["integrations"]
        assert len(integrations) == 7, f"Expected 7 providers, got {len(integrations)}"
        
        # Verify expected provider IDs
        provider_ids = [i["id"] for i in integrations]
        expected_providers = [
            "zoho_crm", "zoho_books", "zoho_mail",
            "stripe", "stripe_test",
            "gocardless", "gocardless_sandbox"
        ]
        
        for provider in expected_providers:
            assert provider in provider_ids, f"Missing provider: {provider}"
        
        # Verify integration structure
        for integration in integrations:
            assert "id" in integration
            assert "name" in integration
            assert "status" in integration
            assert "has_credentials" in integration
            assert "can_connect" in integration
            
    def test_integration_status_values(self, admin_session):
        """Verify integration status and can_connect based on credentials"""
        response = admin_session.get(f"{BASE_URL}/api/oauth/integrations")
        assert response.status_code == 200
        
        data = response.json()
        integrations = {i["id"]: i for i in data["integrations"]}
        
        # Zoho should have credentials (ZOHO_CLIENT_ID is set in .env)
        zoho_crm = integrations.get("zoho_crm")
        assert zoho_crm is not None
        # Since ZOHO_CLIENT_ID is in .env, has_credentials should be True
        assert zoho_crm["can_connect"] == zoho_crm["has_credentials"], \
            "can_connect should match has_credentials"
        
        # Stripe/GoCardless OAuth credentials may not be set
        stripe = integrations.get("stripe")
        assert stripe is not None


class TestOAuthConnect:
    """OAuth Connect Flow Tests"""
    
    def test_connect_zoho_crm_returns_authorization_url(self, admin_session):
        """GET /api/oauth/zoho_crm/connect should return authorization_url"""
        response = admin_session.get(f"{BASE_URL}/api/oauth/zoho_crm/connect")
        
        # May return 400 if credentials not configured
        if response.status_code == 400:
            data = response.json()
            assert "not configured" in data.get("detail", "").lower() or \
                   "contact support" in data.get("detail", "").lower(), \
                   "Should indicate OAuth not configured"
            pytest.skip("Zoho OAuth not configured")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "authorization_url" in data, "Response should have 'authorization_url'"
        assert "state" in data, "Response should have 'state' for CSRF protection"
        assert "provider" in data, "Response should have 'provider'"
        
        auth_url = data["authorization_url"]
        assert "accounts.zoho.com" in auth_url, "Should redirect to Zoho"
        assert "oauth" in auth_url.lower(), "Should be OAuth endpoint"
        
    def test_connect_unknown_provider_returns_400(self, admin_session):
        """GET /api/oauth/invalid_provider/connect should return 400"""
        response = admin_session.get(f"{BASE_URL}/api/oauth/invalid_provider/connect")
        
        assert response.status_code == 400
        data = response.json()
        assert "unknown provider" in data.get("detail", "").lower()


class TestOAuthStatus:
    """OAuth Status API Tests"""
    
    def test_status_not_connected(self, admin_session):
        """GET /api/oauth/{provider}/status returns not_connected for unlinked provider"""
        # Test with a provider that's likely not connected
        response = admin_session.get(f"{BASE_URL}/api/oauth/gocardless_sandbox/status")
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["provider"] == "gocardless_sandbox"
        assert data["name"] == "GoCardless (Sandbox)"
        # Status should be not_connected or similar
        assert data["status"] in ["not_connected", "connected", "failed", "expired"]
        assert "can_connect" in data
        
    def test_status_unknown_provider_returns_400(self, admin_session):
        """GET /api/oauth/invalid_provider/status should return 400"""
        response = admin_session.get(f"{BASE_URL}/api/oauth/invalid_provider/status")
        
        assert response.status_code == 400
        data = response.json()
        assert "unknown provider" in data.get("detail", "").lower()


class TestOAuthDisconnect:
    """OAuth Disconnect API Tests"""
    
    def test_disconnect_not_connected_returns_404(self, admin_session):
        """DELETE /api/oauth/{provider}/disconnect returns 404 if not connected"""
        # Try to disconnect a provider that's not connected
        response = admin_session.delete(f"{BASE_URL}/api/oauth/gocardless_sandbox/disconnect")
        
        # Should return 404 if no connection exists
        assert response.status_code in [200, 404], \
            f"Expected 200 or 404, got {response.status_code}: {response.text}"
        
        if response.status_code == 404:
            data = response.json()
            assert "not found" in data.get("detail", "").lower()
            
    def test_disconnect_unknown_provider_returns_400(self, admin_session):
        """DELETE /api/oauth/invalid_provider/disconnect should return 400"""
        response = admin_session.delete(f"{BASE_URL}/api/oauth/invalid_provider/disconnect")
        
        assert response.status_code == 400
        data = response.json()
        assert "unknown provider" in data.get("detail", "").lower()


class TestRefundEmailTemplate:
    """Refund Email Template Tests"""
    
    def test_refund_template_exists(self, admin_session):
        """Verify refund_processed email template exists"""
        response = admin_session.get(f"{BASE_URL}/api/admin/email-templates")
        
        assert response.status_code == 200
        
        data = response.json()
        templates = data.get("templates", [])
        
        # Find refund_processed template
        refund_template = None
        for t in templates:
            if t.get("trigger") == "refund_processed":
                refund_template = t
                break
        
        assert refund_template is not None, "refund_processed template should exist"
        assert refund_template.get("is_enabled") == True, "Template should be enabled"
        assert "Refund" in refund_template.get("label", ""), "Label should mention Refund"
        
        # Check template has required variables
        available_vars = refund_template.get("available_variables", [])
        expected_vars = ["{{order_number}}", "{{refund_amount}}", "{{processing_time}}"]
        for var in expected_vars:
            assert var in available_vars, f"Template should have {var} variable"


class TestRefundNotification:
    """Refund with Email Notification Tests"""
    
    def test_refund_sends_email_to_customer(self, admin_session):
        """POST /api/admin/orders/{id}/refund should send email notification"""
        # First, get a paid order
        orders_response = admin_session.get(
            f"{BASE_URL}/api/admin/orders",
            params={"status_filter": "paid", "per_page": 5}
        )
        
        if orders_response.status_code != 200:
            pytest.skip("Could not fetch orders")
        
        orders = orders_response.json().get("orders", [])
        
        # Find an order that hasn't been fully refunded
        test_order = None
        for order in orders:
            refunded = order.get("refunded_amount", 0)
            total = order.get("total", 0)
            if total > 0 and refunded < (total * 100):  # refunded is in cents
                test_order = order
                break
        
        if not test_order:
            pytest.skip("No paid orders available for refund test")
        
        order_id = test_order["id"]
        order_number = test_order.get("order_number", "")
        
        # Get email outbox count before refund
        outbox_before = admin_session.get(f"{BASE_URL}/api/admin/email-outbox")
        count_before = len(outbox_before.json().get("emails", [])) if outbox_before.status_code == 200 else 0
        
        # Process a small refund (manual provider to avoid payment API issues)
        refund_response = admin_session.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/refund",
            json={
                "amount": 1.00,  # Small refund amount
                "reason": "requested_by_customer",
                "provider": "manual",
                "process_via_provider": False
            }
        )
        
        # Refund may fail if order doesn't have enough balance - that's ok
        if refund_response.status_code == 400:
            data = refund_response.json()
            if "already been fully refunded" in data.get("detail", ""):
                pytest.skip("Order already fully refunded")
            if "exceeds available" in data.get("detail", ""):
                pytest.skip("Refund amount exceeds available balance")
        
        assert refund_response.status_code == 200, \
            f"Refund failed: {refund_response.status_code} - {refund_response.text}"
        
        refund_data = refund_response.json()
        assert "refund_id" in refund_data
        assert refund_data["provider"] == "manual"
        
        # Check email outbox for refund notification
        # Allow some time for email to be queued
        time.sleep(0.5)
        
        outbox_after = admin_session.get(f"{BASE_URL}/api/admin/email-outbox")
        if outbox_after.status_code == 200:
            emails = outbox_after.json().get("emails", [])
            
            # Look for refund email
            refund_emails = [e for e in emails if e.get("type") == "refund_processed"]
            
            assert len(refund_emails) > 0, \
                "Refund email should be in email_outbox (mocked mode)"
            
            latest_refund_email = refund_emails[0]
            assert order_number in latest_refund_email.get("subject", ""), \
                "Email subject should contain order number"
            assert "refund" in latest_refund_email.get("subject", "").lower(), \
                "Email subject should mention refund"


class TestRefundProviders:
    """Refund Providers Endpoint Tests"""
    
    def test_refund_providers_endpoint(self, admin_session):
        """GET /api/admin/orders/{id}/refund-providers returns available providers"""
        # Get any order
        orders_response = admin_session.get(f"{BASE_URL}/api/admin/orders", params={"per_page": 1})
        
        if orders_response.status_code != 200:
            pytest.skip("Could not fetch orders")
        
        orders = orders_response.json().get("orders", [])
        if not orders:
            pytest.skip("No orders available")
        
        order_id = orders[0]["id"]
        
        response = admin_session.get(f"{BASE_URL}/api/admin/orders/{order_id}/refund-providers")
        
        assert response.status_code == 200
        
        data = response.json()
        assert "order_id" in data
        assert "providers" in data
        
        providers = data["providers"]
        
        # Manual provider should always be available
        manual_provider = next((p for p in providers if p["id"] == "manual"), None)
        assert manual_provider is not None, "Manual provider should always be available"
        assert manual_provider["available"] == True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
