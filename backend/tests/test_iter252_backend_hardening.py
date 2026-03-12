"""
Backend hardening fixes - iteration 252
Tests for 7 backend security/validation fixes:
  Fix 1: GET /api/checkout/status/{session_id} returns 404 for invalid session
  Fix 2: Invalid X-API-Key returns 401 (not 422)
  Fix 3: /api/auth/tenant-info and /api/tenant-info rate limiting (20/min)
  Fix 4: POST /api/auth/customer-login returns 403 for admin accounts and unverified users
  Fix 5: POST /api/auth/register accepts first_name + last_name
  Fix 6: POST /api/orders/preview rejects quantity < 1 (ge=1)
  Fix 7: GET /api/orders and GET /api/subscriptions return empty list for admin JWT
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_token():
    """Get platform admin JWT token (no partner_code needed)."""
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@automateaccounts.local", "password": "ChangeMe123!"},
    )
    assert resp.status_code == 200, f"Admin login failed: {resp.status_code} {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def partner_tenant(admin_headers):
    """Create a test partner tenant for Fix 4 testing."""
    resp = requests.post(
        f"{BASE_URL}/api/admin/tenants",
        json={"name": "TEST_HardeningOrg", "code": "test-hardening-fix4", "status": "active"},
        headers=admin_headers,
    )
    if resp.status_code in (200, 201):
        return resp.json()
    # Try to get existing
    get_resp = requests.get(f"{BASE_URL}/api/admin/tenants", headers=admin_headers)
    if get_resp.status_code == 200:
        tenants = get_resp.json().get("tenants", [])
        for t in tenants:
            if t.get("code") == "test-hardening-fix4":
                return t
    pytest.skip(f"Could not create test tenant: {resp.status_code} {resp.text}")


@pytest.fixture(scope="module")
def partner_admin_user(admin_headers, partner_tenant):
    """Create a partner_admin user in the test tenant."""
    tenant_id = partner_tenant.get("id") or partner_tenant.get("tenant", {}).get("id")
    resp = requests.post(
        f"{BASE_URL}/api/admin/users",
        json={
            "email": "TEST_admin_fix4@example.com",
            "full_name": "Test Admin Fix4",
            "password": "TestAdmin123!",
            "role": "partner_admin",
            "target_tenant_id": tenant_id,
        },
        headers=admin_headers,
    )
    if resp.status_code in (200, 201):
        return {"email": "TEST_admin_fix4@example.com", "password": "TestAdmin123!", "tenant_id": tenant_id}
    pytest.skip(f"Could not create test admin user: {resp.status_code} {resp.text}")


# ─────────────────────────────────────────────────────────────────────────────
# Fix 1: Checkout status returns 404 for invalid session IDs
# ─────────────────────────────────────────────────────────────────────────────

class TestFix1CheckoutStatus404:
    """Fix 1: GET /api/checkout/status/{session_id} returns 404 JSON for invalid session"""

    def test_invalid_session_returns_404(self, admin_headers):
        """Invalid session ID should return 404 (not 500)."""
        resp = requests.get(
            f"{BASE_URL}/api/checkout/status/invalid_session_12345",
            headers=admin_headers,
        )
        assert resp.status_code == 404, (
            f"Expected 404 for invalid session, got {resp.status_code}: {resp.text}"
        )

    def test_invalid_session_returns_json_error(self, admin_headers):
        """Response must be JSON with error/detail key."""
        resp = requests.get(
            f"{BASE_URL}/api/checkout/status/cs_test_totally_fake_session_id_xyz",
            headers=admin_headers,
        )
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data or "error" in data, f"Expected error key in JSON: {data}"
        msg = data.get("detail") or data.get("error", "")
        assert "session" in msg.lower() or "not found" in msg.lower(), (
            f"Expected 'session not found' message, got: {msg}"
        )

    def test_obviously_fake_session_returns_404_not_500(self, admin_headers):
        """Verify no 500 internal server error for a random fake session."""
        resp = requests.get(
            f"{BASE_URL}/api/checkout/status/FAKE_SESSION_00000000",
            headers=admin_headers,
        )
        assert resp.status_code != 500, f"Got 500 internal error: {resp.text}"
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# Fix 2: Invalid X-API-Key returns 401 (not 422)
# ─────────────────────────────────────────────────────────────────────────────

class TestFix2ApiKeyReturns401:
    """Fix 2: Invalid X-API-Key header returns 401 Unauthorized"""

    def test_invalid_api_key_on_tenant_info_returns_401(self):
        """Providing an invalid API key should return 401, not 422."""
        resp = requests.get(
            f"{BASE_URL}/api/tenant-info",
            headers={"X-API-Key": "totally_invalid_key_12345"},
        )
        assert resp.status_code == 401, (
            f"Expected 401 for invalid API key, got {resp.status_code}: {resp.text}"
        )

    def test_invalid_api_key_returns_json_response(self):
        """Invalid API key response should be JSON."""
        resp = requests.get(
            f"{BASE_URL}/api/tenant-info",
            headers={"X-API-Key": "bad_key_xyz_000"},
        )
        assert resp.status_code == 401
        data = resp.json()
        assert "detail" in data, f"Expected 'detail' key in JSON response: {data}"

    def test_invalid_api_key_on_products_returns_401(self):
        """Invalid X-API-Key on /api/products should also return 401."""
        resp = requests.get(
            f"{BASE_URL}/api/products",
            headers={"X-API-Key": "invalid_key_for_products"},
        )
        assert resp.status_code == 401, (
            f"Expected 401, got {resp.status_code}: {resp.text}"
        )

    def test_no_api_key_on_public_endpoint_is_ok(self):
        """Public endpoint without X-API-Key should work normally (200 or similar)."""
        resp = requests.get(
            f"{BASE_URL}/api/tenant-info",
            params={"code": "automate-accounts"},
        )
        # No API key, no code = 400; with valid code = 200
        assert resp.status_code in (200, 400, 404), (
            f"Unexpected status without API key: {resp.status_code}"
        )
        # Definitely not 401 or 422
        assert resp.status_code != 401
        assert resp.status_code != 422


# ─────────────────────────────────────────────────────────────────────────────
# Fix 3: Rate limiting on /api/tenant-info (20/min) and /api/auth/tenant-info
# ─────────────────────────────────────────────────────────────────────────────

class TestFix3RateLimiting:
    """Fix 3: /api/tenant-info and /api/auth/tenant-info rate limited at 20/min"""

    def test_tenant_info_endpoint_responds(self):
        """Verify /api/tenant-info endpoint is accessible."""
        resp = requests.get(
            f"{BASE_URL}/api/tenant-info",
            params={"code": "automate-accounts"},
        )
        assert resp.status_code in (200, 400, 404), (
            f"Unexpected status: {resp.status_code}"
        )

    def test_rate_limit_check_on_tenant_info_path(self):
        """
        Send 25 rapid requests to /api/tenant-info.
        Fix 3 adds rate limit of 20/min for /api/auth/tenant-info.
        IMPORTANT NOTE: If the rate limit path in rate_limit.py is /api/auth/tenant-info
        but the actual route is /api/tenant-info, the 20/min limit won't apply.
        This test verifies whether 429 is returned after 20 requests.
        """
        session = requests.Session()
        responses = []
        for i in range(25):
            resp = session.get(
                f"{BASE_URL}/api/tenant-info",
                params={"code": "automate-accounts"},
            )
            responses.append(resp.status_code)

        status_counts = {}
        for s in responses:
            status_counts[s] = status_counts.get(s, 0) + 1

        print(f"Fix 3 - Rate limit test status distribution: {status_counts}")
        got_429 = 429 in responses
        if not got_429:
            # Check if path mismatch exists in rate_limit.py
            # /api/auth/tenant-info vs actual /api/tenant-info
            print(
                "WARNING: No 429 received for /api/tenant-info with 25 requests. "
                "Possible path mismatch: rate_limit.py uses /api/auth/tenant-info "
                "but the actual endpoint is /api/tenant-info"
            )

        # Test /api/auth/tenant-info to see if that path is rate limited instead
        auth_responses = []
        for i in range(5):
            r = session.get(f"{BASE_URL}/api/auth/tenant-info")
            auth_responses.append(r.status_code)
        print(f"Fix 3 - /api/auth/tenant-info status codes: {auth_responses}")

        # Return test result - 429 should appear on /api/tenant-info within 25 requests
        assert got_429, (
            f"Expected 429 after 20 requests to /api/tenant-info, "
            f"but got: {status_counts}. "
            f"Check rate_limit.py: /api/auth/tenant-info should be /api/tenant-info"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Fix 4: customer-login 403 for admin accounts and unverified users
# ─────────────────────────────────────────────────────────────────────────────

class TestFix4CustomerLoginErrors:
    """Fix 4: POST /api/auth/customer-login returns 403 for admin accounts and unverified users"""

    def test_customer_login_with_admin_account_returns_403(self, partner_admin_user):
        """Admin account trying customer-login should return 403 with specific message."""
        resp = requests.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={
                "partner_code": "test-hardening-fix4",
                "email": partner_admin_user["email"],
                "password": partner_admin_user["password"],
            },
        )
        assert resp.status_code == 403, (
            f"Expected 403 for admin using customer-login, got {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        detail = data.get("detail", "")
        assert "partner-login" in detail.lower() or "admin" in detail.lower(), (
            f"Expected 'use partner-login' message, got: {detail}"
        )

    def test_customer_login_admin_error_message_exact(self, partner_admin_user):
        """Error message should specifically mention /api/auth/partner-login."""
        resp = requests.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={
                "partner_code": "test-hardening-fix4",
                "email": partner_admin_user["email"],
                "password": partner_admin_user["password"],
            },
        )
        assert resp.status_code == 403
        data = resp.json()
        detail = data.get("detail", "")
        # The exact message from auth.py line 285
        assert "/api/auth/partner-login" in detail, (
            f"Expected '/api/auth/partner-login' in error, got: '{detail}'"
        )

    def test_customer_login_unverified_user_returns_403(self):
        """Unverified user trying to login should return 403 'Email not verified'."""
        # Register a new customer (will be unverified)
        email = "TEST_unverified_fix4@example.com"
        reg_resp = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": email,
                "password": "TestPass123!",
                "first_name": "Test",
                "last_name": "Unverified",
                "company_name": "Test Co",
                "partner_code": "test-hardening-fix4",
                "address": {
                    "line1": "123 Test St",
                    "city": "London",
                    "region": "England",
                    "postal": "SW1A 1AA",
                    "country": "GB",
                },
            },
        )
        print(f"Register response: {reg_resp.status_code} {reg_resp.text}")
        # Registration may succeed or fail — only skip if tenant doesn't exist
        if reg_resp.status_code == 400 and "partner code" in reg_resp.text.lower():
            pytest.skip("Test tenant not available")

        # Try login as unverified user
        login_resp = requests.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={
                "partner_code": "test-hardening-fix4",
                "email": email,
                "password": "TestPass123!",
            },
        )
        print(f"Customer login (unverified): {login_resp.status_code} {login_resp.text}")
        # Should be 403 with "Email not verified"
        assert login_resp.status_code == 403, (
            f"Expected 403 for unverified user, got {login_resp.status_code}: {login_resp.text}"
        )
        data = login_resp.json()
        detail = data.get("detail", "")
        assert "verified" in detail.lower() or "verification" in detail.lower(), (
            f"Expected 'not verified' message, got: '{detail}'"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Fix 5: /api/auth/register accepts first_name + last_name
# ─────────────────────────────────────────────────────────────────────────────

class TestFix5RegisterFirstLastName:
    """Fix 5: POST /api/auth/register accepts first_name + last_name instead of full_name"""

    def test_register_with_first_last_name_succeeds(self):
        """Registration with first_name + last_name (no full_name) should succeed."""
        resp = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": "TEST_firstlast@example.com",
                "password": "TestPass123!",
                "first_name": "John",
                "last_name": "Doe",
                "company_name": "Test Corp",
                "partner_code": "test-hardening-fix4",
                "address": {
                    "line1": "10 Downing Street",
                    "city": "London",
                    "region": "England",
                    "postal": "SW1A 2AA",
                    "country": "GB",
                },
            },
        )
        # Registration should succeed (200) or user already exists (400 "already registered")
        # Should NOT fail with "full_name required" type error
        if resp.status_code == 400 and "partner code" in resp.text.lower():
            pytest.skip("Test tenant not found")
        assert resp.status_code in (200, 201), (
            f"Expected success with first_name+last_name, got {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        assert "verification" in data.get("message", "").lower() or "required" in data.get("message", "").lower(), (
            f"Unexpected message: {data}"
        )

    def test_register_with_full_name_still_works(self):
        """Registration with full_name (backward compat) should still work."""
        resp = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": "TEST_fullname_compat@example.com",
                "password": "TestPass123!",
                "full_name": "Jane Smith",
                "company_name": "Test Corp",
                "partner_code": "test-hardening-fix4",
                "address": {
                    "line1": "1 Test Road",
                    "city": "Manchester",
                    "region": "England",
                    "postal": "M1 1AA",
                    "country": "GB",
                },
            },
        )
        if resp.status_code == 400 and "partner code" in resp.text.lower():
            pytest.skip("Test tenant not found")
        assert resp.status_code in (200, 201), (
            f"full_name registration should work: {resp.status_code} {resp.text}"
        )

    def test_register_no_name_returns_400(self):
        """Registration with no name at all (no full_name, first_name, last_name) should return 400."""
        resp = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": "TEST_noname@example.com",
                "password": "TestPass123!",
                # no full_name, first_name, or last_name
                "company_name": "Test Corp",
                "partner_code": "test-hardening-fix4",
                "address": {
                    "line1": "5 Test Ave",
                    "city": "Birmingham",
                    "region": "England",
                    "postal": "B1 1AA",
                    "country": "GB",
                },
            },
        )
        if resp.status_code == 400 and "partner code" in resp.text.lower():
            pytest.skip("Test tenant not found")
        # Both 400 (name required) and 422 (validation error) are acceptable
        assert resp.status_code in (400, 422), (
            f"Expected 400/422 with no name, got {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        detail = str(data.get("detail", ""))
        print(f"No-name register response: {resp.status_code} - {detail}")
        assert "name" in detail.lower(), (
            f"Expected name-related error message, got: {detail}"
        )

    def test_register_only_first_name_works(self):
        """Registration with only first_name (no last_name) should succeed."""
        resp = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": "TEST_firstname_only@example.com",
                "password": "TestPass123!",
                "first_name": "Alice",
                # no last_name
                "partner_code": "test-hardening-fix4",
                "address": {
                    "line1": "7 Alpha Road",
                    "city": "Leeds",
                    "region": "England",
                    "postal": "LS1 1AA",
                    "country": "GB",
                },
            },
        )
        if resp.status_code == 400 and "partner code" in resp.text.lower():
            pytest.skip("Test tenant not found")
        assert resp.status_code in (200, 201), (
            f"first_name only should work, got {resp.status_code}: {resp.text}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Fix 6: /api/orders/preview rejects quantity < 1
# ─────────────────────────────────────────────────────────────────────────────

class TestFix6OrdersPreviewQuantityValidation:
    """Fix 6: POST /api/orders/preview rejects quantity < 1 with 422"""

    def _get_a_product_id(self, admin_headers):
        """Get any active product ID."""
        resp = requests.get(f"{BASE_URL}/api/products", headers=admin_headers)
        if resp.status_code == 200:
            products = resp.json().get("products", [])
            if products:
                return products[0]["id"]
        return "any-product-id"

    def test_preview_quantity_zero_returns_422(self, admin_headers):
        """quantity=0 should return 422 validation error."""
        product_id = self._get_a_product_id(admin_headers)
        resp = requests.post(
            f"{BASE_URL}/api/orders/preview",
            json={"items": [{"product_id": product_id, "quantity": 0, "inputs": {}}]},
            headers=admin_headers,
        )
        assert resp.status_code == 422, (
            f"Expected 422 for quantity=0, got {resp.status_code}: {resp.text}"
        )

    def test_preview_quantity_negative_returns_422(self, admin_headers):
        """quantity=-1 should return 422 validation error."""
        product_id = self._get_a_product_id(admin_headers)
        resp = requests.post(
            f"{BASE_URL}/api/orders/preview",
            json={"items": [{"product_id": product_id, "quantity": -1, "inputs": {}}]},
            headers=admin_headers,
        )
        assert resp.status_code == 422, (
            f"Expected 422 for quantity=-1, got {resp.status_code}: {resp.text}"
        )

    def test_preview_quantity_one_is_valid(self, admin_headers):
        """quantity=1 should NOT return 422 (may 404 if product not found, but not 422 for quantity)."""
        product_id = self._get_a_product_id(admin_headers)
        resp = requests.post(
            f"{BASE_URL}/api/orders/preview",
            json={"items": [{"product_id": product_id, "quantity": 1, "inputs": {}}]},
            headers=admin_headers,
        )
        # Should be 200 (product found) or 404 (product not found), but NOT 422 for quantity
        print(f"Preview quantity=1: {resp.status_code}")
        assert resp.status_code != 422, (
            f"quantity=1 should be valid, but got 422: {resp.text}"
        )

    def test_preview_quantity_large_number_is_valid(self, admin_headers):
        """quantity=100 should be accepted (no upper bound on quantity)."""
        product_id = self._get_a_product_id(admin_headers)
        resp = requests.post(
            f"{BASE_URL}/api/orders/preview",
            json={"items": [{"product_id": product_id, "quantity": 100, "inputs": {}}]},
            headers=admin_headers,
        )
        assert resp.status_code != 422, (
            f"quantity=100 should be valid, got 422: {resp.text}"
        )

    def test_preview_quantity_validation_error_message(self, admin_headers):
        """422 response for quantity=0 should contain a clear validation message."""
        product_id = self._get_a_product_id(admin_headers)
        resp = requests.post(
            f"{BASE_URL}/api/orders/preview",
            json={"items": [{"product_id": product_id, "quantity": 0, "inputs": {}}]},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        data = resp.json()
        detail = str(data.get("detail", ""))
        print(f"Quantity validation error: {detail}")
        # Error should mention quantity or ge constraint
        assert detail, "Expected non-empty detail in 422 response"


# ─────────────────────────────────────────────────────────────────────────────
# Fix 7: GET /api/orders and GET /api/subscriptions return empty list for admin JWT
# ─────────────────────────────────────────────────────────────────────────────

class TestFix7AdminOrdersSubscriptionsEmptyList:
    """Fix 7: Admin JWT gets 200 with empty list from /api/orders and /api/subscriptions"""

    def test_admin_get_orders_returns_200_not_404(self, admin_headers):
        """Admin JWT on GET /api/orders should return 200 (not 404 'Customer not found')."""
        resp = requests.get(f"{BASE_URL}/api/orders", headers=admin_headers)
        assert resp.status_code == 200, (
            f"Expected 200 for admin on /api/orders, got {resp.status_code}: {resp.text}"
        )

    def test_admin_get_orders_returns_empty_list(self, admin_headers):
        """Admin JWT on GET /api/orders should return empty orders and items lists."""
        resp = requests.get(f"{BASE_URL}/api/orders", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "orders" in data, f"Expected 'orders' key in response: {data}"
        assert "items" in data, f"Expected 'items' key in response: {data}"
        assert data["orders"] == [], f"Expected empty orders list, got: {data['orders']}"
        assert data["items"] == [], f"Expected empty items list, got: {data['items']}"

    def test_admin_get_subscriptions_returns_200_not_404(self, admin_headers):
        """Admin JWT on GET /api/subscriptions should return 200 (not 404)."""
        resp = requests.get(f"{BASE_URL}/api/subscriptions", headers=admin_headers)
        assert resp.status_code == 200, (
            f"Expected 200 for admin on /api/subscriptions, got {resp.status_code}: {resp.text}"
        )

    def test_admin_get_subscriptions_returns_empty_list(self, admin_headers):
        """Admin JWT on GET /api/subscriptions should return empty subscriptions list."""
        resp = requests.get(f"{BASE_URL}/api/subscriptions", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "subscriptions" in data, f"Expected 'subscriptions' key: {data}"
        assert data["subscriptions"] == [], (
            f"Expected empty subscriptions list, got: {data['subscriptions']}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Additional edge case: X-API-Key ValidationError handler (Fix 2 extension)
# ─────────────────────────────────────────────────────────────────────────────

class TestFix2ExtendedValidation:
    """Extended tests for Fix 2: Validation error handler converts 422→401 for API key errors."""

    def test_invalid_api_key_not_422(self):
        """Ensure invalid key does NOT return 422 (Unprocessable Entity)."""
        resp = requests.get(
            f"{BASE_URL}/api/products",
            headers={"X-API-Key": "invalid-key-abc"},
        )
        assert resp.status_code != 422, (
            f"Got 422 for invalid API key - should be 401. Response: {resp.text}"
        )

    def test_invalid_api_key_status_is_401(self):
        """Invalid API key MUST return 401."""
        resp = requests.get(
            f"{BASE_URL}/api/categories",
            headers={"X-API-Key": "definitely_invalid_key_xyz"},
        )
        assert resp.status_code == 401, (
            f"Expected 401 for invalid key, got {resp.status_code}: {resp.text}"
        )
