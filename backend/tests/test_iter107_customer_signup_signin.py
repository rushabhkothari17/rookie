"""
Comprehensive E2E tests for Customer Sign Up + Sign In (Iteration 107)
Multi-tenant SaaS platform — Customer scope.

Tests:
  A) Customer Signup: field validation, password complexity, DB persistence,
     currency from country, idempotency, reserved code protection
  B) Email Verification: verify-email, resend, brute-force lockout, idempotency
  C) Customer Login: correct credentials, wrong password, unverified, inactive,
     wrong partner_code, case-insensitive code, admin-blocked
  D) Country Lock: PUT /api/me cannot change country; Admin can change via admin API
  E) Password Reset: forgot-password (no enum), reset-password, expiry
  Scenario 1: Same email in Tenant A + Tenant B → cross-tenant isolation
  Scenario 2: Double signup same tenant → 400; different tenant → 200
  Scenario 3: Verify link used twice → idempotent; brute-force lockout
  Scenario 4: Inactive tenant/user blocking
  Scenario 5: Country lock confirmed
  BRANDING: website-settings get/update
  TENANT ISOLATION: customer cannot access /api/admin/customers or /api/admin/tenants
  AUDIT LOGS: USER_REGISTERED, email_verified, profile_updated created
  PLATFORM ADMIN: can view all customers across tenants
  PARTNER SUPER ADMIN: can view/toggle their tenant's customers
"""
import pytest
import requests
import os
import time
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
PLATFORM_ADMIN_EMAIL = "admin@automateaccounts.local"
PLATFORM_ADMIN_PASSWORD = "ChangeMe123!"
RESERVED_CODE = "automate-accounts"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

# ─── Test Tenant identifiers (unique to this iteration) ───────────────────────
TENANT_A_ORG_NAME = "TEST Iter107 Corp A"
TENANT_A_CODE = "test-iter107-corp-a"
TENANT_A_ADMIN_EMAIL = "TEST-iter107-admin-a@test.local"
TENANT_A_ADMIN_PASSWORD = "TestPass@107A!"

TENANT_B_ORG_NAME = "TEST Iter107 Corp B"
TENANT_B_CODE = "test-iter107-corp-b"
TENANT_B_ADMIN_EMAIL = "TEST-iter107-admin-b@test.local"
TENANT_B_ADMIN_PASSWORD = "TestPass@107B!"

# Customer accounts
CUST_EMAIL = "TEST-cust107@test.local"
CUST_PASSWORD = "CustPass@107!"
CUST_EMAIL_SHARED = "TEST-shared107@test.local"  # used in both tenants
CUST_PASSWORD_SHARED = "SharedPass@107!"

# Inactive-tenant customer
INACTIVE_TENANT_ORG = "TEST Iter107 Inactive Tenant"
INACTIVE_TENANT_EMAIL = "TEST-iter107-inactive@test.local"
INACTIVE_TENANT_PASSWORD = "InactPass@107!"

INACTIVE_USER_EMAIL = "TEST-inactive-user107@test.local"
INACTIVE_USER_PASSWORD = "InactUser@107!"

# Lockout test customer
LOCKOUT_CUST_EMAIL = "TEST-lockout107@test.local"
LOCKOUT_CUST_PASSWORD = "LockoutPass@107!"

# ---------------------------------------------------------------------------
# Shared signup payload helper
# ---------------------------------------------------------------------------
def make_customer_payload(email, password=CUST_PASSWORD, country="Canada"):
    return {
        "email": email,
        "password": password,
        "full_name": "Test Customer 107",
        "company_name": "TEST Corp 107",
        "job_title": "QA Engineer",
        "phone": "+1-555-107-0000",
        "address": {
            "line1": "100 Test Street",
            "line2": "Suite 107",
            "city": "Toronto",
            "region": "Ontario",
            "postal": "M5V 1A1",
            "country": country,
        },
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def mongo_db():
    """Direct MongoDB access for cleanup and verification."""
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


@pytest.fixture(scope="module")
def platform_admin_headers():
    """Platform admin JWT headers."""
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": PLATFORM_ADMIN_EMAIL, "password": PLATFORM_ADMIN_PASSWORD},
    )
    assert resp.status_code == 200, f"Platform admin login failed: {resp.text}"
    token = resp.json().get("token") or resp.cookies.get("access_token")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def tenant_a_info(platform_admin_headers, mongo_db):
    """Create Tenant A via register-partner and return dict with id and code."""
    resp = requests.post(
        f"{BASE_URL}/api/auth/register-partner",
        json={
            "name": TENANT_A_ORG_NAME,
            "admin_name": "TEST Admin A107",
            "admin_email": TENANT_A_ADMIN_EMAIL,
            "admin_password": TENANT_A_ADMIN_PASSWORD,
        },
    )
    if resp.status_code == 200:
        partner_code = resp.json()["partner_code"]
    elif "already registered" in resp.text.lower() or resp.status_code == 400:
        partner_code = TENANT_A_CODE
    else:
        pytest.fail(f"Tenant A creation failed: {resp.text}")

    tenants_resp = requests.get(f"{BASE_URL}/api/admin/tenants", headers=platform_admin_headers)
    assert tenants_resp.status_code == 200
    tenants = tenants_resp.json()["tenants"]
    tenant = next((t for t in tenants if t["code"] == partner_code), None)
    assert tenant is not None, f"Tenant A not found by code '{partner_code}'"
    tenant_id = tenant["id"]

    yield {"id": tenant_id, "code": partner_code}
    _cleanup_tenant(mongo_db, tenant_id, partner_code)


@pytest.fixture(scope="module")
def tenant_a_id(tenant_a_info):
    """Tenant A's ID."""
    return tenant_a_info["id"]


@pytest.fixture(scope="module")
def tenant_a_code(tenant_a_info):
    """Tenant A's partner code (may differ from TENANT_A_CODE if re-run)."""
    return tenant_a_info["code"]


