# Automate Accounts — API Reference

**Base URL:** `https://platform-health-scan.preview.emergentagent.com`  
**All endpoints are prefixed with `/api`.**

---

## Authentication

Most endpoints require a JWT bearer token obtained from a login endpoint.

**Header format:**
```
Authorization: Bearer <token>
```

Tokens are also set automatically as `aa_access_token` HttpOnly cookies on login.

**Roles:**
| Role | Description |
|---|---|
| `platform_super_admin` | Platform-level super admin (no tenant) |
| `partner_super_admin` | Top-level admin of a partner organisation |
| `partner_admin` | Admin of a partner organisation |
| `partner_staff` | Staff member of a partner organisation |
| `customer` | End customer of a partner organisation |

---

## 1. Public Auth Endpoints

### POST `/api/auth/login`
Legacy login. Routes to partner or customer login if `partner_code` is provided.

**Request body:**
```json
{
  "email": "admin@automateaccounts.local",
  "password": "ChangeMe123!",
  "partner_code": "",
  "login_type": "partner"
}
```
**Response `200`:**
```json
{
  "token": "<jwt>",
  "role": "platform_super_admin",
  "tenant_id": null
}
```

**curl:**
```bash
curl -X POST $API_URL/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@automateaccounts.local","password":"ChangeMe123!"}'
```

---

### POST `/api/auth/partner-login`
Login for partner organisation admins and staff. Requires `partner_code`.

**Request body:**
```json
{
  "email": "admin@yourorg.com",
  "password": "YourPassword1!",
  "partner_code": "your-org"
}
```
**Response `200`:**
```json
{
  "token": "<jwt>",
  "role": "partner_super_admin",
  "tenant_id": "<tenant_id>"
}
```

---

### POST `/api/auth/customer-login`
Login for customers scoped to a partner organisation.

**Request body:**
```json
{
  "email": "customer@example.com",
  "password": "YourPassword1!",
  "partner_code": "your-org"
}
```
**Response `200`:** `{ "token", "role", "tenant_id" }`

---

### POST `/api/auth/domain-login`
Login using the request's `Origin` or `Referer` header to identify the tenant (for custom domains).

**Request body:**
```json
{ "email": "user@example.com", "password": "Password1!" }
```
**Response `200`:** `{ "token", "role", "tenant_id", "tenant_name", "is_admin" }`

---

### GET `/api/auth/domain-info`
Get tenant branding info for the current request domain.

**Response `200`:**
```json
{
  "is_custom_domain": true,
  "tenant_name": "Org Name",
  "tenant_code": "org-code",
  "branding": { ... }
}
```

---

### POST `/api/auth/logout`
Clear the HttpOnly authentication cookies.

**Response `200`:** `{ "success": true, "message": "Logged out successfully" }`

---

### POST `/api/auth/refresh`
Get a new access token using the refresh token (from HttpOnly cookie or request body).

**Request body (optional):**
```json
{ "refresh_token": "<refresh_jwt>" }
```
**Response `200`:** `{ "token": "<new_access_jwt>", "expires_in": 3600 }`

---

### POST `/api/auth/register`
Register a new customer account under a partner organisation.

**Request body:**
```json
{
  "email": "customer@example.com",
  "password": "Password1!",
  "full_name": "Jane Doe",
  "company_name": "Acme Ltd",
  "job_title": "Director",
  "phone": "+44 7700 900000",
  "partner_code": "your-org",
  "address": {
    "line1": "123 High St",
    "line2": "",
    "city": "London",
    "region": "England",
    "postal": "SW1A 1AA",
    "country": "GB"
  }
}
```
**Response `200`:** `{ "message": "Verification required" }`

---

### POST `/api/auth/verify-email`
Verify a customer's email with the OTP sent on registration.

**Request body (code method):**
```json
{ "email": "customer@example.com", "code": "123456", "partner_code": "your-org" }
```
**Request body (token method):**
```json
{ "token": "<jwt_token_from_email>" }
```
**Response `200`:** `{ "message": "Verified" }`

---

### POST `/api/auth/resend-verification-email`
Resend OTP verification email.

**Request body:**
```json
{ "email": "customer@example.com", "partner_code": "your-org" }
```
**Response `200`:** `{ "message": "Verification email resent" }`

---

### POST `/api/auth/forgot-password`
Request a password reset OTP (always returns success to prevent email enumeration).

**Request body:**
```json
{ "email": "customer@example.com", "partner_code": "your-org" }
```
**Response `200`:** `{ "message": "If an account with that email exists, a reset code has been sent." }`

---

### POST `/api/auth/reset-password`
Set a new password using the OTP from the forgot-password email.

**Request body:**
```json
{
  "email": "customer@example.com",
  "partner_code": "your-org",
  "code": "123456",
  "new_password": "NewPassword1!"
}
```
**Response `200`:** `{ "message": "Password reset successfully..." }`

---

### POST `/api/auth/register-partner`
Register a new partner organisation (self-service). Sends an OTP for verification.

**Request body:**
```json
{
  "name": "My Organisation",
  "admin_name": "John Smith",
  "admin_email": "john@myorg.com",
  "admin_password": "Password1!",
  "base_currency": "GBP",
  "address": {
    "line1": "1 Business Park",
    "city": "Manchester",
    "postal": "M1 1AA",
    "country": "GB"
  }
}
```
**Response `200`:** `{ "message": "Verification required" }`

---

### POST `/api/auth/verify-partner-email`
Complete partner organisation registration by verifying the OTP.

**Request body:**
```json
{ "email": "john@myorg.com", "code": "123456" }
```
**Response `200`:** `{ "message": "Verified", "partner_code": "my-organisation" }`

---

### GET `/api/me`
Get the current authenticated user's profile, customer record, and address.

**Auth: required**

**Response `200`:**
```json
{
  "id": "<user_id>",
  "email": "user@example.com",
  "full_name": "Jane Doe",
  "role": "customer",
  "tenant_id": "<tenant_id>",
  "customer": { ... },
  "address": { ... }
}
```

---

### GET `/api/tenant-info`
Get tenant display info by partner code or API key.

**Query params:** `code=your-org` OR pass `X-API-Key` header.

**Response `200`:** `{ "tenant": { "name": "Org Name", "code": "org-code", "is_platform": false } }`

---

## 2. Public Store Endpoints

### GET `/api/products`
List all active products for the current tenant.

**Auth:** optional  
**Query params:** `partner_code=<code>` (to scope to a specific tenant)

**Response `200`:** `{ "products": [ { "id", "name", "description", "base_price", "currency", ... } ] }`

**curl:**
```bash
curl "$API_URL/api/products?partner_code=your-org"
```

---

### GET `/api/products/{product_id}`
Get a single active product by ID.

**Auth:** optional  
**Response `200`:** `{ "product": { ... } }`  
**Response `404`:** Product not found (or tenant mismatch)

---

### GET `/api/categories`
List all active product categories with product counts.

**Auth:** optional  
**Query params:** `partner_code=<code>`

**Response `200`:** `{ "categories": [ { "name", "is_active", "blurb" } ], "category_blurbs": { ... } }`

---

### GET `/api/terms`
List all terms and conditions for the current tenant.

**Auth:** optional  
**Query params:** `partner_code=<code>`

**Response `200`:** `{ "terms": [ { "id", "title", "content", "is_default", "status" } ] }`

---

### GET `/api/terms/default`
Get the default (active) terms and conditions document.

**Auth:** optional  
**Response `200`:** `{ "id", "title", "content", "is_default": true, "status": "active" }`

---

### GET `/api/terms/{terms_id}`
Get a specific terms and conditions document.

**Response `200`:** `{ "terms": { ... } }`

---

### POST `/api/pricing/calc`
Calculate price for a product given intake form inputs (no auth required).

**Request body:**
```json
{
  "product_id": "<product_id>",
  "inputs": { "question_key": "value" },
  "partner_code": "your-org"
}
```
**Response `200`:**
```json
{
  "product_id": "<product_id>",
  "subtotal": 99.00,
  "fee": 0.00,
  "total": 99.00,
  "currency": "GBP",
  "is_enquiry": false,
  "breakdown": [ ... ]
}
```

