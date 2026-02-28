"""Admin: Plans management — platform super admin only.

Plans define reusable license templates.
Updating a plan automatically propagates limits to all tenants on that plan.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.helpers import make_id, now_iso
from core.tenant import require_platform_admin
from db.session import db
from services.audit_service import create_audit_log

router = APIRouter(prefix="/api", tags=["admin-plans"])

LIMIT_FIELDS = [
    "max_users", "max_storage_mb", "max_user_roles",
    "max_product_categories", "max_product_terms", "max_enquiries",
    "max_resources", "max_templates", "max_email_templates",
    "max_categories", "max_forms", "max_references",
    "max_orders_per_month", "max_customers_per_month", "max_subscriptions_per_month",
]


class PlanCreate(BaseModel):
    name: str
    description: Optional[str] = None
    warning_threshold_pct: int = 80
    max_users: Optional[int] = None
    max_storage_mb: Optional[int] = None
    max_user_roles: Optional[int] = None
    max_product_categories: Optional[int] = None
    max_product_terms: Optional[int] = None
    max_enquiries: Optional[int] = None
    max_resources: Optional[int] = None
    max_templates: Optional[int] = None
    max_email_templates: Optional[int] = None
    max_categories: Optional[int] = None
    max_forms: Optional[int] = None
    max_references: Optional[int] = None
    max_orders_per_month: Optional[int] = None
    max_customers_per_month: Optional[int] = None
    max_subscriptions_per_month: Optional[int] = None


class PlanUpdate(PlanCreate):
    name: Optional[str] = None  # name optional on update


# ---------------------------------------------------------------------------
# List & Create
# ---------------------------------------------------------------------------

@router.get("/admin/plans")
async def list_plans(admin: Dict[str, Any] = Depends(require_platform_admin)):
    """List all plans (active and inactive)."""
    plans = await db.plans.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    # Enrich with tenant count
    for plan in plans:
        plan["tenant_count"] = await db.tenants.count_documents({"license.plan_id": plan["id"]})
    return {"plans": plans}


@router.post("/admin/plans")
async def create_plan(payload: PlanCreate, admin: Dict[str, Any] = Depends(require_platform_admin)):
    """Create a new plan."""
    existing = await db.plans.find_one({"name": payload.name}, {"_id": 0, "id": 1})
    if existing:
        raise HTTPException(status_code=409, detail="A plan with this name already exists")

    plan_id = make_id()
    plan_doc = {
        "id": plan_id,
        "name": payload.name.strip(),
        "description": (payload.description or "").strip(),
        "is_active": True,
        "warning_threshold_pct": payload.warning_threshold_pct,
        **{f: getattr(payload, f) for f in LIMIT_FIELDS},
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.plans.insert_one({**plan_doc})
    plan_doc.pop("_id", None)

    await create_audit_log(
        entity_type="plan",
        entity_id=plan_id,
        action="created",
        actor=admin.get("email", "admin"),
        details={"name": payload.name},
    )
    return {"plan": plan_doc}


# ---------------------------------------------------------------------------
# Get / Update / Delete
# ---------------------------------------------------------------------------

@router.get("/admin/plans/{plan_id}")
async def get_plan(plan_id: str, admin: Dict[str, Any] = Depends(require_platform_admin)):
    plan = await db.plans.find_one({"id": plan_id}, {"_id": 0})
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan["tenant_count"] = await db.tenants.count_documents({"license.plan_id": plan_id})
    return {"plan": plan}


@router.put("/admin/plans/{plan_id}")
async def update_plan(
    plan_id: str,
    payload: PlanUpdate,
    admin: Dict[str, Any] = Depends(require_platform_admin),
):
    """
    Update a plan and auto-propagate the new limits to ALL tenants on this plan.
    Per-tenant overrides (other license fields not belonging to the plan) are preserved.
    """
    plan = await db.plans.find_one({"id": plan_id}, {"_id": 0})
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Build update dict from payload (only provided fields)
    updates = payload.dict(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates["updated_at"] = now_iso()

    await db.plans.update_one({"id": plan_id}, {"$set": updates})

    # Fetch the now-updated plan
    updated_plan = await db.plans.find_one({"id": plan_id}, {"_id": 0})
    updated_plan.pop("_id", None)

    # --- Auto-propagate to all tenants on this plan ---
    tenant_limit_updates = {
        f: updated_plan.get(f)
        for f in LIMIT_FIELDS
    }
    tenant_limit_updates["warning_threshold_pct"] = updated_plan.get("warning_threshold_pct", 80)
    tenant_limit_updates["plan"] = updated_plan.get("name")

    result = await db.tenants.update_many(
        {"license.plan_id": plan_id},
        {"$set": {
            **{f"license.{k}": v for k, v in tenant_limit_updates.items()},
            "updated_at": now_iso(),
        }},
    )
    affected = result.modified_count

    await create_audit_log(
        entity_type="plan",
        entity_id=plan_id,
        action="updated",
        actor=admin.get("email", "admin"),
        details={
            "changes": {k: v for k, v in updates.items() if k != "updated_at"},
            "tenants_propagated": affected,
        },
    )

    return {
        "plan": updated_plan,
        "tenants_propagated": affected,
    }


@router.delete("/admin/plans/{plan_id}")
async def delete_plan(plan_id: str, admin: Dict[str, Any] = Depends(require_platform_admin)):
    """Delete a plan. Blocked if any tenant is currently on this plan."""
    plan = await db.plans.find_one({"id": plan_id}, {"_id": 0, "id": 1, "name": 1})
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    tenant_count = await db.tenants.count_documents({"license.plan_id": plan_id})
    if tenant_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: {tenant_count} partner org(s) are on this plan. Mark it inactive instead.",
        )

    await db.plans.delete_one({"id": plan_id})
    await create_audit_log(
        entity_type="plan",
        entity_id=plan_id,
        action="deleted",
        actor=admin.get("email", "admin"),
        details={"name": plan.get("name")},
    )
    return {"message": "Plan deleted"}


@router.patch("/admin/plans/{plan_id}/status")
async def toggle_plan_status(plan_id: str, admin: Dict[str, Any] = Depends(require_platform_admin)):
    """Toggle a plan's active/inactive status."""
    plan = await db.plans.find_one({"id": plan_id}, {"_id": 0, "is_active": 1})
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    new_status = not bool(plan.get("is_active", True))
    await db.plans.update_one(
        {"id": plan_id},
        {"$set": {"is_active": new_status, "updated_at": now_iso()}},
    )
    await create_audit_log(
        entity_type="plan",
        entity_id=plan_id,
        action="deactivated" if not new_status else "activated",
        actor=admin.get("email", "admin"),
        details={},
    )
    return {"is_active": new_status}


# ---------------------------------------------------------------------------
# Plan audit logs
# ---------------------------------------------------------------------------

@router.get("/admin/plans/{plan_id}/logs")
async def get_plan_logs(
    plan_id: str,
    limit: int = 50,
    admin: Dict[str, Any] = Depends(require_platform_admin),
):
    """Get audit logs specific to this plan."""
    logs = await db.audit_logs.find(
        {"entity_type": "plan", "entity_id": plan_id},
        {"_id": 0},
    ).sort("created_at", -1).limit(limit).to_list(limit)
    return {"logs": logs}
