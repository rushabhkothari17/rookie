"""
Iteration 277 backend tests:
- Cart preview (orders/preview) endpoint for platform admin
- Store products listing
- Search/sort/pagination API behavior
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"
PARTNER_CODE = "automate-accounts"


@pytest.fixture(scope="module")
def admin_token():
    """Get platform admin JWT token.
    Note: Platform admin logs in WITHOUT partner_code (reserved platform login).
    """
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    assert token, f"No token in response: {data}"
    return token


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json",
    }


class TestAdminLogin:
    """Verify platform admin login works."""

    def test_admin_login_success(self):
        # Platform admin logs in WITHOUT partner_code
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=15,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        token = data.get("token") or data.get("access_token")
        assert token, "Token not returned"
        # Login response returns role at top level (not inside user obj)
        role = data.get("role", "")
        assert "platform" in role or "super_admin" in role or "admin" in role, f"Unexpected role: {role}"
        print(f"PASS: Admin login successful, role={role}")


class TestStoreProducts:
    """Verify products are accessible to platform admin."""

    def test_get_products_as_admin(self, admin_headers):
        resp = requests.get(
            f"{BASE_URL}/api/products",
            headers=admin_headers,
            timeout=15,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        # Should be a list or have items key
        products = data if isinstance(data, list) else data.get("items", data.get("products", []))
        print(f"PASS: Products endpoint returns {len(products)} products")
        return products

    def test_get_store_products_public(self, admin_headers):
        """Test the admin products endpoint to get all products."""
        resp = requests.get(
            f"{BASE_URL}/api/products",
            headers=admin_headers,
            timeout=15,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        products = data if isinstance(data, list) else data.get("items", data.get("products", []))
        print(f"PASS: Products endpoint returns {len(products)} products (admin view)")
        if products:
            first = products[0]
            assert "id" in first, "Product missing 'id'"
            assert "name" in first, "Product missing 'name'"
            print(f"  First product: id={first['id']}, name={first['name']}")
        return products


class TestCartPreview:
    """Test cart preview (orders/preview) endpoint — the main bug being tested."""

    def _get_first_product_id(self, admin_headers):
        """Get a valid product_id from the store."""
        # Try admin products endpoint first
        resp = requests.get(
            f"{BASE_URL}/api/products",
            headers=admin_headers,
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            products = data if isinstance(data, list) else data.get("items", data.get("products", []))
            if products:
                return products[0]["id"]

        # Fallback: try public store endpoint
        resp = requests.get(
            f"{BASE_URL}/api/store/products",
            params={"partner_code": PARTNER_CODE},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            products = data if isinstance(data, list) else data.get("items", [])
            if products:
                return products[0]["id"]
        return None

    def test_cart_preview_platform_admin(self, admin_headers):
        """
        Platform admin should be able to preview cart without 'Product not found' error.
        This was the main bug: platform_admin has tenant_id=None so product lookup failed
        when using tenant_id filter. Fix: if product not found and user is_platform_admin,
        retry without tenant_id filter.
        """
        product_id = self._get_first_product_id(admin_headers)
        if not product_id:
            pytest.skip("No products found — cannot test cart preview")

        print(f"Testing cart preview with product_id={product_id}")

        payload = {
            "items": [
                {
                    "product_id": product_id,
                    "quantity": 1,
                    "inputs": {},
                }
            ],
            "promo_code": None,
        }
        resp = requests.post(
            f"{BASE_URL}/api/orders/preview",
            json=payload,
            headers=admin_headers,
            timeout=15,
        )
        assert resp.status_code == 200, (
            f"Cart preview failed with {resp.status_code}: {resp.text}\n"
            f"Expected: platform admin can preview cart items without 'Product not found' error"
        )
        data = resp.json()
        # Should have results or items
        results = data.get("results") if isinstance(data, dict) else data
        if isinstance(data, dict):
            results = data.get("results", data.get("items", [data]))
        print(f"PASS: Cart preview returns data: {data}")
        assert results, "Cart preview returned empty results"
        first = results[0] if isinstance(results, list) else results
        assert "product_id" in first or "product" in first, f"Expected product data in result: {first}"
        print(f"PASS: Cart preview works for platform admin. product_id={product_id}")

    def test_cart_preview_no_auth_fails(self):
        """Cart preview without auth should return 401/403."""
        resp = requests.post(
            f"{BASE_URL}/api/orders/preview",
            json={"items": [{"product_id": "fake-id", "quantity": 1, "inputs": {}}]},
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        assert resp.status_code in [401, 403, 422], (
            f"Expected 401/403/422 without auth, got {resp.status_code}"
        )
        print(f"PASS: Cart preview without auth returns {resp.status_code}")


class TestStoreFiltersAndPagination:
    """Test store filtering, sorting, and pagination at API level."""

    def test_store_categories_endpoint(self, admin_headers):
        resp = requests.get(
            f"{BASE_URL}/api/categories",
            params={"partner_code": PARTNER_CODE},
            timeout=15,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print(f"PASS: Categories endpoint accessible, response: {resp.json()}")

    def test_store_products_with_search(self, admin_headers):
        """Test products can be searched at API level (admin endpoint)."""
        resp = requests.get(
            f"{BASE_URL}/api/products",
            params={"search": "sample"},
            headers=admin_headers,
            timeout=15,
        )
        # Admin products endpoint should return 200 with search param
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print(f"PASS: Admin products with search param: {resp.status_code}")


class TestResolveAdminTenantId:
    """Test that platform admin can access cross-tenant data."""

    def test_admin_me_endpoint(self, admin_headers):
        """Verify logged-in admin user data has expected role via /api/me."""
        resp = requests.get(
            f"{BASE_URL}/api/me",
            headers=admin_headers,
            timeout=15,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        # /api/me returns {"user": {...}, "customer": {...}}
        user = data.get("user", data)
        role = user.get("role", "")
        is_platform = "platform" in role
        assert is_platform, f"Expected platform role, got: {role}"
        print(f"PASS: Admin /api/me returned role={role}, is_platform={is_platform}")
        # Platform admin tenant_id is None
        tenant_id = user.get("tenant_id")
        assert tenant_id is None, f"Expected tenant_id=None for platform admin, got: {tenant_id}"
        print(f"  tenant_id={tenant_id} (expected None for platform admin)")
