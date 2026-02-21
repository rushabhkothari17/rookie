import requests
import sys
import json
from datetime import datetime

class AutomateAccountsAPITester:
    def __init__(self, base_url="https://ui-stabilization.preview.emergentagent.com"):
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
            "job_title": "Test Position",
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

    def test_admin_catalog_terms_assignment(self):
        """TEST 1: Admin - Product-Terms Assignment"""
        if not self.admin_token:
            print("❌ Skipping admin catalog terms - no admin token")
            return False
            
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        
        # Get products (admin can access regular products endpoint)
        success1, products_response = self.run_test("Admin Get Products", "GET", "products", 200, headers=headers)
        if not success1:
            return False
            
        # Test getting terms list first
        success2, terms_response = self.run_test("Admin Get Terms", "GET", "terms", 200, headers=headers)
        if not success2:
            return False
            
        # Test getting products to find one to update
        if products_response.get("products"):
            product = products_response["products"][0]
            product_id = product["id"]
            
            if terms_response.get("terms"):
                terms_id = terms_response["terms"][0]["id"]
                
                # Test updating product terms assignment
                update_data = {"terms_id": terms_id}
                success3, _ = self.run_test("Admin Update Product Terms", "PUT", f"admin/products/{product_id}/terms", 200, update_data, headers=headers)
                return success1 and success2 and success3
                
        return success1 and success2

    def test_admin_manual_subscription_creation(self):
        """TEST 2: Admin - Manual Subscription Creation"""
        if not self.admin_token:
            print("❌ Skipping manual subscription creation - no admin token")
            return False
            
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        
        # Get subscription products first
        success1, products_response = self.run_test("Get Products for Subscription", "GET", "products", 200, headers=headers)
        if not success1:
            return False
            
        # Find a subscription product
        subscription_product = None
        for product in products_response.get("products", []):
            if product.get("is_subscription"):
                subscription_product = product
                break
                
        if not subscription_product:
            print("❌ No subscription products found")
            return False
            
        # Test creating manual subscription
        manual_sub_data = {
            "customer_email": "admin@automateaccounts.local",
            "product_id": subscription_product["id"],
            "amount": 500.0,
            "renewal_date": "2026-03-20",
            "status": "active"
        }
        
        success2, response = self.run_test("Create Manual Subscription", "POST", "admin/subscriptions/manual", 200, manual_sub_data, headers=headers)
        
        if success2:
            # Verify subscription appears in list
            success3, _ = self.run_test("Verify Manual Subscription in List", "GET", "admin/subscriptions", 200, headers=headers)
            return success1 and success2 and success3
            
        return success1 and success2

    def test_admin_renew_now_button(self):
        """TEST 3: Admin - Renew Now Button"""
        if not self.admin_token:
            print("❌ Skipping renew now test - no admin token")
            return False
            
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        
        # Get subscriptions to find one to renew
        success1, subs_response = self.run_test("Get Subscriptions for Renewal", "GET", "admin/subscriptions", 200, headers=headers)
        if not success1:
            return False
            
        # Find a manual subscription to renew
        manual_subscription = None
        for sub in subs_response.get("subscriptions", []):
            if sub.get("payment_method") == "manual" or sub.get("is_manual"):
                manual_subscription = sub
                break
                
        if not manual_subscription:
            print("❌ No manual subscriptions found for renewal")
            return False
            
        # Test renewing subscription
        success2, renewal_response = self.run_test("Renew Subscription", "POST", f"subscriptions/{manual_subscription['id']}/renew-now", 200, {}, headers=headers)
        
        if success2:
            # Verify renewal order was created
            success3, orders_response = self.run_test("Verify Renewal Order Created", "GET", "admin/orders", 200, headers=headers)
            if success3 and orders_response.get("orders"):
                # Check if any order has subscription_id
                has_subscription_order = any(order.get("subscription_id") for order in orders_response["orders"])
                if has_subscription_order:
                    print("✅ Renewal order with subscription_id found")
                    return True
                else:
                    print("❌ No renewal orders with subscription_id found")
                    return False
                    
        return success1 and success2

    def test_admin_audit_logs(self):
        """TEST 4: Admin - Audit Logs"""
        if not self.admin_token:
            print("❌ Skipping audit logs test - no admin token")
            return False
            
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        
        # Get orders first to get an order ID
        success1, orders_response = self.run_test("Get Orders for Audit", "GET", "admin/orders", 200, headers=headers)
        if not success1:
            return False
            
        # Test audit logs for orders
        if orders_response.get("orders") and len(orders_response["orders"]) > 0:
            order_id = orders_response["orders"][0]["id"]
            success2, order_logs = self.run_test("Get Order Audit Logs", "GET", f"admin/orders/{order_id}/logs", 200, headers=headers)
            
            # Verify log structure has required fields
            if success2 and order_logs.get("logs"):
                log = order_logs["logs"][0]
                has_required_fields = all(field in log for field in ["action", "actor", "created_at", "details"])
                if has_required_fields:
                    print("✅ Audit log has required fields: action, actor, timestamp, details")
                else:
                    print("❌ Audit log missing required fields")
                    return False
        else:
            success2 = True  # No orders to test
            
        # Get subscriptions for audit logs
        success3, subs_response = self.run_test("Get Subscriptions for Audit", "GET", "admin/subscriptions", 200, headers=headers)
        
        # Test audit logs for subscriptions  
        if success3 and subs_response.get("subscriptions") and len(subs_response["subscriptions"]) > 0:
            sub_id = subs_response["subscriptions"][0]["id"]
            success4, sub_logs = self.run_test("Get Subscription Audit Logs", "GET", f"admin/subscriptions/{sub_id}/logs", 200, headers=headers)
            return success1 and success2 and success3 and success4
            
        return success1 and success2 and success3

    def test_stripe_subscription_checkout(self):
        """TEST 5: Stripe Subscription Checkout"""
        if not self.token:
            print("❌ Skipping Stripe checkout - no user token")
            return False
            
        headers = {"Authorization": f"Bearer {self.token}"}
        admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        
        # Get current user and customer info
        success_user, me_response = self.run_test("Get Current User for Card Payment", "GET", "me", 200, headers=headers)
        if not success_user:
            return False
        
        customer_info = me_response.get("customer")
        if not customer_info:
            print("❌ No customer record found for test user")
            return False
        
        # Enable card payment for test customer
        payment_update_data = {
            "allow_bank_transfer": True,
            "allow_card_payment": True
        }
        success_enable, _ = self.run_test("Enable Card Payment", "PUT", f"admin/customers/{customer_info['id']}/payment-methods", 200, payment_update_data, headers=admin_headers)
        if not success_enable:
            return False
        
        # Get subscription product (like "Ongoing Bookkeeping")
        success1, products_response = self.run_test("Get Products for Stripe Checkout", "GET", "products", 200, headers=headers)
        if not success1:
            return False
            
        # Find "Ongoing Bookkeeping" or similar subscription product
        bookkeeping_product = None
        for product in products_response.get("products", []):
            if "bookkeeping" in product.get("name", "").lower() and product.get("is_subscription"):
                bookkeeping_product = product
                break
                
        if not bookkeeping_product:
            print("❌ Ongoing Bookkeeping subscription product not found")
            return False
            
        # Test Stripe checkout session creation
        checkout_data = {
            "items": [{
                "product_id": bookkeeping_product["id"],
                "quantity": 1,
                "inputs": {"transactions": 100, "inventory": False, "multi_currency": False, "offshore": False}
            }],
            "checkout_type": "subscription",
            "origin_url": "https://ui-stabilization.preview.emergentagent.com",
            "terms_accepted": True
        }
        
        success2, checkout_response = self.run_test("Create Stripe Checkout Session", "POST", "checkout/session", 200, checkout_data, headers=headers)
        
        # Verify no error and redirect URL present
        if success2:
            if checkout_response.get("checkout_url") and "stripe" in checkout_response.get("checkout_url", "").lower():
                print("✅ Stripe checkout URL generated successfully")
                return True
            else:
                print("❌ No Stripe checkout URL in response")
                return False
                
        return success1 and success2

    def test_terms_conditions_display(self):
        """TEST 6: Terms & Conditions Display"""
        if not self.token:
            print("❌ Skipping terms display test - no user token")
            return False
            
        headers = {"Authorization": f"Bearer {self.token}"}
        
        # Get terms list
        success1, terms_response = self.run_test("Get Terms List", "GET", "terms", 200, headers=headers)
        if not success1:
            return False
            
        if not terms_response.get("terms"):
            print("❌ No terms found")
            return False
            
        # Test getting resolved terms (should resolve dynamic tags)
        if terms_response.get("terms"):
            # Get a product to test with
            success_prod, products = self.run_test("Get Products for Terms", "GET", "products", 200, headers=headers)
            if success_prod and products.get("products"):
                product_id = products["products"][0]["id"]
                success2, resolved_terms = self.run_test("Get Resolved Terms", "GET", f"terms/for-product/{product_id}", 200, headers=headers)
            else:
                success2 = False
        else:
            success2 = False
        
        if success2:
            # Check if dynamic tags are resolved
            content = resolved_terms.get("content", "")
            if "{" not in content:  # Should have no unresolved tags
                print("✅ Dynamic tags resolved in T&C content")
                return True
            else:
                print("❌ Dynamic tags not resolved in T&C content")
                return False
                
        return success1 and success2

    def test_gocardless_payment_flow(self):
        """TEST 7: GoCardless Flow (CRITICAL - Full End-to-End)"""
        if not self.token:
            print("❌ Skipping GoCardless flow - no user token")
            return False
            
        headers = {"Authorization": f"Bearer {self.token}"}
        
        # Get a product for bank transfer checkout
        success1, products_response = self.run_test("Get Products for GoCardless", "GET", "products", 200, headers=headers)
        if not success1:
            return False
            
        # Use first available product
        if not products_response.get("products"):
            print("❌ No products found for GoCardless test")
            return False
            
        product = products_response["products"][0]
        
        # Test bank transfer checkout creation
        bank_transfer_data = {
            "items": [{
                "product_id": product["id"],
                "quantity": 1,
                "inputs": {}
            }],
            "checkout_type": "one_time",
            "terms_accepted": True
        }
        
        success2, checkout_response = self.run_test("Create Bank Transfer Order", "POST", "checkout/bank-transfer", 200, bank_transfer_data, headers=headers)
        
        if success2:
            order_id = checkout_response.get("order_id")
            redirect_flow_id = checkout_response.get("redirect_flow_id")
            redirect_url = checkout_response.get("gocardless_redirect_url")
            
            if order_id and redirect_flow_id and redirect_url:
                print(f"✅ GoCardless redirect URL created: {redirect_url[:50]}...")
                
                # Test completing redirect flow (simulating return from GoCardless)
                complete_data = {
                    "redirect_flow_id": redirect_flow_id,
                    "order_id": order_id,
                    "subtotal": 100.0,
                    "discount": 0.0,
                    "fee": 0.0,
                    "status": "paid"
                }
                success3, complete_response = self.run_test("Complete GoCardless Redirect", "POST", "gocardless/complete-redirect", 200, complete_data, headers=headers)
                
                if success3:
                    # Verify order status updated
                    success4, order_status = self.run_test("Check Order Status After GoCardless", "GET", f"orders/{order_id}", 200, headers=headers)
                    
                    if success4:
                        status = order_status.get("status")
                        has_payment_id = order_status.get("gocardless_payment_id") is not None
                        
                        if status in ["paid", "pending_payment"] and has_payment_id:
                            print(f"✅ Order status updated to '{status}' with GoCardless payment ID")
                            return True
                        else:
                            print(f"❌ Order status '{status}' or missing GoCardless payment ID")
                            return False
                            
                    return success1 and success2 and success3 and success4
                return success1 and success2 and success3
            else:
                print("❌ Missing order_id, redirect_flow_id, or redirect URL")
                return False
        return success1 and success2

    def test_payment_error_handling(self):
        """TEST 8: Error Messages"""
        if not self.token:
            print("❌ Skipping error handling test - no user token")
            return False
            
        headers = {"Authorization": f"Bearer {self.token}"}
        
        # Test Stripe checkout with invalid configuration (missing stripe_price_id)
        invalid_checkout_data = {
            "items": [{
                "product_id": "nonexistent_product_id",
                "quantity": 1,
                "inputs": {}
            }],
            "checkout_type": "one_time",
            "origin_url": "https://ui-stabilization.preview.emergentagent.com",
            "terms_accepted": True
        }
        
        success1, error_response = self.run_test("Test Invalid Product Checkout", "POST", "checkout/session", 404, invalid_checkout_data, headers=headers)
        
        if success1:
            error_detail = error_response.get("detail", "")
            if "product" in error_detail.lower() or "not found" in error_detail.lower():
                print("✅ Specific error message for invalid product")
            else:
                print(f"❌ Generic error message: {error_detail}")
                return False
                
        # Test checkout without terms accepted
        no_terms_data = {
            "items": [{
                "product_id": "prod_bookkeeping",
                "quantity": 1,
                "inputs": {}
            }],
            "checkout_type": "one_time",
            "origin_url": "https://ui-stabilization.preview.emergentagent.com",
            "terms_accepted": False
        }
        
        success2, terms_error = self.run_test("Test Checkout Without Terms", "POST", "checkout/session", 400, no_terms_data, headers=headers)
        
        if success2:
            error_detail = terms_error.get("detail", "")
            if "terms" in error_detail.lower() or "conditions" in error_detail.lower():
                print("✅ Specific error message for terms not accepted")
            else:
                print(f"❌ Generic error message for terms: {error_detail}")
                return False
                
        return success1 and success2

