"""
DB-backed Settings service with in-memory cache and TTL.

Settings are grouped by category and stored in the `app_settings` MongoDB collection.
Secret settings are masked in UI responses.

Seed call in startup ensures all defaults are pre-populated on first run.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from core.helpers import make_id, now_iso
from db.session import db

# ---------------------------------------------------------------------------
# Default settings catalogue
# ---------------------------------------------------------------------------

SETTINGS_DEFAULTS: List[Dict[str, Any]] = [
    # ---- Payments ----
    {
        "key": "service_fee_rate",
        "value_json": 0.05,
        "value_type": "number",
        "category": "Payments",
        "description": "Percentage service fee applied to all orders (0.05 = 5%).",
        "is_secret": False,
    },
    # ---- Operations ----
    {
        "key": "override_code_expiry_hours",
        "value_json": 48,
        "value_type": "number",
        "category": "Operations",
        "description": "Default expiry in hours for newly generated override codes.",
        "is_secret": False,
    },
    # ---- Email ----
    {
        "key": "resend_api_key",
        "value_json": "",
        "value_type": "secret",
        "category": "Email",
        "description": "Resend API key for transactional email.",
        "is_secret": True,
    },
    {
        "key": "resend_sender_email",
        "value_json": "noreply@automateaccounts.com",
        "value_type": "string",
        "category": "Email",
        "description": "From address used for all outgoing emails.",
        "is_secret": False,
    },
    {
        "key": "admin_notification_email",
        "value_json": "rushabh@automateaccounts.com",
        "value_type": "string",
        "category": "Email",
        "description": "Email address that receives admin notifications (quote requests, etc.).",
        "is_secret": False,
    },
    # ---- Zoho ----
    {
        "key": "zoho_reseller_signup_us",
        "value_json": "https://store.zoho.com/ResellerCustomerSignUp.do?id=0752790261568b40e0d2ffef44a3f4e428bbcca5aa8fba3305f9e276702456a3",
        "value_type": "string",
        "category": "Zoho",
        "description": "Zoho Reseller Customer Signup link shown at checkout (US data center).",
        "is_secret": False,
    },
    {
        "key": "zoho_reseller_signup_ca",
        "value_json": "https://store.zohocloud.ca/ResellerCustomerSignUp.do?id=341bc9b2ab087c30e176e7c0385e3caaa331989c27aa00d0f3a0521dfb926960",
        "value_type": "string",
        "category": "Zoho",
        "description": "Zoho Reseller Customer Signup link shown at checkout (Canada data center).",
        "is_secret": False,
    },
    {
        "key": "zoho_partner_tag_us",
        "value_json": "https://store.zoho.com/html/store/tagyourpartner.html?partnerid=zkms01370000000123731ce9bbb964daefb3ac6c1ff255b5fa6f",
        "value_type": "string",
        "category": "Zoho",
        "description": "Partner tagging link shown at checkout (US data center).",
        "is_secret": False,
    },
    {
        "key": "zoho_partner_tag_ca",
        "value_json": "https://store.zohocloud.ca/html/store/tagyourpartner.html?partnerid=zkms0135000000008003432a39b432f137718e6225e74e34fc66",
        "value_type": "string",
        "category": "Zoho",
        "description": "Partner tagging link shown at checkout (Canada data center).",
        "is_secret": False,
    },
    {
        "key": "zoho_access_instructions_url",
        "value_json": "https://www.automateaccounts.com",
        "value_type": "string",
        "category": "Zoho",
        "description": "URL explaining how customers should provide Zoho account access.",
        "is_secret": False,
    },
    # ---- Branding ----
    {
        "key": "website_url",
        "value_json": "https://www.automateaccounts.com",
        "value_type": "string",
        "category": "Branding",
        "description": "Main website URL used in storefront links.",
        "is_secret": False,
    },
    {
        "key": "contact_email",
        "value_json": "hello@automateaccounts.com",
        "value_type": "string",
        "category": "Branding",
        "description": "Contact / sales email shown on product inquiry pages.",
        "is_secret": False,
    },
    # ---- Feature Flags ----
    {
        "key": "partner_tagging_enabled",
        "value_json": True,
        "value_type": "bool",
        "category": "FeatureFlags",
        "description": "Require Zoho partner tagging step at checkout.",
        "is_secret": False,
    },
]

# Keys that existed in earlier versions and are now obsolete / managed elsewhere
_OBSOLETE_KEYS = [
    "stripe_publishable_key", "stripe_secret_key", "stripe_webhook_secret",
    "gocardless_access_token", "gocardless_environment",
    "logo_url",  # managed by legacy flat app_settings document
    "zoho_partner_link_aus", "zoho_partner_link_nz", "zoho_partner_link_global",
]


# ---------------------------------------------------------------------------
# In-memory cache
# ---------------------------------------------------------------------------

_cache: Dict[str, Any] = {}
_cache_ts: float = 0.0
_CACHE_TTL = 60  # seconds


def _cache_expired() -> bool:
    return (time.time() - _cache_ts) > _CACHE_TTL


# ---------------------------------------------------------------------------
# SettingsService
# ---------------------------------------------------------------------------

class SettingsService:
    """Central settings accessor. Always prefer this over direct DB reads."""

    @staticmethod
    async def seed() -> None:
        """On startup: insert any missing settings with default values."""
        for s in SETTINGS_DEFAULTS:
            existing = await db.app_settings.find_one({"key": s["key"]})
            if not existing:
                await db.app_settings.insert_one({
                    "id": make_id(),
                    "key": s["key"],
                    "value_json": s["value_json"],
                    "value_type": s["value_type"],
                    "category": s["category"],
                    "description": s["description"],
                    "is_secret": s["is_secret"],
                    "updated_at": now_iso(),
                    "updated_by": "system_seed",
                })

    @staticmethod
    async def _load_all() -> Dict[str, Any]:
        global _cache, _cache_ts
        if not _cache_expired():
            return _cache
        docs = await db.app_settings.find({}, {"_id": 0}).to_list(500)
        _cache = {d["key"]: d["value_json"] for d in docs if "key" in d}
        _cache_ts = time.time()
        return _cache

    @staticmethod
    async def get(key: str, default: Any = None) -> Any:
        cache = await SettingsService._load_all()
        return cache.get(key, default)

    @staticmethod
    async def set(key: str, value: Any, updated_by: str = "admin") -> None:
        global _cache_ts  # invalidate cache
        _cache_ts = 0.0
        await db.app_settings.update_one(
            {"key": key},
            {"$set": {"value_json": value, "updated_at": now_iso(), "updated_by": updated_by}},
            upsert=True,
        )

    @staticmethod
    async def list_all(include_secrets: bool = False) -> List[Dict[str, Any]]:
        """Return all settings. Mask secrets unless include_secrets=True."""
        docs = await db.app_settings.find({}, {"_id": 0}).sort("category", 1).to_list(500)
        # Only include structured setting documents (must have a non-empty key)
        result = []
        for d in docs:
            if not d.get("key"):
                continue
            entry: Dict[str, Any] = {
                "id": d.get("id", ""),
                "key": d.get("key", ""),
                "value_json": d.get("value_json"),
                "value_type": d.get("value_type", "string"),
                "category": d.get("category", "General"),
                "description": d.get("description", ""),
                "is_secret": d.get("is_secret", False),
                "updated_at": d.get("updated_at"),
                "updated_by": d.get("updated_by"),
            }
            if entry["is_secret"] and not include_secrets:
                entry["value_json"] = "••••••••"
            result.append(entry)
        return result
