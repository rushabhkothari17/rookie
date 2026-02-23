# Product Requirements Document

## Original Problem Statement
Multi-tenant SaaS platform for partner organizations (e.g. Automate Accounts). Each partner organization (tenant) must have completely isolated data, branding, and configuration. A Platform Admin can impersonate tenants via a Tenant Switcher and also impersonate individual customers via a Customer Switcher.

## Architecture
```
/app/
├── backend/                   FastAPI + MongoDB
│   ├── core/
│   │   ├── constants.py       Generic defaults (no hardcoded tenant names)
│   │   ├── security.py        JWT auth, require_admin, require_super_admin
│   │   └── tenant.py          Tenant isolation: get_tenant_filter, tenant_id_of, get_tenant_admin
│   ├── models.py
│   ├── routes/
│   │   ├── admin/             All admin CRUD routes (tenant-isolated)
│   │   │   ├── tenants.py     Tenant management + /setup-checklist + /customers endpoints
│   │   │   └── users.py       User management + single super_admin enforcement
│   │   ├── articles.py        Article CRUD + public browsing (tenant-isolated)
│   │   ├── auth.py            Login, register, register-partner + _seed_new_tenant()
│   │   ├── store.py           Public store, checkout, orders
│   │   └── website.py         Public website settings (tenant-aware)
│   └── services/
│       ├── audit_service.py   AuditService + create_audit_log + context-variable tenant injection
│       └── settings_service.py Global platform settings (key-based)
└── frontend/
    └── src/
        ├── lib/api.ts         Axios client + X-View-As-Tenant + X-View-As-Customer header injection
        ├── pages/
        │   ├── Admin.tsx      Admin panel, controlled tabs, SetupChecklistWidget, Partner Orgs hidden when viewing-as
        │   └── admin/         All admin tab components (all use /admin/* endpoints only)
        ├── components/
        │   ├── TopNav.tsx     Top navigation with TenantSwitcher + CustomerSwitcher
        │   ├── TenantSwitcher.tsx  Platform admin tenant switcher (search + top-5) + customer state exports
        │   ├── CustomerSwitcher.tsx  Platform admin customer switcher (search by email)
        │   └── admin/
        │       └── SetupChecklistWidget.tsx  5-step setup checklist for tenant admins
        └── contexts/
            ├── AuthContext.tsx
            └── WebsiteContext.tsx  Sends X-Tenant-Slug header for tenant-specific settings
```

## User Personas
- **Platform Admin**: `platform_admin` role, can see ALL data, can impersonate any tenant via Tenant Switcher, and any customer via Customer Switcher
- **Tenant Super Admin**: `partner_super_admin` role, can only see their tenant's data
- **Customer**: End-user who shops on a tenant's storefront

## Core Requirements
1. **Data Isolation**: Every DB collection must be filtered by `tenant_id` for admin endpoints
2. **Public Endpoints**: Must resolve tenant via `partner_code`/`X-Tenant-Slug` header
3. **Seed Data**: New tenants get generic sample data upon registration (no other-tenant references)
4. **Branding**: Each tenant has independent website settings, app settings, colors, logo
5. **Audit Logs**: Every admin action is tagged with `tenant_id` via context variable
6. **Single Super Admin**: Only one `partner_super_admin` and one `super_admin` allowed per tenant
7. **Setup Checklist**: Guides new tenants through 5 setup steps

## Collections with tenant_id
- users, customers, products, categories, articles, article_categories
- orders, subscriptions, promo_codes, override_codes
- bank_transactions, quote_requests, terms_and_conditions
- email_templates, article_email_templates, article_templates, article_logs
- website_settings, app_settings (flat doc), zoho_sync_logs
- audit_logs, audit_trail (via context variable injection)
- exports, references

## Tenant Isolation Implementation
- `get_tenant_filter(admin)`: Returns `{}` for platform admin (all data), `{"tenant_id": X}` for tenant admins, `{"tenant_id": view_as}` when Tenant Switcher is active
- `get_tenant_admin` dependency: Sets `_current_tenant_id` context variable for automatic audit log scoping
- `set_audit_tenant(tid)`: Sets contextvars ContextVar, auto-injected into all AuditService.log() and create_audit_log() calls
- **All admin UI tabs must use `/api/admin/*` endpoints only** — public endpoints don't respect X-View-As-Tenant

## Dual Impersonation (Platform Admin)
- **X-View-As-Tenant**: Forwarded by api.ts for all requests; handled by `get_tenant_admin` dependency
- **X-View-As-Customer**: Also forwarded by api.ts; state stored in sessionStorage (`aa_view_as_customer_id`)
- CustomerSwitcher only visible when a tenant is already selected (platform admin)
- Switching tenants clears the customer selection automatically

