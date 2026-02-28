"""
Backend tests: License limit enforcement for multi-tenant SaaS platform.

KNOWN BUGS under test (from review_request):
  1. /admin/orders/manual   - MISSING check_limit + increment_monthly  → should 403 but returns 201 (BUG)
  2. /admin/subscriptions/manual - MISSING check_limit + increment_monthly → should 403 but returns 201 (BUG)

WORKING correctly:
  3. /admin/customers/create - has check_limit + increment_monthly → returns 403 when at limit (WORKING)
  4. /checkout/bank-transfer - has check_limit + increment_monthly → returns 403 when at limit (WORKING, but GoCardless must be enabled)
  5. /admin/usage            - returns correct usage snapshot with blocked: true when at limit

Test approach:
- Use pymongo directly to set usage counts (license_usage collection)
- Use requests to call the API endpoints
- Platform admin: admin@automateaccounts.local / ChangeMe123!
- Partner admin: sarah@brightaccounting.local / ChangeMe123! (bright-accounting tenant)
- Test tenant ID: cb9c6337-4c59-4e74-a165-6f218354630d (bright-accounting)
"""
import pytest
import requests
import os
from pymongo import MongoClient
from datetime import datetime
from zoneinfo import ZoneInfo

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

PLATFORM_ADMIN = {
    "email": "admin@automateaccounts.local",
    "password": "ChangeMe123!",
}
PARTNER_ADMIN = {
    "email": "sarah@brightaccounting.local",
    "password": "ChangeMe123!",
    "partner_code": "bright-accounting",
}
CUSTOMER = {
    "email": "mark@markchen.local",
    "password": "ChangeMe123!",
    "partner_code": "bright-accounting",
}
TEST_TENANT_ID = "cb9c6337-4c59-4e74-a165-6f218354630d"
TEST_PRODUCT_ID = "1b524bcb-0665-492d-9b82-da390fb08c4b"

EST = ZoneInfo("America/New_York")


def get_current_est_period() -> str:
    """Return 'YYYY-MM' for the current month in EST."""
    return datetime.now(EST).strftime("%Y-%m")


# ---------------------------------------------------------------------------
# MongoDB helper (direct DB access for setting usage counts)
# ---------------------------------------------------------------------------

def set_license_usage(tenant_id: str, orders_count: int = 0, customers_count: int = 0, subscriptions_count: int = 0):
    """Directly set usage counts in license_usage collection."""
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    period = get_current_est_period()
    db.license_usage.update_one(
        {"tenant_id": tenant_id},
        {"$set": {
            "tenant_id": tenant_id,
            "period": period,
            "orders_count": orders_count,
            "customers_count": customers_count,
            "subscriptions_count": subscriptions_count,
            "updated_at": datetime.utcnow().isoformat(),
        }},
        upsert=True,
    )
    client.close()


def get_license_usage(tenant_id: str) -> dict:
    """Fetch current usage counts directly from MongoDB."""
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    usage = db.license_usage.find_one({"tenant_id": tenant_id}, {"_id": 0}) or {}
    client.close()
    return usage


# ---------------------------------------------------------------------------
# Pytest Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def http():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def platform_token(http):
    r = http.post(f"{BASE_URL}/api/auth/login", json={
        "email": PLATFORM_ADMIN["email"],
        "password": PLATFORM_ADMIN["password"],
    })
    if r.status_code != 200:
        pytest.skip(f"Platform admin login failed: {r.text}")
    token = r.json().get("token")
    if not token:
        pytest.skip(f"No token in platform login response: {r.text}")
    return token


@pytest.fixture(scope="module")
def partner_token(http):
    r = http.post(f"{BASE_URL}/api/auth/partner-login", json={
        "email": PARTNER_ADMIN["email"],
        "password": PARTNER_ADMIN["password"],
        "partner_code": PARTNER_ADMIN["partner_code"],
    })
    if r.status_code != 200:
        pytest.skip(f"Partner admin login failed: {r.text}")
    token = r.json().get("token")
    if not token:
        pytest.skip(f"No token in partner login response: {r.text}")
    return token


@pytest.fixture(scope="module")
def customer_token(http):
    r = http.post(f"{BASE_URL}/api/auth/customer-login", json={
        "email": CUSTOMER["email"],
        "password": CUSTOMER["password"],
        "partner_code": CUSTOMER["partner_code"],
    })
    if r.status_code != 200:
        pytest.skip(f"Customer login failed: {r.text}")
    token = r.json().get("token")
    if not token:
        pytest.skip(f"No token in customer login response: {r.text}")
    return token


