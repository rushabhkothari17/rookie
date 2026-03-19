"""Coupons — for ongoing plan upgrades and one-time limit upgrades."""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from core.helpers import make_id, now_iso
from core.tenant import require_platform_admin, require_platform_super_admin, get_tenant_admin, tenant_id_of
from db.session import db
from services.audit_service import create_audit_log

router = APIRouter(prefix="/api", tags=["coupons"])


class CouponCreate(BaseModel):
    code: str
    internal_note: Optional[str] = None
    discount_type: str  # "percentage" | "fixed_amount"
    discount_value: float
    expiry_date: Optional[str] = None
    is_single_use: bool = False
    applies_to: str = "both"  # "ongoing" | "one_time" | "both"
    applicable_plan_ids: Optional[List[str]] = None  # None = all plans
    is_one_time_per_org: bool = True
    is_active: bool = True


class CouponUpdate(BaseModel):
    internal_note: Optional[str] = None
    discount_type: Optional[str] = None
    discount_value: Optional[float] = None
    expiry_date: Optional[str] = None
    is_single_use: Optional[bool] = None
    applies_to: Optional[str] = None
    applicable_plan_ids: Optional[List[str]] = None
    is_one_time_per_org: Optional[bool] = None
    is_active: Optional[bool] = None


class CouponValidate(BaseModel):
    code: str
    upgrade_type: str  # "ongoing" | "one_time"
    plan_id: Optional[str] = None
    base_amount: float


# ── Admin CRUD ──────────────────────────────────────────────────────────────

@router.get("/admin/coupons")
async def list_coupons(admin: Dict[str, Any] = Depends(require_platform_admin)):
    coupons = await db.coupons.find({}, {"_id": 0, "used_by_orgs": 0}).sort("created_at", -1).to_list(200)
    return {"coupons": coupons}


@router.post("/admin/coupons")
async def create_coupon(body: CouponCreate, admin: Dict[str, Any] = Depends(require_platform_super_admin)):
    code = body.code.upper().strip()
    if await db.coupons.find_one({"code": code}):
        raise HTTPException(409, "A coupon with this code already exists")
    if body.discount_type not in ("percentage", "fixed_amount"):
        raise HTTPException(400, "discount_type must be 'percentage' or 'fixed_amount'")
    if body.applies_to not in ("ongoing", "one_time", "both"):
        raise HTTPException(400, "applies_to must be 'ongoing', 'one_time', or 'both'")
    # Validate that any referenced plan IDs actually exist
    if body.applicable_plan_ids:
        found_ids = {p["id"] for p in await db.plans.find({"id": {"$in": body.applicable_plan_ids}}, {"_id": 0, "id": 1}).to_list(100)}
        invalid = [pid for pid in body.applicable_plan_ids if pid not in found_ids]
        if invalid:
            raise HTTPException(400, f"Plan(s) not found: {', '.join(invalid[:3])}")
    doc = {
        "id": make_id(), "code": code,
        "internal_note": body.internal_note or "",
        "discount_type": body.discount_type, "discount_value": body.discount_value,
        "expiry_date": body.expiry_date, "is_single_use": body.is_single_use,
        "applies_to": body.applies_to,
        "applicable_plan_ids": body.applicable_plan_ids,
        "is_one_time_per_org": body.is_one_time_per_org,
        "is_active": body.is_active,
        "usage_count": 0, "used_by_orgs": [],
        "created_at": now_iso(), "updated_at": now_iso(),
        "created_by": admin.get("email"),
    }
    await db.coupons.insert_one(doc)
    doc.pop("_id", None)
    doc.pop("used_by_orgs", None)
    await create_audit_log(entity_type="coupon", entity_id=doc["id"], action="created",
                           actor=admin.get("email", "admin"), details={"code": code})
    return doc


@router.put("/admin/coupons/{coupon_id}")
async def update_coupon(coupon_id: str, body: CouponUpdate, admin: Dict[str, Any] = Depends(require_platform_super_admin)):
    coupon = await db.coupons.find_one({"id": coupon_id}, {"_id": 0})
    if not coupon:
        raise HTTPException(404, "Coupon not found")
    updates = {k: v for k, v in body.dict(exclude_unset=True).items()}
    # Validate plan IDs if being updated
    if "applicable_plan_ids" in updates and updates["applicable_plan_ids"]:
        found_ids = {p["id"] for p in await db.plans.find({"id": {"$in": updates["applicable_plan_ids"]}}, {"_id": 0, "id": 1}).to_list(100)}
        invalid = [pid for pid in updates["applicable_plan_ids"] if pid not in found_ids]
        if invalid:
            raise HTTPException(400, f"Plan(s) not found: {', '.join(invalid[:3])}")
    if "code" in updates:
        updates["code"] = updates["code"].upper().strip()
    updates["updated_at"] = now_iso()
    await db.coupons.update_one({"id": coupon_id}, {"$set": updates})
    await create_audit_log(entity_type="coupon", entity_id=coupon_id, action="updated",
                           actor=admin.get("email", "admin"), details=updates)
    return {**{k: v for k, v in coupon.items() if k != "used_by_orgs"}, **updates}


@router.delete("/admin/coupons/{coupon_id}")
async def delete_coupon(coupon_id: str, admin: Dict[str, Any] = Depends(require_platform_super_admin)):
    if not await db.coupons.find_one({"id": coupon_id}):
        raise HTTPException(404, "Coupon not found")
    coupon_doc = await db.coupons.find_one({"id": coupon_id}, {"_id": 0, "code": 1})
    await db.coupons.delete_one({"id": coupon_id})
    await create_audit_log(entity_type="coupon", entity_id=coupon_id, action="deleted",
                           actor=admin.get("email", "admin"), details={"code": (coupon_doc or {}).get("code", "")})
    return {"message": "Deleted"}


