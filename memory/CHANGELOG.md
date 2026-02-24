# Changelog

## Session: Feb 2026 — Bug Fix Sprint (Fork 9 continuation)

### Fixed Bugs
- **Portal status filter dropdowns** — replaced broken native `<select>` elements with Shadcn `Select` components in `Portal.tsx` (orders & subscriptions filters now work correctly)
- **Users & Customers "Logs" buttons** — fixed `require_super_admin` in `security.py` to allow `partner_super_admin` and `platform_admin` roles (was previously 403 for all users); added try-catch error handling to all logs buttons
- **Subscription logs display** — fixed field name (`timestamp` → `created_at`), now shows actor, action, timestamp, and details in a clean layout

### New Features
- **Confirmation dialogs (AlertDialog)** for all destructive/critical actions:
  - Subscriptions: Cancel, Renew
  - Orders: Delete, Charge
  - Users/Customers: Deactivate/Activate
  - Products: Deactivate/Activate
  - Categories: Toggle active, Delete
  - Promo Codes: Delete button added + confirmation
  - Terms: Delete button added + confirmation
  - Quote Requests: Delete button added + confirmation
- **Logs functionality** added to previously missing modules:
  - Article Categories (frontend + backend endpoint)
  - Article Templates (frontend + backend endpoint)
  - Article Email Templates (frontend + backend endpoint)
- **Backend DELETE endpoint** for quote requests (`DELETE /api/admin/quote-requests/{id}`)
- **Seed script** for Tenant B Test — `backend/seed_tenant_b.py` populates categories, products (6 types including zero-price for scope ID testing), customers, promo codes, subscriptions, orders, quote requests, and terms

### Files Modified
- `backend/core/security.py`
- `backend/routes/admin/quote_requests.py`
- `backend/routes/article_categories.py`
- `backend/routes/article_email_templates.py`
- `backend/routes/article_templates.py`
- `frontend/src/components/ui/alert-dialog.jsx` (explicit children prop)
- `frontend/src/pages/Portal.tsx`
- `frontend/src/pages/admin/SubscriptionsTab.tsx`
- `frontend/src/pages/admin/OrdersTab.tsx`
- `frontend/src/pages/admin/UsersTab.tsx`
- `frontend/src/pages/admin/CustomersTab.tsx`
- `frontend/src/pages/admin/ProductsTab.tsx`
- `frontend/src/pages/admin/CategoriesTab.tsx`
- `frontend/src/pages/admin/PromoCodesTab.tsx`
- `frontend/src/pages/admin/TermsTab.tsx`
- `frontend/src/pages/admin/QuoteRequestsTab.tsx`
- `frontend/src/pages/admin/ArticleCategoriesTab.tsx`
- `frontend/src/pages/admin/ArticleTemplatesTab.tsx`
- `frontend/src/pages/admin/ArticleEmailTemplatesTab.tsx`
- `backend/seed_tenant_b.py` (new file)

## Session: Previous — Dropdown Fix Sprint

### Fixed
- Widespread dropdown failures caused by Emergent Visual Editor injecting `<span>` tags into native `<select>` elements
- Created reusable `SearchableSelect` component at `frontend/src/components/ui/SearchableSelect.tsx`
- Replaced all native `<select>` elements throughout the application with Shadcn `Select` or `SearchableSelect` components
