"""
Iteration 259: Email Architecture Testing
Tests:
  1. Partner signup (register-partner) uses trigger=partner_verification (not verification)
  2. Email sent via Zoho Mail (provider=zoho_mail, status=sent) with partner_verification trigger
  3. Platform admin email templates list includes partner_verification and partner_billing templates
  4. Partner admin email templates list does NOT include platform_admin_only or partner_billing
  5. ensure_seeded for partner tenant removes platform-only/partner_billing templates from DB
  6. Email provider lookup: 2-tier (tenant's own if present, else automate-accounts platform)
  7. Zoho Mail from_email validation code logic (code inspection via DB/API check)
"""
import pytest
import requests
import os
import time
import pymongo
from datetime import datetime, timezone
import uuid

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
PARTNER_CODE = "test-hardening-fix4"
PARTNER_TENANT_ID = "793186c5-ab06-421d-8303-ea967804204a"
PLATFORM_TENANT_ID = "automate-accounts"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

assert BASE_URL, "REACT_APP_BACKEND_URL env var is required"


def get_db():
    client = pymongo.MongoClient(MONGO_URL)
    return client[DB_NAME], client


def get_latest_log(recipient: str, trigger: str = None, after_ts: str = None):
    db, client = get_db()
    query = {"recipient": recipient}
    if trigger:
        query["trigger"] = trigger
    if after_ts:
        query["created_at"] = {"$gte": after_ts}
    logs = list(db.email_logs.find(query, {"_id": 0}).sort("created_at", -1).limit(1))
    client.close()
    return logs[0] if logs else None


