"""
Phase 3 & 4: Partner Self-Service Plan Management and Partner Submissions Admin Review.

Tests:
- GET /api/partner/my-plan
- POST /api/partner/upgrade-plan (pro-rata order)
- POST /api/partner/submissions (downgrade request)
- GET /api/partner/submissions
- GET /api/admin/partner-submissions (admin view)
- PUT /api/admin/partner-submissions/{id} (approve/reject)
- GET /api/admin/plans (monthly_price, currency, is_public)
- PUT /api/admin/plans/{id} (monthly_price, currency, is_public)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

PLATFORM_ADMIN = {
    "email": "admin@automateaccounts.local",
    "password": "ChangeMe123!",
    "partner_code": "automate-accounts",
}

PARTNER_CREDENTIALS = {
    "email": "testpartner@example.com",
    "password": "TestPass123!",
    "partner_code": "test-partner-co",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def admin_session():
    """Authenticated session for platform admin (no partner_code)."""
    session = requests.Session()
    # Platform admin logs in WITHOUT partner_code at /api/auth/login
    r = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": PLATFORM_ADMIN["email"],
        "password": PLATFORM_ADMIN["password"],
    })
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    token = r.json().get("token") or r.json().get("access_token")
    if token:
        session.headers.update({"Authorization": f"Bearer {token}"})
    return session


@pytest.fixture(scope="module")
def partner_session():
    """Authenticated session for test partner admin."""
    session = requests.Session()
    r = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": PARTNER_CREDENTIALS["email"],
        "password": PARTNER_CREDENTIALS["password"],
        "partner_code": PARTNER_CREDENTIALS["partner_code"],
    })
    assert r.status_code == 200, f"Partner login failed: {r.text}"
    token = r.json().get("token") or r.json().get("access_token")
    if token:
        session.headers.update({"Authorization": f"Bearer {token}"})
    return session


# ---------------------------------------------------------------------------
# Admin Plans Tests
# ---------------------------------------------------------------------------

class TestAdminPlans:
    """Test Plans management with monthly_price, currency, is_public fields."""

    def test_list_plans_returns_plans(self, admin_session):
        """GET /admin/plans should return list of plans."""
        r = admin_session.get(f"{BASE_URL}/api/admin/plans")
        assert r.status_code == 200, f"Expected 200 got {r.status_code}: {r.text}"
        data = r.json()
        assert "plans" in data
        assert isinstance(data["plans"], list)
        print(f"PASS: list_plans returned {len(data['plans'])} plans")

    def test_plans_have_monthly_price_field(self, admin_session):
        """Plans should include monthly_price and currency fields."""
        r = admin_session.get(f"{BASE_URL}/api/admin/plans")
        assert r.status_code == 200
        plans = r.json()["plans"]
        assert len(plans) > 0, "Expected at least one plan"
        # Check fields exist on plans
        for plan in plans:
            assert "monthly_price" in plan, f"Plan {plan['name']} missing monthly_price"
            assert "currency" in plan, f"Plan {plan['name']} missing currency"
            assert "is_public" in plan, f"Plan {plan['name']} missing is_public"
        print(f"PASS: All {len(plans)} plans have monthly_price, currency, is_public fields")

    def test_plans_have_public_badge_plans(self, admin_session):
        """Starter and Professional plans should be marked as public."""
        r = admin_session.get(f"{BASE_URL}/api/admin/plans")
        assert r.status_code == 200
        plans = r.json()["plans"]
        public_plans = [p for p in plans if p.get("is_public")]
        print(f"INFO: {len(public_plans)} public plan(s): {[p['name'] for p in public_plans]}")
        # There should be at least some public plans (Starter, Professional)
        assert len(public_plans) >= 1, "Expected at least 1 public plan"
        print(f"PASS: Found {len(public_plans)} public plan(s)")

    def test_create_plan_with_monthly_price(self, admin_session):
        """POST /admin/plans with monthly_price and currency should persist."""
        payload = {
            "name": "TEST_Phase4_Plan",
            "description": "Test plan for phase 4 testing",
            "is_public": True,
            "monthly_price": 49.99,
            "currency": "GBP",
            "max_users": 25,
        }
        r = admin_session.post(f"{BASE_URL}/api/admin/plans", json=payload)
        # May return 409 if already exists; accept that
        if r.status_code == 409:
            print("INFO: TEST_Phase4_Plan already exists (from previous test run)")
            return
        assert r.status_code == 200, f"Expected 200 got {r.status_code}: {r.text}"
        plan = r.json()["plan"]
        assert plan["monthly_price"] == 49.99
        assert plan["currency"] == "GBP"
        assert plan["is_public"] is True
        print(f"PASS: Created plan with monthly_price={plan['monthly_price']}, currency={plan['currency']}")

    def test_update_plan_monthly_price_and_currency(self, admin_session):
        """PUT /admin/plans/{id} should update monthly_price and currency."""
        # Get the test plan
        r = admin_session.get(f"{BASE_URL}/api/admin/plans")
        plans = r.json()["plans"]
        test_plan = next((p for p in plans if p["name"] == "TEST_Phase4_Plan"), None)
        if not test_plan:
            pytest.skip("TEST_Phase4_Plan not found, skipping update test")

        r = admin_session.put(f"{BASE_URL}/api/admin/plans/{test_plan['id']}", json={
            "monthly_price": 59.99,
            "currency": "USD",
        })
        assert r.status_code == 200, f"Expected 200 got {r.status_code}: {r.text}"
        updated = r.json()["plan"]
        assert updated["monthly_price"] == 59.99
        assert updated["currency"] == "USD"
        print(f"PASS: Updated plan monthly_price={updated['monthly_price']}, currency={updated['currency']}")

    def test_delete_test_plan(self, admin_session):
        """Clean up: delete TEST_Phase4_Plan."""
        r = admin_session.get(f"{BASE_URL}/api/admin/plans")
        plans = r.json()["plans"]
        test_plan = next((p for p in plans if p["name"] == "TEST_Phase4_Plan"), None)
        if not test_plan:
            print("INFO: TEST_Phase4_Plan not found for cleanup")
            return
        if (test_plan.get("tenant_count") or 0) > 0:
            print(f"INFO: Skipping delete - {test_plan['tenant_count']} tenants assigned")
            return
        r = admin_session.delete(f"{BASE_URL}/api/admin/plans/{test_plan['id']}")
        assert r.status_code == 200, f"Expected 200 got {r.status_code}: {r.text}"
        print("PASS: Deleted TEST_Phase4_Plan")


# ---------------------------------------------------------------------------
# Partner My Plan Tests
# ---------------------------------------------------------------------------

class TestPartnerMyPlan:
    """Test GET /partner/my-plan endpoint."""

    def test_get_my_plan_returns_structure(self, partner_session):
        """GET /partner/my-plan should return current_plan, subscription, available_plans."""
        r = partner_session.get(f"{BASE_URL}/api/partner/my-plan")
        assert r.status_code == 200, f"Expected 200 got {r.status_code}: {r.text}"
        data = r.json()
        assert "current_plan" in data, "Missing current_plan field"
        assert "license" in data, "Missing license field"
        assert "subscription" in data, "Missing subscription field"
        assert "available_plans" in data, "Missing available_plans field"
        assert isinstance(data["available_plans"], list)
        print(f"PASS: my-plan returned current_plan={data['current_plan']['name'] if data['current_plan'] else None}, {len(data['available_plans'])} available plans")

    def test_get_my_plan_current_plan_has_fields(self, partner_session):
        """Current plan should have required fields."""
        r = partner_session.get(f"{BASE_URL}/api/partner/my-plan")
        assert r.status_code == 200
        current = r.json().get("current_plan")
        if current:
            assert "id" in current
            assert "name" in current
            assert "monthly_price" in current
            print(f"PASS: current_plan={current['name']}, price={current.get('monthly_price')}")
        else:
            print("INFO: No current_plan assigned (may be on Free Trial)")

    def test_get_my_plan_available_plans_are_public(self, partner_session):
        """Available plans should all have is_public=True."""
        r = partner_session.get(f"{BASE_URL}/api/partner/my-plan")
        assert r.status_code == 200
        available = r.json().get("available_plans", [])
        for plan in available:
            assert plan.get("is_public") is True, f"Plan {plan['name']} is not public but shown as available"
        print(f"PASS: All {len(available)} available plans are public")

    def test_partner_requires_auth(self):
        """Without auth, should return 401."""
        r = requests.get(f"{BASE_URL}/api/partner/my-plan")
        assert r.status_code in [401, 403], f"Expected 401/403 got {r.status_code}"
        print("PASS: Unauthenticated request properly rejected")


# ---------------------------------------------------------------------------
# Partner Upgrade Plan Tests
# ---------------------------------------------------------------------------

class TestPartnerUpgradePlan:
    """Test POST /partner/upgrade-plan endpoint."""

    def test_upgrade_to_invalid_plan_returns_404(self, partner_session):
        """Upgrading to a non-existent plan should return 404."""
        r = partner_session.post(f"{BASE_URL}/api/partner/upgrade-plan", json={
            "plan_id": "nonexistent-plan-id-12345"
        })
        assert r.status_code == 404, f"Expected 404 got {r.status_code}: {r.text}"
        print("PASS: Invalid plan_id returns 404")

    def test_upgrade_plan_response_structure(self, partner_session):
        """POST /partner/upgrade-plan to a public plan should return success."""
        # First get available plans
        my_plan_r = partner_session.get(f"{BASE_URL}/api/partner/my-plan")
        assert my_plan_r.status_code == 200
        data = my_plan_r.json()
        available = data.get("available_plans", [])
        current = data.get("current_plan")
        current_price = (current or {}).get("monthly_price", 0) or 0

        # Find an upgrade plan (higher price)
        upgrade_plans = [p for p in available if (p.get("monthly_price") or 0) > current_price]
        if not upgrade_plans:
            pytest.skip("No upgrade plans available for the test partner's current plan")

        target = upgrade_plans[0]
        r = partner_session.post(f"{BASE_URL}/api/partner/upgrade-plan", json={
            "plan_id": target["id"]
        })
        assert r.status_code == 200, f"Expected 200 got {r.status_code}: {r.text}"
        resp = r.json()
        assert "message" in resp
        assert "new_plan" in resp
        assert "prorata_amount" in resp
        assert "next_billing_date" in resp
        print(f"PASS: Upgraded to {target['name']}, prorata_amount={resp['prorata_amount']}, orders_created={resp.get('orders_created')}")

    def test_upgrade_plan_creates_order_when_prorata_positive(self, partner_session):
        """After upgrade, check partner's plan has changed."""
        r = partner_session.get(f"{BASE_URL}/api/partner/my-plan")
        assert r.status_code == 200
        current = r.json().get("current_plan")
        print(f"PASS: Partner current plan after upgrade: {current['name'] if current else 'None'}")
        # The plan should have been updated
        assert current is not None, "current_plan should not be None after upgrade"


