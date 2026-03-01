"""Partner Billing View — partner admins read their own B2B orders and subscriptions.

These routes are scoped to the logged-in partner's own tenant.
Read-only except for subscription cancellation (allowed only after term expires).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from core.helpers import make_id, now_iso
from core.tenant import get_tenant_admin, tenant_id_of, DEFAULT_TENANT_ID
from db.session import db
from services.audit_service import create_audit_log

router = APIRouter(prefix="/api", tags=["partner-billing-view"])


def _require_non_platform(admin: Dict[str, Any]) -> None:
    """Block platform admin from these partner-scoped endpoints."""
    if admin.get("role") == "platform_admin":
        raise HTTPException(status_code=403, detail="Platform admins use /admin/partner-* endpoints instead.")


# ---------------------------------------------------------------------------
# My Orders (read-only)
# ---------------------------------------------------------------------------

@router.get("/partner/my-orders")
async def my_partner_orders(
    status: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """List the partner's own B2B orders (raised by platform admin)."""
    _require_non_platform(admin)
    tid = tenant_id_of(admin)
    query: Dict[str, Any] = {"partner_id": tid}
    if status:
        query["status"] = status
    if search:
        query["$or"] = [
            {"order_number": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
        ]
    skip = (page - 1) * limit
    total = await db.partner_orders.count_documents(query)
    orders = await db.partner_orders.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"orders": orders, "total": total, "page": page, "limit": limit}


# ---------------------------------------------------------------------------
# My Subscriptions (read-only + cancel)
# ---------------------------------------------------------------------------

@router.get("/partner/my-subscriptions")
async def my_partner_subscriptions(
    status: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """List the partner's own B2B subscriptions."""
    _require_non_platform(admin)
    tid = tenant_id_of(admin)
    query: Dict[str, Any] = {"partner_id": tid}
    if status:
        query["status"] = status
    if search:
        query["$or"] = [
            {"subscription_number": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
            {"plan_name": {"$regex": search, "$options": "i"}},
        ]
    skip = (page - 1) * limit
    total = await db.partner_subscriptions.count_documents(query)
    subs = await db.partner_subscriptions.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"subscriptions": subs, "total": total, "page": page, "limit": limit}


@router.post("/partner/my-subscriptions/{sub_id}/cancel")
async def cancel_my_subscription(
    sub_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """Cancel a partner subscription — only allowed after the contract term has expired."""
    _require_non_platform(admin)
    tid = tenant_id_of(admin)

    sub = await db.partner_subscriptions.find_one({"id": sub_id, "partner_id": tid}, {"_id": 0})
    if sub is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    if sub.get("status") == "cancelled":
        raise HTTPException(status_code=400, detail="Subscription is already cancelled")

    # Enforce contract term
    term_months = sub.get("term_months")
    contract_end = sub.get("contract_end_date")
    if term_months and term_months > 0 and contract_end:
        try:
            end_dt = datetime.fromisoformat(contract_end.replace("Z", "+00:00")).replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) < end_dt:
                end_fmt = end_dt.strftime("%d %b %Y")
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot cancel: your contract term runs until {end_fmt}.",
                )
        except HTTPException:
            raise
        except Exception:
            pass

    cancelled_at = now_iso()
    await db.partner_subscriptions.update_one(
        {"id": sub_id},
        {"$set": {"status": "cancelled", "cancelled_at": cancelled_at, "updated_at": cancelled_at}},
    )
    await create_audit_log(
        entity_type="partner_subscription", entity_id=sub_id, action="cancelled_by_partner",
        actor=f"partner_admin:{admin.get('email', '')}",
        details={"cancelled_at": cancelled_at, "partner_id": tid},
    )

    # Send subscription_terminated email to the partner admin themselves
    if admin.get("email"):
        from services.email_service import EmailService
        import asyncio
        asyncio.create_task(EmailService.send(
            trigger="subscription_terminated",
            recipient=admin["email"],
            variables={
                "recipient_name": admin.get("full_name", admin.get("email", "")),
                "subscription_number": sub.get("subscription_number", ""),
                "plan_name": sub.get("plan_name", "—"),
                "cancelled_at": cancelled_at[:10],
                "cancel_reason": "Cancelled by partner administrator",
            },
            db=db,
            tenant_id=DEFAULT_TENANT_ID,
        ))

    return {"message": "Subscription cancelled", "cancelled_at": cancelled_at}


# ---------------------------------------------------------------------------
# Invoice Download
# ---------------------------------------------------------------------------

async def _load_invoice_data(order_id: str, partner_id: str):
    """Load and return order + partner org + invoice settings for PDF generation."""
    order = await db.partner_orders.find_one({"id": order_id, "partner_id": partner_id}, {"_id": 0})
    if not order:
        return None, None, None

    partner_org = await db.tenants.find_one({"id": partner_id}, {"_id": 0}) or {}
    # Load platform admin's invoice settings for the From details
    platform_ts = await db.tenants.find_one({"id": DEFAULT_TENANT_ID}, {"_id": 0}) or {}
    invoice_settings = (platform_ts.get("tax_settings") or {}).get("invoice_settings") or {}
    return order, partner_org, invoice_settings


@router.get("/partner/my-orders/{order_id}/download-invoice")
async def download_partner_invoice(
    order_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """Partner downloads a PDF invoice for one of their own orders."""
    _require_non_platform(admin)
    tid = tenant_id_of(admin)

    order, partner_org, invoice_settings = await _load_invoice_data(order_id, tid)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    from services.invoice_service import generate_partner_invoice_pdf
    platform_name = invoice_settings.get("company_name") or "Automate Accounts"
    pdf_bytes = generate_partner_invoice_pdf(order, partner_org, invoice_settings, platform_name)

    filename = f"invoice-{order.get('order_number', order_id)}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/partner/my-orders/{order_id}/invoice-html")
async def view_partner_invoice_html(
    order_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """Return invoice HTML data (order + active template) for browser print."""
    _require_non_platform(admin)
    tid = tenant_id_of(admin)

    order, partner_org, invoice_settings = await _load_invoice_data(order_id, tid)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    # Try to find an active custom HTML template for this tenant (platform tenant)
    template = await db.partner_invoice_templates.find_one(
        {"tenant_id": DEFAULT_TENANT_ID, "is_active": {"$ne": False}},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    return {
        "order": order,
        "partner": partner_org,
        "invoice_settings": invoice_settings,
        "template": template,
    }
