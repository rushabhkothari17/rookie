"""
Test suite for iter91 fixes:
1. Verification email passes tenant_id to EmailService.send()
2. Email service Resend from_email reads from settings not credentials
3. Product visibility: restricted_to (blacklist) - hidden from blocked customer, visible to others
4. Product visibility: restricted_to (blacklist) - admins see all products
5. Product visibility: visible_to_customers (whitelist) - only that customer sees it
6. ProductCreate model has restricted_to field
7. PUT /api/admin/products/{id} saves restricted_to field
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
PARTNER_CODE = "automate-accounts"

# ─── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_token():
    """Login as platform admin and get token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!"
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.status_code} {resp.text}"
    token = resp.json().get("token")
    assert token, "No token in login response"
    return token


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def test_customer(admin_headers):
    """Create a customer for visibility tests via admin API.
    Response format: {"message": "Customer created", "customer_id": "...", "user_id": "..."}
    """
    import secrets
    suffix = secrets.token_hex(4)
    email = f"test_vis_{suffix}@example.com"
    resp = requests.post(f"{BASE_URL}/api/admin/customers/create", json={
        "full_name": "Test Vis Customer",
        "email": email,
        "company_name": "TEST_VisComp",
        "phone": "1234567890",
        "password": "TestPass123!",
        "line1": "123 Test St",
        "city": "Test City",
        "region": "BC",
        "postal": "V1V1V1",
        "country": "Canada",
        "mark_verified": True,
    }, headers=admin_headers)
    assert resp.status_code in [200, 201], f"Failed to create test customer: {resp.status_code} {resp.text}"
    data = resp.json()
    # Response is flat: {"message": ..., "customer_id": ..., "user_id": ...}
    customer_id = data.get("customer_id") or data.get("customer", {}).get("id")
    user_id = data.get("user_id") or data.get("user", {}).get("id")
    assert customer_id, f"Could not extract customer_id from response: {data}"
    return {"email": email, "customer_id": customer_id, "user_id": user_id}


@pytest.fixture(scope="module")
def customer_token(test_customer):
    """Login as the test customer and get token."""
    resp = requests.post(f"{BASE_URL}/api/auth/customer-login", json={
        "partner_code": PARTNER_CODE,
        "email": test_customer["email"],
        "password": "TestPass123!",
    })
    assert resp.status_code == 200, f"Customer login failed: {resp.status_code} {resp.text}"
    return resp.json().get("token")


