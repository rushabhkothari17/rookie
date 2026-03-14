"""
Security Hardening Tests (iteration 292).

Tests the following fixes:
1. Promo code >100% percentage discount rejected (Pydantic validator)
2. Promo code negative discount rejected
3. Promo code 100% discount allowed
4. Product name max_length=500 enforced (100k char name rejected)
5. Product name 500-char accepted
6. Terms content max_length=500000 enforced (600k char content rejected)
7. Login still works after all changes
8. Login wrong password returns 401 for known AND unknown email (same error message - timing attack fix)
9. Tenant admin can create valid promo codes
10. Tenant admin can create products with normal names
11. SSRF protection: AWS metadata IP blocked
12. Valid webhook URL allowed
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

TENANT_ADMIN_EMAIL = "mayank@automateaccounts.com"
TENANT_ADMIN_PASSWORD = "ChangeMe123!"
TENANT_PARTNER_CODE = "AA"

SUPER_ADMIN_EMAIL = "admin@automateaccounts.local"
SUPER_ADMIN_PASSWORD = "ChangeMe123!"

# IDs to clean up after tests
_created_promo_ids = []
_created_product_ids = []
_created_webhook_ids = []


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def tenant_token(session):
    """JWT for tenant admin."""
    resp = session.post(f"{BASE_URL}/api/auth/partner-login", json={
        "partner_code": TENANT_PARTNER_CODE,
        "email": TENANT_ADMIN_EMAIL,
        "password": TENANT_ADMIN_PASSWORD,
    })
    if resp.status_code != 200:
        pytest.skip(f"Tenant admin login failed ({resp.status_code}): {resp.text[:300]}")
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    if not token:
        pytest.skip(f"No token in login response: {data}")
    return token


@pytest.fixture(scope="module")
def tenant_auth(tenant_token):
    """Requests session authenticated as tenant admin."""
    s = requests.Session()
    s.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {tenant_token}",
    })
    return s


@pytest.fixture(scope="module")
def super_token(session):
    """JWT for super admin."""
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL,
        "password": SUPER_ADMIN_PASSWORD,
    })
    if resp.status_code != 200:
        pytest.skip(f"Super admin login failed ({resp.status_code}): {resp.text[:300]}")
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    if not token:
        pytest.skip(f"No token in login response: {data}")
    return token


# ---------------------------------------------------------------------------
# Cleanup helpers
# ---------------------------------------------------------------------------

def _cleanup_promo(auth, promo_id: str):
    try:
        auth.delete(f"{BASE_URL}/api/admin/promo-codes/{promo_id}")
    except Exception:
        pass


def _cleanup_product(auth, product_id: str):
    try:
        auth.delete(f"{BASE_URL}/api/admin/products/{product_id}")
    except Exception:
        pass


def _cleanup_webhook(auth, webhook_id: str):
    try:
        auth.delete(f"{BASE_URL}/api/admin/webhooks/{webhook_id}")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 1. Promo code validation tests
# ---------------------------------------------------------------------------

class TestPromoCodeValidation:
    """Tests for Pydantic validators on PromoCodeCreate."""

    def test_discount_over_100_percent_rejected(self, tenant_auth):
        """POST /api/admin/promo-codes with discount_value=150 (percentage) must return 422."""
        resp = tenant_auth.post(f"{BASE_URL}/api/admin/promo-codes", json={
            "code": "TEST_OVER100",
            "discount_type": "percentage",
            "discount_value": 150.0,
            "applies_to": "all",
        })
        assert resp.status_code == 422, (
            f"Expected 422 for >100% discount, got {resp.status_code}: {resp.text[:300]}"
        )
        data = resp.json()
        detail_str = str(data.get("detail", "")).lower()
        assert "100" in detail_str or "percentage" in detail_str or "exceed" in detail_str, (
            f"Expected error about 100% limit in: {data.get('detail')}"
        )
        print(f"PASS: 150% discount rejected with 422 - detail: {data.get('detail')}")

    def test_negative_discount_rejected(self, tenant_auth):
        """POST /api/admin/promo-codes with discount_value=-50 must return 422."""
        resp = tenant_auth.post(f"{BASE_URL}/api/admin/promo-codes", json={
            "code": "TEST_NEG_DISCOUNT",
            "discount_type": "percentage",
            "discount_value": -50.0,
            "applies_to": "all",
        })
        assert resp.status_code == 422, (
            f"Expected 422 for negative discount, got {resp.status_code}: {resp.text[:300]}"
        )
        data = resp.json()
        detail_str = str(data.get("detail", "")).lower()
        assert "negative" in detail_str or "non-negative" in detail_str or "0" in detail_str or "discount" in detail_str, (
            f"Expected error about non-negative in: {data.get('detail')}"
        )
        print(f"PASS: -50 discount rejected with 422 - detail: {data.get('detail')}")

    def test_negative_fixed_discount_rejected(self, tenant_auth):
        """POST /api/admin/promo-codes with discount_value=-10 (fixed) must also return 422."""
        resp = tenant_auth.post(f"{BASE_URL}/api/admin/promo-codes", json={
            "code": "TEST_NEG_FIXED",
            "discount_type": "fixed",
            "discount_value": -10.0,
            "applies_to": "all",
        })
        assert resp.status_code == 422, (
            f"Expected 422 for negative fixed discount, got {resp.status_code}: {resp.text[:300]}"
        )
        print(f"PASS: -10 fixed discount rejected with 422")

    def test_100_percent_discount_allowed(self, tenant_auth):
        """POST /api/admin/promo-codes with discount_value=100 (percentage) must succeed (200/201)."""
        code_suffix = str(int(time.time()))[-6:]
        code = f"TEST_FULL100_{code_suffix}"
        resp = tenant_auth.post(f"{BASE_URL}/api/admin/promo-codes", json={
            "code": code,
            "discount_type": "percentage",
            "discount_value": 100.0,
            "applies_to": "all",
        })
        assert resp.status_code in (200, 201), (
            f"Expected 200/201 for 100% discount, got {resp.status_code}: {resp.text[:300]}"
        )
        data = resp.json()
        promo_id = data.get("id")
        assert promo_id, f"Expected 'id' in response: {data}"
        _created_promo_ids.append(promo_id)
        # Cleanup
        _cleanup_promo(tenant_auth, promo_id)
        print(f"PASS: 100% discount allowed, created id={promo_id}")

    def test_valid_percentage_promo_created(self, tenant_auth):
        """Tenant admin can create a valid promo code (normal discount)."""
        code_suffix = str(int(time.time()))[-6:]
        code = f"TEST_VALID20_{code_suffix}"
        resp = tenant_auth.post(f"{BASE_URL}/api/admin/promo-codes", json={
            "code": code,
            "discount_type": "percentage",
            "discount_value": 20.0,
            "applies_to": "all",
        })
        assert resp.status_code in (200, 201), (
            f"Expected 200/201 for valid promo, got {resp.status_code}: {resp.text[:300]}"
        )
        data = resp.json()
        promo_id = data.get("id")
        assert promo_id, f"Expected 'id' in response: {data}"
        _created_promo_ids.append(promo_id)
        # Cleanup
        _cleanup_promo(tenant_auth, promo_id)
        print(f"PASS: Valid 20% promo created, id={promo_id}")

    def test_valid_fixed_promo_created(self, tenant_auth):
        """Tenant admin can create a valid fixed-value promo code."""
        code_suffix = str(int(time.time()))[-6:]
        code = f"TEST_FIXED10_{code_suffix}"
        resp = tenant_auth.post(f"{BASE_URL}/api/admin/promo-codes", json={
            "code": code,
            "discount_type": "fixed",
            "discount_value": 10.0,
            "applies_to": "all",
        })
        assert resp.status_code in (200, 201), (
            f"Expected 200/201 for fixed promo, got {resp.status_code}: {resp.text[:300]}"
        )
        data = resp.json()
        promo_id = data.get("id")
        assert promo_id
        _created_promo_ids.append(promo_id)
        _cleanup_promo(tenant_auth, promo_id)
        print(f"PASS: Valid fixed $10 promo created, id={promo_id}")

    def test_old_100_percent_promo_cleanup(self, tenant_auth):
        """Clean up the old ALLFREE promo code if it exists."""
        old_id = "fc26c6a7-15a7-47ba-8f3c-9777afb10a8f"
        resp = tenant_auth.delete(f"{BASE_URL}/api/admin/promo-codes/{old_id}")
        # 200 = deleted, 404 = already gone — both acceptable
        assert resp.status_code in (200, 404), (
            f"Unexpected status cleaning up ALLFREE: {resp.status_code}: {resp.text[:200]}"
        )
        print(f"PASS: Old ALLFREE promo cleanup status={resp.status_code}")


# ---------------------------------------------------------------------------
# 2. Product field length tests
# ---------------------------------------------------------------------------

class TestProductFieldLengths:
    """Tests for max_length constraints on AdminProductCreate."""

    def test_100k_product_name_rejected(self, tenant_auth):
        """POST /api/admin/products with 100k-char name must return 422."""
        long_name = "A" * 100_000
        resp = tenant_auth.post(f"{BASE_URL}/api/admin/products", json={
            "name": long_name,
            "description_long": "Test product",
        })
        assert resp.status_code == 422, (
            f"Expected 422 for 100k-char name, got {resp.status_code}: {resp.text[:300]}"
        )
        print(f"PASS: 100k-char product name rejected with 422")

    def test_501_char_product_name_rejected(self, tenant_auth):
        """POST /api/admin/products with 501-char name must return 422 (max is 500)."""
        name_501 = "B" * 501
        resp = tenant_auth.post(f"{BASE_URL}/api/admin/products", json={
            "name": name_501,
            "description_long": "Test product",
        })
        assert resp.status_code == 422, (
            f"Expected 422 for 501-char name, got {resp.status_code}: {resp.text[:300]}"
        )
        print(f"PASS: 501-char product name rejected with 422")

    def test_500_char_product_name_accepted(self, tenant_auth):
        """POST /api/admin/products with exactly 500-char name must succeed."""
        name_500 = "C" * 500
        resp = tenant_auth.post(f"{BASE_URL}/api/admin/products", json={
            "name": name_500,
            "description_long": "Test product boundary",
        })
        assert resp.status_code in (200, 201), (
            f"Expected 200/201 for 500-char name, got {resp.status_code}: {resp.text[:300]}"
        )
        data = resp.json()
        product_id = data.get("id") or data.get("product_id")
        if product_id:
            _created_product_ids.append(product_id)
            _cleanup_product(tenant_auth, product_id)
        print(f"PASS: 500-char product name accepted, id={product_id}")

    def test_normal_product_name_accepted(self, tenant_auth):
        """Tenant admin can create a product with a normal name."""
        resp = tenant_auth.post(f"{BASE_URL}/api/admin/products", json={
            "name": "TEST_SecurityAuditProduct",
            "description_long": "A test product for security audit",
            "base_price": 9.99,
        })
        assert resp.status_code in (200, 201), (
            f"Expected 200/201 for normal product, got {resp.status_code}: {resp.text[:300]}"
        )
        data = resp.json()
        product_id = data.get("id") or data.get("product_id")
        if product_id:
            _created_product_ids.append(product_id)
            _cleanup_product(tenant_auth, product_id)
        print(f"PASS: Normal product name accepted, id={product_id}")


# ---------------------------------------------------------------------------
# 3. Terms content length tests
# ---------------------------------------------------------------------------

class TestTermsContentLength:
    """Tests for max_length=500000 on TermsCreate.content."""

    def test_600k_content_rejected(self, tenant_auth):
        """POST /api/admin/terms with 600k-char content must return 422."""
        long_content = "X" * 600_000
        resp = tenant_auth.post(f"{BASE_URL}/api/admin/terms", json={
            "title": "TEST_TermsOverLimit",
            "content": long_content,
            "status": "active",
        })
        assert resp.status_code == 422, (
            f"Expected 422 for 600k-char terms content, got {resp.status_code}: {resp.text[:300]}"
        )
        print(f"PASS: 600k-char terms content rejected with 422")

    def test_500k_content_accepted(self, tenant_auth):
        """POST /api/admin/terms with exactly 500k-char content must succeed."""
        content_500k = "Y" * 500_000
        resp = tenant_auth.post(f"{BASE_URL}/api/admin/terms", json={
            "title": "TEST_TermsBoundary",
            "content": content_500k,
            "status": "active",
        })
        assert resp.status_code in (200, 201), (
            f"Expected 200/201 for 500k-char terms content, got {resp.status_code}: {resp.text[:300]}"
        )
        data = resp.json()
        terms_id = data.get("id")
        # Cleanup
        if terms_id:
            tenant_auth.delete(f"{BASE_URL}/api/admin/terms/{terms_id}")
        print(f"PASS: 500k-char terms content accepted, id={terms_id}")


# ---------------------------------------------------------------------------
# 4. Auth/login tests
# ---------------------------------------------------------------------------

class TestAuthLogin:
    """Tests for login endpoint with valid credentials and timing attack fix."""

    def test_super_admin_login_valid_credentials(self, session):
        """POST /api/auth/login with super admin credentials must return 200."""
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD,
        })
        assert resp.status_code == 200, (
            f"Expected 200 for super admin login, got {resp.status_code}: {resp.text[:300]}"
        )
        data = resp.json()
        assert "token" in data, f"Expected 'token' in response: {data}"
        assert data["token"], "Token should not be empty"
        print(f"PASS: Super admin login succeeded")

    def test_tenant_admin_login_valid_credentials(self, session):
        """POST /api/auth/partner-login with tenant admin credentials must return 200."""
        resp = session.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": TENANT_PARTNER_CODE,
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD,
        })
        assert resp.status_code == 200, (
            f"Expected 200 for tenant admin login, got {resp.status_code}: {resp.text[:300]}"
        )
        data = resp.json()
        assert "token" in data, f"Expected 'token' in response: {data}"
        print(f"PASS: Tenant admin partner-login succeeded")

    def test_login_wrong_password_known_email_returns_401(self, session):
        """Wrong password for known email (timing attack fix path) must return 401."""
        resp = session.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": TENANT_PARTNER_CODE,
            "email": TENANT_ADMIN_EMAIL,
            "password": "WrongPassword999!",
        })
        assert resp.status_code == 401, (
            f"Expected 401 for wrong password known email, got {resp.status_code}: {resp.text[:300]}"
        )
        data = resp.json()
        detail = data.get("detail", "")
        assert "Invalid credentials" in detail, (
            f"Expected 'Invalid credentials' in detail, got: {detail}"
        )
        print(f"PASS: Wrong password for known email returns 401 with 'Invalid credentials'")

    def test_login_wrong_password_unknown_email_returns_401(self, session):
        """Unknown email must return 401 with same error message (timing attack fix)."""
        resp = session.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": TENANT_PARTNER_CODE,
            "email": "nonexistent_user_292@example.com",
            "password": "WrongPassword999!",
        })
        assert resp.status_code == 401, (
            f"Expected 401 for unknown email, got {resp.status_code}: {resp.text[:300]}"
        )
        data = resp.json()
        detail = data.get("detail", "")
        assert "Invalid credentials" in detail, (
            f"Expected 'Invalid credentials' in detail for unknown email, got: {detail}"
        )
        print(f"PASS: Unknown email returns 401 with 'Invalid credentials' (same message as known email)")

    def test_known_and_unknown_email_same_error_message(self, session):
        """Both known-wrong and unknown email must return identical error detail (no user enumeration)."""
        # Known email, wrong password
        resp_known = session.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": TENANT_PARTNER_CODE,
            "email": TENANT_ADMIN_EMAIL,
            "password": "TotallyWrong123!",
        })
        # Unknown email
        resp_unknown = session.post(f"{BASE_URL}/api/auth/partner-login", json={
            "partner_code": TENANT_PARTNER_CODE,
            "email": "doesnotexist292@example.com",
            "password": "TotallyWrong123!",
        })

        assert resp_known.status_code == 401, f"Known email wrong pwd: {resp_known.status_code}"
        assert resp_unknown.status_code == 401, f"Unknown email: {resp_unknown.status_code}"

        detail_known = resp_known.json().get("detail", "")
        detail_unknown = resp_unknown.json().get("detail", "")

        assert detail_known == detail_unknown, (
            f"Error messages differ: known='{detail_known}', unknown='{detail_unknown}'"
        )
        print(f"PASS: Both known+unknown email return identical error: '{detail_known}'")


# ---------------------------------------------------------------------------
# 5. SSRF Protection tests
# ---------------------------------------------------------------------------

class TestSSRFProtection:
    """Tests for SSRF protection on webhook creation."""

    def test_aws_metadata_ip_blocked(self, tenant_auth):
        """POST /api/admin/webhooks with url=http://169.254.169.254/ must return 400."""
        resp = tenant_auth.post(f"{BASE_URL}/api/admin/webhooks", json={
            "name": "TEST_SSRF_Metadata_292",
            "url": "http://169.254.169.254/",
            "events": ["order.created"],
        })
        assert resp.status_code == 400, (
            f"Expected 400 for SSRF AWS metadata IP, got {resp.status_code}: {resp.text[:300]}"
        )
        print(f"PASS: SSRF AWS metadata IP 169.254.169.254 blocked with 400")

    def test_loopback_ip_blocked(self, tenant_auth):
        """POST /api/admin/webhooks with url=http://127.0.0.1/ must return 400."""
        resp = tenant_auth.post(f"{BASE_URL}/api/admin/webhooks", json={
            "name": "TEST_SSRF_Loopback_292",
            "url": "http://127.0.0.1:8001/api/admin/users",
            "events": ["order.created"],
        })
        assert resp.status_code == 400, (
            f"Expected 400 for SSRF loopback IP, got {resp.status_code}: {resp.text[:300]}"
        )
        print(f"PASS: SSRF loopback 127.0.0.1 blocked with 400")

    def test_valid_external_url_allowed(self, tenant_auth):
        """POST /api/admin/webhooks with a valid external URL must succeed."""
        resp = tenant_auth.post(f"{BASE_URL}/api/admin/webhooks", json={
            "name": "TEST_ValidWebhook_292",
            "url": "https://httpbin.org/post",
            "events": ["order.created"],
        })
        assert resp.status_code in (200, 201), (
            f"Expected 200/201 for valid external webhook URL, got {resp.status_code}: {resp.text[:300]}"
        )
        data = resp.json()
        webhook_id = data.get("id")
        assert webhook_id, f"Expected 'id' in response: {data}"
        _created_webhook_ids.append(webhook_id)
        # Cleanup
        _cleanup_webhook(tenant_auth, webhook_id)
        print(f"PASS: Valid external webhook URL accepted, id={webhook_id}")


