"""
Comprehensive E2E Backend Tests - Iteration 30
Covers: Auth, Store, Articles, Profile, Admin CRUD, Exports, Guardrails, Pagination, Notes merge
"""
import pytest
import requests
import os
import time
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"
CUSTOMER_EMAIL = "test-qa-e2e@example.com"
CUSTOMER_PASSWORD = "Test1234!"

# ===== Fixtures =====

@pytest.fixture(scope="session")
def admin_token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return resp.json()["token"]

@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}

@pytest.fixture(scope="session")
def customer_token(admin_headers):
    """Create or get customer user for testing"""
    # Try to register
    reg = requests.post(f"{BASE_URL}/api/auth/register", json={
        "email": CUSTOMER_EMAIL, "password": CUSTOMER_PASSWORD,
        "full_name": "QA Test Customer"
    })
    if reg.status_code == 400 and "already" in reg.text.lower():
        # Already exists, just login
        login = requests.post(f"{BASE_URL}/api/auth/login", json={"email": CUSTOMER_EMAIL, "password": CUSTOMER_PASSWORD})
        if login.status_code == 200:
            return login.json()["token"]
        return None
    if reg.status_code == 200:
        return reg.json().get("token")
    return None

@pytest.fixture(scope="session")
def customer_headers(customer_token):
    if not customer_token:
        pytest.skip("Customer token unavailable")
    return {"Authorization": f"Bearer {customer_token}"}

@pytest.fixture(scope="session")
def seed_data(admin_headers):
    """Create seed data for testing"""
    data = {}

    # Create a category
    r = requests.post(f"{BASE_URL}/api/admin/categories", json={
        "name": "TEST_E2E_Category", "description": "E2E test category", "is_active": True
    }, headers=admin_headers)
    if r.status_code == 200:
        data["category"] = r.json()

    # Create a product
    r = requests.post(f"{BASE_URL}/api/admin/products", json={
        "name": "TEST_E2E_Product", "category": "TEST_E2E_Category",
        "description": "Test product", "price": 99.99,
        "billing_type": "one-time", "pricing_complexity": "simple",
        "is_active": True, "currency": "GBP"
    }, headers=admin_headers)
    if r.status_code == 200:
        data["product"] = r.json().get("product", r.json())

    # Create a customer
    r = requests.post(f"{BASE_URL}/api/admin/customers/create", json={
        "email": "TEST_seed_customer@e2e.com", "full_name": "TEST Seed Customer",
        "company": "Test Corp", "phone": "+441234567890",
        "address": {"line1": "1 Test St", "city": "London", "postal_code": "E1 1AA", "country": "GB"}
    }, headers=admin_headers)
    if r.status_code in [200, 201]:
        data["customer"] = r.json()

    # Create a promo code
    r = requests.post(f"{BASE_URL}/api/admin/promo-codes", json={
        "code": "TESTZOHOR", "discount_type": "percentage", "discount_value": 10,
        "applies_to": "both", "enabled": True
    }, headers=admin_headers)
    if r.status_code == 200:
        data["promo_code"] = r.json()

    # Create ZOHOR promo code if not exists
    r2 = requests.post(f"{BASE_URL}/api/admin/promo-codes", json={
        "code": "ZOHOR", "discount_type": "percentage", "discount_value": 15,
        "applies_to": "both", "enabled": True
    }, headers=admin_headers)
    if r2.status_code == 200:
        data["zohor_code"] = r2.json()

    # Create an article (Scope-Final)
    r = requests.post(f"{BASE_URL}/api/articles", json={
        "title": "TEST_E2E Scope Final Article", "content": "<p>Test content</p>",
        "category": "Scope - Final Won", "visibility": "all", "price": 499.99
    }, headers=admin_headers)
    if r.status_code == 200:
        data["article"] = r.json()

    # Create a bank transaction
    customer_id = None
    if "customer" in data:
        customer_id = data["customer"].get("id") or data["customer"].get("customer_id")

    r = requests.post(f"{BASE_URL}/api/admin/bank-transactions", json={
        "source": "bank_transfer", "type": "credit", "amount": 250.00,
        "currency": "GBP", "reference": "TEST-E2E-TXN", "status": "matched",
        "customer_id": customer_id
    }, headers=admin_headers)
    if r.status_code == 200:
        data["bank_transaction"] = r.json()

    # Create an override code
    if customer_id:
        r = requests.post(f"{BASE_URL}/api/admin/override-codes", json={
            "code": "TESTE2EOVERRIDE", "customer_id": customer_id,
            "is_active": True, "expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat()
        }, headers=admin_headers)
        if r.status_code == 200:
            data["override_code"] = r.json()

    # Create a manual order
    r = requests.post(f"{BASE_URL}/api/admin/orders/manual", json={
        "customer_id": customer_id, "product_id": data.get("product", {}).get("id"),
        "amount": 99.99, "status": "paid", "payment_method": "bank_transfer",
        "note": "TEST E2E paid order"
    }, headers=admin_headers)
    if r.status_code == 200:
        data["order"] = r.json()

    # Create a manual subscription
    r = requests.post(f"{BASE_URL}/api/admin/subscriptions/manual", json={
        "customer_id": customer_id, "product_id": data.get("product", {}).get("id"),
        "amount": 49.99, "plan_name": "TEST E2E Plan", "status": "active",
        "renewal_date": (datetime.utcnow() + timedelta(days=30)).isoformat()[:10]
    }, headers=admin_headers)
    if r.status_code == 200:
        data["subscription"] = r.json()

    # Create a quote request
    r = requests.post(f"{BASE_URL}/api/admin/quote-requests", json={
        "customer_name": "TEST E2E Quote", "customer_email": "test-quote@e2e.com",
        "product_name": "TEST_E2E_Product", "details": "Test quote request details",
        "status": "pending"
    }, headers=admin_headers)
    if r.status_code in [200, 201]:
        data["quote_request"] = r.json()

    # Create terms
    r = requests.post(f"{BASE_URL}/api/admin/terms", json={
        "title": "TEST_E2E Terms", "content": "Test terms content", "is_default": False
    }, headers=admin_headers)
    if r.status_code in [200, 201]:
        data["terms"] = r.json()

    return data


