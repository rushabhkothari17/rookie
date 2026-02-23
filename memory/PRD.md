# Product Requirements Document
## Automate Accounts — Multi-Tenant SaaS Platform

**Original Problem Statement:**
Multi-tenant SaaS platform for accounting/bookkeeping services. Tenant isolation is critical — every API endpoint must be tenant-specific. The platform admin can manage all tenants, impersonate them, and perform global operations.

---

## Architecture
- **Stack**: FastAPI (Python) + React (TypeScript) + MongoDB
- **Pattern**: Multi-tenant with `tenant_id` on all data
- **Auth**: JWT tokens + role-based access (`platform_admin`, `partner_super_admin`, `tenant_admin`, `customer`)
- **Impersonation**: Platform admin → X-View-As-Tenant header (tenant), X-View-As-Customer header (customer)
- **API Key Auth**: `X-API-Key` header on public endpoints as alternative to JWT

---

## Implemented Features (as of Feb 2026)

### Core Infrastructure
- Multi-tenant data isolation across all collections
- JWT auth with role-based access control
- Tenant impersonation (platform admin)
- Customer impersonation (platform admin)

### Admin Panel Tabs
- Users, Customers, Subscriptions, Orders, Promo Codes, Quote Requests, Bank Transactions
- Articles, Article Templates, Article Categories, Override Codes, Categories, Catalog, Terms
- Website Content (payments, domain settings, etc.)
- API (new — see below)
- Logs

### Import/Export System (ALL entities)
All 13 entities support CSV import and export:
- Customers, Subscriptions, Orders, Promo Codes, Quote Requests, Bank Transactions
- Articles, Article Templates, Article Categories
- Override Codes, Categories, Catalog (Products), Terms

**Export endpoints**: `/api/admin/export/{entity}` (13 total)
**Import endpoint**: `POST /api/admin/import/{entity_type}`
**Sample template**: `GET /api/admin/import/template/{entity_type}`

### Payment Provider Validation
- Validate Stripe and GoCardless credentials via test API call
- Endpoint: `POST /api/admin/payment/validate`
- UI: "Validate Credentials" button in Website Content > Payments

### API Key System (NEW - Feb 2026)
- Each tenant can generate one active API key at a time
- Key format: `ak_[48 hex chars]`
- Full key shown once on generation (masked in list view)
- Admin endpoints: `GET/POST/DELETE /api/admin/api-keys`
- `X-API-Key` header supported on all public store endpoints
- Used as alternative to partner_code for external API consumers

### API Documentation Tab (Updated - Feb 2026)
- New "API" sidebar tab below "Website Content"
- API key management — only ACTIVE key shown (revoked/expired hidden)
- Comprehensive REST API documentation (26 endpoints across 7 categories)
- Unified auth model: ALL endpoints use X-API-Key; customer portal also needs Bearer JWT
- "Try It" functionality with explicit API key input field (key never stored)
- Base URL path guidance: API key resolves tenant — no subdomain required
- Non-subdomain partners: use same base URL with X-API-Key header
- Categories: Authentication, Catalog, Terms & Conditions, Articles, Quote Requests, Checkout, Customer Portal

### Partner Code in My Profile (NEW - Feb 2026)
- `/api/me` now returns `partner_code` from the user's tenant
- Profile page shows read-only "Partner / Tenant Code" field for all users
- Visible to: tenant admins, customers, all user types

### Tenant Data Safety
- All admin exports use `get_tenant_filter()` — tenant-isolated
- All admin imports assign `tenant_id` from authenticated admin
- Public endpoints support both JWT and X-API-Key for tenant resolution
- No cross-tenant data leaks on public endpoints

---

## Key API Endpoints

### Authentication
- `POST /api/auth/login` — Admin/partner login
- `POST /api/auth/customer-login` — Customer login
- `GET /api/me` — Current user profile (includes partner_code)

### Public Store (tenant-aware via JWT/X-API-Key/partner_code)
- `GET /api/categories`
- `GET /api/products`
- `GET /api/products/{id}`
- `GET /api/terms`, `GET /api/terms/{id}`
- `GET /api/articles/public`
- `POST /api/pricing/calc`

### Admin CRUD
- `GET/POST/PUT/DELETE /api/admin/{entity}` for all 13 entities

### Admin Export
- `GET /api/admin/export/{entity}` — CSV download (13 entities)

### Admin Import
- `POST /api/admin/import/{entity_type}` — CSV/JSON upload
- `GET /api/admin/import/template/{entity_type}` — Sample template download

### API Key Management
- `GET /api/admin/api-keys`
- `POST /api/admin/api-keys`
- `DELETE /api/admin/api-keys/{key_id}`

---

## Credentials for Testing
- **Platform Admin**: admin@automateaccounts.local / ChangeMe123! / partner_code: automate-accounts
- **Tenant B Admin**: adminb@tenantb.local / ChangeMe123! / partner_code: tenant-b-test

---

## Security Audit
A comprehensive security audit checklist is at `/app/memory/SECURITY_AUDIT_CHECKLIST.md`.
- 125+ checklist items across 20 security domains
- Top 10 critical fixes identified (rate limiting, CORS, token storage, etc.)
- Includes codebase-specific references for each item

### Upcoming/Future
- Full customer portal simulation (X-View-As-Customer in portal/checkout routes)
- Admin Dashboard business metrics widget
- Webhook system for subscription/order events
- Email template customization per tenant

### Known Design Issues (Non-blocking)
- Console hydration warning in CustomersTab from VE tooling injecting `<span>` into `<select>` — tooling artifact, not an app bug
