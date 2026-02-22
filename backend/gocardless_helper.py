import os
import requests
from typing import Optional, Dict, Any

GOCARDLESS_SANDBOX_URL = "https://api-sandbox.gocardless.com"
GOCARDLESS_LIVE_URL = "https://api.gocardless.com"


def get_gocardless_token(override: str = None) -> str:
    return override or os.environ.get("GOCARDLESS_ACCESS_TOKEN", "")


def get_gocardless_api_url(gc_env: str = None) -> str:
    env = gc_env or os.environ.get("GOCARDLESS_ENVIRONMENT", "sandbox")
    return GOCARDLESS_LIVE_URL if env == "live" else GOCARDLESS_SANDBOX_URL


def create_gocardless_customer(email: str, given_name: str, family_name: str, company_name: str = "", gc_token: str = None, gc_env: str = None) -> Optional[Dict[str, Any]]:
    """Create a GoCardless customer"""
    token = get_gocardless_token(gc_token)
    api_url = get_gocardless_api_url(gc_env)
    if not token:
        return None
    
    try:
        response = requests.post(
            f"{api_url}/customers",
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


def create_redirect_flow(session_token: str, success_redirect_url: str, description: str, gc_token: str = None, gc_env: str = None) -> Optional[Dict[str, Any]]:
    """Create a GoCardless redirect flow for mandate setup"""
    token = get_gocardless_token(gc_token)
    api_url = get_gocardless_api_url(gc_env)
    if not token:
        return None
    
    try:
        response = requests.post(
            f"{api_url}/redirect_flows",
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


def complete_redirect_flow(redirect_flow_id: str, session_token: str = "", gc_token: str = None, gc_env: str = None) -> Optional[Dict[str, Any]]:
    """Complete a GoCardless redirect flow after user returns"""
    token = get_gocardless_token(gc_token)
    api_url = get_gocardless_api_url(gc_env)
    if not token:
        print("GoCardless: no access token configured")
        return None
    
    try:
        body = {"data": {"session_token": session_token}} if session_token else {}
        response = requests.post(
            f"{api_url}/redirect_flows/{redirect_flow_id}/actions/complete",
            json=body,
            headers={
                "Authorization": f"Bearer {token}",
                "GoCardless-Version": "2015-07-06",
                "Content-Type": "application/json"
            },
            timeout=10
        )
        print(f"GoCardless complete redirect flow status: {response.status_code}, body: {response.text[:500]}")
        if response.status_code == 200:
            return response.json()["redirect_flows"]
    except Exception as e:
        print(f"GoCardless redirect flow completion failed: {e}")
    return None


def create_payment(amount: float, currency: str, mandate_id: str, description: str, metadata: Dict[str, Any] = None, charge_date: str = None, gc_token: str = None, gc_env: str = None) -> Optional[Dict[str, Any]]:
    """Create a GoCardless payment"""
    token = get_gocardless_token(gc_token)
    api_url = get_gocardless_api_url(gc_env)
    if not token:
        return None
    
    # Convert amount to pence/cents (GoCardless expects integer in minor units)
    amount_in_minor_units = int(amount * 100)
    
    try:
        payment_data = {
            "amount": amount_in_minor_units,
            "currency": currency.upper(),
            "links": {
                "mandate": mandate_id
            },
            "description": description,
            "metadata": metadata or {}
        }
        if charge_date:
            payment_data["charge_date"] = charge_date  # YYYY-MM-DD format

        response = requests.post(
            f"{api_url}/payments",
            json={"payments": payment_data},
            headers={
                "Authorization": f"Bearer {token}",
                "GoCardless-Version": "2015-07-06",
                "Content-Type": "application/json",
                "Idempotency-Key": metadata.get("order_id") or metadata.get("subscription_id") if metadata else ""
            },
            timeout=10
        )
        if response.status_code == 201:
            return response.json()["payments"]
    except Exception as e:
        print(f"GoCardless payment creation failed: {e}")
    return None


def get_payment_status(payment_id: str, gc_token: str = None, gc_env: str = None) -> Optional[Dict[str, Any]]:
    """Get GoCardless payment status"""
    token = get_gocardless_token(gc_token)
    api_url = get_gocardless_api_url(gc_env)
    if not token:
        return None
    
    try:
        response = requests.get(
            f"{api_url}/payments/{payment_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "GoCardless-Version": "2015-07-06",
            },
            timeout=10
        )
        if response.status_code == 200:
            return response.json()["payments"]
    except Exception as e:
        print(f"GoCardless payment status check failed: {e}")
    return None
