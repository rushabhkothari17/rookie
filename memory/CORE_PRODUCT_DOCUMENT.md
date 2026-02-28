# Core Product Document
## Automate Accounts — Partner-Powered SaaS Platform
**Version:** 1.0 | **Audience:** Stakeholders, New Team Members, Product Owners
**Prepared:** February 2026

---

## 1. What Is This Platform?

Automate Accounts is a **white-label, multi-tenant SaaS platform** for accounting and professional services firms. The core idea is simple: a single company (the Platform Owner) operates the software, then licenses it to **Partner Organisations** — typically accounting firms or agencies — who use it to serve their own end-customers.

Think of it like a franchise model:
- **Platform Owner** = Franchisor. Owns the software, sets the rules, manages billing with partners.
- **Partner Organisation** = Franchisee. Gets their own branded storefront, manages their own customers, controls their own content and products.
- **End Customer** = The franchisee's client. Buys services through the partner's storefront.

Every piece of data, every setting, and every interaction is **strictly separated** by organisation. A partner can only ever see their own customers, their own orders, and their own content. This separation is called **Tenant Isolation**.

---

## 2. Who Uses the Platform?

There are three distinct user types, each with different levels of access.

### 2.1 Platform Admin
The single person (or small team) who owns and operates the platform itself. There is only one Platform Admin organisation.

**Can do everything:**
- Create and manage all Partner Organisations
- Set licensing limits and plans for each partner
- View all customers, orders, and subscriptions across all partners
- Manage all products in the central catalogue
- Configure email templates, tax rules, integrations, and system settings
- Issue promo codes, override codes, and manage billing for partners directly
- Access all audit logs, email logs, and system health indicators

### 2.2 Partner Admin (and Staff)
Belongs to a Partner Organisation. Has their own login portal, identified by a unique Partner Code. Can only see and manage data that belongs to their own organisation.

**Can do:**
- Manage their own customers, orders, and subscriptions
- Configure their storefront (filters, branding, organisation address)
- Create and manage their own content (resources, articles, guides)
- Create and manage their own admin users with granular permissions
- View their own invoices and billing history with the Platform
- Send enquiries and scopes of work

**Cannot do:**
- See any other partner's data
- Change platform-level settings
- Exceed the usage limits set by the Platform Admin

### 2.3 End Customer
A client of a Partner Organisation. They do not log in through the Admin Panel. Instead, they access a **Customer-Facing Store** that is specific to their partner. Their account is automatically scoped to that partner; they cannot see or access any other partner's storefront.

**Can do:**
- Browse the product/service catalogue
- Make purchases (one-off orders or subscriptions)
- View their own account, order history, and documents
- Submit enquiries and scopes of work
- Manage payment methods

---

## 3. The Two Login Flows

### 3.1 Partner / Admin Login
Admins and staff log in by first entering their **Partner Code** (e.g., `bright-accounting`). This code identifies which organisation they belong to. After entering the code, they are taken to the standard email + password screen. The platform uses the partner code to ensure the session is scoped to the correct organisation.

> The partner code can also be embedded in a URL link, so partners can bookmark their login page directly.

### 3.2 Customer Login
Customers log in through a separate "Customer" tab on the same login screen. Their login also requires the Partner Code of their specific partner, since the same email address could theoretically exist at multiple partner organisations (each one is completely separate).

---

## 4. Tenant Isolation — The Core Data Rule

Every record in the system belongs to a **Tenant** (a Partner Organisation). The Platform Admin belongs to a special system tenant. This means:

- A customer at Bright Accounting can never see Emma's account at Summit Advisory — even if they share the same email address.
- A subscription created for Bright Accounting's customer never appears in Summit Advisory's orders list.
- Products can be in the global platform catalogue (visible to all) or created specifically for one partner's tenant.
- All API requests automatically filter data by the requesting user's tenant. There is no way to accidentally cross-contaminate data.

---

## 5. Modules & Workflows

---

