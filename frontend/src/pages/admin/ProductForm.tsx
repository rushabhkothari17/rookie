import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  CreditCard, ExternalLink, MessageSquare, X, Plus, ChevronUp, ChevronDown, GitBranch,
} from "lucide-react";
import { IntakeSchemaBuilder, IntakeSchemaJson, EMPTY_INTAKE_SCHEMA } from "./IntakeSchemaBuilder";
import { SectionsEditor, CustomSection, DEFAULT_SECTION } from "./SectionsEditor";

// ── Types ──────────────────────────────────────────────────────────────────────

interface FAQ { question: string; answer: string; }

export interface ProductVisCondition {
  field: string;
  operator: string;
  value: string;
}
export interface ProductVisRuleSet {
  logic: "AND" | "OR";
  conditions: ProductVisCondition[];
}

export interface ProductFormData {
  name: string;
  tagline: string;
  card_title: string;
  card_tag: string;
  card_description: string;
  card_bullets: string[];
  description_long: string;
  bullets: string[];
  tag: string;
  category: string;
  faqs: FAQ[];
  terms_id: string;
  base_price: number;
  is_subscription: boolean;
  stripe_price_id: string;
  price_rounding: string;
  pricing_type: string;
  external_url: string;
  is_active: boolean;
  currency: string;
  visible_to_customers: string[];
  restricted_to: string[];
  visibility_conditions: ProductVisRuleSet | null;
  intake_schema_json: IntakeSchemaJson;
  custom_sections: CustomSection[];
  display_layout: string;
}

type TabKey = "general" | "storecard" | "pricing" | "visibility" | "content";

const TABS: { key: TabKey; label: string }[] = [
  { key: "general",    label: "General" },
  { key: "storecard",  label: "Store Card" },
  { key: "pricing",    label: "Pricing" },
  { key: "visibility", label: "Visibility" },
  { key: "content",    label: "Content" },
];

// ── Empty form default ─────────────────────────────────────────────────────────

export const EMPTY_FORM: ProductFormData = {
  name: "", tagline: "",
  card_title: "", card_tag: "", card_description: "", card_bullets: [],
  description_long: "", bullets: [], tag: "", category: "",
  faqs: [], terms_id: "", base_price: 0, is_subscription: false,
  stripe_price_id: "", price_rounding: "", pricing_type: "internal",
  external_url: "", currency: "USD", is_active: true, visible_to_customers: [],
  restricted_to: [], visibility_conditions: null, intake_schema_json: EMPTY_INTAKE_SCHEMA, custom_sections: [],
  display_layout: "standard",
};

// ── Style tokens (light theme — matches admin panel) ───────────────────────────

const labelCls = "text-xs font-semibold text-slate-600 mb-1.5 block uppercase tracking-wide";
const sectionCls = "space-y-4";
const dividerCls = "border-t border-slate-100 pt-5 mt-1";
const cardCls = "rounded-lg border border-slate-200 bg-white p-4 space-y-4";
const MAX_BULLETS = 8;

// ── Toggle ─────────────────────────────────────────────────────────────────────

function Toggle({ checked, onChange, label, note, testId }: {
  checked: boolean; onChange: (v: boolean) => void; label: string; note?: string; testId?: string;
}) {
  return (
    <label className="flex items-center gap-3 cursor-pointer select-none group">
      <span className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${checked ? "bg-[#0f172a]" : "bg-slate-200"}`}>
        <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} className="sr-only" data-testid={testId} />
        <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform ${checked ? "translate-x-4" : "translate-x-1"}`} />
      </span>
      <span className="text-sm text-slate-700 font-medium">
        {label} {note && <span className="text-slate-400 text-xs font-normal">{note}</span>}
      </span>
    </label>
  );
}

// ── BulletsList ────────────────────────────────────────────────────────────────

