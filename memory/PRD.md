# Product Requirements Document — Automate Accounts Customer Portal

## Original Problem Statement
Build a full-featured customer-facing portal for Automate Accounts (Zoho partner), enabling customers to browse products, place orders, manage subscriptions, and handle payments via Stripe and GoCardless. Admin panel for managing all entities.

## Architecture
- **Frontend**: React + TypeScript + TailwindCSS + Shadcn UI (port 3000)
- **Backend**: FastAPI + Python + MongoDB (port 8001)
- **Payments**: Stripe (card), GoCardless (direct debit)
- **Email**: Resend (API key in admin settings)
- **Rich Text**: TipTap (articles editor)

## Core User Personas
1. **Customer**: browses store, purchases products/subscriptions, views articles
2. **Admin**: manages products, categories, orders, subscriptions, customers, articles, codes

---

## What's Been Implemented

### Session 1 (Initial)
- Auth (register, login, verify email)
- Store with categories, product catalog
- Cart with Stripe checkout and GoCardless direct debit
- Admin panel: Users, Customers, Subscriptions, Orders, Categories, Catalog, Settings, Bank Transactions
- Quote Requests flow
- Promo codes
- Terms & Conditions management
- Bank Transactions tab
- Zoho sync logs

### Session 2 (Partner Tagging + Migrate-to-Books)
- **Zoho Partner Tagging Gate** at checkout: mandatory dropdown, override codes admin (single-use, 48h expiry)
- **Override Codes admin tab**: generate/view/expire codes per customer
- **In-App Migrate to Zoho Books page** (`ProductDetail.tsx`): intake form + complex pricing calculator
- **Global Checkout Questions**: Zoho subscription type, product, account access
- **Centralized Notes JSON**: `build_checkout_notes_json` saves all inputs to `order.notes_json` / `subscription.notes_json`
- **Admin "View Notes" fix**: dialog now shows `notes_json` as pretty-printed JSON + admin text notes

### Session 3 (Articles Module + Scope ID Unlock + Notes Fix) — 2026-02-21
- **Notes JSON Capture (System Critical)**:
  - `build_checkout_notes_json` now includes `payment_method` in `payment` section
  - `scope_request` orders also save `notes_json` with product_intake
  - `scope_request_form` orders save `notes_json` with product_intake + scope_form fields (added in iteration 22)
  - Admin "View Notes" dialog updated to pretty-print `notes_json` as "Intake Data" section
  - `_scope_unlock` metadata captured in `product_intake` when scope ID is used
  - `CartItemInput` Pydantic model now has `price_override` field
- **Articles Module**:
  - Backend: Full CRUD for `articles` collection with `article_logs`
  - 8 categories: Scope-Draft, Scope-Final Lost, Scope-Final Won, Blog, Help, Guide, SOP, Other
  - Price field mandatory for Scope-Final categories
  - Visibility: All or restricted to specific customers
  - Article email via Resend (API key from admin settings)
  - Admin tab "Articles" (between Terms and Promo Codes)
  - TipTap rich text editor with inline base64 image upload
  - Customer-facing `/articles` page with category filters
  - Customer-facing `/articles/:slug` article view
  - "Articles" nav link in TopNav (between Store and Admin)
- **Scope ID Unlock**:
  - Scope ID input on RFQ product detail pages
  - Validates article by ID: must be Scope-Final category with price
  - On valid: unlocks "Add to cart" with article price, shows success panel
  - On invalid: shows error message
  - Scope metadata (`_scope_unlock`) captured in `notes_json.product_intake`
  - Full Stripe checkout flow works with scope-unlocked price

### Session 4 (P1 Audit Logs + P2 DB-backed Settings) — 2026-02-21
- **P1 — Global Audit Log system**:
  - `AuditService` in `backend/services/audit_service.py` with keyset pagination
  - `audit_trail` MongoDB collection with composite indexes
  - `/api/admin/audit-logs` endpoint with full filtering (actor, source, entity_type, action, severity, date range, free text)
  - `LogsTab.tsx`: full-featured admin UI with filters, load-more pagination, detail dialog
  - Audit logging on: settings changes (SETTINGS_KEY_UPDATE, SETTINGS_UPDATE), order status updates, webhooks
