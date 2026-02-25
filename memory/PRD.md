# AutomateAccounts Product Requirements Document

## Original Problem Statement
E-commerce platform for professional services with:
- Product catalog with multiple pricing tiers
- Intake forms with conditional logic
- Multiple product page layouts (Classic, QuickBuy, Wizard, Application, Showcase)
- Full-screen admin product editor
- Payment processing (Stripe, GoCardless, Bank Transfer)
- Free product checkout support

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

### Checkout
- [x] Free product checkout (total = $0, no payment required)
- [x] Multiple payment methods (Card, Bank Transfer, GoCardless)
- [x] Promo codes
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
        │   └── store/
        │       ├── ProductDetail.tsx - Layout router
        │       └── layouts/          - 5 layout components
        ├── components/
        │   └── Store/
        └── App.tsx
```

## Key Endpoints
- `POST /api/checkout/free` - Free product checkout
- `POST /api/checkout/session` - Stripe checkout
- `POST /api/checkout/bank-transfer` - Bank transfer/GoCardless
- `GET /api/products` - Public product list
- `GET /api/categories` - Product categories

## Database Collections
- `products` - Product catalog with `display_layout` field
- `product_categories` - Categories with blurbs
- `orders` - Order records with `payment_method: "free"` support
- `order_items` - Line items with intake answers
- `invoices` - Payment records

## Pending Tasks (P0-P1)
1. Cart UI/UX redesign
2. Move Scope ID validation to Checkout page (for enquiry products)
3. Fix "Edit Article" button visibility for non-admin users

## Future Tasks (P2)
- Complex visibility logic verification (AND/OR conditions)
- Security audit
- Centralized email integration settings

## Test Credentials
- Admin: `admin@automateaccounts.local` / `ChangeMe123!`
- Partner Code: `automate-accounts`

---
*Last Updated: 2026-02-25*