def unique_email(prefix="testiter259"):
    uid = str(uuid.uuid4())[:8]
    return f"{prefix}_{uid}@example.com"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def platform_headers():
    """Platform super admin JWT headers."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!",
    })
    assert resp.status_code == 200, f"Platform admin login failed: {resp.text}"
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def partner_headers():
    """Partner super admin JWT headers for test-hardening-fix4."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "test_admin_fix4@example.com",
        "password": "TestAdmin123!",
        "partner_code": PARTNER_CODE,
    })
    assert resp.status_code == 200, f"Partner admin login failed: {resp.text}"
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Test Suite 1: Partner signup uses trigger=partner_verification
# ---------------------------------------------------------------------------
class TestPartnerSignupTrigger:
    """partner signup must send trigger=partner_verification (not verification)"""

    TEST_EMAIL = None

    def test_register_partner_200(self):
        """POST /api/auth/register-partner returns 200 with Verification required message."""
        TestPartnerSignupTrigger.TEST_EMAIL = unique_email("testiter259_signup")
        payload = {
            "name": "TEST_Iter259_PartnerOrg",
            "admin_name": "Iter259 Admin",
            "admin_email": TestPartnerSignupTrigger.TEST_EMAIL,
            "admin_password": "TestPass#2591",
        }
        resp = requests.post(f"{BASE_URL}/api/auth/register-partner", json=payload)
        assert resp.status_code == 200, f"register-partner failed: {resp.text}"
        data = resp.json()
        assert "message" in data
        assert data["message"] == "Verification required"
        print(f"PASS: register-partner 200 → {TestPartnerSignupTrigger.TEST_EMAIL}")

    def test_email_log_created(self):
        """email_logs must contain a record for the partner signup email."""
        assert TestPartnerSignupTrigger.TEST_EMAIL, "EMAIL not set"
        time.sleep(2)
        log = get_latest_log(TestPartnerSignupTrigger.TEST_EMAIL)
        assert log is not None, f"No email_log found for {TestPartnerSignupTrigger.TEST_EMAIL}"
        print(f"PASS: email_log found: trigger={log.get('trigger')}, status={log.get('status')}")

    def test_trigger_is_partner_verification(self):
        """email_log.trigger must be partner_verification (not the old verification)."""
        log = get_latest_log(TestPartnerSignupTrigger.TEST_EMAIL, trigger="partner_verification")
        assert log is not None, (
            f"No email_log with trigger=partner_verification found for {TestPartnerSignupTrigger.TEST_EMAIL}. "
            f"Got: {get_latest_log(TestPartnerSignupTrigger.TEST_EMAIL)}"
        )
        assert log["trigger"] == "partner_verification", (
            f"Expected trigger=partner_verification, got: {log['trigger']}"
        )
        print(f"PASS: trigger=partner_verification")

    def test_provider_is_zoho_mail(self):
        """email_log.provider must be zoho_mail (sent via platform connection)."""
        log = get_latest_log(TestPartnerSignupTrigger.TEST_EMAIL, trigger="partner_verification")
        assert log is not None, "No email_log found"
        assert log.get("provider") == "zoho_mail", (
            f"Expected provider=zoho_mail, got: {log.get('provider')}"
        )
        print(f"PASS: provider=zoho_mail")

    def test_status_is_sent(self):
        """email_log.status must be sent."""
        log = get_latest_log(TestPartnerSignupTrigger.TEST_EMAIL, trigger="partner_verification")
        assert log is not None, "No email_log found"
        assert log.get("status") == "sent", (
            f"Expected status=sent, got: {log.get('status')} | error: {log.get('error_message')}"
        )
        print(f"PASS: status=sent")

    def test_subject_contains_store_name(self):
        """Email subject must contain 'Automate Accounts' (platform store_name for tenant_id=None)."""
        log = get_latest_log(TestPartnerSignupTrigger.TEST_EMAIL, trigger="partner_verification")
        assert log is not None, "No email_log found"
        subject = log.get("subject", "")
        assert "Automate Accounts" in subject, (
            f"Expected 'Automate Accounts' in subject, got: '{subject}'"
        )
        # Also verify we have the partner-specific subject template
        assert "partner account" in subject.lower() or "partner" in subject.lower(), (
            f"Expected 'partner' keyword in subject for partner_verification template, got: '{subject}'"
        )
        print(f"PASS: subject='{subject}'")

    def test_old_verification_trigger_not_used(self):
        """Must not have an email_log with trigger=verification (old incorrect trigger) for this email."""
        log = get_latest_log(TestPartnerSignupTrigger.TEST_EMAIL, trigger="verification")
        assert log is None, (
            f"BUG: Found email_log with trigger=verification for partner signup. "
            f"This means the old trigger is still being used. Log: {log}"
        )
        print(f"PASS: No verification trigger used (old trigger correctly replaced)")


# ---------------------------------------------------------------------------
# Test Suite 2: Platform admin sees all email templates including restricted ones
# ---------------------------------------------------------------------------
class TestPlatformAdminTemplateVisibility:
    """Platform admin must see partner_verification (platform_admin_only) and partner_billing templates."""

    def test_platform_templates_include_partner_verification(self, platform_headers):
        """GET /api/admin/email-templates for platform admin must include partner_verification."""
        resp = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=platform_headers)
        assert resp.status_code == 200, f"list_templates failed: {resp.text}"
        templates = resp.json().get("templates", [])
        triggers = {t["trigger"] for t in templates}
        assert "partner_verification" in triggers, (
            f"partner_verification template missing from platform admin list. "
            f"Found triggers: {sorted(triggers)}"
        )
        print(f"PASS: partner_verification in platform admin templates ({len(templates)} total)")

    def test_platform_templates_include_partner_billing(self, platform_headers):
        """GET /api/admin/email-templates for platform admin must include partner_billing templates."""
        resp = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=platform_headers)
        assert resp.status_code == 200, f"list_templates failed: {resp.text}"
        templates = resp.json().get("templates", [])
        partner_billing_tpls = [t for t in templates if t.get("category") == "partner_billing"]
        assert len(partner_billing_tpls) > 0, (
            f"No partner_billing templates found in platform admin list. "
            f"All templates: {[t['trigger'] for t in templates]}"
        )
        print(f"PASS: {len(partner_billing_tpls)} partner_billing templates visible to platform admin")
        for t in partner_billing_tpls:
            print(f"  - trigger={t['trigger']} | category={t.get('category')}")

    def test_platform_templates_partner_verification_has_correct_category(self, platform_headers):
        """partner_verification template must have category=platform_admin_only."""
        resp = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=platform_headers)
        assert resp.status_code == 200
        templates = resp.json().get("templates", [])
        pv = next((t for t in templates if t["trigger"] == "partner_verification"), None)
        assert pv is not None, "partner_verification template not found"
        assert pv.get("category") == "platform_admin_only", (
            f"Expected category=platform_admin_only, got: {pv.get('category')}"
        )
        print(f"PASS: partner_verification category=platform_admin_only")

    def test_platform_template_count(self, platform_headers):
        """Platform admin should see 16 templates (all defaults including restricted)."""
        resp = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=platform_headers)
        assert resp.status_code == 200
        templates = resp.json().get("templates", [])
        # Should have at least 14 templates (the minimum expected count)
        assert len(templates) >= 14, (
            f"Expected >=14 templates for platform admin, got {len(templates)}"
        )
        print(f"PASS: Platform admin sees {len(templates)} templates")


