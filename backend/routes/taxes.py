"""Tax management routes: settings, global table, partner override rules."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.helpers import make_id, now_iso
from core.tenant import get_tenant_admin, tenant_id_of
from core.security import get_current_user
from db.session import db
from models import TaxSettingsUpdate, TaxOverrideRuleCreate
from services.audit_service import create_audit_log
from services.tax_tables import get_seed_tax_table

router = APIRouter(prefix="/api", tags=["taxes"])


# ── Tax Settings ─────────────────────────────────────────────────────────────

@router.get("/admin/taxes/settings")
async def get_tax_settings(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tid = tenant_id_of(admin)
    tenant = await db.tenants.find_one({"id": tid}, {"_id": 0, "tax_settings": 1})
    return {"tax_settings": (tenant or {}).get("tax_settings") or {}}


@router.put("/admin/taxes/settings")
async def update_tax_settings(
    payload: TaxSettingsUpdate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tid = tenant_id_of(admin)
    update = {k: v for k, v in payload.dict().items() if v is not None}
    if payload.enabled is not None:
        update["enabled"] = payload.enabled  # preserve False

    if not update:
        return {"message": "Nothing to update"}

    tenant = await db.tenants.find_one({"id": tid}, {"_id": 0, "tax_settings": 1})
    existing = ((tenant or {}).get("tax_settings") or {})
    merged = {**existing, **update}
    await db.tenants.update_one({"id": tid}, {"$set": {"tax_settings": merged}})
    await create_audit_log(
        entity_type="tax_settings", entity_id=tid, action="updated",
        actor=admin.get("email", "admin"), details={"updated_fields": list(update.keys())}, tenant_id=tid,
    )
    return {"message": "Tax settings updated", "tax_settings": merged}


# ── Tax Table ─────────────────────────────────────────────────────────────────

async def _ensure_tax_table_seeded():
    """Seed the tax_tables collection from static data if it is empty."""
    count = await db.tax_tables.count_documents({})
    if count == 0:
        entries = get_seed_tax_table()
        if entries:
            await db.tax_tables.insert_many(entries)


@router.get("/admin/taxes/tables")
async def get_tax_tables(
    country_code: Optional[str] = None,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    await _ensure_tax_table_seeded()
    query: Dict[str, Any] = {}
    if country_code:
        query["country_code"] = country_code.upper()
    entries = await db.tax_tables.find(query, {"_id": 0}).sort(
        [("country_code", 1), ("state_code", 1)]
    ).to_list(600)
    return {"entries": entries}


@router.put("/admin/taxes/tables/{country_code}/{state_code}")
async def update_tax_table_entry(
    country_code: str,
    state_code: str,
    payload: Dict[str, Any],
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    rate = payload.get("rate")
    if rate is None:
        raise HTTPException(status_code=400, detail="rate is required")

    update: Dict[str, Any] = {"rate": float(rate)}
    if payload.get("label"):
        update["label"] = payload["label"]

    await _ensure_tax_table_seeded()
    await db.tax_tables.update_one(
        {"country_code": country_code.upper(), "state_code": state_code.upper()},
        {"$set": update},
        upsert=True,
    )
    await create_audit_log(
        entity_type="tax_table", entity_id=f"{country_code.upper()}/{state_code.upper()}", action="updated",
        actor=admin.get("email", "admin"), details={"rate": float(rate)}, tenant_id=tenant_id_of(admin),
    )
    return {"message": "Tax table entry updated"}


# ── Override Rules ────────────────────────────────────────────────────────────

@router.get("/admin/taxes/overrides")
async def get_tax_overrides(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tid = tenant_id_of(admin)
    rules = await db.tax_override_rules.find(
        {"tenant_id": tid}, {"_id": 0}
    ).sort("priority", -1).to_list(100)
    return {"rules": rules}


@router.post("/admin/taxes/overrides")
async def create_tax_override(
    payload: TaxOverrideRuleCreate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tid = tenant_id_of(admin)
    rule_id = make_id()
    rule = {
        "id": rule_id,
        "tenant_id": tid,
        "name": payload.name,
        "conditions": payload.conditions,
        "tax_rate": float(payload.tax_rate),
        "tax_name": payload.tax_name,
        "priority": payload.priority,
        "enabled": True,
        "created_at": now_iso(),
    }
    await db.tax_override_rules.insert_one(rule)
    rule.pop("_id", None)
    await create_audit_log(
        entity_type="tax_override_rule", entity_id=rule_id, action="created",
        actor=admin.get("email", "admin"), details={"name": payload.name, "tax_rate": float(payload.tax_rate)}, tenant_id=tid,
    )
    return {"rule": rule}


@router.put("/admin/taxes/overrides/{rule_id}")
async def update_tax_override(
    rule_id: str,
    payload: TaxOverrideRuleCreate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tid = tenant_id_of(admin)
    existing = await db.tax_override_rules.find_one(
        {"id": rule_id, "tenant_id": tid}, {"_id": 0}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Override rule not found")

    await db.tax_override_rules.update_one(
        {"id": rule_id, "tenant_id": tid},
        {"$set": {
            "name": payload.name,
            "conditions": payload.conditions,
            "tax_rate": float(payload.tax_rate),
            "tax_name": payload.tax_name,
            "priority": payload.priority,
            "updated_at": now_iso(),
        }},
    )
    await create_audit_log(
        entity_type="tax_override_rule", entity_id=rule_id, action="updated",
        actor=admin.get("email", "admin"), details={"name": payload.name, "tax_rate": float(payload.tax_rate)}, tenant_id=tid,
    )
    return {"message": "Override rule updated"}


@router.delete("/admin/taxes/overrides/{rule_id}")
async def delete_tax_override(
    rule_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tid = tenant_id_of(admin)
    result = await db.tax_override_rules.delete_one({"id": rule_id, "tenant_id": tid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Override rule not found")
    await create_audit_log(
        entity_type="tax_override_rule", entity_id=rule_id, action="deleted",
        actor=admin.get("email", "admin"), details={}, tenant_id=tid,
    )
    return {"message": "Override rule deleted"}


# ── Customer tax-exempt toggle ─────────────────────────────────────────────────

@router.patch("/admin/customers/{customer_id}/tax-exempt")
async def set_customer_tax_exempt(
    customer_id: str,
    payload: Dict[str, Any],
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    from core.tenant import get_tenant_filter
    tf = get_tenant_filter(admin)
    customer = await db.customers.find_one({**tf, "id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    tax_exempt = bool(payload.get("tax_exempt", False))
    await db.customers.update_one(
        {"id": customer_id},
        {"$set": {"tax_exempt": tax_exempt}},
    )
    return {"message": "Customer tax-exempt status updated", "tax_exempt": tax_exempt}


# ── Invoice Settings ─────────────────────────────────────────────────────────

@router.get("/admin/taxes/invoice-settings")
async def get_invoice_settings(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tid = tenant_id_of(admin)
    tenant = await db.tenants.find_one({"id": tid}, {"_id": 0, "tax_settings": 1})
    ts = (tenant or {}).get("tax_settings") or {}
    return {"invoice_settings": ts.get("invoice_settings") or {
        "prefix": "INV",
        "payment_terms": "Due on receipt",
        "footer_notes": "",
        "show_terms": True,
        "template": "classic",
    }}


@router.put("/admin/taxes/invoice-settings")
async def update_invoice_settings(
    payload: Dict[str, Any],
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tid = tenant_id_of(admin)
    tenant = await db.tenants.find_one({"id": tid}, {"_id": 0, "tax_settings": 1})
    ts = (tenant or {}).get("tax_settings") or {}
    existing_inv = ts.get("invoice_settings") or {}
    merged = {**existing_inv, **payload}
    ts["invoice_settings"] = merged
    await db.tenants.update_one({"id": tid}, {"$set": {"tax_settings": ts}})
    return {"message": "Invoice settings updated", "invoice_settings": merged}


# ── Invoice data endpoint (used by InvoiceViewer) ─────────────────────────────

@router.get("/orders/{order_id}/invoice")
async def get_invoice_data(
    order_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Returns all data needed to render an invoice. Accessible by customer (own orders) or admin."""
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Auth check: customer can only see their own orders
    if user.get("role") == "customer":
        customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
        if not customer or order.get("customer_id") != customer.get("id"):
            raise HTTPException(status_code=403, detail="Access denied")
        tenant_id = order.get("tenant_id") or customer.get("tenant_id")
    else:
        tenant_id = order.get("tenant_id") or user.get("tenant_id")

    # Customer details
    customer = await db.customers.find_one({"id": order.get("customer_id")}, {"_id": 0})
    customer_user = {}
    if customer:
        customer_user = await db.users.find_one({"id": customer.get("user_id")}, {"_id": 0, "password_hash": 0}) or {}
    address = await db.addresses.find_one({"customer_id": order.get("customer_id")}, {"_id": 0}) or {}

    # Partner / tenant details
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0}) or {}
    ts = tenant.get("tax_settings") or {}
    invoice_settings = ts.get("invoice_settings") or {
        "prefix": "INV", "payment_terms": "Due on receipt",
        "footer_notes": "", "show_terms": True, "template": "classic",
    }

    # Order items with product names
    items = await db.order_items.find({"order_id": order_id}, {"_id": 0}).to_list(50)
    product_ids = [i.get("product_id") for i in items if i.get("product_id")]
    if product_ids:
        products = await db.products.find(
            {"id": {"$in": product_ids}},
            {"_id": 0, "id": 1, "name": 1}
        ).to_list(len(product_ids))
        pmap = {p["id"]: p["name"] for p in products}
        items = [{**i, "product_name": pmap.get(i.get("product_id", ""), i.get("product_name", ""))} for i in items]

    # Build invoice number
    prefix = invoice_settings.get("prefix", "INV")
    inv_number = f"{prefix}-{order.get('order_number', order_id[:8])}" if prefix else order.get("order_number", order_id[:8])

    return {
        "invoice_number": inv_number,
        "order": order,
        "customer": {
            "full_name": customer_user.get("full_name", ""),
            "email": customer_user.get("email", ""),
            "company_name": customer_user.get("company_name", ""),
            "phone": customer_user.get("phone", ""),
        },
        "address": address,
        "partner": {
            "name": tenant.get("name", ""),
            "code": tenant.get("code", ""),
            "address": tenant.get("address") or {},
        },
        "invoice_settings": invoice_settings,
        "items": items,
    }


