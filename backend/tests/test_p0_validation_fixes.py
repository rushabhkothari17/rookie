"""
Test suite for 4 P0 validation and checkout fixes:
1. Block subscription creation for deleted customers (backend: 400 error)
2. Block negative product prices (backend: ge=0 validator - 422)
3. Scope Final Won resources must have price > 0 (backend: 400)
4. Price > 0 validation for Scope Final - Won resources on create/update
"""

import pytest
import requests
import os
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"

# --- Fixtures ---

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
    pytest.skip(f"Admin authentication failed: {response.text}")


@pytest.fixture(scope="module")
def admin_client(api_client, admin_token):
    """Requests session with admin token"""
    api_client.headers.update({"Authorization": f"Bearer {admin_token}"})
    return api_client


# --- Helper to get tenant_id ---

def get_tenant_id_for_admin(admin_client):
    """Get the first available product to determine tenant info"""
    res = admin_client.get(f"{BASE_URL}/api/admin/products-all?per_page=1")
    if res.status_code == 200:
        products = res.data.get("products", []) if hasattr(res, 'data') else res.json().get("products", [])
        if products:
            return products[0].get("tenant_id")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Fix 1: Block subscription creation for deleted customers
# ─────────────────────────────────────────────────────────────────────────────

class TestSubscriptionDeletedCustomer:
    """Test that creating a subscription for a deleted customer returns 400"""

    @pytest.fixture(scope="class")
    def test_customer_email(self, admin_client):
        """Create a test customer via admin API"""
        import os as _os
        email = f"TEST_deleted_cust_{_os.urandom(4).hex()}@example.com"
        create_res = admin_client.post(
            f"{BASE_URL}/api/admin/customers/create",
            json={
                "full_name": "Test Deleted Customer",
                "email": email,
                "password": "TestPass123!",
                "company_name": "Test Co",
                "mark_verified": True,
            },
        )
        if create_res.status_code not in (200, 201):
            pytest.skip(f"Could not create test customer: {create_res.text}")
        return email

    @pytest.fixture(scope="class")
    def deleted_customer_email(self, admin_client, test_customer_email):
        """Mark the test customer as deleted via direct MongoDB update"""
        # Get customer record via admin API
        custs_res = admin_client.get(
            f"{BASE_URL}/api/admin/customers?per_page=500"
        )
        assert custs_res.status_code == 200
        data = custs_res.json()
        custs = data.get("customers", [])
        usrs = data.get("users", [])
        
        # Build user map by user_id → email
        user_map = {u["id"]: u for u in usrs}
        
        # Find the customer for our test email
        target_cust = None
        for c in custs:
            u = user_map.get(c.get("user_id", ""))
            if u and u.get("email", "").lower() == test_customer_email.lower():
                target_cust = c
                break
        
        if not target_cust:
            pytest.skip(f"Could not find customer for {test_customer_email}")
        
        customer_id = target_cust["id"]
        
        # Directly update MongoDB to set deleted_at
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "test_database")
        
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        
        async def set_deleted():
            await db.customers.update_one(
                {"id": customer_id},
                {"$set": {"deleted_at": datetime.now(timezone.utc).isoformat()}}
            )
        
        asyncio.get_event_loop().run_until_complete(set_deleted())
        client.close()
        
        return test_customer_email

    def test_subscription_for_deleted_customer_returns_400(self, admin_client, deleted_customer_email):
        """POST /api/admin/subscriptions/manual with deleted customer should return 400"""
        # Get any active product
        prods_res = admin_client.get(f"{BASE_URL}/api/admin/products-all?per_page=5")
        if prods_res.status_code != 200 or not prods_res.json().get("products"):
            pytest.skip("No products available for test")
        
        product = prods_res.json()["products"][0]
        
        from datetime import date, timedelta
        renewal = (date.today() + timedelta(days=30)).isoformat()
        
        response = admin_client.post(
            f"{BASE_URL}/api/admin/subscriptions/manual",
            json={
                "customer_email": deleted_customer_email,
                "product_id": product["id"],
                "amount": 100.0,
                "currency": "USD",
                "renewal_date": renewal,
                "status": "active",
                "term_months": 1,
            },
        )
        assert response.status_code == 400, (
            f"Expected 400 for deleted customer, got {response.status_code}: {response.text}"
        )
        detail = response.json().get("detail", "")
        assert "deleted" in detail.lower(), (
            f"Expected 'deleted' in error message, got: {detail}"
        )
        print(f"✓ Subscription creation blocked for deleted customer: {detail}")