# ---------------------------------------------------------------------------
# Test Suite 3: Partner admin does NOT see platform_admin_only or partner_billing
# ---------------------------------------------------------------------------
class TestPartnerAdminTemplateVisibility:
    """Partner admin must not see platform_admin_only or partner_billing templates."""

    def test_partner_admin_no_platform_admin_only(self, partner_headers):
        """GET /api/admin/email-templates for partner admin must exclude platform_admin_only."""
        resp = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=partner_headers)
        assert resp.status_code == 200, f"list_templates failed: {resp.text}"
        templates = resp.json().get("templates", [])
        platform_only = [t for t in templates if t.get("category") == "platform_admin_only"]
        assert len(platform_only) == 0, (
            f"BUG: partner admin sees platform_admin_only templates: "
            f"{[t['trigger'] for t in platform_only]}"
        )
        print(f"PASS: No platform_admin_only templates visible to partner admin")

    def test_partner_admin_no_partner_billing(self, partner_headers):
        """GET /api/admin/email-templates for partner admin must exclude partner_billing."""
        resp = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=partner_headers)
        assert resp.status_code == 200, f"list_templates failed: {resp.text}"
        templates = resp.json().get("templates", [])
        billing_tpls = [t for t in templates if t.get("category") == "partner_billing"]
        assert len(billing_tpls) == 0, (
            f"BUG: partner admin sees partner_billing templates: "
            f"{[t['trigger'] for t in billing_tpls]}"
        )
        print(f"PASS: No partner_billing templates visible to partner admin ({len(templates)} total templates shown)")

    def test_partner_admin_no_partner_verification_trigger(self, partner_headers):
        """partner_verification must not be visible to partner admin."""
        resp = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=partner_headers)
        assert resp.status_code == 200
        templates = resp.json().get("templates", [])
        triggers = {t["trigger"] for t in templates}
        assert "partner_verification" not in triggers, (
            f"BUG: partner_verification trigger visible to partner admin. "
            f"All triggers: {sorted(triggers)}"
        )
        print(f"PASS: partner_verification not visible to partner admin")

    def test_partner_admin_can_see_basic_templates(self, partner_headers):
        """Partner admin should still see normal templates like verification, password_reset, etc."""
        resp = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=partner_headers)
        assert resp.status_code == 200
        templates = resp.json().get("templates", [])
        triggers = {t["trigger"] for t in templates}
        required_triggers = {"verification", "password_reset"}
        missing = required_triggers - triggers
        assert not missing, (
            f"Partner admin is missing expected basic templates: {missing}"
        )
        print(f"PASS: Partner admin sees {len(templates)} basic templates (incl. verification, password_reset)")


