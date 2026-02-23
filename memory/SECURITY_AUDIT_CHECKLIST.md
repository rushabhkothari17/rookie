# Security Audit Checklist — Automate Accounts Platform
**Prepared:** Feb 2026 | **Version:** 1.0 | **Coverage:** Full codebase analysis

> **How to use this checklist:**
> Each item has a STATUS column. Work through each item, mark it PASS / FAIL / PARTIAL / N/A, and add notes.
> Items marked with 🔴 are HIGH risk — prioritise these first.
> Items marked with 🟡 are MEDIUM risk.
> Items marked with 🟢 are LOW risk / best-practice.

---

## TABLE OF CONTENTS
1. [Authentication](#1-authentication)
2. [Authorisation & RBAC](#2-authorisation--rbac)
3. [Tenant Data Isolation](#3-tenant-data-isolation)  ← Most critical for multi-tenant SaaS
4. [API Key Security](#4-api-key-security)
5. [API Security & Input Validation](#5-api-security--input-validation)
6. [Rate Limiting & Abuse Prevention](#6-rate-limiting--abuse-prevention)
7. [Session & Token Management](#7-session--token-management)
8. [Data Exposure & Information Leakage](#8-data-exposure--information-leakage)
9. [File Upload Security](#9-file-upload-security)
10. [Payment Security](#10-payment-security)
11. [Webhook Security](#11-webhook-security)
12. [Email Security](#12-email-security)
13. [CORS & Transport Security](#13-cors--transport-security)
14. [Database Security](#14-database-security)
15. [Audit Logging & Monitoring](#15-audit-logging--monitoring)
16. [Error Handling & Stack Traces](#16-error-handling--stack-traces)
17. [Business Logic Security](#17-business-logic-security)
18. [Infrastructure & Deployment](#18-infrastructure--deployment)
19. [Dependency & Supply Chain Security](#19-dependency--supply-chain-security)
20. [Compliance & Privacy](#20-compliance--privacy)

---

## 1. Authentication

| # | Check | Risk | Area in Code | Status | Notes |
|---|-------|------|--------------|--------|-------|
| 1.1 | Passwords hashed with bcrypt (no MD5/SHA1) | 🔴 | `core/security.py:14` — `CryptContext(schemes=["bcrypt"])` | | |
| 1.2 | Minimum password length enforced (≥ 10 chars) | 🟡 | `routes/auth.py` — register endpoint | | |
| 1.3 | Password complexity rules enforced (upper, lower, number, symbol) | 🟡 | `routes/auth.py` — register endpoint | | |
| 1.4 | Brute-force lockout on login endpoint (after N failed attempts) | 🔴 | `routes/auth.py:100` — no lockout implemented | | CURRENTLY MISSING |
| 1.5 | Account lockout state is stored server-side (not client-trusting) | 🔴 | Not implemented | | |
| 1.6 | CAPTCHA or challenge on login for repeated failures | 🟡 | Not implemented | | |
| 1.7 | Email verification required before portal access | 🟡 | `routes/auth.py` — verify-email flow | | |
| 1.8 | Email verification tokens are single-use and time-limited | 🟡 | `routes/auth.py:570` — verify-email handler | | Verify token expiry is set |
| 1.9 | Password reset tokens are single-use and expire within 1 hour | 🔴 | `services/email_service.py:177` — password_reset | | |
| 1.10 | Password reset does NOT reveal if an email is registered (anti-enumeration) | 🟡 | `routes/auth.py` — forgot-password endpoint | | |
| 1.11 | Admin login is entirely separate from customer login | 🟢 | `routes/auth.py:85/100/147` — separate endpoints | | |
| 1.12 | Platform admin account uses strong credentials in production | 🔴 | Seed: `admin@automateaccounts.local / ChangeMe123!` | | MUST CHANGE ON PROD |
| 1.13 | Multi-factor authentication (MFA) available for admin accounts | 🟡 | Not implemented | | |
| 1.14 | Login audit trail — log all login attempts (success + failure) with IP | 🟡 | Check audit_log coverage | | |
| 1.15 | Default credentials removed or changed in production | 🔴 | Seed users created at startup | | |
| 1.16 | `must_change_password` flag enforced — user cannot skip password change | 🟡 | `routes/auth.py:621` — flag returned in /me | | Verify frontend blocks access |
| 1.17 | Partner code does not replace authentication (partner_code alone cannot authenticate) | 🔴 | `routes/auth.py:100` — partner-login checks password | | |

---

## 2. Authorisation & RBAC

| # | Check | Risk | Area in Code | Status | Notes |
|---|-------|------|--------------|--------|-------|
| 2.1 | All admin endpoints require `require_admin` or `get_tenant_admin` dependency | 🔴 | `/routes/admin/*.py` — all 18 admin route files | | Audit each file |
| 2.2 | Platform-admin-only actions require `require_super_admin` or `platform_admin` role check | 🔴 | `core/tenant.py` — `get_tenant_super_admin` | | |
| 2.3 | Tenant admin cannot access other tenants' admin endpoints via header manipulation | 🔴 | `core/tenant.py:77` — `get_tenant_admin` reads `X-View-As-Tenant` | | |
| 2.4 | `X-View-As-Tenant` header is ONLY honoured for `platform_admin` role | 🔴 | `core/tenant.py:get_tenant_admin` | | Critical: tenant_admin must not be able to use this header |
| 2.5 | `X-View-As-Customer` header is ONLY honoured for `platform_admin` role | 🔴 | `routes/articles.py`, `routes/store.py` | | |
| 2.6 | Customer cannot access other customers' orders via order_id | 🔴 | `routes/store.py:416` — `GET /orders/{order_id}` | | Check ownership validation |
| 2.7 | Customer cannot access other customers' subscriptions via subscription_id | 🔴 | `routes/store.py:434` — `GET /subscriptions` | | |
| 2.8 | Only `platform_admin` can access tenant management endpoints (`/admin/tenants`) | 🔴 | `routes/admin/tenants.py` | | |
| 2.9 | Only one `super_admin` per tenant rule is enforced on user creation AND update | 🟡 | `routes/admin/users.py` | | |
| 2.10 | Tenant admin cannot escalate their own role to `platform_admin` | 🔴 | `routes/admin/users.py` — role update endpoint | | |
| 2.11 | Customer cannot call admin endpoints even with a valid customer JWT | 🔴 | `core/security.py` — `require_admin` dependency | | |
| 2.12 | Role changes to sensitive roles (`platform_admin`, `super_admin`) require additional auth | 🟡 | `routes/admin/users.py` | | |
| 2.13 | Deleted/deactivated users cannot authenticate | 🟡 | `routes/auth.py` — login check | | Check `is_active` flag on login |
| 2.14 | Deactivated customers cannot access portal endpoints | 🟡 | `routes/store.py` — orders/subscriptions endpoints | | |

---

## 3. Tenant Data Isolation

> This is the **most critical** section for a multi-tenant SaaS. Every query must be scoped to a single tenant.

| # | Check | Risk | Area in Code | Status | Notes |
|---|-------|------|--------------|--------|-------|
| 3.1 | All admin list endpoints use `get_tenant_filter(admin)` before DB query | 🔴 | All `/routes/admin/*.py` — 159 usages across codebase | | Audit each individually |
| 3.2 | `GET /admin/customers` — returns only current tenant's customers | 🔴 | `routes/admin/customers.py:23` | | |
| 3.3 | `GET /admin/orders` — returns only current tenant's orders | 🔴 | `routes/admin/orders.py:20` | | |
| 3.4 | `GET /admin/subscriptions` — returns only current tenant's subscriptions | 🔴 | `routes/admin/subscriptions.py:31` | | |
| 3.5 | `GET /admin/products-all` — returns only current tenant's products | 🔴 | `routes/admin/catalog.py:76` | | |
| 3.6 | `GET /admin/export/*` — ALL 13 export endpoints apply tenant filter | 🔴 | `routes/admin/exports.py` | | Verify all 13 endpoints |
| 3.7 | `POST /admin/import/*` — ALL 13 import endpoints assign tenant_id from auth, not from file | 🔴 | `routes/admin/imports.py` | | CSV row tenant_id MUST be overwritten |
| 3.8 | Tenant cannot import records into another tenant by including a different tenant_id in CSV | 🔴 | `routes/admin/imports.py` | | Check tenant_id override logic |
| 3.9 | Article public endpoint returns only published articles for the CURRENT tenant | 🔴 | `routes/articles.py:74` — `GET /articles/public` | | |
| 3.10 | Product listing returns only current tenant's products (no cross-tenant product visibility) | 🔴 | `routes/store.py:60` — `GET /products` | | |
| 3.11 | Terms documents are tenant-scoped (tenant A cannot read tenant B's terms) | 🔴 | `routes/store.py:118` — `GET /terms` | | |
| 3.12 | Promo codes are tenant-scoped (cannot use Tenant B's promo on Tenant A checkout) | 🔴 | `routes/store.py:143` — `POST /promo-codes/validate` | | |
| 3.13 | Bank transactions are tenant-scoped | 🔴 | `routes/admin/bank_transactions.py` | | |
| 3.14 | Quote requests are tenant-scoped | 🔴 | `routes/admin/quote_requests.py` | | |
| 3.15 | Article templates and categories are tenant-scoped | 🔴 | `routes/admin/article_templates.py`, `article_categories` | | |
| 3.16 | Override codes are tenant-scoped | 🔴 | `routes/admin/override_codes.py` | | |
| 3.17 | `X-API-Key` tenant resolution: key can ONLY access its own tenant's data | 🔴 | `core/tenant.py:resolve_api_key_tenant` | | |
| 3.18 | Platform admin impersonation does not leak data from OTHER tenants during same session | 🔴 | Verify session/header isolation | | |
| 3.19 | Audit logs are tenant-scoped | 🟡 | `routes/admin/logs.py` | | |
| 3.20 | Settings (Stripe key, GoCardless token) are tenant-scoped | 🔴 | `routes/admin/settings.py` | | One tenant cannot read another's keys |
| 3.21 | GET /admin/orders/{id} verifies order belongs to current tenant | 🔴 | `routes/admin/orders.py` | | Check ownership validation |
| 3.22 | GET /admin/subscriptions/{id} verifies subscription belongs to current tenant | 🔴 | `routes/admin/subscriptions.py` | | |
| 3.23 | Customer orders/subscriptions are scoped to both tenant AND customer | 🔴 | `routes/store.py` — /orders, /subscriptions | | Customer A cannot see Customer B's data |
| 3.24 | API keys are tenant-scoped — cannot be used to access another tenant's data | 🔴 | `routes/admin/api_keys.py` | | |

---

## 4. API Key Security

| # | Check | Risk | Area in Code | Status | Notes |
|---|-------|------|--------------|--------|-------|
| 4.1 | API keys are stored as plaintext in DB (current implementation) — consider hashing | 🟡 | `routes/admin/api_keys.py` — key stored raw | | If DB is compromised, all keys exposed |
| 4.2 | Only one active API key per tenant at any time | 🟢 | `routes/admin/api_keys.py:POST` — deactivates existing | | |
| 4.3 | Deactivated API keys cannot authenticate requests | 🔴 | `core/tenant.py:resolve_api_key_tenant` — checks `is_active: True` | | |
| 4.4 | Revoked API keys are permanently unusable (not re-activatable) | 🟡 | `routes/admin/api_keys.py:DELETE` | | |
| 4.5 | API key prefix/format is distinguishable (`ak_`) to prevent accidental commitment | 🟢 | Key format: `ak_[48 hex]` | | |
| 4.6 | Full API key is only shown ONCE on creation | 🟡 | `routes/admin/api_keys.py:POST` — returns full key once | | |
| 4.7 | API key `last_used_at` is updated on every use | 🟢 | `core/tenant.py:resolve_api_key_tenant` | | |
| 4.8 | API key usage logs (which endpoints were called) — not currently implemented | 🟡 | Not implemented | | |
| 4.9 | API keys cannot be used to access admin endpoints (admin routes require JWT + admin role) | 🔴 | `routes/admin/*.py` — use `get_tenant_admin` not `resolve_api_key_tenant` | | |
| 4.10 | API key rotation does not cause downtime — old key works until revoked | 🟢 | Generate new key → deactivates old | | |

---

## 5. API Security & Input Validation

| # | Check | Risk | Area in Code | Status | Notes |
|---|-------|------|--------------|--------|-------|
| 5.1 | NoSQL injection via unescaped `$regex` in search queries | 🔴 | `routes/articles.py:48-49` — `$regex` with raw user input | | `re.escape()` used in one place but not all |
| 5.2 | NoSQL injection via user-controlled operator keys (e.g. `{"$gt": ""}` in request body) | 🔴 | Any endpoint accepting raw dict from request body | | Check all `**payload.dict()` spreads |
| 5.3 | All path parameter IDs validated as expected format before DB lookup | 🟡 | All `{id}` endpoints | | |
| 5.4 | Pydantic models used for all request body validation | 🟡 | `models.py` + FastAPI Depends | | Check for `Dict[str, Any]` body payloads that bypass Pydantic |
| 5.5 | String fields have maximum length limits to prevent buffer exhaustion | 🟡 | Various Pydantic models | | |
| 5.6 | Integer fields have sane min/max limits (e.g. prices, quantities, percentages) | 🟡 | `models.py` | | |
| 5.7 | HTML content (articles, terms) sanitized before storage to prevent stored XSS | 🔴 | `routes/articles.py`, `routes/admin/terms.py` | | Raw HTML stored/served |
| 5.8 | HTML content rendered in frontend uses dangerouslySetInnerHTML safely | 🔴 | Article content rendering in React | | Verify DOMPurify or equivalent used |
| 5.9 | Email addresses validated before being used in DB queries or email sends | 🟡 | `routes/auth.py:445` — register endpoint | | |
| 5.10 | Numeric string inputs (amounts, quantities) are coerced to correct type before use | 🟡 | Pricing calculations in `routes/store.py:104` | | |
| 5.11 | Search parameters that are user-controlled are scoped to tenant before regex application | 🔴 | `routes/admin/quote_requests.py:69` — `$regex` on email/product | | |
| 5.12 | Partner code passed by user is validated as a safe string (no special chars) | 🟡 | `routes/auth.py` | | |
| 5.13 | Promo code input is sanitised and case-normalised before lookup | 🟢 | `routes/store.py:143` | | |
| 5.14 | Import CSV files are not executed, only parsed as data | 🔴 | `routes/admin/imports.py:145` | | |
| 5.15 | Import data values are not used as MongoDB operators | 🔴 | `routes/admin/imports.py` | | Check for CSV injection and $ key injection |
| 5.16 | GET requests have no side effects (idempotent) | 🟢 | All GET handlers | | |
| 5.17 | Sensitive query parameters (API keys, tokens) are not logged | 🟡 | Server-side logging | | |

---

## 6. Rate Limiting & Abuse Prevention

| # | Check | Risk | Area in Code | Status | Notes |
|---|-------|------|--------------|--------|-------|
| 6.1 | Rate limiting on login endpoint (to prevent credential stuffing) | 🔴 | `routes/auth.py:100,147` — NO rate limiting | | CURRENTLY MISSING — High Priority |
| 6.2 | Rate limiting on register endpoint (to prevent mass account creation) | 🔴 | `routes/auth.py:445` — NO rate limiting | | |
| 6.3 | Rate limiting on password reset / forgot-password endpoint | 🟡 | `routes/auth.py` — NO rate limiting | | |
| 6.4 | Rate limiting on resend-verification-email endpoint | 🟡 | `routes/auth.py:540` — NO rate limiting | | |
| 6.5 | Rate limiting on public API endpoints (categories, products) for external consumers | 🟡 | `routes/store.py` — NO rate limiting | | |
| 6.6 | Rate limiting on checkout endpoint (prevents rapid fake order creation) | 🔴 | `routes/checkout.py` — NO rate limiting | | |
| 6.7 | Rate limiting on scope-request endpoints (prevents spam) | 🟡 | `routes/store.py:204,266` — NO rate limiting | | |
| 6.8 | Rate limiting on email-sending endpoints (prevent email bombing) | 🔴 | `routes/articles.py:410,479` — email send | | |
| 6.9 | SlowAPI or FastAPI equivalent middleware not installed | 🔴 | `server.py` — no rate limit middleware | | CURRENTLY MISSING |
| 6.10 | IP-based rate limiting at infrastructure level (reverse proxy/WAF) | 🟡 | Depends on deployment | | |
| 6.11 | API key usage rate limits (prevent a single tenant from overloading the platform) | 🟡 | Not implemented | | |
| 6.12 | Import endpoint rate/size limiting (prevent CSV bombs) | 🟡 | `routes/admin/imports.py` — no size limit | | |

---

## 7. Session & Token Management

| # | Check | Risk | Area in Code | Status | Notes |
|---|-------|------|--------------|--------|-------|
| 7.1 | JWT tokens expire after a reasonable window (current: 7 days) | 🟡 | `core/security.py:22` — `timedelta(days=7)` | | Consider 24hr for admin, 7 days for customer |
| 7.2 | JWT token includes tenant_id in payload (for server-side validation) | 🔴 | `core/security.py` — `make_token` function | | |
| 7.3 | JWT tokens are validated server-side on every request (not just decoded) | 🔴 | `core/security.py:30` — jwt.decode | | |
| 7.4 | Revoked/blacklisted tokens (e.g. after password change) cannot be used | 🔴 | No token blacklist implemented | | After password change, old JWT still valid |
| 7.5 | Password change invalidates all existing JWT tokens for that user | 🟡 | Not implemented | | |
| 7.6 | JWT secret is rotated periodically | 🟡 | `core/config.py:JWT_SECRET` | | |
| 7.7 | JWT secret is cryptographically random and sufficiently long (≥ 32 bytes) | 🔴 | Check `JWT_SECRET` environment variable value | | |
| 7.8 | JWT tokens are not stored in localStorage in frontend (prefer httpOnly cookies) | 🟡 | `lib/api.ts` — `localStorage.getItem("aa_token")` | | XSS risk — tokens in localStorage accessible to scripts |
| 7.9 | Sensitive operations require re-authentication (e.g. deleting account, changing email) | 🟡 | Not implemented | | |
| 7.10 | Token replay attacks mitigated (short expiry + rotation) | 🟡 | 7-day expiry without rotation | | |

---

## 8. Data Exposure & Information Leakage

| # | Check | Risk | Area in Code | Status | Notes |
|---|-------|------|--------------|--------|-------|
| 8.1 | Payment secret keys (Stripe, GoCardless) NEVER returned to frontend | 🔴 | `routes/admin/settings.py:69` — redacts keys in responses | | Verify redaction is applied on all GET settings routes |
| 8.2 | Resend API key NEVER returned to frontend | 🔴 | Same as above | | |
| 8.3 | MongoDB `_id` fields excluded from all API responses | 🟡 | `{"_id": 0}` in projections throughout codebase | | |
| 8.4 | Password hashes NEVER included in API responses | 🔴 | Check all user-returning endpoints | | |
| 8.5 | JWT payloads do NOT include sensitive data (passwords, full PII) | 🟡 | `core/security.py:make_token` | | |
| 8.6 | Stack traces NOT exposed in production API error responses | 🔴 | FastAPI default 500 handler | | |
| 8.7 | Internal MongoDB error messages NOT exposed in API responses | 🟡 | Exception handlers | | |
| 8.8 | User enumeration via login error messages prevented (generic "invalid credentials") | 🟡 | `routes/auth.py` — login error messages | | |
| 8.9 | User enumeration via registration prevented ("email already in use" vs generic message) | 🟡 | `routes/auth.py:445` — register endpoint | | |
| 8.10 | Tenant ID / internal IDs not exposed in error messages to customers | 🟡 | All customer-facing error responses | | |
| 8.11 | Audit logs accessible ONLY to platform_admin and tenant_admin (not customers) | 🔴 | `routes/admin/logs.py` | | |
| 8.12 | Health/debug endpoints (if any) not exposed in production | 🟡 | `routes/auth.py:25` — `GET /` root endpoint | | |
| 8.13 | API documentation endpoint (OpenAPI/Swagger) restricted in production | 🟡 | FastAPI default `/docs` and `/redoc` | | Check if accessible in prod |
| 8.14 | Customer A cannot see Customer B's PII through any endpoint | 🔴 | All customer-facing endpoints | | |
| 8.15 | Tenant settings (custom fields, intake questions) not leaked to other tenants | 🟡 | `routes/store.py` — product intake_schema_json | | |

---

## 9. File Upload Security

| # | Check | Risk | Area in Code | Status | Notes |
|---|-------|------|--------------|--------|-------|
| 9.1 | File type validated by content (magic bytes), not just extension | 🔴 | `routes/admin/imports.py:142` — only `.endswith(".csv")` check | | Extension spoofing possible |
| 9.2 | File upload size limit enforced (prevent DoS via large file upload) | 🔴 | `routes/admin/imports.py` — NO size limit | | CURRENTLY MISSING |
| 9.3 | Uploaded logos validated as actual images (content-type + magic bytes) | 🟡 | `routes/admin/settings.py:140` — checks content_type | | |
| 9.4 | Uploaded files are not executed (CSV is parsed, not eval'd) | 🔴 | `routes/admin/imports.py:145` | | No code execution risk in Python csv module |
| 9.5 | CSV injection prevented (values starting with `=`, `+`, `-`, `@` escaped) | 🔴 | Export CSVs generated by `_make_csv_response` in exports.py | | Clients opening in Excel may execute formulas |
| 9.6 | File names are sanitized before any storage operation | 🟡 | Logo upload in settings.py | | |
| 9.7 | Upload destination directory is outside web root (no direct URL access) | 🟢 | Files stored in GridFS/MongoDB or object storage | | |
| 9.8 | Maximum row count limit on CSV imports (prevent exhaustion) | 🟡 | `routes/admin/imports.py` — no row limit | | |
| 9.9 | Zip bombs and embedded macros not possible in CSV format | 🟢 | CSV only — no ZIP/Office format support | | |

---

## 10. Payment Security

| # | Check | Risk | Area in Code | Status | Notes |
|---|-------|------|--------------|--------|-------|
| 10.1 | Credit card numbers NEVER stored, logged, or passed through application (Stripe tokenisation) | 🔴 | `routes/checkout.py` — Stripe sessions only | | Verify no card data touches server |
| 10.2 | Stripe secret key never exposed in frontend JavaScript bundle | 🔴 | Key stored in DB settings, server-side only | | |
| 10.3 | GoCardless access token never exposed in frontend | 🔴 | Same as above | | |
| 10.4 | Payment amounts are computed SERVER-SIDE from product pricing, not client-provided | 🔴 | `routes/checkout.py` — amounts from DB products | | |
| 10.5 | Promo discounts are applied server-side, not trusted from client | 🔴 | `routes/store.py:143` — validate on server | | |
| 10.6 | Order total is re-calculated on server at checkout, not taken from cart | 🔴 | `routes/checkout.py` | | |
| 10.7 | Duplicate checkout sessions cannot create duplicate orders | 🟡 | `routes/checkout.py` — idempotency check | | |
| 10.8 | Stripe webhook signature verified before processing payment events | 🔴 | `routes/webhooks.py` | | |
| 10.9 | GoCardless webhook signature verified (HMAC-SHA256) | 🔴 | `routes/webhooks.py:177-179` — HMAC verification | | |
| 10.10 | Refund operations require admin authentication (not customer-self-service) | 🟡 | Verify refund endpoint access control | | |
| 10.11 | Payment credential validation (Validate button) uses server-side test call, not client-side | 🟢 | `routes/admin/payment_validate.py` — server-side call | | |
| 10.12 | Stripe test vs live key separation enforced in production | 🔴 | Env var based | | |

---

## 11. Webhook Security

| # | Check | Risk | Area in Code | Status | Notes |
|---|-------|------|--------------|--------|-------|
| 11.1 | Stripe webhook endpoint verifies Stripe-Signature header before processing | 🔴 | `routes/webhooks.py` | | |
| 11.2 | GoCardless webhook endpoint verifies HMAC signature before processing | 🔴 | `routes/webhooks.py:177-179` | | Currently implemented |
| 11.3 | Webhook endpoints return 200 quickly; processing is non-blocking | 🟡 | `routes/webhooks.py` | | |
| 11.4 | Webhook replay attacks mitigated (timestamp tolerance check) | 🟡 | Stripe handles this; GoCardless — verify | | |
| 11.5 | Webhook secret key not hardcoded (loaded from env/settings) | 🔴 | `routes/webhooks.py:177` — from env/settings | | |
| 11.6 | Failed webhook deliveries are logged for retry | 🟢 | Audit log coverage for webhook events | | |

---

## 12. Email Security

| # | Check | Risk | Area in Code | Status | Notes |
|---|-------|------|--------------|--------|-------|
| 12.1 | Email "from" address is configurable per tenant (no platform-global override) | 🟡 | `services/email_service.py` | | |
| 12.2 | Email content generated from templates, not raw user input | 🔴 | `services/email_service.py` | | |
| 12.3 | Email template injection prevented (user values escaped in templates) | 🔴 | Template rendering in email_service.py | | |
| 12.4 | Resend API key is tenant-specific (not platform-shared) | 🟡 | `routes/admin/settings.py` — per-tenant settings | | |
| 12.5 | Admin "send article to customer" endpoint is rate-limited | 🟡 | `routes/articles.py:479` — send-email endpoint | | |
| 12.6 | Mass email sends require admin role (not customer-accessible) | 🔴 | `routes/articles.py:410,479` | | Verify auth dependency |
| 12.7 | Email addresses in "send to customer" are validated before sending | 🟡 | `routes/articles.py:479` | | |
| 12.8 | SPF/DKIM/DMARC configured for sending domains | 🟡 | DNS configuration | | Platform-level concern |
| 12.9 | Unsubscribe / opt-out mechanism exists for marketing emails | 🟡 | Not verified | | |

---

## 13. CORS & Transport Security

| # | Check | Risk | Area in Code | Status | Notes |
|---|-------|------|--------------|--------|-------|
| 13.1 | CORS `allow_origins` is NOT `["*"]` in production | 🔴 | `server.py:36` — CURRENTLY `allow_origins=["*"]` | | MUST FIX BEFORE PROD |
| 13.2 | CORS restricts to known tenant domains / platform domain | 🔴 | `server.py:36` | | |
| 13.3 | HTTPS enforced on all endpoints in production (no HTTP fallback) | 🔴 | Infrastructure/deployment level | | |
| 13.4 | HSTS (Strict-Transport-Security) header set | 🟡 | Reverse proxy / FastAPI middleware | | |
| 13.5 | Sensitive cookies (if any) use `Secure`, `HttpOnly`, `SameSite=Strict` flags | 🟡 | JWT stored in localStorage (not cookie) | | |
| 13.6 | X-Content-Type-Options: nosniff header set | 🟢 | FastAPI/reverse proxy | | |
| 13.7 | X-Frame-Options: DENY or SAMEORIGIN set (prevent clickjacking) | 🟡 | FastAPI/reverse proxy | | |
| 13.8 | Content-Security-Policy header configured | 🟡 | React frontend | | |
| 13.9 | Referrer-Policy header configured | 🟢 | | | |
| 13.10 | TLS version ≥ 1.2 (preferably 1.3 only) | 🟡 | Infrastructure | | |

---

## 14. Database Security

| # | Check | Risk | Area in Code | Status | Notes |
|---|-------|------|--------------|--------|-------|
| 14.1 | MongoDB not exposed publicly (firewall / VPC only) | 🔴 | Infrastructure | | |
| 14.2 | MongoDB authentication enabled (username/password) | 🔴 | `backend/.env:MONGO_URL` — check connection string | | |
| 14.3 | MongoDB user has minimum required permissions (not root) | 🟡 | Check connection string privileges | | |
| 14.4 | MongoDB Atlas IP allowlist configured (if using Atlas) | 🟡 | MongoDB Atlas settings | | |
| 14.5 | Database backups enabled and tested | 🟡 | MongoDB Atlas backup / ops team | | |
| 14.6 | Backup data encrypted at rest | 🟡 | Storage layer | | |
| 14.7 | `_id` (ObjectId) never returned in API responses | 🟡 | `{"_id": 0}` projections throughout codebase | | |
| 14.8 | All writes use specific `$set` (not full document replacement) to prevent data loss | 🟡 | All `update_one` calls | | |
| 14.9 | Compound indexes exist for tenant_id + common filter fields (performance + security) | 🟢 | Database schema | | Missing indexes enable data leakage via performance timing |
| 14.10 | No raw MongoDB connection string in frontend code or logs | 🔴 | `backend/.env:MONGO_URL` — backend-only | | |

---

## 15. Audit Logging & Monitoring

| # | Check | Risk | Area in Code | Status | Notes |
|---|-------|------|--------------|--------|-------|
| 15.1 | All admin create/update/delete operations are audit-logged | 🟡 | 123 audit log calls across codebase | | Verify coverage is complete |
| 15.2 | Audit logs include: actor email, entity type, entity ID, action, timestamp, IP | 🟡 | `core/helpers.py` — `create_audit_log` | | |
| 15.3 | Audit logs are tenant-scoped and cannot be modified/deleted by tenant admins | 🔴 | `routes/admin/logs.py` | | |
| 15.4 | Audit logs for sensitive operations: API key generation/revocation | 🟡 | `routes/admin/api_keys.py` — not currently logged | | |
| 15.5 | Audit logs for payment credential changes | 🟡 | `routes/admin/settings.py` | | |
| 15.6 | Audit logs for user role changes | 🔴 | `routes/admin/users.py` | | |
| 15.7 | Failed authentication attempts logged | 🟡 | `routes/auth.py` | | |
| 15.8 | Bulk imports logged with record count and actor | 🟡 | `routes/admin/imports.py` | | |
| 15.9 | Exports logged (what data was exported and by whom) | 🟡 | `routes/admin/exports.py` | | |
| 15.10 | Monitoring/alerting on unusual patterns (many 401s, bulk deletes) | 🟡 | External monitoring required | | |
| 15.11 | Logs stored separately from application (not same DB) | 🟢 | Currently in MongoDB | | Consider external log aggregation |
| 15.12 | Log retention policy defined | 🟢 | | | |

---

## 16. Error Handling & Stack Traces

| # | Check | Risk | Area in Code | Status | Notes |
|---|-------|------|--------------|--------|-------|
| 16.1 | Generic error messages returned to clients (no stack traces) | 🔴 | FastAPI exception handling in `server.py` | | |
| 16.2 | Unhandled exceptions return 500 with generic message, not traceback | 🔴 | FastAPI default — check prod config | | |
| 16.3 | HTTPException detail messages don't reveal internal paths or DB errors | 🟡 | All `raise HTTPException(...)` calls | | |
| 16.4 | MongoDB exceptions caught and mapped to safe error responses | 🟡 | Try/except blocks in route handlers | | |
| 16.5 | Payment provider errors (Stripe, GoCardless) don't leak provider details to customer | 🟡 | `routes/checkout.py` exception handling | | |
| 16.6 | Debug/development mode disabled in production | 🔴 | `server.py` — FastAPI debug flag | | |

---

## 17. Business Logic Security

| # | Check | Risk | Area in Code | Status | Notes |
|---|-------|------|--------------|--------|-------|
| 17.1 | Subscription cannot be cancelled twice | 🟡 | `routes/store.py:434` | | |
| 17.2 | Order cannot be paid multiple times (duplicate Stripe session handling) | 🔴 | `routes/checkout.py` — idempotency | | |
| 17.3 | Expired promo codes cannot be applied | 🟡 | `routes/store.py:143` — promo validation | | |
| 17.4 | Promo code usage limits enforced (max_uses, per-customer limits) | 🟡 | Promo code models | | |
| 17.5 | Product prices cannot be manipulated via request body | 🔴 | `routes/checkout.py` — server-side pricing | | |
| 17.6 | Free/trial tier cannot be exploited by creating multiple accounts | 🟡 | Not a concern if no free tier | | |
| 17.7 | Scope requests cannot be submitted for products from another tenant | 🔴 | `routes/store.py:204,266` — scope-request | | |
| 17.8 | Customer cannot access another customer's articles by scoping | 🔴 | `routes/articles.py:74` — article visibility | | |
| 17.9 | `must_change_password` flow cannot be bypassed (forced on first login) | 🟡 | Frontend enforcement | | |
| 17.10 | User/customer deactivation takes immediate effect across all sessions | 🟡 | JWT-based — tokens remain valid until expiry | | |
| 17.11 | Currency cannot be changed after first order (locked) | 🟢 | Customer model — currency lock logic | | |
| 17.12 | Admin cannot create invoices/orders for customers across tenants | 🔴 | `routes/admin/orders.py:94` — manual order | | |

---

## 18. Infrastructure & Deployment

| # | Check | Risk | Area in Code | Status | Notes |
|---|-------|------|--------------|--------|-------|
| 18.1 | All secrets (JWT_SECRET, MONGO_URL, API keys) in env vars, never in code | 🔴 | `core/config.py` — env-loaded ✓ | | Verify no hardcoded fallbacks in prod |
| 18.2 | `.env` files not committed to version control | 🔴 | `.gitignore` | | |
| 18.3 | Production uses different secrets from development/staging | 🔴 | Deployment configuration | | |
| 18.4 | Kubernetes secrets used for sensitive env vars (not plaintext ConfigMaps) | 🟡 | Deployment manifests | | |
| 18.5 | FastAPI `reload=True` / debug mode disabled in production | 🔴 | `server.py` startup config | | |
| 18.6 | Container runs as non-root user | 🟡 | Dockerfile | | |
| 18.7 | Container base image regularly updated for security patches | 🟡 | Dockerfile | | |
| 18.8 | Network policies restrict pod-to-pod communication | 🟡 | Kubernetes config | | |
| 18.9 | Read-only filesystem for containers where possible | 🟢 | Deployment manifests | | |
| 18.10 | Health check endpoint does not expose sensitive information | 🟡 | `routes/auth.py:25` — `GET /` | | |

---

## 19. Dependency & Supply Chain Security

| # | Check | Risk | Area in Code | Status | Notes |
|---|-------|------|--------------|--------|-------|
| 19.1 | `requirements.txt` pinned to exact versions | 🟡 | `/app/backend/requirements.txt` | | |
| 19.2 | `package.json` frontend dependencies pinned to exact versions | 🟡 | `/app/frontend/package.json` | | |
| 19.3 | Regular dependency vulnerability scans run (`pip-audit`, `npm audit`) | 🟡 | CI/CD pipeline | | |
| 19.4 | No known high-severity CVEs in direct dependencies | 🔴 | Run `pip-audit` and `npm audit` | | |
| 19.5 | Python packages installed from trusted sources only (PyPI) | 🟡 | `requirements.txt` | | Emergentintegrations uses CloudFront CDN |
| 19.6 | No unused/abandoned dependencies with known vulnerabilities | 🟡 | Regular audit | | |
| 19.7 | fastapi, pyjwt, passlib, httpx on latest stable versions | 🟡 | `requirements.txt` | | |
| 19.8 | emergentintegrations package source verified and trusted | 🟡 | CloudFront CDN distribution | | |

---

## 20. Compliance & Privacy

| # | Check | Risk | Area in Code | Status | Notes |
|---|-------|------|--------------|--------|-------|
| 20.1 | Privacy policy in place for data collected (names, emails, payment info) | 🔴 | Legal/compliance | | |
| 20.2 | GDPR: right to erasure (delete account and all associated data) implemented | 🔴 | Not verified — customer delete endpoint? | | |
| 20.3 | GDPR: data portability (customer can export their own data) | 🟡 | Not verified | | |
| 20.4 | GDPR: explicit consent collected before processing personal data | 🟡 | Registration flow | | |
| 20.5 | Data retention policy: old/deleted records purged after N days | 🟡 | Not implemented | | |
| 20.6 | PII fields (name, email, address) encrypted at rest | 🟡 | MongoDB — check field-level encryption | | |
| 20.7 | Personal data minimisation: only collect what's needed | 🟢 | Data models | | |
| 20.8 | Subprocessors (Stripe, GoCardless, Resend) have DPA agreements in place | 🟡 | Legal | | |
| 20.9 | Cookie consent banner present (for analytics/tracking cookies) | 🟡 | Frontend | | |
| 20.10 | Terms & Conditions and Privacy Policy acceptance logged at registration | 🟢 | Registration flow | | |
| 20.11 | PCI DSS compliance for card data handling (Stripe handles, not you) | 🟡 | Stripe tokenisation removes most PCI scope | | |
| 20.12 | Data encrypted in transit between backend and MongoDB | 🟡 | MONGO_URL — verify TLS enabled in connection string | | |

---

## SUMMARY — Risk Count

| Priority | Count | Description |
|----------|-------|-------------|
| 🔴 HIGH | ~65 | Must fix before production launch |
| 🟡 MEDIUM | ~45 | Should fix before launch or immediately post-launch |
| 🟢 LOW | ~15 | Best practice, address in next sprint |

## TOP 10 CRITICAL FIXES (Immediate Action Required)

| Priority | Issue | Location |
|----------|-------|----------|
| 1 | No rate limiting on login/register/checkout endpoints | `server.py` — add slowapi or similar |
| 2 | CORS `allow_origins=["*"]` must be restricted to known domains | `server.py:36` |
| 3 | Platform admin default credentials must be changed in production | `server.py:seed_admin_user` |
| 4 | JWT tokens stored in localStorage (XSS vulnerable) | `lib/api.ts` — consider httpOnly cookies |
| 5 | Token invalidation after password change not implemented | `routes/auth.py` + token blacklist |
| 6 | No file upload size limit on CSV imports (DoS vector) | `routes/admin/imports.py` |
| 7 | HTML content (articles, terms) not sanitized — stored XSS risk | `routes/articles.py`, `routes/admin/terms.py` |
| 8 | NoSQL regex injection with unescaped user input | `routes/articles.py:48-49`, `routes/admin/quote_requests.py:69` |
| 9 | Admin panel Swagger/OpenAPI docs accessible without auth | FastAPI `/docs` endpoint |
| 10 | `X-View-As-Tenant` — verify it is ONLY honoured for `platform_admin` | `core/tenant.py:get_tenant_admin` |

---

*Document maintained at `/app/memory/SECURITY_AUDIT_CHECKLIST.md`. Update STATUS column as items are addressed.*
