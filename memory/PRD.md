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

### Session: Mar 2026 - TenantSwitcher Removed + DB Reset
**Changes:**
- Deleted `TenantSwitcher.tsx` and `CustomerSwitcher.tsx` (frontend components)
- Removed all X-View-As-Tenant and X-View-As-Customer header logic from:
  - `api.ts` request interceptor
  - `TopNav.tsx`, `Admin.tsx`, `EnquiriesTab.tsx` (frontend)
  - `core/tenant.py` (get_tenant_admin, get_tenant_super_admin, get_tenant_filter, tenant_id_of)
  - `articles.py`, `resources.py`, `store.py`, `admin/website.py` (backend)
- Simplified EnquiriesTab: removed partner selection step (now loads all customers/products directly)
- Database fully reset (all 46 collections dropped + reseeded via backend startup)
- Seeded data: platform_super_admin user, automate-accounts tenant, Free Trial plan

### Session: Mar 2026 - Tax Logic Centralization + Sticky Scrollbar Fix + Tax Settings Lock
**Issues fixed:**
1. **Sticky Scrollbar**: Fixed `StickyTableScroll.tsx` - sticky scrollbar now only shows when table's native scrollbar is out of viewport (`rect.bottom > window.innerHeight`). Previously showed even when table bottom was visible.
2. **Centralized Tax Utility**: Created `/app/frontend/src/utils/taxUtils.ts` with `computeTax()` function. Priority: override rules (by priority desc) → tax table (state-specific preferred) → No tax fallback. `resolveCountryCode()` normalizes country names to ISO codes.
3. **PartnerOrdersTab + PartnerSubscriptionsTab**: Removed local COUNTRY_NAME_TO_ISO/resolveCountryCode. Now uses `computeTax()` with: partner address as primary, org address (`/admin/tenants/my`) as fallback, override rules checked first. Also loads org address + override rules on mount.
4. **OrdersTab (manual orders)**: When customer is selected, auto-populates tax based on: tax_exempt → No tax; customer address or org address fallback; computeTax() checks override rules then tax table.
5. **TaxesTab Settings Panel locked**: When enabling tax collection, validates org has country in address + matching tax rules exist. Country/state pre-populated from org address and shown as read-only (with Lock icon). No editable selects when enabled. Uses `/admin/tenants/my` for org address instead of `/admin/tenants`.


**Features added:**
1. **Tax fields on Partner Orders**: `tax_name`, `tax_rate` inputs + auto-calculated tax amount display. Backend `PartnerOrderCreate`/`PartnerOrderUpdate` support all 3 fields. Tax saved to DB.
2. **Tax fields on Partner Subscriptions**: Same fields added to form and `PartnerSubscriptionCreate`/`PartnerSubscriptionUpdate`
3. **Tax fields on Customer Manual Order**: Added `tax_name`, `tax_rate` to manual order form in `OrdersTab.tsx` and `ManualOrderCreate` model
4. **Refund functionality for Partner Orders**: Matches customer orders UX — `RotateCcw` button for paid/partially_refunded orders, refund dialog with amount/reason/provider, partial → `partially_refunded`, full → `refunded`. Backend: `POST /admin/partner-orders/{id}/refund` + `GET /admin/partner-orders/{id}/refund-providers`
5. **Paid date conditional visibility**: `paid_at` field hidden when status ≠ "paid"; auto-clears when status changes away from "paid"
6. **`partially_refunded` status**: Added to `STATUSES` array and `STATUS_COLORS` (orange badge) in PartnerOrdersTab

### Session: Mar 2026 - Partner Orders/Subscriptions Validation + Free Plan Downgrade
**Issues fixed:**
1. **Validation messages**: Per-field specific errors instead of generic "Partner, description and amount are required"
2. **Negative amount**: Blocked in both orders and subscriptions (validates `amt < 0`)
3. **Space-only description**: `.trim()` check before validation + description trimmed on save
4. **Plan not retained in edit**: `plan_id: order.plan_id || ""` (was hardcoded `""`)
5. **Date validations (orders)**: Due date ≥ invoice date; Paid date required when status=paid; Paid date forbidden with non-paid status; Paid date cannot be future
6. **Paid At required indicator**: Red asterisk shown on Paid At label when status is "paid"
7. **Free plan downgrade**: Backend `plan_management.py` now includes `is_default` plans in `visible_plans` — Free Trial always appears as downgrade option
8. **TypeScript fix**: Added `plan_id?: string` to `PartnerOrder` type (was missing, caused compile error)

