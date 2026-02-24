"""
Integration Service for third-party connections.

All integrations use credential-based authentication (API keys, tokens, etc.)
No OAuth redirects - users enter credentials directly.

Credentials are synced to app_settings on validation/activation so that
email_service.py and checkout.py continue to work without changes.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import httpx

from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel

from core.helpers import now_iso
from core.tenant import get_tenant_admin, tenant_id_of
from db.session import db


# ---------------------------------------------------------------------------
# Helper: sync credentials into the legacy app_settings keys
# ---------------------------------------------------------------------------

async def _sync_to_settings(key: str, value: Any) -> None:
    """Write (or upsert) a value into the global app_settings collection."""
    await db.app_settings.update_one(
        {"key": key},
        {"$set": {"key": key, "value_json": value, "updated_at": now_iso()}},
        upsert=True,
    )

router = APIRouter(prefix="/api", tags=["integrations"])

# Zoho Data Centers
ZOHO_DATA_CENTERS = {
    "us": {"name": "United States", "accounts_url": "https://accounts.zoho.com", "api_domain": "https://www.zohoapis.com"},
    "eu": {"name": "Europe", "accounts_url": "https://accounts.zoho.eu", "api_domain": "https://www.zohoapis.eu"},
    "in": {"name": "India", "accounts_url": "https://accounts.zoho.in", "api_domain": "https://www.zohoapis.in"},
    "au": {"name": "Australia", "accounts_url": "https://accounts.zoho.com.au", "api_domain": "https://www.zohoapis.com.au"},
    "jp": {"name": "Japan", "accounts_url": "https://accounts.zoho.jp", "api_domain": "https://www.zohoapis.jp"},
    "ca": {"name": "Canada", "accounts_url": "https://accounts.zohocloud.ca", "api_domain": "https://www.zohoapis.ca"},
}

# Integration Configurations
INTEGRATIONS = {
    # ===== PAYMENT PROVIDERS =====
    "stripe": {
        "name": "Stripe",
        "category": "payments",
        "description": "Process card payments via Stripe",
        "icon": "credit-card",
        "fields": [
            {"key": "api_key", "label": "Secret Key", "hint": "Starts with sk_live_ or sk_test_", "secret": True, "required": True},
            {"key": "publishable_key", "label": "Publishable Key", "hint": "Starts with pk_live_ or pk_test_", "secret": False, "required": False},
        ],
    },
    "gocardless": {
        "name": "GoCardless",
        "category": "payments",
        "description": "Process Direct Debit payments",
        "icon": "landmark",
        "fields": [
            {"key": "access_token", "label": "Access Token", "hint": "From GoCardless Dashboard → Developers", "secret": True, "required": True},
        ],
        "settings": [
            {"key": "success_title", "label": "Success Page Title", "default": "Payment Setup Complete"},
            {"key": "success_message", "label": "Success Message", "default": "Your Direct Debit has been set up successfully."},
            {"key": "success_button_text", "label": "Button Text", "default": "Return to Dashboard"},
        ],
    },
    "gocardless_sandbox": {
        "name": "GoCardless (Sandbox)",
        "category": "payments",
        "description": "Test Direct Debit payments",
        "icon": "landmark",
        "fields": [
            {"key": "access_token", "label": "Sandbox Access Token", "hint": "From GoCardless Sandbox Dashboard", "secret": True, "required": True},
        ],
    },
    
    # ===== EMAIL PROVIDERS =====
    "resend": {
        "name": "Resend",
        "category": "email",
        "description": "Send transactional emails via Resend",
        "icon": "mail",
        "fields": [
            {"key": "api_key", "label": "API Key", "hint": "From resend.com/api-keys", "secret": True, "required": True},
        ],
        "settings": [
            {"key": "from_email", "label": "From Email", "default": "onboarding@resend.dev"},
            {"key": "from_name", "label": "From Name", "default": ""},
            {"key": "reply_to", "label": "Reply-To Email", "default": ""},
        ],
    },
    "zoho_mail": {
        "name": "Zoho Mail",
        "category": "email",
        "description": "Send emails via Zoho Mail API",
        "icon": "mail",
        "is_zoho": True,
        "fields": [
            {"key": "client_id", "label": "Client ID", "hint": "From Zoho API Console", "secret": False, "required": True},
            {"key": "client_secret", "label": "Client Secret", "hint": "From Zoho API Console", "secret": True, "required": True},
            {"key": "refresh_token", "label": "Refresh Token", "hint": "Generated after OAuth", "secret": True, "required": True},
            {"key": "account_id", "label": "Account ID", "hint": "Your Zoho Mail account ID", "secret": False, "required": True},
        ],
        "settings": [
            {"key": "from_email", "label": "From Email", "default": ""},
            {"key": "from_name", "label": "From Name", "default": ""},
        ],
    },
    
    # ===== CRM PROVIDERS =====
    "zoho_crm": {
        "name": "Zoho CRM",
        "category": "crm",
        "description": "Sync customers and orders with Zoho CRM",
        "icon": "users",
        "is_zoho": True,
        "fields": [
            {"key": "client_id", "label": "Client ID", "hint": "From Zoho API Console", "secret": False, "required": True},
            {"key": "client_secret", "label": "Client Secret", "hint": "From Zoho API Console", "secret": True, "required": True},
            {"key": "refresh_token", "label": "Refresh Token", "hint": "Generated after OAuth", "secret": True, "required": True},
        ],
    },
    
    # ===== ACCOUNTING PROVIDERS =====
    "zoho_books": {
        "name": "Zoho Books",
        "category": "accounting",
        "description": "Sync invoices and payments with Zoho Books",
        "icon": "receipt",
        "is_zoho": True,
        "fields": [
            {"key": "client_id", "label": "Client ID", "hint": "From Zoho API Console", "secret": False, "required": True},
            {"key": "client_secret", "label": "Client Secret", "hint": "From Zoho API Console", "secret": True, "required": True},
            {"key": "refresh_token", "label": "Refresh Token", "hint": "Generated after OAuth", "secret": True, "required": True},
            {"key": "organization_id", "label": "Organization ID", "hint": "Your Zoho Books org ID", "secret": False, "required": True},
        ],
    },
    
    # ===== COMING SOON =====
    "hubspot": {
        "name": "HubSpot",
        "category": "crm",
        "description": "Sync contacts and deals with HubSpot",
        "icon": "users",
        "is_coming_soon": True,
    },
    "salesforce": {
        "name": "Salesforce",
        "category": "crm",
        "description": "Enterprise CRM integration",
        "icon": "cloud",
        "is_coming_soon": True,
    },
    "quickbooks": {
        "name": "QuickBooks",
        "category": "accounting",
        "description": "Sync with QuickBooks Online",
        "icon": "calculator",
        "is_coming_soon": True,
    },
    "gmail": {
        "name": "Gmail",
        "category": "email",
        "description": "Send emails via Gmail API",
        "icon": "mail",
        "is_coming_soon": True,
    },
    "outlook": {
        "name": "Microsoft Outlook",
        "category": "email",
        "description": "Send emails via Microsoft Graph",
        "icon": "mail",
        "is_coming_soon": True,
    },
}


class CredentialRequest(BaseModel):
    credentials: Dict[str, str]
    data_center: Optional[str] = "us"
    settings: Optional[Dict[str, str]] = None


class SettingsRequest(BaseModel):
    settings: Dict[str, str]


@router.get("/oauth/integrations")
async def list_integrations(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """List all integrations with their current status."""
    tid = tenant_id_of(admin)
    
    # Get stored connections
    connections = await db.oauth_connections.find({"tenant_id": tid}, {"_id": 0}).to_list(50)
    conn_map = {c["provider"]: c for c in connections}
    
    # Get active email provider
    active_setting = await db.app_settings.find_one({"key": "active_email_provider"}, {"_id": 0})
    active_email = active_setting.get("value_json") if active_setting else None
    
    result = []
    for provider_id, config in INTEGRATIONS.items():
        conn = conn_map.get(provider_id, {})
        is_coming_soon = config.get("is_coming_soon", False)
        
        result.append({
            "id": provider_id,
            "name": config["name"],
            "category": config["category"],
            "description": config.get("description", ""),
            "icon": config.get("icon", "plug"),
            "is_zoho": config.get("is_zoho", False),
            "is_coming_soon": is_coming_soon,
            "fields": config.get("fields", []) if not is_coming_soon else [],
            "settings": config.get("settings", []) if not is_coming_soon else [],
            "status": conn.get("status", "not_connected"),
            "is_validated": conn.get("is_validated", False),
            "is_active": active_email == provider_id if config["category"] == "email" else False,
            "data_center": conn.get("data_center"),
            "stored_settings": conn.get("settings", {}),
            "connected_at": conn.get("connected_at"),
            "validated_at": conn.get("validated_at"),
            "error_message": conn.get("error_message"),
        })
    
    return {
        "integrations": result,
        "zoho_data_centers": [{"id": k, "name": v["name"]} for k, v in ZOHO_DATA_CENTERS.items()],
        "active_email_provider": active_email,
    }


@router.post("/oauth/{provider}/save-credentials")
async def save_credentials(
    provider: str,
    payload: CredentialRequest,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Save credentials for an integration."""
    if provider not in INTEGRATIONS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    
    config = INTEGRATIONS[provider]
    if config.get("is_coming_soon"):
        raise HTTPException(status_code=400, detail=f"{config['name']} is coming soon")
    
    tid = tenant_id_of(admin)
    
    # Validate required fields
    for field in config.get("fields", []):
        if field.get("required") and not payload.credentials.get(field["key"]):
            raise HTTPException(status_code=400, detail=f"{field['label']} is required")
    
    await db.oauth_connections.update_one(
        {"tenant_id": tid, "provider": provider},
        {"$set": {
            "tenant_id": tid,
            "provider": provider,
            "status": "pending",
            "is_validated": False,
            "credentials": payload.credentials,
            "data_center": payload.data_center if config.get("is_zoho") else None,
            "settings": payload.settings or {},
            "connected_at": now_iso(),
            "updated_at": now_iso(),
            "error_message": None,
        }},
        upsert=True
    )
    
    return {"success": True, "message": "Credentials saved. Please validate the connection."}


