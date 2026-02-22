"""
Iteration 36 tests: filter-options endpoint, new filters for subscriptions/orders,
cs_ prefix deep-links, patched data verification (SUB-7EF107CB, AA-7BE7DB36)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASS = "ChangeMe123!"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin JWT token"""
    r = requests.post(f"{BASE_URL}/api/admin/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text}")
    data = r.json()
    token = data.get("token") or data.get("access_token")
    if not token:
        pytest.skip("No token in login response")
    return token


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ─── filter-options endpoint ─────────────────────────────────────────────────

class TestFilterOptions:
    """GET /api/admin/filter-options - single source of truth"""

    def test_filter_options_status_200(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/filter-options", headers=auth_headers)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    def test_filter_options_has_order_statuses(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/filter-options", headers=auth_headers)
        data = r.json()
        assert "order_statuses" in data
        assert isinstance(data["order_statuses"], list)
        assert len(data["order_statuses"]) > 0

    def test_filter_options_has_subscription_statuses(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/filter-options", headers=auth_headers)
        data = r.json()
        assert "subscription_statuses" in data
        assert isinstance(data["subscription_statuses"], list)
        assert len(data["subscription_statuses"]) > 0

    def test_filter_options_has_payment_methods(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/filter-options", headers=auth_headers)
        data = r.json()
        assert "payment_methods" in data
        assert isinstance(data["payment_methods"], list)
        assert len(data["payment_methods"]) > 0

    def test_filter_options_has_bank_transaction_statuses(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/filter-options", headers=auth_headers)
        data = r.json()
        assert "bank_transaction_statuses" in data
        assert isinstance(data["bank_transaction_statuses"], list)
        assert len(data["bank_transaction_statuses"]) > 0

    def test_subscription_statuses_contains_pending_direct_debit(self, auth_headers):
        """pending_direct_debit_setup must be present in subscription_statuses"""
        r = requests.get(f"{BASE_URL}/api/admin/filter-options", headers=auth_headers)
        data = r.json()
        assert "pending_direct_debit_setup" in data["subscription_statuses"]

    def test_order_statuses_contains_pending_direct_debit(self, auth_headers):
        """pending_direct_debit_setup must be present in order_statuses"""
        r = requests.get(f"{BASE_URL}/api/admin/filter-options", headers=auth_headers)
        data = r.json()
        assert "pending_direct_debit_setup" in data["order_statuses"]

    def test_payment_methods_contains_card(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/filter-options", headers=auth_headers)
        data = r.json()
        assert "card" in data["payment_methods"]

    def test_bank_transaction_statuses_values(self, auth_headers):
        """Check known bank transaction statuses are present"""
        r = requests.get(f"{BASE_URL}/api/admin/filter-options", headers=auth_headers)
        data = r.json()
        expected = {"pending", "completed", "matched", "failed", "refunded"}
        actual = set(data["bank_transaction_statuses"])
        missing = expected - actual
        assert not missing, f"Missing bank_transaction_statuses: {missing}"


# ─── Subscriptions new filters ────────────────────────────────────────────────

class TestSubscriptionFilters:
    """New subscription filter params: sub_number, processor_id_filter, plan_name_filter, renewal_from/to, payment"""

    def test_sub_number_filter_returns_SUB_7EF(self, auth_headers):
        """Filter by sub# prefix SUB-7EF should return SUB-7EF107CB"""
        r = requests.get(f"{BASE_URL}/api/admin/subscriptions?sub_number=SUB-7EF", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "subscriptions" in data
        subs = data["subscriptions"]
        assert len(subs) > 0, "Expected at least 1 subscription matching SUB-7EF"
        numbers = [s.get("subscription_number", "") for s in subs]
        assert any("SUB-7EF" in n for n in numbers), f"No sub with SUB-7EF in: {numbers}"

    def test_plan_name_filter_bookkeeping(self, auth_headers):
        """Filter by plan_name_filter=Bookkeeping"""
        r = requests.get(f"{BASE_URL}/api/admin/subscriptions?plan_name_filter=Bookkeeping", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        subs = data["subscriptions"]
        assert len(subs) > 0, "Expected bookkeeping subscriptions"
        for s in subs:
            assert "bookkeeping" in s.get("plan_name", "").lower(), \
                f"plan_name '{s.get('plan_name')}' doesn't contain 'bookkeeping'"

    def test_payment_filter_card(self, auth_headers):
        """Filter by payment=card"""
        r = requests.get(f"{BASE_URL}/api/admin/subscriptions?payment=card", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        subs = data["subscriptions"]
        for s in subs:
            assert s.get("payment_method") == "card", \
                f"Expected payment_method=card, got {s.get('payment_method')}"

    def test_status_filter_active(self, auth_headers):
        """Filter by status=active"""
        r = requests.get(f"{BASE_URL}/api/admin/subscriptions?status=active", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        subs = data["subscriptions"]
        for s in subs:
            assert s.get("status") == "active", f"Expected active, got {s.get('status')}"

    def test_renewal_from_filter(self, auth_headers):
        """Filter by renewal_from=2026-03-01"""
        r = requests.get(f"{BASE_URL}/api/admin/subscriptions?renewal_from=2026-03-01", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        subs = data["subscriptions"]
        for s in subs:
            rd = s.get("renewal_date", "")
            assert rd >= "2026-03-01", f"renewal_date {rd} before 2026-03-01"

    def test_processor_id_filter(self, auth_headers):
        """Filter by processor_id_filter=cs_ returns cs_ prefixed IDs"""
        r = requests.get(f"{BASE_URL}/api/admin/subscriptions?processor_id_filter=cs_", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        # Should at least return HTTP 200; may or may not have results
        assert "subscriptions" in data

    def test_sub_7ef107cb_has_renewal_date(self, auth_headers):
        """The patched subscription SUB-7EF107CB must have renewal_date set"""
        r = requests.get(f"{BASE_URL}/api/admin/subscriptions?sub_number=SUB-7EF107CB", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        subs = data["subscriptions"]
        assert len(subs) >= 1, "SUB-7EF107CB not found"
        sub = next((s for s in subs if s.get("subscription_number") == "SUB-7EF107CB"), None)
        assert sub is not None, "SUB-7EF107CB not found in results"
        assert sub.get("renewal_date"), f"renewal_date is empty for SUB-7EF107CB: {sub}"


# ─── Orders new filters ────────────────────────────────────────────────────────

class TestOrderFilters:
    """New order filter params: sub_number_filter, processor_id_filter, payment_method_filter, pay_date_from/to"""

    def test_sub_number_filter_returns_AA_7BE7DB36(self, auth_headers):
        """Filter by sub_number_filter=SUB-7EF should return order AA-7BE7DB36"""
        r = requests.get(f"{BASE_URL}/api/admin/orders?sub_number_filter=SUB-7EF", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        orders = data.get("orders", [])
        assert len(orders) > 0, "Expected orders matching sub_number_filter=SUB-7EF"
        order_numbers = [o.get("order_number", "") for o in orders]
        assert any("AA-7BE7DB36" in n for n in order_numbers), f"AA-7BE7DB36 not found in: {order_numbers}"

    def test_payment_method_filter_card(self, auth_headers):
        """Filter by payment_method_filter=card returns card orders"""
        r = requests.get(f"{BASE_URL}/api/admin/orders?payment_method_filter=card", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        orders = data.get("orders", [])
        for o in orders:
            assert o.get("payment_method") == "card", \
                f"Expected card, got {o.get('payment_method')}"

    def test_processor_id_filter_pi(self, auth_headers):
        """Filter by processor_id_filter=pi_ returns orders with pi_ processor IDs"""
        r = requests.get(f"{BASE_URL}/api/admin/orders?processor_id_filter=pi_", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        orders = data.get("orders", [])
        for o in orders:
            assert o.get("processor_id", "").startswith("pi_"), \
                f"processor_id '{o.get('processor_id')}' does not start with pi_"

    def test_order_AA_7BE7DB36_has_subscription_number(self, auth_headers):
        """Patched order AA-7BE7DB36 must have subscription_number=SUB-7EF107CB"""
        r = requests.get(f"{BASE_URL}/api/admin/orders?order_number_filter=AA-7BE7DB36", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        orders = data.get("orders", [])
        assert len(orders) >= 1, "AA-7BE7DB36 not found"
        order = next((o for o in orders if o.get("order_number") == "AA-7BE7DB36"), None)
        assert order is not None, "AA-7BE7DB36 not found exactly"
        assert order.get("subscription_number") == "SUB-7EF107CB", \
            f"subscription_number={order.get('subscription_number')}, expected SUB-7EF107CB"

    def test_order_AA_7BE7DB36_has_payment_date(self, auth_headers):
        """Patched order AA-7BE7DB36 must have payment_date set"""
        r = requests.get(f"{BASE_URL}/api/admin/orders?order_number_filter=AA-7BE7DB36", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        orders = data.get("orders", [])
        order = next((o for o in orders if o.get("order_number") == "AA-7BE7DB36"), None)
        assert order is not None, "AA-7BE7DB36 not found"
        assert order.get("payment_date"), f"payment_date is empty for AA-7BE7DB36: {order}"

    def test_pay_date_filter_range(self, auth_headers):
        """pay_date_from/to filter works without error"""
        r = requests.get(f"{BASE_URL}/api/admin/orders?pay_date_from=2026-01-01&pay_date_to=2026-12-31", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "orders" in data


# ─── cs_ prefix deep-link ────────────────────────────────────────────────────

class TestCsDeepLink:
    """cs_ prefix should generate stripe checkout session deep-link"""

    def test_cs_prefix_subscription_exists_and_has_processor_id(self, auth_headers):
        """SUB-7EF107CB processor_id starts with cs_"""
        r = requests.get(f"{BASE_URL}/api/admin/subscriptions?sub_number=SUB-7EF107CB", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        subs = data["subscriptions"]
        sub = next((s for s in subs if s.get("subscription_number") == "SUB-7EF107CB"), None)
        assert sub is not None, "SUB-7EF107CB not found"
        pid = sub.get("processor_id", "")
        assert pid.startswith("cs_"), f"processor_id should start with cs_, got: {pid}"

    def test_cs_prefix_subscription_filter_returns_results(self, auth_headers):
        """Filtering by processor_id_filter=cs_test should return SUB-7EF107CB"""
        r = requests.get(f"{BASE_URL}/api/admin/subscriptions?processor_id_filter=cs_test", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        subs = data["subscriptions"]
        assert len(subs) > 0, "Expected cs_test subscriptions from filter"
        assert any(s.get("processor_id", "").startswith("cs_") for s in subs)
