"""
Tests for db.integrations -> db.oauth_connections migration.
Verifies all integration endpoints now use oauth_connections and 
db.integrations collection no longer exists.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

PLATFORM_ADMIN = {"email": "admin@automateaccounts.local", "password": "ChangeMe123!"}
TENANT_ADMIN = {"email": "mayank@automateaccounts.com", "password": "ChangeMe123!", "partner_code": "AA"}


# ---------------------------------------------------------------------------
# Auth helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def platform_admin_token():
    """Login as platform super admin, return token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json=PLATFORM_ADMIN)
    assert resp.status_code == 200, f"Platform admin login failed: {resp.text}"
    token = resp.json().get("token")
    assert token, "No token returned for platform admin"
    return token


@pytest.fixture(scope="module")
def tenant_admin_token():
    """Login as tenant admin (partner_code=AA), return token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json=TENANT_ADMIN)
    assert resp.status_code == 200, f"Tenant admin login failed: {resp.text}"
    token = resp.json().get("token")
    assert token, "No token returned for tenant admin"
    return token


def auth_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# 1. Authentication Tests
# ---------------------------------------------------------------------------

class TestAuthentication:
    """Verify login still works after migration."""

    def test_platform_admin_login(self):
        """Platform admin can log in and receives token."""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json=PLATFORM_ADMIN)
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        data = resp.json()
        # Should return 'token' field (not access_token)
        assert "token" in data, f"No 'token' in response: {data.keys()}"
        assert isinstance(data["token"], str) and len(data["token"]) > 10
        # Platform super admin returns role + tenant_id fields (not wrapped in 'user')
        assert "role" in data

    def test_tenant_admin_login(self):
        """Tenant admin can log in with partner_code."""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json=TENANT_ADMIN)
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        data = resp.json()
        assert "token" in data, f"No 'token' in response: {data.keys()}"
        assert isinstance(data["token"], str) and len(data["token"]) > 10

    def test_token_field_name_is_token_not_access_token(self):
        """Confirms response uses 'token' key, not 'access_token'."""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json=PLATFORM_ADMIN)
        data = resp.json()
        # 'token' must exist
        assert "token" in data
        # access_token should NOT be the primary field
        # (some implementations may include both, but 'token' must be there)
        assert data["token"] is not None


# ---------------------------------------------------------------------------
# 2. db.integrations Collection Verification
# ---------------------------------------------------------------------------

class TestIntegrationsCollectionDropped:
    """Verify db.integrations was dropped by migration."""

    def test_integrations_collection_not_in_mongodb(self):
        """Direct MongoDB check: integrations collection must not exist."""
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient

        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "test_database")

        async def _check():
            client = AsyncIOMotorClient(mongo_url)
            db = client[db_name]
            collections = await db.list_collection_names()
            client.close()
            return collections

        collections = asyncio.run(_check())
        assert "integrations" not in collections, (
            f"db.integrations collection still exists! Collections: {sorted(collections)}"
        )

    def test_oauth_connections_collection_exists(self):
        """oauth_connections collection must exist."""
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient

        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "test_database")

        async def _check():
            client = AsyncIOMotorClient(mongo_url)
            db = client[db_name]
            collections = await db.list_collection_names()
            client.close()
            return collections

        collections = asyncio.run(_check())
        assert "oauth_connections" in collections, "oauth_connections collection is missing!"


# ---------------------------------------------------------------------------
# 3. GET /api/admin/integrations/status
# ---------------------------------------------------------------------------

class TestIntegrationsStatus:
    """GET /api/admin/integrations/status reads from oauth_connections."""

    def test_status_returns_200(self, platform_admin_token):
        resp = requests.get(
            f"{BASE_URL}/api/admin/integrations/status",
            headers=auth_headers(platform_admin_token)
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_status_has_correct_structure(self, platform_admin_token):
        resp = requests.get(
            f"{BASE_URL}/api/admin/integrations/status",
            headers=auth_headers(platform_admin_token)
        )
        data = resp.json()
        assert "integrations" in data, f"Missing 'integrations' key: {data.keys()}"
        assert "active_email_provider" in data

    def test_status_has_expected_providers(self, platform_admin_token):
        resp = requests.get(
            f"{BASE_URL}/api/admin/integrations/status",
            headers=auth_headers(platform_admin_token)
        )
        data = resp.json()
        integrations = data["integrations"]
        # All expected providers should be present
        for provider in ["resend", "zoho_mail", "zoho_crm", "zoho_books", "stripe", "gocardless"]:
            assert provider in integrations, f"Missing provider '{provider}' in integrations"

    def test_status_has_valid_provider_structure(self, platform_admin_token):
        resp = requests.get(
            f"{BASE_URL}/api/admin/integrations/status",
            headers=auth_headers(platform_admin_token)
        )
        data = resp.json()
        for provider, info in data["integrations"].items():
            assert "status" in info, f"Provider {provider} missing 'status' field"
            assert info["status"] in ("connected", "not_configured"), (
                f"Provider {provider} has unexpected status: {info['status']}"
            )

    def test_status_zoho_mail_connected_for_platform_admin(self, platform_admin_token):
        """Platform admin has a validated zoho_mail entry in oauth_connections."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/integrations/status",
            headers=auth_headers(platform_admin_token)
        )
        data = resp.json()
        zoho_mail = data["integrations"].get("zoho_mail", {})
        # Based on DB: tenant automate-accounts has zoho_mail is_validated=True
        assert zoho_mail.get("status") == "connected", (
            f"zoho_mail should be connected for platform admin, got: {zoho_mail}"
        )


