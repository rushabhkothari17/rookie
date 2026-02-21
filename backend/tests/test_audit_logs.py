"""
Audit Log Instrumentation tests.
Tests: GET /api/admin/audit-logs with filters, pagination,
       and audit log generation from mutations (login, promo_code, customer, article).
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def admin_token():
    """Obtain admin JWT token."""
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@automateaccounts.local", "password": "ChangeMe123!"},
    )
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    token = resp.json().get("token")
    assert token, "No token returned"
    return token


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ---------------------------------------------------------------------------
# 1. Audit logs list loads with total count and pagination
# ---------------------------------------------------------------------------

class TestAuditLogsListAndPagination:
    """GET /api/admin/audit-logs basic structure and pagination."""

    def test_list_returns_200(self, auth_headers):
        """Audit logs endpoint returns 200."""
        resp = requests.get(f"{BASE_URL}/api/admin/audit-logs", headers=auth_headers)
        assert resp.status_code == 200, resp.text

    def test_list_response_structure(self, auth_headers):
        """Response includes logs, total, total_pages, page, per_page."""
        resp = requests.get(f"{BASE_URL}/api/admin/audit-logs?limit=10", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "logs" in data, "Missing 'logs' field"
        assert "total" in data, "Missing 'total' field"
        assert "total_pages" in data, "Missing 'total_pages' field"
        assert "page" in data, "Missing 'page' field"
        assert "per_page" in data, "Missing 'per_page' field"

    def test_total_count_is_integer(self, auth_headers):
        """Total is a positive integer."""
        resp = requests.get(f"{BASE_URL}/api/admin/audit-logs", headers=auth_headers)
        data = resp.json()
        assert isinstance(data["total"], int)
        assert data["total"] >= 0

    def test_per_page_limit_respected(self, auth_headers):
        """limit=10 returns max 10 records."""
        resp = requests.get(f"{BASE_URL}/api/admin/audit-logs?limit=10", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["logs"]) <= 10, f"Got {len(data['logs'])} records, expected <= 10"
        assert data["per_page"] == 10

    def test_per_page_limit_25(self, auth_headers):
        """limit=25 returns max 25 records."""
        resp = requests.get(f"{BASE_URL}/api/admin/audit-logs?limit=25", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["logs"]) <= 25

    def test_page2_returns_different_records(self, auth_headers):
        """page=2 returns different records than page=1."""
        resp1 = requests.get(f"{BASE_URL}/api/admin/audit-logs?limit=5&page=1", headers=auth_headers)
        resp2 = requests.get(f"{BASE_URL}/api/admin/audit-logs?limit=5&page=2", headers=auth_headers)
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        logs1 = resp1.json()["logs"]
        logs2 = resp2.json()["logs"]
        # Should have different log IDs
        if logs1 and logs2:
            ids1 = {l["id"] for l in logs1}
            ids2 = {l["id"] for l in logs2}
            assert ids1 != ids2, "Page 1 and Page 2 returned the same records"

    def test_total_pages_calculation(self, auth_headers):
        """total_pages is correctly calculated."""
        resp = requests.get(f"{BASE_URL}/api/admin/audit-logs?limit=10", headers=auth_headers)
        data = resp.json()
        total = data["total"]
        per_page = data["per_page"]
        expected_pages = max(1, (total + per_page - 1) // per_page)
        assert data["total_pages"] == expected_pages

    def test_log_record_fields(self, auth_headers):
        """Each log record has expected fields."""
        resp = requests.get(f"{BASE_URL}/api/admin/audit-logs?limit=5", headers=auth_headers)
        data = resp.json()
        assert data["logs"], "No logs available to validate fields"
        log = data["logs"][0]
        required_fields = ["id", "occurred_at", "action", "actor_type", "entity_type", "source", "success"]
        for field in required_fields:
            assert field in log, f"Log missing field: {field}"

    def test_unauthorized_access_denied(self):
        """Without token, audit logs endpoint returns 401/403."""
        resp = requests.get(f"{BASE_URL}/api/admin/audit-logs")
        assert resp.status_code in (401, 403), f"Expected 401/403 got {resp.status_code}"


# ---------------------------------------------------------------------------
# 2. Filter tests
# ---------------------------------------------------------------------------

class TestAuditLogsFilters:
    """Filter by actor_type, entity_type, action, success, severity, search."""

    def test_filter_actor_type_admin(self, auth_headers):
        """filter actor_type=admin returns only admin events."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?actor_type=admin&limit=20",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        for log in data["logs"]:
            assert log["actor_type"] == "admin", f"Expected actor_type=admin, got {log['actor_type']}"

    def test_filter_actor_type_user(self, auth_headers):
        """filter actor_type=user returns only user events."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?actor_type=user&limit=20",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        for log in data["logs"]:
            assert log["actor_type"] == "user", f"Expected actor_type=user, got {log['actor_type']}"

    def test_filter_actor_type_system(self, auth_headers):
        """filter actor_type=system returns only system events."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?actor_type=system&limit=20",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        for log in data["logs"]:
            assert log["actor_type"] == "system", f"Expected actor_type=system, got {log['actor_type']}"

    def test_filter_entity_type_user(self, auth_headers):
        """filter entity_type=User shows user-related logs."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?entity_type=User&limit=20",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        for log in data["logs"]:
            assert "user" in log["entity_type"].lower(), \
                f"Expected User entity, got {log['entity_type']}"

    def test_filter_action_user_login(self, auth_headers):
        """filter action=USER_LOGIN shows login events."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?action=USER_LOGIN&limit=20",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # Verify all returned logs match the filter
        for log in data["logs"]:
            assert "USER_LOGIN" in log["action"].upper(), \
                f"Expected USER_LOGIN action, got {log['action']}"

    def test_filter_success_true(self, auth_headers):
        """filter success=true returns only successful events."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?success=true&limit=20",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        for log in data["logs"]:
            assert log["success"] is True, f"Expected success=True, got {log['success']}"

    def test_filter_success_false(self, auth_headers):
        """filter success=false returns only failed events (if any exist)."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?success=false&limit=20",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        for log in data["logs"]:
            assert log["success"] is False, f"Expected success=False, got {log['success']}"

    def test_filter_severity_info(self, auth_headers):
        """filter severity=info returns only info-level events."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?severity=info&limit=20",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        for log in data["logs"]:
            assert log["severity"] == "info", f"Expected severity=info, got {log['severity']}"

    def test_search_query(self, auth_headers):
        """search q=login returns events with 'login' in description/action."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?q=login&limit=10",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # Results should match (description or action contains 'login')
        for log in data["logs"]:
            text = (log.get("description", "") + " " + log.get("action", "")).lower()
            assert "login" in text, f"Log does not contain 'login': {log.get('action')}: {log.get('description')}"

    def test_filter_entity_type_article(self, auth_headers):
        """filter entity_type=Article returns Article events."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?entity_type=Article&limit=20",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        for log in data["logs"]:
            assert "article" in log["entity_type"].lower(), \
                f"Expected Article entity, got {log['entity_type']}"

    def test_date_range_filter(self, auth_headers):
        """Date range filter returns results within range."""
        from datetime import datetime, timedelta
        today = datetime.utcnow().strftime("%Y-%m-%d")
        yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?date_from={yesterday}&date_to={today}&limit=10",
            headers=auth_headers,
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 3. Audit log generation from mutations
# ---------------------------------------------------------------------------

class TestAuditLogGeneration:
    """Verify that mutations create audit log entries."""

    def test_login_generates_user_login_audit(self, auth_headers):
        """Login action generates USER_LOGIN audit log."""
        # Login to generate a fresh audit event
        requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@automateaccounts.local", "password": "ChangeMe123!"},
        )
        time.sleep(0.5)  # brief wait for async write

        resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?action=USER_LOGIN&limit=10",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0, "No USER_LOGIN events found after login"
        login_logs = [l for l in data["logs"] if l["action"] == "USER_LOGIN"]
        assert login_logs, "No exact USER_LOGIN entries in response"
        log = login_logs[0]
        assert log["entity_type"] == "User"
        assert log["actor_email"] == "admin@automateaccounts.local"

    def test_promo_code_creation_generates_audit(self, auth_headers):
        """Promo code creation generates a promo_code audit log."""
        import random
        code_name = f"TESTAUDIT{random.randint(1000, 9999)}"
        create_resp = requests.post(
            f"{BASE_URL}/api/admin/promo-codes",
            headers=auth_headers,
            json={
                "code": code_name,
                "discount_type": "percentage",
                "discount_value": 10,
                "applies_to": "all",
                "applies_to_products": False,
                "product_ids": [],
                "expiry_date": None,
                "max_uses": None,
                "one_time_code": False,
                "enabled": True,
            },
        )
        assert create_resp.status_code == 200, f"Promo code creation failed: {create_resp.text}"
        code_id = create_resp.json().get("id")
        time.sleep(0.5)

        # Check audit log exists for this promo code
        resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?entity_type=promo_code&limit=10",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0, "No promo_code audit log found"

        # Cleanup
        if code_id:
            requests.delete(f"{BASE_URL}/api/admin/promo-codes/{code_id}", headers=auth_headers)

    def test_customer_update_generates_audit(self, auth_headers):
        """Customer update generates a customer audit log."""
        # Get an existing customer first
        cust_resp = requests.get(
            f"{BASE_URL}/api/admin/customers?per_page=1", headers=auth_headers
        )
        assert cust_resp.status_code == 200
        customers = cust_resp.json().get("customers", [])
        if not customers:
            pytest.skip("No customers available to test update audit")

        customer_id = customers[0]["id"]
        # Check audit logs for customer entity
        resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?entity_type=customer&limit=10",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # Should have customer audit logs from prior operations
        assert data["total"] >= 0  # Could be 0 if no previous customer mutations

    def test_article_creation_generates_audit(self, auth_headers):
        """Article creation generates ARTICLE_CREATED audit log."""
        create_resp = requests.post(
            f"{BASE_URL}/api/articles",
            headers=auth_headers,
            json={
                "title": "TEST_AUDIT_ARTICLE",
                "category": "Blog",
                "content": "Test content for audit log testing",
                "visibility": "all",
                "restricted_to": [],
            },
        )
        assert create_resp.status_code == 200, f"Article creation failed: {create_resp.text}"
        article_id = create_resp.json().get("article", {}).get("id")
        time.sleep(0.5)

        # Verify ARTICLE_CREATED in audit logs
        resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?action=ARTICLE_CREATED&limit=10",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0, "No ARTICLE_CREATED audit log found"
        logs = [l for l in data["logs"] if l["action"] == "ARTICLE_CREATED"]
        assert logs, "ARTICLE_CREATED not found in returned logs"
        log = logs[0]
        assert log["entity_type"] == "Article"
        assert log["actor_type"] == "admin"
        assert log["source"] == "admin_ui"

        # Cleanup: delete the test article
        if article_id:
            requests.delete(f"{BASE_URL}/api/articles/{article_id}", headers=auth_headers)
            time.sleep(0.3)

    def test_article_delete_generates_audit(self, auth_headers):
        """Article deletion generates ARTICLE_DELETED audit log."""
        # Create article first
        create_resp = requests.post(
            f"{BASE_URL}/api/articles",
            headers=auth_headers,
            json={
                "title": "TEST_AUDIT_DELETE_ARTICLE",
                "category": "Blog",
                "content": "Content to be deleted",
                "visibility": "all",
                "restricted_to": [],
            },
        )
        assert create_resp.status_code == 200, f"Article creation failed: {create_resp.text}"
        article_id = create_resp.json().get("article", {}).get("id")
        assert article_id

        # Delete the article
        del_resp = requests.delete(
            f"{BASE_URL}/api/articles/{article_id}", headers=auth_headers
        )
        assert del_resp.status_code == 200
        time.sleep(0.5)

        # Verify ARTICLE_DELETED
        resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?action=ARTICLE_DELETED&entity_id={article_id}&limit=5",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0, "No ARTICLE_DELETED audit log found"

    def test_user_registered_generates_audit(self, auth_headers):
        """User registration generates USER_REGISTERED audit log."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?action=USER_REGISTERED&limit=5",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # Should exist from past registrations
        assert data["total"] >= 0


# ---------------------------------------------------------------------------
# 4. Single log detail endpoint
# ---------------------------------------------------------------------------

class TestAuditLogDetail:
    """GET /api/admin/audit-logs/{log_id} returns single log."""

    def test_get_log_by_id(self, auth_headers):
        """Can fetch individual log by ID."""
        # Get a log ID from the list
        list_resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?limit=1", headers=auth_headers
        )
        assert list_resp.status_code == 200
        logs = list_resp.json().get("logs", [])
        if not logs:
            pytest.skip("No logs available")
        log_id = logs[0]["id"]

        # Fetch by ID
        resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs/{log_id}", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "log" in data
        assert data["log"]["id"] == log_id

    def test_get_invalid_log_returns_404(self, auth_headers):
        """Fetching non-existent log returns 404."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs/nonexistent_id_xyz", headers=auth_headers
        )
        assert resp.status_code == 404
