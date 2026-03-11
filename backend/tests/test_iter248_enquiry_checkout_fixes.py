"""
Tests for iteration 248:
- Admin Manual Enquiry creation (customer_id, form_id, form_data)
- Enquiry PDF download endpoint
- Customer dropdown API
- Forms dropdown API
- Products-all API for product dropdown
- Enquiry list loads without errors
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


@pytest.fixture(scope="module")
def admin_token():
    """Login as admin and return token."""
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={
            "email": "admin@automateaccounts.local",
            "password": "ChangeMe123!",
        },
    )
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    data = r.json()
    token = data.get("token") or data.get("access_token")
    assert token, "No token returned"
    return token


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ──────────────────────────────────────────────────────────────
# 1. Enquiry list API
# ──────────────────────────────────────────────────────────────

class TestEnquiriesListAPI:
    """Enquiries list loads without error"""

    def test_enquiries_list_returns_200(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/enquiries?page=1&per_page=20", headers=auth_headers)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    def test_enquiries_list_has_expected_keys(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/enquiries?page=1&per_page=20", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        # Must have enquiries list
        assert "enquiries" in data, "Missing 'enquiries' key in response"
        assert isinstance(data["enquiries"], list), "'enquiries' should be a list"


# ──────────────────────────────────────────────────────────────
# 2. Customer dropdown API
# ──────────────────────────────────────────────────────────────

class TestCustomersDropdownAPI:
    """Customer dropdown data for Create Enquiry dialog"""

    def test_admin_customers_returns_200(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/customers?per_page=200", headers=auth_headers)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    def test_admin_customers_has_customers_key(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/customers?per_page=200", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "customers" in data, "Missing 'customers' key"
        assert isinstance(data["customers"], list)


# ──────────────────────────────────────────────────────────────
# 3. Forms dropdown API
# ──────────────────────────────────────────────────────────────

class TestFormsDropdownAPI:
    """Forms dropdown for Create Enquiry dialog"""

    def test_admin_forms_returns_200(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/forms", headers=auth_headers)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    def test_admin_forms_has_forms_key(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/forms", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "forms" in data, "Missing 'forms' key"
        assert isinstance(data["forms"], list)


# ──────────────────────────────────────────────────────────────
# 4. Products-all API
# ──────────────────────────────────────────────────────────────

class TestProductsAllAPI:
    """Products dropdown for Create Enquiry dialog"""

    def test_admin_products_all_returns_200(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/products-all?per_page=200", headers=auth_headers)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    def test_admin_products_all_has_products_key(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/products-all?per_page=200", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "products" in data, "Missing 'products' key"
        assert isinstance(data["products"], list)


# ──────────────────────────────────────────────────────────────
# 5. Manual Enquiry creation
# ──────────────────────────────────────────────────────────────

class TestManualEnquiryCreation:
    """Admin creates manual enquiry using customer_id (new model)"""

    def _get_first_customer_id(self, auth_headers):
        """Helper to get first available customer ID."""
        r = requests.get(f"{BASE_URL}/api/admin/customers?per_page=200", headers=auth_headers)
        customers = r.json().get("customers", [])
        return customers[0]["id"] if customers else None

    def test_manual_enquiry_requires_valid_customer_id(self, auth_headers):
        """Using an invalid customer_id should return 404."""
        payload = {
            "customer_id": "INVALID_CUSTOMER_ID_DOES_NOT_EXIST",
            "product_id": None,
            "form_id": None,
            "form_data": None,
            "notes": "Test notes",
        }
        r = requests.post(f"{BASE_URL}/api/admin/enquiries/manual", json=payload, headers=auth_headers)
        assert r.status_code == 404, f"Expected 404 for invalid customer, got {r.status_code}: {r.text}"

    def test_manual_enquiry_creates_with_customer_id(self, auth_headers):
        """If customers exist, creating an enquiry with valid customer_id succeeds."""
        customer_id = self._get_first_customer_id(auth_headers)
        if not customer_id:
            pytest.skip("No customers found — skipping manual enquiry creation test")

        payload = {
            "customer_id": customer_id,
            "product_id": None,
            "form_id": None,
            "form_data": {"message": "TEST_Manual enquiry created by test suite"},
            "notes": "TEST_automated test note",
        }
        r = requests.post(f"{BASE_URL}/api/admin/enquiries/manual", json=payload, headers=auth_headers)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

        data = r.json()
        assert "order_number" in data, "Response missing 'order_number'"
        assert data["order_number"].startswith("ENQ-"), f"Unexpected order_number format: {data['order_number']}"
        assert "id" in data, "Response missing 'id'"
        return data["id"]

    def test_manual_enquiry_persists_in_list(self, auth_headers):
        """After creating, the enquiry should appear in the list."""
        customer_id = self._get_first_customer_id(auth_headers)
        if not customer_id:
            pytest.skip("No customers found")

        payload = {
            "customer_id": customer_id,
            "form_data": {"message": "TEST_enquiry persistence check"},
        }
        create_r = requests.post(f"{BASE_URL}/api/admin/enquiries/manual", json=payload, headers=auth_headers)
        assert create_r.status_code == 200

        created_id = create_r.json()["id"]
        # Fetch list and look for the created enquiry
        list_r = requests.get(f"{BASE_URL}/api/admin/enquiries?per_page=500", headers=auth_headers)
        assert list_r.status_code == 200
        enquiries = list_r.json().get("enquiries", [])
        ids = [e["id"] for e in enquiries]
        assert created_id in ids, f"Created enquiry {created_id} not found in list"


# ──────────────────────────────────────────────────────────────
# 6. Enquiry PDF download endpoint
# ──────────────────────────────────────────────────────────────

class TestEnquiryPdfEndpoint:
    """PDF endpoint must exist and return bytes for an existing enquiry"""

    def _get_first_enquiry_id(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/enquiries?per_page=500", headers=auth_headers)
        enquiries = r.json().get("enquiries", [])
        return enquiries[0]["id"] if enquiries else None

    def test_pdf_endpoint_for_existing_enquiry(self, auth_headers):
        """PDF download returns 200 and content-type PDF for existing enquiry."""
        enquiry_id = self._get_first_enquiry_id(auth_headers)
        if not enquiry_id:
            pytest.skip("No enquiries found to test PDF download")

        r = requests.get(
            f"{BASE_URL}/api/admin/enquiries/{enquiry_id}/pdf",
            headers=auth_headers,
        )
        assert r.status_code == 200, f"Expected 200 for PDF, got {r.status_code}: {r.text}"
        content_type = r.headers.get("content-type", "")
        assert "pdf" in content_type.lower() or len(r.content) > 100, \
            f"Expected PDF content, got content-type: {content_type}"

    def test_pdf_endpoint_returns_bytes(self, auth_headers):
        """PDF should be non-empty binary content."""
        enquiry_id = self._get_first_enquiry_id(auth_headers)
        if not enquiry_id:
            pytest.skip("No enquiries found")

        r = requests.get(
            f"{BASE_URL}/api/admin/enquiries/{enquiry_id}/pdf",
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert len(r.content) > 500, f"PDF content too small: {len(r.content)} bytes"

    def test_pdf_endpoint_invalid_id_returns_404(self, auth_headers):
        """Non-existent enquiry should return 404 for PDF."""
        r = requests.get(
            f"{BASE_URL}/api/admin/enquiries/INVALID_ID_999/pdf",
            headers=auth_headers,
        )
        assert r.status_code == 404, f"Expected 404 for invalid ID, got {r.status_code}"