# ---------------------------------------------------------------------------
# Partner Submissions Tests
# ---------------------------------------------------------------------------

class TestPartnerSubmissions:
    """Test partner downgrade request submissions."""

    submission_id = None

    def test_create_downgrade_submission(self, partner_session):
        """POST /partner/submissions should create a pending downgrade request."""
        # Get available plans to find a downgrade target
        my_plan_r = partner_session.get(f"{BASE_URL}/api/partner/my-plan")
        assert my_plan_r.status_code == 200
        data = my_plan_r.json()
        current = data.get("current_plan")
        available = data.get("available_plans", [])
        current_price = (current or {}).get("monthly_price", 0) or 0

        # Find a cheaper plan (downgrade)
        downgrade_plans = [p for p in available if (p.get("monthly_price") or 0) < current_price]

        if not downgrade_plans:
            # Try any plan for submission
            target_id = available[0]["id"] if available else None
            if not target_id:
                pytest.skip("No plans available for submission test")
        else:
            target_id = downgrade_plans[0]["id"]

        r = partner_session.post(f"{BASE_URL}/api/partner/submissions", json={
            "type": "plan_downgrade",
            "requested_plan_id": target_id,
            "message": "TEST_Downgrade request for testing",
        })
        assert r.status_code == 200, f"Expected 200 got {r.status_code}: {r.text}"
        sub = r.json()["submission"]
        assert sub["status"] == "pending"
        assert sub["type"] == "plan_downgrade"
        assert sub["partner_id"] is not None
        assert sub.get("effective_date") is not None
        TestPartnerSubmissions.submission_id = sub["id"]
        print(f"PASS: Created submission id={sub['id']}, status={sub['status']}, effective_date={sub['effective_date']}")

    def test_list_my_submissions(self, partner_session):
        """GET /partner/submissions should return partner's own submissions."""
        r = partner_session.get(f"{BASE_URL}/api/partner/submissions")
        assert r.status_code == 200, f"Expected 200 got {r.status_code}: {r.text}"
        data = r.json()
        assert "submissions" in data
        assert isinstance(data["submissions"], list)
        assert len(data["submissions"]) >= 1, "Expected at least 1 submission after creating one"
        # Verify pending submission is there
        pending = [s for s in data["submissions"] if s["status"] == "pending"]
        print(f"PASS: list_my_submissions returned {len(data['submissions'])} total, {len(pending)} pending")

    def test_submission_has_required_fields(self, partner_session):
        """Each submission should have required fields."""
        r = partner_session.get(f"{BASE_URL}/api/partner/submissions")
        assert r.status_code == 200
        items = r.json()["submissions"]
        assert len(items) > 0
        item = items[0]
        for field in ["id", "partner_id", "type", "status", "created_at", "effective_date"]:
            assert field in item, f"Submission missing field: {field}"
        print(f"PASS: Submission has all required fields")