---

### POST `/api/promo-codes/validate`
Validate a promo code for a product at checkout.

**Auth: required**

**Request body:**
```json
{
  "code": "PROMO20",
  "checkout_type": "one_time",
  "currency": "GBP",
  "product_ids": ["<product_id>"]
}
```
**Response `200`:**
```json
{
  "valid": true,
  "code": "PROMO20",
  "discount_type": "percentage",
  "discount_value": 20
}
```

---

### GET `/api/store/fx-rates`
Get FX rates for common currencies relative to a base currency.

**Query params:** `base=USD` (default)

**Response `200`:** `{ "base": "USD", "rates": { "GBP": 0.79, "EUR": 0.92, ... } }`

---

### GET `/api/store/filters`
List all active store filters (for product filtering UI).

**Response `200`:** `{ "filters": [ { "id", "name", "filter_type", "options", ... } ] }`

---

## 3. Customer Portal Endpoints

All require customer authentication (`Authorization: Bearer <token>`).

### POST `/api/orders/preview`
Preview order totals before checkout (includes tax and fee calculations).

**Request body:**
```json
{
  "items": [
    {
      "product_id": "<product_id>",
      "quantity": 1,
      "inputs": { "question_key": "value" }
    }
  ],
  "payment_method": "stripe"
}
```
**Response `200`:** `{ "items": [ { "product_id", "product_name", "pricing": { "subtotal", "fee", "total" }, ... } ] }`

---

### POST `/api/orders/scope-request`
Submit a scope request for products that require custom pricing.

**Request body:**
```json
{
  "items": [
    { "product_id": "<product_id>", "quantity": 1, "inputs": {} }
  ]
}
```
**Response `200`:** `{ "message": "Enquiry submitted", "order_id": "<id>", "order_number": "AA-XXXX" }`

---

### POST `/api/orders/scope-request-form`
Submit a scope request with a full contact/project form.

**Request body:**
```json
{
  "items": [ { "product_id": "<product_id>", "quantity": 1, "inputs": {} } ],
  "form_data": {
    "name": "Jane Doe",
    "email": "jane@example.com",
    "company": "Acme Ltd",
    "phone": "+44 7700 900000",
    "message": "I need help with...",
    "project_summary": "Automated bookkeeping",
    "desired_outcomes": "Save 5 hours/week",
    "apps_involved": "Xero, Zapier",
    "timeline_urgency": "ASAP",
    "budget_range": "£500–£1000",
    "additional_notes": ""
  }
}
```
**Response `200`:** `{ "message": "Enquiry submitted", "order_id": "<id>", "order_number": "AA-XXXX" }`

---

### GET `/api/orders`
Get all orders for the current customer.

**Response `200`:** `{ "orders": [ ... ], "items": [ ... ] }`

---

### GET `/api/orders/{order_id}`
Get a specific order with its line items and terms.

**Response `200`:** `{ "order": { ... }, "items": [ ... ], "terms": { ... } }`

---

### GET `/api/subscriptions`
Get all subscriptions for the current customer.

**Response `200`:** `{ "subscriptions": [ ... ] }`

---

### POST `/api/subscriptions/{subscription_id}/cancel`
Request cancellation of a subscription.

**Request body:**
```json
{ "reason": "No longer needed" }
```
**Response `200`:** `{ "message": "Cancellation scheduled" }`

---

### GET `/api/orders/{order_id}/invoice`
Get the invoice data for a specific order (PDF-ready).

**Response `200`:** `{ "invoice": { ... }, "line_items": [ ... ], "order": { ... } }`

---

### POST `/api/orders/{order_id}/send-invoice`
Send an invoice email for an order.

**Request body:** `{}`

**Response `200`:** `{ "message": "Invoice sent" }`

---

### GET `/api/me/data-export`
Request a GDPR data export for the current user.

**Response `200`:** `{ "export_id": "<id>", "status": "pending" }`

---

### GET `/api/me/data-export/download`
Download the GDPR data export file (ZIP).

**Response `200`:** Binary file stream (ZIP)

---

### POST `/api/me/request-deletion`
Request account deletion (GDPR right to erasure).

**Response `200`:** `{ "message": "Deletion request submitted" }`

---

## 4. Checkout Endpoints

### POST `/api/checkout/bank-transfer`
Place an order via bank transfer (GoCardless Direct Debit).

**Auth: required**

**Request body:**
```json
{
  "items": [ { "product_id": "<id>", "quantity": 1, "inputs": {} } ],
  "promo_code": "PROMO20",
  "terms_accepted": true,
  "terms_id": "<terms_id>",
  "payment": {
    "method": "bank_transfer",
    "redirect_flow_id": "<gc_redirect_flow_id>"
  }
}
```
**Response `200`:** `{ "order_id": "<id>", "order_number": "AA-XXXX", "status": "confirmed" }`

---

### POST `/api/checkout/session`
Create a Stripe checkout session for card payment.

**Auth: required**

**Request body:**
```json
{
  "items": [ { "product_id": "<id>", "quantity": 1, "inputs": {} } ],
  "promo_code": null,
  "terms_accepted": true,
  "terms_id": "<terms_id>",
  "success_url": "https://yoursite.com/success",
  "cancel_url": "https://yoursite.com/cancel"
}
```
**Response `200`:** `{ "session_id": "<stripe_session_id>", "url": "https://checkout.stripe.com/..." }`

---

### GET `/api/checkout/status/{session_id}`
Poll Stripe checkout session status.

**Response `200`:** `{ "status": "paid | unpaid | expired", "order_id": "<id>" }`

---

### POST `/api/checkout/free`
Place a free (£0.00) order without a payment processor.

**Auth: required**

**Request body:**
```json
{
  "items": [ { "product_id": "<id>", "quantity": 1, "inputs": {} } ],
  "terms_accepted": true
}
```
**Response `200`:** `{ "order_id": "<id>", "order_number": "AA-XXXX" }`

---

### POST `/api/checkout/calculate-tax`
Calculate tax for a basket before checkout.

**Auth: required**

**Request body:**
```json
{
  "items": [ { "product_id": "<id>", "quantity": 1, "subtotal": 99.00 } ],
  "country": "GB",
  "region": "England"
}
```
**Response `200`:** `{ "tax_amount": 19.80, "tax_rate": 0.20, "breakdown": [ ... ] }`

---

### POST `/api/gocardless/complete-redirect`
Complete a GoCardless redirect flow (called after the user returns from GoCardless).

**Auth: required**

**Request body:**
```json
{ "redirect_flow_id": "<gc_id>", "session_token": "<token>" }
```
**Response `200`:** `{ "mandate_id": "<id>", "customer_bank_account_id": "<id>" }`

---

## 5. Admin — Catalog

All admin endpoints require authentication and admin role (`partner_admin` or above).

### GET `/api/admin/products-all`
List all products across all tenants (platform admin) or for the current tenant.

**Query params:** `page`, `limit`, `search`, `category`, `is_active`

**Response `200`:** `{ "products": [ ... ], "total": 42 }`

---

### POST `/api/admin/products`
Create a new product.

**Request body:**
```json
{
  "name": "Bookkeeping Service",
  "description": "Monthly bookkeeping.",
  "category": "Accounting",
  "is_active": true,
  "currency": "GBP",
  "pricing_type": "fixed",
  "base_price": 199.00,
  "billing_period": "monthly"
}
```
**Response `200`:** `{ "id": "<product_id>", "name": "Bookkeeping Service", ... }`

---

### PUT `/api/admin/products/{product_id}`
Update an existing product. Accepts same fields as POST.

**Response `200`:** `{ "id": "<product_id>", ... }`

---

### GET `/api/admin/products/{product_id}/logs`
Get audit logs for a product.

**Response `200`:** `{ "logs": [ ... ] }`

---

### GET `/api/admin/categories`
List all product categories for the current tenant.

**Response `200`:** `{ "categories": [ { "id", "name", "description", "is_active" } ] }`

