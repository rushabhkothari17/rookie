"""
Iteration 71 - Comprehensive Security Sweep for Multi-Tenant SaaS Platform

Tests for:
1. IDOR Prevention - Cannot access/modify another tenant's data
2. Orders Update - customer_id and subscription_id must belong to same tenant
3. Subscriptions Update - customer_id must belong to same tenant
4. Bank Transactions - linked_order_id must belong to same tenant
5. Admin Tab Visibility - customers should NOT see Admin tab, admins SHOULD see it
6. Partner Code Display - partner_code displays correctly in user profile
7. Cross-Tenant Data Isolation - Tenant A cannot reference Tenant B's resources
"""
import pytest
import requests
import os
from typing import Optional

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Tenant A (default tenant) - automate-accounts
# NOTE: admin@automateaccounts.local is platform_admin (sees all) - use for specific tests
TENANT_A_PLATFORM_ADMIN_EMAIL = "admin@automateaccounts.local"
TENANT_A_PLATFORM_ADMIN_PASSWORD = "ChangeMe123!"
TENANT_A_PARTNER_CODE = "automate-accounts"
TENANT_A_ID = "automate-accounts"

# Customer user in Tenant A
TENANT_A_CUSTOMER_EMAIL = "testcustomer@test.com"
TENANT_A_CUSTOMER_PASSWORD = "ChangeMe123!"

# Tenant B - separate tenant for cross-tenant testing
# This is a proper tenant-scoped admin (partner_super_admin with tenant_id set)
TENANT_B_ADMIN_EMAIL = "adminb@tenantb.local"
TENANT_B_ADMIN_PASSWORD = "ChangeMe123!"
TENANT_B_PARTNER_CODE = "tenant-b-test"
TENANT_B_ID = "e7301988-7f0f-4b2b-a678-4e37882e385f"

# For IDOR tests, we use Tenant B admin to try to access Tenant A data
# This is the proper security test - a tenant-scoped admin trying cross-tenant access


def get_admin_token(email, password, partner_code=None):
    """Get admin token via partner-login endpoint."""
    payload = {"email": email, "password": password}
    if partner_code:
        payload["partner_code"] = partner_code
    
    resp = requests.post(f"{BASE_URL}/api/auth/login", json=payload)
    if resp.status_code != 200:
        resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json=payload)
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    return resp.json().get("token") or resp.json().get("access_token")


def get_customer_token(email, password, partner_code):
    """Get customer token via customer-login endpoint."""
    payload = {"email": email, "password": password, "partner_code": partner_code}
    
    # Try partner-login first, expect it to fail for customers with 403
    resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json=payload)
    if resp.status_code == 403:
        # Fall back to customer-login
        resp = requests.post(f"{BASE_URL}/api/auth/customer-login", json=payload)
    
    assert resp.status_code == 200, f"Customer login failed for {email}: {resp.status_code} - {resp.text}"
    return resp.json().get("token") or resp.json().get("access_token")


@pytest.fixture(scope="module")
def tenant_a_admin_token():
    """Platform admin token for Tenant A (can see all data by design)."""
    return get_admin_token(TENANT_A_PLATFORM_ADMIN_EMAIL, TENANT_A_PLATFORM_ADMIN_PASSWORD, TENANT_A_PARTNER_CODE)


@pytest.fixture(scope="module")
def tenant_a_customer_token():
    """Customer token for Tenant A."""
    return get_customer_token(TENANT_A_CUSTOMER_EMAIL, TENANT_A_CUSTOMER_PASSWORD, TENANT_A_PARTNER_CODE)


@pytest.fixture(scope="module")
def tenant_b_admin_token():
    """Admin token for Tenant B (tenant-b-test)."""
    return get_admin_token(TENANT_B_ADMIN_EMAIL, TENANT_B_ADMIN_PASSWORD, TENANT_B_PARTNER_CODE)


# ============================================================================
# 1. ADMIN TAB VISIBILITY TESTS
# ============================================================================

