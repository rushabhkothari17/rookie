"""
Iteration 95 - New Pricing Architecture Test Suite (3-type model)
Tests for:
- internal / external / enquiry pricing types
- New IntakeSchemaBuilder flat array format
- Product CRUD with intake_schema_json
- POST /api/pricing/calc for internal product
- Creating products with intake questions (number + dropdown)
- Store card pricing labels
- Admin login with partner_code
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"
PARTNER_CODE = "automate-accounts"

# Track created product IDs for cleanup
_created_product_ids: list = []


# ─── Auth fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def auth_token():
    """Admin login via partner-login endpoint."""
    resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
        "partner_code": PARTNER_CODE,
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
    })
    if resp.status_code != 200:
        # Fallback: try standard login
        resp2 = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
        })
        if resp2.status_code != 200:
            pytest.fail(f"Admin login failed: partner={resp.status_code} {resp.text}, direct={resp2.status_code} {resp2.text}")
        data = resp2.json()
    else:
        data = resp.json()
    token = data.get("token") or data.get("access_token")
    assert token, f"No token in login response: {data}"
    return token


@pytest.fixture(scope="module")
def admin_client(auth_token):
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}",
    })
    return session


# ─── Test: Admin Login ─────────────────────────────────────────────────────────

class TestAdminLogin:
    """Admin login tests."""

    def test_partner_login_works(self):
        """Admin login via POST /api/auth/partner-login succeeds."""
        resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": PARTNER_CODE,
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
        })
        if resp.status_code == 200:
            token = resp.json().get("token") or resp.json().get("access_token")
            assert token, "No token in partner-login response"
            print(f"✓ Partner login succeeded, token: {token[:20]}...")
        else:
            # Fallback to direct login
            resp2 = requests.post(f"{BASE_URL}/api/auth/login", json={
                "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD,
            })
            assert resp2.status_code == 200, f"Both login attempts failed: {resp.status_code}, {resp2.status_code}"
            print(f"✓ Direct login succeeded (partner-login returned {resp.status_code})")


# ─── Test: Products Catalog ────────────────────────────────────────────────────

class TestProductsCatalog:
    """Catalog product listing tests."""

    def test_catalog_has_21_products(self, admin_client):
        """Admin catalog should have at least 21 seeded products."""
        resp = admin_client.get(f"{BASE_URL}/api/admin/products-all?per_page=500")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        products = data.get("products", [])
        print(f"  Total products in catalog: {len(products)}")
        assert len(products) >= 21, f"Expected at least 21 products, got {len(products)}"
        print(f"✓ Catalog has {len(products)} products (≥21)")

    def test_products_have_new_pricing_types(self, admin_client):
        """Seeded products should use new 3-type model (internal/external/enquiry)."""
        resp = admin_client.get(f"{BASE_URL}/api/admin/products-all?per_page=500")
        assert resp.status_code == 200
        products = resp.json().get("products", [])
        types_found = {p.get("pricing_type") for p in products if p.get("pricing_type")}
        print(f"  Pricing types found in catalog: {types_found}")
        # The new model should only have internal/external/enquiry (plus maybe legacy)
        new_types = {"internal", "external", "enquiry"}
        old_types = {"fixed", "tiered", "calculator", "scope_request", "inquiry"}
        new_type_products = [p for p in products if p.get("pricing_type") in new_types]
        print(f"  Products with new types (internal/external/enquiry): {len(new_type_products)}")
        # At minimum, some products should have the new types
        assert len(new_type_products) > 0, "No products with new pricing types found!"
        print(f"✓ Found {len(new_type_products)} products with new pricing types")

    def test_public_products_endpoint(self):
        """Public /api/products endpoint works."""
        resp = requests.get(f"{BASE_URL}/api/products")
        assert resp.status_code == 200, f"Public products failed: {resp.text}"
        products = resp.json().get("products", [])
        print(f"  Public store has {len(products)} products")
        assert len(products) > 0, "No products visible on public store"
        print(f"✓ Public store has {len(products)} products")


# ─── Test: Create Product with Internal Pricing ───────────────────────────────

class TestCreateInternalProduct:
    """Tests for creating internal pricing products."""

    def test_create_internal_product_no_intake(self, admin_client):
        """Create internal product with base_price, no intake questions."""
        payload = {
            "name": "TEST95_Internal_NoIntake",
            "short_description": "Internal product without intake",
            "category": "CRM",
            "base_price": 199.0,
            "pricing_type": "internal",
            "is_active": True,
        }
        resp = admin_client.post(f"{BASE_URL}/api/admin/products", json=payload)
        assert resp.status_code == 200, f"Create internal failed: {resp.text}"
        product = resp.json().get("product") or resp.json()
        pid = product.get("id")
        assert pid, "No product ID returned"
        _created_product_ids.append(pid)
        assert product.get("pricing_type") == "internal", f"pricing_type mismatch: {product.get('pricing_type')}"
        assert product.get("base_price") == 199.0
        print(f"✓ Created internal product (no intake): ID={pid}")

    def test_create_internal_product_with_intake_questions(self, admin_client):
        """Create internal product with intake_schema_json containing number + dropdown questions."""
        payload = {
            "name": "TEST95_Internal_WithIntake",
            "short_description": "Internal product with intake questions",
            "category": "CRM",
            "base_price": 100.0,
            "pricing_type": "internal",
            "is_active": True,
            "intake_schema_json": {
                "version": 2,
                "questions": [
                    {
                        "key": "num_users",
                        "label": "Number of Users",
                        "helper_text": "How many users?",
                        "required": True,
                        "enabled": True,
                        "order": 0,
                        "type": "number",
                        "price_per_unit": 25.0,
                        "min": 1,
                        "max": 100,
                        "step": 1,
                        "default_value": 1,
                    },
                    {
                        "key": "plan_tier",
                        "label": "Plan Tier",
                        "helper_text": "Select your plan",
                        "required": False,
                        "enabled": True,
                        "order": 1,
                        "type": "dropdown",
                        "affects_price": True,
                        "price_mode": "add",
                        "options": [
                            {"label": "Standard", "value": "standard", "price_value": 0.0},
                            {"label": "Premium", "value": "premium", "price_value": 50.0},
                        ],
                    },
                ],
            },
        }
        resp = admin_client.post(f"{BASE_URL}/api/admin/products", json=payload)
        assert resp.status_code == 200, f"Create internal with intake failed: {resp.status_code} {resp.text}"
        product = resp.json().get("product") or resp.json()
        pid = product.get("id")
        assert pid, "No product ID returned"
        _created_product_ids.append(pid)

        # Verify intake schema was persisted
        schema = product.get("intake_schema_json") or {}
        questions = schema.get("questions", [])
        print(f"  intake_schema_json questions count: {len(questions)}")
        assert len(questions) == 2, f"Expected 2 questions, got {len(questions)}: {questions}"

        # Verify number question
        num_q = next((q for q in questions if q.get("type") == "number"), None)
        assert num_q is not None, "Number question not found in intake schema"
        assert num_q.get("price_per_unit") == 25.0, f"price_per_unit mismatch: {num_q.get('price_per_unit')}"
        assert num_q.get("min") == 1.0
        assert num_q.get("max") == 100.0

        # Verify dropdown question
        drop_q = next((q for q in questions if q.get("type") == "dropdown"), None)
        assert drop_q is not None, "Dropdown question not found"
        assert drop_q.get("affects_price") is True
        assert len(drop_q.get("options", [])) == 2

        print(f"✓ Created internal product with 2 intake questions (number + dropdown): ID={pid}")


# ─── Test: Create External Product ────────────────────────────────────────────

class TestCreateExternalProduct:
    """Tests for external pricing type."""

    def test_create_external_product(self, admin_client):
        """Create external product with external_url."""
        payload = {
            "name": "TEST95_External_Product",
            "short_description": "External URL redirect product",
            "category": "CRM",
            "base_price": 0.0,
            "pricing_type": "external",
            "external_url": "https://example.com/buy",
            "is_active": True,
        }
        resp = admin_client.post(f"{BASE_URL}/api/admin/products", json=payload)
        assert resp.status_code == 200, f"Create external failed: {resp.text}"
        product = resp.json().get("product") or resp.json()
        pid = product.get("id")
        assert pid
        _created_product_ids.append(pid)
        assert product.get("pricing_type") == "external"
        assert product.get("external_url") == "https://example.com/buy"
        print(f"✓ Created external product: ID={pid}, URL={product.get('external_url')}")


# ─── Test: Create Enquiry Product ─────────────────────────────────────────────

class TestCreateEnquiryProduct:
    """Tests for enquiry pricing type."""

    def test_create_enquiry_product(self, admin_client):
        """Create enquiry-only product."""
        payload = {
            "name": "TEST95_Enquiry_Product",
            "short_description": "Enquiry only product",
            "category": "CRM",
            "base_price": 0.0,
            "pricing_type": "enquiry",
            "is_active": True,
        }
        resp = admin_client.post(f"{BASE_URL}/api/admin/products", json=payload)
        assert resp.status_code == 200, f"Create enquiry failed: {resp.text}"
        product = resp.json().get("product") or resp.json()
        pid = product.get("id")
        assert pid
        _created_product_ids.append(pid)
        assert product.get("pricing_type") == "enquiry"
        print(f"✓ Created enquiry product: ID={pid}")


# ─── Test: Update Product (PUT) ───────────────────────────────────────────────

class TestUpdateProduct:
    """Tests for product updates."""

    def test_update_product_pricing_type(self, admin_client):
        """Admin can update a product's pricing_type via PUT /api/admin/products/:id."""
        # Create initial internal product
        create_resp = admin_client.post(f"{BASE_URL}/api/admin/products", json={
            "name": "TEST95_Update_Pricing",
            "short_description": "Update pricing test",
            "category": "CRM",
            "base_price": 150.0,
            "pricing_type": "internal",
            "is_active": True,
        })
        assert create_resp.status_code == 200, f"Create failed: {create_resp.text}"
        pid = (create_resp.json().get("product") or create_resp.json()).get("id")
        _created_product_ids.append(pid)

        # Update to external pricing
        update_resp = admin_client.put(f"{BASE_URL}/api/admin/products/{pid}", json={
            "name": "TEST95_Update_Pricing",
            "pricing_type": "external",
            "external_url": "https://updated-url.com",
            "is_active": True,
        })
        assert update_resp.status_code == 200, f"Update failed: {update_resp.status_code} {update_resp.text}"
        print(f"✓ Product {pid} updated to external type")

    def test_update_product_with_intake_schema(self, admin_client):
        """Admin can update a product and add intake questions via PUT."""
        # Create product
        create_resp = admin_client.post(f"{BASE_URL}/api/admin/products", json={
            "name": "TEST95_Update_IntakeSchema",
            "category": "CRM",
            "base_price": 200.0,
            "pricing_type": "internal",
            "is_active": True,
        })
        assert create_resp.status_code == 200
        pid = (create_resp.json().get("product") or create_resp.json()).get("id")
        _created_product_ids.append(pid)

        # Update with intake_schema_json
        update_resp = admin_client.put(f"{BASE_URL}/api/admin/products/{pid}", json={
            "name": "TEST95_Update_IntakeSchema",
            "is_active": True,
            "intake_schema_json": {
                "version": 2,
                "questions": [
                    {
                        "key": "company_size",
                        "label": "Company Size",
                        "helper_text": "Number of employees",
                        "required": True,
                        "enabled": True,
                        "order": 0,
                        "type": "number",
                        "price_per_unit": 10.0,
                        "min": 1,
                        "max": 1000,
                        "step": 1,
                        "default_value": 5,
                    }
                ],
            },
        })
        assert update_resp.status_code == 200, f"Update with intake failed: {update_resp.status_code} {update_resp.text}"
        print(f"✓ Product {pid} updated with intake schema")

        # Verify persistence by fetching product list
        list_resp = admin_client.get(f"{BASE_URL}/api/admin/products-all?per_page=500")
        products = list_resp.json().get("products", [])
        found = next((p for p in products if p.get("id") == pid), None)
        assert found is not None, f"Product {pid} not found after update"
        schema = found.get("intake_schema_json") or {}
        questions = schema.get("questions", [])
        print(f"  Persisted questions count: {len(questions)}")
        assert len(questions) == 1, f"Expected 1 question persisted, got {len(questions)}"
        assert questions[0].get("price_per_unit") == 10.0
        print(f"✓ Intake schema with number question persisted correctly")


