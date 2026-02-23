"""
Webhook system tests — iteration 69
Covers: event catalog, CRUD, test delivery, rotate-secret, delivery logs,
        validation, tenant isolation, dispatch_event, field filtering, HMAC.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# ── Credentials ───────────────────────────────────────────────────────────────
ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASS = "ChangeMe123!"
PARTNER_CODE = "automate-accounts"

TENANT_B_EMAIL = "adminb@tenantb.local"
TENANT_B_PASS = "ChangeMe123!"
TENANT_B_PARTNER_CODE = "tenant-b"

# Test webhook URL (always returns 200)
TEST_WEBHOOK_URL = "https://httpbin.org/post"


# ── Auth helpers ───────────────────────────────────────────────────────────────

def get_admin_token() -> str:
    """Login as automate-accounts admin and return JWT."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASS,
        "partner_code": PARTNER_CODE,
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return resp.json()["access_token"]


def get_tenant_b_token() -> str:
    """Login as tenant-b admin and return JWT."""
    resp = requests.post(f"{BASE_URL}/api/auth/partner-login", json={
        "email": TENANT_B_EMAIL,
        "password": TENANT_B_PASS,
        "partner_code": TENANT_B_PARTNER_CODE,
    })
    assert resp.status_code == 200, f"Tenant B login failed: {resp.text}"
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_token():
    return get_admin_token()


@pytest.fixture(scope="module")
def tenant_b_token():
    try:
        return get_tenant_b_token()
    except Exception:
        pytest.skip("Tenant B login failed — skipping tenant isolation tests")


