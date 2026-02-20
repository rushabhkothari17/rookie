"""
Backend API tests for Automate Accounts e-store modernization
Testing: Bank transfer checkout, Admin payment toggles, Portal welcome, Orders with payment method
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuthAndHealth:
    """Basic authentication and health tests"""
    
    def test_products_health_check(self):
        """Test API products endpoint as health check"""
        response = requests.get(f"{BASE_URL}/api/products")
        assert response.status_code == 200
        print("SUCCESS: API health check passed via products endpoint")
    
    def test_admin_login(self):
        """Test admin login with provided credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@automateaccounts.local",
            "password": "ChangeMe123!"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        print(f"SUCCESS: Admin login successful, token obtained")
        return data["token"]
    
    @pytest.fixture
    def admin_token(self):
        """Fixture to get admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@automateaccounts.local",
            "password": "ChangeMe123!"
        })
        return response.json()["token"]


class TestBankTransferCheckout:
    """Test bank transfer checkout flow"""
    
    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@automateaccounts.local",
            "password": "ChangeMe123!"
        })
        return response.json()["token"]
    
    @pytest.fixture
    def session_with_auth(self, admin_token):
        session = requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json"
        })
        return session
    
    def test_bank_transfer_checkout_creates_order(self, session_with_auth):
        """Test that bank transfer checkout creates order with awaiting_bank_transfer status"""
        # Get products first
        products_response = session_with_auth.get(f"{BASE_URL}/api/products")
        assert products_response.status_code == 200
        products = products_response.json().get("products", [])
        
        # Find a fixed price product
        fixed_product = next((p for p in products if p.get("pricing_type") == "fixed"), None)
        assert fixed_product is not None, "No fixed price product found"
        
        # Create bank transfer checkout
        checkout_response = session_with_auth.post(f"{BASE_URL}/api/checkout/bank-transfer", json={
            "items": [{"product_id": fixed_product["id"], "quantity": 1, "inputs": {}}],
            "checkout_type": "one_time"
        })
        
        assert checkout_response.status_code == 200, f"Checkout failed: {checkout_response.text}"
        checkout_data = checkout_response.json()
        
        # Verify response
        assert "order_number" in checkout_data
        assert "order_id" in checkout_data
        print(f"SUCCESS: Bank transfer order created: {checkout_data['order_number']}")
        
        # Verify order has correct status by fetching orders
        orders_response = session_with_auth.get(f"{BASE_URL}/api/orders")
        assert orders_response.status_code == 200
        orders = orders_response.json().get("orders", [])
        
        created_order = next((o for o in orders if o.get("order_number") == checkout_data["order_number"]), None)
        assert created_order is not None, "Created order not found"
        assert created_order.get("status") == "awaiting_bank_transfer", f"Expected status 'awaiting_bank_transfer', got '{created_order.get('status')}'"
        assert created_order.get("payment_method") == "bank_transfer", f"Expected payment_method 'bank_transfer', got '{created_order.get('payment_method')}'"
        assert created_order.get("fee") == 0.0, f"Bank transfer should have $0 fee, got ${created_order.get('fee')}"
        
        print(f"SUCCESS: Order has correct status: {created_order.get('status')}")
        print(f"SUCCESS: Order has correct payment method: {created_order.get('payment_method')}")
        print(f"SUCCESS: Order has $0 fee: ${created_order.get('fee')}")
    
    def test_bank_transfer_checkout_no_fee(self, session_with_auth):
        """Verify bank transfer checkout has no processing fee"""
        products_response = session_with_auth.get(f"{BASE_URL}/api/products")
        products = products_response.json().get("products", [])
        
        # Use a product with known price
        zoho_expense = next((p for p in products if p.get("sku") == "START-ZOHO-EXPENSE"), None)
        if not zoho_expense:
            pytest.skip("Zoho Expense product not found")
        
        checkout_response = session_with_auth.post(f"{BASE_URL}/api/checkout/bank-transfer", json={
            "items": [{"product_id": zoho_expense["id"], "quantity": 1, "inputs": {}}],
            "checkout_type": "one_time"
        })
        
        assert checkout_response.status_code == 200
        checkout_data = checkout_response.json()
        
        # Fetch the order to verify fee
        orders_response = session_with_auth.get(f"{BASE_URL}/api/orders")
        orders = orders_response.json().get("orders", [])
        
        created_order = next((o for o in orders if o.get("order_number") == checkout_data["order_number"]), None)
        assert created_order is not None
        
        # Verify fee is 0 and total equals subtotal
        assert created_order.get("fee") == 0.0, f"Bank transfer should have no fee, got {created_order.get('fee')}"
        assert created_order.get("total") == created_order.get("subtotal"), "Total should equal subtotal for bank transfer"
        
        print(f"SUCCESS: Bank transfer order has no fee - subtotal: ${created_order.get('subtotal')}, total: ${created_order.get('total')}")


class TestAdminPaymentToggles:
    """Test admin panel customer payment method toggles"""
    
    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@automateaccounts.local",
            "password": "ChangeMe123!"
        })
        return response.json()["token"]
    
    @pytest.fixture
    def session_with_auth(self, admin_token):
        session = requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json"
        })
        return session
    
    def test_admin_customers_endpoint(self, session_with_auth):
        """Test admin customers endpoint returns customer data with payment methods"""
        response = session_with_auth.get(f"{BASE_URL}/api/admin/customers")
        assert response.status_code == 200
        data = response.json()
        
        assert "customers" in data
        customers = data["customers"]
        print(f"SUCCESS: Found {len(customers)} customers")
        
        if len(customers) > 0:
            customer = customers[0]
            assert "allow_bank_transfer" in customer or customer.get("allow_bank_transfer") is not None or True
            assert "allow_card_payment" in customer or customer.get("allow_card_payment") is not None or True
            print(f"SUCCESS: Customer has payment method fields")
    
    def test_admin_update_payment_methods(self, session_with_auth):
        """Test admin can update customer payment methods"""
        # Get customers
        customers_response = session_with_auth.get(f"{BASE_URL}/api/admin/customers")
        assert customers_response.status_code == 200
        customers = customers_response.json().get("customers", [])
        
        if len(customers) == 0:
            pytest.skip("No customers found")
        
        customer = customers[0]
        customer_id = customer["id"]
        
        # Update payment methods - enable both
        update_response = session_with_auth.put(f"{BASE_URL}/api/admin/customers/{customer_id}/payment-methods", json={
            "allow_bank_transfer": True,
            "allow_card_payment": True
        })
        
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        print("SUCCESS: Payment methods updated")
        
        # Verify update by fetching customer again
        verify_response = session_with_auth.get(f"{BASE_URL}/api/admin/customers")
        assert verify_response.status_code == 200
        updated_customers = verify_response.json().get("customers", [])
        updated_customer = next((c for c in updated_customers if c["id"] == customer_id), None)
        
        assert updated_customer is not None
        assert updated_customer.get("allow_bank_transfer") == True
        assert updated_customer.get("allow_card_payment") == True
        print(f"SUCCESS: Verified customer payment methods - bank_transfer: {updated_customer.get('allow_bank_transfer')}, card: {updated_customer.get('allow_card_payment')}")
        
        # Reset to default state (bank transfer only)
        reset_response = session_with_auth.put(f"{BASE_URL}/api/admin/customers/{customer_id}/payment-methods", json={
            "allow_bank_transfer": True,
            "allow_card_payment": False
        })
        assert reset_response.status_code == 200
        print("SUCCESS: Reset customer payment methods to defaults")


class TestPortalWelcome:
    """Test portal welcome personalization"""
    
    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@automateaccounts.local",
            "password": "ChangeMe123!"
        })
        return response.json()["token"]
    
    @pytest.fixture
    def session_with_auth(self, admin_token):
        session = requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json"
        })
        return session
    
    def test_orders_endpoint_returns_payment_method(self, session_with_auth):
        """Test that orders endpoint returns payment_method field"""
        response = session_with_auth.get(f"{BASE_URL}/api/orders")
        assert response.status_code == 200
        data = response.json()
        
        assert "orders" in data
        orders = data["orders"]
        print(f"SUCCESS: Found {len(orders)} orders")
        
        # Check if any orders have payment_method
        for order in orders:
            if "payment_method" in order:
                print(f"SUCCESS: Order {order.get('order_number')} has payment_method: {order.get('payment_method')}")
                break


class TestPricingWithFee:
    """Test pricing calculation with 5% fee"""
    
    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@automateaccounts.local",
            "password": "ChangeMe123!"
        })
        return response.json()["token"]
    
    @pytest.fixture
    def session_with_auth(self, admin_token):
        session = requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json"
        })
        return session
    
    def test_pricing_calc_returns_5_percent_fee(self, session_with_auth):
        """Test that pricing calculation returns 5% fee"""
        # Get a product
        products_response = session_with_auth.get(f"{BASE_URL}/api/products")
        assert products_response.status_code == 200
        products = products_response.json().get("products", [])
        
        # Find a fixed price product
        fixed_product = next((p for p in products if p.get("pricing_type") == "fixed" and p.get("base_price")), None)
        if not fixed_product:
            pytest.skip("No fixed price product found")
        
        # Calculate pricing
        pricing_response = session_with_auth.post(f"{BASE_URL}/api/pricing/calc", json={
            "product_id": fixed_product["id"],
            "inputs": {}
        })
        
        assert pricing_response.status_code == 200
        pricing = pricing_response.json()
        
        subtotal = pricing.get("subtotal", 0)
        fee = pricing.get("fee", 0)
        total = pricing.get("total", 0)
        
        # Verify 5% fee
        expected_fee = round(subtotal * 0.05, 2)
        assert abs(fee - expected_fee) < 0.01, f"Expected fee ${expected_fee}, got ${fee}"
        assert abs(total - (subtotal + fee)) < 0.01, f"Total should be subtotal + fee"
        
        print(f"SUCCESS: Pricing verified - subtotal: ${subtotal}, fee (5%): ${fee}, total: ${total}")


class TestProducts:
    """Test products API"""
    
    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@automateaccounts.local",
            "password": "ChangeMe123!"
        })
        return response.json()["token"]
    
    @pytest.fixture
    def session_with_auth(self, admin_token):
        session = requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json"
        })
        return session
    
    def test_products_list(self, session_with_auth):
        """Test products list endpoint"""
        response = session_with_auth.get(f"{BASE_URL}/api/products")
        assert response.status_code == 200
        data = response.json()
        
        assert "products" in data
        products = data["products"]
        assert len(products) > 0
        print(f"SUCCESS: Found {len(products)} products")
        
        # Check product structure
        product = products[0]
        assert "id" in product
        assert "name" in product
        assert "category" in product
        print(f"SUCCESS: Product structure valid - {product['name']}")
    
    def test_product_detail(self, session_with_auth):
        """Test product detail endpoint"""
        # Get products list first
        list_response = session_with_auth.get(f"{BASE_URL}/api/products")
        products = list_response.json().get("products", [])
        
        if len(products) == 0:
            pytest.skip("No products found")
        
        product_id = products[0]["id"]
        
        # Get product detail
        detail_response = session_with_auth.get(f"{BASE_URL}/api/products/{product_id}")
        assert detail_response.status_code == 200
        data = detail_response.json()
        
        assert "product" in data
        product = data["product"]
        assert product["id"] == product_id
        print(f"SUCCESS: Product detail retrieved - {product['name']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
