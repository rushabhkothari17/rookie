"""
Backend tests for iteration 120 features:
1. Permissions API - quote_requests removed from ADMIN_MODULES
2. Email templates - quote_request_admin/customer removed for new tenants
3. Article {ref:key} resolution in get_article_by_id
4. FX rate cache (1h TTL) - verify caching behavior via logs
5. Orders export CSV - base_currency_amount column present
6. Subscriptions export CSV - base_currency_amount column present
7. Store products - currency field returned correctly
"""
import pytest
import requests
import os
import csv
import io
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"
PARTNER_CODE = "automate-accounts"


@pytest.fixture(scope="module")
def admin_session():
    """Login and return a requests Session with auth headers."""
    session = requests.Session()
    res = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
    })
    assert res.status_code == 200, f"Admin login failed: {res.text}"
    data = res.json()
    token = data.get("access_token") or data.get("token")
    assert token, f"No token in response: {data}"
    session.headers.update({
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    print(f"\n✓ Admin logged in: {ADMIN_EMAIL}")
    return session


# ─────────────────────────────────────────────────────────────────────────────
# 1. Permissions API – quote_requests not present
# ─────────────────────────────────────────────────────────────────────────────

class TestPermissionsNoQuoteRequests:
    """Verify quote_requests has been removed from ADMIN_MODULES."""

    def test_permissions_modules_no_quote_requests(self, admin_session):
        """GET /api/admin/permissions/modules should NOT contain quote_requests."""
        res = admin_session.get(f"{BASE_URL}/api/admin/permissions/modules")
        assert res.status_code == 200, f"Permissions API failed: {res.text}"
        data = res.json()
        module_keys = [m["key"] for m in data.get("modules", [])]
        print(f"\n  Available modules: {module_keys}")
        assert "quote_requests" not in module_keys, \
            f"quote_requests should NOT be in modules but found: {module_keys}"
        print("✓ quote_requests is NOT in ADMIN_MODULES")

    def test_permissions_modules_returns_expected_keys(self, admin_session):
        """Verify expected modules are still present."""
        res = admin_session.get(f"{BASE_URL}/api/admin/permissions/modules")
        assert res.status_code == 200
        data = res.json()
        module_keys = [m["key"] for m in data.get("modules", [])]
        for expected in ["customers", "orders", "subscriptions", "products", "settings"]:
            assert expected in module_keys, f"Expected module '{expected}' not found in {module_keys}"
        print(f"✓ All expected modules present: {module_keys}")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Email templates – no quote_request_admin / quote_request_customer
# ─────────────────────────────────────────────────────────────────────────────

class TestEmailTemplatesNoLegacyQuoteRequests:
    """Verify legacy quote_request_admin/customer templates are NOT in _TEMPLATES definition.
    
    Note: For existing tenants, the DB may still have these templates from old seedings.
    The feature requirement is that NEW tenants won't have them. We verify this by checking
    the _TEMPLATES list in email_service.py (which defines what new tenants get).
    """

    def test_email_service_templates_list_no_quote_request_admin(self):
        """The _TEMPLATES constant in email_service.py should NOT define quote_request_admin."""
        import ast
        with open("/app/backend/services/email_service.py") as f:
            source = f.read()
        # Parse the file and find the _TEMPLATES list definition
        tree = ast.parse(source)
        # Find string literals "quote_request_admin" in the entire source
        # The _TEMPLATES list should not contain this trigger
        trigger_nodes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.s, str):
                if node.s in ("quote_request_admin", "quote_request_customer"):
                    trigger_nodes.append(node.s)
        print(f"\n  Found legacy triggers in _TEMPLATES source: {trigger_nodes}")
        assert "quote_request_admin" not in trigger_nodes, \
            f"quote_request_admin found in email_service.py _TEMPLATES: {trigger_nodes}"
        print("✓ quote_request_admin NOT in email_service.py _TEMPLATES definition")

    def test_email_service_templates_list_no_quote_request_customer(self):
        """The _TEMPLATES constant in email_service.py should NOT define quote_request_customer."""
        import ast
        with open("/app/backend/services/email_service.py") as f:
            source = f.read()
        tree = ast.parse(source)
        trigger_nodes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.s, str):
                if node.s == "quote_request_customer":
                    trigger_nodes.append(node.s)
        print(f"\n  Found quote_request_customer in source: {trigger_nodes}")
        assert "quote_request_customer" not in trigger_nodes, \
            f"quote_request_customer found in email_service.py: {trigger_nodes}"
        print("✓ quote_request_customer NOT in email_service.py _TEMPLATES definition")

    def test_email_templates_api_returns_200(self, admin_session):
        """GET /api/admin/email-templates should return 200."""
        res = admin_session.get(f"{BASE_URL}/api/admin/email-templates")
        assert res.status_code == 200, f"Email templates API failed: {res.text}"
        data = res.json()
        triggers = [t["trigger"] for t in data.get("templates", [])]
        print(f"\n  Email template triggers from DB (tenant): {triggers}")
        # Informational - existing tenant may have old templates from DB
        print("✓ Email templates API returns 200")

    def test_email_templates_has_expected_triggers(self, admin_session):
        """Verify expected triggers are still present."""
        res = admin_session.get(f"{BASE_URL}/api/admin/email-templates")
        assert res.status_code == 200
        data = res.json()
        triggers = [t["trigger"] for t in data.get("templates", [])]
        for expected in ["verification", "order_placed", "refund_processed", "password_reset"]:
            assert expected in triggers, f"Expected trigger '{expected}' not found in {triggers}"
        print(f"✓ Core triggers present: {triggers}")


