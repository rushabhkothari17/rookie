"""
OAuth Service for third-party integrations.

Handles OAuth 2.0 flows for:
- Zoho (CRM, Books, Mail) with Data Center support
- Stripe Connect
- GoCardless
- Resend (API key based)
"""
from __future__ import annotations

import os
import secrets
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode
import httpx

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from core.helpers import make_id, now_iso
from core.tenant import get_tenant_admin, tenant_id_of
from db.session import db

router = APIRouter(prefix="/api", tags=["oauth"])

# Zoho Data Centers with their respective URLs
ZOHO_DATA_CENTERS = {
    "us": {"name": "United States", "accounts_url": "https://accounts.zoho.com", "api_domain": "https://www.zohoapis.com"},
    "eu": {"name": "Europe", "accounts_url": "https://accounts.zoho.eu", "api_domain": "https://www.zohoapis.eu"},
    "in": {"name": "India", "accounts_url": "https://accounts.zoho.in", "api_domain": "https://www.zohoapis.in"},
    "au": {"name": "Australia", "accounts_url": "https://accounts.zoho.com.au", "api_domain": "https://www.zohoapis.com.au"},
    "jp": {"name": "Japan", "accounts_url": "https://accounts.zoho.jp", "api_domain": "https://www.zohoapis.jp"},
    "ca": {"name": "Canada", "accounts_url": "https://accounts.zohocloud.ca", "api_domain": "https://www.zohoapis.ca"},
}

# Provider configurations
OAUTH_CONFIGS = {
    # ===== PAYMENT PROVIDERS =====
    "stripe": {
        "name": "Stripe",
        "category": "payments",
        "is_credential": True,
        "description": "Process card payments via Stripe",
        "fields": [
            {"key": "api_key", "label": "Secret Key", "hint": "Starts with sk_live_ or sk_test_", "secret": True, "required": True},
            {"key": "publishable_key", "label": "Publishable Key", "hint": "Starts with pk_live_ or pk_test_", "secret": False, "required": False},
        ],
        "validate_url": "https://api.stripe.com/v1/balance",
    },
    "gocardless": {
        "name": "GoCardless",
        "category": "payments",
        "is_credential": True,
        "description": "Process Direct Debit payments via GoCardless",
        "fields": [
            {"key": "access_token", "label": "Access Token", "hint": "From GoCardless Dashboard → Developers", "secret": True, "required": True},
        ],
        "validate_url": "https://api.gocardless.com/creditors",
        "settings": [
            {"key": "success_title", "label": "Success Page Title", "default": "Payment Setup Complete"},
            {"key": "success_message", "label": "Success Page Message", "default": "Your Direct Debit has been set up successfully. You will receive a confirmation email shortly."},
            {"key": "success_button_text", "label": "Button Text", "default": "Return to Dashboard"},
        ],
    },
    "gocardless_sandbox": {
        "name": "GoCardless (Sandbox)",
        "category": "payments",
        "is_credential": True,
        "description": "Test Direct Debit payments in sandbox mode",
        "fields": [
            {"key": "access_token", "label": "Sandbox Access Token", "hint": "From GoCardless Sandbox Dashboard", "secret": True, "required": True},
        ],
        "validate_url": "https://api-sandbox.gocardless.com/creditors",
    },
    
    # ===== EMAIL PROVIDERS =====
    "zoho_mail": {
        "name": "Zoho Mail",
        "category": "email",
        "is_credential": True,
        "is_zoho": True,
        "description": "Send transactional emails via Zoho Mail",
        "fields": [
            {"key": "client_id", "label": "Client ID", "hint": "From Zoho API Console", "secret": False, "required": True},
            {"key": "client_secret", "label": "Client Secret", "hint": "From Zoho API Console", "secret": True, "required": True},
            {"key": "refresh_token", "label": "Refresh Token", "hint": "Generated after OAuth authorization", "secret": True, "required": True},
            {"key": "account_id", "label": "Account ID", "hint": "Your Zoho Mail account ID", "secret": False, "required": True},
        ],
        "settings": [
            {"key": "from_email", "label": "From Email Address", "default": ""},
            {"key": "from_name", "label": "From Name", "default": ""},
        ],
    },
    "resend": {
        "name": "Resend",
        "category": "email",
        "is_credential": True,
        "description": "Send transactional emails via Resend",
        "fields": [
            {"key": "api_key", "label": "API Key", "hint": "From resend.com/api-keys", "secret": True, "required": True},
        ],
        "validate_url": "https://api.resend.com/domains",
        "settings": [
            {"key": "from_email", "label": "From Email Address", "default": "onboarding@resend.dev"},
            {"key": "from_name", "label": "From Name", "default": ""},
        ],
    },
    
    # ===== CRM PROVIDERS =====
    "zoho_crm": {
        "name": "Zoho CRM",
        "category": "crm",
        "is_credential": True,
        "is_zoho": True,
        "description": "Sync customers, orders, and subscriptions with Zoho CRM",
        "fields": [
            {"key": "client_id", "label": "Client ID", "hint": "From Zoho API Console", "secret": False, "required": True},
            {"key": "client_secret", "label": "Client Secret", "hint": "From Zoho API Console", "secret": True, "required": True},
            {"key": "refresh_token", "label": "Refresh Token", "hint": "Generated after OAuth authorization", "secret": True, "required": True},
        ],
    },
    
    # ===== ACCOUNTING PROVIDERS =====
    "zoho_books": {
        "name": "Zoho Books",
        "category": "accounting",
        "is_credential": True,
        "is_zoho": True,
        "description": "Sync invoices, payments, and financial data with Zoho Books",
        "fields": [
            {"key": "client_id", "label": "Client ID", "hint": "From Zoho API Console", "secret": False, "required": True},
            {"key": "client_secret", "label": "Client Secret", "hint": "From Zoho API Console", "secret": True, "required": True},
            {"key": "refresh_token", "label": "Refresh Token", "hint": "Generated after OAuth authorization", "secret": True, "required": True},
            {"key": "organization_id", "label": "Organization ID", "hint": "Your Zoho Books organization ID", "secret": False, "required": True},
        ],
    },
    
    # ===== COMING SOON =====
    "hubspot": {
        "name": "HubSpot",
        "category": "crm",
        "is_coming_soon": True,
        "description": "Sync contacts and deals with HubSpot CRM",
    },
    "salesforce": {
        "name": "Salesforce",
        "category": "crm",
        "is_coming_soon": True,
        "description": "Enterprise CRM integration with Salesforce",
    },
    "quickbooks": {
        "name": "QuickBooks",
        "category": "accounting",
        "is_coming_soon": True,
        "description": "Sync invoices and payments with QuickBooks",
    },
    "gmail": {
        "name": "Gmail",
        "category": "email",
        "is_coming_soon": True,
        "description": "Send emails via Gmail SMTP or API",
    },
    "outlook": {
        "name": "Microsoft Outlook",
        "category": "email",
        "is_coming_soon": True,
        "description": "Send emails via Microsoft Graph API",
    },
}


