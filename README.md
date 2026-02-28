# Automate Accounts — Platform README

> Multi-tenant SaaS admin platform for partner organisations managing customers, products, subscriptions, and documents. Each partner has their own branded storefront and customer portal.

---

## Table of Contents

1. [What This App Does](#1-what-this-app-does)
2. [Architecture Overview](#2-architecture-overview)
3. [User Roles](#3-user-roles)
4. [Running Locally](#4-running-locally)
5. [Environment Variables](#5-environment-variables)
6. [Folder Structure](#6-folder-structure)
7. [Key Features](#7-key-features)
8. [Data Models (MongoDB Collections)](#8-data-models-mongodb-collections)
9. [API Summary](#9-api-summary)
10. [Frontend Pages & Components](#10-frontend-pages--components)
11. [Multi-Tenancy Model](#11-multi-tenancy-model)
12. [3rd Party Integrations](#12-3rd-party-integrations)
13. [Test Credentials](#13-test-credentials)
14. [Backlog](#14-backlog)

---

## 1. What This App Does

Automate Accounts is a **white-label SaaS platform** where a platform operator (Automate Accounts) hosts multiple partner organisations. Each partner gets:

- A **branded admin panel** to manage their own customers, products, orders, and subscriptions
- A **public storefront** at their own domain where their customers browse and purchase services
- A **customer portal** where customers view orders, subscriptions, documents, and their profile
- **Integration connectors** for payments (Stripe, GoCardless), accounting (Zoho Books), CRM (Zoho CRM), email (Zoho Mail, Resend), and cloud storage (Zoho WorkDrive)

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                   Kubernetes Cluster                │
│                                                     │
│  ┌──────────────────┐    ┌───────────────────────┐  │
│  │  React Frontend  │    │   FastAPI Backend      │  │
│  │  (port 3000)     │───▶│   (port 8001)         │  │
│  │  TypeScript      │    │   Python 3.11+        │  │
│  │  ShadCN UI       │    │   Motor (async Mongo) │  │
│  │  Tailwind CSS    │    │                       │  │
│  └──────────────────┘    └──────────┬────────────┘  │
│                                     │               │
│                          ┌──────────▼────────────┐  │
│                          │     MongoDB            │  │
│                          │   (local instance)    │  │
│                          └───────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

**Routing**: Kubernetes ingress proxies `/api/*` → backend (port 8001), everything else → frontend (port 3000).

**Auth**: JWT-based. Login flow: enter partner code → get partner JWT → login with email/password → get user access token.

**Hot reload**: Both frontend (webpack) and backend (uvicorn `--reload`) reload on file save. Supervisor manages both processes.

---

## 3. User Roles

| Role | Access |
|---|---|
| `platform_admin` | Everything — all tenants, all data, platform config |
| `partner_super_admin` | Full access to their own tenant |
| `partner_admin` | Admin panel for their tenant (modules may be restricted) |
| `customer` | Customer portal only (orders, subscriptions, documents, profile) |

Role checks are enforced in `backend/core/tenant.py` via `get_tenant_admin`, `is_platform_admin`, and `require_platform_admin` FastAPI dependencies.

---

## 4. Running Locally

### Prerequisites
- Python 3.11+
- Node.js 18+ and Yarn
- MongoDB running on `localhost:27017`

### Backend
```bash
cd /app/backend
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend
```bash
cd /app/frontend
yarn install
yarn start   # starts on port 3000
```

### Via Supervisor (production-like)
```bash
sudo supervisorctl start all
sudo supervisorctl restart backend   # after .env changes
sudo supervisorctl restart frontend  # after .env changes
```

---

## 5. Environment Variables

### `/app/backend/.env`
```env
MONGO_URL=mongodb://localhost:27017
DB_NAME=test_database
JWT_SECRET=<secret>
ADMIN_EMAIL=admin@automateaccounts.local
ADMIN_PASSWORD=ChangeMe123!
CORS_ORIGINS=*
FRONTEND_URL=https://your-app.preview.emergentagent.com
STRIPE_API_KEY=sk_test_...
GOCARDLESS_ACCESS_TOKEN=...
```

### `/app/frontend/.env`
```env
REACT_APP_BACKEND_URL=https://your-app.preview.emergentagent.com
WDS_SOCKET_PORT=443
```

> **Important**: `REACT_APP_BACKEND_URL` must always be the external URL (not `localhost`) — the Kubernetes ingress routes `/api/*` to the backend automatically.

---

## 6. Folder Structure

```
/app/
├── backend/
│   ├── server.py                   # FastAPI app, all routers registered here
│   ├── models.py                   # All Pydantic request/response models
│   ├── core/
│   │   ├── tenant.py               # Multi-tenancy helpers, role dependencies
│   │   ├── security.py             # JWT auth, get_current_user
│   │   └── helpers.py              # make_id(), now_iso(), formatting utils
│   ├── db/
│   │   └── session.py              # Motor async MongoDB client (db object)
│   ├── routes/
│   │   ├── auth.py                 # Login, register, password reset, JWT
│   │   ├── store.py                # Public store, product visibility, pricing calc
│   │   ├── checkout.py             # Stripe/GoCardless/bank-transfer checkout
│   │   ├── orders.py               # Customer order history
│   │   ├── webhooks.py             # Inbound Stripe/GoCardless webhooks
│   │   └── admin/
│   │       ├── catalog.py          # Product & category CRUD
│   │       ├── customers.py        # Customer management
│   │       ├── orders.py           # Admin order management + refunds
│   │       ├── subscriptions.py    # Subscription management
│   │       ├── users.py            # Admin user management
│   │       ├── website.py          # Website/org settings, signup form schema
│   │       ├── tenants.py          # Partner tenant management (platform admin)
│   │       ├── integrations.py     # Payment/email/CRM integration config
│   │       ├── forms.py            # Custom enquiry form CRUD
│   │       ├── integration_requests.py  # Partner integration request submissions
│   │       ├── finance.py          # Zoho Books sync
│   │       ├── permissions.py      # Roles & permission modules
│   │       └── ...                 # (18 more admin route files)
│   ├── services/
│   │   ├── pricing_service.py      # Intake question pricing engine
│   │   ├── pricing_pdf.py          # Quote PDF generation (ReportLab)
│   │   └── ...
│   └── models/
│       └── form.py                 # Form & FormSubmission models
│
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── Admin.tsx           # Admin panel shell — sidebar + all tabs
│       │   ├── ProductEditor.tsx   # Full-page product create/edit + card preview
│       │   ├── ProductDetail.tsx   # Customer-facing product detail + checkout
│       │   ├── admin/
│       │   │   ├── ProductForm.tsx          # Product form (all tabs)
│       │   │   ├── IntakeSchemaBuilder.tsx  # Drag-and-drop pricing question builder
│       │   │   ├── IntegrationsOverview.tsx # Connect Services page
│       │   │   ├── CustomersTab.tsx
│       │   │   ├── OrdersTab.tsx
│       │   │   ├── ProductsTab.tsx
│       │   │   ├── SubscriptionsTab.tsx
│       │   │   ├── RolesTab.tsx
│       │   │   ├── FormsManagementTab.tsx   # Custom enquiry forms
│       │   │   ├── EnquiriesTab.tsx         # Enquiry submissions + PDF
│       │   │   └── tabs/
│       │   │       └── IntegrationRequestsTab.tsx
│       │   ├── store/
│       │   │   └── layouts/        # Product card layouts (Classic, Showcase, Application, Wizard)
│       │   ├── auth/               # Login, Signup, ForgotPassword
│       │   └── customer/           # Profile, Documents, Orders portal
│       ├── components/
│       │   ├── OfferingCard.tsx     # Store card component (used in grid + preview)
│       │   ├── ui/                 # ShadCN components
│       │   └── admin/              # Admin-specific components
│       ├── contexts/
│       │   ├── AuthContext.tsx      # User auth state
│       │   └── WebsiteContext.tsx   # Tenant website settings
│       ├── hooks/
│       │   ├── useCountries.ts      # Fetches countries from /api/utils/countries
│       │   └── useAuth.ts
│       └── lib/
│           └── api.ts              # Axios instance (auto-attaches JWT + partner token)
│
└── memory/
    ├── PRD.md                      # Full product requirements + all feature history
    ├── API_DOCS.md                 # Complete API reference (35 sections)
    ├── CHANGELOG.md                # Date-stamped session changelog
    └── SECURITY_AUDIT_CHECKLIST.md
```

---

## 7. Key Features

### Admin Panel (Partner)
| Section | Features |
|---|---|
| **Products** | Create/edit products with rich intake question builder, pricing rules (flat, tiered, formula, multiply), store card customisation, custom sections, visibility conditions per customer segment |
| **Customers** | List, create, edit customers; notes; address management; payment method history |
| **Orders** | View, update, refund orders; manual order creation; CSV export |
| **Subscriptions** | Manage Stripe subscriptions; force renew; cancel |
| **Enquiries** | View scope/enquiry submissions; PDF download; status tracking |
| **Organisations** | Store name, logo, brand colours, base currency, billing address |
| **Taxes** | Tax rates by country; used to populate country dropdowns across the app |
| **Forms** | Build custom enquiry forms and attach to products |
| **Connect Services** | Configure Stripe, GoCardless, Zoho CRM/Books/Mail, Resend, WorkDrive |
| **Integration Requests** | Partners submit integration requests; platform admin manages status + notes |
| **Email Templates** | Customise transactional email bodies |
| **Articles & Resources** | Create documents/content scoped to specific customers |
| **Roles** | Custom role creation with module-level access control |
| **API Keys** | Generate/revoke tenant API keys |
| **Webhooks** | Configure outbound webhooks for order/subscription events |

### Public Storefront
- Product grid with category filtering and search
- 5 product page layouts: Classic, QuickBuy, Wizard, Application, Showcase
- Dynamic intake question forms that affect pricing in real-time
- Promo code support
- Multi-currency with live FX rates (exchangerate-api.com, 1-hour cache)
- Product visibility rules based on customer profile fields (country, company, email, status)

### Customer Portal
- Order history with status tracking
- Active subscriptions with cancellation
- Document library (upload/download via Zoho WorkDrive)
- Profile management with schema-driven required fields

### Pricing Engine (`backend/services/pricing_service.py`)
Supports per-question pricing on products:
- **Flat add/subtract** — fixed amount added per selection
- **Multiply** — multiplies the running subtotal (e.g. ×1.5 for urgent)
- **Per-unit** — price × quantity input
- **Tiered** — different rates for different volume bands
- **Formula** — custom expression like `{qty} * {rate}`
- **Price ceiling cap** — hard maximum after all calculations
- **Rounding** — nearest £1, £5, £10, nearest 99p, always up/down

---

## 8. Data Models (MongoDB Collections)

| Collection | Key Fields |
|---|---|
| `tenants` | `id, name, partner_code, is_active, address{}, base_currency` |
| `users` | `id, tenant_id, email, role, full_name, phone, must_change_password` |
| `customers` | `id, tenant_id, user_id, company_name, allow_card_payment` |
| `addresses` | `id, customer_id, line1, city, region, postal, country` |
| `products` | `id, tenant_id, name, base_price, pricing_type, intake_schema_json{}, card_tag, card_description, card_bullets[], visibility_conditions{}, show_price_breakdown, price_rounding, enquiry_form_id` |
| `orders` | `id, tenant_id, customer_id, type(order/scope_request), status, total, currency, base_currency, base_currency_amount, payment_method` |
| `subscriptions` | `id, tenant_id, customer_id, product_id, status, stripe_subscription_id, current_period_end` |
| `website_settings` | `id, tenant_id, store_name, logo_url, brand_color, signup_form_schema{}, scope_form_schema{}` |
| `oauth_connections` | `id, tenant_id, provider, credentials{}, is_validated, settings{}` |
| `app_settings` | `id, tenant_id, key, value` — key/value store for per-tenant config |
| `tenant_forms` | `id, tenant_id, name, form_schema{}` |
| `integration_requests` | `id, tenant_id, partner_code, integration_name, status, notes[], contact_email, contact_phone` |
| `admin_roles` | `id, tenant_id, name, access_level, modules[]` |
| `addresses` | `id, customer_id, line1, line2, city, region, postal, country` |
| `articles` | `id, tenant_id, title, content, visible_to_customers[], ...` |
| `audit_logs` | `id, tenant_id, entity_type, entity_id, action, user_id, diff{}` |

---

## 9. API Summary

All routes prefixed `/api`. Full reference in `/app/memory/API_DOCS.md`.

### Auth
```
POST /api/auth/partner          → get partner JWT from partner code
POST /api/auth/login            → user login → access token
GET  /api/me                    → current user profile
PUT  /api/auth/change-password  → forced password change
```

### Public Store
```
GET  /api/products              → list visible products (applies visibility rules)
GET  /api/products/{id}         → single product
POST /api/pricing/calc          → calculate price from intake answers
POST /api/orders/scope-request  → submit an enquiry
POST /api/checkout/session      → create Stripe checkout
POST /api/checkout/bank-transfer → bank transfer order
POST /api/checkout/free         → free (£0) order
```

### Admin (requires Bearer token)
```
GET/POST/PUT     /api/admin/products
GET/POST/PUT/DEL /api/admin/categories
GET/POST/PUT     /api/admin/customers
GET/POST/PUT/DEL /api/admin/orders
GET/POST/PUT/DEL /api/admin/subscriptions
GET/POST/PUT/DEL /api/admin/forms
GET/POST         /api/integration-requests
PUT              /api/integration-requests/{id}/status
POST             /api/integration-requests/{id}/notes
GET              /api/admin/integrations/status
GET              /api/admin/tenants     (platform admin only)
```

---

## 10. Frontend Pages & Components

| Route | Component | Description |
|---|---|---|
| `/` | `StorePage` | Public product grid |
| `/products/:id` | `ProductDetail.tsx` | Product page with intake form + checkout |
| `/login` | `Login.tsx` | Partner code → user login with force-change modal |
| `/signup` | `Signup.tsx` | Schema-driven customer registration |
| `/admin` | `Admin.tsx` | Admin panel (all tabs via sidebar) |
| `/admin/products/new` | `ProductEditor.tsx` | Create product |
| `/admin/products/:id/edit` | `ProductEditor.tsx` | Edit product + live card preview |
| `/orders` | `OrdersPage` | Customer order history |
| `/subscriptions` | `SubscriptionsPage` | Customer subscriptions |
| `/documents` | `DocumentsPage` | Customer document portal |
| `/profile` | `Profile.tsx` | Customer profile |

### Admin Panel Tabs
```
PLATFORM:     Partner Orgs
PEOPLE:       Users · Roles · Customers
COMMERCE:     Products · Subscriptions · Orders · Enquiries
CONTENT:      Resources · Documents
SETTINGS:     Organization Info · Taxes · Auth & Pages · Forms · Email Templates · References · Custom Domains
INTEGRATIONS: Connect Services · Integration Requests (platform admin) · API · Webhooks · Logs
```

---

## 11. Multi-Tenancy Model

Every request is scoped to a tenant via:

1. **Partner code** — passed as `X-Partner-Code` header or resolved from the custom domain
2. **JWT claims** — the access token embeds `tenant_id`
3. **DB filter** — every query uses `{"tenant_id": tid}` via `get_tenant_filter(user)` from `core/tenant.py`

Platform admins bypass tenant scoping and can view/edit all tenants. They can also "view as tenant" by passing `X-View-As-Tenant: {tenant_id}`.

---

## 12. 3rd Party Integrations

| Service | Purpose | Status |
|---|---|---|
| **Stripe** | Card payments + subscriptions | Live |
| **GoCardless** | Direct Debit payments | Live |
| **Zoho Mail** | Transactional emails | Live |
| **Resend** | Alternative transactional email | Live |
| **Zoho CRM** | Customer sync | Live |
| **Zoho Books** | Order/invoice sync | Live |
| **Zoho WorkDrive** | Customer document storage | Live |
| **exchangerate-api.com** | FX rate conversion | Live |
| **Google Drive** | Cloud storage alternative | Coming Soon |
| **OneDrive** | Cloud storage alternative | Coming Soon |

---

## 13. Test Credentials

| Role | Email | Password | Notes |
|---|---|---|---|
| Platform Admin | `admin@automateaccounts.local` | `ChangeMe123!` | Partner code: `automate-accounts` |
| Partner Admin | `admin@bright-accounting.local` | `ChangeMe123!` | Partner code: `bright-accounting` |
| Test Partner | `TEST_valid_iter133@test.local` | `ChangeMe123!` | Code: `test-org-iter133-valid` |

---

## 14. Backlog

### P1 — High Priority
- Google Drive & OneDrive cloud storage integration (tiles exist, marked "Coming Soon")
- Centralise all email integration settings into a single tab

### P2 — Medium Priority
- Customer Portal: self-service subscription cancellation, renewal date display, Reorder button
- Email notifications to partners when integration request status changes

### P3 — Future
- Security audit / penetration testing
- Comprehensive unit test coverage
- Mobile app version of customer portal
