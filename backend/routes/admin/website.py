"""Admin: Website content settings routes."""
from __future__ import annotations

import json
from typing import Any, Dict

from fastapi import APIRouter, Depends

from core.security import require_admin
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
    "hero_title": "Welcome",
    "hero_subtitle": "",
    # Auth Pages
    "login_title": "Welcome back",
    "login_subtitle": "Sign in to continue.",
    "login_portal_label": "Customer Portal",
    "register_title": "Create your account",
    "register_subtitle": "",
    # Contact
    "contact_email": "",
    "contact_phone": "",
    "contact_address": "",
    # Footer & Nav
    "footer_tagline": "",
    "footer_copyright": "",
    "nav_store_label": "Store",
    "nav_articles_label": "Articles",
    "nav_portal_label": "Portal",
    # Forms text
    "quote_form_title": "Request a Quote",
    "quote_form_subtitle": "Fill in your details and we'll get back to you with a custom quote.",
    "quote_form_response_time": "We'll respond within 1-2 business days.",
    "scope_form_title": "Request Scope",
    "scope_form_subtitle": "Tell us about your project and we'll get back to you with a detailed scope, timeline, and quote.",
    "signup_form_title": "Create your account",
    "signup_form_subtitle": "",
    # Form schemas (JSON)
    "quote_form_schema": _QUOTE_FORM_SCHEMA,
    "scope_form_schema": _SCOPE_FORM_SCHEMA,
    "signup_form_schema": _SIGNUP_FORM_SCHEMA,
    # Email templates
    "email_from_name": "",
    "email_article_subject_template": "Article: {{article_title}}",
    "email_article_cta_text": "View Article",
    "email_article_footer_text": "Your consultant has shared this document with you.",
    "email_verification_subject": "Verify your account",
    "email_verification_body": "Your verification code is {{code}}",
    # Error / UI messages
    "msg_partner_tagging_prompt": "Please select whether you have tagged us as your partner.",
    "msg_override_required": "An override code is required when you have not yet tagged us as your partner.",
    "msg_cart_empty": "Your cart is empty.",
    "msg_quote_success": "Quote request submitted! We'll be in touch shortly.",
    "msg_scope_success": "Scope request submitted!",
    # Payment display labels
    "payment_gocardless_label": "Bank Transfer (GoCardless)",
    "payment_gocardless_description": "No processing fee. We'll send bank transfer instructions.",
    "payment_stripe_label": "Card Payment (Stripe)",
    "payment_stripe_description": "5% processing fee applies. Pay securely with credit/debit card.",
    # Checkout page — Zoho section
    "checkout_zoho_enabled": True,
    "checkout_zoho_title": "Zoho Account Details",
    "checkout_zoho_subscription_options": "Paid - Annual\nPaid - Monthly\nFree / Not on Zoho",
    "checkout_zoho_product_options": "Zoho One (Free)\nZoho One (All employee pricing)\nZoho One (Flexible user pricing)\nZoho Books (Free)\nZoho One (Essentials)\nZoho Books (Standard)\nZoho Books (Professional)\nZoho Books (Premium)\nZoho Books (Elite)\nZoho Books (Ultimate)\nZoho Books (Enterprise)\nNot on Zoho",
    "checkout_zoho_signup_note": "for a free 1 hour Welcome to Zoho and a 30-day trial",
    "checkout_zoho_access_note": "to understand how to provide us access to your Zoho account",
    "checkout_zoho_access_delay_warning": "Please note service delays can happen if you complete purchase without providing us the access.",
    # Checkout page — Partner tagging section
    "checkout_partner_enabled": True,
    "checkout_partner_title": "Have you tagged us as your Zoho Partner?",
    "checkout_partner_description": "You can tag us as your Zoho Partner by clicking the links below. If the US DC link doesn't work, try the CA DC link. You must be logged in to your Zoho account before tagging us.",
    "checkout_partner_options": "Yes\nPre-existing Customer\nNot yet",
    "checkout_partner_misrep_warning": "Misrepresenting or false responses may lead to cancellation of service.",
    # Articles hero
    "articles_hero_label": "Resources",
    "articles_hero_title": "Articles & Guides",
    "articles_hero_subtitle": "",
    # Checkout page
    "checkout_extra_schema": "[]",
    # Dynamic checkout sections (new builder)
    "checkout_sections": "[]",
    # Checkout success page
    "checkout_success_title": "Checkout status",
    "checkout_success_paid_msg": "Payment successful.",
    "checkout_success_pending_msg": "Checking payment status...",
    "checkout_success_expired_msg": "Session expired.",
    "checkout_success_next_steps_title": "Next steps",
    "checkout_success_step_1": "We'll send a confirmation email with intake instructions.",
    "checkout_success_step_2": "A delivery lead will schedule your kickoff within 2 business days.",
    "checkout_success_step_3": "You can track status and invoices in the customer portal.",
    "checkout_portal_link_text": "Go to customer portal",
    # Bank transfer success page
    "bank_success_title": "Order Created",
    "bank_success_message": "Your order has been created and is awaiting bank transfer payment.",
    "bank_instructions_title": "Payment Instructions",
    "bank_instruction_1": "You will receive an email with bank transfer details and instructions.",
    "bank_instruction_2": "Please complete the transfer within 7 business days.",
    "bank_instruction_3": "Once payment is confirmed, your order will be processed and a team member will reach out.",
    "bank_next_steps_title": "What Happens Next",
    "bank_next_step_1": "1. Check your email for transfer instructions",
    "bank_next_step_2": "2. Complete the bank transfer",
    "bank_next_step_3": "3. We'll confirm receipt and begin processing your order",
    # 404 page
    "page_404_title": "Page not found",
    "page_404_link_text": "Back to store",
    # GoCardless callback page
    "gocardless_processing_title": "Processing Direct Debit Setup",
    "gocardless_processing_subtitle": "Please wait while we confirm your mandate...",
    "gocardless_success_title": "Payment Initiated!",
    "gocardless_success_message": "Your Direct Debit mandate has been set up and payment has been initiated. It will be processed shortly.",
    "gocardless_error_title": "Setup Failed",
    "gocardless_error_message": "There was an error completing your Direct Debit setup.",
    "gocardless_return_btn_text": "Return to Store",
    # Verify email page
    "verify_email_label": "Verify email",
    "verify_email_title": "Enter your code",
    "verify_email_subtitle": "We sent a 6-digit code to your email.",
    # Portal page
    "portal_title": "Customer portal",
    "portal_subtitle": "Track your orders and subscriptions in one place.",
    # Profile page
    "profile_label": "My Profile",
    "profile_title": "Account details",
    "profile_subtitle": "Update your contact details. Currency remains locked after your first purchase.",
    # Cart page
    "cart_title": "Your cart",
    "cart_clear_btn_text": "Clear cart",
    "msg_currency_unsupported": "Purchases are not supported in your region yet. Please contact admin for an override.",
    "msg_no_payment_methods": "No payment methods available. Please contact support.",
}


