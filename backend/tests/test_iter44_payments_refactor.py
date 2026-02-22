"""
Iteration 44 Backend Tests: Major Architectural Refactoring
Tests for:
- Payment modes (gocardless/stripe) renaming from bank_transfer/card
- Customer payment filter dropdown (gocardless, stripe, both, none)
- Website settings payment labels/fee rates
- Public website endpoint returns payment display fields
- Backend API: PUT /api/admin/customers/{id}/payment-methods with allowed_payment_modes=['gocardless']
"""
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


@pytest.fixture(scope="module")
def test_customer_id(auth_headers):
    """Get first available customer ID for tests."""
    res = requests.get(f"{BASE_URL}/api/admin/customers", headers=auth_headers)
    assert res.status_code == 200
    customers = res.json().get("customers", [])
    if not customers:
        pytest.skip("No customers found for payment method tests")
    return customers[0]["id"]


# ── Website Settings - Payment Fields ────────────────────────────────────────

class TestWebsiteSettingsPaymentFields:
    """Test payment display fields in website settings (admin endpoint)."""

    def test_admin_website_settings_has_payment_labels(self, auth_headers):
        """Admin website-settings endpoint should return payment_gocardless_label etc."""
        res = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=auth_headers)
        assert res.status_code == 200, f"GET /admin/website-settings failed: {res.text}"
        settings = res.json().get("settings", {})
        assert "payment_gocardless_label" in settings, "Missing payment_gocardless_label"
        assert "payment_gocardless_description" in settings, "Missing payment_gocardless_description"
        assert "payment_stripe_label" in settings, "Missing payment_stripe_label"
        assert "payment_stripe_description" in settings, "Missing payment_stripe_description"
        print(f"payment_gocardless_label: {settings['payment_gocardless_label']}")
        print(f"payment_stripe_label: {settings['payment_stripe_label']}")

    def test_public_website_settings_has_payment_fee_rates(self):
        """Public website-settings endpoint should include payment flags + fee rates."""
        res = requests.get(f"{BASE_URL}/api/website-settings")
        assert res.status_code == 200, f"GET /website-settings (public) failed: {res.text}"
        settings = res.json().get("settings", {})
        assert "stripe_enabled" in settings, "Missing stripe_enabled"
        assert "gocardless_enabled" in settings, "Missing gocardless_enabled"
        assert "stripe_fee_rate" in settings, "Missing stripe_fee_rate"
        assert "gocardless_fee_rate" in settings, "Missing gocardless_fee_rate"
        assert "payment_gocardless_label" in settings, "Missing payment_gocardless_label"
        assert "payment_stripe_label" in settings, "Missing payment_stripe_label"
        print(f"stripe_fee_rate: {settings['stripe_fee_rate']}")
        print(f"gocardless_fee_rate: {settings['gocardless_fee_rate']}")

    def test_public_website_settings_payment_labels_have_defaults(self):
        """Payment labels should have non-empty defaults."""
        res = requests.get(f"{BASE_URL}/api/website-settings")
        settings = res.json().get("settings", {})
        gc_label = settings.get("payment_gocardless_label", "")
        stripe_label = settings.get("payment_stripe_label", "")
        assert gc_label, "payment_gocardless_label should have a default value"
        assert stripe_label, "payment_stripe_label should have a default value"
        print(f"GC Label default: '{gc_label}'")
        print(f"Stripe Label default: '{stripe_label}'")

    def test_update_payment_labels_in_website_settings(self, auth_headers):
        """Update payment labels in website-settings and verify persistence."""
        # Get current values
        res = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=auth_headers)
        original_gc_label = res.json().get("settings", {}).get("payment_gocardless_label", "")

        # Update
        test_label = "TEST GoCardless Bank Transfer"
        update_res = requests.put(
            f"{BASE_URL}/api/admin/website-settings",
            json={"payment_gocardless_label": test_label},
            headers=auth_headers
        )
        assert update_res.status_code == 200, f"PUT /admin/website-settings failed: {update_res.text}"

        # Verify persisted
        verify_res = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=auth_headers)
        updated_label = verify_res.json().get("settings", {}).get("payment_gocardless_label", "")
        assert updated_label == test_label, f"Label not persisted: expected '{test_label}', got '{updated_label}'"
        print(f"Payment label updated to '{test_label}' and persisted")

        # Restore
        restore_label = original_gc_label or "Bank Transfer (GoCardless)"
        requests.put(f"{BASE_URL}/api/admin/website-settings", json={"payment_gocardless_label": restore_label}, headers=auth_headers)


# ── Customer Payment Methods - New API (gocardless/stripe) ───────────────────

