import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  CreditCard, ExternalLink, MessageSquare, X, Plus, ChevronUp, ChevronDown, GitBranch, RefreshCw, Users,
} from "lucide-react";
import { IntakeSchemaBuilder, IntakeSchemaJson, EMPTY_INTAKE_SCHEMA } from "./IntakeSchemaBuilder";
import { SectionsEditor, CustomSection, DEFAULT_SECTION } from "./SectionsEditor";
import { FieldTip } from "./shared/FieldTip";
import api from "@/lib/api";
import { useCountries } from "@/hooks/useCountries";

// ── Types ──────────────────────────────────────────────────────────────────────

interface FAQ { question: string; answer: string; }

export interface ProductVisCondition {
  field: string;
  operator: string;
  value: string;
}
export interface ProductVisGroup {
  logic: "AND" | "OR";
  conditions: ProductVisCondition[];
}
export interface ProductVisRuleSet {
  top_logic: "AND" | "OR";
  groups: ProductVisGroup[];
}

export interface ProductFormData {
  name: string;
  card_tag: string;
  card_description: string;
  card_bullets: string[];
  description_long: string;
  bullets: string[];
  category: string;
  faqs: FAQ[];
  terms_id: string;
  base_price: number;
  is_subscription: boolean;
  stripe_price_id: string;
  price_rounding: string;
  show_price_breakdown: boolean;
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
  enquiry_form_id: string;
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
  name: "",
  card_tag: "", card_description: "", card_bullets: [],
  description_long: "", bullets: [], category: "",
  faqs: [], terms_id: "", base_price: 0, is_subscription: false,
  stripe_price_id: "", price_rounding: "", show_price_breakdown: false,
  pricing_type: "internal",
  external_url: "", currency: "USD", is_active: true, visible_to_customers: [],
  restricted_to: [], visibility_conditions: null, intake_schema_json: EMPTY_INTAKE_SCHEMA, custom_sections: [],
  display_layout: "standard",
  enquiry_form_id: "",
};

// ── Style tokens (light theme — matches admin panel) ───────────────────────────

const labelCls = "text-xs font-semibold text-slate-600 mb-1.5 block uppercase tracking-wide";
const sectionCls = "space-y-6";
const dividerCls = "border-t border-slate-100 pt-5 mt-1";
const cardCls = "rounded-lg border border-slate-200 bg-white p-5 space-y-5";
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

// ── BillingTypeSelector ────────────────────────────────────────────────────────

const BILLING_TYPES = [
  { isSubscription: false, label: "One-time", icon: CreditCard, desc: "Single payment. No recurring charges." },
  { isSubscription: true,  label: "Subscription", icon: RefreshCw, desc: "Recurring billing at regular intervals." },
];

function BillingTypeSelector({ value, onChange }: { value: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="grid grid-cols-2 gap-3">
      {BILLING_TYPES.map(bt => {
        const active = value === bt.isSubscription;
        const Icon = bt.icon;
        return (
          <button key={String(bt.isSubscription)} type="button" onClick={() => onChange(bt.isSubscription)}
            data-testid={`billing-type-${bt.isSubscription ? "subscription" : "one-time"}`}
            className={`flex flex-col items-start p-4 rounded-lg border text-left transition-all ${
              active ? "bg-blue-50 border-[#1e40af] ring-1 ring-[#1e40af]/20 shadow-sm" : "bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50"
            }`}>
            <Icon size={16} className={`mb-2 ${active ? "text-[#1e40af]" : "text-slate-400"}`} />
            <span className={`text-sm font-semibold mb-0.5 ${active ? "text-[#1e40af]" : "text-slate-700"}`}>{bt.label}</span>
            <span className="text-[11px] text-slate-500 leading-relaxed">{bt.desc}</span>
          </button>
        );
      })}
    </div>
  );
}