# ── Send Invoice Email ─────────────────────────────────────────────────────────

@router.post("/orders/{order_id}/send-invoice")
async def send_invoice_email(
    order_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Send the invoice for an order to the customer's email."""
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Auth check
    if user.get("role") == "customer":
        customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
        if not customer or order.get("customer_id") != customer.get("id"):
            raise HTTPException(status_code=403, detail="Access denied")
        tenant_id = order.get("tenant_id") or customer.get("tenant_id")
    else:
        tenant_id = order.get("tenant_id") or user.get("tenant_id")

    # Customer email
    customer = await db.customers.find_one({"id": order.get("customer_id")}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=400, detail="Customer not found")
    customer_user = await db.users.find_one({"id": customer.get("user_id")}, {"_id": 0, "password_hash": 0}) or {}
    recipient_email = customer_user.get("email", "")
    if not recipient_email:
        raise HTTPException(status_code=400, detail="Customer has no email address")

    # Partner / invoice settings
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0}) or {}
    ts = tenant.get("tax_settings") or {}
    invoice_settings = ts.get("invoice_settings") or {"prefix": "INV", "payment_terms": "Due on receipt", "footer_notes": ""}
    prefix = invoice_settings.get("prefix", "INV")
    inv_number = f"{prefix}-{order.get('order_number', order_id[:8])}" if prefix else order.get("order_number", order_id[:8])

    # Build items rows HTML
    items = await db.order_items.find({"order_id": order_id}, {"_id": 0}).to_list(50)
    product_ids = [i.get("product_id") for i in items if i.get("product_id")]
    pmap: Dict[str, str] = {}
    if product_ids:
        products = await db.products.find({"id": {"$in": product_ids}}, {"_id": 0, "id": 1, "name": 1}).to_list(len(product_ids))
        pmap = {p["id"]: p["name"] for p in products}

    currency = order.get("currency", "USD")
    items_rows = ""
    for item in items:
        name = pmap.get(item.get("product_id", ""), item.get("product_name", "Item"))
        amount = f"{currency} {(item.get('line_total') or 0):.2f}"
        items_rows += f'<tr><td style="padding:6px 4px;color:#1e293b;font-size:13px">{name}</td><td style="padding:6px 4px;text-align:right;color:#1e293b;font-size:13px">{amount}</td></tr>'

    # Tax row
    tax_row_html = ""
    if (order.get("tax_amount") or 0) > 0:
        tax_row_html = f'<p style="color:#64748b;font-size:13px;margin:8px 0 0">Tax ({order.get("tax_name","Tax")}): {currency} {order.get("tax_amount",0):.2f}</p>'

    from services.email_service import EmailService
    result = await EmailService.send(
        trigger="invoice_email",
        recipient=recipient_email,
        variables={
            "customer_name": customer_user.get("full_name", "Customer"),
            "customer_email": recipient_email,
            "partner_name": tenant.get("name", ""),
            "invoice_number": inv_number,
            "invoice_date": (order.get("created_at") or "")[:10],
            "order_number": order.get("order_number", ""),
            "order_total": f"{(order.get('total') or 0):.2f}",
            "order_currency": currency,
            "invoice_items_rows": items_rows,
            "tax_row": tax_row_html,
            "footer_notes": invoice_settings.get("footer_notes", ""),
        },
        db=db,
        tenant_id=tenant_id,
    )
    return {"message": "Invoice email sent", "status": result.get("status"), "recipient": recipient_email}


