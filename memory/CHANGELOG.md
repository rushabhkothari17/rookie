# Changelog — Automate Accounts Platform

## Feb 2026 — Security Overhaul (Complete)

### Security Hardening — All 35 Tests Pass
- **Rate Limiting**: Custom `RateLimitMiddleware` per-IP sliding window on login (10/min), register (5/min), checkout (15/min), forgot-password (5/5min), imports (5/min), all other routes (120/min)
- **Security Headers**: `SecurityHeadersMiddleware` — X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy, Permissions-Policy on every response
- **CORS**: Restricted to `FRONTEND_URL` env var in production; `["*"]` in development
- **Docs disabled in production**: Set `ENVIRONMENT=production` to disable /docs and /redoc
- **Global exception handler**: No stack traces to clients; 500 returns generic message
- **NoSQL injection prevention**: `re.escape()` applied to ALL $regex queries (15+ locations across 9 files)
- **IDOR fixes**: Customer order `GET /orders/{id}` and subscription cancel verify customer_id ownership
- **CSV formula injection**: `_serialize_val` prefixes =, +, -, @, \t, \r with single quote in all exports
- **File upload security**: 10MB size limit + 5000 row limit on CSV imports
- **HTML sanitization**: `bleach.clean()` with script/style content removal on all article and terms content
- **Brute-force lockout**: 10 failed attempts → 15-minute lockout; admin can unlock via `POST /api/admin/users/{id}/unlock`
- **Password complexity**: Min 10 chars, uppercase, lowercase, number, special char enforced on register
- **Token version**: `token_version` field in user doc; JWT rejected if version mismatch (invalidates old tokens after password change)
- **Audit logging**: API key create/revoke events now logged; login failures logged
- **MongoDB indexes**: 14 compound indexes created on startup for tenant_id + common filter fields

## Feb 2026 — API Documentation Tab

### API Documentation Tab (New)
- Comprehensive "API" tab in admin panel with 26 endpoints documented
- Working "Try It" with API key input field
- Dual auth model explained (JWT + X-API-Key)
- Only active API keys shown in list

### Other Features
- `partner_code` read-only field in My Profile for all users
- Import/Export buttons added to ArticleCategoriesTab and ArticleTemplatesTab
- Backend API expansion: detail-view endpoints for orders, subscriptions
- `X-API-Key` header supported on all public store endpoints

## Feb 2026 — Import/Export System

### Import/Export (All 13 Entities)
- CSV import with upsert (create + update) for all entities
- CSV export with filters for all entities  
- Sample template download per entity
- All imports assign tenant_id from auth (not from CSV)
- Payment provider credential validation (Stripe + GoCardless test calls)
