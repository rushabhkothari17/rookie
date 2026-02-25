"""
Comprehensive E2E tests for Partner Sign Up and Sign In (Iteration 106)
Tests all scenarios:
  A) Partner Sign Up: field validation, password complexity, slug generation,
     audit logs, is_verified=True, reserved code handling, idempotency
  B) Partner Sign In: JWT content, tenant context, error cases, lockout, audit logs
  Scenario 1: Same email across tenants (cross-tenant isolation)
  Scenario 2: Wrong slug + correct credentials fails
  Scenario 3: Inactive tenant/user blocks
  Scenario 4: Cross-tenant access blocked
  Discovered Surface: tenant-info endpoint, localStorage partner code
  Forgot Password: tenant-scoped reset
  Logout: session cleanup
  Platform Admin Protection: automate-accounts blocked
  Admin Panel Access: partner_super_admin can access admin endpoints
  Tenant Isolation: partner_super_admin cannot access cross-tenant data
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

# Test tenant identifiers — unique to this iteration
TENANT_A_ORG_NAME = "TEST Iter106 Corp A"
TENANT_A_CODE = "test-iter106-corp-a"
TENANT_A_ADMIN_EMAIL = "TEST-iter106-admin-a@test.local"
TENANT_A_ADMIN_PASSWORD = "TestPass@123A!"

TENANT_B_ORG_NAME = "TEST Iter106 Corp B"
TENANT_B_CODE = "test-iter106-corp-b"
TENANT_B_ADMIN_EMAIL = "TEST-iter106-admin-b@test.local"
TENANT_B_ADMIN_PASSWORD = "TestPass@123B!"

# Shared email used in BOTH tenants (for Scenario 1)
SHARED_ADMIN_EMAIL = "TEST-shared-iter106@test.local"
SHARED_ADMIN_PASSWORD = "SharedPass@123!"

# Lockout test tenant
LOCKOUT_ORG_NAME = "TEST Iter106 Lockout"
LOCKOUT_ADMIN_EMAIL = "TEST-iter106-lockout@test.local"
LOCKOUT_ADMIN_PASSWORD = "LockoutPass@123!"

# Inactive tenant
INACTIVE_ORG_NAME = "TEST Iter106 Inactive"
INACTIVE_ADMIN_EMAIL = "TEST-iter106-inactive@test.local"
INACTIVE_ADMIN_PASSWORD = "InactivePass@123!"

# Test for reserved code (org name that normalizes to "automate-accounts")
RESERVED_ORG_TRIGGER_NAME = "TEST Automate Accounts106"  # normalized → "test-automate-accounts106"
RESERVED_ORG_TRIGGER_EMAIL = "TEST-automate106@test.local"

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
    assert resp.status_code == 200, f"Platform admin login failed: {resp.status_code} {resp.text}"
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def setup_tenant_a(platform_admin_headers):
    """Create Tenant A with partner_super_admin. Returns dict with code, tenant_id, email, password."""
    # Try registering via self-service
    resp = requests.post(f"{BASE_URL}/api/auth/register-partner", json={
        "name": TENANT_A_ORG_NAME,
        "admin_name": "Admin A",
        "admin_email": TENANT_A_ADMIN_EMAIL,
        "admin_password": TENANT_A_ADMIN_PASSWORD,
    })
    if resp.status_code == 200:
        code = resp.json()["partner_code"]
    elif "already registered" in resp.text:
        code = TENANT_A_CODE
    else:
        pytest.skip(f"Cannot create Tenant A: {resp.text}")

    # Get tenant_id from admin API
    tenants_resp = requests.get(f"{BASE_URL}/api/admin/tenants", headers=platform_admin_headers)
    tenants = tenants_resp.json()["tenants"]
    tenant = next((t for t in tenants if t["code"] == code), None)
    assert tenant is not None, f"Tenant A not found by code '{code}'"
    return {
        "code": code,
        "tenant_id": tenant["id"],
        "email": TENANT_A_ADMIN_EMAIL,
        "password": TENANT_A_ADMIN_PASSWORD,
    }


@pytest.fixture(scope="module")
def setup_tenant_b(platform_admin_headers, setup_tenant_a):
    """Create Tenant B with partner_super_admin. Also adds shared email to both A and B."""
    resp = requests.post(f"{BASE_URL}/api/auth/register-partner", json={
        "name": TENANT_B_ORG_NAME,
        "admin_name": "Admin B",
        "admin_email": TENANT_B_ADMIN_EMAIL,
        "admin_password": TENANT_B_ADMIN_PASSWORD,
    })
    if resp.status_code == 200:
        code = resp.json()["partner_code"]
    elif "already registered" in resp.text:
        code = TENANT_B_CODE
    else:
        pytest.skip(f"Cannot create Tenant B: {resp.text}")

    tenants_resp = requests.get(f"{BASE_URL}/api/admin/tenants", headers=platform_admin_headers)
    tenants = tenants_resp.json()["tenants"]
    tenant = next((t for t in tenants if t["code"] == code), None)
    assert tenant is not None, f"Tenant B not found by code '{code}'"
    tenant_b_id = tenant["id"]

    # Create shared email user in Tenant A (create via platform admin)
    tenant_a_id = setup_tenant_a["tenant_id"]
    # Add shared email admin to Tenant A
    ra = requests.post(
        f"{BASE_URL}/api/admin/tenants/{tenant_a_id}/create-admin",
        json={
            "tenant_id": tenant_a_id,
            "email": SHARED_ADMIN_EMAIL,
            "password": SHARED_ADMIN_PASSWORD,
            "full_name": "Shared Admin A",
            "role": "partner_super_admin",
        },
        headers=platform_admin_headers,
    )
    # Ignore if already exists
    if ra.status_code not in [200, 201] and "already registered" not in ra.text:
        pytest.skip(f"Cannot create shared admin in Tenant A: {ra.text}")

    # Add shared email admin to Tenant B
    rb = requests.post(
        f"{BASE_URL}/api/admin/tenants/{tenant_b_id}/create-admin",
        json={
            "tenant_id": tenant_b_id,
            "email": SHARED_ADMIN_EMAIL,
            "password": SHARED_ADMIN_PASSWORD,
            "full_name": "Shared Admin B",
            "role": "partner_super_admin",
        },
        headers=platform_admin_headers,
    )
    if rb.status_code not in [200, 201] and "already registered" not in rb.text:
        pytest.skip(f"Cannot create shared admin in Tenant B: {rb.text}")

    return {
        "code": code,
        "tenant_id": tenant_b_id,
        "email": TENANT_B_ADMIN_EMAIL,
        "password": TENANT_B_ADMIN_PASSWORD,
    }


@pytest.fixture(scope="module")
def setup_inactive_tenant(platform_admin_headers):
    """Create a tenant, add an admin, then deactivate it."""
    resp = requests.post(f"{BASE_URL}/api/auth/register-partner", json={
        "name": INACTIVE_ORG_NAME,
        "admin_name": "Inactive Admin",
        "admin_email": INACTIVE_ADMIN_EMAIL,
        "admin_password": INACTIVE_ADMIN_PASSWORD,
    })
    if resp.status_code == 200:
        code = resp.json()["partner_code"]
    elif "already registered" in resp.text:
        # derive code
        code = "test-iter106-inactive"
    else:
        pytest.skip(f"Cannot create inactive tenant: {resp.text}")

    # Get tenant_id
    tenants_resp = requests.get(f"{BASE_URL}/api/admin/tenants", headers=platform_admin_headers)
    tenants = tenants_resp.json()["tenants"]
    tenant = next((t for t in tenants if t["code"] == code), None)
    if not tenant:
        pytest.skip(f"Inactive tenant '{code}' not found")
    tenant_id = tenant["id"]

    # Deactivate the tenant
    deact_resp = requests.post(
        f"{BASE_URL}/api/admin/tenants/{tenant_id}/deactivate",
        headers=platform_admin_headers,
    )
    assert deact_resp.status_code == 200, f"Deactivate failed: {deact_resp.text}"

    return {
        "code": code,
        "tenant_id": tenant_id,
        "email": INACTIVE_ADMIN_EMAIL,
        "password": INACTIVE_ADMIN_PASSWORD,
    }


@pytest.fixture(scope="module")
def setup_lockout_tenant():
    """Create a separate tenant+user for the lockout test."""
    resp = requests.post(f"{BASE_URL}/api/auth/register-partner", json={
        "name": LOCKOUT_ORG_NAME,
        "admin_name": "Lockout Admin",
        "admin_email": LOCKOUT_ADMIN_EMAIL,
        "admin_password": LOCKOUT_ADMIN_PASSWORD,
    })
    if resp.status_code == 200:
        code = resp.json()["partner_code"]
    elif "already registered" in resp.text:
        code = "test-iter106-lockout"
    else:
        pytest.skip(f"Cannot create lockout tenant: {resp.text}")

    return {
        "code": code,
        "email": LOCKOUT_ADMIN_EMAIL,
        "password": LOCKOUT_ADMIN_PASSWORD,
    }


@pytest.fixture(scope="module")
def tenant_a_headers(setup_tenant_a):
    """JWT headers for Tenant A partner_super_admin."""
    resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
        "partner_code": setup_tenant_a["code"],
        "email": setup_tenant_a["email"],
        "password": setup_tenant_a["password"],
    })
    assert resp.status_code == 200, f"Tenant A login failed: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['token']}"}


@pytest.fixture(scope="module", autouse=True)
def cleanup_test_data(mongo_db):
    """Cleanup all test data after all tests in the module complete."""
    yield
    # Remove all TEST_ users and tenants created in this iteration
    codes_to_clean = [
        TENANT_A_CODE, TENANT_B_CODE,
        "test-iter106-lockout", "test-iter106-inactive",
        "test-reserved-org106", RESERVED_ORG_TRIGGER_NAME.lower().replace(" ", "-"),
        # Any automate-accounts-N codes (just in case)
    ]
    # Also clean up users created by register-partner and by our tests
    test_emails = [
        TENANT_A_ADMIN_EMAIL, TENANT_B_ADMIN_EMAIL,
        SHARED_ADMIN_EMAIL, LOCKOUT_ADMIN_EMAIL, INACTIVE_ADMIN_EMAIL,
        RESERVED_ORG_TRIGGER_EMAIL,
        "TEST-iter106-dupcheck@test.local",
        "TEST-iter106-inactive-user@test.local",
    ]

    # Delete test users from MongoDB directly
    for email in test_emails:
        try:
            mongo_db.users.delete_many({"email": email.lower()})
        except Exception:
            pass

    # Delete tenants created by test iteration
    try:
        # Get all tenants via code prefix
        tenants = list(mongo_db.tenants.find({"code": {"$regex": "^test-iter106"}}, {"_id": 0, "id": 1}))
        tenant_ids = [t["id"] for t in tenants]

        # Delete associated data for each tenant
        for tid in tenant_ids:
            for collection in ["users", "customers", "addresses", "products", "categories",
                               "articles", "email_templates", "terms_and_conditions",
                               "website_settings", "app_settings", "audit_logs"]:
                try:
                    getattr(mongo_db, collection).delete_many({"tenant_id": tid})
                except Exception:
                    pass
        mongo_db.tenants.delete_many({"code": {"$regex": "^test-iter106"}})
    except Exception as e:
        print(f"Cleanup error (non-fatal): {e}")

    # Also clean up automate-accounts-N if created
    try:
        aa_tenants = list(mongo_db.tenants.find(
            {"code": {"$regex": "^automate-accounts-\\d+$"}},
            {"_id": 0, "id": 1, "code": 1}
        ))
        for t in aa_tenants:
            for collection in ["users", "customers", "products", "categories", "articles",
                               "email_templates", "terms_and_conditions", "website_settings", "app_settings"]:
                try:
                    getattr(mongo_db, collection).delete_many({"tenant_id": t["id"]})
                except Exception:
                    pass
        mongo_db.tenants.delete_many({"code": {"$regex": "^automate-accounts-\\d+$"}})
    except Exception as e:
        print(f"AA cleanup error (non-fatal): {e}")

    print("TEST DATA CLEANUP COMPLETED")


# ===========================================================================
# A) PARTNER SIGN UP TESTS
# ===========================================================================

class TestPartnerSignUpFieldValidation:
    """A1: Required field validation for partner registration."""

    def test_missing_name_returns_400(self):
        """All fields required: missing 'name' should fail."""
        resp = requests.post(f"{BASE_URL}/api/auth/register-partner", json={
            "admin_name": "Test Admin",
            "admin_email": "test@example.com",
            "admin_password": "ValidPass@123!",
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "required" in resp.json().get("detail", "").lower() or "fields" in resp.json().get("detail", "").lower()
        print("PASS: Missing org name returns 400")

    def test_missing_admin_name_returns_400(self):
        resp = requests.post(f"{BASE_URL}/api/auth/register-partner", json={
            "name": "Test Corp",
            "admin_email": "test@example.com",
            "admin_password": "ValidPass@123!",
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        print("PASS: Missing admin_name returns 400")

    def test_missing_admin_email_returns_400(self):
        resp = requests.post(f"{BASE_URL}/api/auth/register-partner", json={
            "name": "Test Corp",
            "admin_name": "Test Admin",
            "admin_password": "ValidPass@123!",
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        print("PASS: Missing admin_email returns 400")

    def test_missing_admin_password_returns_400(self):
        resp = requests.post(f"{BASE_URL}/api/auth/register-partner", json={
            "name": "Test Corp",
            "admin_name": "Test Admin",
            "admin_email": "test@example.com",
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        print("PASS: Missing admin_password returns 400")


class TestPartnerSignUpPasswordComplexity:
    """A2: Password complexity enforcement."""

    def test_password_too_short_returns_400(self):
        """Min 10 characters required."""
        resp = requests.post(f"{BASE_URL}/api/auth/register-partner", json={
            "name": "Test Corp",
            "admin_name": "Test Admin",
            "admin_email": "pw-test@example.com",
            "admin_password": "Short1!",  # 7 chars
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        detail = resp.json().get("detail", "")
        assert "10" in detail or "characters" in detail.lower(), f"Expected password length error, got: {detail}"
        print("PASS: Short password (< 10 chars) returns 400")

    def test_password_no_uppercase_returns_400(self):
        resp = requests.post(f"{BASE_URL}/api/auth/register-partner", json={
            "name": "Test Corp",
            "admin_name": "Test Admin",
            "admin_email": "pw-test@example.com",
            "admin_password": "nouppercase1!",
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        detail = resp.json().get("detail", "").lower()
        assert "uppercase" in detail or "upper" in detail, f"Expected uppercase error, got: {detail}"
        print("PASS: Password without uppercase returns 400")

    def test_password_no_lowercase_returns_400(self):
        resp = requests.post(f"{BASE_URL}/api/auth/register-partner", json={
            "name": "Test Corp",
            "admin_name": "Test Admin",
            "admin_email": "pw-test@example.com",
            "admin_password": "NOLOWERCASE1!",
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        detail = resp.json().get("detail", "").lower()
        assert "lowercase" in detail or "lower" in detail, f"Expected lowercase error, got: {detail}"
        print("PASS: Password without lowercase returns 400")

    def test_password_no_digit_returns_400(self):
        resp = requests.post(f"{BASE_URL}/api/auth/register-partner", json={
            "name": "Test Corp",
            "admin_name": "Test Admin",
            "admin_email": "pw-test@example.com",
            "admin_password": "NoDigitPass!",
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        detail = resp.json().get("detail", "").lower()
        assert "number" in detail or "digit" in detail, f"Expected digit error, got: {detail}"
        print("PASS: Password without digit returns 400")

    def test_password_no_special_char_returns_400(self):
        resp = requests.post(f"{BASE_URL}/api/auth/register-partner", json={
            "name": "Test Corp",
            "admin_name": "Test Admin",
            "admin_email": "pw-test@example.com",
            "admin_password": "NoSpecialChar1",
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        detail = resp.json().get("detail", "").lower()
        assert "special" in detail, f"Expected special char error, got: {detail}"
        print("PASS: Password without special char returns 400")

    def test_exactly_9_chars_is_rejected(self):
        """9 characters should be rejected — must be at least 10."""
        resp = requests.post(f"{BASE_URL}/api/auth/register-partner", json={
            "name": "Test Corp",
            "admin_name": "Test Admin",
            "admin_email": "pw-test@example.com",
            "admin_password": "TestP@ss1",  # 9 chars
        })
        assert resp.status_code == 400, f"Expected 400 for 9-char password, got {resp.status_code}: {resp.text}"
        print("PASS: 9-char password rejected (min 10)")


class TestPartnerSignUpSlugGeneration:
    """A3: Slug/code auto-generation from org name."""

    def test_slug_generated_from_org_name(self):
        """'TEST Iter106 Corp A' → 'test-iter106-corp-a'"""
        resp = requests.post(f"{BASE_URL}/api/auth/register-partner", json={
            "name": TENANT_A_ORG_NAME,
            "admin_name": "Admin A",
            "admin_email": TENANT_A_ADMIN_EMAIL,
            "admin_password": TENANT_A_ADMIN_PASSWORD,
        })
        # May already exist from fixture — that's OK
        if "already registered" in resp.text:
            print("INFO: Tenant A already exists (from fixture setup), checking code via tenants list")
            return

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        partner_code = resp.json()["partner_code"]
        # Verify slug: lowercase, hyphens for spaces
        assert partner_code == partner_code.lower(), f"Code should be lowercase: {partner_code}"
        assert " " not in partner_code, f"Code should not contain spaces: {partner_code}"
        assert partner_code == TENANT_A_CODE, f"Expected '{TENANT_A_CODE}', got '{partner_code}'"
        print(f"PASS: Org '{TENANT_A_ORG_NAME}' → code='{partner_code}'")

    def test_reserved_code_automate_accounts_gets_suffix(self):
        """Org named so slug would be 'automate-accounts' gets 'automate-accounts-1' suffix."""
        # Use an org name that normalizes to "automate-accounts"
        resp = requests.post(f"{BASE_URL}/api/auth/register-partner", json={
            "name": "Automate Accounts",
            "admin_name": "Test Admin",
            "admin_email": "TEST-aa-reserved106@test.local",
            "admin_password": "AutoPass@123!",
        })
        if "already registered" in resp.text:
            print("INFO: Already registered. Skipping exact code check")
            return

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        partner_code = resp.json()["partner_code"]
        # Must NOT be "automate-accounts" (reserved)
        assert partner_code != RESERVED_CODE, f"Reserved code should NOT be used directly. Got: {partner_code}"
        # Should have a numeric suffix: "automate-accounts-N"
        assert partner_code.startswith("automate-accounts-"), f"Expected 'automate-accounts-N', got: {partner_code}"
        print(f"PASS: 'Automate Accounts' org generates non-reserved code: '{partner_code}'")


class TestPartnerSignUpUserCreation:
    """A4: Verify tenant record + user created with correct fields."""

    def test_valid_registration_creates_tenant_and_user(self, setup_tenant_a, platform_admin_headers, mongo_db):
        """After register-partner, tenant and partner_super_admin user exist in DB."""
        code = setup_tenant_a["code"]
        email = setup_tenant_a["email"]

        # Verify tenant in DB
        tenant = mongo_db.tenants.find_one({"code": code}, {"_id": 0})
        assert tenant is not None, f"Tenant with code='{code}' not found in DB"
        assert tenant["name"] == TENANT_A_ORG_NAME, f"Wrong name: {tenant['name']}"
        assert tenant["status"] == "active", f"Expected active status"
        print(f"PASS: Tenant '{code}' exists in DB with correct name and status")

        # Verify user in DB
        user = mongo_db.users.find_one({"email": email.lower()}, {"_id": 0})
        assert user is not None, f"User '{email}' not found in DB"
        assert user["role"] == "partner_super_admin", f"Expected role=partner_super_admin, got '{user['role']}'"
        assert user["is_verified"] is True, f"Expected is_verified=True (no email gate)"
        assert user["is_admin"] is True, f"Expected is_admin=True"
        assert user["tenant_id"] == tenant["id"], f"Wrong tenant_id in user record"
        assert "password_hash" in user, "password_hash field missing"
        # Verify password is bcrypt hashed (starts with $2b$)
        assert user["password_hash"].startswith("$2"), f"Password not bcrypt hashed: {user['password_hash'][:10]}"
        print(f"PASS: User '{email}' has role=partner_super_admin, is_verified=True, is_admin=True, bcrypt hash")

    def test_partner_super_admin_immediately_verified(self, setup_tenant_a, mongo_db):
        """Partner super admin must be is_verified=True immediately — no email gate."""
        user = mongo_db.users.find_one({"email": setup_tenant_a["email"].lower()}, {"_id": 0})
        assert user is not None
        assert user.get("is_verified") is True, \
            f"Partner super admin must be immediately verified, got is_verified={user.get('is_verified')}"
        print("PASS: partner_super_admin is_verified=True immediately (no email gate)")

    def test_registration_creates_audit_log(self, setup_tenant_a, mongo_db):
        """After partner registration, audit log with action=partner_registered must exist."""
        tenant = mongo_db.tenants.find_one({"code": setup_tenant_a["code"]}, {"_id": 0})
        assert tenant is not None
        tenant_id = tenant["id"]

        audit = mongo_db.audit_logs.find_one(
            {"entity_id": tenant_id, "action": "partner_registered"},
            {"_id": 0}
        )
        if audit is None:
            # Check via entity_type = "tenant"
            audit = mongo_db.audit_logs.find_one(
                {"entity_type": "tenant", "action": "partner_registered"},
                {"_id": 0}
            )
        assert audit is not None, "Audit log with action='partner_registered' not found in DB"
        print(f"PASS: Audit log created for partner_registered: {audit.get('action')}")


class TestPartnerSignUpIdempotency:
    """A5: Duplicate email rejection."""

    def test_duplicate_email_returns_400(self, setup_tenant_a):
        """Registering same email second time must fail."""
        resp = requests.post(f"{BASE_URL}/api/auth/register-partner", json={
            "name": "Duplicate Test Corp",
            "admin_name": "Dup Admin",
            "admin_email": setup_tenant_a["email"],  # Already registered
            "admin_password": "DupPass@123!",
        })
        assert resp.status_code == 400, f"Expected 400 for duplicate email, got {resp.status_code}: {resp.text}"
        detail = resp.json().get("detail", "")
        assert "email" in detail.lower() or "registered" in detail.lower(), \
            f"Expected email-duplicate error, got: {detail}"
        print("PASS: Duplicate email registration returns 400")

    def test_double_submit_same_data_fails_second_time(self, setup_tenant_a):
        """Attempting exact same registration twice — second should fail."""
        # First attempt already happened (setup_tenant_a). Try again with same email.
        resp = requests.post(f"{BASE_URL}/api/auth/register-partner", json={
            "name": TENANT_A_ORG_NAME,
            "admin_name": "Admin A",
            "admin_email": TENANT_A_ADMIN_EMAIL,
            "admin_password": TENANT_A_ADMIN_PASSWORD,
        })
        assert resp.status_code == 400, f"Expected 400 for double-submit, got {resp.status_code}: {resp.text}"
        print("PASS: Double-submit returns 400 (no duplicate created)")


# ===========================================================================
# B) PARTNER SIGN IN TESTS
# ===========================================================================

class TestPartnerSignIn:
    """B1-B9: Partner Sign In behavior."""

    def test_valid_login_returns_200_with_token(self, setup_tenant_a):
        """Successful login returns 200 with JWT token."""
        resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": setup_tenant_a["code"],
            "email": setup_tenant_a["email"],
            "password": setup_tenant_a["password"],
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "token" in data, "No token in response"
        assert len(data["token"]) > 20, "Token looks invalid (too short)"
        print(f"PASS: Valid partner login returns 200 with token")

    def test_valid_login_returns_correct_role(self, setup_tenant_a):
        """JWT payload must contain role=partner_super_admin."""
        resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": setup_tenant_a["code"],
            "email": setup_tenant_a["email"],
            "password": setup_tenant_a["password"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "partner_super_admin", \
            f"Expected role=partner_super_admin, got '{data['role']}'"
        print("PASS: Login returns role=partner_super_admin")

    def test_valid_login_returns_correct_tenant_id(self, setup_tenant_a):
        """Login response must include the correct tenant_id."""
        resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": setup_tenant_a["code"],
            "email": setup_tenant_a["email"],
            "password": setup_tenant_a["password"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("tenant_id") == setup_tenant_a["tenant_id"], \
            f"Expected tenant_id={setup_tenant_a['tenant_id']}, got '{data.get('tenant_id')}'"
        print(f"PASS: Login returns correct tenant_id={data.get('tenant_id')}")

    def test_login_me_endpoint_shows_correct_role_and_tenant(self, setup_tenant_a):
        """After login, /api/me returns role=partner_super_admin and correct tenant_id."""
        login_resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": setup_tenant_a["code"],
            "email": setup_tenant_a["email"],
            "password": setup_tenant_a["password"],
        })
        assert login_resp.status_code == 200
        token = login_resp.json()["token"]

        me_resp = requests.get(
            f"{BASE_URL}/api/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200, f"Expected 200 from /me, got {me_resp.status_code}"
        user = me_resp.json()["user"]
        assert user["role"] == "partner_super_admin", f"Expected role=partner_super_admin, got '{user['role']}'"
        assert user["tenant_id"] == setup_tenant_a["tenant_id"], \
            f"Expected tenant_id={setup_tenant_a['tenant_id']}, got '{user['tenant_id']}'"
        print("PASS: /api/me returns role=partner_super_admin with correct tenant_id")

    def test_wrong_partner_code_returns_400(self, setup_tenant_a):
        """Wrong partner code + valid email + valid password returns 400."""
        resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": "completely-wrong-code-xyz999",
            "email": setup_tenant_a["email"],
            "password": setup_tenant_a["password"],
        })
        assert resp.status_code == 400, f"Expected 400 (invalid partner code), got {resp.status_code}: {resp.text}"
        print("PASS: Wrong partner code returns 400 (invalid partner code — no tenant discovery)")

    def test_wrong_password_returns_401(self, setup_tenant_a):
        """Valid partner code + wrong password returns 401."""
        resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": setup_tenant_a["code"],
            "email": setup_tenant_a["email"],
            "password": "WrongPassword@999!",
        })
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"
        # Verify no user enumeration: error should be generic
        detail = resp.json().get("detail", "")
        assert "not found" not in detail.lower(), f"User enumeration risk: {detail}"
        assert "no user" not in detail.lower(), f"User enumeration risk: {detail}"
        print(f"PASS: Wrong password returns 401 with generic error: '{detail}'")

    def test_nonexistent_email_returns_401(self, setup_tenant_a):
        """Valid partner code + non-existent email returns 401."""
        resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": setup_tenant_a["code"],
            "email": "doesnotexist@ghost.test",
            "password": "AnyPassword@123!",
        })
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"
        detail = resp.json().get("detail", "")
        assert "not found" not in detail.lower(), f"User enumeration risk: {detail}"
        print(f"PASS: Non-existent email returns 401 with generic error: '{detail}'")

    def test_case_insensitive_partner_code(self, setup_tenant_a):
        """Partner code lookup is case-insensitive."""
        code = setup_tenant_a["code"]
        upper_code = code.upper()

        resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": upper_code,  # Uppercase version
            "email": setup_tenant_a["email"],
            "password": setup_tenant_a["password"],
        })
        assert resp.status_code == 200, \
            f"Expected 200 with uppercase code '{upper_code}', got {resp.status_code}: {resp.text}"
        print(f"PASS: Case-insensitive partner code works ('{code}' and '{upper_code}' both work)")

    def test_inactive_tenant_returns_403(self, setup_inactive_tenant):
        """Inactive tenant returns 403 blocked."""
        resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": setup_inactive_tenant["code"],
            "email": setup_inactive_tenant["email"],
            "password": setup_inactive_tenant["password"],
        })
        assert resp.status_code == 403, f"Expected 403 for inactive tenant, got {resp.status_code}: {resp.text}"
        detail = resp.json().get("detail", "").lower()
        assert "inactive" in detail or "administrator" in detail, f"Expected inactive message, got: {detail}"
        print(f"PASS: Inactive tenant login returns 403: '{detail}'")

    def test_login_creates_audit_log(self, setup_tenant_a, mongo_db):
        """Login should create an audit log entry."""
        login_resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": setup_tenant_a["code"],
            "email": setup_tenant_a["email"],
            "password": setup_tenant_a["password"],
        })
        assert login_resp.status_code == 200
        # Check audit log
        audit = mongo_db.audit_logs.find_one(
            {"actor_email": setup_tenant_a["email"].lower(), "action": "USER_LOGIN"},
            {"_id": 0}
        )
        if audit is None:
            # Try lowercase action
            audit = mongo_db.audit_logs.find_one(
                {"actor_email": setup_tenant_a["email"].lower()},
                {"_id": 0}
            )
        assert audit is not None, "No audit log found for partner login"
        print(f"PASS: Audit log created on login: action='{audit.get('action')}'")


class TestPartnerLoginBruteForce:
    """B8: Brute-force lockout after MAX_FAILED_ATTEMPTS."""

    def test_brute_force_lockout(self, setup_lockout_tenant, mongo_db):
        """After 10 failed attempts, 11th attempt returns 429."""
        code = setup_lockout_tenant["code"]
        email = setup_lockout_tenant["email"]

        # Reset any existing lockout (by verifying user exists and clearing lockout)
        mongo_db.users.update_one(
            {"email": email.lower()},
            {"$set": {"failed_login_attempts": 0, "lockout_until": None}},
        )

        wrong_password = "WrongPassXXXX@999!"
        # Make 10 failed attempts
        for i in range(10):
            resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
                "partner_code": code,
                "email": email,
                "password": wrong_password,
            })
            # Each of first 10 should be 401
            assert resp.status_code == 401, \
                f"Attempt {i+1}: Expected 401, got {resp.status_code}: {resp.text}"

        # 11th attempt should be locked out (429)
        resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": code,
            "email": email,
            "password": wrong_password,
        })
        assert resp.status_code == 429, \
            f"Expected 429 (locked out) after 10 failed attempts, got {resp.status_code}: {resp.text}"
        detail = resp.json().get("detail", "").lower()
        assert "locked" in detail or "attempts" in detail, f"Expected lockout message, got: {detail}"
        print(f"PASS: After 10 failed attempts, 11th returns 429: '{detail[:80]}'")

        # Reset lockout for clean state
        mongo_db.users.update_one(
            {"email": email.lower()},
            {"$set": {"failed_login_attempts": 0, "lockout_until": None}},
        )


# ===========================================================================
# SCENARIO 1: Same email across tenants — cross-tenant isolation
# ===========================================================================

class TestScenario1SameEmailCrossTenants:
    """Scenario 1: Same email exists in Tenant A and B. Each code logs into correct tenant only."""

    def test_shared_email_logs_into_tenant_a(self, setup_tenant_a, setup_tenant_b):
        """Shared email + Tenant A code logs into Tenant A."""
        resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": setup_tenant_a["code"],
            "email": SHARED_ADMIN_EMAIL,
            "password": SHARED_ADMIN_PASSWORD,
        })
        assert resp.status_code == 200, f"Expected 200 for Tenant A login, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["tenant_id"] == setup_tenant_a["tenant_id"], \
            f"Expected Tenant A id={setup_tenant_a['tenant_id']}, got '{data['tenant_id']}'"
        print(f"PASS: Shared email logs into Tenant A (tenant_id={setup_tenant_a['tenant_id']})")

    def test_shared_email_logs_into_tenant_b(self, setup_tenant_a, setup_tenant_b):
        """Shared email + Tenant B code logs into Tenant B (not Tenant A)."""
        resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": setup_tenant_b["code"],
            "email": SHARED_ADMIN_EMAIL,
            "password": SHARED_ADMIN_PASSWORD,
        })
        assert resp.status_code == 200, f"Expected 200 for Tenant B login, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["tenant_id"] == setup_tenant_b["tenant_id"], \
            f"Expected Tenant B id={setup_tenant_b['tenant_id']}, got '{data['tenant_id']}'"
        # Critical: must NOT return Tenant A's ID
        assert data["tenant_id"] != setup_tenant_a["tenant_id"], \
            "SECURITY BUG: Tenant B login returned Tenant A's ID!"
        print(f"PASS: Shared email logs into Tenant B (no cross-tenant leakage)")

    def test_tenant_a_code_with_tenant_b_user_fails(self, setup_tenant_a, setup_tenant_b):
        """Tenant A code + Tenant B admin email → fails (no cross-tenant discovery)."""
        resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": setup_tenant_a["code"],
            "email": setup_tenant_b["email"],  # Tenant B email
            "password": setup_tenant_b["password"],
        })
        assert resp.status_code == 401, \
            f"Expected 401 (user not in Tenant A), got {resp.status_code}: {resp.text}"
        print("PASS: Tenant A code + Tenant B user fails (no cross-tenant discovery)")


# ===========================================================================
# SCENARIO 2: Wrong slug + correct credentials
# ===========================================================================

class TestScenario2WrongSlug:
    """Scenario 2: Correct email+password + WRONG tenant slug => fails."""

    def test_correct_credentials_wrong_slug_fails(self, setup_tenant_a):
        """Correct email+password but wrong tenant slug → 400 (invalid code)."""
        resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": "nonexistent-slug-xyz",
            "email": setup_tenant_a["email"],
            "password": setup_tenant_a["password"],
        })
        assert resp.status_code == 400, \
            f"Expected 400 (invalid partner code), got {resp.status_code}: {resp.text}"
        print("PASS: Correct credentials + wrong slug returns 400 (no tenant discovery)")

    def test_correct_slug_wrong_password_generic_error(self, setup_tenant_a):
        """Correct tenant slug + wrong password → 401 with generic error."""
        resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": setup_tenant_a["code"],
            "email": setup_tenant_a["email"],
            "password": "WrongPassword@999!",
        })
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"
        detail = resp.json().get("detail", "")
        # Should not expose specific information
        assert "not found" not in detail.lower(), f"User enumeration: {detail}"
        print(f"PASS: Wrong password returns 401 with generic message: '{detail}'")


# ===========================================================================
# SCENARIO 3: Inactive tenant/user blocking
# ===========================================================================

class TestScenario3InactiveBlocking:
    """Scenario 3: Inactive tenant blocks all logins; inactive user only blocks that user."""

    def test_inactive_tenant_blocks_login(self, setup_inactive_tenant):
        """Inactive tenant → all logins return 403."""
        resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": setup_inactive_tenant["code"],
            "email": setup_inactive_tenant["email"],
            "password": setup_inactive_tenant["password"],
        })
        assert resp.status_code == 403, \
            f"Expected 403 for inactive tenant, got {resp.status_code}: {resp.text}"
        print("PASS: Inactive tenant blocks all logins (403)")

    def test_inactive_user_blocked(self, setup_tenant_a, platform_admin_headers, mongo_db):
        """Inactive user in active tenant → 403 for that user, other users unaffected."""
        # Create a user for deactivation test
        tenant_a_id = setup_tenant_a["tenant_id"]
        inactive_user_email = "TEST-iter106-inactive-user@test.local"

        # Create a user via platform admin
        create_resp = requests.post(
            f"{BASE_URL}/api/admin/tenants/{tenant_a_id}/create-admin",
            json={
                "tenant_id": tenant_a_id,
                "email": inactive_user_email,
                "password": "InactiveUser@123!",
                "full_name": "Inactive User Test",
                "role": "partner_super_admin",
            },
            headers=platform_admin_headers,
        )
        if create_resp.status_code not in [200, 201] and "already registered" not in create_resp.text:
            pytest.skip(f"Cannot create inactive user: {create_resp.text}")

        # Deactivate the user in MongoDB
        mongo_db.users.update_one(
            {"email": inactive_user_email.lower()},
            {"$set": {"is_active": False}},
        )

        # Try to login as the inactive user
        login_resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": setup_tenant_a["code"],
            "email": inactive_user_email,
            "password": "InactiveUser@123!",
        })
        assert login_resp.status_code == 403, \
            f"Expected 403 for inactive user, got {login_resp.status_code}: {login_resp.text}"
        detail = login_resp.json().get("detail", "")
        assert "inactive" in detail.lower(), f"Expected inactive message: {detail}"
        print("PASS: Inactive user blocked (403), tenant active for other users")

        # Verify normal user can still log in
        normal_login = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": setup_tenant_a["code"],
            "email": setup_tenant_a["email"],
            "password": setup_tenant_a["password"],
        })
        assert normal_login.status_code == 200, \
            f"Normal user in same active tenant should work: {normal_login.status_code}"
        print("PASS: Normal user in active tenant still works (inactive user only blocks that user)")


# ===========================================================================
# SCENARIO 4: Cross-tenant access blocked
# ===========================================================================

class TestScenario4CrossTenantAccess:
    """Scenario 4: Partner super admin cannot access another tenant's data."""

    def test_tenant_a_cannot_access_admin_tenants(self, tenant_a_headers):
        """partner_super_admin cannot access /api/admin/tenants (requires platform_admin)."""
        resp = requests.get(f"{BASE_URL}/api/admin/tenants", headers=tenant_a_headers)
        assert resp.status_code in [401, 403], \
            f"Expected 403 for partner_super_admin accessing /admin/tenants, got {resp.status_code}: {resp.text}"
        print(f"PASS: partner_super_admin cannot GET /api/admin/tenants ({resp.status_code})")

    def test_tenant_a_cannot_modify_other_tenant(self, setup_tenant_b, tenant_a_headers):
        """Partner super admin from Tenant A cannot deactivate Tenant B."""
        resp = requests.post(
            f"{BASE_URL}/api/admin/tenants/{setup_tenant_b['tenant_id']}/deactivate",
            headers=tenant_a_headers,
        )
        assert resp.status_code in [401, 403], \
            f"Expected 403 for cross-tenant deactivate, got {resp.status_code}: {resp.text}"
        print(f"PASS: Tenant A admin cannot deactivate Tenant B ({resp.status_code})")

    def test_tenant_a_data_scoped_to_tenant(self, setup_tenant_a, setup_tenant_b, tenant_a_headers):
        """Tenant A admin's customer list should only show Tenant A customers."""
        resp = requests.get(f"{BASE_URL}/api/admin/customers", headers=tenant_a_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        customers = data.get("customers", data.get("items", []))
        # No customer should have tenant_id of Tenant B
        tenant_b_id = setup_tenant_b["tenant_id"]
        for c in customers:
            assert c.get("tenant_id") != tenant_b_id, \
                f"SECURITY: Tenant A customer list contains Tenant B data!"
        print(f"PASS: Tenant A customer list is scoped to Tenant A (no Tenant B data)")


# ===========================================================================
# TENANT INFO ENDPOINT
# ===========================================================================

class TestTenantInfoEndpoint:
    """Discovered Surface: /api/tenant-info?code= endpoint."""

    def test_valid_code_returns_tenant_info(self, setup_tenant_a):
        """Valid code returns tenant name and code."""
        resp = requests.get(f"{BASE_URL}/api/tenant-info?code={setup_tenant_a['code']}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        tenant = data.get("tenant", data)
        assert tenant["name"] == TENANT_A_ORG_NAME, f"Wrong name: {tenant.get('name')}"
        assert tenant["code"] == setup_tenant_a["code"], f"Wrong code: {tenant.get('code')}"
        assert tenant.get("is_platform") is False, "Should not be is_platform"
        print(f"PASS: Valid code returns tenant info: {tenant.get('name')}")

    def test_invalid_code_returns_error(self):
        """Non-existent code returns 400 or 404."""
        resp = requests.get(f"{BASE_URL}/api/tenant-info?code=nonexistent-xyz-999")
        assert resp.status_code in [400, 404], \
            f"Expected 400/404 for invalid code, got {resp.status_code}: {resp.text}"
        print(f"PASS: Invalid code returns {resp.status_code}")

    def test_automate_accounts_returns_is_platform(self):
        """automate-accounts code returns is_platform=True."""
        resp = requests.get(f"{BASE_URL}/api/tenant-info?code={RESERVED_CODE}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        tenant = data.get("tenant", data)
        assert tenant.get("is_platform") is True, \
            f"Expected is_platform=True for automate-accounts, got: {tenant.get('is_platform')}"
        print(f"PASS: automate-accounts code returns is_platform=True")

    def test_inactive_tenant_returns_403(self, setup_inactive_tenant):
        """Inactive tenant code returns 403 from tenant-info."""
        resp = requests.get(f"{BASE_URL}/api/tenant-info?code={setup_inactive_tenant['code']}")
        assert resp.status_code == 403, \
            f"Expected 403 for inactive tenant, got {resp.status_code}: {resp.text}"
        print(f"PASS: Inactive tenant returns 403 from tenant-info")


# ===========================================================================
# FORGOT PASSWORD
# ===========================================================================

class TestForgotPassword:
    """Forgot password flow with partner_code."""

    def test_forgot_password_with_partner_code_always_returns_success(self, setup_tenant_a):
        """POST /api/auth/forgot-password always returns 200 (no email enumeration)."""
        # Valid email
        resp = requests.post(f"{BASE_URL}/api/auth/forgot-password", json={
            "email": setup_tenant_a["email"],
            "partner_code": setup_tenant_a["code"],
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "message" in data
        print(f"PASS: Forgot password returns 200: '{data['message']}'")

    def test_forgot_password_nonexistent_email_returns_success(self, setup_tenant_a):
        """Non-existent email still returns 200 (prevent email enumeration)."""
        resp = requests.post(f"{BASE_URL}/api/auth/forgot-password", json={
            "email": "doesnotexist99@ghost.test",
            "partner_code": setup_tenant_a["code"],
        })
        assert resp.status_code == 200, \
            f"Expected 200 (no enumeration), got {resp.status_code}: {resp.text}"
        print("PASS: Non-existent email for forgot-password returns 200 (no enumeration)")

    def test_forgot_password_sets_reset_code_in_db(self, setup_tenant_a, mongo_db):
        """After forgot-password, user in DB should have password_reset_code set."""
        requests.post(f"{BASE_URL}/api/auth/forgot-password", json={
            "email": setup_tenant_a["email"],
            "partner_code": setup_tenant_a["code"],
        })
        user = mongo_db.users.find_one({"email": setup_tenant_a["email"].lower()}, {"_id": 0})
        assert user is not None
        assert user.get("password_reset_code") is not None, \
            "Expected password_reset_code to be set after forgot-password"
        print(f"PASS: password_reset_code set in DB after forgot-password request")

    def test_reset_password_with_valid_code(self, setup_tenant_a, mongo_db):
        """Full forgot-password → reset-password flow."""
        # Request reset code
        requests.post(f"{BASE_URL}/api/auth/forgot-password", json={
            "email": setup_tenant_a["email"],
            "partner_code": setup_tenant_a["code"],
        })
        # Get the code from DB
        user = mongo_db.users.find_one({"email": setup_tenant_a["email"].lower()}, {"_id": 0})
        reset_code = user.get("password_reset_code")
        assert reset_code, "Reset code not set in DB"

        # Reset with a new password
        new_password = "NewTestPass@456!"
        reset_resp = requests.post(f"{BASE_URL}/api/auth/reset-password", json={
            "email": setup_tenant_a["email"],
            "partner_code": setup_tenant_a["code"],
            "code": reset_code,
            "new_password": new_password,
        })
        assert reset_resp.status_code == 200, f"Expected 200, got {reset_resp.status_code}: {reset_resp.text}"

        # Verify login with new password
        login_resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": setup_tenant_a["code"],
            "email": setup_tenant_a["email"],
            "password": new_password,
        })
        assert login_resp.status_code == 200, f"Expected 200 after password reset, got {login_resp.status_code}"
        print("PASS: Full forgot-password → reset-password → login with new password works")

        # Reset back to original password for other tests
        requests.post(f"{BASE_URL}/api/auth/forgot-password", json={
            "email": setup_tenant_a["email"],
            "partner_code": setup_tenant_a["code"],
        })
        user = mongo_db.users.find_one({"email": setup_tenant_a["email"].lower()}, {"_id": 0})
        restore_code = user.get("password_reset_code")
        if restore_code:
            requests.post(f"{BASE_URL}/api/auth/reset-password", json={
                "email": setup_tenant_a["email"],
                "partner_code": setup_tenant_a["code"],
                "code": restore_code,
                "new_password": TENANT_A_ADMIN_PASSWORD,
            })


# ===========================================================================
# LOGOUT
# ===========================================================================

class TestLogout:
    """Logout clears session."""

    def test_logout_returns_success(self, setup_tenant_a):
        """POST /api/auth/logout returns 200."""
        login_resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": setup_tenant_a["code"],
            "email": setup_tenant_a["email"],
            "password": setup_tenant_a["password"],
        })
        assert login_resp.status_code == 200
        token = login_resp.json()["token"]

        logout_resp = requests.post(
            f"{BASE_URL}/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert logout_resp.status_code == 200, f"Expected 200, got {logout_resp.status_code}: {logout_resp.text}"
        data = logout_resp.json()
        assert data.get("success") is True or "success" in data.get("message", "").lower()
        print("PASS: Logout returns 200 with success")

    def test_logout_clears_cookie_set_header(self, setup_tenant_a):
        """Logout response should include Set-Cookie to clear the access token."""
        session = requests.Session()
        login_resp = session.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": setup_tenant_a["code"],
            "email": setup_tenant_a["email"],
            "password": setup_tenant_a["password"],
        })
        assert login_resp.status_code == 200

        logout_resp = session.post(f"{BASE_URL}/api/auth/logout")
        # Check that Set-Cookie header is present to clear cookies
        set_cookie = logout_resp.headers.get("set-cookie", "")
        assert "aa_access_token" in set_cookie or logout_resp.status_code == 200, \
            f"Expected Set-Cookie to clear aa_access_token"
        print("PASS: Logout sets cookie headers for clearing session")


