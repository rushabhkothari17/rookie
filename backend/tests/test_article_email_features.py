"""
Backend tests for Article Email features:
- POST /api/articles/{id}/send-email (with MOCKED email sending)
- GET/POST/PUT/DELETE /api/article-email-templates
"""

import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_CREDS = {
    "email": "admin@automateaccounts.local",
    "password": "ChangeMe123!",
}


# ---------- fixtures ----------

@pytest.fixture(scope="module")
def admin_token():
    """Obtain admin JWT token."""
    r = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    token = r.json().get("token") or r.json().get("access_token")
    assert token, "No token in login response"
    return token


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def test_article_id(auth_headers):
    """Create a test article to use for send-email tests."""
    payload = {
        "title": "TEST_EmailFeatureArticle",
        "slug": "test-email-feature-article",
        "category": "Blog",
        "content": "<p>Test content for email feature testing.</p>",
        "visibility": "all",
        "restricted_to": [],
    }
    r = requests.post(f"{BASE_URL}/api/articles", json=payload, headers=auth_headers)
    assert r.status_code in (200, 201), f"Failed to create test article: {r.text}"
    article = r.json().get("article", {})
    article_id = article.get("id")
    assert article_id, "No article ID in response"
    yield article_id
    # Cleanup
    requests.delete(f"{BASE_URL}/api/articles/{article_id}", headers=auth_headers)


# ---------- Tests: GET /api/article-email-templates ----------

class TestArticleEmailTemplatesList:
    """GET /api/article-email-templates endpoint"""

    def test_list_templates_returns_200(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/article-email-templates", headers=auth_headers)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    def test_list_templates_returns_templates_key(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/article-email-templates", headers=auth_headers)
        data = r.json()
        assert "templates" in data, f"No 'templates' key in response: {data}"
        assert isinstance(data["templates"], list)

    def test_list_templates_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/article-email-templates")
        assert r.status_code in (401, 403), f"Expected 401/403 without auth, got {r.status_code}"


# ---------- Tests: POST /api/article-email-templates ----------

class TestArticleEmailTemplateCreate:
    """POST /api/article-email-templates endpoint"""

    created_id = None

    def test_create_template_success(self, auth_headers):
        payload = {
            "name": "TEST_EmailTemplate_Basic",
            "subject": "Your Scope Deliverable is Ready",
            "html_body": "<p>Dear Client,</p><p>Your article is ready.</p>",
            "description": "TEST template for article delivery",
        }
        r = requests.post(f"{BASE_URL}/api/article-email-templates", json=payload, headers=auth_headers)
        assert r.status_code in (200, 201), f"Expected 2xx, got {r.status_code}: {r.text}"
        data = r.json()
        assert "template" in data, f"No 'template' key: {data}"
        tpl = data["template"]
        assert tpl["name"] == "TEST_EmailTemplate_Basic"
        assert tpl["subject"] == "Your Scope Deliverable is Ready"
        assert "id" in tpl
        TestArticleEmailTemplateCreate.created_id = tpl["id"]

    def test_create_template_persisted_in_list(self, auth_headers):
        """Verify created template appears in list."""
        if not TestArticleEmailTemplateCreate.created_id:
            pytest.skip("No template created to verify")
        r = requests.get(f"{BASE_URL}/api/article-email-templates", headers=auth_headers)
        assert r.status_code == 200
        templates = r.json().get("templates", [])
        ids = [t["id"] for t in templates]
        assert TestArticleEmailTemplateCreate.created_id in ids, "Created template not found in list"

    def test_create_template_missing_name_fails(self, auth_headers):
        payload = {
            "name": "   ",  # empty after strip
            "subject": "Test Subject",
            "html_body": "<p>Body</p>",
        }
        r = requests.post(f"{BASE_URL}/api/article-email-templates", json=payload, headers=auth_headers)
        assert r.status_code == 400, f"Expected 400 for empty name, got {r.status_code}: {r.text}"

    def test_create_template_requires_auth(self):
        payload = {"name": "Test", "subject": "Sub", "html_body": "<p>B</p>"}
        r = requests.post(f"{BASE_URL}/api/article-email-templates", json=payload)
        assert r.status_code in (401, 403)


# ---------- Tests: PUT /api/article-email-templates/{id} ----------

class TestArticleEmailTemplateUpdate:
    """PUT /api/article-email-templates/{id} endpoint"""

    created_id = None

    def setup_method(self, method):
        pass

    def test_update_template(self, auth_headers):
        # First create one
        payload = {"name": "TEST_ToUpdate", "subject": "Original Subject", "html_body": "<p>Original</p>"}
        r = requests.post(f"{BASE_URL}/api/article-email-templates", json=payload, headers=auth_headers)
        assert r.status_code in (200, 201)
        TestArticleEmailTemplateUpdate.created_id = r.json()["template"]["id"]

        # Update it
        update_r = requests.put(
            f"{BASE_URL}/api/article-email-templates/{TestArticleEmailTemplateUpdate.created_id}",
            json={"subject": "Updated Subject", "html_body": "<p>Updated body</p>"},
            headers=auth_headers,
        )
        assert update_r.status_code == 200, f"PUT failed: {update_r.text}"
        tpl = update_r.json().get("template", {})
        assert tpl.get("subject") == "Updated Subject"
        assert tpl.get("name") == "TEST_ToUpdate"  # name unchanged

    def test_update_nonexistent_template_returns_404(self, auth_headers):
        r = requests.put(
            f"{BASE_URL}/api/article-email-templates/nonexistent_id_xyz",
            json={"subject": "Update"},
            headers=auth_headers,
        )
        assert r.status_code == 404, f"Expected 404, got {r.status_code}"


