"""
SSRF Protection tests for webhook system (iteration 291).
Tests: SSRF blocking of private IPs, valid URL allowed, CRUD, auth enforcement.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

TENANT_ADMIN_EMAIL = "mayank@automateaccounts.com"
TENANT_ADMIN_PASSWORD = "ChangeMe123!"
SUPER_ADMIN_EMAIL = "admin@automateaccounts.local"
SUPER_ADMIN_PASSWORD = "ChangeMe123!"


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def tenant_token(session):
    """Obtain JWT for tenant admin mayank@automateaccounts.com."""
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": TENANT_ADMIN_EMAIL,
        "password": TENANT_ADMIN_PASSWORD,
    })
    if resp.status_code != 200:
        pytest.skip(f"Tenant admin login failed ({resp.status_code}): {resp.text[:200]}")
    token = resp.json().get("token") or resp.json().get("access_token")
    if not token:
        pytest.skip("No token in login response")
    return token


@pytest.fixture(scope="module")
def tenant_auth(session, tenant_token):
    """Session with tenant admin auth header."""
    s = requests.Session()
    s.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {tenant_token}",
    })
    return s


@pytest.fixture(scope="module")
def super_auth(session):
    """Session with super admin auth header."""
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL,
        "password": SUPER_ADMIN_PASSWORD,
    })
    if resp.status_code != 200:
        pytest.skip(f"Super admin login failed ({resp.status_code}): {resp.text[:200]}")
    token = resp.json().get("token") or resp.json().get("access_token")
    if not token:
        pytest.skip("No token in super admin login response")
    s = requests.Session()
    s.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    })
    return s


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def create_webhook(auth_session, url: str, name: str = "TEST_SSRF_Webhook"):
    """POST /api/admin/webhooks with given url. Returns response."""
    return auth_session.post(f"{BASE_URL}/api/admin/webhooks", json={
        "name": name,
        "url": url,
        "subscriptions": [{"event": "order.created", "fields": ["id", "status"]}],
    })


# ---------------------------------------------------------------------------
# 1. SSRF Protection — must block private/reserved IPs
# ---------------------------------------------------------------------------

class TestSSRFBlocking:
    """SSRF protection: all private/reserved IPs and non-http schemes must return 400."""

    def test_aws_metadata_endpoint_blocked(self, tenant_auth):
        """http://169.254.169.254/latest/meta-data/ — link-local (AWS metadata) must be 400."""
        resp = create_webhook(tenant_auth, "http://169.254.169.254/latest/meta-data/",
                              name="TEST_SSRF_AWS_metadata")
        print(f"AWS metadata test: status={resp.status_code}, body={resp.text[:300]}")
        assert resp.status_code == 400, (
            f"Expected 400 for AWS metadata URL, got {resp.status_code}: {resp.text[:200]}"
        )
        # Verify error message indicates blocked/SSRF
        body = resp.json()
        detail = body.get("detail", "").lower()
        assert any(kw in detail for kw in ("blocked", "reserved", "private", "ssrf", "internal", "permitted")), \
            f"Expected SSRF error message, got: {detail}"

    def test_loopback_127_blocked(self, tenant_auth):
        """http://127.0.0.1:8001/api/admin/users — loopback must be 400."""
        resp = create_webhook(tenant_auth, "http://127.0.0.1:8001/api/admin/users",
                              name="TEST_SSRF_loopback")
        print(f"Loopback test: status={resp.status_code}, body={resp.text[:300]}")
        assert resp.status_code == 400, (
            f"Expected 400 for loopback URL, got {resp.status_code}: {resp.text[:200]}"
        )
        body = resp.json()
        detail = body.get("detail", "").lower()
        assert any(kw in detail for kw in ("blocked", "reserved", "private", "ssrf", "internal", "permitted")), \
            f"Expected SSRF error message, got: {detail}"

    def test_private_class_a_blocked(self, tenant_auth):
        """http://10.0.0.1/secret — RFC 1918 class A must be 400."""
        resp = create_webhook(tenant_auth, "http://10.0.0.1/secret",
                              name="TEST_SSRF_classA")
        print(f"Class A test: status={resp.status_code}, body={resp.text[:300]}")
        assert resp.status_code == 400, (
            f"Expected 400 for 10.x.x.x URL, got {resp.status_code}: {resp.text[:200]}"
        )

    def test_private_class_c_blocked(self, tenant_auth):
        """http://192.168.1.1/admin — RFC 1918 class C must be 400."""
        resp = create_webhook(tenant_auth, "http://192.168.1.1/admin",
                              name="TEST_SSRF_classC")
        print(f"Class C test: status={resp.status_code}, body={resp.text[:300]}")
        assert resp.status_code == 400, (
            f"Expected 400 for 192.168.x.x URL, got {resp.status_code}: {resp.text[:200]}"
        )

    def test_private_class_b_blocked(self, tenant_auth):
        """http://172.16.0.1/internal — RFC 1918 class B (172.16–31.x.x) must be 400."""
        resp = create_webhook(tenant_auth, "http://172.16.0.1/internal",
                              name="TEST_SSRF_classB")
        print(f"Class B test: status={resp.status_code}, body={resp.text[:300]}")
        assert resp.status_code == 400, (
            f"Expected 400 for 172.16.x.x URL, got {resp.status_code}: {resp.text[:200]}"
        )

    def test_file_scheme_blocked(self, tenant_auth):
        """file:///etc/passwd — non-http/https scheme must be 400."""
        resp = create_webhook(tenant_auth, "file:///etc/passwd",
                              name="TEST_SSRF_file_scheme")
        print(f"File scheme test: status={resp.status_code}, body={resp.text[:300]}")
        assert resp.status_code == 400, (
            f"Expected 400 for file:// URL, got {resp.status_code}: {resp.text[:200]}"
        )
        body = resp.json()
        detail = body.get("detail", "").lower()
        assert any(kw in detail for kw in ("scheme", "http", "https", "blocked", "ssrf")), \
            f"Expected scheme error message, got: {detail}"

    def test_ssrf_blocked_on_update(self, tenant_auth):
        """PUT /api/admin/webhooks/{id} with private IP in URL must also return 400."""
        # First create a valid webhook
        valid_resp = create_webhook(tenant_auth, "https://httpbin.org/post",
                                     name="TEST_SSRF_UpdateTest")
        if valid_resp.status_code not in (200, 201):
            pytest.skip(f"Could not create test webhook: {valid_resp.status_code} {valid_resp.text[:100]}")

        webhook_id = valid_resp.json().get("id")
        assert webhook_id, "No id in create response"

        # Now try to update with a private URL
        update_resp = tenant_auth.put(
            f"{BASE_URL}/api/admin/webhooks/{webhook_id}",
            json={"url": "http://10.0.0.1/evil"},
        )
        print(f"SSRF update test: status={update_resp.status_code}, body={update_resp.text[:300]}")
        assert update_resp.status_code == 400, (
            f"Expected 400 when updating to private IP, got {update_resp.status_code}: {update_resp.text[:200]}"
        )

        # Cleanup
        tenant_auth.delete(f"{BASE_URL}/api/admin/webhooks/{webhook_id}")


