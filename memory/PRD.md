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

## Prioritized Backlog

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
