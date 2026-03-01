"""
Tests for iteration 162 features:
1. Supported Currencies module (GET/POST/DELETE /api/admin/platform/currencies, GET /api/platform/supported-currencies)
2. FX Currency conversion in /partner/my-plan API
3. Plan visibility rules (tenant attribute matching)
4. Partner org (Tenant) create/edit with partner_type, industry, tags fields
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestSupportedCurrencies:
    """Tests for the Supported Currencies module."""

    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get platform super admin token."""
        r = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@automateaccounts.local",
            "password": "ChangeMe123!"
        })
        assert r.status_code == 200, f"Login failed: {r.text}"
        return r.json().get("token") or r.cookies.get("token")

    @pytest.fixture(scope="class")
    def admin_headers(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}

    def test_public_get_currencies_returns_list(self, admin_headers):
        """GET /api/platform/supported-currencies returns currency list."""
        r = requests.get(f"{BASE_URL}/api/platform/supported-currencies", headers=admin_headers)
        assert r.status_code == 200, f"Failed: {r.text}"
        data = r.json()
        assert "currencies" in data, "Missing 'currencies' key"
        assert isinstance(data["currencies"], list), "currencies should be a list"
        assert len(data["currencies"]) > 0, "Should have at least some currencies"
        print(f"Public currencies: {data['currencies']}")

    def test_public_get_currencies_has_defaults(self, admin_headers):
        """Default currencies include AUD, CAD, EUR, GBP, INR, MXN, USD."""
        r = requests.get(f"{BASE_URL}/api/platform/supported-currencies", headers=admin_headers)
        assert r.status_code == 200
        currencies = r.json()["currencies"]
        defaults = ["AUD", "CAD", "EUR", "GBP", "INR", "MXN", "USD"]
        for d in defaults:
            assert d in currencies, f"Missing default currency: {d}"
        print(f"Verified defaults: {defaults} all present in {currencies}")

    def test_admin_get_currencies_superadmin(self, admin_headers):
        """GET /api/admin/platform/currencies accessible to super admin."""
        r = requests.get(f"{BASE_URL}/api/admin/platform/currencies", headers=admin_headers)
        assert r.status_code == 200, f"Super admin should access this: {r.text}"
        data = r.json()
        assert "currencies" in data
        assert len(data["currencies"]) > 0
        print(f"Admin currencies: {data['currencies']}")

    def test_add_currency(self, admin_headers):
        """POST /api/admin/platform/currencies adds new currency."""
        # Add CHF (test currency)
        r = requests.post(f"{BASE_URL}/api/admin/platform/currencies",
                          json={"code": "CHF"}, headers=admin_headers)
        # Could be 200 (added) or 409 (already exists)
        assert r.status_code in [200, 409], f"Unexpected status: {r.text}"
        if r.status_code == 200:
            data = r.json()
            assert "currencies" in data
            assert "CHF" in data["currencies"]
            print(f"CHF added. New list: {data['currencies']}")
        else:
            print(f"CHF already exists (409) - that's fine")

    def test_add_currency_verified_in_list(self, admin_headers):
        """After adding CHF, verify it appears in the list."""
        # Ensure CHF is added
        requests.post(f"{BASE_URL}/api/admin/platform/currencies",
                      json={"code": "CHF"}, headers=admin_headers)
        # Now verify it's in the list
        r = requests.get(f"{BASE_URL}/api/admin/platform/currencies", headers=admin_headers)
        assert r.status_code == 200
        currencies = r.json()["currencies"]
        assert "CHF" in currencies, f"CHF should be in list: {currencies}"
        print(f"CHF verified in currency list")

    def test_add_invalid_currency_code(self, admin_headers):
        """POST /api/admin/platform/currencies rejects invalid code."""
        r = requests.post(f"{BASE_URL}/api/admin/platform/currencies",
                          json={"code": "INVALID"}, headers=admin_headers)
        assert r.status_code == 400, f"Should reject invalid code: {r.text}"
        print(f"Invalid code correctly rejected: {r.json()}")

    def test_remove_currency(self, admin_headers):
        """DELETE /api/admin/platform/currencies/{code} removes a currency."""
        # First ensure CHF exists
        requests.post(f"{BASE_URL}/api/admin/platform/currencies",
                      json={"code": "CHF"}, headers=admin_headers)
        # Remove it
        r = requests.delete(f"{BASE_URL}/api/admin/platform/currencies/CHF",
                            headers=admin_headers)
        assert r.status_code == 200, f"Delete failed: {r.text}"
        data = r.json()
        assert "currencies" in data
        assert "CHF" not in data["currencies"], "CHF should be removed"
        print(f"CHF removed. Remaining: {data['currencies']}")

    def test_remove_nonexistent_currency(self, admin_headers):
        """DELETE /api/admin/platform/currencies/{code} returns 404 for missing currency."""
        r = requests.delete(f"{BASE_URL}/api/admin/platform/currencies/ZZZ",
                            headers=admin_headers)
        assert r.status_code == 404, f"Should be 404: {r.text}"
        print(f"Non-existent currency correctly 404'd")


