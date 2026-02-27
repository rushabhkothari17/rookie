"""Admin: Forms management and enquiry PDF export."""
from __future__ import annotations

import io
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.helpers import make_id, now_iso
from core.tenant import get_tenant_filter, tenant_id_of, get_tenant_admin
from db.session import db
from services.audit_service import create_audit_log

router = APIRouter(prefix="/api", tags=["admin-forms"])


class FormCreate(BaseModel):
    name: str
    schema: str = "[]"


class FormUpdate(BaseModel):
    name: Optional[str] = None
    schema: Optional[str] = None


@router.get("/admin/forms")
async def list_forms(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """List all custom forms for the tenant."""
    tf = get_tenant_filter(admin)
    forms = await db.tenant_forms.find(tf, {"_id": 0}).sort("created_at", 1).to_list(200)
    return {"forms": forms}


@router.post("/admin/forms")
async def create_form(
    payload: FormCreate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """Create a new custom form."""
    tid = tenant_id_of(admin)
    form_id = make_id()
    form = {
        "id": form_id,
        "tenant_id": tid,
        "name": payload.name.strip(),
        "schema": payload.schema or "[]",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.tenant_forms.insert_one(form)
    form.pop("_id", None)
    await create_audit_log(
        entity_type="form",
        entity_id=form_id,
        action="created",
        actor=admin.get("email", "admin"),
        details={"name": payload.name},
        tenant_id=tid,
    )
    return {"form": form}


@router.put("/admin/forms/{form_id}")
async def update_form(
    form_id: str,
    payload: FormUpdate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """Update an existing custom form."""
    tf = get_tenant_filter(admin)
    existing = await db.tenant_forms.find_one({**tf, "id": form_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Form not found")

    update: Dict[str, Any] = {"updated_at": now_iso()}
    if payload.name is not None:
        update["name"] = payload.name.strip()
    if payload.schema is not None:
        update["schema"] = payload.schema

    await db.tenant_forms.update_one({"id": form_id}, {"$set": update})
    await create_audit_log(
        entity_type="form",
        entity_id=form_id,
        action="updated",
        actor=admin.get("email", "admin"),
        details={"fields": list(update.keys())},
        tenant_id=tenant_id_of(admin),
    )
    return {"message": "Form updated"}


@router.delete("/admin/forms/{form_id}")
async def delete_form(
    form_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """Delete a custom form. Fails if products are using it."""
    tf = get_tenant_filter(admin)
    existing = await db.tenant_forms.find_one({**tf, "id": form_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Form not found")

    products_using = await db.products.count_documents({**tf, "enquiry_form_id": form_id})
    if products_using > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete: {products_using} product(s) reference this form. Update them first.",
        )

    await db.tenant_forms.delete_one({"id": form_id})
    await create_audit_log(
        entity_type="form",
        entity_id=form_id,
        action="deleted",
        actor=admin.get("email", "admin"),
        details={"name": existing.get("name")},
        tenant_id=tenant_id_of(admin),
    )
    return {"message": "Form deleted"}


@router.get("/admin/enquiries/{order_id}/pdf")
async def download_enquiry_pdf(
    order_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """Generate and stream a simple PDF for an enquiry submission."""
    tf = get_tenant_filter(admin)
    order = await db.orders.find_one(
        {**tf, "id": order_id, "type": "scope_request"}, {"_id": 0}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Enquiry not found")

    customer = await db.customers.find_one(
        {"id": order.get("customer_id", "")}, {"_id": 0}
    )
    user = None
    if customer and customer.get("user_id"):
        user = await db.users.find_one(
            {"id": customer["user_id"]},
            {"_id": 0, "id": 1, "email": 1, "full_name": 1},
        )

    items = await db.order_items.find({"order_id": order_id}, {"_id": 0}).to_list(20)
    product_ids = [i.get("product_id") for i in items if i.get("product_id")]
    products = await db.products.find(
        {"id": {"$in": product_ids}}, {"_id": 0, "id": 1, "name": 1}
    ).to_list(20)
    product_names = [p["name"] for p in products]

    from services.enquiry_pdf_service import generate_enquiry_pdf

    pdf_bytes = generate_enquiry_pdf(
        order_number=order.get("order_number", order_id),
        created_at=order.get("created_at", ""),
        customer_name=(
            (user.get("full_name") if user else "")
            or (customer.get("company_name", "") if customer else "")
        ),
        customer_email=user.get("email", "") if user else "",
        products=product_names,
        scope_form_data=order.get("scope_form_data", {}),
        status=order.get("status", ""),
    )

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="enquiry-{order.get("order_number", order_id)}.pdf"'
            )
        },
    )
