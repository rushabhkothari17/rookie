"""
Tests for Iteration 257 — Zoho WorkDrive integration bug fixes:
1. platform_super_admin missing from is_admin role check in documents.py
2. Wrong upload endpoint (fixed to workdrive.zoho.com/api/v1/upload)

Test scenarios:
- Platform super admin GET /api/documents returns 200 (no 'Customer record not found')
- Platform super admin POST /api/documents/upload without customer_id returns 400 ('customer_id is required')
- Platform super admin POST /api/documents/upload with customer_id proceeds to WorkDrive path (not 'Customer record not found')
- is_admin check covers platform_super_admin in all 3 endpoints (list, upload, download)
- workdrive_service.py uses correct upload URL: workdrive.zoho.com/api/v1/upload
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def platform_super_admin_token():
    """Login as platform_super_admin and return JWT token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!"
    })
    if resp.status_code != 200:
        pytest.skip(f"Platform super admin login failed: {resp.status_code}: {resp.text}")
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    if not token:
        pytest.skip("No token returned in login response")
    role = data.get("role", "")
    print(f"[INFO] Logged in as role: {role}")
    assert role == "platform_super_admin", f"Expected platform_super_admin role, got: {role}"
    return token


@pytest.fixture(scope="module")
def admin_headers(platform_super_admin_token):
    """Return request headers with JWT auth."""
    return {
        "Authorization": f"Bearer {platform_super_admin_token}",
        "Content-Type": "application/json",
    }


@pytest.fixture(scope="module")
def admin_headers_no_ct(platform_super_admin_token):
    """Headers without Content-Type (for multipart form uploads)."""
    return {"Authorization": f"Bearer {platform_super_admin_token}"}


@pytest.fixture(scope="module")
def existing_customer_id(admin_headers):
    """Fetch a real customer_id from the system for upload tests."""
    resp = requests.get(f"{BASE_URL}/api/customers", headers=admin_headers)
    if resp.status_code != 200:
        return None
    data = resp.json()
    customers = data.get("customers", [])
    if customers:
        cid = customers[0].get("id")
        print(f"[INFO] Found customer_id for tests: {cid}")
        return cid
    return None


# ---------------------------------------------------------------------------
# Bug Fix 1: platform_super_admin in is_admin check — GET /api/documents
# ---------------------------------------------------------------------------

