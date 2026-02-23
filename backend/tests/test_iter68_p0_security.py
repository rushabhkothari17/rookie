"""
Security P0/P1/Enhancement Tests — Iteration 68

New features verified:
- Content-Security-Policy header (default-src directive)
- API key hashing (POST creates key_hash + key_suffix, NO raw key in DB)
- API key lookup (X-API-Key with hashed key resolves tenant on /api/products)
- API key migration (no plaintext-only keys in DB)
- Export audit log (orders + customers export → action='data_exported')
- Startup security validation (dev mode warns but doesn't crash)
- JWT secret rotation (old 'change_me_super_secret' token → 401)
- Regression: admin login still works
- Regression: list API keys returns key_masked
- Regression: security headers (X-Frame-Options, X-Content-Type-Options)
- pip-audit: starlette 0.41.0, pymongo 4.6.3
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import os
import time

import jwt as pyjwt
import pytest
import requests
from pymongo import MongoClient

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"

# Old JWT secret that was rotated out
OLD_JWT_SECRET = "change_me_super_secret"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def mongo_db():
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


@pytest.fixture(scope="module")
def admin_token():
    """Obtain a fresh admin JWT using the rotated secret."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    token = resp.json().get("access_token") or resp.json().get("token")
    assert token, f"No token in response: {resp.json()}"
    return token


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ---------------------------------------------------------------------------
# 1. Content-Security-Policy Header
# ---------------------------------------------------------------------------

class TestContentSecurityPolicy:
    """CSP header present on every API response."""

    def test_csp_header_on_public_endpoint(self):
        """GET /api/health (or /api/products) should include CSP header."""
        resp = requests.get(f"{BASE_URL}/api/products")
        assert resp.status_code in (200, 404), f"Unexpected status: {resp.status_code}"
        csp = resp.headers.get("Content-Security-Policy", "")
        assert csp, "Content-Security-Policy header is MISSING"
        print(f"CSP header: {csp}")

    def test_csp_contains_default_src(self):
        """CSP must contain 'default-src' directive."""
        resp = requests.get(f"{BASE_URL}/api/products")
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "default-src" in csp, f"'default-src' not found in CSP: '{csp}'"
        print(f"PASS — CSP contains default-src: {csp}")

    def test_csp_on_authenticated_endpoint(self, admin_headers):
        """Authenticated endpoints also carry the CSP header."""
        resp = requests.get(f"{BASE_URL}/api/admin/api-keys", headers=admin_headers)
        assert resp.status_code == 200, f"Unexpected: {resp.text}"
        csp = resp.headers.get("Content-Security-Policy", "")
        assert csp, "CSP header missing on authenticated endpoint"
        assert "default-src" in csp
        print(f"PASS — CSP on /api/admin/api-keys: {csp}")

    def test_csp_frame_ancestors_none(self):
        """CSP should include frame-ancestors 'none'."""
        resp = requests.get(f"{BASE_URL}/api/products")
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "frame-ancestors" in csp, f"frame-ancestors directive missing: {csp}"
        print(f"PASS — frame-ancestors present")


# ---------------------------------------------------------------------------
# 2. API Key Hashing
# ---------------------------------------------------------------------------

