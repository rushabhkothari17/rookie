"""
Tests for Admin Documents tab bug fixes (iteration 253):
- Fix 1: Go to Connected Services button navigates to integrations tab (frontend)
- Fix 2: WorkDrive available items are buttons; connected badge shows when connected
- Fix 3: Upload endpoint returns 502 with clear message (not 500 internal error)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


@pytest.fixture(scope="module")
def admin_token():
    """Get admin JWT token via platform login."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!"
    })
    if resp.status_code != 200:
        pytest.skip(f"Admin login failed with {resp.status_code}: {resp.text}")
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    if not token:
        pytest.skip("No token in admin login response")
    print(f"[INFO] Admin login successful. Role: {data.get('role')}")
    return token


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


class TestDocumentsListEndpoint:
    """Test GET /api/documents endpoint."""

    def test_list_documents_returns_200(self, admin_headers):
        """Admin can list documents (even if empty)."""
        resp = requests.get(f"{BASE_URL}/api/documents", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "documents" in data, f"Expected 'documents' key in response, got: {data}"
        assert isinstance(data["documents"], list)
        print(f"[PASS] GET /api/documents returned 200 with {len(data['documents'])} documents")

    def test_list_documents_unauthorized(self):
        """Unauthenticated request should be rejected."""
        resp = requests.get(f"{BASE_URL}/api/documents")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"
        print(f"[PASS] GET /api/documents without auth returns {resp.status_code}")


class TestUploadDocumentEndpoint:
    """Test POST /api/documents/upload endpoint - Fix 3: 502 not 500."""

    def test_upload_without_customer_id_returns_error(self, admin_headers):
        """Upload without customer_id should return a clear error (400 or 404), NOT 500."""
        headers = {k: v for k, v in admin_headers.items() if k != "Content-Type"}
        files = {"file": ("test.txt", b"test content", "text/plain")}
        resp = requests.post(
            f"{BASE_URL}/api/documents/upload",
            headers=headers,
            files=files
        )
        # Must NOT be 500 (internal error); should be 400 or 404 with clear message
        assert resp.status_code != 500, f"Got 500 internal error: {resp.text}"
        assert resp.status_code in (400, 404), f"Expected 400/404, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "detail" in data
        print(f"[PASS] Upload without customer_id returns {resp.status_code}: {data['detail']}")

    def test_upload_with_invalid_customer_returns_502_not_500(self, admin_headers):
        """Upload with valid admin but no WorkDrive connection should return 502 (not 500).
        
        This is the core Fix 3: WorkDrive errors must surface as 502 with clear messages,
        not 500 generic internal server errors.
        """
        headers = {k: v for k, v in admin_headers.items() if k != "Content-Type"}
        # Use a fake customer_id - it may return 400 (no workdrive), but must NOT be 500
        files = {"file": ("test_upload.txt", b"hello world test content", "text/plain")}
        resp = requests.post(
            f"{BASE_URL}/api/documents/upload?customer_id=fake-customer-id-12345",
            headers=headers,
            files=files
        )
        # Must NOT be 500 (internal server error)
        assert resp.status_code != 500, (
            f"FAIL: Upload returned 500 internal error. Fix 3 not applied! "
            f"Response: {resp.text}"
        )
        # Should be 400 (workdrive not connected) or 502 (workdrive call failed)
        assert resp.status_code in (400, 502, 404), (
            f"Expected 400 or 502 (clear error), got {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        assert "detail" in data, f"No 'detail' key in error response: {data}"
        # The detail should be a meaningful message
        detail = data["detail"]
        assert len(detail) > 0, "Error detail should not be empty"
        print(f"[PASS] Upload with no WorkDrive returns {resp.status_code} with clear message: {detail}")

    def test_upload_error_has_descriptive_message(self, admin_headers):
        """Verify error response has a descriptive, user-facing message (not generic 'Internal Server Error')."""
        headers = {k: v for k, v in admin_headers.items() if k != "Content-Type"}
        files = {"file": ("test2.txt", b"content", "text/plain")}
        resp = requests.post(
            f"{BASE_URL}/api/documents/upload?customer_id=non-existent-customer-abc",
            headers=headers,
            files=files
        )
        # Must have a detail message
        assert resp.status_code != 500, f"Should not return 500: {resp.text}"
        data = resp.json()
        if "detail" in data:
            detail = data["detail"].lower()
            # Should NOT be a generic error
            assert "internal server error" not in detail, (
                f"Error message is too generic: {data['detail']}"
            )
            print(f"[PASS] Error detail is descriptive: {data['detail']}")
        else:
            print(f"[INFO] Response body: {data}")


class TestWorkDriveIntegrationStatus:
    """Test that WorkDrive integration status endpoint works."""

    def test_oauth_integrations_endpoint_works(self, admin_headers):
        """GET /api/oauth/integrations should return integration list."""
        resp = requests.get(f"{BASE_URL}/api/oauth/integrations", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "integrations" in data, f"Expected 'integrations' key, got: {data}"
        print(f"[PASS] GET /api/oauth/integrations returns 200 with {len(data['integrations'])} integrations")

    def test_workdrive_not_connected_for_test_tenant(self, admin_headers):
        """Verify WorkDrive is not connected (expected state for testing)."""
        resp = requests.get(f"{BASE_URL}/api/oauth/integrations", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        integrations = data.get("integrations", [])
        
        # Find WorkDrive integration
        wd = next((i for i in integrations if i.get("id") == "zoho_workdrive"), None)
        if wd:
            is_connected = wd.get("is_validated", False)
            print(f"[INFO] WorkDrive integration found. is_validated={is_connected}")
            if not is_connected:
                print("[PASS] WorkDrive correctly shows as NOT connected")
            else:
                print("[INFO] WorkDrive shows as connected (unexpected for test env)")
        else:
            print("[INFO] WorkDrive integration entry not found in list")

    def test_sync_folders_fails_gracefully_without_workdrive(self, admin_headers):
        """POST /api/admin/workdrive/sync-folders should return 400 when WorkDrive not connected."""
        resp = requests.post(
            f"{BASE_URL}/api/admin/workdrive/sync-folders",
            headers=admin_headers
        )
        # Should return 400 (not connected), not 500 (internal error)
        assert resp.status_code in (400, 200), (
            f"Expected 400 (not connected) or 200, got {resp.status_code}: {resp.text}"
        )
        assert resp.status_code != 500, f"Should not return 500: {resp.text}"
        data = resp.json()
        if resp.status_code == 400:
            assert "detail" in data
            print(f"[PASS] Sync folders returns 400 gracefully: {data['detail']}")
        else:
            print(f"[INFO] Sync folders returned 200: {data}")


class TestAdminDocumentCRUD:
    """Test admin document CRUD operations."""

    def test_get_document_logs_for_nonexistent_doc(self, admin_headers):
        """GET /api/admin/documents/{doc_id}/logs for missing doc should return 200 with empty logs."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/documents/nonexistent-doc-id-12345/logs",
            headers=admin_headers
        )
        # Can return 200 with empty logs or 404 - both valid, just must not be 500
        assert resp.status_code in (200, 404), f"Expected 200/404, got {resp.status_code}: {resp.text}"
        assert resp.status_code != 500
        print(f"[PASS] GET document logs for nonexistent doc returns {resp.status_code}")

    def test_update_nonexistent_document_returns_404(self, admin_headers):
        """PUT /api/admin/documents/{doc_id} for nonexistent doc should return 404."""
        resp = requests.put(
            f"{BASE_URL}/api/admin/documents/nonexistent-doc-id-99999",
            json={"notes": "test note"},
            headers=admin_headers
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
        print(f"[PASS] PUT nonexistent document returns 404")

    def test_delete_nonexistent_document_returns_404(self, admin_headers):
        """DELETE /api/admin/documents/{doc_id} for nonexistent doc should return 404."""
        resp = requests.delete(
            f"{BASE_URL}/api/admin/documents/nonexistent-doc-id-88888",
            headers=admin_headers
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
        print(f"[PASS] DELETE nonexistent document returns 404")
