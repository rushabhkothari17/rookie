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
├── models.py               # WebsiteSettingsUpdate (75+ fields), ResendVerificationRequest
├── routes/
│   ├── auth.py             # POST /api/auth/resend-verification-email (added), configurable verification email
│   ├── checkout.py         # Payment provider enabled checks (stripe + gocardless global flag)
│   └── admin/
│       └── website.py      # DEFAULT_WEBSITE_SETTINGS with 75+ field defaults
├── services/
│   └── settings_service.py # Structured settings - OverrideCodes/Checkout categories; seed() migrates existing DB records
```

### Frontend
```
/app/frontend/src/
├── components/
│   ├── FormSchemaBuilder.tsx
│   ├── admin/
│   │   └── CheckoutSectionsBuilder.tsx
│   └── TopNav.tsx
├── contexts/
│   └── WebsiteContext.tsx     # 75+ dynamic fields
├── pages/
│   ├── VerifyEmail.tsx        # Added "Resend verification code" button
│   ├── admin/
│   │   ├── WebsiteTab.tsx     # Footer & Nav → tile layout; Bank Transfer merged into Checkout Success; Zoho amber box removed
│   │   └── ReferencesSection.tsx  # All items get delete button (removed !ref.system guard)
```

---

## What's Been Implemented

### Session — Iteration 49 (Feb 2026)
- **P0 Bug Fix**: Payment providers now properly blocked at backend when disabled in admin settings. Both `POST /api/checkout/session` (Stripe) and `POST /api/checkout/bank-transfer` (GoCardless) check global `stripe_enabled`/`gocardless_enabled` flags before processing.
- **P0 Bug Fix**: Added `POST /api/auth/resend-verification-email` endpoint + "Resend verification code" button on `/verify` page.
- **P1**: Removed redundant "Bank Transfer Success" admin tile. Content merged into "Checkout Success" slide-over (single place to manage both payment types).
- **P1**: Removed special Zoho amber box from References section. All references now treated equally with delete button.
- **Task**: `override_code_expiry_hours` moved to "OverrideCodes" category in settings_service.py, appears in its own card in System Config.
- **Task**: `partner_tagging_enabled` moved to "Checkout" category, appears in Checkout Page Builder slide-over.
- **Task**: Footer & Nav section refactored from long scrolling form to tile-based layout with 5 tiles + SlideOver editors.
- **settings_service.py seed()**: Now migrates stale metadata (category/description/value_type) for existing DB settings records.

### Earlier Sessions
- Admin Panel Reorganization (Phase 1 & 2): Sidebar navigation, tile-based UI, SlideOver editors
- Email Templates section, Store Hero merge into Branding
- AppFooter.tsx, SlideOver.tsx components
- Dynamic checkout sections builder
- Full page whitelabeling (75+ settings)

---

## P0/P1/P2 Backlog (Remaining)

### P0 — None currently

### P1 — None currently (all user-reported items resolved)

### P2 — Future
- Admin Dashboard for visualizing key business metrics
- Fix known low-priority React Hydration Warning in browser console

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

### Phase 7 — Full Whitelabel Audit + Dynamic Checkout Section Builder (Feb 2026)
- **35+ new website_settings fields** added for complete page content whitelabeling
- **CheckoutSuccess page**: title, paid/pending/expired messages, next steps (3 steps), portal link text — all dynamic
- **BankTransferSuccess page**: title, message, instructions (3), next steps (3) — all dynamic
- **NotFound (404) page**: title and back link text — dynamic; moved inside BaseLayout for consistent navbar
- **GoCardlessCallback page**: processing/success/error titles and messages, return button text — all dynamic
- **VerifyEmail page**: label, title, subtitle — all dynamic
- **Portal page**: title and subtitle — dynamic
- **Profile page**: label, title, subtitle — dynamic
- **Cart page**: cart title, clear button text, currency unsupported message, no payment methods message — all dynamic
- **New "Page Content" section** added to Website admin sidebar with grouped fields for every page
- **Error Messages section** extended with Cart page strings
- **Dynamic Checkout Section Builder** (`CheckoutSectionsBuilder.tsx`): admins can add/edit/reorder/hide/delete sections, each with custom form fields (FormSchemaBuilder)
- **Cart.tsx** updated: if `checkout_sections` is non-empty, renders dynamic sections instead of legacy Zoho/Partner; special `partner_tag_response = Not yet` case handled for override codes
- Backend: `WebsiteSettingsUpdate` and `DEFAULT_WEBSITE_SETTINGS` updated with all 35+ new fields
- WebsiteContext: 75+ fields now in TypeScript interface with defaults
- Fixed: Duplicate Footer & Nav section bug in WebsiteTab.tsx

---

---

### Phase 9 — Major Admin Panel Restructure + Articles Hero Fix + Footer Expansion (Feb 2026)
- **Articles page hero**: Now matches Store page style exactly (dark rounded-3xl card, glow effects, red dash separator, identical layout and typography).
- **Auth & Pages mega-section**: Replaced separate auth/checkout/errors/pages sidebar items with a single consolidated tile-grid section. Groups: Authentication (Login, Sign Up+Form, Verify Email), App Pages (Portal, Profile, 404, GoCardless), Checkout Flow (toggles + builder + success pages), Messages (checkout errors, form responses). Each tile opens a SlideOver.
- **Forms section simplified**: Only Quote Request + Scope Request forms remain (Sign Up form moved to Auth & Pages → Sign Up tile).
- **Footer & Nav expanded**: Added About Us section (title + text), customizable section titles for nav/contact/social, social media links (Twitter/X, LinkedIn, Facebook, Instagram, YouTube).
- **System Config**: `override_code_expiry_hours` now appears in dedicated "Override Codes" sub-section, separated from Operations.
- **Backend**: New footer fields added to `WebsiteSettingsUpdate` model and `DEFAULT_WEBSITE_SETTINGS`.
- Tested at 100% pass rate (14/14 tests via testing_agent_v4_fork, iteration_48.json).
- **P0 Fix**: Email Templates section was not rendering (EmailSection component was imported but never placed in JSX). Fixed.
- **Branding & Hero merged**: Store Hero Banner and Articles Hero Banner fields moved into the Branding section. Removed separate "Store Hero" sidebar entry.
- **Forms section — tile layout**: Each form (Quote, Scope, Signup) now shown as a card tile with field count badge. Edit opens a SlideOver panel with form labels + FormSchemaBuilder.
- **Page Content section — tile layout**: 7 page tiles in a responsive grid (Checkout Success, Bank Transfer, 404, GoCardless, Verify Email, Portal, Profile). Edit opens a SlideOver panel with page-specific fields.
- **AppFooter bug fixed**: `ws.brand_name` → `ws.store_name` (brand_name doesn't exist in WebsiteSettings interface).
- **Articles Hero**: Added articles_hero_label/title/subtitle to WebsiteData interface and WEB_DEFAULTS (was missing from admin panel despite being in backend).
- Tested at 100% pass rate (13/13 tests via testing_agent_v4_fork, iteration_47.json).

---

## P0/P1/P2 Backlog

### P0 (Critical)
- None currently

### P1 (Important)
- Admin Dashboard — KPI cards for revenue, subscriptions, orders, recent activity
- Quote/Scope requests tab should display extra_fields in detail view

### P2 (Nice to have)
- Email delivery live testing (currently mocked; configure Resend key to enable)
- Zoho CRM/Books integration
- SlideOver unique test IDs (cosmetic — both use same data-testid='slideover-panel')

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