class TestAdminTabVisibility:
    """
    Verify Admin tab visibility based on is_admin flag.
    - Customers (is_admin=false) should NOT see Admin tab
    - Admins (is_admin=true) SHOULD see Admin tab
    """

    def test_customer_has_is_admin_false(self, tenant_a_customer_token):
        """Customer's /me response should have is_admin=false."""
        resp = requests.get(
            f"{BASE_URL}/api/me",
            headers={"Authorization": f"Bearer {tenant_a_customer_token}"}
        )
        assert resp.status_code == 200, f"/me failed: {resp.text}"
        data = resp.json()
        user = data.get("user", {})
        
        assert user.get("is_admin") is False, f"Customer should have is_admin=false, got: {user.get('is_admin')}"
        assert user.get("role") == "customer", f"Customer should have role='customer', got: {user.get('role')}"
        print(f"PASS - Customer {user.get('email')} has is_admin=false, role=customer")

    def test_admin_has_is_admin_true(self, tenant_a_admin_token):
        """Admin's /me response should have is_admin=true."""
        resp = requests.get(
            f"{BASE_URL}/api/me",
            headers={"Authorization": f"Bearer {tenant_a_admin_token}"}
        )
        assert resp.status_code == 200, f"/me failed: {resp.text}"
        data = resp.json()
        user = data.get("user", {})
        
        # Admin roles are NOT "customer" - they are admin, super_admin, or platform_admin
        assert user.get("role") != "customer", f"Admin should NOT have role='customer', got: {user.get('role')}"
        # is_admin should be true for non-customer roles
        assert user.get("is_admin") is True, f"Admin should have is_admin=true, got: {user.get('is_admin')}"
        print(f"PASS - Admin {user.get('email')} has is_admin=true, role={user.get('role')}")

    def test_customer_cannot_access_admin_endpoints(self, tenant_a_customer_token):
        """Customers should be blocked from admin endpoints with 403."""
        admin_endpoints = [
            "/api/admin/orders",
            "/api/admin/subscriptions",
            "/api/admin/customers",
            "/api/admin/bank-transactions",
        ]
        
        for endpoint in admin_endpoints:
            resp = requests.get(
                f"{BASE_URL}{endpoint}",
                headers={"Authorization": f"Bearer {tenant_a_customer_token}"}
            )
            assert resp.status_code == 403, f"Customer should get 403 on {endpoint}, got {resp.status_code}"
        
        print(f"PASS - Customer blocked from all {len(admin_endpoints)} admin endpoints with 403")


# ============================================================================
# 2. PARTNER CODE DISPLAY TESTS
# ============================================================================

class TestPartnerCodeDisplay:
    """Verify partner_code displays correctly in user profile."""

    def test_customer_profile_has_partner_code(self, tenant_a_customer_token):
        """Customer's /me should include partner_code resolved from tenant."""
        resp = requests.get(
            f"{BASE_URL}/api/me",
            headers={"Authorization": f"Bearer {tenant_a_customer_token}"}
        )
        assert resp.status_code == 200, f"/me failed: {resp.text}"
        data = resp.json()
        user = data.get("user", {})
        
        partner_code = user.get("partner_code")
        # Customer should have partner_code set from their tenant
        assert partner_code is not None, f"Customer should have partner_code, got None"
        assert partner_code == TENANT_A_PARTNER_CODE, f"Expected partner_code='{TENANT_A_PARTNER_CODE}', got '{partner_code}'"
        print(f"PASS - Customer has partner_code='{partner_code}'")

    def test_admin_profile_has_partner_code(self, tenant_a_admin_token):
        """Admin's /me should include partner_code."""
        resp = requests.get(
            f"{BASE_URL}/api/me",
            headers={"Authorization": f"Bearer {tenant_a_admin_token}"}
        )
        assert resp.status_code == 200, f"/me failed: {resp.text}"
        data = resp.json()
        user = data.get("user", {})
        
        partner_code = user.get("partner_code")
        tenant_id = user.get("tenant_id")
        
        # Platform admins may have null tenant_id → partner_code might be null/empty
        # Regular tenant admins should have partner_code
        print(f"Admin has partner_code='{partner_code}', tenant_id='{tenant_id}'")
        
        if tenant_id:
            assert partner_code is not None, f"Tenant admin should have partner_code"
        # Platform admins with null tenant_id showing '—' is expected behavior

    def test_tenant_b_admin_has_correct_partner_code(self, tenant_b_admin_token):
        """Tenant B admin should have Tenant B's partner_code."""
        resp = requests.get(
            f"{BASE_URL}/api/me",
            headers={"Authorization": f"Bearer {tenant_b_admin_token}"}
        )
        assert resp.status_code == 200, f"/me failed: {resp.text}"
        data = resp.json()
        user = data.get("user", {})
        
        partner_code = user.get("partner_code")
        assert partner_code == TENANT_B_PARTNER_CODE, f"Expected partner_code='{TENANT_B_PARTNER_CODE}', got '{partner_code}'"
        print(f"PASS - Tenant B admin has partner_code='{partner_code}'")


