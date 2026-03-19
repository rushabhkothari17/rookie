"""Admin: CSV import routes with upsert (create + update by id)."""
from __future__ import annotations

import csv
import io
import json
import re
import textwrap
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse

from core.tenant import get_tenant_filter, tenant_id_of, get_tenant_admin
from db.session import db
from core.helpers import make_id, now_iso

router = APIRouter(prefix="/api", tags=["admin-imports"])

# ── Helpers ──────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_cell(val: str) -> str:
    """Strip outer whitespace and prevent CSV formula injection."""
    val = val.strip()
    if val and val[0] in ("=", "+", "-", "@", "|", "\t", "\r"):
        val = "'" + val
    return val


def _parse_val(val: str) -> Any:
    """Parse a string CSV cell into the most appropriate Python type.
    Handles: JSON arrays/objects, booleans, integers, floats, empty → None."""
    val = val.strip()
    if val == "":
        return None
    if val.lower() in ("true", "yes"):
        return True
    if val.lower() in ("false", "no"):
        return False
    # Try JSON for objects and arrays
    if val.startswith("{") or val.startswith("["):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, ValueError):
            pass
    # Try int
    try:
        return int(val)
    except ValueError:
        pass
    # Try float
    try:
        return float(val)
    except ValueError:
        pass
    return val


def _read_csv(content: bytes) -> List[Dict[str, str]]:
    """Parse CSV bytes into a list of dicts. Handles BOM."""
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row in reader:
        rows.append({k.strip(): _sanitize_cell(v) for k, v in row.items() if k})
    return rows


def _build_doc(row: Dict[str, str], entity: str, tid: str, existing_id: Optional[str]) -> Dict[str, Any]:
    """Convert a CSV row dict into a MongoDB document dict."""
    doc: Dict[str, Any] = {}
    for key, val in row.items():
        if not key:
            continue
        parsed = _parse_val(val)
        if parsed is not None:  # Skip empty cells — don't overwrite existing fields with None
            doc[key] = parsed

    doc["tenant_id"] = tid
    if existing_id:
        doc["id"] = existing_id
        doc["updated_at"] = _now()
    else:
        doc.setdefault("id", make_id())
        doc["created_at"] = _now()
        doc["updated_at"] = _now()
    return doc


# ── Configuration ─────────────────────────────────────────────────────────────

ENTITY_COLLECTIONS: Dict[str, str] = {
    "customers":            "customers",
    "orders":               "orders",
    "subscriptions":        "subscriptions",
    "catalog":              "products",
    "promo-codes":          "promo_codes",
    "terms":                "terms_and_conditions",
    "categories":           "categories",
    "article-categories":   "article_categories",
    "article-templates":    "article_templates",
    "resources":            "resources",
    "resource-categories":  "resource_categories",
    "resource-templates":   "resource_templates",
}

REQUIRED_FIELDS: Dict[str, List[str]] = {
    "customers":            [],          # updates only — email is on users doc, not here
    "orders":               ["customer_id", "status", "total"],
    "subscriptions":        ["customer_id", "plan_name", "status"],
    "catalog":              ["name"],
    "promo-codes":          ["code", "discount_type", "discount_value"],
    "terms":                ["title"],
    "categories":           ["name"],
    "article-categories":   ["name"],
    "article-templates":    ["name"],
    "resources":            ["title", "category"],
    "resource-categories":  ["name"],
    "resource-templates":   ["name"],
}

# ── Templates & sample data ───────────────────────────────────────────────────

