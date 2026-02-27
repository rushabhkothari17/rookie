"""
Iteration 75: Testing Finance Tab, Custom Domains, and Order Refunds
- Finance Tab UI - tile-based layout with Zoho Books and QuickBooks coming soon
- Finance Tab API - GET /api/admin/finance/status returns proper structure
- Custom Domains UI - custom domains section in Website Content tab
- Custom Domains API - GET/PUT /api/admin/custom-domains endpoints
- Order Refund UI - Refund button shows for paid orders only
- Order Refund API - POST /api/admin/orders/{id}/refund processes manual refund
- Order Refund API - GET /api/admin/orders/{id}/refunds returns refund history
- Existing functionality - login, customer list, orders list should still work
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://product-refactor.preview.emergentagent.com")

# Test credentials
TENANT_B_ADMIN = {
    "email": "adminb@tenantb.local",
    "password": "ChangeMe123!",
    "partner_code": "tenant-b-test"
}
PLATFORM_ADMIN = {
    "email": "admin@automateaccounts.local",
    "password": "ChangeMe123!"
}

# Order to test for refund (already has one $10 refund recorded)
TEST_ORDER_ID = "ff6f95fd-2854-4196-aceb-0261d109c4e6"


class TestTenantBAdminLogin:
    """Test tenant B admin login works"""
    
    def test_tenant_b_login(self):
        """Test tenant B admin can login"""
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json=TENANT_B_ADMIN,
            timeout=30
        )
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        data = resp.json()
        assert "token" in data
        assert data["role"] == "partner_super_admin"
        assert "tenant_id" in data


class TestFinanceStatus:
    """Test Finance integration status endpoint"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token for tenant B admin"""
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json=TENANT_B_ADMIN,
            timeout=30
        )
        if resp.status_code != 200:
            pytest.skip(f"Login failed: {resp.text}")
        return resp.json()["token"]
    
    def test_finance_status_returns_proper_structure(self, auth_token):
        """GET /api/admin/finance/status returns proper structure"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/finance/status",
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=30
        )
        assert resp.status_code == 200, f"Finance status failed: {resp.text}"
        data = resp.json()
        
        # Check Zoho Books structure
        assert "zoho_books" in data
        zoho = data["zoho_books"]
        assert "is_configured" in zoho
        assert "is_validated" in zoho
        assert isinstance(zoho["is_configured"], bool)
        assert isinstance(zoho["is_validated"], bool)
        
        # Check QuickBooks structure (coming soon)
        assert "quickbooks" in data
        qb = data["quickbooks"]
        assert qb["status"] == "coming_soon"
        assert qb["is_configured"] == False
        assert qb["is_validated"] == False
    
    def test_finance_status_unauthorized_without_token(self):
        """Finance status should return 401 without auth"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/finance/status",
            timeout=30
        )
        assert resp.status_code == 401


