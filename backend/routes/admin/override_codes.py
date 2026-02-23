"""Admin: Override codes routes."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.helpers import make_id, now_iso
from core.security import require_admin
from core.tenant import get_tenant_filter, set_tenant_id, tenant_id_of
from db.session import db
from models import OverrideCodeCreate, OverrideCodeUpdate
from services.audit_service import create_audit_log
from services.settings_service import SettingsService

router = APIRouter(prefix="/api", tags=["admin-override-codes"])


@router.get("/admin/override-codes")
async def list_override_codes(
    page: int = 1,
    per_page: int = 20,
    status: Optional[str] = None,
    customer_id: Optional[str] = None,
    customer_email: Optional[str] = None,
    created_from: Optional[str] = None,
    created_to: Optional[str] = None,
    expires_from: Optional[str] = None,
    expires_to: Optional[str] = None,
    admin: Dict[str, Any] = Depends(require_admin),
):
    query: Dict[str, Any] = {}
    if customer_id:
        query["customer_id"] = customer_id
    if created_from:
        query.setdefault("created_at", {})["$gte"] = created_from
    if created_to:
        query.setdefault("created_at", {})["$lte"] = created_to + "T23:59:59"
    if expires_from:
        query.setdefault("expires_at", {})["$gte"] = expires_from
    if expires_to:
        query.setdefault("expires_at", {})["$lte"] = expires_to + "T23:59:59"

    codes = await db.override_codes.find(query, {"_id": 0}).sort("created_at", -1).to_list(10000)
    now = datetime.now(timezone.utc)

    customer_ids_all = list({r["customer_id"] for r in codes if r.get("customer_id")})
    customers_map = {
        c["id"]: c
        for c in await db.customers.find({"id": {"$in": customer_ids_all}}, {"_id": 0, "id": 1, "user_id": 1}).to_list(5000)
    }
    user_ids = list({c.get("user_id", "") for c in customers_map.values()})
    users_map = {
        u["id"]: u
        for u in await db.users.find({"id": {"$in": user_ids}}, {"_id": 0, "id": 1, "email": 1, "full_name": 1}).to_list(5000)
    }

    results = []
    for oc in codes:
        cid = oc.get("customer_id", "")
        cust = customers_map.get(cid, {})
        user = users_map.get(cust.get("user_id", ""), {})
        effective_status = oc.get("status", "active")
        expires_at = oc.get("expires_at")
        if effective_status == "active" and expires_at:
            try:
                exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                if now > exp_dt:
                    effective_status = "expired"
            except Exception:
                pass
        results.append({
            **oc,
            "effective_status": effective_status,
            "customer_email": user.get("email", ""),
            "customer_name": user.get("full_name", ""),
        })

    if status:
        results = [r for r in results if r["effective_status"] == status]
    if customer_email:
        results = [r for r in results if customer_email.lower() in r["customer_email"].lower()]

    total = len(results)
    skip = (page - 1) * per_page
    return {
        "override_codes": results[skip: skip + per_page],
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": max(1, (total + per_page - 1) // per_page),
    }


@router.post("/admin/override-codes")
async def create_override_code(
    payload: OverrideCodeCreate,
    admin: Dict[str, Any] = Depends(require_admin),
):
    existing = await db.override_codes.find_one({"code": payload.code.strip()}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="An override code with this value already exists.")

    customer = await db.customers.find_one({"id": payload.customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    code_id = make_id()
    created_at = now_iso()
    expiry_hours = int(await SettingsService.get("override_code_expiry_hours", 48))
    expires_at = payload.expires_at or (datetime.now(timezone.utc) + timedelta(hours=expiry_hours)).isoformat()

    await db.override_codes.insert_one({
        "id": code_id,
        "code": payload.code.strip(),
        "customer_id": payload.customer_id,
        "status": "active",
        "created_at": created_at,
        "expires_at": expires_at,
        "used_at": None,
        "used_for_order_id": None,
        "created_by": admin["id"],
    })
    await create_audit_log(
        entity_type="override_code",
        entity_id=code_id,
        action="created",
        actor=f"admin:{admin['id']}",
        details={"code": payload.code.strip(), "customer_id": payload.customer_id, "expires_at": expires_at},
    )
    return {"message": "Override code created", "id": code_id}


@router.put("/admin/override-codes/{code_id}")
async def update_override_code(
    code_id: str,
    payload: OverrideCodeUpdate,
    admin: Dict[str, Any] = Depends(require_admin),
):
    oc = await db.override_codes.find_one({"id": code_id}, {"_id": 0})
    if not oc:
        raise HTTPException(status_code=404, detail="Override code not found")

    updates: Dict[str, Any] = {}

    if payload.code is not None:
        new_code = payload.code.strip()
        if new_code != oc["code"]:
            dup = await db.override_codes.find_one({"code": new_code, "id": {"$ne": code_id}}, {"_id": 0})
            if dup:
                raise HTTPException(status_code=400, detail="An override code with this value already exists.")
        updates["code"] = new_code

    if payload.customer_id is not None:
        cust = await db.customers.find_one({"id": payload.customer_id}, {"_id": 0})
        if not cust:
            raise HTTPException(status_code=404, detail="Customer not found")
        updates["customer_id"] = payload.customer_id

    if payload.status is not None:
        if payload.status not in ["active", "inactive"]:
            raise HTTPException(status_code=400, detail="Status must be 'active' or 'inactive'")
        updates["status"] = payload.status

    if payload.expires_at is not None:
        updates["expires_at"] = payload.expires_at

    if updates:
        await db.override_codes.update_one({"id": code_id}, {"$set": updates})
        await create_audit_log(
            entity_type="override_code",
            entity_id=code_id,
            action="updated",
            actor=f"admin:{admin['id']}",
            details={"updates": updates},
        )

    oc.update(updates)
    oc.pop("_id", None)
    return {"message": "Override code updated", "override_code": oc}


@router.delete("/admin/override-codes/{code_id}")
async def deactivate_override_code(
    code_id: str,
    admin: Dict[str, Any] = Depends(require_admin),
):
    oc = await db.override_codes.find_one({"id": code_id}, {"_id": 0})
    if not oc:
        raise HTTPException(status_code=404, detail="Override code not found")
    await db.override_codes.update_one({"id": code_id}, {"$set": {"status": "inactive"}})
    await create_audit_log(
        entity_type="override_code",
        entity_id=code_id,
        action="deactivated",
        actor=f"admin:{admin['id']}",
        details={},
    )
    return {"message": "Override code deactivated"}


@router.get("/admin/override-codes/{code_id}/logs")
async def get_override_code_logs(code_id: str, admin: Dict[str, Any] = Depends(require_admin)):
    logs = await db.audit_logs.find({"entity_type": "override_code", "entity_id": code_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"logs": logs}