# ---------- Tests: DELETE /api/article-email-templates/{id} ----------

class TestArticleEmailTemplateDelete:
    """DELETE /api/article-email-templates/{id} endpoint"""

    def test_delete_template(self, auth_headers):
        # Create one to delete
        payload = {"name": "TEST_ToDelete", "subject": "Sub", "html_body": "<p>body</p>"}
        r = requests.post(f"{BASE_URL}/api/article-email-templates", json=payload, headers=auth_headers)
        assert r.status_code in (200, 201)
        tpl_id = r.json()["template"]["id"]

        # Delete it
        del_r = requests.delete(f"{BASE_URL}/api/article-email-templates/{tpl_id}", headers=auth_headers)
        assert del_r.status_code in (200, 204), f"DELETE failed: {del_r.text}"

        # Verify it's gone
        list_r = requests.get(f"{BASE_URL}/api/article-email-templates", headers=auth_headers)
        assert list_r.status_code == 200
        ids = [t["id"] for t in list_r.json().get("templates", [])]
        assert tpl_id not in ids, "Template still present after delete"

    def test_delete_nonexistent_returns_404(self, auth_headers):
        r = requests.delete(
            f"{BASE_URL}/api/article-email-templates/nonexistent_xyz",
            headers=auth_headers,
        )
        assert r.status_code == 404


# ---------- Tests: POST /api/articles/{id}/send-email ----------

class TestArticleSendEmail:
    """POST /api/articles/{article_id}/send-email endpoint"""

    def test_send_email_mocked_success(self, auth_headers, test_article_id):
        """Basic send-email with mocked provider."""
        payload = {
            "to": ["test@example.com"],
            "cc": [],
            "bcc": [],
            "subject": "TEST: Article Ready",
            "html_body": "<p>Your article is ready.</p>",
            "attach_pdf": False,
        }
        r = requests.post(
            f"{BASE_URL}/api/articles/{test_article_id}/send-email",
            json=payload,
            headers=auth_headers,
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "sent" in data, f"No 'sent' in response: {data}"
        assert "test@example.com" in data["sent"]
        assert data.get("mocked") is True, "Expected mocked=True when email provider not configured"

    def test_send_email_response_has_message(self, auth_headers, test_article_id):
        payload = {
            "to": ["recipient@test.com"],
            "subject": "TEST Message",
            "html_body": "<p>Hello</p>",
            "attach_pdf": False,
        }
        r = requests.post(
            f"{BASE_URL}/api/articles/{test_article_id}/send-email",
            json=payload,
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert "message" in data
        assert "1" in data["message"]  # "Sent to 1 recipient(s)..."

    def test_send_email_multiple_recipients(self, auth_headers, test_article_id):
        payload = {
            "to": ["user1@example.com", "user2@example.com"],
            "cc": ["cc@example.com"],
            "subject": "TEST: Multiple Recipients",
            "html_body": "<p>Hi everyone</p>",
            "attach_pdf": False,
        }
        r = requests.post(
            f"{BASE_URL}/api/articles/{test_article_id}/send-email",
            json=payload,
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data.get("sent", [])) == 2

    def test_send_email_empty_to_returns_400(self, auth_headers, test_article_id):
        payload = {
            "to": [],
            "subject": "No recipients",
            "html_body": "<p>Body</p>",
            "attach_pdf": False,
        }
        r = requests.post(
            f"{BASE_URL}/api/articles/{test_article_id}/send-email",
            json=payload,
            headers=auth_headers,
        )
        assert r.status_code == 400, f"Expected 400 for empty to, got {r.status_code}: {r.text}"

    def test_send_email_nonexistent_article_returns_404(self, auth_headers):
        payload = {
            "to": ["test@example.com"],
            "subject": "Test",
            "html_body": "<p>Body</p>",
            "attach_pdf": False,
        }
        r = requests.post(
            f"{BASE_URL}/api/articles/nonexistent_article_xyz/send-email",
            json=payload,
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_send_email_requires_auth(self, test_article_id):
        payload = {
            "to": ["test@example.com"],
            "subject": "Test",
            "html_body": "<p>Body</p>",
            "attach_pdf": False,
        }
        r = requests.post(f"{BASE_URL}/api/articles/{test_article_id}/send-email", json=payload)
        assert r.status_code in (401, 403)

    def test_send_email_with_attach_pdf_flag(self, auth_headers, test_article_id):
        """Test that attach_pdf=True is accepted (PDF generation should succeed or fail gracefully)."""
        payload = {
            "to": ["pdftest@example.com"],
            "subject": "TEST: PDF Attachment",
            "html_body": "<p>See attached PDF.</p>",
            "attach_pdf": True,
        }
        r = requests.post(
            f"{BASE_URL}/api/articles/{test_article_id}/send-email",
            json=payload,
            headers=auth_headers,
        )
        # Should succeed (PDF generated + mocked email)
        assert r.status_code == 200, f"Expected 200 with attach_pdf=True, got {r.status_code}: {r.text}"
        data = r.json()
        assert "pdftest@example.com" in data.get("sent", [])


# ---------- Cleanup for test data ----------

def test_cleanup_test_templates(auth_headers):
    """Cleanup TEST_ prefixed email templates created during tests."""
    r = requests.get(f"{BASE_URL}/api/article-email-templates", headers=auth_headers)
    if r.status_code != 200:
        return
    for tpl in r.json().get("templates", []):
        if tpl.get("name", "").startswith("TEST_"):
            requests.delete(f"{BASE_URL}/api/article-email-templates/{tpl['id']}", headers=auth_headers)
    print("Cleanup done: removed TEST_ email templates")