@router.post("/oauth/{provider}/validate")
async def validate_connection(
    provider: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Validate credentials by testing the connection."""
    if provider not in INTEGRATIONS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    
    config = INTEGRATIONS[provider]
    tid = tenant_id_of(admin)
    
    conn = await db.oauth_connections.find_one({"tenant_id": tid, "provider": provider}, {"_id": 0})
    if not conn or not conn.get("credentials"):
        raise HTTPException(status_code=400, detail="No credentials found. Please save credentials first.")
    
    creds = conn["credentials"]
    result = {"success": False, "message": "Validation failed"}
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            if provider == "stripe":
                resp = await client.get(
                    "https://api.stripe.com/v1/balance",
                    auth=(creds.get("api_key", ""), "")
                )
                if resp.status_code == 200:
                    result = {"success": True, "message": "Stripe connection validated successfully"}
                else:
                    err = resp.json().get("error", {}).get("message", "Invalid API key")
                    result = {"success": False, "message": err}
            
            elif provider in ["gocardless", "gocardless_sandbox"]:
                base = "https://api-sandbox.gocardless.com" if "sandbox" in provider else "https://api.gocardless.com"
                resp = await client.get(
                    f"{base}/creditors",
                    headers={
                        "Authorization": f"Bearer {creds.get('access_token', '')}",
                        "GoCardless-Version": "2015-07-06"
                    }
                )
                if resp.status_code == 200:
                    result = {"success": True, "message": "GoCardless connection validated successfully"}
                else:
                    result = {"success": False, "message": "Invalid access token"}
            
            elif provider == "resend":
                resp = await client.get(
                    "https://api.resend.com/domains",
                    headers={"Authorization": f"Bearer {creds.get('api_key', '')}"}
                )
                if resp.status_code == 200:
                    domains = resp.json().get("data", [])
                    domain_names = [d.get("name") for d in domains[:3]]
                    result = {
                        "success": True, 
                        "message": f"Resend validated. Domains: {', '.join(domain_names) if domain_names else 'None configured'}"
                    }
                else:
                    result = {"success": False, "message": "Invalid API key"}
            
            elif provider in ["zoho_mail", "zoho_crm", "zoho_books"]:
                dc = conn.get("data_center", "us")
                dc_config = ZOHO_DATA_CENTERS.get(dc, ZOHO_DATA_CENTERS["us"])
                
                # Refresh token to get access token
                token_resp = await client.post(
                    f"{dc_config['accounts_url']}/oauth/v2/token",
                    data={
                        "grant_type": "refresh_token",
                        "client_id": creds.get("client_id", ""),
                        "client_secret": creds.get("client_secret", ""),
                        "refresh_token": creds.get("refresh_token", ""),
                    }
                )
                
                if token_resp.status_code != 200:
                    err = token_resp.json().get("error", "Invalid credentials")
                    result = {"success": False, "message": f"Token refresh failed: {err}"}
                else:
                    access_token = token_resp.json().get("access_token")
                    
                    # Test API access based on provider
                    if provider == "zoho_mail":
                        test_resp = await client.get(
                            f"{dc_config['api_domain']}/mail/accounts",
                            headers={"Authorization": f"Zoho-oauthtoken {access_token}"}
                        )
                    elif provider == "zoho_crm":
                        test_resp = await client.get(
                            f"{dc_config['api_domain']}/crm/v3/users?type=CurrentUser",
                            headers={"Authorization": f"Zoho-oauthtoken {access_token}"}
                        )
                    else:  # zoho_books
                        test_resp = await client.get(
                            f"{dc_config['api_domain']}/books/v3/organizations",
                            headers={"Authorization": f"Zoho-oauthtoken {access_token}"}
                        )
                    
                    if test_resp.status_code == 200:
                        result = {"success": True, "message": f"{config['name']} connection validated successfully"}
                    else:
                        result = {"success": False, "message": f"Could not access {config['name']} API"}
            
            else:
                result = {"success": False, "message": "Validation not implemented"}
    
    except httpx.TimeoutException:
        result = {"success": False, "message": "Connection timed out"}
    except Exception as e:
        result = {"success": False, "message": str(e)[:100]}
    
    # Update status in oauth_connections
    await db.oauth_connections.update_one(
        {"tenant_id": tid, "provider": provider},
        {"$set": {
            "is_validated": result["success"],
            "status": "connected" if result["success"] else "failed",
            "validated_at": now_iso() if result["success"] else None,
            "error_message": None if result["success"] else result["message"],
            "updated_at": now_iso(),
        }}
    )
    
    # Sync to legacy app_settings so checkout.py / email_service.py pick them up
    if result["success"]:
        creds = conn.get("credentials", {})
        if provider == "stripe":
            await _sync_to_settings("stripe_secret_key", creds.get("api_key", ""))
            if creds.get("publishable_key"):
                await _sync_to_settings("stripe_publishable_key", creds.get("publishable_key", ""))
            await _sync_to_settings("stripe_enabled", True)
        
        elif provider in ("gocardless", "gocardless_sandbox"):
            await _sync_to_settings("gocardless_access_token", creds.get("access_token", ""))
            gc_env = "sandbox" if "sandbox" in provider else "live"
            await _sync_to_settings("gocardless_environment", gc_env)
            await _sync_to_settings("gocardless_enabled", True)
        
        elif provider == "resend":
            await _sync_to_settings("resend_api_key", creds.get("api_key", ""))
    
    return result


@router.post("/oauth/{provider}/update-settings")
async def update_settings(
    provider: str,
    payload: SettingsRequest,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Update provider settings (e.g., success page text, from email)."""
    if provider not in INTEGRATIONS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    
    tid = tenant_id_of(admin)
    
    await db.oauth_connections.update_one(
        {"tenant_id": tid, "provider": provider},
        {"$set": {"settings": payload.settings, "updated_at": now_iso()}}
    )
    
    # If this is the active Resend provider, sync settings to legacy keys too
    if provider == "resend":
        active = await db.app_settings.find_one({"key": "active_email_provider"}, {"_id": 0})
        if active and active.get("value_json") == "resend":
            if "from_email" in payload.settings:
                await _sync_to_settings("resend_sender_email", payload.settings["from_email"])
            if "from_name" in payload.settings:
                await _sync_to_settings("email_from_name", payload.settings["from_name"])
            if "reply_to" in payload.settings:
                await _sync_to_settings("email_reply_to", payload.settings["reply_to"])
    
    return {"success": True, "message": "Settings updated"}


@router.post("/oauth/{provider}/activate")
async def activate_provider(
    provider: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Activate an email provider. Only one can be active at a time."""
    if provider not in INTEGRATIONS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    
    config = INTEGRATIONS[provider]
    if config["category"] != "email":
        raise HTTPException(status_code=400, detail="Only email providers can be activated")
    
    tid = tenant_id_of(admin)
    
    # Must be validated first
    conn = await db.oauth_connections.find_one({"tenant_id": tid, "provider": provider}, {"_id": 0})
    if not conn or not conn.get("is_validated"):
        raise HTTPException(status_code=400, detail="Please validate the connection first")
    
    await db.app_settings.update_one(
        {"key": "active_email_provider"},
        {"$set": {"key": "active_email_provider", "value_json": provider, "updated_at": now_iso()}},
        upsert=True
    )
    
    # Sync credentials to legacy app_settings so email_service.py sends live emails
    creds = conn.get("credentials", {})
    stored_settings = conn.get("settings", {})
    if provider == "resend":
        await _sync_to_settings("resend_api_key", creds.get("api_key", ""))
        await _sync_to_settings("resend_sender_email", stored_settings.get("from_email", ""))
        await _sync_to_settings("email_from_name", stored_settings.get("from_name", ""))
        await _sync_to_settings("email_reply_to", stored_settings.get("reply_to", ""))
        await _sync_to_settings("email_provider_enabled", True)
    
    return {"success": True, "message": f"{config['name']} is now your active email provider"}


@router.post("/oauth/{provider}/deactivate")
async def deactivate_provider(
    provider: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Deactivate an email provider."""
    if provider not in INTEGRATIONS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    
    config = INTEGRATIONS[provider]
    if config["category"] != "email":
        raise HTTPException(status_code=400, detail="Only email providers can be deactivated")
    
    await db.app_settings.update_one(
        {"key": "active_email_provider"},
        {"$set": {"value_json": None, "updated_at": now_iso()}}
    )
    # Disable live email sending
    await _sync_to_settings("email_provider_enabled", False)
    
    return {"success": True, "message": "Email provider deactivated. Emails will be stored but not sent."}


@router.delete("/oauth/{provider}/disconnect")
async def disconnect_provider(
    provider: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Remove credentials and disconnect an integration."""
    if provider not in INTEGRATIONS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    
    config = INTEGRATIONS[provider]
    tid = tenant_id_of(admin)
    
    # If active email provider, deactivate first and clear legacy settings
    if config["category"] == "email":
        active = await db.app_settings.find_one({"key": "active_email_provider"})
        if active and active.get("value_json") == provider:
            await db.app_settings.update_one(
                {"key": "active_email_provider"},
                {"$set": {"value_json": None}}
            )
            await _sync_to_settings("email_provider_enabled", False)
    
    # Disable the payment provider in legacy settings when disconnected
    if provider == "stripe":
        await _sync_to_settings("stripe_enabled", False)
        await _sync_to_settings("stripe_secret_key", "")
    elif provider in ("gocardless", "gocardless_sandbox"):
        await _sync_to_settings("gocardless_enabled", False)
        await _sync_to_settings("gocardless_access_token", "")
    
    await db.oauth_connections.delete_one({"tenant_id": tid, "provider": provider})
    
    return {"success": True, "message": f"{config['name']} disconnected"}


@router.get("/oauth/{provider}/status")
async def get_provider_status(
    provider: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Get detailed status of a provider connection."""
    if provider not in INTEGRATIONS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    
    tid = tenant_id_of(admin)
    config = INTEGRATIONS[provider]
    
    conn = await db.oauth_connections.find_one(
        {"tenant_id": tid, "provider": provider},
        {"_id": 0, "credentials": 0}  # Don't expose credentials
    )
    
    return {
        "provider": provider,
        "name": config["name"],
        "category": config["category"],
        "status": conn.get("status", "not_connected") if conn else "not_connected",
        "is_validated": conn.get("is_validated", False) if conn else False,
        "data_center": conn.get("data_center") if conn else None,
        "settings": conn.get("settings", {}) if conn else {},
        "connected_at": conn.get("connected_at") if conn else None,
        "validated_at": conn.get("validated_at") if conn else None,
        "error_message": conn.get("error_message") if conn else None,
    }