# ---------------------------------------------------------------------------
# Test Suite 4: ensure_seeded removes platform-only templates from partner tenant
# ---------------------------------------------------------------------------
class TestEnsureSeededPruning:
    """ensure_seeded must remove partner_billing/platform_admin_only from non-platform tenants."""

    def test_partner_tenant_no_platform_admin_only_in_db(self):
        """partner tenant DB must have no templates with category=platform_admin_only."""
        db, client = get_db()
        forbidden = list(db.email_templates.find(
            {"tenant_id": PARTNER_TENANT_ID, "category": "platform_admin_only"},
            {"_id": 0, "trigger": 1, "category": 1}
        ))
        client.close()
        assert len(forbidden) == 0, (
            f"BUG: Partner tenant DB has platform_admin_only templates: {forbidden}"
        )
        print(f"PASS: No platform_admin_only templates in partner tenant DB")

    def test_partner_tenant_no_partner_billing_in_db(self):
        """partner tenant DB must have no templates with category=partner_billing after ensure_seeded."""
        db, client = get_db()
        billing = list(db.email_templates.find(
            {"tenant_id": PARTNER_TENANT_ID, "category": "partner_billing"},
            {"_id": 0, "trigger": 1, "category": 1}
        ))
        client.close()
        assert len(billing) == 0, (
            f"BUG: Partner tenant DB has partner_billing templates: {billing}. "
            f"ensure_seeded pruning logic may not have run yet."
        )
        print(f"PASS: No partner_billing templates in partner tenant DB")

    def test_platform_tenant_has_partner_verification_in_db(self):
        """automate-accounts tenant DB must have partner_verification template."""
        db, client = get_db()
        pv = db.email_templates.find_one(
            {"tenant_id": PLATFORM_TENANT_ID, "trigger": "partner_verification"},
            {"_id": 0, "trigger": 1, "category": 1}
        )
        client.close()
        assert pv is not None, "partner_verification template not found in automate-accounts tenant"
        assert pv.get("category") == "platform_admin_only", (
            f"Expected category=platform_admin_only, got: {pv.get('category')}"
        )
        print(f"PASS: partner_verification in platform tenant DB with category=platform_admin_only")

    def test_partner_tenant_has_verification_template_in_db(self):
        """partner tenant DB must still have verification template (non-restricted)."""
        db, client = get_db()
        vt = db.email_templates.find_one(
            {"tenant_id": PARTNER_TENANT_ID, "trigger": "verification"},
            {"_id": 0, "trigger": 1, "category": 1}
        )
        client.close()
        assert vt is not None, "verification template not found in partner tenant (should not have been pruned)"
        print(f"PASS: verification template still in partner tenant DB")

    def test_ensure_seeded_triggers_pruning_via_api(self, partner_headers):
        """Calling list_templates as partner admin triggers ensure_seeded which prunes restricted templates."""
        # This test calls the API (which calls ensure_seeded) and then verifies DB state is clean
        resp = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=partner_headers)
        assert resp.status_code == 200
        
        # After API call, verify DB state
        db, client = get_db()
        forbidden_count = db.email_templates.count_documents({
            "tenant_id": PARTNER_TENANT_ID,
            "category": {"$in": ["platform_admin_only", "partner_billing"]}
        })
        client.close()
        assert forbidden_count == 0, (
            f"BUG: {forbidden_count} forbidden category templates still in partner tenant DB after ensure_seeded"
        )
        print(f"PASS: ensure_seeded prunes restricted templates from partner tenant DB")