@router.get("/admin/coupons/{coupon_id}/logs")
async def get_coupon_logs(coupon_id: str, page: int = 1, limit: int = 20,
                          admin: Dict[str, Any] = Depends(require_platform_admin)):
    flt = {"entity_type": "coupon", "entity_id": coupon_id}
    total = await db.audit_logs.count_documents(flt)
    logs = await db.audit_logs.find(flt, {"_id": 0}).sort("timestamp", -1).skip((page - 1) * limit).limit(limit).to_list(limit)
    return {"logs": logs, "total": total}


# ── Admin Usage Report ───────────────────────────────────────────────────────

@router.get("/admin/coupon-report")
async def get_coupon_report(
    coupon_code: Optional[str] = None,
    admin: Dict[str, Any] = Depends(require_platform_admin),
):
    """Return a full report of every coupon redemption across all partners."""
    query: Dict[str, Any] = {"coupon_id": {"$nin": [None, ""]}}
    if coupon_code:
        # Filter by coupon code — look up the coupon id first
        c = await db.coupons.find_one({"code": coupon_code.upper().strip()}, {"_id": 0, "id": 1})
        if c:
            query["coupon_id"] = c["id"]
        else:
            return {"rows": [], "summary": {"total_redemptions": 0, "total_discount_given": 0.0, "total_revenue_from_couponed_orders": 0.0, "coupons_used": 0}}

    orders = await db.partner_orders.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)

    # Build coupon lookup map
    coupon_ids = list({o["coupon_id"] for o in orders if o.get("coupon_id")})
    coupons_docs = await db.coupons.find({"id": {"$in": coupon_ids}}, {"_id": 0}).to_list(200)
    coupon_map = {c["id"]: c for c in coupons_docs}

    rows = []
    for order in orders:
        coupon = coupon_map.get(order.get("coupon_id"), {})
        base_amount = float(order.get("base_amount") or order.get("amount") or 0)
        final_amount = float(order.get("amount") or 0)
        discount_amount = float(order.get("discount_amount") or max(0.0, base_amount - final_amount))
        rows.append({
            "order_id": order.get("id", ""),
            "order_number": order.get("order_number", ""),
            "coupon_id": order.get("coupon_id", ""),
            "coupon_code": coupon.get("code") or order.get("coupon_code", ""),
            "discount_type": coupon.get("discount_type", ""),
            "discount_value": coupon.get("discount_value", 0),
            "partner_id": order.get("partner_id", ""),
            "partner_name": order.get("partner_name", ""),
            "upgrade_type": order.get("order_type", ""),
            "base_amount": round(base_amount, 2),
            "discount_amount": round(discount_amount, 2),
            "final_amount": round(final_amount, 2),
            "currency": order.get("currency", "GBP"),
            "status": order.get("status", ""),
            "used_at": order.get("created_at", ""),
        })

    unique_coupons = len({r["coupon_code"] for r in rows if r["coupon_code"]})
    total_discount = sum(r["discount_amount"] for r in rows)
    total_revenue = sum(r["final_amount"] for r in rows if r["status"] == "paid")

    return {
        "rows": rows,
        "summary": {
            "total_redemptions": len(rows),
            "total_discount_given": round(total_discount, 2),
            "total_revenue_from_couponed_orders": round(total_revenue, 2),
            "coupons_used": unique_coupons,
        },
    }


# ── Partner-facing validation ───────────────────────────────────────────────

@router.post("/partner/coupons/validate")
async def validate_coupon(body: CouponValidate, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tid = tenant_id_of(admin)
    code = body.code.upper().strip()

    coupon = await db.coupons.find_one({"code": code, "is_active": True}, {"_id": 0})
    if not coupon:
        raise HTTPException(400, "Invalid or inactive coupon code")

    today = now_iso()[:10]
    if coupon.get("expiry_date") and coupon["expiry_date"] < today:
        raise HTTPException(400, "This coupon has expired")

    if coupon["applies_to"] != "both" and coupon["applies_to"] != body.upgrade_type:
        raise HTTPException(400, f"This coupon only applies to {'ongoing plan upgrades' if coupon['applies_to'] == 'ongoing' else 'one-time limit upgrades'}")

    if body.upgrade_type == "ongoing" and body.plan_id:
        applicable = coupon.get("applicable_plan_ids")
        if applicable and body.plan_id not in applicable:
            raise HTTPException(400, "This coupon is not applicable to the selected plan")

    if coupon.get("is_single_use") and coupon.get("usage_count", 0) >= 1:
        raise HTTPException(400, "This coupon has already been used")

    if coupon.get("is_one_time_per_org") and tid in (coupon.get("used_by_orgs") or []):
        raise HTTPException(400, "Your organisation has already used this coupon")

    if coupon["discount_type"] == "percentage":
        discount = round(body.base_amount * coupon["discount_value"] / 100, 2)
    else:
        discount = min(float(coupon["discount_value"]), body.base_amount)

    return {
        "valid": True,
        "coupon_id": coupon["id"],
        "code": coupon["code"],
        "discount_type": coupon["discount_type"],
        "discount_value": coupon["discount_value"],
        "discount_amount": discount,
        "final_amount": round(max(0, body.base_amount - discount), 2),
    }
