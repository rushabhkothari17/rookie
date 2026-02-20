# Automate Accounts E-Store PRD
Date: 2026-02-20

## Original Problem Statement
Build a login-gated Automate Accounts e-store with authentication, currency rules, Stripe checkout (one-time + subscriptions), dynamic pricing calculators, customer portal tables, and admin ops tools. Zoho CRM/Books integrations were required in the full spec but are deferred and MOCKED for this phase. MongoDB is approved in place of Postgres. Build locally only.

## Architecture Summary
- Frontend: React + TypeScript (CRA + CRACO)
- Backend: FastAPI (Python)
- DB: MongoDB
- Payments: Stripe Checkout via emergentintegrations
- Email: MOCKED via email_outbox collection
- Zoho Sync: MOCKED via zoho_sync_logs

## User Personas
- Customer (US/CA): buys one-time services or subscriptions
- Ops Admin: manages catalog content, orders, customers, sync logs, currency overrides

## Core Requirements (Static)
- JWT auth with email verification (enforced)
- Currency by country (USD/CAD only), lock after first purchase
- Product catalog with calculators + marketing copy
- Cart + Stripe checkout + 5% fee
- Customer portal orders/subscriptions tables
- Admin portal for ops + catalog edits

## Implemented (2026-02-20)
- Auth: signup/login/verify (email delivery MOCKED)
- Storefront: category-first navigation, product detail pages, calculators
- Cart: mixed handling, scope requests, external checkout for Zoho Books migration
- Stripe: one-time Checkout sessions; subscription sessions require Stripe price IDs
- Webhooks: idempotent logging + mocked email notifications for invoice.paid/payment_failed
- Customer portal: orders + subscriptions tables
- Admin portal: customers/orders/subscriptions, catalog edit, currency override, order notes
- Zoho sync logs with retry (MOCKED)

## Prioritized Backlog
### P0
- Configure Stripe price IDs for subscription products
- Real email delivery provider integration
- Zoho CRM/Books integration (contacts, deals, invoices)

### P1
- Subscription lifecycle sync (cancel_at_period_end, updates) from webhook events
- Admin search/filter on customers/orders

### P2
- CI/CD + Azure infra, Docker Compose for local dev
- GoCardless phase-2 toggle

## Next Tasks
1. Add real email provider and verification link flow
2. Integrate Zoho CRM/Books with idempotent sync
3. Set Stripe price IDs for subscription products in admin
