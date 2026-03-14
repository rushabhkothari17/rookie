"""Admin: Plans management — platform super admin only.

Plans define reusable license templates.
Updating a plan automatically propagates limits to all tenants on that plan.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.helpers import make_id, now_iso
from core.tenant import require_platform_admin, require_platform_super_admin
from db.session import db
from services.audit_service import create_audit_log
from services.zoho_service import auto_sync_to_zoho_crm

router = APIRouter(prefix="/api", tags=["admin-plans"])

LIMIT_FIELDS = [
    "max_users", "max_storage_mb", "max_user_roles",
    "max_product_categories", "max_product_terms", "max_enquiries",
    "max_resources", "max_templates", "max_email_templates",
    "max_categories", "max_forms", "max_references",
    "max_orders_per_month", "max_customers_per_month", "max_subscriptions_per_month",
]


class VisibilityRule(BaseModel):
    field: str    # country, partner_code, base_currency, name
    operator: str  # equals, not_equals, in, contains
    value: str


class PlanCreate(BaseModel):
    name: str = Field(max_length=100)
    description: Optional[str] = Field(None, max_length=5_000)
    warning_threshold_pct: int = 80
    is_public: bool = False  # visible to partners for self-service upgrade
    visibility_rules: Optional[List[VisibilityRule]] = None  # evaluated when is_public=False
    monthly_price: Optional[float] = None
    currency: Optional[str] = None
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
        "is_public": payload.is_public,
        "visibility_rules": [r.dict() for r in (payload.visibility_rules or [])],
        "is_default": False,
        "warning_threshold_pct": payload.warning_threshold_pct,
        "monthly_price": payload.monthly_price,
        "currency": payload.currency or "GBP",
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
    import asyncio as _asyncio
    _asyncio.ensure_future(auto_sync_to_zoho_crm("platform", "plans", plan_doc, "create"))
    return {"plan": plan_doc}


@router.get("/partner/plans/public")
async def list_public_plans():
    """Return all active public plans — accessible by partner admins for self-service upgrade."""
    plans = await db.plans.find(
        {"is_active": True, "is_public": True},
        {"_id": 0},
    ).sort("created_at", 1).to_list(100)
    return {"plans": plans}


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
async def update_plan(plan_id: str, payload: PlanUpdate, admin: Dict[str, Any] = Depends(require_platform_admin)):
    plan = await db.plans.find_one({"id": plan_id}, {"_id": 0})
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan.get("is_readonly"):
        raise HTTPException(status_code=403, detail="This is the default Free Plan and cannot be edited. Mark it as public to show it to partners.")

    updates = payload.dict(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    updates["updated_at"] = now_iso()
    await db.plans.update_one({"id": plan_id}, {"$set": updates})
    updated_plan = await db.plans.find_one({"id": plan_id}, {"_id": 0})
    updated_plan.pop("_id", None)

    tenant_limit_updates = {f: updated_plan.get(f) for f in LIMIT_FIELDS}
    tenant_limit_updates["warning_threshold_pct"] = updated_plan.get("warning_threshold_pct", 80)
    tenant_limit_updates["plan"] = updated_plan.get("name")
    result = await db.tenants.update_many(
        {"license.plan_id": plan_id},
        {"$set": {**{f"license.{k}": v for k, v in tenant_limit_updates.items()}, "updated_at": now_iso()}},
    )
    await create_audit_log(entity_type="plan", entity_id=plan_id, action="updated",
                           actor=admin.get("email", "admin"),
                           details={"changes": {k: v for k, v in updates.items() if k != "updated_at"},
                                    "tenants_propagated": result.modified_count})
    return {"plan": updated_plan, "tenants_propagated": result.modified_count}


@router.delete("/admin/plans/{plan_id}")
async def delete_plan(plan_id: str, admin: Dict[str, Any] = Depends(require_platform_super_admin)):
    plan = await db.plans.find_one({"id": plan_id}, {"_id": 0, "id": 1, "name": 1, "is_readonly": 1, "is_default": 1})
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan.get("is_readonly") or plan.get("is_default"):
        raise HTTPException(status_code=403, detail="The default Free Plan cannot be deleted.")
    tenant_count = await db.tenants.count_documents({"license.plan_id": plan_id})
    if tenant_count > 0:
        raise HTTPException(status_code=409, detail=f"Cannot delete: {tenant_count} partner org(s) are on this plan.")
    await db.plans.delete_one({"id": plan_id})
    await create_audit_log(entity_type="plan", entity_id=plan_id, action="deleted",
                           actor=admin.get("email", "admin"), details={"name": plan.get("name")})
    return {"message": "Plan deleted"}


@router.patch("/admin/plans/{plan_id}/set-default")
async def set_default_plan(plan_id: str, admin: Dict[str, Any] = Depends(require_platform_admin)):
    """Designate a plan as the system default (Free) plan. Only one can be default at a time."""
    plan = await db.plans.find_one({"id": plan_id}, {"_id": 0, "id": 1})
    if not plan:
        raise HTTPException(404, "Plan not found")
    # Unset previous default
    await db.plans.update_many({"is_default": True}, {"$set": {"is_default": False, "is_readonly": False}})
    # Set new default
    await db.plans.update_one({"id": plan_id}, {"$set": {"is_default": True, "is_readonly": True, "is_active": True}})
    await create_audit_log(entity_type="plan", entity_id=plan_id, action="set_default",
                           actor=admin.get("email", "admin"), details={})
    return {"message": "Default plan updated"}


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