# ============================================================================
# 3. ORDERS UPDATE - IDOR PREVENTION (customer_id, subscription_id)
# ============================================================================

class TestOrdersUpdateTenantIsolation:
    """
    Test that orders.update validates customer_id and subscription_id belong to same tenant.
    Tenant A admin should NOT be able to set customer_id or subscription_id to Tenant B's resources.
    """

    @pytest.fixture(scope="class")
    def tenant_a_order_id(self, tenant_a_admin_token):
        """Get an existing order ID from Tenant A."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/orders?per_page=1",
            headers={"Authorization": f"Bearer {tenant_a_admin_token}"}
        )
        assert resp.status_code == 200, f"Failed to get orders: {resp.text}"
        orders = resp.json().get("orders", [])
        if not orders:
            pytest.skip("No orders available in Tenant A for testing")
        return orders[0]["id"]

    @pytest.fixture(scope="class")
    def tenant_b_customer_id(self, tenant_b_admin_token):
        """Get a customer ID from Tenant B."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/customers?per_page=1",
            headers={"Authorization": f"Bearer {tenant_b_admin_token}"}
        )
        assert resp.status_code == 200, f"Failed to get Tenant B customers: {resp.text}"
        customers = resp.json().get("customers", [])
        if not customers:
            pytest.skip("No customers available in Tenant B for testing")
        return customers[0]["id"]

    @pytest.fixture(scope="class")
    def tenant_b_subscription_id(self, tenant_b_admin_token):
        """Get a subscription ID from Tenant B."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/subscriptions?per_page=1",
            headers={"Authorization": f"Bearer {tenant_b_admin_token}"}
        )
        assert resp.status_code == 200, f"Failed to get Tenant B subscriptions: {resp.text}"
        subs = resp.json().get("subscriptions", [])
        if not subs:
            pytest.skip("No subscriptions available in Tenant B for testing")
        return subs[0]["id"]

    def test_cannot_update_order_with_tenant_b_customer_id(
        self, tenant_a_admin_token, tenant_a_order_id, tenant_b_customer_id
    ):
        """
        CRITICAL IDOR TEST: Tenant A admin cannot assign Tenant B's customer_id to Tenant A order.
        Should return 400 with 'Invalid customer_id' error.
        """
        resp = requests.put(
            f"{BASE_URL}/api/admin/orders/{tenant_a_order_id}",
            json={"customer_id": tenant_b_customer_id},
            headers={"Authorization": f"Bearer {tenant_a_admin_token}"}
        )
        
        # Should be blocked with 400
        assert resp.status_code == 400, (
            f"SECURITY BUG: Tenant A admin was able to set Tenant B customer_id! "
            f"Expected 400, got {resp.status_code}: {resp.text}"
        )
        
        error_detail = resp.json().get("detail", "")
        assert "customer" in error_detail.lower() or "tenant" in error_detail.lower(), (
            f"Error should mention customer/tenant validation, got: {error_detail}"
        )
        print(f"PASS - Cross-tenant customer_id blocked on order update: {error_detail}")

    def test_cannot_update_order_with_tenant_b_subscription_id(
        self, tenant_a_admin_token, tenant_a_order_id, tenant_b_subscription_id
    ):
        """
        CRITICAL IDOR TEST: Tenant A admin cannot assign Tenant B's subscription_id to Tenant A order.
        Should return 400 with 'Invalid subscription_id' error.
        """
        resp = requests.put(
            f"{BASE_URL}/api/admin/orders/{tenant_a_order_id}",
            json={"subscription_id": tenant_b_subscription_id},
            headers={"Authorization": f"Bearer {tenant_a_admin_token}"}
        )
        
        # The backend may not validate subscription_id for cross-tenant - let's check
        # If it returns 200, that's a SECURITY BUG
        if resp.status_code == 200:
            print(f"WARNING: subscription_id update returned 200 - checking if validation is in place")
            # Verify if subscription_number was auto-resolved (which would indicate lookup happened)
            # If no subscription found in tenant scope, subscription_number shouldn't be set
        
        # Expected: 400 or similar rejection
        assert resp.status_code in [400, 404], (
            f"Expected 400/404 for cross-tenant subscription_id, got {resp.status_code}: {resp.text}"
        )
        print(f"PASS - Cross-tenant subscription_id validation in place: {resp.status_code}")


# ============================================================================
# 4. SUBSCRIPTIONS UPDATE - IDOR PREVENTION (customer_id)
# ============================================================================

class TestSubscriptionsUpdateTenantIsolation:
    """
    Test that subscriptions.update validates customer_id belongs to same tenant.
    Tenant A admin should NOT be able to set customer_id to Tenant B's customer.
    """

    @pytest.fixture(scope="class")
    def tenant_a_subscription_id(self, tenant_a_admin_token):
        """Get an existing subscription ID from Tenant A."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/subscriptions?per_page=1",
            headers={"Authorization": f"Bearer {tenant_a_admin_token}"}
        )
        assert resp.status_code == 200, f"Failed to get subscriptions: {resp.text}"
        subs = resp.json().get("subscriptions", [])
        if not subs:
            pytest.skip("No subscriptions available in Tenant A for testing")
        return subs[0]["id"]

    @pytest.fixture(scope="class")
    def tenant_b_customer_id(self, tenant_b_admin_token):
        """Get a customer ID from Tenant B."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/customers?per_page=1",
            headers={"Authorization": f"Bearer {tenant_b_admin_token}"}
        )
        assert resp.status_code == 200, f"Failed to get Tenant B customers: {resp.text}"
        customers = resp.json().get("customers", [])
        if not customers:
            pytest.skip("No customers available in Tenant B for testing")
        return customers[0]["id"]

    def test_cannot_update_subscription_with_tenant_b_customer_id(
        self, tenant_a_admin_token, tenant_a_subscription_id, tenant_b_customer_id
    ):
        """
        CRITICAL IDOR TEST: Tenant A admin cannot assign Tenant B's customer_id to Tenant A subscription.
        Should return 400 with 'Invalid customer_id' error.
        """
        resp = requests.put(
            f"{BASE_URL}/api/admin/subscriptions/{tenant_a_subscription_id}",
            json={"customer_id": tenant_b_customer_id},
            headers={"Authorization": f"Bearer {tenant_a_admin_token}"}
        )
        
        # Should be blocked with 400
        assert resp.status_code == 400, (
            f"SECURITY BUG: Tenant A admin was able to set Tenant B customer_id on subscription! "
            f"Expected 400, got {resp.status_code}: {resp.text}"
        )
        
        error_detail = resp.json().get("detail", "")
        assert "customer" in error_detail.lower() or "tenant" in error_detail.lower(), (
            f"Error should mention customer/tenant validation, got: {error_detail}"
        )
        print(f"PASS - Cross-tenant customer_id blocked on subscription update: {error_detail}")


# ============================================================================
# 5. BANK TRANSACTIONS - IDOR PREVENTION (linked_order_id)
# ============================================================================

class TestBankTransactionsTenantIsolation:
    """
    Test that bank_transactions create validates linked_order_id belongs to same tenant.
    Tenant A admin should NOT be able to link to Tenant B's order.
    """

    @pytest.fixture(scope="class")
    def tenant_b_order_id(self, tenant_b_admin_token):
        """Get an order ID from Tenant B."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/orders?per_page=1",
            headers={"Authorization": f"Bearer {tenant_b_admin_token}"}
        )
        assert resp.status_code == 200, f"Failed to get Tenant B orders: {resp.text}"
        orders = resp.json().get("orders", [])
        if not orders:
            pytest.skip("No orders available in Tenant B for testing")
        return orders[0]["id"]

    def test_cannot_create_bank_transaction_with_tenant_b_order(
        self, tenant_a_admin_token, tenant_b_order_id
    ):
        """
        CRITICAL IDOR TEST: Tenant A admin cannot create bank transaction linked to Tenant B's order.
        Should return 400 with 'Invalid linked_order_id' error.
        """
        from datetime import datetime, timezone
        
        resp = requests.post(
            f"{BASE_URL}/api/admin/bank-transactions",
            json={
                "date": datetime.now(timezone.utc).isoformat(),
                "source": "manual",
                "transaction_id": "TEST_IDOR_CHECK",
                "type": "credit",
                "amount": 100.00,
                "status": "completed",
                "description": "IDOR test transaction",
                "linked_order_id": tenant_b_order_id,  # Cross-tenant order ID!
            },
            headers={"Authorization": f"Bearer {tenant_a_admin_token}"}
        )
        
        # Should be blocked with 400
        assert resp.status_code == 400, (
            f"SECURITY BUG: Tenant A admin was able to link bank transaction to Tenant B order! "
            f"Expected 400, got {resp.status_code}: {resp.text}"
        )
        
        error_detail = resp.json().get("detail", "")
        assert "order" in error_detail.lower() or "tenant" in error_detail.lower(), (
            f"Error should mention order/tenant validation, got: {error_detail}"
        )
        print(f"PASS - Cross-tenant linked_order_id blocked on bank transaction create: {error_detail}")

    def test_can_create_bank_transaction_without_linked_order(self, tenant_a_admin_token):
        """Bank transaction without linked_order_id should work (null is valid)."""
        from datetime import datetime, timezone
        
        resp = requests.post(
            f"{BASE_URL}/api/admin/bank-transactions",
            json={
                "date": datetime.now(timezone.utc).isoformat(),
                "source": "manual",
                "transaction_id": f"TEST_NO_ORDER_{datetime.now().timestamp()}",
                "type": "credit",
                "amount": 50.00,
                "status": "pending",
                "description": "Transaction without linked order",
                # No linked_order_id - should be allowed
            },
            headers={"Authorization": f"Bearer {tenant_a_admin_token}"}
        )
        
        assert resp.status_code == 200, f"Failed to create transaction without linked_order: {resp.text}"
        txn_id = resp.json().get("transaction", {}).get("id")
        print(f"PASS - Bank transaction created without linked_order_id: {txn_id}")
        
        # Cleanup
        if txn_id:
            requests.delete(
                f"{BASE_URL}/api/admin/bank-transactions/{txn_id}",
                headers={"Authorization": f"Bearer {tenant_a_admin_token}"}
            )


