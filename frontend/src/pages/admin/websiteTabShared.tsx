/**
 * Shared types, constants, and atom components used by WebsiteTab section components.
 */
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "@/components/ui/sonner";
import { Eye, EyeOff, FileText, LayoutTemplate, Pencil, Save, X } from "lucide-react";
import api from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useCountries, useProvinces } from "@/hooks/useCountries";

// ─── Types ────────────────────────────────────────────────────────────────────

export type Section = "branding" | "auth" | "forms" | "sysconfig";

export type AuthSlide =
  | "login" | "signup" | "verify_email"
  | "portal" | "profile" | "not_found" | "admin_panel"
  | "checkout_builder" | "checkout_success" | "gocardless_callback"
  | "checkout_messages"
  | "footer_basics" | "footer_about" | "footer_nav" | "footer_contact" | "footer_social"
  | "documents_page"
  | "store_hero" | "articles_hero";

export interface WebsiteData {
  hero_label: string; hero_title: string; hero_subtitle: string;
  articles_hero_label: string; articles_hero_title: string; articles_hero_subtitle: string;
  login_title: string; login_subtitle: string; login_portal_label: string;
  register_title: string; register_subtitle: string;
  contact_email: string; contact_phone: string; contact_address: string;
  footer_tagline: string; footer_copyright: string;
  footer_about_title: string; footer_about_text: string;
  footer_nav_title: string; footer_contact_title: string; footer_social_title: string;
  social_twitter: string; social_linkedin: string; social_facebook: string;
  social_instagram: string; social_youtube: string;
  nav_store_label: string; nav_articles_label: string; nav_portal_label: string;
  scope_form_title: string; scope_form_subtitle: string;
  signup_form_title: string; signup_form_subtitle: string;
  scope_form_schema: string; signup_form_schema: string;
  email_from_name: string; email_article_subject_template: string;
  email_article_cta_text: string; email_article_footer_text: string;
  email_verification_subject: string; email_verification_body: string;
  msg_cart_empty: string; msg_quote_success: string; msg_scope_success: string;
  msg_currency_unsupported: string; msg_no_payment_methods: string;
  payment_gocardless_label: string; payment_gocardless_description: string;
  payment_stripe_label: string; payment_stripe_description: string;
  checkout_zoho_enabled: boolean; checkout_zoho_title: string;
  checkout_zoho_subscription_options: string; checkout_zoho_product_options: string;
  checkout_zoho_signup_note: string; checkout_zoho_access_note: string;
  checkout_zoho_access_delay_warning: string;
  checkout_partner_enabled: boolean; checkout_partner_title: string;
  checkout_partner_description: string; checkout_partner_options: string;
  checkout_partner_misrep_warning: string; checkout_extra_schema: string;
  checkout_sections: string;
  checkout_success_title: string; checkout_success_paid_msg: string;
  checkout_success_pending_msg: string; checkout_success_expired_msg: string;
  checkout_success_next_steps_title: string;
  checkout_success_step_1: string; checkout_success_step_2: string; checkout_success_step_3: string;
  checkout_portal_link_text: string;
  bank_success_title: string; bank_success_message: string;
  bank_instructions_title: string;
  bank_instruction_1: string; bank_instruction_2: string; bank_instruction_3: string;
  bank_next_steps_title: string;
  bank_next_step_1: string; bank_next_step_2: string; bank_next_step_3: string;
  page_404_title: string; page_404_link_text: string;
  gocardless_processing_title: string; gocardless_processing_subtitle: string;
  gocardless_success_title: string; gocardless_success_message: string;
  gocardless_error_title: string; gocardless_error_message: string;
  gocardless_return_btn_text: string;
  verify_email_label: string; verify_email_title: string; verify_email_subtitle: string;
  portal_title: string; portal_subtitle: string;
  profile_label: string; profile_title: string; profile_subtitle: string;
  cart_title: string; cart_clear_btn_text: string;
  admin_page_badge: string; admin_page_title: string; admin_page_subtitle: string;
  bank_transaction_sources: string; bank_transaction_types: string; bank_transaction_statuses: string;
  nav_documents_label: string;
  documents_page_title: string; documents_page_subtitle: string;
  documents_page_upload_label: string; documents_page_upload_hint: string;
  documents_page_empty_text: string;
  signup_bullet_1: string;
  signup_bullet_2: string;
  signup_bullet_3: string;
  signup_cta: string;
}