---

### POST `/api/admin/categories`
Create a new product category.

**Request body:**
```json
{ "name": "Tax & Compliance", "description": "Tax-related services.", "is_active": true }
```
**Response `200`:** `{ "id": "<cat_id>", ... }`

---

### PUT `/api/admin/categories/{cat_id}`
Update a product category.

**Response `200`:** `{ "id": "<cat_id>", ... }`

---

### DELETE `/api/admin/categories/{cat_id}`
Delete a product category (only if no active products use it).

**Response `200`:** `{ "message": "Category deleted" }`

---

### GET `/api/admin/categories/{cat_id}/logs`
Get audit logs for a category.

---

## 6. Admin — Customers

### GET `/api/admin/customers/stats`
Get customer statistics (total, new this month, etc.).

**Response `200`:** `{ "total": 100, "new_this_month": 12, ... }`

---

### GET `/api/admin/customers`
List customers with optional filtering.

**Query params:** `search`, `page`, `limit`, `status` (active/inactive)

**Response `200`:** `{ "customers": [ { "id", "full_name", "email", "company_name", ... } ], "total": 42 }`

---

### POST `/api/admin/customers/create`
Create a new customer (admin-initiated).

**Request body:**
```json
{
  "email": "newcustomer@example.com",
  "password": "TempPass1!",
  "full_name": "Jane Smith",
  "company_name": "Smith Ltd",
  "job_title": "CEO",
  "phone": "+44 7700 900001",
  "country": "GB",
  "mark_verified": true,
  "tenant_id": "<tenant_id>"
}
```
**Response `200`:** `{ "customer_id": "<id>", "user_id": "<id>" }`

---

### PUT `/api/admin/customers/{customer_id}`
Update customer profile and address.

**Request body (nested):**
```json
{
  "customer_data": {
    "full_name": "Jane Smith",
    "company_name": "Smith Ltd",
    "job_title": "Director",
    "phone": "+44 7700 900001"
  },
  "address_data": {
    "line1": "1 New Street",
    "city": "London",
    "postal": "EC1A 1AA",
    "country": "GB"
  }
}
```
**Response `200`:** `{ "message": "Customer updated successfully" }`

---

### PATCH `/api/admin/customers/{customer_id}/active`
Activate or deactivate a customer account.

**Request body:** `{ "is_active": false }`

**Response `200`:** `{ "message": "Customer deactivated" }`

---

### PATCH `/api/admin/customers/{customer_id}/tax-exempt`
Set tax-exempt status for a customer.

**Request body:** `{ "is_tax_exempt": true }`

**Response `200`:** `{ "message": "Tax exempt status updated" }`

---

### PUT `/api/admin/customers/{customer_id}/payment-methods`
Update allowed payment methods for a customer.

**Request body:**
```json
{ "allow_bank_transfer": true, "allow_card_payment": true }
```
**Response `200`:** `{ "message": "Payment methods updated" }`

---

### GET `/api/admin/customers/{customer_id}/logs`
Get audit logs for a customer.

**Response `200`:** `{ "logs": [ ... ] }`

---

### GET `/api/admin/customers/{customer_id}/notes`
Get internal notes for a customer.

**Response `200`:** `{ "notes": [ { "id", "note", "created_by", "created_at" } ] }`

---

### POST `/api/admin/customers/{customer_id}/notes`
Add an internal note to a customer record.

**Request body:** `{ "note": "Customer prefers email contact." }`

**Response `200`:** `{ "id": "<note_id>", ... }`

---

## 7. Admin — Orders & Enquiries

### GET `/api/admin/orders/stats`
Get order statistics.

**Response `200`:** `{ "total": 250, "revenue_this_month": 15000, ... }`

---

### GET `/api/admin/orders`
List all orders with filtering.

**Query params:** `page`, `limit`, `search`, `status`, `customer_id`, `date_from`, `date_to`

**Response `200`:** `{ "orders": [ ... ], "total": 250 }`

---

### POST `/api/admin/orders/manual`
Create a manual order on behalf of a customer.

**Request body:**
```json
{
  "customer_id": "<customer_id>",
  "items": [ { "product_id": "<id>", "quantity": 1, "inputs": {} } ],
  "payment_method": "manual",
  "status": "confirmed",
  "internal_note": "Created manually"
}
```
**Response `200`:** `{ "id": "<order_id>", "order_number": "AA-XXXX" }`

---

### PUT `/api/admin/orders/{order_id}`
Update an order (status, notes, etc.).

**Request body:**
```json
{
  "status": "completed",
  "internal_note": "Order fulfilled",
  "payment_date": "2025-01-15T10:00:00Z"
}
```
**Response `200`:** `{ "message": "Order updated" }`

---

### DELETE `/api/admin/orders/{order_id}`
Delete an order (soft delete or hard delete depending on status).

**Response `200`:** `{ "message": "Order deleted" }`

---

### POST `/api/admin/orders/{order_id}/refund`
Process a refund for an order.

**Request body:**
```json
{
  "amount": 50.00,
  "reason": "Customer request",
  "refund_method": "stripe"
}
```
**Response `200`:** `{ "refund_id": "<id>", "status": "processed" }`

---

### GET `/api/admin/orders/{order_id}/refunds`
List refunds for an order.

**Response `200`:** `{ "refunds": [ ... ] }`

---

### GET `/api/admin/orders/{order_id}/refund-providers`
Get available refund providers for an order.

**Response `200`:** `{ "providers": [ "stripe", "manual" ] }`

---

### POST `/api/admin/orders/{order_id}/auto-charge`
Attempt to auto-charge (re-collect) a failed payment for an order.

**Response `200`:** `{ "message": "Charge initiated" }`

---

### GET `/api/admin/orders/{order_id}/logs`
Get audit logs for an order.

---

### GET `/api/admin/enquiries`
List scope request / enquiry orders.

**Query params:** `page`, `limit`, `status`

**Response `200`:** `{ "orders": [ ... ], "total": 15 }`

---

### PATCH `/api/admin/enquiries/{order_id}/status`
Update the status of an enquiry.

**Request body:** `{ "status": "in_review" }`

**Response `200`:** `{ "message": "Status updated" }`

---

### DELETE `/api/admin/enquiries/{order_id}`
Delete an enquiry.

**Response `200`:** `{ "message": "Enquiry deleted" }`

---

### POST `/api/admin/enquiries/manual`
Create a manual enquiry record.

**Request body:**
```json
{
  "customer_id": "<id>",
  "product_ids": ["<id>"],
  "notes": "Interested in bookkeeping package"
}
```

---

### GET `/api/admin/enquiries/{order_id}/pdf`
Generate a PDF of an enquiry.

**Response `200`:** Binary PDF stream

---

## 8. Admin — Subscriptions

### GET `/api/admin/subscriptions/stats`
Get subscription statistics.

**Response `200`:** `{ "total": 80, "active": 65, "mrr": 12500 }`

---

### GET `/api/admin/filter-options`
Get dropdown filter values for the subscriptions list view.

**Response `200`:** `{ "statuses": [...], "products": [...], "payment_methods": [...] }`

---

### GET `/api/admin/subscriptions`
List all subscriptions with filtering.

**Query params:** `page`, `limit`, `search`, `status`, `customer_id`

**Response `200`:** `{ "subscriptions": [ ... ], "total": 80 }`

---

### POST `/api/admin/subscriptions/manual`
Create a manual subscription.

**Request body:**
```json
{
  "customer_id": "<customer_id>",
  "product_id": "<product_id>",
  "plan_description": "Monthly Bookkeeping",
  "amount": 199.00,
  "currency": "GBP",
  "billing_period": "monthly",
  "start_date": "2025-01-01",
  "payment_method": "bank_transfer",
  "status": "active"
}
```
**Response `200`:** `{ "id": "<subscription_id>", ... }`

---

### PUT `/api/admin/subscriptions/{subscription_id}`
Update a subscription.

**Request body:**
```json
{ "status": "paused", "internal_note": "Customer on holiday" }
```
**Response `200`:** `{ "message": "Subscription updated" }`