### Session: Mar 2026 - Address Field Fixes + RBAC Hardening
**Issues fixed:**
1. **Address Line 2 label**: `AddressFieldRenderer.tsx` hardcoded "Suite / Unit" renamed to "Address Line 2" — applies consistently across all user-facing forms (customer signup, partner signup, profile, checkout, add-customer)
2. **State/Province mandatory**: Default address config updated to `state.required: True` in backend, `FormSchemaBuilder.tsx`, `WebsiteAuthSection.tsx`. Required asterisk `*` now shows on form. Migration function `_migrate_state_required()` applies to existing tenants
3. **City blocks numeric input**: `AddressFieldRenderer.tsx` city `onChange` strips digits via `.replace(/[0-9]/g, "")`
4. **Usage & Limits RBAC**: `UsageDashboard` hidden from partner admins in `PlanBillingTab.tsx` and `Admin.tsx` usage tab
5. **Partner Sign-Up Page tile**: Confirmed hidden from partner admins via `{isPlatformAdmin}` check

### Session: Mar 2026 - Platform Admin Permission Fixes
- Fixed store empty products for platform admin (uses DEFAULT_TENANT_ID not None)
- Fixed IntakeFormPage 403 for admin users (redirect to admin panel)
- Documented permission differences between all admin roles
**Goal**: Fix platform super admin not being able to see all products/resources/intake forms in certain contexts.

**Root causes identified & fixed:**
1. `_resolve_store_tenant_id` in `store.py` returned `None` for platform admins → store returned empty products/categories. Fixed to use `partner_code` or `X-View-As-Tenant` or `DEFAULT_TENANT_ID` instead.
2. `IntakeFormPage.tsx` (customer portal page) called `/portal/intake-forms` which returns 403 for admin users. Fixed: admin users now see a redirect to the admin panel instead of the 403 error.
3. `TenantSwitcher.tsx` only showed for `platform_admin` role, not `platform_super_admin`. Fixed: both roles now see the TenantSwitcher.
4. `articles.py` public listing now uses `X-View-As-Tenant` for platform admins.

**Permission model documented:**
- `platform_super_admin` vs `platform_admin`: Super admin can deactivate tenants, manage currencies, delete plans, manage coupons/OTP rates, platform billing settings. Platform admin has view/read-only for these.
- `partner_super_admin` vs `platform_admin`: Fundamentally different scopes. Platform admin is cross-tenant, partner super admin is tenant-scoped with My Billing section.
- `partner_super_admin` vs `partner_admin`: Super admin has all modules; partner admin only has explicitly assigned modules. Super admin can use get_tenant_super_admin gated actions (bulk user/customer ops, logs).


### Session: Mar 2026 - Comprehensive Input Validation Sweep (Issue: "Does it stop typing for all fields?")
**Goal**: Hard-enforce character limits on every writable form field across the entire app (frontend maxLength + backend Pydantic max_length), with live character counters on the UI.

**All enforced limits — by category:**

| Category | Limit | Fields |
|---|---|---|
| MICRO (auth) | 6 | OTP verification code |
| MICRO (identity) | 10 | Country code, currency code |
| MICRO (identity) | 20 | Postal code |
| MICRO (identity) | 30 | Colour hex/name |
| MICRO (identity) | 50 | Phone number, domain |
| AUTH | 100 | Promo/coupon codes, field keys, city |
| AUTH | 128 | Password |
| SHORT | 200 | Full name, company, job title, address lines, slug, email subject, Stripe price ID, article template category, scope ID |
| SHORT | 253 | Custom domain hostname |
| SHORT | 320 | Email address |
| NAME | 500 | Product/category/form/terms title, article name, webhook name, intake question label, plan name, bullet point limit N/A (200), article/resource template name |
| WEBSITE | 1,000 | All website settings text fields (backend validator), reference value, GDPR reason |
| NOTE | 5,000 | Notes, short descriptions, FAQ answers, promo notes, coupon notes, intake form descriptions, rejection reasons, downgrade messages, cancel reasons, order delete reasons, subscription notes, order notes, quote messages |
| CONTENT | 10,000 | FormSchemaBuilder terms_text blocks |
| CONTENT | 500,000 | Rich HTML: terms content, email HTML body, articles, resources, product long description, intake HTML blocks |

**Files modified (backend):**
- `backend/models.py` — CustomerUpdate, AddressUpdate, SubscriptionUpdate, ManualOrderCreate, ManualSubscriptionCreate, CancelSubscriptionBody, OrderDelete, QuoteRequest, IntakeQuestion, CustomSection, ScopeRequestFormData
- `backend/routes/admin/plans.py` — PlanCreate model added with Field(max_length=...)
- `backend/routes/article_templates.py` — ArticleTemplateCreate + ArticleTemplateUpdate Pydantic models added (was Dict[str,Any] — HIGH priority vulnerability)
- `backend/routes/admin/webhooks.py` — WebhookCreate/WebhookUpdate Pydantic models (was Dict[str,Any]); dead elif removed; 422 validation confirmed via curl

