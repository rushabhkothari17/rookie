# Product Requirements Document — Automate Accounts Platform
**Last Updated:** Feb 2026

## Original Problem Statement
Build a multi-tenant SaaS platform for managing accounts, subscriptions, orders, and billing — with a secure admin portal, customer portal, and public API.

## Architecture
- **Backend**: FastAPI (Python) + MongoDB (Motor async)
- **Frontend**: React + TypeScript + Tailwind + Shadcn/UI
- **Auth**: JWT (admin/customer) + X-API-Key (public API)
- **Payments**: Stripe + GoCardless (per-tenant config)
- **Email**: Resend (per-tenant config)

## Core Multi-Tenant Model
- `partner_code` identifies each tenant (e.g., `automate-accounts`, `tenant-b`)
- All data scoped by `tenant_id`
- Platform super admin can view across tenants via `X-View-As-Tenant` header
- Customer accounts are tenant-specific

## What's Been Implemented

### Phase 1: Core Platform
- Multi-tenant registration + login (partner/customer separate flows)
- Admin CRUD for: customers, orders, subscriptions, products, categories, promo codes, articles, terms, bank transactions, quote requests, API keys, settings
- Customer portal: view orders, subscriptions, articles
- Checkout flows: Stripe (card), GoCardless (direct debit), bank transfer
- Email notifications via Resend (per-tenant)
- Audit log system (append-only)

### Phase 2: Import/Export
- CSV import with upsert for all 13+ entities
- CSV export with tenant-scoped filters
- Sample template downloads
- Payment credential validation (Stripe + GoCardless)

### Phase 3: API Documentation
- Comprehensive API tab in admin with 26 endpoints
- Working "Try It" feature with X-API-Key support
- Public endpoints support X-API-Key for tenant identification

### Phase 4: Security Overhaul (Feb 2026)
See CHANGELOG.md for full details. 35/35 security tests pass.
Key: rate limiting, security headers, CORS restriction, IDOR fixes, NoSQL injection prevention, HTML sanitization, brute-force lockout, admin unlock, password complexity, token invalidation, CSV formula injection, file upload limits, MongoDB indexes, audit logging.

### Phase 5: Webhook System (Feb 2026)
- 12 events across 5 categories (Orders, Subscriptions, Customers, Payments, Quote Requests)
- Per-event field picker — choose exactly which fields go in each event's payload
- HMAC-SHA256 signing (`X-Webhook-Signature: sha256=...`)
- Async delivery with 3 retries (5s → 30s → 2min exponential backoff)
- Full delivery log with request/response detail view
- Test delivery, rotate secret, pause/resume per webhook
- Admin Webhooks tab in sidebar below API (cards UI + create/edit modal + event builder)
- Tenant-isolated (admin can only manage own webhooks)
- [x] ~~Set `ENVIRONMENT=production` in backend .env~~ (code ready — set env var before deploy)
- [x] ~~JWT_SECRET rotated to strong 64-char hex~~ (done — `backend/.env` updated)
- [x] ~~Startup validation warns/errors on weak secrets~~ (implemented in `server.py`)
- [ ] Set strong `ADMIN_PASSWORD` (change default `ChangeMe123!` before production deploy)
- [ ] Verify MongoDB connection string uses read/write role (not root)

## P1 — Implemented
- [x] ~~API key hashing: SHA-256 stored, raw key never in DB~~ (done + migration on startup)
- [x] ~~Content-Security-Policy header~~ (done in `SecurityHeadersMiddleware`)
- [x] ~~Export audit logging~~ (done for orders + customers exports)
- [x] ~~starlette upgraded to 0.41.0 (CVE-2024-47874 fixed)~~
- [x] ~~pymongo upgraded to 4.6.3 (CVE-2024-5629 fixed)~~
- [x] ~~fastapi upgraded to 0.115.14~~
- [x] ~~JWT migration from localStorage to HttpOnly cookie~~ (completed Feb 2026)
- [ ] Run `pip-audit` + `npm audit` as part of CI/CD pipeline

## P2 — Future Sprints
- [ ] MFA / TOTP for admin accounts
- [x] ~~GDPR: customer self-service data export~~ (completed Feb 2026)
- [x] ~~GDPR: customer right-to-erasure self-service~~ (completed Feb 2026)
- [ ] Cookie consent banner
- [ ] Data retention policy automation
- [ ] Per-API-key rate limits
- [ ] Application-level field encryption for PII at rest
- [ ] External monitoring/alerting (Sentry, Datadog)
- [ ] CI/CD: `pip-audit`, `npm audit`, SAST scanning in pipeline