def get_frontend_url() -> str:
    """Get the frontend URL for OAuth callbacks."""
    return os.environ.get("FRONTEND_URL", os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:3000"))


def get_zoho_urls(dc: str = "us") -> Dict[str, str]:
    """Get Zoho URLs for a specific data center."""
    dc_config = ZOHO_DATA_CENTERS.get(dc, ZOHO_DATA_CENTERS["us"])
    return {
        "authorize_url": f"{dc_config['accounts_url']}/oauth/v2/auth",
        "token_url": f"{dc_config['accounts_url']}/oauth/v2/token",
        "api_domain": dc_config["api_domain"],
    }


class CredentialRequest(BaseModel):
    credentials: Dict[str, str]
    data_center: Optional[str] = "us"  # For Zoho providers
    settings: Optional[Dict[str, str]] = None


class ApiKeyRequest(BaseModel):
    api_key: str


@router.get("/oauth/integrations")
async def list_integrations(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """List all available integrations and their current status."""
    tid = tenant_id_of(admin)
    
    # Get stored connections for this tenant
    connections = await db.oauth_connections.find(
        {"tenant_id": tid},
        {"_id": 0}
    ).to_list(50)
    
    conn_map = {c["provider"]: c for c in connections}
    
    # Get active email provider setting
    active_email = await db.app_settings.find_one({"key": "active_email_provider"}, {"_id": 0})
    active_email_provider = active_email.get("value_json") if active_email else None
    
    integrations = []
    for provider_id, config in OAUTH_CONFIGS.items():
        conn = conn_map.get(provider_id, {})
        
        is_coming_soon = config.get("is_coming_soon", False)
        is_validated = conn.get("is_validated", False)
        status = conn.get("status", "not_connected")
        
        # Check if this provider is active (for email providers only)
        is_active = False
        if config["category"] == "email" and not is_coming_soon:
            is_active = active_email_provider == provider_id
        
        integrations.append({
            "id": provider_id,
            "name": config["name"],
            "category": config["category"],
            "description": config.get("description", ""),
            "status": status,
            "is_active": is_active,
            "is_validated": is_validated,
            "connected_at": conn.get("connected_at"),
            "validated_at": conn.get("validated_at"),
            "error_message": conn.get("error_message"),
            "is_zoho": config.get("is_zoho", False),
            "is_coming_soon": is_coming_soon,
            "data_center": conn.get("data_center"),
            "fields": config.get("fields", []),
            "settings": config.get("settings", []),
            "stored_settings": conn.get("settings", {}),
        })
    
    return {
        "integrations": integrations,
        "zoho_data_centers": [{"id": k, "name": v["name"]} for k, v in ZOHO_DATA_CENTERS.items()],
        "active_email_provider": active_email_provider,
    }


@router.post("/oauth/{provider}/save-credentials")
async def save_credentials(
    provider: str,
    payload: CredentialRequest,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Save credentials for an integration (does not validate)."""
    if provider not in OAUTH_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    
    config = OAUTH_CONFIGS[provider]
    
    if config.get("is_coming_soon"):
        raise HTTPException(status_code=400, detail=f"{config['name']} is coming soon")
    
    tid = tenant_id_of(admin)
    
    # Validate required fields
    required_fields = [f["key"] for f in config.get("fields", []) if f.get("required")]
    for field in required_fields:
        if not payload.credentials.get(field):
            field_label = next((f["label"] for f in config["fields"] if f["key"] == field), field)
            raise HTTPException(status_code=400, detail=f"{field_label} is required")
    
    # Save connection
    update_data = {
        "tenant_id": tid,
        "provider": provider,
        "status": "not_connected",
        "is_validated": False,
        "credentials": payload.credentials,
        "data_center": payload.data_center if config.get("is_zoho") else None,
        "settings": payload.settings or {},
        "updated_at": now_iso(),
    }
    
    await db.oauth_connections.update_one(
        {"tenant_id": tid, "provider": provider},
        {"$set": update_data},
        upsert=True
    )
    
    return {"success": True, "message": f"{config['name']} credentials saved. Click Validate to test the connection."}


@router.post("/oauth/{provider}/validate")
async def validate_connection(
    provider: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Validate stored credentials for an integration."""
    if provider not in OAUTH_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    
    config = OAUTH_CONFIGS[provider]
    tid = tenant_id_of(admin)
    
    # Get stored connection
    conn = await db.oauth_connections.find_one(
        {"tenant_id": tid, "provider": provider},
        {"_id": 0}
    )
    
    if not conn or not conn.get("credentials"):
        raise HTTPException(status_code=400, detail="No credentials found. Please save credentials first.")
    
    credentials = conn["credentials"]
    validation_result = {"success": False, "message": "Validation failed"}
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            if provider == "stripe":
                # Validate Stripe API key
                resp = await client.get(
                    "https://api.stripe.com/v1/balance",
                    auth=(credentials.get("api_key", ""), "")
                )
                if resp.status_code == 200:
                    validation_result = {"success": True, "message": "Stripe connection validated"}
                else:
                    error = resp.json().get("error", {}).get("message", "Invalid API key")
                    validation_result = {"success": False, "message": error}
            
            elif provider in ["gocardless", "gocardless_sandbox"]:
                # Validate GoCardless access token
                base_url = "https://api-sandbox.gocardless.com" if "sandbox" in provider else "https://api.gocardless.com"
                resp = await client.get(
                    f"{base_url}/creditors",
                    headers={
                        "Authorization": f"Bearer {credentials.get('access_token', '')}",
                        "GoCardless-Version": "2015-07-06"
                    }
                )
                if resp.status_code == 200:
                    validation_result = {"success": True, "message": "GoCardless connection validated"}
                else:
                    validation_result = {"success": False, "message": "Invalid access token"}
            
            elif provider == "resend":
                # Validate Resend API key
                resp = await client.get(
                    "https://api.resend.com/domains",
                    headers={"Authorization": f"Bearer {credentials.get('api_key', '')}"}
                )
                if resp.status_code == 200:
                    validation_result = {"success": True, "message": "Resend connection validated"}
                else:
                    validation_result = {"success": False, "message": "Invalid API key"}
            
            elif provider == "zoho_mail":
                # Validate Zoho Mail
                dc = conn.get("data_center", "us")
                dc_config = ZOHO_DATA_CENTERS.get(dc, ZOHO_DATA_CENTERS["us"])
                
                # First refresh the access token
                refresh_resp = await client.post(
                    f"{dc_config['accounts_url']}/oauth/v2/token",
                    data={
                        "grant_type": "refresh_token",
                        "client_id": credentials.get("client_id", ""),
                        "client_secret": credentials.get("client_secret", ""),
                        "refresh_token": credentials.get("refresh_token", ""),
                    }
                )
                
                if refresh_resp.status_code == 200:
                    token_data = refresh_resp.json()
                    access_token = token_data.get("access_token")
                    
                    # Test the connection by getting account info
                    test_resp = await client.get(
                        f"{dc_config['api_domain']}/mail/accounts",
                        headers={"Authorization": f"Zoho-oauthtoken {access_token}"}
                    )
                    
                    if test_resp.status_code == 200:
                        validation_result = {"success": True, "message": "Zoho Mail connection validated"}
                    else:
                        validation_result = {"success": False, "message": "Could not access Zoho Mail account"}
                else:
                    error = refresh_resp.json().get("error", "Invalid credentials")
                    validation_result = {"success": False, "message": f"Token refresh failed: {error}"}
            
            elif provider == "zoho_crm":
                # Validate Zoho CRM
                dc = conn.get("data_center", "us")
                dc_config = ZOHO_DATA_CENTERS.get(dc, ZOHO_DATA_CENTERS["us"])
                
                refresh_resp = await client.post(
                    f"{dc_config['accounts_url']}/oauth/v2/token",
                    data={
                        "grant_type": "refresh_token",
                        "client_id": credentials.get("client_id", ""),
                        "client_secret": credentials.get("client_secret", ""),
                        "refresh_token": credentials.get("refresh_token", ""),
                    }
                )
                
                if refresh_resp.status_code == 200:
                    token_data = refresh_resp.json()
                    access_token = token_data.get("access_token")
                    
                    test_resp = await client.get(
                        f"{dc_config['api_domain']}/crm/v3/users?type=CurrentUser",
                        headers={"Authorization": f"Zoho-oauthtoken {access_token}"}
                    )
                    
                    if test_resp.status_code == 200:
                        validation_result = {"success": True, "message": "Zoho CRM connection validated"}
                    else:
                        validation_result = {"success": False, "message": "Could not access Zoho CRM"}
                else:
                    error = refresh_resp.json().get("error", "Invalid credentials")
                    validation_result = {"success": False, "message": f"Token refresh failed: {error}"}
            
            elif provider == "zoho_books":
                # Validate Zoho Books
                dc = conn.get("data_center", "us")
                dc_config = ZOHO_DATA_CENTERS.get(dc, ZOHO_DATA_CENTERS["us"])
                
                refresh_resp = await client.post(
                    f"{dc_config['accounts_url']}/oauth/v2/token",
                    data={
                        "grant_type": "refresh_token",
                        "client_id": credentials.get("client_id", ""),
                        "client_secret": credentials.get("client_secret", ""),
                        "refresh_token": credentials.get("refresh_token", ""),
                    }
                )
                
                if refresh_resp.status_code == 200:
                    token_data = refresh_resp.json()
                    access_token = token_data.get("access_token")
                    org_id = credentials.get("organization_id", "")
                    
                    test_resp = await client.get(
                        f"{dc_config['api_domain']}/books/v3/organizations",
                        headers={"Authorization": f"Zoho-oauthtoken {access_token}"}
                    )
                    
                    if test_resp.status_code == 200:
                        validation_result = {"success": True, "message": "Zoho Books connection validated"}
                    else:
                        validation_result = {"success": False, "message": "Could not access Zoho Books"}
                else:
                    error = refresh_resp.json().get("error", "Invalid credentials")
                    validation_result = {"success": False, "message": f"Token refresh failed: {error}"}
            
            else:
                validation_result = {"success": False, "message": "Validation not implemented for this provider"}
    
    except httpx.TimeoutException:
        validation_result = {"success": False, "message": "Connection timed out. Please try again."}
    except Exception as e:
        validation_result = {"success": False, "message": f"Validation error: {str(e)}"}
    
    # Update connection status
    update_data = {
        "is_validated": validation_result["success"],
        "status": "connected" if validation_result["success"] else "failed",
        "validated_at": now_iso() if validation_result["success"] else None,
        "error_message": None if validation_result["success"] else validation_result["message"],
    }
    
    await db.oauth_connections.update_one(
        {"tenant_id": tid, "provider": provider},
        {"$set": update_data}
    )
    
    return validation_result


@router.post("/oauth/{provider}/update-settings")
async def update_provider_settings(
    provider: str,
    settings: Dict[str, str] = Body(...),
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Update settings for an integration (e.g., success page text)."""
    if provider not in OAUTH_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    
    tid = tenant_id_of(admin)
    
    await db.oauth_connections.update_one(
        {"tenant_id": tid, "provider": provider},
        {"$set": {"settings": settings, "updated_at": now_iso()}}
    )
    
    return {"success": True, "message": "Settings updated"}


@router.post("/oauth/{provider}/activate")
async def activate_provider(
    provider: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Activate an email provider. Only one email provider can be active at a time."""
    if provider not in OAUTH_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    
    config = OAUTH_CONFIGS[provider]
    
    if config["category"] != "email":
        raise HTTPException(status_code=400, detail="Only email providers can be activated/deactivated")
    
    tid = tenant_id_of(admin)
    
    # Check if connection is validated
    conn = await db.oauth_connections.find_one(
        {"tenant_id": tid, "provider": provider},
        {"_id": 0}
    )
    
    if not conn or not conn.get("is_validated"):
        raise HTTPException(status_code=400, detail="Please validate the connection before activating")
    
    # Set as active email provider
    await db.app_settings.update_one(
        {"key": "active_email_provider"},
        {"$set": {"key": "active_email_provider", "value_json": provider, "updated_at": now_iso()}},
        upsert=True
    )
    
    return {"success": True, "message": f"{config['name']} is now your active email provider"}


@router.post("/oauth/{provider}/deactivate")
async def deactivate_provider(
    provider: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Deactivate an email provider."""
    if provider not in OAUTH_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    
    config = OAUTH_CONFIGS[provider]
    
    if config["category"] != "email":
        raise HTTPException(status_code=400, detail="Only email providers can be activated/deactivated")
    
    # Clear active email provider
    await db.app_settings.update_one(
        {"key": "active_email_provider"},
        {"$set": {"key": "active_email_provider", "value_json": None, "updated_at": now_iso()}},
        upsert=True
    )
    
    return {"success": True, "message": f"{config['name']} has been deactivated. Emails will be stored but not sent."}


@router.delete("/oauth/{provider}/disconnect")
async def disconnect_provider(
    provider: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Remove stored credentials for an integration."""
    if provider not in OAUTH_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    
    config = OAUTH_CONFIGS[provider]
    tid = tenant_id_of(admin)
    
    # If this is the active email provider, deactivate it first
    if config["category"] == "email":
        active = await db.app_settings.find_one({"key": "active_email_provider"})
        if active and active.get("value_json") == provider:
            await db.app_settings.update_one(
                {"key": "active_email_provider"},
                {"$set": {"value_json": None}}
            )
    
    # Delete the connection
    await db.oauth_connections.delete_one({"tenant_id": tid, "provider": provider})
    
    return {"success": True, "message": f"{config['name']} disconnected"}
            "provider": provider,
            "status": "connecting",
            "data_center": data_center,
            "updated_at": now_iso()
        }},
        upsert=True
    )
    
    # Build callback URL - must match what's configured in the provider's developer console
    frontend_url = get_frontend_url()
    callback_url = f"{frontend_url}/api/oauth/callback"
    
    params = {
        "client_id": client_id,
        "redirect_uri": callback_url,
        "state": state,
        "response_type": "code",
    }
    
    # Provider-specific parameters
    if config.get("is_zoho"):
        params["scope"] = ",".join(config["scopes"])
        params["access_type"] = "offline"
        params["prompt"] = "consent"
    elif "stripe" in provider:
        params["scope"] = config["scopes"][0]
        params["stripe_landing"] = "login"
    elif "gocardless" in provider:
        params["scope"] = config["scopes"][0]
        params["initial_view"] = "login"
    
    auth_url = f"{authorize_url}?{urlencode(params)}"
    
    return {
        "authorization_url": auth_url,
        "state": state,
        "provider": provider,
        "callback_url": callback_url
    }


@router.get("/oauth/callback")
async def oauth_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
    location: Optional[str] = Query(None),  # Zoho returns datacenter info
):
    """
    Universal OAuth callback handler.
    
    All providers redirect here with code and state.
    """
    frontend_url = get_frontend_url()
    
    # Handle error response from provider
    if error:
        return RedirectResponse(
            url=f"{frontend_url}/admin?tab=integrations&oauth_error={error}&error_desc={error_description or ''}",
            status_code=302
        )
    
    if not code or not state:
        return RedirectResponse(
            url=f"{frontend_url}/admin?tab=integrations&oauth_error=missing_params",
            status_code=302
        )
    
    # Verify state token
    state_doc = await db.oauth_states.find_one_and_delete({"state": state})
    if not state_doc:
        return RedirectResponse(
            url=f"{frontend_url}/admin?tab=integrations&oauth_error=invalid_state",
            status_code=302
        )
    
    provider = state_doc["provider"]
    tid = state_doc["tenant_id"]
    token_url = state_doc.get("token_url")
    data_center = state_doc.get("data_center", "us")
    
    # Check if state expired
    if datetime.fromisoformat(state_doc["expires_at"].replace("Z", "+00:00")) < datetime.now(timezone.utc):
        await db.oauth_connections.update_one(
            {"tenant_id": tid, "provider": provider},
            {"$set": {"status": "failed", "error_message": "Authorization expired", "updated_at": now_iso()}}
        )
        return RedirectResponse(
            url=f"{frontend_url}/admin?tab=integrations&oauth_error=expired&provider={provider}",
            status_code=302
        )
    
    config = OAUTH_CONFIGS.get(provider)
    if not config:
        return RedirectResponse(
            url=f"{frontend_url}/admin?tab=integrations&oauth_error=unknown_provider",
            status_code=302
        )
    
    # Get credentials
    client_id = os.environ.get(config.get("client_id_env", ""), "")
    client_secret = os.environ.get(config.get("client_secret_env", ""), "")
    callback_url = f"{frontend_url}/api/oauth/callback"
    
    # Use stored token_url or get from config
    if not token_url:
        if config.get("is_zoho"):
            token_url = get_zoho_urls(data_center)["token_url"]
        else:
            token_url = config.get("token_url")
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            token_data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": callback_url,
                "client_id": client_id,
                "client_secret": client_secret,
            }
            
            response = await client.post(
                token_url,
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code != 200:
                error_msg = response.text[:200]
                await db.oauth_connections.update_one(
                    {"tenant_id": tid, "provider": provider},
                    {"$set": {
                        "status": "failed",
                        "error_message": f"Token exchange failed: {error_msg}",
                        "updated_at": now_iso()
                    }}
                )
                return RedirectResponse(
                    url=f"{frontend_url}/admin?tab=integrations&oauth_error=token_exchange&provider={provider}",
                    status_code=302
                )
            
            tokens = response.json()
            
            # Calculate token expiry
            expires_in = tokens.get("expires_in", 3600)
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
            
            # Store tokens
            update_data = {
                "status": "connected",
                "access_token": tokens.get("access_token"),
                "refresh_token": tokens.get("refresh_token"),
                "token_type": tokens.get("token_type", "Bearer"),
                "expires_at": expires_at,
                "scope": tokens.get("scope"),
                "data_center": data_center,
                "connected_at": now_iso(),
                "last_refresh": now_iso(),
                "error_message": None,
                "updated_at": now_iso(),
            }
            
            # Provider-specific data
            if "stripe" in provider:
                update_data["stripe_user_id"] = tokens.get("stripe_user_id")
                update_data["stripe_publishable_key"] = tokens.get("stripe_publishable_key")
                update_data["livemode"] = tokens.get("livemode", True)
            elif "gocardless" in provider:
                update_data["organisation_id"] = tokens.get("organisation_id")
            elif config.get("is_zoho"):
                update_data["api_domain"] = tokens.get("api_domain") or get_zoho_urls(data_center)["api_domain"]
            
            await db.oauth_connections.update_one(
                {"tenant_id": tid, "provider": provider},
                {"$set": update_data}
            )
            
            # Auto-enable the provider for its category
            if config["category"] == "payments":
                if "stripe" in provider:
                    await db.app_settings.update_one(
                        {"key": "stripe_enabled"},
                        {"$set": {"key": "stripe_enabled", "value_json": True}},
                        upsert=True
                    )
                elif "gocardless" in provider:
                    await db.app_settings.update_one(
                        {"key": "gocardless_enabled"},
                        {"$set": {"key": "gocardless_enabled", "value_json": True}},
                        upsert=True
                    )
            
            return RedirectResponse(
                url=f"{frontend_url}/admin?tab=integrations&oauth_success=true&provider={provider}",
                status_code=302
            )
            
    except Exception as e:
        await db.oauth_connections.update_one(
            {"tenant_id": tid, "provider": provider},
            {"$set": {
                "status": "failed",
                "error_message": str(e)[:200],
                "updated_at": now_iso()
            }}
        )
        return RedirectResponse(
            url=f"{frontend_url}/admin?tab=integrations&oauth_error=exception&provider={provider}",
            status_code=302
        )


@router.post("/oauth/{provider}/cancel")
async def cancel_oauth(
    provider: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Cancel an in-progress OAuth connection."""
    if provider not in OAUTH_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    
    tid = tenant_id_of(admin)
    
    # Delete any pending states
    await db.oauth_states.delete_many({"tenant_id": tid, "provider": provider})
    
    # Reset connection status
    await db.oauth_connections.update_one(
        {"tenant_id": tid, "provider": provider},
        {"$set": {"status": "not_connected", "error_message": None, "updated_at": now_iso()}}
    )
    
    return {"success": True, "message": "Connection cancelled"}


@router.post("/oauth/{provider}/api-key")
async def set_api_key(
    provider: str,
    payload: ApiKeyRequest,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Set API key for providers that use API key authentication (e.g., Resend)."""
    if provider not in OAUTH_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    
    config = OAUTH_CONFIGS[provider]
    if not config.get("is_api_key"):
        raise HTTPException(status_code=400, detail=f"{config['name']} uses OAuth, not API key")
    
    tid = tenant_id_of(admin)
    setting_key = config.get("api_key_setting", f"{provider}_api_key")
    
    # Save API key to settings
    await db.app_settings.update_one(
        {"key": setting_key},
        {"$set": {"key": setting_key, "value": payload.api_key, "updated_at": now_iso()}},
        upsert=True
    )
    
    # Update connection status
    await db.oauth_connections.update_one(
        {"tenant_id": tid, "provider": provider},
        {"$set": {
            "tenant_id": tid,
            "provider": provider,
            "status": "connected",
            "connected_at": now_iso(),
            "updated_at": now_iso(),
            "error_message": None,
        }},
        upsert=True
    )
    
    return {"success": True, "message": f"{config['name']} API key saved"}


@router.post("/oauth/{provider}/refresh")
async def refresh_oauth_token(
    provider: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Refresh an OAuth access token using the refresh token."""
    if provider not in OAUTH_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    
    config = OAUTH_CONFIGS[provider]
    if config.get("is_api_key"):
        raise HTTPException(status_code=400, detail=f"{config['name']} uses API key, not OAuth")
    
    tid = tenant_id_of(admin)
    
    # Get current connection
    connection = await db.oauth_connections.find_one(
        {"tenant_id": tid, "provider": provider},
        {"_id": 0}
    )
    
    if not connection or not connection.get("refresh_token"):
        raise HTTPException(status_code=400, detail="No refresh token available. Please reconnect.")
    
    # Get token URL based on data center
    data_center = connection.get("data_center", "us")
    if config.get("is_zoho"):
        token_url = get_zoho_urls(data_center)["token_url"]
    else:
        token_url = config.get("token_url")
    
    client_id = os.environ.get(config.get("client_id_env", ""), "")
    client_secret = os.environ.get(config.get("client_secret_env", ""), "")
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            token_data = {
                "grant_type": "refresh_token",
                "refresh_token": connection["refresh_token"],
                "client_id": client_id,
                "client_secret": client_secret,
            }
            
            response = await client.post(
                token_url,
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code != 200:
                error_msg = response.text[:200]
                await db.oauth_connections.update_one(
                    {"tenant_id": tid, "provider": provider},
                    {"$set": {
                        "status": "expired",
                        "error_message": f"Token refresh failed: {error_msg}",
                        "updated_at": now_iso()
                    }}
                )
                raise HTTPException(status_code=400, detail="Token refresh failed. Please reconnect.")
            
            tokens = response.json()
            expires_in = tokens.get("expires_in", 3600)
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
            
            update_data = {
                "access_token": tokens.get("access_token"),
                "token_type": tokens.get("token_type", "Bearer"),
                "expires_at": expires_at,
                "last_refresh": now_iso(),
                "status": "connected",
                "error_message": None,
                "updated_at": now_iso()
            }
            
            # Some providers return a new refresh token
            if tokens.get("refresh_token"):
                update_data["refresh_token"] = tokens["refresh_token"]
            
            await db.oauth_connections.update_one(
                {"tenant_id": tid, "provider": provider},
                {"$set": update_data}
            )
            
            return {"success": True, "expires_at": expires_at}
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/oauth/{provider}/disconnect")
async def disconnect_oauth(
    provider: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Disconnect an OAuth integration."""
    if provider not in OAUTH_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    
    config = OAUTH_CONFIGS[provider]
    tid = tenant_id_of(admin)
    
    # Remove the connection
    await db.oauth_connections.delete_one({"tenant_id": tid, "provider": provider})
    
    # Clear API key if applicable
    if config.get("is_api_key"):
        setting_key = config.get("api_key_setting", f"{provider}_api_key")
        await db.app_settings.delete_one({"key": setting_key})
    
    # Disable the provider
    if config["category"] == "payments":
        if "stripe" in provider:
            await db.app_settings.update_one(
                {"key": "stripe_enabled"},
                {"$set": {"key": "stripe_enabled", "value_json": False}},
                upsert=True
            )
        elif "gocardless" in provider:
            await db.app_settings.update_one(
                {"key": "gocardless_enabled"},
                {"$set": {"key": "gocardless_enabled", "value_json": False}},
                upsert=True
            )
    elif config["category"] == "email":
        # If this was the active email provider, clear it
        await db.app_settings.update_one(
            {"key": "active_email_provider", "value": provider},
            {"$set": {"value": ""}}
        )
    
    return {"success": True, "message": f"{config['name']} disconnected"}


@router.post("/oauth/{provider}/activate")
async def activate_provider(
    provider: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Activate a connected provider (e.g., set as active email provider)."""
    if provider not in OAUTH_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    
    config = OAUTH_CONFIGS[provider]
    tid = tenant_id_of(admin)
    
    # Check if connected
    connection = await db.oauth_connections.find_one(
        {"tenant_id": tid, "provider": provider, "status": "connected"},
        {"_id": 0}
    )
    
    if not connection:
        raise HTTPException(status_code=400, detail=f"{config['name']} is not connected")
    
    if config["category"] == "email":
        # Set as active email provider (only one can be active)
        await db.app_settings.update_one(
            {"key": "active_email_provider"},
            {"$set": {"key": "active_email_provider", "value": provider}},
            upsert=True
        )
        # Also enable email provider
        await db.app_settings.update_one(
            {"key": "email_provider_enabled"},
            {"$set": {"key": "email_provider_enabled", "value_json": True}},
            upsert=True
        )
    elif config["category"] == "payments":
        if "stripe" in provider:
            await db.app_settings.update_one(
                {"key": "stripe_enabled"},
                {"$set": {"key": "stripe_enabled", "value_json": True}},
                upsert=True
            )
        elif "gocardless" in provider:
            await db.app_settings.update_one(
                {"key": "gocardless_enabled"},
                {"$set": {"key": "gocardless_enabled", "value_json": True}},
                upsert=True
            )
    
    return {"success": True, "message": f"{config['name']} activated"}


@router.post("/oauth/{provider}/deactivate")
async def deactivate_provider(
    provider: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Deactivate a provider without disconnecting it."""
    if provider not in OAUTH_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    
    config = OAUTH_CONFIGS[provider]
    
    if config["category"] == "email":
        await db.app_settings.update_one(
            {"key": "active_email_provider", "value": provider},
            {"$set": {"value": ""}}
        )
    elif config["category"] == "payments":
        if "stripe" in provider:
            await db.app_settings.update_one(
                {"key": "stripe_enabled"},
                {"$set": {"value_json": False}}
            )
        elif "gocardless" in provider:
            await db.app_settings.update_one(
                {"key": "gocardless_enabled"},
                {"$set": {"value_json": False}}
            )
    
    return {"success": True, "message": f"{config['name']} deactivated"}


@router.get("/oauth/{provider}/status")
async def get_oauth_status(
    provider: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Get detailed status of an OAuth connection."""
    if provider not in OAUTH_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    
    tid = tenant_id_of(admin)
    config = OAUTH_CONFIGS[provider]
    
    connection = await db.oauth_connections.find_one(
        {"tenant_id": tid, "provider": provider},
        {"_id": 0, "access_token": 0, "refresh_token": 0}
    )
    
    # Check if token is expired
    is_expired = False
    if connection and connection.get("expires_at"):
        try:
            expires_at = datetime.fromisoformat(connection["expires_at"].replace("Z", "+00:00"))
            is_expired = expires_at < datetime.now(timezone.utc)
        except (ValueError, TypeError):
            pass
    
    if not connection:
        return {
            "provider": provider,
            "name": config["name"],
            "status": "not_connected",
            "can_connect": bool(os.environ.get(config.get("client_id_env", ""), "")) if not config.get("is_api_key") else True
        }
    
    return {
        "provider": provider,
        "name": config["name"],
        "status": "expired" if is_expired else connection.get("status", "not_connected"),
        "connected_at": connection.get("connected_at"),
        "last_refresh": connection.get("last_refresh"),
        "expires_at": connection.get("expires_at"),
        "is_expired": is_expired,
        "error_message": connection.get("error_message"),
        "data_center": connection.get("data_center"),
        "can_connect": bool(os.environ.get(config.get("client_id_env", ""), "")) if not config.get("is_api_key") else True,
    }


@router.get("/oauth/health")
async def check_connection_health(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Check health of all OAuth connections for the tenant."""
    tid = tenant_id_of(admin)
    
    connections = await db.oauth_connections.find(
        {"tenant_id": tid, "status": "connected"},
        {"_id": 0, "access_token": 0, "refresh_token": 0}
    ).to_list(50)
    
    health_report = []
    now = datetime.now(timezone.utc)
    
    for conn in connections:
        provider = conn.get("provider")
        expires_at_str = conn.get("expires_at")
        
        status = "healthy"
        message = "Connection is active"
        needs_refresh = False
        
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                time_until_expiry = expires_at - now
                
                if time_until_expiry.total_seconds() < 0:
                    status = "expired"
                    message = "Token has expired. Please refresh or reconnect."
                    needs_refresh = True
                elif time_until_expiry.total_seconds() < 86400:  # Less than 24 hours
                    status = "expiring_soon"
                    message = f"Token expires in {int(time_until_expiry.total_seconds() / 3600)} hours"
                    needs_refresh = True
                elif time_until_expiry.total_seconds() < 604800:  # Less than 7 days
                    status = "warning"
                    message = f"Token expires in {int(time_until_expiry.days)} days"
            except (ValueError, TypeError):
                pass
        
        health_report.append({
            "provider": provider,
            "name": OAUTH_CONFIGS.get(provider, {}).get("name", provider),
            "status": status,
            "message": message,
            "needs_refresh": needs_refresh,
            "expires_at": expires_at_str,
            "last_refresh": conn.get("last_refresh"),
        })
    
    # Count by status
    healthy_count = sum(1 for h in health_report if h["status"] == "healthy")
    warning_count = sum(1 for h in health_report if h["status"] in ("warning", "expiring_soon"))
    expired_count = sum(1 for h in health_report if h["status"] == "expired")
    
    return {
        "summary": {
            "total": len(health_report),
            "healthy": healthy_count,
            "warning": warning_count,
            "expired": expired_count,
        },
        "connections": health_report
    }