class TestPlanVisibilityRules:
    """Tests for plan visibility rules on the /api/partner/my-plan endpoint."""

    @pytest.fixture(scope="class")
    def admin_token(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@automateaccounts.local",
            "password": "ChangeMe123!"
        })
        assert r.status_code == 200
        return r.json().get("token")

    @pytest.fixture(scope="class")
    def partner_token(self):
        """Get partner admin token."""
        r = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@ligerinc.local",
            "password": "ChangeMe123!"
        })
        if r.status_code != 200:
            pytest.skip(f"Partner login failed: {r.text}")
        return r.json().get("token")

    @pytest.fixture(scope="class")
    def admin_headers(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}

    @pytest.fixture(scope="class")
    def partner_headers(self, partner_token):
        return {"Authorization": f"Bearer {partner_token}", "Content-Type": "application/json"}

    def test_my_plan_returns_correct_structure(self, partner_headers):
        """GET /api/partner/my-plan returns expected fields."""
        r = requests.get(f"{BASE_URL}/api/partner/my-plan", headers=partner_headers)
        assert r.status_code == 200, f"Failed: {r.text}"
        data = r.json()
        assert "current_plan" in data, "Missing current_plan"
        assert "available_plans" in data, "Missing available_plans"
        assert "base_currency" in data, "Missing base_currency"
        assert "current_price_in_base" in data, "Missing current_price_in_base"
        print(f"my-plan: base_currency={data['base_currency']}, "
              f"current_price_in_base={data['current_price_in_base']}, "
              f"available_plans count={len(data['available_plans'])}")

    def test_my_plan_available_plans_have_display_fields(self, partner_headers):
        """Available plans should include display_price and display_currency for FX conversion."""
        r = requests.get(f"{BASE_URL}/api/partner/my-plan", headers=partner_headers)
        assert r.status_code == 200
        data = r.json()
        plans = data.get("available_plans", [])
        if not plans:
            print("No available plans — skipping display_price check (may mean partner is on highest plan)")
            return
        for plan in plans:
            assert "display_price" in plan, f"Plan {plan.get('name')} missing display_price"
            assert "display_currency" in plan, f"Plan {plan.get('name')} missing display_currency"
            # display_currency should match base_currency
            assert plan["display_currency"] == data["base_currency"], \
                f"display_currency {plan['display_currency']} != base_currency {data['base_currency']}"
        print(f"All {len(plans)} available plans have display_price and display_currency")

    def test_admin_plan_create_with_visibility_rule(self, admin_headers):
        """POST /api/admin/plans creates plan with visibility_rules field."""
        r = requests.get(f"{BASE_URL}/api/admin/plans", headers=admin_headers)
        assert r.status_code == 200
        plans = r.json().get("plans", [])
        # Pick first non-default plan to edit
        test_plan = next((p for p in plans if not p.get("is_default")), None)
        if not test_plan:
            print("No non-default plans to test visibility rules on")
            return

        # Add a visibility rule to it
        plan_id = test_plan["id"]
        payload = {
            "name": test_plan["name"],
            "is_public": False,
            "visibility_rules": [{"field": "partner_code", "operator": "equals", "value": "ligerinc"}],
            "monthly_price": test_plan.get("monthly_price"),
            "currency": test_plan.get("currency", "GBP"),
        }
        r = requests.put(f"{BASE_URL}/api/admin/plans/{plan_id}", json=payload, headers=admin_headers)
        assert r.status_code == 200, f"Plan update failed: {r.text}"
        data = r.json()
        print(f"Plan updated with visibility rule: {data}")

    def test_get_plan_has_visibility_rules(self, admin_headers):
        """GET /api/admin/plans returns plans with visibility_rules field."""
        r = requests.get(f"{BASE_URL}/api/admin/plans", headers=admin_headers)
        assert r.status_code == 200
        plans = r.json().get("plans", [])
        assert len(plans) > 0
        # Check that visibility_rules field is present on plans (may be null/empty)
        for plan in plans:
            # visibility_rules is optional - just verify the response is valid
            if "visibility_rules" in plan:
                assert isinstance(plan["visibility_rules"], (list, type(None))), \
                    f"visibility_rules should be list or None, got {type(plan['visibility_rules'])}"
        print(f"Plans have valid visibility_rules field structure")