---

### POST `/api/admin/subscriptions/{subscription_id}/cancel`
Cancel a subscription.

**Request body:** `{ "reason": "Customer request", "cancel_immediately": true }`

**Response `200`:** `{ "message": "Subscription cancelled" }`

---

### POST `/api/admin/subscriptions/{subscription_id}/renew-now`
Immediately renew/charge a subscription.

**Response `200`:** `{ "message": "Renewal initiated" }`

---

### POST `/api/admin/subscriptions/{subscription_id}/send-reminder`
Send a renewal reminder email to the customer.

**Response `200`:** `{ "message": "Reminder sent" }`

---

### GET `/api/admin/subscriptions/{subscription_id}/logs`
Get audit logs for a subscription.

---

## 9. Admin — Plans (Platform-level)

Plans are platform-wide license tiers for partner organisations.

### GET `/api/admin/plans`
List all plans.

**Response `200`:** `{ "plans": [ { "id", "name", "max_products", "max_customers", "price", ... } ] }`

---

### POST `/api/admin/plans`
Create a new plan.

**Request body:**
```json
{
  "name": "Starter",
  "max_products": 10,
  "max_customers": 50,
  "max_staff_users": 3,
  "price": 0.00,
  "billing_period": "monthly",
  "is_default": false,
  "status": "active"
}
```
**Response `200`:** `{ "id": "<plan_id>", ... }`

---

### GET `/api/admin/plans/{plan_id}`
Get a specific plan.

**Response `200`:** `{ "plan": { ... } }`

---

### PUT `/api/admin/plans/{plan_id}`
Update a plan.

**Response `200`:** `{ "id": "<plan_id>", ... }`

---

### DELETE `/api/admin/plans/{plan_id}`
Delete a plan.

**Response `200`:** `{ "message": "Plan deleted" }`

---

### PATCH `/api/admin/plans/{plan_id}/set-default`
Set this plan as the default for new partner registrations.

**Response `200`:** `{ "message": "Default plan updated" }`

---

### PATCH `/api/admin/plans/{plan_id}/status`
Change a plan's status (active/inactive).

**Request body:** `{ "status": "active" }`

**Response `200`:** `{ "message": "Plan status updated" }`

---

### GET `/api/admin/plans/{plan_id}/logs`
Get audit logs for a plan.

---

### GET `/api/partner/plans/public`
Get the list of publicly available upgrade plans (for the partner upgrade flow).

**Response `200`:** `{ "plans": [ ... ] }`

---

## 10. Admin — Promo Codes

### GET `/api/admin/promo-codes`
List all promo codes.

**Response `200`:** `{ "promo_codes": [ { "id", "code", "discount_type", "discount_value", "enabled" } ] }`

---

### POST `/api/admin/promo-codes`
Create a new promo code.

**Request body:**
```json
{
  "code": "SAVE20",
  "discount_type": "percentage",
  "discount_value": 20,
  "enabled": true,
  "applies_to": "both",
  "max_uses": 100,
  "expiry_date": "2025-12-31T23:59:59Z",
  "currency": "GBP",
  "one_time_code": false
}
```
**`applies_to` values:** `both` | `one-time` | `subscription`

**Response `200`:** `{ "id": "<promo_id>", ... }`

---

### PUT `/api/admin/promo-codes/{code_id}`
Update a promo code.

**Response `200`:** `{ "id": "<promo_id>", ... }`

---

### DELETE `/api/admin/promo-codes/{code_id}`
Delete a promo code.

**Response `200`:** `{ "message": "Promo code deleted" }`

---

### GET `/api/admin/promo-codes/{promo_id}/logs`
Get audit logs for a promo code.

---

## 11. Admin — Terms & Conditions

### GET `/api/admin/terms`
List all terms and conditions documents for the current tenant.

**Response `200`:** `{ "terms": [ { "id", "title", "status", "is_default" } ] }`

---

### POST `/api/admin/terms`
Create a new T&C document.

**Request body:**
```json
{
  "title": "Service Agreement v2",
  "content": "<h2>Terms</h2><p>...</p>",
  "status": "active",
  "is_default": false
}
```
**Response `200`:** `{ "id": "<terms_id>", ... }`

---

### PUT `/api/admin/terms/{terms_id}`
Update a T&C document.

**Response `200`:** `{ "id": "<terms_id>", ... }`

---

### DELETE `/api/admin/terms/{terms_id}`
Delete a T&C document.

**Response `200`:** `{ "message": "Terms deleted" }`

---

### PUT `/api/admin/products/{product_id}/terms`
Assign specific terms to a product.

**Request body:** `{ "terms_id": "<terms_id>" }`

**Response `200`:** `{ "message": "Terms assigned" }`

---

### GET `/api/terms/for-product/{product_id}`
Get the terms document assigned to a product.

**Response `200`:** Terms document or default terms

---

### GET `/api/admin/terms/{terms_id}/logs`
Get audit logs for a T&C document.

---

## 12. Admin — Users & Permissions

### GET `/api/admin/users`
List admin and staff users for the current tenant.

**Query params:** `search`, `role`, `status`

**Response `200`:** `{ "users": [ { "id", "email", "full_name", "role", "is_active" } ], "total": 10 }`

---

### POST `/api/admin/users`
Create a new admin/staff user.

**Request body:**
```json
{
  "email": "staff@yourorg.com",
  "full_name": "Alice Jones",
  "role": "partner_staff",
  "password": "TempPass1!",
  "is_active": true
}
```
**Response `200`:** `{ "id": "<user_id>", ... }`

---

### PUT `/api/admin/users/{user_id}`
Update a user's profile or role.

**Request body:**
```json
{ "full_name": "Alice Jones", "role": "partner_admin", "is_active": true }
```
**Response `200`:** `{ "message": "User updated" }`

---

### PATCH `/api/admin/users/{user_id}/active`
Activate or deactivate a user.

**Request body:** `{ "is_active": false }`

**Response `200`:** `{ "message": "User deactivated" }`

---

### DELETE `/api/admin/users/{user_id}`
Delete a user account.

**Response `200`:** `{ "message": "User deleted" }`

---

### POST `/api/admin/users/{user_id}/reactivate`
Reactivate a deleted or deactivated user account.

**Response `200`:** `{ "message": "User reactivated" }`

---

### POST `/api/admin/users/{user_id}/unlock`
Unlock a locked-out user account (after too many failed login attempts).

**Response `200`:** `{ "message": "Account unlocked" }`

---

### GET `/api/admin/users/{user_id}/logs`
Get audit logs for a user.

---

### GET `/api/admin/permissions/modules`
Get the list of all permission modules.

**Response `200`:** `{ "modules": [ { "key", "label", "actions" } ] }`

---

### GET `/api/admin/my-permissions`
Get the current user's effective permissions.

**Response `200`:** `{ "permissions": { "catalog": ["view", "create", "edit"], ... } }`

---

### GET `/api/admin/roles`
Get the list of available roles.

**Response `200`:** `{ "roles": [ { "value", "label" } ] }`

---

## 13. Admin — Settings

### GET `/api/admin/settings`
Get all app settings (integrations, branding, notifications).

**Response `200`:** `{ "store_name": "Acme", "primary_color": "#2563eb", ... }`

---

### PUT `/api/admin/settings`
Update app settings (bulk update, any key).

**Request body:** `{ "store_name": "Acme Ltd", "admin_notification_email": "admin@acme.com" }`

**Response `200`:** `{ "message": "Settings updated" }`

---

### GET `/api/admin/settings/structured`
Get settings structured by section (branding, email, payments).

---

### PUT `/api/admin/settings/key/{key}`
Update a single settings key.

**Request body:** `{ "value": "new_value" }`

**Response `200`:** `{ "message": "Setting updated" }`

---

### POST `/api/admin/upload-logo`
Upload a logo image for the organisation.

**Content-Type:** `multipart/form-data`  
**Field:** `file` (image file)

**Response `200`:** `{ "url": "https://..." }`

---