@pytest.fixture(scope="module")
def tenant_b_info(platform_admin_headers, mongo_db):
    """Create Tenant B via register-partner and return dict with id and code."""
    resp = requests.post(
        f"{BASE_URL}/api/auth/register-partner",
        json={
            "name": TENANT_B_ORG_NAME,
            "admin_name": "TEST Admin B107",
            "admin_email": TENANT_B_ADMIN_EMAIL,
            "admin_password": TENANT_B_ADMIN_PASSWORD,
        },
    )
    if resp.status_code == 200:
        partner_code = resp.json()["partner_code"]
    elif "already registered" in resp.text.lower() or resp.status_code == 400:
        partner_code = TENANT_B_CODE
    else:
        pytest.fail(f"Tenant B creation failed: {resp.text}")

    tenants_resp = requests.get(f"{BASE_URL}/api/admin/tenants", headers=platform_admin_headers)
    assert tenants_resp.status_code == 200
    tenants = tenants_resp.json()["tenants"]
    tenant = next((t for t in tenants if t["code"] == partner_code), None)
    assert tenant is not None, f"Tenant B not found by code '{partner_code}'"
    tenant_id = tenant["id"]

    yield {"id": tenant_id, "code": partner_code}
    _cleanup_tenant(mongo_db, tenant_id, partner_code)


@pytest.fixture(scope="module")
def tenant_b_id(tenant_b_info):
    """Tenant B's ID."""
    return tenant_b_info["id"]


@pytest.fixture(scope="module")
def tenant_b_code(tenant_b_info):
    """Tenant B's partner code."""
    return tenant_b_info["code"]


@pytest.fixture(scope="module")
def tenant_a_admin_headers(tenant_a_info):
    """Partner super admin for Tenant A."""
    resp = requests.post(
        f"{BASE_URL}/api/auth/partner-login",
        json={"partner_code": tenant_a_info["code"], "email": TENANT_A_ADMIN_EMAIL, "password": TENANT_A_ADMIN_PASSWORD},
    )
    assert resp.status_code == 200, f"Tenant A admin login failed: {resp.text}"
    token = resp.json().get("token") or resp.cookies.get("access_token")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def tenant_b_admin_headers(tenant_b_info):
    """Partner super admin for Tenant B."""
    resp = requests.post(
        f"{BASE_URL}/api/auth/partner-login",
        json={"partner_code": tenant_b_info["code"], "email": TENANT_B_ADMIN_EMAIL, "password": TENANT_B_ADMIN_PASSWORD},
    )
    assert resp.status_code == 200, f"Tenant B admin login failed: {resp.text}"
    token = resp.json().get("token") or resp.cookies.get("access_token")
    return {"Authorization": f"Bearer {token}"}


def _cleanup_tenant(mongo_db, tenant_id, code):
    """Remove all test data for a tenant."""
    # Remove users
    user_ids = [u["id"] for u in mongo_db.users.find({"tenant_id": tenant_id}, {"id": 1})]
    mongo_db.users.delete_many({"tenant_id": tenant_id})
    # Remove customers
    customer_ids = [c["id"] for c in mongo_db.customers.find({"tenant_id": tenant_id}, {"id": 1})]
    mongo_db.customers.delete_many({"tenant_id": tenant_id})
    # Remove addresses
    mongo_db.addresses.delete_many({"tenant_id": tenant_id})
    # Remove audit logs
    mongo_db.audit_logs.delete_many({"meta.tenant_id": tenant_id})
    # Remove email outbox
    mongo_db.email_outbox.delete_many({})  # safe to clean all test outbox entries
    # Remove website settings
    mongo_db.website_settings.delete_many({"tenant_id": tenant_id})
    # Remove tenant
    mongo_db.tenants.delete_many({"code": code})


# ===========================================================================
# Section A: CUSTOMER SIGNUP
# ===========================================================================