**Files modified (frontend):**
- `frontend/src/lib/fieldLimits.tsx` — NEW: shared LIMIT_* constants + CharCount component
- All admin form pages (TermsTab, EmailSection, ArticleEmailTemplatesTab, ResourceEmailTemplatesTab, AdminIntakeFormsTab, PlansTab, ProductForm, CategoriesTab, ArticleCategoriesTab, ResourceCategoriesTab, ResourcesTab, PartnerSubscriptionsTab, WebhooksTab, ReferencesSection, websiteTabShared, PlanBillingTab, ArticleTemplatesTab, PromoCodesTab, CustomDomainsSection)
- `frontend/src/components/FormSchemaBuilder.tsx` — placeholder (200), helper_text (500), tooltip_text (500), terms_text (10,000)
- `frontend/src/components/UniversalFormRenderer.tsx` — Fixed hardcoded 100-char limit bug, added amber/red color thresholds
- `frontend/src/pages/admin/IntakeSchemaBuilder.tsx` — Added max_length field to IntakeQuestion interface + UI config option for single_line/multi_line fields
- `frontend/src/pages/store/layouts/types.ts` — Added max_length to IntakeQuestion interface
- `frontend/src/pages/store/layouts/utils.tsx` — single_line max 500, multi_line max 5000 (configurable via field.max_length)
- `frontend/src/pages/Cart.tsx` — Quote form name (200), email (320), company (200), phone (50), message (5000), promo (100)
- `frontend/src/pages/Profile.tsx` — GDPR delete reason (1000)
- `frontend/src/pages/ForgotPassword.tsx` — password (128)
- `frontend/src/pages/VerifyEmail.tsx` — email (320), code (6)

**Character counter UX:**
- Appears when user starts typing (hidden on empty fields)
- `text-slate-400` when < 80% of limit
- `text-amber-500` when 80–95% of limit
- `text-red-500` when > 95% of limit
- `maxLength` HTML attribute prevents typing past limit at browser level
- Backend Pydantic validation rejects API calls even if browser limit is bypassed


**Vulnerabilities found and fixed (22/22 tests passing):**
1. **Promo code >100% discount** — Pydantic validator blocks >100% percentage in PromoCodeCreate and PromoCodeUpdate
2. **Promo code negative discount** — Rejects negative `discount_value` for both create and update
3. **Checkout negative total** — All 3 discount paths now cap `discount_amount` at `subtotal` + `max(0, total)` floor
4. **Unbounded field lengths (DoS)** — `max_length` added to all text fields in models.py (name=500, description/notes=5000-10000, content=500000)
5. **CSV formula injection** — `_sanitize_cell()` in imports.py prefixes `=+-@|` formula cells with single quote
6. **API key plaintext fallback** — Removed legacy plaintext lookup path from `tenant.py`; SHA-256 hash only
7. **Timing attack (user enumeration)** — Dummy bcrypt on unknown-email paths in all 3 login routes
8. **OTP stored plaintext (previous)** — HMAC-SHA256 keyed with JWT_SECRET
9. **SSRF in webhook delivery (previous)** — IP blocklist with DNS resolution
10. **Checkout status IDOR (previous)** — Ownership check on session_id


- **OTP Hashing**: All 7 OTP generation points now store HMAC-SHA256 hash (keyed with `JWT_SECRET`) instead of 6-digit plaintext in MongoDB. All 3 verification points use `_verify_otp()` with constant-time comparison. Server/dev logs still receive the raw OTP for testing without email.
- **Refresh token body fallback removed**: `/auth/refresh` now accepts token from HttpOnly cookie only — body injection path removed.
- **Checkout status IDOR fixed**: `/checkout/status/{session_id}` now verifies the session belongs to the requesting customer before processing.
- All three changes are in `backend/routes/auth.py` and `backend/routes/checkout.py`.


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

### Phase 17: UI/UX Overhaul Phase 2 (Mar 2026)
- **Command Palette keyboard navigation**: Fixed Ctrl+K palette (was showing nav hints but not actually handling ArrowUp/ArrowDown/Enter). Added `activeIndex` state, keyboard event handler with ArrowUp/ArrowDown/Enter/Escape support, auto-scroll to active item, reset on query change.
- **Table enhancements**: Applied `aa-table-row` class (left accent bar on hover via `box-shadow: inset 3px 0 0 var(--aa-accent)`) to all main admin tables: Products, Users, Enquiries, Resources, Orders, Subscriptions, Customers.
- **Status badges**: Replaced hardcoded `bg-green-100 text-green-700` style badges with semantic CSS-variable-based `aa-badge-success/danger/warning/accent/muted` classes across all admin tabs. Role badges in UsersTab now use `aa-badge-accent/success/warning/muted`.
- **Skeleton loaders**: Added `aa-skel` skeleton rows for Products tab (uses existing `loading` state) and Users tab (new `usersLoading` state added to properly handle loading vs empty states).
- **Empty states**: Added `aa-empty-geo` visual + descriptive text to Products, Enquiries, Users, and Resources tabs when no data exists.
- **Input focus ring**: Enhanced base `Input` component with `focus-visible:ring-2 ring-[var(--aa-accent)]/20 focus-visible:border-[var(--aa-accent)]` for a blue glow effect on focus.
- Tested via iteration_296 — **13/13 Phase 2 features PASS (100%)**



