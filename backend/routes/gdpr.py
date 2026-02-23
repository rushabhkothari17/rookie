"""GDPR compliance routes for customer data export and deletion."""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import Dict, Any
from pydantic import BaseModel
from core.security import get_current_user
from core.tenant import get_tenant_admin, tenant_id_of
from services.gdpr_service import (
    export_customer_data,
    generate_export_zip,
    request_data_deletion,
    get_gdpr_requests
)
from services.audit_service import create_audit_log
from db.session import db
import io

router = APIRouter(prefix="/api", tags=["gdpr"])


class DeletionRequest(BaseModel):
    reason: str = ""
    confirm: bool = False


# === Customer-facing GDPR endpoints ===

@router.get("/me/data-export")
async def customer_export_data(user: Dict[str, Any] = Depends(get_current_user)):
    """
    Export all customer data (GDPR Article 20 - Right to data portability).
    Returns a JSON with all data associated with the customer.
    """
    if user.get("role") != "customer":
        raise HTTPException(status_code=403, detail="Only customers can export their own data")
    
    customer_id = user.get("customer_id")
    tenant_id = user.get("tenant_id")
    
    if not customer_id:
        # Look up customer by user_id
        customer = await db.customers.find_one(
            {"user_id": user["id"], "tenant_id": tenant_id},
            {"_id": 0, "id": 1}
        )
        if not customer:
            raise HTTPException(status_code=404, detail="Customer record not found")
        customer_id = customer["id"]
    
    export_data = await export_customer_data(customer_id, tenant_id)
    
    await create_audit_log(
        entity_type="gdpr",
        entity_id=customer_id,
        action="data_export_requested",
        actor=f"customer:{customer_id}",
        details={"format": "json"}
    )
    
    return export_data


@router.get("/me/data-export/download")
async def customer_download_data(user: Dict[str, Any] = Depends(get_current_user)):
    """
    Download all customer data as a ZIP file.
    Contains JSON, CSV, and readable text formats.
    """
    if user.get("role") != "customer":
        raise HTTPException(status_code=403, detail="Only customers can export their own data")
    
    customer_id = user.get("customer_id")
    tenant_id = user.get("tenant_id")
    
    if not customer_id:
        customer = await db.customers.find_one(
            {"user_id": user["id"], "tenant_id": tenant_id},
            {"_id": 0, "id": 1}
        )
        if not customer:
            raise HTTPException(status_code=404, detail="Customer record not found")
        customer_id = customer["id"]
    
    export_data = await export_customer_data(customer_id, tenant_id)
    zip_content = generate_export_zip(export_data)
    
    await create_audit_log(
        entity_type="gdpr",
        entity_id=customer_id,
        action="data_export_downloaded",
        actor=f"customer:{customer_id}",
        details={"format": "zip"}
    )
    
    return StreamingResponse(
        io.BytesIO(zip_content),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=my_data_export_{customer_id[:8]}.zip"
        }
    )


@router.post("/me/request-deletion")
async def customer_request_deletion(
    request: DeletionRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Request deletion of all customer data (GDPR Article 17 - Right to erasure).
    This anonymizes the data to maintain business records integrity.
    """
    if user.get("role") != "customer":
        raise HTTPException(status_code=403, detail="Only customers can request their own data deletion")
    
    if not request.confirm:
        raise HTTPException(
            status_code=400, 
            detail="You must confirm the deletion request by setting confirm=true"
        )
    
    customer_id = user.get("customer_id")
    tenant_id = user.get("tenant_id")
    
    if not customer_id:
        customer = await db.customers.find_one(
            {"user_id": user["id"], "tenant_id": tenant_id},
            {"_id": 0, "id": 1}
        )
        if not customer:
            raise HTTPException(status_code=404, detail="Customer record not found")
        customer_id = customer["id"]
    
    # Check for active subscriptions
    active_subs = await db.subscriptions.count_documents({
        "customer_id": customer_id,
        "tenant_id": tenant_id,
        "status": {"$in": ["active", "trialing"]}
    })
    
    if active_subs > 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete account with active subscriptions. Please cancel all subscriptions first."
        )
    
    result = await request_data_deletion(customer_id, tenant_id, request.reason)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Deletion failed"))
    
    return {
        "success": True,
        "message": "Your data has been anonymized. You will be logged out.",
        "completed_at": result["completed_at"]
    }


# === Admin GDPR management endpoints ===

@router.get("/admin/gdpr/requests")
async def admin_get_gdpr_requests(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Get all GDPR requests for compliance tracking."""
    tid = tenant_id_of(admin)
    requests = await get_gdpr_requests(tid)
    return {"requests": requests}


@router.get("/admin/gdpr/export/{customer_id}")
async def admin_export_customer_data(
    customer_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Admin: Export customer data for GDPR subject access request."""
    tid = tenant_id_of(admin)
    
    # Verify customer belongs to tenant
    customer = await db.customers.find_one(
        {"id": customer_id, "tenant_id": tid},
        {"_id": 0}
    )
    
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    export_data = await export_customer_data(customer_id, tid)
    
    await create_audit_log(
        entity_type="gdpr",
        entity_id=customer_id,
        action="admin_data_export",
        actor=admin.get("email", "admin"),
        details={"customer_email": customer.get("email")}
    )
    
    return export_data


@router.get("/admin/gdpr/export/{customer_id}/download")
async def admin_download_customer_data(
    customer_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Admin: Download customer data as ZIP for GDPR subject access request."""
    tid = tenant_id_of(admin)
    
    customer = await db.customers.find_one(
        {"id": customer_id, "tenant_id": tid},
        {"_id": 0}
    )
    
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    export_data = await export_customer_data(customer_id, tid)
    zip_content = generate_export_zip(export_data)
    
    await create_audit_log(
        entity_type="gdpr",
        entity_id=customer_id,
        action="admin_data_export_download",
        actor=admin.get("email", "admin"),
        details={"customer_email": customer.get("email")}
    )
    
    return StreamingResponse(
        io.BytesIO(zip_content),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=customer_export_{customer_id[:8]}.zip"
        }
    )


@router.post("/admin/gdpr/delete/{customer_id}")
async def admin_delete_customer_data(
    customer_id: str,
    request: DeletionRequest,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Admin: Process GDPR deletion request on behalf of customer."""
    tid = tenant_id_of(admin)
    
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="Must confirm deletion by setting confirm=true"
        )
    
    customer = await db.customers.find_one(
        {"id": customer_id, "tenant_id": tid},
        {"_id": 0}
    )
    
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    result = await request_data_deletion(
        customer_id, 
        tid, 
        f"Admin request: {request.reason}"
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Deletion failed"))
    
    return result
