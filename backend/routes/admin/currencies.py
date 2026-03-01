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

DEFAULT_PARTNER_TYPES = ["Reseller", "Direct", "Wholesale", "Agency", "Affiliate", "Other"]
DEFAULT_INDUSTRIES = [
    "Technology", "Finance", "Healthcare", "Retail", "Education",
    "Real Estate", "Manufacturing", "Professional Services", "Other",
]


async def _get_list_doc(key: str, defaults: list) -> Dict:
    doc = await db.platform_settings.find_one({"type": key}, {"_id": 0})
    if not doc:
        doc = {"type": key, "values": defaults, "updated_at": now_iso()}
        await db.platform_settings.insert_one({**doc})
    return doc


async def _get_list(key: str, defaults: list) -> List[str]:
    doc = await _get_list_doc(key, defaults)
    return doc.get("values", defaults)


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


# ─── Generic platform list helpers ───────────────────────────────────────────

class ListItemPayload(BaseModel):
    value: str


def _make_list_routes(slug: str, doc_key: str, defaults: list):
    """Factory: creates GET / POST / DELETE routes for a named platform list."""

    @router.get(f"/platform/{slug}")
    async def get_list_public(admin: Dict[str, Any] = Depends(get_tenant_admin)):
        return {"values": await _get_list(doc_key, defaults)}

    @router.get(f"/admin/platform/{slug}")
    async def get_list_admin(admin: Dict[str, Any] = Depends(require_platform_super_admin)):
        return {"values": await _get_list(doc_key, defaults)}

    @router.post(f"/admin/platform/{slug}")
    async def add_list_item(payload: ListItemPayload, admin: Dict[str, Any] = Depends(require_platform_super_admin)):
        val = payload.value.strip()
        if not val:
            raise HTTPException(400, "Value cannot be empty")
        values = await _get_list(doc_key, defaults)
        if val.lower() in [v.lower() for v in values]:
            raise HTTPException(409, f"'{val}' already exists")
        values.append(val)
        await db.platform_settings.update_one(
            {"type": doc_key},
            {"$set": {"values": values, "updated_at": now_iso()}},
            upsert=True,
        )
        return {"values": values}

    @router.delete(f"/admin/platform/{slug}/{{item}}")
    async def remove_list_item(item: str, admin: Dict[str, Any] = Depends(require_platform_super_admin)):
        item = item.strip()
        values = await _get_list(doc_key, defaults)
        new_vals = [v for v in values if v.lower() != item.lower()]
        if len(new_vals) == len(values):
            raise HTTPException(404, f"'{item}' not found")
        await db.platform_settings.update_one(
            {"type": doc_key},
            {"$set": {"values": new_vals, "updated_at": now_iso()}},
        )
        return {"values": new_vals}


_make_list_routes("partner-types", "partner_types", DEFAULT_PARTNER_TYPES)
_make_list_routes("industries", "industries", DEFAULT_INDUSTRIES)
