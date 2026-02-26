"""Document management API — WorkDrive-backed file storage per customer."""
from __future__ import annotations
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import Response

from db.session import db
from core.helpers import make_id, now_iso
from core.auth import get_current_user, require_admin
from core.helpers import tenant_id_of
from services import workdrive_service as wd

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["documents"])

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


# ── helpers ─────────────────────────────────────────────────────────────────

async def _tenant_id_for_customer(customer_id: str) -> str:
    c = await db.customers.find_one({"id": customer_id}, {"_id": 0, "tenant_id": 1})
    return c["tenant_id"] if c else ""


async def _workdrive_folder_id(tenant_id: str, customer_id: str) -> str:
    """Return the stored WorkDrive folder_id for a customer, or ""."""
    doc = await db.workdrive_folders.find_one(
        {"tenant_id": tenant_id, "customer_id": customer_id},
        {"_id": 0, "folder_id": 1},
    )
    return doc["folder_id"] if doc else ""


async def _ensure_folder(tenant_id: str, customer_id: str) -> str:
    """Ensure customer has a WorkDrive folder; create if missing. Returns folder_id."""
    folder_id = await _workdrive_folder_id(tenant_id, customer_id)
    if folder_id:
        return folder_id

    # Get parent folder from integration settings
    integration = await db.integrations.find_one(
        {"tenant_id": tenant_id, "service": "zoho_workdrive"}, {"_id": 0}
    )
    if not integration or not integration.get("is_validated"):
        raise HTTPException(status_code=400, detail="WorkDrive is not connected for this partner")

    parent_folder_url = integration.get("parent_folder_url", "")
    parent_folder_id = wd.extract_folder_id_from_url(parent_folder_url)
    if not parent_folder_id:
        raise HTTPException(status_code=400, detail="Parent folder URL is not configured. Set it in Connected Services → WorkDrive.")

    # Get customer name
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    user = await db.users.find_one({"id": customer["user_id"]}, {"_id": 0, "full_name": 1}) if customer else None
    customer_name = user.get("full_name", "Customer") if user else "Customer"
    folder_name = f"{customer_name} - {customer_id}"

    result = await wd.create_folder(tenant_id, parent_folder_id, folder_name)
    new_folder_id = result["folder_id"]

    await db.workdrive_folders.insert_one({
        "id": make_id(),
        "tenant_id": tenant_id,
        "customer_id": customer_id,
        "folder_id": new_folder_id,
        "folder_name": folder_name,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    })
    return new_folder_id


# ── List documents ───────────────────────────────────────────────────────────

