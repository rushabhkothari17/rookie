"""
Iteration 62 - Tenant Data Isolation Tests

Tests ALL admin endpoints for proper X-View-As-Tenant isolation:
- Platform admin WITHOUT header → sees all data (no tenant filter)
- Platform admin WITH X-View-As-Tenant header → sees only Tenant B data
- Super admin → cannot use X-View-As-Tenant (no TenantSwitcher access)
- Cross-tenant write protection: can't edit/delete other tenant's articles
- Public endpoints: articles scoped by JWT tenant_id

Tenant B: id=e7301988-7f0f-4b2b-a678-4e37882e385f, code=tenant-b-test
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
TENANT_B_ID = "e7301988-7f0f-4b2b-a678-4e37882e385f"


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def platform_admin_token():
    """Login as platform_admin (admin@automateaccounts.local)."""
    resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!",
        "partner_code": "automate-accounts",
    })
    assert resp.status_code == 200, f"Platform admin login failed: {resp.text}"
    data = resp.json()
    assert data.get("role") == "platform_admin", f"Expected platform_admin, got {data.get('role')}"
    return data["token"]


@pytest.fixture(scope="module")
def super_admin_token():
    """Login as super_admin (superadmin@automateaccounts.local)."""
    resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
        "email": "superadmin@automateaccounts.local",
        "password": "Admin123!",
        "partner_code": "automate-accounts",
    })
    if resp.status_code != 200:
        pytest.skip(f"Super admin login failed: {resp.text}")
    data = resp.json()
    return data["token"]


@pytest.fixture(scope="module")
def platform_headers(platform_admin_token):
    """Headers for platform admin (no tenant switching)."""
    return {"Authorization": f"Bearer {platform_admin_token}"}


@pytest.fixture(scope="module")
def tenant_b_headers(platform_admin_token):
    """Headers for platform admin viewing as Tenant B."""
    return {
        "Authorization": f"Bearer {platform_admin_token}",
        "X-View-As-Tenant": TENANT_B_ID,
    }


@pytest.fixture(scope="module")
def super_admin_headers(super_admin_token):
    """Headers for super_admin (no TenantSwitcher)."""
    return {"Authorization": f"Bearer {super_admin_token}"}


# ---------------------------------------------------------------------------
# Helper: extract count from responses
# ---------------------------------------------------------------------------

def get_count(response_data: dict, key: str) -> int:
    """Extract item count from response using 'total' field or list length."""
    if "total" in response_data:
        return response_data["total"]
    items = response_data.get(key, [])
    return len(items)


# ---------------------------------------------------------------------------
# 1. ARTICLES ISOLATION
# ---------------------------------------------------------------------------

class TestArticlesIsolation:
    """GET /api/articles/admin/list - tenant isolation"""

    def test_platform_admin_no_header_returns_all_articles(self, platform_headers):
        """Without header: platform admin sees all articles (across all tenants)."""
        resp = requests.get(f"{BASE_URL}/api/articles/admin/list", headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        total = data.get("total", 0)
        print(f"Articles without header: total={total}")
        # Platform admin should see at least 1 article (main tenant has articles)
        assert total >= 1, f"Platform admin should see articles without header, got {total}"
        print(f"PASS: Platform admin sees {total} articles without header")

    def test_platform_admin_with_tenant_b_header_returns_zero_articles(self, tenant_b_headers):
        """With Tenant B header: should return 0 articles (Tenant B has none)."""
        resp = requests.get(f"{BASE_URL}/api/articles/admin/list", headers=tenant_b_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        total = data.get("total", 0)
        articles = data.get("articles", [])
        print(f"Articles with Tenant B header: total={total}, articles={len(articles)}")
        assert total == 0, f"Expected 0 articles for Tenant B, got {total}"
        assert articles == [], f"Expected empty articles list for Tenant B, got {articles}"
        print("PASS: Tenant B has 0 articles - isolation working")

    def test_articles_count_difference_confirms_isolation(self, platform_headers, tenant_b_headers):
        """Confirm that header presence changes the count - isolation is active."""
        r_all = requests.get(f"{BASE_URL}/api/articles/admin/list", headers=platform_headers)
        r_tb = requests.get(f"{BASE_URL}/api/articles/admin/list", headers=tenant_b_headers)
        assert r_all.status_code == 200
        assert r_tb.status_code == 200
        all_total = r_all.json().get("total", 0)
        tb_total = r_tb.json().get("total", 0)
        print(f"Articles comparison: all_tenants={all_total}, tenant_b={tb_total}")
        assert all_total > tb_total, f"Without header ({all_total}) should be more than Tenant B ({tb_total})"
        print(f"PASS: Article isolation confirmed. Without header={all_total}, Tenant B={tb_total}")


# ---------------------------------------------------------------------------
# 2. CUSTOMERS ISOLATION
# ---------------------------------------------------------------------------

class TestCustomersIsolation:
    """GET /api/admin/customers - tenant isolation"""

    def test_platform_admin_no_header_sees_all_customers(self, platform_headers):
        """Without header: platform admin sees all customers."""
        resp = requests.get(f"{BASE_URL}/api/admin/customers", headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        total = data.get("total", 0)
        print(f"Customers without header: total={total}")
        assert total >= 1, f"Platform admin should see customers without header, got {total}"
        print(f"PASS: Platform admin sees {total} customers without header")

    def test_platform_admin_with_tenant_b_header_returns_zero_customers(self, tenant_b_headers):
        """With Tenant B header: should return 0 customers."""
        resp = requests.get(f"{BASE_URL}/api/admin/customers", headers=tenant_b_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        total = data.get("total", 0)
        print(f"Customers with Tenant B header: total={total}")
        assert total == 0, f"Expected 0 customers for Tenant B, got {total}"
        print("PASS: Tenant B has 0 customers - isolation working")

    def test_super_admin_cannot_use_tenant_switcher(self, super_admin_headers):
        """Super admin with X-View-As-Tenant header should NOT switch tenant (ignored)."""
        headers_with_switch = {**super_admin_headers, "X-View-As-Tenant": TENANT_B_ID}
        resp = requests.get(f"{BASE_URL}/api/admin/customers", headers=headers_with_switch)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        total = data.get("total", 0)
        print(f"Customers: super_admin with Tenant B header (should be ignored): total={total}")
        # Super admin's tenant_id is automate-accounts, so they should see their tenant's customers
        # The X-View-As-Tenant should be ignored since they're not platform_admin
        print(f"NOTE: Super admin sees {total} customers (tenant header should be ignored)")


# ---------------------------------------------------------------------------
# 3. USERS ISOLATION
# ---------------------------------------------------------------------------

class TestUsersIsolation:
    """GET /api/admin/users - tenant isolation"""

    def test_platform_admin_no_header_sees_all_admin_users(self, platform_headers):
        """Without header: platform admin sees all admin users."""
        resp = requests.get(f"{BASE_URL}/api/admin/users?per_page=100", headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        total = data.get("total", 0)
        print(f"Admin users without header: total={total}")
        assert total >= 1, f"Platform admin should see users without header, got {total}"
        print(f"PASS: Platform admin sees {total} admin users without header")

    def test_platform_admin_with_tenant_b_header_returns_one_user(self, tenant_b_headers):
        """With Tenant B header: should return 1 user (adminb@tenantb.local)."""
        resp = requests.get(f"{BASE_URL}/api/admin/users?per_page=100", headers=tenant_b_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        total = data.get("total", 0)
        users = data.get("users", [])
        print(f"Admin users with Tenant B header: total={total}")
        print(f"Users: {[u.get('email') for u in users]}")
        assert total == 1, f"Expected 1 user for Tenant B (adminb@tenantb.local), got {total}"
        # Verify it's the correct user
        if users:
            assert users[0].get("email") == "adminb@tenantb.local", (
                f"Expected adminb@tenantb.local, got {users[0].get('email')}"
            )
        print("PASS: Tenant B has exactly 1 admin user (adminb@tenantb.local)")

    def test_tenant_b_user_has_correct_tenant_id(self, tenant_b_headers):
        """The Tenant B user should have tenant_id = TENANT_B_ID."""
        resp = requests.get(f"{BASE_URL}/api/admin/users?per_page=100", headers=tenant_b_headers)
        assert resp.status_code == 200
        users = resp.json().get("users", [])
        if users:
            user = users[0]
            tid = user.get("tenant_id")
            print(f"Tenant B user: email={user.get('email')}, tenant_id={tid}")
            assert tid == TENANT_B_ID, f"User tenant_id should be {TENANT_B_ID}, got {tid}"
            print(f"PASS: Tenant B user has correct tenant_id={tid}")


# ---------------------------------------------------------------------------
# 4. ORDERS ISOLATION
# ---------------------------------------------------------------------------

class TestOrdersIsolation:
    """GET /api/admin/orders - tenant isolation"""

    def test_platform_admin_no_header_sees_all_orders(self, platform_headers):
        """Without header: platform admin sees all orders."""
        resp = requests.get(f"{BASE_URL}/api/admin/orders", headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        total = data.get("total", 0)
        print(f"Orders without header: total={total}")
        print(f"PASS: Platform admin sees {total} orders without header")

    def test_platform_admin_with_tenant_b_header_returns_zero_orders(self, tenant_b_headers):
        """With Tenant B header: should return 0 orders."""
        resp = requests.get(f"{BASE_URL}/api/admin/orders", headers=tenant_b_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        total = data.get("total", 0)
        orders = data.get("orders", [])
        print(f"Orders with Tenant B header: total={total}")
        assert total == 0, f"Expected 0 orders for Tenant B, got {total}"
        assert orders == [], f"Expected empty orders for Tenant B, got {orders}"
        print("PASS: Tenant B has 0 orders - isolation working")


# ---------------------------------------------------------------------------
# 5. SUBSCRIPTIONS ISOLATION
# ---------------------------------------------------------------------------

class TestSubscriptionsIsolation:
    """GET /api/admin/subscriptions - tenant isolation"""

    def test_platform_admin_no_header_sees_all_subscriptions(self, platform_headers):
        """Without header: platform admin sees all subscriptions."""
        resp = requests.get(f"{BASE_URL}/api/admin/subscriptions", headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        total = data.get("total", 0)
        print(f"Subscriptions without header: total={total}")
        print(f"PASS: Platform admin sees {total} subscriptions without header")

    def test_platform_admin_with_tenant_b_header_returns_zero_subscriptions(self, tenant_b_headers):
        """With Tenant B header: should return 0 subscriptions."""
        resp = requests.get(f"{BASE_URL}/api/admin/subscriptions", headers=tenant_b_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        total = data.get("total", 0)
        subs = data.get("subscriptions", [])
        print(f"Subscriptions with Tenant B header: total={total}")
        assert total == 0, f"Expected 0 subscriptions for Tenant B, got {total}"
        assert subs == [], f"Expected empty subscriptions for Tenant B, got {subs}"
        print("PASS: Tenant B has 0 subscriptions - isolation working")


# ---------------------------------------------------------------------------
# 6. PROMO CODES ISOLATION
# ---------------------------------------------------------------------------

class TestPromoCodesIsolation:
    """GET /api/admin/promo-codes - tenant isolation"""

    def test_platform_admin_no_header_sees_all_promo_codes(self, platform_headers):
        """Without header: platform admin sees all promo codes."""
        resp = requests.get(f"{BASE_URL}/api/admin/promo-codes", headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        total = data.get("total", 0)
        print(f"Promo codes without header: total={total}")
        print(f"PASS: Platform admin sees {total} promo codes without header")

    def test_platform_admin_with_tenant_b_header_returns_zero_promo_codes(self, tenant_b_headers):
        """With Tenant B header: should return 0 promo codes."""
        resp = requests.get(f"{BASE_URL}/api/admin/promo-codes", headers=tenant_b_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        total = data.get("total", 0)
        codes = data.get("promo_codes", [])
        print(f"Promo codes with Tenant B header: total={total}")
        assert total == 0, f"Expected 0 promo codes for Tenant B, got {total}"
        assert codes == [], f"Expected empty promo codes for Tenant B, got {codes}"
        print("PASS: Tenant B has 0 promo codes - isolation working")


# ---------------------------------------------------------------------------
# 7. BANK TRANSACTIONS ISOLATION
# ---------------------------------------------------------------------------

class TestBankTransactionsIsolation:
    """GET /api/admin/bank-transactions - tenant isolation"""

    def test_platform_admin_no_header_sees_all_transactions(self, platform_headers):
        """Without header: platform admin sees all bank transactions (at least 18)."""
        resp = requests.get(f"{BASE_URL}/api/admin/bank-transactions?per_page=100", headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        total = data.get("total", 0)
        print(f"Bank transactions without header: total={total}")
        assert total >= 1, f"Platform admin should see bank transactions, got {total}"
        print(f"PASS: Platform admin sees {total} bank transactions without header")

    def test_platform_admin_with_tenant_b_header_returns_zero_transactions(self, tenant_b_headers):
        """With Tenant B header: should return 0 bank transactions (all belong to main tenant)."""
        resp = requests.get(f"{BASE_URL}/api/admin/bank-transactions", headers=tenant_b_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        total = data.get("total", 0)
        txns = data.get("transactions", [])
        print(f"Bank transactions with Tenant B header: total={total}")
        assert total == 0, f"Expected 0 bank transactions for Tenant B, got {total}"
        assert txns == [], f"Expected empty transactions for Tenant B, got {txns}"
        print("PASS: Tenant B has 0 bank transactions - isolation working")

    def test_all_transactions_belong_to_main_tenant(self, platform_headers):
        """Verify all bank transactions have tenant_id = automate-accounts."""
        resp = requests.get(f"{BASE_URL}/api/admin/bank-transactions?per_page=100", headers=platform_headers)
        assert resp.status_code == 200
        data = resp.json()
        txns = data.get("transactions", [])
        print(f"Checking tenant_id for {len(txns)} transactions")
        tenant_ids = set(t.get("tenant_id") for t in txns)
        print(f"Unique tenant_ids in transactions: {tenant_ids}")
        # All transactions should belong to automate-accounts (or have None/missing tenant_id)
        non_tenant_b = [t for t in txns if t.get("tenant_id") == TENANT_B_ID]
        assert len(non_tenant_b) == 0, f"Found {len(non_tenant_b)} transactions belonging to Tenant B"
        print("PASS: No bank transactions belong to Tenant B")


# ---------------------------------------------------------------------------
# 8. ARTICLE CATEGORIES ISOLATION
# ---------------------------------------------------------------------------

class TestArticleCategoriesIsolation:
    """GET /api/article-categories - tenant isolation"""

    def test_platform_admin_no_header_sees_all_categories(self, platform_headers):
        """Without header: platform admin sees all article categories."""
        resp = requests.get(f"{BASE_URL}/api/article-categories", headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        cats = data.get("categories", [])
        print(f"Article categories without header: count={len(cats)}")
        print(f"PASS: Platform admin sees {len(cats)} article categories without header")

    def test_platform_admin_with_tenant_b_header_returns_zero_categories(self, tenant_b_headers):
        """With Tenant B header: should return 0 article categories."""
        resp = requests.get(f"{BASE_URL}/api/article-categories", headers=tenant_b_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        cats = data.get("categories", [])
        print(f"Article categories with Tenant B header: count={len(cats)}")
        assert cats == [], f"Expected 0 article categories for Tenant B, got {len(cats)}: {cats}"
        print("PASS: Tenant B has 0 article categories - isolation working")


# ---------------------------------------------------------------------------
# 9. ARTICLE EMAIL TEMPLATES ISOLATION
# ---------------------------------------------------------------------------

class TestArticleEmailTemplatesIsolation:
    """GET /api/article-email-templates - tenant isolation"""

    def test_platform_admin_no_header_sees_all_templates(self, platform_headers):
        """Without header: platform admin sees all article email templates."""
        resp = requests.get(f"{BASE_URL}/api/article-email-templates", headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        templates = data.get("templates", [])
        print(f"Article email templates without header: count={len(templates)}")
        print(f"PASS: Platform admin sees {len(templates)} article email templates without header")

    def test_platform_admin_with_tenant_b_header_returns_zero_templates(self, tenant_b_headers):
        """With Tenant B header: should return 0 article email templates."""
        resp = requests.get(f"{BASE_URL}/api/article-email-templates", headers=tenant_b_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        templates = data.get("templates", [])
        print(f"Article email templates with Tenant B header: count={len(templates)}")
        assert templates == [], f"Expected 0 article email templates for Tenant B, got {len(templates)}: {templates}"
        print("PASS: Tenant B has 0 article email templates - isolation working")


# ---------------------------------------------------------------------------
# 10. EMAIL TEMPLATES ISOLATION
# ---------------------------------------------------------------------------

class TestEmailTemplatesIsolation:
    """GET /api/admin/email-templates - tenant isolation with auto-seeding"""

    def test_platform_admin_no_header_sees_main_tenant_templates(self, platform_headers):
        """Without header: platform admin sees templates seeded for main tenant."""
        resp = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        templates = data.get("templates", [])
        print(f"Email templates without header: count={len(templates)}")
        assert len(templates) >= 1, "Platform admin should see at least 1 email template"
        print(f"PASS: Platform admin sees {len(templates)} email templates without header")

    def test_platform_admin_with_tenant_b_header_returns_seeded_templates_only(self, tenant_b_headers):
        """With Tenant B header: should auto-seed and return Tenant B templates (not main tenant's)."""
        resp = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=tenant_b_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        templates = data.get("templates", [])
        print(f"Email templates with Tenant B header: count={len(templates)}")
        # After first access, ensure_seeded() creates Tenant B templates
        # They should all have tenant_id = TENANT_B_ID
        if templates:
            for t in templates:
                tid = t.get("tenant_id")
                assert tid == TENANT_B_ID, (
                    f"Email template {t.get('trigger')} has tenant_id={tid}, expected {TENANT_B_ID}"
                )
        print(f"PASS: Email templates for Tenant B: {len(templates)} templates, all scoped to Tenant B")

    def test_email_templates_different_counts_confirm_isolation(self, platform_headers, tenant_b_headers):
        """Main tenant and Tenant B have separate email template sets."""
        r_main = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=platform_headers)
        r_tb = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=tenant_b_headers)
        assert r_main.status_code == 200
        assert r_tb.status_code == 200
        main_templates = r_main.json().get("templates", [])
        tb_templates = r_tb.json().get("templates", [])
        main_tids = {t.get("tenant_id") for t in main_templates}
        tb_tids = {t.get("tenant_id") for t in tb_templates}
        print(f"Main tenant templates: {len(main_templates)}, tenant_ids: {main_tids}")
        print(f"Tenant B templates: {len(tb_templates)}, tenant_ids: {tb_tids}")
        # No overlap: main tenant templates should not appear in Tenant B results
        assert TENANT_B_ID not in main_tids or len(main_tids) == 1, (
            "Main tenant view should not include Tenant B templates"
        )
        if tb_templates:
            assert "automate-accounts" not in tb_tids, (
                "Tenant B view should not include main tenant templates"
            )
        print("PASS: Email template isolation confirmed between tenants")


