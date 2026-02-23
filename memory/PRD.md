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
│   │   │   ├── tenants.py     Tenant mgmt + /setup-checklist + /customers endpoints
│   │   │   ├── users.py       User mgmt + single super_admin enforcement
│   │   │   └── subscriptions.py  /admin/subscriptions/{id}/renew-now (admin prefix)
│   │   ├── articles.py        Articles CRUD + /articles/public (X-View-As-Tenant aware)
│   │   ├── auth.py            Login, register, register-partner + _seed_new_tenant()
│   │   ├── store.py           Public store — _tid() respects X-View-As-Tenant for platform_admin
│   │   └── website.py         Public website settings (tenant-aware)
│   └── services/
│       ├── audit_service.py   AuditService + create_audit_log + context-variable tenant injection
│       └── settings_service.py Global platform settings (key-based)
└── frontend/
    └── src/
        ├── lib/api.ts         Axios client + X-View-As-Tenant + X-View-As-Customer header injection
        ├── pages/
        │   ├── Admin.tsx      Admin panel, controlled tabs, SetupChecklistWidget, websiteSection state
        │   └── admin/
        │       ├── ProductsTab.tsx      Uses /admin/products-all + /admin/terms (no public fallbacks)
        │       ├── SubscriptionsTab.tsx Uses /admin/subscriptions/{id}/renew-now (admin prefix)
        │       └── WebsiteTab.tsx       Accepts defaultSection prop for checklist navigation
        ├── components/
        │   ├── TopNav.tsx     Top nav with TenantSwitcher + CustomerSwitcher
        │   ├── TenantSwitcher.tsx  Platform admin tenant switcher (search + top-5) + customer state
        │   ├── CustomerSwitcher.tsx  Platform admin customer switcher (search by email)
        │   └── admin/
        │       └── SetupChecklistWidget.tsx  5-step checklist w/ section-aware navigation
        └── contexts/
            ├── AuthContext.tsx
            └── WebsiteContext.tsx  Sends X-Tenant-Slug header for tenant-specific settings
```

## Tenant Isolation Rules
### Admin endpoints (/api/admin/*)
- ALL use `get_tenant_admin` dependency which reads `X-View-As-Tenant` header
- Platform admins get data for ALL tenants unless `X-View-As-Tenant` is set
- Returns only that tenant's data when header is present

### Public endpoints (/api/products, /api/articles/public, /api/terms, etc.)
- Use `_tid()` helper (store.py) or direct tenant check (articles.py)
- **MUST respect X-View-As-Tenant for platform_admin users**
- `_tid(user, partner_code, x_view_as_tenant)` → prefers x_view_as_tenant over user.tenant_id for platform_admin
- This ensures store/articles/terms pages show correct data when platform admin impersonates a tenant

### Frontend enforcement
- ALL admin tab components must use `/admin/*` endpoints only
- Public store pages must NOT use direct DB queries - always go through API
- `api.ts` automatically injects `X-View-As-Tenant` and `X-View-As-Customer` headers

## What's Been Implemented

### 2026-02-XX — Comprehensive Tenant Isolation Fix + New Features

**Critical: Public Endpoint Tenant Isolation (store.py + articles.py)**
- Updated `_tid()` in store.py to accept `x_view_as_tenant` param
- `/categories`, `/products`, `/products/{id}`, `/pricing/calc`, `/terms`, `/terms/{id}` all respect `X-View-As-Tenant` for platform admins
- `/articles/public` respects `X-View-As-Tenant` AND `X-View-As-Customer` for platform admins
- `/articles/{id}/validate-scope` also updated for X-View-As-Tenant

**Admin Endpoint Path Fixes**
- `ProductsTab.tsx`: Uses `/admin/terms` instead of public `/terms`
- `SubscriptionsTab.tsx`: Uses `/admin/subscriptions/{id}/renew-now` (admin-prefixed)
- `backend/routes/admin/subscriptions.py`: Route updated to match: `@router.post("/admin/subscriptions/{id}/renew-now")`

**Setup Checklist Navigation (section-aware)**
- Checklist items now have `section` property ('branding' or 'payments')
- Clicking items navigates to tab AND specific section within WebsiteTab
- WebsiteTab accepts `defaultSection` prop with `useEffect` for reactive updates
- Admin.tsx tracks `websiteSection` state and passes to WebsiteTab
- Checklist items show descriptive navigation hints (e.g., "Go to Website Content > Branding & Hero")

**New Features (Previous Session)**
- Tenant Switcher: search by name/code, top-5 default display
- Customer Switcher: search by email, appears when viewing a tenant
- Setup Checklist Widget: 5-step setup guide, dismissible
- Single Super Admin enforcement (POST + PUT in users.py)

## Test Credentials
- Platform Admin: `admin@automateaccounts.local` / `ChangeMe123!` / code: `automate-accounts`
- Tenant B Admin: `adminb@tenantb.local` / `ChangeMe123!` / code: `tenant-b-test`

## P0 Backlog (All Resolved)
- [x] Data leaks across all modules (multiple rounds)
- [x] Public endpoints ignoring X-View-As-Tenant (store.py, articles.py)
- [x] Dual Impersonation (Customer Switcher)
- [x] Tenant Switcher search + top-5 limit
- [x] Setup Checklist Widget with section-aware navigation
- [x] Single Super Admin enforcement
- [x] SubscriptionsTab.tsx renew-now endpoint path

## P2 / Future
- [ ] Full customer portal simulation (X-View-As-Customer in portal/checkout routes)
- [ ] Admin Dashboard business metrics widget
- [ ] Additional store.py endpoints (promo-codes/validate, scope-request) may need X-View-As-Tenant for platform admin edge cases
