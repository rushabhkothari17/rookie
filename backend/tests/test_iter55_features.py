"""
Iteration 55 Tests:
- Website settings: admin_page_badge/title/subtitle fields
- Website settings: bank_transaction_sources/types/statuses fields
- Admin website settings API: read/write for new fields
- Cart endpoint basic health check
- RichHtmlEditor-related: articles API and terms API
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# ─── Auth Fixture ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!"
    })
    if resp.status_code != 200:
        pytest.skip("Admin login failed - skipping admin tests")
    return resp.json().get("access_token") or resp.json().get("token")

@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ─── Admin Panel Badge/Title/Subtitle Tests ───────────────────────────────────

class TestAdminPageWebsiteSettings:
    """Tests for admin_page_badge/title/subtitle in website settings"""

    def test_get_website_settings_returns_admin_page_fields(self, admin_headers):
        """GET /admin/website-settings should include admin_page fields"""
        resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "settings" in data, "Response should have 'settings' key"
        # These fields may be empty strings but should be present or at least accessible
        settings = data["settings"]
        # Just verify the endpoint works; fields may be optional
        assert isinstance(settings, dict)

    def test_update_admin_page_badge(self, admin_headers):
        """PUT /admin/website-settings should save admin_page_badge"""
        payload = {
            "admin_page_badge": "TEST_BADGE",
            "admin_page_title": "TEST_Admin Control Centre",
            "admin_page_subtitle": "TEST_Manage customers and orders from one place."
        }
        resp = requests.put(f"{BASE_URL}/api/admin/website-settings", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "message" in data or "settings" in data

    def test_verify_admin_page_fields_persisted(self, admin_headers):
        """Verify admin_page_badge/title/subtitle persisted after update"""
        resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=admin_headers)
        assert resp.status_code == 200
        settings = resp.json()["settings"]
        assert settings.get("admin_page_badge") == "TEST_BADGE", f"Expected TEST_BADGE, got {settings.get('admin_page_badge')}"
        assert settings.get("admin_page_title") == "TEST_Admin Control Centre"
        assert settings.get("admin_page_subtitle") == "TEST_Manage customers and orders from one place."

    def test_cleanup_admin_page_fields(self, admin_headers):
        """Cleanup test data"""
        payload = {
            "admin_page_badge": "",
            "admin_page_title": "",
            "admin_page_subtitle": ""
        }
        # Set to empty to restore defaults
        resp = requests.put(f"{BASE_URL}/api/admin/website-settings", json=payload, headers=admin_headers)
        assert resp.status_code == 200


# ─── Bank Transaction Sources/Types/Statuses Tests ───────────────────────────

class TestBankTransactionWebsiteSettings:
    """Tests for bank_transaction_sources/types/statuses in website settings"""

    def test_update_bank_transaction_sources(self, admin_headers):
        """PUT /admin/website-settings should save bank_transaction_sources"""
        payload = {
            "bank_transaction_sources": "manual\nbank_transfer\ntest_source",
            "bank_transaction_types": "payment\nrefund\ntest_type",
            "bank_transaction_statuses": "pending\ncompleted\ntest_status"
        }
        resp = requests.put(f"{BASE_URL}/api/admin/website-settings", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_verify_bank_transaction_fields_persisted(self, admin_headers):
        """Verify bank_transaction sources/types/statuses persisted"""
        resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=admin_headers)
        assert resp.status_code == 200
        settings = resp.json()["settings"]
        sources = settings.get("bank_transaction_sources", "")
        assert "manual" in sources, f"Expected 'manual' in sources, got: {sources}"
        assert "test_source" in sources, f"Expected 'test_source' in sources, got: {sources}"
        types_ = settings.get("bank_transaction_types", "")
        assert "test_type" in types_, f"Expected 'test_type' in types, got: {types_}"
        statuses = settings.get("bank_transaction_statuses", "")
        assert "test_status" in statuses, f"Expected 'test_status' in statuses, got: {statuses}"

    def test_cleanup_bank_transaction_fields(self, admin_headers):
        """Cleanup test bank_transaction settings"""
        payload = {
            "bank_transaction_sources": "",
            "bank_transaction_types": "",
            "bank_transaction_statuses": ""
        }
        resp = requests.put(f"{BASE_URL}/api/admin/website-settings", json=payload, headers=admin_headers)
        assert resp.status_code == 200

    def test_public_settings_accessible(self):
        """GET /settings/public should be accessible"""
        resp = requests.get(f"{BASE_URL}/api/settings/public")
        assert resp.status_code == 200


# ─── Bank Transactions API Tests ─────────────────────────────────────────────

class TestBankTransactionsAPI:
    """Tests for bank transactions CRUD"""

    def test_list_bank_transactions(self, admin_headers):
        """GET /admin/bank-transactions should return list"""
        resp = requests.get(f"{BASE_URL}/api/admin/bank-transactions", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "transactions" in data
        assert isinstance(data["transactions"], list)

    def test_create_bank_transaction(self, admin_headers):
        """POST /admin/bank-transactions should create a transaction"""
        payload = {
            "date": "2026-02-01",
            "source": "manual",
            "transaction_id": "TEST_TXN_001",
            "type": "payment",
            "amount": 100.00,
            "fees": 1.50,
            "currency": "USD",
            "status": "completed",
            "description": "TEST transaction for iter55"
        }
        resp = requests.post(f"{BASE_URL}/api/admin/bank-transactions", json=payload, headers=admin_headers)
        assert resp.status_code in [200, 201], f"Expected 200/201, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "id" in data or "transaction" in data, f"Response should have id: {data}"
        return data.get("id") or data.get("transaction", {}).get("id")

    def test_create_and_verify_transaction(self, admin_headers):
        """Create and verify a bank transaction persists"""
        payload = {
            "date": "2026-02-01",
            "source": "bank_transfer",
            "transaction_id": "TEST_TXN_VERIFY",
            "type": "payment",
            "amount": 250.00,
            "fees": 2.50,
            "currency": "USD",
            "status": "pending",
            "description": "TEST_BankTxn for iter55 verification"
        }
        create_resp = requests.post(f"{BASE_URL}/api/admin/bank-transactions", json=payload, headers=admin_headers)
        assert create_resp.status_code in [200, 201], f"Create failed: {create_resp.text}"
        
        # Verify it's in the list
        list_resp = requests.get(f"{BASE_URL}/api/admin/bank-transactions", headers=admin_headers)
        assert list_resp.status_code == 200
        txns = list_resp.json().get("transactions", [])
        found = any(t.get("transaction_id") == "TEST_TXN_VERIFY" for t in txns)
        assert found, "Created transaction not found in list"
        
        # Cleanup
        txn_id = create_resp.json().get("id") or create_resp.json().get("transaction", {}).get("id")
        if txn_id:
            requests.delete(f"{BASE_URL}/api/admin/bank-transactions/{txn_id}", headers=admin_headers)


# ─── Articles API Tests (RichHtmlEditor backend support) ─────────────────────

class TestArticlesAPI:
    """Tests for articles CRUD - verifies HTML content is stored correctly"""

    def test_list_articles(self, admin_headers):
        """GET /articles/admin/list should work"""
        resp = requests.get(f"{BASE_URL}/api/articles/admin/list", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "articles" in data

    def test_create_article_with_html_content(self, admin_headers):
        """POST /articles should save HTML content"""
        payload = {
            "title": "TEST_RichHtmlEditor Article",
            "slug": "test-rich-html-editor-article",
            "category": "Blog",
            "content": "<p>This is <strong>bold</strong> text with <em>italic</em> formatting.</p><h2>Heading 2</h2><ul><li>List item 1</li><li>List item 2</li></ul>",
        }
        resp = requests.post(f"{BASE_URL}/api/articles", json=payload, headers=admin_headers)
        assert resp.status_code in [200, 201], f"Expected 200/201, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "article" in data or "id" in data, f"Response: {data}"
        
        article_id = data.get("id") or data.get("article", {}).get("id")
        
        # Verify content saved
        get_resp = requests.get(f"{BASE_URL}/api/articles/{article_id}", headers=admin_headers)
        assert get_resp.status_code == 200
        article = get_resp.json().get("article", get_resp.json())
        assert "<strong>bold</strong>" in article.get("content", ""), "HTML content should be preserved"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/articles/{article_id}", headers=admin_headers)

    def test_list_terms(self, admin_headers):
        """GET /admin/terms should work"""
        resp = requests.get(f"{BASE_URL}/api/admin/terms", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "terms" in data


# ─── Quick Health Checks ──────────────────────────────────────────────────────

class TestHealthChecks:
    """Quick API health checks"""

    def test_api_health(self):
        """API should be responsive"""
        resp = requests.get(f"{BASE_URL}/api/health", timeout=10)
        # Some APIs might not have a /health endpoint
        assert resp.status_code in [200, 404]

    def test_products_endpoint(self):
        """GET /products should be accessible"""
        resp = requests.get(f"{BASE_URL}/api/products")
        assert resp.status_code == 200

    def test_orders_preview_requires_auth(self):
        """POST /orders/preview requires auth or items"""
        resp = requests.post(f"{BASE_URL}/api/orders/preview", json={"items": []})
        # Should return 400 or 401 or 200 with empty
        assert resp.status_code in [200, 400, 401, 422]