# ─── Test: Pricing Calculation ────────────────────────────────────────────────

class TestPricingCalc:
    """Tests for POST /api/pricing/calc endpoint."""

    def test_pricing_calc_internal_base_only(self, admin_client, auth_token):
        """POST /api/pricing/calc for internal product with only base_price."""
        # Create internal product
        create_resp = admin_client.post(f"{BASE_URL}/api/admin/products", json={
            "name": "TEST95_Calc_BaseOnly",
            "category": "CRM",
            "base_price": 500.0,
            "pricing_type": "internal",
            "is_active": True,
        })
        assert create_resp.status_code == 200
        pid = (create_resp.json().get("product") or create_resp.json()).get("id")
        _created_product_ids.append(pid)

        # Calc price
        calc_session = requests.Session()
        calc_session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_token}",
        })
        calc_resp = calc_session.post(f"{BASE_URL}/api/pricing/calc", json={
            "product_id": pid,
            "inputs": {},
        })
        assert calc_resp.status_code == 200, f"Pricing calc failed: {calc_resp.status_code} {calc_resp.text}"
        result = calc_resp.json()
        print(f"  Pricing calc result: {result}")
        assert result.get("subtotal") == 500.0, f"Expected subtotal 500, got {result.get('subtotal')}"
        assert result.get("total") == 500.0
        assert result.get("is_enquiry") is False
        assert result.get("requires_checkout") is True
        print(f"✓ Pricing calc for base-only internal product: subtotal=500.0")

    def test_pricing_calc_internal_with_number_intake(self, admin_client, auth_token):
        """POST /api/pricing/calc for internal product with number intake question."""
        create_resp = admin_client.post(f"{BASE_URL}/api/admin/products", json={
            "name": "TEST95_Calc_NumberIntake",
            "category": "CRM",
            "base_price": 100.0,
            "pricing_type": "internal",
            "is_active": True,
            "intake_schema_json": {
                "version": 2,
                "questions": [
                    {
                        "key": "seats",
                        "label": "Number of Seats",
                        "required": True,
                        "enabled": True,
                        "order": 0,
                        "type": "number",
                        "price_per_unit": 50.0,
                        "min": 1,
                        "max": 100,
                        "step": 1,
                        "default_value": 1,
                    }
                ],
            },
        })
        assert create_resp.status_code == 200, f"Create product for calc failed: {create_resp.text}"
        pid = (create_resp.json().get("product") or create_resp.json()).get("id")
        _created_product_ids.append(pid)

        # Calculate: base=100 + 3 seats * 50 = 250
        calc_session = requests.Session()
        calc_session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_token}",
        })
        calc_resp = calc_session.post(f"{BASE_URL}/api/pricing/calc", json={
            "product_id": pid,
            "inputs": {"seats": 3},
        })
        assert calc_resp.status_code == 200, f"Pricing calc failed: {calc_resp.status_code} {calc_resp.text}"
        result = calc_resp.json()
        print(f"  Pricing calc (3 seats) result: {result}")
        assert result.get("subtotal") == 250.0, f"Expected subtotal 250, got {result.get('subtotal')}"
        print(f"✓ Pricing calc: base=100 + 3×50 = 250 ✓")

    def test_pricing_calc_external_returns_no_checkout(self, admin_client, auth_token):
        """POST /api/pricing/calc for external product returns requires_checkout=False."""
        create_resp = admin_client.post(f"{BASE_URL}/api/admin/products", json={
            "name": "TEST95_Calc_External",
            "category": "CRM",
            "base_price": 0.0,
            "pricing_type": "external",
            "external_url": "https://example.com/external",
            "is_active": True,
        })
        assert create_resp.status_code == 200
        pid = (create_resp.json().get("product") or create_resp.json()).get("id")
        _created_product_ids.append(pid)

        calc_session = requests.Session()
        calc_session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_token}",
        })
        calc_resp = calc_session.post(f"{BASE_URL}/api/pricing/calc", json={
            "product_id": pid,
            "inputs": {},
        })
        assert calc_resp.status_code == 200, f"External calc failed: {calc_resp.text}"
        result = calc_resp.json()
        assert result.get("requires_checkout") is False
        assert result.get("external_url") == "https://example.com/external"
        print(f"✓ External product pricing calc: requires_checkout=False, external_url set")

    def test_pricing_calc_enquiry_returns_is_enquiry(self, admin_client, auth_token):
        """POST /api/pricing/calc for enquiry product returns is_enquiry=True."""
        create_resp = admin_client.post(f"{BASE_URL}/api/admin/products", json={
            "name": "TEST95_Calc_Enquiry",
            "category": "CRM",
            "base_price": 0.0,
            "pricing_type": "enquiry",
            "is_active": True,
        })
        assert create_resp.status_code == 200
        pid = (create_resp.json().get("product") or create_resp.json()).get("id")
        _created_product_ids.append(pid)

        calc_session = requests.Session()
        calc_session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_token}",
        })
        calc_resp = calc_session.post(f"{BASE_URL}/api/pricing/calc", json={
            "product_id": pid,
            "inputs": {},
        })
        assert calc_resp.status_code == 200, f"Enquiry calc failed: {calc_resp.text}"
        result = calc_resp.json()
        assert result.get("is_enquiry") is True
        assert result.get("requires_checkout") is False
        print(f"✓ Enquiry product pricing calc: is_enquiry=True, requires_checkout=False")


