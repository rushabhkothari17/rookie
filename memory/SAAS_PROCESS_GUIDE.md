# SaaS Application Process & Business Function Guide

**Version:** 1.0 (Current Implementation)
**Audience:** Stakeholders, Product Owners, Operations Teams

---

## 1. Platform & Tenant Management (The Foundation)
*The core architecture that enables the multi-tenant "Franchise" model.*

### Concept: Tenant Isolation
Every organization (Partner) on the platform is a separate "Tenant". Data never crosses boundaries.
*   **Platform Admin:** The "Franchisor" who owns the software. Can see and manage all tenants.
*   **Partner Admin:** The "Franchisee". Can only see their own customers, orders, and settings.
*   **End Customer:** Belongs to a specific Partner.

### Key Workflows
*   **Partner Onboarding:**
    1.  Platform Admin creates a new **Tenant** (Organization).
    2.  System auto-generates a unique **Partner Code** (e.g., `bright-accounting`).
    3.  Admin assigns a **License Plan** (e.g., "Gold Tier" with 50 users).
    4.  Partner Admin receives credentials and logs in using their Partner Code.
*   **Custom Domains:** Partners can configure `portal.theircompany.com` so their customers never see the core platform URL.
    *   *Process:* Partner adds domain → CNAME record verification → SSL provisioning.

---

## 2. Partner Lifecycle & Growth (The Business Model)
*How partners join, grow, and manage their relationship with the platform.*

### License Plans & Limits
Plans control what a partner can do. This is the primary upsell mechanism.
*   **Hard Limits:** Max users, max storage, max orders/month.
*   **Soft Limits:** Warning thresholds (e.g., email alert at 80% usage).

### Self-Service Upgrades (New!)
Partners can upgrade their plan without talking to sales.
*   **Workflow:**
    1.  Partner views "My Plan" in the portal.
    2.  Selects a higher tier (e.g., Silver → Gold).
    3.  **Pro-rata Billing:** System calculates the price difference for the remaining days of the month.
    4.  **Instant Access:** Limits are raised immediately upon payment.

### Downgrades & Support
*   **Downgrades:** Must be approved by a Platform Admin to prevent gaming the system.
    *   *Workflow:* Partner submits request → Admin approves → Change applies on the **1st of next month**.

---

## 3. Revenue Operations (The Money)
*Automated billing, invoicing, and tax handling.*

### Billing Engine
*   **Billing Cycle:** Aligned to the 1st of every month for simplicity.
*   **First Month:** Always pro-rated (Partner pays only for the days remaining).
*   **Payment Methods:**
    *   **Stripe:** Credit cards (Auto-pay).
    *   **GoCardless:** Direct Debit (Auto-collect).
    *   **Manual:** Bank Transfers (Admin manually marks "Paid").

### Invoicing (PDF Generation)
*   **Professional PDFs:** Auto-generated for every order.
*   **Customization:** Admin can configure:
    *   Company Logo & Branding.
    *   VAT / Tax Registration Numbers.
    *   Bank Details (IBAN/SWIFT) in the footer.
*   **Delivery:** Emailed to partners/customers and available for download in the portal.

### Automated Scheduler (Daily Jobs)
Running every day at 09:00 UTC:
1.  **Renewal Reminders:** Sends emails X days before a subscription renews.
2.  **Auto-Cancellation:** Cancels subscriptions when their contract term ends.
3.  **Overdue Enforcement:** Warns partners with unpaid invoices, then cancels their service after a grace period (e.g., 7 days).

---

## 4. Customer Experience (The Storefront)
*The white-labeled shopping experience for End Customers.*

### The Storefront
*   **Product Catalogue:** Partners can choose which products to sell.
*   **Visibility Logic:** sophisticated rules determine who sees what.
    *   *Global:* Visible to everyone.
    *   *Exclusive:* Visible only to specific customers (VIPs).
    *   *Conditional:* "Show this product only if Customer Country = 'UK'".
*   **Pricing Tiers:**
    *   **Flat Rate:** Simple price (e.g., $50).
    *   **Tiered/Volume:** "First 10 users @ $10, next 10 @ $8".

### Purchase Flows
1.  **One-Off Orders:** Standard e-commerce cart.
2.  **Subscriptions:** Recurring billing with defined contract terms (e.g., 12 months).
3.  **Scope Requests:** Customers request a quote for custom work.
    *   *Workflow:* Customer fills form → Partner reviews → Partner converts to Order → Customer pays.

---

## 5. Operational Workflows (The Day-to-Day)
*Tools for running the business efficiently.*

### User Management
*   **Role-Based Access Control (RBAC):**
    *   **Partner Super Admin:** Can do everything.
    *   **Staff:** Restricted access (e.g., "Can view Orders but cannot Refund").
    *   **Custom Roles:** Define granular permissions per module.

### Communication Center
*   **Email Templates:** rich HTML templates for every system event (Welcome, Invoice, Reset Password).
*   **Resources (Knowledge Base):**
    *   Publish Articles, Guides, and SOPs.
    *   "Scope Final" feature: Locks a document once a client accepts a quote, preserving the legal agreement.

### Audit Trail
*   **Immutable Logs:** Every action (login, edit, delete) is recorded.
*   **Traceability:** Who did what, when, and from which IP address.
*   **Security:** Logs cannot be deleted, even by admins.

---

## 6. Security & Compliance (The Guardrails)
*   **Authentication:** Secure login with JWT (JSON Web Tokens).
*   **Tenant Isolation:** Middleware ensures a partner can *never* access another partner's data.
*   **GDPR Tools:** Built-in "Right to Erasure" and "Data Export" workflows.
*   **Secret Scanning:** Prevents sensitive API keys (Stripe, AWS) from being exposed.