### P1 — High Priority
- New landing page (needs design prompt from user)
- Radio filters for Role & Status columns in Users table
- Resend API Key UI (allow tenants to enter/save Resend API key when provider = Resend)

### Phase 20: Zoho CRM Sync Expansion (Mar 2026)
- **New: Intake Form Submissions** (create + update) — synced on admin create, admin update, status change
- **New: Users (Admin)** (create + update) — synced on create, edit, activate/deactivate; `password_hash` excluded
- **Updated: Enquiries** — now syncs on status update in addition to create
- **Updated: Addresses** — now syncs on update in addition to create
- **Updated: Product Categories** — now syncs on update in addition to create
- **Updated: Plans (platform)** — now syncs on update in addition to create
- `zoho_service._enrich_record_for_module` extended with `intake_submissions` (answers_json, status) and `users` (is_active string, module_permissions JSON, password_hash stripped)
- `webapp_modules` list in `integrations.py` now has 15 modules (up from 13); both new modules appear in CRM mapping UI
- **Note:** Invoices and Refunds are immutable records — no `update_one` exists in the codebase; update sync would be a no-op. Skipped intentionally.
- Verified via API: all 15 modules return correctly from `/api/admin/integrations/crm-mappings`

### Phase 19: 4 UX Fixes (Mar 2026)
- **Ctrl+K keyboard nav bug fixed**: Root cause was keyboard handler being removed/re-added on every keystroke (stale closure). Fix: stable refs (`filteredRef`, `activeIndexRef`) + capture phase (`addEventListener(..., true)`) + deps=[open, onClose, handleSelect] only. Tested: type 'users' → Enter navigates immediately.
- **FAQ search bar**: Search input visible when product has ≥4 FAQs, real-time filtering, keyword highlighting with `<mark>` styled with `--aa-accent`, "No FAQs match" empty state, clear button.
- **Store search bar expand**: Starts at 132px compact → expands to 220px on focus/typing via `onFocus`/`onBlur` JS style manipulation with CSS `transition-all duration-300`.
- **Store sort button compact**: Reduced from `h-9 min-w-[140px]` to `h-8 text-xs w-auto px-3` (89px wide, 32px tall). Sorting still works correctly.
- Tested via iteration_298 — **22/22 assertions PASS (100%)**

### Phase 18: FAQ Accordion — All Product Layouts (Mar 2026)
- Created shared `FaqAccordion.tsx` component with click-to-expand/collapse behavior, chevron rotation animation, and CSS-variable-based theming (light + dark mode compatible).
- Applied to all 5 product layouts: `ClassicLayout`, `ShowcaseLayout`, `WizardLayout`, `QuickBuyLayout`, `ApplicationLayout` — replacing static Q&A blocks and `<details>/<summary>` HTML.
- Includes fade-in + slide-in animation for opening items, `data-testid` attributes for all FAQ triggers and content panels.
- No Radix dependency needed — implemented natively with `useState` to avoid TypeScript/JSX interop issues.

### Phase 26: Footer Dark Mode + SlideOver Save Fix (Feb 2026)
- **Footer text in dark mode**: `--aa-footer-text-muted` was `#8b949e` (grey, near-zero contrast on `--aa-primary: #4f8ef7` blue background). Fixed to `rgba(255,255,255,0.72)`. Added missing `--aa-footer-text-dim: rgba(255,255,255,0.42)` for dark mode.
- **SlideOver dark mode (UI)**: Panel used hardcoded `bg-white` (invisible in dark) and Save button used `bg-slate-900` (near-invisible on dark card). Fixed to use `var(--aa-card)` for panel and `var(--aa-primary)` for Save button. All text/borders now use CSS variables.
- **Footer save root cause (backend)**: `WebsiteSettingsUpdate._cap_string_lengths` validator iterated ALL request dict keys including undeclared extra fields (e.g., `quote_form_schema` at 870 chars). With default 100-char limit, caused 422 on ALL footer saves. Fix: skip undeclared model fields in the validator.
- **Tested**: 100% pass rate (iteration_303). Both light and dark mode verified.