function BulletsList({ bullets, onChange, placeholder = "Feature or detail", label = "Bullet points" }: {
  bullets: string[]; onChange: (v: string[]) => void; placeholder?: string; label?: string;
}) {
  const update = (i: number, v: string) => { const n = [...bullets]; n[i] = v; onChange(n); };
  const remove = (i: number) => onChange(bullets.filter((_, j) => j !== i));
  const add = () => onChange([...bullets, ""]);
  return (
    <div className="space-y-2">
      <label className={labelCls}>{label}</label>
      {bullets.length === 0 && (
        <p className="text-xs text-slate-400 italic">No bullet points yet.</p>
      )}
      {bullets.map((b, i) => (
        <div key={i} className="flex gap-2 items-center">
          <span className="text-slate-300 text-xs mt-0.5 shrink-0">–</span>
          <Input
            value={b}
            onChange={e => update(i, e.target.value)}
            placeholder={placeholder}
            className="flex-1 h-9 text-sm"
            data-testid={`pf-bullet-${i}`}
          />
          {bullets.length > 1 && (
            <button type="button" onClick={() => remove(i)} className="text-slate-400 hover:text-red-500 shrink-0 transition-colors">
              <X size={14} />
            </button>
          )}
        </div>
      ))}
      {bullets.length < MAX_BULLETS && (
        <button
          type="button"
          onClick={add}
          data-testid="bullets-add-btn"
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

// Client-side evaluator (mirrors backend _eval_product_conditions)
function evalCustomerVis(customer: any, ruleSet: ProductVisRuleSet): boolean {
  const getF = (c: any, field: string): string => {
    const d = c[field];
    if (d !== undefined && d !== null) return String(d).toLowerCase();
    if (field === "state_province") return String(c.address?.region ?? "").toLowerCase();
    if (field === "country") return String(c.address?.country ?? "").toLowerCase();
    return "";
  };
  const evalC = (cond: ProductVisCondition, c: any): boolean => {
    const a = getF(c, cond.field), e = (cond.value || "").toLowerCase();
    switch (cond.operator) {
      case "equals": return a === e;
      case "not_equals": return a !== e;
      case "contains": return a.includes(e);
      case "not_contains": return !a.includes(e);
      case "empty": return !a;
      case "not_empty": return !!a;
      default: return true;
    }
  };
  const evalG = (g: ProductVisGroup, c: any) => {
    if (!g.conditions.length) return true;
    const r = g.conditions.map(cond => evalC(cond, c));
    return g.logic === "OR" ? r.some(Boolean) : r.every(Boolean);
  };
  if (!ruleSet.groups.length) return true;
  const r = ruleSet.groups.map(g => evalG(g, customer));
  return ruleSet.top_logic === "OR" ? r.some(Boolean) : r.every(Boolean);
}

const CUSTOMER_FIELDS = [
  { key: "country",        label: "Country" },
  { key: "company_name",   label: "Company Name" },
  { key: "email",          label: "Email" },
  { key: "status",         label: "Account Status" },
  { key: "state_province", label: "State / Province" },
  { key: "phone",          label: "Phone" },
];

const VIS_OPERATORS = [
  { value: "equals",       label: "equals" },
  { value: "not_equals",   label: "does not equal" },
  { value: "contains",     label: "contains" },
  { value: "not_contains", label: "does not contain" },
  { value: "empty",        label: "is empty / null" },
  { value: "not_empty",    label: "is not empty" },
];
const VIS_NO_VALUE = new Set(["empty", "not_empty"]);
const VIS_MAX_CONDS = 4;
const VIS_MAX_GROUPS = 3;
const VIS_EMPTY_COND = (): ProductVisCondition => ({ field: "country", operator: "equals", value: "" });
const VIS_DEFAULT_GROUP = (): ProductVisGroup => ({ logic: "AND", conditions: [VIS_EMPTY_COND()] });

/** Normalise legacy flat or missing rule into the current grouped format */
function normaliseVisRuleSet(v: ProductVisRuleSet | null | any): ProductVisRuleSet {
  if (!v) return { top_logic: "AND", groups: [VIS_DEFAULT_GROUP()] };
  if (v.groups && Array.isArray(v.groups)) return v as ProductVisRuleSet;
  // Legacy flat: { logic, conditions }
  if (v.conditions && Array.isArray(v.conditions))
    return { top_logic: "AND", groups: [{ logic: v.logic || "AND", conditions: v.conditions }] };
  return { top_logic: "AND", groups: [VIS_DEFAULT_GROUP()] };
}

function LogicBtnVis({ value, onChange, small }: { value: "AND" | "OR"; onChange: (v: "AND" | "OR") => void; small?: boolean }) {
  const sz = small ? "px-1.5 py-0.5 text-[9px]" : "px-2 py-0.5 text-[10px]";
  return (
    <div className="flex rounded overflow-hidden border border-indigo-200">
      {(["AND", "OR"] as const).map(l => (
        <button key={l} type="button" onClick={() => onChange(l)}
          className={`${sz} font-bold transition-colors ${value === l ? "bg-indigo-600 text-white" : "bg-white text-indigo-600 hover:bg-indigo-50"}`}>
          {l}
        </button>
      ))}
    </div>
  );
}

function ProductConditionBuilder({
  value,
  onChange,
  customers = [],
}: {
  value: ProductVisRuleSet | null;
  onChange: (v: ProductVisRuleSet | null) => void;
  customers?: any[];
}) {
  const [showPreview, setShowPreview] = useState(false);
  const ruleSet = normaliseVisRuleSet(value);
  const countries = useCountries();

  const setTopLogic = (tl: "AND" | "OR") => onChange({ ...ruleSet, top_logic: tl });
  const setGroupLogic = (gi: number, logic: "AND" | "OR") =>
    onChange({ ...ruleSet, groups: ruleSet.groups.map((g, i) => i === gi ? { ...g, logic } : g) });

  const setCond = (gi: number, ci: number, patch: Partial<ProductVisCondition>) =>
    onChange({
      ...ruleSet,
      groups: ruleSet.groups.map((g, i) => i !== gi ? g : {
        ...g, conditions: g.conditions.map((c, j) => j !== ci ? c : { ...c, ...patch }),
      }),
    });

  const addCond = (gi: number) => {
    if (ruleSet.groups[gi].conditions.length >= VIS_MAX_CONDS) return;
    onChange({
      ...ruleSet,
      groups: ruleSet.groups.map((grp, i) => i !== gi ? grp : { ...grp, conditions: [...grp.conditions, VIS_EMPTY_COND()] }),
    });
  };

  const removeCond = (gi: number, ci: number) => {
    const newGroups = ruleSet.groups
      .map((g, i) => i !== gi ? g : { ...g, conditions: g.conditions.filter((_, j) => j !== ci) })
      .filter(g => g.conditions.length > 0);
    onChange(newGroups.length ? { ...ruleSet, groups: newGroups } : null);
  };

  const addGroup = () => {
    if (ruleSet.groups.length >= VIS_MAX_GROUPS) return;
    onChange({ ...ruleSet, groups: [...ruleSet.groups, VIS_DEFAULT_GROUP()] });
  };

  const removeGroup = (gi: number) => {
    const newGroups = ruleSet.groups.filter((_, i) => i !== gi);
    onChange(newGroups.length ? { ...ruleSet, groups: newGroups } : null);
  };

  return (
    <div className="bg-indigo-50/60 border border-indigo-100 rounded-lg p-4 space-y-3 mt-3">
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-semibold text-indigo-700 uppercase tracking-wide">Show product when customer matches</p>
        {customers.length > 0 && (
          <button type="button" onClick={() => setShowPreview(v => !v)}
            data-testid="vis-preview-btn"
            className={`flex items-center gap-1.5 text-[11px] font-medium transition-colors px-2.5 py-1 rounded-md border ${
              showPreview ? "bg-indigo-100 border-indigo-200 text-indigo-700" : "bg-white border-slate-200 text-slate-500 hover:border-indigo-200 hover:text-indigo-600"
            }`}>
            <Users size={11} />
            {showPreview
              ? `${customers.filter(c => evalCustomerVis(c, ruleSet)).length} match${customers.filter(c => evalCustomerVis(c, ruleSet)).length !== 1 ? "es" : ""}`
              : "Preview matches"}
          </button>
        )}
      </div>

      {ruleSet.groups.map((group, gi) => (
        <div key={gi}>
          {gi > 0 && (
            <div className="flex items-center gap-2 my-2">
              <div className="flex-1 border-t border-dashed border-indigo-200" />
              <LogicBtnVis value={ruleSet.top_logic} onChange={setTopLogic} />
              <div className="flex-1 border-t border-dashed border-indigo-200" />
            </div>
          )}

          <div className="bg-white border border-indigo-100 rounded-lg p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold text-indigo-500 uppercase tracking-wide">
                {ruleSet.groups.length > 1 ? `Group ${gi + 1}` : "Conditions"}
              </span>
              <div className="flex items-center gap-2">
                {group.conditions.length > 1 && (
                  <LogicBtnVis value={group.logic} onChange={l => setGroupLogic(gi, l)} small />
                )}
                {ruleSet.groups.length > 1 && (
                  <button type="button" onClick={() => removeGroup(gi)} className="text-slate-300 hover:text-red-400 transition-colors ml-1">
                    <X size={12} />
                  </button>
                )}
              </div>
            </div>

            {group.conditions.map((cond, ci) => (
              <div key={ci} className="space-y-1.5">
                {ci > 0 && (
                  <div className="flex items-center gap-2 my-1">
                    <div className="flex-1 border-t border-indigo-100" />
                    <span className="text-[9px] font-bold text-indigo-400">{group.logic}</span>
                    <div className="flex-1 border-t border-indigo-100" />
                  </div>
                )}
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[10px] text-slate-500 block mb-1">Customer field</label>
                    <Select value={cond.field} onValueChange={v => setCond(gi, ci, { field: v })}>
                      <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {CUSTOMER_FIELDS.map(f => <SelectItem key={f.key} value={f.key}>{f.label}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <label className="text-[10px] text-slate-500 block mb-1">Operator</label>
                    <div className="flex gap-1">
                      <Select value={cond.operator} onValueChange={v => setCond(gi, ci, { operator: v, value: VIS_NO_VALUE.has(v) ? "" : cond.value })}>
                        <SelectTrigger className="h-8 text-xs flex-1"><SelectValue /></SelectTrigger>
                        <SelectContent>{VIS_OPERATORS.map(op => <SelectItem key={op.value} value={op.value}>{op.label}</SelectItem>)}</SelectContent>
                      </Select>
                      {(group.conditions.length > 1 || ruleSet.groups.length > 1) && (
                        <button type="button" onClick={() => removeCond(gi, ci)} className="text-slate-300 hover:text-red-400 transition-colors">
                          <X size={13} />
                        </button>
                      )}
                    </div>
                  </div>
                </div>
                {!VIS_NO_VALUE.has(cond.operator) && (
                  <div>
                    <label className="text-[10px] text-slate-500 block mb-1">Value</label>
                    {cond.field === "country" ? (
                      <Select value={cond.value || undefined} onValueChange={v => setCond(gi, ci, { value: v })}>
                        <SelectTrigger className="h-8 text-xs"><SelectValue placeholder="Select country…" /></SelectTrigger>
                        <SelectContent>
                          {countries.map(c => <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    ) : (
                      <Input value={cond.value || ""} onChange={e => setCond(gi, ci, { value: e.target.value })}
                        placeholder="e.g. United Kingdom, Ltd, active" className="h-8 text-xs" />
                    )}
                  </div>
                )}
              </div>
            ))}

            {group.conditions.length < VIS_MAX_CONDS && (
              <button type="button" onClick={() => addCond(gi)}
                className="flex items-center gap-1 text-[11px] text-indigo-500 hover:text-indigo-700 font-medium transition-colors mt-1">
                <Plus size={11} /> Add condition
              </button>
            )}
          </div>
        </div>
      ))}

      {ruleSet.groups.length < VIS_MAX_GROUPS && (
        <button type="button" onClick={addGroup}
          className="flex items-center gap-1.5 text-[11px] text-indigo-500 hover:text-indigo-700 font-medium transition-colors border border-dashed border-indigo-200 rounded-md px-2.5 py-1.5 w-full justify-center hover:bg-indigo-50/50">
          <Plus size={11} /> Add group
        </button>
      )}

      {/* Preview panel */}
      {showPreview && customers.length > 0 && (() => {
        const matched = customers.filter(c => evalCustomerVis(c, ruleSet));
        return (
          <div className="border-t border-indigo-100 pt-3 space-y-2" data-testid="vis-preview-panel">
            {matched.length === 0 ? (
              <p className="text-[11px] text-slate-400 italic">No customers match the current rules</p>
            ) : (
              <>
                <p className="text-[10px] font-semibold text-indigo-600 uppercase tracking-wide">
                  {matched.length} matching customer{matched.length !== 1 ? "s" : ""}
                </p>
                <div className="max-h-36 overflow-y-auto space-y-1.5">
                  {matched.slice(0, 25).map((c: any) => (
                    <div key={c.id} className="flex items-center gap-2 text-[11px] text-slate-700 bg-white border border-indigo-100 rounded px-2.5 py-1.5">
                      <span className="font-medium truncate">{c.company_name || c.full_name || c.email}</span>
                      {c.company_name && c.email && <span className="text-slate-400 truncate">{c.email}</span>}
                    </div>
                  ))}
                  {matched.length > 25 && <p className="text-[10px] text-slate-400 pl-1">...and {matched.length - 25} more</p>}
                </div>
              </>
            )}
          </div>
        );
      })()}

      <p className="text-[10px] text-slate-400 italic">Admins always see all products regardless of conditions.</p>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

export function ProductForm({
  form, setForm, categories, customers, terms, onSave,
}: {
  form: ProductFormData;
  setForm: (f: ProductFormData) => void;
  categories: any[];
  customers: any[];
  terms: any[];
  onSave?: () => void;
}) {
  const [activeTab, setActiveTab] = useState<TabKey>("general");
  const [visSearch, setVisSearch] = useState("");
  const [availableForms, setAvailableForms] = useState<Array<{ id: string; name: string }>>([]);

  useEffect(() => {
    if (form.pricing_type === "enquiry") {
      api.get("/admin/forms").then(res => setAvailableForms(res.data.forms || [])).catch(() => {});
    }
  }, [form.pricing_type]);
  const [localVisMode, setLocalVisMode] = useState<"all" | "restricted" | "show_to_specific" | "conditional">(() => {
    if (form.visibility_conditions) return "conditional";
    if (form.visible_to_customers.length > 0) return "show_to_specific";
    if (form.restricted_to.length > 0) return "restricted";
    return "all";
  });

  const visMode = localVisMode;
  const setVisMode = (mode: "all" | "restricted" | "show_to_specific" | "conditional") => {
    setLocalVisMode(mode);
    if (mode === "all") setForm({ ...form, visible_to_customers: [], restricted_to: [], visibility_conditions: null });
    else if (mode === "restricted") setForm({ ...form, visible_to_customers: [], visibility_conditions: null, restricted_to: [] });
    else if (mode === "show_to_specific") setForm({ ...form, restricted_to: [], visibility_conditions: null, visible_to_customers: [] });
    else if (mode === "conditional") setForm({ ...form, visible_to_customers: [], restricted_to: [],
      visibility_conditions: { top_logic: "AND", groups: [{ logic: "AND", conditions: [{ field: "country", operator: "equals", value: "" }] }] } });
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
              <label className={labelCls}>Product Name *</label>
              <Input value={form.name} onChange={e => s("name")(e.target.value)} placeholder="Product name" data-testid="pf-name" />
            </div>

            <div>
              <label className={labelCls}>Category</label>
              <Select value={form.category || undefined} onValueChange={s("category")}>
                <SelectTrigger data-testid="pf-category"><SelectValue placeholder="Select category" /></SelectTrigger>
                <SelectContent>
                  {categories.map(c => <SelectItem key={c.id} value={c.name}>{c.name}</SelectItem>)}
                </SelectContent>
              </Select>
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
            <BulletsList bullets={form.bullets} onChange={s("bullets")} label="Bullet points (what's included)" />
          </div>

          <div className={cardCls}>
            <Toggle checked={form.is_active} onChange={s("is_active")} label="Active" note="(visible on storefront)" testId="pf-active" />
          </div>
        </div>
      )}

      {/* ── Store Card ──────────────────────────────────────────────────────── */}
      {activeTab === "storecard" && (
        <div className={sectionCls}>
          <p className="text-sm text-slate-500">Customise how this product appears on store catalog cards. The product name is always used as the card title.</p>
          <div className={cardCls}>
            <div>
              <label className={labelCls}>Card tag <span className="text-slate-400 normal-case font-normal tracking-normal text-xs">(badge, e.g. Popular)</span></label>
              <Input value={form.card_tag} onChange={e => s("card_tag")(e.target.value)} placeholder="e.g. Popular" data-testid="pf-card-tag" />
            </div>
            <div>
              <label className={labelCls}>Card description</label>
              <Input value={form.card_description} onChange={e => s("card_description")(e.target.value)} placeholder="Short description shown on the card" data-testid="pf-card-desc" />
            </div>
            <BulletsList
              bullets={form.card_bullets}
              onChange={s("card_bullets")}
              placeholder="Card bullet point"
              label="Card highlights"
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
                {/* Billing type + Stripe Price ID — shown first */}
                <div className="space-y-3 pb-5 border-b border-slate-100 mb-6">
                  <label className={labelCls}>Billing type <FieldTip tip="One-time: customer pays once at checkout. Subscription: recurring charge at a set interval — requires a Stripe Price ID." /></label>
                  <BillingTypeSelector value={form.is_subscription} onChange={s("is_subscription")} />
                  {form.is_subscription && (
                    <div>
                      <label className={labelCls}>Stripe Price ID</label>
                      <Input value={form.stripe_price_id} onChange={e => s("stripe_price_id")(e.target.value)} placeholder="price_…" className="font-mono" data-testid="pf-stripe-price-id" />
                    </div>
                  )}
                </div>

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
                  <div>
                    <label className={labelCls}>Show price breakdown</label>
                    <Select value={form.show_price_breakdown ? "yes" : "no"} onValueChange={v => s("show_price_breakdown")(v === "yes")}>
                      <SelectTrigger data-testid="pf-show-breakdown"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="no">No — show total only</SelectItem>
                        <SelectItem value="yes">Yes — show line-by-line breakdown</SelectItem>
                      </SelectContent>
                    </Select>
                    <p className="text-[11px] text-slate-400 mt-1">Show itemised pricing to customers at checkout</p>
                  </div>
                </div>
              </div>

              <div className="rounded-lg border border-slate-200 bg-white p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2.5">
                    <h4 className="text-sm font-semibold text-slate-900">Intake questions</h4>
                    <span className="text-[11px] text-slate-500 bg-slate-100 border border-slate-200 px-2 py-0.5 rounded-full">
                      {form.intake_schema_json?.questions?.length ?? 0} questions
                    </span>
                  </div>
                  {onSave && (
                    <Button type="button" size="sm" variant="outline" onClick={onSave} className="h-7 text-xs px-3">
                      Save questions
                    </Button>
                  )}
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
            <div className="border border-slate-200 rounded-lg p-5 space-y-4">
              <div className="flex items-center gap-3 text-slate-700">
                <MessageSquare size={20} className="text-slate-400 shrink-0" />
                <div>
                  <p className="text-sm font-semibold">Enquiry only — no online checkout</p>
                  <p className="text-xs text-slate-500 mt-0.5">Customers will submit an enquiry form. You'll be notified to follow up directly.</p>
                </div>
              </div>
              <div className="border-t border-slate-100 pt-4">
                <label className="text-xs font-semibold text-slate-600 mb-1.5 block uppercase tracking-wide">Enquiry Form</label>
                <Select
                  value={form.enquiry_form_id || "default"}
                  onValueChange={v => s("enquiry_form_id")(v === "default" ? "" : v)}
                >
                  <SelectTrigger data-testid="pf-enquiry-form">
                    <SelectValue placeholder="Default Form" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="default">Default Form</SelectItem>
                    {availableForms.map(f => (
                      <SelectItem key={f.id} value={f.id}>{f.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-[11px] text-slate-400 mt-1">
                  Choose a custom form or use the default enquiry form. Manage forms under Settings → Forms.
                </p>
              </div>
            </div>
          )}

          {/* Shared: T&C */}
          <div className={cardCls}>
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
                ["all",              "All customers",                           null],
                ["restricted",       "Restrict from specific customers",        null],
                ["show_to_specific", "Show only to specific customers",         null],
                ["conditional",      "Conditional — based on customer profile", <GitBranch size={14} className="text-indigo-500" />],
              ] as const).map(([mode, label, icon]) => (
                <label key={mode} className="flex items-center gap-3 cursor-pointer group">
                  <span className={`w-4 h-4 rounded-full border-2 flex items-center justify-center transition-colors ${
                    visMode === mode ? "border-[#1e40af] bg-[#1e40af]" : "border-slate-300 group-hover:border-slate-400"
                  }`}>
                    {visMode === mode && <span className="w-1.5 h-1.5 rounded-full bg-white" />}
                  </span>
                  <input type="radio" className="sr-only" checked={visMode === mode} onChange={() => setVisMode(mode)} data-testid={`vis-mode-${mode}`} />
                  <span className="flex items-center gap-1.5 text-sm text-slate-700">
                    {icon}{label}
                  </span>
                </label>
              ))}
            </div>

            {visMode === "conditional" && (
              <ProductConditionBuilder
                value={form.visibility_conditions}
                onChange={v => setForm({ ...form, visibility_conditions: v })}
                customers={customers}
              />
            )}
          </div>

          {(visMode === "restricted" || visMode === "show_to_specific") && (
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
