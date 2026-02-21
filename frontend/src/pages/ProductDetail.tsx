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
import AppShell from "@/components/AppShell";
import ProductHero from "@/components/ProductHero";
import StickyPurchaseSummary from "@/components/StickyPurchaseSummary";
import SectionCard from "@/components/SectionCard";
import IncludedList from "@/components/IncludedList";
import { displayCategory } from "@/lib/categories";
import BooksMigrationForm, { calculateBooksMigrationPrice } from "@/components/BooksMigrationForm";

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
  const [product, setProduct] = useState<any>(null);
  const [inputs, setInputs] = useState<Record<string, any>>({});
  const [pricing, setPricing] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [migBooksData, setMigBooksData] = useState<{inputs: any; price: number; isComplete: boolean}>({inputs: {}, price: 999, isComplete: false});
  const [showScopeModal, setShowScopeModal] = useState(false);
  const [showQuoteModal, setShowQuoteModal] = useState(false);
  const [quoteForm, setQuoteForm] = useState({ name: "", email: "", company: "", phone: "", message: "" });
  const [submittingQuote, setSubmittingQuote] = useState(false);
  // Scope ID unlock state
  const [scopeId, setScopeId] = useState("");
  const [scopeValidating, setScopeValidating] = useState(false);
  const [scopeUnlock, setScopeUnlock] = useState<any>(null); // validated article data
  const [scopeError, setScopeError] = useState("");
  const [scopeForm, setScopeForm] = useState({
    project_summary: "",
    desired_outcomes: "",
    apps_involved: "",
    timeline_urgency: "",
    budget_range: "",
    additional_notes: "",
  });
  const [submittingScope, setSubmittingScope] = useState(false);

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

  const fetchPricing = async (nextInputs: Record<string, any>) => {
    if (!product) return;
    if (product.sku === "MIG-BOOKS") {
      // MIG-BOOKS uses client-side pricing calculator
      return;
    }
    const response = await api.post("/pricing/calc", {
      product_id: product.id,
      inputs: nextInputs,
    });
    setPricing(response.data);
  };

  useEffect(() => {
    if (product) {
      fetchPricing(inputs);
    }
  }, [inputs, product]);

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
    if (product.sku === "MIG-BOOKS") {
      if (!migBooksData.isComplete) {
        toast.error("Please complete the required fields to get your price");
        return;
      }
      addItem({ product_id: product.id, quantity: 1, inputs: migBooksData.inputs, price_override: migBooksData.price });
    } else if (scopeUnlock) {
      // Add to cart with scope-unlocked price
      const scopeInputs = {
        ...inputs,
        _scope_unlock: {
          scope_id: scopeUnlock.article_id,
          article_title: scopeUnlock.title,
          category: scopeUnlock.category,
          price: scopeUnlock.price,
        },
      };
      addItem({ product_id: product.id, quantity: 1, inputs: scopeInputs, price_override: scopeUnlock.price });
    } else {
      addItem({ product_id: product.id, quantity: 1, inputs });
    }
    toast.success("Added to cart");
    navigate("/cart");
  };

  const handleScopeRequest = () => {
    // For Fixed-Scope Development, show modal
    if (product?.sku === "BUILD-FIXED-SCOPE" || product?.pricing_type === "scope_request") {
      setShowScopeModal(true);
    } else {
      // Regular scope request goes to cart
      addItem({ product_id: product.id, quantity: 1, inputs });
      toast.success("Added to cart");
      navigate("/cart");
    }
  };

  const handleSubmitScopeForm = async () => {
    if (!scopeForm.project_summary || !scopeForm.desired_outcomes || !scopeForm.apps_involved || !scopeForm.timeline_urgency) {
      toast.error("Please fill in all required fields");
      return;
    }
    setSubmittingScope(true);
    try {
      const response = await api.post("/orders/scope-request-form", {
        items: [{ product_id: product.id, quantity: 1, inputs }],
        form_data: scopeForm,
      });
      toast.success(`Scope request submitted! Order: ${response.data.order_number}`);
      setShowScopeModal(false);
      navigate("/portal");
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to submit scope request");
    } finally {
      setSubmittingScope(false);
    }
  };

  const isRFQ = product?.sku !== "MIG-BOOKS" && (product?.pricing_complexity === "REQUEST_FOR_QUOTE" || (product?.pricing_complexity === "COMPLEX" && (!pricing || pricing.total === 0)));

  const handleSubmitQuote = async () => {
    if (!quoteForm.name || !quoteForm.email) {
      toast.error("Name and email are required");
      return;
    }
    setSubmittingQuote(true);
    try {
      await api.post("/products/request-quote", {
        product_id: product.id,
        product_name: product.name,
        ...quoteForm,
      });
      toast.success("Quote request submitted! We'll be in touch shortly.");
      setShowQuoteModal(false);
      setQuoteForm({ name: "", email: "", company: "", phone: "", message: "" });
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to submit quote request");
    } finally {
      setSubmittingQuote(false);
    }
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
      return { label: "Request a Quote", onClick: () => setShowQuoteModal(true) };
    }
    if (product.pricing_type === "external") {
      // Legacy fallback: show as add to cart since external redirect is removed
      return { label: "Add to cart", onClick: handleAddToCart };
    }
    if (product.pricing_type === "inquiry") {
      return {
        label: "Contact sales",
        href: "mailto:hello@automateaccounts.com",
      };
    }
    if (pricing?.is_scope_request || product.pricing_type === "scope_request") {
      return { label: "Request scope", onClick: handleScopeRequest };
    }
    return { label: "Add to cart", onClick: handleAddToCart };
  }, [product, pricing, isRFQ, migBooksData]);

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

            <SectionCard title="What's included" testId="product-included">
              <IncludedList items={product.inclusions || product.bullets_included || []} testId="product-included-list" />
            </SectionCard>

            {(product.exclusions || product.bullets_excluded || []).length > 0 && (
              <SectionCard title="Not included" testId="product-excluded">
                <IncludedList
                  items={product.exclusions || product.bullets_excluded || []}
                  testId="product-excluded-list"
                  variant="excluded"
                />
              </SectionCard>
            )}

            {(product.requirements || product.bullets_needed || []).length > 0 && (
              <SectionCard title="What we need from you" testId="product-needed">
                <ul className="space-y-2.5" data-testid="product-needed-list">
                  {(product.requirements || product.bullets_needed || []).map((item: string) => (
                    <li key={item} className="flex items-start gap-2.5">
                      <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-slate-400" />
                      <span className="leading-relaxed">{item}</span>
                    </li>
                  ))}
                </ul>
              </SectionCard>
            )}

            {(product.next_steps || []).length > 0 && (
              <SectionCard title="Next steps" testId="product-next-steps">
                <ol className="space-y-3" data-testid="product-next-steps-list">
                  {(product.next_steps || []).map((item: string, index: number) => (
                    <li key={item} className="flex items-start gap-3">
                      <span className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-bold text-slate-600">
                        {index + 1}
                      </span>
                      <span className="pt-0.5 leading-relaxed">{item}</span>
                    </li>
                  ))}
                </ol>
              </SectionCard>
            )}

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
            ) : pricing ? (
              <StickyPurchaseSummary
                pricing={{
                  subtotal: pricing.subtotal,
                  fee: pricing.fee,
                  total: pricing.total,
                }}
                cta={ctaConfig}
                currency={customer?.currency}
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
            <DialogTitle>Request a Quote — {product?.name}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <p className="text-sm text-slate-500">
              Fill in your details and we'll get back to you with a custom quote.
            </p>
            <div className="space-y-1">
              <label className="text-sm font-medium text-slate-700">Your Name *</label>
              <Input value={quoteForm.name} onChange={(e) => setQuoteForm({ ...quoteForm, name: e.target.value })} placeholder="Full name" data-testid="quote-name" />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium text-slate-700">Email *</label>
              <Input type="email" value={quoteForm.email} onChange={(e) => setQuoteForm({ ...quoteForm, email: e.target.value })} placeholder="your@email.com" data-testid="quote-email" />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium text-slate-700">Company</label>
              <Input value={quoteForm.company} onChange={(e) => setQuoteForm({ ...quoteForm, company: e.target.value })} placeholder="Company name" data-testid="quote-company" />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium text-slate-700">Phone</label>
              <Input value={quoteForm.phone} onChange={(e) => setQuoteForm({ ...quoteForm, phone: e.target.value })} placeholder="+1 (555) 000-0000" data-testid="quote-phone" />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium text-slate-700">Message</label>
              <Textarea value={quoteForm.message} onChange={(e) => setQuoteForm({ ...quoteForm, message: e.target.value })} placeholder="Tell us about your requirements…" rows={3} data-testid="quote-message" />
            </div>
            <Button className="w-full" onClick={handleSubmitQuote} disabled={submittingQuote} data-testid="quote-submit-button">
              {submittingQuote ? "Submitting…" : "Submit Quote Request"}
            </Button>
            <p className="text-xs text-slate-400 text-center">
              We'll respond within 1-2 business days.
            </p>
          </div>
        </DialogContent>
      </Dialog>

      {/* Scope Request Modal */}
      <Dialog open={showScopeModal} onOpenChange={setShowScopeModal}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="scope-request-modal">
          <DialogHeader>
            <DialogTitle>Request Scope for {product?.name}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <p className="text-sm text-slate-500">
              Tell us about your project and we'll get back to you with a detailed scope, timeline, and quote.
            </p>
            <div className="space-y-1">
              <label className="text-sm font-medium text-slate-700">Project Summary *</label>
              <Textarea
                placeholder="Describe your project in a few sentences..."
                value={scopeForm.project_summary}
                onChange={(e) => setScopeForm({ ...scopeForm, project_summary: e.target.value })}
                data-testid="scope-project-summary"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium text-slate-700">Desired Outcomes *</label>
              <Textarea
                placeholder="What do you want to achieve with this project?"
                value={scopeForm.desired_outcomes}
                onChange={(e) => setScopeForm({ ...scopeForm, desired_outcomes: e.target.value })}
                data-testid="scope-desired-outcomes"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium text-slate-700">Apps Involved *</label>
              <Input
                placeholder="e.g., Zoho CRM, Zoho Books, Zoho Desk..."
                value={scopeForm.apps_involved}
                onChange={(e) => setScopeForm({ ...scopeForm, apps_involved: e.target.value })}
                data-testid="scope-apps-involved"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium text-slate-700">Timeline / Urgency *</label>
              <Select
                value={scopeForm.timeline_urgency}
                onValueChange={(v) => setScopeForm({ ...scopeForm, timeline_urgency: v })}
              >
                <SelectTrigger data-testid="scope-timeline">
                  <SelectValue placeholder="Select timeline" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="asap">ASAP (within 2 weeks)</SelectItem>
                  <SelectItem value="1-month">Within 1 month</SelectItem>
                  <SelectItem value="2-3-months">2-3 months</SelectItem>
                  <SelectItem value="flexible">Flexible / No rush</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium text-slate-700">Budget Range (optional)</label>
              <Select
                value={scopeForm.budget_range}
                onValueChange={(v) => setScopeForm({ ...scopeForm, budget_range: v })}
              >
                <SelectTrigger data-testid="scope-budget">
                  <SelectValue placeholder="Select budget range" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="under-5k">Under $5,000</SelectItem>
                  <SelectItem value="5k-10k">$5,000 - $10,000</SelectItem>
                  <SelectItem value="10k-25k">$10,000 - $25,000</SelectItem>
                  <SelectItem value="25k-50k">$25,000 - $50,000</SelectItem>
                  <SelectItem value="50k+">$50,000+</SelectItem>
                  <SelectItem value="not-sure">Not sure yet</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium text-slate-700">Additional Notes (optional)</label>
              <Textarea
                placeholder="Anything else we should know?"
                value={scopeForm.additional_notes}
                onChange={(e) => setScopeForm({ ...scopeForm, additional_notes: e.target.value })}
                data-testid="scope-additional-notes"
              />
            </div>
            <Button
              className="w-full"
              onClick={handleSubmitScopeForm}
              disabled={submittingScope}
              data-testid="scope-submit-button"
            >
              {submittingScope ? "Submitting..." : "Submit Scope Request"}
            </Button>
            <p className="text-xs text-slate-400 text-center">
              Our team will review your request and email you within 1-2 business days.
            </p>
          </div>
        </DialogContent>
      </Dialog>
    </AppShell>
  );
}