@router.get("/website-settings")
async def get_website_settings_public():
    """Public endpoint — returns all website content + branding + payment flags."""
    app_s = await db.app_settings.find_one({}, {"_id": 0}) or {}
    web_s = await db.website_settings.find_one({}, {"_id": 0}) or {}

    # Load payment provider flags from structured settings (app_settings)
    stripe_enabled = await SettingsService.get("stripe_enabled", False)
    gocardless_enabled = await SettingsService.get("gocardless_enabled", False)
    stripe_fee_rate = await SettingsService.get("stripe_fee_rate", 0.05)
    gocardless_fee_rate = await SettingsService.get("gocardless_fee_rate", 0.0)

    return {
        "settings": {
            **DEFAULT_WEBSITE_SETTINGS,
            # Branding (from app_settings)
            "store_name": app_s.get("store_name", ""),
            "logo_url": app_s.get("logo_url") or "",
            "primary_color": app_s.get("primary_color") or "",
            "accent_color": app_s.get("accent_color") or "",
            # Content overrides (from website_settings)
            **{k: v for k, v in web_s.items() if v is not None and k != "_id"},
            # Payment flags (always from SettingsService)
            "stripe_enabled": bool(stripe_enabled),
            "gocardless_enabled": bool(gocardless_enabled),
            "stripe_fee_rate": float(stripe_fee_rate) if stripe_fee_rate else 0.05,
            "gocardless_fee_rate": float(gocardless_fee_rate) if gocardless_fee_rate else 0.0,
        }
    }


@router.get("/admin/website-settings")
async def get_website_settings_admin(admin: Dict[str, Any] = Depends(require_admin)):
    web_s = await db.website_settings.find_one({}, {"_id": 0}) or {}
    return {"settings": {**DEFAULT_WEBSITE_SETTINGS, **web_s}}


@router.put("/admin/website-settings")
async def update_website_settings(
    payload: WebsiteSettingsUpdate,
    admin: Dict[str, Any] = Depends(require_admin),
):
    update = {k: v for k, v in payload.dict().items() if v is not None}
    if not update:
        return {"message": "Nothing to update"}
    await db.website_settings.update_one({}, {"$set": update}, upsert=True)
    await create_audit_log(
        entity_type="website_settings",
        entity_id="website",
        action="updated",
        actor=admin.get("email", "admin"),
        details={"keys_changed": list(update.keys())},
    )
    return {"message": "Website settings updated"}
