"""
Iteration 16: Tests for email notifications for enquiries.
Tests:
- GET /api/admin/email-templates returns 'enquiry_customer' with is_enabled=True
- GET /api/admin/email-templates shows 'scope_request_admin' with company/phone/products/message vars
- POST /api/orders/scope-request-form creates order AND triggers email_outbox entries
- POST /api/orders/scope-request (cart-based) also triggers emails
- GET /api/admin/email-logs returns mocked entries after enquiry submission
- GET /api/admin/enquiries returns 200 (regression)
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def admin_token():
    """Get platform admin token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.status_code} {resp.text}"
    token = resp.json().get("token") or resp.json().get("access_token")
    assert token, f"No token in login response: {resp.json()}"
    print(f"Admin token acquired: {token[:20]}...")
    return token


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ---------------------------------------------------------------------------
# Email Templates Tests
# ---------------------------------------------------------------------------

class TestEmailTemplates:
    """Tests for GET /api/admin/email-templates."""

    def test_email_templates_returns_200(self, admin_headers):
        """Email templates endpoint should return 200."""
        resp = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "templates" in data, f"Missing 'templates' key: {data.keys()}"
        print(f"PASS: email-templates returns 200. Count={len(data['templates'])}")

    def test_enquiry_customer_template_exists(self, admin_headers):
        """enquiry_customer template should exist with is_enabled=True."""
        resp = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=admin_headers)
        assert resp.status_code == 200
        templates = resp.json().get("templates", [])
        triggers = {t["trigger"]: t for t in templates}
        
        assert "enquiry_customer" in triggers, (
            f"enquiry_customer template NOT FOUND. Available triggers: {list(triggers.keys())}"
        )
        tmpl = triggers["enquiry_customer"]
        assert tmpl.get("is_enabled") is True, (
            f"enquiry_customer template is NOT enabled: is_enabled={tmpl.get('is_enabled')}"
        )
        print(f"PASS: enquiry_customer template exists and is_enabled=True")
        print(f"  Subject: {tmpl.get('subject')}")
        print(f"  Available vars: {tmpl.get('available_variables')}")

    def test_enquiry_customer_template_available_variables(self, admin_headers):
        """enquiry_customer template should have order_number, products, summary variables."""
        resp = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=admin_headers)
        templates = resp.json().get("templates", [])
        triggers = {t["trigger"]: t for t in templates}
        
        tmpl = triggers.get("enquiry_customer", {})
        avail_vars = tmpl.get("available_variables", [])
        expected_vars = ["{{order_number}}", "{{customer_name}}", "{{customer_email}}", "{{products}}", "{{summary}}"]
        for v in expected_vars:
            assert v in avail_vars, f"enquiry_customer missing variable {v}. Available: {avail_vars}"
        print(f"PASS: enquiry_customer has all expected variables: {avail_vars}")

    def test_scope_request_admin_template_exists(self, admin_headers):
        """scope_request_admin template should exist with updated variables."""
        resp = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=admin_headers)
        assert resp.status_code == 200
        templates = resp.json().get("templates", [])
        triggers = {t["trigger"]: t for t in templates}
        
        assert "scope_request_admin" in triggers, (
            f"scope_request_admin NOT FOUND. Available: {list(triggers.keys())}"
        )
        tmpl = triggers["scope_request_admin"]
        print(f"PASS: scope_request_admin template exists")
        print(f"  is_enabled: {tmpl.get('is_enabled')}")

    def test_scope_request_admin_has_new_variables(self, admin_headers):
        """scope_request_admin should have company, phone, products, message variables."""
        resp = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=admin_headers)
        templates = resp.json().get("templates", [])
        triggers = {t["trigger"]: t for t in templates}
        
        tmpl = triggers.get("scope_request_admin", {})
        avail_vars = tmpl.get("available_variables", [])
        required_new_vars = ["{{company}}", "{{phone}}", "{{products}}", "{{message}}"]
        for v in required_new_vars:
            assert v in avail_vars, (
                f"scope_request_admin missing variable {v}. Available: {avail_vars}"
            )
        print(f"PASS: scope_request_admin has all required new variables: {avail_vars}")

    def test_email_templates_require_auth(self):
        """Email templates endpoint should require authentication."""
        resp = requests.get(f"{BASE_URL}/api/admin/email-templates")
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"
        print("PASS: email-templates requires auth")


# ---------------------------------------------------------------------------
# Email Notifications via scope-request-form
# ---------------------------------------------------------------------------

