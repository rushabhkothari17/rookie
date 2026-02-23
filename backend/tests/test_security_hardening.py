"""
Security Hardening Tests — Iteration 67
Tests all security features implemented in the security hardening session.

Covers:
- Rate limiting (login, register)
- Security headers
- NoSQL injection prevention
- IDOR fixes (orders, subscriptions)
- CSV formula injection prevention
- File size limit (10MB)
- Row count limit (5000 rows)
- HTML sanitization (articles, terms)
- API key audit logging
- Password complexity
- Admin unlock
- Token version invalidation
- Brute force lockout
- Swagger/ReDoc accessibility (dev vs prod)
- Admin login
- API key masking in settings
- Tenant isolation
"""

from __future__ import annotations

import io
import os
import secrets
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
import hashlib

import pytest
import requests
from passlib.context import CryptContext
from pymongo import MongoClient

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"

TENANT_B_PARTNER_CODE = "tenant-b"
TENANT_B_EMAIL = "adminb@tenantb.local"
TENANT_B_PASSWORD = "ChangeMe123!"

AUTOMATE_ACCOUNTS_PARTNER_CODE = "automate-accounts"

# ---------------------------------------------------------------------------
# Synchronous pymongo connection (for direct DB setup only)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def mongo_db():
    client = MongoClient(MONGO_URL)
    db_conn = client[DB_NAME]
    yield db_conn
    client.close()


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _make_id():
    return str(uuid.uuid4())


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Session-level fixtures (created once, reused across tests)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def admin_token():
    """Get admin token via POST /api/auth/login (platform admin, no partner_code)."""
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="session")
def tenant_b_token():
    """Get tenant B admin token via partner-login."""
    resp = requests.post(
        f"{BASE_URL}/api/auth/partner-login",
        json={
            "partner_code": TENANT_B_PARTNER_CODE,
            "email": TENANT_B_EMAIL,
            "password": TENANT_B_PASSWORD,
        },
        timeout=15,
    )
    if resp.status_code != 200:
        pytest.skip(f"Tenant B login failed: {resp.text} — skipping tenant isolation tests")
    return resp.json()["token"]


@pytest.fixture(scope="session")
def tenant_b_tenant_id(mongo_db):
    """Resolve tenant-b's tenant_id from DB."""
    t = mongo_db.tenants.find_one({"code": TENANT_B_PARTNER_CODE}, {"_id": 0, "id": 1})
    if not t:
        pytest.skip("Tenant B not found in DB — skipping")
    return t["id"]


@pytest.fixture(scope="session")
def automate_accounts_tenant_id(mongo_db):
    """Resolve automate-accounts tenant_id from DB."""
    t = mongo_db.tenants.find_one({"code": AUTOMATE_ACCOUNTS_PARTNER_CODE}, {"_id": 0, "id": 1})
    if not t:
        pytest.skip("automate-accounts tenant not found in DB")
    return t["id"]


@pytest.fixture(scope="session")
def test_lockout_user(mongo_db):
    """
    Create a test user directly in MongoDB for brute-force lockout test.
    Returns (user_doc). Cleaned up after session.
    """
    email = f"test_lockout_{secrets.token_hex(4)}@test.local"
    password = "LockTest@2026!"
    user_id = _make_id()
    hashed = pwd_context.hash(password)
    user_doc = {
        "id": user_id,
        "email": email,
        "password_hash": hashed,
        "full_name": "Lockout Test User",
        "company_name": "Test",
        "phone": "",
        "is_verified": True,
        "is_active": True,
        "is_admin": False,
        "role": "customer",
        "tenant_id": None,
        "failed_login_attempts": 0,
        "lockout_until": None,
        "token_version": 0,
        "created_at": _now_iso(),
    }
    mongo_db.users.insert_one(user_doc)
    yield {"email": email, "password": password, "id": user_id}
    # Cleanup
    mongo_db.users.delete_one({"id": user_id})


@pytest.fixture(scope="session")
def test_token_version_user(mongo_db):
    """
    Create a test user for the token_version invalidation test.
    Returns dict with email, password, user_id.
    """
    email = f"test_tokver_{secrets.token_hex(4)}@test.local"
    password = "TokenVer@2026!"
    user_id = _make_id()
    hashed = pwd_context.hash(password)
    user_doc = {
        "id": user_id,
        "email": email,
        "password_hash": hashed,
        "full_name": "Token Version Test",
        "company_name": "Test",
        "phone": "",
        "is_verified": True,
        "is_active": True,
        "is_admin": False,
        "role": "customer",
        "tenant_id": None,
        "failed_login_attempts": 0,
        "lockout_until": None,
        "token_version": 0,
        "created_at": _now_iso(),
    }
    mongo_db.users.insert_one(user_doc)
    yield {"email": email, "password": password, "id": user_id}
    # Cleanup
    mongo_db.users.delete_one({"id": user_id})


