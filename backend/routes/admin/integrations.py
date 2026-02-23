"""Admin routes for Zoho Mail and CRM integrations."""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from core.tenant import get_tenant_admin, get_tenant_filter, tenant_id_of
from services.zoho_service import (
    ZohoOAuthService, ZohoMailService, ZohoCRMService,
    get_crm_field_mappings, save_crm_field_mapping, delete_crm_field_mapping
)
from services.audit_service import create_audit_log
from db.session import db

router = APIRouter(prefix="/api", tags=["admin-integrations"])


# === Pydantic Models ===

class ZohoCredentials(BaseModel):
    client_id: str
    client_secret: str
    datacenter: str = "US"  # US or CA
    redirect_uri: Optional[str] = None


class ZohoTokenExchange(BaseModel):
    code: str
    client_id: str
    client_secret: str
    redirect_uri: str
    datacenter: str = "US"


class ZohoValidateRequest(BaseModel):
    access_token: str
    datacenter: str = "US"


class CRMFieldMapping(BaseModel):
    id: Optional[str] = None
    webapp_module: str  # customers, orders, subscriptions, quote_requests
    crm_module: str  # Leads, Contacts, Accounts, Deals
    field_mappings: List[Dict[str, str]]  # [{webapp_field: "email", crm_field: "Email"}]
    sync_on_create: bool = True
    sync_on_update: bool = True
    is_active: bool = True


# === Email Provider Settings (Resend + Zoho Mail) ===

@router.get("/admin/integrations/email-providers")
async def get_email_providers(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Get configured email providers (Resend and Zoho Mail)."""
    tid = tenant_id_of(admin)
    
    # Get settings
    resend_key = await db.app_settings.find_one(
        {"tenant_id": tid, "key": "resend_api_key"},
        {"_id": 0}
    )
    
    zoho_mail = await db.integrations.find_one(
        {"tenant_id": tid, "service": "zoho_mail"},
        {"_id": 0}
    )
    
    return {
        "providers": {
            "resend": {
                "configured": bool(resend_key and resend_key.get("value")),
                "key_set": bool(resend_key and resend_key.get("value"))
            },
            "zoho_mail": {
                "configured": bool(zoho_mail and zoho_mail.get("credentials")),
                "datacenter": zoho_mail.get("datacenter") if zoho_mail else None,
                "connected_at": zoho_mail.get("updated_at") if zoho_mail else None
            }
        }
    }


@router.post("/admin/integrations/resend/validate")
async def validate_resend(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Validate Resend API key by making a test API call."""
    import httpx
    
    tid = tenant_id_of(admin)
    setting = await db.app_settings.find_one(
        {"tenant_id": tid, "key": "resend_api_key"},
        {"_id": 0}
    )
    
    if not setting or not setting.get("value"):
        raise HTTPException(status_code=400, detail="Resend API key not configured")
    
    api_key = setting["value"]
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.resend.com/domains",
                headers={"Authorization": f"Bearer {api_key}"}
            )
            
            if response.status_code == 200:
                domains = response.json().get("data", [])
                return {
                    "success": True,
                    "message": "Resend connection validated",
                    "domains_count": len(domains),
                    "domains": [d.get("name") for d in domains]
                }
            else:
                return {
                    "success": False,
                    "message": f"Validation failed: {response.status_code}",
                    "error": response.text
                }
    except Exception as e:
        return {"success": False, "message": str(e)}


# === Zoho Mail Integration ===