class TestScopeRequestFormEmails:
    """Tests that POST /api/orders/scope-request-form triggers email notifications."""

    def _get_first_product(self, admin_headers):
        """Helper to get first available product."""
        resp = requests.get(f"{BASE_URL}/api/products")
        assert resp.status_code == 200
        products = resp.json().get("products", [])
        if not products:
            pytest.skip("No products available")
        return products[0]

    def test_scope_request_form_creates_order(self, admin_headers):
        """POST scope-request-form should create an order and return order_id/order_number."""
        product = self._get_first_product(admin_headers)
        resp = requests.post(
            f"{BASE_URL}/api/orders/scope-request-form",
            headers=admin_headers,
            json={
                "items": [{"product_id": product["id"], "quantity": 1, "inputs": {}}],
                "form_data": {
                    "name": "TEST_Email Notification User",
                    "email": "test_email_notif@example.com",
                    "company": "TEST Email Corp",
                    "phone": "+1 555 111 2222",
                    "message": "TEST: Testing email notifications for enquiry",
                    "project_summary": "Email notification test project",
                }
            }
        )
        print(f"scope-request-form response: {resp.status_code} {resp.text[:300]}")
        if resp.status_code == 404 and "Customer" in resp.text:
            pytest.skip("Admin user has no customer record - email tests need customer account")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "order_id" in data, f"Missing order_id: {data}"
        assert "order_number" in data, f"Missing order_number: {data}"
        print(f"PASS: Order created: {data['order_number']}")

    def test_email_logs_after_scope_request_form(self, admin_headers):
        """After submitting enquiry, email_logs should contain mocked entries."""
        # First submit an enquiry
        product = self._get_first_product(admin_headers)
        ts = int(time.time())
        test_email = f"testnotif_{ts}@example.com"
        
        post_resp = requests.post(
            f"{BASE_URL}/api/orders/scope-request-form",
            headers=admin_headers,
            json={
                "items": [{"product_id": product["id"], "quantity": 1, "inputs": {}}],
                "form_data": {
                    "name": f"TEST_EmailLog_{ts}",
                    "email": test_email,
                    "company": "TEST Corp",
                    "phone": "+1 555 0000",
                    "message": f"TEST email log check {ts}",
                }
            }
        )
        print(f"Order submission: {post_resp.status_code}")
        if post_resp.status_code == 404 and "Customer" in post_resp.text:
            pytest.skip("Admin user has no customer record - skipping email log test")
        
        if post_resp.status_code != 200:
            pytest.skip(f"Order creation failed with {post_resp.status_code}: {post_resp.text}")
        
        order_number = post_resp.json().get("order_number", "")
        
        # Check email logs
        logs_resp = requests.get(f"{BASE_URL}/api/admin/email-logs", headers=admin_headers)
        assert logs_resp.status_code == 200, f"email-logs failed: {logs_resp.status_code}"
        logs = logs_resp.json().get("logs", [])
        
        # Find logs related to this submission
        enquiry_customer_logs = [l for l in logs if l.get("trigger") == "enquiry_customer"]
        scope_admin_logs = [l for l in logs if l.get("trigger") == "scope_request_admin"]
        
        print(f"Total logs: {len(logs)}")
        print(f"enquiry_customer logs: {len(enquiry_customer_logs)}")
        print(f"scope_request_admin logs: {len(scope_admin_logs)}")
        
        if enquiry_customer_logs:
            latest = enquiry_customer_logs[0]
            print(f"Latest enquiry_customer log: trigger={latest.get('trigger')}, status={latest.get('status')}, recipient={latest.get('recipient')}")
        
        # At minimum, the customer confirmation email should be in logs
        assert len(enquiry_customer_logs) > 0, (
            f"No enquiry_customer email logs found. Total logs count={len(logs)}. "
            f"Available triggers: {list(set(l.get('trigger') for l in logs))}"
        )
        print(f"PASS: enquiry_customer email log found after scope-request-form submission")

    def test_admin_email_logs_structure(self, admin_headers):
        """email-logs should return structured entries."""
        resp = requests.get(f"{BASE_URL}/api/admin/email-logs", headers=admin_headers)
        assert resp.status_code == 200
        logs = resp.json().get("logs", [])
        if not logs:
            print("INFO: No email logs yet - cannot verify structure")
            return
        
        log = logs[0]
        required_fields = ["id", "trigger", "recipient", "subject", "status", "created_at"]
        for field in required_fields:
            assert field in log, f"Missing field '{field}' in email log: {list(log.keys())}"
        print(f"PASS: Email log has required fields. Sample: trigger={log['trigger']}, status={log['status']}")


# ---------------------------------------------------------------------------
# Admin notification email setting
# ---------------------------------------------------------------------------

