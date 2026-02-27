import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import api from "@/lib/api";

export interface WebsiteSettings {
  // Branding
  store_name: string;
  logo_url: string;
  primary_color: string;
  accent_color: string;
  danger_color: string;
  success_color: string;
  warning_color: string;
  background_color: string;
  text_color: string;
  border_color: string;
  muted_color: string;
  // Store hero
  hero_label: string;
  hero_title: string;
  hero_subtitle: string;
  // Auth pages
  login_title: string;
  login_subtitle: string;
  login_portal_label: string;
  register_title: string;
  register_subtitle: string;
  // Contact
  contact_email: string;
  contact_phone: string;
  contact_address: string;
  // Footer & Nav
  footer_tagline: string;
  footer_copyright: string;
  nav_store_label: string;
  nav_articles_label: string;
  nav_portal_label: string;
  // Forms text
  quote_form_title: string;
  quote_form_subtitle: string;
  quote_form_response_time: string;
  scope_form_title: string;
  scope_form_subtitle: string;
  signup_form_title: string;
  signup_form_subtitle: string;
  // Form schemas (JSON strings)
  quote_form_schema: string;
  scope_form_schema: string;
  signup_form_schema: string;
  // Email templates
  email_from_name: string;
  email_article_subject_template: string;
  email_article_cta_text: string;
  email_article_footer_text: string;
  email_verification_subject: string;
  email_verification_body: string;
  // Error / UI messages
  msg_partner_tagging_prompt: string;
  msg_override_required: string;
  msg_cart_empty: string;
  msg_quote_success: string;
  msg_scope_success: string;
  // Payment flags (from settings_service)
  stripe_enabled: boolean;
  gocardless_enabled: boolean;
  workdrive_enabled: boolean;
  stripe_fee_rate: number;
  gocardless_fee_rate: number;
  // Payment display labels (configurable per white-label)
  payment_gocardless_label: string;
  payment_gocardless_description: string;
  payment_stripe_label: string;
  payment_stripe_description: string;
  // Articles hero
  articles_hero_label: string;
  articles_hero_title: string;
  articles_hero_subtitle: string;
  // Checkout page configuration (legacy)
  checkout_zoho_enabled: boolean;
  checkout_zoho_title: string;
  checkout_zoho_description: string;
  checkout_zoho_subscription_options: string;
  checkout_zoho_subscription_type_label: string;
  checkout_zoho_product_options: string;
  checkout_zoho_product_label: string;
  checkout_zoho_access_options: string;
  checkout_zoho_access_label: string;
  checkout_zoho_signup_note: string;
  checkout_zoho_access_note: string;
  checkout_zoho_access_delay_warning: string;
  checkout_partner_enabled: boolean;
  checkout_partner_title: string;
  checkout_partner_description: string;
  checkout_partner_question: string;
  checkout_partner_options: string;
  checkout_partner_misrep_warning: string;
  checkout_extra_schema: string;
  checkout_terms_enabled: boolean;
  // Dynamic checkout sections (new builder)
  checkout_sections: string;
  // Checkout success page
  checkout_success_title: string;
  checkout_success_paid_msg: string;
  checkout_success_pending_msg: string;
  checkout_success_expired_msg: string;
  checkout_success_next_steps_title: string;
  checkout_success_step_1: string;
  checkout_success_step_2: string;
  checkout_success_step_3: string;
  checkout_portal_link_text: string;
  // Bank transfer success page
  bank_success_title: string;
  bank_success_message: string;
  bank_instructions_title: string;
  bank_instruction_1: string;
  bank_instruction_2: string;
  bank_instruction_3: string;
  bank_next_steps_title: string;
  bank_next_step_1: string;
  bank_next_step_2: string;
  bank_next_step_3: string;
  // 404 page
  page_404_title: string;
  page_404_link_text: string;
  // GoCardless callback page
  gocardless_processing_title: string;
  gocardless_processing_subtitle: string;
  gocardless_success_title: string;
  gocardless_success_message: string;
  gocardless_error_title: string;
  gocardless_error_message: string;
  gocardless_return_btn_text: string;
  // Verify email page
  verify_email_label: string;
  verify_email_title: string;
  verify_email_subtitle: string;
  // Portal page
  portal_title: string;
  portal_subtitle: string;
  // Profile page
  profile_label: string;
  profile_title: string;
  profile_subtitle: string;
  // Cart page
  cart_title: string;
  cart_clear_btn_text: string;
  msg_currency_unsupported: string;
  msg_no_payment_methods: string;
  // Footer extras
  footer_about_title: string;
  footer_about_text: string;
  footer_nav_title: string;
  footer_contact_title: string;
  footer_social_title: string;
  social_twitter: string;
  social_linkedin: string;
  social_facebook: string;
  social_instagram: string;
  social_youtube: string;
  // Admin panel
  admin_page_badge: string;
  admin_page_title: string;
  admin_page_subtitle: string;
  // Bank transaction form
  bank_transaction_sources: string;
  bank_transaction_types: string;
  bank_transaction_statuses: string;
  // Documents page
  nav_documents_label: string;
  documents_page_title: string;
  documents_page_subtitle: string;
  documents_page_upload_label: string;
  documents_page_upload_hint: string;
  documents_page_empty_text: string;
  // Signup page bullets
  signup_bullet_1: string;
  signup_bullet_2: string;
  signup_bullet_3: string;
  signup_cta: string;
}