# ── Partner-Specific Invoice Templates ────────────────────────────────────────

@router.get("/admin/taxes/invoice-templates")
async def get_invoice_templates(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tid = tenant_id_of(admin)
    templates = await db.partner_invoice_templates.find(
        {"tenant_id": tid}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return {"templates": templates}


@router.post("/admin/taxes/invoice-templates")
async def create_invoice_template(
    payload: Dict[str, Any],
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tid = tenant_id_of(admin)
    if not payload.get("name"):
        raise HTTPException(status_code=400, detail="name is required")
    tmpl = {
        "id": make_id(),
        "tenant_id": tid,
        "name": payload["name"],
        "html_body": payload.get("html_body", ""),
        "is_active": True,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.partner_invoice_templates.insert_one(tmpl)
    tmpl.pop("_id", None)
    return {"template": tmpl}


@router.put("/admin/taxes/invoice-templates/{tmpl_id}")
async def update_invoice_template(
    tmpl_id: str,
    payload: Dict[str, Any],
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tid = tenant_id_of(admin)
    existing = await db.partner_invoice_templates.find_one({"id": tmpl_id, "tenant_id": tid}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Template not found")
    update = {k: v for k, v in payload.items() if k in {"name", "html_body", "is_active"}}
    update["updated_at"] = now_iso()
    await db.partner_invoice_templates.update_one({"id": tmpl_id, "tenant_id": tid}, {"$set": update})
    return {"message": "Template updated"}


@router.delete("/admin/taxes/invoice-templates/{tmpl_id}")
async def delete_invoice_template(
    tmpl_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tid = tenant_id_of(admin)
    result = await db.partner_invoice_templates.delete_one({"id": tmpl_id, "tenant_id": tid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"message": "Template deleted"}


# ── Invoice data endpoint updated to include custom templates ─────────────────

@router.get("/admin/taxes/invoice-templates-for-viewer")
async def get_invoice_templates_for_viewer(
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """Used by the InvoiceViewer to load custom templates for the selector."""
    tid = tenant_id_of(admin)
    templates = await db.partner_invoice_templates.find(
        {"tenant_id": tid, "is_active": {"$ne": False}}, {"_id": 0}
    ).to_list(50)
    return {"templates": templates}


# ── Tax Summary ───────────────────────────────────────────────────────────────

@router.get("/admin/taxes/summary")
async def get_tax_summary(
    months: int = 12,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """Aggregate tax collected by month and tax type."""
    from core.tenant import get_tenant_filter
    tf = get_tenant_filter(admin)
    query = {**tf, "tax_amount": {"$gt": 0}}

    pipeline = [
        {"$match": query},
        {"$group": {
            "_id": {
                "month": {"$substr": ["$created_at", 0, 7]},
                "tax_name": "$tax_name",
                "currency": "$currency",
            },
            "total_tax": {"$sum": "$tax_amount"},
            "total_revenue": {"$sum": "$total"},
            "order_count": {"$sum": 1},
        }},
        {"$sort": {"_id.month": -1, "_id.tax_name": 1}},
        {"$limit": months * 10},
    ]

    results = await db.orders.aggregate(pipeline).to_list(500)
    rows = []
    for r in results:
        rows.append({
            "month": r["_id"]["month"],
            "tax_name": r["_id"]["tax_name"] or "Tax",
            "currency": r["_id"]["currency"] or "USD",
            "total_tax": round(r["total_tax"], 2),
            "total_revenue": round(r["total_revenue"], 2),
            "order_count": r["order_count"],
        })
    return {"summary": rows}
