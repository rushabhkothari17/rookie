import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import api from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/sonner";
import { useCart } from "@/contexts/CartContext";
import { useAuth } from "@/contexts/AuthContext";
import { useWebsite } from "@/contexts/WebsiteContext";
import AppShell from "@/components/AppShell";
import ProductHero from "@/components/ProductHero";
import StickyPurchaseSummary from "@/components/StickyPurchaseSummary";
import SectionCard from "@/components/SectionCard";
import { displayCategory } from "@/lib/categories";
import { parseSchema, type FormField } from "@/components/FormSchemaBuilder";

// ── Dynamic form field renderer ─────────────────────────────
function DynamicField({ field, value, onChange }: {
  field: FormField; value: string; onChange: (v: string) => void;
}) {
  const common = { "data-testid": `dyn-field-${field.key}` };
  if (field.type === "textarea") {
    return <Textarea value={value} onChange={e => onChange(e.target.value)} placeholder={field.placeholder} rows={3} {...common} />;
  }
  if (field.type === "select") {
    return (
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger {...common}><SelectValue placeholder="Select…" /></SelectTrigger>
        <SelectContent>
          {(field.options || []).map(opt => {
            const [label, val] = opt.includes("|") ? opt.split("|") : [opt, opt];
            return <SelectItem key={val} value={val}>{label}</SelectItem>;
          })}
        </SelectContent>
      </Select>
    );
  }
  if (field.type === "checkbox") {
    return (
      <label className="flex items-center gap-2 cursor-pointer" {...common}>
        <Checkbox checked={value === "true"} onCheckedChange={c => onChange(c ? "true" : "false")} />
        <span className="text-sm text-slate-600">{field.placeholder || field.label}</span>
      </label>
    );
  }
  return (
    <Input type={field.type === "password" ? "password" : field.type === "number" ? "number" : field.type === "date" ? "date" : "text"}
      value={value} onChange={e => onChange(e.target.value)} placeholder={field.placeholder} {...common} />
  );
}

const QUOTE_STD = ["name", "email", "company", "phone", "message"];
const SCOPE_STD = ["project_summary", "desired_outcomes", "apps_involved", "timeline_urgency", "budget_range", "additional_notes"];

// ── Intake helpers ──────────────────────────────────────────
function getEnabledIntakeQuestions(schema: any): any[] {
  if (!schema?.questions) return [];
  const result: any[] = [];
  for (const qtype of ["dropdown", "multiselect", "single_line", "multi_line"]) {
    const qs = (schema.questions[qtype] || [])
      .filter((q: any) => q.enabled)
      .sort((a: any, b: any) => (a.order ?? 0) - (b.order ?? 0));
    result.push(...qs.map((q: any) => ({ ...q, qtype })));
  }
  return result;
}

function renderIntakeField(q: any, value: any, onChange: (v: any) => void) {
  if (q.qtype === "dropdown") {
    return (
      <Select value={value || ""} onValueChange={onChange}>
        <SelectTrigger data-testid={`intake-${q.key}`}>
          <SelectValue placeholder={`Select…`} />
        </SelectTrigger>
        <SelectContent>
          {(q.options || []).map((opt: any) => (
            <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
          ))}
        </SelectContent>
      </Select>
    );
  }
  if (q.qtype === "multiselect") {
    const selected: string[] = Array.isArray(value) ? value : [];
    return (
      <div className="space-y-2" data-testid={`intake-${q.key}`}>
        {(q.options || []).map((opt: any) => (
          <label key={opt.value} className="flex items-center gap-2 text-sm cursor-pointer">
            <Checkbox
              checked={selected.includes(opt.value)}
              onCheckedChange={(checked) =>
                onChange(checked ? [...selected, opt.value] : selected.filter((v: string) => v !== opt.value))
              }
            />
            {opt.label}
          </label>
        ))}
      </div>
    );
  }
  if (q.qtype === "multi_line") {
    return (
      <Textarea
        value={value || ""}
        onChange={e => onChange(e.target.value)}
        placeholder={q.helper_text || ""}
        rows={3}
        data-testid={`intake-${q.key}`}
      />
    );
  }
  return (
    <Input
      value={value || ""}
      onChange={e => onChange(e.target.value)}
      placeholder={q.helper_text || ""}
      data-testid={`intake-${q.key}`}
    />
  );
}

