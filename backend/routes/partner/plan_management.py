"""Partner self-service plan management routes.

Endpoints:
  GET  /api/partner/my-plan        – current plan, subscription, and available upgrades
  POST /api/partner/upgrade-plan   – upgrade to a higher plan (creates sub + pro-rata order)
  POST /api/partner/submissions    – submit a downgrade / support request
  GET  /api/partner/submissions    – partner's own submissions list
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.helpers import make_id, now_iso
from core.tenant import get_tenant_admin, tenant_id_of, DEFAULT_TENANT_ID
from db.session import db
from services.audit_service import create_audit_log

router = APIRouter(prefix="/api", tags=["partner-plans"])

# ---------------------------------------------------------------------------
# GET /partner/my-plan
# ---------------------------------------------------------------------------

@router.get("/partner/my-plan")
async def get_my_plan(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Return current plan info, active subscription, and available public plans for upgrade."""
    tid = tenant_id_of(admin)
    tenant = await db.tenants.find_one({"id": tid}, {"_id": 0, "license": 1, "name": 1})
    license_info = (tenant or {}).get("license") or {}

    current_plan_id = license_info.get("plan_id")
    current_plan = None
    if current_plan_id:
        current_plan = await db.plans.find_one({"id": current_plan_id}, {"_id": 0})

    # Active partner subscription for this partner
    subscription = await db.partner_subscriptions.find_one(
        {"partner_id": tid, "status": {"$in": ["active", "pending"]}},
        {"_id": 0},
    )

    # Available public plans (exclude current, show all active+public)
    available_plans = await db.plans.find(
        {"is_active": True, "is_public": True, "id": {"$ne": current_plan_id}},
        {"_id": 0},
    ).sort("max_users", 1).to_list(50)

    return {
        "current_plan": current_plan,
        "license": license_info,
        "subscription": subscription,
        "available_plans": available_plans,
    }


# ---------------------------------------------------------------------------
# POST /partner/upgrade-plan
# ---------------------------------------------------------------------------

class UpgradePlanRequest(BaseModel):
    plan_id: str