- **P2 — DB-backed Settings (complete)**:
  - `SettingsService` in `backend/services/settings_service.py` with in-memory cache (60s TTL) + startup cleanup of obsolete keys
  - `app_settings` collection seeded with 12 structured settings across 6 categories
  - **Categories**: Payments (`service_fee_rate`), Operations (`override_code_expiry_hours`), Email (resend + sender + admin email), Zoho (5 checkout URLs), Branding (`website_url`, `contact_email`), FeatureFlags (`partner_tagging_enabled`)
  - **Removed dead settings**: stripe_publishable/secret/webhook keys, gocardless_access_token/environment, logo_url (duplicate), zoho_partner_link_aus/nz/global (wrong URLs, unused)
  - `/api/settings/public` extended to return all Zoho + branding fields (unauthenticated)
  - `/api/admin/settings/structured` GET — grouped by category (clean, no dead keys)
  - `/api/admin/settings/key/{key}` PUT — update single setting
  - **Wired to codebase**: `service_fee_rate` used in `calculate_price()`, order create, webhook renewal; `resend_api_key` via SettingsService; `override_code_expiry_hours` for override code generation
  - **Cart.tsx**: loads 5 Zoho URLs from `/api/settings/public` (no more hardcoded)
  - **ProductDetail.tsx**: loads `contact_email` + `website_url` from settings; passes `website_url` to `BooksMigrationForm`
  - **SettingsTab.tsx** cleaned up: removed API Keys section, removed Secondary color (unused), clean 2-column Brand Colors layout

---

## DB Collections
- `users`, `customers`, `addresses`, `products`, `categories`
- `orders` (+ `notes_json`, `partner_tag_response`, `override_code_id`)
- `subscriptions` (+ `notes_json`, `partner_tag_response`, `override_code_id`)
- `override_codes` — code, customer_id, expires_at, status, used_at
- `articles` — id, title, slug, category, price, content, visibility, restricted_to, created_at, updated_at, deleted_at
- `article_logs` — id, article_id, action, actor, details, created_at
- `app_settings`, `terms`, `promo_codes`, `quote_requests`, `zoho_sync_logs`

---

## Key API Endpoints

### Articles
- `GET /api/articles/admin/list` — admin list (no content)
- `GET /api/articles/public` — customer-visible list (no content)
- `GET /api/articles/{id}` — single article with content
- `GET /api/articles/{id}/validate-scope` — validate scope ID for RFQ unlock
- `GET /api/articles/{id}/logs` — admin timeline
- `POST /api/articles` — create (admin)
- `PUT /api/articles/{id}` — update (admin)
- `DELETE /api/articles/{id}` — soft delete (admin)
- `POST /api/articles/{id}/email` — send article link via Resend

---

## Test Credentials
- Admin: `admin@automateaccounts.local` / `ChangeMe123!`
- GoCardless test bank (Canada): Institution `0003`, Transit `00006`, Account `1234567`

---

## Prioritized Backlog

### P0 — Next
- **Audit Log Instrumentation**: Log key mutations (order create/update, subscription, customer, product, article, promo codes, override codes) — currently only settings + webhook + order status are instrumented

### P1 — Upcoming
- **`server.py` Refactor**: Extract route groups into `routes/` (auth, products, orders, subscriptions, etc.) — server.py is 6500+ lines
- Full Zoho CRM & Books Integration (data sync)
- Email integration for Quote Requests (use Resend)

### P2 — Future
- PostgreSQL migration (user-deferred)
- Scope-request form endpoint (`/api/orders/scope-request-form`) notes_json capture (currently missing)

---

## Known Issues / Notes
- `scope-request-form` endpoint does not include `notes_json` (different from `/orders/scope-request`)
- GoCardless payment flow: previously broken, fixed once, needs ongoing monitoring
