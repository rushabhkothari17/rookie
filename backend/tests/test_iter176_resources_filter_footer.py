"""
Iteration 176 backend tests:
1. Resources admin list endpoint with price/currency filters
2. Verify price_min, price_max, price_currency params work correctly
Test resource: title='test', price=100, currency=USD
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


@pytest.fixture(scope="module")
def admin_token():
    """Get admin token for automate-accounts platform super admin."""
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@automateaccounts.local", "password": "ChangeMe123!"},
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} - {r.text}"
    token = r.json().get("token") or r.json().get("access_token")
    assert token, f"No token in response: {r.json()}"
    return token


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


class TestResourcesAdminListFilter:
    """Test /resources/admin/list with price and currency filters."""

    def test_list_all_resources_no_filter(self, admin_headers):
        """Should return resources including the 'test' resource with price=100 USD."""
        r = requests.get(f"{BASE_URL}/api/resources/admin/list", headers=admin_headers)
        assert r.status_code == 200, f"Unexpected status: {r.status_code}, {r.text}"
        data = r.json()
        assert "resources" in data
        assert "total" in data
        print(f"Total resources (no filter): {data['total']}")
        # Verify the test resource exists
        titles = [res.get("title", "") for res in data["resources"]]
        print(f"Resource titles: {titles}")

    def test_list_resources_price_min_50(self, admin_headers):
        """price_min=50 should return resources with price >= 50. Test resource has price=100."""
        r = requests.get(
            f"{BASE_URL}/api/resources/admin/list",
            params={"price_min": 50},
            headers=admin_headers,
        )
        assert r.status_code == 200, f"Status: {r.status_code}, {r.text}"
        data = r.json()
        resources = data["resources"]
        total = data["total"]
        print(f"Resources with price_min=50: total={total}")
        # All returned resources must have price >= 50
        for res in resources:
            if res.get("price") is not None:
                assert float(res["price"]) >= 50, f"Resource {res.get('id')} has price {res['price']} < 50"
        # Expect at least the test resource (price=100) to be included
        prices = [res.get("price") for res in resources]
        print(f"Prices: {prices}")
        assert total >= 1, "Expected at least 1 resource with price >= 50"

    def test_list_resources_price_min_200(self, admin_headers):
        """price_min=200 should return 0 resources since test resource has price=100."""
        r = requests.get(
            f"{BASE_URL}/api/resources/admin/list",
            params={"price_min": 200},
            headers=admin_headers,
        )
        assert r.status_code == 200, f"Status: {r.status_code}, {r.text}"
        data = r.json()
        total = data["total"]
        print(f"Resources with price_min=200: total={total}")
        assert total == 0, f"Expected 0 resources with price_min=200, got {total}"

    def test_list_resources_price_max_150(self, admin_headers):
        """price_max=150 should include the test resource (price=100)."""
        r = requests.get(
            f"{BASE_URL}/api/resources/admin/list",
            params={"price_max": 150},
            headers=admin_headers,
        )
        assert r.status_code == 200, f"Status: {r.status_code}, {r.text}"
        data = r.json()
        total = data["total"]
        print(f"Resources with price_max=150: total={total}")
        for res in data["resources"]:
            if res.get("price") is not None:
                assert float(res["price"]) <= 150, f"Resource price {res['price']} > 150"

    def test_list_resources_currency_usd(self, admin_headers):
        """price_currency=USD should return resources with currency=USD. Test resource is USD."""
        r = requests.get(
            f"{BASE_URL}/api/resources/admin/list",
            params={"price_currency": "USD"},
            headers=admin_headers,
        )
        assert r.status_code == 200, f"Status: {r.status_code}, {r.text}"
        data = r.json()
        total = data["total"]
        resources = data["resources"]
        print(f"Resources with currency=USD: total={total}")
        # All returned resources must have currency=USD
        for res in resources:
            assert res.get("currency") == "USD", f"Resource {res.get('id')} has currency {res.get('currency')}"
        assert total >= 1, "Expected at least 1 USD resource"

    def test_list_resources_currency_gbp(self, admin_headers):
        """price_currency=GBP should return 0 resources (test resource is USD)."""
        r = requests.get(
            f"{BASE_URL}/api/resources/admin/list",
            params={"price_currency": "GBP"},
            headers=admin_headers,
        )
        assert r.status_code == 200, f"Status: {r.status_code}, {r.text}"
        data = r.json()
        total = data["total"]
        print(f"Resources with currency=GBP: total={total}")
        assert total == 0, f"Expected 0 GBP resources, got {total}"

    def test_list_resources_combined_filter(self, admin_headers):
        """Combined: price_min=50 + price_currency=USD should return the test resource."""
        r = requests.get(
            f"{BASE_URL}/api/resources/admin/list",
            params={"price_min": 50, "price_currency": "USD"},
            headers=admin_headers,
        )
        assert r.status_code == 200, f"Status: {r.status_code}, {r.text}"
        data = r.json()
        total = data["total"]
        resources = data["resources"]
        print(f"Resources with price_min=50, currency=USD: total={total}")
        # Expect test resource (price=100, currency=USD)
        assert total >= 1, "Expected at least 1 resource"
        for res in resources:
            assert res.get("currency") == "USD", f"Currency mismatch: {res.get('currency')}"
            if res.get("price") is not None:
                assert float(res["price"]) >= 50, f"Price {res['price']} < 50"

    def test_list_resources_pagination_fields(self, admin_headers):
        """Verify response has pagination fields."""
        r = requests.get(f"{BASE_URL}/api/resources/admin/list", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "page" in data
        assert "per_page" in data
        assert "total" in data
        assert "total_pages" in data
        print(f"Pagination: page={data['page']}, per_page={data['per_page']}, total={data['total']}, total_pages={data['total_pages']}")

    def test_list_resources_price_range(self, admin_headers):
        """price_min=50, price_max=150 should return test resource."""
        r = requests.get(
            f"{BASE_URL}/api/resources/admin/list",
            params={"price_min": 50, "price_max": 150},
            headers=admin_headers,
        )
        assert r.status_code == 200
        data = r.json()
        total = data["total"]
        print(f"Resources with price 50-150: total={total}")
        for res in data["resources"]:
            if res.get("price") is not None:
                price = float(res["price"])
                assert 50 <= price <= 150, f"Price {price} out of range 50-150"