### Phase 25: ProductForm Spacing Fix + Clone Product Feature (Feb 2026)
- **ProductForm spacing**: Changed `sectionCls` from `"space-y-6"` → `"flex flex-col gap-6"` and `cardCls` from `"... space-y-5"` → `"... flex flex-col gap-5"`. Also fixed the billing type inner container from `space-y-3` → `flex flex-col gap-3`. All sections in the product form (General, Pricing, Visibility tabs) now have correct spacing when switching between conditional pricing types (Internal/External/Enquiry).
- **Clone Product feature**: Added `POST /api/admin/products/{id}/clone` backend endpoint — copies all fields, generates new ID, appends `_cloned` to name, sets `is_active: False`, logs audit entry. Added Clone button (with Copy icon, loading state) in the Products table next to Edit. Toast notification on success. Table auto-refreshes after clone.
- **Tested**: 100% pass rate (iteration_302). Backend: 8/8, Frontend: 100%. Clone creates correct `_cloned` suffix + Inactive status.

### Phase 24: Codebase-Wide Spacing Fix + Dark Mode Text Contrast (Feb 2026)
- **P0 — Spacing Bug**: `space-y-*` fails on containers with conditional children wrapped in `display:contents` spans. Fixed by replacing ALL top-level `space-y-*` containers with `flex flex-col gap-*` across the entire app (30+ admin tabs, Portal, Store, store layouts). Files changed: all `*Tab.tsx` files in `/pages/admin/`, `Portal.tsx`, `Store.tsx`, `store/layouts/ShowcaseLayout.tsx`, `WizardLayout.tsx`. 
- **P1 — Hero Text Contrast**: `text-slate-300/400` overrides in dark mode used semi-transparent colors that became near-invisible on the `--aa-primary` blue hero backgrounds. Fixed by: (1) Changing `text-slate-400` override from `color-mix(... transparent)` to a solid `color-mix(... var(--aa-text))`, (2) Adding hero-section-specific overrides in `index.css` giving white-based colors (`rgba(255,255,255,0.55/0.70)`) to text inside `[data-testid="store-hero"]` and `[data-testid="cart-hero"]`.
- **Tested**: 100% pass rate (iteration_301). All spacing gaps confirmed 16-40px. Dark mode text readable on all hero sections.

### Phase 23: Cart Page Section Gap Fix (Mar 2026)
- **Root cause**: `space-y-*` uses `> :not([hidden]) ~ :not([hidden])` CSS selector (direct child combinator). All conditional JSX renders (`{condition && <div>}`) are wrapped in `<span style="display:contents">` elements in the DOM. CSS applies `margin-top` to these spans, but `display:contents` discards the element's own box model — margins have zero visual effect. Actual section divs inside are grandchildren, never receiving the gap.
- **Fix**: Replaced all `space-y-8` → `flex flex-col gap-8` and `space-y-4` → `flex flex-col gap-4` in Cart.tsx. In CSS Flexbox, `display:contents` children are promoted as direct flex items, so `gap` correctly applies between Cart Items, Payment Method, Subscription date, etc.
- **Specifically fixed**: (1) Outer `cart-page` wrapper: hero → content grid gap, (2) Left column: Cart Items → Payment Method gap, (3) Right column: Promo Code → Order Summary → Terms gap, (4) Terms section: checkbox → Create Order button gap (was 0px, now 16px).
- **Tested**: All gaps verified via JS measurements (hero→content: 32px, section→section: 32px, checkbox→button: 16px). Light mode regression clean.

### Phase 22: Dark Mode Gap & Button Blending Fix (Mar 2026)
- **Root cause 1 fixed**: `--aa-primary: #161b22` = same as `--aa-card: #161b22` → buttons (Create Order, Clear Cart), hero banners, Order Summary headers ALL invisible (same bg as surrounding cards). Fixed: `--aa-primary: #4f8ef7` (accent blue), `--aa-primary-hover: #6ba4ff`, `--aa-primary-fg: #ffffff` in `.aa-dark`.
- **Root cause 2 fixed**: Section cards had no box-shadow in dark mode; the subtle contrast between page bg (`#0d1117`) and card bg (`#161b22`) was imperceptible on most displays, making adjacent cards appear to touch. Fixed by: `.aa-dark .rounded-2xl.border, .aa-dark .rounded-xl.border { box-shadow: 0 1px 3px rgba(0,0,0,0.5), 0 4px 20px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.04) !important }`.
- **Root cause 3 fixed**: Opacity-modifier Tailwind classes (`bg-slate-50/50`, `bg-slate-50/60`, `bg-white/50`, `bg-white/40`) bypass standard `.aa-dark .bg-slate-50` CSS rules (different class names). Added explicit overrides for all these in `index.css`.
- **Additional fixes**: `divide-slate-100`, `border-slate-100` now use `--aa-border` in dark mode. Added `border border-slate-200` to Cart Order Summary card (was borderless, excluded from shadow rule). Fixed FiltersTab inactive item bg, IntegrationsOverview badge.
- **Tested**: 7/7 assertions PASS (100%) — hero blue, cards elevated, buttons blue, cart page correct, light mode clean.