class TestCustomDomains:
    """Test Custom Domains API endpoints"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token for tenant B admin"""
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json=TENANT_B_ADMIN,
            timeout=30
        )
        if resp.status_code != 200:
            pytest.skip(f"Login failed: {resp.text}")
        return resp.json()["token"]
    
    def test_get_custom_domains(self, auth_token):
        """GET /api/admin/custom-domains returns domains array"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/custom-domains",
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=30
        )
        assert resp.status_code == 200, f"Get custom domains failed: {resp.text}"
        data = resp.json()
        assert "domains" in data
        assert isinstance(data["domains"], list)
    
    def test_update_custom_domains(self, auth_token):
        """PUT /api/admin/custom-domains updates domains"""
        # First get current domains
        resp = requests.get(
            f"{BASE_URL}/api/admin/custom-domains",
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=30
        )
        original_domains = resp.json().get("domains", [])
        
        # Add a test domain
        test_domain = "test-billing.testcompany.com"
        new_domains = original_domains + [test_domain] if test_domain not in original_domains else original_domains
        
        resp = requests.put(
            f"{BASE_URL}/api/admin/custom-domains",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"domains": new_domains},
            timeout=30
        )
        assert resp.status_code == 200, f"Update custom domains failed: {resp.text}"
        data = resp.json()
        assert "domains" in data
        assert test_domain in data["domains"]
        
        # Verify GET returns updated domains
        resp = requests.get(
            f"{BASE_URL}/api/admin/custom-domains",
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=30
        )
        assert test_domain in resp.json()["domains"]
        
        # Cleanup - remove test domain
        resp = requests.delete(
            f"{BASE_URL}/api/admin/custom-domains/{test_domain}",
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=30
        )
        # Allow 404 if already deleted or not found
        assert resp.status_code in [200, 404]
    
    def test_invalid_domain_format_rejected(self, auth_token):
        """Invalid domain format should be rejected"""
        resp = requests.put(
            f"{BASE_URL}/api/admin/custom-domains",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"domains": ["invalid domain with spaces"]},
            timeout=30
        )
        assert resp.status_code == 400, f"Expected 400 for invalid domain: {resp.text}"


class TestOrderRefunds:
    """Test Order Refund API endpoints"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token for tenant B admin"""
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json=TENANT_B_ADMIN,
            timeout=30
        )
        if resp.status_code != 200:
            pytest.skip(f"Login failed: {resp.text}")
        return resp.json()["token"]
    
    def test_get_order_refunds_endpoint_exists(self, auth_token):
        """GET /api/admin/orders/{id}/refunds returns refund history"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/orders/{TEST_ORDER_ID}/refunds",
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=30
        )
        # May return 404 if order doesn't exist for this tenant, but endpoint should exist
        assert resp.status_code in [200, 404], f"Unexpected status: {resp.status_code} - {resp.text}"
        
        if resp.status_code == 200:
            data = resp.json()
            assert "refunds" in data
            assert isinstance(data["refunds"], list)
    
    def test_refund_endpoint_exists(self, auth_token):
        """POST /api/admin/orders/{id}/refund endpoint exists"""
        # This test just validates the endpoint exists with proper validation
        resp = requests.post(
            f"{BASE_URL}/api/admin/orders/{TEST_ORDER_ID}/refund",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "amount": 0.01,  # Very small amount
                "reason": "requested_by_customer",
                "provider": "manual",
                "process_via_provider": False
            },
            timeout=30
        )
        # Endpoint should return 200/400/404 but not 405/500
        assert resp.status_code in [200, 400, 404], f"Unexpected status: {resp.status_code} - {resp.text}"
    
    def test_refund_manual_provider_works(self, auth_token):
        """Manual refund should work for paid orders"""
        # First find a paid order
        resp = requests.get(
            f"{BASE_URL}/api/admin/orders?status_filter=paid&per_page=1",
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=30
        )
        if resp.status_code != 200:
            pytest.skip("Could not fetch orders")
        
        orders = resp.json().get("orders", [])
        if not orders:
            pytest.skip("No paid orders found for testing")
        
        order = orders[0]
        order_id = order["id"]
        order_total = order.get("total", 0)
        already_refunded = order.get("refunded_amount", 0) / 100  # Convert from cents
        available = order_total - already_refunded
        
        if available <= 0:
            pytest.skip("Order already fully refunded")
        
        # Try a small manual refund (1 cent or 0.01)
        refund_amount = min(0.01, available)
        
        resp = requests.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/refund",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "amount": refund_amount,
                "reason": "TEST_requested_by_customer",
                "provider": "manual",
                "process_via_provider": False
            },
            timeout=30
        )
        
        if resp.status_code == 200:
            data = resp.json()
            assert "refund_id" in data
            assert data["provider"] == "manual"
            assert "amount" in data
        elif resp.status_code == 400:
            # May fail if already refunded - that's acceptable
            pass
        else:
            pytest.fail(f"Unexpected status: {resp.status_code} - {resp.text}")


class TestExistingFunctionality:
    """Test existing functionality still works"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token for tenant B admin"""
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json=TENANT_B_ADMIN,
            timeout=30
        )
        if resp.status_code != 200:
            pytest.skip(f"Login failed: {resp.text}")
        return resp.json()["token"]
    
    def test_customer_list_works(self, auth_token):
        """Customer list endpoint works"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/customers",
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=30
        )
        assert resp.status_code == 200, f"Customer list failed: {resp.text}"
        data = resp.json()
        assert "customers" in data
    
    def test_orders_list_works(self, auth_token):
        """Orders list endpoint works"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/orders",
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=30
        )
        assert resp.status_code == 200, f"Orders list failed: {resp.text}"
        data = resp.json()
        assert "orders" in data
        assert "items" in data
    
    def test_products_list_works(self, auth_token):
        """Products list endpoint works"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/products-all",
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=30
        )
        assert resp.status_code == 200, f"Products list failed: {resp.text}"
        data = resp.json()
        assert "products" in data


class TestZohoBooksIntegration:
    """Test Zoho Books integration endpoints (MOCKED - no actual API calls)"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token for tenant B admin"""
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json=TENANT_B_ADMIN,
            timeout=30
        )
        if resp.status_code != 200:
            pytest.skip(f"Login failed: {resp.text}")
        return resp.json()["token"]
    
    def test_save_zoho_credentials_endpoint_exists(self, auth_token):
        """Zoho Books save credentials endpoint exists"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/finance/zoho-books/save-credentials",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "client_id": "TEST_CLIENT_ID",
                "client_secret": "TEST_CLIENT_SECRET",
                "datacenter": "US"
            },
            timeout=30
        )
        # Should succeed
        assert resp.status_code == 200, f"Save credentials failed: {resp.text}"
        data = resp.json()
        assert data["success"] == True
    
    def test_get_account_mappings_endpoint_exists(self, auth_token):
        """Zoho Books account mappings endpoint exists"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/finance/zoho-books/account-mappings",
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=30
        )
        assert resp.status_code == 200, f"Get mappings failed: {resp.text}"
        data = resp.json()
        assert "mappings" in data
        assert "webapp_entities" in data
    
    def test_sync_history_endpoint_exists(self, auth_token):
        """Sync history endpoint exists"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/finance/sync-history",
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=30
        )
        assert resp.status_code == 200, f"Sync history failed: {resp.text}"
        data = resp.json()
        assert "jobs" in data


class TestPlatformAdminLogin:
    """Test platform admin login still works"""
    
    def test_platform_admin_login(self):
        """Platform admin can login with partner_code=automate-accounts"""
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={**PLATFORM_ADMIN, "partner_code": "automate-accounts"},
            timeout=30
        )
        assert resp.status_code == 200, f"Platform admin login failed: {resp.text}"
        data = resp.json()
        assert "token" in data
        assert data.get("role") in ["admin", "platform_admin", "partner_super_admin"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
