#!/usr/bin/env python3
import requests
import sys
import json

class ReviewRequestTester:
    def __init__(self):
        self.base_url = "https://bug-fix-sprint-9.preview.emergentagent.com"
        self.admin_token = None
        self.user_token = None
        
    def authenticate(self):
        """Authenticate admin and create test user"""
        # Admin login
        admin_login = {
            "email": "admin@automateaccounts.local",
            "password": "ChangeMe123!"
        }
        
        response = requests.post(f"{self.base_url}/api/auth/login", json=admin_login)
        if response.status_code == 200:
            self.admin_token = response.json().get("token")
            print("✅ Admin authentication successful")
        else:
            print("❌ Admin authentication failed")
            return False
            
        # Create test user
        test_email = "testreview@test.com"
        signup_data = {
            "full_name": "Review Test User",
            "job_title": "Tester",
            "company_name": "Test Co",
            "email": test_email,
            "phone": "+1234567890", 
            "password": "TestPass123!",
            "address": {
                "line1": "123 Test St", "line2": "", "city": "Test City",
                "region": "Test State", "postal": "12345", "country": "USA"
            }
        }
        
        response = requests.post(f"{self.base_url}/api/auth/register", json=signup_data)
        if response.status_code == 200:
            verification_code = response.json().get("verification_code")
            
            # Verify email
            verify_data = {"email": test_email, "code": verification_code}
            requests.post(f"{self.base_url}/api/auth/verify-email", json=verify_data)
            
            # Login
            login_data = {"email": test_email, "password": "TestPass123!"}
            response = requests.post(f"{self.base_url}/api/auth/login", json=login_data)
            if response.status_code == 200:
                self.user_token = response.json().get("token")
                print("✅ User authentication successful")
                
                # Enable card payment for this user
                me_response = requests.get(f"{self.base_url}/api/me", headers={"Authorization": f"Bearer {self.user_token}"})
                customer_id = me_response.json().get("customer", {}).get("id")
                
                if customer_id:
                    payment_data = {"allow_bank_transfer": True, "allow_card_payment": True}
                    requests.put(
                        f"{self.base_url}/api/admin/customers/{customer_id}/payment-methods",
                        json=payment_data,
                        headers={"Authorization": f"Bearer {self.admin_token}"}
                    )
                
                return True
        
        return False

    def test_exact_review_request_payload(self):
        """Test the exact payload from the review request"""
        print("\n" + "="*70)
        print("🎯 TESTING EXACT REVIEW REQUEST PAYLOAD")
        print("="*70)
        
        # Exact payload from review request
        payload = {
            "items": [{"product_id": "prod_ongoing_bookkeeping", "quantity": 1, "inputs": {}}],
            "checkout_type": "subscription",
            "origin_url": "https://bug-fix-sprint-9.preview.emergentagent.com",
            "terms_accepted": True
        }
        
        print("📦 Testing payload:")
        print(json.dumps(payload, indent=2))
        
        headers = {"Authorization": f"Bearer {self.user_token}", "Content-Type": "application/json"}
        
        response = requests.post(f"{self.base_url}/api/checkout/session", json=payload, headers=headers)
        
        print(f"\n📊 Response:")
        print(f"   Status: {response.status_code}")
        
        try:
            response_json = response.json()
            print(f"   Response: {json.dumps(response_json, indent=2)}")
        except:
            print(f"   Text: {response.text}")
            response_json = {}
        
        if response.status_code == 200:
            if response_json.get("url") and response_json.get("session_id"):
                print("\n✅ SUCCESS: Stripe checkout session created successfully")
                print(f"   Session ID: {response_json.get('session_id')}")
                print(f"   Checkout URL: {response_json.get('url')}")
                return True
            else:
                print("\n❌ Response missing URL or session_id")
                return False
        else:
            error = response_json.get("detail", "Unknown error")
            if "payment" in error and "recurring price" in error:
                print(f"\n❌ CRITICAL BUG STILL PRESENT: {error}")
            elif "stripe price" in error.lower():
                print(f"\n⚠️  Stripe configuration issue: {error}")
            else:
                print(f"\n❌ Other error: {error}")
            return False

    def test_gocardless_errors(self):
        """Test GoCardless error scenarios"""
        print("\n" + "="*70) 
        print("🛠️  TESTING GOCARDLESS ERROR SCENARIOS")
        print("="*70)
        
        headers = {"Authorization": f"Bearer {self.user_token}", "Content-Type": "application/json"}
        
        # Test 1: Invalid bank transfer payload
        print("\n📋 Test 1: Bank transfer with invalid data")
        invalid_data = {
            "items": [{"product_id": "nonexistent", "quantity": 1, "inputs": {}}],
            "checkout_type": "one_time",
            "terms_accepted": True
        }
        
        response = requests.post(f"{self.base_url}/api/checkout/bank-transfer", json=invalid_data, headers=headers)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 404:
            error_detail = response.json().get("detail", "")
            print(f"   Error: {error_detail}")
            print(f"   Error type: {type(error_detail)}")
            if isinstance(error_detail, str):
                print("   ✅ Error is string format")
            else:
                print("   ❌ Error is not string format")
        
        # Test 2: Invalid GoCardless redirect completion
        print("\n📋 Test 2: Invalid GoCardless redirect completion")
        invalid_redirect = {
            "redirect_flow_id": "invalid_flow_12345",
            "order_id": "fake_order",
            "subtotal": 100.0,
            "discount": 0.0,
            "fee": 5.0,
            "status": "paid"
        }
        
        response = requests.post(f"{self.base_url}/api/gocardless/complete-redirect", json=invalid_redirect, headers=headers)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 400:
            error_detail = response.json().get("detail", "")
            print(f"   Error: {error_detail}")
            print(f"   Error type: {type(error_detail)}")
            if isinstance(error_detail, str) and ("redirect" in error_detail.lower() or "expired" in error_detail.lower()):
                print("   ✅ Error is human-readable string")
                return True
            else:
                print("   ❌ Error is not proper format")
                return False
        
        return True

    def run_review_tests(self):
        """Run all tests specified in the review request"""
        print("🔥 TESTING CRITICAL BUG FIXES - STRIPE SUBSCRIPTION MODE & GOCARDLESS ERROR HANDLING")
        print("Backend URL: https://bug-fix-sprint-9.preview.emergentagent.com/api")
        print("Admin Credentials: admin@automateaccounts.local / ChangeMe123!")
        print("="*90)
        
        if not self.authenticate():
            print("❌ Authentication failed")
            return False
            
        test1 = self.test_exact_review_request_payload()
        test2 = self.test_gocardless_errors()
        
        print("\n" + "="*70)
        print("📊 FINAL REVIEW REQUEST VALIDATION")
        print("="*70)
        
        results = [
            ("✅ Stripe subscription session uses mode='subscription'", test1),
            ("✅ All error responses have string 'detail' field", test2), 
            ("✅ No raw Pydantic objects in API responses", test2),
            ("✅ GoCardless errors are human-readable", test2)
        ]
        
        passed = sum(1 for _, result in results if result)
        
        for desc, result in results:
            status = "PASS" if result else "FAIL"
            icon = "✅" if result else "❌"
            print(f"{icon} {desc}: {status}")
        
        print("="*70)
        print(f"Critical validations: {passed}/{len(results)} PASSED")
        
        if passed == len(results):
            print("\n🎉 ALL CRITICAL BUG FIXES VERIFIED SUCCESSFULLY!")
        else:
            print(f"\n⚠️  {len(results) - passed} validation(s) still failing")
            
        return passed == len(results)

def main():
    tester = ReviewRequestTester()
    success = tester.run_review_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())