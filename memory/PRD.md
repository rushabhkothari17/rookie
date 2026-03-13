# Product Requirements Document

## Project Overview
Multi-tenant SaaS platform (Automate Accounts) for partner organizations to sell services/products.
Platform has three user tiers: Platform Admin, Partner Admins, and Customers.

## Original Problem Statement
Build a white-label service commerce platform with:
- Multi-tenant architecture (Platform > Partner Orgs > Customers)
- Partner onboarding with org creation, branding, email setup
- Customer signup & portal (services, cart, orders, profile)
- Admin panel: users, customers, products/services, quotes, emails, website config
- Payment integrations (Stripe, GoCardless)
- File storage via Zoho WorkDrive
- Dynamic form builder (FormSchemaBuilder) powering all customer-facing forms

## Architecture

### Backend (FastAPI + MongoDB)
```
/app/backend/
├── server.py              # App startup, seeds platform tenant
├── routes/
│   ├── admin/
│   │   ├── tenants.py     # Partner org CRUD, create-partner endpoint
│   │   ├── users.py       # User management, tenant-scoped email validation
│   │   ├── customers.py   # Customer management, tenant-scoped email validation
│   │   └── ...
│   ├── website.py         # Public/admin website settings (store_name sync fix)
│   └── ...
├── services/
│   └── settings_service.py  # Cache TTL = 1s
└── models/
```

### Frontend (React + TypeScript)
```
/app/frontend/src/
├── components/
│   ├── UniversalFormRenderer.tsx    # SINGLE form renderer — all forms use this
│   ├── AddressFieldRenderer.tsx     # Address block (canonical order: Line1→Line2→City→Country→State→Postal)
│   ├── FormSchemaBuilder.tsx        # Admin drag-and-drop schema editor
│   ├── CustomerSignupFields.tsx     # Thin wrapper: injects email/password, delegates to UniversalFormRenderer
│   └── admin/
│       └── PartnerOrgForm.tsx       # Thin adapter: maps PartnerOrgFormValue to flat keys for UniversalFormRenderer
├── pages/
│   ├── Profile.tsx                  # Fully schema-driven via UniversalFormRenderer
│   ├── Signup.tsx                   # Uses CustomerSignupFields + PartnerOrgForm
│   ├── ProductDetail.tsx            # Scope/quote modals use UniversalFormRenderer (addressMode=json)
│   └── admin/
│       ├── CustomersTab.tsx         # Uses CustomerSignupFields (compact)
│       ├── TenantsTab.tsx           # Uses PartnerOrgForm (compact)
│       └── websiteTabShared.tsx     # OrgAddressSection: standalone but canonical order
└── contexts/
    └── WebsiteContext.tsx           # refresh() function for post-save sync
```

## Key Design Decisions

### Universal Form Rendering (Latest — Feb 2026)
- **`UniversalFormRenderer`** is the single source of truth for ALL form rendering
- All field types handled: text, email, tel, number, date, textarea, select, checkbox, address
- Address canonical order: `Line 1 → Line 2 → City → Country → State/Province → Postal`
- Country must come BEFORE State/Province (functional requirement: province dropdown depends on country)
- `compact` mode for admin dialogs, full mode for public pages
- `addressMode="flat"` (default): address sub-fields as flat keys (line1, city, region, etc.)
- `addressMode="json"`: address stored as JSON string (for dynamic scope/quote forms)

### Form Schema System
- Admin configures forms via `FormSchemaBuilder` (drag/reorder, toggle fields, set required/optional)
- Schemas stored in `app_settings` collection per tenant
- `signup_form_schema` → Customer signup, profile page
- `partner_signup_form_schema` → Partner org creation
- `scope_form_schema` → Quote/scope request modals
- `checkout_extra_schema` → Extra checkout fields

### Data Synchronization
- `store_name` stored in both `tenants` and `app_settings`; edit endpoint updates both
- `refreshWebsite()` in WebsiteContext forces UI re-fetch after save
- Settings cache TTL = 1 second (was 60s)

### Tenant-Scoped Email Uniqueness
- Email must be unique within a tenant across BOTH users AND customers collections
- Platform admin can reuse emails across different tenants

## What's Been Implemented (Chronological)

### Phase 1: Core Platform
- Multi-tenant architecture, partner org creation, customer signup
- Admin panel: users, customers, products, orders, email templates
- FormSchemaBuilder for dynamic form configuration
- Payment integrations: Stripe, GoCardless
- Zoho WorkDrive file storage

