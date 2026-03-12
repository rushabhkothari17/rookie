import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

PLATFORM_ADMIN_ID = 'edce2cc5-1b73-4e12-8879-d486fe90f4fe'
PLATFORM_TENANT_ID = 'automate-accounts'

WIPE_ALL = [
    'addresses', 'admin_roles', 'api_keys',
    'article_logs', 'article_templates', 'articles',
    'audit_logs', 'audit_trail', 'bank_transactions',
    'categories', 'coupons', 'crm_mappings', 'customer_notes', 'customers',
    'email_logs', 'email_outbox', 'file_uploads',
    'gdpr_requests', 'integration_requests', 'invoices', 'license_usage',
    'oauth_connections', 'oauth_states',
    'one_time_plan_rates', 'one_time_upgrades', 'order_items', 'orders',
    'override_codes', 'partner_invoice_templates', 'partner_orders',
    'partner_submissions', 'partner_subscriptions', 'pending_partner_registrations',
    'plans', 'products', 'promo_codes', 'quote_requests', 'refunds',
    'resource_categories', 'resource_email_templates', 'resource_logs',
    'resource_templates', 'resources',
    'store_filters', 'subscriptions', 'tax_override_rules',
    'tenant_forms', 'tenant_notes', 'terms', 'terms_and_conditions',
    'webhook_deliveries', 'webhooks', 'website_references',
    'workdrive_folders', 'zoho_sync_logs',
]

async def clean():
    client = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = client[os.environ['DB_NAME']]

    for col in WIPE_ALL:
        r = await db[col].delete_many({})
        if r.deleted_count > 0:
            print(f'  Wiped {col}: {r.deleted_count} records')

    r = await db.users.delete_many({'id': {'$ne': PLATFORM_ADMIN_ID}})
    print(f'  Users: removed {r.deleted_count} non-admin users')

    r = await db.tenants.delete_many({'id': {'$ne': PLATFORM_TENANT_ID}})
    print(f'  Tenants: removed {r.deleted_count} non-platform tenants')

    r = await db.website_settings.delete_many({'tenant_id': {'$ne': PLATFORM_TENANT_ID}})
    print(f'  website_settings: removed {r.deleted_count} extra records')

    print()
    print('=== FINAL STATE (non-empty collections) ===')
    all_cols = await db.list_collection_names()
    for c in sorted(all_cols):
        count = await db[c].count_documents({})
        if count > 0:
            print(f'  {c}: {count}')

    client.close()

asyncio.run(clean())
