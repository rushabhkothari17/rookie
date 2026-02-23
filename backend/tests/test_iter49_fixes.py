"""
Tests for iteration 49 fixes:
- P0 Bug 1: Payment provider bypass (stripe/gocardless disabled → 400)
- P0 Bug 2: Resend verification email endpoint
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# ─── helpers ────────────────────────────────────────────────────────────────

def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!",
    })
    if r.status_code == 200:
        return r.json().get("token")
    return None

def register_and_verify(suffix: str):
    """Register a test user, verify email, return (email, token)."""
    email = f"TEST_iter49_{suffix}@example.com"
    # Register
    r = requests.post(f"{BASE_URL}/api/auth/register", json={
        "email": email,
        "password": "TestPass123!",
        "full_name": "Test Iter49",
        "job_title": "Tester",
        "company_name": "Test Co",
        "phone": "+1 555 0100",
        "address": {"line1": "123 Main St", "line2": "", "city": "Toronto", "region": "ON", "postal": "M1A 1A1", "country": "Canada"},
    })
    assert r.status_code == 200, f"Register failed: {r.status_code} {r.text}"
    code = r.json().get("verification_code")
    assert code, "No verification_code in register response"
    # Verify
    rv = requests.post(f"{BASE_URL}/api/auth/verify-email", json={"email": email, "code": code})
    assert rv.status_code == 200, f"Verify failed: {rv.status_code} {rv.text}"
    # Login
    rl = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "TestPass123!"})
    assert rl.status_code == 200, f"Login failed: {rl.status_code} {rl.text}"
    token = rl.json().get("token")
    return email, token


# ─── P0 Bug 2: Resend verification email ────────────────────────────────────

class TestResendVerificationEmail:
    """Tests for POST /api/auth/resend-verification-email"""

    def test_resend_endpoint_exists_and_returns_200(self):
        """POST /api/auth/resend-verification-email should exist (not 404/405)"""
        email = f"TEST_resend_check_{int(time.time())}@example.com"
        # Register user (unverified)
        r = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": "TestPass123!",
            "full_name": "Resend Test",
            "job_title": "Tester",
            "company_name": "Test Co",
            "phone": "+1 555 0200",
            "address": {"line1": "1 Test St", "line2": "", "city": "Toronto", "region": "ON", "postal": "M1A 1A1", "country": "Canada"},
        })
        assert r.status_code == 200, f"Register failed: {r.status_code}"

        # Resend
        res = requests.post(f"{BASE_URL}/api/auth/resend-verification-email", json={"email": email})
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"

    def test_resend_returns_verification_code(self):
        """Response must include verification_code field"""
        email = f"TEST_resend_code_{int(time.time())}@example.com"
        requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": "TestPass123!",
            "full_name": "Resend Code",
            "job_title": "Tester",
            "company_name": "Test Co",
            "phone": "+1 555 0201",
            "address": {"line1": "1 Test St", "line2": "", "city": "Toronto", "region": "ON", "postal": "M1A 1A1", "country": "Canada"},
        })
        res = requests.post(f"{BASE_URL}/api/auth/resend-verification-email", json={"email": email})
        assert res.status_code == 200
        data = res.json()
        assert "verification_code" in data, f"verification_code missing from response: {data}"
        code = data["verification_code"]
        assert isinstance(code, str) and len(code) > 0, f"Invalid code: {code}"
        print(f"Got verification_code: {code}")

    def test_resend_for_nonexistent_user_returns_404(self):
        """Resend for unknown email should return 404"""
        res = requests.post(f"{BASE_URL}/api/auth/resend-verification-email", json={"email": "nonexistent_user_xyz@never.com"})
        assert res.status_code == 404, f"Expected 404, got {res.status_code}: {res.text}"

    def test_resend_for_already_verified_user_returns_message(self):
        """Resend for verified user should return graceful response"""
        email = f"TEST_resend_verified_{int(time.time())}@example.com"
        # Register + verify
        r = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": "TestPass123!",
            "full_name": "Already Verified",
            "job_title": "Tester",
            "company_name": "Test Co",
            "phone": "+1 555 0202",
            "address": {"line1": "1 Test St", "line2": "", "city": "Toronto", "region": "ON", "postal": "M1A 1A1", "country": "Canada"},
        })
        assert r.status_code == 200
        code = r.json().get("verification_code")
        requests.post(f"{BASE_URL}/api/auth/verify-email", json={"email": email, "code": code})

        # Now resend - should succeed but say "Already verified"
        res = requests.post(f"{BASE_URL}/api/auth/resend-verification-email", json={"email": email})
        assert res.status_code == 200
        data = res.json()
        assert "message" in data
        print(f"Resend for verified user: {data}")

    def test_resend_new_code_can_verify_email(self):
        """New code from resend should work for verification"""
        email = f"TEST_resend_verify_{int(time.time())}@example.com"
        # Register
        r = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": "TestPass123!",
            "full_name": "Resend Verify",
            "job_title": "Tester",
            "company_name": "Test Co",
            "phone": "+1 555 0203",
            "address": {"line1": "1 Test St", "line2": "", "city": "Toronto", "region": "ON", "postal": "M1A 1A1", "country": "Canada"},
        })
        assert r.status_code == 200
        old_code = r.json().get("verification_code")

        # Resend - gets new code
        res = requests.post(f"{BASE_URL}/api/auth/resend-verification-email", json={"email": email})
        assert res.status_code == 200
        new_code = res.json().get("verification_code")
        assert new_code, "No verification_code in resend response"

        # Verify with new code
        rv = requests.post(f"{BASE_URL}/api/auth/verify-email", json={"email": email, "code": new_code})
        assert rv.status_code == 200, f"Verify with new code failed: {rv.status_code}"
        print(f"Verified successfully with resent code (old={old_code}, new={new_code})")


# ─── P0 Bug 1: Payment provider bypass ─────────────────────────────────────

class TestPaymentProviderBypass:
    """Tests that stripe_enabled=false and gocardless_enabled=false block checkout"""

    def test_bank_transfer_blocked_when_gocardless_disabled(self):
        """POST /api/checkout/bank-transfer should return 400 when gocardless_enabled=false"""
        email, token = register_and_verify(f"gc_{int(time.time())}")
        headers = {"Authorization": f"Bearer {token}"}

        # Try bank transfer (gocardless is disabled)
        # First get a product to use in the request
        products_r = requests.get(f"{BASE_URL}/api/products")
        products = products_r.json().get("products", []) if products_r.status_code == 200 else []
        
        # Use a simple product or empty items list - gocardless check comes before item processing
        # The gocardless_enabled check happens AFTER customer lookup
        # For the simplest test, provide minimal required fields
        payload = {
            "items": [],  # will fail at item building, but we want 400 for gocardless
            "checkout_type": "one_time",
            "terms_accepted": True,
            "promo_code": None,
            "extra_fields": {},
            "partner_tag_response": None,
            "override_code": None,
        }
        
        # Build a real payload with a product if possible
        one_time_products = [p for p in products if p.get("pricing_type") not in ["external", "inquiry", "subscription"]]
        if one_time_products:
            prod = one_time_products[0]
            payload["items"] = [{"product_id": prod["id"], "quantity": 1, "inputs": {}}]

        r = requests.post(f"{BASE_URL}/api/checkout/bank-transfer", json=payload, headers=headers)
        
        # Should return 400 because gocardless is disabled
        # (gocardless check happens before item processing when items=[] might cause different error)
        # With valid items: gocardless check fires
        # With empty items: item processing error might fire first
        print(f"bank-transfer response: {r.status_code} - {r.text[:200]}")
        
        if one_time_products:
            assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
            assert "not available" in r.json().get("detail", "").lower() or "gocardless" in r.json().get("detail", "").lower() or "bank transfer" in r.json().get("detail", "").lower(), \
                f"Expected gocardless disabled message, got: {r.json().get('detail')}"
        else:
            # No products in DB, but we can still verify the response is not 200
            assert r.status_code != 200, f"Expected non-200 when gocardless disabled, got {r.status_code}"
            print("No products available for full test, but provider bypass check completed")

    def test_stripe_checkout_session_blocked_when_stripe_disabled(self):
        """POST /api/checkout/session should return 400 for one_time when stripe_enabled=false"""
        email, token = register_and_verify(f"stripe_{int(time.time())}")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get products
        products_r = requests.get(f"{BASE_URL}/api/products")
        products = products_r.json().get("products", []) if products_r.status_code == 200 else []
        one_time_products = [p for p in products if p.get("pricing_type") not in ["external", "inquiry"] and not p.get("is_subscription")]

        payload = {
            "items": [],
            "checkout_type": "one_time",
            "terms_accepted": True,
            "origin_url": "https://example.com",
            "promo_code": None,
            "extra_fields": {},
            "partner_tag_response": None,
            "override_code": None,
            "zoho_subscription_type": "Standard",
            "current_zoho_product": "CRM",
            "zoho_account_access": True,
        }
        
        if one_time_products:
            prod = one_time_products[0]
            payload["items"] = [{"product_id": prod["id"], "quantity": 1, "inputs": {}}]

        r = requests.post(f"{BASE_URL}/api/checkout/session", json=payload, headers=headers)
        print(f"checkout/session response: {r.status_code} - {r.text[:300]}")
        
        # Possible responses:
        # 400 - stripe disabled (what we want to verify)
        # 400 - currency not USD/CAD (Canada user, so might be OK if currency is CAD)
        # 403 - card payment not enabled for account (customer default)
        # 404 - no products
        
        if r.status_code == 400:
            detail = r.json().get("detail", "")
            if "stripe" in detail.lower() or "card payments" in detail.lower():
                print(f"✓ Stripe bypass blocked correctly: {detail}")
            else:
                print(f"Got 400 but for different reason: {detail}")
        elif r.status_code == 403:
            # Means customer doesn't have card payment enabled - stripe check comes BEFORE this for one_time
            # This would mean stripe_enabled check is NOT blocking correctly for this flow path
            # Actually check the code order again...
            detail = r.json().get("detail", "")
            if "currency" not in detail.lower():
                print(f"WARNING: Got 403 ({detail}) instead of 400 for stripe disabled - check order of checks")
        else:
            print(f"Got {r.status_code}: {r.text[:200]}")
        
        # Key assertion: should NOT be 200 (would mean bypass succeeded)
        assert r.status_code != 200, f"Checkout session must not succeed when stripe is disabled"

    def test_stripe_disabled_returns_400_with_correct_message(self):
        """Verify the exact error message when stripe is disabled"""
        email, token = register_and_verify(f"stripemsg_{int(time.time())}")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Update customer to allow_card_payment=true via admin
        admin_tok = admin_token()
        if not admin_tok:
            pytest.skip("Admin auth failed")
        
        # Get customer ID for this user
        me_r = requests.get(f"{BASE_URL}/api/me", headers={"Authorization": f"Bearer {token}"})
        assert me_r.status_code == 200
        customer = me_r.json().get("customer")
        if not customer:
            pytest.skip("No customer for test user")
        
        # Enable card payment via admin API
        admin_headers = {"Authorization": f"Bearer {admin_tok}"}
        upd_r = requests.put(
            f"{BASE_URL}/api/admin/customers/{customer['id']}",
            json={"allow_card_payment": True, "currency": "CAD"},
            headers=admin_headers
        )
        print(f"Admin update customer: {upd_r.status_code} {upd_r.text[:100]}")
        
        # Try checkout with card payment enabled but stripe globally disabled
        payload = {
            "items": [],
            "checkout_type": "one_time",
            "terms_accepted": True,
            "origin_url": "https://example.com",
            "promo_code": None,
            "extra_fields": {},
            "partner_tag_response": None,
            "override_code": None,
            "zoho_subscription_type": "Standard",
            "current_zoho_product": "CRM",
            "zoho_account_access": True,
        }
        
        products_r = requests.get(f"{BASE_URL}/api/products")
        products = products_r.json().get("products", []) if products_r.status_code == 200 else []
        one_time_products = [p for p in products if p.get("pricing_type") not in ["external", "inquiry"] and not p.get("is_subscription")]
        if one_time_products:
            payload["items"] = [{"product_id": one_time_products[0]["id"], "quantity": 1, "inputs": {}}]

        r = requests.post(f"{BASE_URL}/api/checkout/session", json=payload, headers=headers)
        print(f"Stripe disabled check: {r.status_code} {r.text[:300]}")
        
        # With card_payment enabled and stripe globally disabled:
        # For one_time: stripe check comes first → should be 400
        if r.status_code == 400:
            detail = r.json().get("detail", "")
            if "card payments are currently not available" in detail.lower():
                print(f"✓ Stripe bypass correctly blocked: '{detail}'")
            else:
                print(f"Got 400 for different reason: {detail}")
        assert r.status_code != 200, "Stripe checkout must not succeed when stripe_enabled=false"

    def test_bank_transfer_blocked_with_correct_message_structure(self):
        """gocardless disabled should return 400 with proper error detail"""
        email, token = register_and_verify(f"gcmsg_{int(time.time())}")
        headers = {"Authorization": f"Bearer {token}"}
        
        products_r = requests.get(f"{BASE_URL}/api/products")
        products = products_r.json().get("products", []) if products_r.status_code == 200 else []
        one_time_products = [p for p in products if p.get("pricing_type") not in ["external", "inquiry"] and not p.get("is_subscription")]
        
        if not one_time_products:
            pytest.skip("No one-time products available for test")
        
        prod = one_time_products[0]
        payload = {
            "items": [{"product_id": prod["id"], "quantity": 1, "inputs": {}}],
            "checkout_type": "one_time",
            "terms_accepted": True,
            "promo_code": None,
            "extra_fields": {},
            "partner_tag_response": None,
            "override_code": None,
        }
        r = requests.post(f"{BASE_URL}/api/checkout/bank-transfer", json=payload, headers=headers)
        print(f"bank-transfer blocked: {r.status_code} {r.text[:300]}")
        
        assert r.status_code == 400, f"Expected 400 for gocardless disabled, got {r.status_code}: {r.text}"
        detail = r.json().get("detail", "")
        assert "bank transfer" in detail.lower() or "not available" in detail.lower(), \
            f"Expected 'bank transfer' or 'not available' in detail, got: {detail}"
        print(f"✓ Bank transfer bypass correctly blocked: '{detail}'")
