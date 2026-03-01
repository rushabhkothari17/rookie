"""Platform supported currencies — platform super admin only for writes; all auth users for reads."""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.helpers import now_iso
from core.tenant import require_platform_super_admin, get_tenant_admin
from db.session import db

router = APIRouter(prefix="/api", tags=["platform-currencies"])

DEFAULT_CURRENCIES = ["AUD", "CAD", "EUR", "GBP", "INR", "MXN", "USD"]
_DOC_KEY = "supported_currencies"


async def _get_doc() -> Dict:
    doc = await db.platform_settings.find_one({"type": _DOC_KEY}, {"_id": 0})
    if not doc:
        doc = {"type": _DOC_KEY, "currencies": DEFAULT_CURRENCIES, "updated_at": now_iso()}
        await db.platform_settings.insert_one({**doc})
    return doc


async def get_supported_currencies_list() -> List[str]:
    """Helper used by other modules to fetch the current list."""
    doc = await _get_doc()
    return sorted(doc.get("currencies", DEFAULT_CURRENCIES))


@router.get("/platform/supported-currencies")
async def public_get_currencies(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Return supported currencies — accessible to all authenticated users."""
    return {"currencies": await get_supported_currencies_list()}


@router.get("/admin/platform/currencies")
async def admin_get_currencies(admin: Dict[str, Any] = Depends(require_platform_super_admin)):
    return {"currencies": await get_supported_currencies_list()}


class AddCurrencyPayload(BaseModel):
    code: str


@router.post("/admin/platform/currencies")
async def add_currency(payload: AddCurrencyPayload, admin: Dict[str, Any] = Depends(require_platform_super_admin)):
    code = payload.code.strip().upper()
    if len(code) != 3 or not code.isalpha():
        raise HTTPException(status_code=400, detail="Currency code must be 3 letters (ISO 4217)")
    currencies = await get_supported_currencies_list()
    if code in currencies:
        raise HTTPException(status_code=409, detail="Currency already in the list")
    currencies.append(code)
    currencies = sorted(currencies)
    await db.platform_settings.update_one(
        {"type": _DOC_KEY},
        {"$set": {"currencies": currencies, "updated_at": now_iso()}},
        upsert=True,
    )
    return {"currencies": currencies}


@router.delete("/admin/platform/currencies/{code}")
async def remove_currency(code: str, admin: Dict[str, Any] = Depends(require_platform_super_admin)):
    code = code.strip().upper()
    currencies = await get_supported_currencies_list()
    if code not in currencies:
        raise HTTPException(status_code=404, detail="Currency not found")
    currencies = sorted(c for c in currencies if c != code)
    await db.platform_settings.update_one(
        {"type": _DOC_KEY},
        {"$set": {"currencies": currencies, "updated_at": now_iso()}},
    )
    return {"currencies": currencies}
