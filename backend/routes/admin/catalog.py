"""Admin: Catalog (products + categories) routes."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.helpers import make_id, now_iso
from core.security import require_admin
from db.session import db
from models import AdminProductCreate, AdminProductUpdate, CategoryCreate, CategoryUpdate
from services.audit_service import create_audit_log
from services.pricing_service import build_price_inputs

router = APIRouter(prefix="/api", tags=["admin-catalog"])


@router.get("/admin/products-all")
async def admin_list_all_products(
    page: int = 1,
    per_page: int = 20,
    search: Optional[str] = None,
    category: Optional[str] = None,
    billing: Optional[str] = None,
    pricing_type: Optional[str] = None,
    status: Optional[str] = None,
    admin: Dict[str, Any] = Depends(require_admin),
):
    query: Dict[str, Any] = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"sku": {"$regex": search, "$options": "i"}},
        ]
    if category:
        query["category"] = category
    if billing:
        query["billing_cycle"] = billing
    if pricing_type:
        query["pricing_type"] = pricing_type
    if status == "active":
        query["is_active"] = True
    elif status == "inactive":
        query["is_active"] = False

    total = await db.products.count_documents(query)
    skip = (page - 1) * per_page
    products = await db.products.find(query, {"_id": 0}).skip(skip).limit(per_page).to_list(per_page)
    return {
        "products": products,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": max(1, (total + per_page - 1) // per_page),
    }


@router.post("/admin/products")
async def admin_create_product(
    payload: AdminProductCreate,
    admin: Dict[str, Any] = Depends(require_admin),
):
    product_id = make_id()
    sku = f"CUSTOM-{product_id[:8].upper()}"
    product: Dict[str, Any] = {
        "id": product_id,
        "sku": sku,
        "name": payload.name,
        "short_description": payload.short_description,
        "tagline": payload.short_description,
        "description_long": payload.description_long,
        "bullets": payload.bullets,
        "tag": payload.tag,
        "category": payload.category,
        "outcome": payload.outcome,
        "automation_details": payload.automation_details,
        "support_details": payload.support_details,
        "inclusions": payload.inclusions,
        "exclusions": payload.exclusions,
        "requirements": payload.requirements,
        "next_steps": payload.next_steps,
        "faqs": payload.faqs,
        "terms_id": payload.terms_id,
        "base_price": payload.base_price,
        "is_subscription": payload.is_subscription,
        "stripe_price_id": payload.stripe_price_id,
        "pricing_complexity": payload.pricing_complexity,
        "is_active": payload.is_active,
        "visible_to_customers": payload.visible_to_customers,
        "pricing_type": "simple",
        "pricing_rules": {},
        "created_at": now_iso(),
        "is_custom": True,
    }
    product["price_inputs"] = build_price_inputs(product)
    await db.products.insert_one(product)
    product.pop("_id", None)
    return {"product": product}


@router.put("/admin/products/{product_id}")
async def admin_update_product(
    product_id: str,
    payload: AdminProductUpdate,
    admin: Dict[str, Any] = Depends(require_admin),
):
    existing = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Product not found")

    update_fields: Dict[str, Any] = {
        "name": payload.name,
        "is_active": payload.is_active,
    }
    if payload.short_description is not None:
        update_fields["short_description"] = payload.short_description
        update_fields["tagline"] = payload.short_description
    if payload.tagline is not None and not payload.short_description:
        update_fields["tagline"] = payload.tagline
    if payload.description_long is not None:
        update_fields["description_long"] = payload.description_long
    if payload.bullets is not None:
        update_fields["bullets"] = payload.bullets
    if payload.bullets_included is not None:
        update_fields["bullets_included"] = payload.bullets_included
    if payload.bullets_excluded is not None:
        update_fields["bullets_excluded"] = payload.bullets_excluded
    if payload.bullets_needed is not None:
        update_fields["bullets_needed"] = payload.bullets_needed
    if payload.tag is not None:
        update_fields["tag"] = payload.tag
    if payload.category is not None:
        update_fields["category"] = payload.category
    if payload.outcome is not None:
        update_fields["outcome"] = payload.outcome
    if payload.automation_details is not None:
        update_fields["automation_details"] = payload.automation_details
    if payload.support_details is not None:
        update_fields["support_details"] = payload.support_details
    if payload.inclusions is not None:
        update_fields["inclusions"] = payload.inclusions
    if payload.exclusions is not None:
        update_fields["exclusions"] = payload.exclusions
    if payload.requirements is not None:
        update_fields["requirements"] = payload.requirements
    if payload.next_steps is not None:
        update_fields["next_steps"] = payload.next_steps
    if payload.faqs is not None:
        update_fields["faqs"] = payload.faqs
    if payload.terms_id is not None:
        update_fields["terms_id"] = payload.terms_id
    if payload.base_price is not None:
        update_fields["base_price"] = payload.base_price
    if payload.is_subscription is not None:
        update_fields["is_subscription"] = payload.is_subscription
    if payload.stripe_price_id is not None:
        update_fields["stripe_price_id"] = payload.stripe_price_id
    if payload.pricing_complexity is not None:
        update_fields["pricing_complexity"] = payload.pricing_complexity
    if payload.pricing_rules is not None:
        update_fields["pricing_rules"] = payload.pricing_rules
    if payload.visible_to_customers is not None:
        update_fields["visible_to_customers"] = payload.visible_to_customers

    merged = {**existing, **update_fields}
    merged["price_inputs"] = build_price_inputs(merged)
    await db.products.update_one({"id": product_id}, {"$set": merged})
    return {"message": "Product updated"}


@router.get("/admin/categories")
async def admin_list_categories(
    page: int = 1,
    per_page: int = 20,
    search: Optional[str] = None,
    status: Optional[str] = None,
    admin: Dict[str, Any] = Depends(require_admin),
):
    query: Dict[str, Any] = {}
    if search:
        query["name"] = {"$regex": search, "$options": "i"}
    if status == "active":
        query["is_active"] = True
    elif status == "inactive":
        query["is_active"] = False

    cats = await db.categories.find(query, {"_id": 0}).sort("name", 1).to_list(1000)
    for cat in cats:
        cat["product_count"] = await db.products.count_documents({"category": cat["name"]})
    total = len(cats)
    skip = (page - 1) * per_page
    return {
        "categories": cats[skip: skip + per_page],
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": max(1, (total + per_page - 1) // per_page),
    }


@router.post("/admin/categories")
async def admin_create_category(
    payload: CategoryCreate,
    admin: Dict[str, Any] = Depends(require_admin),
):
    existing = await db.categories.find_one({"name": payload.name})
    if existing:
        raise HTTPException(status_code=409, detail="Category already exists")
    cat = {
        "id": make_id(),
        "name": payload.name,
        "description": payload.description,
        "is_active": payload.is_active,
        "created_at": now_iso(),
    }
    await db.categories.insert_one(cat)
    cat.pop("_id", None)
    return {"category": cat}


@router.put("/admin/categories/{cat_id}")
async def admin_update_category(
    cat_id: str,
    payload: CategoryUpdate,
    admin: Dict[str, Any] = Depends(require_admin),
):
    cat = await db.categories.find_one({"id": cat_id}, {"_id": 0})
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    update = {k: v for k, v in payload.dict().items() if v is not None}
    if payload.description is not None:
        update["description"] = payload.description
    if update:
        await db.categories.update_one({"id": cat_id}, {"$set": update})
    cat.update(update)
    return {"category": cat}


@router.delete("/admin/categories/{cat_id}")
async def admin_delete_category(
    cat_id: str,
    admin: Dict[str, Any] = Depends(require_admin),
):
    cat = await db.categories.find_one({"id": cat_id})
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    product_count = await db.products.count_documents({"category": cat["name"]})
    if product_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: {product_count} product(s) are linked to this category.",
        )
    await db.categories.delete_one({"id": cat_id})
    return {"message": "Category deleted"}
