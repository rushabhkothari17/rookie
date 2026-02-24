"""
OAuth Service for third-party integrations.

Handles OAuth 2.0 flows for:
- Zoho (CRM, Books, Mail)
- Stripe Connect
- GoCardless
"""
from __future__ import annotations

import os
import secrets
from typing import Any, Dict, Optional
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode
import httpx

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from core.helpers import make_id, now_iso
from core.tenant import get_tenant_admin, tenant_id_of
from db.session import db

router = APIRouter(prefix="/api", tags=["oauth"])

# OAuth Configuration - These would come from environment variables in production
OAUTH_CONFIGS = {
    "zoho_crm": {
        "name": "Zoho CRM",
        "authorize_url": "https://accounts.zoho.com/oauth/v2/auth",
        "token_url": "https://accounts.zoho.com/oauth/v2/token",
        "scopes": ["ZohoCRM.modules.ALL", "ZohoCRM.settings.ALL", "ZohoCRM.users.READ"],
        "client_id_env": "ZOHO_CLIENT_ID",
        "client_secret_env": "ZOHO_CLIENT_SECRET",
    },
    "zoho_books": {
        "name": "Zoho Books",
        "authorize_url": "https://accounts.zoho.com/oauth/v2/auth",
        "token_url": "https://accounts.zoho.com/oauth/v2/token",
        "scopes": ["ZohoBooks.fullaccess.all"],
        "client_id_env": "ZOHO_CLIENT_ID",
        "client_secret_env": "ZOHO_CLIENT_SECRET",
    },
    "zoho_mail": {
        "name": "Zoho Mail",
        "authorize_url": "https://accounts.zoho.com/oauth/v2/auth",
        "token_url": "https://accounts.zoho.com/oauth/v2/token",
        "scopes": ["ZohoMail.messages.CREATE", "ZohoMail.accounts.READ"],
        "client_id_env": "ZOHO_CLIENT_ID",
        "client_secret_env": "ZOHO_CLIENT_SECRET",
    },
    "stripe": {
        "name": "Stripe",
        "authorize_url": "https://connect.stripe.com/oauth/authorize",
        "token_url": "https://connect.stripe.com/oauth/token",
        "scopes": ["read_write"],
        "client_id_env": "STRIPE_CLIENT_ID",
        "client_secret_env": "STRIPE_SECRET_KEY",
    },
    "stripe_test": {
        "name": "Stripe (Test Mode)",
        "authorize_url": "https://connect.stripe.com/oauth/authorize",
        "token_url": "https://connect.stripe.com/oauth/token",
        "scopes": ["read_write"],
        "client_id_env": "STRIPE_TEST_CLIENT_ID",
        "client_secret_env": "STRIPE_TEST_SECRET_KEY",
    },
    "gocardless": {
        "name": "GoCardless",
        "authorize_url": "https://connect.gocardless.com/oauth/authorize",
        "token_url": "https://connect.gocardless.com/oauth/access_token",
        "scopes": ["full_access"],
        "client_id_env": "GOCARDLESS_CLIENT_ID",
        "client_secret_env": "GOCARDLESS_CLIENT_SECRET",
    },
    "gocardless_sandbox": {
        "name": "GoCardless (Sandbox)",
        "authorize_url": "https://connect-sandbox.gocardless.com/oauth/authorize",
        "token_url": "https://connect-sandbox.gocardless.com/oauth/access_token",
        "scopes": ["full_access"],
        "client_id_env": "GOCARDLESS_SANDBOX_CLIENT_ID",
        "client_secret_env": "GOCARDLESS_SANDBOX_CLIENT_SECRET",
    },
}


def get_frontend_url() -> str:
    """Get the frontend URL for OAuth callbacks."""
    return os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:3000")


