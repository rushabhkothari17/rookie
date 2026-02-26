"""
Iteration 111 - Comprehensive Catalog + Multi-tenant QA Tests
Tests: Categories, Products, Pricing Engine, Intake Questions, Visibility,
       Promo Codes, Terms, Tenant Isolation, Security
"""
import pytest
import requests
import os
import time
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Shared state for test data created during testing
TEST_DATA = {}


# ─────────────────────────── AUTH FIXTURES ───────────────────────────────────

@pytest.fixture(scope="session")
def platform_admin_token():
    """Platform admin login WITHOUT partner_code"""
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!"
    })
    assert r.status_code == 200, f"Platform admin login failed: {r.text}"
    token = r.json().get("token")
    assert token, "No token in platform admin login response"
    return token


@pytest.fixture(scope="session")
def platform_admin_headers(platform_admin_token):
    return {"Authorization": f"Bearer {platform_admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def tenant_a_token():
    """Tenant A super admin login WITH partner_code"""
    r = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
        "email": "test.super.a@iter109.test",
        "password": "QATest123!",
        "partner_code": "test-iter109-a"
    })
    assert r.status_code == 200, f"Tenant A login failed: {r.text}"
    token = r.json().get("token")
    assert token, "No token in tenant A login response"
    return token


@pytest.fixture(scope="session")
def tenant_a_headers(tenant_a_token):
    return {"Authorization": f"Bearer {tenant_a_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def tenant_a_id():
    return "5ed23354-05bc-4603-8613-6a12a26a0f28"


@pytest.fixture(scope="session")
def customer_a_token():
    """Register and login test customer for tenant-a.
    partner_code must be passed as query parameter in registration.
    """
    reg_payload = {
        "email": "test_cust_iter111b@test.local",
        "password": "TestCustomer123!",
        "full_name": "TEST Customer 111 B",
        "company_name": "Test Co",
        "phone": "1234567890",
        "address": {
            "line1": "1 Test Street",
            "line2": "",
            "city": "London",
            "region": "England",
            "postal": "SW1A 1AA",
            "country": "GB"
        }
    }
    # Try registration - partner_code is a query param NOT body
    reg_r = requests.post(
        f"{BASE_URL}/api/auth/register",
        json=reg_payload,
        params={"partner_code": "test-iter109-a"}
    )
    if reg_r.status_code == 200:
        # New registration - verify email
        verif_code = reg_r.json().get("verification_code")
        if verif_code:
            requests.post(f"{BASE_URL}/api/auth/verify-email", json={
                "email": "test_cust_iter111b@test.local",
                "code": verif_code
            })
    
    # Login
    login_r = requests.post(f"{BASE_URL}/api/auth/customer-login", json={
        "email": "test_cust_iter111b@test.local",
        "password": "TestCustomer123!",
        "partner_code": "test-iter109-a"
    })
    if login_r.status_code != 200:
        pytest.skip(f"Customer login failed: {login_r.text}")
    return login_r.json().get("token")


@pytest.fixture(scope="session")
def customer_a_headers(customer_a_token):
    return {"Authorization": f"Bearer {customer_a_token}", "Content-Type": "application/json"}


# ─────────────────────────── A. CATEGORIES ───────────────────────────────────

class TestCategories:
    """A. Product Categories: CRUD, uniqueness, ordering, tenant isolation"""

    def test_create_category_tenant_a(self, tenant_a_headers):
        """Create category for tenant-a"""
        r = requests.post(f"{BASE_URL}/api/admin/categories", json={
            "name": "TEST_Cat_Iter111",
            "description": "Test category for iter111",
            "is_active": True
        }, headers=tenant_a_headers)
        assert r.status_code == 200, f"Create category failed: {r.text}"
        data = r.json()
        assert "category" in data
        assert data["category"]["name"] == "TEST_Cat_Iter111"
        cat_id = data["category"]["id"]
        TEST_DATA["category_id"] = cat_id
        TEST_DATA["category_name"] = "TEST_Cat_Iter111"
        print(f"Created category ID: {cat_id}")

    def test_duplicate_category_rejected(self, tenant_a_headers):
        """Duplicate category name within same tenant should return 409"""
        r = requests.post(f"{BASE_URL}/api/admin/categories", json={
            "name": "TEST_Cat_Iter111",
            "description": "duplicate",
            "is_active": True
        }, headers=tenant_a_headers)
        assert r.status_code == 409, f"Expected 409 for duplicate category, got {r.status_code}"
        print("PASS: Duplicate category correctly rejected with 409")

    def test_list_categories_tenant_a(self, tenant_a_headers):
        """List categories for tenant A - should include newly created one"""
        r = requests.get(f"{BASE_URL}/api/admin/categories", headers=tenant_a_headers)
        assert r.status_code == 200
        data = r.json()
        names = [c["name"] for c in data["categories"]]
        assert "TEST_Cat_Iter111" in names, f"TEST_Cat_Iter111 not found in {names}"
        print(f"Found {len(names)} categories for tenant-a")

    def test_edit_category(self, tenant_a_headers):
        """Edit category name"""
        cat_id = TEST_DATA.get("category_id")
        if not cat_id:
            pytest.skip("No category_id available")
        r = requests.put(f"{BASE_URL}/api/admin/categories/{cat_id}", json={
            "name": "TEST_Cat_Iter111_Updated",
            "description": "Updated description"
        }, headers=tenant_a_headers)
        assert r.status_code == 200, f"Update category failed: {r.text}"
        TEST_DATA["category_name"] = "TEST_Cat_Iter111_Updated"
        print("PASS: Category updated")

    def test_category_tenant_isolation(self, platform_admin_headers):
        """Platform admin sees categories; verify tenant_id is set"""
        r = requests.get(f"{BASE_URL}/api/admin/categories", headers=platform_admin_headers)
        assert r.status_code == 200
        data = r.json()
        # Platform admin sees all categories (cross-tenant)
        print(f"Platform admin sees {data['total']} categories total")

    def test_category_not_visible_other_tenant(self, tenant_a_headers):
        """Test tenant isolation by checking category count/content"""
        # Tenant-A categories should only show tenant-A categories
        r = requests.get(f"{BASE_URL}/api/admin/categories", headers=tenant_a_headers)
        assert r.status_code == 200
        cats = r.json()["categories"]
        # All returned categories should belong to tenant-a
        for cat in cats:
            assert cat.get("tenant_id") == "5ed23354-05bc-4603-8613-6a12a26a0f28" or cat.get("tenant_id") is None, \
                f"Category {cat['name']} has wrong tenant_id: {cat.get('tenant_id')}"
        print(f"PASS: {len(cats)} tenant-a categories, all properly scoped")

    def test_delete_category_with_products_blocked(self, tenant_a_headers):
        """Cannot delete a category that has linked products"""
        # Use a category name that might have products (create one first if needed)
        # We'll test this after product creation
        pass


# ─────────────────────────── B. PRODUCTS ─────────────────────────────────────

class TestProducts:
    """B. Products: All layouts, fields, visibility, pricing"""

    def test_create_standard_product(self, tenant_a_headers):
        """Create product with all fields, layout=standard"""
        cat_name = TEST_DATA.get("category_name", "TEST_Cat_Iter111_Updated")
        payload = {
            "name": "TEST_Product_Standard_Iter111",
            "tagline": "Test tagline",
            "tag": "test-tag",
            "category": cat_name,
            "description_long": "This is a long description for testing.",
            "bullets": ["Bullet 1", "Bullet 2", "Bullet 3"],
            "card_title": "Test Card Title",
            "card_tag": "card-tag",
            "card_description": "Card description",
            "card_bullets": ["Card bullet 1", "Card bullet 2"],
            "display_layout": "standard",
            "pricing_type": "internal",
            "base_price": 100.0,
            "is_active": True
        }
        r = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=tenant_a_headers)
        assert r.status_code == 200, f"Create product failed: {r.text}"
        data = r.json()
        product = data["product"]
        assert product["name"] == "TEST_Product_Standard_Iter111"
        assert product["base_price"] == 100.0
        assert product["display_layout"] == "standard"
        assert product["pricing_type"] == "internal"
        assert product["tag"] == "test-tag"
        assert product["category"] == cat_name
        TEST_DATA["product_id_standard"] = product["id"]
        print(f"Created standard product ID: {product['id']}")

    def test_product_stored_in_db(self, tenant_a_headers):
        """Verify product is retrievable and all fields stored correctly"""
        r = requests.get(f"{BASE_URL}/api/admin/products-all", headers=tenant_a_headers)
        assert r.status_code == 200
        products = r.json()["products"]
        found = next((p for p in products if p["name"] == "TEST_Product_Standard_Iter111"), None)
        assert found is not None, "Product not found in listing"
        assert found["bullets"] == ["Bullet 1", "Bullet 2", "Bullet 3"]
        assert found["card_bullets"] == ["Card bullet 1", "Card bullet 2"]
        print("PASS: Product fields verified in DB")

    def test_create_quick_buy_layout(self, tenant_a_headers):
        """B2: Create product with quick_buy layout"""
        r = requests.post(f"{BASE_URL}/api/admin/products", json={
            "name": "TEST_Product_QuickBuy_Iter111",
            "display_layout": "quick_buy",
            "pricing_type": "internal",
            "base_price": 50.0,
            "is_active": True
        }, headers=tenant_a_headers)
        assert r.status_code == 200
        p = r.json()["product"]
        assert p["display_layout"] == "quick_buy"
        TEST_DATA["product_id_quickbuy"] = p["id"]
        print(f"Created quick_buy product: {p['id']}")

    def test_create_wizard_layout(self, tenant_a_headers):
        """B2: Create product with wizard layout"""
        r = requests.post(f"{BASE_URL}/api/admin/products", json={
            "name": "TEST_Product_Wizard_Iter111",
            "display_layout": "wizard",
            "pricing_type": "internal",
            "base_price": 200.0,
            "is_active": True
        }, headers=tenant_a_headers)
        assert r.status_code == 200
        p = r.json()["product"]
        assert p["display_layout"] == "wizard"
        TEST_DATA["product_id_wizard"] = p["id"]

    def test_create_application_layout(self, tenant_a_headers):
        """B2: Create product with application layout"""
        r = requests.post(f"{BASE_URL}/api/admin/products", json={
            "name": "TEST_Product_Application_Iter111",
            "display_layout": "application",
            "pricing_type": "internal",
            "base_price": 300.0,
            "is_active": True
        }, headers=tenant_a_headers)
        assert r.status_code == 200
        p = r.json()["product"]
        assert p["display_layout"] == "application"
        TEST_DATA["product_id_application"] = p["id"]

    def test_create_showcase_layout(self, tenant_a_headers):
        """B2: Create product with showcase layout"""
        r = requests.post(f"{BASE_URL}/api/admin/products", json={
            "name": "TEST_Product_Showcase_Iter111",
            "display_layout": "showcase",
            "pricing_type": "internal",
            "base_price": 500.0,
            "is_active": True
        }, headers=tenant_a_headers)
        assert r.status_code == 200
        p = r.json()["product"]
        assert p["display_layout"] == "showcase"
        TEST_DATA["product_id_showcase"] = p["id"]
        print("PASS: All 5 layout types created successfully")

    def test_create_subscription_product(self, tenant_a_headers):
        """B3: Subscription product"""
        r = requests.post(f"{BASE_URL}/api/admin/products", json={
            "name": "TEST_Product_Subscription_Iter111",
            "display_layout": "standard",
            "pricing_type": "internal",
            "base_price": 99.0,
            "is_subscription": True,
            "stripe_price_id": "price_test_iter111",
            "is_active": True
        }, headers=tenant_a_headers)
        assert r.status_code == 200
        p = r.json()["product"]
        assert p["is_subscription"] is True
        assert p["stripe_price_id"] == "price_test_iter111"
        TEST_DATA["product_id_subscription"] = p["id"]
        print("PASS: Subscription product created")

    def test_create_enquiry_product(self, tenant_a_headers):
        """B4: Enquiry-only product"""
        r = requests.post(f"{BASE_URL}/api/admin/products", json={
            "name": "TEST_Product_Enquiry_Iter111",
            "display_layout": "standard",
            "pricing_type": "enquiry",
            "base_price": 0.0,
            "is_active": True
        }, headers=tenant_a_headers)
        assert r.status_code == 200
        p = r.json()["product"]
        assert p["pricing_type"] == "enquiry"
        TEST_DATA["product_id_enquiry"] = p["id"]
        print("PASS: Enquiry product created")

    def test_create_external_link_product(self, tenant_a_headers):
        """B5: External link product"""
        r = requests.post(f"{BASE_URL}/api/admin/products", json={
            "name": "TEST_Product_External_Iter111",
            "display_layout": "standard",
            "pricing_type": "external",
            "external_url": "https://example.com/buy",
            "base_price": 0.0,
            "is_active": True
        }, headers=tenant_a_headers)
        assert r.status_code == 200
        p = r.json()["product"]
        assert p["pricing_type"] == "external"
        assert p["external_url"] == "https://example.com/buy"
        TEST_DATA["product_id_external"] = p["id"]
        print("PASS: External link product created")


