"""
Iteration 142: Integration Requests Feature Tests
Tests for the integration requests API endpoints.
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test data
PLATFORM_ADMIN_EMAIL = "admin@automateaccounts.local"
PLATFORM_ADMIN_PASSWORD = "ChangeMe123!"
PARTNER_ADMIN_EMAIL = "test.integration.partner@iter142.test"
PARTNER_ADMIN_PASSWORD = "TestIntegReq142!"

_platform_token = None
_partner_token = None
_created_request_id = None


def get_platform_token():
    global _platform_token
    if not _platform_token:
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PLATFORM_ADMIN_EMAIL,
            "password": PLATFORM_ADMIN_PASSWORD
        })
        if resp.status_code == 200:
            _platform_token = resp.json().get("token")
        time.sleep(1)
    return _platform_token


def get_partner_token():
    global _partner_token
    if not _partner_token:
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PARTNER_ADMIN_EMAIL,
            "password": PARTNER_ADMIN_PASSWORD
        })
        if resp.status_code == 200:
            _partner_token = resp.json().get("token")
        time.sleep(1)
    return _partner_token


class TestIntegrationRequestsSecurity:
    """Test access control for integration requests endpoints."""

    def test_platform_admin_can_list_requests(self):
        """Platform admin: GET /api/integration-requests returns 200."""
        token = get_platform_token()
        if not token:
            pytest.skip("Could not get platform admin token")
        resp = requests.get(f"{BASE_URL}/api/integration-requests",
                            headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "integration_requests" in data
        assert isinstance(data["integration_requests"], list)

    def test_partner_admin_cannot_list_requests(self):
        """Partner admin: GET /api/integration-requests returns 403."""
        token = get_partner_token()
        if not token:
            pytest.skip("Could not get partner admin token")
        resp = requests.get(f"{BASE_URL}/api/integration-requests",
                            headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
        assert "Platform admin access required" in resp.json().get("detail", "")

    def test_platform_admin_cannot_submit_request(self):
        """Platform admin: POST /api/integration-requests returns 403."""
        token = get_platform_token()
        if not token:
            pytest.skip("Could not get platform admin token")
        resp = requests.post(f"{BASE_URL}/api/integration-requests",
                             headers={"Authorization": f"Bearer {token}"},
                             json={"integration_name": "Test", "contact_email": "admin@test.com"})
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
        assert "Platform admins cannot submit requests" in resp.json().get("detail", "")

    def test_unauthenticated_cannot_list_requests(self):
        """Unauthenticated: GET /api/integration-requests returns 401/403."""
        resp = requests.get(f"{BASE_URL}/api/integration-requests")
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"

    def test_unauthenticated_cannot_submit_request(self):
        """Unauthenticated: POST /api/integration-requests returns 401/403."""
        resp = requests.post(f"{BASE_URL}/api/integration-requests",
                             json={"integration_name": "Test", "contact_email": "test@test.com"})
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"


class TestIntegrationRequestsCRUD:
    """Test full CRUD flow for integration requests."""

    def test_partner_admin_can_submit_request(self):
        """Partner admin can submit an integration request."""
        global _created_request_id
        token = get_partner_token()
        if not token:
            pytest.skip("Could not get partner admin token")
        resp = requests.post(f"{BASE_URL}/api/integration-requests",
                             headers={"Authorization": f"Bearer {token}"},
                             json={
                                 "integration_name": "TEST Pytest Integration",
                                 "description": "Automated pytest test integration request",
                                 "contact_email": PARTNER_ADMIN_EMAIL,
                                 "contact_phone": "5559876543",
                                 "phone_country_code": "+1"
                             })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "integration_request" in data
        req = data["integration_request"]

        # Validate response structure and values
        assert req.get("id"), "Should have an ID"
        assert req.get("integration_name") == "TEST Pytest Integration"
        assert req.get("status") == "Pending", f"Initial status should be Pending, got {req.get('status')}"
        assert req.get("contact_email") == PARTNER_ADMIN_EMAIL
        assert req.get("contact_phone") == "5559876543"
        assert req.get("phone_country_code") == "+1"
        assert req.get("description") == "Automated pytest test integration request"
        assert req.get("notes") == []
        assert req.get("created_at") is not None
        assert "_id" not in req, "MongoDB _id should not be in response"

        _created_request_id = req["id"]

    def test_platform_admin_can_see_submitted_request(self):
        """Platform admin: submitted request appears in list."""
        token = get_platform_token()
        if not token:
            pytest.skip("Could not get platform admin token")
        if not _created_request_id:
            pytest.skip("No request was created in previous test")
        resp = requests.get(f"{BASE_URL}/api/integration-requests",
                            headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        requests_list = resp.json().get("integration_requests", [])
        ids = [r.get("id") for r in requests_list]
        assert _created_request_id in ids, f"Created request {_created_request_id} not in list"

    def test_platform_admin_can_update_status(self):
        """Platform admin: can update request status."""
        token = get_platform_token()
        if not token:
            pytest.skip("Could not get platform admin token")
        if not _created_request_id:
            pytest.skip("No request was created")
        resp = requests.put(f"{BASE_URL}/api/integration-requests/{_created_request_id}/status",
                            headers={"Authorization": f"Bearer {token}"},
                            json={"status": "Working"})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        req = resp.json().get("integration_request", {})
        assert req.get("status") == "Working"

    def test_platform_admin_can_change_status_to_all_options(self):
        """Platform admin: can update to any valid status."""
        token = get_platform_token()
        if not token:
            pytest.skip("Could not get platform admin token")
        if not _created_request_id:
            pytest.skip("No request was created")
        for status in ["Not Started", "Future", "Rejected", "Completed", "Pending"]:
            resp = requests.put(
                f"{BASE_URL}/api/integration-requests/{_created_request_id}/status",
                headers={"Authorization": f"Bearer {token}"},
                json={"status": status}
            )
            assert resp.status_code == 200, f"Status {status} failed: {resp.status_code}"
            assert resp.json().get("integration_request", {}).get("status") == status
            time.sleep(0.3)

    def test_invalid_status_returns_400(self):
        """Platform admin: invalid status returns 400."""
        token = get_platform_token()
        if not token:
            pytest.skip("Could not get platform admin token")
        if not _created_request_id:
            pytest.skip("No request was created")
        resp = requests.put(f"{BASE_URL}/api/integration-requests/{_created_request_id}/status",
                            headers={"Authorization": f"Bearer {token}"},
                            json={"status": "InvalidStatus"})
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"

    def test_platform_admin_can_add_note(self):
        """Platform admin: can add a note to a request."""
        token = get_platform_token()
        if not token:
            pytest.skip("Could not get platform admin token")
        if not _created_request_id:
            pytest.skip("No request was created")
        resp = requests.post(
            f"{BASE_URL}/api/integration-requests/{_created_request_id}/notes",
            headers={"Authorization": f"Bearer {token}"},
            json={"text": "TEST NOTE from pytest iter142"}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        req = resp.json().get("integration_request", {})
        notes = req.get("notes", [])
        assert len(notes) >= 1, "Should have at least one note"
        note_texts = [n.get("text") for n in notes]
        assert "TEST NOTE from pytest iter142" in note_texts

    def test_partner_admin_cannot_add_note(self):
        """Partner admin: cannot add a note (403)."""
        token = get_partner_token()
        if not token:
            pytest.skip("Could not get partner admin token")
        if not _created_request_id:
            pytest.skip("No request was created")
        resp = requests.post(
            f"{BASE_URL}/api/integration-requests/{_created_request_id}/notes",
            headers={"Authorization": f"Bearer {token}"},
            json={"text": "partner should not add notes"}
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"

    def test_partner_admin_cannot_update_status(self):
        """Partner admin: cannot update status (403)."""
        token = get_partner_token()
        if not token:
            pytest.skip("Could not get partner admin token")
        if not _created_request_id:
            pytest.skip("No request was created")
        resp = requests.put(f"{BASE_URL}/api/integration-requests/{_created_request_id}/status",
                            headers={"Authorization": f"Bearer {token}"},
                            json={"status": "Completed"})
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"

    def test_submit_request_requires_integration_name(self):
        """Partner admin: submit without integration_name gets 422."""
        token = get_partner_token()
        if not token:
            pytest.skip("Could not get partner admin token")
        resp = requests.post(f"{BASE_URL}/api/integration-requests",
                             headers={"Authorization": f"Bearer {token}"},
                             json={"contact_email": "test@test.com"})
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"

    def test_submit_request_requires_contact_email(self):
        """Partner admin: submit without contact_email gets 422."""
        token = get_partner_token()
        if not token:
            pytest.skip("Could not get partner admin token")
        resp = requests.post(f"{BASE_URL}/api/integration-requests",
                             headers={"Authorization": f"Bearer {token}"},
                             json={"integration_name": "Test"}
                             )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"

    def test_nonexistent_request_status_update_returns_404(self):
        """Platform admin: updating nonexistent request returns 404."""
        token = get_platform_token()
        if not token:
            pytest.skip("Could not get platform admin token")
        resp = requests.put(f"{BASE_URL}/api/integration-requests/nonexistent-id-12345/status",
                            headers={"Authorization": f"Bearer {token}"},
                            json={"status": "Working"})
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"

    def test_response_does_not_include_mongo_id(self):
        """Verify _id is not in any response."""
        token = get_platform_token()
        if not token:
            pytest.skip("Could not get platform admin token")
        resp = requests.get(f"{BASE_URL}/api/integration-requests",
                            headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        for req in resp.json().get("integration_requests", []):
            assert "_id" not in req, "MongoDB _id should not be in response"
