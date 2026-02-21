# Automate Accounts E-Store - Product Requirements Document

## Overview
Production-ready, login-gated e-store for Automate Accounts providing Zoho services including setup, customization, migrations, training, and ongoing support.

## Tech Stack
- **Frontend**: React + TypeScript, TailwindCSS, Shadcn UI
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **Payments**: Stripe (Card), GoCardless (Bank Transfer - ready for integration)
- **Auth**: JWT with email verification

## Recent P0 Fixes (Feb 20, 2026)

### 1. Signup Validation ✅
- All fields required EXCEPT Address Line 2
- Added new required field: **Job Title**
- Country determined at signup and locked thereafter

### 2. Country Lock ✅
- Profile page: Country field is read-only/disabled
- Backend: Rejects any country change attempts (403 error) for non-admin users

### 3. Promo Code System ✅
- **Admin Panel**: Full promo code management
  - Create/edit/toggle promo codes
  - Fields: code, discount_type, discount_value, applies_to, expiry_date, max_uses, one_time_code, enabled
  - Computed Status column: Active/Inactive
- **Checkout**: Promo code input with Apply button
- **Calculation**: Discount applied BEFORE fee → fee = 5% * (subtotal - discount)
- **Persisted**: promo_code, discount_amount stored on Order

### 4. View Details Behavior ✅
- Opens in SAME tab (removed target=_blank)

### 5. Naming Fix ✅
- "Managed Services" everywhere (fixed "Manages Services" typo)

### 6. Fixed-Scope Development ✅
- Request Scope button opens modal
- Form captures: project_summary, desired_outcomes, apps_involved, timeline_urgency, budget_range, additional_notes
- Creates scope_request order and sends email to rushabh@automateaccounts.com (MOCKED)

### 7. Duplicate Product Fix ✅
- "Historical Accounting & Data Cleanup" now appears only once

### 8. Admin Improvements ✅
- **Catalog Tab**: Billing Type column (One-time/Subscription badges) + filter dropdown
- **Orders Tab**: All required columns (Date, Amount paid, Fee, Customer name, Customer email, Payment method, Products) + date range/email filters

### 9. Store Personalization ✅
- Header shows "Hi, {firstName}" for logged-in users

### 10. GoCardless Readiness ✅
- Sandbox token stored: `sandbox_gZiP8udcwMBiBek0c9EIbBdi33tB7qIOzfHAE3AN`
- Ready for future integration

## Core Features

### Authentication & Authorization ✅
- User registration with email verification + job title field
- Login with JWT tokens
- Auth-gated store access
- Admin role with elevated permissions
- **Admin Credentials**: admin@automateaccounts.local / ChangeMe123!

### Product Catalog ✅
- 22 products across 6 categories
- Category tabs with horizontal pill navigation
- Product detail pages with pricing breakdown
- Price inputs (selectors, hour pickers, etc.)

### Payment Methods ✅
- **Bank Transfer (GoCardless)** - Default, no fee
  - Creates order with status `awaiting_bank_transfer`
- **Card Payment (Stripe)** - 5% processing fee
  - Only available if admin enables per customer

### Promo Codes ✅
- Percent or fixed discount
- Apply to one-time, subscription, or both
- Expiry date, max uses, one-time per customer options
- Discount applied before fee calculation

## Category Structure
1. Zoho Express Setup
2. Migrate to Zoho
3. Managed Services ← Fixed naming
4. Build & Automate
5. Accounting on Zoho
6. Audit & Optimize

## Data Models

### Users
```json
{
  "id": "string",
  "email": "string",
  "password_hash": "string",
  "full_name": "string",
  "job_title": "string",  // NEW - required
  "is_verified": "boolean",
  "is_admin": "boolean"
}
```

### Customers
```json
{
  "id": "string",
  "user_id": "string",
  "company_name": "string",
  "phone": "string",
  "currency": "USD|CAD",
  "allow_bank_transfer": "boolean (default: true)",
  "allow_card_payment": "boolean (default: false)"
}
```