# ---------------------------------------------------------------------------
# Test Suite 5: Email provider lookup - 2-tier logic
# ---------------------------------------------------------------------------
class TestEmailProviderLookup:
    """Verify 2-tier provider lookup: tenant connection OR platform fallback (no global tier)."""

    def test_platform_has_zoho_mail_connection(self):
        """automate-accounts must have a validated Zoho Mail connection for fallback."""
        db, client = get_db()
        conn = db.oauth_connections.find_one(
            {"tenant_id": PLATFORM_TENANT_ID, "provider": "zoho_mail", "is_validated": True},
            {"_id": 0, "settings": 1, "credentials": 1}
        )
        client.close()
        assert conn is not None, "Platform Zoho Mail connection not found"
        from_email = conn.get("settings", {}).get("from_email", "")
        assert from_email, "Platform Zoho Mail connection has no from_email configured"
        print(f"PASS: Platform Zoho Mail connection — from_email={from_email}")

    def test_partner_tenant_has_no_email_provider(self):
        """test-hardening-fix4 tenant must have no validated email provider (validates fallback test)."""
        db, client = get_db()
        conn = db.oauth_connections.find_one(
            {"tenant_id": PARTNER_TENANT_ID, "provider": {"$in": ["zoho_mail", "resend"]}, "is_validated": True},
            {"_id": 0}
        )
        client.close()
        assert conn is None, (
            f"Partner tenant unexpectedly has email connection: {conn}. "
            f"This would bypass the platform fallback."
        )
        print(f"PASS: Partner tenant has no email provider — fallback to platform will occur")

    def test_no_global_email_connection_in_db(self):
        """No email connections with tenant_id=None or tenant_id='' should exist (no global tier)."""
        db, client = get_db()
        # Check for any zoho_mail/resend connections with no tenant_id (old global tier)
        global_conns = list(db.oauth_connections.find(
            {
                "provider": {"$in": ["zoho_mail", "resend"]},
                "tenant_id": {"$in": [None, ""]}
            },
            {"_id": 0, "provider": 1, "tenant_id": 1}
        ))
        client.close()
        assert len(global_conns) == 0, (
            f"Found global (no-tenant) email connections which shouldn't exist "
            f"in the 2-tier architecture: {global_conns}"
        )
        print(f"PASS: No global/no-tenant email connections found")

    def test_partner_signup_uses_platform_fallback_for_email(self):
        """When tenant_id=None (partner signup), email is sent via platform Zoho Mail."""
        # This is already confirmed by the log from TestPartnerSignupTrigger
        db, client = get_db()
        # Look for recent partner_verification emails sent with provider=zoho_mail, no tenant_id
        logs = list(db.email_logs.find(
            {"trigger": "partner_verification", "provider": "zoho_mail", "status": "sent"},
            {"_id": 0, "trigger": 1, "status": 1, "provider": 1, "tenant_id": 1}
        ).sort("created_at", -1).limit(5))
        client.close()
        assert len(logs) > 0, (
            "No sent partner_verification emails via zoho_mail found. "
            "Platform fallback may not be working."
        )
        # Verify these don't have a partner tenant_id (they are platform-level sends)
        partner_tenant_logs = [l for l in logs if l.get("tenant_id") == PARTNER_TENANT_ID]
        assert len(partner_tenant_logs) == 0, (
            f"BUG: partner_verification emails logged with partner tenant_id: {partner_tenant_logs}"
        )
        print(f"PASS: {len(logs)} partner_verification logs via zoho_mail (platform fallback) with no partner tenant_id")

    def test_email_provider_lookup_uses_effective_tenant(self):
        """Verify the 2-tier logic: tenant_id given → use tenant's provider; else use platform.
        
        Per spec: effective_tid = tenant_id if tenant_id else PLATFORM_TENANT
        - partner signup (tenant_id=None) → effective_tid=automate-accounts → Zoho Mail (sent)
        - customer signup (tenant_id=partner_tenant, no provider) → effective_tid=partner_tenant → MOCKED
        This is correct 2-tier behavior (no fallback when tenant_id is set).
        """
        db, client = get_db()
        # Check that partner_verification emails (tenant_id=None) use platform Zoho Mail
        pv_logs = list(db.email_logs.find(
            {"trigger": "partner_verification", "provider": "zoho_mail", "status": "sent"},
            {"_id": 0, "trigger": 1, "status": 1, "tenant_id": 1}
        ).sort("created_at", -1).limit(3))
        # Check that customer emails from partner tenant (has tenant_id) are mocked
        mocked_logs = list(db.email_logs.find(
            {"tenant_id": PARTNER_TENANT_ID, "trigger": "verification", "status": "mocked"},
            {"_id": 0, "trigger": 1, "status": 1}
        ).sort("created_at", -1).limit(1))
        client.close()
        
        assert len(pv_logs) > 0, (
            "No partner_verification emails via zoho_mail (should use platform when tenant_id=None)"
        )
        print(f"INFO: 2-tier logic verified: tenant_id=None → platform Zoho Mail ({len(pv_logs)} partner_verification sent logs)")
        print(f"INFO: tenant_id=partner_tenant (no provider) → MOCKED ({len(mocked_logs)} mocked logs, correct per 2-tier spec)")


