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
│   │       ├── catalog.py       # Products + Categories CRUD
│   │       ├── quote_requests.py # Quote requests
│   │       ├── bank_transactions.py # Bank transactions
│   │       ├── override_codes.py   # Override codes
│   │       ├── exports.py       # CSV exports for all entities
│   │       └── settings.py      # App settings
│   ├── services/
│   │   ├── audit_service.py    # AuditService class + create_audit_log helper
│   │   ├── pricing_service.py  # build_price_inputs, calculate_price, calculate_books_migration_price
│   │   └── settings_service.py # SettingsService (key-value store with MongoDB)
│   └── server.py               # FastAPI app setup, middleware, all router includes, startup tasks
└── frontend/
    └── src/
        └── pages/
            └── admin/
                └── tabs/   # CustomersTab, OrdersTab, SubscriptionsTab, etc.
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
- The old api_router still remains in server.py as a safety fallback for any edge cases

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

## Phase 4: Audit Log Instrumentation (Completed — Feb 2026)
- AuditService wired into ALL mutation endpoints: auth, customers, orders, subscriptions, users, catalog, promo_codes, terms, quote_requests, bank_transactions, override_codes, articles, settings, misc
- `create_audit_log` helper fixed: PascalCase entity types (PromoCode not Promo_code), correct source (admin_ui vs api), no double-prefix in action names
- LogsTab rebuilt: actor_type filter, page-based pagination with total count, colored badges, relative time, before/after/meta JSON in detail dialog
- Test reports: /app/test_reports/iteration_29.json (28/28 backend, all frontend pass)

## Phase 5: Subscription Filter Bug Fix (Completed — Feb 2026)
- Root cause: Frontend `SUB_STATUSES` was missing `paused` status (existed in DB & backend constants); `gocardless` payment option didn't match DB value `bank_transfer`
- Fix: Added `paused` to `SUB_STATUSES`; removed misleading `gocardless` option from `PAYMENT_METHODS` in `SubscriptionsTab.tsx`
- All 6 status filters and 3 payment filters now accurately reflect DB data
- File: `/app/frontend/src/pages/admin/SubscriptionsTab.tsx`

## Phase 6: Settings Tab Payment Variables Restored + Full Filter Audit (Completed — Feb 2026)
### Settings Restoration
- `stripe_secret_key`, `stripe_publishable_key`, `stripe_webhook_secret`, `gocardless_access_token`, `gocardless_environment` were mistakenly placed in `_OBSOLETE_KEYS` by a previous refactor and deleted on startup
- Removed all 5 from `_OBSOLETE_KEYS`, added to `SETTINGS_DEFAULTS` with env var fallback values
- Checkout, webhook, and GoCardless routes now read keys from SettingsService at request time (DB first, env var fallback)
- `gocardless_helper.py` functions now accept optional `gc_token` and `gc_env` parameters for dynamic routing
- Files: `settings_service.py`, `gocardless_helper.py`, `routes/checkout.py`, `routes/webhooks.py`, `routes/gocardless.py`

### Filter Enum Audit (all admin tabs checked)
| Tab | Issue | Records Affected | Fixed |
|-----|-------|-----------------|-------|
| Subscriptions | `paused` status missing | 2 | ✅ |
| Subscriptions | `gocardless` payment (stored as `bank_transfer`) | misleading | ✅ |
| Orders | `pending_direct_debit_setup` missing | 21 | ✅ |
| Orders | `scope_requested` missing | 3 | ✅ |
| Orders | edit dialog: `gocardless` payment → replaced with `manual` | 5 | ✅ |
| Bank Transactions | `matched` status missing | 5 | ✅ |
| Bank Transactions | `bank_transfer` source missing | 10 | ✅ |
| Bank Transactions | `stripe`/`gocardless` sources not in DB | misleading | ✅ |

## Phase 7: server.py Full Cleanup (Completed — Feb 2026)
- Removed old `api_router` dead code: 6,973 → 2,271 lines in Phase 6
- Extracted `build_seed_products` (458 lines) to `data/seed_products.py`
- Removed all duplicate function definitions (validate_order_status, calculate_books_migration_price, resolve_terms_tags, create_audit_log, build_checkout_notes_json, validate_and_consume_partner_tag, build_price_inputs, calculate_price)
- Removed all duplicate Pydantic model class definitions (all now properly in models.py)
- Replaced with clean imports from their respective service/data modules
- Final server.py: 853 lines (down from 6,973) — 88% reduction
- Files: `server.py`, `data/__init__.py`, `data/seed_products.py`