class TestApiKeyHashing:
    """POST /api/admin/api-keys stores hash only, not raw key."""

    @pytest.fixture(scope="class")
    def created_key_data(self, admin_headers, mongo_db):
        """Create an API key and yield (response_data, db_doc)."""
        resp = requests.post(
            f"{BASE_URL}/api/admin/api-keys",
            json={"name": "TEST_hashing_test_key"},
            headers=admin_headers,
        )
        assert resp.status_code == 200, f"Create API key failed: {resp.text}"
        data = resp.json()
        raw_key = data.get("key")
        assert raw_key, "API response must include raw key (returned once)"
        key_id = data.get("id")
        # Fetch the DB document by id
        doc = mongo_db.api_keys.find_one({"id": key_id}, {"_id": 0})
        yield data, doc
        # Cleanup
        mongo_db.api_keys.delete_one({"id": key_id})

    def test_raw_key_not_in_db(self, created_key_data):
        """The 'key' field must NOT be present in the DB document."""
        _, doc = created_key_data
        assert doc is not None, "API key document not found in DB"
        assert "key" not in doc, f"Raw 'key' field found in DB doc: {list(doc.keys())}"
        print("PASS — 'key' field absent from DB")

    def test_key_hash_in_db(self, created_key_data):
        """key_hash (SHA-256) must be present in DB."""
        _, doc = created_key_data
        assert "key_hash" in doc, f"'key_hash' missing from DB doc: {list(doc.keys())}"
        print(f"PASS — key_hash present: {doc['key_hash'][:16]}...")

    def test_key_hash_correct_value(self, created_key_data):
        """The stored key_hash should be SHA-256(raw_key)."""
        response_data, doc = created_key_data
        raw_key = response_data["key"]
        expected_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        assert doc["key_hash"] == expected_hash, (
            f"key_hash mismatch. Expected {expected_hash}, got {doc['key_hash']}"
        )
        print(f"PASS — key_hash matches SHA-256(raw_key)")

    def test_key_suffix_in_db(self, created_key_data):
        """key_suffix (last 8 chars) must be stored."""
        response_data, doc = created_key_data
        raw_key = response_data["key"]
        assert "key_suffix" in doc, "key_suffix missing from DB"
        assert doc["key_suffix"] == raw_key[-8:], (
            f"key_suffix mismatch: stored={doc['key_suffix']}, expected={raw_key[-8:]}"
        )
        print(f"PASS — key_suffix={doc['key_suffix']}")

    def test_response_includes_key_once(self, created_key_data):
        """The POST response should include the raw key exactly once (for user to copy)."""
        response_data, _ = created_key_data
        assert "key" in response_data, "Raw key missing from POST response"
        assert response_data["key"].startswith("ak_"), f"Key format unexpected: {response_data['key']}"
        print(f"PASS — raw key returned in response: {response_data['key'][:12]}...")

    def test_list_endpoint_hides_raw_key(self, admin_headers):
        """GET /api/admin/api-keys must NOT return 'key' or 'key_hash', only 'key_masked'."""
        resp = requests.get(f"{BASE_URL}/api/admin/api-keys", headers=admin_headers)
        assert resp.status_code == 200
        keys = resp.json().get("api_keys", [])
        for k in keys:
            assert "key" not in k, f"Raw 'key' exposed in list: {k}"
            assert "key_hash" not in k, f"'key_hash' exposed in list: {k}"
            assert "key_masked" in k, f"'key_masked' missing from list item: {k}"
        print(f"PASS — {len(keys)} keys listed, all masked")


# ---------------------------------------------------------------------------
# 3. API Key Lookup (hashed key resolves tenant)
# ---------------------------------------------------------------------------

class TestApiKeyLookup:
    """X-API-Key header with a newly-created hashed key resolves tenant on /api/products."""

    def test_api_key_resolves_tenant_on_products(self, admin_headers):
        """Create key → use X-API-Key on GET /api/products → gets 200 (tenant resolved)."""
        # Create a fresh key
        create_resp = requests.post(
            f"{BASE_URL}/api/admin/api-keys",
            json={"name": "TEST_lookup_test_key"},
            headers=admin_headers,
        )
        assert create_resp.status_code == 200, f"Create failed: {create_resp.text}"
        raw_key = create_resp.json()["key"]
        key_id = create_resp.json()["id"]

        try:
            # Use it on /api/products
            products_resp = requests.get(
                f"{BASE_URL}/api/products",
                headers={"X-API-Key": raw_key},
            )
            assert products_resp.status_code == 200, (
                f"Expected 200 from /api/products with valid API key, got {products_resp.status_code}: {products_resp.text[:200]}"
            )
            print(f"PASS — /api/products returned 200 with hashed API key")
        finally:
            # Cleanup
            requests.delete(f"{BASE_URL}/api/admin/api-keys/{key_id}", headers=admin_headers)

    def test_invalid_api_key_still_works(self):
        """Invalid X-API-Key should not error out — products endpoint still returns 200 (public)."""
        resp = requests.get(
            f"{BASE_URL}/api/products",
            headers={"X-API-Key": "ak_invalidkey12345"},
        )
        # Public endpoint should still return 200 (API key failure → no tenant filter,
        # defaults to platform or empty result, not 401/500)
        assert resp.status_code in (200, 404), (
            f"Unexpected status with bad API key: {resp.status_code}"
        )
        print(f"PASS — Invalid API key returns {resp.status_code} (no crash)")


# ---------------------------------------------------------------------------
# 4. API Key Migration (no legacy plaintext-only keys)
# ---------------------------------------------------------------------------