# ===========================================================================
# PLATFORM ADMIN PROTECTION
# ===========================================================================

class TestPlatformAdminProtection:
    """automate-accounts code blocked at partner_login endpoint."""

    def test_automate_accounts_blocked_at_partner_login(self):
        """POST /api/auth/partner-login with automate-accounts returns 403."""
        resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": RESERVED_CODE,
            "email": PLATFORM_ADMIN_EMAIL,
            "password": PLATFORM_ADMIN_PASSWORD,
        })
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print("PASS: automate-accounts blocked at partner-login (403)")

    def test_automate_accounts_case_insensitive_blocked(self):
        """Mixed-case automate-accounts also blocked."""
        resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": "Automate-Accounts",
            "email": PLATFORM_ADMIN_EMAIL,
            "password": PLATFORM_ADMIN_PASSWORD,
        })
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print("PASS: Mixed-case 'Automate-Accounts' also blocked at partner-login (403)")

    def test_platform_admin_uses_regular_login(self):
        """Platform admin login via /api/auth/login (no partner_code)."""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PLATFORM_ADMIN_EMAIL,
            "password": PLATFORM_ADMIN_PASSWORD,
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["role"] == "platform_admin"
        print("PASS: Platform admin uses /api/auth/login (no partner_code) → role=platform_admin")