@router.get("/documents")
async def list_documents(
    customer_id: str = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Admin: returns all documents for the tenant (or filtered by customer_id).
    Customer: returns their own documents only.
    """
    tid = tenant_id_of(current_user)
    role = current_user.get("role", "")
    is_admin = role in ("admin", "platform_admin", "partner_admin", "partner_super_admin", "partner_staff")

    if not is_admin:
        # Customer — find their customer record
        customer = await db.customers.find_one({"user_id": current_user["id"]}, {"_id": 0})
        if not customer:
            return {"documents": []}
        cid = customer["id"]
        query = {"tenant_id": tid, "customer_id": cid}
    else:
        query: Dict[str, Any] = {"tenant_id": tid}
        if customer_id:
            query["customer_id"] = customer_id

    docs = await db.workdrive_documents.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)

    # Enrich with customer name
    customer_ids = list({d["customer_id"] for d in docs})
    customer_map: Dict[str, str] = {}
    for cid in customer_ids:
        cust = await db.customers.find_one({"id": cid}, {"_id": 0, "user_id": 1})
        if cust:
            u = await db.users.find_one({"id": cust["user_id"]}, {"_id": 0, "full_name": 1})
            customer_map[cid] = u.get("full_name", "") if u else ""

    for d in docs:
        d["customer_name"] = customer_map.get(d["customer_id"], "")

    return {"documents": docs}


# ── Upload document ──────────────────────────────────────────────────────────

@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    customer_id: str = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Upload a document (max 5 MB) to the customer's WorkDrive folder."""
    tid = tenant_id_of(current_user)
    role = current_user.get("role", "")
    is_admin = role in ("admin", "platform_admin", "partner_admin", "partner_super_admin", "partner_staff")

    if not is_admin:
        # Customer uploads to their own folder
        cust = await db.customers.find_one({"user_id": current_user["id"]}, {"_id": 0})
        if not cust:
            raise HTTPException(status_code=404, detail="Customer record not found")
        cid = cust["id"]
        uploaded_by_label = "customer"
        uploaded_by_id = current_user["id"]
    else:
        if not customer_id:
            raise HTTPException(status_code=400, detail="customer_id is required for admin uploads")
        cid = customer_id
        uploaded_by_label = "admin"
        uploaded_by_id = current_user["id"]

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"File exceeds 5 MB limit ({len(content)/1024/1024:.1f} MB)")

    folder_id = await _ensure_folder(tid, cid)

    result = await wd.upload_file(tid, folder_id, file.filename, content, file.content_type or "application/octet-stream")

    doc_id = make_id()
    doc = {
        "id": doc_id,
        "tenant_id": tid,
        "customer_id": cid,
        "workdrive_file_id": result["workdrive_file_id"],
        "folder_id": folder_id,
        "file_name": file.filename,
        "file_size": len(content),
        "mime_type": file.content_type or "application/octet-stream",
        "uploaded_by": uploaded_by_label,
        "uploaded_by_id": uploaded_by_id,
        "notes": "",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.workdrive_documents.insert_one(doc)
    doc.pop("_id", None)
    return {"document": doc}


# ── Download document ─────────────────────────────────────────────────────────

@router.get("/documents/{doc_id}/download")
async def download_document(
    doc_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Proxy-download a document from WorkDrive (auth required)."""
    tid = tenant_id_of(current_user)
    doc = await db.workdrive_documents.find_one({"id": doc_id, "tenant_id": tid}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    role = current_user.get("role", "")
    is_admin = role in ("admin", "platform_admin", "partner_admin", "partner_super_admin", "partner_staff")
    if not is_admin:
        cust = await db.customers.find_one({"user_id": current_user["id"]}, {"_id": 0})
        if not cust or cust["id"] != doc["customer_id"]:
            raise HTTPException(status_code=403, detail="Access denied")

    content, filename = await wd.download_file(tid, doc["workdrive_file_id"])
    return Response(
        content=content,
        media_type=doc.get("mime_type", "application/octet-stream"),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Update document notes (admin only) ────────────────────────────────────────

@router.put("/admin/documents/{doc_id}")
async def update_document(
    doc_id: str,
    payload: Dict[str, Any],
    admin: Dict[str, Any] = Depends(require_admin),
):
    """Edit a document's notes (admin only)."""
    tid = tenant_id_of(admin)
    doc = await db.workdrive_documents.find_one({"id": doc_id, "tenant_id": tid}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    update: Dict[str, Any] = {"updated_at": now_iso()}
    if "notes" in payload:
        update["notes"] = str(payload["notes"])
    if "file_name" in payload:
        update["file_name"] = str(payload["file_name"])

    await db.workdrive_documents.update_one({"id": doc_id}, {"$set": update})
    updated = await db.workdrive_documents.find_one({"id": doc_id}, {"_id": 0})
    return {"document": updated}


# ── Delete document (admin only) ─────────────────────────────────────────────

@router.delete("/admin/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    admin: Dict[str, Any] = Depends(require_admin),
):
    """Delete a document from WorkDrive and the DB (admin only)."""
    tid = tenant_id_of(admin)
    doc = await db.workdrive_documents.find_one({"id": doc_id, "tenant_id": tid}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        await wd.delete_file(tid, doc["workdrive_file_id"])
    except Exception as exc:
        logger.warning("WorkDrive delete failed (removing from DB anyway): %s", exc)

    await db.workdrive_documents.delete_one({"id": doc_id})
    return {"message": "Document deleted"}


# ── Initial sync: create folders for all existing customers ───────────────────

@router.post("/admin/workdrive/sync-folders")
async def sync_customer_folders(admin: Dict[str, Any] = Depends(require_admin)):
    """Create WorkDrive folders for all existing customers that don't have one yet."""
    tid = tenant_id_of(admin)
    integration = await db.integrations.find_one(
        {"tenant_id": tid, "service": "zoho_workdrive"}, {"_id": 0}
    )
    if not integration or not integration.get("is_validated"):
        raise HTTPException(status_code=400, detail="WorkDrive is not connected")

    parent_folder_url = integration.get("parent_folder_url", "")
    parent_folder_id = wd.extract_folder_id_from_url(parent_folder_url)
    if not parent_folder_id:
        raise HTTPException(status_code=400, detail="Parent folder URL not configured")

    customers = await db.customers.find({"tenant_id": tid}, {"_id": 0}).to_list(5000)
    created = 0
    skipped = 0
    errors: List[str] = []

    for cust in customers:
        cid = cust["id"]
        existing = await db.workdrive_folders.find_one(
            {"tenant_id": tid, "customer_id": cid}, {"_id": 0, "id": 1}
        )
        if existing:
            skipped += 1
            continue
        try:
            user = await db.users.find_one({"id": cust.get("user_id", "")}, {"_id": 0, "full_name": 1})
            customer_name = user.get("full_name", "Customer") if user else "Customer"
            folder_name = f"{customer_name} - {cid}"
            result = await wd.create_folder(tid, parent_folder_id, folder_name)
            await db.workdrive_folders.insert_one({
                "id": make_id(),
                "tenant_id": tid,
                "customer_id": cid,
                "folder_id": result["folder_id"],
                "folder_name": folder_name,
                "created_at": now_iso(),
                "updated_at": now_iso(),
            })
            created += 1
        except Exception as exc:
            errors.append(f"customer {cid}: {str(exc)[:100]}")

    return {
        "created": created,
        "skipped": skipped,
        "errors": errors,
        "total": len(customers),
    }


# ── Document audit logs ───────────────────────────────────────────────────────

@router.get("/admin/documents/{doc_id}/logs")
async def get_document_logs(
    doc_id: str,
    admin: Dict[str, Any] = Depends(require_admin),
):
    """Return audit log entries for a document."""
    tid = tenant_id_of(admin)
    logs = await db.audit_logs.find(
        {"entity_type": "document", "entity_id": doc_id},
        {"_id": 0},
    ).sort("created_at", -1).to_list(100)
    return {"logs": logs}
