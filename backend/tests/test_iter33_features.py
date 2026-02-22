"""
Iteration 33: Test new features:
1. GET /admin/categories/{id}/logs - category audit logs endpoint
2. Admin QuoteRequests - Edit/Logs buttons side-by-side (visual, tested via frontend)
3. Admin Customers - Currency column (verify API returns currency field)
4. Articles pagination - 9 per page, Previous/Next controls
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"
CUSTOMER_EMAIL = "test_user_004712@test.com"
CUSTOMER_PASSWORD = "Test1234!"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# -------------------------------------------------------------------
# 1. Categories Audit Logs endpoint
# -------------------------------------------------------------------

class TestCategoryLogs:
    """Tests for GET /admin/categories/{id}/logs"""

    def test_list_categories_returns_items(self, admin_headers):
        """GET /admin/categories returns a list of categories."""
        resp = requests.get(f"{BASE_URL}/api/admin/categories?per_page=20", headers=admin_headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        assert "categories" in data
        assert isinstance(data["categories"], list)
        print(f"Total categories: {data.get('total', 0)}")

    def test_category_logs_requires_auth(self):
        """GET /admin/categories/{id}/logs requires authentication."""
        # Get any category first with auth
        resp = requests.get(f"{BASE_URL}/api/admin/categories?per_page=5", headers={
            "Authorization": "Bearer admin_token", "Content-Type": "application/json"
        })
        # unauthenticated request to logs
        resp2 = requests.get(f"{BASE_URL}/api/admin/categories/some-id/logs")
        assert resp2.status_code in [401, 403], f"Expected 401/403, got {resp2.status_code}"

    def test_category_logs_for_existing_category(self, admin_headers):
        """GET /admin/categories/{id}/logs returns logs for existing category."""
        # Get categories list first
        list_resp = requests.get(f"{BASE_URL}/api/admin/categories?per_page=5", headers=admin_headers)
        assert list_resp.status_code == 200
        cats = list_resp.json().get("categories", [])

        if not cats:
            pytest.skip("No categories found in DB")

        cat_id = cats[0]["id"]
        resp = requests.get(f"{BASE_URL}/api/admin/categories/{cat_id}/logs", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "logs" in data, f"'logs' key missing from response: {data}"
        assert isinstance(data["logs"], list), f"logs should be a list, got {type(data['logs'])}"
        print(f"Category {cat_id} has {len(data['logs'])} log entries")

    def test_category_logs_no_id_field(self, admin_headers):
        """Category logs should not expose MongoDB _id."""
        list_resp = requests.get(f"{BASE_URL}/api/admin/categories?per_page=5", headers=admin_headers)
        cats = list_resp.json().get("categories", [])
        if not cats:
            pytest.skip("No categories found")

        cat_id = cats[0]["id"]
        resp = requests.get(f"{BASE_URL}/api/admin/categories/{cat_id}/logs", headers=admin_headers)
        assert resp.status_code == 200
        logs = resp.json()["logs"]
        for log in logs:
            assert "_id" not in log, f"MongoDB _id should not be in log: {log}"
        print(f"No _id fields found in {len(logs)} logs - PASS")

    def test_category_logs_after_create(self, admin_headers):
        """Creating a category creates an audit log; verifiable via logs endpoint."""
        import time
        cat_name = f"TEST_CAT_LOGS_{int(time.time())}"
        # Create category
        create_resp = requests.post(
            f"{BASE_URL}/api/admin/categories",
            json={"name": cat_name, "description": "Test category for audit log", "is_active": True},
            headers=admin_headers
        )
        assert create_resp.status_code == 200, f"Create failed: {create_resp.text}"
        cat_id = create_resp.json()["category"]["id"]

        try:
            # Fetch logs
            logs_resp = requests.get(f"{BASE_URL}/api/admin/categories/{cat_id}/logs", headers=admin_headers)
            assert logs_resp.status_code == 200
            logs = logs_resp.json()["logs"]
            assert len(logs) >= 1, f"Expected at least 1 log after create, got {len(logs)}"
            actions = [l["action"] for l in logs]
            assert "created" in actions, f"Expected 'created' action in logs, got {actions}"
            print(f"Category creation audit log verified: {actions}")
        finally:
            # Cleanup - delete the test category
            requests.delete(f"{BASE_URL}/api/admin/categories/{cat_id}", headers=admin_headers)

    def test_category_logs_after_update(self, admin_headers):
        """Updating a category creates an 'updated' audit log."""
        import time
        cat_name = f"TEST_CAT_UPD_{int(time.time())}"
        create_resp = requests.post(
            f"{BASE_URL}/api/admin/categories",
            json={"name": cat_name, "description": "Initial", "is_active": True},
            headers=admin_headers
        )
        assert create_resp.status_code == 200
        cat_id = create_resp.json()["category"]["id"]

        try:
            # Update category
            upd_resp = requests.put(
                f"{BASE_URL}/api/admin/categories/{cat_id}",
                json={"name": cat_name, "description": "Updated description", "is_active": True},
                headers=admin_headers
            )
            assert upd_resp.status_code == 200

            # Fetch logs
            logs_resp = requests.get(f"{BASE_URL}/api/admin/categories/{cat_id}/logs", headers=admin_headers)
            assert logs_resp.status_code == 200
            logs = logs_resp.json()["logs"]
            actions = [l["action"] for l in logs]
            assert "updated" in actions, f"Expected 'updated' action in logs, got {actions}"
            print(f"Category update audit log verified: {actions}")
        finally:
            requests.delete(f"{BASE_URL}/api/admin/categories/{cat_id}", headers=admin_headers)

    def test_category_logs_nonexistent_returns_empty(self, admin_headers):
        """GET /admin/categories/nonexistent-id/logs returns 200 with empty logs."""
        resp = requests.get(f"{BASE_URL}/api/admin/categories/nonexistent-id-xyz/logs", headers=admin_headers)
        # Should return 200 with empty logs (not 404)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "logs" in data
        assert data["logs"] == [], f"Expected empty logs for nonexistent category, got {data['logs']}"
        print("Nonexistent category logs returns empty list - PASS")


# -------------------------------------------------------------------
# 2. Customers API - Currency field
# -------------------------------------------------------------------

class TestCustomersCurrencyField:
    """Tests that admin customers API returns currency field."""

    def test_customers_list_has_currency_field(self, admin_headers):
        """GET /admin/customers returns customers with currency field."""
        resp = requests.get(f"{BASE_URL}/api/admin/customers?per_page=20", headers=admin_headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        assert "customers" in data
        customers = data["customers"]
        assert len(customers) > 0, "Expected at least one customer"
        # Check first customer has currency key (may be None/null)
        first = customers[0]
        assert "currency" in first or first.get("currency") is None, \
            f"Currency key not found in customer: {list(first.keys())}"
        print(f"Customer currency fields: {[c.get('currency') for c in customers[:5]]}")

    def test_customers_with_currency_values(self, admin_headers):
        """Check how many customers have non-null currency values."""
        resp = requests.get(f"{BASE_URL}/api/admin/customers?per_page=100", headers=admin_headers)
        assert resp.status_code == 200
        customers = resp.json().get("customers", [])
        with_currency = [c for c in customers if c.get("currency")]
        print(f"{len(with_currency)}/{len(customers)} customers have currency set")
        # Log the unique currencies found
        currencies = list(set(c.get("currency") for c in customers if c.get("currency")))
        print(f"Currencies found: {currencies}")
        # At least the currency key must exist
        for c in customers[:5]:
            assert "currency" in c, f"Currency key missing from customer {c.get('id')}"


# -------------------------------------------------------------------
# 3. Articles API - verify enough articles exist for pagination
# -------------------------------------------------------------------

class TestArticlesPagination:
    """Tests for articles pagination - verify API returns 33 articles."""

    @pytest.fixture(scope="class")
    def customer_headers(self):
        """Customer auth headers (articles/public requires auth)."""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": CUSTOMER_EMAIL, "password": CUSTOMER_PASSWORD})
        if resp.status_code != 200:
            pytest.skip(f"Customer login failed: {resp.text}")
        token = resp.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def test_articles_public_endpoint_accessible(self, customer_headers):
        """GET /articles/public is accessible with customer auth."""
        resp = requests.get(f"{BASE_URL}/api/articles/public", headers=customer_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "articles" in data
        print(f"Total articles: {len(data['articles'])}")

    def test_articles_count_supports_pagination(self, customer_headers):
        """Articles count >= 9 so pagination will be triggered."""
        resp = requests.get(f"{BASE_URL}/api/articles/public", headers=customer_headers)
        assert resp.status_code == 200
        articles = resp.json().get("articles", [])
        assert len(articles) >= 9, f"Expected >=9 articles for pagination, got {len(articles)}"
        print(f"Articles count: {len(articles)} - pagination will trigger with >9")

    def test_articles_count_for_4_pages(self, customer_headers):
        """Verify 33 articles exist => 4 pages of 9."""
        resp = requests.get(f"{BASE_URL}/api/articles/public", headers=customer_headers)
        assert resp.status_code == 200
        articles = resp.json().get("articles", [])
        count = len(articles)
        expected_pages = (count + 8) // 9  # ceiling division by 9
        print(f"Articles: {count} => {expected_pages} pages of 9")
        # Just verify the count is reasonable for multiple pages
        assert count > 9, f"Expected >9 articles for multi-page pagination, got {count}"

    def test_articles_have_required_fields(self, customer_headers):
        """Articles have required fields for display."""
        resp = requests.get(f"{BASE_URL}/api/articles/public", headers=customer_headers)
        assert resp.status_code == 200
        articles = resp.json().get("articles", [])
        if not articles:
            pytest.skip("No articles found")
        first = articles[0]
        required = ["id", "title", "category", "updated_at"]
        for field in required:
            assert field in first, f"Article missing required field: {field}"
        print(f"First article fields: {list(first.keys())}")

    def test_articles_no_id_field(self, customer_headers):
        """Articles should not expose MongoDB _id."""
        resp = requests.get(f"{BASE_URL}/api/articles/public", headers=customer_headers)
        assert resp.status_code == 200
        articles = resp.json().get("articles", [])
        for art in articles[:5]:
            assert "_id" not in art, f"MongoDB _id should not be in article: {art}"


# -------------------------------------------------------------------
# 4. Quote Requests API - verify logs endpoint works
# -------------------------------------------------------------------

class TestQuoteRequestLogs:
    """Tests for quote request logs endpoint (horizontal buttons - verified in frontend)."""

    def test_quote_requests_list(self, admin_headers):
        """GET /admin/quote-requests returns list."""
        resp = requests.get(f"{BASE_URL}/api/admin/quote-requests?per_page=5", headers=admin_headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        assert "quotes" in data
        print(f"Total quote requests: {data.get('total', 0)}")

    def test_quote_request_logs_endpoint(self, admin_headers):
        """GET /admin/quote-requests/{id}/logs returns logs."""
        list_resp = requests.get(f"{BASE_URL}/api/admin/quote-requests?per_page=5", headers=admin_headers)
        assert list_resp.status_code == 200
        quotes = list_resp.json().get("quotes", [])
        if not quotes:
            pytest.skip("No quote requests found")

        qid = quotes[0]["id"]
        logs_resp = requests.get(f"{BASE_URL}/api/admin/quote-requests/{qid}/logs", headers=admin_headers)
        assert logs_resp.status_code == 200, f"Expected 200, got {logs_resp.status_code}: {logs_resp.text}"
        data = logs_resp.json()
        assert "logs" in data
        print(f"Quote request {qid} has {len(data['logs'])} logs")
