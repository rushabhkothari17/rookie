import requests
import sys
import json
from datetime import datetime

class AutomateAccountsAPITester:
    def __init__(self, base_url="https://crm-estore.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.admin_token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.user_email = f"test_user_{datetime.now().strftime('%H%M%S')}@test.com"
        self.verification_code = None
        
    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}"
        default_headers = {'Content-Type': 'application/json'}
        if headers:
            default_headers.update(headers)
        
        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=default_headers)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=default_headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=default_headers)
                
            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return True, response.json()
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"   Error: {error_detail}")
                except:
                    print(f"   Response text: {response.text}")
                return False, {}
                
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_basic_health(self):
        """Test basic API health"""
        success, _ = self.run_test("API Health Check", "GET", "", 200)
        return success

    def test_signup(self):
        """Test user signup"""
        signup_data = {
            "full_name": "Test User",
            "company_name": "Test Company",
            "email": self.user_email,
            "phone": "+1234567890",
            "password": "TestPass123!",
            "address": {
                "line1": "123 Test St",
                "line2": "",
                "city": "Test City",
                "region": "Test Region",
                "postal": "12345",
                "country": "USA"
            }
        }
        
        success, response = self.run_test("User Signup", "POST", "auth/register", 200, signup_data)
        if success and response.get("verification_code"):
            self.verification_code = response["verification_code"]
            print(f"   Verification code: {self.verification_code}")
        return success

    def test_email_verification(self):
        """Test email verification"""
        if not self.verification_code:
            print("❌ Skipping verification - no verification code")
            return False
            
        verify_data = {
            "email": self.user_email,
            "code": self.verification_code
        }
        
        success, _ = self.run_test("Email Verification", "POST", "auth/verify-email", 200, verify_data)
        return success

    def test_login(self):
        """Test user login"""
        login_data = {
            "email": self.user_email,
            "password": "TestPass123!"
        }
        
        success, response = self.run_test("User Login", "POST", "auth/login", 200, login_data)
        if success and response.get("token"):
            self.token = response["token"]
        return success

    def test_admin_login(self):
        """Test admin login"""
        admin_data = {
            "email": "admin@automateaccounts.local",
            "password": "ChangeMe123!"
        }
        
        success, response = self.run_test("Admin Login", "POST", "auth/login", 200, admin_data)
        if success and response.get("token"):
            self.admin_token = response["token"]
        return success

    def test_get_me(self):
        """Test getting current user info"""
        if not self.token:
            print("❌ Skipping get me - no token")
            return False
            
        headers = {"Authorization": f"Bearer {self.token}"}
        success, _ = self.run_test("Get Current User", "GET", "me", 200, headers=headers)
        return success

    def test_get_categories(self):
        """Test getting product categories"""
        if not self.token:
            print("❌ Skipping categories - no token")
            return False
            
        headers = {"Authorization": f"Bearer {self.token}"}
        success, _ = self.run_test("Get Categories", "GET", "categories", 200, headers=headers)
        return success

    def test_get_products(self):
        """Test getting products"""
        if not self.token:
            print("❌ Skipping products - no token")
            return False
            
        headers = {"Authorization": f"Bearer {self.token}"}
        success, response = self.run_test("Get Products", "GET", "products", 200, headers=headers)
        
        if success and response.get("products"):
            # Test getting individual product
            product_id = response["products"][0]["id"]
            success2, _ = self.run_test("Get Single Product", "GET", f"products/{product_id}", 200, headers=headers)
            return success and success2
        return success

    def test_pricing_calculation(self):
        """Test pricing calculation for a calculator product"""
        if not self.token:
            print("❌ Skipping pricing calc - no token")
            return False
            
        headers = {"Authorization": f"Bearer {self.token}"}
        
        # Get products first to find a calculator product
        products_success, products_response = self.run_test("Get Products for Pricing", "GET", "products", 200, headers=headers)
        if not products_success:
            return False
            
        calculator_product = None
        for product in products_response.get("products", []):
            if product.get("pricing_type") == "calculator":
                calculator_product = product
                break
                
        if not calculator_product:
            print("❌ No calculator products found")
            return False
            
        # Test pricing calculation
        calc_data = {
            "product_id": calculator_product["id"],
            "inputs": {"hours": 20, "payment_option": "pay_now"} if calculator_product.get("id") == "prod_hours_pack" else {}
        }
        
        success, _ = self.run_test("Pricing Calculation", "POST", "pricing/calc", 200, calc_data, headers=headers)
        return success

    def test_order_preview(self):
        """Test order preview"""
        if not self.token:
            print("❌ Skipping order preview - no token")
            return False
            
        headers = {"Authorization": f"Bearer {self.token}"}
        
        # Get a product first
        products_success, products_response = self.run_test("Get Products for Order", "GET", "products", 200, headers=headers)
        if not products_success or not products_response.get("products"):
            return False
            
        product = products_response["products"][0]
        
        preview_data = {
            "items": [{
                "product_id": product["id"],
                "quantity": 1,
                "inputs": {}
            }]
        }
        
        success, _ = self.run_test("Order Preview", "POST", "orders/preview", 200, preview_data, headers=headers)
        return success

    def test_scope_request(self):
        """Test scope request creation"""
        if not self.token:
            print("❌ Skipping scope request - no token")
            return False
            
        headers = {"Authorization": f"Bearer {self.token}"}
        
        # Find a scope request product (hours pack with scope_later option)
        products_success, products_response = self.run_test("Get Products for Scope", "GET", "products", 200, headers=headers)
        if not products_success:
            return False
            
        hours_pack_product = None
        for product in products_response.get("products", []):
            if product.get("id") == "prod_hours_pack":
                hours_pack_product = product
                break
                
        if not hours_pack_product:
            print("❌ Hours pack product not found")
            return False
            
        scope_data = {
            "items": [{
                "product_id": hours_pack_product["id"],
                "quantity": 1,
                "inputs": {"hours": 20, "payment_option": "scope_later"}
            }]
        }
        
        success, _ = self.run_test("Scope Request", "POST", "orders/scope-request", 200, scope_data, headers=headers)
        return success

    def test_get_orders(self):
        """Test getting user orders"""
        if not self.token:
            print("❌ Skipping get orders - no token")
            return False
            
        headers = {"Authorization": f"Bearer {self.token}"}
        success, _ = self.run_test("Get Orders", "GET", "orders", 200, headers=headers)
        return success

    def test_get_subscriptions(self):
        """Test getting user subscriptions"""
        if not self.token:
            print("❌ Skipping get subscriptions - no token")
            return False
            
        headers = {"Authorization": f"Bearer {self.token}"}
        success, _ = self.run_test("Get Subscriptions", "GET", "subscriptions", 200, headers=headers)
        return success

    def test_admin_endpoints(self):
        """Test admin endpoints"""
        if not self.admin_token:
            print("❌ Skipping admin tests - no admin token")
            return False
            
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        
        # Test admin customers
        success1, _ = self.run_test("Admin Get Customers", "GET", "admin/customers", 200, headers=headers)
        
        # Test admin orders
        success2, _ = self.run_test("Admin Get Orders", "GET", "admin/orders", 200, headers=headers)
        
        # Test admin subscriptions  
        success3, _ = self.run_test("Admin Get Subscriptions", "GET", "admin/subscriptions", 200, headers=headers)
        
        # Test admin sync logs
        success4, _ = self.run_test("Admin Get Sync Logs", "GET", "admin/sync-logs", 200, headers=headers)
        
        return success1 and success2 and success3 and success4

def main():
    tester = AutomateAccountsAPITester()
    
    print("🚀 Starting Automate Accounts API Testing...")
    print(f"Testing against: {tester.base_url}")
    
    # Basic tests
    tester.test_basic_health()
    
    # Authentication flow tests
    tester.test_signup()
    tester.test_email_verification()
    tester.test_login()
    tester.test_admin_login()
    
    # User functionality tests
    tester.test_get_me()
    tester.test_get_categories()
    tester.test_get_products()
    tester.test_pricing_calculation()
    tester.test_order_preview()
    tester.test_scope_request()
    tester.test_get_orders()
    tester.test_get_subscriptions()
    
    # Admin functionality tests
    tester.test_admin_endpoints()
    
    print(f"\n📊 Final Results:")
    print(f"Tests run: {tester.tests_run}")
    print(f"Tests passed: {tester.tests_passed}")
    print(f"Tests failed: {tester.tests_run - tester.tests_passed}")
    print(f"Success rate: {(tester.tests_passed / tester.tests_run * 100):.1f}%")
    
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())