@router.get("/oauth/integrations")
async def list_integrations(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """List all available OAuth integrations and their current status."""
    tid = tenant_id_of(admin)
    
    # Get stored connections for this tenant
    connections = await db.oauth_connections.find(
        {"tenant_id": tid},
        {"_id": 0}
    ).to_list(50)
    
    conn_map = {c["provider"]: c for c in connections}
    
    integrations = []
    for provider_id, config in OAUTH_CONFIGS.items():
        conn = conn_map.get(provider_id, {})
        
        # Check if credentials are configured
        client_id = os.environ.get(config["client_id_env"], "")
        has_credentials = bool(client_id)
        
        integrations.append({
            "id": provider_id,
            "name": config["name"],
            "status": conn.get("status", "not_connected"),
            "connected_at": conn.get("connected_at"),
            "last_refresh": conn.get("last_refresh"),
            "expires_at": conn.get("expires_at"),
            "error_message": conn.get("error_message"),
            "has_credentials": has_credentials,
            "can_connect": has_credentials,
        })
    
    return {"integrations": integrations}


@router.get("/oauth/{provider}/connect")
async def initiate_oauth(
    provider: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """
    Initiate OAuth flow for a provider.
    
    Returns the authorization URL to redirect the user to.
    """
    if provider not in OAUTH_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    
    config = OAUTH_CONFIGS[provider]
    tid = tenant_id_of(admin)
    
    # Get OAuth credentials from environment
    client_id = os.environ.get(config["client_id_env"], "")
    if not client_id:
        raise HTTPException(
            status_code=400,
            detail=f"OAuth not configured for {config['name']}. Please contact support."
        )
    
    # Generate state token for CSRF protection
    state = secrets.token_urlsafe(32)
    
    # Store state in database with tenant association
    await db.oauth_states.insert_one({
        "state": state,
        "tenant_id": tid,
        "provider": provider,
        "admin_id": admin["id"],
        "created_at": now_iso(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
    })
    
    # Update connection status to "connecting"
    await db.oauth_connections.update_one(
        {"tenant_id": tid, "provider": provider},
        {"$set": {
            "tenant_id": tid,
            "provider": provider,
            "status": "connecting",
            "updated_at": now_iso()
        }},
        upsert=True
    )
    
    # Build authorization URL
    callback_url = f"{get_frontend_url()}/api/oauth/{provider}/callback"
    
    params = {
        "client_id": client_id,
        "redirect_uri": callback_url,
        "state": state,
        "response_type": "code",
    }
    
    # Provider-specific parameters
    if provider.startswith("zoho"):
        params["scope"] = ",".join(config["scopes"])
        params["access_type"] = "offline"  # For refresh token
        params["prompt"] = "consent"
    elif provider.startswith("stripe"):
        params["scope"] = config["scopes"][0]
        params["stripe_landing"] = "login"
    elif provider.startswith("gocardless"):
        params["scope"] = config["scopes"][0]
        params["initial_view"] = "login"
    
    auth_url = f"{config['authorize_url']}?{urlencode(params)}"
    
    return {
        "authorization_url": auth_url,
        "state": state,
        "provider": provider
    }


@router.get("/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None)
):
    """
    OAuth callback handler.
    
    Exchanges the authorization code for access tokens.
    """
    if provider not in OAUTH_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    
    frontend_url = get_frontend_url()
    
    # Handle error response from provider
    if error:
        return RedirectResponse(
            url=f"{frontend_url}/admin?oauth_error={error}&provider={provider}",
            status_code=302
        )
    
    if not code or not state:
        return RedirectResponse(
            url=f"{frontend_url}/admin?oauth_error=missing_params&provider={provider}",
            status_code=302
        )
    
    # Verify state token
    state_doc = await db.oauth_states.find_one_and_delete({"state": state})
    if not state_doc:
        return RedirectResponse(
            url=f"{frontend_url}/admin?oauth_error=invalid_state&provider={provider}",
            status_code=302
        )
    
    # Check if state expired
    if datetime.fromisoformat(state_doc["expires_at"]) < datetime.now(timezone.utc):
        await db.oauth_connections.update_one(
            {"tenant_id": state_doc["tenant_id"], "provider": provider},
            {"$set": {"status": "failed", "error_message": "Authorization expired"}}
        )
        return RedirectResponse(
            url=f"{frontend_url}/admin?oauth_error=expired&provider={provider}",
            status_code=302
        )
    
    tid = state_doc["tenant_id"]
    config = OAUTH_CONFIGS[provider]
    
    # Exchange code for tokens
    client_id = os.environ.get(config["client_id_env"], "")
    client_secret = os.environ.get(config["client_secret_env"], "")
    callback_url = f"{frontend_url}/api/oauth/{provider}/callback"
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            token_data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": callback_url,
                "client_id": client_id,
                "client_secret": client_secret,
            }
            
            # Provider-specific token request
            if provider.startswith("stripe"):
                response = await client.post(
                    config["token_url"],
                    data=token_data
                )
            else:
                response = await client.post(
                    config["token_url"],
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
                    url=f"{frontend_url}/admin?oauth_error=token_exchange&provider={provider}",
                    status_code=302
                )
            
            tokens = response.json()
            
            # Calculate token expiry
            expires_in = tokens.get("expires_in", 3600)
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
            
            # Store tokens
            await db.oauth_connections.update_one(
                {"tenant_id": tid, "provider": provider},
                {"$set": {
                    "status": "connected",
                    "access_token": tokens.get("access_token"),
                    "refresh_token": tokens.get("refresh_token"),
                    "token_type": tokens.get("token_type", "Bearer"),
                    "expires_at": expires_at,
                    "scope": tokens.get("scope"),
                    "connected_at": now_iso(),
                    "last_refresh": now_iso(),
                    "error_message": None,
                    "updated_at": now_iso(),
                    # Stripe-specific
                    "stripe_user_id": tokens.get("stripe_user_id"),
                    "stripe_publishable_key": tokens.get("stripe_publishable_key"),
                    # GoCardless-specific
                    "organisation_id": tokens.get("organisation_id"),
                }}
            )
            
            return RedirectResponse(
                url=f"{frontend_url}/admin?oauth_success=true&provider={provider}",
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
            url=f"{frontend_url}/admin?oauth_error=exception&provider={provider}",
            status_code=302
        )


@router.post("/oauth/{provider}/refresh")
async def refresh_oauth_token(
    provider: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Refresh an OAuth access token using the refresh token."""
    if provider not in OAUTH_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    
    tid = tenant_id_of(admin)
    config = OAUTH_CONFIGS[provider]
    
    # Get current connection
    connection = await db.oauth_connections.find_one(
        {"tenant_id": tid, "provider": provider},
        {"_id": 0}
    )
    
    if not connection or not connection.get("refresh_token"):
        raise HTTPException(status_code=400, detail="No refresh token available")
    
    client_id = os.environ.get(config["client_id_env"], "")
    client_secret = os.environ.get(config["client_secret_env"], "")
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            token_data = {
                "grant_type": "refresh_token",
                "refresh_token": connection["refresh_token"],
                "client_id": client_id,
                "client_secret": client_secret,
            }
            
            response = await client.post(
                config["token_url"],
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code != 200:
                error_msg = response.text[:200]
                await db.oauth_connections.update_one(
                    {"tenant_id": tid, "provider": provider},
                    {"$set": {
                        "status": "failed",
                        "error_message": f"Token refresh failed: {error_msg}",
                        "updated_at": now_iso()
                    }}
                )
                raise HTTPException(status_code=400, detail="Token refresh failed")
            
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
    
    tid = tenant_id_of(admin)
    
    # Remove the connection
    result = await db.oauth_connections.delete_one(
        {"tenant_id": tid, "provider": provider}
    )
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    return {"success": True, "message": f"{OAUTH_CONFIGS[provider]['name']} disconnected"}


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
        {"_id": 0, "access_token": 0, "refresh_token": 0}  # Don't expose tokens
    )
    
    if not connection:
        return {
            "provider": provider,
            "name": config["name"],
            "status": "not_connected",
            "can_connect": bool(os.environ.get(config["client_id_env"], ""))
        }
    
    # Check if token is expired
    is_expired = False
    if connection.get("expires_at"):
        try:
            expires_at = datetime.fromisoformat(connection["expires_at"].replace("Z", "+00:00"))
            is_expired = expires_at < datetime.now(timezone.utc)
        except:
            pass
    
    return {
        "provider": provider,
        "name": config["name"],
        "status": "expired" if is_expired else connection.get("status", "not_connected"),
        "connected_at": connection.get("connected_at"),
        "last_refresh": connection.get("last_refresh"),
        "expires_at": connection.get("expires_at"),
        "is_expired": is_expired,
        "error_message": connection.get("error_message"),
        "can_connect": bool(os.environ.get(config["client_id_env"], "")),
        # Provider-specific info
        "stripe_user_id": connection.get("stripe_user_id"),
        "organisation_id": connection.get("organisation_id"),
    }
