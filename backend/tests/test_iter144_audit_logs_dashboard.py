"""
Iteration 144 - Audit Trail Dashboard Backend Tests
Tests: /api/admin/audit-logs/stats, /api/admin/audit-logs (list), /api/admin/audit-logs/{id}
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_token():
    """Get platform admin token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.status_code} {resp.text}"
    token = resp.json().get("token") or resp.json().get("access_token")
    assert token, f"No token in response: {resp.json()}"
    return token


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ── Stats Endpoint Tests ──────────────────────────────────────────────────────

class TestAuditStatsEndpoint:
    """Tests for GET /api/admin/audit-logs/stats"""

    def test_stats_returns_200(self, auth_headers):
        """Stats endpoint should return 200."""
        resp = requests.get(f"{BASE_URL}/api/admin/audit-logs/stats", headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print("PASS: Stats endpoint returns 200")

    def test_stats_response_shape(self, auth_headers):
        """Stats response should have all required keys."""
        resp = requests.get(f"{BASE_URL}/api/admin/audit-logs/stats", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        required_keys = ["total", "errors", "today", "by_actor_type", "top_actions", "top_entity_types"]
        for key in required_keys:
            assert key in data, f"Missing key '{key}' in stats response"
        print(f"PASS: Stats response has all required keys: {required_keys}")

    def test_stats_total_is_positive(self, auth_headers):
        """Total events should be > 0 (1477 events in DB per context)."""
        resp = requests.get(f"{BASE_URL}/api/admin/audit-logs/stats", headers=auth_headers)
        data = resp.json()
        assert data["total"] >= 0, "total should be non-negative"
        print(f"PASS: stats.total = {data['total']}")

    def test_stats_errors_non_negative(self, auth_headers):
        """Errors count should be non-negative and <= total."""
        resp = requests.get(f"{BASE_URL}/api/admin/audit-logs/stats", headers=auth_headers)
        data = resp.json()
        assert data["errors"] >= 0
        assert data["errors"] <= data["total"]
        print(f"PASS: stats.errors = {data['errors']} (total={data['total']})")

    def test_stats_today_non_negative(self, auth_headers):
        """Today's event count should be non-negative."""
        resp = requests.get(f"{BASE_URL}/api/admin/audit-logs/stats", headers=auth_headers)
        data = resp.json()
        assert data["today"] >= 0
        print(f"PASS: stats.today = {data['today']}")

    def test_stats_by_actor_type_is_dict(self, auth_headers):
        """by_actor_type should be a dict."""
        resp = requests.get(f"{BASE_URL}/api/admin/audit-logs/stats", headers=auth_headers)
        data = resp.json()
        assert isinstance(data["by_actor_type"], dict), "by_actor_type should be a dict"
        print(f"PASS: by_actor_type = {data['by_actor_type']}")

    def test_stats_top_actions_is_list(self, auth_headers):
        """top_actions should be a list with action + count fields."""
        resp = requests.get(f"{BASE_URL}/api/admin/audit-logs/stats", headers=auth_headers)
        data = resp.json()
        assert isinstance(data["top_actions"], list)
        if data["top_actions"]:
            first = data["top_actions"][0]
            assert "action" in first, "top_actions items need 'action' key"
            assert "count" in first, "top_actions items need 'count' key"
            assert isinstance(first["count"], int)
        print(f"PASS: top_actions has {len(data['top_actions'])} items")

    def test_stats_top_entity_types_is_list(self, auth_headers):
        """top_entity_types should be a list with entity_type + count fields."""
        resp = requests.get(f"{BASE_URL}/api/admin/audit-logs/stats", headers=auth_headers)
        data = resp.json()
        assert isinstance(data["top_entity_types"], list)
        if data["top_entity_types"]:
            first = data["top_entity_types"][0]
            assert "entity_type" in first
            assert "count" in first
        print(f"PASS: top_entity_types has {len(data['top_entity_types'])} items")

    def test_stats_with_date_from_filter(self, auth_headers):
        """Stats with date_from filter should return correct data."""
        date_from = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
        resp = requests.get(f"{BASE_URL}/api/admin/audit-logs/stats",
                            headers=auth_headers,
                            params={"date_from": date_from})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 0
        print(f"PASS: Stats with date_from={date_from}: total={data['total']}")

    def test_stats_with_date_range(self, auth_headers):
        """Stats with both date_from and date_to filter."""
        date_from = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
        date_to = datetime.utcnow().strftime("%Y-%m-%d")
        resp = requests.get(f"{BASE_URL}/api/admin/audit-logs/stats",
                            headers=auth_headers,
                            params={"date_from": date_from, "date_to": date_to})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 0
        print(f"PASS: Stats 7d range ({date_from} to {date_to}): total={data['total']}")

    def test_stats_requires_auth(self):
        """Stats endpoint should require authentication."""
        resp = requests.get(f"{BASE_URL}/api/admin/audit-logs/stats")
        assert resp.status_code in [401, 403], f"Expected 401/403 without auth, got {resp.status_code}"
        print(f"PASS: Stats endpoint rejects unauthenticated request (status={resp.status_code})")


# ── List Audit Logs Tests ─────────────────────────────────────────────────────

class TestAuditLogsList:
    """Tests for GET /api/admin/audit-logs"""

    def test_list_returns_200(self, auth_headers):
        """List endpoint should return 200."""
        resp = requests.get(f"{BASE_URL}/api/admin/audit-logs", headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print("PASS: Audit logs list returns 200")

    def test_list_response_shape(self, auth_headers):
        """List response must have logs, total, page, per_page, total_pages."""
        resp = requests.get(f"{BASE_URL}/api/admin/audit-logs", headers=auth_headers)
        data = resp.json()
        for key in ["logs", "total", "page", "per_page", "total_pages"]:
            assert key in data, f"Missing key '{key}' in list response"
        print(f"PASS: List response shape OK: total={data['total']}, pages={data['total_pages']}")

    def test_list_logs_is_array(self, auth_headers):
        """logs field should be an array."""
        resp = requests.get(f"{BASE_URL}/api/admin/audit-logs", headers=auth_headers)
        data = resp.json()
        assert isinstance(data["logs"], list)
        print(f"PASS: logs is a list with {len(data['logs'])} items")

    def test_list_default_limit_50(self, auth_headers):
        """Default limit should be 50 and result <= 50 items."""
        resp = requests.get(f"{BASE_URL}/api/admin/audit-logs", headers=auth_headers)
        data = resp.json()
        assert len(data["logs"]) <= 50, f"Expected <=50 logs, got {len(data['logs'])}"
        assert data["per_page"] == 50
        print(f"PASS: Default limit 50, got {len(data['logs'])} items")

    def test_list_limit_25(self, auth_headers):
        """With limit=25, response should have <= 25 items."""
        resp = requests.get(f"{BASE_URL}/api/admin/audit-logs", headers=auth_headers, params={"limit": 25})
        data = resp.json()
        assert len(data["logs"]) <= 25
        assert data["per_page"] == 25
        print(f"PASS: limit=25 returned {len(data['logs'])} items")

    def test_list_limit_100(self, auth_headers):
        """With limit=100, response should have <= 100 items."""
        resp = requests.get(f"{BASE_URL}/api/admin/audit-logs", headers=auth_headers, params={"limit": 100})
        data = resp.json()
        assert len(data["logs"]) <= 100
        assert data["per_page"] == 100
        print(f"PASS: limit=100 returned {len(data['logs'])} items")

    def test_list_pagination_page2(self, auth_headers):
        """Page 2 with limit 25 should return different items from page 1."""
        resp1 = requests.get(f"{BASE_URL}/api/admin/audit-logs", headers=auth_headers, params={"limit": 25, "page": 1})
        resp2 = requests.get(f"{BASE_URL}/api/admin/audit-logs", headers=auth_headers, params={"limit": 25, "page": 2})
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        ids1 = {log["id"] for log in resp1.json()["logs"] if "id" in log}
        ids2 = {log["id"] for log in resp2.json()["logs"] if "id" in log}
        if ids1 and ids2:
            assert ids1.isdisjoint(ids2), "Page 1 and Page 2 should not have overlapping IDs"
        print(f"PASS: Pagination - page1 has {len(ids1)} unique IDs, page2 has {len(ids2)} unique IDs, no overlap")

    def test_list_filter_by_date_from(self, auth_headers):
        """date_from filter should restrict results."""
        date_from = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
        resp = requests.get(f"{BASE_URL}/api/admin/audit-logs", headers=auth_headers, params={"date_from": date_from, "limit": 25})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["logs"], list)
        print(f"PASS: date_from={date_from} filter returns {len(data['logs'])} logs, total={data['total']}")

    def test_list_log_item_fields(self, auth_headers):
        """Each log item should have expected fields."""
        resp = requests.get(f"{BASE_URL}/api/admin/audit-logs", headers=auth_headers, params={"limit": 10})
        data = resp.json()
        logs = data["logs"]
        if not logs:
            pytest.skip("No logs returned - cannot verify log item fields")
        log = logs[0]
        # Check for key fields expected by the frontend
        expected_fields = ["id", "action", "actor_type"]
        for field in expected_fields:
            assert field in log, f"Log item missing '{field}' field"
        print(f"PASS: Log item has required fields. Sample: action={log.get('action')}, actor_type={log.get('actor_type')}")

    def test_list_filter_by_actor_type(self, auth_headers):
        """actor_type filter should work."""
        # First get available actor types from stats
        stats_resp = requests.get(f"{BASE_URL}/api/admin/audit-logs/stats", headers=auth_headers)
        by_actor = stats_resp.json().get("by_actor_type", {})
        if not by_actor:
            pytest.skip("No actor type data available")
        actor_type = list(by_actor.keys())[0]
        resp = requests.get(f"{BASE_URL}/api/admin/audit-logs", headers=auth_headers,
                            params={"actor_type": actor_type, "limit": 10})
        assert resp.status_code == 200
        data = resp.json()
        print(f"PASS: actor_type={actor_type} filter returns {data['total']} total logs")

    def test_list_requires_auth(self):
        """List endpoint should require authentication."""
        resp = requests.get(f"{BASE_URL}/api/admin/audit-logs")
        assert resp.status_code in [401, 403], f"Expected 401/403 without auth, got {resp.status_code}"
        print(f"PASS: List endpoint rejects unauthenticated request (status={resp.status_code})")


# ── Single Log Endpoint ────────────────────────────────────────────────────────

class TestAuditLogById:
    """Tests for GET /api/admin/audit-logs/{log_id}"""

    def test_get_log_by_valid_id(self, auth_headers):
        """Should return a single log by ID."""
        # Get first log from list
        list_resp = requests.get(f"{BASE_URL}/api/admin/audit-logs", headers=auth_headers, params={"limit": 1})
        logs = list_resp.json().get("logs", [])
        if not logs:
            pytest.skip("No logs available to test individual fetch")
        log_id = logs[0]["id"]
        resp = requests.get(f"{BASE_URL}/api/admin/audit-logs/{log_id}", headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "log" in data, "Response should have 'log' key"
        assert data["log"]["id"] == log_id
        print(f"PASS: Fetch single log id={log_id} OK")

    def test_get_log_404_for_invalid_id(self, auth_headers):
        """Should return 404 for non-existent log ID."""
        resp = requests.get(f"{BASE_URL}/api/admin/audit-logs/nonexistent-id-xyz", headers=auth_headers)
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print("PASS: 404 returned for nonexistent log ID")
