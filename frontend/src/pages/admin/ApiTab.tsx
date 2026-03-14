import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/sonner";
import { Copy, RefreshCw, Trash2, ChevronDown, ChevronRight, Play, Key, BookOpen, Info, AlertCircle } from "lucide-react";
import api from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Param {
  name: string;
  in: "query" | "path" | "header" | "body";
  type: string;
  required?: boolean;
  description: string;
  example?: string;
}

interface EndpointDef {
  method: "GET" | "POST" | "PUT" | "DELETE" | "PATCH";
  path: string;
  summary: string;
  description: string;
  /**
   * "api-key"      = X-API-Key only (public/tenant endpoints)
   * "customer-jwt" = X-API-Key + customer Bearer JWT
   * "admin-jwt"    = admin Bearer JWT only (from /api/auth/partner-login)
   */
  auth: "api-key" | "customer-jwt" | "admin-jwt";
  tags: string[];
  params?: Param[];
  bodySchema?: Record<string, any>;
  responseExample?: Record<string, any>;
}

// ── Endpoint Definitions ──────────────────────────────────────────────────────

const API_ENDPOINTS: EndpointDef[] = [
  // ── Authentication ────────────────────────────────────────────────────────
  {
    method: "GET", path: "/api/tenant-info", auth: "api-key", tags: ["Authentication"],
    summary: "Verify API Key / Get tenant info",
    description: "Verify your API key is valid and return basic tenant information. Pass either X-API-Key header (preferred) or ?code= query parameter.",
    params: [{ name: "code", in: "query", type: "string", required: false, description: "Partner code (optional — omit to resolve from X-API-Key)", example: "your-partner-code" }],
    responseExample: { tenant_id: "your-tenant-id", name: "Your Company Ltd", code: "your-partner-code" },
  },
  {
    method: "POST", path: "/api/auth/customer-login", auth: "api-key", tags: ["Authentication"],
    summary: "Login as customer (get JWT)",
    description: "Authenticate a customer with email and password. Returns a JWT token used for all customer-specific endpoints. Pass X-API-Key to identify the tenant.",
    bodySchema: { email: "string", password: "string" },
    responseExample: { token: "eyJhbGci...", role: "customer", tenant_id: "your-tenant-id" },
  },
  {
    method: "POST", path: "/api/auth/register", auth: "api-key", tags: ["Authentication"],
    summary: "Register a new customer",
    description: "Register a new customer account under your tenant. A verification email is sent.",
    bodySchema: { email: "string", password: "string", full_name: "string", company_name: "string (optional)", partner_code: "your-partner-code" },
    responseExample: { success: true, message: "Verification email sent" },
  },
  {
    method: "POST", path: "/api/auth/verify-email", auth: "api-key", tags: ["Authentication"],
    summary: "Verify customer email",
    description: "Verify a customer's email address using the OTP code or token sent in the verification email.",
    bodySchema: { email: "string", code: "string (OTP)", partner_code: "your-partner-code" },
    responseExample: { success: true, message: "Email verified" },
  },
  {
    method: "POST", path: "/api/auth/resend-verification-email", auth: "api-key", tags: ["Authentication"],
    summary: "Resend verification email",
    description: "Resend the email verification link to an unverified customer.",
    bodySchema: { email: "string", partner_code: "your-partner-code" },
    responseExample: { success: true },
  },
  {
    method: "POST", path: "/api/auth/forgot-password", auth: "api-key", tags: ["Authentication"],
    summary: "Request password reset",
    description: "Send a password reset OTP to a customer's email. Always returns success to prevent email enumeration.",
    bodySchema: { email: "string", partner_code: "your-partner-code" },
    responseExample: { message: "If an account with that email exists, a reset code has been sent." },
  },
  {
    method: "POST", path: "/api/auth/reset-password", auth: "api-key", tags: ["Authentication"],
    summary: "Reset password with OTP",
    description: "Set a new password using the OTP received via forgot-password email.",
    bodySchema: { email: "string", partner_code: "your-partner-code", code: "123456", new_password: "NewPassword1!" },
    responseExample: { message: "Password reset successfully" },
  },
  // ── Catalog ───────────────────────────────────────────────────────────────
  {
    method: "GET", path: "/api/categories", auth: "api-key", tags: ["Catalog"],
    summary: "List product categories",
    description: "Returns all active product categories with optional blurb text.",
    responseExample: { categories: ["Bookkeeping", "Tax Returns"], category_blurbs: { "Bookkeeping": "Monthly bookkeeping services" } },
  },
  {
    method: "GET", path: "/api/products", auth: "api-key", tags: ["Catalog"],
    summary: "List all products",
    description: "Returns all active, publicly visible products. When called with a customer JWT, respects customer-level visibility restrictions.",
    responseExample: { products: [{ id: "prod_xxx", name: "Starter Package", base_price: 499, billing_period: "monthly", category: "Bookkeeping" }] },
  },
  {
    method: "GET", path: "/api/products/{id}", auth: "api-key", tags: ["Catalog"],
    summary: "Get product details",
    description: "Returns full product details including pricing schema and intake fields. Use intake_schema_json to build a dynamic quote form.",
    params: [{ name: "id", in: "path", type: "string", required: true, description: "Product ID", example: "prod_abc123" }],
    responseExample: { product: { id: "prod_xxx", name: "Starter Package", pricing_type: "dynamic", billing_period: "monthly", intake_schema_json: [] } },
  },
  {
    method: "POST", path: "/api/pricing/calc", auth: "customer-jwt", tags: ["Catalog"],
    summary: "Calculate dynamic pricing",
    description: "Calculate the price for a product given customer-specific inputs. Use the product's intake_schema_json to determine required inputs. Requires customer JWT.",
    bodySchema: { product_id: "string", inputs: { field_name: "value" } },
    responseExample: { product_id: "prod_xxx", total: 699, line_items: [{ label: "Base fee", amount: 499 }] },
  },
  // ── Terms & Conditions ─────────────────────────────────────────────────────
  {
    method: "GET", path: "/api/terms", auth: "api-key", tags: ["Terms & Conditions"],
    summary: "List T&C documents",
    description: "Returns all Terms & Conditions documents published by the tenant.",
    responseExample: { terms: [{ id: "terms_xxx", title: "Standard Service Agreement", status: "active", is_default: true }] },
  },
  {
    method: "GET", path: "/api/terms/{id}", auth: "api-key", tags: ["Terms & Conditions"],
    summary: "Get T&C by ID",
    description: "Returns the full content of a specific Terms & Conditions document.",
    params: [{ name: "id", in: "path", type: "string", required: true, description: "Terms document ID", example: "terms_abc123" }],
    responseExample: { terms: { id: "terms_xxx", title: "Standard Service Agreement", content: "<h1>Terms</h1>..." } },
  },
  // ── Articles ──────────────────────────────────────────────────────────────
  {
    method: "GET", path: "/api/articles/public", auth: "api-key", tags: ["Articles"],
    summary: "List published articles",
    description: "Returns all published, public articles. When called with a customer JWT, returns articles visible to that customer.",
    params: [{ name: "category", in: "query", type: "string", required: false, description: "Filter by category slug", example: "guides" }],
    responseExample: { articles: [{ id: "art_xxx", title: "Getting Started", category: "Guides", published: true }] },
  },
  {
    method: "GET", path: "/api/articles/{id}", auth: "api-key", tags: ["Articles"],
    summary: "Get article by ID",
    description: "Returns the full HTML content of a specific article.",
    params: [{ name: "id", in: "path", type: "string", required: true, description: "Article ID", example: "art_abc123" }],
    responseExample: { article: { id: "art_xxx", title: "Getting Started", content: "<h1>Welcome</h1>..." } },
  },
  {
    method: "GET", path: "/api/article-categories/public", auth: "api-key", tags: ["Articles"],
    summary: "List article categories",
    description: "Returns all article categories available for the tenant.",
    responseExample: { categories: [{ id: "cat_xxx", name: "Guides", color: "#1e40af" }] },
  },
  // ── Resources ─────────────────────────────────────────────────────────────
  {
    method: "GET", path: "/api/resources/public", auth: "api-key", tags: ["Resources"],
    summary: "List public resources",
    description: "Returns all publicly available resources (downloads, documents, guides).",
    responseExample: { resources: [{ id: "res_xxx", name: "2025 Tax Guide.pdf", file_type: "pdf", visibility: "all" }] },
  },
  {
    method: "GET", path: "/api/resource-categories/public", auth: "api-key", tags: ["Resources"],
    summary: "List resource categories",
    description: "Returns all public resource categories.",
    responseExample: { categories: [{ id: "cat_xxx", name: "Guides", color: "#3B82F6" }] },
  },
  // ── Quote / Scope Requests ────────────────────────────────────────────────
  {
    method: "POST", path: "/api/orders/scope-request-form", auth: "api-key", tags: ["Quote Requests"],
    summary: "Submit a quote request",
    description: "Submit a scope/quote request without customer auth. Suitable for public-facing quote forms. Associates the request with the tenant via X-API-Key.",
    bodySchema: { items: [{ product_id: "string", quantity: 1, inputs: {} }], form_data: { name: "string (required)", email: "string (required)", company: "string (optional)", phone: "string (optional)", message: "string (optional)" } },
    responseExample: { success: true, message: "Your request has been received", request_id: "req_xxx" },
  },
  {
    method: "POST", path: "/api/orders/preview", auth: "customer-jwt", tags: ["Quote Requests"],
    summary: "Preview order pricing",
    description: "Calculate and preview the full pricing for a potential order before checkout. Requires customer JWT.",
    bodySchema: { items: [{ product_id: "string", quantity: 1, inputs: { field_key: "value" } }] },
    responseExample: { subtotal: 499, discount: 50, fee: 10, total: 459, line_items: [] },
  },
  {
    method: "POST", path: "/api/promo-codes/validate", auth: "customer-jwt", tags: ["Quote Requests"],
    summary: "Validate a promo code",
    description: "Check if a promo code is valid and return its discount details. Requires customer JWT.",
    bodySchema: { code: "string (required)", checkout_type: "one_time | subscription (required)", product_ids: ["prod_xxx"], currency: "USD (optional)" },
    responseExample: { valid: true, discount_type: "percentage", discount_value: 20, applies_to: "all" },
  },
  // ── Checkout ──────────────────────────────────────────────────────────────
  {
    method: "POST", path: "/api/checkout/session", auth: "customer-jwt", tags: ["Checkout"],
    summary: "Create Stripe checkout session",
    description: "Create a Stripe-hosted checkout session. Returns a redirect URL to the Stripe payment page.",
    bodySchema: { items: [{ product_id: "string (required)", quantity: 1, inputs: {} }], promo_code: "string (optional)", terms_accepted: true, terms_id: "string (optional)", origin_url: "string (required)" },
    responseExample: { url: "https://checkout.stripe.com/...", session_id: "cs_xxx", order_id: "ord_xxx" },
  },
  {
    method: "GET", path: "/api/checkout/status/{session_id}", auth: "customer-jwt", tags: ["Checkout"],
    summary: "Get checkout session status",
    description: "Check the status of a Stripe checkout session after the customer returns from the payment page.",
    params: [{ name: "session_id", in: "path", type: "string", required: true, description: "Stripe session ID", example: "cs_xxx" }],
    responseExample: { status: "paid", order_id: "ord_xxx", amount_total: 49900, currency: "usd" },
  },
  {
    method: "POST", path: "/api/checkout/bank-transfer", auth: "customer-jwt", tags: ["Checkout"],
    summary: "Initiate GoCardless Direct Debit",
    description: "Create a GoCardless Direct Debit setup for a subscription. Returns a redirect URL for the customer to complete bank authorisation.",
    bodySchema: { product_id: "string", promo_code: "string (optional)", terms_accepted: true, intake_answers: {} },
    responseExample: { order_id: "ord_xxx", gocardless_redirect_url: "https://pay.gocardless.com/...", status: "pending_direct_debit_setup" },
  },
  {
    method: "POST", path: "/api/checkout/free", auth: "customer-jwt", tags: ["Checkout"],
    summary: "Place a free order",
    description: "Place an order for a product priced at £0.00 — no payment processor required.",
    bodySchema: { items: [{ product_id: "string", quantity: 1, inputs: {} }], terms_accepted: true },
    responseExample: { order_id: "ord_xxx", order_number: "AA-XXXX" },
  },
  // ── Customer Portal ───────────────────────────────────────────────────────
  {
    method: "GET", path: "/api/me", auth: "customer-jwt", tags: ["Customer Portal"],
    summary: "Get current user profile",
    description: "Returns the authenticated customer's profile, customer record, and address.",
    responseExample: { user: { id: "usr_xxx", email: "jane@example.com", full_name: "Jane Smith" }, customer: {}, address: {} },
  },
  {
    method: "PUT", path: "/api/me", auth: "customer-jwt", tags: ["Customer Portal"],
    summary: "Update customer profile",
    description: "Update the authenticated customer's name, company, phone, and address.",
    bodySchema: { full_name: "string (optional)", company_name: "string (optional)", phone: "string (optional)", address: { line1: "", city: "", postal: "", country: "" } },
    responseExample: { success: true },
  },
  {
    method: "GET", path: "/api/orders", auth: "customer-jwt", tags: ["Customer Portal"],
    summary: "List customer orders",
    description: "Returns all orders for the authenticated customer, including line items.",
    responseExample: { orders: [{ id: "ord_xxx", order_number: "ORD-001", status: "complete", total_amount: 499 }], items: [] },
  },
  {
    method: "GET", path: "/api/orders/{id}", auth: "customer-jwt", tags: ["Customer Portal"],
    summary: "Get order details",
    description: "Returns full details of a specific order including all line items.",
    params: [{ name: "id", in: "path", type: "string", required: true, description: "Order ID", example: "ord_abc123" }],
    responseExample: { order: { id: "ord_xxx", order_number: "ORD-001", status: "complete", total_amount: 499 }, items: [{ product_name: "Starter Package", quantity: 1, amount: 499 }] },
  },
  {
    method: "GET", path: "/api/subscriptions", auth: "customer-jwt", tags: ["Customer Portal"],
    summary: "List customer subscriptions",
    description: "Returns all subscriptions for the authenticated customer.",
    responseExample: { subscriptions: [{ id: "sub_xxx", product_name: "Starter Package", status: "active", billing_period: "monthly", next_billing_date: "2026-04-01" }] },
  },
  {
    method: "POST", path: "/api/subscriptions/{id}/cancel", auth: "customer-jwt", tags: ["Customer Portal"],
    summary: "Cancel a subscription",
    description: "Request cancellation of a subscription. It remains active until end of billing period.",
    params: [{ name: "id", in: "path", type: "string", required: true, description: "Subscription ID", example: "sub_abc123" }],
    bodySchema: { reason: "string (optional)" },
    responseExample: { success: true, message: "Subscription will be cancelled at end of billing period" },
  },

  // ══════════════════════════════════════════════════════════════════════════
  // ADMIN ENDPOINTS (require Admin JWT from /api/auth/partner-login)
  // ══════════════════════════════════════════════════════════════════════════

  // ── Admin — Catalog ───────────────────────────────────────────────────────
  {
    method: "GET", path: "/api/admin/products-all", auth: "admin-jwt", tags: ["Admin — Catalog"],
    summary: "List all products (admin)",
    description: "Returns all products for your tenant including inactive ones. Supports pagination and filtering.",
    params: [
      { name: "page", in: "query", type: "integer", required: false, description: "Page number", example: "1" },
      { name: "limit", in: "query", type: "integer", required: false, description: "Results per page (max 100)", example: "20" },
      { name: "search", in: "query", type: "string", required: false, description: "Search by name", example: "bookkeeping" },
      { name: "is_active", in: "query", type: "boolean", required: false, description: "Filter by active status", example: "true" },
    ],
    responseExample: { products: [{ id: "prod_xxx", name: "Starter Package", is_active: true, base_price: 499 }], total: 12 },
  },
  {
    method: "POST", path: "/api/admin/products", auth: "admin-jwt", tags: ["Admin — Catalog"],
    summary: "Create a product",
    description: "Create a new service or product in your catalogue.",
    bodySchema: { name: "Bookkeeping Service", description: "Monthly bookkeeping.", category: "Accounting", is_active: true, currency: "GBP", pricing_type: "fixed", base_price: 199.00, billing_period: "monthly" },
    responseExample: { id: "prod_xxx", name: "Bookkeeping Service" },
  },
  {
    method: "PUT", path: "/api/admin/products/{product_id}", auth: "admin-jwt", tags: ["Admin — Catalog"],
    summary: "Update a product",
    description: "Update any field on an existing product.",
    params: [{ name: "product_id", in: "path", type: "string", required: true, description: "Product ID", example: "prod_abc123" }],
    bodySchema: { name: "Updated Name", base_price: 249.00, is_active: true },
    responseExample: { id: "prod_xxx", name: "Updated Name" },
  },
  {
    method: "GET", path: "/api/admin/categories", auth: "admin-jwt", tags: ["Admin — Catalog"],
    summary: "List categories (admin)",
    description: "Returns all product categories including inactive ones.",
    responseExample: { categories: [{ id: "cat_xxx", name: "Accounting", is_active: true }] },
  },
  {
    method: "POST", path: "/api/admin/categories", auth: "admin-jwt", tags: ["Admin — Catalog"],
    summary: "Create a category",
    description: "Create a new product category.",
    bodySchema: { name: "Tax & Compliance", description: "Tax filing and compliance services.", is_active: true },
    responseExample: { id: "cat_xxx", name: "Tax & Compliance" },
  },
  {
    method: "PUT", path: "/api/admin/categories/{cat_id}", auth: "admin-jwt", tags: ["Admin — Catalog"],
    summary: "Update a category",
    params: [{ name: "cat_id", in: "path", type: "string", required: true, description: "Category ID", example: "cat_abc123" }],
    bodySchema: { name: "Updated Name", is_active: false },
    description: "Update a product category's name, description, or active status.",
    responseExample: { id: "cat_xxx", name: "Updated Name" },
  },
  {
    method: "DELETE", path: "/api/admin/categories/{cat_id}", auth: "admin-jwt", tags: ["Admin — Catalog"],
    summary: "Delete a category",
    description: "Delete a product category. Fails if active products are using it.",
    params: [{ name: "cat_id", in: "path", type: "string", required: true, description: "Category ID", example: "cat_abc123" }],
    responseExample: { message: "Category deleted" },
  },
  // ── Admin — Customers ─────────────────────────────────────────────────────
  {
    method: "GET", path: "/api/admin/customers/stats", auth: "admin-jwt", tags: ["Admin — Customers"],
    summary: "Customer statistics",
    description: "Returns high-level stats: total customers, new this month, active/inactive counts.",
    responseExample: { total: 100, new_this_month: 12, active: 88, inactive: 12 },
  },
  {
    method: "GET", path: "/api/admin/customers", auth: "admin-jwt", tags: ["Admin — Customers"],
    summary: "List customers",
    description: "Returns a paginated list of customers with optional search and status filtering.",
    params: [
      { name: "search", in: "query", type: "string", required: false, description: "Search by name/email", example: "jane" },
      { name: "page", in: "query", type: "integer", required: false, description: "Page number", example: "1" },
      { name: "limit", in: "query", type: "integer", required: false, description: "Results per page", example: "25" },
    ],
    responseExample: { customers: [{ id: "cust_xxx", full_name: "Jane Smith", email: "jane@example.com", company_name: "Smith Ltd" }], total: 100 },
  },
  {
    method: "POST", path: "/api/admin/customers/create", auth: "admin-jwt", tags: ["Admin — Customers"],
    summary: "Create a customer (admin)",
    description: "Create a new customer account on behalf of a customer. Bypasses the email verification flow if mark_verified is true.",
    bodySchema: { email: "newcustomer@example.com", password: "TempPass1!", full_name: "Jane Smith", company_name: "Smith Ltd", job_title: "CEO", phone: "+44 7700 900001", country: "GB", mark_verified: true },
    responseExample: { customer_id: "cust_xxx", user_id: "usr_xxx" },
  },
  {
    method: "PUT", path: "/api/admin/customers/{customer_id}", auth: "admin-jwt", tags: ["Admin — Customers"],
    summary: "Update a customer",
    description: "Update a customer's profile and/or address. Both customer_data and address_data are optional objects.",
    params: [{ name: "customer_id", in: "path", type: "string", required: true, description: "Customer ID", example: "cust_abc123" }],
    bodySchema: { customer_data: { full_name: "Jane Smith", company_name: "Smith Ltd", job_title: "Director", phone: "+44 7700 900001" }, address_data: { line1: "1 New Street", city: "London", postal: "EC1A 1AA", country: "GB" } },
    responseExample: { message: "Customer updated successfully" },
  },
  {
    method: "PATCH", path: "/api/admin/customers/{customer_id}/active", auth: "admin-jwt", tags: ["Admin — Customers"],
    summary: "Activate/deactivate a customer",
    description: "Set the active status of a customer account.",
    params: [{ name: "customer_id", in: "path", type: "string", required: true, description: "Customer ID", example: "cust_abc123" }],
    bodySchema: { is_active: false },
    responseExample: { message: "Customer deactivated" },
  },
  {
    method: "GET", path: "/api/admin/customers/{customer_id}/notes", auth: "admin-jwt", tags: ["Admin — Customers"],
    summary: "Get customer notes",
    description: "Returns all internal notes added to a customer's record.",
    params: [{ name: "customer_id", in: "path", type: "string", required: true, description: "Customer ID", example: "cust_abc123" }],
    responseExample: { notes: [{ id: "note_xxx", note: "Prefers email contact", created_at: "2026-01-01T00:00:00Z" }] },
  },
  {
    method: "POST", path: "/api/admin/customers/{customer_id}/notes", auth: "admin-jwt", tags: ["Admin — Customers"],
    summary: "Add a customer note",
    description: "Add an internal note to a customer record. Notes are only visible to admins.",
    params: [{ name: "customer_id", in: "path", type: "string", required: true, description: "Customer ID", example: "cust_abc123" }],
    bodySchema: { note: "Customer prefers email contact. Do not call." },
    responseExample: { id: "note_xxx", note: "Customer prefers email contact." },
  },
  // ── Admin — Orders ────────────────────────────────────────────────────────
  {
    method: "GET", path: "/api/admin/orders/stats", auth: "admin-jwt", tags: ["Admin — Orders"],
    summary: "Order statistics",
    description: "Returns order stats: total orders, revenue this month, pending count, etc.",
    responseExample: { total: 250, revenue_this_month: 15000, pending: 5 },
  },
  {
    method: "GET", path: "/api/admin/orders", auth: "admin-jwt", tags: ["Admin — Orders"],
    summary: "List orders",
    description: "Returns a paginated list of all orders with filtering by status, customer, and date range.",
    params: [
      { name: "search", in: "query", type: "string", required: false, description: "Search by order number or customer name", example: "ORD-001" },
      { name: "status", in: "query", type: "string", required: false, description: "Filter by status (pending, confirmed, completed)", example: "confirmed" },
      { name: "page", in: "query", type: "integer", required: false, description: "Page number", example: "1" },
    ],
    responseExample: { orders: [{ id: "ord_xxx", order_number: "ORD-001", customer_name: "Jane Smith", total_amount: 499, status: "confirmed" }], total: 250 },
  },
  {
    method: "POST", path: "/api/admin/orders/manual", auth: "admin-jwt", tags: ["Admin — Orders"],
    summary: "Create manual order",
    description: "Create an order on behalf of a customer, bypassing the checkout flow.",
    bodySchema: { customer_id: "cust_xxx", items: [{ product_id: "prod_xxx", quantity: 1, inputs: {} }], payment_method: "manual", status: "confirmed", internal_note: "Created manually" },
    responseExample: { id: "ord_xxx", order_number: "ORD-001" },
  },
  {
    method: "PUT", path: "/api/admin/orders/{order_id}", auth: "admin-jwt", tags: ["Admin — Orders"],
    summary: "Update an order",
    description: "Update an order's status, internal notes, or payment date.",
    params: [{ name: "order_id", in: "path", type: "string", required: true, description: "Order ID", example: "ord_abc123" }],
    bodySchema: { status: "completed", internal_note: "Order fulfilled and delivered." },
    responseExample: { message: "Order updated" },
  },
  {
    method: "DELETE", path: "/api/admin/orders/{order_id}", auth: "admin-jwt", tags: ["Admin — Orders"],
    summary: "Delete an order",
    description: "Delete an order record.",
    params: [{ name: "order_id", in: "path", type: "string", required: true, description: "Order ID", example: "ord_abc123" }],
    responseExample: { message: "Order deleted" },
  },
  {
    method: "POST", path: "/api/admin/orders/{order_id}/refund", auth: "admin-jwt", tags: ["Admin — Orders"],
    summary: "Process a refund",
    description: "Issue a full or partial refund for an order.",
    params: [{ name: "order_id", in: "path", type: "string", required: true, description: "Order ID", example: "ord_abc123" }],
    bodySchema: { amount: 50.00, reason: "Customer request", refund_method: "stripe" },
    responseExample: { refund_id: "ref_xxx", status: "processed" },
  },
  // ── Admin — Enquiries ─────────────────────────────────────────────────────
  {
    method: "GET", path: "/api/admin/enquiries", auth: "admin-jwt", tags: ["Admin — Enquiries"],
    summary: "List enquiries",
    description: "Returns all scope/quote enquiries with optional status filtering.",
    params: [
      { name: "status", in: "query", type: "string", required: false, description: "Filter by status (new, in_review, quoted, closed)", example: "new" },
      { name: "page", in: "query", type: "integer", required: false, description: "Page number", example: "1" },
    ],
    responseExample: { orders: [{ id: "enq_xxx", order_number: "ENQ-001", customer_name: "Jane Smith", status: "new" }], total: 15 },
  },
  {
    method: "PATCH", path: "/api/admin/enquiries/{order_id}/status", auth: "admin-jwt", tags: ["Admin — Enquiries"],
    summary: "Update enquiry status",
    description: "Update the status of an enquiry.",
    params: [{ name: "order_id", in: "path", type: "string", required: true, description: "Enquiry (order) ID", example: "enq_abc123" }],
    bodySchema: { status: "in_review" },
    responseExample: { message: "Status updated" },
  },
  {
    method: "DELETE", path: "/api/admin/enquiries/{order_id}", auth: "admin-jwt", tags: ["Admin — Enquiries"],
    summary: "Delete an enquiry",
    description: "Permanently delete an enquiry record.",
    params: [{ name: "order_id", in: "path", type: "string", required: true, description: "Enquiry (order) ID", example: "enq_abc123" }],
    responseExample: { message: "Enquiry deleted" },
  },
  // ── Admin — Subscriptions ─────────────────────────────────────────────────
  {
    method: "GET", path: "/api/admin/subscriptions/stats", auth: "admin-jwt", tags: ["Admin — Subscriptions"],
    summary: "Subscription statistics",
    description: "Returns subscription stats: total, active, MRR, churn rate.",
    responseExample: { total: 80, active: 65, mrr: 12500 },
  },
  {
    method: "GET", path: "/api/admin/subscriptions", auth: "admin-jwt", tags: ["Admin — Subscriptions"],
    summary: "List subscriptions",
    description: "Returns a paginated list of subscriptions with optional status and customer filtering.",
    params: [
      { name: "search", in: "query", type: "string", required: false, description: "Search by customer name or product", example: "jane" },
      { name: "status", in: "query", type: "string", required: false, description: "Filter by status (active, paused, cancelled)", example: "active" },
      { name: "page", in: "query", type: "integer", required: false, description: "Page number", example: "1" },
    ],
    responseExample: { subscriptions: [{ id: "sub_xxx", customer_name: "Jane Smith", product_name: "Starter", status: "active", amount: 199 }], total: 80 },
  },
  {
    method: "POST", path: "/api/admin/subscriptions/manual", auth: "admin-jwt", tags: ["Admin — Subscriptions"],
    summary: "Create manual subscription",
    description: "Create a subscription record manually outside of the checkout flow.",
    bodySchema: { customer_id: "cust_xxx", product_id: "prod_xxx", plan_description: "Monthly Bookkeeping", amount: 199.00, currency: "GBP", billing_period: "monthly", start_date: "2026-01-01", payment_method: "bank_transfer", status: "active" },
    responseExample: { id: "sub_xxx" },
  },
  {
    method: "PUT", path: "/api/admin/subscriptions/{subscription_id}", auth: "admin-jwt", tags: ["Admin — Subscriptions"],
    summary: "Update a subscription",
    description: "Update a subscription's status, amount, or notes.",
    params: [{ name: "subscription_id", in: "path", type: "string", required: true, description: "Subscription ID", example: "sub_abc123" }],
    bodySchema: { status: "paused", internal_note: "Customer on holiday until April" },
    responseExample: { message: "Subscription updated" },
  },
  {
    method: "POST", path: "/api/admin/subscriptions/{subscription_id}/cancel", auth: "admin-jwt", tags: ["Admin — Subscriptions"],
    summary: "Cancel a subscription",
    description: "Cancel a subscription. Can cancel immediately or at end of billing period.",
    params: [{ name: "subscription_id", in: "path", type: "string", required: true, description: "Subscription ID", example: "sub_abc123" }],
    bodySchema: { reason: "Customer request", cancel_immediately: false },
    responseExample: { message: "Subscription cancelled" },
  },
  {
    method: "POST", path: "/api/admin/subscriptions/{subscription_id}/send-reminder", auth: "admin-jwt", tags: ["Admin — Subscriptions"],
    summary: "Send renewal reminder",
    description: "Send a renewal reminder email to the customer for a subscription.",
    params: [{ name: "subscription_id", in: "path", type: "string", required: true, description: "Subscription ID", example: "sub_abc123" }],
    bodySchema: {},
    responseExample: { message: "Reminder sent" },
  },
  // ── Admin — Terms & Conditions ────────────────────────────────────────────
  {
    method: "GET", path: "/api/admin/terms", auth: "admin-jwt", tags: ["Admin — Terms & Promo"],
    summary: "List T&C documents (admin)",
    description: "Returns all Terms & Conditions documents including drafts and inactive versions.",
    responseExample: { terms: [{ id: "terms_xxx", title: "Service Agreement v2", status: "active", is_default: true }] },
  },
  {
    method: "POST", path: "/api/admin/terms", auth: "admin-jwt", tags: ["Admin — Terms & Promo"],
    summary: "Create a T&C document",
    description: "Create a new Terms & Conditions document.",
    bodySchema: { title: "Service Agreement v2", content: "<h2>Terms</h2><p>...</p>", status: "active", is_default: false },
    responseExample: { id: "terms_xxx", title: "Service Agreement v2" },
  },
  {
    method: "PUT", path: "/api/admin/terms/{terms_id}", auth: "admin-jwt", tags: ["Admin — Terms & Promo"],
    summary: "Update a T&C document",
    params: [{ name: "terms_id", in: "path", type: "string", required: true, description: "Terms document ID", example: "terms_abc123" }],
    bodySchema: { title: "Updated Title", content: "<p>Updated content</p>", status: "active" },
    description: "Update the title, content, or status of a T&C document.",
    responseExample: { id: "terms_xxx", title: "Updated Title" },
  },
  {
    method: "DELETE", path: "/api/admin/terms/{terms_id}", auth: "admin-jwt", tags: ["Admin — Terms & Promo"],
    summary: "Delete a T&C document",
    description: "Delete a Terms & Conditions document.",
    params: [{ name: "terms_id", in: "path", type: "string", required: true, description: "Terms document ID", example: "terms_abc123" }],
    responseExample: { message: "Terms deleted" },
  },
  // ── Admin — Promo Codes ───────────────────────────────────────────────────
  {
    method: "GET", path: "/api/admin/promo-codes", auth: "admin-jwt", tags: ["Admin — Terms & Promo"],
    summary: "List promo codes",
    description: "Returns all promotional codes for the tenant.",
    responseExample: { promo_codes: [{ id: "promo_xxx", code: "SAVE20", discount_type: "percentage", discount_value: 20, enabled: true }] },
  },
  {
    method: "POST", path: "/api/admin/promo-codes", auth: "admin-jwt", tags: ["Admin — Terms & Promo"],
    summary: "Create a promo code",
    description: "Create a new promotional discount code.",
    bodySchema: { code: "SAVE20", discount_type: "percentage", discount_value: 20, enabled: true, applies_to: "both", max_uses: 100, expiry_date: "2026-12-31T23:59:59Z" },
    responseExample: { id: "promo_xxx", code: "SAVE20" },
  },
  {
    method: "PUT", path: "/api/admin/promo-codes/{code_id}", auth: "admin-jwt", tags: ["Admin — Terms & Promo"],
    summary: "Update a promo code",
    params: [{ name: "code_id", in: "path", type: "string", required: true, description: "Promo code ID", example: "promo_abc123" }],
    bodySchema: { enabled: false, max_uses: 50 },
    description: "Update a promo code's settings or disable it.",
    responseExample: { id: "promo_xxx", code: "SAVE20", enabled: false },
  },
  {
    method: "DELETE", path: "/api/admin/promo-codes/{code_id}", auth: "admin-jwt", tags: ["Admin — Terms & Promo"],
    summary: "Delete a promo code",
    description: "Permanently delete a promo code.",
    params: [{ name: "code_id", in: "path", type: "string", required: true, description: "Promo code ID", example: "promo_abc123" }],
    responseExample: { message: "Promo code deleted" },
  },
  // ── Admin — Users ─────────────────────────────────────────────────────────
  {
    method: "GET", path: "/api/admin/users", auth: "admin-jwt", tags: ["Admin — Users"],
    summary: "List admin/staff users",
    description: "Returns all admin and staff users for the current organisation.",
    params: [
      { name: "search", in: "query", type: "string", required: false, description: "Search by name or email", example: "alice" },
      { name: "role", in: "query", type: "string", required: false, description: "Filter by role", example: "partner_staff" },
    ],
    responseExample: { users: [{ id: "usr_xxx", email: "alice@org.com", full_name: "Alice Jones", role: "partner_staff", is_active: true }], total: 10 },
  },
  {
    method: "POST", path: "/api/admin/users", auth: "admin-jwt", tags: ["Admin — Users"],
    summary: "Create a staff user",
    description: "Create a new admin or staff user for the organisation. Available roles: partner_admin, partner_staff.",
    bodySchema: { email: "staff@yourorg.com", full_name: "Alice Jones", role: "partner_staff", password: "TempPass1!", is_active: true },
    responseExample: { id: "usr_xxx", email: "staff@yourorg.com" },
  },
  {
    method: "PUT", path: "/api/admin/users/{user_id}", auth: "admin-jwt", tags: ["Admin — Users"],
    summary: "Update a user",
    description: "Update a user's name, role, or active status.",
    params: [{ name: "user_id", in: "path", type: "string", required: true, description: "User ID", example: "usr_abc123" }],
    bodySchema: { full_name: "Alice Jones", role: "partner_admin", is_active: true },
    responseExample: { message: "User updated" },
  },
  {
    method: "PATCH", path: "/api/admin/users/{user_id}/active", auth: "admin-jwt", tags: ["Admin — Users"],
    summary: "Activate/deactivate a user",
    description: "Set the active status of a staff user.",
    params: [{ name: "user_id", in: "path", type: "string", required: true, description: "User ID", example: "usr_abc123" }],
    bodySchema: { is_active: false },
    responseExample: { message: "User deactivated" },
  },
  {
    method: "DELETE", path: "/api/admin/users/{user_id}", auth: "admin-jwt", tags: ["Admin — Users"],
    summary: "Delete a user",
    description: "Permanently delete a staff user account.",
    params: [{ name: "user_id", in: "path", type: "string", required: true, description: "User ID", example: "usr_abc123" }],
    responseExample: { message: "User deleted" },
  },
  // ── Admin — Webhooks ──────────────────────────────────────────────────────
  {
    method: "GET", path: "/api/admin/webhooks/events", auth: "admin-jwt", tags: ["Admin — Webhooks"],
    summary: "List webhook event types",
    description: "Returns all available webhook event names you can subscribe to.",
    responseExample: { events: ["order.confirmed", "subscription.created", "subscription.cancelled", "customer.registered"] },
  },
  {
    method: "GET", path: "/api/admin/webhooks", auth: "admin-jwt", tags: ["Admin — Webhooks"],
    summary: "List webhooks",
    description: "Returns all configured webhook endpoints.",
    responseExample: { webhooks: [{ id: "wh_xxx", url: "https://example.com/webhook", events: ["order.confirmed"], is_active: true }] },
  },
  {
    method: "POST", path: "/api/admin/webhooks", auth: "admin-jwt", tags: ["Admin — Webhooks"],
    summary: "Create a webhook",
    description: "Register a new webhook URL. The signing secret is only returned once — store it securely. Use subscriptions to specify which events trigger this webhook and which fields to include in the payload. Shorthand: pass events as a string array to subscribe with all default fields.",
    bodySchema: {
      url: "https://example.com/webhook",
      name: "My CRM Sync (optional)",
      subscriptions: [
        { event: "order.created", fields: ["id", "order_number", "customer_email", "total"] },
        { event: "customer.registered", fields: ["id", "email", "full_name", "company"] }
      ],
      "events (shorthand)": ["order.created", "customer.registered"]
    },
    responseExample: { id: "wh_xxx", secret: "whsec_..." },
  },
  {
    method: "PUT", path: "/api/admin/webhooks/{webhook_id}", auth: "admin-jwt", tags: ["Admin — Webhooks"],
    summary: "Update a webhook",
    params: [{ name: "webhook_id", in: "path", type: "string", required: true, description: "Webhook ID", example: "wh_abc123" }],
    bodySchema: {
      url: "https://example.com/new-url",
      subscriptions: [{ event: "order.created", fields: ["id", "order_number"] }],
      is_active: true
    },
    description: "Update a webhook's URL, event subscriptions, or active status. Accepts either subscriptions or events (shorthand).",
    responseExample: { message: "Webhook updated" },
  },
  {
    method: "DELETE", path: "/api/admin/webhooks/{webhook_id}", auth: "admin-jwt", tags: ["Admin — Webhooks"],
    summary: "Delete a webhook",
    description: "Remove a webhook endpoint.",
    params: [{ name: "webhook_id", in: "path", type: "string", required: true, description: "Webhook ID", example: "wh_abc123" }],
    responseExample: { message: "Webhook deleted" },
  },
  {
    method: "POST", path: "/api/admin/webhooks/{webhook_id}/test", auth: "admin-jwt", tags: ["Admin — Webhooks"],
    summary: "Test a webhook",
    description: "Send a test ping event to a webhook URL to verify it's reachable.",
    params: [{ name: "webhook_id", in: "path", type: "string", required: true, description: "Webhook ID", example: "wh_abc123" }],
    bodySchema: {},
    responseExample: { message: "Test event sent", status: 200 },
  },
  // ── Admin — Settings & Website ────────────────────────────────────────────
  {
    method: "GET", path: "/api/admin/settings", auth: "admin-jwt", tags: ["Admin — Settings"],
    summary: "Get app settings",
    description: "Returns all organisation settings including branding, email config, and integrations status.",
    responseExample: { store_name: "Acme Ltd", primary_color: "#2563eb", admin_notification_email: "admin@acme.com" },
  },
  {
    method: "PUT", path: "/api/admin/settings", auth: "admin-jwt", tags: ["Admin — Settings"],
    summary: "Update app settings",
    description: "Update any app settings key. Partial updates are supported.",
    bodySchema: { store_name: "Acme Ltd", admin_notification_email: "admin@acme.com", primary_color: "#2563eb" },
    responseExample: { message: "Settings updated" },
  },
  {
    method: "GET", path: "/api/admin/website-settings", auth: "admin-jwt", tags: ["Admin — Settings"],
    summary: "Get website settings",
    description: "Returns all website content settings (hero text, nav labels, footer copy, etc.).",
    responseExample: { hero_title: "Welcome to Acme", footer_tagline: "We help businesses grow." },
  },
  {
    method: "PUT", path: "/api/admin/website-settings", auth: "admin-jwt", tags: ["Admin — Settings"],
    summary: "Update website settings",
    description: "Update any website content setting. Partial updates are supported.",
    bodySchema: { hero_title: "Welcome to Acme", hero_subtitle: "Streamline your finances.", cta_button_text: "Get Started" },
    responseExample: { message: "Website settings updated" },
  },
  // ── Admin — Email Templates ───────────────────────────────────────────────
  {
    method: "GET", path: "/api/admin/email-templates", auth: "admin-jwt", tags: ["Admin — Email"],
    summary: "List email templates",
    description: "Returns all email templates. Each template is tied to a trigger event (e.g. order.confirmed).",
    responseExample: { templates: [{ id: "tmpl_xxx", trigger: "order.confirmed", name: "Order Confirmation", subject: "Your order {{order_number}} is confirmed", is_active: true }] },
  },
  {
    method: "PUT", path: "/api/admin/email-templates/{template_id}", auth: "admin-jwt", tags: ["Admin — Email"],
    summary: "Update an email template",
    description: "Customise the subject or HTML body of an email template. Use {{variable}} syntax for dynamic values.",
    params: [{ name: "template_id", in: "path", type: "string", required: true, description: "Template ID", example: "tmpl_abc123" }],
    bodySchema: { subject: "Your order {{order_number}} is confirmed", body: "<p>Hi {{customer_name}},</p><p>Your order has been received.</p>", is_active: true },
    responseExample: { message: "Template updated" },
  },
  {
    method: "GET", path: "/api/admin/email-logs", auth: "admin-jwt", tags: ["Admin — Email"],
    summary: "Get email logs",
    description: "Returns a log of recently sent emails including status (sent, failed).",
    responseExample: { logs: [{ id: "log_xxx", to: "customer@example.com", subject: "Order confirmed", status: "sent", created_at: "2026-01-01T10:00:00Z" }] },
  },
  // ── Admin — Resources ─────────────────────────────────────────────────────
  {
    method: "GET", path: "/api/resources/admin/list", auth: "admin-jwt", tags: ["Admin — Resources & Articles"],
    summary: "List resources (admin)",
    description: "Returns all resources including visibility settings.",
    responseExample: { resources: [{ id: "res_xxx", name: "2025 Tax Guide.pdf", file_type: "pdf", visibility: "customers" }] },
  },
  {
    method: "PUT", path: "/api/resources/{resource_id}", auth: "admin-jwt", tags: ["Admin — Resources & Articles"],
    summary: "Update a resource",
    description: "Update a resource's name, description, or visibility settings.",
    params: [{ name: "resource_id", in: "path", type: "string", required: true, description: "Resource ID", example: "res_abc123" }],
    bodySchema: { name: "Updated Guide.pdf", visibility: "all", description: "Updated description" },
    responseExample: { message: "Resource updated" },
  },
  {
    method: "DELETE", path: "/api/resources/{resource_id}", auth: "admin-jwt", tags: ["Admin — Resources & Articles"],
    summary: "Delete a resource",
    description: "Permanently delete a resource and its associated file.",
    params: [{ name: "resource_id", in: "path", type: "string", required: true, description: "Resource ID", example: "res_abc123" }],
    responseExample: { message: "Resource deleted" },
  },
  {
    method: "GET", path: "/api/articles/admin/list", auth: "admin-jwt", tags: ["Admin — Resources & Articles"],
    summary: "List articles (admin)",
    description: "Returns all articles including drafts.",
    responseExample: { articles: [{ id: "art_xxx", title: "2025 Tax Guide", slug: "2025-tax-guide", status: "published" }] },
  },
  {
    method: "POST", path: "/api/articles", auth: "admin-jwt", tags: ["Admin — Resources & Articles"],
    summary: "Create an article",
    description: "Create a new knowledge base article.",
    bodySchema: { title: "2025 Tax Guide", content: "<h2>Introduction</h2><p>...</p>", category: "Tax Tips", status: "published", visibility: "all" },
    responseExample: { id: "art_xxx", title: "2025 Tax Guide" },
  },
  {
    method: "PUT", path: "/api/articles/{article_id}", auth: "admin-jwt", tags: ["Admin — Resources & Articles"],
    summary: "Update an article",
    params: [{ name: "article_id", in: "path", type: "string", required: true, description: "Article ID", example: "art_abc123" }],
    bodySchema: { title: "Updated Title", content: "<p>Updated content.</p>", status: "published" },
    description: "Update an article's title, content, or publication status.",
    responseExample: { message: "Article updated" },
  },
  {
    method: "DELETE", path: "/api/articles/{article_id}", auth: "admin-jwt", tags: ["Admin — Resources & Articles"],
    summary: "Delete an article",
    description: "Permanently delete an article.",
    params: [{ name: "article_id", in: "path", type: "string", required: true, description: "Article ID", example: "art_abc123" }],
    responseExample: { message: "Article deleted" },
  },
  // ── Admin — Export ────────────────────────────────────────────────────────
  {
    method: "GET", path: "/api/admin/export/customers", auth: "admin-jwt", tags: ["Admin — Export"],
    summary: "Export customers (CSV)",
    description: "Download all customer records as a CSV file.",
    responseExample: { note: "Returns a CSV file download" },
  },
  {
    method: "GET", path: "/api/admin/export/orders", auth: "admin-jwt", tags: ["Admin — Export"],
    summary: "Export orders (CSV)",
    description: "Download all order records as a CSV file.",
    responseExample: { note: "Returns a CSV file download" },
  },
  {
    method: "GET", path: "/api/admin/export/subscriptions", auth: "admin-jwt", tags: ["Admin — Export"],
    summary: "Export subscriptions (CSV)",
    description: "Download all subscription records as a CSV file.",
    responseExample: { note: "Returns a CSV file download" },
  },
  {
    method: "GET", path: "/api/admin/export/catalog", auth: "admin-jwt", tags: ["Admin — Export"],
    summary: "Export product catalog (CSV)",
    description: "Download the full product catalogue as a CSV file.",
    responseExample: { note: "Returns a CSV file download" },
  },
  // ── Admin — Integrations ──────────────────────────────────────────────────
  {
    method: "GET", path: "/api/admin/integrations/status", auth: "admin-jwt", tags: ["Admin — Integrations"],
    summary: "Integration status overview",
    description: "Returns the connection status of all configured integrations (email, CRM, payments).",
    responseExample: { active_email_provider: "resend", integrations: { zoho_crm: { connected: true }, stripe: { connected: false }, gocardless: { connected: true } } },
  },
  {
    method: "GET", path: "/api/admin/integrations/email-providers", auth: "admin-jwt", tags: ["Admin — Integrations"],
    summary: "Email providers config",
    description: "Returns the configured email providers and which one is currently active.",
    responseExample: { active_provider: "resend", providers: [{ type: "resend", is_configured: true, is_active: true }] },
  },
  {
    method: "GET", path: "/api/admin/integrations/crm-mappings", auth: "admin-jwt", tags: ["Admin — Integrations"],
    summary: "CRM field mappings",
    description: "Returns all Zoho CRM field mappings for all 13 synced application modules.",
    responseExample: { mappings: { customers: [{ local_field: "email", crm_field: "Email", crm_module: "Contacts" }], orders: [] } },
  },
];


