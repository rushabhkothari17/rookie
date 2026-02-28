from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime, timedelta
import os
import logging

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "")

# ---------------------------------------------------------------------------
# Infrastructure imports from modules
# ---------------------------------------------------------------------------
from db.session import db, client
from core.config import ADMIN_EMAIL, ADMIN_PASSWORD
from core.helpers import now_iso, make_id
from core.security import pwd_context
from core.constants import ALLOWED_ORDER_STATUSES, ALLOWED_SUBSCRIPTION_STATUSES
from core.tenant import DEFAULT_TENANT_ID
import core.config as _cfg

JWT_SECRET = _cfg.JWT_SECRET
ADMIN_PASSWORD = _cfg.ADMIN_PASSWORD
from services.audit_service import AuditService, ensure_audit_indexes, create_audit_log
from services.settings_service import SettingsService
from middleware.request_id import RequestIDMiddleware
from middleware.rate_limit import RateLimitMiddleware
from middleware.security_headers import SecurityHeadersMiddleware

# Seed data and pricing helpers
from data.seed_products import build_seed_products
from services.pricing_service import calculate_price

# ---------------------------------------------------------------------------
# App — disable interactive docs in production
# ---------------------------------------------------------------------------
app = FastAPI(
    docs_url=None if ENVIRONMENT == "production" else "/docs",
    redoc_url=None if ENVIRONMENT == "production" else "/redoc",
    openapi_url=None if ENVIRONMENT == "production" else "/openapi.json",
)

# ---------------------------------------------------------------------------
# Middleware (order matters — outermost first)
# ---------------------------------------------------------------------------
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)

# CORS — restrict to known frontend in production, allow all in dev
cors_origins = [FRONTEND_URL] if (ENVIRONMENT == "production" and FRONTEND_URL) else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Global exception handler — never expose stack traces to clients
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logging.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again later."},
    )

# ---------------------------------------------------------------------------
# Include new route modules
# ---------------------------------------------------------------------------
from routes.auth import router as auth_router
from routes.store import router as store_router
from routes.checkout import router as checkout_router
from routes.gocardless import router as gocardless_router
from routes.webhooks import router as webhooks_router
from routes.admin.logs import router as audit_logs_router
from routes.admin.misc import router as admin_misc_router
from routes.admin.promo_codes import router as admin_promo_codes_router
from routes.admin.terms import router as admin_terms_router
from routes.admin.customers import router as admin_customers_router
from routes.admin.orders import router as admin_orders_router
from routes.admin.subscriptions import router as admin_subscriptions_router
from routes.admin.users import router as admin_users_router
from routes.admin.catalog import router as admin_catalog_router
from routes.admin.exports import router as admin_exports_router
from routes.admin.settings import router as admin_settings_router
from routes.admin.website import router as admin_website_router
from routes.uploads import router as uploads_router
from routes.admin.references import router as references_router
from routes.admin.email_templates import router as email_templates_router
from routes.resources import router as resources_router
from routes.resource_templates import router as resource_templates_router
from routes.resource_email_templates import router as resource_email_templates_router
from routes.resource_categories import router as resource_categories_router
# Legacy compatibility aliases (redirect /api/articles → /api/resources)
from routes.articles import router as articles_router  # kept for old API clients
from routes.article_categories import router as article_categories_router
from routes.article_templates import router as article_templates_router
from routes.article_email_templates import router as article_email_templates_router
from routes.admin.plans import router as plans_admin_router
from routes.admin.partner_billing import router as partner_billing_router
from routes.partner_billing_view import router as partner_billing_view_router
from routes.admin.tenants import router as tenants_admin_router
from routes.admin.payment_validate import router as payment_validate_router
from routes.admin.imports import router as imports_admin_router
from routes.admin.api_keys import router as api_keys_admin_router
from routes.admin.webhooks import router as webhooks_admin_router
from routes.admin.integrations import router as integrations_admin_router
from routes.admin.finance import router as finance_admin_router
from routes.admin.permissions import router as permissions_admin_router
from routes.gdpr import router as gdpr_router
from routes.downloads import router as downloads_router
from routes.oauth import router as oauth_router
from routes.taxes import router as taxes_router
from routes.utils import router as utils_router
from routes.documents import router as documents_router
from routes.admin.forms import router as admin_forms_router
from routes.admin.integration_requests import router as integration_requests_router

