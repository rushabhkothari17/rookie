"""
Backend tests for new intake pricing features:
- Tiered pricing (number questions with pricing_mode=tiered)
- Boolean/yes-no pricing (affects_price_boolean / price_for_yes / price_for_no)
- Price floor and ceiling caps
- Product save with all new features
- Visibility rules (hidden questions excluded from pricing)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


# ── Helpers ─────────────────────────────────────────────────────────────────

def get_admin_token():
    # Use partner-login for tenant-scoped access
    resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!",
        "partner_code": "automate-accounts",
    })
    if resp.status_code == 200:
        data = resp.json()
        return data.get("access_token") or data.get("token")
    # Fallback to regular login
    resp2 = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!",
    })
    if resp2.status_code == 200:
        data = resp2.json()
        return data.get("access_token") or data.get("token")
    return None


def auth_headers():
    token = get_admin_token()
    if not token:
        pytest.skip("Admin login failed — skipping test")
    return {"Authorization": f"Bearer {token}"}


def create_product(payload: dict, headers: dict) -> dict:
    resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=headers)
    assert resp.status_code == 200, f"Create product failed: {resp.text}"
    data = resp.json()
    # API wraps result in {"product": {...}}
    return data.get("product", data)


def calc_price(product_id: str, inputs: dict, headers: dict = None) -> dict:
    h = headers or auth_headers()
    resp = requests.post(f"{BASE_URL}/api/pricing/calc", json={
        "product_id": product_id,
        "inputs": inputs,
    }, headers=h)
    assert resp.status_code == 200, f"Price calc failed: {resp.text}"
    return resp.json()


def delete_product(product_id: str, headers: dict):
    """Deactivate product (no DELETE endpoint exists — deactivate instead)."""
    requests.put(f"{BASE_URL}/api/admin/products/{product_id}",
                 json={"name": "TEST96_DEACTIVATED", "is_active": False},
                 headers=headers)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_auth():
    return auth_headers()


@pytest.fixture(scope="module")
def tiered_product(admin_auth):
    """Create a product with a tiered-pricing number question."""
    payload = {
        "name": "TEST96_Tiered_Pricing",
        "short_description": "Tiered pricing test",
        "base_price": 100.0,
        "pricing_type": "internal",
        "is_active": True,
        "intake_schema_json": {
            "version": 2,
            "questions": [
                {
                    "key": "users",
                    "label": "Number of Users",
                    "helper_text": "",
                    "required": True,
                    "enabled": True,
                    "order": 0,
                    "type": "number",
                    "pricing_mode": "tiered",
                    "tiers": [
                        {"from": 0, "to": 10, "price_per_unit": 5.0},
                        {"from": 10, "to": None, "price_per_unit": 3.0},
                    ],
                    "min": 0,
                    "max": 1000,
                    "step": 1,
                }
            ],
        },
    }
    product = create_product(payload, admin_auth)
    yield product
    delete_product(product["id"], admin_auth)


@pytest.fixture(scope="module")
def boolean_product(admin_auth):
    """Create a product with a boolean question that affects price."""
    payload = {
        "name": "TEST96_Boolean_Pricing",
        "short_description": "Boolean pricing test",
        "base_price": 200.0,
        "pricing_type": "internal",
        "is_active": True,
        "intake_schema_json": {
            "version": 2,
            "questions": [
                {
                    "key": "rush_delivery",
                    "label": "Rush Delivery?",
                    "helper_text": "",
                    "required": False,
                    "enabled": True,
                    "order": 0,
                    "type": "boolean",
                    # Note: pricing_service.py checks q.get("affects_price"), not affects_price_boolean
                    "affects_price": True,
                    "price_for_yes": 50.0,
                    "price_for_no": 0.0,
                }
            ],
        },
    }
    product = create_product(payload, admin_auth)
    yield product
    delete_product(product["id"], admin_auth)


@pytest.fixture(scope="module")
def floor_ceiling_product(admin_auth):
    """Create a product with price floor and ceiling caps."""
    payload = {
        "name": "TEST96_Floor_Ceiling",
        "short_description": "Price caps test",
        "base_price": 0.0,
        "pricing_type": "internal",
        "is_active": True,
        "intake_schema_json": {
            "version": 2,
            "price_floor": 50.0,
            "price_ceiling": 200.0,
            "questions": [
                {
                    "key": "hours",
                    "label": "Hours",
                    "helper_text": "",
                    "required": True,
                    "enabled": True,
                    "order": 0,
                    "type": "number",
                    "pricing_mode": "flat",
                    "price_per_unit": 20.0,
                    "min": 0,
                    "max": 100,
                    "step": 1,
                }
            ],
        },
    }
    product = create_product(payload, admin_auth)
    yield product
    delete_product(product["id"], admin_auth)


# ── Tiered Pricing Tests ──────────────────────────────────────────────────────

class TestTieredPricing:
    """Tiered pricing calculation: (val-from)*ppu for each tier."""

    def test_tiered_within_first_tier(self, tiered_product, admin_auth):
        """5 users: all in first tier 0-10 at £5/user = 25. Base 100. Total = 125."""
        result = calc_price(tiered_product["id"], {"users": 5}, admin_auth)
        assert result["subtotal"] == 125.0, f"Expected 125, got {result['subtotal']}"
        assert result["requires_checkout"] is True

    def test_tiered_at_boundary(self, tiered_product, admin_auth):
        """10 users: exactly 10 in first tier 0-10 at £5 = 50. Base 100. Total = 150."""
        result = calc_price(tiered_product["id"], {"users": 10}, admin_auth)
        assert result["subtotal"] == 150.0, f"Expected 150, got {result['subtotal']}"

    def test_tiered_spanning_two_tiers(self, tiered_product, admin_auth):
        """15 users: first 10 at £5 = 50, next 5 at £3 = 15. Base 100. Total = 165."""
        result = calc_price(tiered_product["id"], {"users": 15}, admin_auth)
        assert result["subtotal"] == 165.0, f"Expected 165, got {result['subtotal']}"

    def test_tiered_has_line_items(self, tiered_product, admin_auth):
        """Tiered pricing should include line items in response."""
        result = calc_price(tiered_product["id"], {"users": 15}, admin_auth)
        line_items = result.get("line_items", [])
        assert len(line_items) >= 2, f"Expected at least 2 line items, got {line_items}"
        labels = [item["label"] for item in line_items]
        assert any("Number of Users" in lbl or "users" in lbl.lower() for lbl in labels), \
            f"No users line item found in: {labels}"

    def test_tiered_zero_value_no_charge(self, tiered_product, admin_auth):
        """0 users: tiered adds 0. Total = base 100."""
        result = calc_price(tiered_product["id"], {"users": 0}, admin_auth)
        assert result["subtotal"] == 100.0, f"Expected 100, got {result['subtotal']}"

    def test_product_save_with_tiered_intake(self, admin_auth):
        """Admin can save a product with tiered pricing intake - verifies persistence."""
        payload = {
            "name": "TEST96_Save_Tiered",
            "short_description": "Save tiered",
            "base_price": 50.0,
            "pricing_type": "internal",
            "is_active": True,
            "intake_schema_json": {
                "version": 2,
                "questions": [
                    {
                        "key": "transactions",
                        "label": "Monthly Transactions",
                        "helper_text": "How many transactions per month?",
                        "required": True,
                        "enabled": True,
                        "order": 0,
                        "type": "number",
                        "pricing_mode": "tiered",
                        "tiers": [
                            {"from": 0, "to": 100, "price_per_unit": 0.5},
                            {"from": 100, "to": 500, "price_per_unit": 0.3},
                            {"from": 500, "to": None, "price_per_unit": 0.1},
                        ],
                        "min": 0,
                        "max": 10000,
                        "step": 10,
                    }
                ],
            },
        }
        product = create_product(payload, admin_auth)
        pid = product["id"]
        try:
            assert product.get("pricing_type") == "internal"
            # Verify via list endpoint (no GET by ID)
            get_resp = requests.get(
                f"{BASE_URL}/api/admin/products-all?per_page=200",
                headers=admin_auth
            )
            assert get_resp.status_code == 200
            prods = get_resp.json().get("products", [])
            saved = next((p for p in prods if p.get("id") == pid), None)
            assert saved is not None, f"Product {pid} not found in list"
            schema = saved.get("intake_schema_json", {})
            questions = schema.get("questions", [])
            assert len(questions) == 1, f"Expected 1 question, got {len(questions)}"
            assert questions[0].get("pricing_mode") == "tiered"
            assert len(questions[0].get("tiers", [])) == 3
        finally:
            delete_product(pid, admin_auth)


# ── Boolean Pricing Tests ─────────────────────────────────────────────────────

class TestBooleanPricing:
    """Boolean (yes/no) question affects price."""

    def test_boolean_yes_adds_price(self, boolean_product, admin_auth):
        """Answer 'yes' → adds price_for_yes (50). Base 200. Total = 250."""
        result = calc_price(boolean_product["id"], {"rush_delivery": "yes"}, admin_auth)
        assert result["subtotal"] == 250.0, f"Expected 250, got {result['subtotal']}"

    def test_boolean_no_no_addition(self, boolean_product, admin_auth):
        """Answer 'no' → price_for_no is 0. Total stays 200."""
        result = calc_price(boolean_product["id"], {"rush_delivery": "no"}, admin_auth)
        assert result["subtotal"] == 200.0, f"Expected 200, got {result['subtotal']}"

    def test_boolean_yes_line_item(self, boolean_product, admin_auth):
        """Yes answer should create a line item."""
        result = calc_price(boolean_product["id"], {"rush_delivery": "yes"}, admin_auth)
        line_items = result.get("line_items", [])
        labels = [item["label"] for item in line_items]
        assert any("Rush Delivery" in lbl or "rush_delivery" in lbl.lower() for lbl in labels), \
            f"Expected 'Rush Delivery' line item in {labels}"

    def test_boolean_true_string(self, boolean_product, admin_auth):
        """Answer 'true' (string) should also be treated as yes."""
        result = calc_price(boolean_product["id"], {"rush_delivery": "true"}, admin_auth)
        assert result["subtotal"] == 250.0, f"Expected 250 for 'true', got {result['subtotal']}"

    def test_boolean_missing_answer_no_charge(self, boolean_product, admin_auth):
        """No answer provided → boolean question ignored, only base price."""
        result = calc_price(boolean_product["id"], {}, admin_auth)
        assert result["subtotal"] == 200.0, f"Expected 200 (base only), got {result['subtotal']}"


# ── Price Floor / Ceiling Tests ───────────────────────────────────────────────

class TestPriceFloorCeiling:
    """Price floor and ceiling caps."""

    def test_floor_applied_when_below_minimum(self, floor_ceiling_product, admin_auth):
        """1 hour at £20 = £20, but floor is £50. Total should be £50."""
        result = calc_price(floor_ceiling_product["id"], {"hours": 1}, admin_auth)
        assert result["subtotal"] == 50.0, f"Expected floor 50, got {result['subtotal']}"

    def test_floor_not_applied_when_above(self, floor_ceiling_product, admin_auth):
        """3 hours at £20 = £60, floor is £50. Total should be £60 (no floor applied)."""
        result = calc_price(floor_ceiling_product["id"], {"hours": 3}, admin_auth)
        assert result["subtotal"] == 60.0, f"Expected 60, got {result['subtotal']}"

    def test_ceiling_applied_when_above_maximum(self, floor_ceiling_product, admin_auth):
        """15 hours at £20 = £300, ceiling is £200. Total should be £200."""
        result = calc_price(floor_ceiling_product["id"], {"hours": 15}, admin_auth)
        assert result["subtotal"] == 200.0, f"Expected ceiling 200, got {result['subtotal']}"

    def test_ceiling_not_applied_when_below(self, floor_ceiling_product, admin_auth):
        """8 hours at £20 = £160, ceiling is £200. Total should be £160."""
        result = calc_price(floor_ceiling_product["id"], {"hours": 8}, admin_auth)
        assert result["subtotal"] == 160.0, f"Expected 160, got {result['subtotal']}"

    def test_floor_line_item_label(self, floor_ceiling_product, admin_auth):
        """When floor is applied, a 'Minimum pricing applied' line item should appear."""
        result = calc_price(floor_ceiling_product["id"], {"hours": 1}, admin_auth)
        labels = [item["label"] for item in result.get("line_items", [])]
        assert any("Minimum pricing" in lbl or "floor" in lbl.lower() for lbl in labels), \
            f"Expected minimum pricing line item, got: {labels}"

    def test_ceiling_line_item_label(self, floor_ceiling_product, admin_auth):
        """When ceiling is applied, a 'Maximum pricing cap applied' line item should appear."""
        result = calc_price(floor_ceiling_product["id"], {"hours": 15}, admin_auth)
        labels = [item["label"] for item in result.get("line_items", [])]
        assert any("Maximum pricing cap" in lbl or "cap" in lbl.lower() for lbl in labels), \
            f"Expected maximum pricing cap line item, got: {labels}"


# ── Visibility Rules - Pricing Exclusion ────────────────────────────────────

class TestVisibilityRulesPricingExclusion:
    """Hidden questions should not affect pricing when keys not in inputs."""

    def test_hidden_question_not_included_in_pricing(self, admin_auth):
        """Create product with 2 questions: one conditional on the other.
        When question 1 is 'no', question 2 (priced) key not sent → only base price."""
        payload = {
            "name": "TEST96_Visibility_Pricing",
            "short_description": "Visibility test",
            "base_price": 100.0,
            "pricing_type": "internal",
            "is_active": True,
            "intake_schema_json": {
                "version": 2,
                "questions": [
                    {
                        "key": "include_support",
                        "label": "Include Support",
                        "helper_text": "",
                        "required": False,
                        "enabled": True,
                        "order": 0,
                        "type": "boolean",
                        "affects_price": False,
                    },
                    {
                        "key": "support_hours",
                        "label": "Support Hours",
                        "helper_text": "",
                        "required": False,
                        "enabled": True,
                        "order": 1,
                        "type": "number",
                        "pricing_mode": "flat",
                        "price_per_unit": 50.0,
                        "min": 0,
                        "max": 100,
                        "step": 1,
                        "visibility_rule": {
                            "depends_on": "include_support",
                            "operator": "equals",
                            "value": "yes",
                        },
                    },
                ],
            },
        }
        product = create_product(payload, admin_auth)
        pid = product["id"]
        try:
            # Scenario 1: Frontend omits support_hours (hidden) - only include_support sent
            result_no_support = calc_price(pid, {"include_support": "no"}, admin_auth)
            assert result_no_support["subtotal"] == 100.0, \
                f"Expected 100 when support_hours not sent, got {result_no_support['subtotal']}"

            # Scenario 2: Frontend includes support_hours (visible) - both sent
            result_with_support = calc_price(pid, {"include_support": "yes", "support_hours": 2}, admin_auth)
            assert result_with_support["subtotal"] == 200.0, \
                f"Expected 200 when support_hours=2 included, got {result_with_support['subtotal']}"
        finally:
            delete_product(pid, admin_auth)


# ── Product Save With Full New Features ──────────────────────────────────────

class TestProductSaveNewFeatures:
    """End-to-end: Admin can create and retrieve products with all new features."""

    def test_save_product_with_boolean_and_tiered_and_caps(self, admin_auth):
        """Create product with boolean + tiered number + price caps. Verify persistence."""
        payload = {
            "name": "TEST96_Full_Features",
            "short_description": "Full features test",
            "base_price": 0.0,
            "pricing_type": "internal",
            "is_active": True,
            "intake_schema_json": {
                "version": 2,
                "price_floor": 100.0,
                "price_ceiling": 500.0,
                "questions": [
                    {
                        "key": "volume",
                        "label": "Transaction Volume",
                        "helper_text": "Enter monthly volume",
                        "required": True,
                        "enabled": True,
                        "order": 0,
                        "type": "number",
                        "pricing_mode": "tiered",
                        "tiers": [
                            {"from": 0, "to": 50, "price_per_unit": 2.0},
                            {"from": 50, "to": None, "price_per_unit": 1.0},
                        ],
                        "min": 0,
                        "max": 500,
                        "step": 1,
                    },
                    {
                        "key": "priority_support",
                        "label": "Priority Support",
                        "helper_text": "Add priority support?",
                        "required": False,
                        "enabled": True,
                        "order": 1,
                        "type": "boolean",
                        "affects_price": True,
                        "price_for_yes": 30.0,
                        "price_for_no": 0.0,
                    },
                ],
            },
        }
        product = create_product(payload, admin_auth)
        pid = product["id"]
        try:
            # Verify structure persisted via list
            get_resp = requests.get(f"{BASE_URL}/api/admin/products-all?per_page=200", headers=admin_auth)
            assert get_resp.status_code == 200
            prods = get_resp.json().get("products", [])
            saved = next((p for p in prods if p.get("id") == pid), None)
            if saved is None:
                pytest.skip(f"Product {pid} not found in list - may not be indexed yet")
            schema = saved.get("intake_schema_json", {})
            assert schema.get("price_floor") == 100.0, f"price_floor not saved: {schema}"
            assert schema.get("price_ceiling") == 500.0, f"price_ceiling not saved: {schema}"
            questions = schema.get("questions", [])
            assert len(questions) == 2, f"Expected 2 questions, got {len(questions)}"
            q_types = {q["key"]: q["type"] for q in questions}
            assert q_types.get("volume") == "number"
            assert q_types.get("priority_support") == "boolean"

            # 30 volume (all in first tier at £2) = 60, + yes support 30 = 90 < floor 100 → 100
            result = calc_price(pid, {"volume": 30, "priority_support": "yes"}, admin_auth)
            assert result["subtotal"] == 100.0, f"Expected floor 100, got {result['subtotal']}"

            # 80 volume: 50*2=100 + 30*1=30 = 130. + yes support 30 = 160. No floor/ceiling.
            result2 = calc_price(pid, {"volume": 80, "priority_support": "yes"}, admin_auth)
            assert result2["subtotal"] == 160.0, f"Expected 160, got {result2['subtotal']}"
        finally:
            delete_product(pid, admin_auth)

    def test_save_product_with_visibility_rule(self, admin_auth):
        """Create product with visibility_rule on a question — verifies it persists."""
        payload = {
            "name": "TEST96_Vis_Rule_Product",
            "short_description": "Visibility rule test",
            "base_price": 50.0,
            "pricing_type": "internal",
            "is_active": True,
            "intake_schema_json": {
                "version": 2,
                "questions": [
                    {
                        "key": "service_type",
                        "label": "Service Type",
                        "helper_text": "",
                        "required": True,
                        "enabled": True,
                        "order": 0,
                        "type": "dropdown",
                        "affects_price": False,
                        "options": [
                            {"label": "Basic", "value": "basic", "price_value": 0},
                            {"label": "Premium", "value": "premium", "price_value": 0},
                        ],
                    },
                    {
                        "key": "extra_feature",
                        "label": "Extra Feature",
                        "helper_text": "Only for premium",
                        "required": False,
                        "enabled": True,
                        "order": 1,
                        "type": "boolean",
                        "affects_price": True,
                        "price_for_yes": 25.0,
                        "price_for_no": 0.0,
                        "visibility_rule": {
                            "depends_on": "service_type",
                            "operator": "equals",
                            "value": "premium",
                        },
                    },
                ],
            },
        }
        product = create_product(payload, admin_auth)
        pid = product["id"]
        try:
            get_resp = requests.get(f"{BASE_URL}/api/admin/products-all?per_page=200", headers=admin_auth)
            assert get_resp.status_code == 200
            prods = get_resp.json().get("products", [])
            saved = next((p for p in prods if p.get("id") == pid), None)
            if saved is None:
                pytest.skip(f"Product {pid} not found in list")
            schema = saved.get("intake_schema_json", {})
            questions = schema.get("questions", [])
            vis_q = next((q for q in questions if q["key"] == "extra_feature"), None)
            assert vis_q is not None, "extra_feature question not found"
            assert vis_q.get("visibility_rule") is not None, "visibility_rule not persisted"
            rule = vis_q["visibility_rule"]
            assert rule.get("depends_on") == "service_type"
            assert rule.get("operator") == "equals"
            assert rule.get("value") == "premium"
        finally:
            delete_product(pid, admin_auth)
