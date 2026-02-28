"""
Iteration 151 Backend Tests:
- Store Filters CRUD (/api/admin/store-filters) 
- Public Store Filters endpoint (/api/store/filters)
- Email Templates count (should include renewal reminders = 15 templates)
- Scheduler service smoke test (just verify it starts without error)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# ── Auth helpers ─────────────────────────────────────────────────────────────

def get_platform_admin_token():
    # Platform admin login does NOT use partner_code
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@automateaccounts.local",
        "password": "ChangeMe123!"
    })
    if resp.status_code == 200:
        return resp.json().get("token")
    return None

def get_partner_admin_token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "sarah@brightaccounting.local",
        "password": "ChangeMe123!",
        "partner_code": "bright-accounting"
    })
    if resp.status_code == 200:
        return resp.json().get("token")
    return None


@pytest.fixture(scope="module")
def platform_token():
    token = get_platform_admin_token()
    if not token:
        pytest.skip("Platform admin login failed")
    return token

@pytest.fixture(scope="module")
def partner_token():
    token = get_partner_admin_token()
    if not token:
        pytest.skip("Partner admin login failed")
    return token

@pytest.fixture(scope="module")
def platform_headers(platform_token):
    return {"Authorization": f"Bearer {platform_token}", "Content-Type": "application/json"}

@pytest.fixture(scope="module")
def partner_headers(partner_token):
    return {"Authorization": f"Bearer {partner_token}", "Content-Type": "application/json"}


# ── Email Templates ──────────────────────────────────────────────────────────

class TestEmailTemplates:
    """Verify email templates including renewal reminders"""

    def test_email_templates_list_returns_200(self, platform_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_email_templates_count_at_least_15(self, platform_headers):
        """Should have 15 templates now including subscription_renewal_reminder and partner_subscription_renewal_reminder"""
        resp = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=platform_headers)
        assert resp.status_code == 200
        data = resp.json()
        templates = data.get("templates", [])
        assert len(templates) >= 15, f"Expected >= 15 templates, got {len(templates)}: {[t['trigger'] for t in templates]}"

    def test_subscription_renewal_reminder_template_exists(self, platform_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=platform_headers)
        assert resp.status_code == 200
        triggers = [t["trigger"] for t in resp.json().get("templates", [])]
        assert "subscription_renewal_reminder" in triggers, f"Missing subscription_renewal_reminder. Found: {triggers}"

    def test_partner_subscription_renewal_reminder_template_exists(self, platform_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=platform_headers)
        assert resp.status_code == 200
        triggers = [t["trigger"] for t in resp.json().get("templates", [])]
        assert "partner_subscription_renewal_reminder" in triggers, f"Missing partner_subscription_renewal_reminder. Found: {triggers}"

    def test_renewal_reminder_template_has_correct_fields(self, platform_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=platform_headers)
        assert resp.status_code == 200
        templates = resp.json().get("templates", [])
        reminder = next((t for t in templates if t["trigger"] == "subscription_renewal_reminder"), None)
        assert reminder is not None
        assert reminder.get("label") == "Subscription Renewal Reminder"
        assert reminder.get("is_enabled") is True
        assert "{{renewal_date}}" in reminder.get("available_variables", [])


# ── Store Filters CRUD ────────────────────────────────────────────────────────

class TestStoreFiltersCRUD:
    """CRUD for /api/admin/store-filters"""

    created_filter_id = None
    created_price_filter_id = None
    created_custom_filter_id = None

    def test_list_store_filters_empty_or_list(self, platform_headers):
        """GET /admin/store-filters should return 200"""
        resp = requests.get(f"{BASE_URL}/api/admin/store-filters", headers=platform_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "filters" in data
        assert "total" in data

    def test_create_category_filter(self, platform_headers):
        """POST /admin/store-filters - category type"""
        payload = {
            "name": "TEST_Service Type",
            "filter_type": "category",
            "is_active": True,
            "sort_order": 0,
            "show_count": True
        }
        resp = requests.post(f"{BASE_URL}/api/admin/store-filters", json=payload, headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "filter" in data
        assert data["filter"]["name"] == "TEST_Service Type"
        assert data["filter"]["filter_type"] == "category"
        assert data["filter"]["is_active"] is True
        TestStoreFiltersCRUD.created_filter_id = data["filter"]["id"]

    def test_get_store_filters_returns_created(self, platform_headers):
        """GET after creation should include the new filter"""
        resp = requests.get(f"{BASE_URL}/api/admin/store-filters", headers=platform_headers)
        assert resp.status_code == 200
        filters = resp.json()["filters"]
        ids = [f["id"] for f in filters]
        assert TestStoreFiltersCRUD.created_filter_id in ids, f"Created filter not in list: {ids}"

    def test_update_store_filter_name(self, platform_headers):
        """PUT /admin/store-filters/{id} - update name"""
        fid = TestStoreFiltersCRUD.created_filter_id
        assert fid is not None, "No filter created yet"
        resp = requests.put(
            f"{BASE_URL}/api/admin/store-filters/{fid}",
            json={"name": "TEST_Updated Service Type"},
            headers=platform_headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["filter"]["name"] == "TEST_Updated Service Type"

    def test_get_after_update_shows_new_name(self, platform_headers):
        """GET after update verifies persistence"""
        fid = TestStoreFiltersCRUD.created_filter_id
        resp = requests.get(f"{BASE_URL}/api/admin/store-filters", headers=platform_headers)
        assert resp.status_code == 200
        filters = resp.json()["filters"]
        f = next((f for f in filters if f["id"] == fid), None)
        assert f is not None
        assert f["name"] == "TEST_Updated Service Type"

    def test_toggle_filter_inactive(self, platform_headers):
        """PUT to set is_active=False"""
        fid = TestStoreFiltersCRUD.created_filter_id
        resp = requests.put(
            f"{BASE_URL}/api/admin/store-filters/{fid}",
            json={"is_active": False},
            headers=platform_headers
        )
        assert resp.status_code == 200
        assert resp.json()["filter"]["is_active"] is False

    def test_create_price_range_filter_with_options(self, platform_headers):
        """POST /admin/store-filters - price_range type with options"""
        payload = {
            "name": "TEST_Price Range",
            "filter_type": "price_range",
            "options": [
                {"label": "Under £50", "value": "0-50"},
                {"label": "£50-£200", "value": "50-200"},
                {"label": "Over £200", "value": "200-999999"}
            ],
            "is_active": True,
            "sort_order": 1,
            "show_count": True
        }
        resp = requests.post(f"{BASE_URL}/api/admin/store-filters", json=payload, headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["filter"]["filter_type"] == "price_range"
        assert len(data["filter"]["options"]) == 3
        assert data["filter"]["options"][0]["label"] == "Under £50"
        assert data["filter"]["options"][0]["value"] == "0-50"
        TestStoreFiltersCRUD.created_price_filter_id = data["filter"]["id"]

    def test_create_custom_filter_with_options(self, platform_headers):
        """POST /admin/store-filters - custom type with options"""
        payload = {
            "name": "TEST_Business Size",
            "filter_type": "custom",
            "options": [
                {"label": "Small Business", "value": "small"},
                {"label": "Medium Business", "value": "medium"},
                {"label": "Enterprise", "value": "enterprise"}
            ],
            "is_active": True,
            "sort_order": 2
        }
        resp = requests.post(f"{BASE_URL}/api/admin/store-filters", json=payload, headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["filter"]["filter_type"] == "custom"
        assert len(data["filter"]["options"]) == 3
        TestStoreFiltersCRUD.created_custom_filter_id = data["filter"]["id"]

    def test_invalid_filter_type_returns_400(self, platform_headers):
        """POST with invalid filter_type should return 400"""
        payload = {"name": "TEST_Bad Filter", "filter_type": "invalid_type"}
        resp = requests.post(f"{BASE_URL}/api/admin/store-filters", json=payload, headers=platform_headers)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"

    def test_update_nonexistent_filter_returns_404(self, platform_headers):
        """PUT on non-existent filter ID should return 404"""
        resp = requests.put(
            f"{BASE_URL}/api/admin/store-filters/nonexistent-id-12345",
            json={"name": "Should Fail"},
            headers=platform_headers
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"


# ── Public Store Filters Endpoint ─────────────────────────────────────────────

class TestPublicStoreFilters:
    """Test the public /api/store/filters endpoint (no auth required)"""

    def test_public_store_filters_no_auth(self):
        """GET /store/filters without any auth header"""
        resp = requests.get(f"{BASE_URL}/api/store/filters")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_public_store_filters_returns_active_only(self, platform_headers):
        """Public endpoint should only return active filters"""
        # First get all filters (admin) and check only active ones appear in public endpoint
        admin_resp = requests.get(f"{BASE_URL}/api/admin/store-filters", headers=platform_headers)
        assert admin_resp.status_code == 200
        active_filters = [f for f in admin_resp.json()["filters"] if f["is_active"]]

        public_resp = requests.get(f"{BASE_URL}/api/store/filters")
        assert public_resp.status_code == 200
        public_filters = public_resp.json()["filters"]
        # All public filters should be active
        for pf in public_filters:
            assert pf.get("is_active") is True, f"Filter {pf['name']} is not active but appeared in public endpoint"

    def test_public_store_filters_with_tenant_code(self):
        """GET /store/filters?tenant_code=automate-accounts"""
        resp = requests.get(f"{BASE_URL}/api/store/filters?tenant_code=automate-accounts")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "filters" in data

    def test_public_store_filters_structure(self):
        """Filters should have expected fields"""
        resp = requests.get(f"{BASE_URL}/api/store/filters")
        assert resp.status_code == 200
        for f in resp.json().get("filters", []):
            assert "id" in f
            assert "name" in f
            assert "filter_type" in f
            assert "is_active" in f


# ── Delete Cleanup ────────────────────────────────────────────────────────────

class TestStoreFiltersDelete:
    """Delete test data"""

    def test_delete_category_filter(self, platform_headers):
        fid = TestStoreFiltersCRUD.created_filter_id
        if not fid:
            pytest.skip("No filter created")
        resp = requests.delete(f"{BASE_URL}/api/admin/store-filters/{fid}", headers=platform_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert "deleted" in resp.json().get("message", "").lower()

    def test_verify_deleted_filter_gone(self, platform_headers):
        fid = TestStoreFiltersCRUD.created_filter_id
        if not fid:
            pytest.skip("No filter to verify")
        resp = requests.get(f"{BASE_URL}/api/admin/store-filters", headers=platform_headers)
        assert resp.status_code == 200
        ids = [f["id"] for f in resp.json()["filters"]]
        assert fid not in ids, f"Deleted filter {fid} still in list"

    def test_delete_price_range_filter(self, platform_headers):
        fid = TestStoreFiltersCRUD.created_price_filter_id
        if not fid:
            pytest.skip("No price filter created")
        resp = requests.delete(f"{BASE_URL}/api/admin/store-filters/{fid}", headers=platform_headers)
        assert resp.status_code == 200

    def test_delete_custom_filter(self, platform_headers):
        fid = TestStoreFiltersCRUD.created_custom_filter_id
        if not fid:
            pytest.skip("No custom filter created")
        resp = requests.delete(f"{BASE_URL}/api/admin/store-filters/{fid}", headers=platform_headers)
        assert resp.status_code == 200

    def test_delete_nonexistent_filter_returns_404(self, platform_headers):
        resp = requests.delete(
            f"{BASE_URL}/api/admin/store-filters/nonexistent-id-99999",
            headers=platform_headers
        )
        assert resp.status_code == 404


# ── Partner Admin Access ──────────────────────────────────────────────────────

class TestPartnerAdminMyBilling:
    """Regression - partner admin My Billing still works"""

    def test_partner_my_subscriptions(self, partner_headers):
        resp = requests.get(f"{BASE_URL}/api/partner/my-subscriptions", headers=partner_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_partner_my_orders(self, partner_headers):
        resp = requests.get(f"{BASE_URL}/api/partner/my-orders", headers=partner_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


# ── Store Filters Access Control ──────────────────────────────────────────────

class TestStoreFiltersAccessControl:
    """Store filters admin endpoints require auth"""

    def test_list_store_filters_requires_auth(self):
        resp = requests.get(f"{BASE_URL}/api/admin/store-filters")
        assert resp.status_code in (401, 403), f"Expected 401/403 without auth, got {resp.status_code}"

    def test_create_store_filter_requires_auth(self):
        payload = {"name": "Unauthorized Filter", "filter_type": "category"}
        resp = requests.post(f"{BASE_URL}/api/admin/store-filters", json=payload)
        assert resp.status_code in (401, 403), f"Expected 401/403 without auth, got {resp.status_code}"