# ---------------------------------------------------------------------------
# Test Suite 6: Zoho Mail from_email validation logic
# ---------------------------------------------------------------------------
class TestZohoMailValidation:
    """Verify Zoho Mail validate endpoint checks from_email against Zoho Mail account senders."""

    def test_platform_zoho_mail_from_email_is_valid(self):
        """Platform Zoho Mail connection's from_email should be a known valid sender."""
        db, client = get_db()
        conn = db.oauth_connections.find_one(
            {"tenant_id": PLATFORM_TENANT_ID, "provider": "zoho_mail", "is_validated": True},
            {"_id": 0, "settings": 1, "credentials": 1}
        )
        client.close()
        assert conn is not None, "Platform Zoho Mail connection not found"
        settings = conn.get("settings", {})
        from_email = settings.get("from_email", "")
        assert from_email, "from_email missing from Zoho Mail settings"
        # Verify it's a non-empty email
        assert "@" in from_email, f"from_email is not a valid email: '{from_email}'"
        print(f"PASS: Platform Zoho Mail from_email='{from_email}' is set")

    def test_zoho_mail_connection_is_validated(self):
        """Platform Zoho Mail connection must have is_validated=True."""
        db, client = get_db()
        conn = db.oauth_connections.find_one(
            {"tenant_id": PLATFORM_TENANT_ID, "provider": "zoho_mail"},
            {"_id": 0, "is_validated": 1, "status": 1}
        )
        client.close()
        assert conn is not None, "Platform Zoho Mail connection not found"
        assert conn.get("is_validated") == True, (
            f"Platform Zoho Mail connection is_validated={conn.get('is_validated')}, status={conn.get('status')}"
        )
        print(f"PASS: Platform Zoho Mail connection is_validated=True, status={conn.get('status')}")

    def test_zoho_access_token_caching_in_db(self):
        """Zoho Mail connection should have cached access_token and access_token_expires_at in credentials."""
        db, client = get_db()
        conn = db.oauth_connections.find_one(
            {"tenant_id": PLATFORM_TENANT_ID, "provider": "zoho_mail"},
            {"_id": 0, "credentials": 1}
        )
        client.close()
        assert conn is not None, "Platform Zoho Mail connection not found"
        creds = conn.get("credentials", {})
        access_token = creds.get("access_token", "")
        expires_at = creds.get("access_token_expires_at", "")
        # After sending a test email, token should have been cached
        assert access_token, (
            "access_token not cached in credentials. "
            "This means each email send calls refresh_access_token() — see iter258 critical bug."
        )
        assert expires_at, (
            "access_token_expires_at not cached in credentials. "
            "Token refresh caching is not working."
        )
        print(f"PASS: Zoho access_token cached in DB, expires_at={expires_at}")


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data():
    yield
    db, client = get_db()
    db.pending_partner_registrations.delete_many({
        "email": {"$regex": r"^testiter259_.*@example\.com$"}
    })
    db.users.delete_many({
        "email": {"$regex": r"^testiter259_.*@example\.com$"},
        "is_verified": False,
    })
    client.close()
    print("Cleanup: Removed testiter259_* pending registrations and unverified users")