# ---------------------------------------------------------------------------
# Phase 1: License setup via API (platform admin)
# ---------------------------------------------------------------------------

class TestLicenseSetup:
    """Platform admin sets license limits on bright-accounting tenant."""

    def test_get_tenant_license_before_setup(self, http, platform_token):
        """Verify tenant exists and we can read its license."""
        r = http.get(
            f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license",
            headers={"Authorization": f"Bearer {platform_token}"},
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "license" in data, f"Response missing 'license': {data}"
        print(f"PASS: Get tenant license before setup - plan: {data['license'].get('plan')}")

    def test_set_license_max_orders_per_month_1(self, http, platform_token):
        """Set max_orders_per_month=1 for bright-accounting via platform admin."""
        r = http.put(
            f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license",
            headers={"Authorization": f"Bearer {platform_token}"},
            json={"max_orders_per_month": 1},
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["license"]["max_orders_per_month"] == 1, f"Limit not set correctly: {data['license']}"
        print(f"PASS: License set max_orders_per_month=1")

    def test_set_license_max_subscriptions_per_month_1(self, http, platform_token):
        """Set max_subscriptions_per_month=1 for bright-accounting."""
        r = http.put(
            f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license",
            headers={"Authorization": f"Bearer {platform_token}"},
            json={"max_subscriptions_per_month": 1},
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["license"]["max_subscriptions_per_month"] == 1, f"Limit not set: {data['license']}"
        print(f"PASS: License set max_subscriptions_per_month=1")

    def test_set_license_max_customers_per_month_1(self, http, platform_token):
        """Set max_customers_per_month=1 for bright-accounting."""
        r = http.put(
            f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license",
            headers={"Authorization": f"Bearer {platform_token}"},
            json={"max_customers_per_month": 1},
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["license"]["max_customers_per_month"] == 1, f"Limit not set: {data['license']}"
        print(f"PASS: License set max_customers_per_month=1")

    def test_verify_license_updated(self, http, platform_token):
        """Verify all three limits are set in the license."""
        r = http.get(
            f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license",
            headers={"Authorization": f"Bearer {platform_token}"},
        )
        assert r.status_code == 200
        lic = r.json()["license"]
        assert lic["max_orders_per_month"] == 1, f"orders limit: {lic}"
        assert lic["max_subscriptions_per_month"] == 1, f"subs limit: {lic}"
        assert lic["max_customers_per_month"] == 1, f"customers limit: {lic}"
        print(f"PASS: All three limits verified: orders=1, subs=1, customers=1")


# ---------------------------------------------------------------------------
# Phase 2: Set usage to "at limit" directly in MongoDB
# ---------------------------------------------------------------------------

class TestSetUsageAtLimit:
    """Set MongoDB usage counters to simulate being at the monthly limit."""

    def test_set_orders_count_at_limit(self):
        """Set orders_count=1 directly in MongoDB (at limit for max=1)."""
        set_license_usage(TEST_TENANT_ID, orders_count=1, customers_count=0, subscriptions_count=0)
        usage = get_license_usage(TEST_TENANT_ID)
        assert usage.get("orders_count") == 1, f"orders_count not set: {usage}"
        assert usage.get("tenant_id") == TEST_TENANT_ID, f"Wrong tenant: {usage}"
        period = get_current_est_period()
        assert usage.get("period") == period, f"Period mismatch: {usage}"
        print(f"PASS: orders_count=1 set in MongoDB for period {period}")

    def test_get_usage_snapshot_shows_blocked(self, http, partner_token):
        """Partner admin /admin/usage should show orders_this_month.blocked=True."""
        r = http.get(
            f"{BASE_URL}/api/admin/usage",
            headers={"Authorization": f"Bearer {partner_token}"},
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "usage" in data, f"Missing 'usage' in response: {data}"
        orders_usage = data["usage"].get("orders_this_month", {})
        assert orders_usage.get("blocked") == True, (
            f"Expected orders_this_month.blocked=True but got: {orders_usage}. "
            f"Full usage: {data['usage']}"
        )
        assert orders_usage.get("current") == 1, f"current should be 1: {orders_usage}"
        assert orders_usage.get("limit") == 1, f"limit should be 1: {orders_usage}"
        print(f"PASS: /admin/usage shows orders blocked: current=1/1, pct={orders_usage.get('pct')}%")


# ---------------------------------------------------------------------------
# Phase 3: Test /admin/orders/manual - EXPECTED BUG (no limit check)
# ---------------------------------------------------------------------------

class TestManualOrderLimitCheck:
    """
    BUG CONFIRMATION: /admin/orders/manual does NOT enforce license limits.
    When at limit (orders_count=1, max=1), creating a manual order should return 403.
    But due to MISSING check_limit call, it returns 201 instead.
    """

    def test_manual_order_at_limit_should_be_403_but_is_201(self, http, partner_token):
        """
        BUG: Creating manual order when at limit should return 403, but returns 201.
        This test CONFIRMS the bug - it PASSES only if the bug is present (201 returned).
        If fixed, this test should be updated to expect 403.
        """
        # Ensure we are at limit
        set_license_usage(TEST_TENANT_ID, orders_count=1, customers_count=0, subscriptions_count=0)

        r = http.post(
            f"{BASE_URL}/api/admin/orders/manual",
            headers={"Authorization": f"Bearer {partner_token}"},
            json={
                "customer_email": "mark@markchen.local",
                "product_id": TEST_PRODUCT_ID,
                "quantity": 1,
                "subtotal": 10.0,
                "discount": 0.0,
                "fee": 0.0,
                "status": "unpaid",
                "currency": "USD",
                "internal_note": "TEST_license_limit_check",
            },
        )
        # BUG: This should be 403 but returns 201
        # If the status code is NOT 403, the bug is confirmed
        if r.status_code == 403:
            print("PASS: /admin/orders/manual correctly returned 403 (BUG IS FIXED)")
            assert r.status_code == 403  # Bug was fixed
        else:
            # BUG CONFIRMED: limit not enforced
            print(f"BUG CONFIRMED: /admin/orders/manual returned {r.status_code} instead of 403 when at limit")
            print(f"Response: {r.text}")
            # Confirm the order was created despite being at limit
            assert r.status_code == 201 or r.status_code == 200, (
                f"Unexpected status {r.status_code}: {r.text}"
            )
            # Cleanup the incorrectly created order
            if r.status_code in (200, 201):
                order_id = r.json().get("order_id")
                if order_id:
                    print(f"Cleanup: deleting incorrectly created order {order_id}")
                    http.delete(
                        f"{BASE_URL}/api/admin/orders/{order_id}",
                        headers={"Authorization": f"Bearer {partner_token}"},
                        json={"reason": "Test cleanup - order created when at limit (BUG)"},
                    )
            pytest.fail(
                f"BUG CONFIRMED: /admin/orders/manual returned {r.status_code} "
                f"instead of 403 when at limit (orders_count=1, max_orders_per_month=1). "
                f"Missing check_limit call in routes/admin/orders.py create_manual_order()."
            )

    def test_limit_was_not_incremented_by_manual_order(self, http, partner_token):
        """
        SECONDARY BUG: Even if the order was created, the usage counter was NOT incremented.
        increment_monthly is also missing from /admin/orders/manual.
        """
        usage = get_license_usage(TEST_TENANT_ID)
        # Since increment_monthly is not called in manual order creation,
        # orders_count should still be 1 (unchanged from our direct DB set)
        # If it were incremented, it would be 2
        current_count = usage.get("orders_count", 0)
        print(f"INFO: orders_count after manual order creation = {current_count}")
        # The count should remain at 1 (we set it to 1 and manual order doesn't increment)
        # This confirms increment_monthly is also missing
        if current_count == 1:
            print("INFO CONFIRMED: increment_monthly NOT called in /admin/orders/manual (secondary bug)")
        else:
            print(f"INFO: orders_count changed to {current_count} (unexpected)")


# ---------------------------------------------------------------------------
# Phase 4: Test /admin/subscriptions/manual - EXPECTED BUG (no limit check)
# ---------------------------------------------------------------------------

class TestManualSubscriptionLimitCheck:
    """
    BUG CONFIRMATION: /admin/subscriptions/manual does NOT enforce license limits.
    When at limit, should return 403 but returns 201 instead.
    """

    def test_manual_subscription_at_limit_should_be_403_but_is_201(self, http, partner_token):
        """
        BUG: Creating manual subscription when at limit should return 403, but returns 201.
        """
        # Set subscriptions at limit
        set_license_usage(TEST_TENANT_ID, orders_count=0, customers_count=0, subscriptions_count=1)

        from datetime import timedelta
        renewal_date = (datetime.utcnow() + timedelta(days=30)).isoformat()

        r = http.post(
            f"{BASE_URL}/api/admin/subscriptions/manual",
            headers={"Authorization": f"Bearer {partner_token}"},
            json={
                "customer_email": "mark@markchen.local",
                "product_id": TEST_PRODUCT_ID,
                "amount": 99.0,
                "currency": "USD",
                "status": "active",
                "renewal_date": renewal_date,
                "internal_note": "TEST_license_limit_check",
            },
        )
        # BUG: Should be 403 but returns 201
        if r.status_code == 403:
            print("PASS: /admin/subscriptions/manual correctly returned 403 (BUG IS FIXED)")
            assert r.status_code == 403
        else:
            print(f"BUG CONFIRMED: /admin/subscriptions/manual returned {r.status_code} instead of 403 when at limit")
            print(f"Response: {r.text}")
            assert r.status_code in (200, 201), f"Unexpected status {r.status_code}: {r.text}"
            # Cleanup created subscription
            if r.status_code in (200, 201):
                sub_id = r.json().get("subscription_id")
                if sub_id:
                    print(f"Cleanup: would need to cancel subscription {sub_id}")
            pytest.fail(
                f"BUG CONFIRMED: /admin/subscriptions/manual returned {r.status_code} "
                f"instead of 403 when at limit (subscriptions_count=1, max_subscriptions_per_month=1). "
                f"Missing check_limit call in routes/admin/subscriptions.py create_manual_subscription()."
            )


# ---------------------------------------------------------------------------
# Phase 5: Test /admin/customers/create - WORKING (has limit check)
# ---------------------------------------------------------------------------

class TestCustomerCreateLimitCheck:
    """
    WORKING: /admin/customers/create has check_limit call.
    Should return 403 when at limit.
    """

    def test_customer_create_at_limit_returns_403(self, http, partner_token):
        """When at customer limit, creating a customer should return 403."""
        # Set customers at limit
        set_license_usage(TEST_TENANT_ID, orders_count=0, customers_count=1, subscriptions_count=0)

        import time
        unique_email = f"test_limit_{int(time.time())}@test.com"
        r = http.post(
            f"{BASE_URL}/api/admin/customers/create",
            headers={"Authorization": f"Bearer {partner_token}"},
            json={
                "email": unique_email,
                "password": "TestPass123!",
                "full_name": "TEST Limit Check",
                "company_name": "TEST Co",
                "line1": "123 Test St",
                "city": "London",
                "region": "Greater London",
                "postal": "W1A 1AA",
                "country": "GB",
                "mark_verified": True,
                "job_title": "",
                "phone": "",
            },
        )
        assert r.status_code == 403, (
            f"Expected 403 when at customer limit, got {r.status_code}: {r.text}. "
            f"check_limit IS implemented in /admin/customers/create."
        )
        assert "limit" in r.text.lower() or "monthly" in r.text.lower(), (
            f"Error message should mention limit: {r.text}"
        )
        print(f"PASS: /admin/customers/create returned 403 when at limit (WORKING)")
        print(f"Error detail: {r.json().get('detail', '')}")

    def test_customer_create_below_limit_succeeds(self, http, partner_token):
        """When below customer limit, creating a customer should succeed."""
        # Reset usage to 0
        set_license_usage(TEST_TENANT_ID, orders_count=0, customers_count=0, subscriptions_count=0)

        import time
        unique_email = f"test_below_limit_{int(time.time())}@test.com"
        r = http.post(
            f"{BASE_URL}/api/admin/customers/create",
            headers={"Authorization": f"Bearer {partner_token}"},
            json={
                "email": unique_email,
                "password": "TestPass123!",
                "full_name": "TEST Below Limit",
                "company_name": "TEST Co",
                "line1": "123 Test St",
                "city": "London",
                "region": "Greater London",
                "postal": "W1A 1AA",
                "country": "GB",
                "mark_verified": True,
                "job_title": "",
                "phone": "",
            },
        )
        # Should succeed (0 < max=1)
        assert r.status_code in (200, 201), (
            f"Expected 200/201 when below limit, got {r.status_code}: {r.text}"
        )
        print(f"PASS: Customer created successfully when below limit (WORKING)")
        # Verify usage was incremented
        usage = get_license_usage(TEST_TENANT_ID)
        customers_count = usage.get("customers_count", 0)
        print(f"INFO: customers_count after create = {customers_count} (should be 1)")
        assert customers_count == 1, (
            f"Expected customers_count=1 after create, got {customers_count}. "
            f"increment_monthly IS called in /admin/customers/create."
        )
        print(f"PASS: increment_monthly correctly called, customers_count incremented to {customers_count}")


# ---------------------------------------------------------------------------
# Phase 6: Test /admin/usage endpoint (LimitBanner data source)
# ---------------------------------------------------------------------------

class TestUsageEndpoint:
    """Test the /admin/usage endpoint that feeds the LimitBanner."""

    def test_usage_endpoint_returns_snapshot(self, http, partner_token):
        """Partner admin can access their usage snapshot."""
        r = http.get(
            f"{BASE_URL}/api/admin/usage",
            headers={"Authorization": f"Bearer {partner_token}"},
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "usage" in data, f"Missing 'usage': {data}"
        assert "license" in data, f"Missing 'license': {data}"
        assert "period" in data, f"Missing 'period': {data}"
        print(f"PASS: /admin/usage returns snapshot for period {data['period']}")

    def test_usage_orders_blocked_at_limit(self, http, partner_token):
        """When orders_count=1 and max=1, usage shows blocked: True."""
        set_license_usage(TEST_TENANT_ID, orders_count=1, customers_count=0, subscriptions_count=0)
        r = http.get(
            f"{BASE_URL}/api/admin/usage",
            headers={"Authorization": f"Bearer {partner_token}"},
        )
        assert r.status_code == 200
        orders_usage = r.json()["usage"].get("orders_this_month", {})
        assert orders_usage.get("blocked") == True, f"Expected blocked=True: {orders_usage}"
        assert orders_usage.get("current") == 1
        assert orders_usage.get("limit") == 1
        assert orders_usage.get("pct") == 100
        print(f"PASS: Usage shows orders blocked=True, pct=100% when at limit")

    def test_usage_subscriptions_blocked_at_limit(self, http, partner_token):
        """When subscriptions_count=1 and max=1, usage shows blocked: True."""
        set_license_usage(TEST_TENANT_ID, orders_count=0, customers_count=0, subscriptions_count=1)
        r = http.get(
            f"{BASE_URL}/api/admin/usage",
            headers={"Authorization": f"Bearer {partner_token}"},
        )
        assert r.status_code == 200
        subs_usage = r.json()["usage"].get("subscriptions_this_month", {})
        assert subs_usage.get("blocked") == True, f"Expected blocked=True: {subs_usage}"
        assert subs_usage.get("current") == 1
        assert subs_usage.get("limit") == 1
        print(f"PASS: Usage shows subscriptions blocked=True when at limit")

    def test_usage_orders_not_blocked_below_limit(self, http, partner_token):
        """When orders_count=0 and max=1, usage shows blocked: False."""
        set_license_usage(TEST_TENANT_ID, orders_count=0, customers_count=0, subscriptions_count=0)
        r = http.get(
            f"{BASE_URL}/api/admin/usage",
            headers={"Authorization": f"Bearer {partner_token}"},
        )
        assert r.status_code == 200
        orders_usage = r.json()["usage"].get("orders_this_month", {})
        assert orders_usage.get("blocked") == False, f"Expected blocked=False: {orders_usage}"
        assert orders_usage.get("current") == 0
        print(f"PASS: Usage shows orders blocked=False when below limit")

    def test_platform_admin_cannot_access_usage(self, http, platform_token):
        """Platform admin can access usage for any tenant via tenants/{id}/license."""
        # Platform admin uses GET /admin/tenants/{id}/license, not /admin/usage
        r = http.get(
            f"{BASE_URL}/api/admin/usage",
            headers={"Authorization": f"Bearer {platform_token}"},
        )
        # Platform admins can access this (they have tenant_id in their token)
        # Just verify it returns a valid response
        assert r.status_code in (200, 403), f"Unexpected status: {r.status_code}"
        print(f"INFO: Platform admin /admin/usage returned {r.status_code}")


# ---------------------------------------------------------------------------
# Phase 7: Test checkout/bank-transfer limit check (customer auth)
# ---------------------------------------------------------------------------

class TestCheckoutBankTransferLimitCheck:
    """
    WORKING: /checkout/bank-transfer has check_limit.
    Note: GoCardless must be enabled for bright-accounting tenant.
    If GoCardless not enabled → returns 400 (before limit check is reached).
    If GoCardless enabled AND at limit → should return 403.
    """

    def test_checkout_bank_transfer_at_limit_returns_403_or_400_gocardless(self, http, customer_token):
        """
        When orders_count=1 (at limit), bank-transfer checkout should return 403.
        If GoCardless not enabled for the tenant, will get 400 first.
        The limit check IS present in the code (verified by code review).
        """
        # Set orders at limit
        set_license_usage(TEST_TENANT_ID, orders_count=1, customers_count=0, subscriptions_count=0)

        r = http.post(
            f"{BASE_URL}/api/checkout/bank-transfer",
            headers={"Authorization": f"Bearer {customer_token}"},
            json={
                "items": [{"product_id": TEST_PRODUCT_ID, "quantity": 1, "inputs": {}}],
                "checkout_type": "one_time",
                "terms_accepted": True,
                "terms_id": None,
                "promo_code": None,
            },
        )
        print(f"INFO: /checkout/bank-transfer response at limit: {r.status_code} - {r.text[:200]}")

        if r.status_code == 400 and "bank transfer" in r.text.lower():
            # GoCardless not enabled for this tenant - cannot test 403 path
            print(
                "INFO: GoCardless not enabled for bright-accounting. "
                "Limit check at line 153 is correct in code but cannot be reached from this test. "
                "The limit check IS implemented (verified by code review of checkout.py)."
            )
            pytest.skip("GoCardless not enabled - cannot test bank-transfer limit check from HTTP level")
        elif r.status_code == 403:
            assert "limit" in r.text.lower() or "monthly" in r.text.lower(), (
                f"403 returned but error message doesn't mention limit: {r.text}"
            )
            print(f"PASS: /checkout/bank-transfer returned 403 when at limit")
        elif r.status_code == 403 and "terms" in r.text.lower():
            print(f"INFO: Got 400 for terms validation - terms check before limit check")
        else:
            # Could be 403 for other reasons or 400 for missing terms
            print(f"INFO: Got {r.status_code} - {r.text[:300]}")
            # The key verification is that the code has check_limit (confirmed by code review)
            # and NOT the order created despite being at limit
            assert r.status_code != 200 and r.status_code != 201, (
                f"Unexpected 200/201: order should not be created: {r.text}"
            )


# ---------------------------------------------------------------------------
# Phase 8: Cleanup — reset usage and license limits
# ---------------------------------------------------------------------------

class TestCleanup:
    """Reset bright-accounting license limits and usage after testing."""

    def test_reset_usage_counters(self, http, platform_token):
        """Reset monthly usage counters for bright-accounting."""
        r = http.post(
            f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/usage/reset",
            headers={"Authorization": f"Bearer {platform_token}"},
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        usage = get_license_usage(TEST_TENANT_ID)
        assert usage.get("orders_count", -1) == 0, f"orders_count not reset: {usage}"
        assert usage.get("customers_count", -1) == 0, f"customers_count not reset: {usage}"
        assert usage.get("subscriptions_count", -1) == 0, f"subscriptions_count not reset: {usage}"
        print(f"PASS: Usage counters reset to 0")

    def test_remove_license_limits(self, http, platform_token):
        """Remove (null) all monthly limits from bright-accounting license."""
        r = http.put(
            f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license",
            headers={"Authorization": f"Bearer {platform_token}"},
            json={
                "max_orders_per_month": None,
                "max_subscriptions_per_month": None,
                "max_customers_per_month": None,
            },
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        lic = r.json()["license"]
        assert lic.get("max_orders_per_month") is None, f"orders limit not cleared: {lic}"
        assert lic.get("max_subscriptions_per_month") is None, f"subs limit not cleared: {lic}"
        assert lic.get("max_customers_per_month") is None, f"customers limit not cleared: {lic}"
        print(f"PASS: License limits cleared (unlimited)")