### GET `/api/settings/public`
Get public branding settings (no auth required).

**Response `200`:** `{ "store_name", "primary_color", "secondary_color", "logo_url" }`

---

## 14. Admin — Website Settings

### GET `/api/website-settings`
Get public website copy settings (hero text, footer, nav labels, etc.).

**Query params:** `partner_code=<code>`

**Response `200`:** Full website_settings document.

---

### GET `/api/admin/website-settings`
Get all website settings for the current tenant (admin view).

**Response `200`:** Full website_settings document.

---

### PUT `/api/admin/website-settings`
Update website settings (any key from the website_settings document).

**Request body:** `{ "hero_title": "Welcome", "footer_tagline": "We help businesses grow." }`

**Response `200`:** `{ "message": "Website settings updated" }`

---

## 15. Admin — Email Templates

### GET `/api/admin/email-templates`
List all email templates for the current tenant.

**Response `200`:** `{ "templates": [ { "id", "trigger", "name", "subject", "is_active" } ] }`

---

### PUT `/api/admin/email-templates/{template_id}`
Update an email template.

**Request body:**
```json
{
  "subject": "Your order {{order_number}} is confirmed",
  "body": "<p>Hi {{customer_name}},</p>...",
  "is_active": true
}
```
**Response `200`:** `{ "message": "Template updated" }`

---

### GET `/api/admin/email-logs`
List recent email logs (sent, failed, mocked).

**Response `200`:** `{ "logs": [ { "id", "to", "subject", "status", "created_at" } ] }`

---

## 16. Admin — Integrations

### GET `/api/admin/integrations/email-providers`
Get configured email providers for the current tenant.

**Response `200`:** `{ "active_provider": "resend", "providers": [ { "type", "is_configured", "is_active" } ] }`

---

### POST `/api/admin/integrations/email-providers/set-active`
Set the active email provider.

**Request body:** `{ "provider": "resend" }`

**Response `200`:** `{ "message": "Email provider updated" }`

---

### POST `/api/admin/integrations/resend/validate`
Validate a Resend API key.

**Request body:** `{ "api_key": "re_..." }`

**Response `200`:** `{ "valid": true, "message": "Resend API key is valid" }`

---

### POST `/api/admin/integrations/zoho-mail/save-credentials`
Save Zoho Mail OAuth credentials.

**Request body:** `{ "client_id": "...", "client_secret": "...", "redirect_uri": "..." }`

---

### POST `/api/admin/integrations/zoho-mail/exchange-token`
Exchange a Zoho Mail authorisation code for tokens.

**Request body:** `{ "code": "...", "redirect_uri": "..." }`

---

### POST `/api/admin/integrations/zoho-mail/validate`
Validate the current Zoho Mail connection.

---

### POST `/api/admin/integrations/zoho-mail/select-account`
Select the active Zoho Mail sending account.

**Request body:** `{ "account_id": "..." }`

---

### POST `/api/admin/integrations/zoho-mail/refresh-token`
Force-refresh the Zoho Mail access token.

---

### POST `/api/admin/integrations/zoho-crm/save-credentials`
Save Zoho CRM OAuth credentials.

**Request body:** `{ "client_id": "...", "client_secret": "...", "redirect_uri": "..." }`

---

### POST `/api/admin/integrations/zoho-crm/exchange-token`
Exchange a Zoho CRM authorisation code for tokens.

**Request body:** `{ "code": "...", "redirect_uri": "..." }`

---

### POST `/api/admin/integrations/zoho-crm/validate`
Validate the Zoho CRM connection.

**Response `200`:** `{ "valid": true }`

---

### GET `/api/admin/integrations/zoho-crm/modules`
List available Zoho CRM modules.

**Response `200`:** `{ "modules": [ { "api_name", "module_name" } ] }`

---

### GET `/api/admin/integrations/zoho-crm/modules/{module_name}/fields`
Get the fields for a specific Zoho CRM module.

**Response `200`:** `{ "fields": [ { "api_name", "display_label", "data_type" } ] }`

---

### GET `/api/admin/integrations/crm-mappings`
Get all Zoho CRM field mappings for all 13 application modules.

**Response `200`:** `{ "mappings": { "customers": [...], "orders": [...], ... } }`

---

### POST `/api/admin/integrations/crm-mappings`
Save CRM field mappings for a module.

**Request body:**
```json
{
  "module": "customers",
  "mappings": [
    { "local_field": "email", "crm_field": "Email", "crm_module": "Contacts" }
  ]
}
```

---

### DELETE `/api/admin/integrations/crm-mappings/{mapping_id}`
Delete a CRM mapping.

---

### GET `/api/admin/integrations/status`
Get the overall integration status (email, CRM, payments).

**Response `200`:**
```json
{
  "active_email_provider": "resend",
  "integrations": {
    "zoho_crm": { "connected": true },
    "stripe": { "connected": false },
    "gocardless": { "connected": true }
  }
}
```

---

### POST `/api/admin/integrations/stripe/validate`
Validate a Stripe API key and save it.

**Request body:** `{ "secret_key": "sk_live_..." }`

**Response `200`:** `{ "valid": true }`

---

### POST `/api/admin/integrations/gocardless/validate`
Validate GoCardless API credentials.

**Request body:** `{ "access_token": "...", "environment": "live" }`

**Response `200`:** `{ "valid": true }`

---

### GET `/api/admin/integrations/workdrive`
Get Zoho WorkDrive integration status.

---

### POST `/api/admin/integrations/workdrive/save-credentials`
Save Zoho WorkDrive OAuth credentials.

---

### POST `/api/admin/integrations/workdrive/exchange-token`
Exchange a WorkDrive authorisation code for tokens.

---

### POST `/api/admin/integrations/workdrive/validate`
Validate the WorkDrive connection.

---

### PUT `/api/admin/integrations/workdrive/parent-folder`
Set the parent folder for WorkDrive uploads.

---

### DELETE `/api/admin/integrations/workdrive/disconnect`
Disconnect the WorkDrive integration.

---

## 17. Admin — Finance (Zoho Books)

### GET `/api/admin/finance/status`
Get Zoho Books connection status.

**Response `200`:** `{ "connected": true, "organisation_name": "Acme Ltd" }`

---

### POST `/api/admin/finance/zoho-books/save-credentials`
Save Zoho Books OAuth credentials.

---

### POST `/api/admin/finance/zoho-books/validate`
Validate Zoho Books connection and retrieve organisations.

---

### POST `/api/admin/finance/zoho-books/refresh`
Force-refresh the Zoho Books access token.

---

### GET `/api/admin/finance/zoho-books/account-mappings`
Get Zoho Books account mappings.

---

### POST `/api/admin/finance/zoho-books/account-mappings`
Save Zoho Books account mappings.

---

### DELETE `/api/admin/finance/zoho-books/account-mappings/{mapping_id}`
Delete a Zoho Books account mapping.

---

### POST `/api/admin/finance/zoho-books/sync-now`
Trigger a manual sync to Zoho Books.

**Response `200`:** `{ "message": "Sync complete", "synced": 12, "failed": 0 }`

---

### GET `/api/admin/finance/sync-history`
Get Zoho Books sync history.

**Response `200`:** `{ "history": [ { "id", "synced_at", "status", "records" } ] }`

---

## 18. Admin — API Keys

### GET `/api/admin/api-keys`
List all API keys for the current tenant.

**Response `200`:** `{ "keys": [ { "id", "name", "key_prefix", "is_active", "created_at" } ] }`

---

### POST `/api/admin/api-keys`
Create a new API key.

**Request body:**
```json
{ "name": "My Integration Key", "permissions": ["read"] }
```
**Response `200`:** `{ "id": "<key_id>", "key": "aa_live_...", "name": "My Integration Key" }`

> **Note:** The full key is only returned on creation. Store it securely.

---

### DELETE `/api/admin/api-keys/{key_id}`
Revoke an API key.

**Response `200`:** `{ "message": "API key deleted" }`

---

## 19. Admin — Webhooks

### GET `/api/admin/webhooks/events`
List all available webhook event types.