class TestCustomerPaymentMethodsNewAPI:
    """Test the new allowed_payment_modes API (gocardless/stripe naming)."""

    def test_set_gocardless_only(self, auth_headers, test_customer_id):
        """PUT with allowed_payment_modes=['gocardless'] sets allow_bank_transfer=True."""
        res = requests.put(
            f"{BASE_URL}/api/admin/customers/{test_customer_id}/payment-methods",
            json={"allowed_payment_modes": ["gocardless"]},
            headers=auth_headers
        )
        assert res.status_code == 200, f"PUT payment-methods failed: {res.text}"
        assert res.json().get("message") == "Payment methods updated"

        # Verify booleans were synced
        customers_res = requests.get(f"{BASE_URL}/api/admin/customers", headers=auth_headers)
        customers = customers_res.json().get("customers", [])
        updated = next((c for c in customers if c["id"] == test_customer_id), None)
        assert updated is not None, "Customer not found after update"
        assert updated.get("allow_bank_transfer") == True, "allow_bank_transfer should be True for gocardless"
        assert updated.get("allow_card_payment") == False, "allow_card_payment should be False when only gocardless"
        # Check allowed_payment_modes array
        modes = updated.get("allowed_payment_modes", [])
        assert "gocardless" in modes, f"allowed_payment_modes should contain 'gocardless', got: {modes}"
        print(f"GoCcardless-only mode set. allow_bank_transfer={updated.get('allow_bank_transfer')}, modes={modes}")

    def test_set_stripe_only(self, auth_headers, test_customer_id):
        """PUT with allowed_payment_modes=['stripe'] sets allow_card_payment=True."""
        res = requests.put(
            f"{BASE_URL}/api/admin/customers/{test_customer_id}/payment-methods",
            json={"allowed_payment_modes": ["stripe"]},
            headers=auth_headers
        )
        assert res.status_code == 200

        customers_res = requests.get(f"{BASE_URL}/api/admin/customers", headers=auth_headers)
        customers = customers_res.json().get("customers", [])
        updated = next((c for c in customers if c["id"] == test_customer_id), None)
        assert updated is not None
        assert updated.get("allow_card_payment") == True, "allow_card_payment should be True for stripe"
        assert updated.get("allow_bank_transfer") == False, "allow_bank_transfer should be False when only stripe"
        modes = updated.get("allowed_payment_modes", [])
        assert "stripe" in modes, f"allowed_payment_modes should contain 'stripe', got: {modes}"
        print(f"Stripe-only mode set. allow_card_payment={updated.get('allow_card_payment')}, modes={modes}")

    def test_set_both_modes(self, auth_headers, test_customer_id):
        """PUT with allowed_payment_modes=['gocardless', 'stripe'] sets both booleans True."""
        res = requests.put(
            f"{BASE_URL}/api/admin/customers/{test_customer_id}/payment-methods",
            json={"allowed_payment_modes": ["gocardless", "stripe"]},
            headers=auth_headers
        )
        assert res.status_code == 200

        customers_res = requests.get(f"{BASE_URL}/api/admin/customers", headers=auth_headers)
        customers = customers_res.json().get("customers", [])
        updated = next((c for c in customers if c["id"] == test_customer_id), None)
        assert updated is not None
        assert updated.get("allow_bank_transfer") == True
        assert updated.get("allow_card_payment") == True
        modes = updated.get("allowed_payment_modes", [])
        assert "gocardless" in modes and "stripe" in modes
        print(f"Both modes set. modes={modes}")

    def test_set_none_modes(self, auth_headers, test_customer_id):
        """PUT with allowed_payment_modes=[] sets both booleans False."""
        res = requests.put(
            f"{BASE_URL}/api/admin/customers/{test_customer_id}/payment-methods",
            json={"allowed_payment_modes": []},
            headers=auth_headers
        )
        assert res.status_code == 200

        customers_res = requests.get(f"{BASE_URL}/api/admin/customers", headers=auth_headers)
        customers = customers_res.json().get("customers", [])
        updated = next((c for c in customers if c["id"] == test_customer_id), None)
        assert updated is not None
        assert updated.get("allow_bank_transfer") == False
        assert updated.get("allow_card_payment") == False
        print("Empty modes set correctly (both booleans False)")

    def test_old_bank_transfer_name_normalized_to_gocardless(self, auth_headers, test_customer_id):
        """Sending old 'bank_transfer' mode name should normalize to 'gocardless'."""
        res = requests.put(
            f"{BASE_URL}/api/admin/customers/{test_customer_id}/payment-methods",
            json={"allowed_payment_modes": ["bank_transfer"]},
            headers=auth_headers
        )
        assert res.status_code == 200

        customers_res = requests.get(f"{BASE_URL}/api/admin/customers", headers=auth_headers)
        customers = customers_res.json().get("customers", [])
        updated = next((c for c in customers if c["id"] == test_customer_id), None)
        assert updated is not None
        modes = updated.get("allowed_payment_modes", [])
        # Should be normalized to 'gocardless', not 'bank_transfer'
        assert "gocardless" in modes, f"Old 'bank_transfer' should be normalized to 'gocardless', got: {modes}"
        assert "bank_transfer" not in modes, f"'bank_transfer' should not remain in modes: {modes}"
        print(f"bank_transfer normalized to gocardless: modes={modes}")

    def test_old_card_name_normalized_to_stripe(self, auth_headers, test_customer_id):
        """Sending old 'card' mode name should normalize to 'stripe'."""
        res = requests.put(
            f"{BASE_URL}/api/admin/customers/{test_customer_id}/payment-methods",
            json={"allowed_payment_modes": ["card"]},
            headers=auth_headers
        )
        assert res.status_code == 200

        customers_res = requests.get(f"{BASE_URL}/api/admin/customers", headers=auth_headers)
        customers = customers_res.json().get("customers", [])
        updated = next((c for c in customers if c["id"] == test_customer_id), None)
        assert updated is not None
        modes = updated.get("allowed_payment_modes", [])
        assert "stripe" in modes, f"Old 'card' should be normalized to 'stripe', got: {modes}"
        assert "card" not in modes, f"'card' should not remain in modes: {modes}"
        print(f"card normalized to stripe: modes={modes}")

    def test_invalid_customer_returns_404(self, auth_headers):
        """Nonexistent customer should return 404."""
        res = requests.put(
            f"{BASE_URL}/api/admin/customers/nonexistent_id_xyz/payment-methods",
            json={"allowed_payment_modes": ["gocardless"]},
            headers=auth_headers
        )
        assert res.status_code == 404, f"Expected 404, got {res.status_code}"
        print("404 returned for nonexistent customer")

    def test_restore_gocardless_after_tests(self, auth_headers, test_customer_id):
        """Restore customer to gocardless-only after tests."""
        res = requests.put(
            f"{BASE_URL}/api/admin/customers/{test_customer_id}/payment-methods",
            json={"allowed_payment_modes": ["gocardless"]},
            headers=auth_headers
        )
        assert res.status_code == 200
        print("Customer restored to gocardless-only")


