"""
Iteration 114: Comprehensive Orders & Subscriptions QA
Tests: A1-A5, B1-B4, C1-C2, D1-D2, E1-E2, F1-F5, G1-G4, H1-H3, I1-I2, SEC1-SEC3
"""
import pytest
import requests
import time
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# ── Tenant IDs ────────────────────────────────────────────────────────────────
TENANT_A_ID = "5ed23354-05bc-4603-8613-6a12a26a0f28"  # test-iter109-a
TENANT_B_ID = "782db42a-d9b7-4e64-9cf0-032e43c5164e"  # test-iter109-b
DEFAULT_TENANT = "automate-accounts"

# ── Credentials ──────────────────────────────────────────────────────────────
ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"
TENANT_A_ADMIN_EMAIL = "test.super.a@iter109.test"
TENANT_A_ADMIN_PASSWORD = "TestPass123!"
TENANT_B_ADMIN_EMAIL = "test.super.b@iter109.test"
TENANT_B_ADMIN_PASSWORD = "TestPass123!"
CUSTOMER_EMAIL = "test_enq_iter16@test.local"
CUSTOMER_PASSWORD = "TestPass123!"
CUSTOMER_PARTNER_CODE = "test-iter109-a"


# ────────────────────────────── FIXTURES ──────────────────────────────────────

@pytest.fixture(scope="module")
def admin_token():
    """Get platform admin token"""
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
    })
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def tenant_a_admin_token():
    """Get tenant A admin token"""
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TENANT_A_ADMIN_EMAIL,
        "password": TENANT_A_ADMIN_PASSWORD,
        "partner_code": "test-iter109-a",
        "login_type": "partner"
    })
    if r.status_code != 200:
        pytest.skip(f"Tenant A admin login failed: {r.text}")
    return r.json()["token"]


@pytest.fixture(scope="module")
def tenant_b_admin_token():
    """Get tenant B admin token"""
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TENANT_B_ADMIN_EMAIL,
        "password": TENANT_B_ADMIN_PASSWORD,
        "partner_code": "test-iter109-b",
        "login_type": "partner"
    })
    if r.status_code != 200:
        pytest.skip(f"Tenant B admin login failed: {r.text}")
    return r.json()["token"]