### Promo Codes (NEW)
```json
{
  "id": "string",
  "code": "string (unique, uppercase)",
  "discount_type": "percent|fixed",
  "discount_value": "number",
  "applies_to": "one-time|subscription|both",
  "expiry_date": "string|null",
  "max_uses": "number|null",
  "one_time_code": "boolean",
  "usage_count": "number",
  "enabled": "boolean"
}
```

### Orders
```json
{
  "id": "string",
  "order_number": "string",
  "customer_id": "string",
  "status": "pending|paid|awaiting_bank_transfer|cancelled|scope_pending",
  "subtotal": "number",
  "discount_amount": "number",  // NEW
  "promo_code": "string|null",  // NEW
  "fee": "number",
  "total": "number",
  "currency": "USD|CAD",
  "payment_method": "bank_transfer|card",
  "type": "one_time|subscription_start|subscription_renewal|scope_request"
}
```

## API Endpoints

### Authentication
- `POST /api/auth/register` - User registration (requires job_title)
- `POST /api/auth/login` - User login

### Promo Codes
- `GET /api/admin/promo-codes` - List all promo codes (admin)
- `POST /api/admin/promo-codes` - Create promo code (admin)
- `PUT /api/admin/promo-codes/{id}` - Update promo code (admin)
- `DELETE /api/admin/promo-codes/{id}` - Delete promo code (admin)
- `POST /api/promo-codes/validate` - Validate promo code (user)

### Checkout
- `POST /api/checkout/session` - Create Stripe checkout (supports promo_code)
- `POST /api/checkout/bank-transfer` - Create bank transfer order (supports promo_code)

### Scope Request
- `POST /api/orders/scope-request-form` - Submit scope request with form data

## Mocked Integrations
- **GoCardless/Bank Transfer**: Creates order with status only
- **Zoho CRM & Books**: Creates log entries instead of API calls
- **Email to rushabh@automateaccounts.com**: Creates email_outbox entry, not actually sent

## Inactive Users/Customers + CSV Export (Feb 21, 2026) ✅

### Inactive Users/Customers
- `is_active` field added to users (startup migration backfills `True` for all)
- Login rejects inactive users with `403: Account is inactive`
- `get_current_user` also rejects → existing tokens stop working immediately  
- `PATCH /admin/users/{id}/active?active=false` — super_admin only; self-deactivation blocked
- `PATCH /admin/customers/{id}/active?active=false` — any admin; cascades to linked user; self-lockout protection at both backend and frontend level
- Status badge (Active/Inactive) shown in Customers + Users tabs
- Deactivate/Activate button per row — hidden on own account row
- All toggles audit-logged with actor + before/after

### CSV Exports
- `GET /api/admin/export/orders` — all DB fields + enriched customer email/name; same filters as list
- `GET /api/admin/export/customers` — all DB fields + address + user fields merged
- `GET /api/admin/export/subscriptions` — all DB fields + enriched customer info; same filters
- `GET /api/admin/export/catalog` — all DB product fields
- Export CSV buttons on all 4 tabs (Orders, Customers, Subscriptions, Catalog)
- Downloads via `fetch + Bearer token + Blob` using `aa_token` localStorage key
- Filenames include date: `orders_2026-02-21.csv`

## Product & Category Management System + Settings Tab (Feb 21, 2026) ✅

### New Backend Endpoints
- `GET /api/settings/public` - Public brand settings (logo, colors, store name)
- `GET/PUT /api/admin/settings` - Admin settings management (secrets masked)
- `POST /api/admin/upload-logo` - Logo upload (stored as base64 in MongoDB)
- `GET/POST /api/admin/categories` - Category CRUD
- `PUT/DELETE /api/admin/categories/{id}` - Category update/delete
- `GET /api/admin/products-all` - All products including inactive (admin only)
- `POST /api/admin/products` - Create new product with full model
- `PUT /api/admin/products/{id}` - Expanded product update (all new fields)
- `POST /api/products/request-quote` - Submit quote request (saved to DB, email TBD)
- `GET /api/admin/quote-requests` - List quote requests

### New Product Fields
- `short_description`, `bullets` (3 fixed), `tag`, `outcome`
- `automation_details`, `support_details`
- `inclusions`, `exclusions`, `requirements`, `next_steps` (dynamic lists)
- `faqs` (Q&A pairs, dynamic)
- `pricing_complexity`: SIMPLE | COMPLEX | REQUEST_FOR_QUOTE
- `visible_to_customers` (list of customer IDs, empty = all)