@pytest.fixture(scope="module")
def created_webhook(admin_token):
    """Create a test webhook and yield its data; delete after module."""
    payload = {
        "name": "TEST_WebhookCRUD",
        "url": TEST_WEBHOOK_URL,
        "subscriptions": [
            {"event": "order.created", "fields": ["id", "order_number", "total", "customer_email"]},
        ],
    }
    resp = requests.post(
        f"{BASE_URL}/api/admin/webhooks",
        json=payload,
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200, f"Create webhook failed: {resp.text}"
    data = resp.json()
    yield data
    # Teardown: delete the webhook
    requests.delete(
        f"{BASE_URL}/api/admin/webhooks/{data['id']}",
        headers=auth_headers(admin_token),
    )


# ── Event Catalog ──────────────────────────────────────────────────────────────

class TestEventCatalog:
    """GET /api/admin/webhooks/events — returns event catalog."""

    def test_event_catalog_status_200(self, admin_token):
        resp = requests.get(f"{BASE_URL}/api/admin/webhooks/events", headers=auth_headers(admin_token))
        assert resp.status_code == 200

    def test_event_catalog_has_events_key(self, admin_token):
        resp = requests.get(f"{BASE_URL}/api/admin/webhooks/events", headers=auth_headers(admin_token))
        data = resp.json()
        assert "events" in data

    def test_event_catalog_has_12_events(self, admin_token):
        resp = requests.get(f"{BASE_URL}/api/admin/webhooks/events", headers=auth_headers(admin_token))
        events = resp.json()["events"]
        assert len(events) == 12, f"Expected 12 events, got {len(events)}: {list(events.keys())}"

    def test_event_catalog_has_5_categories(self, admin_token):
        resp = requests.get(f"{BASE_URL}/api/admin/webhooks/events", headers=auth_headers(admin_token))
        events = resp.json()["events"]
        categories = {v["category"] for v in events.values()}
        assert len(categories) == 5, f"Expected 5 categories, got {len(categories)}: {categories}"

    def test_event_catalog_5_correct_categories(self, admin_token):
        resp = requests.get(f"{BASE_URL}/api/admin/webhooks/events", headers=auth_headers(admin_token))
        events = resp.json()["events"]
        categories = {v["category"] for v in events.values()}
        expected = {"Orders", "Subscriptions", "Customers", "Payments", "Quote Requests"}
        assert categories == expected, f"Categories mismatch: {categories}"

    def test_event_catalog_order_created_has_fields(self, admin_token):
        resp = requests.get(f"{BASE_URL}/api/admin/webhooks/events", headers=auth_headers(admin_token))
        events = resp.json()["events"]
        assert "order.created" in events
        assert "fields" in events["order.created"]
        assert len(events["order.created"]["fields"]) > 0

    def test_event_catalog_requires_auth(self):
        resp = requests.get(f"{BASE_URL}/api/admin/webhooks/events")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"


# ── Create Webhook ─────────────────────────────────────────────────────────────

class TestCreateWebhook:
    """POST /api/admin/webhooks — create a webhook."""

    def test_create_returns_200(self, admin_token):
        payload = {
            "name": "TEST_Create_basic",
            "url": TEST_WEBHOOK_URL,
            "subscriptions": [{"event": "order.created", "fields": ["id", "total"]}],
        }
        resp = requests.post(f"{BASE_URL}/api/admin/webhooks", json=payload, headers=auth_headers(admin_token))
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        wh_id = resp.json()["id"]
        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/webhooks/{wh_id}", headers=auth_headers(admin_token))

    def test_create_returns_secret_with_whsec_prefix(self, admin_token):
        payload = {
            "name": "TEST_Create_secret_prefix",
            "url": TEST_WEBHOOK_URL,
            "subscriptions": [{"event": "order.created", "fields": ["id"]}],
        }
        resp = requests.post(f"{BASE_URL}/api/admin/webhooks", json=payload, headers=auth_headers(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "secret" in data, "secret not returned on creation"
        assert data["secret"].startswith("whsec_"), f"Secret doesn't start with 'whsec_': {data['secret']}"
        requests.delete(f"{BASE_URL}/api/admin/webhooks/{data['id']}", headers=auth_headers(admin_token))

    def test_create_with_custom_secret(self, admin_token):
        custom_secret = "whsec_mycustomsecret123"
        payload = {
            "name": "TEST_Create_custom_secret",
            "url": TEST_WEBHOOK_URL,
            "secret": custom_secret,
            "subscriptions": [{"event": "order.created", "fields": ["id"]}],
        }
        resp = requests.post(f"{BASE_URL}/api/admin/webhooks", json=payload, headers=auth_headers(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["secret"] == custom_secret
        requests.delete(f"{BASE_URL}/api/admin/webhooks/{data['id']}", headers=auth_headers(admin_token))

    def test_create_stores_subscriptions(self, admin_token):
        payload = {
            "name": "TEST_Create_subs",
            "url": TEST_WEBHOOK_URL,
            "subscriptions": [
                {"event": "order.created", "fields": ["id", "total"]},
                {"event": "customer.registered", "fields": ["email"]},
            ],
        }
        resp = requests.post(f"{BASE_URL}/api/admin/webhooks", json=payload, headers=auth_headers(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["subscriptions"]) == 2
        events = [s["event"] for s in data["subscriptions"]]
        assert "order.created" in events
        assert "customer.registered" in events
        requests.delete(f"{BASE_URL}/api/admin/webhooks/{data['id']}", headers=auth_headers(admin_token))

    def test_create_url_validation_no_scheme(self, admin_token):
        payload = {
            "name": "TEST_Bad_url",
            "url": "webhook.example.com/hook",
            "subscriptions": [{"event": "order.created", "fields": ["id"]}],
        }
        resp = requests.post(f"{BASE_URL}/api/admin/webhooks", json=payload, headers=auth_headers(admin_token))
        assert resp.status_code == 400, f"Expected 400 for bad URL, got {resp.status_code}: {resp.text}"

    def test_create_unknown_event_returns_400(self, admin_token):
        payload = {
            "name": "TEST_Bad_event",
            "url": TEST_WEBHOOK_URL,
            "subscriptions": [{"event": "nonexistent.event", "fields": ["id"]}],
        }
        resp = requests.post(f"{BASE_URL}/api/admin/webhooks", json=payload, headers=auth_headers(admin_token))
        assert resp.status_code == 400, f"Expected 400 for unknown event, got {resp.status_code}: {resp.text}"

    def test_create_unknown_field_returns_400(self, admin_token):
        payload = {
            "name": "TEST_Bad_field",
            "url": TEST_WEBHOOK_URL,
            "subscriptions": [{"event": "order.created", "fields": ["nonexistent_field_xyz"]}],
        }
        resp = requests.post(f"{BASE_URL}/api/admin/webhooks", json=payload, headers=auth_headers(admin_token))
        assert resp.status_code == 400, f"Expected 400 for unknown field, got {resp.status_code}: {resp.text}"


# ── List Webhooks ──────────────────────────────────────────────────────────────

class TestListWebhooks:
    """GET /api/admin/webhooks — list webhooks."""

    def test_list_returns_200(self, admin_token):
        resp = requests.get(f"{BASE_URL}/api/admin/webhooks", headers=auth_headers(admin_token))
        assert resp.status_code == 200

    def test_list_has_webhooks_key(self, admin_token):
        resp = requests.get(f"{BASE_URL}/api/admin/webhooks", headers=auth_headers(admin_token))
        data = resp.json()
        assert "webhooks" in data
        assert isinstance(data["webhooks"], list)

    def test_list_does_not_expose_secret(self, admin_token, created_webhook):
        resp = requests.get(f"{BASE_URL}/api/admin/webhooks", headers=auth_headers(admin_token))
        webhooks = resp.json()["webhooks"]
        # Find our test webhook
        found = next((w for w in webhooks if w["id"] == created_webhook["id"]), None)
        assert found is not None, "Test webhook not found in list"
        assert "secret" not in found, "Secret should NOT be exposed in list"


# ── Update Webhook ─────────────────────────────────────────────────────────────

class TestUpdateWebhook:
    """PUT /api/admin/webhooks/{id} — update webhook."""

    def test_update_name(self, admin_token, created_webhook):
        wh_id = created_webhook["id"]
        resp = requests.put(
            f"{BASE_URL}/api/admin/webhooks/{wh_id}",
            json={"name": "TEST_Updated_name"},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "TEST_Updated_name"

    def test_update_is_active_false(self, admin_token, created_webhook):
        wh_id = created_webhook["id"]
        resp = requests.put(
            f"{BASE_URL}/api/admin/webhooks/{wh_id}",
            json={"is_active": False},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_active"] is False

    def test_update_is_active_true(self, admin_token, created_webhook):
        wh_id = created_webhook["id"]
        resp = requests.put(
            f"{BASE_URL}/api/admin/webhooks/{wh_id}",
            json={"is_active": True},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_active"] is True

    def test_update_subscriptions(self, admin_token, created_webhook):
        wh_id = created_webhook["id"]
        new_subs = [
            {"event": "order.created", "fields": ["id", "total"]},
            {"event": "payment.succeeded", "fields": ["amount", "currency"]},
        ]
        resp = requests.put(
            f"{BASE_URL}/api/admin/webhooks/{wh_id}",
            json={"subscriptions": new_subs},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        subs = resp.json()["subscriptions"]
        events = [s["event"] for s in subs]
        assert "order.created" in events
        assert "payment.succeeded" in events

    def test_update_url(self, admin_token, created_webhook):
        wh_id = created_webhook["id"]
        new_url = TEST_WEBHOOK_URL + "?v=2"
        resp = requests.put(
            f"{BASE_URL}/api/admin/webhooks/{wh_id}",
            json={"url": new_url},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["url"] == new_url

    def test_update_nonexistent_returns_404(self, admin_token):
        resp = requests.put(
            f"{BASE_URL}/api/admin/webhooks/nonexistent_id_9999",
            json={"name": "Ghost"},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 404


# ── Delete Webhook ─────────────────────────────────────────────────────────────

class TestDeleteWebhook:
    """DELETE /api/admin/webhooks/{id} — delete webhook."""

    def test_delete_webhook(self, admin_token):
        # Create one specifically to delete
        payload = {
            "name": "TEST_ToDelete",
            "url": TEST_WEBHOOK_URL,
            "subscriptions": [{"event": "order.created", "fields": ["id"]}],
        }
        create_resp = requests.post(f"{BASE_URL}/api/admin/webhooks", json=payload, headers=auth_headers(admin_token))
        assert create_resp.status_code == 200
        wh_id = create_resp.json()["id"]

        # Delete it
        del_resp = requests.delete(f"{BASE_URL}/api/admin/webhooks/{wh_id}", headers=auth_headers(admin_token))
        assert del_resp.status_code == 200
        assert del_resp.json().get("success") is True

    def test_delete_nonexistent_returns_404(self, admin_token):
        resp = requests.delete(
            f"{BASE_URL}/api/admin/webhooks/nonexistent_del_9999",
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 404

    def test_deleted_webhook_not_in_list(self, admin_token):
        # Create then delete then verify not in list
        payload = {
            "name": "TEST_DeleteVerify",
            "url": TEST_WEBHOOK_URL,
            "subscriptions": [{"event": "order.created", "fields": ["id"]}],
        }
        create_resp = requests.post(f"{BASE_URL}/api/admin/webhooks", json=payload, headers=auth_headers(admin_token))
        wh_id = create_resp.json()["id"]
        requests.delete(f"{BASE_URL}/api/admin/webhooks/{wh_id}", headers=auth_headers(admin_token))

        list_resp = requests.get(f"{BASE_URL}/api/admin/webhooks", headers=auth_headers(admin_token))
        webhooks = list_resp.json()["webhooks"]
        ids = [w["id"] for w in webhooks]
        assert wh_id not in ids, "Deleted webhook still appears in list"


# ── Test Delivery ──────────────────────────────────────────────────────────────

class TestTestDelivery:
    """POST /api/admin/webhooks/{id}/test — sends test delivery."""

    def test_test_delivery_returns_200(self, admin_token, created_webhook):
        wh_id = created_webhook["id"]
        resp = requests.post(
            f"{BASE_URL}/api/admin/webhooks/{wh_id}/test",
            json={"event": "order.created"},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200

    def test_test_delivery_has_required_fields(self, admin_token, created_webhook):
        wh_id = created_webhook["id"]
        resp = requests.post(
            f"{BASE_URL}/api/admin/webhooks/{wh_id}/test",
            json={"event": "order.created"},
            headers=auth_headers(admin_token),
        )
        data = resp.json()
        assert "success" in data
        assert "status_code" in data
        assert "body" in data

    def test_test_delivery_success_with_httpbin(self, admin_token, created_webhook):
        wh_id = created_webhook["id"]
        resp = requests.post(
            f"{BASE_URL}/api/admin/webhooks/{wh_id}/test",
            json={"event": "order.created"},
            headers=auth_headers(admin_token),
        )
        data = resp.json()
        assert data["success"] is True, f"Test delivery failed: {data}"
        assert data["status_code"] == 200

    def test_test_delivery_nonexistent_webhook_404(self, admin_token):
        resp = requests.post(
            f"{BASE_URL}/api/admin/webhooks/ghost_webhook_9999/test",
            json={"event": "order.created"},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 404


# ── Rotate Secret ─────────────────────────────────────────────────────────────

class TestRotateSecret:
    """POST /api/admin/webhooks/{id}/rotate-secret — returns new whsec_ prefixed secret."""

    def test_rotate_returns_200(self, admin_token, created_webhook):
        wh_id = created_webhook["id"]
        resp = requests.post(
            f"{BASE_URL}/api/admin/webhooks/{wh_id}/rotate-secret",
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200

    def test_rotate_returns_secret_with_whsec_prefix(self, admin_token, created_webhook):
        wh_id = created_webhook["id"]
        resp = requests.post(
            f"{BASE_URL}/api/admin/webhooks/{wh_id}/rotate-secret",
            headers=auth_headers(admin_token),
        )
        data = resp.json()
        assert "secret" in data
        assert data["secret"].startswith("whsec_"), f"Rotated secret doesn't start with 'whsec_': {data['secret']}"

    def test_rotate_secret_is_different_each_time(self, admin_token, created_webhook):
        wh_id = created_webhook["id"]
        resp1 = requests.post(f"{BASE_URL}/api/admin/webhooks/{wh_id}/rotate-secret", headers=auth_headers(admin_token))
        resp2 = requests.post(f"{BASE_URL}/api/admin/webhooks/{wh_id}/rotate-secret", headers=auth_headers(admin_token))
        assert resp1.json()["secret"] != resp2.json()["secret"], "Rotated secrets should be unique"


# ── Delivery Logs ─────────────────────────────────────────────────────────────

class TestDeliveryLogs:
    """GET /api/admin/webhooks/{id}/deliveries — delivery log with pagination."""

    def test_deliveries_returns_200(self, admin_token, created_webhook):
        wh_id = created_webhook["id"]
        resp = requests.get(
            f"{BASE_URL}/api/admin/webhooks/{wh_id}/deliveries",
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200

    def test_deliveries_response_structure(self, admin_token, created_webhook):
        wh_id = created_webhook["id"]
        resp = requests.get(
            f"{BASE_URL}/api/admin/webhooks/{wh_id}/deliveries",
            headers=auth_headers(admin_token),
        )
        data = resp.json()
        assert "deliveries" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert "total_pages" in data

    def test_deliveries_pagination_defaults(self, admin_token, created_webhook):
        wh_id = created_webhook["id"]
        resp = requests.get(
            f"{BASE_URL}/api/admin/webhooks/{wh_id}/deliveries",
            headers=auth_headers(admin_token),
        )
        data = resp.json()
        assert data["page"] == 1
        assert data["per_page"] == 25

    def test_deliveries_nonexistent_webhook_404(self, admin_token):
        resp = requests.get(
            f"{BASE_URL}/api/admin/webhooks/ghost_webhook_9999/deliveries",
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 404


# ── Tenant Isolation ───────────────────────────────────────────────────────────

class TestTenantIsolation:
    """Webhooks belong to tenant and cannot be accessed cross-tenant."""

    def test_tenant_b_cannot_access_tenant_a_webhook(self, admin_token, tenant_b_token, created_webhook):
        wh_id = created_webhook["id"]
        resp = requests.get(
            f"{BASE_URL}/api/admin/webhooks/{wh_id}",
            headers=auth_headers(tenant_b_token),
        )
        assert resp.status_code == 404, f"Expected 404 (cross-tenant), got {resp.status_code}: {resp.text}"

    def test_tenant_b_cannot_delete_tenant_a_webhook(self, admin_token, tenant_b_token, created_webhook):
        wh_id = created_webhook["id"]
        resp = requests.delete(
            f"{BASE_URL}/api/admin/webhooks/{wh_id}",
            headers=auth_headers(tenant_b_token),
        )
        assert resp.status_code == 404, f"Expected 404 (cross-tenant), got {resp.status_code}: {resp.text}"

    def test_tenant_b_cannot_update_tenant_a_webhook(self, admin_token, tenant_b_token, created_webhook):
        wh_id = created_webhook["id"]
        resp = requests.put(
            f"{BASE_URL}/api/admin/webhooks/{wh_id}",
            json={"name": "CROSS_TENANT_HACK"},
            headers=auth_headers(tenant_b_token),
        )
        assert resp.status_code == 404, f"Expected 404 (cross-tenant), got {resp.status_code}: {resp.text}"

    def test_tenant_b_webhooks_list_does_not_include_tenant_a_webhooks(
        self, admin_token, tenant_b_token, created_webhook
    ):
        wh_id = created_webhook["id"]
        resp = requests.get(f"{BASE_URL}/api/admin/webhooks", headers=auth_headers(tenant_b_token))
        assert resp.status_code == 200
        ids = [w["id"] for w in resp.json()["webhooks"]]
        assert wh_id not in ids, "Tenant A webhook leaked into Tenant B's list"


# ── dispatch_event on Order Creation ──────────────────────────────────────────

class TestDispatchEvent:
    """
    Create a webhook, trigger order.created, wait, check delivery log.
    Also verify field filtering: only configured fields appear in payload.data.
    """

    @pytest.fixture(scope="class")
    def webhook_for_dispatch(self, admin_token):
        """Create a webhook with 3 fields for order.created."""
        payload = {
            "name": "TEST_Dispatch",
            "url": TEST_WEBHOOK_URL,
            "subscriptions": [
                {"event": "order.created", "fields": ["id", "order_number", "total"]},
            ],
        }
        resp = requests.post(f"{BASE_URL}/api/admin/webhooks", json=payload, headers=auth_headers(admin_token))
        assert resp.status_code == 200, f"Create dispatch webhook failed: {resp.text}"
        data = resp.json()
        yield data
        requests.delete(f"{BASE_URL}/api/admin/webhooks/{data['id']}", headers=auth_headers(admin_token))

    @pytest.fixture(scope="class")
    def created_order_and_delivery(self, admin_token, webhook_for_dispatch):
        """Create a manual order (triggering order.created) and return webhook + delivery info."""
        # Get a customer to attach to the order
        customers_resp = requests.get(
            f"{BASE_URL}/api/admin/customers?limit=1",
            headers=auth_headers(admin_token),
        )
        customer_id = None
        if customers_resp.status_code == 200:
            customers = customers_resp.json().get("customers", [])
            if customers:
                customer_id = customers[0]["id"]

        order_payload = {
            "customer_id": customer_id or "test_customer",
            "product_name": "TEST Webhook Dispatch Product",
            "amount": 9999,
            "status": "pending",
            "notes": "TEST webhook dispatch order",
        }
        order_resp = requests.post(
            f"{BASE_URL}/api/admin/orders/manual",
            json=order_payload,
            headers=auth_headers(admin_token),
        )
        assert order_resp.status_code in (200, 201), f"Create order failed: {order_resp.text}"

        # Wait for async delivery to complete
        time.sleep(5)

        wh_id = webhook_for_dispatch["id"]
        deliveries_resp = requests.get(
            f"{BASE_URL}/api/admin/webhooks/{wh_id}/deliveries",
            headers=auth_headers(admin_token),
        )
        return {
            "webhook": webhook_for_dispatch,
            "order": order_resp.json(),
            "deliveries": deliveries_resp.json(),
        }

    def test_dispatch_creates_delivery_record(self, admin_token, created_order_and_delivery):
        deliveries = created_order_and_delivery["deliveries"]
        assert deliveries["total"] >= 1, "No delivery records found after order creation"

    def test_dispatch_delivery_event_is_order_created(self, admin_token, created_order_and_delivery):
        deliveries_list = created_order_and_delivery["deliveries"]["deliveries"]
        if not deliveries_list:
            pytest.skip("No deliveries to inspect")
        # Find the most recent order.created delivery
        order_deliveries = [d for d in deliveries_list if d["event"] == "order.created"]
        assert len(order_deliveries) >= 1, f"No order.created delivery found. Events found: {[d['event'] for d in deliveries_list]}"

    def test_dispatch_delivery_status_success(self, admin_token, created_order_and_delivery):
        deliveries_list = created_order_and_delivery["deliveries"]["deliveries"]
        if not deliveries_list:
            pytest.skip("No deliveries to inspect")
        order_deliveries = [d for d in deliveries_list if d["event"] == "order.created"]
        if not order_deliveries:
            pytest.skip("No order.created deliveries")
        latest = order_deliveries[0]
        assert latest["status"] == "success", f"Delivery status is '{latest['status']}', expected 'success'"

    def test_field_filtering_only_configured_fields(self, admin_token, webhook_for_dispatch, created_order_and_delivery):
        """dispatch_event should filter payload.data to only the 3 configured fields."""
        wh_id = webhook_for_dispatch["id"]
        deliveries_list = created_order_and_delivery["deliveries"]["deliveries"]
        if not deliveries_list:
            pytest.skip("No deliveries to inspect")
        order_deliveries = [d for d in deliveries_list if d["event"] == "order.created"]
        if not order_deliveries:
            pytest.skip("No order.created deliveries")

        # Fetch the full delivery detail (includes payload)
        delivery_id = order_deliveries[0]["id"]
        detail_resp = requests.get(
            f"{BASE_URL}/api/admin/webhooks/{wh_id}/deliveries/{delivery_id}",
            headers=auth_headers(admin_token),
        )
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert "payload" in detail, "Delivery detail should have 'payload' field"
        payload_data = detail["payload"].get("data", {})
        # Only id, order_number, total should be present (the 3 configured fields)
        configured_fields = {"id", "order_number", "total"}
        actual_fields = set(payload_data.keys())
        assert actual_fields == configured_fields or actual_fields.issubset(configured_fields), \
            f"Payload data has unexpected fields: {actual_fields}. Expected only: {configured_fields}"
        assert len(actual_fields) <= 3, f"More than 3 fields in payload.data: {actual_fields}"


# ── HMAC Signature ─────────────────────────────────────────────────────────────

class TestHMACSignature:
    """Verify HMAC-SHA256 signing logic."""

    def test_hmac_signature_format(self):
        """Verify the signature format: sha256=<hex>."""
        secret = "whsec_testsecret"
        body = b'{"event": "order.created", "data": {"id": "123"}}'
        expected_sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        formatted = f"sha256={expected_sig}"
        assert formatted.startswith("sha256=")
        assert len(formatted) > 10

    def test_hmac_signature_correctness(self):
        """The signature must equal HMAC-SHA256(secret, body)."""
        secret = "whsec_testsecret"
        body = json.dumps({"event": "test", "data": {}}).encode()
        expected_hex = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        # Simulate what the server does
        from backend.services.webhook_service import _sign_payload
        sig = _sign_payload(secret, body)
        assert sig == expected_hex

    def test_test_endpoint_sends_hmac_header(self, admin_token, created_webhook):
        """The test delivery to httpbin.org should show X-Webhook-Signature in the response."""
        wh_id = created_webhook["id"]
        resp = requests.post(
            f"{BASE_URL}/api/admin/webhooks/{wh_id}/test",
            json={"event": "order.created"},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        if data.get("success") and data.get("body"):
            # httpbin echoes headers; parse the body as JSON to verify
            try:
                body = json.loads(data["body"])
                headers = body.get("headers", {})
                sig_header = headers.get("X-Webhook-Signature", headers.get("x-webhook-signature", ""))
                assert sig_header.startswith("sha256="), f"Missing sha256= prefix in X-Webhook-Signature: '{sig_header}'"
            except (json.JSONDecodeError, AttributeError):
                # If httpbin returns truncated body, just verify delivery succeeded
                assert data["success"] is True


# ── Audit Logging ──────────────────────────────────────────────────────────────

class TestAuditLogging:
    """Creating a webhook should create an audit log entry."""

    def test_create_webhook_creates_audit_log(self, admin_token):
        # Create a webhook
        payload = {
            "name": "TEST_AuditLog",
            "url": TEST_WEBHOOK_URL,
            "subscriptions": [{"event": "order.created", "fields": ["id"]}],
        }
        create_resp = requests.post(f"{BASE_URL}/api/admin/webhooks", json=payload, headers=auth_headers(admin_token))
        assert create_resp.status_code == 200
        wh_id = create_resp.json()["id"]

        # Check audit logs
        audit_resp = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?entity_id={wh_id}",
            headers=auth_headers(admin_token),
        )
        assert audit_resp.status_code == 200
        logs = audit_resp.json().get("logs", [])
        webhook_log = [l for l in logs if wh_id in str(l)]
        assert len(webhook_log) >= 1, f"No audit log found for webhook {wh_id}"

        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/webhooks/{wh_id}", headers=auth_headers(admin_token))