# ---------------------------------------------------------------------------
# 2. Valid public URL allowed
# ---------------------------------------------------------------------------

class TestValidWebhookCreation:
    """A public, routable URL should succeed (201)."""

    created_webhook_id = None

    def test_valid_public_url_allowed(self, tenant_auth):
        """https://httpbin.org/post — public URL must return 200 or 201."""
        resp = create_webhook(tenant_auth, "https://httpbin.org/post",
                              name="TEST_ValidWebhook_httpbin")
        print(f"Valid URL test: status={resp.status_code}, body={resp.text[:400]}")
        assert resp.status_code in (200, 201), (
            f"Expected 200/201 for valid public URL, got {resp.status_code}: {resp.text[:300]}"
        )
        data = resp.json()
        assert "id" in data, f"No 'id' field in response: {data}"
        assert data.get("url") == "https://httpbin.org/post", "URL not stored correctly"
        TestValidWebhookCreation.created_webhook_id = data["id"]

    def test_created_webhook_appears_in_list(self, tenant_auth):
        """GET /api/admin/webhooks — newly created webhook should appear in list."""
        if not TestValidWebhookCreation.created_webhook_id:
            pytest.skip("Previous test did not create webhook")
        resp = tenant_auth.get(f"{BASE_URL}/api/admin/webhooks")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        webhooks = data.get("webhooks", [])
        ids = [w["id"] for w in webhooks]
        assert TestValidWebhookCreation.created_webhook_id in ids, \
            f"Created webhook {TestValidWebhookCreation.created_webhook_id} not found in list: {ids}"


# ---------------------------------------------------------------------------
# 3. Webhook CRUD
# ---------------------------------------------------------------------------

