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
  // Footer
  footer_tagline: string;
  // Quote / Scope forms
  quote_form_title: string;
  quote_form_subtitle: string;
  quote_form_response_time: string;
  scope_form_title: string;
  scope_form_subtitle: string;
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
  quote_form_title: "Request a Quote",
  quote_form_subtitle: "Fill in your details and we'll get back to you with a custom quote.",
  quote_form_response_time: "We'll respond within 1-2 business days.",
  scope_form_title: "Request Scope",
  scope_form_subtitle: "Tell us about your project and we'll get back to you with a detailed scope, timeline, and quote.",
};

const WebsiteContext = createContext<WebsiteSettings>(DEFAULT_SETTINGS);

export function WebsiteProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<WebsiteSettings>(DEFAULT_SETTINGS);

  useEffect(() => {
    api.get("/website-settings")
      .then(res => {
        const s = res.data.settings || {};
        setSettings(prev => ({ ...prev, ...s }));
        // Apply CSS custom property for primary color if set
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
