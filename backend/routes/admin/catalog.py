"""Admin: Catalog (products + categories) routes."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.helpers import make_id, now_iso
from core.security import require_admin
from core.tenant import get_tenant_filter, set_tenant_id, tenant_id_of, get_tenant_admin
from db.session import db
from models import AdminProductCreate, AdminProductUpdate, CategoryCreate, CategoryUpdate, IntakeSchemaJson
from services.audit_service import create_audit_log
from services.pricing_service import calculate_price

router = APIRouter(prefix="/api", tags=["admin-catalog"])


def _label_to_key(label: str, fallback: str = "key") -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")[:40] or fallback


def _normalize_schema_dict(schema_dict: dict) -> None:
    """Auto-generate keys for questions and values for options (in-place on dict)."""
    questions = schema_dict.get("questions", {})
    for q_type in ("dropdown", "multiselect", "single_line", "multi_line"):
        for i, q in enumerate(questions.get(q_type, [])):
            if not q.get("key", "").strip():
                q["key"] = _label_to_key(q.get("label", ""), f"q_{i}")
            for opt in q.get("options", []):
                if not opt.get("value", "").strip():
                    opt["value"] = _label_to_key(opt.get("label", ""), "opt")


def _validate_intake_schema(schema: IntakeSchemaJson) -> None:
    """Validate intake schema: key uniqueness, option arrays, max 10 per type."""
    all_keys: list = []
    type_map = {
        "dropdown": schema.questions.dropdown,
        "multiselect": schema.questions.multiselect,
        "single_line": schema.questions.single_line,
        "multi_line": schema.questions.multi_line,
    }
    for q_type, questions in type_map.items():
        if len(questions) > 10:
            raise HTTPException(status_code=400, detail=f"Max 10 {q_type} questions allowed")
        for q in questions:
            if q_type in ("dropdown", "multiselect"):
                if not q.options:
                    raise HTTPException(status_code=400, detail=f"Question '{q.key or q.label}' must have options")
                for opt in q.options:
                    if not opt.label:
                        raise HTTPException(status_code=400, detail=f"Option in '{q.key or q.label}' must have a label")
            if q.key:
                all_keys.append(q.key)
    seen: set = set()
    for k in all_keys:
        if k in seen:
            raise HTTPException(status_code=400, detail=f"Duplicate question key: '{k}'")
        seen.add(k)


def _build_sections(sections_payload: list) -> List[Dict[str, Any]]:
    """Normalize custom_sections list: ensure IDs and consistent order."""
    result = []
    for i, sec in enumerate(sections_payload):
        sec_dict = sec.dict() if hasattr(sec, "dict") else dict(sec)
        if not sec_dict.get("id"):
            sec_dict["id"] = make_id()
        sec_dict["order"] = i
        result.append(sec_dict)
    return result


@router.get("/admin/products-all")
async def admin_list_all_products(
    page: int = 1,
    per_page: int = 20,
    search: Optional[str] = None,
    category: Optional[str] = None,
    billing: Optional[str] = None,
    pricing_type: Optional[str] = None,
    status: Optional[str] = None,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    query: Dict[str, Any] = {**tf}
    if search:
        query["$or"] = [
            {"name": {"$regex": re.escape(search), "$options": "i"}},
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
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tid = tenant_id_of(admin)
    product_id = make_id()
    product: Dict[str, Any] = {
        "id": product_id,
        "tenant_id": tid,
        "name": payload.name,
        "short_description": payload.short_description,
        "tagline": payload.tagline or payload.short_description,
        "card_title": payload.card_title,
        "card_tag": payload.card_tag,
        "card_description": payload.card_description,
        "card_bullets": payload.card_bullets,
        "description_long": payload.description_long,
        "bullets": payload.bullets,
        "bullets_included": payload.bullets_included,
        "tag": payload.tag,
        "category": payload.category,
        "faqs": payload.faqs,
        "terms_id": payload.terms_id,
        "base_price": payload.base_price,
        "is_subscription": payload.is_subscription,
        "stripe_price_id": payload.stripe_price_id,
        "is_active": payload.is_active,
        "visible_to_customers": payload.visible_to_customers,
        "restricted_to": payload.restricted_to,
        "price_rounding": payload.price_rounding or None,
        "pricing_type": payload.pricing_type or "fixed",
        "pricing_rules": payload.pricing_rules or {},
        "created_at": now_iso(),
        "is_custom": True,
    }
    # Custom sections — default to one "Overview" section if not provided
    if payload.custom_sections:
        product["custom_sections"] = _build_sections(payload.custom_sections)
    else:
        product["custom_sections"] = [{
            "id": make_id(), "name": "Overview", "content": "",
            "icon": "FileText", "icon_color": "blue", "tags": [], "order": 0,
        }]
    if payload.intake_schema_json is not None:
        _validate_intake_schema(payload.intake_schema_json)
        schema_dict = payload.intake_schema_json.dict()
        _normalize_schema_dict(schema_dict)
        product["intake_schema_json"] = {
            **schema_dict,
            "version": 1,
            "updated_at": now_iso(),
            "updated_by": admin.get("email", admin["id"]),
        }
    product["price_inputs"] = build_price_inputs(product)
    await db.products.insert_one(product)
    product.pop("_id", None)
    audit_details: Dict[str, Any] = {"name": payload.name, "category": payload.category, "is_subscription": payload.is_subscription}
    if payload.intake_schema_json is not None:
        q = payload.intake_schema_json.questions
        audit_details["intake_schema"] = {
            "dropdown": len(q.dropdown), "multiselect": len(q.multiselect),
            "single_line": len(q.single_line), "multi_line": len(q.multi_line),
        }
    await create_audit_log(
        entity_type="product",
        entity_id=product_id,
        action="created",
        actor=f"admin:{admin.get('email', admin['id'])}",
        details=audit_details,
    )
    return {"product": product}


@router.put("/admin/products/{product_id}")
async def admin_update_product(
    product_id: str,
    payload: AdminProductUpdate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    existing = await db.products.find_one({**tf, "id": product_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Product not found")

    update_fields: Dict[str, Any] = {
        "name": payload.name,
        "is_active": payload.is_active,
    }
    if payload.short_description is not None:
        update_fields["short_description"] = payload.short_description
    if payload.tagline is not None:
        update_fields["tagline"] = payload.tagline
    elif payload.short_description is not None and not existing.get("tagline"):
        update_fields["tagline"] = payload.short_description
    if payload.card_title is not None:
        update_fields["card_title"] = payload.card_title
    if payload.card_tag is not None:
        update_fields["card_tag"] = payload.card_tag
    if payload.card_description is not None:
        update_fields["card_description"] = payload.card_description
    if payload.card_bullets is not None:
        update_fields["card_bullets"] = payload.card_bullets
    if payload.description_long is not None:
        update_fields["description_long"] = payload.description_long
    if payload.bullets is not None:
        update_fields["bullets"] = payload.bullets
    if payload.bullets_included is not None:
        update_fields["bullets_included"] = payload.bullets_included
    if payload.tag is not None:
        update_fields["tag"] = payload.tag
    if payload.category is not None:
        update_fields["category"] = payload.category
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
    if payload.pricing_type is not None:
        update_fields["pricing_type"] = payload.pricing_type
    if payload.pricing_rules is not None:
        update_fields["pricing_rules"] = payload.pricing_rules
    if payload.visible_to_customers is not None:
        update_fields["visible_to_customers"] = payload.visible_to_customers
    if payload.restricted_to is not None:
        update_fields["restricted_to"] = payload.restricted_to
    if payload.price_rounding is not None:
        update_fields["price_rounding"] = payload.price_rounding if payload.price_rounding else None
    if payload.intake_schema_json is not None:
        _validate_intake_schema(payload.intake_schema_json)
        schema_dict = payload.intake_schema_json.dict()
        _normalize_schema_dict(schema_dict)
        current_version = (existing.get("intake_schema_json") or {}).get("version", 0)
        update_fields["intake_schema_json"] = {
            **schema_dict,
            "version": current_version + 1,
            "updated_at": now_iso(),
            "updated_by": admin.get("email", admin["id"]),
        }
    if payload.custom_sections is not None:
        update_fields["custom_sections"] = _build_sections(payload.custom_sections)

    merged = {**existing, **update_fields}
    merged["price_inputs"] = build_price_inputs(merged)
    await db.products.update_one({"id": product_id}, {"$set": merged})
    audit_details: Dict[str, Any] = {"name": payload.name, "is_active": payload.is_active}
    if payload.intake_schema_json is not None:
        q = payload.intake_schema_json.questions
        audit_details["intake_schema"] = {
            "dropdown": len(q.dropdown), "multiselect": len(q.multiselect),
            "single_line": len(q.single_line), "multi_line": len(q.multi_line),
            "version": update_fields["intake_schema_json"]["version"],
        }
    await create_audit_log(
        entity_type="product",
        entity_id=product_id,
        action="updated",
        actor=f"admin:{admin.get('email', admin['id'])}",
        details=audit_details,
    )
    return {"message": "Product updated"}


@router.get("/admin/categories")
async def admin_list_categories(
    page: int = 1,
    per_page: int = 20,
    search: Optional[str] = None,
    status: Optional[str] = None,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    query: Dict[str, Any] = {**tf}
    if search:
        query["name"] = {"$regex": re.escape(search), "$options": "i"}
    if status == "active":
        query["is_active"] = True
    elif status == "inactive":
        query["is_active"] = False

    cats = await db.categories.find(query, {"_id": 0}).sort("name", 1).to_list(1000)
    for cat in cats:
        cat["product_count"] = await db.products.count_documents({**tf, "category": cat["name"]})
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
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    tid = tenant_id_of(admin)
    existing = await db.categories.find_one({**tf, "name": payload.name})
    if existing:
        raise HTTPException(status_code=409, detail="Category already exists")
    cat = {
        "id": make_id(),
        "tenant_id": tid,
        "name": payload.name,
        "description": payload.description,
        "is_active": payload.is_active,
        "created_at": now_iso(),
    }
    await db.categories.insert_one(cat)
    cat.pop("_id", None)
    await create_audit_log(
        entity_type="category",
        entity_id=cat["id"],
        action="created",
        actor=f"admin:{admin.get('email', admin['id'])}",
        details={"name": payload.name},
    )
    return {"category": cat}


@router.put("/admin/categories/{cat_id}")
async def admin_update_category(
    cat_id: str,
    payload: CategoryUpdate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    cat = await db.categories.find_one({**tf, "id": cat_id}, {"_id": 0})
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    update = {k: v for k, v in payload.dict().items() if v is not None}
    if payload.description is not None:
        update["description"] = payload.description
    if update:
        await db.categories.update_one({"id": cat_id}, {"$set": update})
    cat.update(update)
    await create_audit_log(
        entity_type="category",
        entity_id=cat_id,
        action="updated",
        actor=f"admin:{admin.get('email', admin['id'])}",
        details={"changes": update},
    )
    return {"category": cat}


@router.delete("/admin/categories/{cat_id}")
async def admin_delete_category(
    cat_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    cat = await db.categories.find_one({**get_tenant_filter(admin), "id": cat_id})
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    product_count = await db.products.count_documents({"category": cat["name"]})
    if product_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: {product_count} product(s) are linked to this category.",
        )
    await db.categories.delete_one({"id": cat_id})
    await create_audit_log(
        entity_type="category",
        entity_id=cat_id,
        action="deleted",
        actor=f"admin:{admin.get('email', admin['id'])}",
        details={"name": cat.get("name")},
    )
    return {"message": "Category deleted"}


@router.get("/admin/products/{product_id}/logs")
async def get_product_logs(product_id: str, page: int = 1, limit: int = 20, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    product = await db.products.find_one({**tf, "id": product_id}, {"_id": 0, "id": 1})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    flt = {"entity_type": "product", "entity_id": product_id}
    total = await db.audit_logs.count_documents(flt)
    skip = (page - 1) * limit
    logs = await db.audit_logs.find(flt, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"logs": logs, "total": total, "page": page, "limit": limit, "pages": max(1, (total + limit - 1) // limit)}

@router.get("/admin/categories/{cat_id}/logs")
async def get_category_logs(cat_id: str, page: int = 1, limit: int = 20, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    cat = await db.categories.find_one({**tf, "id": cat_id}, {"_id": 0, "id": 1})
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    flt = {"entity_type": "category", "entity_id": cat_id}
    total = await db.audit_logs.count_documents(flt)
    skip = (page - 1) * limit
    logs = await db.audit_logs.find(flt, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"logs": logs, "total": total, "page": page, "limit": limit, "pages": max(1, (total + limit - 1) // limit)}


