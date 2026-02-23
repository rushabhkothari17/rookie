"""Zoho Mail and CRM integration services with multi-datacenter support."""
import httpx
import hashlib
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from db.session import db

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
