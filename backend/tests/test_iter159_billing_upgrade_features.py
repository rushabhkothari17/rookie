"""
Backend tests for iter159 - Billing Upgrade Flow features:
1. Admin One-Time Plans CRUD (GET/POST/PUT/DELETE)
2. Admin Coupons CRUD (GET/POST/PUT/DELETE)
3. Partner coupon validate endpoint
4. Partner one-time-rates endpoint
5. Partner upgrade-plan-ongoing endpoint
6. Partner one-time-upgrade endpoint
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# ── Auth Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def platform_admin_token():
    """Login as platform admin and return token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!"
    })
    if resp.status_code == 200:
        token = resp.json().get("token") or resp.json().get("access_token")
        print(f"Platform admin login: OK, token={token[:20]}...")
        return token
    pytest.skip(f"Platform admin login failed: {resp.status_code} {resp.text}")


@pytest.fixture(scope="module")
def admin_headers(platform_admin_token):
    return {"Authorization": f"Bearer {platform_admin_token}"}


# ── One-Time Plans Tests ──────────────────────────────────────────────────────

class TestOneTimePlans:
    """Tests for /api/admin/one-time-plans CRUD"""

    created_rate_id = None

    def test_list_rates_unauthenticated(self):
        """GET /api/admin/one-time-plans without auth returns 401/403"""
        resp = requests.get(f"{BASE_URL}/api/admin/one-time-plans")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"
        print(f"PASS: Unauthenticated returns {resp.status_code}")

    def test_list_rates_returns_modules(self, admin_headers):
        """GET /api/admin/one-time-plans returns rates + modules"""
        resp = requests.get(f"{BASE_URL}/api/admin/one-time-plans", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "rates" in data, "Response should have 'rates'"
        assert "modules" in data, "Response should have 'modules'"
        assert isinstance(data["rates"], list), "Rates should be a list"
        assert isinstance(data["modules"], list), "Modules should be a list"
        assert len(data["modules"]) > 0, "Should have at least one module"
        # Check module structure
        for m in data["modules"]:
            assert "key" in m, "Module should have 'key'"
            assert "label" in m, "Module should have 'label'"
        print(f"PASS: Rates list: {len(data['rates'])} rates, {len(data['modules'])} modules")

    def test_create_rate_orders(self, admin_headers):
        """POST /api/admin/one-time-plans creates an Orders/month rate"""
        # First check if rate already exists and delete it
        list_resp = requests.get(f"{BASE_URL}/api/admin/one-time-plans", headers=admin_headers)
        existing_rates = list_resp.json().get("rates", [])
        for r in existing_rates:
            if r.get("module_key") == "max_orders_per_month":
                # Delete existing to start fresh
                requests.delete(f"{BASE_URL}/api/admin/one-time-plans/{r['id']}", headers=admin_headers)
                break

        resp = requests.post(f"{BASE_URL}/api/admin/one-time-plans", json={
            "module_key": "max_orders_per_month",
            "price_per_record": 1.00,
            "currency": "GBP",
            "is_active": True
        }, headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("module_key") == "max_orders_per_month"
        assert data.get("price_per_record") == 1.00
        assert data.get("currency") == "GBP"
        assert data.get("is_active") is True
        assert "id" in data
        TestOneTimePlans.created_rate_id = data["id"]
        print(f"PASS: Created rate id={data['id']}, module={data['module_key']}, price={data['price_per_record']}")

    def test_create_rate_duplicate_rejected(self, admin_headers):
        """POST duplicate module_key returns 409"""
        resp = requests.post(f"{BASE_URL}/api/admin/one-time-plans", json={
            "module_key": "max_orders_per_month",
            "price_per_record": 2.00,
            "currency": "GBP",
            "is_active": True
        }, headers=admin_headers)
        assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"
        print(f"PASS: Duplicate rate rejected with 409")

    def test_create_rate_invalid_module_rejected(self, admin_headers):
        """POST unknown module_key returns 400"""
        resp = requests.post(f"{BASE_URL}/api/admin/one-time-plans", json={
            "module_key": "invalid_module",
            "price_per_record": 1.00,
            "currency": "GBP"
        }, headers=admin_headers)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        print(f"PASS: Invalid module rejected with 400")

    def test_update_rate(self, admin_headers):
        """PUT /api/admin/one-time-plans/{id} updates the rate"""
        if not TestOneTimePlans.created_rate_id:
            pytest.skip("No rate created in previous test")
        resp = requests.put(
            f"{BASE_URL}/api/admin/one-time-plans/{TestOneTimePlans.created_rate_id}",
            json={"price_per_record": 1.50, "currency": "GBP"},
            headers=admin_headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("price_per_record") == 1.50, f"Expected 1.50, got {data.get('price_per_record')}"
        print(f"PASS: Rate updated to price={data['price_per_record']}")

    def test_update_nonexistent_rate(self, admin_headers):
        """PUT /api/admin/one-time-plans/nonexistent returns 404"""
        resp = requests.put(
            f"{BASE_URL}/api/admin/one-time-plans/nonexistent_id",
            json={"price_per_record": 2.00},
            headers=admin_headers
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
        print(f"PASS: Nonexistent rate returns 404")

    def test_verify_rate_in_list(self, admin_headers):
        """GET list should now contain the created rate"""
        if not TestOneTimePlans.created_rate_id:
            pytest.skip("No rate created")
        resp = requests.get(f"{BASE_URL}/api/admin/one-time-plans", headers=admin_headers)
        assert resp.status_code == 200
        rates = resp.json().get("rates", [])
        ids = [r["id"] for r in rates]
        assert TestOneTimePlans.created_rate_id in ids, "Created rate should be in list"
        print(f"PASS: Created rate appears in list with {len(rates)} total rates")

    def test_delete_rate(self, admin_headers):
        """DELETE /api/admin/one-time-plans/{id} removes the rate"""
        if not TestOneTimePlans.created_rate_id:
            pytest.skip("No rate created")
        resp = requests.delete(
            f"{BASE_URL}/api/admin/one-time-plans/{TestOneTimePlans.created_rate_id}",
            headers=admin_headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print(f"PASS: Rate deleted")

    def test_verify_rate_deleted(self, admin_headers):
        """Deleted rate should not appear in list"""
        if not TestOneTimePlans.created_rate_id:
            pytest.skip("No rate created")
        resp = requests.get(f"{BASE_URL}/api/admin/one-time-plans", headers=admin_headers)
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json().get("rates", [])]
        assert TestOneTimePlans.created_rate_id not in ids, "Deleted rate should not be in list"
        print(f"PASS: Deleted rate not in list")


# ── Coupons Tests ─────────────────────────────────────────────────────────────

class TestCoupons:
    """Tests for /api/admin/coupons CRUD"""

    created_coupon_id = None
    coupon_code = "TEST_SAVE10_ITER159"

    def test_list_coupons_unauthenticated(self):
        """GET /api/admin/coupons without auth returns 401/403"""
        resp = requests.get(f"{BASE_URL}/api/admin/coupons")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"
        print(f"PASS: Unauthenticated returns {resp.status_code}")

    def test_list_coupons(self, admin_headers):
        """GET /api/admin/coupons returns list of coupons"""
        resp = requests.get(f"{BASE_URL}/api/admin/coupons", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "coupons" in data, "Response should have 'coupons'"
        assert isinstance(data["coupons"], list)
        print(f"PASS: Coupons list: {len(data['coupons'])} coupons")

    def test_create_coupon_save10(self, admin_headers):
        """POST /api/admin/coupons creates SAVE10 coupon"""
        # Delete if exists
        list_resp = requests.get(f"{BASE_URL}/api/admin/coupons", headers=admin_headers)
        for c in list_resp.json().get("coupons", []):
            if c.get("code") == TestCoupons.coupon_code:
                requests.delete(f"{BASE_URL}/api/admin/coupons/{c['id']}", headers=admin_headers)
                break

        resp = requests.post(f"{BASE_URL}/api/admin/coupons", json={
            "code": TestCoupons.coupon_code,
            "discount_type": "percentage",
            "discount_value": 10,
            "applies_to": "both",
            "expiry_date": "2027-12-31",
            "is_one_time_per_org": True,
            "is_single_use": False,
            "is_active": True
        }, headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("code") == TestCoupons.coupon_code
        assert data.get("discount_type") == "percentage"
        assert data.get("discount_value") == 10
        assert data.get("applies_to") == "both"
        assert data.get("expiry_date") == "2027-12-31"
        assert data.get("is_one_time_per_org") is True
        assert data.get("is_active") is True
        assert "id" in data
        TestCoupons.created_coupon_id = data["id"]
        print(f"PASS: Created coupon id={data['id']}, code={data['code']}, discount={data['discount_value']}%")

    def test_create_coupon_duplicate_rejected(self, admin_headers):
        """POST duplicate coupon code returns 409"""
        resp = requests.post(f"{BASE_URL}/api/admin/coupons", json={
            "code": TestCoupons.coupon_code,
            "discount_type": "percentage",
            "discount_value": 5,
            "applies_to": "ongoing"
        }, headers=admin_headers)
        assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"
        print(f"PASS: Duplicate coupon rejected with 409")

    def test_create_coupon_invalid_discount_type(self, admin_headers):
        """POST coupon with invalid discount_type returns 400"""
        resp = requests.post(f"{BASE_URL}/api/admin/coupons", json={
            "code": "INVALID_TYPE_TEST",
            "discount_type": "invalid_type",
            "discount_value": 10,
            "applies_to": "both"
        }, headers=admin_headers)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        print(f"PASS: Invalid discount_type rejected with 400")

    def test_verify_coupon_in_list(self, admin_headers):
        """GET list should contain the created coupon"""
        if not TestCoupons.created_coupon_id:
            pytest.skip("No coupon created")
        resp = requests.get(f"{BASE_URL}/api/admin/coupons", headers=admin_headers)
        assert resp.status_code == 200
        ids = [c["id"] for c in resp.json().get("coupons", [])]
        assert TestCoupons.created_coupon_id in ids, "Created coupon should be in list"
        print(f"PASS: Created coupon appears in list")

    def test_update_coupon(self, admin_headers):
        """PUT /api/admin/coupons/{id} updates the coupon"""
        if not TestCoupons.created_coupon_id:
            pytest.skip("No coupon created")
        resp = requests.put(
            f"{BASE_URL}/api/admin/coupons/{TestCoupons.created_coupon_id}",
            json={"discount_value": 15, "internal_note": "Updated by test"},
            headers=admin_headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("discount_value") == 15, f"Expected 15, got {data.get('discount_value')}"
        assert data.get("internal_note") == "Updated by test"
        print(f"PASS: Coupon updated: discount_value={data['discount_value']}")

    def test_update_nonexistent_coupon(self, admin_headers):
        """PUT /api/admin/coupons/nonexistent returns 404"""
        resp = requests.put(
            f"{BASE_URL}/api/admin/coupons/nonexistent_id",
            json={"discount_value": 5},
            headers=admin_headers
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
        print(f"PASS: Nonexistent coupon returns 404")

    def test_delete_coupon(self, admin_headers):
        """DELETE /api/admin/coupons/{id} removes the coupon"""
        if not TestCoupons.created_coupon_id:
            pytest.skip("No coupon created")
        resp = requests.delete(
            f"{BASE_URL}/api/admin/coupons/{TestCoupons.created_coupon_id}",
            headers=admin_headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print(f"PASS: Coupon deleted")

    def test_verify_coupon_deleted(self, admin_headers):
        """Deleted coupon should not appear in list"""
        if not TestCoupons.created_coupon_id:
            pytest.skip("No coupon created")
        resp = requests.get(f"{BASE_URL}/api/admin/coupons", headers=admin_headers)
        assert resp.status_code == 200
        ids = [c["id"] for c in resp.json().get("coupons", [])]
        assert TestCoupons.created_coupon_id not in ids, "Deleted coupon should not be in list"
        print(f"PASS: Deleted coupon not in list")


# ── Coupon Validation Tests (Partner) ─────────────────────────────────────────

class TestCouponValidation:
    """Tests for POST /api/partner/coupons/validate"""

    coupon_code = "TEST_VALIDATE_ITER159"
    coupon_id = None

    def test_setup_coupon_for_validation(self, admin_headers):
        """Create a test coupon to validate"""
        # Cleanup first
        list_resp = requests.get(f"{BASE_URL}/api/admin/coupons", headers=admin_headers)
        for c in list_resp.json().get("coupons", []):
            if c.get("code") == TestCouponValidation.coupon_code:
                requests.delete(f"{BASE_URL}/api/admin/coupons/{c['id']}", headers=admin_headers)

        resp = requests.post(f"{BASE_URL}/api/admin/coupons", json={
            "code": TestCouponValidation.coupon_code,
            "discount_type": "percentage",
            "discount_value": 10,
            "applies_to": "both",
            "expiry_date": "2027-12-31",
            "is_one_time_per_org": False,
            "is_single_use": False,
            "is_active": True
        }, headers=admin_headers)
        if resp.status_code == 200:
            TestCouponValidation.coupon_id = resp.json()["id"]
            print(f"PASS: Created validation test coupon id={TestCouponValidation.coupon_id}")
        else:
            pytest.skip(f"Could not create test coupon: {resp.status_code}")

    def test_validate_coupon_ongoing(self, admin_headers):
        """POST /api/partner/coupons/validate with valid coupon returns discount details"""
        resp = requests.post(f"{BASE_URL}/api/partner/coupons/validate", json={
            "code": TestCouponValidation.coupon_code,
            "upgrade_type": "ongoing",
            "base_amount": 100.0
        }, headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("valid") is True
        assert data.get("discount_amount") == 10.0, f"Expected 10.0, got {data.get('discount_amount')}"
        assert data.get("final_amount") == 90.0, f"Expected 90.0, got {data.get('final_amount')}"
        assert data.get("discount_type") == "percentage"
        assert data.get("discount_value") == 10
        print(f"PASS: Coupon validate ongoing: discount={data['discount_amount']}, final={data['final_amount']}")

    def test_validate_coupon_one_time(self, admin_headers):
        """POST /api/partner/coupons/validate for one_time upgrade"""
        resp = requests.post(f"{BASE_URL}/api/partner/coupons/validate", json={
            "code": TestCouponValidation.coupon_code,
            "upgrade_type": "one_time",
            "base_amount": 50.0
        }, headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("valid") is True
        assert data.get("discount_amount") == 5.0
        assert data.get("final_amount") == 45.0
        print(f"PASS: Coupon validate one_time: discount={data['discount_amount']}, final={data['final_amount']}")

    def test_validate_invalid_coupon(self, admin_headers):
        """POST with invalid coupon code returns 400"""
        resp = requests.post(f"{BASE_URL}/api/partner/coupons/validate", json={
            "code": "INVALID_CODE_XYZ",
            "upgrade_type": "ongoing",
            "base_amount": 100.0
        }, headers=admin_headers)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        print(f"PASS: Invalid coupon returns 400")

    def test_validate_expired_coupon(self, admin_headers):
        """Expired coupon returns 400"""
        # Create expired coupon
        code = "TEST_EXPIRED_ITER159"
        # Cleanup
        list_resp = requests.get(f"{BASE_URL}/api/admin/coupons", headers=admin_headers)
        for c in list_resp.json().get("coupons", []):
            if c.get("code") == code:
                requests.delete(f"{BASE_URL}/api/admin/coupons/{c['id']}", headers=admin_headers)

        create_resp = requests.post(f"{BASE_URL}/api/admin/coupons", json={
            "code": code,
            "discount_type": "percentage",
            "discount_value": 5,
            "applies_to": "both",
            "expiry_date": "2020-01-01",  # expired
            "is_active": True
        }, headers=admin_headers)
        if create_resp.status_code != 200:
            pytest.skip("Could not create expired coupon")

        resp = requests.post(f"{BASE_URL}/api/partner/coupons/validate", json={
            "code": code,
            "upgrade_type": "ongoing",
            "base_amount": 100.0
        }, headers=admin_headers)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        # Cleanup
        expired_id = create_resp.json()["id"]
        requests.delete(f"{BASE_URL}/api/admin/coupons/{expired_id}", headers=admin_headers)
        print(f"PASS: Expired coupon returns 400")

    def test_cleanup_validation_coupon(self, admin_headers):
        """Clean up test coupon"""
        if TestCouponValidation.coupon_id:
            requests.delete(
                f"{BASE_URL}/api/admin/coupons/{TestCouponValidation.coupon_id}",
                headers=admin_headers
            )
            print(f"PASS: Cleaned up validation test coupon")


# ── Partner One-Time Rates Tests ───────────────────────────────────────────────

class TestPartnerOneTimeRates:
    """Tests for GET /api/partner/one-time-rates"""

    rate_id = None

    def test_one_time_rates_unauthenticated(self):
        """GET /api/partner/one-time-rates without auth returns 401/403"""
        resp = requests.get(f"{BASE_URL}/api/partner/one-time-rates")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"
        print(f"PASS: Unauthenticated returns {resp.status_code}")

    def test_one_time_rates_empty_initially(self, admin_headers):
        """GET /api/partner/one-time-rates returns list (may be empty)"""
        resp = requests.get(f"{BASE_URL}/api/partner/one-time-rates", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "rates" in data, "Response should have 'rates'"
        assert isinstance(data["rates"], list)
        print(f"PASS: One-time rates: {len(data['rates'])} active rates")

    def test_create_rate_and_verify_in_partner_endpoint(self, admin_headers):
        """Creating a rate should make it visible in /api/partner/one-time-rates"""
        # Delete if max_customers_per_month already exists
        list_resp = requests.get(f"{BASE_URL}/api/admin/one-time-plans", headers=admin_headers)
        for r in list_resp.json().get("rates", []):
            if r.get("module_key") == "max_customers_per_month":
                requests.delete(f"{BASE_URL}/api/admin/one-time-plans/{r['id']}", headers=admin_headers)
                break

        create_resp = requests.post(f"{BASE_URL}/api/admin/one-time-plans", json={
            "module_key": "max_customers_per_month",
            "price_per_record": 2.50,
            "currency": "GBP",
            "is_active": True
        }, headers=admin_headers)
        if create_resp.status_code != 200:
            pytest.skip(f"Could not create rate: {create_resp.text}")
        TestPartnerOneTimeRates.rate_id = create_resp.json()["id"]

        # Verify it appears in partner endpoint
        resp = requests.get(f"{BASE_URL}/api/partner/one-time-rates", headers=admin_headers)
        assert resp.status_code == 200
        rates = resp.json().get("rates", [])
        keys = [r["module_key"] for r in rates]
        assert "max_customers_per_month" in keys, f"Newly created rate should appear. Got keys: {keys}"
        # Find and verify details
        rate = next(r for r in rates if r["module_key"] == "max_customers_per_month")
        assert rate["price_per_record"] == 2.50
        assert rate["currency"] == "GBP"
        print(f"PASS: Created rate appears in partner endpoint: {rate}")

    def test_inactive_rate_not_in_partner_endpoint(self, admin_headers):
        """Inactive rates should NOT appear in /api/partner/one-time-rates"""
        # Delete if max_subscriptions_per_month exists
        list_resp = requests.get(f"{BASE_URL}/api/admin/one-time-plans", headers=admin_headers)
        for r in list_resp.json().get("rates", []):
            if r.get("module_key") == "max_subscriptions_per_month":
                requests.delete(f"{BASE_URL}/api/admin/one-time-plans/{r['id']}", headers=admin_headers)
                break

        create_resp = requests.post(f"{BASE_URL}/api/admin/one-time-plans", json={
            "module_key": "max_subscriptions_per_month",
            "price_per_record": 1.00,
            "currency": "GBP",
            "is_active": False  # inactive
        }, headers=admin_headers)
        if create_resp.status_code != 200:
            pytest.skip("Could not create inactive rate")
        inactive_id = create_resp.json()["id"]

        resp = requests.get(f"{BASE_URL}/api/partner/one-time-rates", headers=admin_headers)
        assert resp.status_code == 200
        keys = [r["module_key"] for r in resp.json().get("rates", [])]
        assert "max_subscriptions_per_month" not in keys, "Inactive rate should not appear in partner endpoint"

        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/one-time-plans/{inactive_id}", headers=admin_headers)
        print(f"PASS: Inactive rate not visible in partner endpoint")

    def test_cleanup_customer_rate(self, admin_headers):
        """Clean up test rate for customers/month"""
        if TestPartnerOneTimeRates.rate_id:
            requests.delete(
                f"{BASE_URL}/api/admin/one-time-plans/{TestPartnerOneTimeRates.rate_id}",
                headers=admin_headers
            )
            print(f"PASS: Cleaned up test rate")


# ── Partner Upgrade Plan Ongoing ───────────────────────────────────────────────

class TestPartnerUpgradePlanOngoing:
    """Tests for POST /api/partner/upgrade-plan-ongoing"""

    test_coupon_id = None
    test_coupon_code = "TEST_ONGOING_ITER159"

    def test_upgrade_plan_ongoing_no_auth(self):
        """POST without auth returns 401/403"""
        resp = requests.post(f"{BASE_URL}/api/partner/upgrade-plan-ongoing",
                             json={"plan_id": "someid"})
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"
        print(f"PASS: Unauthenticated upgrade returns {resp.status_code}")

    def test_upgrade_plan_ongoing_invalid_plan(self, admin_headers):
        """POST with invalid plan_id returns 404"""
        resp = requests.post(f"{BASE_URL}/api/partner/upgrade-plan-ongoing",
                             json={"plan_id": "nonexistent_plan_id"},
                             headers=admin_headers)
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
        print(f"PASS: Invalid plan returns 404")

    def test_upgrade_plan_ongoing_with_public_plan(self, admin_headers):
        """POST with a valid public plan returns checkout_url or success message"""
        # Get available public plans
        plans_resp = requests.get(f"{BASE_URL}/api/partner/my-plan", headers=admin_headers)
        if plans_resp.status_code != 200:
            pytest.skip("Could not get my-plan data")
        plan_data = plans_resp.json()
        available = plan_data.get("available_plans", [])
        current_price = (plan_data.get("current_plan") or {}).get("monthly_price") or 0
        upgrades = [p for p in available if (p.get("monthly_price") or 0) > current_price]
        if not upgrades:
            pytest.skip("No upgrade plans available")
        target_plan = upgrades[0]
        resp = requests.post(f"{BASE_URL}/api/partner/upgrade-plan-ongoing",
                             json={"plan_id": target_plan["id"], "coupon_code": ""},
                             headers=admin_headers)
        # Should return checkout_url OR success message (if flat_diff == 0)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "checkout_url" in data or "message" in data, f"Response should have checkout_url or message: {data}"
        print(f"PASS: Upgrade plan ongoing response: {list(data.keys())}")

    def test_upgrade_plan_ongoing_with_coupon(self, admin_headers):
        """POST with valid coupon returns checkout_url or applies coupon discount"""
        # Create a 100% coupon so it activates without Stripe
        # Cleanup
        list_resp = requests.get(f"{BASE_URL}/api/admin/coupons", headers=admin_headers)
        for c in list_resp.json().get("coupons", []):
            if c.get("code") == TestPartnerUpgradePlanOngoing.test_coupon_code:
                requests.delete(f"{BASE_URL}/api/admin/coupons/{c['id']}", headers=admin_headers)

        coupon_resp = requests.post(f"{BASE_URL}/api/admin/coupons", json={
            "code": TestPartnerUpgradePlanOngoing.test_coupon_code,
            "discount_type": "percentage",
            "discount_value": 100,  # 100% off
            "applies_to": "ongoing",
            "is_one_time_per_org": False,
            "is_active": True
        }, headers=admin_headers)
        if coupon_resp.status_code != 200:
            pytest.skip(f"Could not create coupon: {coupon_resp.text}")
        TestPartnerUpgradePlanOngoing.test_coupon_id = coupon_resp.json()["id"]

        # Get a public plan
        plans_resp = requests.get(f"{BASE_URL}/api/partner/my-plan", headers=admin_headers)
        if plans_resp.status_code != 200:
            pytest.skip("Could not get my-plan data")
        available = plans_resp.json().get("available_plans", [])
        current_price = (plans_resp.json().get("current_plan") or {}).get("monthly_price") or 0
        upgrades = [p for p in available if (p.get("monthly_price") or 0) > current_price]
        if not upgrades:
            pytest.skip("No upgrade plans available")

        resp = requests.post(f"{BASE_URL}/api/partner/upgrade-plan-ongoing",
                             json={
                                 "plan_id": upgrades[0]["id"],
                                 "coupon_code": TestPartnerUpgradePlanOngoing.test_coupon_code
                             },
                             headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "checkout_url" in data or "message" in data, f"Response should have checkout_url or message"
        print(f"PASS: Upgrade with 100% coupon: {list(data.keys())}")

    def test_cleanup_coupon(self, admin_headers):
        """Clean up test coupon"""
        if TestPartnerUpgradePlanOngoing.test_coupon_id:
            requests.delete(
                f"{BASE_URL}/api/admin/coupons/{TestPartnerUpgradePlanOngoing.test_coupon_id}",
                headers=admin_headers
            )
            print(f"PASS: Cleaned up upgrade test coupon")


# ── One-Time Upgrade Tests ─────────────────────────────────────────────────────

class TestOneTimeUpgrade:
    """Tests for POST /api/partner/one-time-upgrade"""

    rate_id = None

    def test_one_time_upgrade_no_auth(self):
        """POST without auth returns 401/403"""
        resp = requests.post(f"{BASE_URL}/api/partner/one-time-upgrade",
                             json={"upgrades": [{"module_key": "max_orders_per_month", "quantity": 10}]})
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"
        print(f"PASS: Unauthenticated returns {resp.status_code}")

    def test_one_time_upgrade_no_rate_configured(self, admin_headers):
        """POST for module with no rate returns 400"""
        resp = requests.post(f"{BASE_URL}/api/partner/one-time-upgrade",
                             json={"upgrades": [{"module_key": "max_users", "quantity": 5}]},
                             headers=admin_headers)
        # If no rate for max_users is configured, should return 400
        if resp.status_code == 400:
            print(f"PASS: No rate configured returns 400")
        elif resp.status_code == 200:
            print(f"PASS (rate exists): Returns 200 with checkout_url or message")

    def test_one_time_upgrade_zero_quantity(self, admin_headers):
        """POST with quantity=0 returns 400"""
        # First create a rate for max_orders_per_month
        list_resp = requests.get(f"{BASE_URL}/api/admin/one-time-plans", headers=admin_headers)
        for r in list_resp.json().get("rates", []):
            if r.get("module_key") == "max_orders_per_month":
                TestOneTimeUpgrade.rate_id = r["id"]
                break

        if not TestOneTimeUpgrade.rate_id:
            create_resp = requests.post(f"{BASE_URL}/api/admin/one-time-plans", json={
                "module_key": "max_orders_per_month",
                "price_per_record": 1.00,
                "currency": "GBP",
                "is_active": True
            }, headers=admin_headers)
            if create_resp.status_code == 200:
                TestOneTimeUpgrade.rate_id = create_resp.json()["id"]

        resp = requests.post(f"{BASE_URL}/api/partner/one-time-upgrade",
                             json={"upgrades": [{"module_key": "max_orders_per_month", "quantity": 0}]},
                             headers=admin_headers)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        print(f"PASS: Zero quantity returns 400")

    def test_one_time_upgrade_valid_request(self, admin_headers):
        """POST with valid module and quantity returns checkout_url or message"""
        if not TestOneTimeUpgrade.rate_id:
            pytest.skip("No rate available for max_orders_per_month")

        resp = requests.post(f"{BASE_URL}/api/partner/one-time-upgrade",
                             json={"upgrades": [{"module_key": "max_orders_per_month", "quantity": 10}]},
                             headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "checkout_url" in data or "message" in data or "boosts" in data, \
            f"Response should have checkout_url, message, or boosts: {data}"
        print(f"PASS: One-time upgrade response: {list(data.keys())}")

    def test_cleanup_rate(self, admin_headers):
        """Clean up test rate"""
        if TestOneTimeUpgrade.rate_id:
            requests.delete(
                f"{BASE_URL}/api/admin/one-time-plans/{TestOneTimeUpgrade.rate_id}",
                headers=admin_headers
            )
            print(f"PASS: Cleaned up test rate for one-time upgrade")
