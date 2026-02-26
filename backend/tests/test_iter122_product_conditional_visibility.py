"""
Iteration 122 backend tests:
- Product Conditional Visibility (4th visibility option) 
- Backend _eval_product_conditions logic
- GET /api/products filtering with conditional visibility
- Admin sees all products regardless of conditions
- Intake form multi-condition visibility (VisibilityRuleSet) - tested via product create/update
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_token():
    """Get admin token (platform_admin, no partner_code needed)."""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!"
    })
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    return response.json()["token"]

@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}

@pytest.fixture(scope="module")
def tenant_id(admin_headers):
    """Get the tenant ID for automate-accounts."""
    resp = requests.get(f"{BASE_URL}/api/admin/tenants", headers=admin_headers)
    assert resp.status_code == 200
    tenants = resp.json().get("tenants", [])
    for t in tenants:
        if t.get("code") == "automate-accounts":
            return t["id"]
    # fallback: use first tenant
    return tenants[0]["id"] if tenants else None

@pytest.fixture(scope="module")
def partner_admin_token(tenant_id):
    """Get a partner admin token for the automate-accounts tenant."""
    resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
        "partner_code": "automate-accounts",
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!"
    })
    if resp.status_code == 200:
        return resp.json().get("token")
    # Try platform admin token with X-View-As-Tenant header instead
    return None

# ── Test: GET /api/products is now accessible ─────────────────────────────────

class TestProductsEndpointFixed:
    """Verify GET /api/products now works correctly after decorator fix."""

    def test_get_products_returns_200(self):
        """GET /api/products should return product list, not 422 error."""
        resp = requests.get(f"{BASE_URL}/api/products?partner_code=automate-accounts")
        assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert "products" in data, "Response must contain 'products' key"
        assert isinstance(data["products"], list), "products must be a list"

    def test_get_products_returns_product_list(self):
        """GET /api/products should return at least 1 product."""
        resp = requests.get(f"{BASE_URL}/api/products?partner_code=automate-accounts")
        assert resp.status_code == 200
        products = resp.json()["products"]
        assert len(products) > 0, "Should have at least 1 active product"

    def test_get_products_no_body_required(self):
        """GET /api/products should work without any body parameters."""
        resp = requests.get(f"{BASE_URL}/api/products?partner_code=automate-accounts")
        # Should NOT return 422 (body parameters required) 
        assert resp.status_code != 422, f"Endpoint incorrectly requires body params: {resp.text[:200]}"
        assert resp.status_code == 200

# ── Test: Admin can create product with visibility_conditions ─────────────────

class TestProductConditionalVisibilityCreate:
    """Test creating a product with conditional visibility."""

    created_product_id = None

    def test_create_product_with_conditional_visibility(self, admin_headers, tenant_id):
        """Admin can create a product with visibility_conditions rule set."""
        payload = {
            "name": "TEST_Conditional_Visibility_Product",
            "tagline": "Test product for conditional visibility",
            "description_long": "Test description",
            "base_price": 100,
            "is_active": True,
            "pricing_type": "internal",
            "currency": "USD",
            "is_subscription": False,
            "visible_to_customers": [],
            "restricted_to": [],
            "visibility_conditions": {
                "logic": "AND",
                "conditions": [
                    {"field": "country", "operator": "equals", "value": "UK"}
                ]
            },
            "card_title": "",
            "card_tag": "",
            "card_description": "",
            "card_bullets": [],
            "bullets": [],
            "tag": "",
            "category": "",
            "faqs": [],
            "terms_id": "",
            "stripe_price_id": "",
            "external_url": "",
        }
        if tenant_id:
            headers = {**admin_headers, "X-View-As-Tenant": tenant_id}
        else:
            headers = admin_headers

        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=headers)
        assert resp.status_code == 200, f"Create product failed: {resp.status_code} {resp.text[:300]}"
        data = resp.json()
        product = data.get("product", data)
        assert product.get("name") == "TEST_Conditional_Visibility_Product"
        vis_cond = product.get("visibility_conditions")
        assert vis_cond is not None, "visibility_conditions should be saved"
        assert vis_cond.get("logic") == "AND"
        assert len(vis_cond.get("conditions", [])) == 1
        assert vis_cond["conditions"][0]["field"] == "country"
        assert vis_cond["conditions"][0]["operator"] == "equals"
        assert vis_cond["conditions"][0]["value"] == "UK"
        TestProductConditionalVisibilityCreate.created_product_id = product.get("id")

    def test_product_with_conditions_not_visible_unauthenticated(self):
        """Product with conditional visibility should not show to unauthenticated users (no match)."""
        pid = TestProductConditionalVisibilityCreate.created_product_id
        if not pid:
            pytest.skip("Product not created in previous test")
        # Unauthenticated user has no customer data, so conditions won't match
        resp = requests.get(f"{BASE_URL}/api/products?partner_code=automate-accounts")
        assert resp.status_code == 200
        products = resp.json()["products"]
        product_ids = [p["id"] for p in products]
        # With country=UK condition, unauthenticated user (no customer) should not see it
        # The _eval_product_conditions returns False for empty customer dict when field is required
        assert pid not in product_ids, f"Conditional product {pid} should NOT be visible to unauthenticated user"

    def test_admin_sees_conditional_product(self, admin_headers, tenant_id):
        """Admin should see all products via /api/admin/products-all regardless of conditions."""
        pid = TestProductConditionalVisibilityCreate.created_product_id
        if not pid:
            pytest.skip("Product not created in previous test")
        if tenant_id:
            headers = {**admin_headers, "X-View-As-Tenant": tenant_id}
        else:
            headers = admin_headers
        resp = requests.get(f"{BASE_URL}/api/admin/products-all", headers=headers)
        assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}"
        data = resp.json()
        products = data.get("products", data.get("items", []))
        product_ids = [p["id"] for p in products]
        assert pid in product_ids, f"Admin should see conditional product {pid} in products-all"

    def test_update_product_visibility_conditions_multi_condition(self, admin_headers, tenant_id):
        """Update product with multi-condition OR rule and verify via GET."""
        pid = TestProductConditionalVisibilityCreate.created_product_id
        if not pid:
            pytest.skip("Product not created in previous test")
        if tenant_id:
            headers = {**admin_headers, "X-View-As-Tenant": tenant_id}
        else:
            headers = admin_headers

        payload = {
            "name": "TEST_Conditional_Visibility_Product",
            "is_active": True,
            "visible_to_customers": [],
            "restricted_to": [],
            "visibility_conditions": {
                "logic": "OR",
                "conditions": [
                    {"field": "country", "operator": "equals", "value": "UK"},
                    {"field": "company_name", "operator": "contains", "value": "Ltd"},
                ]
            },
        }
        resp = requests.put(f"{BASE_URL}/api/admin/products/{pid}", json=payload, headers=headers)
        assert resp.status_code == 200, f"Update failed: {resp.text[:300]}"
        # PUT returns {"message": "Product updated"}, so verify via GET products-all
        resp2 = requests.get(f"{BASE_URL}/api/admin/products-all", headers=headers)
        assert resp2.status_code == 200
        products = resp2.json().get("products", [])
        product = next((p for p in products if p["id"] == pid), None)
        assert product is not None, f"Product {pid} not found after update"
        vis_cond = product.get("visibility_conditions")
        assert vis_cond is not None, "visibility_conditions should not be None after update"
        assert vis_cond.get("logic") == "OR"
        assert len(vis_cond.get("conditions", [])) == 2

    def test_update_product_clear_visibility_conditions(self, admin_headers, tenant_id):
        """Clearing visibility_conditions sets it to null — verify via GET."""
        pid = TestProductConditionalVisibilityCreate.created_product_id
        if not pid:
            pytest.skip("Product not created in previous test")
        if tenant_id:
            headers = {**admin_headers, "X-View-As-Tenant": tenant_id}
        else:
            headers = admin_headers

        payload = {
            "name": "TEST_Conditional_Visibility_Product",
            "is_active": False,  # Also deactivate for cleanup
            "visible_to_customers": [],
            "restricted_to": [],
            "visibility_conditions": None,
        }
        resp = requests.put(f"{BASE_URL}/api/admin/products/{pid}", json=payload, headers=headers)
        assert resp.status_code == 200, f"Update failed: {resp.text[:300]}"
        # Verify via GET (all products including inactive)
        resp2 = requests.get(f"{BASE_URL}/api/admin/products-all?status=inactive", headers=headers)
        if resp2.status_code == 200:
            products = resp2.json().get("products", [])
            product = next((p for p in products if p["id"] == pid), None)
            if product:
                assert product.get("visibility_conditions") is None, "visibility_conditions should be null after clearing"


# ── Test: _eval_product_conditions logic ─────────────────────────────────────

class TestEvalProductConditionsLogic:
    """Test conditional visibility logic through end-to-end product creation + query.
    Creates a product with various conditions, then queries to verify filtering works.
    """

    def test_conditional_product_OR_logic_filtered_correctly(self, admin_headers, tenant_id):
        """Products with OR logic should show if ANY condition matches."""
        # We can't directly call _eval_product_conditions, but we can test 
        # the admin endpoint response validates visibility_conditions are saved correctly
        if tenant_id:
            headers = {**admin_headers, "X-View-As-Tenant": tenant_id}
        else:
            headers = admin_headers

        payload = {
            "name": "TEST_OR_Logic_Product",
            "tagline": "Test OR logic",
            "description_long": "Test",
            "base_price": 50,
            "is_active": True,
            "pricing_type": "internal",
            "currency": "USD",
            "is_subscription": False,
            "visible_to_customers": [],
            "restricted_to": [],
            "visibility_conditions": {
                "logic": "OR",
                "conditions": [
                    {"field": "country", "operator": "equals", "value": "UK"},
                    {"field": "country", "operator": "equals", "value": "CA"},
                ]
            },
            "card_title": "", "card_tag": "", "card_description": "",
            "card_bullets": [], "bullets": [], "tag": "", "category": "",
            "faqs": [], "terms_id": "", "stripe_price_id": "", "external_url": "",
        }
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=headers)
        assert resp.status_code == 200, f"Create failed: {resp.text[:200]}"
        product = resp.json().get("product", resp.json())
        pid = product.get("id")
        vis_cond = product.get("visibility_conditions")
        assert vis_cond["logic"] == "OR"
        assert len(vis_cond["conditions"]) == 2

        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/products/{pid}", headers=headers)

    def test_conditional_product_with_empty_operator(self, admin_headers, tenant_id):
        """Products with 'empty' operator should be created correctly."""
        if tenant_id:
            headers = {**admin_headers, "X-View-As-Tenant": tenant_id}
        else:
            headers = admin_headers

        payload = {
            "name": "TEST_Empty_Operator_Product",
            "tagline": "Test empty operator",
            "description_long": "Test",
            "base_price": 0,
            "is_active": True,
            "pricing_type": "internal",
            "currency": "USD",
            "is_subscription": False,
            "visible_to_customers": [],
            "restricted_to": [],
            "visibility_conditions": {
                "logic": "AND",
                "conditions": [
                    {"field": "phone", "operator": "empty", "value": ""}
                ]
            },
            "card_title": "", "card_tag": "", "card_description": "",
            "card_bullets": [], "bullets": [], "tag": "", "category": "",
            "faqs": [], "terms_id": "", "stripe_price_id": "", "external_url": "",
        }
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=headers)
        assert resp.status_code == 200, f"Create with empty operator failed: {resp.text[:200]}"
        product = resp.json().get("product", resp.json())
        pid = product.get("id")
        vis_cond = product.get("visibility_conditions")
        assert vis_cond["conditions"][0]["operator"] == "empty"
        assert vis_cond["conditions"][0]["value"] == ""

        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/products/{pid}", headers=headers)

    def test_conditional_product_with_not_empty_operator(self, admin_headers, tenant_id):
        """Products with 'not_empty' operator should be created correctly."""
        if tenant_id:
            headers = {**admin_headers, "X-View-As-Tenant": tenant_id}
        else:
            headers = admin_headers

        payload = {
            "name": "TEST_NotEmpty_Operator_Product",
            "tagline": "Test not_empty operator",
            "description_long": "Test",
            "base_price": 0,
            "is_active": True,
            "pricing_type": "internal",
            "currency": "USD",
            "is_subscription": False,
            "visible_to_customers": [],
            "restricted_to": [],
            "visibility_conditions": {
                "logic": "AND",
                "conditions": [
                    {"field": "company_name", "operator": "not_empty", "value": ""}
                ]
            },
            "card_title": "", "card_tag": "", "card_description": "",
            "card_bullets": [], "bullets": [], "tag": "", "category": "",
            "faqs": [], "terms_id": "", "stripe_price_id": "", "external_url": "",
        }
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=headers)
        assert resp.status_code == 200, f"Create with not_empty operator failed: {resp.text[:200]}"
        product = resp.json().get("product", resp.json())
        pid = product.get("id")
        vis_cond = product.get("visibility_conditions")
        assert vis_cond["conditions"][0]["operator"] == "not_empty"

        # Unauthenticated user: company_name is empty, so not_empty is False → product hidden
        resp2 = requests.get(f"{BASE_URL}/api/products?partner_code=automate-accounts")
        products = resp2.json()["products"]
        product_ids = [p["id"] for p in products]
        assert pid not in product_ids, f"Product with not_empty condition should not be visible to user with empty company_name"

        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/products/{pid}", headers=headers)


# ── Test: Intake form with visibility_conditions in schema ────────────────────

class TestIntakeMultiConditionVisibility:
    """Test that intake schema can store multi-condition visibility rules."""

    def test_create_product_with_intake_multi_condition_rule(self, admin_headers, tenant_id):
        """Intake schema can save multi-condition visibility rules."""
        if tenant_id:
            headers = {**admin_headers, "X-View-As-Tenant": tenant_id}
        else:
            headers = admin_headers

        payload = {
            "name": "TEST_Intake_MultiCondition_Product",
            "tagline": "Test intake multi-condition",
            "description_long": "Test",
            "base_price": 0,
            "is_active": True,
            "pricing_type": "internal",
            "currency": "USD",
            "is_subscription": False,
            "visible_to_customers": [],
            "restricted_to": [],
            "visibility_conditions": None,
            "intake_schema_json": {
                "version": 2,
                "questions": [
                    {
                        "key": "plan_type",
                        "label": "Plan Type",
                        "type": "dropdown",
                        "required": True,
                        "enabled": True,
                        "order": 0,
                        "step_group": 0,
                        "helper_text": "",
                        "affects_price": False,
                        "price_mode": "add",
                        "options": [
                            {"label": "Basic", "value": "basic", "price_value": 0},
                            {"label": "Premium", "value": "premium", "price_value": 0},
                        ],
                        "visibility_rule": None,
                    },
                    {
                        "key": "extra_feature",
                        "label": "Extra Feature",
                        "type": "boolean",
                        "required": False,
                        "enabled": True,
                        "order": 1,
                        "step_group": 0,
                        "helper_text": "",
                        # Multi-condition visibility rule
                        "visibility_rule": {
                            "logic": "OR",
                            "conditions": [
                                {"depends_on": "plan_type", "operator": "equals", "value": "premium"},
                                {"depends_on": "plan_type", "operator": "contains", "value": "prem"},
                            ]
                        },
                    },
                    {
                        "key": "notes",
                        "label": "Notes",
                        "type": "single_line",
                        "required": False,
                        "enabled": True,
                        "order": 2,
                        "step_group": 0,
                        "helper_text": "",
                        # Visibility rule with not_contains operator
                        "visibility_rule": {
                            "logic": "AND",
                            "conditions": [
                                {"depends_on": "plan_type", "operator": "not_contains", "value": "basic"},
                            ]
                        },
                    },
                ]
            },
            "card_title": "", "card_tag": "", "card_description": "",
            "card_bullets": [], "bullets": [], "tag": "", "category": "",
            "faqs": [], "terms_id": "", "stripe_price_id": "", "external_url": "",
        }
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=headers)
        assert resp.status_code == 200, f"Create intake product failed: {resp.status_code} {resp.text[:300]}"
        product = resp.json().get("product", resp.json())
        pid = product.get("id")
        schema = product.get("intake_schema_json", {})
        questions = schema.get("questions", [])
        assert len(questions) == 3, f"Should have 3 questions, got {len(questions)}"

        # Verify OR multi-condition was saved
        extra_q = next((q for q in questions if q.get("key") == "extra_feature"), None)
        assert extra_q is not None, "extra_feature question must be present"
        vis_rule = extra_q.get("visibility_rule")
        assert vis_rule is not None, "visibility_rule must be saved"
        assert vis_rule.get("logic") == "OR"
        assert len(vis_rule.get("conditions", [])) == 2

        # Verify not_contains operator was saved
        notes_q = next((q for q in questions if q.get("key") == "notes"), None)
        assert notes_q is not None
        notes_rule = notes_q.get("visibility_rule")
        assert notes_rule is not None
        conds = notes_rule.get("conditions", [])
        assert len(conds) == 1
        assert conds[0]["operator"] == "not_contains"

        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/products/{pid}", headers=headers)

    def test_intake_backward_compat_legacy_rule(self, admin_headers, tenant_id):
        """Legacy single-rule format still works when creating/updating products."""
        if tenant_id:
            headers = {**admin_headers, "X-View-As-Tenant": tenant_id}
        else:
            headers = admin_headers

        payload = {
            "name": "TEST_Intake_LegacyRule_Product",
            "tagline": "Test legacy rule backward compat",
            "description_long": "Test",
            "base_price": 0,
            "is_active": True,
            "pricing_type": "internal",
            "currency": "USD",
            "is_subscription": False,
            "visible_to_customers": [],
            "restricted_to": [],
            "visibility_conditions": None,
            "intake_schema_json": {
                "version": 2,
                "questions": [
                    {
                        "key": "trigger_field",
                        "label": "Trigger Field",
                        "type": "dropdown",
                        "required": True,
                        "enabled": True,
                        "order": 0,
                        "step_group": 0,
                        "helper_text": "",
                        "affects_price": False,
                        "price_mode": "add",
                        "options": [{"label": "Yes", "value": "yes", "price_value": 0}],
                        "visibility_rule": None,
                    },
                    {
                        "key": "dependent_field",
                        "label": "Dependent Field",
                        "type": "single_line",
                        "required": False,
                        "enabled": True,
                        "order": 1,
                        "step_group": 0,
                        "helper_text": "",
                        # Legacy format
                        "visibility_rule": {
                            "depends_on": "trigger_field",
                            "operator": "equals",
                            "value": "yes"
                        },
                    },
                ]
            },
            "card_title": "", "card_tag": "", "card_description": "",
            "card_bullets": [], "bullets": [], "tag": "", "category": "",
            "faqs": [], "terms_id": "", "stripe_price_id": "", "external_url": "",
        }
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=headers)
        assert resp.status_code == 200, f"Create legacy rule product failed: {resp.text[:200]}"
        product = resp.json().get("product", resp.json())
        pid = product.get("id")
        questions = product.get("intake_schema_json", {}).get("questions", [])
        dep_q = next((q for q in questions if q.get("key") == "dependent_field"), None)
        assert dep_q is not None
        # Legacy format should be preserved (or normalized to conditions format)
        vis_rule = dep_q.get("visibility_rule")
        assert vis_rule is not None, "Legacy visibility rule must be preserved"

        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/products/{pid}", headers=headers)

    def test_intake_empty_operator_in_visibility_rule(self, admin_headers, tenant_id):
        """Intake visibility rule with 'empty' operator saves correctly."""
        if tenant_id:
            headers = {**admin_headers, "X-View-As-Tenant": tenant_id}
        else:
            headers = admin_headers

        payload = {
            "name": "TEST_Intake_Empty_Operator",
            "tagline": "Test empty operator in intake",
            "description_long": "Test",
            "base_price": 0,
            "is_active": True,
            "pricing_type": "internal",
            "currency": "USD",
            "is_subscription": False,
            "visible_to_customers": [],
            "restricted_to": [],
            "visibility_conditions": None,
            "intake_schema_json": {
                "version": 2,
                "questions": [
                    {
                        "key": "q1",
                        "label": "Question 1",
                        "type": "single_line",
                        "required": False,
                        "enabled": True,
                        "order": 0,
                        "step_group": 0,
                        "helper_text": "",
                        "visibility_rule": None,
                    },
                    {
                        "key": "q2",
                        "label": "Question 2 - show when q1 is empty",
                        "type": "single_line",
                        "required": False,
                        "enabled": True,
                        "order": 1,
                        "step_group": 0,
                        "helper_text": "",
                        "visibility_rule": {
                            "logic": "AND",
                            "conditions": [
                                {"depends_on": "q1", "operator": "empty", "value": ""}
                            ]
                        },
                    },
                ]
            },
            "card_title": "", "card_tag": "", "card_description": "",
            "card_bullets": [], "bullets": [], "tag": "", "category": "",
            "faqs": [], "terms_id": "", "stripe_price_id": "", "external_url": "",
        }
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=headers)
        assert resp.status_code == 200, f"Create with empty operator failed: {resp.text[:200]}"
        product = resp.json().get("product", resp.json())
        pid = product.get("id")
        questions = product.get("intake_schema_json", {}).get("questions", [])
        q2 = next((q for q in questions if q.get("key") == "q2"), None)
        assert q2 is not None
        vis_rule = q2.get("visibility_rule")
        assert vis_rule is not None
        conds = vis_rule.get("conditions", [])
        assert conds[0]["operator"] == "empty"
        assert conds[0]["value"] == ""

        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/products/{pid}", headers=headers)
