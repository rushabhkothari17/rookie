# AutomateAccounts Product Requirements Document

## Original Problem Statement
E-commerce platform for professional services with:
- Product catalog with multiple pricing tiers
- Intake forms with conditional logic
- Multiple product page layouts (Classic, QuickBuy, Wizard, Application, Showcase)
- Full-screen admin product editor
- Payment processing (Stripe, GoCardless, Bank Transfer)
- Free product checkout support
- Modern cart experience

## Core Features Implemented

### Product Management
- [x] 5 distinct product page layouts (Classic, QuickBuy, Wizard, Application, Showcase)
- [x] Full-screen product editor at `/admin/products/:id/edit`
- [x] Dynamic layout selection per product
- [x] Advanced intake forms with conditional visibility
- [x] Tiered pricing engine with formulas

### Admin Interface (RESTRUCTURED 2026-02-25)
- [x] **Products tab** now contains: Products, Categories, Promo Codes, Terms (as sub-tabs)
- [x] **Articles tab** now contains: Articles, Templates, Email Templates, Categories, Override Codes (as sub-tabs)
- [x] **Main sidebar** updated:
  - PEOPLE: Users, Customers
  - COMMERCE: Products, Subscriptions, Orders, Requests
  - CONTENT: Articles, Email Templates, References
  - SETTINGS: Website Content, Custom Domains
  - INTEGRATIONS: Connect Services, API, Webhooks, Logs
- [x] **Website Content** streamlined:
  - Removed Payments section (keep in Connected Services)
  - Removed Bank Transaction Form from Forms
  - Removed Email Templates, References, Custom Domains (moved to sidebar)
- [x] Bank Transactions module fully removed

### Cart & Checkout (REDESIGNED 2026-02-25)
- [x] **Two-column layout**: Cart items on left, Order Summary sidebar on right
- [x] **Modern payment method cards**: Bank Transfer (no fee) and Card Payment (5% fee)
- [x] **Increased spacing** between sections (space-y-8, gap-10)
- [x] **Collapsible promo code section**
- [x] **Clean empty cart state** with shopping cart icon and Browse CTA
- [x] **Scope ID validation in Cart** (moved from product pages)
- [x] Free product checkout (total = $0, no payment required)
- [x] Multiple payment methods (Card, Bank Transfer, GoCardless)
- [x] Terms & Conditions acceptance

### Store
- [x] Category sidebar with blurbs
- [x] Blank category filtering (fixed)
- [x] Product search and filters

## Architecture

```
/app/
├── backend/
│   ├── routes/
│   │   ├── catalog.py      - Product CRUD
│   │   ├── checkout.py     - All checkout endpoints including /checkout/free
│   │   ├── store.py        - Public store APIs
│   │   └── uploads.py      - File handling
│   ├── services/
│   │   └── pricing_service.py - Tiered pricing calculations
│   └── server.py
└── frontend/
    └── src/
        ├── pages/
        │   ├── admin/
        │   │   ├── ProductsTab.tsx   - Products/Categories/Promo/Terms tabs
        │   │   ├── ArticlesTab.tsx   - Articles/Templates/Email/Categories/Override tabs
        │   │   ├── WebsiteTab.tsx    - Streamlined (removed payments, references, etc.)
        │   │   ├── EmailTemplatesTab.tsx - NEW standalone tab
        │   │   ├── ReferencesTab.tsx - NEW standalone tab
        │   │   ├── CustomDomainsTab.tsx - NEW standalone tab
        │   │   └── CategoriesTab.tsx
        │   ├── store/
        │   │   ├── ProductDetail.tsx - Layout router
        │   │   └── layouts/          - 5 layout components
        │   ├── Cart.tsx              - REDESIGNED with increased spacing
        │   └── ProductEditor.tsx     - Fixed API endpoint
        ├── components/
        │   └── Store/
        └── App.tsx
```

## Key Endpoints
- `POST /api/checkout/free` - Free product checkout
- `POST /api/checkout/session` - Stripe checkout
- `POST /api/checkout/bank-transfer` - Bank transfer/GoCardless
- `POST /api/orders/preview` - Cart preview with pricing
- `GET /api/admin/products-all` - Admin products list
- `GET /api/products` - Public product list
- `GET /api/categories` - Product categories

