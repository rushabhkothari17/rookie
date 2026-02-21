"""
Iteration 22 bug fixes testing:
1. validate-scope endpoint accepts both short ID (8 chars) and full UUID
2. scope-request-form endpoint writes notes_json with product_intake + scope_form
3. Error message wording: 'Invalid Scope Id' (capital S, lowercase d)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"
TEST_SCOPE_ARTICLE_FULL_ID = "2fc74332-bd67-4e48-bc94-28aae13653db"
TEST_SCOPE_ARTICLE_SHORT_ID = "2fc74332"
RFQ_PRODUCT_ID = "prod_fixed_scope_dev"


@pytest.fixture(scope="module")
def admin_token():
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return resp.json().get("token")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ─────────────────────────────────────────────────────────────
# Fix 1: validate-scope accepts short ID (first 8 chars)
# ─────────────────────────────────────────────────────────────
class TestValidateScopeShortId:
    """
    P0 fix: validate-scope endpoint now accepts both full UUID and short ID (first 8 chars).
    '2fc74332' should resolve to the Test Scope Final article.
    """

    def test_validate_scope_with_full_uuid(self, auth_headers):
        """validate-scope returns valid=True with full UUID."""
        resp = requests.get(
            f"{BASE_URL}/api/articles/{TEST_SCOPE_ARTICLE_FULL_ID}/validate-scope",
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("valid") is True, f"Expected valid=True, got {data}"
        assert data.get("price") in [1500, 1500.0], f"Expected price=1500, got {data.get('price')}"
        assert data.get("article_id") == TEST_SCOPE_ARTICLE_FULL_ID, f"Expected article_id={TEST_SCOPE_ARTICLE_FULL_ID}, got {data.get('article_id')}"
        print(f"PASS: Full UUID validates correctly: valid={data['valid']}, price={data['price']}")

    def test_validate_scope_with_short_id(self, auth_headers):
        """P0 fix: validate-scope returns valid=True with short ID (first 8 chars)."""
        resp = requests.get(
            f"{BASE_URL}/api/articles/{TEST_SCOPE_ARTICLE_SHORT_ID}/validate-scope",
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("valid") is True, f"Expected valid=True for short ID, got {data}"
        assert data.get("price") in [1500, 1500.0], f"Expected price=1500 for short ID, got {data.get('price')}"
        # Should resolve to the full article ID
        assert data.get("article_id") == TEST_SCOPE_ARTICLE_FULL_ID, f"Expected article_id={TEST_SCOPE_ARTICLE_FULL_ID} for short ID, got {data.get('article_id')}"
        print(f"PASS: Short ID '2fc74332' validates correctly: valid={data['valid']}, price={data['price']}")

    def test_validate_scope_invalid_id_returns_404(self, auth_headers):
        """Invalid scope ID returns 404 with detail 'Invalid Scope Id'."""
        resp = requests.get(
            f"{BASE_URL}/api/articles/00000000/validate-scope",
            headers=auth_headers,
        )
        assert resp.status_code in [400, 404], f"Expected 400/404, got {resp.status_code}: {resp.text}"
        data = resp.json()
        detail = data.get("detail", "")
        assert detail == "Invalid Scope Id", f"Expected 'Invalid Scope Id' (capital S, lowercase d), got '{detail}'"
        print(f"PASS: Invalid scope ID returns error: '{detail}'")

    def test_validate_scope_short_and_full_return_same_article(self, auth_headers):
        """Both short and full ID should return the same article details."""
        resp_short = requests.get(
            f"{BASE_URL}/api/articles/{TEST_SCOPE_ARTICLE_SHORT_ID}/validate-scope",
            headers=auth_headers,
        )
        resp_full = requests.get(
            f"{BASE_URL}/api/articles/{TEST_SCOPE_ARTICLE_FULL_ID}/validate-scope",
            headers=auth_headers,
        )
        assert resp_short.status_code == 200
        assert resp_full.status_code == 200
        short_data = resp_short.json()
        full_data = resp_full.json()
        assert short_data.get("article_id") == full_data.get("article_id"), \
            f"Short and full ID should resolve to same article. Short: {short_data.get('article_id')}, Full: {full_data.get('article_id')}"
        assert short_data.get("price") == full_data.get("price"), \
            f"Prices should match. Short: {short_data.get('price')}, Full: {full_data.get('price')}"
        print(f"PASS: Short and full ID resolve to same article: {short_data.get('article_id')}")


# ─────────────────────────────────────────────────────────────
# Fix 2: scope-request-form writes notes_json with product_intake + scope_form
# ─────────────────────────────────────────────────────────────
class TestScopeRequestFormNotesJson:
    """
    Fix: POST /api/orders/scope-request-form now includes notes_json with
    product_intake and scope_form data.
    """

    created_order_id = None

    def test_scope_request_form_creates_order_with_notes_json(self, auth_headers):
        """POST /api/orders/scope-request-form creates order with notes_json containing product_intake and scope_form."""
        payload = {
            "items": [
                {
                    "product_id": RFQ_PRODUCT_ID,
                    "quantity": 1,
                    "inputs": {"company_name": "TEST_Company", "project_name": "TEST_Project"},
                }
            ],
            "form_data": {
                "project_summary": "TEST_scope_form_project_summary",
                "desired_outcomes": "TEST desired outcome",
                "apps_involved": "TEST Xero, Salesforce",
                "timeline_urgency": "1-3 months",
                "budget_range": "5000-10000",
                "additional_notes": "TEST additional notes",
            },
        }
        resp = requests.post(
            f"{BASE_URL}/api/orders/scope-request-form",
            json=payload,
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "order_id" in data, f"Expected 'order_id' in response, got {data}"
        TestScopeRequestFormNotesJson.created_order_id = data.get("order_id")
        print(f"PASS: scope-request-form created order: {TestScopeRequestFormNotesJson.created_order_id}")

    def test_scope_request_form_order_has_notes_json(self, auth_headers):
        """Verify the created order has notes_json with product_intake and scope_form fields."""
        if not TestScopeRequestFormNotesJson.created_order_id:
            pytest.skip("Order not created in previous test")
        
        order_id = TestScopeRequestFormNotesJson.created_order_id
        # Get order via admin endpoint
        resp = requests.get(
            f"{BASE_URL}/api/admin/orders?per_page=100",
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        orders = resp.json().get("orders", [])
        order = next((o for o in orders if o.get("id") == order_id), None)
        assert order is not None, f"Order {order_id} not found in admin orders list"
        
        notes_json = order.get("notes_json")
        assert notes_json is not None, f"Expected notes_json in order, got None. Order: {order}"
        
        # Check product_intake field
        assert "product_intake" in notes_json, f"Expected 'product_intake' in notes_json, got keys: {list(notes_json.keys())}"
        product_intake = notes_json["product_intake"]
        assert RFQ_PRODUCT_ID in product_intake, f"Expected '{RFQ_PRODUCT_ID}' in product_intake, got {product_intake}"
        
        # Check scope_form field
        assert "scope_form" in notes_json, f"Expected 'scope_form' in notes_json, got keys: {list(notes_json.keys())}"
        scope_form = notes_json["scope_form"]
        assert "project_summary" in scope_form, f"Expected 'project_summary' in scope_form, got {scope_form}"
        assert scope_form["project_summary"] == "TEST_scope_form_project_summary", \
            f"Expected project_summary='TEST_scope_form_project_summary', got {scope_form.get('project_summary')}"
        
        print(f"PASS: notes_json has product_intake and scope_form. Keys: {list(notes_json.keys())}")

    def test_scope_request_form_notes_json_payment_field(self, auth_headers):
        """Verify notes_json also has payment field with method=scope_request_form."""
        if not TestScopeRequestFormNotesJson.created_order_id:
            pytest.skip("Order not created in previous test")
        
        order_id = TestScopeRequestFormNotesJson.created_order_id
        resp = requests.get(
            f"{BASE_URL}/api/admin/orders?per_page=100",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        orders = resp.json().get("orders", [])
        order = next((o for o in orders if o.get("id") == order_id), None)
        assert order is not None
        
        notes_json = order.get("notes_json", {})
        payment = notes_json.get("payment", {})
        assert payment.get("method") == "scope_request_form", \
            f"Expected payment.method='scope_request_form', got {payment}"
        print(f"PASS: notes_json.payment.method='scope_request_form'")

    def test_cleanup_scope_request_form_order(self, auth_headers):
        """Cleanup: Delete the TEST_ scope-request-form order."""
        if not TestScopeRequestFormNotesJson.created_order_id:
            pytest.skip("No order to delete")
        
        order_id = TestScopeRequestFormNotesJson.created_order_id
        resp = requests.delete(
            f"{BASE_URL}/api/admin/orders/{order_id}",
            json={"reason": "TEST cleanup - iter22"},
            headers=auth_headers,
        )
        # Accept 200, 204, or 404 (already deleted)
        assert resp.status_code in [200, 204, 404], f"Cleanup failed: {resp.status_code}: {resp.text}"
        print(f"PASS: Cleaned up test order {order_id}")


# ─────────────────────────────────────────────────────────────
# Fix 3: Article visibility/content verification via API
# ─────────────────────────────────────────────────────────────
class TestArticleMetadata:
    """
    Verify article API returns the id field needed for Short ID/Article ID display.
    """

    def test_article_api_returns_id_field(self, auth_headers):
        """Article API should return 'id' field for Short ID display."""
        resp = requests.get(
            f"{BASE_URL}/api/articles/{TEST_SCOPE_ARTICLE_FULL_ID}",
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        article = data.get("article", data)
        
        assert "id" in article, f"Expected 'id' field in article response, got keys: {list(article.keys())}"
        article_id = article["id"]
        assert len(article_id) == 36, f"Expected UUID length 36, got {len(article_id)}: {article_id}"
        
        # Short ID is first 8 chars
        short_id = article_id[:8]
        assert short_id == TEST_SCOPE_ARTICLE_SHORT_ID, \
            f"Expected short_id={TEST_SCOPE_ARTICLE_SHORT_ID}, got {short_id}"
        
        print(f"PASS: Article has id={article_id}, short_id={short_id}")

    def test_article_api_returns_title(self, auth_headers):
        """Article API returns title for Test Scope Final article."""
        resp = requests.get(
            f"{BASE_URL}/api/articles/{TEST_SCOPE_ARTICLE_FULL_ID}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        article = data.get("article", data)
        title = article.get("title", "")
        assert title, f"Expected non-empty title, got: '{title}'"
        print(f"PASS: Article title: '{title}'")
