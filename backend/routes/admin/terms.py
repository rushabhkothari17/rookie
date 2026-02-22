"""Admin: Terms & Conditions management."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.helpers import make_id, now_iso
from core.security import require_admin, get_current_user
from db.session import db
from models import TermsCreate, TermsUpdate
from services.audit_service import create_audit_log
from services.checkout_service import resolve_terms_tags

router = APIRouter(prefix="/api", tags=["admin-terms"])


@router.get("/terms/default")
async def get_default_terms():
    default = await db.terms_and_conditions.find_one({"is_default": True, "status": "active"}, {"_id": 0})
    if not default:
        raise HTTPException(status_code=404, detail="No default terms found")
    return default


@router.get("/terms/for-product/{product_id}")
async def get_terms_for_product(product_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    terms_id = product.get("terms_id")
    if terms_id:
        terms = await db.terms_and_conditions.find_one({"id": terms_id, "status": "active"}, {"_id": 0})
    else:
        terms = await db.terms_and_conditions.find_one({"is_default": True, "status": "active"}, {"_id": 0})
    if not terms:
        raise HTTPException(status_code=404, detail="No terms found for this product")
    address = await db.addresses.find_one({"user_id": user["id"]}, {"_id": 0})
    resolved_content = resolve_terms_tags(terms["content"], user, address or {}, product["name"])
    return {"id": terms["id"], "title": terms["title"], "content": resolved_content, "raw_content": terms["content"]}


@router.get("/admin/terms")
async def admin_list_terms(
    page: int = 1,
    per_page: int = 20,
    search: Optional[str] = None,
    status: Optional[str] = None,
    created_from: Optional[str] = None,
    created_to: Optional[str] = None,
    admin: Dict[str, Any] = Depends(require_admin),
):
    query: Dict[str, Any] = {}
    if status:
        query["status"] = status
    if search:
        query["title"] = {"$regex": search, "$options": "i"}
    if created_from:
        query.setdefault("created_at", {})["$gte"] = created_from
    if created_to:
        query.setdefault("created_at", {})["$lte"] = created_to + "T23:59:59"
    total = await db.terms_and_conditions.count_documents(query)
    skip = (page - 1) * per_page
    terms = await db.terms_and_conditions.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(per_page).to_list(per_page)
    return {"terms": terms, "page": page, "per_page": per_page, "total": total, "total_pages": max(1, (total + per_page - 1) // per_page)}


@router.post("/admin/terms")
async def create_terms(payload: TermsCreate, admin: Dict[str, Any] = Depends(require_admin)):
    if payload.is_default:
        await db.terms_and_conditions.update_many({"is_default": True}, {"$set": {"is_default": False}})
    terms_id = make_id()
    await db.terms_and_conditions.insert_one({
        "id": terms_id, "title": payload.title, "content": payload.content,
        "is_default": payload.is_default, "status": payload.status, "created_at": now_iso(),
    })
    await create_audit_log(
        entity_type="terms",
        entity_id=terms_id,
        action="created",
        actor=f"admin:{admin.get('email', admin['id'])}",
        details={"title": payload.title, "is_default": payload.is_default, "status": payload.status},
    )
    return {"message": "Terms created", "id": terms_id}


@router.put("/admin/terms/{terms_id}")
async def update_terms(terms_id: str, payload: TermsUpdate, admin: Dict[str, Any] = Depends(require_admin)):
    existing = await db.terms_and_conditions.find_one({"id": terms_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Terms not found")
    update_data: Dict[str, Any] = {}
    if payload.title is not None:
        update_data["title"] = payload.title
    if payload.content is not None:
        update_data["content"] = payload.content
    if payload.status is not None:
        update_data["status"] = payload.status
    if update_data:
        await db.terms_and_conditions.update_one({"id": terms_id}, {"$set": update_data})
    await create_audit_log(
        entity_type="terms",
        entity_id=terms_id,
        action="updated",
        actor=f"admin:{admin.get('email', admin['id'])}",
        details={"changes": update_data},
    )
    return {"message": "Terms updated"}


@router.delete("/admin/terms/{terms_id}")
async def delete_terms(terms_id: str, admin: Dict[str, Any] = Depends(require_admin)):
    existing = await db.terms_and_conditions.find_one({"id": terms_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Terms not found")
    if existing.get("is_default"):
        raise HTTPException(status_code=400, detail="Cannot delete default terms")
    await db.terms_and_conditions.delete_one({"id": terms_id})
    await db.products.update_many({"terms_id": terms_id}, {"$unset": {"terms_id": ""}})
    await create_audit_log(
        entity_type="terms",
        entity_id=terms_id,
        action="deleted",
        actor=f"admin:{admin.get('email', admin['id'])}",
        details={"title": existing.get("title")},
    )
    return {"message": "Terms deleted"}


@router.put("/admin/products/{product_id}/terms")
async def assign_terms_to_product(
    product_id: str,
    terms_id: Optional[str] = None,
    admin: Dict[str, Any] = Depends(require_admin),
):
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if terms_id:
        terms = await db.terms_and_conditions.find_one({"id": terms_id}, {"_id": 0})
        if not terms:
            raise HTTPException(status_code=404, detail="Terms not found")
        await db.products.update_one({"id": product_id}, {"$set": {"terms_id": terms_id}})
        await create_audit_log(entity_type="product", entity_id=product_id, action="terms_assigned", actor=admin["email"], details={"terms_id": terms_id, "terms_title": terms.get("title")})
    else:
        await db.products.update_one({"id": product_id}, {"$unset": {"terms_id": ""}})
        await create_audit_log(entity_type="product", entity_id=product_id, action="terms_removed", actor=admin["email"], details={})
    return {"message": "Terms assignment updated"}
