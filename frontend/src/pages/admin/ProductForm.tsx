import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  CreditCard, ExternalLink, MessageSquare, X, Plus, ChevronUp, ChevronDown,
} from "lucide-react";
import { IntakeSchemaBuilder, IntakeSchemaJson, EMPTY_INTAKE_SCHEMA } from "./IntakeSchemaBuilder";
import { SectionsEditor, CustomSection, DEFAULT_SECTION } from "./SectionsEditor";

// ── Types ──────────────────────────────────────────────────────────────────────

interface FAQ { question: string; answer: string; }

export interface ProductFormData {
  name: string;
  short_description: string;
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
  visible_to_customers: string[];
  restricted_to: string[];
  intake_schema_json: IntakeSchemaJson;
  custom_sections: CustomSection[];
}

type TabKey = "general" | "storecard" | "pricing" | "visibility" | "content";

const TABS: { key: TabKey; label: string }[] = [
  { key: "general",    label: "General" },
  { key: "storecard",  label: "Store Card" },
  { key: "pricing",    label: "Pricing" },
  { key: "visibility", label: "Visibility" },
  { key: "content",    label: "Content" },
];

// ── Empty form default ────────────────────────────────────────────────────────

export const EMPTY_FORM: ProductFormData = {
  name: "", short_description: "", tagline: "",
  card_title: "", card_tag: "", card_description: "", card_bullets: [],
  description_long: "", bullets: [], tag: "", category: "",
  faqs: [], terms_id: "", base_price: 0, is_subscription: false,
  stripe_price_id: "", price_rounding: "", pricing_type: "internal",
  external_url: "", is_active: true, visible_to_customers: [],
  restricted_to: [], intake_schema_json: EMPTY_INTAKE_SCHEMA, custom_sections: [],
};

// ── Sub-components ─────────────────────────────────────────────────────────────

const inputCls = "bg-[#1e293b] border-[#334155] text-[#f8fafc] placeholder:text-[#475569] focus:ring-1 focus:ring-[#dc2626] focus:border-[#dc2626] h-10 transition-all";
const labelCls = "text-sm font-medium text-[#94a3b8] mb-1.5 block";
const sectionCls = "space-y-4";
const dividerCls = "border-t border-[#1e293b] pt-5 mt-1";

const MAX_BULLETS = 8;

function BulletsList({ bullets, onChange, placeholder = "Feature or detail" }: {
  bullets: string[]; onChange: (v: string[]) => void; placeholder?: string;
}) {
  const items = bullets.length > 0 ? bullets : [""];
  const update = (i: number, v: string) => { const n = [...items]; n[i] = v; onChange(n.filter(Boolean)); };
  const remove = (i: number) => onChange(items.filter((_, j) => j !== i));
  return (
    <div className="space-y-2">
      <label className={labelCls}>Bullet points <span className="text-[#475569] font-normal text-xs">(what's included)</span></label>
      {items.map((b, i) => (
        <div key={i} className="flex gap-2 items-center">
          <span className="text-[#dc2626] text-xs mt-0.5 shrink-0">–</span>
          <Input
            value={b}
            onChange={e => update(i, e.target.value)}
            placeholder={placeholder}
            className={`${inputCls} flex-1 h-9`}
            data-testid={`pf-bullet-${i}`}
          />
          {items.length > 1 && (
            <button type="button" onClick={() => remove(i)} className="text-[#475569] hover:text-red-400 shrink-0 transition-colors">
              <X size={14} />
            </button>
          )}
        </div>
      ))}
      {items.length < MAX_BULLETS && (
        <button
          type="button"
          onClick={() => onChange([...items.filter(Boolean), ""])}
          className="flex items-center gap-1.5 text-xs text-[#64748b] hover:text-[#94a3b8] transition-colors"
        >
          <Plus size={12} /> Add bullet
        </button>
      )}
    </div>
  );
}

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
        <button type="button" onClick={add} className="flex items-center gap-1 text-xs text-[#64748b] hover:text-[#94a3b8] transition-colors">
          <Plus size={12} /> Add FAQ
        </button>
      </div>
      {faqs.map((faq, i) => (
        <div key={i} className="bg-[#1e293b] border border-[#334155] rounded-lg p-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-[#64748b] uppercase tracking-wider">Q{i + 1}</span>
            <button type="button" onClick={() => remove(i)} className="text-[#475569] hover:text-red-400 transition-colors"><X size={12} /></button>
          </div>
          <Input value={faq.question} onChange={e => update(i, "question", e.target.value)} placeholder="Question" className={`${inputCls} h-9 text-sm`} data-testid={`faq-q-${i}`} />
          <Textarea value={faq.answer} onChange={e => update(i, "answer", e.target.value)} placeholder="Answer" rows={2} className="bg-[#1e293b] border-[#334155] text-[#f8fafc] placeholder:text-[#475569] focus:ring-1 focus:ring-[#dc2626] focus:border-[#dc2626] text-sm resize-none" data-testid={`faq-a-${i}`} />
        </div>
      ))}
    </div>
  );
}