### Phase 21: Comprehensive Dark Mode UI Fix (Mar 2026)
- **Root cause 1 fixed**: `--primary: 210 40% 90%` (very light/white) in `.aa-dark` CSS vars was making all default-variant Shadcn buttons (Create Customer, New Product, etc.) appear as white pills on dark backgrounds. Fixed to `--primary: 217 91% 64%` (accent blue `#4f8ef7`) with `--primary-foreground: 0 0% 100%` (white text).
- **Root cause 2 fixed**: `bg-white/90` Tailwind opacity modifier class (used on SelectTrigger `<button>` elements in `UniversalFormRenderer.tsx` and `AddressFieldRenderer.tsx`) was not caught by the `.aa-dark .bg-white` CSS override. Fixed by: (a) Rewriting `pillInput`, `pillSelect`, `pillTextarea` helper functions in both files to use CSS variables (`--aa-card`, `--aa-text`, `--aa-border`, `--aa-muted`, `--aa-accent`, `--aa-surface`) instead of hardcoded `bg-white/90 text-slate-900 border-slate-200`, (b) Adding a CSS override `.aa-dark .bg-white\/90` in `index.css`.
- **Additional CSS overrides added** in `index.css`: `focus:bg-white`, `focus:border-slate-800`, `hover:border-slate-300`, `data-[state=open]:border-slate-800`, `data-[state=checked]:bg-slate-900` (checkbox/radio), signature canvas bg, sticky ProductEditor header, terms/T&C content block.
- **Tested**: 8/8 assertions PASS (100%) — buttons blue, inputs dark, sub-tabs dark-active, persistence works, light mode regression clean.

### Phase 17: UI/UX Phase 2 + Dark Mode (Mar 2026)
- **Phase 2**: Keyboard navigation fixed for Ctrl+K command palette (ArrowUp/Down/Enter/Escape). Table row hover accent bars (aa-table-row), semantic status badges (aa-badge-*), skeleton loaders (aa-skel), and empty states (aa-empty-geo) across all admin tabs (Products, Users, Enquiries, Resources, Orders, Subscriptions, Customers). Input focus glow ring. Tested: 13/13 PASS.
- **Dark Mode**: Moon/Sun toggle in sidebar, `html.aa-dark` CSS variable overrides (GitHub Dark palette), localStorage persistence, FOUC prevention inline script. Tested: 17/17 PASS.

### Phase 25: Partner Orders/Subscriptions Billing Enhancements (Mar 2026)
**8 features/fixes implemented:**
1. **`offline` → `manual`**: Removed `"offline"` from all payment method lists across `PartnerOrdersTab.tsx`, `PartnerSubscriptionsTab.tsx`, `OrdersTab.tsx`, `SubscriptionsTab.tsx`, and `backend/routes/admin/partner_billing.py`. Backend now rejects `"offline"` with 400. `backend/routes/admin/orders.py` uses `"manual"` for all auto-created orders.
2. **Mandatory Plan field**: Both `PartnerOrdersTab.tsx` and `PartnerSubscriptionsTab.tsx` forms now show `Plan *` (required asterisk), frontend validates and blocks save without a plan, and backend `create_partner_order` / `create_partner_subscription` enforce `plan_id` with a 400 error.
3. **Dynamic Tax Dropdown**: When tax module is enabled (`/api/admin/taxes/settings`), both forms load all tax entries (`/api/admin/taxes/tables`) and show a "Quick-fill from Tax Table" dropdown filtered by the selected partner's country/region. Selecting an entry auto-populates `tax_name` and `tax_rate` inputs. Manual override always available.
4. **`partially_refunded` badge fix**: Replaced `<Badge>` component with `<span>` using STATUS_COLORS map (including `partially_refunded: "bg-orange-100 text-orange-700"`) — eliminates the Tailwind specificity issue.
5. **Status read-only for refunded states**: Status `<Select>` in Partner Orders edit dialog is `disabled` when `form.status === "refunded" || form.status === "partially_refunded"`, with helper text explaining it's set by the refund process.
6. **Outstanding Amount column**: New column in Partner Orders table — shows `amount - refunded_amount` in amber for non-zero values; `—` for paid/refunded/cancelled orders.
7. **Enhanced Invoice PDF** (`invoice_service.py`): Header now shows platform address + contact info. Totals section shows Subtotal, Tax (with name+rate), **TOTAL**, Refunded (if any), and **BALANCE DUE** (red) or **PAID** (green). Pay Now hyperlink section for unpaid/pending orders with a payment URL.
8. **Invoice download for refunded orders**: Download button shown for `paid`, `partially_refunded`, and `refunded` orders. Backend endpoint updated to allow these 3 statuses.
- **Tested**: iteration_307 — 93% backend pass, 95% frontend pass. Backend plan_id and offline validations confirmed via curl tests.