## Credentials (Dev/Test)
- Platform admin: `admin@automateaccounts.local` / `ChangeMe123!`
- Partner code: `automate-accounts`
- Tenant B admin: `adminb@tenantb.local` / `ChangeMe123!`
- Partner code B: `tenant-b`

## Test Suite
- `/app/backend/tests/test_security_hardening.py` — 35 tests, all pass (Feb 2026)
- Previous: `/app/test_reports/iteration_231.json` — 31 tests, all pass (pre-security work)
- Security: `/app/test_reports/iteration_67.json` — 35 tests, all pass (security hardening)
- Webhooks: `/app/test_reports/iteration_364.json` — 49 tests, all pass (webhook system)
- UI Bugs: `/app/test_reports/iteration_70.json` — 7 backend + frontend tests pass (login flow fix)
- Security Sweep: `/app/test_reports/iteration_71.json` — 22 backend tests pass (IDOR, tenant isolation)

### P0 Bug Fixes (Feb 2026)
**Bug 1 - Admin Tab Visibility:** Fixed customer login flow. AuthContext now falls back to `/auth/customer-login` when `/auth/partner-login` returns 403 "Access denied". TopNav correctly uses `{user?.is_admin && ...}` to hide Admin tab for customers.

**Bug 2 - Partner Code Display:** Partner code now displays correctly in user profile. Backend `/me` endpoint resolves `partner_code` from tenant table via `tenant_id`. Profile.tsx displays `user?.partner_code` with fallback to "—".

**Bug 3 - Cross-Tab Session Sync:** Added storage event listener in AuthContext to sync login/logout across browser tabs sharing the same localStorage.

**Bug 4 - Partner Code Resolution:** Fixed `store.py` - partner_code was being used directly as tenant_id instead of looking up actual tenant. Now properly resolves via `_resolve_tenant_id()` async function.

### Security Hardening - IDOR Prevention (Feb 2026)
- **orders.py:** Added tenant-scope validation for `customer_id` and `subscription_id` updates
- **subscriptions.py:** Added tenant-scope validation for `customer_id` updates, fixed webhook customer lookups
- **bank_transactions.py:** Added tenant-scope validation for `linked_order_id`
- **settings.py:** Added file type and size validation for logo uploads (2MB max)
- All cross-tenant access attempts now return 400/404 errors as expected

### Phase 6: Integrations & GDPR (Feb 2026)
**Zoho Mail Integration:**
- OAuth2 flow with US/CA datacenter selection
- Connection validation endpoint
- Stored alongside Resend as alternative email provider

**Zoho CRM Integration:**
- OAuth2 flow with US/CA datacenter selection  
- Dynamic module and field discovery
- Field mapping UI (webapp modules → CRM modules)
- Supports: Customers, Orders, Subscriptions, Quote Requests mapping

**GDPR Compliance:**
- Customer data export (JSON + ZIP with CSV/TXT)
- Right-to-erasure (account anonymization)
- Admin GDPR request tracking
- Active subscription check before deletion

**New Files:**
- `backend/services/zoho_service.py` - Zoho Mail/CRM service classes
- `backend/services/gdpr_service.py` - GDPR export/deletion logic
- `backend/routes/admin/integrations.py` - Integration CRUD endpoints
- `backend/routes/gdpr.py` - GDPR customer/admin endpoints
- `frontend/src/pages/admin/CRMTab.tsx` - CRM integration UI

### Test Data
- Comprehensive test cases CSV: `/app/test_cases_comprehensive.csv` (121 test cases)
- Tenant B seeded with: 5 customers, 5 products, 3 subscriptions, 5 orders, 3 articles, 3 quote requests, 2 promo codes, 3 bank transactions

### Phase 7: HttpOnly Cookie Authentication (Feb 2026)
**Security Enhancement - HttpOnly Cookies:**
- Migrated JWT tokens from localStorage to HttpOnly cookies
- Login endpoints now set `aa_access_token` cookie with proper security flags:
  - `httponly=True` (XSS protection)
  - `secure=True` (HTTPS only in production)
  - `samesite=lax` (CSRF protection)
- Token extraction supports both Authorization header and cookie for backward compatibility
- Logout endpoint (`/api/auth/logout`) properly clears the cookie
- Frontend AuthContext updated to call logout endpoint
- API client configured with `withCredentials: true` for cookie support

**Files Modified:**
- `backend/routes/auth.py` - Cookie set/clear helpers, login endpoints updated
- `backend/core/security.py` - `HTTPBearer(auto_error=False)` to allow cookie-only auth
- `frontend/src/contexts/AuthContext.tsx` - Logout calls API endpoint
- `frontend/src/lib/api.ts` - `withCredentials: true` added

