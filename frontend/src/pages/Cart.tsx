import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import api from "@/lib/api";
import { useCart } from "@/contexts/CartContext";
import { useAuth } from "@/contexts/AuthContext";
import { useWebsite } from "@/contexts/WebsiteContext";
import PriceSummary from "@/components/PriceSummary";

export default function Cart() {
  const navigate = useNavigate();
  const { items, removeItem, clear } = useCart();
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

  const sectionRequiredFieldsMissing = useMemo(() => {
    if (!checkoutSections) return false;
    return checkoutSections.some((section: any) => {
      const fields = parseSectionFields(section.fields_schema);
      return fields.some((f: any) => f.required && !extraFields[f.key || f.name]);
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
    if (!preview?.items) return { oneTime: [], subscriptions: [], scope: [], external: [], inquiry: [] };
    return preview.items.reduce(
      (acc: any, item: any) => {
        if (item.product.pricing_type === "external") acc.external.push(item);
        else if (item.product.pricing_type === "inquiry") acc.inquiry.push(item);
        else if (item.pricing.is_scope_request) acc.scope.push(item);
        else if (item.pricing.is_subscription) acc.subscriptions.push(item);
        else acc.oneTime.push(item);
        return acc;
      },
      { oneTime: [], subscriptions: [], scope: [], external: [], inquiry: [] },
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

    setLoading(true);
    try {
      if (paymentMethod === "bank_transfer") {
        const response = await api.post("/checkout/bank-transfer", {
          items: groupItems.map((item) => ({
            product_id: item.product.id,
            quantity: item.quantity,
            inputs: item.inputs,
          })),
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
        });
        
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
          items: groupItems.map((item) => ({
            product_id: item.product.id,
            quantity: item.quantity,
            inputs: item.inputs,
          })),
          checkout_type: checkoutType,
          origin_url: window.location.origin,
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
                <p className="text-sm text-amber-600">{ws.msg_no_payment_methods || "No payment methods available. Please contact support."}</p>
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
                    {/* Zoho Account Details — dynamic from website settings */}
                    {ws.checkout_zoho_enabled !== false && (() => {
                      const subOpts = ws.checkout_zoho_subscription_options?.split('\n').filter(Boolean) || ["Paid - Annual", "Paid - Monthly", "Free / Not on Zoho"];
                      const prodOpts = ws.checkout_zoho_product_options?.split('\n').filter(Boolean) || [];
                      const signupUrl = address?.country === "Canada" ? zohoUrls.reseller_signup_ca : zohoUrls.reseller_signup_us;
                      return (
                        <div className="rounded-md border border-slate-200 bg-slate-50 p-4 space-y-4" data-testid="zoho-checkout-questions">
                          <p className="text-sm font-semibold text-slate-700">{ws.checkout_zoho_title || "Zoho Account Details"}</p>
                          <div className="space-y-1">
                            <label className="text-xs font-medium text-slate-600 block">Current Zoho subscription type? <span className="text-red-500">*</span></label>
                            <select data-testid="zoho-subscription-type" value={zohoSubscriptionType} onChange={e => setZohoSubscriptionType(e.target.value)}
                              className={`w-full h-9 border rounded-md px-3 text-sm bg-white text-slate-800 ${!zohoSubscriptionType ? "border-red-300" : "border-slate-300"}`}>
                              <option value="">-- Select --</option>
                              {subOpts.map(opt => <option key={opt} value={opt}>{opt}</option>)}
                            </select>
                          </div>
                          {prodOpts.length > 0 && (
                            <div className="space-y-1">
                              <label className="text-xs font-medium text-slate-600 block">Current Zoho Product? <span className="text-red-500">*</span></label>
                              <select data-testid="current-zoho-product" value={currentZohoProduct} onChange={e => setCurrentZohoProduct(e.target.value)}
                                className={`w-full h-9 border rounded-md px-3 text-sm bg-white text-slate-800 ${!currentZohoProduct ? "border-red-300" : "border-slate-300"}`}>
                                <option value="">-- Select --</option>
                                {prodOpts.map(opt => <option key={opt} value={opt}>{opt}</option>)}
                              </select>
                              {currentZohoProduct === "Not on Zoho" && signupUrl && (
                                <div className="mt-2 p-3 bg-blue-50 border border-blue-200 rounded-md text-xs text-blue-800">
                                  Sign up to Zoho now using{" "}
                                  <a href={signupUrl} target="_blank" rel="noopener noreferrer" className="underline font-medium text-blue-700" data-testid="zoho-signup-link">this link</a>
                                  {" "}{ws.checkout_zoho_signup_note || "for a free 1 hour Welcome to Zoho and a 30-day trial"}
                                </div>
                              )}
                            </div>
                          )}
                          <div className="space-y-1">
                            <label className="text-xs font-medium text-slate-600 block">Have you provided us access to your Zoho account? <span className="text-red-500">*</span></label>
                            {zohoUrls.access_instructions_url && (
                              <p className="text-xs text-slate-500">
                                Please use <a href={zohoUrls.access_instructions_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 underline" data-testid="zoho-access-link">this link</a>{" "}
                                {ws.checkout_zoho_access_note || "to understand how to provide us access to your Zoho account"}
                              </p>
                            )}
                            <select data-testid="zoho-account-access" value={zohoAccountAccess} onChange={e => setZohoAccountAccess(e.target.value)}
                              className={`w-full h-9 border rounded-md px-3 text-sm bg-white text-slate-800 ${!zohoAccountAccess ? "border-red-300" : "border-slate-300"}`}>
                              <option value="">-- Select --</option>
                              <option value="Yes">Yes</option>
                              <option value="Not yet">Not yet</option>
                            </select>
                            {zohoAccountAccess === "Not yet" && (
                              <div className="bg-amber-50 border border-amber-300 rounded-md p-2 text-xs text-amber-800">
                                <strong>Note:</strong> {ws.checkout_zoho_access_delay_warning || "Please note service delays can happen if you complete purchase without providing us the access."}
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })()}

                    {/* ZOHOR promo code note */}
                    {promoApplied?.code && promoApplied.code.toUpperCase().includes("ZOHOR") && (
                      <div
                        className="rounded-md border border-blue-200 bg-blue-50 p-3 text-xs text-blue-800"
                        data-testid="zohor-promo-note"
                      >
                        <strong>Note:</strong> This service involves external sponsorship. Please checkout now — however, we will begin work only after we receive confirmation of sponsorship from the third party.
                      </div>
                    )}

                    {/* Partner Tagging — dynamic from website settings */}
                    {ws.checkout_partner_enabled !== false && (() => {
                      const partnerOpts = ws.checkout_partner_options?.split('\n').filter(Boolean) || ["Yes", "Pre-existing Customer", "Not yet"];
                      return (
                        <div className="rounded-md border border-blue-200 bg-blue-50 p-4 space-y-3" data-testid="partner-tag-section">
                          <label className="text-sm font-semibold text-slate-700 block">
                            {ws.checkout_partner_title || "Have you tagged us as your Zoho Partner?"} <span className="text-red-500">*</span>
                          </label>
                          <p className="text-xs text-slate-500 leading-relaxed">
                            {ws.checkout_partner_description || "You can tag us as your Zoho Partner by clicking the links below."}
                            {(zohoUrls.partner_tag_us || zohoUrls.partner_tag_ca) && (
                              <>
                                {" "}
                                {zohoUrls.partner_tag_us && <><a href={zohoUrls.partner_tag_us} target="_blank" rel="noopener noreferrer" className="text-blue-600 underline font-medium" data-testid="partner-tag-us-link">here (US DC)</a>{" "}</>}
                                {zohoUrls.partner_tag_ca && <>{zohoUrls.partner_tag_us ? "or " : ""}<a href={zohoUrls.partner_tag_ca} target="_blank" rel="noopener noreferrer" className="text-blue-600 underline font-medium" data-testid="partner-tag-ca-link">here (CA DC)</a>.</>}
                              </>
                            )}
                            {ws.checkout_partner_misrep_warning && (
                              <> <span className="text-red-600 font-medium">{ws.checkout_partner_misrep_warning}</span></>
                            )}
                          </p>
                          <select data-testid="partner-tag-dropdown" value={partnerTagResponse}
                            onChange={e => { setPartnerTagResponse(e.target.value); setOverrideCode(""); }}
                            className={`w-full h-10 border rounded-md px-3 text-sm bg-white text-slate-800 ${!partnerTagResponse ? "border-red-300" : "border-slate-300"}`}>
                            <option value="">-- Select an option --</option>
                            {partnerOpts.map(opt => <option key={opt} value={opt}>{opt}</option>)}
                          </select>
                          {partnerTagResponse === "Not yet" && (
                            <div className="space-y-1">
                              <label className="text-xs font-semibold text-slate-600 block">Override Code <span className="text-red-500">*</span></label>
                              <Input data-testid="override-code-checkout-input" value={overrideCode} onChange={e => setOverrideCode(e.target.value)}
                                placeholder="Enter override code provided by admin"
                                className={`text-sm ${!overrideCode.trim() ? "border-red-300" : "border-slate-300"}`} />
                              <p className="text-xs text-slate-500">Contact admin to receive a valid override code for your account.</p>
                            </div>
                          )}
                        </div>
                      );
                    })()}
                    {/* Custom extra questions from website settings */}
                    {extraSchema.length > 0 && (
                      <div className="rounded-md border border-slate-200 bg-slate-50 p-4 space-y-4" data-testid="checkout-extra-questions">
                        {extraSchema.map((field: any) => (
                          <div key={field.name} className="space-y-1">
                            <label className="text-xs font-medium text-slate-600 block">
                              {field.label}{field.required && <span className="text-red-500"> *</span>}
                            </label>
                            {field.type === "select" ? (
                              <select value={extraFields[field.name] || ""} onChange={e => setExtraFields(p => ({ ...p, [field.name]: e.target.value }))}
                                className="w-full h-9 border border-slate-200 rounded-md px-3 text-sm bg-white">
                                <option value="">-- Select --</option>
                                {(field.options || []).map((opt: string) => <option key={opt} value={opt}>{opt}</option>)}
                              </select>
                            ) : field.type === "checkbox" ? (
                              <label className="flex items-center gap-2 text-sm cursor-pointer">
                                <input type="checkbox" checked={extraFields[field.name] === "true"}
                                  onChange={e => setExtraFields(p => ({ ...p, [field.name]: String(e.target.checked) }))} />
                                {field.label}
                              </label>
                            ) : (
                              <Input value={extraFields[field.name] || ""} onChange={e => setExtraFields(p => ({ ...p, [field.name]: e.target.value }))}
                                placeholder={field.placeholder || ""} className="text-sm" />
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                    {/* Terms & Conditions */}
                    <div className="flex items-start gap-2 p-3 rounded-md border border-slate-200 bg-slate-50">
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
                    <Button
                      className="w-full bg-slate-900 hover:bg-slate-800"
                      onClick={() => handleCheckout(section.items, section.checkoutType)}
                      disabled={
                        loading ||
                        !termsAccepted ||
                        (ws.checkout_partner_enabled !== false && !partnerTagResponse) ||
                        (ws.checkout_partner_enabled !== false && partnerTagResponse === "Not yet" && !overrideCode.trim()) ||
                        (ws.checkout_zoho_enabled !== false && !zohoSubscriptionType) ||
                        (ws.checkout_zoho_enabled !== false && (() => { const p = ws.checkout_zoho_product_options?.split('\n').filter(Boolean) || []; return p.length > 0 && !currentZohoProduct; })()) ||
                        (ws.checkout_zoho_enabled !== false && !zohoAccountAccess) ||
                        currencyUnsupported ||
                        (!allowBankTransfer && !allowCardPayment) ||
                        (section.checkoutType === "subscription" && subscriptionMissingPrice && paymentMethod === "card")
                      }
                      data-testid={`cart-checkout-${section.checkoutType}`}
                    >
                      {paymentMethod === "bank_transfer"
                        ? `Create ${section.checkoutType === "one_time" ? "order" : "subscription request"}`
                        : `Proceed to ${section.checkoutType === "one_time" ? "checkout" : "subscription checkout"}`}
                    </Button>
                  </div>
                )}
              </div>
            ))}

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
