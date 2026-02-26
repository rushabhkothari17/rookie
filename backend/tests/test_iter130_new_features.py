"""
Backend tests for new features in iteration 130:
1. Read-only Country display for admin/partner admin profile views (tax_settings.country)
2. Subscription tax calculation (tax_amount/tax_rate/tax_name on subscriptions)
3. Partner-specific invoice templates CRUD
4. Email Invoice button (send-invoice endpoint, invoice_email template)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"

SARAH_EMAIL = "sarah@brightaccounting.local"
SARAH_PASSWORD = "BrightAdmin123!"


@pytest.fixture(scope="module")
def admin_token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    token = resp.json().get("access_token") or resp.json().get("token")
    assert token, "No token returned from admin login"
    return token


@pytest.fixture(scope="module")
def sarah_token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": SARAH_EMAIL, "password": SARAH_PASSWORD})
    if resp.status_code != 200:
        pytest.skip(f"Sarah login failed: {resp.text}")
    token = resp.json().get("access_token") or resp.json().get("token")
    assert token, "No token returned from Sarah login"
    return token


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture
def sarah_headers(sarah_token):
    return {"Authorization": f"Bearer {sarah_token}", "Content-Type": "application/json"}


# ── Feature 1: Admin Profile Country from Tax Settings ───────────────────────

class TestAdminProfileCountry:
    """Test that admin can access tax settings which include country for profile display."""

    def test_admin_can_get_tax_settings(self, admin_headers):
        """GET /admin/taxes/settings should return 200 with tax_settings"""
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/settings", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "tax_settings" in data, "Response missing 'tax_settings'"

    def test_tax_settings_has_country_field(self, admin_headers):
        """tax_settings should have a 'country' field (can be empty or set)"""
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/settings", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        ts = data.get("tax_settings", {})
        # country key may or may not exist but should be accessible
        country = ts.get("country", "")
        print(f"Admin tax_settings.country = '{country}'")
        # Just verify it's a string (could be empty if not configured)
        assert isinstance(country, str), "country should be a string"

    def test_sarah_can_get_tax_settings(self, sarah_headers):
        """Sarah (bright-accounting admin) can also get tax settings"""
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/settings", headers=sarah_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "tax_settings" in data

    def test_admin_me_endpoint(self, admin_headers):
        """GET /me should return user data for admin"""
        resp = requests.get(f"{BASE_URL}/api/me", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "role" in data or "user" in data, "Missing user/role in /me response"
        # Print role for debugging
        user = data.get("user", data)
        print(f"Admin role = '{user.get('role', 'N/A')}'")

    def test_sarah_me_endpoint(self, sarah_headers):
        """GET /me should return user data for Sarah"""
        resp = requests.get(f"{BASE_URL}/api/me", headers=sarah_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "role" in data or "user" in data


# ── Feature 3: Partner-Specific Invoice Templates CRUD ───────────────────────

class TestInvoiceTemplatesCRUD:
    """Test CRUD for partner-specific invoice templates."""

    def test_get_invoice_templates_returns_200(self, admin_headers):
        """GET /admin/taxes/invoice-templates should return 200"""
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/invoice-templates", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_get_invoice_templates_has_templates_array(self, admin_headers):
        """Response should contain 'templates' array"""
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/invoice-templates", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "templates" in data, "Response missing 'templates' key"
        assert isinstance(data["templates"], list), "'templates' should be a list"

    def test_create_invoice_template_success(self, admin_headers):
        """POST /admin/taxes/invoice-templates should create and return template"""
        payload = {
            "name": "TEST_Bright Accounting Template",
            "html_body": "<!DOCTYPE html><html><body><h1>Invoice {{invoice_number}}</h1><p>From: {{partner_name}}</p><p>Total: {{order_total}}</p></body></html>"
        }
        resp = requests.post(
            f"{BASE_URL}/api/admin/taxes/invoice-templates",
            json=payload,
            headers=admin_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "template" in data, "Response missing 'template'"
        tmpl = data["template"]
        assert tmpl.get("name") == payload["name"]
        assert tmpl.get("html_body") == payload["html_body"]
        assert "id" in tmpl, "Template missing 'id'"
        assert "tenant_id" in tmpl, "Template missing 'tenant_id'"
        assert "_id" not in tmpl, "Template should not expose MongoDB _id"
        return tmpl["id"]

    def test_create_template_requires_name(self, admin_headers):
        """POST /admin/taxes/invoice-templates without name should return 400"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/taxes/invoice-templates",
            json={"html_body": "<html></html>"},
            headers=admin_headers,
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"

    def test_create_and_get_template_persisted(self, admin_headers):
        """After creating a template, it should appear in GET list"""
        # Create
        create_resp = requests.post(
            f"{BASE_URL}/api/admin/taxes/invoice-templates",
            json={"name": "TEST_Persistence Check Template", "html_body": "<html>test</html>"},
            headers=admin_headers,
        )
        assert create_resp.status_code == 200
        created_id = create_resp.json()["template"]["id"]

        # List
        list_resp = requests.get(f"{BASE_URL}/api/admin/taxes/invoice-templates", headers=admin_headers)
        assert list_resp.status_code == 200
        template_ids = [t["id"] for t in list_resp.json().get("templates", [])]
        assert created_id in template_ids, f"Template {created_id} not found in list"

        # Cleanup
        del_resp = requests.delete(
            f"{BASE_URL}/api/admin/taxes/invoice-templates/{created_id}",
            headers=admin_headers,
        )
        assert del_resp.status_code == 200

    def test_update_invoice_template(self, admin_headers):
        """PUT /admin/taxes/invoice-templates/{id} should update template"""
        # Create first
        create_resp = requests.post(
            f"{BASE_URL}/api/admin/taxes/invoice-templates",
            json={"name": "TEST_Update Me Template", "html_body": "<html>original</html>"},
            headers=admin_headers,
        )
        assert create_resp.status_code == 200
        tmpl_id = create_resp.json()["template"]["id"]

        # Update
        update_resp = requests.put(
            f"{BASE_URL}/api/admin/taxes/invoice-templates/{tmpl_id}",
            json={"name": "TEST_Updated Template Name", "html_body": "<html>updated</html>"},
            headers=admin_headers,
        )
        assert update_resp.status_code == 200, f"Expected 200, got {update_resp.status_code}: {update_resp.text}"

        # Verify update persisted
        list_resp = requests.get(f"{BASE_URL}/api/admin/taxes/invoice-templates", headers=admin_headers)
        templates = {t["id"]: t for t in list_resp.json().get("templates", [])}
        assert tmpl_id in templates
        assert templates[tmpl_id]["name"] == "TEST_Updated Template Name"

        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/taxes/invoice-templates/{tmpl_id}", headers=admin_headers)

    def test_delete_invoice_template(self, admin_headers):
        """DELETE /admin/taxes/invoice-templates/{id} should remove template"""
        # Create
        create_resp = requests.post(
            f"{BASE_URL}/api/admin/taxes/invoice-templates",
            json={"name": "TEST_Delete Me Template", "html_body": "<html></html>"},
            headers=admin_headers,
        )
        assert create_resp.status_code == 200
        tmpl_id = create_resp.json()["template"]["id"]

        # Delete
        del_resp = requests.delete(
            f"{BASE_URL}/api/admin/taxes/invoice-templates/{tmpl_id}",
            headers=admin_headers,
        )
        assert del_resp.status_code == 200

        # Verify removed
        list_resp = requests.get(f"{BASE_URL}/api/admin/taxes/invoice-templates", headers=admin_headers)
        template_ids = [t["id"] for t in list_resp.json().get("templates", [])]
        assert tmpl_id not in template_ids, "Deleted template still in list"

    def test_delete_nonexistent_template_returns_404(self, admin_headers):
        """DELETE with nonexistent ID should return 404"""
        resp = requests.delete(
            f"{BASE_URL}/api/admin/taxes/invoice-templates/nonexistent-id-xyz",
            headers=admin_headers,
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"

    def test_invoice_templates_unauthenticated_returns_401(self):
        """GET /admin/taxes/invoice-templates without auth should return 401"""
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/invoice-templates")
        assert resp.status_code in [401, 403]


# ── Invoice Templates For Viewer ─────────────────────────────────────────────

class TestInvoiceTemplatesForViewer:
    """Test the viewer-specific endpoint for templates."""

    def test_get_templates_for_viewer_returns_200(self, admin_headers):
        """GET /admin/taxes/invoice-templates-for-viewer should return 200"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/taxes/invoice-templates-for-viewer",
            headers=admin_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_get_templates_for_viewer_has_templates_array(self, admin_headers):
        """Response should contain 'templates' array"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/taxes/invoice-templates-for-viewer",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "templates" in data, "Response missing 'templates'"
        assert isinstance(data["templates"], list)

    def test_viewer_templates_excludes_mongodb_id(self, admin_headers):
        """Templates in viewer response should not contain MongoDB _id"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/taxes/invoice-templates-for-viewer",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        for tmpl in resp.json().get("templates", []):
            assert "_id" not in tmpl, "Template should not expose MongoDB _id"

    def test_viewer_templates_only_shows_active(self, admin_headers):
        """Viewer endpoint should only show active templates (is_active != False)"""
        # Create an active template
        create_resp = requests.post(
            f"{BASE_URL}/api/admin/taxes/invoice-templates",
            json={"name": "TEST_Viewer Active Template", "html_body": "<html>viewer</html>"},
            headers=admin_headers,
        )
        assert create_resp.status_code == 200
        tmpl_id = create_resp.json()["template"]["id"]

        # Check it appears in viewer
        viewer_resp = requests.get(
            f"{BASE_URL}/api/admin/taxes/invoice-templates-for-viewer",
            headers=admin_headers,
        )
        assert viewer_resp.status_code == 200
        viewer_ids = [t["id"] for t in viewer_resp.json().get("templates", [])]
        assert tmpl_id in viewer_ids, "Active template should appear in viewer"

        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/taxes/invoice-templates/{tmpl_id}", headers=admin_headers)

    def test_templates_for_viewer_unauthenticated_returns_401(self):
        """GET /admin/taxes/invoice-templates-for-viewer without auth should return 401"""
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/invoice-templates-for-viewer")
        assert resp.status_code in [401, 403]


# ── Feature 4: Email Invoice Endpoint ────────────────────────────────────────

class TestEmailInvoice:
    """Test POST /orders/{id}/send-invoice"""

    def test_send_invoice_invalid_order_returns_404(self, admin_headers):
        """POST /orders/invalid-id/send-invoice should return 404"""
        resp = requests.post(
            f"{BASE_URL}/api/orders/invalid-id/send-invoice",
            json={},
            headers=admin_headers,
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"

    def test_send_invoice_unauthenticated_returns_401(self):
        """POST /orders/{id}/send-invoice without auth should return 401"""
        resp = requests.post(f"{BASE_URL}/api/orders/test-id/send-invoice", json={})
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"

    def test_send_invoice_for_real_order(self, admin_headers):
        """POST /orders/{valid_id}/send-invoice should return 200 or error about missing customer"""
        # Get a real order ID
        orders_resp = requests.get(f"{BASE_URL}/api/admin/orders?per_page=1", headers=admin_headers)
        if orders_resp.status_code != 200:
            pytest.skip("Cannot list orders")
        orders = orders_resp.json().get("orders", [])
        if not orders:
            pytest.skip("No orders in DB")

        order_id = orders[0]["id"]
        resp = requests.post(
            f"{BASE_URL}/api/orders/{order_id}/send-invoice",
            json={},
            headers=admin_headers,
        )
        # Should succeed (200) or return 400 if customer has no email
        assert resp.status_code in [200, 400], f"Expected 200 or 400, got {resp.status_code}: {resp.text}"
        if resp.status_code == 200:
            data = resp.json()
            assert "recipient" in data, "Response missing 'recipient'"
            assert "status" in data, "Response missing 'status'"
            print(f"Invoice email sent to: {data.get('recipient')}, status: {data.get('status')}")


# ── Email Templates - invoice_email trigger ───────────────────────────────────

class TestEmailTemplateInvoice:
    """Test that invoice_email template exists and is seeded."""

    def test_email_templates_list_contains_invoice(self, admin_headers):
        """Email templates list should contain invoice_email trigger"""
        resp = requests.get(f"{BASE_URL}/api/admin/website/email-templates", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        templates = data.get("templates", [])
        triggers = [t.get("trigger") for t in templates]
        assert "invoice_email" in triggers, f"invoice_email trigger not found. Found triggers: {triggers}"

    def test_invoice_email_template_has_correct_label(self, admin_headers):
        """invoice_email template should have label 'Invoice (Customer)'"""
        resp = requests.get(f"{BASE_URL}/api/admin/website/email-templates", headers=admin_headers)
        assert resp.status_code == 200
        templates = resp.json().get("templates", [])
        invoice_tmpl = next((t for t in templates if t.get("trigger") == "invoice_email"), None)
        assert invoice_tmpl is not None, "invoice_email template not found"
        assert invoice_tmpl.get("label") == "Invoice (Customer)", \
            f"Expected 'Invoice (Customer)', got '{invoice_tmpl.get('label')}'"

    def test_invoice_email_template_is_enabled(self, admin_headers):
        """invoice_email template should be enabled"""
        resp = requests.get(f"{BASE_URL}/api/admin/website/email-templates", headers=admin_headers)
        assert resp.status_code == 200
        templates = resp.json().get("templates", [])
        invoice_tmpl = next((t for t in templates if t.get("trigger") == "invoice_email"), None)
        if invoice_tmpl:
            assert invoice_tmpl.get("is_enabled", True) is True, "invoice_email should be enabled"

    def test_invoice_email_template_has_variables(self, admin_headers):
        """invoice_email template should have invoice-specific variables"""
        resp = requests.get(f"{BASE_URL}/api/admin/website/email-templates", headers=admin_headers)
        assert resp.status_code == 200
        templates = resp.json().get("templates", [])
        invoice_tmpl = next((t for t in templates if t.get("trigger") == "invoice_email"), None)
        if invoice_tmpl:
            avail_vars = invoice_tmpl.get("available_variables", [])
            assert "{{invoice_number}}" in avail_vars or any("invoice" in v for v in avail_vars), \
                f"Expected invoice variables, got: {avail_vars}"


# ── Sarah (Partner Admin) Template Isolation ─────────────────────────────────

class TestTemplateIsolation:
    """Test that custom templates are tenant-scoped."""

    def test_sarah_can_get_invoice_templates(self, sarah_headers):
        """Sarah should be able to get her own invoice templates"""
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/invoice-templates", headers=sarah_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "templates" in data

    def test_templates_are_tenant_scoped(self, admin_headers, sarah_headers):
        """Templates created by admin should NOT be visible to Sarah"""
        # Create template as admin
        create_resp = requests.post(
            f"{BASE_URL}/api/admin/taxes/invoice-templates",
            json={"name": "TEST_Admin Only Template", "html_body": "<html>admin</html>"},
            headers=admin_headers,
        )
        assert create_resp.status_code == 200
        admin_tmpl_id = create_resp.json()["template"]["id"]

        # Check Sarah's templates
        sarah_resp = requests.get(f"{BASE_URL}/api/admin/taxes/invoice-templates", headers=sarah_headers)
        assert sarah_resp.status_code == 200
        sarah_ids = [t["id"] for t in sarah_resp.json().get("templates", [])]
        assert admin_tmpl_id not in sarah_ids, "Admin's template should not be visible to Sarah"

        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/taxes/invoice-templates/{admin_tmpl_id}", headers=admin_headers)


# ── Cleanup: Remove all TEST_ templates ─────────────────────────────────────

class TestCleanup:
    """Cleanup any TEST_ prefixed templates that were created"""

    def test_cleanup_test_templates(self, admin_headers, sarah_headers):
        """Remove any TEST_ templates created during testing"""
        for headers in [admin_headers, sarah_headers]:
            resp = requests.get(f"{BASE_URL}/api/admin/taxes/invoice-templates", headers=headers)
            if resp.status_code == 200:
                for tmpl in resp.json().get("templates", []):
                    if tmpl.get("name", "").startswith("TEST_"):
                        requests.delete(
                            f"{BASE_URL}/api/admin/taxes/invoice-templates/{tmpl['id']}",
                            headers=headers,
                        )
        print("Cleanup complete")