### Product Visibility Logic
- Only `is_active=True` products shown on storefront
- If product's category is inactive → product hidden
- If `visible_to_customers` is non-empty → only those customers see it
- Inactive product direct URL access blocked for non-admins (404)

### Frontend New Components
- `/pages/admin/ProductsTab.tsx` - Full product CRUD table with filters
- `/pages/admin/CategoriesTab.tsx` - Category CRUD with active/inactive toggle
- `/pages/admin/ProductForm.tsx` - Complete product form with dynamic lists
- `/pages/admin/SettingsTab.tsx` - API keys, brand colors, logo upload

### Admin Panel Updates
- New tabs: **Categories** and **Settings** added
- **Catalog tab** now uses ProductsTab (full CRUD replacing simple table)
- `Admin.tsx` refactored to import tab components

### Storefront Updates
- `TopNav.tsx` fetches logo/store_name from `/api/settings/public`
- `ProductDetail.tsx` shows "Request a Quote" modal for COMPLEX/REQUEST_FOR_QUOTE
- `ProductHero.tsx` uses actual `outcome`, `automation_details`, `support_details` fields

### Bug Fixes Round 2 (Feb 2026)
- Category deletion blocked (409) if products linked; client-side check + product count column
- Category description field added (create/edit/view); descriptions seeded from CATEGORY_BLURBS
- Manual quote request CRUD from admin (create/edit with product, customer, contact, status)
- Admin tab order: Users, Customers, Subscriptions, Orders, Quote Requests, Categories, Catalog, Terms, Promos, Settings, Zoho sync
- Promo tab: Status filter, Code filter, Date Created column
- Terms tab: Products Linked column (assign terms via Catalog > Edit), Status filter
- Catalog table: Preview link per product row (opens product detail in new tab)
- Processing fee hidden from product detail page (only Total shown)
- Store category blurbs loaded from /api/categories endpoint (dynamic)
- Store.tsx finalList includes all categories beyond static CATEGORY_ORDER

## Bug Fix Batch (Feb 2026) ✅

- **Product detail spacing**: Switched to `flex flex-col gap-6` + `pb-8` on SectionCard — boxes no longer touch.
- **Color theme**: Active category tab → dark navy. `View details` link → dark slate. Red kept only as thin accent lines/dots.
- **Admin cancel button**: IIFE-based `contract_end_date` check — hidden when contract is active, shows "Contract active" hint.
- **Stripe trial_end**: Added Yes/No radio (Start today / Future date). Future date enforces 3-day minimum. Backend validates + skips trial if no future date.
- **GoCardless subtotal**: `subtotal` field made `Optional` in `CompleteGoCardlessRedirect` — endpoint now accepts requests without it (backend reads from DB).



### Quick Fixes
- **Add to Cart logic**: COMPLEX pricing products with a calculated price > $0 now show "Add to Cart" (not "Request Quote"). Only `REQUEST_FOR_QUOTE` type (or COMPLEX with $0 price) shows the quote button.
- **Key Bullets bug**: `OfferingCard` now reads `product.bullets` field (from admin KEY BULLETS), fixing cards not showing bullets.
- **Product detail spacing**: Sections now use `space-y-8` (32px) for clearer visual separation.
- **Currency fix**: Removed hardcoded "All prices in CAD" — now displays user's actual currency from AuthContext.
- **Color theme**: CTA buttons changed from red to dark navy (`bg-slate-900`). Red remains only as accent decorators (lines, dots, active tabs).

### New Features
- **Subscription Contract End Date**: 
  - Default = start_date + 12 months, stored in DB.
  - Startup migration backfills existing subscriptions.
  - New "Contract End" column in admin subscriptions table.
  - Editable in edit modal (logged to audit trail).
  - Portal: cancel button hidden until contract end date passes; shows "Contract active until [date]" message instead.
