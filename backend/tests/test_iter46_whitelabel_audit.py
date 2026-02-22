"""
Iteration 46: Test new whitelabel audit features
Tests: dynamic checkout sections builder, page content fields, new ws fields on all pages.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_token():
    """Get admin JWT token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!"
    })
    if resp.status_code != 200:
        pytest.skip(f"Admin login failed ({resp.status_code}): {resp.text[:200]}")
    return resp.json().get("access_token") or resp.json().get("token")


@pytest.fixture(scope="module")
def admin_client(admin_token):
    """Requests session with admin auth."""
    s = requests.Session()
    s.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {admin_token}"
    })
    return s


# ─── Public website settings endpoint ────────────────────────────────────────

class TestPublicWebsiteSettings:
    """GET /api/website-settings returns all new fields."""

    def test_endpoint_returns_200(self):
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"

    def test_response_has_settings_key(self):
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        data = resp.json()
        assert "settings" in data, "Response must have 'settings' key"

    def test_has_checkout_sections_field(self):
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        settings = resp.json()["settings"]
        assert "checkout_sections" in settings, "Must have checkout_sections"
        # Should be valid JSON array string
        import json
        val = settings["checkout_sections"]
        parsed = json.loads(val)
        assert isinstance(parsed, list), "checkout_sections must be JSON array"

    def test_has_page_404_fields(self):
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        settings = resp.json()["settings"]
        assert "page_404_title" in settings, "Must have page_404_title"
        assert "page_404_link_text" in settings, "Must have page_404_link_text"
        assert settings["page_404_title"] != "", "page_404_title must have default value"
        assert settings["page_404_link_text"] != "", "page_404_link_text must have default value"

    def test_has_checkout_success_fields(self):
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        settings = resp.json()["settings"]
        required_fields = [
            "checkout_success_title", "checkout_success_paid_msg",
            "checkout_success_pending_msg", "checkout_success_expired_msg",
            "checkout_success_next_steps_title", "checkout_success_step_1",
            "checkout_success_step_2", "checkout_success_step_3",
            "checkout_portal_link_text"
        ]
        for field in required_fields:
            assert field in settings, f"Missing field: {field}"

    def test_has_bank_transfer_success_fields(self):
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        settings = resp.json()["settings"]
        required_fields = [
            "bank_success_title", "bank_success_message",
            "bank_instructions_title", "bank_instruction_1", "bank_instruction_2", "bank_instruction_3",
            "bank_next_steps_title", "bank_next_step_1", "bank_next_step_2", "bank_next_step_3"
        ]
        for field in required_fields:
            assert field in settings, f"Missing field: {field}"

    def test_has_gocardless_page_fields(self):
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        settings = resp.json()["settings"]
        required_fields = [
            "gocardless_processing_title", "gocardless_processing_subtitle",
            "gocardless_success_title", "gocardless_success_message",
            "gocardless_error_title", "gocardless_error_message",
            "gocardless_return_btn_text"
        ]
        for field in required_fields:
            assert field in settings, f"Missing field: {field}"

    def test_has_verify_email_fields(self):
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        settings = resp.json()["settings"]
        for field in ["verify_email_label", "verify_email_title", "verify_email_subtitle"]:
            assert field in settings, f"Missing field: {field}"

    def test_has_portal_fields(self):
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        settings = resp.json()["settings"]
        for field in ["portal_title", "portal_subtitle"]:
            assert field in settings, f"Missing field: {field}"
        assert settings["portal_title"] != "", "portal_title must have default value"

    def test_has_profile_fields(self):
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        settings = resp.json()["settings"]
        for field in ["profile_label", "profile_title", "profile_subtitle"]:
            assert field in settings, f"Missing field: {field}"

    def test_has_cart_fields(self):
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        settings = resp.json()["settings"]
        for field in ["cart_title", "cart_clear_btn_text", "msg_currency_unsupported", "msg_no_payment_methods"]:
            assert field in settings, f"Missing field: {field}"
        assert settings["cart_title"] != "", "cart_title must have default value"


# ─── Admin website settings CRUD ─────────────────────────────────────────────