# ============================================================================
# 6. CROSS-TENANT DATA ACCESS PREVENTION
# ============================================================================

class TestCrossTenantDataAccess:
    """
    Verify Tenant A admin cannot directly access Tenant B's resources.
    """

    def test_tenant_a_cannot_see_tenant_b_orders(self, tenant_a_admin_token, tenant_b_admin_token):
        """Tenant A admin should not see Tenant B's orders in their list."""
        # Get Tenant B's orders
        resp_b = requests.get(
            f"{BASE_URL}/api/admin/orders?per_page=100",
            headers={"Authorization": f"Bearer {tenant_b_admin_token}"}
        )
        assert resp_b.status_code == 200
        tenant_b_order_ids = {o["id"] for o in resp_b.json().get("orders", [])}
        
        if not tenant_b_order_ids:
            pytest.skip("No Tenant B orders to test")
        
        # Get Tenant A's orders
        resp_a = requests.get(
            f"{BASE_URL}/api/admin/orders?per_page=100",
            headers={"Authorization": f"Bearer {tenant_a_admin_token}"}
        )
        assert resp_a.status_code == 200
        tenant_a_order_ids = {o["id"] for o in resp_a.json().get("orders", [])}
        
        # Tenant B orders should NOT appear in Tenant A's list
        leaked_orders = tenant_b_order_ids & tenant_a_order_ids
        assert not leaked_orders, (
            f"SECURITY BUG: Tenant B orders leaked to Tenant A: {leaked_orders}"
        )
        print(f"PASS - Tenant B orders ({len(tenant_b_order_ids)}) not visible to Tenant A")

    def test_tenant_a_cannot_see_tenant_b_customers(self, tenant_a_admin_token, tenant_b_admin_token):
        """Tenant A admin should not see Tenant B's customers."""
        # Get Tenant B's customers
        resp_b = requests.get(
            f"{BASE_URL}/api/admin/customers?per_page=100",
            headers={"Authorization": f"Bearer {tenant_b_admin_token}"}
        )
        assert resp_b.status_code == 200
        tenant_b_customer_ids = {c["id"] for c in resp_b.json().get("customers", [])}
        
        if not tenant_b_customer_ids:
            pytest.skip("No Tenant B customers to test")
        
        # Get Tenant A's customers
        resp_a = requests.get(
            f"{BASE_URL}/api/admin/customers?per_page=100",
            headers={"Authorization": f"Bearer {tenant_a_admin_token}"}
        )
        assert resp_a.status_code == 200
        tenant_a_customer_ids = {c["id"] for c in resp_a.json().get("customers", [])}
        
        # Tenant B customers should NOT appear in Tenant A's list
        leaked_customers = tenant_b_customer_ids & tenant_a_customer_ids
        assert not leaked_customers, (
            f"SECURITY BUG: Tenant B customers leaked to Tenant A: {leaked_customers}"
        )
        print(f"PASS - Tenant B customers ({len(tenant_b_customer_ids)}) not visible to Tenant A")

    def test_tenant_a_cannot_see_tenant_b_subscriptions(self, tenant_a_admin_token, tenant_b_admin_token):
        """Tenant A admin should not see Tenant B's subscriptions."""
        # Get Tenant B's subscriptions
        resp_b = requests.get(
            f"{BASE_URL}/api/admin/subscriptions?per_page=100",
            headers={"Authorization": f"Bearer {tenant_b_admin_token}"}
        )
        assert resp_b.status_code == 200
        tenant_b_sub_ids = {s["id"] for s in resp_b.json().get("subscriptions", [])}
        
        if not tenant_b_sub_ids:
            pytest.skip("No Tenant B subscriptions to test")
        
        # Get Tenant A's subscriptions
        resp_a = requests.get(
            f"{BASE_URL}/api/admin/subscriptions?per_page=100",
            headers={"Authorization": f"Bearer {tenant_a_admin_token}"}
        )
        assert resp_a.status_code == 200
        tenant_a_sub_ids = {s["id"] for s in resp_a.json().get("subscriptions", [])}
        
        # Tenant B subscriptions should NOT appear in Tenant A's list
        leaked_subs = tenant_b_sub_ids & tenant_a_sub_ids
        assert not leaked_subs, (
            f"SECURITY BUG: Tenant B subscriptions leaked to Tenant A: {leaked_subs}"
        )
        print(f"PASS - Tenant B subscriptions ({len(tenant_b_sub_ids)}) not visible to Tenant A")