### Phase 28: 7-Issue Second Round Fixes (Mar 2026)
**User reported failures from Phase 27 fixes, all addressed:**
1. **Sidebar** (final behavior): When collapsed → only section icons visible (clickable). Click → expand sidebar + navigate to section's first tab. `!sidebarCollapsed` guard added to all 7 section tab blocks + `handleExpandSection()` function added.
2. **Footer text** — `--aa-footer-text-dim` increased to `rgba(255,255,255,0.72)` (from 0.48) for better contrast on dark footer.
3. **Sticky scrollbar** — Added `.sticky-scroll-bar` CSS class with `::-webkit-scrollbar { height: 14px }`, dark grey thumb, container height 18px.
4. **Customer dropdown** — Replaced native HTML `<input list>/<datalist>` with `<SearchableSelect>` in "Create Manual Order" dialog.
5. **Default tax** — `emptyForm()` now defaults `tax_name: "No tax"`, `tax_rate: "0"` in both `PartnerOrdersTab` and `PartnerSubscriptionsTab`.
6. **Tax fallbacks** — `onValueChange` sets "No tax"/"0" (not empty) when partner has no address or no matching tax rules.
7. **Strict tax validation** — `resolveISO()` function normalizes country names to ISO codes. `orgAddress` uses `find(is_platform) || tenants[0]` to get correct org for both platform and partner admins. Toggle validation checks org address country via ISO before enabling.
- **Tested**: iteration_309 — 7/8 PASS. Final sidebar tab-hiding fix applied post-test.


**All 9 fixes implemented and verified PASS (100%):**
1. **Sidebar icons in collapsed state** — `SectionHeader` now renders section icon (not just a divider) in collapsed mode. Each accordion section uses `(sidebarCollapsed || expandedSection === 'x')` to always show tabs when collapsed.
2. **Strict tax collection validation** — `TaxSettingsPanel` in `TaxesTab.tsx`: save() now validates country is selected and matching tax rules exist before enabling. Toggle pre-populates country/state from org address.
3. **Tax auto-population fix (Issue 3)** — onValueChange handler in `PartnerOrdersTab` now checks `taxEnabled` first; clears tax fields when no match found.
4. **Customer dropdown white text fix** — Added `text-slate-900` class to customer email input in `OrdersTab.tsx` Create Manual Order modal.
5. **Tax Amount column in Partner Subscriptions** — Added `tax_rate`, `tax_name`, `tax_amount` to `PartnerSubscription` type and `Tax Amt` column header/cell in table.
6. **Default tax when disabled** — Both `PartnerOrdersTab` and `PartnerSubscriptionsTab`: `useEffect` sets `tax_name: 'No tax'` / `tax_rate: '0'` when `taxEnabled = false`. onValueChange also respects this.
7. **Country filter in Tax Rate Table** — `TaxTablePanel` now loads all entries once and filters client-side; `availableCountries` is a `useMemo` derived from entry data (shows 33 countries, not 90+).
8. **Thicker sticky scrollbar** — `StickyTableScroll.tsx` scrollbar height increased from 14 to 20px.
9. **Footer text contrast fix** — `--aa-footer-text-dim` changed from `#475569` (dark, invisible on dark bg) to `rgba(255,255,255,0.48)` in `index.css` and `WebsiteContext.tsx`.
- **Tested**: iteration_308 — 100% frontend pass (9/9).


- **Free Trial plan** — Set `is_public: True` in seed and migrated existing DB record so partners can self-sign up on the Free Trial plan
- **Invoice download for unpaid** — Download invoice button now shown for ALL statuses except `cancelled`; backend endpoint updated accordingly
- **Refund max validation** — Partner Orders & Customer Orders: refund button now only shows when there is a positive available balance (`amount - refunded_amount > 0`); `max` attribute and front-end validation prevent submitting more than the available amount
- **Tax country mapping** — Added `resolveCountryCode()` helper mapping full country names (e.g. "Canada", "United Kingdom") to ISO codes (e.g. "CA", "GB") so tax table lookups work correctly; also removed the `taxEnabled` gate on the quick-fill dropdown (it now shows whenever matching entries exist, not just when the tax module is enabled)


- Spacing on Resources and My Profile pages (minor UI inconsistency)
- Centralize Email Settings

