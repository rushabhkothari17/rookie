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

## P0 — Pre-Production Checklist
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
- [ ] JWT migration from localStorage to HttpOnly cookie (large refactor — future)
- [ ] Run `pip-audit` + `npm audit` as part of CI/CD pipeline

## P2 — Future Sprints
- [ ] MFA / TOTP for admin accounts
- [ ] GDPR: customer self-service data export
- [ ] GDPR: customer right-to-erasure self-service
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
- Latest: `/app/test_reports/iteration_67.json` — 35 tests, all pass (security hardening)