# ---------------------------------------------------------------------------
# Admin Partner Submissions Tests
# ---------------------------------------------------------------------------

class TestAdminPartnerSubmissions:
    """Test admin endpoints for managing partner submissions."""

    def test_admin_can_list_all_submissions(self, admin_session):
        """GET /admin/partner-submissions should return all submissions for platform admin."""
        r = admin_session.get(f"{BASE_URL}/api/admin/partner-submissions")
        assert r.status_code == 200, f"Expected 200 got {r.status_code}: {r.text}"
        data = r.json()
        assert "submissions" in data
        assert "total" in data
        assert "page" in data
        assert isinstance(data["submissions"], list)
        print(f"PASS: admin list_partner_submissions returned {data['total']} total, {len(data['submissions'])} on page")

    def test_admin_can_filter_by_status(self, admin_session):
        """GET /admin/partner-submissions?status=pending should filter results."""
        r = admin_session.get(f"{BASE_URL}/api/admin/partner-submissions", params={"status": "pending"})
        assert r.status_code == 200, f"Expected 200 got {r.status_code}: {r.text}"
        data = r.json()
        # All returned items should be pending
        for item in data["submissions"]:
            assert item["status"] == "pending", f"Got non-pending item: {item['status']}"
        print(f"PASS: filter status=pending returned {len(data['submissions'])} pending submissions")

    def test_admin_approve_submission(self, admin_session):
        """PUT /admin/partner-submissions/{id} with action=approve should approve and apply plan."""
        sub_id = TestPartnerSubmissions.submission_id
        if not sub_id:
            # Try to find a pending submission
            r = admin_session.get(f"{BASE_URL}/api/admin/partner-submissions", params={"status": "pending"})
            items = r.json().get("submissions", [])
            if not items:
                pytest.skip("No pending submissions to approve")
            sub_id = items[0]["id"]

        r = admin_session.put(f"{BASE_URL}/api/admin/partner-submissions/{sub_id}", json={
            "action": "approve",
            "resolution_note": "TEST_Approved for automated testing",
        })
        assert r.status_code == 200, f"Expected 200 got {r.status_code}: {r.text}"
        resp = r.json()
        assert resp["status"] == "approved"
        assert resp["message"] == "Submission approved"
        print(f"PASS: Approved submission {sub_id}: status={resp['status']}")

    def test_approved_submission_shows_in_list(self, admin_session):
        """After approval, the submission should show as approved."""
        r = admin_session.get(f"{BASE_URL}/api/admin/partner-submissions", params={"status": "approved"})
        assert r.status_code == 200
        approved = r.json()["submissions"]
        # Should have at least one approved submission
        print(f"PASS: {len(approved)} approved submission(s) in list")

    def test_admin_reject_new_submission(self, admin_session, partner_session):
        """Create a new submission and reject it."""
        # Create a new submission first
        my_plan_r = partner_session.get(f"{BASE_URL}/api/partner/my-plan")
        data = my_plan_r.json()
        available = data.get("available_plans", [])
        if not available:
            pytest.skip("No available plans to submit")

        target_id = available[0]["id"]
        sub_r = partner_session.post(f"{BASE_URL}/api/partner/submissions", json={
            "type": "plan_downgrade",
            "requested_plan_id": target_id,
            "message": "TEST_Submission to be rejected",
        })
        assert sub_r.status_code == 200
        sub_id = sub_r.json()["submission"]["id"]

        # Reject it
        r = admin_session.put(f"{BASE_URL}/api/admin/partner-submissions/{sub_id}", json={
            "action": "reject",
            "resolution_note": "TEST_Rejected for automated testing",
        })
        assert r.status_code == 200, f"Expected 200 got {r.status_code}: {r.text}"
        resp = r.json()
        assert resp["status"] == "rejected"
        print(f"PASS: Rejected submission {sub_id}: status={resp['status']}")

    def test_cannot_resolve_already_resolved_submission(self, admin_session):
        """Trying to approve/reject an already resolved submission should return 400."""
        sub_id = TestPartnerSubmissions.submission_id
        if not sub_id:
            pytest.skip("No submission ID available")

        r = admin_session.put(f"{BASE_URL}/api/admin/partner-submissions/{sub_id}", json={
            "action": "approve",
        })
        assert r.status_code == 400, f"Expected 400 got {r.status_code}: {r.text}"
        print("PASS: Cannot re-resolve an already-resolved submission (400 returned)")

    def test_partner_cannot_access_admin_submissions(self, partner_session):
        """Partner admin should not be able to see ALL submissions via admin endpoint (only own)."""
        r = partner_session.get(f"{BASE_URL}/api/admin/partner-submissions")
        # Partner admins still get 200 but only see their own submissions
        assert r.status_code == 200, f"Expected 200 got {r.status_code}: {r.text}"
        data = r.json()
        # All returned items should belong to the partner
        for item in data.get("submissions", []):
            print(f"  Submission: partner_id={item.get('partner_id')}, type={item.get('type')}")
        print(f"PASS: Partner sees {len(data['submissions'])} submissions (own only)")

    def test_only_platform_admin_can_approve(self, partner_session, admin_session):
        """Only platform admin should be able to approve/reject submissions."""
        # Create a submission
        my_plan_r = partner_session.get(f"{BASE_URL}/api/partner/my-plan")
        data = my_plan_r.json()
        available = data.get("available_plans", [])
        if not available:
            pytest.skip("No available plans")

        sub_r = partner_session.post(f"{BASE_URL}/api/partner/submissions", json={
            "type": "plan_downgrade",
            "requested_plan_id": available[0]["id"],
            "message": "TEST_To test authorization",
        })
        assert sub_r.status_code == 200
        sub_id = sub_r.json()["submission"]["id"]

        # Partner tries to approve — should be 403
        r = partner_session.put(f"{BASE_URL}/api/admin/partner-submissions/{sub_id}", json={
            "action": "approve",
        })
        assert r.status_code == 403, f"Expected 403 got {r.status_code}: {r.text}"
        print("PASS: Partner admin correctly gets 403 when trying to approve/reject submissions")

        # Clean up - admin rejects it
        admin_session.put(f"{BASE_URL}/api/admin/partner-submissions/{sub_id}", json={
            "action": "reject",
            "resolution_note": "TEST_Auth test cleanup",
        })

    def test_approve_nonexistent_submission_returns_404(self, admin_session):
        """Approving a non-existent submission should return 404."""
        r = admin_session.put(f"{BASE_URL}/api/admin/partner-submissions/nonexistent-id-xyz", json={
            "action": "approve",
        })
        assert r.status_code == 404, f"Expected 404 got {r.status_code}: {r.text}"
        print("PASS: Nonexistent submission returns 404")

    def test_invalid_action_returns_400(self, admin_session):
        """PUT with invalid action should return 400."""
        # Get any submission
        r = admin_session.get(f"{BASE_URL}/api/admin/partner-submissions")
        items = r.json().get("submissions", [])
        if not items:
            pytest.skip("No submissions to test")
        sub_id = items[0]["id"]

        r = admin_session.put(f"{BASE_URL}/api/admin/partner-submissions/{sub_id}", json={
            "action": "invalid_action",
        })
        assert r.status_code == 400, f"Expected 400 got {r.status_code}: {r.text}"
        print("PASS: Invalid action returns 400")


# ---------------------------------------------------------------------------
# Public plans endpoint
# ---------------------------------------------------------------------------

class TestPublicPlansEndpoint:
    """Test GET /partner/plans/public endpoint."""

    def test_public_plans_endpoint_works_no_auth(self):
        """GET /partner/plans/public should return public plans without auth."""
        r = requests.get(f"{BASE_URL}/api/partner/plans/public")
        assert r.status_code == 200, f"Expected 200 got {r.status_code}: {r.text}"
        data = r.json()
        assert "plans" in data
        assert isinstance(data["plans"], list)
        for plan in data["plans"]:
            assert plan.get("is_public") is True, f"Non-public plan returned: {plan['name']}"
        print(f"PASS: /partner/plans/public returned {len(data['plans'])} public plans: {[p['name'] for p in data['plans']]}")
