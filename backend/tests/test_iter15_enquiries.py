"""Iteration 15: Tests for merged Enquiries system.
Tests:
- GET /api/admin/enquiries endpoint
- PATCH /api/admin/enquiries/{id}/status endpoint
- DELETE /api/admin/enquiries/{id} endpoint
- POST /api/orders/scope-request-form (simple enquiry: name/email/company/phone/message)
- POST /api/orders/scope-request-form (full scope fields)
- POST /api/products/request-quote REMOVED (should return 404)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"
PARTNER_CODE = "automate-accounts"

# --- Fixtures ---

@pytest.fixture(scope="module")
def admin_token():
    """Get platform admin token. Platform admin logs in WITHOUT partner_code."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
        # NO partner_code for platform admin - that's reserved
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.status_code} {resp.text}"
    token = resp.json().get("token") or resp.json().get("access_token")
    assert token, f"No token in login response: {resp.json()}"
    print(f"Admin token acquired: {token[:20]}...")
    return token


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def customer_token():
    """Get customer token to test scope-request-form endpoint.
    Platform admin login (no partner_code)."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!",
        # No partner_code for platform admin
    })
    if resp.status_code == 200:
        token = resp.json().get("token") or resp.json().get("access_token")
        if token:
            return token
    return None


@pytest.fixture(scope="module")
def customer_headers(customer_token):
    if not customer_token:
        pytest.skip("No customer token available")
    return {"Authorization": f"Bearer {customer_token}"}


# --- Tests for GET /api/admin/enquiries ---

class TestAdminEnquiriesGet:
    """Tests for GET /api/admin/enquiries endpoint."""

    def test_get_enquiries_requires_auth(self):
        """Endpoint should require authentication."""
        resp = requests.get(f"{BASE_URL}/api/admin/enquiries")
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"
        print("PASS: GET /admin/enquiries requires auth")

    def test_get_enquiries_returns_200(self, admin_headers):
        """Admin can fetch enquiries list."""
        resp = requests.get(f"{BASE_URL}/api/admin/enquiries", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code} {resp.text}"
        data = resp.json()
        print(f"PASS: GET /admin/enquiries returns 200, data: {data}")

    def test_get_enquiries_response_structure(self, admin_headers):
        """Response must have enquiries array and pagination fields."""
        resp = requests.get(f"{BASE_URL}/api/admin/enquiries", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "enquiries" in data, f"Missing 'enquiries' key in response: {data.keys()}"
        assert isinstance(data["enquiries"], list), "enquiries must be a list"
        assert "total" in data, "Missing 'total' field"
        assert "page" in data, "Missing 'page' field"
        assert "total_pages" in data, "Missing 'total_pages' field"
        print(f"PASS: enquiries response structure correct. total={data['total']}")

    def test_get_enquiries_with_status_filter(self, admin_headers):
        """Status filter should work without error."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/enquiries",
            params={"status_filter": "scope_pending"},
            headers=admin_headers
        )
        assert resp.status_code == 200, f"Status filter failed: {resp.text}"
        data = resp.json()
        assert "enquiries" in data
        # All returned items should have scope_pending status
        for e in data["enquiries"]:
            assert e["status"] == "scope_pending", f"Wrong status: {e['status']}"
        print(f"PASS: status_filter works, got {len(data['enquiries'])} results")

    def test_get_enquiries_with_email_filter(self, admin_headers):
        """Email filter should work without error."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/enquiries",
            params={"email_filter": "nonexistent@test.com"},
            headers=admin_headers
        )
        assert resp.status_code == 200, f"Email filter failed: {resp.text}"
        data = resp.json()
        assert data["enquiries"] == [], f"Should be empty for nonexistent email, got {data['enquiries']}"
        print("PASS: email_filter works, returns empty for unknown email")

    def test_get_enquiries_pagination(self, admin_headers):
        """Pagination params should work."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/enquiries",
            params={"page": 1, "per_page": 5},
            headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["enquiries"]) <= 5, "Should return at most 5 items"
        print(f"PASS: pagination works, got {len(data['enquiries'])} items")


# --- Tests for Scope Request Form ---