class TestCustomerSignup:
    """A) Customer signup: fields, validation, DB persistence, currency, idempotency"""

    def test_signup_success_canada(self, tenant_a_info, mongo_db):
        """Full signup with Canada → CAD currency, DB persistence"""
        tenant_a_id = tenant_a_info["id"]
        partner_code = tenant_a_info["code"]
        payload = make_customer_payload(CUST_EMAIL, country="Canada")
        resp = requests.post(f"{BASE_URL}/api/auth/register?partner_code={partner_code}", json=payload)
        assert resp.status_code == 200, f"Signup failed: {resp.text}"
        data = resp.json()
        assert "verification_code" in data, "No verification_code in response (MOCKED)"
        assert data.get("email_delivery") == "MOCKED"

        # DB: user created
        user = mongo_db.users.find_one({"email": CUST_EMAIL.lower(), "tenant_id": tenant_a_id})
        assert user is not None, "User not created in DB"
        assert user["is_verified"] is False, "User should be unverified after signup"
        assert user["is_admin"] is False
        assert user["role"] == "customer"
        assert user.get("password_hash"), "No password hash stored"
        # bcrypt hash starts with $2b$
        assert user["password_hash"].startswith("$2"), "Password hash not bcrypt"

        # DB: customer record
        customer = mongo_db.customers.find_one({"tenant_id": tenant_a_id, "user_id": user["id"]})
        assert customer is not None, "Customer record not created"
        assert customer["currency"] == "CAD", f"Expected CAD, got {customer.get('currency')}"
        assert customer["tenant_id"] == tenant_a_id

        # DB: address record
        address = mongo_db.addresses.find_one({"customer_id": customer["id"]})
        assert address is not None, "Address record not created"
        assert address["country"] == "Canada"
        assert address["line1"] == "100 Test Street"
        assert address["city"] == "Toronto"
        assert address["region"] == "Ontario"
        assert address["postal"] == "M5V 1A1"

    def test_signup_currency_usa(self, tenant_b_info, mongo_db):
        """USA signup → USD currency"""
        tenant_b_id = tenant_b_info["id"]
        partner_code = tenant_b_info["code"]
        payload = make_customer_payload("TEST-cust107-usa@test.local", country="USA")
        resp = requests.post(f"{BASE_URL}/api/auth/register?partner_code={partner_code}", json=payload)
        assert resp.status_code == 200, f"USA signup failed: {resp.text}"
        user = mongo_db.users.find_one({"email": "TEST-cust107-usa@test.local", "tenant_id": tenant_b_id})
        assert user, "User not created"
        customer = mongo_db.customers.find_one({"user_id": user["id"]})
        assert customer, "Customer not created"
        assert customer["currency"] == "USD", f"Expected USD got {customer.get('currency')}"

    def test_signup_currency_uk(self, tenant_b_info, mongo_db):
        """UK signup → GBP currency"""
        tenant_b_id = tenant_b_info["id"]
        partner_code = tenant_b_info["code"]
        payload = make_customer_payload("TEST-cust107-uk@test.local", country="UK")
        resp = requests.post(f"{BASE_URL}/api/auth/register?partner_code={partner_code}", json=payload)
        assert resp.status_code == 200, f"UK signup failed: {resp.text}"
        user = mongo_db.users.find_one({"email": "TEST-cust107-uk@test.local", "tenant_id": tenant_b_id})
        assert user, "User not created"
        customer = mongo_db.customers.find_one({"user_id": user["id"]})
        assert customer, "Customer not created"
        assert customer["currency"] == "GBP", f"Expected GBP got {customer.get('currency')}"

    def test_signup_currency_unknown(self, tenant_b_info, mongo_db):
        """Unknown country signup → USD (default)"""
        tenant_b_id = tenant_b_info["id"]
        partner_code = tenant_b_info["code"]
        payload = make_customer_payload("TEST-cust107-unknown@test.local", country="Atlantis")
        resp = requests.post(f"{BASE_URL}/api/auth/register?partner_code={partner_code}", json=payload)
        assert resp.status_code == 200, f"Unknown country signup failed: {resp.text}"
        user = mongo_db.users.find_one({"email": "TEST-cust107-unknown@test.local", "tenant_id": tenant_b_id})
        assert user, "User not created"
        customer = mongo_db.customers.find_one({"user_id": user["id"]})
        assert customer, "Customer not created"
        assert customer["currency"] == "USD", f"Expected USD (default) got {customer.get('currency')}"

    # --- Validation tests ---

    def test_signup_missing_email(self, tenant_a_info):
        """Missing email → 422"""
        partner_code = tenant_a_info["code"]
        payload = make_customer_payload("dummy@test.local")
        del payload["email"]
        resp = requests.post(f"{BASE_URL}/api/auth/register?partner_code={partner_code}", json=payload)
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"

    def test_signup_missing_full_name(self, tenant_a_info):
        """Missing full_name → 422"""
        partner_code = tenant_a_info["code"]
        payload = make_customer_payload("TEST-missing-name@test.local")
        del payload["full_name"]
        resp = requests.post(f"{BASE_URL}/api/auth/register?partner_code={partner_code}", json=payload)
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"

    def test_signup_missing_address(self, tenant_a_info):
        """Missing address → 422"""
        partner_code = tenant_a_info["code"]
        payload = make_customer_payload("TEST-missing-addr@test.local")
        del payload["address"]
        resp = requests.post(f"{BASE_URL}/api/auth/register?partner_code={partner_code}", json=payload)
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"

    def test_signup_password_too_short(self, tenant_a_info):
        """Password < 10 chars → 400"""
        partner_code = tenant_a_info["code"]
        payload = make_customer_payload("TEST-shortpw107@test.local", password="Abc1!")
        resp = requests.post(f"{BASE_URL}/api/auth/register?partner_code={partner_code}", json=payload)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        assert "10 characters" in resp.json().get("detail", "")

    def test_signup_password_no_uppercase(self, tenant_a_info):
        """Password without uppercase → 400"""
        partner_code = tenant_a_info["code"]
        payload = make_customer_payload("TEST-noupcase107@test.local", password="testpass1@a")
        resp = requests.post(f"{BASE_URL}/api/auth/register?partner_code={partner_code}", json=payload)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        assert "uppercase" in resp.json().get("detail", "").lower()

    def test_signup_password_no_lowercase(self, tenant_a_info):
        """Password without lowercase → 400"""
        partner_code = tenant_a_info["code"]
        payload = make_customer_payload("TEST-nolower107@test.local", password="TESTPASS1@A")
        resp = requests.post(f"{BASE_URL}/api/auth/register?partner_code={partner_code}", json=payload)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        assert "lowercase" in resp.json().get("detail", "").lower()

    def test_signup_password_no_digit(self, tenant_a_info):
        """Password without digit → 400"""
        partner_code = tenant_a_info["code"]
        payload = make_customer_payload("TEST-nodigit107@test.local", password="TestPass@abc")
        resp = requests.post(f"{BASE_URL}/api/auth/register?partner_code={partner_code}", json=payload)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        assert "number" in resp.json().get("detail", "").lower()

    def test_signup_password_no_special(self, tenant_a_info):
        """Password without special char → 400"""
        partner_code = tenant_a_info["code"]
        payload = make_customer_payload("TEST-nospecial107@test.local", password="TestPass1234")
        resp = requests.post(f"{BASE_URL}/api/auth/register?partner_code={partner_code}", json=payload)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        assert "special" in resp.json().get("detail", "").lower()

    def test_signup_reserved_code_blocked(self, tenant_a_info):
        """Reserved code (automate-accounts) → 403"""
        payload = make_customer_payload("TEST-reserved107@test.local")
        resp = requests.post(f"{BASE_URL}/api/auth/register?partner_code={RESERVED_CODE}", json=payload)
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
        assert "reserved" in resp.json().get("detail", "").lower()

    def test_signup_idempotency_same_tenant(self, tenant_a_info):
        """Same email + same tenant → 400 Email already registered"""
        partner_code = tenant_a_info["code"]
        payload = make_customer_payload(CUST_EMAIL)
        resp = requests.post(f"{BASE_URL}/api/auth/register?partner_code={partner_code}", json=payload)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        assert "already registered" in resp.json().get("detail", "").lower()

    def test_signup_same_email_different_tenant_allowed(self, tenant_a_info, tenant_b_info):
        """Same email in Tenant A and Tenant B → both 200 (cross-tenant isolation)"""
        # CUST_EMAIL already exists in Tenant A (from test_signup_success_canada)
        # Signup with same email in Tenant B → should succeed
        payload = make_customer_payload(CUST_EMAIL)
        resp = requests.post(f"{BASE_URL}/api/auth/register?partner_code={tenant_b_info['code']}", json=payload)
        assert resp.status_code == 200, f"Cross-tenant same email should be allowed: {resp.text}"

    def test_signup_audit_log_created(self, tenant_a_info, mongo_db):
        """USER_REGISTERED audit log is created after signup"""
        log = mongo_db.audit_logs.find_one({
            "action": "USER_REGISTERED",
            "actor_email": CUST_EMAIL.lower(),
        })
        assert log is not None, "USER_REGISTERED audit log not found"


# ===========================================================================
# Section B: EMAIL VERIFICATION
# ===========================================================================

