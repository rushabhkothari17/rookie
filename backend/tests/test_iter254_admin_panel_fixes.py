"""
Backend tests for Admin Panel fixes - Iteration 254
Tests: Filters Tab (Issues 1-5), Users/Presets (Issues 6-8), 
       Store filter validation (409/422), Presets CRUD
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth_token(session):
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if resp.status_code != 200:
        pytest.skip(f"Admin login failed: {resp.status_code} - {resp.text}")
    token = resp.json().get("token") or resp.json().get("access_token")
    return token


@pytest.fixture(scope="module")
def authed_session(session, auth_token):
    """Session with Bearer auth header."""
    login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    token = login_resp.json().get("token") or login_resp.json().get("access_token")
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


# ── Test: Store Filters CRUD ──────────────────────────────────────────────────

class TestStoreFilters:
    """Store filter API tests - Issues 1-5"""

    def test_list_store_filters(self, authed_session):
        """GET /api/admin/store-filters should return list"""
        r = authed_session.get(f"{BASE_URL}/api/admin/store-filters")
        assert r.status_code == 200, f"Unexpected: {r.text}"
        data = r.json()
        assert "filters" in data
        assert isinstance(data["filters"], list)
        print(f"PASS: list_store_filters - {len(data['filters'])} filters found")

    def test_create_filter_name_too_long_returns_422(self, authed_session):
        """Issue 3: Names > 100 chars should return 422"""
        long_name = "A" * 101
        r = authed_session.post(f"{BASE_URL}/api/admin/store-filters", json={
            "name": long_name,
            "filter_type": "tag",
            "options": [],
            "is_active": True,
            "sort_order": 0
        })
        assert r.status_code == 422, f"Expected 422 for too-long name, got {r.status_code}: {r.text}"
        print(f"PASS: 422 returned for name > 100 chars")

    def test_create_filter_duplicate_name_returns_409(self, authed_session):
        """Issue 4: Duplicate filter names should return 409"""
        # First create a filter
        name = "TEST_Duplicate_Filter_Check_254"
        create1 = authed_session.post(f"{BASE_URL}/api/admin/store-filters", json={
            "name": name,
            "filter_type": "tag",
            "options": [{"label": "Option1", "value": "option1"}],
            "is_active": True,
            "sort_order": 99
        })
        if create1.status_code == 409:
            # Already exists from a previous run; that's fine - test duplicate behavior
            pass
        elif create1.status_code == 201 or create1.status_code == 200:
            pass
        else:
            pytest.skip(f"Could not create first filter: {create1.status_code} {create1.text}")

        # Now try creating same name again
        create2 = authed_session.post(f"{BASE_URL}/api/admin/store-filters", json={
            "name": name,
            "filter_type": "billing_type",
            "options": [],
            "is_active": True,
            "sort_order": 99
        })
        assert create2.status_code == 409, f"Expected 409 for duplicate name, got {create2.status_code}: {create2.text}"
        assert "already exists" in create2.json().get("detail", "").lower(), f"Expected 'already exists' in detail: {create2.json()}"
        print(f"PASS: 409 returned for duplicate filter name")

        # Clean up: delete the test filter
        filters_resp = authed_session.get(f"{BASE_URL}/api/admin/store-filters")
        if filters_resp.status_code == 200:
            for f in filters_resp.json().get("filters", []):
                if f.get("name") == name:
                    authed_session.delete(f"{BASE_URL}/api/admin/store-filters/{f['id']}")

    def test_create_filter_plan_name_type(self, authed_session):
        """Issue 1: plan_name should be a valid filter_type"""
        name = "TEST_Plan_Name_Filter_254"
        r = authed_session.post(f"{BASE_URL}/api/admin/store-filters", json={
            "name": name,
            "filter_type": "plan_name",
            "options": [{"label": "Pro", "value": "pro"}],
            "is_active": True,
            "sort_order": 99
        })
        # Should succeed (200 or 201), or 409 if already exists from prev run
        assert r.status_code in (200, 201, 409), f"Unexpected: {r.status_code}: {r.text}"
        if r.status_code in (200, 201):
            data = r.json()
            assert data.get("filter", {}).get("filter_type") == "plan_name", f"filter_type not plan_name: {data}"
            print(f"PASS: plan_name filter type accepted")
            # Clean up
            fid = data["filter"].get("id")
            if fid:
                authed_session.delete(f"{BASE_URL}/api/admin/store-filters/{fid}")
        else:
            print(f"PASS: plan_name filter type OK (409 means it already exists)")

    def test_create_filter_with_multiple_tag_options(self, authed_session):
        """Issue 5: Creating a tag filter with multiple options saves ALL"""
        name = "TEST_Tag_Options_Filter_254"
        options = [
            {"label": "Fast", "value": "fast"},
            {"label": "Slow", "value": "slow"},
            {"label": "Medium", "value": "medium"},
        ]
        r = authed_session.post(f"{BASE_URL}/api/admin/store-filters", json={
            "name": name,
            "filter_type": "tag",
            "options": options,
            "is_active": True,
            "sort_order": 99
        })
        if r.status_code == 409:
            # Already exists, clean up and retry
            filters_resp = authed_session.get(f"{BASE_URL}/api/admin/store-filters")
            for f in filters_resp.json().get("filters", []):
                if f.get("name") == name:
                    authed_session.delete(f"{BASE_URL}/api/admin/store-filters/{f['id']}")
            r = authed_session.post(f"{BASE_URL}/api/admin/store-filters", json={
                "name": name,
                "filter_type": "tag",
                "options": options,
                "is_active": True,
                "sort_order": 99
            })
        assert r.status_code in (200, 201), f"Create failed: {r.status_code}: {r.text}"
        data = r.json()
        saved_options = data.get("filter", {}).get("options", [])
        assert len(saved_options) == 3, f"Expected 3 options saved, got {len(saved_options)}: {saved_options}"
        print(f"PASS: All {len(saved_options)} tag options saved correctly")

        # Clean up
        fid = data["filter"].get("id")
        if fid:
            authed_session.delete(f"{BASE_URL}/api/admin/store-filters/{fid}")

    def test_create_filter_exact_100_chars_name(self, authed_session):
        """Issue 3: Exactly 100 char name should succeed"""
        name = "A" * 100
        r = authed_session.post(f"{BASE_URL}/api/admin/store-filters", json={
            "name": name,
            "filter_type": "billing_type",
            "options": [],
            "is_active": True,
            "sort_order": 99
        })
        # Should succeed or 409 if dup
        assert r.status_code in (200, 201, 409), f"100-char name should be valid, got {r.status_code}: {r.text}"
        if r.status_code in (200, 201):
            fid = r.json().get("filter", {}).get("id")
            if fid:
                authed_session.delete(f"{BASE_URL}/api/admin/store-filters/{fid}")
        print(f"PASS: Exactly 100 char name accepted (status {r.status_code})")


# ── Test: Admin Permissions Modules (preset_roles) ────────────────────────────

class TestPermissionsModules:
    """Test /api/admin/permissions/modules - Issues 6-8"""

    def test_get_permissions_modules(self, authed_session):
        """GET /api/admin/permissions/modules returns modules and preset_roles"""
        r = authed_session.get(f"{BASE_URL}/api/admin/permissions/modules")
        assert r.status_code == 200, f"Unexpected: {r.status_code}: {r.text}"
        data = r.json()
        assert "modules" in data
        assert "preset_roles" in data
        assert isinstance(data["preset_roles"], list)
        print(f"PASS: Modules endpoint returns {len(data['preset_roles'])} preset_roles")

    def test_system_presets_have_is_system_true(self, authed_session):
        """Issues 6-7: Built-in presets should have is_system=True"""
        r = authed_session.get(f"{BASE_URL}/api/admin/permissions/modules")
        assert r.status_code == 200
        data = r.json()
        presets = data.get("preset_roles", [])
        system_presets = [p for p in presets if p.get("is_system") is True]
        assert len(system_presets) > 0, f"No system presets found. Presets: {presets}"
        # Check they have required fields
        for p in system_presets:
            assert "key" in p, f"Missing key in preset: {p}"
            assert "name" in p, f"Missing name in preset: {p}"
            assert p["is_system"] is True, f"Expected is_system=True: {p}"
        print(f"PASS: {len(system_presets)} system presets with is_system=True found")


# ── Test: Custom Presets CRUD ────────────────────────────────────────────────

class TestPresetsCRUD:
    """Test /api/admin/presets - Issues 6-8"""
    _created_id = None

    def test_list_presets_empty_or_list(self, authed_session):
        """GET /api/admin/presets returns list"""
        r = authed_session.get(f"{BASE_URL}/api/admin/presets")
        assert r.status_code == 200, f"Unexpected: {r.status_code}: {r.text}"
        data = r.json()
        assert "presets" in data
        assert isinstance(data["presets"], list)
        print(f"PASS: list presets returns {len(data['presets'])} custom presets")

    def test_create_custom_preset(self, authed_session):
        """Issue 8: POST /api/admin/presets creates a preset with tenant_id"""
        # Clean up any leftover from previous run
        list_r = authed_session.get(f"{BASE_URL}/api/admin/presets")
        for p in list_r.json().get("presets", []):
            if p.get("name") == "TEST_Custom_Preset_254":
                authed_session.delete(f"{BASE_URL}/api/admin/presets/{p['id']}")

        r = authed_session.post(f"{BASE_URL}/api/admin/presets", json={
            "name": "TEST_Custom_Preset_254",
            "description": "Test preset for iteration 254",
            "module_permissions": {"customers": "read", "orders": "write"}
        })
        assert r.status_code in (200, 201), f"Create preset failed: {r.status_code}: {r.text}"
        data = r.json()
        preset = data.get("preset", {})
        assert preset.get("name") == "TEST_Custom_Preset_254"
        assert preset.get("is_custom") is True, f"Expected is_custom=True: {preset}"
        assert "tenant_id" in preset, f"Missing tenant_id in preset: {preset}"
        assert "id" in preset
        TestPresetsCRUD._created_id = preset["id"]
        print(f"PASS: Custom preset created with id={preset['id']}, tenant_id={preset['tenant_id']}")

    def test_custom_preset_appears_in_permissions_modules(self, authed_session):
        """Issue 8: Custom preset should appear in /permissions/modules endpoint"""
        r = authed_session.get(f"{BASE_URL}/api/admin/permissions/modules")
        assert r.status_code == 200
        presets = r.json().get("preset_roles", [])
        custom = [p for p in presets if p.get("name") == "TEST_Custom_Preset_254"]
        assert len(custom) > 0, f"Custom preset not in permissions/modules. Found: {[p['name'] for p in presets]}"
        assert custom[0].get("is_system") is False, f"Expected is_system=False for custom: {custom[0]}"
        print(f"PASS: Custom preset appears in permissions/modules with is_system=False")

    def test_create_duplicate_preset_returns_409(self, authed_session):
        """Issue 8: Duplicate preset names should return 409"""
        r = authed_session.post(f"{BASE_URL}/api/admin/presets", json={
            "name": "TEST_Custom_Preset_254",
            "description": "Duplicate",
            "module_permissions": {}
        })
        assert r.status_code == 409, f"Expected 409 for duplicate preset, got {r.status_code}: {r.text}"
        print(f"PASS: 409 for duplicate preset name")

    def test_update_custom_preset(self, authed_session):
        """PUT /api/admin/presets/{id} updates the preset"""
        if not TestPresetsCRUD._created_id:
            pytest.skip("No preset created to update")
        r = authed_session.put(f"{BASE_URL}/api/admin/presets/{TestPresetsCRUD._created_id}", json={
            "name": "TEST_Custom_Preset_254",
            "description": "Updated description",
            "module_permissions": {"customers": "write", "orders": "read"}
        })
        assert r.status_code == 200, f"Update preset failed: {r.status_code}: {r.text}"
        preset = r.json().get("preset", {})
        assert preset.get("description") == "Updated description"
        print(f"PASS: Preset updated successfully")

    def test_delete_custom_preset(self, authed_session):
        """DELETE /api/admin/presets/{id} removes the preset"""
        if not TestPresetsCRUD._created_id:
            pytest.skip("No preset created to delete")
        r = authed_session.delete(f"{BASE_URL}/api/admin/presets/{TestPresetsCRUD._created_id}")
        assert r.status_code == 200, f"Delete preset failed: {r.status_code}: {r.text}"
        # Verify it's gone
        get_r = authed_session.get(f"{BASE_URL}/api/admin/presets")
        remaining = [p for p in get_r.json().get("presets", []) if p.get("id") == TestPresetsCRUD._created_id]
        assert len(remaining) == 0, f"Preset not deleted: {remaining}"
        print(f"PASS: Preset deleted and verified gone")

    def test_delete_nonexistent_preset_returns_404(self, authed_session):
        """DELETE non-existent preset should return 404"""
        r = authed_session.delete(f"{BASE_URL}/api/admin/presets/nonexistent_id_12345")
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
        print(f"PASS: 404 for non-existent preset delete")


# ── Test: Resources endpoint ──────────────────────────────────────────────────

class TestResourcesEndpoint:
    """Test resources endpoint for Issue 9"""

    def test_resources_list(self, authed_session):
        """GET /api/resources/admin/list returns list"""
        r = authed_session.get(f"{BASE_URL}/api/resources/admin/list")
        assert r.status_code == 200, f"Unexpected: {r.status_code}: {r.text}"
        data = r.json()
        assert "resources" in data
        print(f"PASS: /api/resources/admin/list returns {len(data['resources'])} resources")

    def test_resource_view_uses_slug_or_id(self, authed_session):
        """Issue 9: Resource should have slug or id for URL construction"""
        r = authed_session.get(f"{BASE_URL}/api/resources/admin/list?per_page=5")
        assert r.status_code == 200
        data = r.json()
        resources = data.get("resources", [])
        if len(resources) == 0:
            print("INFO: No resources to test view URL, skipping check")
            return
        for res in resources[:3]:
            assert "id" in res, f"Resource missing id: {res}"
            slug_or_id = res.get("slug") or res.get("id")
            assert slug_or_id, f"Resource has neither slug nor id: {res}"
        print(f"PASS: Resources have slug/id for URL construction")
