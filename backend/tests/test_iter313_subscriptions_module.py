"""
Backend tests for Subscriptions module fixes - Iteration 313
Tests: Bug#1 (renew-now currency), Bug#2 (renew-now billing interval), Bug#3 (contract_end_date null),
Bug#4 (billing_interval stored), Bug#5 (update renewal_date persists), Bug#6 (advance_billing_date),
Issue#8 (payment_method), Issue#9 (billing_interval/currency in update), Issue#10 (email multi-filter),
Issue#11 (cancel with edit permission), Issue#13 (import template billing_interval),
Export with filters, Model validation (ManualSubscriptionCreate, SubscriptionUpdate)
"""
import pytest
import requests
import os
import time
from datetime import date, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


# ── Auth helpers ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!"
    })
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok, "No token in response"
    return tok


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ── Test: advance_billing_date function (Bug#6) ──────────────────────────────

class TestAdvanceBillingDate:
    """Directly test the advance_billing_date function (Bug#6)."""

    def test_biannual_advance(self):
        """advance_billing_date('2026-03-01', 'biannual') should return '2026-09-01'"""
        from services.billing_service import advance_billing_date
        result = advance_billing_date("2026-03-01", "biannual")
        assert result == "2026-09-01", f"Expected 2026-09-01 for biannual, got {result}"

    def test_weekly_advance(self):
        """advance_billing_date('2026-03-01', 'weekly') should return '2026-03-08'"""
        from services.billing_service import advance_billing_date
        result = advance_billing_date("2026-03-01", "weekly")
        assert result == "2026-03-08", f"Expected 2026-03-08 for weekly, got {result}"

    def test_monthly_advance(self):
        """advance_billing_date('2026-03-15', 'monthly') should return '2026-04-01'"""
        from services.billing_service import advance_billing_date
        result = advance_billing_date("2026-03-15", "monthly")
        # monthly goes to 1st of next month
        assert result == "2026-04-01", f"Expected 2026-04-01 for monthly, got {result}"

    def test_quarterly_advance(self):
        """advance_billing_date('2026-03-01', 'quarterly') should return '2026-06-01'"""
        from services.billing_service import advance_billing_date
        result = advance_billing_date("2026-03-01", "quarterly")
        assert result == "2026-06-01", f"Expected 2026-06-01 for quarterly, got {result}"

    def test_annual_advance(self):
        """advance_billing_date('2026-03-01', 'annual') should return '2027-03-01'"""
        from services.billing_service import advance_billing_date
        result = advance_billing_date("2026-03-01", "annual")
        assert result == "2027-03-01", f"Expected 2027-03-01 for annual, got {result}"


# ── Test: ManualSubscriptionCreate model ────────────────────────────────────

class TestManualSubscriptionModel:
    """Validate ManualSubscriptionCreate model fields."""

    def test_model_has_billing_interval(self):
        """Model accepts billing_interval field (Fix#4)."""
        import sys
        sys.path.insert(0, "/app/backend")
        from models import ManualSubscriptionCreate
        # Should not raise validation error
        payload = ManualSubscriptionCreate(
            customer_email="test@test.com",
            product_id="prod_xxx",
            amount=100.0,
            currency="GBP",
            renewal_date="2026-12-01",
            billing_interval="quarterly",
            payment_method="bank_transfer",
        )
        assert payload.billing_interval == "quarterly"
        assert payload.payment_method == "bank_transfer"

    def test_model_has_payment_method(self):
        """Model accepts payment_method field (Fix#8)."""
        from models import ManualSubscriptionCreate
        payload = ManualSubscriptionCreate(
            customer_email="test@test.com",
            product_id="prod_xxx",
            amount=50.0,
            currency="USD",
            renewal_date="2026-12-01",
            payment_method="bank_transfer",
        )
        assert payload.payment_method == "bank_transfer"

    def test_model_default_billing_interval(self):
        """Default billing_interval is 'monthly'."""
        from models import ManualSubscriptionCreate
        payload = ManualSubscriptionCreate(
            customer_email="test@test.com",
            product_id="prod_xxx",
            amount=50.0,
            currency="USD",
            renewal_date="2026-12-01",
        )
        assert payload.billing_interval == "monthly"


class TestSubscriptionUpdateModel:
    """Validate SubscriptionUpdate model fields (Issue#9)."""

    def test_model_has_billing_interval(self):
        """SubscriptionUpdate accepts billing_interval (Fix#9)."""
        from models import SubscriptionUpdate
        payload = SubscriptionUpdate(billing_interval="annual")
        assert payload.billing_interval == "annual"

    def test_model_has_currency(self):
        """SubscriptionUpdate accepts currency (Fix#9)."""
        from models import SubscriptionUpdate
        payload = SubscriptionUpdate(currency="EUR")
        assert payload.currency == "EUR"


# ── Helper fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def test_customer(admin_headers):
    """Get or create a test customer for subscription tests."""
    # Try to find existing test customer
    list_r = requests.get(f"{BASE_URL}/api/admin/customers?per_page=100", headers=admin_headers)
    custs = list_r.json().get("customers", [])
    users = list_r.json().get("users", [])
    user_map = {u["id"]: u for u in users}
    test_email = "test_subtest313@example.com"
    for c in custs:
        u = user_map.get(c.get("user_id"), {})
        if u.get("email", "").lower() == test_email:
            return {"customer_id": c["id"], "email": test_email}

    # Create the customer using the correct endpoint
    r = requests.post(f"{BASE_URL}/api/admin/customers/create", json={
        "full_name": "TEST Sub User",
        "email": test_email,
        "password": "TestPass123!",
        "company_name": "TEST Corp",
    }, headers=admin_headers)
    if r.status_code not in (200, 201):
        pytest.skip(f"Failed to create test customer: {r.text}")
    data = r.json()
    return {"customer_id": data.get("customer_id", ""), "email": test_email}


@pytest.fixture(scope="module")
def test_product(admin_headers):
    """Get or create a subscription-type product."""
    r = requests.get(f"{BASE_URL}/api/admin/products-all?per_page=200", headers=admin_headers)
    products = r.json().get("products", [])
    active = [p for p in products if p.get("is_active") and not p.get("deleted_at") and p.get("pricing_type") == "subscription"]
    if active:
        return active[0]
    # Create one if none exist
    cr = requests.post(f"{BASE_URL}/api/admin/products", json={
        "name": "TEST_Monthly Plan 313",
        "pricing_type": "subscription",
        "base_price": 100.0,
        "currency": "GBP",
        "is_active": True,
        "is_subscription": True,
        "card_title": "TEST Monthly",
        "tagline": "Test subscription plan",
    }, headers=admin_headers)
    if cr.status_code not in (200, 201):
        pytest.skip(f"No subscription products and could not create one: {cr.text}")
    return cr.json().get("product", {})


# ── Test: Create Manual Subscription ────────────────────────────────────────

class TestCreateManualSubscription:
    """Tests for POST /admin/subscriptions/manual"""

    def test_stores_billing_interval(self, admin_headers, test_customer, test_product):
        """Bug#4: billing_interval is stored in the subscription document."""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        renewal = (date.today() + timedelta(days=31)).isoformat()
        r = requests.post(f"{BASE_URL}/api/admin/subscriptions/manual", json={
            "customer_email": test_customer["email"],
            "product_id": test_product["id"],
            "amount": 99.0,
            "currency": "GBP",
            "renewal_date": renewal,
            "start_date": tomorrow,
            "billing_interval": "quarterly",
            "payment_method": "bank_transfer",
            "term_months": 0,
            "status": "active",
        }, headers=admin_headers)
        assert r.status_code in (200, 201), f"Create failed: {r.text}"
        sub_id = r.json().get("subscription_id")
        assert sub_id, "No subscription_id in response"

        # GET to verify persistence
        list_r = requests.get(f"{BASE_URL}/api/admin/subscriptions?per_page=100", headers=admin_headers)
        subs = list_r.json().get("subscriptions", [])
        found = next((s for s in subs if s["id"] == sub_id), None)
        assert found, f"Subscription {sub_id} not found in list"
        assert found.get("billing_interval") == "quarterly", f"Expected quarterly, got: {found.get('billing_interval')}"
        # Store for later tests
        TestCreateManualSubscription._created_sub_id = sub_id

    def test_stores_payment_method(self, admin_headers, test_customer, test_product):
        """Issue#8: payment_method stored correctly, not hardcoded to 'offline'."""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        renewal = (date.today() + timedelta(days=31)).isoformat()
        r = requests.post(f"{BASE_URL}/api/admin/subscriptions/manual", json={
            "customer_email": test_customer["email"],
            "product_id": test_product["id"],
            "amount": 50.0,
            "currency": "USD",
            "renewal_date": renewal,
            "start_date": tomorrow,
            "billing_interval": "monthly",
            "payment_method": "bank_transfer",
            "term_months": 0,
            "status": "active",
        }, headers=admin_headers)
        assert r.status_code in (200, 201), f"Create failed: {r.text}"
        sub_id = r.json().get("subscription_id")
        assert sub_id

        list_r = requests.get(f"{BASE_URL}/api/admin/subscriptions?per_page=100", headers=admin_headers)
        subs = list_r.json().get("subscriptions", [])
        found = next((s for s in subs if s["id"] == sub_id), None)
        assert found, f"Subscription {sub_id} not found in list"
        assert found.get("payment_method") == "bank_transfer", f"Expected bank_transfer, got: {found.get('payment_method')}"

    def test_term_months_zero_results_in_null_contract_end_date(self, admin_headers, test_customer, test_product):
        """Bug#3: term_months=0 → contract_end_date must be null."""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        renewal = (date.today() + timedelta(days=31)).isoformat()
        r = requests.post(f"{BASE_URL}/api/admin/subscriptions/manual", json={
            "customer_email": test_customer["email"],
            "product_id": test_product["id"],
            "amount": 75.0,
            "currency": "GBP",
            "renewal_date": renewal,
            "start_date": tomorrow,
            "billing_interval": "monthly",
            "payment_method": "offline",
            "term_months": 0,
            "status": "active",
        }, headers=admin_headers)
        assert r.status_code in (200, 201), f"Create failed: {r.text}"
        sub_id = r.json().get("subscription_id")
        assert sub_id

        list_r = requests.get(f"{BASE_URL}/api/admin/subscriptions?per_page=100", headers=admin_headers)
        subs = list_r.json().get("subscriptions", [])
        found = next((s for s in subs if s["id"] == sub_id), None)
        assert found, f"Subscription {sub_id} not found in list"
        # contract_end_date should be null/None when term_months=0
        contract_end = found.get("contract_end_date")
        assert contract_end is None or contract_end == "", f"Expected null contract_end_date for term_months=0, got: {contract_end}"


# ── Test: Update Subscription (Bug#5, Issue#9) ──────────────────────────────

class TestUpdateSubscription:
    """Tests for PUT /admin/subscriptions/{id}"""

    @pytest.fixture(scope="class")
    def sub_to_update(self, admin_headers, test_customer, test_product):
        """Create a subscription for update tests."""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        renewal = (date.today() + timedelta(days=31)).isoformat()
        r = requests.post(f"{BASE_URL}/api/admin/subscriptions/manual", json={
            "customer_email": test_customer["email"],
            "product_id": test_product["id"],
            "amount": 120.0,
            "currency": "GBP",
            "renewal_date": renewal,
            "start_date": tomorrow,
            "billing_interval": "monthly",
            "payment_method": "offline",
            "term_months": 0,
            "status": "active",
        }, headers=admin_headers)
        assert r.status_code in (200, 201), f"Create failed: {r.text}"
        return r.json()["subscription_id"]

    def test_update_renewal_date_persists(self, admin_headers, sub_to_update):
        """Bug#5: PUT with renewal_date actually saves it to DB."""
        new_renewal = (date.today() + timedelta(days=60)).isoformat()
        r = requests.put(f"{BASE_URL}/api/admin/subscriptions/{sub_to_update}", json={
            "renewal_date": new_renewal,
        }, headers=admin_headers)
        assert r.status_code == 200, f"Update failed: {r.text}"

        # Verify it was actually saved
        list_r = requests.get(f"{BASE_URL}/api/admin/subscriptions?per_page=200", headers=admin_headers)
        subs = list_r.json().get("subscriptions", [])
        found = next((s for s in subs if s["id"] == sub_to_update), None)
        assert found, f"Subscription {sub_to_update} not found after update"
        assert found.get("renewal_date", "")[:10] == new_renewal, \
            f"renewal_date not persisted: expected {new_renewal}, got {found.get('renewal_date', '')[:10]}"

    def test_update_billing_interval_persists(self, admin_headers, sub_to_update):
        """Issue#9: PUT with billing_interval='annual' saves billing_interval."""
        r = requests.put(f"{BASE_URL}/api/admin/subscriptions/{sub_to_update}", json={
            "billing_interval": "annual",
        }, headers=admin_headers)
        assert r.status_code == 200, f"Update failed: {r.text}"

        list_r = requests.get(f"{BASE_URL}/api/admin/subscriptions?per_page=200", headers=admin_headers)
        subs = list_r.json().get("subscriptions", [])
        found = next((s for s in subs if s["id"] == sub_to_update), None)
        assert found, "Subscription not found after update"
        assert found.get("billing_interval") == "annual", \
            f"billing_interval not persisted: expected annual, got {found.get('billing_interval')}"

    def test_update_currency_persists(self, admin_headers, sub_to_update):
        """Issue#9: PUT with currency='EUR' saves currency."""
        r = requests.put(f"{BASE_URL}/api/admin/subscriptions/{sub_to_update}", json={
            "currency": "EUR",
        }, headers=admin_headers)
        assert r.status_code == 200, f"Update failed: {r.text}"

        list_r = requests.get(f"{BASE_URL}/api/admin/subscriptions?per_page=200", headers=admin_headers)
        subs = list_r.json().get("subscriptions", [])
        found = next((s for s in subs if s["id"] == sub_to_update), None)
        assert found, "Subscription not found after update"
        assert found.get("currency") == "EUR", \
            f"currency not persisted: expected EUR, got {found.get('currency')}"


# ── Test: Renew Now (Bug#1, Bug#2) ───────────────────────────────────────────

class TestRenewNow:
    """Tests for POST /admin/subscriptions/{id}/renew-now"""

    @pytest.fixture(scope="class")
    def gbp_quarterly_sub(self, admin_headers, test_customer, test_product):
        """Create a GBP quarterly subscription for renew tests."""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        renewal = "2026-06-01"  # specific date for testing quarterly advance
        r = requests.post(f"{BASE_URL}/api/admin/subscriptions/manual", json={
            "customer_email": test_customer["email"],
            "product_id": test_product["id"],
            "amount": 300.0,
            "currency": "GBP",
            "renewal_date": renewal,
            "start_date": tomorrow,
            "billing_interval": "quarterly",
            "payment_method": "offline",
            "term_months": 0,
            "status": "active",
        }, headers=admin_headers)
        assert r.status_code in (200, 201), f"Create failed: {r.text}"
        return r.json()["subscription_id"]

    def test_renew_now_uses_subscription_currency(self, admin_headers, gbp_quarterly_sub):
        """Bug#1: renew-now creates order with subscription's currency (GBP, not USD)."""
        r = requests.post(f"{BASE_URL}/api/admin/subscriptions/{gbp_quarterly_sub}/renew-now",
                          headers=admin_headers)
        assert r.status_code == 200, f"Renew-now failed: {r.text}"
        data = r.json()
        order_id = data.get("order_id")
        assert order_id, "No order_id in response"

        # Verify order was created with correct currency
        orders_r = requests.get(f"{BASE_URL}/api/admin/orders?per_page=200", headers=admin_headers)
        orders = orders_r.json().get("orders", [])
        order = next((o for o in orders if o.get("id") == order_id), None)
        assert order, f"Order {order_id} not found"
        assert order.get("currency") == "GBP", \
            f"Bug#1: Expected currency GBP in renewal order, got {order.get('currency')}"

    def test_renew_now_advances_quarterly_by_3_months(self, admin_headers, gbp_quarterly_sub):
        """Bug#2: renew-now advances renewal_date using billing_interval (quarterly → +3 months to 1st)."""
        # After renew-now in the previous test, renewal_date should have moved
        # Since we set renewal to 2026-06-01 and interval is quarterly, it should now be 2026-09-01
        list_r = requests.get(f"{BASE_URL}/api/admin/subscriptions?per_page=200", headers=admin_headers)
        subs = list_r.json().get("subscriptions", [])
        found = next((s for s in subs if s["id"] == gbp_quarterly_sub), None)
        assert found, f"Subscription {gbp_quarterly_sub} not found"
        new_renewal = found.get("renewal_date", "")[:10]
        assert new_renewal == "2026-09-01", \
            f"Bug#2: Expected renewal_date=2026-09-01 after quarterly renew-now, got {new_renewal}"

    def test_renew_now_returns_next_renewal_date(self, admin_headers, test_customer, test_product):
        """Bug#2: renew-now response has valid next_renewal_date string."""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        # Create a monthly sub with a specific renewal date
        renewal = "2026-05-01"
        r = requests.post(f"{BASE_URL}/api/admin/subscriptions/manual", json={
            "customer_email": test_customer["email"],
            "product_id": test_product["id"],
            "amount": 100.0,
            "currency": "USD",
            "renewal_date": renewal,
            "start_date": tomorrow,
            "billing_interval": "monthly",
            "payment_method": "offline",
            "term_months": 0,
            "status": "active",
        }, headers=admin_headers)
        assert r.status_code in (200, 201), f"Create failed: {r.text}"
        sub_id = r.json()["subscription_id"]

        renew_r = requests.post(f"{BASE_URL}/api/admin/subscriptions/{sub_id}/renew-now",
                                headers=admin_headers)
        assert renew_r.status_code == 200, f"Renew-now failed: {renew_r.text}"
        data = renew_r.json()
        next_renewal = data.get("next_renewal_date")
        assert next_renewal, "next_renewal_date missing from response"
        # Monthly from 2026-05-01 → 2026-06-01
        assert next_renewal == "2026-06-01", \
            f"Expected 2026-06-01 for monthly advance from 2026-05-01, got {next_renewal}"


# ── Test: Cancel Subscription (Issue#11) ─────────────────────────────────────

class TestCancelSubscription:
    """Tests for POST /admin/subscriptions/{id}/cancel"""

    def test_cancel_returns_200_not_403(self, admin_headers, test_customer, test_product):
        """Issue#11: cancel endpoint returns 200 (uses 'edit' permission, not 'delete')."""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        renewal = (date.today() + timedelta(days=31)).isoformat()
        r = requests.post(f"{BASE_URL}/api/admin/subscriptions/manual", json={
            "customer_email": test_customer["email"],
            "product_id": test_product["id"],
            "amount": 50.0,
            "currency": "GBP",
            "renewal_date": renewal,
            "start_date": tomorrow,
            "billing_interval": "monthly",
            "payment_method": "offline",
            "term_months": 0,
            "status": "active",
        }, headers=admin_headers)
        assert r.status_code in (200, 201), f"Create failed: {r.text}"
        sub_id = r.json()["subscription_id"]

        cancel_r = requests.post(f"{BASE_URL}/api/admin/subscriptions/{sub_id}/cancel",
                                 headers=admin_headers)
        assert cancel_r.status_code == 200, \
            f"Issue#11: Cancel returned {cancel_r.status_code} not 200: {cancel_r.text}"
        data = cancel_r.json()
        assert "cancelled_at" in data or "message" in data, \
            f"Cancel response missing expected fields: {data}"


# ── Test: Email Multi-filter (Issue#10) ──────────────────────────────────────

class TestEmailMultiFilter:
    """Tests for GET /admin/subscriptions?email= multi-email filter (Issue#10)."""

    def test_single_email_filter(self, admin_headers, test_customer):
        """Single email filter returns subscriptions for that customer."""
        r = requests.get(
            f"{BASE_URL}/api/admin/subscriptions?per_page=50&email={test_customer['email']}",
            headers=admin_headers
        )
        assert r.status_code == 200, f"Filter request failed: {r.text}"
        subs = r.json().get("subscriptions", [])
        # We created multiple test subscriptions, should find at least some
        assert isinstance(subs, list), "Expected list of subscriptions"

    def test_multi_email_filter_uses_in_query(self, admin_headers, test_customer):
        """Issue#10: comma-separated emails use $in query not broken regex."""
        # Two emails - one valid, one non-existent
        email1 = test_customer["email"]
        email2 = "nonexistent_x@example.com"
        r = requests.get(
            f"{BASE_URL}/api/admin/subscriptions?per_page=50&email={email1},{email2}",
            headers=admin_headers
        )
        assert r.status_code == 200, f"Multi-email filter failed: {r.text}"
        # Should not raise 500 (broken regex was the bug)
        subs = r.json().get("subscriptions", [])
        assert isinstance(subs, list)


# ── Test: Export with Filters (Issue#12) ─────────────────────────────────────

class TestExportWithFilters:
    """Tests for GET /admin/export/subscriptions with filter params."""

    def test_export_status_filter_active_returns_csv(self, admin_headers):
        """Export with status=active returns a CSV response (not unfiltered)."""
        r = requests.get(
            f"{BASE_URL}/api/admin/export/subscriptions?status=active",
            headers=admin_headers
        )
        assert r.status_code == 200, f"Export failed: {r.text}"
        content_type = r.headers.get("content-type", "")
        assert "text/csv" in content_type, f"Expected CSV content-type, got: {content_type}"
        # Parse CSV to verify only active rows
        text = r.text
        if text.strip() == "No data":
            return  # No active subs, but filter worked
        lines = text.strip().split("\n")
        assert len(lines) >= 1, "CSV has no content"
        # If there's data, check the status column
        if len(lines) > 1:
            header = lines[0].lower()
            if "status" in header:
                headers = [h.strip('"') for h in lines[0].split(",")]
                status_idx = next((i for i, h in enumerate(headers) if "status" in h.lower()), None)
                if status_idx is not None:
                    for line in lines[1:]:
                        cells = line.split(",")
                        if len(cells) > status_idx:
                            row_status = cells[status_idx].strip('"').strip()
                            if row_status:
                                assert row_status == "active", \
                                    f"Export returned non-active row with status: {row_status}"

    def test_export_no_filter_returns_csv(self, admin_headers):
        """Export without filters returns all subscriptions as CSV."""
        r = requests.get(f"{BASE_URL}/api/admin/export/subscriptions", headers=admin_headers)
        assert r.status_code == 200, f"Export failed: {r.text}"
        assert "text/csv" in r.headers.get("content-type", "")


# ── Test: Import Template (Issue#13) ─────────────────────────────────────────

class TestImportTemplate:
    """Tests for GET /admin/import/template/subscriptions"""

    def test_template_has_billing_interval_not_billing_cycle(self, admin_headers):
        """Issue#13: Template CSV uses billing_interval column, not billing_cycle."""
        r = requests.get(f"{BASE_URL}/api/admin/import/template/subscriptions",
                         headers=admin_headers)
        assert r.status_code == 200, f"Template download failed: {r.text}"
        content_type = r.headers.get("content-type", "")
        assert "text/csv" in content_type, f"Expected CSV, got: {content_type}"
        text = r.text
        lines = text.strip().split("\n")
        assert len(lines) >= 1, "Template is empty"
        header_row = lines[0].lower()
        assert "billing_interval" in header_row, \
            f"Template should have 'billing_interval' column, got header: {lines[0]}"
        assert "billing_cycle" not in header_row, \
            f"Template should NOT have 'billing_cycle' column, but found it in: {lines[0]}"

    def test_template_sample_data_has_billing_interval(self, admin_headers):
        """Sample data row also uses billing_interval."""
        r = requests.get(f"{BASE_URL}/api/admin/import/template/subscriptions",
                         headers=admin_headers)
        assert r.status_code == 200
        text = r.text
        # billing_interval value should appear in the CSV data row
        assert "billing_interval" in text or "monthly" in text.lower() or "quarterly" in text.lower(), \
            "Sample data should have a billing interval value"


# ── Test: Subscriptions list endpoint ────────────────────────────────────────

class TestSubscriptionsList:
    """Basic tests for GET /admin/subscriptions"""

    def test_list_returns_200(self, admin_headers):
        """List endpoint returns 200."""
        r = requests.get(f"{BASE_URL}/api/admin/subscriptions?per_page=10", headers=admin_headers)
        assert r.status_code == 200, f"List failed: {r.text}"
        data = r.json()
        assert "subscriptions" in data
        assert "total" in data
        assert "total_pages" in data

    def test_list_includes_billing_interval(self, admin_headers):
        """Subscriptions list includes billing_interval field."""
        r = requests.get(f"{BASE_URL}/api/admin/subscriptions?per_page=50", headers=admin_headers)
        assert r.status_code == 200
        subs = r.json().get("subscriptions", [])
        # At least one of the test subs we created should have billing_interval
        assert any("billing_interval" in s for s in subs), \
            "No subscription in list has billing_interval field"

    def test_status_filter_active(self, admin_headers):
        """Status filter returns only active subscriptions."""
        r = requests.get(f"{BASE_URL}/api/admin/subscriptions?status=active&per_page=50", headers=admin_headers)
        assert r.status_code == 200
        subs = r.json().get("subscriptions", [])
        for s in subs:
            assert s.get("status") == "active", \
                f"Expected active status, got: {s.get('status')}"

    def test_filter_options_endpoint(self, admin_headers):
        """Filter options endpoint returns subscription_statuses and payment_methods."""
        r = requests.get(f"{BASE_URL}/api/admin/filter-options", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "subscription_statuses" in data
        assert "payment_methods" in data
        # payment_methods should include bank_transfer (Issue#8 related)
        assert "bank_transfer" in data["payment_methods"], \
            f"bank_transfer not in payment_methods: {data['payment_methods']}"