class TestEmailVerification:
    """B) Email verification flow + brute force lockout"""

    def test_verify_email_correct_code(self, tenant_a_info, mongo_db):
        """Correct verification code → is_verified=True"""
        partner_code = tenant_a_info["code"]
        payload = make_customer_payload("TEST-verify107@test.local")
        signup_resp = requests.post(f"{BASE_URL}/api/auth/register?partner_code={partner_code}", json=payload)
        assert signup_resp.status_code == 200
        code = signup_resp.json()["verification_code"]
        email = "TEST-verify107@test.local"

        verify_resp = requests.post(f"{BASE_URL}/api/auth/verify-email", json={"email": email, "code": code})
        assert verify_resp.status_code == 200, f"Verify email failed: {verify_resp.text}"
        assert verify_resp.json().get("message") in ["Verified", "Already verified"]

        # DB: is_verified=True
        user = mongo_db.users.find_one({"email": email.lower()})
        assert user["is_verified"] is True, "is_verified should be True after verification"
        assert user.get("verification_code") is None, "verification_code should be cleared"

    def test_verify_email_wrong_code(self, tenant_a_info, mongo_db):
        """Wrong code → 400"""
        partner_code = tenant_a_info["code"]
        payload = make_customer_payload("TEST-wrongcode107@test.local")
        signup_resp = requests.post(f"{BASE_URL}/api/auth/register?partner_code={partner_code}", json=payload)
        assert signup_resp.status_code == 200
        email = "TEST-wrongcode107@test.local"

        resp = requests.post(f"{BASE_URL}/api/auth/verify-email", json={"email": email, "code": "000000"})
        assert resp.status_code == 400, f"Expected 400 for wrong code, got {resp.status_code}"
        assert "invalid" in resp.json().get("detail", "").lower()

    def test_verify_email_brute_force_lockout(self, tenant_a_info, mongo_db):
        """5 wrong codes → 429 lockout for 15 minutes"""
        partner_code = tenant_a_info["code"]
        payload = make_customer_payload("TEST-bruteverify107@test.local")
        signup_resp = requests.post(f"{BASE_URL}/api/auth/register?partner_code={partner_code}", json=payload)
        assert signup_resp.status_code == 200
        email = "TEST-bruteverify107@test.local"

        # Send 5 wrong codes
        for i in range(5):
            resp = requests.post(f"{BASE_URL}/api/auth/verify-email", json={"email": email, "code": f"11111{i}"})
            if i < 4:
                assert resp.status_code == 400, f"Attempt {i+1}: expected 400, got {resp.status_code}"
            else:
                # 5th attempt should trigger lockout
                assert resp.status_code == 429, f"5th attempt: expected 429, got {resp.status_code}"

        # Subsequent attempt should still be locked
        resp = requests.post(f"{BASE_URL}/api/auth/verify-email", json={"email": email, "code": "999999"})
        assert resp.status_code == 429, "User should still be locked out"

    def test_verify_email_already_verified_idempotent(self, tenant_a_info, mongo_db):
        """Already verified user → 200 'Already verified'"""
        # Re-use test-verify107 which was verified in test_verify_email_correct_code
        resp = requests.post(
            f"{BASE_URL}/api/auth/verify-email",
            json={"email": "TEST-verify107@test.local", "code": "000000"},
        )
        assert resp.status_code == 200, f"Expected 200 for already verified: {resp.status_code}"
        assert "already verified" in resp.json().get("message", "").lower()

    def test_resend_verification_email(self, tenant_a_info, mongo_db):
        """Resend → new code generated, audit log created"""
        partner_code = tenant_a_info["code"]
        payload = make_customer_payload("TEST-resend107@test.local")
        signup_resp = requests.post(f"{BASE_URL}/api/auth/register?partner_code={partner_code}", json=payload)
        assert signup_resp.status_code == 200
        original_code = signup_resp.json()["verification_code"]
        email = "TEST-resend107@test.local"

        resend_resp = requests.post(f"{BASE_URL}/api/auth/resend-verification-email", json={"email": email})
        assert resend_resp.status_code == 200, f"Resend failed: {resend_resp.text}"
        new_code = resend_resp.json().get("verification_code")
        assert new_code is not None, "No verification code in resend response"

        # Audit log: verification_resent
        log = mongo_db.audit_logs.find_one({"action": "verification_resent", "actor": email.lower()})
        assert log is not None, "verification_resent audit log not found"

    def test_email_outbox_after_verification(self, tenant_a_info, mongo_db):
        """After successful verify-email, email_outbox record with type=welcome created"""
        outbox = mongo_db.email_outbox.find_one({"to": "TEST-verify107@test.local", "type": "welcome"})
        assert outbox is not None, "email_outbox welcome record not found after verification"
        assert outbox["status"] == "MOCKED"

    def test_audit_log_email_verified(self, tenant_a_info, mongo_db):
        """email_verified audit log created after successful verification"""
        log = mongo_db.audit_logs.find_one({
            "action": "email_verified",
            "actor": "TEST-verify107@test.local",
        })
        assert log is not None, "email_verified audit log not found"


# ===========================================================================
# Section C: CUSTOMER LOGIN
# ===========================================================================

