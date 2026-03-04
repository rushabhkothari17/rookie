# Partner Licensing & Billing System — PRD

## Original Problem Statement
Build a multi-tenant SaaS platform with a comprehensive B2B partner management layer including partner licensing, plan management, partner billing (orders & subscriptions), a partner-facing portal, automated email notifications, and scheduled background jobs.

---

## Latest Updates (March 4, 2026) — Form Validation & Enquiry Creation

### Completed: Mandatory Field Validation Across All Admin Forms ✅
Added validation (toast.error + early return) to:
- **Users** (new/edit): Full Name required
- **Promo Codes** (new/edit): Code, Discount type, Value, Applies to, Product eligibility, Expiry date
- **ProductEditor**: Category, Checkout type, Terms & conditions
- **Terms** (new/edit): Title, Content
- **Filters**: Filter type
- **Manual Subscription**: Customer email, Product, Start date, Billing interval, Amount, Currency, Contract term
- **Manual Order**: Customer email, Product, Currency, Status
- **Resources**: Content
- **Templates**: Default category, Description, Content
- **Email Templates**: Description, Email body
- **Resource Categories**: Description
- **References**: Value

### Completed: Create Manual Enquiry Button + Dialog ✅
- Backend: `POST /api/admin/enquiries/manual` in `orders.py` (validates customer email exists in DB, creates ENQ-XXXX record)
- Frontend: "Create Enquiry" button in EnquiriesTab header → opens dialog with Customer Email (required), Product (optional), Notes (optional)



### Completed: Footer Full-Width Fix ✅
- **Problem**: Admin panel footer was constrained inside `aa-container` (max-width + padding), not spanning full viewport width.
- **Fix**: Moved `AppFooter` from `Admin.tsx` into `BaseLayout` in `App.tsx` (placed after `</main>`, outside `aa-container`), matching the pattern used in `AppShell.tsx` for public pages.
- **Verified**: Footer is now 1920px wide matching full viewport on both admin and store pages (iteration_176.json).

### Completed: Resources Price/Currency Filter Fix ✅
- **Problem**: The price min/max and currency filter on the Resources tab did nothing — frontend sent params to backend but wrong file (`articles.py`) was updated; actual resources use `resources.py`.
- **Fix**: Updated `/resources/admin/list` in `resources.py` to handle `price_min`, `price_max`, `price_currency`, `modified_from`, `modified_to`, and `partner` query params with proper MongoDB `$gte`/`$lte` comparisons.
- **Verified**: price_min=50 → 1 result; price_min=200 → 0 results; price_currency=USD → 1 result; price_currency=GBP → 0 results (iteration_176.json).


- **Problem**: Price/Amount filter popovers only had Min/Max range inputs, no way to filter by currency alongside a value range.
- **Fix**: Added optional `currencyOptions?: [string, string][]` prop to `ColHeader` component. When provided with `filterType="number-range"`, a currency `<select>` appears above the Min/Max inputs.
- **Scope**: Applied to 6 columns across 5 tabs: Products (Price), Subscriptions (Amount + Tax), Partner Subscriptions (Amount), Partner Orders (Amount), Resources (Price).
- **Filtering logic**: Client-side currency check added to ProductsTab, PartnerSubscriptionsTab, PartnerOrdersTab. Backend updated for SubscriptionsTab (`amount_min`, `amount_max`, `amount_currency`, `tax_min`, `tax_max`, `tax_currency`). ResourcesTab backend updated to handle `price_currency`, `price_min`, `price_max`, `modified_from`, `modified_to`, `partner` params.
- **Bug fix**: `Admin.tsx` was missing `import { Tabs, TabsList, TabsTrigger, TabsContent }` causing compile errors — fixed.
- **Verified**: Testing agent 100% pass (iteration_175.json).

## Latest Updates (March 3, 2026)

### Completed: Signup page & Add Customer form — shared single source of truth ✅
- **Problem**: Both forms used `signup_form_schema` but rendered fields differently (different ordering, different sections, Add Customer missing custom fields).
- **Fix**: Created `frontend/src/components/CustomerSignupFields.tsx` — a single shared component used by both `/signup` page and the admin "Add Customer" dialog. Fields render in schema order with email+password always injected after `full_name`. Supports compact (dialog) and full-page layouts.
- **Verified**: Testing agent confirmed 100% pass — same field order on both forms (Full Name → Email → Password → Company → Job Title → Phone → Address), labels from schema, no cursor loss, customer creation succeeds.