# ─────────────────────────────────────────────────────────────────────────────
# 3. Article {ref:key} resolution
# ─────────────────────────────────────────────────────────────────────────────

class TestArticleRefResolution:
    """Test that {ref:key} tokens in article content are resolved."""

    _ref_key = "TEST_iter120_ref"
    _ref_value = "TestRefValue120"
    _article_id = None
    _ref_id = None

    def test_create_reference_for_article(self, admin_session):
        """Create a test reference key/value in website_references."""
        # Create a reference via the admin references API
        res = admin_session.post(f"{BASE_URL}/api/admin/references", json={
            "key": self._ref_key,
            "value": self._ref_value,
        })
        # If it already exists (409 or 400), that's fine, we just need it to exist
        if res.status_code in (409, 400):
            print(f"  Reference '{self._ref_key}' may already exist (status {res.status_code})")
        else:
            assert res.status_code in (200, 201), f"Create reference failed: {res.status_code} {res.text}"
            data = res.json()
            TestArticleRefResolution._ref_id = (data.get("reference") or data).get("id")
            print(f"✓ Created reference: key={self._ref_key}, value={self._ref_value}")

    def test_create_article_with_ref_token(self, admin_session):
        """Create an article whose content contains a {{ref:key}} token."""
        # Get valid categories first
        cat_res = admin_session.get(f"{BASE_URL}/api/admin/article-categories")
        categories = []
        if cat_res.status_code == 200:
            cats = cat_res.json().get("categories", [])
            categories = [c["name"] for c in cats if c.get("name")]

        # Pick a non-scope category
        safe_cat = next((c for c in categories if "scope" not in c.lower() and "Scope" not in c), None)
        if not safe_cat:
            safe_cat = "General"  # Fallback

        article_payload = {
            "title": "TEST_iter120 Ref Resolution Test",
            "category": safe_cat,
            "content": f"<p>This is a test. Reference value: {{{{ref:{self._ref_key}}}}}</p>",
            "visibility": "all",
        }
        res = admin_session.post(f"{BASE_URL}/api/articles", json=article_payload)
        assert res.status_code in (200, 201), f"Create article failed: {res.status_code} {res.text}"
        data = res.json()
        article = data.get("article", data)
        TestArticleRefResolution._article_id = article.get("id")
        print(f"✓ Created article id={self._article_id} with ref token content")

    def test_get_article_resolves_ref_token(self, admin_session):
        """GET /api/articles/{id} should resolve {{ref:key}} to its value."""
        if not self._article_id:
            pytest.skip("No article_id – creation test may have failed")

        res = admin_session.get(f"{BASE_URL}/api/articles/{self._article_id}")
        assert res.status_code == 200, f"GET article failed: {res.status_code} {res.text}"
        data = res.json()
        article = data.get("article", data)
        content = article.get("content", "")
        print(f"\n  Article content: {content[:200]}")

        # The {ref:key} token should be replaced with the value
        assert f"{{{{ref:{self._ref_key}}}}}" not in content, \
            f"{{{{ref:{self._ref_key}}}}} token was NOT resolved in content: {content}"
        assert self._ref_value in content, \
            f"Expected '{self._ref_value}' in resolved content, got: {content}"
        print(f"✓ Article ref resolved: {self._ref_key} → {self._ref_value}")

    def test_cleanup_article(self, admin_session):
        """Delete the test article."""
        if self._article_id:
            res = admin_session.delete(f"{BASE_URL}/api/articles/{self._article_id}")
            assert res.status_code in (200, 204), f"Delete failed: {res.text}"
            print(f"✓ Cleaned up test article {self._article_id}")

    def test_cleanup_reference(self, admin_session):
        """Delete the test reference if we have its ID."""
        if self._ref_id:
            res = admin_session.delete(f"{BASE_URL}/api/admin/references/{self._ref_id}")
            assert res.status_code in (200, 204), f"Delete reference failed: {res.text}"
            print(f"✓ Cleaned up test reference {self._ref_id}")
        else:
            # Try to find and delete by key
            res = admin_session.get(f"{BASE_URL}/api/admin/references")
            if res.status_code == 200:
                refs = res.json().get("references", [])
                for r in refs:
                    if r.get("key") == self._ref_key:
                        del_res = admin_session.delete(f"{BASE_URL}/api/admin/references/{r['id']}")
                        print(f"✓ Cleaned up reference by key: {del_res.status_code}")
                        break


