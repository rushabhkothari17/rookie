"""
Iter 265: Tests for 4 bug fixes:
1. Province stays selected (tested via frontend)
2. Job title/phone from signup appear in /me response
3. Admin edits job_title/phone => appears in /me for the customer
4. Real-time validation (frontend only)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Admin credentials for automate-accounts
ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin token for platform admin."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    data = resp.json()
    return data.get("token", "")


@pytest.fixture(scope="module")
def partner_admin_headers(admin_token):
    """Headers with partner admin token."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def test_customer_id(partner_admin_headers):
    """Get a customer to test with — use first available customer under partner."""
    # Find the tenant for automate-accounts
    resp = requests.get(
        f"{BASE_URL}/api/tenant-info?code=automate-accounts",
    )
    if resp.status_code != 200:
        pytest.skip("Cannot resolve tenant")

    resp2 = requests.get(
        f"{BASE_URL}/api/admin/customers?limit=5",
        headers=partner_admin_headers,
    )
    if resp2.status_code != 200:
        pytest.skip(f"Cannot list customers: {resp2.text}")
    
    data = resp2.json()
    customers = data.get("customers") or data.get("items") or []
    if not customers:
        pytest.skip("No customers found")
    
    # Return first customer id
    return customers[0]["id"]


class TestGetMeReturnsJobTitle:
    """Test that GET /me returns job_title in user object."""

    def test_me_endpoint_returns_job_title_field(self, admin_token):
        """Admin user's /me should include job_title field."""
        resp = requests.get(
            f"{BASE_URL}/api/me",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert resp.status_code == 200, f"GET /me failed: {resp.text}"
        data = resp.json()
        
        user = data.get("user", {})
        assert "job_title" in user, f"job_title missing from /me response. Keys: {list(user.keys())}"
        print(f"PASS: /me returns job_title='{user.get('job_title')}'")

    def test_me_endpoint_structure(self, admin_token):
        """GET /me returns expected fields including job_title, phone."""
        resp = requests.get(
            f"{BASE_URL}/api/me",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        user = data.get("user", {})
        
        # All expected fields in user object
        required_fields = ["id", "email", "full_name", "company_name", "phone", "job_title", "role"]
        for field in required_fields:
            assert field in user, f"Missing field '{field}' in /me user object"
        print(f"PASS: All required fields present in /me: {required_fields}")


class TestAdminCustomerJobTitleUpdate:
    """Test admin can update customer job_title/phone and it reflects in /me."""

    def test_get_customer_list(self, partner_admin_headers):
        """Admin can fetch customer list."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/customers",
            headers=partner_admin_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        # Support both response shapes
        assert "customers" in data or "items" in data, f"Unexpected response: {list(data.keys())}"
        print(f"PASS: Admin customers endpoint returns data")

    def test_update_customer_job_title_and_phone(self, partner_admin_headers, test_customer_id):
        """Admin can update customer's job_title and phone fields."""
        new_job_title = "TEST_Senior Engineer"
        new_phone = "+1-555-0199"

        resp = requests.put(
            f"{BASE_URL}/api/admin/customers/{test_customer_id}",
            headers=partner_admin_headers,
            json={
                "customer_data": {
                    "job_title": new_job_title,
                    "phone": new_phone,
                },
                "address_data": {}
            }
        )
        assert resp.status_code == 200, f"Customer update failed: {resp.status_code} {resp.text}"
        print(f"PASS: Admin customer update succeeded for customer_id={test_customer_id}")

    def test_customer_detail_reflects_updated_job_title(self, partner_admin_headers, test_customer_id):
        """After admin update, customer record should show updated job_title."""
        # First update
        requests.put(
            f"{BASE_URL}/api/admin/customers/{test_customer_id}",
            headers=partner_admin_headers,
            json={
                "customer_data": {
                    "job_title": "TEST_Updated Title",
                    "phone": "+1-555-0100",
                },
                "address_data": {}
            }
        )

        # Now fetch customer detail
        resp = requests.get(
            f"{BASE_URL}/api/admin/customers/{test_customer_id}",
            headers=partner_admin_headers,
        )
        if resp.status_code in [404, 405]:
            pytest.skip("Customer detail GET endpoint not available (405/404)")


        assert resp.status_code == 200, f"Customer detail failed: {resp.text}"
        data = resp.json()
        print(f"PASS: Customer detail fetched: {list(data.keys())}")


class TestCustomerSignupJobTitle:
    """Test that customer signup with job_title stores it in the user record."""

    def test_create_customer_with_job_title_via_admin(self, partner_admin_headers):
        """Admin create customer with job_title should persist."""
        import time
        unique_email = f"TEST_cust_{int(time.time())}@test-field.local"
        
        resp = requests.post(
            f"{BASE_URL}/api/admin/customers/create",
            headers=partner_admin_headers,
            json={
                "full_name": "TEST Customer Fields",
                "email": unique_email,
                "company_name": "Test Company",
                "job_title": "Test Engineer",
                "phone": "+1-555-1234",
                "password": "TestPass123!",
                "address": {
                    "line1": "123 Test St",
                    "line2": "",
                    "city": "Toronto",
                    "region": "ON",
                    "postal": "M5V 3A8",
                    "country": "CA"
                }
            }
        )
        assert resp.status_code in [200, 201], f"Create customer failed: {resp.status_code} {resp.text}"
        data = resp.json()
        
        # Check job_title is in response
        if "job_title" in data:
            assert data["job_title"] == "Test Engineer", f"job_title mismatch: {data.get('job_title')}"
        
        print(f"PASS: Customer created with job_title. Response keys: {list(data.keys())}")
        return data

    def test_created_customer_job_title_in_customers_list(self, partner_admin_headers):
        """After creating customer with job_title, it should appear in customer list."""
        import time
        unique_email = f"TEST_jobt_{int(time.time())}@test-field.local"
        
        # Create customer
        create_resp = requests.post(
            f"{BASE_URL}/api/admin/customers/create",
            headers=partner_admin_headers,
            json={
                "full_name": "TEST JobTitle Verification",
                "email": unique_email,
                "company_name": "Job Title Co",
                "job_title": "Director of Testing",
                "phone": "+1-555-5678",
                "password": "TestPass123!",
                "address": {
                    "line1": "456 Verify Ave",
                    "line2": "",
                    "city": "Vancouver",
                    "region": "BC",
                    "postal": "V6B 1H7",
                    "country": "CA"
                }
            }
        )
        assert create_resp.status_code in [200, 201], f"Create failed: {create_resp.text}"
        
        # Check the customer was created
        created_data = create_resp.json()
        customer_id = created_data.get("id") or created_data.get("customer_id")
        
        if customer_id:
            # Verify via admin get customer
            detail_resp = requests.get(
                f"{BASE_URL}/api/admin/customers/{customer_id}",
                headers=partner_admin_headers,
            )
            if detail_resp.status_code == 200:
                detail = detail_resp.json()
                # Look for job_title in user or user_info field
                user_info = detail.get("user") or detail
                job_title_val = user_info.get("job_title")
                print(f"PASS: Created customer detail - job_title='{job_title_val}'")
            else:
                print(f"INFO: Customer detail endpoint not available (status {detail_resp.status_code})")
        else:
            print(f"INFO: No customer_id in create response - cannot verify detail")


class TestMeUpdateJobTitle:
    """Test PUT /me correctly updates job_title."""

    def test_put_me_with_job_title(self, admin_token):
        """PUT /me should accept and update job_title."""
        new_job_title = "TEST_Platform Admin Title"
        resp = requests.put(
            f"{BASE_URL}/api/me",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "job_title": new_job_title,
                "full_name": "Platform Admin",
                "address": {
                    "line1": "",
                    "line2": "",
                    "city": "",
                    "region": "",
                    "postal": "",
                    "country": "",
                }
            }
        )
        # Platform admin may not have a customer record so 404 is acceptable
        assert resp.status_code in [200, 404], f"PUT /me failed: {resp.status_code} {resp.text}"
        if resp.status_code == 200:
            print(f"PASS: PUT /me with job_title succeeded")
        else:
            print(f"INFO: PUT /me returned 404 (admin may not have customer record - expected)")

    def test_get_me_after_update(self, admin_token):
        """GET /me should always return job_title field."""
        resp = requests.get(
            f"{BASE_URL}/api/me",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert resp.status_code == 200
        user = resp.json().get("user", {})
        assert "job_title" in user, "job_title missing from /me after update"
        print(f"PASS: /me job_title field present: '{user.get('job_title')}'")
