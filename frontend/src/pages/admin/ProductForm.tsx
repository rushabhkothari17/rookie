import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { X, Plus } from "lucide-react";
import { IntakeSchemaBuilder, IntakeSchemaJson, EMPTY_INTAKE_SCHEMA } from "./IntakeSchemaBuilder";
import { SectionsEditor, CustomSection, DEFAULT_SECTION } from "./SectionsEditor";

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
  pricing_rules: Record<string, any>;
  is_active: boolean;
  visible_to_customers: string[];
  restricted_to: string[];
  intake_schema_json: IntakeSchemaJson;
  custom_sections: CustomSection[];
}

function makeId() {
  return Math.random().toString(36).substr(2, 9);
}

export const EMPTY_FORM: ProductFormData = {
  name: "", short_description: "", tagline: "",
  card_title: "", card_tag: "", card_description: "", card_bullets: [],
  description_long: "",
  bullets: [""],
  tag: "", category: "",
  faqs: [], terms_id: "", base_price: 0, is_subscription: false, stripe_price_id: "",
  price_rounding: "", pricing_type: "fixed", pricing_rules: {},
  is_active: true, visible_to_customers: [], restricted_to: [],
  intake_schema_json: EMPTY_INTAKE_SCHEMA,
  custom_sections: [{ ...DEFAULT_SECTION, id: makeId() }],
};

const MAX_BULLETS = 10;

function BulletsList({ bullets, onChange }: { bullets: string[]; onChange: (v: string[]) => void; }) {
  const update = (i: number, v: string) => { const n = [...bullets]; n[i] = v; onChange(n); };
  const add = () => { if (bullets.length < MAX_BULLETS) onChange([...bullets, ""]); };
  const remove = (i: number) => { if (bullets.length > 1) onChange(bullets.filter((_, j) => j !== i)); };
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <label className="text-xs text-slate-600">Key Bullets</label>
        <span className="text-[10px] text-slate-400">{bullets.length} / {MAX_BULLETS}</span>
      </div>
      <div className="space-y-1.5">
        {bullets.map((b, i) => (
          <div key={i} className="flex gap-2 items-center">
            <Input value={b} onChange={e => update(i, e.target.value)} placeholder={`Bullet ${i + 1}`} className="h-8 text-sm" data-testid={`pf-bullet-${i}`} />
            <button type="button" onClick={() => remove(i)} disabled={bullets.length <= 1} className="text-red-400 hover:text-red-600 disabled:opacity-25 shrink-0"><X size={15} /></button>
          </div>
        ))}
        {bullets.length < MAX_BULLETS && (
          <Button type="button" variant="outline" size="sm" onClick={add} className="h-7 text-xs" data-testid="pf-bullet-add">
            <Plus size={12} className="mr-1" /> Add Bullet
          </Button>
        )}
      </div>
    </div>
  );
}

function FAQList({ faqs, onChange }: { faqs: FAQ[]; onChange: (v: FAQ[]) => void; }) {
  const update = (i: number, key: keyof FAQ, v: string) => {
    const n = [...faqs]; n[i] = { ...n[i], [key]: v }; onChange(n);
  };
  const add = () => onChange([...faqs, { question: "", answer: "" }]);
  const remove = (i: number) => onChange(faqs.filter((_, j) => j !== i));
  return (
    <div>
      <label className="text-xs text-slate-600">FAQs</label>
      <div className="space-y-3 mt-1">
        {faqs.map((faq, i) => (
          <div key={i} className="border border-slate-200 rounded-lg p-3 space-y-2 relative">
            <button type="button" onClick={() => remove(i)} className="absolute top-2 right-2 text-red-400 hover:text-red-600"><X size={14} /></button>
            <Input value={faq.question} onChange={e => update(i, "question", e.target.value)} placeholder="Question" data-testid={`faq-q-${i}`} />
            <Textarea value={faq.answer} onChange={e => update(i, "answer", e.target.value)} placeholder="Answer" rows={2} data-testid={`faq-a-${i}`} />
          </div>
        ))}
        <Button type="button" variant="outline" size="sm" onClick={add} data-testid="faq-add">
          <Plus size={14} className="mr-1" /> Add FAQ
        </Button>
      </div>
    </div>
  );
}

interface Customer { id: string; user_id: string; company_name?: string; email?: string; }
interface Term { id: string; title: string; }

type TabKey = "general" | "pricing" | "intake" | "content";

const TABS: { key: TabKey; label: string }[] = [
  { key: "general", label: "General" },
  { key: "pricing", label: "Pricing" },
  { key: "intake", label: "Intake Questions" },
  { key: "content", label: "Page Content" },
];