# ============================================================================
# 7. DIRECT RESOURCE ACCESS BY ID (IDOR)
# ============================================================================

class TestDirectResourceAccessIDOR:
    """
    Test that Tenant A admin cannot access Tenant B's resources directly by ID.
    """

    @pytest.fixture(scope="class")
    def tenant_b_order_id(self, tenant_b_admin_token):
        """Get an order ID from Tenant B."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/orders?per_page=1",
            headers={"Authorization": f"Bearer {tenant_b_admin_token}"}
        )
        assert resp.status_code == 200
        orders = resp.json().get("orders", [])
        if not orders:
            pytest.skip("No Tenant B orders for IDOR test")
        return orders[0]["id"]

    @pytest.fixture(scope="class")
    def tenant_b_subscription_id(self, tenant_b_admin_token):
        """Get a subscription ID from Tenant B."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/subscriptions?per_page=1",
            headers={"Authorization": f"Bearer {tenant_b_admin_token}"}
        )
        assert resp.status_code == 200
        subs = resp.json().get("subscriptions", [])
        if not subs:
            pytest.skip("No Tenant B subscriptions for IDOR test")
        return subs[0]["id"]

    def test_tenant_a_cannot_update_tenant_b_order(self, tenant_a_admin_token, tenant_b_order_id):
        """
        IDOR TEST: Tenant A admin cannot update Tenant B's order by ID.
        """
        resp = requests.put(
            f"{BASE_URL}/api/admin/orders/{tenant_b_order_id}",
            json={"internal_note": "IDOR attack attempt"},
            headers={"Authorization": f"Bearer {tenant_a_admin_token}"}
        )
        
        assert resp.status_code == 404, (
            f"SECURITY BUG: Tenant A admin could access Tenant B order! "
            f"Expected 404, got {resp.status_code}: {resp.text}"
        )
        print(f"PASS - Tenant A blocked from updating Tenant B order: 404")

    def test_tenant_a_cannot_delete_tenant_b_order(self, tenant_a_admin_token, tenant_b_order_id):
        """
        IDOR TEST: Tenant A admin cannot delete Tenant B's order by ID.
        """
        resp = requests.delete(
            f"{BASE_URL}/api/admin/orders/{tenant_b_order_id}",
            json={"reason": "IDOR attack attempt"},
            headers={"Authorization": f"Bearer {tenant_a_admin_token}"}
        )
        
        assert resp.status_code == 404, (
            f"SECURITY BUG: Tenant A admin could delete Tenant B order! "
            f"Expected 404, got {resp.status_code}: {resp.text}"
        )
        print(f"PASS - Tenant A blocked from deleting Tenant B order: 404")

    def test_tenant_a_cannot_update_tenant_b_subscription(self, tenant_a_admin_token, tenant_b_subscription_id):
        """
        IDOR TEST: Tenant A admin cannot update Tenant B's subscription by ID.
        """
        resp = requests.put(
            f"{BASE_URL}/api/admin/subscriptions/{tenant_b_subscription_id}",
            json={"new_note": "IDOR attack attempt"},
            headers={"Authorization": f"Bearer {tenant_a_admin_token}"}
        )
        
        assert resp.status_code == 404, (
            f"SECURITY BUG: Tenant A admin could access Tenant B subscription! "
            f"Expected 404, got {resp.status_code}: {resp.text}"
        )
        print(f"PASS - Tenant A blocked from updating Tenant B subscription: 404")

    def test_tenant_a_cannot_cancel_tenant_b_subscription(self, tenant_a_admin_token, tenant_b_subscription_id):
        """
        IDOR TEST: Tenant A admin cannot cancel Tenant B's subscription by ID.
        """
        resp = requests.post(
            f"{BASE_URL}/api/admin/subscriptions/{tenant_b_subscription_id}/cancel",
            headers={"Authorization": f"Bearer {tenant_a_admin_token}"}
        )
        
        assert resp.status_code == 404, (
            f"SECURITY BUG: Tenant A admin could cancel Tenant B subscription! "
            f"Expected 404, got {resp.status_code}: {resp.text}"
        )
        print(f"PASS - Tenant A blocked from canceling Tenant B subscription: 404")