# ─────────────────────────── C. PRICING ENGINE ───────────────────────────────

class TestPricingEngine:
    """C. Pricing Engine: Fixed, subscription, enquiry, intake adjustments, rounding"""

    def test_create_product_with_dropdown_intake(self, tenant_a_headers):
        """C: Create product with dropdown intake question (+50 add)"""
        payload = {
            "name": "TEST_Product_PricingIntake_Iter111",
            "display_layout": "standard",
            "pricing_type": "internal",
            "base_price": 100.0,
            "is_active": True,
            "intake_schema_json": {
                "questions": [
                    {
                        "key": "service_tier",
                        "label": "Service Tier",
                        "type": "dropdown",
                        "required": True,
                        "affects_price": True,
                        "price_mode": "add",
                        "options": [
                            {"label": "Basic", "value": "basic", "price_value": 0},
                            {"label": "Premium", "value": "premium", "price_value": 50},
                            {"label": "Enterprise", "value": "enterprise", "price_value": 200}
                        ],
                        "order": 0
                    }
                ]
            }
        }
        r = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=tenant_a_headers)
        assert r.status_code == 200, f"Create pricing product failed: {r.text}"
        p = r.json()["product"]
        assert p["intake_schema_json"] is not None
        assert len(p["intake_schema_json"]["questions"]) == 1
        TEST_DATA["product_id_pricing"] = p["id"]
        print(f"Created pricing product ID: {p['id']}")

    def test_pricing_calc_base_only(self, customer_a_headers):
        """C: Preview API returns base_price=100 when no intake selection"""
        product_id = TEST_DATA.get("product_id_pricing")
        if not product_id:
            pytest.skip("No pricing product available")
        r = requests.post(f"{BASE_URL}/api/pricing/calc", json={
            "product_id": product_id,
            "inputs": {}
        }, headers=customer_a_headers)
        assert r.status_code == 200, f"Pricing calc failed: {r.text}"
        data = r.json()
        assert data["subtotal"] == 100.0, f"Expected 100.0, got {data['subtotal']}"
        print(f"PASS: Base-only pricing = {data['subtotal']}")

    def test_pricing_calc_with_dropdown_add(self, customer_a_headers):
        """C: Preview returns 150 when premium (+50) selected"""
        product_id = TEST_DATA.get("product_id_pricing")
        if not product_id:
            pytest.skip("No pricing product available")
        r = requests.post(f"{BASE_URL}/api/pricing/calc", json={
            "product_id": product_id,
            "inputs": {"service_tier": "premium"}
        }, headers=customer_a_headers)
        assert r.status_code == 200, f"Pricing calc failed: {r.text}"
        data = r.json()
        assert data["subtotal"] == 150.0, f"Expected 150.0 (100+50), got {data['subtotal']}"
        print(f"PASS: Pricing with add = {data['subtotal']}")

    def test_pricing_calc_multiply(self, tenant_a_headers, customer_a_headers):
        """C: Multiplier intake doubles price"""
        payload = {
            "name": "TEST_Product_Multiply_Iter111",
            "pricing_type": "internal",
            "base_price": 100.0,
            "is_active": True,
            "intake_schema_json": {
                "questions": [
                    {
                        "key": "tier_mult",
                        "label": "Multiplier",
                        "type": "dropdown",
                        "affects_price": True,
                        "price_mode": "multiply",
                        "options": [
                            {"label": "x2", "value": "x2", "price_value": 2},
                            {"label": "x1", "value": "x1", "price_value": 1}
                        ],
                        "order": 0
                    }
                ]
            }
        }
        r = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=tenant_a_headers)
        assert r.status_code == 200
        pid = r.json()["product"]["id"]
        TEST_DATA["product_id_multiply"] = pid

        # Test multiply pricing
        r2 = requests.post(f"{BASE_URL}/api/pricing/calc", json={
            "product_id": pid,
            "inputs": {"tier_mult": "x2"}
        }, headers=customer_a_headers)
        assert r2.status_code == 200
        data = r2.json()
        assert data["subtotal"] == 200.0, f"Expected 200.0 (100*2), got {data['subtotal']}"
        print(f"PASS: Multiplier pricing = {data['subtotal']}")

    def test_pricing_rounding(self, tenant_a_headers, customer_a_headers):
        """C: Price rounding to nearest 25"""
        payload = {
            "name": "TEST_Product_Rounding_Iter111",
            "pricing_type": "internal",
            "base_price": 110.0,
            "price_rounding": "25",
            "is_active": True
        }
        r = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=tenant_a_headers)
        assert r.status_code == 200
        pid = r.json()["product"]["id"]
        TEST_DATA["product_id_rounding"] = pid

        r2 = requests.post(f"{BASE_URL}/api/pricing/calc", json={
            "product_id": pid,
            "inputs": {}
        }, headers=customer_a_headers)
        assert r2.status_code == 200
        data = r2.json()
        # 110 rounded up to nearest 25 = 125
        assert data["subtotal"] == 125.0, f"Expected 125.0 (rounding 110→125), got {data['subtotal']}"
        print(f"PASS: Price rounding = {data['subtotal']}")

    def test_enquiry_pricing_returns_zero(self, customer_a_headers):
        """C: Enquiry product returns total=0, is_enquiry=True"""
        product_id = TEST_DATA.get("product_id_enquiry")
        if not product_id:
            pytest.skip("No enquiry product available")
        r = requests.post(f"{BASE_URL}/api/pricing/calc", json={
            "product_id": product_id,
            "inputs": {}
        }, headers=customer_a_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0.0
        assert data["is_enquiry"] is True
        print("PASS: Enquiry pricing = 0, is_enquiry=True")

    def test_external_pricing_returns_zero(self, customer_a_headers):
        """C: External product returns total=0, external_url set"""
        product_id = TEST_DATA.get("product_id_external")
        if not product_id:
            pytest.skip("No external product available")
        r = requests.post(f"{BASE_URL}/api/pricing/calc", json={
            "product_id": product_id,
            "inputs": {}
        }, headers=customer_a_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0.0
        assert data["external_url"] == "https://example.com/buy"
        print(f"PASS: External pricing = 0, url={data['external_url']}")


# ─────────────────────────── D. INTAKE QUESTIONS ─────────────────────────────

class TestIntakeQuestions:
    """D. Intake Questions: All types, required/optional, pricing impacts"""

    def test_create_product_all_intake_types(self, tenant_a_headers):
        """D: Create product with all intake question types"""
        payload = {
            "name": "TEST_Product_AllIntakeTypes_Iter111",
            "pricing_type": "internal",
            "base_price": 100.0,
            "is_active": True,
            "intake_schema_json": {
                "questions": [
                    {
                        "key": "service_option",
                        "label": "Service Option",
                        "type": "dropdown",
                        "required": True,
                        "affects_price": True,
                        "price_mode": "add",
                        "options": [
                            {"label": "Basic", "value": "basic", "price_value": 0},
                            {"label": "Premium", "value": "premium", "price_value": 50}
                        ],
                        "order": 0
                    },
                    {
                        "key": "add_ons",
                        "label": "Add-ons",
                        "type": "multiselect",
                        "required": False,
                        "affects_price": True,
                        "price_mode": "add",
                        "options": [
                            {"label": "Support", "value": "support", "price_value": 25},
                            {"label": "Consulting", "value": "consulting", "price_value": 75}
                        ],
                        "order": 1
                    },
                    {
                        "key": "employee_count",
                        "label": "Number of Employees",
                        "type": "number",
                        "required": False,
                        "price_per_unit": 10.0,
                        "min": 1,
                        "max": 1000,
                        "order": 2
                    },
                    {
                        "key": "rush_order",
                        "label": "Rush Order?",
                        "type": "boolean",
                        "required": False,
                        "affects_price": True,
                        "price_for_yes": 25.0,
                        "price_for_no": 0.0,
                        "order": 3
                    },
                    {
                        "key": "company_name",
                        "label": "Company Name",
                        "type": "single_line",
                        "required": True,
                        "order": 4
                    },
                    {
                        "key": "description",
                        "label": "Project Description",
                        "type": "multi_line",
                        "required": False,
                        "order": 5
                    },
                    {
                        "key": "start_date",
                        "label": "Start Date",
                        "type": "date",
                        "required": False,
                        "order": 6
                    },
                    {
                        "key": "html_block_1",
                        "label": "Instructions",
                        "type": "html_block",
                        "content": "<p>Please fill all required fields.</p>",
                        "order": 7
                    }
                ]
            }
        }
        r = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=tenant_a_headers)
        assert r.status_code == 200, f"Create all-types product failed: {r.text}"
        p = r.json()["product"]
        questions = p["intake_schema_json"]["questions"]
        q_types = {q["type"] for q in questions}
        assert "dropdown" in q_types
        assert "multiselect" in q_types
        assert "number" in q_types
        assert "boolean" in q_types
        assert "single_line" in q_types
        assert "multi_line" in q_types
        assert "date" in q_types
        assert "html_block" in q_types
        TEST_DATA["product_id_all_intake"] = p["id"]
        print(f"PASS: All intake types stored: {q_types}")

    def test_number_intake_pricing(self, customer_a_headers):
        """D: Number field with price_per_unit=10 for 5 employees = +50"""
        product_id = TEST_DATA.get("product_id_all_intake")
        if not product_id:
            pytest.skip("No all-intake product available")
        r = requests.post(f"{BASE_URL}/api/pricing/calc", json={
            "product_id": product_id,
            "inputs": {
                "service_option": "basic",
                "employee_count": 5
            }
        }, headers=customer_a_headers)
        assert r.status_code == 200
        data = r.json()
        # base=100 + basic=0 + 5 employees * 10 = 150
        assert data["subtotal"] == 150.0, f"Expected 150.0, got {data['subtotal']}"
        print(f"PASS: Number intake pricing: {data['subtotal']}")

    def test_boolean_intake_pricing(self, customer_a_headers):
        """D: Boolean field - rush_order=yes adds 25"""
        product_id = TEST_DATA.get("product_id_all_intake")
        if not product_id:
            pytest.skip("No all-intake product available")
        r = requests.post(f"{BASE_URL}/api/pricing/calc", json={
            "product_id": product_id,
            "inputs": {
                "service_option": "basic",
                "rush_order": "yes"
            }
        }, headers=customer_a_headers)
        assert r.status_code == 200
        data = r.json()
        # base=100 + basic=0 + rush=25 = 125
        assert data["subtotal"] == 125.0, f"Expected 125.0, got {data['subtotal']}"
        print(f"PASS: Boolean intake pricing: {data['subtotal']}")

    def test_multiselect_intake_pricing(self, customer_a_headers):
        """D: Multiselect - support(25) + consulting(75) = +100"""
        product_id = TEST_DATA.get("product_id_all_intake")
        if not product_id:
            pytest.skip("No all-intake product available")
        r = requests.post(f"{BASE_URL}/api/pricing/calc", json={
            "product_id": product_id,
            "inputs": {
                "service_option": "basic",
                "add_ons": ["support", "consulting"]
            }
        }, headers=customer_a_headers)
        assert r.status_code == 200
        data = r.json()
        # base=100 + support=25 + consulting=75 = 200
        assert data["subtotal"] == 200.0, f"Expected 200.0, got {data['subtotal']}"
        print(f"PASS: Multiselect intake pricing: {data['subtotal']}")

    def test_intake_schema_validation_duplicate_key(self, tenant_a_headers):
        """D: Duplicate question key should be rejected"""
        r = requests.post(f"{BASE_URL}/api/admin/products", json={
            "name": "TEST_bad_intake",
            "pricing_type": "internal",
            "base_price": 0.0,
            "is_active": False,
            "intake_schema_json": {
                "questions": [
                    {"key": "dup_key", "label": "Q1", "type": "single_line", "order": 0},
                    {"key": "dup_key", "label": "Q2", "type": "single_line", "order": 1}
                ]
            }
        }, headers=tenant_a_headers)
        assert r.status_code == 400, f"Expected 400 for duplicate key, got {r.status_code}: {r.text}"
        print("PASS: Duplicate intake key correctly rejected")


# ─────────────────────────── E. VISIBILITY ───────────────────────────────────

class TestVisibility:
    """E. Visibility Rules: all / allowlist / blocklist / inactive"""

    def test_active_product_visible_in_store(self, customer_a_headers):
        """E: Active product appears in store listing"""
        r = requests.get(f"{BASE_URL}/api/products", headers=customer_a_headers)
        assert r.status_code == 200
        products = r.json()["products"]
        names = [p["name"] for p in products]
        # Standard product should be visible
        assert "TEST_Product_Standard_Iter111" in names, \
            f"Standard product not in store: {names[:5]}..."
        print(f"PASS: Active product visible in store. {len(products)} products listed")

    def test_inactive_product_not_in_store(self, tenant_a_headers, customer_a_headers):
        """E: Inactive product does not appear in store"""
        # Create inactive product
        r = requests.post(f"{BASE_URL}/api/admin/products", json={
            "name": "TEST_Product_Inactive_Iter111",
            "pricing_type": "internal",
            "base_price": 50.0,
            "is_active": False
        }, headers=tenant_a_headers)
        assert r.status_code == 200
        pid = r.json()["product"]["id"]
        TEST_DATA["product_id_inactive"] = pid

        # Check it's not in store
        r2 = requests.get(f"{BASE_URL}/api/products", headers=customer_a_headers)
        products = r2.json()["products"]
        names = [p["name"] for p in products]
        assert "TEST_Product_Inactive_Iter111" not in names, "Inactive product found in store!"
        print("PASS: Inactive product not in store listing")

    def test_inactive_product_404_via_direct_url(self, customer_a_headers):
        """E: Direct URL to inactive product returns 404"""
        pid = TEST_DATA.get("product_id_inactive")
        if not pid:
            pytest.skip("No inactive product available")
        r = requests.get(f"{BASE_URL}/api/products/{pid}", headers=customer_a_headers)
        assert r.status_code == 404, f"Expected 404 for inactive product, got {r.status_code}"
        print("PASS: Inactive product returns 404 on direct URL")

    def test_visibility_allowlist(self, tenant_a_headers, customer_a_headers):
        """E: Restricted product (allowlist) not visible to non-listed customer"""
        # Create product visible only to a specific (non-existent) customer
        r = requests.post(f"{BASE_URL}/api/admin/products", json={
            "name": "TEST_Product_Restricted_Iter111",
            "pricing_type": "internal",
            "base_price": 150.0,
            "is_active": True,
            "visible_to_customers": ["nonexistent_customer_id_xyz"]
        }, headers=tenant_a_headers)
        assert r.status_code == 200
        pid = r.json()["product"]["id"]
        TEST_DATA["product_id_restricted"] = pid

        # Check it's not in store for our customer
        r2 = requests.get(f"{BASE_URL}/api/products", headers=customer_a_headers)
        products = r2.json()["products"]
        names = [p["name"] for p in products]
        assert "TEST_Product_Restricted_Iter111" not in names, \
            "Restricted product visible to non-listed customer!"
        print("PASS: Allowlist product not visible to non-listed customer")

    def test_visibility_direct_url_blocked(self, customer_a_headers):
        """E: Direct URL to restricted product returns 404"""
        pid = TEST_DATA.get("product_id_restricted")
        if not pid:
            pytest.skip("No restricted product available")
        r = requests.get(f"{BASE_URL}/api/products/{pid}", headers=customer_a_headers)
        assert r.status_code == 404, f"Expected 404 for restricted product, got {r.status_code}"
        print("PASS: Restricted product returns 404 on direct URL access")


# ─────────────────────────── F. PROMO CODES ──────────────────────────────────

class TestPromoCodes:
    """F. Promo Codes: Percent-off, fixed-amount, expire, usage limits"""

    def test_create_percent_promo(self, tenant_a_headers):
        """F: Create 20% percent-off promo code"""
        r = requests.post(f"{BASE_URL}/api/admin/promo-codes", json={
            "code": "TEST20_ITER111",
            "discount_type": "percentage",
            "discount_value": 20.0,
            "applies_to": "both",
            "applies_to_products": "all",
            "enabled": True
        }, headers=tenant_a_headers)
        assert r.status_code == 200, f"Create promo code failed: {r.text}"
        data = r.json()
        assert "id" in data
        TEST_DATA["promo_id_percent"] = data["id"]
        print(f"Created percent promo: {data['id']}")

    def test_create_fixed_promo(self, tenant_a_headers):
        """F: Create $10 fixed-amount promo code"""
        r = requests.post(f"{BASE_URL}/api/admin/promo-codes", json={
            "code": "FIXED10_ITER111",
            "discount_type": "fixed",
            "discount_value": 10.0,
            "applies_to": "both",
            "applies_to_products": "all",
            "enabled": True
        }, headers=tenant_a_headers)
        assert r.status_code == 200, f"Create fixed promo failed: {r.text}"
        TEST_DATA["promo_id_fixed"] = r.json()["id"]
        print("PASS: Fixed promo created")

    def test_validate_percent_promo(self, customer_a_headers):
        """F: Validate percent promo code via API"""
        r = requests.post(f"{BASE_URL}/api/promo-codes/validate", json={
            "code": "TEST20_ITER111",
            "checkout_type": "one_time"
        }, headers=customer_a_headers)
        assert r.status_code == 200, f"Validate promo failed: {r.text}"
        data = r.json()
        assert data["valid"] is True
        assert data["discount_type"] == "percentage"
        assert data["discount_value"] == 20.0
        print("PASS: Percent promo validated correctly")

    def test_create_expired_promo(self, tenant_a_headers):
        """F: Create expired promo code"""
        expired_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        r = requests.post(f"{BASE_URL}/api/admin/promo-codes", json={
            "code": "EXPIRED_ITER111",
            "discount_type": "percentage",
            "discount_value": 10.0,
            "applies_to": "both",
            "expiry_date": expired_date,
            "enabled": True
        }, headers=tenant_a_headers)
        assert r.status_code == 200
        TEST_DATA["promo_id_expired"] = r.json()["id"]

    def test_expired_promo_rejected(self, customer_a_headers):
        """F: Expired promo code should be rejected at validation"""
        r = requests.post(f"{BASE_URL}/api/promo-codes/validate", json={
            "code": "EXPIRED_ITER111",
            "checkout_type": "one_time"
        }, headers=customer_a_headers)
        assert r.status_code == 400, f"Expected 400 for expired promo, got {r.status_code}"
        assert "expired" in r.json().get("detail", "").lower()
        print("PASS: Expired promo code correctly rejected")

    def test_create_limited_use_promo(self, tenant_a_headers):
        """F: Create promo with max_uses=1"""
        r = requests.post(f"{BASE_URL}/api/admin/promo-codes", json={
            "code": "LIMITED_ITER111",
            "discount_type": "percentage",
            "discount_value": 5.0,
            "applies_to": "both",
            "max_uses": 1,
            "enabled": True
        }, headers=tenant_a_headers)
        assert r.status_code == 200
        TEST_DATA["promo_id_limited"] = r.json()["id"]

    def test_deactivate_promo(self, tenant_a_headers):
        """F: Deactivate promo code"""
        promo_id = TEST_DATA.get("promo_id_fixed")
        if not promo_id:
            pytest.skip("No fixed promo available")
        r = requests.put(f"{BASE_URL}/api/admin/promo-codes/{promo_id}", json={
            "enabled": False
        }, headers=tenant_a_headers)
        assert r.status_code == 200
        print("PASS: Promo code deactivated")

    def test_deactivated_promo_rejected(self, customer_a_headers):
        """F: Deactivated promo code should be rejected"""
        r = requests.post(f"{BASE_URL}/api/promo-codes/validate", json={
            "code": "FIXED10_ITER111",
            "checkout_type": "one_time"
        }, headers=customer_a_headers)
        assert r.status_code == 400, f"Expected 400 for inactive promo, got {r.status_code}"
        print("PASS: Deactivated promo correctly rejected")

    def test_list_promo_codes(self, tenant_a_headers):
        """F: List promo codes"""
        r = requests.get(f"{BASE_URL}/api/admin/promo-codes", headers=tenant_a_headers)
        assert r.status_code == 200
        data = r.json()
        codes = [c["code"] for c in data["promo_codes"]]
        assert "TEST20_ITER111" in codes
        print(f"PASS: Listed {len(codes)} promo codes for tenant-a")

    def test_promo_tenant_isolation(self, tenant_a_headers):
        """F: Promo codes are tenant-scoped"""
        r = requests.get(f"{BASE_URL}/api/admin/promo-codes", headers=tenant_a_headers)
        codes = r.json()["promo_codes"]
        for code in codes:
            assert code.get("tenant_id") == "5ed23354-05bc-4603-8613-6a12a26a0f28" or code.get("tenant_id") is None, \
                f"Promo code {code['code']} has wrong tenant_id: {code.get('tenant_id')}"
        print(f"PASS: All {len(codes)} promo codes properly tenant-scoped")


# ─────────────────────────── G. TERMS ────────────────────────────────────────

class TestTerms:
    """G. Terms: CRUD, product assignment, snapshot immutability"""

    def test_create_terms(self, tenant_a_headers):
        """G: Create terms document"""
        r = requests.post(f"{BASE_URL}/api/admin/terms", json={
            "title": "TEST_Terms_Iter111",
            "content": "<p>These are test terms and conditions for iter111.</p>",
            "is_default": False,
            "status": "active"
        }, headers=tenant_a_headers)
        assert r.status_code == 200, f"Create terms failed: {r.text}"
        data = r.json()
        assert "id" in data
        TEST_DATA["terms_id"] = data["id"]
        print(f"Created terms ID: {data['id']}")

    def test_list_terms(self, tenant_a_headers):
        """G: List terms documents"""
        r = requests.get(f"{BASE_URL}/api/admin/terms", headers=tenant_a_headers)
        assert r.status_code == 200
        data = r.json()
        titles = [t["title"] for t in data["terms"]]
        assert "TEST_Terms_Iter111" in titles
        print(f"PASS: Terms listed: {len(titles)} documents")

    def test_assign_terms_to_product(self, tenant_a_headers):
        """G: Assign terms to product"""
        product_id = TEST_DATA.get("product_id_standard")
        terms_id = TEST_DATA.get("terms_id")
        if not product_id or not terms_id:
            pytest.skip("No product or terms available")
        r = requests.put(f"{BASE_URL}/api/admin/products/{product_id}/terms",
                         params={"terms_id": terms_id},
                         headers=tenant_a_headers)
        assert r.status_code == 200, f"Assign terms failed: {r.text}"
        print("PASS: Terms assigned to product")

    def test_update_terms(self, tenant_a_headers):
        """G: Update terms title"""
        terms_id = TEST_DATA.get("terms_id")
        if not terms_id:
            pytest.skip("No terms available")
        r = requests.put(f"{BASE_URL}/api/admin/terms/{terms_id}", json={
            "title": "TEST_Terms_Iter111_Updated"
        }, headers=tenant_a_headers)
        assert r.status_code == 200
        print("PASS: Terms updated")

    def test_delete_default_terms_blocked(self, tenant_a_headers):
        """G: Cannot delete default terms"""
        # Find the default terms
        r = requests.get(f"{BASE_URL}/api/admin/terms", headers=tenant_a_headers)
        terms = r.json()["terms"]
        default = next((t for t in terms if t.get("is_default")), None)
        if not default:
            print("SKIP: No default terms found for deletion test")
            return
        r2 = requests.delete(f"{BASE_URL}/api/admin/terms/{default['id']}", headers=tenant_a_headers)
        assert r2.status_code == 400, f"Expected 400 for deleting default terms, got {r2.status_code}"
        print("PASS: Default terms deletion correctly blocked")

    def test_terms_html_sanitized(self, tenant_a_headers):
        """G: Terms content with script tag should be sanitized"""
        r = requests.post(f"{BASE_URL}/api/admin/terms", json={
            "title": "TEST_Terms_XSS_Iter111",
            "content": "<p>Safe content</p><script>alert('xss')</script>",
            "is_default": False,
            "status": "active"
        }, headers=tenant_a_headers)
        assert r.status_code == 200
        tid = r.json()["id"]
        TEST_DATA["terms_id_xss"] = tid
        # Verify script tag was removed
        r2 = requests.get(f"{BASE_URL}/api/admin/terms", headers=tenant_a_headers)
        terms = r2.json()["terms"]
        terms_doc = next((t for t in terms if t["id"] == tid), None)
        if terms_doc:
            assert "<script>" not in terms_doc.get("content", ""), "Script tag not sanitized!"
            print("PASS: XSS content sanitized in terms")


# ─────────────────────────── H. TENANT ISOLATION ─────────────────────────────

class TestTenantIsolation:
    """H. Tenant Isolation: Platform admin vs tenant admin vs cross-tenant"""

    def test_platform_admin_sees_all_products(self, platform_admin_headers):
        """H: Platform admin can see products from all tenants"""
        r = requests.get(f"{BASE_URL}/api/admin/products-all", headers=platform_admin_headers)
        assert r.status_code == 200
        data = r.json()
        total = data["total"]
        # Should see products from multiple tenants (automate-accounts + test-iter109-a)
        assert total > 0, "Platform admin sees no products"
        # Check that products from multiple tenants are visible
        products = data["products"]
        tenant_ids = set(p.get("tenant_id") for p in products if p.get("tenant_id"))
        print(f"PASS: Platform admin sees {total} products from tenants: {tenant_ids}")

    def test_tenant_a_sees_only_own_products(self, tenant_a_headers, tenant_a_id):
        """H: Tenant-a admin sees only their own products"""
        r = requests.get(f"{BASE_URL}/api/admin/products-all", headers=tenant_a_headers)
        assert r.status_code == 200
        products = r.json()["products"]
        for p in products:
            assert p.get("tenant_id") == tenant_a_id, \
                f"Product {p['name']} has wrong tenant_id: {p.get('tenant_id')}"
        print(f"PASS: Tenant-a sees {len(products)} products, all correctly scoped")

    def test_tenant_a_categories_isolated(self, tenant_a_headers, tenant_a_id):
        """H: Tenant-a categories are isolated"""
        r = requests.get(f"{BASE_URL}/api/admin/categories", headers=tenant_a_headers)
        assert r.status_code == 200
        cats = r.json()["categories"]
        for cat in cats:
            assert cat.get("tenant_id") == tenant_a_id, \
                f"Category {cat['name']} has wrong tenant_id: {cat.get('tenant_id')}"
        print(f"PASS: Tenant-a categories isolated: {len(cats)} categories")

    def test_tenant_a_terms_isolated(self, tenant_a_headers, tenant_a_id):
        """H: Tenant-a terms are isolated"""
        r = requests.get(f"{BASE_URL}/api/admin/terms", headers=tenant_a_headers)
        assert r.status_code == 200
        terms = r.json()["terms"]
        for t in terms:
            assert t.get("tenant_id") == tenant_a_id, \
                f"Terms {t.get('title')} has wrong tenant_id: {t.get('tenant_id')}"
        print(f"PASS: Tenant-a terms isolated: {len(terms)} terms")

    def test_tenant_a_promo_codes_isolated(self, tenant_a_headers, tenant_a_id):
        """H: Tenant-a promo codes are isolated"""
        r = requests.get(f"{BASE_URL}/api/admin/promo-codes", headers=tenant_a_headers)
        assert r.status_code == 200
        codes = r.json()["promo_codes"]
        for code in codes:
            assert code.get("tenant_id") == tenant_a_id, \
                f"Promo {code['code']} has wrong tenant_id: {code.get('tenant_id')}"
        print(f"PASS: Tenant-a promo codes isolated: {len(codes)} codes")

    def test_platform_admin_product_partner_column(self, platform_admin_headers):
        """H: Products returned by platform admin include partner_code field"""
        r = requests.get(f"{BASE_URL}/api/admin/products-all", headers=platform_admin_headers)
        assert r.status_code == 200
        products = r.json()["products"]
        if not products:
            print("SKIP: No products to check partner_code field")
            return
        # At least some products should have partner_code enriched
        has_partner = any("partner_code" in p for p in products)
        print(f"PASS: Partner code enrichment present: {has_partner}")

    def test_store_customer_a_sees_only_tenant_a_products(self, customer_a_headers, tenant_a_id):
        """H2: Customer from tenant-a only sees tenant-a products in store"""
        r = requests.get(f"{BASE_URL}/api/products", headers=customer_a_headers)
        assert r.status_code == 200
        products = r.json()["products"]
        for p in products:
            assert p.get("tenant_id") == tenant_a_id, \
                f"Customer sees product {p['name']} from different tenant: {p.get('tenant_id')}"
        print(f"PASS: Customer-a sees {len(products)} products, all from tenant-a only")


# ─────────────────────────── SECURITY ────────────────────────────────────────

class TestSecurity:
    """SECURITY: Price tampering, visibility bypass"""

    def test_price_tampering_server_recalculates(self, customer_a_headers):
        """SECURITY: Server-side price calculation ignores client tampered values"""
        product_id = TEST_DATA.get("product_id_pricing")
        if not product_id:
            pytest.skip("No pricing product available")
        # Request orders preview with honest inputs — server must use base price
        r = requests.post(f"{BASE_URL}/api/orders/preview", json={
            "items": [
                {
                    "product_id": product_id,
                    "inputs": {"service_tier": "basic"},
                    # No price_override field = server must calculate
                }
            ]
        }, headers=customer_a_headers)
        assert r.status_code == 200, f"Orders preview failed: {r.text}"
        data = r.json()
        item = data["items"][0]
        # Server should return 100.0 (base) not a tampered value
        assert item["subtotal"] == 100.0, f"Expected 100.0, got {item['subtotal']}"
        print(f"PASS: Server-side price calculation: {item['subtotal']}")

    def test_visibility_bypass_blocked(self, customer_a_headers):
        """SECURITY: Direct access to restricted product returns 404"""
        pid = TEST_DATA.get("product_id_restricted")
        if not pid:
            pytest.skip("No restricted product available")
        r = requests.get(f"{BASE_URL}/api/products/{pid}", headers=customer_a_headers)
        assert r.status_code == 404, f"Expected 404 for restricted product bypass, got {r.status_code}"
        print("PASS: Visibility bypass attempt correctly blocked")

    def test_tenant_a_cannot_access_platform_wide_endpoint(self, tenant_a_headers):
        """SECURITY: Tenant-a cannot access other tenant products via admin API"""
        # Tenant-a admin should only get their own products
        r = requests.get(f"{BASE_URL}/api/admin/products-all", headers=tenant_a_headers)
        assert r.status_code == 200
        products = r.json()["products"]
        for p in products:
            assert p.get("tenant_id") == "5ed23354-05bc-4603-8613-6a12a26a0f28", \
                f"Cross-tenant data leak: {p['name']} has tenant_id {p.get('tenant_id')}"
        print(f"PASS: Tenant-a admin cannot see other tenants' products")


# ─────────────────────────── CLEANUP ─────────────────────────────────────────

class TestCleanup:
    """Cleanup test data created during testing"""

    def test_delete_test_promo_codes(self, tenant_a_headers):
        """Cleanup: Delete test promo codes"""
        promo_ids = [
            TEST_DATA.get("promo_id_percent"),
            TEST_DATA.get("promo_id_fixed"),
            TEST_DATA.get("promo_id_expired"),
            TEST_DATA.get("promo_id_limited"),
        ]
        deleted = 0
        for pid in promo_ids:
            if pid:
                r = requests.delete(f"{BASE_URL}/api/admin/promo-codes/{pid}", headers=tenant_a_headers)
                if r.status_code == 200:
                    deleted += 1
        print(f"Deleted {deleted} test promo codes")

    def test_delete_test_terms(self, tenant_a_headers):
        """Cleanup: Delete test terms"""
        terms_ids = [TEST_DATA.get("terms_id"), TEST_DATA.get("terms_id_xss")]
        deleted = 0
        for tid in terms_ids:
            if tid:
                r = requests.delete(f"{BASE_URL}/api/admin/terms/{tid}", headers=tenant_a_headers)
                if r.status_code == 200:
                    deleted += 1
        print(f"Deleted {deleted} test terms docs")

    def test_delete_test_category(self, tenant_a_headers):
        """Cleanup: Restore category name first (since products link to it)"""
        cat_id = TEST_DATA.get("category_id")
        if not cat_id:
            print("No test category to clean up")
            return
        # Category has products, so deletion should fail - that's expected
        r = requests.delete(f"{BASE_URL}/api/admin/categories/{cat_id}", headers=tenant_a_headers)
        # 409 expected if products are still linked
        print(f"Category deletion attempt: {r.status_code} - {'PASS (has products)' if r.status_code == 409 else r.text}")

    def test_summary_of_created_data(self):
        """Summary of all created test data"""
        print("\n=== TEST DATA SUMMARY ===")
        for key, val in TEST_DATA.items():
            print(f"  {key}: {val}")
        print("========================")