// ── Pricing type card ──────────────────────────────────────────────────────────

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
    <div className="grid grid-cols-3 gap-3 mb-6">
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
                ? "bg-[#1e293b] border-[#dc2626] ring-1 ring-[#dc2626]/40 shadow-[0_0_20px_rgba(220,38,38,0.08)]"
                : "bg-[#0f172a] border-[#334155] hover:border-[#475569] hover:bg-[#1e293b]/50"
            }`}
          >
            <span className={`mb-2.5 transition-colors ${active ? "text-[#dc2626]" : "text-[#64748b] group-hover:text-[#94a3b8]"}`}>
              {pt.icon}
            </span>
            <span className={`text-sm font-semibold mb-1 ${active ? "text-[#f8fafc]" : "text-[#94a3b8]"}`}>
              {pt.label}
            </span>
            <span className="text-[11px] text-[#475569] leading-relaxed">{pt.desc}</span>
          </button>
        );
      })}
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
    <div className="text-[#f8fafc]">
      {/* Tab nav */}
      <div className="flex items-center gap-0 border-b border-[#1e293b] mb-6">
        {TABS.map(tab => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            data-testid={`pf-tab-${tab.key}`}
            className={`relative px-4 py-3 text-sm font-medium transition-colors ${
              activeTab === tab.key
                ? "text-[#dc2626]"
                : "text-[#64748b] hover:text-[#94a3b8]"
            }`}
          >
            {tab.label}
            {activeTab === tab.key && (
              <span className="absolute bottom-0 left-0 w-full h-0.5 bg-[#dc2626] rounded-t" />
            )}
          </button>
        ))}
      </div>

      {/* ── General ─────────────────────────────────────────────────────────── */}
      {activeTab === "general" && (
        <div className={sectionCls}>
          <div>
            <label className={labelCls}>Name *</label>
            <Input value={form.name} onChange={e => s("name")(e.target.value)} placeholder="Product name" className={inputCls} data-testid="pf-name" />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelCls}>Category</label>
              <Select value={form.category} onValueChange={s("category")}>
                <SelectTrigger className={inputCls} data-testid="pf-category"><SelectValue placeholder="Select category" /></SelectTrigger>
                <SelectContent className="bg-[#1e293b] border-[#334155] text-[#f8fafc]">
                  {categories.map(c => <SelectItem key={c.id} value={c.name}>{c.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className={labelCls}>Tag <span className="text-[#475569] text-xs font-normal">(e.g. Popular)</span></label>
              <Input value={form.tag} onChange={e => s("tag")(e.target.value)} placeholder="Popular" className={inputCls} data-testid="pf-tag" />
            </div>
          </div>

          <div>
            <label className={labelCls}>Tagline</label>
            <Input value={form.tagline} onChange={e => s("tagline")(e.target.value)} placeholder="One-line punch" className={inputCls} data-testid="pf-tagline" />
          </div>

          <div>
            <label className={labelCls}>Detail page description</label>
            <Textarea value={form.description_long} onChange={e => s("description_long")(e.target.value)} placeholder="Full description for the product page" rows={3} className="bg-[#1e293b] border-[#334155] text-[#f8fafc] placeholder:text-[#475569] focus:ring-1 focus:ring-[#dc2626] focus:border-[#dc2626] resize-none" data-testid="pf-long-desc" />
          </div>

          <BulletsList bullets={form.bullets} onChange={s("bullets")} />

          <div className={dividerCls}>
            <label className="flex items-center gap-2.5 cursor-pointer select-none">
              <span className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${form.is_active ? "bg-[#dc2626]" : "bg-[#334155]"}`}>
                <input type="checkbox" checked={form.is_active} onChange={e => s("is_active")(e.target.checked)} className="sr-only" data-testid="pf-active" />
                <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform ${form.is_active ? "translate-x-4" : "translate-x-1"}`} />
              </span>
              <span className="text-sm text-[#94a3b8]">Active <span className="text-[#475569] text-xs">(visible on storefront)</span></span>
            </label>
          </div>
        </div>
      )}

      {/* ── Store Card ──────────────────────────────────────────────────────── */}
      {activeTab === "storecard" && (
        <div className={sectionCls}>
          <p className="text-sm text-[#64748b]">Customise how this product appears on the store catalog cards. Leave blank to use the General values.</p>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelCls}>Card title</label>
              <Input value={form.card_title} onChange={e => s("card_title")(e.target.value)} placeholder={form.name || "Uses Name"} className={inputCls} data-testid="pf-card-title" />
            </div>
            <div>
              <label className={labelCls}>Card tag</label>
              <Input value={form.card_tag} onChange={e => s("card_tag")(e.target.value)} placeholder={form.tag || "Uses Tag"} className={inputCls} data-testid="pf-card-tag" />
            </div>
          </div>

          <div>
            <label className={labelCls}>Card description</label>
            <Input value={form.card_description} onChange={e => s("card_description")(e.target.value)} placeholder={form.short_description || "Uses Short Description"} className={inputCls} data-testid="pf-card-desc" />
          </div>

          <BulletsList
            bullets={form.card_bullets.length > 0 ? form.card_bullets : [""]}
            onChange={v => s("card_bullets")(v.filter(Boolean))}
            placeholder="Card bullet point"
          />
        </div>
      )}

      {/* ── Pricing ─────────────────────────────────────────────────────────── */}
      {activeTab === "pricing" && (
        <div className={sectionCls}>
          <PricingTypeSelector value={form.pricing_type || "internal"} onChange={s("pricing_type")} />

          {/* Internal */}
          {(form.pricing_type === "internal" || !form.pricing_type) && (
            <>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className={labelCls}>Base price (£)</label>
                  <Input
                    type="number"
                    value={form.base_price || ""}
                    onChange={e => s("base_price")(parseFloat(e.target.value) || 0)}
                    placeholder="0"
                    className={`${inputCls} font-mono`}
                    data-testid="pf-price"
                  />
                  <p className="text-[11px] text-[#475569] mt-1">Leave 0 for free or intake-only pricing</p>
                </div>
                <div>
                  <label className={labelCls}>Price rounding</label>
                  <Select value={form.price_rounding || "none"} onValueChange={v => s("price_rounding")(v === "none" ? "" : v)}>
                    <SelectTrigger className={inputCls} data-testid="pf-price-rounding"><SelectValue placeholder="No rounding" /></SelectTrigger>
                    <SelectContent className="bg-[#1e293b] border-[#334155] text-[#f8fafc]">
                      <SelectItem value="none">No rounding</SelectItem>
                      <SelectItem value="25">Round to nearest £25</SelectItem>
                      <SelectItem value="50">Round to nearest £50</SelectItem>
                      <SelectItem value="100">Round to nearest £100</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className={dividerCls}>
                <div className="flex items-center gap-2.5 mb-4">
                  <h4 className="text-sm font-semibold text-[#f8fafc]">Intake questions</h4>
                  <span className="text-[11px] text-[#475569] bg-[#1e293b] border border-[#334155] px-2 py-0.5 rounded-full">
                    {form.intake_schema_json?.questions?.length ?? 0} questions
                  </span>
                </div>
                <p className="text-xs text-[#64748b] mb-4">
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
            <div>
              <label className={labelCls}>External URL</label>
              <Input
                value={form.external_url || ""}
                onChange={e => s("external_url")(e.target.value)}
                placeholder="https://..."
                className={inputCls}
                data-testid="pf-external-url"
              />
              <p className="text-[11px] text-[#475569] mt-1">Opens in a new tab when customer clicks the product</p>
            </div>
          )}

          {/* Enquiry */}
          {form.pricing_type === "enquiry" && (
            <div className="border border-dashed border-[#334155] rounded-lg p-5 text-center">
              <MessageSquare size={24} className="text-[#475569] mx-auto mb-2" />
              <p className="text-sm font-medium text-[#94a3b8]">Enquiry only — no online checkout</p>
              <p className="text-xs text-[#475569] mt-1">Customers will submit an enquiry form. You'll be notified to follow up directly.</p>
            </div>
          )}

          {/* Shared: subscription + T&C */}
          <div className={dividerCls}>
            <div className="space-y-4">
              <label className="flex items-center gap-2.5 cursor-pointer select-none">
                <span className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${form.is_subscription ? "bg-[#dc2626]" : "bg-[#334155]"}`}>
                  <input type="checkbox" checked={form.is_subscription} onChange={e => s("is_subscription")(e.target.checked)} className="sr-only" data-testid="pf-subscription" />
                  <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform ${form.is_subscription ? "translate-x-4" : "translate-x-1"}`} />
                </span>
                <span className="text-sm text-[#94a3b8]">Subscription <span className="text-[#475569] text-xs">(recurring billing)</span></span>
              </label>

              {form.is_subscription && (
                <div>
                  <label className={labelCls}>Stripe Price ID</label>
                  <Input value={form.stripe_price_id} onChange={e => s("stripe_price_id")(e.target.value)} placeholder="price_…" className={`${inputCls} font-mono`} data-testid="pf-stripe-price-id" />
                </div>
              )}

              <div>
                <label className={labelCls}>Terms & Conditions</label>
                <Select value={form.terms_id || "default"} onValueChange={v => s("terms_id")(v === "default" ? "" : v)}>
                  <SelectTrigger className={inputCls} data-testid="pf-terms"><SelectValue placeholder="Default T&C" /></SelectTrigger>
                  <SelectContent className="bg-[#1e293b] border-[#334155] text-[#f8fafc]">
                    <SelectItem value="default">Default T&C</SelectItem>
                    {terms.map(t => <SelectItem key={t.id} value={t.id}>{t.title}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Visibility ──────────────────────────────────────────────────────── */}
      {activeTab === "visibility" && (
        <div className={sectionCls}>
          <div>
            <label className={labelCls}>Customer visibility</label>
            <div className="space-y-2 mt-2">
              {([
                ["all",              "All customers"],
                ["restricted",       "Restrict from specific customers"],
                ["show_to_specific", "Show only to specific customers"],
              ] as const).map(([mode, label]) => (
                <label key={mode} className="flex items-center gap-3 cursor-pointer group">
                  <span className={`w-4 h-4 rounded-full border-2 flex items-center justify-center transition-colors ${
                    visMode === mode ? "border-[#dc2626] bg-[#dc2626]" : "border-[#475569] group-hover:border-[#94a3b8]"
                  }`}>
                    {visMode === mode && <span className="w-1.5 h-1.5 rounded-full bg-white" />}
                  </span>
                  <input type="radio" className="sr-only" checked={visMode === mode} onChange={() => setVisMode(mode)} data-testid={`vis-mode-${mode}`} />
                  <span className="text-sm text-[#94a3b8]">{label}</span>
                </label>
              ))}
            </div>
          </div>

          {visMode !== "all" && (
            <div className={dividerCls}>
              <label className={labelCls}>
                {visMode === "restricted" ? "Hidden from" : "Visible only to"}
              </label>
              <Input
                value={visSearch}
                onChange={e => setVisSearch(e.target.value)}
                placeholder="Search customers…"
                className={inputCls}
                data-testid="vis-customer-search"
              />
              {filteredVisCustomers.length > 0 && (
                <div className="mt-2 bg-[#1e293b] border border-[#334155] rounded-lg overflow-hidden shadow-xl">
                  {filteredVisCustomers.map(c => (
                    <button
                      key={c.id}
                      type="button"
                      onClick={() => visMode === "show_to_specific" ? addVisibleCustomer(c.id) : addRestrictedCustomer(c.id)}
                      className="w-full text-left px-4 py-2.5 hover:bg-[#334155] transition-colors text-sm text-[#f8fafc]"
                      data-testid={`vis-add-${c.id}`}
                    >
                      <span className="font-medium">{c.company_name || c.email}</span>
                      {c.company_name && <span className="text-[#64748b] ml-2 text-xs">{c.email}</span>}
                    </button>
                  ))}
                </div>
              )}

              {/* Selected list */}
              {(visMode === "show_to_specific" ? form.visible_to_customers : form.restricted_to).length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {(visMode === "show_to_specific" ? form.visible_to_customers : form.restricted_to).map(id => {
                    const c = customers.find(x => x.id === id);
                    return (
                      <span key={id} className="flex items-center gap-1.5 bg-[#1e293b] border border-[#334155] text-[#94a3b8] text-xs px-3 py-1.5 rounded-full">
                        {c?.company_name || c?.email || id}
                        <button
                          type="button"
                          onClick={() => visMode === "show_to_specific" ? removeVisibleCustomer(id) : removeRestrictedCustomer(id)}
                          className="text-[#475569] hover:text-red-400 transition-colors"
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
          <div>
            <div className="flex items-center justify-between mb-3">
              <label className={`${labelCls} mb-0`}>Custom sections</label>
              <span className="text-xs text-[#475569]">Up to 10</span>
            </div>
            <SectionsEditor sections={form.custom_sections} onChange={s("custom_sections")} />
          </div>
          <div className={dividerCls}>
            <FAQList faqs={form.faqs} onChange={s("faqs")} />
          </div>
        </div>
      )}
    </div>
  );
}
