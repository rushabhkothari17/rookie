# PRD — Admin SaaS Platform (Automate Accounts)

## Original Problem Statement
Multi-tenant SaaS admin platform for partner organizations managing customer subscriptions, products, and documents. Partners each have their own branded storefront with customers.

## Architecture
- **Backend**: FastAPI + MongoDB
- **Frontend**: React + TypeScript + ShadCN UI
- **Auth**: JWT-based with multi-role: platform_admin, partner_super_admin, partner_admin, customer
- **Deployment**: Kubernetes (preview URL: https://config-management-2.preview.emergentagent.com)

## User Personas
1. **Platform Admin** (`admin@automateaccounts.local`) — manages all partner tenants
2. **Partner Admin** (`admin@ligerinc.local`) — manages their own org, customers, products
3. **Customer** — accesses the partner's e-shop/portal

## Core Requirements (Implemented)

### Admin Panel Sidebar Structure (CURRENT as of Feb 2026)
```
PLATFORM: Partner Orgs
PEOPLE: Users, Customers
COMMERCE: Products, Subscriptions, Orders, Enquiries, Taxes
CONTENT: Resources, Documents, Email Templates, References
SETTINGS:
  - Organization Info      (renamed from "Branding & Hero")
  - Auth & Pages           (standalone, includes Footer & Nav)
  - Forms                  (standalone)
  - System Config          (standalone, without Base Currency)
  - Custom Domains
INTEGRATIONS: Connect Services, API, Webhooks, Logs
```

### What's Implemented

#### Product 1: Mandatory Partner Address (Feb 2026)
- Partner signup requires: Line 1, City, Postal, State/Province, Country
- OrgAddressSection in Organization Info tab, appears directly below Store Name
- Country and State/Province are dropdowns (from /utils/provinces API)
- Only partner admins see address section (platform admins see null)
- Backend: PUT /api/admin/tenants/{id}/address, GET /api/admin/tenants/my

#### Product 2: Zoho WorkDrive Integration (Feb 2026)
- OAuth flow in Connect Services (Cloud Storage category)
- Customer folders auto-created in WorkDrive on customer creation/rename
- Backfill endpoint: POST /api/documents/sync-folders
- Admin Documents tab: file management table with notes, edit, delete
- Customer-facing /documents page: upload/download (max 5MB), no delete
- WorkDrive-enabled gate: Documents nav tab only shows if partner has WorkDrive connected

#### Admin Panel Restructure (Feb 2026)
- "Website Content" tab DELETED
- "Branding & Hero" renamed to "Organization Info" (top-level tab)
  - Includes: Store Name, Address, Logo, Brand Colors, Hero Banners, Base Currency
- "Auth & Pages" as top-level tab (includes Footer & Nav at bottom)
  - New: "Documents Page" tile (customizes /documents page text)
- "Forms" as top-level tab
- "System Config" as top-level tab (Operations + FeatureFlags, no Base Currency)

#### Documents Page Customization (Feb 2026)
- Partner admins can customize via Auth & Pages > Documents Page tile:
  - Nav tab label (in top navigation)
  - Page title, subtitle
  - Upload section label, hint text
  - Empty state text
- Fields stored in website_settings collection
- TopNav uses ws.nav_documents_label || "Documents"
- Documents.tsx uses ws.documents_page_* with fallback defaults

## Key API Endpoints

### Partner Address
- `GET /api/admin/tenants/my` — get own tenant (includes address)
- `PUT /api/admin/tenants/{id}/address` — update address

### WorkDrive & Documents
- `GET /api/oauth/workdrive/authorize` — OAuth start
- `GET /api/oauth/workdrive/callback` — OAuth callback
- `GET /api/documents` — admin: list all files
- `GET /api/documents/customer` — customer: list their files
- `POST /api/documents/upload-url` — presigned upload
- `DELETE /api/documents/{file_id}` — delete
- `POST /api/documents/{file_id}/notes` — add notes
- `POST /api/documents/sync-folders` — backfill all customer folders

### Website Settings
- `GET /api/admin/website-settings` — includes all fields incl. documents_page_*
- `PUT /api/admin/website-settings` — save settings
- `GET /api/website-settings` — public settings (used by frontend context)

## Key DB Schema
- `tenants`: `address: {line1, line2, city, region, postal, country}`
- `oauth_connections`: WorkDrive tokens + `settings.parent_folder_url`
- `website_settings`: includes `nav_documents_label`, `documents_page_title`, `documents_page_subtitle`, `documents_page_upload_label`, `documents_page_upload_hint`, `documents_page_empty_text`

## Prioritized Backlog

### P0 (Critical — must do next)
- None currently

### P1 (High — next sprint)
- Google Drive & OneDrive integration (currently "Coming Soon" in Connect Services)
- Admin: allow editing partner organization address from admin panel (platform admin view)

### P2 (Medium)
- Customer Portal: self-service subscription cancellation
- Customer Portal: display renewal dates
- Customer Portal: "Reorder" button
- Centralize email settings into a single tab

### P3 (Backlog / Future)
- Security audit / penetration testing
- Comprehensive unit test coverage
- Mobile app version of customer portal

## Test Credentials
- **Platform Admin**: `admin@automateaccounts.local` / `ChangeMe123!` (partner code: `automate-accounts`)
- **Partner Admin (Liger Inc)**: `admin@ligerinc.local` / `ChangeMe123!`
- **Customer (Liger Inc)**: `customer1@ligerinc.local` / `ChangeMe123!`
- **Test Partner (from iter134)**: `TEST_valid_iter133@test.local` / `ChangeMe123!` (code: `test-org-iter133-valid`)

## 3rd Party Integrations
- GoCardless (Payments)
- Stripe (Payments)
- Zoho Mail (Email)
- Zoho WorkDrive (Cloud Storage)
- exchangerate-api.com (FX rates)
- jspdf & html2canvas (Frontend PDF Generation)

## Files of Reference
- `backend/routes/admin/tenants.py` — address endpoints
- `backend/routes/documents.py` — WorkDrive document endpoints
- `backend/routes/integrations/workdrive_service.py` — WorkDrive service
- `backend/routes/integrations/oauth.py` — OAuth flows
- `backend/models/models.py` — all Pydantic models (incl. WebsiteSettingsUpdate)
- `backend/routes/admin/website.py` — DEFAULT_WEBSITE_SETTINGS
- `frontend/src/pages/Admin.tsx` — admin sidebar + tabs
- `frontend/src/pages/admin/WebsiteTab.tsx` — all settings tab content
- `frontend/src/pages/admin/AdminDocumentsTab.tsx` — admin documents management
- `frontend/src/pages/Documents.tsx` — customer-facing documents
- `frontend/src/contexts/WebsiteContext.tsx` — website settings context
- `frontend/src/components/TopNav.tsx` — customer nav with Documents link
- `frontend/src/pages/auth/PartnerSignup.tsx` — mandatory address signup
