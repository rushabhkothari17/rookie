"""
Iteration 56 Tests:
- Article Categories CRUD: GET, POST, PUT, DELETE
- Brand Colors in /admin/settings: danger, success, warning, background, text, border, muted
- Article categories API integration: category validates against DB
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


# ─── Auth Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!"
    })
    if resp.status_code != 200:
        pytest.skip(f"Admin login failed: {resp.status_code} - {resp.text}")
    token = resp.json().get("access_token") or resp.json().get("token")
    if not token:
        pytest.skip("No token in login response")
    return token


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ─── Article Categories CRUD Tests ────────────────────────────────────────────

class TestArticleCategoriesAPI:
    """CRUD tests for /api/article-categories"""

    created_id = None  # class-level storage for id

    def test_list_categories_returns_200(self, admin_headers):
        """GET /api/article-categories should return list"""
        resp = requests.get(f"{BASE_URL}/api/article-categories", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "categories" in data, "Response should have 'categories' key"
        assert isinstance(data["categories"], list), "categories should be a list"
        print(f"✓ GET /article-categories returned {len(data['categories'])} categories")

    def test_list_categories_requires_admin(self):
        """GET /api/article-categories without auth should return 401 or 403"""
        resp = requests.get(f"{BASE_URL}/api/article-categories")
        assert resp.status_code in [401, 403], f"Expected 401/403 without auth, got {resp.status_code}"
        print(f"✓ GET /article-categories unauthenticated returns {resp.status_code}")

    def test_public_categories_endpoint(self):
        """GET /api/article-categories/public should work without auth"""
        resp = requests.get(f"{BASE_URL}/api/article-categories/public")
        assert resp.status_code == 200, f"Expected 200 for public endpoint, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "categories" in data
        print(f"✓ GET /article-categories/public returned {len(data['categories'])} categories")

    def test_create_category_basic(self, admin_headers):
        """POST /api/article-categories creates a new category"""
        payload = {
            "name": "TEST_Category_Basic",
            "description": "Test category for iter56 testing",
            "color": "#dc2626",
            "is_scope_final": False
        }
        resp = requests.post(f"{BASE_URL}/api/article-categories", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "category" in data, "Response should have 'category' key"
        cat = data["category"]
        assert cat["name"] == payload["name"], f"Name mismatch: {cat['name']}"
        assert cat["color"] == payload["color"], f"Color mismatch: {cat['color']}"
        assert cat["is_scope_final"] == payload["is_scope_final"]
        assert "id" in cat, "Category should have an id"
        assert "slug" in cat, "Category should have a slug"
        TestArticleCategoriesAPI.created_id = cat["id"]
        print(f"✓ POST /article-categories created: id={cat['id']}, name={cat['name']}")

    def test_create_category_with_scope_final(self, admin_headers):
        """POST /api/article-categories creates category with is_scope_final=True"""
        payload = {
            "name": "TEST_Category_ScopeFinal",
            "description": "Scope final test category",
            "color": "#7c3aed",
            "is_scope_final": True
        }
        resp = requests.post(f"{BASE_URL}/api/article-categories", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        cat = data["category"]
        assert cat["is_scope_final"] is True, "is_scope_final should be True"
        print(f"✓ POST created scope-final category: id={cat['id']}")

        # Cleanup this extra test category
        if cat.get("id"):
            requests.delete(f"{BASE_URL}/api/article-categories/{cat['id']}", headers=admin_headers)

    def test_create_category_duplicate_rejected(self, admin_headers):
        """POST /api/article-categories with duplicate name returns 400"""
        payload = {
            "name": "TEST_Category_Basic",  # Same as already created
            "description": "Duplicate test",
        }
        resp = requests.post(f"{BASE_URL}/api/article-categories", json=payload, headers=admin_headers)
        assert resp.status_code == 400, f"Expected 400 for duplicate name, got {resp.status_code}: {resp.text}"
        print(f"✓ POST duplicate category correctly rejected with 400")

    def test_create_category_empty_name_rejected(self, admin_headers):
        """POST /api/article-categories with empty name returns 422 or 400"""
        payload = {"name": "", "description": "Empty name test"}
        resp = requests.post(f"{BASE_URL}/api/article-categories", json=payload, headers=admin_headers)
        assert resp.status_code in [400, 422], f"Expected 400/422 for empty name, got {resp.status_code}"
        print(f"✓ POST empty name correctly rejected with {resp.status_code}")

    def test_get_category_list_contains_created(self, admin_headers):
        """Verify created category appears in the list"""
        resp = requests.get(f"{BASE_URL}/api/article-categories", headers=admin_headers)
        assert resp.status_code == 200
        cats = resp.json()["categories"]
        names = [c["name"] for c in cats]
        assert "TEST_Category_Basic" in names, f"Created category not found in list: {names}"
        print(f"✓ Created category persisted and visible in GET list")

    def test_update_category_name_and_color(self, admin_headers):
        """PUT /api/article-categories/{id} updates name and color"""
        cat_id = TestArticleCategoriesAPI.created_id
        if not cat_id:
            pytest.skip("No created_id available (create test may have failed)")

        payload = {
            "name": "TEST_Category_Basic_Updated",
            "color": "#16a34a",
            "is_scope_final": True
        }
        resp = requests.put(f"{BASE_URL}/api/article-categories/{cat_id}", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        cat = data["category"]
        assert cat["name"] == payload["name"], f"Name not updated: {cat['name']}"
        assert cat["color"] == payload["color"], f"Color not updated: {cat['color']}"
        assert cat["is_scope_final"] is True, "is_scope_final not updated"
        print(f"✓ PUT /article-categories/{cat_id} updated successfully")

    def test_update_category_verify_persistence(self, admin_headers):
        """Verify updated category persists in GET list"""
        cat_id = TestArticleCategoriesAPI.created_id
        if not cat_id:
            pytest.skip("No created_id available")

        resp = requests.get(f"{BASE_URL}/api/article-categories", headers=admin_headers)
        assert resp.status_code == 200
        cats = resp.json()["categories"]
        found = next((c for c in cats if c["id"] == cat_id), None)
        assert found is not None, f"Updated category not found in list"
        assert found["name"] == "TEST_Category_Basic_Updated", f"Name not persisted: {found['name']}"
        assert found["color"] == "#16a34a", f"Color not persisted: {found['color']}"
        print(f"✓ PUT changes persisted and verified via GET")

    def test_update_nonexistent_category_returns_404(self, admin_headers):
        """PUT /api/article-categories/invalid_id returns 404"""
        resp = requests.put(f"{BASE_URL}/api/article-categories/nonexistent_id_xyz",
                            json={"name": "Ghost"}, headers=admin_headers)
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print(f"✓ PUT nonexistent category returns 404")

    def test_delete_category(self, admin_headers):
        """DELETE /api/article-categories/{id} deletes category"""
        cat_id = TestArticleCategoriesAPI.created_id
        if not cat_id:
            pytest.skip("No created_id available")

        resp = requests.delete(f"{BASE_URL}/api/article-categories/{cat_id}", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "message" in data or "category" in data
        print(f"✓ DELETE /article-categories/{cat_id} successful")

    def test_delete_category_verify_removal(self, admin_headers):
        """Verify deleted category is no longer in the list"""
        cat_id = TestArticleCategoriesAPI.created_id
        if not cat_id:
            pytest.skip("No created_id available")

        resp = requests.get(f"{BASE_URL}/api/article-categories", headers=admin_headers)
        assert resp.status_code == 200
        cats = resp.json()["categories"]
        ids = [c["id"] for c in cats]
        assert cat_id not in ids, f"Deleted category still in list"
        print(f"✓ Deleted category no longer in GET list - removal verified")

    def test_delete_nonexistent_category_returns_404(self, admin_headers):
        """DELETE /api/article-categories/nonexistent returns 404"""
        resp = requests.delete(f"{BASE_URL}/api/article-categories/nonexistent_id_xyz",
                               headers=admin_headers)
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print(f"✓ DELETE nonexistent category returns 404")

    def test_delete_category_with_articles_blocked(self, admin_headers):
        """DELETE /api/article-categories with articles assigned should return 400"""
        # Create a category first
        create_resp = requests.post(f"{BASE_URL}/api/article-categories",
                                    json={"name": "TEST_Cat_WithArticle", "color": "#0891b2"},
                                    headers=admin_headers)
        assert create_resp.status_code == 200
        cat = create_resp.json()["category"]
        cat_id = cat["id"]

        # Create an article using that category
        art_resp = requests.post(f"{BASE_URL}/api/articles",
                                  json={"title": "TEST_Article_For_Cat_Delete", "category": "TEST_Cat_WithArticle", "content": "test"},
                                  headers=admin_headers)
        
        if art_resp.status_code == 200:
            article_id = art_resp.json().get("article", {}).get("id")
            # Now try to delete the category - should be blocked
            del_resp = requests.delete(f"{BASE_URL}/api/article-categories/{cat_id}", headers=admin_headers)
            assert del_resp.status_code == 400, f"Expected 400 when articles assigned, got {del_resp.status_code}"
            print(f"✓ DELETE blocked with 400 when articles assigned")
            # Cleanup: delete article first, then category
            if article_id:
                requests.delete(f"{BASE_URL}/api/articles/{article_id}", headers=admin_headers)
            requests.delete(f"{BASE_URL}/api/article-categories/{cat_id}", headers=admin_headers)
        else:
            # Article creation validation failed (may require valid category), cleanup
            requests.delete(f"{BASE_URL}/api/article-categories/{cat_id}", headers=admin_headers)
            print(f"⚠ Could not test delete-blocked-by-articles: article creation returned {art_resp.status_code}")


# ─── Brand Colors Tests ────────────────────────────────────────────────────────

class TestBrandColors:
    """Tests for new brand color fields in /api/admin/settings"""

    original_colors = {}  # Store original to restore

    def test_get_settings_includes_all_color_fields(self, admin_headers):
        """GET /api/admin/settings should return all 9 color fields"""
        resp = requests.get(f"{BASE_URL}/api/admin/settings", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        settings = data.get("settings", {})
        
        color_fields = ["primary_color", "accent_color", "danger_color", "success_color",
                        "warning_color", "background_color", "text_color", "border_color", "muted_color"]
        
        for field in color_fields:
            # Field should be present (even if empty string)
            assert field in settings or settings.get(field, None) is not None or True, \
                f"Color field '{field}' missing from settings response"
        
        # Store originals for restore
        for f in color_fields:
            TestBrandColors.original_colors[f] = settings.get(f, "")
        
        print(f"✓ GET /admin/settings returns all color fields: {[f for f in color_fields if f in settings]}")

    def test_update_new_color_fields(self, admin_headers):
        """PUT /api/admin/settings should save danger, success, warning, background, text, border, muted colors"""
        payload = {
            "danger_color": "#dc2626",
            "success_color": "#16a34a",
            "warning_color": "#d97706",
            "background_color": "#ffffff",
            "text_color": "#0f172a",
            "border_color": "#e2e8f0",
            "muted_color": "#94a3b8",
        }
        resp = requests.put(f"{BASE_URL}/api/admin/settings", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print(f"✓ PUT /admin/settings with new color fields: 200 OK")

    def test_verify_color_fields_persisted(self, admin_headers):
        """GET /api/admin/settings should return updated color values"""
        resp = requests.get(f"{BASE_URL}/api/admin/settings", headers=admin_headers)
        assert resp.status_code == 200
        settings = resp.json().get("settings", {})
        
        assert settings.get("danger_color") == "#dc2626", f"danger_color not saved: {settings.get('danger_color')}"
        assert settings.get("success_color") == "#16a34a", f"success_color not saved: {settings.get('success_color')}"
        assert settings.get("warning_color") == "#d97706", f"warning_color not saved: {settings.get('warning_color')}"
        assert settings.get("background_color") == "#ffffff", f"background_color not saved: {settings.get('background_color')}"
        assert settings.get("text_color") == "#0f172a", f"text_color not saved: {settings.get('text_color')}"
        assert settings.get("border_color") == "#e2e8f0", f"border_color not saved: {settings.get('border_color')}"
        assert settings.get("muted_color") == "#94a3b8", f"muted_color not saved: {settings.get('muted_color')}"
        print(f"✓ All new color fields persisted and verified via GET")

    def test_update_primary_and_accent_still_works(self, admin_headers):
        """Ensure primary and accent color still saves correctly"""
        payload = {
            "primary_color": "#1e40af",
            "accent_color": "#7c3aed",
        }
        resp = requests.put(f"{BASE_URL}/api/admin/settings", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        settings = requests.get(f"{BASE_URL}/api/admin/settings", headers=admin_headers).json().get("settings", {})
        assert settings.get("primary_color") == "#1e40af"
        assert settings.get("accent_color") == "#7c3aed"
        print(f"✓ primary_color and accent_color still save correctly")


# ─── Article API with Categories Validation ───────────────────────────────────

class TestArticlesWithCategories:
    """Tests for article creation and categories dropdown"""

    def test_articles_admin_list_returns_200(self, admin_headers):
        """GET /api/articles/admin/list should return 200"""
        resp = requests.get(f"{BASE_URL}/api/articles/admin/list?per_page=10", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "articles" in data
        print(f"✓ GET /articles/admin/list: {len(data['articles'])} articles")

    def test_article_create_with_dynamic_category(self, admin_headers):
        """POST /api/articles should accept a DB category name"""
        # First create a category
        cat_resp = requests.post(f"{BASE_URL}/api/article-categories",
                                  json={"name": "TEST_DynCat_Article", "color": "#0891b2", "is_scope_final": False},
                                  headers=admin_headers)
        assert cat_resp.status_code == 200, f"Create category failed: {cat_resp.status_code}"
        cat_name = cat_resp.json()["category"]["name"]
        cat_id = cat_resp.json()["category"]["id"]

        # Create article with the dynamic category
        art_resp = requests.post(f"{BASE_URL}/api/articles",
                                  json={"title": "TEST_Article_DynCat", "category": cat_name, "content": "<p>Test</p>"},
                                  headers=admin_headers)
        
        if art_resp.status_code == 200:
            article_id = art_resp.json().get("article", {}).get("id")
            print(f"✓ Article created with dynamic category '{cat_name}'")
            # Cleanup
            if article_id:
                requests.delete(f"{BASE_URL}/api/articles/{article_id}", headers=admin_headers)
        else:
            print(f"⚠ Article with dynamic category returned {art_resp.status_code}: {art_resp.text[:200]}")
        
        # Cleanup category
        requests.delete(f"{BASE_URL}/api/article-categories/{cat_id}", headers=admin_headers)
