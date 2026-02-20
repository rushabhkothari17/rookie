# Automate Accounts E-Store - Product Requirements Document

## Overview
Production-ready, login-gated e-store for Automate Accounts providing Zoho services including setup, customization, migrations, training, and ongoing support.

## Tech Stack
- **Frontend**: React + TypeScript, TailwindCSS, Shadcn UI
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **Payments**: Stripe (Card), GoCardless (Bank Transfer - MOCKED)
- **Auth**: JWT with email verification

## Core Features

### 1. Authentication & Authorization ✅
- User registration with email verification
- Login with JWT tokens
- Auth-gated store access
- Admin role with elevated permissions
- **Admin Credentials**: admin@automateaccounts.local / ChangeMe123!

### 2. Product Catalog ✅
- 23 products across 6 categories
- Category tabs with horizontal pill navigation
- Product detail pages with pricing breakdown
- Price inputs (selectors, hour pickers, etc.)

### 3. Payment Methods ✅
- **Bank Transfer (GoCardless)** - Default, no fee, MOCKED
  - Creates order with status `awaiting_bank_transfer`
  - Shows confirmation page with instructions
- **Card Payment (Stripe)** - 5% processing fee
  - Only available if admin enables per customer
  - Redirects to Stripe Checkout

### 4. Admin Panel ✅
- **Customers Tab**: View all customers, toggle payment methods (Bank Transfer/Card Payment)
- **Orders Tab**: View all orders with filters (date, product, email)
- **Subscriptions Tab**: Manage subscriptions
- **Catalog Tab**: Edit product content
- **Zoho Sync Logs Tab**: View sync history (mocked)

### 5. Customer Portal ✅
- Personalized welcome message ("Welcome, {Name}")
- One-time orders table with payment method column
- Subscriptions table with renewal dates
- Order details with status tracking

### 6. Store UI/UX ✅
- Premium SaaS design with subtle gradients
- Sticky header with blur effect
- Horizontal category pill tabs
- Modern card design (rounded-3xl, subtle shadow)
- Product cards WITHOUT prices (prices only on detail page)
- "View Details" opens in new tab

## Category Structure
1. Zoho Express Setup
2. Migrate to Zoho (formerly "Migrations")
3. Managed Services (formerly "Ongoing Plans")
4. Build & Automate
5. Accounting on Zoho
6. Audit & Optimize

## Hero Copy
- **Title**: "One Partner, One Roadmap - We've Got Zoho Covered"
- **Subtitle**: "All-in-one Zoho partner for setup, customization, migrations, training and ongoing support."

## Data Models

### Users
```json
{
  "id": "string",
  "email": "string",
  "password_hash": "string",
  "full_name": "string",
  "is_verified": "boolean",
  "is_admin": "boolean"
}
```

### Customers
```json
{
  "id": "string",
  "user_id": "string",
  "company_name": "string",
  "phone": "string",
  "currency": "USD|CAD",
  "allow_bank_transfer": "boolean (default: true)",
  "allow_card_payment": "boolean (default: false)",
  "stripe_customer_id": "string|null"
}
```

### Orders
```json
{
  "id": "string",
  "order_number": "string",
  "customer_id": "string",
  "status": "pending|paid|awaiting_bank_transfer|cancelled",
  "subtotal": "number",
  "fee": "number",
  "total": "number",
  "currency": "USD|CAD",
  "payment_method": "bank_transfer|card",
  "type": "one_time|subscription_start|subscription_renewal"
}
```

## API Endpoints

### Authentication
- `POST /api/auth/register` - User registration
- `POST /api/auth/login` - User login
- `GET /api/auth/verify/{token}` - Email verification

### Products
- `GET /api/products` - List all products
- `GET /api/products/{id}` - Get product details
- `POST /api/pricing/calc` - Calculate pricing

### Checkout
- `POST /api/checkout/session` - Create Stripe checkout session
- `POST /api/checkout/bank-transfer` - Create bank transfer order

### Orders
- `GET /api/orders` - List user's orders
- `POST /api/orders/preview` - Preview cart pricing

### Admin
- `GET /api/admin/customers` - List customers with addresses
- `PUT /api/admin/customers/{id}/payment-methods` - Update payment methods
- `GET /api/admin/orders` - List all orders
- `GET /api/admin/subscriptions` - List all subscriptions

## Completed Work (Feb 20, 2026)
- ✅ Full-stack application setup (React + FastAPI + MongoDB)
- ✅ Authentication with JWT and email verification
- ✅ Product catalog with 23 products across 6 categories
- ✅ Modern UI/UX with premium SaaS design
- ✅ Payment method selection (Bank Transfer / Card)
- ✅ Admin panel with customer payment toggles
- ✅ Portal with welcome personalization and payment columns
- ✅ Bank transfer order flow (mocked)
- ✅ Product cards without prices (only detail page)
- ✅ Category tabs with correct order and naming
- ✅ Store hero copy updated

## Mocked Integrations
- **GoCardless/Bank Transfer**: Creates order with status only, no real payment
- **Zoho CRM & Books**: Creates log entries instead of API calls

## Pending/Future Work
- [ ] Full Zoho CRM & Books integration
- [ ] Real GoCardless integration
- [ ] Subscription renewal order creation on webhook
- [ ] My Profile page implementation
- [ ] Admin order/subscription filtering
- [ ] New products: Fixed-Scope Development, Historical Accounting & Data Cleanup
- [ ] Enterprise pricing dropdown

## Files Reference
- `/app/backend/server.py` - Main backend API
- `/app/frontend/src/App.tsx` - Main router
- `/app/frontend/src/pages/Store.tsx` - Store page
- `/app/frontend/src/pages/Portal.tsx` - Customer portal
- `/app/frontend/src/pages/Admin.tsx` - Admin panel
- `/app/frontend/src/pages/Cart.tsx` - Cart with payment selection
- `/app/frontend/src/pages/BankTransferSuccess.tsx` - Bank transfer confirmation