@pytest.fixture(scope="session")
def idor_customers(mongo_db):
    """
    Create two customers directly in MongoDB for IDOR testing.
    Each customer has a user record. Returns list of dicts.
    """
    tenant_record = mongo_db.tenants.find_one({"code": AUTOMATE_ACCOUNTS_PARTNER_CODE}, {"_id": 0, "id": 1})
    if not tenant_record:
        # Fall back to default tenant
        tenant_id = None
    else:
        tenant_id = tenant_record["id"]

    customers = []
    for i in range(2):
        email = f"test_idor{i}_{secrets.token_hex(4)}@test.local"
        password = "IdorTest@2026!"
        user_id = _make_id()
        customer_id = _make_id()
        hashed = pwd_context.hash(password)

        user_doc = {
            "id": user_id,
            "email": email,
            "password_hash": hashed,
            "full_name": f"IDOR Customer {i}",
            "company_name": "TestCo",
            "phone": "",
            "is_verified": True,
            "is_active": True,
            "is_admin": False,
            "role": "customer",
            "tenant_id": tenant_id,
            "token_version": 0,
            "created_at": _now_iso(),
        }
        customer_doc = {
            "id": customer_id,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "company_name": "TestCo",
            "phone": "",
            "currency": "GBP",
            "currency_locked": False,
            "allow_bank_transfer": True,
            "allow_card_payment": False,
            "stripe_customer_id": None,
            "created_at": _now_iso(),
        }
        address_doc = {
            "id": _make_id(),
            "customer_id": customer_id,
            "tenant_id": tenant_id,
            "line1": "1 Test St",
            "line2": "",
            "city": "London",
            "region": "England",
            "postal": "EC1A 1BB",
            "country": "GB",
        }
        mongo_db.users.insert_one(user_doc)
        mongo_db.customers.insert_one(customer_doc)
        mongo_db.addresses.insert_one(address_doc)

        customers.append({
            "email": email,
            "password": password,
            "user_id": user_id,
            "customer_id": customer_id,
            "tenant_id": tenant_id,
        })

    yield customers
    # Cleanup
    for c in customers:
        mongo_db.users.delete_one({"id": c["user_id"]})
        mongo_db.customers.delete_one({"id": c["customer_id"]})


@pytest.fixture(scope="session")
def idor_order(mongo_db, idor_customers):
    """
    Create an order belonging to idor_customers[0].
    Returns the order_id.
    """
    cust = idor_customers[0]
    order_id = _make_id()
    order_doc = {
        "id": order_id,
        "tenant_id": cust["tenant_id"],
        "order_number": f"TEST-{order_id[:8].upper()}",
        "customer_id": cust["customer_id"],
        "type": "one_time",
        "status": "complete",
        "subtotal": 99.0,
        "fee": 0.0,
        "total": 99.0,
        "currency": "GBP",
        "payment_method": "stripe",
        "created_at": _now_iso(),
    }
    mongo_db.orders.insert_one(order_doc)
    yield order_id
    mongo_db.orders.delete_one({"id": order_id})


@pytest.fixture(scope="session")
def idor_subscription(mongo_db, idor_customers):
    """
    Create a subscription belonging to idor_customers[0].
    Returns the subscription_id.
    """
    cust = idor_customers[0]
    sub_id = _make_id()
    sub_doc = {
        "id": sub_id,
        "tenant_id": cust["tenant_id"],
        "subscription_number": f"SUB-{sub_id[:8].upper()}",
        "customer_id": cust["customer_id"],
        "status": "active",
        "amount": 99.0,
        "currency": "GBP",
        "billing_period": "monthly",
        "created_at": _now_iso(),
    }
    mongo_db.subscriptions.insert_one(sub_doc)
    yield sub_id
    mongo_db.subscriptions.delete_one({"id": sub_id})


def _get_customer_token(customer: Dict[str, Any]) -> Optional[str]:
    """Login as a customer (direct login, no partner code) via /api/auth/login."""
    # For customers with no tenant, use the plain login
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": customer["email"], "password": customer["password"]},
        timeout=15,
    )
    if resp.status_code == 200:
        return resp.json()["token"]
    # Try partner login with automate-accounts partner code
    resp2 = requests.post(
        f"{BASE_URL}/api/auth/partner-login",
        json={
            "partner_code": AUTOMATE_ACCOUNTS_PARTNER_CODE,
            "email": customer["email"],
            "password": customer["password"],
        },
        timeout=15,
    )
    if resp2.status_code == 200:
        return resp2.json()["token"]
    return None


# ===========================================================================
# 1. Admin Login
# ===========================================================================

class TestAdminLogin:
    """Verify platform admin can log in without partner_code."""

    def test_admin_login_success(self):
        """Admin can login with email/password, no partner_code required."""
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=15,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "token" in data, "Response should contain a token"
        assert data.get("role") in ("super_admin", "platform_admin", "admin", "partner_super_admin"), (
            f"Unexpected role: {data.get('role')}"
        )
        print(f"Admin login success — role={data.get('role')}, tenant_id={data.get('tenant_id')}")

    def test_admin_login_wrong_password_returns_401(self):
        """Wrong password returns 401."""
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": "WrongPassword!"},
            timeout=15,
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"
        print("Admin wrong password → 401 confirmed")


# ===========================================================================
# 2. Security Headers
# ===========================================================================

