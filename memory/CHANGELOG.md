# Changelog

## Feb 2026 — 100% Audit Trail Coverage
- **taxes.py**: Added `create_audit_log` to all 10 write endpoints (tax settings, tax table, override rules, customer tax-exempt, invoice settings, invoice templates)
- **documents.py**: Added `create_audit_log` to upload, update, delete document endpoints; scoped audit log query to tenant_id
- **admin/integration_requests.py**: Added `create_audit_log` to submit, status_update, and note_add endpoints
- **uploads.py**: Added `create_audit_log` to file upload endpoint (temp files for intake questions)
- **zoho_service.py**: Bridged Zoho CRM & Books auto-sync outcomes to audit trail — success/failure of actual sync calls now appear in `audit_trail` with `actor=system`
- All 20 backend tests pass (test_iter143_audit_trail_coverage.py)

## Feb 26, 2026 — Admin Panel Settings Restructure
- Renamed "Branding & Hero" → "Organization Info" as top-level SETTINGS tab
- "Auth & Pages", "Forms", "System Config" as separate top-level SETTINGS tabs
- Footer & Nav merged into Auth & Pages; Store Hero + Articles Hero moved as tiles
- "Website Content" tab deleted
- OrgAddressSection added to Organization Info (right under Store Name)
- Base Currency moved from System Config to Organization Info
- Documents page customization: nav label, title, subtitle, upload text, empty text
- SetupChecklistWidget updated to new tab names

## Feb 27, 2026 — Multi-Feature Auth, Signup & Admin Fixes
- **Back buttons**: Login signin step + customer/partner signup → partner signin page
- **Email read-only in Profile**: Lock icon, bg-slate-50 styling, "Admins can change" hint
- **Phone validation**: 7–15 digit regex validation on signup & My Profile
- **Password criteria hint**: "Min. 10 chars · uppercase · number · special char" shown on signup + force-change modal
- **bank_transactions removed** from Admin > Users > Modules (ADMIN_MODULES)
- **First-time login password change**: `must_change_password` flag in partner-login response; ForcePasswordChangeModal in Login.tsx; POST /api/auth/change-password endpoint
- **Signup bullets editable**: signup_bullet_1/2/3 configurable via Admin > Auth & Pages > Sign Up Page slide
- **Address as one block** in signup form: isFieldVisible("address") controls visibility; required from schema controls asterisks; LOCKED_STANDARD_KEYS ensures backward compat
- **Company/Address asterisk bug fixed**: SIGNUP_DEFAULT_SCHEMA seeds locked standard fields so required flags work correctly
- **Countries from tax tables**: GET /api/utils/countries endpoint; signup page uses dynamic list
- **Phone required synced with signup form**: Profile.tsx reads phoneRequired from ws.signup_form_schema
- **Hero banners as tiles**: Store Hero Banner + Articles Hero Banner tiles added to Auth & Pages; removed from Org Info inline fields

## Earlier Sessions
- Zoho WorkDrive OAuth integration
- Admin Documents management tab
- Customer-facing Documents portal (/documents)
- Partner mandatory address on signup
- WorkDrive folder auto-creation per customer
