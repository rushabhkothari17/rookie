"""
Comprehensive backend test for refactored route modules.
Tests all new route files under /app/backend/routes/
"""
import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────
@pytest.fixture(scope="session")
def admin_token():
    """Authenticate as admin and return JWT token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200, f"Admin login failed: {resp.status_code} {resp.text}"
    token = resp.json().get("token")
    assert token, "No token returned"
    return token


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ─────────────────────────────────────────────
# Public endpoints
# ─────────────────────────────────────────────
class TestPublicEndpoints:
    """Public endpoints: root, products, settings"""

    def test_root(self):
        resp = requests.get(f"{BASE_URL}/api/")
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data
        print(f"✓ Root: {data['message']}")

    def test_public_products(self):
        resp = requests.get(f"{BASE_URL}/api/products")
        assert resp.status_code == 200
        data = resp.json()
        assert "products" in data
        assert isinstance(data["products"], list)
        print(f"✓ Products: {len(data['products'])} products returned")

    def test_public_settings(self):
        resp = requests.get(f"{BASE_URL}/api/settings/public")
        assert resp.status_code == 200
        data = resp.json()
        assert "settings" in data
        print(f"✓ Public settings returned: {list(data['settings'].keys())[:5]}")

    def test_categories(self):
        resp = requests.get(f"{BASE_URL}/api/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert "categories" in data
        print(f"✓ Categories: {data['categories']}")


# ─────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────
class TestAuth:
    """Auth: login, register, profile"""

    def test_login_success(self):
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert isinstance(data["token"], str)
        print("✓ Admin login successful")

    def test_login_invalid_credentials(self):
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "wrong@test.com", "password": "wrongpass"})
        assert resp.status_code == 401
        print("✓ Invalid login correctly returns 401")

    def test_get_profile(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/me", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "user" in data
        assert data["user"]["email"] == ADMIN_EMAIL
        assert data["user"]["is_admin"] is True
        print(f"✓ /me returns correct admin profile: {data['user']['email']}")

    def test_register_new_user(self, session):
        """Register a test user (TEST_ prefix for cleanup identification)"""
        unique_email = f"test_refactor_{uuid.uuid4().hex[:6]}@test.com"
        payload = {
            "email": unique_email,
            "password": "TestPass123!",
            "full_name": "TEST Refactor User",
            "company_name": "TEST Co",
            "job_title": "Tester",
            "phone": "1234567890",
            "address": {
                "line1": "123 Test St",
                "line2": "",
                "city": "Testville",
                "region": "NSW",
                "postal": "2000",
                "country": "AU"
            }
        }
        resp = session.post(f"{BASE_URL}/api/auth/register", json=payload)
        assert resp.status_code == 200, f"Register failed: {resp.text}"
        data = resp.json()
        assert "verification_code" in data or "message" in data
        print(f"✓ User registered: {unique_email}")

    def test_unauthorized_profile_access(self):
        resp = requests.get(f"{BASE_URL}/api/me")
        assert resp.status_code in [401, 403]
        print("✓ /me correctly rejects unauthenticated request")


# ─────────────────────────────────────────────
# Admin Customers
# ─────────────────────────────────────────────
class TestAdminCustomers:
    """Admin: Customer management"""

    def test_list_customers(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/customers", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "customers" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert "total_pages" in data
        print(f"✓ Admin customers: {data['total']} total, page {data['page']}/{data['total_pages']}")

    def test_list_customers_pagination(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/customers?page=1&per_page=5", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["customers"]) <= 5
        assert data["per_page"] == 5
        print(f"✓ Pagination working: returned {len(data['customers'])} customers with per_page=5")

    def test_list_customers_search_filter(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/customers?search=test", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "customers" in data
        print(f"✓ Customer search filter works: {data['total']} matches")

    def test_create_customer(self, admin_headers):
        unique_email = f"test_cust_{uuid.uuid4().hex[:6]}@test.com"
        payload = {
            "full_name": "TEST Customer Create",
            "company_name": "TEST Corp",
            "job_title": "Manager",
            "email": unique_email,
            "phone": "0411000111",
            "password": "TestPass123!",
            "line1": "45 Test Ave",
            "city": "Sydney",
            "region": "NSW",
            "postal": "2000",
            "country": "AU",
            "mark_verified": True
        }
        resp = requests.post(f"{BASE_URL}/api/admin/customers/create", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Create customer failed: {resp.text}"
        data = resp.json()
        assert "customer_id" in data
        assert "user_id" in data
        # Store for later use
        TestAdminCustomers._created_customer_id = data["customer_id"]
        print(f"✓ Admin create customer: {data['customer_id']}")
        return data

    def test_update_customer_payment_methods(self, admin_headers):
        """Update payment methods on an existing customer"""
        # First get a customer
        resp = requests.get(f"{BASE_URL}/api/admin/customers?per_page=1", headers=admin_headers)
        customers = resp.json().get("customers", [])
        if not customers:
            pytest.skip("No customers available for this test")
        cust_id = customers[0]["id"]
        payload = {"allow_bank_transfer": True, "allow_card_payment": True}
        resp = requests.put(f"{BASE_URL}/api/admin/customers/{cust_id}/payment-methods", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Payment methods update failed: {resp.text}"
        data = resp.json()
        assert "message" in data
        print(f"✓ Payment methods updated for customer {cust_id}")

    def test_activate_deactivate_customer(self, admin_headers):
        """Test activate/deactivate customer endpoint"""
        # Create test customer first
        unique_email = f"test_act_{uuid.uuid4().hex[:6]}@test.com"
        payload = {
            "full_name": "TEST Activate Customer",
            "company_name": "TEST Inc",
            "job_title": "Tester",
            "email": unique_email,
            "phone": "0411000222",
            "password": "TestPass123!",
            "line1": "10 Test Rd",
            "city": "Melbourne",
            "region": "VIC",
            "postal": "3000",
            "country": "AU",
            "mark_verified": True
        }
        create_resp = requests.post(f"{BASE_URL}/api/admin/customers/create", json=payload, headers=admin_headers)
        assert create_resp.status_code == 200
        cust_id = create_resp.json()["customer_id"]

        # Deactivate
        resp = requests.patch(f"{BASE_URL}/api/admin/customers/{cust_id}/active?active=false", headers=admin_headers)
        assert resp.status_code == 200, f"Deactivate failed: {resp.text}"
        data = resp.json()
        assert data.get("is_active") is False

        # Reactivate
        resp = requests.patch(f"{BASE_URL}/api/admin/customers/{cust_id}/active?active=true", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("is_active") is True
        print(f"✓ Customer activate/deactivate works for {cust_id}")


# ─────────────────────────────────────────────
# Admin Orders
# ─────────────────────────────────────────────
class TestAdminOrders:
    """Admin: Order management"""

    def test_list_orders(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/orders", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "orders" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert "total_pages" in data
        print(f"✓ Admin orders: {data['total']} total")

    def test_list_orders_pagination(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/orders?page=1&per_page=5", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["orders"]) <= 5
        print(f"✓ Orders pagination: {len(data['orders'])} returned with per_page=5")

    def test_list_orders_status_filter(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/orders?status_filter=paid", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        for order in data["orders"]:
            assert order["status"] == "paid"
        print(f"✓ Orders status filter: {len(data['orders'])} paid orders")

    def test_create_manual_order(self, admin_headers):
        """Create a manual order for an existing customer and product"""
        # Get a customer email
        cust_resp = requests.get(f"{BASE_URL}/api/admin/customers?per_page=1", headers=admin_headers)
        customers = cust_resp.json().get("customers", [])
        if not customers:
            pytest.skip("No customers available")

        cust_id = customers[0].get("id", "")
        # Get corresponding user email
        users_data = cust_resp.json().get("users", [])
        customer_email = None
        cust_user_id = customers[0].get("user_id", "")
        for u in users_data:
            if u["id"] == cust_user_id:
                customer_email = u["email"]
                break
        if not customer_email:
            # fallback: fetch directly
            user_resp = requests.get(f"{BASE_URL}/api/admin/users", headers=admin_headers)
            if user_resp.status_code != 200:
                customer_email = ADMIN_EMAIL  # fallback to admin
            else:
                customer_email = ADMIN_EMAIL

        # Get a product
        prod_resp = requests.get(f"{BASE_URL}/api/products")
        products = prod_resp.json().get("products", [])
        if not products:
            pytest.skip("No products available")
        product_id = products[0]["id"]

        payload = {
            "customer_email": customer_email,
            "product_id": product_id,
            "quantity": 1,
            "inputs": {},
            "subtotal": 999.0,
            "discount": 0.0,
            "fee": 0.0,
            "status": "paid",
            "internal_note": "TEST manual order"
        }
        resp = requests.post(f"{BASE_URL}/api/admin/orders/manual", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Manual order creation failed: {resp.text}"
        data = resp.json()
        assert "order_id" in data
        assert "order_number" in data
        TestAdminOrders._created_order_id = data["order_id"]
        print(f"✓ Manual order created: {data['order_number']}")
        return data

    def test_update_order(self, admin_headers):
        """Update an existing order"""
        # First create an order
        create_data = self.test_create_manual_order(admin_headers)
        order_id = create_data["order_id"]
        
        payload = {"status": "completed", "internal_note": "Updated by test"}
        resp = requests.put(f"{BASE_URL}/api/admin/orders/{order_id}", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Order update failed: {resp.text}"
        data = resp.json()
        assert "message" in data
        print(f"✓ Order {order_id} updated successfully")

    def test_delete_order(self, admin_headers):
        """Delete (soft-delete) an order"""
        create_data = self.test_create_manual_order(admin_headers)
        order_id = create_data["order_id"]

        resp = requests.delete(f"{BASE_URL}/api/admin/orders/{order_id}", json={"reason": "TEST deletion"}, headers=admin_headers)
        assert resp.status_code == 200, f"Order delete failed: {resp.text}"
        data = resp.json()
        assert "message" in data
        print(f"✓ Order {order_id} soft-deleted successfully")


# ─────────────────────────────────────────────
# Admin Subscriptions
# ─────────────────────────────────────────────
class TestAdminSubscriptions:
    """Admin: Subscription management"""

    def test_list_subscriptions(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/subscriptions", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "subscriptions" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert "total_pages" in data
        print(f"✓ Admin subscriptions: {data['total']} total")

    def test_list_subscriptions_pagination(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/subscriptions?page=1&per_page=5", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["subscriptions"]) <= 5
        print(f"✓ Subscription pagination: {len(data['subscriptions'])} per page")

    def test_list_subscriptions_status_filter(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/subscriptions?status=active", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        for sub in data["subscriptions"]:
            assert sub["status"] == "active"
        print(f"✓ Subscription status filter: {len(data['subscriptions'])} active")

    def test_create_manual_subscription(self, admin_headers):
        """Create a manual subscription"""
        # Get a customer email
        cust_resp = requests.get(f"{BASE_URL}/api/admin/customers?per_page=1", headers=admin_headers)
        cust_data = cust_resp.json()
        customers = cust_data.get("customers", [])
        if not customers:
            pytest.skip("No customers available")

        cust_user_id = customers[0].get("user_id", "")
        users_data = cust_data.get("users", [])
        customer_email = ADMIN_EMAIL
        for u in users_data:
            if u["id"] == cust_user_id:
                customer_email = u["email"]
                break

        # Get a subscription product
        prod_resp = requests.get(f"{BASE_URL}/api/products")
        products = prod_resp.json().get("products", [])
        sub_products = [p for p in products if p.get("is_subscription")]
        if not sub_products:
            sub_products = products
        if not sub_products:
            pytest.skip("No products available")
        product_id = sub_products[0]["id"]

        from datetime import datetime, timedelta
        renewal_date = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S")

        payload = {
            "customer_email": customer_email,
            "product_id": product_id,
            "quantity": 1,
            "inputs": {},
            "amount": 250.0,
            "renewal_date": renewal_date,
            "status": "active",
            "internal_note": "TEST manual subscription"
        }
        resp = requests.post(f"{BASE_URL}/api/admin/subscriptions/manual", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Manual subscription creation failed: {resp.text}"
        data = resp.json()
        assert "subscription_id" in data
        assert "subscription_number" in data
        TestAdminSubscriptions._created_sub_id = data["subscription_id"]
        print(f"✓ Manual subscription created: {data['subscription_number']}")
        return data

    def test_update_subscription(self, admin_headers):
        """Update a subscription"""
        create_data = self.test_create_manual_subscription(admin_headers)
        sub_id = create_data["subscription_id"]

        payload = {"status": "paused", "new_note": "TEST note added"}
        resp = requests.put(f"{BASE_URL}/api/admin/subscriptions/{sub_id}", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Sub update failed: {resp.text}"
        data = resp.json()
        assert "message" in data
        print(f"✓ Subscription {sub_id} updated")

    def test_cancel_subscription(self, admin_headers):
        """Cancel a subscription"""
        create_data = self.test_create_manual_subscription(admin_headers)
        sub_id = create_data["subscription_id"]

        resp = requests.post(f"{BASE_URL}/api/admin/subscriptions/{sub_id}/cancel", headers=admin_headers)
        assert resp.status_code == 200, f"Sub cancel failed: {resp.text}"
        data = resp.json()
        assert "message" in data
        assert "cancelled_at" in data
        print(f"✓ Subscription {sub_id} cancelled")


# ─────────────────────────────────────────────
# Admin Users
# ─────────────────────────────────────────────
class TestAdminUsers:
    """Admin: User management (super_admin required)"""

    def test_list_admin_users(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/users", headers=admin_headers)
        # super_admin access required - 200 if admin is super_admin, 403 otherwise
        assert resp.status_code in [200, 403], f"Unexpected status: {resp.status_code} {resp.text}"
        if resp.status_code == 200:
            data = resp.json()
            assert "users" in data
            assert "total" in data
            print(f"✓ Admin users list: {data['total']} admin users")
        else:
            print(f"⚠ Admin users requires super_admin (got 403 - current user may be regular admin)")

    def test_create_admin_user(self, admin_headers):
        """Create a new admin user"""
        unique_email = f"test_admin_{uuid.uuid4().hex[:6]}@test.com"
        payload = {
            "email": unique_email,
            "full_name": "TEST Admin User",
            "company_name": "TEST Admin Corp",
            "job_title": "Admin Tester",
            "phone": "0411000333",
            "password": "AdminTest123!",
            "role": "admin"
        }
        resp = requests.post(f"{BASE_URL}/api/admin/users", json=payload, headers=admin_headers)
        assert resp.status_code in [200, 403], f"Unexpected status: {resp.status_code} {resp.text}"
        if resp.status_code == 200:
            data = resp.json()
            assert "user_id" in data
            print(f"✓ Admin user created: {data['user_id']}")
        else:
            print(f"⚠ Create admin user requires super_admin (403)")


# ─────────────────────────────────────────────
# Admin Catalog
# ─────────────────────────────────────────────
class TestAdminCatalog:
    """Admin: Products + categories"""

    def test_list_all_products(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/products-all", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "products" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert "total_pages" in data
        print(f"✓ Admin products-all: {data['total']} products")

    def test_list_products_pagination(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/products-all?page=1&per_page=5", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["products"]) <= 5
        print(f"✓ Product pagination working")

    def test_list_categories(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/categories", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "categories" in data
        assert "total" in data
        print(f"✓ Admin categories: {data['total']} categories")

    def test_create_category(self, admin_headers):
        """Create a new test category"""
        cat_name = f"TEST Category {uuid.uuid4().hex[:4]}"
        payload = {"name": cat_name, "description": "TEST category for automated tests", "is_active": True}
        resp = requests.post(f"{BASE_URL}/api/admin/categories", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Create category failed: {resp.text}"
        data = resp.json()
        assert "category" in data
        assert data["category"]["name"] == cat_name
        TestAdminCatalog._created_cat_id = data["category"]["id"]
        TestAdminCatalog._created_cat_name = cat_name
        print(f"✓ Category created: {cat_name} (id={data['category']['id']})")
        return data

    def test_update_category(self, admin_headers):
        """Update the created category"""
        create_data = self.test_create_category(admin_headers)
        cat_id = create_data["category"]["id"]

        payload = {"description": "TEST updated description", "is_active": False}
        resp = requests.put(f"{BASE_URL}/api/admin/categories/{cat_id}", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Update category failed: {resp.text}"
        data = resp.json()
        assert "category" in data
        print(f"✓ Category {cat_id} updated")

    def test_delete_category_no_products(self, admin_headers):
        """Delete a category that has no products"""
        create_data = self.test_create_category(admin_headers)
        cat_id = create_data["category"]["id"]

        resp = requests.delete(f"{BASE_URL}/api/admin/categories/{cat_id}", headers=admin_headers)
        assert resp.status_code == 200, f"Delete category failed: {resp.text}"
        print(f"✓ Category {cat_id} deleted")


# ─────────────────────────────────────────────
# Admin Quote Requests
# ─────────────────────────────────────────────
class TestAdminQuoteRequests:
    """Admin: Quote request listing"""

    def test_list_quote_requests(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/quote-requests", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "quotes" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert "total_pages" in data
        print(f"✓ Admin quote requests: {data['total']} total")

    def test_list_quote_requests_pagination(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/quote-requests?page=1&per_page=5", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["quotes"]) <= 5
        print(f"✓ Quote requests pagination: {len(data['quotes'])} per page")


# ─────────────────────────────────────────────
# Admin Bank Transactions
# ─────────────────────────────────────────────
class TestAdminBankTransactions:
    """Admin: Bank transaction CRUD"""

    def test_list_bank_transactions(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/bank-transactions", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "transactions" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert "total_pages" in data
        print(f"✓ Bank transactions: {data['total']} total")

    def test_create_bank_transaction(self, admin_headers):
        """Create a new bank transaction"""
        payload = {
            "date": "2026-02-01",
            "source": "manual",
            "transaction_id": f"TXN-TEST-{uuid.uuid4().hex[:8]}",
            "type": "payment",
            "amount": 500.0,
            "fees": 2.50,
            "currency": "USD",
            "status": "completed",
            "description": "TEST transaction for automated testing",
            "internal_notes": "Created by test suite"
        }
        resp = requests.post(f"{BASE_URL}/api/admin/bank-transactions", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Create bank transaction failed: {resp.text}"
        data = resp.json()
        assert "transaction" in data
        txn = data["transaction"]
        assert txn["amount"] == 500.0
        assert txn["source"] == "manual"
        assert txn["status"] == "completed"
        # Verify net_amount calculated correctly
        assert txn["net_amount"] == 497.5  # 500.0 - 2.50
        TestAdminBankTransactions._created_txn_id = txn["id"]
        print(f"✓ Bank transaction created: {txn['id']}")
        return txn

    def test_update_bank_transaction(self, admin_headers):
        """Update a bank transaction"""
        txn = self.test_create_bank_transaction(admin_headers)
        txn_id = txn["id"]

        payload = {"status": "pending", "description": "TEST updated description"}
        resp = requests.put(f"{BASE_URL}/api/admin/bank-transactions/{txn_id}", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Update bank transaction failed: {resp.text}"
        data = resp.json()
        assert "transaction" in data
        assert data["transaction"]["status"] == "pending"
        print(f"✓ Bank transaction {txn_id} updated")

    def test_delete_bank_transaction(self, admin_headers):
        """Delete a bank transaction"""
        txn = self.test_create_bank_transaction(admin_headers)
        txn_id = txn["id"]

        resp = requests.delete(f"{BASE_URL}/api/admin/bank-transactions/{txn_id}", headers=admin_headers)
        assert resp.status_code == 200, f"Delete bank transaction failed: {resp.text}"
        data = resp.json()
        assert "message" in data
        print(f"✓ Bank transaction {txn_id} deleted")

    def test_get_bank_transaction_logs(self, admin_headers):
        """Get logs for a bank transaction"""
        txn = self.test_create_bank_transaction(admin_headers)
        txn_id = txn["id"]

        resp = requests.get(f"{BASE_URL}/api/admin/bank-transactions/{txn_id}/logs", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "logs" in data
        assert len(data["logs"]) > 0
        print(f"✓ Bank transaction logs: {len(data['logs'])} log entries")


# ─────────────────────────────────────────────
# Admin Override Codes
# ─────────────────────────────────────────────
class TestAdminOverrideCodes:
    """Admin: Override code management"""

    def test_list_override_codes(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/override-codes", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "override_codes" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert "total_pages" in data
        print(f"✓ Override codes: {data['total']} total")

    def test_create_override_code(self, admin_headers):
        """Create a new override code for a customer"""
        # Get a customer
        cust_resp = requests.get(f"{BASE_URL}/api/admin/customers?per_page=1", headers=admin_headers)
        customers = cust_resp.json().get("customers", [])
        if not customers:
            pytest.skip("No customers available")

        cust_id = customers[0]["id"]
        code_val = f"TEST{uuid.uuid4().hex[:8].upper()}"
        payload = {
            "code": code_val,
            "customer_id": cust_id
        }
        resp = requests.post(f"{BASE_URL}/api/admin/override-codes", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Create override code failed: {resp.text}"
        data = resp.json()
        assert "id" in data
        TestAdminOverrideCodes._created_code_id = data["id"]
        TestAdminOverrideCodes._created_code_val = code_val
        print(f"✓ Override code created: {code_val} (id={data['id']})")
        return data

    def test_update_override_code(self, admin_headers):
        """Update an override code"""
        create_data = self.test_create_override_code(admin_headers)
        code_id = create_data["id"]

        payload = {"status": "inactive"}
        resp = requests.put(f"{BASE_URL}/api/admin/override-codes/{code_id}", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Update override code failed: {resp.text}"
        data = resp.json()
        assert "override_code" in data or "message" in data
        print(f"✓ Override code {code_id} updated")

    def test_deactivate_override_code(self, admin_headers):
        """Deactivate an override code (DELETE endpoint)"""
        create_data = self.test_create_override_code(admin_headers)
        code_id = create_data["id"]

        resp = requests.delete(f"{BASE_URL}/api/admin/override-codes/{code_id}", headers=admin_headers)
        assert resp.status_code == 200, f"Deactivate override code failed: {resp.text}"
        data = resp.json()
        assert "message" in data
        print(f"✓ Override code {code_id} deactivated")


# ─────────────────────────────────────────────
# Admin Settings
# ─────────────────────────────────────────────
class TestAdminSettings:
    """Admin: Settings get/update"""

    def test_get_settings(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/settings", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "settings" in data
        print(f"✓ Admin settings retrieved: {list(data['settings'].keys())[:5]}")

    def test_update_settings(self, admin_headers):
        """Update non-sensitive settings"""
        payload = {"store_name": "TEST Automate Accounts Store"}
        resp = requests.put(f"{BASE_URL}/api/admin/settings", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Settings update failed: {resp.text}"
        data = resp.json()
        assert "message" in data
        print(f"✓ Settings updated")

    def test_get_structured_settings(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/settings/structured", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "settings" in data
        print(f"✓ Structured settings: {list(data['settings'].keys())}")


# ─────────────────────────────────────────────
# Admin Exports
# ─────────────────────────────────────────────
class TestAdminExports:
    """Admin: CSV exports"""

    def test_export_orders_csv(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/export/orders", headers=admin_headers)
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("Content-Type", "")
        content = resp.text
        assert len(content) > 0
        print(f"✓ Orders CSV export: {len(content)} chars")

    def test_export_customers_csv(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/export/customers", headers=admin_headers)
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("Content-Type", "")
        content = resp.text
        assert len(content) > 0
        print(f"✓ Customers CSV export: {len(content)} chars")

    def test_export_subscriptions_csv(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/export/subscriptions", headers=admin_headers)
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("Content-Type", "")
        print("✓ Subscriptions CSV export works")

    def test_export_catalog_csv(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/export/catalog", headers=admin_headers)
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("Content-Type", "")
        print("✓ Catalog CSV export works")

    def test_export_bank_transactions_csv(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/export/bank-transactions", headers=admin_headers)
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("Content-Type", "")
        print("✓ Bank transactions CSV export works")


# ─────────────────────────────────────────────
# Articles
# ─────────────────────────────────────────────
class TestArticles:
    """Articles: admin CRUD"""

    def test_list_articles_admin(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/articles/admin/list", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "articles" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert "total_pages" in data
        print(f"✓ Admin articles: {data['total']} total")

    def test_create_article(self, admin_headers):
        """Create an article"""
        payload = {
            "title": "TEST Article for Automated Tests",
            "category": "General",
            "content": "<p>TEST content for automated testing</p>",
            "visibility": "all",
            "restricted_to": []
        }
        resp = requests.post(f"{BASE_URL}/api/articles", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Create article failed: {resp.text}"
        data = resp.json()
        assert "article" in data
        article = data["article"]
        assert article["title"] == payload["title"]
        assert article["category"] == "General"
        assert "id" in article
        TestArticles._created_article_id = article["id"]
        print(f"✓ Article created: {article['id']}")
        return article

    def test_update_article(self, admin_headers):
        """Update an article"""
        article = self.test_create_article(admin_headers)
        article_id = article["id"]

        payload = {"title": "TEST Article UPDATED", "content": "<p>UPDATED content</p>"}
        resp = requests.put(f"{BASE_URL}/api/articles/{article_id}", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Update article failed: {resp.text}"
        data = resp.json()
        assert "article" in data
        assert data["article"]["title"] == "TEST Article UPDATED"
        print(f"✓ Article {article_id} updated")

    def test_delete_article(self, admin_headers):
        """Delete an article (soft delete)"""
        article = self.test_create_article(admin_headers)
        article_id = article["id"]

        resp = requests.delete(f"{BASE_URL}/api/articles/{article_id}", headers=admin_headers)
        assert resp.status_code == 200, f"Delete article failed: {resp.text}"
        data = resp.json()
        assert "message" in data
        print(f"✓ Article {article_id} deleted")


# ─────────────────────────────────────────────
# Admin Promo Codes
# ─────────────────────────────────────────────
class TestAdminPromoCodes:
    """Admin: Promo code listing"""

    def test_list_promo_codes(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/promo-codes", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "promo_codes" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert "total_pages" in data
        print(f"✓ Promo codes: {data['total']} total")

    def test_create_promo_code(self, admin_headers):
        """Create a promo code"""
        code = f"TEST{uuid.uuid4().hex[:6].upper()}"
        payload = {
            "code": code,
            "discount_type": "percent",
            "discount_value": 10.0,
            "applies_to": "both",
            "applies_to_products": "all",
            "product_ids": [],
            "one_time_code": False,
            "enabled": True
        }
        resp = requests.post(f"{BASE_URL}/api/admin/promo-codes", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Create promo code failed: {resp.text}"
        data = resp.json()
        assert "id" in data
        print(f"✓ Promo code created: {code}")
        return {"id": data["id"], "code": code}


# ─────────────────────────────────────────────
# Admin Terms
# ─────────────────────────────────────────────
class TestAdminTerms:
    """Admin: Terms & Conditions listing"""

    def test_list_terms(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/terms", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "terms" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert "total_pages" in data
        print(f"✓ Admin terms: {data['total']} total")