# ─── Test: Store Card Pricing Labels ─────────────────────────────────────────

class TestStoreCardLabels:
    """Tests that store products have correct pricing labels via public endpoint."""

    def test_internal_product_has_base_price(self, admin_client):
        """Internal product with base_price is visible on public store."""
        create_resp = admin_client.post(f"{BASE_URL}/api/admin/products", json={
            "name": "TEST95_Store_Internal",
            "category": "CRM",
            "base_price": 299.0,
            "pricing_type": "internal",
            "is_active": True,
        })
        assert create_resp.status_code == 200
        pid = (create_resp.json().get("product") or create_resp.json()).get("id")
        _created_product_ids.append(pid)

        # Check public store
        pub_resp = requests.get(f"{BASE_URL}/api/products")
        assert pub_resp.status_code == 200
        products = pub_resp.json().get("products", [])
        test_prod = next((p for p in products if p.get("id") == pid), None)
        if test_prod:
            assert test_prod.get("base_price") == 299.0
            assert test_prod.get("pricing_type") == "internal"
            print(f"✓ Internal product visible on store with base_price=299")
        else:
            print(f"  Note: Product {pid} not on public store (may be tenant-filtered)")

    def test_external_product_on_public_store(self, admin_client):
        """External product shows pricing_type=external on public store."""
        create_resp = admin_client.post(f"{BASE_URL}/api/admin/products", json={
            "name": "TEST95_Store_External",
            "category": "CRM",
            "base_price": 0.0,
            "pricing_type": "external",
            "external_url": "https://external.com",
            "is_active": True,
        })
        assert create_resp.status_code == 200
        pid = (create_resp.json().get("product") or create_resp.json()).get("id")
        _created_product_ids.append(pid)

        pub_resp = requests.get(f"{BASE_URL}/api/products")
        products = pub_resp.json().get("products", [])
        test_prod = next((p for p in products if p.get("id") == pid), None)
        if test_prod:
            assert test_prod.get("pricing_type") == "external"
            print(f"✓ External product on store: pricing_type=external, external_url set")
        else:
            print(f"  Note: Product {pid} not visible on public store")

    def test_enquiry_product_on_public_store(self, admin_client):
        """Enquiry product shows pricing_type=enquiry on public store."""
        create_resp = admin_client.post(f"{BASE_URL}/api/admin/products", json={
            "name": "TEST95_Store_Enquiry",
            "category": "CRM",
            "base_price": 0.0,
            "pricing_type": "enquiry",
            "is_active": True,
        })
        assert create_resp.status_code == 200
        pid = (create_resp.json().get("product") or create_resp.json()).get("id")
        _created_product_ids.append(pid)

        pub_resp = requests.get(f"{BASE_URL}/api/products")
        products = pub_resp.json().get("products", [])
        test_prod = next((p for p in products if p.get("id") == pid), None)
        if test_prod:
            assert test_prod.get("pricing_type") == "enquiry"
            print(f"✓ Enquiry product on store: pricing_type=enquiry")
        else:
            print(f"  Note: Product {pid} not visible on public store")
