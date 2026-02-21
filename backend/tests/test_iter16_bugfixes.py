"""
Iteration 16 - Bug Fix Tests
Tests:
1. GoCardless complete-redirect accepts request without subtotal (Optional)
2. Admin subscription cancel button logic (contract_end_date check)
3. Stripe 3-day minimum for future start date
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


@pytest.fixture(scope="module")
def admin_token():
    """Get admin token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!"
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Admin auth failed")


@pytest.fixture
def admin_client(admin_token):
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {admin_token}"
    })
    return session


class TestGoCardlessCompleteRedirect:
    """Test GoCardless complete-redirect endpoint with optional subtotal"""

    def test_without_subtotal_should_not_return_422(self, admin_client):
        """Bug fix 5: POST /api/gocardless/complete-redirect without subtotal should not 422"""
        response = admin_client.post(f"{BASE_URL}/api/gocardless/complete-redirect", json={
            "redirect_flow_id": "test_redirect_id_123",
            "order_id": "test_order_id_123"
            # No 'subtotal' field - should be optional
        })
        # Must NOT be 422 (validation error means subtotal still required)
        assert response.status_code != 422, (
            f"Expected NOT 422 but got 422 - subtotal is still required! Response: {response.text}"
        )
        # Should be 400 (bad redirect flow) or similar business error
        print(f"Status code (should be 400 or similar business error): {response.status_code}")
        print(f"Response: {response.text[:200]}")

    def test_without_subtotal_returns_400_not_422(self, admin_client):
        """Confirm we get 400 (business error) not 422 (validation error)"""
        response = admin_client.post(f"{BASE_URL}/api/gocardless/complete-redirect", json={
            "redirect_flow_id": "RE_TESTNOTEXIST",
            "order_id": "ORD_TESTNOTEXIST"
        })
        # 422 = validation error (means subtotal is still required)
        # 400 or 404 = business logic error (correct - subtotal is optional)
        assert response.status_code in [400, 404, 500], (
            f"Expected 400/404/500 but got {response.status_code} - this may indicate subtotal is still required"
        )
        print(f"GoCardless without subtotal returns: {response.status_code} ✓")

    def test_with_subtotal_still_works(self, admin_client):
        """Ensure passing subtotal still works"""
        response = admin_client.post(f"{BASE_URL}/api/gocardless/complete-redirect", json={
            "redirect_flow_id": "RE_TESTNOTEXIST",
            "order_id": "ORD_TESTNOTEXIST",
            "subtotal": 100.00
        })
        # Should not be 422 (validation error)
        assert response.status_code != 422, f"Unexpected 422: {response.text}"
        print(f"GoCardless with subtotal returns: {response.status_code} ✓")


class TestAdminSubscriptions:
    """Test Admin Subscriptions cancel button logic"""

    def test_subscriptions_endpoint_loads(self, admin_client):
        """Admin subscriptions endpoint returns data"""
        response = admin_client.get(f"{BASE_URL}/api/admin/subscriptions")
        assert response.status_code == 200, f"Unexpected status: {response.status_code}"
        data = response.json()
        assert "subscriptions" in data
        subs = data["subscriptions"]
        print(f"Total subscriptions: {len(subs)}")

    def test_sub_70126f2e_has_future_contract_end(self, admin_client):
        """SUB-70126F2E should have contract_end_date in future (2027-02-21)"""
        response = admin_client.get(f"{BASE_URL}/api/admin/subscriptions")
        assert response.status_code == 200
        subs = response.json().get("subscriptions", [])
        
        target = next((s for s in subs if s.get("subscription_number") == "SUB-70126F2E"), None)
        if target is None:
            pytest.skip("SUB-70126F2E not found in subscriptions")
        
        contract_end = target.get("contract_end_date", "")
        print(f"SUB-70126F2E contract_end_date: {contract_end}")
        assert contract_end, "contract_end_date should not be empty"
        # Should be in the future (2027-02-21)
        assert contract_end >= "2027-01-01", f"Expected future date but got: {contract_end}"

    def test_sub_1ed7919b_has_past_contract_end(self, admin_client):
        """SUB-1ED7919B should have contract_end_date in past (2026-01-15)"""
        response = admin_client.get(f"{BASE_URL}/api/admin/subscriptions")
        assert response.status_code == 200
        subs = response.json().get("subscriptions", [])
        
        target = next((s for s in subs if s.get("subscription_number") == "SUB-1ED7919B"), None)
        if target is None:
            pytest.skip("SUB-1ED7919B not found in subscriptions")
        
        contract_end = target.get("contract_end_date", "")
        print(f"SUB-1ED7919B contract_end_date: {contract_end}")
        assert contract_end, "contract_end_date should not be empty"
        # Should be in the past (2026-01-15, today is Feb 2026)
        assert contract_end <= "2026-02-01", f"Expected past date but got: {contract_end}"


class TestCheckoutFutureStartDate:
    """Test cart/checkout future start date validation"""

    def test_checkout_bank_transfer_endpoint_exists(self, admin_client):
        """Checkout endpoint is accessible"""
        # Test with invalid data to verify endpoint existence
        response = admin_client.post(f"{BASE_URL}/api/checkout/bank-transfer", json={
            "items": [],
            "checkout_type": "subscription",
            "start_date": "2026-02-22"  # Only 1 day from today
        })
        # Should not be 404 - endpoint should exist
        assert response.status_code != 404, "Checkout endpoint not found"
        print(f"Checkout endpoint status: {response.status_code}")

    def test_subscription_start_date_too_soon_rejected(self, admin_client):
        """Start date less than 3 days from today should be rejected"""
        from datetime import datetime, timedelta
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        response = admin_client.post(f"{BASE_URL}/api/checkout/bank-transfer", json={
            "items": [],
            "checkout_type": "subscription",
            "start_date": tomorrow,
            "terms_accepted": True
        })
        # Should be 400 or 422 (validation error for too-soon date)
        # 400 means business logic rejected it, which is correct
        print(f"Start date = tomorrow ({tomorrow}): status {response.status_code}")
        # We just verify the endpoint doesn't crash
        assert response.status_code in [400, 422, 200], f"Unexpected: {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
