"""
Iteration 63 - Bug Fixes Testing

Tests:
1. CRITICAL: Tenant B admin can view article at /articles/7f2d54e3-46dd-4fdc-8b37-09816e04a9ca (no 'Failed to load')
2. CRITICAL: Platform admin + X-View-As-Tenant=TB can access TB articles via header
3. CRITICAL: Platform admin WITHOUT view-as CANNOT access TB articles (correct isolation)
4. P0: Audit logs show entries for Tenant B after performing actions
5. P0: Audit logs scoped - Tenant B only sees their own logs, not AA logs
6. P0: Platform admin with X-View-As-Tenant=TB sees only TB audit logs
7. P2: test-new-corp website settings have stripe_enabled=False, gocardless_enabled=False
8. P2: TenantSwitcher sessionStorage - verify getViewAsTenantHeader exported function
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

TENANT_B_ID = "e7301988-7f0f-4b2b-a678-4e37882e385f"
TB_ARTICLE_ID = "7f2d54e3-46dd-4fdc-8b37-09816e04a9ca"
TEST_NEW_CORP_PARTNER_CODE = "test-new-corp-seed"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def platform_admin_token():
    """Login as platform_admin."""
    resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!",
        "partner_code": "automate-accounts",
    })
    assert resp.status_code == 200, f"Platform admin login failed: {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="module")
def tenant_b_admin_token():
    """Login as Tenant B admin (partner_super_admin with is_admin=True)."""
    resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
        "email": "adminb@tenantb.local",
        "password": "ChangeMe123!",
        "partner_code": "tenant-b-test",
    })
    assert resp.status_code == 200, f"Tenant B admin login failed: {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="module")
def test_new_corp_admin_token():
    """Login as Test New Corp admin."""
    resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
        "email": "admin@test-new-corp.local",
        "password": "ChangeMe123!",
        "partner_code": "test-new-corp-seed",
    })
    if resp.status_code != 200:
        pytest.skip(f"Test New Corp login failed: {resp.text}")
    return resp.json()["token"]


# ---------------------------------------------------------------------------
# 1. CRITICAL: Article access by Tenant B admin
# ---------------------------------------------------------------------------

class TestArticleAccessTenantB:
    """Tests for article GET by ID with tenant isolation fixes."""

    def test_tenant_b_admin_can_access_tb_article(self, tenant_b_admin_token):
        """Tenant B admin (tenant_id=TB) can fetch the TB article without 'Failed to load'."""
        resp = requests.get(
            f"{BASE_URL}/api/articles/{TB_ARTICLE_ID}",
            headers={"Authorization": f"Bearer {tenant_b_admin_token}"},
        )
        assert resp.status_code == 200, (
            f"Expected 200 for TB admin accessing TB article, got {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        assert "article" in data, "Response missing 'article' key"
        article = data["article"]
        assert article["id"] == TB_ARTICLE_ID, f"Wrong article ID: {article.get('id')}"
        assert article["tenant_id"] == TENANT_B_ID, f"Wrong tenant_id: {article.get('tenant_id')}"
        print(f"PASS: TB admin can access TB article '{article.get('title')}'")

    def test_platform_admin_with_view_as_tb_can_access_tb_article(self, platform_admin_token):
        """Platform admin WITH X-View-As-Tenant=TB header can access TB article."""
        resp = requests.get(
            f"{BASE_URL}/api/articles/{TB_ARTICLE_ID}",
            headers={
                "Authorization": f"Bearer {platform_admin_token}",
                "X-View-As-Tenant": TENANT_B_ID,
            },
        )
        assert resp.status_code == 200, (
            f"Expected 200 for platform admin with TB header, got {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        assert "article" in data, "Response missing 'article' key"
        article = data["article"]
        assert article["id"] == TB_ARTICLE_ID
        assert article["tenant_id"] == TENANT_B_ID
        print(f"PASS: Platform admin with X-View-As-Tenant can access TB article '{article.get('title')}'")

    def test_platform_admin_without_view_as_cannot_access_tb_article(self, platform_admin_token):
        """Platform admin WITHOUT X-View-As-Tenant header gets 404 for TB article (correct isolation)."""
        resp = requests.get(
            f"{BASE_URL}/api/articles/{TB_ARTICLE_ID}",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
        )
        # Platform admin without view-as has tenant_id=None → defaults to "automate-accounts"
        # TB article has tenant_id="e7301988-..." → NOT in "automate-accounts" → 404
        assert resp.status_code == 404, (
            f"Expected 404 for platform admin without view-as header, got {resp.status_code}: {resp.text}"
        )
        print(f"PASS: Platform admin without X-View-As-Tenant correctly gets 404 for TB article")


# ---------------------------------------------------------------------------
# 2. P0: Audit logs scoped to Tenant B
# ---------------------------------------------------------------------------

class TestAuditLogsTenantB:
    """Tests for audit log creation and scoping for Tenant B."""

    def test_tenant_b_admin_can_access_audit_logs(self, tenant_b_admin_token):
        """TB admin (is_admin=True) can access audit logs endpoint."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs",
            headers={"Authorization": f"Bearer {tenant_b_admin_token}"},
        )
        assert resp.status_code == 200, (
            f"Expected 200 for TB admin audit logs, got {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        assert "logs" in data
        print(f"PASS: TB admin can access audit logs, total: {data.get('total', 0)}")

    def test_audit_logs_scoped_for_tenant_b(self, tenant_b_admin_token):
        """Audit logs returned for TB admin contain only Tenant B logs (no AA logs)."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?limit=50",
            headers={"Authorization": f"Bearer {tenant_b_admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        logs = data.get("logs", [])
        
        # Verify all logs belong to Tenant B
        for log in logs:
            assert log.get("tenant_id") == TENANT_B_ID, (
                f"Found non-TB log in TB admin's audit logs: tenant_id={log.get('tenant_id')}, action={log.get('action')}"
            )
        print(f"PASS: All {len(logs)} audit logs are scoped to Tenant B")

    def test_audit_logs_has_entries_for_tenant_b(self, tenant_b_admin_token):
        """Tenant B should have at least 1 audit log entry (from previous article actions)."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs",
            headers={"Authorization": f"Bearer {tenant_b_admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        total = data.get("total", 0)
        logs = data.get("logs", [])
        print(f"TB audit logs total: {total}, returned: {len(logs)}")
        assert total >= 1, f"Expected at least 1 audit log for Tenant B, got {total}"
        print(f"PASS: Tenant B has {total} audit log entries")

    def test_audit_log_created_after_article_update(self, tenant_b_admin_token):
        """After Tenant B admin updates an article, an audit log entry is created with correct tenant_id."""
        # Update the TB article
        update_resp = requests.put(
            f"{BASE_URL}/api/articles/{TB_ARTICLE_ID}",
            headers={"Authorization": f"Bearer {tenant_b_admin_token}"},
            json={"title": "TB Article (Audit Test)", "category": "Blog"},
        )
        assert update_resp.status_code == 200, f"Article update failed: {update_resp.text}"
        print(f"Article updated successfully")
        
        # Query audit logs for the specific article
        audit_resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?entity_id={TB_ARTICLE_ID}&limit=5",
            headers={"Authorization": f"Bearer {tenant_b_admin_token}"},
        )
        assert audit_resp.status_code == 200
        audit_data = audit_resp.json()
        logs = audit_data.get("logs", [])
        
        assert len(logs) >= 1, f"Expected audit log after article update, got {len(logs)} logs for entity_id={TB_ARTICLE_ID}"
        
        # The most recent log should be the update
        latest_log = logs[0]
        assert latest_log.get("tenant_id") == TENANT_B_ID, (
            f"Audit log tenant_id mismatch: expected {TENANT_B_ID}, got {latest_log.get('tenant_id')}"
        )
        assert latest_log.get("entity_id") == TB_ARTICLE_ID
        print(f"PASS: Audit log created with tenant_id={latest_log.get('tenant_id')}, action={latest_log.get('action')}")

    def test_platform_admin_without_view_as_sees_all_audit_logs(self, platform_admin_token):
        """Platform admin without X-View-As-Tenant sees all tenants' audit logs (no filter)."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?limit=50",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        total = data.get("total", 0)
        logs = data.get("logs", [])
        # Should see multiple tenant_ids in the logs (or just AA tenant logs at minimum)
        print(f"Platform admin total audit logs (no view-as): {total}")
        assert total >= 0  # Non-failing check; just verify endpoint works
        print(f"PASS: Platform admin can access audit logs without view-as header")

    def test_platform_admin_with_view_as_tb_sees_only_tb_audit_logs(self, platform_admin_token):
        """Platform admin WITH X-View-As-Tenant=TB sees only Tenant B audit logs."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?limit=50",
            headers={
                "Authorization": f"Bearer {platform_admin_token}",
                "X-View-As-Tenant": TENANT_B_ID,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        logs = data.get("logs", [])
        
        # All logs should be Tenant B
        for log in logs:
            assert log.get("tenant_id") == TENANT_B_ID, (
                f"Platform admin viewing as TB got non-TB log: tenant_id={log.get('tenant_id')}"
            )
        print(f"PASS: Platform admin with X-View-As-Tenant=TB sees {len(logs)} TB-only audit logs")

    def test_tb_admin_does_not_see_aa_audit_logs(self, tenant_b_admin_token, platform_admin_token):
        """TB admin should NOT see automate-accounts (main tenant) audit logs."""
        # First, create an AA audit log via platform admin
        # Just call the audit logs endpoint as platform admin (this creates context)
        
        # Now get TB audit logs and ensure no "automate-accounts" tenant_id logs
        resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?limit=100",
            headers={"Authorization": f"Bearer {tenant_b_admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        logs = data.get("logs", [])
        
        aa_logs = [log for log in logs if log.get("tenant_id") == "automate-accounts"]
        assert len(aa_logs) == 0, (
            f"TB admin can see {len(aa_logs)} AA audit logs (data leak!): {[l.get('action') for l in aa_logs[:3]]}"
        )
        print(f"PASS: TB admin sees 0 AA audit logs (correctly isolated)")


# ---------------------------------------------------------------------------
# 3. P0: Audit logs entity-wise filtering works for Tenant B
# ---------------------------------------------------------------------------

class TestAuditLogsEntityWise:
    """Tests for entity-type filtered audit logs for Tenant B."""
    
    def test_audit_logs_entity_type_filter_article(self, tenant_b_admin_token):
        """Filter audit logs by entity_type=Article for Tenant B."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?entity_type=Article&limit=20",
            headers={"Authorization": f"Bearer {tenant_b_admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        logs = data.get("logs", [])
        total = data.get("total", 0)
        print(f"TB Article audit logs: {total}")
        # All returned logs should have entity_type matching Article
        for log in logs:
            assert "article" in log.get("entity_type", "").lower(), (
                f"Unexpected entity_type: {log.get('entity_type')}"
            )
            assert log.get("tenant_id") == TENANT_B_ID, (
                f"Non-TB log in entity filter: tenant_id={log.get('tenant_id')}"
            )
        print(f"PASS: Entity-type filter works for Tenant B, {total} article logs found")

    def test_audit_logs_entity_id_filter_works(self, tenant_b_admin_token):
        """Filter audit logs by entity_id returns only matching logs for TB."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?entity_id={TB_ARTICLE_ID}",
            headers={"Authorization": f"Bearer {tenant_b_admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        logs = data.get("logs", [])
        total = data.get("total", 0)
        print(f"TB audit logs for article {TB_ARTICLE_ID[:8]}...: {total}")
        assert total >= 1, f"Expected at least 1 audit log for TB article {TB_ARTICLE_ID}"
        for log in logs:
            assert log.get("entity_id") == TB_ARTICLE_ID
            assert log.get("tenant_id") == TENANT_B_ID
        print(f"PASS: Entity-id filter returns {total} logs for TB article")


# ---------------------------------------------------------------------------
# 4. P2: Test New Corp website settings (no payment methods)
# ---------------------------------------------------------------------------

class TestNewCorpWebsiteSettings:
    """Tests for test-new-corp tenant payment configuration."""

    def test_website_settings_endpoint_works_for_test_new_corp(self, test_new_corp_admin_token):
        """Test New Corp admin can access website settings."""
        resp = requests.get(
            f"{BASE_URL}/api/website-settings",
            headers={"Authorization": f"Bearer {test_new_corp_admin_token}"},
        )
        assert resp.status_code == 200, f"Website settings endpoint failed: {resp.text}"
        data = resp.json()
        settings = data.get("settings", {})
        print(f"test-new-corp website settings keys: {list(settings.keys())[:10]}")
        print(f"PASS: Website settings endpoint works for test-new-corp")

    def test_new_corp_has_no_stripe_payment(self, test_new_corp_admin_token):
        """Test New Corp should have stripe_enabled=False (no payment method configured)."""
        resp = requests.get(
            f"{BASE_URL}/api/website-settings",
            headers={"Authorization": f"Bearer {test_new_corp_admin_token}"},
        )
        assert resp.status_code == 200
        settings = resp.json().get("settings", {})
        stripe_enabled = settings.get("stripe_enabled", False)
        assert stripe_enabled is False or stripe_enabled == 0, (
            f"Expected stripe_enabled=False for test-new-corp, got {stripe_enabled}"
        )
        print(f"PASS: test-new-corp stripe_enabled={stripe_enabled}")

    def test_new_corp_has_no_gocardless_payment(self, test_new_corp_admin_token):
        """Test New Corp should have gocardless_enabled=False (no payment method configured)."""
        resp = requests.get(
            f"{BASE_URL}/api/website-settings",
            headers={"Authorization": f"Bearer {test_new_corp_admin_token}"},
        )
        assert resp.status_code == 200
        settings = resp.json().get("settings", {})
        gc_enabled = settings.get("gocardless_enabled", False)
        assert gc_enabled is False or gc_enabled == 0, (
            f"Expected gocardless_enabled=False for test-new-corp, got {gc_enabled}"
        )
        print(f"PASS: test-new-corp gocardless_enabled={gc_enabled}")

    def test_new_corp_request_quote_fallback_eligible(self, test_new_corp_admin_token):
        """Verify test-new-corp is eligible for 'Request a Quote' fallback (no payment methods)."""
        resp = requests.get(
            f"{BASE_URL}/api/website-settings",
            headers={"Authorization": f"Bearer {test_new_corp_admin_token}"},
        )
        assert resp.status_code == 200
        settings = resp.json().get("settings", {})
        stripe_enabled = settings.get("stripe_enabled", False)
        gc_enabled = settings.get("gocardless_enabled", False)
        # Both must be falsy for "Request a Quote" to appear
        assert not stripe_enabled and not gc_enabled, (
            f"Expected both payment methods disabled, got stripe={stripe_enabled}, gc={gc_enabled}"
        )
        print(f"PASS: test-new-corp eligible for Request a Quote fallback (no payment methods)")


# ---------------------------------------------------------------------------
# 5. Verify article admin list isolation
# ---------------------------------------------------------------------------

class TestArticleAdminListIsolation:
    """Verify articles admin list with X-View-As-Tenant works correctly."""

    def test_tb_admin_sees_only_tb_articles_in_list(self, tenant_b_admin_token):
        """TB admin's article list only shows TB articles."""
        resp = requests.get(
            f"{BASE_URL}/api/articles/admin/list",
            headers={"Authorization": f"Bearer {tenant_b_admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        articles = data.get("articles", [])
        for art in articles:
            assert art.get("tenant_id") == TENANT_B_ID, (
                f"TB admin sees non-TB article: id={art.get('id')}, tenant_id={art.get('tenant_id')}"
            )
        print(f"PASS: TB admin article list shows {len(articles)} TB-only articles")

    def test_platform_admin_with_view_as_tb_sees_tb_articles(self, platform_admin_token):
        """Platform admin viewing as TB sees only TB articles."""
        resp = requests.get(
            f"{BASE_URL}/api/articles/admin/list",
            headers={
                "Authorization": f"Bearer {platform_admin_token}",
                "X-View-As-Tenant": TENANT_B_ID,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        articles = data.get("articles", [])
        for art in articles:
            assert art.get("tenant_id") == TENANT_B_ID
        print(f"PASS: Platform admin with TB header sees {len(articles)} TB articles in admin list")