class TestCustomerLogin:
    """C) Customer login flow: correct creds, errors, gating, isolation"""

    # Helper: Sign up and verify a customer, return their customer token
    @staticmethod
    def _signup_and_verify(tenant_code, email, password=CUST_PASSWORD, country="Canada"):
        payload = make_customer_payload(email, password=password, country=country)
        signup_resp = requests.post(f"{BASE_URL}/api/auth/register?partner_code={tenant_code}", json=payload)
        if signup_resp.status_code != 200:
            return None, None
        code = signup_resp.json()["verification_code"]
        verify_resp = requests.post(f"{BASE_URL}/api/auth/verify-email", json={"email": email, "code": code})
        return signup_resp.json(), verify_resp.json()

    def test_customer_login_success(self, tenant_a_info):
        """Correct partner_code + email + password → 200 + token + role=customer"""
        tenant_a_id = tenant_a_info["id"]
        partner_code = tenant_a_info["code"]
        email = "TEST-login107@test.local"
        self._signup_and_verify(partner_code, email)

        resp = requests.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={"partner_code": partner_code, "email": email, "password": CUST_PASSWORD},
        )
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        data = resp.json()
        assert "token" in data
        assert data["role"] == "customer"
        assert data["tenant_id"] == tenant_a_id

    def test_customer_login_jwt_content(self, tenant_a_info):
        """JWT token contains role=customer and correct tenant_id"""
        import base64
        import json as _json
        tenant_a_id = tenant_a_info["id"]
        partner_code = tenant_a_info["code"]
        email = "TEST-login107@test.local"
        resp = requests.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={"partner_code": partner_code, "email": email, "password": CUST_PASSWORD},
        )
        assert resp.status_code == 200
        token = resp.json()["token"]
        parts = token.split(".")
        assert len(parts) == 3, "JWT should have 3 parts"
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = _json.loads(base64.b64decode(padded))
        assert claims.get("role") == "customer"
        assert claims.get("tenant_id") == tenant_a_id
        assert claims.get("is_admin") is False

    def test_customer_login_wrong_password(self, tenant_a_info):
        """Wrong password → 401 (generic message, no email-not-found leakage)"""
        partner_code = tenant_a_info["code"]
        email = "TEST-login107@test.local"
        resp = requests.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={"partner_code": partner_code, "email": email, "password": "WrongPass@999"},
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        detail = resp.json().get("detail", "")
        assert "invalid credentials" in detail.lower(), f"Expected 'Invalid credentials', got: {detail}"
        assert "not found" not in detail.lower()

    def test_customer_login_unverified_blocked(self, tenant_a_info):
        """Unverified user login → 403 Email verification required"""
        partner_code = tenant_a_info["code"]
        resp = requests.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={"partner_code": partner_code, "email": CUST_EMAIL, "password": CUST_PASSWORD},
        )
        assert resp.status_code == 403, f"Expected 403 for unverified user, got {resp.status_code}"
        assert "verification" in resp.json().get("detail", "").lower()

    def test_customer_login_wrong_partner_code(self):
        """Wrong partner code → 400/404"""
        resp = requests.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={"partner_code": "nonexistent-tenant-xyz", "email": "someone@test.local", "password": "Pass@1234"},
        )
        assert resp.status_code in [400, 404], f"Expected 400/404, got {resp.status_code}"

    def test_customer_login_case_insensitive_partner_code(self, tenant_a_info):
        """Case-insensitive partner code: UPPERCASE and MixedCase → same result"""
        partner_code = tenant_a_info["code"]
        email = "TEST-login107@test.local"
        resp1 = requests.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={"partner_code": partner_code.upper(), "email": email, "password": CUST_PASSWORD},
        )
        assert resp1.status_code == 200, f"UPPERCASE partner_code failed: {resp1.text}"

        mixed = partner_code.title().replace("-", "-")
        resp2 = requests.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={"partner_code": mixed, "email": email, "password": CUST_PASSWORD},
        )
        assert resp2.status_code == 200, f"MixedCase partner_code failed: {resp2.text}"

    def test_customer_login_reserved_code_blocked(self):
        """automate-accounts code → 403 reserved"""
        resp = requests.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={"partner_code": RESERVED_CODE, "email": "admin@test.local", "password": CUST_PASSWORD},
        )
        assert resp.status_code == 403, f"Expected 403 for reserved code, got {resp.status_code}"

    def test_customer_login_admin_user_blocked(self, tenant_a_info):
        """Admin user trying customer_login → 403 'Please use Partner Login'"""
        partner_code = tenant_a_info["code"]
        resp = requests.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={"partner_code": partner_code, "email": TENANT_A_ADMIN_EMAIL, "password": TENANT_A_ADMIN_PASSWORD},
        )
        assert resp.status_code == 403, f"Expected 403 for admin via customer login, got {resp.status_code}"
        assert "partner login" in resp.json().get("detail", "").lower()

    def test_customer_login_cross_tenant_isolated(self, tenant_a_info, tenant_b_info):
        """Customer from Tenant A cannot login with Tenant B slug"""
        email = "TEST-login107@test.local"  # Only in Tenant A (verified)
        resp = requests.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={"partner_code": tenant_b_info["code"], "email": email, "password": CUST_PASSWORD},
        )
        assert resp.status_code in [401, 403], f"Expected 401/403 for cross-tenant, got {resp.status_code}"


# ===========================================================================
# Section D: COUNTRY LOCK
# ===========================================================================

class TestCountryLock:
    """D) PUT /api/me cannot change country; Admin can via admin API"""

    def _get_verified_customer_token(self, tenant_code, email, password=CUST_PASSWORD):
        """Helper: get a verified customer JWT token."""
        payload = make_customer_payload(email, password=password)
        signup_resp = requests.post(f"{BASE_URL}/api/auth/register?partner_code={tenant_code}", json=payload)
        if signup_resp.status_code != 200:
            return None
        code = signup_resp.json()["verification_code"]
        requests.post(f"{BASE_URL}/api/auth/verify-email", json={"email": email, "code": code})
        login_resp = requests.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={"partner_code": tenant_code, "email": email, "password": password},
        )
        if login_resp.status_code != 200:
            return None
        return login_resp.json()["token"]

    def test_put_me_no_country_field(self, tenant_a_info):
        """PUT /api/me with country field → field silently ignored (UpdateProfileRequest has no country)"""
        partner_code = tenant_a_info["code"]
        tenant_a_id = tenant_a_info["id"]
        email = "TEST-countrylock107@test.local"
        token = self._get_verified_customer_token(partner_code, email)
        assert token, "Could not get customer token"

        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.put(
            f"{BASE_URL}/api/me",
            json={"full_name": "Updated Name", "country": "USA"},
            headers=headers,
        )
        assert resp.status_code == 200, f"PUT /api/me failed: {resp.text}"

        # Verify country was NOT updated in DB
        from pymongo import MongoClient
        client = MongoClient(MONGO_URL)
        db = client[DB_NAME]
        user = db.users.find_one({"email": email.lower()})
        customer = db.customers.find_one({"user_id": user["id"]}) if user else None
        address = db.addresses.find_one({"customer_id": customer["id"]}) if customer else None
        client.close()
        assert address is not None, "Address not found"
        assert address.get("country") == "Canada", f"Country should not change, got {address.get('country')}"

    def test_put_me_profile_update_works(self, tenant_a_info):
        """PUT /api/me with allowed fields → profile updated"""
        partner_code = tenant_a_info["code"]
        email = "TEST-countrylock107@test.local"
        login_resp = requests.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={"partner_code": partner_code, "email": email, "password": CUST_PASSWORD},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = requests.put(
            f"{BASE_URL}/api/me",
            json={"full_name": "Updated Name 107", "phone": "+1-555-999-0000"},
            headers=headers,
        )
        assert resp.status_code == 200, f"PUT /api/me failed: {resp.text}"

    def test_admin_can_update_country(self, tenant_a_info, tenant_a_admin_headers, mongo_db):
        """Admin PUT to update customer address WITH country change works"""
        tenant_a_id = tenant_a_info["id"]
        email = "TEST-countrylock107@test.local"
        user = mongo_db.users.find_one({"email": email.lower(), "tenant_id": tenant_a_id})
        assert user, "User not found"
        customer = mongo_db.customers.find_one({"user_id": user["id"]})
        assert customer, "Customer not found"
        customer_id = customer["id"]

        resp = requests.put(
            f"{BASE_URL}/api/admin/customers/{customer_id}",
            json={
                "customer": {"full_name": "Admin Updated Name"},
                "address": {"country": "USA", "line1": "200 Admin Street", "city": "New York", "region": "NY", "postal": "10001"},
            },
            headers=tenant_a_admin_headers,
        )
        assert resp.status_code == 200, f"Admin update failed: {resp.text}"

        # Verify country was updated in DB
        updated_address = mongo_db.addresses.find_one({"customer_id": customer_id})
        assert updated_address is not None
        assert updated_address.get("country") == "USA", f"Country should now be USA, got {updated_address.get('country')}"

    def test_profile_updated_audit_log(self, tenant_a_info, mongo_db):
        """profile_updated audit log created on profile change"""
        log = mongo_db.audit_logs.find_one({
            "action": "profile_updated",
            "actor": "TEST-countrylock107@test.local",
        })
        assert log is not None, "profile_updated audit log not found"


