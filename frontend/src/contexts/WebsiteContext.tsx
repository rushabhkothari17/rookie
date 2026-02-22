import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import api from "@/lib/api";

export interface WebsiteSettings {
  // Branding
  store_name: string;
  logo_url: string;
  primary_color: string;
  accent_color: string;
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
}

const DEFAULT_SETTINGS: WebsiteSettings = {
  store_name: "",
  logo_url: "",
  primary_color: "",
  accent_color: "",
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
};

const WebsiteContext = createContext<WebsiteSettings>(DEFAULT_SETTINGS);

export function WebsiteProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<WebsiteSettings>(DEFAULT_SETTINGS);

  useEffect(() => {
    api.get("/website-settings")
      .then(res => {
        const s = res.data.settings || {};
        setSettings(prev => ({ ...prev, ...s }));
        if (s.primary_color) {
          document.documentElement.style.setProperty("--aa-primary", s.primary_color);
        }
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