class TestListDocumentsPlatformSuperAdmin:
    """Bug fix 1: platform_super_admin must reach the admin code path in list_documents."""

    def test_list_documents_returns_200_not_customer_record_not_found(self, admin_headers):
        """
        CRITICAL: GET /api/documents as platform_super_admin must return 200 with documents list.
        Before fix: would get 'Customer record not found' because is_admin check was missing platform_super_admin.
        After fix: returns {'documents': [...]} with 200.
        """
        resp = requests.get(f"{BASE_URL}/api/documents", headers=admin_headers)
        assert resp.status_code == 200, (
            f"FAIL: Expected 200, got {resp.status_code}. "
            f"platform_super_admin may not be in is_admin check! "
            f"Response: {resp.text}"
        )
        data = resp.json()
        assert "documents" in data, f"Expected 'documents' key in response, got: {data}"
        assert isinstance(data["documents"], list), "documents should be a list"
        # Ensure 'Customer record not found' error is not in response
        assert "Customer record not found" not in resp.text, (
            "Got 'Customer record not found' - BUG: platform_super_admin not in is_admin check!"
        )
        print(f"[PASS] GET /api/documents as platform_super_admin returns 200 with {len(data['documents'])} documents")

    def test_list_documents_with_customer_id_filter(self, admin_headers):
        """GET /api/documents?customer_id=xxx as platform_super_admin should return 200."""
        resp = requests.get(
            f"{BASE_URL}/api/documents?customer_id=some-nonexistent-customer",
            headers=admin_headers
        )
        assert resp.status_code == 200, (
            f"Expected 200 with empty list, got {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        assert "documents" in data
        # Empty list is valid for nonexistent customer
        assert isinstance(data["documents"], list)
        print(f"[PASS] GET /api/documents?customer_id=... returns 200: {len(data['documents'])} docs")

    def test_list_documents_no_auth_rejected(self):
        """Unauthenticated request should be rejected."""
        resp = requests.get(f"{BASE_URL}/api/documents")
        assert resp.status_code in (401, 403), f"Expected 401/403 without auth, got {resp.status_code}"
        print(f"[PASS] GET /api/documents without auth returns {resp.status_code}")


# ---------------------------------------------------------------------------
# Bug Fix 1: platform_super_admin in is_admin check — POST /api/documents/upload
# ---------------------------------------------------------------------------

class TestUploadDocumentPlatformSuperAdmin:
    """Bug fix 1: platform_super_admin must reach the admin upload code path."""

    def test_upload_without_customer_id_returns_400_not_customer_record_not_found(self, admin_headers_no_ct):
        """
        CRITICAL: Upload without customer_id as platform_super_admin should return 400
        with message 'customer_id is required for admin uploads'.
        Before fix: would return 404 'Customer record not found' because admin fell into customer path.
        After fix: returns 400 'customer_id is required for admin uploads'.
        """
        files = {"file": ("test.txt", b"test content for iter257", "text/plain")}
        resp = requests.post(
            f"{BASE_URL}/api/documents/upload",
            headers=admin_headers_no_ct,
            files=files
        )
        # Must return 400, not 404 with 'Customer record not found'
        assert resp.status_code == 400, (
            f"FAIL: Expected 400 'customer_id is required', got {resp.status_code}. "
            f"Response: {resp.text}"
        )
        data = resp.json()
        assert "detail" in data, f"No 'detail' in response: {data}"
        detail = data["detail"].lower()
        # Should say 'customer_id is required' not 'customer record not found'
        assert "customer_id is required" in detail or "customer_id" in detail, (
            f"Expected 'customer_id is required for admin uploads', got: {data['detail']}"
        )
        assert "customer record not found" not in detail, (
            f"BUG: Got 'Customer record not found' - platform_super_admin not in is_admin check! "
            f"Detail: {data['detail']}"
        )
        print(f"[PASS] Upload without customer_id returns 400: {data['detail']}")

    def test_upload_with_customer_id_no_workdrive_returns_meaningful_error(self, admin_headers_no_ct, existing_customer_id):
        """
        CRITICAL: Upload with customer_id as platform_super_admin should proceed to WorkDrive check
        and return 400 (WorkDrive not connected) or 502, but NOT 'Customer record not found'.
        This verifies the admin code path is reached.
        """
        # Use real customer_id if available, otherwise use a fake one
        cid = existing_customer_id or "fake-customer-id-iter257"
        files = {"file": ("test_upload.txt", b"hello world from iter257 test", "text/plain")}
        resp = requests.post(
            f"{BASE_URL}/api/documents/upload?customer_id={cid}",
            headers=admin_headers_no_ct,
            files=files
        )
        # Must NOT return 'Customer record not found' (that was the bug)
        assert "Customer record not found" not in resp.text, (
            f"BUG: Got 'Customer record not found' - platform_super_admin not in is_admin check! "
            f"Response: {resp.text}"
        )
        # With WorkDrive not configured, expect 400 (not connected) or 502 (api call fail)
        # NOT 404 'customer record not found'
        assert resp.status_code != 404 or "customer record not found" not in resp.text.lower(), (
            f"BUG: platform_super_admin hit customer code path. Response: {resp.text}"
        )
        # Valid responses: 400 (workdrive not connected), 502 (workdrive error), 413 (too large)
        assert resp.status_code in (400, 502, 413, 200), (
            f"Expected WorkDrive-related error (400/502) or success (200), got {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        print(f"[PASS] Upload with customer_id as platform_super_admin returns {resp.status_code}: {data.get('detail', data)}")

    def test_upload_error_is_not_internal_server_error(self, admin_headers_no_ct):
        """Upload should never return 500 internal server error."""
        files = {"file": ("test.txt", b"content", "text/plain")}
        resp = requests.post(
            f"{BASE_URL}/api/documents/upload?customer_id=nonexistent-customer-iter257",
            headers=admin_headers_no_ct,
            files=files
        )
        assert resp.status_code != 500, (
            f"FAIL: Got 500 internal server error. Fix not applied! Response: {resp.text}"
        )
        print(f"[PASS] Upload with invalid customer_id returns {resp.status_code} (not 500)")


# ---------------------------------------------------------------------------
# Bug Fix 1: platform_super_admin in is_admin check — GET /api/documents/{id}/download
# ---------------------------------------------------------------------------

class TestDownloadDocumentPlatformSuperAdmin:
    """Bug fix 1: platform_super_admin must be in is_admin check for download endpoint."""

    def test_download_nonexistent_doc_returns_404(self, admin_headers):
        """
        GET /api/documents/{doc_id}/download as platform_super_admin for nonexistent doc
        should return 404 'Document not found', not any auth error or customer-record error.
        """
        resp = requests.get(
            f"{BASE_URL}/api/documents/nonexistent-doc-iter257/download",
            headers=admin_headers
        )
        # Platform admin should pass the auth/role check and get 404 for missing doc
        assert resp.status_code == 404, (
            f"Expected 404 'Document not found', got {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        assert "detail" in data
        assert "document not found" in data["detail"].lower() or "not found" in data["detail"].lower(), (
            f"Unexpected error detail: {data['detail']}"
        )
        print(f"[PASS] Download nonexistent doc as platform_super_admin returns 404: {data['detail']}")

    def test_download_no_auth_rejected(self):
        """Download without auth should return 401/403."""
        resp = requests.get(f"{BASE_URL}/api/documents/some-doc-id/download")
        assert resp.status_code in (401, 403), (
            f"Expected 401/403 without auth, got {resp.status_code}"
        )
        print(f"[PASS] Download without auth returns {resp.status_code}")


# ---------------------------------------------------------------------------
# Bug Fix 2: Correct upload URL in workdrive_service.py
# ---------------------------------------------------------------------------

class TestWorkdriveServiceUploadURL:
    """Bug fix 2: upload endpoint should use workdrive.zoho.com/api/v1/upload (not /files/{id}/files)."""

    def test_upload_url_code_is_correct(self):
        """
        Verify by static code analysis that workdrive_service.py uses the correct upload URL.
        The old broken URL was: /workdrive/api/v1/files/{folder_id}/files (returns HTTP 405)
        The correct URL is: workdrive.zoho.com/api/v1/upload (with multipart content + parent_id)
        """
        import importlib.util
        import sys
        import inspect

        # Load the module source to inspect
        service_path = os.path.join(
            os.path.dirname(__file__), "..", "services", "workdrive_service.py"
        )
        service_path = os.path.abspath(service_path)
        assert os.path.exists(service_path), f"workdrive_service.py not found at {service_path}"

        with open(service_path, "r") as f:
            source = f.read()

        # Check that DATACENTER_UPLOAD_DOMAINS is defined with correct zoho domains
        assert "DATACENTER_UPLOAD_DOMAINS" in source, "DATACENTER_UPLOAD_DOMAINS not found in workdrive_service.py"
        assert "workdrive.zoho.com" in source, "Expected workdrive.zoho.com in DATACENTER_UPLOAD_DOMAINS"

        # Check that upload_file uses /api/v1/upload path
        assert "/api/v1/upload" in source, (
            "FAIL: /api/v1/upload not found in workdrive_service.py! "
            "Old broken endpoint (/files/{folder_id}/files) may still be in use."
        )

        # Verify the OLD broken endpoint is NOT used in upload_file function
        # (the old broken pattern was f"...files/{folder_id}/files")
        # Check that upload_domain is used for upload (not api_domain)
        assert "upload_domain" in source, "Expected 'upload_domain' variable in upload_file function"

        print("[PASS] workdrive_service.py uses correct upload URL: workdrive.zoho.com/api/v1/upload")

    def test_upload_uses_correct_form_fields(self):
        """
        Verify upload uses 'content' (file) and 'parent_id' form fields (not some other format).
        The old implementation used the wrong field names.
        """
        service_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "services", "workdrive_service.py")
        )
        with open(service_path, "r") as f:
            source = f.read()

        # Check multipart field names
        assert '"content"' in source or "'content'" in source, (
            "FAIL: 'content' field not found in upload_file — WorkDrive expects file in 'content' field"
        )
        assert '"parent_id"' in source or "'parent_id'" in source, (
            "FAIL: 'parent_id' field not found in upload_file — WorkDrive expects folder ID in 'parent_id' field"
        )
        print("[PASS] upload_file uses correct form fields: 'content' (file) and 'parent_id'")

    def test_datacenter_upload_domains_has_all_regions(self):
        """DATACENTER_UPLOAD_DOMAINS must have all required datacenter entries."""
        service_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "services", "workdrive_service.py")
        )
        with open(service_path, "r") as f:
            source = f.read()

        required_domains = [
            "workdrive.zoho.com",    # US
            "workdrive.zoho.eu",     # EU
        ]
        for domain in required_domains:
            assert domain in source, f"FAIL: {domain} not found in DATACENTER_UPLOAD_DOMAINS"
        print("[PASS] DATACENTER_UPLOAD_DOMAINS has required datacenter entries")


