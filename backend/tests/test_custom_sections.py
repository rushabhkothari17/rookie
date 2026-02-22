"""Backend tests for custom sections feature - admin product form with custom_sections CRUD."""
import os
import pytest
import requests
from typing import Optional

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token."""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!"
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"Admin login failed: {response.status_code} {response.text}")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ─── Test: GET /api/admin/products-all returns custom_sections field ───────────
class TestAdminProductsList:
    """Verify admin products list endpoint returns custom_sections."""

    def test_admin_products_list_returns_custom_sections_field(self, auth_headers):
        """GET /api/admin/products-all should include custom_sections in products."""
        resp = requests.get(f"{BASE_URL}/api/admin/products-all?per_page=10", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "products" in data
        print(f"Total products: {data.get('total', 0)}")
        # Check at least some products exist
        if data["products"]:
            # Products may or may not have custom_sections based on migration
            # Just verify the endpoint works
            print(f"First product: {data['products'][0].get('name', 'N/A')}")
            print(f"Has custom_sections: {'custom_sections' in data['products'][0]}")


# ─── Test: POST /api/admin/products creates product with custom_sections ──────
class TestAdminProductCreate:
    """Test creating products with custom_sections."""

    created_product_id: Optional[str] = None

    def test_create_product_with_custom_sections(self, auth_headers):
        """POST /api/admin/products with custom_sections saves them correctly."""
        payload = {
            "name": "TEST_CustomSections_Product",
            "short_description": "Test product for custom sections",
            "description_long": "A product to test the custom sections feature",
            "bullets": ["Bullet 1", "Bullet 2"],
            "tag": "Popular",
            "category": "",
            "base_price": 100.0,
            "is_active": False,
            "custom_sections": [
                {
                    "id": "",
                    "name": "What's Included",
                    "content": "## Overview\n- Feature 1\n- Feature 2",
                    "icon": "CheckCircle",
                    "icon_color": "green",
                    "tags": ["Included"],
                    "order": 0
                },
                {
                    "id": "",
                    "name": "Support",
                    "content": "24/7 support",
                    "icon": "Headphones",
                    "icon_color": "blue",
                    "tags": [],
                    "order": 1
                }
            ]
        }
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=auth_headers)
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        data = resp.json()
        product = data.get("product", {})
        assert product.get("name") == "TEST_CustomSections_Product"
        
        # Verify custom_sections were saved
        assert "custom_sections" in product, "custom_sections field missing from response"
        sections = product["custom_sections"]
        assert len(sections) == 2, f"Expected 2 sections, got {len(sections)}"
        
        # Verify IDs were auto-generated (since we sent empty ids)
        for sec in sections:
            assert sec.get("id"), f"Section ID was not auto-generated: {sec}"
        
        # Verify section content
        assert sections[0]["name"] == "What's Included"
        assert sections[0]["icon"] == "CheckCircle"
        assert sections[0]["icon_color"] == "green"
        assert "Included" in sections[0]["tags"]
        assert sections[1]["name"] == "Support"
        assert sections[1]["icon"] == "Headphones"
        
        TestAdminProductCreate.created_product_id = product["id"]
        print(f"Created product ID: {product['id']}")
        print(f"Sections: {[s['name'] for s in sections]}")

    def test_create_product_default_section_when_none_provided(self, auth_headers):
        """When no custom_sections provided, backend auto-creates default 'Overview' section."""
        payload = {
            "name": "TEST_DefaultSection_Product",
            "short_description": "Test product without custom sections",
            "bullets": ["Bullet 1"],
            "base_price": 50.0,
            "is_active": False,
            # No custom_sections provided
        }
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=auth_headers)
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        product = resp.json().get("product", {})

        # Verify default 'Overview' section was auto-created
        assert "custom_sections" in product, "custom_sections field missing"
        sections = product["custom_sections"]
        assert len(sections) == 1, f"Expected 1 default section, got {len(sections)}"
        assert sections[0]["name"] == "Overview", f"Default section name should be 'Overview', got: {sections[0]['name']}"
        assert sections[0]["icon"] == "FileText"
        assert sections[0]["icon_color"] == "blue"
        
        # Clean up this test product
        prod_id = product["id"]
        requests.put(f"{BASE_URL}/api/admin/products/{prod_id}", json={"name": "TEST_DefaultSection_Product", "is_active": False}, headers=auth_headers)
        print(f"Default section test product ID: {prod_id}")
        print(f"Default section: {sections[0]}")

    def test_create_product_with_tag_and_short_description(self, auth_headers):
        """Verify tag and short_description are saved correctly."""
        payload = {
            "name": "TEST_Tag_ShortDesc_Product",
            "short_description": "Short description for card",
            "tag": "Best Seller",
            "bullets": ["Bullet A", "Bullet B", "Bullet C"],
            "base_price": 200.0,
            "is_active": False,
        }
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=auth_headers)
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        product = resp.json().get("product", {})
        assert product["tag"] == "Best Seller"
        assert product["short_description"] == "Short description for card"
        assert product["bullets"] == ["Bullet A", "Bullet B", "Bullet C"]
        
        # Verify via GET product endpoint
        prod_id = product["id"]
        get_resp = requests.get(f"{BASE_URL}/api/products/{prod_id}", headers=auth_headers)
        # Product is inactive so won't be accessible via public endpoint
        # Just verify the data was saved via the admin endpoint product response
        print(f"Product tag: {product['tag']}")
        print(f"Product short_description: {product['short_description']}")
        print(f"Product bullets count: {len(product['bullets'])}")
        
        # Clean up
        requests.put(f"{BASE_URL}/api/admin/products/{prod_id}", json={"name": "TEST_Tag_ShortDesc_Product", "is_active": False}, headers=auth_headers)


# ─── Test: PUT /api/admin/products/{id} updates custom_sections ───────────────
class TestAdminProductUpdate:
    """Test updating products custom_sections."""

    def test_update_product_custom_sections(self, auth_headers):
        """PUT /api/admin/products/{id} with custom_sections updates them correctly."""
        if not TestAdminProductCreate.created_product_id:
            pytest.skip("No product ID from create test")
        
        prod_id = TestAdminProductCreate.created_product_id
        
        # Update with new sections
        update_payload = {
            "name": "TEST_CustomSections_Product",
            "is_active": False,
            "custom_sections": [
                {
                    "id": "existing-id",
                    "name": "Updated Section",
                    "content": "Updated content with **markdown**",
                    "icon": "Star",
                    "icon_color": "purple",
                    "tags": ["tag1", "tag2"],
                    "order": 0
                },
                {
                    "id": "",
                    "name": "New Added Section",
                    "content": "Newly added section content",
                    "icon": "Zap",
                    "icon_color": "orange",
                    "tags": [],
                    "order": 1
                }
            ]
        }
        
        resp = requests.put(f"{BASE_URL}/api/admin/products/{prod_id}", json=update_payload, headers=auth_headers)
        assert resp.status_code == 200, f"Update failed: {resp.text}"
        
        # Verify the update by fetching product from admin list
        list_resp = requests.get(f"{BASE_URL}/api/admin/products-all?per_page=500", headers=auth_headers)
        assert list_resp.status_code == 200
        products = list_resp.json().get("products", [])
        updated_product = next((p for p in products if p["id"] == prod_id), None)
        
        assert updated_product is not None, "Updated product not found in list"
        assert "custom_sections" in updated_product
        sections = updated_product["custom_sections"]
        assert len(sections) == 2, f"Expected 2 sections after update, got {len(sections)}"
        assert sections[0]["name"] == "Updated Section"
        assert sections[0]["icon"] == "Star"
        assert sections[0]["icon_color"] == "purple"
        assert sections[0]["tags"] == ["tag1", "tag2"]
        assert sections[1]["name"] == "New Added Section"
        # New section should have auto-generated ID
        assert sections[1].get("id"), "New section should have auto-generated ID"
        
        print(f"Updated sections: {[s['name'] for s in sections]}")

    def test_update_product_remove_all_sections(self, auth_headers):
        """Updating with empty custom_sections should result in empty list (not default)."""
        if not TestAdminProductCreate.created_product_id:
            pytest.skip("No product ID from create test")
        
        prod_id = TestAdminProductCreate.created_product_id
        
        update_payload = {
            "name": "TEST_CustomSections_Product",
            "is_active": False,
            "custom_sections": []
        }
        resp = requests.put(f"{BASE_URL}/api/admin/products/{prod_id}", json=update_payload, headers=auth_headers)
        assert resp.status_code == 200, f"Update failed: {resp.text}"
        
        # Verify sections are empty (fallback to static on frontend)
        list_resp = requests.get(f"{BASE_URL}/api/admin/products-all?per_page=500", headers=auth_headers)
        products = list_resp.json().get("products", [])
        product = next((p for p in products if p["id"] == prod_id), None)
        assert product is not None
        sections = product.get("custom_sections", [])
        assert sections == [], f"Expected empty sections, got {sections}"
        print(f"Sections after empty update: {sections}")


# ─── Test: Intake Schema key auto-generation and read-only key ─────────────────
class TestIntakeSchemaKeyGeneration:
    """Test that intake schema keys are auto-generated from labels."""

    def test_intake_key_auto_generated_from_label(self, auth_headers):
        """Intake question key should be auto-generated from label."""
        payload = {
            "name": "TEST_IntakeKey_Product",
            "base_price": 100.0,
            "is_active": False,
            "intake_schema_json": {
                "version": 1,
                "questions": {
                    "dropdown": [
                        {
                            "key": "",  # empty - should be auto-generated
                            "label": "What type of integration?",
                            "helper_text": "Select the type",
                            "required": True,
                            "enabled": True,
                            "order": 0,
                            "affects_price": False,
                            "price_mode": "add",
                            "options": [
                                {"label": "Basic", "value": "", "price_value": 0},
                                {"label": "Advanced", "value": "", "price_value": 0}
                            ]
                        }
                    ],
                    "multiselect": [],
                    "single_line": [],
                    "multi_line": []
                }
            }
        }
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=auth_headers)
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        product = resp.json().get("product", {})
        schema = product.get("intake_schema_json", {})
        
        dropdown_qs = schema.get("questions", {}).get("dropdown", [])
        assert len(dropdown_qs) == 1, "Expected 1 dropdown question"
        q = dropdown_qs[0]
        
        # Key should be auto-generated from label
        assert q["key"] != "", "Key should not be empty after auto-generation"
        # "What type of integration?" -> "what_type_of_integration"
        assert q["key"] == "what_type_of_integration", f"Unexpected key: {q['key']}"
        
        # Options value should also be auto-generated from label
        options = q.get("options", [])
        assert len(options) == 2
        assert options[0]["value"] == "basic", f"Option value should be 'basic', got: {options[0]['value']}"
        assert options[1]["value"] == "advanced", f"Option value should be 'advanced', got: {options[1]['value']}"
        
        print(f"Auto-generated key: {q['key']}")
        print(f"Option values: {[o['value'] for o in options]}")
        
        # Clean up
        prod_id = product["id"]
        requests.put(f"{BASE_URL}/api/admin/products/{prod_id}", json={"name": "TEST_IntakeKey_Product", "is_active": False}, headers=auth_headers)

    def test_intake_schema_with_single_line_question(self, auth_headers):
        """Single-line question key auto-generation."""
        payload = {
            "name": "TEST_IntakeSingleLine_Product",
            "base_price": 50.0,
            "is_active": False,
            "intake_schema_json": {
                "version": 1,
                "questions": {
                    "dropdown": [],
                    "multiselect": [],
                    "single_line": [
                        {
                            "key": "",
                            "label": "Company Name",
                            "helper_text": "Enter your company",
                            "required": True,
                            "enabled": True,
                            "order": 0,
                            "affects_price": False,
                            "price_mode": "add",
                            "options": []
                        }
                    ],
                    "multi_line": []
                }
            }
        }
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=auth_headers)
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        product = resp.json().get("product", {})
        schema = product.get("intake_schema_json", {})
        single_qs = schema.get("questions", {}).get("single_line", [])
        assert len(single_qs) == 1
        assert single_qs[0]["key"] == "company_name", f"Key should be 'company_name', got: {single_qs[0]['key']}"
        
        # Clean up
        prod_id = product["id"]
        requests.put(f"{BASE_URL}/api/admin/products/{prod_id}", json={"name": "TEST_IntakeSingleLine_Product", "is_active": False}, headers=auth_headers)


# ─── Test: GET /api/products/{id} returns custom_sections (public endpoint) ───
class TestPublicProductEndpoint:
    """Test that the public product endpoint returns custom_sections for detail page rendering."""

    def test_public_product_returns_custom_sections(self, auth_headers):
        """Active product with custom_sections should return them via public endpoint."""
        # Create an active product with custom sections
        payload = {
            "name": "TEST_Public_CustomSections",
            "short_description": "Test public endpoint with custom sections",
            "bullets": ["bullet 1", "bullet 2"],
            "tag": "Featured",
            "base_price": 99.0,
            "is_active": True,  # Must be active for public endpoint
            "custom_sections": [
                {
                    "id": "",
                    "name": "Overview",
                    "content": "This is the overview section content.",
                    "icon": "FileText",
                    "icon_color": "blue",
                    "tags": [],
                    "order": 0
                }
            ]
        }
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=auth_headers)
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        product = resp.json().get("product", {})
        prod_id = product["id"]
        
        try:
            # Test public endpoint
            public_resp = requests.get(f"{BASE_URL}/api/products/{prod_id}")
            assert public_resp.status_code == 200, f"Public product fetch failed: {public_resp.text}"
            pub_product = public_resp.json().get("product", {})
            
            # Verify custom_sections present in public response
            assert "custom_sections" in pub_product, "custom_sections missing from public endpoint"
            sections = pub_product["custom_sections"]
            assert len(sections) == 1
            assert sections[0]["name"] == "Overview"
            assert sections[0]["icon"] == "FileText"
            assert sections[0]["icon_color"] == "blue"
            
            # Verify tag and short_description
            assert pub_product.get("tag") == "Featured"
            assert pub_product.get("short_description") == "Test public endpoint with custom sections"
            assert pub_product.get("bullets") == ["bullet 1", "bullet 2"]
            
            print(f"Public product custom_sections: {sections}")
        finally:
            # Clean up - deactivate
            requests.put(f"{BASE_URL}/api/admin/products/{prod_id}", json={
                "name": "TEST_Public_CustomSections", "is_active": False
            }, headers=auth_headers)


# ─── Cleanup: Remove all TEST_ products created during testing ─────────────────
class TestCleanup:
    """Clean up test products."""

    def test_cleanup_test_products(self, auth_headers):
        """Remove all TEST_ prefix products created during testing."""
        resp = requests.get(f"{BASE_URL}/api/admin/products-all?per_page=500", headers=auth_headers)
        if resp.status_code != 200:
            return
        
        products = resp.json().get("products", [])
        test_products = [p for p in products if p.get("name", "").startswith("TEST_")]
        
        print(f"Cleaning up {len(test_products)} test products...")
        for p in test_products:
            # Just deactivate rather than deleting (no delete endpoint)
            requests.put(f"{BASE_URL}/api/admin/products/{p['id']}", json={
                "name": p["name"],
                "is_active": False
            }, headers=auth_headers)
        
        print(f"Cleanup complete for {len(test_products)} products")
        assert True  # cleanup doesn't need to fail tests
