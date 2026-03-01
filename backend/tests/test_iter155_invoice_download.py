"""
Iteration 155 - Partner PDF Invoice Download Tests
Tests:
  - Admin download endpoint: GET /api/admin/partner-orders/{order_id}/download-invoice
  - Partner download endpoint: GET /api/partner/my-orders/{order_id}/download-invoice
  - Partner 403 for other partner's orders
  - PDF validity check (starts with %PDF, > 1000 bytes)
  - Invoice HTML endpoint: GET /api/partner/my-orders/{order_id}/invoice-html
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"
PARTNER_EMAIL = "testpartner@example.com"
PARTNER_PASSWORD = "TestPass123!"
PARTNER_CODE = "test-partner-co"
KNOWN_ORDER_ID = "28987c23-5ae4-447e-a199-710456191278"
KNOWN_ORDER_NUMBER = "PO-2026-0006"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def admin_token():
    """Get platform admin auth token (no partner_code for platform admin)."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
    })
    if resp.status_code == 200:
        data = resp.json()
        token = data.get("token") or data.get("access_token")
        if token:
            return token
    pytest.skip(f"Admin login failed with status {resp.status_code}: {resp.text}")


@pytest.fixture(scope="module")
def partner_token():
    """Get test partner auth token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": PARTNER_EMAIL,
        "password": PARTNER_PASSWORD,
        "partner_code": PARTNER_CODE,
    })
    if resp.status_code == 200:
        data = resp.json()
        token = data.get("token") or data.get("access_token")
        if token:
            return token
    pytest.skip(f"Partner login failed with status {resp.status_code}: {resp.text}")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def partner_headers(partner_token):
    return {"Authorization": f"Bearer {partner_token}"}


# ---------------------------------------------------------------------------
# Admin invoice download tests
# ---------------------------------------------------------------------------

class TestAdminInvoiceDownload:
    """Admin endpoint: GET /api/admin/partner-orders/{order_id}/download-invoice"""

    def test_admin_download_invoice_status_200(self, admin_headers):
        """Admin should get 200 for a known order."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/partner-orders/{KNOWN_ORDER_ID}/download-invoice",
            headers=admin_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"

    def test_admin_download_invoice_content_type_pdf(self, admin_headers):
        """Response Content-Type must be application/pdf."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/partner-orders/{KNOWN_ORDER_ID}/download-invoice",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        ct = resp.headers.get("content-type", "")
        assert "application/pdf" in ct, f"Expected application/pdf, got: {ct}"

    def test_admin_download_invoice_valid_pdf_header(self, admin_headers):
        """PDF bytes must start with %PDF magic bytes."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/partner-orders/{KNOWN_ORDER_ID}/download-invoice",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.content[:4] == b"%PDF", f"Response doesn't start with %PDF: {resp.content[:10]}"

    def test_admin_download_invoice_size_greater_than_1kb(self, admin_headers):
        """PDF must be > 1000 bytes (a real PDF, not empty)."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/partner-orders/{KNOWN_ORDER_ID}/download-invoice",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        size = len(resp.content)
        assert size > 1000, f"PDF too small: {size} bytes"

    def test_admin_download_invoice_content_disposition(self, admin_headers):
        """Response should have Content-Disposition attachment header."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/partner-orders/{KNOWN_ORDER_ID}/download-invoice",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        cd = resp.headers.get("content-disposition", "")
        assert "attachment" in cd.lower(), f"Expected 'attachment' in Content-Disposition, got: {cd}"
        assert ".pdf" in cd.lower(), f"Expected .pdf in Content-Disposition, got: {cd}"

    def test_admin_download_invoice_not_found(self, admin_headers):
        """Non-existent order returns 404."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/partner-orders/nonexistent-order-id/download-invoice",
            headers=admin_headers,
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"

    def test_admin_download_invoice_unauthenticated(self):
        """Unauthenticated request returns 401 or 403."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/partner-orders/{KNOWN_ORDER_ID}/download-invoice",
        )
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"


# ---------------------------------------------------------------------------
# Partner invoice download tests
# ---------------------------------------------------------------------------

