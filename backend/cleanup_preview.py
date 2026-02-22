"""Preview what will be deleted before running the actual cleanup."""
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

    print('=== CATEGORIES ===')
    cats = await db.categories.find({}, {'_id': 0, 'name': 1}).to_list(1000)
    keep = [c['name'] for c in cats if c['name'] in KEEP_CATS]
    delete = [c['name'] for c in cats if c['name'] not in KEEP_CATS]
    print(f'  KEEP  ({len(keep)}): {sorted(keep)}')
    print(f'  DELETE({len(delete)}): {sorted(delete)}')

    print('\n=== PRODUCTS ===')
    prods = await db.products.find({}, {'_id': 0, 'name': 1}).to_list(1000)
    keep_p = sorted([p['name'] for p in prods if p['name'] in KEEP_PRODUCTS])
    delete_p = sorted([p['name'] for p in prods if p['name'] not in KEEP_PRODUCTS])
    print(f'  KEEP  ({len(keep_p)}): {keep_p}')
    print(f'  DELETE({len(delete_p)}): {delete_p}')

    print('\n=== TERMS ===')
    terms = await db.terms_and_conditions.find({}, {'_id': 0, 'title': 1}).to_list(1000)
    for t in terms:
        flag = 'KEEP' if t['title'] == 'Default Terms & Conditions' else 'DELETE'
        print(f'  [{flag}] {t["title"]}')

    print('\n=== USERS ===')
    all_users = await db.users.find({}, {'_id': 0, 'email': 1}).to_list(1000)
    print(f'  Total: {len(all_users)} | Will delete: {len([u for u in all_users if u["email"] != ADMIN_EMAIL])}')

    print('\n=== COUNTS TO DELETE ===')
    for col, q in [
        ('subscriptions', {}), ('orders', {}), ('order_items', {}),
        ('quote_requests', {}), ('bank_transactions', {}), ('articles', {}),
        ('article_logs', {}), ('override_codes', {}), ('promo_codes', {}),
        ('invoices', {}), ('payment_transactions', {}), ('audit_logs', {}),
        ('audit_trail', {}), ('addresses', {}), ('email_outbox', {}),
        ('zoho_sync_logs', {}), ('pricing_rules', {}),
    ]:
        n = await db[col].count_documents(q)
        print(f'  {col}: {n}')

asyncio.run(main())