## Database Collections
- `products` - Product catalog with `display_layout` field
- `product_categories` - Categories with blurbs
- `orders` - Order records with `payment_method: "free"` support
- `order_items` - Line items with intake answers
- `invoices` - Payment records

## Completed in Latest Session (2026-02-25)
1. ✅ Cart UI/UX complete redesign
2. ✅ Scope ID moved to Cart (from product pages)
3. ✅ **Admin UI restructured**:
   - Products tab: +Promo Codes, +Terms sub-tabs
   - Articles tab: +Override Codes sub-tab
   - Main sidebar: +Email Templates, +References, +Custom Domains
   - Website Content: -Payments, -Bank Transaction Form, -Email, -References, -Domains
4. ✅ Product editing fixed (API endpoint corrected)
5. ✅ Cart spacing increased

## Completed in Latest Session (2026-02-26) — Bug Fixes
1. ✅ **P2 Recurring Bug Fixed (3rd+ time, now closed):** "Edit Article" button was visible to `partner_super_admin` because `user?.is_admin` is `true` for all admin roles. Changed to `user?.role === 'platform_admin'` in `ArticleView.tsx` line 14. Verified: platform_admin sees button ✓, partner_super_admin does NOT see button ✓.
2. ✅ **Duplicate tenant `automate-accs` deleted:** Removed tenant (id: `3e50877e-...`) + 1 user, 1 product, 1 category, 1 article, 1 website_settings, 1 terms doc, 1 email template. Original `automate-accounts` intact.

## Completed in Latest Session (2026-03-[current]) — Security Audit & Hardening

### Security Audit Results (All 10 checks PASS)
1. ✅ Platform admin login via legacy endpoint (no partner_code) works correctly
2. ✅ `partner_login` with `automate-accounts` code is BLOCKED (403) — hardcoded guard added
3. ✅ `customer_login` with `automate-accounts` code is BLOCKED (403)
4. ✅ Customer `register` with `automate-accounts` partner_code is BLOCKED (403)
5. ✅ Create tenant with `automate-accounts` code is BLOCKED (400) — explicit hardcoded guard added
6. ✅ Create partner admin user under platform tenant is BLOCKED (403) — `is_platform` check added
7. ✅ Platform admin can list ALL tenants (unrestricted access)
8. ✅ Platform admin has unrestricted customer access across all tenants
9. ✅ Platform admin has unrestricted order access across all tenants
10. ✅ Unauthenticated access to admin endpoints is blocked

### Security Code Changes Made
- `backend/routes/auth.py` — `partner_login`: Added explicit block for `automate-accounts` code
- `backend/routes/auth.py` — `register_partner`: Hardcoded check added (loop also skips reserved code)
- `backend/routes/admin/tenants.py` — `create_tenant`: Hardcoded block for `automate-accounts` code
- `backend/routes/admin/tenants.py` — `create_partner_admin`: Block creating users under platform tenant
- `backend/server.py` — `seed_admin_user()`: Added `role: "platform_admin"` and `tenant_id: None` to ensure correct role on new deployments

### Access Control Architecture (Confirmed Secure)
- `platform_admin` role: Bypasses all tenant filters → sees ALL data
- `partner_super_admin/admin/staff`: Strictly scoped to their `tenant_id`
- `platform_admin` check: Via `is_platform_admin()` function (role == "platform_admin")
- `X-View-As-Tenant` header: Only honored for `platform_admin` role
- Admin endpoints: Use `get_tenant_admin` → `require_admin` + tenant scoping
- Tenant management: Uses `require_platform_admin` — strictly `platform_admin` only
- `platform_admin` role: Cannot be assigned via admin API (excluded from allowed_roles in user CRUD)

## Completed in Latest Session (2026-03-current) — Articles→Resources Refactor & Platform Admin Overhaul

