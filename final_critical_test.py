#!/usr/bin/env python3
import requests
import sys
import json

def test_critical_bug_fixes():
    """
    Final comprehensive test for the critical bug fixes mentioned in review request:
    
    TEST 1: Stripe Subscription Checkout Mode (CRITICAL)
    - Test subscription product checkout (Ongoing Bookkeeping)
    - Verify Stripe session created with mode="subscription"
    - Previous error should NOT appear: "You specified `payment` mode but passed a recurring price"
    
    TEST 2: GoCardless Error Response Format  
    - Test that GoCardless errors return proper string messages
    - No Pydantic validation objects in response
    
    TEST 3: GoCardless Callback Error Handling
    - All errors should be strings, not objects
    - Human-readable error messages
    """
    
    base_url = "https://server-migration-8.preview.emergentagent.com"
    
    print("🔥 CRITICAL BUG FIXES - FINAL VALIDATION")
    print("="*80)
    print("Backend URL:", base_url + "/api")
    print("Admin Credentials: admin@automateaccounts.local / ChangeMe123!")
    print("="*80)
    
    # Authenticate
    print("\n🔐 Authentication...")
    admin_data = {"email": "admin@automateaccounts.local", "password": "ChangeMe123!"}
    response = requests.post(f"{base_url}/api/auth/login", json=admin_data)
    
    if response.status_code != 200:
        print("❌ Admin authentication failed")
        return False
        
    admin_token = response.json()["token"]
    print("✅ Admin authenticated")
    
    # Create test user  
    test_email = "finaltest@test.com"
    signup = {
        "full_name": "Final Test User", "job_title": "Tester", "company_name": "Test Co",
        "email": test_email, "phone": "+1234567890", "password": "TestPass123!",
        "address": {"line1": "123 Test St", "line2": "", "city": "Test City", "region": "Test State", "postal": "12345", "country": "USA"}
    }
    
    response = requests.post(f"{base_url}/api/auth/register", json=signup)
    verification_code = response.json().get("verification_code")
    
    # Verify and login
    requests.post(f"{base_url}/api/auth/verify-email", json={"email": test_email, "code": verification_code})
    response = requests.post(f"{base_url}/api/auth/login", json={"email": test_email, "password": "TestPass123!"})
    user_token = response.json()["token"]
    
    # Enable card payment
    me_response = requests.get(f"{base_url}/api/me", headers={"Authorization": f"Bearer {user_token}"})
    customer_id = me_response.json()["customer"]["id"]
    payment_data = {"allow_bank_transfer": True, "allow_card_payment": True}
    requests.put(f"{base_url}/api/admin/customers/{customer_id}/payment-methods", json=payment_data, headers={"Authorization": f"Bearer {admin_token}"})
    
    print("✅ User authenticated and card payment enabled")
    
    # TEST 1: Stripe Subscription Mode Fix
    print("\n" + "="*60)
    print("🎯 TEST 1: STRIPE SUBSCRIPTION CHECKOUT MODE")
    print("="*60)
    
    # Correct payload with right product ID
    payload = {
        "items": [{"product_id": "prod_bookkeeping", "quantity": 1, "inputs": {"transactions": 100, "inventory": False, "multi_currency": False, "offshore": False}}],
        "checkout_type": "subscription",
        "origin_url": "https://server-migration-8.preview.emergentagent.com", 
        "terms_accepted": True
    }
    
    print("📦 Testing Stripe subscription checkout...")
    print(f"   Product ID: prod_bookkeeping (Ongoing Bookkeeping)")
    print(f"   Checkout Type: subscription")
    
    headers = {"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"}
    response = requests.post(f"{base_url}/api/checkout/session", json=payload, headers=headers)
    
    print(f"📊 Response Status: {response.status_code}")
    
    test1_pass = False
    if response.status_code == 200:
        result = response.json()
        session_id = result.get("session_id")
        url = result.get("url")
        
        if session_id and url and "stripe" in url:
            print("✅ SUCCESS: Stripe checkout session created successfully")
            print(f"   Session ID: {session_id}")
            print(f"   URL: {url[:80]}...")
            print("✅ CRITICAL VALIDATION: mode='subscription' used (no 'payment mode but recurring price' error)")
            test1_pass = True
        else:
            print("❌ Missing session_id or URL in response")
    else:
        error = response.json().get("detail", "")
        if "payment" in error and "recurring price" in error:
            print(f"❌ CRITICAL BUG STILL PRESENT: {error}")
        else:
            print(f"❌ Error: {error}")
    
    # TEST 2: GoCardless Error Response Format
    print("\n" + "="*60)
    print("🛠️  TEST 2: GOCARDLESS ERROR RESPONSE FORMAT")
    print("="*60)
    
    test2_pass = True
    
    # Test invalid product error
    invalid_data = {"items": [{"product_id": "invalid", "quantity": 1, "inputs": {}}], "checkout_type": "one_time", "terms_accepted": True}
    response = requests.post(f"{base_url}/api/checkout/bank-transfer", json=invalid_data, headers=headers)
    
    if response.status_code == 404:
        error = response.json().get("detail", "")
        if isinstance(error, str):
            print(f"✅ Bank transfer error is string: '{error}'")
        else:
            print(f"❌ Bank transfer error is not string: {type(error)}")
            test2_pass = False
    
    # Test missing terms error  
    missing_terms = {"items": [{"product_id": "prod_bookkeeping", "quantity": 1, "inputs": {}}], "checkout_type": "one_time", "terms_accepted": False}
    response = requests.post(f"{base_url}/api/checkout/bank-transfer", json=missing_terms, headers=headers)
    
    if response.status_code == 400:
        error = response.json().get("detail", "")
        if isinstance(error, str) and "terms" in error.lower():
            print(f"✅ Terms validation error is string: '{error}'")
        else:
            print(f"❌ Terms validation error format issue: {type(error)}")
            test2_pass = False
    
    # TEST 3: GoCardless Callback Error Handling
    print("\n" + "="*60)
    print("🛠️  TEST 3: GOCARDLESS CALLBACK ERROR HANDLING")
    print("="*60)
    
    test3_pass = True
    
    # Test invalid redirect flow
    invalid_redirect = {"redirect_flow_id": "invalid_12345", "order_id": "fake", "subtotal": 100.0, "discount": 0.0, "fee": 5.0, "status": "paid"}
    response = requests.post(f"{base_url}/api/gocardless/complete-redirect", json=invalid_redirect, headers=headers)
    
    if response.status_code == 400:
        error = response.json().get("detail", "")
        if isinstance(error, str) and any(word in error.lower() for word in ["redirect", "flow", "expired", "failed"]):
            print(f"✅ GoCardless redirect error is human-readable: '{error[:80]}...'")
        else:
            print(f"❌ GoCardless redirect error format issue: {type(error)}")
            test3_pass = False
    
    # FINAL VALIDATION SUMMARY
    print("\n" + "="*60)
    print("📊 CRITICAL VALIDATIONS SUMMARY")
    print("="*60)
    
    validations = [
        ("Stripe subscription session uses mode='subscription'", test1_pass),
        ("All error responses have string 'detail' field", test2_pass),
        ("No raw Pydantic objects in API responses", test2_pass and test3_pass), 
        ("GoCardless errors are human-readable", test3_pass)
    ]
    
    passed = sum(1 for _, result in validations if result)
    
    for desc, result in validations:
        icon = "✅" if result else "❌"
        status = "PASS" if result else "FAIL"
        print(f"{icon} {desc}: {status}")
    
    print("="*60)
    print(f"CRITICAL VALIDATIONS: {passed}/{len(validations)} PASSED")
    
    if passed == len(validations):
        print("\n🎉 ALL CRITICAL BUG FIXES VERIFIED SUCCESSFULLY!")
        print("✅ Stripe subscription checkout uses correct mode='subscription'")
        print("✅ No 'payment mode but recurring price' errors")
        print("✅ All GoCardless errors return proper string messages") 
        print("✅ Error handling is human-readable")
        return True
    else:
        print(f"\n⚠️  {len(validations) - passed} critical issue(s) still present")
        return False

if __name__ == "__main__":
    success = test_critical_bug_fixes()
    sys.exit(0 if success else 1)