"""Phase 3 Backend Tests: References, Email Templates, Customer Payment Methods"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"

# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token."""
    res = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert res.status_code == 200, f"Admin login failed: {res.text}"
    return res.json().get("access_token") or res.json().get("token")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ── Backend Health ────────────────────────────────────────────────────────────

class TestBackendHealth:
    """Verify backend is up and key APIs work."""

    def test_health_endpoint(self):
        res = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert res.status_code in (200, 404), f"Backend unreachable: {res.status_code}"
        print("Backend health check passed")

    def test_admin_login(self):
        res = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert res.status_code == 200, f"Admin login failed: {res.text}"
        data = res.json()
        assert "access_token" in data or "token" in data, "No token in response"
        print("Admin login OK")


# ── References API ────────────────────────────────────────────────────────────

class TestReferencesAPI:
    """CRUD tests for /api/admin/references."""

    _created_id = None

    def test_list_references(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/admin/references", headers=auth_headers)
        assert res.status_code == 200, f"GET /admin/references failed: {res.text}"
        data = res.json()
        assert "references" in data, "Response missing 'references' key"
        assert isinstance(data["references"], list), "References should be a list"
        print(f"List references: {len(data['references'])} found")

    def test_create_reference(self, auth_headers):
        payload = {
            "label": "TEST Phase3 Contact Email",
            "key": "test_phase3_contact_email",
            "type": "email",
            "value": "test-phase3@example.com",
            "description": "Test reference for Phase 3"
        }
        res = requests.post(f"{BASE_URL}/api/admin/references", json=payload, headers=auth_headers)
        assert res.status_code == 200, f"POST /admin/references failed: {res.text}"
        data = res.json()
        assert "reference" in data
        ref = data["reference"]
        assert ref["key"] == "test_phase3_contact_email"
        assert ref["label"] == "TEST Phase3 Contact Email"
        assert ref["type"] == "email"
        TestReferencesAPI._created_id = ref["id"]
        print(f"Created reference id={ref['id']}")

    def test_create_reference_duplicate_key_fails(self, auth_headers):
        payload = {
            "label": "Duplicate Test",
            "key": "test_phase3_contact_email",  # same key as above
            "type": "text",
            "value": "duplicate"
        }
        res = requests.post(f"{BASE_URL}/api/admin/references", json=payload, headers=auth_headers)
        assert res.status_code == 400, f"Expected 400 for duplicate key, got {res.status_code}"
        print("Duplicate key correctly rejected")

    def test_update_reference(self, auth_headers):
        if not TestReferencesAPI._created_id:
            pytest.skip("No created reference to update")
        ref_id = TestReferencesAPI._created_id
        update = {"value": "updated-test-phase3@example.com", "description": "Updated description"}
        res = requests.put(f"{BASE_URL}/api/admin/references/{ref_id}", json=update, headers=auth_headers)
        assert res.status_code == 200, f"PUT /admin/references/{ref_id} failed: {res.text}"
        data = res.json()
        assert data["reference"]["value"] == "updated-test-phase3@example.com"
        print("Reference updated successfully")

    def test_delete_reference(self, auth_headers):
        if not TestReferencesAPI._created_id:
            pytest.skip("No created reference to delete")
        ref_id = TestReferencesAPI._created_id
        res = requests.delete(f"{BASE_URL}/api/admin/references/{ref_id}", headers=auth_headers)
        assert res.status_code == 200, f"DELETE /admin/references/{ref_id} failed: {res.text}"
        print("Reference deleted successfully")

    def test_public_references_endpoint(self):
        """Public (no auth) references endpoint."""
        res = requests.get(f"{BASE_URL}/api/references")
        assert res.status_code == 200, f"GET /references (public) failed: {res.text}"
        data = res.json()
        assert "references" in data
        print(f"Public references: {len(data['references'])} found")


# ── Email Templates API ───────────────────────────────────────────────────────

class TestEmailTemplatesAPI:
    """Tests for /api/admin/email-templates."""

    _first_template_id = None

    def test_list_email_templates(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=auth_headers)
        assert res.status_code == 200, f"GET /admin/email-templates failed: {res.text}"
        data = res.json()
        assert "templates" in data
        assert isinstance(data["templates"], list)
        assert len(data["templates"]) > 0, "Expected at least 1 email template"
        print(f"Email templates count: {len(data['templates'])}")
        TestEmailTemplatesAPI._first_template_id = data["templates"][0]["id"]

    def test_template_has_required_fields(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=auth_headers)
        assert res.status_code == 200
        templates = res.json()["templates"]
        for tmpl in templates:
            assert "id" in tmpl, "Template missing 'id'"
            assert "trigger" in tmpl, "Template missing 'trigger'"
            assert "label" in tmpl, "Template missing 'label'"
            assert "is_enabled" in tmpl, "Template missing 'is_enabled'"
            assert "subject" in tmpl, "Template missing 'subject'"
        print("All templates have required fields")

    def test_update_template_subject(self, auth_headers):
        if not TestEmailTemplatesAPI._first_template_id:
            pytest.skip("No template available")
        tmpl_id = TestEmailTemplatesAPI._first_template_id
        # Get current state
        res = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=auth_headers)
        templates = res.json()["templates"]
        current = next((t for t in templates if t["id"] == tmpl_id), None)
        original_subject = current["subject"] if current else "Original Subject"

        # Update subject
        new_subject = f"TEST Updated Subject {tmpl_id[:8]}"
        update_res = requests.put(
            f"{BASE_URL}/api/admin/email-templates/{tmpl_id}",
            json={"subject": new_subject},
            headers=auth_headers
        )
        assert update_res.status_code == 200, f"PUT template failed: {update_res.text}"
        data = update_res.json()
        assert data["template"]["subject"] == new_subject
        print(f"Template subject updated: '{new_subject}'")

        # Restore original
        requests.put(f"{BASE_URL}/api/admin/email-templates/{tmpl_id}", json={"subject": original_subject}, headers=auth_headers)

    def test_toggle_template_enabled(self, auth_headers):
        if not TestEmailTemplatesAPI._first_template_id:
            pytest.skip("No template available")
        tmpl_id = TestEmailTemplatesAPI._first_template_id
        res = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=auth_headers)
        templates = res.json()["templates"]
        current = next((t for t in templates if t["id"] == tmpl_id), None)
        original_enabled = current["is_enabled"] if current else True

        # Toggle
        toggle_res = requests.put(
            f"{BASE_URL}/api/admin/email-templates/{tmpl_id}",
            json={"is_enabled": not original_enabled},
            headers=auth_headers
        )
        assert toggle_res.status_code == 200
        assert toggle_res.json()["template"]["is_enabled"] == (not original_enabled)
        print(f"Template toggled to is_enabled={not original_enabled}")

        # Restore
        requests.put(f"{BASE_URL}/api/admin/email-templates/{tmpl_id}", json={"is_enabled": original_enabled}, headers=auth_headers)

    def test_email_logs_endpoint(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/admin/email-logs", headers=auth_headers)
        assert res.status_code == 200, f"GET /admin/email-logs failed: {res.text}"
        data = res.json()
        assert "logs" in data
        print(f"Email logs: {len(data['logs'])} entries")


# ── Customer Payment Methods API ──────────────────────────────────────────────

class TestCustomerPaymentMethodsAPI:
    """Tests for /api/admin/customers/{id}/payment-methods."""

    _test_customer_id = None

    def test_get_customers_list(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/admin/customers", headers=auth_headers)
        assert res.status_code == 200, f"GET /admin/customers failed: {res.text}"
        data = res.json()
        assert "customers" in data
        customers = data["customers"]
        assert len(customers) > 0, "Need at least one customer for payment method tests"
        TestCustomerPaymentMethodsAPI._test_customer_id = customers[0]["id"]
        print(f"Found {len(customers)} customers. Using ID: {customers[0]['id']}")

    def test_update_payment_methods_with_allowed_modes(self, auth_headers):
        if not TestCustomerPaymentMethodsAPI._test_customer_id:
            pytest.skip("No customer ID available")
        cid = TestCustomerPaymentMethodsAPI._test_customer_id
        res = requests.put(
            f"{BASE_URL}/api/admin/customers/{cid}/payment-methods",
            json={"allowed_payment_modes": ["bank_transfer"]},
            headers=auth_headers
        )
        assert res.status_code == 200, f"PUT payment-methods failed: {res.text}"
        print(f"Payment methods updated for customer {cid}")

    def test_payment_methods_updates_legacy_booleans(self, auth_headers):
        """Setting allowed_payment_modes should sync legacy booleans."""
        if not TestCustomerPaymentMethodsAPI._test_customer_id:
            pytest.skip("No customer ID available")
        cid = TestCustomerPaymentMethodsAPI._test_customer_id

        # Set only bank_transfer
        res = requests.put(
            f"{BASE_URL}/api/admin/customers/{cid}/payment-methods",
            json={"allowed_payment_modes": ["bank_transfer"]},
            headers=auth_headers
        )
        assert res.status_code == 200

        # Verify customer data shows updated booleans
        customers_res = requests.get(f"{BASE_URL}/api/admin/customers", headers=auth_headers)
        customers = customers_res.json()["customers"]
        updated = next((c for c in customers if c["id"] == cid), None)
        if updated:
            assert updated.get("allow_bank_transfer") == True
            assert updated.get("allow_card_payment") == False
            print("Legacy booleans synced correctly")

    def test_update_payment_methods_both_modes(self, auth_headers):
        if not TestCustomerPaymentMethodsAPI._test_customer_id:
            pytest.skip("No customer ID available")
        cid = TestCustomerPaymentMethodsAPI._test_customer_id
        res = requests.put(
            f"{BASE_URL}/api/admin/customers/{cid}/payment-methods",
            json={"allowed_payment_modes": ["bank_transfer", "card"]},
            headers=auth_headers
        )
        assert res.status_code == 200
        print("Both payment modes set successfully")

    def test_update_payment_methods_invalid_customer(self, auth_headers):
        res = requests.put(
            f"{BASE_URL}/api/admin/customers/nonexistent_id_xyz/payment-methods",
            json={"allowed_payment_modes": ["bank_transfer"]},
            headers=auth_headers
        )
        assert res.status_code == 404, f"Expected 404 for nonexistent customer, got {res.status_code}"
        print("404 returned for nonexistent customer")


# ── Website Settings API ──────────────────────────────────────────────────────

class TestWebsiteSettingsAPI:
    """Test website settings endpoints used by WebsiteTab."""

    def test_get_admin_settings(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/admin/settings", headers=auth_headers)
        assert res.status_code == 200, f"GET /admin/settings failed: {res.text}"
        data = res.json()
        assert "settings" in data
        print(f"Admin settings keys: {list(data['settings'].keys())[:5]}")

    def test_get_admin_settings_structured(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/admin/settings/structured", headers=auth_headers)
        assert res.status_code == 200, f"GET /admin/settings/structured failed: {res.text}"
        data = res.json()
        assert "settings" in data
        print(f"Structured settings categories: {list(data['settings'].keys())}")

    def test_get_admin_website_settings(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=auth_headers)
        assert res.status_code == 200, f"GET /admin/website-settings failed: {res.text}"
        data = res.json()
        assert "settings" in data
        print("Website settings loaded OK")

    def test_update_store_name(self, auth_headers):
        # Get current
        res = requests.get(f"{BASE_URL}/api/admin/settings", headers=auth_headers)
        current_settings = res.json().get("settings", {})
        original_name = current_settings.get("store_name", "Test Store")

        # Update
        test_name = "TEST Phase3 Store"
        update_res = requests.put(
            f"{BASE_URL}/api/admin/settings",
            json={"store_name": test_name},
            headers=auth_headers
        )
        assert update_res.status_code == 200, f"PUT /admin/settings failed: {update_res.text}"

        # Verify
        verify_res = requests.get(f"{BASE_URL}/api/admin/settings", headers=auth_headers)
        updated_settings = verify_res.json().get("settings", {})
        assert updated_settings.get("store_name") == test_name
        print(f"Store name updated to '{test_name}'")

        # Restore
        requests.put(f"{BASE_URL}/api/admin/settings", json={"store_name": original_name}, headers=auth_headers)
