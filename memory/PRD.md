# Product Requirements Document — Automate Accounts Admin Portal
_Last updated: Feb 2026_

## Original Problem Statement
Build a full-featured admin panel for "Automate Accounts" — a Zoho automation consultancy. The platform provides:
- Customer-facing product store with complex pricing (fixed, tiered, calculator, scope request)
- Admin panel for managing customers, orders, subscriptions, products, users, financials, and content
- Integrations: Stripe (card payments), GoCardless (Direct Debit), Resend (email)

## Architecture

```
/app/
├── backend/
│   ├── core/
│   │   ├── config.py       # env vars: JWT_SECRET, STRIPE_API_KEY, ADMIN credentials
│   │   ├── constants.py    # ALLOWED_ORDER/SUBSCRIPTION_STATUSES, ARTICLE_CATEGORIES, etc.
│   │   ├── helpers.py      # make_id, now_iso, round_cents, _slugify, currency_for_country
│   │   └── security.py     # pwd_context, JWT helpers, get_current_user, require_admin, require_super_admin
│   ├── db/
│   │   └── session.py      # MongoDB connection (db, client)
│   ├── middleware/
│   │   ├── audit.py        # audit middleware
│   │   └── request_id.py   # RequestID middleware
│   ├── models/
│   │   └── models.py       # Pydantic request/response models (in /app/backend/models.py)
│   ├── routes/
│   │   ├── auth.py          # Auth + profile endpoints
│   │   ├── store.py         # Store (products, categories, orders, subscriptions)
│   │   ├── checkout.py      # Stripe + bank transfer checkout
│   │   ├── gocardless.py    # GoCardless redirect flow
│   │   ├── webhooks.py      # Stripe webhooks
│   │   ├── articles.py      # Articles CRUD + email
│   │   └── admin/
│   │       ├── logs.py          # Audit logs
│   │       ├── misc.py          # currency-override, sync-logs, partner-map, notes
│   │       ├── promo_codes.py   # Promo codes admin
│   │       ├── terms.py         # Terms & Conditions admin
│   │       ├── customers.py     # Customer management
│   │       ├── orders.py        # Order management
│   │       ├── subscriptions.py # Subscription management
│   │       ├── users.py         # Admin user management
│   │       ├── catalog.py       # Products + Categories CRUD (updated with custom_sections)
│   │       ├── quote_requests.py # Quote requests
│   │       ├── bank_transactions.py # Bank transactions
│   │       ├── override_codes.py   # Override codes
│   │       ├── exports.py       # CSV exports for all entities
│   │       └── settings.py      # App settings
│   ├── services/
│   │   ├── audit_service.py    # AuditService class + create_audit_log helper
│   │   ├── pricing_service.py  # build_price_inputs, calculate_price, calculate_books_migration_price
│   │   └── settings_service.py # SettingsService (key-value store with MongoDB)
│   ├── migration_script.py  # One-time migration: old static sections → custom_sections (NOT run yet)
│   └── server.py               # FastAPI app setup, middleware, all router includes, startup tasks
└── frontend/
    └── src/
        └── pages/
            ├── admin/
            │   ├── ProductForm.tsx       # Tabbed layout (General/Pricing/Intake/Page Content)
            │   ├── SectionsEditor.tsx    # Custom sections editor (NEW)
            │   ├── IntakeSchemaBuilder.tsx # Read-only keys, auto-gen option values
            │   ├── ProductsTab.tsx       # Updated productToForm + handleSave
            │   └── tabs/   # CustomersTab, OrdersTab, SubscriptionsTab, etc.
            └── ProductDetail.tsx  # Dynamic custom_sections rendering with fallback
```

## What's Been Implemented

### Phase 1: Admin Panel UI (Completed)
- Full admin panel with 14 tabs: Users, Customers, Subscriptions, Orders, Quote Requests, Bank Transactions, Articles, Categories, Catalog, Terms, Override Codes, Promo Codes, Settings, Logs
- Server-side pagination, filtering, sorting across all admin tables
- CSV export for all major entities
- Searchable email typeahead in product edit form (visible_to_customers)
- Consistent `text-sm` font sizing across all admin tables

### Phase 2: UI Bug Fixes (Completed)
- Fixed inconsistent font sizes in CustomersTab.tsx, SubscriptionsTab.tsx
- Implemented searchable email typeahead for product visibility (ProductForm.tsx)
- All UI issues verified by testing agent (100% pass rate)

### Phase 3: Backend Refactoring (Completed — Feb 2026)
- Migrated all endpoints from monolithic server.py into 20 route modules
- Modular structure: routes/, services/, models/, core/, db/, middleware/
- All 61 backend tests pass (100% pass rate)
- server.py cleaned up: removed duplicate constants, all new routers wired

## Tech Stack
- Frontend: React + TypeScript, Tailwind CSS, Shadcn/UI
- Backend: FastAPI (Python), Motor (async MongoDB)
- Database: MongoDB
- Auth: JWT tokens
- Payments: Stripe (card), GoCardless (Direct Debit)
- Email: Resend

## 3rd Party Integrations
- **Stripe**: Checkout sessions, webhook events, payment intents
- **GoCardless**: Redirect flow for Direct Debit mandates, payment creation
- **Resend**: Article email delivery

## Admin Credentials (test)
- Email: admin@automateaccounts.local
- Password: ChangeMe123!

### Phase 15: Product Experience Overhaul (Completed — Feb 2026)

#### Summary
Complete overhaul of product creation/editing experience and customer-facing product pages.

