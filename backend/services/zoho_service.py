"""Zoho Mail and CRM integration services with multi-datacenter support."""
import httpx
import hashlib
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from db.session import db
from services.audit_service import create_audit_log

logger = logging.getLogger(__name__)

# Datacenter configurations
ZOHO_DATACENTERS = {
    "US": {
        "accounts_url": "https://accounts.zoho.com",
        "mail_url": "https://mail.zoho.com",
        "crm_url": "https://www.zohoapis.com",
    },
    "CA": {
        "accounts_url": "https://accounts.zohocloud.ca",
        "mail_url": "https://mail.zohocloud.ca",
        "crm_url": "https://www.zohoapis.ca",
    },
}


class ZohoOAuthService:
    """Handles Zoho OAuth2 authentication for both Mail and CRM."""
    
    def __init__(self, tenant_id: str, datacenter: str = "US"):
        self.tenant_id = tenant_id
        self.datacenter = datacenter.upper()
        self.dc_config = ZOHO_DATACENTERS.get(self.datacenter, ZOHO_DATACENTERS["US"])
    
    async def get_credentials(self, service: str = "mail") -> Optional[Dict[str, Any]]:
        """Get stored OAuth credentials for a service (mail or crm)."""
        key = f"zoho_{service}"
        creds = await db.integrations.find_one(
            {"tenant_id": self.tenant_id, "service": key},
            {"_id": 0}
        )
        return creds
    
    async def store_credentials(self, service: str, credentials: Dict[str, Any]) -> None:
        """Store OAuth credentials for a service."""
        key = f"zoho_{service}"
        await db.integrations.update_one(
            {"tenant_id": self.tenant_id, "service": key},
            {"$set": {
                "tenant_id": self.tenant_id,
                "service": key,
                "datacenter": self.datacenter,
                "credentials": credentials,
                "updated_at": datetime.utcnow().isoformat()
            }},
            upsert=True
        )
    
    def get_authorization_url(self, service: str, redirect_uri: str, client_id: str) -> str:
        """Generate OAuth2 authorization URL."""
        scopes = {
            "mail": "ZohoMail.accounts.ALL,ZohoMail.messages.CREATE,ZohoMail.messages.READ",
            "crm": "ZohoCRM.modules.ALL,ZohoCRM.settings.fields.ALL,ZohoCRM.settings.modules.ALL"
        }
        
        params = {
            "client_id": client_id,
            "response_type": "code",
            "scope": scopes.get(service, scopes["mail"]),
            "redirect_uri": redirect_uri,
            "access_type": "offline"
        }
        
        param_str = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.dc_config['accounts_url']}/oauth/v2/auth?{param_str}"
    
    async def exchange_code_for_tokens(
        self, 
        code: str, 
        client_id: str, 
        client_secret: str, 
        redirect_uri: str
    ) -> Dict[str, Any]:
        """Exchange authorization code for access and refresh tokens."""
        token_url = f"{self.dc_config['accounts_url']}/oauth/v2/token"
        
        payload = {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(token_url, data=payload)
            response.raise_for_status()
            return response.json()
    
    async def refresh_access_token(
        self, 
        refresh_token: str, 
        client_id: str, 
        client_secret: str
    ) -> Dict[str, Any]:
        """Refresh expired access token."""
        token_url = f"{self.dc_config['accounts_url']}/oauth/v2/token"
        
        payload = {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(token_url, data=payload)
            response.raise_for_status()
            return response.json()


class ZohoMailService:
    """Service for sending emails via Zoho Mail API."""
    
    def __init__(self, tenant_id: str, datacenter: str = "US"):
        self.tenant_id = tenant_id
        self.datacenter = datacenter.upper()
        self.dc_config = ZOHO_DATACENTERS.get(self.datacenter, ZOHO_DATACENTERS["US"])
        self.oauth_service = ZohoOAuthService(tenant_id, datacenter)
    
    async def validate_connection(self, access_token: str) -> Dict[str, Any]:
        """Validate Zoho Mail connection by fetching accounts."""
        api_url = f"{self.dc_config['mail_url']}/api/accounts"
        
        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(api_url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    accounts = data.get("data", [])
                    return {
                        "success": True,
                        "message": "Connection validated successfully",
                        "accounts_count": len(accounts),
                        "accounts": [
                            {"email": acc.get("emailAddress"), "account_id": acc.get("accountId")}
                            for acc in accounts
                        ]
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Validation failed: {response.status_code}",
                        "error": response.text
                    }
        except Exception as e:
            logger.error(f"Zoho Mail validation error: {e}")
            return {"success": False, "message": str(e)}
    
    async def send_email(
        self,
        access_token: str,
        account_id: str,
        from_address: str,
        to_addresses: List[str],
        subject: str,
        content: str,
        content_type: str = "html"
    ) -> Dict[str, Any]:
        """Send an email via Zoho Mail API."""
        api_url = f"{self.dc_config['mail_url']}/api/accounts/{account_id}/messages"
        
        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "fromAddress": from_address,
            "toAddress": ",".join(to_addresses),
            "subject": subject,
            "content": content,
            "mailFormat": content_type
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(api_url, json=payload, headers=headers)
                
                if response.status_code in [200, 201]:
                    return {"success": True, "data": response.json()}
                else:
                    return {"success": False, "error": response.text}
        except Exception as e:
            logger.error(f"Zoho Mail send error: {e}")
            return {"success": False, "error": str(e)}


class ZohoCRMService:
    """Service for Zoho CRM integration with module/field discovery and mapping."""
    
    def __init__(self, tenant_id: str, datacenter: str = "US"):
        self.tenant_id = tenant_id
        self.datacenter = datacenter.upper()
        self.dc_config = ZOHO_DATACENTERS.get(self.datacenter, ZOHO_DATACENTERS["US"])
        self.oauth_service = ZohoOAuthService(tenant_id, datacenter)
    
    async def validate_connection(self, access_token: str) -> Dict[str, Any]:
        """Validate Zoho CRM connection by fetching modules."""
        api_url = f"{self.dc_config['crm_url']}/crm/v6/settings/modules"
        
        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(api_url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    modules = data.get("modules", [])
                    return {
                        "success": True,
                        "message": "Connection validated successfully",
                        "modules_count": len(modules),
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
                else:
                    return {
                        "success": False,
                        "message": f"Validation failed: {response.status_code}",
                        "error": response.text
                    }
        except Exception as e:
            logger.error(f"Zoho CRM validation error: {e}")
            return {"success": False, "message": str(e)}
    
    async def get_modules(self, access_token: str) -> Dict[str, Any]:
        """Fetch available CRM modules."""
        api_url = f"{self.dc_config['crm_url']}/crm/v6/settings/modules"
        
        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}"
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(api_url, headers=headers)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Zoho CRM get modules error: {e}")
            return {"error": str(e)}
    
    async def get_module_fields(self, access_token: str, module_api_name: str) -> Dict[str, Any]:
        """Fetch fields for a specific CRM module."""
        api_url = f"{self.dc_config['crm_url']}/crm/v6/settings/fields"
        
        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}"
        }
        
        params = {"module": module_api_name}
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(api_url, headers=headers, params=params)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Zoho CRM get fields error: {e}")
            return {"error": str(e)}
    
    async def create_record(
        self, 
        access_token: str, 
        module_api_name: str, 
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a record in Zoho CRM."""
        api_url = f"{self.dc_config['crm_url']}/crm/v6/{module_api_name}"
        
        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {"data": [data]}
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(api_url, json=payload, headers=headers)
                return {"status_code": response.status_code, "data": response.json()}
        except Exception as e:
            logger.error(f"Zoho CRM create record error: {e}")
            return {"error": str(e)}
    
    async def update_record(
        self, 
        access_token: str, 
        module_api_name: str, 
        record_id: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a record in Zoho CRM."""
        api_url = f"{self.dc_config['crm_url']}/crm/v6/{module_api_name}"
        
        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Content-Type": "application/json"
        }
        
        data["id"] = record_id
        payload = {"data": [data]}
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.put(api_url, json=payload, headers=headers)
                return {"status_code": response.status_code, "data": response.json()}
        except Exception as e:
            logger.error(f"Zoho CRM update record error: {e}")
            return {"error": str(e)}


async def get_crm_field_mappings(tenant_id: str) -> List[Dict[str, Any]]:
    """Get CRM field mappings for a tenant."""
    mappings = await db.crm_mappings.find(
        {"tenant_id": tenant_id},
        {"_id": 0}
    ).to_list(100)
    return mappings


async def save_crm_field_mapping(tenant_id: str, mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Save a CRM field mapping."""
    mapping["tenant_id"] = tenant_id
    mapping["updated_at"] = datetime.utcnow().isoformat()
    
    await db.crm_mappings.update_one(
        {
            "tenant_id": tenant_id,
            "webapp_module": mapping["webapp_module"],
            "crm_module": mapping["crm_module"]
        },
        {"$set": mapping},
        upsert=True
    )
    return {"success": True, "mapping": mapping}


async def delete_crm_field_mapping(tenant_id: str, mapping_id: str) -> Dict[str, Any]:
    """Delete a CRM field mapping."""
    result = await db.crm_mappings.delete_one(
        {"tenant_id": tenant_id, "id": mapping_id}
    )
    return {"success": result.deleted_count > 0}


# ---------------------------------------------------------------------------
# Auto-sync functionality for real-time Zoho CRM sync on record create/update
# ---------------------------------------------------------------------------

async def auto_sync_to_zoho_crm(
    tenant_id: str,
    webapp_module: str,
    record: Dict[str, Any],
    operation: str = "create"  # "create" or "update"
) -> Dict[str, Any]:
    """
    Automatically sync a single record to Zoho CRM based on active mappings.
    
    Args:
        tenant_id: The tenant ID
        webapp_module: The webapp module name (customers, orders, subscriptions, quote_requests)
        record: The record data to sync
        operation: "create" or "update"
    
    Returns:
        Dict with success status and any errors
    """
    try:
        # Find active mapping for this module
        mapping = await db.crm_mappings.find_one({
            "tenant_id": tenant_id,
            "webapp_module": webapp_module,
            "is_active": True,
            "$or": [{"provider": "zoho_crm"}, {"provider": {"$exists": False}}],
        }, {"_id": 0})
        
        if not mapping:
            # No active mapping for this module - skip silently
            return {"success": True, "skipped": True, "reason": "no_mapping"}
        
        # Check if sync is enabled for this operation
        if operation == "create" and not mapping.get("sync_on_create", True):
            return {"success": True, "skipped": True, "reason": "sync_on_create_disabled"}
        if operation == "update" and not mapping.get("sync_on_update", True):
            return {"success": True, "skipped": True, "reason": "sync_on_update_disabled"}
        
        crm_module = mapping.get("crm_module")
        field_maps = mapping.get("field_mappings", [])
        
        if not crm_module or not field_maps:
            return {"success": True, "skipped": True, "reason": "incomplete_mapping"}
        
        # Get Zoho connection credentials
        conn = await db.oauth_connections.find_one(
            {"tenant_id": tenant_id, "provider": "zoho_crm", "is_validated": True},
            {"_id": 0}
        )
        if not conn:
            logger.warning(f"Auto-sync skipped: No validated Zoho CRM connection for tenant {tenant_id}")
            return {"success": False, "error": "no_zoho_connection"}
        
        creds = conn.get("credentials", {})
        refresh_token = creds.get("refresh_token")
        client_id = creds.get("client_id")
        client_secret = creds.get("client_secret")
        api_domain = creds.get("_api_domain", "https://www.zohoapis.com")
        accounts_url = creds.get("_accounts_url", "https://accounts.zoho.com")
        
        if not all([refresh_token, client_id, client_secret]):
            return {"success": False, "error": "missing_credentials"}
        
        # Get access token
        async with httpx.AsyncClient(timeout=30.0) as client:
            token_resp = await client.post(
                f"{accounts_url}/oauth/v2/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            )
            if token_resp.status_code != 200:
                logger.error(f"Auto-sync token refresh failed: {token_resp.text}")
                return {"success": False, "error": "token_refresh_failed"}
            
            access_token = token_resp.json().get("access_token")
            if not access_token:
                return {"success": False, "error": "no_access_token"}
            
            # Enrich record if it's a customer (add email, full_name from user)
            enriched_record = dict(record)
            if webapp_module == "customers" and record.get("user_id"):
                user = await db.users.find_one(
                    {"id": record["user_id"]},
                    {"_id": 0, "email": 1, "full_name": 1}
                )
                if user:
                    enriched_record["email"] = user.get("email")
                    enriched_record["full_name"] = user.get("full_name")
            
            # Build Zoho record from field mappings
            zoho_record: Dict[str, Any] = {}
            for fm in field_maps:
                wf = fm.get("webapp_field")
                cf = fm.get("crm_field")
                if wf and cf:
                    val = enriched_record.get(wf)
                    if val is not None:
                        zoho_record[cf] = val if isinstance(val, (int, float, bool)) else str(val)
            
            if not zoho_record:
                return {"success": True, "skipped": True, "reason": "no_fields_to_sync"}
            
            # Send to Zoho CRM
            resp = await client.post(
                f"{api_domain}/crm/v3/{crm_module}",
                json={"data": [zoho_record]},
                headers={
                    "Authorization": f"Zoho-oauthtoken {access_token}",
                    "Content-Type": "application/json",
                },
            )
            
            if resp.status_code in [200, 201]:
                resp_data = resp.json().get("data", [])
                if resp_data and isinstance(resp_data[0], dict):
                    code = resp_data[0].get("code", "")
                    if code in ("SUCCESS", "RECORD_ADDED"):
                        zoho_id = resp_data[0].get("details", {}).get("id")
                        logger.info(f"Auto-sync success: {webapp_module} -> {crm_module}, Zoho ID: {zoho_id}")
                        await create_audit_log(
                            entity_type=webapp_module, entity_id=record.get("id", "unknown"),
                            action="zoho_crm_sync_success", actor="system",
                            details={"zoho_module": crm_module, "operation": operation, "zoho_id": zoho_id},
                            tenant_id=tenant_id,
                        )
                        return {"success": True, "zoho_id": zoho_id}
                    else:
                        error_msg = resp_data[0].get("message", str(resp_data[0]))
                        logger.warning(f"Auto-sync Zoho error: {error_msg}")
                        await create_audit_log(
                            entity_type=webapp_module, entity_id=record.get("id", "unknown"),
                            action="zoho_crm_sync_failed", actor="system",
                            details={"zoho_module": crm_module, "operation": operation, "error": error_msg},
                            tenant_id=tenant_id,
                        )
                        return {"success": False, "error": error_msg}
                return {"success": True}
            else:
                error_msg = resp.text[:200]
                logger.error(f"Auto-sync HTTP error {resp.status_code}: {error_msg}")
                await create_audit_log(
                    entity_type=webapp_module, entity_id=record.get("id", "unknown"),
                    action="zoho_crm_sync_failed", actor="system",
                    details={"zoho_module": crm_module, "operation": operation, "error": error_msg},
                    tenant_id=tenant_id,
                )
                return {"success": False, "error": f"HTTP {resp.status_code}: {error_msg}"}
                
    except Exception as e:
        logger.error(f"Auto-sync exception: {str(e)}")
        return {"success": False, "error": str(e)}


async def auto_sync_to_zoho_books(
    tenant_id: str,
    webapp_module: str,
    record: Dict[str, Any],
    operation: str = "create"
) -> Dict[str, Any]:
    """
    Automatically sync a single record to Zoho Books based on active mappings.
    """
    try:
        # Find active mapping for this module in Zoho Books
        mapping = await db.crm_mappings.find_one({
            "tenant_id": tenant_id,
            "webapp_module": webapp_module,
            "provider": "zoho_books",
            "is_active": True,
        }, {"_id": 0})
        
        if not mapping:
            return {"success": True, "skipped": True, "reason": "no_mapping"}
        
        if operation == "create" and not mapping.get("sync_on_create", True):
            return {"success": True, "skipped": True, "reason": "sync_on_create_disabled"}
        if operation == "update" and not mapping.get("sync_on_update", True):
            return {"success": True, "skipped": True, "reason": "sync_on_update_disabled"}
        
        books_module = mapping.get("crm_module")
        field_maps = mapping.get("field_mappings", [])
        
        if not books_module or not field_maps:
            return {"success": True, "skipped": True, "reason": "incomplete_mapping"}
        
        # Get Zoho Books connection credentials
        conn = await db.oauth_connections.find_one(
            {"tenant_id": tenant_id, "provider": "zoho_books", "is_validated": True},
            {"_id": 0}
        )
        if not conn:
            return {"success": False, "error": "no_zoho_books_connection"}
        
        creds = conn.get("credentials", {})
        refresh_token = creds.get("refresh_token")
        client_id = creds.get("client_id")
        client_secret = creds.get("client_secret")
        api_domain = creds.get("_api_domain", "https://www.zohoapis.com")
        accounts_url = creds.get("_accounts_url", "https://accounts.zoho.com")
        organization_id = creds.get("organization_id", "")
        
        if not all([refresh_token, client_id, client_secret]):
            return {"success": False, "error": "missing_credentials"}
        
        # Get access token
        async with httpx.AsyncClient(timeout=30.0) as client:
            token_resp = await client.post(
                f"{accounts_url}/oauth/v2/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            )
            if token_resp.status_code != 200:
                return {"success": False, "error": "token_refresh_failed"}
            
            access_token = token_resp.json().get("access_token")
            if not access_token:
                return {"success": False, "error": "no_access_token"}
            
            # Enrich record if it's a customer
            enriched_record = dict(record)
            if webapp_module == "customers" and record.get("user_id"):
                user = await db.users.find_one(
                    {"id": record["user_id"]},
                    {"_id": 0, "email": 1, "full_name": 1}
                )
                if user:
                    enriched_record["email"] = user.get("email")
                    enriched_record["full_name"] = user.get("full_name")
            
            # Build Zoho Books record from field mappings
            zoho_record: Dict[str, Any] = {}
            for fm in field_maps:
                wf = fm.get("webapp_field")
                cf = fm.get("crm_field")
                if wf and cf:
                    val = enriched_record.get(wf)
                    if val is not None:
                        zoho_record[cf] = val if isinstance(val, (int, float, bool)) else str(val)
            
            if not zoho_record:
                return {"success": True, "skipped": True, "reason": "no_fields_to_sync"}
            
            # Books module to endpoint map
            endpoint_map = {
                "contacts": "contacts",
                "invoices": "invoices",
                "estimates": "estimates",
                "bills": "bills",
                "recurringinvoices": "recurringinvoices",
            }
            endpoint = endpoint_map.get(books_module, books_module)
            
            # Send to Zoho Books
            params = {"organization_id": organization_id} if organization_id else {}
            resp = await client.post(
                f"{api_domain}/books/v3/{endpoint}",
                json=zoho_record,
                params=params,
                headers={
                    "Authorization": f"Zoho-oauthtoken {access_token}",
                    "Content-Type": "application/json",
                },
            )
            
            if resp.status_code in [200, 201]:
                resp_data = resp.json()
                if resp_data.get("code") == 0:  # Zoho Books uses code 0 for success
                    entity_key = endpoint.rstrip('s')  # contacts -> contact
                    zoho_id = resp_data.get(entity_key, {}).get("contact_id") or resp_data.get(entity_key, {}).get("invoice_id")
                    logger.info(f"Auto-sync Zoho Books success: {webapp_module} -> {books_module}, ID: {zoho_id}")
                    await create_audit_log(
                        entity_type=webapp_module, entity_id=record.get("id", "unknown"),
                        action="zoho_books_sync_success", actor="system",
                        details={"books_module": books_module, "operation": operation, "zoho_id": zoho_id},
                        tenant_id=tenant_id,
                    )
                    return {"success": True, "zoho_id": zoho_id}
                else:
                    error_msg = resp_data.get("message", str(resp_data))
                    logger.warning(f"Auto-sync Zoho Books error: {error_msg}")
                    await create_audit_log(
                        entity_type=webapp_module, entity_id=record.get("id", "unknown"),
                        action="zoho_books_sync_failed", actor="system",
                        details={"books_module": books_module, "operation": operation, "error": error_msg},
                        tenant_id=tenant_id,
                    )
                    return {"success": False, "error": error_msg}
            else:
                error_msg = resp.text[:200]
                logger.error(f"Auto-sync Zoho Books HTTP error {resp.status_code}: {error_msg}")
                await create_audit_log(
                    entity_type=webapp_module, entity_id=record.get("id", "unknown"),
                    action="zoho_books_sync_failed", actor="system",
                    details={"books_module": books_module, "operation": operation, "error": error_msg},
                    tenant_id=tenant_id,
                )
                return {"success": False, "error": f"HTTP {resp.status_code}: {error_msg}"}
                
    except Exception as e:
        logger.error(f"Auto-sync Zoho Books exception: {str(e)}")
        return {"success": False, "error": str(e)}