@router.post("/partner/upgrade-plan")
async def upgrade_plan(
    payload: UpgradePlanRequest,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """
    Self-service plan upgrade. Creates a new subscription (if none) or updates
    the existing one and generates a pro-rata order for the difference.
    All billing anchored to 1st of the month.
    """
    tid = tenant_id_of(admin)

    # Validate target plan
    new_plan = await db.plans.find_one({"id": payload.plan_id, "is_active": True, "is_public": True}, {"_id": 0})
    if not new_plan:
        raise HTTPException(status_code=404, detail="Plan not found or not available for self-service upgrade")

    # Current plan
    tenant = await db.tenants.find_one({"id": tid}, {"_id": 0, "license": 1, "name": 1})
    license_info = (tenant or {}).get("license") or {}
    current_plan_id = license_info.get("plan_id")
    if current_plan_id:
        current_plan = await db.plans.find_one({"id": current_plan_id}, {"_id": 0})
        old_monthly = (current_plan or {}).get("monthly_price", 0) or 0
    else:
        old_monthly = 0

    new_monthly = new_plan.get("monthly_price", 0) or 0
    partner_name = (tenant or {}).get("name", "")

    # Pro-rata billing
    from services.billing_service import calculate_prorata, calculate_upgrade_prorata, next_first_of_month
    today = datetime.now(timezone.utc).date()

    # Existing active subscription?
    existing_sub = await db.partner_subscriptions.find_one(
        {"partner_id": tid, "status": {"$in": ["active", "pending"]}},
        {"_id": 0},
    )

    now = now_iso()
    orders_created = []

    if existing_sub:
        # ── UPGRADE existing subscription ──────────────────────────────
        prorata = calculate_upgrade_prorata(old_monthly, new_monthly, today)

        # Update subscription plan
        await db.partner_subscriptions.update_one(
            {"id": existing_sub["id"]},
            {"$set": {
                "plan_id": new_plan["id"],
                "plan_name": new_plan["name"],
                "amount": new_monthly,
                "updated_at": now,
            }},
        )

        # Create pro-rata difference order only if there's a chargeable amount
        if prorata["prorata_amount"] > 0:
            seq = await db.partner_orders.count_documents({}) + 1
            year = today.year
            order_number = f"PO-{year}-{seq:04d}"
            order_id = make_id()
            order_doc = {
                "id": order_id,
                "order_number": order_number,
                "subscription_id": existing_sub["id"],
                "subscription_number": existing_sub.get("subscription_number", ""),
                "partner_id": tid,
                "partner_name": partner_name,
                "plan_id": new_plan["id"],
                "description": f"Plan upgrade to {new_plan['name']} — pro-rata for {prorata['days_remaining']} days",
                "amount": prorata["prorata_amount"],
                "currency": existing_sub.get("currency", "GBP"),
                "status": "pending",
                "payment_method": existing_sub.get("payment_method", "offline"),
                "invoice_date": today.isoformat(),
                "due_date": today.isoformat(),
                "order_type": "upgrade_prorata",
                "created_at": now,
                "created_by": admin.get("email", "system"),
            }
            await db.partner_orders.insert_one(order_doc)
            orders_created.append(order_number)
    else:
        # ── NEW subscription ────────────────────────────────────────────
        prorata = calculate_prorata(new_monthly, today)
        sub_seq = await db.partner_subscriptions.count_documents({}) + 1
        sub_number = f"PS-{today.year}-{sub_seq:04d}"
        sub_id = make_id()

        sub_doc = {
            "id": sub_id,
            "subscription_number": sub_number,
            "partner_id": tid,
            "partner_name": partner_name,
            "plan_id": new_plan["id"],
            "plan_name": new_plan["name"],
            "description": f"Platform subscription — {new_plan['name']}",
            "amount": new_monthly,
            "currency": "GBP",
            "billing_interval": "monthly",
            "status": "active",
            "payment_method": "offline",
            "start_date": today.isoformat(),
            "next_billing_date": prorata["next_billing_date"],
            "created_at": now,
            "created_by": admin.get("email", "system"),
        }
        await db.partner_subscriptions.insert_one(sub_doc)

        if prorata["prorata_amount"] > 0:
            seq = await db.partner_orders.count_documents({}) + 1
            order_number = f"PO-{today.year}-{seq:04d}"
            order_id = make_id()
            order_doc = {
                "id": order_id,
                "order_number": order_number,
                "subscription_id": sub_id,
                "subscription_number": sub_number,
                "partner_id": tid,
                "partner_name": partner_name,
                "plan_id": new_plan["id"],
                "description": f"New subscription — {new_plan['name']} (pro-rata {prorata['days_remaining']}/{prorata['days_in_month']} days)",
                "amount": prorata["prorata_amount"],
                "currency": "GBP",
                "status": "pending",
                "payment_method": "offline",
                "invoice_date": today.isoformat(),
                "due_date": prorata["next_billing_date"],
                "order_type": "new_prorata",
                "created_at": now,
                "created_by": admin.get("email", "system"),
            }
            await db.partner_orders.insert_one(order_doc)
            orders_created.append(order_number)

    # Assign the new plan to the tenant's license
    limits = {k: v for k, v in new_plan.items() if k.startswith("max_")}
    await db.tenants.update_one({"id": tid}, {"$set": {
        "license": {
            "plan_id": new_plan["id"],
            "plan_name": new_plan["name"],
            "assigned_at": now,
            **limits,
        }
    }})

    await create_audit_log(
        entity_type="tenant",
        entity_id=tid,
        action="plan_upgraded",
        actor=admin.get("email", "system"),
        details={"from": current_plan_id, "to": new_plan["id"], "orders_created": orders_created},
    )

    return {
        "message": f"Successfully upgraded to {new_plan['name']}",
        "new_plan": new_plan,
        "orders_created": orders_created,
        "prorata_amount": prorata["prorata_amount"],
        "next_billing_date": prorata["next_billing_date"],
    }


# ---------------------------------------------------------------------------
# POST /partner/submissions  (downgrade request / support)
# ---------------------------------------------------------------------------

class SubmissionCreate(BaseModel):
    type: str  # "plan_downgrade" | "support"
    requested_plan_id: Optional[str] = None
    message: str = ""


@router.post("/partner/submissions")
async def create_submission(
    payload: SubmissionCreate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tid = tenant_id_of(admin)
    tenant = await db.tenants.find_one({"id": tid}, {"_id": 0, "license": 1, "name": 1})
    license_info = (tenant or {}).get("license") or {}
    current_plan_id = license_info.get("plan_id")

    requested_plan = None
    if payload.requested_plan_id:
        requested_plan = await db.plans.find_one({"id": payload.requested_plan_id}, {"_id": 0})

    # Effective date for downgrade = next 1st of month
    from services.billing_service import next_first_of_month
    today = datetime.now(timezone.utc).date()
    effective_date = next_first_of_month(today).isoformat()

    sub_id = make_id()
    doc = {
        "id": sub_id,
        "partner_id": tid,
        "partner_name": (tenant or {}).get("name", ""),
        "type": payload.type,
        "current_plan_id": current_plan_id,
        "current_plan_name": license_info.get("plan_name", ""),
        "requested_plan_id": payload.requested_plan_id,
        "requested_plan_name": (requested_plan or {}).get("name", ""),
        "message": payload.message,
        "status": "pending",
        "effective_date": effective_date,
        "created_by": admin.get("email", ""),
        "created_at": now_iso(),
        "resolved_at": None,
        "resolved_by": None,
        "resolution_note": None,
    }
    await db.partner_submissions.insert_one(doc)
    doc.pop("_id", None)
    return {"submission": doc}


# ---------------------------------------------------------------------------
# GET /partner/submissions
# ---------------------------------------------------------------------------

@router.get("/partner/submissions")
async def list_my_submissions(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tid = tenant_id_of(admin)
    items = await db.partner_submissions.find(
        {"partner_id": tid}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return {"submissions": items}
