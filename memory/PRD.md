# Automate Accounts Platform — PRD

## Original Problem Statement
Build a fully configurable, admin-driven SaaS platform for accounting/automation services. All product pricing, intake questions, and catalog content must be manageable from the admin UI without code changes.

## Architecture
```
/app/
├── backend/
│   ├── routes/          # catalog.py, checkout.py, auth.py, etc.
│   ├── services/
│   │   ├── pricing_service.py    # 3-type pricing engine + tiered/boolean/caps
│   │   ├── checkout_service.py
│   │   └── zoho_service.py
│   ├── models.py         # All Pydantic models incl. IntakeQuestion, PricingTier, VisibilityRule
│   ├── server.py
│   └── seed_products.py
└── frontend/
    └── src/
        ├── pages/
        │   ├── admin/
        │   │   ├── ProductForm.tsx      # Light-themed product form (5 tabs)
        │   │   ├── IntakeSchemaBuilder.tsx # Full intake builder with tiered/boolean/visibility
        │   │   ├── ProductsTab.tsx       # Admin catalog management
        │   │   └── (other admin tabs)
        │   ├── ProductDetail.tsx        # Customer-facing product + live price preview
        │   └── Store.tsx
        ├── components/
        │   ├── StickyPurchaseSummary.tsx # Live price with line items breakdown
        │   └── (other components)
        └── types/index.ts
```

## What's Been Implemented

### Phase 1 — Initial Build (Previous sessions)
- Full multi-tenant platform with JWT auth
- Admin panel with Customers, Orders, Subscriptions, Articles, Website settings
- Store/catalog with product cards, product detail pages
- GoCardless + Stripe payment integration
- Zoho Mail transactional email

### Phase 2 — Pricing Architecture Refactor (Session ~7-8)
- Replaced complex pricing model with 3 clean types: `internal`, `external`, `enquiry`
- `internal`: base_price + intake questions → checkout
- `external`: redirect to external_url
- `enquiry`: contact/RFQ form only
- Rewrote pricing_service.py for the new model
- Rewrote seed_products.py with clean schema

### Phase 3 — Codebase Cleanup (Session ~8-9)
- Removed dead DB collections: `pricing_rules`, `terms`, `payment_transactions`
- Removed dead fields from products: `pricing_complexity`, `sku`, `next_steps`, etc.
- Removed `apply_catalog_overrides()` hardcoded function
- Deleted dead files: `migration_script.py`, `OverrideCodesTab.jsx`

### Phase 4 — Admin UI Redesign + Theme Fix (Session ~10, Feb 2026)
- Complete rewrite of `ProductForm.tsx` — dark → light theme matching admin panel
- Complete rewrite of `IntakeSchemaBuilder.tsx` — dark → light theme
- Updated `ProductsTab.tsx` dialog to white/slate light theme
- Color system: `bg-white`, `border-slate-200`, `text-slate-900`, `#1e40af` blue accent, `#0f172a` navy

### Phase 5 — Advanced Intake Question Features (Feb 2026)
- **Tiered pricing** for number fields: progressive tier brackets (from/to/£per unit)
- **Boolean/Yes-No field type**: simple toggle question with optional price_for_yes/price_for_no
- **Price floor & ceiling caps**: schema-level min/max price constraints applied after all calculations
- **Conditional visibility rules**: show/hide questions based on other question's answer (depends_on/operator/value)
- **Live price preview** with itemized line items breakdown in StickyPurchaseSummary
- Customer-facing form only sends visible questions' answers to pricing API

## Key DB Schema — products
```json
{
  "pricing_type": "internal | external | enquiry",
  "base_price": 0,
  "external_url": "string (for external type)",
  "intake_schema_json": {
    "version": 2,
    "price_floor": null,
    "price_ceiling": null,
    "questions": [
      {
        "key": "string",
        "label": "string",
        "type": "dropdown | multiselect | number | boolean | single_line | multi_line",
        "enabled": true,
        "required": false,
        "affects_price": false,
        "price_mode": "add | multiply",
        "options": [{"label":"","value":"","price_value":0}],
        "pricing_mode": "flat | tiered",
        "price_per_unit": 0,
        "tiers": [{"from":0,"to":10,"price_per_unit":5}],
        "price_for_yes": 0,
        "price_for_no": 0,
        "visibility_rule": {
          "depends_on": "question_key",
          "operator": "equals | not_equals | greater_than | less_than | contains | not_empty",
          "value": "string"
        }
      }
    ]
  }
}
```

## Key API Endpoints
- `POST /api/auth/login` — multi-tenant login
- `GET /api/catalog/products` — public product list
- `POST /api/pricing/calc` — calculate price with inputs
- `PUT /api/catalog/products/{id}` — admin update product
- `POST /api/checkout/session` — create checkout session

## Admin Credentials (dev)
- Platform Admin: `admin@automateaccounts.local` / `ChangeMe123!`
- Tenant Admin: `adminb@tenantb.local` / `ChangeMe123!` (partner_code: `tenant-b-test`)

## Prioritized Backlog

### P0 — Critical
- (None currently — all P0 resolved)

### P1 — High Priority
- **Email integration settings**: Centralize email config in admin panel
- **"Coming Soon" integrations**: Gmail, Microsoft Outlook, HubSpot, Salesforce, QuickBooks credential forms

### P2 — Medium Priority
- **Multi-step / wizard form**: Split long questionnaires across pages
- **Date + File upload field types**: For scheduling and document attachment
- **Cross-field formula pricing**: `field_a × field_b × multiplier`
- **Security audit**: Penetration testing

### P3 — Low Priority / Bugs
- **Edit Article button**: Sometimes visible to non-admin users (recurring, 3+ occurrences)
- **Product DELETE endpoint**: Currently only deactivation via PUT
- **GET /api/admin/products/{id}**: Single product admin fetch endpoint

## 3rd Party Integrations
- GoCardless (payment)
- Stripe (payment + subscriptions)
- Zoho Mail (transactional email)
