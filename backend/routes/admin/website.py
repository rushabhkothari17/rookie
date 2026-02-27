"""Admin: Website content settings routes."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header

from core.security import require_admin, optional_get_current_user
from core.tenant import get_tenant_filter, tenant_id_of, DEFAULT_TENANT_ID, get_tenant_admin
from db.session import db
from models import WebsiteSettingsUpdate
from services.audit_service import create_audit_log
from services.settings_service import SettingsService

router = APIRouter(prefix="/api", tags=["website-settings"])

_QUOTE_FORM_SCHEMA = json.dumps([
    {"id": "f_name", "key": "name", "label": "Your Name", "type": "text", "required": True, "placeholder": "Full name", "locked": False, "enabled": True, "order": 0},
    {"id": "f_email", "key": "email", "label": "Email", "type": "email", "required": True, "placeholder": "your@email.com", "locked": False, "enabled": True, "order": 1},
    {"id": "f_company", "key": "company", "label": "Company", "type": "text", "required": False, "placeholder": "Company name", "locked": False, "enabled": True, "order": 2},
    {"id": "f_phone", "key": "phone", "label": "Phone", "type": "tel", "required": False, "placeholder": "+1 (555) 000-0000", "locked": False, "enabled": True, "order": 3},
    {"id": "f_message", "key": "message", "label": "Message", "type": "textarea", "required": False, "placeholder": "Tell us about your requirements\u2026", "locked": False, "enabled": True, "order": 4},
])

_SCOPE_FORM_SCHEMA = json.dumps([
    {"id": "s_summary", "key": "project_summary", "label": "Project Summary", "type": "textarea", "required": True, "placeholder": "Describe your project in a few sentences...", "locked": False, "enabled": True, "order": 0},
    {"id": "s_outcomes", "key": "desired_outcomes", "label": "Desired Outcomes", "type": "textarea", "required": True, "placeholder": "What do you want to achieve with this project?", "locked": False, "enabled": True, "order": 1},
    {"id": "s_apps", "key": "apps_involved", "label": "Apps Involved", "type": "text", "required": True, "placeholder": "e.g., Zoho CRM, Zoho Books, Zoho Desk...", "locked": False, "enabled": True, "order": 2},
    {"id": "s_timeline", "key": "timeline_urgency", "label": "Timeline / Urgency", "type": "select", "required": True, "options": ["ASAP (within 2 weeks)|asap", "Within 1 month|1-month", "2-3 months|2-3-months", "Flexible / No rush|flexible"], "locked": False, "enabled": True, "order": 3},
    {"id": "s_budget", "key": "budget_range", "label": "Budget Range", "type": "select", "required": False, "options": ["Under $5,000|under-5k", "$5,000 - $10,000|5k-10k", "$10,000 - $25,000|10k-25k", "$25,000 - $50,000|25k-50k", "$50,000+|50k+", "Not sure yet|not-sure"], "locked": False, "enabled": True, "order": 4},
    {"id": "s_notes", "key": "additional_notes", "label": "Additional Notes", "type": "textarea", "required": False, "placeholder": "Anything else we should know?", "locked": False, "enabled": True, "order": 5},
])

_DEFAULT_ADDRESS_CONFIG = {
    "line1":   {"enabled": True, "required": True},
    "line2":   {"enabled": True, "required": False},
    "city":    {"enabled": True, "required": True},
    "state":   {"enabled": True, "required": False},
    "postal":  {"enabled": True, "required": True},
    "country": {"enabled": True, "required": True},
}

_SIGNUP_FORM_SCHEMA = json.dumps([
    {"id": "su_name",    "key": "full_name",    "label": "Full Name",    "type": "text",    "required": True,  "placeholder": "", "options": [], "locked": True, "enabled": True, "order": 0},
    {"id": "su_company", "key": "company_name", "label": "Company Name", "type": "text",    "required": False, "placeholder": "", "options": [], "locked": True, "enabled": True, "order": 1},
    {"id": "su_job",     "key": "job_title",    "label": "Job Title",    "type": "text",    "required": False, "placeholder": "", "options": [], "locked": True, "enabled": True, "order": 2},
    {"id": "su_phone",   "key": "phone",        "label": "Phone",        "type": "tel",     "required": False, "placeholder": "", "options": [], "locked": True, "enabled": True, "order": 3},
    {"id": "su_address", "key": "address",      "label": "Address",      "type": "address", "required": False, "placeholder": "", "options": [], "locked": True, "enabled": True, "order": 4,
     "address_config": _DEFAULT_ADDRESS_CONFIG},
])

def _migrate_signup_schema(schema_str: str) -> str:
    """Migrate old signup schema format to current format.
    - Removes standalone country/email/password locked fields
    - Adds address field with type 'address' and default address_config
    - Upgrades existing 'address' field from type 'text' to type 'address'
    """
    try:
        fields = json.loads(schema_str) if schema_str else []
        if not fields:
            return schema_str
        has_address = any(f.get("key") == "address" for f in fields)
        has_old_country = any(f.get("key") == "country" and f.get("locked") for f in fields)

        # Step 1: remove old locked fields (email, password, standalone country)
        if has_old_country:
            fields = [f for f in fields if f.get("key") not in ("country", "email", "password") or not f.get("locked")]

        # Step 2: add address field if missing
        if not has_address:
            max_order = max((f.get("order", 0) for f in fields), default=0)
            fields.append({
                "id": "su_address", "key": "address", "label": "Address",
                "type": "address", "required": False, "placeholder": "", "options": [],
                "locked": True, "enabled": True, "order": max_order + 1,
                "address_config": _DEFAULT_ADDRESS_CONFIG,
            })

        # Step 3: upgrade any address field from type 'text' to 'address' and inject address_config
        changed = False
        for f in fields:
            if f.get("key") == "address":
                if f.get("type") != "address":
                    f["type"] = "address"
                    changed = True
                if not f.get("address_config"):
                    f["address_config"] = _DEFAULT_ADDRESS_CONFIG
                    changed = True

        if has_old_country or not has_address or changed:
            fields.sort(key=lambda f: f.get("order", 0))
            return json.dumps(fields)
    except Exception:
        pass
    return schema_str


DEFAULT_WEBSITE_SETTINGS: Dict[str, Any] = {
    # Store Hero
    "hero_label": "STOREFRONT",
    "hero_title": "Our Services",
    "hero_subtitle": "Choose from our range of professional services tailored to your business needs.",
    # Auth Pages
    "login_title": "Welcome back",
    "login_subtitle": "Sign in to your account to continue.",
    "login_portal_label": "Customer Portal",
    "login_btn_text": "Sign In",
    "register_title": "Create your account",
    "register_subtitle": "",
    # Signup form labels
    "signup_label": "Get Started",
    "signup_form_title": "Create your account",
    "signup_form_subtitle": "",
    "signup_btn_text": "Create Account",
    # Verify email page
    "verify_email_label": "Verify Email",
    "verify_email_title": "Enter your code",
    "verify_email_subtitle": "We sent a 6-digit verification code to your email address.",
    # Portal page
    "portal_label": "Customer Portal",
    "portal_title": "My Account",
    "portal_subtitle": "Track your orders, subscriptions, and manage your account.",
    # Profile page
    "profile_label": "My Profile",
    "profile_title": "Account Details",
    "profile_subtitle": "Update your contact details. Currency is locked after your first purchase.",
    # Contact — empty by default, each tenant fills these in
    "contact_email": "",
    "contact_phone": "",
    "contact_address": "",
    # Footer & Nav — empty by default
    "footer_tagline": "",
    "footer_copyright": "",
    "footer_about_title": "About Us",
    "footer_about_text": "",
    "footer_nav_title": "Navigation",
    "footer_contact_title": "Contact",
    "footer_social_title": "Follow Us",
    "nav_store_label": "Services",
    "nav_articles_label": "Resources",
    "nav_portal_label": "My Account",
    "social_twitter": "",
    "social_linkedin": "",
    "social_facebook": "",
    "social_instagram": "",
    "social_youtube": "",
    # Forms text
    "quote_form_title": "Request a Quote",
    "quote_form_subtitle": "Fill in your details and we'll get back to you with a custom quote.",
    "quote_form_response_time": "We'll respond within 1–2 business days.",
    "scope_form_title": "Request Scope",
    "scope_form_subtitle": "Tell us about your project and we'll get back to you with a detailed scope, timeline, and quote.",
    # Form schemas (JSON)
    "quote_form_schema": _QUOTE_FORM_SCHEMA,
    "scope_form_schema": _SCOPE_FORM_SCHEMA,
    "signup_form_schema": _SIGNUP_FORM_SCHEMA,
    # Email templates — empty by default
    "email_from_name": "",
    "email_article_subject_template": "Article: {{article_title}}",
    "email_article_cta_text": "View Article",
    "email_article_footer_text": "Your consultant has shared this document with you.",
    "email_verification_subject": "Verify your email address",
    "email_verification_body": "Your verification code is: {{code}}. This code expires in 24 hours.",
    # Error / UI messages
    "msg_partner_tagging_prompt": "Please confirm whether you have tagged us as your partner before continuing.",
    "msg_override_required": "An override code is required to proceed.",
    "msg_cart_empty": "Your cart is empty. Browse our services to get started.",
    "msg_terms_not_accepted": "Please read and accept the Terms & Conditions to proceed.",
    "msg_quote_success": "Thank you! Your quote request has been received. We'll be in touch within 1–2 business days.",
    "msg_scope_success": "Thank you! Your scope request has been received. We'll review it and get back to you shortly.",
    "msg_currency_unsupported": "Purchases are not supported in your region. Please contact us for assistance.",
    "msg_no_payment_methods": "No payment methods are currently available. Please contact support.",
    # Payment display labels
    "payment_gocardless_label": "Bank Transfer (Direct Debit)",
    "payment_gocardless_description": "No processing fee. We'll set up a direct debit from your account.",
    "payment_stripe_label": "Card Payment",
    "payment_stripe_description": "Pay securely by credit or debit card. A processing fee applies.",
    # Checkout page — legacy sections disabled by default
    "checkout_zoho_enabled": False,
    "checkout_zoho_title": "Account Details",
    "checkout_zoho_subscription_options": "",
    "checkout_zoho_product_options": "",
    "checkout_zoho_signup_note": "",
    "checkout_zoho_access_note": "",
    "checkout_zoho_access_delay_warning": "",
    # Checkout page — partner tagging disabled by default
    "checkout_partner_enabled": False,
    "checkout_partner_title": "Partner Confirmation",
    "checkout_partner_description": "",
    "checkout_partner_options": "Yes\nNot yet",
    "checkout_partner_misrep_warning": "",
    # Articles hero
    "articles_hero_label": "Resources",
    "articles_hero_title": "Articles & Guides",
    "articles_hero_subtitle": "Tips, guides, and updates from our team.",
    # Dynamic checkout sections — empty by default (no Zoho/partner examples)
    "checkout_extra_schema": "[]",
    "checkout_sections": "[]",
    # Checkout success page
    "checkout_success_title": "Payment Confirmed",
    "checkout_success_paid_msg": "Your payment was successful.",
    "checkout_success_pending_msg": "Checking payment status — please wait a moment.",
    "checkout_success_expired_msg": "Your session has expired. Please return to the store.",
    "checkout_success_next_steps_title": "What Happens Next",
    "checkout_success_step_1": "You'll receive a confirmation email with your order details.",
    "checkout_success_step_2": "A team member will be in touch within 1–2 business days.",
    "checkout_success_step_3": "Track your order and invoices in the customer portal.",
    "checkout_portal_link_text": "Go to Customer Portal",
    # Bank transfer success page
    "bank_success_title": "Order Created",
    "bank_success_message": "Your order has been created and is awaiting payment.",
    "bank_instructions_title": "Payment Instructions",
    "bank_instruction_1": "Transfer the exact amount shown on your order confirmation to our bank account.",
    "bank_instruction_2": "Include your order number as the payment reference.",
    "bank_instruction_3": "Your order will be activated within 1–2 business days of payment being received.",
    "bank_next_steps_title": "What Happens Next",
    "bank_next_step_1": "Check your email for full payment details and instructions.",
    "bank_next_step_2": "Complete the payment using your order number as reference.",
    "bank_next_step_3": "We'll confirm receipt and begin processing your order.",
    # 404 page
    "page_404_title": "Page Not Found",
    "page_404_subtitle": "The page you're looking for doesn't exist or has been moved.",
    "page_404_link_text": "Back to Services",
    # GoCardless callback page
    "gocardless_processing_title": "Setting Up Your Direct Debit",
    "gocardless_processing_subtitle": "Please wait while we confirm your bank authorisation.",
    "gocardless_success_title": "Direct Debit Set Up",
    "gocardless_success_message": "Your direct debit mandate has been set up successfully.",
    "gocardless_error_title": "Setup Failed",
    "gocardless_error_message": "We were unable to set up your direct debit. Please try again or contact support.",
    "gocardless_return_btn_text": "Return to Store",
    # Cart page
    "cart_title": "Your Cart",
    "cart_clear_btn_text": "Clear Cart",
    # Payment provider display text
    "payment_processing_msg": "Processing your payment, please wait…",
    "payment_terms_label": "I have read and agree to the",
    "payment_terms_link_text": "Terms & Conditions",
    # Documents page
    "nav_documents_label": "",
    "documents_page_title": "",
    "documents_page_subtitle": "",
    "documents_page_upload_label": "",
    "documents_page_upload_hint": "",
    "documents_page_empty_text": "",
    "signup_bullet_1": "",
    "signup_bullet_2": "",
    "signup_bullet_3": "",
    "signup_cta": "",
}


@router.get("/website-settings")
async def get_website_settings_public(
    partner_code: Optional[str] = None,
    x_view_as_tenant: Optional[str] = Header(default=None, alias="X-View-As-Tenant"),
    user: Optional[Dict[str, Any]] = Depends(optional_get_current_user),
):
    """Public endpoint — returns all website content + branding + payment flags."""
    from core.tenant import resolve_tenant, is_platform_admin
    # Priority: TenantSwitcher > partner_code > user JWT > default
    if x_view_as_tenant and user and is_platform_admin(user):
        tid = x_view_as_tenant
    elif partner_code:
        try:
            tenant = await resolve_tenant(partner_code)
            tid = tenant["id"]
        except Exception:
            tid = DEFAULT_TENANT_ID
    elif user and user.get("tenant_id"):
        tid = user["tenant_id"]
    else:
        tid = DEFAULT_TENANT_ID

    app_s = await db.app_settings.find_one({"tenant_id": tid, "key": {"$exists": False}}, {"_id": 0}) or {}
    web_s = await db.website_settings.find_one({"tenant_id": tid}, {"_id": 0}) or {}

    # Load payment provider flags from oauth_connections (Connected Services)
    stripe_conn = await db.oauth_connections.find_one({"tenant_id": tid, "provider": "stripe", "is_validated": True}, {"_id": 0})
    gocardless_conn = await db.oauth_connections.find_one(
        {"tenant_id": tid, "provider": {"$in": ["gocardless", "gocardless_sandbox"]}, "is_validated": True}, 
        {"_id": 0}
    )
    workdrive_conn = await db.oauth_connections.find_one(
        {"tenant_id": tid, "provider": "zoho_workdrive", "is_validated": True}, {"_id": 0}
    )
    stripe_enabled = bool(stripe_conn)
    gocardless_enabled = bool(gocardless_conn)
    workdrive_enabled = bool(workdrive_conn)
    
    # Fee rates and UI settings from oauth_connections settings field
    stripe_settings = stripe_conn.get("settings", {}) if stripe_conn else {}
    gocardless_settings = gocardless_conn.get("settings", {}) if gocardless_conn else {}
    
    stripe_fee_rate = float(stripe_settings.get("fee_rate", 0.05))
    gocardless_fee_rate = float(gocardless_settings.get("fee_rate", 0.0))

    settings = {
        **DEFAULT_WEBSITE_SETTINGS,
        # Branding (from app_settings)
        "store_name": app_s.get("store_name", ""),
        "logo_url": app_s.get("logo_url") or "",
        "primary_color": app_s.get("primary_color") or "",
        "accent_color": app_s.get("accent_color") or "",
        "danger_color": app_s.get("danger_color") or "",
        "success_color": app_s.get("success_color") or "",
        "warning_color": app_s.get("warning_color") or "",
        "background_color": app_s.get("background_color") or "",
        "text_color": app_s.get("text_color") or "",
        "border_color": app_s.get("border_color") or "",
        "muted_color": app_s.get("muted_color") or "",
        # Content overrides (from website_settings)
        **{k: v for k, v in web_s.items() if v is not None and k not in ("_id", "tenant_id")},
        # Payment flags (from oauth_connections)
        "stripe_enabled": bool(stripe_enabled),
        "gocardless_enabled": bool(gocardless_enabled),
        "workdrive_enabled": bool(workdrive_enabled),
        "stripe_fee_rate": float(stripe_fee_rate),
        "gocardless_fee_rate": float(gocardless_fee_rate),
        # Stripe UI settings
        "payment_stripe_label": stripe_settings.get("label", DEFAULT_WEBSITE_SETTINGS.get("payment_stripe_label", "Card Payment")),
        "payment_stripe_description": stripe_settings.get("description", DEFAULT_WEBSITE_SETTINGS.get("payment_stripe_description", "Pay securely by credit or debit card.")),
        # GoCardless UI settings
        "payment_gocardless_label": gocardless_settings.get("label", DEFAULT_WEBSITE_SETTINGS.get("payment_gocardless_label", "Bank Transfer (Direct Debit)")),
        "payment_gocardless_description": gocardless_settings.get("description", DEFAULT_WEBSITE_SETTINGS.get("payment_gocardless_description", "No processing fee. We'll set up a direct debit.")),
        "gocardless_processing_title": gocardless_settings.get("processing_title", DEFAULT_WEBSITE_SETTINGS.get("gocardless_processing_title", "Setting Up Your Direct Debit")),
        "gocardless_processing_subtitle": gocardless_settings.get("processing_subtitle", DEFAULT_WEBSITE_SETTINGS.get("gocardless_processing_subtitle", "Please wait while we confirm your bank authorisation.")),
        "gocardless_success_title": gocardless_settings.get("success_title", DEFAULT_WEBSITE_SETTINGS.get("gocardless_success_title", "Direct Debit Set Up")),
        "gocardless_success_message": gocardless_settings.get("success_message", DEFAULT_WEBSITE_SETTINGS.get("gocardless_success_message", "Your direct debit mandate has been set up successfully.")),
        "gocardless_error_title": gocardless_settings.get("error_title", DEFAULT_WEBSITE_SETTINGS.get("gocardless_error_title", "Setup Failed")),
        "gocardless_error_message": gocardless_settings.get("error_message", DEFAULT_WEBSITE_SETTINGS.get("gocardless_error_message", "We were unable to set up your direct debit. Please try again.")),
        "gocardless_return_btn_text": gocardless_settings.get("return_btn_text", DEFAULT_WEBSITE_SETTINGS.get("gocardless_return_btn_text", "Return to Store")),
    }
    # Migrate: inject default checkout_sections when DB has empty value
    try:
        cs = settings.get("checkout_sections", "[]")
        if not cs or json.loads(cs) == []:
            settings["checkout_sections"] = DEFAULT_WEBSITE_SETTINGS["checkout_sections"]
    except Exception:
        pass
    # Migrate: fix old signup schema format (standalone country → address block)
    try:
        settings["signup_form_schema"] = _migrate_signup_schema(settings.get("signup_form_schema", "[]"))
    except Exception:
        pass
    return {"settings": settings}


@router.get("/admin/website-settings")
async def get_website_settings_admin(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tid = tenant_id_of(admin)
    web_s = await db.website_settings.find_one({"tenant_id": tid}, {"_id": 0}) or {}
    app_s = await db.app_settings.find_one({"tenant_id": tid, "key": {"$exists": False}}, {"_id": 0}) or {}
    # Merge: defaults → app_settings (branding/colors) → website_settings (content overrides)
    merged = {
        **DEFAULT_WEBSITE_SETTINGS,
        "store_name": app_s.get("store_name", ""),
        "logo_url": app_s.get("logo_url") or "",
        "primary_color": app_s.get("primary_color") or "",
        "accent_color": app_s.get("accent_color") or "",
        "danger_color": app_s.get("danger_color") or "",
        "success_color": app_s.get("success_color") or "",
        "warning_color": app_s.get("warning_color") or "",
        "background_color": app_s.get("background_color") or "",
        "text_color": app_s.get("text_color") or "",
        "border_color": app_s.get("border_color") or "",
        "muted_color": app_s.get("muted_color") or "",
        **{k: v for k, v in web_s.items() if v is not None and k not in ("_id", "tenant_id")},
    }
    # Migrate: inject default checkout_sections when DB has empty value
    try:
        cs = merged.get("checkout_sections", "[]")
        if not cs or json.loads(cs) == []:
            merged["checkout_sections"] = DEFAULT_WEBSITE_SETTINGS["checkout_sections"]
    except Exception:
        pass
    # Migrate: fix old signup schema format (standalone country → address block)
    try:
        merged["signup_form_schema"] = _migrate_signup_schema(merged.get("signup_form_schema", "[]"))
    except Exception:
        pass
    return {"settings": merged}


@router.put("/admin/website-settings")
async def update_website_settings(
    payload: WebsiteSettingsUpdate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tid = tenant_id_of(admin)
    update = {k: v for k, v in payload.dict().items() if v is not None}
    if not update:
        return {"message": "Nothing to update"}
    await db.website_settings.update_one({"tenant_id": tid}, {"$set": {**update, "tenant_id": tid}}, upsert=True)
    await create_audit_log(
        entity_type="website_settings",
        entity_id="website",
        action="updated",
        actor=admin.get("email", "admin"),
        details={"keys_changed": list(update.keys())},
    )
    return {"message": "Website settings updated"}
