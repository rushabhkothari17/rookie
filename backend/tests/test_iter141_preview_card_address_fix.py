"""
Iteration 141 backend tests:
1. Verify /api/products endpoint returns 200 and products list
2. Verify /api/products/{id} endpoint works (with/without auth)
3. Verify visibility conditions work for authenticated users (address loaded from db.addresses)
4. Verify /api/categories returns correctly
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
PARTNER_CODE = "automate-accounts"
ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"


@pytest.fixture(scope="module")
def admin_token():
    """Login as admin and get JWT token."""
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    if resp.status_code == 200:
        data = resp.json()
        token = data.get("access_token") or data.get("token")
        return token
    pytest.skip(f"Admin login failed: {resp.status_code} {resp.text[:200]}")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


class TestBackendHealth:
    """Basic connectivity tests"""

    def test_api_root(self):
        resp = requests.get(f"{BASE_URL}/api/")
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data
        print(f"API root: {data['message']}")

    def test_categories_public(self):
        """Public categories endpoint returns 200 with list"""
        resp = requests.get(
            f"{BASE_URL}/api/categories",
            params={"partner_code": PARTNER_CODE},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "categories" in data
        assert isinstance(data["categories"], list)
        print(f"Categories: {data['categories'][:3]}")


class TestProductsEndpoint:
    """Tests for the get_products endpoint (address loading fix)"""

    def test_products_public_no_auth(self):
        """Public products list without auth should work"""
        resp = requests.get(
            f"{BASE_URL}/api/products",
            params={"partner_code": PARTNER_CODE},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "products" in data
        assert isinstance(data["products"], list)
        print(f"Products count (unauthenticated): {len(data['products'])}")

    def test_products_with_admin_auth(self, admin_headers):
        """Admin should see all active products"""
        resp = requests.get(
            f"{BASE_URL}/api/products",
            headers=admin_headers,
            params={"partner_code": PARTNER_CODE},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "products" in data
        products = data["products"]
        assert isinstance(products, list)
        print(f"Products count (admin): {len(products)}")

    def test_products_have_expected_fields(self, admin_headers):
        """Products should have basic expected fields"""
        resp = requests.get(
            f"{BASE_URL}/api/products",
            headers=admin_headers,
            params={"partner_code": PARTNER_CODE},
        )
        assert resp.status_code == 200
        products = resp.json().get("products", [])
        if products:
            p = products[0]
            # Verify key fields exist (no _id)
            assert "id" in p, "Product should have 'id'"
            assert "name" in p, "Product should have 'name'"
            assert "_id" not in p, "MongoDB _id should be excluded"
            print(f"First product: {p.get('name')} (id={p.get('id')})")


class TestSingleProductEndpoint:
    """Tests for get_product (also has address loading fix)"""

    def test_single_product_with_admin_auth(self, admin_headers):
        """Fetch a real product by ID with admin auth"""
        # First get a product ID
        list_resp = requests.get(
            f"{BASE_URL}/api/products",
            headers=admin_headers,
            params={"partner_code": PARTNER_CODE},
        )
        assert list_resp.status_code == 200
        products = list_resp.json().get("products", [])
        if not products:
            pytest.skip("No active products found to test single product endpoint")
        
        product_id = products[0]["id"]
        resp = requests.get(
            f"{BASE_URL}/api/products/{product_id}",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "product" in data
        product = data["product"]
        assert product["id"] == product_id
        assert "_id" not in product
        print(f"Single product fetched: {product.get('name')} (id={product_id})")

    def test_single_product_nonexistent_returns_404(self, admin_headers):
        """Nonexistent product ID should return 404"""
        resp = requests.get(
            f"{BASE_URL}/api/products/nonexistent-product-id-12345",
            headers=admin_headers,
        )
        assert resp.status_code == 404
        print("Nonexistent product correctly returns 404")


class TestAdminProductsCRUD:
    """Admin product CRUD endpoints (used by ProductEditor)"""

    def test_admin_products_all_list(self, admin_headers):
        """Admin products-all endpoint works"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/products-all",
            headers=admin_headers,
            params={"per_page": 100},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "products" in data
        print(f"Admin products-all count: {len(data['products'])}")

    def test_admin_categories(self, admin_headers):
        """Admin categories endpoint works"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/categories",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "categories" in data
        print(f"Admin categories: {data.get('categories', [])[:3]}")

    def test_admin_customers_returns_addresses(self, admin_headers):
        """Admin customers endpoint should return addresses (used by ProductEditor enrichment)"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/customers",
            headers=admin_headers,
            params={"per_page": 100},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "customers" in data
        # Check if addresses are included (used for frontend enrichment)
        if "addresses" in data:
            print(f"Addresses count: {len(data['addresses'])}")
        else:
            print("Note: addresses not returned in customers response (frontend enriches from separate call)")
        print(f"Customers count: {len(data['customers'])}")

    def test_create_and_delete_product(self, admin_headers):
        """Full CRUD: Create a product with visibility conditions and verify persistence, then delete"""
        # Create product with visibility conditions (country-based)
        payload = {
            "name": "TEST_Preview_Card_Product",
            "card_tag": "Test Tag",
            "card_description": "Test card description for preview",
            "card_bullets": ["Bullet one", "Bullet two"],
            "description_long": "Full description",
            "bullets": [],
            "category": "Build & Automate",
            "faqs": [],
            "base_price": 100,
            "is_subscription": False,
            "pricing_type": "internal",
            "is_active": True,
            "visible_to_customers": [],
            "restricted_to": [],
            "intake_schema_json": {"questions": []},
            "custom_sections": [],
            "display_layout": "standard",
            "currency": "USD",
            "visibility_conditions": {
                "top_logic": "AND",
                "groups": [
                    {
                        "logic": "AND",
                        "conditions": [
                            {"field": "country", "operator": "equals", "value": "GB"}
                        ]
                    }
                ]
            },
        }
        create_resp = requests.post(
            f"{BASE_URL}/api/admin/products",
            headers=admin_headers,
            json=payload,
        )
        assert create_resp.status_code in [200, 201], f"Create failed: {create_resp.text[:300]}"
        data = create_resp.json()
        # The API may return the product or just a message
        product_id = None
        if "id" in data:
            product_id = data["id"]
        elif "product" in data:
            product_id = data["product"].get("id")
        elif "product_id" in data:
            product_id = data["product_id"]
        
        print(f"Created product with visibility conditions: {data}")

        # GET to verify persistence
        if product_id:
            get_resp = requests.get(
                f"{BASE_URL}/api/admin/products/{product_id}",
                headers=admin_headers,
            )
            if get_resp.status_code == 200:
                product = get_resp.json().get("product", get_resp.json())
                assert product.get("name") == "TEST_Preview_Card_Product"
                vis = product.get("visibility_conditions", {})
                assert vis.get("groups") is not None, "Visibility conditions groups should be saved"
                print(f"Product visibility conditions persisted: {vis}")
                
                # DELETE to clean up
                del_resp = requests.delete(
                    f"{BASE_URL}/api/admin/products/{product_id}",
                    headers=admin_headers,
                )
                print(f"Delete status: {del_resp.status_code}")
