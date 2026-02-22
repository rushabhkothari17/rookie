import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { X, Plus } from "lucide-react";
import { IntakeSchemaBuilder, IntakeSchemaJson, EMPTY_INTAKE_SCHEMA } from "./IntakeSchemaBuilder";

interface FAQ { question: string; answer: string; }

export interface ProductFormData {
  name: string;
  short_description: string;
  description_long: string;
  bullets: string[];
  tag: string;
  category: string;
  outcome: string;
  automation_details: string;
  support_details: string;
  inclusions: string[];
  exclusions: string[];
  requirements: string[];
  next_steps: string[];
  faqs: FAQ[];
  terms_id: string;
  base_price: number;
  is_subscription: boolean;
  stripe_price_id: string;
  pricing_complexity: string;
  is_active: boolean;
  visible_to_customers: string[];
  intake_schema_json: IntakeSchemaJson;
}

export const EMPTY_FORM: ProductFormData = {
  name: "", short_description: "", description_long: "", bullets: ["", "", ""],
  tag: "", category: "", outcome: "", automation_details: "", support_details: "",
  inclusions: [], exclusions: [], requirements: [], next_steps: [],
  faqs: [], terms_id: "", base_price: 0, is_subscription: false, stripe_price_id: "",
  pricing_complexity: "SIMPLE", is_active: true, visible_to_customers: [],
  intake_schema_json: EMPTY_INTAKE_SCHEMA,
};

