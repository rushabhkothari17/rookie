"""Admin routes for Finance integrations (Zoho Books, QuickBooks)."""
from __future__ import annotations

from typing import Any, Dict, Optional, List
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.helpers import make_id, now_iso
from core.tenant import get_tenant_admin, get_tenant_filter, tenant_id_of
from db.session import db
from services.audit_service import create_audit_log

router = APIRouter(prefix="/api", tags=["admin-finance"])


# ---------------------------------------------------------------------------
# Zoho Books Integration
# ---------------------------------------------------------------------------

class ZohoBooksCredentials(BaseModel):
    client_id: str
    client_secret: str
    datacenter: str = "US"  # US, EU, IN, AU


class ZohoBooksValidation(BaseModel):
    access_token: str
    datacenter: str = "US"


class ZohoBooksAccountMapping(BaseModel):
    webapp_entity: str  # "invoice", "payment", "customer", "product"
    zoho_module: str   # "invoices", "customerpayments", "contacts", "items"
    field_mappings: List[Dict[str, str]]
    sync_enabled: bool = True


@router.get("/admin/finance/status")
async def get_finance_status(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Get status of all finance integrations."""
    tid = tenant_id_of(admin)
    
    # Check Zoho Books status
    zoho_books_creds = await db.integrations.find_one(
        {"tenant_id": tid, "provider": "zoho_books"},
        {"_id": 0}
    )
    
    zoho_books_status = {
        "is_configured": bool(zoho_books_creds and zoho_books_creds.get("client_id")),
        "is_validated": bool(zoho_books_creds and zoho_books_creds.get("is_validated")),
        "datacenter": zoho_books_creds.get("datacenter") if zoho_books_creds else None,
        "organization_id": zoho_books_creds.get("organization_id") if zoho_books_creds else None,
        "validated_at": zoho_books_creds.get("validated_at") if zoho_books_creds else None
    }
    
    return {
        "zoho_books": zoho_books_status,
        "quickbooks": {
            "is_configured": False,
            "is_validated": False,
            "status": "coming_soon"
        }
    }


@router.post("/admin/finance/zoho-books/save-credentials")
async def save_zoho_books_credentials(
    payload: ZohoBooksCredentials,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Save Zoho Books OAuth credentials."""
    tid = tenant_id_of(admin)
    
    await db.integrations.update_one(
        {"tenant_id": tid, "provider": "zoho_books"},
        {"$set": {
            "tenant_id": tid,
            "provider": "zoho_books",
            "client_id": payload.client_id,
            "client_secret": payload.client_secret,
            "datacenter": payload.datacenter,
            "updated_at": now_iso()
        }},
        upsert=True
    )
    
    await create_audit_log(
        entity_type="integration",
        entity_id="zoho_books",
        action="credentials_saved",
        actor=f"admin:{admin['id']}",
        details={"datacenter": payload.datacenter}
    )
    
    return {"success": True, "message": "Zoho Books credentials saved"}


@router.post("/admin/finance/zoho-books/validate")
async def validate_zoho_books(
    payload: ZohoBooksValidation,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Validate Zoho Books connection and fetch organization info."""
    import httpx
    
    tid = tenant_id_of(admin)
    
    # Determine API URL based on datacenter
    dc_urls = {
        "US": "https://books.zoho.com",
        "EU": "https://books.zoho.eu",
        "IN": "https://books.zoho.in",
        "AU": "https://books.zoho.com.au",
        "CA": "https://books.zohocloud.ca"
    }
    api_url = dc_urls.get(payload.datacenter, dc_urls["US"])
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Get organizations
            resp = await client.get(
                f"{api_url}/api/v3/organizations",
                headers={"Authorization": f"Zoho-oauthtoken {payload.access_token}"}
            )
            
            if resp.status_code != 200:
                return {
                    "success": False,
                    "message": f"Zoho Books API error: {resp.status_code}",
                    "details": resp.text[:200]
                }
            
            data = resp.json()
            organizations = data.get("organizations", [])
            
            if not organizations:
                return {
                    "success": False,
                    "message": "No Zoho Books organizations found for this account"
                }
            
            # Use first organization (most accounts have one)
            org = organizations[0]
            
            # Save validation status
            await db.integrations.update_one(
                {"tenant_id": tid, "provider": "zoho_books"},
                {"$set": {
                    "is_validated": True,
                    "validated_at": now_iso(),
                    "access_token": payload.access_token,
                    "organization_id": org.get("organization_id"),
                    "organization_name": org.get("name"),
                    "datacenter": payload.datacenter
                }}
            )
            
            await create_audit_log(
                entity_type="integration",
                entity_id="zoho_books",
                action="connection_validated",
                actor=f"admin:{admin['id']}",
                details={"organization": org.get("name")}
            )
            
            return {
                "success": True,
                "message": "Zoho Books connection validated",
                "organization": {
                    "id": org.get("organization_id"),
                    "name": org.get("name"),
                    "country": org.get("country"),
                    "currency_code": org.get("currency_code")
                },
                "organizations_count": len(organizations)
            }
            
    except httpx.TimeoutException:
        return {"success": False, "message": "Connection timeout - please try again"}
    except Exception as e:
        return {"success": False, "message": f"Connection error: {str(e)[:100]}"}


@router.post("/admin/finance/zoho-books/refresh")
async def refresh_zoho_books(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Refresh Zoho Books connection status."""
    tid = tenant_id_of(admin)
    
    creds = await db.integrations.find_one(
        {"tenant_id": tid, "provider": "zoho_books"},
        {"_id": 0}
    )
    
    if not creds or not creds.get("access_token"):
        return {"success": False, "message": "No access token configured"}
    
    # Re-validate using stored token
    return await validate_zoho_books(
        ZohoBooksValidation(
            access_token=creds["access_token"],
            datacenter=creds.get("datacenter", "US")
        ),
        admin
    )


@router.get("/admin/finance/zoho-books/account-mappings")
async def get_zoho_books_mappings(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Get configured account mappings for Zoho Books sync."""
    tid = tenant_id_of(admin)
    
    mappings = await db.finance_mappings.find(
        {"tenant_id": tid, "provider": "zoho_books"},
        {"_id": 0}
    ).to_list(50)
    
    # Define available webapp entities
    webapp_entities = [
        {"name": "invoice", "label": "Invoices", "fields": ["invoice_number", "customer_id", "amount", "due_date", "status"]},
        {"name": "payment", "label": "Payments", "fields": ["payment_id", "invoice_id", "amount", "payment_date", "method"]},
        {"name": "customer", "label": "Customers", "fields": ["customer_id", "name", "email", "company", "address"]},
        {"name": "product", "label": "Products", "fields": ["product_id", "name", "sku", "price", "description"]},
    ]
    
    return {
        "mappings": mappings,
        "webapp_entities": webapp_entities
    }


@router.post("/admin/finance/zoho-books/account-mappings")
async def create_zoho_books_mapping(
    payload: ZohoBooksAccountMapping,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Create or update an account mapping for Zoho Books."""
    tid = tenant_id_of(admin)
    
    mapping_id = make_id()
    
    # Check for existing mapping for this entity
    existing = await db.finance_mappings.find_one({
        "tenant_id": tid,
        "provider": "zoho_books",
        "webapp_entity": payload.webapp_entity
    })
    
    if existing:
        # Update existing
        await db.finance_mappings.update_one(
            {"id": existing["id"]},
            {"$set": {
                "zoho_module": payload.zoho_module,
                "field_mappings": payload.field_mappings,
                "sync_enabled": payload.sync_enabled,
                "updated_at": now_iso()
            }}
        )
        await create_audit_log(entity_type="finance_mapping", entity_id=existing["id"], action="updated", actor=admin.get("email", "admin"), details={"provider": "zoho_books", "webapp_entity": payload.webapp_entity})
        return {"success": True, "mapping_id": existing["id"], "updated": True}
    
    # Create new
    doc = {
        "id": mapping_id,
        "tenant_id": tid,
        "provider": "zoho_books",
        "webapp_entity": payload.webapp_entity,
        "zoho_module": payload.zoho_module,
        "field_mappings": payload.field_mappings,
        "sync_enabled": payload.sync_enabled,
        "created_at": now_iso()
    }
    await db.finance_mappings.insert_one(doc)
    
    await create_audit_log(entity_type="finance_mapping", entity_id=mapping_id, action="created", actor=admin.get("email", "admin"), details={"provider": "zoho_books", "webapp_entity": payload.webapp_entity})
    return {"success": True, "mapping_id": mapping_id, "updated": False}


@router.delete("/admin/finance/zoho-books/account-mappings/{mapping_id}")
async def delete_zoho_books_mapping(
    mapping_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Delete an account mapping."""
    tid = tenant_id_of(admin)
    
    result = await db.finance_mappings.delete_one({
        "id": mapping_id,
        "tenant_id": tid,
        "provider": "zoho_books"
    })
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Mapping not found")
    
    await create_audit_log(entity_type="finance_mapping", entity_id=mapping_id, action="deleted", actor=admin.get("email", "admin"), details={"provider": "zoho_books"})
    return {"success": True, "message": "Mapping deleted"}


@router.post("/admin/finance/zoho-books/sync-now")
async def trigger_zoho_books_sync(
    entity: str = "all",
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Trigger a manual sync with Zoho Books."""
    tid = tenant_id_of(admin)
    
    # Check if validated
    creds = await db.integrations.find_one(
        {"tenant_id": tid, "provider": "zoho_books", "is_validated": True},
        {"_id": 0}
    )
    
    if not creds:
        raise HTTPException(
            status_code=400,
            detail="Zoho Books not configured or not validated"
        )
    
    # In production, this would queue a background sync job
    # For now, return a mock response
    sync_id = make_id()
    
    await db.sync_jobs.insert_one({
        "id": sync_id,
        "tenant_id": tid,
        "provider": "zoho_books",
        "entity": entity,
        "status": "queued",
        "triggered_by": f"admin:{admin['id']}",
        "created_at": now_iso()
    })
    
    await create_audit_log(
        entity_type="sync_job",
        entity_id=sync_id,
        action="triggered",
        actor=f"admin:{admin['id']}",
        details={"provider": "zoho_books", "entity": entity}
    )
    
    return {
        "success": True,
        "sync_id": sync_id,
        "message": f"Sync job queued for {entity}",
        "note": "Sync jobs run in the background. Check sync history for status."
    }


@router.get("/admin/finance/sync-history")
async def get_sync_history(
    limit: int = 20,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Get recent sync job history."""
    tid = tenant_id_of(admin)
    
    jobs = await db.sync_jobs.find(
        {"tenant_id": tid},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    return {"jobs": jobs}