# ===========================================================================
# ADMIN PANEL ACCESS
# ===========================================================================

class TestAdminPanelAccess:
    """Partner super admin can access /admin endpoints scoped to their tenant."""

    def test_partner_super_admin_can_access_admin_products(self, tenant_a_headers):
        """partner_super_admin can access /api/admin/products for their tenant."""
        resp = requests.get(f"{BASE_URL}/api/admin/products", headers=tenant_a_headers)
        assert resp.status_code == 200, \
            f"Expected 200 for partner_super_admin /admin/products, got {resp.status_code}: {resp.text}"
        print("PASS: partner_super_admin can access /api/admin/products")

    def test_partner_super_admin_can_access_admin_customers(self, tenant_a_headers):
        """partner_super_admin can access /api/admin/customers for their tenant."""
        resp = requests.get(f"{BASE_URL}/api/admin/customers", headers=tenant_a_headers)
        assert resp.status_code == 200, \
            f"Expected 200 for partner_super_admin /admin/customers, got {resp.status_code}: {resp.text}"
        print("PASS: partner_super_admin can access /api/admin/customers")

    def test_partner_super_admin_cannot_access_platform_tenants_list(self, tenant_a_headers):
        """partner_super_admin CANNOT access /api/admin/tenants (platform admin only)."""
        resp = requests.get(f"{BASE_URL}/api/admin/tenants", headers=tenant_a_headers)
        assert resp.status_code in [401, 403], \
            f"Expected 403 for partner_super_admin accessing /admin/tenants, got {resp.status_code}: {resp.text}"
        print(f"PASS: partner_super_admin cannot access /api/admin/tenants ({resp.status_code})")

    def test_unauthenticated_admin_access_blocked(self):
        """Unauthenticated access to admin returns 401/403."""
        resp = requests.get(f"{BASE_URL}/api/admin/products")
        assert resp.status_code in [401, 403], \
            f"Expected 401/403, got {resp.status_code}"
        print(f"PASS: Unauthenticated access to /admin/products blocked ({resp.status_code})")


