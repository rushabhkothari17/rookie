import { useState, useEffect, useMemo } from "react";
import { RequiredLabel } from "@/components/shared/RequiredLabel";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import api from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/sonner";
import { useCart } from "@/contexts/CartContext";
import { useAuth } from "@/contexts/AuthContext";
import { useWebsite, usePartnerCode } from "@/contexts/WebsiteContext";
import AppShell from "@/components/AppShell";
import { displayCategory } from "@/lib/categories";
import { parseSchema, getAddressConfig } from "@/components/FormSchemaBuilder";
import { type AddressValue } from "@/components/AddressFieldRenderer";
import { UniversalFormRenderer } from "@/components/UniversalFormRenderer";
import { ProductLayout, evaluateVisibilityRule, getEnabledIntakeQuestions } from "@/pages/store/layouts";

const QUOTE_STD: string[] = [];
const SCOPE_STD: string[] = [];

export default function ProductDetail() {
  const { productId } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { addItem } = useCart();
  const { customer } = useAuth();
  const ws = useWebsite();
  const partnerCode = usePartnerCode();

  const [product, setProduct] = useState<any>(null);
  const [inputs, setInputs] = useState<Record<string, any>>({});
  const [intakeAnswers, setIntakeAnswers] = useState<Record<string, any>>({});
  const [pricing, setPricing] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  /** Build the metadata payload that CartContext uses for type/currency validation */
  const cartMeta = () => ({
    pricing_type: product?.pricing_type || "internal",
    currency: product?.currency || "USD",
    is_subscription: !!product?.is_subscription,
  });

  /** Attempt addItem — show error toast if validation fails, otherwise navigate to cart */
  const tryAddItem = (item: Parameters<typeof addItem>[0]): boolean => {
    const err = addItem({ ...item, ...cartMeta() });
    if (err) {
      toast.error(err);
      return false;
    }
    return true;
  };
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
      else if (q.type === "dropdown") defaults[q.key] = "";
      else defaults[q.key] = "";
    }
    // Pre-fill from URL search params: ?client_name=John&budget=5000
    // Any param matching an intake question key is applied
    const urlPrefill: Record<string, any> = {};
    for (const q of enabledIntakeQuestions) {
      const paramVal = searchParams.get(q.key);
      if (paramVal !== null && paramVal !== "") {
        if (q.type === "multiselect") {
          urlPrefill[q.key] = paramVal.split(",").map(s => s.trim()).filter(Boolean);
        } else if (q.type === "number") {
          const num = parseFloat(paramVal);
          urlPrefill[q.key] = isNaN(num) ? paramVal : num;
        } else {
          urlPrefill[q.key] = paramVal;
        }
      }
    }
    setIntakeAnswers({ ...defaults, ...urlPrefill });
  }, [product]);

  // Handle intake question change: update answer + clear all questions below (by order)
  const handleIntakeChange = (key: string, value: any) => {
    setIntakeAnswers(prev => {
      const changedQ = enabledIntakeQuestions.find(q => q.key === key);
      const changedOrder = changedQ?.order ?? -1;
      const newAnswers: Record<string, any> = { ...prev, [key]: value };
      // Clear every question that comes after the changed one (by display order)
      for (const q of enabledIntakeQuestions) {
        if ((q.order ?? 0) > changedOrder) {
          newAnswers[q.key] = q.type === "multiselect" ? [] : "";
        }
      }
      return newAnswers;
    });
  };

  const fetchPricing = async (nextInputs: Record<string, any>) => {
    if (!product) return;
    if (product.pricing_type === "enquiry") {
      // Enquiry products don't go through the pricing calculator; set a placeholder so layouts render correctly
      setPricing({ subtotal: 0, fee: 0, total: 0, line_items: [], requires_checkout: false, is_subscription: false, is_enquiry: true, external_url: null });
      return;
    }
    // Only include visible questions' answers in the pricing calculation
    // Skip booleans that haven't been explicitly selected (empty string = unanswered)
    const visibleAnswers: Record<string, any> = {};
    for (const q of visibleIntakeQuestions) {
      const val = intakeAnswers[q.key];
      if (q.type === "boolean" && (val === "" || val === null || val === undefined)) continue;
      if (val !== undefined) visibleAnswers[q.key] = val;
    }
    const response = await api.post("/pricing/calc", {
      product_id: product.id,
      inputs: { ...nextInputs, ...visibleAnswers },
      partner_code: partnerCode || undefined,
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
      const res = await api.get(`/resources/${scopeId.trim()}/validate-scope`);
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
      const trimmedVal = typeof val === "string" ? val.trim() : val;
      const empty = q.type === "multiselect" ? !trimmedVal || trimmedVal.length === 0 : !trimmedVal || trimmedVal === "";
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
      if (!tryAddItem({ product_id: product.id, quantity: 1, inputs: scopeInputs, price_override: scopeUnlock.price })) return;
    } else {
      if (!tryAddItem({ product_id: product.id, quantity: 1, inputs: { ...inputs, ...intakeAnswers } })) return;
    }
    toast.success("Added to cart");
    navigate("/cart");
  };

  const handleScopeRequest = () => {
    // All scope request products (including BUILD-FIXED-SCOPE) navigate to cart
    // The cart's "Quote Requests" section provides both Scope ID unlock and Request a Quote form
    if (!tryAddItem({ product_id: product.id, quantity: 1, inputs })) return;
    toast.success("Added to cart");
    navigate("/cart");
  };

  const handleSubmitScopeForm = async () => {
    // Use product's custom form schema if available, else fall back to default
    const activeSchema = product?.resolved_form_schema || ws.scope_form_schema;
    const scopeSchema = parseSchema(activeSchema).filter(f => f.enabled !== false);
    const requiredFields = scopeSchema.filter(f => f.required);
    for (const field of requiredFields) {
      if (field.type === "address") {
        const addrCfg = getAddressConfig(field);
        const addrVal: AddressValue = (() => { try { return JSON.parse(scopeFormData[field.key] || "{}"); } catch { return {}; } })();
        if (addrCfg.line1.required && !addrVal.line1) { toast.error(`${field.label}: Address Line 1 is required`); return; }
        if (addrCfg.city.required && !addrVal.city) { toast.error(`${field.label}: City is required`); return; }
        if (addrCfg.country.required && !addrVal.country) { toast.error(`${field.label}: Country is required`); return; }
        if (addrCfg.postal.required && !addrVal.postal) { toast.error(`${field.label}: Postal Code is required`); return; }
        if (addrCfg.state.required && !addrVal.region) { toast.error(`${field.label}: State/Province is required`); return; }
      } else {
        if (!scopeFormData[field.key]) {
          toast.error(`${field.label} is required`);
          return;
        }
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

  // isRFQ: product shows "price on request" only when price is genuinely unknown
  // base_price=0 means explicitly free — NOT RFQ; base_price=null/undefined = unknown price
  const isRFQ = !pricing?.is_enquiry && pricing !== null &&
    product?.base_price == null &&
    (pricing?.total === 0 || !pricing?.total);

  const handleSubmitQuote = async () => {
    // Validate required fields (if schema-driven)
    const qSchema = parseSchema(ws.scope_form_schema).filter(f => f.enabled !== false && f.required);
    if (qSchema.length > 0) {
      for (const field of qSchema) {
        if (field.type === "address") {
          const addrCfg = getAddressConfig(field);
          const addrVal: AddressValue = (() => { try { return JSON.parse(quoteFormData[field.key] || "{}"); } catch { return {}; } })();
          if (addrCfg.line1.required && !addrVal.line1) { toast.error(`${field.label}: Address Line 1 is required`); return; }
          if (addrCfg.country.required && !addrVal.country) { toast.error(`${field.label}: Country is required`); return; }
        } else if (!quoteFormData[field.key]) {
          toast.error(`${field.label} is required`); return;
        }
      }
    } else {
      // No schema configured and no hardcoded fallback — allow empty submission
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
        return { label: `Add to cart — ${new Intl.NumberFormat("en-US", { style: "currency", currency: product?.currency || "USD", minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(scopeUnlock.price)}`, onClick: handleAddToCart };
      }
      return {
        label: "Proceed to checkout",
        onClick: () => {
          if (!tryAddItem({ product_id: product.id, quantity: 1, inputs: { ...inputs, ...intakeAnswers } })) return;
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
        return { label: `Add to cart — ${new Intl.NumberFormat("en-US", { style: "currency", currency: product?.currency || "USD", minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(scopeUnlock.price)}`, onClick: handleAddToCart };
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
    <AppShell activeCategory={categoryLabel} showCategoryTabs={false}>
      <div className="space-y-8" data-testid="product-detail">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 transition-colors group"
          data-testid="product-back-button"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="group-hover:-translate-x-0.5 transition-transform"><path d="M19 12H5"/><polyline points="12 19 5 12 12 5"/></svg>
          Back
        </button>
        <ProductLayout
          layoutType={layoutType}
          product={product}
          pricing={pricing}
          intakeAnswers={intakeAnswers}
          onIntakeChange={handleIntakeChange}
          visibleIntakeQuestions={visibleIntakeQuestions}
          handleAddToCart={handleAddToCart}
          isRFQ={isRFQ}
          isSubscription={Boolean(product?.is_subscription)}
          termsUrl={termsUrl}
          currency={product?.currency}
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
                return (
                  <UniversalFormRenderer
                    fields={schema}
                    values={quoteFormData}
                    onChange={(key, val) => setQuoteFormData(prev => ({ ...prev, [key]: val }))}
                    compact={true}
                    addressMode="json"
                  />
                );
              }
              // No schema configured — render nothing (no hardcoded fallback)
              return null;
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
              const activeSchema = product?.resolved_form_schema || ws.scope_form_schema;
              const schema = parseSchema(activeSchema).filter(f => f.enabled !== false);
              if (schema.length > 0) {
                return (
                  <UniversalFormRenderer
                    fields={schema}
                    values={scopeFormData}
                    onChange={(key, val) => setScopeFormData(prev => ({ ...prev, [key]: val }))}
                    compact={true}
                    addressMode="json"
                  />
                );
              }
              // No schema configured — render nothing (no hardcoded fallback)
              return null;
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