const METHOD_COLORS: Record<string, string> = {
  GET: "bg-emerald-100 text-emerald-700",
  POST: "bg-blue-100 text-blue-700",
  PUT: "bg-amber-100 text-amber-700",
  DELETE: "bg-red-100 text-red-700",
  PATCH: "bg-purple-100 text-purple-700",
};

const ALL_TAGS = Array.from(new Set(API_ENDPOINTS.flatMap(e => e.tags)));

// ── Endpoint Card ─────────────────────────────────────────────────────────────

function EndpointCard({ ep, testApiKey, testAdminJwt }: { ep: EndpointDef; testApiKey: string; testAdminJwt: string }) {
  const [open, setOpen] = useState(false);
  const [tryOpen, setTryOpen] = useState(false);
  const [tryInputs, setTryInputs] = useState<Record<string, string>>({});
  const [tryBody, setTryBody] = useState(ep.bodySchema ? JSON.stringify(ep.bodySchema, null, 2) : "");
  const [tryJwt, setTryJwt] = useState("");
  const [tryResult, setTryResult] = useState<{ status: number; body: any } | null>(null);
  const [trying, setTrying] = useState(false);

  const handleTry = async () => {
    if (ep.auth === "admin-jwt" && !testAdminJwt.trim()) {
      toast.error("Paste your Admin JWT in the field above to test admin endpoints.");
      return;
    }
    if (ep.auth !== "admin-jwt" && !testApiKey.trim()) {
      toast.error("Enter your API key in the field above before using Try It.");
      return;
    }
    setTrying(true);
    setTryResult(null);
    try {
      const base = process.env.REACT_APP_BACKEND_URL || "";
      let url = base + ep.path;
      const pathParams = (ep.params || []).filter(p => p.in === "path");
      for (const p of pathParams) url = url.replace(`{${p.name}}`, tryInputs[p.name] || `:${p.name}`);
      const qp = (ep.params || []).filter(p => p.in === "query").filter(p => tryInputs[p.name]);
      if (qp.length) url += "?" + qp.map(p => `${p.name}=${encodeURIComponent(tryInputs[p.name])}`).join("&");

      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (ep.auth === "admin-jwt") {
        headers["Authorization"] = `Bearer ${testAdminJwt.trim()}`;
      } else {
        headers["X-API-Key"] = testApiKey.trim();
        if (ep.auth === "customer-jwt" && tryJwt.trim()) {
          headers["Authorization"] = `Bearer ${tryJwt.trim()}`;
        }
      }

      let body: string | undefined;
      if (ep.bodySchema && tryBody.trim() && ep.method !== "GET") body = tryBody;

      const resp = await fetch(url, { method: ep.method, headers, body });
      const data = await resp.json().catch(() => ({}));
      setTryResult({ status: resp.status, body: data });
    } catch (e: any) {
      setTryResult({ status: 0, body: { error: e.message } });
    } finally {
      setTrying(false);
    }
  };

  const authBadge = ep.auth === "api-key"
    ? <span className="text-[10px] px-1.5 py-0.5 rounded font-medium bg-indigo-100 text-indigo-700">X-API-Key</span>
    : ep.auth === "customer-jwt"
    ? <span className="text-[10px] px-1.5 py-0.5 rounded font-medium bg-orange-100 text-orange-700">X-API-Key + JWT</span>
    : <span className="text-[10px] px-1.5 py-0.5 rounded font-medium bg-violet-100 text-violet-700">Admin JWT</span>;

  return (
    <div className="border border-slate-200 rounded-xl overflow-hidden" data-testid={`endpoint-card-${ep.method}-${ep.path.replace(/\//g, "-").replace(/[{}]/g, "")}`}>
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center gap-3 px-4 py-3 bg-white hover:bg-slate-50 transition-colors text-left"
      >
        <span className={`text-[11px] font-bold px-2 py-0.5 rounded font-mono min-w-[48px] text-center ${METHOD_COLORS[ep.method]}`}>{ep.method}</span>
        <span className="font-mono text-sm text-slate-700 flex-1 truncate">{ep.path}</span>
        {authBadge}
        {open ? <ChevronDown size={14} className="text-slate-400 shrink-0" /> : <ChevronRight size={14} className="text-slate-400 shrink-0" />}
      </button>

      {open && (
        <div className="border-t border-slate-100 bg-slate-50 p-4 space-y-4">
          <div>
            <p className="text-sm font-semibold text-slate-800">{ep.summary}</p>
            <p className="text-xs text-slate-500 mt-1">{ep.description}</p>
          </div>

          {/* Auth requirements */}
          <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 space-y-1.5">
            <p className="text-xs font-semibold text-slate-600">Authentication</p>
            {ep.auth === "admin-jwt" ? (
              <div className="flex items-center gap-2 text-xs text-slate-600">
                <Key size={12} className="text-violet-500 shrink-0" />
                <span>Required:</span>
                <code className="bg-slate-100 px-1.5 py-0.5 rounded font-mono">Authorization: Bearer &lt;admin-jwt&gt;</code>
                <span className="text-slate-400">(from /api/auth/partner-login)</span>
              </div>
            ) : (
              <>
                <div className="flex items-center gap-2 text-xs text-slate-600">
                  <Key size={12} className="text-indigo-500 shrink-0" />
                  <span>Always required:</span>
                  <code className="bg-slate-100 px-1.5 py-0.5 rounded font-mono">X-API-Key: ak_…</code>
                </div>
                {ep.auth === "customer-jwt" && (
                  <div className="flex items-center gap-2 text-xs text-slate-600">
                    <Key size={12} className="text-orange-500 shrink-0" />
                    <span>Also required:</span>
                    <code className="bg-slate-100 px-1.5 py-0.5 rounded font-mono">Authorization: Bearer &lt;customer-jwt&gt;</code>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Parameters */}
          {ep.params && ep.params.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">Parameters</p>
              <div className="rounded-lg overflow-hidden border border-slate-200">
                <table className="w-full text-xs">
                  <thead className="bg-white border-b border-slate-100">
                    <tr>
                      <th className="text-left px-3 py-2 text-slate-500 font-medium">Name</th>
                      <th className="text-left px-3 py-2 text-slate-500 font-medium">In</th>
                      <th className="text-left px-3 py-2 text-slate-500 font-medium">Type</th>
                      <th className="text-left px-3 py-2 text-slate-500 font-medium">Req.</th>
                      <th className="text-left px-3 py-2 text-slate-500 font-medium">Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ep.params.map(p => (
                      <tr key={p.name} className="border-b border-slate-100 last:border-0 bg-white">
                        <td className="px-3 py-2 font-mono text-slate-800">{p.name}</td>
                        <td className="px-3 py-2 text-slate-500">{p.in}</td>
                        <td className="px-3 py-2 text-slate-500">{p.type}</td>
                        <td className="px-3 py-2">{p.required ? <span className="text-red-500">Yes</span> : <span className="text-slate-400">No</span>}</td>
                        <td className="px-3 py-2 text-slate-500">{p.description}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Body */}
          {ep.bodySchema && (
            <div>
              <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">Request Body (JSON)</p>
              <pre className="bg-slate-900 text-green-300 text-[11px] font-mono p-3 rounded-lg overflow-x-auto">
                {JSON.stringify(ep.bodySchema, null, 2)}
              </pre>
            </div>
          )}

          {/* Response */}
          {ep.responseExample && (
            <div>
              <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">Example Response</p>
              <pre className="bg-slate-900 text-blue-300 text-[11px] font-mono p-3 rounded-lg overflow-x-auto">
                {JSON.stringify(ep.responseExample, null, 2)}
              </pre>
            </div>
          )}

          {/* Try It */}
          <div className="border-t border-slate-200 pt-3">
            <button onClick={() => setTryOpen(v => !v)} className="flex items-center gap-2 text-xs font-semibold text-slate-700 hover:text-indigo-600 transition-colors">
              <Play size={12} />
              {tryOpen ? "Hide Try It" : "Try It Live"}
            </button>

            {tryOpen && (
              <div className="mt-3 space-y-3">
                {ep.auth === "admin-jwt" && (
                  <div>
                    <label className="text-xs font-medium text-violet-700">Admin JWT (from /api/auth/partner-login) — pre-filled from above</label>
                    <Input placeholder="eyJhbGci…" value={testAdminJwt} readOnly className="mt-1 h-8 text-xs font-mono bg-violet-50 border-violet-200 cursor-not-allowed" />
                  </div>
                )}
                {ep.auth === "customer-jwt" && (
                  <div>
                    <label className="text-xs font-medium text-orange-700">Customer JWT (from /api/auth/customer-login)</label>
                    <Input placeholder="eyJhbGci…" value={tryJwt} onChange={e => setTryJwt(e.target.value)} className="mt-1 h-8 text-xs font-mono" />
                  </div>
                )}

                {(ep.params || []).filter(p => p.in !== "header").map(p => (
                  <div key={p.name}>
                    <label className="text-xs text-slate-500">{p.name} ({p.in}){p.required ? <span className="text-red-500"> *</span> : ""}</label>
                    <Input placeholder={p.example || `Enter ${p.name}`} value={tryInputs[p.name] || ""} onChange={e => setTryInputs(prev => ({ ...prev, [p.name]: e.target.value }))} className="mt-1 h-8 text-xs font-mono" />
                  </div>
                ))}

                {ep.bodySchema && (
                  <div>
                    <label className="text-xs text-slate-500">Request Body (JSON)</label>
                    <textarea value={tryBody} onChange={e => setTryBody(e.target.value)} rows={5} className="mt-1 w-full text-xs font-mono border border-slate-200 rounded-lg p-2 bg-white resize-y" />
                  </div>
                )}

                <Button size="sm" onClick={handleTry} disabled={trying} className="gap-2">
                  <Play size={12} />
                  {trying ? "Sending…" : "Send Request"}
                </Button>

                {tryResult && (
                  <div className={`rounded-lg overflow-hidden border ${tryResult.status >= 200 && tryResult.status < 300 ? "border-green-200" : "border-red-200"}`}>
                    <div className={`px-3 py-1.5 text-xs font-mono font-semibold ${tryResult.status >= 200 && tryResult.status < 300 ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
                      HTTP {tryResult.status || "Error"}
                    </div>
                    <pre className="bg-slate-900 text-slate-200 text-[11px] font-mono p-3 overflow-x-auto max-h-64">
                      {JSON.stringify(tryResult.body, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── API Key Manager ───────────────────────────────────────────────────────────

function ApiKeyManager({ onKeyResolved }: { onKeyResolved: (key: string) => void }) {
  const [keys, setKeys] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [newKeyName, setNewKeyName] = useState("Production Key");
  const [revealedKey, setRevealedKey] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get("/admin/api-keys");
      setKeys(res.data.api_keys || []);
    } catch { toast.error("Failed to load API keys"); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const handleGenerate = async () => {
    if (!window.confirm("Generating a new key will revoke the existing active key for this tenant. Continue?")) return;
    setGenerating(true);
    try {
      const res = await api.post("/admin/api-keys", { name: newKeyName });
      setRevealedKey(res.data.key);
      await load();
      toast.success("New API key generated. Copy it now — it won't be shown again.");
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to generate key");
    } finally {
      setGenerating(false);
      setShowNew(false);
    }
  };

  const handleRevoke = async (keyId: string, name: string) => {
    if (!window.confirm(`Revoke key "${name}"? All integrations using this key will stop working immediately.`)) return;
    try {
      await api.delete(`/admin/api-keys/${keyId}`);
      toast.success("API key revoked");
      setRevealedKey(null);
      load();
    } catch { toast.error("Failed to revoke key"); }
  };

  const copyKey = (key: string) => {
    navigator.clipboard.writeText(key).then(() => toast.success("Copied to clipboard"));
    onKeyResolved(key);
  };

  const activeKey = keys.find(k => k.is_active);

  return (
    <div className="flex flex-col gap-5">
      {/* Revealed new key banner */}
      {revealedKey && (
        <div className="rounded-xl bg-amber-50 border border-amber-300 p-4 space-y-2">
          <div className="flex items-center gap-2">
            <AlertCircle size={16} className="text-amber-600" />
            <p className="text-sm font-semibold text-amber-800">Your new API key — copy it now!</p>
          </div>
          <p className="text-xs text-amber-700">This key will not be shown again. Store it in a secure location (e.g. environment variables, a secrets manager).</p>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-white border border-amber-200 rounded px-3 py-2 text-sm font-mono text-amber-900 break-all" data-testid="new-api-key-value">{revealedKey}</code>
            <Button size="sm" variant="outline" className="shrink-0" onClick={() => copyKey(revealedKey)} data-testid="copy-api-key-btn">
              <Copy size={13} className="mr-1" /> Copy & Use
            </Button>
          </div>
          <Button size="sm" variant="ghost" className="text-amber-700 text-xs" onClick={() => setRevealedKey(null)}>Dismiss</Button>
        </div>
      )}

      {/* Current active key */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div>
            <p className="text-sm font-semibold text-slate-800">Active API Key</p>
            <p className="text-xs text-slate-500 mt-0.5">One key per tenant. Generating a new key immediately revokes the current one.</p>
          </div>
          <Button size="sm" variant="outline" onClick={() => setShowNew(v => !v)} data-testid="generate-api-key-btn">
            <RefreshCw size={13} className="mr-1.5" />
            {activeKey ? "Regenerate Key" : "Generate Key"}
          </Button>
        </div>

        {showNew && (
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 mb-4 space-y-3">
            <p className="text-xs font-semibold text-slate-600">Key Label (optional)</p>
            <Input value={newKeyName} onChange={e => setNewKeyName(e.target.value)} placeholder="e.g. Production" className="h-8 text-sm" data-testid="api-key-name-input" />
            <div className="flex gap-2">
              <Button size="sm" onClick={handleGenerate} disabled={generating} data-testid="confirm-generate-key-btn">
                {generating ? "Generating…" : "Generate Key"}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setShowNew(false)}>Cancel</Button>
            </div>
          </div>
        )}

        {loading ? (
          <p className="text-xs text-slate-400 py-4">Loading…</p>
        ) : !activeKey ? (
          <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center">
            <Key size={24} className="mx-auto text-slate-300 mb-2" />
            <p className="text-sm text-slate-500">No active API key.</p>
            <p className="text-xs text-slate-400 mt-1">Generate a key to start integrating your tenant's API.</p>
          </div>
        ) : (
          <div className="rounded-xl border border-green-200 bg-white p-4 flex items-center gap-4" data-testid={`api-key-row-${activeKey.id}`}>
            <div className="h-2.5 w-2.5 rounded-full bg-green-500 shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <p className="text-sm font-medium text-slate-800">{activeKey.name || "API Key"}</p>
                <span className="text-[10px] px-1.5 py-0.5 rounded font-medium bg-green-100 text-green-700">Active</span>
              </div>
              <p className="text-xs font-mono text-slate-400 mt-0.5">{activeKey.key_masked || "•••••••••••••••"}</p>
              <p className="text-[11px] text-slate-400 mt-0.5">
                Created {new Date(activeKey.created_at).toLocaleDateString()}
                {activeKey.last_used_at ? ` · Last used ${new Date(activeKey.last_used_at).toLocaleDateString()}` : " · Never used"}
              </p>
            </div>
            <Button variant="ghost" size="sm" className="text-red-400 hover:text-red-600 shrink-0" onClick={() => handleRevoke(activeKey.id, activeKey.name)} data-testid={`revoke-key-${activeKey.id}`}>
              <Trash2 size={13} />
            </Button>
          </div>
        )}
      </div>

      {/* Quick start */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
        <p className="text-sm font-semibold text-slate-800">Quick Start</p>

        <div className="rounded-lg bg-blue-50 border border-blue-200 p-3 flex items-start gap-3">
          <Info size={14} className="text-blue-500 mt-0.5 shrink-0" />
          <p className="text-xs text-blue-700">
            <strong>No subdomain required.</strong> Your API key identifies your tenant on every request.
            Regardless of whether your customers access the platform via a subdomain or the main URL,
            all API calls use the same base URL — only the <code className="bg-blue-100 px-1 rounded font-mono">X-API-Key</code> header differs per tenant.
          </p>
        </div>

        <div className="space-y-3">
          <div>
            <p className="text-xs font-medium text-slate-600 mb-1">1. Every request must include your API key:</p>
            <pre className="bg-slate-900 text-green-300 text-[11px] font-mono p-3 rounded-lg overflow-x-auto">
{`X-API-Key: ak_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`}
            </pre>
          </div>
          <div>
            <p className="text-xs font-medium text-slate-600 mb-1">2. Example — fetch your products (cURL):</p>
            <pre className="bg-slate-900 text-blue-300 text-[11px] font-mono p-3 rounded-lg overflow-x-auto">
{`curl ${process.env.REACT_APP_BACKEND_URL || "https://your-domain.com"}/api/products \\
  -H "X-API-Key: ak_xxxxxxxx..."`}
            </pre>
          </div>
          <div>
            <p className="text-xs font-medium text-slate-600 mb-1">3. For customer-specific endpoints, also send a customer JWT:</p>
            <pre className="bg-slate-900 text-amber-300 text-[11px] font-mono p-3 rounded-lg overflow-x-auto">
{`# Step 1: Get the JWT
curl -X POST ${process.env.REACT_APP_BACKEND_URL || "https://your-domain.com"}/api/auth/customer-login \\
  -H "X-API-Key: ak_xxxxxxxx..." \\
  -H "Content-Type: application/json" \\
  -d '{"email":"customer@example.com","password":"..."}'

# Step 2: Use JWT + API Key together
curl ${process.env.REACT_APP_BACKEND_URL || "https://your-domain.com"}/api/subscriptions \\
  -H "X-API-Key: ak_xxxxxxxx..." \\
  -H "Authorization: Bearer eyJhbGci..."`}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Main Tab ──────────────────────────────────────────────────────────────────

export function ApiTab() {
  const [activeTag, setActiveTag] = useState<string>("All");
  const [searchTerm, setSearchTerm] = useState("");
  const [activeSection, setActiveSection] = useState<"keys" | "docs">("keys");
  const [testApiKey, setTestApiKey] = useState("");
  const [testAdminJwt, setTestAdminJwt] = useState("");

  const filtered = API_ENDPOINTS.filter(ep => {
    const matchTag = activeTag === "All" || ep.tags.includes(activeTag);
    const matchSearch = !searchTerm || ep.path.toLowerCase().includes(searchTerm.toLowerCase()) || ep.summary.toLowerCase().includes(searchTerm.toLowerCase());
    return matchTag && matchSearch;
  });

  return (
    <div className="space-y-6" data-testid="api-tab">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900">API</h2>
          <p className="text-sm text-slate-500 mt-0.5">Manage your API key and explore all available endpoints.</p>
        </div>
        <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-1">
          <button
            onClick={() => setActiveSection("keys")}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${activeSection === "keys" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}
            data-testid="api-section-keys"
          >
            <Key size={12} className="inline mr-1.5" />API Keys
          </button>
          <button
            onClick={() => setActiveSection("docs")}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${activeSection === "docs" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}
            data-testid="api-section-docs"
          >
            <BookOpen size={12} className="inline mr-1.5" />Documentation ({API_ENDPOINTS.length})
          </button>
        </div>
      </div>

      {activeSection === "keys" && (
        <ApiKeyManager onKeyResolved={key => { setTestApiKey(key); setActiveSection("docs"); }} />
      )}

      {activeSection === "docs" && (
        <div className="space-y-4">
          {/* Try It global API key input */}
          <div className="rounded-xl border border-indigo-200 bg-indigo-50 p-4 space-y-2">
            <div className="flex items-center gap-2">
              <Key size={14} className="text-indigo-600" />
              <p className="text-xs font-semibold text-indigo-800">API Key for Try It <span className="text-indigo-500 font-normal">(public &amp; customer endpoints)</span></p>
            </div>
            <p className="text-xs text-indigo-600">Paste your API key here to test public and customer-facing endpoints.</p>
            <div className="flex gap-2">
              <Input
                placeholder="ak_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                value={testApiKey}
                onChange={e => setTestApiKey(e.target.value)}
                className="font-mono text-xs h-8 bg-white border-indigo-200"
                data-testid="try-it-api-key-input"
              />
              {testApiKey && (
                <Button size="sm" variant="ghost" className="text-xs shrink-0" onClick={() => setTestApiKey("")}>Clear</Button>
              )}
            </div>
            {testApiKey && (
              <p className="text-[11px] text-indigo-600 flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-green-500 inline-block" /> API key active for public/customer endpoints.
              </p>
            )}
          </div>

          {/* Admin JWT input */}
          <div className="rounded-xl border border-violet-200 bg-violet-50 p-4 space-y-2">
            <div className="flex items-center gap-2">
              <Key size={14} className="text-violet-600" />
              <p className="text-xs font-semibold text-violet-800">Admin JWT for Try It <span className="text-violet-500 font-normal">(admin endpoints)</span></p>
            </div>
            <p className="text-xs text-violet-600">
              Get a token via <code className="bg-violet-100 px-1 rounded font-mono">POST /api/auth/partner-login</code> and paste it here to test admin endpoints.
            </p>
            <div className="flex gap-2">
              <Input
                placeholder="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9…"
                value={testAdminJwt}
                onChange={e => setTestAdminJwt(e.target.value)}
                className="font-mono text-xs h-8 bg-white border-violet-200"
                data-testid="try-it-admin-jwt-input"
              />
              {testAdminJwt && (
                <Button size="sm" variant="ghost" className="text-xs shrink-0" onClick={() => setTestAdminJwt("")}>Clear</Button>
              )}
            </div>
            {testAdminJwt && (
              <p className="text-[11px] text-violet-600 flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-green-500 inline-block" /> Admin JWT active for admin endpoints.
              </p>
            )}
          </div>

          {/* Auth model callout */}
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-lg border border-indigo-200 bg-white p-3">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-700">X-API-Key</span>
                <span className="text-xs font-medium text-slate-700">Public endpoints</span>
              </div>
              <p className="text-[11px] text-slate-500">Required on every public request. Identifies your tenant — no subdomain needed.</p>
            </div>
            <div className="rounded-lg border border-orange-200 bg-white p-3">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-orange-100 text-orange-700">X-API-Key + JWT</span>
                <span className="text-xs font-medium text-slate-700">Customer endpoints</span>
              </div>
              <p className="text-[11px] text-slate-500">X-API-Key + customer Bearer JWT (from /api/auth/customer-login).</p>
            </div>
            <div className="rounded-lg border border-violet-200 bg-white p-3">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-violet-100 text-violet-700">Admin JWT</span>
                <span className="text-xs font-medium text-slate-700">Admin endpoints</span>
              </div>
              <p className="text-[11px] text-slate-500">Bearer JWT from /api/auth/partner-login. No X-API-Key needed — tenant resolved from token.</p>
            </div>
          </div>

          {/* Filter + search */}
          <div className="flex gap-5">
            {/* Tag filter */}
            <div className="w-44 shrink-0 space-y-1">
              <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider px-2 pb-1">Filter</p>
              {["All", ...ALL_TAGS].map(tag => (
                <button key={tag} onClick={() => setActiveTag(tag)}
                  className={`w-full text-left px-3 py-2 text-xs rounded-lg transition-colors ${activeTag === tag ? "bg-slate-900 text-white font-medium" : "text-slate-600 hover:bg-slate-100"}`}
                  data-testid={`api-tag-${tag.toLowerCase().replace(/\s+/g, "-").replace(/[&]/g, "")}`}
                >
                  {tag}
                </button>
              ))}
            </div>

            {/* Endpoints */}
            <div className="flex-1 min-w-0 space-y-2.5">
              <div className="flex items-center gap-3">
                <Input placeholder="Search endpoints…" value={searchTerm} onChange={e => setSearchTerm(e.target.value)} className="h-8 text-xs w-64" data-testid="api-search-input" />
                <span className="text-xs text-slate-400">{filtered.length} endpoint{filtered.length !== 1 ? "s" : ""}</span>
              </div>

              <div className="rounded-lg bg-slate-50 border border-slate-200 px-4 py-2.5 flex items-center gap-2">
                <Info size={13} className="text-slate-400 shrink-0" />
                <p className="text-[11px] text-slate-500">
                  All paths are relative — prepend your base URL: <code className="bg-white border px-1 rounded font-mono">{process.env.REACT_APP_BACKEND_URL || "https://your-domain.com"}</code>.
                  The <strong>X-API-Key</strong> resolves the tenant, so the same base URL works for all tenants.
                </p>
              </div>

              {filtered.map((ep, i) => (
                <EndpointCard key={i} ep={ep} testApiKey={testApiKey} testAdminJwt={testAdminJwt} />
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
