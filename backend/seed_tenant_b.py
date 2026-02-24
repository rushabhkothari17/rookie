"""
Seed script for Tenant B Test.
Populates the 'Tenant B Test' tenant with comprehensive test data.
Run with: python3 seed_tenant_b.py
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
import hashlib

sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv(".env")

import motor.motor_asyncio

TENANT_ID = "e7301988-7f0f-4b2b-a678-4e37882e385f"
DB = None


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return str(uuid.uuid4())


async def seed():
    global DB
    client = motor.motor_asyncio.AsyncIOMotorClient(os.environ["MONGO_URL"])
    DB = client[os.environ["DB_NAME"]]

    print(f"Seeding tenant: {TENANT_ID}")

    await seed_categories()
    await seed_products()
    await seed_customers()
    await seed_promo_codes()
    await seed_subscriptions()
    await seed_orders()
    await seed_quote_requests()
    await seed_terms()
    print("\n✅ Seed complete for Tenant B Test!")


async def seed_categories():
    print("  → Categories...")
    existing = await DB.categories.count_documents({"tenant_id": TENANT_ID})
    if existing > 0:
        print(f"    (already has {existing} categories, skipping)")
        return

    cats = [
        {"id": uid(), "tenant_id": TENANT_ID, "name": "SaaS Products", "slug": "saas-products", "description": "Software as a Service products", "is_active": True, "created_at": now_iso()},
        {"id": uid(), "tenant_id": TENANT_ID, "name": "Consulting Services", "slug": "consulting-services", "description": "Professional consulting services", "is_active": True, "created_at": now_iso()},
        {"id": uid(), "tenant_id": TENANT_ID, "name": "Setup & Onboarding", "slug": "setup-onboarding", "description": "One-time setup services", "is_active": True, "created_at": now_iso()},
    ]
    await DB.categories.insert_many(cats)
    print(f"    Created {len(cats)} categories")


async def seed_products():
    print("  → Products...")
    existing = await DB.products.count_documents({"tenant_id": TENANT_ID})
    if existing >= 5:
        print(f"    (already has {existing} products, skipping)")
        return

    products = [
        # Fixed-price subscription product
        {
            "id": uid(), "tenant_id": TENANT_ID,
            "name": "TB Starter Plan", "sku": "TB-STARTER",
            "description": "Starter plan with basic features",
            "pricing_type": "fixed", "base_price": 49.0,
            "is_subscription": True, "billing_period": "monthly",
            "is_active": True, "is_scope_request": False,
            "category": "SaaS Products",
            "created_at": now_iso(),
        },
        # Fixed-price one-time product
        {
            "id": uid(), "tenant_id": TENANT_ID,
            "name": "TB Onboarding Package", "sku": "TB-ONBOARDING",
            "description": "One-time setup and onboarding service",
            "pricing_type": "fixed", "base_price": 299.0,
            "is_subscription": False,
            "is_active": True, "is_scope_request": False,
            "category": "Setup & Onboarding",
            "created_at": now_iso(),
        },
        # Zero-price product (triggers scope ID unlock flow)
        {
            "id": uid(), "tenant_id": TENANT_ID,
            "name": "TB Custom Development", "sku": "TB-CUSTOM-DEV",
            "description": "Custom development project with scope-based pricing",
            "pricing_type": "fixed", "base_price": 0.0,
            "is_subscription": False,
            "is_active": True, "is_scope_request": False,
            "category": "Consulting Services",
            "created_at": now_iso(),
        },
        # Scope request product (shows quote form)
        {
            "id": uid(), "tenant_id": TENANT_ID,
            "name": "TB Enterprise Solution", "sku": "TB-ENTERPRISE",
            "description": "Enterprise-grade solution with custom pricing",
            "pricing_type": "scope_request", "base_price": 0.0,
            "is_subscription": False,
            "is_active": True, "is_scope_request": True,
            "category": "Consulting Services",
            "created_at": now_iso(),
        },
        # Inactive product (for testing deactivate flow)
        {
            "id": uid(), "tenant_id": TENANT_ID,
            "name": "TB Legacy Plan (Deprecated)", "sku": "TB-LEGACY",
            "description": "Old plan no longer sold",
            "pricing_type": "fixed", "base_price": 19.0,
            "is_subscription": True, "billing_period": "monthly",
            "is_active": False, "is_scope_request": False,
            "category": "SaaS Products",
            "created_at": now_iso(),
        },
        # High-price product
        {
            "id": uid(), "tenant_id": TENANT_ID,
            "name": "TB Growth Plan", "sku": "TB-GROWTH",
            "description": "Growth plan for scaling businesses",
            "pricing_type": "fixed", "base_price": 149.0,
            "is_subscription": True, "billing_period": "monthly",
            "is_active": True, "is_scope_request": False,
            "category": "SaaS Products",
            "created_at": now_iso(),
        },
    ]
    await DB.products.insert_many(products)
    print(f"    Created {len(products)} products")
    return products


async def seed_customers():
    print("  → Customers...")
    existing = await DB.customers.count_documents({"tenant_id": TENANT_ID})
    if existing >= 3:
        print(f"    (already has {existing} customers, skipping)")
        return

    customers = [
        {
            "id": uid(), "tenant_id": TENANT_ID,
            "name": "Alice Johnson", "email": "alice.johnson@example.com",
            "company_name": "Johnson Corp", "phone": "+1-555-0101",
            "currency": "USD", "is_active": True,
            "created_at": now_iso(),
        },
        {
            "id": uid(), "tenant_id": TENANT_ID,
            "name": "Bob Smith", "email": "bob.smith@example.com",
            "company_name": "Smith Enterprises", "phone": "+1-555-0102",
            "currency": "USD", "is_active": True,
            "created_at": now_iso(),
        },
        {
            "id": uid(), "tenant_id": TENANT_ID,
            "name": "Carol Williams", "email": "carol.w@testbiz.com",
            "company_name": "TestBiz Ltd", "phone": "+1-555-0103",
            "currency": "USD", "is_active": True,
            "created_at": now_iso(),
        },
        {
            "id": uid(), "tenant_id": TENANT_ID,
            "name": "David Lee", "email": "david.lee@deactivated.com",
            "company_name": "Deactivated Co", "phone": "+1-555-0104",
            "currency": "USD", "is_active": False,
            "created_at": now_iso(),
        },
    ]
    await DB.customers.insert_many(customers)
    print(f"    Created {len(customers)} customers")
    return customers


async def seed_promo_codes():
    print("  → Promo codes...")
    existing = await DB.promo_codes.count_documents({"tenant_id": TENANT_ID})
    if existing >= 2:
        print(f"    (already has {existing} promo codes, skipping)")
        return

    promos = [
        {
            "id": uid(), "tenant_id": TENANT_ID,
            "code": "WELCOME20", "discount_type": "percentage",
            "discount_value": 20.0, "max_uses": 100, "uses": 5,
            "enabled": True, "valid_from": now_iso(),
            "valid_until": (datetime.now(timezone.utc) + timedelta(days=90)).isoformat(),
            "created_at": now_iso(),
        },
        {
            "id": uid(), "tenant_id": TENANT_ID,
            "code": "SAVE50", "discount_type": "fixed",
            "discount_value": 50.0, "max_uses": 10, "uses": 2,
            "enabled": True, "valid_from": now_iso(),
            "valid_until": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "created_at": now_iso(),
        },
        {
            "id": uid(), "tenant_id": TENANT_ID,
            "code": "EXPIRED10", "discount_type": "percentage",
            "discount_value": 10.0, "max_uses": 50, "uses": 50,
            "enabled": False,
            "created_at": now_iso(),
        },
    ]
    await DB.promo_codes.insert_many(promos)
    print(f"    Created {len(promos)} promo codes")


async def seed_subscriptions():
    print("  → Subscriptions...")
    existing = await DB.subscriptions.count_documents({"tenant_id": TENANT_ID})
    if existing >= 2:
        print(f"    (already has {existing} subscriptions, skipping)")
        return

    subs = [
        {
            "id": uid(), "tenant_id": TENANT_ID,
            "customer_email": "alice.johnson@example.com",
            "product_name": "TB Starter Plan", "product_sku": "TB-STARTER",
            "amount": 49.0, "currency": "USD",
            "status": "active", "billing_period": "monthly",
            "renewal_date": (datetime.now(timezone.utc) + timedelta(days=15)).isoformat(),
            "created_at": now_iso(),
        },
        {
            "id": uid(), "tenant_id": TENANT_ID,
            "customer_email": "bob.smith@example.com",
            "product_name": "TB Growth Plan", "product_sku": "TB-GROWTH",
            "amount": 149.0, "currency": "USD",
            "status": "active", "billing_period": "monthly",
            "renewal_date": (datetime.now(timezone.utc) + timedelta(days=22)).isoformat(),
            "created_at": now_iso(),
        },
        {
            "id": uid(), "tenant_id": TENANT_ID,
            "customer_email": "carol.w@testbiz.com",
            "product_name": "TB Starter Plan", "product_sku": "TB-STARTER",
            "amount": 49.0, "currency": "USD",
            "status": "canceled", "billing_period": "monthly",
            "renewal_date": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
            "created_at": now_iso(),
        },
    ]
    await DB.subscriptions.insert_many(subs)
    print(f"    Created {len(subs)} subscriptions")


async def seed_orders():
    print("  → Orders...")
    existing = await DB.orders.count_documents({"tenant_id": TENANT_ID})
    if existing >= 2:
        print(f"    (already has {existing} orders, skipping)")
        return

    orders = [
        {
            "id": uid(), "tenant_id": TENANT_ID,
            "order_number": f"TB-ORD-001",
            "customer_email": "alice.johnson@example.com",
            "product_name": "TB Onboarding Package",
            "subtotal": 299.0, "discount": 0.0, "fee": 0.0, "total": 299.0,
            "currency": "USD", "status": "paid",
            "created_at": now_iso(),
        },
        {
            "id": uid(), "tenant_id": TENANT_ID,
            "order_number": f"TB-ORD-002",
            "customer_email": "bob.smith@example.com",
            "product_name": "TB Growth Plan",
            "subtotal": 149.0, "discount": 29.8, "fee": 0.0, "total": 119.2,
            "currency": "USD", "status": "paid",
            "promo_code": "WELCOME20",
            "created_at": now_iso(),
        },
        {
            "id": uid(), "tenant_id": TENANT_ID,
            "order_number": f"TB-ORD-003",
            "customer_email": "carol.w@testbiz.com",
            "product_name": "TB Starter Plan",
            "subtotal": 49.0, "discount": 0.0, "fee": 0.0, "total": 49.0,
            "currency": "USD", "status": "unpaid",
            "created_at": now_iso(),
        },
        {
            "id": uid(), "tenant_id": TENANT_ID,
            "order_number": f"TB-ORD-004",
            "customer_email": "alice.johnson@example.com",
            "product_name": "TB Starter Plan",
            "subtotal": 49.0, "discount": 0.0, "fee": 0.0, "total": 49.0,
            "currency": "USD", "status": "refunded",
            "created_at": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
        },
    ]
    await DB.orders.insert_many(orders)
    print(f"    Created {len(orders)} orders")


async def seed_quote_requests():
    print("  → Quote requests...")
    existing = await DB.quote_requests.count_documents({"tenant_id": TENANT_ID})
    if existing >= 2:
        print(f"    (already has {existing} quote requests, skipping)")
        return

    quotes = [
        {
            "id": uid(), "tenant_id": TENANT_ID,
            "name": "Frank Davis", "email": "frank.davis@bigco.com",
            "company": "BigCo Inc", "phone": "+1-555-0200",
            "product_name": "TB Enterprise Solution",
            "message": "We need an enterprise solution for 500 users",
            "status": "pending", "created_at": now_iso(),
        },
        {
            "id": uid(), "tenant_id": TENANT_ID,
            "name": "Grace Kim", "email": "grace.kim@startup.io",
            "company": "Startup.io", "phone": "+1-555-0201",
            "product_name": "TB Custom Development",
            "message": "We need a custom integration built",
            "status": "quoted", "quoted_amount": 5000.0,
            "created_at": now_iso(),
        },
    ]
    await DB.quote_requests.insert_many(quotes)
    print(f"    Created {len(quotes)} quote requests")


async def seed_terms():
    print("  → Terms...")
    existing = await DB.terms.count_documents({"tenant_id": TENANT_ID})
    if existing >= 1:
        print(f"    (already has {existing} terms, skipping)")
        return

    terms = [
        {
            "id": uid(), "tenant_id": TENANT_ID,
            "title": "Standard Terms of Service",
            "slug": "tos",
            "content": "<h1>Terms of Service</h1><p>These are the standard terms of service for Tenant B Test.</p><p>By using our services, you agree to these terms.</p>",
            "is_active": True, "is_default": True,
            "created_at": now_iso(),
        },
        {
            "id": uid(), "tenant_id": TENANT_ID,
            "title": "Data Processing Agreement",
            "slug": "dpa",
            "content": "<h1>Data Processing Agreement</h1><p>This DPA governs how we process your data.</p>",
            "is_active": True, "is_default": False,
            "created_at": now_iso(),
        },
    ]
    await DB.terms.insert_many(terms)
    print(f"    Created {len(terms)} terms documents")


if __name__ == "__main__":
    asyncio.run(seed())
