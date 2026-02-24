"""
Integration Service for third-party connections.

All integrations use credential-based authentication (API keys, tokens, etc.)
No OAuth redirects - users enter credentials directly.

Credentials are synced to app_settings on validation/activation so that
email_service.py and checkout.py continue to work without changes.
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone
import httpx

from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel

from core.helpers import now_iso
from core.tenant import get_tenant_admin, tenant_id_of
from db.session import db


# ---------------------------------------------------------------------------
# In-memory Zoho access token cache: {(tid, provider): (access_token, expiry_epoch)}
# Tokens are cached for 55 minutes (Zoho access tokens last 60 minutes).
# ---------------------------------------------------------------------------
_zoho_token_cache: Dict[Tuple[str, str], Tuple[str, float]] = {}
_ZOHO_TOKEN_TTL = 55 * 60  # 55 minutes in seconds


async def _get_zoho_access_token_cached(
    tid: str, provider: str, creds: Dict[str, Any], dc_config: Dict[str, Any]
) -> str:
    """
    Get a Zoho access token, using the in-memory cache if valid.
    Avoids hammering Zoho's token endpoint on repeated calls.
    """
    cache_key = (tid, provider)
    cached = _zoho_token_cache.get(cache_key)
    if cached:
        token, expiry = cached
        if time.time() < expiry:
            return token

    # Refresh from Zoho
    async with httpx.AsyncClient(timeout=15.0) as client:
        token_resp = await client.post(
            f"{dc_config['accounts_url']}/oauth/v2/token",
            data={
                "grant_type": "refresh_token",
                "client_id": creds.get("client_id", ""),
                "client_secret": creds.get("client_secret", ""),
                "refresh_token": creds.get("refresh_token", ""),
            },
        )
    if token_resp.status_code != 200 or token_resp.json().get("error"):
        raise HTTPException(status_code=400, detail="Token refresh failed — please reconnect the Zoho integration")

    access_token = token_resp.json()["access_token"]
    _zoho_token_cache[cache_key] = (access_token, time.time() + _ZOHO_TOKEN_TTL)
    return access_token


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
    "us": {"name": "United States", "accounts_url": "https://accounts.zoho.com",     "api_domain": "https://www.zohoapis.com",    "mail_api": "https://mail.zoho.com/api"},
    "eu": {"name": "Europe",         "accounts_url": "https://accounts.zoho.eu",      "api_domain": "https://www.zohoapis.eu",     "mail_api": "https://mail.zoho.eu/api"},
    "in": {"name": "India",          "accounts_url": "https://accounts.zoho.in",      "api_domain": "https://www.zohoapis.in",     "mail_api": "https://mail.zoho.in/api"},
    "au": {"name": "Australia",      "accounts_url": "https://accounts.zoho.com.au",  "api_domain": "https://www.zohoapis.com.au", "mail_api": "https://mail.zoho.com.au/api"},
    "jp": {"name": "Japan",          "accounts_url": "https://accounts.zoho.jp",      "api_domain": "https://www.zohoapis.jp",     "mail_api": "https://mail.zoho.jp/api"},
    "ca": {"name": "Canada",         "accounts_url": "https://accounts.zohocloud.ca", "api_domain": "https://www.zohoapis.ca",     "mail_api": "https://mail.zohocloud.ca/api"},
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
            {"key": "client_id",    "label": "Client ID",           "hint": "From Zoho API Console",                                          "secret": False, "required": True},
            {"key": "client_secret","label": "Client Secret",       "hint": "From Zoho API Console",                                          "secret": True,  "required": True},
            {"key": "auth_code",    "label": "Authorization Code",  "hint": "One-time code from API Console → Generate Code tab (expires fast)","secret": False, "required": False},
        ],
        "settings": [
            {"key": "from_email", "label": "From Email", "default": ""},
            {"key": "from_name",  "label": "From Name",  "default": ""},
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
            {"key": "client_id",    "label": "Client ID",          "hint": "From Zoho API Console",                                          "secret": False, "required": True},
            {"key": "client_secret","label": "Client Secret",      "hint": "From Zoho API Console",                                          "secret": True,  "required": True},
            {"key": "auth_code",    "label": "Authorization Code", "hint": "One-time code from API Console → Generate Code tab (expires fast)","secret": False, "required": False},
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
            {"key": "client_id",    "label": "Client ID",          "hint": "From Zoho API Console",                                          "secret": False, "required": True},
            {"key": "client_secret","label": "Client Secret",      "hint": "From Zoho API Console",                                          "secret": True,  "required": True},
            {"key": "auth_code",    "label": "Authorization Code", "hint": "One-time code from API Console → Generate Code tab (expires fast)","secret": False, "required": False},
            {"key": "organization_id","label": "Organization ID",  "hint": "Zoho Books → Settings → Organization Profile",                   "secret": False, "required": True},
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
    """Save credentials for an integration. Empty fields preserve existing stored values (edit mode)."""
    if provider not in INTEGRATIONS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    
    config = INTEGRATIONS[provider]
    if config.get("is_coming_soon"):
        raise HTTPException(status_code=400, detail=f"{config['name']} is coming soon")
    
    tid = tenant_id_of(admin)
    
    # Fetch existing connection to merge credentials (edit mode: blank field = keep existing)
    existing = await db.oauth_connections.find_one({"tenant_id": tid, "provider": provider}, {"_id": 0})
    existing_creds = existing.get("credentials", {}) if existing else {}
    
    # Merge: only overwrite a field if a non-empty value was provided
    merged_creds: Dict[str, str] = dict(existing_creds)
    for k, v in payload.credentials.items():
        if v:  # non-empty value replaces existing
            merged_creds[k] = v
    
    # Auto-exchange Zoho authorization code → refresh token (server-side, one-time)
    # Try every DC's accounts URL — auth codes are DC-specific, so we probe to find the right one
    if merged_creds.get("auth_code") and config.get("is_zoho"):
        dc = payload.data_center or "us"
        # Build ordered list: selected DC first, then all others
        selected_dc_cfg = ZOHO_DATA_CENTERS.get(dc, ZOHO_DATA_CENTERS["us"])
        all_accounts_urls = [selected_dc_cfg["accounts_url"]] + [
            v["accounts_url"] for k, v in ZOHO_DATA_CENTERS.items()
            if v["accounts_url"] != selected_dc_cfg["accounts_url"]
        ]

        token_data = None
        async with httpx.AsyncClient(timeout=15) as client:
            for accounts_url in all_accounts_urls:
                resp = await client.post(
                    f"{accounts_url}/oauth/v2/token",
                    data={
                        "grant_type": "authorization_code",
                        "client_id": merged_creds.get("client_id", ""),
                        "client_secret": merged_creds.get("client_secret", ""),
                        "code": merged_creds["auth_code"],
                        "redirect_uri": "https://www.zoho.com",
                    }
                )
                td = resp.json()
                if resp.status_code == 200 and "refresh_token" in td:
                    token_data = td
                    break  # found the right DC

        if not token_data:
            raise HTTPException(
                status_code=400,
                detail="Failed to exchange authorization code — check your Client ID, Client Secret, and that the code hasn't expired"
            )
        merged_creds["refresh_token"] = token_data["refresh_token"]
        # Also store the api_domain from the token response if provided
        if token_data.get("api_domain"):
            merged_creds["_api_domain"] = token_data["api_domain"]
        # Remove the consumed one-time auth_code — never store it
        merged_creds.pop("auth_code", None)
    
    # Validate required fields against the merged result (skip auth_code — it's optional on edit)
    for field in config.get("fields", []):
        if field.get("required") and field["key"] != "auth_code" and not merged_creds.get(field["key"]):
            raise HTTPException(status_code=400, detail=f"{field['label']} is required")
    
    # For Zoho: require auth_code on first connection (needed to get refresh_token)
    if config.get("is_zoho") and not merged_creds.get("refresh_token") and not merged_creds.get("auth_code"):
        raise HTTPException(status_code=400, detail="Authorization Code is required to establish the connection")
    
    await db.oauth_connections.update_one(
        {"tenant_id": tid, "provider": provider},
        {"$set": {
            "tenant_id": tid,
            "provider": provider,
            "status": "pending",
            "is_validated": False,
            "credentials": merged_creds,
            "data_center": payload.data_center if config.get("is_zoho") else None,
            "settings": payload.settings or (existing.get("settings", {}) if existing else {}),
            "connected_at": existing.get("connected_at", now_iso()) if existing else now_iso(),
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
                    try:
                        err = token_resp.json().get("error", token_resp.json().get("message", "Invalid credentials"))
                    except Exception:
                        err = f"HTTP {token_resp.status_code}"
                    result = {"success": False, "message": f"Token refresh failed: {err}"}
                elif token_resp.json().get("error"):
                    # Zoho returns HTTP 200 with {"error":"..."} for expired/revoked tokens
                    err = token_resp.json().get("error", "unknown")
                    if err in ("invalid_code", "invalid_token", "access_denied"):
                        result = {"success": False, "message": "Refresh token has expired or been revoked — please reconnect with a fresh Authorization Code"}
                    else:
                        result = {"success": False, "message": f"Token refresh failed: {err}"}
                else:
                    token_data = token_resp.json()
                    access_token = token_data.get("access_token")

                    # Helper: try all DC combinations (accounts_url → token → api_domain)
                    # This handles cross-DC accounts where token DC must match API DC
                    async def _zoho_api_get(path: str) -> tuple:
                        """
                        Returns (response, working_api_domain).
                        Tries each DC's accounts_url + api_domain pair until one succeeds.
                        INVALID_URL_PATTERN or invalid token = wrong DC, try next.
                        """
                        # If we stored _api_domain hint during auth code exchange, try it first
                        hint_domain = creds.get("_api_domain")
                        ordered = [(dc_config["accounts_url"], dc_config["api_domain"])] + [
                            (v["accounts_url"], v["api_domain"])
                            for v in ZOHO_DATA_CENTERS.values()
                            if v["api_domain"] != dc_config["api_domain"]
                        ]
                        # Promote the hinted domain to front
                        if hint_domain:
                            ordered = (
                                [(v["accounts_url"], v["api_domain"]) for v in ZOHO_DATA_CENTERS.values() if v["api_domain"] == hint_domain]
                                + [(au, ad) for au, ad in ordered if ad != hint_domain]
                            )
                        last_resp = None
                        for accts_url, api_domain in ordered:
                            # Get a fresh access token from this DC's accounts server
                            if accts_url == dc_config["accounts_url"]:
                                current_token = access_token  # already obtained
                            else:
                                tok_r = await client.post(
                                    f"{accts_url}/oauth/v2/token",
                                    data={
                                        "grant_type": "refresh_token",
                                        "client_id": creds.get("client_id", ""),
                                        "client_secret": creds.get("client_secret", ""),
                                        "refresh_token": creds.get("refresh_token", ""),
                                    }
                                )
                                if tok_r.status_code != 200:
                                    continue  # this accounts server doesn't know this token
                                tok_body = tok_r.json()
                                if tok_body.get("error"):
                                    continue  # Zoho soft error (HTTP 200 with error body)
                                current_token = tok_body.get("access_token", "")
                                if not current_token:
                                    continue

                            r = await client.get(
                                f"{api_domain}{path}",
                                headers={"Authorization": f"Zoho-oauthtoken {current_token}"}
                            )
                            last_resp = r
                            if r.status_code == 200:
                                return r, api_domain
                            # Wrong DC indicators — try next
                            try:
                                err_code = r.json().get("code", "")
                                if err_code not in (
                                    "INVALID_URL_PATTERN",
                                    "INVALID_OAUTH_TOKEN",
                                    "invalid_token",
                                    "AUTHENTICATION_FAILURE",
                                ):
                                    return r, api_domain  # real error, stop here
                            except Exception:
                                return r, api_domain
                        return (last_resp or None), dc_config["api_domain"]

                    # Test API access based on provider
                    if provider == "zoho_mail":
                        # Try each DC's mail_api — use matching accounts_url to get a valid token
                        all_mail_dcs = [(dc_config["accounts_url"], dc_config["mail_api"])] + [
                            (v["accounts_url"], v["mail_api"])
                            for v in ZOHO_DATA_CENTERS.values()
                            if v["mail_api"] != dc_config["mail_api"]
                        ]
                        test_resp = None
                        for accts_url, mail_api in all_mail_dcs:
                            if accts_url == dc_config["accounts_url"]:
                                mail_token = access_token
                            else:
                                tok_r = await client.post(
                                    f"{accts_url}/oauth/v2/token",
                                    data={
                                        "grant_type": "refresh_token",
                                        "client_id": creds.get("client_id", ""),
                                        "client_secret": creds.get("client_secret", ""),
                                        "refresh_token": creds.get("refresh_token", ""),
                                    }
                                )
                                if tok_r.status_code != 200:
                                    continue
                                tok_body = tok_r.json()
                                if tok_body.get("error"):
                                    continue  # Zoho soft error
                                mail_token = tok_body.get("access_token", "")
                                if not mail_token:
                                    continue
                            r = await client.get(
                                f"{mail_api}/accounts",
                                headers={"Authorization": f"Zoho-oauthtoken {mail_token}"}
                            )
                            test_resp = r
                            if r.status_code == 200:
                                accounts = r.json().get("data", [])
                                if accounts:
                                    auto_account_id = str(accounts[0].get("accountId", ""))
                                    if auto_account_id:
                                        await db.oauth_connections.update_one(
                                            {"tenant_id": tid, "provider": "zoho_mail"},
                                            {"$set": {"credentials.account_id": auto_account_id}}
                                        )
                                break
                    elif provider == "zoho_crm":
                        test_resp, _ = await _zoho_api_get("/crm/v3/Leads?per_page=1&fields=id")
                    else:  # zoho_books
                        test_resp, _ = await _zoho_api_get("/books/v3/organizations")

                    if test_resp.status_code == 200:
                        result = {"success": True, "message": f"{config['name']} connection validated successfully"}
                    else:
                        # Expose the actual Zoho error for easier debugging
                        try:
                            err_body = test_resp.json()
                            zoho_code = err_body.get("code", "")
                            zoho_msg  = err_body.get("message", "")
                            if zoho_code == "OAUTH_SCOPE_MISMATCH":
                                detail = "Scope mismatch — re-generate the Authorization Code with the correct scopes (see Setup Guide)"
                            elif zoho_code == "INVALID_URL_PATTERN":
                                detail = "Could not find your account on any Zoho data center — check your credentials and try again"
                            else:
                                detail = zoho_msg or zoho_code or f"HTTP {test_resp.status_code}"
                        except Exception:
                            detail = f"HTTP {test_resp.status_code}"
                        result = {"success": False, "message": f"Could not access {config['name']} API: {detail}"}
            
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


# ---------------------------------------------------------------------------
# Helper: get Zoho connection credentials
# ---------------------------------------------------------------------------

async def _get_zoho_conn_info(tid: str, provider: str):
    """Return (credentials dict, dc_config dict) for a validated Zoho provider."""
    conn = await db.oauth_connections.find_one(
        {"tenant_id": tid, "provider": provider}, {"_id": 0}
    )
    if not conn or not conn.get("is_validated"):
        raise HTTPException(status_code=400, detail=f"{provider} is not connected or validated")
    dc = conn.get("data_center", "us")
    return conn["credentials"], ZOHO_DATA_CENTERS.get(dc, ZOHO_DATA_CENTERS["us"])


# ---------------------------------------------------------------------------
# Zoho Module Discovery (for mapping UI)
# ---------------------------------------------------------------------------

@router.get("/oauth/zoho_crm/modules")
async def get_zoho_crm_modules_for_mapping(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Fetch available Zoho CRM modules using stored credentials."""
    tid = tenant_id_of(admin)
    creds, dc_config = await _get_zoho_conn_info(tid, "zoho_crm")

    async with httpx.AsyncClient(timeout=20.0) as client:
        token_resp = await client.post(
            f"{dc_config['accounts_url']}/oauth/v2/token",
            data={
                "grant_type": "refresh_token",
                "client_id": creds.get("client_id", ""),
                "client_secret": creds.get("client_secret", ""),
                "refresh_token": creds.get("refresh_token", ""),
            },
        )
        if token_resp.status_code != 200 or token_resp.json().get("error"):
            raise HTTPException(status_code=400, detail="Token refresh failed — please reconnect Zoho CRM")

        access_token = token_resp.json()["access_token"]
        api_domain = creds.get("_api_domain", dc_config["api_domain"])

        modules_resp = await client.get(
            f"{api_domain}/crm/v3/settings/modules",
            headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
        )
        if modules_resp.status_code != 200:
            # fallback to v6
            modules_resp = await client.get(
                f"{api_domain}/crm/v6/settings/modules",
                headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
            )

        if modules_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch Zoho CRM modules")

        modules = modules_resp.json().get("modules", [])
        return {
            "modules": [
                {
                    "api_name": m.get("api_name"),
                    "plural_label": m.get("plural_label") or m.get("api_name"),
                    "singular_label": m.get("singular_label") or m.get("api_name"),
                }
                for m in modules
                if m.get("api_supported") and m.get("api_name")
            ]
        }