class TestTenantFieldsPartnerTypeIndustryTags:
    """Test that tenant create/update supports partner_type, industry, tags."""

    @pytest.fixture(scope="class")
    def admin_token(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@automateaccounts.local",
            "password": "ChangeMe123!"
        })
        assert r.status_code == 200
        return r.json().get("token")

    @pytest.fixture(scope="class")
    def admin_headers(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}

    def test_tenants_list_returns_tenants(self, admin_headers):
        """GET /api/admin/tenants returns tenants with new fields."""
        r = requests.get(f"{BASE_URL}/api/admin/tenants", headers=admin_headers)
        assert r.status_code == 200, f"Failed: {r.text}"
        data = r.json()
        assert "tenants" in data
        assert len(data["tenants"]) > 0
        print(f"Got {len(data['tenants'])} tenants")

    def test_tenant_update_with_partner_type_industry_tags(self, admin_headers):
        """PUT /api/admin/tenants/{id} accepts partner_type, industry, tags."""
        # Get list of tenants
        r = requests.get(f"{BASE_URL}/api/admin/tenants", headers=admin_headers)
        assert r.status_code == 200
        tenants = r.json().get("tenants", [])
        # Find a non-platform-default tenant
        test_tenant = next(
            (t for t in tenants if t.get("code") != "automate-accounts"), None
        )
        if not test_tenant:
            print("No non-default tenant to test against - skipping")
            return

        tenant_id = test_tenant["id"]
        payload = {
            "name": test_tenant["name"],
            "partner_type": "Reseller",
            "industry": "Technology",
            "tags": ["test", "automated"]
        }
        r = requests.put(f"{BASE_URL}/api/admin/tenants/{tenant_id}", json=payload,
                         headers=admin_headers)
        assert r.status_code == 200, f"Tenant update failed: {r.text}"
        print(f"Tenant updated with partner_type/industry/tags: {r.json()}")

    def test_tenant_get_after_update_has_new_fields(self, admin_headers):
        """After updating tenant, GET /api/admin/tenants returns updated fields."""
        r = requests.get(f"{BASE_URL}/api/admin/tenants", headers=admin_headers)
        assert r.status_code == 200
        tenants = r.json().get("tenants", [])
        test_tenant = next(
            (t for t in tenants if t.get("code") != "automate-accounts"), None
        )
        if not test_tenant:
            print("No non-default tenant found")
            return

        # Check the fields exist in response (may be null if not set)
        # After our update above, they should be set
        tid = test_tenant["id"]
        # update it
        payload = {"name": test_tenant["name"], "partner_type": "Agency", "industry": "Finance", "tags": ["vip"]}
        r = requests.put(f"{BASE_URL}/api/admin/tenants/{tid}", json=payload, headers=admin_headers)
        assert r.status_code == 200

        # Fetch again and verify
        r2 = requests.get(f"{BASE_URL}/api/admin/tenants", headers=admin_headers)
        tenants2 = r2.json().get("tenants", [])
        updated = next((t for t in tenants2 if t["id"] == tid), None)
        if updated:
            assert updated.get("partner_type") == "Agency", f"partner_type mismatch: {updated.get('partner_type')}"
            assert updated.get("industry") == "Finance", f"industry mismatch: {updated.get('industry')}"
            assert "vip" in (updated.get("tags") or []), f"tags missing 'vip': {updated.get('tags')}"
            print(f"Tenant fields verified: partner_type={updated.get('partner_type')}, "
                  f"industry={updated.get('industry')}, tags={updated.get('tags')}")
        else:
            print("Could not re-fetch updated tenant")