class TestAdminWebsiteSettingsCRUD:
    """PUT /api/admin/website-settings saves new fields correctly."""

    def test_admin_get_website_settings(self, admin_client):
        resp = admin_client.get(f"{BASE_URL}/api/admin/website-settings")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "settings" in data

    def test_put_page_404_fields(self, admin_client):
        """Save 404 page fields and verify they persist."""
        original_resp = admin_client.get(f"{BASE_URL}/api/admin/website-settings")
        original = original_resp.json()["settings"]
        original_title = original.get("page_404_title", "Page not found")

        # Update
        resp = admin_client.put(f"{BASE_URL}/api/admin/website-settings", json={
            "page_404_title": "TEST_404 - Page not found",
            "page_404_link_text": "TEST_Back to home"
        })
        assert resp.status_code == 200, f"PUT failed: {resp.status_code}: {resp.text[:200]}"

        # Verify GET
        get_resp = admin_client.get(f"{BASE_URL}/api/admin/website-settings")
        settings = get_resp.json()["settings"]
        assert settings["page_404_title"] == "TEST_404 - Page not found"
        assert settings["page_404_link_text"] == "TEST_Back to home"

        # Restore
        admin_client.put(f"{BASE_URL}/api/admin/website-settings", json={
            "page_404_title": original_title,
            "page_404_link_text": original.get("page_404_link_text", "Back to store")
        })

    def test_put_checkout_sections_field(self, admin_client):
        """Save checkout_sections JSON and verify it persists."""
        import json
        test_sections = json.dumps([
            {
                "id": "cs_test001",
                "title": "TEST Section",
                "description": "Test description",
                "enabled": True,
                "order": 0,
                "fields_schema": json.dumps([
                    {"id": "f1", "key": "test_field", "label": "Test Field", "type": "text", "required": True}
                ])
            }
        ])

        resp = admin_client.put(f"{BASE_URL}/api/admin/website-settings", json={
            "checkout_sections": test_sections
        })
        assert resp.status_code == 200, f"PUT failed: {resp.status_code}: {resp.text[:200]}"

        # Verify
        get_resp = admin_client.get(f"{BASE_URL}/api/admin/website-settings")
        settings = get_resp.json()["settings"]
        stored = settings.get("checkout_sections", "[]")
        parsed = json.loads(stored)
        assert isinstance(parsed, list), "checkout_sections must be a JSON array"
        assert len(parsed) == 1, "Should have 1 section"
        assert parsed[0]["title"] == "TEST Section"

        # Cleanup - restore to empty
        admin_client.put(f"{BASE_URL}/api/admin/website-settings", json={
            "checkout_sections": "[]"
        })

    def test_put_portal_fields(self, admin_client):
        """Save portal page fields and verify they persist."""
        original_resp = admin_client.get(f"{BASE_URL}/api/admin/website-settings")
        original = original_resp.json()["settings"]

        resp = admin_client.put(f"{BASE_URL}/api/admin/website-settings", json={
            "portal_title": "TEST_My Portal",
            "portal_subtitle": "TEST_Track your orders here."
        })
        assert resp.status_code == 200

        get_resp = admin_client.get(f"{BASE_URL}/api/admin/website-settings")
        settings = get_resp.json()["settings"]
        assert settings["portal_title"] == "TEST_My Portal"
        assert settings["portal_subtitle"] == "TEST_Track your orders here."

        # Restore
        admin_client.put(f"{BASE_URL}/api/admin/website-settings", json={
            "portal_title": original.get("portal_title", "Customer portal"),
            "portal_subtitle": original.get("portal_subtitle", "Track your orders and subscriptions in one place.")
        })

    def test_put_cart_fields(self, admin_client):
        """Save cart page fields and verify they persist."""
        original_resp = admin_client.get(f"{BASE_URL}/api/admin/website-settings")
        original = original_resp.json()["settings"]

        resp = admin_client.put(f"{BASE_URL}/api/admin/website-settings", json={
            "cart_title": "TEST_Shopping Cart",
            "cart_clear_btn_text": "TEST_Empty Cart",
            "msg_currency_unsupported": "TEST_Currency not supported",
            "msg_no_payment_methods": "TEST_No payment methods"
        })
        assert resp.status_code == 200

        get_resp = admin_client.get(f"{BASE_URL}/api/admin/website-settings")
        settings = get_resp.json()["settings"]
        assert settings["cart_title"] == "TEST_Shopping Cart"
        assert settings["cart_clear_btn_text"] == "TEST_Empty Cart"
        assert settings["msg_currency_unsupported"] == "TEST_Currency not supported"
        assert settings["msg_no_payment_methods"] == "TEST_No payment methods"

        # Restore
        admin_client.put(f"{BASE_URL}/api/admin/website-settings", json={
            "cart_title": original.get("cart_title", "Your cart"),
            "cart_clear_btn_text": original.get("cart_clear_btn_text", "Clear cart"),
            "msg_currency_unsupported": original.get("msg_currency_unsupported", ""),
            "msg_no_payment_methods": original.get("msg_no_payment_methods", "")
        })

    def test_put_bank_success_fields(self, admin_client):
        """Save bank transfer success page fields and verify they persist."""
        resp = admin_client.put(f"{BASE_URL}/api/admin/website-settings", json={
            "bank_success_title": "TEST_Bank Order Created",
            "bank_success_message": "TEST_Your order is awaiting payment."
        })
        assert resp.status_code == 200

        get_resp = admin_client.get(f"{BASE_URL}/api/admin/website-settings")
        settings = get_resp.json()["settings"]
        assert settings["bank_success_title"] == "TEST_Bank Order Created"
        assert settings["bank_success_message"] == "TEST_Your order is awaiting payment."

        # Restore
        admin_client.put(f"{BASE_URL}/api/admin/website-settings", json={
            "bank_success_title": "Order Created",
            "bank_success_message": "Your order has been created and is awaiting bank transfer payment."
        })

    def test_put_profile_fields(self, admin_client):
        """Save profile page fields and verify they persist."""
        resp = admin_client.put(f"{BASE_URL}/api/admin/website-settings", json={
            "profile_label": "TEST_Profile Label",
            "profile_title": "TEST_My Account",
            "profile_subtitle": "TEST_Update your details."
        })
        assert resp.status_code == 200

        get_resp = admin_client.get(f"{BASE_URL}/api/admin/website-settings")
        settings = get_resp.json()["settings"]
        assert settings["profile_label"] == "TEST_Profile Label"
        assert settings["profile_title"] == "TEST_My Account"
        assert settings["profile_subtitle"] == "TEST_Update your details."

        # Restore
        admin_client.put(f"{BASE_URL}/api/admin/website-settings", json={
            "profile_label": "My Profile",
            "profile_title": "Account details",
            "profile_subtitle": "Update your contact details. Currency remains locked after your first purchase."
        })

    def test_checkout_success_fields_persist(self, admin_client):
        """Save checkout success page fields and verify they persist."""
        resp = admin_client.put(f"{BASE_URL}/api/admin/website-settings", json={
            "checkout_success_title": "TEST_Checkout Status",
            "checkout_success_paid_msg": "TEST_Payment received!"
        })
        assert resp.status_code == 200

        get_resp = admin_client.get(f"{BASE_URL}/api/admin/website-settings")
        settings = get_resp.json()["settings"]
        assert settings["checkout_success_title"] == "TEST_Checkout Status"
        assert settings["checkout_success_paid_msg"] == "TEST_Payment received!"

        # Restore
        admin_client.put(f"{BASE_URL}/api/admin/website-settings", json={
            "checkout_success_title": "Checkout status",
            "checkout_success_paid_msg": "Payment successful."
        })

    def test_verify_email_fields_persist(self, admin_client):
        """Save verify email page fields and verify they persist."""
        resp = admin_client.put(f"{BASE_URL}/api/admin/website-settings", json={
            "verify_email_label": "TEST_Email Verify",
            "verify_email_title": "TEST_Enter Your Code"
        })
        assert resp.status_code == 200

        get_resp = admin_client.get(f"{BASE_URL}/api/admin/website-settings")
        settings = get_resp.json()["settings"]
        assert settings["verify_email_label"] == "TEST_Email Verify"
        assert settings["verify_email_title"] == "TEST_Enter Your Code"

        # Restore
        admin_client.put(f"{BASE_URL}/api/admin/website-settings", json={
            "verify_email_label": "Verify email",
            "verify_email_title": "Enter your code"
        })


