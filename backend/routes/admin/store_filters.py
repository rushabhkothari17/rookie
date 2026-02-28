"""Store filters admin CRUD — partners configure customer-facing filters."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.helpers import make_id, now_iso
from core.tenant import get_tenant_admin, get_tenant_filter, tenant_id_of
from db.session import db
from services.audit_service import create_audit_log

router = APIRouter(prefix="/api", tags=["store-filters"])

FILTER_TYPES = {"category", "tag", "price_range", "custom"}


class FilterOption(BaseModel):
    label: str
    value: str


class StoreFilterCreate(BaseModel):
    name: str
    filter_type: str  # category | tag | price_range | custom
    options: Optional[List[FilterOption]] = None  # For price_range: [{label:"Under £50", value:"0-50"}]
    is_active: bool = True
    sort_order: int = 0
    show_count: bool = True  # Show product count next to option


class StoreFilterUpdate(BaseModel):
    name: Optional[str] = None
    filter_type: Optional[str] = None
    options: Optional[List[FilterOption]] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None
    show_count: Optional[bool] = None


@router.get("/admin/store-filters")
async def list_store_filters(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    filters = await db.store_filters.find(tf, {"_id": 0}).sort("sort_order", 1).to_list(100)
    return {"filters": filters, "total": len(filters)}


@router.post("/admin/store-filters")
async def create_store_filter(
    payload: StoreFilterCreate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    if payload.filter_type not in FILTER_TYPES:
        raise HTTPException(status_code=400, detail=f"filter_type must be one of: {', '.join(FILTER_TYPES)}")

    tid = tenant_id_of(admin)
    filter_id = make_id()
    doc = {
        "id": filter_id,
        "tenant_id": tid,
        "name": payload.name.strip(),
        "filter_type": payload.filter_type,
        "options": [o.dict() for o in (payload.options or [])],
        "is_active": payload.is_active,
        "sort_order": payload.sort_order,
        "show_count": payload.show_count,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "created_by": admin.get("email", "admin"),
    }
    await db.store_filters.insert_one({**doc})
    await create_audit_log(
        entity_type="store_filter", entity_id=filter_id, action="created",
        actor=admin.get("email", "admin"),
        details={"name": doc["name"], "type": doc["filter_type"]},
    )
    return {"filter": doc}


@router.put("/admin/store-filters/{filter_id}")
async def update_store_filter(
    filter_id: str,
    payload: StoreFilterUpdate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    existing = await db.store_filters.find_one({**tf, "id": filter_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Filter not found")

    updates: Dict[str, Any] = {"updated_at": now_iso()}
    if payload.name is not None:
        updates["name"] = payload.name.strip()
    if payload.filter_type is not None:
        if payload.filter_type not in FILTER_TYPES:
            raise HTTPException(status_code=400, detail=f"filter_type must be one of: {', '.join(FILTER_TYPES)}")
        updates["filter_type"] = payload.filter_type
    if payload.options is not None:
        updates["options"] = [o.dict() for o in payload.options]
    if payload.is_active is not None:
        updates["is_active"] = payload.is_active
    if payload.sort_order is not None:
        updates["sort_order"] = payload.sort_order
    if payload.show_count is not None:
        updates["show_count"] = payload.show_count

    await db.store_filters.update_one({"id": filter_id}, {"$set": updates})
    await create_audit_log(
        entity_type="store_filter", entity_id=filter_id, action="updated",
        actor=admin.get("email", "admin"), details=updates,
    )
    updated = await db.store_filters.find_one({"id": filter_id}, {"_id": 0})
    return {"filter": updated}


@router.delete("/admin/store-filters/{filter_id}")
async def delete_store_filter(
    filter_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    existing = await db.store_filters.find_one({**tf, "id": filter_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Filter not found")
    await db.store_filters.delete_one({"id": filter_id})
    await create_audit_log(
        entity_type="store_filter", entity_id=filter_id, action="deleted",
        actor=admin.get("email", "admin"), details={"name": existing.get("name")},
    )
    return {"message": "Filter deleted"}


@router.patch("/admin/store-filters/reorder")
async def reorder_store_filters(
    payload: List[Dict[str, Any]],
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """Bulk update sort_order. Payload: [{id: ..., sort_order: ...}, ...]"""
    tf = get_tenant_filter(admin)
    for item in payload:
        if "id" in item and "sort_order" in item:
            await db.store_filters.update_one(
                {**tf, "id": item["id"]},
                {"$set": {"sort_order": item["sort_order"], "updated_at": now_iso()}},
            )
    return {"message": "Reordered"}


# ── Public endpoint ──────────────────────────────────────────────────────────

@router.get("/store/filters")
async def public_store_filters(tenant_code: Optional[str] = None):
    """Public endpoint: returns active filters for the storefront.
    Optionally filtered by tenant_code (resolved via partner code).
    """
    query: Dict[str, Any] = {"is_active": True}
    if tenant_code:
        tenant = await db.tenants.find_one({"code": tenant_code.lower()}, {"_id": 0, "id": 1})
        if tenant:
            query["tenant_id"] = tenant["id"]

    filters = await db.store_filters.find(query, {"_id": 0}).sort("sort_order", 1).to_list(50)
    return {"filters": filters}
