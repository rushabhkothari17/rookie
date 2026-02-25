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
import PriceSummary from "@/components/PriceSummary";

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
  // Scope ID unlock for scope_request items in cart
  const [cartScopeId, setCartScopeId] = useState("");
  const [cartScopeValidating, setCartScopeValidating] = useState(false);
  const [cartScopeUnlock, setCartScopeUnlock] = useState<any>(null);
  const [cartScopeError, setCartScopeError] = useState("");
  // Quote modal for RFQ (zero-price) items
  const [showCartQuoteModal, setShowCartQuoteModal] = useState(false);
  const [cartQuoteProduct, setCartQuoteProduct] = useState<any>(null);
  const [cartQuoteForm, setCartQuoteForm] = useState({ name: "", email: "", company: "", phone: "", message: "" });
  const [submittingCartQuote, setSubmittingCartQuote] = useState(false);
  const [zohoUrls, setZohoUrls] = useState({
    reseller_signup_us: "",
    reseller_signup_ca: "",
    partner_tag_us: "",
    partner_tag_ca: "",
    access_instructions_url: "",
  });

  // Parse custom extra checkout questions from website settings (legacy)
  const extraSchema = useMemo(() => {
    try { return JSON.parse(ws.checkout_extra_schema || "[]"); }
    catch { return []; }
  }, [ws.checkout_extra_schema]);

  // Parse new dynamic checkout sections — if non-empty, replaces legacy zoho/partner sections
  const checkoutSections = useMemo(() => {
    try {
      const parsed = JSON.parse(ws.checkout_sections || "[]");
      if (Array.isArray(parsed) && parsed.length > 0) {
        return parsed
          .filter((s: any) => s.enabled !== false)
          .sort((a: any, b: any) => (a.order || 0) - (b.order || 0));
      }
    } catch {}
    return null; // null means use legacy zoho/partner system
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

  // Parse a "Label|value" option string into {label, value}
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

  useEffect(() => {
    api.get("/settings/public").then((res) => {
      const s = res.data.settings || {};
      setZohoUrls((prev) => ({
        reseller_signup_us: s.zoho_reseller_signup_us || prev.reseller_signup_us,
        reseller_signup_ca: s.zoho_reseller_signup_ca || prev.reseller_signup_ca,
        partner_tag_us: s.zoho_partner_tag_us || prev.partner_tag_us,
        partner_tag_ca: s.zoho_partner_tag_ca || prev.partner_tag_ca,
        access_instructions_url: s.zoho_access_instructions_url || prev.access_instructions_url,
      }));
    }).catch(() => {});
  }, []);

  // Respect per-customer allowed_payment_modes if set; fall back to legacy booleans
  const allowedModes: string[] | undefined = customer?.allowed_payment_modes?.length
    ? customer.allowed_payment_modes
    : undefined;
  const allowBankTransfer = allowedModes
    ? allowedModes.includes("gocardless")
    : (customer?.allow_bank_transfer ?? true);
  const allowCardPayment = allowedModes
    ? allowedModes.includes("stripe")
    : (customer?.allow_card_payment ?? false);

  // Payment display — from website settings (configurable per white-label)
  const gcLabel = ws.payment_gocardless_label || "Bank Transfer (GoCardless)";
  const gcDescription = ws.payment_gocardless_description || "No processing fee. We'll send bank transfer instructions.";
  const stripeLabel = ws.payment_stripe_label || "Card Payment (Stripe)";
  const stripeDescription = ws.payment_stripe_description || "Processing fee applies. Pay securely with credit/debit card.";
  // Fee rate from settings (e.g. 0.05 = 5%)
  const stripeFeeRate = ws.stripe_fee_rate || 0.05;
  const stripeFeePercent = Math.round(stripeFeeRate * 100);

  useEffect(() => {
    if (allowBankTransfer) {
      setPaymentMethod("bank_transfer");
    } else if (allowCardPayment) {
      setPaymentMethod("card");
    }
  }, [allowBankTransfer, allowCardPayment]);

  const loadPreview = async () => {
    if (items.length === 0) {
      setPreview(null);
      return;
    }
    const response = await api.post("/orders/preview", { items });
    setPreview(response.data);
  };

  useEffect(() => {
    loadPreview();
  }, [items]);

  const handleApplyPromo = async () => {
    if (!promoCode.trim()) return;
    setPromoError("");
    try {
      const checkoutType = grouped.subscriptions.length > 0 ? "subscription" : "one_time";
      const response = await api.post("/promo-codes/validate", { code: promoCode, checkout_type: checkoutType });
      setPromoApplied(response.data);
      toast.success("Promo code applied!");
    } catch (error: any) {
      setPromoError(error.response?.data?.detail || "Invalid promo code");
      setPromoApplied(null);
    }
  };

  const handleRemovePromo = () => {
    setPromoApplied(null);
    setPromoCode("");
    setPromoError("");
  };

  const grouped = useMemo(() => {
    if (!preview?.items) return { oneTime: [], subscriptions: [], scope: [], external: [], inquiry: [], rfq: [] };
    return preview.items.reduce(
      (acc: any, item: any) => {
        if (item.product.pricing_type === "external") acc.external.push(item);
        else if (item.product.pricing_type === "inquiry") acc.inquiry.push(item);
        else if (item.pricing.is_scope_request) acc.scope.push(item);
        else if (item.pricing.is_subscription) acc.subscriptions.push(item);
        // Zero-price one-time items without a scope unlock are RFQ items
        else if (item.pricing.subtotal === 0 && !item.inputs?._scope_unlock) acc.rfq.push(item);
        else acc.oneTime.push(item);
        return acc;
      },
      { oneTime: [], subscriptions: [], scope: [], external: [], inquiry: [], rfq: [] },
    );
  }, [preview]);

  const subscriptionMissingPrice = grouped.subscriptions.some(
    (item: any) => !item.product.stripe_price_id && !item.pricing.subtotal,
  );

  const loadTerms = async () => {
    if (items.length === 0) return;
    try {
      const productId = items[0].product_id;
      const response = await api.get(`/terms/for-product/${productId}`);
      setTermsContent(response.data);
    } catch (error) {
      console.error("Failed to load terms", error);
    }
  };

  useEffect(() => {
    loadTerms();
  }, [items]);

  const handleCheckout = async (groupItems: any[], checkoutType: string) => {
    if (!termsAccepted) {
      toast.error("Please accept the Terms & Conditions to proceed");
      return;
    }
    // Legacy validation only when not using new checkout_sections
    if (!checkoutSections) {
      if (!partnerTagResponse) {
        toast.error(ws.msg_partner_tagging_prompt || "Please select whether you have tagged us as your partner");
        return;
      }
      if (partnerTagResponse === "Not yet" && !overrideCode.trim()) {
        toast.error(ws.msg_override_required || "An override code is required when you have not yet tagged us as your partner");
        return;
      }
    }
    // New sections validation
    if (checkoutSections && sectionRequiredFieldsMissing) {
      toast.error("Please complete all required fields before proceeding");
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

    // Calculate total for this group of items
    const groupSubtotal = groupItems.reduce((sum: number, item: any) => sum + item.pricing.subtotal, 0);
    let groupDiscount = 0;
    if (promoApplied) {
      if (promoApplied.discount_type === "percent") {
        groupDiscount = Math.round(groupSubtotal * promoApplied.discount_value) / 100;
      } else {
        groupDiscount = Math.min(promoApplied.discount_value, groupSubtotal);
      }
    }
    const groupTotal = groupSubtotal - groupDiscount;
    const isFreeCheckout = groupTotal <= 0;

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

      // Handle FREE checkout (total = $0)
      if (isFreeCheckout && checkoutType === "one_time") {
        const response = await api.post("/checkout/free", checkoutPayload);
        toast.success("Order completed successfully!");
        clear();
        navigate(`/checkout/success?order=${response.data.order_number || ""}&free=true`);
        return;
      }

      if (paymentMethod === "bank_transfer") {
        const response = await api.post("/checkout/bank-transfer", checkoutPayload);
        
        // Check if GoCardless redirect is needed
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
        const response = await api.post("/checkout/session", {
          ...checkoutPayload,
          origin_url: window.location.origin,
        });
        window.location.href = response.data.url;
      }
    } catch (error: any) {
      // Safe error message extraction
      let errorMsg = "Checkout failed. Please try again.";
      
      if (error.response?.data) {
        const data = error.response.data;
        
        // Handle string detail
        if (typeof data.detail === 'string') {
          errorMsg = data.detail;
        }
        // Handle Pydantic validation errors (array of objects)
        else if (Array.isArray(data.detail)) {
          const messages = data.detail.map((err: any) => {
            if (typeof err === 'string') return err;
            if (err.msg) return `${err.loc?.join('.') || 'Field'}: ${err.msg}`;
            return JSON.stringify(err);
          });
          errorMsg = messages.join('; ');
        }
        // Handle object detail
        else if (typeof data.detail === 'object') {
          errorMsg = data.detail.message || data.detail.msg || JSON.stringify(data.detail);
        }
        // Fallback to generic message if exists
        else if (data.message) {
          errorMsg = data.message;
        }
      }
      
      toast.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const handleValidateCartScopeId = async () => {
    if (!cartScopeId.trim()) return;
    setCartScopeValidating(true);
    setCartScopeError("");
    setCartScopeUnlock(null);
    try {
      const res = await api.get(`/articles/${cartScopeId.trim()}/validate-scope`);
      setCartScopeUnlock(res.data);
    } catch (e: any) {
      setCartScopeError(e.response?.data?.detail || "Invalid Scope ID");
    } finally {
      setCartScopeValidating(false);
    }
  };

  const handleApplyScopeToCart = () => {
    if (!cartScopeUnlock) return;
    grouped.scope.forEach((item: any) => {
      updateItem(item.product.id, {
        inputs: {
          ...item.inputs,
          _scope_unlock: {
            scope_id: cartScopeUnlock.article_id,
            article_title: cartScopeUnlock.title,
            category: cartScopeUnlock.category,
            price: cartScopeUnlock.price,
          },
        },
        price_override: cartScopeUnlock.price,
      });
    });
    setCartScopeUnlock(null);
    setCartScopeId("");
    toast.success("Scope unlocked! Item updated in cart.");
  };

  const handleSubmitCartQuote = async () => {
    if (!cartQuoteProduct) return;
    setSubmittingCartQuote(true);
    try {
      await api.post(`/products/request-quote`, {
        ...cartQuoteForm,
        product_id: cartQuoteProduct.id,
        product_name: cartQuoteProduct.name,
      });
      toast.success("Quote request submitted! We'll be in touch shortly.");
      setShowCartQuoteModal(false);
      setCartQuoteForm({ name: "", email: "", company: "", phone: "", message: "" });
      removeItem(cartQuoteProduct.id);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to submit quote request");
    } finally {
      setSubmittingCartQuote(false);
    }
  };

  const handleScopeRequest = async () => {
    setLoading(true);
    try {
      const response = await api.post("/orders/scope-request", {
        items: grouped.scope.map((item: any) => ({
          product_id: item.product.id,
          quantity: item.quantity,
          inputs: item.inputs,
        })),
      });
      toast.success(`Scope request submitted: ${response.data.order_number}`);
      clear();
      navigate("/portal");
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Scope request failed");
    } finally {
      setLoading(false);
    }
  };

  if (items.length === 0) {
    return (
      <div className="text-center text-slate-600" data-testid="cart-empty">
        {ws.msg_cart_empty || "Your cart is empty."}
      </div>
    );
  }

  const currencyUnsupported =
    preview?.currency && !["USD", "CAD"].includes(preview.currency);

  const showFee = paymentMethod === "card";
  const oneTimeSubtotal = grouped.oneTime.reduce((sum: number, item: any) => sum + item.pricing.subtotal, 0);
  const subscriptionSubtotal = grouped.subscriptions.reduce((sum: number, item: any) => sum + item.pricing.subtotal, 0);
  const totalSubtotal = oneTimeSubtotal + subscriptionSubtotal;
  
  // Calculate discount
  let discountAmount = 0;
  if (promoApplied) {
    if (promoApplied.discount_type === "percent") {
      discountAmount = Math.round(totalSubtotal * promoApplied.discount_value) / 100;
    } else {
      discountAmount = Math.min(promoApplied.discount_value, totalSubtotal);
    }
  }
  
  // Fee is calculated on discounted subtotal
  const discountedSubtotal = totalSubtotal - discountAmount;
  const fee = showFee ? Math.round(discountedSubtotal * stripeFeeRate * 100) / 100 : 0;
  const total = discountedSubtotal + fee;

  return (
    <div className="space-y-8" data-testid="cart-page">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">{ws.cart_title || "Your cart"}</h1>
        <Button variant="ghost" onClick={clear} data-testid="cart-clear-button">
          {ws.cart_clear_btn_text || "Clear cart"}
        </Button>
      </div>

      {currencyUnsupported && (
        <div
          className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-700"
          data-testid="cart-currency-block"
        >
          {ws.msg_currency_unsupported || "Purchases are not supported in your region yet. Please contact admin for an override."}
        </div>
      )}

      {preview && (
        <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
          <div className="space-y-6">
            {/* Payment Method Selection */}
            <div className="rounded-xl border border-slate-200 bg-white p-6" data-testid="cart-payment-method">
              <h2 className="text-lg font-semibold text-slate-900 mb-4">Payment Method</h2>
              <div className="space-y-3">
                {allowBankTransfer && (
                  <button
                    type="button"
                    onClick={() => setPaymentMethod("bank_transfer")}
                    className={`w-full flex items-center gap-3 rounded-lg border p-4 text-left transition-colors ${
                      paymentMethod === "bank_transfer"
                        ? "border-slate-900 bg-slate-50"
                        : "border-slate-200 hover:bg-slate-50"
                    }`}
                    data-testid="payment-bank-option"
                  >
                    <div className={`h-4 w-4 rounded-full border-2 flex items-center justify-center ${
                      paymentMethod === "bank_transfer" ? "border-slate-900" : "border-slate-300"
                    }`}>
                      {paymentMethod === "bank_transfer" && (
                        <div className="h-2 w-2 rounded-full bg-slate-900" />
                      )}
                    </div>
                    <div className="flex-1">
                      <div className="font-medium text-slate-900">{gcLabel}</div>
                      <div className="text-sm text-slate-500">{gcDescription}</div>
                    </div>
                  </button>
                )}
                {allowCardPayment && (
                  <button
                    type="button"
                    onClick={() => setPaymentMethod("card")}
                    className={`w-full flex items-center gap-3 rounded-lg border p-4 text-left transition-colors ${
                      paymentMethod === "card"
                        ? "border-slate-900 bg-slate-50"
                        : "border-slate-200 hover:bg-slate-50"
                    }`}
                    data-testid="payment-card-option"
                  >
                    <div className={`h-4 w-4 rounded-full border-2 flex items-center justify-center ${
                      paymentMethod === "card" ? "border-slate-900" : "border-slate-300"
                    }`}>
                      {paymentMethod === "card" && (
                        <div className="h-2 w-2 rounded-full bg-slate-900" />
                      )}
                    </div>
                    <div className="flex-1">
                      <div className="font-medium text-slate-900">{stripeLabel}</div>
                      <div className="text-sm text-slate-500">{stripeDescription}</div>
                    </div>
                  </button>
                )}
              </div>
              {!allowBankTransfer && !allowCardPayment && (
                <div className="space-y-3">
                  <p className="text-sm text-amber-600" data-testid="no-payment-msg">{ws.msg_no_payment_methods || "No payment methods available. Please contact support."}</p>
                  {!ws.stripe_enabled && !ws.gocardless_enabled && (
                    <button
                      data-testid="cart-request-quote-fallback"
                      className="w-full bg-slate-900 text-white py-3 px-6 rounded-lg font-semibold hover:bg-slate-800 transition-colors"
                      onClick={() => {
                        const email = ws.contact_email || "";
                        const subject = encodeURIComponent("Quote Request");
                        const body = encodeURIComponent("Hi,\n\nI'd like to request a quote for my cart items.\n\nThank you.");
                        window.location.href = `mailto:${email}?subject=${subject}&body=${body}`;
                      }}
                    >
                      Request a Quote
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* Promo Code Section */}
            <div className="rounded-xl border border-slate-200 bg-white p-6" data-testid="cart-promo-section">
              <h2 className="text-lg font-semibold text-slate-900 mb-3">Promo Code</h2>
              {promoApplied ? (
                <div className="flex items-center justify-between p-3 bg-green-50 border border-green-200 rounded-lg">
                  <div>
                    <span className="font-mono font-semibold text-green-700">{promoApplied.code}</span>
                    <span className="ml-2 text-sm text-green-600">
                      ({promoApplied.discount_type === "percent" ? `${promoApplied.discount_value}% off` : `$${promoApplied.discount_value} off`})
                    </span>
                  </div>
                  <button onClick={handleRemovePromo} className="text-sm text-red-600 hover:text-red-700" data-testid="cart-promo-remove">Remove</button>
                </div>
              ) : (
                <div className="flex gap-2">
                  <Input
                    placeholder="Enter promo code"
                    value={promoCode}
                    onChange={(e) => setPromoCode(e.target.value.toUpperCase())}
                    className="flex-1"
                    data-testid="cart-promo-input"
                  />
                  <Button onClick={handleApplyPromo} variant="outline" data-testid="cart-promo-apply">Apply</Button>
                </div>
              )}
              {promoError && <p className="mt-2 text-sm text-red-600" data-testid="cart-promo-error">{promoError}</p>}
            </div>

            {[
              { title: "One-time purchases", items: grouped.oneTime, checkoutType: "one_time" },
              { title: "Subscriptions", items: grouped.subscriptions, checkoutType: "subscription" },
            ].map((section) => (
              <div key={section.title} className="space-y-3">
                <h2 className="text-lg font-semibold text-slate-900">{section.title}</h2>
                {section.items.length === 0 ? (
                  <p className="text-sm text-slate-500">No items in this section.</p>
                ) : (
                  <div className="space-y-3">
                    {section.items.map((item: any) => (
                      <div
                        key={item.product.id}
                        className="rounded-xl border border-slate-200 bg-white p-4"
                        data-testid={`cart-item-${item.product.id}`}
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <div
                              className="text-sm font-semibold text-slate-900"
                              data-testid={`cart-item-name-${item.product.id}`}
                            >
                              {item.product.name}
                            </div>
                            <div
                              className="text-xs text-slate-500"
                              data-testid={`cart-item-tagline-${item.product.id}`}
                            >
                              {item.product.tagline}
                            </div>
                          </div>
                          <div
                            className="text-sm font-semibold text-slate-900"
                            data-testid={`cart-item-total-${item.product.id}`}
                          >
                            ${(showFee ? item.pricing.total : item.pricing.subtotal).toFixed(2)}
                          </div>
                        </div>
                        <div className="mt-3 flex justify-between text-xs text-slate-500">
                          <span data-testid={`cart-item-subtotal-${item.product.id}`}>
                            Subtotal ${item.pricing.subtotal.toFixed(2)}
                            {showFee && item.pricing.fee > 0 && ` + $${item.pricing.fee.toFixed(2)} fee`}
                          </span>
                          <button
                            className="text-red-600"
                            onClick={() => removeItem(item.product.id)}
                            data-testid={`cart-remove-${item.product.id}`}
                          >
                            Remove
                          </button>
                        </div>
                      </div>
                    ))}
                    {section.checkoutType === "subscription" && subscriptionMissingPrice && paymentMethod === "card" && (
                      <div
                        className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-700"
                        data-testid="cart-subscription-warning"
                      >
                        Subscription checkout is unavailable until a Stripe price ID is configured by admin.
                      </div>
                    )}
                    {section.checkoutType === "subscription" && paymentMethod === "bank_transfer" && (
                      <div
                        className="rounded-md border border-blue-200 bg-blue-50 p-3 text-xs text-blue-700"
                        data-testid="cart-subscription-bank-notice"
                      >
                        Subscriptions via bank transfer require direct debit setup. We'll contact you with next steps.
                      </div>
                    )}
                    {/* Subscription Start Date */}
                    {section.checkoutType === "subscription" && (
                      <div
                        className="rounded-md border border-slate-200 bg-slate-50 p-3 space-y-3"
                        data-testid="cart-subscription-start-date"
                      >
                        <label className="text-xs font-semibold text-slate-600 block">
                          Subscription Start Date
                        </label>
                        <div className="flex gap-4">
                          <label className="flex items-center gap-2 text-sm text-slate-600 cursor-pointer">
                            <input
                              type="radio"
                              name="futureStart"
                              checked={!futureStartEnabled}
                              onChange={() => { setFutureStartEnabled(false); setSubscriptionStartDate(""); }}
                              data-testid="cart-start-today"
                            />
                            Start today
                          </label>
                          <label className="flex items-center gap-2 text-sm text-slate-600 cursor-pointer">
                            <input
                              type="radio"
                              name="futureStart"
                              checked={futureStartEnabled}
                              onChange={() => setFutureStartEnabled(true)}
                              data-testid="cart-start-future"
                            />
                            Future start date
                          </label>
                        </div>
                        {futureStartEnabled && (
                          <div className="space-y-1">
                            <Input
                              type="date"
                              value={subscriptionStartDate}
                              min={new Date(Date.now() + 3 * 86400000).toISOString().slice(0, 10)}
                              max={new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10)}
                              onChange={e => setSubscriptionStartDate(e.target.value)}
                              className="text-sm"
                              data-testid="cart-subscription-start-date-input"
                            />
                            <p className="text-xs text-slate-400">
                              Future start date must be at least 3 days from today (max 30 days).
                            </p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}

            {/* ── Checkout Questions & Buttons (shown once for all items) ── */}
            {(grouped.oneTime.length > 0 || grouped.subscriptions.length > 0) && (
              <div className="space-y-4">
                {/* Dynamic checkout sections (new) OR legacy zoho/partner (fallback) */}
                {checkoutSections !== null ? (
                  <>
                    {checkoutSections.map((csection: any) => {
                      const sectionFields = parseSectionFields(csection.fields_schema);
                      return (
                        <div key={csection.id} className="rounded-md border border-slate-200 bg-slate-50 p-4 space-y-4" data-testid={`checkout-section-${csection.id}`}>
                          <p className="text-sm font-semibold text-slate-700">{csection.title}</p>
                          {csection.description && <p className="text-xs text-slate-500">{csection.description}</p>}
                          {sectionFields.filter((f: any) => f.enabled !== false).map((field: any) => {
                            const fKey = field.id || field.key || field.name;
                            return (
                              <div key={fKey} className="space-y-1">
                                <label className="text-sm font-medium text-slate-700">{field.label}{field.required && <span className="text-red-500 ml-1">*</span>}</label>
                                {field.type === "select" ? (
                                  <Select
                                    value={extraFields[fKey] || undefined}
                                    onValueChange={(v) => setExtraFields(p => ({ ...p, [fKey]: v }))}
                                  >
                                    <SelectTrigger
                                      className={`w-full bg-white text-slate-900 ${field.required && !extraFields[fKey] ? "border-red-300" : "border-slate-300"}`}
                                      data-testid={`section-field-${fKey}`}
                                    >
                                      <SelectValue placeholder="-- Select --" />
                                    </SelectTrigger>
                                    <SelectContent>
                                      {parseOptions(field.options).map((opt: string) => {
                                        const { label, value } = parseOptionItem(opt);
                                        return <SelectItem key={value} value={value}>{label}</SelectItem>;
                                      })}
                                    </SelectContent>
                                  </Select>
                                ) : field.type === "checkbox" ? (
                                  <div className="flex items-center gap-2">
                                    <input type="checkbox" checked={extraFields[fKey] === "true"} onChange={e => setExtraFields(p => ({ ...p, [fKey]: String(e.target.checked) }))} className="h-4 w-4" data-testid={`section-field-${fKey}`} />
                                    <span className="text-sm text-slate-600">{field.placeholder}</span>
                                  </div>
                                ) : (
                                  <input type={field.type === "email" ? "email" : "text"} placeholder={field.placeholder || ""} value={extraFields[fKey] || ""} onChange={e => setExtraFields(p => ({ ...p, [fKey]: e.target.value }))} className="w-full h-9 border border-slate-300 rounded-md px-3 text-sm bg-white text-slate-900" data-testid={`section-field-${fKey}`} />
                                )}
                              </div>
                            );
                          })}
                          {/* Special: partner_tag_response = Not yet triggers override code input */}
                          {sectionFields.some((f: any) => (f.id || f.key || f.name) === 'partner_tag_response') && extraFields['partner_tag_response'] === 'Not yet' && (
                            <div className="space-y-1">
                              <label className="text-sm font-medium text-slate-700">Partner Override Code</label>
                              <input type="text" placeholder="Enter override code" value={overrideCode} onChange={e => setOverrideCode(e.target.value)} className="w-full h-9 border border-slate-300 rounded-md px-3 text-sm bg-white text-slate-900" data-testid="section-override-code" />
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </>
                ) : (
                  <>
                    {ws.checkout_zoho_enabled !== false && (() => {
                      const subOpts = ws.checkout_zoho_subscription_options?.split('\n').filter(Boolean) || ["Paid - Annual", "Paid - Monthly", "Free / Not on Zoho"];
                      const prodOpts = ws.checkout_zoho_product_options?.split('\n').filter(Boolean) || [];
                      const accessOpts = ws.checkout_zoho_access_options?.split('\n').filter(Boolean) || ["New Customer", "Pre-existing Customer"];
                      return (
                        <div className="rounded-md border border-slate-200 bg-slate-50 p-4 space-y-4" data-testid="zoho-checkout-section">
                          <p className="text-sm font-semibold text-slate-700">{ws.checkout_zoho_title || "Zoho Account Details"}</p>
                          {ws.checkout_zoho_description && <p className="text-xs text-slate-500">{ws.checkout_zoho_description}</p>}
                          <div className="space-y-1">
                            <label className="text-sm font-medium text-slate-700">{ws.checkout_zoho_subscription_type_label || "Current Zoho subscription type?"}<span className="text-red-500 ml-1">*</span></label>
                            <Select value={zohoSubscriptionType || undefined} onValueChange={setZohoSubscriptionType}>
                              <SelectTrigger className="w-full bg-white text-slate-900" data-testid="zoho-subscription-type"><SelectValue placeholder="-- Select --" /></SelectTrigger>
                              <SelectContent>
                                {subOpts.map((o: string) => { const {label, value} = parseOptionItem(o); return <SelectItem key={value} value={value}>{label}</SelectItem>; })}
                              </SelectContent>
                            </Select>
                          </div>
                          {prodOpts.length > 0 && (
                            <div className="space-y-1">
                              <label className="text-sm font-medium text-slate-700">{ws.checkout_zoho_product_label || "Which Zoho products?"}<span className="text-red-500 ml-1">*</span></label>
                              <Select value={currentZohoProduct || undefined} onValueChange={setCurrentZohoProduct}>
                                <SelectTrigger className="w-full bg-white text-slate-900" data-testid="zoho-current-product"><SelectValue placeholder="-- Select --" /></SelectTrigger>
                                <SelectContent>
                                  {prodOpts.map((o: string) => { const {label, value} = parseOptionItem(o); return <SelectItem key={value} value={value}>{label}</SelectItem>; })}
                                </SelectContent>
                              </Select>
                            </div>
                          )}
                          <div className="space-y-1">
                            <label className="text-sm font-medium text-slate-700">{ws.checkout_zoho_access_label || "Zoho account access?"}<span className="text-red-500 ml-1">*</span></label>
                            <Select value={zohoAccountAccess || undefined} onValueChange={setZohoAccountAccess}>
                              <SelectTrigger className="w-full bg-white text-slate-900" data-testid="zoho-account-access"><SelectValue placeholder="-- Select --" /></SelectTrigger>
                              <SelectContent>
                                {accessOpts.map((o: string) => { const {label, value} = parseOptionItem(o); return <SelectItem key={value} value={value}>{label}</SelectItem>; })}
                              </SelectContent>
                            </Select>
                          </div>
                        </div>
                      );
                    })()}
                    {ws.checkout_partner_enabled !== false && (() => {
                      const partnerOpts = ws.checkout_partner_options?.split('\n').filter(Boolean) || ["Yes", "Not yet"];
                      return (
                        <div className="rounded-md border border-slate-200 bg-slate-50 p-4 space-y-4" data-testid="partner-checkout-section">
                          <p className="text-sm font-semibold text-slate-700">{ws.checkout_partner_title || "Partner Tag"}</p>
                          {ws.checkout_partner_description && <p className="text-xs text-slate-500">{ws.checkout_partner_description}</p>}
                          <div className="space-y-1">
                            <label className="text-sm font-medium text-slate-700">{ws.checkout_partner_question || "Have you tagged us as your Partner?"}<span className="text-red-500 ml-1">*</span></label>
                            <Select value={partnerTagResponse || undefined} onValueChange={setPartnerTagResponse}>
                              <SelectTrigger className="w-full bg-white text-slate-900" data-testid="partner-tag-response"><SelectValue placeholder="-- Select --" /></SelectTrigger>
                              <SelectContent>
                                {partnerOpts.map((o: string) => { const {label, value} = parseOptionItem(o); return <SelectItem key={value} value={value}>{label}</SelectItem>; })}
                              </SelectContent>
                            </Select>
                          </div>
                          {partnerTagResponse === "Not yet" && (
                            <div className="space-y-1">
                              <label className="text-sm font-medium text-slate-700">Partner Override Code</label>
                              <input type="text" placeholder="Enter override code" value={overrideCode} onChange={e => setOverrideCode(e.target.value)} className="w-full h-9 border border-slate-300 rounded-md px-3 text-sm bg-white text-slate-900" data-testid="partner-override-code" />
                            </div>
                          )}
                        </div>
                      );
                    })()}
                  </>
                )}

                {/* Extra schema fields (from legacy checkout extra_schema) */}
                {ws.checkout_extra_schema && (() => {
                  const extraSchema = JSON.parse(ws.checkout_extra_schema || "[]");
                  if (!Array.isArray(extraSchema) || extraSchema.length === 0) return null;
                  return (
                    <div className="rounded-md border border-slate-200 bg-slate-50 p-4 space-y-4" data-testid="extra-schema-section">
                      {extraSchema.filter((f: any) => f.enabled !== false).map((field: any) => (
                        <div key={field.name} className="space-y-1">
                          <label className="text-sm font-medium text-slate-700">{field.label}{field.required && <span className="text-red-500 ml-1">*</span>}</label>
                          {field.type === "select" ? (
                            <Select value={extraFields[field.name] || undefined} onValueChange={v => setExtraFields(p => ({ ...p, [field.name]: v }))}>
                              <SelectTrigger className="w-full bg-white text-slate-900"><SelectValue placeholder="-- Select --" /></SelectTrigger>
                              <SelectContent>
                                {parseOptions(field.options).map((opt: string) => {
                                  const { label, value } = parseOptionItem(opt);
                                  return <SelectItem key={value} value={value}>{label}</SelectItem>;
                                })}
                              </SelectContent>
                            </Select>
                          ) : field.type === "checkbox" ? (
                            <div className="flex items-center gap-2">
                              <input type="checkbox" checked={extraFields[field.name] === "true"} onChange={e => setExtraFields(p => ({ ...p, [field.name]: String(e.target.checked) }))} />
                              <span className="text-sm text-slate-600">{field.placeholder}</span>
                            </div>
                          ) : (
                            <input type={field.type === "email" ? "email" : "text"} placeholder={field.placeholder || ""} value={extraFields[field.name] || ""} onChange={e => setExtraFields(p => ({ ...p, [field.name]: e.target.value }))} className="w-full h-9 border border-slate-200 rounded-md px-3 text-sm bg-white text-slate-900" />
                          )}
                        </div>
                      ))}
                    </div>
                  );
                })()}

                {/* Terms & Conditions */}
                {ws.checkout_terms_enabled !== false && (
                  <div className="flex items-start gap-3 rounded-md border border-slate-200 bg-slate-50 p-3" data-testid="cart-terms-section">
                    <input
                      type="checkbox"
                      id="terms-checkbox"
                      checked={termsAccepted}
                      onChange={(e) => setTermsAccepted(e.target.checked)}
                      className="mt-1"
                    />
                    <label htmlFor="terms-checkbox" className="text-sm text-slate-700 flex-1">
                      I accept the{" "}
                      <button
                        type="button"
                        onClick={() => setShowTermsModal(true)}
                        className="text-slate-900 underline font-medium"
                      >
                        Terms & Conditions
                      </button>
                    </label>
                  </div>
                )}

                {/* Checkout buttons per section type */}
                {grouped.oneTime.length > 0 && (
                  <Button
                    className="w-full bg-slate-900 hover:bg-slate-800"
                    onClick={() => handleCheckout(grouped.oneTime, "one_time")}
                    disabled={
                      loading ||
                      !termsAccepted ||
                      (checkoutSections !== null
                        ? sectionRequiredFieldsMissing || (extraFields['partner_tag_response'] === 'Not yet' && !overrideCode.trim())
                        : (
                          (ws.checkout_partner_enabled !== false && !partnerTagResponse) ||
                          (ws.checkout_partner_enabled !== false && partnerTagResponse === "Not yet" && !overrideCode.trim()) ||
                          (ws.checkout_zoho_enabled !== false && !zohoSubscriptionType) ||
                          (ws.checkout_zoho_enabled !== false && (() => { const p = ws.checkout_zoho_product_options?.split('\n').filter(Boolean) || []; return p.length > 0 && !currentZohoProduct; })()) ||
                          (ws.checkout_zoho_enabled !== false && !zohoAccountAccess)
                        )
                      ) ||
                      currencyUnsupported ||
                      (!allowBankTransfer && !allowCardPayment)
                    }
                    data-testid="cart-checkout-one_time"
                  >
                    {paymentMethod === "bank_transfer" ? "Create order" : "Proceed to checkout"}
                  </Button>
                )}
                {grouped.subscriptions.length > 0 && (
                  <Button
                    className="w-full bg-slate-900 hover:bg-slate-800"
                    onClick={() => handleCheckout(grouped.subscriptions, "subscription")}
                    disabled={
                      loading ||
                      !termsAccepted ||
                      (checkoutSections !== null
                        ? sectionRequiredFieldsMissing || (extraFields['partner_tag_response'] === 'Not yet' && !overrideCode.trim())
                        : (
                          (ws.checkout_partner_enabled !== false && !partnerTagResponse) ||
                          (ws.checkout_partner_enabled !== false && partnerTagResponse === "Not yet" && !overrideCode.trim()) ||
                          (ws.checkout_zoho_enabled !== false && !zohoSubscriptionType) ||
                          (ws.checkout_zoho_enabled !== false && (() => { const p = ws.checkout_zoho_product_options?.split('\n').filter(Boolean) || []; return p.length > 0 && !currentZohoProduct; })()) ||
                          (ws.checkout_zoho_enabled !== false && !zohoAccountAccess)
                        )
                      ) ||
                      currencyUnsupported ||
                      (!allowBankTransfer && !allowCardPayment) ||
                      (subscriptionMissingPrice && paymentMethod === "card")
                    }
                    data-testid="cart-checkout-subscription"
                  >
                    {paymentMethod === "bank_transfer" ? "Create subscription request" : "Proceed to subscription checkout"}
                  </Button>
                )}
              </div>
            )}

            <div className="space-y-3">
              <h2 className="text-lg font-semibold text-slate-900">Scope 'n Pay Later</h2>
              {grouped.scope.length === 0 ? (
                <p className="text-sm text-slate-500">No scope requests yet.</p>
              ) : (
                <div className="space-y-3">
                  {grouped.scope.map((item: any) => (
                    <div
                      key={item.product.id}
                      className="rounded-xl border border-slate-200 bg-white p-4"
                      data-testid={`cart-scope-item-${item.product.id}`}
                    >
                      <div
                        className="text-sm font-semibold text-slate-900"
                        data-testid={`cart-scope-name-${item.product.id}`}
                      >
                        {item.product.name}
                      </div>
                      <div
                        className="text-xs text-slate-500"
                        data-testid={`cart-scope-estimate-${item.product.id}`}
                      >
                        Estimated ${item.pricing.subtotal.toFixed(2)}
                      </div>
                    </div>
                  ))}
                  {/* Scope ID Unlock — allows customers with a pre-approved scope to skip the request step */}
                  <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3" data-testid="cart-scope-id-section">
                    <p className="text-sm font-medium text-slate-700">Already have a Scope ID?</p>
                    <p className="text-xs text-slate-500">If you received a finalized scope document, enter the Scope ID to unlock pricing and proceed directly to checkout.</p>
                    <div className="flex gap-2">
                      <Input
                        value={cartScopeId}
                        onChange={(e) => { setCartScopeId(e.target.value); setCartScopeUnlock(null); setCartScopeError(""); }}
                        placeholder="Enter Scope ID"
                        className="flex-1 font-mono text-sm"
                        data-testid="cart-scope-id-input"
                      />
                      <Button
                        variant="outline"
                        onClick={handleValidateCartScopeId}
                        disabled={cartScopeValidating || !cartScopeId.trim()}
                        data-testid="cart-scope-id-validate-btn"
                      >
                        {cartScopeValidating ? "Checking…" : "Validate"}
                      </Button>
                    </div>
                    {cartScopeError && <p className="text-sm text-red-600" data-testid="cart-scope-id-error">{cartScopeError}</p>}
                    {cartScopeUnlock && (
                      <div className="rounded-lg bg-green-50 border border-green-200 p-3 space-y-2" data-testid="cart-scope-id-success">
                        <p className="text-sm font-semibold text-green-800">Scope unlocked: {cartScopeUnlock.title}</p>
                        <p className="text-sm font-bold text-green-800">${cartScopeUnlock.price}</p>
                        <Button onClick={handleApplyScopeToCart} className="w-full" size="sm" data-testid="cart-scope-apply-btn">
                          Apply Scope &amp; Proceed to Checkout
                        </Button>
                      </div>
                    )}
                  </div>
                  <Button
                    className="w-full bg-blue-600 hover:bg-blue-700"
                    onClick={handleScopeRequest}
                    disabled={loading}
                    data-testid="cart-scope-submit"
                  >
                    Submit scope request
                  </Button>
                </div>
              )}
            </div>

            {/* RFQ (Quote Request) section — for zero-price products */}
            {grouped.rfq.length > 0 && (
              <div className="space-y-3" data-testid="cart-rfq-section">
                <h2 className="text-lg font-semibold text-slate-900">Quote Requests</h2>
                <div className="space-y-3">
                  {grouped.rfq.map((item: any) => (
                    <div key={item.product.id} className="rounded-xl border border-slate-200 bg-white p-4 space-y-3" data-testid={`cart-rfq-item-${item.product.id}`}>
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="text-sm font-semibold text-slate-900" data-testid={`cart-rfq-name-${item.product.id}`}>{item.product.name}</div>
                          <div className="text-xs text-slate-500">Price to be confirmed</div>
                        </div>
                        <button onClick={() => removeItem(item.product.id)} className="text-xs text-red-500 hover:text-red-700" data-testid={`cart-rfq-remove-${item.product.id}`}>Remove</button>
                      </div>
                      {/* Scope ID unlock */}
                      <div className="rounded-lg border border-slate-100 bg-slate-50 p-3 space-y-2" data-testid="cart-rfq-scope-section">
                        <p className="text-xs font-medium text-slate-700">Have a Scope ID? Enter it to unlock your quote price instantly.</p>
                        <div className="flex gap-2">
                          <Input
                            value={cartScopeId}
                            onChange={(e) => { setCartScopeId(e.target.value); setCartScopeUnlock(null); setCartScopeError(""); }}
                            placeholder="Enter Scope ID"
                            className="flex-1 font-mono text-sm"
                            data-testid="cart-rfq-scope-id-input"
                          />
                          <Button variant="outline" size="sm" onClick={handleValidateCartScopeId} disabled={cartScopeValidating || !cartScopeId.trim()} data-testid="cart-rfq-scope-validate-btn">
                            {cartScopeValidating ? "Checking…" : "Validate"}
                          </Button>
                        </div>
                        {cartScopeError && <p className="text-xs text-red-600" data-testid="cart-rfq-scope-error">{cartScopeError}</p>}
                        {cartScopeUnlock && (
                          <div className="rounded-lg bg-green-50 border border-green-200 p-3 space-y-2" data-testid="cart-rfq-scope-success">
                            <p className="text-sm font-semibold text-green-800">Scope unlocked: {cartScopeUnlock.title}</p>
                            <p className="text-sm font-bold text-green-800">${cartScopeUnlock.price}</p>
                            <Button onClick={handleApplyScopeToCart} className="w-full" size="sm" data-testid="cart-rfq-scope-apply-btn">
                              Apply Scope &amp; Proceed to Checkout
                            </Button>
                          </div>
                        )}
                      </div>
                      <Button
                        variant="outline"
                        className="w-full border-slate-300"
                        onClick={() => { setCartQuoteProduct(item.product); setShowCartQuoteModal(true); }}
                        data-testid={`cart-rfq-request-quote-btn-${item.product.id}`}
                      >
                        Request a Quote
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="space-y-3">
              <h2 className="text-lg font-semibold text-slate-900">External checkouts</h2>
              {grouped.external.length === 0 ? (
                <p className="text-sm text-slate-500">No external services in cart.</p>
              ) : (
                <div className="space-y-3">
                  {grouped.external.map((item: any) => (
                    <div
                      key={item.product.id}
                      className="rounded-xl border border-slate-200 bg-white p-4"
                      data-testid={`cart-external-item-${item.product.id}`}
                    >
                      <div
                        className="text-sm font-semibold text-slate-900"
                        data-testid={`cart-external-name-${item.product.id}`}
                      >
                        {item.product.name}
                      </div>
                      <a
                        href={item.pricing.external_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs text-blue-600"
                        data-testid={`cart-external-${item.product.id}`}
                      >
                        Continue to external checkout
                      </a>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {grouped.inquiry.length > 0 && (
              <div
                className="rounded-xl border border-dashed border-slate-300 bg-white p-4"
                data-testid="cart-inquiry-block"
              >
                <div
                  className="text-sm font-semibold text-slate-900"
                  data-testid="cart-inquiry-title"
                >
                  Inquiry-only services
                </div>
                <p className="text-xs text-slate-500" data-testid="cart-inquiry-description">
                  These services require a consult. Contact sales to proceed.
                </p>
              </div>
            )}
          </div>

          <div className="space-y-4">
            <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3" data-testid="cart-price-summary">
              <div className="flex justify-between text-sm">
                <span className="text-slate-500">Subtotal</span>
                <span className="text-slate-900">${totalSubtotal.toFixed(2)}</span>
              </div>
              {discountAmount > 0 && (
                <div className="flex justify-between text-sm text-green-600">
                  <span>Discount ({promoApplied?.code})</span>
                  <span>-${discountAmount.toFixed(2)}</span>
                </div>
              )}
              {showFee && (
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">Processing fee ({stripeFeePercent}%)</span>
                  <span className="text-slate-900">${fee.toFixed(2)}</span>
                </div>
              )}
              <div className="border-t border-slate-200 pt-3 flex justify-between">
                <span className="font-semibold text-slate-900">Total</span>
                <span className="font-semibold text-slate-900">${total.toFixed(2)}</span>
              </div>
            </div>
            <div
              className="rounded-xl border border-slate-200 bg-white p-4 text-xs text-slate-500"
              data-testid="cart-currency-note"
            >
              {paymentMethod === "bank_transfer" 
                ? (ws.payment_gocardless_description || "No processing fee for bank transfer orders.")
                : "Prices are displayed as $ only. Final currency will be confirmed in Stripe Checkout."}
            </div>
          </div>
        </div>
      )}

      {/* Quote Request Modal for RFQ items */}
      {showCartQuoteModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-slate-200">
              <h2 className="text-xl font-semibold text-slate-900">Request a Quote</h2>
              {cartQuoteProduct && <p className="text-sm text-slate-500 mt-1">{cartQuoteProduct.name}</p>}
            </div>
            <div className="p-6 space-y-4">
              <div className="space-y-1">
                <label className="text-sm font-medium text-slate-700">Your Name</label>
                <Input value={cartQuoteForm.name} onChange={e => setCartQuoteForm(f => ({ ...f, name: e.target.value }))} placeholder="John Smith" data-testid="cart-quote-name" />
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium text-slate-700">Email</label>
                <Input type="email" value={cartQuoteForm.email} onChange={e => setCartQuoteForm(f => ({ ...f, email: e.target.value }))} placeholder="john@company.com" data-testid="cart-quote-email" />
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium text-slate-700">Company</label>
                <Input value={cartQuoteForm.company} onChange={e => setCartQuoteForm(f => ({ ...f, company: e.target.value }))} placeholder="Your Company" data-testid="cart-quote-company" />
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium text-slate-700">Phone (optional)</label>
                <Input value={cartQuoteForm.phone} onChange={e => setCartQuoteForm(f => ({ ...f, phone: e.target.value }))} placeholder="+1 555 000 0000" data-testid="cart-quote-phone" />
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium text-slate-700">Message (optional)</label>
                <textarea value={cartQuoteForm.message} onChange={e => setCartQuoteForm(f => ({ ...f, message: e.target.value }))} placeholder="Describe your requirements…" rows={4} className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm bg-white text-slate-900 resize-none" data-testid="cart-quote-message" />
              </div>
            </div>
            <div className="p-6 border-t border-slate-200 flex gap-3">
              <Button variant="outline" className="flex-1" onClick={() => setShowCartQuoteModal(false)}>Cancel</Button>
              <Button className="flex-1 bg-slate-900 hover:bg-slate-800" onClick={handleSubmitCartQuote} disabled={submittingCartQuote || !cartQuoteForm.name || !cartQuoteForm.email} data-testid="cart-quote-submit">
                {submittingCartQuote ? "Submitting…" : "Submit Request"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Terms & Conditions Modal */}
      {showTermsModal && termsContent && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-2xl w-full max-h-[80vh] overflow-hidden flex flex-col">
            <div className="p-6 border-b border-slate-200">
              <h2 className="text-xl font-semibold text-slate-900">{termsContent.title}</h2>
            </div>
            <div className="p-6 overflow-y-auto flex-1">
              <div className="prose prose-sm max-w-none">
                <pre className="whitespace-pre-wrap text-sm text-slate-700 font-sans">{termsContent.content}</pre>
              </div>
            </div>
            <div className="p-6 border-t border-slate-200">
              <Button onClick={() => setShowTermsModal(false)} className="w-full">Close</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
