# Product Requirements Document — Automate Accounts (Whitelabel Platform)

## Original Problem Statement
Build a fully customizable "whitelabel" solution that can be resold. No content should be hardcoded. Everything must be dynamically managed from the admin panel.

## Core Requirements (User Specified)
1. **Fully Dynamic Content** — No hardcoded text anywhere (hero, auth, forms, navigation, email, errors, all pages)
2. **Website Configuration Module** — Admin panel "Website Content" tab managing all sitewide content
3. **Customizable Product Pages** — Dynamic sections with rich text (markdown), icons, custom names
4. **Customizable Forms** — ALL forms (Quote, Scope, Signup) fully customizable via schema builder
5. **Admin UX Overhaul** — Tabbed product form, visual icon picker, auto-key generation
6. **Store UI/UX** — Left-sidebar category navigation (scalable)
7. **Data Migration** — Existing products migrated to dynamic sections format
8. **Email Templates** — All emails configurable, cannot be deleted
9. **Integrations Tab** — GoCardless, Stripe, Resend API keys in Website module
10. **Settings Merge** — Settings tab removed, merged into Website Content tab
11. **Dynamic Checkout Section Builder** — Admins define sections with custom form fields on cart page
12. **Complete Page Whitelabeling** — All pages (CheckoutSuccess, BankTransfer, 404, GoCardless, VerifyEmail, Portal, Profile, Cart) use dynamic strings

---

## Architecture

### Backend
```
/app/backend/
├── models.py               # WebsiteSettingsUpdate (75+ fields), QuoteRequest, RegisterRequest
├── routes/
│   ├── auth.py             # profile_meta support, configurable verification email
│   ├── articles.py         # Configurable email templates
│   └── admin/
│       └── website.py      # DEFAULT_WEBSITE_SETTINGS with 75+ field defaults
├── services/
│   └── settings_service.py # Structured settings (Payments/Email/Zoho/Branding/Operations)
```

### Frontend
```
/app/frontend/src/
├── components/
│   ├── FormSchemaBuilder.tsx          # Visual form field schema editor
│   ├── admin/
│   │   └── CheckoutSectionsBuilder.tsx  # Dynamic checkout section builder (NEW)
│   ├── IconPicker.tsx
│   └── TopNav.tsx
├── contexts/
│   └── WebsiteContext.tsx     # 75+ dynamic fields
├── pages/
│   ├── Admin.tsx              # Settings tab REMOVED, merged into Website Content
│   ├── Cart.tsx               # Fully dynamic (new checkout_sections + legacy fallback)
│   ├── CheckoutSuccess.tsx    # All strings from ws.checkout_success_*
│   ├── BankTransferSuccess.tsx # All strings from ws.bank_*
│   ├── NotFound.tsx           # ws.page_404_title/link_text
│   ├── GoCardlessCallback.tsx  # ws.gocardless_* fields
│   ├── VerifyEmail.tsx        # ws.verify_email_*
│   ├── Portal.tsx             # ws.portal_title/subtitle
│   ├── Profile.tsx            # ws.profile_label/title/subtitle
│   └── admin/
│       └── WebsiteTab.tsx     # 12-section admin panel + new CheckoutSectionsBuilder
```

---

## Website Settings Sections (WebsiteTab)
| Section | Content |
|---------|---------|
| Branding | Store name, logo upload, primary/accent colors |
| Store Hero | Hero label, title, subtitle |
| Auth Pages | Login/register page text |
| Forms | Quote/Scope/Signup form schema builders + text labels |
| Email Templates | From name, article email subject/CTA/footer, verification email |
| Error Messages | Partner tagging prompt, override required, cart empty, quote/scope success |
| Footer & Nav | Footer text, copyright, nav link labels, contact info |
| Links & URLs | Zoho URLs (signup, partner tag, access instructions) |
| Integrations | Stripe, GoCardless, Resend API keys |
| System Config | Service fee rate, feature flags, operations settings |

---

## Form Schema System
- Schemas stored as JSON strings in `website_settings` collection
- Three form schemas: `quote_form_schema`, `scope_form_schema`, `signup_form_schema`
- Field types: text, email, tel, number, date, textarea, select, checkbox, file, password
- Locked fields (core auth): cannot be deleted, can be shown/hidden
- Custom extra fields in signup → stored in `profile_meta` on user record
- Custom extra fields in quote/scope → stored in `extra_fields` on quote/scope record

---

## What Has Been Implemented

### Phase 1 - Dynamic Content Architecture (Session 1)
- WebsiteContext with global settings provider
- website_settings MongoDB collection
- Dynamic text on Login, Signup, Store Hero, TopNav, Quote modals
- Store page redesigned with left-sidebar categories
- Visual IconPicker component

### Phase 2 - Product Customization (Session 1)
- custom_sections on products (tabbed product form, SectionsEditor)
- react-markdown support for section content
- Migration of 21 existing products to new format