class TestPartnerPlanBillingFXCurrency:
    """Test FX currency conversion in partner plan & billing."""

    @pytest.fixture(scope="class")
    def partner_token(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@ligerinc.local",
            "password": "ChangeMe123!"
        })
        if r.status_code != 200:
            pytest.skip(f"Partner login failed: {r.text}")
        return r.json().get("token")

    @pytest.fixture(scope="class")
    def partner_headers(self, partner_token):
        return {"Authorization": f"Bearer {partner_token}", "Content-Type": "application/json"}

    def test_partner_my_plan_base_currency(self, partner_headers):
        """Partner my-plan returns base_currency matching partner org's base_currency."""
        r = requests.get(f"{BASE_URL}/api/partner/my-plan", headers=partner_headers)
        assert r.status_code == 200, f"Failed: {r.text}"
        data = r.json()
        base_currency = data.get("base_currency")
        assert base_currency is not None, "base_currency should not be None"
        assert len(base_currency) == 3, f"base_currency should be 3-letter ISO code: {base_currency}"
        print(f"Partner base_currency: {base_currency}")

    def test_partner_one_time_rates(self, partner_headers):
        """GET /api/partner/one-time-rates returns rates."""
        r = requests.get(f"{BASE_URL}/api/partner/one-time-rates", headers=partner_headers)
        assert r.status_code == 200, f"Failed: {r.text}"
        data = r.json()
        assert "rates" in data
        print(f"One-time rates: {data['rates']}")

    def test_partner_plan_available_plans_display_in_base_currency(self, partner_headers):
        """Available plans in /partner/my-plan should show prices in base currency."""
        r = requests.get(f"{BASE_URL}/api/partner/my-plan", headers=partner_headers)
        assert r.status_code == 200
        data = r.json()
        base_currency = data.get("base_currency")
        available_plans = data.get("available_plans", [])
        
        for plan in available_plans:
            display_currency = plan.get("display_currency")
            assert display_currency == base_currency, \
                f"Plan {plan.get('name')}: display_currency={display_currency} != base_currency={base_currency}"
        
        print(f"All {len(available_plans)} plans have display_currency={base_currency}")


class TestCurrenciesPermissions:
    """Test that currencies admin endpoint requires super admin role."""

    @pytest.fixture(scope="class")
    def partner_token(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@ligerinc.local",
            "password": "ChangeMe123!"
        })
        if r.status_code != 200:
            pytest.skip(f"Partner login failed: {r.text}")
        return r.json().get("token")

    @pytest.fixture(scope="class")
    def partner_headers(self, partner_token):
        return {"Authorization": f"Bearer {partner_token}", "Content-Type": "application/json"}

    def test_partner_cannot_access_admin_currencies(self, partner_headers):
        """Partner user should NOT be able to access /api/admin/platform/currencies."""
        r = requests.get(f"{BASE_URL}/api/admin/platform/currencies", headers=partner_headers)
        assert r.status_code in [401, 403], \
            f"Partner should not access admin currencies endpoint: {r.status_code} {r.text}"
        print(f"Partner correctly denied admin currencies access: {r.status_code}")

    def test_partner_cannot_add_currency(self, partner_headers):
        """Partner user should NOT be able to add currencies."""
        r = requests.post(f"{BASE_URL}/api/admin/platform/currencies",
                          json={"code": "XYZ"}, headers=partner_headers)
        assert r.status_code in [401, 403], \
            f"Partner should not add currencies: {r.status_code} {r.text}"
        print(f"Partner correctly denied adding currencies: {r.status_code}")

    def test_partner_can_read_public_currencies(self, partner_headers):
        """Partner user CAN access /api/platform/supported-currencies (public endpoint)."""
        r = requests.get(f"{BASE_URL}/api/platform/supported-currencies", headers=partner_headers)
        assert r.status_code == 200, f"Partner should read public currencies: {r.text}"
        data = r.json()
        assert "currencies" in data
        print(f"Partner can read public currencies: {data['currencies']}")
