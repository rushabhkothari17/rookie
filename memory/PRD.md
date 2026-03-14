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

## Completed Work Log

### Session: Mar 2026 - CRITICAL SSRF Fix in Webhook Delivery
- **CRITICAL fixed**: Added `_validate_webhook_url()` to `backend/services/webhook_service.py` — resolves hostnames via DNS and blocks all private/reserved IP ranges before any outbound HTTP request.
- **Blocked ranges**: 127.0.0.0/8 (loopback), 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16 (private), 169.254.0.0/16 (AWS metadata/link-local), 100.64.0.0/10 (CGN), documentation ranges, IPv6 equivalents.
- **Defense-in-depth**: Validation applied at 3 layers: (1) webhook create/update, (2) test delivery, (3) async retry delivery — defends against DNS rebinding attacks.
- **scheme blocking**: Only `http://` and `https://` allowed; `file://`, `ftp://`, etc. are rejected.
- **Testing**: 21/21 backend tests passed (iteration_291). Test file: `/app/backend/tests/test_ssrf_webhook_protection.py`.

### Session: Feb 2026 - Full Security Audit (3 passes)
- **Pass 1**: ReDoS (5 files), GoCardless webhook bypass, SVG XSS via logo upload
- **Pass 2**: No body size limit (DoS), unbounded pagination, to_list(None), rate limiter memory leak
- **Pass 3 (auth/tenant isolation)**: IDOR on uploads, password reset brute force, plaintext API key fallback, store cross-tenant data leakage (tf={}), logs IDOR, promo code cross-tenant, articles customer lookup cross-tenant
- All 13 vulnerabilities fixed and regression tested (iteration_289, iteration_290)
- **Goal**: Consolidate two overlapping storage collections into one source of truth for all integration records.
- **Changes**: Updated `ZohoOAuthService.get_credentials()` + `store_credentials()` in `zoho_service.py`; updated all 30+ `db.integrations` reads/writes in `routes/admin/integrations.py` and `routes/admin/finance.py` to use `db.oauth_connections`.
- **Migration**: Wrote and ran `migrate_integrations.py` (0 existing docs migrated in this env); `db.integrations` collection **dropped**.
- **Testing**: 47/47 backend + frontend tests passed (iteration_289).

### Session: Mar 2026 - P2 Fix: Encryption at Rest for Integration Secrets
- Created `services/encryption_service.py` (Fernet AES-128-CBC + HMAC-SHA256, `enc:` prefix for migration safety).
- Added `ENCRYPTION_KEY` to `backend/.env`.
- **Write paths encrypted**: `_sync_to_settings` (oauth.py), `SettingsService.set()`, `oauth_connections.credentials` on validation save.
- **Read paths decrypted**: `SettingsService.get()`, `email_service.py`, `refund_service.py`, `oauth.py` (validate, token refresh, Zoho Books).
- **Bonus fix**: `refund_service.py` was reading Stripe key from wrong collection (`db.settings`) — fixed to read from `oauth_connections` with fallback to `app_settings`.
- Sensitive fields encrypted: `api_key`, `access_token`, `client_secret`, `refresh_token`, `secret_key`, `password` in `oauth_connections.credentials`; `resend_api_key`, `stripe_secret_key`, `gocardless_access_token`, `stripe_publishable_key` in `app_settings`.
- All fixes curl + unit test verified.

### Session: Mar 2026 - Security Audit & Hardening
- **CRITICAL fixed**: `get_current_user` now explicitly rejects JWTs with `type: "refresh"` — refresh tokens can no longer impersonate access tokens.
- **HIGH fixed**: `password_hash` now excluded from all 6 `find_one` calls in `users.py` and `security.py`.
- **MEDIUM fixed**: Added `Strict-Transport-Security: max-age=31536000; includeSubDomains` to `SecurityHeadersMiddleware`.
- **MEDIUM fixed**: Rate limiter `_get_client_ip` validates X-Forwarded-For length (max 45 chars = IPv6) to mitigate header-stuffing attacks.
- **Known remaining (P2)**: Integration secrets (Stripe, GoCardless, Resend) stored plaintext in `app_settings` — recommend AES encryption at rest. Requires data migration.
- **Testing**: All fixes curl-verified.

