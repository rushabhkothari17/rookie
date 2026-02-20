import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import api from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/sonner";
import { useCart } from "@/contexts/CartContext";
import AppShell from "@/components/AppShell";
import ProductHero from "@/components/ProductHero";
import StickyPurchaseSummary from "@/components/StickyPurchaseSummary";
import SectionCard from "@/components/SectionCard";
import IncludedList from "@/components/IncludedList";
import { displayCategory, slugFromCategory } from "@/lib/categories";

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
  const [product, setProduct] = useState<any>(null);
  const [inputs, setInputs] = useState<Record<string, any>>({});
  const [pricing, setPricing] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [showScopeModal, setShowScopeModal] = useState(false);
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

  const handleAddToCart = () => {
    addItem({ product_id: product.id, quantity: 1, inputs });
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

  const requiresStripePrice =
    pricing?.is_subscription && !product?.stripe_price_id;

  const ctaConfig = useMemo(() => {
    if (!product || !pricing) {
      return { label: "Add to cart" };
    }
    if (product.pricing_type === "external") {
      return {
        label: "Continue to migration checkout",
        href: product.pricing_rules.external_url,
      };
    }
    if (product.pricing_type === "inquiry") {
      return {
        label: "Contact sales",
        href: "mailto:hello@automateaccounts.com",
      };
    }
    if (pricing.is_scope_request || product.pricing_type === "scope_request") {
      return { label: "Request scope", onClick: handleScopeRequest };
    }
    return { label: "Add to cart", onClick: handleAddToCart };
  }, [product, pricing]);

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
  const categorySlug = slugFromCategory(categoryLabel);

  return (
    <AppShell activeCategory={categoryLabel}>
      <div className="space-y-8" data-testid="product-detail">
        <nav className="text-xs text-slate-500" data-testid="product-breadcrumbs">
          <Link to="/store" className="hover:text-slate-700" data-testid="breadcrumb-home">
            Home
          </Link>
          <span className="mx-2">/</span>
          <Link
            to={`/store?category=${categorySlug}`}
            className="hover:text-slate-700"
            data-testid="breadcrumb-category"
          >
            {categoryLabel}
          </Link>
          <span className="mx-2">/</span>
          <span className="text-slate-700" data-testid="breadcrumb-product">
            {product.name}
          </span>
        </nav>

        <div className="grid gap-10 lg:grid-cols-[1.4fr_0.9fr]">
          <div className="space-y-8">
            <ProductHero product={product} />

            {product.price_inputs?.length > 0 && (
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
              <IncludedList items={product.bullets_included || []} testId="product-included-list" />
            </SectionCard>
            <SectionCard title="Not included" testId="product-excluded">
              <ul className="space-y-2" data-testid="product-excluded-list">
                {(product.bullets_excluded || []).map((item: string) => (
                  <li key={item}>• {item}</li>
                ))}
              </ul>
            </SectionCard>
            <SectionCard title="What we need from you" testId="product-needed">
              <ul className="space-y-2" data-testid="product-needed-list">
                {(product.bullets_needed || []).map((item: string) => (
                  <li key={item}>• {item}</li>
                ))}
              </ul>
            </SectionCard>
            <SectionCard title="Next steps" testId="product-next-steps">
              <ol className="space-y-2" data-testid="product-next-steps-list">
                {(product.next_steps || []).map((item: string, index: number) => (
                  <li key={item}>{index + 1}. {item}</li>
                ))}
              </ol>
            </SectionCard>
            <SectionCard title="FAQs" testId="product-faqs">
              <ul className="space-y-2" data-testid="product-faqs-list">
                {(product.faqs || []).map((item: string) => (
                  <li key={item}>• {item}</li>
                ))}
              </ul>
            </SectionCard>
            <Link to="/store" className="text-sm text-slate-500" data-testid="product-back-link">
              Back to store
            </Link>
          </div>

          <div className="space-y-4">
            {pricing ? (
              <StickyPurchaseSummary
                pricing={{
                  subtotal: pricing.subtotal,
                  fee: pricing.fee,
                  total: pricing.total,
                }}
                cta={ctaConfig}
                disabled={requiresStripePrice}
                warning={
                  requiresStripePrice
                    ? "Subscription checkout is unavailable until a Stripe price ID is configured by admin."
                    : undefined
                }
              />
            ) : (
              <div
                className="rounded-3xl bg-white/80 p-6 text-sm text-slate-500"
                data-testid="product-summary-loading"
              >
                Calculating pricing...
              </div>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
