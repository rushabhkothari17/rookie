"""Hard delete all test data. Run cleanup_preview.py first to verify."""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
load_dotenv()

KEEP_CATS = {
    'Accounting on Zoho', 'Audit & Optimize', 'Build & Automate',
    'Managed Services', 'Migrate to Zoho', 'Zoho Express Setup'
}
KEEP_PRODUCTS = {
    'On-Demand Build Hours Pack', 'Migrate to Zoho WorkDrive', 'Migrate to Zoho Sign',
    'Migrate to Zoho People', 'Migrate to Zoho Mail', 'Migrate to Zoho Forms',
    'Migrate to Zoho Desk', 'Migrate to Zoho Books', 'Historical Accounting & Data Cleanup',
    'Fixed-Scope Development', 'Ongoing Bookkeeping', 'Ongoing Zoho Development',
    'Ongoing Zoho Development \u2014 Enterprise', 'Unlimited Zoho Support',
    'Zoho Books Express Setup', 'Zoho CRM Express Setup', 'Zoho Expense Setup',
    'Zoho Health Check Plus', 'Zoho Health Check Starter', 'Zoho People Setup'
}
ADMIN_EMAIL = 'admin@automateaccounts.local'

async def main():
    client = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = client[os.environ['DB_NAME']]

    results = {}

    # 1. Full-wipe collections (no conditions needed)
    FULL_WIPE = [
        'subscriptions', 'orders', 'order_items', 'quote_requests',
        'bank_transactions', 'articles', 'article_logs',
        'override_codes', 'promo_codes', 'invoices',
        'payment_transactions', 'audit_logs', 'audit_trail',
        'addresses', 'email_outbox', 'zoho_sync_logs', 'pricing_rules',
    ]
    for col in FULL_WIPE:
        r = await db[col].delete_many({})
        results[col] = r.deleted_count

    # 2. Users — keep admin only
    r = await db.users.delete_many({'email': {'$ne': ADMIN_EMAIL}})
    results['users'] = r.deleted_count

    # 3. Customers — keep admin only
    r = await db.customers.delete_many({'email': {'$ne': ADMIN_EMAIL}})
    results['customers'] = r.deleted_count

    # 4. Categories — keep the 6 real ones
    r = await db.categories.delete_many({'name': {'$nin': list(KEEP_CATS)}})
    results['categories'] = r.deleted_count

    # 5. Products — keep the 20 real ones
    r = await db.products.delete_many({'name': {'$nin': list(KEEP_PRODUCTS)}})
    results['products'] = r.deleted_count

    # 6. Terms — keep Default only
    r = await db.terms_and_conditions.delete_many({'title': {'$ne': 'Default Terms & Conditions'}})
    results['terms_and_conditions'] = r.deleted_count

    # 7. app_settings — delete test/temp keys but keep real config
    # Only delete rows whose 'key' contains TEST or is clearly test data
    r = await db.app_settings.delete_many({
        'key': {'$regex': '^(TEST|test)', '$options': 'i'}
    })
    results['app_settings_test_keys'] = r.deleted_count

    print('\n=== HARD DELETE RESULTS ===')
    total = 0
    for k, v in results.items():
        print(f'  {k}: deleted {v}')
        total += v
    print(f'\n  TOTAL DELETED: {total} documents')

    # Verify remaining counts
    print('\n=== REMAINING COUNTS ===')
    for col in ['users', 'customers', 'categories', 'products', 'terms_and_conditions',
                'subscriptions', 'orders', 'articles', 'override_codes', 'promo_codes']:
        n = await db[col].count_documents({})
        print(f'  {col}: {n}')

asyncio.run(main())