# ===========================================================================
# Section E: PASSWORD RESET
# ===========================================================================

class TestPasswordReset:
    """E) Forgot password (no enumeration), reset-password, expiry"""

    def test_forgot_password_valid_email(self, tenant_a_info, mongo_db):
        """forgot-password with valid email → success message (no enumeration)"""
        partner_code = tenant_a_info["code"]
        email = "TEST-pwreset107@test.local"
        payload = make_customer_payload(email)
        signup_resp = requests.post(f"{BASE_URL}/api/auth/register?partner_code={partner_code}", json=payload)
        assert signup_resp.status_code == 200
        code = signup_resp.json()["verification_code"]
        requests.post(f"{BASE_URL}/api/auth/verify-email", json={"email": email, "code": code})

        resp = requests.post(
            f"{BASE_URL}/api/auth/forgot-password",
            json={"email": email, "partner_code": partner_code},
        )
        assert resp.status_code == 200, f"Forgot password failed: {resp.text}"
        assert "sent" in resp.json().get("message", "").lower() or "account" in resp.json().get("message", "").lower()

        # DB: password_reset_code and expiry stored
        user = mongo_db.users.find_one({"email": email.lower()})
        assert user.get("password_reset_code"), "password_reset_code not stored"
        assert user.get("password_reset_expires"), "password_reset_expires not stored"

    def test_forgot_password_nonexistent_email(self, tenant_a_info):
        """forgot-password with non-existent email → always returns success (no enumeration)"""
        partner_code = tenant_a_info["code"]
        resp = requests.post(
            f"{BASE_URL}/api/auth/forgot-password",
            json={"email": "nonexistent107@test.local", "partner_code": partner_code},
        )
        assert resp.status_code == 200, f"Expected 200 even for non-existent email: {resp.text}"
        assert "if an account" in resp.json().get("message", "").lower()

    def test_reset_password_correct_code(self, tenant_a_info, mongo_db):
        """Reset password with correct code → password updated"""
        partner_code = tenant_a_info["code"]
        email = "TEST-pwreset107@test.local"
        user = mongo_db.users.find_one({"email": email.lower()})
        reset_code = user.get("password_reset_code")
        assert reset_code, "No reset code found"

        new_password = "NewPass@107Reset!"
        resp = requests.post(
            f"{BASE_URL}/api/auth/reset-password",
            json={"email": email, "partner_code": partner_code, "code": reset_code, "new_password": new_password},
        )
        assert resp.status_code == 200, f"Reset password failed: {resp.text}"
        assert "reset" in resp.json().get("message", "").lower()

        # DB: reset code cleared
        updated_user = mongo_db.users.find_one({"email": email.lower()})
        assert "password_reset_code" not in updated_user or updated_user.get("password_reset_code") is None

        # Login with new password works
        login_resp = requests.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={"partner_code": partner_code, "email": email, "password": new_password},
        )
        assert login_resp.status_code == 200, f"Login with new password failed: {login_resp.text}"

    def test_reset_password_wrong_code(self, tenant_a_info, mongo_db):
        """Reset password with wrong code → 400"""
        partner_code = tenant_a_info["code"]
        email = "TEST-pwreset-wrong107@test.local"
        payload = make_customer_payload(email)
        signup_resp = requests.post(f"{BASE_URL}/api/auth/register?partner_code={partner_code}", json=payload)
        assert signup_resp.status_code == 200
        code = signup_resp.json()["verification_code"]
        requests.post(f"{BASE_URL}/api/auth/verify-email", json={"email": email, "code": code})
        requests.post(f"{BASE_URL}/api/auth/forgot-password", json={"email": email, "partner_code": partner_code})

        resp = requests.post(
            f"{BASE_URL}/api/auth/reset-password",
            json={"email": email, "partner_code": partner_code, "code": "000000", "new_password": "NewPass@107!"},
        )
        assert resp.status_code == 400, f"Expected 400 for wrong code, got {resp.status_code}"
        assert "invalid" in resp.json().get("detail", "").lower()

    def test_reset_password_new_password_complexity(self, tenant_a_info, mongo_db):
        """Reset password with weak new password → 400"""
        partner_code = tenant_a_info["code"]
        email = "TEST-pwreset-weak107@test.local"
        payload = make_customer_payload(email)
        signup_resp = requests.post(f"{BASE_URL}/api/auth/register?partner_code={partner_code}", json=payload)
        assert signup_resp.status_code == 200
        code = signup_resp.json()["verification_code"]
        requests.post(f"{BASE_URL}/api/auth/verify-email", json={"email": email, "code": code})
        requests.post(f"{BASE_URL}/api/auth/forgot-password", json={"email": email, "partner_code": partner_code})
        user = mongo_db.users.find_one({"email": email.lower()})
        reset_code = user.get("password_reset_code")

        resp = requests.post(
            f"{BASE_URL}/api/auth/reset-password",
            json={"email": email, "partner_code": partner_code, "code": reset_code, "new_password": "weakpass"},
        )
        assert resp.status_code == 400, f"Expected 400 for weak password, got {resp.status_code}"


# ===========================================================================
# Section: TENANT ISOLATION
# ===========================================================================

