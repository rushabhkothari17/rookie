"""
Intake Forms Backend API Tests
Tests for intake_forms and intake_form_records collections
Routes: /api/admin/intake-forms, /api/admin/intake-form-records, /api/portal/intake-forms
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"

# ── Shared fixtures ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_token():
    """Platform admin JWT token."""
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ── GET /admin/intake-forms ────────────────────────────────────────────────────

class TestAdminIntakeFormsCRUD:
    """CRUD tests for intake form definitions"""

    created_form_id = None

    def test_list_intake_forms_empty(self, admin_headers):
        """GET /admin/intake-forms returns list (may be empty)."""
        r = requests.get(f"{BASE_URL}/api/admin/intake-forms", headers=admin_headers)
        assert r.status_code == 200, f"Expected 200: {r.text}"
        data = r.json()
        assert "forms" in data, "Response missing 'forms' key"
        assert isinstance(data["forms"], list)
        print(f"PASS: GET /admin/intake-forms — {len(data['forms'])} forms found")

    def test_create_intake_form(self, admin_headers):
        """POST /admin/intake-forms creates a new form."""
        payload = {
            "name": "TEST_Client Intake Questionnaire",
            "description": "Test intake form description",
            "form_schema": '[{"id":"f_001","key":"business_type","label":"Business Type","type":"text","required":true,"placeholder":"","options":[],"locked":false,"enabled":true,"order":0}]',
            "is_enabled": True,
            "auto_approve": False,
            "allow_skip_signature": False,
        }
        r = requests.post(f"{BASE_URL}/api/admin/intake-forms", json=payload, headers=admin_headers)
        assert r.status_code == 200, f"Create form failed: {r.text}"
        data = r.json()
        assert "form" in data
        form = data["form"]
        assert form["name"] == payload["name"]
        assert form["is_enabled"] == True
        assert form["auto_approve"] == False
        assert "id" in form
        assert "tenant_id" in form
        TestAdminIntakeFormsCRUD.created_form_id = form["id"]
        print(f"PASS: POST /admin/intake-forms — form created: {form['id']}")

    def test_get_intake_form_by_id(self, admin_headers):
        """GET /admin/intake-forms/{form_id} returns specific form."""
        form_id = TestAdminIntakeFormsCRUD.created_form_id
        if not form_id:
            pytest.skip("No form created in previous test")
        r = requests.get(f"{BASE_URL}/api/admin/intake-forms/{form_id}", headers=admin_headers)
        assert r.status_code == 200, f"Get form by ID failed: {r.text}"
        data = r.json()
        assert data["form"]["id"] == form_id
        assert data["form"]["name"] == "TEST_Client Intake Questionnaire"
        print(f"PASS: GET /admin/intake-forms/{form_id} — form retrieved")

    def test_update_intake_form(self, admin_headers):
        """PUT /admin/intake-forms/{form_id} updates the form."""
        form_id = TestAdminIntakeFormsCRUD.created_form_id
        if not form_id:
            pytest.skip("No form created in previous test")
        payload = {
            "name": "TEST_Updated Intake Form",
            "auto_approve": True,
            "description": "Updated description",
        }
        r = requests.put(f"{BASE_URL}/api/admin/intake-forms/{form_id}", json=payload, headers=admin_headers)
        assert r.status_code == 200, f"Update form failed: {r.text}"
        data = r.json()
        assert "message" in data or "form" in data
        # Verify via GET
        get_r = requests.get(f"{BASE_URL}/api/admin/intake-forms/{form_id}", headers=admin_headers)
        assert get_r.status_code == 200
        updated = get_r.json()["form"]
        assert updated["name"] == "TEST_Updated Intake Form"
        assert updated["auto_approve"] == True
        print(f"PASS: PUT /admin/intake-forms/{form_id} — form updated and verified")

    def test_list_intake_forms_includes_created(self, admin_headers):
        """GET /admin/intake-forms returns created form in list."""
        form_id = TestAdminIntakeFormsCRUD.created_form_id
        if not form_id:
            pytest.skip("No form created")
        r = requests.get(f"{BASE_URL}/api/admin/intake-forms", headers=admin_headers)
        assert r.status_code == 200
        forms = r.json()["forms"]
        ids = [f["id"] for f in forms]
        assert form_id in ids, f"Created form not found in list. IDs: {ids}"
        print(f"PASS: Verified created form appears in list")

    def test_get_nonexistent_form(self, admin_headers):
        """GET /admin/intake-forms/{form_id} returns 404 for non-existent form."""
        r = requests.get(f"{BASE_URL}/api/admin/intake-forms/nonexistent_id_12345", headers=admin_headers)
        assert r.status_code == 404, f"Expected 404: {r.text}"
        print("PASS: Non-existent form returns 404")


# ── GET /admin/intake-form-records ────────────────────────────────────────────

class TestAdminIntakeFormRecords:
    """Tests for intake form records"""

    created_record_id = None

    def test_list_records_empty(self, admin_headers):
        """GET /admin/intake-form-records returns paginated records."""
        r = requests.get(f"{BASE_URL}/api/admin/intake-form-records", headers=admin_headers)
        assert r.status_code == 200, f"Expected 200: {r.text}"
        data = r.json()
        assert "records" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert isinstance(data["records"], list)
        assert data["page"] == 1
        print(f"PASS: GET /admin/intake-form-records — total={data['total']} records")

    def test_list_records_pagination_params(self, admin_headers):
        """GET /admin/intake-form-records supports page and limit query params."""
        r = requests.get(f"{BASE_URL}/api/admin/intake-form-records?page=1&limit=5", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["limit"] == 5
        assert data["page"] == 1
        print("PASS: Pagination params accepted")

    def test_list_records_filter_by_status(self, admin_headers):
        """GET /admin/intake-form-records?status=pending filters correctly."""
        r = requests.get(f"{BASE_URL}/api/admin/intake-form-records?status=pending", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        for record in data["records"]:
            assert record["status"] == "pending", f"Filter not applied: {record['status']}"
        print(f"PASS: Status filter works — {len(data['records'])} pending records")

    def test_create_record_missing_customer(self, admin_headers):
        """POST /admin/intake-form-records returns 404 for invalid customer_id."""
        form_id = TestAdminIntakeFormsCRUD.created_form_id
        if not form_id:
            pytest.skip("No form created")
        r = requests.post(f"{BASE_URL}/api/admin/intake-form-records", json={
            "intake_form_id": form_id,
            "customer_id": "nonexistent_customer_id_12345",
        }, headers=admin_headers)
        assert r.status_code == 404, f"Expected 404 for missing customer: {r.text}"
        print("PASS: Missing customer_id returns 404")

    def test_create_record_missing_form(self, admin_headers):
        """POST /admin/intake-form-records returns 404 for invalid intake_form_id."""
        r = requests.post(f"{BASE_URL}/api/admin/intake-form-records", json={
            "intake_form_id": "nonexistent_form_12345",
            "customer_id": "some_customer_id",
        }, headers=admin_headers)
        assert r.status_code == 404, f"Expected 404 for missing form: {r.text}"
        print("PASS: Missing form_id returns 404")


# ── Status Update ──────────────────────────────────────────────────────────────

class TestStatusUpdate:
    """Tests for status update endpoints"""

    def test_update_invalid_status(self, admin_headers):
        """PUT /admin/intake-form-records/{id}/status rejects invalid status."""
        # Use a non-existent record — should fail
        r = requests.put(
            f"{BASE_URL}/api/admin/intake-form-records/fake_record_id_999/status",
            json={"status": "invalid_status"},
            headers=admin_headers
        )
        # Should be either 400 (invalid status) or 404 (record not found)
        assert r.status_code in [400, 404], f"Expected 400 or 404: {r.status_code} {r.text}"
        print(f"PASS: Invalid status returns {r.status_code}")

    def test_update_nonexistent_record_status(self, admin_headers):
        """PUT /admin/intake-form-records/{id}/status returns 404 for missing record."""
        r = requests.put(
            f"{BASE_URL}/api/admin/intake-form-records/nonexistent_record_9999/status",
            json={"status": "approved"},
            headers=admin_headers
        )
        # Invalid status checked first (400) OR record not found (404)
        assert r.status_code in [404, 400], f"Expected 404/400: {r.text}"
        print(f"PASS: Non-existent record status update returns {r.status_code}")


# ── Portal Endpoints ──────────────────────────────────────────────────────────

class TestPortalEndpoints:
    """Tests for portal endpoints — require customer auth"""

    def test_portal_pending_check_without_auth(self):
        """GET /portal/intake-forms/pending-check requires authentication."""
        r = requests.get(f"{BASE_URL}/api/portal/intake-forms/pending-check")
        # Should be 401 or 403 (not 200)
        assert r.status_code in [401, 403, 422], f"Expected 401/403/422 without auth: {r.text}"
        print(f"PASS: Portal pending-check requires auth — {r.status_code}")

    def test_portal_intake_forms_without_auth(self):
        """GET /portal/intake-forms requires authentication."""
        r = requests.get(f"{BASE_URL}/api/portal/intake-forms")
        assert r.status_code in [401, 403, 422], f"Expected 401/403/422 without auth: {r.text}"
        print(f"PASS: Portal intake-forms requires auth — {r.status_code}")

    def test_portal_pending_check_with_admin_token(self, admin_headers):
        """GET /portal/intake-forms/pending-check returns 403 for admin (not customer role)."""
        r = requests.get(f"{BASE_URL}/api/portal/intake-forms/pending-check", headers=admin_headers)
        # Admin user has platform_super_admin role, not customer — should return 403
        assert r.status_code == 403, f"Expected 403 for non-customer: {r.status_code} {r.text}"
        print(f"PASS: Portal pending-check returns 403 for admin role")

    def test_portal_intake_forms_with_admin_token(self, admin_headers):
        """GET /portal/intake-forms returns 403 for admin (not customer role)."""
        r = requests.get(f"{BASE_URL}/api/portal/intake-forms", headers=admin_headers)
        assert r.status_code == 403, f"Expected 403 for non-customer: {r.status_code} {r.text}"
        print(f"PASS: Portal intake-forms returns 403 for admin role")


# ── Notes endpoint ────────────────────────────────────────────────────────────

class TestNotesEndpoint:
    """Tests for notes on intake form records"""

    def test_add_note_to_nonexistent_record(self, admin_headers):
        """POST /admin/intake-form-records/{id}/notes returns 404 for missing record."""
        r = requests.post(
            f"{BASE_URL}/api/admin/intake-form-records/nonexistent_record_id/notes",
            json={"text": "This is a test note"},
            headers=admin_headers
        )
        assert r.status_code == 404, f"Expected 404: {r.text}"
        print("PASS: Notes on non-existent record returns 404")


# ── Full workflow: create form → create record (with customer) ─────────────────

class TestFullWorkflow:
    """Test complete workflow with real customer if available"""

    def test_create_form_with_tc_schema(self, admin_headers):
        """POST /admin/intake-forms creates form with T&C and signature fields."""
        tc_schema = '[{"id":"f_tc","key":"terms_conditions","label":"Terms & Conditions","type":"terms_conditions","required":false,"placeholder":"","options":[],"locked":false,"enabled":true,"order":0,"terms_text":"By signing below, you agree to our terms."},{"id":"f_sig","key":"signature","label":"Signature","type":"signature","required":true,"placeholder":"","options":[],"locked":true,"enabled":true,"order":1}]'
        payload = {
            "name": "TEST_TC Signature Form",
            "description": "Form with T&C and signature",
            "form_schema": tc_schema,
            "is_enabled": True,
            "auto_approve": True,
            "allow_skip_signature": True,
        }
        r = requests.post(f"{BASE_URL}/api/admin/intake-forms", json=payload, headers=admin_headers)
        assert r.status_code == 200, f"Create TC form failed: {r.text}"
        data = r.json()
        form = data["form"]
        assert form["auto_approve"] == True
        assert form["allow_skip_signature"] == True
        print(f"PASS: T&C + Signature form created: {form['id']}")

    def test_admin_intake_forms_unauthorized(self):
        """GET /admin/intake-forms returns 401/403 without token."""
        r = requests.get(f"{BASE_URL}/api/admin/intake-forms")
        assert r.status_code in [401, 403, 422], f"Expected 401/403/422: {r.status_code}"
        print(f"PASS: Admin intake-forms requires auth — {r.status_code}")

    def test_admin_intake_form_records_unauthorized(self):
        """GET /admin/intake-form-records returns 401/403 without token."""
        r = requests.get(f"{BASE_URL}/api/admin/intake-form-records")
        assert r.status_code in [401, 403, 422], f"Expected 401/403/422: {r.status_code}"
        print(f"PASS: Admin intake-form-records requires auth — {r.status_code}")


# ── Cleanup fixture ───────────────────────────────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def cleanup(admin_headers):
    """Cleanup TEST_ prefixed intake forms after tests."""
    yield
    # Delete test forms
    try:
        r = requests.get(f"{BASE_URL}/api/admin/intake-forms", headers=admin_headers)
        if r.status_code == 200:
            for form in r.json().get("forms", []):
                if form.get("name", "").startswith("TEST_"):
                    requests.delete(f"{BASE_URL}/api/admin/intake-forms/{form['id']}", headers=admin_headers)
        print("Cleanup: TEST_ forms deleted")
    except Exception as e:
        print(f"Cleanup failed: {e}")
