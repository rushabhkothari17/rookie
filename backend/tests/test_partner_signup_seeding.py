"""
Backend tests for partner signup and default data seeding (Iteration 284).
Tests:
- Address validation: register-partner fails with 400 if address provided but region missing
- Address validation: register-partner succeeds with all address fields including region
- verify-partner-email creates partner_subscription and partner_order in DB
- Product currency uses partner's base_currency (not hardcoded GBP)
- Product placeholder content fields are set (tagline, description_long, bullets, faqs, card_description)
- Website settings defaults: register_subtitle and signup_form_subtitle are non-empty
- Email from name: website_settings.email_from_name = org name
- Email templates: order_placed and subscription_created have is_enabled=true
- Favicon upload endpoint: POST /api/admin/upload-favicon
- GET /api/admin/settings includes favicon_url
- GET /api/settings/public includes favicon_url
"""

import os
import time
import pytest
import requests
import pymongo
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "automate_accounts")

# Test credentials
ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"
ADMIN_PARTNER_CODE = "automate-accounts"

# Test partner details (unique per run)
TEST_EMAIL = f"test_partner_seed_{int(time.time())}@example.com"
TEST_ORG_NAME = f"TestOrg {int(time.time())}"
TEST_CURRENCY = "EUR"  # Use EUR to verify currency seeding (not GBP, not default USD)

_partner_code: str = ""


@pytest.fixture(scope="module")
def client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def admin_token(client):
    """Get platform admin token."""
    res = client.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
    })
    if res.status_code == 200:
        token = res.json().get("token")
        client.headers.update({"Authorization": f"Bearer {token}"})
        return token
    pytest.skip(f"Admin login failed: {res.status_code} {res.text}")


@pytest.fixture(scope="module")
def db():
    """MongoDB connection."""
    mongo_client = pymongo.MongoClient(MONGO_URL)
    yield mongo_client[DB_NAME]
    mongo_client.close()


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Address validation – missing region should fail
# ─────────────────────────────────────────────────────────────────────────────

class TestAddressValidation:
    """Address validation for register-partner endpoint."""

    def test_register_partner_fails_missing_region(self, client):
        """POST /api/auth/register-partner: if address provided but region missing, return 400."""
        res = client.post(f"{BASE_URL}/api/auth/register-partner", json={
            "name": TEST_ORG_NAME + "_bad",
            "admin_name": "Test Admin",
            "admin_email": f"badaddr_{int(time.time())}@example.com",
            "admin_password": "TestPass123!",
            "base_currency": "USD",
            "address": {
                "line1": "123 Main St",
                "city": "London",
                "postal": "SW1A 1AA",
                "country": "GB",
                # region is intentionally missing
            },
        })
        assert res.status_code == 400, f"Expected 400 but got {res.status_code}: {res.text}"
        data = res.json()
        detail = data.get("detail", "")
        assert "region" in detail.lower() or "address" in detail.lower(), f"Expected region/address error but got: {detail}"
        print(f"PASS: Address validation - missing region returns 400: {detail}")

    def test_register_partner_fails_missing_city(self, client):
        """POST /api/auth/register-partner: if address provided but city missing, return 400."""
        res = client.post(f"{BASE_URL}/api/auth/register-partner", json={
            "name": TEST_ORG_NAME + "_nocity",
            "admin_name": "Test Admin",
            "admin_email": f"nocity_{int(time.time())}@example.com",
            "admin_password": "TestPass123!",
            "base_currency": "USD",
            "address": {
                "line1": "123 Main St",
                "region": "ENG",
                "postal": "SW1A 1AA",
                "country": "GB",
                # city is intentionally missing
            },
        })
        assert res.status_code == 400, f"Expected 400 but got {res.status_code}: {res.text}"
        data = res.json()
        detail = data.get("detail", "")
        assert "city" in detail.lower() or "address" in detail.lower(), f"Expected city/address error but got: {detail}"
        print(f"PASS: Address validation - missing city returns 400: {detail}")

    def test_register_partner_succeeds_with_all_address_fields(self, client):
        """POST /api/auth/register-partner: succeeds if all address fields including region provided."""
        global TEST_EMAIL, TEST_ORG_NAME, TEST_CURRENCY
        res = client.post(f"{BASE_URL}/api/auth/register-partner", json={
            "name": TEST_ORG_NAME,
            "admin_name": "Test Admin EUR",
            "admin_email": TEST_EMAIL,
            "admin_password": "TestPass123!",
            "base_currency": TEST_CURRENCY,
            "address": {
                "line1": "123 Test Street",
                "line2": "Suite 1",
                "city": "Amsterdam",
                "region": "NH",
                "postal": "1011 AB",
                "country": "NL",
            },
        })
        assert res.status_code == 200, f"Expected 200 but got {res.status_code}: {res.text}"
        data = res.json()
        assert "message" in data, f"Expected 'message' in response but got: {data}"
        print(f"PASS: Address validation - complete address returns 200: {data['message']}")

    def test_register_partner_succeeds_without_address(self, client):
        """POST /api/auth/register-partner: succeeds if no address provided at all."""
        res = client.post(f"{BASE_URL}/api/auth/register-partner", json={
            "name": TEST_ORG_NAME + "_noaddr",
            "admin_name": "Test Admin NoAddr",
            "admin_email": f"noaddr_{int(time.time())}@example.com",
            "admin_password": "TestPass123!",
            "base_currency": "USD",
        })
        assert res.status_code == 200, f"Expected 200 but got {res.status_code}: {res.text}"
        print("PASS: Address validation - no address returns 200")


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: Verify partner email and check seeded data
# ─────────────────────────────────────────────────────────────────────────────