**Test Report:** `/app/test_reports/iteration_72.json` - 100% pass rate, all auth flows verified

### Phase 8: Multi-Feature Implementation (Feb 2026)

**1. Cookie Consent Banner (GDPR)**
- Non-blocking bottom notification bar
- "Accept All" and "Essential Only" buttons
- localStorage persistence of consent choice
- Smooth slide-in animation
- New file: `frontend/src/components/CookieConsent.tsx`

**2. CRM Tab Tile Layout Refactor**
- Zoho CRM provider displayed as clickable tile
- "Coming Soon" placeholders for Salesforce and HubSpot
- Setup guide with step-by-step instructions
- Refresh connection button
- Slide-out configuration panel on tile click
- Refactored: `frontend/src/pages/admin/CRMTab.tsx`

**3. Email Provider Mutual Exclusivity**
- Only one email provider can be active at a time
- Clear messaging when activating new provider
- "Connected" / "Not Connected" status badges
- Warning when no provider is active
- Deactivate button to disable current provider
- Setup guides added to Resend and Zoho Mail panels
- Refactored: `frontend/src/pages/admin/EmailSection.tsx`

**4. Webhook Delivery Dashboard & Replay**
- Stats dashboard showing Total/Success/Failed/Pending counts
- Success rate percentage
- Recent failures list with webhook names
- Replay button for failed deliveries
- New endpoint: `/api/admin/webhooks/delivery-stats`
- New endpoint: `/api/admin/webhooks/{id}/deliveries/{id}/replay`
- Modified: `backend/routes/admin/webhooks.py`
- Modified: `frontend/src/pages/admin/WebhooksTab.tsx`

**5. Security Audit Fixes**
- Fixed IDOR in user activation endpoint (tenant filter added)
- Fixed IDOR in user logs endpoint (tenant ownership verified)
- Added brute-force protection to email verification (5 attempts, 15-min lockout)
- Modified: `backend/routes/admin/users.py`
- Modified: `backend/routes/auth.py`

**6. Integration Guides**
- Reusable IntegrationGuide component created
- Guides for: Resend, Zoho Mail, Zoho CRM, Stripe, GoCardless
- Step-by-step setup instructions
- Direct links to provider dashboards
- Pro tips for each integration
- New file: `frontend/src/components/admin/IntegrationGuide.tsx`

**Test Reports:**
- `/app/test_reports/iteration_73.json` - All features verified
- Route ordering bug fixed in webhooks.py by testing agent

### Phase 9: JWT Refresh & Performance (Feb 2026)

**1. JWT Token Refresh Mechanism**
- Access tokens now expire in 1 hour (was 7 days)
- Refresh tokens last 30 days, stored in HttpOnly cookie (path=/api/auth)
- New endpoint: `/api/auth/refresh` - exchanges refresh token for new access token
- Frontend API interceptor auto-refreshes on 401 errors
- Token type validation ('access' vs 'refresh') prevents token misuse
- Modified: `backend/core/security.py`, `backend/routes/auth.py`
- Modified: `frontend/src/lib/api.ts`

**2. N+1 Query Optimization - Customers List**
- Replaced in-memory filtering with MongoDB aggregation pipeline
- Single query joins customers + users + addresses
- Filters (search, country, status, payment_mode) applied in database
- Reduced memory usage and improved response times
- Modified: `backend/routes/admin/customers.py`

**3. Non-Blocking Setup Wizard**
- Widget is now collapsible (minimize to floating badge)
- "Dismiss permanently" option stored in localStorage  
- Shows only incomplete tasks (max 3 visible)
- Compact progress indicator
- Modified: `frontend/src/components/admin/SetupChecklistWidget.tsx`

**4. Contextual Guides System**
- Created comprehensive guide database with 15+ topics
- Three display variants: inline, tooltip, collapsible
- Topics covered:
  - Customer Management (status, payment methods, currency)
  - Orders (lifecycle, refunds)
  - Subscriptions (billing cycles, proration)
  - Webhooks (signatures, retries)
  - API Keys (best practices)
  - Products (pricing, variants)
  - User Roles (permissions)
  - Store (SEO)
- New file: `frontend/src/components/admin/ContextualGuide.tsx`

**Test Reports:**
- `/app/test_reports/iteration_74.json` - 100% pass rate (19/19 tests)
- Bug fixed: UnboundLocalError in verify_email (shadowed datetime imports)

