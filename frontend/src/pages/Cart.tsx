import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import api from "@/lib/api";
import { useCart } from "@/contexts/CartContext";
import { useAuth } from "@/contexts/AuthContext";
import PriceSummary from "@/components/PriceSummary";

export default function Cart() {
  const navigate = useNavigate();
  const { items, removeItem, clear } = useCart();
  const { customer } = useAuth();
  const [preview, setPreview] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState<string>("bank_transfer");
  const [promoCode, setPromoCode] = useState("");
  const [promoApplied, setPromoApplied] = useState<any>(null);
  const [promoError, setPromoError] = useState("");
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [showTermsModal, setShowTermsModal] = useState(false);
  const [termsContent, setTermsContent] = useState<any>(null);

  const allowBankTransfer = customer?.allow_bank_transfer ?? true;
  const allowCardPayment = customer?.allow_card_payment ?? false;

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
        });
        toast.success("Order created successfully");
        clear();
        navigate(`/checkout/bank-transfer?order=${response.data.order_number || ""}`);
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
        });
        window.location.href = response.data.url;
      }
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Checkout failed");
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
        Your cart is empty.
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
  const fee = showFee ? Math.round(discountedSubtotal * 5) / 100 : 0;
  const total = discountedSubtotal + fee;

  return (
    <div className="space-y-8" data-testid="cart-page">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">Your cart</h1>
        <Button variant="ghost" onClick={clear} data-testid="cart-clear-button">
          Clear cart
        </Button>
      </div>

      {currencyUnsupported && (
        <div
          className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-700"
          data-testid="cart-currency-block"
        >
          Purchases are not supported in your region yet. Please contact admin for an override.
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
                      <div className="font-medium text-slate-900">Bank Transfer (GoCardless)</div>
                      <div className="text-sm text-slate-500">No processing fee. We'll send bank transfer instructions.</div>
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
                      <div className="font-medium text-slate-900">Card Payment (Stripe)</div>
                      <div className="text-sm text-slate-500">5% processing fee applies. Pay securely with credit/debit card.</div>
                    </div>
                  </button>
                )}
              </div>
              {!allowBankTransfer && !allowCardPayment && (
                <p className="text-sm text-amber-600">No payment methods available. Please contact support.</p>
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
                  <span className="text-slate-500">Processing fee (5%)</span>
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
                ? "No processing fee for bank transfer orders."
                : "Prices are displayed as $ only. Final currency will be confirmed in Stripe Checkout."}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
