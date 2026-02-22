import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/sonner";
import { Eye, EyeOff, Save, Upload, X } from "lucide-react";
import api from "@/lib/api";
import FormSchemaBuilder from "@/components/FormSchemaBuilder";
import ReferencesSection from "./ReferencesSection";
import EmailSection from "./EmailSection";

// ─── Types ───────────────────────────────────────────────────────────────────

type Section =
  | "branding" | "hero" | "auth" | "forms" | "email" | "errors"
  | "footer" | "references" | "integrations" | "sysconfig";

interface WebsiteData {
  hero_label: string; hero_title: string; hero_subtitle: string;
  login_title: string; login_subtitle: string; login_portal_label: string;
  register_title: string; register_subtitle: string;
  contact_email: string; contact_phone: string; contact_address: string;
  footer_tagline: string; footer_copyright: string;
  nav_store_label: string; nav_articles_label: string; nav_portal_label: string;
  quote_form_title: string; quote_form_subtitle: string; quote_form_response_time: string;
  scope_form_title: string; scope_form_subtitle: string;
  signup_form_title: string; signup_form_subtitle: string;
  quote_form_schema: string; scope_form_schema: string; signup_form_schema: string;
  email_from_name: string; email_article_subject_template: string;
  email_article_cta_text: string; email_article_footer_text: string;
  email_verification_subject: string; email_verification_body: string;
  msg_partner_tagging_prompt: string; msg_override_required: string;
  msg_cart_empty: string; msg_quote_success: string; msg_scope_success: string;
}

interface BrandingData {
  store_name: string; primary_color: string; accent_color: string; logo_url: string;
}

const WEB_DEFAULTS: WebsiteData = {
  hero_label: "", hero_title: "", hero_subtitle: "",
  login_title: "", login_subtitle: "", login_portal_label: "",
  register_title: "", register_subtitle: "",
  contact_email: "", contact_phone: "", contact_address: "",
  footer_tagline: "", footer_copyright: "",
  nav_store_label: "", nav_articles_label: "", nav_portal_label: "",
  quote_form_title: "", quote_form_subtitle: "", quote_form_response_time: "",
  scope_form_title: "", scope_form_subtitle: "",
  signup_form_title: "", signup_form_subtitle: "",
  quote_form_schema: "", scope_form_schema: "", signup_form_schema: "",
  email_from_name: "", email_article_subject_template: "",
  email_article_cta_text: "", email_article_footer_text: "",
  email_verification_subject: "", email_verification_body: "",
  msg_partner_tagging_prompt: "", msg_override_required: "",
  msg_cart_empty: "", msg_quote_success: "", msg_scope_success: "",
};

// ─── Sidebar config ───────────────────────────────────────────────────────────

const SIDEBAR: { group: string; items: { key: Section; label: string }[] }[] = [
  {
    group: "Brand",
    items: [{ key: "branding", label: "Branding" }],
  },
  {
    group: "Content",
    items: [
      { key: "hero", label: "Store Hero" },
      { key: "auth", label: "Auth Pages" },
      { key: "forms", label: "Forms" },
      { key: "email", label: "Email Templates" },
      { key: "errors", label: "Error Messages" },
      { key: "footer", label: "Footer & Nav" },
    ],
  },
  {
    group: "Configuration",
    items: [
      { key: "references", label: "References" },
      { key: "integrations", label: "Integrations" },
      { key: "sysconfig", label: "System Config" },
    ],
  },
];

// ─── Small helper components ─────────────────────────────────────────────────

function Field({ label, hint, value, onChange, multiline = false, testId }: {
  label: string; hint?: string; value: string;
  onChange: (v: string) => void; multiline?: boolean; testId?: string;
}) {
  return (
    <div>
      <label className="text-xs font-medium text-slate-700">{label}</label>
      {hint && <p className="text-[11px] text-slate-400 mb-1">{hint}</p>}
      {multiline ? (
        <Textarea value={value} onChange={e => onChange(e.target.value)} rows={2}
          className="mt-0.5 text-sm" data-testid={testId} />
      ) : (
        <Input value={value} onChange={e => onChange(e.target.value)}
          className="mt-0.5" data-testid={testId} />
      )}
    </div>
  );
}