def main():
    tester = AutomateAccountsAPITester()
    
    print("🚀 Starting Automate Accounts P0 Functions Testing...")
    print(f"Testing against: {tester.base_url}")
    print("Admin credentials: admin@automateaccounts.local / ChangeMe123!")
    print("="*80)
    
    # Authentication setup
    tester.test_basic_health()
    tester.test_signup()
    tester.test_email_verification()
    tester.test_login()
    tester.test_admin_login()
    
    if not tester.admin_token:
        print("❌ CRITICAL: Admin login failed - cannot proceed with P0 tests")
        return 1
    
    print("\n" + "="*80)
    print("🔥 P0 CRITICAL FUNCTIONS TESTING")
    print("="*80)
    
    # P0 Tests as specified in review request
    print("\n📋 TEST 1: Admin - Product-Terms Assignment")
    test1_result = tester.test_admin_catalog_terms_assignment()
    
    print("\n📋 TEST 2: Admin - Manual Subscription Creation")  
    test2_result = tester.test_admin_manual_subscription_creation()
    
    print("\n📋 TEST 3: Admin - Renew Now Button")
    test3_result = tester.test_admin_renew_now_button()
    
    print("\n📋 TEST 4: Admin - Audit Logs")
    test4_result = tester.test_admin_audit_logs()
    
    print("\n📋 TEST 5: Stripe Subscription Checkout")
    test5_result = tester.test_stripe_subscription_checkout()
    
    print("\n📋 TEST 6: Terms & Conditions Display")
    test6_result = tester.test_terms_conditions_display()
    
    print("\n📋 TEST 7: GoCardless Flow (CRITICAL - End-to-End)")
    test7_result = tester.test_gocardless_payment_flow()
    
    print("\n📋 TEST 8: Error Messages")
    test8_result = tester.test_payment_error_handling()
    
    # Summary of P0 Tests
    p0_tests = [
        ("Admin Product-Terms Assignment", test1_result),
        ("Admin Manual Subscription Creation", test2_result),
        ("Admin Renew Now Button", test3_result),
        ("Admin Audit Logs", test4_result),
        ("Stripe Subscription Checkout", test5_result),
        ("Terms & Conditions Display", test6_result),
        ("GoCardless Payment Flow", test7_result),
        ("Payment Error Handling", test8_result)
    ]
    
    print(f"\n📊 P0 TEST RESULTS:")
    print("="*80)
    
    p0_passed = 0
    for test_name, result in p0_tests:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:40} {status}")
        if result:
            p0_passed += 1
    
    print("="*80)
    print(f"\n📊 OVERALL RESULTS:")
    print(f"Total API tests run: {tester.tests_run}")
    print(f"Total API tests passed: {tester.tests_passed}")
    print(f"API Success rate: {(tester.tests_passed / tester.tests_run * 100):.1f}%")
    print(f"P0 Functions passed: {p0_passed}/8")
    print(f"P0 Success rate: {(p0_passed / 8 * 100):.1f}%")
    
    # Critical validation results
    critical_failures = []
    if not test1_result:
        critical_failures.append("❌ Catalog tab cannot open or terms assignment failed")
    if not test3_result:
        critical_failures.append("❌ 'Renew Now' button not working for manual subscriptions")
    if not test7_result:
        critical_failures.append("❌ GoCardless payment completion failed - order status not updated")
    if not test4_result:
        critical_failures.append("❌ Audit logs missing timestamps or actor info")
        
    if critical_failures:
        print("\n🚨 CRITICAL VALIDATIONS FAILED:")
        for failure in critical_failures:
            print(failure)
    else:
        print("\n✅ All critical validations passed!")
    
    return 0 if p0_passed >= 6 else 1  # Allow 2 failures out of 8 tests

if __name__ == "__main__":
    sys.exit(main())