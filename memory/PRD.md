# PRD — Admin SaaS Platform (Automate Accounts)

## Original Problem Statement
Multi-tenant SaaS admin platform for partner organizations managing customer subscriptions, products, and documents. Partners each have their own branded storefront with customers.

## Architecture
- **Backend**: FastAPI + MongoDB
- **Frontend**: React + TypeScript + ShadCN UI
- **Auth**: JWT-based with multi-role: platform_admin, partner_super_admin, partner_admin, customer
- **Deployment**: Kubernetes (preview URL: https://subscription-hub-113.preview.emergentagent.com)

## User Personas
1. **Platform Admin** (`admin@automateaccounts.local`) — manages all partner tenants
2. **Partner Admin** (`admin@ligerinc.local`) — manages their own org, customers, products
3. **Customer** — accesses the partner's e-shop/portal

## Core Requirements (Implemented)

### Admin Panel Sidebar Structure (CURRENT as of Feb 2026)
```
PLATFORM (Platform Admin only):
  - Partner Orgs        (manage tenants; License, Add Admin, Notes, Audit Logs, Address, plan filter)
  - Plans               (CRUD for license plans; auto-propagation to tenants)
  - Partner Subscriptions  (B2B recurring billing; Stripe hosted checkout; stats: MRR/ARR)
  - Partner Orders         (B2B one-time fees; manual + Stripe checkout; revenue stats)
PEOPLE: Users, Roles, Customers
ACCOUNT: Usage & Limits (Partner Admins only - shows usage vs plan limits)
COMMERCE: Products, Subscriptions, Orders, Enquiries
CONTENT: Resources, Documents
SETTINGS:
  - Organization Info      (Store Name → Base Currency → Address → Logo → Brand Colors)
  - Taxes                  (moved here from Commerce)
  - Auth & Pages
  - Forms                  (New full Forms Management module - create/edit/delete custom forms)
  - Email Templates        (moved here from Content)
  - References             (moved here from Content)
  - Custom Domains
INTEGRATIONS: Connect Services (with color-coded missing integration alerts), API, Webhooks, Logs
NOTE: System Config tab DELETED
```

### What's Implemented

## What Was Implemented (Feb 2026 — Product Management Overhaul)

### Partner Billing System — Backend & Frontend (Feb 2026)
- **Backend** (`backend/routes/admin/partner_billing.py`): Full CRUD for `partner_orders` + `partner_subscriptions` collections; stats endpoints (MRR, ARR, revenue by currency); Stripe hosted checkout for card subscriptions & one-time orders; audit trail on all actions; Stripe webhook handlers in `webhooks.py`.
- **Frontend** (`PartnerOrdersTab.tsx`, `PartnerSubscriptionsTab.tsx`): Stats dashboards, filters (partner/plan/status/interval), create/edit modals, cancellation, Stripe checkout link generation/copy, audit log dialog.
- **Bug fixed**: Audit log sort field `timestamp` → `created_at` in `partner_billing.py` (iter148).

### Plan Management System (Feb 2026)
- `backend/routes/admin/plans.py`: CRUD plans, auto-propagation to tenants, tenant counts per plan, audit logging.
- `frontend/src/pages/admin/PlansTab.tsx`: Full plan management UI.
- `TenantsTab.tsx`: "Filter by Plan" dropdown added to Partner Orgs tab.


- **New backend endpoint**: `GET /api/admin/audit-logs/stats` — returns total/errors/today/by_actor_type/top_actions/top_entity_types for the selected period
- **Rebuilt LogsTab.tsx** with full dashboard: 4 stats cards, Top Actions clickable chips, quick date range buttons (Today/7d/30d/90d/All), default last-30-days filter, expanded entity types, per-page selector (25/50/100), detail dialog with full metadata
- All 24/24 tests pass (backend + frontend)

### 100% Audit Trail Coverage (Feb 2026)
- **taxes.py** — All 10 write endpoints now log to `audit_logs` + `audit_trail`
- **documents.py** — Upload, update, delete document endpoints now log to `audit_logs` + `audit_trail`
- **admin/integration_requests.py** — Submit, status update, note add now log to `audit_logs` + `audit_trail`
- **uploads.py** — File upload endpoint now logs to `audit_logs` + `audit_trail`
- **zoho_service.py** — `auto_sync_to_zoho_crm` and `auto_sync_to_zoho_books` now write sync success/failure events to `audit_trail` with `actor="system"` and entity linking

### Integration Requests Feature (Feb 28, 2026)
- Backend: `backend/routes/admin/integration_requests.py` — POST submit (partner only), GET list (platform admin only), PUT status update, POST note add
- Frontend partner view: "Request an integration" collapsible form at bottom of Connect Services (IntegrationsOverview.tsx) — pre-fills email/phone, country code dropdown, integration name + description
- Frontend platform admin view: `IntegrationRequestsTab.tsx` — full management table with status dropdown, inline notes panel, partner info columns
- Status options: Pending, Not Started, Working, Future, Rejected, Completed

### Pricing & Store Card Verifications (Feb 28, 2026)
- Boolean × multiplier pricing: 1000 × 1.5 = 1500 confirmed end-to-end via pricing/calc API
- Clear store card & save: card_tag/card_description/card_bullets all correctly clear to null/[] and persist through reload


1. **Country visibility rules fixed** — backend `store.py` now loads address from separate `addresses` collection and attaches it before evaluating visibility conditions (both `get_products` and `get_product` endpoints)
2. **Preview store card** — "Preview card" button added to product editor header; opens modal with live `OfferingCard` preview, content chips, and tip for empty store card


All 22 user-reported bugs and enhancements fixed and verified 100% by testing agent:
1. **Admin tab persistence** — URL `?tab=catalog` param + localStorage; Back button from product editor goes to catalog tab
2. **Categories dropdown** — Fixed empty-string placeholder issue (`value={form.category || undefined}`)
3. **Store card bullets** — Fixed `items.length` → `bullets.length` compile error
4. **Clear store card & save** — Backend already correctly handles null/empty; confirmed working
5. **Country dropdown in visibility** — Select populated from Taxes module countries when condition field = "country"
6. **Default checkout type** — "Internal Checkout" pre-selected on new products
7. **Price rounding display** — `price_mode` field name fixed in OfferingCard.tsx; multiplier-mode skips starting price calc
8. **No Rounding save** — Confirmed correct (null ↔ "" conversion)
9. **Show price breakdown** — Toggle works, default = No
10. **Intake question save** — "Save questions" button added in intake section (triggers full product save)
11. **Intake question reordering** — Stable React keys (`key={q.key || 'q_'+i}`) prevent state mixing
12. **Required/Affects price conditional** — Only shown when question is Enabled
13. **Auto-required on affects_price** — Enabling "Affects price" automatically sets Required = true
14. **Tooltip moved below helper text** — Moved from Advanced Settings to main question body
15. **Price floor removed** — Only "Price ceiling cap" shown in intake builder
16. **Boolean affects_price duplication** — Removed standalone checkbox, kept MiniToggle in flags row
17. **Boolean price mode (multiplier)** — Add ± and Multiply × radio options for Yes/No questions
18. **Dropdown no default** — Fixed auto-selection of first option (`defaults[q.key] = ""`)
19. **Multiplier not affecting base price** — OfferingCard and backend pricing skip multiply-mode questions for starting price calc
20. **TypeScript types** — Added `card_description`, `card_tag`, `card_bullets`, `price_rounding`, `show_price_breakdown` to Product type

#### Dynamic Enquiry Forms Module (Feb 2026)
- `Form` and `FormSubmission` models in `backend/models/form.py`
- CRUD API at `backend/routes/forms.py`
- `FormsManagementTab.tsx`, `EnquiriesTab.tsx` with PDF download
- Forms linked to products via `enquiry_form_id`

#### Dashboard & UI Fixes (Feb 2026)
- Fixed email provider detection bug (tenant scoping in oauth.py)
- Color-coded integration alerts on dashboard
- Admin sidebar rearranged (Taxes, Email Templates moved to Settings)
- System Config tab removed
- Base currency moved under Store Name


- Created shared `useCountries()` and `useProvinces()` hooks at `frontend/src/hooks/useCountries.ts`
- All country dropdowns across the entire app now pull from `/api/utils/countries` (taxes module): `SettingsTab.tsx`, `websiteTabShared.tsx` (OrgAddressSection), `TenantsTab.tsx`, `CustomersTab.tsx` (filter + edit form), `Signup.tsx` (partner signup + customer signup), `Profile.tsx`
- Province/state dropdowns now work for ANY country (removed Canada/USA-only restriction) across all files
- Removed hardcoded default "Canada" from all initial states
- Customer filter dropdown in `CustomersTab.tsx` now uses dynamic country list
- `TaxesTab.tsx` COUNTRIES expanded from 16 to 80+ world countries for adding new tax rates
- `utils.py` `_ISO_TO_NAME` expanded from 12 to 80+ countries for proper name resolution
- `AddressFieldRenderer.tsx` fallback only used when API fails (not a source of truth)

#### Product 0b: Address Field Type in FormSchemaBuilder (Feb 2026)
- New `address` field type in `FormSchemaBuilder` — works in ALL form builders (signup, enquiry/scope, custom)
- Admin can individually toggle/require each sub-field: Line 1, Line 2, City, State/Province, Postal, Country
- `address_config` property on `FormField` stores per-sub-field enabled/required settings
- New `AddressFieldRenderer` component fetches countries from taxes module (`/api/utils/countries`) and provinces from `/api/utils/provinces` when country selected
- `DynamicField` in `ProductDetail.tsx` now handles `type === "address"` for enquiry/scope forms
- `Signup.tsx` and `CustomersTab.tsx` address blocks now use `address_config` for sub-field show/hide and required
- Backend `_SIGNUP_FORM_SCHEMA` updated to type `"address"` with `_DEFAULT_ADDRESS_CONFIG`; migration upgrades existing schemas
- `AdminCreateCustomerRequest` model made all address fields Optional to support disabled sub-fields
- Files: `FormSchemaBuilder.tsx`, `AddressFieldRenderer.tsx`, `CustomersTab.tsx`, `Signup.tsx`, `ProductDetail.tsx`, `backend/models.py`, `backend/routes/admin/website.py`

#### Product 0: Schema-Driven "Create Customer" Dialog (Feb 2026)
- Backend `_SIGNUP_FORM_SCHEMA` fixed: now has `full_name`, `company_name`, `job_title`, `phone`, `address` (no standalone `country`, no `email`, no `password`)
- Migration function `_migrate_signup_schema()` runs on every GET to convert old schemas (with locked `country`) to new format (with `address`)
- Admin Create Customer dialog is fully schema-driven: address block visibility/required status controlled by `address` field in schema
- FormSchemaBuilder in Auth & Pages > Sign Up now shows exactly 5 correct fields
- Both public (`/api/website-settings`) and admin (`/api/admin/website-settings`) endpoints apply migration
- Files: `backend/routes/admin/website.py`, `frontend/src/pages/admin/CustomersTab.tsx`

#### Product 1: Mandatory Partner Address (Feb 2026)
- Partner signup requires: Line 1, City, Postal, State/Province, Country
- OrgAddressSection in Organization Info tab, appears directly below Store Name
- Country and State/Province are dropdowns (from /utils/provinces API)
- Only partner admins see address section (platform admins see null)
- Backend: PUT /api/admin/tenants/{id}/address, GET /api/admin/tenants/my

#### Product 2: Zoho WorkDrive Integration (Feb 2026)
- OAuth flow in Connect Services (Cloud Storage category)
- Customer folders auto-created in WorkDrive on customer creation/rename
- Backfill endpoint: POST /api/documents/sync-folders
- Admin Documents tab: file management table with notes, edit, delete
- Customer-facing /documents page: upload/download (max 5MB), no delete
- WorkDrive-enabled gate: Documents nav tab only shows if partner has WorkDrive connected

#### Dynamic Enquiry Forms Module (Feb 2026)
- New `FormsManagementTab.tsx` — full CRUD for custom enquiry forms (create, edit, delete)
- Default Form tile (from `scope_form_schema`) shows field count + edit opens SlideOver with `FormSchemaBuilder`
- Custom forms stored in `tenant_forms` MongoDB collection (per-tenant)
- Backend routes: `GET/POST/PUT/DELETE /api/admin/forms` at `/app/backend/routes/admin/forms.py`
- Products with "Enquiry" pricing type now have a form selector dropdown (Default Form + custom forms)
- `enquiry_form_id` field on products; store API resolves `resolved_form_schema` from `tenant_forms`
- ProductDetail.tsx uses `product.resolved_form_schema` over `ws.scope_form_schema` when set
- **PDF Download**: `GET /api/admin/enquiries/{id}/pdf` using ReportLab (`enquiry_pdf_service.py`)
- Enquiry detail dialog now has "Download PDF" button (token-authenticated fetch)
- Audit logging for all form create/update/delete events

#### Dashboard Integration Alerts (Feb 2026)
- Fixed multi-tenant bug: `active_email_provider` in `app_settings` now uses tenant-scoped key (`active_email_provider_{tid}`)
- Backward compat: falls back to legacy global key if tenant-scoped key not found
- Color-coded alert banners added to Connect Services page:
  - Email (Red) — no active provider
  - Payments (Red) — no validated payment provider
  - Cloud Storage (Orange) — no validated cloud storage
  - Accounting System (Amber) — no validated accounting integration
  - CRM (Amber) — no validated CRM

#### Admin Panel UI Rearrangements (Feb 2026)
- **Sidebar**: Taxes moved from Commerce → Settings (below Organization Info)
- **Sidebar**: Email Templates + References moved from Content → Settings (below Forms)
- **Sidebar**: System Config tab DELETED from everywhere
- **Org Info**: Base Currency widget moved to directly below Store Name (above Address)

#### WebsiteTab Refactor (Feb 2026)
- WebsiteTab.tsx refactored from 1330 lines to ~150 lines
- Child components:
  - `websiteTabShared.tsx` — shared types, interfaces, atom components (Field, ColorInput, SectionDivider, AuthTile, FormTile, SettingRow, BaseCurrencyWidget, OrgAddressSection)
  - `WebsiteOrgSection.tsx` — Org Info section (logo, colors, currency, address)
  - `WebsiteAuthSection.tsx` — Auth & Pages tile grid + all slide-over content
  - `WebsiteFormsSection.tsx` — Forms tile + form slide-over
  - `WebsiteSysSection.tsx` — System Config section

#### Dynamic Roles UI (Feb 2026)
- New "Roles" tab in Admin > People (visible to super_admin / platform_admin)
- Backend CRUD: GET/POST/PUT/DELETE /api/admin/roles
- 6 built-in preset roles (Super Admin, Manager, Support, Viewer, Accountant, Content Editor)
- Custom roles stored in `admin_roles` MongoDB collection
- UI: card grid with Built-in badge (read-only view) vs custom (edit/delete)
- Create/Edit dialog: name, description, access level select, module checkboxes

#### Platform Admin Features (Feb 2026)
- Platform admin can edit any partner's organization address from Partner Orgs view
- TenantsTab.tsx has "Edit Address" button that opens a modal

#### Authentication & User Flow (Feb 2026)
- Forced password change for new non-customer users on first login
- `must_change_password` flag on users collection
- `ForcePasswordChangeModal` blocks app until password updated
- PUT /api/auth/change-password endpoint
- "Back" buttons on login, signup, partner signup pages
- Customer email field read-only in My Profile
- Password criteria tooltip on signup screen
- Dynamic Country/State dropdowns from /api/utils/countries

#### Forms & Validation (Feb 2026)
- SignUp form: schema-driven from `signup_form_schema` in website_settings
- Required field asterisks shown based on schema
- Address block configurable as single unit (enable/disable, required)
- My Profile respects signup form's mandatory field settings
- Phone/email basic validation

## Key API Endpoints

### Roles
- `GET /api/admin/roles` — returns all roles (preset + custom from DB) + modules list
- `POST /api/admin/roles` — create custom role
- `PUT /api/admin/roles/{role_id}` — update custom role
- `DELETE /api/admin/roles/{role_id}` — delete custom role

### Partner Address
- `GET /api/admin/tenants/my` — get own tenant (includes address)
- `PUT /api/admin/tenants/{id}/address` — update address (used by platform admin)

### Auth
- `PUT /api/auth/change-password` — for forced password change flow
- `GET /api/utils/countries` — countries/states for dropdowns

### WorkDrive & Documents
- `GET /api/oauth/workdrive/authorize`, `GET /api/oauth/workdrive/callback`
- `GET /api/documents`, `GET /api/documents/customer`
- `POST /api/documents/upload-url`, `DELETE /api/documents/{file_id}`
- `POST /api/documents/sync-folders` — backfill customer folders

### Website Settings
- `GET /api/admin/website-settings` — includes all dynamic content fields
- `PUT /api/admin/website-settings` — save
- `GET /api/website-settings` — public

## Key DB Schema
- `tenants`: `address: {line1, line2, city, region, postal, country}`
- `oauth_connections`: WorkDrive tokens + `settings.parent_folder_url`
- `admin_roles`: custom roles (`id, name, description, access_level, modules[], is_preset:false, tenant_id`)
- `users`: `must_change_password: bool`
- `website_settings`: all configurable text including `signup_bullet_1/2/3`, `signup_cta`, `nav_documents_label`, `documents_page_*`, `signup_form_schema`

## Prioritized Backlog

### P1 (High — next sprint)
- Google Drive & OneDrive full integration (currently "Coming Soon" tiles in Connect Services)
- Centralize all email settings into a single tab

### P2 (Medium)
- Customer Portal: self-service subscription cancellation
- Customer Portal: display renewal dates
- Customer Portal: "Reorder" button

### P3 (Backlog / Future)
- Security audit / penetration testing
- Comprehensive unit test coverage
- Mobile app version of customer portal

## Test Credentials
- **Platform Admin**: `admin@automateaccounts.local` / `ChangeMe123!` (tenant: `automate-accounts`)
- **Partner Admin (Bright Accounting)**: `admin@bright-accounting.local` (tenant: `bright-accounting`)
- **Forced Password Change User**: `testuser@bright-accounting.local` / `ChangeMe123!` (tenant: `bright-accounting`)
- **Test Partner (iter133)**: `TEST_valid_iter133@test.local` / `ChangeMe123!` (code: `test-org-iter133-valid`)

## 3rd Party Integrations
- GoCardless (Payments)
- Stripe (Payments)
- Zoho Mail (Email)
- Zoho WorkDrive (Cloud Storage)
- exchangerate-api.com (FX rates)
- jspdf & html2canvas (Frontend PDF Generation)
- Google Drive (COMING SOON)
- OneDrive (COMING SOON)

## Plans Management (Feb 2026)
### Backend:
- `backend/routes/admin/plans.py` — Full CRUD: GET/POST /admin/plans, GET/PUT/DELETE/PATCH /{plan_id}, GET /{plan_id}/logs
- Auto-propagation: `PUT /admin/plans/{plan_id}` updates all tenants with matching plan_id
- Delete blocked if tenants assigned; PATCH /status to toggle active/inactive
- Audit logged on all create/update/delete/activate/deactivate
### Frontend:
- `frontend/src/pages/admin/PlansTab.tsx` — Table with create/edit/logs/toggle/delete; expandable row shows all limits + read-only plan ID
- `frontend/src/pages/admin/TenantLicenseModal.tsx` — Plan field now a Select dropdown (active plans only); selecting plan auto-fills limit fields

## Partner Licensing System (Feb 2026)
### Backend:
- `backend/services/license_service.py` — Core service: check_limit, increment_monthly, get_full_usage_snapshot, lazy EST-based monthly reset
- `backend/routes/admin/tenants.py` — New endpoints: GET/PUT /{tid}/license, POST /{tid}/usage/reset, GET/POST/DELETE /{tid}/notes, GET /usage (partner self-view)
### Frontend:
- `frontend/src/pages/admin/TenantLicenseModal.tsx` — License editor + live usage progress bars per resource
- `frontend/src/pages/admin/TenantNotesModal.tsx` — Internal notes CRUD
- `frontend/src/pages/admin/UsageDashboard.tsx` — Partner admin: view own usage vs limits
- `frontend/src/layout/LimitBanner.tsx` — Top warning banner when approaching/hitting limits
- `frontend/src/pages/admin/TenantsTab.tsx` — Updated: License, Add Admin, + MoreActions (Address, Notes, Logs) per tenant row
### Enforcement (13 endpoints):
- users.py, customers.py (monthly), checkout.py (orders+subs monthly), resources.py, resource_templates.py, resource_categories.py, catalog.py, forms.py, terms.py, references.py

## Files of Reference
- `backend/routes/admin/permissions.py` — roles CRUD endpoints + permission helpers
- `backend/routes/admin/tenants.py` — address endpoints
- `backend/models/models.py` — all Pydantic models (incl. WebsiteSettingsUpdate, RoleCreate/Update)
- `backend/routes/admin/website.py` — DEFAULT_WEBSITE_SETTINGS
- `frontend/src/pages/Admin.tsx` — admin sidebar + tabs (incl. Roles tab)
- `frontend/src/pages/admin/RolesTab.tsx` — Roles management UI
- `frontend/src/pages/admin/WebsiteTab.tsx` — thin container (refactored)
- `frontend/src/pages/admin/websiteTabShared.tsx` — shared types + atoms
- `frontend/src/pages/admin/WebsiteOrgSection.tsx` — Org Info section
- `frontend/src/pages/admin/WebsiteAuthSection.tsx` — Auth & Pages section
- `frontend/src/pages/admin/WebsiteFormsSection.tsx` — Forms section
- `frontend/src/pages/admin/WebsiteSysSection.tsx` — System Config section
- `frontend/src/pages/auth/Login.tsx` — force password change modal
- `frontend/src/pages/auth/Signup.tsx` — schema-driven, dynamic content
- `frontend/src/pages/customer/Profile.tsx` — read-only email, dynamic required fields
- `frontend/src/pages/platform/tabs/TenantsTab.tsx` — platform admin partner address editing
- `frontend/src/contexts/WebsiteContext.tsx` — website settings context
- `frontend/src/components/TopNav.tsx` — customer nav with Documents link