TEMPLATES: Dict[str, List[str]] = {
    "customers": [
        "id", "company_name", "phone", "currency",
        "allowed_payment_modes", "allow_bank_transfer", "allow_card_payment",
        "stripe_customer_id", "zoho_crm_contact_id", "zoho_books_contact_id",
    ],
    "orders": [
        "id", "order_number", "customer_id", "type", "status",
        "subtotal", "discount_amount", "fee", "total", "currency",
        "payment_method", "tax_rate", "tax_name", "tax_amount",
        "order_date", "payment_date", "processor_id", "internal_note",
    ],
    "subscriptions": [
        "id", "subscription_number", "customer_id", "plan_name", "product_id",
        "status", "payment_method", "billing_interval", "amount", "currency",
        "renewal_date", "start_date", "contract_end_date",
        "cancel_at_period_end", "internal_note", "processor_id", "term_months",
    ],
    "catalog": [
        "id", "name", "category", "card_tag", "card_description", "card_bullets",
        "description_long", "bullets", "base_price", "currency",
        "is_subscription", "billing_type", "billing_cycle",
        "pricing_type", "stripe_price_id", "is_active", "visible_to_customers",
        "display_layout", "default_term_months", "show_price_breakdown",
        "custom_sections", "intake_schema_json",
    ],
    "promo-codes": [
        "id", "code", "discount_type", "discount_value",
        "applies_to", "applies_to_products", "product_ids",
        "expiry_date", "max_uses", "usage_count", "enabled",
        "one_time_code", "promo_note", "currency",
    ],
    "terms": [
        "id", "title", "content", "is_active", "version",
    ],
    "categories": [
        "id", "name", "description",
    ],
    "article-categories": [
        "id", "name", "description", "color",
    ],
    "article-templates": [
        "id", "name", "description", "category", "content",
    ],
    "resources": [
        "id", "title", "slug", "category", "content",
        "visibility", "restricted_to", "price", "currency",
    ],
    "resource-categories": [
        "id", "name", "description", "color", "is_scope_final",
    ],
    "resource-templates": [
        "id", "name", "description", "category", "content",
    ],
}

