"""
Iteration 132 tests: Province/State endpoint, Cart payment UI, Renewal History, Regression
Tests:
- GET /api/utils/provinces?country_code=Canada (13 provinces)
- GET /api/utils/provinces?country_code=USA (51 states)
- GET /api/utils/provinces?country_code=UK (empty regions)
- GET /api/utils/provinces?country_code=CA (ISO code alias)
- GET /api/utils/provinces?country_code=US (ISO code alias)
- Admin login regression
- Customer login regression
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestProvincesEndpoint:
    """Province/state endpoint tests — public, no auth required"""

    def test_canada_full_name_returns_13_provinces(self):
        """Canada by full name returns exactly 13 provinces"""
        r = requests.get(f"{BASE_URL}/api/utils/provinces", params={"country_code": "Canada"})
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "regions" in data, "Response must have 'regions' key"
        assert len(data["regions"]) == 13, f"Expected 13 provinces, got {len(data['regions'])}"
        # Check a few known provinces
        values = {p["value"] for p in data["regions"]}
        assert "ON" in values, "Ontario (ON) must be present"
        assert "BC" in values, "British Columbia (BC) must be present"
        assert "QC" in values, "Quebec (QC) must be present"

    def test_canada_iso_code_ca_returns_13_provinces(self):
        """Canada by ISO code CA returns exactly 13 provinces"""
        r = requests.get(f"{BASE_URL}/api/utils/provinces", params={"country_code": "CA"})
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert len(data["regions"]) == 13, f"Expected 13 provinces, got {len(data['regions'])}"

    def test_usa_full_name_returns_51_states(self):
        """USA by full name returns exactly 51 states"""
        r = requests.get(f"{BASE_URL}/api/utils/provinces", params={"country_code": "USA"})
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "regions" in data, "Response must have 'regions' key"
        assert len(data["regions"]) == 51, f"Expected 51 states, got {len(data['regions'])}"
        # Check a few known states
        values = {s["value"] for s in data["regions"]}
        assert "CA" in values, "California (CA) must be present"
        assert "NY" in values, "New York (NY) must be present"
        assert "DC" in values, "District of Columbia (DC) must be present"

    def test_usa_iso_code_us_returns_51_states(self):
        """USA by ISO code US returns exactly 51 states"""
        r = requests.get(f"{BASE_URL}/api/utils/provinces", params={"country_code": "US"})
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert len(data["regions"]) == 51, f"Expected 51 states, got {len(data['regions'])}"

    def test_uk_returns_empty_regions(self):
        """UK (unsupported country) returns empty regions list"""
        r = requests.get(f"{BASE_URL}/api/utils/provinces", params={"country_code": "UK"})
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "regions" in data, "Response must have 'regions' key"
        assert data["regions"] == [], f"Expected empty list for UK, got {data['regions']}"

    def test_other_country_returns_empty(self):
        """Random country code returns empty regions"""
        r = requests.get(f"{BASE_URL}/api/utils/provinces", params={"country_code": "Other"})
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["regions"] == [], "Expected empty list for unsupported country"

    def test_response_structure(self):
        """Response has correct structure: country_code and regions array of {value, label}"""
        r = requests.get(f"{BASE_URL}/api/utils/provinces", params={"country_code": "Canada"})
        assert r.status_code == 200
        data = r.json()
        assert "country_code" in data, "Response must have 'country_code' key"
        assert "regions" in data, "Response must have 'regions' key"
        assert isinstance(data["regions"], list), "regions must be a list"
        # Each region must have value and label
        for region in data["regions"]:
            assert "value" in region, f"Region {region} must have 'value' key"
            assert "label" in region, f"Region {region} must have 'label' key"

    def test_missing_country_code_param_returns_422(self):
        """Missing required param returns 422"""
        r = requests.get(f"{BASE_URL}/api/utils/provinces")
        assert r.status_code == 422, f"Expected 422, got {r.status_code}"

    def test_endpoint_is_public_no_auth_required(self):
        """Province endpoint works without any auth header"""
        r = requests.get(
            f"{BASE_URL}/api/utils/provinces",
            params={"country_code": "Canada"},
            headers={}  # Explicitly no auth
        )
        assert r.status_code == 200, f"Should not require auth, got {r.status_code}"


class TestAdminLoginRegression:
    """Admin login regression test — platform admin uses no partner_code"""

    def test_platform_admin_login_success(self):
        """Platform admin can login without partner_code"""
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": "admin@automateaccounts.local",
                "password": "ChangeMe123!"
            }
        )
        assert r.status_code == 200, f"Platform admin login failed: {r.status_code} {r.text}"
        data = r.json()
        assert "token" in data, "Response must have 'token' key"

    def test_partner_admin_login_success(self):
        """Partner admin can login with valid partner_code — uses test-iter109-a tenant.
        Note: test.super.a account may be locked from previous test runs; check for 401 or lockout.
        """
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "partner_code": "test-iter109-a",
                "email": "test.super.a@iter109.test",
                "password": "TestSuper109!A"
            }
        )
        # Account may be locked from previous test runs — accept lockout as non-regression
        if r.status_code in (403, 429) and "locked" in r.text.lower():
            pytest.skip("Partner admin account locked from prior test runs — not a regression")
        assert r.status_code == 200, f"Partner admin login failed: {r.status_code} {r.text}"
        data = r.json()
        assert "token" in data, "Response must have 'token' key"

    def test_admin_login_wrong_password_401(self):
        """Admin login with wrong password returns 401"""
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": "admin@automateaccounts.local",
                "password": "WrongPassword999!"
            }
        )
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"


class TestCustomerLoginRegression:
    """Customer login regression test — uses test-iter109-a tenant"""

    def test_customer_login_success(self):
        """Customer can login with valid credentials (login_type=customer required)"""
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "partner_code": "test-iter109-a",
                "email": "test_cust3_iter111@test.local",
                "password": "TestCustomer123!",
                "login_type": "customer"
            }
        )
        assert r.status_code == 200, f"Customer login failed: {r.status_code} {r.text}"
        data = r.json()
        assert "token" in data, "Response must have 'token' key"

    def test_customer_can_access_orders(self):
        """Customer can access their orders after login"""
        login_r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "partner_code": "test-iter109-a",
                "email": "test_cust3_iter111@test.local",
                "password": "TestCustomer123!",
                "login_type": "customer"
            }
        )
        if login_r.status_code != 200:
            pytest.skip("Customer login failed, skipping order access test")

        token = login_r.json().get("token")

        r = requests.get(
            f"{BASE_URL}/api/orders",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 200, f"Customer orders access failed: {r.status_code} {r.text}"
        data = r.json()
        assert isinstance(data, list) or "orders" in data, "Orders response must be a list or dict with orders key"

    def test_customer_can_access_subscriptions(self):
        """Customer can access their subscriptions after login"""
        login_r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "partner_code": "test-iter109-a",
                "email": "test_cust3_iter111@test.local",
                "password": "TestCustomer123!",
                "login_type": "customer"
            }
        )
        if login_r.status_code != 200:
            pytest.skip("Customer login failed, skipping subscriptions access test")

        token = login_r.json().get("token")

        r = requests.get(
            f"{BASE_URL}/api/subscriptions",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 200, f"Customer subscriptions access failed: {r.status_code} {r.text}"
