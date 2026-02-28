# AutomateAccounts — API Reference

> All routes are prefixed with `/api` via the Kubernetes ingress (e.g. `/api/auth/login`).  
> **Auth header**: `Authorization: Bearer <jwt_token>` unless marked _Public_.  
> **Partner header** (where noted): `x-partner-token: <partner_jwt>` — obtained from `POST /api/auth/partner`.  
> Last updated: 2026-02-27

---

## Table of Contents
1. [Authentication & Identity](#1-authentication--identity)
2. [Public Store](#2-public-store)
3. [Checkout](#3-checkout)
4. [Admin — Catalog (Products & Categories)](#4-admin--catalog-products--categories)
5. [Admin — Customers](#5-admin--customers)
6. [Admin — Orders](#6-admin--orders)
7. [Admin — Enquiries](#7-admin--enquiries)
8. [Admin — Subscriptions](#8-admin--subscriptions)
9. [Admin — Users](#9-admin--users)
10. [Admin — Promo Codes](#10-admin--promo-codes)
11. [Admin — Terms & Conditions](#11-admin--terms--conditions)
12. [Admin — References](#12-admin--references)
13. [Admin — Settings & Website](#13-admin--settings--website)
14. [Admin — Integrations](#14-admin--integrations)
15. [Admin — Finance (Zoho Books)](#15-admin--finance-zoho-books)
16. [Admin — Webhooks](#16-admin--webhooks)
17. [Admin — Exports & Imports](#17-admin--exports--imports)
18. [Admin — API Keys](#18-admin--api-keys)
19. [Admin — Taxes](#19-admin--taxes)
20. [Admin — Tenants & Custom Domains](#20-admin--tenants--custom-domains)
21. [Admin — GDPR](#21-admin--gdpr)
22. [Admin — Audit Logs](#22-admin--audit-logs)
23. [Admin — Email Templates](#23-admin--email-templates)
24. [Admin — Documents](#24-admin--documents)
25. [Admin — Integration Requests](#25-admin--integration-requests)
26. [Content — Articles](#26-content--articles)
27. [Content — Article Categories](#27-content--article-categories)
28. [Content — Article Templates](#28-content--article-templates)
29. [Content — Article Email Templates](#29-content--article-email-templates)
30. [Content — Resources](#30-content--resources)
31. [Content — Resource Categories](#31-content--resource-categories)
32. [Content — Resource Templates](#32-content--resource-templates)
33. [Content — Resource Email Templates](#33-content--resource-email-templates)
34. [Webhooks (Inbound)](#34-webhooks-inbound)
35. [OAuth / CRM](#35-oauth--crm)
36. [Uploads & Downloads](#36-uploads--downloads)
37. [GDPR — Customer Self-Service](#37-gdpr--customer-self-service)

---

## 1. Authentication & Identity

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/api/` | Public | Health check |
| `GET`  | `/api/tenant-info` | Public | Tenant branding and settings for a domain |
| `GET`  | `/api/auth/domain-info` | Public | Resolve partner info from `?domain=` query param |
| `POST` | `/api/auth/partner` | Public | Exchange partner code → partner JWT. Body: `{ partner_code }` |
| `POST` | `/api/auth/partner-login` | Public | Alias for partner JWT exchange |
| `POST` | `/api/auth/customer-login` | Public | Customer login using partner JWT header |
| `POST` | `/api/auth/domain-login` | Public | Login via custom domain (auto-resolves partner) |
| `POST` | `/api/auth/login` | Partner JWT | Admin/user login. Body: `{ email, password }` |
| `POST` | `/api/auth/logout` | Bearer | Invalidate session |
| `POST` | `/api/auth/refresh` | Bearer | Refresh access token |
| `POST` | `/api/auth/register-partner` | Public | Register a new partner/tenant. Body: `{ partner_code, company_name, email, password, ... }` |
| `POST` | `/api/auth/register` | Partner JWT | Customer self-registration. Body: `{ email, password, full_name, ... }` |
| `POST` | `/api/auth/resend-verification-email` | Partner JWT | Re-send email verification |
| `POST` | `/api/auth/verify-email` | Partner JWT | Verify email token. Body: `{ token }` |
| `POST` | `/api/auth/forgot-password` | Partner JWT | Send password-reset email. Body: `{ email }` |
| `POST` | `/api/auth/reset-password` | Partner JWT | Reset password with token. Body: `{ token, new_password }` |
| `GET`  | `/api/me` | Bearer | Get current user profile |
| `PUT`  | `/api/me` | Bearer | Update profile. Body: `UpdateProfileRequest` fields |

### Key Models

**`UpdateProfileRequest`**
```json
{
  "full_name": "string",
  "phone": "string",
  "address": { "line1": "string", "city": "string", "country": "string", "postcode": "string", "region": "string" }
}
```

---

## 2. Public Store

All routes are public (no auth required unless the product has restricted visibility). Partner JWT header required.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/api/categories` | Public | List active product categories |
| `GET`  | `/api/products` | Public | List visible products. Supports `?category=`, `?layout=`, `?search=`. Applies `visibility_conditions` filtering |
| `GET`  | `/api/products/{product_id}` | Public/Bearer | Get single product by `id` or `slug`. Enforces visibility for both auth and anon users |
| `POST` | `/api/pricing/calc` | Public | Calculate price for intake form answers. Body: `PricingCalcRequest` |
| `GET`  | `/api/terms` | Public | List active terms documents |
| `GET`  | `/api/terms/default` | Public | Get the default terms document |
| `GET`  | `/api/terms/{terms_id}` | Public | Get specific terms document |
| `GET`  | `/api/terms/for-product/{product_id}` | Public | Get terms linked to a product |
| `POST` | `/api/promo-codes/validate` | Bearer | Validate a promo code. Body: `{ code, product_ids: [] }` |
| `POST` | `/api/orders/preview` | Bearer | Preview order totals with discounts/FX. Body: `OrderPreviewRequest` |
| `POST` | `/api/orders/scope-request` | Bearer | Submit an enquiry (scope request) from the cart. Formerly "quote request" |
| `POST` | `/api/orders/scope-request-form` | Public/Bearer | Submit an enquiry with embedded intake form data |
| `GET`  | `/api/orders` | Bearer | Get customer's own orders. Filter: `?status=`, `?page=`, `?per_page=` |
| `GET`  | `/api/orders/{order_id}` | Bearer | Get a specific order |
| `GET`  | `/api/subscriptions` | Bearer | List customer's active subscriptions |
| `POST` | `/api/subscriptions/{subscription_id}/cancel` | Bearer | Cancel a subscription. Body: `{ reason? }` |
| `GET`  | `/api/references` | Public | Get all `{ref:key}` reference variables for the tenant (used in articles, emails) |

### Product Visibility (`visibility_conditions`)

As of v2, products support **nested grouped conditional visibility** based on customer profile fields:

```json
{
  "top_logic": "AND",
  "groups": [
    {
      "logic": "AND",
      "conditions": [
        { "field": "country", "operator": "equals", "value": "United Kingdom" }
      ]
    }
  ]
}
```

**Operators**: `equals`, `not_equals`, `contains`, `not_contains`, `empty`, `not_empty`  
**Customer fields**: `country`, `company_name`, `email`, `status`, `state_province`, `phone`

Backward-compatible: legacy flat `{ "logic": "AND", "conditions": [...] }` is still evaluated correctly.

### Cart Validation Rules
- Cannot mix `one-time` and `subscription` products in the same cart
- Cannot mix products with different `currency` values
- Cart is cleared on conflict (user shown an error message)

### Key Models

**`PricingCalcRequest`**
```json
{
  "product_id": "string",
  "answers": { "question_key": "value" },
  "quantity": 1
}
```

**`OrderPreviewRequest`**
```json
{
  "items": [{ "product_id": "string", "quantity": 1, "answers": {}, "promo_code": "string?" }]
}
```

**`ScopeRequestBody`** (for `/orders/scope-request`)
```json
{
  "items": [{ "product_id": "string", "quantity": 1, "answers": {} }],
  "message": "string"
}
```

**`ScopeRequestFormData`** (for `/orders/scope-request-form`)
```json
{
  "product_id": "string",
  "answers": { "key": "value" },
  "message": "string",
  "extra_fields": { "key": "value" }
}
```

---

## 3. Checkout

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/checkout/session` | Bearer | Create a Stripe checkout session. Returns `{ session_id, url }` |
| `GET`  | `/api/checkout/status/{session_id}` | Bearer | Poll Stripe session status. Returns `{ status, order_id }` |
| `POST` | `/api/checkout/bank-transfer` | Bearer | Initiate a bank transfer order. Returns `{ order_id, reference }` |
| `POST` | `/api/checkout/free` | Bearer | Complete a free (£0) order instantly |

### FX / Multi-Currency

Every order and subscription stores:
- `currency` — the product's transaction currency (e.g. `"GBP"`)
- `base_currency` — the tenant's base/reporting currency (e.g. `"USD"`)
- `base_currency_amount` — the order total converted to base currency at the time of purchase

FX rates are fetched from `exchangerate-api.com` with a **1-hour TTL cache**.

### Key Models

**`CheckoutSessionRequestBody`**
```json
{
  "items": [{ "product_id": "string", "quantity": 1, "answers": {} }],
  "promo_code": "string?",
  "success_url": "string",
  "cancel_url": "string",
  "extra_fields": {}
}
```

**`BankTransferCheckoutRequest`**
```json
{
  "items": [{ "product_id": "string", "quantity": 1, "answers": {} }],
  "promo_code": "string?",
  "extra_fields": {},
  "terms_accepted": true
}
```

---

## 4. Admin — Catalog (Products & Categories)

All routes require **admin JWT**.

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/admin/products-all` | List ALL products (including inactive). Supports `?status=`, `?category=`, `?search=` |
| `POST` | `/api/admin/products` | Create a new product |
| `PUT`  | `/api/admin/products/{product_id}` | Update a product (all fields) |
| `GET`  | `/api/admin/products/{product_id}/logs` | Audit log for a product |
| `PUT`  | `/api/admin/products/{product_id}/terms` | Assign a terms document to a product |
| `GET`  | `/api/admin/categories` | List all categories |
| `POST` | `/api/admin/categories` | Create a category |
| `PUT`  | `/api/admin/categories/{cat_id}` | Update a category |
| `DELETE` | `/api/admin/categories/{cat_id}` | Delete a category |
| `GET`  | `/api/admin/categories/{cat_id}/logs` | Audit log for a category |

### Product Fields (`AdminProductCreate` / `AdminProductUpdate`)

```json
{
  "name": "string",
  "slug": "string",
  "description": "string",
  "status": "active | inactive | coming_soon",
  "layout": "classic | quickbuy | wizard | application | showcase",
  "pricing_type": "internal | external | enquiry",
  "currency": "GBP",
  "price": 100.00,
  "is_subscription": false,
  "stripe_price_id": "price_...",
  "category_id": "string?",
  "visible_to_customers": [],
  "restricted_to": [],
  "visibility_conditions": {
    "top_logic": "AND",
    "groups": [{ "logic": "AND", "conditions": [{ "field": "country", "operator": "equals", "value": "UK" }] }]
  },
  "intake_schema": {
    "questions": [],
    "layout": "standard | wizard"
  },
  "custom_sections": [],
  "bullets": [],
  "images": [],
  "terms_id": "string?"
}
```

**`is_subscription`**: `false` = One-time payment (default), `true` = Recurring subscription (requires `stripe_price_id`)

**`pricing_type`**:
- `internal` — price managed here, checkout via Stripe/GoCardless/Bank Transfer
- `external` — shows an external URL button (no internal checkout)
- `enquiry` — adds to a scope/enquiry request, no direct payment

**`visibility_conditions`** (optional, `null` = visible to everyone):
- Legacy flat format still supported: `{ "logic": "AND", "conditions": [...] }`
- New grouped format: `{ "top_logic": "AND", "groups": [{ "logic": "AND", "conditions": [...] }] }`

### Intake Question Schema

Each question in `intake_schema.questions`:

```json
{
  "id": "string",
  "key": "string",
  "type": "text | number | boolean | dropdown | multiselect | formula | date | file | html_block",
  "label": "string",
  "helper_text": "string",
  "tooltip_text": "string?",
  "required": true,
  "enabled": true,
  "affects_price": false,
  "step_group": 0,
  "options": [{ "label": "string", "value": "string", "price_value": 0 }],
  "price_per_unit": 0,
  "price_formula": "multiply | add",
  "price_mode": "flat | tiered | none | add | multiply",
  "tiers": [{ "up_to": 10, "price": 5.0 }],
  "price_if_yes": 0,
  "price_if_no": 0,
  "formula_expression": "{qty} * {rate}",
  "date_format": "YYYY-MM-DD",
  "accept_types": ".pdf,.docx",
  "max_size_mb": 10,
  "content": "<p>HTML content</p>",
  "visibility_rule": {
    "top_logic": "AND",
    "groups": [{ "logic": "AND", "conditions": [{ "depends_on": "question_key", "operator": "equals", "value": "yes" }] }]
  }
}
```

**`visibility_rule`** (intake questions): show/hide based on answers to other questions.  
Operators: `equals`, `not_equals`, `greater_than`, `less_than`, `contains`, `not_contains`, `not_empty`, `empty`

---

## 5. Admin — Customers

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/admin/customers` | List customers. Returns `{ customers[], users[], addresses[], total, page, per_page, total_pages }` |
| `POST` | `/api/admin/customers/create` | Manually create a customer + linked user |
| `PUT`  | `/api/admin/customers/{customer_id}` | Update customer details |
| `PATCH`| `/api/admin/customers/{customer_id}/active` | Enable/disable a customer account |
| `PUT`  | `/api/admin/customers/{customer_id}/payment-methods` | Update saved payment methods |
| `PUT`  | `/api/admin/customers/{customer_id}/partner-map` | Map customer to a different partner |
| `GET`  | `/api/admin/customers/{customer_id}/logs` | Audit log |
| `GET`  | `/api/admin/customers/{customer_id}/notes` | Get customer notes |
| `POST` | `/api/admin/customers/{customer_id}/notes` | Add a customer note |

**`GET /admin/customers` response** includes three parallel arrays (`customers`, `users`, `addresses`) that can be joined on `customer.user_id === user.id` and `address.customer_id === customer.id`. This structure is used by the frontend to enrich customers for the visibility-condition preview feature.

---

## 6. Admin — Orders

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/admin/orders` | List orders. Filter: `?status=`, `?customer_id=`, `?page=`, `?per_page=`, `?from_date=`, `?to_date=` |
| `GET`  | `/api/admin/orders/{order_id}/logs` | Audit log for an order |
| `POST` | `/api/admin/orders/manual` | Create a manual order (admin-only) |
| `PUT`  | `/api/admin/orders/{order_id}` | Update order (status, notes, payment details) |
| `DELETE` | `/api/admin/orders/{order_id}` | Delete an order |
| `POST` | `/api/admin/orders/{order_id}/refund` | Issue a refund. Body: `{ amount?, reason, provider }` |
| `GET`  | `/api/admin/orders/{order_id}/refunds` | List refunds for an order |
| `GET`  | `/api/admin/orders/{order_id}/refund-providers` | Available refund providers for the order |
| `POST` | `/api/admin/orders/{order_id}/auto-charge` | Trigger an auto-charge attempt |

### Order Object (key fields)
```json
{
  "id": "string",
  "order_number": "string",
  "type": "order | scope_request",
  "status": "pending | paid | failed | refunded | scope_requested | responded | closed",
  "customer_id": "string",
  "total": 100.00,
  "currency": "GBP",
  "base_currency": "USD",
  "base_currency_amount": 127.50,
  "payment_method": "stripe | bank_transfer | gocardless | free | scope_request",
  "items": [],
  "created_at": "ISO datetime"
}
```

---

## 7. Admin — Enquiries

> Formerly called "Quote Requests". Orders with `type: "scope_request"` are surfaced here.

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/admin/enquiries` | List enquiries. Filter: `?status=`, `?customer_id=`, `?page=`, `?per_page=` |
| `PATCH`| `/api/admin/enquiries/{order_id}/status` | Update enquiry status. Body: `{ status }` |
| `DELETE` | `/api/admin/enquiries/{order_id}` | Delete an enquiry |

**Enquiry statuses**: `scope_pending`, `scope_requested`, `responded`, `closed`

> **Note**: Enquiry orders are regular orders with `type: "scope_request"`. They appear in both `/admin/orders` (full detail) and `/admin/enquiries` (filtered view).

---

## 8. Admin — Subscriptions

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/admin/filter-options` | Get filter options (statuses, payment methods) for subscriptions UI |
| `GET`  | `/api/admin/subscriptions` | List subscriptions. Filter: `?status=`, `?customer_id=`, `?page=`, `?per_page=` |
| `GET`  | `/api/admin/subscriptions/{subscription_id}/logs` | Audit log |
| `POST` | `/api/admin/subscriptions/manual` | Create a manual subscription record |
| `POST` | `/api/admin/subscriptions/{subscription_id}/renew-now` | Force-renew a subscription immediately |
| `PUT`  | `/api/admin/subscriptions/{subscription_id}` | Update subscription record |
| `POST` | `/api/admin/subscriptions/{subscription_id}/cancel` | Cancel a subscription |

### Subscription Object (key fields)
```json
{
  "id": "string",
  "customer_id": "string",
  "product_id": "string",
  "status": "active | cancelled | past_due | incomplete",
  "currency": "GBP",
  "base_currency": "USD",
  "base_currency_amount": 127.50,
  "stripe_subscription_id": "sub_...",
  "current_period_end": "ISO datetime"
}
```

---

## 9. Admin — Users

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/admin/users` | List all users for the tenant |
| `POST` | `/api/admin/users` | Create a new admin/staff user |
| `PUT`  | `/api/admin/users/{user_id}` | Update user profile / role |
| `PATCH`| `/api/admin/users/{user_id}/active` | Enable/disable user account |
| `GET`  | `/api/admin/users/{user_id}/logs` | Audit log |
| `POST` | `/api/admin/users/{user_id}/unlock` | Unlock a locked-out account |
| `DELETE` | `/api/admin/users/{user_id}` | Delete a user (soft-delete) |
| `POST` | `/api/admin/users/{user_id}/reactivate` | Reactivate a deleted user |
| `GET`  | `/api/admin/permissions/modules` | List all permission modules |
| `GET`  | `/api/admin/my-permissions` | Get current admin's permission set |

---

## 10. Admin — Promo Codes

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/admin/promo-codes` | List all promo codes |
| `POST` | `/api/admin/promo-codes` | Create a promo code |
| `PUT`  | `/api/admin/promo-codes/{code_id}` | Update a promo code |
| `DELETE` | `/api/admin/promo-codes/{code_id}` | Delete a promo code |
| `GET`  | `/api/admin/promo-codes/{promo_id}/logs` | Audit log |

### PromoCode Fields
```json
{
  "code": "SAVE10",
  "type": "percentage | fixed",
  "value": 10.0,
  "expires_at": "ISO datetime?",
  "max_uses": 100,
  "product_ids": [],
  "is_active": true
}
```

---

## 11. Admin — Terms & Conditions

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/terms/default` | Get default terms (public) |
| `GET`  | `/api/terms/for-product/{product_id}` | Get terms for a product (public) |
| `GET`  | `/api/admin/terms` | List all terms documents |
| `POST` | `/api/admin/terms` | Create a terms document |
| `PUT`  | `/api/admin/terms/{terms_id}` | Update a terms document |
| `DELETE` | `/api/admin/terms/{terms_id}` | Delete a terms document |
| `PUT`  | `/api/admin/products/{product_id}/terms` | Assign terms to a product |
| `GET`  | `/api/admin/terms/{terms_id}/logs` | Audit log |

---

## 12. Admin — References

> References provide `{ref:key}` variables resolved in **emails and public article content**.

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/references` | Public — get all references for the tenant |
| `GET`  | `/api/admin/references` | Admin — list all references |
| `POST` | `/api/admin/references` | Create a reference |
| `PUT`  | `/api/admin/references/{ref_id}` | Update a reference |
| `DELETE` | `/api/admin/references/{ref_id}` | Delete a reference |

### Reference Fields
```json
{
  "key": "company_name",
  "value": "Automate Accounts Ltd",
  "description": "Used in emails and article content"
}
```

Usage in content: `{ref:company_name}` → resolves to `"Automate Accounts Ltd"` at render time.

---

## 13. Admin — Settings & Website

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/settings/public` | Public tenant settings (name, logo, colors) |
| `GET`  | `/api/website-settings` | Public website content settings |
| `GET`  | `/api/admin/settings` | Full settings object |
| `PUT`  | `/api/admin/settings` | Update settings. Body: `AppSettingsUpdate` |
| `GET`  | `/api/admin/settings/structured` | Settings grouped by category |
| `PUT`  | `/api/admin/settings/key/{key}` | Update a single setting by key |
| `POST` | `/api/admin/upload-logo` | Upload tenant logo (multipart) |
| `GET`  | `/api/admin/website-settings` | Full website content settings |
| `PUT`  | `/api/admin/website-settings` | Update website content. Body: `WebsiteSettingsUpdate` |
| `GET`  | `/api/admin/tenant/base-currency` | Get tenant's base/reporting currency |
| `PUT`  | `/api/admin/tenant/base-currency` | Set base currency. Body: `{ currency: "USD" }` |
| `GET`  | `/api/admin/setup-checklist` | Return onboarding checklist status |

---

## 14. Admin — Integrations

### Email Providers

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/admin/integrations/email-providers` | List configured email providers |
| `POST` | `/api/admin/integrations/email-providers/set-active` | Set the active email provider. Body: `{ provider }` |
| `POST` | `/api/admin/integrations/resend/validate` | Validate a Resend API key |
| `POST` | `/api/admin/integrations/zoho-mail/save-credentials` | Save Zoho Mail credentials |
| `POST` | `/api/admin/integrations/zoho-mail/exchange-token` | Exchange OAuth code for Zoho Mail token |
| `POST` | `/api/admin/integrations/zoho-mail/validate` | Test Zoho Mail connection |
| `POST` | `/api/admin/integrations/zoho-mail/select-account` | Select a sending account |
| `POST` | `/api/admin/integrations/zoho-mail/refresh-token` | Refresh Zoho Mail OAuth token |

### CRM (Zoho CRM)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/admin/integrations/zoho-crm/save-credentials` | Save Zoho CRM OAuth credentials |
| `POST` | `/api/admin/integrations/zoho-crm/exchange-token` | Exchange OAuth code for CRM token |
| `POST` | `/api/admin/integrations/zoho-crm/validate` | Test CRM connection |
| `GET`  | `/api/admin/integrations/zoho-crm/modules` | List available CRM modules |
| `GET`  | `/api/admin/integrations/zoho-crm/modules/{module_name}/fields` | List fields for a CRM module |
| `GET`  | `/api/admin/integrations/crm-mappings` | List field mappings |
| `POST` | `/api/admin/integrations/crm-mappings` | Create a field mapping |
| `DELETE` | `/api/admin/integrations/crm-mappings/{mapping_id}` | Delete a field mapping |

### Payment Providers

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/admin/integrations/stripe/validate` | Validate a Stripe API key |
| `POST` | `/api/admin/integrations/gocardless/validate` | Validate a GoCardless token |
| `POST` | `/api/admin/payment/validate` | Validate a payment against an order |

### Status

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/admin/integrations/status` | Integration health dashboard (all providers) |

### Legacy OAuth Endpoints (Zoho CRM/Books)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/oauth/{provider}/save-settings` | Save OAuth settings for provider |
| `GET`  | `/api/oauth/{provider}/settings` | Get OAuth settings |
| `GET`  | `/api/oauth/integrations` | List connected OAuth integrations |
| `POST` | `/api/oauth/{provider}/save-credentials` | Save OAuth credentials |
| `POST` | `/api/oauth/{provider}/validate` | Validate OAuth connection |
| `POST` | `/api/oauth/{provider}/activate` | Activate an OAuth integration |
| `POST` | `/api/oauth/{provider}/deactivate` | Deactivate an OAuth integration |
| `DELETE` | `/api/oauth/{provider}/disconnect` | Disconnect OAuth integration |
| `POST` | `/api/oauth/zoho_crm/bulk-sync` | Bulk sync all customers to Zoho CRM |
| `POST` | `/api/oauth/zoho_books/bulk-sync` | Bulk sync all orders to Zoho Books |
| `GET`  | `/api/oauth/{provider}/status` | Integration status |

---

## 15. Admin — Finance (Zoho Books)

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/admin/finance/status` | Finance integration status |
| `POST` | `/api/admin/finance/zoho-books/save-credentials` | Save Zoho Books credentials |
| `POST` | `/api/admin/finance/zoho-books/validate` | Validate Zoho Books connection |
| `POST` | `/api/admin/finance/zoho-books/refresh` | Refresh Zoho Books OAuth token |
| `GET`  | `/api/admin/finance/zoho-books/account-mappings` | List account mappings |
| `POST` | `/api/admin/finance/zoho-books/account-mappings` | Create an account mapping |
| `DELETE` | `/api/admin/finance/zoho-books/account-mappings/{mapping_id}` | Delete an account mapping |
| `POST` | `/api/admin/finance/zoho-books/sync-now` | Force sync all orders to Zoho Books |
| `GET`  | `/api/admin/finance/sync-history` | Sync history log |
| `GET`  | `/api/admin/sync-logs` | All sync logs |
| `POST` | `/api/admin/sync-logs/{log_id}/retry` | Retry a failed sync |

---

## 16. Admin — Webhooks

Outbound webhooks (push events to external URLs).

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/admin/webhooks/events` | List all supported event types |
| `GET`  | `/api/admin/webhooks/delivery-stats` | Delivery success/failure stats |
| `GET`  | `/api/admin/webhooks` | List configured webhooks |
| `POST` | `/api/admin/webhooks` | Create a webhook. Body: `{ url, events[], secret? }` |
| `GET`  | `/api/admin/webhooks/{webhook_id}` | Get webhook config |
| `PUT`  | `/api/admin/webhooks/{webhook_id}` | Update webhook |
| `DELETE` | `/api/admin/webhooks/{webhook_id}` | Delete webhook |
| `POST` | `/api/admin/webhooks/{webhook_id}/rotate-secret` | Rotate signing secret |
| `POST` | `/api/admin/webhooks/{webhook_id}/test` | Send a test event |
| `GET`  | `/api/admin/webhooks/{webhook_id}/deliveries` | List delivery attempts |
| `GET`  | `/api/admin/webhooks/{webhook_id}/deliveries/{delivery_id}` | Get delivery detail |
| `POST` | `/api/admin/webhooks/{webhook_id}/deliveries/{delivery_id}/replay` | Replay a delivery |

---

## 17. Admin — Exports & Imports

### Exports (CSV)

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/admin/export/orders` | Export orders as CSV. Includes `base_currency_amount` column |
| `GET`  | `/api/admin/export/customers` | Export customers as CSV |
| `GET`  | `/api/admin/export/subscriptions` | Export subscriptions as CSV. Includes `base_currency_amount` |
| `GET`  | `/api/admin/export/catalog` | Export products catalog as CSV |
| `GET`  | `/api/admin/export/articles` | Export articles as CSV |
| `GET`  | `/api/admin/export/categories` | Export categories as CSV |
| `GET`  | `/api/admin/export/terms` | Export terms documents as CSV |
| `GET`  | `/api/admin/export/promo-codes` | Export promo codes as CSV |
| `GET`  | `/api/admin/export/bank-transactions` | Export bank transactions as CSV |
| `GET`  | `/api/admin/export/article-categories` | Export article categories as CSV |
| `GET`  | `/api/admin/export/article-templates` | Export article templates as CSV |

All export endpoints accept optional `?from_date=` and `?to_date=` query params.

### Imports (CSV)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/admin/import/{entity}` | Import CSV for entity. `{entity}`: `orders`, `customers`, `products`, `subscriptions`, `articles`, `resources` |
| `GET`  | `/api/admin/import/template/{entity}` | Download CSV template for entity |

---

## 18. Admin — Bank Transactions

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/admin/bank-transactions` | List bank transfer transactions |
| `POST` | `/api/admin/bank-transactions` | Log a manual bank receipt |
| `PUT`  | `/api/admin/bank-transactions/{txn_id}` | Update a transaction record |
| `DELETE` | `/api/admin/bank-transactions/{txn_id}` | Delete a transaction |
| `GET`  | `/api/admin/bank-transactions/{txn_id}/logs` | Audit log |

---

## 19. Admin — API Keys

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/admin/api-keys` | List API keys for the tenant |
| `POST` | `/api/admin/api-keys` | Create a new API key. Returns the raw key once |
| `DELETE` | `/api/admin/api-keys/{key_id}` | Revoke an API key |

---

## 20. Admin — Tenants & Custom Domains

> Platform admin (`is_platform_admin`) only for tenant management.

### Tenants

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/admin/tenants` | List all tenants (platform admin) |
| `POST` | `/api/admin/tenants` | Create a new tenant |
| `PUT`  | `/api/admin/tenants/{tenant_id}` | Update tenant |
| `POST` | `/api/admin/tenants/{tenant_id}/activate` | Activate tenant |
| `POST` | `/api/admin/tenants/{tenant_id}/deactivate` | Deactivate tenant |
| `POST` | `/api/admin/tenants/{tenant_id}/create-admin` | Create an admin user for the tenant |
| `GET`  | `/api/admin/tenants/{tenant_id}/users` | List tenant's users |
| `GET`  | `/api/admin/tenants/{tenant_id}/customers` | List tenant's customers |

### Custom Domains

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/admin/custom-domains` | List custom domains |
| `POST` | `/api/admin/custom-domains` | Add a custom domain |
| `PUT`  | `/api/admin/custom-domains` | Update custom domain config |
| `POST` | `/api/admin/custom-domains/{domain}/verify` | Trigger DNS verification |
| `DELETE` | `/api/admin/custom-domains/{domain}` | Remove a custom domain |

---

## 21. Admin — GDPR

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/api/admin/gdpr/requests` | Admin | List data deletion requests |
| `GET`  | `/api/admin/gdpr/export/{customer_id}` | Admin | Generate data export for customer |
| `GET`  | `/api/admin/gdpr/export/{customer_id}/download` | Admin | Download export ZIP |
| `POST` | `/api/admin/gdpr/delete/{customer_id}` | Admin | Execute customer data deletion |

---

## 22. Admin — Audit Logs

Prefix from `server.py`: `/api/logs` (registered via `audit_logs_router`).

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/logs` | List all audit log entries. Filter: `?entity_type=`, `?entity_id=`, `?action=`, `?page=` |
| `GET`  | `/api/logs/{log_id}` | Get single audit log entry |

---

## 23. Admin — Email Templates

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/admin/email-templates` | List system email templates |
| `PUT`  | `/api/admin/email-templates/{template_id}` | Update an email template body/subject |
| `GET`  | `/api/admin/email-logs` | List email send history |

> **Note**: Legacy quote-request email templates (`quote_request_admin`, `quote_request_customer`) have been removed. They are replaced by `scope_request_admin` / `enquiry_customer` triggers.

---

## 24. Content — Articles

> Articles are tenant-scoped documents (proposals, reports, etc.). Supports `{ref:key}` variable substitution in public content.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/api/articles/admin/list` | Admin | List all articles (admin view) |
| `GET`  | `/api/articles/public` | Bearer | List articles visible to the current customer |
| `GET`  | `/api/articles/{article_id}` | Bearer | Get a single article. `{ref:key}` variables resolved at read time |
| `GET`  | `/api/articles/{article_id}/validate-scope` | Bearer | Check if customer has access |
| `GET`  | `/api/articles/{article_id}/download` | Bearer | Download article as PDF |
| `GET`  | `/api/articles/{article_id}/logs` | Admin | Audit log |
| `POST` | `/api/articles` | Admin | Create an article |
| `PUT`  | `/api/articles/{article_id}` | Admin | Update an article |
| `DELETE` | `/api/articles/{article_id}` | Admin | Delete an article |
| `POST` | `/api/articles/{article_id}/email` | Admin | Preview email render |
| `POST` | `/api/articles/{article_id}/send-email` | Admin | Send article by email |

---

## 25. Content — Article Categories

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/api/article-categories` | Admin | List all article categories |
| `GET`  | `/api/article-categories/public` | Public | List public article categories |
| `POST` | `/api/article-categories` | Admin | Create category |
| `PUT`  | `/api/article-categories/{category_id}` | Admin | Update category |
| `DELETE` | `/api/article-categories/{category_id}` | Admin | Delete category |
| `GET`  | `/api/article-categories/{category_id}/logs` | Admin | Audit log |

---

## 26. Content — Article Templates

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/api/article-templates` | Admin | List templates |
| `POST` | `/api/article-templates` | Admin | Create template |
| `PUT`  | `/api/article-templates/{template_id}` | Admin | Update template |
| `DELETE` | `/api/article-templates/{template_id}` | Admin | Delete template |
| `GET`  | `/api/article-templates/{template_id}/logs` | Admin | Audit log |

---

## 27. Content — Article Email Templates

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/api/article-email-templates` | Admin | List email templates |
| `POST` | `/api/article-email-templates` | Admin | Create email template |
| `PUT`  | `/api/article-email-templates/{template_id}` | Admin | Update email template |
| `DELETE` | `/api/article-email-templates/{template_id}` | Admin | Delete email template |
| `GET`  | `/api/article-email-templates/{template_id}/logs` | Admin | Audit log |

---

## 28. Content — Resources

> Same structure as Articles. Resources are typically files/documents for customers to download.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/api/resources/admin/list` | Admin | List all resources |
| `GET`  | `/api/resources/public` | Bearer | List resources visible to customer |
| `GET`  | `/api/resources/{resource_id}` | Bearer | Get a resource |
| `GET`  | `/api/resources/{resource_id}/validate-scope` | Bearer | Check access |
| `GET`  | `/api/resources/{resource_id}/download` | Bearer | Download resource |
| `GET`  | `/api/resources/{resource_id}/logs` | Admin | Audit log |
| `POST` | `/api/resources` | Admin | Create resource |
| `PUT`  | `/api/resources/{resource_id}` | Admin | Update resource |
| `DELETE` | `/api/resources/{resource_id}` | Admin | Delete resource |
| `POST` | `/api/resources/{resource_id}/email` | Admin | Preview email |
| `POST` | `/api/resources/{resource_id}/send-email` | Admin | Send resource by email |

---

## 29. Content — Resource Categories

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/api/resource-categories` | Admin | List all categories |
| `GET`  | `/api/resource-categories/public` | Public | Public categories |
| `POST` | `/api/resource-categories` | Admin | Create |
| `PUT`  | `/api/resource-categories/{category_id}` | Admin | Update |
| `DELETE` | `/api/resource-categories/{category_id}` | Admin | Delete |
| `GET`  | `/api/resource-categories/{category_id}/logs` | Admin | Audit log |

---

## 30. Content — Resource Templates

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/api/resource-templates` | Admin | List |
| `POST` | `/api/resource-templates` | Admin | Create |
| `PUT`  | `/api/resource-templates/{template_id}` | Admin | Update |
| `DELETE` | `/api/resource-templates/{template_id}` | Admin | Delete |
| `GET`  | `/api/resource-templates/{template_id}/logs` | Admin | Audit log |

---

## 31. Content — Resource Email Templates

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/api/resource-email-templates` | Admin | List |
| `POST` | `/api/resource-email-templates` | Admin | Create |
| `PUT`  | `/api/resource-email-templates/{template_id}` | Admin | Update |
| `DELETE` | `/api/resource-email-templates/{template_id}` | Admin | Delete |
| `GET`  | `/api/resource-email-templates/{template_id}/logs` | Admin | Audit log |

---

## 32. Webhooks (Inbound)

Payment provider callbacks — **no auth** (verified by signature).

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/webhook/stripe` | Stripe webhook events (payment intent, subscription events) |
| `POST` | `/api/webhook/gocardless` | GoCardless webhook events |
| `POST` | `/api/gocardless/complete-redirect` | GoCardless redirect after Direct Debit authorization |

---

## 33. OAuth / CRM

See Section 14 for OAuth endpoints. Additional endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/oauth/zoho_crm/modules` | List CRM modules |
| `GET`  | `/api/oauth/zoho_crm/modules/{module_name}/fields` | Module fields |
| `GET`  | `/api/oauth/zoho_books/modules` | List Books modules |
| `GET`  | `/api/oauth/zoho_books/modules/{module_name}/fields` | Module fields |

---

## 34. Uploads & Downloads

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/uploads` | Bearer | Upload a file (multipart). Returns `{ upload_id, url }` |
| `GET`  | `/api/uploads/{upload_id}` | Public | Retrieve an uploaded file |
| `GET`  | `/api/download/test-cases` | Admin | Download test case data |

---

## 35. GDPR — Customer Self-Service

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/api/me/data-export` | Bearer | Request a data export package |
| `GET`  | `/api/me/data-export/download` | Bearer | Download the data export ZIP |
| `POST` | `/api/me/request-deletion` | Bearer | Request account data deletion |

---

## Changelog

| Date | Change |
|------|--------|
| 2026-02-27 | **Enquiries**: `quote_requests` collection dropped. `POST /orders/scope-request` replaces `POST /orders/quote-request`. `/admin/enquiries` replaces `/admin/quote-requests`. Status field uses `scope_requested` / `scope_pending` instead of `quote_*`. |
| 2026-02-27 | **Product Visibility V2**: `visibility_conditions` now supports nested grouped format `{ top_logic, groups: [{ logic, conditions }] }`. Legacy flat format still accepted. |
| 2026-02-27 | **FX / Multi-Currency**: `currency`, `base_currency`, `base_currency_amount` added to Order and Subscription documents. Rates from `exchangerate-api.com` with 1-hour TTL cache. |
| 2026-02-27 | **References in Articles**: `{ref:key}` variables now resolved in public article content (previously emails only). |
| 2026-02-27 | **Cart Validation**: Backend and frontend enforce no mixing of billing types or currencies per cart. |
| 2026-02-27 | **Email Templates**: `quote_request_admin` / `quote_request_customer` templates removed. Replaced by `scope_request_admin` / `enquiry_customer`. |
| 2026-02-27 | **Removed preferred_currency**: `currency` and `currency_locked` fields removed from customer documents. Stripped from `auth.py` registration flow and unset via migration. Currency is now driven entirely by the product's `currency` field. Portal orders/subscriptions now display `order.currency` / `sub.currency` instead of a customer-level preference. |
