import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/sonner";
import api from "@/lib/api";

interface WebsiteSettings {
  hero_label: string;
  hero_title: string;
  hero_subtitle: string;
  login_title: string;
  login_subtitle: string;
  login_portal_label: string;
  register_title: string;
  register_subtitle: string;
  contact_email: string;
  contact_phone: string;
  contact_address: string;
  footer_tagline: string;
  quote_form_title: string;
  quote_form_subtitle: string;
  quote_form_response_time: string;
  scope_form_title: string;
  scope_form_subtitle: string;
}

const DEFAULTS: WebsiteSettings = {
  hero_label: "", hero_title: "", hero_subtitle: "",
  login_title: "", login_subtitle: "", login_portal_label: "",
  register_title: "", register_subtitle: "",
  contact_email: "", contact_phone: "", contact_address: "",
  footer_tagline: "",
  quote_form_title: "", quote_form_subtitle: "", quote_form_response_time: "",
  scope_form_title: "", scope_form_subtitle: "",
};

type Section = "hero" | "auth" | "contact" | "forms" | "footer";

const SECTIONS: { key: Section; label: string }[] = [
  { key: "hero", label: "Store Hero" },
  { key: "auth", label: "Authentication Pages" },
  { key: "forms", label: "Forms" },
  { key: "contact", label: "Contact Info" },
  { key: "footer", label: "Footer" },
];

function Field({
  label,
  hint,
  value,
  onChange,
  multiline = false,
  testId,
}: {
  label: string;
  hint?: string;
  value: string;
  onChange: (v: string) => void;
  multiline?: boolean;
  testId?: string;
}) {
  return (
    <div>
      <label className="text-xs font-medium text-slate-700">{label}</label>
      {hint && <p className="text-[11px] text-slate-400 mb-1">{hint}</p>}
      {multiline ? (
        <Textarea
          value={value}
          onChange={e => onChange(e.target.value)}
          rows={2}
          className="mt-0.5 text-sm"
          data-testid={testId}
        />
      ) : (
        <Input
          value={value}
          onChange={e => onChange(e.target.value)}
          className="mt-0.5"
          data-testid={testId}
        />
      )}
    </div>
  );
}

export default function WebsiteTab() {
  const [settings, setSettings] = useState<WebsiteSettings>(DEFAULTS);
  const [activeSection, setActiveSection] = useState<Section>("hero");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/admin/website-settings")
      .then(res => setSettings({ ...DEFAULTS, ...(res.data.settings || {}) }))
      .catch(() => toast.error("Failed to load website settings"))
      .finally(() => setLoading(false));
  }, []);

  const s = (key: keyof WebsiteSettings) => (v: string) =>
    setSettings(prev => ({ ...prev, [key]: v }));

  const save = async () => {
    setSaving(true);
    try {
      await api.put("/admin/website-settings", settings);
      toast.success("Website settings saved");
    } catch {
      toast.error("Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="p-8 text-slate-400 text-sm">Loading…</div>;

  return (
    <div data-testid="admin-website-tab">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Website Content</h2>
          <p className="text-sm text-slate-500 mt-0.5">All text and labels shown on the customer-facing website.</p>
        </div>
        <Button onClick={save} disabled={saving} data-testid="website-save-btn">
          {saving ? "Saving…" : "Save Changes"}
        </Button>
      </div>

      <div className="flex gap-6">
        {/* Sidebar nav */}
        <div className="w-44 shrink-0 space-y-0.5">
          {SECTIONS.map(sec => (
            <button
              key={sec.key}
              type="button"
              onClick={() => setActiveSection(sec.key)}
              className={`w-full text-left px-3 py-2 text-sm rounded transition-colors ${
                activeSection === sec.key
                  ? "bg-slate-900 text-white font-medium"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
              data-testid={`website-section-${sec.key}`}
            >
              {sec.label}
            </button>
          ))}
        </div>

        {/* Content area */}
        <div className="flex-1 space-y-4 border border-slate-100 rounded-xl p-6 bg-white">
          {activeSection === "hero" && (
            <>
              <h3 className="text-sm font-semibold text-slate-700 mb-3">Store Homepage Hero Banner</h3>
              <Field label="Label (small text above title)" value={settings.hero_label} onChange={s("hero_label")} testId="ws-hero-label" />
              <Field label="Title" hint="Main headline on the store homepage" value={settings.hero_title} onChange={s("hero_title")} multiline testId="ws-hero-title" />
              <Field label="Subtitle" hint="Supporting text below the headline" value={settings.hero_subtitle} onChange={s("hero_subtitle")} multiline testId="ws-hero-subtitle" />
            </>
          )}

          {activeSection === "auth" && (
            <>
              <h3 className="text-sm font-semibold text-slate-700 mb-3">Login Page</h3>
              <Field label="Portal label" hint='Small label above the title (e.g. "Customer Portal")' value={settings.login_portal_label} onChange={s("login_portal_label")} testId="ws-login-portal" />
              <Field label="Title" value={settings.login_title} onChange={s("login_title")} testId="ws-login-title" />
              <Field label="Subtitle" value={settings.login_subtitle} onChange={s("login_subtitle")} testId="ws-login-subtitle" />
              <div className="border-t border-slate-100 pt-4 mt-4">
                <h3 className="text-sm font-semibold text-slate-700 mb-3">Register Page</h3>
                <Field label="Title" value={settings.register_title} onChange={s("register_title")} testId="ws-register-title" />
                <Field label="Subtitle" value={settings.register_subtitle} onChange={s("register_subtitle")} multiline testId="ws-register-subtitle" />
              </div>
            </>
          )}

          {activeSection === "forms" && (
            <>
              <h3 className="text-sm font-semibold text-slate-700 mb-3">Quote Request Form</h3>
              <Field label="Title" value={settings.quote_form_title} onChange={s("quote_form_title")} testId="ws-quote-title" />
              <Field label="Subtitle" value={settings.quote_form_subtitle} onChange={s("quote_form_subtitle")} multiline testId="ws-quote-subtitle" />
              <Field label="Response time message" hint='Shown at bottom of form (e.g. "We respond within 1-2 business days.")' value={settings.quote_form_response_time} onChange={s("quote_form_response_time")} testId="ws-quote-response" />
              <div className="border-t border-slate-100 pt-4 mt-4">
                <h3 className="text-sm font-semibold text-slate-700 mb-3">Scope Request Form (RFQ products)</h3>
                <Field label="Title" value={settings.scope_form_title} onChange={s("scope_form_title")} testId="ws-scope-title" />
                <Field label="Subtitle" value={settings.scope_form_subtitle} onChange={s("scope_form_subtitle")} multiline testId="ws-scope-subtitle" />
              </div>
            </>
          )}

          {activeSection === "contact" && (
            <>
              <h3 className="text-sm font-semibold text-slate-700 mb-3">Contact Information</h3>
              <Field label="Contact Email" value={settings.contact_email} onChange={s("contact_email")} testId="ws-contact-email" />
              <Field label="Phone Number" value={settings.contact_phone} onChange={s("contact_phone")} testId="ws-contact-phone" />
              <Field label="Address" value={settings.contact_address} onChange={s("contact_address")} multiline testId="ws-contact-address" />
            </>
          )}

          {activeSection === "footer" && (
            <>
              <h3 className="text-sm font-semibold text-slate-700 mb-3">Footer</h3>
              <Field label="Footer tagline" hint="Short text shown in the footer" value={settings.footer_tagline} onChange={s("footer_tagline")} testId="ws-footer-tagline" />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
