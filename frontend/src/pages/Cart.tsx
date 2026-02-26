import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import api from "@/lib/api";
import { useCart } from "@/contexts/CartContext";
import { useAuth } from "@/contexts/AuthContext";
import { useWebsite } from "@/contexts/WebsiteContext";
import { ShoppingCart, Trash2, Tag, CreditCard, Building2, ChevronDown, ChevronUp, X, Check, AlertCircle, FileText, Clock, ExternalLink, HelpCircle } from "lucide-react";

export default function Cart() {
  const navigate = useNavigate();
  const { items, removeItem, clear, updateItem } = useCart();
  const { customer, address } = useAuth();
  const ws = useWebsite();
  const [preview, setPreview] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState<string>("bank_transfer");
  const [promoCode, setPromoCode] = useState("");
  const [promoApplied, setPromoApplied] = useState<any>(null);
  const [promoError, setPromoError] = useState("");
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [showTermsModal, setShowTermsModal] = useState(false);
  const [termsContent, setTermsContent] = useState<any>(null);
  const [subscriptionStartDate, setSubscriptionStartDate] = useState("");
  const [futureStartEnabled, setFutureStartEnabled] = useState(false);
  const [partnerTagResponse, setPartnerTagResponse] = useState("");
  const [overrideCode, setOverrideCode] = useState("");
  const [zohoSubscriptionType, setZohoSubscriptionType] = useState("");
  const [currentZohoProduct, setCurrentZohoProduct] = useState("");
  const [zohoAccountAccess, setZohoAccountAccess] = useState("");
  const [extraFields, setExtraFields] = useState<Record<string, string>>({});
  
  // Scope ID state
  const [cartScopeId, setCartScopeId] = useState("");
  const [cartScopeValidating, setCartScopeValidating] = useState(false);
  const [cartScopeUnlock, setCartScopeUnlock] = useState<any>(null);
  const [cartScopeError, setCartScopeError] = useState("");
  
  // Quote modal for RFQ items
  const [showCartQuoteModal, setShowCartQuoteModal] = useState(false);
  const [cartQuoteProduct, setCartQuoteProduct] = useState<any>(null);
  const [cartQuoteForm, setCartQuoteForm] = useState({ name: "", email: "", company: "", phone: "", message: "" });
  const [submittingCartQuote, setSubmittingCartQuote] = useState(false);
  
  // Collapsible sections
  const [showPromoSection, setShowPromoSection] = useState(false);
  const [showCheckoutOptions, setShowCheckoutOptions] = useState(true);

  // Parse checkout sections
  const checkoutSections = useMemo(() => {
    try {
      const parsed = JSON.parse(ws.checkout_sections || "[]");
      if (Array.isArray(parsed) && parsed.length > 0) {
        return parsed.filter((s: any) => s.enabled !== false).sort((a: any, b: any) => (a.order || 0) - (b.order || 0));
      }
    } catch {}
    return null;
  }, [ws.checkout_sections]);

  const parseSectionFields = (fieldsSchema: string) => {
    try {
      const fields = JSON.parse(fieldsSchema || "[]");
      return Array.isArray(fields) ? fields.filter((f: any) => f.enabled !== false) : [];
    } catch { return []; }
  };

  const parseOptions = (options: any): string[] => {
    if (Array.isArray(options)) return options.filter(Boolean);
    if (typeof options === "string") return options.split("\n").map(s => s.trim()).filter(Boolean);
    return [];
  };

  const parseOptionItem = (opt: string): { label: string; value: string } => {
    const pipeIdx = opt.indexOf("|");
    if (pipeIdx === -1) return { label: opt.trim(), value: opt.trim() };
    return { label: opt.slice(0, pipeIdx).trim(), value: opt.slice(pipeIdx + 1).trim() || opt.slice(0, pipeIdx).trim() };
  };

  const sectionRequiredFieldsMissing = useMemo(() => {
    if (!checkoutSections) return false;
    return checkoutSections.some((section: any) => {
      const fields = parseSectionFields(section.fields_schema);
      return fields.some((f: any) => f.required && !extraFields[f.id || f.key || f.name]);
    });
  }, [checkoutSections, extraFields]);

  // Load cart preview
  useEffect(() => {
    if (items.length === 0) { setPreview(null); return; }
    const loadPreview = async () => {
      try {
        const r = await api.post("/orders/preview", { items: items.map(i => ({ product_id: i.product_id, quantity: i.quantity, inputs: i.inputs })) });
        setPreview(r.data);
      } catch { toast.error("Failed to load cart preview"); }
    };
    loadPreview();
  }, [items]);

  // Load terms
  useEffect(() => {
    const loadTerms = async () => {
      try {
        const r = await api.get("/terms/default");
        setTermsContent(r.data);
      } catch {}
    };
    loadTerms();
  }, []);

  // Group items by type
  const grouped = useMemo(() => {
    if (!preview) return { oneTime: [], subscriptions: [], scope: [], rfq: [], external: [], inquiry: [] };
    const groups: any = { oneTime: [], subscriptions: [], scope: [], rfq: [], external: [], inquiry: [] };
    preview.items.forEach((item: any) => {
      const p = item.product;
      if (p.product_type === "scope_request") groups.scope.push(item);
      else if (p.product_type === "external_checkout") groups.external.push(item);
      else if (p.product_type === "enquiry") groups.inquiry.push(item);
      else if (item.pricing.subtotal === 0 && !item.inputs?._scope_unlock) groups.rfq.push(item);
      else if (p.is_subscription) groups.subscriptions.push(item);
      else groups.oneTime.push(item);
    });
    return groups;
  }, [preview]);

  // Payment settings
  const allowBankTransfer = ws.gocardless_enabled !== false;
  const allowCardPayment = ws.stripe_enabled !== false;
  const stripeFeeRate = ws.stripe_fee_rate || 0.029;
  const stripeFeePercent = Math.round(stripeFeeRate * 1000) / 10; // Convert to percentage for display
  const showFee = paymentMethod === "card";
  const currencyUnsupported = preview?.currency && !["USD", "CAD"].includes(preview.currency);
  const subscriptionMissingPrice = grouped.subscriptions.some((i: any) => !i.product.stripe_price_id);

  // Calculate totals
  const oneTimeSubtotal = grouped.oneTime.reduce((sum: number, item: any) => sum + item.pricing.subtotal, 0);
  const subscriptionSubtotal = grouped.subscriptions.reduce((sum: number, item: any) => sum + item.pricing.subtotal, 0);
  const totalSubtotal = oneTimeSubtotal + subscriptionSubtotal;
  
  let discountAmount = 0;
  if (promoApplied) {
    if (promoApplied.discount_type === "percent") {
      discountAmount = Math.round(totalSubtotal * promoApplied.discount_value) / 100;
    } else {
      discountAmount = Math.min(promoApplied.discount_value, totalSubtotal);
    }
  }
  
  const discountedSubtotal = totalSubtotal - discountAmount;
  const fee = showFee ? Math.round(discountedSubtotal * stripeFeeRate * 100) / 100 : 0;
  const total = discountedSubtotal + fee;
  const isFreeCheckout = total <= 0 && grouped.oneTime.length > 0;

  // Handlers
  const handleApplyPromo = async () => {
    if (!promoCode.trim()) return;
    setPromoError("");
    try {
      const productIds = items.map((i: any) => i.productId || i.product_id || i.id).filter(Boolean);
      const checkoutType = items.some((i: any) => i.is_subscription || i.pricing?.is_subscription) ? "subscription" : "one_time";
      const r = await api.post("/promo/validate", { code: promoCode.trim(), checkout_type: checkoutType, product_ids: productIds });
      setPromoApplied(r.data.promo || r.data);
      setPromoCode("");
      toast.success("Promo code applied!");
    } catch (e: any) {
      setPromoError(e.response?.data?.detail || "Invalid promo code");
    }
  };

  const handleRemovePromo = () => {
    setPromoApplied(null);
    setPromoError("");
  };

  const handleValidateCartScopeId = async () => {
    if (!cartScopeId.trim()) return;
    setCartScopeValidating(true);
    setCartScopeError("");
    setCartScopeUnlock(null);
    try {
      const r = await api.post("/scope/validate", { scope_id: cartScopeId.trim() });
      setCartScopeUnlock(r.data);
    } catch (e: any) {
      setCartScopeError(e.response?.data?.detail || "Invalid Scope ID");
    } finally {
      setCartScopeValidating(false);
    }
  };

  const handleApplyScopeToCart = async () => {
    if (!cartScopeUnlock) return;
    try {
      const scopeItem = grouped.scope[0] || grouped.rfq[0];
      if (scopeItem) {
        updateItem(scopeItem.product.id, {
          ...scopeItem,
          inputs: { ...(scopeItem.inputs || {}), _scope_unlock: cartScopeUnlock },
          price_override: cartScopeUnlock.price,
        });
        toast.success("Scope applied! You can now proceed to checkout.");
        setCartScopeId("");
        setCartScopeUnlock(null);
      }
    } catch {
      toast.error("Failed to apply scope");
    }
  };

  const handleScopeRequest = async () => {
    setLoading(true);
    try {
      const scopeItems = grouped.scope.map((i: any) => ({ product_id: i.product.id, quantity: i.quantity, inputs: i.inputs }));
      await api.post("/scope/request", { items: scopeItems });
      toast.success("Scope request submitted! We'll be in touch soon.");
      grouped.scope.forEach((i: any) => removeItem(i.product.id));
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to submit scope request");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitCartQuote = async () => {
    if (!cartQuoteProduct || !cartQuoteForm.name || !cartQuoteForm.email) return;
    setSubmittingCartQuote(true);
    try {
      await api.post("/quote-requests", {
        product_id: cartQuoteProduct.id,
        name: cartQuoteForm.name,
        email: cartQuoteForm.email,
        company: cartQuoteForm.company,
        phone: cartQuoteForm.phone,
        message: cartQuoteForm.message,
      });
      toast.success("Quote request submitted!");
      setShowCartQuoteModal(false);
      setCartQuoteForm({ name: "", email: "", company: "", phone: "", message: "" });
      removeItem(cartQuoteProduct.id);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to submit quote request");
    } finally {
      setSubmittingCartQuote(false);
    }
  };

  const handleCheckout = async (groupItems: any[], checkoutType: string) => {
    if (!termsAccepted) {
      toast.error("Please accept the Terms & Conditions to proceed");
      return;
    }
    if (!checkoutSections) {
      if (ws.checkout_partner_enabled !== false && !partnerTagResponse) {
        toast.error(ws.msg_partner_tagging_prompt || "Please select whether you have tagged us as your partner");
        return;
      }
      if (ws.checkout_partner_enabled !== false && partnerTagResponse === "Not yet" && !overrideCode.trim()) {
        toast.error(ws.msg_override_required || "An override code is required");
        return;
      }
    }
    if (checkoutSections && sectionRequiredFieldsMissing) {
      toast.error("Please complete all required fields");
      return;
    }
    if (checkoutSections && extraFields['partner_tag_response'] === 'Not yet' && !overrideCode.trim()) {
      toast.error(ws.msg_override_required || "An override code is required");
      return;
    }

    const partnerTag = checkoutSections ? (extraFields['partner_tag_response'] || null) : (partnerTagResponse || null);
    const overrideVal = partnerTag === 'Not yet' ? overrideCode.trim() : null;
    const zohoSubType = checkoutSections ? (extraFields['zoho_subscription_type'] || null) : zohoSubscriptionType;
    const zohoProduct = checkoutSections ? (extraFields['current_zoho_product'] || null) : currentZohoProduct;
    const zohoAccess = checkoutSections ? (extraFields['zoho_account_access'] || null) : zohoAccountAccess;

    const groupSubtotal = groupItems.reduce((sum: number, item: any) => sum + item.pricing.subtotal, 0);
    let groupDiscount = 0;
    if (promoApplied) {
      if (promoApplied.discount_type === "percent") groupDiscount = Math.round(groupSubtotal * promoApplied.discount_value) / 100;
      else groupDiscount = Math.min(promoApplied.discount_value, groupSubtotal);
    }
    const isFree = (groupSubtotal - groupDiscount) <= 0;

    setLoading(true);
    try {
      const checkoutPayload = {
        items: groupItems.map((item) => {
          const cartItem = items.find((ci) => ci.product_id === item.product.id);
          return {
            product_id: item.product.id,
            quantity: item.quantity,
            inputs: item.inputs,
            ...(cartItem?.price_override != null ? { price_override: cartItem.price_override } : {}),
          };
        }),
        checkout_type: checkoutType,
        promo_code: promoApplied?.code || null,
        terms_accepted: termsAccepted,
        terms_id: termsContent?.id || null,
        start_date: checkoutType === "subscription" && futureStartEnabled && subscriptionStartDate ? subscriptionStartDate : null,
        partner_tag_response: partnerTag,
        override_code: overrideVal,
        zoho_subscription_type: zohoSubType,
        current_zoho_product: zohoProduct,
        zoho_account_access: zohoAccess,
        extra_fields: Object.keys(extraFields).length ? extraFields : undefined,
      };

      if (isFree && checkoutType === "one_time") {
        const response = await api.post("/checkout/free", checkoutPayload);
        toast.success("Order completed successfully!");
        clear();
        navigate(`/checkout/success?order=${response.data.order_number || ""}&free=true`);
        return;
      }

      if (paymentMethod === "bank_transfer") {
        const response = await api.post("/checkout/bank-transfer", checkoutPayload);
        if (response.data.gocardless_redirect_url) {
          toast.success("Redirecting to Direct Debit setup...");
          clear();
          window.location.href = response.data.gocardless_redirect_url;
        } else {
          toast.success("Order created successfully");
          clear();
          navigate(`/checkout/bank-transfer?order=${response.data.order_number || ""}`);
        }
      } else {
        const response = await api.post("/checkout/session", { ...checkoutPayload, origin_url: window.location.origin });
        window.location.href = response.data.url;
      }
    } catch (error: any) {
      let errorMsg = "Checkout failed. Please try again.";
      if (error.response?.data) {
        const data = error.response.data;
        if (typeof data.detail === 'string') errorMsg = data.detail;
        else if (Array.isArray(data.detail)) errorMsg = data.detail.map((e: any) => e.msg || e.message || JSON.stringify(e)).join(", ");
      }
      toast.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  // Check if there are enquiry products that need Scope ID
  const hasEnquiryProducts = grouped.inquiry.length > 0 || grouped.scope.length > 0;

  if (items.length === 0) {
    return (
      <div className="space-y-8" data-testid="cart-empty">
        {/* Hero Banner - matches Store */}
        <section
          className="relative overflow-hidden rounded-3xl px-10 py-12 shadow-[0_30px_70px_rgba(15,23,42,0.15)]"
          style={{ backgroundColor: "var(--aa-primary)" }}
        >
          <div className="pointer-events-none absolute -right-24 -top-24 h-80 w-80 rounded-full blur-3xl" style={{ backgroundColor: "color-mix(in srgb, var(--aa-accent) 10%, transparent)" }} />
          <div className="pointer-events-none absolute bottom-0 left-0 h-56 w-56 rounded-full blur-2xl" style={{ backgroundColor: "color-mix(in srgb, var(--aa-accent) 5%, transparent)" }} />
          <div className="relative space-y-4">
            <div className="flex items-center gap-2.5">
              <div className="h-0.5 w-8 rounded-full" style={{ backgroundColor: "var(--aa-accent)" }} />
              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Checkout</p>
            </div>
            <h1 className="text-4xl font-bold text-white">{ws.cart_title || "Shopping Cart"}</h1>
          </div>
        </section>

        {/* Empty state */}
        <div className="flex flex-col items-center justify-center text-center py-16">
          <div className="w-20 h-20 rounded-full flex items-center justify-center mb-6" style={{ backgroundColor: "color-mix(in srgb, var(--aa-primary) 10%, transparent)" }}>
            <ShoppingCart className="w-10 h-10" style={{ color: "var(--aa-primary)" }} />
          </div>
          <h2 className="text-2xl font-semibold text-slate-900 mb-2">Your cart is empty</h2>
          <p className="text-slate-500 mb-6 max-w-md">Looks like you haven't added anything to your cart yet. Browse our products and find something you'll love.</p>
          <Button 
            onClick={() => navigate("/store")} 
            className="text-white hover:opacity-90 transition-all"
            style={{ backgroundColor: "var(--aa-primary)" }}
            data-testid="cart-browse-btn"
          >
            Browse Products
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8" data-testid="cart-page">
      {/* Hero Banner - matches Store */}
      <section
        className="relative overflow-hidden rounded-3xl px-10 py-12 shadow-[0_30px_70px_rgba(15,23,42,0.15)]"
        style={{ backgroundColor: "var(--aa-primary)" }}
        data-testid="cart-hero"
      >
        <div className="pointer-events-none absolute -right-24 -top-24 h-80 w-80 rounded-full blur-3xl" style={{ backgroundColor: "color-mix(in srgb, var(--aa-accent) 10%, transparent)" }} />
        <div className="pointer-events-none absolute bottom-0 left-0 h-56 w-56 rounded-full blur-2xl" style={{ backgroundColor: "color-mix(in srgb, var(--aa-accent) 5%, transparent)" }} />
        <div className="relative flex items-center justify-between">
          <div className="space-y-4">
            <div className="flex items-center gap-2.5">
              <div className="h-0.5 w-8 rounded-full" style={{ backgroundColor: "var(--aa-accent)" }} />
              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Checkout</p>
            </div>
            <h1 className="text-4xl font-bold text-white">{ws.cart_title || "Shopping Cart"}</h1>
            <p className="text-slate-300">{preview?.items?.length || 0} item{(preview?.items?.length || 0) !== 1 ? 's' : ''} in your cart</p>
          </div>
          <Button 
            variant="outline" 
            size="sm" 
            onClick={clear} 
            className="border-white/30 text-white hover:bg-white/10 gap-2" 
            data-testid="cart-clear-button"
          >
            <Trash2 size={16} />
            Clear All
          </Button>
        </div>
      </section>

      {currencyUnsupported && (
        <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4" data-testid="cart-currency-block">
          <AlertCircle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-amber-800">Currency Not Supported</p>
            <p className="text-sm text-amber-700 mt-1">{ws.msg_currency_unsupported || "Purchases are not supported in your region yet. Please contact admin for an override."}</p>
          </div>
        </div>
      )}

      {preview && (
        <div className="grid gap-8 lg:grid-cols-[1fr_380px]">
          {/* Main Content */}
          <div className="space-y-6">
            {/* Cart Items */}
            <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-sm">
              <div className="p-4 border-b border-slate-100 bg-slate-50/50">
                <h2 className="font-semibold text-slate-900">Cart Items</h2>
              </div>
              <div className="divide-y divide-slate-100">
                {[...grouped.oneTime, ...grouped.subscriptions].map((item: any) => (
                  <div key={item.product.id} className="p-4 hover:bg-slate-50/50 transition-colors" data-testid={`cart-item-${item.product.id}`}>
                    <div className="flex gap-4">
                      {item.product.image_url && (
                        <div className="w-16 h-16 rounded-xl bg-slate-100 overflow-hidden flex-shrink-0 shadow-sm">
                          <img src={item.product.image_url} alt="" className="w-full h-full object-cover" />
                        </div>
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <h3 className="font-medium text-slate-900" data-testid={`cart-item-name-${item.product.id}`}>{item.product.name}</h3>
                            {item.product.tagline && <p className="text-sm text-slate-500 mt-0.5">{item.product.tagline}</p>}
                            {item.product.is_subscription && (
                              <span className="inline-flex items-center gap-1 mt-2 px-2 py-0.5 rounded-full text-xs font-medium" style={{ backgroundColor: "color-mix(in srgb, var(--aa-accent) 15%, transparent)", color: "var(--aa-accent)" }}>
                                <Clock size={12} /> Subscription
                              </span>
                            )}
                          </div>
                          <div className="text-right">
                            <p className="font-semibold text-slate-900" data-testid={`cart-item-total-${item.product.id}`}>
                              ${(showFee ? item.pricing.total : item.pricing.subtotal).toFixed(2)}
                            </p>
                            {showFee && item.pricing.fee > 0 && (
                              <p className="text-xs text-slate-500">incl. ${item.pricing.fee.toFixed(2)} fee</p>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center justify-between mt-3">
                          <span className="text-sm text-slate-500">Qty: {item.quantity}</span>
                          <button onClick={() => removeItem(item.product.id)} className="text-sm text-red-500 hover:text-red-700 transition-colors" data-testid={`cart-remove-${item.product.id}`}>
                            Remove
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
                {grouped.oneTime.length === 0 && grouped.subscriptions.length === 0 && (
                  <div className="p-8 text-center text-slate-500">No purchasable items in cart</div>
                )}
              </div>
            </div>

            {/* Subscription Start Date */}
            {grouped.subscriptions.length > 0 && (
              <div className="rounded-2xl border border-slate-200 bg-white p-5" data-testid="cart-subscription-start-date">
                <h3 className="font-semibold text-slate-900 mb-4">Subscription Start Date</h3>
                <div className="flex flex-wrap gap-4">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="radio" name="futureStart" checked={!futureStartEnabled} onChange={() => { setFutureStartEnabled(false); setSubscriptionStartDate(""); }} className="w-4 h-4 text-slate-900" data-testid="cart-start-today" />
                    <span className="text-sm text-slate-700">Start today</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="radio" name="futureStart" checked={futureStartEnabled} onChange={() => setFutureStartEnabled(true)} className="w-4 h-4 text-slate-900" data-testid="cart-start-future" />
                    <span className="text-sm text-slate-700">Future start date</span>
                  </label>
                </div>
                {futureStartEnabled && (
                  <div className="mt-4">
                    <Input type="date" value={subscriptionStartDate} min={new Date(Date.now() + 3 * 86400000).toISOString().slice(0, 10)} max={new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10)} onChange={e => setSubscriptionStartDate(e.target.value)} className="max-w-xs" data-testid="cart-subscription-start-date-input" />
                    <p className="text-xs text-slate-500 mt-2">Must be 3-30 days from today</p>
                  </div>
                )}
              </div>
            )}

            {/* Payment Method */}
            {(allowBankTransfer || allowCardPayment) && !isFreeCheckout && (
              <div className="rounded-2xl border border-slate-200 bg-white p-5" data-testid="cart-payment-method">
                <h3 className="font-semibold text-slate-900 mb-4">Payment Method</h3>
                <div className="grid gap-3 sm:grid-cols-2">
                  {allowBankTransfer && (
                    <button type="button" onClick={() => setPaymentMethod("bank_transfer")} className={`flex items-center gap-4 rounded-xl border-2 p-4 text-left transition-all ${paymentMethod === "bank_transfer" ? "border-slate-900 bg-slate-50" : "border-slate-200 hover:border-slate-300"}`} data-testid="payment-bank-option">
                      <div className={`w-10 h-10 rounded-full flex items-center justify-center ${paymentMethod === "bank_transfer" ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-600"}`}>
                        <Building2 size={20} />
                      </div>
                      <div className="flex-1">
                        <p className="font-medium text-slate-900">{ws.payment_gocardless_label || "Bank Transfer"}</p>
                        <p className="text-xs text-slate-500 mt-0.5">No processing fee</p>
                      </div>
                      {paymentMethod === "bank_transfer" && <Check size={20} className="text-slate-900" />}
                    </button>
                  )}
                  {allowCardPayment && (
                    <button type="button" onClick={() => setPaymentMethod("card")} className={`flex items-center gap-4 rounded-xl border-2 p-4 text-left transition-all ${paymentMethod === "card" ? "border-slate-900 bg-slate-50" : "border-slate-200 hover:border-slate-300"}`} data-testid="payment-card-option">
                      <div className={`w-10 h-10 rounded-full flex items-center justify-center ${paymentMethod === "card" ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-600"}`}>
                        <CreditCard size={20} />
                      </div>
                      <div className="flex-1">
                        <p className="font-medium text-slate-900">{ws.payment_stripe_label || "Credit Card"}</p>
                        <p className="text-xs text-slate-500 mt-0.5">{stripeFeePercent}% processing fee</p>
                      </div>
                      {paymentMethod === "card" && <Check size={20} className="text-slate-900" />}
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* Checkout Questions - Dynamic Sections */}
            {checkoutSections !== null ? (
              checkoutSections.map((csection: any) => {
                const sectionFields = parseSectionFields(csection.fields_schema);
                return (
                  <div key={csection.id} className="rounded-2xl border border-slate-200 bg-white p-5" data-testid={`checkout-section-${csection.id}`}>
                    <h3 className="font-semibold text-slate-900 mb-1">{csection.title}</h3>
                    {csection.description && <p className="text-sm text-slate-500 mb-4">{csection.description}</p>}
                    <div className="space-y-4">
                      {sectionFields.map((field: any) => {
                        const fKey = field.id || field.key || field.name;
                        return (
                          <div key={fKey}>
                            <label className="text-sm font-medium text-slate-700 block mb-1.5">{field.label}{field.required && <span className="text-red-500 ml-1">*</span>}</label>
                            {field.type === "select" ? (
                              <Select value={extraFields[fKey] || undefined} onValueChange={(v) => setExtraFields(p => ({ ...p, [fKey]: v }))}>
                                <SelectTrigger className={`w-full bg-white ${field.required && !extraFields[fKey] ? "border-red-300" : ""}`} data-testid={`section-field-${fKey}`}>
                                  <SelectValue placeholder="Select an option..." />
                                </SelectTrigger>
                                <SelectContent>
                                  {parseOptions(field.options).map((opt: string) => { const { label, value } = parseOptionItem(opt); return <SelectItem key={value} value={value}>{label}</SelectItem>; })}
                                </SelectContent>
                              </Select>
                            ) : field.type === "checkbox" ? (
                              <label className="flex items-center gap-2 cursor-pointer">
                                <input type="checkbox" checked={extraFields[fKey] === "true"} onChange={e => setExtraFields(p => ({ ...p, [fKey]: String(e.target.checked) }))} className="w-4 h-4" data-testid={`section-field-${fKey}`} />
                                <span className="text-sm text-slate-600">{field.placeholder}</span>
                              </label>
                            ) : (
                              <Input type={field.type === "email" ? "email" : "text"} placeholder={field.placeholder || ""} value={extraFields[fKey] || ""} onChange={e => setExtraFields(p => ({ ...p, [fKey]: e.target.value }))} data-testid={`section-field-${fKey}`} />
                            )}
                          </div>
                        );
                      })}
                      {sectionFields.some((f: any) => (f.id || f.key || f.name) === 'partner_tag_response') && extraFields['partner_tag_response'] === 'Not yet' && (
                        <div>
                          <label className="text-sm font-medium text-slate-700 block mb-1.5">Partner Override Code</label>
                          <Input placeholder="Enter override code" value={overrideCode} onChange={e => setOverrideCode(e.target.value)} data-testid="section-override-code" />
                        </div>
                      )}
                    </div>
                  </div>
                );
              })
            ) : (
              <>
                {/* Legacy Zoho Section */}
                {ws.checkout_zoho_enabled !== false && (
                  <div className="rounded-2xl border border-slate-200 bg-white p-5" data-testid="zoho-checkout-section">
                    <h3 className="font-semibold text-slate-900 mb-1">{ws.checkout_zoho_title || "Zoho Account Details"}</h3>
                    {ws.checkout_zoho_description && <p className="text-sm text-slate-500 mb-4">{ws.checkout_zoho_description}</p>}
                    <div className="space-y-4">
                      <div>
                        <label className="text-sm font-medium text-slate-700 block mb-1.5">{ws.checkout_zoho_subscription_type_label || "Zoho subscription type?"}<span className="text-red-500 ml-1">*</span></label>
                        <Select value={zohoSubscriptionType || undefined} onValueChange={setZohoSubscriptionType}>
                          <SelectTrigger className="w-full bg-white" data-testid="zoho-subscription-type"><SelectValue placeholder="Select..." /></SelectTrigger>
                          <SelectContent>
                            {(ws.checkout_zoho_subscription_options?.split('\n').filter(Boolean) || ["Paid - Annual", "Paid - Monthly", "Free / Not on Zoho"]).map((o: string) => { const {label, value} = parseOptionItem(o); return <SelectItem key={value} value={value}>{label}</SelectItem>; })}
                          </SelectContent>
                        </Select>
                      </div>
                      <div>
                        <label className="text-sm font-medium text-slate-700 block mb-1.5">{ws.checkout_zoho_access_label || "Zoho account access?"}<span className="text-red-500 ml-1">*</span></label>
                        <Select value={zohoAccountAccess || undefined} onValueChange={setZohoAccountAccess}>
                          <SelectTrigger className="w-full bg-white" data-testid="zoho-account-access"><SelectValue placeholder="Select..." /></SelectTrigger>
                          <SelectContent>
                            {(ws.checkout_zoho_access_options?.split('\n').filter(Boolean) || ["New Customer", "Pre-existing Customer"]).map((o: string) => { const {label, value} = parseOptionItem(o); return <SelectItem key={value} value={value}>{label}</SelectItem>; })}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  </div>
                )}
                {/* Legacy Partner Section */}
                {ws.checkout_partner_enabled !== false && (
                  <div className="rounded-2xl border border-slate-200 bg-white p-5" data-testid="partner-checkout-section">
                    <h3 className="font-semibold text-slate-900 mb-1">{ws.checkout_partner_title || "Partner Tag"}</h3>
                    {ws.checkout_partner_description && <p className="text-sm text-slate-500 mb-4">{ws.checkout_partner_description}</p>}
                    <div className="space-y-4">
                      <div>
                        <label className="text-sm font-medium text-slate-700 block mb-1.5">{ws.checkout_partner_question || "Have you tagged us as your Partner?"}<span className="text-red-500 ml-1">*</span></label>
                        <Select value={partnerTagResponse || undefined} onValueChange={setPartnerTagResponse}>
                          <SelectTrigger className="w-full bg-white" data-testid="partner-tag-response"><SelectValue placeholder="Select..." /></SelectTrigger>
                          <SelectContent>
                            {(ws.checkout_partner_options?.split('\n').filter(Boolean) || ["Yes", "Not yet"]).map((o: string) => { const {label, value} = parseOptionItem(o); return <SelectItem key={value} value={value}>{label}</SelectItem>; })}
                          </SelectContent>
                        </Select>
                      </div>
                      {partnerTagResponse === "Not yet" && (
                        <div>
                          <label className="text-sm font-medium text-slate-700 block mb-1.5">Partner Override Code</label>
                          <Input placeholder="Enter override code" value={overrideCode} onChange={e => setOverrideCode(e.target.value)} data-testid="partner-override-code" />
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </>
            )}

            {/* Scope/Enquiry Section - MOVED HERE from product pages */}
            {hasEnquiryProducts && (
              <div className="rounded-2xl border-2 border-dashed border-blue-200 bg-blue-50/50 p-5" data-testid="cart-scope-section">
                <div className="flex items-start gap-3 mb-4">
                  <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                    <FileText className="w-5 h-5 text-blue-600" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-slate-900">Scope-Based Items</h3>
                    <p className="text-sm text-slate-500 mt-1">These items require scoping before checkout. Enter your Scope ID if you have one, or submit a scope request.</p>
                  </div>
                </div>
                
                {/* List scope/enquiry items */}
                <div className="space-y-3 mb-4">
                  {[...grouped.scope, ...grouped.inquiry].map((item: any) => (
                    <div key={item.product.id} className="flex items-center justify-between p-3 bg-white rounded-lg border border-blue-100">
                      <div>
                        <p className="font-medium text-slate-900">{item.product.name}</p>
                        <p className="text-xs text-slate-500">Requires scope approval</p>
                      </div>
                      <button onClick={() => removeItem(item.product.id)} className="text-xs text-red-500 hover:text-red-700">Remove</button>
                    </div>
                  ))}
                </div>

                {/* Scope ID Input */}
                <div className="bg-white rounded-xl p-4 border border-blue-100" data-testid="cart-scope-id-section">
                  <div className="flex items-center gap-2 mb-3">
                    <HelpCircle size={16} className="text-blue-600" />
                    <p className="text-sm font-medium text-slate-700">Already have a Scope ID?</p>
                  </div>
                  <p className="text-xs text-slate-500 mb-3">Enter your Scope ID to unlock pricing and proceed directly to checkout.</p>
                  <div className="flex gap-2">
                    <Input value={cartScopeId} onChange={(e) => { setCartScopeId(e.target.value); setCartScopeUnlock(null); setCartScopeError(""); }} placeholder="Enter Scope ID (e.g., SCOPE-ABC123)" className="flex-1 font-mono text-sm" data-testid="cart-scope-id-input" />
                    <Button variant="outline" onClick={handleValidateCartScopeId} disabled={cartScopeValidating || !cartScopeId.trim()} data-testid="cart-scope-id-validate-btn">
                      {cartScopeValidating ? "Checking..." : "Validate"}
                    </Button>
                  </div>
                  {cartScopeError && <p className="text-sm text-red-600 mt-2" data-testid="cart-scope-id-error">{cartScopeError}</p>}
                  {cartScopeUnlock && (
                    <div className="mt-3 rounded-lg bg-green-50 border border-green-200 p-4" data-testid="cart-scope-id-success">
                      <div className="flex items-center gap-2 mb-2">
                        <Check className="w-5 h-5 text-green-600" />
                        <p className="font-semibold text-green-800">Scope Validated!</p>
                      </div>
                      <p className="text-sm text-green-700 mb-1">{cartScopeUnlock.title}</p>
                      <p className="text-lg font-bold text-green-800 mb-3">${cartScopeUnlock.price}</p>
                      <Button onClick={handleApplyScopeToCart} className="w-full bg-green-600 hover:bg-green-700" data-testid="cart-scope-apply-btn">
                        Apply Scope & Continue to Checkout
                      </Button>
                    </div>
                  )}
                </div>

                {/* Or Request Scope */}
                <div className="mt-4 pt-4 border-t border-blue-100">
                  <p className="text-sm text-slate-600 mb-3">Don't have a Scope ID? Submit a scope request and we'll get back to you with pricing.</p>
                  <Button variant="outline" className="w-full border-blue-300 text-blue-700 hover:bg-blue-50" onClick={handleScopeRequest} disabled={loading} data-testid="cart-scope-submit">
                    Submit Scope Request
                  </Button>
                </div>
              </div>
            )}

            {/* RFQ Section */}
            {grouped.rfq.length > 0 && (
              <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden" data-testid="cart-rfq-section">
                <div className="p-4 border-b border-slate-100 bg-slate-50">
                  <h2 className="font-semibold text-slate-900">Quote Requests</h2>
                  <p className="text-sm text-slate-500">These items require a quote before purchase</p>
                </div>
                <div className="divide-y divide-slate-100">
                  {grouped.rfq.map((item: any) => (
                    <div key={item.product.id} className="p-4" data-testid={`cart-rfq-item-${item.product.id}`}>
                      <div className="flex items-center justify-between mb-3">
                        <div>
                          <p className="font-medium text-slate-900">{item.product.name}</p>
                          <p className="text-xs text-slate-500">Price to be confirmed</p>
                        </div>
                        <button onClick={() => removeItem(item.product.id)} className="text-xs text-red-500 hover:text-red-700">Remove</button>
                      </div>
                      <Button variant="outline" size="sm" className="w-full" onClick={() => { setCartQuoteProduct(item.product); setShowCartQuoteModal(true); }} data-testid={`cart-rfq-request-quote-btn-${item.product.id}`}>
                        Request Quote
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* External Checkouts */}
            {grouped.external.length > 0 && (
              <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden">
                <div className="p-4 border-b border-slate-100 bg-slate-50">
                  <h2 className="font-semibold text-slate-900">External Services</h2>
                </div>
                <div className="divide-y divide-slate-100">
                  {grouped.external.map((item: any) => (
                    <div key={item.product.id} className="p-4 flex items-center justify-between" data-testid={`cart-external-item-${item.product.id}`}>
                      <p className="font-medium text-slate-900">{item.product.name}</p>
                      <a href={item.pricing.external_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700">
                        Continue <ExternalLink size={14} />
                      </a>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Sidebar - Order Summary */}
          <div className="lg:sticky lg:top-6 space-y-6 h-fit">
            {/* Promo Code */}
            <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden" data-testid="cart-promo-section">
              <button onClick={() => setShowPromoSection(!showPromoSection)} className="w-full flex items-center justify-between p-4 text-left hover:bg-slate-50/50 transition-colors">
                <div className="flex items-center gap-3">
                  <Tag size={18} style={{ color: "var(--aa-accent)" }} />
                  <span className="font-medium text-slate-900">Promo Code</span>
                </div>
                {showPromoSection ? <ChevronUp size={18} className="text-slate-400" /> : <ChevronDown size={18} className="text-slate-400" />}
              </button>
              {showPromoSection && (
                <div className="px-4 pb-4">
                  {promoApplied ? (
                    <div className="flex items-center justify-between p-3 rounded-lg" style={{ backgroundColor: "color-mix(in srgb, var(--aa-accent) 10%, transparent)", borderColor: "var(--aa-accent)" }}>
                      <div className="flex items-center gap-2">
                        <Check size={16} style={{ color: "var(--aa-accent)" }} />
                        <span className="font-mono font-medium" style={{ color: "var(--aa-primary)" }}>{promoApplied.code}</span>
                        <span className="text-sm text-slate-600">({promoApplied.discount_type === "percent" ? `${promoApplied.discount_value}% off` : `$${promoApplied.discount_value} off`})</span>
                      </div>
                      <button onClick={handleRemovePromo} className="text-red-500 hover:text-red-700" data-testid="cart-promo-remove">
                        <X size={16} />
                      </button>
                    </div>
                  ) : (
                    <div className="flex gap-2">
                      <Input placeholder="Enter code" value={promoCode} onChange={(e) => setPromoCode(e.target.value.toUpperCase())} className="flex-1" data-testid="cart-promo-input" />
                      <Button onClick={handleApplyPromo} variant="outline" data-testid="cart-promo-apply">Apply</Button>
                    </div>
                  )}
                  {promoError && <p className="mt-2 text-sm text-red-600" data-testid="cart-promo-error">{promoError}</p>}
                </div>
              )}
            </div>

            {/* Order Summary */}
            <div className="rounded-2xl overflow-hidden shadow-[0_10px_40px_rgba(15,23,42,0.1)]" data-testid="cart-price-summary">
              <div className="p-4" style={{ backgroundColor: "var(--aa-primary)" }}>
                <h3 className="font-semibold text-white">Order Summary</h3>
              </div>
              <div className="p-5 bg-white">
                <div className="space-y-3 text-sm">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Subtotal</span>
                    <span className="text-slate-900">${totalSubtotal.toFixed(2)}</span>
                  </div>
                  {discountAmount > 0 && (
                    <div className="flex justify-between" style={{ color: "var(--aa-accent)" }}>
                      <span>Discount ({promoApplied?.code})</span>
                      <span>-${discountAmount.toFixed(2)}</span>
                    </div>
                  )}
                  {showFee && fee > 0 && (
                    <div className="flex justify-between">
                      <span className="text-slate-500">Processing fee ({stripeFeePercent}%)</span>
                      <span className="text-slate-900">${fee.toFixed(2)}</span>
                    </div>
                  )}
                  <div className="pt-3 border-t border-slate-200 flex justify-between">
                    <span className="font-semibold text-slate-900">Total</span>
                    <span className="font-bold text-lg" style={{ color: "var(--aa-primary)" }}>${total.toFixed(2)}</span>
                  </div>
                </div>
                {isFreeCheckout && (
                  <div className="mt-3 p-2 rounded-lg text-center" style={{ backgroundColor: "color-mix(in srgb, var(--aa-accent) 10%, transparent)" }}>
                    <p className="text-sm font-medium" style={{ color: "var(--aa-accent)" }}>This order is free!</p>
                  </div>
                )}
              </div>
            </div>

            {/* Terms & Checkout */}
            <div className="rounded-2xl border border-slate-200 bg-white p-5 space-y-4 shadow-sm">
              {ws.checkout_terms_enabled !== false && (
                <label className="flex items-start gap-3 cursor-pointer" data-testid="cart-terms-section">
                  <input 
                    type="checkbox" 
                    checked={termsAccepted} 
                    onChange={(e) => setTermsAccepted(e.target.checked)} 
                    className="mt-1 w-4 h-4 rounded"
                    style={{ accentColor: "var(--aa-accent)" }}
                  />
                  <span className="text-sm text-slate-600">
                    I accept the{" "}
                    <button type="button" onClick={() => setShowTermsModal(true)} className="underline font-medium hover:no-underline" style={{ color: "var(--aa-primary)" }}>
                      Terms & Conditions
                    </button>
                  </span>
                </label>
              )}
              
              {grouped.oneTime.length > 0 && (
                <Button 
                  className="w-full h-12 text-base text-white transition-all hover:opacity-90 shadow-lg" 
                  style={{ backgroundColor: "var(--aa-primary)" }}
                  onClick={() => handleCheckout(grouped.oneTime, "one_time")} 
                  disabled={loading || !termsAccepted || (checkoutSections !== null ? sectionRequiredFieldsMissing || (extraFields['partner_tag_response'] === 'Not yet' && !overrideCode.trim()) : ((ws.checkout_partner_enabled !== false && !partnerTagResponse) || (ws.checkout_partner_enabled !== false && partnerTagResponse === "Not yet" && !overrideCode.trim()) || (ws.checkout_zoho_enabled !== false && !zohoSubscriptionType) || (ws.checkout_zoho_enabled !== false && !zohoAccountAccess))) || currencyUnsupported || (!isFreeCheckout && !allowBankTransfer && !allowCardPayment)} 
                  data-testid="cart-checkout-one_time"
                >
                  {loading ? "Processing..." : isFreeCheckout ? "Complete Free Order" : paymentMethod === "bank_transfer" ? "Create Order" : "Proceed to Checkout"}
                </Button>
              )}
              
              {grouped.subscriptions.length > 0 && (
                <Button 
                  className="w-full h-12 text-base text-white transition-all hover:opacity-90 shadow-lg" 
                  style={{ backgroundColor: "var(--aa-accent)" }}
                  onClick={() => handleCheckout(grouped.subscriptions, "subscription")} 
                  disabled={loading || !termsAccepted || (checkoutSections !== null ? sectionRequiredFieldsMissing : ((ws.checkout_partner_enabled !== false && !partnerTagResponse) || (ws.checkout_zoho_enabled !== false && !zohoSubscriptionType) || (ws.checkout_zoho_enabled !== false && !zohoAccountAccess))) || currencyUnsupported || (!allowBankTransfer && !allowCardPayment) || (subscriptionMissingPrice && paymentMethod === "card")} 
                  data-testid="cart-checkout-subscription"
                >
                  {loading ? "Processing..." : "Subscribe Now"}
                </Button>
              )}

              {subscriptionMissingPrice && paymentMethod === "card" && grouped.subscriptions.length > 0 && (
                <p className="text-xs text-amber-600 text-center">Subscription checkout unavailable - Stripe price ID not configured</p>
              )}
            </div>

            {/* Payment Note */}
            <p className="text-xs text-slate-400 text-center px-4" data-testid="cart-currency-note">
              {paymentMethod === "bank_transfer" ? (ws.payment_gocardless_description || "No processing fee for bank transfer.") : "Final currency confirmed at checkout."}
            </p>
          </div>
        </div>
      )}

      {/* Quote Request Modal */}
      {showCartQuoteModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-slate-200 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold text-slate-900">Request a Quote</h2>
                {cartQuoteProduct && <p className="text-sm text-slate-500 mt-1">{cartQuoteProduct.name}</p>}
              </div>
              <button onClick={() => setShowCartQuoteModal(false)} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
            </div>
            <div className="p-6 space-y-4">
              <div><label className="text-sm font-medium text-slate-700 block mb-1.5">Your Name *</label><Input value={cartQuoteForm.name} onChange={e => setCartQuoteForm(f => ({ ...f, name: e.target.value }))} placeholder="John Smith" data-testid="cart-quote-name" /></div>
              <div><label className="text-sm font-medium text-slate-700 block mb-1.5">Email *</label><Input type="email" value={cartQuoteForm.email} onChange={e => setCartQuoteForm(f => ({ ...f, email: e.target.value }))} placeholder="john@company.com" data-testid="cart-quote-email" /></div>
              <div><label className="text-sm font-medium text-slate-700 block mb-1.5">Company</label><Input value={cartQuoteForm.company} onChange={e => setCartQuoteForm(f => ({ ...f, company: e.target.value }))} placeholder="Your Company" data-testid="cart-quote-company" /></div>
              <div><label className="text-sm font-medium text-slate-700 block mb-1.5">Phone</label><Input value={cartQuoteForm.phone} onChange={e => setCartQuoteForm(f => ({ ...f, phone: e.target.value }))} placeholder="+1 555 000 0000" data-testid="cart-quote-phone" /></div>
              <div><label className="text-sm font-medium text-slate-700 block mb-1.5">Message</label><textarea value={cartQuoteForm.message} onChange={e => setCartQuoteForm(f => ({ ...f, message: e.target.value }))} placeholder="Describe your requirements..." rows={4} className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-slate-900" data-testid="cart-quote-message" /></div>
            </div>
            <div className="p-6 border-t border-slate-200 flex gap-3">
              <Button variant="outline" className="flex-1" onClick={() => setShowCartQuoteModal(false)}>Cancel</Button>
              <Button className="flex-1 bg-slate-900 hover:bg-slate-800" onClick={handleSubmitCartQuote} disabled={submittingCartQuote || !cartQuoteForm.name || !cartQuoteForm.email} data-testid="cart-quote-submit">
                {submittingCartQuote ? "Submitting..." : "Submit Request"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Terms Modal */}
      {showTermsModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[80vh] overflow-hidden flex flex-col">
            <div className="p-6 border-b border-slate-200 flex items-center justify-between">
              <h2 className="text-xl font-semibold text-slate-900">{termsContent?.title || "Terms & Conditions"}</h2>
              <button onClick={() => setShowTermsModal(false)} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
            </div>
            <div className="p-6 overflow-y-auto flex-1">
              {termsContent?.content ? (
                <div className="prose prose-sm max-w-none">
                  <pre className="whitespace-pre-wrap text-sm text-slate-700 font-sans">{termsContent.content}</pre>
                </div>
              ) : (
                <div className="text-center py-8">
                  <p className="text-slate-500">No terms and conditions have been configured yet.</p>
                  <p className="text-sm text-slate-400 mt-2">Please contact the administrator if you need to review the terms.</p>
                </div>
              )}
            </div>
            <div className="p-6 border-t border-slate-200">
              <Button onClick={() => { setShowTermsModal(false); setTermsAccepted(true); }} className="w-full bg-slate-900 hover:bg-slate-800">
                {termsContent?.content ? "Accept & Close" : "Close"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