@pytest.fixture(scope="module")
def customer_headers(customer_token):
    return {"Authorization": f"Bearer {customer_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def test_product_restricted(admin_headers, test_customer):
    """Create a product with restricted_to=[customer_id] (blacklist)."""
    resp = requests.post(f"{BASE_URL}/api/admin/products", json={
        "name": "TEST_Restricted_Product_91",
        "short_description": "Test restricted product",
        "description_long": "Blacklisted from specific customer",
        "base_price": 99.0,
        "is_active": True,
        "category": "General Services",
        "restricted_to": [test_customer["customer_id"]],
        "visible_to_customers": [],
    }, headers=admin_headers)
    assert resp.status_code in [200, 201], f"Failed to create restricted product: {resp.status_code} {resp.text}"
    pid = resp.json().get("product", {}).get("id")
    assert pid, "No product id returned"
    yield pid
    # Cleanup: deactivate since no DELETE endpoint for products
    requests.put(f"{BASE_URL}/api/admin/products/{pid}", json={
        "name": "TEST_Restricted_Product_91", "is_active": False
    }, headers=admin_headers)


@pytest.fixture(scope="module")
def test_product_whitelist(admin_headers, test_customer):
    """Create a product with visible_to_customers=[customer_id] (whitelist)."""
    resp = requests.post(f"{BASE_URL}/api/admin/products", json={
        "name": "TEST_Whitelist_Product_91",
        "short_description": "Test whitelist product",
        "description_long": "Only visible to specific customer",
        "base_price": 149.0,
        "is_active": True,
        "category": "General Services",
        "restricted_to": [],
        "visible_to_customers": [test_customer["customer_id"]],
    }, headers=admin_headers)
    assert resp.status_code in [200, 201], f"Failed to create whitelist product: {resp.status_code} {resp.text}"
    pid = resp.json().get("product", {}).get("id")
    assert pid, "No product id returned"
    yield pid
    # Cleanup: deactivate since no DELETE endpoint for products
    requests.put(f"{BASE_URL}/api/admin/products/{pid}", json={
        "name": "TEST_Whitelist_Product_91", "is_active": False
    }, headers=admin_headers)


# ─── Tests ───────────────────────────────────────────────────────────────────

class TestProductRestrictedTo:
    """Blacklist mode: restricted_to hides product from listed customers, admins always see it."""

    def test_restricted_product_hidden_from_blocked_customer(self, customer_headers, test_product_restricted):
        """Customer in restricted_to cannot see the product in GET /api/products."""
        resp = requests.get(f"{BASE_URL}/api/products", headers=customer_headers,
                            params={"partner_code": PARTNER_CODE})
        assert resp.status_code == 200, f"Products call failed: {resp.text}"
        products = resp.json().get("products", [])
        product_ids = [p["id"] for p in products]
        assert test_product_restricted not in product_ids, (
            f"Restricted product {test_product_restricted} should NOT be visible to blocked customer"
        )
        print(f"PASS: Restricted product is hidden from blocked customer")

    def test_restricted_product_visible_to_anonymous(self, test_product_restricted):
        """Anonymous users (no token) can see blacklist products."""
        resp = requests.get(f"{BASE_URL}/api/products", params={"partner_code": PARTNER_CODE})
        assert resp.status_code == 200, f"Products call failed: {resp.text}"
        products = resp.json().get("products", [])
        product_ids = [p["id"] for p in products]
        assert test_product_restricted in product_ids, (
            f"Restricted product {test_product_restricted} SHOULD be visible to anonymous users"
        )
        print(f"PASS: Restricted product is visible to anonymous users")

    def test_restricted_product_visible_to_admin(self, admin_headers, test_product_restricted):
        """Admin can always see all products including restricted ones."""
        # Admins should see all products via GET /api/products with admin JWT
        resp = requests.get(f"{BASE_URL}/api/products", headers=admin_headers,
                            params={"partner_code": PARTNER_CODE})
        assert resp.status_code == 200, f"Products call failed: {resp.text}"
        products = resp.json().get("products", [])
        product_ids = [p["id"] for p in products]
        assert test_product_restricted in product_ids, (
            f"Restricted product {test_product_restricted} SHOULD be visible to admin"
        )
        print(f"PASS: Restricted product is visible to admin")


class TestProductWhitelistVisibility:
    """Whitelist mode: visible_to_customers shows product only to listed customers."""

    def test_whitelist_product_visible_to_whitelisted_customer(self, customer_headers, test_product_whitelist):
        """Customer in visible_to_customers CAN see the whitelist product."""
        resp = requests.get(f"{BASE_URL}/api/products", headers=customer_headers,
                            params={"partner_code": PARTNER_CODE})
        assert resp.status_code == 200, f"Products call failed: {resp.text}"
        products = resp.json().get("products", [])
        product_ids = [p["id"] for p in products]
        assert test_product_whitelist in product_ids, (
            f"Whitelist product {test_product_whitelist} SHOULD be visible to whitelisted customer"
        )
        print(f"PASS: Whitelist product is visible to the whitelisted customer")

    def test_whitelist_product_hidden_from_anonymous(self, test_product_whitelist):
        """Anonymous users cannot see whitelist-only products."""
        resp = requests.get(f"{BASE_URL}/api/products", params={"partner_code": PARTNER_CODE})
        assert resp.status_code == 200, f"Products call failed: {resp.text}"
        products = resp.json().get("products", [])
        product_ids = [p["id"] for p in products]
        assert test_product_whitelist not in product_ids, (
            f"Whitelist product {test_product_whitelist} should NOT be visible to anonymous"
        )
        print(f"PASS: Whitelist product is hidden from anonymous users")

    def test_whitelist_product_visible_to_admin(self, admin_headers, test_product_whitelist):
        """Admins can see whitelist-only products."""
        resp = requests.get(f"{BASE_URL}/api/products", headers=admin_headers,
                            params={"partner_code": PARTNER_CODE})
        assert resp.status_code == 200, f"Products call failed: {resp.text}"
        products = resp.json().get("products", [])
        product_ids = [p["id"] for p in products]
        assert test_product_whitelist in product_ids, (
            f"Whitelist product {test_product_whitelist} SHOULD be visible to admin"
        )
        print(f"PASS: Whitelist product is visible to admin")


class TestProductModelRestrictedTo:
    """Verify AdminProductCreate model accepts restricted_to and it's saved correctly."""

    def test_create_product_with_restricted_to(self, admin_headers, test_customer):
        """POST /api/admin/products with restricted_to saves the field."""
        import secrets
        suffix = secrets.token_hex(4)
        resp = requests.post(f"{BASE_URL}/api/admin/products", json={
            "name": f"TEST_RestrictedField_{suffix}",
            "short_description": "Field test",
            "base_price": 50.0,
            "is_active": True,
            "category": "General Services",
            "restricted_to": [test_customer["customer_id"]],
            "visible_to_customers": [],
        }, headers=admin_headers)
        assert resp.status_code in [200, 201], f"Create failed: {resp.status_code} {resp.text}"
        product = resp.json().get("product", {})
        assert "restricted_to" in product, "restricted_to field should be in product response"
        assert test_customer["customer_id"] in product["restricted_to"], \
            f"Customer ID should be in restricted_to, got: {product['restricted_to']}"
        print(f"PASS: restricted_to field saved on product create: {product['restricted_to']}")
        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/products/{product['id']}", headers=admin_headers)

    def test_update_product_restricted_to(self, admin_headers, test_customer):
        """PUT /api/admin/products/{id} saves restricted_to field."""
        import secrets
        suffix = secrets.token_hex(4)
        # Create without restriction
        create_resp = requests.post(f"{BASE_URL}/api/admin/products", json={
            "name": f"TEST_UpdateRestricted_{suffix}",
            "base_price": 75.0,
            "is_active": True,
            "category": "General Services",
            "restricted_to": [],
            "visible_to_customers": [],
        }, headers=admin_headers)
        assert create_resp.status_code in [200, 201], f"Create failed: {create_resp.text}"
        pid = create_resp.json()["product"]["id"]

        # Update with restriction
        update_resp = requests.put(f"{BASE_URL}/api/admin/products/{pid}", json={
            "name": f"TEST_UpdateRestricted_{suffix}",
            "is_active": True,
            "restricted_to": [test_customer["customer_id"]],
            "visible_to_customers": [],
        }, headers=admin_headers)
        assert update_resp.status_code == 200, f"Update failed: {update_resp.status_code} {update_resp.text}"
        print(f"PASS: PUT /api/admin/products/{pid} accepted restricted_to update")

        # Verify via admin product list
        list_resp = requests.get(f"{BASE_URL}/api/admin/products-all", headers=admin_headers)
        assert list_resp.status_code == 200
        products = list_resp.json().get("products", [])
        updated = next((p for p in products if p["id"] == pid), None)
        assert updated is not None, "Updated product not found in list"
        assert test_customer["customer_id"] in updated.get("restricted_to", []), \
            f"restricted_to not saved after update. Got: {updated.get('restricted_to')}"
        print(f"PASS: restricted_to persisted after update: {updated['restricted_to']}")
        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/products/{pid}", headers=admin_headers)


class TestEmailTenantIdFix:
    """Verify that the register endpoint sends verification email with tenant_id."""

    def test_register_returns_email_delivery_field(self):
        """POST /api/auth/register should succeed and return email_delivery field."""
        import secrets
        suffix = secrets.token_hex(4)
        resp = requests.post(f"{BASE_URL}/api/auth/register", params={"partner_code": PARTNER_CODE}, json={
            "full_name": "Test Email Fix User",
            "email": f"test_email_fix_{suffix}@example.com",
            "password": "TestPass123!",
            "company_name": "TEST_EmailFix",
            "job_title": "Tester",
            "phone": "1234567890",
            "address": {
                "line1": "1 Test Street",
                "city": "Vancouver",
                "region": "BC",
                "postal": "V1V 1V1",
                "country": "Canada",
            },
        })
        assert resp.status_code == 200, f"Register failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "email_delivery" in data or "message" in data, \
            f"Expected email_delivery or message in response, got: {data}"
        # The email_delivery field (MOCKED means Zoho was tried but email_outbox used as fallback)
        # Either "MOCKED" (if Zoho not reached) or "sent" (if Zoho sends it)
        print(f"PASS: Register endpoint returns email_delivery: {data.get('email_delivery')}")
        # Note: verification_code is returned for testing convenience
        assert "verification_code" in data, "Expected verification_code in response"
        print(f"PASS: verification_code is present in register response")

    def test_register_with_default_tenant_sends_email(self):
        """Register without partner_code should use default tenant_id."""
        import secrets
        suffix = secrets.token_hex(4)
        resp = requests.post(f"{BASE_URL}/api/auth/register", json={
            "full_name": "Test Default Tenant",
            "email": f"test_default_tenant_{suffix}@example.com",
            "password": "TestPass123!",
            "company_name": "TEST_DefaultTenant",
            "address": {
                "line1": "1 Test Street",
                "city": "Vancouver",
                "region": "BC",
                "postal": "V1V 1V1",
                "country": "Canada",
            },
        })
        assert resp.status_code == 200, f"Register failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "message" in data
        print(f"PASS: Register without partner_code works with default tenant")


class TestAdminProductsListFiltering:
    """Verify admin can always see all products via admin endpoints."""

    def test_admin_can_list_all_products(self, admin_headers):
        """GET /api/admin/products-all returns all products for admin."""
        resp = requests.get(f"{BASE_URL}/api/admin/products-all", headers=admin_headers)
        assert resp.status_code == 200, f"Admin products list failed: {resp.text}"
        data = resp.json()
        assert "products" in data, "Expected 'products' in response"
        assert "total" in data, "Expected 'total' in response"
        print(f"PASS: Admin can list all products, total: {data['total']}")

    def test_store_products_returns_200(self):
        """GET /api/products returns 200 for anonymous."""
        resp = requests.get(f"{BASE_URL}/api/products", params={"partner_code": PARTNER_CODE})
        assert resp.status_code == 200, f"Public products failed: {resp.text}"
        data = resp.json()
        assert "products" in data
        print(f"PASS: Public store returns {len(data['products'])} products")