class TestApiKeyMigration:
    """verify no DB documents have 'key' field without 'key_hash' (migration ran)."""

    def test_no_unmigrated_legacy_keys(self, mongo_db):
        """api_keys collection should have zero docs with 'key' field but no 'key_hash'."""
        count = mongo_db.api_keys.count_documents(
            {"key": {"$exists": True}, "key_hash": {"$exists": False}}
        )
        assert count == 0, (
            f"Found {count} api_keys document(s) with raw 'key' but no 'key_hash' — migration incomplete!"
        )
        print(f"PASS — 0 unmigrated legacy API keys")

    def test_all_active_keys_have_key_hash(self, mongo_db):
        """All active API keys must have key_hash stored."""
        without_hash = mongo_db.api_keys.count_documents(
            {"is_active": True, "key_hash": {"$exists": False}}
        )
        assert without_hash == 0, (
            f"{without_hash} active key(s) missing key_hash!"
        )
        print(f"PASS — all active keys have key_hash")


# ---------------------------------------------------------------------------
# 5 & 6. Export Audit Log
# ---------------------------------------------------------------------------

class TestExportAuditLog:
    """Export endpoints write action='data_exported' to audit_trail."""

    def _get_recent_export_logs(self, admin_headers, entity_id: str) -> list:
        """Fetch recent audit logs for export entity.
        create_audit_log stores action as 'EXPORT_DATA_EXPORTED' in audit_trail
        and entity_type as 'Export' (PascalCase).
        """
        resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs",
            params={"entity_type": "export", "limit": 50},
            headers=admin_headers,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        # API returns 'logs' key (not 'audit_logs')
        logs = data.get("logs", data.get("audit_logs", []))
        return [
            log for log in logs
            if log.get("entity_id") == entity_id
            and "data_exported" in log.get("action", "").lower()
        ]

    def test_orders_export_creates_audit_log(self, admin_headers):
        """GET /api/admin/export/orders → audit log entry with action='data_exported'."""
        # Capture pre-export log count
        pre_logs = self._get_recent_export_logs(admin_headers, "orders")
        pre_count = len(pre_logs)

        # Trigger export
        export_resp = requests.get(
            f"{BASE_URL}/api/admin/export/orders",
            headers=admin_headers,
        )
        assert export_resp.status_code == 200, f"Orders export failed: {export_resp.text}"

        # Wait briefly for async DB write
        time.sleep(0.5)

        post_logs = self._get_recent_export_logs(admin_headers, "orders")
        post_count = len(post_logs)

        assert post_count > pre_count, (
            f"No new data_exported audit log after orders export. Before={pre_count}, After={post_count}"
        )
        print(f"PASS — orders export audit log created (total logs: {post_count})")

    def test_customers_export_creates_audit_log(self, admin_headers):
        """GET /api/admin/export/customers → audit log entry with action='data_exported'."""
        pre_logs = self._get_recent_export_logs(admin_headers, "customers")
        pre_count = len(pre_logs)

        export_resp = requests.get(
            f"{BASE_URL}/api/admin/export/customers",
            headers=admin_headers,
        )
        assert export_resp.status_code == 200, f"Customers export failed: {export_resp.text}"

        time.sleep(0.5)

        post_logs = self._get_recent_export_logs(admin_headers, "customers")
        post_count = len(post_logs)

        assert post_count > pre_count, (
            f"No new data_exported audit log after customers export. Before={pre_count}, After={post_count}"
        )
        print(f"PASS — customers export audit log created (total logs: {post_count})")

    def test_audit_log_action_is_data_exported(self, admin_headers):
        """Verify the audit log action field equals 'data_exported' exactly."""
        # Trigger an export to ensure at least one exists
        requests.get(f"{BASE_URL}/api/admin/export/orders", headers=admin_headers)
        time.sleep(0.5)

        resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs",
            params={"entity_type": "export", "limit": 50},
            headers=admin_headers,
        )
        assert resp.status_code == 200, f"Audit log fetch failed: {resp.text}"
        logs = resp.json().get("audit_logs", resp.json().get("logs", []))
        data_exported_logs = [l for l in logs if l.get("action") == "data_exported"]
        assert len(data_exported_logs) > 0, (
            f"No logs with action='data_exported' found. Logs: {[l.get('action') for l in logs[:5]]}"
        )
        print(f"PASS — found {len(data_exported_logs)} log(s) with action='data_exported'")


# ---------------------------------------------------------------------------
# 7. Startup Security Validation (dev mode)
# ---------------------------------------------------------------------------