## Phase 9: Comprehensive Audit Logging (Completed — Feb 2026)

### Summary
All 23 previously identified audit logging gaps have been addressed. Every POST/PUT/DELETE action (internal or external) now writes to BOTH `audit_logs` (entity-level history) AND `audit_trail` (admin Logs tab).

### Group A — Added to BOTH (previously had no audit logging):
1. `PUT /api/me` — user profile update → `profile_updated`
2. `POST /auth/verify-email` — email verification → `email_verified`
3. `POST /orders/scope-request` — customer scope request → `scope_request_created`
4. `POST /orders/scope-request-form` — customer scope form → `scope_request_form_created`
5. `POST /subscriptions/{id}/cancel` — customer cancels subscription → `cancellation_requested`
6. `PUT /admin/customers/{id}/payment-methods` — payment method update → `payment_methods_updated`
7. `POST /admin/sync-logs/{id}/retry` — Zoho sync retry → `sync_retry`
8. `PUT /admin/products/{id}/terms` — terms assignment → `terms_assigned`/`terms_removed`
9. `POST /admin/upload-logo` — logo upload → `logo_uploaded`

### Group B — Added audit_logs write (previously audit_trail only):
10. `POST /auth/register` — registration
11. `POST /auth/login` — login
12-14. Article CRUD (create, update, delete) + email action
15-17. Bank transaction CRUD
18-20. Quote request (submit, create, update)
21-22. Settings bulk update + single key update

### New Backend /logs Endpoints:
- `GET /admin/customers/{id}/logs`
- `GET /admin/users/{id}/logs`
- `GET /admin/products/{id}/logs`
- `GET /admin/promo-codes/{id}/logs`
- `GET /admin/override-codes/{id}/logs`
- `GET /admin/quote-requests/{id}/logs`
- `GET /admin/terms/{id}/logs`
- `GET /admin/bank-transactions/{id}/logs` — updated to merge inline + audit_logs

### Frontend Logs Buttons Added:
- Users, Customers, Products, PromoCodes, OverrideCodes, QuoteRequests, Terms tabs all have per-row "Logs" button that opens an audit log dialog.

- Test reports: `/app/test_reports/iteration_32.json` (39/39 backend, 100% frontend)
### Stripe Import Fix
- Root cause: `checkout.py` imported from `emergentintegrations.payments.stripe` but that `__init__.py` only exports `StripeCheckout` and `CheckoutError`. `CheckoutSessionRequest`, etc. are only in the `.checkout` submodule.
- Fix: Changed import to `from emergentintegrations.payments.stripe.checkout import ...`
- Result: Stripe checkout flows fully restored (returns valid `checkout.stripe.com` URL)

### GoCardless Webhook Secret Fix
- Root cause: `gocardless_webhook_secret` was never added to `SETTINGS_DEFAULTS` in `settings_service.py` during settings refactor.
- Fix: Added entry to `SETTINGS_DEFAULTS` with `is_secret=True`, `category=Payments`
- Files: `routes/checkout.py`, `services/settings_service.py`
- Test reports: `/app/test_reports/iteration_31.json` (24/24 pass, 100%)

## Phase 11: Filter System Overhaul + Checkout Data Completeness (Feb 2026)

### Root Cause Fixed (Recurring Filter Bug)
- **Single source of truth**: Added `GET /api/admin/filter-options` endpoint in `subscriptions.py` returning values from `constants.py`. Both OrdersTab and SubscriptionsTab (and BankTransactionsTab) now load their status/payment method dropdowns from this endpoint on mount with fallback defaults. No more frontend ↔ backend drift.

### Checkout Flow Completeness
- **Stripe subscriptions** (`checkout_status`): Now fetches actual Stripe PaymentIntent ID (`pi_xxx`) from the checkout session via `stripe.checkout.Session.retrieve(expand=["payment_intent","subscription"])`. Stores `pi_xxx` as `processor_id`. All subscription fields populated: `subscription_number`, `created_at`, `start_date`, `renewal_date`, `contract_end_date`, `product_id`, `notes`, `internal_note`, `stripe_subscription_id`. Order back-filled with `subscription_id`, `subscription_number`, `payment_date`.
- **GoCardless subscriptions**: Added `subscription_number`, `created_at`, `updated_at`, `renewal_date`, `product_id`, `notes`, `internal_note`.
- **Order subscription_id update**: Backend auto-resolves `subscription_number` when `subscription_id` is set via admin edit.
- **Existing data patched**: SUB-7EF107CB (renewal_date), AA-7BE7DB36 (payment_date, subscription_id, subscription_number).

