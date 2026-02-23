import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/sonner";
import { Eye, EyeOff, FileText, LayoutTemplate, Pencil, Save, Upload, X } from "lucide-react";
import api from "@/lib/api";
import FormSchemaBuilder from "@/components/FormSchemaBuilder";
import ReferencesSection from "./ReferencesSection";
import EmailSection from "./EmailSection";
import CheckoutSectionsBuilder from "@/components/admin/CheckoutSectionsBuilder";
import SlideOver from "@/components/admin/SlideOver";

// ─── Types ────────────────────────────────────────────────────────────────────

type Section = "branding" | "auth" | "forms" | "email" | "footer" | "references" | "payments" | "sysconfig";

type AuthSlide =
  | "login" | "signup" | "verify_email"
  | "portal" | "profile" | "not_found" | "admin_panel"
  | "checkout_builder" | "checkout_success" | "gocardless_callback"
  | "checkout_messages" | "form_messages"
  | "footer_basics" | "footer_about" | "footer_nav" | "footer_contact" | "footer_social";

interface WebsiteData {
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
  quote_form_title: string; quote_form_subtitle: string; quote_form_response_time: string;
  scope_form_title: string; scope_form_subtitle: string;
  signup_form_title: string; signup_form_subtitle: string;
  quote_form_schema: string; scope_form_schema: string; signup_form_schema: string;
  email_from_name: string; email_article_subject_template: string;
  email_article_cta_text: string; email_article_footer_text: string;
  email_verification_subject: string; email_verification_body: string;
  msg_partner_tagging_prompt: string; msg_override_required: string;
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
}

interface BrandingData {
  store_name: string; primary_color: string; accent_color: string; logo_url: string;
}

const WEB_DEFAULTS: WebsiteData = {
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
  quote_form_title: "", quote_form_subtitle: "", quote_form_response_time: "",
  scope_form_title: "", scope_form_subtitle: "",
  signup_form_title: "", signup_form_subtitle: "",
  quote_form_schema: "", scope_form_schema: "", signup_form_schema: "",
  email_from_name: "", email_article_subject_template: "",
  email_article_cta_text: "", email_article_footer_text: "",
  email_verification_subject: "", email_verification_body: "",
  msg_partner_tagging_prompt: "", msg_override_required: "",
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
};

// ─── Sidebar ──────────────────────────────────────────────────────────────────

const SIDEBAR: { group: string; items: { key: Section; label: string }[] }[] = [
  { group: "Brand", items: [{ key: "branding", label: "Branding & Hero" }] },
  { group: "Content", items: [
    { key: "auth", label: "Auth & Pages" },
    { key: "forms", label: "Forms" },
    { key: "email", label: "Email Templates" },
  ]},
  { group: "Configuration", items: [
    { key: "footer", label: "Footer & Nav" },
    { key: "references", label: "References" },
    { key: "payments", label: "Payments" },
    { key: "sysconfig", label: "System Config" },
  ]},
];

// ─── Helper components ────────────────────────────────────────────────────────

