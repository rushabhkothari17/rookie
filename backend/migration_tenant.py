"""
Tenant migration script — run once to:
1. Create the default "Automate Accounts" tenant
2. Backfill tenant_id on ALL existing collections
3. Promote the platform super admin user
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from core.helpers import make_id, now_iso
from db.session import db

DEFAULT_TENANT = {
    "id": "automate-accounts",
    "name": "Automate Accounts",
    "code": "automate-accounts",
    "status": "active",
    "created_at": now_iso(),
    "updated_at": now_iso(),
}

# All collections that hold business data (not system/meta collections)
BUSINESS_COLLECTIONS = [
    "users",
    "customers",
    "addresses",
    "orders",
    "order_items",
    "subscriptions",
    "products",
    "categories",
    "articles",
    "article_categories",
    "article_templates",
    "article_email_templates",
    "article_logs",
    "email_templates",
    "email_outbox",
    "email_logs",
    "bank_transactions",
    "promo_codes",
    "override_codes",
    "quote_requests",
    "terms_and_conditions",
    "audit_logs",
    "audit_trail",
    "invoices",
    "payment_transactions",
    "website_references",
    "zoho_sync_logs",
]

# Settings collections are handled separately (they have mixed document types)
SETTINGS_COLLECTIONS = [
    "website_settings",
]

PLATFORM_ADMIN_EMAIL = "admin@automateaccounts.local"


async def run():
    print("=== Tenant Migration Starting ===\n")

    # 1. Create default tenant (upsert)
    existing = await db.tenants.find_one({"id": "automate-accounts"})
    if existing:
        print("✓ Default tenant already exists — skipping creation")
    else:
        await db.tenants.insert_one({**DEFAULT_TENANT})
        print("✓ Created default tenant: automate-accounts")

    # 2. Backfill business collections
    tid = DEFAULT_TENANT["id"]
    for coll_name in BUSINESS_COLLECTIONS:
        coll = getattr(db, coll_name)
        result = await coll.update_many(
            {"tenant_id": {"$exists": False}},
            {"$set": {"tenant_id": tid}},
        )
        if result.modified_count:
            print(f"  Backfilled {result.modified_count:>5} docs → {coll_name}")
        else:
            print(f"  No docs to backfill    → {coll_name}")

    # 3. Backfill website_settings (single flat document)
    for coll_name in SETTINGS_COLLECTIONS:
        coll = getattr(db, coll_name)
        result = await coll.update_many(
            {"tenant_id": {"$exists": False}},
            {"$set": {"tenant_id": tid}},
        )
        print(f"  Backfilled {result.modified_count:>5} docs → {coll_name}")

    # 4. Backfill app_settings — only the flat branding document (no "key" field)
    result = await db.app_settings.update_many(
        {"key": {"$exists": False}, "tenant_id": {"$exists": False}},
        {"$set": {"tenant_id": tid}},
    )
    print(f"  Backfilled {result.modified_count:>5} docs → app_settings (flat branding)")

    # 5. Promote platform super admin
    user = await db.users.find_one({"email": PLATFORM_ADMIN_EMAIL})
    if user:
        await db.users.update_one(
            {"email": PLATFORM_ADMIN_EMAIL},
            {"$set": {
                "role": "platform_super_admin",
                "is_admin": True,
                "tenant_id": None,
            }},
        )
        print(f"\n✓ Promoted {PLATFORM_ADMIN_EMAIL} → platform_super_admin (tenant_id: null)")
    else:
        print(f"\n⚠ Platform admin {PLATFORM_ADMIN_EMAIL} not found — skipping promotion")

    # 6. Create indexes for tenant_id on key collections
    for coll_name in ["users", "customers", "orders", "products", "articles"]:
        coll = getattr(db, coll_name)
        await coll.create_index("tenant_id")
    print("\n✓ Created tenant_id indexes on key collections")

    print("\n=== Migration Complete ===")


if __name__ == "__main__":
    asyncio.run(run())