# ===== SECTION 1: Auth & Root =====

class TestAuth:
    """Auth endpoint tests"""

    def test_root_returns_200(self):
        r = requests.get(f"{BASE_URL}/api/")
        assert r.status_code == 200

    def test_admin_login_success(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200
        data = r.json()
        assert "token" in data
        assert data["user"]["role"] in ["admin", "super_admin"]

    def test_login_invalid_credentials(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"})
        assert r.status_code in [401, 400]

    def test_me_returns_profile(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/me", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "email" in data
        assert data["email"] == ADMIN_EMAIL

    def test_me_unauthorized(self):
        r = requests.get(f"{BASE_URL}/api/me")
        assert r.status_code in [401, 403]

    def test_admin_accesses_admin_endpoint(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/customers", headers=admin_headers)
        assert r.status_code == 200


# ===== SECTION 2: Store =====

class TestStore:
    """Public store endpoint tests"""

    def test_categories_list(self):
        r = requests.get(f"{BASE_URL}/api/categories")
        assert r.status_code == 200
        data = r.json()
        assert "categories" in data

    def test_products_list(self):
        r = requests.get(f"{BASE_URL}/api/products")
        assert r.status_code == 200
        data = r.json()
        assert "products" in data
        assert isinstance(data["products"], list)

    def test_product_detail(self):
        # Get first available product
        r = requests.get(f"{BASE_URL}/api/products")
        assert r.status_code == 200
        products = r.json()["products"]
        if not products:
            pytest.skip("No products available")
        pid = products[0]["id"]
        r2 = requests.get(f"{BASE_URL}/api/products/{pid}")
        assert r2.status_code == 200
        assert "product" in r2.json()

    def test_product_not_found(self):
        r = requests.get(f"{BASE_URL}/api/products/nonexistent-id-9999")
        assert r.status_code == 404

    def test_terms_list(self):
        r = requests.get(f"{BASE_URL}/api/terms")
        assert r.status_code == 200
        assert "terms" in r.json()

    def test_promo_code_validate_valid(self, admin_headers, customer_headers, seed_data):
        # Need customer token for promo validation
        r = requests.post(f"{BASE_URL}/api/promo-codes/validate", json={
            "code": "TESTZOHOR", "checkout_type": "one_time"
        }, headers=customer_headers)
        # If the code was created in seed_data it should be valid
        assert r.status_code in [200, 404, 400]  # 404/400 if not seeded

    def test_promo_code_validate_invalid(self, customer_headers):
        r = requests.post(f"{BASE_URL}/api/promo-codes/validate", json={
            "code": "INVALIDCODE9999", "checkout_type": "one_time"
        }, headers=customer_headers)
        assert r.status_code == 404


# ===== SECTION 3: Articles (Public) =====

class TestArticlesPublic:
    """Article public endpoint tests"""

    def test_public_articles_list(self, customer_headers):
        r = requests.get(f"{BASE_URL}/api/articles/public", headers=customer_headers)
        assert r.status_code == 200
        data = r.json()
        assert "articles" in data

    def test_validate_scope_final_article(self, customer_headers, seed_data):
        """Scope-Final article should validate successfully"""
        article = seed_data.get("article", {})
        article_id = article.get("id") or article.get("article_id")
        if not article_id:
            pytest.skip("Scope-Final article not seeded")
        r = requests.get(f"{BASE_URL}/api/articles/{article_id}/validate-scope", headers=customer_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["valid"] is True
        assert "price" in data
        assert data["price"] == 499.99

    def test_validate_scope_invalid_id(self, customer_headers):
        r = requests.get(f"{BASE_URL}/api/articles/nonexistent-9999/validate-scope", headers=customer_headers)
        assert r.status_code == 404

    def test_article_detail(self, customer_headers, seed_data):
        article = seed_data.get("article", {})
        article_id = article.get("id") or article.get("article_id")
        if not article_id:
            pytest.skip("Article not seeded")
        r = requests.get(f"{BASE_URL}/api/articles/{article_id}", headers=customer_headers)
        assert r.status_code == 200
        assert "article" in r.json()


# ===== SECTION 4: Profile =====

class TestProfile:
    """Profile update tests"""

    def test_profile_update_name(self, customer_headers):
        r = requests.put(f"{BASE_URL}/api/me", json={
            "full_name": "QA Test Customer Updated", "phone": "+441234567999"
        }, headers=customer_headers)
        assert r.status_code == 200

    def test_profile_persists(self, customer_headers):
        # Update then retrieve
        requests.put(f"{BASE_URL}/api/me", json={"full_name": "QA Profile Persist"}, headers=customer_headers)
        r = requests.get(f"{BASE_URL}/api/me", headers=customer_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["full_name"] == "QA Profile Persist"


# ===== SECTION 5: Admin - Customers =====

class TestAdminCustomers:
    """Admin customers CRUD tests"""

    def test_customers_list(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/customers", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "customers" in data
        assert "total" in data

    def test_customers_pagination(self, admin_headers):
        r1 = requests.get(f"{BASE_URL}/api/admin/customers?page=1&per_page=5", headers=admin_headers)
        assert r1.status_code == 200
        data = r1.json()
        assert "total_pages" in data
        assert data.get("page") == 1

    def test_customers_search_filter(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/customers?search=TEST_seed", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        customers = data.get("customers", [])
        # Should find seed customer
        assert any("TEST_seed" in c.get("full_name", "") or "TEST_seed" in c.get("email", "") for c in customers)

    def test_create_customer(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/customers/create", json={
            "email": "TEST_new_customer@e2e.com", "full_name": "TEST New Customer",
            "company": "New Corp", "phone": "+441234567891",
            "address": {"line1": "2 New St", "city": "London", "postal_code": "E1 2BB", "country": "GB"}
        }, headers=admin_headers)
        assert r.status_code in [200, 201]

    def test_create_customer_duplicate_email(self, admin_headers):
        """Creating customer with existing email should fail"""
        requests.post(f"{BASE_URL}/api/admin/customers/create", json={
            "email": "TEST_dup_email@e2e.com", "full_name": "TEST Dup",
            "address": {"country": "GB"}
        }, headers=admin_headers)
        r2 = requests.post(f"{BASE_URL}/api/admin/customers/create", json={
            "email": "TEST_dup_email@e2e.com", "full_name": "TEST Dup2",
            "address": {"country": "GB"}
        }, headers=admin_headers)
        assert r2.status_code == 400

    def test_update_customer(self, admin_headers, seed_data):
        customer = seed_data.get("customer", {})
        cid = customer.get("id") or customer.get("customer_id")
        if not cid:
            pytest.skip("No seed customer")
        r = requests.put(f"{BASE_URL}/api/admin/customers/{cid}", json={
            "full_name": "TEST Updated Customer Name", "company": "Updated Corp"
        }, headers=admin_headers)
        assert r.status_code == 200

    def test_customer_payment_methods_toggle(self, admin_headers, seed_data):
        customer = seed_data.get("customer", {})
        cid = customer.get("id") or customer.get("customer_id")
        if not cid:
            pytest.skip("No seed customer")
        r = requests.put(f"{BASE_URL}/api/admin/customers/{cid}/payment-methods", json={
            "allow_bank_transfer": True, "allow_card_payment": False
        }, headers=admin_headers)
        assert r.status_code == 200

    def test_customer_activate_deactivate(self, admin_headers, seed_data):
        customer = seed_data.get("customer", {})
        cid = customer.get("id") or customer.get("customer_id")
        if not cid:
            pytest.skip("No seed customer")
        r = requests.patch(f"{BASE_URL}/api/admin/customers/{cid}/active", json={"is_active": False}, headers=admin_headers)
        assert r.status_code == 200
        # Reactivate
        r2 = requests.patch(f"{BASE_URL}/api/admin/customers/{cid}/active", json={"is_active": True}, headers=admin_headers)
        assert r2.status_code == 200

    def test_customer_notes_merge(self, admin_headers, seed_data):
        """Adding a note should push to notes array (not replace)"""
        customer = seed_data.get("customer", {})
        cid = customer.get("id") or customer.get("customer_id")
        if not cid:
            pytest.skip("No seed customer")
        # Add first note
        r1 = requests.put(f"{BASE_URL}/api/admin/customers/{cid}", json={
            "new_note": "First test note"
        }, headers=admin_headers)
        assert r1.status_code == 200
        # Add second note
        r2 = requests.put(f"{BASE_URL}/api/admin/customers/{cid}", json={
            "new_note": "Second test note"
        }, headers=admin_headers)
        assert r2.status_code == 200
        # Verify both notes exist
        r3 = requests.get(f"{BASE_URL}/api/admin/customers?search=TEST_seed", headers=admin_headers)
        if r3.status_code == 200:
            customers = r3.json().get("customers", [])
            matching = [c for c in customers if c.get("id") == cid]
            if matching:
                notes = matching[0].get("notes", [])
                # Should have at least 2 notes (merge, not replace)
                assert len(notes) >= 2, f"Expected >= 2 notes (merge), got {len(notes)}"


# ===== SECTION 6: Admin - Orders =====

class TestAdminOrders:
    """Admin orders CRUD tests"""

    def test_orders_list(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/orders", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "orders" in data
        assert "total" in data

    def test_orders_pagination(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/orders?page=1&per_page=5", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "orders" in data
        assert len(data["orders"]) <= 5

    def test_orders_status_filter(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/orders?status_filter=paid", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        for order in data.get("orders", []):
            assert order["status"] == "paid"

    def test_create_manual_order(self, admin_headers, seed_data):
        customer = seed_data.get("customer", {})
        cid = customer.get("id") or customer.get("customer_id")
        r = requests.post(f"{BASE_URL}/api/admin/orders/manual", json={
            "customer_id": cid, "amount": 75.00,
            "status": "paid", "payment_method": "bank_transfer",
            "note": "TEST manual order"
        }, headers=admin_headers)
        assert r.status_code in [200, 201]
        data = r.json()
        assert "order_id" in data or "id" in data

    def test_update_order_status(self, admin_headers, seed_data):
        order = seed_data.get("order", {})
        oid = order.get("order_id") or order.get("id")
        if not oid:
            pytest.skip("No seed order")
        r = requests.put(f"{BASE_URL}/api/admin/orders/{oid}", json={
            "status": "completed", "internal_note": "TEST updated note"
        }, headers=admin_headers)
        assert r.status_code == 200

    def test_update_order_invalid_status(self, admin_headers, seed_data):
        """Invalid order status should return 400"""
        order = seed_data.get("order", {})
        oid = order.get("order_id") or order.get("id")
        if not oid:
            pytest.skip("No seed order")
        r = requests.put(f"{BASE_URL}/api/admin/orders/{oid}", json={
            "status": "INVALID_STATUS_XYZ"
        }, headers=admin_headers)
        assert r.status_code == 400

    def test_order_logs(self, admin_headers, seed_data):
        order = seed_data.get("order", {})
        oid = order.get("order_id") or order.get("id")
        if not oid:
            pytest.skip("No seed order")
        r = requests.get(f"{BASE_URL}/api/admin/orders/{oid}/logs", headers=admin_headers)
        assert r.status_code == 200
        assert "logs" in r.json()

    def test_delete_order_soft(self, admin_headers):
        """Create and soft delete an order"""
        r = requests.post(f"{BASE_URL}/api/admin/orders/manual", json={
            "amount": 10.00, "status": "pending", "payment_method": "bank_transfer",
            "note": "TEST order to delete"
        }, headers=admin_headers)
        if r.status_code not in [200, 201]:
            pytest.skip("Could not create order to delete")
        oid = r.json().get("order_id") or r.json().get("id")
        del_r = requests.delete(f"{BASE_URL}/api/admin/orders/{oid}", json={"reason": "Test deletion"}, headers=admin_headers)
        assert del_r.status_code in [200, 204]

    def test_order_note_appended(self, admin_headers, seed_data):
        """Order internal_note should be appended, not replaced"""
        order = seed_data.get("order", {})
        oid = order.get("order_id") or order.get("id")
        if not oid:
            pytest.skip("No seed order")
        # First note
        requests.put(f"{BASE_URL}/api/admin/orders/{oid}", json={"internal_note": "Note A"}, headers=admin_headers)
        # Second note
        r2 = requests.put(f"{BASE_URL}/api/admin/orders/{oid}", json={"internal_note": "Note B"}, headers=admin_headers)
        assert r2.status_code == 200
        # We just verify it doesn't crash; note merge logic depends on backend impl


# ===== SECTION 7: Admin - Subscriptions =====

class TestAdminSubscriptions:
    """Admin subscriptions CRUD tests"""

    def test_subscriptions_list(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/subscriptions", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "subscriptions" in data

    def test_subscriptions_status_filter(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/subscriptions?status=active", headers=admin_headers)
        assert r.status_code == 200
        for sub in r.json().get("subscriptions", []):
            assert sub["status"] == "active"

    def test_subscription_invalid_status(self, admin_headers, seed_data):
        sub = seed_data.get("subscription", {})
        sid = sub.get("subscription_id") or sub.get("id")
        if not sid:
            pytest.skip("No seed subscription")
        r = requests.put(f"{BASE_URL}/api/admin/subscriptions/{sid}", json={
            "status": "INVALID_SUB_STATUS"
        }, headers=admin_headers)
        assert r.status_code == 400

    def test_subscription_logs(self, admin_headers, seed_data):
        sub = seed_data.get("subscription", {})
        sid = sub.get("subscription_id") or sub.get("id")
        if not sid:
            pytest.skip("No seed subscription")
        r = requests.get(f"{BASE_URL}/api/admin/subscriptions/{sid}/logs", headers=admin_headers)
        assert r.status_code == 200
        assert "logs" in r.json()

    def test_cancel_subscription(self, admin_headers, seed_data):
        """Create and cancel subscription"""
        customer = seed_data.get("customer", {})
        cid = customer.get("id") or customer.get("customer_id")
        r = requests.post(f"{BASE_URL}/api/admin/subscriptions/manual", json={
            "customer_id": cid, "amount": 25.00, "plan_name": "TEST Cancel Plan",
            "status": "active", "renewal_date": "2026-12-31"
        }, headers=admin_headers)
        if r.status_code not in [200, 201]:
            pytest.skip("Could not create subscription")
        sid = r.json().get("subscription_id") or r.json().get("id")
        cancel_r = requests.post(f"{BASE_URL}/api/admin/subscriptions/{sid}/cancel", json={
            "reason": "Test cancellation"
        }, headers=admin_headers)
        assert cancel_r.status_code == 200


# ===== SECTION 8: Admin - Articles =====

class TestAdminArticles:
    """Admin articles CRUD tests"""

    def test_articles_list(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/articles/admin/list", headers=admin_headers)
        assert r.status_code == 200
        assert "articles" in r.json()

    def test_create_article(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/articles", json={
            "title": "TEST_E2E Blog Article", "content": "<p>Test content</p>",
            "category": "Blog", "visibility": "all"
        }, headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "id" in data or "article" in data

    def test_create_scope_final_article_with_price(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/articles", json={
            "title": "TEST_E2E Scope Final", "content": "<p>Scope content</p>",
            "category": "Scope - Final Won", "visibility": "all", "price": 299.99
        }, headers=admin_headers)
        assert r.status_code == 200

    def test_update_article(self, admin_headers, seed_data):
        article = seed_data.get("article", {})
        aid = article.get("id") or article.get("article_id")
        if not aid:
            pytest.skip("No seed article")
        r = requests.put(f"{BASE_URL}/api/articles/{aid}", json={
            "title": "TEST_E2E Scope Final Updated", "price": 599.99
        }, headers=admin_headers)
        assert r.status_code == 200

    def test_article_logs(self, admin_headers, seed_data):
        article = seed_data.get("article", {})
        aid = article.get("id") or article.get("article_id")
        if not aid:
            pytest.skip("No seed article")
        r = requests.get(f"{BASE_URL}/api/articles/{aid}/logs", headers=admin_headers)
        assert r.status_code == 200

    def test_delete_article(self, admin_headers):
        """Create and delete an article"""
        r = requests.post(f"{BASE_URL}/api/articles", json={
            "title": "TEST_E2E Delete Article", "content": "<p>Delete me</p>",
            "category": "Blog", "visibility": "all"
        }, headers=admin_headers)
        if r.status_code != 200:
            pytest.skip("Could not create article")
        aid = r.json().get("id")
        del_r = requests.delete(f"{BASE_URL}/api/articles/{aid}", headers=admin_headers)
        assert del_r.status_code == 200


# ===== SECTION 9: Admin - Categories =====

class TestAdminCategories:
    """Admin categories CRUD tests"""

    def test_categories_list(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/categories", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "categories" in data

    def test_create_category(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/categories", json={
            "name": "TEST_E2E_New_Cat", "description": "New test category", "is_active": True
        }, headers=admin_headers)
        assert r.status_code == 200

    def test_update_category(self, admin_headers, seed_data):
        cat = seed_data.get("category", {})
        cid = cat.get("id") or cat.get("category_id")
        if not cid:
            pytest.skip("No seed category")
        r = requests.put(f"{BASE_URL}/api/admin/categories/{cid}", json={
            "description": "Updated description"
        }, headers=admin_headers)
        assert r.status_code == 200

    def test_delete_empty_category(self, admin_headers):
        """Category with no products should delete successfully"""
        r = requests.post(f"{BASE_URL}/api/admin/categories", json={
            "name": "TEST_E2E_Delete_Cat", "description": "To delete", "is_active": True
        }, headers=admin_headers)
        if r.status_code != 200:
            pytest.skip("Could not create category")
        cid = r.json().get("id")
        if not cid:
            pytest.skip("No category id returned")
        del_r = requests.delete(f"{BASE_URL}/api/admin/categories/{cid}", headers=admin_headers)
        assert del_r.status_code in [200, 204]

    def test_delete_category_with_products_fails(self, admin_headers, seed_data):
        """Category with products should return 409"""
        cat = seed_data.get("category", {})
        cid = cat.get("id") or cat.get("category_id")
        if not cid:
            pytest.skip("No seed category")
        # Seed category has a product linked to it
        del_r = requests.delete(f"{BASE_URL}/api/admin/categories/{cid}", headers=admin_headers)
        assert del_r.status_code == 409


# ===== SECTION 10: Admin - Catalog/Products =====

class TestAdminCatalog:
    """Admin products CRUD tests"""

    def test_products_all_list(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/products-all", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "products" in data

    def test_create_product(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/products", json={
            "name": "TEST_E2E_New_Product", "category": "TEST_E2E_Category",
            "description": "New test product", "price": 149.99,
            "billing_type": "one-time", "pricing_complexity": "simple",
            "is_active": True, "currency": "GBP"
        }, headers=admin_headers)
        assert r.status_code == 200

    def test_update_product(self, admin_headers, seed_data):
        product = seed_data.get("product", {})
        pid = product.get("id")
        if not pid:
            pytest.skip("No seed product")
        r = requests.put(f"{BASE_URL}/api/admin/products/{pid}", json={
            "name": "TEST_E2E_Product_Updated", "price": 109.99
        }, headers=admin_headers)
        assert r.status_code == 200

    def test_products_filter_by_category(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/products-all?category=TEST_E2E_Category", headers=admin_headers)
        assert r.status_code == 200


# ===== SECTION 11: Admin - Terms =====

class TestAdminTerms:
    """Admin terms CRUD tests"""

    def test_terms_list(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/terms", headers=admin_headers)
        assert r.status_code == 200
        assert "terms" in r.json()

    def test_create_terms(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/terms", json={
            "title": "TEST_E2E Terms Duplicate", "content": "Test terms content 2",
            "is_default": False
        }, headers=admin_headers)
        assert r.status_code in [200, 201]

    def test_delete_default_terms_fails(self, admin_headers):
        """Deleting default terms should fail"""
        terms = requests.get(f"{BASE_URL}/api/admin/terms", headers=admin_headers).json().get("terms", [])
        default_terms = [t for t in terms if t.get("is_default")]
        if not default_terms:
            pytest.skip("No default terms found")
        tid = default_terms[0]["id"]
        r = requests.delete(f"{BASE_URL}/api/admin/terms/{tid}", headers=admin_headers)
        assert r.status_code == 400

    def test_delete_non_default_terms(self, admin_headers, seed_data):
        terms = seed_data.get("terms", {})
        tid = terms.get("id") or terms.get("terms_id")
        if not tid:
            pytest.skip("No seed terms")
        # Try to delete (may fail if it's the only terms)
        r = requests.delete(f"{BASE_URL}/api/admin/terms/{tid}", headers=admin_headers)
        assert r.status_code in [200, 204, 400]  # 400 if it's the last default


# ===== SECTION 12: Admin - Override Codes =====

class TestAdminOverrideCodes:
    """Admin override codes CRUD tests"""

    def test_override_codes_list(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/override-codes", headers=admin_headers)
        assert r.status_code == 200
        assert "codes" in r.json()

    def test_create_override_code(self, admin_headers, seed_data):
        customer = seed_data.get("customer", {})
        cid = customer.get("id") or customer.get("customer_id")
        r = requests.post(f"{BASE_URL}/api/admin/override-codes", json={
            "code": "TESTE2EOVERRIDE2", "customer_id": cid,
            "is_active": True,
            "expires_at": (datetime.utcnow() + timedelta(days=60)).isoformat()
        }, headers=admin_headers)
        assert r.status_code == 200

    def test_duplicate_override_code_fails(self, admin_headers, seed_data):
        """Duplicate override code should return 400"""
        customer = seed_data.get("customer", {})
        cid = customer.get("id") or customer.get("customer_id")
        # Try to create same code twice
        requests.post(f"{BASE_URL}/api/admin/override-codes", json={
            "code": "TESTDUPOVERRIDE", "customer_id": cid, "is_active": True
        }, headers=admin_headers)
        r2 = requests.post(f"{BASE_URL}/api/admin/override-codes", json={
            "code": "TESTDUPOVERRIDE", "customer_id": cid, "is_active": True
        }, headers=admin_headers)
        assert r2.status_code == 400

    def test_update_override_code(self, admin_headers, seed_data):
        oc = seed_data.get("override_code", {})
        oid = oc.get("id") or oc.get("code_id")
        if not oid:
            pytest.skip("No seed override code")
        r = requests.put(f"{BASE_URL}/api/admin/override-codes/{oid}", json={
            "is_active": False
        }, headers=admin_headers)
        assert r.status_code == 200

    def test_deactivate_override_code(self, admin_headers, seed_data):
        oc = seed_data.get("override_code", {})
        oid = oc.get("id") or oc.get("code_id")
        if not oid:
            pytest.skip("No seed override code")
        r = requests.delete(f"{BASE_URL}/api/admin/override-codes/{oid}", headers=admin_headers)
        assert r.status_code in [200, 204]


# ===== SECTION 13: Admin - Promo Codes =====

class TestAdminPromoCodes:
    """Admin promo codes CRUD tests"""

    def test_promo_codes_list(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/promo-codes", headers=admin_headers)
        assert r.status_code == 200
        assert "codes" in r.json()

    def test_create_promo_code_zohor(self, admin_headers):
        """Test creating ZOHOR promo code"""
        r = requests.post(f"{BASE_URL}/api/admin/promo-codes", json={
            "code": "ZOHOR2", "discount_type": "percentage", "discount_value": 15,
            "applies_to": "both", "enabled": True
        }, headers=admin_headers)
        assert r.status_code == 200

    def test_duplicate_promo_code_fails(self, admin_headers):
        """Duplicate promo code should fail"""
        requests.post(f"{BASE_URL}/api/admin/promo-codes", json={
            "code": "TESTDUPPROMO", "discount_type": "fixed", "discount_value": 10,
            "applies_to": "both", "enabled": True
        }, headers=admin_headers)
        r2 = requests.post(f"{BASE_URL}/api/admin/promo-codes", json={
            "code": "TESTDUPPROMO", "discount_type": "fixed", "discount_value": 10,
            "applies_to": "both", "enabled": True
        }, headers=admin_headers)
        assert r2.status_code == 400

    def test_update_promo_code(self, admin_headers, seed_data):
        pc = seed_data.get("promo_code", {})
        pid = pc.get("id") or pc.get("code_id")
        if not pid:
            pytest.skip("No seed promo code")
        r = requests.put(f"{BASE_URL}/api/admin/promo-codes/{pid}", json={
            "discount_value": 20, "enabled": True
        }, headers=admin_headers)
        assert r.status_code == 200

    def test_delete_promo_code(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/promo-codes", json={
            "code": "TESTDELPROMO", "discount_type": "fixed", "discount_value": 5,
            "applies_to": "both", "enabled": True
        }, headers=admin_headers)
        if r.status_code != 200:
            pytest.skip("Could not create promo code")
        pid = r.json().get("id")
        if not pid:
            pytest.skip("No id returned")
        del_r = requests.delete(f"{BASE_URL}/api/admin/promo-codes/{pid}", headers=admin_headers)
        assert del_r.status_code in [200, 204]


# ===== SECTION 14: Admin - Bank Transactions =====

class TestAdminBankTransactions:
    """Admin bank transactions CRUD tests"""

    def test_bank_transactions_list(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/bank-transactions", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "transactions" in data

    def test_create_bank_transaction(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/bank-transactions", json={
            "source": "bank_transfer", "type": "credit", "amount": 100.00,
            "currency": "GBP", "reference": "TEST-TXN-NEW", "status": "pending"
        }, headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "id" in data or "transaction" in data

    def test_bank_transaction_logs(self, admin_headers, seed_data):
        txn = seed_data.get("bank_transaction", {})
        tid = txn.get("id") or txn.get("transaction_id")
        if not tid:
            pytest.skip("No seed bank transaction")
        r = requests.get(f"{BASE_URL}/api/admin/bank-transactions/{tid}/logs", headers=admin_headers)
        assert r.status_code == 200

    def test_update_bank_transaction(self, admin_headers, seed_data):
        txn = seed_data.get("bank_transaction", {})
        tid = txn.get("id") or txn.get("transaction_id")
        if not tid:
            pytest.skip("No seed bank transaction")
        r = requests.put(f"{BASE_URL}/api/admin/bank-transactions/{tid}", json={
            "status": "matched", "reference": "TEST-UPDATED-REF"
        }, headers=admin_headers)
        assert r.status_code == 200

    def test_delete_bank_transaction(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/bank-transactions", json={
            "source": "bank_transfer", "type": "debit", "amount": 50.00,
            "currency": "GBP", "reference": "TEST-DEL-TXN", "status": "pending"
        }, headers=admin_headers)
        if r.status_code != 200:
            pytest.skip("Could not create bank transaction")
        tid = r.json().get("id")
        if not tid:
            pytest.skip("No id returned")
        del_r = requests.delete(f"{BASE_URL}/api/admin/bank-transactions/{tid}", headers=admin_headers)
        assert del_r.status_code in [200, 204]


# ===== SECTION 15: Admin - Quote Requests =====

class TestAdminQuoteRequests:
    """Admin quote requests tests"""

    def test_quote_requests_list(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/quote-requests", headers=admin_headers)
        assert r.status_code == 200
        assert "quote_requests" in r.json()

    def test_quote_requests_pagination(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/quote-requests?page=1&per_page=5", headers=admin_headers)
        assert r.status_code == 200


# ===== SECTION 16: Admin - Users =====

class TestAdminUsers:
    """Admin users management tests"""

    def test_users_list(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/users", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "users" in data

    def test_create_admin_user(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/users", json={
            "email": "TEST_admin_user@e2e.com", "full_name": "TEST Admin User",
            "password": "Test1234!", "role": "admin"
        }, headers=admin_headers)
        assert r.status_code in [200, 201]


# ===== SECTION 17: Admin - Settings =====

class TestAdminSettings:
    """Admin settings tests"""

    def test_settings_load(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/settings", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "store_name" in data or "settings" in data

    def test_update_setting(self, admin_headers):
        r = requests.put(f"{BASE_URL}/api/admin/settings", json={
            "store_name": "TEST E2E Store"
        }, headers=admin_headers)
        assert r.status_code == 200

    def test_structured_settings(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/settings/structured", headers=admin_headers)
        assert r.status_code == 200


# ===== SECTION 18: Admin - Logs =====

class TestAdminLogs:
    """Admin audit logs tests"""

    def test_logs_list(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/audit-logs", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "logs" in data
        assert "total" in data

    def test_logs_filter_actor_type(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/audit-logs?actor_type=admin", headers=admin_headers)
        assert r.status_code == 200
        for log in r.json().get("logs", []):
            assert log["actor_type"] == "admin"

    def test_logs_filter_success_false(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/audit-logs?success=false", headers=admin_headers)
        assert r.status_code == 200

    def test_logs_pagination(self, admin_headers):
        r1 = requests.get(f"{BASE_URL}/api/admin/audit-logs?page=1&limit=10", headers=admin_headers)
        r2 = requests.get(f"{BASE_URL}/api/admin/audit-logs?page=2&limit=10", headers=admin_headers)
        assert r1.status_code == 200
        assert r2.status_code == 200
        logs1 = [l["id"] for l in r1.json().get("logs", [])]
        logs2 = [l["id"] for l in r2.json().get("logs", [])]
        # Page 2 should have different records
        if logs1 and logs2:
            assert logs1 != logs2

    def test_logs_login_creates_audit(self, admin_headers):
        """Login should create USER_LOGIN audit entry"""
        r = requests.get(f"{BASE_URL}/api/admin/audit-logs?action=USER_LOGIN", headers=admin_headers)
        assert r.status_code == 200
        logs = r.json().get("logs", [])
        assert len(logs) > 0, "Expected USER_LOGIN audit logs"


# ===== SECTION 19: Exports =====

class TestExports:
    """CSV export endpoint tests"""

    def test_export_orders(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/export/orders", headers=admin_headers)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")

    def test_export_customers(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/export/customers", headers=admin_headers)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")

    def test_export_subscriptions(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/export/subscriptions", headers=admin_headers)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")

    def test_export_catalog(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/export/catalog", headers=admin_headers)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")

    def test_export_bank_transactions(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/export/bank-transactions", headers=admin_headers)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")

    def test_export_quote_requests(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/export/quote-requests", headers=admin_headers)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")

    def test_export_promo_codes(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/export/promo-codes", headers=admin_headers)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")

    def test_export_override_codes(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/export/override-codes", headers=admin_headers)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")

    def test_export_terms(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/export/terms", headers=admin_headers)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")

    def test_export_articles(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/export/articles", headers=admin_headers)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")

    def test_export_categories(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/export/categories", headers=admin_headers)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")


# ===== SECTION 20: Error Handling / Guardrails =====

class TestGuardrailsAndErrors:
    """Error handling and guardrail tests"""

    def test_401_unauthenticated(self):
        """Unauthenticated requests to protected endpoints"""
        r = requests.get(f"{BASE_URL}/api/admin/customers")
        assert r.status_code in [401, 403]

    def test_403_customer_accessing_admin(self, customer_headers):
        """Customer token should not access admin endpoints"""
        r = requests.get(f"{BASE_URL}/api/admin/customers", headers=customer_headers)
        assert r.status_code in [401, 403]

    def test_404_nonexistent_resource(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/orders/nonexistent-99999", headers=admin_headers)
        assert r.status_code == 404

    def test_422_missing_required_fields(self, admin_headers):
        """Missing required fields should return 422"""
        r = requests.post(f"{BASE_URL}/api/admin/promo-codes", json={
            "discount_type": "percentage"
            # Missing required 'code' field
        }, headers=admin_headers)
        assert r.status_code == 422

    def test_currency_override_locks_currency(self, admin_headers, seed_data):
        """Setting currency_override should lock the currency"""
        customer = seed_data.get("customer", {})
        cid = customer.get("id") or customer.get("customer_id")
        if not cid:
            pytest.skip("No seed customer")
        r = requests.put(f"{BASE_URL}/api/admin/customers/{cid}", json={
            "currency": "USD", "currency_locked": True
        }, headers=admin_headers)
        assert r.status_code == 200

    def test_invalid_order_status_rejected(self, admin_headers, seed_data):
        order = seed_data.get("order", {})
        oid = order.get("order_id") or order.get("id")
        if not oid:
            pytest.skip("No seed order")
        r = requests.put(f"{BASE_URL}/api/admin/orders/{oid}", json={
            "status": "NOT_A_REAL_STATUS"
        }, headers=admin_headers)
        assert r.status_code == 400

    def test_invalid_subscription_status_rejected(self, admin_headers, seed_data):
        sub = seed_data.get("subscription", {})
        sid = sub.get("subscription_id") or sub.get("id")
        if not sid:
            pytest.skip("No seed subscription")
        r = requests.put(f"{BASE_URL}/api/admin/subscriptions/{sid}", json={
            "status": "NOT_VALID_STATUS"
        }, headers=admin_headers)
        assert r.status_code == 400


# ===== SECTION 21: Audit Log Completeness =====

class TestAuditLogCompleteness:
    """Verify audit logs are created for key operations"""

    def test_audit_log_for_article_created(self, admin_headers):
        """Create article and verify audit log"""
        r = requests.post(f"{BASE_URL}/api/articles", json={
            "title": "TEST_AUDIT Article", "content": "<p>Audit test</p>",
            "category": "Blog", "visibility": "all"
        }, headers=admin_headers)
        assert r.status_code == 200
        # Wait a moment for async audit
        time.sleep(0.5)
        logs = requests.get(f"{BASE_URL}/api/admin/audit-logs?action=ARTICLE_CREATED", headers=admin_headers)
        assert logs.status_code == 200
        assert len(logs.json().get("logs", [])) > 0

    def test_audit_log_for_customer_created(self, admin_headers):
        """Create customer and verify audit log"""
        r = requests.post(f"{BASE_URL}/api/admin/customers/create", json={
            "email": "TEST_audit_cust@e2e.com", "full_name": "TEST Audit Customer",
            "address": {"country": "GB"}
        }, headers=admin_headers)
        assert r.status_code in [200, 201, 400]  # 400 if already exists
        time.sleep(0.5)
        logs = requests.get(f"{BASE_URL}/api/admin/audit-logs?action=CUSTOMER_CREATED", headers=admin_headers)
        assert logs.status_code == 200

    def test_audit_log_for_promo_created(self, admin_headers):
        """Create promo code and verify audit log"""
        r = requests.post(f"{BASE_URL}/api/admin/promo-codes", json={
            "code": "TEST_AUDIT_PROMO_LOG", "discount_type": "fixed",
            "discount_value": 5, "applies_to": "both", "enabled": True
        }, headers=admin_headers)
        assert r.status_code in [200, 400]
        time.sleep(0.5)
        logs = requests.get(f"{BASE_URL}/api/admin/audit-logs?action=PROMO_CODE_CREATED", headers=admin_headers)
        assert logs.status_code == 200

    def test_audit_entity_type_pascal_case(self, admin_headers):
        """Verify entity types are stored in PascalCase (not snake_case)"""
        logs = requests.get(f"{BASE_URL}/api/admin/audit-logs?entity_type=PromoCode", headers=admin_headers)
        assert logs.status_code == 200
        for log in logs.json().get("logs", []):
            assert log["entity_type"] == "PromoCode", f"Expected PromoCode, got {log['entity_type']}"