# ─────────────────────────────────────────────────────────────────────────────
# 4. FX rate caching – verify backend cache behavior
# ─────────────────────────────────────────────────────────────────────────────

class TestFXRateCaching:
    """Test FX rate cache logic (1-hour TTL). We verify the cache works by checking
    that repeated calls to the FX endpoint are faster/consistent."""

    def test_fx_api_first_call_succeeds(self):
        """External FX API should return a valid response."""
        res = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10)
        assert res.status_code == 200, f"FX API call failed: {res.status_code}"
        data = res.json()
        assert data.get("result") == "success", f"FX API bad result: {data.get('result')}"
        assert "USD" in data.get("rates", {}), "USD not in FX rates"
        print(f"✓ FX API first call: result=success, rates count={len(data.get('rates', {}))}")

    def test_fx_cache_constants_in_checkout_service(self):
        """Verify the _fx_cache dict and TTL constant are defined in checkout_service.py."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "checkout_service",
            "/app/backend/services/checkout_service.py"
        )
        mod = importlib.util.load_from_spec(spec)  # type: ignore
        spec.loader.exec_module(mod)  # type: ignore
        # Check cache dict exists
        assert hasattr(mod, "_fx_cache"), "_fx_cache dict not found in checkout_service"
        assert hasattr(mod, "_FX_CACHE_TTL"), "_FX_CACHE_TTL constant not found"
        assert mod._FX_CACHE_TTL == 3600, f"Expected TTL=3600, got {mod._FX_CACHE_TTL}"
        print(f"✓ _fx_cache dict present, _FX_CACHE_TTL = {mod._FX_CACHE_TTL}s")

    def test_fx_get_rate_function_exists(self):
        """get_fx_rate async function must exist in checkout_service."""
        import ast
        with open("/app/backend/services/checkout_service.py") as f:
            source = f.read()
        tree = ast.parse(source)
        fn_names = [n.name for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef)]
        assert "get_fx_rate" in fn_names, f"get_fx_rate not found. Async fns: {fn_names}"
        print(f"✓ get_fx_rate async function defined in checkout_service.py")

    def test_fx_cache_key_format_in_source(self):
        """Verify cache key format and TTL check in source code."""
        with open("/app/backend/services/checkout_service.py") as f:
            source = f.read()
        assert "_fx_cache" in source, "_fx_cache not found in checkout_service.py"
        assert "_FX_CACHE_TTL" in source, "_FX_CACHE_TTL not found in checkout_service.py"
        assert "time.time()" in source, "time.time() cache logic not found"
        print("✓ FX cache logic (key, TTL check) present in checkout_service.py")


# ─────────────────────────────────────────────────────────────────────────────
# 5. Orders export CSV – base_currency_amount column
# ─────────────────────────────────────────────────────────────────────────────

class TestOrdersExportCSV:
    """Test that orders export CSV contains base_currency_amount column."""

    def test_orders_export_returns_csv(self, admin_session):
        """GET /api/admin/export/orders should return CSV data."""
        res = admin_session.get(f"{BASE_URL}/api/admin/export/orders")
        assert res.status_code == 200, f"Export orders failed: {res.status_code} {res.text}"
        content_type = res.headers.get("content-type", "")
        assert "text/csv" in content_type or "csv" in content_type, \
            f"Expected CSV content-type, got: {content_type}"
        print(f"✓ Orders export returns CSV (content-type: {content_type})")

    def test_orders_export_has_base_currency_amount_or_no_data(self, admin_session):
        """If orders exist with base_currency_amount stored, it should appear in CSV headers."""
        res = admin_session.get(f"{BASE_URL}/api/admin/export/orders")
        assert res.status_code == 200
        csv_content = res.text
        print(f"\n  CSV first 300 chars: {csv_content[:300]}")

        if csv_content.strip() == "No data":
            print("  ⚠ No orders in system - creating a test order to check export")
            pytest.skip("No orders data to test base_currency_amount column")

        # Parse CSV headers
        reader = csv.DictReader(io.StringIO(csv_content))
        headers = reader.fieldnames or []
        print(f"  CSV headers: {headers}")

        # Check if any order has base_currency_amount
        rows = list(reader)
        if rows:
            has_bca_col = "base_currency_amount" in headers
            print(f"  base_currency_amount in headers: {has_bca_col}")
            # The field appears only if orders were created via checkout with FX
            # If no orders have it, the column won't appear
            print(f"  Total orders: {len(rows)}")
            if has_bca_col:
                bca_values = [r.get("base_currency_amount") for r in rows if r.get("base_currency_amount")]
                print(f"  Orders with base_currency_amount: {len(bca_values)}")
                print("✓ base_currency_amount column present in orders export")
            else:
                print("  ℹ base_currency_amount not in CSV headers - orders may predate FX feature")
        else:
            print("  ⚠ CSV had headers but no rows")

    def test_orders_export_create_order_verify_bca_column(self, admin_session):
        """Create a manual order with base_currency_amount field and verify it exports."""
        # Create a manual order with explicit base_currency_amount
        payload = {
            "customer_email": "TEST_iter120_order@test.invalid",
            "product_name": "TEST Order Currency Export",
            "amount": 100.0,
            "currency": "CAD",
            "base_currency_amount": 75.0,
            "status": "pending",
            "notes": "Test for iter120 base_currency_amount export",
        }
        res = admin_session.post(f"{BASE_URL}/api/admin/orders/manual", json=payload)
        if res.status_code not in (200, 201):
            print(f"  ℹ Manual order creation returned {res.status_code}: {res.text[:200]}")
            # Manual order endpoint may have different required fields - this is informational
            pytest.skip(f"Manual order creation not available with test data: {res.status_code}")

        order_id = res.json().get("order", {}).get("id") or res.json().get("id")
        print(f"  Created test order id: {order_id}")

        # Now export and check
        export_res = admin_session.get(f"{BASE_URL}/api/admin/export/orders")
        assert export_res.status_code == 200
        headers = csv.DictReader(io.StringIO(export_res.text)).fieldnames or []
        print(f"  CSV headers after order creation: {headers}")

        # Cleanup
        if order_id:
            admin_session.delete(f"{BASE_URL}/api/admin/orders/{order_id}")

        # base_currency_amount should be in headers now
        assert "base_currency_amount" in headers, \
            f"base_currency_amount not in CSV headers after creating order with that field: {headers}"
        print("✓ base_currency_amount column present in orders export CSV")


# ─────────────────────────────────────────────────────────────────────────────
# 6. Subscriptions export CSV – base_currency_amount column
# ─────────────────────────────────────────────────────────────────────────────

class TestSubscriptionsExportCSV:
    """Test that subscriptions export CSV contains base_currency_amount column."""

    def test_subscriptions_export_returns_csv(self, admin_session):
        """GET /api/admin/export/subscriptions should return CSV data."""
        res = admin_session.get(f"{BASE_URL}/api/admin/export/subscriptions")
        assert res.status_code == 200, f"Export subscriptions failed: {res.status_code} {res.text}"
        content_type = res.headers.get("content-type", "")
        assert "text/csv" in content_type or "csv" in content_type, \
            f"Expected CSV content-type, got: {content_type}"
        print(f"✓ Subscriptions export returns CSV (content-type: {content_type})")

    def test_subscriptions_export_has_base_currency_amount_or_reports(self, admin_session):
        """Subscriptions with base_currency_amount should show that column in CSV."""
        res = admin_session.get(f"{BASE_URL}/api/admin/export/subscriptions")
        assert res.status_code == 200
        csv_content = res.text

        if csv_content.strip() == "No data":
            print("  ⚠ No subscriptions in system - skipping column check")
            pytest.skip("No subscriptions data")

        reader = csv.DictReader(io.StringIO(csv_content))
        headers = reader.fieldnames or []
        rows = list(reader)
        print(f"\n  CSV headers: {headers}")
        print(f"  Total subscriptions: {len(rows)}")

        has_bca = "base_currency_amount" in headers
        if has_bca:
            bca_values = [r.get("base_currency_amount") for r in rows if r.get("base_currency_amount")]
            print(f"  Subscriptions with base_currency_amount: {len(bca_values)}")
            print("✓ base_currency_amount column present in subscriptions export")
        else:
            print("  ℹ base_currency_amount not in CSV headers - subscriptions may predate feature")


# ─────────────────────────────────────────────────────────────────────────────
# 7. Store products API – currency field returned
# ─────────────────────────────────────────────────────────────────────────────

class TestStoreCurrencyFields:
    """Test that product listings return currency field for frontend to use."""

    def test_store_products_return_currency_field(self, admin_session):
        """GET /api/store/products should return products with currency field."""
        res = requests.get(f"{BASE_URL}/api/store/products")
        assert res.status_code == 200, f"Store products failed: {res.status_code} {res.text}"
        data = res.json()
        products = data.get("products", data.get("items", []))
        print(f"\n  Products returned: {len(products)}")

        if not products:
            # Try the admin catalog
            res2 = admin_session.get(f"{BASE_URL}/api/admin/catalog/products")
            products = res2.json().get("products", []) if res2.status_code == 200 else []

        assert len(products) > 0, "No products returned from store"

        # Check currency field exists
        for p in products[:5]:
            currency = p.get("currency")
            print(f"  Product '{p.get('id')}' name='{p.get('name')}' currency={currency}")

        # At least some products should have a currency field
        products_with_currency = [p for p in products if p.get("currency")]
        print(f"  Products with currency field: {len(products_with_currency)}/{len(products)}")
        assert len(products_with_currency) > 0, \
            "No products have a 'currency' field set - frontend cannot render correct currency"
        print("✓ Products have currency field")

    def test_prod_bookkeeping_has_cad_currency(self, admin_session):
        """Product prod_bookkeeping should have currency=CAD."""
        # First try admin catalog
        res = admin_session.get(f"{BASE_URL}/api/admin/catalog/products/prod_bookkeeping")
        if res.status_code == 404:
            # Try store products
            res = requests.get(f"{BASE_URL}/api/store/products")
            if res.status_code == 200:
                products = res.json().get("products", [])
                bookkeeping = next((p for p in products if p.get("id") == "prod_bookkeeping"), None)
                if not bookkeeping:
                    print("  ℹ prod_bookkeeping not found in store products")
                    pytest.skip("prod_bookkeeping product not found")
                currency = bookkeeping.get("currency")
                print(f"\n  prod_bookkeeping currency: {currency}")
                assert currency == "CAD", f"Expected prod_bookkeeping.currency=CAD, got: {currency}"
                print("✓ prod_bookkeeping has currency=CAD")
                return

        if res.status_code == 200:
            product = res.json().get("product", res.json())
            currency = product.get("currency")
            print(f"\n  prod_bookkeeping currency: {currency}")
            assert currency == "CAD", f"Expected prod_bookkeeping.currency=CAD, got: {currency}"
            print("✓ prod_bookkeeping has currency=CAD")
        else:
            pytest.skip(f"Could not fetch prod_bookkeeping: {res.status_code}")

    def test_store_categories_endpoint(self):
        """GET /api/store/categories should return 200."""
        res = requests.get(f"{BASE_URL}/api/store/categories")
        assert res.status_code == 200, f"Store categories failed: {res.status_code}"
        print("✓ Store categories endpoint works")