function DynamicStringList({ label, items, onChange, placeholder, testId }: {
  label: string; items: string[]; onChange: (v: string[]) => void; placeholder?: string; testId?: string;
}) {
  const update = (i: number, v: string) => { const n = [...items]; n[i] = v; onChange(n); };
  const add = () => onChange([...items, ""]);
  const remove = (i: number) => onChange(items.filter((_, j) => j !== i));
  return (
    <div>
      <label className="text-xs text-slate-600">{label}</label>
      <div className="space-y-2 mt-1">
        {items.map((item, i) => (
          <div key={i} className="flex gap-2 items-center">
            <Input value={item} onChange={(e) => update(i, e.target.value)} placeholder={placeholder || "Enter value"} data-testid={`${testId}-${i}`} />
            <button type="button" onClick={() => remove(i)} className="text-red-400 hover:text-red-600 shrink-0"><X size={16} /></button>
          </div>
        ))}
        <Button type="button" variant="outline" size="sm" onClick={add} data-testid={`${testId}-add`}>
          <Plus size={14} className="mr-1" /> Add
        </Button>
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
            <Input value={faq.question} onChange={(e) => update(i, "question", e.target.value)} placeholder="Question" data-testid={`faq-q-${i}`} />
            <Textarea value={faq.answer} onChange={(e) => update(i, "answer", e.target.value)} placeholder="Answer" rows={2} data-testid={`faq-a-${i}`} />
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
  const s = (key: keyof ProductFormData) => (v: any) => setForm({ ...form, [key]: v });
  const [visSearch, setVisSearch] = useState("");

  const addVisibleCustomer = (id: string) => {
    if (!form.visible_to_customers.includes(id)) {
      setForm({ ...form, visible_to_customers: [...form.visible_to_customers, id] });
    }
    setVisSearch("");
  };

  const removeVisibleCustomer = (id: string) => {
    setForm({ ...form, visible_to_customers: form.visible_to_customers.filter((c) => c !== id) });
  };

  const filteredVisCustomers = visSearch
    ? customers.filter((c) => {
        const q = visSearch.toLowerCase();
        return (c.email?.toLowerCase().includes(q) || c.company_name?.toLowerCase().includes(q)) && !form.visible_to_customers.includes(c.id);
      }).slice(0, 10)
    : [];

  // Fixed bullets array to always have 3 slots
  const updateBullet = (i: number, v: string) => {
    const b = [...form.bullets];
    while (b.length < 3) b.push("");
    b[i] = v;
    setForm({ ...form, bullets: b });
  };
  const bullets = [...(form.bullets || [])];
  while (bullets.length < 3) bullets.push("");

  return (
    <div className="space-y-5">
      {/* Basic Info */}
      <div className="space-y-3 border-b border-slate-100 pb-4">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Basic Info</h4>
        <div>
          <label className="text-xs text-slate-600">Name *</label>
          <Input value={form.name} onChange={(e) => s("name")(e.target.value)} placeholder="Product name" className="mt-1" data-testid="pf-name" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-slate-600">Tag</label>
            <Input value={form.tag} onChange={(e) => s("tag")(e.target.value)} placeholder="e.g. Popular" className="mt-1" data-testid="pf-tag" />
          </div>
          <div>
            <label className="text-xs text-slate-600">Category</label>
            <Select value={form.category} onValueChange={s("category")}>
              <SelectTrigger className="mt-1" data-testid="pf-category"><SelectValue placeholder="Select category" /></SelectTrigger>
              <SelectContent>
                {categories.map((c) => <SelectItem key={c.id} value={c.name}>{c.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>
        <div>
          <label className="text-xs text-slate-600">Short Description</label>
          <Input value={form.short_description} onChange={(e) => s("short_description")(e.target.value)} placeholder="One-line description" className="mt-1" data-testid="pf-short-desc" />
        </div>
        <div>
          <label className="text-xs text-slate-600">Detail Page Description</label>
          <Textarea value={form.description_long} onChange={(e) => s("description_long")(e.target.value)} placeholder="Full description for the product detail page" rows={3} className="mt-1" data-testid="pf-long-desc" />
        </div>
      </div>

      {/* Bullets */}
      <div className="space-y-3 border-b border-slate-100 pb-4">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Key Bullets (3)</h4>
        {[0, 1, 2].map((i) => (
          <Input key={i} value={bullets[i]} onChange={(e) => updateBullet(i, e.target.value)} placeholder={`Bullet point ${i + 1}`} data-testid={`pf-bullet-${i}`} />
        ))}
      </div>

      {/* Outcome & Details */}
      <div className="space-y-3 border-b border-slate-100 pb-4">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Outcome & Details</h4>
        <div>
          <label className="text-xs text-slate-600">Outcome</label>
          <Textarea value={form.outcome} onChange={(e) => s("outcome")(e.target.value)} placeholder="What the customer will achieve" rows={2} className="mt-1" data-testid="pf-outcome" />
        </div>
        <div>
          <label className="text-xs text-slate-600">Automation Details</label>
          <Textarea value={form.automation_details} onChange={(e) => s("automation_details")(e.target.value)} rows={2} className="mt-1" data-testid="pf-automation" />
        </div>
        <div>
          <label className="text-xs text-slate-600">Support Details</label>
          <Textarea value={form.support_details} onChange={(e) => s("support_details")(e.target.value)} rows={2} className="mt-1" data-testid="pf-support" />
        </div>
      </div>

      {/* Dynamic Lists */}
      <div className="space-y-4 border-b border-slate-100 pb-4">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Inclusions & Requirements</h4>
        <DynamicStringList label="What's Included" items={form.inclusions} onChange={s("inclusions")} placeholder="Included item" testId="pf-inc" />
        <DynamicStringList label="What's NOT Included" items={form.exclusions} onChange={s("exclusions")} placeholder="Excluded item" testId="pf-exc" />
        <DynamicStringList label="What We Need From You" items={form.requirements} onChange={s("requirements")} placeholder="Required input" testId="pf-req" />
        <DynamicStringList label="Next Steps" items={form.next_steps} onChange={s("next_steps")} placeholder="Next step" testId="pf-next" />
      </div>

      {/* FAQs */}
      <div className="border-b border-slate-100 pb-4">
        <FAQList faqs={form.faqs} onChange={s("faqs")} />
      </div>

      {/* Pricing */}
      <div className="space-y-3 border-b border-slate-100 pb-4">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Pricing</h4>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-slate-600">Base Price</label>
            <Input type="number" value={form.base_price} onChange={(e) => s("base_price")(parseFloat(e.target.value) || 0)} className="mt-1" data-testid="pf-price" />
          </div>
          <div>
            <label className="text-xs text-slate-600">Pricing Complexity</label>
            <Select value={form.pricing_complexity} onValueChange={s("pricing_complexity")}>
              <SelectTrigger className="mt-1" data-testid="pf-complexity"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="SIMPLE">SIMPLE — Fixed Price</SelectItem>
                <SelectItem value="COMPLEX">COMPLEX — Custom Quote</SelectItem>
                <SelectItem value="REQUEST_FOR_QUOTE">REQUEST FOR QUOTE</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={form.is_subscription}
              onChange={(e) => s("is_subscription")(e.target.checked)}
              className="w-4 h-4 rounded"
              data-testid="pf-subscription"
            />
            <span className="text-sm">Subscription (recurring billing)</span>
          </label>
        </div>
        {form.is_subscription && (
          <div>
            <label className="text-xs text-slate-600">Stripe Price ID</label>
            <Input value={form.stripe_price_id} onChange={(e) => s("stripe_price_id")(e.target.value)} placeholder="price_…" className="mt-1 font-mono text-sm" data-testid="pf-stripe-price-id" />
          </div>
        )}
        <div>
          <label className="text-xs text-slate-600">Terms & Conditions</label>
          <Select value={form.terms_id || "default"} onValueChange={(v) => s("terms_id")(v === "default" ? "" : v)}>
            <SelectTrigger className="mt-1" data-testid="pf-terms"><SelectValue placeholder="Default T&C" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="default">Default T&C</SelectItem>
              {terms.map((t) => <SelectItem key={t.id} value={t.id}>{t.title}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Visibility */}
      <div className="space-y-3 border-b border-slate-100 pb-4">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Visibility</h4>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => s("is_active")(e.target.checked)}
              className="w-4 h-4 rounded"
              data-testid="pf-active"
            />
            <span className="text-sm">Active (visible on storefront)</span>
          </label>
        </div>
        <div>
          <label className="text-xs text-slate-600">
            Visible to specific customers only — leave empty for all customers
          </label>
          {/* Typeahead search */}
          <div className="mt-2 relative">
            <Input
              placeholder="Search customer by email…"
              value={visSearch}
              onChange={(e) => setVisSearch(e.target.value)}
              className="h-9 text-sm"
              data-testid="pf-vis-search"
            />
            {filteredVisCustomers.length > 0 && (
              <div className="absolute z-10 w-full border border-slate-200 rounded bg-white shadow-md max-h-40 overflow-y-auto mt-1">
                {filteredVisCustomers.map((c) => (
                  <div
                    key={c.id}
                    onClick={() => addVisibleCustomer(c.id)}
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
          {/* Selected chips */}
          {form.visible_to_customers.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1" data-testid="pf-visibility-list">
              {form.visible_to_customers.map((custId) => {
                const c = customers.find((x) => x.id === custId);
                return (
                  <span key={custId} className="inline-flex items-center gap-1 bg-slate-100 text-slate-700 text-xs px-2 py-1 rounded-full">
                    {c?.email || c?.company_name || custId.slice(0, 8)}
                    <button
                      type="button"
                      onClick={() => removeVisibleCustomer(custId)}
                      className="text-slate-400 hover:text-red-500 font-bold"
                      data-testid={`pf-vis-remove-${custId}`}
                    >×</button>
                  </span>
                );
              })}
              <button
                type="button"
                onClick={() => s("visible_to_customers")([])}
                className="text-xs text-slate-400 hover:text-red-500 underline ml-1"
              >
                Clear all
              </button>
            </div>
          )}
          {form.visible_to_customers.length > 0 && (
            <p className="text-xs text-blue-600 font-medium mt-1">
              {form.visible_to_customers.length} customer(s) selected — product hidden from all others
            </p>
          )}
        </div>
      </div>

      {/* Intake Questions */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Intake Questions</h4>
          <span className="text-xs text-slate-400">Shown to customer on product page</span>
        </div>
        <IntakeSchemaBuilder
          schema={form.intake_schema_json}
          onChange={v => setForm({ ...form, intake_schema_json: v })}
        />
      </div>
    </div>
  );
}