app.include_router(auth_router)
app.include_router(store_router)
app.include_router(checkout_router)
app.include_router(gocardless_router)
app.include_router(webhooks_router)
app.include_router(audit_logs_router)
app.include_router(oauth_router)
app.include_router(admin_misc_router)
app.include_router(admin_promo_codes_router)
app.include_router(admin_terms_router)
app.include_router(admin_customers_router)
app.include_router(admin_orders_router)
app.include_router(admin_subscriptions_router)
app.include_router(admin_users_router)
app.include_router(admin_catalog_router)
app.include_router(admin_exports_router)
app.include_router(admin_settings_router)
app.include_router(admin_website_router)
app.include_router(uploads_router)
app.include_router(references_router)
app.include_router(email_templates_router)
app.include_router(resources_router)
app.include_router(resource_templates_router)
app.include_router(resource_email_templates_router)
app.include_router(resource_categories_router)
app.include_router(articles_router)  # legacy /api/articles/* backwards compat
app.include_router(article_categories_router)
app.include_router(article_templates_router)
app.include_router(article_email_templates_router)
app.include_router(tenants_admin_router)
app.include_router(plans_admin_router)
app.include_router(partner_billing_router)
app.include_router(payment_validate_router)
app.include_router(imports_admin_router)
app.include_router(api_keys_admin_router)
app.include_router(webhooks_admin_router)
app.include_router(integrations_admin_router)
app.include_router(finance_admin_router)
app.include_router(permissions_admin_router)
app.include_router(gdpr_router)
app.include_router(downloads_router)
app.include_router(taxes_router)
app.include_router(utils_router)
app.include_router(documents_router)
app.include_router(admin_forms_router)
app.include_router(integration_requests_router)



async def seed_admin_user():
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        return
    existing = await db.users.find_one({"email": ADMIN_EMAIL}, {"_id": 0})
    if existing:
        # Ensure the platform admin always has the correct role, even if it was changed
        if existing.get("role") != "platform_admin" or existing.get("tenant_id") is not None:
            await db.users.update_one(
                {"email": ADMIN_EMAIL},
                {"$set": {"role": "platform_admin", "tenant_id": None, "is_admin": True}}
            )
        return
    user_id = make_id()
    hashed = pwd_context.hash(ADMIN_PASSWORD)
    user_doc = {
        "id": user_id,
        "email": ADMIN_EMAIL,
        "password_hash": hashed,
        "full_name": "Automate Accounts Admin",
        "company_name": "Automate Accounts",
        "phone": "",
        "is_verified": True,
        "is_admin": True,
        "role": "platform_admin",
        "tenant_id": None,
        "verification_code": None,
        "created_at": now_iso(),
    }
    await db.users.insert_one(user_doc)
    customer_id = make_id()
    await db.customers.insert_one(
        {
            "id": customer_id,
            "user_id": user_id,
            "company_name": "Automate Accounts",
            "phone": "",
            "currency": "USD",
            "currency_locked": True,
            "allow_bank_transfer": True,
            "allow_card_payment": True,
            "stripe_customer_id": None,
            "zoho_crm_contact_id": None,
            "zoho_books_contact_id": None,
            "created_at": now_iso(),
        }
    )
    await db.addresses.insert_one(
        {
            "id": make_id(),
            "customer_id": customer_id,
            "line1": "",
            "line2": "",
            "city": "",
            "region": "",
            "postal": "",
            "country": "USA",
        }
    )