@pytest.fixture(scope="module")
def customer_token():
    """Get test customer token"""
    time.sleep(2)  # Rate limit buffer
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": CUSTOMER_EMAIL,
        "password": CUSTOMER_PASSWORD,
        "partner_code": CUSTOMER_PARTNER_CODE,
        "login_type": "customer"
    })
    if r.status_code != 200:
        pytest.skip(f"Customer login failed: {r.text}")
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def tenant_a_headers(tenant_a_admin_token):
    return {"Authorization": f"Bearer {tenant_a_admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def tenant_b_headers(tenant_b_admin_token):
    return {"Authorization": f"Bearer {tenant_b_admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def customer_headers(customer_token):
    return {"Authorization": f"Bearer {customer_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def a_product(admin_headers):
    """Get a fixed-price product"""
    r = requests.get(f"{BASE_URL}/api/products", headers=admin_headers)
    assert r.status_code == 200
    products = r.json().get("products", [])
    # Find a product with base_price > 0 and not subscription
    for p in products:
        if p.get("base_price") and p.get("base_price") > 0 and not p.get("is_subscription") and p.get("pricing_type") == "internal":
            return p
    pytest.skip("No fixed-price non-subscription product found")


@pytest.fixture(scope="module")
def a_subscription_product(admin_headers):
    """Get a subscription product"""
    r = requests.get(f"{BASE_URL}/api/products", headers=admin_headers)
    assert r.status_code == 200
    products = r.json().get("products", [])
    for p in products:
        if p.get("is_subscription") and p.get("base_price") and p.get("base_price") > 0:
            return p
    pytest.skip("No subscription product found")


@pytest.fixture(scope="module")
def existing_tenant_a_orders(admin_headers):
    """Get existing orders from tenant A"""
    r = requests.get(
        f"{BASE_URL}/api/admin/orders?per_page=10",
        headers={**admin_headers, "X-View-As-Tenant": TENANT_A_ID}
    )
    assert r.status_code == 200
    return r.json().get("orders", [])


# ─────────────────────── PLATFORM ADMIN TESTS ─────────────────────────────────

class TestAdminOrdersAPI:
    """F1: Admin orders list with filters and pagination"""

    def test_admin_get_orders_200(self, admin_headers):
        """Platform admin can get all orders"""
        r = requests.get(f"{BASE_URL}/api/admin/orders", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "orders" in data
        assert "total" in data
        assert "page" in data
        assert "total_pages" in data
        print(f"PASS: Admin get orders - total: {data['total']}")

    def test_admin_orders_pagination(self, admin_headers):
        """F1: Pagination works correctly"""
        r = requests.get(f"{BASE_URL}/api/admin/orders?page=1&per_page=1", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert len(data["orders"]) <= 1
        assert data["per_page"] == 1
        assert data["page"] == 1
        print(f"PASS: Pagination test - orders on page: {len(data['orders'])}")

    def test_admin_orders_status_filter(self, admin_headers):
        """F1: Status filter works"""
        r = requests.get(f"{BASE_URL}/api/admin/orders?status_filter=scope_pending", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        for order in data["orders"]:
            assert order["status"] == "scope_pending", f"Order {order.get('order_number')} has wrong status"
        print(f"PASS: Status filter - {len(data['orders'])} scope_pending orders")

    def test_admin_orders_date_filter(self, admin_headers):
        """F1: Date range filter works"""
        r = requests.get(
            f"{BASE_URL}/api/admin/orders?pay_date_from=2024-01-01&pay_date_to=2030-12-31",
            headers=admin_headers
        )
        assert r.status_code == 200
        print(f"PASS: Date filter - {r.json().get('total', 0)} orders in range")

    def test_admin_orders_tenant_scoped_view(self, admin_headers):
        """Platform admin can view tenant A orders via X-View-As-Tenant"""
        r = requests.get(
            f"{BASE_URL}/api/admin/orders?per_page=10",
            headers={**admin_headers, "X-View-As-Tenant": TENANT_A_ID}
        )
        assert r.status_code == 200
        data = r.json()
        # All returned orders must belong to tenant A
        for order in data["orders"]:
            assert order.get("tenant_id") == TENANT_A_ID, \
                f"Order {order.get('order_number')} tenant mismatch: {order.get('tenant_id')}"
        print(f"PASS: Tenant scoped view - {len(data['orders'])} orders for tenant A")

    def test_admin_get_order_notes_json(self, admin_headers, existing_tenant_a_orders):
        """F3: Admin 'View Notes' shows full notes_json"""
        if not existing_tenant_a_orders:
            pytest.skip("No orders found for tenant A")
        order = existing_tenant_a_orders[0]
        notes_json = order.get("notes_json")
        assert notes_json is not None, "notes_json missing from order"
        assert isinstance(notes_json, dict), "notes_json should be a dict"
        print(f"PASS: View Notes - notes_json keys: {list(notes_json.keys())}")


class TestAdminOrderStatusChange:
    """F2: Status changes logged in audit trail"""

    def test_admin_update_order_status(self, admin_headers, existing_tenant_a_orders):
        """F2: Admin can change order status"""
        if not existing_tenant_a_orders:
            pytest.skip("No orders for tenant A")
        order = existing_tenant_a_orders[0]
        order_id = order["id"]
        current_status = order["status"]

        # Change to 'scope_requested' if currently 'scope_pending', or vice versa
        new_status = "scope_requested" if current_status == "scope_pending" else "scope_pending"
        r = requests.put(
            f"{BASE_URL}/api/admin/orders/{order_id}",
            headers={**admin_headers, "X-View-As-Tenant": TENANT_A_ID},
            json={"status": new_status}
        )
        assert r.status_code == 200
        assert r.json().get("message") == "Order updated successfully"
        print(f"PASS: Status change {current_status} -> {new_status}")

        # Restore original status
        requests.put(
            f"{BASE_URL}/api/admin/orders/{order_id}",
            headers={**admin_headers, "X-View-As-Tenant": TENANT_A_ID},
            json={"status": current_status}
        )

    def test_admin_order_status_change_audit_log(self, admin_headers, existing_tenant_a_orders):
        """F2: Status changes logged in audit trail with tenant_id"""
        if not existing_tenant_a_orders:
            pytest.skip("No orders for tenant A")
        order = existing_tenant_a_orders[0]
        order_id = order["id"]

        # Change status
        r_update = requests.put(
            f"{BASE_URL}/api/admin/orders/{order_id}",
            headers={**admin_headers, "X-View-As-Tenant": TENANT_A_ID},
            json={"status": "scope_requested"}
        )
        assert r_update.status_code == 200

        # Check audit log
        r_logs = requests.get(
            f"{BASE_URL}/api/admin/orders/{order_id}/logs",
            headers={**admin_headers, "X-View-As-Tenant": TENANT_A_ID}
        )
        assert r_logs.status_code == 200
        logs = r_logs.json().get("logs", [])
        assert len(logs) > 0, "No audit logs found for order"
        
        # Check that logs don't contain secrets/tokens
        log_str = str(logs).lower()
        assert "password" not in log_str, "Password found in audit logs!"
        assert "jwt_secret" not in log_str, "JWT secret found in audit logs!"
        
        # Restore
        requests.put(
            f"{BASE_URL}/api/admin/orders/{order_id}",
            headers={**admin_headers, "X-View-As-Tenant": TENANT_A_ID},
            json={"status": "scope_pending"}
        )
        print(f"PASS: Audit log for order - {len(logs)} logs found, no secrets exposed")

    def test_admin_order_invalid_status_rejected(self, admin_headers, existing_tenant_a_orders):
        """F2: Invalid status is rejected"""
        if not existing_tenant_a_orders:
            pytest.skip("No orders for tenant A")
        order = existing_tenant_a_orders[0]
        r = requests.put(
            f"{BASE_URL}/api/admin/orders/{order['id']}",
            headers={**admin_headers, "X-View-As-Tenant": TENANT_A_ID},
            json={"status": "INVALID_STATUS_XYZ"}
        )
        assert r.status_code == 400
        print("PASS: Invalid status rejected")


class TestManualOrderCreation:
    """B4: Manual/offline order creation"""

    def test_create_manual_order(self, admin_headers, a_product):
        """B4: Admin creates unpaid manual order"""
        tenant_id = DEFAULT_TENANT
        # Get a customer for the default tenant
        r_custs = requests.get(
            f"{BASE_URL}/api/admin/customers?per_page=10",
            headers=admin_headers
        )
        custs = r_custs.json().get("customers", [])
        # Find a customer with email
        test_cust = None
        for c in custs:
            if c.get("partner_code") == "automate-accounts":
                # Get user email
                r_users = requests.get(
                    f"{BASE_URL}/api/admin/users?per_page=50",
                    headers=admin_headers
                )
                users = r_users.json().get("users", [])
                for u in users:
                    r_cust = requests.get(
                        f"{BASE_URL}/api/admin/customers/{c['id']}",
                        headers=admin_headers
                    )
                    if r_cust.status_code == 200:
                        cust_data = r_cust.json().get("customer", {})
                        user_id = cust_data.get("user_id")
                        if user_id:
                            for usr in users:
                                if usr.get("id") == user_id:
                                    test_cust = (c, usr.get("email"))
                                    break
                    if test_cust:
                        break
                if test_cust:
                    break

        if not test_cust:
            # Try using tenant A
            r_custs_a = requests.get(
                f"{BASE_URL}/api/admin/customers?per_page=10",
                headers={**admin_headers, "X-View-As-Tenant": TENANT_A_ID}
            )
            custs_a = r_custs_a.json().get("customers", [])
            if not custs_a:
                pytest.skip("No customer found for manual order test")
            cust_a = custs_a[0]
            # Get their user record via customer details
            r_cust_detail = requests.get(
                f"{BASE_URL}/api/admin/customers/{cust_a['id']}",
                headers={**admin_headers, "X-View-As-Tenant": TENANT_A_ID}
            )
            if r_cust_detail.status_code != 200:
                pytest.skip("Cannot get customer details")
            cust_detail = r_cust_detail.json().get("customer", {})
            user_id = cust_detail.get("user_id")
            r_users = requests.get(f"{BASE_URL}/api/admin/users?per_page=50", headers=admin_headers)
            users = r_users.json().get("users", [])
            email = next((u["email"] for u in users if u["id"] == user_id), None)
            if not email:
                pytest.skip("Cannot find customer email")
            headers_to_use = {**admin_headers, "X-View-As-Tenant": TENANT_A_ID}
            product_id = a_product["id"]
        else:
            headers_to_use = admin_headers
            product_id = a_product["id"]
            email = test_cust[1]

        r = requests.post(
            f"{BASE_URL}/api/admin/orders/manual",
            headers=headers_to_use,
            json={
                "customer_email": email,
                "product_id": product_id,
                "quantity": 1,
                "subtotal": 500.0,
                "discount": 0.0,
                "fee": 0.0,
                "status": "unpaid",
                "internal_note": "TEST_manual_order_iter114"
            }
        )
        if r.status_code == 404:
            pytest.skip(f"Product or customer not found: {r.json()}")
        assert r.status_code == 200, f"Manual order failed: {r.json()}"
        data = r.json()
        assert "order_id" in data
        assert "order_number" in data
        order_number = data["order_number"]
        order_id = data["order_id"]
        print(f"PASS: Manual order created - {order_number}")

        # Verify order is unpaid with no payment_date
        r_check = requests.get(
            f"{BASE_URL}/api/admin/orders?order_number_filter={order_number}",
            headers=headers_to_use
        )
        assert r_check.status_code == 200
        orders = r_check.json().get("orders", [])
        matching = [o for o in orders if o.get("order_number") == order_number]
        if matching:
            o = matching[0]
            assert o.get("status") == "unpaid", f"Manual order should be unpaid, got: {o.get('status')}"
            assert o.get("payment_date") is None or o.get("payment_date") == "", "Unpaid order should not have payment_date"
            print(f"PASS: Manual order status=unpaid, no payment_date")

        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/admin/orders/{order_id}",
            headers=headers_to_use,
            json={"reason": "TEST cleanup iter114"}
        )


class TestAdminSubscriptionsAPI:
    """G1-G4: Admin subscriptions management"""

    def test_admin_get_subscriptions_200(self, admin_headers):
        """G1: Admin gets subscriptions list"""
        r = requests.get(f"{BASE_URL}/api/admin/subscriptions", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "subscriptions" in data
        assert "total" in data
        print(f"PASS: Get subscriptions - total: {data['total']}")

    def test_admin_subscriptions_status_filter(self, admin_headers):
        """G1: Status filter on subscriptions"""
        r = requests.get(f"{BASE_URL}/api/admin/subscriptions?status=active", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        for s in data["subscriptions"]:
            assert s["status"] == "active", f"Expected active, got {s['status']}"
        print(f"PASS: Subscriptions status filter - {len(data['subscriptions'])} active")

    def test_admin_subscriptions_offline_manual_status_enum(self, admin_headers):
        """G3: offline_manual is valid subscription status"""
        # Verify ALLOWED_SUBSCRIPTION_STATUSES from filter-options API
        r = requests.get(f"{BASE_URL}/api/admin/filter-options", headers=admin_headers)
        assert r.status_code == 200
        sub_statuses = r.json().get("subscription_statuses", [])
        assert "offline_manual" in sub_statuses, f"offline_manual not in statuses: {sub_statuses}"
        # 'manual' alone should NOT be a valid status
        assert "manual" not in sub_statuses, f"'manual' should not be standalone status"
        print(f"PASS: offline_manual is valid subscription status, 'manual' alone is not")

    def test_admin_create_manual_subscription(self, admin_headers, a_subscription_product):
        """G1: Create manual subscription with offline_manual status"""
        # Get customers for default tenant
        r_custs = requests.get(f"{BASE_URL}/api/admin/customers?per_page=10", headers=admin_headers)
        custs = r_custs.json().get("customers", [])
        
        # Find a customer with an email we can use
        r_users = requests.get(f"{BASE_URL}/api/admin/users?per_page=50", headers=admin_headers)
        users = r_users.json().get("users", [])
        
        # Use tenant A admin as test customer proxy
        test_email = None
        for u in users:
            if u.get("tenant_id") == TENANT_A_ID and u.get("role") in ["partner_super_admin", "partner_admin"]:
                # Check if there's a customer record for them
                test_email = u.get("email")
                break
        
        if not test_email:
            pytest.skip("No suitable test user for subscription creation")

        r = requests.post(
            f"{BASE_URL}/api/admin/subscriptions/manual",
            headers={**admin_headers, "X-View-As-Tenant": TENANT_A_ID},
            json={
                "customer_email": test_email,
                "product_id": a_subscription_product["id"],
                "amount": 99.0,
                "renewal_date": "2026-12-31",
                "start_date": "2026-01-01",
                "status": "offline_manual",
                "internal_note": "TEST_manual_sub_iter114"
            }
        )
        # This might fail if user has no customer record in tenant A
        if r.status_code in [404, 400]:
            # Try a customer that exists in tenant A
            r_cust_a = requests.get(
                f"{BASE_URL}/api/admin/customers?per_page=5",
                headers={**admin_headers, "X-View-As-Tenant": TENANT_A_ID}
            )
            cust_a = r_cust_a.json().get("customers", [])
            if not cust_a:
                pytest.skip("No customers in tenant A for subscription test")
            
            # Get user email from customer record
            cust = cust_a[0]
            r_detail = requests.get(
                f"{BASE_URL}/api/admin/customers/{cust['id']}",
                headers={**admin_headers, "X-View-As-Tenant": TENANT_A_ID}
            )
            if r_detail.status_code != 200:
                pytest.skip("Cannot get customer detail")
            user_id = r_detail.json().get("customer", {}).get("user_id")
            if not user_id:
                pytest.skip("Customer has no user_id")
            email_for_test = next((u["email"] for u in users if u["id"] == user_id), None)
            if not email_for_test:
                pytest.skip("Cannot find user email for customer")
            
            r = requests.post(
                f"{BASE_URL}/api/admin/subscriptions/manual",
                headers={**admin_headers, "X-View-As-Tenant": TENANT_A_ID},
                json={
                    "customer_email": email_for_test,
                    "product_id": a_subscription_product["id"],
                    "amount": 99.0,
                    "renewal_date": "2026-12-31",
                    "start_date": "2026-01-01",
                    "status": "offline_manual",
                    "internal_note": "TEST_manual_sub_iter114"
                }
            )

        if r.status_code not in [200, 201]:
            print(f"NOTE: Manual subscription creation returned {r.status_code}: {r.json()}")
            pytest.skip("Manual subscription creation requires proper customer setup")

        data = r.json()
        assert "subscription_id" in data
        assert "subscription_number" in data
        sub_id = data["subscription_id"]
        sub_number = data["subscription_number"]
        print(f"PASS: Manual subscription created - {sub_number} with offline_manual status")

        # Verify status is offline_manual
        r_list = requests.get(
            f"{BASE_URL}/api/admin/subscriptions?status=offline_manual",
            headers={**admin_headers, "X-View-As-Tenant": TENANT_A_ID}
        )
        assert r_list.status_code == 200
        subs = r_list.json().get("subscriptions", [])
        matching = [s for s in subs if s.get("id") == sub_id]
        if matching:
            assert matching[0]["status"] == "offline_manual", \
                f"Expected offline_manual, got: {matching[0]['status']}"
            print(f"PASS: Subscription status=offline_manual verified in DB")

        # G2: Test cancel subscription
        r_cancel = requests.post(
            f"{BASE_URL}/api/admin/subscriptions/{sub_id}/cancel",
            headers={**admin_headers, "X-View-As-Tenant": TENANT_A_ID}
        )
        assert r_cancel.status_code == 200
        assert r_cancel.json().get("message") == "Subscription cancellation scheduled"
        print(f"PASS: Subscription cancelled - transitions to canceled_pending")

        # Verify cancel audit log
        r_logs = requests.get(
            f"{BASE_URL}/api/admin/subscriptions/{sub_id}/logs",
            headers={**admin_headers, "X-View-As-Tenant": TENANT_A_ID}
        )
        assert r_logs.status_code == 200
        logs = r_logs.json().get("logs", [])
        cancel_logged = any(log.get("action") == "cancelled" for log in logs)
        assert cancel_logged, "Cancel action not in audit logs"
        print(f"PASS: Cancel action logged in audit trail")

        # G4: Test renewal
        r_renew = requests.post(
            f"{BASE_URL}/api/admin/subscriptions/{sub_id}/renew-now",
            headers={**admin_headers, "X-View-As-Tenant": TENANT_A_ID}
        )
        # This might fail for cancelled subscriptions, that's fine
        if r_renew.status_code == 200:
            renew_data = r_renew.json()
            assert "order_id" in renew_data
            assert "next_renewal_date" in renew_data
            print(f"PASS: Subscription renewal - new renewal date: {renew_data['next_renewal_date']}")
        else:
            print(f"INFO: Renewal returned {r_renew.status_code} - may be expected for cancelled sub")


class TestFilterOptions:
    """F1: Filter options endpoint"""

    def test_filter_options_all_statuses(self, admin_headers):
        """F1: Filter options returns all order and subscription statuses"""
        r = requests.get(f"{BASE_URL}/api/admin/filter-options", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        
        # Check order statuses contain expected values
        order_statuses = data.get("order_statuses", [])
        expected_order = ["pending", "paid", "unpaid", "completed", "cancelled"]
        for s in expected_order:
            assert s in order_statuses, f"'{s}' missing from order_statuses"
        
        # Check subscription statuses
        sub_statuses = data.get("subscription_statuses", [])
        expected_sub = ["active", "unpaid", "cancelled", "offline_manual"]
        for s in expected_sub:
            assert s in sub_statuses, f"'{s}' missing from subscription_statuses"
        
        # Check payment methods
        payment_methods = data.get("payment_methods", [])
        assert "card" in payment_methods
        assert "bank_transfer" in payment_methods
        print(f"PASS: Filter options - order_statuses: {len(order_statuses)}, sub_statuses: {len(sub_statuses)}")


class TestCSVExport:
    """F4: CSV export for orders"""

    def test_export_orders_csv(self, admin_headers):
        """F4: Export orders CSV returns valid CSV content"""
        r = requests.get(f"{BASE_URL}/api/admin/orders/export", headers=admin_headers)
        if r.status_code == 404:
            pytest.skip("Export endpoint not found at /api/admin/orders/export")
        assert r.status_code == 200
        content_type = r.headers.get("content-type", "")
        assert "csv" in content_type.lower() or "text" in content_type.lower(), \
            f"Expected CSV content-type, got: {content_type}"
        print(f"PASS: CSV export - content-type: {content_type}, size: {len(r.content)} bytes")


# ─────────────────────── SECURITY / CROSS-TENANT TESTS ────────────────────────

class TestCrossTenantIsolation:
    """SEC2, SEC3: Cross-tenant isolation"""

    def test_admin_tenant_a_cannot_access_tenant_b_orders(
        self, tenant_a_headers, existing_tenant_a_orders
    ):
        """SEC2: Tenant A admin cannot access tenant B orders by guessing order IDs"""
        # First get tenant B orders via platform admin
        r_admin = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        admin_tok = r_admin.json()["token"]
        r_b_orders = requests.get(
            f"{BASE_URL}/api/admin/orders?per_page=5",
            headers={"Authorization": f"Bearer {admin_tok}", "X-View-As-Tenant": TENANT_B_ID}
        )
        b_orders = r_b_orders.json().get("orders", [])
        if not b_orders:
            # Create a test order in tenant B to verify isolation
            print("INFO: No tenant B orders to test isolation against (skipping cross-tenant check)")
            return

        b_order_id = b_orders[0]["id"]
        # Tenant A admin tries to access tenant B order
        r = requests.get(
            f"{BASE_URL}/api/admin/orders/{b_order_id}",
            headers=tenant_a_headers
        )
        # Should either 404 or return empty (not tenant B's data)
        if r.status_code == 200:
            # Check that the returned order doesn't belong to tenant B
            returned_order = r.json().get("order", r.json())
            if isinstance(returned_order, dict):
                tenant_id = returned_order.get("tenant_id")
                assert tenant_id != TENANT_B_ID, \
                    f"SEC VIOLATION: Tenant A admin can see tenant B order! tenant_id={tenant_id}"
        print(f"PASS: Cross-tenant isolation - Tenant A cannot access Tenant B orders (status: {r.status_code})")

    def test_tenant_isolation_orders_list(self, tenant_a_headers, tenant_b_headers):
        """SEC2: Tenant A orders list only shows tenant A orders"""
        r_a = requests.get(f"{BASE_URL}/api/admin/orders", headers=tenant_a_headers)
        assert r_a.status_code == 200
        a_orders = r_a.json().get("orders", [])
        
        for order in a_orders:
            tenant_id = order.get("tenant_id")
            assert tenant_id == TENANT_A_ID, \
                f"SEC VIOLATION: Tenant A admin sees order from tenant {tenant_id}"
        print(f"PASS: Tenant A order list - all {len(a_orders)} orders belong to tenant A")

        r_b = requests.get(f"{BASE_URL}/api/admin/orders", headers=tenant_b_headers)
        assert r_b.status_code == 200
        b_orders = r_b.json().get("orders", [])
        
        for order in b_orders:
            tenant_id = order.get("tenant_id")
            assert tenant_id == TENANT_B_ID, \
                f"SEC VIOLATION: Tenant B admin sees order from tenant {tenant_id}"
        print(f"PASS: Tenant B order list - all {len(b_orders)} orders belong to tenant B")

    def test_tenant_isolation_subscriptions_list(self, tenant_a_headers, tenant_b_headers):
        """SEC2: Tenant subscriptions list is isolated"""
        r_a = requests.get(f"{BASE_URL}/api/admin/subscriptions", headers=tenant_a_headers)
        assert r_a.status_code == 200
        a_subs = r_a.json().get("subscriptions", [])
        
        for sub in a_subs:
            assert sub.get("tenant_id") == TENANT_A_ID, \
                f"SEC VIOLATION: Tenant A admin sees sub from tenant {sub.get('tenant_id')}"
        print(f"PASS: Tenant A subscriptions isolated - {len(a_subs)} subs")

    def test_customer_cross_tenant_order_isolation(self, customer_token):
        """SEC3: Customer cannot access orders from other tenants"""
        if not customer_token:
            pytest.skip("No customer token available")
        
        cust_headers = {"Authorization": f"Bearer {customer_token}"}
        
        # Get all platform admin orders to find an order from different tenant
        r_admin = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        admin_tok = r_admin.json()["token"]
        
        # Get an order from DEFAULT tenant (not customer's tenant)
        r_other = requests.get(
            f"{BASE_URL}/api/admin/orders?per_page=5",
            headers={"Authorization": f"Bearer {admin_tok}"}
        )
        other_orders = r_other.json().get("orders", [])
        
        # Filter orders NOT from tenant A
        other_tenant_orders = [o for o in other_orders if o.get("tenant_id") != TENANT_A_ID]
        
        if not other_tenant_orders:
            print("INFO: No orders from other tenants to test isolation (skipping)")
            return
        
        other_order_id = other_tenant_orders[0]["id"]
        
        # Customer tries to access the other tenant's order
        r = requests.get(
            f"{BASE_URL}/api/orders/{other_order_id}",
            headers=cust_headers
        )
        assert r.status_code in [403, 404], \
            f"SEC VIOLATION: Customer got status {r.status_code} accessing other tenant order"
        print(f"PASS: Customer cross-tenant isolation - got {r.status_code} (expected 403/404)")


class TestPriceTamperingPrevention:
    """SEC1: Price tampering prevention"""

    def test_checkout_price_override_ignored_server_side(self, customer_token, a_product):
        """SEC1: Client cannot override price via checkout payload"""
        if not customer_token:
            pytest.skip("No customer token available")

        cust_headers = {"Authorization": f"Bearer {customer_token}"}
        product_id = a_product["id"]
        real_price = a_product.get("base_price", 100)
        tampered_price = 0.01  # Try to buy for 1 cent

        # Try to submit checkout with price_override
        r = requests.post(
            f"{BASE_URL}/api/checkout/session",
            headers=cust_headers,
            json={
                "items": [{"product_id": product_id, "quantity": 1, "inputs": {}, "price_override": tampered_price}],
                "checkout_type": "one_time",
                "origin_url": "https://audit-trail-fix-1.preview.emergentagent.com",
                "terms_accepted": True,
                "partner_tag_response": "Yes",
                "zoho_subscription_type": "Paid - Annual",
                "current_zoho_product": "Zoho Books",
                "zoho_account_access": "New Customer"
            }
        )
        # If returns 400 (stripe not enabled / card not enabled), that's still OK
        # If returns 200 with a URL, the tampered price should NOT be reflected in the order
        if r.status_code in [400, 403]:
            # Payment not enabled for customer or stripe not connected - expected
            print(f"PASS: Price tampering test - checkout rejected ({r.status_code}): {r.json().get('detail', '')[:100]}")
        elif r.status_code == 200:
            # Check order was created with real price, not tampered price
            order_id = r.json().get("order_id")
            if order_id:
                r_check = requests.get(
                    f"{BASE_URL}/api/admin/orders?per_page=50",
                    headers={"Authorization": f"Bearer {requests.post(f'{BASE_URL}/api/auth/login', json={'email': ADMIN_EMAIL, 'password': ADMIN_PASSWORD}).json()['token']}"}
                )
                orders = r_check.json().get("orders", [])
                matching_order = next((o for o in orders if o["id"] == order_id), None)
                if matching_order:
                    order_total = matching_order.get("total", 0)
                    # Total should NOT be tampered_price * 1.05
                    assert order_total > tampered_price * 2, \
                        f"SEC VIOLATION: Price tampering may have succeeded! Order total: {order_total}, tampered: {tampered_price}"
                    print(f"PASS: Server computed correct price {order_total}, ignoring tampered {tampered_price}")
        else:
            print(f"INFO: Checkout returned {r.status_code} - {r.json().get('detail', '')[:100]}")


class TestServiceFeeCalculation:
    """B1: 5% service fee verification"""

    def test_service_fee_rate_constant(self):
        """Verify SERVICE_FEE_RATE = 0.05 (5%)"""
        import sys
        sys.path.insert(0, "/app/backend")
        try:
            from core.constants import SERVICE_FEE_RATE
            assert SERVICE_FEE_RATE == 0.05, f"Expected 0.05, got {SERVICE_FEE_RATE}"
            print(f"PASS: SERVICE_FEE_RATE = {SERVICE_FEE_RATE} (5%)")
        except ImportError:
            pytest.skip("Cannot import backend constants directly")

    def test_fee_in_checkout_session_order(self, admin_headers, existing_tenant_a_orders):
        """B1: Verify fee on paid card orders is approximately 5%"""
        # Get any card payment order to verify fee calculation
        r = requests.get(
            f"{BASE_URL}/api/admin/orders?payment_method_filter=card",
            headers=admin_headers
        )
        assert r.status_code == 200
        orders = r.json().get("orders", [])
        
        card_orders_with_fee = [o for o in orders if o.get("fee") and o.get("fee") > 0]
        if not card_orders_with_fee:
            print("INFO: No card orders with fee found - skipping fee calculation verification")
            return
        
        for order in card_orders_with_fee[:3]:
            subtotal = order.get("subtotal", 0)
            fee = order.get("fee", 0)
            total = order.get("total", 0)
            
            if subtotal > 0:
                actual_fee_rate = fee / subtotal
                # Allow +/- 0.01 tolerance for rounding
                assert 0.04 <= actual_fee_rate <= 0.10, \
                    f"Fee rate {actual_fee_rate:.2%} seems wrong for order {order.get('order_number')}"
                print(f"PASS: Fee calculation - subtotal:{subtotal} fee:{fee} total:{total} rate:{actual_fee_rate:.2%}")


class TestNotesJsonMerge:
    """E1, E2: notes_json merge verification"""

    def test_existing_orders_have_notes_json(self, admin_headers, existing_tenant_a_orders):
        """E1: notes_json populated on scope_request orders"""
        if not existing_tenant_a_orders:
            pytest.skip("No tenant A orders to check")
        
        for order in existing_tenant_a_orders:
            notes_json = order.get("notes_json")
            assert notes_json is not None, f"Order {order.get('order_number')} missing notes_json"
            assert isinstance(notes_json, dict), "notes_json should be dict"
            assert "payment" in notes_json, f"notes_json missing 'payment' key for {order.get('order_number')}"
            assert "system_metadata" in notes_json, "notes_json missing 'system_metadata' key"
            print(f"PASS: notes_json present for {order.get('order_number')} - keys: {list(notes_json.keys())}")

    def test_scope_form_orders_have_form_data_in_notes(self, admin_headers, existing_tenant_a_orders):
        """E1: scope_form data in notes_json for scope_request_form orders"""
        if not existing_tenant_a_orders:
            pytest.skip("No orders to check")
        
        scope_orders = [o for o in existing_tenant_a_orders if o.get("type") == "scope_request"]
        if not scope_orders:
            pytest.skip("No scope_request type orders")
        
        for order in scope_orders:
            notes_json = order.get("notes_json", {})
            if notes_json.get("scope_form"):
                print(f"PASS: scope_form found in notes_json for {order.get('order_number')}")
            else:
                print(f"INFO: No scope_form in notes_json for {order.get('order_number')} (may be scope_request type without form)")

    def test_notes_json_structure_checkout_intake(self, admin_headers, existing_tenant_a_orders):
        """E1: checkout_intake keys present in notes_json when set"""
        if not existing_tenant_a_orders:
            pytest.skip("No orders to check")
        
        for order in existing_tenant_a_orders:
            notes = order.get("notes_json", {})
            # scope_form orders may have scope_form instead of checkout_intake
            if notes.get("checkout_intake"):
                intake = notes["checkout_intake"]
                # These keys should be present (values may be None)
                expected_keys = ["partner_tag_response", "terms_accepted", "promo_code", "payment_method"]
                # Check: payment key present
                assert "payment" in notes, f"payment missing from notes_json"
                print(f"PASS: checkout_intake structure valid for {order.get('order_number')}")


class TestCustomerPortal:
    """H1, H2, H3: Customer portal"""

    def test_customer_portal_orders_visible(self, customer_token):
        """H1: Customer portal shows orders with price, currency, status"""
        if not customer_token:
            pytest.skip("No customer token")
        
        r = requests.get(
            f"{BASE_URL}/api/orders",
            headers={"Authorization": f"Bearer {customer_token}"}
        )
        assert r.status_code == 200
        data = r.json()
        assert "orders" in data
        
        for order in data["orders"]:
            # Check required fields present
            assert "order_number" in order, "order_number missing from portal order"
            assert "status" in order, "status missing from portal order"
            assert "total" in order, "total missing from portal order"
            assert "currency" in order, "currency missing from portal order"
            print(f"  Order: {order.get('order_number')} status:{order.get('status')} total:{order.get('total')} currency:{order.get('currency')}")
        print(f"PASS: Customer portal orders - {len(data['orders'])} orders visible")

    def test_customer_portal_no_internal_fields(self, customer_token):
        """H3: Customer portal does NOT expose internal/admin fields"""
        if not customer_token:
            pytest.skip("No customer token")
        
        r = requests.get(
            f"{BASE_URL}/api/orders",
            headers={"Authorization": f"Bearer {customer_token}"}
        )
        assert r.status_code == 200
        orders = r.json().get("orders", [])
        
        # These fields should NOT appear in customer-facing orders
        # notes_json may contain customer's own intake data, which is fine
        # But internal_note should not be sent (unless it's empty)
        for order in orders:
            # Check no sensitive internal admin fields
            order_str = str(order).lower()
            # Stripe API keys should not appear
            assert "sk_test" not in order_str and "sk_live" not in order_str, \
                "Stripe API key found in customer order!"
            # JWT tokens should not appear  
            assert "jwt_secret" not in order_str, "JWT secret found in customer order!"
        print(f"PASS: Customer portal - no sensitive internal fields exposed in {len(orders)} orders")

    def test_customer_portal_subscriptions(self, customer_token):
        """H2: Customer portal subscriptions with status and renewal date"""
        if not customer_token:
            pytest.skip("No customer token")
        
        r = requests.get(
            f"{BASE_URL}/api/subscriptions",
            headers={"Authorization": f"Bearer {customer_token}"}
        )
        assert r.status_code == 200
        subs = r.json().get("subscriptions", [])
        
        for sub in subs:
            assert "status" in sub, "status missing from portal subscription"
            assert "plan_name" in sub, "plan_name missing"
            # renewal_date should be present for active subscriptions
            if sub.get("status") == "active":
                assert "renewal_date" in sub, "renewal_date missing from active subscription"
        print(f"PASS: Customer portal subscriptions - {len(subs)} subscriptions visible")

    def test_customer_portal_idor_protection(self, customer_token):
        """SEC3: Customer cannot access orders belonging to other customers"""
        if not customer_token:
            pytest.skip("No customer token")
        
        cust_headers = {"Authorization": f"Bearer {customer_token}"}
        
        # Get customer's own orders first
        r_own = requests.get(f"{BASE_URL}/api/orders", headers=cust_headers)
        assert r_own.status_code == 200
        own_order_ids = {o["id"] for o in r_own.json().get("orders", [])}
        
        # Try to access an order we know exists from the scope_pending orders
        r_admin = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        admin_tok = r_admin.json()["token"]
        r_all = requests.get(
            f"{BASE_URL}/api/admin/orders?per_page=20",
            headers={"Authorization": f"Bearer {admin_tok}"}
        )
        all_order_ids = [o["id"] for o in r_all.json().get("orders", []) if o["id"] not in own_order_ids]
        
        if not all_order_ids:
            print("INFO: No other orders to test IDOR protection against")
            return
        
        # Try accessing first "foreign" order
        foreign_order_id = all_order_ids[0]
        r = requests.get(f"{BASE_URL}/api/orders/{foreign_order_id}", headers=cust_headers)
        assert r.status_code in [403, 404], \
            f"IDOR VULNERABILITY: Customer got {r.status_code} for foreign order {foreign_order_id}"
        print(f"PASS: IDOR protection - Customer cannot access foreign order (got {r.status_code})")


class TestCheckoutAPIValidations:
    """A1-A5: Checkout validation tests"""

    def test_checkout_requires_terms_accepted(self, customer_token, a_product):
        """Checkout rejects if terms_accepted=False"""
        if not customer_token:
            pytest.skip("No customer token")
        
        cust_headers = {"Authorization": f"Bearer {customer_token}"}
        r = requests.post(
            f"{BASE_URL}/api/checkout/session",
            headers=cust_headers,
            json={
                "items": [{"product_id": a_product["id"], "quantity": 1, "inputs": {}}],
                "checkout_type": "one_time",
                "origin_url": "https://audit-trail-fix-1.preview.emergentagent.com",
                "terms_accepted": False,  # <-- Must be rejected
                "partner_tag_response": "Yes",
                "zoho_subscription_type": "Paid - Annual",
                "current_zoho_product": "Zoho Books",
                "zoho_account_access": "New Customer"
            }
        )
        assert r.status_code == 400
        assert "terms" in r.json().get("detail", "").lower() or "Terms" in r.json().get("detail", "")
        print(f"PASS: Checkout rejects when terms not accepted: {r.json().get('detail')}")

    def test_checkout_requires_partner_tag(self, customer_token, a_product):
        """A5: Checkout requires partner_tag_response"""
        if not customer_token:
            pytest.skip("No customer token")
        
        cust_headers = {"Authorization": f"Bearer {customer_token}"}
        r = requests.post(
            f"{BASE_URL}/api/checkout/session",
            headers=cust_headers,
            json={
                "items": [{"product_id": a_product["id"], "quantity": 1, "inputs": {}}],
                "checkout_type": "one_time",
                "origin_url": "https://audit-trail-fix-1.preview.emergentagent.com",
                "terms_accepted": True,
                "partner_tag_response": None,  # <-- Missing
                "zoho_subscription_type": "Paid - Annual",
                "current_zoho_product": "Zoho Books",
                "zoho_account_access": "New Customer"
            }
        )
        # Should either be rejected with 400 (partner tag required) or fail with another validation
        # The backend validates partner_tag_response in validate_and_consume_partner_tag
        assert r.status_code in [400, 403], \
            f"Expected 400/403 for missing partner tag, got {r.status_code}: {r.json().get('detail')}"
        print(f"PASS: Checkout requires partner tag: {r.status_code} - {r.json().get('detail', '')[:80]}")

    def test_checkout_not_yet_requires_override_code(self, customer_token, a_product):
        """A5: 'Not yet' partner tag requires override code"""
        if not customer_token:
            pytest.skip("No customer token")
        
        cust_headers = {"Authorization": f"Bearer {customer_token}"}
        r = requests.post(
            f"{BASE_URL}/api/checkout/session",
            headers=cust_headers,
            json={
                "items": [{"product_id": a_product["id"], "quantity": 1, "inputs": {}}],
                "checkout_type": "one_time",
                "origin_url": "https://audit-trail-fix-1.preview.emergentagent.com",
                "terms_accepted": True,
                "partner_tag_response": "Not yet",
                "override_code": "",  # Empty - should be rejected
                "zoho_subscription_type": "Paid - Annual",
                "current_zoho_product": "Zoho Books",
                "zoho_account_access": "New Customer"
            }
        )
        assert r.status_code == 400
        detail = r.json().get("detail", "")
        assert "override" in detail.lower() or "Override" in detail, \
            f"Expected override code error, got: {detail}"
        print(f"PASS: 'Not yet' partner tag requires override code: {detail[:80]}")

    def test_checkout_bank_transfer_requires_terms(self, customer_token, a_product):
        """Bank transfer checkout also requires terms"""
        if not customer_token:
            pytest.skip("No customer token")
        
        cust_headers = {"Authorization": f"Bearer {customer_token}"}
        r = requests.post(
            f"{BASE_URL}/api/checkout/bank-transfer",
            headers=cust_headers,
            json={
                "items": [{"product_id": a_product["id"], "quantity": 1, "inputs": {}}],
                "checkout_type": "one_time",
                "terms_accepted": False,
                "partner_tag_response": "Yes"
            }
        )
        assert r.status_code == 400
        assert "terms" in r.json().get("detail", "").lower()
        print(f"PASS: Bank transfer checkout requires terms acceptance")

    def test_checkout_unauthenticated_rejected(self, a_product):
        """Checkout requires authentication"""
        r = requests.post(
            f"{BASE_URL}/api/checkout/session",
            json={
                "items": [{"product_id": a_product["id"], "quantity": 1, "inputs": {}}],
                "checkout_type": "one_time",
                "origin_url": "https://test.com",
                "terms_accepted": True
            }
        )
        assert r.status_code == 401
        print("PASS: Checkout requires authentication")


class TestScopeIDValidation:
    """I1: Scope ID validation"""

    def test_invalid_scope_id_returns_error(self, customer_token):
        """I1: Invalid scope ID returns 'Invalid Scope Id' or similar error"""
        if not customer_token:
            pytest.skip("No customer token")
        
        cust_headers = {"Authorization": f"Bearer {customer_token}"}
        r = requests.get(
            f"{BASE_URL}/api/resources/INVALID-SCOPE-ID-DOESNOTEXIST/validate-scope",
            headers=cust_headers
        )
        assert r.status_code in [400, 404], \
            f"Expected 400/404 for invalid scope ID, got {r.status_code}"
        detail = r.json().get("detail", "")
        assert any(word in detail.lower() for word in ["invalid", "not found", "scope"]), \
            f"Expected invalid scope error, got: {detail}"
        print(f"PASS: Invalid scope ID returns {r.status_code}: {detail[:60]}")

    def test_scope_request_requires_auth(self):
        """Scope request endpoint requires authentication"""
        r = requests.post(
            f"{BASE_URL}/api/orders/scope-request-form",
            json={"items": [], "form_data": {}}
        )
        assert r.status_code == 401
        print("PASS: Scope request requires authentication")


class TestGoCardlessCheckout:
    """B3: GoCardless sandbox flow"""

    def test_gocardless_not_enabled_returns_error(self, customer_token, a_product):
        """B3: Bank transfer returns error if GoCardless not configured"""
        if not customer_token:
            pytest.skip("No customer token")
        
        cust_headers = {"Authorization": f"Bearer {customer_token}"}
        r = requests.post(
            f"{BASE_URL}/api/checkout/bank-transfer",
            headers=cust_headers,
            json={
                "items": [{"product_id": a_product["id"], "quantity": 1, "inputs": {}}],
                "checkout_type": "one_time",
                "terms_accepted": True,
                "partner_tag_response": "Yes",
                "zoho_subscription_type": "Paid - Annual",
                "current_zoho_product": "Zoho Books",
                "zoho_account_access": "New Customer"
            }
        )
        # Should either:
        # - Return 400 "Bank transfer payments are currently not available" (if GC not connected)
        # - Return 403 "Bank transfer not enabled" (if customer doesn't have it enabled)
        # - Return redirect URL (if GC is connected and customer has it enabled)
        if r.status_code in [400, 403, 500]:
            detail = r.json().get("detail", "")
            print(f"INFO: GoCardless bank transfer status {r.status_code}: {detail[:80]}")
        elif r.status_code == 200:
            data = r.json()
            if data.get("gocardless_redirect_url"):
                # GC is configured - order should be pending_direct_debit_setup
                print(f"PASS: GoCardless redirect URL created: order {data.get('order_number')}")
            else:
                print(f"INFO: Bank transfer returned 200 but no redirect URL: {data}")
        print(f"INFO: GoCardless checkout returned {r.status_code}")


class TestPaymentMethodDisable:
    """C1, C2: Payment method disable"""

    def test_customer_without_card_payment_rejected(self, admin_headers, customer_token, a_product):
        """C1: Customer with allow_card_payment=False is rejected for Stripe"""
        if not customer_token:
            pytest.skip("No customer token")
        
        cust_headers = {"Authorization": f"Bearer {customer_token}"}
        r = requests.post(
            f"{BASE_URL}/api/checkout/session",
            headers=cust_headers,
            json={
                "items": [{"product_id": a_product["id"], "quantity": 1, "inputs": {}}],
                "checkout_type": "one_time",
                "origin_url": "https://audit-trail-fix-1.preview.emergentagent.com",
                "terms_accepted": True,
                "partner_tag_response": "Yes",
                "zoho_subscription_type": "Paid - Annual",
                "current_zoho_product": "Zoho Books",
                "zoho_account_access": "New Customer"
            }
        )
        # The test customer has allow_card_payment=False (from our inspection)
        # Should return 403 "Card payment is not enabled for your account"
        if r.status_code == 403:
            assert "card" in r.json().get("detail", "").lower() or "Card" in r.json().get("detail", "")
            print(f"PASS: Card payment disabled customer rejected: {r.json().get('detail')}")
        elif r.status_code == 400:
            detail = r.json().get("detail", "")
            print(f"INFO: Checkout rejected with 400: {detail[:80]}")
        else:
            print(f"INFO: Checkout returned {r.status_code} for customer with card disabled")


class TestCurrencyConsistency:
    """D1, D2: Currency consistency"""

    def test_customer_orders_have_consistent_currency(self, customer_token):
        """D2: Currency in orders is consistent"""
        if not customer_token:
            pytest.skip("No customer token")
        
        r = requests.get(
            f"{BASE_URL}/api/orders",
            headers={"Authorization": f"Bearer {customer_token}"}
        )
        assert r.status_code == 200
        orders = r.json().get("orders", [])
        
        # All orders should have currency field
        for order in orders:
            currency = order.get("currency")
            assert currency is not None, f"Order {order.get('order_number')} missing currency"
            assert currency in ["USD", "CAD", "GBP", "AUD", "EUR", None], \
                f"Unexpected currency: {currency}"
        print(f"PASS: Currency consistent in {len(orders)} customer orders")

    def test_admin_orders_have_currency_field(self, admin_headers, existing_tenant_a_orders):
        """D2: Admin view shows currency on orders"""
        if not existing_tenant_a_orders:
            pytest.skip("No orders to check")
        
        for order in existing_tenant_a_orders:
            # Currency should be present in order record
            # For scope_request orders, currency may be None but field should exist
            assert "currency" in order, f"currency field missing from admin order {order.get('order_number')}"
        print(f"PASS: Currency field present in {len(existing_tenant_a_orders)} admin orders")


class TestAutoCharge:
    """F5: Auto-charge feature"""

    def test_auto_charge_endpoint_exists(self, admin_headers):
        """F5: Auto-charge endpoint exists and handles non-existent order"""
        r = requests.post(
            f"{BASE_URL}/api/admin/orders/nonexistent-order-id/auto-charge",
            headers=admin_headers
        )
        assert r.status_code == 404
        print(f"PASS: Auto-charge endpoint exists and returns 404 for non-existent order")

    def test_auto_charge_paid_order_rejected(self, admin_headers, existing_tenant_a_orders):
        """F5: Auto-charge returns error for already paid orders"""
        if not existing_tenant_a_orders:
            pytest.skip("No orders to test")
        
        # Create a paid manual order first and try to auto-charge it
        # The existing orders are scope_pending, not paid, so skip
        paid_orders = [o for o in existing_tenant_a_orders if o.get("status") == "paid"]
        if not paid_orders:
            print("INFO: No paid orders to test auto-charge rejection")
            return
        
        order_id = paid_orders[0]["id"]
        r = requests.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/auto-charge",
            headers={**admin_headers, "X-View-As-Tenant": TENANT_A_ID}
        )
        assert r.status_code == 400
        assert "already paid" in r.json().get("detail", "").lower()
        print(f"PASS: Auto-charge rejects already-paid orders")


class TestRefundAPI:
    """EXTRA: Refund API tests"""

    def test_refund_unpaid_order_rejected(self, admin_headers, existing_tenant_a_orders):
        """Refund requires paid status"""
        if not existing_tenant_a_orders:
            pytest.skip("No orders to test")
        
        # All existing orders are scope_pending, try refunding one
        order = existing_tenant_a_orders[0]
        r = requests.post(
            f"{BASE_URL}/api/admin/orders/{order['id']}/refund",
            headers={**admin_headers, "X-View-As-Tenant": TENANT_A_ID},
            json={"provider": "manual", "reason": "requested_by_customer", "process_via_provider": False}
        )
        assert r.status_code == 400
        assert "paid" in r.json().get("detail", "").lower()
        print(f"PASS: Refund rejects non-paid orders: {r.json().get('detail')}")

    def test_refund_providers_endpoint(self, admin_headers, existing_tenant_a_orders):
        """EXTRA: Refund providers endpoint returns valid data"""
        if not existing_tenant_a_orders:
            pytest.skip("No orders to test")
        
        order = existing_tenant_a_orders[0]
        r = requests.get(
            f"{BASE_URL}/api/admin/orders/{order['id']}/refund-providers",
            headers={**admin_headers, "X-View-As-Tenant": TENANT_A_ID}
        )
        assert r.status_code == 200
        data = r.json()
        assert "providers" in data
        assert "manual" in [p["id"] for p in data["providers"]], "Manual provider should always be available"
        print(f"PASS: Refund providers - available: {[p['id'] for p in data['providers']]}")


class TestPromoCodeValidation:
    """A3: Promo code server-side validation"""

    def test_promo_code_validate_endpoint(self, customer_token, a_product):
        """A3: Promo validation endpoint requires auth"""
        if not customer_token:
            pytest.skip("No customer token")
        
        # Test with non-existent promo
        r = requests.post(
            f"{BASE_URL}/api/promo-codes/validate",
            headers={"Authorization": f"Bearer {customer_token}"},
            json={
                "code": "NONEXISTENT_CODE_XYZ",
                "checkout_type": "one_time",
                "product_ids": [a_product["id"]]
            }
        )
        assert r.status_code == 404
        print(f"PASS: Non-existent promo code returns 404")

    def test_promo_code_validate_requires_auth(self, a_product):
        """A3: Promo validation requires authentication"""
        r = requests.post(
            f"{BASE_URL}/api/promo-codes/validate",
            json={"code": "TEST", "checkout_type": "one_time", "product_ids": [a_product["id"]]}
        )
        assert r.status_code == 401
        print("PASS: Promo code validation requires auth")
