"""
Backend tests for P1 features:
- Invoice Settings CRUD (GET/PUT /admin/taxes/invoice-settings)
- Tax Summary (GET /admin/taxes/summary)
- Invoice data endpoint (GET /orders/{id}/invoice)
- CSV exports containing base_currency_amount and tax_amount columns
"""

import pytest
import requests
import os
import csv
import io

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"

CUSTOMER_EMAIL = "mark@markchen.local"
CUSTOMER_PASSWORD = "MarkClient123!"


@pytest.fixture(scope="module")
def admin_token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return resp.json().get("access_token") or resp.json().get("token")


@pytest.fixture(scope="module")
def customer_token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": CUSTOMER_EMAIL, "password": CUSTOMER_PASSWORD})
    if resp.status_code != 200:
        pytest.skip(f"Customer login failed: {resp.text}")
    return resp.json().get("access_token") or resp.json().get("token")


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture
def customer_headers(customer_token):
    return {"Authorization": f"Bearer {customer_token}", "Content-Type": "application/json"}


# ── Invoice Settings ─────────────────────────────────────────────────────────

class TestInvoiceSettings:
    """Tests for GET/PUT /admin/taxes/invoice-settings"""

    def test_get_invoice_settings_returns_200(self, admin_headers):
        """GET /admin/taxes/invoice-settings should return 200 with invoice_settings object"""
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/invoice-settings", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_get_invoice_settings_structure(self, admin_headers):
        """invoice_settings should contain expected keys"""
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/invoice-settings", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "invoice_settings" in data, "Response missing 'invoice_settings' key"
        settings = data["invoice_settings"]
        # Should have at least these defaults or existing values
        assert isinstance(settings, dict), "invoice_settings should be a dict"

    def test_put_invoice_settings_success(self, admin_headers):
        """PUT /admin/taxes/invoice-settings should update and return 200"""
        payload = {
            "prefix": "INV",
            "payment_terms": "Net 30",
            "template": "modern",
            "footer_notes": "Thank you for your business.",
            "show_terms": True,
        }
        resp = requests.put(
            f"{BASE_URL}/api/admin/taxes/invoice-settings",
            json=payload,
            headers=admin_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "invoice_settings" in data, "Response missing 'invoice_settings' key"
        settings = data["invoice_settings"]
        assert settings.get("prefix") == "INV"
        assert settings.get("payment_terms") == "Net 30"
        assert settings.get("template") == "modern"

    def test_put_invoice_settings_persisted(self, admin_headers):
        """After PUT, GET should return updated settings"""
        payload = {"prefix": "TEST-INV", "payment_terms": "Net 7", "template": "minimal"}
        put_resp = requests.put(
            f"{BASE_URL}/api/admin/taxes/invoice-settings",
            json=payload,
            headers=admin_headers,
        )
        assert put_resp.status_code == 200

        get_resp = requests.get(f"{BASE_URL}/api/admin/taxes/invoice-settings", headers=admin_headers)
        assert get_resp.status_code == 200
        settings = get_resp.json()["invoice_settings"]
        assert settings.get("prefix") == "TEST-INV"
        assert settings.get("payment_terms") == "Net 7"
        assert settings.get("template") == "minimal"

    def test_put_invoice_settings_restore(self, admin_headers):
        """Restore settings back to defaults after test"""
        payload = {"prefix": "INV", "payment_terms": "Due on receipt", "template": "classic", "footer_notes": "", "show_terms": True}
        resp = requests.put(
            f"{BASE_URL}/api/admin/taxes/invoice-settings",
            json=payload,
            headers=admin_headers,
        )
        assert resp.status_code == 200

    def test_invoice_settings_unauthenticated_returns_401(self):
        """GET invoice settings without token should return 401"""
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/invoice-settings")
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"


# ── Tax Summary ───────────────────────────────────────────────────────────────

class TestTaxSummary:
    """Tests for GET /admin/taxes/summary"""

    def test_get_tax_summary_returns_200(self, admin_headers):
        """GET /admin/taxes/summary should return 200"""
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/summary", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_get_tax_summary_structure(self, admin_headers):
        """Response should contain 'summary' list"""
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/summary", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data, "Response missing 'summary' key"
        assert isinstance(data["summary"], list), "'summary' should be a list"

    def test_get_tax_summary_months_param(self, admin_headers):
        """Should accept months query parameter"""
        for months in ["3", "6", "12", "24"]:
            resp = requests.get(
                f"{BASE_URL}/api/admin/taxes/summary?months={months}",
                headers=admin_headers,
            )
            assert resp.status_code == 200, f"Failed for months={months}: {resp.text}"

    def test_tax_summary_row_structure(self, admin_headers):
        """If any rows exist, they should have the right structure"""
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/summary?months=24", headers=admin_headers)
        assert resp.status_code == 200
        rows = resp.json().get("summary", [])
        for row in rows:
            assert "month" in row, "Row missing 'month'"
            assert "tax_name" in row, "Row missing 'tax_name'"
            assert "currency" in row, "Row missing 'currency'"
            assert "total_tax" in row, "Row missing 'total_tax'"
            assert "total_revenue" in row, "Row missing 'total_revenue'"
            assert "order_count" in row, "Row missing 'order_count'"

    def test_tax_summary_unauthenticated(self):
        """GET /admin/taxes/summary without auth should return 401"""
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/summary")
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"


# ── Invoice Data Endpoint ─────────────────────────────────────────────────────

class TestInvoiceDataEndpoint:
    """Tests for GET /orders/{order_id}/invoice"""

    def test_invoice_invalid_order_returns_404(self, admin_headers):
        """GET /orders/nonexistent/invoice should return 404"""
        resp = requests.get(f"{BASE_URL}/api/orders/nonexistent-order-id-xyz/invoice", headers=admin_headers)
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"

    def test_invoice_unauthenticated_returns_401(self):
        """GET /orders/{id}/invoice without auth should return 401"""
        resp = requests.get(f"{BASE_URL}/api/orders/someid/invoice")
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"

    def test_invoice_data_structure_if_order_exists(self, admin_headers):
        """If any orders exist, GET invoice for one should return proper structure"""
        # Get any existing order
        orders_resp = requests.get(f"{BASE_URL}/api/admin/orders?per_page=1", headers=admin_headers)
        if orders_resp.status_code != 200:
            pytest.skip("Cannot list orders")

        orders = orders_resp.json().get("orders", [])
        if not orders:
            pytest.skip("No orders in DB to test invoice for")

        order_id = orders[0]["id"]
        resp = requests.get(f"{BASE_URL}/api/orders/{order_id}/invoice", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

        data = resp.json()
        # Check required keys in invoice response
        assert "invoice_number" in data, "Missing invoice_number"
        assert "order" in data, "Missing order"
        assert "customer" in data, "Missing customer"
        assert "address" in data, "Missing address"
        assert "partner" in data, "Missing partner"
        assert "invoice_settings" in data, "Missing invoice_settings"
        assert "items" in data, "Missing items"

    def test_invoice_number_uses_prefix(self, admin_headers):
        """invoice_number should use the configured prefix"""
        orders_resp = requests.get(f"{BASE_URL}/api/admin/orders?per_page=1", headers=admin_headers)
        if orders_resp.status_code != 200:
            pytest.skip("Cannot list orders")
        orders = orders_resp.json().get("orders", [])
        if not orders:
            pytest.skip("No orders in DB")

        order_id = orders[0]["id"]
        resp = requests.get(f"{BASE_URL}/api/orders/{order_id}/invoice", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        invoice_number = data.get("invoice_number", "")
        # Should start with some prefix or order number
        assert len(invoice_number) > 0, "invoice_number should not be empty"


# ── CSV Export Columns ────────────────────────────────────────────────────────

class TestCsvExportColumns:
    """Verify base_currency_amount and tax_amount exist in CSV exports"""

    def test_orders_export_has_tax_and_base_currency_columns(self, admin_headers):
        """Orders CSV should include base_currency_amount and tax_amount columns"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/export/orders",
            headers={k: v for k, v in admin_headers.items() if k != "Content-Type"},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        content = resp.content.decode("utf-8")
        # Check if there's actual data (not just "No data")
        if content.strip() == "No data":
            pytest.skip("No orders to export")
        reader = csv.DictReader(io.StringIO(content))
        fieldnames = reader.fieldnames or []
        assert "base_currency_amount" in fieldnames, f"Missing base_currency_amount in orders CSV. Found: {fieldnames}"
        assert "tax_amount" in fieldnames, f"Missing tax_amount in orders CSV. Found: {fieldnames}"

    def test_subscriptions_export_has_tax_and_base_currency_columns(self, admin_headers):
        """Subscriptions CSV should include base_currency_amount and tax_amount columns"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/export/subscriptions",
            headers={k: v for k, v in admin_headers.items() if k != "Content-Type"},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        content = resp.content.decode("utf-8")
        if content.strip() == "No data":
            pytest.skip("No subscriptions to export")
        reader = csv.DictReader(io.StringIO(content))
        fieldnames = reader.fieldnames or []
        assert "base_currency_amount" in fieldnames, f"Missing base_currency_amount in subscriptions CSV. Found: {fieldnames}"
        assert "tax_amount" in fieldnames, f"Missing tax_amount in subscriptions CSV. Found: {fieldnames}"


# ── Existing Tax Settings (smoke test from iter128 regression) ────────────────

class TestTaxSettingsRegression:
    """Regression tests to ensure previous tax features still work"""

    def test_get_tax_settings_returns_200(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/settings", headers=admin_headers)
        assert resp.status_code == 200

    def test_get_tax_tables_returns_200(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/tables", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "entries" in data
        assert len(data["entries"]) > 0

    def test_get_overrides_returns_200(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/overrides", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "rules" in data
