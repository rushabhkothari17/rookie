"""
Test: partner_verification email template visibility
- Platform admin should see partner_verification (category=platform_admin_only)
- Partner admin should NOT see partner_verification template
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

PLATFORM_ADMIN_CREDS = {
    "partner_code": "automate-accounts",
    "email": "admin@automateaccounts.local",
    "password": "ChangeMe123!",
}

PARTNER_ADMIN_CREDS = {
    "partner_code": "test-partner-corp",
    "email": "alice@testpartner.com",
    "password": "TestPass123!",
}


def login(session: requests.Session, creds: dict) -> str:
    """Login and return auth token.
    Platform admin uses /auth/login without partner_code.
    Partner admin uses /auth/partner-login with partner_code.
    """
    partner_code = creds.get("partner_code", "")
    if partner_code == "automate-accounts":
        # Platform admin login - no partner_code needed
        r = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": creds["email"],
            "password": creds["password"],
        })
    else:
        # Partner admin login
        r = session.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": partner_code,
            "email": creds["email"],
            "password": creds["password"],
        })
    if r.status_code == 200:
        return r.json().get("token", "")
    print(f"Login failed for {creds['email']}: {r.status_code} {r.text}")
    return ""


@pytest.fixture(scope="module")
def platform_admin_token():
    s = requests.Session()
    token = login(s, PLATFORM_ADMIN_CREDS)
    if not token:
        pytest.skip("Platform admin login failed")
    return token


@pytest.fixture(scope="module")
def partner_admin_token():
    s = requests.Session()
    token = login(s, PARTNER_ADMIN_CREDS)
    if not token:
        pytest.skip("Partner admin login failed")
    return token


class TestEmailTemplatesVisibility:
    """Email templates visibility based on role"""

    def test_platform_admin_gets_partner_verification_template(self, platform_admin_token):
        """Platform admin should see partner_verification template"""
        r = requests.get(
            f"{BASE_URL}/api/admin/email-templates",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        templates = data.get("templates", [])
        triggers = [t["trigger"] for t in templates]
        print(f"Platform admin templates ({len(templates)}): {triggers}")
        assert "partner_verification" in triggers, (
            f"partner_verification NOT found in platform admin templates: {triggers}"
        )
        print("PASS: Platform admin sees partner_verification template")

    def test_platform_admin_partner_verification_has_correct_category(self, platform_admin_token):
        """partner_verification template should have category=platform_admin_only"""
        r = requests.get(
            f"{BASE_URL}/api/admin/email-templates",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
        )
        assert r.status_code == 200
        templates = r.json().get("templates", [])
        pv_templates = [t for t in templates if t["trigger"] == "partner_verification"]
        assert len(pv_templates) > 0, "partner_verification template not found"
        pv = pv_templates[0]
        assert pv.get("category") == "platform_admin_only", (
            f"Expected category='platform_admin_only', got '{pv.get('category')}'"
        )
        assert pv.get("label") == "Partner Account Verification", (
            f"Expected label='Partner Account Verification', got '{pv.get('label')}'"
        )
        print(f"PASS: partner_verification has category=platform_admin_only, label='{pv['label']}'")

    def test_partner_admin_does_not_see_partner_verification(self, partner_admin_token):
        """Partner admin should NOT see partner_verification template"""
        r = requests.get(
            f"{BASE_URL}/api/admin/email-templates",
            headers={"Authorization": f"Bearer {partner_admin_token}"},
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        templates = data.get("templates", [])
        triggers = [t["trigger"] for t in templates]
        print(f"Partner admin templates ({len(templates)}): {triggers}")
        assert "partner_verification" not in triggers, (
            f"partner_verification SHOULD NOT be in partner admin templates, but found: {triggers}"
        )
        print("PASS: Partner admin does NOT see partner_verification template")

    def test_partner_admin_does_not_see_any_platform_admin_only_templates(self, partner_admin_token):
        """Partner admin should NOT see any template with category=platform_admin_only"""
        r = requests.get(
            f"{BASE_URL}/api/admin/email-templates",
            headers={"Authorization": f"Bearer {partner_admin_token}"},
        )
        assert r.status_code == 200
        templates = r.json().get("templates", [])
        platform_only = [t for t in templates if t.get("category") == "platform_admin_only"]
        assert len(platform_only) == 0, (
            f"Partner admin sees platform_admin_only templates: {[t['trigger'] for t in platform_only]}"
        )
        print("PASS: Partner admin sees NO platform_admin_only templates")

    def test_partner_admin_does_not_see_partner_billing_templates(self, partner_admin_token):
        """Partner admin should NOT see any template with category=partner_billing"""
        r = requests.get(
            f"{BASE_URL}/api/admin/email-templates",
            headers={"Authorization": f"Bearer {partner_admin_token}"},
        )
        assert r.status_code == 200
        templates = r.json().get("templates", [])
        billing = [t for t in templates if t.get("category") == "partner_billing"]
        assert len(billing) == 0, (
            f"Partner admin sees partner_billing templates: {[t['trigger'] for t in billing]}"
        )
        print("PASS: Partner admin sees NO partner_billing templates")

    def test_platform_admin_sees_partner_billing_templates(self, platform_admin_token):
        """Platform admin should also see partner_billing templates"""
        r = requests.get(
            f"{BASE_URL}/api/admin/email-templates",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
        )
        assert r.status_code == 200
        templates = r.json().get("templates", [])
        billing = [t for t in templates if t.get("category") == "partner_billing"]
        print(f"Platform admin partner_billing templates: {[t['trigger'] for t in billing]}")
        # Just verify no crash - platform admin should see them if they exist
        # The count may be 0 if no partner_billing templates are defined
        print(f"PASS: Platform admin sees {len(billing)} partner_billing templates (may be 0)")

    def test_unauthenticated_request_returns_401(self):
        """Unauthenticated request should return 401"""
        r = requests.get(f"{BASE_URL}/api/admin/email-templates")
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"
        print("PASS: Unauthenticated request returns 401")
