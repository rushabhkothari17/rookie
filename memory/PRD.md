# PRD — Admin SaaS Platform (Automate Accounts)

## Original Problem Statement
Multi-tenant SaaS admin platform for partner organizations managing customer subscriptions, products, and documents. Partners each have their own branded storefront with customers.

## Architecture
- **Backend**: FastAPI + MongoDB
- **Frontend**: React + TypeScript + ShadCN UI
- **Auth**: JWT-based with multi-role: platform_admin, partner_super_admin, partner_admin, customer
- **Deployment**: Kubernetes (preview URL: https://admin-form-sync.preview.emergentagent.com)

## User Personas
1. **Platform Admin** (`admin@automateaccounts.local`) — manages all partner tenants
2. **Partner Admin** (`admin@ligerinc.local`) — manages their own org, customers, products
3. **Customer** — accesses the partner's e-shop/portal

## Core Requirements (Implemented)

### Admin Panel Sidebar Structure (CURRENT as of Feb 2026)
```
PLATFORM: Partner Orgs
PEOPLE: Users, Roles, Customers
COMMERCE: Products, Subscriptions, Orders, Enquiries, Taxes
CONTENT: Resources, Documents, Email Templates, References
SETTINGS:
  - Organization Info      (Store Name, Logo, Brand Colors, Base Currency, Address)
  - Auth & Pages           (tile-based, includes Footer & Nav, Hero Banners, Signup CTA)
  - Forms                  (Enquiry Form builder)
  - System Config          (Operations + Feature Flags)
  - Custom Domains
INTEGRATIONS: Connect Services (incl. Google Drive + OneDrive COMING SOON), API, Webhooks, Logs
```

### What's Implemented

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

#### Admin Panel Restructure + Dynamic Forms (Feb 2026)
- "Website Content" tab DELETED
- "Organization Info" (top-level) — Store Name, Address, Logo, Brand Colors, Base Currency
- "Auth & Pages" (top-level, tile-grid) — Login, Signup, Verify Email, Portal, Profile, Admin Panel, 404, Documents Page, Hero Banners, Checkout Builder, Checkout Success, Checkout Messages, Footer & Nav
- Signup page: bullets 1/2/3 + CTA field editable from Auth & Pages > Sign Up tile
- "Forms" (top-level) — Enquiry Form schema builder
- "System Config" (top-level) — Operations + Feature Flags

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
