import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
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
import { displayCategory } from "@/lib/categories";
import { parseSchema, type FormField } from "@/components/FormSchemaBuilder";
import { ProductLayout, evaluateVisibilityRule, getEnabledIntakeQuestions } from "@/pages/store/layouts";

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
        <SelectTrigger {...common}><SelectValue placeholder="Select..." /></SelectTrigger>
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

  // Filter by visibility rules using current answers (supports multi-level chaining)
  const visibleIntakeQuestions = useMemo(
    () => enabledIntakeQuestions.filter(q => 
      evaluateVisibilityRule(q.visibility_rule, intakeAnswers, enabledIntakeQuestions)
    ),
    [enabledIntakeQuestions, intakeAnswers]
  );

  useEffect(() => {
    if (!enabledIntakeQuestions.length) return;
    const defaults: Record<string, any> = {};
    for (const q of enabledIntakeQuestions) {
      if (q.type === "multiselect") defaults[q.key] = [];
      else if (q.type === "dropdown") defaults[q.key] = q.options?.[0]?.value || "";
      else defaults[q.key] = "";
    }
    setIntakeAnswers(defaults);
  }, [product]);

  const fetchPricing = async (nextInputs: Record<string, any>) => {
    if (!product) return;
    if (product.pricing_type === "enquiry") {
      // Enquiry products don't go through the pricing calculator; set a placeholder so layouts render correctly
      setPricing({ subtotal: 0, fee: 0, total: 0, line_items: [], requires_checkout: false, is_subscription: false, is_enquiry: true, external_url: null });
      return;
    }
    // Only include visible questions' answers in the pricing calculation
    const visibleAnswers: Record<string, any> = {};
    for (const q of visibleIntakeQuestions) {
      if (intakeAnswers[q.key] !== undefined) visibleAnswers[q.key] = intakeAnswers[q.key];
    }
    const response = await api.post("/pricing/calc", {
      product_id: product.id,
      inputs: { ...nextInputs, ...visibleAnswers },
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
    // Validate required visible intake questions only
    for (const q of visibleIntakeQuestions) {
      if (!q.required) continue;
      const val = intakeAnswers[q.key];
      const empty = q.type === "multiselect" ? !val || val.length === 0 : !val || val === "";
      if (empty) { toast.error(`"${q.label}" is required`); return; }
    }

    if (scopeUnlock) {
      const scopeInputs = {
        ...inputs,
        ...intakeAnswers,
        _scope_unlock: {
          scope_id: scopeUnlock.resource_id || scopeUnlock.article_id,
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
    setSubmittingScope(true);
    try {
      const stdFields = Object.fromEntries(SCOPE_STD.map(k => [k, scopeFormData[k] || ""]));
      const extra = Object.fromEntries(Object.entries(scopeFormData).filter(([k]) => !SCOPE_STD.includes(k)));
      const response = await api.post("/orders/scope-request-form", {
        items: [{ product_id: product.id, quantity: 1, inputs }],
        form_data: { ...stdFields, extra_fields: Object.keys(extra).length ? extra : undefined },
      });
      toast.success(ws.msg_scope_success || `Enquiry submitted! Reference: ${response.data.order_number}`);
      setShowScopeModal(false);
      navigate("/portal");
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to submit enquiry");
    } finally { setSubmittingScope(false); }
  };

  // isRFQ: product shows "price on request" when pricing returns 0 with no base price
  const isRFQ = !pricing?.is_enquiry && pricing !== null &&
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
      const response = await api.post("/orders/scope-request-form", {
        items: [{ product_id: product.id, quantity: 1, inputs: {} }],
        form_data: {
          name: stdFields.name,
          email: stdFields.email,
          company: stdFields.company,
          phone: stdFields.phone,
          message: stdFields.message,
          ...(Object.keys(extra).length ? { extra_fields: extra } : {}),
        },
      });
      toast.success(ws.msg_quote_success || `Enquiry submitted! Reference: ${response.data.order_number}`);
      setShowQuoteModal(false);
      setQuoteFormData({ name: "", email: "", company: "", phone: "", message: "" });
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to submit enquiry");
    } finally { setSubmittingQuote(false); }
  };

  const requiresStripePrice =
    pricing?.is_subscription && !product?.stripe_price_id;

  const ctaConfig = useMemo(() => {
    if (!product || !pricing) {
      return { label: "Add to cart" };
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
    if (product.pricing_type === "enquiry") {
      return {
        label: "Request a Quote",
        onClick: () => setShowScopeModal(true),
      };
    }
    if (pricing?.is_enquiry || product.pricing_type === "enquiry") {
      // If a Scope ID has been validated, switch CTA to Add to cart with the unlocked price
      if (scopeUnlock) {
        return { label: `Add to cart — $${scopeUnlock.price}`, onClick: handleAddToCart };
      }
      return { label: "Proceed to checkout", onClick: handleScopeRequest };
    }
    return { label: "Add to cart", onClick: handleAddToCart };
  }, [product, pricing, isRFQ, scopeUnlock]);

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
  
  // Determine terms URL if product has terms_id
  const termsUrl = product.terms_id ? `/terms/${product.terms_id}` : undefined;
  
  // Determine layout type
  const layoutType = product.display_layout || "standard";

  return (
    <AppShell activeCategory={categoryLabel}>
      <div className="space-y-8" data-testid="product-detail">
        <ProductLayout
          layoutType={layoutType}
          product={product}
          pricing={pricing}
          intakeAnswers={intakeAnswers}
          setIntakeAnswers={setIntakeAnswers}
          visibleIntakeQuestions={visibleIntakeQuestions}
          handleAddToCart={handleAddToCart}
          isRFQ={isRFQ}
          isSubscription={Boolean(product?.is_subscription)}
          termsUrl={termsUrl}
          currency={customer?.currency}
          scopeUnlock={scopeUnlock}
          scopeId={scopeId}
          setScopeId={(v) => { setScopeId(v); setScopeUnlock(null); setScopeError(""); }}
          handleValidateScopeId={handleValidateScopeId}
          scopeValidating={scopeValidating}
          scopeError={scopeError}
        />
      </div>

      {/* Quote / Enquiry Modal (for fixed-price products without payment configured) */}
      <Dialog open={showQuoteModal} onOpenChange={setShowQuoteModal}>
        <DialogContent className="max-w-md" data-testid="quote-request-modal">
          <DialogHeader>
            <DialogTitle>{ws.scope_form_title || "Request a Quote"} — {product?.name}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
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
              {submittingQuote ? "Submitting…" : "Submit Enquiry"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Scope / Enquiry Request Modal */}
      <Dialog open={showScopeModal} onOpenChange={setShowScopeModal}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="scope-request-modal">
          <DialogHeader>
            <DialogTitle>{ws.scope_form_title || "Request a Quote"} — {product?.name}</DialogTitle>
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
              {submittingScope ? "Submitting..." : "Submit Enquiry"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </AppShell>
  );
}