# ============================================================================
# 8. SUBSCRIPTION CANCEL WEBHOOK TENANT ISOLATION
# ============================================================================

class TestSubscriptionCancelWebhookIsolation:
    """
    Verify subscription cancel properly looks up customer within tenant scope.
    The cancel webhook dispatches customer info - must use tenant-scoped lookup.
    """

    def test_cancel_subscription_returns_correct_response(self, tenant_a_admin_token):
        """Cancel subscription for Tenant A should work correctly."""
        # Get a subscription to cancel (or skip if none)
        resp = requests.get(
            f"{BASE_URL}/api/admin/subscriptions?status=active&per_page=1",
            headers={"Authorization": f"Bearer {tenant_a_admin_token}"}
        )
        assert resp.status_code == 200
        subs = resp.json().get("subscriptions", [])
        
        if not subs:
            pytest.skip("No active subscriptions to test cancel")
        
        sub_id = subs[0]["id"]
        
        # Cancel the subscription
        cancel_resp = requests.post(
            f"{BASE_URL}/api/admin/subscriptions/{sub_id}/cancel",
            headers={"Authorization": f"Bearer {tenant_a_admin_token}"}
        )
        
        assert cancel_resp.status_code == 200, f"Cancel failed: {cancel_resp.text}"
        data = cancel_resp.json()
        assert "cancelled_at" in data, f"Expected cancelled_at in response: {data}"
        print(f"PASS - Subscription cancel returned: {data}")