export function ProductForm({
  form,
  setForm,
  categories,
  customers,
  terms,
}: {
  form: ProductFormData;
  setForm: (f: ProductFormData) => void;
  categories: { id: string; name: string; is_active: boolean }[];
  customers: Customer[];
  terms: Term[];
}) {
  const [activeTab, setActiveTab] = useState<TabKey>("general");
  const [visSearch, setVisSearch] = useState("");
  const [pricingRulesText, setPricingRulesText] = useState(() => {
    const r = form.pricing_rules;
    return r && Object.keys(r).length > 0 ? JSON.stringify(r, null, 2) : "";
  });
  const [pricingRulesError, setPricingRulesError] = useState("");

  const handlePricingRulesChange = (text: string) => {
    setPricingRulesText(text);
    if (!text.trim()) {
      setPricingRulesError("");
      setForm({ ...form, pricing_rules: {} });
      return;
    }
    try {
      const parsed = JSON.parse(text);
      setPricingRulesError("");
      setForm({ ...form, pricing_rules: parsed });
    } catch {
      setPricingRulesError("Invalid JSON");
    }
  };

  // Derive visibility mode from form data
  const visMode = form.visible_to_customers.length > 0
    ? "show_to_specific"
    : form.restricted_to.length > 0
      ? "restricted"
      : "all";

  const setVisMode = (mode: "all" | "restricted" | "show_to_specific") => {
    if (mode === "all") {
      setForm({ ...form, visible_to_customers: [], restricted_to: [] });
    } else if (mode === "restricted") {
      setForm({ ...form, visible_to_customers: [], restricted_to: form.restricted_to });
    } else {
      setForm({ ...form, restricted_to: [], visible_to_customers: form.visible_to_customers });
    }
  };

  const s = (key: keyof ProductFormData) => (v: any) => setForm({ ...form, [key]: v });

  const addVisibleCustomer = (id: string) => {
    if (!form.visible_to_customers.includes(id)) {
      setForm({ ...form, visible_to_customers: [...form.visible_to_customers, id] });
    }
    setVisSearch("");
  };

  const removeVisibleCustomer = (id: string) => {
    setForm({ ...form, visible_to_customers: form.visible_to_customers.filter(c => c !== id) });
  };

  const addRestrictedCustomer = (id: string) => {
    if (!form.restricted_to.includes(id)) {
      setForm({ ...form, restricted_to: [...form.restricted_to, id] });
    }
    setVisSearch("");
  };

  const removeRestrictedCustomer = (id: string) => {
    setForm({ ...form, restricted_to: form.restricted_to.filter(c => c !== id) });
  };

  const filteredVisCustomers = visSearch
    ? customers.filter(c => {
        const q = visSearch.toLowerCase();
        const activeList = visMode === "show_to_specific" ? form.visible_to_customers : form.restricted_to;
        return (c.email?.toLowerCase().includes(q) || c.company_name?.toLowerCase().includes(q)) && !activeList.includes(c.id);
      }).slice(0, 10)
    : [];

  return (
    <div className="space-y-0">
      {/* Tab navigation */}
      <div className="flex gap-0 border-b border-slate-200 mb-5">
        {TABS.map(tab => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            data-testid={`pf-tab-${tab.key}`}
            className={`px-4 py-2.5 text-xs font-semibold tracking-wide transition-colors border-b-2 -mb-px ${
              activeTab === tab.key
                ? "border-slate-800 text-slate-900 bg-white"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ─── Tab: General ─── */}
      {activeTab === "general" && (
        <div className="space-y-4">
          <div>
            <label className="text-xs text-slate-600">Name *</label>
            <Input value={form.name} onChange={e => s("name")(e.target.value)} placeholder="Product name" className="mt-1" data-testid="pf-name" />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-slate-600">Tag</label>
              <Input value={form.tag} onChange={e => s("tag")(e.target.value)} placeholder="e.g. Popular" className="mt-1" data-testid="pf-tag" />
            </div>
            <div>
              <label className="text-xs text-slate-600">Category</label>
              <Select value={form.category} onValueChange={s("category")}>
                <SelectTrigger className="mt-1" data-testid="pf-category"><SelectValue placeholder="Select category" /></SelectTrigger>
                <SelectContent>
                  {categories.map(c => <SelectItem key={c.id} value={c.name}>{c.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div>
            <label className="text-xs text-slate-600">Short Description</label>
            <Input value={form.short_description} onChange={e => s("short_description")(e.target.value)} placeholder="One-line description shown on product cards" className="mt-1" data-testid="pf-short-desc" />
          </div>

          <div>
            <label className="text-xs text-slate-600">Detail Page Description</label>
            <Textarea value={form.description_long} onChange={e => s("description_long")(e.target.value)} placeholder="Full description for the product detail page" rows={3} className="mt-1" data-testid="pf-long-desc" />
          </div>

          <BulletsList bullets={form.bullets} onChange={s("bullets")} />

          {/* Visibility */}
          <div className="space-y-3 border-t border-slate-100 pt-4">
            <div className="flex items-center gap-2">
              <label className="flex items-center gap-2 cursor-pointer text-sm">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={e => s("is_active")(e.target.checked)}
                  className="w-4 h-4 rounded"
                  data-testid="pf-active"
                />
                Active (visible on storefront)
              </label>
            </div>

            {/* Visibility mode selector */}
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-2">Customer Visibility</label>
              <div className="space-y-2">
                <label className="flex items-start gap-2.5 cursor-pointer rounded-lg border border-slate-200 p-3 hover:bg-slate-50 transition-colors" data-testid="pf-vis-all">
                  <input type="radio" name="visMode" checked={visMode === "all"} onChange={() => setVisMode("all")} className="mt-0.5 w-4 h-4 accent-slate-800" />
                  <div>
                    <div className="text-sm font-medium text-slate-800">All customers</div>
                    <div className="text-xs text-slate-500">Everyone can see this product on the store</div>
                  </div>
                </label>
                <label className="flex items-start gap-2.5 cursor-pointer rounded-lg border border-slate-200 p-3 hover:bg-slate-50 transition-colors" data-testid="pf-vis-restricted">
                  <input type="radio" name="visMode" checked={visMode === "restricted"} onChange={() => setVisMode("restricted")} className="mt-0.5 w-4 h-4 accent-slate-800" />
                  <div>
                    <div className="text-sm font-medium text-slate-800">Restrict from specific customers</div>
                    <div className="text-xs text-slate-500">Selected customers cannot see this product; everyone else can</div>
                  </div>
                </label>
                <label className="flex items-start gap-2.5 cursor-pointer rounded-lg border border-slate-200 p-3 hover:bg-slate-50 transition-colors" data-testid="pf-vis-specific">
                  <input type="radio" name="visMode" checked={visMode === "show_to_specific"} onChange={() => setVisMode("show_to_specific")} className="mt-0.5 w-4 h-4 accent-slate-800" />
                  <div>
                    <div className="text-sm font-medium text-slate-800">Show only to specific customers</div>
                    <div className="text-xs text-slate-500">Only selected customers can see this product</div>
                  </div>
                </label>
              </div>
            </div>

            {/* Customer search for restricted/specific modes */}
            {visMode !== "all" && (
              <div>
                <label className="text-xs text-slate-600">
                  {visMode === "restricted" ? "Customers to block:" : "Customers who can see it:"}
                </label>
                <div className="mt-1.5 relative">
                  <Input
                    placeholder="Search by email or company…"
                    value={visSearch}
                    onChange={e => setVisSearch(e.target.value)}
                    className="h-8 text-sm"
                    data-testid="pf-vis-search"
                  />
                  {filteredVisCustomers.length > 0 && (
                    <div className="absolute z-10 w-full border border-slate-200 rounded bg-white shadow-md max-h-40 overflow-y-auto mt-1">
                      {filteredVisCustomers.map(c => (
                        <div
                          key={c.id}
                          onClick={() => visMode === "restricted" ? addRestrictedCustomer(c.id) : addVisibleCustomer(c.id)}
                          className="px-3 py-2 hover:bg-slate-50 cursor-pointer text-sm"
                          data-testid={`pf-vis-option-${c.id}`}
                        >
                          <span className="font-medium">{c.email || c.company_name || c.id.slice(0, 8)}</span>
                          {c.company_name && c.email && <span className="text-slate-400"> — {c.company_name}</span>}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                {/* Selected customers chips */}
                {visMode === "restricted" && form.restricted_to.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1" data-testid="pf-restricted-list">
                    {form.restricted_to.map(custId => {
                      const c = customers.find(x => x.id === custId);
                      return (
                        <span key={custId} className="inline-flex items-center gap-1 bg-red-50 text-red-700 border border-red-200 text-xs px-2 py-1 rounded-full">
                          {c?.email || c?.company_name || custId.slice(0, 8)}
                          <button type="button" onClick={() => removeRestrictedCustomer(custId)} className="text-red-400 hover:text-red-600 font-bold" data-testid={`pf-restricted-remove-${custId}`}>×</button>
                        </span>
                      );
                    })}
                    <button type="button" onClick={() => s("restricted_to")([])} className="text-xs text-slate-400 hover:text-red-500 underline ml-1">Clear all</button>
                  </div>
                )}
                {visMode === "show_to_specific" && form.visible_to_customers.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1" data-testid="pf-visibility-list">
                    {form.visible_to_customers.map(custId => {
                      const c = customers.find(x => x.id === custId);
                      return (
                        <span key={custId} className="inline-flex items-center gap-1 bg-blue-50 text-blue-700 border border-blue-200 text-xs px-2 py-1 rounded-full">
                          {c?.email || c?.company_name || custId.slice(0, 8)}
                          <button type="button" onClick={() => removeVisibleCustomer(custId)} className="text-blue-400 hover:text-red-500 font-bold" data-testid={`pf-vis-remove-${custId}`}>×</button>
                        </span>
                      );
                    })}
                    <button type="button" onClick={() => s("visible_to_customers")([])} className="text-xs text-slate-400 hover:text-red-500 underline ml-1">Clear all</button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ─── Tab: Pricing ─── */}
      {activeTab === "pricing" && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-slate-600">Base Price ($)</label>
              <Input type="number" value={form.base_price} onChange={e => s("base_price")(parseFloat(e.target.value) || 0)} className="mt-1" data-testid="pf-price" />
            </div>
            <div>
              <label className="text-xs text-slate-600">Price Rounding</label>
              <Select value={form.price_rounding || "none"} onValueChange={v => s("price_rounding")(v === "none" ? "" : v)}>
                <SelectTrigger className="mt-1" data-testid="pf-price-rounding"><SelectValue placeholder="No rounding" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">No rounding</SelectItem>
                  <SelectItem value="25">Round to nearest $25</SelectItem>
                  <SelectItem value="50">Round to nearest $50</SelectItem>
                  <SelectItem value="100">Round to nearest $100</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <label className="flex items-center gap-2 cursor-pointer text-sm">
            <input
              type="checkbox"
              checked={form.is_subscription}
              onChange={e => s("is_subscription")(e.target.checked)}
              className="w-4 h-4 rounded"
              data-testid="pf-subscription"
            />
            Subscription (recurring billing)
          </label>

          {form.is_subscription && (
            <div>
              <label className="text-xs text-slate-600">Stripe Price ID</label>
              <Input value={form.stripe_price_id} onChange={e => s("stripe_price_id")(e.target.value)} placeholder="price_…" className="mt-1 font-mono text-sm" data-testid="pf-stripe-price-id" />
            </div>
          )}

          <div>
            <label className="text-xs text-slate-600">Terms & Conditions</label>
            <Select value={form.terms_id || "default"} onValueChange={v => s("terms_id")(v === "default" ? "" : v)}>
              <SelectTrigger className="mt-1" data-testid="pf-terms"><SelectValue placeholder="Default T&C" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="default">Default T&C</SelectItem>
                {terms.map(t => <SelectItem key={t.id} value={t.id}>{t.title}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>

          {/* Advanced: Pricing Rules JSON */}
          {form.pricing_rules && Object.keys(form.pricing_rules).length > 0 && (
            <div>
              <label className="text-xs text-slate-600">Pricing Rules (Advanced)</label>
              <p className="text-[10px] text-slate-400 mb-1">
                JSON config for tiered/calculator pricing. Edit to update rates, variants, etc.
              </p>
              <Textarea
                value={pricingRulesText}
                onChange={e => handlePricingRulesChange(e.target.value)}
                rows={6}
                className="mt-1 font-mono text-xs"
                placeholder="{}"
                data-testid="pf-pricing-rules"
              />
              {pricingRulesError && (
                <p className="text-xs text-red-500 mt-1">{pricingRulesError}</p>
              )}
            </div>
          )}
        </div>
      )}

      {/* ─── Tab: Intake Questions ─── */}
      {activeTab === "intake" && (
        <div className="space-y-3">
          <p className="text-xs text-slate-500">Configure questions shown to the customer on the product page.</p>
          <IntakeSchemaBuilder
            schema={form.intake_schema_json}
            onChange={v => setForm({ ...form, intake_schema_json: v })}
          />
        </div>
      )}

      {/* ─── Tab: Page Content ─── */}
      {activeTab === "content" && (
        <div className="space-y-5">
          <div>
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Custom Sections</h4>
              <span className="text-xs text-slate-400">Up to 10 sections</span>
            </div>
            <SectionsEditor
              sections={form.custom_sections}
              onChange={s("custom_sections")}
            />
          </div>

          <div className="border-t border-slate-100 pt-4">
            <FAQList faqs={form.faqs} onChange={s("faqs")} />
          </div>
        </div>
      )}
    </div>
  );
}
