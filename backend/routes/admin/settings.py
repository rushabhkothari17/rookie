"""Admin: Settings routes."""
from __future__ import annotations

import base64
from typing import Any, Dict

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from core.security import require_admin
from core.tenant import tenant_id_of, DEFAULT_TENANT_ID
from db.session import db
from models import AppSettingsUpdate
from services.audit_service import AuditService, create_audit_log
from services.settings_service import SettingsService

router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/settings/public")
async def get_public_settings():
    settings = await db.app_settings.find_one({}, {"_id": 0})
    if not settings:
        return {"settings": {}}
    zoho_keys = [
        "zoho_reseller_signup_us", "zoho_reseller_signup_ca",
        "zoho_partner_tag_us", "zoho_partner_tag_ca",
        "zoho_access_instructions_url",
    ]
    branding_keys = ["website_url", "contact_email"]
    extra: Dict[str, Any] = {}
    for k in zoho_keys + branding_keys:
        extra[k] = await SettingsService.get(k, "")
    return {"settings": {
        "primary_color": settings.get("primary_color"),
        "secondary_color": settings.get("secondary_color"),
        "accent_color": settings.get("accent_color"),
        "logo_url": settings.get("logo_url"),
        "store_name": settings.get("store_name"),
        **extra,
    }}


@router.get("/admin/settings")
async def get_app_settings(admin: Dict[str, Any] = Depends(require_admin)):
    tid = tenant_id_of(admin)
    settings = await db.app_settings.find_one({"tenant_id": tid, "key": {"$exists": False}}, {"_id": 0})
    if not settings:
        return {"settings": {}}
    masked = {**settings}
    for key in ["resend_api_key"]:
        if masked.get(key) and not masked[key].startswith("••"):
            masked[key] = "••••••••" + masked[key][-4:]
    return {"settings": masked}


@router.put("/admin/settings")
async def update_app_settings(
    payload: AppSettingsUpdate,
    admin: Dict[str, Any] = Depends(require_admin),
):
    tid = tenant_id_of(admin)
    update = {k: v for k, v in payload.dict().items() if v is not None}
    for key in ["stripe_secret_key", "gocardless_token", "resend_api_key"]:
        if key in update and update[key].startswith("••"):
            del update[key]
    if not update:
        return {"message": "Nothing to update"}
    await db.app_settings.update_one({}, {"$set": update}, upsert=True)
    for k, v in update.items():
        await SettingsService.set(k, v, updated_by=admin.get("email", "admin"))
    await AuditService.log(
        action="SETTINGS_UPDATE",
        description=f"Admin updated settings: {list(update.keys())}",
        entity_type="Setting",
        actor_type="admin",
        actor_email=admin.get("email"),
        actor_role=admin.get("role"),
        source="admin_ui",
        after_json={k: "***" if "key" in k or "secret" in k or "token" in k else v for k, v in update.items()},
    )
    await create_audit_log(entity_type="setting", entity_id="app_settings", action="settings_updated", actor=admin.get("email", "admin"), details={"keys_changed": list(update.keys())})
    return {"message": "Settings updated"}


@router.get("/admin/settings/structured")
async def get_structured_settings(admin: Dict[str, Any] = Depends(require_admin)):
    items = await SettingsService.list_all(include_secrets=False)
    grouped: Dict[str, list] = {}
    for item in items:
        cat = item.get("category", "General")
        grouped.setdefault(cat, []).append(item)
    return {"settings": grouped}


@router.put("/admin/settings/key/{key}")
async def update_setting_by_key(
    key: str,
    payload: Dict[str, Any],
    admin: Dict[str, Any] = Depends(require_admin),
):
    value = payload.get("value")
    if value is None:
        raise HTTPException(status_code=400, detail="value is required")
    before_val = await SettingsService.get(key)
    await SettingsService.set(key, value, updated_by=admin.get("email", "admin"))
    is_secret = ("key" in key or "secret" in key or "token" in key or "password" in key)
    await AuditService.log(
        action="SETTINGS_KEY_UPDATE",
        description=f"Setting '{key}' updated by {admin.get('email', 'admin')}",
        entity_type="Setting",
        entity_id=key,
        actor_type="admin",
        actor_email=admin.get("email"),
        source="admin_ui",
        before_json={"value": "***" if is_secret else before_val},
        after_json={"value": "***" if is_secret else value},
    )
    await create_audit_log(entity_type="setting", entity_id=key, action="setting_key_updated", actor=admin.get("email", "admin"), details={"key": key, "is_secret": is_secret})
    return {"message": f"Setting '{key}' updated"}


@router.post("/admin/upload-logo")
async def upload_logo(
    file: UploadFile = File(...),
    admin: Dict[str, Any] = Depends(require_admin),
):
    contents = await file.read()
    b64 = base64.b64encode(contents).decode()
    content_type = file.content_type or "image/png"
    data_url = f"data:{content_type};base64,{b64}"
    await db.app_settings.update_one({}, {"$set": {"logo_url": data_url}}, upsert=True)
    await create_audit_log(entity_type="setting", entity_id="logo", action="logo_uploaded", actor=admin.get("email", "admin"), details={"file_name": file.filename, "content_type": content_type})
    return {"logo_url": data_url}
