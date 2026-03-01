#!/usr/bin/env python3
"""
Backend Test Suite for Partner Admin Creation with Permissions Flow
Tests the new granular permissions system for Partner Admin users.
"""

import asyncio
import aiohttp
import json
import sys
from typing import Dict, Any, Optional


class PartnerAdminTester:
    def __init__(self):
        # Use the production backend URL from frontend/.env
        self.base_url = "https://partner-billing-hub-1.preview.emergentagent.com/api"
        self.session: Optional[aiohttp.ClientSession] = None
        self.admin_token: Optional[str] = None
        self.created_tenant_id: Optional[str] = None
        self.created_users: list = []
        
    async def setup_session(self):
        """Initialize aiohttp session with proper headers."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"Content-Type": "application/json"}
        )
    
    async def cleanup(self):
        """Clean up the session."""
        if self.session:
            await self.session.close()
    
    async def login_platform_admin(self) -> bool:
        """Step 1: Login as Platform Admin."""
        print("🔐 Step 1: Logging in as Platform Admin...")
        
        login_data = {
            "email": "admin@automateaccounts.local",
            "password": "ChangeMe123!"
        }
        
        try:
            async with self.session.post(f"{self.base_url}/auth/login", json=login_data) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    print(f"Login response: {result}")  # Debug output
                    self.admin_token = result.get("token")  # Fix: use "token" not "access_token"
                    if self.admin_token:
                        # Update session headers with auth token
                        self.session.headers.update({"Authorization": f"Bearer {self.admin_token}"})
                        print("✅ Platform Admin login successful")
                        return True
                    else:
                        print("❌ No access token received")
                        print(f"Full response: {result}")
                        return False
                else:
                    error_text = await resp.text()
                    print(f"❌ Platform Admin login failed: {resp.status} - {error_text}")
                    return False
        except Exception as e:
            print(f"❌ Platform Admin login error: {e}")
            return False
    
    async def create_partner_org(self) -> bool:
        """Step 2: Create a new Partner Organization."""
        print("\n🏢 Step 2: Creating Test Partner Organization...")
        
        org_data = {
            "name": "Test Partner Org",
            "code": "test-partner-permissions",
            "status": "active"
        }
        
        try:
            async with self.session.post(f"{self.base_url}/admin/tenants", json=org_data) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    tenant = result.get("tenant", {})
                    self.created_tenant_id = tenant.get("id")
                    if self.created_tenant_id:
                        print(f"✅ Partner Organization created: {tenant.get('name')} (ID: {self.created_tenant_id})")
                        return True
                    else:
                        print("❌ No tenant ID received")
                        return False
                elif resp.status == 400:
                    error_data = await resp.json()
                    if "already in use" in error_data.get("detail", ""):
                        # Try to find existing tenant
                        print("ℹ️  Partner code already exists, finding existing tenant...")
                        return await self.find_existing_tenant()
                    else:
                        print(f"❌ Partner org creation failed: {error_data.get('detail')}")
                        return False
                else:
                    error_text = await resp.text()
                    print(f"❌ Partner org creation failed: {resp.status} - {error_text}")
                    return False
        except Exception as e:
            print(f"❌ Partner org creation error: {e}")
            return False
    
    async def find_existing_tenant(self) -> bool:
        """Find existing tenant if code is already in use."""
        try:
            async with self.session.get(f"{self.base_url}/admin/tenants") as resp:
                if resp.status == 200:
                    result = await resp.json()
                    tenants = result.get("tenants", [])
                    for tenant in tenants:
                        if tenant.get("code") == "test-partner-permissions":
                            self.created_tenant_id = tenant.get("id")
                            print(f"✅ Found existing Partner Organization: {tenant.get('name')} (ID: {self.created_tenant_id})")
                            return True
                    print("❌ Could not find existing tenant")
                    return False
                else:
                    print(f"❌ Failed to list tenants: {resp.status}")
                    return False
        except Exception as e:
            print(f"❌ Error finding tenant: {e}")
            return False
    
    async def create_partner_admin_with_permissions(self) -> bool:
        """Step 3: Create Partner Admin with specific permissions."""
        print(f"\n👤 Step 3: Creating Partner Admin with read-only permissions...")
        
        admin_data = {
            "email": "partner.admin@testorg.local",
            "full_name": "Test Partner Admin",
            "password": "SecurePass123!",
            "role": "partner_admin",  # NOT partner_super_admin
            "access_level": "read_only",
            "modules": ["customers", "orders"]
        }
        
        try:
            async with self.session.post(f"{self.base_url}/admin/tenants/{self.created_tenant_id}/create-admin", json=admin_data) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    user_id = result.get("user_id")
                    if user_id:
                        self.created_users.append({"id": user_id, "email": admin_data["email"], "role": "partner_admin"})
                        print(f"✅ Partner Admin created: {admin_data['email']} (ID: {user_id})")
                        return True
                    else:
                        print("❌ No user ID received")
                        return False
                else:
                    error_text = await resp.text()
                    print(f"❌ Partner Admin creation failed: {resp.status} - {error_text}")
                    return False
        except Exception as e:
            print(f"❌ Partner Admin creation error: {e}")
            return False
    
    async def create_partner_super_admin(self) -> bool:
        """Step 5: Create Partner Super Admin and verify it defaults to full access."""
        print(f"\n👑 Step 5: Creating Partner Super Admin...")
        
        super_admin_data = {
            "email": "partner.superadmin@testorg.local", 
            "full_name": "Test Partner Super Admin",
            "password": "SecurePass123!",
            "role": "partner_super_admin",
            "access_level": "read_only",  # This should be ignored/defaulted to full
            "modules": ["customers"]  # This should be ignored for super admin
        }
        
        try:
            async with self.session.post(f"{self.base_url}/admin/tenants/{self.created_tenant_id}/create-admin", json=super_admin_data) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    user_id = result.get("user_id")
                    if user_id:
                        self.created_users.append({"id": user_id, "email": super_admin_data["email"], "role": "partner_super_admin"})
                        print(f"✅ Partner Super Admin created: {super_admin_data['email']} (ID: {user_id})")
                        return True
                    else:
                        print("❌ No user ID received")
                        return False
                else:
                    error_text = await resp.text()
                    print(f"❌ Partner Super Admin creation failed: {resp.status} - {error_text}")
                    return False
        except Exception as e:
            print(f"❌ Partner Super Admin creation error: {e}")
            return False
    
    async def verify_user_permissions(self) -> bool:
        """Step 4 & 6: Verify users have correct permissions via GET /api/admin/users."""
        print(f"\n🔍 Step 4 & 6: Verifying user permissions in database...")
        
        # Get tenant users to verify permissions
        try:
            async with self.session.get(f"{self.base_url}/admin/tenants/{self.created_tenant_id}/users") as resp:
                if resp.status == 200:
                    result = await resp.json()
                    users = result.get("users", [])
                    
                    verified_count = 0
                    for created_user in self.created_users:
                        user_found = False
                        for db_user in users:
                            if db_user.get("email") == created_user["email"]:
                                user_found = True
                                email = db_user.get("email")
                                role = db_user.get("role")
                                access_level = db_user.get("access_level")
                                modules = db_user.get("permissions", {}).get("modules", [])
                                
                                print(f"\n📋 User: {email}")
                                print(f"   Role: {role}")
                                print(f"   Access Level: {access_level}")
                                print(f"   Modules: {modules}")
                                
                                if created_user["role"] == "partner_admin":
                                    # Verify partner_admin has expected permissions
                                    if (role == "partner_admin" and 
                                        access_level == "read_only" and 
                                        set(modules) == {"customers", "orders"}):
                                        print(f"   ✅ Partner Admin permissions correct")
                                        verified_count += 1
                                    else:
                                        print(f"   ❌ Partner Admin permissions incorrect")
                                        print(f"      Expected: role=partner_admin, access_level=read_only, modules=['customers', 'orders']")
                                        print(f"      Actual: role={role}, access_level={access_level}, modules={modules}")
                                        
                                elif created_user["role"] == "partner_super_admin":
                                    # Verify partner_super_admin has full access (should ignore access_level)
                                    expected_access = access_level == "full_access" or access_level is None
                                    if role == "partner_super_admin" and expected_access:
                                        print(f"   ✅ Partner Super Admin permissions correct (access_level defaulted to full)")
                                        verified_count += 1
                                    else:
                                        print(f"   ❌ Partner Super Admin permissions incorrect")
                                        print(f"      Expected: role=partner_super_admin, access_level=full_access (or None)")
                                        print(f"      Actual: role={role}, access_level={access_level}")
                                break
                        
                        if not user_found:
                            print(f"❌ User {created_user['email']} not found in tenant users")
                    
                    return verified_count == len(self.created_users)
                else:
                    error_text = await resp.text()
                    print(f"❌ Failed to get tenant users: {resp.status} - {error_text}")
                    return False
        except Exception as e:
            print(f"❌ Error verifying permissions: {e}")
            return False
    
    async def run_full_test(self) -> bool:
        """Run the complete Partner Admin Creation with Permissions test flow."""
        print("🚀 Starting Partner Admin Creation with Permissions Test Flow")
        print("=" * 70)
        
        await self.setup_session()
        
        try:
            # Step 1: Login as Platform Admin
            if not await self.login_platform_admin():
                return False
            
            # Step 2: Create Partner Organization
            if not await self.create_partner_org():
                return False
            
            # Step 3: Create Partner Admin with permissions
            if not await self.create_partner_admin_with_permissions():
                return False
            
            # Step 5: Create Partner Super Admin
            if not await self.create_partner_super_admin():
                return False
            
            # Step 4 & 6: Verify all permissions
            if not await self.verify_user_permissions():
                return False
            
            print("\n" + "=" * 70)
            print("🎉 All Partner Admin Creation with Permissions tests PASSED!")
            return True
            
        except Exception as e:
            print(f"\n❌ Test execution error: {e}")
            return False
        finally:
            await self.cleanup()


async def main():
    """Main test execution."""
    tester = PartnerAdminTester()
    success = await tester.run_full_test()
    
    if success:
        print("\n✅ PARTNER ADMIN CREATION WITH PERMISSIONS FLOW: ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("\n❌ PARTNER ADMIN CREATION WITH PERMISSIONS FLOW: SOME TESTS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())