# ─── Public endpoint reflects admin changes ──────────────────────────────────

class TestPublicEndpointReflectsAdminChanges:
    """Verify public endpoint returns admin-saved values."""

    def test_public_endpoint_reflects_portal_change(self, admin_client):
        """After admin updates portal_title, public endpoint must reflect it."""
        admin_client.put(f"{BASE_URL}/api/admin/website-settings", json={
            "portal_title": "TEST_Public Portal Check"
        })
        import time; time.sleep(0.5)  # Small delay for DB write

        pub_resp = requests.get(f"{BASE_URL}/api/website-settings")
        pub_settings = pub_resp.json()["settings"]
        assert pub_settings["portal_title"] == "TEST_Public Portal Check", \
            f"Public endpoint didn't reflect change: {pub_settings.get('portal_title')}"

        # Restore
        admin_client.put(f"{BASE_URL}/api/admin/website-settings", json={
            "portal_title": "Customer portal"
        })

    def test_public_endpoint_reflects_cart_title_change(self, admin_client):
        """After admin updates cart_title, public endpoint must reflect it."""
        admin_client.put(f"{BASE_URL}/api/admin/website-settings", json={
            "cart_title": "TEST_My Shopping Cart"
        })
        import time; time.sleep(0.5)

        pub_resp = requests.get(f"{BASE_URL}/api/website-settings")
        pub_settings = pub_resp.json()["settings"]
        assert pub_settings["cart_title"] == "TEST_My Shopping Cart", \
            f"Public endpoint didn't reflect change: {pub_settings.get('cart_title')}"

        # Restore
        admin_client.put(f"{BASE_URL}/api/admin/website-settings", json={
            "cart_title": "Your cart"
        })