SAMPLE_DATA: Dict[str, Dict[str, str]] = {
    "customers": {
        "id": "",
        "company_name": "Acme Ltd",
        "phone": "+44 7700 900000",
        "currency": "GBP",
        "allowed_payment_modes": '["gocardless","card"]',
        "allow_bank_transfer": "false",
        "allow_card_payment": "true",
        "stripe_customer_id": "cus_XXXX",
        "zoho_crm_contact_id": "",
        "zoho_books_contact_id": "",
    },
    "orders": {
        "id": "",
        "order_number": "AA-10001",
        "customer_id": "cust-uuid-here",
        "type": "one_time",
        "status": "paid",
        "subtotal": "99.00",
        "discount_amount": "0",
        "fee": "0",
        "total": "99.00",
        "currency": "GBP",
        "payment_method": "card",
        "tax_rate": "20",
        "tax_name": "VAT",
        "tax_amount": "16.50",
        "order_date": "2025-01-15",
        "payment_date": "2025-01-15",
        "processor_id": "pi_stripe_id",
        "internal_note": "",
    },
    "subscriptions": {
        "id": "",
        "subscription_number": "SUB-00001",
        "customer_id": "cust-uuid-here",
        "plan_name": "Growth Plan",
        "product_id": "prod-uuid-here",
        "status": "active",
        "payment_method": "gocardless",
        "billing_interval": "monthly",
        "amount": "149.00",
        "currency": "GBP",
        "renewal_date": "2025-02-01",
        "start_date": "2025-01-01",
        "contract_end_date": "2025-12-31",
        "cancel_at_period_end": "false",
        "internal_note": "",
        "processor_id": "GC-mandate-id",
        "term_months": "12",
    },
    "catalog": {
        "id": "",
        "name": "Growth Plan",
        "category": "Bookkeeping",
        "card_tag": "Most Popular",
        "card_description": "Full bookkeeping & payroll",
        "card_bullets": '["Up to 100 transactions/mo","Monthly reports","Dedicated accountant"]',
        "description_long": "Comprehensive bookkeeping service...",
        "bullets": '["VAT returns","Bank reconciliation","Payroll for 5 staff"]',
        "base_price": "149.00",
        "currency": "GBP",
        "is_subscription": "true",
        "billing_type": "prorata",
        "billing_cycle": "monthly",
        "pricing_type": "fixed",
        "stripe_price_id": "price_XXXX",
        "is_active": "true",
        "visible_to_customers": "true",
        "display_layout": "standard",
        "default_term_months": "12",
        "show_price_breakdown": "false",
        "custom_sections": '[{"name":"Overview","content":"<p>Overview here</p>","icon":"FileText","icon_color":"blue","tags":[]}]',
        "intake_schema_json": '{"questions":[{"id":"q1","label":"Company name","type":"text","required":true},{"id":"q2","label":"How many employees?","type":"number","required":false},{"id":"q3","label":"Software used","type":"multi_select","required":false,"options":["Xero","QuickBooks","Sage","Other"]},{"id":"q4","label":"Filing frequency","type":"radio","required":true,"options":["Monthly","Quarterly","Annually"]},{"id":"q5","label":"Any notes?","type":"textarea","required":false}]}',
    },
    "promo-codes": {
        "id": "",
        "code": "SAVE20",
        "discount_type": "percent",
        "discount_value": "20",
        "applies_to": "all",
        "applies_to_products": '[]',
        "product_ids": '[]',
        "expiry_date": "2025-12-31T23:59:59",
        "max_uses": "100",
        "usage_count": "0",
        "enabled": "true",
        "one_time_code": "false",
        "promo_note": "Summer campaign",
        "currency": "",
    },
    "terms": {
        "id": "",
        "title": "Standard Terms of Service",
        "content": "<p>Your terms here...</p>",
        "is_active": "true",
        "version": "1",
    },
    "categories": {
        "id": "",
        "name": "Bookkeeping",
        "description": "All bookkeeping related products",
    },
    "article-categories": {
        "id": "",
        "name": "Guides",
        "description": "How-to guides for clients",
        "color": "#3b82f6",
    },
    "article-templates": {
        "id": "",
        "name": "Onboarding Guide",
        "description": "Template for new client onboarding",
        "category": "Guides",
        "content": "<p>Welcome to our service...</p>",
    },
    "resources": {
        "id": "",
        "title": "How to submit your receipts",
        "slug": "how-to-submit-receipts",
        "category": "Guides",
        "content": "<p>Step 1: Log in...</p>",
        "visibility": "all",
        "restricted_to": '[]',
        "price": "",
        "currency": "",
    },
    "resource-categories": {
        "id": "",
        "name": "Guides",
        "description": "How-to guides",
        "color": "#3b82f6",
        "is_scope_final": "false",
    },
    "resource-templates": {
        "id": "",
        "name": "Quarterly Review Template",
        "description": "Template for quarterly client reviews",
        "category": "Reviews",
        "content": "<p>Q1 Review...</p>",
    },
}

# ── Guide content ─────────────────────────────────────────────────────────────

