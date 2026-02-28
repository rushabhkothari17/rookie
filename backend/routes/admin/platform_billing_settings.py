"""Platform-level billing and scheduler configuration."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.helpers import now_iso
from core.tenant import get_tenant_admin, is_platform_admin
from db.session import db

router = APIRouter(prefix="/api", tags=["admin-platform-billing"])

SETTINGS_ID = "platform_billing_settings"
DEFAULTS: Dict[str, Any] = {
    "overdue_grace_days": 7,
    "overdue_warning_days": 3,
}


async def _get_settings() -> Dict[str, Any]:
    doc = await db.platform_settings.find_one({"id": SETTINGS_ID}, {"_id": 0})
    return {**DEFAULTS, **(doc or {})}


@router.get("/admin/platform-billing-settings")
async def get_billing_settings(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    if not is_platform_admin(admin):
        raise HTTPException(status_code=403, detail="Platform admins only")
    return await _get_settings()


class BillingSettingsUpdate(BaseModel):
    overdue_grace_days: Optional[int] = None
    overdue_warning_days: Optional[int] = None


@router.put("/admin/platform-billing-settings")
async def update_billing_settings(
    payload: BillingSettingsUpdate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    if not is_platform_admin(admin):
        raise HTTPException(status_code=403, detail="Platform admins only")

    current = await _get_settings()
    if payload.overdue_grace_days is not None:
        if payload.overdue_grace_days < 1:
            raise HTTPException(status_code=400, detail="overdue_grace_days must be >= 1")
        current["overdue_grace_days"] = payload.overdue_grace_days
    if payload.overdue_warning_days is not None:
        if payload.overdue_warning_days < 0:
            raise HTTPException(status_code=400, detail="overdue_warning_days must be >= 0")
        current["overdue_warning_days"] = payload.overdue_warning_days

    current["id"] = SETTINGS_ID
    current["updated_at"] = now_iso()
    await db.platform_settings.replace_one(
        {"id": SETTINGS_ID}, current, upsert=True
    )
    current.pop("_id", None)
    return current
