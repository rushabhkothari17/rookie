# Product Requirements Document

## Original Problem Statement
Multi-tenant SaaS platform for partner organizations (e.g. Automate Accounts). Each partner organization (tenant) must have completely isolated data, branding, and configuration. A Platform Admin can impersonate tenants via a Tenant Switcher.

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
│   │   ├── articles.py        Article CRUD + public browsing (tenant-isolated)
│   │   ├── auth.py            Login, register, register-partner + _seed_new_tenant()
│   │   ├── store.py           Public store, checkout, orders
│   │   └── website.py         Public website settings (tenant-aware)
│   └── services/
│       ├── audit_service.py   AuditService + create_audit_log + context-variable tenant injection
│       └── settings_service.py Global platform settings (key-based)
└── frontend/
    └── src/
        ├── api.ts             Axios client + X-View-As-Tenant header injection
        ├── pages/
        │   ├── Admin.tsx      Admin panel, Partner Orgs tab hidden when viewing-as-tenant
        │   └── admin/         All admin tab components
        ├── components/
        │   ├── TopNav.tsx     Top navigation with TenantSwitcher
        │   └── TenantSwitcher.tsx  Platform admin tenant switcher + subscribeToTenantSwitch()
        └── contexts/
            ├── AuthContext.tsx
            └── WebsiteContext.tsx  Sends X-Tenant-Slug header for tenant-specific settings
```

## User Personas
- **Platform Admin**: `platform_admin` role, can see ALL data, can impersonate any tenant via Tenant Switcher
- **Tenant Super Admin**: `partner_super_admin` role, can only see their tenant's data
- **Customer**: End-user who shops on a tenant's storefront

## Core Requirements
1. **Data Isolation**: Every DB collection must be filtered by `tenant_id` for admin endpoints
2. **Public Endpoints**: Must resolve tenant via `partner_code`/`X-Tenant-Slug` header
3. **Seed Data**: New tenants get generic sample data upon registration (no other-tenant references)
4. **Branding**: Each tenant has independent website settings, app settings, colors, logo
5. **Audit Logs**: Every admin action is tagged with `tenant_id` via context variable

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

## What's Been Implemented
### 2026-02-23 — Critical Bug Fixes + P2 Tasks

**Bug Fix: Article Tenant Isolation via X-View-As-Tenant**
- `GET /api/articles/{id}` now accepts `X-View-As-Tenant` header
- Platform admin + view-as-tenant can access that tenant's articles
- No header (raw platform admin) correctly gets 404 for other tenants' articles
- Added admin role bypass for article visibility restrictions

**Audit Trail 100% Coverage**
- `get_current_user` (security.py) now calls `set_audit_tenant(user.tenant_id)` — covers ALL customer-facing routes
- `get_tenant_admin` (tenant.py) also sets audit context — covers ALL admin routes
- Both `AuditService.log()` and `create_audit_log()` auto-inherit `tenant_id` from request context
- Zero call sites changed — contextvars handles it transparently

**P2: Payment Fallback (Request a Quote)**
- When `!stripe_enabled && !gocardless_enabled`, Cart shows "Request a Quote" mailto button
- ProductDetail `ctaConfig` also returns "Request a Quote" for fixed-price products with no payment methods
- New tenants see quote flow by default until they configure Stripe or GoCardless

**P2: React Hydration Warning Fix**
- `TenantSwitcher.tsx` module-level `sessionStorage` reads wrapped in `try/catch` + `typeof window` check
- Warning was from Emergent VE tooling (not code), not actionable

**Partner Orgs Tab Reactive Fix**
- Uses `subscribeToTenantSwitch()` for reactive state — hides immediately when admin switches tenants, shows again on revert
- Fixed tenant isolation in ALL routes:
  - `override_codes.py`: Added tenant filter to list, create, update, deactivate
  - `misc.py`: Added tenant filter to sync-logs, customer notes, partner-map
  - `subscriptions.py`: Fixed manual subscription creation, renewal order tenant_id
  - `terms.py`: Fixed public terms endpoints to use user's tenant
  - `settings.py`: Fixed /settings/public and logo upload to use tenant context
  - `store.py`: Fixed promo code validation, orders/preview, removed hardcoded "automate-accounts"
  - `articles.py`: Fixed branding lookups; added admin bypass for visibility restriction
  - `orders.py`: Fixed auto_charge_order tenant filter; entity logs ownership check
  - `subscriptions.py`: Entity logs ownership check
  - `catalog.py`: Category delete and product/category logs ownership checks
  - `quote_requests.py`: Admin update with tenant filter
  - `bank_transactions.py`: Logs endpoint with tenant filter
  - `website.py`: Public endpoint reads payment flags from tenant's app_settings (not global)
- **Audit Log Context Injection**: Added `contextvars.ContextVar` pattern so all AuditService.log() and create_audit_log() calls automatically inherit tenant_id from the request context, without changing 109 individual call sites
- **New Tenant Seeding**: `_seed_new_tenant()` in auth.py provisions new tenants with: generic website_settings, app_settings, 1 category, 1 product, 1 article, 1 ToS, 1 email template
- **Fix existing bad data**: Updated all non-default tenants' store_name to their actual name (removing incorrectly cloned "Automate Accounts" branding)
- **Partner Orgs tab**: Hidden from platform admin when they are "viewing as" a tenant; hidden from non-platform_admin users
- **TenantSwitcher**: Exported `subscribeToTenantSwitch()` for reactive state tracking

## Test Credentials
- Platform Admin: `admin@automateaccounts.local` / `ChangeMe123!` / code: `automate-accounts`
- Tenant B Admin: `adminb@tenantb.local` / `ChangeMe123!` / code: `tenant-b-test`
- Test New Corp: `admin@test-new-corp.local` / `ChangeMe123!` / code: `test-new-corp-seed`

## P0 Backlog (Resolved)
- [x] Data leaks across all modules
- [x] Incorrect "Automate Accounts" branding for new tenants
- [x] Partner Orgs tab visible to wrong users

## P1 Backlog (Resolved)
- [x] New tenant seed data
- [x] Audit logs not visible to tenant admins

## P2 Remaining
- [ ] Payment Integration Defaults: Remove hardcoded payment examples, add "Request a Quote" fallback
- [ ] React Hydration Warning
- [ ] Admin Dashboard with business metrics

## Key API Endpoints
- `POST /api/auth/partner-login` → `{ token, role, tenant_id }`
- `POST /api/auth/register-partner` → Create new tenant + seed data
- `GET /api/website-settings?partner_code=X` → Tenant-specific settings
- `GET /api/products?partner_code=X` → Public store for tenant
- `GET /api/admin/audit-logs` → Tenant-scoped audit trail
- All `/api/admin/*` → Tenant-scoped via `get_tenant_admin` + `X-View-As-Tenant` header