## What's Been Implemented

### 2026-02-XX — P0 Data Leak Fix + New Features

**P0 Fix: Cross-Tenant Data Leak**
- `ProductsTab.tsx`: Removed fallback to public `/products` endpoint (fallback was `.catch(() => api.get("/products"))` which ignored X-View-As-Tenant). Now uses only `/admin/products-all`
- All article-related sub-tabs already used `get_tenant_admin` protected endpoints — confirmed correct

**Tenant Switcher Enhancement**
- Added search input (by tenant name or code) inside dropdown
- Shows top 5 active tenants by default; shows all matching tenants when searching
- "+N more — search to find them" hint when >5 active tenants
- Closes on outside click

**Customer Switcher (Dual Impersonation)**
- New `CustomerSwitcher.tsx` component in TopNav, only visible when platform admin is viewing a specific tenant
- Fetches customers from `GET /api/admin/tenants/{tenant_id}/customers` (new endpoint)
- Search by email, company name, or full name
- Stores state in sessionStorage (`aa_view_as_customer_id`, `aa_view_as_customer_email`)
- `api.ts` forwards `X-View-As-Customer` header alongside `X-View-As-Tenant`
- Clear customer selection via ✕ button or switching tenant

**Setup Checklist Widget**
- New `SetupChecklistWidget.tsx` component shown above tabs in Admin dashboard
- 5 steps: Brand Customized, First Product, Payment Configured, First Customer, First Article
- Clicking an incomplete step navigates to the relevant admin tab
- Dismissible (stores `aa_checklist_dismissed` in sessionStorage)
- Auto-hides when all steps complete
- Only visible to tenant admins or platform admin viewing-as a specific tenant
- Backend: `GET /api/admin/setup-checklist` returns `{checklist:{...}, completed, total}`

**Single Super Admin Enforcement**
- `POST /api/admin/users`: Rejects `partner_super_admin` or `super_admin` if one already exists for the tenant
- `PUT /api/admin/users/{id}`: Rejects update to `super_admin` role if another user already holds it

**Prior Session (2026-02-23) — Critical Bug Fixes + P2 Tasks**
- Audit Trail 100% Coverage via contextvars
- Payment Fallback "Request a Quote"
- Partner Orgs Tab Reactive Fix
- Tenant Seeding with generic data
- Fixed tenant isolation in all routes (override_codes, misc, subscriptions, terms, settings, store, articles, orders, catalog, quote_requests, bank_transactions, website)

## Test Credentials
- Platform Admin: `admin@automateaccounts.local` / `ChangeMe123!` / code: `automate-accounts`
- Tenant B Admin: `adminb@tenantb.local` / `ChangeMe123!` / code: `tenant-b-test`
- Test New Corp: `admin@test-new-corp.local` / `ChangeMe123!` / code: `test-new-corp-seed`

## Key API Endpoints
- `POST /api/auth/partner-login` → `{ token, role, tenant_id }`
- `POST /api/auth/register-partner` → Create new tenant + seed data
- `GET /api/website-settings?partner_code=X` → Tenant-specific settings
- `GET /api/products?partner_code=X` → Public store for tenant
- `GET /api/admin/audit-logs` → Tenant-scoped audit trail
- `GET /api/admin/setup-checklist` → Checklist status (5 items)
- `GET /api/admin/tenants/{id}/customers` → Customer list for customer switcher
- All `/api/admin/*` → Tenant-scoped via `get_tenant_admin` + `X-View-As-Tenant` header

## P0 Backlog (Resolved)
- [x] Data leaks across all modules
- [x] Incorrect "Automate Accounts" branding for new tenants
- [x] Partner Orgs tab visible to wrong users
- [x] P0 regression: ProductsTab using public /products fallback
- [x] Dual Impersonation (Customer Switcher)
- [x] Tenant Switcher search + top-5 limit
- [x] Setup Checklist Widget
- [x] Single Super Admin enforcement

## P1 Backlog
- [x] New tenant seed data
- [x] Audit logs not visible to tenant admins

## P2 / Future
- [ ] X-View-As-Customer support in portal/store routes (simulate full customer view)
- [ ] /terms endpoint in ProductsTab uses public endpoint (minor - terms typically shared)
- [ ] Admin Dashboard with business metrics widget
- [ ] Customer Switcher: backend support for /articles/public with X-View-As-Customer header
- [ ] Export to Github (use Emergent "Save to Github" feature)