- **Bank Transactions Tab** (admin): Full CRUD for manual transaction log. Fields: date, source, txn ID, type, amount, fees, net, currency, status, description, linked order, notes. Filters, logs per transaction, export CSV.
- **Subscription Start Date at checkout**: Date picker in cart for subscription products (any date within next 30 days). Passed to Stripe as `trial_end` (scheduled billing start). GoCardless: stored `start_date` used as `charge_date` for first payment.



### Changes Made
- **Global CSS**: `--aa-accent` changed from blue (#2563eb) to red (#dc2626) for brand identity
- **Background gradient**: Updated to use subtle red tints instead of purple/indigo
- **TopNav**: Removed "Portal" and "My Profile" from main nav bar (still in dropdown). Added CSS var application from settings on load.
- **ProductHero**: Completely redesigned — dark navy (#0f172a) hero banner with red accent dash, category label, product title & description. Tag pills REMOVED.
- **SectionCard**: Red left-border accent on all section headers
- **StickyPurchaseSummary**: Red CTA button, cleaner price display with icons
- **OfferingCard**: Clean white card with red "View details" link (replaced blue button)
- **Store Hero**: Dark navy banner matching brand identity
- **CategoryTabs**: Active tab now uses red background (was dark navy)
- **Admin Settings**: Colors updated to proper brand defaults (Primary #0f172a, Accent #dc2626)

### Bug Fix
- **Category navigation bug**: Fixed `categoryFromSlug` in `lib/categories.ts` — now handles space-to-hyphen conversion for custom categories (e.g. "Test Category" → slug "test-category" now maps correctly back)


- `CategoryTabs.tsx` now fetches from `GET /api/categories` dynamically (new categories appear automatically)
- `Store.tsx` `finalList` now includes new categories beyond CATEGORY_ORDER
- `productToForm` maps legacy fields: `bullets_included→inclusions`, `bullets_excluded→exclusions`, `bullets_needed→requirements`
- Startup migration backfills `pricing_complexity` based on `pricing_type` (calculator→COMPLEX, scope_request→REQUEST_FOR_QUOTE, etc.)
- Inactive products blocked from storefront and product detail page (404 for all users)
- `QuoteRequestsTab.tsx` added showing date, product, contact, company, phone, message, status
- Customer visibility checkbox list shows company names with "X selected / Clear" control

### Next: Product Admin (COMPLEX vs SIMPLE pricing)
- Fields: title, short_description, tag, outcome, automation, support, bullets (3), FAQs, terms_id, billing_type, pricing_type (SIMPLE/COMPLEX)
- SIMPLE: fixed price/stripe_price_id, add-to-cart enabled
- COMPLEX: contact-us flow, `allow_checkout=false` by default

### Subscriptions Tab Overhaul
- **Start Date vs Created Date**: Both shown separately. Start Date = `start_date` (backfilled from `current_period_start` for Stripe, `created_at` for manual). Created Date = `created_at` (read-only in edit modal).
- **Cancellation Date**: Shown in table (`cancel_at_period_end` → `current_period_end`; fully cancelled → `canceled_at`)
- **Subscription ID** (`subscription_number`): Shown in Admin table + Customer Portal (backfilled for legacy subs)
- **Filters**: Customer Name/Company, Email, Plan, Status, Payment, Renewal From/To, Created From/To date range
- **Sorting**: Sort by Created Date or Renewal Date (asc/desc)
- **Renew button**: Disabled for `canceled_pending` status with descriptive tooltip
- **Notes**: View Notes button per row; Edit modal has Notes field (appended with timestamp + actor to `notes[]` array)
- **Status enum**: `ALLOWED_SUBSCRIPTION_STATUSES` = active/unpaid/paused/canceled_pending/cancelled/offline_manual
- **Data migration**: `payment_method="manual"` → `"offline"`, all subs have `subscription_number`, `start_date`, `role` backfilled

### Role Model: Super Admin vs Admin
- `require_super_admin` dependency added
- Users tab (admin panel) — visible only to `super_admin`
- Create Admin User form (email, name, password, role) — super_admin only
- `must_change_password=true` for newly created admin users
- `role` field in `/me` response, AuthContext updated

### Admin → Customers: Create Customer
- Create Customer button in Customers tab
- Form: Name, Company, Job Title, Email, Phone, Password, Address (line1-2, city, region, postal, country)
- Country locked after creation
- `mark_verified` option (checked by default)
- Full audit log on creation

### Customer Portal
- Subscriptions table: Sub ID column, correct Start Date, Cancellation Date, friendly status labels
- Cancel button hidden for already-cancelled/pending-cancel subscriptions

### Orders Tab Improvements
- **Table layout**: compact `text-xs`, `overflow-x-auto` container, `min-w-[1100px]`, actions in single row (no-wrap)
- **Date sorting**: Date column header toggles asc/desc sort (default: newest first)
- **Payment Date column**: Visible in table, editable in Edit dialog
- **Filters added**: Order # (contains), Status (dropdown), Product Name — alongside existing date/email filters
- **Edit Order dialog**: Customer selector (auto-shows email), Order Date, Payment Date, Status (9 options incl. completed/disputed), Payment Method, Add Note (appended to notes array)
- **View Notes button**: Shows notes history with timestamp + actor. Count badge when notes exist.
- **Notes stored as**: `order.notes[]` = `{text, timestamp, actor}` array, appended via `$push`

### Subscriptions Tab Improvements
- **Created Date column**: Shows `created_at` (backfilled for legacy records)
- **Filters panel**: Customer Name, Email, Plan, Status, Payment Method, Renewal From/To date range
- **Edit Subscription**: Customer selector, Plan, Amount, Renewal Date, Status dropdown, Payment Method
- **Cancel button**: Visible for non-cancelled subs, requires confirmation, sets `canceled_pending`, creates audit log
- **Admin cancel endpoint**: `POST /api/admin/subscriptions/{id}/cancel`

### Backend Additions
- `disputed`, `scope_pending`, `canceled_pending` added to `ALLOWED_ORDER_STATUSES`
- `new_note` field on `OrderUpdate` → appends to `notes` array + creates `note_added` audit log
- `customer_id`, `payment_method` added to `SubscriptionUpdate`
- `order_number_filter`, `status_filter` query params on `GET /admin/orders`

### P0 Admin CRUD (Feb 2026) ✅
- **Customer Edit**: Full dialog with Name, Company, Job Title, Phone, Address fields. Country locked.
- **Orders**: Paginated table (20/page) with Edit (status, payment method, payment date, notes), Delete, and Auto-Charge buttons.
- **Subscriptions**: Edit dialog (plan name, amount, renewal date), Renew Now (manual only), View Logs.
- **Audit Logs**: View Logs button on orders and subscriptions shows full change history.
- **Catalog - Terms Assignment**: Per-product Terms & Conditions dropdown in Catalog tab.
- **Backend Fix**: Removed duplicate `PUT /admin/orders/{order_id}` endpoint. New comprehensive endpoint active.
- **Bug Fix**: Customer Edit address fields now correctly send user-edited values instead of stale state.

### Key Admin API Endpoints
- `PUT /api/admin/customers/{customer_id}` - Edit customer + address
- `GET /api/admin/orders?page=&per_page=` - Paginated orders list
- `PUT /api/admin/orders/{order_id}` - Update order (status, payment method, date, notes)
- `DELETE /api/admin/orders/{order_id}` - Soft delete order
- `POST /api/admin/orders/{order_id}/auto-charge` - Auto-charge unpaid order
- `PUT /api/admin/subscriptions/{subscription_id}` - Edit subscription
- `GET /api/admin/{entity_type}/{entity_id}/logs` - Audit log history

## Pending/Future Work
- [ ] Real GoCardless integration (end-to-end payment confirmation)
- [ ] Full Zoho CRM & Books integration
- [ ] Real email sending for scope requests
- [ ] Subscription renewal order creation on Stripe webhook

## Files Reference
- `/app/backend/server.py` - Main backend API
- `/app/frontend/src/pages/Admin.tsx` - Admin panel with promo codes
- `/app/frontend/src/pages/Cart.tsx` - Cart with promo code input
- `/app/frontend/src/pages/Signup.tsx` - Registration with job title
- `/app/frontend/src/pages/Profile.tsx` - Profile with country locked
- `/app/frontend/src/pages/ProductDetail.tsx` - Scope request modal
- `/app/frontend/src/lib/categories.ts` - Category naming (Managed Services)
