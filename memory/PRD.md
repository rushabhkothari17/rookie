# AutomateAccounts Product Requirements Document

## Original Problem Statement
E-commerce platform for professional services with:
- Product catalog with multiple pricing tiers
- Intake forms with conditional logic
- Multiple product page layouts (Classic, QuickBuy, Wizard, Application, Showcase)
- Full-screen admin product editor
- Payment processing (Stripe, GoCardless, Bank Transfer)
- Free product checkout support
- Modern cart experience

## Core Features Implemented

### Product Management
- [x] 5 distinct product page layouts (Classic, QuickBuy, Wizard, Application, Showcase)
- [x] Full-screen product editor at `/admin/products/:id/edit`
- [x] Dynamic layout selection per product
- [x] Advanced intake forms with conditional visibility
- [x] Tiered pricing engine with formulas

### Admin Interface (RESTRUCTURED 2026-02-25)
- [x] **Products tab** now contains: Products, Categories, Promo Codes, Terms (as sub-tabs)
- [x] **Articles tab** now contains: Articles, Templates, Email Templates, Categories, Override Codes (as sub-tabs)
- [x] **Main sidebar** updated:
  - PEOPLE: Users, Customers
  - COMMERCE: Products, Subscriptions, Orders, Requests
  - CONTENT: Articles, Email Templates, References
  - SETTINGS: Website Content, Custom Domains
  - INTEGRATIONS: Connect Services, API, Webhooks, Logs
- [x] **Website Content** streamlined:
  - Removed Payments section (keep in Connected Services)
  - Removed Bank Transaction Form from Forms
  - Removed Email Templates, References, Custom Domains (moved to sidebar)
- [x] Bank Transactions module fully removed

### Cart & Checkout (REDESIGNED 2026-02-25)
- [x] **Two-column layout**: Cart items on left, Order Summary sidebar on right
- [x] **Modern payment method cards**: Bank Transfer (no fee) and Card Payment (5% fee)
- [x] **Increased spacing** between sections (space-y-8, gap-10)
- [x] **Collapsible promo code section**
- [x] **Clean empty cart state** with shopping cart icon and Browse CTA
- [x] **Scope ID validation in Cart** (moved from product pages)
- [x] Free product checkout (total = $0, no payment required)
- [x] Multiple payment methods (Card, Bank Transfer, GoCardless)
- [x] Terms & Conditions acceptance

### Store
- [x] Category sidebar with blurbs
- [x] Blank category filtering (fixed)
- [x] Product search and filters

## Architecture

```
/app/
├── backend/
│   ├── routes/
│   │   ├── catalog.py      - Product CRUD
│   │   ├── checkout.py     - All checkout endpoints including /checkout/free
│   │   ├── store.py        - Public store APIs
│   │   └── uploads.py      - File handling
│   ├── services/
│   │   └── pricing_service.py - Tiered pricing calculations
│   └── server.py
└── frontend/
    └── src/
        ├── pages/
        │   ├── admin/
        │   │   ├── ProductsTab.tsx   - Products/Categories/Promo/Terms tabs
        │   │   ├── ArticlesTab.tsx   - Articles/Templates/Email/Categories/Override tabs
        │   │   ├── WebsiteTab.tsx    - Streamlined (removed payments, references, etc.)
        │   │   ├── EmailTemplatesTab.tsx - NEW standalone tab
        │   │   ├── ReferencesTab.tsx - NEW standalone tab
        │   │   ├── CustomDomainsTab.tsx - NEW standalone tab
        │   │   └── CategoriesTab.tsx
        │   ├── store/
        │   │   ├── ProductDetail.tsx - Layout router
        │   │   └── layouts/          - 5 layout components
        │   ├── Cart.tsx              - REDESIGNED with increased spacing
        │   └── ProductEditor.tsx     - Fixed API endpoint
        ├── components/
        │   └── Store/
        └── App.tsx
```

## Key Endpoints
- `POST /api/checkout/free` - Free product checkout
- `POST /api/checkout/session` - Stripe checkout
- `POST /api/checkout/bank-transfer` - Bank transfer/GoCardless
- `POST /api/orders/preview` - Cart preview with pricing
- `GET /api/admin/products-all` - Admin products list
- `GET /api/products` - Public product list
- `GET /api/categories` - Product categories

## Database Collections
- `products` - Product catalog with `display_layout` field
- `product_categories` - Categories with blurbs
- `orders` - Order records with `payment_method: "free"` support
- `order_items` - Line items with intake answers
- `invoices` - Payment records

## Completed in Latest Session (2026-02-25)
1. ✅ Cart UI/UX complete redesign
2. ✅ Scope ID moved to Cart (from product pages)
3. ✅ **Admin UI restructured**:
   - Products tab: +Promo Codes, +Terms sub-tabs
   - Articles tab: +Override Codes sub-tab
   - Main sidebar: +Email Templates, +References, +Custom Domains
   - Website Content: -Payments, -Bank Transaction Form, -Email, -References, -Domains
4. ✅ Product editing fixed (API endpoint corrected)
5. ✅ Cart spacing increased

## Completed in Latest Session (2026-02-26) — Auth Gateway
1. ✅ **Auth Gateway Flow**: `/login` is now a two-step gateway. Step 1: neutral platform screen (no partner branding), enter partner code → validate against `/api/tenant-info`. Step 2: partner branding applied (logo, colors, store name), shows sign in form. Partner code persists in `localStorage` as `aa_partner_code`.
2. ✅ **Signup + ForgotPassword protected**: Both pages now read `aa_partner_code` from localStorage. If missing, they redirect to `/login` (the gateway). Partner code field removed from both forms. Partner badge shown with "Change" link.
3. ✅ **Dynamic branding**: `applyPartnerBranding(code)` exported from `WebsiteContext` fetches & applies partner CSS variables on-the-fly. `WebsiteContext` also auto-loads partner branding on mount if code is stored.
4. ✅ **All 11/11 frontend tests passed** by testing agent.

## Pending Tasks (P1)
1. Fix "Edit Article" button visibility for non-admin users (recurring bug)

## Future Tasks (P2)
- Security audit
- Centralized email integration settings
- Credential forms for "Coming Soon" integrations

## Test Credentials
- Admin: `admin@automateaccounts.local` / `ChangeMe123!`
- Partner Code: `automate-accounts`

## Test Reports
- `/app/test_reports/iteration_99.json` - Sidebar restructure tests (100% pass)
- `/app/test_reports/iteration_100.json` - Cart redesign tests (100% pass)
- `/app/test_reports/iteration_101.json` - Admin UI restructuring tests (100% pass)

---
*Last Updated: 2026-02-25*
