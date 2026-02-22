# Product Requirements Document — Automate Accounts Admin Portal

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

## Known Issues / Technical Debt
- server.py still contains old `api_router` (~6000 lines) as safety fallback. Remove after production validation.
- HTML hydration warning in admin dropdowns (non-blocking, Radix UI issue)
- Old audit_trail entries may have `Promo_code` entity_type; new entries use `PromoCode`

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