function ColorInput({ label, value, onChange, testId }: {
  label: string; value: string; onChange: (v: string) => void; testId?: string;
}) {
  return (
    <div>
      <label className="text-xs text-slate-600">{label}</label>
      <div className="flex items-center gap-2 mt-1">
        <input type="color" value={value || "#000000"} onChange={e => onChange(e.target.value)}
          className="w-10 h-10 rounded cursor-pointer border border-slate-200" data-testid={testId} />
        <Input value={value} onChange={e => onChange(e.target.value)}
          placeholder="#000000" className="w-32 font-mono text-sm" />
      </div>
    </div>
  );
}

// Reusable setting row for DB-backed structured settings (integrations, links, sysconfig)
function SettingRow({ item, onSaved }: { item: any; onSaved: (key: string, val: any) => void }) {
  const [editVal, setEditVal] = useState("");
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showSecret, setShowSecret] = useState(false);
  const isBool = item.value_type === "bool";
  const isNumber = item.value_type === "number";
  const isSecret = item.is_secret || item.value_type === "secret";
  const displayVal = String(item.value_json ?? "");

  const handleSave = async () => {
    setSaving(true);
    try {
      let val: any = editVal;
      if (isBool) val = editVal === "true";
      if (isNumber) val = parseFloat(editVal);
      await api.put(`/admin/settings/key/${item.key}`, { value: val });
      toast.success(`'${item.key}' saved`);
      onSaved(item.key, val);
      setIsEditing(false);
      setShowSecret(false);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Save failed");
    } finally { setSaving(false); }
  };

  const handleBoolToggle = async (checked: boolean) => {
    setSaving(true);
    try {
      await api.put(`/admin/settings/key/${item.key}`, { value: checked });
      toast.success(`'${item.key}' updated`);
      onSaved(item.key, checked);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Save failed");
    } finally { setSaving(false); }
  };

  return (
    <div className="flex items-start gap-3 py-2 border-b border-slate-100 last:border-0">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-xs font-mono font-medium text-slate-700">{item.key}</span>
          {isSecret && <span className="text-[10px] text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded">secret</span>}
          {isNumber && <span className="text-[10px] text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">number</span>}
        </div>
        {item.description && <p className="text-xs text-slate-400 mb-1">{item.description}</p>}
        {isBool ? (
          <div className="flex items-center gap-2">
            <button role="switch" aria-checked={item.value_json === true || item.value_json === "true"}
              onClick={() => handleBoolToggle(!(item.value_json === true || item.value_json === "true"))}
              disabled={saving} data-testid={`setting-toggle-${item.key}`}
              className={`relative inline-flex h-5 w-9 items-center rounded-full border-2 border-transparent transition-colors focus:outline-none disabled:opacity-50 ${(item.value_json === true || item.value_json === "true") ? "bg-primary" : "bg-input"}`}>
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${(item.value_json === true || item.value_json === "true") ? "translate-x-4" : "translate-x-0"}`} />
            </button>
            <span className="text-xs text-slate-500">{(item.value_json === true || item.value_json === "true") ? "Enabled" : "Disabled"}</span>
          </div>
        ) : isEditing ? (
          <div className="flex items-center gap-2">
            <div className="relative">
              <Input type={isSecret && !showSecret ? "password" : isNumber ? "number" : "text"}
                value={editVal} onChange={e => setEditVal(e.target.value)}
                className="h-7 text-xs font-mono w-72 pr-7" autoFocus data-testid={`setting-input-${item.key}`} />
              {isSecret && (
                <button type="button" onClick={() => setShowSecret(!showSecret)} className="absolute right-2 top-1.5 text-slate-400 hover:text-slate-600">
                  {showSecret ? <EyeOff size={12} /> : <Eye size={12} />}
                </button>
              )}
            </div>
            <Button size="sm" className="h-7 px-2 text-xs gap-1" onClick={handleSave} disabled={saving} data-testid={`setting-save-${item.key}`}>
              <Save size={10} />{saving ? "…" : "Save"}
            </Button>
            <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={() => { setIsEditing(false); setShowSecret(false); }} disabled={saving}>
              <X size={10} />
            </Button>
          </div>
        ) : (
          <button onClick={() => { setEditVal(displayVal); setIsEditing(true); }}
            className="text-left text-xs font-mono text-slate-600 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded px-2 py-1 max-w-md w-full truncate transition-colors"
            data-testid={`setting-display-${item.key}`}>
            {isSecret ? "••••••••" : displayVal || <span className="text-slate-300 italic">not set</span>}
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function WebsiteTab() {
  const [activeSection, setActiveSection] = useState<Section>("branding");
  const [ws, setWs] = useState<WebsiteData>(WEB_DEFAULTS);
  const [branding, setBranding] = useState<BrandingData>({ store_name: "", primary_color: "", accent_color: "", logo_url: "" });
  const [structured, setStructured] = useState<Record<string, any[]>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = async () => {
    setLoading(true);
    try {
      const [webRes, appRes, structRes] = await Promise.all([
        api.get("/admin/website-settings"),
        api.get("/admin/settings"),
        api.get("/admin/settings/structured"),
      ]);
      const ws_ = webRes.data.settings || {};
      setWs({ ...WEB_DEFAULTS, ...ws_ });
      const app_ = appRes.data.settings || {};
      setBranding({ store_name: app_.store_name || "", primary_color: app_.primary_color || "", accent_color: app_.accent_color || "", logo_url: app_.logo_url || "" });
      setStructured(structRes.data.settings || {});
    } catch {
      toast.error("Failed to load settings");
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const s = (key: keyof WebsiteData) => (v: string) => setWs(prev => ({ ...prev, [key]: v }));
  const b = (key: keyof BrandingData) => (v: string) => setBranding(prev => ({ ...prev, [key]: v }));

  const save = async () => {
    setSaving(true);
    try {
      await Promise.all([
        api.put("/admin/website-settings", ws),
        api.put("/admin/settings", branding),
      ]);
      toast.success("Settings saved");
    } catch {
      toast.error("Failed to save settings");
    } finally { setSaving(false); }
  };

  const handleLogoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingLogo(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await api.post("/admin/upload-logo", formData, { headers: { "Content-Type": "multipart/form-data" } });
      setBranding(prev => ({ ...prev, logo_url: res.data.logo_url }));
      toast.success("Logo uploaded");
    } catch { toast.error("Logo upload failed"); }
    finally { setUploadingLogo(false); if (fileRef.current) fileRef.current.value = ""; }
  };

  const handleRemoveLogo = async () => {
    try {
      await api.put("/admin/settings", { logo_url: "" });
      setBranding(prev => ({ ...prev, logo_url: "" }));
      toast.success("Logo removed");
    } catch { toast.error("Failed to remove logo"); }
  };

  const onStructuredSaved = (key: string, newVal: any) => {
    setStructured(prev => {
      const next = { ...prev };
      Object.keys(next).forEach(cat => {
        next[cat] = next[cat].map(item => item.key === key ? { ...item, value_json: newVal } : item);
      });
      return next;
    });
  };

  const structuredForCategories = (cats: string[]) => {
    return cats.flatMap(cat => (structured[cat] || []).map(item => ({ ...item, _category: cat })));
  };

  if (loading) return <div className="p-8 text-slate-400 text-sm">Loading…</div>;

  return (
    <div data-testid="admin-website-tab">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Website Settings</h2>
          <p className="text-sm text-slate-500 mt-0.5">Manage all content, branding, forms, and integrations.</p>
        </div>
        <Button onClick={save} disabled={saving} data-testid="website-save-btn">
          {saving ? "Saving…" : "Save Changes"}
        </Button>
      </div>

      <div className="flex gap-6">
        {/* Sidebar */}
        <div className="w-48 shrink-0 space-y-4">
          {SIDEBAR.map(group => (
            <div key={group.group}>
              <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider px-3 pb-1">{group.group}</p>
              <div className="space-y-0.5">
                {group.items.map(item => (
                  <button key={item.key} type="button" onClick={() => setActiveSection(item.key)}
                    className={`w-full text-left px-3 py-2 text-sm rounded transition-colors ${activeSection === item.key ? "bg-slate-900 text-white font-medium" : "text-slate-600 hover:bg-slate-100"}`}
                    data-testid={`website-section-${item.key}`}>
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0 border border-slate-100 rounded-xl p-6 bg-white space-y-5">

          {/* ── Branding ── */}
          {activeSection === "branding" && (
            <>
              <h3 className="text-sm font-semibold text-slate-700">Store Information</h3>
              <Field label="Store Name" value={branding.store_name} onChange={b("store_name")} testId="ws-store-name" />

              <div className="border-t border-slate-100 pt-4">
                <h3 className="text-sm font-semibold text-slate-700 mb-3">Logo</h3>
                {branding.logo_url ? (
                  <div className="flex items-center gap-4">
                    <img src={branding.logo_url} alt="Logo" className="h-14 w-auto object-contain border border-slate-200 rounded-lg p-2 bg-slate-50" data-testid="ws-logo-preview" />
                    <div className="flex gap-2">
                      <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()} disabled={uploadingLogo}>Replace</Button>
                      <Button variant="ghost" size="sm" className="text-red-500" onClick={handleRemoveLogo}>Remove</Button>
                    </div>
                  </div>
                ) : (
                  <div className="border-2 border-dashed border-slate-200 rounded-xl p-8 text-center cursor-pointer hover:border-slate-400 transition-colors" onClick={() => fileRef.current?.click()} data-testid="ws-logo-dropzone">
                    <Upload size={24} className="mx-auto text-slate-400 mb-2" />
                    <p className="text-sm text-slate-500">Click to upload logo</p>
                    <p className="text-xs text-slate-400 mt-1">PNG, JPG, SVG — max 2MB</p>
                  </div>
                )}
                <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handleLogoUpload} data-testid="ws-logo-input" />
              </div>

              <div className="border-t border-slate-100 pt-4">
                <h3 className="text-sm font-semibold text-slate-700 mb-1">Brand Colors</h3>
                <p className="text-xs text-slate-400 mb-3">Applied to the storefront. Primary = navbars. Accent = CTA buttons.</p>
                <div className="grid grid-cols-2 gap-4">
                  <ColorInput label="Primary" value={branding.primary_color} onChange={b("primary_color")} testId="ws-primary-color" />
                  <ColorInput label="Accent" value={branding.accent_color} onChange={b("accent_color")} testId="ws-accent-color" />
                </div>
              </div>
            </>
          )}

          {/* ── Store Hero ── */}
          {activeSection === "hero" && (
            <>
              <h3 className="text-sm font-semibold text-slate-700 mb-3">Store Homepage Hero Banner</h3>
              <Field label="Label (small text above title)" value={ws.hero_label} onChange={s("hero_label")} testId="ws-hero-label" />
              <Field label="Title" hint="Main headline" value={ws.hero_title} onChange={s("hero_title")} multiline testId="ws-hero-title" />
              <Field label="Subtitle" value={ws.hero_subtitle} onChange={s("hero_subtitle")} multiline testId="ws-hero-subtitle" />
            </>
          )}

          {/* ── Auth Pages ── */}
          {activeSection === "auth" && (
            <>
              <h3 className="text-sm font-semibold text-slate-700 mb-3">Login Page</h3>
              <Field label="Portal label" hint='Small label above the title (e.g. "Customer Portal")' value={ws.login_portal_label} onChange={s("login_portal_label")} testId="ws-login-portal" />
              <Field label="Title" value={ws.login_title} onChange={s("login_title")} testId="ws-login-title" />
              <Field label="Subtitle" value={ws.login_subtitle} onChange={s("login_subtitle")} testId="ws-login-subtitle" />
              <div className="border-t border-slate-100 pt-4">
                <h3 className="text-sm font-semibold text-slate-700 mb-3">Register / Sign Up Page</h3>
                <Field label="Title" value={ws.register_title} onChange={s("register_title")} testId="ws-register-title" />
                <Field label="Subtitle" value={ws.register_subtitle} onChange={s("register_subtitle")} multiline testId="ws-register-subtitle" />
              </div>
            </>
          )}

          {/* ── Forms ── */}
          {activeSection === "forms" && (
            <>
              <h3 className="text-sm font-semibold text-slate-700">Quote Request Form</h3>
              <p className="text-xs text-slate-400 -mt-3">Shown when a customer requests a quote on a product.</p>
              <Field label="Title" value={ws.quote_form_title} onChange={s("quote_form_title")} testId="ws-quote-title" />
              <Field label="Subtitle" value={ws.quote_form_subtitle} onChange={s("quote_form_subtitle")} multiline testId="ws-quote-subtitle" />
              <Field label="Response time message" hint='Shown at bottom of form (e.g. "We respond within 1-2 business days.")' value={ws.quote_form_response_time} onChange={s("quote_form_response_time")} testId="ws-quote-response" />
              <div className="mt-2">
                <FormSchemaBuilder title="Form fields" value={ws.quote_form_schema} onChange={s("quote_form_schema")} />
              </div>

              <div className="border-t border-slate-100 pt-5">
                <h3 className="text-sm font-semibold text-slate-700">Scope Request Form</h3>
                <p className="text-xs text-slate-400 mb-3">Shown for fixed-scope / RFQ products.</p>
                <Field label="Title" value={ws.scope_form_title} onChange={s("scope_form_title")} testId="ws-scope-title" />
                <Field label="Subtitle" value={ws.scope_form_subtitle} onChange={s("scope_form_subtitle")} multiline testId="ws-scope-subtitle" />
                <div className="mt-2">
                  <FormSchemaBuilder title="Form fields" value={ws.scope_form_schema} onChange={s("scope_form_schema")} />
                </div>
              </div>

              <div className="border-t border-slate-100 pt-5">
                <h3 className="text-sm font-semibold text-slate-700">Customer Sign-up Form</h3>
                <p className="text-xs text-slate-400 mb-3">Shown on the registration page. Locked fields cannot be removed (core auth). Toggle "shown/hidden" to control optional fields.</p>
                <Field label="Title" value={ws.signup_form_title} onChange={s("signup_form_title")} testId="ws-signup-title" />
                <Field label="Subtitle" value={ws.signup_form_subtitle} onChange={s("signup_form_subtitle")} multiline testId="ws-signup-subtitle" />
                <div className="mt-2">
                  <FormSchemaBuilder title="Form fields" value={ws.signup_form_schema} onChange={s("signup_form_schema")} />
                </div>
              </div>
            </>
          )}

          {/* ── Email Templates ── */}
          {activeSection === "email" && (
            <>
              <h3 className="text-sm font-semibold text-slate-700 mb-1">Email Sender</h3>
              <Field label="From Name" hint='Display name shown as sender (e.g. "Acme Support")' value={ws.email_from_name} onChange={s("email_from_name")} testId="ws-email-from-name" />

              <div className="border-t border-slate-100 pt-4">
                <h3 className="text-sm font-semibold text-slate-700 mb-3">Article Email</h3>
                <p className="text-xs text-slate-400 mb-3">Sent when admin emails an article to customers. Use <code className="bg-slate-100 px-1 rounded">{"{{article_title}}"}</code> in subject.</p>
                <Field label="Subject template" value={ws.email_article_subject_template} onChange={s("email_article_subject_template")} testId="ws-email-article-subject" />
                <Field label="CTA button text" value={ws.email_article_cta_text} onChange={s("email_article_cta_text")} testId="ws-email-article-cta" />
                <Field label="Footer text" hint="Small text shown at the bottom of the email." value={ws.email_article_footer_text} onChange={s("email_article_footer_text")} multiline testId="ws-email-article-footer" />
              </div>

              <div className="border-t border-slate-100 pt-4">
                <h3 className="text-sm font-semibold text-slate-700 mb-3">Verification Email</h3>
                <p className="text-xs text-slate-400 mb-3">Sent on signup. Use <code className="bg-slate-100 px-1 rounded">{"{{code}}"}</code> for the verification code.</p>
                <Field label="Subject" value={ws.email_verification_subject} onChange={s("email_verification_subject")} testId="ws-email-verify-subject" />
                <Field label="Body" value={ws.email_verification_body} onChange={s("email_verification_body")} multiline testId="ws-email-verify-body" />
              </div>
            </>
          )}

          {/* ── Error Messages ── */}
          {activeSection === "errors" && (
            <>
              <h3 className="text-sm font-semibold text-slate-700 mb-3">User-facing Messages</h3>
              <p className="text-xs text-slate-400 mb-4">Customize the messages and prompts shown to customers.</p>
              <Field label="Partner tagging prompt" hint="Shown in cart when partner tagging status is not selected." value={ws.msg_partner_tagging_prompt} onChange={s("msg_partner_tagging_prompt")} multiline testId="ws-msg-partner" />
              <Field label="Override code required message" hint="Shown when customer hasn't tagged you as their partner." value={ws.msg_override_required} onChange={s("msg_override_required")} multiline testId="ws-msg-override" />
              <Field label="Cart empty message" value={ws.msg_cart_empty} onChange={s("msg_cart_empty")} testId="ws-msg-cart-empty" />
              <Field label="Quote request success" value={ws.msg_quote_success} onChange={s("msg_quote_success")} testId="ws-msg-quote-success" />
              <Field label="Scope request success" value={ws.msg_scope_success} onChange={s("msg_scope_success")} testId="ws-msg-scope-success" />
            </>
          )}

          {/* ── Footer & Nav ── */}
          {activeSection === "footer" && (
            <>
              <h3 className="text-sm font-semibold text-slate-700 mb-3">Footer</h3>
              <Field label="Footer tagline" hint="Short text shown in the footer" value={ws.footer_tagline} onChange={s("footer_tagline")} testId="ws-footer-tagline" />
              <Field label="Copyright text" hint='e.g. "© 2025 Acme Inc. All rights reserved."' value={ws.footer_copyright} onChange={s("footer_copyright")} testId="ws-footer-copyright" />

              <div className="border-t border-slate-100 pt-4">
                <h3 className="text-sm font-semibold text-slate-700 mb-3">Navigation Labels</h3>
                <div className="grid grid-cols-3 gap-4">
                  <Field label="Store link label" value={ws.nav_store_label} onChange={s("nav_store_label")} testId="ws-nav-store" />
                  <Field label="Articles link label" value={ws.nav_articles_label} onChange={s("nav_articles_label")} testId="ws-nav-articles" />
                  <Field label="Portal link label" value={ws.nav_portal_label} onChange={s("nav_portal_label")} testId="ws-nav-portal" />
                </div>
              </div>

              <div className="border-t border-slate-100 pt-4">
                <h3 className="text-sm font-semibold text-slate-700 mb-3">Contact Info</h3>
                <Field label="Contact Email" value={ws.contact_email} onChange={s("contact_email")} testId="ws-contact-email" />
                <Field label="Phone Number" value={ws.contact_phone} onChange={s("contact_phone")} testId="ws-contact-phone" />
                <Field label="Address" value={ws.contact_address} onChange={s("contact_address")} multiline testId="ws-contact-address" />
              </div>
            </>
          )}

          {/* ── Links & URLs ── */}
          {activeSection === "links" && (
            <>
              <h3 className="text-sm font-semibold text-slate-700 mb-1">Links & URLs</h3>
              <p className="text-xs text-slate-400 mb-4">Click any value to edit. Changes are saved individually.</p>
              {["Zoho", "Branding"].map(cat => {
                const items = structured[cat] || [];
                if (!items.length) return null;
                return (
                  <div key={cat} className="rounded-xl border border-slate-200 bg-white p-5 mb-4">
                    <h4 className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-3">{cat}</h4>
                    {items.map(item => <SettingRow key={item.key} item={item} onSaved={onStructuredSaved} />)}
                  </div>
                );
              })}
              {!structured["Zoho"] && !structured["Branding"] && (
                <p className="text-sm text-slate-400">No link settings configured.</p>
              )}
            </>
          )}

          {/* ── Integrations ── */}
          {activeSection === "integrations" && (
            <>
              <h3 className="text-sm font-semibold text-slate-700 mb-1">Integrations</h3>
              <p className="text-xs text-slate-400 mb-4">API keys and credentials for third-party services. Click a value to edit.</p>
              {["Payments", "Email"].map(cat => {
                const items = (structured[cat] || []).filter(item =>
                  item.is_secret || item.value_type === "secret" ||
                  ["key", "token", "secret"].some((kw: string) => item.key.toLowerCase().includes(kw)) ||
                  item.key.toLowerCase().includes("email") || item.key.toLowerCase().includes("sender")
                );
                if (!items.length) return null;
                return (
                  <div key={cat} className="rounded-xl border border-slate-200 bg-white p-5 mb-4">
                    <h4 className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-3">{cat}</h4>
                    {items.map((item: any) => <SettingRow key={item.key} item={item} onSaved={onStructuredSaved} />)}
                  </div>
                );
              })}
              {!structured["Payments"] && !structured["Email"] && (
                <p className="text-sm text-slate-400">No integration settings found.</p>
              )}
            </>
          )}

          {/* ── System Config ── */}
          {activeSection === "sysconfig" && (
            <>
              <h3 className="text-sm font-semibold text-slate-700 mb-1">System Configuration</h3>
              <p className="text-xs text-slate-400 mb-4">Database-backed settings. Click any value to edit.</p>
              {["Operations", "FeatureFlags"].map(cat => {
                const items = structured[cat] || [];
                if (!items.length) return null;
                return (
                  <div key={cat} className="rounded-xl border border-slate-200 bg-white p-5 mb-4">
                    <h4 className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-3">{cat.replace("FeatureFlags", "Feature Flags")}</h4>
                    {items.map((item: any) => <SettingRow key={item.key} item={item} onSaved={onStructuredSaved} />)}
                  </div>
                );
              })}
              {/* Non-API-key items from Payments (e.g. service_fee_rate) */}
              {(() => {
                const feeItems = (structured["Payments"] || []).filter((item: any) =>
                  !item.is_secret && item.value_type !== "secret" &&
                  !["key", "token", "secret"].some((kw: string) => item.key.toLowerCase().includes(kw)) &&
                  !item.key.toLowerCase().includes("sender")
                );
                if (!feeItems.length) return null;
                return (
                  <div className="rounded-xl border border-slate-200 bg-white p-5 mb-4">
                    <h4 className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-3">Payment Settings</h4>
                    {feeItems.map((item: any) => <SettingRow key={item.key} item={item} onSaved={onStructuredSaved} />)}
                  </div>
                );
              })()}
            </>
          )}

        </div>
      </div>
    </div>
  );
}
