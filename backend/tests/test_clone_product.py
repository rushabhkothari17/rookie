"""Backend tests for product clone endpoint and related catalog operations."""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

PARTNER_CODE = "automate-accounts"
ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"


@pytest.fixture(scope="module")
def auth_token():
    """Get auth token for platform super admin (no partner_code needed)."""
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    token = r.json().get("token") or r.json().get("access_token")
    assert token, f"No token in response: {r.json()}"
    return token


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def sample_product_id(auth_headers):
    """Get the first available product ID for testing."""
    r = requests.get(f"{BASE_URL}/api/admin/products-all?per_page=10", headers=auth_headers)
    assert r.status_code == 200, f"Failed to list products: {r.text}"
    products = r.json().get("products", [])
    assert len(products) > 0, "No products found in the catalog"
    return products[0]["id"], products[0]["name"]


class TestCloneEndpoint:
    """Tests for POST /api/admin/products/{product_id}/clone"""

    def test_clone_product_returns_200(self, auth_headers, sample_product_id):
        """Clone endpoint should return 200 with cloned product."""
        product_id, product_name = sample_product_id
        r = requests.post(
            f"{BASE_URL}/api/admin/products/{product_id}/clone",
            headers=auth_headers,
        )
        assert r.status_code == 200, f"Clone failed: {r.status_code} {r.text}"
        data = r.json()
        assert "product" in data, f"No 'product' key in response: {data}"

    def test_clone_product_name_has_cloned_suffix(self, auth_headers, sample_product_id):
        """Cloned product name should end with '_cloned'."""
        product_id, product_name = sample_product_id
        r = requests.post(
            f"{BASE_URL}/api/admin/products/{product_id}/clone",
            headers=auth_headers,
        )
        assert r.status_code == 200
        cloned = r.json()["product"]
        assert cloned["name"].endswith("_cloned"), f"Expected '_cloned' suffix, got: {cloned['name']}"
        assert cloned["name"] == product_name + "_cloned", \
            f"Expected '{product_name}_cloned', got '{cloned['name']}'"

    def test_clone_product_is_inactive(self, auth_headers, sample_product_id):
        """Cloned product should be inactive."""
        product_id, _ = sample_product_id
        r = requests.post(
            f"{BASE_URL}/api/admin/products/{product_id}/clone",
            headers=auth_headers,
        )
        assert r.status_code == 200
        cloned = r.json()["product"]
        assert cloned["is_active"] is False, f"Cloned product should be inactive, got: {cloned['is_active']}"

    def test_clone_product_has_new_id(self, auth_headers, sample_product_id):
        """Cloned product should have a different ID than the original."""
        product_id, _ = sample_product_id
        r = requests.post(
            f"{BASE_URL}/api/admin/products/{product_id}/clone",
            headers=auth_headers,
        )
        assert r.status_code == 200
        cloned = r.json()["product"]
        assert cloned["id"] != product_id, f"Cloned product should have a new ID"
        assert "id" in cloned, "Cloned product missing id field"

    def test_clone_product_appears_in_list(self, auth_headers, sample_product_id):
        """After cloning, the new product should appear in the products list."""
        product_id, product_name = sample_product_id
        r = requests.post(
            f"{BASE_URL}/api/admin/products/{product_id}/clone",
            headers=auth_headers,
        )
        assert r.status_code == 200
        cloned = r.json()["product"]
        cloned_id = cloned["id"]

        # Verify by listing products
        list_r = requests.get(f"{BASE_URL}/api/admin/products-all?per_page=500", headers=auth_headers)
        assert list_r.status_code == 200
        all_products = list_r.json().get("products", [])
        found = next((p for p in all_products if p["id"] == cloned_id), None)
        assert found is not None, f"Cloned product {cloned_id} not found in product list"
        assert found["is_active"] is False, "Cloned product should be inactive in list"
        assert found["name"].endswith("_cloned")

    def test_original_product_unchanged_after_clone(self, auth_headers, sample_product_id):
        """Original product should remain unchanged after clone."""
        product_id, product_name = sample_product_id

        # Get original before clone
        before_r = requests.get(f"{BASE_URL}/api/admin/products-all?per_page=500", headers=auth_headers)
        assert before_r.status_code == 200
        original_before = next(
            (p for p in before_r.json()["products"] if p["id"] == product_id), None
        )
        assert original_before is not None

        # Clone
        r = requests.post(
            f"{BASE_URL}/api/admin/products/{product_id}/clone",
            headers=auth_headers,
        )
        assert r.status_code == 200

        # Get original after clone
        after_r = requests.get(f"{BASE_URL}/api/admin/products-all?per_page=500", headers=auth_headers)
        assert after_r.status_code == 200
        original_after = next(
            (p for p in after_r.json()["products"] if p["id"] == product_id), None
        )
        assert original_after is not None, "Original product not found after clone"
        assert original_after["name"] == product_name, \
            f"Original product name changed! Expected '{product_name}', got '{original_after['name']}'"

    def test_clone_nonexistent_product_returns_404(self, auth_headers):
        """Cloning a non-existent product should return 404."""
        r = requests.post(
            f"{BASE_URL}/api/admin/products/nonexistent_product_id_xyz/clone",
            headers=auth_headers,
        )
        assert r.status_code == 404, f"Expected 404, got: {r.status_code}"

    def test_clone_without_auth_returns_401(self):
        """Clone without auth should return 401."""
        r = requests.post(f"{BASE_URL}/api/admin/products/some_id/clone")
        assert r.status_code in (401, 403), f"Expected 401/403, got: {r.status_code}"
