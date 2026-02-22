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

## Known Issues / Technical Debt
- HTML hydration warning in admin dropdowns (non-blocking, Radix UI issue)
- Old audit_trail entries may have `Promo_code` entity_type; new entries use `PromoCode`
- Orders email filter is client-side only (filters current page only, not all pages)

## Prioritized Backlog

### P0 — Must Have
- Remove old api_router endpoint definitions from server.py (final cleanup)

### P1 — High Value
- Audit Log Instrumentation: instrument all routes to use AuditService for comprehensive logging
- Production monitoring + error alerting

### P2 — Nice to Have
- Zoho CRM & Books integration (sync customers, orders)
- Email notifications for Quote Requests submitted
- PostgreSQL migration (if scale requires it)

## Test Reports
- `/app/test_reports/iteration_5.json` — UI bug fix verification (100% pass)
- `/app/test_reports/iteration_28.json` — Backend refactor regression test (61/61 pass, 100%)
- `/app/test_reports/iteration_29.json` — Audit log instrumentation (28/28 pass, 100%)
- `/app/test_reports/iteration_30.json` — Full E2E QA pass (95.8% backend, 90% frontend, 1 critical cart crash fixed)
- `/app/backend/tests/test_refactored_routes.py` — Pytest suite for all new route modules
