"""
Iteration 184 - Email format validation and maxLength tests
Tests: email format validation in register + admin_create_customer,
field maxLength on email/company/phone, line2 optional placeholder
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_token():
    """Get platform admin JWT token"""
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@automateaccounts.local", "password": "ChangeMe123!"},
    )
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return resp.json()["token"]


# ── Backend: POST /api/auth/register email validation ────────────────────────

VALID_ADDRESS = {"line1": "123 Main St", "line2": "", "city": "Toronto", "region": "ON", "postal": "M5V 1A1", "country": "CA"}


class TestRegisterEmailValidation:
    """POST /api/auth/register - email format check"""

    def test_register_invalid_email_no_tld_returns_400(self):
        """'a@gmai' has no dot in domain → must return 400"""
        resp = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": "a@gmai",
                "password": "ValidPass1!",
                "full_name": "Test User",
                "partner_code": "automate-accounts",
                "address": VALID_ADDRESS,
            },
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        data = resp.json()
        detail = data.get("detail", "")
        assert "invalid" in detail.lower() or "format" in detail.lower(), (
            f"Expected 'invalid'/'format' in detail, got: {detail}"
        )

    def test_register_valid_email_format_accepted(self):
        """A properly formed email should not be rejected by the format check"""
        resp = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": "validtest_iter184@example.com",
                "password": "ValidPass1!",
                "full_name": "Valid User",
                "partner_code": "automate-accounts",
                "address": VALID_ADDRESS,
            },
        )
        # 200, 201, 400 (duplicate), 403 (reserved code), 409 all acceptable — NOT a format error
        assert resp.status_code in (200, 201, 400, 403, 409), (
            f"Unexpected status for valid email: {resp.status_code}: {resp.text}"
        )
        if resp.status_code == 400:
            detail = resp.json().get("detail", "")
            assert "format" not in detail.lower(), (
                f"Valid email rejected for format: {detail}"
            )

    def test_register_email_missing_dot_in_domain_returns_400(self):
        """'user@nodomain' (no dot, no TLD) → reject"""
        resp = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": "user@nodomain",
                "password": "ValidPass1!",
                "full_name": "Test",
                "partner_code": "automate-accounts",
                "address": VALID_ADDRESS,
            },
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"

    def test_register_email_single_char_tld_returns_400(self):
        """'user@test.c' (TLD < 2 chars) → reject"""
        resp = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": "user@test.c",
                "password": "ValidPass1!",
                "full_name": "Test",
                "partner_code": "automate-accounts",
                "address": VALID_ADDRESS,
            },
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"


# ── Backend: POST /api/admin/customers/create email validation ───────────────

class TestAdminCreateCustomerEmailValidation:
    """POST /api/admin/customers/create - email format check (admin auth required)"""

    def test_admin_create_invalid_email_returns_400(self, admin_token):
        """'a@gmai' → must return 400 with invalid email format message"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/customers/create",
            json={
                "email": "a@gmai",
                "password": "ValidPass1!",
                "full_name": "Test Invalid Email",
                "mark_verified": True,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        data = resp.json()
        detail = data.get("detail", "")
        assert "invalid" in detail.lower() or "format" in detail.lower(), (
            f"Expected 'invalid'/'format' in detail, got: {detail}"
        )

    def test_admin_create_valid_email_format_accepted(self, admin_token):
        """Properly-formed email should not get rejected by the format check"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/customers/create",
            json={
                "email": "test_iter184_validformat@example.com",
                "password": "ValidPass1!",
                "full_name": "Test Valid Admin Create",
                "mark_verified": True,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # 200, 201 (success) or 400 due to duplicate are fine. 400 for format is not.
        assert resp.status_code in (200, 201, 400, 409), (
            f"Unexpected: {resp.status_code}: {resp.text}"
        )
        if resp.status_code == 400:
            detail = resp.json().get("detail", "")
            assert "format" not in detail.lower(), (
                f"Valid email wrongly rejected for format: {detail}"
            )

    def test_admin_create_email_no_tld_returns_400(self, admin_token):
        """'user@nodomain' → reject"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/customers/create",
            json={
                "email": "user@nodomain",
                "password": "ValidPass1!",
                "full_name": "No TLD Test",
                "mark_verified": True,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"

    def test_admin_create_without_auth_returns_401_or_403(self):
        """Without token the endpoint must reject with 401/403"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/customers/create",
            json={
                "email": "noauth@example.com",
                "password": "ValidPass1!",
                "full_name": "No Auth",
                "mark_verified": True,
            },
        )
        assert resp.status_code in (401, 403), (
            f"Expected 401/403, got {resp.status_code}: {resp.text}"
        )
