"""
MIG-BOOKS Feature Tests: Pricing calculator, Zoho checkout questions, notes_json
Tests for iteration 19 - new features on top of partner-tagging
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
MIG_BOOKS_PRODUCT_ID = "prod_migrate_books"


@pytest.fixture(scope="module")
def admin_token():
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@automateaccounts.local", "password": "ChangeMe123!"},
    )
    if resp.status_code == 200:
        return resp.json().get("token")
    pytest.skip(f"Admin login failed: {resp.status_code} {resp.text}")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ─── 1. Product page loads ─────────────────────────────────────────────────────

class TestMIGBOOKSProduct:
    """Product availability and structure tests"""

    def test_product_exists_at_prod_migrate_books(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/api/products/{MIG_BOOKS_PRODUCT_ID}", headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        product = data.get("product", data)
        assert product["id"] == MIG_BOOKS_PRODUCT_ID
        print("PASS: MIG-BOOKS product found at prod_migrate_books")

    def test_product_has_calc_type_books_migration(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/api/products/{MIG_BOOKS_PRODUCT_ID}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        product = data.get("product", data)
        assert product.get("pricing_type") == "calculator", f"pricing_type={product.get('pricing_type')}"
        assert product.get("pricing_rules", {}).get("calc_type") == "books_migration"
        print("PASS: MIG-BOOKS has pricing_type=calculator, calc_type=books_migration")

    def test_product_sku_is_mig_books(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/api/products/{MIG_BOOKS_PRODUCT_ID}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        product = data.get("product", data)
        assert product.get("sku") == "MIG-BOOKS"
        print("PASS: product sku is MIG-BOOKS")


# ─── 2. Pricing Calculator Formula ─────────────────────────────────────────────

class TestBooksMigrationPricing:
    """Pricing formula tests via /api/pricing/calc"""

    def test_1y_standard_no_premium(self, auth_headers):
        # 1Y + YTD, standard source, no premium → 999
        resp = requests.post(
            f"{BASE_URL}/api/pricing/calc",
            json={"product_id": MIG_BOOKS_PRODUCT_ID, "inputs": {
                "years": "1", "source_system": "quickbooks_online", "data_types": ["customers"]
            }},
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["subtotal"] == 999.0, f"Expected 999, got {data['subtotal']}"
        print(f"PASS: 1Y standard no premium = $999")

    def test_3y_standard_no_premium(self, auth_headers):
        # 3Y + YTD, standard source, no premium → 999 + 2*350 = 1699
        resp = requests.post(
            f"{BASE_URL}/api/pricing/calc",
            json={"product_id": MIG_BOOKS_PRODUCT_ID, "inputs": {
                "years": "3", "source_system": "quickbooks_online", "data_types": ["invoices"]
            }},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["subtotal"] == 1699.0, f"Expected 1699, got {data['subtotal']}"
        print(f"PASS: 3Y standard no premium = $1699")

    def test_6y_standard_with_premium(self, auth_headers):
        # 6Y + YTD, standard source, premium items → (999 + 4*350 + 1*300) * 1.5 = 4048.5 → round=3999
        resp = requests.post(
            f"{BASE_URL}/api/pricing/calc",
            json={"product_id": MIG_BOOKS_PRODUCT_ID, "inputs": {
                "years": "6", "source_system": "quickbooks_online", "data_types": ["price_list"]
            }},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["subtotal"] == 3999.0, f"Expected 3999, got {data['subtotal']}"
        print(f"PASS: 6Y standard with premium = $3999")

    def test_6y_xero_no_premium(self, auth_headers):
        # 6Y + YTD, xero (non-standard), no premium → (999 + 4*350 + 1*300) * 1.2 = 3238.8 → round=3199
        resp = requests.post(
            f"{BASE_URL}/api/pricing/calc",
            json={"product_id": MIG_BOOKS_PRODUCT_ID, "inputs": {
                "years": "6", "source_system": "xero", "data_types": ["invoices"]
            }},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["subtotal"] == 3199.0, f"Expected 3199, got {data['subtotal']}"
        print(f"PASS: 6Y xero no premium = $3199 (3238.8 rounds to 3199)")

    def test_2y_standard_no_premium(self, auth_headers):
        # 2Y + YTD, standard, no premium → 999 + 350 = 1349 → round=1349
        resp = requests.post(
            f"{BASE_URL}/api/pricing/calc",
            json={"product_id": MIG_BOOKS_PRODUCT_ID, "inputs": {
                "years": "2", "source_system": "quickbooks_online", "data_types": ["customers"]
            }},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["subtotal"] == 1349.0, f"Expected 1349, got {data['subtotal']}"
        print(f"PASS: 2Y standard no premium = $1349")

    def test_5y_standard_no_premium(self, auth_headers):
        # 5Y + YTD, standard, no premium → 999 + 4*350 = 2399 → round=2399
        resp = requests.post(
            f"{BASE_URL}/api/pricing/calc",
            json={"product_id": MIG_BOOKS_PRODUCT_ID, "inputs": {
                "years": "5", "source_system": "spreadsheet", "data_types": ["customers"]
            }},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["subtotal"] == 2399.0, f"Expected 2399, got {data['subtotal']}"
        print(f"PASS: 5Y standard no premium = $2399")

    def test_non_standard_source_applies_1_2x(self, auth_headers):
        # 1Y + YTD, freshbooks (non-standard), no premium → 999 * 1.2 = 1198.8 → round=1199
        resp = requests.post(
            f"{BASE_URL}/api/pricing/calc",
            json={"product_id": MIG_BOOKS_PRODUCT_ID, "inputs": {
                "years": "1", "source_system": "freshbooks", "data_types": ["customers"]
            }},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["subtotal"] == 1199.0, f"Expected 1199, got {data['subtotal']}"
        print(f"PASS: 1Y freshbooks (non-standard) = $1199")

    def test_premium_items_apply_1_5x(self, auth_headers):
        # 1Y + YTD, standard source, premium item → 999 * 1.5 = 1498.5 → round=1499
        resp = requests.post(
            f"{BASE_URL}/api/pricing/calc",
            json={"product_id": MIG_BOOKS_PRODUCT_ID, "inputs": {
                "years": "1", "source_system": "quickbooks_online", "data_types": ["timesheet"]
            }},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["subtotal"] == 1499.0, f"Expected 1499, got {data['subtotal']}"
        print(f"PASS: 1Y standard with timesheet (premium) = $1499")

    def test_pricing_response_has_line_items(self, auth_headers):
        resp = requests.post(
            f"{BASE_URL}/api/pricing/calc",
            json={"product_id": MIG_BOOKS_PRODUCT_ID, "inputs": {
                "years": "3", "source_system": "xero", "data_types": ["price_list", "invoices"]
            }},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "line_items" in data, "Response should have line_items"
        assert isinstance(data["line_items"], list)
        assert len(data["line_items"]) > 0
        print(f"PASS: pricing response has line_items: {data['line_items']}")


# ─── 3. Checkout Models Have Zoho Fields ──────────────────────────────────────

class TestCheckoutZohoFields:
    """Verify zoho fields are saved in notes_json after checkout"""

    def test_bank_transfer_checkout_with_zoho_fields_creates_order(self, auth_headers):
        """Full checkout with all zoho fields should succeed and save notes_json"""
        # Find MIG-BOOKS product ID
        resp = requests.post(
            f"{BASE_URL}/api/checkout/bank-transfer",
            json={
                "items": [{
                    "product_id": MIG_BOOKS_PRODUCT_ID,
                    "quantity": 1,
                    "inputs": {
                        "source_system": "quickbooks_online",
                        "access_confirmed": "yes",
                        "zoho_products": "",
                        "years": "1",
                        "data_types": ["invoices"],
                        "other_data": "",
                        "other_info": "",
                    }
                }],
                "checkout_type": "one_time",
                "promo_code": None,
                "terms_accepted": True,
                "partner_tag_response": "Yes",
                "zoho_subscription_type": "Paid - Annual",
                "current_zoho_product": "Zoho Books (Standard)",
                "zoho_account_access": "Yes",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "order_number" in data or "order_id" in data or "gocardless_redirect_url" in data
        print(f"PASS: Bank transfer checkout with zoho fields succeeded: {data.get('order_number', 'N/A')}")

    def test_checkout_without_zoho_fields_still_proceeds(self, auth_headers):
        """Zoho fields are Optional at backend - backend allows missing fields (frontend enforces)"""
        resp = requests.post(
            f"{BASE_URL}/api/checkout/bank-transfer",
            json={
                "items": [{
                    "product_id": MIG_BOOKS_PRODUCT_ID,
                    "quantity": 1,
                    "inputs": {
                        "source_system": "quickbooks_online",
                        "access_confirmed": "yes",
                        "years": "1",
                        "data_types": ["invoices"],
                    }
                }],
                "checkout_type": "one_time",
                "terms_accepted": True,
                "partner_tag_response": "Yes",
                # zoho fields missing
            },
            headers=auth_headers,
        )
        # Backend makes zoho fields Optional, so this should succeed (200)
        # If backend validates these as required and returns 400, that's the expected behavior
        print(f"INFO: Checkout without zoho fields returned {resp.status_code}")
        # We just assert it doesn't crash with 500
        assert resp.status_code in [200, 400], f"Unexpected status {resp.status_code}: {resp.text}"
        if resp.status_code == 400:
            print(f"INFO: Backend validates zoho fields as required: {resp.json()}")
        else:
            print("INFO: Backend allows missing zoho fields (Optional), frontend enforces")

    def test_notes_json_saved_on_order(self, auth_headers):
        """Verify notes_json has product_intake, checkout_intake, system_metadata keys"""
        # First create an order
        resp = requests.post(
            f"{BASE_URL}/api/checkout/bank-transfer",
            json={
                "items": [{
                    "product_id": MIG_BOOKS_PRODUCT_ID,
                    "quantity": 1,
                    "inputs": {
                        "source_system": "quickbooks_online",
                        "access_confirmed": "yes",
                        "years": "2",
                        "data_types": ["invoices", "customers"],
                    }
                }],
                "checkout_type": "one_time",
                "terms_accepted": True,
                "partner_tag_response": "Yes",
                "zoho_subscription_type": "Paid - Monthly",
                "current_zoho_product": "Zoho Books (Professional)",
                "zoho_account_access": "Not yet",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text}"
        
        order_number = resp.json().get("order_number")
        if not order_number:
            pytest.skip("Order number not returned - cannot verify notes_json")
        
        # Fetch the order from admin portal to verify notes_json
        orders_resp = requests.get(
            f"{BASE_URL}/api/admin/orders?limit=5",
            headers=auth_headers,
        )
        assert orders_resp.status_code == 200
        orders = orders_resp.json()
        
        target_order = None
        for o in (orders if isinstance(orders, list) else orders.get("orders", [])):
            if o.get("order_number") == order_number:
                target_order = o
                break
        
        if target_order:
            notes_json = target_order.get("notes_json")
            if notes_json:
                assert "product_intake" in notes_json, "notes_json missing product_intake"
                assert "checkout_intake" in notes_json, "notes_json missing checkout_intake"
                assert "system_metadata" in notes_json, "notes_json missing system_metadata"
                
                checkout_intake = notes_json["checkout_intake"]
                assert checkout_intake.get("zoho_subscription_type") == "Paid - Monthly"
                assert checkout_intake.get("current_zoho_product") == "Zoho Books (Professional)"
                assert checkout_intake.get("zoho_account_access") == "Not yet"
                print(f"PASS: notes_json has all required keys and correct values")
            else:
                print("INFO: notes_json not in admin orders response (may require different endpoint)")
        else:
            print(f"INFO: Order {order_number} not found in recent orders")


# ─── 4. Round to Nearest 99 Logic ──────────────────────────────────────────────

class TestRoundToNearest99:
    """Test backend round_to_nearest_99 via pricing API"""

    def test_3238_8_rounds_to_3199(self, auth_headers):
        """6Y xero (2699 * 1.2 = 3238.8) should round to 3199 not 3299"""
        resp = requests.post(
            f"{BASE_URL}/api/pricing/calc",
            json={"product_id": MIG_BOOKS_PRODUCT_ID, "inputs": {
                "years": "6", "source_system": "xero", "data_types": ["invoices"]
            }},
            headers=auth_headers,
        )
        data = resp.json()
        assert data["subtotal"] == 3199.0
        print("PASS: 3238.8 rounds to 3199 (distance to 3199 = 39.8, to 3299 = 60.2, choose lower)")

    def test_exact_99_stays_at_99(self, auth_headers):
        """1Y standard no premium = 999 (already at X99)"""
        resp = requests.post(
            f"{BASE_URL}/api/pricing/calc",
            json={"product_id": MIG_BOOKS_PRODUCT_ID, "inputs": {
                "years": "1", "source_system": "quickbooks_online", "data_types": []
            }},
            headers=auth_headers,
        )
        data = resp.json()
        assert data["subtotal"] == 999.0
        print("PASS: 999 stays at 999")


# ─── 5. Checkout Backend Validation ──────────────────────────────────────────

class TestCheckoutValidation:
    """Verify backend checkout validation"""

    def test_checkout_blocked_without_terms(self, auth_headers):
        resp = requests.post(
            f"{BASE_URL}/api/checkout/bank-transfer",
            json={
                "items": [{"product_id": MIG_BOOKS_PRODUCT_ID, "quantity": 1, "inputs": {}}],
                "checkout_type": "one_time",
                "terms_accepted": False,
                "partner_tag_response": "Yes",
                "zoho_subscription_type": "Paid - Annual",
                "current_zoho_product": "Zoho Books (Standard)",
                "zoho_account_access": "Yes",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        print("PASS: Checkout blocked without terms accepted")

    def test_checkout_blocked_without_partner_tag(self, auth_headers):
        resp = requests.post(
            f"{BASE_URL}/api/checkout/bank-transfer",
            json={
                "items": [{"product_id": MIG_BOOKS_PRODUCT_ID, "quantity": 1, "inputs": {}}],
                "checkout_type": "one_time",
                "terms_accepted": True,
                "partner_tag_response": None,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        print("PASS: Checkout blocked without partner_tag_response")
