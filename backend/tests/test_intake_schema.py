"""
Backend tests for Intake Questions / Intake Schema feature.
Tests: product create/update with intake_schema_json, validation, audit logs.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"

TEST_PRODUCT_ID = "fc5d2e93-4adc-4db8-9ac9-f4df3e416e7a"


@pytest.fixture(scope="module")
def admin_token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ── Helper: minimal valid product payload ─────────────────────────────────────
def base_product_payload(name: str, intake_schema: dict = None) -> dict:
    payload = {
        "name": name,
        "short_description": "Test product for intake schema",
        "description_long": "",
        "bullets": [],
        "category": "",
        "base_price": 100.0,
        "is_subscription": False,
        "pricing_complexity": "SIMPLE",
        "is_active": True,
        "pricing_rules": {},
    }
    if intake_schema is not None:
        payload["intake_schema_json"] = intake_schema
    return payload


# ── Test 1: Fetch existing test product with intake schema ────────────────────
class TestIntakeSchemaRead:
    """Verify that the seeded test product has intake_schema_json properly stored."""

    def test_product_has_intake_schema(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/products/{TEST_PRODUCT_ID}", headers=admin_headers)
        assert resp.status_code == 200, f"Product fetch failed: {resp.text}"
        p = resp.json()["product"]
        assert "intake_schema_json" in p, "intake_schema_json not found on product"
        ij = p["intake_schema_json"]
        assert "version" in ij
        assert "questions" in ij
        assert ij["version"] >= 1

    def test_dropdown_question_structure(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/products/{TEST_PRODUCT_ID}", headers=admin_headers)
        p = resp.json()["product"]
        dropdowns = p["intake_schema_json"]["questions"].get("dropdown", [])
        assert len(dropdowns) >= 1, "Expected at least one dropdown question"
        q = dropdowns[0]
        assert q.get("key") == "company_size"
        assert "label" in q
        assert "options" in q
        assert len(q["options"]) >= 1

    def test_admin_products_all_includes_intake_schema(self, admin_headers):
        """Admin products-all endpoint should return products with intake_schema_json (search by name)."""
        resp = requests.get(f"{BASE_URL}/api/admin/products-all?search=Intake+Test&per_page=50", headers=admin_headers)
        assert resp.status_code == 200
        products = resp.json()["products"]
        target = next((p for p in products if p["id"] == TEST_PRODUCT_ID), None)
        assert target is not None, f"Test product not found in admin products-all. Products returned: {[p.get('name') for p in products]}"
        assert "intake_schema_json" in target


# ── Test 2: Create product WITH intake schema ─────────────────────────────────
class TestIntakeSchemaCreate:
    """Create products with various intake schemas."""

    created_ids = []

    def test_create_product_with_dropdown_schema(self, admin_headers):
        schema = {
            "version": 1,
            "questions": {
                "dropdown": [
                    {
                        "key": "TEST_company_type",
                        "label": "Company Type",
                        "helper_text": "Pick your type",
                        "required": True,
                        "enabled": True,
                        "order": 0,
                        "affects_price": False,
                        "options": [
                            {"label": "Startup", "value": "startup"},
                            {"label": "Enterprise", "value": "enterprise"},
                        ],
                    }
                ],
                "multiselect": [],
                "single_line": [],
                "multi_line": [],
            },
        }
        payload = base_product_payload("TEST_Intake_Dropdown_Product", intake_schema=schema)
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        product = resp.json()["product"]
        assert "intake_schema_json" in product
        ij = product["intake_schema_json"]
        assert ij["version"] == 1
        assert ij["updated_by"] == ADMIN_EMAIL
        assert len(ij["questions"]["dropdown"]) == 1
        TestIntakeSchemaCreate.created_ids.append(product["id"])

    def test_create_product_with_single_line_schema(self, admin_headers):
        schema = {
            "version": 1,
            "questions": {
                "dropdown": [],
                "multiselect": [],
                "single_line": [
                    {
                        "key": "TEST_contact_name",
                        "label": "Contact Name",
                        "helper_text": "Your name",
                        "required": True,
                        "enabled": True,
                        "order": 0,
                        "affects_price": False,
                        "options": [],
                    }
                ],
                "multi_line": [],
            },
        }
        payload = base_product_payload("TEST_Intake_SingleLine_Product", intake_schema=schema)
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        product = resp.json()["product"]
        TestIntakeSchemaCreate.created_ids.append(product["id"])
        ij = product["intake_schema_json"]
        assert len(ij["questions"]["single_line"]) == 1

    def test_create_product_with_multiselect_schema(self, admin_headers):
        schema = {
            "version": 1,
            "questions": {
                "dropdown": [],
                "multiselect": [
                    {
                        "key": "TEST_apps_used",
                        "label": "Apps Used",
                        "helper_text": "Select all that apply",
                        "required": False,
                        "enabled": True,
                        "order": 0,
                        "affects_price": True,
                        "options": [
                            {"label": "Zoho CRM", "value": "zoho_crm"},
                            {"label": "Zoho Books", "value": "zoho_books"},
                        ],
                    }
                ],
                "single_line": [],
                "multi_line": [],
            },
        }
        payload = base_product_payload("TEST_Intake_Multiselect_Product", intake_schema=schema)
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        product = resp.json()["product"]
        TestIntakeSchemaCreate.created_ids.append(product["id"])
        ij = product["intake_schema_json"]
        assert len(ij["questions"]["multiselect"]) == 1
        assert ij["questions"]["multiselect"][0]["affects_price"] is True

    def test_created_product_persisted_in_db(self, admin_headers):
        """Re-fetch one of the created products to verify persistence."""
        if not TestIntakeSchemaCreate.created_ids:
            pytest.skip("No products created in this test run")
        pid = TestIntakeSchemaCreate.created_ids[0]
        resp = requests.get(f"{BASE_URL}/api/products/{pid}", headers=admin_headers)
        assert resp.status_code == 200
        p = resp.json()["product"]
        assert "intake_schema_json" in p
        assert p["intake_schema_json"]["questions"]["dropdown"][0]["key"] == "TEST_company_type"


# ── Test 3: Update product with new intake schema ─────────────────────────────
class TestIntakeSchemaUpdate:
    """Update existing product intake schema and verify version bump."""

    def test_update_intake_schema_bumps_version(self, admin_headers):
        # Fetch current version
        resp = requests.get(f"{BASE_URL}/api/products/{TEST_PRODUCT_ID}", headers=admin_headers)
        current_version = resp.json()["product"]["intake_schema_json"]["version"]

        # Build update payload with same dropdown question
        p = resp.json()["product"]
        update_payload = {
            "name": p["name"],
            "is_active": p.get("is_active", True),
            "pricing_rules": p.get("pricing_rules", {}),
            "intake_schema_json": {
                "version": current_version,
                "questions": {
                    "dropdown": [
                        {
                            "key": "company_size",
                            "label": "Company Size",
                            "helper_text": "How large is your company?",
                            "required": True,
                            "enabled": True,
                            "order": 0,
                            "affects_price": False,
                            "options": [
                                {"label": "1–10", "value": "1_10"},
                                {"label": "11–50", "value": "11_50"},
                                {"label": "50+", "value": "50_plus"},
                            ],
                        }
                    ],
                    "multiselect": [],
                    "single_line": [],
                    "multi_line": [],
                },
            },
        }
        resp2 = requests.put(f"{BASE_URL}/api/admin/products/{TEST_PRODUCT_ID}", json=update_payload, headers=admin_headers)
        assert resp2.status_code == 200, f"Update failed: {resp2.text}"

        # Verify version bumped
        resp3 = requests.get(f"{BASE_URL}/api/products/{TEST_PRODUCT_ID}", headers=admin_headers)
        new_version = resp3.json()["product"]["intake_schema_json"]["version"]
        assert new_version == current_version + 1, f"Version not bumped: {current_version} -> {new_version}"

    def test_update_intake_schema_sets_updated_by(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/products/{TEST_PRODUCT_ID}", headers=admin_headers)
        ij = resp.json()["product"]["intake_schema_json"]
        assert ij.get("updated_by") == ADMIN_EMAIL

    def test_update_intake_schema_sets_updated_at(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/products/{TEST_PRODUCT_ID}", headers=admin_headers)
        ij = resp.json()["product"]["intake_schema_json"]
        assert ij.get("updated_at") is not None


# ── Test 4: Backend validation ─────────────────────────────────────────────────
class TestIntakeSchemaValidation:
    """Validation: duplicate keys, missing options, max 10 per type."""

    def test_duplicate_question_key_returns_400(self, admin_headers):
        schema = {
            "version": 1,
            "questions": {
                "dropdown": [
                    {
                        "key": "same_key",
                        "label": "Question 1",
                        "required": False,
                        "enabled": True,
                        "order": 0,
                        "affects_price": False,
                        "options": [{"label": "A", "value": "a"}],
                    }
                ],
                "multiselect": [
                    {
                        "key": "same_key",  # Duplicate!
                        "label": "Question 2",
                        "required": False,
                        "enabled": True,
                        "order": 0,
                        "affects_price": False,
                        "options": [{"label": "B", "value": "b"}],
                    }
                ],
                "single_line": [],
                "multi_line": [],
            },
        }
        payload = base_product_payload("TEST_INVALID_dup_keys", intake_schema=schema)
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=admin_headers)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "Duplicate" in resp.json().get("detail", ""), f"Unexpected error: {resp.json()}"

    def test_max_10_dropdown_questions_returns_400(self, admin_headers):
        questions = []
        for i in range(11):
            questions.append({
                "key": f"q_{i}",
                "label": f"Question {i}",
                "required": False,
                "enabled": True,
                "order": i,
                "affects_price": False,
                "options": [{"label": "X", "value": "x"}],
            })
        schema = {
            "version": 1,
            "questions": {
                "dropdown": questions,
                "multiselect": [],
                "single_line": [],
                "multi_line": [],
            },
        }
        payload = base_product_payload("TEST_INVALID_too_many_dropdown", intake_schema=schema)
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=admin_headers)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "Max 10" in resp.json().get("detail", ""), f"Unexpected error: {resp.json()}"

    def test_dropdown_without_options_returns_400(self, admin_headers):
        schema = {
            "version": 1,
            "questions": {
                "dropdown": [
                    {
                        "key": "no_options_q",
                        "label": "Empty Options",
                        "required": False,
                        "enabled": True,
                        "order": 0,
                        "affects_price": False,
                        "options": [],  # Empty options!
                    }
                ],
                "multiselect": [],
                "single_line": [],
                "multi_line": [],
            },
        }
        payload = base_product_payload("TEST_INVALID_empty_options", intake_schema=schema)
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=admin_headers)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"

    def test_empty_question_key_returns_400(self, admin_headers):
        schema = {
            "version": 1,
            "questions": {
                "dropdown": [],
                "multiselect": [],
                "single_line": [
                    {
                        "key": "",  # Empty key!
                        "label": "Test Q",
                        "required": False,
                        "enabled": True,
                        "order": 0,
                        "affects_price": False,
                        "options": [],
                    }
                ],
                "multi_line": [],
            },
        }
        payload = base_product_payload("TEST_INVALID_empty_key", intake_schema=schema)
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=admin_headers)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"

    def test_max_10_multiselect_questions_returns_400(self, admin_headers):
        questions = []
        for i in range(11):
            questions.append({
                "key": f"ms_{i}",
                "label": f"Multiselect {i}",
                "required": False,
                "enabled": True,
                "order": i,
                "affects_price": False,
                "options": [{"label": "X", "value": "x"}],
            })
        schema = {
            "version": 1,
            "questions": {
                "dropdown": [],
                "multiselect": questions,
                "single_line": [],
                "multi_line": [],
            },
        }
        payload = base_product_payload("TEST_INVALID_too_many_multiselect", intake_schema=schema)
        resp = requests.post(f"{BASE_URL}/api/admin/products", json=payload, headers=admin_headers)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"


# ── Test 5: Audit logs include intake_schema details ─────────────────────────
class TestIntakeSchemaAuditLogs:
    """After update, logs endpoint should show intake_schema in details."""

    def test_product_logs_endpoint_accessible(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/products/{TEST_PRODUCT_ID}/logs", headers=admin_headers)
        assert resp.status_code == 200
        logs = resp.json()["logs"]
        assert isinstance(logs, list)
        assert len(logs) > 0, "No logs found for test product"

    def test_update_log_contains_intake_schema_details(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/products/{TEST_PRODUCT_ID}/logs", headers=admin_headers)
        logs = resp.json()["logs"]
        # Find an update log with intake_schema details
        intake_logs = [l for l in logs if l.get("action") == "updated" and "intake_schema" in l.get("details", {})]
        assert len(intake_logs) > 0, f"No update logs with intake_schema details found. Log actions: {[l.get('action') for l in logs]}"
        log = intake_logs[0]
        intake_detail = log["details"]["intake_schema"]
        assert "dropdown" in intake_detail
        assert "version" in intake_detail

    def test_log_actor_is_admin(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/products/{TEST_PRODUCT_ID}/logs", headers=admin_headers)
        logs = resp.json()["logs"]
        intake_logs = [l for l in logs if "intake_schema" in l.get("details", {})]
        if intake_logs:
            actor = intake_logs[0].get("actor", "")
            assert "admin:" in actor or "admin" in actor.lower(), f"Unexpected actor: {actor}"


# ── Test 6: Product detail endpoint returns intake schema for customer ────────
class TestIntakeSchemaCustomerView:
    """Public /api/products/{id} returns intake_schema_json for rendering on detail page."""

    def test_public_product_detail_has_intake_schema(self):
        resp = requests.get(f"{BASE_URL}/api/products/{TEST_PRODUCT_ID}")
        assert resp.status_code == 200
        p = resp.json()["product"]
        assert "intake_schema_json" in p, "intake_schema_json not in public product response"

    def test_public_product_intake_has_enabled_questions(self):
        resp = requests.get(f"{BASE_URL}/api/products/{TEST_PRODUCT_ID}")
        p = resp.json()["product"]
        ij = p["intake_schema_json"]
        dropdowns = ij["questions"].get("dropdown", [])
        assert len(dropdowns) >= 1
        assert dropdowns[0].get("enabled") is True


# ── Cleanup: delete test-created products ────────────────────────────────────
@pytest.fixture(scope="module", autouse=True)
def cleanup(admin_headers):
    yield
    # Delete all TEST_ created products
    for pid in TestIntakeSchemaCreate.created_ids:
        try:
            # Toggle off + soft delete by deactivating
            requests.put(f"{BASE_URL}/api/admin/products/{pid}", 
                        json={"name": f"DELETED_{pid}", "is_active": False, "pricing_rules": {}},
                        headers=admin_headers)
        except Exception:
            pass
