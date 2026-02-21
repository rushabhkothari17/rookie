"""
Iteration 15 backend tests:
- Bank Transactions CRUD endpoints
- Subscription Contract End Date
- Product pricing complexity (COMPLEX with price shows Add to Cart logic)
- Zoho Books Express product check
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Admin credentials
ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"


@pytest.fixture(scope="module")
def admin_token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if resp.status_code == 200:
        return resp.json().get("token")
    pytest.skip(f"Admin auth failed: {resp.status_code} {resp.text}")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ============ BANK TRANSACTIONS TESTS ============

class TestBankTransactionsCRUD:
    """Bank Transactions full CRUD"""

    created_txn_id = None

    def test_list_bank_transactions(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/bank-transactions", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "transactions" in data
        assert isinstance(data["transactions"], list)
        print(f"[OK] List transactions: {len(data['transactions'])} found")

    def test_create_bank_transaction(self, admin_headers):
        payload = {
            "date": "2026-02-15",
            "source": "manual",
            "transaction_id": "TEST-001",
            "type": "payment",
            "amount": 500.0,
            "fees": 5.0,
            "currency": "USD",
            "status": "completed",
            "description": "Test payment iteration 15",
            "linked_order_id": "",
            "internal_notes": "Created by test suite",
        }
        resp = requests.post(f"{BASE_URL}/api/admin/bank-transactions", json=payload, headers=admin_headers)
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        data = resp.json()
        assert "transaction" in data
        txn = data["transaction"]
        assert txn["source"] == "manual"
        assert txn["amount"] == 500.0
        assert txn["fees"] == 5.0
        # Verify net amount = 500 - 5 = 495
        assert txn["net_amount"] == 495.0, f"Net amount should be 495, got {txn['net_amount']}"
        assert txn["status"] == "completed"
        assert txn["currency"] == "USD"
        assert "id" in txn
        TestBankTransactionsCRUD.created_txn_id = txn["id"]
        print(f"[OK] Created transaction id={txn['id']}, net_amount={txn['net_amount']}")

    def test_created_transaction_appears_in_list(self, admin_headers):
        assert TestBankTransactionsCRUD.created_txn_id, "No txn created yet"
        resp = requests.get(f"{BASE_URL}/api/admin/bank-transactions", headers=admin_headers)
        data = resp.json()
        ids = [t["id"] for t in data["transactions"]]
        assert TestBankTransactionsCRUD.created_txn_id in ids
        print(f"[OK] Created transaction appears in list")

    def test_filter_by_source(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/bank-transactions?source=manual", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        for txn in data["transactions"]:
            assert txn["source"] == "manual"
        print(f"[OK] Source filter: {len(data['transactions'])} manual transactions")

    def test_filter_by_status(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/bank-transactions?status=completed", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        for txn in data["transactions"]:
            assert txn["status"] == "completed"
        print(f"[OK] Status filter: {len(data['transactions'])} completed transactions")

    def test_filter_by_type(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/bank-transactions?type=payment", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        for txn in data["transactions"]:
            assert txn["type"] == "payment"
        print(f"[OK] Type filter: {len(data['transactions'])} payment transactions")

    def test_update_bank_transaction(self, admin_headers):
        assert TestBankTransactionsCRUD.created_txn_id, "No txn created yet"
        update_payload = {"description": "Updated test payment", "status": "completed"}
        resp = requests.put(
            f"{BASE_URL}/api/admin/bank-transactions/{TestBankTransactionsCRUD.created_txn_id}",
            json=update_payload,
            headers=admin_headers
        )
        assert resp.status_code == 200, f"Update failed: {resp.text}"
        data = resp.json()
        assert "transaction" in data
        assert data["transaction"]["description"] == "Updated test payment"
        print(f"[OK] Transaction updated")

    def test_get_transaction_logs(self, admin_headers):
        assert TestBankTransactionsCRUD.created_txn_id, "No txn created yet"
        resp = requests.get(
            f"{BASE_URL}/api/admin/bank-transactions/{TestBankTransactionsCRUD.created_txn_id}/logs",
            headers=admin_headers
        )
        assert resp.status_code == 200, f"Logs failed: {resp.text}"
        data = resp.json()
        assert "logs" in data
        assert isinstance(data["logs"], list)
        assert len(data["logs"]) >= 1  # At least the 'created' log
        # After update, should have at least 2 logs
        assert len(data["logs"]) >= 2, f"Expected >=2 logs (create+update), got {len(data['logs'])}"
        actions = [l["action"] for l in data["logs"]]
        assert "created" in actions
        assert "updated" in actions
        print(f"[OK] Logs: {actions}")

    def test_delete_bank_transaction(self, admin_headers):
        assert TestBankTransactionsCRUD.created_txn_id, "No txn created yet"
        resp = requests.delete(
            f"{BASE_URL}/api/admin/bank-transactions/{TestBankTransactionsCRUD.created_txn_id}",
            headers=admin_headers
        )
        assert resp.status_code == 200, f"Delete failed: {resp.text}"
        print(f"[OK] Transaction deleted")

    def test_deleted_transaction_not_in_list(self, admin_headers):
        assert TestBankTransactionsCRUD.created_txn_id, "No txn created yet"
        resp = requests.get(f"{BASE_URL}/api/admin/bank-transactions", headers=admin_headers)
        data = resp.json()
        ids = [t["id"] for t in data["transactions"]]
        assert TestBankTransactionsCRUD.created_txn_id not in ids
        print(f"[OK] Deleted transaction no longer in list")

    def test_delete_nonexistent_returns_404(self, admin_headers):
        resp = requests.delete(
            f"{BASE_URL}/api/admin/bank-transactions/nonexistent-id-12345",
            headers=admin_headers
        )
        assert resp.status_code == 404
        print(f"[OK] 404 for nonexistent transaction")


# ============ SUBSCRIPTION CONTRACT END DATE ============

class TestSubscriptionContractEndDate:
    """Test that subscriptions have contract_end_date field"""

    def test_subscriptions_list_has_contract_end(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/admin/subscriptions", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        subs = data.get("subscriptions", [])
        print(f"Found {len(subs)} subscriptions")
        if subs:
            # All subscriptions should have contract_end_date (backfilled on startup)
            for sub in subs[:5]:  # Check first 5
                assert "contract_end_date" in sub or sub.get("contract_end_date") is not None, \
                    f"Sub {sub.get('id')} missing contract_end_date"
            print(f"[OK] Subscriptions have contract_end_date field")
        else:
            print("[INFO] No subscriptions found to test")


# ============ PRODUCT PRICING COMPLEXITY ============

class TestProductPricingComplexity:
    """Test prod_zoho_books_express pricing complexity"""

    def test_zoho_books_express_product_exists(self):
        resp = requests.get(f"{BASE_URL}/api/products/prod_zoho_books_express")
        assert resp.status_code == 200, f"Product not found: {resp.text}"
        product = resp.json().get("product", {})
        assert product["id"] == "prod_zoho_books_express"
        print(f"[OK] Product found: {product['name']}")

    def test_zoho_books_express_pricing(self):
        resp = requests.get(f"{BASE_URL}/api/products/prod_zoho_books_express")
        assert resp.status_code == 200
        product = resp.json().get("product", {})
        pricing_complexity = product.get("pricing_complexity", "SIMPLE")
        print(f"pricing_complexity={pricing_complexity}")

        # Test the pricing endpoint
        pricing_resp = requests.post(f"{BASE_URL}/api/pricing/calc", json={
            "product_id": "prod_zoho_books_express",
            "inputs": {}
        })
        assert pricing_resp.status_code == 200
        pricing = pricing_resp.json()
        print(f"pricing total={pricing.get('total')}, subtotal={pricing.get('subtotal')}")

        # If COMPLEX and total > 0, it should NOT be RFQ → should show Add to Cart
        if pricing_complexity == "COMPLEX" and pricing.get("total", 0) > 0:
            print(f"[OK] COMPLEX product with price={pricing['total']} → should show Add to Cart (not RFQ)")
        elif pricing_complexity == "REQUEST_FOR_QUOTE":
            print(f"[INFO] Product is REQUEST_FOR_QUOTE → shows Request a Quote")
        else:
            print(f"[INFO] Product pricing_complexity={pricing_complexity}, total={pricing.get('total')}")

    def test_pricing_calc_returns_nonzero(self):
        pricing_resp = requests.post(f"{BASE_URL}/api/pricing/calc", json={
            "product_id": "prod_zoho_books_express",
            "inputs": {}
        })
        assert pricing_resp.status_code == 200
        pricing = pricing_resp.json()
        total = pricing.get("total", 0)
        assert total > 0, f"Expected total > 0 for Zoho Books Express (COMPLEX+priced), got {total}"
        print(f"[OK] Pricing total = {total} (non-zero → Add to Cart logic correct)")


# ============ TEST CATALOG PRODUCT BULLETS ============

class TestCatalogProductBullets:
    """Test that TEST_CatalogProduct has bullets"""

    def test_store_products_list(self):
        resp = requests.get(f"{BASE_URL}/api/products?category=test-category")
        assert resp.status_code in [200, 404]
        if resp.status_code == 200:
            products = resp.json().get("products", [])
            print(f"Found {len(products)} products in test-category")
            for p in products:
                if "TEST" in p.get("name", "").upper():
                    bullets = p.get("card_bullets") or p.get("bullets") or p.get("bullets_included") or []
                    print(f"  TEST product bullets: {bullets}")
                    assert len(bullets) > 0, f"TEST product {p['name']} has no bullets"
        else:
            print("[INFO] No test-category found (404)")


# ============ EXPORT BANK TRANSACTIONS ============

class TestBankTransactionsExport:
    """Test CSV export of bank transactions"""

    def test_export_csv_returns_content(self, admin_headers):
        resp = requests.get(
            f"{BASE_URL}/api/admin/export/bank-transactions",
            headers=admin_headers,
            allow_redirects=True
        )
        assert resp.status_code == 200
        content_type = resp.headers.get("content-type", "")
        assert "csv" in content_type or "text" in content_type, f"Expected CSV content-type, got {content_type}"
        assert len(resp.content) > 0
        print(f"[OK] Export CSV: {len(resp.content)} bytes, content-type={content_type}")