@router.get("/oauth/zoho_books/modules")
async def get_zoho_books_modules_for_mapping(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Return fixed list of Zoho Books modules (Books uses resource-based URLs, not module API)."""
    tid = tenant_id_of(admin)
    conn = await db.oauth_connections.find_one({"tenant_id": tid, "provider": "zoho_books"}, {"_id": 0})
    if not conn or not conn.get("is_validated"):
        raise HTTPException(status_code=400, detail="Zoho Books is not connected or validated")
    return {
        "modules": [
            {"api_name": "contacts", "plural_label": "Contacts", "singular_label": "Contact"},
            {"api_name": "invoices", "plural_label": "Invoices", "singular_label": "Invoice"},
            {"api_name": "estimates", "plural_label": "Estimates", "singular_label": "Estimate"},
            {"api_name": "bills", "plural_label": "Bills", "singular_label": "Bill"},
            {"api_name": "recurringinvoices", "plural_label": "Recurring Invoices", "singular_label": "Recurring Invoice"},
        ]
    }


# ---------------------------------------------------------------------------
# Zoho CRM Bulk Sync
# ---------------------------------------------------------------------------

@router.post("/oauth/zoho_crm/bulk-sync")
async def zoho_crm_bulk_sync(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Bulk sync existing webapp records to Zoho CRM using saved field mappings."""
    tid = tenant_id_of(admin)
    creds, dc_config = await _get_zoho_conn_info(tid, "zoho_crm")

    # Load active CRM mappings (include legacy mappings without provider field)
    mappings = await db.crm_mappings.find(
        {
            "tenant_id": tid,
            "is_active": True,
            "$or": [{"provider": "zoho_crm"}, {"provider": {"$exists": False}}],
        },
        {"_id": 0},
    ).to_list(20)

    if not mappings:
        return {"success": False, "message": "No active mappings configured. Set up entity mappings first."}

    async with httpx.AsyncClient(timeout=60.0) as client:
        token_resp = await client.post(
            f"{dc_config['accounts_url']}/oauth/v2/token",
            data={
                "grant_type": "refresh_token",
                "client_id": creds.get("client_id", ""),
                "client_secret": creds.get("client_secret", ""),
                "refresh_token": creds.get("refresh_token", ""),
            },
        )
        if token_resp.status_code != 200 or token_resp.json().get("error"):
            raise HTTPException(status_code=400, detail="Token refresh failed — please reconnect Zoho CRM")

        access_token = token_resp.json()["access_token"]
        api_domain = creds.get("_api_domain", dc_config["api_domain"])

        synced_counts: Dict[str, int] = {}
        errors: List[str] = []

        collection_map: Dict[str, Any] = {
            "customers": db.customers,
            "orders": db.orders,
            "subscriptions": db.subscriptions,
            "quote_requests": db.quote_requests,
        }

        for mapping in mappings:
            webapp_module = mapping.get("webapp_module")
            crm_module = mapping.get("crm_module")
            field_maps = mapping.get("field_mappings", [])

            if not webapp_module or not crm_module or not field_maps:
                continue

            coll = collection_map.get(webapp_module)
            if coll is None:
                continue

            docs = await coll.find({"tenant_id": tid}, {"_id": 0}).to_list(500)

            zoho_records = []
            for record in docs:
                zoho_record: Dict[str, Any] = {}
                for fm in field_maps:
                    wf = fm.get("webapp_field")
                    cf = fm.get("crm_field")
                    if wf and cf:
                        val = record.get(wf)
                        if val is not None:
                            zoho_record[cf] = val if isinstance(val, (int, float, bool)) else str(val)
                if zoho_record:
                    zoho_records.append(zoho_record)

            synced = 0
            for i in range(0, len(zoho_records), 100):
                batch = zoho_records[i : i + 100]
                resp = await client.post(
                    f"{api_domain}/crm/v3/{crm_module}",
                    json={"data": batch},
                    headers={
                        "Authorization": f"Zoho-oauthtoken {access_token}",
                        "Content-Type": "application/json",
                    },
                )
                if resp.status_code in [200, 201]:
                    resp_data = resp.json().get("data", [])
                    if resp_data and isinstance(resp_data[0], dict) and "code" in resp_data[0]:
                        synced += sum(1 for d in resp_data if d.get("code") in ("SUCCESS", "RECORD_ADDED"))
                    else:
                        synced += len(batch)
                else:
                    try:
                        err = resp.json()
                        errors.append(f"{webapp_module}→{crm_module}: {err.get('message', str(err))[:80]}")
                    except Exception:
                        errors.append(f"{webapp_module}→{crm_module}: HTTP {resp.status_code}")

            synced_counts[f"{webapp_module}→{crm_module}"] = synced

    total = sum(synced_counts.values())
    return {
        "success": len(errors) == 0,
        "synced": synced_counts,
        "total_synced": total,
        "errors": errors[:5],
        "message": (
            f"Sync completed. {total} records synced."
            if not errors
            else f"Sync completed with {len(errors)} error(s). {total} records synced."
        ),
    }


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