### MODULE 1: Partner Organisations (Platform Admin Only)

**Purpose:** Manage the organisations that use the platform. Think of this as the "franchise registry."

**Key Screens:**
- Partner Orgs list with status badges (Active / Inactive)
- Create New Partner Org dialog (full form: org name, admin name, email, password, base currency, full address)
- Partner detail view with license settings, notes, and admin account management

**Primary Actions:**
- Create a new partner organisation. The system auto-generates a unique Partner Code from the org name (e.g., "Bright Accounting" → `bright-accounting`). The code is shown at creation and can be copied.
- Enable or disable a partner org. Disabled orgs cannot log in.
- Assign a licensing Plan to a partner, which sets usage limits.
- Add notes to a partner record (internal only, never visible to the partner).
- Create additional admin users within a partner org.
- Filter partners by their assigned plan.

**Key Rules:**
- The Partner Code is permanent once created and is used for all logins.
- Every partner must have at least one Super Admin user.
- Disabling a partner blocks all logins for that org but preserves all data.

---

### MODULE 2: Plans (Platform Admin Only)

**Purpose:** Define the tiers of service that can be offered to partners. Each plan sets hard limits on what a partner can do.

**Key Screens:**
- Plans list
- Create / Edit Plan form with all limit fields

**Primary Actions:**
- Create a Plan with a name, description, and specific limits for each feature (e.g., max 5 users, max 100 orders per month, max 20 products).
- Activate or deactivate a plan.
- Assign a plan to a Partner Org.
- Set a warning threshold (e.g., 80%) — the system alerts the partner when they are nearing a limit.

**Configurable Limits Per Plan:**
- Total users (admin + staff)
- Storage (MB)
- User roles
- Product categories
- Product terms
- Enquiries
- Resources
- Templates (article and resource)
- Email templates
- Resource categories
- Custom forms
- References
- Orders per month
- New customers per month
- Subscriptions per month

**Key Rules:**
- If a limit is left blank, it is treated as unlimited.
- When a partner hits a limit, the system blocks the action and shows an error. This applies to manual creation through the admin panel as well as automated or API-driven flows.
- Reducing a limit below current usage does not delete existing data; it only blocks new additions.

---

### MODULE 3: Customers

**Purpose:** The central registry of all end-customers for a given organisation.

**Key Screens:**
- Customers list with search and filters (country, status, payment mode, partner mapping)
- Customer detail / edit dialog
- CSV import and export

**Primary Actions:**
- Create a customer record (full name, email, phone, country, address, payment method, partner mapping status).
- Edit customer details at any time.
- Assign a payment method to a customer: Stripe, GoCardless, Offline/Manual.
- Set and update the **Partner Map** status (see Glossary).
- Import multiple customers from a CSV file.
- Export the full customer list to CSV.
- View full audit history for any customer record.

**Partner Map Statuses:**
- *Not set* — default, no mapping decision made
- *Yes – Pending Verification* — customer has requested to be linked to a partner
- *Pre-existing Customer – Pending Verification* — was already a customer before the partner was assigned
- *Not yet – Pending Verification* — customer opted out, pending confirmation
- *Yes (Verified)* — confirmed as this partner's customer
- *Pre-existing Customer (Verified)* — confirmed pre-existing
- *Not yet (Verified)* — confirmed not a partner customer

**What Customers See:**
Customers have their own portal view showing their account information, documents, and purchase history. They do not see the Partner Map status or any internal admin fields.

**Key Rules:**
- A customer belongs to exactly one tenant (partner org or platform).
- A customer's email must be unique within their tenant.
- Deleting a customer is controlled. The system enforces a soft-delete and requires confirmation.

---

### MODULE 4: Products

**Purpose:** The service or product catalogue. Products are what customers buy (one-off) or subscribe to.

**Key Screens:**
- Products list (searchable, filterable by category and catalogue type)
- Product detail / edit form (full product editor)
- Categories sub-tab
- Terms sub-tab
- Promo Codes sub-tab
- Import / Export CSV

