"""Payment credential validation endpoints."""
from __future__ import annotations

import httpx
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends

from core.tenant import get_tenant_admin
from db.session import db
from services.audit_service import create_audit_log

router = APIRouter(prefix="/api", tags=["payment-validation"])


@router.post("/admin/payment/validate")
async def validate_payment_credentials(
    payload: Dict[str, Any] = Body(...),
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """Test payment provider credentials before enabling them."""
    provider = payload.get("provider", "").lower()

    if provider == "stripe":
        secret_key = payload.get("secret_key", "").strip()
        if not secret_key:
            return {"success": False, "error": "Secret key is required"}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    "https://api.stripe.com/v1/balance",
                    headers={"Authorization": f"Bearer {secret_key}"},
                )
            if r.status_code == 200:
                data = r.json()
                mode = "live" if secret_key.startswith("sk_live") else "test"
                await create_audit_log(entity_type="integration", entity_id="stripe", action="credentials_validated", actor=admin.get("email", "admin"), details={"provider": "stripe", "mode": mode, "success": True})
                return {"success": True, "mode": mode, "message": f"Stripe connected ({mode} mode)"}
            elif r.status_code == 401:
                await create_audit_log(entity_type="integration", entity_id="stripe", action="credentials_validated", actor=admin.get("email", "admin"), details={"provider": "stripe", "success": False})
                return {"success": False, "error": "Invalid Stripe secret key. Check your key at dashboard.stripe.com/apikeys"}
            else:
                return {"success": False, "error": f"Stripe returned status {r.status_code}"}
        except httpx.TimeoutException:
            return {"success": False, "error": "Connection timed out. Please check your internet connection."}
        except Exception as e:
            return {"success": False, "error": f"Connection failed: {str(e)}"}

    elif provider == "gocardless":
        access_token = payload.get("access_token", "").strip()
        environment = payload.get("environment", "sandbox").strip().lower()
        if not access_token:
            return {"success": False, "error": "Access token is required"}
        base_url = (
            "https://api-sandbox.gocardless.com"
            if environment == "sandbox"
            else "https://api.gocardless.com"
        )
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"{base_url}/creditors",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "GoCardless-Version": "2015-07-06",
                        "Content-Type": "application/json",
                    },
                )
            if r.status_code == 200:
                data = r.json()
                creditors = data.get("creditors", [])
                name = creditors[0].get("name", "Account") if creditors else "Account"
                await create_audit_log(entity_type="integration", entity_id="gocardless", action="credentials_validated", actor=admin.get("email", "admin"), details={"provider": "gocardless", "environment": environment, "success": True})
                return {"success": True, "mode": environment, "message": f"GoCardless connected — {name} ({environment})"}
            elif r.status_code == 401:
                await create_audit_log(entity_type="integration", entity_id="gocardless", action="credentials_validated", actor=admin.get("email", "admin"), details={"provider": "gocardless", "success": False})
                return {"success": False, "error": "Invalid access token. Get yours at manage.gocardless.com/developers/access-tokens"}
            else:
                return {"success": False, "error": f"GoCardless returned status {r.status_code}"}
        except httpx.TimeoutException:
            return {"success": False, "error": "Connection timed out."}
        except Exception as e:
            return {"success": False, "error": f"Connection failed: {str(e)}"}

    return {"success": False, "error": f"Unknown provider: {provider}"}