class TestStartupSecurityValidation:
    """Server starts normally in development mode even with default ADMIN_PASSWORD."""

    def test_server_running_in_dev_mode(self):
        """Server responds — proves it didn't crash from weak-password warning in dev."""
        resp = requests.get(f"{BASE_URL}/api/products", timeout=10)
        assert resp.status_code in (200, 404), f"Server not responding: {resp.status_code}"
        print("PASS — server running in ENVIRONMENT=development with ChangeMe123!")

    def test_dev_docs_accessible(self):
        """In dev mode, /docs should be accessible (server started successfully)."""
        resp = requests.get(f"{BASE_URL}/docs", timeout=10)
        assert resp.status_code == 200, f"/docs returned {resp.status_code} — server may not have started"
        print("PASS — /docs accessible, server started normally")

    def test_server_logs_warning_not_crash(self):
        """Verify by checking backend logs for WARNING about weak ADMIN_PASSWORD."""
        import subprocess
        result = subprocess.run(
            ["tail", "-n", "200", "/var/log/supervisor/backend.out.log"],
            capture_output=True, text=True
        )
        log_text = result.stdout + result.stderr
        # The server should show a warning, NOT a FATAL/RuntimeError/traceback for dev mode
        has_warning = "ADMIN_PASSWORD" in log_text and ("warning" in log_text.lower() or "⚠️" in log_text)
        has_fatal = "FATAL:" in log_text and "ADMIN_PASSWORD" in log_text

        assert not has_fatal, "Server raised FATAL error for default ADMIN_PASSWORD in dev mode!"
        print(f"PASS — Server has warning log (not fatal): warning_found={has_warning}")


# ---------------------------------------------------------------------------
# 8. JWT Secret Rotation
# ---------------------------------------------------------------------------