**Response `200`:** `{ "events": [ "order.confirmed", "subscription.created", "customer.registered", ... ] }`

---

### GET `/api/admin/webhooks/delivery-stats`
Get webhook delivery statistics.

**Response `200`:** `{ "total": 500, "successful": 480, "failed": 20 }`

---

### GET `/api/admin/webhooks`
List all configured webhooks.

**Response `200`:** `{ "webhooks": [ { "id", "url", "events", "is_active" } ] }`

---

### POST `/api/admin/webhooks`
Create a new webhook.

**Request body:**
```json
{
  "url": "https://example.com/webhook",
  "events": ["order.confirmed", "customer.registered"],
  "is_active": true
}
```
**Response `200`:** `{ "id": "<webhook_id>", "secret": "whsec_..." }`

> **Note:** The webhook secret is only returned once. Store it for signature verification.

---

### GET `/api/admin/webhooks/{webhook_id}`
Get a specific webhook configuration.

---

### PUT `/api/admin/webhooks/{webhook_id}`
Update a webhook.

**Request body:** `{ "url": "https://new-url.com/webhook", "events": [...], "is_active": true }`

**Response `200`:** `{ "message": "Webhook updated" }`

---

### DELETE `/api/admin/webhooks/{webhook_id}`
Delete a webhook.

**Response `200`:** `{ "message": "Webhook deleted" }`

---

### POST `/api/admin/webhooks/{webhook_id}/rotate-secret`
Rotate the signing secret for a webhook.

**Response `200`:** `{ "secret": "whsec_new_..." }`

---

### POST `/api/admin/webhooks/{webhook_id}/test`
Send a test event to a webhook URL.

**Response `200`:** `{ "message": "Test event sent", "status": 200 }`

---

### GET `/api/admin/webhooks/{webhook_id}/deliveries`
Get delivery logs for a webhook.

---

### GET `/api/admin/webhooks/{webhook_id}/deliveries/{delivery_id}`
Get details of a specific webhook delivery.

---

### POST `/api/admin/webhooks/{webhook_id}/deliveries/{delivery_id}/replay`
Replay a failed webhook delivery.

---

## 20. Admin — Taxes & Invoices

### GET `/api/admin/taxes/settings`
Get tax settings (enabled, default rates, etc.).

**Response `200`:** `{ "tax_enabled": true, "default_rate": 0.20, "country": "GB" }`

---

### PUT `/api/admin/taxes/settings`
Update tax settings.

**Request body:** `{ "tax_enabled": true, "default_rate": 0.20 }`

---

### GET `/api/admin/taxes/tables`
Get tax rate tables by country/state.

---

### PUT `/api/admin/taxes/tables/{country_code}/{state_code}`
Set a tax rate for a country/state combination.

**Request body:** `{ "rate": 0.10 }`

---

### GET `/api/admin/taxes/overrides`
Get customer-level tax overrides.

---

### POST `/api/admin/taxes/overrides`
Create a tax override rule.

**Request body:**
```json
{ "product_id": "<id>", "customer_id": "<id>", "rate": 0.0, "reason": "Exempt" }
```

---

### PUT `/api/admin/taxes/overrides/{rule_id}`
Update a tax override.

---

### DELETE `/api/admin/taxes/overrides/{rule_id}`
Delete a tax override.

---

### GET `/api/admin/taxes/invoice-settings`
Get invoice settings (numbering, branding, terms).

---

### PUT `/api/admin/taxes/invoice-settings`
Update invoice settings.

---

### GET `/api/admin/taxes/invoice-templates`
List invoice templates.

---

### POST `/api/admin/taxes/invoice-templates`
Create a new invoice template.

---

### PUT `/api/admin/taxes/invoice-templates/{tmpl_id}`
Update an invoice template.

---

### DELETE `/api/admin/taxes/invoice-templates/{tmpl_id}`
Delete an invoice template.

---

### GET `/api/admin/taxes/invoice-templates-for-viewer`
Get invoice templates for the customer-facing viewer.

---

### GET `/api/admin/taxes/summary`
Get tax collected summary report.

**Response `200`:** `{ "total_tax_collected": 5000, "by_country": { "GB": 4000, ... } }`

---

## 21. Admin — Tenants (Platform Admin Only)

These endpoints are only available to `platform_super_admin`.

### GET `/api/admin/tenants`
List all partner organisations.

**Response `200`:** `{ "tenants": [ { "id", "name", "code", "status", "created_at" } ] }`

---

### POST `/api/admin/tenants`
Create a new tenant/partner organisation.

**Request body:**
```json
{
  "name": "New Partner Org",
  "code": "new-partner",
  "status": "active",
  "base_currency": "GBP"
}
```
**Response `200`:** `{ "id": "<tenant_id>", ... }`

---

### POST `/api/admin/tenants/create-partner`
Create a partner organisation with a seed admin user.

**Request body:**
```json
{
  "name": "New Partner",
  "admin_email": "admin@newpartner.com",
  "admin_name": "Admin User",
  "admin_password": "SecurePass1!",
  "base_currency": "GBP"
}
```

---

### PUT `/api/admin/tenants/{tenant_id}`
Update a tenant's details.

---

### POST `/api/admin/tenants/{tenant_id}/activate`
Activate a tenant.

---

### POST `/api/admin/tenants/{tenant_id}/deactivate`
Deactivate a tenant.

---

### PUT `/api/admin/tenants/{tenant_id}/address`
Update a tenant's address.

---

### GET `/api/admin/tenants/my`
Get the current admin's tenant details.

---

### PUT `/api/admin/tenant-settings`
Update tenant-level settings.

---

### GET `/api/admin/tenants/{tenant_id}/license`
Get a tenant's license/plan details.

---

### PUT `/api/admin/tenants/{tenant_id}/license`
Assign or update a tenant's license plan.

**Request body:** `{ "plan_id": "<plan_id>" }`

---

### POST `/api/admin/tenants/{tenant_id}/usage/reset`
Reset a tenant's monthly usage counters.

---

### GET `/api/admin/usage`
Get usage statistics for the current tenant.

**Response `200`:** `{ "customers_this_month": 5, "limit": 50, "products_used": 3 }`

---

### GET `/api/admin/tenants/{tenant_id}/notes`
Get notes for a tenant.

---

### POST `/api/admin/tenants/{tenant_id}/notes`
Add a note to a tenant.

---

### DELETE `/api/admin/tenants/{tenant_id}/notes/{note_id}`
Delete a tenant note.

---

### POST `/api/admin/tenants/{tenant_id}/create-admin`
Create a new admin user for a tenant.

---

### GET `/api/admin/tenants/{tenant_id}/users`
List all users in a tenant.

---

### GET `/api/admin/tenants/{tenant_id}/customers`
List all customers in a tenant.

---

### GET `/api/admin/custom-domains`
List custom domains for the current tenant.

---

### POST `/api/admin/custom-domains`
Add a custom domain.

**Request body:** `{ "domain": "billing.yourcompany.com" }`

---

### PUT `/api/admin/custom-domains`
Update custom domain settings.

---

### POST `/api/admin/custom-domains/{domain}/verify`
Verify DNS ownership for a custom domain.

---

### DELETE `/api/admin/custom-domains/{domain}`
Remove a custom domain.

---

### GET `/api/admin/setup-checklist`
Get the onboarding setup checklist progress.

**Response `200`:** `{ "items": [ { "key", "label", "completed" } ], "percentage": 60 }`

---

### POST `/api/admin/tenants/{tenant_id}/transfer-super-admin`
Transfer super admin ownership to another user.

**Request body:** `{ "new_admin_email": "newadmin@org.com" }`

---

## 22. Admin — Resources

Resources are downloadable files/documents shared with customers.

### GET `/api/resources/admin/list`
List all resources for the current tenant (admin view).

**Response `200`:** `{ "resources": [ { "id", "name", "file_type", "visibility", "created_at" } ] }`

---

### GET `/api/resources/public`
List publicly available resources.

**Response `200`:** `{ "resources": [ ... ] }`

---