function Field({ label, hint, value, onChange, multiline = false, testId, placeholder }: {
  label: string; hint?: string; value: string; onChange: (v: string) => void;
  multiline?: boolean; testId?: string; placeholder?: string;
}) {
  return (
    <div>
      <label className="text-xs font-medium text-slate-700">{label}</label>
      {hint && <p className="text-[11px] text-slate-400 mt-0.5 mb-1">{hint}</p>}
      {multiline ? (
        <Textarea value={value} onChange={e => onChange(e.target.value)} rows={2}
          className="mt-0.5 text-sm" data-testid={testId} placeholder={placeholder} />
      ) : (
        <Input value={value} onChange={e => onChange(e.target.value)}
          className="mt-0.5" data-testid={testId} placeholder={placeholder} />
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

function Toggle({ label, description, checked, onChange, testId }: {
  label: string; description?: string; checked: boolean; onChange: (v: boolean) => void; testId?: string;
}) {
  return (
    <div className="flex items-center justify-between py-2">
      <div>
        <p className="text-sm font-medium text-slate-700">{label}</p>
        {description && <p className="text-xs text-slate-400 mt-0.5">{description}</p>}
      </div>
      <button role="switch" aria-checked={checked} onClick={() => onChange(!checked)}
        data-testid={testId}
        className={`relative inline-flex h-5 w-9 items-center rounded-full border-2 border-transparent transition-colors ${checked ? "bg-slate-900" : "bg-slate-200"}`}>
        <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${checked ? "translate-x-4" : "translate-x-0"}`} />
      </button>
    </div>
  );
}

function SectionDivider({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 pt-2">
      <div className="flex-1 h-px bg-slate-100" />
      <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">{label}</span>
      <div className="flex-1 h-px bg-slate-100" />
    </div>
  );
}

// ─── Tile components ──────────────────────────────────────────────────────────

function AuthTile({ title, description, preview, onEdit, testId }: {
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

function FormTile({ title, description, fieldCount, onEdit, testId }: {
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

// ─── SettingRow ───────────────────────────────────────────────────────────────

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

// ─── Payment Provider Card ────────────────────────────────────────────────────

function PaymentProviderCard({
  title, subtitle, enabledItem, displayLabelKey, displayDescKey,
  initialLabel, initialDesc, credItems, feeRateItem, onSaved,
  onCallbackSettings,
}: {
  title: string; subtitle: string; enabledItem: any;
  displayLabelKey: string; displayDescKey: string;
  initialLabel: string; initialDesc: string;
  credItems: any[]; feeRateItem: any | null;
  onSaved: (key: string, val: any) => void;
  onCallbackSettings?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [label, setLabel] = useState(initialLabel);
  const [desc, setDesc] = useState(initialDesc);
  const [saving, setSaving] = useState(false);
  const [isEnabled, setIsEnabled] = useState(
    enabledItem?.value_json === "true" || enabledItem?.value_json === true
  );
  const [toggling, setToggling] = useState(false);

  useEffect(() => { setLabel(initialLabel); }, [initialLabel]);
  useEffect(() => { setDesc(initialDesc); }, [initialDesc]);

  const toggleEnabled = async () => {
    const next = !isEnabled;
    setToggling(true);
    try {
      await api.put(`/admin/settings/key/${enabledItem.key}`, { value: next });
      setIsEnabled(next);
      toast.success(next ? `${title} enabled` : `${title} disabled`);
    } catch { toast.error("Failed to update"); }
    finally { setToggling(false); }
  };

  const saveLabels = async () => {
    setSaving(true);
    try {
      await api.put("/admin/website-settings", { [displayLabelKey]: label, [displayDescKey]: desc });
      toast.success("Checkout labels saved");
    } catch { toast.error("Save failed"); }
    finally { setSaving(false); }
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white overflow-hidden" data-testid={`payment-card-${enabledItem?.key}`}>
      <div className="flex items-center justify-between px-5 py-4">
        <div className="flex items-center gap-3">
          <div className={`h-2.5 w-2.5 rounded-full flex-shrink-0 transition-colors ${isEnabled ? "bg-green-500" : "bg-slate-300"}`} />
          <div>
            <p className="text-sm font-semibold text-slate-900">{title}</p>
            <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={toggleEnabled} disabled={toggling || !enabledItem}
            className={`px-3 py-1 text-xs font-medium rounded-full transition-all border disabled:opacity-50 ${isEnabled ? "bg-green-50 text-green-700 border-green-200 hover:bg-red-50 hover:text-red-700 hover:border-red-200" : "bg-slate-100 text-slate-500 border-slate-200 hover:bg-green-50 hover:text-green-700 hover:border-green-200"}`}
            data-testid={`payment-toggle-${enabledItem?.key}`}>
            {isEnabled ? "Enabled" : "Disabled"}
          </button>
          <button onClick={() => setOpen(v => !v)}
            className={`p-2 rounded-lg transition-colors ${open ? "bg-slate-900 text-white" : "text-slate-400 hover:text-slate-700 hover:bg-slate-100"}`}
            data-testid={`payment-edit-${enabledItem?.key}`}>
            <Pencil size={13} />
          </button>
        </div>
      </div>
      {open && (
        <div className="border-t border-slate-100">
          <div className="p-4 bg-slate-50 space-y-3">
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-widest">Checkout Display</p>
            <div>
              <label className="text-xs text-slate-500 block mb-1">Label (shown to customers)</label>
              <input value={label} onChange={e => setLabel(e.target.value)} className="w-full h-9 text-sm border border-slate-200 rounded-lg px-3 bg-white" />
            </div>
            <div>
              <label className="text-xs text-slate-500 block mb-1">Description (shown under label)</label>
              <input value={desc} onChange={e => setDesc(e.target.value)} className="w-full h-9 text-sm border border-slate-200 rounded-lg px-3 bg-white" />
            </div>
            <button onClick={saveLabels} disabled={saving} className="text-xs bg-slate-900 text-white px-3 py-1.5 rounded-lg hover:bg-slate-700 disabled:opacity-50 transition-colors">
              {saving ? "Saving…" : "Save Labels"}
            </button>
          </div>
          {credItems.length > 0 && (
            <div className="p-4 border-t border-slate-100 space-y-1">
              <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-widest mb-2">Credentials & Config</p>
              {credItems.map((item: any) => <SettingRow key={item.key} item={item} onSaved={onSaved} />)}
            </div>
          )}
          {feeRateItem && (
            <div className="p-4 border-t border-slate-100">
              <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-widest mb-2">Fee Rate</p>
              <SettingRow item={feeRateItem} onSaved={onSaved} />
            </div>
          )}
          {onCallbackSettings && (
            <div className="p-4 border-t border-slate-100 flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-700">Callback Page Text</p>
                <p className="text-[11px] text-slate-400 mt-0.5">Processing, success &amp; error messages shown during direct debit setup</p>
              </div>
              <button onClick={onCallbackSettings} className="flex items-center gap-1.5 text-xs text-slate-600 border border-slate-200 rounded-lg px-3 py-1.5 hover:bg-slate-100 transition-colors" data-testid="gc-callback-edit-btn">
                <Pencil size={11} /> Edit
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Auth SlideOver titles & descriptions ─────────────────────────────────────

function getAuthSlideTitle(key: AuthSlide | null): string {
  const map: Record<AuthSlide, string> = {
    login: "Login Page", signup: "Sign Up Page", verify_email: "Verify Email Page",
    portal: "Customer Portal", profile: "Profile Page",
    not_found: "404 Not Found Page",
    checkout_builder: "Checkout Page Builder", checkout_success: "Checkout Success",
    gocardless_callback: "GoCardless Callback Page",
    checkout_messages: "Checkout Messages", form_messages: "Form Response Messages",
    footer_basics: "Footer Text", footer_about: "About Us Section",
    footer_nav: "Navigation", footer_contact: "Contact Info", footer_social: "Social Media",
  };
  return key ? map[key] : "";
}

function getAuthSlideDesc(key: AuthSlide | null): string {
  const map: Record<AuthSlide, string> = {
    login: "Text shown on the login page.", signup: "Text + custom fields on the registration page.",
    verify_email: "Text shown when customers verify their email.", portal: "Heading and subtitle on the customer portal.",
    profile: "Heading and subtitle on the profile page.", not_found: "Content for the 404 error page.",
    checkout_builder: "Build and configure checkout sections. Includes cart page settings.",
    checkout_success: "Success page content for Stripe and bank transfer payments.",
    gocardless_callback: "Processing, success, and error page text shown during GoCardless direct debit setup.",
    checkout_messages: "Customer-facing error and instruction messages during checkout.",
    form_messages: "Success messages shown after quote / scope requests.",
    footer_basics: "Tagline and copyright text shown in the footer.",
    footer_about: "About us section heading and descriptive text.",
    footer_nav: "Navigation section title and link labels.",
    footer_contact: "Contact details shown in the footer.",
    footer_social: "Social media platform links.",
  };
  return key ? map[key] : "";
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
  const [slideSaving, setSlideSaving] = useState(false);
  const [authSlide, setAuthSlide] = useState<AuthSlide | null>(null);
  const [formSlide, setFormSlide] = useState<"quote" | "scope" | "bank_transaction" | null>(null);
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
    } catch { toast.error("Failed to load settings"); }
    finally { setLoading(false); }
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
    } catch { toast.error("Failed to save settings"); }
    finally { setSaving(false); }
  };

  const saveSection = async (onDone?: () => void) => {
    setSlideSaving(true);
    try {
      await api.put("/admin/website-settings", ws);
      toast.success("Saved");
      onDone?.();
    } catch { toast.error("Save failed"); }
    finally { setSlideSaving(false); }
  };

  const getFieldCount = (schema: string): number => {
    try { return JSON.parse(schema || "[]").length; } catch { return 0; }
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

        {/* Content panel */}
        <div className="flex-1 min-w-0 border border-slate-100 rounded-xl p-6 bg-white space-y-5">

          {/* ── Branding & Hero ── */}
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
                <p className="text-xs text-slate-400 mb-3">Primary = navbars. Accent = CTA buttons.</p>
                <div className="grid grid-cols-2 gap-4">
                  <ColorInput label="Primary" value={branding.primary_color} onChange={b("primary_color")} testId="ws-primary-color" />
                  <ColorInput label="Accent" value={branding.accent_color} onChange={b("accent_color")} testId="ws-accent-color" />
                </div>
              </div>
              <div className="border-t border-slate-100 pt-4">
                <h3 className="text-sm font-semibold text-slate-700 mb-3">Store Hero Banner</h3>
                <div className="space-y-3">
                  <Field label="Label" value={ws.hero_label} onChange={s("hero_label")} testId="ws-hero-label" />
                  <Field label="Title" value={ws.hero_title} onChange={s("hero_title")} multiline testId="ws-hero-title" />
                  <Field label="Subtitle" value={ws.hero_subtitle} onChange={s("hero_subtitle")} multiline testId="ws-hero-subtitle" />
                </div>
              </div>
              <div className="border-t border-slate-100 pt-4">
                <h3 className="text-sm font-semibold text-slate-700 mb-3">Articles Hero Banner</h3>
                <div className="space-y-3">
                  <Field label="Label" value={ws.articles_hero_label} onChange={s("articles_hero_label")} testId="ws-articles-hero-label" />
                  <Field label="Title" value={ws.articles_hero_title} onChange={s("articles_hero_title")} testId="ws-articles-hero-title" />
                  <Field label="Subtitle" value={ws.articles_hero_subtitle} onChange={s("articles_hero_subtitle")} multiline testId="ws-articles-hero-subtitle" />
                </div>
              </div>
            </>
          )}

          {/* ── Auth & Pages ── */}
          {activeSection === "auth" && (
            <>
              <div className="mb-2">
                <h3 className="text-sm font-semibold text-slate-700">Auth & Pages</h3>
                <p className="text-xs text-slate-400 mt-0.5">Click any tile to edit text, forms, or page content.</p>
              </div>

              <SectionDivider label="Authentication" />
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <AuthTile title="Login Page" description="Login title, subtitle, portal label" preview={ws.login_title || undefined} onEdit={() => setAuthSlide("login")} testId="auth-tile-login" />
                <AuthTile title="Sign Up Page" description={`Register page + ${getFieldCount(ws.signup_form_schema)} form fields`} preview={ws.register_title || undefined} onEdit={() => setAuthSlide("signup")} testId="auth-tile-signup" />
                <AuthTile title="Verify Email" description="Verification page content" preview={ws.verify_email_title || undefined} onEdit={() => setAuthSlide("verify_email")} testId="auth-tile-verify-email" />
              </div>

              <SectionDivider label="App Pages" />
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <AuthTile title="Customer Portal" preview={ws.portal_title || undefined} description="Portal heading & subtitle" onEdit={() => setAuthSlide("portal")} testId="auth-tile-portal" />
                <AuthTile title="Profile Page" preview={ws.profile_title || undefined} description="Profile heading & subtitle" onEdit={() => setAuthSlide("profile")} testId="auth-tile-profile" />
                <AuthTile title="404 Not Found" preview={ws.page_404_title || undefined} description="Error page content" onEdit={() => setAuthSlide("not_found")} testId="auth-tile-404" />
              </div>

              <SectionDivider label="Checkout Flow" />
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <AuthTile title="Checkout Page Builder" description="Dynamic sections + cart page settings" onEdit={() => setAuthSlide("checkout_builder")} testId="auth-tile-checkout-builder" />
                <AuthTile title="Checkout Success" preview={ws.checkout_success_title || undefined} description="Page after successful payment or bank transfer" onEdit={() => setAuthSlide("checkout_success")} testId="auth-tile-checkout-success" />
              </div>

              <SectionDivider label="Messages" />
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <AuthTile title="Checkout Messages" description="Cart, payment errors & override prompts" onEdit={() => setAuthSlide("checkout_messages")} testId="auth-tile-checkout-messages" />
                <AuthTile title="Form Responses" description="Quote & scope success messages" onEdit={() => setAuthSlide("form_messages")} testId="auth-tile-form-messages" />
              </div>
            </>
          )}

          {/* ── Forms ── */}
          {activeSection === "forms" && (
            <>
              <h3 className="text-sm font-semibold text-slate-700 mb-1">Forms</h3>
              <p className="text-xs text-slate-400 mb-4">Click to edit form text labels and custom fields.</p>
              <div className="space-y-3">
                <FormTile title="Quote Request Form" description="Shown when a customer requests a quote" fieldCount={getFieldCount(ws.quote_form_schema)} onEdit={() => setFormSlide("quote")} testId="form-tile-quote" />
                <FormTile title="Scope Request Form" description="Shown for fixed-scope / RFQ products" fieldCount={getFieldCount(ws.scope_form_schema)} onEdit={() => setFormSlide("scope")} testId="form-tile-scope" />
              </div>
              <p className="text-xs text-slate-400 mt-3">The customer Sign-up form is managed in <button onClick={() => setActiveSection("auth")} className="text-slate-600 underline">Auth &amp; Pages → Sign Up</button>.</p>
            </>
          )}

          {/* ── Email Templates ── */}
          {activeSection === "email" && <EmailSection />}

          {/* ── Footer & Nav ── */}
          {activeSection === "footer" && (
            <>
              <h3 className="text-sm font-semibold text-slate-700 mb-1">Footer & Navigation</h3>
              <p className="text-xs text-slate-400 mb-4">Click any tile to edit footer content and navigation settings.</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <AuthTile title="Footer Text" description="Tagline and copyright" preview={ws.footer_tagline || ws.footer_copyright || undefined} onEdit={() => setAuthSlide("footer_basics")} testId="footer-tile-basics" />
                <AuthTile title="About Us" description="About section heading and text" preview={ws.footer_about_title || undefined} onEdit={() => setAuthSlide("footer_about")} testId="footer-tile-about" />
                <AuthTile title="Navigation" description="Nav section title and link labels" preview={ws.footer_nav_title || undefined} onEdit={() => setAuthSlide("footer_nav")} testId="footer-tile-nav" />
                <AuthTile title="Contact Info" description="Email, phone, and address" preview={ws.contact_email || undefined} onEdit={() => setAuthSlide("footer_contact")} testId="footer-tile-contact" />
                <AuthTile title="Social Media" description="Social network links" preview={ws.footer_social_title || undefined} onEdit={() => setAuthSlide("footer_social")} testId="footer-tile-social" />
              </div>
            </>
          )}

          {/* ── References ── */}
          {activeSection === "references" && (
            <>
              <p className="text-xs text-slate-500 mb-4">
                References are key-value pairs used across your app. Use <code className="font-mono bg-slate-100 px-1 rounded">{"{{ref:key}}"}</code> to reference them in content fields.
              </p>
              <ReferencesSection />
            </>
          )}

          {/* ── Payments ── */}
          {activeSection === "payments" && (
            <>
              <div className="flex items-center justify-between mb-1">
                <h3 className="text-sm font-semibold text-slate-700">Payment Integrations</h3>
              </div>
              <p className="text-xs text-slate-400 mb-4">Enabled providers appear in the Customers module for per-customer assignment.</p>
              <PaymentProviderCard
                title="GoCardless" subtitle="Direct Debit / Bank Transfer"
                enabledItem={(structured["Payments"] || []).find((i: any) => i.key === "gocardless_enabled")}
                displayLabelKey="payment_gocardless_label" displayDescKey="payment_gocardless_description"
                initialLabel={ws.payment_gocardless_label} initialDesc={ws.payment_gocardless_description}
                credItems={(structured["Payments"] || []).filter((i: any) => i.key.startsWith("gocardless") && i.key !== "gocardless_enabled" && i.key !== "gocardless_fee_rate")}
                feeRateItem={(structured["Payments"] || []).find((i: any) => i.key === "gocardless_fee_rate") || null}
                onSaved={onStructuredSaved}
                onCallbackSettings={() => setAuthSlide("gocardless_callback")}
              />
              <PaymentProviderCard
                title="Stripe" subtitle="Credit / Debit Card"
                enabledItem={(structured["Payments"] || []).find((i: any) => i.key === "stripe_enabled")}
                displayLabelKey="payment_stripe_label" displayDescKey="payment_stripe_description"
                initialLabel={ws.payment_stripe_label} initialDesc={ws.payment_stripe_description}
                credItems={(structured["Payments"] || []).filter((i: any) => i.key.startsWith("stripe") && i.key !== "stripe_enabled" && i.key !== "stripe_fee_rate" && i.key !== "service_fee_rate")}
                feeRateItem={(structured["Payments"] || []).find((i: any) => i.key === "stripe_fee_rate") || null}
                onSaved={onStructuredSaved}
              />
            </>
          )}

          {/* ── System Config ── */}
          {activeSection === "sysconfig" && (
            <>
              <h3 className="text-sm font-semibold text-slate-700 mb-1">System Configuration</h3>
              <p className="text-xs text-slate-400 mb-4">Click any value to edit inline.</p>

              {/* Override Codes sub-section */}
              {(() => {
                const items = structured["OverrideCodes"] || [];
                if (!items.length) return null;
                return (
                  <div className="rounded-xl border border-slate-200 bg-white p-5 mb-4">
                    <h4 className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-1">Override Codes</h4>
                    <p className="text-xs text-slate-400 mb-3">Settings for the override code system used in the checkout flow.</p>
                    {items.map((item: any) => <SettingRow key={item.key} item={item} onSaved={onStructuredSaved} />)}
                  </div>
                );
              })()}

              {["Operations"].map(cat => {
                const items = (structured[cat] || []);
                if (!items.length) return null;
                return (
                  <div key={cat} className="rounded-xl border border-slate-200 bg-white p-5 mb-4">
                    <h4 className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-3">{cat}</h4>
                    {items.map((item: any) => <SettingRow key={item.key} item={item} onSaved={onStructuredSaved} />)}
                  </div>
                );
              })}

              {/* FeatureFlags remaining items */}
              {(() => {
                const items = (structured["FeatureFlags"] || []);
                if (!items.length) return null;
                return (
                  <div className="rounded-xl border border-slate-200 bg-white p-5 mb-4">
                    <h4 className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-3">Feature Flags</h4>
                    {items.map((item: any) => <SettingRow key={item.key} item={item} onSaved={onStructuredSaved} />)}
                  </div>
                );
              })()}
            </>
          )}
        </div>
      </div>

      {/* ── Auth & Pages SlideOver ── */}
      <SlideOver
        open={authSlide !== null}
        onClose={() => setAuthSlide(null)}
        title={getAuthSlideTitle(authSlide)}
        description={getAuthSlideDesc(authSlide)}
        onSave={() => saveSection(() => setAuthSlide(null))}
        saving={slideSaving}
      >
        {/* Login */}
        {authSlide === "login" && (
          <div className="space-y-4">
            <Field label="Portal label" hint='Small label above title (e.g. "Customer Portal")' value={ws.login_portal_label} onChange={s("login_portal_label")} testId="ws-login-portal" />
            <Field label="Title" value={ws.login_title} onChange={s("login_title")} testId="ws-login-title" />
            <Field label="Subtitle" value={ws.login_subtitle} onChange={s("login_subtitle")} testId="ws-login-subtitle" />
          </div>
        )}

        {/* Sign Up */}
        {authSlide === "signup" && (
          <div className="space-y-4">
            <Field label="Page title" value={ws.register_title} onChange={s("register_title")} testId="ws-register-title" />
            <Field label="Page subtitle" value={ws.register_subtitle} onChange={s("register_subtitle")} multiline testId="ws-register-subtitle" />
            <Field label="Form title" value={ws.signup_form_title} onChange={s("signup_form_title")} testId="ws-signup-title" />
            <Field label="Form subtitle" value={ws.signup_form_subtitle} onChange={s("signup_form_subtitle")} multiline testId="ws-signup-subtitle" />
            <div className="border-t border-slate-100 pt-3">
              <FormSchemaBuilder title="Registration form fields" value={ws.signup_form_schema} onChange={s("signup_form_schema")} />
            </div>
          </div>
        )}

        {/* Verify Email */}
        {authSlide === "verify_email" && (
          <div className="space-y-4">
            <Field label="Step label" value={ws.verify_email_label} onChange={s("verify_email_label")} testId="ws-ve-label" />
            <Field label="Title" value={ws.verify_email_title} onChange={s("verify_email_title")} testId="ws-ve-title" />
            <Field label="Subtitle / instructions" value={ws.verify_email_subtitle} onChange={s("verify_email_subtitle")} multiline testId="ws-ve-subtitle" />
          </div>
        )}

        {/* Customer Portal */}
        {authSlide === "portal" && (
          <div className="space-y-4">
            <Field label="Page title" value={ws.portal_title} onChange={s("portal_title")} testId="ws-portal-title" />
            <Field label="Page subtitle" value={ws.portal_subtitle} onChange={s("portal_subtitle")} multiline testId="ws-portal-subtitle" />
          </div>
        )}

        {/* Profile */}
        {authSlide === "profile" && (
          <div className="space-y-4">
            <Field label="Breadcrumb label" value={ws.profile_label} onChange={s("profile_label")} testId="ws-profile-label" />
            <Field label="Page title" value={ws.profile_title} onChange={s("profile_title")} testId="ws-profile-title" />
            <Field label="Page subtitle" value={ws.profile_subtitle} onChange={s("profile_subtitle")} multiline testId="ws-profile-subtitle" />
          </div>
        )}

        {/* 404 */}
        {authSlide === "not_found" && (
          <div className="space-y-4">
            <Field label="Heading" value={ws.page_404_title} onChange={s("page_404_title")} testId="ws-404-title" />
            <Field label="Back link text" value={ws.page_404_link_text} onChange={s("page_404_link_text")} testId="ws-404-link" />
          </div>
        )}

        {/* Checkout Builder */}
        {authSlide === "checkout_builder" && (
          <div className="space-y-5">
            <div>
              <p className="text-xs font-semibold text-slate-600 uppercase tracking-wider mb-2">Dynamic Sections</p>
              <p className="text-xs text-slate-400 mb-3">Build custom sections for the checkout page. The pre-loaded Zoho and Partner sections can be edited or replaced here.</p>
              <CheckoutSectionsBuilder value={ws.checkout_sections} onChange={s("checkout_sections")} />
            </div>

            <div className="border-t border-slate-100 pt-4">
              <p className="text-xs font-semibold text-slate-600 uppercase tracking-wider mb-3">Cart Page</p>
              <div className="space-y-3">
                <Field label="Cart heading" value={ws.cart_title} onChange={s("cart_title")} testId="ws-cart-title" />
                <Field label="Clear cart button text" value={ws.cart_clear_btn_text} onChange={s("cart_clear_btn_text")} testId="ws-cart-clear-btn" />
              </div>
            </div>
          </div>
        )}

        {/* Checkout Success (includes Bank Transfer + GoCardless) */}
        {authSlide === "checkout_success" && (
          <div className="space-y-4">
            <Field label="Page heading" value={ws.checkout_success_title} onChange={s("checkout_success_title")} testId="ws-cs-title" />
            <Field label="Payment successful message" value={ws.checkout_success_paid_msg} onChange={s("checkout_success_paid_msg")} testId="ws-cs-paid" />
            <Field label="Checking status message" value={ws.checkout_success_pending_msg} onChange={s("checkout_success_pending_msg")} testId="ws-cs-pending" />
            <Field label="Session expired message" value={ws.checkout_success_expired_msg} onChange={s("checkout_success_expired_msg")} testId="ws-cs-expired" />
            <Field label="Next steps heading" value={ws.checkout_success_next_steps_title} onChange={s("checkout_success_next_steps_title")} testId="ws-cs-next-title" />
            <Field label="Step 1" value={ws.checkout_success_step_1} onChange={s("checkout_success_step_1")} testId="ws-cs-step1" />
            <Field label="Step 2" value={ws.checkout_success_step_2} onChange={s("checkout_success_step_2")} testId="ws-cs-step2" />
            <Field label="Step 3" value={ws.checkout_success_step_3} onChange={s("checkout_success_step_3")} testId="ws-cs-step3" />
            <Field label="Portal link text" value={ws.checkout_portal_link_text} onChange={s("checkout_portal_link_text")} testId="ws-cs-portal-link" />
            <div className="border-t border-slate-100 pt-4">
              <p className="text-xs font-semibold text-slate-600 uppercase tracking-wider mb-3">Bank Transfer Order Confirmation</p>
              <div className="space-y-3">
                <Field label="Page heading" value={ws.bank_success_title} onChange={s("bank_success_title")} testId="ws-bt-title" />
                <Field label="Intro message" value={ws.bank_success_message} onChange={s("bank_success_message")} multiline testId="ws-bt-message" />
                <Field label="Instructions heading" value={ws.bank_instructions_title} onChange={s("bank_instructions_title")} testId="ws-bt-instr-title" />
                <Field label="Instruction 1" value={ws.bank_instruction_1} onChange={s("bank_instruction_1")} testId="ws-bt-i1" />
                <Field label="Instruction 2" value={ws.bank_instruction_2} onChange={s("bank_instruction_2")} testId="ws-bt-i2" />
                <Field label="Instruction 3" value={ws.bank_instruction_3} onChange={s("bank_instruction_3")} testId="ws-bt-i3" />
                <Field label="Next steps heading" value={ws.bank_next_steps_title} onChange={s("bank_next_steps_title")} testId="ws-bt-next-title" />
                <Field label="Next step 1" value={ws.bank_next_step_1} onChange={s("bank_next_step_1")} testId="ws-bt-ns1" />
                <Field label="Next step 2" value={ws.bank_next_step_2} onChange={s("bank_next_step_2")} testId="ws-bt-ns2" />
                <Field label="Next step 3" value={ws.bank_next_step_3} onChange={s("bank_next_step_3")} testId="ws-bt-ns3" />
              </div>
            </div>
          </div>
        )}

        {/* GoCardless Callback Page */}
        {authSlide === "gocardless_callback" && (
          <div className="space-y-4">
            <Field label="Processing title" value={ws.gocardless_processing_title} onChange={s("gocardless_processing_title")} testId="ws-gc-proc-title" />
            <Field label="Processing subtitle" value={ws.gocardless_processing_subtitle} onChange={s("gocardless_processing_subtitle")} testId="ws-gc-proc-sub" />
            <Field label="Success title" value={ws.gocardless_success_title} onChange={s("gocardless_success_title")} testId="ws-gc-succ-title" />
            <Field label="Success message" value={ws.gocardless_success_message} onChange={s("gocardless_success_message")} multiline testId="ws-gc-succ-msg" />
            <Field label="Error title" value={ws.gocardless_error_title} onChange={s("gocardless_error_title")} testId="ws-gc-err-title" />
            <Field label="Error message" value={ws.gocardless_error_message} onChange={s("gocardless_error_message")} multiline testId="ws-gc-err-msg" />
            <Field label="Return button text" value={ws.gocardless_return_btn_text} onChange={s("gocardless_return_btn_text")} testId="ws-gc-return-btn" />
          </div>
        )}

        {/* Checkout Messages */}
        {authSlide === "checkout_messages" && (
          <div className="space-y-4">
            <Field label="Partner tagging prompt" hint="Shown at checkout when partner status not selected" value={ws.msg_partner_tagging_prompt} onChange={s("msg_partner_tagging_prompt")} multiline testId="ws-msg-partner" />
            <Field label="Override code required message" hint="Shown when customer hasn't tagged you as partner" value={ws.msg_override_required} onChange={s("msg_override_required")} multiline testId="ws-msg-override" />
            <Field label="Cart empty message" value={ws.msg_cart_empty} onChange={s("msg_cart_empty")} testId="ws-msg-cart-empty" />
            <Field label="Currency unsupported message" value={ws.msg_currency_unsupported} onChange={s("msg_currency_unsupported")} multiline testId="ws-msg-currency" />
            <Field label="No payment methods message" value={ws.msg_no_payment_methods} onChange={s("msg_no_payment_methods")} multiline testId="ws-msg-no-payment" />
          </div>
        )}

        {/* Form Messages */}
        {authSlide === "form_messages" && (
          <div className="space-y-4">
            <Field label="Quote request success" hint="Shown after submitting a quote request" value={ws.msg_quote_success} onChange={s("msg_quote_success")} testId="ws-msg-quote-success" />
            <Field label="Scope request success" hint="Shown after submitting a scope request" value={ws.msg_scope_success} onChange={s("msg_scope_success")} testId="ws-msg-scope-success" />
          </div>
        )}

        {/* Footer Basics */}
        {authSlide === "footer_basics" && (
          <div className="space-y-4">
            <Field label="Tagline" hint="Short line shown under your brand name" value={ws.footer_tagline} onChange={s("footer_tagline")} testId="ws-footer-tagline" />
            <Field label="Copyright text" hint='e.g. "© 2025 Acme Inc."' value={ws.footer_copyright} onChange={s("footer_copyright")} testId="ws-footer-copyright" />
          </div>
        )}

        {/* Footer About */}
        {authSlide === "footer_about" && (
          <div className="space-y-4">
            <Field label="Section title" hint='Shown as heading (e.g. "About Us")' value={ws.footer_about_title} onChange={s("footer_about_title")} placeholder="About Us" testId="ws-footer-about-title" />
            <Field label="About us text" value={ws.footer_about_text} onChange={s("footer_about_text")} multiline testId="ws-footer-about-text" />
          </div>
        )}

        {/* Footer Nav */}
        {authSlide === "footer_nav" && (
          <div className="space-y-4">
            <Field label="Navigation section title" value={ws.footer_nav_title} onChange={s("footer_nav_title")} placeholder="Navigation" testId="ws-footer-nav-title" />
            <div className="grid grid-cols-3 gap-3">
              <Field label="Store label" value={ws.nav_store_label} onChange={s("nav_store_label")} testId="ws-nav-store" />
              <Field label="Articles label" value={ws.nav_articles_label} onChange={s("nav_articles_label")} testId="ws-nav-articles" />
              <Field label="Portal label" value={ws.nav_portal_label} onChange={s("nav_portal_label")} testId="ws-nav-portal" />
            </div>
          </div>
        )}

        {/* Footer Contact */}
        {authSlide === "footer_contact" && (
          <div className="space-y-4">
            <Field label="Contact section title" value={ws.footer_contact_title} onChange={s("footer_contact_title")} placeholder="Contact" testId="ws-footer-contact-title" />
            <Field label="Email" value={ws.contact_email} onChange={s("contact_email")} testId="ws-contact-email" />
            <Field label="Phone" value={ws.contact_phone} onChange={s("contact_phone")} testId="ws-contact-phone" />
            <Field label="Address" value={ws.contact_address} onChange={s("contact_address")} multiline testId="ws-contact-address" />
          </div>
        )}

        {/* Footer Social */}
        {authSlide === "footer_social" && (
          <div className="space-y-4">
            <Field label="Section title" value={ws.footer_social_title} onChange={s("footer_social_title")} placeholder="Follow Us" testId="ws-footer-social-title" />
            <div className="space-y-3">
              <Field label="X / Twitter URL" value={ws.social_twitter} onChange={s("social_twitter")} placeholder="https://x.com/yourhandle" testId="ws-social-twitter" />
              <Field label="LinkedIn URL" value={ws.social_linkedin} onChange={s("social_linkedin")} placeholder="https://linkedin.com/company/..." testId="ws-social-linkedin" />
              <Field label="Facebook URL" value={ws.social_facebook} onChange={s("social_facebook")} placeholder="https://facebook.com/..." testId="ws-social-facebook" />
              <Field label="Instagram URL" value={ws.social_instagram} onChange={s("social_instagram")} placeholder="https://instagram.com/..." testId="ws-social-instagram" />
              <Field label="YouTube URL" value={ws.social_youtube} onChange={s("social_youtube")} placeholder="https://youtube.com/@..." testId="ws-social-youtube" />
            </div>
          </div>
        )}
      </SlideOver>

      {/* ── Forms SlideOver ── */}
      <SlideOver
        open={formSlide !== null}
        onClose={() => setFormSlide(null)}
        title={formSlide === "quote" ? "Quote Request Form" : "Scope Request Form"}
        description={formSlide === "quote" ? "Shown when a customer requests a quote on a product." : "Shown for fixed-scope / RFQ products."}
        onSave={() => saveSection(() => setFormSlide(null))}
        saving={slideSaving}
      >
        {formSlide === "quote" && (
          <div className="space-y-4">
            <Field label="Form title" value={ws.quote_form_title} onChange={s("quote_form_title")} testId="ws-quote-title" />
            <Field label="Subtitle" value={ws.quote_form_subtitle} onChange={s("quote_form_subtitle")} multiline testId="ws-quote-subtitle" />
            <Field label="Response time message" hint='Shown at the bottom of the form.' value={ws.quote_form_response_time} onChange={s("quote_form_response_time")} testId="ws-quote-response" />
            <div className="border-t border-slate-100 pt-3">
              <FormSchemaBuilder title="Form fields" value={ws.quote_form_schema} onChange={s("quote_form_schema")} />
            </div>
          </div>
        )}
        {formSlide === "scope" && (
          <div className="space-y-4">
            <Field label="Form title" value={ws.scope_form_title} onChange={s("scope_form_title")} testId="ws-scope-title" />
            <Field label="Subtitle" value={ws.scope_form_subtitle} onChange={s("scope_form_subtitle")} multiline testId="ws-scope-subtitle" />
            <div className="border-t border-slate-100 pt-3">
              <FormSchemaBuilder title="Form fields" value={ws.scope_form_schema} onChange={s("scope_form_schema")} />
            </div>
          </div>
        )}
      </SlideOver>
    </div>
  );
}