**Primary Actions:**
- Create a product with name, description, pricing, category, available payment methods, billing interval (for subscriptions), and default contract term.
- Enable or disable a product (disabled products no longer appear in the storefront).
- Assign products to categories.
- Create, edit, and delete product categories.
- Create **Product Terms** — legal or contractual text snippets attached to specific products, presented at checkout.
- Create **Promo Codes** that apply discounts to products.
- Import products from CSV (useful for Zoho/CRM sync).

**Product Fields (Key Ones):**
- Name, description, and category
- Price and currency
- Billing interval (one-off, monthly, annually, etc.)
- Default contract term (in months) — auto-populates the term when creating a subscription for this product
- Payment methods accepted (Stripe, GoCardless, Bank Transfer, Offline)
- Whether it can be purchased via subscription or only as a one-off order

**Promo Codes:**
- Fixed amount or percentage discount
- Applicable to orders, subscriptions, or both
- Can target all products or specific ones
- Can have an expiry date and a maximum number of uses
- One-time-use codes: a single code that is invalidated after one redemption
- Admins can add internal notes to a promo code

**Key Rules:**
- Disabled products are hidden from the storefront but existing orders/subscriptions referencing them are unaffected.
- A product's default term auto-fills the contract term field when manually creating a subscription, saving time.
- Promo codes are validated at checkout and at manual order creation.

---

### MODULE 5: Orders

**Purpose:** Record and manage one-off and ad-hoc purchases.

**Key Screens:**
- Orders list with rich filters (date, status, email, order number, product, payment method)
- Order detail / edit dialog
- CSV import and export

**Order Statuses:**
- `pending` — created but not yet actioned
- `pending_payment` — awaiting payment confirmation
- `awaiting_bank_transfer` — customer chose bank transfer; payment not yet received
- `pending_direct_debit_setup` — GoCardless mandate not yet authorised
- `scope_requested` / `scope_pending` — scoping workflow in progress
- `paid` — payment confirmed
- `unpaid` — payment failed or not received
- `completed` — fulfilment done
- `canceled_pending` — cancellation requested but not yet processed
- `cancelled` — fully cancelled
- `refunded` — full refund issued
- `disputed` — chargeback or dispute raised

**Primary Actions:**
- Create an order manually (select customer, product, quantity, price, currency, payment method).
- Edit an order's status, amount, or internal notes.
- Link an order to a Stripe or GoCardless payment processor ID (with direct links to the relevant Stripe/GoCardless dashboard record).
- Issue a refund.
- Export orders to CSV.
- Import orders from CSV.
- View full audit trail for any order.

**Payment Processing:**
- **Stripe**: Card payments. Checkout sessions are created and confirmed via webhook when the customer pays. The order status updates automatically.
- **GoCardless**: Direct debit. A mandate is first set up by the customer. Once active, payments are collected against the mandate. Webhook events update the order status.
- **Bank Transfer**: Manual. Admin monitors their bank account and manually updates the order status to `paid` when the transfer arrives.
- **Offline / Manual**: Cash or other manual methods. Admin updates manually.

**Key Rules:**
- All orders include a snapshot of the product terms accepted by the customer at the time of purchase. This snapshot is preserved even if terms are later changed.
- Orders that are auto-created by the renewal scheduler for manual-payment subscriptions start as `pending` and must be actioned by an admin.
- The Platform Admin can see orders for all tenants. A Partner Admin only sees orders within their own tenant.

---

### MODULE 6: Subscriptions

**Purpose:** Manage recurring billing relationships with customers.

**Key Screens:**
- Subscriptions list with filters (status, email, plan, payment method, date range)
- Manual Subscription creation dialog
- Edit Subscription dialog
- Statistics bar (total, active, new this month)

**Subscription Statuses:**
- `active` — currently renewing
- `pending` — just created, awaiting first payment
- `cancelled` — cancelled by admin or by automated rule
- `expired` — end date passed