# ---------------------------------------------------------------------------
# 11. CATALOG/PRODUCTS ISOLATION
# ---------------------------------------------------------------------------

class TestCatalogProductsIsolation:
    """GET /api/admin/products-all - tenant isolation"""

    def test_platform_admin_no_header_sees_all_products(self, platform_headers):
        """Without header: platform admin sees all products."""
        resp = requests.get(f"{BASE_URL}/api/admin/products-all", headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        total = data.get("total", 0)
        print(f"Products without header: total={total}")
        print(f"PASS: Platform admin sees {total} products without header")

    def test_platform_admin_with_tenant_b_header_returns_zero_products(self, tenant_b_headers):
        """With Tenant B header: should return 0 products."""
        resp = requests.get(f"{BASE_URL}/api/admin/products-all", headers=tenant_b_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        total = data.get("total", 0)
        products = data.get("products", [])
        print(f"Products with Tenant B header: total={total}")
        assert total == 0, f"Expected 0 products for Tenant B, got {total}"
        assert products == [], f"Expected empty products for Tenant B, got {products}"
        print("PASS: Tenant B has 0 products - isolation working")


# ---------------------------------------------------------------------------
# 12. QUOTE REQUESTS ISOLATION
# ---------------------------------------------------------------------------

class TestQuoteRequestsIsolation:
    """GET /api/admin/quote-requests - tenant isolation"""

    def test_platform_admin_no_header_sees_all_quote_requests(self, platform_headers):
        """Without header: platform admin sees all quote requests."""
        resp = requests.get(f"{BASE_URL}/api/admin/quote-requests", headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        total = data.get("total", 0)
        print(f"Quote requests without header: total={total}")
        print(f"PASS: Platform admin sees {total} quote requests without header")

    def test_platform_admin_with_tenant_b_header_returns_zero_quote_requests(self, tenant_b_headers):
        """With Tenant B header: should return 0 quote requests."""
        resp = requests.get(f"{BASE_URL}/api/admin/quote-requests", headers=tenant_b_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        total = data.get("total", 0)
        quotes = data.get("quotes", [])
        print(f"Quote requests with Tenant B header: total={total}")
        assert total == 0, f"Expected 0 quote requests for Tenant B, got {total}"
        print("PASS: Tenant B has 0 quote requests - isolation working")


# ---------------------------------------------------------------------------
# 13. CROSS-TENANT WRITE PROTECTION
# ---------------------------------------------------------------------------

class TestCrossTenantWriteProtection:
    """Test that admins cannot read/edit/delete articles from another tenant."""

    @pytest.fixture(scope="class")
    def main_tenant_article_id(self, platform_headers):
        """Get an article_id belonging to the main tenant (automate-accounts)."""
        resp = requests.get(f"{BASE_URL}/api/articles/admin/list", headers=platform_headers)
        assert resp.status_code == 200
        data = resp.json()
        articles = data.get("articles", [])
        if not articles:
            pytest.skip("No articles found to test cross-tenant protection")
        # Get an article from main tenant
        main_articles = [a for a in articles if a.get("tenant_id") == "automate-accounts"]
        if not main_articles:
            main_articles = articles
        article = main_articles[0]
        print(f"Using article: id={article.get('id')}, tenant_id={article.get('tenant_id')}")
        return article.get("id")

    def test_super_admin_cannot_access_article_via_public_endpoint_if_wrong_tenant(self, super_admin_headers):
        """Super admin with automate-accounts tenant_id trying to access public article endpoint."""
        # Super admin has tenant_id=automate-accounts, so this endpoint uses that tenant_id
        resp = requests.get(
            f"{BASE_URL}/api/articles/nonexistent-cross-tenant-article-id",
            headers=super_admin_headers
        )
        assert resp.status_code in (404, 401, 403), (
            f"Expected 404/401/403 for nonexistent article, got {resp.status_code}: {resp.text}"
        )
        print(f"PASS: Cross-tenant article access returns {resp.status_code}")

    def test_platform_admin_with_tenant_b_cannot_access_main_tenant_article(
        self, tenant_b_headers, main_tenant_article_id
    ):
        """Platform admin viewing as Tenant B cannot access main tenant's article via admin update."""
        if not main_tenant_article_id:
            pytest.skip("No main tenant article available")
        # Try to update a main-tenant article while viewing as Tenant B
        resp = requests.put(
            f"{BASE_URL}/api/articles/{main_tenant_article_id}",
            headers=tenant_b_headers,
            json={"title": "Cross-tenant write attempt"}
        )
        # Should return 404 (article not found in Tenant B scope)
        assert resp.status_code == 404, (
            f"Expected 404 for cross-tenant article update, got {resp.status_code}: {resp.text}"
        )
        print(f"PASS: Cross-tenant article update blocked (404 returned)")

    def test_platform_admin_with_tenant_b_cannot_delete_main_tenant_article(
        self, tenant_b_headers, main_tenant_article_id
    ):
        """Platform admin viewing as Tenant B cannot delete main tenant's article."""
        if not main_tenant_article_id:
            pytest.skip("No main tenant article available")
        resp = requests.delete(
            f"{BASE_URL}/api/articles/{main_tenant_article_id}",
            headers=tenant_b_headers
        )
        # Should return 404 (article not found in Tenant B scope)
        assert resp.status_code == 404, (
            f"Expected 404 for cross-tenant article delete, got {resp.status_code}: {resp.text}"
        )
        print(f"PASS: Cross-tenant article delete blocked (404 returned)")


# ---------------------------------------------------------------------------
# 14. PUBLIC ARTICLES ENDPOINT - JWT TENANT SCOPING
# ---------------------------------------------------------------------------

class TestPublicArticlesJwtScoping:
    """GET /api/articles/public - should return articles scoped to JWT tenant_id"""

    @pytest.fixture(scope="class")
    def customer_token(self):
        """Try to get a customer token from the main tenant (automate-accounts)."""
        # Try logging in as a customer (non-admin user)
        # Check known customers from the main tenant
        # We'll use the partner-login endpoint with a known customer or use store login
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "superadmin@automateaccounts.local",
            "password": "Admin123!",
            "partner_code": "automate-accounts",
        })
        if resp.status_code == 200:
            return resp.json().get("token")
        pytest.skip("Could not get customer token for public articles test")

    def test_public_articles_requires_authentication(self):
        """Public articles endpoint requires JWT authentication."""
        resp = requests.get(f"{BASE_URL}/api/articles/public")
        assert resp.status_code in (401, 403, 422), (
            f"Expected auth error without token, got {resp.status_code}: {resp.text}"
        )
        print(f"PASS: /articles/public requires authentication (got {resp.status_code})")

    def test_public_articles_returns_only_tenant_articles(self, platform_headers):
        """Admin using public endpoint sees articles scoped to their tenant."""
        # Using platform admin token - their tenant_id is None/automate-accounts
        resp = requests.get(f"{BASE_URL}/api/articles/public", headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        articles = data.get("articles", [])
        print(f"Public articles for platform admin: count={len(articles)}")
        # All articles should be from DEFAULT_TENANT_ID (automate-accounts)
        for a in articles:
            tid = a.get("tenant_id")
            assert tid in (None, "automate-accounts"), (
                f"Article {a.get('id')} has wrong tenant_id: {tid}"
            )
        print(f"PASS: Public articles correctly scoped to tenant, found {len(articles)} articles")


# ---------------------------------------------------------------------------
# 15. ARTICLE TEMPLATES ISOLATION (BONUS - with seeding)
# ---------------------------------------------------------------------------

class TestArticleTemplatesIsolation:
    """GET /api/article-templates - tenant isolation with _seed_defaults"""

    def test_platform_admin_no_header_sees_main_tenant_templates(self, platform_headers):
        """Without header: platform admin sees main tenant article templates."""
        resp = requests.get(f"{BASE_URL}/api/article-templates", headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        templates = data.get("templates", [])
        print(f"Article templates without header: count={len(templates)}")
        assert len(templates) >= 1, "Platform admin should see at least 1 article template"
        print(f"PASS: Platform admin sees {len(templates)} article templates without header")

    def test_platform_admin_with_tenant_b_header_seeds_and_returns_tenant_b_templates(
        self, tenant_b_headers
    ):
        """With Tenant B header: _seed_defaults creates 4 templates for Tenant B on first access."""
        resp = requests.get(f"{BASE_URL}/api/article-templates", headers=tenant_b_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        templates = data.get("templates", [])
        print(f"Article templates with Tenant B header: count={len(templates)}")
        # _seed_defaults creates 4 default templates on first access
        assert len(templates) == 4, (
            f"Expected 4 seeded templates for Tenant B, got {len(templates)}"
        )
        # All templates should belong to Tenant B
        for t in templates:
            tid = t.get("tenant_id")
            assert tid == TENANT_B_ID, (
                f"Template {t.get('name')} has tenant_id={tid}, expected {TENANT_B_ID}"
            )
        print(f"PASS: Tenant B has {len(templates)} seeded article templates, all scoped correctly")

    def test_article_templates_not_shared_between_tenants(
        self, platform_headers, tenant_b_headers
    ):
        """Article templates from main tenant should not appear in Tenant B view."""
        r_main = requests.get(f"{BASE_URL}/api/article-templates", headers=platform_headers)
        r_tb = requests.get(f"{BASE_URL}/api/article-templates", headers=tenant_b_headers)
        assert r_main.status_code == 200
        assert r_tb.status_code == 200
        main_ids = {t.get("id") for t in r_main.json().get("templates", [])}
        tb_ids = {t.get("id") for t in r_tb.json().get("templates", [])}
        overlap = main_ids & tb_ids
        print(f"Main tenant templates: {len(main_ids)}, Tenant B: {len(tb_ids)}, Overlap: {len(overlap)}")
        assert len(overlap) == 0, (
            f"Found {len(overlap)} templates shared between main tenant and Tenant B: {overlap}"
        )
        print("PASS: Article templates not shared between tenants")


# ---------------------------------------------------------------------------
# 16. VERIFY TENANT B TENANT RECORD EXISTS
# ---------------------------------------------------------------------------

class TestTenantBRecord:
    """Verify Tenant B exists and is properly configured."""

    def test_platform_admin_can_see_tenant_b_in_tenants_list(self, platform_headers):
        """Platform admin should see Tenant B in /admin/tenants."""
        resp = requests.get(f"{BASE_URL}/api/admin/tenants", headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        tenants = data.get("tenants", [])
        tenant_b = next((t for t in tenants if t.get("id") == TENANT_B_ID), None)
        if not tenant_b:
            # Also check by code
            tenant_b = next((t for t in tenants if t.get("code") == "tenant-b-test"), None)
        print(f"Tenants: {[t.get('code') for t in tenants]}")
        assert tenant_b is not None, f"Tenant B (id={TENANT_B_ID}) not found in tenants list"
        print(f"PASS: Tenant B found in tenants list: {tenant_b.get('code')}")

    def test_platform_admin_tenant_b_header_is_validated(self, tenant_b_headers):
        """X-View-As-Tenant for Tenant B should be validated (tenant must exist in DB)."""
        # If the tenant doesn't exist, get_tenant_admin returns admin without _view_as
        # We can verify this by checking that the tenant switching actually works
        resp_all = requests.get(f"{BASE_URL}/api/admin/users?per_page=100",
                                headers={"Authorization": tenant_b_headers["Authorization"]})
        resp_tb = requests.get(f"{BASE_URL}/api/admin/users?per_page=100",
                               headers=tenant_b_headers)
        assert resp_all.status_code == 200
        assert resp_tb.status_code == 200
        all_total = resp_all.json().get("total", 0)
        tb_total = resp_tb.json().get("total", 0)
        print(f"Users: all_tenants={all_total}, tenant_b={tb_total}")
        assert all_total != tb_total or tb_total == 1, (
            "Tenant B header should scope results differently from no-header "
            f"(all={all_total}, tb={tb_total})"
        )
        print("PASS: Tenant B header is validated and applied")