### Phase 3 - Whitelabel Expansion (Session 2 - Feb 2026)
- Merged Settings tab into Website Content (10 sections)
- FormSchemaBuilder component for all forms
- Dynamic form rendering in ProductDetail.tsx (quote + scope)
- Dynamic signup form (show/hide fields, custom extra fields → profile_meta)
- Email templates configurable (articles.py uses settings)
- Auth verification email uses configurable subject/body
- Error messages configurable (Cart.tsx, etc.)
- Nav labels configurable (TopNav.tsx)
- Integrations section (Stripe/GoCardless/Resend keys)
- Links & URLs section (Zoho URLs)
- System Config section (fee, flags)
- profile_meta on RegisterRequest → stored in user record
- extra_fields on QuoteRequest + ScopeRequestFormData

---

### Phase 6 — Payments UI Redesign, Cart Dynamic Content, Whitelabel Audit (Feb 2026)
- Payments section: compact provider cards with colored status dot, pill Enable/Disable toggle, pencil icon that expands inline with label/desc/API keys/fee rate
- Customer filter: dynamically shows only globally-enabled payment providers (GoCardless/Stripe) via useWebsite()
- Zoho system links moved to References section (amber System Links panel) — removed from System Config
- New 'Checkout' section in Website admin: configure Zoho section (title/options/notes/toggle), Partner section (title/desc/options/toggle), Custom Extra Questions (FormSchemaBuilder)
- Cart.tsx: all Zoho section content, partner tagging content, options — fully dynamic from website settings
- Custom extra checkout questions supported via checkout_extra_schema; answers stored in orders as extra_fields with audit log
- CartContext: fixed lazy initializer (prevents flash-of-empty-cart on load)
- Checkout button disabled state now respects show/hide flags for Zoho and partner sections
- Whitelabel audit: removed hardcoded automateaccounts.com email/URL from ProductDetail.tsx, "Secure payment via Stripe" from StickyPurchaseSummary.tsx

- Removed redundant 'Integrations' tab from Website admin sidebar
- Added 'Payments' section (GoCardless + Stripe cards with toggle, display labels, API keys, fee rates)
- Removed 'Payment Settings' from System Config (now lives in Payments tab)
- Email section retains its own Resend provider config (clean separation)
- Customer module: replaced Bank Transfer/Card Payment columns with 'Payment Methods' chips column
- Customer module: replaced bank/card filters with unified 'Payment Mode' dropdown (GoCardless/Stripe/Both/None)
- allowed_payment_modes values standardized: 'bank_transfer' → 'gocardless', 'card' → 'stripe'
- Cart.tsx: payment method labels, descriptions, and fee % are now fully dynamic from website settings
- Email Templates: TipTap rich text editor added as first tab (alongside HTML Source + Preview)
- Dead code cleanup: removed unused handlePaymentToggle function
- currency_for_country() expanded (Phase 4) to support GBP, AUD, NZD, SGD, INR, ZAR, EUR

- Fixed IndentationError in articles.py (orphaned code from incomplete refactor)
- EmailSection.tsx — full email template editor (9 system templates, enable/disable toggle, HTML editor with variable insertion, live preview, email logs)
- ReferencesSection.tsx — CRUD for key-value references (`{{ref:key}}` syntax usable in templates and content)
- email_service.py — centralized email sending (Resend integration + mocked outbox fallback)
- email_templates routes — GET/PUT for all templates
- references routes — full CRUD
- allowed_payment_modes on Customer edit dialog (Bank Transfer / Card Payment checkboxes)
- Cart.tsx respects allowed_payment_modes (falls back to legacy booleans)
- currency_for_country() expanded to support GBP, AUD, NZD, SGD, INR, ZAR, EUR

---

## P0/P1/P2 Backlog

### P0 (Critical)
- None currently

### P1 (Important)
- Admin Dashboard — KPI cards for revenue, subscriptions, orders, recent activity
- Quote/Scope requests tab should display extra_fields in detail view

### P2 (Nice to have)
- Full whitelabel audit — scan codebase for remaining hardcoded brand references
- Footer component (no global footer currently)
- Email delivery live testing (currently mocked; configure Resend key to enable)
- Zoho CRM/Books integration

### Backlog
- React Hydration Warning (low priority technical debt)
- Admin dashboard metrics/analytics
- Customer notification emails for order status changes

---

## Credentials
- Admin: admin@automateaccounts.local / ChangeMe123!

## Third-Party Integrations
- Stripe (payments — global toggle: stripe_enabled in settings)
- GoCardless (direct debit — global toggle: gocardless_enabled in settings)
- Resend (email — global toggle: email_provider_enabled; falls back to mocked outbox)

## Key API Endpoints
- `GET /api/website-settings` — Public, returns all settings + form schemas
- `GET /api/admin/website-settings` — Admin, returns all settings
- `PUT /api/admin/website-settings` — Admin, updates website settings
- `GET /api/admin/settings/structured` — Admin, returns grouped DB settings
- `PUT /api/admin/settings/key/{key}` — Admin, updates individual setting
- `GET /api/admin/email-templates` — Admin, list all email templates
- `PUT /api/admin/email-templates/{id}` — Admin, update template subject/body/enabled
- `GET /api/admin/email-logs` — Admin, view email send logs
- `GET /api/admin/references` — Admin, list all references
- `POST /api/admin/references` — Admin, create reference
- `PUT /api/admin/references/{id}` — Admin, update reference
- `DELETE /api/admin/references/{id}` — Admin, delete reference
- `PUT /api/admin/customers/{id}/payment-methods` — Admin, set allowed_payment_modes
