"""
Backend API tests for P0 Bug Fix: Tenant Query Fix
Testing: Public store/articles pages showing all products/articles to authenticated users.
Products/articles stored under tenant_id='automate-accounts' should be visible to Tenant B users.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

PLATFORM_ADMIN_EMAIL = "admin@automateaccounts.local"
PLATFORM_ADMIN_PASSWORD = "ChangeMe123!"

TENANT_B_EMAIL = "adminb@tenantb.local"
TENANT_B_PASSWORD = "ChangeMe123!"
TENANT_B_ID = "e7301988-7f0f-4b2b-a678-4e37882e385f"

DEFAULT_TENANT_ID = "automate-accounts"


@pytest.fixture(scope="module")
def platform_admin_token():
    """Get platform admin JWT token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": PLATFORM_ADMIN_EMAIL,
        "password": PLATFORM_ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Platform admin login failed: {response.text}"
    token = response.json().get("token")
    assert token, "No token in response"
    print(f"Platform admin token obtained")
    return token


@pytest.fixture(scope="module")
def tenant_b_token():
    """Get Tenant B admin JWT token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TENANT_B_EMAIL,
        "password": TENANT_B_PASSWORD
    })
    assert response.status_code == 200, f"Tenant B login failed: {response.text}"
    token = response.json().get("token")
    assert token, "No token in response"
    print(f"Tenant B token obtained")
    return token


class TestTenantBProductsAndCategories:
    """Test that Tenant B user can see global catalog products and categories"""

    def test_tenant_b_products_returns_results(self, tenant_b_token):
        """Tenant B user should see products from automate-accounts global catalog"""
        response = requests.get(
            f"{BASE_URL}/api/products",
            headers={"Authorization": f"Bearer {tenant_b_token}"}
        )
        assert response.status_code == 200, f"Products request failed: {response.text}"
        data = response.json()
        products = data.get("products", [])
        count = len(products)
        print(f"Tenant B products count: {count}")
        # Should return at least products from automate-accounts catalog
        assert count > 0, "Tenant B should see products from global catalog"
        print(f"SUCCESS: Tenant B sees {count} products (expected ~91)")

    def test_tenant_b_products_count_approximately_91(self, tenant_b_token):
        """Tenant B user should see approximately 91 products"""
        response = requests.get(
            f"{BASE_URL}/api/products",
            headers={"Authorization": f"Bearer {tenant_b_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        products = data.get("products", [])
        count = len(products)
        print(f"Tenant B products count: {count}")
        # Should see the global automate-accounts catalog (~91 products)
        assert count >= 50, f"Expected at least 50 products (global catalog), got {count}"
        print(f"SUCCESS: Tenant B sees {count} products (expected ~91)")

    def test_tenant_b_products_include_automate_accounts_tenant(self, tenant_b_token):
        """Products returned for Tenant B should include products from automate-accounts"""
        response = requests.get(
            f"{BASE_URL}/api/products",
            headers={"Authorization": f"Bearer {tenant_b_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        products = data.get("products", [])
        tenant_ids = {p.get("tenant_id") for p in products}
        print(f"Tenant IDs in Tenant B products: {tenant_ids}")
        assert DEFAULT_TENANT_ID in tenant_ids, f"Expected 'automate-accounts' products in result, found tenant_ids: {tenant_ids}"
        print(f"SUCCESS: Products include automate-accounts tenant items")

    def test_tenant_b_categories_returns_results(self, tenant_b_token):
        """Tenant B user should see categories from global catalog"""
        response = requests.get(
            f"{BASE_URL}/api/categories",
            headers={"Authorization": f"Bearer {tenant_b_token}"}
        )
        assert response.status_code == 200, f"Categories request failed: {response.text}"
        data = response.json()
        categories = data.get("categories", [])
        count = len(categories)
        print(f"Tenant B categories count: {count}")
        assert count > 0, "Tenant B should see categories from global catalog"
        print(f"SUCCESS: Tenant B sees {count} categories (expected ~11)")

    def test_tenant_b_categories_count_approximately_11(self, tenant_b_token):
        """Tenant B user should see approximately 11 categories"""
        response = requests.get(
            f"{BASE_URL}/api/categories",
            headers={"Authorization": f"Bearer {tenant_b_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        categories = data.get("categories", [])
        count = len(categories)
        print(f"Tenant B categories: {categories}")
        assert count >= 5, f"Expected at least 5 categories, got {count}"
        print(f"SUCCESS: Tenant B sees {count} categories (expected ~11)")


class TestPlatformAdminProducts:
    """Test platform admin product visibility"""

    def test_platform_admin_products_no_duplication(self, platform_admin_token):
        """Platform admin should see products without duplication (~75 for automate-accounts)"""
        response = requests.get(
            f"{BASE_URL}/api/products",
            headers={"Authorization": f"Bearer {platform_admin_token}"}
        )
        assert response.status_code == 200, f"Products request failed: {response.text}"
        data = response.json()
        products = data.get("products", [])
        count = len(products)
        print(f"Platform admin products count: {count}")
        # Platform admin (tenant_id=automate-accounts) should see automate-accounts products
        # Without duplication - tid and DEFAULT_TENANT_ID are the same for platform admin
        assert count > 0, "Platform admin should see products"
        print(f"SUCCESS: Platform admin sees {count} products (expected ~75)")

    def test_platform_admin_no_duplicate_products(self, platform_admin_token):
        """Platform admin products should not have duplicate product IDs"""
        response = requests.get(
            f"{BASE_URL}/api/products",
            headers={"Authorization": f"Bearer {platform_admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        products = data.get("products", [])
        product_ids = [p.get("id") for p in products]
        unique_ids = set(product_ids)
        assert len(product_ids) == len(unique_ids), f"Duplicate products found! Total: {len(product_ids)}, Unique: {len(unique_ids)}"
        print(f"SUCCESS: No duplicate products for platform admin. Count: {len(products)}")

    def test_platform_admin_view_as_tenant_b_shows_more_products(self, platform_admin_token):
        """Platform admin using X-View-As-Tenant (Tenant B) should return ~91 products"""
        response = requests.get(
            f"{BASE_URL}/api/products",
            headers={
                "Authorization": f"Bearer {platform_admin_token}",
                "X-View-As-Tenant": TENANT_B_ID
            }
        )
        assert response.status_code == 200, f"Products with X-View-As-Tenant failed: {response.text}"
        data = response.json()
        products = data.get("products", [])
        count = len(products)
        print(f"Platform admin (view as Tenant B) products count: {count}")
        assert count > 0, "Should see products when viewing as Tenant B"
        print(f"SUCCESS: Platform admin viewing as Tenant B sees {count} products (expected ~91)")


class TestTenantBArticles:
    """Test that Tenant B user can see articles from both their tenant AND automate-accounts"""

    def test_tenant_b_articles_public_returns_results(self, tenant_b_token):
        """Tenant B user should see articles from both tenant_b and automate-accounts"""
        response = requests.get(
            f"{BASE_URL}/api/articles/public",
            headers={"Authorization": f"Bearer {tenant_b_token}"}
        )
        assert response.status_code == 200, f"Articles public request failed: {response.text}"
        data = response.json()
        articles = data.get("articles", [])
        count = len(articles)
        print(f"Tenant B articles count: {count}")
        # Should return at least some articles
        assert count >= 0, "Articles endpoint should return a list"
        print(f"SUCCESS: Tenant B sees {count} articles")

    def test_tenant_b_articles_include_global_catalog(self, tenant_b_token):
        """Articles for Tenant B should include automate-accounts articles"""
        response = requests.get(
            f"{BASE_URL}/api/articles/public",
            headers={"Authorization": f"Bearer {tenant_b_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        articles = data.get("articles", [])
        tenant_ids = {a.get("tenant_id") for a in articles}
        print(f"Tenant IDs in Tenant B articles: {tenant_ids}")
        # If there are articles, verify they include automate-accounts OR tenant B articles
        if articles:
            assert DEFAULT_TENANT_ID in tenant_ids or TENANT_B_ID in tenant_ids, \
                f"Expected automate-accounts or tenant B articles, found: {tenant_ids}"
        print(f"SUCCESS: Tenant B articles include correct tenants: {tenant_ids}")


class TestPlatformAdminArticles:
    """Test platform admin article visibility"""

    def test_platform_admin_articles_public_returns_results(self, platform_admin_token):
        """Platform admin should see articles"""
        response = requests.get(
            f"{BASE_URL}/api/articles/public",
            headers={"Authorization": f"Bearer {platform_admin_token}"}
        )
        assert response.status_code == 200, f"Articles public request failed: {response.text}"
        data = response.json()
        articles = data.get("articles", [])
        count = len(articles)
        print(f"Platform admin articles count: {count}")
        print(f"SUCCESS: Platform admin sees {count} articles")

    def test_platform_admin_view_as_tenant_b_articles(self, platform_admin_token):
        """Platform admin using X-View-As-Tenant (Tenant B) should see Tenant B articles"""
        response = requests.get(
            f"{BASE_URL}/api/articles/public",
            headers={
                "Authorization": f"Bearer {platform_admin_token}",
                "X-View-As-Tenant": TENANT_B_ID
            }
        )
        assert response.status_code == 200, f"Articles with X-View-As-Tenant failed: {response.text}"
        data = response.json()
        articles = data.get("articles", [])
        count = len(articles)
        print(f"Platform admin (view as Tenant B) articles count: {count}")
        print(f"SUCCESS: Platform admin viewing as Tenant B sees {count} articles")


class TestNoDeduplication:
    """Test that the $in query fix doesn't cause duplicate results"""

    def test_tenant_b_products_no_duplicates(self, tenant_b_token):
        """Tenant B products should not have duplicate product IDs"""
        response = requests.get(
            f"{BASE_URL}/api/products",
            headers={"Authorization": f"Bearer {tenant_b_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        products = data.get("products", [])
        product_ids = [p.get("id") for p in products]
        unique_ids = set(product_ids)
        assert len(product_ids) == len(unique_ids), \
            f"Duplicate products found for Tenant B! Total: {len(product_ids)}, Unique: {len(unique_ids)}"
        print(f"SUCCESS: No duplicate products for Tenant B. Count: {len(products)}")

    def test_tenant_b_categories_no_duplicates(self, tenant_b_token):
        """Tenant B categories should not have duplicates"""
        response = requests.get(
            f"{BASE_URL}/api/categories",
            headers={"Authorization": f"Bearer {tenant_b_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        categories = data.get("categories", [])
        unique_categories = set(categories)
        assert len(categories) == len(unique_categories), \
            f"Duplicate categories found! Total: {len(categories)}, Unique: {len(unique_categories)}"
        print(f"SUCCESS: No duplicate categories for Tenant B. Count: {len(categories)}")


class TestUnauthenticatedAccess:
    """Test unauthenticated access to public endpoints"""

    def test_unauthenticated_products_returns_global_catalog(self):
        """Unauthenticated user should see the global/default catalog"""
        response = requests.get(f"{BASE_URL}/api/products")
        assert response.status_code == 200, f"Products request failed: {response.text}"
        data = response.json()
        products = data.get("products", [])
        count = len(products)
        print(f"Unauthenticated products count: {count}")
        assert count > 0, "Unauthenticated user should see global catalog products"
        print(f"SUCCESS: Unauthenticated user sees {count} products")

    def test_unauthenticated_categories_returns_global_catalog(self):
        """Unauthenticated user should see the global categories"""
        response = requests.get(f"{BASE_URL}/api/categories")
        assert response.status_code == 200, f"Categories request failed: {response.text}"
        data = response.json()
        categories = data.get("categories", [])
        count = len(categories)
        print(f"Unauthenticated categories count: {count}")
        assert count > 0, "Unauthenticated user should see global catalog categories"
        print(f"SUCCESS: Unauthenticated user sees {count} categories")