# ============================================================================
# 9. REGRESSION: BASIC FUNCTIONALITY STILL WORKS
# ============================================================================

class TestBasicFunctionalityRegression:
    """Ensure security fixes didn't break basic functionality."""

    def test_admin_can_list_orders(self, tenant_a_admin_token):
        """Admin can still list their own tenant's orders."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/orders",
            headers={"Authorization": f"Bearer {tenant_a_admin_token}"}
        )
        assert resp.status_code == 200, f"Failed to list orders: {resp.text}"
        assert "orders" in resp.json()
        print(f"PASS - Admin can list orders: {resp.json().get('total', 0)} total")

    def test_admin_can_list_subscriptions(self, tenant_a_admin_token):
        """Admin can still list their own tenant's subscriptions."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/subscriptions",
            headers={"Authorization": f"Bearer {tenant_a_admin_token}"}
        )
        assert resp.status_code == 200, f"Failed to list subscriptions: {resp.text}"
        assert "subscriptions" in resp.json()
        print(f"PASS - Admin can list subscriptions: {resp.json().get('total', 0)} total")

    def test_admin_can_list_bank_transactions(self, tenant_a_admin_token):
        """Admin can still list their own tenant's bank transactions."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/bank-transactions",
            headers={"Authorization": f"Bearer {tenant_a_admin_token}"}
        )
        assert resp.status_code == 200, f"Failed to list bank transactions: {resp.text}"
        assert "transactions" in resp.json()
        print(f"PASS - Admin can list bank transactions: {resp.json().get('total', 0)} total")

    def test_admin_can_list_customers(self, tenant_a_admin_token):
        """Admin can still list their own tenant's customers."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/customers",
            headers={"Authorization": f"Bearer {tenant_a_admin_token}"}
        )
        assert resp.status_code == 200, f"Failed to list customers: {resp.text}"
        assert "customers" in resp.json()
        print(f"PASS - Admin can list customers: {resp.json().get('total', 0)} total")
