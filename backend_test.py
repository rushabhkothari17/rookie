#!/usr/bin/env python3
"""
Backend Testing Suite for Partner Admin Creation - Access Level Override
Testing the specific fix for Partner Super Admin Access Level Override
"""

import asyncio
import json
import os
import sys
from typing import Dict, Any

# Add backend directory to path for imports
sys.path.insert(0, "/app/backend")

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv("/app/frontend/.env")

# Get backend URL from environment
BACKEND_URL = os.getenv("REACT_APP_BACKEND_URL", "https://admin-column-headers.preview.emergentagent.com")
API_BASE = f"{BACKEND_URL}/api"

class BackendTester:
    def __init__(self):
        self.admin_token = None
        self.test_tenant_id = None
        
    def log_test(self, test_name: str, status: str, details: str = ""):
        """Log test results with clear formatting."""
        status_emoji = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{status_emoji} {test_name}: {status}")
        if details:
            print(f"   Details: {details}")
        print()
    
    async def test_platform_admin_login(self):
        """Test 1: Platform admin can login successfully."""
        try:
            response = requests.post(f"{API_BASE}/auth/login", json={
                "email": "admin@automateaccounts.local",
                "password": "ChangeMe123!",
                "login_type": "platform"
            }, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                print(f"Login response data: {data}")  # Debug output
                self.admin_token = data.get("access_token") or data.get("token")  # Try both fields
                if self.admin_token:
                    self.log_test("Platform Admin Login", "PASS", "Successfully logged in as platform admin")
                    return True
                else:
                    self.log_test("Platform Admin Login", "FAIL", f"No access token in response. Response: {data}")
                    return False
            else:
                self.log_test("Platform Admin Login", "FAIL", f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Platform Admin Login", "FAIL", f"Exception: {str(e)}")
            return False

    async def test_create_test_tenant(self):
        """Test 2: Create a test tenant for partner admin testing."""
        if not self.admin_token:
            self.log_test("Create Test Tenant", "FAIL", "No admin token available")
            return False
            
        try:
            # Use a timestamp to ensure uniqueness
            import time
            unique_suffix = str(int(time.time() * 1000))[-8:]  # Last 8 digits
            
            response = requests.post(f"{API_BASE}/admin/tenants", 
                json={
                    "name": f"Test Partner Super Admin Org {unique_suffix}",
                    "code": f"test-super-admin-{unique_suffix}",
                    "status": "active"
                },
                headers={"Authorization": f"Bearer {self.admin_token}"},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                self.test_tenant_id = data["tenant"]["id"]
                self.log_test("Create Test Tenant", "PASS", f"Created tenant with ID: {self.test_tenant_id}")
                return True
            else:
                self.log_test("Create Test Tenant", "FAIL", f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Create Test Tenant", "FAIL", f"Exception: {str(e)}")
            return False

    async def test_partner_super_admin_access_level_override(self):
        """Test 3: Partner Super Admin access_level override - CRITICAL TEST from review request."""
        if not self.admin_token or not self.test_tenant_id:
            self.log_test("Partner Super Admin Access Level Override", "FAIL", "Missing admin token or tenant ID")
            return False
            
        try:
            # Create partner_super_admin with EXPLICIT access_level="read_only"
            response = requests.post(f"{API_BASE}/admin/tenants/{self.test_tenant_id}/create-admin",
                json={
                    "tenant_id": self.test_tenant_id,  # Required in body as per model
                    "email": "super.admin@testorg.com",
                    "full_name": "Test Super Admin",
                    "password": "TestPass123!",
                    "role": "partner_super_admin",
                    "access_level": "read_only"  # EXPLICITLY setting to read_only
                },
                headers={"Authorization": f"Bearer {self.admin_token}"},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                user_id = data.get("user_id")
                
                # Verify in database by getting the user details
                users_response = requests.get(f"{API_BASE}/admin/tenants/{self.test_tenant_id}/users",
                    headers={"Authorization": f"Bearer {self.admin_token}"},
                    timeout=30
                )
                
                if users_response.status_code == 200:
                    users_data = users_response.json()
                    super_admin_user = None
                    
                    for user in users_data.get("users", []):
                        if user.get("email") == "super.admin@testorg.com":
                            super_admin_user = user
                            break
                    
                    if super_admin_user:
                        stored_access_level = super_admin_user.get("access_level")
                        if stored_access_level == "full_access":
                            self.log_test("Partner Super Admin Access Level Override", "PASS", 
                                        f"✅ CORRECT: access_level stored as 'full_access' (was overridden from 'read_only')")
                            return True
                        else:
                            self.log_test("Partner Super Admin Access Level Override", "FAIL", 
                                        f"❌ BUG: access_level stored as '{stored_access_level}' (should be 'full_access')")
                            return False
                    else:
                        self.log_test("Partner Super Admin Access Level Override", "FAIL", "User not found in tenant users list")
                        return False
                else:
                    self.log_test("Partner Super Admin Access Level Override", "FAIL", f"Failed to get users: {users_response.text}")
                    return False
            else:
                self.log_test("Partner Super Admin Access Level Override", "FAIL", f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Partner Super Admin Access Level Override", "FAIL", f"Exception: {str(e)}")
            return False

    async def test_partner_admin_read_only_acceptance(self):
        """Test 4: Regular partner_admin still accepts read_only access level."""
        if not self.admin_token or not self.test_tenant_id:
            self.log_test("Partner Admin Read Only Acceptance", "FAIL", "Missing admin token or tenant ID")
            return False
            
        try:
            # Create partner_admin with access_level="read_only"
            response = requests.post(f"{API_BASE}/admin/tenants/{self.test_tenant_id}/create-admin",
                json={
                    "tenant_id": self.test_tenant_id,  # Required in body as per model
                    "email": "regular.admin@testorg.com",
                    "full_name": "Test Regular Admin", 
                    "password": "TestPass123!",
                    "role": "partner_admin",
                    "access_level": "read_only"
                },
                headers={"Authorization": f"Bearer {self.admin_token}"},
                timeout=30
            )
            
            if response.status_code == 200:
                # Verify the access level was stored correctly
                users_response = requests.get(f"{API_BASE}/admin/tenants/{self.test_tenant_id}/users",
                    headers={"Authorization": f"Bearer {self.admin_token}"},
                    timeout=30
                )
                
                if users_response.status_code == 200:
                    users_data = users_response.json()
                    regular_admin_user = None
                    
                    for user in users_data.get("users", []):
                        if user.get("email") == "regular.admin@testorg.com":
                            regular_admin_user = user
                            break
                    
                    if regular_admin_user:
                        stored_access_level = regular_admin_user.get("access_level")
                        if stored_access_level == "read_only":
                            self.log_test("Partner Admin Read Only Acceptance", "PASS", 
                                        f"✅ CORRECT: partner_admin access_level stored as 'read_only'")
                            return True
                        else:
                            self.log_test("Partner Admin Read Only Acceptance", "FAIL", 
                                        f"❌ BUG: partner_admin access_level stored as '{stored_access_level}' (should be 'read_only')")
                            return False
                    else:
                        self.log_test("Partner Admin Read Only Acceptance", "FAIL", "Regular admin user not found")
                        return False
                else:
                    self.log_test("Partner Admin Read Only Acceptance", "FAIL", f"Failed to get users: {users_response.text}")
                    return False
            else:
                self.log_test("Partner Admin Read Only Acceptance", "FAIL", f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Partner Admin Read Only Acceptance", "FAIL", f"Exception: {str(e)}")
            return False

    async def cleanup_test_tenant(self):
        """Cleanup: Delete the test tenant."""
        if self.admin_token and self.test_tenant_id:
            try:
                # Deactivate the test tenant
                response = requests.post(f"{API_BASE}/admin/tenants/{self.test_tenant_id}/deactivate",
                    headers={"Authorization": f"Bearer {self.admin_token}"},
                    timeout=30
                )
                if response.status_code == 200:
                    self.log_test("Cleanup Test Tenant", "PASS", "Test tenant deactivated successfully")
                else:
                    self.log_test("Cleanup Test Tenant", "FAIL", f"Failed to deactivate: {response.text}")
            except Exception as e:
                self.log_test("Cleanup Test Tenant", "FAIL", f"Cleanup failed: {str(e)}")

    async def run_all_tests(self):
        """Run all tests in sequence."""
        print("🔍 BACKEND TESTING - Partner Super Admin Access Level Override")
        print("=" * 80)
        print(f"Testing against: {API_BASE}")
        print()
        
        test_results = []
        
        # Test 1: Platform Admin Login
        result1 = await self.test_platform_admin_login()
        test_results.append(("Platform Admin Login", result1))
        
        if result1:
            # Test 2: Create Test Tenant
            result2 = await self.test_create_test_tenant()
            test_results.append(("Create Test Tenant", result2))
            
            if result2:
                # Test 3: CRITICAL - Partner Super Admin Access Level Override
                result3 = await self.test_partner_super_admin_access_level_override()
                test_results.append(("Partner Super Admin Access Level Override", result3))
                
                # Test 4: Partner Admin Read Only Acceptance
                result4 = await self.test_partner_admin_read_only_acceptance()
                test_results.append(("Partner Admin Read Only Acceptance", result4))
                
                # Cleanup
                await self.cleanup_test_tenant()
        
        # Summary
        print("=" * 80)
        print("📊 TEST SUMMARY")
        print("=" * 80)
        
        passed = sum(1 for _, result in test_results if result)
        total = len(test_results)
        
        for test_name, result in test_results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status} {test_name}")
        
        print()
        print(f"Results: {passed}/{total} tests passed ({(passed/total*100):.1f}%)")
        
        if passed == total:
            print("🎉 ALL TESTS PASSED! Partner Super Admin Access Level Override is working correctly.")
        else:
            print("⚠️  SOME TESTS FAILED! Review the failures above.")
        
        return passed == total

async def main():
    tester = BackendTester()
    success = await tester.run_all_tests()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)