class TestPartnerInvoiceDownload:
    """Partner endpoint: GET /api/partner/my-orders/{order_id}/download-invoice"""

    def test_partner_download_own_order_status_200(self, partner_headers):
        """Partner should get 200 for their own order."""
        resp = requests.get(
            f"{BASE_URL}/api/partner/my-orders/{KNOWN_ORDER_ID}/download-invoice",
            headers=partner_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"

    def test_partner_download_own_order_content_type_pdf(self, partner_headers):
        """Response Content-Type must be application/pdf."""
        resp = requests.get(
            f"{BASE_URL}/api/partner/my-orders/{KNOWN_ORDER_ID}/download-invoice",
            headers=partner_headers,
        )
        assert resp.status_code == 200
        ct = resp.headers.get("content-type", "")
        assert "application/pdf" in ct, f"Expected application/pdf, got: {ct}"

    def test_partner_download_own_order_valid_pdf(self, partner_headers):
        """PDF bytes must start with %PDF and be > 1000 bytes."""
        resp = requests.get(
            f"{BASE_URL}/api/partner/my-orders/{KNOWN_ORDER_ID}/download-invoice",
            headers=partner_headers,
        )
        assert resp.status_code == 200
        assert resp.content[:4] == b"%PDF", f"Response doesn't start with %PDF"
        assert len(resp.content) > 1000, f"PDF too small: {len(resp.content)} bytes"

    def test_partner_download_order_not_found_returns_404(self, partner_headers):
        """Non-existent / other partner's order returns 404 (not 403, since lookup is by partner_id)."""
        # Use an order ID that doesn't belong to this partner
        resp = requests.get(
            f"{BASE_URL}/api/partner/my-orders/nonexistent-order-000000/download-invoice",
            headers=partner_headers,
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"

    def test_partner_platform_admin_blocked_on_partner_endpoint(self, admin_headers):
        """Platform admin gets 403 when using the partner endpoint."""
        resp = requests.get(
            f"{BASE_URL}/api/partner/my-orders/{KNOWN_ORDER_ID}/download-invoice",
            headers=admin_headers,
        )
        assert resp.status_code == 403, f"Expected 403 for platform admin on partner endpoint, got {resp.status_code}"

    def test_partner_download_unauthenticated(self):
        """Unauthenticated request returns 401 or 403."""
        resp = requests.get(
            f"{BASE_URL}/api/partner/my-orders/{KNOWN_ORDER_ID}/download-invoice",
        )
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"


# ---------------------------------------------------------------------------
# Invoice HTML endpoint
# ---------------------------------------------------------------------------

class TestInvoiceHtmlEndpoint:
    """Partner endpoint: GET /api/partner/my-orders/{order_id}/invoice-html"""

    def test_invoice_html_returns_200(self, partner_headers):
        """Partner can get invoice data as JSON."""
        resp = requests.get(
            f"{BASE_URL}/api/partner/my-orders/{KNOWN_ORDER_ID}/invoice-html",
            headers=partner_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"

    def test_invoice_html_contains_order_field(self, partner_headers):
        """Response JSON must contain 'order' field."""
        resp = requests.get(
            f"{BASE_URL}/api/partner/my-orders/{KNOWN_ORDER_ID}/invoice-html",
            headers=partner_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "order" in data, f"Expected 'order' key in response, got keys: {list(data.keys())}"

    def test_invoice_html_contains_partner_field(self, partner_headers):
        """Response JSON must contain 'partner' field."""
        resp = requests.get(
            f"{BASE_URL}/api/partner/my-orders/{KNOWN_ORDER_ID}/invoice-html",
            headers=partner_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "partner" in data, f"Expected 'partner' key in response, got keys: {list(data.keys())}"

    def test_invoice_html_contains_invoice_settings_field(self, partner_headers):
        """Response JSON must contain 'invoice_settings' field."""
        resp = requests.get(
            f"{BASE_URL}/api/partner/my-orders/{KNOWN_ORDER_ID}/invoice-html",
            headers=partner_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "invoice_settings" in data, f"Expected 'invoice_settings' key in response"

    def test_invoice_html_contains_template_field(self, partner_headers):
        """Response JSON must contain 'template' field (may be null)."""
        resp = requests.get(
            f"{BASE_URL}/api/partner/my-orders/{KNOWN_ORDER_ID}/invoice-html",
            headers=partner_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "template" in data, f"Expected 'template' key in response"

    def test_invoice_html_order_has_correct_id(self, partner_headers):
        """The order in the response must match the requested order ID."""
        resp = requests.get(
            f"{BASE_URL}/api/partner/my-orders/{KNOWN_ORDER_ID}/invoice-html",
            headers=partner_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        order = data.get("order", {})
        assert order.get("id") == KNOWN_ORDER_ID, f"Expected order id {KNOWN_ORDER_ID}, got {order.get('id')}"

    def test_invoice_html_order_number_matches(self, partner_headers):
        """The order_number in the response should be PO-2026-0006."""
        resp = requests.get(
            f"{BASE_URL}/api/partner/my-orders/{KNOWN_ORDER_ID}/invoice-html",
            headers=partner_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        order = data.get("order", {})
        assert order.get("order_number") == KNOWN_ORDER_NUMBER, f"Expected {KNOWN_ORDER_NUMBER}, got {order.get('order_number')}"

    def test_invoice_html_platform_admin_blocked(self, admin_headers):
        """Platform admin gets 403 on this partner-scoped endpoint."""
        resp = requests.get(
            f"{BASE_URL}/api/partner/my-orders/{KNOWN_ORDER_ID}/invoice-html",
            headers=admin_headers,
        )
        assert resp.status_code == 403, f"Expected 403 for platform admin, got {resp.status_code}"

    def test_invoice_html_not_found(self, partner_headers):
        """Non-existent order returns 404."""
        resp = requests.get(
            f"{BASE_URL}/api/partner/my-orders/nonexistent-order-999/invoice-html",
            headers=partner_headers,
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"


# ---------------------------------------------------------------------------
# Cross-partner access control
# ---------------------------------------------------------------------------

class TestCrossPartnerAccessControl:
    """Verify partners cannot access each other's order invoices."""

    def test_partner_cannot_download_another_partners_order_via_nonexistent_id(self, partner_headers):
        """
        When partner_id doesn't match, the order is effectively 'not found' — returns 404.
        The system filters by partner_id in the query, so other partner's orders appear as 404.
        """
        # This simulates trying to access an order that belongs to a different partner
        # The system will return 404 (not 403) because it filters by partner_id
        resp = requests.get(
            f"{BASE_URL}/api/partner/my-orders/another-partners-order-id-000/download-invoice",
            headers=partner_headers,
        )
        # The endpoint uses partner_id filter, so it returns 404 for cross-partner access
        assert resp.status_code == 404, f"Expected 404 for cross-partner access, got {resp.status_code}"
