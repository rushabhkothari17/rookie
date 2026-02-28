"""Admin: manage partner plan-change / support submissions."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.helpers import now_iso
from core.tenant import get_tenant_admin, tenant_id_of, is_platform_admin
from db.session import db
from services.audit_service import create_audit_log

router = APIRouter(prefix="/api", tags=["admin-partner-submissions"])


@router.get("/admin/partner-submissions")
async def list_partner_submissions(
    status: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """List partner submissions. Platform admins see all; partner admins see own."""
    query: Dict[str, Any] = {}
    if not is_platform_admin(admin):
        tid = tenant_id_of(admin)
        query["partner_id"] = tid
    if status:
        query["status"] = status

    total = await db.partner_submissions.count_documents(query)
    skip = (page - 1) * per_page
    items = await db.partner_submissions.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(per_page).to_list(per_page)
    return {
        "submissions": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, (total + per_page - 1) // per_page),
    }


class SubmissionResolve(BaseModel):
    action: str  # "approve" | "reject"
    resolution_note: Optional[str] = None


@router.put("/admin/partner-submissions/{submission_id}")
async def resolve_partner_submission(
    submission_id: str,
    payload: SubmissionResolve,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """Approve or reject a partner submission. Only platform admins."""
    if not is_platform_admin(admin):
        raise HTTPException(status_code=403, detail="Only platform admins can resolve submissions")

    if payload.action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")

    sub = await db.partner_submissions.find_one({"id": submission_id}, {"_id": 0})
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if sub.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Submission is already resolved")

    now = now_iso()
    new_status = "approved" if payload.action == "approve" else "rejected"

    update: Dict[str, Any] = {
        "status": new_status,
        "resolved_at": now,
        "resolved_by": admin.get("email", "admin"),
        "resolution_note": payload.resolution_note or "",
    }

    # If approved downgrade — apply the plan change immediately
    if payload.action == "approve" and sub.get("type") == "plan_downgrade" and sub.get("requested_plan_id"):
        new_plan = await db.plans.find_one({"id": sub["requested_plan_id"]}, {"_id": 0})
        if new_plan:
            limits = {k: v for k, v in new_plan.items() if k.startswith("max_")}
            await db.tenants.update_one(
                {"id": sub["partner_id"]},
                {"$set": {
                    "license": {
                        "plan_id": new_plan["id"],
                        "plan_name": new_plan["name"],
                        "assigned_at": now,
                        **limits,
                    }
                }},
            )
            # Also update any active subscription plan reference
            await db.partner_subscriptions.update_many(
                {"partner_id": sub["partner_id"], "status": {"$in": ["active", "pending"]}},
                {"$set": {"plan_id": new_plan["id"], "plan_name": new_plan["name"], "amount": new_plan.get("monthly_price", 0), "updated_at": now}},
            )
            update["applied_plan_id"] = new_plan["id"]
            update["applied_plan_name"] = new_plan["name"]

    await db.partner_submissions.update_one({"id": submission_id}, {"$set": update})

    await create_audit_log(
        entity_type="partner_submission",
        entity_id=submission_id,
        action=f"submission_{new_status}",
        actor=admin.get("email", "admin"),
        details={
            "partner_id": sub.get("partner_id"),
            "type": sub.get("type"),
            "resolution_note": payload.resolution_note,
        },
    )

    return {"message": f"Submission {new_status}", "status": new_status}
