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

## Admin Panel Enhanced Features (Feb 21, 2026) ✅

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