### Session: Mar 2026 - Full Audit Logging Coverage
- **P0** — Added missing `create_audit_log` calls to `coupons.py` (create/update/delete), `currencies.py` (add/remove), `platform_billing_settings.py` (update), `intake_forms.py` (delete form, admin create/update record, add/update/delete note, portal submit).
- **P1** — Added `/logs` GET endpoints for: coupon, form (forms management), intake_form definition, webhook (audit trail). Added `AuditLogDialog` log buttons to: Coupons (PlansTab), Forms Management, Intake Forms builder, Webhooks (separate from delivery logs).
- **P2** — Fixed `LogsTab` `ENTITY_TYPES` filter: 34 entries, all lowercase, added `coupon`, `webhook`, `intake_form`, `intake_form_record`, `form`, `currency`, `platform_billing_settings`, etc. Fixed case-mismatch (stored lowercase vs capitalized filter).
- **Testing:** 100% frontend pass (iteration 288).

### Session: Mar 2026 - P1 Fix: Backend Mandatory Rejection Reason Enforcement
- **Fix**: Added a 400-guard in `backend/routes/admin/intake_forms.py` → `update_record_status` endpoint. If `status == "rejected"` and `rejection_reason` is empty/missing, the API now returns `HTTP 400` with a clear message.
- **Tested**: curl confirmed — reject without reason → 400, reject with reason → 200.

### Session: Mar 2026 - P0 Bug Fix: Version History PDF Downloads
- **Root Cause**: `const downloadPDF = (record: IntakeRecord) => {` declaration was missing from `AdminIntakeFormsTab.tsx`, causing the `IntakeFormRecords` component to be typed as returning `void` instead of `ReactNode`.
- **Fix**: Added the missing function declaration wrapper at line 575 in `AdminIntakeFormsTab.tsx`.
- **Result**: Both `downloadPDF` (current record) and `downloadVersionPDF` (historical versions) work correctly. Version history modal now shows each archived version with a working Download PDF button.
- **Seed data**: Fixed missing `archived_at` timestamps in test version entries in MongoDB.
- **Testing**: 100% frontend pass rate (testing agent iteration 286).

### Session: Feb 2026 - Password Reset Link + Product Page Audit
- **Password Reset Link Expiry Timer**:
  - `ForgotPassword.tsx`: live countdown timer from `?expires=ISO_TIMESTAMP` URL param — grey badge counting down `Xm Ys`, turns amber in last minute, turns red with "Link Expired" message when past expiry; submit button disabled + shows "Link Expired" text
  - Backend: passes `reset_expires_at` (formatted human-readable UTC) as email variable + `expires` ISO timestamp in URL
  - Email template: shows exact expiry time instead of generic "1 hour"
  - `available_variables` updated to include `{{reset_expires_at}}`

- **Admin-Initiated Password Reset Link** (was sending code-only, now sends clickable link):
  - New `admin_password_reset` email template with "Set New Password" button and `{{reset_link}}` variable
  - `customers.py` + `users.py`: build `reset_link = {APP_URL}/forgot-password?email=...&code=...&partner=...`, use new trigger
  - `ForgotPassword.tsx`: reads `?email`, `?code`, `?partner` from URL params, skips to set-password step, hides code field when pre-filled
- **Product Page Audit — card_description removed from detail pages**:
  - `ShowcaseLayout.tsx`: hero subtitle now uses `product.tagline` (not `card_description`)
  - `ApplicationLayout.tsx`: overview intro now uses `product.tagline` (not `card_description`)
  - `ProductHero.tsx` (used by Classic): fallback chain fixed from `description_long || tagline || short_description` → `tagline || short_description`

