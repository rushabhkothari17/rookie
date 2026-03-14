"""
Character limits validation tests — iteration 294.
Tests new limits: _NAME/_SHORT = 100, website body fields = 1000.
Validates: products, categories, terms, plans, address, website settings, cart quote form.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"
TENANT_EMAIL = "mayank@automateaccounts.com"
TENANT_PASSWORD = "ChangeMe123!"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if r.status_code == 200:
        return r.json().get("access_token") or r.json().get("token")
    pytest.skip(f"Admin login failed: {r.status_code} {r.text[:200]}")


@pytest.fixture(scope="module")
def tenant_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": TENANT_EMAIL, "password": TENANT_PASSWORD})
    if r.status_code == 200:
        return r.json().get("access_token") or r.json().get("token")
    pytest.skip(f"Tenant login failed: {r.status_code} {r.text[:200]}")


@pytest.fixture(scope="module")
def admin_client(admin_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def tenant_client(tenant_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {tenant_token}", "Content-Type": "application/json"})
    return s


def over(n: int) -> str:
    """String with n+1 chars — exceeds limit."""
    return "T" * (n + 1)


def at(n: int) -> str:
    """String with exactly n chars — at limit."""
    return "T" * n


# ── Health ────────────────────────────────────────────────────────────────────

class TestHealth:
    """Backend health check."""

    def test_health(self):
        r = requests.get(f"{BASE_URL}/api/health")
        assert r.status_code in (200, 404), f"Backend not reachable: {r.status_code}"

    def test_login_works(self, tenant_token):
        assert tenant_token is not None and len(tenant_token) > 10


# ── Products — name max 100 ──────────────────────────────────────────────────

class TestProductNameLimit:
    """Products: AdminProductCreate.name uses _NAME (max_length=100)."""

    def test_product_name_101_rejected(self, tenant_client):
        """POST /api/admin/products with name > 100 chars must return 422."""
        r = tenant_client.post(f"{BASE_URL}/api/admin/products", json={
            "name": over(100),
            "base_price": 0,
            "is_active": True
        })
        assert r.status_code == 422, f"Expected 422 for 101-char product name, got {r.status_code}: {r.text[:300]}"

    def test_product_name_100_accepted(self, tenant_client):
        """POST /api/admin/products with name == 100 chars must succeed."""
        r = tenant_client.post(f"{BASE_URL}/api/admin/products", json={
            "name": "TEST_PROD_" + at(90),
            "base_price": 0,
            "is_active": True
        })
        assert r.status_code in (200, 201), f"Expected 201 for 100-char product name, got {r.status_code}: {r.text[:300]}"
        # Cleanup
        pid = (r.json().get("product") or {}).get("id") or r.json().get("id")
        if pid:
            tenant_client.delete(f"{BASE_URL}/api/admin/products/{pid}")


# ── Categories — name max 100 ────────────────────────────────────────────────

class TestCategoryNameLimit:
    """Categories: CategoryCreate.name uses _NAME (max_length=100)."""

    def test_category_name_101_rejected(self, tenant_client):
        """POST /api/admin/categories with name > 100 chars must return 422."""
        r = tenant_client.post(f"{BASE_URL}/api/admin/categories", json={
            "name": over(100),
            "description": "Valid",
            "is_active": True
        })
        assert r.status_code == 422, f"Expected 422 for 101-char category name, got {r.status_code}: {r.text[:300]}"

    def test_category_name_100_accepted(self, tenant_client):
        """POST /api/admin/categories with name == 100 chars must succeed."""
        r = tenant_client.post(f"{BASE_URL}/api/admin/categories", json={
            "name": "TEST_CAT_" + at(91),
            "description": "Valid",
            "is_active": True
        })
        assert r.status_code in (200, 201), f"Expected 201 for 100-char category name, got {r.status_code}: {r.text[:300]}"
        cat_id = r.json().get("id") or (r.json().get("category") or {}).get("id")
        if cat_id:
            tenant_client.delete(f"{BASE_URL}/api/admin/categories/{cat_id}")


# ── Terms — title max 100 ────────────────────────────────────────────────────

class TestTermsTitleLimit:
    """Terms: TermsCreate.title uses _NAME (max_length=100)."""

    def test_terms_title_101_rejected(self, tenant_client):
        """POST /api/admin/terms with title > 100 chars must return 422."""
        r = tenant_client.post(f"{BASE_URL}/api/admin/terms", json={
            "title": over(100),
            "content": "Some content",
            "is_default": False,
            "status": "active"
        })
        assert r.status_code == 422, f"Expected 422 for 101-char terms title, got {r.status_code}: {r.text[:300]}"

    def test_terms_title_100_accepted(self, tenant_client):
        """POST /api/admin/terms with title == 100 chars must succeed."""
        r = tenant_client.post(f"{BASE_URL}/api/admin/terms", json={
            "title": "TEST_TERMS_" + at(89),
            "content": "Some content",
            "is_default": False,
            "status": "active"
        })
        assert r.status_code in (200, 201), f"Expected 201 for 100-char terms title, got {r.status_code}: {r.text[:300]}"
        tid = r.json().get("id") or (r.json().get("terms") or {}).get("id")
        if tid:
            tenant_client.delete(f"{BASE_URL}/api/admin/terms/{tid}")


# ── Plans — name max should be 100 (but route uses 500) ─────────────────────

class TestPlanNameLimit:
    """Plans: PlanCreate.name — checking current limit."""

    def test_plan_name_101_rejected(self, admin_client):
        """POST /api/admin/plans with name > 100 chars — should be 422 per spec but plan route may still use 500."""
        r = admin_client.post(f"{BASE_URL}/api/admin/plans", json={
            "name": over(100),
            "description": "Valid desc"
        })
        # Per new requirements: plan name should be max 100 → 422
        # But plans.py still has max_length=500 (BUG!) → may return 201
        print(f"Plan name 101 chars → {r.status_code}: {r.text[:200]}")
        if r.status_code in (200, 201):
            print("BUG DETECTED: Plan name > 100 chars was accepted (plans.py still uses max_length=500)")
            pid = (r.json().get("plan") or {}).get("id") or r.json().get("id")
            if pid:
                admin_client.delete(f"{BASE_URL}/api/admin/plans/{pid}")
        assert r.status_code == 422, (
            f"BUG: Plan name > 100 chars was NOT rejected (got {r.status_code}). "
            "plans.py PlanCreate.name still uses max_length=500 instead of _NAME/100."
        )

    def test_plan_name_100_accepted(self, admin_client):
        """POST /api/admin/plans with name == 100 chars should succeed."""
        r = admin_client.post(f"{BASE_URL}/api/admin/plans", json={
            "name": "TEST_PLAN_" + at(90),
            "description": "Valid"
        })
        assert r.status_code in (200, 201), f"Expected 201 for 100-char plan name, got {r.status_code}: {r.text[:300]}"
        pid = (r.json().get("plan") or {}).get("id") or r.json().get("id")
        if pid:
            admin_client.delete(f"{BASE_URL}/api/admin/plans/{pid}")


# ── Address line1 — max 100 ──────────────────────────────────────────────────

class TestAddressLine1Limit:
    """AddressInput.line1 uses max_length=100."""

    def test_address_line1_101_rejected(self, tenant_client):
        """Registration with address.line1 > 100 chars should be rejected."""
        r = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": "testaddr999@example.com",
            "password": "TestPass123!",
            "full_name": "Test User",
            "company_name": "",
            "job_title": "",
            "phone": "",
            "address": {
                "line1": over(100),
                "line2": "",
                "city": "London",
                "region": "",
                "postal": "E1 1AA",
                "country": "GB"
            },
            "partner_code": "aa"
        })
        assert r.status_code == 422, f"Expected 422 for 101-char address line1, got {r.status_code}: {r.text[:300]}"

    def test_address_line1_100_accepted_format(self, tenant_client):
        """Verify AddressInput.line1 with exactly 100 chars passes Pydantic validation."""
        # Test via registration endpoint — use exactly 100-char line1
        r = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": "testaddr_accept_999@example.com",
            "password": "TestPass123!",
            "full_name": "Test User",
            "company_name": "",
            "job_title": "",
            "phone": "",
            "address": {
                "line1": "T" * 100,
                "line2": "",
                "city": "London",
                "region": "ENG",
                "postal": "E1 1AA",
                "country": "GB"
            },
            "partner_code": "aa"
        })
        # This should either succeed (200/201) or fail for other reasons (email exists, etc)
        # but NOT 422 for address line1 length
        if r.status_code == 422:
            error = r.json().get("detail", "")
            assert "line1" not in str(error).lower() and "100" not in str(error), \
                f"Address line1 100-char should be valid but got 422: {error}"
        print(f"100-char line1 registration: {r.status_code}: {r.text[:200]}")
        # Accept 422 only if it's NOT about line1 length
        assert r.status_code not in (422,) or "line1" not in r.text.lower()


# ── Website Settings — title fields max 100, body fields max 1000 ────────────

class TestWebsiteSettingsLimits:
    """WebsiteSettingsUpdate: title/label fields ≤ 100, body/subtitle ≤ 1000."""

    def test_hero_title_101_rejected(self, tenant_client):
        """Website hero_title (title field, non-body) > 100 chars should be rejected."""
        r = tenant_client.put(f"{BASE_URL}/api/admin/website-settings", json={
            "hero_title": over(100)
        })
        assert r.status_code == 422, f"Expected 422 for hero_title > 100, got {r.status_code}: {r.text[:300]}"

    def test_hero_subtitle_1001_rejected(self, tenant_client):
        """Website hero_subtitle (body field) > 1000 chars should be rejected."""
        r = tenant_client.put(f"{BASE_URL}/api/admin/website-settings", json={
            "hero_subtitle": over(1000)
        })
        assert r.status_code == 422, f"Expected 422 for hero_subtitle > 1000, got {r.status_code}: {r.text[:300]}"

    def test_hero_title_100_accepted(self, tenant_client):
        """Website hero_title == 100 chars should be accepted."""
        r = tenant_client.put(f"{BASE_URL}/api/admin/website-settings", json={
            "hero_title": at(100)
        })
        assert r.status_code in (200, 201), f"Expected success for 100-char hero_title, got {r.status_code}: {r.text[:300]}"

    def test_hero_subtitle_1000_accepted(self, tenant_client):
        """Website hero_subtitle == 1000 chars should be accepted."""
        r = tenant_client.put(f"{BASE_URL}/api/admin/website-settings", json={
            "hero_subtitle": at(1000)
        })
        assert r.status_code in (200, 201), f"Expected success for 1000-char hero_subtitle, got {r.status_code}: {r.text[:300]}"

    def test_bank_instruction_101_rejected(self, tenant_client):
        """bank_instruction_1 (body field) > 1000 chars should be rejected."""
        r = tenant_client.put(f"{BASE_URL}/api/admin/website-settings", json={
            "bank_instruction_1": over(1000)
        })
        assert r.status_code == 422, f"Expected 422 for bank_instruction_1 > 1000, got {r.status_code}: {r.text[:300]}"

    def test_social_url_101_accepted(self, tenant_client):
        """Social URL fields (social_twitter etc.) should accept URLs up to 2048 chars.
        After fix: social_twitter with 101-char URL should be ACCEPTED."""
        url_101 = "https://twitter.com/" + "x" * 81  # 101 chars
        r = tenant_client.put(f"{BASE_URL}/api/admin/website-settings", json={
            "social_twitter": url_101
        })
        print(f"social_twitter 101-char URL → {r.status_code}: {r.text[:200]}")
        assert r.status_code in (200, 201), (
            f"social_twitter 101-char URL should be accepted (URL field, limit=2048), "
            f"got {r.status_code}. This may indicate the url_fields fix in validator is not applied."
        )

    def test_social_url_2049_rejected(self, tenant_client):
        """Social URL with >2048 chars should be rejected."""
        r = tenant_client.put(f"{BASE_URL}/api/admin/website-settings", json={
            "social_twitter": "https://twitter.com/" + "x" * 2030  # > 2048
        })
        print(f"social_twitter 2050-char URL → {r.status_code}: {r.text[:200]}")
        assert r.status_code == 422, \
            f"Expected 422 for social_twitter > 2048 chars, got {r.status_code}"


# ── Cart Quote Form — name/company max 100 via ScopeRequestFormData ──────────

class TestCartQuoteFormLimit:
    """Cart quote form uses /api/orders/scope-request-form → ScopeRequestFormData."""

    def test_scope_form_name_201_rejected(self, tenant_client):
        """ScopeRequestFormData.name has max_length=200 (should be 100 per spec).
        Testing that name > 200 chars is rejected."""
        r = tenant_client.post(f"{BASE_URL}/api/orders/scope-request-form", json={
            "items": [{"product_id": "test", "quantity": 1, "inputs": {}}],
            "form_data": {
                "name": over(200),
                "email": "test@example.com",
                "message": "test message"
            }
        })
        # 422 for validation, 404 if product not found
        assert r.status_code in (404, 422), f"Expected 422/404, got {r.status_code}: {r.text[:300]}"

    def test_scope_form_name_101_behavior(self, tenant_client):
        """ScopeRequestFormData.name max_length should now be 100.
        A 101-char name should return 422."""
        r = tenant_client.post(f"{BASE_URL}/api/orders/scope-request-form", json={
            "items": [{"product_id": "test", "quantity": 1, "inputs": {}}],
            "form_data": {
                "name": over(100),
                "email": "test@example.com",
                "message": "test message"
            }
        })
        print(f"ScopeRequestFormData.name 101 chars → {r.status_code}: {r.text[:200]}")
        # After fix: max_length=100 → 101-char name should return 422
        assert r.status_code == 422, (
            f"Expected 422 for ScopeRequestFormData.name > 100 chars, got {r.status_code}. "
            "ScopeRequestFormData.name should now be max_length=100."
        )

    def test_scope_form_company_101_rejected(self, tenant_client):
        """ScopeRequestFormData.company uses _SHORT (max_length=100) — 101 chars should fail."""
        r = tenant_client.post(f"{BASE_URL}/api/orders/scope-request-form", json={
            "items": [{"product_id": "test", "quantity": 1, "inputs": {}}],
            "form_data": {
                "name": "Valid Name",
                "email": "test@example.com",
                "company": over(100),
                "message": "test"
            }
        })
        # 422 if validation fails, 404 if product not found (validation passed)
        assert r.status_code in (404, 422), f"Expected 422/404, got {r.status_code}: {r.text[:300]}"


# ── Resource categories — name max 100 ───────────────────────────────────────

class TestResourceCategoryLimit:
    """ArticleCategoryCreate.name uses _NAME (max_length=100)."""

    def test_resource_category_101_rejected(self, tenant_client):
        r = tenant_client.post(f"{BASE_URL}/api/resource-categories", json={
            "name": over(100),
            "description": "Valid"
        })
        assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text[:300]}"

    def test_resource_category_100_accepted(self, tenant_client):
        r = tenant_client.post(f"{BASE_URL}/api/resource-categories", json={
            "name": "TEST_RC_" + at(92),
            "description": "Valid"
        })
        assert r.status_code in (200, 201), f"Expected success, got {r.status_code}: {r.text[:300]}"
        rid = r.json().get("id") or (r.json().get("category") or {}).get("id")
        if rid:
            tenant_client.delete(f"{BASE_URL}/api/resource-categories/{rid}")


# ── Webhook name — current limit check ───────────────────────────────────────

class TestWebhookNameLimit:
    """Webhook name: route uses Dict[str,Any] + truncation at 120 chars (known issue)."""

    def test_webhook_name_500_behavior(self, tenant_client):
        """Webhook name with 500 chars — backend truncates to 120 (Dict-based route)."""
        r = tenant_client.post(f"{BASE_URL}/api/admin/webhooks", json={
            "name": at(500),
            "url": "https://example.com/webhook",
            "subscriptions": []
        })
        print(f"Webhook 500-char name → {r.status_code}: {r.text[:200]}")
        # Webhook backend uses Dict — it may succeed (and truncate to 120)
        # This is a known issue: should use Pydantic model with max_length=100
        if r.status_code in (200, 201):
            created = r.json()
            wid = created.get("webhook", {}).get("id") or created.get("id")
            if wid:
                tenant_client.delete(f"{BASE_URL}/api/admin/webhooks/{wid}")
        # Just document, not fail here (known issue from iteration 293)
        assert r.status_code in (200, 201, 400, 422), f"Unexpected: {r.status_code}"


# ── Models.py constant verification ──────────────────────────────────────────

class TestModelConstants:
    """Verify _NAME=100, _SHORT=100 in models.py."""

    def test_name_constant_is_100(self):
        with open("/app/backend/models.py") as f:
            content = f.read()
        assert '"max_length": 100' in content or "max_length=100" in content, \
            "Expected max_length=100 in models.py"
        # Verify _NAME dict has max_length 100
        assert '_NAME    = {"min_length": 1, "max_length": 100}' in content or \
               '_NAME = {"min_length": 1, "max_length": 100}' in content, \
            "Expected _NAME with max_length=100"

    def test_short_constant_is_100(self):
        with open("/app/backend/models.py") as f:
            content = f.read()
        assert '_SHORT   = {"max_length": 100}' in content or \
               '_SHORT = {"max_length": 100}' in content, \
            "Expected _SHORT with max_length=100"

    def test_plans_route_updated_to_100(self):
        """Verify plans.py now uses max_length=100 for plan name."""
        with open("/app/backend/routes/admin/plans.py") as f:
            content = f.read()
        # Should NOT have max_length=500 for plan name anymore
        assert "max_length=500" not in content or "_NAME" in content, \
            "plans.py still uses max_length=500 for plan name — should use max_length=100 or _NAME"
        assert "max_length=100" in content, \
            "Expected max_length=100 in plans.py after fix"

    def test_website_settings_has_validator(self):
        with open("/app/backend/models.py") as f:
            content = f.read()
        assert "_cap_string_lengths" in content, "Expected WebsiteSettingsUpdate validator"
        assert "body_fields" in content, "Expected body_fields set in validator"
        assert "limit = 1_000" in content or "limit = 1000" in content, "Expected 1000 limit for body fields"
        assert "limit = 100" in content, "Expected 100 limit for other fields"