function BulletsList({ bullets, onChange, placeholder = "Feature or detail" }: {
  bullets: string[]; onChange: (v: string[]) => void; placeholder?: string;
}) {
  const items = bullets.length > 0 ? bullets : [""];
  const update = (i: number, v: string) => { const n = [...items]; n[i] = v; onChange(n.filter(Boolean)); };
  const remove = (i: number) => onChange(items.filter((_, j) => j !== i));
  return (
    <div className="space-y-2">
      <label className={labelCls}>Bullet points <span className="text-slate-400 normal-case font-normal tracking-normal">(what's included)</span></label>
      {items.map((b, i) => (
        <div key={i} className="flex gap-2 items-center">
          <span className="text-slate-300 text-xs mt-0.5 shrink-0">–</span>
          <Input
            value={b}
            onChange={e => update(i, e.target.value)}
            placeholder={placeholder}
            className="flex-1 h-9 text-sm"
            data-testid={`pf-bullet-${i}`}
          />
          {items.length > 1 && (
            <button type="button" onClick={() => remove(i)} className="text-slate-400 hover:text-red-500 shrink-0 transition-colors">
              <X size={14} />
            </button>
          )}
        </div>
      ))}
      {items.length < MAX_BULLETS && (
        <button
          type="button"
          onClick={() => onChange([...items.filter(Boolean), ""])}
          className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-700 transition-colors mt-1"
        >
          <Plus size={12} /> Add bullet
        </button>
      )}
    </div>
  );
}

// ── FAQList ────────────────────────────────────────────────────────────────────

function FAQList({ faqs, onChange }: { faqs: FAQ[]; onChange: (v: FAQ[]) => void }) {
  const add = () => onChange([...faqs, { question: "", answer: "" }]);
  const remove = (i: number) => onChange(faqs.filter((_, j) => j !== i));
  const update = (i: number, field: "question" | "answer", val: string) => {
    const n = [...faqs]; n[i] = { ...n[i], [field]: val }; onChange(n);
  };
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className={`${labelCls} mb-0`}>FAQs</label>
        <button type="button" onClick={add} className="flex items-center gap-1 text-xs text-[#1e40af] hover:text-blue-700 transition-colors font-medium">
          <Plus size={12} /> Add FAQ
        </button>
      </div>
      {faqs.map((faq, i) => (
        <div key={i} className="bg-slate-50 border border-slate-200 rounded-lg p-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Q{i + 1}</span>
            <button type="button" onClick={() => remove(i)} className="text-slate-400 hover:text-red-500 transition-colors"><X size={12} /></button>
          </div>
          <Input value={faq.question} onChange={e => update(i, "question", e.target.value)} placeholder="Question" className="h-9 text-sm" data-testid={`faq-q-${i}`} />
          <Textarea value={faq.answer} onChange={e => update(i, "answer", e.target.value)} placeholder="Answer" rows={2} className="text-sm resize-none" data-testid={`faq-a-${i}`} />
        </div>
      ))}
    </div>
  );
}

// ── Pricing type selector ──────────────────────────────────────────────────────

const PRICING_TYPES = [
  {
    id: "internal",
    label: "Internal Checkout",
    icon: <CreditCard size={18} />,
    desc: "Base price + intake questions. Customer checks out on your platform.",
  },
  {
    id: "external",
    label: "External Link",
    icon: <ExternalLink size={18} />,
    desc: "Redirect to a third-party URL in a new tab.",
  },
  {
    id: "enquiry",
    label: "Enquiry Only",
    icon: <MessageSquare size={18} />,
    desc: "No checkout. Customer submits an enquiry to discuss pricing.",
  },
];

function PricingTypeSelector({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="grid grid-cols-3 gap-3 mb-5">
      {PRICING_TYPES.map(pt => {
        const active = value === pt.id;
        return (
          <button
            key={pt.id}
            type="button"
            onClick={() => onChange(pt.id)}
            data-testid={`pricing-type-${pt.id}`}
            className={`flex flex-col items-start p-4 rounded-lg border text-left transition-all duration-150 group ${
              active
                ? "bg-blue-50 border-[#1e40af] ring-1 ring-[#1e40af]/20 shadow-sm"
                : "bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50"
            }`}
          >
            <span className={`mb-2.5 transition-colors ${active ? "text-[#1e40af]" : "text-slate-400 group-hover:text-slate-500"}`}>
              {pt.icon}
            </span>
            <span className={`text-sm font-semibold mb-1 ${active ? "text-[#1e40af]" : "text-slate-700"}`}>
              {pt.label}
            </span>
            <span className="text-[11px] text-slate-500 leading-relaxed">{pt.desc}</span>
          </button>
        );
      })}
    </div>
  );
}

