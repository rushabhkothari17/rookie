import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/sonner";
import { ChevronDown, ChevronUp, Eye, EyeOff, Pencil, Plus, Save, Upload, X } from "lucide-react";
import api from "@/lib/api";
import FormSchemaBuilder from "@/components/FormSchemaBuilder";
import ReferencesSection from "./ReferencesSection";
import EmailSection from "./EmailSection";

// ─── Types ───────────────────────────────────────────────────────────────────

type Section =
  | "branding" | "hero" | "auth" | "forms" | "checkout" | "email" | "errors"
  | "footer" | "references" | "payments" | "sysconfig" | "pages";

interface CheckoutSection {
  id: string;
  title: string;
  description: string;
  enabled: boolean;
  order: number;
  fields_schema: string;
}

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
  // Payment display
  payment_gocardless_label: string; payment_gocardless_description: string;
  payment_stripe_label: string; payment_stripe_description: string;
  // Checkout legacy fields
  checkout_zoho_enabled: boolean; checkout_zoho_title: string;
  checkout_zoho_subscription_options: string; checkout_zoho_product_options: string;
  checkout_zoho_signup_note: string; checkout_zoho_access_note: string;
  checkout_zoho_access_delay_warning: string;
  checkout_partner_enabled: boolean; checkout_partner_title: string;
  checkout_partner_description: string; checkout_partner_options: string;
  checkout_partner_misrep_warning: string; checkout_extra_schema: string;
  // Dynamic checkout sections
  checkout_sections: string;
  // Page content strings
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
  msg_currency_unsupported: string; msg_no_payment_methods: string;
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
  // Page content
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
  msg_currency_unsupported: "", msg_no_payment_methods: "",
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
      { key: "checkout", label: "Checkout" },
      { key: "email", label: "Email Templates" },
      { key: "errors", label: "Error Messages" },
      { key: "footer", label: "Footer & Nav" },
      { key: "pages", label: "Page Content" },
    ],
  },
  {
    group: "Configuration",
    items: [
      { key: "references", label: "References" },
      { key: "payments", label: "Payments" },
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

// ─── Checkout Section Builder ──────────────────────────────────────────────

function makeCSId() { return "cs_" + Math.random().toString(36).slice(2, 8); }

function CheckoutSectionsList({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [sections, setSections] = useState<CheckoutSection[]>(() => {
    try { const p = JSON.parse(value); return Array.isArray(p) ? p : []; } catch { return []; }
  });
  const [editingId, setEditingId] = useState<string | null>(null);

  const commit = (updated: CheckoutSection[]) => {
    const reordered = updated.map((s, i) => ({ ...s, order: i }));
    setSections(reordered);
    onChange(JSON.stringify(reordered));
  };

  const add = () => {
    const id = makeCSId();
    const newSection: CheckoutSection = { id, title: "New Section", description: "", enabled: true, order: sections.length, fields_schema: "[]" };
    const updated = [...sections, newSection];
    commit(updated);
    setEditingId(id);
  };

  const remove = (id: string) => {
    commit(sections.filter(s => s.id !== id));
    if (editingId === id) setEditingId(null);
  };

  const update = (id: string, patch: Partial<CheckoutSection>) => {
    commit(sections.map(s => s.id === id ? { ...s, ...patch } : s));
  };

  const move = (id: string, dir: -1 | 1) => {
    const idx = sections.findIndex(s => s.id === id);
    if (idx < 0) return;
    const next = idx + dir;
    if (next < 0 || next >= sections.length) return;
    const arr = [...sections];
    [arr[idx], arr[next]] = [arr[next], arr[idx]];
    commit(arr);
  };

  return (
    <div className="space-y-2" data-testid="checkout-sections-builder">
      {sections.length === 0 && (
        <p className="text-xs text-slate-400 text-center py-6 border border-dashed border-slate-200 rounded-lg">
          No custom sections yet. Add your first section below.
          <br /><span className="text-slate-300">Legacy sections (Zoho/Partner) remain active until you add sections here.</span>
        </p>
      )}
      {sections.map((section, idx) => (
        <div key={section.id} className="rounded-xl border border-slate-200 bg-white overflow-hidden" data-testid={`checkout-section-card-${section.id}`}>
          <div className="flex items-center justify-between px-4 py-3">
            <div className="flex items-center gap-3 min-w-0">
              <div className={`h-2 w-2 rounded-full flex-shrink-0 ${section.enabled ? "bg-green-500" : "bg-slate-300"}`} />
              <div className="min-w-0">
                <p className="text-sm font-medium text-slate-800 truncate">{section.title || "Untitled"}</p>
                {section.description && <p className="text-xs text-slate-400 truncate max-w-xs">{section.description}</p>}
              </div>
            </div>
            <div className="flex items-center gap-1.5 shrink-0">
              <button onClick={() => update(section.id, { enabled: !section.enabled })}
                className={`px-2.5 py-1 text-xs font-medium rounded-full transition-all border ${section.enabled ? "bg-green-50 text-green-700 border-green-200" : "bg-slate-100 text-slate-500 border-slate-200"}`}
                data-testid={`checkout-section-toggle-${section.id}`}>
                {section.enabled ? "Visible" : "Hidden"}
              </button>
              <button onClick={() => move(section.id, -1)} disabled={idx === 0} className="p-1 text-slate-400 hover:text-slate-600 disabled:opacity-30"><ChevronUp size={14} /></button>
              <button onClick={() => move(section.id, 1)} disabled={idx === sections.length - 1} className="p-1 text-slate-400 hover:text-slate-600 disabled:opacity-30"><ChevronDown size={14} /></button>
              <button onClick={() => setEditingId(editingId === section.id ? null : section.id)}
                className={`p-1.5 rounded-lg transition-colors ${editingId === section.id ? "bg-slate-900 text-white" : "text-slate-400 hover:text-slate-700 hover:bg-slate-100"}`}
                data-testid={`checkout-section-edit-${section.id}`}>
                <Pencil size={13} />
              </button>
              <button onClick={() => remove(section.id)} className="p-1.5 rounded-lg text-red-400 hover:text-red-600 hover:bg-red-50 transition-colors" data-testid={`checkout-section-remove-${section.id}`}>
                <X size={13} />
              </button>
            </div>
          </div>
          {editingId === section.id && (
            <div className="border-t border-slate-100 p-4 space-y-4 bg-slate-50">
              <div className="space-y-3">
                <div>
                  <label className="text-xs text-slate-500 block mb-1">Section Title</label>
                  <input value={section.title} onChange={e => update(section.id, { title: e.target.value })}
                    className="w-full h-9 text-sm border border-slate-200 rounded-lg px-3 bg-white" placeholder="e.g. Account Details"
                    data-testid={`checkout-section-title-input-${section.id}`} />
                </div>
                <div>
                  <label className="text-xs text-slate-500 block mb-1">Description <span className="text-slate-400">(shown to customers above the fields)</span></label>
                  <textarea value={section.description} onChange={e => update(section.id, { description: e.target.value })}
                    className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 bg-white resize-none" rows={2}
                    placeholder="Optional description shown above the form fields"
                    data-testid={`checkout-section-desc-input-${section.id}`} />
                </div>
              </div>
              <div className="border-t border-slate-100 pt-4">
                <FormSchemaBuilder title="Section Fields" value={section.fields_schema} onChange={v => update(section.id, { fields_schema: v })} />
              </div>
            </div>
          )}
        </div>
      ))}
      <button onClick={add} className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-700 font-medium px-3 py-2 rounded-lg hover:bg-blue-50 transition-colors mt-1"
        data-testid="add-checkout-section-btn">
        <Plus size={14} /> Add Section
      </button>
    </div>
  );
}

// Reusable setting row for DB-backed structured settings
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

// ─── Payment Provider Card ──────────────────────────────────────────────────

function PaymentProviderCard({
  title, subtitle, enabledItem, displayLabelKey, displayDescKey,
  initialLabel, initialDesc, credItems, feeRateItem, onSaved,
}: {
  title: string; subtitle: string; enabledItem: any;
  displayLabelKey: string; displayDescKey: string;
  initialLabel: string; initialDesc: string;
  credItems: any[]; feeRateItem: any | null;
  onSaved: (key: string, val: any) => void;
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
            className={`px-3 py-1 text-xs font-medium rounded-full transition-all border disabled:opacity-50 ${
              isEnabled
                ? "bg-green-50 text-green-700 border-green-200 hover:bg-red-50 hover:text-red-700 hover:border-red-200"
                : "bg-slate-100 text-slate-500 border-slate-200 hover:bg-green-50 hover:text-green-700 hover:border-green-200"
            }`} data-testid={`payment-toggle-${enabledItem?.key}`}>
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
              <input value={label} onChange={e => setLabel(e.target.value)}
                placeholder="e.g. Bank Transfer (GoCardless)"
                className="w-full h-9 text-sm border border-slate-200 rounded-lg px-3 bg-white" />
            </div>
            <div>
              <label className="text-xs text-slate-500 block mb-1">Description (shown under label)</label>
              <input value={desc} onChange={e => setDesc(e.target.value)}
                placeholder="Short description"
                className="w-full h-9 text-sm border border-slate-200 rounded-lg px-3 bg-white" />
            </div>
            <button onClick={saveLabels} disabled={saving}
              className="text-xs bg-slate-900 text-white px-3 py-1.5 rounded-lg hover:bg-slate-700 disabled:opacity-50 transition-colors">
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
        </div>
      )}
    </div>
  );
}

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
          {activeSection === "email" && <EmailSection />}
          {/* ── Checkout ── */}
          {activeSection === "checkout" && (
            <>
              <h3 className="text-sm font-semibold text-slate-700 mb-1">Checkout Page Content</h3>
              <p className="text-xs text-slate-400 mb-4">Configure sections and questions shown in the cart/checkout flow.</p>

              {/* Zoho Section */}
              <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4 mb-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="text-sm font-semibold text-slate-900">Zoho Account Details</h4>
                    <p className="text-xs text-slate-400">Section shown before checkout for Zoho account info</p>
                  </div>
                  <button onClick={() => setWs(p => ({...p, checkout_zoho_enabled: !p.checkout_zoho_enabled}))}
                    className={`px-3 py-1 text-xs font-medium rounded-full transition-all border ${
                      ws.checkout_zoho_enabled
                        ? "bg-green-50 text-green-700 border-green-200"
                        : "bg-slate-100 text-slate-500 border-slate-200"
                    }`} data-testid="checkout-zoho-toggle">
                    {ws.checkout_zoho_enabled ? "Visible" : "Hidden"}
                  </button>
                </div>
                <div className="space-y-3 border-t border-slate-100 pt-4">
                  <Field label="Section title" value={ws.checkout_zoho_title} onChange={s("checkout_zoho_title")} testId="ws-zoho-title" />
                  <div>
                    <label className="text-xs text-slate-600 block mb-1">Subscription options <span className="text-slate-400">(one per line)</span></label>
                    <Textarea value={ws.checkout_zoho_subscription_options} onChange={e => s("checkout_zoho_subscription_options")(e.target.value)}
                      className="text-sm min-h-20 font-mono" data-testid="ws-zoho-sub-options" />
                  </div>
                  <div>
                    <label className="text-xs text-slate-600 block mb-1">Product options <span className="text-slate-400">(one per line)</span></label>
                    <Textarea value={ws.checkout_zoho_product_options} onChange={e => s("checkout_zoho_product_options")(e.target.value)}
                      className="text-sm min-h-32 font-mono" data-testid="ws-zoho-product-options" />
                  </div>
                  <Field label="Signup note (shown when 'Not on Zoho')" value={ws.checkout_zoho_signup_note} onChange={s("checkout_zoho_signup_note")} />
                  <Field label="Access instructions note" value={ws.checkout_zoho_access_note} onChange={s("checkout_zoho_access_note")} />
                  <Field label="Access delay warning" value={ws.checkout_zoho_access_delay_warning} onChange={s("checkout_zoho_access_delay_warning")} />
                </div>
              </div>

              {/* Partner Tagging Section */}
              <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4 mb-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="text-sm font-semibold text-slate-900">Partner Tagging</h4>
                    <p className="text-xs text-slate-400">Section for "Have you tagged us as your partner?"</p>
                  </div>
                  <button onClick={() => setWs(p => ({...p, checkout_partner_enabled: !p.checkout_partner_enabled}))}
                    className={`px-3 py-1 text-xs font-medium rounded-full transition-all border ${
                      ws.checkout_partner_enabled
                        ? "bg-green-50 text-green-700 border-green-200"
                        : "bg-slate-100 text-slate-500 border-slate-200"
                    }`} data-testid="checkout-partner-toggle">
                    {ws.checkout_partner_enabled ? "Visible" : "Hidden"}
                  </button>
                </div>
                <div className="space-y-3 border-t border-slate-100 pt-4">
                  <Field label="Section title / question" value={ws.checkout_partner_title} onChange={s("checkout_partner_title")} testId="ws-partner-title" />
                  <div>
                    <label className="text-xs text-slate-600 block mb-1">Description text <span className="text-slate-400">(shown above response options; URLs managed in References)</span></label>
                    <Textarea value={ws.checkout_partner_description} onChange={e => s("checkout_partner_description")(e.target.value)}
                      className="text-sm min-h-16" data-testid="ws-partner-desc" />
                  </div>
                  <div>
                    <label className="text-xs text-slate-600 block mb-1">Response options <span className="text-slate-400">(one per line)</span></label>
                    <Textarea value={ws.checkout_partner_options} onChange={e => s("checkout_partner_options")(e.target.value)}
                      className="text-sm min-h-16 font-mono" data-testid="ws-partner-options" />
                  </div>
                  <Field label="Misrepresentation warning" value={ws.checkout_partner_misrep_warning} onChange={s("checkout_partner_misrep_warning")} />
                </div>
              </div>

              {/* Custom Extra Questions */}
              <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
                <div>
                  <h4 className="text-sm font-semibold text-slate-900">Custom Extra Questions</h4>
                  <p className="text-xs text-slate-400 mt-0.5">Additional questions shown at checkout. Answers are stored with each order.</p>
                </div>
                <div className="border-t border-slate-100 pt-4">
                  <FormSchemaBuilder title="Extra checkout questions" value={ws.checkout_extra_schema} onChange={s("checkout_extra_schema")} />
                </div>
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

          {/* ── References ── */}
          {activeSection === "references" && (
            <>
              {/* Zoho system URLs — moved here from System Config */}
              {(structured["Zoho"] || []).length > 0 && (
                <div className="rounded-xl border border-amber-100 bg-amber-50 p-5 mb-4">
                  <h4 className="text-xs font-semibold text-amber-700 uppercase tracking-wide mb-1">System Links (Zoho)</h4>
                  <p className="text-xs text-amber-600 mb-3">Partner tag and signup URLs used in the checkout flow. Click a value to edit.</p>
                  {(structured["Zoho"] || []).map((item: any) => <SettingRow key={item.key} item={item} onSaved={onStructuredSaved} />)}
                </div>
              )}
              <ReferencesSection />
            </>
          )}

          {/* ── Payments ── */}
          {activeSection === "payments" && (
            <>
              <div className="flex items-center justify-between mb-1">
                <h3 className="text-sm font-semibold text-slate-700">Payment Integrations</h3>
                <p className="text-xs text-slate-400">Enabled providers appear in the Customers module for per-customer assignment.</p>
              </div>
              <PaymentProviderCard
                title="GoCardless" subtitle="Direct Debit / Bank Transfer"
                enabledItem={(structured["Payments"] || []).find((i: any) => i.key === "gocardless_enabled")}
                displayLabelKey="payment_gocardless_label" displayDescKey="payment_gocardless_description"
                initialLabel={ws.payment_gocardless_label} initialDesc={ws.payment_gocardless_description}
                credItems={(structured["Payments"] || []).filter((i: any) =>
                  i.key.startsWith("gocardless") && i.key !== "gocardless_enabled" && i.key !== "gocardless_fee_rate"
                )}
                feeRateItem={(structured["Payments"] || []).find((i: any) => i.key === "gocardless_fee_rate") || null}
                onSaved={onStructuredSaved}
              />
              <PaymentProviderCard
                title="Stripe" subtitle="Credit / Debit Card"
                enabledItem={(structured["Payments"] || []).find((i: any) => i.key === "stripe_enabled")}
                displayLabelKey="payment_stripe_label" displayDescKey="payment_stripe_description"
                initialLabel={ws.payment_stripe_label} initialDesc={ws.payment_stripe_description}
                credItems={(structured["Payments"] || []).filter((i: any) =>
                  i.key.startsWith("stripe") && i.key !== "stripe_enabled" && i.key !== "stripe_fee_rate" && i.key !== "service_fee_rate"
                )}
                feeRateItem={(structured["Payments"] || []).find((i: any) => i.key === "stripe_fee_rate") || null}
                onSaved={onStructuredSaved}
              />
              <p className="text-xs text-slate-400 mt-1">Credentials save immediately. Checkout labels save with the "Save Changes" button above.</p>
            </>
          )}

          {/* ── System Config ── */}
          {activeSection === "sysconfig" && (
            <>
              <h3 className="text-sm font-semibold text-slate-700 mb-1">System Configuration</h3>
              <p className="text-xs text-slate-400 mb-4">Database-backed settings. Click any value to edit. Zoho system links are managed in the References section.</p>
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
            </>
          )}

        </div>
      </div>
    </div>
  );
}