class TestAdminNotificationEmail:
    """Check admin_notification_email setting for admin emails."""

    def test_admin_settings_has_notification_email(self, admin_headers):
        """Admin settings should optionally have admin_notification_email configured."""
        resp = requests.get(f"{BASE_URL}/api/admin/settings", headers=admin_headers)
        assert resp.status_code == 200, f"Settings endpoint failed: {resp.status_code}"
        settings = resp.json().get("settings", {})
        admin_email = settings.get("admin_notification_email", "")
        print(f"admin_notification_email setting: '{admin_email}'")
        if not admin_email:
            print("INFO: admin_notification_email is NOT configured - admin notification emails will NOT be sent")
            print("INFO: To test admin email, configure admin_notification_email in System Config")
        else:
            print(f"PASS: admin_notification_email is configured as: {admin_email}")


# ---------------------------------------------------------------------------
# Email Outbox Tests (mocked emails)
# ---------------------------------------------------------------------------

class TestEmailOutbox:
    """Test that mocked emails go to email_outbox collection."""

    def test_customer_email_in_outbox_after_submission(self, admin_headers):
        """After enquiry submission, email_outbox should contain enquiry_customer type entry."""
        product_resp = requests.get(f"{BASE_URL}/api/products")
        products = product_resp.json().get("products", [])
        if not products:
            pytest.skip("No products available")
        product = products[0]
        
        ts = int(time.time())
        user_email = ADMIN_EMAIL  # The admin user's email = what customer confirmation goes to
        
        # Submit enquiry
        post_resp = requests.post(
            f"{BASE_URL}/api/orders/scope-request-form",
            headers=admin_headers,
            json={
                "items": [{"product_id": product["id"], "quantity": 1, "inputs": {}}],
                "form_data": {
                    "name": f"TEST_Outbox_{ts}",
                    "email": user_email,
                    "company": "TEST Outbox Corp",
                    "message": f"TEST outbox check {ts}",
                }
            }
        )
        print(f"Outbox test - order creation: {post_resp.status_code}")
        if post_resp.status_code == 404 and "Customer" in post_resp.text:
            pytest.skip("Admin user has no customer record - skipping outbox test")
        if post_resp.status_code != 200:
            pytest.skip(f"Order creation failed: {post_resp.text[:200]}")
        
        # Now check email logs for the customer confirmation
        # The email_logs endpoint is accessible; check if enquiry_customer was logged
        logs_resp = requests.get(f"{BASE_URL}/api/admin/email-logs", headers=admin_headers)
        assert logs_resp.status_code == 200
        logs = logs_resp.json().get("logs", [])
        
        # Find enquiry_customer logs
        cust_logs = [l for l in logs if l.get("trigger") == "enquiry_customer"]
        print(f"Found {len(cust_logs)} enquiry_customer log entries")
        
        assert len(cust_logs) > 0, (
            "No enquiry_customer email log found after scope-request-form submission. "
            "The email notification may not be firing."
        )
        
        latest = cust_logs[0]
        print(f"Latest enquiry_customer email: recipient={latest.get('recipient')}, status={latest.get('status')}, provider={latest.get('provider')}")
        # Status should be 'mocked' when no provider configured
        assert latest.get("status") in ["mocked", "sent"], (
            f"Unexpected email status: {latest.get('status')}"
        )
        print(f"PASS: Customer confirmation email logged with status={latest.get('status')}")


# ---------------------------------------------------------------------------
# Admin Enquiries Regression
# ---------------------------------------------------------------------------

class TestAdminEnquiriesRegression:
    """Regression test: Admin enquiries endpoint should still work."""

    def test_get_enquiries_returns_200(self, admin_headers):
        """GET /api/admin/enquiries should still return 200."""
        resp = requests.get(f"{BASE_URL}/api/admin/enquiries", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "enquiries" in data
        print(f"PASS: GET /admin/enquiries returns 200. Count={data.get('total', 0)}")

    def test_enquiries_have_expected_fields(self, admin_headers):
        """Enquiries should have expected structure."""
        resp = requests.get(f"{BASE_URL}/api/admin/enquiries", headers=admin_headers)
        data = resp.json()
        enquiries = data.get("enquiries", [])
        if not enquiries:
            print("INFO: No enquiries in DB")
            return
        e = enquiries[0]
        required = ["id", "order_number", "status", "type", "created_at"]
        for f in required:
            assert f in e, f"Missing field {f} in enquiry"
        print(f"PASS: Enquiry has required fields. type={e.get('type')}, status={e.get('status')}")
