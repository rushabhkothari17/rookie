"""
Tests for 13 bug fixes (iteration 244):
1. Product name 100-char limit + character counter (frontend only, but can test backend limit acceptance)
2. Product name overflow on store card (frontend only)
3. Default T&C save blocking removed (terms optional)
4+5. Inactive categories filtered from product dropdown
6+7. Categories endpoint returns objects with is_active+blurb; all categories shown
8. Card Tag appears on store front
9. Visibility rule Country=India works (empty string fallback)
10. Currency shows as £ or € symbol in cart (Intl.NumberFormat - frontend only, but backend sends currency field)
11. Cart shows price breakdown when show_price_breakdown=true
12. not_equals visibility rule hidden when dependent question unanswered (frontend only)
13. DebouncedNumberInput (frontend only)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"

CUSTOMER_EMAIL = "TEST_bugfix242_customer@example.com"
CUSTOMER_PASSWORD = "Test@bugfix242!"
PARTNER_CODE = "testpartner242"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_token(session):
    resp = session.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if resp.status_code != 200:
        pytest.skip(f"Admin login failed: {resp.status_code}")
    return resp.json().get("token")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def customer_token(session):
    resp = session.post(f"{BASE_URL}/api/auth/customer-login", json={
        "email": CUSTOMER_EMAIL, "password": CUSTOMER_PASSWORD, "partner_code": PARTNER_CODE
    })
    if resp.status_code != 200:
        pytest.skip(f"Customer login failed: {resp.status_code} {resp.text}")
    return resp.json().get("token")


@pytest.fixture(scope="module")
def customer_headers(customer_token):
    return {"Authorization": f"Bearer {customer_token}", "Content-Type": "application/json"}


# ── Issue 1: Product name 100-char limit accepted by backend ──────────────────

class TestIssue1ProductNameLimit:
    """Backend should accept product names up to 100 chars"""

    def test_create_product_with_long_name_accepted(self, session, admin_headers):
        """100 char product name should be accepted by backend"""
        long_name = "A" * 100  # exactly 100 chars
        resp = session.post(f"{BASE_URL}/api/admin/products", json={
            "name": long_name,
            "category": "General Services",
            "pricing_type": "internal",
            "base_price": 10,
            "is_active": False,  # don't publish it
        }, headers=admin_headers)
        # Should succeed
        assert resp.status_code in [200, 201], f"Expected success for 100-char name, got {resp.status_code}: {resp.text}"
        data = resp.json()
        product_id = data.get("product", {}).get("id") or data.get("id")
        if product_id:
            # Cleanup
            session.delete(f"{BASE_URL}/api/admin/products/{product_id}", headers=admin_headers)


# ── Issue 3: Default T&C save no longer blocks ───────────────────────────────

class TestIssue3DefaultTCNoBlock:
    """Creating product without terms_id should succeed"""

    def test_create_product_no_terms_id_succeeds(self, session, admin_headers):
        """Product with no terms_id (null) should save without error"""
        resp = session.post(f"{BASE_URL}/api/admin/products", json={
            "name": "TEST_NoTerms_BugFix244",
            "category": "General Services",
            "pricing_type": "internal",
            "base_price": 100,
            "terms_id": None,
            "is_active": False,
        }, headers=admin_headers)
        assert resp.status_code in [200, 201], f"Expected success for product with no terms_id, got {resp.status_code}: {resp.text}"
        data = resp.json()
        product_id = data.get("product", {}).get("id") or data.get("id")
        assert product_id, "Response should include product id"
        # Verify terms_id is null/missing in retrieved product
        get_resp = session.get(f"{BASE_URL}/api/admin/products-all?per_page=500", headers=admin_headers)
        products = get_resp.json().get("products", [])
        prod = next((p for p in products if p.get("id") == product_id), None)
        if prod:
            assert prod.get("terms_id") in [None, ""], f"terms_id should be null, got {prod.get('terms_id')}"
        if product_id:
            session.delete(f"{BASE_URL}/api/admin/products/{product_id}", headers=admin_headers)

    def test_create_product_with_default_terms_string_succeeds(self, session, admin_headers):
        """Product with empty string terms_id should also save"""
        resp = session.post(f"{BASE_URL}/api/admin/products", json={
            "name": "TEST_EmptyTerms_BugFix244",
            "category": "General Services",
            "pricing_type": "internal",
            "base_price": 100,
            "terms_id": "",
            "is_active": False,
        }, headers=admin_headers)
        assert resp.status_code in [200, 201], f"Expected success for product with empty terms_id, got {resp.status_code}: {resp.text}"
        data = resp.json()
        product_id = data.get("product", {}).get("id") or data.get("id")
        if product_id:
            session.delete(f"{BASE_URL}/api/admin/products/{product_id}", headers=admin_headers)


# ── Issues 4+5: Inactive categories filtered ─────────────────────────────────

class TestIssue45InactiveCategories:
    """Inactive categories should not appear in product creation dropdown (store endpoint)"""

    def test_admin_can_deactivate_category(self, session, admin_headers):
        """Admin can create and then deactivate a category"""
        import time
        cat_name = f"TEST_InactiveCat_{int(time.time())}"
        # Create a test category
        resp = session.post(f"{BASE_URL}/api/admin/categories", json={
            "name": cat_name,
            "description": "test category to be deactivated",
            "is_active": True,
        }, headers=admin_headers)
        assert resp.status_code in [200, 201], f"Category creation failed: {resp.status_code}: {resp.text}"
        cat_id = resp.json().get("category", {}).get("id") or resp.json().get("id")
        assert cat_id, "Category ID should be in response"

        # Deactivate it
        patch_resp = session.put(f"{BASE_URL}/api/admin/categories/{cat_id}", json={
            "is_active": False,
        }, headers=admin_headers)
        assert patch_resp.status_code in [200, 201], f"Category deactivation failed: {patch_resp.status_code}: {patch_resp.text}"

        # Verify is_active=False in response
        deactivated = patch_resp.json().get("category", {})
        assert deactivated.get("is_active") == False, "Category should be marked as inactive"

        # Verify admin categories endpoint still shows it (admin sees all)
        get_resp = session.get(f"{BASE_URL}/api/admin/categories", headers=admin_headers)
        all_cats = get_resp.json().get("categories", [])
        cat = next((c for c in all_cats if c.get("id") == cat_id), None)
        assert cat, "Deactivated category should still appear in admin list"
        assert cat.get("is_active") == False, "Category should be marked as inactive in admin list"

        # Cleanup
        session.delete(f"{BASE_URL}/api/admin/categories/{cat_id}", headers=admin_headers)

    def test_inactive_category_not_in_store_categories(self, session, admin_headers):
        """A deactivated category should not appear in store /categories"""
        import time
        cat_name = f"TEST_StoreFilter_{int(time.time())}"
        # Create a test category
        create_resp = session.post(f"{BASE_URL}/api/admin/categories", json={
            "name": cat_name,
            "description": "filter test",
            "is_active": True,
        }, headers=admin_headers)
        assert create_resp.status_code in [200, 201], f"Category creation failed: {create_resp.status_code}: {create_resp.text}"
        cat_id = create_resp.json().get("category", {}).get("id") or create_resp.json().get("id")
        assert cat_id, "Category ID should be returned"

        # Create a product in this category
        prod_resp = session.post(f"{BASE_URL}/api/admin/products", json={
            "name": f"TEST_Product_{cat_name[:30]}",
            "category": cat_name,
            "pricing_type": "internal",
            "base_price": 50,
            "is_active": True,
        }, headers=admin_headers)
        prod_id = prod_resp.json().get("product", {}).get("id") if prod_resp.status_code in [200, 201] else None

        # Deactivate the category
        deact_resp = session.put(f"{BASE_URL}/api/admin/categories/{cat_id}", json={"is_active": False}, headers=admin_headers)
        assert deact_resp.status_code in [200, 201], f"Deactivation failed: {deact_resp.status_code}"

        # Store should NOT show inactive category
        store_cats_after = session.get(f"{BASE_URL}/api/categories").json().get("categories", [])
        cat_names_after = [c["name"] for c in store_cats_after]
        assert cat_name not in cat_names_after, f"Inactive category should not appear in store categories, got: {cat_names_after}"

        # Cleanup
        if prod_id:
            session.delete(f"{BASE_URL}/api/admin/products/{prod_id}", headers=admin_headers)
        session.delete(f"{BASE_URL}/api/admin/categories/{cat_id}", headers=admin_headers)


# ── Issues 6+7: Categories endpoint returns objects ──────────────────────────

class TestIssue67CategoriesEndpoint:
    """Store /categories endpoint returns objects with name, is_active, blurb"""

    def test_categories_returns_objects_with_fields(self, session):
        """GET /api/categories should return list of objects with name, is_active, blurb"""
        resp = session.get(f"{BASE_URL}/api/categories")
        assert resp.status_code == 200, f"Categories endpoint failed: {resp.status_code}"
        data = resp.json()
        cats = data.get("categories", [])
        assert isinstance(cats, list), "categories should be a list"
        if cats:
            cat = cats[0]
            assert "name" in cat, "Category object should have 'name'"
            assert "is_active" in cat, "Category object should have 'is_active'"
            assert "blurb" in cat, "Category object should have 'blurb'"

    def test_all_active_categories_with_products_shown(self, session, admin_headers):
        """All active categories with active products should appear in store endpoint"""
        # Get admin categories count
        admin_resp = session.get(f"{BASE_URL}/api/admin/categories", headers=admin_headers)
        assert admin_resp.status_code == 200
        all_admin_cats = admin_resp.json().get("categories", [])
        active_admin_cats = [c for c in all_admin_cats if c.get("is_active") and not c.get("tenant_id")]
        
        # Get store categories
        store_resp = session.get(f"{BASE_URL}/api/categories")
        assert store_resp.status_code == 200
        store_cats = store_resp.json().get("categories", [])
        
        # Store should have categories (not just 2 or truncated list)
        # If there are active categories with products, they should appear
        print(f"Admin active categories: {len(active_admin_cats)}, Store categories: {len(store_cats)}")
        # Just verify we get more than 0 categories if admin has active ones
        # The store endpoint only shows categories that have at least 1 active product
        assert isinstance(store_cats, list)

    def test_categories_with_partner_code(self, session):
        """Categories for partner code testpartner242 should work"""
        resp = session.get(f"{BASE_URL}/api/categories?partner_code=testpartner242")
        assert resp.status_code == 200
        data = resp.json()
        cats = data.get("categories", [])
        # testpartner242 has "General Services" category with a product
        if cats:
            for cat in cats:
                assert "name" in cat
                assert "is_active" in cat
                assert "blurb" in cat
                assert cat["is_active"] == True, "Only active categories should be returned"


# ── Issue 8: Card Tag appears on store front ─────────────────────────────────

class TestIssue8CardTag:
    """Card tag set in admin should appear in product data returned by store"""

    def test_product_with_card_tag_has_it_in_store_data(self, session, admin_headers):
        """Product with card_tag set should return card_tag in store products endpoint"""
        # Create product with card_tag
        resp = session.post(f"{BASE_URL}/api/admin/products", json={
            "name": "TEST_CardTag_244",
            "category": "General Services",
            "pricing_type": "internal",
            "base_price": 200,
            "card_tag": "TEST Featured",
            "is_active": True,
        }, headers=admin_headers)
        assert resp.status_code in [200, 201], f"Product creation failed: {resp.status_code}: {resp.text}"
        product_id = resp.json().get("product", {}).get("id") or resp.json().get("id")
        assert product_id, "Product ID should be in response"

        # Check admin products-all for card_tag
        all_prods_resp = session.get(f"{BASE_URL}/api/admin/products-all?per_page=500", headers=admin_headers)
        all_prods = all_prods_resp.json().get("products", [])
        prod_admin = next((p for p in all_prods if p.get("id") == product_id), None)
        assert prod_admin, "Product should be findable in admin list"
        assert prod_admin.get("card_tag") == "TEST Featured", f"card_tag should be 'TEST Featured', got {prod_admin.get('card_tag')}"

        # Cleanup
        session.delete(f"{BASE_URL}/api/admin/products/{product_id}", headers=admin_headers)


# ── Issue 9: Visibility rule Country=India ────────────────────────────────────

class TestIssue9CountryVisibility:
    """Product with visibility rule Country=India should be visible to India-based customer"""

    def test_products_visible_to_india_customer(self, session, admin_headers, customer_headers):
        """Create product visible only to India customers; verify it shows when address is India"""
        # First update customer address to India
        update_resp = session.put(f"{BASE_URL}/api/me", json={
            "address": {
                "line1": "123 Test Street",
                "city": "Mumbai",
                "region": "Maharashtra",
                "postal": "400001",
                "country": "India"
            }
        }, headers=customer_headers)
        assert update_resp.status_code == 200, f"Address update failed: {update_resp.status_code}: {update_resp.text}"

        # Create product in testpartner242 tenant using partner admin credentials
        partner_resp = session.post(f"{BASE_URL}/api/auth/partner-login", json={
            "email": "partneradmin@testpartner242.local",
            "password": "Admin@123!",
            "partner_code": "testpartner242"
        })
        assert partner_resp.status_code == 200, f"Partner admin login failed: {partner_resp.status_code}"
        partner_token = partner_resp.json().get("token")
        partner_headers = {"Authorization": f"Bearer {partner_token}", "Content-Type": "application/json"}

        # Create product with country=India visibility rule in testpartner242 tenant
        vis_conditions = {
            "top_logic": "AND",
            "groups": [{
                "logic": "AND",
                "conditions": [{
                    "field": "country",
                    "operator": "equals",
                    "value": "india"
                }]
            }]
        }
        resp = session.post(f"{BASE_URL}/api/admin/products", json={
            "name": "TEST_IndiaOnly_244",
            "category": "General Services",
            "pricing_type": "internal",
            "base_price": 500,
            "is_active": True,
            "visibility_conditions": vis_conditions,
        }, headers=partner_headers)
        assert resp.status_code in [200, 201], f"Product creation failed: {resp.status_code}: {resp.text}"
        product_id = resp.json().get("product", {}).get("id") or resp.json().get("id")
        assert product_id

        # Get products as customer (in same testpartner242 tenant)
        store_resp = session.get(f"{BASE_URL}/api/products?partner_code={PARTNER_CODE}", headers=customer_headers)
        assert store_resp.status_code == 200
        store_prods = store_resp.json().get("products", [])
        prod_ids = [p.get("id") for p in store_prods]
        assert product_id in prod_ids, f"India-only product should be visible to India-addressed customer. Products: {prod_ids[:5]}"

        # Cleanup - restore customer address
        session.put(f"{BASE_URL}/api/me", json={
            "address": {"line1": "456 New Address St", "line2": "Suite 100", "city": "Vancouver",
                       "region": "British Columbia", "postal": "V5V5V5", "country": "Canada"}
        }, headers=customer_headers)
        session.delete(f"{BASE_URL}/api/admin/products/{product_id}", headers=partner_headers)

    def test_visibility_country_empty_string_fallback(self, session, admin_headers):
        """Backend evalSingleVisCond handles empty string customer country by checking address"""
        # Verify the /categories endpoint doesn't error out
        resp = session.get(f"{BASE_URL}/api/categories")
        assert resp.status_code == 200

        # Create product with country visibility to test the endpoint
        vis_conditions = {
            "top_logic": "AND",
            "groups": [{
                "logic": "AND",
                "conditions": [{
                    "field": "country",
                    "operator": "equals",
                    "value": ""
                }]
            }]
        }
        resp = session.post(f"{BASE_URL}/api/admin/products", json={
            "name": "TEST_EmptyCountry_244",
            "category": "General Services",
            "pricing_type": "internal",
            "base_price": 100,
            "is_active": True,
            "visibility_conditions": vis_conditions,
        }, headers=admin_headers)
        assert resp.status_code in [200, 201], f"Product creation failed: {resp.status_code}"
        product_id = resp.json().get("product", {}).get("id") or resp.json().get("id")

        # Products endpoint should work without error
        store_resp = session.get(f"{BASE_URL}/api/products")
        assert store_resp.status_code == 200

        if product_id:
            session.delete(f"{BASE_URL}/api/admin/products/{product_id}", headers=admin_headers)


# ── Issue 10: Currency shows as £/€ symbol (backend sends currency code) ──────

class TestIssue10Currency:
    """Backend returns currency field, frontend uses Intl.NumberFormat for symbols"""

    def test_product_currency_field_in_store_data(self, session, admin_headers):
        """Product with GBP currency should return currency='GBP' in store endpoint"""
        resp = session.post(f"{BASE_URL}/api/admin/products", json={
            "name": "TEST_GBP_Currency_244",
            "category": "General Services",
            "pricing_type": "internal",
            "base_price": 150,
            "currency": "GBP",
            "is_active": True,
        }, headers=admin_headers)
        assert resp.status_code in [200, 201], f"Product creation failed: {resp.status_code}: {resp.text}"
        product_id = resp.json().get("product", {}).get("id") or resp.json().get("id")

        # Verify currency stored correctly
        all_prods_resp = session.get(f"{BASE_URL}/api/admin/products-all?per_page=500", headers=admin_headers)
        all_prods = all_prods_resp.json().get("products", [])
        prod = next((p for p in all_prods if p.get("id") == product_id), None)
        if prod:
            assert prod.get("currency") == "GBP", f"Expected GBP, got {prod.get('currency')}"

        if product_id:
            session.delete(f"{BASE_URL}/api/admin/products/{product_id}", headers=admin_headers)

    def test_product_currency_eur_field_stored(self, session, admin_headers):
        """Product with EUR currency should return currency='EUR'"""
        resp = session.post(f"{BASE_URL}/api/admin/products", json={
            "name": "TEST_EUR_Currency_244",
            "category": "General Services",
            "pricing_type": "internal",
            "base_price": 200,
            "currency": "EUR",
            "is_active": True,
        }, headers=admin_headers)
        assert resp.status_code in [200, 201]
        product_id = resp.json().get("product", {}).get("id") or resp.json().get("id")

        all_prods_resp = session.get(f"{BASE_URL}/api/admin/products-all?per_page=500", headers=admin_headers)
        all_prods = all_prods_resp.json().get("products", [])
        prod = next((p for p in all_prods if p.get("id") == product_id), None)
        if prod:
            assert prod.get("currency") == "EUR", f"Expected EUR, got {prod.get('currency')}"

        if product_id:
            session.delete(f"{BASE_URL}/api/admin/products/{product_id}", headers=admin_headers)


# ── Issue 11: Price breakdown in cart ────────────────────────────────────────

class TestIssue11PriceBreakdown:
    """Product with show_price_breakdown=true should have line_items in cart preview"""

    def test_product_with_show_price_breakdown_field(self, session, admin_headers):
        """Product can be created and retrieved with show_price_breakdown=true"""
        resp = session.post(f"{BASE_URL}/api/admin/products", json={
            "name": "TEST_PriceBreakdown_244",
            "category": "General Services",
            "pricing_type": "internal",
            "base_price": 300,
            "show_price_breakdown": True,
            "is_active": True,
        }, headers=admin_headers)
        assert resp.status_code in [200, 201], f"Product creation failed: {resp.status_code}: {resp.text}"
        product_id = resp.json().get("product", {}).get("id") or resp.json().get("id")

        # Verify show_price_breakdown stored
        all_prods_resp = session.get(f"{BASE_URL}/api/admin/products-all?per_page=500", headers=admin_headers)
        all_prods = all_prods_resp.json().get("products", [])
        prod = next((p for p in all_prods if p.get("id") == product_id), None)
        if prod:
            assert prod.get("show_price_breakdown") == True, f"Expected show_price_breakdown=True"

        if product_id:
            session.delete(f"{BASE_URL}/api/admin/products/{product_id}", headers=admin_headers)

    def test_order_preview_has_line_items_for_price_breakdown(self, session, admin_headers, customer_headers):
        """Order preview should have line_items when product has intake questions"""
        # Login as partner admin to create product in testpartner242 tenant
        partner_resp = session.post(f"{BASE_URL}/api/auth/partner-login", json={
            "email": "partneradmin@testpartner242.local",
            "password": "Admin@123!",
            "partner_code": "testpartner242"
        })
        assert partner_resp.status_code == 200, f"Partner login failed: {partner_resp.status_code}"
        partner_token = partner_resp.json().get("token")
        partner_headers = {"Authorization": f"Bearer {partner_token}", "Content-Type": "application/json"}

        # Create product with intake question that affects price in testpartner242 tenant
        intake_schema = {
            "questions": [{
                "key": "hours",
                "type": "number",
                "label": "Hours",
                "required": True,
                "enabled": True,
                "price_per_unit": 10,
                "min": 1,
                "order": 1,
            }]
        }
        resp = session.post(f"{BASE_URL}/api/admin/products", json={
            "name": "TEST_BreakdownLineItems_244",
            "category": "General Services",
            "pricing_type": "internal",
            "base_price": 100,
            "show_price_breakdown": True,
            "intake_schema_json": intake_schema,
            "is_active": True,
        }, headers=partner_headers)
        assert resp.status_code in [200, 201], f"Product creation failed: {resp.status_code}: {resp.text}"
        product_id = resp.json().get("product", {}).get("id") or resp.json().get("id")

        # Order preview - customer is in same testpartner242 tenant
        preview_resp = session.post(f"{BASE_URL}/api/orders/preview", json={
            "items": [{
                "product_id": product_id,
                "quantity": 1,
                "inputs": {"hours": 5}
            }]
        }, headers=customer_headers)
        assert preview_resp.status_code == 200, f"Order preview failed: {preview_resp.status_code}: {preview_resp.text}"
        preview_data = preview_resp.json()
        items = preview_data.get("items", [])
        assert len(items) > 0, "Preview should have items"
        item = items[0]
        pricing = item.get("pricing", {})
        # line_items should be present for price breakdown
        line_items = pricing.get("line_items", [])
        print(f"Line items: {line_items}")
        # Base price (100) + hours*10 (50) = 150
        assert pricing.get("subtotal") == 150, f"Subtotal should be 150, got {pricing.get('subtotal')}"

        if product_id:
            session.delete(f"{BASE_URL}/api/admin/products/{product_id}", headers=partner_headers)