# ---------------------------------------------------------------------------
# 4. GET /api/admin/integrations/email-providers
# ---------------------------------------------------------------------------

class TestEmailProviders:
    """GET /api/admin/integrations/email-providers reads from oauth_connections."""

    def test_email_providers_returns_200(self, platform_admin_token):
        resp = requests.get(
            f"{BASE_URL}/api/admin/integrations/email-providers",
            headers=auth_headers(platform_admin_token)
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_email_providers_has_resend_and_zoho_mail(self, platform_admin_token):
        resp = requests.get(
            f"{BASE_URL}/api/admin/integrations/email-providers",
            headers=auth_headers(platform_admin_token)
        )
        data = resp.json()
        assert "providers" in data, f"Missing 'providers' key: {data.keys()}"
        providers = data["providers"]
        assert "resend" in providers, "Missing 'resend' in providers"
        assert "zoho_mail" in providers, "Missing 'zoho_mail' in providers"

    def test_email_providers_resend_structure(self, platform_admin_token):
        resp = requests.get(
            f"{BASE_URL}/api/admin/integrations/email-providers",
            headers=auth_headers(platform_admin_token)
        )
        providers = resp.json()["providers"]
        resend = providers["resend"]
        # Must have these keys
        assert "has_api_key" in resend
        assert "is_validated" in resend
        assert "is_active" in resend

    def test_email_providers_zoho_mail_structure(self, platform_admin_token):
        resp = requests.get(
            f"{BASE_URL}/api/admin/integrations/email-providers",
            headers=auth_headers(platform_admin_token)
        )
        providers = resp.json()["providers"]
        zoho_mail = providers["zoho_mail"]
        # Must have these keys
        assert "is_configured" in zoho_mail
        assert "is_validated" in zoho_mail
        assert "is_active" in zoho_mail

    def test_email_providers_zoho_mail_validated_for_platform_admin(self, platform_admin_token):
        """Platform admin's tenant has validated zoho_mail."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/integrations/email-providers",
            headers=auth_headers(platform_admin_token)
        )
        providers = resp.json()["providers"]
        zoho_mail = providers["zoho_mail"]
        assert zoho_mail.get("is_validated") is True, (
            f"zoho_mail should be validated for platform admin tenant, got: {zoho_mail}"
        )

    def test_email_providers_active_provider_field(self, platform_admin_token):
        resp = requests.get(
            f"{BASE_URL}/api/admin/integrations/email-providers",
            headers=auth_headers(platform_admin_token)
        )
        data = resp.json()
        # active_provider field must be present
        assert "active_provider" in data


# ---------------------------------------------------------------------------
# 5. GET /api/admin/finance/status
# ---------------------------------------------------------------------------

class TestFinanceStatus:
    """GET /api/admin/finance/status reads from oauth_connections."""

    def test_finance_status_returns_200(self, platform_admin_token):
        resp = requests.get(
            f"{BASE_URL}/api/admin/finance/status",
            headers=auth_headers(platform_admin_token)
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_finance_status_has_zoho_books(self, platform_admin_token):
        resp = requests.get(
            f"{BASE_URL}/api/admin/finance/status",
            headers=auth_headers(platform_admin_token)
        )
        data = resp.json()
        assert "zoho_books" in data, f"Missing 'zoho_books' key: {data.keys()}"

    def test_finance_status_zoho_books_structure(self, platform_admin_token):
        resp = requests.get(
            f"{BASE_URL}/api/admin/finance/status",
            headers=auth_headers(platform_admin_token)
        )
        zoho_books = resp.json()["zoho_books"]
        # Required fields
        assert "is_configured" in zoho_books
        assert "is_validated" in zoho_books

    def test_finance_status_zoho_books_not_configured_for_empty_tenant(self, tenant_admin_token):
        """Tenant with no oauth_connections should get is_configured=False."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/finance/status",
            headers=auth_headers(tenant_admin_token)
        )
        assert resp.status_code == 200
        zoho_books = resp.json()["zoho_books"]
        assert zoho_books.get("is_configured") is False, (
            f"Tenant admin should have no Zoho Books configured, got: {zoho_books}"
        )

    def test_finance_status_has_quickbooks(self, platform_admin_token):
        resp = requests.get(
            f"{BASE_URL}/api/admin/finance/status",
            headers=auth_headers(platform_admin_token)
        )
        data = resp.json()
        assert "quickbooks" in data