### Session: Feb 2026 - Product Layout Standardization & Admin Dark Mode
- **P0 Complete: All Product Page Layouts Standardized** (all 4 non-standard layouts rewritten):
  - `QuickBuyLayout.tsx`: Removed `slice(0,4)` question cap, replaced local `formatCurrency` with shared utils, replaced `bg-blue-600` with `var(--aa-primary)`, added free/subscription indicators, ReactMarkdown for custom sections, all sdp_* labels from WebsiteContext
  - `WizardLayout.tsx`: Fixed progress bar (0% first step → 100% review step), fixed boolean review display (case-insensitive), removed local `formatCurrency`, fixed `isEnquiry` vs `isRFQ` inconsistency, CSS variables throughout, all sdp_* labels
  - `ApplicationLayout.tsx`: Full 4-section nav (Overview/Form/Pricing/FAQs), fixed `isFree` handling in pricing, CSS variables, sdp_* labels for all nav items and buttons
  - `ShowcaseLayout.tsx`: Theme-aware hero gradient using CSS variables, pricingQuestions vs infoQuestions split, CSS variables for calculator panel, sdp_* labels, ReactMarkdown sections
  - `ClassicLayout.tsx`: Added `useWebsite()` for sdp_* labels, fixed CTA labels to use `formatCurrency`, fixed subscription/free indicators to use CSS vars
- **Admin Dark Mode Fix**:
  - `websiteTabShared.tsx`: `AuthTile`, `FormTile`, `SectionDivider`, `BaseCurrencyWidget`, `Field` components all updated to use CSS variables (`var(--aa-card)`, `var(--aa-border)`, `var(--aa-text)`, `var(--aa-muted)`, `var(--aa-surface)`)
- **Service Detail Page Tile (Admin > Auth & Pages)**:
  - New "service_detail" `AuthSlide` type added
  - New tile added in App Pages tab with `data-testid="auth-tile-service-detail"`
  - Slide panel with 18 configurable fields: section headers (intake, features, about, faqs, key features, additional info, pricing), CTA labels (free/buy/quote), Showcase panel labels, Application layout nav/button labels, Wizard step/review/submit labels
  - All `sdp_*` keys added to `WebsiteData`, `WEB_DEFAULTS`, `WebsiteSettings`, `DEFAULT_SETTINGS`

### Session: Feb 2026 - Admin Features & Bug Fixes
- **Admin-Initiated Password Reset** (P0 complete):
  - Backend: `POST /api/admin/customers/{id}/send-reset-link` and `POST /api/admin/users/{id}/send-reset-link` — super admin only, increments `token_version` (forces logout), sends password reset email via Resend (mocked if no API key)
  - Frontend: "SECURITY ACTIONS" section in Customer and User edit modals with "Send Password Reset Link" button
- **Active Tab Highlight Fix** (P1 complete, recurring issue resolved):
  - Root cause: Radix `TooltipTrigger asChild` was overriding `TabsTrigger`'s `data-state` attribute — breaking CSS `[data-state="active"]` rules
  - Fix: Used `React.createContext<string>("")` (ActiveTabCtx) to share `activeTab` with `SideTab`; applied active styles via inline `style` prop instead of CSS data-state selector
- **Dark Mode Text Selection Fix** (P1 complete):
  - Added `.aa-dark ::selection { background: var(--aa-accent); color: var(--aa-bg); }` in `index.css`
- **404 on Logout Mitigation** (P1 partial):
  - `api.ts` now skips token refresh attempt if no token in localStorage (prevents spurious background 401→refresh cycles after logout)
- **UI Standardization** (previous session): All admin tables/headers aligned to Products table style
- **ResizeObserver Fix** (previous session): Set `avoidCollisions={false}` in base UI components
- **429 Rate Limiting Fix** (previous session): Increased global limit + path-keyed limits
- **Stale Data Fix** (previous session): `get_store_name()` helper centralizes store name access across 5 services
- **Dark Mode Overhaul** (previous session): Comprehensive CSS rewrite for dark theme