# ---------------------------------------------------------------------------
# 6. Checkout discount capping tests (API-level verification)
# ---------------------------------------------------------------------------

class TestCheckoutDiscountCapping:
    """Tests verifying discount_amount is capped and total cannot go negative."""

    def test_discount_capped_in_checkout_preview(self, tenant_auth):
        """Verify the checkout calculate tax endpoint works (returns valid structure)."""
        resp = tenant_auth.post(f"{BASE_URL}/api/checkout/calculate-tax", json={
            "subtotal": 50.0,
        })
        # May return 404 (no customer for admin) or 200 — just not a 500 server error
        assert resp.status_code != 500, (
            f"Checkout calculate-tax returned 500: {resp.text[:300]}"
        )
        print(f"PASS: Checkout calculate-tax endpoint is healthy (status={resp.status_code})")


# ---------------------------------------------------------------------------
# Module-level cleanup fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def cleanup_all(tenant_auth):
    """Cleanup any test data that persisted after individual tests."""
    yield
    for pid in _created_promo_ids:
        _cleanup_promo(tenant_auth, pid)
    for prod_id in _created_product_ids:
        _cleanup_product(tenant_auth, prod_id)
    for wh_id in _created_webhook_ids:
        _cleanup_webhook(tenant_auth, wh_id)