export interface BrandingData {
  store_name: string; primary_color: string; accent_color: string;
  danger_color: string; success_color: string; warning_color: string;
  background_color: string; text_color: string; border_color: string; muted_color: string;
  logo_url: string;
}

export const WEB_DEFAULTS: WebsiteData = {
  hero_label: "", hero_title: "", hero_subtitle: "",
  articles_hero_label: "", articles_hero_title: "", articles_hero_subtitle: "",
  login_title: "", login_subtitle: "", login_portal_label: "",
  register_title: "", register_subtitle: "",
  contact_email: "", contact_phone: "", contact_address: "",
  footer_tagline: "", footer_copyright: "",
  footer_about_title: "", footer_about_text: "",
  footer_nav_title: "", footer_contact_title: "", footer_social_title: "",
  social_twitter: "", social_linkedin: "", social_facebook: "", social_instagram: "", social_youtube: "",
  nav_store_label: "", nav_articles_label: "", nav_portal_label: "",
  scope_form_title: "", scope_form_subtitle: "",
  signup_form_title: "", signup_form_subtitle: "",
  scope_form_schema: "", signup_form_schema: "",
  email_from_name: "", email_article_subject_template: "",
  email_article_cta_text: "", email_article_footer_text: "",
  email_verification_subject: "", email_verification_body: "",
  msg_cart_empty: "", msg_quote_success: "", msg_scope_success: "",
  msg_currency_unsupported: "", msg_no_payment_methods: "",
  payment_gocardless_label: "", payment_gocardless_description: "",
  payment_stripe_label: "", payment_stripe_description: "",
  checkout_zoho_enabled: true, checkout_zoho_title: "",
  checkout_zoho_subscription_options: "", checkout_zoho_product_options: "",
  checkout_zoho_signup_note: "", checkout_zoho_access_note: "",
  checkout_zoho_access_delay_warning: "",
  checkout_partner_enabled: true, checkout_partner_title: "",
  checkout_partner_description: "", checkout_partner_options: "",
  checkout_partner_misrep_warning: "", checkout_extra_schema: "[]",
  checkout_sections: "[]",
  checkout_success_title: "", checkout_success_paid_msg: "",
  checkout_success_pending_msg: "", checkout_success_expired_msg: "",
  checkout_success_next_steps_title: "",
  checkout_success_step_1: "", checkout_success_step_2: "", checkout_success_step_3: "",
  checkout_portal_link_text: "",
  bank_success_title: "", bank_success_message: "",
  bank_instructions_title: "",
  bank_instruction_1: "", bank_instruction_2: "", bank_instruction_3: "",
  bank_next_steps_title: "",
  bank_next_step_1: "", bank_next_step_2: "", bank_next_step_3: "",
  page_404_title: "", page_404_link_text: "",
  gocardless_processing_title: "", gocardless_processing_subtitle: "",
  gocardless_success_title: "", gocardless_success_message: "",
  gocardless_error_title: "", gocardless_error_message: "",
  gocardless_return_btn_text: "",
  verify_email_label: "", verify_email_title: "", verify_email_subtitle: "",
  portal_title: "", portal_subtitle: "",
  profile_label: "", profile_title: "", profile_subtitle: "",
  cart_title: "", cart_clear_btn_text: "",
  admin_page_badge: "", admin_page_title: "", admin_page_subtitle: "",
  bank_transaction_sources: "", bank_transaction_types: "", bank_transaction_statuses: "",
  nav_documents_label: "",
  documents_page_title: "", documents_page_subtitle: "",
  documents_page_upload_label: "", documents_page_upload_hint: "",
  documents_page_empty_text: "",
  signup_bullet_1: "", signup_bullet_2: "", signup_bullet_3: "", signup_cta: "",
};

// ─── Atom components ──────────────────────────────────────────────────────────