### Backend (FastAPI + MongoDB)
```
/app/backend/
├── server.py              # App startup, seeds platform tenant
├── routes/
│   ├── admin/
│   │   ├── tenants.py     # Partner org CRUD, create-partner endpoint
│   │   ├── users.py       # User management, tenant-scoped email validation
│   │   ├── customers.py   # Customer management, tenant-scoped email validation
│   │   ├── website.py     # Website settings, signup form migration (_migrate_signup_schema + _migrate_partner_signup_schema)
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

### Phase 14: 12 UI Enhancements — Animations, Skeleton, Glass, Tooltips (March 2026)
- **Smooth Page Transitions**: `BaseLayout` + `AppShell` wrap content in `motion.div` keyed by `location.pathname`. Fade-in + slight upward slide on every navigation.
- **Skeleton Loaders**: `SkeletonCard`, `SkeletonRow`, `SkeletonStat`, `SkeletonGrid` reusable components. Used in Store (products), Portal (orders table + stat cards), Articles.
- **Staggered List Animations**: Articles grid cards animate in with `staggerChildren: 0.06`. Portal order rows use staggered `motion.tr` with `delay: idx * 0.04`.
- **Portal Stats + Counter Animation**: `PortalStats` component added above order table showing Orders, Subscriptions, Total Spend. Numbers count up from 0 using `useCountUp` hook with easeOutExpo easing.
- **Glassmorphism Cards**: `aa-glass` CSS class (backdrop-blur 20px, 72% opacity) applied to portal stat cards.
- **Empty States**: `EmptyState` component with icon + title + description. Used in Store (no products/search), Articles (no articles), Portal (no orders).
- **Button Ripple Effect**: CSS `::after` pseudo-element ripple on all `.btn-primary` + `.aa-btn-ripple` buttons. OfferingCard CTA updated with explicit ripple + primary accent style.
- **Button Hover Depth**: All `btn-primary` buttons get `translateY(-1px)` + glow shadow on hover.
- **Admin Sidebar Tooltips**: `SideTab` helper wraps all 32 sidebar `TabsTrigger`s in Radix `Tooltip`. `TooltipProvider` wraps sidebar. Tooltip appears on right on hover.
- **Hover Animations on Sidebar**: `hover:translate-x-0.5` + `hover:bg-[var(--aa-surface)]` on all sidebar items.
- **Page Loader Top Bar**: Gradient progress bar (`--aa-accent` → `--aa-primary`) with glow shadow on route changes.
- **Toast Redesign**: Sonner `Toaster` with `borderRadius:12px`, `backdropFilter:blur(12px)`, brand border color.
- **Hero Accent Line Animation**: `aa-hero-accent` keyframe slide-in on ProductHero accent bar.
- Tested via iteration_278 — **11/12 PASS (92%)**, 1 minor (ripple CSS extended to all buttons ✓ fixed post-test)
- **Cart Preview Bug Fixed**: `orders_preview` endpoint failed for platform admins (tenant_id=null) — now uses `_resolve_tenant_id` + fallback `is_platform_admin` product lookup across all tenants
- **`_resolve_tenant_id` Bug Fixed**: Was checking `role == "platform_admin"` (missing `platform_super_admin`) — now uses `is_platform_admin()` helper
- **Store Search+Sort Layout**: Removed `flex-wrap w-full sm:w-auto` — replaced with `flex-nowrap` + `flex-1 min-w-[120px] max-w-[200px]` on search, so search and sort always render side-by-side
- **Dark Theme Icon Visibility**: `--aa-muted` now explicitly set to `#8b949e` (visible on dark backgrounds) when `aa-dark` mode activates; added `.aa-dark .text-slate-400 svg` CSS overrides
- **Partner Pages Theme**: Login.tsx, Signup.tsx, ForgotPassword.tsx — all `bg-white` containers replaced with `style={{ backgroundColor: "var(--aa-bg)" }}` so they follow admin-configured theme
- **Page Loader Animation**: `PageLoader.tsx` component — top progress bar using gradient from accent to primary, triggers on every `useLocation` change inside BrowserRouter
- **Admin Sidebar Hover Animations**: `TAB_CLASS` updated with `hover:translate-x-0.5 hover:bg-[var(--aa-surface)] transition-all`
- **Store Pagination**: 12 products per page, resets on filter/sort/search change, prev/next + page number buttons with brand primary color active state
- **Cart Item Hover**: Added `aa-cart-item` class with `translateX(2px)` hover effect
- **ProductHero Accent Line**: Added `aa-hero-accent` keyframe animation for accent line slide-in
- **CSS Animations**: Added `aa-product-lift`, `aa-cart-item`, `aa-img-zoom`, `aa-hero-accent`, `aa-float`, `aa-float-slow`, `aa-nav-link` utility classes
- Tested via iteration_277 — **7/7 features PASS (100%)**

