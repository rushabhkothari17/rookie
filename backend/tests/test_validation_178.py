"""
Iteration 178: Test backend validation for manual enquiries endpoint
and form validation checks
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAdminAuth:
    """Admin authentication for testing"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get admin auth token"""
        # Login with partner code first
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@automateaccounts.local",
            "password": "ChangeMe123!",
            "partner_code": "automate-accounts"
        })
        if response.status_code == 200:
            token = response.json().get("access_token") or response.json().get("token")
            if token:
                return {"Authorization": f"Bearer {token}"}
        # Try without partner_code
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@automateaccounts.local",
            "password": "ChangeMe123!"
        })
        if response.status_code == 200:
            token = response.json().get("access_token") or response.json().get("token")
            if token:
                return {"Authorization": f"Bearer {token}"}
        pytest.skip("Authentication failed - skipping authenticated tests")


class TestManualEnquiryEndpoint(TestAdminAuth):
    """Test POST /api/admin/enquiries/manual endpoint"""

    def test_create_enquiry_with_valid_email(self, auth_headers):
        """Test creating an enquiry with valid customer email"""
        response = requests.post(
            f"{BASE_URL}/api/admin/enquiries/manual",
            json={
                "customer_email": "admin@automateaccounts.local",
                "product_id": None,
                "notes": "Test enquiry from automated tests"
            },
            headers=auth_headers
        )
        print(f"Create enquiry status: {response.status_code}")
        print(f"Create enquiry response: {response.text[:300]}")
        assert response.status_code == 200
        data = response.json()
        assert "order_number" in data
        assert "id" in data
        assert data["order_number"].startswith("ENQ-")
        print(f"Created enquiry: {data['order_number']}")

    def test_create_enquiry_with_invalid_email_returns_404(self, auth_headers):
        """Test creating enquiry with non-existent email returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/admin/enquiries/manual",
            json={
                "customer_email": "nonexistent-TEST-user@example.com",
                "product_id": None,
                "notes": None
            },
            headers=auth_headers
        )
        print(f"Invalid email status: {response.status_code}")
        print(f"Invalid email response: {response.text[:300]}")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower() or "Customer not found" in data["detail"]

    def test_create_enquiry_without_auth_returns_401(self):
        """Test that endpoint requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/admin/enquiries/manual",
            json={
                "customer_email": "admin@automateaccounts.local",
                "product_id": None,
                "notes": None
            }
        )
        print(f"No auth status: {response.status_code}")
        assert response.status_code in [401, 403]

    def test_create_enquiry_missing_email_returns_422(self, auth_headers):
        """Test creating enquiry without email field returns 422"""
        response = requests.post(
            f"{BASE_URL}/api/admin/enquiries/manual",
            json={
                "product_id": None,
                "notes": "test"
            },
            headers=auth_headers
        )
        print(f"Missing email status: {response.status_code}")
        # Should fail validation (422) since customer_email is required
        assert response.status_code == 422

    def test_enquiries_list_endpoint(self, auth_headers):
        """Test that enquiries list endpoint works"""
        response = requests.get(
            f"{BASE_URL}/api/admin/enquiries",
            headers=auth_headers
        )
        print(f"List enquiries status: {response.status_code}")
        assert response.status_code == 200
        data = response.json()
        assert "enquiries" in data
        assert isinstance(data["enquiries"], list)
        print(f"Found {len(data['enquiries'])} enquiries")