// ── Product Conditional Visibility Builder ────────────────────────────────────

const CUSTOMER_FIELDS = [
  { key: "country",       label: "Country" },
  { key: "company_name",  label: "Company Name" },
  { key: "email",         label: "Email" },
  { key: "status",        label: "Account Status" },
  { key: "state_province",label: "State / Province" },
  { key: "phone",         label: "Phone" },
];

const VIS_OPERATORS = [
  { value: "equals",      label: "equals" },
  { value: "not_equals",  label: "does not equal" },
  { value: "contains",    label: "contains" },
  { value: "not_contains",label: "does not contain" },
  { value: "empty",       label: "is empty / null" },
  { value: "not_empty",   label: "is not empty" },
];
const VIS_NO_VALUE = new Set(["empty", "not_empty"]);
const VIS_MAX = 4;
const VIS_EMPTY_COND: ProductVisCondition = { field: "country", operator: "equals", value: "" };

function ProductConditionBuilder({
  value,
  onChange,
}: {
  value: ProductVisRuleSet | null;
  onChange: (v: ProductVisRuleSet | null) => void;
}) {
  const ruleSet: ProductVisRuleSet = value ?? { logic: "AND", conditions: [{ ...VIS_EMPTY_COND }] };

  const updateLogic = (logic: "AND" | "OR") => onChange({ ...ruleSet, logic });
  const updateCond = (i: number, patch: Partial<ProductVisCondition>) => {
    const conds = ruleSet.conditions.map((c, idx) => idx === i ? { ...c, ...patch } : c);
    onChange({ ...ruleSet, conditions: conds });
  };
  const addCond = () => {
    if (ruleSet.conditions.length >= VIS_MAX) return;
    onChange({ ...ruleSet, conditions: [...ruleSet.conditions, { ...VIS_EMPTY_COND }] });
  };
  const removeCond = (i: number) => {
    const conds = ruleSet.conditions.filter((_, idx) => idx !== i);
    onChange(conds.length ? { ...ruleSet, conditions: conds } : null);
  };

  return (
    <div className="bg-indigo-50/60 border border-indigo-100 rounded-lg p-4 space-y-3 mt-3">
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-semibold text-indigo-700 uppercase tracking-wide">Show product when customer matches</p>
        {ruleSet.conditions.length > 1 && (
          <div className="flex rounded-md overflow-hidden border border-indigo-200 text-[10px] font-semibold">
            {(["AND", "OR"] as const).map(l => (
              <button key={l} type="button" onClick={() => updateLogic(l)}
                className={`px-2.5 py-1 transition-colors ${ruleSet.logic === l ? "bg-indigo-600 text-white" : "bg-white text-indigo-600 hover:bg-indigo-50"}`}>
                {l}
              </button>
            ))}
          </div>
        )}
      </div>

      {ruleSet.conditions.map((cond, i) => (
        <div key={i} className="space-y-2">
          {i > 0 && (
            <div className="flex items-center gap-2 my-1">
              <div className="flex-1 border-t border-indigo-100" />
              <span className="text-[10px] font-bold text-indigo-400">{ruleSet.logic}</span>
              <div className="flex-1 border-t border-indigo-100" />
            </div>
          )}
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[10px] text-slate-500 block mb-1">Customer field</label>
              <Select value={cond.field} onValueChange={v => updateCond(i, { field: v })}>
                <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {CUSTOMER_FIELDS.map(f => <SelectItem key={f.key} value={f.key}>{f.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-[10px] text-slate-500 block mb-1">Operator</label>
              <div className="flex gap-1">
                <Select value={cond.operator} onValueChange={v => updateCond(i, { operator: v, value: VIS_NO_VALUE.has(v) ? "" : cond.value })}>
                  <SelectTrigger className="h-8 text-xs flex-1"><SelectValue /></SelectTrigger>
                  <SelectContent>{VIS_OPERATORS.map(op => <SelectItem key={op.value} value={op.value}>{op.label}</SelectItem>)}</SelectContent>
                </Select>
                {ruleSet.conditions.length > 1 && (
                  <button type="button" onClick={() => removeCond(i)} className="text-slate-300 hover:text-red-400 transition-colors">
                    <X size={13} />
                  </button>
                )}
              </div>
            </div>
          </div>
          {!VIS_NO_VALUE.has(cond.operator) && (
            <div>
              <label className="text-[10px] text-slate-500 block mb-1">Value</label>
              <Input value={cond.value || ""} onChange={e => updateCond(i, { value: e.target.value })}
                placeholder="e.g. United Kingdom, Ltd, active" className="h-8 text-xs" />
            </div>
          )}
        </div>
      ))}

      {ruleSet.conditions.length < VIS_MAX && (
        <button type="button" onClick={addCond}
          className="flex items-center gap-1 text-[11px] text-indigo-500 hover:text-indigo-700 font-medium transition-colors">
          <Plus size={11} /> Add condition
        </button>
      )}
      <p className="text-[10px] text-slate-400 italic">Admins always see all products regardless of conditions.</p>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

export function ProductForm({
  form, setForm, categories, customers, terms,
}: {
  form: ProductFormData;
  setForm: (f: ProductFormData) => void;
  categories: any[];
  customers: any[];
  terms: any[];
}) {
  const [activeTab, setActiveTab] = useState<TabKey>("general");
  const [visSearch, setVisSearch] = useState("");
  const [localVisMode, setLocalVisMode] = useState<"all" | "restricted" | "show_to_specific">(() => {
    if (form.visible_to_customers.length > 0) return "show_to_specific";
    if (form.restricted_to.length > 0) return "restricted";
    return "all";
  });

  const visMode = localVisMode;
  const setVisMode = (mode: "all" | "restricted" | "show_to_specific") => {
    setLocalVisMode(mode);
    if (mode === "all") setForm({ ...form, visible_to_customers: [], restricted_to: [] });
    else if (mode === "restricted") setForm({ ...form, visible_to_customers: [], restricted_to: [] });
    else setForm({ ...form, restricted_to: [], visible_to_customers: [] });
  };

  const s = (key: keyof ProductFormData) => (v: any) => setForm({ ...form, [key]: v });

  const addVisibleCustomer = (id: string) => {
    if (!form.visible_to_customers.includes(id))
      setForm({ ...form, visible_to_customers: [...form.visible_to_customers, id] });
    setVisSearch("");
  };
  const removeVisibleCustomer = (id: string) =>
    setForm({ ...form, visible_to_customers: form.visible_to_customers.filter(c => c !== id) });
  const addRestrictedCustomer = (id: string) => {
    if (!form.restricted_to.includes(id))
      setForm({ ...form, restricted_to: [...form.restricted_to, id] });
    setVisSearch("");
  };
  const removeRestrictedCustomer = (id: string) =>
    setForm({ ...form, restricted_to: form.restricted_to.filter(c => c !== id) });

  const filteredVisCustomers = visSearch
    ? customers.filter(c => {
        const q = visSearch.toLowerCase();
        const active = visMode === "show_to_specific" ? form.visible_to_customers : form.restricted_to;
        return (c.email?.toLowerCase().includes(q) || c.company_name?.toLowerCase().includes(q)) && !active.includes(c.id);
      }).slice(0, 10)
    : [];

  return (
    <div>
      {/* Tab nav */}
      <div className="flex items-center gap-0 border-b border-slate-200 mb-5">
        {TABS.map(tab => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            data-testid={`pf-tab-${tab.key}`}
            className={`relative px-4 py-3 text-sm font-medium transition-colors ${
              activeTab === tab.key
                ? "text-[#1e40af]"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {tab.label}
            {activeTab === tab.key && (
              <span className="absolute bottom-0 left-0 w-full h-0.5 bg-[#1e40af] rounded-t" />
            )}
          </button>
        ))}
      </div>

      {/* ── General ─────────────────────────────────────────────────────────── */}
      {activeTab === "general" && (
        <div className={sectionCls}>
          <div className={cardCls}>
            <div>
              <label className={labelCls}>Name *</label>
              <Input value={form.name} onChange={e => s("name")(e.target.value)} placeholder="Product name" data-testid="pf-name" />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelCls}>Category</label>
                <Select value={form.category} onValueChange={s("category")}>
                  <SelectTrigger data-testid="pf-category"><SelectValue placeholder="Select category" /></SelectTrigger>
                  <SelectContent>
                    {categories.map(c => <SelectItem key={c.id} value={c.name}>{c.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className={labelCls}>Tag <span className="text-slate-400 normal-case font-normal tracking-normal text-xs">(e.g. Popular)</span></label>
                <Input value={form.tag} onChange={e => s("tag")(e.target.value)} placeholder="Popular" data-testid="pf-tag" />
              </div>
            </div>

            <div>
              <label className={labelCls}>Tagline</label>
              <Input value={form.tagline} onChange={e => s("tagline")(e.target.value)} placeholder="One-line punch" data-testid="pf-tagline" />
            </div>

            <div>
              <label className={labelCls}>Page layout <span className="text-slate-400 normal-case font-normal tracking-normal text-xs">(how product detail page is rendered)</span></label>
              <Select value={form.display_layout || "standard"} onValueChange={s("display_layout")}>
                <SelectTrigger data-testid="pf-layout"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="standard">Standard — two-column: info left, price right</SelectItem>
                  <SelectItem value="quick_buy">Quick Buy — compact, price-first, fast checkout</SelectItem>
                  <SelectItem value="wizard">Wizard — guided step-by-step form with progress bar</SelectItem>
                  <SelectItem value="application">Application Form — sidebar nav, sections, enterprise feel</SelectItem>
                  <SelectItem value="showcase">Showcase + Configurator — hero section, live calculator</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className={cardCls}>
            <div>
              <label className={labelCls}>Detail page description</label>
              <Textarea value={form.description_long} onChange={e => s("description_long")(e.target.value)} placeholder="Full description for the product page" rows={3} className="resize-none text-sm" data-testid="pf-long-desc" />
            </div>
            <BulletsList bullets={form.bullets} onChange={s("bullets")} />
          </div>

          <div className={cardCls}>
            <Toggle checked={form.is_active} onChange={s("is_active")} label="Active" note="(visible on storefront)" testId="pf-active" />
          </div>
        </div>
      )}

      {/* ── Store Card ──────────────────────────────────────────────────────── */}
      {activeTab === "storecard" && (
        <div className={sectionCls}>
          <p className="text-sm text-slate-500">Customise how this product appears on the store catalog cards. Leave blank to use the General values.</p>
          <div className={cardCls}>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelCls}>Card title</label>
                <Input value={form.card_title} onChange={e => s("card_title")(e.target.value)} placeholder={form.name || "Uses Name"} data-testid="pf-card-title" />
              </div>
              <div>
                <label className={labelCls}>Card tag</label>
                <Input value={form.card_tag} onChange={e => s("card_tag")(e.target.value)} placeholder={form.tag || "Uses Tag"} data-testid="pf-card-tag" />
              </div>
            </div>
            <div>
              <label className={labelCls}>Card description</label>
              <Input value={form.card_description} onChange={e => s("card_description")(e.target.value)} placeholder="Uses tagline if blank" data-testid="pf-card-desc" />
            </div>
            <BulletsList
              bullets={form.card_bullets.length > 0 ? form.card_bullets : [""]}
              onChange={v => s("card_bullets")(v.filter(Boolean))}
              placeholder="Card bullet point"
            />
          </div>
        </div>
      )}

      {/* ── Pricing ─────────────────────────────────────────────────────────── */}
      {activeTab === "pricing" && (
        <div className={sectionCls}>
          <PricingTypeSelector value={form.pricing_type || "internal"} onChange={s("pricing_type")} />

          {/* Currency - always required for internal pricing */}
          {/* Embedded directly in the pricing card below for cleaner layout */}

          {/* Internal */}
          {(form.pricing_type === "internal" || !form.pricing_type) && (
            <>
              <div className={cardCls}>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={labelCls}>Base price</label>
                    <Input
                      type="number"
                      value={form.base_price || ""}
                      onChange={e => s("base_price")(parseFloat(e.target.value) || 0)}
                      placeholder="0"
                      className="font-mono"
                      data-testid="pf-price"
                    />
                    <p className="text-[11px] text-slate-400 mt-1">Leave 0 for free or intake-only pricing</p>
                  </div>
                  <div>
                    <label className={labelCls}>Currency <span className="text-red-500">*</span></label>
                    <Select value={form.currency || "USD"} onValueChange={v => s("currency")(v)}>
                      <SelectTrigger data-testid="pf-currency"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {["USD", "CAD", "EUR", "AUD", "GBP", "INR", "MXN"].map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4 mt-4">
                  <div>
                    <label className={labelCls}>Price rounding</label>
                    <Select value={form.price_rounding || "none"} onValueChange={v => s("price_rounding")(v === "none" ? "" : v)}>
                      <SelectTrigger data-testid="pf-price-rounding"><SelectValue placeholder="No rounding" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">No rounding</SelectItem>
                        <SelectItem value="25">Round to nearest 25</SelectItem>
                        <SelectItem value="50">Round to nearest 50</SelectItem>
                        <SelectItem value="100">Round to nearest 100</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div />
                </div>
              </div>

              <div className="rounded-lg border border-slate-200 bg-white p-4">
                <div className="flex items-center gap-2.5 mb-3">
                  <h4 className="text-sm font-semibold text-slate-900">Intake questions</h4>
                  <span className="text-[11px] text-slate-500 bg-slate-100 border border-slate-200 px-2 py-0.5 rounded-full">
                    {form.intake_schema_json?.questions?.length ?? 0} questions
                  </span>
                </div>
                <p className="text-xs text-slate-500 mb-4">
                  Questions shown to the customer before checkout. Number and dropdown questions can add to or multiply the total price.
                </p>
                <IntakeSchemaBuilder
                  schema={form.intake_schema_json}
                  onChange={v => setForm({ ...form, intake_schema_json: v })}
                />
              </div>
            </>
          )}

          {/* External */}
          {form.pricing_type === "external" && (
            <div className={cardCls}>
              <div>
                <label className={labelCls}>External URL</label>
                <Input
                  value={form.external_url || ""}
                  onChange={e => s("external_url")(e.target.value)}
                  placeholder="https://..."
                  data-testid="pf-external-url"
                />
                <p className="text-[11px] text-slate-400 mt-1">Opens in a new tab when customer clicks the product</p>
              </div>
            </div>
          )}

          {/* Enquiry */}
          {form.pricing_type === "enquiry" && (
            <div className="border border-dashed border-slate-200 rounded-lg p-6 text-center bg-slate-50">
              <MessageSquare size={24} className="text-slate-400 mx-auto mb-2" />
              <p className="text-sm font-semibold text-slate-700">Enquiry only — no online checkout</p>
              <p className="text-xs text-slate-500 mt-1">Customers will submit an enquiry form. You'll be notified to follow up directly.</p>
            </div>
          )}

          {/* Shared: subscription + T&C */}
          <div className={cardCls}>
            {form.pricing_type !== "external" && form.pricing_type !== "enquiry" && (
              <>
                <Toggle checked={form.is_subscription} onChange={s("is_subscription")} label="Subscription" note="(recurring billing)" testId="pf-subscription" />
                {form.is_subscription && (
                  <div>
                    <label className={labelCls}>Stripe Price ID</label>
                    <Input value={form.stripe_price_id} onChange={e => s("stripe_price_id")(e.target.value)} placeholder="price_…" className="font-mono" data-testid="pf-stripe-price-id" />
                  </div>
                )}
              </>
            )}
            <div>
              <label className={labelCls}>Terms & Conditions</label>
              <Select value={form.terms_id || "default"} onValueChange={v => s("terms_id")(v === "default" ? "" : v)}>
                <SelectTrigger data-testid="pf-terms"><SelectValue placeholder="Default T&C" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="default">Default T&C</SelectItem>
                  {terms.map(t => <SelectItem key={t.id} value={t.id}>{t.title}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>
      )}

      {/* ── Visibility ──────────────────────────────────────────────────────── */}
      {activeTab === "visibility" && (
        <div className={sectionCls}>
          <div className={cardCls}>
            <label className={labelCls}>Customer visibility</label>
            <div className="space-y-2.5 mt-1">
              {([
                ["all",              "All customers"],
                ["restricted",       "Restrict from specific customers"],
                ["show_to_specific", "Show only to specific customers"],
              ] as const).map(([mode, label]) => (
                <label key={mode} className="flex items-center gap-3 cursor-pointer group">
                  <span className={`w-4 h-4 rounded-full border-2 flex items-center justify-center transition-colors ${
                    visMode === mode ? "border-[#1e40af] bg-[#1e40af]" : "border-slate-300 group-hover:border-slate-400"
                  }`}>
                    {visMode === mode && <span className="w-1.5 h-1.5 rounded-full bg-white" />}
                  </span>
                  <input type="radio" className="sr-only" checked={visMode === mode} onChange={() => setVisMode(mode)} data-testid={`vis-mode-${mode}`} />
                  <span className="text-sm text-slate-700">{label}</span>
                </label>
              ))}
            </div>
          </div>

          {visMode !== "all" && (
            <div className={cardCls}>
              <label className={labelCls}>
                {visMode === "restricted" ? "Hidden from" : "Visible only to"}
              </label>
              <div className="relative">
                <Input
                  value={visSearch}
                  onChange={e => setVisSearch(e.target.value)}
                  placeholder="Search customers…"
                  data-testid="vis-customer-search"
                />
                {filteredVisCustomers.length > 0 && (
                  <div className="absolute z-10 top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-lg overflow-hidden shadow-lg">
                    {filteredVisCustomers.map(c => (
                      <button
                        key={c.id}
                        type="button"
                        onClick={() => visMode === "show_to_specific" ? addVisibleCustomer(c.id) : addRestrictedCustomer(c.id)}
                        className="w-full text-left px-4 py-2.5 hover:bg-slate-50 transition-colors text-sm text-slate-900 border-b border-slate-100 last:border-0"
                        data-testid={`vis-add-${c.id}`}
                      >
                        <span className="font-medium">{c.company_name || c.email}</span>
                        {c.company_name && <span className="text-slate-400 ml-2 text-xs">{c.email}</span>}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {(visMode === "show_to_specific" ? form.visible_to_customers : form.restricted_to).length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {(visMode === "show_to_specific" ? form.visible_to_customers : form.restricted_to).map(id => {
                    const c = customers.find(x => x.id === id);
                    return (
                      <span key={id} className="flex items-center gap-1.5 bg-slate-100 border border-slate-200 text-slate-700 text-xs px-3 py-1.5 rounded-full">
                        {c?.company_name || c?.email || id}
                        <button
                          type="button"
                          onClick={() => visMode === "show_to_specific" ? removeVisibleCustomer(id) : removeRestrictedCustomer(id)}
                          className="text-slate-400 hover:text-red-500 transition-colors"
                        >
                          <X size={11} />
                        </button>
                      </span>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Content ─────────────────────────────────────────────────────────── */}
      {activeTab === "content" && (
        <div className={sectionCls}>
          <div className={cardCls}>
            <div className="flex items-center justify-between mb-1">
              <label className={`${labelCls} mb-0`}>Custom sections</label>
              <span className="text-xs text-slate-400">Up to 10</span>
            </div>
            <SectionsEditor sections={form.custom_sections} onChange={s("custom_sections")} />
          </div>
          <div className={cardCls}>
            <FAQList faqs={form.faqs} onChange={s("faqs")} />
          </div>
        </div>
      )}
    </div>
  );
}