### Mar 2026 — Table Standardization & Form Migration Fix
- **Table White Background**: All admin table containers updated from `overflow-hidden` (no bg) → `rounded-xl border border-slate-200 bg-white overflow-x-auto`, matching product table reference style. Files: PlansTab (4 tables), UsersTab, ResourceEmailTemplatesTab, PartnerSubscriptionsTab, ResourcesTab, MyOrdersTab, ArticleCategoriesTab, ArticleTemplatesTab, ResourceCategoriesTab, ArticleEmailTemplatesTab, LogsTab, ReferencesSection, ResourceTemplatesTab, MySubscriptionsTab, TaxesTab, PartnerOrdersTab
- **Currencies Add Button**: CurrenciesTab Add button now uses `size="sm"` to match Products page button style
- **Signup Form Migration Fix**: Fixed bug in `_migrate_signup_schema` — return condition now includes `shift > 0` so schemas missing email/password are correctly returned after injection
- **Partner Signup Migration**: Added `_migrate_partner_signup_schema` function to inject `admin_email`/`admin_password` locked fields into old partner signup schemas. Called in both GET /website-settings endpoints
- Tested via iteration_280 — **6/6 frontend + 11/11 backend PASS (100%)**

- **Dynamic Visibility (Part A — Field-level)**: Added `VisibilityRuleSet` types + `VisibilityRuleEditor` component to `FormSchemaBuilder.tsx`. Each field now has a collapsible "Visibility rule" panel with AND/OR group logic, up to 3 groups × 4 conditions, operators (equals/not_equals/contains/not_contains/not_empty/empty), and a field-picker dropdown. Eye icon in field header when rule is active. `UniversalFormRenderer.tsx` evaluates rules in real-time — hidden fields are removed from the rendered list.
- **Dynamic Visibility (Part B — Form-level)**: `AdminIntakeFormsTab.tsx` Customer Assignment now has 3 modes: "All customers", "Specific customers only" (customer_ids picker), and "Conditional (profile-based)" which renders `ProductConditionBuilder` reused from `ProductForm.tsx`. Backend updated: `visibility_conditions: Optional[Dict]` field added to create/update models; `_customer_matches_rules` refactored to a clean 3-way priority: specific IDs → profile conditions → all.

- **Gap Fix 4 — Branded PDF**: Both admin and customer PDFs now include: colored header band (brand `primary_color`), logo image (if `logo_url` set), store name in white, form title + customer meta, brand-colored divider, question/answer pairs with label hierarchy, signature box, and timestamped footer. Async logo fetch using FileReader → base64.
- **Mandatory Rejection Reason**: Admin selecting "Rejected" from status dropdown now opens a Dialog requiring a reason before confirming. Reason is sent to backend and included in the rejection email notification.

- **Gap Fixes (Gap 1, 2, 5)**: (1) Signature cleared on re-edit — `openForm()` in `IntakeFormPage.tsx` now strips `signature_data_url`/`signature_name` from pre-fill so customer must always re-sign. (2) Customer assignment UI added to `IntakeFormBuilder` — admin can choose "All customers" (default) or "Specific customers only" with searchable multi-select; `customer_ids` saved to backend. (3) Re-edit approved form warning — Dialog explains versioning impact and blocks accidental editing.

- **ColHeader Column Filters on Intake Form Records**: Replaced separate filter bar (search input + status dropdown + form dropdown) with `ColHeader` inline column filters matching the Products table UX. Columns now support: Customer (text search), Form (radio select), Status (radio select), Submitted (date range + sort), Version (sort only), Partner (sort only). Backend updated with `sort_by`/`sort_dir` params (whitelisted via `_SORTABLE_COLS`).