**Primary Actions:**
- Create a subscription manually (customer, product, amount, currency, renewal date, payment method, contract term, reminder days).
- Edit all subscription fields including renewal date, amount, status, and notes.
- Cancel a subscription. If the subscription is within a locked contract term, cancellation is blocked until the contract end date.
- Set **Contract Term** (in months): locks the subscription for a fixed period.
- Set **Auto-Cancel on Term End**: if enabled, the system automatically cancels the subscription on the contract end date (via the nightly scheduler).
- Set **Renewal Reminder Days**: how many days before the renewal date to send an email reminder. Leave blank to disable reminders for this subscription.
- Send a test renewal reminder email immediately ("Test Reminder" button in edit dialog).

**Automated Renewal Logic (runs nightly at 09:00–09:10 UTC):**
1. **Renewal Reminder emails** are sent per subscription, using the subscription-level reminder days. If not set on the subscription, the organisation-level default is used. If neither is set, no reminder is sent.
2. **Auto-cancellation** runs for subscriptions where the contract end date has passed and the auto-cancel flag is on.
3. **Auto-renewal orders** are created as `pending` for any active subscription with a manual payment method whose renewal date is today. Stripe and GoCardless subscriptions are excluded because they renew automatically via their respective payment platforms.

**What Customers See:**
Customers can view their own active subscriptions in their portal, including the renewal date. Self-service cancellation is a planned future feature.

**Key Rules:**
- A subscription within an active contract term cannot be manually cancelled until the end date.
- The test reminder button fires an immediate email regardless of the scheduled time — useful for verifying email templates.
- Reminder tracking is per-renewal-date: once a reminder is sent for a given date, it will not be resent. When the renewal date updates to the next cycle, the system resets and will send again at the right time.

---

### MODULE 7: Enquiries

**Purpose:** Manage incoming service requests and scoping conversations from customers.

**Key Screens:**
- Enquiries list with filters (status, date range, email)
- Enquiry detail view with full conversation history

**Enquiry Statuses:**
- `Pending` — just received, not yet reviewed
- `Requested` — admin has requested a formal scope of work
- `Responded` — admin has replied
- `Closed` — resolved, no further action

**Primary Actions:**
- View enquiry content including any form fields submitted by the customer.
- Update the status of an enquiry.
- Delete an enquiry (with confirmation).
- Export enquiries to CSV.

**Key Rules:**
- Enquiries are automatically scoped to the tenant. Platform Admin sees all; partner admin sees only their own.
- The enquiry captures the exact form fields submitted at the time. These are stored immutably.

---

### MODULE 8: Resources (Knowledge Base)

**Purpose:** A content management system for articles, guides, scopes of work, SOPs, and help documents that can be sent to or accessed by customers.

**Key Screens:**
- Resources list (searchable, filterable by category)
- Resource editor (rich text, title, slug, category, tags)
- Resource Templates sub-tab
- Resource Categories sub-tab
- Email Template sub-tab (for resource delivery)

**Resource Categories:**
- Scope – Draft
- Scope – Final Lost
- Scope – Final Won *(locked once set — see Scope Final rule)*
- Blog
- Help
- Guide
- SOP
- Other

**Primary Actions:**
- Create a resource with rich HTML content (bold, italic, links, images, tables, headers).
- Publish or unpublish a resource.
- Categorise a resource.
- Add tags for searchability.
- Create resource templates (pre-built content blocks that admins can reuse when drafting new resources).
- Send a resource directly to a customer via email using a resource-specific email template.
- Manage resource categories (create/delete custom categories subject to plan limits).

**Scope Final Rule:**
- Once a resource is categorised as either **Scope – Final Won** or **Scope – Final Lost**, the category is locked. It cannot be changed back to a draft or to any other category. This preserves the integrity of accepted or rejected scopes of work.

