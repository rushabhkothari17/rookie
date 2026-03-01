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

### Phase 7: Overdue Cancellation, Product Billing Type & User Filter (Feb 2026)
- **Phase 5 — Overdue Cancellation**: Scheduler Job 4 (`cancel_overdue_partner_subscriptions`, daily 09:15 UTC) detects overdue partner orders, sends warning email at configurable days, auto-cancels subscription + reverts to Free Trial past grace period. New `GET/PUT /api/admin/platform-billing-settings` endpoint + new admin "Billing Settings" tab in Platform section.
- **Phase 2B — Product Billing Type**: Added `billing_type: "prorata" | "fixed"` field to products. Visible in Product Form > Pricing > "Subscription billing method" dropdown (shown only when `is_subscription=true`). Pro-rata aligns first invoice to 1st of month; Fixed always charges full monthly price from start date.
- **Phase 6 — User Form Parity**: Platform admins can filter the Users tab by partner organisation via a new dropdown. Backend `/api/admin/users` now accepts optional `partner_id` query parameter.
- **FieldTip Bug Fix**: Converted tooltips from CSS hover (`group-hover`) to click-to-toggle React state. Fixes all-tooltips-visible-at-once bug caused by parent `group` class conflict.
- `GET /api/partner/my-plan` — returns current plan, subscription, and available public plans
- `POST /api/partner/upgrade-plan` — instant self-service upgrade with pro-rata billing (creates order + updates subscription)
- `POST /api/partner/submissions` — submit a downgrade or support request (effective next 1st of month)
- `GET /api/partner/submissions` — partner views their own submissions
- `GET /api/admin/partner-submissions` — platform admin views all partner submissions (with status filter, search)
- `PUT /api/admin/partner-submissions/{id}` — approve/reject submission; approval immediately applies plan change to tenant
- **New Frontend Tabs**: `PlanBillingTab` (partner), `MySubmissionsTab` (partner), `PartnerSubmissionsTab` (platform admin)
- Plans now support `monthly_price` and `currency` fields for pricing display + pro-rata calculation
- Plans table in Admin shows Price column and `Public` badge for self-service eligible plans
- **APScheduler** integrated (3 daily jobs at 09:00–09:10 UTC):
  1. **send_renewal_reminders** — configurable `reminder_days` per subscription/tenant
  2. **auto_cancel_subscriptions** — auto-cancels when `contract_end_date <= today` and `auto_cancel_on_termination=true`
  3. **create_renewal_orders** — creates `pending` orders for manual-payment subs on billing day
- **Configurable Reminder Days**:
  - `reminder_days` field on each subscription (customer + partner) — overrides org default
  - `default_reminder_days` on tenant document — org-level default
  - `null`/blank = no reminders sent for that scope
  - UI: SettingsTab "Subscription Notifications" section, plus per-subscription field with tooltip
  - PUT `/api/admin/tenant-settings` endpoint for any admin to update their org default

---

## Key File References

### Backend (New/Modified)
| File | Purpose |
|------|---------|
| `backend/services/scheduler_service.py` | 3 APScheduler jobs |
| `backend/routes/admin/tenants.py` | Added PUT `/admin/tenant-settings` |
| `backend/routes/admin/subscriptions.py` | reminder_days on create/update |
| `backend/routes/admin/partner_billing.py` | reminder_days on partner subs |
| `backend/routes/admin/store_filters.py` | Store product filters |
| `backend/routes/partner/billing_view.py` | Partner-facing billing views |
| `backend/models.py` | reminder_days, default_reminder_days, term fields |

### Frontend (New/Modified)
| File | Purpose |
|------|---------|
| `frontend/src/pages/admin/SettingsTab.tsx` | ReminderNotificationSection |
| `frontend/src/pages/admin/SubscriptionsTab.tsx` | reminder_days field |
| `frontend/src/pages/admin/PartnerSubscriptionsTab.tsx` | reminder_days field |
| `frontend/src/pages/admin/FiltersTab.tsx` | Store filter management |
| `frontend/src/pages/partner/MyOrdersTab.tsx` | Partner order history |
| `frontend/src/pages/partner/MySubscriptionsTab.tsx` | Partner sub history |

---

## Key API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/admin/subscriptions/{id}/send-reminder` | Immediately send test renewal reminder |
| POST | `/api/admin/partner-subscriptions/{id}/send-reminder` | Immediately send test renewal reminder |
| PUT | `/api/admin/tenant-settings` | Update org-level default_reminder_days |
| POST | `/api/admin/subscriptions/manual` | Create customer sub (includes reminder_days) |
| PUT | `/api/admin/subscriptions/{id}` | Update customer sub (includes reminder_days) |
| POST | `/api/admin/partner-subscriptions` | Create partner sub (includes reminder_days) |
| PUT | `/api/admin/partner-subscriptions/{id}` | Update partner sub (includes reminder_days) |
| GET | `/api/admin/store-filters` | Get store filters |
| POST | `/api/admin/store-filters` | Save store filters |
| GET | `/api/partner/my-orders` | Partner's own orders |
| GET | `/api/partner/my-subscriptions` | Partner's own subs |

---

## DB Schema (Key Fields)
- `subscriptions`, `partner_subscriptions`: `term_months`, `contract_end_date`, `auto_cancel_on_termination`, `reminder_days`, `reminder_sent_for_renewal_date`, `auto_renewal_order_date`
- `tenants`: `default_reminder_days`
- `products`: `default_term_months`
- `store_filters`: `{ tenant_id, filters: [{id, name, type, options}] }`

---

## Prioritized Backlog

### P0 — Next Sprint
- **Google Drive & OneDrive** cloud storage integration (currently "Coming Soon")
- **Customer Portal Self-Service**: subscription cancellation, renewal date display, "Reorder" button

### P1 — Future
- Security audit / penetration test
- Centralize all email integration settings in one UI section

### P2 — Backlog
- GoCardless mandate management UI
- Bulk subscription import via CSV
- Analytics dashboard for partner billing revenue
