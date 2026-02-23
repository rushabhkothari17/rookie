"""Admin: Website content settings routes."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends

from core.security import require_admin
from core.tenant import get_tenant_filter, tenant_id_of, DEFAULT_TENANT_ID
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

_SIGNUP_FORM_SCHEMA = json.dumps([
    {"id": "su_name", "key": "full_name", "label": "Full Name", "type": "text", "required": True, "placeholder": "Your full name", "locked": True, "enabled": True, "order": 0},
    {"id": "su_email", "key": "email", "label": "Email", "type": "email", "required": True, "placeholder": "your@email.com", "locked": True, "enabled": True, "order": 1},
    {"id": "su_password", "key": "password", "label": "Password", "type": "password", "required": True, "placeholder": "", "locked": True, "enabled": True, "order": 2},
    {"id": "su_company", "key": "company_name", "label": "Company Name", "type": "text", "required": True, "placeholder": "Your company", "locked": False, "enabled": True, "order": 3},
    {"id": "su_job", "key": "job_title", "label": "Job Title", "type": "text", "required": False, "placeholder": "Your role", "locked": False, "enabled": True, "order": 4},
    {"id": "su_phone", "key": "phone", "label": "Phone", "type": "tel", "required": False, "placeholder": "+1 (555) 000-0000", "locked": False, "enabled": True, "order": 5},
    {"id": "su_country", "key": "country", "label": "Country", "type": "select", "required": True, "options": ["Canada|Canada", "United States|USA", "Other|Other"], "locked": True, "enabled": True, "order": 6},
])

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
    "register_subtitle": "Join us to access all services and manage your account in one place.",
    # Signup form labels
    "signup_label": "Get Started",
    "signup_form_title": "Create your account",
    "signup_form_subtitle": "Fill in your details below to get started.",
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
    # Contact
    "contact_email": "hello@yourbusiness.com",
    "contact_phone": "+1 (555) 000-0000",
    "contact_address": "",
    # Footer & Nav
    "footer_tagline": "Professional services tailored to your business.",
    "footer_copyright": "© 2025 Your Business Name. All rights reserved.",
    "footer_about_title": "About Us",
    "footer_about_text": "We are a dedicated team of professionals helping businesses grow and succeed. Contact us to find out how we can help.",
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
    # Email templates
    "email_from_name": "Your Business Name",
    "email_article_subject_template": "Article: {{article_title}}",
    "email_article_cta_text": "View Article",
    "email_article_footer_text": "Your consultant has shared this document with you.",
    "email_verification_subject": "Verify your email address",
    "email_verification_body": "Your verification code is: {{code}}. This code expires in 24 hours.",
    # Error / UI messages
    "msg_partner_tagging_prompt": "Please confirm whether you have tagged us as your partner before continuing.",
    "msg_override_required": "An override code is required when you have not yet tagged us as your partner.",
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
    # Checkout page — legacy Zoho section (still used as fallback)
    "checkout_zoho_enabled": True,
    "checkout_zoho_title": "Zoho Account Details",
    "checkout_zoho_subscription_options": "Paid - Annual\nPaid - Monthly\nFree / Not on Zoho",
    "checkout_zoho_product_options": "Zoho One\nZoho CRM\nZoho Books\nZoho People\nNot on Zoho",
    "checkout_zoho_signup_note": "for a free trial and onboarding session",
    "checkout_zoho_access_note": "to understand how to provide us access to your Zoho account",
    "checkout_zoho_access_delay_warning": "Service delays may occur if access is not granted before purchase.",
    # Checkout page — legacy partner tagging section (still used as fallback)
    "checkout_partner_enabled": True,
    "checkout_partner_title": "Have you tagged us as your Partner?",
    "checkout_partner_description": "Tag us as your partner by clicking the links below. You must be logged in to your account before tagging.",
    "checkout_partner_options": "Yes\nPre-existing Customer\nNot yet",
    "checkout_partner_misrep_warning": "False responses may result in cancellation of service.",
    # Articles hero
    "articles_hero_label": "Resources",
    "articles_hero_title": "Articles & Guides",
    "articles_hero_subtitle": "Tips, guides, and updates from our team of experts.",
    # Checkout extra schema (legacy)
    "checkout_extra_schema": "[]",
    # Dynamic checkout sections (new builder — replaces legacy Zoho/Partner sections)
    "checkout_sections": json.dumps([
        {
            "id": "cs_zoho_account",
            "title": "Zoho Account Details",
            "description": "Please provide your Zoho account information so we can set up your services.",
            "enabled": True,
            "order": 0,
            "fields_schema": json.dumps([
                {"id": "zoho_subscription_type", "label": "Current Zoho subscription type?", "type": "select", "required": True, "options": "Paid - Annual\nPaid - Monthly\nFree / Not on Zoho", "placeholder": "-- Select --", "enabled": True},
                {"id": "current_zoho_product", "label": "Which Zoho product are you primarily using?", "type": "text", "required": False, "options": "", "placeholder": "e.g. Zoho CRM, Zoho Books", "enabled": True},
                {"id": "zoho_account_access", "label": "Have you granted us access to your Zoho account?", "type": "select", "required": True, "options": "Yes, I have granted access\nNo \u2014 I will do this shortly\nNo \u2014 I need help with this", "placeholder": "-- Select --", "enabled": True},
            ]),
        },
        {
            "id": "cs_partner_tagging",
            "title": "Have you tagged us as your Partner?",
            "description": "Tag us as your partner by clicking the links below.",
            "enabled": True,
            "order": 1,
            "fields_schema": json.dumps([
                {"id": "partner_tag_response", "label": "Have you tagged us as your partner?", "type": "select", "required": True, "options": "Yes\nPre-existing Customer\nNot yet", "placeholder": "-- Select --", "enabled": True},
            ]),
        },
    ]),
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
    # Bank transfer success page (offline payment confirmation)
    "bank_success_title": "Order Created",
    "bank_success_message": "Your order has been created and is awaiting bank transfer payment. You will receive an email with payment instructions shortly.",
    "bank_instructions_title": "Payment Instructions",
    "bank_instruction_1": "Transfer the exact amount shown on your order confirmation to our bank account.",
    "bank_instruction_2": "Include your order number as the payment reference.",
    "bank_instruction_3": "Your order will be activated within 1–2 business days of payment being received.",
    "bank_next_steps_title": "What Happens Next",
    "bank_next_step_1": "Check your email for full bank transfer details and instructions.",
    "bank_next_step_2": "Complete the bank transfer using your order number as reference.",
    "bank_next_step_3": "We'll confirm receipt and begin processing your order.",
    # 404 page
    "page_404_title": "Page Not Found",
    "page_404_subtitle": "The page you're looking for doesn't exist or has been moved.",
    "page_404_link_text": "Back to Services",
    # GoCardless callback page
    "gocardless_processing_title": "Setting Up Your Direct Debit",
    "gocardless_processing_subtitle": "Please wait while we confirm your bank authorisation.",
    "gocardless_success_title": "Direct Debit Set Up",
    "gocardless_success_message": "Your direct debit mandate has been set up successfully. You will be redirected shortly.",
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
}


@router.get("/website-settings")
async def get_website_settings_public(partner_code: Optional[str] = None):
    """Public endpoint — returns all website content + branding + payment flags."""
    from fastapi import Request
    from core.tenant import resolve_tenant
    if partner_code:
        try:
            tenant = await resolve_tenant(partner_code)
            tid = tenant["id"]
        except Exception:
            tid = DEFAULT_TENANT_ID
    else:
        tid = DEFAULT_TENANT_ID

    app_s = await db.app_settings.find_one({"tenant_id": tid, "key": {"$exists": False}}, {"_id": 0}) or {}
    web_s = await db.website_settings.find_one({"tenant_id": tid}, {"_id": 0}) or {}

    # Load payment provider flags from structured settings (app_settings)
    stripe_enabled = await SettingsService.get("stripe_enabled", False)
    gocardless_enabled = await SettingsService.get("gocardless_enabled", False)
    stripe_fee_rate = await SettingsService.get("stripe_fee_rate", 0.05)
    gocardless_fee_rate = await SettingsService.get("gocardless_fee_rate", 0.0)

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
        # Payment flags (always from SettingsService)
        "stripe_enabled": bool(stripe_enabled),
        "gocardless_enabled": bool(gocardless_enabled),
        "stripe_fee_rate": float(stripe_fee_rate) if stripe_fee_rate else 0.05,
        "gocardless_fee_rate": float(gocardless_fee_rate) if gocardless_fee_rate else 0.0,
    }
    # Migrate: inject default checkout_sections when DB has empty value
    try:
        cs = settings.get("checkout_sections", "[]")
        if not cs or json.loads(cs) == []:
            settings["checkout_sections"] = DEFAULT_WEBSITE_SETTINGS["checkout_sections"]
    except Exception:
        pass
    return {"settings": settings}


@router.get("/admin/website-settings")
async def get_website_settings_admin(admin: Dict[str, Any] = Depends(require_admin)):
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
    return {"settings": merged}


@router.put("/admin/website-settings")
async def update_website_settings(
    payload: WebsiteSettingsUpdate,
    admin: Dict[str, Any] = Depends(require_admin),
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
