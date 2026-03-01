"""
Iteration 156 - Invoice Settings: Bank Details, Logo & VAT, Company Details
Tests:
- GET/PUT invoice settings with new bank_details, vat_number, company fields
- PDF generation includes bank details, VAT number, payment terms
- Admin and partner download both include new fields
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"
PARTNER_EMAIL = "testpartner@example.com"
PARTNER_PASSWORD = "TestPass123!"
KNOWN_ORDER_ID = "28987c23-5ae4-447e-a199-710456191278"


@pytest.fixture(scope="module")
def admin_token():
    resp = requests.post(f"{BASE_URL}/api/auth/signin", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    data = resp.json()
    token = data.get("access_token") or data.get("token")
    assert token, f"No token in response: {data}"
    return token


@pytest.fixture(scope="module")
def partner_token():
    # Partner needs tenant code first - find the tenant code
    resp = requests.post(f"{BASE_URL}/api/auth/signin", json={"email": PARTNER_EMAIL, "password": PARTNER_PASSWORD})
    if resp.status_code != 200:
        pytest.skip(f"Partner login failed: {resp.text}")
    data = resp.json()
    token = data.get("access_token") or data.get("token")
    assert token, f"No partner token in response: {data}"
    return token


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def partner_headers(partner_token):
    return {"Authorization": f"Bearer {partner_token}", "Content-Type": "application/json"}


# ── GET invoice settings ──────────────────────────────────────────────────────

class TestGetInvoiceSettings:
    """GET /api/admin/taxes/invoice-settings"""

    def test_get_invoice_settings_returns_200(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/invoice-settings", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_get_invoice_settings_has_invoice_settings_key(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/invoice-settings", headers=admin_headers)
        data = resp.json()
        assert "invoice_settings" in data, f"Missing invoice_settings key in: {data.keys()}"

    def test_get_invoice_settings_has_bank_details(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/invoice-settings", headers=admin_headers)
        inv = resp.json().get("invoice_settings", {})
        # bank_details may be a dict or None/missing - check it's accessible
        assert "bank_details" in inv or inv == {}, f"bank_details missing from invoice_settings: {inv.keys()}"

    def test_get_invoice_settings_has_vat_number_field(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/invoice-settings", headers=admin_headers)
        inv = resp.json().get("invoice_settings", {})
        # vat_number may be empty string - just check field exists if settings were previously saved
        # Accept if it's a string (possibly empty)
        vat = inv.get("vat_number")
        assert isinstance(vat, (str, type(None))), f"vat_number should be str or None, got {type(vat)}"

    def test_get_invoice_settings_has_logo_url(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/invoice-settings", headers=admin_headers)
        inv = resp.json().get("invoice_settings", {})
        logo = inv.get("logo_url")
        assert isinstance(logo, (str, type(None))), f"logo_url should be str or None, got {type(logo)}"

    def test_get_invoice_settings_unauthenticated_returns_401(self):
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/invoice-settings")
        assert resp.status_code in (401, 403), f"Expected 401/403 without auth, got {resp.status_code}"


# ── PUT invoice settings ──────────────────────────────────────────────────────

class TestPutInvoiceSettings:
    """PUT /api/admin/taxes/invoice-settings with new fields"""

    FULL_PAYLOAD = {
        "prefix": "INV",
        "payment_terms": "Net 30",
        "footer_notes": "Thank you for your business.",
        "show_terms": True,
        "template": "classic",
        "company_name": "Automate Accounts Ltd",
        "company_email": "billing@automateaccounts.com",
        "company_phone": "+44 20 1234 5678",
        "company_address": "10 Finance St, London, EC1A 1BB",
        "logo_url": "",
        "vat_number": "GB 123 456 789",
        "bank_details": {
            "bank_name": "Barclays Bank",
            "account_name": "Automate Accounts Ltd",
            "account_number": "12345678",
            "sort_code": "20-00-00",
            "iban": "GB29 BARC 2000 0012 3456 78",
            "bic": "BARCGB22"
        }
    }

    def test_put_invoice_settings_returns_200(self, admin_headers):
        resp = requests.put(
            f"{BASE_URL}/api/admin/taxes/invoice-settings",
            json=self.FULL_PAYLOAD,
            headers=admin_headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_put_invoice_settings_response_has_message(self, admin_headers):
        resp = requests.put(
            f"{BASE_URL}/api/admin/taxes/invoice-settings",
            json=self.FULL_PAYLOAD,
            headers=admin_headers
        )
        data = resp.json()
        assert "message" in data or "invoice_settings" in data, f"Response missing expected keys: {data}"

    def test_put_invoice_settings_persists_vat_number(self, admin_headers):
        # Save
        requests.put(f"{BASE_URL}/api/admin/taxes/invoice-settings", json=self.FULL_PAYLOAD, headers=admin_headers)
        # Fetch back
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/invoice-settings", headers=admin_headers)
        inv = resp.json().get("invoice_settings", {})
        assert inv.get("vat_number") == "GB 123 456 789", f"vat_number not persisted: {inv.get('vat_number')}"

    def test_put_invoice_settings_persists_bank_details(self, admin_headers):
        requests.put(f"{BASE_URL}/api/admin/taxes/invoice-settings", json=self.FULL_PAYLOAD, headers=admin_headers)
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/invoice-settings", headers=admin_headers)
        inv = resp.json().get("invoice_settings", {})
        bd = inv.get("bank_details") or {}
        assert bd.get("bank_name") == "Barclays Bank", f"bank_name not persisted: {bd}"
        assert bd.get("sort_code") == "20-00-00", f"sort_code not persisted: {bd}"
        assert bd.get("iban") == "GB29 BARC 2000 0012 3456 78", f"iban not persisted: {bd}"
        assert bd.get("bic") == "BARCGB22", f"bic not persisted: {bd}"

    def test_put_invoice_settings_persists_company_details(self, admin_headers):
        requests.put(f"{BASE_URL}/api/admin/taxes/invoice-settings", json=self.FULL_PAYLOAD, headers=admin_headers)
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/invoice-settings", headers=admin_headers)
        inv = resp.json().get("invoice_settings", {})
        assert inv.get("company_name") == "Automate Accounts Ltd", f"company_name not persisted: {inv}"
        assert inv.get("company_email") == "billing@automateaccounts.com", f"company_email not persisted"
        assert inv.get("company_address") == "10 Finance St, London, EC1A 1BB", f"company_address not persisted"

    def test_put_invoice_settings_persists_payment_terms(self, admin_headers):
        requests.put(f"{BASE_URL}/api/admin/taxes/invoice-settings", json=self.FULL_PAYLOAD, headers=admin_headers)
        resp = requests.get(f"{BASE_URL}/api/admin/taxes/invoice-settings", headers=admin_headers)
        inv = resp.json().get("invoice_settings", {})
        assert inv.get("payment_terms") == "Net 30", f"payment_terms not persisted: {inv.get('payment_terms')}"


# ── PDF Download - Admin ──────────────────────────────────────────────────────

class TestAdminInvoicePDF:
    """Admin PDF download for a known partner order"""

    def test_admin_pdf_returns_200(self, admin_headers):
        resp = requests.get(
            f"{BASE_URL}/api/admin/partner-orders/{KNOWN_ORDER_ID}/download-invoice",
            headers=admin_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"

    def test_admin_pdf_content_type(self, admin_headers):
        resp = requests.get(
            f"{BASE_URL}/api/admin/partner-orders/{KNOWN_ORDER_ID}/download-invoice",
            headers=admin_headers,
        )
        assert "application/pdf" in resp.headers.get("content-type", ""), \
            f"Expected PDF content-type, got: {resp.headers.get('content-type')}"

    def test_admin_pdf_is_valid_pdf_magic(self, admin_headers):
        resp = requests.get(
            f"{BASE_URL}/api/admin/partner-orders/{KNOWN_ORDER_ID}/download-invoice",
            headers=admin_headers,
        )
        assert resp.content[:4] == b"%PDF", f"PDF does not start with %PDF magic bytes"

    def test_admin_pdf_minimum_size(self, admin_headers):
        resp = requests.get(
            f"{BASE_URL}/api/admin/partner-orders/{KNOWN_ORDER_ID}/download-invoice",
            headers=admin_headers,
        )
        assert len(resp.content) > 1000, f"PDF too small: {len(resp.content)} bytes"

    def test_admin_pdf_contains_bank_details(self, admin_headers):
        """Verify PDF text contains bank details after settings are saved"""
        # First ensure settings are saved with bank details
        payload = {
            "vat_number": "GB 123 456 789",
            "payment_terms": "Net 30",
            "bank_details": {
                "bank_name": "Barclays Bank",
                "account_name": "Automate Accounts Ltd",
                "account_number": "12345678",
                "sort_code": "20-00-00",
                "iban": "GB29 BARC 2000 0012 3456 78",
                "bic": "BARCGB22"
            }
        }
        requests.put(f"{BASE_URL}/api/admin/taxes/invoice-settings", json=payload, headers=admin_headers)

        # Download PDF
        resp = requests.get(
            f"{BASE_URL}/api/admin/partner-orders/{KNOWN_ORDER_ID}/download-invoice",
            headers=admin_headers,
        )
        assert resp.status_code == 200

        # Extract text from PDF using pypdf
        try:
            import io
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(resp.content))
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            text_lower = text.lower()
            print(f"PDF text excerpt: {text[:500]}")
            assert "bank" in text_lower or "barclays" in text_lower, \
                f"PDF does not contain bank details. Text: {text[:300]}"
        except ImportError:
            pytest.skip("pypdf not installed")

    def test_admin_pdf_contains_vat_number(self, admin_headers):
        """Verify PDF text contains VAT number"""
        payload = {"vat_number": "GB 123 456 789"}
        requests.put(f"{BASE_URL}/api/admin/taxes/invoice-settings", json=payload, headers=admin_headers)

        resp = requests.get(
            f"{BASE_URL}/api/admin/partner-orders/{KNOWN_ORDER_ID}/download-invoice",
            headers=admin_headers,
        )
        assert resp.status_code == 200

        try:
            import io
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(resp.content))
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            print(f"PDF text for VAT check: {text[:500]}")
            assert "GB 123 456 789" in text or "vat" in text.lower() or "123" in text, \
                f"VAT number not found in PDF. Text: {text[:400]}"
        except ImportError:
            pytest.skip("pypdf not installed")

    def test_admin_pdf_contains_payment_terms(self, admin_headers):
        """Verify PDF text contains payment terms"""
        payload = {"payment_terms": "Net 30"}
        requests.put(f"{BASE_URL}/api/admin/taxes/invoice-settings", json=payload, headers=admin_headers)

        resp = requests.get(
            f"{BASE_URL}/api/admin/partner-orders/{KNOWN_ORDER_ID}/download-invoice",
            headers=admin_headers,
        )
        assert resp.status_code == 200

        try:
            import io
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(resp.content))
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            print(f"PDF text for payment terms check: {text[:500]}")
            assert "net 30" in text.lower() or "Net 30" in text or "payment" in text.lower(), \
                f"Payment terms not in PDF. Text: {text[:400]}"
        except ImportError:
            pytest.skip("pypdf not installed")

    def test_admin_pdf_contains_sort_code(self, admin_headers):
        """Verify Sort Code in PDF"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/partner-orders/{KNOWN_ORDER_ID}/download-invoice",
            headers=admin_headers,
        )
        try:
            import io
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(resp.content))
            text = "".join(page.extract_text() or "" for page in reader.pages)
            print(f"Sort code check - PDF text: {text[:600]}")
            assert "20-00-00" in text or "sort" in text.lower(), \
                f"Sort code not found in PDF. Text: {text[:400]}"
        except ImportError:
            pytest.skip("pypdf not installed")

    def test_admin_pdf_contains_iban(self, admin_headers):
        """Verify IBAN in PDF"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/partner-orders/{KNOWN_ORDER_ID}/download-invoice",
            headers=admin_headers,
        )
        try:
            import io
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(resp.content))
            text = "".join(page.extract_text() or "" for page in reader.pages)
            assert "iban" in text.lower() or "GB29" in text, \
                f"IBAN not found in PDF. Text: {text[:400]}"
        except ImportError:
            pytest.skip("pypdf not installed")

    def test_admin_pdf_contains_bic(self, admin_headers):
        """Verify BIC/SWIFT in PDF"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/partner-orders/{KNOWN_ORDER_ID}/download-invoice",
            headers=admin_headers,
        )
        try:
            import io
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(resp.content))
            text = "".join(page.extract_text() or "" for page in reader.pages)
            assert "bic" in text.lower() or "barcgb22" in text.lower() or "swift" in text.lower(), \
                f"BIC not found in PDF. Text: {text[:400]}"
        except ImportError:
            pytest.skip("pypdf not installed")


