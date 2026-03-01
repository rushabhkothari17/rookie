"""
Products Module Tests (Iteration 157)
Tests for: Products list, create, update, status toggle, categories CRUD, audit logs, partner isolation
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
PLATFORM_CODE = "automate-accounts"
PLATFORM_EMAIL = "admin@automateaccounts.local"
PLATFORM_PASS = "ChangeMe123!"
PARTNER_CODE = "liger-inc"
PARTNER_EMAIL = "admin@ligerinc.local"
PARTNER_PASS = "ChangeMe123!"

TEST_PREFIX = "TEST_PROD_157"


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def platform_token():
    """Get platform admin token"""
    res = requests.post(f"{BASE_URL}/api/auth/login", json={
        "partner_code": PLATFORM_CODE,
        "email": PLATFORM_EMAIL,
        "password": PLATFORM_PASS,
    })
    if res.status_code != 200:
        pytest.skip(f"Platform admin login failed: {res.status_code} {res.text}")
    return res.json().get("access_token") or res.json().get("token")


@pytest.fixture(scope="module")
def partner_token():
    """Get partner admin token"""
    res = requests.post(f"{BASE_URL}/api/auth/login", json={
        "partner_code": PARTNER_CODE,
        "email": PARTNER_EMAIL,
        "password": PARTNER_PASS,
    })
    if res.status_code != 200:
        pytest.skip(f"Partner admin login failed: {res.status_code} {res.text}")
    return res.json().get("access_token") or res.json().get("token")


@pytest.fixture(scope="module")
def platform_client(platform_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {platform_token}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def partner_client(partner_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {partner_token}", "Content-Type": "application/json"})
    return s


# ── Health: Auth ──────────────────────────────────────────────────────────────

class TestAuth:
    """Verify auth works for both roles"""

    def test_platform_admin_login(self):
        res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "partner_code": PLATFORM_CODE, "email": PLATFORM_EMAIL, "password": PLATFORM_PASS,
        })
        assert res.status_code == 200, f"Login failed: {res.text}"
        data = res.json()
        assert "access_token" in data or "token" in data

    def test_partner_admin_login(self):
        res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "partner_code": PARTNER_CODE, "email": PARTNER_EMAIL, "password": PARTNER_PASS,
        })
        assert res.status_code == 200, f"Login failed: {res.text}"
        data = res.json()
        assert "access_token" in data or "token" in data

    def test_unauthenticated_products_returns_401(self):
        res = requests.get(f"{BASE_URL}/api/admin/products-all")
        assert res.status_code == 401


# ── Products List ─────────────────────────────────────────────────────────────

class TestProductsList:
    """GET /admin/products-all"""

    def test_list_products_returns_200(self, platform_client):
        res = platform_client.get(f"{BASE_URL}/api/admin/products-all?per_page=500")
        assert res.status_code == 200, f"Got {res.status_code}: {res.text}"

    def test_list_products_has_correct_structure(self, platform_client):
        res = platform_client.get(f"{BASE_URL}/api/admin/products-all?per_page=500")
        assert res.status_code == 200
        data = res.json()
        assert "products" in data
        assert "total" in data
        assert "page" in data
        assert isinstance(data["products"], list)

    def test_list_products_no_mongo_id(self, platform_client):
        """Products must not expose MongoDB _id"""
        res = platform_client.get(f"{BASE_URL}/api/admin/products-all?per_page=10")
        assert res.status_code == 200
        for p in res.json()["products"]:
            assert "_id" not in p, f"MongoDB _id exposed in product: {p.get('id')}"

    def test_list_products_has_expected_fields(self, platform_client):
        res = platform_client.get(f"{BASE_URL}/api/admin/products-all?per_page=20")
        assert res.status_code == 200
        products = res.json()["products"]
        if products:
            p = products[0]
            for field in ["id", "name", "is_active", "is_subscription"]:
                assert field in p, f"Missing field '{field}' in product"

    def test_partner_list_products_returns_200(self, partner_client):
        res = partner_client.get(f"{BASE_URL}/api/admin/products-all?per_page=500")
        assert res.status_code == 200

    def test_search_filter_works(self, platform_client):
        """Searching by name filters results server-side"""
        res = platform_client.get(f"{BASE_URL}/api/admin/products-all?search=xyz_nonexistent_query_abc")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 0 or all("xyz_nonexistent" in p["name"].lower() for p in data["products"])


# ── Create Product ────────────────────────────────────────────────────────────

class TestCreateProduct:
    """POST /admin/products"""

    def test_create_one_time_product(self, platform_client):
        payload = {
            "name": f"{TEST_PREFIX}_OneTime",
            "category": "",
            "description_long": "Test one-time product",
            "bullets": ["Feature 1", "Feature 2"],
            "base_price": 49.99,
            "is_subscription": False,
            "is_active": True,
            "pricing_type": "internal",
            "currency": "USD",
        }
        res = platform_client.post(f"{BASE_URL}/api/admin/products", json=payload)
        assert res.status_code == 200, f"Create failed: {res.text}"
        data = res.json()
        assert "product" in data
        assert data["product"]["name"] == payload["name"]
        assert data["product"]["is_subscription"] is False
        assert data["product"]["base_price"] == 49.99

    def test_create_subscription_product_with_stripe(self, platform_client):
        payload = {
            "name": f"{TEST_PREFIX}_Subscription",
            "category": "",
            "description_long": "Test subscription product",
            "bullets": [],
            "base_price": 99.00,
            "is_subscription": True,
            "stripe_price_id": "price_test_12345",
            "default_term_months": 12,
            "billing_type": "prorata",
            "is_active": True,
            "pricing_type": "internal",
            "currency": "USD",
        }
        res = platform_client.post(f"{BASE_URL}/api/admin/products", json=payload)
        assert res.status_code == 200, f"Create failed: {res.text}"
        data = res.json()
        assert data["product"]["is_subscription"] is True
        assert data["product"]["stripe_price_id"] == "price_test_12345"
        assert data["product"]["billing_type"] == "prorata"

    def test_create_product_with_external_pricing(self, platform_client):
        payload = {
            "name": f"{TEST_PREFIX}_External",
            "category": "",
            "base_price": 0,
            "is_subscription": False,
            "is_active": True,
            "pricing_type": "external",
            "external_url": "https://example.com/buy",
            "currency": "USD",
        }
        res = platform_client.post(f"{BASE_URL}/api/admin/products", json=payload)
        assert res.status_code == 200, f"Create failed: {res.text}"
        data = res.json()
        assert data["product"]["pricing_type"] == "external"
        assert data["product"]["external_url"] == "https://example.com/buy"

    def test_create_product_with_enquiry_pricing(self, platform_client):
        payload = {
            "name": f"{TEST_PREFIX}_Enquiry",
            "category": "",
            "base_price": 0,
            "is_subscription": False,
            "is_active": True,
            "pricing_type": "enquiry",
            "currency": "USD",
        }
        res = platform_client.post(f"{BASE_URL}/api/admin/products", json=payload)
        assert res.status_code == 200, f"Create failed: {res.text}"
        data = res.json()
        assert data["product"]["pricing_type"] == "enquiry"

    def test_create_product_with_visibility_conditions(self, platform_client):
        payload = {
            "name": f"{TEST_PREFIX}_ConditionalVis",
            "category": "",
            "base_price": 0,
            "is_subscription": False,
            "is_active": True,
            "pricing_type": "internal",
            "currency": "USD",
            "visibility_conditions": {
                "top_logic": "AND",
                "groups": [{
                    "logic": "AND",
                    "conditions": [{"field": "country", "operator": "equals", "value": "us"}]
                }]
            }
        }
        res = platform_client.post(f"{BASE_URL}/api/admin/products", json=payload)
        assert res.status_code == 200, f"Create failed: {res.text}"
        data = res.json()
        assert data["product"]["visibility_conditions"] is not None

    def test_create_product_with_store_card(self, platform_client):
        payload = {
            "name": f"{TEST_PREFIX}_StoreCard",
            "category": "",
            "card_tag": "Popular",
            "card_description": "Best seller",
            "card_bullets": ["Bullet A", "Bullet B"],
            "base_price": 29.99,
            "is_subscription": False,
            "is_active": True,
            "pricing_type": "internal",
            "currency": "USD",
        }
        res = platform_client.post(f"{BASE_URL}/api/admin/products", json=payload)
        assert res.status_code == 200, f"Create failed: {res.text}"
        data = res.json()
        assert data["product"]["card_tag"] == "Popular"
        assert data["product"]["card_description"] == "Best seller"
        assert data["product"]["card_bullets"] == ["Bullet A", "Bullet B"]

    def test_partner_can_create_product(self, partner_client):
        payload = {
            "name": f"{TEST_PREFIX}_PartnerProduct",
            "category": "",
            "base_price": 19.99,
            "is_subscription": False,
            "is_active": True,
            "pricing_type": "internal",
            "currency": "USD",
        }
        res = partner_client.post(f"{BASE_URL}/api/admin/products", json=payload)
        assert res.status_code == 200, f"Partner create failed: {res.text}"
        data = res.json()
        assert data["product"]["name"] == payload["name"]


# ── Get Product by ID + Persistence check ─────────────────────────────────────

class TestProductPersistence:
    """Create → list to verify persistence"""

    def test_create_and_verify_in_list(self, platform_client):
        unique_name = f"{TEST_PREFIX}_{uuid.uuid4().hex[:8]}"
        payload = {
            "name": unique_name,
            "category": "",
            "base_price": 75.00,
            "is_subscription": False,
            "is_active": True,
            "pricing_type": "internal",
            "currency": "USD",
        }
        res = platform_client.post(f"{BASE_URL}/api/admin/products", json=payload)
        assert res.status_code == 200
        product_id = res.json()["product"]["id"]

        # Verify via list with search
        list_res = platform_client.get(f"{BASE_URL}/api/admin/products-all?search={unique_name}&per_page=10")
        assert list_res.status_code == 200
        products = list_res.json()["products"]
        ids = [p["id"] for p in products]
        assert product_id in ids, f"Created product {product_id} not found in list"


# ── Update Product ────────────────────────────────────────────────────────────

class TestUpdateProduct:
    """PUT /admin/products/{id}"""

    def test_update_product_name(self, platform_client):
        # Create
        create_res = platform_client.post(f"{BASE_URL}/api/admin/products", json={
            "name": f"{TEST_PREFIX}_UpdateTest",
            "base_price": 10.0,
            "is_subscription": False,
            "is_active": True,
            "pricing_type": "internal",
            "currency": "USD",
        })
        assert create_res.status_code == 200
        product_id = create_res.json()["product"]["id"]

        # Update
        update_res = platform_client.put(f"{BASE_URL}/api/admin/products/{product_id}", json={
            "name": f"{TEST_PREFIX}_UpdateTest_Renamed",
            "is_active": True,
        })
        assert update_res.status_code == 200, f"Update failed: {update_res.text}"

    def test_deactivate_product(self, platform_client):
        # Create active product
        create_res = platform_client.post(f"{BASE_URL}/api/admin/products", json={
            "name": f"{TEST_PREFIX}_ToggleTest",
            "base_price": 10.0,
            "is_subscription": False,
            "is_active": True,
            "pricing_type": "internal",
            "currency": "USD",
        })
        assert create_res.status_code == 200
        product_id = create_res.json()["product"]["id"]

        # Deactivate
        deactivate_res = platform_client.put(f"{BASE_URL}/api/admin/products/{product_id}", json={
            "name": f"{TEST_PREFIX}_ToggleTest",
            "is_active": False,
        })
        assert deactivate_res.status_code == 200, f"Deactivate failed: {deactivate_res.text}"

    def test_update_nonexistent_product_returns_404(self, platform_client):
        res = platform_client.put(f"{BASE_URL}/api/admin/products/nonexistent_id_xyz", json={
            "name": "Test",
            "is_active": True,
        })
        assert res.status_code == 404


# ── Subscription-specific fields ──────────────────────────────────────────────

class TestSubscriptionFields:
    """Verify subscription-specific fields are saved/returned correctly"""

    def test_subscription_fields_persisted(self, platform_client):
        payload = {
            "name": f"{TEST_PREFIX}_SubFields",
            "base_price": 50.0,
            "is_subscription": True,
            "stripe_price_id": "price_testXYZ",
            "default_term_months": 6,
            "billing_type": "fixed",
            "is_active": True,
            "pricing_type": "internal",
            "currency": "USD",
        }
        res = platform_client.post(f"{BASE_URL}/api/admin/products", json=payload)
        assert res.status_code == 200
        product = res.json()["product"]
        assert product["is_subscription"] is True
        assert product["stripe_price_id"] == "price_testXYZ"
        assert product["default_term_months"] == 6
        assert product["billing_type"] == "fixed"

    def test_billing_type_prorata(self, platform_client):
        payload = {
            "name": f"{TEST_PREFIX}_SubProrata",
            "base_price": 30.0,
            "is_subscription": True,
            "stripe_price_id": "price_prorata",
            "billing_type": "prorata",
            "is_active": True,
            "pricing_type": "internal",
            "currency": "USD",
        }
        res = platform_client.post(f"{BASE_URL}/api/admin/products", json=payload)
        assert res.status_code == 200
        assert res.json()["product"]["billing_type"] == "prorata"


# ── Audit Logs ────────────────────────────────────────────────────────────────

class TestProductAuditLogs:
    """GET /admin/products/{id}/logs"""

    def test_product_logs_returns_200(self, platform_client):
        # Create product to get its ID
        create_res = platform_client.post(f"{BASE_URL}/api/admin/products", json={
            "name": f"{TEST_PREFIX}_ForLogs",
            "base_price": 10.0,
            "is_subscription": False,
            "is_active": True,
            "pricing_type": "internal",
            "currency": "USD",
        })
        assert create_res.status_code == 200
        product_id = create_res.json()["product"]["id"]

        res = platform_client.get(f"{BASE_URL}/api/admin/products/{product_id}/logs")
        assert res.status_code == 200, f"Logs failed: {res.text}"
        data = res.json()
        assert "logs" in data
        assert "total" in data

    def test_product_logs_contains_creation_event(self, platform_client):
        # Create product
        create_res = platform_client.post(f"{BASE_URL}/api/admin/products", json={
            "name": f"{TEST_PREFIX}_LogsCreation",
            "base_price": 10.0,
            "is_subscription": False,
            "is_active": True,
            "pricing_type": "internal",
            "currency": "USD",
        })
        assert create_res.status_code == 200
        product_id = create_res.json()["product"]["id"]

        logs_res = platform_client.get(f"{BASE_URL}/api/admin/products/{product_id}/logs")
        assert logs_res.status_code == 200
        logs = logs_res.json()["logs"]
        assert len(logs) >= 1, "Expected at least one audit log (creation) for new product"
        actions = [l.get("action") for l in logs]
        assert "created" in actions, f"Creation log not found. Actions: {actions}"

    def test_product_logs_nonexistent_returns_404(self, platform_client):
        res = platform_client.get(f"{BASE_URL}/api/admin/products/nonexistent_xyz/logs")
        assert res.status_code == 404


# ── Categories CRUD ───────────────────────────────────────────────────────────

class TestCategories:
    """GET/POST/PUT/DELETE /admin/categories"""

    created_cat_id = None

    def test_list_categories_returns_200(self, platform_client):
        res = platform_client.get(f"{BASE_URL}/api/admin/categories")
        assert res.status_code == 200
        data = res.json()
        assert "categories" in data
        assert isinstance(data["categories"], list)

    def test_create_category(self, platform_client):
        unique_name = f"{TEST_PREFIX}_Cat_{uuid.uuid4().hex[:6]}"
        res = platform_client.post(f"{BASE_URL}/api/admin/categories", json={
            "name": unique_name,
            "description": "Test category description",
            "is_active": True,
        })
        assert res.status_code == 200, f"Create category failed: {res.text}"
        data = res.json()
        assert "category" in data
        assert data["category"]["name"] == unique_name
        TestCategories.created_cat_id = data["category"]["id"]

    def test_category_has_id(self, platform_client):
        assert TestCategories.created_cat_id is not None, "Category was not created in previous test"

    def test_update_category(self, platform_client):
        if not TestCategories.created_cat_id:
            pytest.skip("No category to update")
        res = platform_client.put(f"{BASE_URL}/api/admin/categories/{TestCategories.created_cat_id}", json={
            "name": f"{TEST_PREFIX}_CatUpdated",
            "description": "Updated description",
        })
        assert res.status_code == 200, f"Update category failed: {res.text}"

    def test_delete_empty_category(self, platform_client):
        """Can delete a category with no products linked"""
        unique_name = f"{TEST_PREFIX}_CatDel_{uuid.uuid4().hex[:6]}"
        create_res = platform_client.post(f"{BASE_URL}/api/admin/categories", json={
            "name": unique_name,
            "description": "To delete",
            "is_active": True,
        })
        assert create_res.status_code == 200
        cat_id = create_res.json()["category"]["id"]

        del_res = platform_client.delete(f"{BASE_URL}/api/admin/categories/{cat_id}")
        assert del_res.status_code == 200, f"Delete failed: {del_res.text}"

    def test_delete_nonexistent_category_returns_404(self, platform_client):
        res = platform_client.delete(f"{BASE_URL}/api/admin/categories/nonexistent_cat_xyz")
        assert res.status_code == 404

    def test_duplicate_category_returns_409(self, platform_client):
        if not TestCategories.created_cat_id:
            pytest.skip("No category reference available")
        # Attempt to create category with same name as updated one
        res = platform_client.post(f"{BASE_URL}/api/admin/categories", json={
            "name": f"{TEST_PREFIX}_CatUpdated",
            "description": "Duplicate",
            "is_active": True,
        })
        assert res.status_code == 409, f"Expected 409 conflict, got {res.status_code}"

    def test_category_logs_returns_200(self, platform_client):
        if not TestCategories.created_cat_id:
            pytest.skip("No category to get logs for")
        res = platform_client.get(f"{BASE_URL}/api/admin/categories/{TestCategories.created_cat_id}/logs")
        assert res.status_code == 200
        data = res.json()
        assert "logs" in data

    def test_partner_list_categories(self, partner_client):
        res = partner_client.get(f"{BASE_URL}/api/admin/categories")
        assert res.status_code == 200


# ── Partner Isolation ─────────────────────────────────────────────────────────

class TestPartnerIsolation:
    """Partner admin can only see their own products"""

    def test_partner_cannot_see_platform_products(self, platform_client, partner_client):
        # Create a product as platform admin (not tagged to liger-inc)
        create_res = platform_client.post(f"{BASE_URL}/api/admin/products", json={
            "name": f"{TEST_PREFIX}_PlatformOnly",
            "base_price": 100.0,
            "is_subscription": False,
            "is_active": True,
            "pricing_type": "internal",
            "currency": "USD",
        })
        assert create_res.status_code == 200
        platform_product_id = create_res.json()["product"]["id"]

        # Partner admin fetches their products
        partner_res = partner_client.get(f"{BASE_URL}/api/admin/products-all?per_page=500")
        assert partner_res.status_code == 200
        partner_product_ids = [p["id"] for p in partner_res.json()["products"]]
        # Partner should NOT see the platform-created product (different tenant)
        assert platform_product_id not in partner_product_ids, \
            "Partner admin can see platform admin's product - tenant isolation broken!"

    def test_partner_created_product_visible_to_partner(self, partner_client):
        """Products created by partner admin appear in their list"""
        create_res = partner_client.post(f"{BASE_URL}/api/admin/products", json={
            "name": f"{TEST_PREFIX}_PartnerOwned",
            "base_price": 25.0,
            "is_subscription": False,
            "is_active": True,
            "pricing_type": "internal",
            "currency": "USD",
        })
        assert create_res.status_code == 200
        partner_product_id = create_res.json()["product"]["id"]

        list_res = partner_client.get(f"{BASE_URL}/api/admin/products-all?per_page=500")
        assert list_res.status_code == 200
        ids = [p["id"] for p in list_res.json()["products"]]
        assert partner_product_id in ids, "Partner's own product not visible in their list"

    def test_platform_admin_sees_partner_code_in_products(self, platform_client, partner_client):
        """Platform admin can see partner_code on products"""
        # Create product as partner
        create_res = partner_client.post(f"{BASE_URL}/api/admin/products", json={
            "name": f"{TEST_PREFIX}_PartnerTagged",
            "base_price": 15.0,
            "is_subscription": False,
            "is_active": True,
            "pricing_type": "internal",
            "currency": "USD",
        })
        assert create_res.status_code == 200
        partner_product_id = create_res.json()["product"]["id"]

        # Platform admin lists all products and finds partner_code
        list_res = platform_client.get(f"{BASE_URL}/api/admin/products-all?per_page=500")
        assert list_res.status_code == 200
        products = list_res.json()["products"]
        partner_products = [p for p in products if p.get("id") == partner_product_id]
        if partner_products:
            p = partner_products[0]
            # platform admin should see partner_code
            assert "partner_code" in p, f"partner_code not present in product for platform admin. Product: {p}"


# ── Export CSV ────────────────────────────────────────────────────────────────

class TestExportCsv:
    """GET /admin/export/catalog"""

    def test_export_catalog_csv_returns_200(self, platform_client):
        res = platform_client.get(f"{BASE_URL}/api/admin/export/catalog")
        assert res.status_code == 200, f"CSV export failed: {res.text}"

    def test_export_csv_content_type(self, platform_client):
        res = platform_client.get(f"{BASE_URL}/api/admin/export/catalog")
        assert res.status_code == 200
        ct = res.headers.get("content-type", "")
        assert "csv" in ct.lower() or "text" in ct.lower() or "octet-stream" in ct.lower(), \
            f"Unexpected content-type: {ct}"