### Completed: Signup page & Add Customer form now share the same schema ✅
- **Problem**: The `/signup` page and admin "Add Customer" dialog both read from `signup_form_schema` (Auth & Pages > Customer Sign up), but the "Add Customer" dialog was not rendering custom extra fields and was not saving `profile_meta`.
- **Fix**: Added custom field rendering (text, textarea, select, number, date) to the Create Customer dialog, `profile_meta` is now passed to the API and stored on the user document.
- **Backend**: Added `profile_meta: Optional[Dict[str, Any]]` to `AdminCreateCustomerRequest` model; stored in `user_doc` on creation.
- **Files changed**: `backend/models.py`, `backend/routes/admin/customers.py`, `frontend/src/pages/admin/CustomersTab.tsx`

### Completed: Two Bug Fixes ✅
- **PromoCodesTab cursor bug fixed**: `PromoForm` component was defined inside `PromoCodesTab`, causing full remount (and focus loss) on every keystroke. Moved to module level. Verified by testing agent (iteration_173.json).
- **Hardcoded currency symbol fixed**: Admin Products table and ProductDetail preview page were displaying `$` regardless of product currency. Now uses `Intl.NumberFormat` with `product.currency` (e.g., A$300, CA$199). Verified by testing agent.

### Completed: Extended Filter Refactor (12 Modules) ✅
- Extended multi-select dropdown filters to 12 additional admin modules:
  - **Customers**: Name, State/Province, Payment Methods, Partner Map, Partner, Status
  - **Products**: Name, Category, Billing, Status (+ Price number range)
  - **Categories**: Name, Products, Status (+ Description text search)
  - **Promo Codes**: Code, Discount, Applies To, Usage, Status
  - **Terms**: Title, Products Linked, Default, Status
  - **Subscriptions**: Sub #, Processor ID, Customer Email, Plan, Currency, Payment, Status (+ Amount/Tax number ranges)
  - **Orders**: Order #, Customer, Email, Product(s), Sub #, Processor ID, Method, Status, Partner
  - **Enquiries**: Order #, Customer, Partner, Products, Status
  - **Resources**: Category, Partner (+ Modified date range, Price number range)
  - **Resource Templates**: Name, Category, Type
  - **Resource Email Templates**: Name
  - **Resource Categories**: Name, Scope Final
- **Testing Status:** 95% pass (iteration_172.json)

### Previous Session (March 2, 2026):
- Converted 7 admin tables (Plans, Partner Subscriptions, Partner Orders, Partner Submissions, Users)
- Fixed Stripe 403 Error in `Cart.tsx`
- Fixed Partner Orders 405 Error (missing decorator)
- Added Customers Email text search + Country multi-select

## Target Users
- **Platform Admins**: Manage all tenants, partners, products, billing
- **Partner Admins**: Manage their own customers, storefronts, view own billing
- **End Customers**: Purchase services via partner storefronts

## Core Architecture
- **Backend**: FastAPI + MongoDB + APScheduler
- **Frontend**: React (TypeScript) + Shadcn UI
- **Payments**: Stripe, GoCardless
- **Emails**: Resend, Zoho Mail
- **Integrations**: Zoho CRM, Zoho Books, Zoho WorkDrive, exchangerate-api.com

---

## What's Been Implemented

### Phase 1: Partner Licensing & Plans
- Plan creation and assignment to partners
- License usage tracking with strict enforcement on all manual create paths
- Partner portal showing license usage
- **Free Trial plan** auto-seeded on startup (all limits=10, `is_default=true`)
- `is_public` flag on plans — controls visibility for partner self-service upgrade
- `GET /api/partner/plans/public` endpoint — returns plans where `is_public=true`
- Auto-assigned to new partner orgs at signup
- Reset to Free Trial when a partner subscription is cancelled

### Phase 2: Partner Billing
- Full CRUD for partner orders and subscriptions (admin UI + API)
- Manual creation with license limit enforcement
- Stripe and GoCardless webhook routing with `billing_type: 'partner'` metadata
- Partner-facing read-only views (MyOrdersTab, MySubscriptionsTab)
- Automated emails for new partner orders and subscriptions