async def seed_products():
    if await db.products.count_documents({}) > 0:
        return
    settings = await db.settings.find_one({"id": "app_settings"}, {"_id": 0})
    if not settings:
        settings = {
            "id": "app_settings",
            "zoho_books_migration_url": "https://paymentprocess-873927405.development.catalystserverless.com/app/index.html",
        }
        await db.settings.insert_one(settings)
    products = build_seed_products(settings["zoho_books_migration_url"])
    for product in products:
        product["tenant_id"] = DEFAULT_TENANT_ID
        await db.products.insert_one(product)




async def ensure_db_security_indexes():
    """Create compound indexes for tenant isolation — prevents collection scans and data leaks."""
    idx = [
        ("users", [("tenant_id", 1), ("email", 1)]),
        ("customers", [("tenant_id", 1), ("user_id", 1)]),
        ("orders", [("tenant_id", 1), ("customer_id", 1)]),
        ("orders", [("tenant_id", 1), ("created_at", -1)]),
        ("subscriptions", [("tenant_id", 1), ("customer_id", 1)]),
        ("subscriptions", [("tenant_id", 1), ("created_at", -1)]),
        ("products", [("tenant_id", 1), ("is_active", 1)]),
        ("resources", [("tenant_id", 1), ("status", 1)]),
        ("promo_codes", [("tenant_id", 1), ("code", 1)]),
        ("api_keys", [("key_hash", 1), ("is_active", 1)]),
        ("api_keys", [("key", 1), ("is_active", 1)]),      # legacy plaintext fallback
        ("api_keys", [("tenant_id", 1), ("is_active", 1)]),
        ("quote_requests", [("tenant_id", 1), ("created_at", -1)]),        ("audit_logs", [("tenant_id", 1), ("created_at", -1)]),
    ]
    for collection_name, keys in idx:
        try:
            collection = getattr(db, collection_name)
            await collection.create_index(keys, background=True)
        except Exception:
            pass


async def migrate_api_key_hashes():
    """One-time migration: hash any plaintext API keys created before hashing was introduced."""
    import hashlib
    legacy_keys = await db.api_keys.find(
        {"key": {"$exists": True}, "key_hash": {"$exists": False}}, {"_id": 0, "id": 1, "key": 1}
    ).to_list(1000)
    for doc in legacy_keys:
        raw_key = doc["key"]
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        suffix = raw_key[-8:]
        await db.api_keys.update_one(
            {"id": doc["id"]},
            {"$set": {"key_hash": key_hash, "key_suffix": suffix}, "$unset": {"key": ""}},
        )
    if legacy_keys:
        logging.info("Migrated %d legacy API keys to SHA-256 hashes", len(legacy_keys))


def _validate_startup_secrets():
    """Warn loudly if weak/default secrets are detected."""
    weak_jwt = len(JWT_SECRET) < 32 or JWT_SECRET in (
        "change_me_super_secret", "secret", "changeme", "your-secret-key"
    )
    weak_admin_pw = ADMIN_PASSWORD in ("ChangeMe123!", "password", "admin123", "changeme")

    if ENVIRONMENT == "production":
        if weak_jwt:
            raise RuntimeError(
                "FATAL: JWT_SECRET is weak or default. Set a strong secret (≥ 32 random chars) before running in production."
            )
        if weak_admin_pw:
            raise RuntimeError(
                "FATAL: ADMIN_PASSWORD is a default/weak value. Change it before running in production."
            )
    else:
        if weak_jwt:
            logging.warning("⚠️  JWT_SECRET is weak/default — acceptable in dev but MUST be changed before production.")
        if weak_admin_pw:
            logging.warning("⚠️  ADMIN_PASSWORD is a known default — MUST be changed before production.")


@app.on_event("startup")