**What Customers See:**
Published resources (specifically Help, Guide, and Blog categories) can be surfaced on the customer-facing store depending on configuration. Scope documents are internal and not publicly accessible unless specifically shared.

---

### MODULE 9: Documents

**Purpose:** Upload and manage file attachments (PDFs, contracts, etc.) associated with the organisation or its customers.

**Key Screens:**
- Documents list with upload capability
- File viewer

**Primary Actions:**
- Upload documents (PDF and other file types).
- View uploaded documents.
- Delete documents.

---

### MODULE 10: Partner Subscriptions & Partner Orders (Platform Admin Only)

**Purpose:** Manage the billing relationship between the Platform Owner and each Partner Organisation. This is completely separate from the end-customer billing managed by partners.

**Partner Orders — What They Are:**
When a partner purchases a service, platform access, or add-on from the Platform Owner, a Partner Order is created. This is the B2B invoice between the platform and the partner.

**Key Screens:**
- Partner Orders list (filterable by partner, status, date, payment method)
- Create Partner Order dialog
- Edit Partner Order dialog
- Partner Subscriptions list (same filter options)
- Create / Edit Partner Subscription dialog

**Primary Actions (Partner Orders):**
- Create a partner order manually (select partner, plan, amount, currency, due date, payment method).
- Update order status (pending → paid → completed).
- Add internal notes.
- Link to a Stripe or GoCardless payment processor record.

**Primary Actions (Partner Subscriptions):**
- Create a partner subscription (partner, plan, billing interval, amount, currency, start date, billing date, payment method).
- Edit all fields including renewal date, amount, contract term.
- Set auto-cancel on term end.
- Set renewal reminder days (or leave blank to suppress reminders).
- Send a test renewal reminder email instantly.
- Cancel a subscription (blocked if within a contract term).

**What Partners See:**
Partner Admins have a read-only view of their own orders and subscriptions in their portal ("My Orders" and "My Subscriptions" tabs). They cannot edit or create their own billing records — only the Platform Admin can do that.

**Key Rules:**
- License limits are enforced when creating partner subscriptions. If a partner has reached the subscription limit for their plan, creation is blocked.
- Auto-renewal orders for manual-payment partner subscriptions are created automatically by the nightly scheduler, just like customer subscriptions.

---

### MODULE 11: Taxes

**Purpose:** Configure tax rules that apply to orders and subscriptions based on customer location and product type.

**Key Screens:**
- Tax Tables list (country + rate)
- Tax Override Rules (conditional logic overrides)

**Primary Actions:**
- Create standard tax rules by country (e.g., UK VAT at 20%).
- Create conditional override rules (e.g., if customer is in the EU and product type is Software, apply 0% reverse charge).
- Enable or disable individual tax rules.

**Condition Fields Available:**
- Customer country
- Customer province/state
- Product category
- Product name

**Key Rules:**
- Tax rules are evaluated at the time of checkout or manual order creation.
- Override rules take precedence over standard table entries.
- Tax tables support the majority of countries globally.

---

### MODULE 12: Email Templates & Email Log

**Purpose:** Full control over every automated email the system sends, plus a history of all sent emails.

**Key Screens:**
- Email Templates list (organised by category)
- Template editor with rich text, subject line, and variable insertion
- Email Log (searchable by recipient, trigger, status, date range)

**Email Categories:**
- Customer Billing (order confirmations, subscription events)
- Partner Billing (partner order and subscription emails)
- Customer Auth (welcome, password reset)
- Resources (resource delivery emails)
- Enquiries
- System

**Primary Actions:**
- Edit the subject line and HTML body of any email template.
- Enable or disable individual templates (disabling prevents that email from being sent entirely).
- Insert template variables (e.g., `{{customer_name}}`, `{{order_number}}`, `{{renewal_date}}`) using a helper panel.
- Preview rendered email content.
- View email send history: who received what, when, via which provider, and whether it succeeded or failed.

