"""Backend tests for iteration 52 new features:
1. GoCardless Callback Page moved to Payments section (frontend-only change)
2. Admin sidebar dark active state (frontend-only)
3. References unified (Zoho refs now regular website_references)
4. Customers pagination changed from 20 to 10 (frontend-only, backend still accepts per_page param)
5. Article Templates: CRUD + 4 defaults
6. Article download endpoints: PDF and DOCX
"""
import os
import pytest
import requests

# Load env from frontend/.env if not set
def _get_base_url():
    url = os.environ.get("REACT_APP_BACKEND_URL", "")
    if not url:
        env_path = os.path.join(os.path.dirname(__file__), "../../../frontend/.env")
        try:
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        url = line.split("=", 1)[1].strip()
                        break
        except FileNotFoundError:
            pass
    return url.rstrip("/")

BASE_URL = _get_base_url()
ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"
# Test article ID from context (starts with 32c38143)
TEST_ARTICLE_ID_PREFIX = "32c38143"


@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token."""
    res = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if res.status_code != 200:
        pytest.skip(f"Auth failed: {res.status_code} {res.text[:200]}")
    return res.json().get("token")


@pytest.fixture(scope="module")
def admin_headers(auth_token):
    """Admin auth headers."""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def test_article_id(admin_headers):
    """Get a test article ID to use for download tests."""
    # First try to find article starting with TEST_ARTICLE_ID_PREFIX
    res = requests.get(f"{BASE_URL}/api/articles/admin/list?per_page=50", headers=admin_headers)
    assert res.status_code == 200, f"Failed to list articles: {res.text[:200]}"
    articles = res.data.get("articles", []) if hasattr(res, 'data') else res.json().get("articles", [])
    for a in articles:
        if a["id"].startswith(TEST_ARTICLE_ID_PREFIX):
            return a["id"]
    # If not found, create one
    create_res = requests.post(f"{BASE_URL}/api/articles", json={
        "title": "TEST_Download Article",
        "category": "Blog",
        "content": "<h1>Test</h1><p>This is test content for download.</p>",
        "visibility": "all",
        "restricted_to": []
    }, headers=admin_headers)
    if create_res.status_code == 200:
        return create_res.json()["article"]["id"]
    # If creation also failed, just return None
    return None


# ─── Test: References - Zoho links seeded as regular refs ──────────────────────

class TestReferencesUnified:
    """Test that Zoho links are seeded as regular references in the unified table."""

    def test_list_references_returns_all_refs(self, admin_headers):
        """GET /api/admin/references should return references including Zoho ones."""
        res = requests.get(f"{BASE_URL}/api/admin/references", headers=admin_headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text[:200]}"
        data = res.json()
        assert "references" in data, "Response should have 'references' key"
        refs = data["references"]
        assert isinstance(refs, list), "references should be a list"
        print(f"PASS: GET /api/admin/references returned {len(refs)} references")

    def test_zoho_refs_are_seeded(self, admin_headers):
        """Zoho refs should be seeded as regular references, not system refs."""
        res = requests.get(f"{BASE_URL}/api/admin/references", headers=admin_headers)
        assert res.status_code == 200
        refs = res.json().get("references", [])
        ref_keys = {r["key"] for r in refs}
        expected_zoho_keys = {
            "zoho_reseller_signup_us",
            "zoho_reseller_signup_ca",
            "zoho_partner_tag_us",
            "zoho_partner_tag_ca",
            "zoho_access_instructions_url",
        }
        missing = expected_zoho_keys - ref_keys
        assert not missing, f"Missing Zoho refs: {missing}"
        print(f"PASS: All 5 Zoho refs found in unified references table")

    def test_zoho_refs_are_not_system(self, admin_headers):
        """Zoho refs should NOT be system=True so they can be deleted."""
        res = requests.get(f"{BASE_URL}/api/admin/references", headers=admin_headers)
        assert res.status_code == 200
        refs = res.json().get("references", [])
        zoho_refs = [r for r in refs if r.get("key", "").startswith("zoho_")]
        for ref in zoho_refs:
            assert not ref.get("system"), f"Zoho ref '{ref['key']}' should NOT be system=True (should be deletable)"
        print(f"PASS: {len(zoho_refs)} Zoho refs are non-system (have edit + delete icons)")

    def test_zoho_refs_response_structure(self, admin_headers):
        """Each Zoho ref should have id, key, label, type, value fields."""
        res = requests.get(f"{BASE_URL}/api/admin/references", headers=admin_headers)
        refs = res.json().get("references", [])
        zoho_refs = [r for r in refs if r.get("key", "").startswith("zoho_")]
        assert len(zoho_refs) == 5, f"Expected 5 Zoho refs, got {len(zoho_refs)}"
        for ref in zoho_refs:
            assert "id" in ref, f"Missing 'id' in ref {ref.get('key')}"
            assert "key" in ref, f"Missing 'key' in ref {ref.get('key')}"
            assert "label" in ref, f"Missing 'label' in ref {ref.get('key')}"
            assert "type" in ref, f"Missing 'type' in ref {ref.get('key')}"
            assert ref.get("type") == "url", f"Zoho ref '{ref['key']}' should have type='url'"
            assert "_id" not in ref, "MongoDB _id should be excluded from response"
        print(f"PASS: All Zoho refs have correct structure (id, key, label, type)")

    def test_can_edit_zoho_ref(self, admin_headers):
        """PUT /api/admin/references/{id} should work on Zoho refs."""
        res = requests.get(f"{BASE_URL}/api/admin/references", headers=admin_headers)
        refs = res.json().get("references", [])
        zoho_ref = next((r for r in refs if r.get("key") == "zoho_access_instructions_url"), None)
        if not zoho_ref:
            pytest.skip("zoho_access_instructions_url not found")
        update_res = requests.put(
            f"{BASE_URL}/api/admin/references/{zoho_ref['id']}",
            json={"value": "https://test.example.com/zoho-access"},
            headers=admin_headers
        )
        assert update_res.status_code == 200, f"Expected 200, got {update_res.status_code}: {update_res.text[:200]}"
        data = update_res.json()
        assert "reference" in data
        assert data["reference"]["value"] == "https://test.example.com/zoho-access"
        print("PASS: Zoho ref can be updated via PUT /api/admin/references/{id}")

    def test_create_and_delete_custom_ref(self, admin_headers):
        """POST + DELETE /api/admin/references should work for custom refs."""
        create_res = requests.post(f"{BASE_URL}/api/admin/references", json={
            "label": "TEST_Iter52 Ref",
            "key": "test_iter52_ref_unique",
            "type": "text",
            "value": "test_value",
            "description": "Test ref for iter52"
        }, headers=admin_headers)
        assert create_res.status_code == 200, f"Expected 200, got {create_res.status_code}: {create_res.text[:200]}"
        ref_id = create_res.json()["reference"]["id"]
        # Now delete it
        del_res = requests.delete(f"{BASE_URL}/api/admin/references/{ref_id}", headers=admin_headers)
        assert del_res.status_code == 200, f"Delete failed: {del_res.status_code}: {del_res.text[:200]}"
        print("PASS: Can create and delete custom references")


# ─── Test: Article Templates CRUD ──────────────────────────────────────────────

class TestArticleTemplates:
    """Test article templates CRUD endpoints."""

    def test_list_templates_returns_defaults(self, admin_headers):
        """GET /api/article-templates should return 4 default templates after seeding."""
        res = requests.get(f"{BASE_URL}/api/article-templates", headers=admin_headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text[:200]}"
        data = res.json()
        assert "templates" in data
        templates = data["templates"]
        assert len(templates) >= 4, f"Expected at least 4 templates, got {len(templates)}"
        print(f"PASS: GET /api/article-templates returned {len(templates)} templates")

    def test_four_default_templates_exist(self, admin_headers):
        """Verify 4 specific default templates: Blog Post, Guide/How-To, SOP, Scope of Work."""
        res = requests.get(f"{BASE_URL}/api/article-templates", headers=admin_headers)
        templates = res.json().get("templates", [])
        template_names = {t["name"] for t in templates}
        expected_names = {"Blog Post", "Guide / How-To", "Standard Operating Procedure (SOP)", "Scope of Work"}
        missing = expected_names - template_names
        assert not missing, f"Missing default templates: {missing}. Available: {template_names}"
        print(f"PASS: All 4 default templates found: {expected_names}")

    def test_default_templates_have_correct_structure(self, admin_headers):
        """Default templates should have id, name, description, category, content, is_default fields."""
        res = requests.get(f"{BASE_URL}/api/article-templates", headers=admin_headers)
        templates = res.json().get("templates", [])
        default_tpls = [t for t in templates if t.get("is_default")]
        assert len(default_tpls) == 4, f"Expected 4 default templates, got {len(default_tpls)}"
        for tpl in default_tpls:
            assert "id" in tpl
            assert "name" in tpl
            assert "description" in tpl
            assert "category" in tpl
            assert "content" in tpl
            assert tpl.get("is_default") == True
            assert "_id" not in tpl, "MongoDB _id should not be in response"
        print("PASS: Default templates have correct structure")

    def test_create_custom_template(self, admin_headers):
        """POST /api/article-templates should create a custom template."""
        res = requests.post(f"{BASE_URL}/api/article-templates", json={
            "name": "TEST_Custom Template Iter52",
            "description": "A test template",
            "category": "Blog",
            "content": "<h1>Test Template</h1><p>Content here</p>"
        }, headers=admin_headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text[:200]}"
        data = res.json()
        assert "template" in data
        tpl = data["template"]
        assert tpl["name"] == "TEST_Custom Template Iter52"
        assert tpl["is_default"] == False
        assert "_id" not in tpl
        return tpl["id"]

    def test_update_custom_template(self, admin_headers):
        """PUT /api/article-templates/{id} should update the template."""
        # Create first
        create_res = requests.post(f"{BASE_URL}/api/article-templates", json={
            "name": "TEST_Update Template",
            "description": "Original description",
            "category": "Blog",
            "content": "<p>Original content</p>"
        }, headers=admin_headers)
        assert create_res.status_code == 200
        tpl_id = create_res.json()["template"]["id"]

        # Update
        update_res = requests.put(f"{BASE_URL}/api/article-templates/{tpl_id}", json={
            "name": "TEST_Update Template (Updated)",
            "description": "Updated description",
            "content": "<p>Updated content</p>"
        }, headers=admin_headers)
        assert update_res.status_code == 200, f"Expected 200, got {update_res.status_code}: {update_res.text[:200]}"
        updated = update_res.json()["template"]
        assert updated["name"] == "TEST_Update Template (Updated)"
        assert updated["description"] == "Updated description"
        print("PASS: Template updated successfully")

        # Cleanup
        requests.delete(f"{BASE_URL}/api/article-templates/{tpl_id}", headers=admin_headers)

    def test_delete_custom_template(self, admin_headers):
        """DELETE /api/article-templates/{id} should delete the template."""
        # Create first
        create_res = requests.post(f"{BASE_URL}/api/article-templates", json={
            "name": "TEST_Delete Template",
            "description": "To be deleted",
            "category": "Other",
            "content": "<p>Content</p>"
        }, headers=admin_headers)
        assert create_res.status_code == 200
        tpl_id = create_res.json()["template"]["id"]

        # Delete
        del_res = requests.delete(f"{BASE_URL}/api/article-templates/{tpl_id}", headers=admin_headers)
        assert del_res.status_code == 200, f"Expected 200, got {del_res.status_code}: {del_res.text[:200]}"
        assert del_res.json().get("message") == "Deleted"
        print("PASS: Template deleted successfully")

    def test_cannot_create_template_without_name(self, admin_headers):
        """POST /api/article-templates without name should return 400."""
        res = requests.post(f"{BASE_URL}/api/article-templates", json={
            "description": "No name",
            "content": "<p>Content</p>"
        }, headers=admin_headers)
        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text[:200]}"
        print("PASS: Creating template without name returns 400")


# ─── Test: Article Download (PDF / DOCX) ──────────────────────────────────────

class TestArticleDownload:
    """Test article download endpoints for PDF and DOCX formats."""

    @pytest.fixture(scope="class")
    def article_id(self, admin_headers):
        """Create a test article for download tests."""
        # Check if test article already exists
        res = requests.get(f"{BASE_URL}/api/articles/admin/list?per_page=50&search=TEST_Download", headers=admin_headers)
        if res.status_code == 200:
            articles = res.json().get("articles", [])
            if articles:
                return articles[0]["id"]
        # Create new
        create_res = requests.post(f"{BASE_URL}/api/articles", json={
            "title": "TEST_Download Article for Iter52",
            "category": "Blog",
            "content": "<h1>Download Test</h1><p>This article is for testing PDF and DOCX download functionality.</p><h2>Section 1</h2><p>Some content here.</p>",
            "visibility": "all",
            "restricted_to": []
        }, headers=admin_headers)
        assert create_res.status_code == 200, f"Failed to create article: {create_res.text[:200]}"
        return create_res.json()["article"]["id"]

    def test_download_pdf_returns_binary(self, admin_headers, article_id):
        """GET /api/articles/{id}/download?format=pdf should return PDF content."""
        res = requests.get(
            f"{BASE_URL}/api/articles/{article_id}/download?format=pdf",
            headers=admin_headers
        )
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text[:200]}"
        assert res.headers.get("content-type") == "application/pdf", f"Expected PDF content-type, got {res.headers.get('content-type')}"
        assert len(res.content) > 0, "PDF content should not be empty"
        # PDF magic bytes: %PDF
        assert res.content[:4] == b"%PDF", f"PDF content should start with %PDF"
        print(f"PASS: PDF download returns valid PDF ({len(res.content)} bytes)")

    def test_download_docx_returns_binary(self, admin_headers, article_id):
        """GET /api/articles/{id}/download?format=docx should return DOCX content."""
        res = requests.get(
            f"{BASE_URL}/api/articles/{article_id}/download?format=docx",
            headers=admin_headers
        )
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text[:200]}"
        content_type = res.headers.get("content-type", "")
        assert "wordprocessingml" in content_type, f"Expected DOCX content-type, got {content_type}"
        assert len(res.content) > 0, "DOCX content should not be empty"
        # DOCX magic bytes: PK (ZIP format)
        assert res.content[:2] == b"PK", f"DOCX should start with PK (ZIP format)"
        print(f"PASS: DOCX download returns valid DOCX ({len(res.content)} bytes)")

    def test_pdf_has_content_disposition_header(self, admin_headers, article_id):
        """PDF download should have Content-Disposition header with filename."""
        res = requests.get(
            f"{BASE_URL}/api/articles/{article_id}/download?format=pdf",
            headers=admin_headers
        )
        assert res.status_code == 200
        cd = res.headers.get("content-disposition", "")
        assert "attachment" in cd, f"Content-Disposition should be attachment, got: {cd}"
        assert ".pdf" in cd, f"Filename should end in .pdf, got: {cd}"
        print(f"PASS: PDF has correct Content-Disposition: {cd}")

    def test_docx_has_content_disposition_header(self, admin_headers, article_id):
        """DOCX download should have Content-Disposition header with filename."""
        res = requests.get(
            f"{BASE_URL}/api/articles/{article_id}/download?format=docx",
            headers=admin_headers
        )
        assert res.status_code == 200
        cd = res.headers.get("content-disposition", "")
        assert "attachment" in cd, f"Content-Disposition should be attachment, got: {cd}"
        assert ".docx" in cd, f"Filename should end in .docx, got: {cd}"
        print(f"PASS: DOCX has correct Content-Disposition: {cd}")

    def test_download_invalid_article_returns_404(self, admin_headers):
        """GET /api/articles/{non_existent_id}/download should return 404."""
        res = requests.get(
            f"{BASE_URL}/api/articles/non_existent_id_xyz/download?format=pdf",
            headers=admin_headers
        )
        assert res.status_code == 404, f"Expected 404, got {res.status_code}"
        print("PASS: Download for non-existent article returns 404")


# ─── Test: Customers pagination ────────────────────────────────────────────────

class TestCustomersPagination:
    """Test customers API supports per_page=10."""

    def test_customers_with_per_page_10(self, admin_headers):
        """GET /api/admin/customers?per_page=10 should return at most 10 customers."""
        res = requests.get(f"{BASE_URL}/api/admin/customers?per_page=10&page=1", headers=admin_headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text[:200]}"
        data = res.json()
        assert "customers" in data
        assert len(data["customers"]) <= 10, f"Expected at most 10 customers per page, got {len(data['customers'])}"
        assert "total_pages" in data
        assert "total" in data
        print(f"PASS: Customers API supports per_page=10. Total: {data['total']}, Pages: {data['total_pages']}, Per page: {len(data['customers'])}")

    def test_customers_pagination_structure(self, admin_headers):
        """Customers API should return proper pagination metadata."""
        res = requests.get(f"{BASE_URL}/api/admin/customers?per_page=10&page=1", headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        assert "total_pages" in data, "Missing total_pages"
        assert "total" in data, "Missing total"
        assert "customers" in data, "Missing customers"
        print(f"PASS: Pagination structure correct: total={data['total']}, pages={data['total_pages']}")