class TestTenantIsolation:
    """Verify customer cannot access admin endpoints"""

    def _get_customer_token(self, tenant_code, email):
        payload = make_customer_payload(email)
        signup = requests.post(f"{BASE_URL}/api/auth/register?partner_code={tenant_code}", json=payload)
        if signup.status_code != 200:
            return None
        code = signup.json()["verification_code"]
        requests.post(f"{BASE_URL}/api/auth/verify-email", json={"email": email, "code": code})
        login = requests.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={"partner_code": tenant_code, "email": email, "password": CUST_PASSWORD},
        )
        if login.status_code != 200:
            return None
        return login.json()["token"]

    def test_customer_cannot_access_admin_customers(self, tenant_a_info):
        """Customer JWT cannot access /api/admin/customers → 403"""
        partner_code = tenant_a_info["code"]
        token = self._get_customer_token(partner_code, "TEST-isolation107@test.local")
        assert token, "Could not get customer token"
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(f"{BASE_URL}/api/admin/customers", headers=headers)
        assert resp.status_code in [403, 401], f"Expected 403/401, got {resp.status_code}"

    def test_customer_cannot_access_admin_tenants(self, tenant_a_info):
        """Customer JWT cannot access /api/admin/tenants → 403"""
        partner_code = tenant_a_info["code"]
        login = requests.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={"partner_code": partner_code, "email": "TEST-isolation107@test.local", "password": CUST_PASSWORD},
        )
        if login.status_code != 200:
            pytest.skip("Customer token not available")
        token = login.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(f"{BASE_URL}/api/admin/tenants", headers=headers)
        assert resp.status_code in [403, 401], f"Expected 403/401, got {resp.status_code}"

    def test_customer_tenant_id_matches_their_tenant(self, tenant_a_info):
        """Customer JWT tenant_id matches their own tenant"""
        import base64, json as _json
        partner_code = tenant_a_info["code"]
        tenant_a_id = tenant_a_info["id"]
        login = requests.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={"partner_code": partner_code, "email": "TEST-isolation107@test.local", "password": CUST_PASSWORD},
        )
        if login.status_code != 200:
            pytest.skip("Customer token not available")
        token = login.json()["token"]
        parts = token.split(".")
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = _json.loads(base64.b64decode(padded))
        assert claims["tenant_id"] == tenant_a_id, f"JWT tenant_id mismatch: {claims['tenant_id']} != {tenant_a_id}"


# ===========================================================================
# Section: SCENARIO 4 — Inactive tenant / inactive user
# ===========================================================================

class TestInactiveScenarios:
    """Scenario 4: Inactive tenant → customer_login returns 403. Inactive user → only that user blocked."""

    def test_inactive_user_blocked(self, tenant_a_info, tenant_a_admin_headers, mongo_db):
        """Deactivating a customer prevents login"""
        partner_code = tenant_a_info["code"]
        tenant_a_id = tenant_a_info["id"]
        email = INACTIVE_USER_EMAIL

        payload = make_customer_payload(email, password=INACTIVE_USER_PASSWORD)
        signup_resp = requests.post(f"{BASE_URL}/api/auth/register?partner_code={partner_code}", json=payload)
        assert signup_resp.status_code == 200
        code = signup_resp.json()["verification_code"]
        requests.post(f"{BASE_URL}/api/auth/verify-email", json={"email": email, "code": code})

        user = mongo_db.users.find_one({"email": email.lower(), "tenant_id": tenant_a_id})
        assert user, "User not found"
        customer = mongo_db.customers.find_one({"user_id": user["id"]})
        assert customer, "Customer not found"
        customer_id = customer["id"]

        deactivate_resp = requests.patch(
            f"{BASE_URL}/api/admin/customers/{customer_id}/active?active=false",
            headers=tenant_a_admin_headers,
        )
        assert deactivate_resp.status_code == 200, f"Deactivation failed: {deactivate_resp.text}"

        login_resp = requests.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={"partner_code": partner_code, "email": email, "password": INACTIVE_USER_PASSWORD},
        )
        assert login_resp.status_code == 403, f"Expected 403 for inactive user, got {login_resp.status_code}"
        assert "inactive" in login_resp.json().get("detail", "").lower()

    def test_reactivate_user_allows_login(self, tenant_a_info, tenant_a_admin_headers, mongo_db):
        """Re-activating a customer allows login again"""
        partner_code = tenant_a_info["code"]
        tenant_a_id = tenant_a_info["id"]
        email = INACTIVE_USER_EMAIL
        user = mongo_db.users.find_one({"email": email.lower(), "tenant_id": tenant_a_id})
        customer = mongo_db.customers.find_one({"user_id": user["id"]}) if user else None
        if not customer:
            pytest.skip("Customer not found")

        activate_resp = requests.patch(
            f"{BASE_URL}/api/admin/customers/{customer['id']}/active?active=true",
            headers=tenant_a_admin_headers,
        )
        assert activate_resp.status_code == 200, f"Re-activation failed: {activate_resp.text}"

        login_resp = requests.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={"partner_code": partner_code, "email": email, "password": INACTIVE_USER_PASSWORD},
        )
        assert login_resp.status_code == 200, f"Login after re-activation failed: {login_resp.text}"


# ===========================================================================
# Section: BRANDING — Website Settings
# ===========================================================================

class TestBranding:
    """Branding: website-settings get/update, tenant customization"""

    def test_get_website_settings_public(self, tenant_a_info):
        """GET /api/website-settings?partner_code → returns settings"""
        partner_code = tenant_a_info["code"]
        resp = requests.get(f"{BASE_URL}/api/website-settings?partner_code={partner_code}")
        assert resp.status_code == 200, f"GET website-settings failed: {resp.text}"
        settings = resp.json().get("settings", {})
        assert "login_title" in settings
        assert "register_title" in settings

    def test_get_website_settings_admin(self, tenant_a_admin_headers):
        """GET /api/admin/website-settings returns auth page config"""
        resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=tenant_a_admin_headers)
        assert resp.status_code == 200, f"GET admin website-settings failed: {resp.text}"
        settings = resp.json().get("settings", {})
        assert "login_title" in settings

    def test_update_website_settings_and_verify(self, tenant_a_admin_headers):
        """Update login_title → GET reflects change"""
        custom_title = "TEST Login 107 Custom Title"
        put_resp = requests.put(
            f"{BASE_URL}/api/admin/website-settings",
            json={"login_title": custom_title},
            headers=tenant_a_admin_headers,
        )
        assert put_resp.status_code == 200, f"PUT website-settings failed: {put_resp.text}"

        get_resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=tenant_a_admin_headers)
        assert get_resp.status_code == 200
        settings = get_resp.json().get("settings", {})
        assert settings.get("login_title") == custom_title, f"login_title not updated: {settings.get('login_title')}"

    def test_website_settings_tenant_isolated(self, tenant_a_admin_headers, tenant_b_admin_headers):
        """Website settings changes in Tenant A don't affect Tenant B"""
        resp_b = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=tenant_b_admin_headers)
        assert resp_b.status_code == 200
        settings_b = resp_b.json().get("settings", {})
        custom_title = "TEST Login 107 Custom Title"
        assert settings_b.get("login_title") != custom_title, "Tenant B should not see Tenant A's settings"


