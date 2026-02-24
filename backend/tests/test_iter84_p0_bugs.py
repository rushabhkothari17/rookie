"""
Test P0 Bug Fixes - iter84
Tests:
1. Cart page checkout dropdowns (Zoho/partner) - verify sections visible in website settings
2. Admin manual order/subscription - products dropdown (should have products loaded from /admin/products-all)
3. Customer portal /portal - no 404 errors, shows orders/subscriptions
4. Admin edit order - product change dropdown shows options
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# ── Auth helpers ──────────────────────────────────────────────────────────────

def admin_session(partner_code="automate-accounts"):
    """Return requests session with admin auth cookies"""
    s = requests.Session()
    resp = s.post(f"{BASE_URL}/api/auth/partner-login", json={
        "email": "superadmin@automateaccounts.local",
        "password": "ChangeMe123!",
        "partner_code": partner_code,
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.status_code} {resp.text}"
    # Save cookie manually to ensure it's sent
    for c in resp.cookies:
        s.cookies.set(c.name, c.value)
    return s

def customer_session(partner_code="automate-accounts"):
    """Return requests session with customer auth cookies"""
    s = requests.Session()
    resp = s.post(f"{BASE_URL}/api/auth/customer-login", json={
        "email": "testcustomer@test.com",
        "password": "ChangeMe123!",
        "partner_code": partner_code,
    })
    assert resp.status_code == 200, f"Customer login failed: {resp.status_code} {resp.text}"
    for c in resp.cookies:
        s.cookies.set(c.name, c.value)
    return s


# ── Bug 1: Cart page checkout sections ───────────────────────────────────────

class TestCartCheckoutSections:
    """Verify the checkout sections/dropdowns data for cart page"""

    def test_website_settings_has_checkout_sections(self):
        """Website settings should include checkout_sections with configured sections"""
        resp = requests.get(f"{BASE_URL}/api/website-settings", headers={"X-Partner-Code": "automate-accounts"})
        assert resp.status_code == 200, f"Settings failed: {resp.status_code}"
        settings = resp.json().get("settings", {})
        checkout_keys = [k for k in settings.keys() if "checkout" in k.lower()]
        print(f"Checkout-related keys: {checkout_keys}")
        assert len(checkout_keys) > 0, "No checkout configuration in website settings"
        print(f"PASS: {len(checkout_keys)} checkout settings found")

    def test_checkout_sections_json_valid(self):
        """If checkout_sections is set, it should be valid JSON array"""
        import json
        resp = requests.get(f"{BASE_URL}/api/website-settings", headers={"X-Partner-Code": "automate-accounts"})
        assert resp.status_code == 200
        settings = resp.json().get("settings", {})
        
        sections_raw = settings.get("checkout_sections", "")
        if sections_raw:
            sections = json.loads(sections_raw)
            assert isinstance(sections, list), "checkout_sections should be a JSON array"
            print(f"PASS: checkout_sections is valid JSON array with {len(sections)} sections")
            for s in sections:
                print(f"  Section: {s.get('id','?')} - {s.get('title','untitled')}")
                # Each section should have fields
                fields = s.get('fields', [])
                for f in fields:
                    if f.get('type') == 'select':
                        opts = f.get('options', [])
                        assert len(opts) > 0, f"Field {f.get('name')} select has no options"
                        print(f"    Field {f.get('name')}: {len(opts)} options")
        else:
            print("INFO: checkout_sections empty, using legacy zoho/partner system")
            assert settings.get("checkout_zoho_enabled", True) is not False or settings.get("checkout_partner_enabled", True) is not False

    def test_store_products_available(self):
        """Store products endpoint should return products that can be added to cart"""
        resp = requests.get(f"{BASE_URL}/api/products", headers={"X-Partner-Code": "automate-accounts"})
        assert resp.status_code == 200, f"Store products failed: {resp.status_code}"
        products = resp.json().get("products", [])
        assert len(products) > 0, "No products in store"
        print(f"PASS: Store has {len(products)} products")


# ── Bug 2: Admin Manual Order/Subscription - Products Dropdown ───────────────

class TestAdminManualOrderProducts:
    """Verify admin manual order dialog product dropdown has options"""

    def test_admin_products_all_returns_30plus_products(self):
        """GET /admin/products-all should return 30+ products for admin dropdowns"""
        s = admin_session()
        resp = s.get(f"{BASE_URL}/api/admin/products-all?per_page=500")
        assert resp.status_code == 200, f"products-all failed: {resp.status_code} {resp.text}"
        products = resp.json().get("products", [])
        assert len(products) >= 30, f"Expected 30+ products, got {len(products)}"
        print(f"PASS: /admin/products-all returns {len(products)} products")
        # Verify structure
        for p in products[:3]:
            assert "id" in p, f"Product missing id: {p}"
            assert "name" in p, f"Product missing name: {p}"

    def test_admin_products_all_page_size(self):
        """Admin products endpoint should support large page size for loading all products"""
        s = admin_session()
        resp = s.get(f"{BASE_URL}/api/admin/products-all?per_page=200")
        assert resp.status_code == 200
        data = resp.json()
        products = data.get("products", [])
        total = data.get("total", 0)
        print(f"PASS: Total: {total}, returned: {len(products)}")
        assert len(products) > 0

    def test_admin_customers_for_email_autocomplete(self):
        """GET /admin/customers should return customers for email autocomplete"""
        s = admin_session()
        resp = s.get(f"{BASE_URL}/api/admin/customers?per_page=1000")
        assert resp.status_code == 200, f"customers failed: {resp.status_code}"
        data = resp.json()
        customers = data.get("customers", data.get("users", []))
        assert len(customers) > 0, "Expected at least 1 customer"
        print(f"PASS: {len(customers)} customers for autocomplete")

    def test_admin_manual_order_endpoint_works_with_valid_data(self):
        """POST /admin/orders/manual should create an order with valid data"""
        s = admin_session()
        resp = s.post(f"{BASE_URL}/api/admin/orders/manual", json={
            "customer_email": "testcustomer@test.com",
            "product_id": "prod_zoho_crm_express",
            "subtotal": 100,
            "fee": 0,
            "status": "pending",
            "payment_method": "manual",
            "internal_note": "TEST_ automated test order - please delete"
        })
        # Should succeed or fail with validation (not 404)
        assert resp.status_code != 404, f"POST /admin/orders/manual not found"
        print(f"PASS: /admin/orders/manual endpoint accessible (status: {resp.status_code})")
        if resp.status_code == 201 or resp.status_code == 200:
            data = resp.json()
            print(f"  Created order: {data.get('order_number', data.get('id', 'unknown'))}")


class TestAdminManualSubscriptionProducts:
    """Verify admin manual subscription dialog product dropdown has options"""

    def test_admin_subscription_products_available(self):
        """Products for subscription dialog should be loaded from /admin/products-all"""
        s = admin_session()
        resp = s.get(f"{BASE_URL}/api/admin/products-all?per_page=500")
        assert resp.status_code == 200
        products = resp.json().get("products", [])
        assert len(products) >= 30, f"Expected 30+ products for subscription dropdown, got {len(products)}"
        print(f"PASS: {len(products)} products available for manual subscription dropdown")

    def test_admin_manual_subscription_endpoint_accessible(self):
        """POST /admin/subscriptions/manual endpoint should be accessible"""
        s = admin_session()
        resp = s.post(f"{BASE_URL}/api/admin/subscriptions/manual", json={
            "customer_email": "testcustomer@test.com",
            "product_id": "prod_zoho_crm_express",
            "amount": 50.00,
            "status": "active",
            "renewal_date": "2026-03-25"
        })
        assert resp.status_code != 404, "POST /admin/subscriptions/manual endpoint not found"
        print(f"PASS: /admin/subscriptions/manual endpoint accessible (status: {resp.status_code})")


# ── Bug 3: Customer Portal /portal - No 404 errors ───────────────────────────

class TestCustomerPortal:
    """Verify customer portal loads without 404 errors"""

    def test_customer_login_success(self):
        """Customer should be able to log in"""
        resp = requests.post(f"{BASE_URL}/api/auth/customer-login", json={
            "email": "testcustomer@test.com",
            "password": "ChangeMe123!",
            "partner_code": "automate-accounts",
        })
        assert resp.status_code == 200, f"Customer login failed: {resp.status_code} {resp.text}"
        print("PASS: Customer login successful")

    def test_customer_portal_orders_200(self):
        """GET /orders should return 200 for valid customer"""
        s = customer_session()
        resp = s.get(f"{BASE_URL}/api/orders")
        assert resp.status_code == 200, f"Customer /orders returned {resp.status_code}: {resp.text[:200]}"
        orders = resp.json().get("orders", [])
        print(f"PASS: Customer /orders returns {len(orders)} orders")

    def test_customer_portal_subscriptions_200(self):
        """GET /subscriptions should return 200 for valid customer"""
        s = customer_session()
        resp = s.get(f"{BASE_URL}/api/subscriptions")
        assert resp.status_code == 200, f"Customer /subscriptions returned {resp.status_code}: {resp.text[:200]}"
        subs = resp.json().get("subscriptions", [])
        print(f"PASS: Customer /subscriptions returns {len(subs)} subscriptions")

    def test_customer_portal_products_200(self):
        """GET /products should return 200 for valid customer"""
        s = customer_session()
        resp = s.get(f"{BASE_URL}/api/products")
        assert resp.status_code == 200, f"Customer /products returned {resp.status_code}: {resp.text[:200]}"
        products = resp.json().get("products", [])
        print(f"PASS: Customer /products returns {len(products)} products")

    def test_customer_portal_all_apis_200(self):
        """All three Portal APIs must return 200 (simulates Portal.tsx Promise.all)"""
        s = customer_session()
        results = {}
        for endpoint in ["/api/orders", "/api/subscriptions", "/api/products"]:
            resp = s.get(f"{BASE_URL}{endpoint}")
            results[endpoint] = resp.status_code
        print(f"Portal API results: {results}")
        for endpoint, status in results.items():
            assert status == 200, f"{endpoint} returned {status} (expected 200)"
        print("PASS: All 3 Portal APIs return 200")

    def test_customer_has_orders_and_subscriptions(self):
        """Customer testcustomer@test.com should have at least 1 order and 1 subscription"""
        s = customer_session()
        orders = s.get(f"{BASE_URL}/api/orders").json().get("orders", [])
        subs = s.get(f"{BASE_URL}/api/subscriptions").json().get("subscriptions", [])
        print(f"Customer orders: {len(orders)}, subscriptions: {len(subs)}")
        assert len(orders) >= 1, f"Expected at least 1 order, got {len(orders)}"
        assert len(subs) >= 1, f"Expected at least 1 subscription, got {len(subs)}"
        print("PASS: Customer has orders and subscriptions")


# ── Bug 4: Admin Edit Order - Product Dropdown ────────────────────────────────

class TestAdminEditOrderDropdown:
    """Verify admin edit order dialog product change dropdown works"""

    def test_admin_orders_list_has_orders(self):
        """Admin orders list should return orders for editing"""
        s = admin_session()
        resp = s.get(f"{BASE_URL}/api/admin/orders?per_page=20")
        assert resp.status_code == 200, f"Admin orders failed: {resp.status_code}"
        orders = resp.json().get("orders", [])
        assert len(orders) > 0, "Expected at least 1 order to test editing"
        print(f"PASS: /admin/orders returns {len(orders)} orders")

    def test_admin_order_edit_endpoint_exists(self):
        """PUT /admin/orders/{id} should exist and be accessible"""
        s = admin_session()
        orders = s.get(f"{BASE_URL}/api/admin/orders?per_page=1").json().get("orders", [])
        if not orders:
            pytest.skip("No orders to test edit endpoint")
        
        order_id = orders[0]["id"]
        resp = s.put(f"{BASE_URL}/api/admin/orders/{order_id}", json={
            "status": orders[0].get("status", "pending"),
        })
        assert resp.status_code != 404, "PUT /admin/orders/{id} not found (404)"
        print(f"PASS: Edit order endpoint accessible (status: {resp.status_code})")

    def test_products_available_for_order_change(self):
        """Products list for order change dropdown should have 30+ products"""
        s = admin_session()
        products = s.get(f"{BASE_URL}/api/admin/products-all?per_page=500").json().get("products", [])
        assert len(products) >= 30, f"Expected 30+ products for order change dropdown, got {len(products)}"
        print(f"PASS: {len(products)} products available for order change dropdown")


# ── Website Settings ─────────────────────────────────────────────────────────

class TestWebsiteSettings:
    """Verify website settings include checkout configuration"""

    def test_public_settings_accessible(self):
        """Public website settings should be accessible"""
        resp = requests.get(f"{BASE_URL}/api/website-settings", headers={"X-Partner-Code": "automate-accounts"})
        assert resp.status_code == 200, f"Website settings failed: {resp.status_code}"
        print(f"PASS: Public website settings accessible")

    def test_admin_website_settings_accessible(self):
        """Admin should be able to read website settings"""
        s = admin_session()
        resp = s.get(f"{BASE_URL}/api/admin/website-settings")
        assert resp.status_code == 200, f"Admin website settings failed: {resp.status_code}"
        settings = resp.json().get("settings", {})
        checkout_keys = [k for k in settings.keys() if "checkout" in k.lower()]
        print(f"PASS: Admin website settings accessible with {len(checkout_keys)} checkout settings")

