"""Admin: Website content settings routes."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from core.security import require_admin
from db.session import db
from models import WebsiteSettingsUpdate
from services.audit_service import create_audit_log

router = APIRouter(prefix="/api", tags=["website-settings"])

DEFAULT_WEBSITE_SETTINGS: Dict[str, Any] = {
    "hero_label": "AUTOMATE ACCOUNTS STOREFRONT",
    "hero_title": "One Partner, One Roadmap — We've Got Zoho Covered",
    "hero_subtitle": "All-in-one Zoho partner for setup, customization, migrations, training and ongoing support.",
    "login_title": "Welcome back",
    "login_subtitle": "Sign in to unlock the store.",
    "login_portal_label": "Customer Portal",
    "register_title": "Create your portal access",
    "register_subtitle": "We'll use this info to configure pricing and currency.",
    "contact_email": "",
    "contact_phone": "",
    "contact_address": "",
    "footer_tagline": "",
    "quote_form_title": "Request a Quote",
    "quote_form_subtitle": "Fill in your details and we'll get back to you with a custom quote.",
    "quote_form_response_time": "We'll respond within 1-2 business days.",
    "scope_form_title": "Request Scope",
    "scope_form_subtitle": "Tell us about your project and we'll get back to you with a detailed scope, timeline, and quote.",
}


@router.get("/website-settings")
async def get_website_settings_public():
    """Public endpoint — returns all website content + branding."""
    app_s = await db.app_settings.find_one({}, {"_id": 0}) or {}
    web_s = await db.website_settings.find_one({}, {"_id": 0}) or {}
    return {
        "settings": {
            **DEFAULT_WEBSITE_SETTINGS,
            # Branding (from app_settings)
            "store_name": app_s.get("store_name", ""),
            "logo_url": app_s.get("logo_url") or "",
            "primary_color": app_s.get("primary_color") or "",
            "accent_color": app_s.get("accent_color") or "",
            # Content overrides (from website_settings)
            **{k: v for k, v in web_s.items() if v is not None and k != "_id"},
        }
    }


@router.get("/admin/website-settings")
async def get_website_settings_admin(admin: Dict[str, Any] = Depends(require_admin)):
    web_s = await db.website_settings.find_one({}, {"_id": 0}) or {}
    return {"settings": {**DEFAULT_WEBSITE_SETTINGS, **web_s}}


@router.put("/admin/website-settings")
async def update_website_settings(
    payload: WebsiteSettingsUpdate,
    admin: Dict[str, Any] = Depends(require_admin),
):
    update = {k: v for k, v in payload.dict().items() if v is not None}
    if not update:
        return {"message": "Nothing to update"}
    await db.website_settings.update_one({}, {"$set": update}, upsert=True)
    await create_audit_log(
        entity_type="website_settings",
        entity_id="website",
        action="updated",
        actor=admin.get("email", "admin"),
        details={"keys_changed": list(update.keys())},
    )
    return {"message": "Website settings updated"}