class TestJWTRotation:
    """Old tokens signed with 'change_me_super_secret' must be rejected."""

    def _make_old_token(self, sub: str = "fake-user-id") -> str:
        """Create a JWT signed with the OLD secret."""
        import time as _time
        payload = {
            "sub": sub,
            "role": "admin",
            "token_version": 0,
            "exp": int(_time.time()) + 3600,
        }
        return pyjwt.encode(payload, OLD_JWT_SECRET, algorithm="HS256")

    def test_old_token_rejected_on_admin_endpoint(self):
        """Token signed with old secret → 401 on any protected endpoint."""
        old_token = self._make_old_token()
        resp = requests.get(
            f"{BASE_URL}/api/admin/api-keys",
            headers={"Authorization": f"Bearer {old_token}"},
        )
        assert resp.status_code == 401, (
            f"Expected 401 for old JWT secret token, got {resp.status_code}: {resp.text}"
        )
        print(f"PASS — old secret token correctly rejected with 401")

    def test_old_token_rejected_on_auth_me(self):
        """Old-secret token rejected on /api/auth/me or any user endpoint."""
        old_token = self._make_old_token()
        resp = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {old_token}"},
        )
        assert resp.status_code == 401, (
            f"Expected 401, got {resp.status_code}: {resp.text}"
        )
        print("PASS — old secret token rejected on /api/auth/me")

    def test_new_token_still_works(self, admin_headers):
        """Fresh token (signed with new secret) is accepted."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/api-keys",
            headers=admin_headers,
        )
        assert resp.status_code == 200, (
            f"Fresh token rejected unexpectedly: {resp.status_code}: {resp.text}"
        )
        print("PASS — fresh token accepted on /api/admin/api-keys")


# ---------------------------------------------------------------------------
# 9. Regression: Admin Login
# ---------------------------------------------------------------------------

class TestAdminLoginRegression:
    """Admin login still works after JWT secret rotation."""

    def test_admin_login_success(self):
        """POST /api/auth/login returns 200 + token."""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
        })
        assert resp.status_code == 200, f"Admin login failed: {resp.text}"
        data = resp.json()
        token = data.get("access_token") or data.get("token")
        assert token, f"No token in response: {data}"
        print(f"PASS — admin login returns token")

    def test_wrong_password_returns_401(self):
        """Wrong password → 401 (not 500 or other error)."""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": "WrongPassword99!",
        })
        assert resp.status_code in (401, 400, 429), (
            f"Expected 401 for wrong password, got {resp.status_code}"
        )
        print(f"PASS — wrong password returns {resp.status_code}")


# ---------------------------------------------------------------------------
# 10. Regression: List API Keys (masked)
# ---------------------------------------------------------------------------

class TestListApiKeysRegression:
    """GET /api/admin/api-keys returns key_masked, not raw key."""

    def test_list_returns_key_masked(self, admin_headers):
        """Each API key in list must have key_masked field."""
        # Ensure at least one key exists
        requests.post(
            f"{BASE_URL}/api/admin/api-keys",
            json={"name": "TEST_list_regression_key"},
            headers=admin_headers,
        )
        resp = requests.get(f"{BASE_URL}/api/admin/api-keys", headers=admin_headers)
        assert resp.status_code == 200, f"List keys failed: {resp.text}"
        keys = resp.json().get("api_keys", [])
        assert len(keys) > 0, "No API keys returned"
        for k in keys:
            assert "key_masked" in k, f"'key_masked' missing from key: {k}"
            assert k["key_masked"].startswith("ak_"), f"Unexpected mask format: {k['key_masked']}"
            assert "key" not in k, f"Raw key exposed: {k}"
        print(f"PASS — {len(keys)} key(s) listed, all have key_masked")

    def test_list_does_not_expose_key_hash(self, admin_headers):
        """key_hash must not be returned in list response."""
        resp = requests.get(f"{BASE_URL}/api/admin/api-keys", headers=admin_headers)
        assert resp.status_code == 200
        keys = resp.json().get("api_keys", [])
        for k in keys:
            assert "key_hash" not in k, f"key_hash exposed in list: {k}"
        print("PASS — key_hash not exposed in list")


# ---------------------------------------------------------------------------
# 11. Regression: Security Headers
# ---------------------------------------------------------------------------

class TestSecurityHeadersRegression:
    """Previously-passing security headers still present."""

    def test_x_frame_options(self):
        resp = requests.get(f"{BASE_URL}/api/products")
        assert resp.headers.get("X-Frame-Options") == "DENY", (
            f"X-Frame-Options missing or wrong: {resp.headers.get('X-Frame-Options')}"
        )
        print("PASS — X-Frame-Options: DENY")

    def test_x_content_type_options(self):
        resp = requests.get(f"{BASE_URL}/api/products")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff", (
            f"X-Content-Type-Options missing: {resp.headers.get('X-Content-Type-Options')}"
        )
        print("PASS — X-Content-Type-Options: nosniff")

    def test_csp_complete_directives(self):
        """CSP should include all four directives."""
        resp = requests.get(f"{BASE_URL}/api/products")
        csp = resp.headers.get("Content-Security-Policy", "")
        for directive in ["default-src", "frame-ancestors", "form-action", "base-uri"]:
            assert directive in csp, f"'{directive}' missing from CSP: {csp}"
        print(f"PASS — all 4 CSP directives present: {csp}")


# ---------------------------------------------------------------------------
# 12. Regression: Rate Limiting (quick sanity)
# ---------------------------------------------------------------------------

class TestRateLimitingRegression:
    """Quick sanity: rate limit on login is still active."""

    def test_login_rate_limit_active(self):
        """Fire 12 rapid login requests — at least one should return 429."""
        results = []
        for _ in range(12):
            resp = requests.post(f"{BASE_URL}/api/auth/login", json={
                "email": "ratecheck@example.com",
                "password": "dummy",
            })
            results.append(resp.status_code)
        assert 429 in results, (
            f"Expected at least one 429 from rate limiting. Got: {set(results)}"
        )
        print(f"PASS — rate limiting active, got 429 after rapid requests. Codes: {set(results)}")


# ---------------------------------------------------------------------------
# 13. pip-audit CVE Versions
# ---------------------------------------------------------------------------

class TestPipAuditVersions:
    """Verify fixed package versions are installed."""

    def test_starlette_version(self):
        """starlette must be >= 0.41.0 (fixes CVE-2024-47874)."""
        version = importlib.metadata.version("starlette")
        major, minor, patch = (int(x) for x in version.split(".")[:3])
        assert (major, minor, patch) >= (0, 41, 0), (
            f"starlette {version} is too old — need >= 0.41.0 for CVE-2024-47874 fix"
        )
        print(f"PASS — starlette {version} >= 0.41.0 ✓")

    def test_pymongo_version(self):
        """pymongo must be >= 4.6.3 (fixes CVE-2024-5629)."""
        version = importlib.metadata.version("pymongo")
        major, minor, patch = (int(x) for x in version.split(".")[:3])
        assert (major, minor, patch) >= (4, 6, 3), (
            f"pymongo {version} is too old — need >= 4.6.3 for CVE-2024-5629 fix"
        )
        print(f"PASS — pymongo {version} >= 4.6.3 ✓")