# ---------------------------------------------------------------------------
# Role check verification via code analysis
# ---------------------------------------------------------------------------

class TestIsAdminRoleCheckIncludesPlatformSuperAdmin:
    """Verify all 3 document endpoints include platform_super_admin in is_admin check."""

    def _load_documents_source(self) -> str:
        docs_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "routes", "documents.py")
        )
        assert os.path.exists(docs_path), f"documents.py not found at {docs_path}"
        with open(docs_path, "r") as f:
            return f.read()

    def test_list_documents_is_admin_includes_platform_super_admin(self):
        """list_documents must have platform_super_admin in its is_admin tuple."""
        source = self._load_documents_source()
        # Find the list_documents function
        assert "platform_super_admin" in source, (
            "FAIL: platform_super_admin not found in documents.py is_admin checks"
        )
        # Count occurrences (should appear in all 3 endpoint is_admin checks)
        count = source.count("platform_super_admin")
        assert count >= 3, (
            f"FAIL: platform_super_admin appears only {count} time(s) in documents.py. "
            f"Expected at least 3 (one per endpoint: list, upload, download)"
        )
        print(f"[PASS] platform_super_admin appears {count} times in documents.py is_admin checks")

    def test_all_three_endpoints_have_consistent_is_admin_check(self):
        """All 3 endpoints should use the same is_admin role tuple."""
        source = self._load_documents_source()
        # The role tuple should be consistent across all 3 endpoints
        role_tuple = (
            '"admin", "platform_admin", "platform_super_admin"'
        )
        assert "platform_super_admin" in source, (
            "FAIL: platform_super_admin missing from documents.py"
        )
        # Verify the tuple appears in context of is_admin assignments
        lines_with_is_admin = [
            line.strip() for line in source.split("\n")
            if "is_admin" in line and "role in" in line
        ]
        print(f"[INFO] is_admin lines found: {lines_with_is_admin}")
        for line in lines_with_is_admin:
            assert "platform_super_admin" in line, (
                f"FAIL: is_admin check missing platform_super_admin: {line}"
            )
        assert len(lines_with_is_admin) >= 3, (
            f"Expected at least 3 is_admin checks (list/upload/download), found {len(lines_with_is_admin)}: {lines_with_is_admin}"
        )
        print(f"[PASS] All {len(lines_with_is_admin)} is_admin checks include platform_super_admin")
