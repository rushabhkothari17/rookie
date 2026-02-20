import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import api from "@/lib/api";
import { useCart } from "@/contexts/CartContext";
import PriceSummary from "@/components/PriceSummary";

export default function Cart() {
  const navigate = useNavigate();
  const { items, removeItem, clear } = useCart();
  const [preview, setPreview] = useState<any>(null);
  const [loading, setLoading] = useState(false);

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
  }, [items.length]);

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

  const handleCheckout = async (groupItems: any[], checkoutType: string) => {
    setLoading(true);
    try {
      const response = await api.post("/checkout/session", {
        items: groupItems.map((item) => ({
          product_id: item.product.id,
          quantity: item.quantity,
          inputs: item.inputs,
        })),
        checkout_type: checkoutType,
        origin_url: window.location.origin,
      });
      window.location.href = response.data.url;
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

  return (
    <div className="space-y-8" data-testid="cart-page">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">Your cart</h1>
        <Button variant="ghost" onClick={clear} data-testid="cart-clear-button">
          Clear cart
        </Button>
      </div>

      {preview && (
        <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
          <div className="space-y-6">
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
                            <div className="text-sm font-semibold text-slate-900">
                              {item.product.name}
                            </div>
                            <div className="text-xs text-slate-500">
                              {item.product.tagline}
                            </div>
                          </div>
                          <div className="text-sm font-semibold text-slate-900">
                            ${item.pricing.total.toFixed(2)}
                          </div>
                        </div>
                        <div className="mt-3 flex justify-between text-xs text-slate-500">
                          <span>Subtotal ${item.pricing.subtotal.toFixed(2)}</span>
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
                    <Button
                      className="w-full bg-slate-900 hover:bg-slate-800"
                      onClick={() => handleCheckout(section.items, section.checkoutType)}
                      disabled={loading}
                      data-testid={`cart-checkout-${section.checkoutType}`}
                    >
                      Proceed to {section.checkoutType === "one_time" ? "checkout" : "subscription checkout"}
                    </Button>
                  </div>
                )}
              </div>
            ))}

            <div className="space-y-3">
              <h2 className="text-lg font-semibold text-slate-900">Scope n Pay Later</h2>
              {grouped.scope.length === 0 ? (
                <p className="text-sm text-slate-500">No scope requests yet.</p>
              ) : (
                <div className="space-y-3">
                  {grouped.scope.map((item: any) => (
                    <div key={item.product.id} className="rounded-xl border border-slate-200 bg-white p-4">
                      <div className="text-sm font-semibold text-slate-900">{item.product.name}</div>
                      <div className="text-xs text-slate-500">Estimated ${item.pricing.subtotal.toFixed(2)}</div>
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
                    <div key={item.product.id} className="rounded-xl border border-slate-200 bg-white p-4">
                      <div className="text-sm font-semibold text-slate-900">{item.product.name}</div>
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
              <div className="rounded-xl border border-dashed border-slate-300 bg-white p-4">
                <div className="text-sm font-semibold text-slate-900">Inquiry-only services</div>
                <p className="text-xs text-slate-500">
                  These services require a consult. Contact sales to proceed.
                </p>
              </div>
            )}
          </div>

          <div className="space-y-4">
            <PriceSummary
              subtotal={preview.summary.one_time.subtotal + preview.summary.subscription.subtotal}
              fee={preview.summary.one_time.fee + preview.summary.subscription.fee}
              total={preview.summary.one_time.total + preview.summary.subscription.total}
            />
            <div className="rounded-xl border border-slate-200 bg-white p-4 text-xs text-slate-500" data-testid="cart-currency-note">
              Prices are displayed as $ only. Final currency will be confirmed in Stripe Checkout.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
