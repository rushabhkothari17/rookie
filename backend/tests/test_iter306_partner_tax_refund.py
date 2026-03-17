"""
Backend tests for iteration 306:
- Tax fields in partner orders (create/update)
- Tax fields in partner subscriptions (create/update)
- Partner order refund endpoint
- Partner order refund-providers endpoint
- Manual customer order tax fields
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


@pytest.fixture(scope="module")
def admin_token():
    """Get platform admin auth token (no partner_code for platform admin)."""
    res = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!",
    })
    assert res.status_code == 200, f"Login failed: {res.text}"
    data = res.json()
    return data.get("token") or data.get("access_token")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def partner_tenant_id(auth_headers):
    """Get a partner tenant id to use for testing."""
    res = requests.get(f"{BASE_URL}/api/admin/tenants", headers=auth_headers)
    assert res.status_code == 200
    tenants = res.data.get("tenants") if hasattr(res, "data") else res.json().get("tenants", [])
    # Filter out automate-accounts
    partners = [t for t in tenants if t.get("code") != "automate-accounts"]
    assert len(partners) > 0, "No partner tenant found"
    return partners[0]["id"]


# ---- Helper fixture to get first non-platform tenant ----
def get_first_partner_id(auth_headers):
    res = requests.get(f"{BASE_URL}/api/admin/tenants", headers=auth_headers)
    assert res.status_code == 200
    tenants = res.json().get("tenants", [])
    partners = [t for t in tenants if t.get("code") != "automate-accounts"]
    assert len(partners) > 0, "No partner tenant found"
    return partners[0]["id"]


class TestPartnerOrderTaxFields:
    """Test tax fields when creating and retrieving partner orders."""

    created_order_id = None

    def test_create_partner_order_with_tax(self, auth_headers):
        """Create a partner order with tax fields and verify they are saved."""
        partner_id = get_first_partner_id(auth_headers)
        payload = {
            "partner_id": partner_id,
            "description": "TEST_Tax Order",
            "amount": 100.0,
            "currency": "GBP",
            "status": "unpaid",
            "payment_method": "manual",
            "tax_name": "HST",
            "tax_rate": 13.0,
            "tax_amount": 13.0,
        }
        res = requests.post(f"{BASE_URL}/api/admin/partner-orders", json=payload, headers=auth_headers)
        assert res.status_code == 200, f"Create order failed: {res.text}"
        data = res.json()
        assert "order" in data
        order = data["order"]
        assert order["tax_name"] == "HST"
        assert order["tax_rate"] == 13.0
        assert order["tax_amount"] == 13.0
        assert order["amount"] == 100.0
        # Store for further tests
        TestPartnerOrderTaxFields.created_order_id = order["id"]
        print(f"PASS: Partner order with tax created - ID: {order['id']}, tax_name: {order['tax_name']}, tax_rate: {order['tax_rate']}")

    def test_get_partner_order_has_tax(self, auth_headers):
        """Verify GET on the created order returns tax fields."""
        order_id = TestPartnerOrderTaxFields.created_order_id
        if not order_id:
            pytest.skip("No order ID available from previous test")
        res = requests.get(f"{BASE_URL}/api/admin/partner-orders/{order_id}", headers=auth_headers)
        assert res.status_code == 200, f"Get order failed: {res.text}"
        order = res.json()["order"]
        assert order["tax_name"] == "HST"
        assert order["tax_rate"] == 13.0
        assert order["tax_amount"] == 13.0
        print(f"PASS: GET partner order retains tax fields correctly")

    def test_update_partner_order_tax(self, auth_headers):
        """Update tax fields on an existing order and verify they persist."""
        order_id = TestPartnerOrderTaxFields.created_order_id
        if not order_id:
            pytest.skip("No order ID available from previous test")
        update_payload = {
            "tax_name": "GST",
            "tax_rate": 5.0,
            "tax_amount": 5.0,
        }
        res = requests.put(f"{BASE_URL}/api/admin/partner-orders/{order_id}", json=update_payload, headers=auth_headers)
        assert res.status_code == 200, f"Update order failed: {res.text}"
        order = res.json()["order"]
        assert order["tax_name"] == "GST"
        assert order["tax_rate"] == 5.0
        print(f"PASS: Update partner order tax fields persists correctly")


class TestPartnerOrderRefund:
    """Test refund endpoints for partner orders."""

    paid_order_id = None

    def test_create_paid_order_for_refund(self, auth_headers):
        """Create a paid partner order to test refund on."""
        partner_id = get_first_partner_id(auth_headers)
        from datetime import date
        today = date.today().isoformat()
        payload = {
            "partner_id": partner_id,
            "description": "TEST_Paid Order For Refund",
            "amount": 200.0,
            "currency": "GBP",
            "status": "paid",
            "payment_method": "manual",
            "paid_at": today,
            "tax_name": "VAT",
            "tax_rate": 20.0,
            "tax_amount": 40.0,
        }
        res = requests.post(f"{BASE_URL}/api/admin/partner-orders", json=payload, headers=auth_headers)
        assert res.status_code == 200, f"Create paid order failed: {res.text}"
        order = res.json()["order"]
        assert order["status"] == "paid"
        TestPartnerOrderRefund.paid_order_id = order["id"]
        print(f"PASS: Paid partner order created for refund - ID: {order['id']}")

    def test_get_refund_providers(self, auth_headers):
        """GET /admin/partner-orders/{order_id}/refund-providers returns providers including 'manual'."""
        order_id = TestPartnerOrderRefund.paid_order_id
        if not order_id:
            pytest.skip("No paid order ID available")
        res = requests.get(f"{BASE_URL}/api/admin/partner-orders/{order_id}/refund-providers", headers=auth_headers)
        assert res.status_code == 200, f"Get refund providers failed: {res.text}"
        data = res.json()
        assert "providers" in data
        providers = data["providers"]
        assert len(providers) > 0
        # Check manual provider is always present
        manual_providers = [p for p in providers if p["id"] == "manual"]
        assert len(manual_providers) > 0, "Manual provider missing from list"
        assert manual_providers[0]["available"] is True
        print(f"PASS: Refund providers endpoint returns providers: {[p['id'] for p in providers]}")

    def test_partial_refund_changes_status(self, auth_headers):
        """Partial refund should change status to partially_refunded."""
        order_id = TestPartnerOrderRefund.paid_order_id
        if not order_id:
            pytest.skip("No paid order ID available")
        refund_payload = {
            "amount": 50.0,
            "reason": "requested_by_partner",
        }
        res = requests.post(f"{BASE_URL}/api/admin/partner-orders/{order_id}/refund", json=refund_payload, headers=auth_headers)
        assert res.status_code == 200, f"Partial refund failed: {res.text}"
        data = res.json()
        order = data["order"]
        assert order["status"] == "partially_refunded", f"Expected partially_refunded, got {order['status']}"
        assert order["refunded_amount"] == 50.0, f"Expected refunded_amount=50, got {order['refunded_amount']}"
        print(f"PASS: Partial refund changes status to partially_refunded and sets refunded_amount=50.0")

    def test_full_refund_changes_status_to_refunded(self, auth_headers):
        """Full refund should change status to refunded."""
        order_id = TestPartnerOrderRefund.paid_order_id
        if not order_id:
            pytest.skip("No paid order ID available")
        # Remaining amount = 200 - 50 = 150
        refund_payload = {
            "reason": "requested_by_partner",
            # Leave amount empty for full refund of remaining balance
        }
        res = requests.post(f"{BASE_URL}/api/admin/partner-orders/{order_id}/refund", json=refund_payload, headers=auth_headers)
        assert res.status_code == 200, f"Full refund failed: {res.text}"
        data = res.json()
        order = data["order"]
        assert order["status"] == "refunded", f"Expected refunded, got {order['status']}"
        assert order["refunded_amount"] == 200.0, f"Expected refunded_amount=200, got {order['refunded_amount']}"
        print(f"PASS: Full refund changes status to refunded and sets refunded_amount=200.0")

    def test_refund_exceeds_available_returns_error(self, auth_headers):
        """Cannot refund more than the available balance."""
        partner_id = get_first_partner_id(auth_headers)
        from datetime import date
        today = date.today().isoformat()
        # Create a fresh paid order
        create_res = requests.post(f"{BASE_URL}/api/admin/partner-orders", json={
            "partner_id": partner_id,
            "description": "TEST_Refund Exceed Order",
            "amount": 100.0,
            "currency": "GBP",
            "status": "paid",
            "payment_method": "manual",
            "paid_at": today,
        }, headers=auth_headers)
        assert create_res.status_code == 200
        new_order_id = create_res.json()["order"]["id"]

        # Try to refund 150 when only 100 available
        res = requests.post(f"{BASE_URL}/api/admin/partner-orders/{new_order_id}/refund", json={
            "amount": 150.0,
            "reason": "other",
        }, headers=auth_headers)
        assert res.status_code == 400, f"Expected 400 for exceeding refund, got {res.status_code}: {res.text}"
        print(f"PASS: Refund exceeding available balance returns 400")

    def test_refund_unpaid_order_returns_error(self, auth_headers):
        """Cannot refund an unpaid order."""
        partner_id = get_first_partner_id(auth_headers)
        create_res = requests.post(f"{BASE_URL}/api/admin/partner-orders", json={
            "partner_id": partner_id,
            "description": "TEST_Unpaid Order No Refund",
            "amount": 100.0,
            "currency": "GBP",
            "status": "unpaid",
            "payment_method": "manual",
        }, headers=auth_headers)
        assert create_res.status_code == 200
        unpaid_order_id = create_res.json()["order"]["id"]

        res = requests.post(f"{BASE_URL}/api/admin/partner-orders/{unpaid_order_id}/refund", json={
            "amount": 50.0,
            "reason": "other",
        }, headers=auth_headers)
        assert res.status_code == 400, f"Expected 400 for unpaid order refund, got {res.status_code}: {res.text}"
        print(f"PASS: Refund of unpaid order returns 400")


class TestPartnerSubscriptionTaxFields:
    """Test tax fields when creating partner subscriptions."""

    created_sub_id = None

    def test_create_partner_subscription_with_tax(self, auth_headers):
        """Create a partner subscription with tax fields."""
        partner_id = get_first_partner_id(auth_headers)
        payload = {
            "partner_id": partner_id,
            "description": "TEST_Tax Subscription",
            "amount": 50.0,
            "currency": "GBP",
            "billing_interval": "monthly",
            "status": "pending",
            "payment_method": "manual",
            "tax_name": "HST",
            "tax_rate": 13.0,
            "tax_amount": 6.5,
        }
        res = requests.post(f"{BASE_URL}/api/admin/partner-subscriptions", json=payload, headers=auth_headers)
        assert res.status_code == 200, f"Create subscription failed: {res.text}"
        data = res.json()
        assert "subscription" in data
        sub = data["subscription"]
        assert sub["tax_name"] == "HST"
        assert sub["tax_rate"] == 13.0
        assert sub["tax_amount"] == 6.5
        TestPartnerSubscriptionTaxFields.created_sub_id = sub["id"]
        print(f"PASS: Partner subscription with tax created - ID: {sub['id']}, tax_name: {sub['tax_name']}")

    def test_get_subscription_retains_tax(self, auth_headers):
        """Verify GET on subscription returns tax fields."""
        sub_id = TestPartnerSubscriptionTaxFields.created_sub_id
        if not sub_id:
            pytest.skip("No subscription ID available")
        res = requests.get(f"{BASE_URL}/api/admin/partner-subscriptions/{sub_id}", headers=auth_headers)
        assert res.status_code == 200
        sub = res.json()["subscription"]
        assert sub["tax_name"] == "HST"
        assert sub["tax_rate"] == 13.0
        print(f"PASS: GET subscription retains tax fields")