### What Was Done
1. ✅ **Articles renamed to Resources** everywhere: DB collections, backend routes, frontend files, UI text
2. ✅ **Platform Admin unscoped view**: Admin sees all data from all tenants (Customers, Users, Products, Resources, Orders, Subscriptions) — achieved by removing `tenant_id` filter for `platform_admin` role in all list endpoints
3. ✅ **"Partner" column** added to all admin tables (Customers, Users, Products, Resources, Orders, Subscriptions) — only visible when logged in as `platform_admin`
4. ✅ **Default country fixed** in Create Customer dialog: was `"GB"`, now empty
5. ✅ **Admin sidebar reordered**: "Partner Orgs" now appears before "Users"
6. ✅ **Data enrichment**: `enrich_partner_codes` helper in `backend/core/tenant.py` injects `partner_code` into every admin list response
7. ✅ **ResourceView isAdmin fix**: Extended to include `super_admin` and `partner_super_admin` roles
8. ✅ **`_DT` NameError fixed** in `resources.py` get_article_by_id
9. ✅ **All-Tenants ResourceView** fixed for platform admin (tid=None when no X-View-As-Tenant header)
10. ✅ **SetupChecklistWidget** updated: "Create an article" → "Create a resource"
11. ✅ **DB fix**: admin@automateaccounts.local role corrected to `platform_admin`

### Architecture Changes
- `backend/core/tenant.py` — `enrich_partner_codes()` helper function added
- `backend/routes/resources.py` — replaces articles.py, platform-admin-unscoped
- `backend/routes/resource_categories.py` — replaces article_categories.py
- `backend/routes/admin/customers.py`, `users.py`, `orders.py`, `catalog.py`, `subscriptions.py`, `references.py`, `requests.py`, `terms.py`, `promo_codes.py`, `logs.py` — all enriched with `partner_code`
- `frontend/src/pages/admin/ResourcesTab.tsx` — exports `ResourcesTab` (was `ArticlesTab`)
- `frontend/src/pages/Resources.tsx`, `ResourceView.tsx` — public resource pages
- DB collections renamed: `articles`→`resources`, `article_categories`→`resource_categories`, `article_templates`→`resource_templates`, `article_email_templates`→`resource_email_templates`

### Test Results (iteration_110.json)
- All 10 features tested: 100% PASS
- Platform admin login, Partner columns, multi-tenant data, Resources pages all confirmed working

## Session: 5 QA-Driven Bug Fixes (2026-03-current)

1. ✅ **Promo Code Product-Scope Enforcement** — `store.py` validate endpoint now rejects promos when `applies_to_products=selected` and cart contains ineligible product IDs. Also added `product_ids` to `ApplyPromoRequest` model.
2. ✅ **ZOHOR Sponsorship Note** — When promo code contains "ZOHOR": validate returns `is_sponsored: true`; checkout `notes_json` includes `sponsorship_note`; Cart UI shows amber sponsorship banner. Fixed `/promo/validate` → `/promo-codes/validate` URL mismatch in Cart.tsx.
3. ✅ **Category Rename Cascade** — `admin_update_category` now runs `products.update_many` to update all linked products when category name changes.
4. ✅ **Category Delete Button UX** — Delete button is now `disabled` with a tooltip ("N product(s) linked — reassign them first") when `product_count > 0`. Uses Tooltip component from shadcn/ui.
5. ✅ **Customer Registration partner_code in body** — Added `partner_code: Optional[str]` to `RegisterRequest` model; auth.py register uses `partner_code or payload.partner_code` so both query param and body field work.

## Future Tasks (P2)
- Centralized email integration settings
- Credential forms for "Coming Soon" integrations
- Formal penetration testing
- Verify complex intake form visibility (`AND`/`OR` operators)
- Catalog field ↔ UI layout linkage summary
- Ensure new platform admin accounts are always seeded with `role='platform_admin'` (not `role='custom'`)

## Test Credentials
- Platform Admin: `admin@automateaccounts.local` / `ChangeMe123!`
- Platform Admin Code: `automate-accounts` (reserved — only for platform admin login, NOT partner_login)
- Login path for platform admin: `POST /api/auth/login` without `partner_code`

## Test Reports
- `/app/test_reports/iteration_99.json` — Sidebar restructure tests (100% pass)
- `/app/test_reports/iteration_100.json` — Cart redesign tests (100% pass)
- `/app/test_reports/iteration_101.json` — Admin UI restructuring tests (100% pass)

---
*Last Updated: 2026-03-[current]*