### Phase 29: Stripe Partner Plan Upgrade Flow Fix (Mar 2026)
**Critical P0 bug fixed — partner plan upgrades now work end-to-end:**
1. **Fixed `core.utils` import bug** — `billing_service.py` was importing `now_iso, make_id` from non-existent `core.utils`. Changed to `core.helpers`. This caused a silent failure in `confirm_plan_upgrade`.
2. **Added `partner_upgrade` webhook handler** — `webhooks.py` was missing an `elif event_meta.get("type") == "partner_upgrade":` block. Stripe's `checkout.session.completed` event was received but ignored. Now correctly calls `confirm_plan_upgrade(pending, partner_id)`.
3. **Removed dead code from webhook** — Removed a duplicate second `if checkout.session.completed` block inside the `one_time_upgrade` branch (lines 381-423) that was leftover from the old `partner_upgrade` implementation.
4. **Fixed `cancel-pending-upgrade` endpoint** — Was cancelling `partner_orders` records but the new flow stores pre-payment state in `pending_plan_upgrades`. Now cancels `pending_plan_upgrades` first (with `partner_orders` as legacy fallback).
5. **Added coupon usage recording** — `confirm_plan_upgrade()` now records coupon usage when a coupon was applied to the upgrade.
6. **Fixed duplicate `_record_coupon_usage` call** — Zero-charge coupon path in `upgrade_plan_ongoing` had `_record_coupon_usage` called twice due to duplicate `if coupon_id:` blocks.

**Data flow (correct):**
- Partner clicks Upgrade → `POST /partner/upgrade-plan-ongoing` → creates `pending_plan_upgrades` doc + Stripe session (NO order created yet)
- Partner pays in Stripe → Stripe fires `checkout.session.completed` → webhook calls `confirm_plan_upgrade()` → creates `partner_orders` (paid), updates tenant license, marks pending as completed
- Frontend polls `GET /partner/upgrade-plan-status?session_id=X` → calls `confirm_plan_upgrade()` as backup if webhook was slow
- `confirm_plan_upgrade()` is atomic + idempotent (uses `find_one_and_update` so only processes once even if called by webhook AND polling simultaneously)

- **Tested**: iteration_311 — 100% (24/24 backend + 11/11 frontend)

### Phase 30: Orders Module — 17 Gap Fixes (Mar 2026)
**Critical bug fixes + validations + functional improvements:**
1. **Bug#1 fixed**: `refund_service.py` compared cents vs currency units for status — now `new_refunded >= int(total * 100)`. $50 refund on $100 order correctly sets `partially_refunded`.
2. **Bug#2 fixed**: Refund dialog "Already Refunded" showed hardcoded `$` — now uses order currency.
3. **Validations added** (frontend `handleCreateManual` + `handleEdit`): payment_date required when status=paid, discount≤subtotal, quantity≥1, subtotal≥0, total≥0, refund amount>0.
4. **Functional#10**: Refunded column added to orders table (stores in cents, displays divided by 100).
5. **Functional#11**: Refund History dialog — "Refunds" button on refunded orders, calls `GET /admin/orders/{id}/refunds`.
6. **Functional#12**: Status filter now supports multi-select (`$in` query) instead of exact match.
7. **Functional#13**: Partner filter is now server-side (resolves codes → tenant IDs via DB lookup).
8. **Functional#14**: Currency dropdown uses `useSupportedCurrencies` hook instead of 7 hardcoded values.
9. **Functional#15**: Edit order auto-recalculates `tax_amount` from `tax_rate` when subtotal changes.
10. **Functional#16**: Create manual order: tax included in total; live preview shows "Tax (X%): Y + Total: Z".
11. **Functional#17**: Edit order status change away from "paid" auto-clears `payment_date`.
12. **UX**: Subtotal/Fee/Total labels in edit dialog now show actual order currency code.
- **Tested**: iteration_312 — 100% (23/23 backend + 14/15 frontend, 1 blocked by Radix Select selector not a bug)

### Phase 31: Subscriptions Module — 19 Gap Fixes (Mar 2026)
- **Bug#1-7**: renew-now USD currency fix, billing-interval-aware date advancement (biannual+weekly added to advance_billing_date), contract_end_date null for term_months=0, billing_interval stored in model+DB, renewal_date now actually saved in update, scheduler advances customer renewal_date, cancellation email now resolves customer→user→email
- **Issues#8-13**: payment_method field added to create, SubscriptionUpdate has billing_interval+currency, email multi-filter uses $in, cancel permission changed to "edit", CSV export respects all active filters, import template uses billing_interval
- **Frontend#14-18**: amount label uses actual currency, billing_interval+currency editable in edit, Renew button guarded to active/unpaid, payment_method in create form, Interval column in table
- **Tested**: iteration_313 — 100% (30/30 backend + 5/5 frontend)

### P2 — Upcoming  
- Add radio filters for Role & Status columns in Users table
- Build new landing page
- Allow customers to browse their own submission history

### P2 — Future
- Google Drive & OneDrive Integration
- Customer Portal Enhancements (self-service cancellation, renewal dates, reorder button)
- Move `ProductConditionBuilder` to shared components directory (Refactor)

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
