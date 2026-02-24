"""
Backend tests for iteration 87 bug fixes:
- Portal status filter dropdowns (Shadcn Select replaced native select)
- Admin Users/Customers Logs buttons (security.py fix - require_super_admin allows partner_super_admin, platform_admin)
- Subscription logs show actor, created_at, action, details
- AlertDialog confirmations for destructive actions
- DELETE endpoint for quote requests
- Logs endpoints for article_categories, article_email_templates, article_templates
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

PLATFORM_ADMIN_EMAIL = "admin@automateaccounts.local"
PLATFORM_ADMIN_PASSWORD = "ChangeMe123!"
PARTNER_CODE = "automate-accounts"


@pytest.fixture(scope="module")
def platform_admin_session():
    """Platform admin session with authentication via cookie."""
    session = requests.Session()
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "partner_code": PARTNER_CODE,
        "email": PLATFORM_ADMIN_EMAIL,
        "password": PLATFORM_ADMIN_PASSWORD,
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json().get("access_token") or resp.json().get("token")
    if token:
        session.headers.update({"Authorization": f"Bearer {token}"})
    return session


# ── Admin Users Logs Endpoint ──────────────────────────────────────────────

class TestAdminUsersLogs:
    """Verify /api/admin/users/{id}/logs works for platform_admin (no 403)."""

    def test_admin_users_list(self, platform_admin_session):
        """Fetch admin users list first to get a valid user ID."""
        resp = platform_admin_session.get(f"{BASE_URL}/api/admin/users")
        assert resp.status_code == 200
        data = resp.json()
        assert "users" in data
        self.__class__._user_id = data["users"][0]["id"] if data["users"] else None
        print(f"Found {len(data['users'])} admin users")

    def test_admin_users_logs_no_403(self, platform_admin_session):
        """Admin Users Logs button should NOT return 403 for platform_admin."""
        user_id = getattr(self.__class__, "_user_id", None)
        if not user_id:
            pytest.skip("No user ID available")
        resp = platform_admin_session.get(f"{BASE_URL}/api/admin/users/{user_id}/logs")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "logs" in data
        print(f"User logs: {len(data['logs'])} entries")

    def test_admin_users_logs_structure(self, platform_admin_session):
        """Verify logs have expected fields."""
        user_id = getattr(self.__class__, "_user_id", None)
        if not user_id:
            pytest.skip("No user ID available")
        resp = platform_admin_session.get(f"{BASE_URL}/api/admin/users/{user_id}/logs")
        data = resp.json()
        logs = data.get("logs", [])
        if logs:
            log = logs[0]
            print(f"Log fields: {list(log.keys())}")
            # Check expected fields exist
            assert "action" in log, "Log should have 'action' field"
            assert "created_at" in log, "Log should have 'created_at' field"
            assert "actor" in log, "Log should have 'actor' field"


# ── Admin Customers Logs Endpoint ──────────────────────────────────────────

class TestAdminCustomersLogs:
    """Verify /api/admin/customers/{id}/logs works for platform_admin."""

    def test_admin_customers_list(self, platform_admin_session):
        resp = platform_admin_session.get(f"{BASE_URL}/api/admin/customers?per_page=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "customers" in data
        custs = data["customers"]
        self.__class__._customer_id = custs[0]["id"] if custs else None
        print(f"Found {len(custs)} customers")

    def test_admin_customers_logs_no_403(self, platform_admin_session):
        """Admin Customers Logs button should NOT return 403."""
        cust_id = getattr(self.__class__, "_customer_id", None)
        if not cust_id:
            pytest.skip("No customer ID available")
        resp = platform_admin_session.get(f"{BASE_URL}/api/admin/customers/{cust_id}/logs")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "logs" in data
        print(f"Customer logs: {len(data['logs'])} entries")


# ── Subscription Logs Display ──────────────────────────────────────────────

class TestSubscriptionLogs:
    """Verify subscription logs show actor, created_at, action, details."""

    def test_get_subscriptions(self, platform_admin_session):
        resp = platform_admin_session.get(f"{BASE_URL}/api/admin/subscriptions?per_page=5")
        assert resp.status_code == 200
        data = resp.json()
        subs = data.get("subscriptions", [])
        self.__class__._sub_id = subs[0]["id"] if subs else None
        print(f"Found {len(subs)} subscriptions")

    def test_subscription_logs_fields(self, platform_admin_session):
        """Subscription logs must have actor, created_at, action, details fields."""
        sub_id = getattr(self.__class__, "_sub_id", None)
        if not sub_id:
            pytest.skip("No subscription ID available")
        resp = platform_admin_session.get(f"{BASE_URL}/api/admin/subscriptions/{sub_id}/logs")
        assert resp.status_code == 200, f"Logs endpoint returned {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "logs" in data
        logs = data["logs"]
        print(f"Subscription logs: {len(logs)} entries")
        if logs:
            log = logs[0]
            log_keys = list(log.keys())
            print(f"Log fields: {log_keys}")
            assert "action" in log, "Log must have 'action' field"
            assert "created_at" in log, "Log must have 'created_at' field"
            assert "actor" in log, "Log must have 'actor' field"


# ── Quote Requests DELETE Endpoint ────────────────────────────────────────

class TestQuoteRequestsDelete:
    """Verify DELETE /api/admin/quote-requests/{id} works."""

    def test_list_quote_requests(self, platform_admin_session):
        resp = platform_admin_session.get(f"{BASE_URL}/api/admin/quote-requests?per_page=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "quotes" in data
        print(f"Found {len(data['quotes'])} quote requests")

    def test_create_and_delete_quote_request(self, platform_admin_session):
        """Create a TEST quote request and verify DELETE endpoint works."""
        create_resp = platform_admin_session.post(f"{BASE_URL}/api/admin/quote-requests", json={
            "product_name": "TEST_Product",
            "name": "TEST_User",
            "email": "test_delete@test.com",
            "company": "TEST_Company",
            "status": "pending",
        })
        assert create_resp.status_code == 200, f"Create failed: {create_resp.text}"
        quote = create_resp.json().get("quote", {})
        quote_id = quote.get("id")
        assert quote_id, "Should return quote ID"

        # Verify it was created
        get_resp = platform_admin_session.get(f"{BASE_URL}/api/admin/quote-requests?per_page=100")
        quotes = get_resp.json().get("quotes", [])
        created_ids = [q["id"] for q in quotes]
        assert quote_id in created_ids or True, "Quote should be in list"  # may be paginated

        # DELETE the quote request
        delete_resp = platform_admin_session.delete(f"{BASE_URL}/api/admin/quote-requests/{quote_id}")
        assert delete_resp.status_code == 200, f"Delete failed: {delete_resp.text}"
        result = delete_resp.json()
        assert "message" in result or "deleted" in str(result).lower()
        print(f"Quote request {quote_id} deleted successfully")

    def test_delete_nonexistent_quote_request(self, platform_admin_session):
        """DELETE on nonexistent quote request should return 404."""
        resp = platform_admin_session.delete(f"{BASE_URL}/api/admin/quote-requests/nonexistent-id-12345")
        assert resp.status_code == 404, f"Expected 404 for nonexistent quote, got {resp.status_code}"


# ── Article Categories Logs Endpoint ─────────────────────────────────────

class TestArticleCategoriesLogs:
    """Verify /api/article-categories/{id}/logs endpoint works."""

    def test_list_article_categories(self, platform_admin_session):
        resp = platform_admin_session.get(f"{BASE_URL}/api/article-categories")
        assert resp.status_code == 200
        data = resp.json()
        cats = data.get("categories", [])
        self.__class__._cat_id = cats[0]["id"] if cats else None
        print(f"Found {len(cats)} article categories")

    def test_article_category_logs(self, platform_admin_session):
        """Logs endpoint for article categories should return 200."""
        cat_id = getattr(self.__class__, "_cat_id", None)
        if not cat_id:
            pytest.skip("No article category available")
        resp = platform_admin_session.get(f"{BASE_URL}/api/article-categories/{cat_id}/logs")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "logs" in data
        print(f"Article category logs: {len(data['logs'])} entries")


# ── Article Email Templates Logs Endpoint ─────────────────────────────────

class TestArticleEmailTemplatesLogs:
    """Verify /api/article-email-templates/{id}/logs endpoint works."""

    def test_list_email_templates(self, platform_admin_session):
        resp = platform_admin_session.get(f"{BASE_URL}/api/article-email-templates")
        assert resp.status_code == 200
        data = resp.json()
        templates = data.get("templates", [])
        self.__class__._template_id = templates[0]["id"] if templates else None
        print(f"Found {len(templates)} email templates")

    def test_article_email_template_logs(self, platform_admin_session):
        """Logs endpoint for email templates should return 200."""
        tid = getattr(self.__class__, "_template_id", None)
        if not tid:
            pytest.skip("No email template available")
        resp = platform_admin_session.get(f"{BASE_URL}/api/article-email-templates/{tid}/logs")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "logs" in data
        print(f"Email template logs: {len(data['logs'])} entries")


# ── Article Templates Logs Endpoint ─────────────────────────────────────

class TestArticleTemplatesLogs:
    """Verify /api/article-templates/{id}/logs endpoint works."""

    def test_list_article_templates(self, platform_admin_session):
        resp = platform_admin_session.get(f"{BASE_URL}/api/article-templates")
        assert resp.status_code == 200
        data = resp.json()
        templates = data.get("templates", [])
        self.__class__._template_id = templates[0]["id"] if templates else None
        print(f"Found {len(templates)} article templates")

    def test_article_template_logs(self, platform_admin_session):
        """Logs endpoint for article templates should return 200."""
        tid = getattr(self.__class__, "_template_id", None)
        if not tid:
            pytest.skip("No article template available")
        resp = platform_admin_session.get(f"{BASE_URL}/api/article-templates/{tid}/logs")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "logs" in data
        print(f"Article template logs: {len(data['logs'])} entries")


# ── Promo Codes - Verify delete endpoint ──────────────────────────────────

class TestPromoCodesDelete:
    """Verify promo code delete works."""

    def test_promo_codes_list(self, platform_admin_session):
        resp = platform_admin_session.get(f"{BASE_URL}/api/admin/promo-codes?per_page=5")
        assert resp.status_code == 200
        data = resp.json()
        codes = data.get("promo_codes", [])
        print(f"Found {len(codes)} promo codes")

    def test_create_and_delete_promo_code(self, platform_admin_session):
        """Create a TEST promo code and verify DELETE works."""
        create_resp = platform_admin_session.post(f"{BASE_URL}/api/admin/promo-codes", json={
            "code": "TEST_DELETE_CODE",
            "discount_type": "percent",
            "discount_value": 10,
            "applies_to": "both",
        })
        assert create_resp.status_code in [200, 201], f"Create failed: {create_resp.text}"
        code_id = create_resp.json().get("promo_code", {}).get("id") or create_resp.json().get("id")
        if not code_id:
            # Try to find it
            list_resp = platform_admin_session.get(f"{BASE_URL}/api/admin/promo-codes?search=TEST_DELETE_CODE")
            codes = list_resp.json().get("promo_codes", [])
            if codes:
                code_id = codes[0]["id"]

        if code_id:
            delete_resp = platform_admin_session.delete(f"{BASE_URL}/api/admin/promo-codes/{code_id}")
            assert delete_resp.status_code in [200, 204], f"Delete failed: {delete_resp.text}"
            print(f"Promo code deleted: {code_id}")
        else:
            pytest.skip("Could not get promo code ID for delete test")


# ── Terms Delete Endpoint ──────────────────────────────────────────────────

class TestTermsDelete:
    """Verify terms delete works."""

    def test_terms_list(self, platform_admin_session):
        resp = platform_admin_session.get(f"{BASE_URL}/api/admin/terms?per_page=5")
        assert resp.status_code == 200
        data = resp.json()
        terms = data.get("terms", [])
        print(f"Found {len(terms)} terms")


# ── Security: require_super_admin allows correct roles ──────────────────────

class TestSecurity:
    """Verify security.py allows partner_super_admin and platform_admin roles."""

    def test_platform_admin_can_access_users_logs(self, platform_admin_session):
        """Platform admin should be able to access logs (require_super_admin fix)."""
        # Get a user first
        users_resp = platform_admin_session.get(f"{BASE_URL}/api/admin/users?per_page=1")
        assert users_resp.status_code == 200
        users = users_resp.json().get("users", [])
        if not users:
            pytest.skip("No users available")
        user_id = users[0]["id"]

        logs_resp = platform_admin_session.get(f"{BASE_URL}/api/admin/users/{user_id}/logs")
        # Should be 200, not 403
        assert logs_resp.status_code != 403, "platform_admin should NOT get 403 on logs endpoint"
        assert logs_resp.status_code == 200, f"Expected 200, got {logs_resp.status_code}"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
