"""
Test suite for iteration 139: Dynamic Enquiry Forms Module, Dashboard Integration Alerts,
Admin Panel UI Rearrangements.

Tests:
- Forms CRUD: GET/POST/PUT/DELETE /api/admin/forms
- PDF endpoint: GET /api/admin/enquiries/{order_id}/pdf
- Backend registration of forms router
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"


@pytest.fixture(scope="module")
def admin_token():
    """Get auth token for platform admin."""
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    if resp.status_code == 200:
        data = resp.json()
        token = data.get("token") or data.get("access_token")
        if token:
            return token
    pytest.skip(f"Admin login failed: {resp.status_code} {resp.text[:200]}")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ── Forms CRUD tests ───────────────────────────────────────────────────────────

def test_get_forms_returns_list(auth_headers):
    """GET /api/admin/forms should return a list (even if empty)."""
    resp = requests.get(f"{BASE_URL}/api/admin/forms", headers=auth_headers)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "forms" in data, f"Response missing 'forms' key: {data}"
    assert isinstance(data["forms"], list), "Forms should be a list"
    print(f"PASS: GET /api/admin/forms returned {len(data['forms'])} forms")


def test_create_form_success(auth_headers):
    """POST /api/admin/forms should create a form with name and form_schema."""
    payload = {"name": "TEST_Project Brief Form", "form_schema": "[]"}
    resp = requests.post(f"{BASE_URL}/api/admin/forms", json=payload, headers=auth_headers)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "form" in data, f"Response missing 'form' key: {data}"
    form = data["form"]
    assert form["name"] == "TEST_Project Brief Form", f"Name mismatch: {form}"
    assert "id" in form, "Form should have an id"
    assert "created_at" in form, "Form should have created_at"
    print(f"PASS: POST /api/admin/forms created form id={form['id']}")


def test_create_form_missing_name(auth_headers):
    """POST /api/admin/forms without name should return 422."""
    payload = {"form_schema": "[]"}
    resp = requests.post(f"{BASE_URL}/api/admin/forms", json=payload, headers=auth_headers)
    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
    print("PASS: POST /api/admin/forms without name returns 422")


def test_create_update_delete_form(auth_headers):
    """Full cycle: Create → Update → Verify → Delete."""
    # Create
    create_resp = requests.post(
        f"{BASE_URL}/api/admin/forms",
        json={"name": "TEST_UpdateDelete", "form_schema": "[]"},
        headers=auth_headers,
    )
    assert create_resp.status_code == 200, f"Create failed: {create_resp.text}"
    form_id = create_resp.json()["form"]["id"]

    # Update
    update_resp = requests.put(
        f"{BASE_URL}/api/admin/forms/{form_id}",
        json={"name": "TEST_UpdateDelete-Renamed", "form_schema": '[{"type":"text","label":"Name"}]'},
        headers=auth_headers,
    )
    assert update_resp.status_code == 200, f"Update failed: {update_resp.text}"
    print(f"PASS: PUT /api/admin/forms/{form_id} succeeded")

    # Verify via GET list
    list_resp = requests.get(f"{BASE_URL}/api/admin/forms", headers=auth_headers)
    assert list_resp.status_code == 200
    forms = list_resp.json().get("forms", [])
    updated = next((f for f in forms if f["id"] == form_id), None)
    assert updated is not None, "Updated form should still exist"
    assert updated["name"] == "TEST_UpdateDelete-Renamed", f"Name not updated: {updated}"
    print("PASS: Updated form name confirmed via GET list")

    # Delete
    del_resp = requests.delete(f"{BASE_URL}/api/admin/forms/{form_id}", headers=auth_headers)
    assert del_resp.status_code == 200, f"Delete failed: {del_resp.text}"
    print(f"PASS: DELETE /api/admin/forms/{form_id} succeeded")

    # Verify deletion
    list_resp2 = requests.get(f"{BASE_URL}/api/admin/forms", headers=auth_headers)
    forms2 = list_resp2.json().get("forms", [])
    assert not any(f["id"] == form_id for f in forms2), "Deleted form should not appear in list"
    print("PASS: Deleted form absent from GET list")


def test_update_nonexistent_form(auth_headers):
    """PUT /api/admin/forms/{bad_id} should return 404."""
    resp = requests.put(
        f"{BASE_URL}/api/admin/forms/nonexistent-form-id-12345",
        json={"name": "Should Fail"},
        headers=auth_headers,
    )
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
    print("PASS: PUT /api/admin/forms/nonexistent returns 404")


def test_delete_nonexistent_form(auth_headers):
    """DELETE /api/admin/forms/{bad_id} should return 404."""
    resp = requests.delete(
        f"{BASE_URL}/api/admin/forms/nonexistent-form-id-99999",
        headers=auth_headers,
    )
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
    print("PASS: DELETE /api/admin/forms/nonexistent returns 404")


# ── PDF endpoint tests ─────────────────────────────────────────────────────────

def test_pdf_endpoint_nonexistent_order(auth_headers):
    """GET /api/admin/enquiries/{bad_id}/pdf should return 404."""
    resp = requests.get(
        f"{BASE_URL}/api/admin/enquiries/nonexistent-order-id-00000/pdf",
        headers=auth_headers,
    )
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
    print("PASS: GET /api/admin/enquiries/nonexistent/pdf returns 404")


def test_pdf_endpoint_unauthenticated():
    """GET /api/admin/enquiries/{id}/pdf without auth should return 401/403."""
    resp = requests.get(
        f"{BASE_URL}/api/admin/enquiries/some-order-id/pdf",
    )
    assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}: {resp.text}"
    print(f"PASS: PDF endpoint unauthenticated returns {resp.status_code}")


# ── Cleanup test data ──────────────────────────────────────────────────────────

def test_cleanup_test_forms(auth_headers):
    """Clean up any TEST_ forms created during testing."""
    list_resp = requests.get(f"{BASE_URL}/api/admin/forms", headers=auth_headers)
    if list_resp.status_code != 200:
        print("Cleanup skipped: could not list forms")
        return
    forms = list_resp.json().get("forms", [])
    deleted = 0
    for form in forms:
        if form.get("name", "").startswith("TEST_"):
            del_resp = requests.delete(f"{BASE_URL}/api/admin/forms/{form['id']}", headers=auth_headers)
            if del_resp.status_code == 200:
                deleted += 1
    print(f"Cleanup: Deleted {deleted} TEST_ forms")