**Key Rules:**
- Variables are replaced at send time with the actual values for that specific record.
- Disabling a template means that event no longer triggers any email. This is useful for temporarily pausing notifications during migrations or testing.
- System templates (like password reset) cannot be deleted but can be edited and disabled.
- Each tenant can only see and edit templates within their own scope. Platform Admin manages all templates.

---

### MODULE 13: Webhooks

**Purpose:** Connect the platform to payment processors (Stripe and GoCardless) so that payment events automatically update order and subscription statuses without manual intervention.

**How It Works:**
When a customer pays via Stripe or a direct debit completes via GoCardless, the payment processor sends a notification ("webhook event") to the platform. The platform processes this event and updates the relevant order or subscription status automatically.

**Webhook Routing:**
The system uses metadata embedded in each payment intent or subscription to determine whether the event is for an **end-customer** order or a **partner** order. Events tagged with `billing_type: partner` are routed to the partner billing processing logic. All other events go to customer billing.

**Key Screens:**
- Webhooks configuration tab
- Webhook delivery log

---

### MODULE 14: Storefront Filters (Partner Admin)

**Purpose:** Allows a Partner Admin to customise which products appear in their customer-facing storefront, by creating filter groups.

**Key Screens:**
- Filters management tab (visible to partner admins)
- Filter group builder (name, type, options list)

**Primary Actions:**
- Create filter groups (e.g., "Service Type" with options: Bookkeeping, Tax, Payroll).
- Edit or remove filters.
- The filters apply dynamically to the product listing on the partner's storefront.

**What Customers See:**
Customers see the filter panel on the products/store page with the options their partner admin has configured. They can use filters to narrow down the service catalogue.

---

### MODULE 15: Website Settings (Partner Admin)

**Purpose:** Control how the storefront looks and behaves for an individual partner's customers.

**Key Screens:**
- Organization Info (store name, logo, brand colours)
- Auth & Pages (login page messaging, banners, custom sliders)
- Forms (configure quote request and scope of work forms)
- System Config (manage integration settings, feature flags)

**Primary Actions:**
- Upload a logo.
- Set primary and accent colours to match brand guidelines.
- Customise the login page carousel/slides (images + text).
- Enable or disable features (e.g., GoCardless, Stripe, quote requests, resource portal).
- Configure custom quote request form fields.

---

### MODULE 16: Settings (Partner Admin)

**Purpose:** Manage the organisation-level configuration that applies to all subscriptions and notifications.

**Key Screens:**
- Organisation Address section (used on invoices and documents)
- Subscription Notifications section (default reminder days)
- System configuration values (integration keys, colour overrides)

**Primary Actions:**
- Save or update the registered organisation address.
- Set the **Default Renewal Reminder Days** for the organisation — the number of days before renewal to send a reminder email to customers. Leave blank to disable all reminders at the organisation level (individual subscriptions can still override this).

---

### MODULE 17: Users & Roles (Partner Admin)

**Purpose:** Manage admin and staff accounts within a partner organisation, with granular permission control.

**Key Screens:**
- Users list with status badges
- Create / Edit User dialog (name, email, password, role)
- Role assignment with module-level permissions

**User Roles:**
- **Partner Super Admin** — full access to everything within the org
- **Partner Admin** — near-full access, set at creation
- **Partner Staff** — limited access, module-level permissions configured per user
- **Custom** — fully custom permission set built by the Super Admin

**Module-Level Permissions:**
Admins can grant or restrict access to specific modules per user: Customers, Orders, Subscriptions, Products, Resources, Enquiries, Documents, Settings, and more.

**Primary Actions:**
- Create a new user (email, name, password, role).
- Edit a user's name, email, or permissions.
- Activate or deactivate a user.
- View audit logs for a specific user.

**Key Rules:**
- Creating a user counts against the plan's `max_users` limit.
- A Super Admin cannot deactivate themselves.
- Password must meet complexity requirements: minimum 10 characters, at least one uppercase, one lowercase, one number, and one symbol.

---