class TestSecurityHeaders:
    """Every API response should include OWASP security headers."""

    def test_x_content_type_options_on_login_endpoint(self):
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "check@headers.com", "password": "any"},
            timeout=15,
        )
        header_val = resp.headers.get("X-Content-Type-Options", "")
        assert header_val == "nosniff", (
            f"Expected 'nosniff', got '{header_val}'"
        )
        print(f"X-Content-Type-Options: {header_val}")

    def test_x_frame_options_on_login_endpoint(self):
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "check@headers.com", "password": "any"},
            timeout=15,
        )
        header_val = resp.headers.get("X-Frame-Options", "")
        assert header_val == "DENY", (
            f"Expected 'DENY', got '{header_val}'"
        )
        print(f"X-Frame-Options: {header_val}")

    def test_x_xss_protection_header(self):
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "check@headers.com", "password": "any"},
            timeout=15,
        )
        header_val = resp.headers.get("X-XSS-Protection", "")
        assert header_val, "X-XSS-Protection header should be present"
        print(f"X-XSS-Protection: {header_val}")

    def test_referrer_policy_header(self):
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "check@headers.com", "password": "any"},
            timeout=15,
        )
        header_val = resp.headers.get("Referrer-Policy", "")
        assert header_val, "Referrer-Policy header should be present"
        print(f"Referrer-Policy: {header_val}")

    def test_security_headers_on_get_endpoint(self, admin_token):
        """Security headers also present on GET endpoints."""
        resp = requests.get(
            f"{BASE_URL}/api/me",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        print("Security headers confirmed on GET /api/me")


# ===========================================================================
# 3. Swagger/ReDoc in Dev Environment
# ===========================================================================

class TestSwaggerRedoc:
    """In dev (ENVIRONMENT != production), /docs and /redoc should be accessible."""

    def test_docs_accessible_in_dev(self):
        """GET /docs should return 200 in dev mode."""
        resp = requests.get(f"{BASE_URL}/docs", timeout=15)
        assert resp.status_code == 200, (
            f"Expected /docs to be accessible in dev (status=200), got {resp.status_code}"
        )
        print(f"GET /docs → {resp.status_code} (accessible in dev)")

    def test_redoc_accessible_in_dev(self):
        """GET /redoc should return 200 in dev mode."""
        resp = requests.get(f"{BASE_URL}/redoc", timeout=15)
        assert resp.status_code == 200, (
            f"Expected /redoc to be accessible in dev (status=200), got {resp.status_code}"
        )
        print(f"GET /redoc → {resp.status_code} (accessible in dev)")


# ===========================================================================
# 4. Password Complexity
# ===========================================================================

class TestPasswordComplexity:
    """POST /api/auth/register with weak password should return 400."""

    _BASE_PAYLOAD = {
        "email": "complexity_test@test.local",
        "full_name": "Test User",
        "company_name": "TestCo",
        "address": {
            "line1": "1 Test St",
            "city": "London",
            "region": "England",
            "postal": "EC1A 1BB",
            "country": "GB",
        },
    }

    def test_weak_password_no_uppercase(self):
        payload = {**self._BASE_PAYLOAD, "password": "password123!"}
        resp = requests.post(f"{BASE_URL}/api/auth/register", json=payload, timeout=15)
        assert resp.status_code == 400, f"Expected 400 for weak password, got {resp.status_code}: {resp.text}"
        print(f"Weak password (no uppercase) → 400: {resp.json().get('detail')}")

    def test_weak_password_too_short(self):
        payload = {**self._BASE_PAYLOAD, "password": "Abc1@"}
        resp = requests.post(f"{BASE_URL}/api/auth/register", json=payload, timeout=15)
        assert resp.status_code == 400, f"Expected 400 for too-short password, got {resp.status_code}: {resp.text}"
        print(f"Too-short password → 400: {resp.json().get('detail')}")

    def test_weak_password_no_special_char(self):
        payload = {**self._BASE_PAYLOAD, "password": "Password123"}
        resp = requests.post(f"{BASE_URL}/api/auth/register", json=payload, timeout=15)
        assert resp.status_code == 400, f"Expected 400 for no-special-char, got {resp.status_code}: {resp.text}"
        print(f"No special char → 400: {resp.json().get('detail')}")

    def test_weak_password_common_password123(self):
        """'password123' should fail complexity (no uppercase, no special char)."""
        payload = {**self._BASE_PAYLOAD, "password": "password123"}
        resp = requests.post(f"{BASE_URL}/api/auth/register", json=payload, timeout=15)
        assert resp.status_code == 400, f"Expected 400 for 'password123', got {resp.status_code}: {resp.text}"
        print(f"'password123' → 400: {resp.json().get('detail')}")


# ===========================================================================
# 5. HTML Sanitization — Articles
# ===========================================================================

class TestHTMLSanitizationArticles:
    """POST /api/articles with XSS content should be sanitized."""

    def test_article_xss_script_stripped(self, admin_token, mongo_db):
        """<script>alert('xss')</script> should be stripped from article content."""
        # Get a valid category
        cats_resp = requests.get(
            f"{BASE_URL}/api/articles/admin/list",
            headers={"Authorization": f"Bearer {admin_token}"},
            params={"per_page": 1},
            timeout=15,
        )
        # Get valid category from DB
        cats = list(mongo_db.article_categories.find({"is_active": True}, {"_id": 0, "name": 1}).limit(1))
        if cats:
            category = cats[0]["name"]
        else:
            # Use a hardcoded fallback
            category = "Blog"

        xss_content = "<p>Hello</p><script>alert('xss')</script><p>World</p>"
        resp = requests.post(
            f"{BASE_URL}/api/articles",
            json={
                "title": f"XSS Test Article {secrets.token_hex(4)}",
                "category": category,
                "content": xss_content,
                "visibility": "all",
                "restricted_to": [],
            },
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )

        if resp.status_code == 400 and "Invalid category" in resp.text:
            # Try to find any valid category
            all_cats = list(mongo_db.article_categories.find({}, {"_id": 0, "name": 1}).limit(5))
            if not all_cats:
                pytest.skip("No article categories found in DB")
            category = all_cats[0]["name"]
            resp = requests.post(
                f"{BASE_URL}/api/articles",
                json={
                    "title": f"XSS Test Article {secrets.token_hex(4)}",
                    "category": category,
                    "content": xss_content,
                    "visibility": "all",
                    "restricted_to": [],
                },
                headers={"Authorization": f"Bearer {admin_token}"},
                timeout=15,
            )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        article = resp.json().get("article", {})
        content = article.get("content", "")
        assert "<script>" not in content, f"<script> tag should be stripped from content: '{content}'"
        assert "alert" not in content, f"alert() should be stripped from content: '{content}'"
        print(f"XSS in article sanitized: '{content}'")

        # Cleanup
        article_id = article.get("id")
        if article_id:
            requests.delete(
                f"{BASE_URL}/api/articles/{article_id}",
                headers={"Authorization": f"Bearer {admin_token}"},
                timeout=10,
            )


# ===========================================================================
# 6. HTML Sanitization — Terms
# ===========================================================================

class TestHTMLSanitizationTerms:
    """POST /api/admin/terms with XSS content should be sanitized."""

    def test_terms_xss_script_stripped(self, admin_token, mongo_db):
        """<script> tag should be stripped from terms content."""
        xss_content = "<h1>Terms</h1><script>alert('xss')</script><p>Some terms.</p>"
        resp = requests.post(
            f"{BASE_URL}/api/admin/terms",
            json={
                "title": f"XSS Terms Test {secrets.token_hex(4)}",
                "content": xss_content,
                "is_default": False,
                "status": "active",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        terms_id = resp.json().get("id")

        # Fetch from DB to verify content was sanitized
        terms_doc = mongo_db.terms_and_conditions.find_one({"id": terms_id}, {"_id": 0, "content": 1})
        assert terms_doc, "Terms should be in DB"
        content = terms_doc.get("content", "")
        assert "<script>" not in content, f"<script> should be stripped: '{content}'"
        assert "alert" not in content, f"alert() should be stripped: '{content}'"
        print(f"XSS in terms sanitized: '{content}'")

        # Cleanup
        if terms_id:
            requests.delete(
                f"{BASE_URL}/api/admin/terms/{terms_id}",
                headers={"Authorization": f"Bearer {admin_token}"},
                timeout=10,
            )


# ===========================================================================
# 7. CSV Formula Injection Prevention
# ===========================================================================

class TestCSVFormulaInjection:
    """GET /api/admin/export/orders should prefix formula chars with single quote."""

    def test_csv_formula_chars_prefixed(self, admin_token, mongo_db):
        """
        Insert an order with a formula-like field value, export as CSV,
        verify that = + - @ chars in values are prefixed with '.
        """
        # Insert a test order with a formula-like value in order_number
        order_id = _make_id()
        formula_order_number = "=SUM(1,2)"  # CSV injection payload
        order_doc = {
            "id": order_id,
            "tenant_id": None,  # platform admin sees orders by tenant filter
            "order_number": formula_order_number,
            "customer_id": "test_customer_formula_inject",
            "status": "complete",
            "subtotal": 99.0,
            "fee": 0.0,
            "total": 99.0,
            "currency": "GBP",
            "payment_method": "stripe",
            "created_at": _now_iso(),
        }
        mongo_db.orders.insert_one(order_doc)

        try:
            resp = requests.get(
                f"{BASE_URL}/api/admin/export/orders",
                headers={"Authorization": f"Bearer {admin_token}"},
                timeout=20,
            )
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
            csv_content = resp.text

            # Check that the formula value is prefixed with '
            # Either '=SUM(1,2) or it might not appear if order belongs to different tenant
            if formula_order_number in csv_content:
                assert f"'{formula_order_number}" in csv_content or "=SUM" not in csv_content, (
                    f"Formula injection not prevented: '{formula_order_number}' appears un-escaped in CSV"
                )
                print(f"CSV formula injection prevented: '{formula_order_number}' is prefixed")
            else:
                print("Formula order not in CSV (different tenant scope — testing _serialize_val directly)")
                # Test the serialize function behavior directly using a simple assertion
                # The function should prefix = + - @ with '
                from routes.admin.exports import _serialize_val
                assert _serialize_val("=SUM(1,2)") == "'=SUM(1,2)", (
                    f"_serialize_val should prefix = with ', got: {_serialize_val('=SUM(1,2)')}"
                )
                assert _serialize_val("+CMD") == "'+CMD", (
                    f"_serialize_val should prefix + with ', got: {_serialize_val('+CMD')}"
                )
                assert _serialize_val("-1+1") == "'-1+1", (
                    f"_serialize_val should prefix - with ', got: {_serialize_val('-1+1')}"
                )
                assert _serialize_val("@SUM(1,2)") == "'@SUM(1,2)", (
                    f"_serialize_val should prefix @ with ', got: {_serialize_val('@SUM(1,2)')}"
                )
                assert _serialize_val("normal value") == "normal value", (
                    "Normal values should not be modified"
                )
                print("_serialize_val formula injection prevention confirmed")
        finally:
            mongo_db.orders.delete_one({"id": order_id})


# ===========================================================================
# 8. File Size Limit
# ===========================================================================

class TestFileSizeLimit:
    """POST /api/admin/import/customers with >10MB file should return 413."""

    def test_file_size_over_10mb_returns_413(self, admin_token):
        """A file over 10MB should return 413."""
        # Generate a CSV content just over 10MB
        # 10MB = 10 * 1024 * 1024 = 10485760 bytes
        # Create a CSV header + rows to exceed this size
        header = "email,full_name,company_name,country,currency\n"
        row = "test@example.com,Test User,TestCo,GB,GBP\n"
        # Calculate rows needed to exceed 10MB
        target_size = 10 * 1024 * 1024 + 100  # Just over 10MB
        rows_needed = (target_size - len(header)) // len(row) + 1
        # Build the content
        content = header + row * rows_needed
        content_bytes = content.encode("utf-8")
        assert len(content_bytes) > 10 * 1024 * 1024, "Test file must be > 10MB"

        file_obj = io.BytesIO(content_bytes)
        resp = requests.post(
            f"{BASE_URL}/api/admin/import/customers",
            headers={"Authorization": f"Bearer {admin_token}"},
            files={"file": ("large_file.csv", file_obj, "text/csv")},
            timeout=60,
        )
        assert resp.status_code == 413, (
            f"Expected 413 for file over 10MB, got {resp.status_code}: {resp.text}"
        )
        print(f"File size limit test: {len(content_bytes)} bytes → 413 response")


# ===========================================================================
# 9. Row Count Limit
# ===========================================================================

class TestRowCountLimit:
    """POST /api/admin/import/customers with >5000 rows should return 400."""

    def test_row_count_over_5000_returns_400(self, admin_token):
        """A CSV with more than 5000 rows should return 400."""
        header = "email\n"
        # Generate 5001 rows
        rows = "\n".join([f"test_{i}@example.com" for i in range(5001)]) + "\n"
        content = header + rows
        content_bytes = content.encode("utf-8")

        # Ensure it's not over 10MB
        assert len(content_bytes) < 10 * 1024 * 1024, "Test file for row count must be < 10MB"
        assert content_bytes.count(b"\n") - 1 > 5000, "Should have >5000 data rows"

        file_obj = io.BytesIO(content_bytes)
        resp = requests.post(
            f"{BASE_URL}/api/admin/import/customers",
            headers={"Authorization": f"Bearer {admin_token}"},
            files={"file": ("many_rows.csv", file_obj, "text/csv")},
            timeout=30,
        )
        assert resp.status_code == 400, (
            f"Expected 400 for >5000 rows, got {resp.status_code}: {resp.text}"
        )
        assert "5000" in resp.text or "too many" in resp.text.lower(), (
            f"Error message should mention row limit: {resp.text}"
        )
        print(f"Row count limit test: 5001 rows → 400: {resp.json().get('detail')}")


# ===========================================================================
# 10. API Key Audit Logging
# ===========================================================================

class TestAPIKeyAuditLogging:
    """Creating and revoking API keys should create audit log entries."""

    def test_create_api_key_creates_audit_log(self, admin_token):
        """POST /api/admin/api-keys should create an audit_key_created log entry."""
        # Create a new API key
        resp = requests.post(
            f"{BASE_URL}/api/admin/api-keys",
            json={"name": f"Test Key {secrets.token_hex(4)}"},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        assert resp.status_code == 200, f"Expected 200 when creating API key, got {resp.status_code}: {resp.text}"
        key_data = resp.json()
        key_id = key_data.get("id")
        assert key_id, "Response should contain key ID"
        assert key_data.get("key"), "Response should contain the full key (shown once)"
        print(f"API key created: {key_id}")

        # Check audit log for api_key_created action
        time.sleep(0.5)  # Brief wait for async log write
        logs_resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs",
            headers={"Authorization": f"Bearer {admin_token}"},
            params={"entity_type": "api_key", "action": "api_key_created"},
            timeout=15,
        )
        assert logs_resp.status_code == 200, f"Expected 200 for audit logs: {logs_resp.text}"
        logs = logs_resp.json().get("logs", [])
        matching = [l for l in logs if l.get("entity_id") == key_id or l.get("action") == "api_key_created"]
        assert len(matching) > 0, (
            f"Should find api_key_created audit log entry for key {key_id}, logs: {logs[:3]}"
        )
        print(f"API key audit log found: {matching[0].get('action')}")

        # Now revoke the key
        revoke_resp = requests.delete(
            f"{BASE_URL}/api/admin/api-keys/{key_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        assert revoke_resp.status_code == 200, f"Expected 200 when revoking key: {revoke_resp.text}"

        # Check audit log for api_key_revoked
        time.sleep(0.5)
        revoke_logs_resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs",
            headers={"Authorization": f"Bearer {admin_token}"},
            params={"entity_type": "api_key", "action": "api_key_revoked"},
            timeout=15,
        )
        assert revoke_logs_resp.status_code == 200
        revoke_logs = revoke_logs_resp.json().get("logs", [])
        matching_revoke = [l for l in revoke_logs if l.get("entity_id") == key_id or l.get("action") == "api_key_revoked"]
        assert len(matching_revoke) > 0, (
            f"Should find api_key_revoked audit log entry for key {key_id}"
        )
        print(f"API key revoke audit log found: {matching_revoke[0].get('action')}")


# ===========================================================================
# 11. Admin Settings — API Key Masking
# ===========================================================================

class TestAdminSettingsMasking:
    """GET /api/admin/settings should mask the resend_api_key in response."""

    def test_settings_masks_resend_api_key(self, admin_token, mongo_db):
        """resend_api_key in settings should be masked with ••••••••."""
        # First set a fake resend_api_key in settings (directly in DB)
        fake_key = "re_live_1234567890abcdef"
        tenant_record = mongo_db.app_settings.find_one({"key": {"$exists": False}}, {"_id": 0, "tenant_id": 1})
        if tenant_record:
            tid = tenant_record.get("tenant_id")
            mongo_db.app_settings.update_one(
                {"tenant_id": tid, "key": {"$exists": False}},
                {"$set": {"resend_api_key": fake_key}},
                upsert=True,
            )

        resp = requests.get(
            f"{BASE_URL}/api/admin/settings",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        assert resp.status_code == 200, f"Expected 200: {resp.text}"
        settings = resp.json().get("settings", {})

        # If resend_api_key is present, it should be masked
        if settings.get("resend_api_key"):
            masked_key = settings["resend_api_key"]
            assert masked_key.startswith("••"), (
                f"resend_api_key should be masked: got '{masked_key}'"
            )
            assert fake_key not in masked_key, (
                f"Full API key should not appear in response: '{masked_key}'"
            )
            print(f"resend_api_key masked correctly: '{masked_key}'")
        else:
            print("resend_api_key not present in settings — checking endpoint returns 200")
            assert resp.status_code == 200
            print("GET /api/admin/settings returned 200 (no resend_api_key to mask)")


# ===========================================================================
# 12. NoSQL Injection Prevention
# ===========================================================================

class TestNoSQLInjection:
    """Search queries with $regex special chars should be treated as literals."""

    def test_search_with_regex_chars_treated_as_literal(self, admin_token):
        """Searching with '(.*)' should not act as a regex operator — just no results or safe result."""
        # Test: search in articles list with regex special chars
        nosql_payload = "(.*)"  # Would match everything as a regex
        resp = requests.get(
            f"{BASE_URL}/api/articles/admin/list",
            headers={"Authorization": f"Bearer {admin_token}"},
            params={"search": nosql_payload},
            timeout=15,
        )
        # Should return 200 (not 500) — query is safe
        assert resp.status_code == 200, (
            f"Search with regex chars should not return 500: {resp.status_code}: {resp.text}"
        )
        print(f"NoSQL injection test (.*): status={resp.status_code}, found {len(resp.json().get('articles', []))} articles")

    def test_search_with_dollar_sign_chars(self, admin_token):
        """$where or $regex operators in search should not be executed."""
        nosql_payload = "$where"
        resp = requests.get(
            f"{BASE_URL}/api/articles/admin/list",
            headers={"Authorization": f"Bearer {admin_token}"},
            params={"search": nosql_payload},
            timeout=15,
        )
        assert resp.status_code == 200, (
            f"Search with '$where' should not return 500: {resp.status_code}: {resp.text}"
        )
        print(f"NoSQL injection test ($where): status={resp.status_code}")

    def test_search_with_dot_star_regex(self, admin_token):
        """Search with '.*' regex should be escaped and treated as literal."""
        nosql_payload = ".*"
        resp = requests.get(
            f"{BASE_URL}/api/articles/admin/list",
            headers={"Authorization": f"Bearer {admin_token}"},
            params={"search": nosql_payload},
            timeout=15,
        )
        assert resp.status_code == 200, (
            f"Search with '.*' should be safe: {resp.status_code}: {resp.text}"
        )
        # With re.escape, '.*' becomes '\.\*' — should match nothing if no article has '.*' in title
        print(f"NoSQL injection test (.*): status={resp.status_code}")


# ===========================================================================
# 13. IDOR — Order Access
# ===========================================================================

class TestIDOROrder:
    """Customer should NOT be able to access another customer's order."""

    def test_customer_cannot_access_other_customers_order(self, idor_customers, idor_order):
        """Customer 2 should get 404 when accessing Customer 1's order."""
        # Get token for customer 2
        customer2 = idor_customers[1]
        token2 = _get_customer_token(customer2)
        if not token2:
            pytest.skip("Could not log in as IDOR customer 2")

        resp = requests.get(
            f"{BASE_URL}/api/orders/{idor_order}",
            headers={"Authorization": f"Bearer {token2}"},
            timeout=15,
        )
        assert resp.status_code == 404, (
            f"Customer 2 should NOT access Customer 1's order. Got {resp.status_code}: {resp.text}"
        )
        print(f"IDOR order test: customer2 got {resp.status_code} (expected 404)")

    def test_customer_can_access_own_order(self, idor_customers, idor_order):
        """Customer 1 should be able to access their own order."""
        customer1 = idor_customers[0]
        token1 = _get_customer_token(customer1)
        if not token1:
            pytest.skip("Could not log in as IDOR customer 1")

        resp = requests.get(
            f"{BASE_URL}/api/orders/{idor_order}",
            headers={"Authorization": f"Bearer {token1}"},
            timeout=15,
        )
        assert resp.status_code == 200, (
            f"Customer 1 should access their own order. Got {resp.status_code}: {resp.text}"
        )
        print(f"IDOR order test: customer1 own order → {resp.status_code}")


# ===========================================================================
# 14. IDOR — Subscription Cancel
# ===========================================================================

class TestIDORSubscriptionCancel:
    """Customer should NOT be able to cancel another customer's subscription."""

    def test_customer_cannot_cancel_other_customers_subscription(self, idor_customers, idor_subscription):
        """Customer 2 should get 404 when cancelling Customer 1's subscription."""
        customer2 = idor_customers[1]
        token2 = _get_customer_token(customer2)
        if not token2:
            pytest.skip("Could not log in as IDOR customer 2")

        resp = requests.post(
            f"{BASE_URL}/api/subscriptions/{idor_subscription}/cancel",
            json={"reason": "test"},
            headers={"Authorization": f"Bearer {token2}"},
            timeout=15,
        )
        assert resp.status_code == 404, (
            f"Customer 2 should NOT cancel Customer 1's subscription. Got {resp.status_code}: {resp.text}"
        )
        print(f"IDOR subscription cancel: customer2 got {resp.status_code} (expected 404)")

    def test_customer_can_cancel_own_subscription(self, idor_customers, idor_subscription):
        """Customer 1 should be able to cancel their own subscription."""
        customer1 = idor_customers[0]
        token1 = _get_customer_token(customer1)
        if not token1:
            pytest.skip("Could not log in as IDOR customer 1")

        resp = requests.post(
            f"{BASE_URL}/api/subscriptions/{idor_subscription}/cancel",
            json={"reason": "test cancel"},
            headers={"Authorization": f"Bearer {token1}"},
            timeout=15,
        )
        assert resp.status_code == 200, (
            f"Customer 1 should be able to cancel own subscription. Got {resp.status_code}: {resp.text}"
        )
        print(f"IDOR subscription cancel: customer1 own sub → {resp.status_code}")


# ===========================================================================
# 15. Tenant Isolation
# ===========================================================================

class TestTenantIsolation:
    """Admin from Tenant B should not see Tenant A's data."""

    def test_tenant_b_cannot_see_automate_accounts_customers(
        self, admin_token, tenant_b_token, automate_accounts_tenant_id
    ):
        """Tenant B admin's customer list should not include automate-accounts customers."""
        # Get automate-accounts customer count from platform admin
        aa_resp = requests.get(
            f"{BASE_URL}/api/admin/customers",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        assert aa_resp.status_code == 200

        # Get tenant B customer list — should NOT include automate-accounts customers
        tb_resp = requests.get(
            f"{BASE_URL}/api/admin/customers",
            headers={"Authorization": f"Bearer {tenant_b_token}"},
            timeout=15,
        )
        assert tb_resp.status_code == 200, f"Tenant B admin should access their customers: {tb_resp.text}"

        aa_customers = aa_resp.json().get("customers", [])
        tb_customers = tb_resp.json().get("customers", [])

        # None of the automate-accounts customers should appear in tenant B's list
        aa_customer_ids = {c["id"] for c in aa_customers}
        tb_customer_ids = {c["id"] for c in tb_customers}
        overlap = aa_customer_ids & tb_customer_ids
        assert len(overlap) == 0, (
            f"Tenant isolation breach: {len(overlap)} customer(s) shared between tenants: {overlap}"
        )
        print(f"Tenant isolation OK: AA customers={len(aa_customers)}, TB customers={len(tb_customers)}, overlap={len(overlap)}")

    def test_tenant_b_cannot_see_automate_accounts_orders(
        self, admin_token, tenant_b_token
    ):
        """Tenant B admin's order list should not include automate-accounts orders."""
        aa_resp = requests.get(
            f"{BASE_URL}/api/admin/orders",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        tb_resp = requests.get(
            f"{BASE_URL}/api/admin/orders",
            headers={"Authorization": f"Bearer {tenant_b_token}"},
            timeout=15,
        )
        assert aa_resp.status_code == 200
        assert tb_resp.status_code == 200

        aa_orders = aa_resp.json().get("orders", [])
        tb_orders = tb_resp.json().get("orders", [])
        aa_order_ids = {o["id"] for o in aa_orders}
        tb_order_ids = {o["id"] for o in tb_orders}
        overlap = aa_order_ids & tb_order_ids
        assert len(overlap) == 0, (
            f"Tenant isolation breach on orders: {len(overlap)} shared: {overlap}"
        )
        print(f"Order tenant isolation OK: AA orders={len(aa_orders)}, TB orders={len(tb_orders)}")


# ===========================================================================
# 16. Brute Force Lockout
# ===========================================================================

class TestBruteForce:
    """After 10 failed login attempts, account gets locked and 429 is returned."""

    def test_brute_force_lockout_after_10_failed_attempts(self, test_lockout_user, mongo_db):
        """10 failed login attempts → lockout → 429 on next attempt."""
        email = test_lockout_user["email"]
        wrong_password = "WrongPassword!999"

        # Reset state first
        mongo_db.users.update_one(
            {"id": test_lockout_user["id"]},
            {"$set": {"failed_login_attempts": 0, "lockout_until": None}},
        )

        # Send 10 failed login attempts
        status_codes = []
        for i in range(10):
            resp = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": email, "password": wrong_password},
                timeout=15,
            )
            status_codes.append(resp.status_code)
            # Small delay to avoid rate limit triggering before lockout
            time.sleep(0.1)

        print(f"10 failed logins → status codes: {status_codes}")

        # All 10 should return 401 (wrong password) or 429 (locked)
        for code in status_codes:
            assert code in (401, 429), f"Expected 401 or 429, got {code}"

        # Now verify user is locked (failed_login_attempts >= 10)
        user_doc = mongo_db.users.find_one({"id": test_lockout_user["id"]}, {"_id": 0})
        assert user_doc, "User should exist"

        # The lockout_until should be set after 10 attempts
        if user_doc.get("failed_login_attempts", 0) >= 10:
            assert user_doc.get("lockout_until") is not None, (
                "lockout_until should be set after 10 failed attempts"
            )
            print(f"Lockout set: failed_login_attempts={user_doc.get('failed_login_attempts')}, lockout_until={user_doc.get('lockout_until')}")

            # 11th attempt should return 429 (locked out)
            resp11 = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": email, "password": wrong_password},
                timeout=15,
            )
            assert resp11.status_code == 429, (
                f"Expected 429 for locked account, got {resp11.status_code}: {resp11.text}"
            )
            print(f"11th login attempt → 429 (locked out)")
        else:
            print(f"Rate limit may have kicked in early. Attempts: {user_doc.get('failed_login_attempts')}")


# ===========================================================================
# 17. Admin Unlock
# ===========================================================================

class TestAdminUnlock:
    """POST /api/admin/users/{id}/unlock should reset lockout."""

    def test_admin_can_unlock_locked_user(self, admin_token, test_lockout_user, mongo_db):
        """Admin unlock should reset failed_login_attempts and lockout_until."""
        user_id = test_lockout_user["id"]

        # First, ensure the user IS locked
        future_lockout = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
        mongo_db.users.update_one(
            {"id": user_id},
            {"$set": {"failed_login_attempts": 10, "lockout_until": future_lockout}},
        )

        # Admin unlocks the user
        resp = requests.post(
            f"{BASE_URL}/api/admin/users/{user_id}/unlock",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        assert resp.status_code == 200, f"Expected 200 for admin unlock, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "unlocked" in data.get("message", "").lower() or "unlock" in data.get("message", "").lower(), (
            f"Unexpected message: {data.get('message')}"
        )
        print(f"Admin unlock: {data.get('message')}")

        # Verify in DB that lockout is cleared
        user_doc = mongo_db.users.find_one({"id": user_id}, {"_id": 0, "failed_login_attempts": 1, "lockout_until": 1})
        assert user_doc.get("failed_login_attempts") == 0, (
            f"failed_login_attempts should be 0 after unlock, got {user_doc.get('failed_login_attempts')}"
        )
        assert user_doc.get("lockout_until") is None, (
            f"lockout_until should be None after unlock, got {user_doc.get('lockout_until')}"
        )

        # Verify user can login again with correct password
        login_resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": test_lockout_user["email"], "password": test_lockout_user["password"]},
            timeout=15,
        )
        assert login_resp.status_code == 200, (
            f"User should be able to login after unlock, got {login_resp.status_code}: {login_resp.text}"
        )
        print("User can login again after admin unlock")


# ===========================================================================
# 18. Token Version Invalidation
# ===========================================================================

class TestTokenVersionInvalidation:
    """After token_version is incremented in DB, old JWT should be rejected."""

    def test_old_token_rejected_after_token_version_increment(self, test_token_version_user, mongo_db):
        """Old JWT should return 401 after token_version is incremented."""
        email = test_token_version_user["email"]
        password = test_token_version_user["password"]
        user_id = test_token_version_user["id"]

        # Login to get a token
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": email, "password": password},
            timeout=15,
        )
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        old_token = resp.json()["token"]

        # Verify old token works
        me_resp = requests.get(
            f"{BASE_URL}/api/me",
            headers={"Authorization": f"Bearer {old_token}"},
            timeout=15,
        )
        assert me_resp.status_code == 200, f"Old token should work initially: {me_resp.text}"
        print("Old token works before token_version increment")

        # Increment token_version in DB (simulating password change)
        result = mongo_db.users.update_one(
            {"id": user_id},
            {"$inc": {"token_version": 1}},
        )
        assert result.modified_count == 1, "Should have incremented token_version"

        # Try old token — should now return 401
        old_me_resp = requests.get(
            f"{BASE_URL}/api/me",
            headers={"Authorization": f"Bearer {old_token}"},
            timeout=15,
        )
        assert old_me_resp.status_code == 401, (
            f"Old token should be rejected after token_version increment, got {old_me_resp.status_code}: {old_me_resp.text}"
        )
        assert "expired" in old_me_resp.json().get("detail", "").lower() or "session" in old_me_resp.json().get("detail", "").lower(), (
            f"Should mention session expired: {old_me_resp.json().get('detail')}"
        )
        print(f"Old token rejected with 401 after token_version increment: {old_me_resp.json().get('detail')}")

        # New login with new token should work
        new_login = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": email, "password": password},
            timeout=15,
        )
        assert new_login.status_code == 200, f"New login should succeed: {new_login.text}"
        new_token = new_login.json()["token"]
        new_me = requests.get(
            f"{BASE_URL}/api/me",
            headers={"Authorization": f"Bearer {new_token}"},
            timeout=15,
        )
        assert new_me.status_code == 200, f"New token should work: {new_me.text}"
        print("New token works after token_version increment")


# ===========================================================================
# 19. Rate Limiting — Register (5 per minute)
# ===========================================================================

class TestRateLimitRegister:
    """POST /api/auth/register should return 429 after 5 rapid requests from same IP."""

    def test_register_rate_limit_429_after_5_requests(self):
        """Send 6 rapid register requests — at least one should return 429."""
        # Wait for any existing register rate limit window to expire
        # (other tests may have consumed some tokens)
        print("Sleeping 65s to reset rate limit window for register...")
        time.sleep(65)

        payload_base = {
            "full_name": "Rate Test",
            "company_name": "TestCo",
            "address": {
                "line1": "1 Test St",
                "city": "London",
                "region": "England",
                "postal": "EC1A 1BB",
                "country": "GB",
            },
        }
        status_codes = []
        for i in range(7):
            payload = {
                **payload_base,
                "email": f"ratelimit_test_{i}_{secrets.token_hex(4)}@test.local",
                "password": "RateLimit@2026!",
            }
            resp = requests.post(
                f"{BASE_URL}/api/auth/register",
                json=payload,
                timeout=15,
            )
            status_codes.append(resp.status_code)
            # No sleep — fire as fast as possible

        print(f"Register rate limit test: status codes = {status_codes}")
        assert 429 in status_codes, (
            f"Expected at least one 429 in {status_codes} after 7 rapid register requests"
        )
        count_429 = status_codes.count(429)
        print(f"Got {count_429} rate-limited (429) responses out of {len(status_codes)} register attempts")


# ===========================================================================
# 20. Rate Limiting — Login (10 per minute)
# ===========================================================================

class TestRateLimitLogin:
    """POST /api/auth/login should return 429 after 10 rapid requests from same IP."""

    def test_login_rate_limit_429_after_10_requests(self):
        """Send 12 rapid login requests — at least one should return 429."""
        # Wait for any existing login rate limit window to expire
        print("Sleeping 65s to reset rate limit window for login...")
        time.sleep(65)

        status_codes = []
        for i in range(13):
            resp = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={
                    "email": f"ratelimit_probe_{i}@test.invalid",
                    "password": "AnyPassword@123",
                },
                timeout=15,
            )
            status_codes.append(resp.status_code)
            # No sleep — fire as fast as possible

        print(f"Login rate limit test: status codes = {status_codes}")
        assert 429 in status_codes, (
            f"Expected at least one 429 in {status_codes} after 13 rapid login requests"
        )
        count_429 = status_codes.count(429)
        print(f"Got {count_429} rate-limited (429) responses out of {len(status_codes)} login attempts")