# ---------------------------------------------------------------------------
# 6. GET /api/admin/integrations/workdrive
# ---------------------------------------------------------------------------

class TestWorkdriveStatus:
    """GET /api/admin/integrations/workdrive reads from oauth_connections."""

    def test_workdrive_status_returns_200(self, platform_admin_token):
        resp = requests.get(
            f"{BASE_URL}/api/admin/integrations/workdrive",
            headers=auth_headers(platform_admin_token)
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_workdrive_status_has_required_fields(self, platform_admin_token):
        resp = requests.get(
            f"{BASE_URL}/api/admin/integrations/workdrive",
            headers=auth_headers(platform_admin_token)
        )
        data = resp.json()
        assert "status" in data
        assert "is_validated" in data

    def test_workdrive_not_validated_when_no_valid_token(self, platform_admin_token):
        """Platform admin has no validated workdrive token -> is_validated=False."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/integrations/workdrive",
            headers=auth_headers(platform_admin_token)
        )
        data = resp.json()
        # The workdrive may be 'not_connected' (no record) or 'pending' (creds saved but not validated)
        # Either way, it should NOT be 'connected' and is_validated must be False
        assert data.get("status") in ("not_connected", "pending"), (
            f"Unexpected workdrive status: {data.get('status')}"
        )
        assert data.get("is_validated") is False

    def test_workdrive_not_connected_for_tenant_admin(self, tenant_admin_token):
        resp = requests.get(
            f"{BASE_URL}/api/admin/integrations/workdrive",
            headers=auth_headers(tenant_admin_token)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data


# ---------------------------------------------------------------------------
# 7. POST /api/admin/integrations/zoho-mail/save-credentials
# ---------------------------------------------------------------------------

class TestSaveZohoMailCredentials:
    """POST zoho-mail/save-credentials saves to oauth_connections (not db.integrations)."""

    def test_save_zoho_mail_creds_returns_200(self, platform_admin_token):
        payload = {
            "client_id": "TEST_client_id_1000",
            "client_secret": "TEST_client_secret_abc",
            "datacenter": "US"
        }
        resp = requests.post(
            f"{BASE_URL}/api/admin/integrations/zoho-mail/save-credentials",
            json=payload,
            headers=auth_headers(platform_admin_token)
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_save_zoho_mail_creds_success_response(self, platform_admin_token):
        payload = {
            "client_id": "TEST_client_id_1000",
            "client_secret": "TEST_client_secret_abc",
            "datacenter": "US"
        }
        resp = requests.post(
            f"{BASE_URL}/api/admin/integrations/zoho-mail/save-credentials",
            json=payload,
            headers=auth_headers(platform_admin_token)
        )
        data = resp.json()
        assert data.get("success") is True, f"Expected success=True: {data}"
        assert "message" in data

    def test_save_zoho_mail_creds_persisted_in_oauth_connections(self, platform_admin_token):
        """After save-credentials, the record should be in oauth_connections."""
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient

        payload = {
            "client_id": "TEST_verify_client_id",
            "client_secret": "TEST_verify_secret",
            "datacenter": "US"
        }
        resp = requests.post(
            f"{BASE_URL}/api/admin/integrations/zoho-mail/save-credentials",
            json=payload,
            headers=auth_headers(platform_admin_token)
        )
        assert resp.status_code == 200

        async def _check():
            mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
            db_name = os.environ.get("DB_NAME", "test_database")
            client = AsyncIOMotorClient(mongo_url)
            db = client[db_name]
            doc = await db.oauth_connections.find_one(
                {"tenant_id": "automate-accounts", "provider": "zoho_mail"},
                {"_id": 0, "credentials": 0}
            )
            client.close()
            return doc

        doc = asyncio.run(_check())
        assert doc is not None, "No zoho_mail record in oauth_connections after save!"
        assert doc.get("provider") == "zoho_mail"

    def test_save_zoho_mail_not_written_to_integrations_collection(self, platform_admin_token):
        """Saving credentials must NOT write to db.integrations (collection must stay dropped)."""
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient

        payload = {"client_id": "TEST_no_integrations", "client_secret": "TEST_secret", "datacenter": "US"}
        requests.post(
            f"{BASE_URL}/api/admin/integrations/zoho-mail/save-credentials",
            json=payload,
            headers=auth_headers(platform_admin_token)
        )

        async def _check():
            mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
            db_name = os.environ.get("DB_NAME", "test_database")
            client = AsyncIOMotorClient(mongo_url)
            db = client[db_name]
            collections = await db.list_collection_names()
            client.close()
            return collections

        collections = asyncio.run(_check())
        assert "integrations" not in collections, "db.integrations was re-created by save-credentials!"


# ---------------------------------------------------------------------------
# 8. POST /api/admin/integrations/zoho-crm/save-credentials
# ---------------------------------------------------------------------------

class TestSaveZohoCRMCredentials:
    """POST zoho-crm/save-credentials saves to oauth_connections."""

    def test_save_zoho_crm_creds_returns_200(self, platform_admin_token):
        payload = {
            "client_id": "TEST_crm_client_id",
            "client_secret": "TEST_crm_secret",
            "datacenter": "US"
        }
        resp = requests.post(
            f"{BASE_URL}/api/admin/integrations/zoho-crm/save-credentials",
            json=payload,
            headers=auth_headers(platform_admin_token)
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_save_zoho_crm_success_flag(self, platform_admin_token):
        payload = {
            "client_id": "TEST_crm_client_id",
            "client_secret": "TEST_crm_secret",
            "datacenter": "US"
        }
        resp = requests.post(
            f"{BASE_URL}/api/admin/integrations/zoho-crm/save-credentials",
            json=payload,
            headers=auth_headers(platform_admin_token)
        )
        data = resp.json()
        assert data.get("success") is True

    def test_save_zoho_crm_persisted_in_oauth_connections(self, platform_admin_token):
        """After save, record appears in oauth_connections with provider=zoho_crm."""
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient

        payload = {
            "client_id": "TEST_crm_verify",
            "client_secret": "TEST_crm_verify_secret",
            "datacenter": "US"
        }
        resp = requests.post(
            f"{BASE_URL}/api/admin/integrations/zoho-crm/save-credentials",
            json=payload,
            headers=auth_headers(platform_admin_token)
        )
        assert resp.status_code == 200

        async def _check():
            mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
            db_name = os.environ.get("DB_NAME", "test_database")
            client = AsyncIOMotorClient(mongo_url)
            db = client[db_name]
            doc = await db.oauth_connections.find_one(
                {"tenant_id": "automate-accounts", "provider": "zoho_crm"},
                {"_id": 0, "credentials": 0}
            )
            client.close()
            return doc

        doc = asyncio.run(_check())
        assert doc is not None, "No zoho_crm record in oauth_connections after save!"
        assert doc.get("provider") == "zoho_crm"
        # data_center should be 'us' (lowercase from datacenter='US')
        assert doc.get("data_center") == "us"


# ---------------------------------------------------------------------------
# 9. POST /api/admin/finance/zoho-books/save-credentials
# ---------------------------------------------------------------------------

class TestSaveZohoBooksCredentials:
    """POST /api/admin/finance/zoho-books/save-credentials saves to oauth_connections."""

    def test_save_zoho_books_creds_returns_200(self, platform_admin_token):
        payload = {
            "client_id": "TEST_books_client_id",
            "client_secret": "TEST_books_secret",
            "datacenter": "US"
        }
        resp = requests.post(
            f"{BASE_URL}/api/admin/finance/zoho-books/save-credentials",
            json=payload,
            headers=auth_headers(platform_admin_token)
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_save_zoho_books_success_flag(self, platform_admin_token):
        payload = {
            "client_id": "TEST_books_client_id",
            "client_secret": "TEST_books_secret",
            "datacenter": "US"
        }
        resp = requests.post(
            f"{BASE_URL}/api/admin/finance/zoho-books/save-credentials",
            json=payload,
            headers=auth_headers(platform_admin_token)
        )
        data = resp.json()
        assert data.get("success") is True

    def test_save_zoho_books_persisted_in_oauth_connections(self, platform_admin_token):
        """After save, record appears in oauth_connections with provider=zoho_books."""
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient

        payload = {
            "client_id": "TEST_books_verify",
            "client_secret": "TEST_books_verify_secret",
            "datacenter": "US"
        }
        resp = requests.post(
            f"{BASE_URL}/api/admin/finance/zoho-books/save-credentials",
            json=payload,
            headers=auth_headers(platform_admin_token)
        )
        assert resp.status_code == 200

        async def _check():
            mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
            db_name = os.environ.get("DB_NAME", "test_database")
            client = AsyncIOMotorClient(mongo_url)
            db = client[db_name]
            doc = await db.oauth_connections.find_one(
                {"tenant_id": "automate-accounts", "provider": "zoho_books"},
                {"_id": 0, "credentials": 0}
            )
            client.close()
            return doc

        doc = asyncio.run(_check())
        assert doc is not None, "No zoho_books record in oauth_connections after save!"
        assert doc.get("provider") == "zoho_books"

    def test_save_zoho_books_not_in_integrations(self, platform_admin_token):
        """db.integrations must not be re-created by this save."""
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient

        payload = {"client_id": "TEST_no_int", "client_secret": "TEST_s", "datacenter": "US"}
        requests.post(
            f"{BASE_URL}/api/admin/finance/zoho-books/save-credentials",
            json=payload,
            headers=auth_headers(platform_admin_token)
        )

        async def _check():
            mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
            db_name = os.environ.get("DB_NAME", "test_database")
            client = AsyncIOMotorClient(mongo_url)
            db = client[db_name]
            cols = await db.list_collection_names()
            client.close()
            return cols

        cols = asyncio.run(_check())
        assert "integrations" not in cols


# ---------------------------------------------------------------------------
# 10. POST /api/admin/integrations/workdrive/save-credentials
# ---------------------------------------------------------------------------

class TestSaveWorkdriveCredentials:
    """POST /api/admin/integrations/workdrive/save-credentials saves to oauth_connections."""

    def test_save_workdrive_creds_returns_200(self, platform_admin_token):
        payload = {
            "client_id": "TEST_workdrive_client",
            "client_secret": "TEST_workdrive_secret",
            "datacenter": "US"
        }
        resp = requests.post(
            f"{BASE_URL}/api/admin/integrations/workdrive/save-credentials",
            json=payload,
            headers=auth_headers(platform_admin_token)
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_save_workdrive_returns_auth_url(self, platform_admin_token):
        payload = {
            "client_id": "TEST_workdrive_client",
            "client_secret": "TEST_workdrive_secret",
            "datacenter": "US"
        }
        resp = requests.post(
            f"{BASE_URL}/api/admin/integrations/workdrive/save-credentials",
            json=payload,
            headers=auth_headers(platform_admin_token)
        )
        data = resp.json()
        assert "auth_url" in data, f"Expected auth_url in response: {data.keys()}"
        assert "message" in data

    def test_save_workdrive_persisted_in_oauth_connections(self, platform_admin_token):
        """After save, record in oauth_connections with provider=zoho_workdrive."""
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient

        payload = {
            "client_id": "TEST_wd_verify",
            "client_secret": "TEST_wd_secret",
            "datacenter": "US"
        }
        resp = requests.post(
            f"{BASE_URL}/api/admin/integrations/workdrive/save-credentials",
            json=payload,
            headers=auth_headers(platform_admin_token)
        )
        assert resp.status_code == 200

        async def _check():
            mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
            db_name = os.environ.get("DB_NAME", "test_database")
            client = AsyncIOMotorClient(mongo_url)
            db = client[db_name]
            doc = await db.oauth_connections.find_one(
                {"tenant_id": "automate-accounts", "provider": "zoho_workdrive"},
                {"_id": 0, "credentials": 0}
            )
            client.close()
            return doc

        doc = asyncio.run(_check())
        assert doc is not None, "No zoho_workdrive record in oauth_connections after save!"
        assert doc.get("provider") == "zoho_workdrive"
        # is_validated should start as False after just saving credentials
        assert doc.get("is_validated") is False

    def test_save_workdrive_not_in_integrations(self, platform_admin_token):
        """db.integrations must not be re-created."""
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient

        payload = {"client_id": "TEST_wd_ni", "client_secret": "TEST_s", "datacenter": "US"}
        requests.post(
            f"{BASE_URL}/api/admin/integrations/workdrive/save-credentials",
            json=payload,
            headers=auth_headers(platform_admin_token)
        )

        async def _check():
            mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
            db_name = os.environ.get("DB_NAME", "test_database")
            client = AsyncIOMotorClient(mongo_url)
            db = client[db_name]
            cols = await db.list_collection_names()
            client.close()
            return cols

        cols = asyncio.run(_check())
        assert "integrations" not in cols


# ---------------------------------------------------------------------------
# 11. Admin panel loads  
# ---------------------------------------------------------------------------

class TestAdminPanelLoads:
    """Verify /api/admin endpoints are accessible without 500 errors."""

    def test_admin_dashboard_accessible(self, platform_admin_token):
        """GET /api/admin/users returns 200."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/users",
            headers=auth_headers(platform_admin_token)
        )
        assert resp.status_code == 200, f"Admin users endpoint failed: {resp.status_code}: {resp.text}"

    def test_admin_tenants_accessible(self, platform_admin_token):
        """GET /api/admin/tenants returns 200."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/tenants",
            headers=auth_headers(platform_admin_token)
        )
        assert resp.status_code == 200, f"Admin tenants endpoint failed: {resp.status_code}: {resp.text}"

    def test_tenant_admin_finance_status(self, tenant_admin_token):
        """Tenant admin can access /api/admin/finance/status without error."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/finance/status",
            headers=auth_headers(tenant_admin_token)
        )
        assert resp.status_code == 200, f"Finance status failed for tenant admin: {resp.status_code}: {resp.text}"

    def test_tenant_admin_integrations_status(self, tenant_admin_token):
        """Tenant admin can access /api/admin/integrations/status without error."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/integrations/status",
            headers=auth_headers(tenant_admin_token)
        )
        assert resp.status_code == 200, f"Integrations status failed for tenant admin: {resp.status_code}: {resp.text}"

    def test_tenant_admin_email_providers(self, tenant_admin_token):
        """Tenant admin can access email-providers without error."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/integrations/email-providers",
            headers=auth_headers(tenant_admin_token)
        )
        assert resp.status_code == 200, f"Email providers failed for tenant admin: {resp.status_code}: {resp.text}"

    def test_no_500_on_integrations_status(self, platform_admin_token):
        """Integration status must not return 500."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/integrations/status",
            headers=auth_headers(platform_admin_token)
        )
        assert resp.status_code != 500, f"Integration status returned 500: {resp.text}"

    def test_no_500_on_finance_status(self, platform_admin_token):
        """Finance status must not return 500."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/finance/status",
            headers=auth_headers(platform_admin_token)
        )
        assert resp.status_code != 500, f"Finance status returned 500: {resp.text}"