### Phase 2: Fixes & Features (Recent Sessions)
- P0 Partner Creation Bug Fix (new `POST /api/admin/tenants/create-partner` endpoint)
- Customer-to-Partner Mapping (partner dropdown in Create Customer dialog)
- Store & Partner Name Sync (dynamic top-left name, partner list shows store_name)
- Email Template Visibility Fix (partner_verification template visible to platform admin)
- Database Wipe + Seed Cleanup (startup seeds only platform tenant, no demo products)
- Tenant-Scoped Email Uniqueness (cross-collection validation)
- Product Price Display Fix ($0 instead of "RFQ" for zero-price products)
- Cache TTL reduced 60s → 1s

### Phase 3: Universal Form Rendering + Bug Fixes (Feb 2026)
- Created `UniversalFormRenderer` — single source of truth for ALL form rendering
- Fixed `AddressFieldRenderer` — canonical field order (Line1→Line2→City→Country→State→Postal), renamed state→region
- Rewrote `CustomerSignupFields` — thin wrapper around UniversalFormRenderer
- Rewrote `PartnerOrgForm` — adapter mapping PartnerOrgFormValue → flat keys
- Rewrote `Profile.tsx` — fully schema-driven, reads/saves ALL schema fields dynamically
- Updated `ProductDetail.tsx` — scope/quote modals use UniversalFormRenderer (addressMode=json)
- Fixed `websiteTabShared.tsx` — org address canonical order
- Added real-time validation (email format, phone format) in `UniversalFormRenderer`
- Fixed province clearing bug: only dispatch CHANGED address keys (not all 6 on every change)
- Fixed `GET /me` to return `job_title` in user object
- Fixed Admin customers list MongoDB projection to include `job_title` and `phone`
- Added `noValidate` to Profile form so address-required fields don't block other field saves
- Fixed `Signup.tsx` to pass `partnerCode` to CustomerSignupFields for correct country/province lists
- Fixed Admin "Add Customer" dialog to use `ws.signup_form_schema` (same source as signup page) — no more separate API fetch
- Hidden "My Profile" from all admin roles (platform_admin, platform_super_admin, partner_admin, partner_super_admin) — only `role === "customer"` users see it
- Fixed login page org name: now reads `branding.store_name` (from `app_settings`) instead of `tenant.name` so it refreshes when org name is saved in settings

### Phase 5: Form Unification & UI Polish (March 2026)
- Edit Customer dialog rewritten to use `UniversalFormRenderer` (same source as Create Customer)
- `normaliseCountry()` utility added to map ISO codes (CA, US, GB...) to full names — fixes legacy customer pre-fill
- Both Create & Edit Customer dialogs now structurally identical: pill inputs, placeholder-only labels, ADDRESS section, gap-4 spacing
- Only difference: Edit dialog has Payment Methods + Tax Exempt sections (no email/password); Create has email+password
- Verified by testing agents iteration_267 + iteration_268
- Updated `input.jsx` base: `rounded-full`, `h-11`, smooth focus + focusGlow animation
- Updated `button.jsx` base: `rounded-full`, active scale(0.97), hover shadow-lift
- Updated `select.jsx` trigger: `rounded-full`; content: `rounded-2xl`
- Updated `textarea.jsx`: `rounded-3xl`
- Global CSS in `index.css`: `.auth-input`, `.btn-primary`, `@keyframes focusGlow`, `@keyframes fadeSlideUp`
- Login.tsx: pill inputs, full-width pill button, staggered slide-up animations
- ForgotPassword.tsx: consistent pill styling
- Profile.tsx: pill read-only inputs with dashed border
- Focus glow animation on ALL inputs (one-shot pulse → settles to ring)
- Edit Customer dialog: updated to match Create Customer - uppercase labels (11px tracking), grid layout, gap-4 spacing, pill inputs
- Create Customer dialog: fixed 0px gap bug (React 19 `display:contents` span breaks `space-y-*`, fixed with `flex flex-col gap-4`)
- Filters tab: updated to use AdminPageHeader + size="sm" buttons, matches Products tab styling
- Verified by testing agent iteration_267.json — 7/8 tests PASS, gap bug fixed post-test