### Phase 3: Subscription Term Management
- `term_months`, `contract_end_date`, `auto_cancel_on_termination` on both customer and partner subscriptions
- Backend enforces term-end dates on manual cancellation
- Admin UI to manage these settings

### Phase 4: Storefront Filters & UX
- Partner admins can configure product filters for their customer-facing stores (FiltersTab)
- Login page accepts `partnerCode` URL parameter for streamlined partner login

### Phase 5–7: Billing Automation, Plan Upgrades, Stripe
- Stripe Checkout for partner plan upgrades (pro-rata and flat-diff flows)
- APScheduler 4 daily jobs: renewal reminders, auto-cancel, renewal orders, overdue cancellation
- Configurable `reminder_days` per subscription and per tenant
- `GET /api/partner/my-plan`, `POST /api/partner/upgrade-plan`, `POST /api/partner/submissions`
- Partner billing portal, Usage & Limits embedded in Plan & Billing tab

### Phase 8: Advanced Billing Features (Mar 2026)
- **Dual Upgrade Flows** (frontend + backend):
  - `POST /api/partner/upgrade-plan-ongoing` — flat monthly difference, partner pays upfront, plan activates on Stripe confirmation
  - `POST /api/partner/one-time-upgrade` — per-module extra capacity for current billing cycle only, resets on renewal
- **Coupon System** (admin + partner):
  - Admin CRUD: `GET/POST/PUT/DELETE /api/admin/coupons`
  - Partner validation: `POST /api/partner/coupons/validate`
  - Supports: percentage/fixed, expiry, single-use global, one-use-per-org, applicable plans restriction
  - Coupon code applied in-app before Stripe checkout
- **One-Time Plans Rate Table** (admin):
  - Admin CRUD: `GET/POST/PUT/DELETE /api/admin/one-time-plans`
  - Partner read: `GET /api/partner/one-time-rates`
  - Configurable price-per-unit for 10 module types
- **Coupon Usage Report** tab (4th inner section in Plans tab):
  - Summary cards: Total Redemptions, Unique Coupons, Total Discount Given, Revenue (Couponed Orders)
  - Full table: Date | Partner | Coupon | Upgrade Type | Original | Discount | Paid | Status
  - Totals row, filter-by-code input, Refresh button
  - Backend: `GET /api/admin/coupon-report` with optional `?coupon_code=` filter
- **Partner Plan & Billing Tab** updated with:
  - "Upgrade to [Plan]" button → OngoingUpgradeDialog (flat diff + coupon)
  - "Buy Extra Limits" button → OneTimeUpgradeModal (per-module qty + coupon)
  - Active boosts displayed if present
  - `onetimeupgrade_status` URL param handled on return from Stripe
- **Free Trial plan protection**: `is_default=true`, delete/deactivate buttons disabled in UI and blocked in API
- **Unpaid subscription status**: scheduler marks subscriptions `unpaid` when renewal order unpaid >1 day; auto-reactivates when order paid
- **Subscription status**: `paused` removed; `pending` treated as Free Plan
- **`isPlatformAdmin` check** updated to include `platform_super_admin` role in Admin.tsx
- **Scheduler** resets `one_time_boosts` on each renewal cycle

---

## Key File References

### Backend (New/Modified)
| File | Purpose |
|------|---------|
| `backend/routes/admin/one_time_plans.py` | One-Time rate table CRUD |
| `backend/routes/admin/coupons.py` | Coupon CRUD + partner validate |
| `backend/routes/partner/plan_management.py` | upgrade-plan-ongoing, one-time-upgrade, one-time-rates |
| `backend/routes/admin/plans.py` | Protect default (Free Trial) plan |
| `backend/routes/admin/partner_billing.py` | Activate subscription on paid order |
| `backend/services/scheduler_service.py` | Unpaid sub marking, one-time boost reset |
| `backend/services/billing_service.py` | `calculate_upgrade_flat`, `advance_billing_date` |
| `backend/routes/webhooks.py` | one_time_upgrade webhook handler |

### Frontend (New/Modified)
| File | Purpose |
|------|---------|
| `frontend/src/pages/admin/PlansTab.tsx` | 3 sections: Plans, One-Time Rates, Coupons |
| `frontend/src/pages/admin/PlanBillingTab.tsx` | Dual upgrade flows, coupon apply |
| `frontend/src/pages/Admin.tsx` | isPlatformAdmin includes platform_super_admin |

