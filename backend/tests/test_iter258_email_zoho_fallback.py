"""
Iteration 258: Test email delivery via Zoho Mail for all auth flows.
Tests:
  - Partner signup OTP → Zoho Mail (provider=zoho_mail, status=sent)
  - Resend verification for partner → Zoho Mail
  - Customer signup OTP (via partner_code) → Zoho Mail (fallback from tenant with no provider)
  - Forgot password → Zoho Mail
  - Email subjects include correct store_name (not blank)
  - Platform fallback: when tenant has no email provider, automate-accounts Zoho Mail is used
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
PARTNER_CODE = "test-hardening-fix4"        # TEST_HardeningOrg
PARTNER_TENANT_ID = "793186c5-ab06-421d-8603-ea967804204a"  # filled below
PLATFORM_TENANT_ID = "automate-accounts"

# Use pymongo synchronous client for DB verification
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


def get_db():
    client = pymongo.MongoClient(MONGO_URL)
    return client[DB_NAME], client


def get_latest_log(recipient: str, trigger: str = None, after_ts: str = None):
    """Return the most recent email_log for a recipient, optionally filtered by trigger and timestamp."""
    db, client = get_db()
    query = {"recipient": recipient}
    if trigger:
        query["trigger"] = trigger
    if after_ts:
        query["created_at"] = {"$gte": after_ts}
    logs = list(db.email_logs.find(query, {"_id": 0}).sort("created_at", -1).limit(1))
    client.close()
    return logs[0] if logs else None


def ts_now():
    return datetime.now(timezone.utc).isoformat()


def unique_email(prefix="testiter258"):
    uid = str(uuid.uuid4())[:8]
    return f"{prefix}_{uid}@example.com"


# ---------------------------------------------------------------------------
# Helper: Login as platform super admin
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def admin_headers():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!",
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Helper: resolve the real partner tenant_id
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def partner_tenant_id():
    db, client = get_db()
    tenant = db.tenants.find_one({"code": PARTNER_CODE}, {"_id": 0, "id": 1})
    client.close()
    assert tenant, f"Tenant {PARTNER_CODE} not found in DB"
    return tenant["id"]


# ---------------------------------------------------------------------------
# Test 1: Partner signup sends OTP via Zoho Mail
# ---------------------------------------------------------------------------
class TestPartnerSignupEmail:
    """Partner signup (POST /api/auth/register-partner) sends OTP via Zoho Mail"""

    TEST_EMAIL = None

    def test_register_partner_200(self):
        TestPartnerSignupEmail.TEST_EMAIL = unique_email("testiter258_partner_signup")
        payload = {
            "name": "TEST_Iter258_PartnerOrg",
            "admin_name": "Iter258 Admin",
            "admin_email": TestPartnerSignupEmail.TEST_EMAIL,
            "admin_password": "TestPass#2581",
        }
        resp = requests.post(f"{BASE_URL}/api/auth/register-partner", json=payload)
        assert resp.status_code == 200, f"register-partner failed: {resp.text}"
        data = resp.json()
        assert "message" in data
        print(f"PASS: register-partner 200 for {TestPartnerSignupEmail.TEST_EMAIL}")

    def test_partner_signup_email_log_exists(self):
        """email_logs should have a record for the partner signup email"""
        assert TestPartnerSignupEmail.TEST_EMAIL, "email not set — run register test first"
        # Allow a second for async email processing
        time.sleep(2)
        log = get_latest_log(TestPartnerSignupEmail.TEST_EMAIL, trigger="verification")
        assert log is not None, f"No email_log found for {TestPartnerSignupEmail.TEST_EMAIL}"
        print(f"PASS: email_log exists: {log}")

    def test_partner_signup_email_provider_zoho(self):
        """email_log.provider should be zoho_mail"""
        log = get_latest_log(TestPartnerSignupEmail.TEST_EMAIL, trigger="verification")
        assert log is not None, "No email_log found"
        assert log.get("provider") == "zoho_mail", f"Expected provider=zoho_mail, got: {log.get('provider')}"
        print(f"PASS: provider=zoho_mail")

    def test_partner_signup_email_status_sent(self):
        """email_log.status should be 'sent'"""
        log = get_latest_log(TestPartnerSignupEmail.TEST_EMAIL, trigger="verification")
        assert log is not None, "No email_log found"
        assert log.get("status") == "sent", f"Expected status=sent, got: {log.get('status')} | error: {log.get('error_message')}"
        print(f"PASS: status=sent")

    def test_partner_signup_subject_contains_store_name(self):
        """Email subject should contain 'Automate Accounts' (not empty store_name)"""
        log = get_latest_log(TestPartnerSignupEmail.TEST_EMAIL, trigger="verification")
        assert log is not None, "No email_log found"
        subject = log.get("subject", "")
        assert "Automate Accounts" in subject, f"Expected 'Automate Accounts' in subject, got: '{subject}'"
        assert "Verify your  account" not in subject, f"Subject has empty store_name: '{subject}'"
        print(f"PASS: subject='{subject}'")

    def test_partner_signup_no_tenant_id_in_log(self):
        """For partner signup, tenant_id should be absent (since it's platform-level)"""
        log = get_latest_log(TestPartnerSignupEmail.TEST_EMAIL, trigger="verification")
        assert log is not None, "No email_log found"
        # tenant_id may be absent or None — either is acceptable
        # The important thing is it doesn't belong to the partner tenant
        tid = log.get("tenant_id")
        assert tid != "793186c5-ab06-421d-8303-ea967804204a", f"Unexpected partner tenant_id in log: {tid}"
        print(f"PASS: tenant_id in log={tid} (not the partner tenant)")


# ---------------------------------------------------------------------------
# Test 2: Resend verification for partner sends via Zoho Mail
# ---------------------------------------------------------------------------
class TestResendPartnerVerificationEmail:
    """POST /api/auth/resend-verification-email for pending partner → Zoho Mail"""

    TEST_EMAIL = None

    def test_setup_pending_partner(self):
        """Create a new pending partner registration to test resend"""
        TestResendPartnerVerificationEmail.TEST_EMAIL = unique_email("testiter258_resend_partner")
        payload = {
            "name": "TEST_Iter258_ResendOrg",
            "admin_name": "Iter258 Resend Admin",
            "admin_email": TestResendPartnerVerificationEmail.TEST_EMAIL,
            "admin_password": "TestPass#2582",
        }
        resp = requests.post(f"{BASE_URL}/api/auth/register-partner", json=payload)
        assert resp.status_code == 200, f"Setup register-partner failed: {resp.text}"
        # Wait to avoid Zoho token refresh rate limiting on rapid successive calls
        time.sleep(5)
        print(f"PASS: setup pending partner {TestResendPartnerVerificationEmail.TEST_EMAIL}")

    def test_resend_verification_email_200(self):
        """POST /api/auth/resend-verification-email returns 200"""
        assert TestResendPartnerVerificationEmail.TEST_EMAIL
        resp = requests.post(f"{BASE_URL}/api/auth/resend-verification-email", json={
            "email": TestResendPartnerVerificationEmail.TEST_EMAIL,
        })
        assert resp.status_code == 200, f"resend-verification-email failed: {resp.text}"
        print(f"PASS: resend-verification-email 200")

    def test_resend_partner_email_provider_zoho(self):
        """Resend email_log.provider should be zoho_mail"""
        time.sleep(2)
        log = get_latest_log(TestResendPartnerVerificationEmail.TEST_EMAIL, trigger="verification")
        assert log is not None, "No email_log found"
        assert log.get("provider") == "zoho_mail", f"Expected zoho_mail, got: {log.get('provider')}"
        print(f"PASS: provider=zoho_mail on resend")

    def test_resend_partner_email_status_sent(self):
        """Resend email_log.status should be 'sent'"""
        log = get_latest_log(TestResendPartnerVerificationEmail.TEST_EMAIL, trigger="verification")
        assert log is not None, "No email_log found"
        assert log.get("status") == "sent", f"Expected sent, got: {log.get('status')} | error: {log.get('error_message')}"
        print(f"PASS: status=sent on resend")

    def test_resend_subject_contains_store_name(self):
        """Resend subject should have 'Automate Accounts' (platform store_name)"""
        log = get_latest_log(TestResendPartnerVerificationEmail.TEST_EMAIL, trigger="verification")
        subject = log.get("subject", "")
        assert "Automate Accounts" in subject, f"Expected 'Automate Accounts' in subject, got: '{subject}'"
        print(f"PASS: resend subject='{subject}'")


# ---------------------------------------------------------------------------
# Test 3: Customer signup with partner_code → Zoho Mail fallback
# ---------------------------------------------------------------------------
class TestCustomerSignupEmail:
    """POST /api/auth/register with partner_code → Zoho Mail (tenant has no email provider)"""

    TEST_EMAIL = None

    def test_customer_signup_200(self):
        TestCustomerSignupEmail.TEST_EMAIL = unique_email("testiter258_cust_signup")
        payload = {
            "first_name": "Iter258",
            "last_name": "Customer",
            "email": TestCustomerSignupEmail.TEST_EMAIL,
            "password": "CustomerPass#258",
            "partner_code": PARTNER_CODE,
            "address": {
                "line1": "1 Test Street",
                "city": "London",
                "region": "England",
                "postal": "SW1A 1AA",
                "country": "GB",
            },
        }
        resp = requests.post(f"{BASE_URL}/api/auth/register", json=payload)
        assert resp.status_code == 200, f"customer register failed: {resp.text}"
        data = resp.json()
        assert data.get("message") == "Verification required"
        # Wait to avoid Zoho token refresh rate limiting
        time.sleep(5)
        print(f"PASS: customer register 200 for {TestCustomerSignupEmail.TEST_EMAIL}")

    def test_customer_signup_email_log_exists(self):
        time.sleep(2)
        log = get_latest_log(TestCustomerSignupEmail.TEST_EMAIL, trigger="verification")
        assert log is not None, f"No email_log found for {TestCustomerSignupEmail.TEST_EMAIL}"
        print(f"PASS: email_log found: {log}")

    def test_customer_signup_email_provider_zoho(self):
        """Fallback to platform Zoho Mail since partner tenant has no email provider"""
        log = get_latest_log(TestCustomerSignupEmail.TEST_EMAIL, trigger="verification")
        assert log is not None, "No email_log found"
        assert log.get("provider") == "zoho_mail", (
            f"Expected provider=zoho_mail (platform fallback), got: {log.get('provider')}. "
            f"This would fail if tenant has no email provider and fallback is broken."
        )
        print(f"PASS: provider=zoho_mail (fallback used)")

    def test_customer_signup_email_status_sent(self):
        log = get_latest_log(TestCustomerSignupEmail.TEST_EMAIL, trigger="verification")
        assert log is not None, "No email_log found"
        assert log.get("status") == "sent", f"Expected sent, got: {log.get('status')} | error: {log.get('error_message')}"
        print(f"PASS: status=sent")

    def test_customer_signup_subject_contains_store_name(self):
        """Subject should have tenant store_name (TEST_HardeningOrg), NOT empty"""
        log = get_latest_log(TestCustomerSignupEmail.TEST_EMAIL, trigger="verification")
        subject = log.get("subject", "")
        # Store name for test-hardening-fix4 is 'TEST_HardeningOrg'
        assert "TEST_HardeningOrg" in subject, (
            f"Expected 'TEST_HardeningOrg' in subject (tenant store_name), got: '{subject}'"
        )
        assert "Verify your  account" not in subject, f"Subject has empty store_name: '{subject}'"
        print(f"PASS: subject='{subject}'")

    def test_customer_signup_tenant_id_in_log(self):
        """email_log should have the partner tenant_id"""
        db, client = get_db()
        tenant = db.tenants.find_one({"code": PARTNER_CODE}, {"_id": 0, "id": 1})
        client.close()
        partner_tid = tenant["id"] if tenant else None

        log = get_latest_log(TestCustomerSignupEmail.TEST_EMAIL, trigger="verification")
        log_tid = log.get("tenant_id")
        assert log_tid == partner_tid, f"Expected tenant_id={partner_tid}, got={log_tid}"
        print(f"PASS: tenant_id correctly set in log: {log_tid}")


# ---------------------------------------------------------------------------
# Test 4: Forgot password → Zoho Mail
# ---------------------------------------------------------------------------
class TestForgotPasswordEmail:
    """POST /api/auth/forgot-password → Zoho Mail"""

    def test_forgot_password_for_partner_admin_200(self):
        """Forgot password for partner admin (who has no email provider) → uses platform Zoho"""
        resp = requests.post(f"{BASE_URL}/api/auth/forgot-password", json={
            "email": "test_admin_fix4@example.com",
            "partner_code": PARTNER_CODE,
        })
        assert resp.status_code == 200, f"forgot-password failed: {resp.text}"
        data = resp.json()
        assert "message" in data
        # Wait to avoid Zoho token refresh rate limiting
        time.sleep(5)
        print(f"PASS: forgot-password 200")

    def test_forgot_password_email_log_exists(self):
        time.sleep(2)
        log = get_latest_log("test_admin_fix4@example.com", trigger="password_reset")
        assert log is not None, "No email_log found for password_reset"
        print(f"PASS: password_reset email_log found: {log}")

    def test_forgot_password_provider_zoho(self):
        log = get_latest_log("test_admin_fix4@example.com", trigger="password_reset")
        assert log is not None, "No email_log found"
        assert log.get("provider") == "zoho_mail", f"Expected zoho_mail, got: {log.get('provider')}"
        print(f"PASS: provider=zoho_mail for forgot-password")

    def test_forgot_password_status_sent(self):
        log = get_latest_log("test_admin_fix4@example.com", trigger="password_reset")
        assert log is not None, "No email_log found"
        assert log.get("status") == "sent", f"Expected sent, got: {log.get('status')} | error: {log.get('error_message')}"
        print(f"PASS: status=sent for forgot-password")

    def test_forgot_password_subject_contains_store_name(self):
        """Subject should have store_name (TEST_HardeningOrg), not empty"""
        log = get_latest_log("test_admin_fix4@example.com", trigger="password_reset")
        subject = log.get("subject", "")
        assert "TEST_HardeningOrg" in subject, f"Expected 'TEST_HardeningOrg' in subject, got: '{subject}'"
        assert "Reset your  password" not in subject, f"Subject has empty store_name: '{subject}'"
        print(f"PASS: subject='{subject}'")

    def test_forgot_password_platform_admin_200(self):
        """Forgot password for platform admin (tenant_id=None) → Zoho Mail"""
        resp = requests.post(f"{BASE_URL}/api/auth/forgot-password", json={
            "email": "admin@automateaccounts.local",
        })
        assert resp.status_code == 200, f"forgot-password for platform admin failed: {resp.text}"
        # Wait to avoid rate limiting
        time.sleep(5)
        print(f"PASS: forgot-password 200 for platform admin")

    def test_forgot_password_platform_admin_email_sent(self):
        """Platform admin password reset should be sent via Zoho Mail with correct store_name"""
        time.sleep(2)
        log = get_latest_log("admin@automateaccounts.local", trigger="password_reset")
        assert log is not None, "No email_log found for platform admin"
        assert log.get("provider") == "zoho_mail", f"Expected zoho_mail, got: {log.get('provider')}"
        assert log.get("status") == "sent", f"Expected sent, got: {log.get('status')}"
        subject = log.get("subject", "")
        assert "Automate Accounts" in subject, f"Expected 'Automate Accounts' in subject, got: '{subject}'"
        print(f"PASS: platform admin forgot-password sent via Zoho — subject='{subject}'")


# ---------------------------------------------------------------------------
# Test 5: Verify DB state — Zoho Mail connection on platform tenant
# ---------------------------------------------------------------------------
class TestEmailFallbackConfiguration:
    """Verify that platform tenant has Zoho Mail configured and fallback works"""

    def test_platform_zoho_mail_connection_exists(self):
        """automate-accounts must have a validated Zoho Mail connection"""
        db, client = get_db()
        conn = db.oauth_connections.find_one(
            {"tenant_id": "automate-accounts", "provider": "zoho_mail", "is_validated": True},
            {"_id": 0, "settings": 1, "credentials": 1}
        )
        client.close()
        assert conn is not None, "Platform (automate-accounts) Zoho Mail connection not found"
        settings = conn.get("settings", {})
        from_email = settings.get("from_email", "")
        assert from_email, "from_email is empty in Zoho Mail settings"
        print(f"PASS: Platform Zoho Mail configured — from_email={from_email}")

    def test_platform_store_name_set(self):
        """automate-accounts website_settings.store_name must not be empty"""
        db, client = get_db()
        ws = db.website_settings.find_one(
            {"tenant_id": "automate-accounts"},
            {"_id": 0, "store_name": 1}
        )
        client.close()
        assert ws is not None, "website_settings for automate-accounts not found"
        store_name = ws.get("store_name", "")
        assert store_name, "store_name is empty for automate-accounts"
        assert store_name.strip(), "store_name is whitespace for automate-accounts"
        print(f"PASS: store_name='{store_name}'")

    def test_partner_tenant_has_no_email_provider(self):
        """test-hardening-fix4 tenant should have NO email provider (ensures fallback is tested)"""
        db, client = get_db()
        tenant = db.tenants.find_one({"code": PARTNER_CODE}, {"_id": 0, "id": 1})
        assert tenant, f"Tenant {PARTNER_CODE} not found"
        tenant_id = tenant["id"]
        conn = db.oauth_connections.find_one(
            {"tenant_id": tenant_id, "provider": {"$in": ["zoho_mail", "resend"]}, "is_validated": True},
            {"_id": 0}
        )
        client.close()
        assert conn is None, (
            f"Partner tenant unexpectedly has email connection: {conn}. "
            "This would bypass the fallback logic we are testing."
        )
        print(f"PASS: partner tenant has no email provider — fallback will be triggered")

    def test_email_fallback_code_path_covered(self):
        """Verify that email_logs for partner tenant emails used platform Zoho Mail (provider=zoho_mail)"""
        db, client = get_db()
        tenant = db.tenants.find_one({"code": PARTNER_CODE}, {"_id": 0, "id": 1})
        assert tenant
        tenant_id = tenant["id"]
        # Find logs for this tenant that used zoho_mail and are sent
        sent_logs = list(db.email_logs.find(
            {"tenant_id": tenant_id, "provider": "zoho_mail", "status": "sent"},
            {"_id": 0, "trigger": 1, "subject": 1, "recipient": 1}
        ).sort("created_at", -1).limit(5))
        client.close()
        assert len(sent_logs) > 0, (
            f"No sent zoho_mail logs found for partner tenant {tenant_id}. "
            "Fallback may not be working."
        )
        print(f"PASS: {len(sent_logs)} sent zoho_mail logs found for partner tenant")
        for log in sent_logs:
            print(f"  - {log['trigger']} → '{log['subject']}' → {log['recipient']}")


# ---------------------------------------------------------------------------
# Test 6: Resend verification for unverified customer
# ---------------------------------------------------------------------------
class TestResendCustomerVerificationEmail:
    """POST /api/auth/resend-verification-email for existing unverified customer → Zoho Mail"""

    def test_resend_customer_verification_200(self):
        """Resend for existing unverified customer in partner tenant"""
        resp = requests.post(f"{BASE_URL}/api/auth/resend-verification-email", json={
            "email": "test_unverified_fix4@example.com",
            "partner_code": PARTNER_CODE,
        })
        assert resp.status_code == 200, f"resend-verification-email failed: {resp.text}"
        data = resp.json()
        assert "message" in data
        # Wait to avoid Zoho token refresh rate limiting
        time.sleep(5)
        print(f"PASS: resend customer verification 200")

    def test_resend_customer_email_provider_zoho(self):
        time.sleep(2)
        log = get_latest_log("test_unverified_fix4@example.com", trigger="verification")
        assert log is not None, "No email_log found"
        assert log.get("provider") == "zoho_mail", f"Expected zoho_mail, got: {log.get('provider')}"
        print(f"PASS: provider=zoho_mail for customer resend")

    def test_resend_customer_email_status_sent(self):
        log = get_latest_log("test_unverified_fix4@example.com", trigger="verification")
        assert log is not None, "No email_log found"
        assert log.get("status") == "sent", f"Expected sent, got: {log.get('status')} | error: {log.get('error_message')}"
        print(f"PASS: status=sent for customer resend")

    def test_resend_customer_subject_contains_store_name(self):
        log = get_latest_log("test_unverified_fix4@example.com", trigger="verification")
        subject = log.get("subject", "")
        assert "TEST_HardeningOrg" in subject, f"Expected 'TEST_HardeningOrg' in subject, got: '{subject}'"
        print(f"PASS: subject='{subject}' contains TEST_HardeningOrg")


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data():
    """Cleanup test pending registrations and unverified users created during testing"""
    yield
    db, client = get_db()
    # Clean up pending partner registrations created by this test
    db.pending_partner_registrations.delete_many({
        "email": {"$regex": "^testiter258_.*@example\\.com$"}
    })
    # Clean up unverified users created by this test
    db.users.delete_many({
        "email": {"$regex": "^testiter258_.*@example\\.com$"},
        "is_verified": False
    })
    client.close()
    print("Cleanup: Removed testiter258_* pending registrations and unverified users")
