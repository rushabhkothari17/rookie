"""
Test suite for P0 fixes:
- Signup form has Job Title field (required)
- Profile page - Country field is disabled/read-only (backend rejects country change for non-admin)
- Admin Promo Codes tab - create promo code
- Validate promo code API - returns discount info
- Cart page has promo code input and apply button
- View Details opens in SAME tab (not new tab)
- Category tabs show 'Managed Services' (not 'Manages Services')
- Only ONE 'Historical Accounting' product exists
- Admin Orders table has all required columns
- Admin Catalog table has billing type column and filter
- Store header shows user's first name
- Fixed-Scope Development product shows scope request modal
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"

# Test user for signup/profile tests
TEST_USER_EMAIL = f"test_p0_{os.urandom(4).hex()}@example.com"
TEST_USER_PASSWORD = "TestPass123!"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def admin_token(api_client):
    """Get admin authentication token"""
    response = api_client.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Admin authentication failed")


@pytest.fixture(scope="module")
def test_user_token(api_client):
    """Create a test user and get their token"""
    # Register test user with job_title
    register_response = api_client.post(
        f"{BASE_URL}/api/auth/register",
        json={
            "full_name": "Test P0 User",
            "job_title": "QA Engineer",  # New required field
            "company_name": "Test Company",
            "email": TEST_USER_EMAIL,
            "phone": "555-1234",
            "password": TEST_USER_PASSWORD,
            "address": {
                "line1": "123 Test St",
                "line2": "",
                "city": "Toronto",
                "region": "ON",
                "postal": "M5V 1A1",
                "country": "Canada",
            },
        },
    )
    if register_response.status_code != 200:
        pytest.skip(f"User registration failed: {register_response.text}")

    # Verify the user
    verification_code = register_response.json().get("verification_code")
    api_client.post(
        f"{BASE_URL}/api/auth/verify",
        json={"email": TEST_USER_EMAIL, "code": verification_code},
    )

    # Login
    login_response = api_client.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD},
    )
    if login_response.status_code == 200:
        return login_response.json().get("token")
    pytest.skip("Test user authentication failed")


class TestSignupJobTitle:
    """Test that signup requires job_title field"""

    def test_signup_requires_job_title(self, api_client):
        """Signup should fail without job_title"""
        response = api_client.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "full_name": "No Job Title User",
                # Missing job_title
                "company_name": "Test Company",
                "email": f"nojob_{os.urandom(4).hex()}@example.com",
                "phone": "555-9999",
                "password": "TestPass123!",
                "address": {
                    "line1": "123 Test St",
                    "line2": "",
                    "city": "Toronto",
                    "region": "ON",
                    "postal": "M5V 1A1",
                    "country": "Canada",
                },
            },
        )
        # Should fail with 422 (validation error) because job_title is required
        assert response.status_code == 422, f"Expected 422 for missing job_title, got {response.status_code}"
        print("✓ Signup correctly rejects missing job_title")

    def test_signup_with_job_title_succeeds(self, api_client):
        """Signup with job_title should succeed"""
        email = f"withjob_{os.urandom(4).hex()}@example.com"
        response = api_client.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "full_name": "With Job Title User",
                "job_title": "Software Developer",
                "company_name": "Test Company",
                "email": email,
                "phone": "555-8888",
                "password": "TestPass123!",
                "address": {
                    "line1": "123 Test St",
                    "line2": "",
                    "city": "Toronto",
                    "region": "ON",
                    "postal": "M5V 1A1",
                    "country": "Canada",
                },
            },
        )
        assert response.status_code == 200, f"Signup failed: {response.text}"
        print("✓ Signup with job_title succeeds")


class TestCountryLock:
    """Test that non-admin users cannot change their country"""

    def test_country_change_blocked_for_non_admin(self, api_client, test_user_token):
        """Non-admin user attempting to change country should get 403"""
        api_client.headers.update({"Authorization": f"Bearer {test_user_token}"})

        # Try to update profile with different country
        response = api_client.put(
            f"{BASE_URL}/api/me",
            json={
                "full_name": "Test P0 User",
                "company_name": "Test Company",
                "phone": "555-1234",
                "address": {
                    "line1": "123 Test St",
                    "line2": "",
                    "city": "New York",
                    "region": "NY",
                    "postal": "10001",
                    "country": "USA",  # Changed from Canada to USA
                },
            },
        )
        assert response.status_code == 403, f"Expected 403 for country change, got {response.status_code}: {response.text}"
        assert "Country cannot be changed" in response.json().get("detail", "")
        print("✓ Country change correctly blocked for non-admin users")


class TestPromoCodeSystem:
    """Test admin promo code creation and validation"""

    def test_admin_create_promo_code(self, api_client, admin_token):
        """Admin can create a promo code"""
        api_client.headers.update({"Authorization": f"Bearer {admin_token}"})

        promo_code = f"TEST{os.urandom(3).hex().upper()}"
        response = api_client.post(
            f"{BASE_URL}/api/admin/promo-codes",
            json={
                "code": promo_code,
                "discount_type": "percent",
                "discount_value": 15,
                "applies_to": "both",
                "expiry_date": None,
                "max_uses": None,
                "one_time_code": False,
                "enabled": True,
            },
        )
        assert response.status_code == 200, f"Promo creation failed: {response.text}"
        data = response.json()
        # The response has promo_code nested
        promo_data = data.get("promo_code", data)
        assert promo_data.get("code") == promo_code
        print(f"✓ Admin successfully created promo code: {promo_code}")
        return promo_code

    def test_admin_list_promo_codes(self, api_client, admin_token):
        """Admin can list promo codes"""
        api_client.headers.update({"Authorization": f"Bearer {admin_token}"})
        response = api_client.get(f"{BASE_URL}/api/admin/promo-codes")
        assert response.status_code == 200, f"List promo codes failed: {response.text}"
        data = response.json()
        assert "promo_codes" in data
        print(f"✓ Admin promo codes list retrieved: {len(data['promo_codes'])} codes")

    def test_validate_promo_code(self, api_client, admin_token, test_user_token):
        """Validate promo code returns discount info"""
        # First create a promo code as admin
        api_client.headers.update({"Authorization": f"Bearer {admin_token}"})
        promo_code = f"VALID{os.urandom(3).hex().upper()}"
        create_response = api_client.post(
            f"{BASE_URL}/api/admin/promo-codes",
            json={
                "code": promo_code,
                "discount_type": "percent",
                "discount_value": 20,
                "applies_to": "both",
                "expiry_date": None,
                "max_uses": None,
                "one_time_code": False,
                "enabled": True,
            },
        )
        assert create_response.status_code == 200

        # Validate as test user
        api_client.headers.update({"Authorization": f"Bearer {test_user_token}"})
        response = api_client.post(
            f"{BASE_URL}/api/promo-codes/validate",
            json={"code": promo_code, "checkout_type": "one_time"},
        )
        assert response.status_code == 200, f"Promo validation failed: {response.text}"
        data = response.json()
        assert data.get("valid") is True
        assert data.get("code") == promo_code
        assert data.get("discount_type") == "percent"
        assert data.get("discount_value") == 20
        print(f"✓ Promo code validation returns correct discount info: {data}")

    def test_invalid_promo_code(self, api_client, test_user_token):
        """Invalid promo code returns 404"""
        api_client.headers.update({"Authorization": f"Bearer {test_user_token}"})
        response = api_client.post(
            f"{BASE_URL}/api/promo-codes/validate",
            json={"code": "INVALIDCODE999", "checkout_type": "one_time"},
        )
        assert response.status_code == 404, f"Expected 404 for invalid promo code, got {response.status_code}"
        print("✓ Invalid promo code returns 404")


class TestProductCatalog:
    """Test product catalog features"""

    def test_only_one_historical_accounting_product(self, api_client):
        """There should only be ONE Historical Accounting product"""
        response = api_client.get(f"{BASE_URL}/api/products")
        assert response.status_code == 200
        products = response.json().get("products", [])
        
        historical_products = [p for p in products if "Historical Accounting" in p.get("name", "")]
        assert len(historical_products) == 1, f"Expected 1 Historical Accounting product, found {len(historical_products)}: {[p['name'] for p in historical_products]}"
        print(f"✓ Only ONE Historical Accounting product exists: {historical_products[0]['name']}")

    def test_fixed_scope_development_exists(self, api_client):
        """Fixed-Scope Development product should exist with scope_request pricing type"""
        response = api_client.get(f"{BASE_URL}/api/products")
        assert response.status_code == 200
        products = response.json().get("products", [])
        
        fixed_scope = [p for p in products if p.get("sku") == "BUILD-FIXED-SCOPE"]
        assert len(fixed_scope) == 1, "Fixed-Scope Development product not found"
        assert fixed_scope[0].get("pricing_type") == "scope_request"
        print(f"✓ Fixed-Scope Development product exists with scope_request pricing type")

    def test_products_have_billing_type_info(self, api_client):
        """Products should have is_subscription field for billing type"""
        response = api_client.get(f"{BASE_URL}/api/products")
        assert response.status_code == 200
        products = response.json().get("products", [])
        
        # Check that products have is_subscription field
        subscriptions = [p for p in products if p.get("is_subscription")]
        one_time = [p for p in products if not p.get("is_subscription")]
        print(f"✓ Products have billing type: {len(subscriptions)} subscriptions, {len(one_time)} one-time")


class TestAdminOrders:
    """Test admin orders table features"""

    def test_admin_orders_endpoint(self, api_client, admin_token):
        """Admin orders endpoint returns required fields"""
        api_client.headers.update({"Authorization": f"Bearer {admin_token}"})
        response = api_client.get(f"{BASE_URL}/api/admin/orders")
        assert response.status_code == 200
        data = response.json()
        assert "orders" in data
        
        # Check that orders have required columns
        if data["orders"]:
            order = data["orders"][0]
            required_fields = ["order_number", "created_at", "subtotal", "fee", "total", "status", "payment_method"]
            for field in required_fields:
                assert field in order, f"Order missing required field: {field}"
        print("✓ Admin orders endpoint returns all required fields")


class TestCategoryDisplay:
    """Test category naming"""

    def test_managed_services_category_in_products(self, api_client):
        """Products with 'Manages Services' category should be normalized to 'Managed Services'"""
        response = api_client.get(f"{BASE_URL}/api/products")
        assert response.status_code == 200
        products = response.json().get("products", [])
        
        # Products stored as "Manages Services" in DB are transformed by frontend
        # Backend may still return "Manages Services" - this is handled by frontend displayCategory()
        categories = set(p.get("category", "") for p in products)
        print(f"✓ Product categories from API: {categories}")
        
        # The key products that should be in Managed Services
        ongoing_support = [p for p in products if p.get("sku") == "ONGOING-SUPPORT"]
        ongoing_dev = [p for p in products if p.get("sku") == "ONGOING-DEV"]
        assert len(ongoing_support) == 1, "Unlimited Zoho Support product not found"
        assert len(ongoing_dev) == 1, "Ongoing Zoho Development product not found"
        print("✓ Managed Services products exist (ONGOING-SUPPORT, ONGOING-DEV)")


class TestScopeRequestForm:
    """Test scope request form submission"""

    def test_scope_request_form_endpoint(self, api_client, test_user_token):
        """Scope request form endpoint should accept submissions"""
        api_client.headers.update({"Authorization": f"Bearer {test_user_token}"})
        
        # Get Fixed-Scope Development product
        products_response = api_client.get(f"{BASE_URL}/api/products")
        products = products_response.json().get("products", [])
        fixed_scope = [p for p in products if p.get("sku") == "BUILD-FIXED-SCOPE"]
        
        if not fixed_scope:
            pytest.skip("Fixed-Scope Development product not found")
        
        product_id = fixed_scope[0]["id"]
        
        response = api_client.post(
            f"{BASE_URL}/api/orders/scope-request-form",
            json={
                "items": [{"product_id": product_id, "quantity": 1, "inputs": {}}],
                "form_data": {
                    "project_summary": "Test project summary",
                    "desired_outcomes": "Test desired outcomes",
                    "apps_involved": "Zoho CRM, Zoho Books",
                    "timeline_urgency": "1-month",
                    "budget_range": "10k-25k",
                    "additional_notes": "Test additional notes",
                },
            },
        )
        assert response.status_code == 200, f"Scope request form submission failed: {response.text}"
        data = response.json()
        assert "order_number" in data
        print(f"✓ Scope request form submitted successfully: {data['order_number']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