### GET `/api/resources/{resource_id}`
Get a specific resource.

**Auth:** required  
**Response `200`:** `{ "resource": { ... } }`

---

### GET `/api/resources/{resource_id}/download`
Download a resource file.

**Auth:** required  
**Response `200`:** Binary file stream

---

### GET `/api/resources/{resource_id}/validate-scope`
Check if the current user has access to a scope-restricted resource.

---

### POST `/api/resources`
Create/upload a new resource.

**Content-Type:** `multipart/form-data`  
**Fields:** `name`, `description`, `visibility` (all/customers/specific), `file`

**Response `200`:** `{ "id": "<resource_id>", ... }`

---

### PUT `/api/resources/{resource_id}`
Update a resource's metadata.

---

### DELETE `/api/resources/{resource_id}`
Delete a resource.

---

### POST `/api/resources/{resource_id}/email`
Email a resource to a customer via a template.

**Request body:** `{ "customer_id": "<id>", "template_id": "<id>" }`

---

### POST `/api/resources/{resource_id}/send-email`
Send a resource email directly.

**Request body:** `{ "to": "customer@example.com", "subject": "Your document", "message": "Please find attached..." }`

---

### GET `/api/resources/{resource_id}/logs`
Get audit logs for a resource.

---

## 23. Admin — Resource & Article Categories

### GET `/api/resource-categories`
List all resource categories (admin).

### GET `/api/resource-categories/public`
List public resource categories.

### POST `/api/resource-categories`
Create a new resource category.

**Request body:** `{ "name": "Guides", "description": "How-to guides", "color": "#3B82F6" }`

**Response `200`:** `{ "category": { "id", "name", ... } }`

### PUT `/api/resource-categories/{category_id}`
Update a resource category.

### DELETE `/api/resource-categories/{category_id}`
Delete a resource category.

---

### GET `/api/article-categories`
List all article categories (admin).

### GET `/api/article-categories/public`
List public article categories.

### POST `/api/article-categories`
Create a new article category.

**Request body:** `{ "name": "Tax Tips", "description": "Tax advice articles", "color": "#10B981" }`

**Response `200`:** `{ "category": { "id", "name", ... } }`

### PUT `/api/article-categories/{category_id}`
Update an article category.

### DELETE `/api/article-categories/{category_id}`
Delete an article category.

---

## 24. Admin — Articles

### GET `/api/articles/admin/list`
List all articles for the current tenant (admin view).

**Response `200`:** `{ "articles": [ { "id", "title", "slug", "status", "category" } ] }`

---

### GET `/api/articles/public`
List published articles (public).

---

### GET `/api/articles/{article_id}`
Get a specific article.

**Auth:** required  
**Response `200`:** `{ "article": { "id", "title", "content", "category", "status" } }`

---

### GET `/api/articles/{article_id}/download`
Download an article as PDF.

---

### GET `/api/articles/{article_id}/validate-scope`
Check if the current user has access to a scope-restricted article.

---

### POST `/api/articles`
Create a new article.

**Request body:**
```json
{
  "title": "2025 Tax Guide",
  "content": "<h2>Introduction</h2><p>...</p>",
  "category": "Tax Tips",
  "status": "published",
  "visibility": "all"
}
```

---

### PUT `/api/articles/{article_id}`
Update an article.

---

### DELETE `/api/articles/{article_id}`
Delete an article.

---

### POST `/api/articles/{article_id}/email`
Email an article to a customer via a template.

### POST `/api/articles/{article_id}/send-email`
Send an article email directly.

---

## 25. Admin — Forms

### GET `/api/admin/forms`
List all custom intake forms.

**Response `200`:** `{ "forms": [ { "id", "name", "schema" } ] }`

---

### POST `/api/admin/forms`
Create a new custom form.

**Request body:**
```json
{
  "name": "Product Intake Form",
  "schema": "[{\"type\":\"text\",\"key\":\"company_name\",\"label\":\"Company Name\",\"required\":true}]"
}
```
**Response `200`:** `{ "id": "<form_id>", ... }`

---

### PUT `/api/admin/forms/{form_id}`
Update a form's schema or name.

---

### DELETE `/api/admin/forms/{form_id}`
Delete a form.

---

## 26. Admin — Sync Logs & Misc

### GET `/api/admin/sync-logs`
List Zoho CRM sync logs.

**Response `200`:** `{ "logs": [ { "id", "entity_type", "entity_id", "status", "attempts" } ] }`

---

### POST `/api/admin/sync-logs/{log_id}/retry`
Retry a failed Zoho CRM sync operation.

**Response `200`:** `{ "message": "Retry queued" }`

---

### GET `/api/admin/tenant/base-currency`
Get the current tenant's base currency.

**Response `200`:** `{ "currency": "GBP" }`

---

### PUT `/api/admin/tenant/base-currency`
Update the tenant's base currency.

**Request body:** `{ "currency": "USD" }`

---

## 27. Admin — Import / Export

### GET `/api/admin/export/orders`
Export orders as CSV.

**Response `200`:** CSV file download

---

### GET `/api/admin/export/customers`
Export customers as CSV.

---

### GET `/api/admin/export/subscriptions`
Export subscriptions as CSV.

---

### GET `/api/admin/export/catalog`
Export product catalog as CSV.

---

### GET `/api/admin/export/articles`
Export articles as CSV.

---

### GET `/api/admin/export/categories`
Export categories as CSV.

---

### GET `/api/admin/export/terms`
Export terms & conditions as CSV.

---

### GET `/api/admin/export/promo-codes`
Export promo codes as CSV.

---

### GET `/api/admin/export/article-categories`
Export article categories as CSV.

---

### GET `/api/admin/export/article-templates`
Export article templates as CSV.

---

### POST `/api/admin/import/{entity}`
Import data from a CSV file.

**`entity` values:** `customers`, `products`, `orders`, `subscriptions`, `articles`, `resources`

**Content-Type:** `multipart/form-data`  
**Field:** `file` (CSV file)

**Response `200`:** `{ "imported": 25, "failed": 2, "errors": [ ... ] }`

---

### GET `/api/admin/import/template/{entity}`
Download a CSV import template for an entity type.

**Response `200`:** CSV template file

---

## 28. Admin — Audit Logs

### GET `/api/stats`
Get platform-level statistics (platform admin only).

**Response `200`:** `{ "total_tenants": 10, "total_orders": 500, ... }`

---

### GET `/api/logs`
Get audit logs with filtering.

**Query params:** `entity_type`, `entity_id`, `action`, `page`, `limit`, `date_from`, `date_to`

**Response `200`:** `{ "logs": [ { "id", "action", "entity_type", "entity_id", "actor", "created_at" } ] }`

---

### GET `/api/logs/{log_id}`
Get a specific audit log entry.

---

## 29. Admin — Store Filters

### GET `/api/admin/store-filters`
List all store filters.

**Response `200`:** `{ "filters": [ { "id", "name", "filter_type", "options", "is_active" } ], "total": 5 }`

---

### POST `/api/admin/store-filters`
Create a new store filter.

**Request body:**
```json
{
  "name": "Service Category",
  "filter_type": "category",
  "is_active": true,
  "sort_order": 1,
  "show_count": true,
  "options": null
}
```
**`filter_type` values:** `category` | `tag` | `price_range` | `plan_name` | `custom`

**Response `200`:** `{ "id": "<filter_id>", ... }`

---

### PUT `/api/admin/store-filters/{filter_id}`
Update a store filter.

---

### DELETE `/api/admin/store-filters/{filter_id}`
Delete a store filter.

---

### PATCH `/api/admin/store-filters/reorder`
Reorder store filters.

**Request body:** `{ "order": ["<filter_id_1>", "<filter_id_2>", ...] }`

---

## 30. Admin — GDPR

### GET `/api/admin/gdpr/requests`
List all GDPR deletion requests.

**Response `200`:** `{ "requests": [ { "id", "customer_id", "status", "requested_at" } ] }`

---

### GET `/api/admin/gdpr/export/{customer_id}`
Generate a GDPR data export for a customer.