# ─────────────────────────────────────────────────────────────────────────────
# Fix 2: Block negative product prices (ge=0 validator)
# ─────────────────────────────────────────────────────────────────────────────

class TestProductNegativePrice:
    """Test that products with negative base_price are rejected"""

    def _get_first_category(self, admin_client):
        """Get any available category name"""
        res = admin_client.get(f"{BASE_URL}/api/product-categories")
        if res.status_code == 200:
            cats = res.json().get("categories", [])
            if cats:
                return cats[0]["name"]
        # Fallback
        return "Managed Services"

    def test_negative_base_price_returns_422(self, admin_client):
        """POST /api/admin/products with base_price=-10 should return 422"""
        category = self._get_first_category(admin_client)
        response = admin_client.post(
            f"{BASE_URL}/api/admin/products",
            json={
                "name": "TEST_Negative Price Product",
                "category": category,
                "base_price": -10,
                "pricing_type": "internal",
                "is_subscription": False,
                "is_active": True,
                "currency": "USD",
            },
        )
        assert response.status_code == 422, (
            f"Expected 422 for negative base_price, got {response.status_code}: {response.text}"
        )
        print(f"✓ Negative base_price correctly rejected with 422")

    def test_zero_base_price_succeeds(self, admin_client):
        """POST /api/admin/products with base_price=0 should succeed (free product allowed)"""
        import os as _os
        category = self._get_first_category(admin_client)
        product_name = f"TEST_Free Product {_os.urandom(3).hex()}"
        response = admin_client.post(
            f"{BASE_URL}/api/admin/products",
            json={
                "name": product_name,
                "category": category,
                "base_price": 0,
                "pricing_type": "internal",
                "is_subscription": False,
                "is_active": True,
                "currency": "USD",
            },
        )
        assert response.status_code in (200, 201), (
            f"Expected 200/201 for base_price=0, got {response.status_code}: {response.text}"
        )
        data = response.json()
        product = data.get("product", data)
        assert product.get("base_price") == 0, f"Expected base_price=0, got {product.get('base_price')}"
        print(f"✓ Product with base_price=0 created successfully: {product_name}")
        
        # Cleanup
        product_id = product.get("id")
        if product_id:
            admin_client.delete(f"{BASE_URL}/api/admin/products/{product_id}")


# ─────────────────────────────────────────────────────────────────────────────
# Fix 3 & 4: Scope Final Won resources must have price > 0
# ─────────────────────────────────────────────────────────────────────────────