const DEFAULT_SETTINGS: WebsiteSettings = {
  store_name: "",
  logo_url: "",
  primary_color: "",
  accent_color: "",
  danger_color: "",
  success_color: "",
  warning_color: "",
  background_color: "",
  text_color: "",
  border_color: "",
  muted_color: "",
  hero_label: "STOREFRONT",
  hero_title: "Welcome",
  hero_subtitle: "",
  login_title: "Welcome back",
  login_subtitle: "Sign in to continue.",
  login_portal_label: "Customer Portal",
  register_title: "Create your account",
  register_subtitle: "",
  contact_email: "",
  contact_phone: "",
  contact_address: "",
  footer_tagline: "",
  footer_copyright: "",
  nav_store_label: "Store",
  nav_articles_label: "Articles",
  nav_portal_label: "Portal",
  quote_form_title: "Request a Quote",
  quote_form_subtitle: "Fill in your details and we'll get back to you with a custom quote.",
  quote_form_response_time: "We'll respond within 1-2 business days.",
  scope_form_title: "Request Scope",
  scope_form_subtitle: "Tell us about your project and we'll get back to you with a detailed scope, timeline, and quote.",
  signup_form_title: "Create your account",
  signup_form_subtitle: "",
  quote_form_schema: "",
  scope_form_schema: "",
  signup_form_schema: "",
  email_from_name: "",
  email_article_subject_template: "Article: {{article_title}}",
  email_article_cta_text: "View Article",
  email_article_footer_text: "Your consultant has shared this document with you.",
  email_verification_subject: "Verify your account",
  email_verification_body: "Your verification code is {{code}}",
  msg_partner_tagging_prompt: "Please select whether you have tagged us as your partner.",
  msg_override_required: "An override code is required when you have not yet tagged us as your partner.",
  msg_cart_empty: "Your cart is empty.",
  msg_quote_success: "Quote request submitted! We'll be in touch shortly.",
  msg_scope_success: "Scope request submitted!",
  stripe_enabled: false,
  gocardless_enabled: false,
  workdrive_enabled: false,
  stripe_fee_rate: 0.05,
  gocardless_fee_rate: 0.0,
  payment_gocardless_label: "Bank Transfer (GoCardless)",
  payment_gocardless_description: "No processing fee. We'll send bank transfer instructions.",
  payment_stripe_label: "Card Payment (Stripe)",
  payment_stripe_description: "5% processing fee applies. Pay securely with credit/debit card.",
  articles_hero_label: "Resources",
  articles_hero_title: "Articles & Guides",
  articles_hero_subtitle: "",
  checkout_zoho_enabled: true,
  checkout_zoho_title: "Zoho Account Details",
  checkout_zoho_description: "",
  checkout_zoho_subscription_options: "Paid - Annual\nPaid - Monthly\nFree / Not on Zoho",
  checkout_zoho_subscription_type_label: "Current Zoho subscription type?",
  checkout_zoho_product_options: "",
  checkout_zoho_product_label: "Which Zoho products?",
  checkout_zoho_access_options: "New Customer\nPre-existing Customer",
  checkout_zoho_access_label: "Zoho account access?",
  checkout_zoho_signup_note: "for a free 1 hour Welcome to Zoho and a 30-day trial",
  checkout_zoho_access_note: "to understand how to provide us access to your Zoho account",
  checkout_zoho_access_delay_warning: "Please note service delays can happen if you complete purchase without providing us the access.",
  checkout_partner_enabled: true,
  checkout_partner_title: "Have you tagged us as your Zoho Partner?",
  checkout_partner_description: "You can tag us as your Zoho Partner by clicking the links below.",
  checkout_partner_question: "Have you tagged us as your Partner?",
  checkout_partner_options: "Yes\nPre-existing Customer\nNot yet",
  checkout_partner_misrep_warning: "Misrepresenting or false responses may lead to cancellation of service.",
  checkout_extra_schema: "[]",
  checkout_terms_enabled: true,
  checkout_sections: "[]",
  // Checkout success page
  checkout_success_title: "Checkout status",
  checkout_success_paid_msg: "Payment successful.",
  checkout_success_pending_msg: "Checking payment status...",
  checkout_success_expired_msg: "Session expired.",
  checkout_success_next_steps_title: "Next steps",
  checkout_success_step_1: "We'll send a confirmation email with intake instructions.",
  checkout_success_step_2: "A delivery lead will schedule your kickoff within 2 business days.",
  checkout_success_step_3: "You can track status and invoices in the customer portal.",
  checkout_portal_link_text: "Go to customer portal",
  // Bank transfer success page
  bank_success_title: "Order Created",
  bank_success_message: "Your order has been created and is awaiting bank transfer payment.",
  bank_instructions_title: "Payment Instructions",
  bank_instruction_1: "You will receive an email with bank transfer details and instructions.",
  bank_instruction_2: "Please complete the transfer within 7 business days.",
  bank_instruction_3: "Once payment is confirmed, your order will be processed and a team member will reach out.",
  bank_next_steps_title: "What Happens Next",
  bank_next_step_1: "1. Check your email for transfer instructions",
  bank_next_step_2: "2. Complete the bank transfer",
  bank_next_step_3: "3. We'll confirm receipt and begin processing your order",
  // 404 page
  page_404_title: "Page not found",
  page_404_link_text: "Back to store",
  // GoCardless callback page
  gocardless_processing_title: "Processing Direct Debit Setup",
  gocardless_processing_subtitle: "Please wait while we confirm your mandate...",
  gocardless_success_title: "Payment Initiated!",
  gocardless_success_message: "Your Direct Debit mandate has been set up and payment has been initiated. It will be processed shortly.",
  gocardless_error_title: "Setup Failed",
  gocardless_error_message: "There was an error completing your Direct Debit setup.",
  gocardless_return_btn_text: "Return to Store",
  // Verify email page
  verify_email_label: "Verify email",
  verify_email_title: "Enter your code",
  verify_email_subtitle: "We sent a 6-digit code to your email.",
  // Portal page
  portal_title: "Customer portal",
  portal_subtitle: "Track your orders and subscriptions in one place.",
  // Profile page
  profile_label: "My Profile",
  profile_title: "Account details",
  profile_subtitle: "Update your contact details. Currency remains locked after your first purchase.",
  // Cart page
  cart_title: "Your cart",
  cart_clear_btn_text: "Clear cart",
  msg_currency_unsupported: "Purchases are not supported in your region yet. Please contact admin for an override.",
  msg_no_payment_methods: "No payment methods available. Please contact support.",
  footer_about_title: "About Us",
  footer_about_text: "",
  footer_nav_title: "Navigation",
  footer_contact_title: "Contact",
  footer_social_title: "Follow Us",
  social_twitter: "",
  social_linkedin: "",
  social_facebook: "",
  social_instagram: "",
  social_youtube: "",
  admin_page_badge: "",
  admin_page_title: "",
  admin_page_subtitle: "",
  bank_transaction_sources: "",
  bank_transaction_types: "",
  bank_transaction_statuses: "",
  nav_documents_label: "",
  documents_page_title: "",
  documents_page_subtitle: "",
  documents_page_upload_label: "",
  documents_page_upload_hint: "",
  documents_page_empty_text: "",
  signup_bullet_1: "",
  signup_bullet_2: "",
  signup_bullet_3: "",
  signup_cta: "",
};