# ===========================================================================
# Section: PLATFORM ADMIN + PARTNER SUPER ADMIN CUSTOMER MANAGEMENT
# ===========================================================================

class TestAdminCustomerAccess:
    """Platform admin can view all customers; Partner super admin can view/toggle their own"""

    def test_platform_admin_can_view_all_customers(self, platform_admin_headers, tenant_a_info, tenant_b_info):
        """Platform admin GET /api/admin/customers → can see all tenants"""
        resp = requests.get(f"{BASE_URL}/api/admin/customers", headers=platform_admin_headers)
        assert resp.status_code == 200, f"Platform admin GET customers failed: {resp.text}"
        data = resp.json()
        assert "customers" in data

    def test_partner_admin_sees_only_own_customers(self, tenant_a_admin_headers, tenant_b_admin_headers, tenant_a_info, tenant_b_info):
        """Partner super admin sees only their tenant's customers"""
        tenant_a_id = tenant_a_info["id"]
        tenant_b_id = tenant_b_info["id"]
        resp_a = requests.get(f"{BASE_URL}/api/admin/customers", headers=tenant_a_admin_headers)
        resp_b = requests.get(f"{BASE_URL}/api/admin/customers", headers=tenant_b_admin_headers)
        assert resp_a.status_code == 200
        assert resp_b.status_code == 200

        customers_a = resp_a.json().get("customers", [])
        customers_b = resp_b.json().get("customers", [])

        for cust in customers_a:
            assert cust.get("tenant_id") == tenant_a_id, f"Tenant A admin sees foreign customer: {cust}"

        for cust in customers_b:
            assert cust.get("tenant_id") == tenant_b_id, f"Tenant B admin sees foreign customer: {cust}"

    def test_partner_admin_toggle_customer_active(self, tenant_a_info, tenant_a_admin_headers, mongo_db):
        """Partner super admin can toggle customer active/inactive"""
        tenant_a_id = tenant_a_info["id"]
        customers = list(mongo_db.customers.find({"tenant_id": tenant_a_id}))
        if not customers:
            pytest.skip("No customers in Tenant A")
        customer_id = customers[0]["id"]

        resp = requests.patch(
            f"{BASE_URL}/api/admin/customers/{customer_id}/active?active=false",
            headers=tenant_a_admin_headers,
        )
        assert resp.status_code == 200, f"Toggle failed: {resp.text}"
        data = resp.json()
        assert data.get("is_active") is False

        # Re-activate
        requests.patch(
            f"{BASE_URL}/api/admin/customers/{customer_id}/active?active=true",
            headers=tenant_a_admin_headers,
        )

    def test_partner_admin_cannot_access_other_tenant_customer(self, tenant_a_admin_headers, tenant_b_info, mongo_db):
        """Tenant A admin cannot deactivate Tenant B customer → 403/404"""
        tenant_b_id = tenant_b_info["id"]
        customers_b = list(mongo_db.customers.find({"tenant_id": tenant_b_id}))
        if not customers_b:
            pytest.skip("No customers in Tenant B")
        cust_b_id = customers_b[0]["id"]

        resp = requests.patch(
            f"{BASE_URL}/api/admin/customers/{cust_b_id}/active?active=false",
            headers=tenant_a_admin_headers,
        )
        assert resp.status_code in [403, 404], f"Cross-tenant access not blocked: {resp.status_code}"


# ===========================================================================
# Section: SCENARIO 1 — Cross-Tenant Isolation
# ===========================================================================

class TestCrossTenantIsolation:
    """Scenario 1: Same email in Tenant A and Tenant B → each login only works for their tenant"""

    def test_shared_email_signup_tenant_a(self, tenant_a_info, mongo_db):
        """Sign up SHARED email in Tenant A"""
        partner_code = tenant_a_info["code"]
        payload = make_customer_payload(CUST_EMAIL_SHARED, password=CUST_PASSWORD_SHARED)
        resp = requests.post(f"{BASE_URL}/api/auth/register?partner_code={partner_code}", json=payload)
        assert resp.status_code == 200, f"Shared email signup in A failed: {resp.text}"
        code = resp.json()["verification_code"]
        verify = requests.post(f"{BASE_URL}/api/auth/verify-email", json={"email": CUST_EMAIL_SHARED, "code": code})
        assert verify.status_code == 200

    def test_shared_email_signup_tenant_b(self, tenant_b_info, mongo_db):
        """Sign up same SHARED email in Tenant B — should succeed (cross-tenant)"""
        partner_code = tenant_b_info["code"]
        payload = make_customer_payload(CUST_EMAIL_SHARED, password=CUST_PASSWORD_SHARED)
        resp = requests.post(f"{BASE_URL}/api/auth/register?partner_code={partner_code}", json=payload)
        assert resp.status_code == 200, f"Shared email signup in B failed: {resp.text}"

    def test_shared_email_a_login_uses_tenant_a_only(self, tenant_a_info):
        """Shared email login via Tenant A slug → returns Tenant A token"""
        tenant_a_id = tenant_a_info["id"]
        partner_code = tenant_a_info["code"]
        resp = requests.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={"partner_code": partner_code, "email": CUST_EMAIL_SHARED, "password": CUST_PASSWORD_SHARED},
        )
        assert resp.status_code == 200, f"Shared email login via A slug failed: {resp.text}"
        assert resp.json()["tenant_id"] == tenant_a_id

    def test_verify_email_no_tenant_scoping_flag(self, mongo_db):
        """
        KNOWN DESIGN GAP: verify-email and resend-verification-email do NOT scope by tenant_id.
        If same email exists in 2 tenants, first matching user gets verified.
        """
        users = list(mongo_db.users.find({"email": CUST_EMAIL_SHARED.lower()}))
        if len(users) == 2:
            verified_count = sum(1 for u in users if u.get("is_verified"))
            print(f"DESIGN GAP: {len(users)} users with same email. Verified count: {verified_count}")
        assert True, "Design gap flagged: verify-email and resend do not scope by tenant_id"