class TestScopeFinalWonPrice:
    """Test price > 0 validation for Scope - Final Won resources"""

    def _create_resource_with_price(self, admin_client, price, category="Scope - Final Won"):
        """Helper to create a resource with given price"""
        import os as _os
        title = f"TEST_Scope Final Resource {_os.urandom(3).hex()}"
        return admin_client.post(
            f"{BASE_URL}/api/resources",
            json={
                "title": title,
                "slug": f"test-scope-{_os.urandom(3).hex()}",
                "category": category,
                "price": price,
                "currency": "USD",
                "content": "<p>Test scope document content</p>",
                "visibility": "all",
                "restricted_to": [],
            },
        )

    def test_scope_final_won_price_zero_returns_400(self, admin_client):
        """POST /api/resources with Scope - Final Won and price=0 should return 400"""
        response = self._create_resource_with_price(admin_client, price=0)
        assert response.status_code == 400, (
            f"Expected 400 for price=0 on Scope - Final Won, got {response.status_code}: {response.text}"
        )
        detail = response.json().get("detail", "")
        assert "price" in detail.lower() or "0" in detail, (
            f"Expected price-related error, got: {detail}"
        )
        print(f"✓ Scope - Final Won with price=0 correctly rejected: {detail}")

    def test_scope_final_won_negative_price_returns_400(self, admin_client):
        """POST /api/resources with Scope - Final Won and price=-5 should return 400"""
        response = self._create_resource_with_price(admin_client, price=-5)
        assert response.status_code == 400, (
            f"Expected 400 for price=-5 on Scope - Final Won, got {response.status_code}: {response.text}"
        )
        print(f"✓ Scope - Final Won with price=-5 correctly rejected")

    def test_scope_final_won_valid_price_succeeds(self, admin_client):
        """POST /api/resources with Scope - Final Won and price=100 should succeed"""
        import os as _os
        title = f"TEST_Scope Final Won Valid {_os.urandom(3).hex()}"
        slug = f"test-scope-valid-{_os.urandom(3).hex()}"
        response = admin_client.post(
            f"{BASE_URL}/api/resources",
            json={
                "title": title,
                "slug": slug,
                "category": "Scope - Final Won",
                "price": 100.0,
                "currency": "USD",
                "content": "<p>Valid scope final won document</p>",
                "visibility": "all",
                "restricted_to": [],
            },
        )
        assert response.status_code in (200, 201), (
            f"Expected 200/201 for price=100 on Scope - Final Won, got {response.status_code}: {response.text}"
        )
        data = response.json()
        resource = data.get("resource", data)
        assert resource.get("price") == 100.0, f"Expected price=100, got {resource.get('price')}"
        print(f"✓ Scope - Final Won with price=100 created successfully: {title}")
        
        # Cleanup
        resource_id = resource.get("id")
        if resource_id:
            admin_client.delete(f"{BASE_URL}/api/resources/{resource_id}")

    def test_scope_final_won_update_price_zero_returns_400(self, admin_client):
        """PUT /api/resources/{id} with Scope - Final Won and price=0 should return 400"""
        import os as _os
        # First create a valid resource
        title = f"TEST_Scope Final Update {_os.urandom(3).hex()}"
        create_res = admin_client.post(
            f"{BASE_URL}/api/resources",
            json={
                "title": title,
                "slug": f"test-scope-upd-{_os.urandom(3).hex()}",
                "category": "Scope - Final Won",
                "price": 200.0,
                "currency": "USD",
                "content": "<p>Test for update validation</p>",
                "visibility": "all",
                "restricted_to": [],
            },
        )
        if create_res.status_code not in (200, 201):
            pytest.skip(f"Could not create resource for update test: {create_res.text}")
        
        resource = create_res.json().get("resource", create_res.json())
        resource_id = resource.get("id")
        
        # Now try updating with price=0
        update_res = admin_client.put(
            f"{BASE_URL}/api/resources/{resource_id}",
            json={
                "title": resource.get("title"),
                "category": "Scope - Final Won",
                "price": 0,
                "currency": "USD",
                "content": "<p>Updated content</p>",
                "visibility": "all",
                "restricted_to": [],
            },
        )
        assert update_res.status_code == 400, (
            f"Expected 400 for price=0 on Scope - Final Won update, got {update_res.status_code}: {update_res.text}"
        )
        print(f"✓ Scope - Final Won update with price=0 correctly rejected")
        
        # Cleanup
        if resource_id:
            admin_client.delete(f"{BASE_URL}/api/resources/{resource_id}")

    def test_scope_final_won_update_negative_price_returns_400(self, admin_client):
        """PUT /api/resources/{id} with Scope - Final Won and price=-5 should return 400"""
        import os as _os
        # First create a valid resource
        title = f"TEST_Scope Final Update Neg {_os.urandom(3).hex()}"
        create_res = admin_client.post(
            f"{BASE_URL}/api/resources",
            json={
                "title": title,
                "slug": f"test-scope-neg-{_os.urandom(3).hex()}",
                "category": "Scope - Final Won",
                "price": 150.0,
                "currency": "USD",
                "content": "<p>Test for update validation</p>",
                "visibility": "all",
                "restricted_to": [],
            },
        )
        if create_res.status_code not in (200, 201):
            pytest.skip(f"Could not create resource for update test: {create_res.text}")
        
        resource = create_res.json().get("resource", create_res.json())
        resource_id = resource.get("id")
        
        # Now try updating with price=-5
        update_res = admin_client.put(
            f"{BASE_URL}/api/resources/{resource_id}",
            json={
                "title": resource.get("title"),
                "category": "Scope - Final Won",
                "price": -5,
                "currency": "USD",
                "content": "<p>Updated content</p>",
                "visibility": "all",
                "restricted_to": [],
            },
        )
        assert update_res.status_code == 400, (
            f"Expected 400 for price=-5 on Scope - Final Won update, got {update_res.status_code}: {update_res.text}"
        )
        print(f"✓ Scope - Final Won update with price=-5 correctly rejected")
        
        # Cleanup
        if resource_id:
            admin_client.delete(f"{BASE_URL}/api/resources/{resource_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