export function Field({ label, hint, value, onChange, multiline = false, testId, placeholder, disabled }: {
  label: string; hint?: string; value: string; onChange: (v: string) => void;
  multiline?: boolean; testId?: string; placeholder?: string; disabled?: boolean;
}) {
  return (
    <div>
      <label className="text-xs font-medium text-slate-700">{label}</label>
      {hint && <p className="text-[11px] text-slate-400 mt-0.5 mb-1">{hint}</p>}
      {multiline ? (
        <Textarea value={value} onChange={e => onChange(e.target.value)} rows={2}
          className="mt-0.5 text-sm" data-testid={testId} placeholder={placeholder} disabled={disabled} />
      ) : (
        <Input value={value} onChange={e => onChange(e.target.value)}
          className="mt-0.5" data-testid={testId} placeholder={placeholder} disabled={disabled} />
      )}
    </div>
  );
}

export function ColorInput({ label, value, onChange, testId }: {
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

export function SectionDivider({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 pt-2">
      <div className="flex-1 h-px bg-slate-100" />
      <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">{label}</span>
      <div className="flex-1 h-px bg-slate-100" />
    </div>
  );
}

export function AuthTile({ title, description, preview, onEdit, testId }: {
  title: string; description?: string; preview?: string; onEdit: () => void; testId?: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 flex items-center gap-3 hover:border-slate-300 transition-colors cursor-pointer" onClick={onEdit} data-testid={testId}>
      <div className="p-2.5 rounded-xl bg-slate-100 shrink-0">
        <LayoutTemplate size={15} className="text-slate-600" />
      </div>
      <div className="flex-1 min-w-0">
        <h4 className="text-xs font-semibold text-slate-900">{title}</h4>
        {preview
          ? <p className="text-[11px] text-slate-600 mt-0.5 truncate">{preview}</p>
          : description && <p className="text-[11px] text-slate-400 mt-0.5">{description}</p>
        }
      </div>
      <Pencil size={13} className="text-slate-400 shrink-0" />
    </div>
  );
}

export function FormTile({ title, description, fieldCount, onEdit, testId }: {
  title: string; description: string; fieldCount: number; onEdit: () => void; testId?: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 flex items-center gap-4 hover:border-slate-300 transition-colors cursor-pointer" onClick={onEdit} data-testid={testId}>
      <div className="p-3 rounded-xl bg-slate-100 shrink-0">
        <FileText size={18} className="text-slate-600" />
      </div>
      <div className="flex-1 min-w-0">
        <h4 className="text-sm font-semibold text-slate-900">{title}</h4>
        <p className="text-xs text-slate-400 mt-0.5">{description}</p>
        <span className="mt-1.5 inline-block text-[11px] font-medium text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
          {fieldCount} field{fieldCount !== 1 ? "s" : ""}
        </span>
      </div>
      <Pencil size={14} className="text-slate-400 shrink-0" />
    </div>
  );
}

export function SettingRow({ item, onSaved }: { item: any; onSaved: (key: string, val: any) => void }) {
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

// ─── Base Currency ────────────────────────────────────────────────────────────
const CURRENCIES = ["USD", "CAD", "EUR", "AUD", "GBP", "INR", "MXN"];

export function BaseCurrencyWidget() {
  const [currency, setCurrency] = useState("USD");
  const [saving, setSaving] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    api.get("/admin/tenant/base-currency").then(r => {
      setCurrency(r.data.base_currency || "USD");
      setLoaded(true);
    }).catch(() => setLoaded(true));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put("/admin/tenant/base-currency", { base_currency: currency });
      toast.success("Base currency updated");
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to update currency");
    } finally { setSaving(false); }
  };

  if (!loaded) return null;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 mb-4">
      <h4 className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-1">Base Currency</h4>
      <p className="text-xs text-slate-400 mb-3">The primary currency for your partner account.</p>
      <div className="flex items-center gap-3">
        <Select value={currency} onValueChange={setCurrency}>
          <SelectTrigger className="w-40" data-testid="base-currency-select">
            <SelectValue placeholder="Select currency" />
          </SelectTrigger>
          <SelectContent>
            {CURRENCIES.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
          </SelectContent>
        </Select>
        <Button onClick={handleSave} disabled={saving} size="sm" data-testid="base-currency-save-btn">
          {saving ? "Saving..." : "Save"}
        </Button>
      </div>
    </div>
  );
}

// ─── Organization Address ─────────────────────────────────────────────────────
const ORG_COUNTRIES = [
  {v:"Canada",l:"Canada"},{v:"USA",l:"United States"},{v:"UK",l:"United Kingdom"},
  {v:"Australia",l:"Australia"},{v:"India",l:"India"},{v:"Germany",l:"Germany"},
  {v:"France",l:"France"},{v:"Netherlands",l:"Netherlands"},{v:"Singapore",l:"Singapore"},
  {v:"New Zealand",l:"New Zealand"},
];

export function OrgAddressSection() {
  const { user } = useAuth();
  const [tenantId, setTenantId] = useState("");
  const [addr, setAddr] = useState({ line1:"", line2:"", city:"", region:"", postal:"", country:"Canada" });
  const [provinces, setProvinces] = useState<{value:string;label:string}[]>([]);
  const [saving, setSaving] = useState(false);
  const isPlatformAdmin = !!(user?.role && ["platform_admin", "admin"].includes(user.role));

  useEffect(() => {
    if (isPlatformAdmin) return;
    api.get("/admin/tenants/my").then(r => {
      setTenantId(r.data.tenant?.id || "");
      const a = r.data.tenant?.address || {};
      setAddr({ line1: a.line1||"", line2: a.line2||"", city: a.city||"", region: a.region||"", postal: a.postal||"", country: a.country||"Canada" });
    }).catch(() => {});
  }, [isPlatformAdmin]);

  useEffect(() => {
    if (isPlatformAdmin) return;
    if (addr.country === "Canada" || addr.country === "USA") {
      api.get(`/utils/provinces?country_code=${addr.country}`).then(r => setProvinces(r.data.regions || [])).catch(() => setProvinces([]));
    } else { setProvinces([]); }
  }, [addr.country, isPlatformAdmin]);

  if (isPlatformAdmin) return null;

  const save = async () => {
    if (!tenantId) return;
    setSaving(true);
    try {
      await api.put(`/admin/tenants/${tenantId}/address`, { address: addr });
      toast.success("Organization address saved");
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to save address");
    } finally { setSaving(false); }
  };

  return (
    <div className="border-t border-slate-100 pt-4">
      <h3 className="text-sm font-semibold text-slate-700 mb-1">Organization Address</h3>
      <p className="text-xs text-slate-400 mb-3">Your organization's registered address.</p>
      <div className="space-y-2" data-testid="org-address-section">
        <Input placeholder="Line 1 *" value={addr.line1} onChange={e => setAddr(p=>({...p,line1:e.target.value}))} data-testid="org-addr-line1" />
        <Input placeholder="Line 2 (optional)" value={addr.line2} onChange={e => setAddr(p=>({...p,line2:e.target.value}))} data-testid="org-addr-line2" />
        <div className="grid grid-cols-2 gap-2">
          <Input placeholder="City *" value={addr.city} onChange={e => setAddr(p=>({...p,city:e.target.value}))} data-testid="org-addr-city" />
          <Input placeholder="Postal Code *" value={addr.postal} onChange={e => setAddr(p=>({...p,postal:e.target.value}))} data-testid="org-addr-postal" />
        </div>
        <Select value={addr.country} onValueChange={v => setAddr(p=>({...p,country:v,region:""}))}>
          <SelectTrigger data-testid="org-addr-country"><SelectValue placeholder="Country *" /></SelectTrigger>
          <SelectContent>{ORG_COUNTRIES.map(c=><SelectItem key={c.v} value={c.v}>{c.l}</SelectItem>)}</SelectContent>
        </Select>
        {provinces.length > 0 ? (
          <Select value={addr.region} onValueChange={v => setAddr(p=>({...p,region:v}))}>
            <SelectTrigger data-testid="org-addr-region-select"><SelectValue placeholder="Province / State *" /></SelectTrigger>
            <SelectContent>{provinces.map(p=><SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}</SelectContent>
          </Select>
        ) : (
          <Input placeholder="State / Province *" value={addr.region} onChange={e => setAddr(p=>({...p,region:e.target.value}))} data-testid="org-addr-region-input" />
        )}
      </div>
      <Button onClick={save} disabled={saving} size="sm" className="mt-3" data-testid="org-addr-save-btn">
        {saving ? "Saving…" : "Save Address"}
      </Button>
    </div>
  );
}
