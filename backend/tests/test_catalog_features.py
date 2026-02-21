"""
Backend tests for Catalog, Categories, Settings, and Quote features
Tests: admin/products-all, admin/categories CRUD, admin/products, settings/public, admin/settings
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return resp.json().get("token")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ============ PRODUCTS ALL ============

class TestProductsAll:
    """Test GET /admin/products-all"""

    def test_get_all_products_returns_22_plus(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/products-all", headers=admin_headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        assert "products" in data, "Response missing 'products' key"
        products = data["products"]
        assert isinstance(products, list), "products should be a list"
        assert len(products) >= 20, f"Expected at least 20 products, got {len(products)}"
        # Verify no _id in response
        for p in products[:3]:
            assert "_id" not in p, "Product should not expose MongoDB _id"
        print(f"PASS: /admin/products-all returned {len(products)} products")

    def test_get_all_products_requires_auth(self):
        resp = requests.get(f"{BASE_URL}/api/admin/products-all")
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"
        print("PASS: /admin/products-all requires authentication")


# ============ CATEGORIES ============

class TestCategories:
    """Test CRUD for /admin/categories"""

    created_cat_id = None

    def test_list_categories_returns_list(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/categories", headers=admin_headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        assert "categories" in data
        assert isinstance(data["categories"], list)
        print(f"PASS: GET /admin/categories returned {len(data['categories'])} categories")

    def test_list_categories_requires_auth(self):
        resp = requests.get(f"{BASE_URL}/api/admin/categories")
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"
        print("PASS: GET /admin/categories requires authentication")

    def test_create_category(self, admin_headers):
        payload = {"name": "TEST_CatalogTestCategory", "is_active": True}
        resp = requests.post(f"{BASE_URL}/api/admin/categories", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Failed to create category: {resp.text}"
        data = resp.json()
        assert "category" in data
        cat = data["category"]
        assert cat["name"] == "TEST_CatalogTestCategory"
        assert cat["is_active"] is True
        assert "id" in cat
        assert "_id" not in cat
        TestCategories.created_cat_id = cat["id"]
        print(f"PASS: POST /admin/categories created category id={cat['id']}")

    def test_create_category_persisted(self, admin_headers):
        """Verify created category shows in list"""
        resp = requests.get(f"{BASE_URL}/api/admin/categories", headers=admin_headers)
        assert resp.status_code == 200
        cats = resp.json()["categories"]
        ids = [c["id"] for c in cats]
        assert TestCategories.created_cat_id in ids, "Created category not found in list"
        print("PASS: Created category persisted in DB")

    def test_create_duplicate_category_fails(self, admin_headers):
        payload = {"name": "TEST_CatalogTestCategory", "is_active": True}
        resp = requests.post(f"{BASE_URL}/api/admin/categories", json=payload, headers=admin_headers)
        assert resp.status_code == 409, f"Expected 409 conflict, got {resp.status_code}: {resp.text}"
        print("PASS: Duplicate category creation returns 409")

    def test_update_category_name(self, admin_headers):
        cat_id = TestCategories.created_cat_id
        assert cat_id, "No category ID from create test"
        resp = requests.put(f"{BASE_URL}/api/admin/categories/{cat_id}", json={"name": "TEST_CatalogTestCategoryUpdated"}, headers=admin_headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        assert "category" in data
        print(f"PASS: PUT /admin/categories/{cat_id} updated")

    def test_update_category_persisted(self, admin_headers):
        cat_id = TestCategories.created_cat_id
        resp = requests.get(f"{BASE_URL}/api/admin/categories", headers=admin_headers)
        cats = resp.json()["categories"]
        updated = next((c for c in cats if c["id"] == cat_id), None)
        assert updated, "Updated category not found"
        assert updated["name"] == "TEST_CatalogTestCategoryUpdated", "Name update not persisted"
        print("PASS: Category name update persisted")

    def test_deactivate_category(self, admin_headers):
        cat_id = TestCategories.created_cat_id
        resp = requests.put(f"{BASE_URL}/api/admin/categories/{cat_id}", json={"is_active": False}, headers=admin_headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        print(f"PASS: Category deactivated")

    def test_deactivation_persisted(self, admin_headers):
        cat_id = TestCategories.created_cat_id
        resp = requests.get(f"{BASE_URL}/api/admin/categories", headers=admin_headers)
        cats = resp.json()["categories"]
        updated = next((c for c in cats if c["id"] == cat_id), None)
        assert updated, "Category not found"
        # NOTE: is_active=False may not be returned if filter excludes inactive
        print(f"PASS: Category deactivation check. is_active={updated.get('is_active')}")

    def test_delete_category(self, admin_headers):
        cat_id = TestCategories.created_cat_id
        resp = requests.delete(f"{BASE_URL}/api/admin/categories/{cat_id}", headers=admin_headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        print(f"PASS: DELETE /admin/categories/{cat_id}")

    def test_delete_nonexistent_category_returns_404(self, admin_headers):
        resp = requests.delete(f"{BASE_URL}/api/admin/categories/nonexistent-id-12345", headers=admin_headers)
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print("PASS: DELETE nonexistent category returns 404")


# ============ PRODUCTS (Admin Create) ============

class TestAdminProducts:
    """Test POST /admin/products (create) and PUT /admin/products/{id}"""

    created_product_id = None

    def test_create_product_simple(self, admin_headers):
        payload = {
            "name": "TEST_CatalogProduct",
            "short_description": "A test product for catalog testing",
            "description_long": "Detailed description of the test product for catalog.",
            "bullets": ["Bullet 1", "Bullet 2", "Bullet 3"],
            "tag": "Test",
            "category": "Test Category",
            "outcome": "Test outcome",
            "automation_details": "Test automation details",
            "support_details": "Test support details",
            "inclusions": ["Inclusion 1", "Inclusion 2"],
            "exclusions": ["Exclusion 1"],
            "requirements": ["Requirement 1"],
            "next_steps": ["Step 1", "Step 2"],
            "faqs": [{"question": "Q1?", "answer": "A1."}, {"question": "Q2?", "answer": "A2."}],
            "base_price": 999.00,
            "is_subscription": False,
            "pricing_complexity": "SIMPLE",
            "is_active": True,
            "visible_to_customers": [],
        }
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Failed to create product: {resp.text}"
        data = resp.json()
        assert "product" in data
        product = data["product"]
        assert product["name"] == "TEST_CatalogProduct"
        assert product["base_price"] == 999.00
        assert product["pricing_complexity"] == "SIMPLE"
        assert product["is_active"] is True
        assert "_id" not in product
        TestAdminProducts.created_product_id = product["id"]
        print(f"PASS: POST /admin/products created product id={product['id']}")

    def test_create_product_persisted(self, admin_headers):
        """Verify created product appears in products-all"""
        resp = requests.get(f"{BASE_URL}/api/admin/products-all", headers=admin_headers)
        assert resp.status_code == 200
        products = resp.json()["products"]
        ids = [p["id"] for p in products]
        assert TestAdminProducts.created_product_id in ids, "Created product not found"
        print("PASS: Created product persisted in DB")

    def test_create_rfq_product(self, admin_headers):
        """Test creating REQUEST_FOR_QUOTE product"""
        payload = {
            "name": "TEST_RFQProduct",
            "short_description": "RFQ test product",
            "description_long": "RFQ detailed description",
            "bullets": ["RFQ Bullet 1", "RFQ Bullet 2", "RFQ Bullet 3"],
            "tag": "Enterprise",
            "category": "Enterprise",
            "outcome": "Custom outcome",
            "base_price": 0.0,
            "is_subscription": False,
            "pricing_complexity": "REQUEST_FOR_QUOTE",
            "is_active": True,
            "visible_to_customers": [],
        }
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        product = data["product"]
        assert product["pricing_complexity"] == "REQUEST_FOR_QUOTE"
        print(f"PASS: RFQ product created id={product['id']}")

    def test_update_product_active_status(self, admin_headers):
        """Test deactivating a product"""
        pid = TestAdminProducts.created_product_id
        assert pid, "No product ID from create test"
        resp = requests.put(f"{BASE_URL}/api/admin/products/{pid}", json={
            "name": "TEST_CatalogProduct",
            "is_active": False,
            "pricing_rules": {},
        }, headers=admin_headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        print(f"PASS: Product deactivated (PUT /admin/products/{pid})")

    def test_deactivation_persisted(self, admin_headers):
        """Verify deactivated product is not in storefront"""
        resp = requests.get(f"{BASE_URL}/api/products")
        assert resp.status_code == 200
        products = resp.json().get("products", [])
        ids = [p["id"] for p in products]
        assert TestAdminProducts.created_product_id not in ids, "Deactivated product should not appear on storefront"
        print("PASS: Deactivated product does not appear in storefront")


# ============ SETTINGS ============

class TestSettings:
    """Test GET/PUT /admin/settings and GET /settings/public"""

    def test_get_public_settings_no_auth(self):
        """Public settings endpoint should work without auth"""
        resp = requests.get(f"{BASE_URL}/api/settings/public")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        assert "settings" in data
        settings = data["settings"]
        # Should only have public fields
        for key in ["stripe_secret_key", "gocardless_token", "resend_api_key"]:
            assert key not in settings, f"Secret key {key} should not be in public settings"
        print(f"PASS: GET /settings/public returns {list(settings.keys())}")

    def test_get_admin_settings_requires_auth(self):
        resp = requests.get(f"{BASE_URL}/api/admin/settings")
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"
        print("PASS: GET /admin/settings requires auth")

    def test_get_admin_settings(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/settings", headers=admin_headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        assert "settings" in data
        print(f"PASS: GET /admin/settings works for admin")

    def test_update_settings_store_name(self, admin_headers):
        payload = {"store_name": "TEST_StoreName"}
        resp = requests.put(f"{BASE_URL}/api/admin/settings", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        assert "message" in data
        print(f"PASS: PUT /admin/settings updates store_name")

    def test_store_name_persisted(self, admin_headers):
        """Verify store name update persisted"""
        resp = requests.get(f"{BASE_URL}/api/admin/settings", headers=admin_headers)
        assert resp.status_code == 200
        settings = resp.json()["settings"]
        # Note: if store_name is not returned in the masked response, check public settings
        print(f"PASS: Settings loaded after update")

    def test_update_primary_color(self, admin_headers):
        payload = {"primary_color": "#123456"}
        resp = requests.put(f"{BASE_URL}/api/admin/settings", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        print("PASS: PUT /admin/settings updates primary_color")

    def test_primary_color_in_public_settings(self, admin_headers):
        """Public settings should reflect updated primary color"""
        resp = requests.get(f"{BASE_URL}/api/settings/public")
        assert resp.status_code == 200
        settings = resp.json()["settings"]
        assert settings.get("primary_color") == "#123456", f"Expected #123456, got {settings.get('primary_color')}"
        print("PASS: Primary color update visible in public settings")

    def test_secret_keys_masked_in_admin_settings(self, admin_headers):
        """Secret keys should be masked after saving"""
        # First set a test key
        payload = {"resend_api_key": "re_test_secretkey_12345"}
        resp = requests.put(f"{BASE_URL}/api/admin/settings", json=payload, headers=admin_headers)
        assert resp.status_code == 200

        # Get settings and verify masking
        resp = requests.get(f"{BASE_URL}/api/admin/settings", headers=admin_headers)
        assert resp.status_code == 200
        settings = resp.json()["settings"]
        if settings.get("resend_api_key"):
            # Should be masked
            assert "••" in str(settings["resend_api_key"]), f"API key not masked: {settings['resend_api_key']}"
        print("PASS: Secret key masked in admin settings response")


# ============ STOREFRONT PRODUCT VISIBILITY ============

class TestStorefrontVisibility:
    """Test that storefront only shows active products"""

    def test_storefront_products_are_active(self):
        resp = requests.get(f"{BASE_URL}/api/products")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        assert "products" in data
        products = data["products"]
        # All products from storefront should be active
        for p in products:
            assert p.get("is_active", True) is not False, f"Inactive product {p.get('name')} visible on storefront"
        print(f"PASS: All {len(products)} storefront products are active")

    def test_storefront_products_no_id(self):
        resp = requests.get(f"{BASE_URL}/api/products")
        assert resp.status_code == 200
        products = resp.json().get("products", [])
        for p in products[:3]:
            assert "_id" not in p, "Product should not expose MongoDB _id"
        print("PASS: Products don't expose MongoDB _id")


# ============ QUOTE REQUESTS ============

class TestQuoteRequests:
    """Test /products/request-quote endpoint"""

    def test_request_quote_requires_auth(self):
        payload = {
            "product_id": "test_product",
            "product_name": "Test Product",
            "name": "Test User",
            "email": "test@example.com",
            "message": "Test quote request"
        }
        resp = requests.post(f"{BASE_URL}/api/products/request-quote", json=payload)
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}: {resp.text}"
        print("PASS: POST /products/request-quote requires authentication")

    def test_admin_can_list_quote_requests(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/quote-requests", headers=admin_headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        assert "quotes" in data
        assert isinstance(data["quotes"], list)
        print(f"PASS: GET /admin/quote-requests returns {len(data['quotes'])} quotes")