---

### GET `/api/admin/gdpr/export/{customer_id}/download`
Download the GDPR export for a customer.

---

### POST `/api/admin/gdpr/delete/{customer_id}`
Permanently delete all data for a customer (GDPR right to erasure).

---

## 31. Admin — Platform Billing

These endpoints manage the billing between platform admin and partner organisations.

### GET `/api/admin/partner-orders/stats`
Get partner billing order statistics.

### GET `/api/admin/partner-orders`
List all partner billing orders.

### POST `/api/admin/partner-orders`
Create a partner billing order.

### GET `/api/admin/partner-orders/{order_id}`
Get a specific partner order.

### PUT `/api/admin/partner-orders/{order_id}`
Update a partner order.

### DELETE `/api/admin/partner-orders/{order_id}`
Delete a partner order.

### GET `/api/admin/partner-subscriptions/stats`
Get partner subscription statistics.

### GET `/api/admin/partner-subscriptions`
List all partner subscriptions.

### POST `/api/admin/partner-subscriptions`
Create a partner subscription.

### GET `/api/admin/partner-subscriptions/{sub_id}`
Get a specific partner subscription.

### PUT `/api/admin/partner-subscriptions/{sub_id}`
Update a partner subscription.

### PATCH `/api/admin/partner-subscriptions/{sub_id}/cancel`
Cancel a partner subscription.

### POST `/api/admin/partner-billing/stripe-checkout`
Create a Stripe checkout for a partner to pay their platform fee.

### POST `/api/admin/partner-subscriptions/{subscription_id}/send-reminder`
Send a payment reminder to a partner.

### GET `/api/admin/partner-orders/{order_id}/download-invoice`
Download an invoice for a partner order.

---

## 32. Partner Self-Service Endpoints

These are used by partner organisations to manage their own plan/billing.

### GET `/api/partner/my-plan`
Get the current partner's plan and usage.

**Response `200`:** `{ "plan": { "name", "limits" }, "usage": { "customers": 12, "products": 5 } }`

---

### POST `/api/partner/upgrade-plan`
Request a plan upgrade.

**Request body:** `{ "plan_id": "<plan_id>", "payment_method": "stripe" }`

---

### GET `/api/partner/upgrade-plan-status`
Check the status of a pending plan upgrade.

---

### GET `/api/partner/my-orders`
List the current partner's platform billing orders.

---

### GET `/api/partner/my-subscriptions`
List the current partner's platform subscriptions.

---

### POST `/api/partner/my-subscriptions/{sub_id}/cancel`
Cancel a platform subscription.

---

### GET `/api/partner/my-orders/{order_id}/download-invoice`
Download an invoice for a partner's own platform order.

---

### GET `/api/partner/billing/current`
Get current billing status and next payment date.

---

### POST `/api/partner/billing-portal`
Create a Stripe billing portal session for the partner to manage their own billing.

---

## 33. OAuth Provider Endpoints

These manage third-party OAuth integrations (Zoho CRM, Zoho Books, etc.).

### POST `/api/oauth/{provider}/save-credentials`
Save OAuth credentials for a provider.

**`provider` values:** `zoho_crm` | `zoho_books` | `zoho_mail` | `workdrive`

### POST `/api/oauth/{provider}/validate`
Validate the OAuth connection for a provider.

### GET `/api/oauth/{provider}/settings`
Get stored settings for a provider.

### GET `/api/oauth/integrations`
List all configured OAuth integrations.

### POST `/api/oauth/{provider}/update-settings`
Update settings for a provider.

### POST `/api/oauth/{provider}/activate`
Activate an integration provider.

### POST `/api/oauth/{provider}/deactivate`
Deactivate an integration provider.

### DELETE `/api/oauth/{provider}/disconnect`
Disconnect and remove an integration.

### GET `/api/oauth/{provider}/status`
Get the connection status for a specific provider.

### POST `/api/oauth/zoho_crm/bulk-sync`
Trigger a full bulk sync from the application to Zoho CRM for all 13 modules.

**Response `200`:**
```json
{
  "synced": {
    "customers": 45,
    "orders": 120,
    "subscriptions": 30,
    "products": 10,
    "categories": 5,
    "plans": 3,
    "terms": 2,
    "promo_codes": 8,
    "resources": 15,
    "enquiries": 7,
    "invoices": 100,
    "refunds": 5,
    "addresses": 45
  }
}
```

### POST `/api/oauth/zoho_books/bulk-sync`
Trigger a full bulk sync to Zoho Books.

---

## 34. Documents

### GET `/api/documents`
List documents for the current user.

**Auth:** required

---

### POST `/api/documents/upload`
Upload a document (admin).

**Content-Type:** `multipart/form-data`  
**Fields:** `file`, `customer_id`, `name`

---

### GET `/api/documents/{doc_id}/download`
Download a document.

---

### PUT `/api/admin/documents/{doc_id}`
Update document metadata.

---

### DELETE `/api/admin/documents/{doc_id}`
Delete a document.

---

### POST `/api/admin/workdrive/sync-folders`
Sync customer folders to Zoho WorkDrive.

---

### GET `/api/admin/documents/{doc_id}/logs`
Get audit logs for a document.

---

## 35. Utility Endpoints

### GET `/api/utils/countries`
Get a list of all countries (ISO codes and names).

**Response `200`:** `{ "countries": [ { "code": "GB", "name": "United Kingdom" }, ... ] }`

---

### GET `/api/utils/provinces`
Get provinces/states for a country.

**Query params:** `country_code=US` (required)

**Response `200`:** `{ "provinces": [ { "code": "CA", "name": "California" }, ... ] }`

---

### GET `/api/references`
Get public reference data (for dropdown fields).

### GET `/api/admin/references`
Get all reference data (admin).

### POST `/api/admin/references`
Create reference data.

### PUT `/api/admin/references/{ref_id}`
Update reference data.

### DELETE `/api/admin/references/{ref_id}`
Delete reference data.

---

## 36. Webhooks (Incoming)

### POST `/api/webhook/stripe`
Stripe webhook receiver (for processing payment events).

**Auth:** Stripe signature verification (`Stripe-Signature` header)

---

### POST `/api/webhook/gocardless`
GoCardless webhook receiver.

**Auth:** GoCardless signature verification

---

## 37. Uploads

### POST `/api/uploads`
Upload a file (generic, for images etc.).

**Content-Type:** `multipart/form-data`  
**Field:** `file`

**Response `200`:** `{ "id": "<upload_id>", "url": "https://..." }`

---

### GET `/api/uploads/{upload_id}`
Get upload metadata by ID.

---

## Error Responses

| Code | Meaning |
|---|---|
| `400` | Bad request (missing or invalid fields) |
| `401` | Authentication required or invalid token |
| `403` | Access denied (wrong role or inactive account) |
| `404` | Resource not found |
| `422` | Validation error (Pydantic model mismatch) |
| `429` | Rate limited or account locked out |
| `500` | Internal server error |

**Error body:**
```json
{ "detail": "Human-readable error message" }
```

For `422` errors, additional detail is available:
```json
{
  "detail": "Validation failed",
  "errors": [
    { "type": "missing", "loc": ["body", "field_name"], "msg": "Field required" }
  ]
}
```

---

## Quick-Start Test Script

```bash
API_URL="https://platform-health-scan.preview.emergentagent.com"

# 1. Login as platform admin
TOKEN=$(curl -s -X POST "$API_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@automateaccounts.local","password":"ChangeMe123!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

H="Authorization: Bearer $TOKEN"

# 2. List products
curl -s "$API_URL/api/admin/products-all" -H "$H" | python3 -m json.tool

# 3. List customers
curl -s "$API_URL/api/admin/customers" -H "$H" | python3 -m json.tool

# 4. Create a promo code
curl -s -X POST "$API_URL/api/admin/promo-codes" \
  -H "Content-Type: application/json" \
  -H "$H" \
  -d '{"code":"LAUNCH20","discount_type":"percentage","discount_value":20,"enabled":true,"applies_to":"both"}'
```
