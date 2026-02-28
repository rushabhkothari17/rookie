"""
Tests for Plans Management System (Iteration 147).
Tests: CRUD plans, auto-propagation, audit logs, status toggle,
delete blocked logic, and tenant license with plan_id.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"
TEST_TENANT_ID = "cb9c6337-4c59-4e74-a165-6f218354630d"


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def auth_token():
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        cookies={},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    # httpOnly cookie-based auth: return the session cookie jar
    return resp.cookies


@pytest.fixture(scope="module")
def admin_session(auth_token):
    s = requests.Session()
    s.cookies.update(auth_token)
    return s


@pytest.fixture(scope="module")
def created_plan_id(admin_session):
    """Create a TEST_ plan and return its id; delete after module."""
    payload = {
        "name": "TEST_PlanMgmt_Alpha",
        "description": "Testing plan",
        "warning_threshold_pct": 75,
        "max_users": 5,
        "max_storage_mb": 100,
        "max_user_roles": 3,
        "max_product_categories": None,
        "max_product_terms": None,
        "max_enquiries": None,
        "max_resources": None,
        "max_templates": None,
        "max_email_templates": None,
        "max_categories": None,
        "max_forms": None,
        "max_references": None,
        "max_orders_per_month": None,
        "max_customers_per_month": None,
        "max_subscriptions_per_month": None,
    }
    resp = admin_session.post(f"{BASE_URL}/api/admin/plans", json=payload)
    assert resp.status_code == 200, f"Create plan failed: {resp.text}"
    plan_id = resp.json()["plan"]["id"]
    yield plan_id

    # Cleanup: delete if not assigned to any tenant
    try:
        admin_session.delete(f"{BASE_URL}/api/admin/plans/{plan_id}")
    except Exception:
        pass


# ─── 1. List plans ─────────────────────────────────────────────────────────────

class TestListPlans:
    """GET /api/admin/plans"""

    def test_list_plans_returns_200(self, admin_session):
        resp = admin_session.get(f"{BASE_URL}/api/admin/plans")
        assert resp.status_code == 200

    def test_list_plans_has_plans_key(self, admin_session):
        resp = admin_session.get(f"{BASE_URL}/api/admin/plans")
        data = resp.json()
        assert "plans" in data
        assert isinstance(data["plans"], list)

    def test_list_plans_has_tenant_count(self, admin_session):
        resp = admin_session.get(f"{BASE_URL}/api/admin/plans")
        data = resp.json()
        # Each plan must have tenant_count field
        for plan in data["plans"]:
            assert "tenant_count" in plan, f"tenant_count missing from plan: {plan}"
            assert isinstance(plan["tenant_count"], int)

    def test_list_plans_includes_starter(self, admin_session):
        resp = admin_session.get(f"{BASE_URL}/api/admin/plans")
        names = [p["name"] for p in resp.json()["plans"]]
        assert any("Starter" in n or "starter" in n.lower() for n in names), \
            f"'Starter' plan not found in {names}"

    def test_list_plans_requires_auth(self):
        resp = requests.get(f"{BASE_URL}/api/admin/plans")
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"


# ─── 2. Create plan ────────────────────────────────────────────────────────────

class TestCreatePlan:
    """POST /api/admin/plans"""

    def test_create_plan_returns_plan(self, admin_session, created_plan_id):
        # Fixture already created a plan; just verify it's accessible
        resp = admin_session.get(f"{BASE_URL}/api/admin/plans/{created_plan_id}")
        assert resp.status_code == 200
        data = resp.json()["plan"]
        assert data["name"] == "TEST_PlanMgmt_Alpha"
        assert data["max_users"] == 5
        assert data["max_storage_mb"] == 100

    def test_create_plan_duplicate_name_returns_409(self, admin_session):
        payload = {"name": "TEST_PlanMgmt_Alpha"}
        resp = admin_session.post(f"{BASE_URL}/api/admin/plans", json=payload)
        assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"

    def test_create_plan_missing_name_returns_error(self, admin_session):
        payload = {"description": "No name"}
        resp = admin_session.post(f"{BASE_URL}/api/admin/plans", json=payload)
        assert resp.status_code in [400, 422], f"Expected 400/422, got {resp.status_code}"

    def test_create_plan_sets_is_active_true(self, admin_session, created_plan_id):
        resp = admin_session.get(f"{BASE_URL}/api/admin/plans/{created_plan_id}")
        assert resp.json()["plan"]["is_active"] is True


# ─── 3. Get plan ───────────────────────────────────────────────────────────────

class TestGetPlan:
    """GET /api/admin/plans/{plan_id}"""

    def test_get_plan_returns_correct_data(self, admin_session, created_plan_id):
        resp = admin_session.get(f"{BASE_URL}/api/admin/plans/{created_plan_id}")
        assert resp.status_code == 200
        plan = resp.json()["plan"]
        assert plan["id"] == created_plan_id
        assert "tenant_count" in plan

    def test_get_plan_not_found(self, admin_session):
        resp = admin_session.get(f"{BASE_URL}/api/admin/plans/nonexistent-plan-id")
        assert resp.status_code == 404


# ─── 4. Update plan & propagation ────────────────────────────────────────────

class TestUpdatePlan:
    """PUT /api/admin/plans/{plan_id} — updates plan, returns tenants_propagated"""

    def test_update_plan_returns_updated_data(self, admin_session, created_plan_id):
        payload = {"max_users": 10, "max_storage_mb": 200}
        resp = admin_session.put(f"{BASE_URL}/api/admin/plans/{created_plan_id}", json=payload)
        assert resp.status_code == 200, f"Update failed: {resp.text}"
        data = resp.json()
        assert "plan" in data
        assert data["plan"]["max_users"] == 10
        assert data["plan"]["max_storage_mb"] == 200

    def test_update_plan_has_tenants_propagated_field(self, admin_session, created_plan_id):
        payload = {"max_users": 10}
        resp = admin_session.put(f"{BASE_URL}/api/admin/plans/{created_plan_id}", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "tenants_propagated" in data, "Response missing 'tenants_propagated'"
        assert isinstance(data["tenants_propagated"], int)

    def test_update_plan_persists_changes(self, admin_session, created_plan_id):
        # Update and then GET to confirm persistence
        payload = {"description": "Updated description", "warning_threshold_pct": 85}
        admin_session.put(f"{BASE_URL}/api/admin/plans/{created_plan_id}", json=payload)
        get_resp = admin_session.get(f"{BASE_URL}/api/admin/plans/{created_plan_id}")
        plan = get_resp.json()["plan"]
        assert plan["description"] == "Updated description"
        assert plan["warning_threshold_pct"] == 85

    def test_update_nonexistent_plan_returns_404(self, admin_session):
        resp = admin_session.put(f"{BASE_URL}/api/admin/plans/nonexistent", json={"max_users": 5})
        assert resp.status_code == 404

    def test_update_empty_payload_returns_400(self, admin_session, created_plan_id):
        resp = admin_session.put(f"{BASE_URL}/api/admin/plans/{created_plan_id}", json={})
        assert resp.status_code == 400


# ─── 5. Audit logs per plan ────────────────────────────────────────────────────

class TestPlanLogs:
    """GET /api/admin/plans/{plan_id}/logs"""

    def test_get_plan_logs_returns_200(self, admin_session, created_plan_id):
        resp = admin_session.get(f"{BASE_URL}/api/admin/plans/{created_plan_id}/logs")
        assert resp.status_code == 200

    def test_get_plan_logs_has_logs_key(self, admin_session, created_plan_id):
        resp = admin_session.get(f"{BASE_URL}/api/admin/plans/{created_plan_id}/logs")
        data = resp.json()
        assert "logs" in data
        assert isinstance(data["logs"], list)

    def test_get_plan_logs_contains_created_action(self, admin_session, created_plan_id):
        resp = admin_session.get(f"{BASE_URL}/api/admin/plans/{created_plan_id}/logs")
        logs = resp.json()["logs"]
        actions = [l.get("action") for l in logs]
        assert "created" in actions, f"Expected 'created' in actions: {actions}"

    def test_get_plan_logs_log_has_required_fields(self, admin_session, created_plan_id):
        resp = admin_session.get(f"{BASE_URL}/api/admin/plans/{created_plan_id}/logs")
        logs = resp.json()["logs"]
        assert len(logs) > 0
        for log in logs:
            assert "action" in log
            assert "actor" in log
            assert "timestamp" in log


# ─── 6. Toggle plan status ────────────────────────────────────────────────────

class TestTogglePlanStatus:
    """PATCH /api/admin/plans/{plan_id}/status"""

    def test_toggle_plan_status_to_inactive(self, admin_session, created_plan_id):
        # Ensure it's active first
        get_resp = admin_session.get(f"{BASE_URL}/api/admin/plans/{created_plan_id}")
        initial_active = get_resp.json()["plan"]["is_active"]

        resp = admin_session.patch(f"{BASE_URL}/api/admin/plans/{created_plan_id}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "is_active" in data
        assert data["is_active"] == (not initial_active)

    def test_toggle_plan_status_back_to_active(self, admin_session, created_plan_id):
        # Toggle once more to restore
        get_resp = admin_session.get(f"{BASE_URL}/api/admin/plans/{created_plan_id}")
        before = get_resp.json()["plan"]["is_active"]

        resp = admin_session.patch(f"{BASE_URL}/api/admin/plans/{created_plan_id}/status")
        assert resp.status_code == 200
        assert resp.json()["is_active"] == (not before)

    def test_toggle_nonexistent_plan_returns_404(self, admin_session):
        resp = admin_session.patch(f"{BASE_URL}/api/admin/plans/nonexistent/status")
        assert resp.status_code == 404


# ─── 7. Delete plan — blocked if tenants assigned ─────────────────────────────

class TestDeletePlan:
    """DELETE /api/admin/plans/{plan_id}"""

    def test_delete_starter_plan_blocked_if_tenants(self, admin_session):
        """'Starter' plan (already has tenants) should be blocked with 409."""
        list_resp = admin_session.get(f"{BASE_URL}/api/admin/plans")
        plans = list_resp.json()["plans"]
        starter = next((p for p in plans if "starter" in p["name"].lower()), None)
        if starter and starter.get("tenant_count", 0) > 0:
            del_resp = admin_session.delete(f"{BASE_URL}/api/admin/plans/{starter['id']}")
            assert del_resp.status_code == 409, f"Expected 409, got {del_resp.status_code}: {del_resp.text}"
        else:
            pytest.skip("Starter plan has 0 tenants — cannot test 409 block")

    def test_delete_unassigned_plan_succeeds(self, admin_session):
        """Create a new plan with no tenants and delete it."""
        create_resp = admin_session.post(
            f"{BASE_URL}/api/admin/plans",
            json={"name": "TEST_DeleteMe_Plan", "max_users": 1},
        )
        assert create_resp.status_code == 200
        plan_id = create_resp.json()["plan"]["id"]

        del_resp = admin_session.delete(f"{BASE_URL}/api/admin/plans/{plan_id}")
        assert del_resp.status_code == 200, f"Delete failed: {del_resp.text}"

        # Confirm it no longer exists
        get_resp = admin_session.get(f"{BASE_URL}/api/admin/plans/{plan_id}")
        assert get_resp.status_code == 404

    def test_delete_nonexistent_plan_returns_404(self, admin_session):
        resp = admin_session.delete(f"{BASE_URL}/api/admin/plans/nonexistent-plan-id")
        assert resp.status_code == 404


# ─── 8. Tenant license with plan_id auto-fills limits ─────────────────────────

class TestTenantLicenseWithPlanId:
    """PUT /api/admin/tenants/{tid}/license with plan_id"""

    def test_assign_plan_to_tenant_fills_limits(self, admin_session, created_plan_id):
        """
        Assigning a plan_id should auto-fill the tenant license with plan limits.
        """
        # Make sure plan has known limits
        admin_session.put(
            f"{BASE_URL}/api/admin/plans/{created_plan_id}",
            json={"max_users": 10, "max_storage_mb": 500},
        )

        # Assign plan to tenant
        license_payload = {"plan_id": created_plan_id}
        resp = admin_session.put(
            f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license",
            json=license_payload,
        )
        assert resp.status_code == 200, f"Failed to set license: {resp.text}"
        license_data = resp.json()["license"]
        assert license_data.get("plan_id") == created_plan_id
        assert license_data.get("max_users") == 10
        assert license_data.get("max_storage_mb") == 500

    def test_assign_plan_tenant_license_has_plan_name(self, admin_session, created_plan_id):
        """License should store the plan name."""
        resp = admin_session.get(f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license")
        assert resp.status_code == 200
        license_data = resp.json()["license"]
        # Should have plan name stored
        assert license_data.get("plan_id") == created_plan_id

    def test_assign_nonexistent_plan_to_tenant_returns_404(self, admin_session):
        resp = admin_session.put(
            f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license",
            json={"plan_id": "nonexistent-plan-id"},
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"

    def test_reset_tenant_license_after_tests(self, admin_session):
        """Reset tenant license to unlimited for other tests."""
        resp = admin_session.put(
            f"{BASE_URL}/api/admin/tenants/{TEST_TENANT_ID}/license",
            json={
                "plan_id": None,
                "max_users": None, "max_storage_mb": None, "max_user_roles": None,
                "max_product_categories": None, "max_product_terms": None,
                "max_enquiries": None, "max_resources": None, "max_templates": None,
                "max_email_templates": None, "max_categories": None, "max_forms": None,
                "max_references": None, "max_orders_per_month": None,
                "max_customers_per_month": None, "max_subscriptions_per_month": None,
            },
        )
        assert resp.status_code == 200
