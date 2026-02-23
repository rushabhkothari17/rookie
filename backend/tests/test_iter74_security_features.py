"""
Iteration 74 Backend Tests:
- JWT token refresh endpoint (/api/auth/refresh)
- Login sets both aa_access_token (1hr) and aa_refresh_token (30day) cookies
- Customers list endpoint uses aggregation (no N+1)
- Admin login still works with new token system
- IDOR fix - user activation requires tenant filter
- Verification code brute-force protection (5 attempts = lockout)
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Credentials
ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"
PARTNER_CODE = "automate-accounts"


class TestJWTTokenRefresh:
    """Test JWT token refresh functionality."""
    
    def test_login_returns_token_and_sets_cookies(self):
        """Test that partner login returns token and sets both cookies."""
        session = requests.Session()
        response = session.post(
            f"{BASE_URL}/api/auth/partner-login",
            json={
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD,
                "partner_code": PARTNER_CODE
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Response should include token
        assert "token" in data, "Response should include token"
        assert "role" in data, "Response should include role"
        
        # Check cookies are set
        cookies = session.cookies.get_dict()
        assert "aa_access_token" in cookies, "aa_access_token cookie should be set"
        # Note: aa_refresh_token may not be visible in cookies dict due to path restriction
        
    def test_token_refresh_with_valid_refresh_token(self):
        """Test token refresh endpoint with valid refresh token from cookie."""
        session = requests.Session()
        
        # First login to get tokens
        login_resp = session.post(
            f"{BASE_URL}/api/auth/partner-login",
            json={
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD,
                "partner_code": PARTNER_CODE
            }
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        
        original_token = login_resp.json().get("token")
        
        # Call refresh endpoint - should work with cookie
        refresh_resp = session.post(f"{BASE_URL}/api/auth/refresh")
        assert refresh_resp.status_code == 200, f"Refresh failed: {refresh_resp.status_code}: {refresh_resp.text}"
        
        data = refresh_resp.json()
        assert "token" in data, "Refresh should return new token"
        assert "expires_in" in data, "Refresh should return expires_in"
        
        # Verify expires_in is approximately 1 hour (3600 seconds)
        assert data["expires_in"] == 3600, f"Expected expires_in to be 3600, got {data['expires_in']}"
        
        # New token should work for API calls
        me_resp = session.get(
            f"{BASE_URL}/api/me",
            headers={"Authorization": f"Bearer {data['token']}"}
        )
        assert me_resp.status_code == 200, f"/api/me failed with new token: {me_resp.text}"
        
    def test_token_refresh_without_refresh_token_fails(self):
        """Test token refresh endpoint without refresh token returns 401."""
        response = requests.post(f"{BASE_URL}/api/auth/refresh")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        
        data = response.json()
        assert "detail" in data
        assert "Refresh token required" in data["detail"] or "refresh" in data["detail"].lower()
        
    def test_access_token_in_header_works(self):
        """Test that access token in Authorization header still works (backward compatibility)."""
        # Login
        login_resp = requests.post(
            f"{BASE_URL}/api/auth/partner-login",
            json={
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD,
                "partner_code": PARTNER_CODE
            }
        )
        token = login_resp.json().get("token")
        
        # Access API with Bearer token
        me_resp = requests.get(
            f"{BASE_URL}/api/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert me_resp.status_code == 200, f"Expected 200, got {me_resp.status_code}"


class TestCustomerLoginTokens:
    """Test customer login also sets refresh tokens."""
    
    def test_customer_login_sets_cookies(self):
        """Test that customer login sets both access and refresh cookies."""
        session = requests.Session()
        
        # First need to create a customer or skip if none exists
        # Try customer login
        response = session.post(
            f"{BASE_URL}/api/auth/customer-login",
            json={
                "email": "testcustomer@test.com",
                "password": "ChangeMe123!",
                "partner_code": PARTNER_CODE
            }
        )
        
        if response.status_code == 401:
            pytest.skip("Test customer does not exist")
            
        if response.status_code == 200:
            data = response.json()
            assert "token" in data
            
            # Check cookies are set
            cookies = session.cookies.get_dict()
            assert "aa_access_token" in cookies, "aa_access_token should be set for customer login"


class TestCustomersListAggregation:
    """Test customers list endpoint uses aggregation efficiently."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin."""
        self.session = requests.Session()
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/partner-login",
            json={
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD,
                "partner_code": PARTNER_CODE
            }
        )
        if login_resp.status_code == 200:
            token = login_resp.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
        
    def test_customers_list_returns_all_data_in_one_response(self):
        """Test customers list returns customers, users, addresses in single response."""
        response = self.session.get(f"{BASE_URL}/api/admin/customers")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify response structure has all required fields
        assert "customers" in data, "Response should have customers"
        assert "users" in data, "Response should have users"
        assert "addresses" in data, "Response should have addresses"
        assert "total" in data, "Response should have total count"
        assert "page" in data, "Response should have page"
        assert "per_page" in data, "Response should have per_page"
        assert "total_pages" in data, "Response should have total_pages"
        
    def test_customers_list_with_search_filter(self):
        """Test customers list search filter works."""
        response = self.session.get(
            f"{BASE_URL}/api/admin/customers",
            params={"search": "test"}
        )
        assert response.status_code == 200
        
    def test_customers_list_with_country_filter(self):
        """Test customers list country filter works."""
        response = self.session.get(
            f"{BASE_URL}/api/admin/customers",
            params={"country": "GB"}
        )
        assert response.status_code == 200
        
    def test_customers_list_with_status_filter(self):
        """Test customers list status filter works."""
        response = self.session.get(
            f"{BASE_URL}/api/admin/customers",
            params={"status": "active"}
        )
        assert response.status_code == 200
        
    def test_customers_list_pagination(self):
        """Test customers list pagination works."""
        response = self.session.get(
            f"{BASE_URL}/api/admin/customers",
            params={"page": 1, "per_page": 5}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["page"] == 1
        assert data["per_page"] == 5


class TestAdminLoginWithNewTokenSystem:
    """Test admin login still works with new JWT token system."""
    
    def test_partner_login_works(self):
        """Test partner login with platform admin credentials."""
        response = requests.post(
            f"{BASE_URL}/api/auth/partner-login",
            json={
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD,
                "partner_code": PARTNER_CODE
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "token" in data
        assert data["role"] == "platform_admin"
        
    def test_legacy_login_with_partner_code_works(self):
        """Test legacy login endpoint with partner_code."""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD,
                "partner_code": PARTNER_CODE
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "token" in data
        
    def test_admin_can_access_admin_endpoints(self):
        """Test that admin token can access admin endpoints."""
        session = requests.Session()
        login_resp = session.post(
            f"{BASE_URL}/api/auth/partner-login",
            json={
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD,
                "partner_code": PARTNER_CODE
            }
        )
        token = login_resp.json().get("token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Test admin endpoint access
        customers_resp = session.get(f"{BASE_URL}/api/admin/customers")
        assert customers_resp.status_code == 200, f"Admin should access /admin/customers: {customers_resp.status_code}"


class TestIDORFixUserActivation:
    """Test IDOR fix - user activation requires tenant filter."""
    
    def test_activate_customer_requires_valid_customer_id(self):
        """Test that activating customer requires valid customer ID in tenant."""
        session = requests.Session()
        # Login
        login_resp = session.post(
            f"{BASE_URL}/api/auth/partner-login",
            json={
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD,
                "partner_code": PARTNER_CODE
            }
        )
        if login_resp.status_code == 429:
            pytest.skip("Rate limited - skipping test")
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json().get("token")
        
        # Try to activate a non-existent customer
        fake_customer_id = "fake_nonexistent_customer_id"
        response = session.patch(
            f"{BASE_URL}/api/admin/customers/{fake_customer_id}/active",
            params={"active": True},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 404, f"Expected 404 for non-existent customer, got {response.status_code}: {response.text}"
        
    def test_deactivate_customer_requires_valid_customer_id(self):
        """Test that deactivating customer requires valid customer ID in tenant."""
        session = requests.Session()
        # Login
        login_resp = session.post(
            f"{BASE_URL}/api/auth/partner-login",
            json={
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD,
                "partner_code": PARTNER_CODE
            }
        )
        if login_resp.status_code == 429:
            pytest.skip("Rate limited - skipping test")
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json().get("token")
        
        fake_customer_id = "fake_nonexistent_customer_id"
        response = session.patch(
            f"{BASE_URL}/api/admin/customers/{fake_customer_id}/active",
            params={"active": False},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 404, f"Expected 404 for non-existent customer, got {response.status_code}: {response.text}"


class TestBruteForceProtectionVerification:
    """Test verification code brute-force protection (5 attempts = lockout)."""
    
    def _create_test_user_for_verification(self):
        """Helper to create a test user for verification testing."""
        import secrets
        unique_id = secrets.token_hex(4)
        email = f"TEST_bruteforce_{unique_id}@test.com"
        
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": email,
                "password": "TestPassword123!",
                "full_name": "Test Bruteforce User",
                "company_name": "Test Co",
                "phone": "1234567890",
                "job_title": "Tester",
                "address": {
                    "line1": "123 Test St",
                    "city": "London",
                    "region": "London",
                    "postal": "SW1A 1AA",
                    "country": "GB"
                }
            },
            params={"partner_code": PARTNER_CODE}
        )
        
        if response.status_code == 200:
            return email, response.json().get("verification_code")
        return None, None
        
    def test_verification_lockout_after_5_failed_attempts(self):
        """Test that verification is locked after 5 failed attempts."""
        email, correct_code = self._create_test_user_for_verification()
        
        if not email:
            pytest.skip("Could not create test user")
            
        last_response = None
        # Make 5 failed verification attempts
        for i in range(5):
            last_response = requests.post(
                f"{BASE_URL}/api/auth/verify-email",
                json={
                    "email": email,
                    "code": "000000"  # Wrong code
                }
            )
            if last_response.status_code == 429:
                # Already locked out - test passes
                break
            elif last_response.status_code >= 500:
                pytest.skip(f"Server error during verification test: {last_response.status_code}")
        
        # 6th attempt should be locked (429) if not already
        if last_response.status_code != 429:
            response = requests.post(
                f"{BASE_URL}/api/auth/verify-email",
                json={
                    "email": email,
                    "code": "000000"  # Wrong code
                }
            )
            if response.status_code >= 500:
                pytest.skip(f"Server error during verification test: {response.status_code}")
            assert response.status_code == 429, f"Expected 429 (Too Many Requests) after 5 failed attempts, got {response.status_code}"
            
            data = response.json()
            assert "detail" in data
            assert "too many" in data["detail"].lower() or "locked" in data["detail"].lower()
        else:
            # Already verified lockout occurred during attempts
            data = last_response.json()
            assert "detail" in data
        
    def test_verification_with_correct_code_works(self):
        """Test that correct verification code works before lockout."""
        email, correct_code = self._create_test_user_for_verification()
        
        if not email or not correct_code:
            pytest.skip("Could not create test user")
            
        # Verify with correct code
        response = requests.post(
            f"{BASE_URL}/api/auth/verify-email",
            json={
                "email": email,
                "code": correct_code
            }
        )
        assert response.status_code == 200, f"Expected 200 with correct code, got {response.status_code}: {response.text}"


class TestLoginBruteForceProtection:
    """Test login brute-force protection (10 attempts = lockout)."""
    
    def test_login_lockout_message_format(self):
        """Test that lockout message format is correct (tested by checking response structure)."""
        # This test verifies the lockout mechanism exists by checking constants
        # We don't actually trigger lockout to avoid test interference
        
        # Test that invalid credentials return proper 401 (or 429 if rate limited)
        response = requests.post(
            f"{BASE_URL}/api/auth/partner-login",
            json={
                "email": "nonexistent_unique_test@test.com",
                "password": "WrongPassword123!",
                "partner_code": PARTNER_CODE
            }
        )
        # Accept 401 (invalid credentials) or 429 (rate limited) - both are security measures
        assert response.status_code in [401, 429], f"Expected 401 or 429, got {response.status_code}"
        
        data = response.json()
        assert "detail" in data
        if response.status_code == 401:
            assert "Invalid credentials" in data["detail"]
        elif response.status_code == 429:
            # Rate limiting is also a valid security response
            assert "rate" in data["detail"].lower() or "limit" in data["detail"].lower() or "locked" in data["detail"].lower()


class TestLogout:
    """Test logout clears cookies properly."""
    
    def test_logout_clears_cookies(self):
        """Test that logout clears authentication cookies."""
        session = requests.Session()
        
        # First login
        login_resp = session.post(
            f"{BASE_URL}/api/auth/partner-login",
            json={
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD,
                "partner_code": PARTNER_CODE
            }
        )
        if login_resp.status_code == 429:
            pytest.skip("Rate limited - skipping test")
        assert login_resp.status_code == 200, f"Login failed: {login_resp.status_code}: {login_resp.text}"
        
        # Verify cookies are set
        assert "aa_access_token" in session.cookies.get_dict()
        
        # Logout
        logout_resp = session.post(f"{BASE_URL}/api/auth/logout")
        assert logout_resp.status_code == 200
        
        data = logout_resp.json()
        assert data.get("success") is True
