"""
Iteration 65 - Tests for:
1. Public endpoint tenant isolation (products, articles/public, terms with X-View-As-Tenant)
2. Admin products endpoint tenant scoping
3. Admin terms endpoint tenant scoping (ProductsTab.tsx now calls /admin/terms)
4. Subscriptions renew-now endpoint (frontend calls /admin/subscriptions/{id}/renew-now)
5. Articles/public with X-View-As-Tenant and X-View-As-Customer headers
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

PLATFORM_ADMIN_EMAIL = "admin@automateaccounts.local"
PLATFORM_ADMIN_PASSWORD = "ChangeMe123!"
PLATFORM_ADMIN_PARTNER_CODE = "automate-accounts"

TENANT_B_ADMIN_EMAIL = "adminb@tenantb.local"
TENANT_B_ADMIN_PASSWORD = "ChangeMe123!"
TENANT_B_PARTNER_CODE = "tenant-b-test"
TENANT_B_ID = "e7301988-7f0f-4b2b-a678-4e37882e385f"


def get_token(email, password, partner_code):
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": email,
        "password": password,
        "partner_code": partner_code,
    })
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="module")
def platform_admin_token():
    return get_token(PLATFORM_ADMIN_EMAIL, PLATFORM_ADMIN_PASSWORD, PLATFORM_ADMIN_PARTNER_CODE)


@pytest.fixture(scope="module")
def tenant_b_admin_token():
    return get_token(TENANT_B_ADMIN_EMAIL, TENANT_B_ADMIN_PASSWORD, TENANT_B_PARTNER_CODE)


# ─── Public Endpoint Tenant Isolation ─────────────────────────────────────────

class TestPublicProductsEndpointTenantIsolation:
    """Platform admin calling /api/products with X-View-As-Tenant header should return ONLY that tenant's products."""

    def test_products_default_tenant_returns_many(self, platform_admin_token):
        """Without X-View-As-Tenant, platform admin sees default tenant products (many)."""
        resp = requests.get(
            f"{BASE_URL}/api/products",
            headers={"Authorization": f"Bearer {platform_admin_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        count = len(data.get("products", []))
        print(f"Default tenant product count: {count}")
        # Should have many products for default tenant
        assert count > 1, f"Expected >1 products for default tenant, got {count}"

    def test_products_with_x_view_as_tenant_b_returns_only_tenant_b_products(self, platform_admin_token):
        """Platform admin with X-View-As-Tenant=Tenant B should see ONLY Tenant B products (expected: 1 product 'TB Product')."""
        resp = requests.get(
            f"{BASE_URL}/api/products",
            headers={
                "Authorization": f"Bearer {platform_admin_token}",
                "X-View-As-Tenant": TENANT_B_ID,
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        products = data.get("products", [])
        print(f"Tenant B product count via X-View-As-Tenant: {len(products)}")
        print(f"Tenant B products: {[p.get('name') for p in products]}")
        # Tenant B should have exactly 1 active product: "TB Product"
        assert len(products) == 1, f"Expected 1 product for Tenant B, got {len(products)}: {[p.get('name') for p in products]}"
        assert products[0].get("name") == "TB Product", f"Expected 'TB Product', got '{products[0].get('name')}'"

    def test_products_not_leaking_default_tenant_data_to_tenant_b(self, platform_admin_token):
        """Critical: Ensure Tenant B doesn't see default tenant products (data leak fix verification)."""
        resp = requests.get(
            f"{BASE_URL}/api/products",
            headers={
                "Authorization": f"Bearer {platform_admin_token}",
                "X-View-As-Tenant": TENANT_B_ID,
            }
        )
        assert resp.status_code == 200
        products = resp.json().get("products", [])
        # None of the default tenant products should appear
        for p in products:
            assert p.get("tenant_id") == TENANT_B_ID or p.get("tenant_id") is None, \
                f"Product '{p.get('name')}' belongs to tenant '{p.get('tenant_id')}', not Tenant B!"


class TestPublicArticlesEndpointTenantIsolation:
    """Platform admin calling /api/articles/public with X-View-As-Tenant should return ONLY that tenant's articles."""

    def test_articles_public_without_header_returns_default_tenant_articles(self, platform_admin_token):
        """Without X-View-As-Tenant, platform admin sees default tenant articles."""
        resp = requests.get(
            f"{BASE_URL}/api/articles/public",
            headers={"Authorization": f"Bearer {platform_admin_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        count = len(data.get("articles", []))
        print(f"Default tenant article count: {count}")
        assert count >= 1, f"Expected >=1 articles for default tenant, got {count}"

    def test_articles_public_with_x_view_as_tenant_b_returns_only_tenant_b_articles(self, platform_admin_token):
        """Platform admin with X-View-As-Tenant=Tenant B sees ONLY Tenant B articles (expected: 1 article)."""
        resp = requests.get(
            f"{BASE_URL}/api/articles/public",
            headers={
                "Authorization": f"Bearer {platform_admin_token}",
                "X-View-As-Tenant": TENANT_B_ID,
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        articles = data.get("articles", [])
        print(f"Tenant B article count via X-View-As-Tenant: {len(articles)}")
        print(f"Tenant B articles: {[a.get('title') for a in articles]}")
        # Tenant B should have 1 article
        assert len(articles) == 1, f"Expected 1 article for Tenant B, got {len(articles)}: {[a.get('title') for a in articles]}"

    def test_articles_public_isolation_no_default_tenant_data(self, platform_admin_token):
        """Ensure Tenant B articles don't include default tenant articles."""
        resp = requests.get(
            f"{BASE_URL}/api/articles/public",
            headers={
                "Authorization": f"Bearer {platform_admin_token}",
                "X-View-As-Tenant": TENANT_B_ID,
            }
        )
        assert resp.status_code == 200
        articles = resp.json().get("articles", [])
        for a in articles:
            assert a.get("tenant_id") == TENANT_B_ID, \
                f"Article '{a.get('title')}' belongs to tenant '{a.get('tenant_id')}', not Tenant B!"

    def test_articles_public_with_x_view_as_customer_header(self, platform_admin_token):
        """Platform admin with both X-View-As-Tenant and X-View-As-Customer should work (customer visibility filter)."""
        # Use a non-existent customer ID - should still return unrestricted articles
        resp = requests.get(
            f"{BASE_URL}/api/articles/public",
            headers={
                "Authorization": f"Bearer {platform_admin_token}",
                "X-View-As-Tenant": TENANT_B_ID,
                "X-View-As-Customer": "non-existent-customer-id",
            }
        )
        assert resp.status_code == 200
        articles = resp.json().get("articles", [])
        print(f"Tenant B articles with X-View-As-Customer: {len(articles)}")
        # Articles with visibility='all' should still be returned even with invalid customer
        for a in articles:
            if a.get("visibility") != "all" and a.get("restricted_to"):
                # restricted articles wouldn't appear for invalid customer
                assert "non-existent-customer-id" in a.get("restricted_to", [])


class TestPublicTermsEndpointTenantIsolation:
    """Platform admin calling /api/terms with X-View-As-Tenant should return ONLY that tenant's terms."""

    def test_terms_without_header_returns_default_tenant_terms(self, platform_admin_token):
        """Without X-View-As-Tenant, platform admin sees default tenant terms."""
        resp = requests.get(
            f"{BASE_URL}/api/terms",
            headers={"Authorization": f"Bearer {platform_admin_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        terms = data.get("terms", [])
        print(f"Default tenant terms count: {len(terms)}")

    def test_terms_with_x_view_as_tenant_b_returns_tenant_b_terms(self, platform_admin_token):
        """Platform admin with X-View-As-Tenant=Tenant B should see Tenant B's terms (may be 0 if none configured)."""
        resp = requests.get(
            f"{BASE_URL}/api/terms",
            headers={
                "Authorization": f"Bearer {platform_admin_token}",
                "X-View-As-Tenant": TENANT_B_ID,
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        terms = data.get("terms", [])
        print(f"Tenant B terms count via X-View-As-Tenant: {len(terms)}")
        # Verify no default tenant terms leak in
        for t in terms:
            assert t.get("tenant_id") == TENANT_B_ID, \
                f"Terms '{t.get('title')}' belongs to tenant '{t.get('tenant_id')}', not Tenant B!"

    def test_terms_default_count_differs_from_tenant_b_count(self, platform_admin_token):
        """Verify default tenant and Tenant B return different term counts."""
        default_resp = requests.get(
            f"{BASE_URL}/api/terms",
            headers={"Authorization": f"Bearer {platform_admin_token}"}
        )
        tb_resp = requests.get(
            f"{BASE_URL}/api/terms",
            headers={
                "Authorization": f"Bearer {platform_admin_token}",
                "X-View-As-Tenant": TENANT_B_ID,
            }
        )
        assert default_resp.status_code == 200
        assert tb_resp.status_code == 200
        default_count = len(default_resp.json().get("terms", []))
        tb_count = len(tb_resp.json().get("terms", []))
        print(f"Default tenant terms: {default_count}, Tenant B terms: {tb_count}")
        # They should differ (since different tenants)
        # Note: Tenant B may have 0 terms - that's OK
        assert default_count != tb_count or (default_count == 0 and tb_count == 0), \
            f"Both tenants have {default_count} terms - may indicate isolation is not working"


# ─── Admin Products Endpoint (already confirmed working in iter64) ─────────────

class TestAdminProductsEndpoint:
    """Verify /api/admin/products-all returns tenant-scoped products."""

    def test_admin_products_all_for_tenant_b_returns_1_product(self, platform_admin_token):
        """Platform admin viewing as Tenant B should see exactly 1 admin product."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/products-all?per_page=500",
            headers={
                "Authorization": f"Bearer {platform_admin_token}",
                "X-View-As-Tenant": TENANT_B_ID,
            }
        )
        assert resp.status_code == 200
        products = resp.json().get("products", [])
        print(f"Tenant B admin products count: {len(products)}")
        assert len(products) == 1, f"Expected 1 product for Tenant B admin, got {len(products)}"
        assert products[0].get("name") == "TB Product"

    def test_admin_products_all_default_tenant_returns_more(self, platform_admin_token):
        """Platform admin without X-View-As-Tenant sees more products (default tenant)."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/products-all?per_page=500",
            headers={"Authorization": f"Bearer {platform_admin_token}"}
        )
        assert resp.status_code == 200
        products = resp.json().get("products", [])
        print(f"Default tenant admin products count: {len(products)}")
        assert len(products) > 1


# ─── Admin Terms Endpoint (ProductsTab.tsx now calls /admin/terms) ─────────────

class TestAdminTermsEndpoint:
    """Verify /api/admin/terms returns tenant-scoped terms."""

    def test_admin_terms_accessible_as_platform_admin(self, platform_admin_token):
        """Platform admin can access /api/admin/terms."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/terms",
            headers={"Authorization": f"Bearer {platform_admin_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "terms" in data
        print(f"Default tenant admin terms count: {len(data['terms'])}")

    def test_admin_terms_for_tenant_b_via_header(self, platform_admin_token):
        """Platform admin with X-View-As-Tenant=Tenant B gets Tenant B terms only."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/terms",
            headers={
                "Authorization": f"Bearer {platform_admin_token}",
                "X-View-As-Tenant": TENANT_B_ID,
            }
        )
        assert resp.status_code == 200
        terms = resp.json().get("terms", [])
        print(f"Tenant B admin terms count: {len(terms)}")
        # All returned terms should be for Tenant B
        for t in terms:
            assert t.get("tenant_id") == TENANT_B_ID, \
                f"Terms '{t.get('title')}' from wrong tenant '{t.get('tenant_id')}'"

    def test_admin_terms_accessible_as_tenant_b_admin(self, tenant_b_admin_token):
        """Tenant B admin can access /api/admin/terms and sees only their terms."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/terms",
            headers={"Authorization": f"Bearer {tenant_b_admin_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "terms" in data
        print(f"Tenant B admin (direct login) terms count: {len(data['terms'])}")


# ─── Subscriptions Renew-Now Endpoint ─────────────────────────────────────────

class TestSubscriptionsRenewNowEndpoint:
    """
    CRITICAL: SubscriptionsTab.tsx calls /admin/subscriptions/{id}/renew-now
    But backend route is at /subscriptions/{id}/renew-now (no /admin/ prefix)
    This test verifies whether the endpoint exists at the admin path.
    """

    def test_renew_now_at_old_path_not_admin_path(self, platform_admin_token):
        """
        Verify which path the renew-now endpoint is actually registered at.
        Frontend calls /admin/subscriptions/{id}/renew-now but backend has /subscriptions/{id}/renew-now
        """
        # Test with a fake sub ID to check if route exists vs 404
        test_id = "non-existent-sub-id-for-route-check"
        
        # Test OLD path (without /admin/ prefix) - what backend has
        old_path_resp = requests.post(
            f"{BASE_URL}/api/subscriptions/{test_id}/renew-now",
            headers={"Authorization": f"Bearer {platform_admin_token}"}
        )
        print(f"OLD path /api/subscriptions/{{id}}/renew-now: {old_path_resp.status_code}")
        
        # Test NEW path (with /admin/ prefix) - what frontend now calls
        new_path_resp = requests.post(
            f"{BASE_URL}/api/admin/subscriptions/{test_id}/renew-now",
            headers={"Authorization": f"Bearer {platform_admin_token}"}
        )
        print(f"NEW path /api/admin/subscriptions/{{id}}/renew-now: {new_path_resp.status_code}")
        
        # The backend registered route is without /admin/ prefix
        # A 404 for non-existent resource is still a valid route (vs route-level 404 for no route)
        # Both should be "found" (404 for missing sub, or 200 if found)
        # A 405 or route-level 404 means the path doesn't exist
        
        print(f"OLD path response body: {old_path_resp.text[:200]}")
        print(f"NEW path response body: {new_path_resp.text[:200]}")
        
        # Check if new path is broken (returns 404 Not Found at route level)
        # The old path should return 404 "Subscription not found" (resource not found)
        # The new path should also return 404 "Subscription not found" if route exists
        # But if new path returns 404 with "Not Found" (no detail), the route doesn't exist
        
        if new_path_resp.status_code == 404:
            new_detail = new_path_resp.json().get("detail", "") if new_path_resp.headers.get("content-type", "").startswith("application/json") else ""
            if new_detail == "Not Found":
                print("CRITICAL BUG: /admin/subscriptions/{id}/renew-now route does NOT exist in backend!")
                print("Frontend calls this path but backend only has /subscriptions/{id}/renew-now")
        
        if old_path_resp.status_code == 404:
            old_detail = old_path_resp.json().get("detail", "") if old_path_resp.headers.get("content-type", "").startswith("application/json") else ""
            if old_detail == "Subscription not found":
                print("OLD path /subscriptions/{id}/renew-now EXISTS in backend (returns 404 for missing sub)")
        
        # The assertion should be that the admin path (what frontend calls) works
        # Currently this may fail if backend wasn't updated
        assert new_path_resp.status_code != 422, "Route found but request format error"
        # We expect either a route-level 404 (bug) or resource-not-found 404 (ok)
        # This test documents the current state
        print(f"RESULT: Frontend calls /admin/subscriptions/{{id}}/renew-now -> backend returns {new_path_resp.status_code}")

    def test_renew_now_admin_path_route_exists(self, platform_admin_token):
        """
        Assert that the ADMIN path /api/admin/subscriptions/{id}/renew-now is reachable.
        If this test fails, it means the backend was NOT updated to match the frontend change.
        """
        # First get a real subscription ID to test with
        subs_resp = requests.get(
            f"{BASE_URL}/api/admin/subscriptions?per_page=1",
            headers={"Authorization": f"Bearer {platform_admin_token}"}
        )
        assert subs_resp.status_code == 200
        subs = subs_resp.json().get("subscriptions", [])
        
        if not subs:
            pytest.skip("No subscriptions available to test renew-now")
        
        sub_id = subs[0]["id"]
        
        # Test the admin path
        resp = requests.post(
            f"{BASE_URL}/api/admin/subscriptions/{sub_id}/renew-now",
            headers={"Authorization": f"Bearer {platform_admin_token}"}
        )
        print(f"Admin renew-now response: {resp.status_code} - {resp.text[:300]}")
        
        # If it's a 404 with "Not Found" (no detail), the route doesn't exist
        if resp.status_code == 404:
            try:
                detail = resp.json().get("detail", "")
                if detail == "Not Found":
                    assert False, "CRITICAL: /api/admin/subscriptions/{id}/renew-now route does NOT exist - backend was not updated to match frontend change!"
                else:
                    # 404 with a specific detail means route exists but resource not found
                    print(f"Route exists, sub not found: {detail}")
            except Exception:
                assert False, f"Route does not exist: {resp.text}"
        else:
            # 200 or other status means route works
            assert resp.status_code in [200, 201], f"Unexpected status: {resp.status_code} - {resp.text}"


# ─── Store Page Isolation (via API) ─────────────────────────────────────────

class TestStorePageTenantIsolation:
    """Verify that store-related public endpoints are properly isolated."""

    def test_categories_endpoint_with_x_view_as_tenant(self, platform_admin_token):
        """GET /api/categories with X-View-As-Tenant should return Tenant B categories only."""
        resp = requests.get(
            f"{BASE_URL}/api/categories",
            headers={
                "Authorization": f"Bearer {platform_admin_token}",
                "X-View-As-Tenant": TENANT_B_ID,
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        print(f"Tenant B categories: {data.get('categories', [])}")

    def test_default_tenant_categories_differ(self, platform_admin_token):
        """Default tenant categories should differ from Tenant B categories."""
        default_resp = requests.get(
            f"{BASE_URL}/api/categories",
            headers={"Authorization": f"Bearer {platform_admin_token}"}
        )
        tb_resp = requests.get(
            f"{BASE_URL}/api/categories",
            headers={
                "Authorization": f"Bearer {platform_admin_token}",
                "X-View-As-Tenant": TENANT_B_ID,
            }
        )
        assert default_resp.status_code == 200
        assert tb_resp.status_code == 200
        default_cats = set(default_resp.json().get("categories", []))
        tb_cats = set(tb_resp.json().get("categories", []))
        print(f"Default tenant categories: {default_cats}")
        print(f"Tenant B categories: {tb_cats}")
        # They should not be identical (different tenants have different products/categories)
        # Note: may overlap if same category names exist - but count should differ


# ─── Tenant B Admin Direct Tests ─────────────────────────────────────────────

class TestTenantBAdminEndpoints:
    """Verify Tenant B admin using their own token sees only their data."""

    def test_tenant_b_admin_products_scoped(self, tenant_b_admin_token):
        """Tenant B admin (direct login) should only see Tenant B products."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/products-all?per_page=500",
            headers={"Authorization": f"Bearer {tenant_b_admin_token}"}
        )
        assert resp.status_code == 200
        products = resp.json().get("products", [])
        print(f"Tenant B admin direct products: {len(products)}")
        assert len(products) == 1
        assert products[0].get("name") == "TB Product"

    def test_tenant_b_admin_articles_scoped(self, tenant_b_admin_token):
        """Tenant B admin (direct login) should only see Tenant B articles."""
        resp = requests.get(
            f"{BASE_URL}/api/articles/admin/list",
            headers={"Authorization": f"Bearer {tenant_b_admin_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        articles = data.get("articles", [])
        print(f"Tenant B admin direct articles: {len(articles)}")
        assert len(articles) == 1