const renderInputField = (
  field: any,
  value: any,
  onChange: (value: any) => void,
) => {
  if (field.type === "select") {
    return (
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger data-testid={`product-input-${field.id}`}>
          <SelectValue placeholder={field.label} />
        </SelectTrigger>
        <SelectContent>
          {field.options.map((option: any) => (
            <SelectItem
              key={option.id}
              value={option.id}
              data-testid={`product-input-${field.id}-${option.id}`}
            >
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    );
  }
  if (field.type === "checkbox") {
    return (
      <label className="flex items-center gap-2 text-sm text-slate-600">
        <Checkbox
          checked={Boolean(value)}
          onCheckedChange={(checked) => onChange(Boolean(checked))}
          data-testid={`product-input-${field.id}`}
        />
        {field.label}
      </label>
    );
  }
  return (
    <Input
      type="number"
      min={field.min}
      max={field.max}
      step={field.step}
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value)}
      data-testid={`product-input-${field.id}`}
    />
  );
};

export default function ProductDetail() {
  const { productId } = useParams();
  const navigate = useNavigate();
  const { addItem } = useCart();
  const { customer } = useAuth();
  const ws = useWebsite();
  const [product, setProduct] = useState<any>(null);
  const [inputs, setInputs] = useState<Record<string, any>>({});
  const [intakeAnswers, setIntakeAnswers] = useState<Record<string, any>>({});
  const [pricing, setPricing] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [showScopeModal, setShowScopeModal] = useState(false);
  const [showQuoteModal, setShowQuoteModal] = useState(false);
  const [quoteFormData, setQuoteFormData] = useState<Record<string, string>>({ name: "", email: "", company: "", phone: "", message: "" });
  const [submittingQuote, setSubmittingQuote] = useState(false);
  // Scope ID unlock state
  const [scopeId, setScopeId] = useState("");
  const [scopeValidating, setScopeValidating] = useState(false);
  const [scopeUnlock, setScopeUnlock] = useState<any>(null);
  const [scopeError, setScopeError] = useState("");
  const [scopeFormData, setScopeFormData] = useState<Record<string, string>>({
    project_summary: "", desired_outcomes: "", apps_involved: "",
    timeline_urgency: "", budget_range: "", additional_notes: "",
  });
  const [submittingScope, setSubmittingScope] = useState(false);
  const [contactEmail, setContactEmail] = useState("");
  const [websiteUrl, setWebsiteUrl] = useState("");

  useEffect(() => {
    api.get("/settings/public").then((res) => {
      const s = res.data.settings || {};
      if (s.contact_email) setContactEmail(s.contact_email);
      if (s.website_url) setWebsiteUrl(s.website_url);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    const load = async () => {
      try {
        const response = await api.get(`/products/${productId}`);
        setProduct(response.data.product);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [productId]);

  useEffect(() => {
    if (!product) return;
    const initialInputs: Record<string, any> = {};
    product.price_inputs?.forEach((field: any) => {
      if (field.type === "select") {
        initialInputs[field.id] = field.options?.[0]?.id || "";
      } else if (field.type === "checkbox") {
        initialInputs[field.id] = false;
      } else {
        initialInputs[field.id] = field.min ?? "";
      }
    });
    setInputs(initialInputs);
  }, [product]);

  // Compute enabled intake questions & initialise answers with defaults
  const enabledIntakeQuestions = useMemo(() => getEnabledIntakeQuestions(product?.intake_schema_json), [product]);

  useEffect(() => {
    if (!enabledIntakeQuestions.length) return;
    const defaults: Record<string, any> = {};
    for (const q of enabledIntakeQuestions) {
      if (q.qtype === "multiselect") defaults[q.key] = [];
      else if (q.qtype === "dropdown") defaults[q.key] = q.options?.[0]?.value || "";
      else defaults[q.key] = "";
    }
    setIntakeAnswers(defaults);
  }, [product]);

  const fetchPricing = async (nextInputs: Record<string, any>) => {
    if (!product) return;
    if (product.pricing_type === "inquiry") return; // inquiry products have no calculator
    const response = await api.post("/pricing/calc", {
      product_id: product.id,
      inputs: { ...nextInputs, ...intakeAnswers },
    });
    setPricing(response.data);
  };

  useEffect(() => {
    if (product) {
      fetchPricing(inputs);
    }
  }, [inputs, product, intakeAnswers]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleInputChange = (key: string, value: any) => {
    setInputs((prev) => ({ ...prev, [key]: value }));
  };

  const handleValidateScopeId = async () => {
    if (!scopeId.trim()) return;
    setScopeValidating(true);
    setScopeError("");
    setScopeUnlock(null);
    try {
      const res = await api.get(`/articles/${scopeId.trim()}/validate-scope`);
      setScopeUnlock(res.data);
    } catch (e: any) {
      setScopeError(e.response?.data?.detail || "Invalid Scope ID");
    } finally {
      setScopeValidating(false);
    }
  };

  const handleAddToCart = () => {
    // Validate required intake questions
    for (const q of enabledIntakeQuestions) {
      if (!q.required) continue;
      const val = intakeAnswers[q.key];
      const empty = q.qtype === "multiselect" ? !val || val.length === 0 : !val || val === "";
      if (empty) { toast.error(`"${q.label}" is required`); return; }
    }

    if (scopeUnlock) {
      const scopeInputs = {
        ...inputs,
        ...intakeAnswers,
        _scope_unlock: {
          scope_id: scopeUnlock.article_id,
          article_title: scopeUnlock.title,
          category: scopeUnlock.category,
          price: scopeUnlock.price,
        },
      };
      addItem({ product_id: product.id, quantity: 1, inputs: scopeInputs, price_override: scopeUnlock.price });
    } else {
      addItem({ product_id: product.id, quantity: 1, inputs: { ...inputs, ...intakeAnswers } });
    }
    toast.success("Added to cart");
    navigate("/cart");
  };

  const handleScopeRequest = () => {
    // All scope request products (including BUILD-FIXED-SCOPE) navigate to cart
    // The cart's "Quote Requests" section provides both Scope ID unlock and Request a Quote form
    addItem({ product_id: product.id, quantity: 1, inputs });
    toast.success("Added to cart");
    navigate("/cart");
  };

  const handleSubmitScopeForm = async () => {
    const scopeSchema = parseSchema(ws.scope_form_schema).filter(f => f.enabled !== false);
    const requiredFields = scopeSchema.filter(f => f.required);
    for (const field of requiredFields) {
      if (!scopeFormData[field.key]) {
        toast.error(`${field.label} is required`);
        return;
      }
    }
    if (!scopeFormData.project_summary || !scopeFormData.desired_outcomes || !scopeFormData.apps_involved || !scopeFormData.timeline_urgency) {
      toast.error("Please fill in all required fields");
      return;
    }
    setSubmittingScope(true);
    try {
      const stdFields = Object.fromEntries(SCOPE_STD.map(k => [k, scopeFormData[k] || ""]));
      const extra = Object.fromEntries(Object.entries(scopeFormData).filter(([k]) => !SCOPE_STD.includes(k)));
      const response = await api.post("/orders/scope-request-form", {
        items: [{ product_id: product.id, quantity: 1, inputs }],
        form_data: { ...stdFields, extra_fields: Object.keys(extra).length ? extra : undefined },
      });
      toast.success(ws.msg_scope_success || `Scope request submitted! Order: ${response.data.order_number}`);
      setShowScopeModal(false);
      navigate("/portal");
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to submit scope request");
    } finally { setSubmittingScope(false); }
  };

  // isRFQ: product shows "price on request" when pricing returns 0 with no base price
  const isRFQ = !pricing?.is_scope_request && pricing !== null &&
    (pricing?.total === 0 || (!product?.base_price && !pricing?.total));

  const handleSubmitQuote = async () => {
    if (!quoteFormData.name || !quoteFormData.email) {
      toast.error("Name and email are required");
      return;
    }
    setSubmittingQuote(true);
    try {
      const stdFields = Object.fromEntries(QUOTE_STD.map(k => [k, quoteFormData[k] || ""]));
      const extra = Object.fromEntries(Object.entries(quoteFormData).filter(([k]) => !QUOTE_STD.includes(k)));
      await api.post("/products/request-quote", {
        product_id: product.id,
        product_name: product.name,
        ...stdFields,
        ...(Object.keys(extra).length ? { extra_fields: extra } : {}),
      });
      toast.success(ws.msg_quote_success || "Quote request submitted! We'll be in touch shortly.");
      setShowQuoteModal(false);
      setQuoteFormData({ name: "", email: "", company: "", phone: "", message: "" });
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to submit quote request");
    } finally { setSubmittingQuote(false); }
  };

  const requiresStripePrice =
    pricing?.is_subscription && !product?.stripe_price_id;

  const ctaConfig = useMemo(() => {
    if (!product || (!pricing && product.sku !== "MIG-BOOKS")) {
      return { label: "Add to cart" };
    }
    if (product.sku === "MIG-BOOKS") {
      return {
        label: migBooksData.isComplete ? "Add to cart" : "Complete form to add to cart",
        onClick: migBooksData.isComplete ? handleAddToCart : undefined,
        disabled: !migBooksData.isComplete,
      };
    }
    if (isRFQ) {
      // If scope has been unlocked, switch CTA to Add to cart with the unlocked price
      if (scopeUnlock) {
        return { label: `Add to cart — $${scopeUnlock.price}`, onClick: handleAddToCart };
      }
      // Otherwise navigate to cart — the cart page has Scope ID unlock + Request a Quote
      return {
        label: "Proceed to checkout",
        onClick: () => {
          addItem({ product_id: product.id, quantity: 1, inputs: { ...inputs, ...intakeAnswers } });
          toast.success("Added to cart");
          navigate("/cart");
        },
      };
    }
    // Fallback: no payment methods configured — force quote request
    if (!ws.stripe_enabled && !ws.gocardless_enabled && product.pricing_type === "fixed") {
      return { label: "Request a Quote", onClick: () => setShowQuoteModal(true) };
    }
    if (product.pricing_type === "external") {
      return { label: "Add to cart", onClick: handleAddToCart };
    }
    if (product.pricing_type === "inquiry") {
      return {
        label: "Contact sales",
        href: `mailto:${contactEmail}`,
      };
    }
    if (pricing?.is_scope_request || product.pricing_type === "scope_request") {
      // If a Scope ID has been validated, switch CTA to Add to cart with the unlocked price
      if (scopeUnlock) {
        return { label: `Add to cart — $${scopeUnlock.price}`, onClick: handleAddToCart };
      }
      return { label: "Proceed to checkout", onClick: handleScopeRequest };
    }
    return { label: "Add to cart", onClick: handleAddToCart };
  }, [product, pricing, isRFQ, migBooksData, scopeUnlock]);

  if (loading) {
    return (
      <AppShell activeCategory={null}>
        <div className="flex items-center justify-center py-20" data-testid="product-loading">
          Loading...
        </div>
      </AppShell>
    );
  }

  if (!product) {
    return (
      <AppShell activeCategory={null}>
        <div className="text-sm text-slate-600" data-testid="product-not-found">
          Product not found
        </div>
      </AppShell>
    );
  }

  const categoryLabel = displayCategory(product.category);

  return (
    <AppShell activeCategory={categoryLabel}>
      <div className="space-y-8" data-testid="product-detail">
        <div className="grid gap-8 lg:grid-cols-[1.4fr_0.9fr]">
          <div className="flex flex-col gap-6">
            <ProductHero product={product} />

            {product.sku === "MIG-BOOKS" && (
              <SectionCard title="Migration Details" testId="books-migration-config">
                <BooksMigrationForm
                  onChange={setMigBooksData}
                  initialValues={{}}
                  websiteUrl={websiteUrl}
                  pricingRules={product.pricing_rules || {}}
                />
              </SectionCard>
            )}

            {product.sku !== "MIG-BOOKS" && product.price_inputs?.length > 0 && (
              <SectionCard title="Configure pricing" testId="product-input-card">
                <div className="space-y-3">
                  {product.price_inputs?.map((field: any) => (
                    <div key={field.id} className="space-y-2">
                      <label className="text-sm text-slate-600">{field.label}</label>
                      {renderInputField(field, inputs[field.id], (value) =>
                        handleInputChange(field.id, value),
                      )}
                    </div>
                  ))}
                </div>
              </SectionCard>
            )}

            {enabledIntakeQuestions.length > 0 && (
              <SectionCard title="Tell us about your project" testId="product-intake-section">
                <div className="space-y-4">
                  {enabledIntakeQuestions.map((q: any) => (
                    <div key={q.key} className="space-y-1.5" data-testid={`intake-field-${q.key}`}>
                      <label className="text-sm font-medium text-slate-700">
                        {q.label}
                        {q.required && <span className="text-red-500 ml-1">*</span>}
                      </label>
                      {q.helper_text && (
                        <p className="text-xs text-slate-400">{q.helper_text}</p>
                      )}
                      {renderIntakeField(
                        q,
                        intakeAnswers[q.key],
                        (v: any) => setIntakeAnswers(prev => ({ ...prev, [q.key]: v }))
                      )}
                    </div>
                  ))}
                </div>
              </SectionCard>
            )}

            {/* Scope ID Unlock — for RFQ products AND scope_request products (not MIG-BOOKS or BUILD-FIXED-SCOPE) */}
            {(isRFQ || pricing?.is_scope_request || product.pricing_type === "scope_request") && product.sku !== "MIG-BOOKS" && product.sku !== "BUILD-FIXED-SCOPE" && (
              <SectionCard title="Unlock with Scope ID" testId="scope-id-card">
                <div className="space-y-3">
                  <p className="text-sm text-slate-500">
                    If you have received a finalized scope document, enter the Scope ID below to unlock pricing and proceed to checkout. Otherwise, submit an enquiry to proceed.
                  </p>
                  <div className="flex gap-2">
                    <Input
                      value={scopeId}
                      onChange={(e) => { setScopeId(e.target.value); setScopeUnlock(null); setScopeError(""); }}
                      placeholder="Enter Scope ID"
                      className="flex-1 font-mono text-sm"
                      data-testid="scope-id-input"
                    />
                    <Button
                      variant="outline"
                      onClick={handleValidateScopeId}
                      disabled={scopeValidating || !scopeId.trim()}
                      data-testid="scope-id-validate-btn"
                    >
                      {scopeValidating ? "Checking…" : "Validate"}
                    </Button>
                  </div>
                  {scopeError && (
                    <p className="text-sm text-red-600" data-testid="scope-id-error">{scopeError.includes("Invalid") ? "Invalid Scope Id" : scopeError}</p>
                  )}
                  {scopeUnlock && (
                    <div className="rounded-lg bg-green-50 border border-green-200 p-3 space-y-1" data-testid="scope-id-success">
                      <p className="text-sm font-semibold text-green-800">Scope unlocked</p>
                      <p className="text-xs text-green-700">{scopeUnlock.title}</p>
                      <p className="text-sm font-bold text-green-800">${scopeUnlock.price}</p>
                    </div>
                  )}
                </div>
              </SectionCard>
            )}

            {/* ── Custom sections ── */}
            {(product.custom_sections || []).map((sec: any, i: number) => (
              <SectionCard
                key={sec.id || i}
                title={sec.name}
                testId={`custom-section-${i}`}
                icon={sec.icon}
                iconColor={sec.icon_color}
              >
                {sec.content ? (
                  <div className="prose prose-sm max-w-none text-slate-600 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:my-0.5">
                    <ReactMarkdown>{sec.content}</ReactMarkdown>
                  </div>
                ) : (
                  <span className="text-slate-400 italic">No content added yet.</span>
                )}
                {sec.tags?.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-3">
                    {sec.tags.map((tag: string) => (
                      <span key={tag} className="px-2 py-0.5 bg-slate-100 rounded-full text-xs text-slate-500">{tag}</span>
                    ))}
                  </div>
                )}
              </SectionCard>
            ))}

            {(product.faqs || []).length > 0 && (
              <SectionCard title="FAQs" testId="product-faqs">
                <div className="space-y-5" data-testid="product-faqs-list">
                  {(product.faqs || []).map((item: any, i: number) =>
                    typeof item === "string" ? (
                      <p key={i} className="leading-relaxed">• {item}</p>
                    ) : (
                      <div key={i} className="space-y-1">
                        <p className="font-semibold text-slate-800">{item.question}</p>
                        <p className="text-slate-500 leading-relaxed">{item.answer}</p>
                      </div>
                    )
                  )}
                </div>
              </SectionCard>
            )}
          </div>

          <div>
            {product.sku === "MIG-BOOKS" ? (
              <StickyPurchaseSummary
                pricing={{
                  subtotal: migBooksData.price,
                  fee: 0,
                  total: migBooksData.price,
                }}
                cta={ctaConfig}
                currency={customer?.currency}
                disabled={false}
              />
            ) : scopeUnlock ? (
              <StickyPurchaseSummary
                pricing={{
                  subtotal: scopeUnlock.price,
                  fee: 0,
                  total: scopeUnlock.price,
                }}
                cta={ctaConfig}
                currency={customer?.currency}
                disabled={false}
              />
            ) : pricing ? (
              <StickyPurchaseSummary
                pricing={{
                  subtotal: pricing.subtotal,
                  fee: pricing.fee,
                  total: pricing.total,
                }}
                cta={ctaConfig}
                currency={customer?.currency}
                isRFQ={isRFQ || !!pricing?.is_scope_request}
                disabled={requiresStripePrice}
                warning={
                  requiresStripePrice
                    ? "Subscription checkout is unavailable until a Stripe price ID is configured by admin."
                    : undefined
                }
              />
            ) : (
              <div
                className="rounded-3xl border border-slate-100 bg-white p-6 text-sm text-slate-400"
                data-testid="product-summary-loading"
              >
                Calculating pricing...
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Quote Request Modal */}
      <Dialog open={showQuoteModal} onOpenChange={setShowQuoteModal}>
        <DialogContent className="max-w-md" data-testid="quote-request-modal">
          <DialogHeader>
            <DialogTitle>{ws.quote_form_title || "Request a Quote"} — {product?.name}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            {ws.quote_form_subtitle && <p className="text-sm text-slate-500">{ws.quote_form_subtitle}</p>}
            {(() => {
              const schema = parseSchema(ws.quote_form_schema).filter(f => f.enabled !== false);
              if (schema.length > 0) {
                return schema.map(field => (
                  <div key={field.id} className="space-y-1">
                    <label className="text-sm font-medium text-slate-700">
                      {field.label}{field.required && " *"}
                    </label>
                    <DynamicField
                      field={field}
                      value={quoteFormData[field.key] || ""}
                      onChange={v => setQuoteFormData(prev => ({ ...prev, [field.key]: v }))}
                    />
                  </div>
                ));
              }
              // Fallback to hardcoded fields
              return (
                <>
                  <div className="space-y-1">
                    <label className="text-sm font-medium text-slate-700">Your Name *</label>
                    <Input value={quoteFormData.name || ""} onChange={e => setQuoteFormData(p => ({ ...p, name: e.target.value }))} placeholder="Full name" data-testid="quote-name" />
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium text-slate-700">Email *</label>
                    <Input type="email" value={quoteFormData.email || ""} onChange={e => setQuoteFormData(p => ({ ...p, email: e.target.value }))} placeholder="your@email.com" data-testid="quote-email" />
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium text-slate-700">Company</label>
                    <Input value={quoteFormData.company || ""} onChange={e => setQuoteFormData(p => ({ ...p, company: e.target.value }))} placeholder="Company name" data-testid="quote-company" />
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium text-slate-700">Phone</label>
                    <Input value={quoteFormData.phone || ""} onChange={e => setQuoteFormData(p => ({ ...p, phone: e.target.value }))} placeholder="+1 (555) 000-0000" data-testid="quote-phone" />
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium text-slate-700">Message</label>
                    <Textarea value={quoteFormData.message || ""} onChange={e => setQuoteFormData(p => ({ ...p, message: e.target.value }))} placeholder="Tell us about your requirements…" rows={3} data-testid="quote-message" />
                  </div>
                </>
              );
            })()}
            <Button className="w-full" onClick={handleSubmitQuote} disabled={submittingQuote} data-testid="quote-submit-button">
              {submittingQuote ? "Submitting…" : "Submit Quote Request"}
            </Button>
            {ws.quote_form_response_time && (
              <p className="text-xs text-slate-400 text-center">{ws.quote_form_response_time}</p>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Scope Request Modal */}
      <Dialog open={showScopeModal} onOpenChange={setShowScopeModal}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="scope-request-modal">
          <DialogHeader>
            <DialogTitle>{ws.scope_form_title || "Request Scope"} — {product?.name}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            {ws.scope_form_subtitle && <p className="text-sm text-slate-500">{ws.scope_form_subtitle}</p>}
            {(() => {
              const schema = parseSchema(ws.scope_form_schema).filter(f => f.enabled !== false);
              if (schema.length > 0) {
                return schema.map(field => (
                  <div key={field.id} className="space-y-1">
                    <label className="text-sm font-medium text-slate-700">
                      {field.label}{field.required && " *"}
                    </label>
                    <DynamicField
                      field={field}
                      value={scopeFormData[field.key] || ""}
                      onChange={v => setScopeFormData(prev => ({ ...prev, [field.key]: v }))}
                    />
                  </div>
                ));
              }
              // Fallback hardcoded scope fields
              return (
                <>
                  <div className="space-y-1">
                    <label className="text-sm font-medium text-slate-700">Project Summary *</label>
                    <Textarea placeholder="Describe your project..." value={scopeFormData.project_summary || ""} onChange={e => setScopeFormData(p => ({ ...p, project_summary: e.target.value }))} data-testid="scope-project-summary" />
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium text-slate-700">Desired Outcomes *</label>
                    <Textarea placeholder="What do you want to achieve?" value={scopeFormData.desired_outcomes || ""} onChange={e => setScopeFormData(p => ({ ...p, desired_outcomes: e.target.value }))} data-testid="scope-desired-outcomes" />
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium text-slate-700">Apps Involved *</label>
                    <Input placeholder="e.g., CRM, accounting, email..." value={scopeFormData.apps_involved || ""} onChange={e => setScopeFormData(p => ({ ...p, apps_involved: e.target.value }))} data-testid="scope-apps-involved" />
                  </div>
                </>
              );
            })()}
            <Button className="w-full" onClick={handleSubmitScopeForm} disabled={submittingScope} data-testid="scope-submit-button">
              {submittingScope ? "Submitting..." : "Submit Scope Request"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </AppShell>
  );
}