const WebsiteContext = createContext<WebsiteSettings>(DEFAULT_SETTINGS);

// ─── Standalone branding helpers (usable outside context) ──────────────────

/** Fetch + apply a partner's branding, returns the settings. */
export async function applyPartnerBranding(partnerCode: string): Promise<Record<string, any>> {
  const url = partnerCode
    ? `${process.env.REACT_APP_BACKEND_URL}/api/website-settings?partner_code=${encodeURIComponent(partnerCode)}`
    : `${process.env.REACT_APP_BACKEND_URL}/api/website-settings`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch branding");
  const data = await res.json();
  const s = data.settings || {};
  _applyBrandingToDOM(s);
  return s;
}

function _applyBrandingToDOM(s: Record<string, any>) {
  const _hexToHsl = (hex: string): string | null => {
    const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
    if (!m) return null;
    const r = parseInt(m[1].slice(0, 2), 16) / 255;
    const g = parseInt(m[1].slice(2, 4), 16) / 255;
    const b = parseInt(m[1].slice(4, 6), 16) / 255;
    const max = Math.max(r, g, b), min = Math.min(r, g, b);
    const l = (max + min) / 2;
    let h = 0, s = 0;
    if (max !== min) {
      const d = max - min;
      s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
      if (max === r) h = (g - b) / d + (g < b ? 6 : 0);
      else if (max === g) h = (b - r) / d + 2;
      else h = (r - g) / d + 4;
      h /= 6;
    }
    return `${Math.round(h * 360)} ${Math.round(s * 100)}% ${Math.round(l * 100)}%`;
  };
  const set = (v: string, c: string) => document.documentElement.style.setProperty(v, c);
  const setHsl = (v: string, c: string) => { const h = _hexToHsl(c); if (h) set(v, h); };
  if (s.primary_color) { set("--aa-primary", s.primary_color); setHsl("--primary", s.primary_color); document.documentElement.style.setProperty("--primary-foreground", "0 0% 98%"); }
  if (s.accent_color) { set("--aa-accent", s.accent_color); set("--aa-accent-hover", s.accent_color); setHsl("--ring", s.accent_color); }
  if (s.danger_color) { set("--aa-danger", s.danger_color); setHsl("--destructive", s.danger_color); }
  if (s.success_color) set("--aa-success", s.success_color);
  if (s.warning_color) set("--aa-warning", s.warning_color);
  if (s.background_color) { set("--aa-bg", s.background_color); setHsl("--background", s.background_color); }
  if (s.text_color) { set("--aa-text", s.text_color); setHsl("--foreground", s.text_color); setHsl("--card-foreground", s.text_color); }
  if (s.border_color) { set("--aa-border", s.border_color); setHsl("--border", s.border_color); setHsl("--input", s.border_color); }
  if (s.muted_color) { set("--aa-muted", s.muted_color); setHsl("--muted-foreground", s.muted_color); }
}

// (branding helpers are now in _applyBrandingToDOM above)

export function WebsiteProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<WebsiteSettings>(DEFAULT_SETTINGS);

  useEffect(() => {
    const storedCode = localStorage.getItem("aa_partner_code") || "";
    const url = storedCode
      ? `/website-settings?partner_code=${encodeURIComponent(storedCode)}`
      : "/website-settings";
    api.get(url)
      .then(res => {
        const s = res.data.settings || {};
        setSettings(prev => ({ ...prev, ...s }));
        _applyBrandingToDOM(s);
      })
      .catch(() => {});
  }, []);

  return (
    <WebsiteContext.Provider value={settings}>
      {children}
    </WebsiteContext.Provider>
  );
}

export function useWebsite(): WebsiteSettings {
  return useContext(WebsiteContext);
}