---

## Key API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/partner/upgrade-plan-ongoing` | Flat monthly diff upgrade, Stripe checkout |
| POST | `/api/partner/one-time-upgrade` | Per-module capacity boost, Stripe checkout |
| GET | `/api/partner/one-time-upgrade-status` | Poll after Stripe return |
| GET | `/api/partner/one-time-rates` | Partner read-only rate catalogue |
| POST | `/api/partner/coupons/validate` | Preview coupon discount before checkout |
| GET/POST/PUT/DELETE | `/api/admin/one-time-plans` | One-time rate table CRUD |
| GET/POST/PUT/DELETE | `/api/admin/coupons` | Coupon CRUD |
| POST | `/api/admin/subscriptions/{id}/send-reminder` | Send test renewal reminder |
| PUT | `/api/admin/tenant-settings` | Update org-level default_reminder_days |
| GET | `/api/partner/my-plan` | Current plan, subscription, available upgrades |
| GET | `/api/admin/store-filters` | Get store filters |
| POST | `/api/admin/store-filters` | Save store filters |

---

## DB Schema (Key Fields)
- `subscriptions`, `partner_subscriptions`: `term_months`, `contract_end_date`, `auto_cancel_on_termination`, `reminder_days`, `reminder_sent_for_renewal_date`, `auto_renewal_order_date`, `status` (active/pending/unpaid/cancelled)
- `tenants`: `default_reminder_days`, `license.one_time_boosts`, `license.one_time_boosts_expire_at`
- `plans`: `is_default`, `is_public`, `monthly_price`, `currency`
- `coupons`: `code`, `discount_type`, `discount_value`, `expiry_date`, `is_single_use`, `applies_to`, `applicable_plan_ids`, `is_one_time_per_org`, `is_active`, `usage_count`, `used_by_orgs`
- `one_time_plan_rates`: `module_key`, `label`, `price_per_record`, `currency`, `is_active`
- `one_time_upgrades`: `partner_id`, `upgrades`, `subtotal`, `final_amount`, `billing_period_end`, `status`

---

## Prioritized Backlog

### P0 — Completed
- ✅ **Role & Permission System Overhaul** — COMPLETE (Mar 2026)
- ✅ **UI/UX Enhancements Batch** — COMPLETE (Mar 2026)
- ✅ **Supported Currencies Module** — COMPLETE (Mar 2026)
- ✅ **Plan Visibility Rules** — COMPLETE (Mar 2026)
- ✅ **Tenant Profile Fields** — COMPLETE (Mar 2026)
- ✅ **FX Currency Fix in Plan Billing** — COMPLETE (Mar 2026)
- ✅ **Plan & Billing 2-Button Layout** — COMPLETE (Mar 2026)
- ✅ **Partner Type & Industry Management** — COMPLETE (Feb 2026): TenantsTab now has 3 sub-tabs (Partner List, Partner Types, Industries); `GenericListManager` reusable CRUD component; `usePlatformList` hook; all dropdowns pull from API not hardcoded
- ✅ **Partner Staff Role Removed** — COMPLETE (Feb 2026): Removed from backend valid_roles, frontend dropdowns, and role label maps; only Platform Admin, Partner Super Admin, Partner Admin remain
- ✅ **Full Data Wipe** — COMPLETE (Feb 2026): All collections cleared; only admin@automateaccounts.local preserved
  - Role dropdown in Add User: Platform Admin, Partner Super Admin, Partner Admin, Partner Staff (no Platform Super Admin option)
  - Searchable partner org picker appears when creating partner roles from platform admin context
  - Block 2nd partner super admin with clear transfer-flow guidance
  - Module list scoped to selected role (partner roles = partner modules only)
  - Partner Org column in users table
  - Edit dialog: role change field (guarded by hierarchy rules); super admin shows info box instead of module editor
  - Cleaned up 4 fake platform super admin test accounts → demoted to platform_admin