### MODULE 18: Custom Domains (Partner Admin)

**Purpose:** Allow a partner to serve the platform on their own custom domain (e.g., `portal.brightaccounting.co.uk`).

**Primary Actions:**
- Add a custom domain.
- Verify DNS ownership.
- Set as primary domain.

---

### MODULE 19: API Keys (Platform Admin)

**Purpose:** Generate and manage API keys for programmatic access to the platform's data.

**Key Screens:**
- API Keys list
- Create Key dialog (name, expiry, permissions)

**Primary Actions:**
- Create an API key with a name and optional expiry date.
- Revoke an existing key.
- Copy the key value (shown only once at creation).

---

### MODULE 20: Integrations Overview

**Purpose:** A central overview of all third-party services connected to the platform, with connection status indicators.

**Connected Services:**
- **Zoho CRM** — customer and deal sync
- **Zoho Books** — invoice and accounting sync
- **Zoho WorkDrive** — file storage and document management
- **Stripe** — card payments
- **GoCardless** — direct debit payments
- **Resend** — transactional email delivery
- **Exchange Rate API** — live currency conversion for multi-currency pricing
- **Google Drive / OneDrive** — *(Coming Soon)*

---

### MODULE 21: Logs & Audit Trail

**Purpose:** Full traceability of all actions taken on the platform — who did what and when.

**Key Screens:**
- Audit Logs list with filters (entity type, action, actor, date range)
- Per-record audit history (accessible from any edit dialog with a "Logs" button)

**Tracked Actions Include:**
- Customer created / edited / deleted
- Order created / updated / refunded
- Subscription created / cancelled / renewed
- User created / deactivated
- Product enabled / disabled
- Email template edited
- Settings changed
- Partner organisation created / disabled

**Key Rules:**
- Audit logs are immutable. They cannot be edited or deleted.
- Every admin action is attributed to the user who performed it.
- The Platform Admin can see audit logs for all tenants. Partners see only logs for their own organisation.

---

### MODULE 22: GDPR Tools

**Purpose:** Handle data subject access requests and right-to-erasure requests in compliance with data protection regulations.

**Primary Actions:**
- Record a GDPR data access request.
- Record a right-to-erasure (deletion) request.
- Track request status.
- Export a customer's data on request.

---

## 6. Customer-Facing Store (End Customer Experience)

The storefront is what end-customers interact with directly. It is scoped to a specific partner organisation and reflects that partner's branding, products, and configuration.

**Key Pages:**
- **Home / Landing** — customised welcome message, hero image, and call-to-action
- **Store / Services** — filterable product catalogue using the partner's configured filters
- **Checkout** — add to basket, apply promo codes, choose payment method, accept terms
- **My Account** — view profile, update address and payment details
- **My Orders** — full order history with status
- **My Subscriptions** — active subscriptions with renewal dates
- **Resources / Knowledge Base** — published Help, Guide, and Blog articles
- **Request a Quote** — submit a custom enquiry using the partner's configured form
- **Documents** — view documents shared by the admin

**Payment Flows:**
- *Stripe (Card):* Customer is redirected to a hosted Stripe Checkout page, completes payment, and is returned to a confirmation page. The order status updates automatically via webhook.
- *GoCardless (Direct Debit):* Customer authorises a Direct Debit mandate. Once authorised, payments are collected automatically on future billing dates.
- *Bank Transfer:* Customer is shown the bank details and instructed to transfer manually. Admin monitors and marks the order as paid manually.
- *Offline:* Cash or cheque. Admin marks as paid manually.

---

## 7. Automated Background Jobs

The platform runs three automated tasks every day between 09:00 and 09:10 UTC:

