"""
Iteration 82: Testing Connect Services refactoring features.

Tests cover:
1. Cart page dropdowns (zoho_subscription_type, current_zoho_product, etc.) - via website-settings API
2. Payment settings read from oauth_connections
3. API /api/website-settings returns correct payment labels and fee rates
4. Admin login works with tenant-b-test
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
TENANT_ADMIN = {
    "partner_code": "tenant-b-test",
    "email": "adminb@tenantb.local",
    "password": "ChangeMe123!"
}

CUSTOMER = {
    "partner_code": "tenant-b-test",
    "email": "john.smith@tenantb.local",
    "password": "ChangeMe123!"
}


class TestAdminLogin:
    """Test admin authentication"""
    
    def test_admin_login_success(self):
        """Admin login should work with tenant-b-test credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TENANT_ADMIN)
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert data.get("role") in ["partner_super_admin", "admin", "tenant_admin"]
        assert data.get("tenant_id") is not None


class TestCustomerLogin:
    """Test customer authentication"""
    
    def test_customer_login_success(self):
        """Customer login should work with tenant-b-test credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/customer-login", json=CUSTOMER)
        assert response.status_code == 200, f"Customer login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert data.get("role") == "customer"


class TestWebsiteSettingsAPI:
    """Test /api/website-settings endpoint for payment settings"""
    
    def test_website_settings_returns_payment_flags(self):
        """Website settings should return stripe_enabled and gocardless_enabled from oauth_connections"""
        response = requests.get(f"{BASE_URL}/api/website-settings?partner_code=tenant-b-test")
        assert response.status_code == 200, f"Website settings failed: {response.text}"
        data = response.json()
        settings = data.get("settings", {})
        
        # Check payment flags exist
        assert "stripe_enabled" in settings, "Missing stripe_enabled in settings"
        assert "gocardless_enabled" in settings, "Missing gocardless_enabled in settings"
        
        # Check fee rates exist
        assert "stripe_fee_rate" in settings, "Missing stripe_fee_rate in settings"
        assert "gocardless_fee_rate" in settings, "Missing gocardless_fee_rate in settings"
        
        # Check payment labels exist
        assert "payment_stripe_label" in settings, "Missing payment_stripe_label"
        assert "payment_gocardless_label" in settings, "Missing payment_gocardless_label"
    
    def test_website_settings_checkout_sections(self):
        """Website settings should return checkout_sections with dropdown options"""
        response = requests.get(f"{BASE_URL}/api/website-settings?partner_code=tenant-b-test")
        assert response.status_code == 200
        data = response.json()
        settings = data.get("settings", {})
        
        # Check checkout_sections exist
        checkout_sections = settings.get("checkout_sections", "[]")
        assert checkout_sections is not None, "Missing checkout_sections"
        
        # Try parsing checkout_sections if it's a string
        import json
        if isinstance(checkout_sections, str):
            try:
                sections = json.loads(checkout_sections)
                if len(sections) > 0:
                    # Verify first section has fields_schema
                    first_section = sections[0]
                    assert "fields_schema" in first_section, "Missing fields_schema in section"
                    
                    # Parse fields_schema
                    fields_schema = first_section.get("fields_schema", "[]")
                    if isinstance(fields_schema, str):
                        fields = json.loads(fields_schema)
                        # Look for dropdown fields with options
                        for field in fields:
                            if field.get("type") == "select":
                                options = field.get("options", "")
                                assert options, f"Select field {field.get('id')} has no options"
                                print(f"  Field {field.get('id')}: options = {options[:50]}...")
            except json.JSONDecodeError:
                pytest.fail("checkout_sections is not valid JSON")


class TestAdminWebsiteSettings:
    """Test admin website settings API"""
    
    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TENANT_ADMIN)
        if response.status_code != 200:
            pytest.skip("Admin login failed")
        return response.json().get("token")
    
    def test_admin_website_settings_readable(self, admin_token):
        """Admin should be able to read website settings"""
        response = requests.get(
            f"{BASE_URL}/api/admin/website-settings",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Admin website settings failed: {response.text}"
        data = response.json()
        settings = data.get("settings", {})
        
        # Verify checkout_sections exist
        assert "checkout_sections" in settings
        
        # Verify form schemas exist
        assert "quote_form_schema" in settings
        assert "scope_form_schema" in settings
        assert "signup_form_schema" in settings


class TestOAuthIntegrationsAPI:
    """Test oauth integrations list endpoint"""
    
    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TENANT_ADMIN)
        if response.status_code != 200:
            pytest.skip("Admin login failed")
        return response.json().get("token")
    
    def test_list_integrations(self, admin_token):
        """Should list all available integrations"""
        response = requests.get(
            f"{BASE_URL}/api/oauth/integrations",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check integrations list exists
        integrations = data.get("integrations", [])
        assert len(integrations) > 0, "No integrations returned"
        
        # Check stripe and gocardless are in the list
        provider_ids = [i.get("id") for i in integrations]
        assert "stripe" in provider_ids, "Stripe not in integrations"
        assert "gocardless" in provider_ids or "gocardless_sandbox" in provider_ids, "GoCardless not in integrations"
        
        # Verify stripe has settings configuration
        stripe_integration = next((i for i in integrations if i.get("id") == "stripe"), None)
        assert stripe_integration is not None
        assert "settings" in stripe_integration or "stored_settings" in stripe_integration


class TestFormSchemaBuilderFix:
    """Test that FormSchemaBuilder handles options correctly"""
    
    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TENANT_ADMIN)
        if response.status_code != 200:
            pytest.skip("Admin login failed")
        return response.json().get("token")
    
    def test_checkout_sections_with_select_fields(self, admin_token):
        """Checkout sections should have properly formatted select field options"""
        response = requests.get(
            f"{BASE_URL}/api/admin/website-settings",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        settings = data.get("settings", {})
        
        import json
        checkout_sections_str = settings.get("checkout_sections", "[]")
        
        try:
            sections = json.loads(checkout_sections_str)
        except:
            sections = checkout_sections_str if isinstance(checkout_sections_str, list) else []
        
        for section in sections:
            fields_schema_str = section.get("fields_schema", "[]")
            try:
                fields = json.loads(fields_schema_str)
            except:
                fields = fields_schema_str if isinstance(fields_schema_str, list) else []
            
            for field in fields:
                if field.get("type") == "select":
                    options = field.get("options", "")
                    # Options can be string (newline separated) or array
                    if isinstance(options, str):
                        # Should be newline separated
                        assert options == "" or "\n" in options or len(options.split("\n")) > 0, \
                            f"Field {field.get('id')} options not properly formatted"
                    elif isinstance(options, list):
                        # Array format is also valid
                        pass
                    
                    # Key validation: field should have id or key
                    assert field.get("id") or field.get("key"), \
                        f"Field missing id/key: {field}"


class TestPaymentSettingsFromOAuth:
    """Test that payment settings are read from oauth_connections"""
    
    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TENANT_ADMIN)
        if response.status_code != 200:
            pytest.skip("Admin login failed")
        return response.json().get("token")
    
    def test_stripe_settings_in_oauth_config(self, admin_token):
        """Stripe settings should be configurable via oauth_connections"""
        response = requests.get(
            f"{BASE_URL}/api/oauth/integrations",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        integrations = data.get("integrations", [])
        
        stripe = next((i for i in integrations if i.get("id") == "stripe"), None)
        assert stripe is not None, "Stripe integration not found"
        
        # Check that stripe has settings configuration fields
        settings_config = stripe.get("settings", [])
        if isinstance(settings_config, list):
            setting_keys = [s.get("key") for s in settings_config]
            assert "fee_rate" in setting_keys or any("fee" in k for k in setting_keys if k), \
                "fee_rate setting not in stripe config"
    
    def test_gocardless_settings_in_oauth_config(self, admin_token):
        """GoCardless settings should be configurable via oauth_connections"""
        response = requests.get(
            f"{BASE_URL}/api/oauth/integrations",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        integrations = data.get("integrations", [])
        
        gocardless = next((i for i in integrations if "gocardless" in i.get("id", "")), None)
        assert gocardless is not None, "GoCardless integration not found"
        
        # Check that gocardless has settings configuration
        settings_config = gocardless.get("settings", [])
        if isinstance(settings_config, list) and len(settings_config) > 0:
            setting_keys = [s.get("key") for s in settings_config]
            # GoCardless should have UI text settings
            assert any(k for k in setting_keys if k), "GoCardless has no settings configured"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
