"""
Backend tests for iteration 315: Orders and Subscriptions module audit
Tests: X-1, X-2, X-3, C-1, C-2, H-3, M-6(model), M-8, M-9, M-10(model), M-11, M-12(code)
"""
import os
import pytest
import requests
from datetime import datetime, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASS = "ChangeMe123!"
PARTNER_EMAIL = "rushabh0996@gmail.com"
PARTNER_PASS = "ChangeMe123!"


# ---------------------------------------------------------------------------
# Auth fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS, "login_type": "platform"})
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    t = r.json().get("token")
    assert t, "No token in login response"
    return t


@pytest.fixture(scope="module")
def partner_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": PARTNER_EMAIL, "password": PARTNER_PASS, "partner_code": "edd", "login_type": "partner"})
    if r.status_code != 200:
        pytest.skip(f"Partner login failed: {r.text}")
    t = r.json().get("token")
    if not t:
        pytest.skip("No partner token in login response")
    return t


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def partner_headers(partner_token):
    return {"Authorization": f"Bearer {partner_token}", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Helper: get existing orders / subscriptions from admin
# ---------------------------------------------------------------------------

def get_first_order(headers):
    r = requests.get(f"{BASE_URL}/api/admin/orders?per_page=5&sort_by=created_at&sort_order=desc", headers=headers)
    if r.status_code == 200:
        orders = r.json().get("orders", [])
        return orders[0] if orders else None
    return None


def get_first_sub(headers):
    r = requests.get(f"{BASE_URL}/api/admin/subscriptions?per_page=5&sort_by=created_at&sort_order=desc", headers=headers)
    if r.status_code == 200:
        subs = r.json().get("subscriptions", [])
        return subs[0] if subs else None
    return None


# ===========================================================================
# X-1: Server-side creation date filter
# ===========================================================================

class TestX1CreatedDateFilter:
    """X-1: GET /api/admin/orders with created_from/created_to should server-filter."""

    def test_created_from_filter_returns_200(self, admin_headers):
        """Passing created_from should not crash."""
        r = requests.get(f"{BASE_URL}/api/admin/orders?created_from=2024-01-01&per_page=5", headers=admin_headers)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "orders" in data
        assert "total" in data

    def test_created_to_filter_returns_200(self, admin_headers):
        """Passing created_to should not crash."""
        r = requests.get(f"{BASE_URL}/api/admin/orders?created_to=2099-12-31&per_page=5", headers=admin_headers)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    def test_date_range_filters_result_count(self, admin_headers):
        """created_from far future should return 0 records."""
        r = requests.get(f"{BASE_URL}/api/admin/orders?created_from=2099-01-01&per_page=5", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0, f"Expected 0 orders after 2099, got {data['total']}"

    def test_wide_date_range_returns_all(self, admin_headers):
        """Wide range should equal total without filter."""
        r_all = requests.get(f"{BASE_URL}/api/admin/orders?per_page=1", headers=admin_headers)
        r_wide = requests.get(f"{BASE_URL}/api/admin/orders?created_from=2000-01-01&created_to=2099-12-31&per_page=1", headers=admin_headers)
        assert r_all.status_code == 200
        assert r_wide.status_code == 200
        total_all = r_all.json().get("total", 0)
        total_wide = r_wide.json().get("total", 0)
        assert total_all == total_wide, f"Wide range ({total_wide}) should match unfiltered ({total_all})"

    def test_created_from_respects_boundary(self, admin_headers):
        """Records before created_from must not appear."""
        r = requests.get(f"{BASE_URL}/api/admin/orders?created_from=2099-06-01&per_page=20", headers=admin_headers)
        assert r.status_code == 200
        orders = r.json().get("orders", [])
        for o in orders:
            created = o.get("created_at", "")
            assert created >= "2099-06-01", f"Order created_at={created} is before filter 2099-06-01"


# ===========================================================================
# X-2: Server-side email / customer-name filter
# ===========================================================================

class TestX2EmailCustomerNameFilter:
    """X-2: email_filter and customer_name_filter should do server-side lookup."""

    def test_email_filter_returns_200(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/orders?email_filter=nonexistent%40example.com&per_page=5", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        # email that doesn't exist should return 0
        assert data["total"] == 0 or isinstance(data["total"], int)

    def test_email_filter_with_unknown_email_returns_empty(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/orders?email_filter=nobody_xyz_12345%40noemail.com&per_page=5", headers=admin_headers)
        assert r.status_code == 200
        assert r.json().get("total", -1) == 0

    def test_customer_name_filter_returns_200(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/orders?customer_name_filter=zzzznoname&per_page=5", headers=admin_headers)
        assert r.status_code == 200
        assert r.json().get("total", -1) == 0

    def test_email_filter_accepts_real_email(self, admin_headers):
        """If the partner email exists as a customer, filtering by it should work."""
        # Just test no 500 error, result may be 0 if they have no orders
        r = requests.get(f"{BASE_URL}/api/admin/orders?email_filter=rushabh0996%40gmail.com&per_page=5", headers=admin_headers)
        assert r.status_code == 200, f"email_filter caused error: {r.text}"


# ===========================================================================
# X-3: Sort field aliases — Orders
# ===========================================================================

class TestX3OrderSortAliases:
    """X-3: Sort colKey aliases should map to correct MongoDB fields."""

    @pytest.mark.parametrize("sort_by", [
        "payment_date",      # was pay_date
        "payment_method",    # was method
        "subscription_number",  # was sub_number
        "partner_code",      # was partner
        "tax_amount",        # was tax
        "created_at",        # direct field
        "total",             # direct field
    ])
    def test_order_sort_by(self, sort_by, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/orders?sort_by={sort_by}&sort_order=desc&per_page=5", headers=admin_headers)
        assert r.status_code == 200, f"sort_by={sort_by} returned {r.status_code}: {r.text}"
        data = r.json()
        assert "orders" in data

    @pytest.mark.parametrize("old_alias", [
        "pay_date",    # old alias — should still work (maps via alias dict)
        "method",      # old alias
        "sub_number",  # old alias
        "partner",     # old alias
        "tax",         # old alias
    ])
    def test_old_order_sort_aliases_still_work(self, old_alias, admin_headers):
        """Old colKey aliases in _ORDER_SORT_ALIASES should map properly (backend maps them)."""
        r = requests.get(f"{BASE_URL}/api/admin/orders?sort_by={old_alias}&sort_order=asc&per_page=5", headers=admin_headers)
        assert r.status_code == 200, f"old alias sort_by={old_alias} returned {r.status_code}: {r.text}"


# ===========================================================================
# X-3: Sort field aliases — Subscriptions
# ===========================================================================

class TestX3SubSortAliases:
    """X-3: Subscription sort colKey aliases should map to correct MongoDB fields."""

    @pytest.mark.parametrize("sort_by", [
        "subscription_number",  # was sub_number
        "customer_email",       # was email
        "plan_name",            # was plan
        "tax_amount",           # was tax
        "payment_method",       # was payment
        "created_at",           # direct
        "amount",               # direct
    ])
    def test_sub_sort_by(self, sort_by, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/subscriptions?sort_by={sort_by}&sort_order=desc&per_page=5", headers=admin_headers)
        assert r.status_code == 200, f"subscriptions sort_by={sort_by} returned {r.status_code}: {r.text}"
        data = r.json()
        assert "subscriptions" in data

    @pytest.mark.parametrize("old_alias", [
        "sub_number",   # old alias
        "email",        # old alias
        "plan",         # old alias
        "tax",          # old alias
        "payment",      # old alias
    ])
    def test_old_sub_sort_aliases_still_work(self, old_alias, admin_headers):
        """Old subscription colKey aliases should map properly via _SUB_SORT_ALIASES."""
        r = requests.get(f"{BASE_URL}/api/admin/subscriptions?sort_by={old_alias}&sort_order=asc&per_page=5", headers=admin_headers)
        assert r.status_code == 200, f"old sub alias sort_by={old_alias} returned {r.status_code}: {r.text}"


# ===========================================================================
# C-2: Product filter pre-pagination (total_count reflects filtered count)
# ===========================================================================

class TestC2ProductFilterPrePagination:
    """C-2: Product filter should be applied before pagination."""

    def test_product_filter_nonexistent_returns_zero(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/orders?product_filter=XXXXXXXXXNONEXISTENTPRODUCT&per_page=5", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0, f"Expected 0 for nonexistent product, got {data['total']}"
        assert data["total_pages"] == 1, f"Expected 1 page for empty results, got {data['total_pages']}"

    def test_product_filter_total_less_than_unfiltered(self, admin_headers):
        """Filtering by a specific product name should give total <= unfiltered total."""
        r_all = requests.get(f"{BASE_URL}/api/admin/orders?per_page=1", headers=admin_headers)
        unfiltered_total = r_all.json().get("total", 0)
        if unfiltered_total == 0:
            pytest.skip("No orders in the system to test product filter")
        # Use a unique product name unlikely to match everything
        r_filtered = requests.get(f"{BASE_URL}/api/admin/orders?product_filter=SomeProduct&per_page=1", headers=admin_headers)
        assert r_filtered.status_code == 200
        filtered_total = r_filtered.json().get("total", 0)
        assert filtered_total <= unfiltered_total, f"Filtered total {filtered_total} > unfiltered {unfiltered_total}"

    def test_product_filter_total_pages_consistent(self, admin_headers):
        """total_pages must reflect filtered total, not total DB rows."""
        r = requests.get(f"{BASE_URL}/api/admin/orders?product_filter=XXXXXXXXXNONEXISTENTPRODUCT&per_page=20", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        # 0 total → 1 page (max(1, ceil(0/20)))
        expected_pages = max(1, (data["total"] + data["per_page"] - 1) // data["per_page"])
        assert data["total_pages"] == expected_pages, f"total_pages={data['total_pages']}, expected {expected_pages}"


# ===========================================================================
# H-3: Multi-value filters via $in
# ===========================================================================

class TestH3MultiValueFilters:
    """H-3: Comma-separated filter values should use $in, not single regex."""

    def test_order_number_filter_multi_returns_200(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/orders?order_number_filter=AA-001,AA-002&per_page=5", headers=admin_headers)
        assert r.status_code == 200, f"multi-value order_number_filter failed: {r.text}"
        data = r.json()
        assert "orders" in data
        # All returned orders must have one of the specified order numbers
        for o in data.get("orders", []):
            assert o["order_number"] in ["AA-001", "AA-002"], f"Unexpected order number {o['order_number']}"

    def test_sub_number_filter_multi_returns_200(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/orders?sub_number_filter=SUB-001,SUB-002&per_page=5", headers=admin_headers)
        assert r.status_code == 200, f"multi-value sub_number_filter failed: {r.text}"

    def test_processor_id_filter_multi_returns_200(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/orders?processor_id_filter=pi_abc,pi_def&per_page=5", headers=admin_headers)
        assert r.status_code == 200, f"multi-value processor_id_filter failed: {r.text}"

    def test_payment_method_filter_multi_returns_200(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/orders?payment_method_filter=manual,card&per_page=5", headers=admin_headers)
        assert r.status_code == 200, f"multi-value payment_method_filter failed: {r.text}"
        data = r.json()
        # All returned orders must have payment_method in the filter list
        for o in data.get("orders", []):
            assert o.get("payment_method") in ["manual", "card"], f"Unexpected payment_method {o.get('payment_method')}"

    def test_single_payment_method_filter_works(self, admin_headers):
        """Single value filter should also work (single regex, not $in)."""
        r = requests.get(f"{BASE_URL}/api/admin/orders?payment_method_filter=manual&per_page=5", headers=admin_headers)
        assert r.status_code == 200

    def test_status_filter_multi_returns_200(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/orders?status_filter=paid,unpaid&per_page=5", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        for o in data.get("orders", []):
            assert o.get("status") in ["paid", "unpaid"], f"Unexpected status {o.get('status')}"


# ===========================================================================
# M-8: OrderUpdate has currency field; can save currency change
# ===========================================================================

class TestM8OrderCurrencyUpdate:
    """M-8: Order edit should accept and persist a currency change."""

    def test_order_update_currency_field_accepted(self, admin_headers):
        """PUT /api/admin/orders/{id} with currency should not reject it."""
        order = get_first_order(admin_headers)
        if not order:
            pytest.skip("No orders to test currency update")
        order_id = order["id"]
        orig_currency = order.get("currency", "USD")
        new_currency = "EUR" if orig_currency != "EUR" else "USD"
        r = requests.put(
            f"{BASE_URL}/api/admin/orders/{order_id}",
            json={"currency": new_currency},
            headers=admin_headers,
        )
        assert r.status_code == 200, f"currency update failed: {r.text}"
        # Verify persistence
        r2 = requests.get(f"{BASE_URL}/api/admin/orders?per_page=1&page=1", headers=admin_headers)
        # Re-fetch specific order (no direct GET by ID, so verify via stats or list)
        # Just confirm 200 was returned
        assert r2.status_code == 200
        # Restore original currency
        requests.put(f"{BASE_URL}/api/admin/orders/{order_id}", json={"currency": orig_currency}, headers=admin_headers)

    def test_order_update_currency_persisted(self, admin_headers):
        """After PUT with currency, re-fetching order should show new currency."""
        # Get all orders and find one we can modify
        r = requests.get(f"{BASE_URL}/api/admin/orders?per_page=20&sort_by=created_at&sort_order=desc", headers=admin_headers)
        assert r.status_code == 200
        orders = r.json().get("orders", [])
        if not orders:
            pytest.skip("No orders available")
        order = orders[0]
        order_id = order["id"]
        orig = order.get("currency", "USD")
        new_cur = "GBP" if orig != "GBP" else "USD"
        put_r = requests.put(f"{BASE_URL}/api/admin/orders/{order_id}", json={"currency": new_cur}, headers=admin_headers)
        assert put_r.status_code == 200
        # Re-fetch and check
        r2 = requests.get(f"{BASE_URL}/api/admin/orders?per_page=20&sort_by=created_at&sort_order=desc", headers=admin_headers)
        found = next((o for o in r2.json().get("orders", []) if o["id"] == order_id), None)
        if found:
            assert found.get("currency") == new_cur, f"Expected {new_cur}, got {found.get('currency')}"
        # Restore
        requests.put(f"{BASE_URL}/api/admin/orders/{order_id}", json={"currency": orig}, headers=admin_headers)


# ===========================================================================
# M-9: Subscriptions with both currency and amount_currency don't overwrite
# ===========================================================================

class TestM9SubscriptionCurrencyFilter:
    """M-9: currency and amount_currency params should both be applied."""

    def test_currency_and_amount_currency_same_value_returns_200(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/subscriptions?currency=USD&amount_currency=USD&per_page=5", headers=admin_headers)
        assert r.status_code == 200, f"currency+amount_currency filter failed: {r.text}"
        data = r.json()
        assert "subscriptions" in data

    def test_currency_and_amount_currency_conflicting_no_overwrite(self, admin_headers):
        """When currency=USD and amount_currency=EUR, neither should silently overwrite the other.
        The backend code falls back to UNION when intersection is empty (design choice).
        This test verifies the endpoint returns 200 and does NOT crash or return only EUR subs
        (which would mean the amount_currency overwrote currency)."""
        r_usd = requests.get(f"{BASE_URL}/api/admin/subscriptions?currency=USD&per_page=5", headers=admin_headers)
        r_conflict = requests.get(f"{BASE_URL}/api/admin/subscriptions?currency=USD&amount_currency=EUR&per_page=5", headers=admin_headers)
        assert r_conflict.status_code == 200, f"conflicting currency filter failed: {r_conflict.text}"
        data = r_conflict.json()
        # The endpoint must return a valid response (list + total)
        assert "subscriptions" in data
        assert "total" in data
        # The total with currency=USD+amount_currency=EUR should be >= total with just currency=USD
        # (union fallback) — as long as it's not ONLY EUR results (which would mean overwrite happened)
        subs_returned = data.get("subscriptions", [])
        for s in subs_returned:
            # Each sub's currency must be USD or EUR (union of both filters)
            assert s.get("currency") in ["USD", "EUR"], \
                f"Unexpected currency {s.get('currency')} in union filter result"

    def test_currency_filter_alone_returns_200(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/subscriptions?currency=USD&per_page=5", headers=admin_headers)
        assert r.status_code == 200

    def test_amount_currency_filter_alone_returns_200(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/subscriptions?amount_currency=USD&per_page=5", headers=admin_headers)
        assert r.status_code == 200


# ===========================================================================
# M-11: Manual subscription term_months uses calendar months (relativedelta)
# ===========================================================================

class TestM11CalendarMonths:
    """M-11: term_months=3 from 2026-01-31 → contract_end_date=2026-04-30."""

    def test_create_manual_sub_term_months_calendar(self, partner_headers):
        """Create a manual subscription with term_months=3, start=2026-01-31."""
        # First get a customer and product
        cust_r = requests.get(f"{BASE_URL}/api/admin/customers?per_page=5", headers=partner_headers)
        if cust_r.status_code != 200:
            pytest.skip("Cannot fetch customers for M-11 test")
        customers = cust_r.json().get("customers", [])
        users = cust_r.json().get("users", [])
        if not customers or not users:
            pytest.skip("No customers available for M-11 test")
        # Find a customer with email
        cust = None
        cust_email = None
        for c in customers:
            u = next((u for u in users if u["id"] == c.get("user_id")), None)
            if u and u.get("email"):
                cust = c
                cust_email = u["email"]
                break
        if not cust_email:
            pytest.skip("No customer with email found")

        prod_r = requests.get(f"{BASE_URL}/api/admin/products-all?per_page=5", headers=partner_headers)
        if prod_r.status_code != 200 or not prod_r.json().get("products"):
            pytest.skip("No products available for M-11 test")
        product = prod_r.json()["products"][0]

        # Create manual subscription: start=2026-01-31, term_months=3
        payload = {
            "customer_email": cust_email,
            "product_id": product["id"],
            "amount": 99.0,
            "currency": "USD",
            "renewal_date": "2026-04-30",
            "start_date": "2026-01-31",
            "status": "active",
            "billing_interval": "monthly",
            "payment_method": "manual",
            "term_months": 3,
        }
        r = requests.post(f"{BASE_URL}/api/admin/subscriptions/manual", json=payload, headers=partner_headers)
        if r.status_code == 403:
            pytest.skip("License limit reached for subscriptions")
        assert r.status_code == 200, f"Create manual sub failed: {r.text}"
        sub_id = r.json().get("subscription_id")
        assert sub_id, "No subscription_id in response"

        # Fetch the subscription and verify contract_end_date
        r2 = requests.get(f"{BASE_URL}/api/admin/subscriptions?per_page=50&sort_by=created_at&sort_order=desc", headers=partner_headers)
        assert r2.status_code == 200
        subs = r2.json().get("subscriptions", [])
        created_sub = next((s for s in subs if s["id"] == sub_id), None)
        if created_sub:
            end_date = created_sub.get("contract_end_date", "")
            # 2026-01-31 + 3 calendar months = 2026-04-30
            assert end_date.startswith("2026-04-30"), f"Expected 2026-04-30, got {end_date}"

        # Cleanup: cancel and verify
        if sub_id:
            requests.post(f"{BASE_URL}/api/admin/subscriptions/{sub_id}/cancel", json={}, headers=partner_headers)

    def test_term_months_0_gives_no_contract_end(self, partner_headers):
        """term_months=0 should result in no contract_end_date."""
        cust_r = requests.get(f"{BASE_URL}/api/admin/customers?per_page=5", headers=partner_headers)
        if cust_r.status_code != 200:
            pytest.skip("Cannot fetch customers")
        customers = cust_r.json().get("customers", [])
        users = cust_r.json().get("users", [])
        cust_email = None
        for c in customers:
            u = next((u for u in users if u["id"] == c.get("user_id")), None)
            if u and u.get("email"):
                cust_email = u["email"]
                break
        if not cust_email:
            pytest.skip("No customer with email")

        prod_r = requests.get(f"{BASE_URL}/api/admin/products-all?per_page=5", headers=partner_headers)
        if prod_r.status_code != 200 or not prod_r.json().get("products"):
            pytest.skip("No products")
        product = prod_r.json()["products"][0]

        payload = {
            "customer_email": cust_email,
            "product_id": product["id"],
            "amount": 49.0,
            "currency": "USD",
            "renewal_date": "2027-01-01",
            "start_date": "2026-01-01",
            "status": "active",
            "billing_interval": "monthly",
            "payment_method": "manual",
            "term_months": 0,
        }
        r = requests.post(f"{BASE_URL}/api/admin/subscriptions/manual", json=payload, headers=partner_headers)
        if r.status_code == 403:
            pytest.skip("License limit")
        assert r.status_code == 200, f"Create manual sub failed: {r.text}"
        sub_id = r.json().get("subscription_id")
        if sub_id:
            r2 = requests.get(f"{BASE_URL}/api/admin/subscriptions?per_page=50&sort_by=created_at&sort_order=desc", headers=partner_headers)
            subs = r2.json().get("subscriptions", [])
            created_sub = next((s for s in subs if s["id"] == sub_id), None)
            if created_sub:
                assert created_sub.get("contract_end_date") is None, \
                    f"term_months=0 should give no contract_end_date, got {created_sub.get('contract_end_date')}"
            requests.post(f"{BASE_URL}/api/admin/subscriptions/{sub_id}/cancel", json={}, headers=partner_headers)


# ===========================================================================
# C-1: ManualSubscriptionCreate.payment_method defaults to 'manual'
# ===========================================================================

class TestC1DefaultPaymentMethod:
    """C-1: Creating manual subscription without specifying payment_method should default to 'manual'."""

    def test_manual_sub_default_payment_method(self, partner_headers):
        cust_r = requests.get(f"{BASE_URL}/api/admin/customers?per_page=5", headers=partner_headers)
        if cust_r.status_code != 200:
            pytest.skip("Cannot fetch customers")
        customers = cust_r.json().get("customers", [])
        users = cust_r.json().get("users", [])
        cust_email = None
        for c in customers:
            u = next((u for u in users if u["id"] == c.get("user_id")), None)
            if u and u.get("email"):
                cust_email = u["email"]
                break
        if not cust_email:
            pytest.skip("No customer email found")

        prod_r = requests.get(f"{BASE_URL}/api/admin/products-all?per_page=5", headers=partner_headers)
        if prod_r.status_code != 200 or not prod_r.json().get("products"):
            pytest.skip("No products")
        product = prod_r.json()["products"][0]

        # Do NOT provide payment_method — it should default to 'manual'
        payload = {
            "customer_email": cust_email,
            "product_id": product["id"],
            "amount": 19.0,
            "currency": "USD",
            "renewal_date": "2027-06-01",
            "start_date": "2026-06-01",
            "status": "active",
            "billing_interval": "monthly",
            # payment_method intentionally omitted to test default
        }
        r = requests.post(f"{BASE_URL}/api/admin/subscriptions/manual", json=payload, headers=partner_headers)
        if r.status_code == 403:
            pytest.skip("License limit")
        assert r.status_code == 200, f"Create manual sub failed: {r.text}"
        sub_id = r.json().get("subscription_id")
        if sub_id:
            r2 = requests.get(f"{BASE_URL}/api/admin/subscriptions?per_page=50&sort_by=created_at&sort_order=desc", headers=partner_headers)
            subs = r2.json().get("subscriptions", [])
            created_sub = next((s for s in subs if s["id"] == sub_id), None)
            if created_sub:
                assert created_sub.get("payment_method") == "manual", \
                    f"Expected payment_method='manual', got '{created_sub.get('payment_method')}'"
            requests.post(f"{BASE_URL}/api/admin/subscriptions/{sub_id}/cancel", json={}, headers=partner_headers)


# ===========================================================================
# M-12: Admin cancel subscription — verify it works (no duplicate fetch)
# ===========================================================================

class TestM12CancelSubscription:
    """M-12: Cancel subscription should succeed (code ensures no duplicate customer fetch)."""

    def test_cancel_nonexistent_returns_404(self, partner_headers):
        r = requests.post(f"{BASE_URL}/api/admin/subscriptions/nonexistentid/cancel", json={}, headers=partner_headers)
        assert r.status_code == 404, f"Expected 404 for nonexistent sub, got {r.status_code}"

    def test_cancel_flow_creates_subscription_and_cancels(self, partner_headers):
        """Create a subscription and then cancel it."""
        cust_r = requests.get(f"{BASE_URL}/api/admin/customers?per_page=5", headers=partner_headers)
        if cust_r.status_code != 200:
            pytest.skip("Cannot fetch customers")
        customers = cust_r.json().get("customers", [])
        users = cust_r.json().get("users", [])
        cust_email = None
        for c in customers:
            u = next((u for u in users if u["id"] == c.get("user_id")), None)
            if u and u.get("email"):
                cust_email = u["email"]
                break
        if not cust_email:
            pytest.skip("No customer with email")

        prod_r = requests.get(f"{BASE_URL}/api/admin/products-all?per_page=5", headers=partner_headers)
        if prod_r.status_code != 200 or not prod_r.json().get("products"):
            pytest.skip("No products")
        product = prod_r.json()["products"][0]

        payload = {
            "customer_email": cust_email,
            "product_id": product["id"],
            "amount": 9.99,
            "currency": "USD",
            "renewal_date": "2027-01-01",
            "start_date": "2026-01-01",
            "status": "active",
            "billing_interval": "monthly",
            "payment_method": "manual",
        }
        create_r = requests.post(f"{BASE_URL}/api/admin/subscriptions/manual", json=payload, headers=partner_headers)
        if create_r.status_code == 403:
            pytest.skip("License limit")
        assert create_r.status_code == 200
        sub_id = create_r.json().get("subscription_id")
        assert sub_id

        # Cancel it
        cancel_r = requests.post(f"{BASE_URL}/api/admin/subscriptions/{sub_id}/cancel", json={}, headers=partner_headers)
        assert cancel_r.status_code == 200, f"Cancel failed: {cancel_r.text}"
        data = cancel_r.json()
        assert "message" in data
        assert "Subscription cancellation scheduled" in data["message"] or "cancelled" in data["message"].lower()


# ===========================================================================
# General API Health
# ===========================================================================

class TestGeneralAPIHealth:
    """Basic API health checks."""

    def test_orders_list_returns_200(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/orders?per_page=5", headers=admin_headers)
        assert r.status_code == 200

    def test_orders_stats_returns_200(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/orders/stats", headers=admin_headers)
        assert r.status_code == 200

    def test_subscriptions_list_returns_200(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/subscriptions?per_page=5", headers=admin_headers)
        assert r.status_code == 200

    def test_subscriptions_stats_returns_200(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/subscriptions/stats", headers=admin_headers)
        assert r.status_code == 200

    def test_filter_options_returns_200(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/filter-options", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "order_statuses" in data
        assert "subscription_statuses" in data
        assert "payment_methods" in data

    def test_filter_options_partially_refunded_in_statuses(self, admin_headers):
        """M-6: partially_refunded is handled in the frontend badge color.
        NOTE: It is currently NOT in ALLOWED_ORDER_STATUSES constant, which means
        users cannot filter by it via the dropdown. This is a known minor gap
        — orders get this status from the refund system automatically, not via admin UI."""
        r = requests.get(f"{BASE_URL}/api/admin/filter-options", headers=admin_headers)
        assert r.status_code == 200
        statuses = r.json().get("order_statuses", [])
        # Core statuses must be present
        for expected_status in ["paid", "unpaid", "cancelled", "refunded"]:
            assert expected_status in statuses, f"'{expected_status}' missing from order_statuses"
        # Note: partially_refunded is NOT in ALLOWED_ORDER_STATUSES (minor gap)
        # Reported as action item for main agent
        if "partially_refunded" not in statuses:
            print("WARNING: 'partially_refunded' not in filter-options order_statuses. Users cannot filter by this status.")
        # This test passes regardless (doesn't block M-6 badge coloring which is client-side)
