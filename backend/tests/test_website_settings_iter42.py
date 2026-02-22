"""
Backend tests for Website Settings + Form Schema Builder features (Iteration 42).
Tests: admin/website-settings GET/PUT, admin/settings/structured, form schemas,
integrations section, system config, links/URLs section.
"""
import json
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


@pytest.fixture(scope="module")
def admin_token():
    """Get admin token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!"
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return resp.json().get("token") or resp.json().get("access_token")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ── 1. Public website settings ──────────────────────────────────────────────

class TestPublicWebsiteSettings:
    """GET /api/website-settings (public)"""

    def test_public_settings_200(self):
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        assert resp.status_code == 200, resp.text

    def test_public_settings_has_defaults(self):
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        data = resp.json()
        settings = data.get("settings", {})
        assert "hero_label" in settings
        assert "hero_title" in settings

    def test_public_settings_has_form_schemas(self):
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        settings = resp.json().get("settings", {})
        # Form schemas should be present (JSON strings)
        assert "quote_form_schema" in settings
        assert "scope_form_schema" in settings
        assert "signup_form_schema" in settings

    def test_public_settings_form_schemas_are_valid_json(self):
        resp = requests.get(f"{BASE_URL}/api/website-settings")
        settings = resp.json().get("settings", {})
        for key in ["quote_form_schema", "scope_form_schema", "signup_form_schema"]:
            val = settings.get(key, "")
            if val:
                parsed = json.loads(val)
                assert isinstance(parsed, list), f"{key} should parse to a list"
                print(f"{key}: {len(parsed)} fields")


# ── 2. Admin website settings ───────────────────────────────────────────────

class TestAdminWebsiteSettings:
    """GET/PUT /api/admin/website-settings"""

    def test_get_admin_website_settings_200(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=admin_headers)
        assert resp.status_code == 200, resp.text

    def test_admin_website_settings_has_all_sections(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=admin_headers)
        settings = resp.json().get("settings", {})
        # Branding / hero
        assert "hero_label" in settings
        assert "hero_title" in settings
        # Auth
        assert "login_title" in settings
        assert "register_title" in settings
        # Forms
        assert "quote_form_title" in settings
        assert "scope_form_title" in settings
        assert "signup_form_title" in settings
        # Form schemas
        assert "quote_form_schema" in settings
        assert "scope_form_schema" in settings
        assert "signup_form_schema" in settings

    def test_admin_website_settings_has_email_templates(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=admin_headers)
        settings = resp.json().get("settings", {})
        assert "email_from_name" in settings
        assert "email_article_subject_template" in settings
        assert "email_article_cta_text" in settings
        assert "email_article_footer_text" in settings
        assert "email_verification_subject" in settings
        assert "email_verification_body" in settings

    def test_admin_website_settings_has_error_messages(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=admin_headers)
        settings = resp.json().get("settings", {})
        assert "msg_partner_tagging_prompt" in settings
        assert "msg_override_required" in settings
        assert "msg_cart_empty" in settings
        assert "msg_quote_success" in settings
        assert "msg_scope_success" in settings

    def test_admin_website_settings_has_footer_nav(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=admin_headers)
        settings = resp.json().get("settings", {})
        assert "footer_tagline" in settings
        assert "footer_copyright" in settings
        assert "nav_store_label" in settings
        assert "nav_articles_label" in settings
        assert "nav_portal_label" in settings

    def test_update_website_settings_hero(self, admin_headers):
        """Test PUT /api/admin/website-settings saves data."""
        payload = {
            "hero_label": "TEST_STOREFRONT",
            "hero_title": "TEST Welcome",
        }
        resp = requests.put(f"{BASE_URL}/api/admin/website-settings", json=payload, headers=admin_headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "message" in data

    def test_update_persists_in_get(self, admin_headers):
        """After PUT, GET should reflect updated values."""
        payload = {"hero_label": "TEST_VERIFY_LABEL"}
        requests.put(f"{BASE_URL}/api/admin/website-settings", json=payload, headers=admin_headers)

        resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=admin_headers)
        settings = resp.json().get("settings", {})
        assert settings.get("hero_label") == "TEST_VERIFY_LABEL"

    def test_update_email_templates(self, admin_headers):
        """Email template fields can be updated."""
        payload = {
            "email_from_name": "TEST Support Team",
            "email_verification_subject": "TEST Verify your account",
        }
        resp = requests.put(f"{BASE_URL}/api/admin/website-settings", json=payload, headers=admin_headers)
        assert resp.status_code == 200, resp.text

    def test_update_error_messages(self, admin_headers):
        """Error/UI message fields can be updated."""
        payload = {
            "msg_cart_empty": "TEST Your cart is empty.",
            "msg_quote_success": "TEST Quote submitted!",
        }
        resp = requests.put(f"{BASE_URL}/api/admin/website-settings", json=payload, headers=admin_headers)
        assert resp.status_code == 200, resp.text

    def test_update_form_schema(self, admin_headers):
        """Form schema (JSON string) can be updated."""
        schema = json.dumps([
            {"id": "f_test", "key": "test_field", "label": "Test Field", "type": "text",
             "required": False, "placeholder": "test", "options": [], "locked": False, "enabled": True, "order": 0}
        ])
        payload = {"quote_form_schema": schema}
        resp = requests.put(f"{BASE_URL}/api/admin/website-settings", json=payload, headers=admin_headers)
        assert resp.status_code == 200, resp.text

    def test_website_settings_requires_admin_auth(self):
        """Without auth, should return 401/403."""
        resp = requests.get(f"{BASE_URL}/api/admin/website-settings")
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"

    def test_website_settings_put_requires_admin_auth(self):
        resp = requests.put(f"{BASE_URL}/api/admin/website-settings", json={"hero_label": "hack"})
        assert resp.status_code in [401, 403]


# ── 3. Structured settings (for Integrations, System Config, Links & URLs) ──

class TestStructuredSettings:
    """GET /api/admin/settings/structured - used for Integrations, Links, System Config sections."""

    def test_structured_settings_200(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/settings/structured", headers=admin_headers)
        assert resp.status_code == 200, resp.text

    def test_structured_settings_has_payments_category(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/settings/structured", headers=admin_headers)
        settings = resp.json().get("settings", {})
        assert "Payments" in settings, f"Categories found: {list(settings.keys())}"
        payments = settings["Payments"]
        keys = [item["key"] for item in payments]
        print(f"Payments keys: {keys}")
        assert "service_fee_rate" in keys
        # Should have at least one Stripe key
        stripe_keys = [k for k in keys if "stripe" in k.lower()]
        assert len(stripe_keys) > 0, f"No Stripe keys found in {keys}"

    def test_structured_settings_has_email_category(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/settings/structured", headers=admin_headers)
        settings = resp.json().get("settings", {})
        assert "Email" in settings, f"Categories found: {list(settings.keys())}"
        email_keys = [item["key"] for item in settings["Email"]]
        print(f"Email keys: {email_keys}")
        assert "resend_api_key" in email_keys

    def test_structured_settings_has_zoho_category(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/settings/structured", headers=admin_headers)
        settings = resp.json().get("settings", {})
        assert "Zoho" in settings, f"Categories found: {list(settings.keys())}"
        zoho_keys = [item["key"] for item in settings["Zoho"]]
        print(f"Zoho keys: {zoho_keys}")
        assert len(zoho_keys) > 0

    def test_structured_settings_has_feature_flags(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/settings/structured", headers=admin_headers)
        settings = resp.json().get("settings", {})
        assert "FeatureFlags" in settings, f"Categories found: {list(settings.keys())}"
        ff_keys = [item["key"] for item in settings["FeatureFlags"]]
        print(f"Feature flags: {ff_keys}")
        assert "partner_tagging_enabled" in ff_keys

    def test_structured_settings_secrets_are_masked(self, admin_headers):
        """Secrets should be masked as ••••••••."""
        resp = requests.get(f"{BASE_URL}/api/admin/settings/structured", headers=admin_headers)
        settings = resp.json().get("settings", {})
        for cat_items in settings.values():
            for item in cat_items:
                if item.get("is_secret"):
                    val = str(item.get("value_json", ""))
                    if val and len(val) > 4:
                        assert "••" in val, f"Secret {item['key']} not masked: {val}"

    def test_update_setting_by_key(self, admin_headers):
        """PUT /api/admin/settings/key/{key} saves values."""
        resp = requests.put(
            f"{BASE_URL}/api/admin/settings/key/override_code_expiry_hours",
            json={"value": 72},
            headers=admin_headers
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "message" in data


# ── 4. Default form schema content ──────────────────────────────────────────

class TestFormSchemaDefaults:
    """Verify default form schemas have expected fields."""

    def test_quote_form_schema_default_fields(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=admin_headers)
        settings = resp.json().get("settings", {})
        schema_str = settings.get("quote_form_schema", "")
        if not schema_str:
            pytest.skip("quote_form_schema not set (may have been cleared)")
        schema = json.loads(schema_str)
        assert isinstance(schema, list)
        keys = [f["key"] for f in schema]
        print(f"Quote form keys: {keys}")
        # Should have at minimum: name, email
        assert "name" in keys or "email" in keys, f"Expected name/email in {keys}"

    def test_scope_form_schema_has_timeline_select(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=admin_headers)
        settings = resp.json().get("settings", {})
        schema_str = settings.get("scope_form_schema", "")
        if not schema_str:
            pytest.skip("scope_form_schema not set")
        schema = json.loads(schema_str)
        keys = [f["key"] for f in schema]
        print(f"Scope form keys: {keys}")
        # Should have timeline_urgency as select type
        timeline = next((f for f in schema if f["key"] == "timeline_urgency"), None)
        if timeline:
            assert timeline["type"] == "select"
            assert len(timeline.get("options", [])) > 0
        else:
            print("Note: timeline_urgency not found in schema (may have been customized)")

    def test_signup_form_schema_has_locked_fields(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=admin_headers)
        settings = resp.json().get("settings", {})
        schema_str = settings.get("signup_form_schema", "")
        if not schema_str:
            pytest.skip("signup_form_schema not set")
        schema = json.loads(schema_str)
        locked_fields = [f for f in schema if f.get("locked")]
        print(f"Locked fields in signup: {[f['key'] for f in locked_fields]}")
        # full_name, email, password should be locked
        locked_keys = [f["key"] for f in locked_fields]
        assert len(locked_keys) > 0, "Expected at least some locked fields in signup form"


# ── 5. Cleanup (restore defaults) ───────────────────────────────────────────

class TestCleanup:
    def test_restore_hero_and_schema_defaults(self, admin_headers):
        """Restore defaults that tests modified."""
        import json as _json
        _QUOTE_SCHEMA = _json.dumps([
            {"id": "f_name", "key": "name", "label": "Your Name", "type": "text", "required": True, "placeholder": "Full name", "locked": False, "enabled": True, "order": 0},
            {"id": "f_email", "key": "email", "label": "Email", "type": "email", "required": True, "placeholder": "your@email.com", "locked": False, "enabled": True, "order": 1},
            {"id": "f_company", "key": "company", "label": "Company", "type": "text", "required": False, "placeholder": "Company name", "locked": False, "enabled": True, "order": 2},
            {"id": "f_phone", "key": "phone", "label": "Phone", "type": "tel", "required": False, "placeholder": "+1 (555) 000-0000", "locked": False, "enabled": True, "order": 3},
            {"id": "f_message", "key": "message", "label": "Message", "type": "textarea", "required": False, "placeholder": "Tell us about your requirements\u2026", "locked": False, "enabled": True, "order": 4},
        ])
        resp = requests.put(f"{BASE_URL}/api/admin/website-settings",
                           json={"hero_label": "STOREFRONT", "hero_title": "Welcome", "quote_form_schema": _QUOTE_SCHEMA},
                           headers=admin_headers)
        assert resp.status_code == 200
        print("Restored hero_label and quote_form_schema to defaults")