class TestPartnerVerifyAndSeeding:
    """Verify partner email and check DB seeded data."""

    def test_verify_partner_email(self, client, db):
        """Get OTP from DB and verify the partner email."""
        global _partner_code
        # Get the verification code from the DB
        pending = db.pending_partner_registrations.find_one({"email": TEST_EMAIL}, {"_id": 0})
        assert pending is not None, f"No pending registration found for {TEST_EMAIL}"
        code = pending.get("verification_code")
        assert code, f"No verification code found for {TEST_EMAIL}"
        print(f"Got verification code: {code}")

        res = client.post(f"{BASE_URL}/api/auth/verify-partner-email", json={
            "email": TEST_EMAIL,
            "code": code,
        })
        assert res.status_code == 200, f"Expected 200 but got {res.status_code}: {res.text}"
        data = res.json()
        assert "partner_code" in data, f"Expected 'partner_code' in response but got: {data}"
        _partner_code = data["partner_code"]
        print(f"PASS: Partner email verified. Partner code: {_partner_code}")

    def test_partner_subscription_created(self, db):
        """After verify-partner-email, a partner_subscription should be created in DB."""
        global _partner_code
        if not _partner_code:
            pytest.skip("Partner code not available - previous test may have failed")

        tenant = db.tenants.find_one({"code": _partner_code}, {"_id": 0, "id": 1, "name": 1})
        assert tenant, f"Tenant not found with code: {_partner_code}"
        tenant_id = tenant["id"]

        sub = db.partner_subscriptions.find_one({"partner_id": tenant_id}, {"_id": 0})
        assert sub is not None, f"No partner_subscription found for tenant {tenant_id}"
        
        # Verify key fields
        assert sub.get("status") == "active", f"Expected status 'active' but got: {sub.get('status')}"
        assert sub.get("partner_name") == TEST_ORG_NAME, f"Expected partner_name '{TEST_ORG_NAME}' but got: {sub.get('partner_name')}"
        assert sub.get("subscription_number", "").startswith("PS-"), f"Expected PS- prefix but got: {sub.get('subscription_number')}"
        assert sub.get("payment_method") == "manual", f"Expected payment_method 'manual'"
        print(f"PASS: Partner subscription created: {sub.get('subscription_number')}")

    def test_partner_order_created(self, db):
        """After verify-partner-email, a partner_order should be created in DB."""
        global _partner_code
        if not _partner_code:
            pytest.skip("Partner code not available")

        tenant = db.tenants.find_one({"code": _partner_code}, {"_id": 0, "id": 1})
        assert tenant, f"Tenant not found with code: {_partner_code}"
        tenant_id = tenant["id"]

        order = db.partner_orders.find_one({"partner_id": tenant_id}, {"_id": 0})
        assert order is not None, f"No partner_order found for tenant {tenant_id}"
        
        # Verify key fields
        assert order.get("status") == "paid", f"Expected status 'paid' but got: {order.get('status')}"
        assert order.get("partner_name") == TEST_ORG_NAME, f"Expected partner_name '{TEST_ORG_NAME}'"
        assert order.get("order_number", "").startswith("PO-"), f"Expected PO- prefix but got: {order.get('order_number')}"
        print(f"PASS: Partner order created: {order.get('order_number')}")

    def test_product_uses_base_currency(self, db):
        """New partner's sample product should use their selected base_currency (EUR), not hardcoded GBP."""
        global _partner_code
        if not _partner_code:
            pytest.skip("Partner code not available")

        tenant = db.tenants.find_one({"code": _partner_code}, {"_id": 0, "id": 1})
        assert tenant, f"Tenant not found with code: {_partner_code}"
        tenant_id = tenant["id"]

        product = db.products.find_one({"tenant_id": tenant_id}, {"_id": 0})
        assert product is not None, f"No product found for tenant {tenant_id}"
        
        product_currency = product.get("currency")
        assert product_currency == TEST_CURRENCY, f"Expected currency '{TEST_CURRENCY}' but got: {product_currency}"
        print(f"PASS: Product currency is {product_currency} (matches base_currency {TEST_CURRENCY})")

    def test_product_placeholder_content_fields(self, db):
        """New partner's sample product should have tagline, description_long, bullets, faqs, card_description."""
        global _partner_code
        if not _partner_code:
            pytest.skip("Partner code not available")

        tenant = db.tenants.find_one({"code": _partner_code}, {"_id": 0, "id": 1})
        assert tenant, f"Tenant not found with code: {_partner_code}"
        tenant_id = tenant["id"]

        product = db.products.find_one({"tenant_id": tenant_id}, {"_id": 0})
        assert product is not None, f"No product found for tenant {tenant_id}"

        # Check all required placeholder fields
        assert product.get("tagline"), f"tagline is empty: {product.get('tagline')}"
        assert product.get("description_long"), f"description_long is empty: {product.get('description_long')}"
        assert product.get("bullets"), f"bullets is empty: {product.get('bullets')}"
        assert product.get("faqs"), f"faqs is empty: {product.get('faqs')}"
        assert product.get("card_description"), f"card_description is empty: {product.get('card_description')}"
        
        print(f"PASS: Product placeholder fields set:")
        print(f"  tagline: {product['tagline'][:50]}...")
        print(f"  description_long: {product['description_long'][:50]}...")
        print(f"  bullets: {product['bullets'][:50]}...")
        print(f"  faqs: {product['faqs'][:50]}...")
        print(f"  card_description: {product['card_description'][:50]}...")

    def test_website_settings_register_subtitle(self, db):
        """New partner's website_settings should have non-empty register_subtitle."""
        global _partner_code
        if not _partner_code:
            pytest.skip("Partner code not available")

        tenant = db.tenants.find_one({"code": _partner_code}, {"_id": 0, "id": 1})
        assert tenant, f"Tenant not found with code: {_partner_code}"
        tenant_id = tenant["id"]

        ws = db.website_settings.find_one({"tenant_id": tenant_id}, {"_id": 0})
        assert ws is not None, f"No website_settings found for tenant {tenant_id}"
        
        register_subtitle = ws.get("register_subtitle", "")
        assert register_subtitle, f"register_subtitle is empty: {register_subtitle}"
        print(f"PASS: register_subtitle set: {register_subtitle}")

    def test_website_settings_signup_form_subtitle(self, db):
        """New partner's website_settings should have non-empty signup_form_subtitle."""
        global _partner_code
        if not _partner_code:
            pytest.skip("Partner code not available")

        tenant = db.tenants.find_one({"code": _partner_code}, {"_id": 0, "id": 1})
        assert tenant, f"Tenant not found with code: {_partner_code}"
        tenant_id = tenant["id"]

        ws = db.website_settings.find_one({"tenant_id": tenant_id}, {"_id": 0})
        assert ws is not None, f"No website_settings found for tenant {tenant_id}"
        
        signup_form_subtitle = ws.get("signup_form_subtitle", "")
        assert signup_form_subtitle, f"signup_form_subtitle is empty: {signup_form_subtitle}"
        print(f"PASS: signup_form_subtitle set: {signup_form_subtitle}")

    def test_website_settings_email_from_name_is_org_name(self, db):
        """New partner's website_settings.email_from_name should be set to their org name."""
        global _partner_code
        if not _partner_code:
            pytest.skip("Partner code not available")

        tenant = db.tenants.find_one({"code": _partner_code}, {"_id": 0, "id": 1})
        assert tenant, f"Tenant not found with code: {_partner_code}"
        tenant_id = tenant["id"]

        ws = db.website_settings.find_one({"tenant_id": tenant_id}, {"_id": 0})
        assert ws is not None, f"No website_settings found for tenant {tenant_id}"
        
        email_from_name = ws.get("email_from_name", "")
        assert email_from_name == TEST_ORG_NAME, f"Expected email_from_name '{TEST_ORG_NAME}' but got: '{email_from_name}'"
        print(f"PASS: email_from_name is '{email_from_name}' (matches org name)")

    def test_email_templates_order_placed_enabled(self, db):
        """New partner should have order_placed email template with is_enabled=true."""
        global _partner_code
        if not _partner_code:
            pytest.skip("Partner code not available")

        tenant = db.tenants.find_one({"code": _partner_code}, {"_id": 0, "id": 1})
        assert tenant, f"Tenant not found with code: {_partner_code}"
        tenant_id = tenant["id"]

        template = db.email_templates.find_one({"tenant_id": tenant_id, "trigger": "order_placed"}, {"_id": 0})
        assert template is not None, f"No order_placed template found for tenant {tenant_id}"
        
        is_enabled = template.get("is_enabled")
        assert is_enabled is True, f"Expected is_enabled=True for order_placed but got: {is_enabled}"
        print(f"PASS: order_placed template is_enabled={is_enabled}")

    def test_email_templates_subscription_created_enabled(self, db):
        """New partner should have subscription_created email template with is_enabled=true."""
        global _partner_code
        if not _partner_code:
            pytest.skip("Partner code not available")

        tenant = db.tenants.find_one({"code": _partner_code}, {"_id": 0, "id": 1})
        assert tenant, f"Tenant not found with code: {_partner_code}"
        tenant_id = tenant["id"]

        template = db.email_templates.find_one({"tenant_id": tenant_id, "trigger": "subscription_created"}, {"_id": 0})
        assert template is not None, f"No subscription_created template found for tenant {tenant_id}"
        
        is_enabled = template.get("is_enabled")
        assert is_enabled is True, f"Expected is_enabled=True for subscription_created but got: {is_enabled}"
        print(f"PASS: subscription_created template is_enabled={is_enabled}")


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: Favicon endpoints
# ─────────────────────────────────────────────────────────────────────────────

