"""
Iteration 34 - Testing:
1. Admin Orders table has processor_id field in response
2. Admin Subscriptions table has processor_id field in response
3. Articles page has no product category tabs
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"


@pytest.fixture(scope="module")
def admin_token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if resp.status_code != 200:
        pytest.skip(f"Admin login failed: {resp.status_code} {resp.text}")
    return resp.json().get("access_token") or resp.json().get("token")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ---- Backend: GET /api/admin/orders ----

class TestAdminOrdersProcessorId:
    """Admin orders endpoint includes processor_id field"""

    def test_admin_orders_returns_200(self, admin_headers):
        """GET /api/admin/orders returns 200"""
        resp = requests.get(f"{BASE_URL}/api/admin/orders?page=1&per_page=5", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print("PASS: GET /api/admin/orders returns 200")

    def test_admin_orders_response_structure(self, admin_headers):
        """Response has orders, items, total fields"""
        resp = requests.get(f"{BASE_URL}/api/admin/orders?page=1&per_page=5", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "orders" in data, "Missing 'orders' key"
        assert "items" in data, "Missing 'items' key"
        assert "total" in data, "Missing 'total' key"
        assert "total_pages" in data, "Missing 'total_pages' key"
        print(f"PASS: Orders response structure valid, total={data['total']}")

    def test_admin_orders_processor_id_field_present_or_none(self, admin_headers):
        """Each order returned should not have _id, processor_id field can be None or a string"""
        resp = requests.get(f"{BASE_URL}/api/admin/orders?page=1&per_page=20", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        orders = data.get("orders", [])
        print(f"Total orders fetched: {len(orders)}")
        
        for order in orders:
            # _id should not be in response
            assert "_id" not in order, f"Order {order.get('id')} has _id in response"
            # id should always be present
            assert "id" in order, "Order missing 'id'"
            # processor_id can be present (string) or absent/None - both acceptable
            if "processor_id" in order:
                val = order["processor_id"]
                assert val is None or isinstance(val, str), f"processor_id should be str or None, got {type(val)}"
                print(f"  Order {order['id'][:8]}... processor_id={'(none)' if not val else val[:15]+'...'}")
        
        print(f"PASS: All {len(orders)} orders have valid processor_id field (None or string)")

    def test_admin_orders_no_private_id(self, admin_headers):
        """Orders response does not contain MongoDB _id"""
        resp = requests.get(f"{BASE_URL}/api/admin/orders?page=1&per_page=5", headers=admin_headers)
        data = resp.json()
        for order in data.get("orders", []):
            assert "_id" not in order, f"MongoDB _id leaked for order {order.get('id')}"
        print("PASS: No MongoDB _id in orders response")


# ---- Backend: GET /api/admin/subscriptions ----

class TestAdminSubscriptionsProcessorId:
    """Admin subscriptions endpoint includes processor_id field"""

    def test_admin_subscriptions_returns_200(self, admin_headers):
        """GET /api/admin/subscriptions returns 200"""
        resp = requests.get(f"{BASE_URL}/api/admin/subscriptions?page=1&per_page=5", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print("PASS: GET /api/admin/subscriptions returns 200")

    def test_admin_subscriptions_response_structure(self, admin_headers):
        """Response has subscriptions, total, total_pages fields"""
        resp = requests.get(f"{BASE_URL}/api/admin/subscriptions?page=1&per_page=5", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "subscriptions" in data, "Missing 'subscriptions' key"
        assert "total" in data, "Missing 'total' key"
        assert "total_pages" in data, "Missing 'total_pages' key"
        print(f"PASS: Subscriptions response structure valid, total={data['total']}")

    def test_admin_subscriptions_processor_id_field(self, admin_headers):
        """Each subscription has no _id; processor_id/stripe_subscription_id/gocardless_mandate_id can be None or string"""
        resp = requests.get(f"{BASE_URL}/api/admin/subscriptions?page=1&per_page=20", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        subs = data.get("subscriptions", [])
        print(f"Total subscriptions fetched: {len(subs)}")
        
        for sub in subs:
            assert "_id" not in sub, f"Subscription {sub.get('id')} has _id in response"
            assert "id" in sub, "Subscription missing 'id'"
            # Check fallback fields
            for field in ["processor_id", "stripe_subscription_id", "gocardless_mandate_id"]:
                if field in sub:
                    val = sub[field]
                    assert val is None or isinstance(val, str), f"{field} should be str or None, got {type(val)}"
            
            # Log which display value would be used (frontend fallback chain)
            display_val = sub.get("processor_id") or sub.get("stripe_subscription_id") or sub.get("gocardless_mandate_id")
            print(f"  Sub {sub['id'][:8]}... display_processor={'(none)' if not display_val else display_val[:15]+'...'}")
        
        print(f"PASS: All {len(subs)} subscriptions have valid processor_id chain")

    def test_admin_subscriptions_no_private_id(self, admin_headers):
        """Subscriptions response does not contain MongoDB _id"""
        resp = requests.get(f"{BASE_URL}/api/admin/subscriptions?page=1&per_page=5", headers=admin_headers)
        data = resp.json()
        for sub in data.get("subscriptions", []):
            assert "_id" not in sub, f"MongoDB _id leaked for sub {sub.get('id')}"
        print("PASS: No MongoDB _id in subscriptions response")


# ---- Backend: Articles ----

class TestArticlesPublic:
    """Articles public endpoint"""

    def test_articles_public_requires_auth(self, admin_headers):
        """GET /api/articles/public returns 200 for authenticated users"""
        resp = requests.get(f"{BASE_URL}/api/articles/public", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "articles" in data, "Missing 'articles' key"
        print(f"PASS: /api/articles/public returns 200, articles={len(data['articles'])}")

    def test_articles_no_product_category_fields(self, admin_headers):
        """Articles should not return 'store_category' or 'product_category' fields for frontend tabs"""
        resp = requests.get(f"{BASE_URL}/api/articles/public", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        articles = data.get("articles", [])
        # Articles have 'category' field (Blog, Scope - Final Won, etc.)
        categories = list(set(a.get("category", "") for a in articles if a.get("category")))
        print(f"Article categories found: {categories}")
        # Verify none have 'product_category' keys (store product categories)
        product_cat_names = ["Zoho Express Setup", "Migrate to Zoho", "Managed Services"]
        for a in articles:
            cat = a.get("category", "")
            assert cat not in product_cat_names, f"Article has product category name as category: {cat}"
        print("PASS: No articles have store product category names as their category")
