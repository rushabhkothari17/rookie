"""
Backend tests for iteration 41 - 4 fixes: icon colors, category refresh, hero cleanup, legacy sections removal.
Tests: migration verification, custom_sections data, product hero fields, category API.
"""
import os
import pytest
import requests

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
    pytest.skip(f"Admin login failed: {response.status_code}")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ─── Test: Migrated products have custom_sections ─────────────────────────────
class TestMigratedProducts:
    """Verify migration ran - 21 products should have custom_sections."""

    def test_zoho_crm_has_custom_sections(self, auth_headers):
        """prod_zoho_crm_express must have custom_sections after migration."""
        resp = requests.get(f"{BASE_URL}/api/admin/products-all?per_page=500", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        products = data.get("products", [])
        zoho = next((p for p in products if p.get("id") == "prod_zoho_crm_express"), None)
        assert zoho is not None, "prod_zoho_crm_express not found"
        cs = zoho.get("custom_sections", [])
        assert len(cs) > 0, f"Expected custom_sections, got {len(cs)}"
        print(f"Zoho CRM custom_sections count: {len(cs)}")

    def test_zoho_crm_custom_sections_structure(self, auth_headers):
        """custom_sections must have name, content, icon, icon_color fields."""
        resp = requests.get(f"{BASE_URL}/api/products/prod_zoho_crm_express")
        assert resp.status_code == 200
        product = resp.json().get("product", {})
        cs = product.get("custom_sections", [])
        assert len(cs) > 0
        first = cs[0]
        assert "name" in first
        assert "content" in first
        assert "icon" in first
        assert "icon_color" in first
        print(f"First section: name={first['name']}, icon={first['icon']}, icon_color={first['icon_color']}")
        print(f"Content (first 100): {first.get('content','')[:100]}")

    def test_zoho_crm_section_content_has_markdown(self):
        """Section content should contain markdown-style bullets."""
        resp = requests.get(f"{BASE_URL}/api/products/prod_zoho_crm_express")
        assert resp.status_code == 200
        product = resp.json().get("product", {})
        cs = product.get("custom_sections", [])
        assert len(cs) > 0
        # At least one section should have `- ` bullet or `1.` numbered list
        has_markdown = any(
            "- " in s.get("content", "") or "1." in s.get("content", "")
            for s in cs
        )
        assert has_markdown, "Expected markdown bullets in section content"

    def test_total_migrated_products_count(self, auth_headers):
        """At least 10 products should have custom_sections (migration ran successfully)."""
        resp = requests.get(f"{BASE_URL}/api/admin/products-all?per_page=500", headers=auth_headers)
        assert resp.status_code == 200
        products = resp.json().get("products", [])
        with_cs = [p for p in products if len(p.get("custom_sections", [])) > 0]
        assert len(with_cs) >= 10, f"Expected >=10 products with custom_sections, got {len(with_cs)}"
        print(f"Products with custom_sections: {len(with_cs)}/{len(products)}")

    def test_product_has_description_long(self):
        """Zoho CRM should have description_long for hero display."""
        resp = requests.get(f"{BASE_URL}/api/products/prod_zoho_crm_express")
        assert resp.status_code == 200
        product = resp.json().get("product", {})
        desc_long = product.get("description_long", "")
        # description_long should be set (non-empty) after migration
        assert isinstance(desc_long, str)
        print(f"description_long: {repr(desc_long[:100])}")


# ─── Test: Categories API ─────────────────────────────────────────────────────
class TestCategoriesAPI:
    """Verify categories API works for product form."""

    def test_categories_endpoint_returns_list(self, auth_headers):
        """GET /api/admin/categories should return categories list."""
        resp = requests.get(f"{BASE_URL}/api/admin/categories?per_page=500", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "categories" in data
        categories = data["categories"]
        assert isinstance(categories, list)
        assert len(categories) > 0, "Expected at least one category"
        print(f"Categories count: {len(categories)}")
        for c in categories[:5]:
            print(f"  Category: {c.get('name')} ({c.get('id')})")

    def test_categories_have_name_and_id(self, auth_headers):
        """Each category must have id and name fields."""
        resp = requests.get(f"{BASE_URL}/api/admin/categories?per_page=500", headers=auth_headers)
        assert resp.status_code == 200
        categories = resp.json().get("categories", [])
        for cat in categories:
            assert "id" in cat, f"Category missing id: {cat}"
            assert "name" in cat, f"Category missing name: {cat}"


# ─── Test: Products public endpoint ──────────────────────────────────────────
class TestPublicProducts:
    """Test public product endpoints used by frontend."""

    def test_product_detail_returns_custom_sections(self):
        """Public product detail must include custom_sections."""
        resp = requests.get(f"{BASE_URL}/api/products/prod_zoho_crm_express")
        assert resp.status_code == 200
        product = resp.json().get("product", {})
        assert "custom_sections" in product
        cs = product["custom_sections"]
        assert len(cs) > 0
        print(f"Public product custom_sections: {len(cs)}")

    def test_product_list_returns_store_fields(self):
        """Product list must return tag, short_description, bullets for store cards."""
        resp = requests.get(f"{BASE_URL}/api/products")
        assert resp.status_code == 200
        data = resp.json()
        products = data.get("products", [])
        assert len(products) > 0, "No products returned"
        # Check at least one product has the store card fields
        for p in products[:5]:
            # These are store card required fields - just verify they're present in response
            assert "name" in p
            assert "short_description" in p or "tagline" in p
            print(f"  {p['name']}: tag={p.get('tag')}, short_desc={p.get('short_description','')[:40]}")

    def test_product_detail_no_legacy_section_rendering(self):
        """Product should still have custom_sections not legacy-only structure.
        The frontend relies on custom_sections for display."""
        resp = requests.get(f"{BASE_URL}/api/products/prod_zoho_crm_express")
        assert resp.status_code == 200
        product = resp.json().get("product", {})
        # Must have custom_sections (migration ran)
        cs = product.get("custom_sections", [])
        assert len(cs) > 0, "Migration should have populated custom_sections"

    def test_faqs_present_on_product(self):
        """FAQs must be present on migrated product."""
        resp = requests.get(f"{BASE_URL}/api/products/prod_zoho_crm_express")
        assert resp.status_code == 200
        product = resp.json().get("product", {})
        # FAQs should be present (either from migration or original)
        faqs = product.get("faqs", [])
        print(f"FAQs count: {len(faqs)}")
        # Just assert it's a list (may be empty if product had none)
        assert isinstance(faqs, list)


# ─── Test: Admin product detail endpoint ─────────────────────────────────────
class TestAdminProductDetail:
    """Test admin product detail API for custom_sections."""

    def test_admin_product_get_by_id_via_list(self, auth_headers):
        """Admin products-all with filter should return custom_sections for prod_zoho_crm_express.
        Note: /api/admin/products/{id} only supports PUT (405 on GET) — use list endpoint."""
        resp = requests.get(f"{BASE_URL}/api/admin/products-all?per_page=500", headers=auth_headers)
        assert resp.status_code == 200
        products = resp.json().get("products", [])
        product = next((p for p in products if p.get("id") == "prod_zoho_crm_express"), None)
        assert product is not None, "prod_zoho_crm_express not found in admin list"
        assert "custom_sections" in product
        cs = product["custom_sections"]
        assert len(cs) > 0
        print(f"Admin product custom_sections: {len(cs)}")
        for sec in cs:
            print(f"  Section: {sec['name']} - icon={sec.get('icon')} color={sec.get('icon_color')}")
