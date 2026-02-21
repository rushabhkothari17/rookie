import os
import requests
from typing import Optional, Dict, Any

GOCARDLESS_API_URL = "https://api-sandbox.gocardless.com"

def get_gocardless_token() -> str:
    return os.environ.get("GOCARDLESS_ACCESS_TOKEN", "")

def create_gocardless_customer(email: str, given_name: str, family_name: str, company_name: str = "") -> Optional[Dict[str, Any]]:
    """Create a GoCardless customer"""
    token = get_gocardless_token()
    if not token:
        return None
    
    try:
        response = requests.post(
            f"{GOCARDLESS_API_URL}/customers",
            json={
                "customers": {
                    "email": email,
                    "given_name": given_name,
                    "family_name": family_name,
                    "company_name": company_name,
                }
            },
            headers={
                "Authorization": f"Bearer {token}",
                "GoCardless-Version": "2015-07-06",
                "Content-Type": "application/json"
            },
            timeout=10
        )
        if response.status_code == 201:
            return response.json()["customers"]
    except Exception as e:
        print(f"GoCardless customer creation failed: {e}")
    return None

def create_redirect_flow(session_token: str, success_redirect_url: str, description: str) -> Optional[Dict[str, Any]]:
    """Create a GoCardless redirect flow for mandate setup"""
    token = get_gocardless_token()
    if not token:
        return None
    
    try:
        response = requests.post(
            f"{GOCARDLESS_API_URL}/redirect_flows",
            json={
                "redirect_flows": {
                    "session_token": session_token,
                    "success_redirect_url": success_redirect_url,
                    "description": description,
                }
            },
            headers={
                "Authorization": f"Bearer {token}",
                "GoCardless-Version": "2015-07-06",
                "Content-Type": "application/json"
            },
            timeout=10
        )
        if response.status_code == 201:
            return response.json()["redirect_flows"]
    except Exception as e:
        print(f"GoCardless redirect flow creation failed: {e}")
    return None

def complete_redirect_flow(redirect_flow_id: str) -> Optional[Dict[str, Any]]:
    """Complete a GoCardless redirect flow after user returns"""
    token = get_gocardless_token()
    if not token:
        return None
    
    try:
        response = requests.post(
            f"{GOCARDLESS_API_URL}/redirect_flows/{redirect_flow_id}/actions/complete",
            json={},
            headers={
                "Authorization": f"Bearer {token}",
                "GoCardless-Version": "2015-07-06",
                "Content-Type": "application/json"
            },
            timeout=10
        )
        if response.status_code == 200:
            return response.json()["redirect_flows"]
    except Exception as e:
        print(f"GoCardless redirect flow completion failed: {e}")
    return None