### Phase 6: Form Size & Animation Polish (March 2026)
- Reduced all admin form inputs from h-11 (44px) → h-9 (36px) via `input.jsx` and `select.jsx` base component changes
- Reduced UFR pill inputs from h-12 (48px) → h-9 (compact) / h-10 (full) — size-aware based on `compact` prop
- Reduced AddressFieldRenderer inputs from h-12 (48px) → h-9 (compact) / h-10 (full) — same pattern
- Added `dialogIn` animation to all dialogs (`[role='dialog'] > div`) via `index.css`
- Enhanced `focusGlow` animation (more visible pulse)
- Auth pages (Login `.auth-input` = 48px, ForgotPassword explicit `h-11` = 44px) unaffected
- Verified via testing agent iteration_270 — 8/8 tests PASS
- Verified `store_name → tenants.name` sync via curl: PUT /api/admin/settings updates both `app_settings.store_name` AND `tenants.name` in one operation (settings.py line 82-83)

### Phase 7: Zoho CRM Extended Module Sync (March 2026)
- **13 syncable modules total** (3 existing + 10 new): customers, orders, subscriptions, products, enquiries, invoices, resources, plans, categories, terms, promo_codes, refunds, addresses
- **Products module** includes 19 fields: all standard fields + `intake_questions_count`, `intake_questions_labels`, `intake_questions_json` (full schema as text)
- **Multiple mappings per module**: `find_one` → `find` fan-out in `auto_sync_to_zoho_crm` — one store module can sync to multiple Zoho CRM destinations simultaneously
- **Auto-sync triggers added** to: catalog.py, promo_codes.py, resources.py, terms.py, plans.py, orders.py (enquiries), checkout.py (invoices, 3 paths), refund_service.py, customers.py (addresses)
- **Frontend DEFAULT_FIELD_MAPS** expanded with sensible default mappings for all 13 modules
- Verified via testing agent iteration_271 — 18/18 backend tests PASS



### Phase 8: Product Detail Cleanup + CRM Sync Completions (March 2026)
- **Hardcoded policy text removed** from `StickyPurchaseSummary.tsx`: "No refunds for delivered services", "Subscriptions cancel at end of billing month", "Secure payment via our payment provider" — all layouts
- **Hardcoded fallback forms removed** from `ProductDetail.tsx`: Quote and Scope modals no longer show hardcoded fields when no schema is configured; clean empty state  
- **URL param autofill** for intake questions: `?question_key=value` in product URL pre-fills intake form answers (supports string, number, multiselect via comma-separated)
- **Bulk Sync Now covers all 13 modules**: `oauth.py` updated from 3 → 13 modules with enrichment applied
- Verified via testing agent iteration_272 — all checks passed

### Phase 9: API Documentation (March 2026)
- **Created `/app/docs/api.md`** — complete API reference covering all 37 endpoint groups and 200+ endpoints
- **Modules documented**: Auth, Public Store, Customer Portal, Checkout, Admin Catalog, Admin Customers, Orders, Enquiries, Subscriptions, Plans, Promo Codes, Terms, Users & Permissions, Settings, Website Settings, Email Templates, Integrations (Zoho CRM/Mail/Books/WorkDrive, Stripe, GoCardless), Finance, API Keys, Webhooks, Taxes & Invoices, Tenants, Resources, Articles, Forms, Import/Export, Audit Logs, Store Filters, GDPR, Partner Billing, OAuth, Documents, Utilities, Incoming Webhooks
- **All endpoints tested**: 66 GET endpoints + 17 mutation (POST/PUT/DELETE) endpoints = 83 total, 100% PASS
- **Includes**: request body schemas, response shapes, curl examples, field validation notes, error codes, quick-start test script