@router.post("/admin/integrations/zoho-mail/save-credentials")
async def save_zoho_mail_credentials(
    credentials: ZohoCredentials,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Save Zoho Mail OAuth credentials."""
    tid = tenant_id_of(admin)
    
    await db.integrations.update_one(
        {"tenant_id": tid, "service": "zoho_mail"},
        {"$set": {
            "tenant_id": tid,
            "service": "zoho_mail",
            "datacenter": credentials.datacenter.upper(),
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "redirect_uri": credentials.redirect_uri
        }},
        upsert=True
    )
    
    await create_audit_log(
        entity_type="integration",
        entity_id="zoho_mail",
        action="credentials_saved",
        actor=admin.get("email", "admin"),
        details={"datacenter": credentials.datacenter}
    )
    
    return {"success": True, "message": "Zoho Mail credentials saved"}


@router.post("/admin/integrations/zoho-mail/exchange-token")
async def exchange_zoho_mail_token(
    payload: ZohoTokenExchange,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Exchange authorization code for Zoho Mail tokens."""
    tid = tenant_id_of(admin)
    oauth = ZohoOAuthService(tid, payload.datacenter)
    
    try:
        tokens = await oauth.exchange_code_for_tokens(
            payload.code,
            payload.client_id,
            payload.client_secret,
            payload.redirect_uri
        )
        
        # Store tokens
        await oauth.store_credentials("mail", {
            "access_token": tokens.get("access_token"),
            "refresh_token": tokens.get("refresh_token"),
            "expires_in": tokens.get("expires_in"),
            "token_type": tokens.get("token_type")
        })
        
        return {"success": True, "message": "Zoho Mail connected successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/admin/integrations/zoho-mail/validate")
async def validate_zoho_mail(
    payload: ZohoValidateRequest,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Validate Zoho Mail connection."""
    tid = tenant_id_of(admin)
    mail_service = ZohoMailService(tid, payload.datacenter)
    
    result = await mail_service.validate_connection(payload.access_token)
    return result


@router.post("/admin/integrations/zoho-mail/refresh-token")
async def refresh_zoho_mail_token(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Refresh Zoho Mail access token."""
    tid = tenant_id_of(admin)
    
    integration = await db.integrations.find_one(
        {"tenant_id": tid, "service": "zoho_mail"},
        {"_id": 0}
    )
    
    if not integration or not integration.get("credentials"):
        raise HTTPException(status_code=400, detail="Zoho Mail not configured")
    
    oauth = ZohoOAuthService(tid, integration.get("datacenter", "US"))
    
    try:
        new_tokens = await oauth.refresh_access_token(
            integration["credentials"]["refresh_token"],
            integration["client_id"],
            integration["client_secret"]
        )
        
        await oauth.store_credentials("mail", {
            **integration["credentials"],
            "access_token": new_tokens.get("access_token"),
            "expires_in": new_tokens.get("expires_in")
        })
        
        return {"success": True, "access_token": new_tokens.get("access_token")}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# === Zoho CRM Integration ===

@router.post("/admin/integrations/zoho-crm/save-credentials")
async def save_zoho_crm_credentials(
    credentials: ZohoCredentials,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Save Zoho CRM OAuth credentials."""
    tid = tenant_id_of(admin)
    
    await db.integrations.update_one(
        {"tenant_id": tid, "service": "zoho_crm"},
        {"$set": {
            "tenant_id": tid,
            "service": "zoho_crm",
            "datacenter": credentials.datacenter.upper(),
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "redirect_uri": credentials.redirect_uri
        }},
        upsert=True
    )
    
    await create_audit_log(
        entity_type="integration",
        entity_id="zoho_crm",
        action="credentials_saved",
        actor=admin.get("email", "admin"),
        details={"datacenter": credentials.datacenter}
    )
    
    return {"success": True, "message": "Zoho CRM credentials saved"}


@router.post("/admin/integrations/zoho-crm/exchange-token")
async def exchange_zoho_crm_token(
    payload: ZohoTokenExchange,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Exchange authorization code for Zoho CRM tokens."""
    tid = tenant_id_of(admin)
    oauth = ZohoOAuthService(tid, payload.datacenter)
    
    try:
        tokens = await oauth.exchange_code_for_tokens(
            payload.code,
            payload.client_id,
            payload.client_secret,
            payload.redirect_uri
        )
        
        await oauth.store_credentials("crm", {
            "access_token": tokens.get("access_token"),
            "refresh_token": tokens.get("refresh_token"),
            "expires_in": tokens.get("expires_in"),
            "token_type": tokens.get("token_type")
        })
        
        return {"success": True, "message": "Zoho CRM connected successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/admin/integrations/zoho-crm/validate")
async def validate_zoho_crm(
    payload: ZohoValidateRequest,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Validate Zoho CRM connection and return available modules."""
    tid = tenant_id_of(admin)
    crm_service = ZohoCRMService(tid, payload.datacenter)
    
    result = await crm_service.validate_connection(payload.access_token)
    return result


@router.get("/admin/integrations/zoho-crm/modules")
async def get_zoho_crm_modules(
    access_token: str = Query(...),
    datacenter: str = Query("US"),
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Get available Zoho CRM modules."""
    tid = tenant_id_of(admin)
    crm_service = ZohoCRMService(tid, datacenter)
    
    result = await crm_service.get_modules(access_token)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    modules = result.get("modules", [])
    return {
        "modules": [
            {
                "api_name": m.get("api_name"),
                "module_name": m.get("module_name"),
                "singular_label": m.get("singular_label"),
                "plural_label": m.get("plural_label")
            }
            for m in modules if m.get("api_supported")
        ]
    }


@router.get("/admin/integrations/zoho-crm/modules/{module_name}/fields")
async def get_zoho_crm_module_fields(
    module_name: str,
    access_token: str = Query(...),
    datacenter: str = Query("US"),
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Get fields for a specific Zoho CRM module."""
    tid = tenant_id_of(admin)
    crm_service = ZohoCRMService(tid, datacenter)
    
    result = await crm_service.get_module_fields(access_token, module_name)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    fields = result.get("fields", [])
    return {
        "module": module_name,
        "fields": [
            {
                "api_name": f.get("api_name"),
                "field_label": f.get("field_label"),
                "data_type": f.get("data_type"),
                "required": f.get("system_mandatory", False),
                "read_only": f.get("read_only", False),
                "custom_field": f.get("custom_field", False),
                "max_length": f.get("length"),
                "pick_list_values": [
                    {"value": p.get("display_value"), "id": p.get("id")}
                    for p in f.get("pick_list_values", [])
                ] if f.get("pick_list_values") else None
            }
            for f in fields
        ]
    }


# === CRM Field Mappings ===

@router.get("/admin/integrations/crm-mappings")
async def get_crm_mappings(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Get all CRM field mappings for the tenant."""
    tid = tenant_id_of(admin)
    mappings = await get_crm_field_mappings(tid)
    
    # Define webapp modules available for mapping
    webapp_modules = [
        {"name": "customers", "label": "Customers", "fields": [
            "email", "full_name", "company_name", "phone", "currency", "is_active", "created_at"
        ]},
        {"name": "orders", "label": "Orders", "fields": [
            "order_number", "status", "total", "currency", "payment_method", "type", "created_at"
        ]},
        {"name": "subscriptions", "label": "Subscriptions", "fields": [
            "subscription_number", "plan_name", "status", "amount", "currency", "billing_cycle", "created_at"
        ]},
        {"name": "quote_requests", "label": "Quote Requests", "fields": [
            "email", "contact_name", "company_name", "phone", "message", "status", "created_at"
        ]}
    ]
    
    return {
        "mappings": mappings,
        "webapp_modules": webapp_modules
    }


@router.post("/admin/integrations/crm-mappings")
async def create_crm_mapping(
    mapping: CRMFieldMapping,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Create or update a CRM field mapping."""
    tid = tenant_id_of(admin)
    
    import uuid
    mapping_data = mapping.dict()
    if not mapping_data.get("id"):
        mapping_data["id"] = str(uuid.uuid4())
    
    result = await save_crm_field_mapping(tid, mapping_data)
    
    await create_audit_log(
        entity_type="crm_mapping",
        entity_id=mapping_data["id"],
        action="mapping_saved",
        actor=admin.get("email", "admin"),
        details={"webapp_module": mapping.webapp_module, "crm_module": mapping.crm_module}
    )
    
    return result


@router.delete("/admin/integrations/crm-mappings/{mapping_id}")
async def remove_crm_mapping(
    mapping_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Delete a CRM field mapping."""
    tid = tenant_id_of(admin)
    result = await delete_crm_field_mapping(tid, mapping_id)
    
    if result["success"]:
        await create_audit_log(
            entity_type="crm_mapping",
            entity_id=mapping_id,
            action="mapping_deleted",
            actor=admin.get("email", "admin")
        )
    
    return result


# === Integration Status ===

@router.get("/admin/integrations/status")
async def get_all_integrations_status(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Get status of all integrations."""
    tid = tenant_id_of(admin)
    
    integrations = await db.integrations.find(
        {"tenant_id": tid},
        {"_id": 0, "credentials": 0, "client_secret": 0}
    ).to_list(20)
    
    # Get Resend status
    resend_key = await db.app_settings.find_one(
        {"tenant_id": tid, "key": "resend_api_key"},
        {"_id": 0}
    )
    
    # Get Stripe status
    stripe_key = await db.app_settings.find_one(
        {"tenant_id": tid, "key": "stripe_secret_key"},
        {"_id": 0}
    )
    
    # Get GoCardless status
    gc_key = await db.app_settings.find_one(
        {"tenant_id": tid, "key": "gocardless_access_token"},
        {"_id": 0}
    )
    
    return {
        "integrations": {
            "resend": {
                "status": "connected" if (resend_key and resend_key.get("value")) else "not_configured",
                "type": "email"
            },
            "zoho_mail": next(
                ({"status": "connected" if i.get("credentials") else "credentials_only", 
                  "datacenter": i.get("datacenter"), "type": "email"}
                 for i in integrations if i.get("service") == "zoho_mail"),
                {"status": "not_configured", "type": "email"}
            ),
            "zoho_crm": next(
                ({"status": "connected" if i.get("credentials") else "credentials_only",
                  "datacenter": i.get("datacenter"), "type": "crm"}
                 for i in integrations if i.get("service") == "zoho_crm"),
                {"status": "not_configured", "type": "crm"}
            ),
            "stripe": {
                "status": "connected" if (stripe_key and stripe_key.get("value")) else "not_configured",
                "type": "payment"
            },
            "gocardless": {
                "status": "connected" if (gc_key and gc_key.get("value")) else "not_configured",
                "type": "payment"
            }
        }
    }
