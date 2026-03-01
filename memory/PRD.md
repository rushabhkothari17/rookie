# Partner Licensing & Billing System — PRD

## Original Problem Statement
Build a multi-tenant SaaS platform with a comprehensive B2B partner management layer including partner licensing, plan management, partner billing (orders & subscriptions), a partner-facing portal, automated email notifications, and scheduled background jobs.

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

### P0 — Next Sprint
- ✅ **Role & Permission System Overhaul** — COMPLETE (Mar 2026)
- ✅ **UI/UX Enhancements Batch** — COMPLETE (Mar 2026)
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

## Completed (Recent)

### Advanced Billing Features (Mar 2026)
- Dual upgrade paths: Ongoing Plan (flat diff) + One-Time Limits (per-module boost)
- Full coupon management system with admin CRUD and partner validation
- One-Time Plans rate table (admin configures $/unit, partners buy capacity)
- Free Trial plan protection (default badge, locked buttons)
- Unpaid subscription lifecycle via scheduler
- One-time boosts reset on renewal cycle
- isPlatformAdmin includes platform_super_admin role (Admin.tsx fix)
- 41/41 backend tests passing, all frontend features verified