### Phase 12: Dark Mode Deep Fixes (March 2026)
- **Root cause fixed**: `.aa-bg` had hardcoded `linear-gradient(#ffffff, #f8fafc)` → replaced with CSS-variable radial gradients using `var(--aa-bg)`, `var(--aa-accent)`, `var(--aa-primary)`
- **Shadcn deep integration**: `--muted`, `--secondary`, `--accent`, `--popover`, `--border` Shadcn CSS vars dynamically set to dark equivalents when `aa-dark` activated; light defaults restored on Slate Pro
- **Store layout**: Removed `w-full` class conflict on sidebar aside; now uses clean `hidden md:block` pattern
- **Midnight Tech palette redesigned**: Primary `#161b22` (hero) vs Background `#0d1117` (page) = 30-unit color difference = clear depth; Accent `#58a6ff` (GitHub-dark bright blue)
- **Ocean Deep palette redesigned** with proper 3-layer depth
- Tested via iteration_276 — **10/10 tests PASS** (page bg dark, admin full dark, store layout side-by-side, hero depth confirmed, Shadcn vars dark)
- **New CSS variables**: `--aa-card`, `--aa-surface`, `--aa-primary-fg` (auto-luminance), `--aa-card-border`, `--aa-glow` (auto from accent), `--aa-text`, `--aa-muted`
- **Global `.aa-dark` class**: Auto-toggled on `<html>` when background luminance < 0.08 — overrides ALL hardcoded Tailwind slate classes (bg-white, text-slate-*, border-slate-*, inputs, tables, badges, hover states)
- **Dot pattern hero texture**: `radial-gradient` dots using `--aa-primary-fg` at 22% opacity (replaced harsh grid lines)
- **Theme presets** (3): Midnight Tech (GitHub-dark palette), Slate Pro (light default), Ocean Deep (teal dark)
- **All form inputs** (`auth-input`, standard inputs) use CSS variables — no hardcoded colors remain
- Tested via iteration_274 + iteration_275 — dark mode confirmed fully readable (table cells rgb(230,237,243) on dark bg, no black-on-black)
- **New CSS variables**: `--aa-card`, `--aa-surface`, `--aa-primary-fg` (auto-computed), `--aa-card-border`, `--aa-glow` (auto-derived from accent)
- **New utility classes**: `.aa-card`, `.aa-card-glow`, `.aa-surface`, `.aa-badge` + semantic variants (success/danger/warning/muted/accent), `.aa-mono` (JetBrains Mono), `.aa-grid-texture` (hero grid overlay), `.aa-active-accent` (sidebar glow), `.aa-input`, `.aa-glow-sm/md`, theme-aware scrollbars
- **Admin panel**: 3 one-click theme presets (Midnight Tech dark, Slate Pro light, Ocean Deep teal) with color swatches + 2 new color pickers (Card Background, Surface)
- **Components**: OfferingCard → CSS variables throughout; TopNav → glass backdrop; Admin sidebar → CSS var border/bg; Hero sections → grid texture; AppShell → CSS var background
- **Backend**: `card_color`, `surface_color` added to `AppSettingsUpdate` model + all 3 settings endpoints (`/settings/public`, `/website-settings`, `/admin/website-settings`)
- Verified via testing agent iteration_274 — **18/18 backend + 10/10 frontend = 100% pass rate**
- **TopNav.tsx**: Hamburger menu on mobile (`md:hidden`), animated mobile drawer with all nav links, closes on route change
- **Admin.tsx**: Collapsible sidebar on mobile — toggle button shows active tab name, overlay backdrop, sidebar slides in from left with z-index layering
- **Store.tsx**: Mobile filters toggle button, `flex-col md:flex-row` layout, responsive hero padding (`px-6 md:px-10`), search+sort wraps on mobile, aside cleaned up
- **Resources.tsx**: Responsive hero padding fixed
- **index.css**: Global mobile CSS — admin tables get `overflow-x: auto` scroll container, store layout stacks vertically on mobile
- Verified via testing agent iteration_273 — 8/8 tests PASS (100%)

### P0 — Critical (None currently)

### P1 — High Priority
- New landing page (needs design prompt from user)
- Radio filters for Role & Status columns in Users table

### P2 — Medium Priority
- Spacing on Resources and My Profile pages (minor UI inconsistency)
- Resend API Key UI (allow tenants to enter/save Resend API key when provider = Resend)
- Centralize Email Settings

### P3 — Future / Backlog
- Google Drive & OneDrive Integration
- Customer Portal: self-service subscription cancellation, renewal dates, Reorder button
- UsersTab.tsx refactor (1200+ lines, break into smaller components)

## Credentials
- Platform Admin: admin@automateaccounts.local / ChangeMe123! / partner_code: automate-accounts

## 3rd Party Integrations
- GoCardless (Payments)
- Stripe (Payments)
- Zoho Suite (OAuth, WorkDrive)
- Resend (Email — configured, requires API key)
- open.er-api.com (FX rates)
- jspdf & html2canvas (Frontend PDF)
- framer-motion (UI Animations)
