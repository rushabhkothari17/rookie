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

### Admin Interface
- [x] Products tab with Products/Categories sub-tabs
- [x] "Catalog" renamed to "Products"
- [x] "Quote Requests" renamed to "Requests"
- [x] Bank Transactions module removed
- [x] Customer Portal link in main nav
- [x] Blank category bug fixed in store sidebar

### Cart & Checkout (REDESIGNED 2026-02-25)
- [x] **Two-column layout**: Cart items on left, Order Summary sidebar on right
- [x] **Modern payment method cards**: Bank Transfer (no fee) and Card Payment (5% fee)
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
        │   │   ├── ProductEditor.tsx - Full-screen editor
        │   │   ├── ProductsTab.tsx   - Products/Categories tabs
        │   │   └── CategoriesTab.tsx
        │   ├── store/
        │   │   ├── ProductDetail.tsx - Layout router
        │   │   └── layouts/          - 5 layout components
        │   └── Cart.tsx              - REDESIGNED cart page
        ├── components/
        │   └── Store/
        └── App.tsx
```

## Key Endpoints
- `POST /api/checkout/free` - Free product checkout
- `POST /api/checkout/session` - Stripe checkout
- `POST /api/checkout/bank-transfer` - Bank transfer/GoCardless
- `POST /api/orders/preview` - Cart preview with pricing
- `GET /api/products` - Public product list
- `GET /api/categories` - Product categories

## Database Collections
- `products` - Product catalog with `display_layout` field
- `product_categories` - Categories with blurbs
- `orders` - Order records with `payment_method: "free"` support
- `order_items` - Line items with intake answers
- `invoices` - Payment records

## Completed in Latest Session (2026-02-25)
1. ✅ Fixed "blank category" issue in Store sidebar
2. ✅ Admin sidebar restructured (Products under Commerce, Categories as sub-tab)
3. ✅ Free product checkout backend endpoint
4. ✅ **Cart UI/UX complete redesign**:
   - Two-column layout
   - Modern payment method cards
   - Collapsible promo code
   - Clean empty state
   - Sticky order summary
5. ✅ **Scope ID moved to Cart** (removed from product pages)

## Pending Tasks (P1)
1. Fix "Edit Article" button visibility for non-admin users (recurring bug)
2. Verify complex multi-level visibility logic for intake forms

## Future Tasks (P2)
- Security audit
- Centralized email integration settings
- Credential forms for "Coming Soon" integrations (Gmail, Outlook, HubSpot)

## Test Credentials
- Admin: `admin@automateaccounts.local` / `ChangeMe123!`
- Partner Code: `automate-accounts`

## Test Reports
- `/app/test_reports/iteration_99.json` - Sidebar restructure tests (100% pass)
- `/app/test_reports/iteration_100.json` - Cart redesign tests (100% pass)

---
*Last Updated: 2026-02-25*