class TestWebhookCRUD:
    """Basic CRUD operations for webhooks."""

    created_id = None

    def test_get_webhooks_returns_list(self, tenant_auth):
        """GET /api/admin/webhooks should return 200 with a webhooks array."""
        resp = tenant_auth.get(f"{BASE_URL}/api/admin/webhooks")
        print(f"List webhooks: status={resp.status_code}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "webhooks" in data, f"Expected 'webhooks' key in response, got: {list(data.keys())}"
        assert isinstance(data["webhooks"], list), "webhooks should be a list"

    def test_create_webhook_and_get(self, tenant_auth):
        """POST + GET single webhook — data should persist correctly."""
        name = "TEST_CRUD_Webhook"
        create_resp = create_webhook(tenant_auth, "https://httpbin.org/post", name=name)
        assert create_resp.status_code in (200, 201), \
            f"Create failed {create_resp.status_code}: {create_resp.text[:200]}"
        data = create_resp.json()
        assert "id" in data
        webhook_id = data["id"]
        TestWebhookCRUD.created_id = webhook_id

        # GET single
        get_resp = tenant_auth.get(f"{BASE_URL}/api/admin/webhooks/{webhook_id}")
        assert get_resp.status_code == 200, \
            f"GET single failed {get_resp.status_code}: {get_resp.text[:200]}"
        get_data = get_resp.json()
        assert get_data["id"] == webhook_id
        assert get_data["name"] == name
        assert get_data.get("url") == "https://httpbin.org/post"
        # Secret should NOT be returned in GET
        assert "secret" not in get_data, "Secret should not be exposed in GET single"

    def test_update_webhook(self, tenant_auth):
        """PUT /api/admin/webhooks/{id} — name update should persist."""
        if not TestWebhookCRUD.created_id:
            pytest.skip("No webhook created in previous test")
        webhook_id = TestWebhookCRUD.created_id
        new_name = "TEST_CRUD_Webhook_Updated"
        put_resp = tenant_auth.put(
            f"{BASE_URL}/api/admin/webhooks/{webhook_id}",
            json={"name": new_name},
        )
        assert put_resp.status_code == 200, \
            f"Update failed {put_resp.status_code}: {put_resp.text[:200]}"
        data = put_resp.json()
        assert data.get("name") == new_name, f"Name not updated: {data.get('name')}"

        # Verify via GET
        get_resp = tenant_auth.get(f"{BASE_URL}/api/admin/webhooks/{webhook_id}")
        assert get_resp.status_code == 200
        assert get_resp.json().get("name") == new_name

    def test_delete_webhook_and_verify_gone(self, tenant_auth):
        """DELETE /api/admin/webhooks/{id} — webhook should return 404 after deletion."""
        if not TestWebhookCRUD.created_id:
            pytest.skip("No webhook created in previous test")
        webhook_id = TestWebhookCRUD.created_id

        del_resp = tenant_auth.delete(f"{BASE_URL}/api/admin/webhooks/{webhook_id}")
        print(f"Delete webhook: status={del_resp.status_code}")
        assert del_resp.status_code in (200, 204), \
            f"Delete failed {del_resp.status_code}: {del_resp.text[:200]}"

        # Verify 404 after delete
        get_resp = tenant_auth.get(f"{BASE_URL}/api/admin/webhooks/{webhook_id}")
        assert get_resp.status_code == 404, \
            f"Expected 404 after delete, got {get_resp.status_code}: {get_resp.text[:200]}"

    def test_delete_nonexistent_webhook_returns_404(self, tenant_auth):
        """DELETE /api/admin/webhooks/nonexistent-id — must return 404."""
        resp = tenant_auth.delete(f"{BASE_URL}/api/admin/webhooks/nonexistent-fake-id-999")
        assert resp.status_code == 404, \
            f"Expected 404, got {resp.status_code}: {resp.text[:200]}"


# ---------------------------------------------------------------------------
# 4. Authentication enforcement
# ---------------------------------------------------------------------------

class TestWebhookAuthentication:
    """All webhook admin endpoints must reject unauthenticated requests."""

    def test_list_webhooks_requires_auth(self, session):
        """GET /api/admin/webhooks without token must return 401 or 403."""
        resp = session.get(f"{BASE_URL}/api/admin/webhooks")
        print(f"Unauth GET webhooks: status={resp.status_code}")
        assert resp.status_code in (401, 403), \
            f"Expected 401/403 without auth, got {resp.status_code}"

    def test_create_webhook_requires_auth(self, session):
        """POST /api/admin/webhooks without token must return 401 or 403."""
        resp = session.post(f"{BASE_URL}/api/admin/webhooks", json={
            "name": "TEST_Unauth",
            "url": "https://httpbin.org/post",
            "subscriptions": [],
        })
        print(f"Unauth POST webhook: status={resp.status_code}")
        assert resp.status_code in (401, 403), \
            f"Expected 401/403 without auth, got {resp.status_code}"

    def test_update_webhook_requires_auth(self, session):
        """PUT /api/admin/webhooks/fake-id without token must return 401 or 403."""
        resp = session.put(f"{BASE_URL}/api/admin/webhooks/fake-id",
                           json={"name": "Updated"})
        print(f"Unauth PUT webhook: status={resp.status_code}")
        assert resp.status_code in (401, 403), \
            f"Expected 401/403 without auth, got {resp.status_code}"

    def test_delete_webhook_requires_auth(self, session):
        """DELETE /api/admin/webhooks/fake-id without token must return 401 or 403."""
        resp = session.delete(f"{BASE_URL}/api/admin/webhooks/fake-id")
        print(f"Unauth DELETE webhook: status={resp.status_code}")
        assert resp.status_code in (401, 403), \
            f"Expected 401/403 without auth, got {resp.status_code}"

    def test_test_endpoint_requires_auth(self, session):
        """POST /api/admin/webhooks/fake-id/test without token must return 401 or 403."""
        resp = session.post(f"{BASE_URL}/api/admin/webhooks/fake-id/test",
                            json={"event": "order.created"})
        print(f"Unauth test webhook: status={resp.status_code}")
        assert resp.status_code in (401, 403), \
            f"Expected 401/403 without auth, got {resp.status_code}"

    def test_deliveries_requires_auth(self, session):
        """GET /api/admin/webhooks/fake-id/deliveries without token must return 401 or 403."""
        resp = session.get(f"{BASE_URL}/api/admin/webhooks/fake-id/deliveries")
        print(f"Unauth GET deliveries: status={resp.status_code}")
        assert resp.status_code in (401, 403), \
            f"Expected 401/403 without auth, got {resp.status_code}"


# ---------------------------------------------------------------------------
# 5. Tenant isolation: super admin using webhook endpoints
# ---------------------------------------------------------------------------

class TestWebhookTenantIsolation:
    """Tenant admin cannot access/delete webhooks from another tenant."""

    def test_tenant_cannot_delete_nonowned_webhook(self, tenant_auth, super_auth):
        """Tenant admin delete of a webhook they don't own returns 404 (not 200)."""
        # Create webhook as super_admin
        create_resp = super_auth.post(f"{BASE_URL}/api/admin/webhooks", json={
            "name": "TEST_SuperAdminWebhook",
            "url": "https://httpbin.org/post",
            "subscriptions": [],
        })
        if create_resp.status_code not in (200, 201):
            pytest.skip(f"Could not create super_admin webhook: {create_resp.status_code}")

        super_webhook_id = create_resp.json().get("id")
        assert super_webhook_id

        # Tenant admin tries to delete it — should be 404 (not found in their tenant)
        del_resp = tenant_auth.delete(f"{BASE_URL}/api/admin/webhooks/{super_webhook_id}")
        print(f"Cross-tenant delete: status={del_resp.status_code}")
        assert del_resp.status_code == 404, \
            f"Expected 404 for cross-tenant delete, got {del_resp.status_code}"

        # Cleanup: super_admin deletes it
        super_auth.delete(f"{BASE_URL}/api/admin/webhooks/{super_webhook_id}")


# ---------------------------------------------------------------------------
# 6. Cleanup of any leftover TEST_ webhooks from valid URL creation tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def cleanup_test_webhooks(request):
    """After all tests, clean up TEST_ prefixed webhooks."""
    yield
    # Best-effort cleanup
    try:
        session = requests.Session()
        login = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD,
        })
        if login.status_code == 200:
            token = login.json().get("token") or login.json().get("access_token")
            session.headers.update({
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            })
            list_resp = session.get(f"{BASE_URL}/api/admin/webhooks")
            if list_resp.status_code == 200:
                for wh in list_resp.json().get("webhooks", []):
                    if wh.get("name", "").startswith("TEST_"):
                        session.delete(f"{BASE_URL}/api/admin/webhooks/{wh['id']}")
                        print(f"Cleaned up webhook: {wh['name']} ({wh['id']})")
    except Exception as e:
        print(f"Cleanup error (non-fatal): {e}")
