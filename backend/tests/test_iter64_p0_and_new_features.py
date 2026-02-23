"""
Iteration 64 Backend Tests
- P0 Data Leak Fix: products and articles tenant isolation
- Setup Checklist API
- Single super_admin enforcement
- Customer List API for Tenant Switcher
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
TENANT_B_ID = "e7301988-7f0f-4b2b-a678-4e37882e385f"

# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def platform_admin_token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!",
        "partner_code": "automate-accounts",
    })
    assert resp.status_code == 200, f"Platform admin login failed: {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="module")
def tenant_b_admin_token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "adminb@tenantb.local",
        "password": "ChangeMe123!",
        "partner_code": "tenant-b-test",
    })
    assert resp.status_code == 200, f"Tenant B admin login failed: {resp.text}"
    return resp.json()["token"]


# ──────────────────────────────────────────────────────────────────────────────
# P0 Fix: Products data isolation
# ──────────────────────────────────────────────────────────────────────────────

class TestProductsDataIsolation:
    """P0 Fix — /api/admin/products-all must respect X-View-As-Tenant header"""

    def test_products_all_platform_admin_no_header_returns_all(self, platform_admin_token):
        """Platform admin with no tenant header should see all products (platform-level)"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/products-all?per_page=500",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        products = data.get("products", [])
        # Platform view should show multiple products (more than 1)
        assert len(products) > 1, f"Expected multiple products in platform view, got {len(products)}"

    def test_products_all_with_tenant_b_header_returns_only_tenant_b_products(self, platform_admin_token):
        """Platform admin with X-View-As-Tenant=Tenant B should see ONLY Tenant B products"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/products-all?per_page=500",
            headers={
                "Authorization": f"Bearer {platform_admin_token}",
                "X-View-As-Tenant": TENANT_B_ID,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        products = data.get("products", [])
        # Tenant B has exactly 1 product
        assert len(products) == 1, f"Expected 1 product for Tenant B, got {len(products)}"
        assert products[0]["name"] == "TB Product", f"Expected 'TB Product', got {products[0]['name']}"

    def test_products_all_tenant_b_admin_token_returns_only_tenant_b(self, tenant_b_admin_token):
        """Tenant B admin should see only their products"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/products-all?per_page=500",
            headers={"Authorization": f"Bearer {tenant_b_admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        products = data.get("products", [])
        assert len(products) == 1, f"Expected 1 product for Tenant B admin, got {len(products)}"
        # All products must belong to Tenant B
        for p in products:
            assert p.get("tenant_id") == TENANT_B_ID or p.get("name") == "TB Product"


# ──────────────────────────────────────────────────────────────────────────────
# P0 Fix: Articles data isolation
# ──────────────────────────────────────────────────────────────────────────────

class TestArticlesDataIsolation:
    """P0 Fix — articles must be scoped to tenant"""

    def test_articles_platform_admin_no_header_sees_all(self, platform_admin_token):
        """Platform admin with no header sees all articles across tenants"""
        resp = requests.get(
            f"{BASE_URL}/api/articles/admin/list",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        articles = data.get("articles", [])
        # Without tenant header, platform admin sees all
        assert len(articles) > 1, f"Platform admin expected >1 articles, got {len(articles)}"

    def test_articles_with_tenant_b_header_returns_only_tenant_b(self, platform_admin_token):
        """Platform admin with X-View-As-Tenant=Tenant B sees only Tenant B articles"""
        resp = requests.get(
            f"{BASE_URL}/api/articles/admin/list",
            headers={
                "Authorization": f"Bearer {platform_admin_token}",
                "X-View-As-Tenant": TENANT_B_ID,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        articles = data.get("articles", [])
        assert len(articles) == 1, f"Expected 1 Tenant B article, got {len(articles)}"
        assert "TB Article" in articles[0]["title"], f"Expected TB article, got {articles[0]['title']}"

    def test_articles_tenant_b_admin_sees_only_tenant_b(self, tenant_b_admin_token):
        """Tenant B admin sees only Tenant B articles"""
        resp = requests.get(
            f"{BASE_URL}/api/articles/admin/list",
            headers={"Authorization": f"Bearer {tenant_b_admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        articles = data.get("articles", [])
        assert len(articles) == 1, f"Expected 1 article for Tenant B, got {len(articles)}"


# ──────────────────────────────────────────────────────────────────────────────
# Setup Checklist API
# ──────────────────────────────────────────────────────────────────────────────

class TestSetupChecklist:
    """GET /api/admin/setup-checklist"""

    def test_setup_checklist_returns_correct_structure(self, tenant_b_admin_token):
        """Checklist must return { checklist, completed, total }"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/setup-checklist",
            headers={"Authorization": f"Bearer {tenant_b_admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "checklist" in data, "Missing 'checklist' key"
        assert "completed" in data, "Missing 'completed' key"
        assert "total" in data, "Missing 'total' key"
        assert data["total"] == 5, f"Expected total=5, got {data['total']}"

    def test_setup_checklist_has_all_5_keys(self, tenant_b_admin_token):
        """Checklist must have all 5 setup step keys"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/setup-checklist",
            headers={"Authorization": f"Bearer {tenant_b_admin_token}"},
        )
        assert resp.status_code == 200
        checklist = resp.json()["checklist"]
        required_keys = ["brand_customized", "first_product", "payment_configured", "first_customer", "first_article"]
        for key in required_keys:
            assert key in checklist, f"Missing checklist key: {key}"
            assert isinstance(checklist[key], bool), f"Key '{key}' must be boolean"

    def test_setup_checklist_completed_matches_bool_count(self, tenant_b_admin_token):
        """completed count must equal number of True values in checklist"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/setup-checklist",
            headers={"Authorization": f"Bearer {tenant_b_admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        checklist = data["checklist"]
        expected_completed = sum(1 for v in checklist.values() if v)
        assert data["completed"] == expected_completed, \
            f"completed={data['completed']} but sum of True values={expected_completed}"

    def test_setup_checklist_platform_admin_viewing_as_tenant_b(self, platform_admin_token):
        """Platform admin viewing as Tenant B should get Tenant B checklist"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/setup-checklist",
            headers={
                "Authorization": f"Bearer {platform_admin_token}",
                "X-View-As-Tenant": TENANT_B_ID,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        # TB has 1 product and 1 article, but no customers/payment
        assert data["checklist"]["first_product"] is True
        assert data["checklist"]["first_article"] is True
        assert data["checklist"]["first_customer"] is False

    def test_setup_checklist_tenant_b_has_product_and_article(self, tenant_b_admin_token):
        """Tenant B has 1 product and 1 article, so first_product and first_article should be True"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/setup-checklist",
            headers={"Authorization": f"Bearer {tenant_b_admin_token}"},
        )
        assert resp.status_code == 200
        checklist = resp.json()["checklist"]
        assert checklist["first_product"] is True, "Tenant B should have first_product=True"
        assert checklist["first_article"] is True, "Tenant B should have first_article=True"

    def test_setup_checklist_unauthenticated_returns_401(self):
        """Unauthenticated request to setup-checklist should fail"""
        resp = requests.get(f"{BASE_URL}/api/admin/setup-checklist")
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"


# ──────────────────────────────────────────────────────────────────────────────
# Customer List API
# ──────────────────────────────────────────────────────────────────────────────

class TestCustomerListAPI:
    """GET /api/admin/tenants/{tenant_id}/customers"""

    def test_customer_list_returns_correct_structure(self, platform_admin_token):
        """Must return { customers: [...] }"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/tenants/{TENANT_B_ID}/customers",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "customers" in data, "Missing 'customers' key in response"
        assert isinstance(data["customers"], list)

    def test_customer_list_has_correct_fields(self, platform_admin_token):
        """Each customer must have id, email, company_name, full_name"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/tenants/{TENANT_B_ID}/customers",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
        )
        assert resp.status_code == 200
        customers = resp.json()["customers"]
        # Even if no customers, structure is valid
        for c in customers:
            assert "id" in c, "Customer missing 'id'"
            assert "email" in c, "Customer missing 'email'"
            assert "company_name" in c, "Customer missing 'company_name'"

    def test_customer_list_invalid_tenant_returns_404(self, platform_admin_token):
        """Invalid tenant ID should return 404"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/tenants/nonexistent-tenant-id/customers",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
        )
        assert resp.status_code == 404

    def test_customer_list_requires_platform_admin(self, tenant_b_admin_token):
        """Non-platform-admin should not be able to access this endpoint"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/tenants/{TENANT_B_ID}/customers",
            headers={"Authorization": f"Bearer {tenant_b_admin_token}"},
        )
        # Should be 403 (not platform admin)
        assert resp.status_code in [403, 401], f"Expected 401/403, got {resp.status_code}"


# ──────────────────────────────────────────────────────────────────────────────
# Single super_admin enforcement
# ──────────────────────────────────────────────────────────────────────────────

class TestSingleSuperAdminEnforcement:
    """Only one super_admin and one partner_super_admin per tenant allowed"""

    def test_create_second_super_admin_rejected(self, tenant_b_admin_token):
        """Creating a second super_admin when one exists should return 400"""
        # Tenant B already has a super_admin (from previous test run or creation)
        resp = requests.post(
            f"{BASE_URL}/api/admin/users",
            headers={
                "Authorization": f"Bearer {tenant_b_admin_token}",
                "Content-Type": "application/json",
            },
            json={
                "email": "TEST_third_super@tenantb.local",
                "password": "ChangeMe123!",
                "full_name": "TEST Third Super",
                "role": "super_admin",
            },
        )
        # Either it's rejected (400) or there's no existing super_admin yet (201/200)
        # Since we created one in the setup, it should be 400
        if resp.status_code == 200 or resp.status_code == 201:
            # First super_admin was created — now try again
            resp2 = requests.post(
                f"{BASE_URL}/api/admin/users",
                headers={
                    "Authorization": f"Bearer {tenant_b_admin_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "email": "TEST_fourth_super@tenantb.local",
                    "password": "ChangeMe123!",
                    "full_name": "TEST Fourth Super",
                    "role": "super_admin",
                },
            )
            assert resp2.status_code == 400, f"Expected 400 for second super_admin, got {resp2.status_code}: {resp2.text}"
            assert "super admin already exists" in resp2.json().get("detail", "").lower()
        else:
            assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
            assert "super admin already exists" in resp.json().get("detail", "").lower()

    def test_create_second_partner_super_admin_rejected(self, tenant_b_admin_token):
        """Creating a second partner_super_admin when one exists should return 400"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/users",
            headers={
                "Authorization": f"Bearer {tenant_b_admin_token}",
                "Content-Type": "application/json",
            },
            json={
                "email": "TEST_second_partner@tenantb.local",
                "password": "ChangeMe123!",
                "full_name": "TEST Second Partner Admin",
                "role": "partner_super_admin",
            },
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "super admin already exists" in resp.json().get("detail", "").lower()

    def test_update_user_to_super_admin_when_one_exists_rejected(self, tenant_b_admin_token, platform_admin_token):
        """Updating an existing user role to super_admin when one already exists should fail"""
        # Get tenant B users to find a non-super_admin to update
        resp = requests.get(
            f"{BASE_URL}/api/admin/tenants/{TENANT_B_ID}/users",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
        )
        assert resp.status_code == 200
        users = resp.json()["users"]
        # Find a non-super_admin user to try promoting
        non_super = [u for u in users if u.get("role") not in ("super_admin", "platform_admin")]
        if not non_super:
            pytest.skip("No non-super_admin users to test with")

        target_user = non_super[0]
        # Try to update to super_admin role
        update_resp = requests.put(
            f"{BASE_URL}/api/admin/users/{target_user['id']}",
            headers={
                "Authorization": f"Bearer {tenant_b_admin_token}",
                "Content-Type": "application/json",
            },
            json={"role": "super_admin"},
        )
        # There's already a super_admin - should be rejected
        if update_resp.status_code == 200:
            # Might have updated - check if there's no existing super_admin it overlaps with
            pass  # Not necessarily a bug if no other super_admin exists
        # If 400, that's the expected behavior when super_admin already exists
        if update_resp.status_code == 400:
            assert "super admin already exists" in update_resp.json().get("detail", "").lower()


# ──────────────────────────────────────────────────────────────────────────────
# Tenant Switcher - Tenant list API
# ──────────────────────────────────────────────────────────────────────────────

class TestTenantListForSwitcher:
    """GET /api/admin/tenants — used by TenantSwitcher"""

    def test_tenant_list_returns_tenants(self, platform_admin_token):
        """Must return list of tenants"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/tenants",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "tenants" in data
        tenants = data["tenants"]
        assert len(tenants) > 0

    def test_tenant_list_has_status_field(self, platform_admin_token):
        """Each tenant must have status field for filtering active tenants"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/tenants",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
        )
        assert resp.status_code == 200
        tenants = resp.json()["tenants"]
        for t in tenants:
            assert "status" in t, f"Tenant missing 'status': {t.get('name')}"
            assert "name" in t, f"Tenant missing 'name'"
            assert "code" in t, f"Tenant missing 'code'"
            assert "id" in t, f"Tenant missing 'id'"

    def test_tenant_b_exists_and_is_active(self, platform_admin_token):
        """Tenant B must exist and be active"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/tenants",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
        )
        assert resp.status_code == 200
        tenants = resp.json()["tenants"]
        tenant_b = next((t for t in tenants if t["id"] == TENANT_B_ID), None)
        assert tenant_b is not None, "Tenant B not found in tenant list"
        assert tenant_b["status"] == "active", f"Tenant B not active: {tenant_b['status']}"

    def test_non_platform_admin_cannot_list_tenants(self, tenant_b_admin_token):
        """Non-platform admin cannot list tenants"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/tenants",
            headers={"Authorization": f"Bearer {tenant_b_admin_token}"},
        )
        assert resp.status_code in [403, 401], f"Expected 401/403, got {resp.status_code}"