GUIDES: Dict[str, str] = {
    "customers": textwrap.dedent("""\
        # Customers Import Guide

        ## Important Notes
        - This import updates the `customers` record only. Email, full name, and address fields live
          in separate collections and CANNOT be set via this import. Use the admin UI to create new
          customer accounts.
        - Leave `id` blank to create a new record. Provide an existing `id` to update it.
        - `allowed_payment_modes`: JSON array. Valid values: "gocardless", "card", "bank_transfer".
          Example: ["gocardless","card"]
        - `allow_bank_transfer` / `allow_card_payment`: true or false

        ## All Fields
        | Field | Type | Required | Notes |
        |---|---|---|---|
        | id | string | No | Leave blank to create; provide to update |
        | company_name | string | No | Overrides existing company name |
        | phone | string | No | E.164 format recommended: +44 7700 900000 |
        | currency | string | No | ISO 4217 code: GBP, USD, EUR |
        | allowed_payment_modes | JSON array | No | ["gocardless","card"] |
        | allow_bank_transfer | boolean | No | true / false |
        | allow_card_payment | boolean | No | true / false |
        | stripe_customer_id | string | No | Stripe customer ID (cus_XXXX) |
        | zoho_crm_contact_id | string | No | Zoho CRM Contact ID |
        | zoho_books_contact_id | string | No | Zoho Books Contact ID |
    """),

    "orders": textwrap.dedent("""\
        # Orders Import Guide

        ## Important Notes
        - `customer_id` must be the UUID of an existing customer record (not the email).
        - `status` valid values: pending, paid, cancelled, refunded, failed
        - `payment_method` valid values: card, gocardless, bank_transfer, manual
        - `type` valid values: one_time, subscription_charge, upgrade, adjustment
        - `processor_id`: Stripe Payment Intent ID (pi_XXXX) or GoCardless payment ID
        - Order line items (individual products per order) live in a separate `order_items`
          collection and CANNOT be imported via this CSV. Use the admin UI to add line items.
        - Dates should be ISO-8601: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS

        ## All Fields
        | Field | Type | Required | Notes |
        |---|---|---|---|
        | id | string | No | Leave blank to create |
        | order_number | string | No | Auto-generated if blank (AA-XXXXX) |
        | customer_id | string | Yes | UUID of customer |
        | type | string | No | one_time / subscription_charge / upgrade / adjustment |
        | status | string | Yes | pending / paid / cancelled / refunded / failed |
        | subtotal | number | No | Pre-tax, pre-discount amount |
        | discount_amount | number | No | Total discount applied |
        | fee | number | No | Service or processing fee |
        | total | number | Yes | Final billed amount |
        | currency | string | No | GBP, USD, EUR (defaults to tenant currency) |
        | payment_method | string | No | card / gocardless / bank_transfer / manual |
        | tax_rate | number | No | Percentage, e.g. 20 for 20% |
        | tax_name | string | No | VAT / Sales Tax |
        | tax_amount | number | No | Calculated tax amount |
        | order_date | string | No | YYYY-MM-DD |
        | payment_date | string | No | YYYY-MM-DD |
        | processor_id | string | No | Stripe pi_XXXX or GoCardless ID |
        | internal_note | string | No | Admin-only note |
    """),

    "subscriptions": textwrap.dedent("""\
        # Subscriptions Import Guide

        ## Important Notes
        - `customer_id` must be the UUID of an existing customer record.
        - `product_id` must be the UUID of an existing product in the catalog.
        - `status` valid values: active, cancelled, paused, past_due, trialing, pending
        - `payment_method` valid values: card, gocardless, bank_transfer, manual
        - `billing_interval` valid values: monthly, annual, quarterly, one_time
        - Dates should be ISO-8601: YYYY-MM-DD

        ## All Fields
        | Field | Type | Required | Notes |
        |---|---|---|---|
        | id | string | No | Leave blank to create |
        | subscription_number | string | No | Auto-generated if blank |
        | customer_id | string | Yes | UUID of customer |
        | plan_name | string | Yes | Display name of the plan |
        | product_id | string | No | UUID of product in catalog |
        | status | string | Yes | active / cancelled / paused / past_due / trialing |
        | payment_method | string | No | card / gocardless / bank_transfer / manual |
        | billing_interval | string | No | monthly / annual / quarterly |
        | amount | number | No | Recurring charge amount |
        | currency | string | No | GBP, USD, EUR |
        | renewal_date | string | No | Next billing date: YYYY-MM-DD |
        | start_date | string | No | Subscription start: YYYY-MM-DD |
        | contract_end_date | string | No | Contract end: YYYY-MM-DD |
        | cancel_at_period_end | boolean | No | true / false |
        | internal_note | string | No | Admin-only note |
        | processor_id | string | No | Stripe sub ID or GoCardless mandate ID |
        | term_months | number | No | Contract length in months |
    """),

    "catalog": textwrap.dedent("""\
        # Products (Catalog) Import Guide

        ## Important Notes
        - `custom_sections` and `intake_schema_json` are JSON fields — wrap in double-quotes and escape
          inner quotes if needed.
        - `billing_cycle` valid values: monthly, annual, quarterly
        - `billing_type` valid values: prorata, fixed
        - `pricing_type` valid values: fixed, variable, internal
        - `display_layout` valid values: standard, compact, featured
        - `visibility` applies to which customers can see the product.

        ## intake_schema_json — Question Types
        All intake questions live in the `questions` array inside `intake_schema_json`.
        Each question has: id, label, type, required, options (for select types), placeholder (for text).

        | type | Description | options needed? |
        |---|---|---|
        | text | Single-line text input | No |
        | textarea | Multi-line text area | No |
        | number | Numeric input | No |
        | date | Date picker | No |
        | select | Single-choice dropdown | Yes — array of strings |
        | multi_select | Multi-choice checkboxes | Yes — array of strings |
        | radio | Single-choice radio buttons | Yes — array of strings |
        | file | File upload | No |
        | checkbox | Single boolean checkbox | No |
        | email | Email input with validation | No |
        | phone | Phone number input | No |

        Example with all question types:
        {"questions":[
          {"id":"q1","label":"Full name","type":"text","required":true,"placeholder":"Your full name"},
          {"id":"q2","label":"Description","type":"textarea","required":false},
          {"id":"q3","label":"Employee count","type":"number","required":true},
          {"id":"q4","label":"Start date","type":"date","required":false},
          {"id":"q5","label":"Plan type","type":"select","required":true,"options":["Basic","Pro","Enterprise"]},
          {"id":"q6","label":"Services needed","type":"multi_select","required":false,"options":["Bookkeeping","VAT","Payroll"]},
          {"id":"q7","label":"Billing frequency","type":"radio","required":true,"options":["Monthly","Quarterly","Annually"]},
          {"id":"q8","label":"Upload ID","type":"file","required":false},
          {"id":"q9","label":"I agree to terms","type":"checkbox","required":true},
          {"id":"q10","label":"Email address","type":"email","required":true},
          {"id":"q11","label":"Phone","type":"phone","required":false}
        ]}

        ## custom_sections — Structure
        Array of section objects: [{"name":"Overview","content":"<p>HTML here</p>","icon":"FileText","icon_color":"blue","tags":[]}]
        icon_color valid values: blue, green, red, yellow, orange, slate

        ## All Fields
        | Field | Type | Required | Notes |
        |---|---|---|---|
        | id | string | No | Leave blank to create |
        | name | string | Yes | Product display name |
        | category | string | No | Must match an existing category |
        | card_tag | string | No | Small badge label, e.g. "Most Popular" |
        | card_description | string | No | Short card subtitle |
        | card_bullets | JSON array | No | ["Bullet 1","Bullet 2"] |
        | description_long | string | No | Full HTML description |
        | bullets | JSON array | No | Detail page bullet points |
        | base_price | number | No | Price in major currency units |
        | currency | string | No | GBP / USD / EUR |
        | is_subscription | boolean | No | true for recurring, false for one-time |
        | billing_type | string | No | prorata / fixed |
        | billing_cycle | string | No | monthly / annual / quarterly |
        | pricing_type | string | No | fixed / variable / internal |
        | stripe_price_id | string | No | Stripe Price ID (price_XXXX) |
        | is_active | boolean | No | true / false |
        | visible_to_customers | boolean | No | true / false |
        | display_layout | string | No | standard / compact / featured |
        | default_term_months | number | No | Default contract length |
        | show_price_breakdown | boolean | No | Show tax breakdown on checkout |
        | custom_sections | JSON array | No | Array of section objects |
        | intake_schema_json | JSON object | No | Question schema (see above) |
    """),

    "promo-codes": textwrap.dedent("""\
        # Promo Codes Import Guide

        ## Important Notes
        - `discount_type` valid values: percent, fixed
          (Note: use "percent" NOT "percentage")
        - `applies_to` valid values: all, specific, subscription, one_time
        - `applies_to_products`: JSON array of product name strings
        - `product_ids`: JSON array of product UUID strings
        - `expiry_date`: ISO-8601 datetime string: 2025-12-31T23:59:59
        - `enabled`: true / false (replaces the deprecated "is_active" field)
        - `one_time_code`: true = code can only be used once per customer
        - `usage_count`: current number of times the code has been used (read-only in UI)
        - `currency`: leave blank to apply to all currencies; set to e.g. "GBP" to restrict

        ## All Fields
        | Field | Type | Required | Notes |
        |---|---|---|---|
        | id | string | No | Leave blank to create |
        | code | string | Yes | Unique promo code string (uppercase recommended) |
        | discount_type | string | Yes | percent / fixed |
        | discount_value | number | Yes | 20 for 20% off, or 10.00 for £10 off |
        | applies_to | string | No | all / specific / subscription / one_time |
        | applies_to_products | JSON array | No | ["Growth Plan","Starter"] |
        | product_ids | JSON array | No | ["uuid1","uuid2"] |
        | expiry_date | string | No | ISO datetime or YYYY-MM-DD |
        | max_uses | number | No | Maximum total uses (leave blank = unlimited) |
        | usage_count | number | No | Current use count (usually 0 on import) |
        | enabled | boolean | No | true / false (default: true) |
        | one_time_code | boolean | No | true = one use per customer |
        | promo_note | string | No | Internal note (not shown to customers) |
        | currency | string | No | Restrict to currency (blank = all) |
    """),

    "terms": textwrap.dedent("""\
        # Terms & Conditions Import Guide

        ## Important Notes
        - `content` should be valid HTML string.
        - `is_active`: only one terms document can be active at a time. Setting true here does NOT
          automatically deactivate others — use the admin UI to manage active terms.
        - `version`: string or number, e.g. "1", "2.1", "v3"

        ## All Fields
        | Field | Type | Required | Notes |
        |---|---|---|---|
        | id | string | No | Leave blank to create |
        | title | string | Yes | Display name for the terms document |
        | content | string | No | Full HTML content |
        | is_active | boolean | No | true / false |
        | version | string | No | Version label |
    """),

    "categories": textwrap.dedent("""\
        # Product Categories Import Guide

        ## All Fields
        | Field | Type | Required | Notes |
        |---|---|---|---|
        | id | string | No | Leave blank to create |
        | name | string | Yes | Category display name |
        | description | string | No | Short description |
    """),

    "article-categories": textwrap.dedent("""\
        # Article Categories Import Guide

        ## All Fields
        | Field | Type | Required | Notes |
        |---|---|---|---|
        | id | string | No | Leave blank to create |
        | name | string | Yes | Category display name |
        | description | string | No | Short description |
        | color | string | No | Hex color code, e.g. #3b82f6 |
    """),

    "article-templates": textwrap.dedent("""\
        # Article Templates Import Guide

        ## Notes
        - `content` is an HTML string.
        - `category` must match an existing article category name.

        ## All Fields
        | Field | Type | Required | Notes |
        |---|---|---|---|
        | id | string | No | Leave blank to create |
        | name | string | Yes | Template display name |
        | description | string | No | Short description |
        | category | string | No | Must match an existing article category |
        | content | string | No | HTML content |
    """),

    "resources": textwrap.dedent("""\
        # Resources Import Guide

        ## Important Notes
        - `category` must match an existing resource category name.
        - `visibility` valid values: all, customers_only, restricted
        - `restricted_to`: JSON array of customer IDs when visibility = "restricted".
          Example: ["cust-uuid-1","cust-uuid-2"]
        - `price` and `currency`: only required for Scope Final category resources.
        - `slug`: auto-generated from `title` if left blank. Must be URL-safe.
        - `content` is an HTML string.

        ## All Fields
        | Field | Type | Required | Notes |
        |---|---|---|---|
        | id | string | No | Leave blank to create |
        | title | string | Yes | Resource display title |
        | slug | string | No | URL slug — auto-generated from title if blank |
        | category | string | Yes | Must match an existing resource category |
        | content | string | No | HTML content body |
        | visibility | string | No | all / customers_only / restricted |
        | restricted_to | JSON array | No | Customer UUIDs for restricted visibility |
        | price | number | No | Required for Scope Final resources |
        | currency | string | No | GBP / USD / EUR (for Scope Final) |
    """),

    "resource-categories": textwrap.dedent("""\
        # Resource Categories Import Guide

        ## Notes
        - `is_scope_final`: When true, resources in this category require a price.
        - `color`: Hex color code used in the UI.

        ## All Fields
        | Field | Type | Required | Notes |
        |---|---|---|---|
        | id | string | No | Leave blank to create |
        | name | string | Yes | Category display name |
        | description | string | No | Short description |
        | color | string | No | Hex color, e.g. #3b82f6 |
        | is_scope_final | boolean | No | true / false |
    """),

    "resource-templates": textwrap.dedent("""\
        # Resource Templates Import Guide

        ## Notes
        - `category` should match an existing resource category name.
        - `content` is an HTML string used as the default content when creating from template.

        ## All Fields
        | Field | Type | Required | Notes |
        |---|---|---|---|
        | id | string | No | Leave blank to create |
        | name | string | Yes | Template display name |
        | description | string | No | Short description |
        | category | string | No | Resource category name |
        | content | string | No | Default HTML content |
    """),
}

# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/admin/import/template/{entity}")
async def download_import_template(
    entity: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    if entity not in TEMPLATES:
        raise HTTPException(status_code=400, detail=f"Unknown entity: {entity}")
    fields = TEMPLATES[entity]
    sample = SAMPLE_DATA.get(entity, {})
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerow({f: sample.get(f, "") for f in fields})
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="import_template_{entity}.csv"'},
    )


@router.get("/admin/import/template/{entity}/guide")
async def download_import_guide(
    entity: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """Return a Markdown guide for the given import entity."""
    if entity not in GUIDES:
        raise HTTPException(status_code=400, detail=f"No guide available for entity: {entity}")
    guide = GUIDES[entity]
    return StreamingResponse(
        iter([guide]),
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="import_guide_{entity}.md"'},
    )


@router.post("/admin/import/{entity}")
async def import_entity(
    entity: str,
    file: UploadFile = File(...),
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    if entity not in ENTITY_COLLECTIONS:
        raise HTTPException(status_code=400, detail=f"Unknown entity: {entity}")

    collection_name = ENTITY_COLLECTIONS[entity]
    collection = getattr(db, collection_name)
    required = REQUIRED_FIELDS.get(entity, [])
    tid = tenant_id_of(admin)

    content = await file.read()
    try:
        rows = _read_csv(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {e}")

    if not rows:
        raise HTTPException(status_code=400, detail="CSV file is empty or has no data rows")

    created = updated = skipped = 0
    errors: List[Dict[str, Any]] = []

    for row_num, row in enumerate(rows, start=2):  # row 2 = first data row (row 1 = header)
        # Check required fields
        missing = [f for f in required if not row.get(f, "").strip()]
        if missing:
            errors.append({"row": row_num, "error": f"Missing required field(s): {', '.join(missing)}", "data": row})
            continue

        row_id = row.get("id", "").strip()
        existing = None
        if row_id:
            existing = await collection.find_one({"id": row_id, "tenant_id": tid}, {"_id": 0, "id": 1})

        try:
            doc = _build_doc(row, entity, tid, row_id if existing else None)
        except Exception as e:
            errors.append({"row": row_num, "error": f"Row processing error: {e}", "data": row})
            continue

        try:
            if existing:
                # Update — never overwrite id or tenant_id from row data
                update_fields = {k: v for k, v in doc.items() if k not in ("id", "tenant_id", "_id")}
                if update_fields:
                    await collection.update_one({"id": row_id, "tenant_id": tid}, {"$set": update_fields})
                updated += 1
            else:
                # Insert — ensure no _id leaks in
                doc.pop("_id", None)
                if not row_id:
                    doc["id"] = make_id()
                await collection.insert_one(doc)
                created += 1
        except Exception as e:
            errors.append({"row": row_num, "error": f"Database error: {e}", "data": row})
            skipped += 1

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "total": len(rows),
    }
