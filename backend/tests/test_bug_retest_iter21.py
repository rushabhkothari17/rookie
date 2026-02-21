"""
Bug retest tests for Iteration 21:
1. Scope unlock cart price - calculate_price() now detects _scope_unlock in inputs
2. notes_json captured in scope_request orders (via /api/orders/scope-request)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"
TEST_SCOPE_ARTICLE_ID = "2fc74332-bd67-4e48-bc94-28aae13653db"
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
# Fix 1: Scope Unlock Cart Price
# ─────────────────────────────────────────────────────────────
class TestScopeUnlockCartPrice:
    """
    After fix: calculate_price() now detects _scope_unlock in inputs.
    When _scope_unlock is present with a price, the item should be treated as
    a one-time purchase at the scope price (not $0 scope_request).
    """

    def test_scope_article_exists_and_has_price(self, auth_headers):
        """Verify the test Scope-Final article (2fc74332) exists with price=1500."""
        resp = requests.get(
            f"{BASE_URL}/api/articles/{TEST_SCOPE_ARTICLE_ID}",
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("price") == 1500, f"Expected price=1500, got {data.get('price')}"
        print(f"PASS: Scope article exists with price={data['price']}")

    def test_validate_scope_id_returns_price(self, auth_headers):
        """Validate scope ID returns valid=true and price=1500."""
        resp = requests.post(
            f"{BASE_URL}/api/articles/validate-scope",
            json={"scope_id": TEST_SCOPE_ARTICLE_ID, "product_id": RFQ_PRODUCT_ID},
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("valid") is True, f"Expected valid=True, got {data.get('valid')}"
        assert data.get("price") == 1500, f"Expected price=1500, got {data.get('price')}"
        print(f"PASS: validate-scope returns valid=True, price={data.get('price')}")

    def test_order_preview_without_scope_unlock_returns_scope_request(self, auth_headers):
        """Without _scope_unlock, scope_request product returns is_scope_request=True, subtotal=0."""
        resp = requests.post(
            f"{BASE_URL}/api/orders/preview",
            json={
                "items": [
                    {
                        "product_id": RFQ_PRODUCT_ID,
                        "quantity": 1,
                        "inputs": {},
                    }
                ]
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        scope_items = data.get("scope_request", {}).get("items", [])
        assert len(scope_items) > 0, "Expected item in scope_request group (no unlock)"
        subtotal = scope_items[0].get("pricing", {}).get("subtotal", -1)
        assert subtotal == 0.0, f"Expected subtotal=0 (no unlock), got {subtotal}"
        print(f"PASS: Without scope_unlock, item is in scope_request with subtotal=0")

    def test_order_preview_with_scope_unlock_returns_one_time_at_1500(self, auth_headers):
        """
        THE KEY TEST: With _scope_unlock in inputs, scope_request product should
        return is_scope_request=False and subtotal=1500 (not $0).
        """
        resp = requests.post(
            f"{BASE_URL}/api/orders/preview",
            json={
                "items": [
                    {
                        "product_id": RFQ_PRODUCT_ID,
                        "quantity": 1,
                        "inputs": {
                            "_scope_unlock": {
                                "article_id": TEST_SCOPE_ARTICLE_ID,
                                "price": 1500,
                                "title": "Test Scope-Final",
                            }
                        },
                    }
                ]
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        print(f"Preview response: {data}")

        # The item should NOT be in scope_request group
        scope_items = data.get("scope_request", {}).get("items", [])
        assert len(scope_items) == 0, f"Item should NOT be in scope_request after unlock, but got {scope_items}"

        # The item SHOULD be in one_time group
        one_time_items = data.get("one_time", {}).get("items", [])
        assert len(one_time_items) > 0, "Item should be in one_time group after scope unlock"

        subtotal = one_time_items[0].get("pricing", {}).get("subtotal", -1)
        assert subtotal == 1500.0, f"Expected subtotal=1500 after scope unlock, got {subtotal}"

        is_scope_request = one_time_items[0].get("pricing", {}).get("is_scope_request", True)
        assert is_scope_request is False, f"Expected is_scope_request=False after unlock, got {is_scope_request}"

        print(f"PASS: With scope_unlock, item is in one_time group with subtotal={subtotal}")

    def test_order_preview_with_scope_unlock_totals_correct(self, auth_headers):
        """Verify the overall totals in order preview are correct with scope unlock."""
        resp = requests.post(
            f"{BASE_URL}/api/orders/preview",
            json={
                "items": [
                    {
                        "product_id": RFQ_PRODUCT_ID,
                        "quantity": 1,
                        "inputs": {
                            "_scope_unlock": {
                                "article_id": TEST_SCOPE_ARTICLE_ID,
                                "price": 1500,
                                "title": "Test Scope-Final",
                            }
                        },
                    }
                ]
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        one_time = data.get("one_time", {})
        subtotal = one_time.get("subtotal", -1)
        assert subtotal == 1500.0, f"Expected one_time subtotal=1500, got {subtotal}"
        print(f"PASS: Order preview one_time subtotal={subtotal}")


# ─────────────────────────────────────────────────────────────
# Fix 2: notes_json in scope_request orders
# ─────────────────────────────────────────────────────────────
class TestNotesJsonInScopeRequest:
    """
    Verify that scope_request orders have notes_json captured.
    Uses the /api/orders/scope-request endpoint.
    """

    created_order_id = None

    def test_scope_request_order_is_created(self, auth_headers):
        """Submit a scope_request and verify it's created successfully."""
        resp = requests.post(
            f"{BASE_URL}/api/orders/scope-request",
            json={
                "items": [
                    {
                        "product_id": RFQ_PRODUCT_ID,
                        "quantity": 1,
                        "inputs": {
                            "project_notes": "Test scope request from iteration 21 tests"
                        },
                    }
                ]
            },
            headers=auth_headers,
        )
        assert resp.status_code in (200, 201), f"Expected 200/201, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "order_id" in data or "id" in data, f"No order_id in response: {data}"
        TestNotesJsonInScopeRequest.created_order_id = data.get("order_id") or data.get("id")
        print(f"PASS: Scope request order created with id={TestNotesJsonInScopeRequest.created_order_id}")

    def test_scope_request_order_has_notes_json(self, auth_headers):
        """Fetch the created scope_request order and verify notes_json is present."""
        if not TestNotesJsonInScopeRequest.created_order_id:
            pytest.skip("No order_id available from previous test")

        # Get admin orders list and find this order
        resp = requests.get(
            f"{BASE_URL}/api/admin/orders",
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        orders = resp.json().get("orders", resp.json() if isinstance(resp.json(), list) else [])
        
        # Find our order
        our_order = None
        for order in orders:
            if order.get("id") == TestNotesJsonInScopeRequest.created_order_id:
                our_order = order
                break

        if not our_order:
            # Try by order_number pattern or type
            for order in orders:
                if order.get("type") == "scope_request" and order.get("payment_method") == "scope_request":
                    our_order = order
                    break

        assert our_order is not None, f"Could not find created order {TestNotesJsonInScopeRequest.created_order_id} in orders list"

        notes_json = our_order.get("notes_json")
        assert notes_json is not None, f"notes_json is missing from scope_request order: {our_order}"
        assert "product_intake" in notes_json, f"notes_json missing product_intake: {notes_json}"
        assert "payment" in notes_json, f"notes_json missing payment: {notes_json}"
        assert "system_metadata" in notes_json, f"notes_json missing system_metadata: {notes_json}"
        print(f"PASS: Scope request order has notes_json with keys: {list(notes_json.keys())}")

    def test_scope_request_order_notes_json_has_product_intake(self, auth_headers):
        """Verify notes_json.product_intake captures the product inputs."""
        if not TestNotesJsonInScopeRequest.created_order_id:
            pytest.skip("No order_id available")

        resp = requests.get(
            f"{BASE_URL}/api/admin/orders",
            headers=auth_headers,
        )
        orders = resp.json().get("orders", resp.json() if isinstance(resp.json(), list) else [])

        our_order = None
        for order in orders:
            if order.get("id") == TestNotesJsonInScopeRequest.created_order_id:
                our_order = order
                break

        if not our_order:
            pytest.skip("Order not found in list")

        notes_json = our_order.get("notes_json", {})
        product_intake = notes_json.get("product_intake", {})
        assert RFQ_PRODUCT_ID in product_intake, (
            f"Expected {RFQ_PRODUCT_ID} in product_intake, got keys: {list(product_intake.keys())}"
        )
        print(f"PASS: notes_json.product_intake has product {RFQ_PRODUCT_ID}")

    def test_cleanup_scope_request_order(self, auth_headers):
        """Cleanup: Delete the test scope request order."""
        if not TestNotesJsonInScopeRequest.created_order_id:
            pytest.skip("No order_id to cleanup")
        resp = requests.delete(
            f"{BASE_URL}/api/admin/orders/{TestNotesJsonInScopeRequest.created_order_id}",
            json={"reason": "Test cleanup iter21"},
            headers=auth_headers,
        )
        print(f"Cleanup order {TestNotesJsonInScopeRequest.created_order_id}: status={resp.status_code}")