#### Backend Changes
- **New `CustomSection` Pydantic model** in `models.py`: fields `id`, `name`, `content`, `icon`, `icon_color`, `tags`, `order`
- **`custom_sections` field added** to both `AdminProductCreate` and `AdminProductUpdate` models
- **Auto-generation helpers** in `catalog.py`:
  - `_normalize_schema_dict()`: auto-generates intake question keys from labels (if empty)
  - Auto-generates intake option values from labels (if empty)
  - `_build_sections()`: ensures all sections have unique IDs, consistent order
- **Default section auto-created**: new products without `custom_sections` get a default "Overview" section
- **Migration script** at `/app/backend/migration_script.py`: converts old static fields (outcome, automation_details, support_details, inclusions, exclusions, requirements, next_steps) into `custom_sections` array. **NOT run yet — requires admin approval.**

#### Admin UI Changes
- **ProductForm.tsx** fully rewritten with **4-tab layout**:
  - **General**: Name, Tag, Category, Short Description, Description, Key Bullets (dynamic 1–10), visibility
  - **Pricing**: Base Price, Price Rounding, Subscription, Stripe Price ID, Terms
  - **Intake Questions**: existing IntakeSchemaBuilder
  - **Page Content**: SectionsEditor + FAQs
- **SectionsEditor.tsx** (new file): add/remove/reorder up to 10 custom sections, each with name, icon (24 Lucide icons), icon color (6 colors), markdown content, optional tags
- **IntakeSchemaBuilder.tsx** updated:
  - Question `key` field is now **read-only** (displayed as auto-generated from label)
  - Option `value` input **removed** — auto-generated from option label
- **ProductsTab.tsx** updated: `productToForm` maps `custom_sections`, `handleSave` sends `custom_sections` in payload

#### Customer UI Changes
- **ProductDetail.tsx**: renders `custom_sections` dynamically (with icon, color, content, tags); falls back to old static section rendering if `custom_sections` is empty
- **OfferingCard.tsx**: shows `product.tag` (custom tag field), `product.short_description`, ALL bullets (no 3-bullet limit)
- **SectionCard.tsx**: enhanced with optional `icon` and `iconColor` props (dynamic Lucide icon rendering)

#### Key DB Schema Change
- **ADD**: `custom_sections: List[object]` to products collection
- **Future (migration)**: Remove `outcome`, `automation_details`, `support_details`, `inclusions`, `exclusions`, `requirements`, `next_steps` after migration is run

- Test report: `/app/test_reports/iteration_40.json` (10/10 backend, 100% frontend)

### Phase 15b: Product Page Bug Fixes & Migration (Feb 2026)

- **Icon picker fix**: Dynamic Tailwind classes purged at build time → fixed by switching to inline `style={{ color/backgroundColor: hex }}` in SectionsEditor and SectionCard
- **Category dropdown staleness fix**: `useEffect` on `showDialog` state in ProductsTab re-fetches categories each time the form opens
- **ProductHero hardcoded content removed**: `outcomeCopy()` fallback function eliminated; hero now shows only `description_long` + `bullets` from the product record
- **Legacy sections removed from ProductDetail**: Fallback rendering (inclusions/exclusions/requirements/next_steps) removed entirely; page now only shows `custom_sections` + FAQs
- **react-markdown added**: Custom section content now rendered as proper HTML (bullets, ordered lists, bold, etc.)
- **Migration ran**: 21 products migrated from old static fields → `custom_sections`; 8 products already had sections (skipped)
- Test report: `/app/test_reports/iteration_41.json` (12/12 backend, 100% frontend)

## Known Issues / Technical Debt
- HTML hydration warning `<span> cannot be child of <select>/<option>` — caused by Emergent VE browser wrapper. **Not fixable in application code.** Non-blocking.
- Section content in `ProductDetail.tsx` is rendered with `whitespace-pre-wrap` (plain text). Markdown formatting like `- bullet` shows as literal dashes, not HTML bullets. Admin form says "Markdown supported" meaning admins can TYPE markdown syntax — rendering is plain text. A markdown library (react-markdown) could be added if proper rendering is desired.
- Migration script at `/app/backend/migration_script.py` is READY but **NOT RUN**. Requires explicit admin approval.
- Old audit_trail entries may have `Promo_code` entity_type; new entries use `PromoCode`
- Orders email filter is client-side only (filters current page only)

## Prioritized Backlog

### P0 — Done
- ~~Custom Sections + Product Form Overhaul~~ Done (Phase 15)
- ~~Remove old api_router endpoint definitions from server.py~~ Done
- ~~Fix Stripe checkout (incorrect import path)~~ Done
- ~~Fix GoCardless checkout (missing webhook secret in settings)~~ Done

### P1 — High Value
- **Run Migration Script**: After admin verifies new product form, run `python /app/backend/migration_script.py` to migrate existing products to custom_sections
- **Admin Dashboard**: visual metrics for revenue, subscriptions, orders, recent activity (charts, KPI cards)
- **Markdown rendering**: Add react-markdown for proper markdown rendering in custom sections on ProductDetail

### P2 — Nice to Have
- Zoho CRM & Books integration (sync customers, orders)
- Email notifications for Quote Requests submitted
- PostgreSQL migration (if scale requires it)

## Test Reports
- `/app/test_reports/iteration_28.json` — Backend refactor regression test (61/61 pass, 100%)
- `/app/test_reports/iteration_29.json` — Audit log instrumentation (28/28 pass, 100%)
- `/app/test_reports/iteration_38.json` — Intake Questions Schema (20/20 backend, 100% frontend)
- `/app/test_reports/iteration_39.json` — Pricing Overhaul (27/27 backend, 100% frontend)
- `/app/test_reports/iteration_40.json` — Product Experience Overhaul (10/10 backend, 100% frontend)
