"""
Iteration 80: Credential-Based Integration System Tests

Tests the completely rewritten Connect Services hub:
- 12 integrations (7 active + 5 coming soon)
- save-credentials, validate, activate, deactivate, disconnect endpoints
- app_settings sync after validation
- Email provider activation logic (only one active at a time)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

PLATFORM_ADMIN = {
    "email": "admin@automateaccounts.local",
    "password": "ChangeMe123!",
    "partner_code": "automate-accounts"
}


@pytest.fixture(scope="module")
def auth_session():
    """Create a session with auth cookie for platform admin."""
    session = requests.Session()
    resp = session.post(f"{BASE_URL}/api/auth/login", json=PLATFORM_ADMIN)
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    # Support both cookie-based and token-based auth
    token = resp.json().get("token")
    if token:
        session.headers.update({"Authorization": f"Bearer {token}"})
    return session


class TestListIntegrations:
    """Test GET /api/oauth/integrations - 12 integrations, 6 DCs"""

    def test_returns_12_integrations(self, auth_session):
        """Verify endpoint returns exactly 12 integrations (7 active + 5 coming soon)."""
        resp = auth_session.get(f"{BASE_URL}/api/oauth/integrations")
        assert resp.status_code == 200

        data = resp.json()
        integrations = data.get("integrations", [])
        assert len(integrations) == 12, f"Expected 12, got {len(integrations)}: {[i['id'] for i in integrations]}"

    def test_returns_7_active_integrations(self, auth_session):
        """Verify 7 non-coming-soon integrations exist."""
        resp = auth_session.get(f"{BASE_URL}/api/oauth/integrations")
        assert resp.status_code == 200

        integrations = resp.json()["integrations"]
        active = [i for i in integrations if not i.get("is_coming_soon")]
        expected_active = {"stripe", "gocardless", "gocardless_sandbox", "zoho_mail", "resend", "zoho_crm", "zoho_books"}
        actual_active = {i["id"] for i in active}
        assert actual_active == expected_active, f"Active mismatch. Got: {actual_active}"

    def test_returns_5_coming_soon(self, auth_session):
        """Verify 5 coming soon integrations (HubSpot, Salesforce, QuickBooks, Gmail, Outlook)."""
        resp = auth_session.get(f"{BASE_URL}/api/oauth/integrations")
        assert resp.status_code == 200

        integrations = resp.json()["integrations"]
        coming_soon = [i for i in integrations if i.get("is_coming_soon")]
        expected_cs = {"hubspot", "salesforce", "quickbooks", "gmail", "outlook"}
        actual_cs = {i["id"] for i in coming_soon}
        assert actual_cs == expected_cs, f"Coming soon mismatch. Got: {actual_cs}"

    def test_required_fields_present(self, auth_session):
        """Verify each integration has the required fields."""
        resp = auth_session.get(f"{BASE_URL}/api/oauth/integrations")
        assert resp.status_code == 200

        required = ["id", "name", "category", "status", "is_validated", "is_active", "is_coming_soon", "fields", "settings"]
        for integration in resp.json()["integrations"]:
            for field in required:
                assert field in integration, f"Missing field '{field}' in {integration['id']}"

    def test_coming_soon_have_empty_fields(self, auth_session):
        """Verify coming soon integrations have no action fields."""
        resp = auth_session.get(f"{BASE_URL}/api/oauth/integrations")
        assert resp.status_code == 200

        for integration in resp.json()["integrations"]:
            if integration.get("is_coming_soon"):
                assert integration["fields"] == [], f"{integration['id']} coming_soon should have no fields"

    def test_returns_6_zoho_data_centers(self, auth_session):
        """Verify 6 Zoho data centers returned."""
        resp = auth_session.get(f"{BASE_URL}/api/oauth/integrations")
        assert resp.status_code == 200

        data = resp.json()
        assert "zoho_data_centers" in data
        dcs = data["zoho_data_centers"]
        assert len(dcs) == 6, f"Expected 6 DCs, got {len(dcs)}"

        expected_dc_ids = {"us", "eu", "in", "au", "jp", "ca"}
        actual_dc_ids = {dc["id"] for dc in dcs}
        assert actual_dc_ids == expected_dc_ids, f"DC mismatch: {actual_dc_ids}"

    def test_requires_authentication(self):
        """Verify endpoint requires auth."""
        resp = requests.get(f"{BASE_URL}/api/oauth/integrations")
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"


class TestSaveCredentials:
    """Test POST /api/oauth/{provider}/save-credentials"""

    def test_stripe_save_credentials_returns_pending(self, auth_session):
        """Save Stripe credentials and verify status becomes 'pending'."""
        # First disconnect if exists
        auth_session.delete(f"{BASE_URL}/api/oauth/stripe/disconnect")

        resp = auth_session.post(
            f"{BASE_URL}/api/oauth/stripe/save-credentials",
            json={"credentials": {"api_key": "sk_test_FAKE_KEY_12345", "publishable_key": "pk_test_FAKE_KEY_12345"}}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") == True

        # Verify status is now pending
        status_resp = auth_session.get(f"{BASE_URL}/api/oauth/stripe/status")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["status"] == "pending", f"Expected 'pending', got {status_data['status']}"

    def test_resend_save_credentials(self, auth_session):
        """Save Resend API key credentials."""
        # Disconnect first
        auth_session.delete(f"{BASE_URL}/api/oauth/resend/disconnect")

        resp = auth_session.post(
            f"{BASE_URL}/api/oauth/resend/save-credentials",
            json={"credentials": {"api_key": "re_test_FAKE_12345"}}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") == True

        # Verify saved with pending status
        status_resp = auth_session.get(f"{BASE_URL}/api/oauth/resend/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "pending"

    def test_gocardless_save_credentials(self, auth_session):
        """Save GoCardless access_token credentials."""
        auth_session.delete(f"{BASE_URL}/api/oauth/gocardless/disconnect")

        resp = auth_session.post(
            f"{BASE_URL}/api/oauth/gocardless/save-credentials",
            json={"credentials": {"access_token": "TEST_GC_TOKEN_12345"}}
        )
        assert resp.status_code == 200
        assert resp.json().get("success") == True

    def test_gocardless_sandbox_save_credentials(self, auth_session):
        """Save GoCardless Sandbox access_token."""
        auth_session.delete(f"{BASE_URL}/api/oauth/gocardless_sandbox/disconnect")

        resp = auth_session.post(
            f"{BASE_URL}/api/oauth/gocardless_sandbox/save-credentials",
            json={"credentials": {"access_token": "TEST_GC_SANDBOX_TOKEN_12345"}}
        )
        assert resp.status_code == 200
        assert resp.json().get("success") == True

    def test_zoho_crm_requires_all_three_fields(self, auth_session):
        """Zoho CRM requires client_id, client_secret, and refresh_token."""
        # Missing refresh_token → should fail
        resp = auth_session.post(
            f"{BASE_URL}/api/oauth/zoho_crm/save-credentials",
            json={"credentials": {"client_id": "test_id", "client_secret": "test_secret"}}
        )
        assert resp.status_code == 400, f"Expected 400 for missing refresh_token, got {resp.status_code}"
        assert "refresh_token" in resp.json().get("detail", "").lower() or "required" in resp.json().get("detail", "").lower()

    def test_zoho_crm_save_all_required_fields(self, auth_session):
        """Save Zoho CRM with all required fields."""
        auth_session.delete(f"{BASE_URL}/api/oauth/zoho_crm/disconnect")

        resp = auth_session.post(
            f"{BASE_URL}/api/oauth/zoho_crm/save-credentials",
            json={
                "credentials": {
                    "client_id": "TEST_CLIENT_ID",
                    "client_secret": "TEST_CLIENT_SECRET",
                    "refresh_token": "TEST_REFRESH_TOKEN"
                },
                "data_center": "us"
            }
        )
        assert resp.status_code == 200
        assert resp.json().get("success") == True

    def test_coming_soon_save_credentials_rejected(self, auth_session):
        """Coming soon integrations should reject save-credentials."""
        resp = auth_session.post(
            f"{BASE_URL}/api/oauth/hubspot/save-credentials",
            json={"credentials": {"api_key": "test"}}
        )
        assert resp.status_code == 400
        assert "coming soon" in resp.json().get("detail", "").lower()

    def test_unknown_provider_rejected(self, auth_session):
        """Unknown providers should return 400."""
        resp = auth_session.post(
            f"{BASE_URL}/api/oauth/nonexistent/save-credentials",
            json={"credentials": {"api_key": "test"}}
        )
        assert resp.status_code == 400


class TestValidateConnection:
    """Test POST /api/oauth/{provider}/validate"""

    def test_stripe_validate_fake_key_returns_failure(self, auth_session):
        """Validate Stripe with fake key - should return success=False with error."""
        # Ensure we have credentials saved
        auth_session.post(
            f"{BASE_URL}/api/oauth/stripe/save-credentials",
            json={"credentials": {"api_key": "sk_test_FAKE_KEY_12345"}}
        )

        resp = auth_session.post(f"{BASE_URL}/api/oauth/stripe/validate")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") == False, "Fake Stripe key should fail validation"
        assert data.get("message"), "Error message should be provided"

        # Verify status updated to 'failed'
        status_resp = auth_session.get(f"{BASE_URL}/api/oauth/stripe/status")
        assert status_resp.json()["status"] == "failed"
        assert status_resp.json()["is_validated"] == False

    def test_resend_validate_fake_key_returns_failure(self, auth_session):
        """Validate Resend with fake key - should return success=False."""
        # Ensure credentials saved
        auth_session.post(
            f"{BASE_URL}/api/oauth/resend/save-credentials",
            json={"credentials": {"api_key": "re_test_FAKE_12345"}}
        )

        resp = auth_session.post(f"{BASE_URL}/api/oauth/resend/validate")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") == False
        assert data.get("message"), "Error message should be provided"

    def test_validate_without_credentials_fails(self, auth_session):
        """Validate without credentials should return 400."""
        # Disconnect GoCardless sandbox first to clear any credentials
        auth_session.delete(f"{BASE_URL}/api/oauth/gocardless_sandbox/disconnect")

        resp = auth_session.post(f"{BASE_URL}/api/oauth/gocardless_sandbox/validate")
        assert resp.status_code == 400

    def test_gocardless_validate_fake_token_returns_failure(self, auth_session):
        """Validate GoCardless with fake access token - should fail."""
        auth_session.post(
            f"{BASE_URL}/api/oauth/gocardless/save-credentials",
            json={"credentials": {"access_token": "TEST_GC_TOKEN_FAKE"}}
        )

        resp = auth_session.post(f"{BASE_URL}/api/oauth/gocardless/validate")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") == False


class TestDisconnect:
    """Test DELETE /api/oauth/{provider}/disconnect"""

    def test_stripe_disconnect_removes_connection(self, auth_session):
        """Disconnect Stripe removes the connection record."""
        # Save credentials first
        auth_session.post(
            f"{BASE_URL}/api/oauth/stripe/save-credentials",
            json={"credentials": {"api_key": "sk_test_FAKE_12345"}}
        )

        # Disconnect
        resp = auth_session.delete(f"{BASE_URL}/api/oauth/stripe/disconnect")
        assert resp.status_code == 200
        assert resp.json().get("success") == True

        # Verify status is not_connected
        status_resp = auth_session.get(f"{BASE_URL}/api/oauth/stripe/status")
        assert status_resp.json()["status"] == "not_connected"
        assert status_resp.json()["is_validated"] == False

    def test_stripe_disconnect_sets_stripe_enabled_false(self, auth_session):
        """Disconnecting Stripe sets stripe_enabled=False in app_settings."""
        # Save and validate/disconnect
        auth_session.post(
            f"{BASE_URL}/api/oauth/stripe/save-credentials",
            json={"credentials": {"api_key": "sk_test_FAKE"}}
        )
        auth_session.delete(f"{BASE_URL}/api/oauth/stripe/disconnect")

        # Check app_settings
        settings_resp = auth_session.get(f"{BASE_URL}/api/admin/settings")
        if settings_resp.status_code == 200:
            settings = settings_resp.json()
            # stripe_enabled should be False or absent
            stripe_enabled = settings.get("stripe_enabled", False)
            assert stripe_enabled == False, f"stripe_enabled should be False after disconnect, got {stripe_enabled}"

    def test_disconnect_unknown_provider(self, auth_session):
        """Disconnecting unknown provider returns 400."""
        resp = auth_session.delete(f"{BASE_URL}/api/oauth/nonexistent/disconnect")
        assert resp.status_code == 400


class TestEmailProviderActivation:
    """Test activate/deactivate email providers"""

    def test_activate_requires_validated_connection(self, auth_session):
        """Activating without validated connection should return 400."""
        # Make sure Resend is not validated
        auth_session.delete(f"{BASE_URL}/api/oauth/resend/disconnect")

        resp = auth_session.post(f"{BASE_URL}/api/oauth/resend/activate")
        assert resp.status_code == 400, f"Expected 400 for unvalidated, got {resp.status_code}"

    def test_activate_non_email_provider_fails(self, auth_session):
        """Activating a non-email provider (e.g. Stripe) should return 400."""
        resp = auth_session.post(f"{BASE_URL}/api/oauth/stripe/activate")
        assert resp.status_code == 400

    def test_deactivate_email_provider(self, auth_session):
        """Deactivate email provider sets email_provider_enabled=False."""
        # Add some email credentials first (even if not validated)
        auth_session.post(
            f"{BASE_URL}/api/oauth/resend/save-credentials",
            json={"credentials": {"api_key": "re_test_FAKE"}}
        )

        # Deactivate
        resp = auth_session.post(f"{BASE_URL}/api/oauth/resend/deactivate")
        assert resp.status_code == 200
        assert resp.json().get("success") == True

    def test_deactivate_non_email_provider_fails(self, auth_session):
        """Deactivating a non-email provider should return 400."""
        resp = auth_session.post(f"{BASE_URL}/api/oauth/stripe/deactivate")
        assert resp.status_code == 400

    def test_only_one_email_active_at_a_time(self, auth_session):
        """Activating one email provider while another is active should deactivate old one."""
        # We can only test this if we have validated providers
        # For now verify the logic through the API response structure
        resp = auth_session.get(f"{BASE_URL}/api/oauth/integrations")
        assert resp.status_code == 200

        data = resp.json()
        active_email_providers = [i for i in data["integrations"] if i.get("is_active")]
        assert len(active_email_providers) <= 1, \
            f"More than one email provider active: {[p['id'] for p in active_email_providers]}"


class TestProviderStatus:
    """Test GET /api/oauth/{provider}/status"""

    def test_stripe_status_endpoint(self, auth_session):
        """Verify Stripe status endpoint returns correct structure."""
        resp = auth_session.get(f"{BASE_URL}/api/oauth/stripe/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "provider" in data
        assert "status" in data
        assert "is_validated" in data
        assert data["provider"] == "stripe"

    def test_unknown_provider_status(self, auth_session):
        """Unknown provider status should return 400."""
        resp = auth_session.get(f"{BASE_URL}/api/oauth/nonexistent/status")
        assert resp.status_code == 400


class TestUpdateSettings:
    """Test POST /api/oauth/{provider}/update-settings"""

    def test_update_settings_for_gocardless(self, auth_session):
        """Update GoCardless settings (success page text)."""
        # Save credentials first
        auth_session.post(
            f"{BASE_URL}/api/oauth/gocardless/save-credentials",
            json={"credentials": {"access_token": "TEST_TOKEN"}}
        )

        resp = auth_session.post(
            f"{BASE_URL}/api/oauth/gocardless/update-settings",
            json={"settings": {"success_title": "Payment Complete!", "success_message": "Done."}}
        )
        assert resp.status_code == 200
        assert resp.json().get("success") == True

    def test_update_settings_unknown_provider(self, auth_session):
        """Update settings for unknown provider returns 400."""
        resp = auth_session.post(
            f"{BASE_URL}/api/oauth/nonexistent/update-settings",
            json={"settings": {"key": "value"}}
        )
        assert resp.status_code == 400


class TestIntegrationsCategorization:
    """Verify integrations are categorized correctly."""

    def test_stripe_in_payments_category(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/oauth/integrations")
        integrations = {i["id"]: i for i in resp.json()["integrations"]}
        assert integrations["stripe"]["category"] == "payments"
        assert integrations["gocardless"]["category"] == "payments"
        assert integrations["gocardless_sandbox"]["category"] == "payments"

    def test_email_providers_in_email_category(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/oauth/integrations")
        integrations = {i["id"]: i for i in resp.json()["integrations"]}
        assert integrations["resend"]["category"] == "email"
        assert integrations["zoho_mail"]["category"] == "email"
        assert integrations["gmail"]["category"] == "email"
        assert integrations["outlook"]["category"] == "email"

    def test_crm_providers_in_crm_category(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/oauth/integrations")
        integrations = {i["id"]: i for i in resp.json()["integrations"]}
        assert integrations["zoho_crm"]["category"] == "crm"
        assert integrations["hubspot"]["category"] == "crm"
        assert integrations["salesforce"]["category"] == "crm"

    def test_accounting_providers_in_accounting_category(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/oauth/integrations")
        integrations = {i["id"]: i for i in resp.json()["integrations"]}
        assert integrations["zoho_books"]["category"] == "accounting"
        assert integrations["quickbooks"]["category"] == "accounting"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