### New Filters
- **Subscriptions**: sub#, processor ID, plan name, renewal date range, method
- **Orders**: sub#, processor ID, payment method, payment date range
- **Backend**: New query params on `GET /admin/subscriptions` and `GET /admin/orders`

### Deep-Link Enhancement
- Added `cs_` prefix → `https://dashboard.stripe.com/checkout/sessions/{id}` in `getProcessorLink`
- Added `pending_direct_debit_setup` to `ALLOWED_SUBSCRIPTION_STATUSES`
- Added `ALLOWED_PAYMENT_METHODS` and `ALLOWED_BANK_TRANSACTION_STATUSES` to `constants.py`

### Portal Fix
- Fixed `TypeError: Cannot read properties of undefined (reading 'toFixed')` — all `.toFixed()` calls now null-safe
- Test report: `/app/test_reports/iteration_36.json` (24/24 backend + frontend = 100%)

### Summary
Admin can now one-click open any Stripe or GoCardless payment/subscription in the provider's dashboard directly from the Orders or Subscriptions table. The processor_id is also editable via the Edit dialog.

### Changes
- `OrdersTab.tsx` + `SubscriptionsTab.tsx`: `getProcessorLink()` helper maps ID prefixes to dashboard URLs:
  - `pi_` / `ch_` → `https://dashboard.stripe.com/payments/{id}`
  - `sub_` → `https://dashboard.stripe.com/subscriptions/{id}`
  - `cus_` → `https://dashboard.stripe.com/customers/{id}`
  - `in_` → `https://dashboard.stripe.com/invoices/{id}`
  - `PM` → `https://manage.gocardless.com/payments/{id}`
  - `MD` → `https://manage.gocardless.com/mandates/{id}`
  - `SB` → `https://manage.gocardless.com/subscriptions/{id}`
- Table cell renders blue clickable badge with ExternalLink icon for known prefixes; plain badge for unknown
- Edit dialog: new `processor_id` text input (pre-filled); inline ExternalLink button opens dashboard
- `models.py`: Added `processor_id: Optional[str] = None` to both `OrderUpdate` and `SubscriptionUpdate`
- `routes/admin/orders.py` + `routes/admin/subscriptions.py`: Handle `processor_id` in PUT with audit logging (`changes.processor_id`)
- Test report: `/app/test_reports/iteration_35.json` (18/18 backend + 13/13 frontend = 100%)

## Known Issues / Technical Debt
- HTML hydration warning `<span> cannot be child of <select>/<option>` — caused by Emergent VE browser wrapper injecting spans. **Not fixable in application code.** Non-blocking.
- Old audit_trail entries may have `Promo_code` entity_type; new entries use `PromoCode`
- Orders email filter is client-side only (filters current page only, not all pages)

## Prioritized Backlog

### P0 — Must Have
- ~~Remove old api_router endpoint definitions from server.py~~ Done
- ~~Fix Stripe checkout (incorrect import path)~~ Done
- ~~Fix GoCardless checkout (missing webhook secret in settings)~~ Done
- ~~Processor ID deep-link + edit~~ Done

### P1 — High Value
- **Admin Dashboard**: visual metrics for revenue, subscriptions, orders, recent activity (charts, KPI cards)
- Production monitoring + error alerting

### P2 — Nice to Have
- Zoho CRM & Books integration (sync customers, orders)
- Email notifications for Quote Requests submitted
- PostgreSQL migration (if scale requires it)

## Test Reports
- `/app/test_reports/iteration_28.json` — Backend refactor regression test (61/61 pass, 100%)
- `/app/test_reports/iteration_29.json` — Audit log instrumentation (28/28 pass, 100%)
- `/app/test_reports/iteration_30.json` — Full E2E QA pass (95.8% backend, 90% frontend)
- `/app/test_reports/iteration_31.json` — P0 checkout bug fixes (24/24 pass, 100%)
- `/app/test_reports/iteration_35.json` — Processor ID deep-link + edit (18/18 backend, 13/13 frontend, 100%)
- `/app/backend/tests/test_iter35_processor_id.py` — Processor ID test suite