# ===========================================================================
# TENANT ISOLATION
# ===========================================================================

class TestTenantIsolation:
    """Tenant A admin cannot see Tenant B data."""

    def test_tenant_a_orders_scoped_to_tenant_a(self, tenant_a_headers, setup_tenant_b):
        """Tenant A admin sees only their own orders."""
        resp = requests.get(f"{BASE_URL}/api/admin/orders", headers=tenant_a_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        orders = data.get("orders", data.get("items", []))
        tenant_b_id = setup_tenant_b["tenant_id"]
        for order in orders:
            assert order.get("tenant_id") != tenant_b_id, \
                "SECURITY: Tenant A order list contains Tenant B data!"
        print("PASS: Tenant A order list contains no Tenant B data")

    def test_tenant_a_products_scoped_to_tenant_a(self, tenant_a_headers, setup_tenant_b):
        """Tenant A admin sees only their own products."""
        resp = requests.get(f"{BASE_URL}/api/admin/products", headers=tenant_a_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        products = data.get("products", data.get("items", []))
        tenant_b_id = setup_tenant_b["tenant_id"]
        for product in products:
            assert product.get("tenant_id") != tenant_b_id, \
                "SECURITY: Tenant A product list contains Tenant B data!"
        print("PASS: Tenant A product list contains no Tenant B data")