class TestScopeRequestForm:
    """Tests for POST /api/orders/scope-request-form endpoint."""

    def test_scope_request_form_requires_auth(self):
        """Endpoint should require authentication."""
        resp = requests.post(f"{BASE_URL}/api/orders/scope-request-form", json={
            "items": [],
            "form_data": {"name": "Test", "email": "test@test.com"}
        })
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"
        print("PASS: POST /orders/scope-request-form requires auth")

    def test_scope_request_form_simple_enquiry(self, admin_headers):
        """POST with simple contact fields should succeed (optional full scope fields)."""
        # First get a product to use
        products_resp = requests.get(f"{BASE_URL}/api/products")
        assert products_resp.status_code == 200
        products = products_resp.json().get("products", [])
        if not products:
            pytest.skip("No products available for test")

        product = products[0]
        resp = requests.post(
            f"{BASE_URL}/api/orders/scope-request-form",
            headers=admin_headers,
            json={
                "items": [{"product_id": product["id"], "quantity": 1, "inputs": {}}],
                "form_data": {
                    "name": "TEST_Enquiry User",
                    "email": "test_enquiry@example.com",
                    "company": "TEST Corp",
                    "phone": "+1 555 000 0000",
                    "message": "I am interested in your services.",
                }
            }
        )
        print(f"Simple scope request response: {resp.status_code} {resp.text[:200]}")
        # This requires a customer record for the admin user
        # If customer not found, we get 404
        if resp.status_code == 404:
            print("INFO: Admin user has no customer record - test needs a customer account")
            pytest.skip("Admin user has no customer record - endpoint requires customer")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "order_id" in data, f"Missing order_id: {data}"
        assert "order_number" in data, f"Missing order_number: {data}"
        print(f"PASS: Simple scope request created: {data['order_number']}")
        return data["order_id"]

    def test_scope_request_form_full_scope(self, admin_headers):
        """POST with full scope fields should succeed."""
        products_resp = requests.get(f"{BASE_URL}/api/products")
        products = products_resp.json().get("products", [])
        if not products:
            pytest.skip("No products available")

        product = products[0]
        resp = requests.post(
            f"{BASE_URL}/api/orders/scope-request-form",
            headers=admin_headers,
            json={
                "items": [{"product_id": product["id"], "quantity": 1, "inputs": {}}],
                "form_data": {
                    "project_summary": "TEST Full scope project summary",
                    "desired_outcomes": "Automate accounting processes",
                    "apps_involved": "Zoho Books, CRM, Spreadsheets",
                    "timeline_urgency": "ASAP - within 2 weeks",
                    "budget_range": "$5,000 - $10,000",
                    "additional_notes": "TEST iteration 15 test",
                    "name": "TEST_Full Scope User",
                    "email": "test_fullscope@example.com",
                    "company": "TEST Enterprise Ltd",
                    "phone": "+44 7700 900000",
                    "message": "Interested in full scope",
                }
            }
        )
        print(f"Full scope request response: {resp.status_code} {resp.text[:300]}")
        if resp.status_code == 404 and "Customer" in resp.text:
            pytest.skip("Admin user has no customer record - test needs a customer account")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "order_id" in data
        assert "order_number" in data
        print(f"PASS: Full scope request created: {data['order_number']}")

    def test_scope_request_form_empty_items(self, admin_headers):
        """POST with empty items array should still succeed (order created with no items)."""
        resp = requests.post(
            f"{BASE_URL}/api/orders/scope-request-form",
            headers=admin_headers,
            json={
                "items": [],
                "form_data": {
                    "name": "TEST_Empty Items User",
                    "email": "test_empty@example.com",
                    "message": "Just sending a message",
                }
            }
        )
        print(f"Empty items scope request: {resp.status_code} {resp.text[:200]}")
        if resp.status_code == 404 and "Customer" in resp.text:
            pytest.skip("Admin user has no customer record")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print("PASS: Empty items scope request created")


# --- Test that old /products/request-quote is REMOVED ---

class TestOldQuoteEndpointRemoved:
    """Verify that the customer-facing /products/request-quote is REMOVED."""

    def test_request_quote_endpoint_returns_404(self):
        """POST /api/products/request-quote should return 404 or 405 (endpoint removed).
        The path /products/{product_id} matches, but there's no POST on it → 405.
        Both 404 and 405 confirm the customer-facing POST endpoint is removed."""
        resp = requests.post(
            f"{BASE_URL}/api/products/request-quote",
            json={
                "product_id": "some-product-id",
                "product_name": "Test Product",
                "name": "Test User",
                "email": "test@test.com",
                "message": "Test message"
            }
        )
        print(f"Old request-quote response: {resp.status_code} {resp.text[:200]}")
        assert resp.status_code in [404, 405], (
            f"Expected 404 or 405 (endpoint removed), but got {resp.status_code}. "
            f"The old /products/request-quote endpoint should have been removed!"
        )
        print(f"PASS: POST /products/request-quote returns {resp.status_code} - endpoint correctly removed")

    def test_request_quote_with_auth_returns_404(self, admin_headers):
        """Even with auth, /products/request-quote should be 404."""
        resp = requests.post(
            f"{BASE_URL}/api/products/request-quote",
            headers=admin_headers,
            json={
                "product_id": "some-product-id",
                "product_name": "Test Product",
                "name": "Test User",
                "email": "test@test.com",
            }
        )
        print(f"Old request-quote with auth: {resp.status_code}")
        assert resp.status_code in [404, 405], (
            f"Expected 404/405, got {resp.status_code}. Old endpoint still accessible!"
        )
        print(f"PASS: Old /products/request-quote returns {resp.status_code} even with auth")


# --- Tests for PATCH and DELETE enquiries ---