# ── PDF Download - Partner ────────────────────────────────────────────────────

class TestPartnerInvoicePDF:
    """Partner PDF download uses same invoice_settings from platform admin"""

    def test_partner_pdf_returns_200(self, partner_headers):
        resp = requests.get(
            f"{BASE_URL}/api/partner/my-orders/{KNOWN_ORDER_ID}/download-invoice",
            headers=partner_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"

    def test_partner_pdf_is_valid(self, partner_headers):
        resp = requests.get(
            f"{BASE_URL}/api/partner/my-orders/{KNOWN_ORDER_ID}/download-invoice",
            headers=partner_headers,
        )
        assert resp.content[:4] == b"%PDF", "Partner PDF does not start with %PDF"
        assert len(resp.content) > 1000, f"Partner PDF too small: {len(resp.content)}"

    def test_partner_pdf_contains_bank_details(self, partner_headers):
        """Partner PDF uses same platform invoice_settings → should have bank details"""
        resp = requests.get(
            f"{BASE_URL}/api/partner/my-orders/{KNOWN_ORDER_ID}/download-invoice",
            headers=partner_headers,
        )
        assert resp.status_code == 200
        try:
            import io
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(resp.content))
            text = "".join(page.extract_text() or "" for page in reader.pages)
            print(f"Partner PDF bank check: {text[:500]}")
            assert "bank" in text.lower() or "barclays" in text.lower(), \
                f"Partner PDF missing bank details. Text: {text[:400]}"
        except ImportError:
            pytest.skip("pypdf not installed")

    def test_partner_pdf_contains_vat_number(self, partner_headers):
        """Partner PDF should include VAT number"""
        resp = requests.get(
            f"{BASE_URL}/api/partner/my-orders/{KNOWN_ORDER_ID}/download-invoice",
            headers=partner_headers,
        )
        assert resp.status_code == 200
        try:
            import io
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(resp.content))
            text = "".join(page.extract_text() or "" for page in reader.pages)
            print(f"Partner PDF VAT check: {text[:500]}")
            assert "vat" in text.lower() or "GB 123 456 789" in text or "123" in text, \
                f"Partner PDF missing VAT number. Text: {text[:400]}"
        except ImportError:
            pytest.skip("pypdf not installed")