### Phase 16: Intake Form System — P0 Bug Fixes (Mar 2026)
- **Email Notifications**: Added `EmailService.send` call in `update_record_status` endpoint (`intake_forms.py`) for `approved` and `rejected` status changes. Uses `intake_form_status_changed` email template with rejection reason HTML block. Non-blocking via `asyncio.create_task`.
- **TypeScript Fix**: Fixed `nav_intake_enabled` boolean/string type comparison in `TopNav.tsx` using `as unknown` cast to handle both string `"false"` (stored by admin settings API) and boolean `false` (WebsiteContext default). Fixed `WebsiteAuthSection.tsx` to use `setBool` pattern for the checkbox.
- Tested via iteration_285 — **20/20 backend tests PASS (100%)**

### Phase 16: Intake Form System (Mar 2026)
- **Universal Form Builder**: Added `terms_conditions` + `signature` field types to `FormSchemaBuilder.tsx` and `UniversalFormRenderer.tsx`. T&C auto-appends a locked canvas+typed-name signature field. Available across all forms in the system.
- **Backend**: New `intake_forms` + `intake_form_records` collections with full CRUD, status transitions (pending→submitted→under_review→approved/rejected), versioning, notes, logs, and portal endpoints.
- **Admin Tab**: New "Intake Forms" tab under Content section with sub-tabs: "Intake Form Records" (table with filters, actions: view, versions, logs, notes, PDF download) and "Intake Form Builder" (FormSchemaBuilder + system locked fields + per-form settings: enabled/disabled, auto-approve, allow-skip-signature).
- **Storefront Page**: `/intake-form` — login required, shows all assigned forms with status, allows submit/re-submit, customer PDF download.
- **Checkout Gate**: Cart.tsx blocks checkout (all types incl. free) if any intake form is not "approved". Shows modal with link to `/intake-form` and per-form reason.
- **Footer Nav Management**: All 4 nav links (Store, Articles, Portal, Intake Form) now managed from Admin → Auth & Pages → Footer → Navigation. Nav intake link label + toggle configurable.
- **Seeding**: New tenants receive a default "Client Intake Questionnaire" with sample questions + T&C + signature field.
- **Currency Fix**: Partner subscription/order now uses partner's `base_currency` not hardcoded "USD".
- **Bug Fix** (by testing agent): Added missing `/api` prefix to intake_forms router, fixed TypeScript issues, fixed boolean comparison in AppFooter.
- Tested via iteration_285 — **21/21 backend tests PASS (100%)**

### Phase 15: New Partner Onboarding Overhaul (Mar 2026)
- **Address Validation**: `address.region` is now mandatory if any other primary address field is provided during partner registration
- **Auto-create Partner Subscription + Order**: `verify-partner-email` now creates `partner_subscription` + `partner_order` for the free/default plan on partner signup
- **Dynamic Product Currency**: Sample product now uses partner's selected `base_currency` instead of hardcoded GBP
- **Placeholder Content**: Sample product seeded with `tagline`, `description_long`, `bullets`, `faqs`, `card_description` placeholder text
- **Default Website Settings**: `register_subtitle`, `signup_form_subtitle` now populated with sensible defaults; `email_from_name` defaults to org name
- **Email Templates Enabled**: `order_placed` and `subscription_created` templates now `is_enabled: True` by default for new tenants; all templates created via `ensure_seeded()` at signup
- **Favicon Upload**: New UI in Admin > Branding with `POST /api/admin/upload-favicon`; favicon applied to browser tab via DOM; stored as base64 in `app_settings`; exposed in `/settings/public` and `/admin/settings`
- Bug Fix: `UnboundLocalError` in `verify-partner-email` — removed duplicate `from datetime import timezone` inside conditional blocks that shadowed the module-level import
- Tested via iteration_284 — **19/19 tests PASS (100%)**

### P0 — Critical (None currently)

### P1 — High Priority
- New landing page (needs design prompt from user)
- Radio filters for Role & Status columns in Users table
- Resend API Key UI (allow tenants to enter/save Resend API key when provider = Resend)

### P2 — Medium Priority
- Spacing on Resources and My Profile pages (minor UI inconsistency)
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
