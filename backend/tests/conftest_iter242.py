"""Shared fixtures for iter242 bug fix tests"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"
CUSTOMER_EMAIL = "TEST_bugfix242_customer@example.com"
CUSTOMER_PASSWORD = "Test@bugfix242!"
PARTNER_CODE = "testpartner242"

@pytest.fixture(scope="session")
def admin_token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
    })
    assert resp.status_code == 200
    return resp.json()["token"]

@pytest.fixture(scope="session")
def customer_token():
    resp = requests.post(f"{BASE_URL}/api/auth/customer-login", json={
        "email": CUSTOMER_EMAIL, "password": CUSTOMER_PASSWORD, "partner_code": PARTNER_CODE
    })
    if resp.status_code == 200:
        return resp.json()["token"]
    pytest.skip(f"Customer login failed: {resp.status_code}")