async def startup_tasks():
    _validate_startup_secrets()
    await ensure_audit_indexes()
    await ensure_db_security_indexes()
    await migrate_api_key_hashes()
    await SettingsService.cleanup_obsolete()
    await SettingsService.seed()
    await seed_admin_user()
    await seed_products()
    await db.customers.update_many(
        {"allow_bank_transfer": {"$exists": False}},
        {"$set": {"allow_bank_transfer": True}},
    )
    await db.customers.update_many(
        {"allow_card_payment": {"$exists": False}},
        {"$set": {"allow_card_payment": False}},
    )
    
    # Ensure default T&C exists
    default_terms = await db.terms_and_conditions.find_one({"is_default": True}, {"_id": 0})
    if not default_terms:
        await db.terms_and_conditions.insert_one({
            "id": make_id(),
            "title": "Default Terms & Conditions",
            "content": "{company_name} {product_name} - TEST",
            "is_default": True,
            "status": "active",
            "created_at": now_iso(),
        })
    
    # Migrate payment_method="manual" → "offline" for subscriptions (canonical value)
    await db.subscriptions.update_many(
        {"payment_method": "manual"},
        {"$set": {"payment_method": "offline"}}
    )
    
    # Migrate any subscription with status not in ALLOWED_SUBSCRIPTION_STATUSES
    invalid_status_subs = await db.subscriptions.find(
        {"status": {"$nin": ALLOWED_SUBSCRIPTION_STATUSES}}, {"_id": 0, "id": 1, "status": 1}
    ).to_list(500)
    for sub in invalid_status_subs:
        old_status = sub.get("status", "unknown")
        await db.subscriptions.update_one(
            {"id": sub["id"]},
            {"$set": {"status": "active", "_migrated_status": old_status}}
        )
        await create_audit_log(
            entity_type="subscription",
            entity_id=sub["id"],
            action="status_migrated",
            actor="system",
            details={"old_status": old_status, "new_status": "active", "reason": "canonical status migration"}
        )
    
    # Backfill subscription_number for any subscriptions missing it
    subs_missing_number = await db.subscriptions.find(
        {"subscription_number": {"$exists": False}}, {"_id": 0, "id": 1}
    ).to_list(500)
    for sub in subs_missing_number:
        sub_num = f"SUB-{sub['id'].split('-')[0].upper()}"
        await db.subscriptions.update_one({"id": sub["id"]}, {"$set": {"subscription_number": sub_num}})
    
    # Backfill start_date for subscriptions missing it
    await db.subscriptions.update_many(
        {"start_date": {"$exists": False}, "current_period_start": {"$exists": True}},
        [{"$set": {"start_date": "$current_period_start"}}]
    )
    await db.subscriptions.update_many(
        {"start_date": {"$exists": False}},
        [{"$set": {"start_date": "$created_at"}}]
    )
    
    # Backfill role field for admin users (set existing admins to super_admin)
    await db.users.update_many(
        {"is_admin": True, "role": {"$exists": False}},
        {"$set": {"role": "super_admin"}}
    )
    await db.users.update_many(
        {"is_admin": False, "role": {"$exists": False}},
        {"$set": {"role": "customer"}}
    )
    
    # Backfill is_active=True for all existing users (so nobody is inadvertently locked out)
    await db.users.update_many(
        {"is_active": {"$exists": False}},
        {"$set": {"is_active": True}}
    )

    # Backfill partner_map and notes fields for existing customers
    await db.customers.update_many(
        {"partner_map": {"$exists": False}},
        {"$set": {"partner_map": None}}
    )
    await db.customers.update_many(
        {"notes": {"$exists": False}},
        {"$set": {"notes": []}}
    )

    # === NEW MIGRATIONS ===

    # 1. Seed categories collection from existing product category strings (with blurbs)
    CATEGORY_BLURBS_SEED = {
        "Zoho Express Setup": "Fast-track your Zoho setup with expert-led implementation.",
        "Migrate to Zoho": "Move critical systems with minimal downtime and clear milestones.",
        "Managed Services": "Your long-term Zoho partner - managing enhancements, resolving issues, and scaling workflows as you evolve.",
        "Build & Automate": "On-demand development hours to design, build, automate, and refine your Technology stack (Zoho & Non-Zoho).",
        "Accounting on Zoho": "Monthly finance operations tailored to your transaction volume.",
        "Audit & Optimize": "Diagnose what's slowing you down - Refine, Streamline & Maximize",
    }
    all_prods = await db.products.find({}, {"_id": 0, "category": 1}).to_list(2000)
    existing_prod_cats = {p["category"] for p in all_prods if p.get("category")}
    for cat_name in existing_prod_cats:
        existing_cat = await db.categories.find_one({"name": cat_name})
        if not existing_cat:
            await db.categories.insert_one({
                "id": make_id(),
                "name": cat_name,
                "description": CATEGORY_BLURBS_SEED.get(cat_name, ""),
                "is_active": True,
                "created_at": now_iso(),
            })
        elif "description" not in existing_cat and cat_name in CATEGORY_BLURBS_SEED:
            await db.categories.update_one(
                {"name": cat_name},
                {"$set": {"description": CATEGORY_BLURBS_SEED[cat_name]}}
            )

    # Backfill contract_end_date for existing subscriptions (default 12 months from start)
    async for sub in db.subscriptions.find({"contract_end_date": {"$exists": False}}):
        start_raw = sub.get("start_date") or sub.get("current_period_start") or sub.get("created_at")
        if start_raw:
            try:
                start_dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
                contract_end = start_dt + timedelta(days=365)
                await db.subscriptions.update_one(
                    {"id": sub["id"]},
                    {"$set": {"contract_end_date": contract_end.isoformat()}}
                )
            except Exception:
                pass

    # Seed default app settings (brand colors) if not already customized
    existing_settings = await db.app_settings.find_one({})
    if not existing_settings:
        await db.app_settings.insert_one({
            "primary_color": "#0f172a",
            "secondary_color": "#f8fafc",
            "accent_color": "#dc2626",
            "store_name": "Automate Accounts",
            "logo_url": "",
        })
    else:
        # Update test color placeholders to proper brand defaults
        updates = {}
        if existing_settings.get("primary_color") == "#123456":
            updates["primary_color"] = "#0f172a"
        if not existing_settings.get("accent_color"):
            updates["accent_color"] = "#dc2626"
        if updates:
            await db.app_settings.update_one({}, {"$set": updates})

    # ── Currency migrations ──────────────────────────────────────────────────
    # Backfill products with currency="USD" where not set
    await db.products.update_many(
        {"currency": {"$exists": False}},
        {"$set": {"currency": "USD"}}
    )
    # Backfill tenants with base_currency="USD" where not set
    await db.tenants.update_many(
        {"base_currency": {"$exists": False}},
        {"$set": {"base_currency": "USD"}}
    )
    # Drop legacy override_codes collection
    try:
        await db.client.get_default_database().drop_collection("override_codes")
    except Exception:
        pass
    # Drop legacy quote_requests collection
    try:
        await db.client.get_default_database().drop_collection("quote_requests")
    except Exception:
        pass

    # Remove deprecated preferred_currency fields from customer documents
    try:
        await db.customers.update_many(
            {"$or": [{"currency": {"$exists": True}}, {"currency_locked": {"$exists": True}}]},
            {"$unset": {"currency": "", "currency_locked": ""}}
        )
    except Exception:
        pass

    # Prune deprecated email templates across all tenants
    try:
        from services.email_service import _DEPRECATED_TRIGGERS
        if _DEPRECATED_TRIGGERS:
            await db.email_templates.delete_many(
                {"trigger": {"$in": list(_DEPRECATED_TRIGGERS)}, "is_system": True}
            )
    except Exception:
        pass




@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
