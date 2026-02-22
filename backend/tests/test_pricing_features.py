"""
Backend tests for pricing feature changes (iteration 39):
- pricing_type=simple/fixed handled correctly (returns base_price, not 0)
- intake questions with affects_price: add and multiply modes
- price_rounding (25, 50, 100) applied correctly
- Admin catalog: categories per_page=500, no pricing_complexity filter
- Product create/update with price_rounding field
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"


@pytest.fixture(scope="module")
def admin_token():
    resp = requests.post(f"{BASE_URL}/api/auth/login",
                         json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# Track created product IDs for cleanup
created_product_ids = []


# ── Helper ────────────────────────────────────────────────────────────────────

def make_product_payload(name: str, base_price: float = 500.0, intake_schema: dict = None,
                          price_rounding: str = None) -> dict:
    payload = {
        "name": name,
        "short_description": "Pricing test product",
        "description_long": "",
        "bullets": [],
        "category": "Test",
        "base_price": base_price,
        "is_subscription": False,
        "pricing_complexity": "SIMPLE",
        "is_active": True,
        "pricing_rules": {},
    }
    if intake_schema is not None:
        payload["intake_schema_json"] = intake_schema
    if price_rounding is not None:
        payload["price_rounding"] = price_rounding
    return payload


# ── Test 1: pricing_type=simple/fixed returns correct subtotal ─────────────────

class TestSimpleFixedPricing:
    """New products get pricing_type=fixed; existing 'simple' products handled same way."""

    created_id = None

    def test_create_product_gets_fixed_pricing_type(self, admin_headers):
        """New product created via admin should have pricing_type=fixed."""
        payload = make_product_payload("TEST_PRICING_SimpleFixed", base_price=350.0)
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        product = resp.json()["product"]
        assert product.get("pricing_type") == "fixed", f"Expected 'fixed', got: {product.get('pricing_type')}"
        TestSimpleFixedPricing.created_id = product["id"]
        created_product_ids.append(product["id"])

    def test_pricing_calc_fixed_returns_correct_subtotal(self, admin_headers):
        """pricing/calc for a fixed product should return subtotal = base_price."""
        if not TestSimpleFixedPricing.created_id:
            pytest.skip("No product created")
        pid = TestSimpleFixedPricing.created_id
        resp = requests.post(
            f"{BASE_URL}/api/pricing/calc",
            json={"product_id": pid, "inputs": {}},
            headers=admin_headers,
        )
        assert resp.status_code == 200, f"Pricing calc failed: {resp.text}"
        data = resp.json()
        assert data["subtotal"] == 350.0, f"Expected subtotal=350, got: {data['subtotal']}"
        assert data["total"] > 0, f"Expected total > 0, got: {data['total']}"

    def test_pricing_calc_base_price_zero_returns_zero(self, admin_headers):
        """Product with base_price=0 should return subtotal=0 (triggers RFQ on frontend)."""
        payload = make_product_payload("TEST_PRICING_ZeroPrice", base_price=0.0)
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        pid = resp.json()["product"]["id"]
        created_product_ids.append(pid)

        resp2 = requests.post(
            f"{BASE_URL}/api/pricing/calc",
            json={"product_id": pid, "inputs": {}},
            headers=admin_headers,
        )
        assert resp2.status_code == 200, f"Pricing calc failed: {resp2.text}"
        data = resp2.json()
        assert data["subtotal"] == 0.0, f"Expected subtotal=0, got: {data['subtotal']}"
        assert data["total"] == 0.0, f"Expected total=0, got: {data['total']}"


# ── Test 2: Intake price adjustments – Add mode ────────────────────────────────

class TestIntakePriceAdjustAdd:
    """Intake dropdown with affects_price=True and price_mode='add' should add/subtract price."""

    created_id = None

    def test_create_product_with_add_mode_intake(self, admin_headers):
        """Create product with add-mode intake question (professional tier adds $300)."""
        schema = {
            "version": 1,
            "questions": {
                "dropdown": [
                    {
                        "key": "service_tier",
                        "label": "Service Tier",
                        "helper_text": "Choose your tier",
                        "required": True,
                        "enabled": True,
                        "order": 0,
                        "affects_price": True,
                        "price_mode": "add",
                        "options": [
                            {"label": "Standard", "value": "standard", "price_value": 0},
                            {"label": "Professional", "value": "professional", "price_value": 300},
                            {"label": "Enterprise", "value": "enterprise", "price_value": 700},
                        ],
                    }
                ],
                "multiselect": [],
                "single_line": [],
                "multi_line": [],
            },
        }
        payload = make_product_payload("TEST_PRICING_AddMode", base_price=500.0, intake_schema=schema)
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        pid = resp.json()["product"]["id"]
        created_product_ids.append(pid)
        TestIntakePriceAdjustAdd.created_id = pid

    def test_pricing_add_mode_no_selection(self, admin_headers):
        """No service_tier input → subtotal = base_price = 500."""
        if not TestIntakePriceAdjustAdd.created_id:
            pytest.skip("No product created")
        pid = TestIntakePriceAdjustAdd.created_id
        resp = requests.post(
            f"{BASE_URL}/api/pricing/calc",
            json={"product_id": pid, "inputs": {}},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # No selection → no intake adjustment, base_price=500
        assert data["subtotal"] == 500.0, f"Expected 500, got: {data['subtotal']}"

    def test_pricing_add_mode_professional_selection(self, admin_headers):
        """service_tier=professional (+300) → subtotal = 500 + 300 = 800."""
        if not TestIntakePriceAdjustAdd.created_id:
            pytest.skip("No product created")
        pid = TestIntakePriceAdjustAdd.created_id
        resp = requests.post(
            f"{BASE_URL}/api/pricing/calc",
            json={"product_id": pid, "inputs": {"service_tier": "professional"}},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["subtotal"] == 800.0, f"Expected subtotal=800, got: {data['subtotal']}. Full response: {data}"

    def test_pricing_add_mode_enterprise_selection(self, admin_headers):
        """service_tier=enterprise (+700) → subtotal = 500 + 700 = 1200."""
        if not TestIntakePriceAdjustAdd.created_id:
            pytest.skip("No product created")
        pid = TestIntakePriceAdjustAdd.created_id
        resp = requests.post(
            f"{BASE_URL}/api/pricing/calc",
            json={"product_id": pid, "inputs": {"service_tier": "enterprise"}},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["subtotal"] == 1200.0, f"Expected subtotal=1200, got: {data['subtotal']}"

    def test_pricing_add_mode_line_items_present(self, admin_headers):
        """Response should contain line_items with the intake adjustment listed."""
        if not TestIntakePriceAdjustAdd.created_id:
            pytest.skip("No product created")
        pid = TestIntakePriceAdjustAdd.created_id
        resp = requests.post(
            f"{BASE_URL}/api/pricing/calc",
            json={"product_id": pid, "inputs": {"service_tier": "professional"}},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        line_items = data.get("line_items", [])
        assert len(line_items) >= 2, f"Expected at least 2 line items, got: {line_items}"
        labels = [li["label"] for li in line_items]
        # Should have a line item for base and one for the intake adjustment
        assert any("Professional" in l or "Service Tier" in l for l in labels), f"No intake adjustment in line_items: {labels}"


# ── Test 3: Intake price adjustments – Multiply mode ──────────────────────────

class TestIntakePriceAdjustMultiply:
    """Intake dropdown with affects_price=True and price_mode='multiply' should multiply price."""

    created_id = None

    def test_create_product_with_multiply_mode_intake(self, admin_headers):
        """Create product with multiply-mode intake question (0.9 for 10% discount)."""
        schema = {
            "version": 1,
            "questions": {
                "dropdown": [
                    {
                        "key": "discount_tier",
                        "label": "Discount",
                        "helper_text": "",
                        "required": False,
                        "enabled": True,
                        "order": 0,
                        "affects_price": True,
                        "price_mode": "multiply",
                        "options": [
                            {"label": "No discount", "value": "none", "price_value": 0},
                            {"label": "10% off", "value": "ten_pct", "price_value": 0.9},
                            {"label": "20% off", "value": "twenty_pct", "price_value": 0.8},
                        ],
                    }
                ],
                "multiselect": [],
                "single_line": [],
                "multi_line": [],
            },
        }
        payload = make_product_payload("TEST_PRICING_MultiplyMode", base_price=500.0, intake_schema=schema)
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        pid = resp.json()["product"]["id"]
        created_product_ids.append(pid)
        TestIntakePriceAdjustMultiply.created_id = pid

    def test_pricing_multiply_mode_10pct(self, admin_headers):
        """discount_tier=ten_pct (×0.9) → subtotal = 500 × 0.9 = 450."""
        if not TestIntakePriceAdjustMultiply.created_id:
            pytest.skip("No product created")
        pid = TestIntakePriceAdjustMultiply.created_id
        resp = requests.post(
            f"{BASE_URL}/api/pricing/calc",
            json={"product_id": pid, "inputs": {"discount_tier": "ten_pct"}},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["subtotal"] == 450.0, f"Expected subtotal=450, got: {data['subtotal']}. Full: {data}"

    def test_pricing_multiply_mode_20pct(self, admin_headers):
        """discount_tier=twenty_pct (×0.8) → subtotal = 500 × 0.8 = 400."""
        if not TestIntakePriceAdjustMultiply.created_id:
            pytest.skip("No product created")
        pid = TestIntakePriceAdjustMultiply.created_id
        resp = requests.post(
            f"{BASE_URL}/api/pricing/calc",
            json={"product_id": pid, "inputs": {"discount_tier": "twenty_pct"}},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["subtotal"] == 400.0, f"Expected subtotal=400, got: {data['subtotal']}"

    def test_pricing_multiply_mode_line_items(self, admin_headers):
        """Multiply line item label should contain the multiplier notation."""
        if not TestIntakePriceAdjustMultiply.created_id:
            pytest.skip("No product created")
        pid = TestIntakePriceAdjustMultiply.created_id
        resp = requests.post(
            f"{BASE_URL}/api/pricing/calc",
            json={"product_id": pid, "inputs": {"discount_tier": "ten_pct"}},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        line_items = data.get("line_items", [])
        labels = [li["label"] for li in line_items]
        # The multiply mode line item should contain '×' or 'x' notation
        assert any("×" in l or "x" in l.lower() for l in labels), f"No multiply notation in line_items: {labels}"


# ── Test 4: Price Rounding ────────────────────────────────────────────────────

class TestPriceRounding:
    """Products with price_rounding field should round their subtotal."""

    rounding_ids = {}

    def test_create_product_with_rounding_100(self, admin_headers):
        """Product with price_rounding=100 and base_price=333 → subtotal rounded to 300."""
        payload = make_product_payload("TEST_PRICING_Round100", base_price=333.0, price_rounding="100")
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        product = resp.json()["product"]
        pid = product["id"]
        created_product_ids.append(pid)
        TestPriceRounding.rounding_ids["100"] = pid
        assert product.get("price_rounding") == "100", f"price_rounding not persisted: {product.get('price_rounding')}"

    def test_pricing_rounding_100_333_rounds_to_300(self, admin_headers):
        """333 rounded to nearest 100 = 300."""
        pid = TestPriceRounding.rounding_ids.get("100")
        if not pid:
            pytest.skip("No product created")
        resp = requests.post(
            f"{BASE_URL}/api/pricing/calc",
            json={"product_id": pid, "inputs": {}},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["subtotal"] == 300.0, f"Expected subtotal=300, got: {data['subtotal']}"

    def test_create_product_with_rounding_50(self, admin_headers):
        """Product with price_rounding=50 and base_price=175 → subtotal = 200 (nearest 50)."""
        payload = make_product_payload("TEST_PRICING_Round50", base_price=175.0, price_rounding="50")
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        pid = resp.json()["product"]["id"]
        created_product_ids.append(pid)
        TestPriceRounding.rounding_ids["50"] = pid

    def test_pricing_rounding_50_175_rounds_to_200(self, admin_headers):
        """175 rounded to nearest 50 = 200."""
        pid = TestPriceRounding.rounding_ids.get("50")
        if not pid:
            pytest.skip("No product created")
        resp = requests.post(
            f"{BASE_URL}/api/pricing/calc",
            json={"product_id": pid, "inputs": {}},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["subtotal"] == 200.0, f"Expected subtotal=200, got: {data['subtotal']}"

    def test_create_product_with_rounding_25(self, admin_headers):
        """Product with price_rounding=25 and base_price=487 → subtotal = 500 (nearest 25)."""
        payload = make_product_payload("TEST_PRICING_Round25", base_price=487.0, price_rounding="25")
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        pid = resp.json()["product"]["id"]
        created_product_ids.append(pid)
        TestPriceRounding.rounding_ids["25"] = pid

    def test_pricing_rounding_25_487_rounds_to_500(self, admin_headers):
        """487 rounded to nearest 25 = 500."""
        pid = TestPriceRounding.rounding_ids.get("25")
        if not pid:
            pytest.skip("No product created")
        resp = requests.post(
            f"{BASE_URL}/api/pricing/calc",
            json={"product_id": pid, "inputs": {}},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["subtotal"] == 500.0, f"Expected subtotal=500, got: {data['subtotal']}"

    def test_product_without_rounding_not_rounded(self, admin_headers):
        """Product without price_rounding should return exact base_price."""
        payload = make_product_payload("TEST_PRICING_NoRounding", base_price=333.0)
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=admin_headers)
        assert resp.status_code == 200
        pid = resp.json()["product"]["id"]
        created_product_ids.append(pid)

        resp2 = requests.post(
            f"{BASE_URL}/api/pricing/calc",
            json={"product_id": pid, "inputs": {}},
            headers=admin_headers,
        )
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["subtotal"] == 333.0, f"Expected exact 333, got: {data['subtotal']}"


# ── Test 5: Update product with price_rounding ────────────────────────────────

class TestUpdatePriceRounding:
    """Verify price_rounding is persisted on product update."""

    updated_id = None

    def test_create_product_without_rounding(self, admin_headers):
        payload = make_product_payload("TEST_PRICING_UpdateRounding", base_price=250.0)
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=admin_headers)
        assert resp.status_code == 200
        product = resp.json()["product"]
        pid = product["id"]
        created_product_ids.append(pid)
        TestUpdatePriceRounding.updated_id = pid
        # No rounding initially
        assert product.get("price_rounding") is None or product.get("price_rounding") == ""

    def test_update_product_to_add_rounding(self, admin_headers):
        """Update product to add price_rounding=100."""
        pid = TestUpdatePriceRounding.updated_id
        if not pid:
            pytest.skip("No product created")
        resp = requests.put(
            f"{BASE_URL}/api/admin/products/{pid}",
            json={"name": "TEST_PRICING_UpdateRounding", "is_active": True,
                  "pricing_rules": {}, "base_price": 250.0, "price_rounding": "100"},
            headers=admin_headers,
        )
        assert resp.status_code == 200, f"Update failed: {resp.text}"

    def test_pricing_after_update_has_rounding(self, admin_headers):
        """After setting price_rounding=100, base_price=250 → round to nearest 100 = 300."""
        pid = TestUpdatePriceRounding.updated_id
        if not pid:
            pytest.skip("No product created")
        resp = requests.post(
            f"{BASE_URL}/api/pricing/calc",
            json={"product_id": pid, "inputs": {}},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # 250 rounded to nearest 100 = 300
        assert data["subtotal"] == 300.0, f"Expected subtotal=300 (250 rounded to 100), got: {data['subtotal']}"


# ── Test 6: Admin catalog categories per_page=500 ─────────────────────────────

class TestAdminCatalogCategories:
    """Admin categories endpoint should return all categories when per_page=500."""

    def test_admin_categories_per_page_500(self, admin_headers):
        """When per_page=500, should return all categories."""
        resp = requests.get(f"{BASE_URL}/api/admin/categories?per_page=500", headers=admin_headers)
        assert resp.status_code == 200, f"Categories fetch failed: {resp.text}"
        data = resp.json()
        assert "categories" in data
        assert isinstance(data["categories"], list)
        # per_page=500 should fetch up to 500 categories
        assert data["per_page"] == 500 or len(data["categories"]) == data["total"]

    def test_admin_categories_default_20(self, admin_headers):
        """Default per_page=20 returns at most 20 categories."""
        resp = requests.get(f"{BASE_URL}/api/admin/categories", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["categories"]) <= 20

    def test_admin_products_per_page_500(self, admin_headers):
        """When per_page=500, admin products-all should return all products."""
        resp = requests.get(f"{BASE_URL}/api/admin/products-all?per_page=500", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "products" in data
        # Verify the per_page returned
        assert data["per_page"] == 500


# ── Test 7: Rounding with intake adjustments ─────────────────────────────────

class TestRoundingWithIntake:
    """Rounding should be applied AFTER intake adjustments."""

    created_id = None

    def test_create_product_rounding_with_add_intake(self, admin_headers):
        """base_price=475, add_intake=+75 → 550, rounded to nearest 100 = 600."""
        schema = {
            "version": 1,
            "questions": {
                "dropdown": [
                    {
                        "key": "extra_feature",
                        "label": "Extra Feature",
                        "helper_text": "",
                        "required": False,
                        "enabled": True,
                        "order": 0,
                        "affects_price": True,
                        "price_mode": "add",
                        "options": [
                            {"label": "None", "value": "none", "price_value": 0},
                            {"label": "Basic add-on", "value": "basic", "price_value": 75},
                        ],
                    }
                ],
                "multiselect": [],
                "single_line": [],
                "multi_line": [],
            },
        }
        payload = make_product_payload("TEST_PRICING_RoundWithIntake", base_price=475.0,
                                        intake_schema=schema, price_rounding="100")
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        pid = resp.json()["product"]["id"]
        created_product_ids.append(pid)
        TestRoundingWithIntake.created_id = pid

    def test_rounding_applied_after_intake_add(self, admin_headers):
        """475 base + 75 intake add = 550, then round to nearest 100 = 600."""
        pid = TestRoundingWithIntake.created_id
        if not pid:
            pytest.skip("No product created")
        resp = requests.post(
            f"{BASE_URL}/api/pricing/calc",
            json={"product_id": pid, "inputs": {"extra_feature": "basic"}},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["subtotal"] == 600.0, f"Expected 600 (475+75=550, rounded to 100), got: {data['subtotal']}"


# ── Cleanup ────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def cleanup(admin_headers):
    yield
    for pid in created_product_ids:
        try:
            requests.put(
                f"{BASE_URL}/api/admin/products/{pid}",
                json={"name": f"DELETED_{pid[:8]}", "is_active": False, "pricing_rules": {}},
                headers=admin_headers,
            )
        except Exception:
            pass