- ✅ **Roles Tab Removed / Presets merged into Users** — COMPLETE (Feb 2026): Roles top-level tab deleted; Quick Presets sub-tab added inside Users tab showing 5 built-in preset cards; admin_roles CRUD removed from backend
- ✅ **Tags Management Sub-tab** — COMPLETE (Feb 2026): 4th sub-tab in Partner Orgs for managing the tags taxonomy (used in plan visibility rules)
- ✅ **Roles & Permissions System Overhaul** — COMPLETE (Feb 2026):
  - Platform Super Admin (1, immutable — cannot edit/deactivate/self-demote); Partner Super Admin (1 per org, transferable)
  - Platform Admin role creatable from Users tab (only by platform_super_admin)
  - Per-module read/write permissions replace global access_level (19 modules: 7 platform-only, 12 partner/shared)
  - Module list scoped to context (platform admins see all, partner super admin sees partner modules only)
  - Partner super admin transfer via "Make Super Admin" button in partner org user list
  - New platform_admin defaults to all modules with read access: "Upgrade Plan" opens UpgradePlansModal with FX prices; "Buy Extra Limits" opens one-time modal
  - Shared `ISO_CURRENCIES` constant in `frontend/src/lib/constants.ts`, imported across 4 admin files
  - SearchableSelect (combobox with search) for Partner and Plan fields in `PartnerOrdersTab` and `PartnerSubscriptionsTab` form modals
  - Currency field in `PartnerOrders` create/edit form changed from text input to Select dropdown
  - "Pending" status badge readability fixed in both `PartnerOrdersTab` and `PartnerSubscriptionsTab`
  - Real-time Next Billing Date + Expiry Date computation already in place in subscription forms

### P1 — Future
- **Google Drive & OneDrive** cloud storage integration (currently "Coming Soon")
- **Customer Portal Self-Service**: subscription cancellation, renewal date display, "Reorder" button
- Centralize all email integration settings in one UI section

### P2 — Backlog
- GoCardless mandate management UI
- Bulk subscription import via CSV
- Analytics dashboard for partner billing revenue

---

### Critical Billing Bug Fixes (Mar 2026)
- **Dismiss Pending Upgrade (P0):** Removed invalid `sort=` parameter from `update_one` call in `cancel_pending_upgrade` — was causing a `TypeError` (500 error) in `partner/plan_management.py`.
- **Exchange Rate for One-Time Upgrades (P0):** Modified `GET /api/partner/one-time-rates` to fetch partner's `base_currency` and apply live FX conversion (`get_fx_rate`) to each rate's `price_per_record` before returning. Partners now see correctly priced rates in their own currency.

## Completed (Recent)

### Column-Level Sorting & Filtering Across All Admin Tables (Feb 2026)
- Created reusable `frontend/src/components/shared/ColHeader.tsx` component with sort (asc/desc), filter controls (text, number-range, date-range, status dropdown)
- Applied ColHeader to all 18 admin panel tables, removing old separate filter UIs
- Fixed SubscriptionsTab.tsx: Amount, Tax, Currency columns now use subscription-specific data (not plan data)
- Fixed empty-state rendering: Coupons and Partner Submissions tables now always show table headers even when no data exists
- All 18 tables verified via testing agent: 100% pass rate

### Sub-tab Design Unification (Mar 2026)
- Plans tab: Converted from custom button navigation to Shadcn `Tabs` components (matching Partner Orgs design)
- Resources tab: Converted from custom button navigation to Shadcn `Tabs` components
- Supported Currencies Add button: Confirmed working

### PartnerOrgForm Unification (Mar 2026)
- Deleted Partner Types, Industries, and Tags concept entirely (sub-tabs, plan visibility rule fields, edit form, backend routes)
- Created shared `PartnerOrgForm` component used by both Admin "New Partner Org" dialog and public `/signup?type=partner`
- Both forms now identical: Org Name, Admin Account (name/email/password), Base Currency, Address
- Added "Partner Sign-Up Page" tile in Auth & Pages with FormSchemaBuilder (6 fields, 4 locked + Currency + Address toggleable)
- Currency uses live `useSupportedCurrencies` list everywhere (no more hardcoded options)

### Advanced Billing Features (Mar 2026)
- Dual upgrade paths: Ongoing Plan (flat diff) + One-Time Limits (per-module boost)
- Full coupon management system with admin CRUD and partner validation
- One-Time Plans rate table (admin configures $/unit, partners buy capacity)
- Free Trial plan protection (default badge, locked buttons)
- Unpaid subscription lifecycle via scheduler
- One-time boosts reset on renewal cycle
- isPlatformAdmin includes platform_super_admin role (Admin.tsx fix)
- 41/41 backend tests passing, all frontend features verified