class TestEnquiryStatusAndDelete:
    """Tests for PATCH /admin/enquiries/{id}/status and DELETE /admin/enquiries/{id}."""

    @pytest.fixture(scope="class")
    def test_enquiry_id(self, admin_headers):
        """Create a scope request order for testing status update and delete."""
        # Create an enquiry via scope-request-form if possible
        # First need a customer session; let's try to find an existing enquiry instead
        resp = requests.get(
            f"{BASE_URL}/api/admin/enquiries",
            params={"per_page": 1},
            headers=admin_headers
        )
        if resp.status_code == 200 and resp.json().get("enquiries"):
            enquiry_id = resp.json()["enquiries"][0]["id"]
            print(f"Using existing enquiry ID for tests: {enquiry_id}")
            return enquiry_id
        pytest.skip("No enquiries available for status/delete tests")

    def test_patch_enquiry_status(self, admin_headers, test_enquiry_id):
        """PATCH /admin/enquiries/{id}/status should update status."""
        resp = requests.patch(
            f"{BASE_URL}/api/admin/enquiries/{test_enquiry_id}/status",
            headers=admin_headers,
            json={"status": "responded"}
        )
        print(f"PATCH status response: {resp.status_code} {resp.text[:200]}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("status") == "responded", f"Expected status='responded', got {data}"
        print(f"PASS: Status updated to 'responded'")

    def test_patch_enquiry_status_without_field(self, admin_headers, test_enquiry_id):
        """PATCH without status field should return 400."""
        resp = requests.patch(
            f"{BASE_URL}/api/admin/enquiries/{test_enquiry_id}/status",
            headers=admin_headers,
            json={}
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        print("PASS: PATCH without status field returns 400")

    def test_patch_enquiry_status_nonexistent(self, admin_headers):
        """PATCH non-existent enquiry should return 404."""
        resp = requests.patch(
            f"{BASE_URL}/api/admin/enquiries/nonexistent-id/status",
            headers=admin_headers,
            json={"status": "closed"}
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print("PASS: PATCH non-existent enquiry returns 404")

    def test_delete_enquiry_nonexistent(self, admin_headers):
        """DELETE non-existent enquiry should return 404."""
        resp = requests.delete(
            f"{BASE_URL}/api/admin/enquiries/nonexistent-id",
            headers=admin_headers
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print("PASS: DELETE non-existent enquiry returns 404")

    def test_delete_enquiry_and_verify(self, admin_headers):
        """Create a scope order and delete it - verify it's gone."""
        # First get any existing enquiry to delete
        resp = requests.get(
            f"{BASE_URL}/api/admin/enquiries",
            headers=admin_headers,
            params={"per_page": 50}
        )
        if resp.status_code != 200:
            pytest.skip("Cannot fetch enquiries")
        enquiries = resp.json().get("enquiries", [])

        # Find a test enquiry (with TEST in name or scope_pending status)
        test_enquiry = None
        for e in enquiries:
            scope_data = e.get("scope_form_data") or {}
            name = scope_data.get("name", "")
            if "TEST" in str(name) or e.get("status") == "scope_pending":
                test_enquiry = e
                break

        if not test_enquiry:
            pytest.skip("No suitable test enquiry to delete")

        delete_resp = requests.delete(
            f"{BASE_URL}/api/admin/enquiries/{test_enquiry['id']}",
            headers=admin_headers
        )
        print(f"DELETE response: {delete_resp.status_code} {delete_resp.text[:200]}")
        assert delete_resp.status_code == 200, f"DELETE failed: {delete_resp.text}"

        # Verify it's gone
        get_resp = requests.get(
            f"{BASE_URL}/api/admin/enquiries",
            headers=admin_headers,
            params={"per_page": 50}
        )
        remaining = get_resp.json().get("enquiries", [])
        deleted_ids = [e["id"] for e in remaining]
        assert test_enquiry["id"] not in deleted_ids, "Enquiry still present after deletion!"
        print(f"PASS: Enquiry {test_enquiry['id']} deleted and verified gone")


# --- Test Enquiries data structure ---

class TestEnquiriesDataStructure:
    """Verify enquiry objects have the expected fields."""

    def test_enquiry_fields_structure(self, admin_headers):
        """Each enquiry object should have required fields."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/enquiries",
            headers=admin_headers
        )
        assert resp.status_code == 200
        enquiries = resp.json().get("enquiries", [])

        if not enquiries:
            print("INFO: No enquiries in DB - cannot verify field structure")
            return

        e = enquiries[0]
        required_fields = ["id", "status", "created_at", "order_number", "type"]
        for field in required_fields:
            assert field in e, f"Missing field '{field}' in enquiry: {list(e.keys())}"
        assert e.get("type") == "scope_request", f"Expected type='scope_request', got {e.get('type')}"
        print(f"PASS: Enquiry has all required fields. Sample: type={e['type']}, status={e['status']}")