| Job | When It Runs | What It Does |
|-----|-------------|--------------|
| Renewal Reminder Emails | 09:00 | For each active subscription, checks if today is exactly `reminder_days` before the renewal date. If yes, sends a reminder email to the customer or partner admin. Skipped if `reminder_days` is blank. |
| Auto-Cancel Subscriptions | 09:05 | Finds all active subscriptions where the contract end date is today or in the past AND `auto_cancel_on_termination` is enabled. Cancels them and sends a cancellation email. |
| Auto-Create Renewal Orders | 09:10 | For active manual-payment subscriptions whose renewal date is today, creates a new `pending` order for the admin to action. Stripe/GoCardless subscriptions are excluded — they renew automatically. |

---

## 8. Notifications & Email System

The platform sends automated emails for the following events (all configurable and disableable per template):

**Customer Events:**
- Welcome / account created
- Password reset
- Order placed
- Order status updates (paid, completed, cancelled, refunded)
- Subscription created
- Subscription renewal reminder
- Subscription cancelled / terminated
- Resource delivered

**Partner Events:**
- New partner order received
- Partner subscription created
- Partner subscription renewal reminder
- Partner subscription cancelled / terminated

**System Events:**
- Password reset for admin users
- New enquiry received

All emails are sent via the configured provider (Resend or Zoho Mail). Each template supports HTML formatting and dynamic variables. Admins can test any renewal reminder email immediately using the "Test Reminder" button on the subscription edit dialog.

---

## 9. Glossary

| Term | Plain-English Meaning |
|------|-----------------------|
| **Tenant** | An isolated organisation on the platform. Every partner org and the platform itself are each a tenant. Data never crosses between tenants. |
| **Partner Organisation (Partner Org)** | An accounting firm or agency that has been granted access to the platform by the Platform Owner. They use the platform to serve their own customers. |
| **Partner Code** | A unique short-name (e.g., `bright-accounting`) that identifies a Partner Organisation. Used at login and can be embedded in URLs. Auto-generated from the org name. |
| **Platform Admin** | The operator of the platform itself. Has global access across all tenants. |
| **Tenant Isolation** | The system rule that ensures each organisation's data is completely invisible to all other organisations. |
| **Plan** | A licensing tier assigned to a Partner Organisation that sets hard limits on usage (max users, max orders per month, etc.). |
| **License Limit** | A specific cap defined in the partner's Plan. When reached, the system blocks further additions. |
| **Scope Final** | A resource category status ("Scope – Final Won" or "Scope – Final Lost") that is permanently locked once set. Used to preserve the integrity of agreed or rejected scopes of work. Cannot be changed or reversed. |
| **Override Code** | A special code an admin can generate to bypass certain platform restrictions — for example, to allow a customer to access a product that is otherwise restricted. |
| **Partner Map** | A status on a customer record indicating whether that customer has been verified as belonging to a specific partner. Used in scenarios where customers existed before a partner relationship was formalised. |
| **Contract Term** | A fixed duration (in months) for a subscription, during which cancellation is blocked. Set per subscription or defaulted from the product. |
| **Auto-Cancel on Term End** | A flag on a subscription that, when enabled, automatically cancels the subscription when its contract end date arrives. |
| **Reminder Days** | The number of days before a renewal date to send an automated reminder email. Configurable per subscription, with an org-level default. Blank = no reminders. |
| **Terms Snapshot** | An immutable copy of the product's terms and conditions captured at the time a customer accepted them during checkout. Preserved permanently on the order record even if terms are later updated. |
| **Webhook** | An automated message sent by a payment processor (Stripe or GoCardless) to the platform when a payment event occurs (e.g., payment succeeded, mandate authorised). The platform processes this to update order/subscription statuses without manual intervention. |
| **Promo Code** | A discount code a customer can enter at checkout. Can be a fixed amount or percentage, time-limited, use-limited, and product-specific. |
| **Base Currency** | The primary currency set for a Partner Organisation, used as the default for pricing and invoicing within that org. |
| **Mandate** | A GoCardless authorisation from a customer allowing the platform to collect direct debit payments from their bank account on future dates. |

---

*This document reflects the platform as of February 2026. It is intended as a living document and should be updated as features are released.*