# ── Customer Payment Mode Filter ──────────────────────────────────────────────

class TestCustomerPaymentModeFilter:
    """Test the payment_mode filter query param on /api/admin/customers."""

    def test_filter_gocardless_returns_200(self, auth_headers):
        """Filter by gocardless should work without error."""
        res = requests.get(f"{BASE_URL}/api/admin/customers?payment_mode=gocardless", headers=auth_headers)
        assert res.status_code == 200, f"GET with payment_mode=gocardless failed: {res.text}"
        data = res.json()
        assert "customers" in data
        print(f"payment_mode=gocardless filter: {len(data['customers'])} customers")

    def test_filter_stripe_returns_200(self, auth_headers):
        """Filter by stripe should work without error."""
        res = requests.get(f"{BASE_URL}/api/admin/customers?payment_mode=stripe", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "customers" in data
        print(f"payment_mode=stripe filter: {len(data['customers'])} customers")

    def test_filter_both_returns_200(self, auth_headers):
        """Filter by both should work without error."""
        res = requests.get(f"{BASE_URL}/api/admin/customers?payment_mode=both", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "customers" in data
        print(f"payment_mode=both filter: {len(data['customers'])} customers")

    def test_filter_none_returns_200(self, auth_headers):
        """Filter by none should work without error."""
        res = requests.get(f"{BASE_URL}/api/admin/customers?payment_mode=none", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "customers" in data
        print(f"payment_mode=none filter: {len(data['customers'])} customers")

    def test_gocardless_filter_returns_bank_transfer_customers(self, auth_headers, test_customer_id):
        """After setting gocardless for test customer, filter should find them."""
        # Ensure customer has gocardless
        requests.put(
            f"{BASE_URL}/api/admin/customers/{test_customer_id}/payment-methods",
            json={"allowed_payment_modes": ["gocardless"]},
            headers=auth_headers
        )
        # Filter
        res = requests.get(f"{BASE_URL}/api/admin/customers?payment_mode=gocardless", headers=auth_headers)
        customers = res.json().get("customers", [])
        ids = [c["id"] for c in customers]
        assert test_customer_id in ids, f"Test customer should appear in gocardless filter results"
        # Verify all returned customers have allow_bank_transfer=True
        for c in customers:
            assert c.get("allow_bank_transfer") == True, f"Customer {c['id']} should have allow_bank_transfer=True"
        print(f"gocardless filter returns {len(customers)} customers, all with allow_bank_transfer=True")


# ── Structured Settings - Payments Category ──────────────────────────────────

class TestStructuredSettingsPayments:
    """Verify Payments category in structured settings has correct keys."""

    def test_structured_settings_has_payments_category(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/admin/settings/structured", headers=auth_headers)
        assert res.status_code == 200
        structured = res.json().get("settings", {})
        assert "Payments" in structured, f"Missing 'Payments' category. Available: {list(structured.keys())}"
        payments = structured["Payments"]
        print(f"Payments settings count: {len(payments)}")

    def test_payments_has_gocardless_and_stripe_toggles(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/admin/settings/structured", headers=auth_headers)
        structured = res.json().get("settings", {})
        payments = structured.get("Payments", [])
        keys = [p["key"] for p in payments]
        assert "gocardless_enabled" in keys, f"Missing gocardless_enabled. Keys: {keys}"
        assert "stripe_enabled" in keys, f"Missing stripe_enabled. Keys: {keys}"
        print(f"Payment keys: {keys}")

    def test_payments_has_fee_rate_settings(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/admin/settings/structured", headers=auth_headers)
        structured = res.json().get("settings", {})
        payments = structured.get("Payments", [])
        keys = [p["key"] for p in payments]
        assert "stripe_fee_rate" in keys, f"Missing stripe_fee_rate. Keys: {keys}"
        # gocardless_fee_rate should also exist
        has_gc_fee = "gocardless_fee_rate" in keys
        print(f"stripe_fee_rate present: True, gocardless_fee_rate present: {has_gc_fee}")
        print(f"All payment keys: {keys}")

    def test_sysconfig_does_not_have_payment_category(self, auth_headers):
        """System Config section should not include Payments category anymore."""
        res = requests.get(f"{BASE_URL}/api/admin/settings/structured", headers=auth_headers)
        structured = res.json().get("settings", {})
        # Payments category should exist (it's shown in the Payments tab)
        # But it should NOT appear under the 3 sysconfig categories: Operations, FeatureFlags, Zoho
        sysconfig_cats = ["Operations", "FeatureFlags", "Zoho"]
        for cat in sysconfig_cats:
            items = structured.get(cat, [])
            keys = [i["key"] for i in items]
            payment_keys = [k for k in keys if "gocardless" in k or "stripe" in k or "payment" in k]
            assert not payment_keys, f"Category '{cat}' should not have payment keys. Found: {payment_keys}"
        print("System Config categories (Operations, FeatureFlags, Zoho) have no payment keys")


# ── Email Templates API (for TipTap rich text editor testing) ─────────────────

class TestEmailTemplatesForEditor:
    """Verify email templates API returns data needed by TipTap editor."""

    def test_templates_have_html_body_field(self, auth_headers):
        """Templates must have html_body for the rich text editor."""
        res = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=auth_headers)
        assert res.status_code == 200
        templates = res.json().get("templates", [])
        assert len(templates) > 0
        for tmpl in templates:
            assert "html_body" in tmpl, f"Template {tmpl.get('trigger')} missing 'html_body'"
            assert "subject" in tmpl
            assert "available_variables" in tmpl
        print(f"All {len(templates)} templates have html_body for rich text editor")

    def test_template_html_body_update_persists(self, auth_headers):
        """Update html_body via API and verify it persists (TipTap editor save)."""
        # Get first template
        res = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=auth_headers)
        templates = res.json().get("templates", [])
        if not templates:
            pytest.skip("No templates available")

        tmpl = templates[0]
        tmpl_id = tmpl["id"]
        original_body = tmpl.get("html_body", "")

        # Update with HTML content (as TipTap would generate)
        test_html = "<p><strong>TEST Rich Text Content</strong></p><p>Updated by iter44 tests.</p>"
        update_res = requests.put(
            f"{BASE_URL}/api/admin/email-templates/{tmpl_id}",
            json={"html_body": test_html},
            headers=auth_headers
        )
        assert update_res.status_code == 200
        assert update_res.json()["template"]["html_body"] == test_html

        # Verify via GET
        verify_res = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=auth_headers)
        updated_tmpl = next((t for t in verify_res.json()["templates"] if t["id"] == tmpl_id), None)
        assert updated_tmpl["html_body"] == test_html
        print(f"html_body updated and persisted for template {tmpl_id[:8]}")

        # Restore original
        requests.put(f"{BASE_URL}/api/admin/email-templates/{tmpl_id}", json={"html_body": original_body}, headers=auth_headers)