class TestFaviconEndpoints:
    """Tests for favicon upload and retrieval endpoints."""

    @pytest.fixture(scope="class")
    def admin_client(self):
        session = requests.Session()
        # Login as platform admin
        login_res = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
        })
        if login_res.status_code != 200:
            pytest.skip(f"Admin login failed: {login_res.status_code}")
        token = login_res.json().get("token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        return session

    def test_admin_settings_has_favicon_url_field(self, admin_client):
        """GET /api/admin/settings should return response that includes favicon_url field."""
        res = admin_client.get(f"{BASE_URL}/api/admin/settings")
        assert res.status_code == 200, f"Expected 200 but got {res.status_code}: {res.text}"
        data = res.json()
        settings = data.get("settings", {})
        assert "favicon_url" in settings, f"favicon_url field not found in admin settings: {list(settings.keys())}"
        print(f"PASS: GET /api/admin/settings includes favicon_url field (value: {settings.get('favicon_url', '(empty)')})")

    def test_public_settings_has_favicon_url_field(self, admin_client):
        """GET /api/settings/public should include favicon_url field."""
        res = admin_client.get(f"{BASE_URL}/api/settings/public")
        assert res.status_code == 200, f"Expected 200 but got {res.status_code}: {res.text}"
        data = res.json()
        settings = data.get("settings", {})
        assert "favicon_url" in settings, f"favicon_url field not found in public settings: {list(settings.keys())}"
        print(f"PASS: GET /api/settings/public includes favicon_url field (value: {settings.get('favicon_url', '(empty)')})")

    def test_upload_favicon_endpoint(self, admin_client):
        """POST /api/admin/upload-favicon should accept an image file and return favicon_url."""
        # Create a minimal 1x1 PNG in memory (base64-encoded)
        import base64
        # Minimal valid PNG: 1x1 pixel transparent PNG
        png_b64 = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhf"
            "DwAChwGA60e6kgAAAABJRU5ErkJggg=="
        )
        png_bytes = base64.b64decode(png_b64)
        
        # Upload without Content-Type application/json header for multipart
        headers = {k: v for k, v in admin_client.headers.items() if k.lower() != "content-type"}
        res = requests.post(
            f"{BASE_URL}/api/admin/upload-favicon",
            files={"file": ("favicon.png", png_bytes, "image/png")},
            headers=headers,
        )
        assert res.status_code == 200, f"Expected 200 but got {res.status_code}: {res.text}"
        data = res.json()
        assert "favicon_url" in data, f"Expected 'favicon_url' in response but got: {data}"
        favicon_url = data["favicon_url"]
        assert favicon_url.startswith("data:image/"), f"Expected data: URL but got: {favicon_url[:50]}"
        print(f"PASS: POST /api/admin/upload-favicon returns favicon_url (data:image/...)")

    def test_upload_favicon_validates_file_size(self, admin_client):
        """POST /api/admin/upload-favicon should reject files larger than 512KB."""
        # Create a large fake file (>512KB)
        large_data = b"x" * (512 * 1024 + 1)
        
        headers = {k: v for k, v in admin_client.headers.items() if k.lower() != "content-type"}
        res = requests.post(
            f"{BASE_URL}/api/admin/upload-favicon",
            files={"file": ("big.png", large_data, "image/png")},
            headers=headers,
        )
        assert res.status_code == 413, f"Expected 413 but got {res.status_code}: {res.text}"
        print(f"PASS: POST /api/admin/upload-favicon rejects files > 512KB with 413")

    def test_upload_favicon_validates_file_type(self, admin_client):
        """POST /api/admin/upload-favicon should reject non-image files."""
        headers = {k: v for k, v in admin_client.headers.items() if k.lower() != "content-type"}
        res = requests.post(
            f"{BASE_URL}/api/admin/upload-favicon",
            files={"file": ("test.pdf", b"fake pdf content", "application/pdf")},
            headers=headers,
        )
        assert res.status_code == 400, f"Expected 400 but got {res.status_code}: {res.text}"
        print(f"PASS: POST /api/admin/upload-favicon rejects non-image files with 400")
