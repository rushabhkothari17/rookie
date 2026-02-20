import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ExternalLink, Plus } from "lucide-react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { toast } from "@/components/ui/sonner";
import { useCart } from "@/contexts/CartContext";

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

  const priceSummary = useMemo(() => {
    if (!pricing) return null;
    return (
      <div className="space-y-2 rounded-xl border border-slate-200 bg-white p-6">
        <div className="text-sm text-slate-500" data-testid="product-price-subtotal">
          Subtotal: ${pricing.subtotal.toFixed(2)}
        </div>
        <div className="text-sm text-slate-500" data-testid="product-price-fee">
          Processing fee (5%): ${pricing.fee.toFixed(2)}
        </div>
        <div className="text-lg font-semibold text-slate-900" data-testid="product-price-total">
          Total: ${pricing.total.toFixed(2)}
        </div>
      </div>
    );
  }, [pricing]);

  const requiresStripePrice =
    pricing?.is_subscription && !product?.stripe_price_id;


  if (loading) {
    return (
      <div className="flex items-center justify-center" data-testid="product-loading">
        Loading...
      </div>
    );
  }

  if (!product) {
    return (
      <div className="text-sm text-slate-600" data-testid="product-not-found">
        Product not found
      </div>
    );
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[1.3fr_1fr]" data-testid="product-detail">
      <div className="space-y-6">
        <div className="space-y-3">
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">{product.category}</p>
          <h1 className="text-3xl font-semibold text-slate-900" data-testid="product-name">{product.name}</h1>
          <p className="text-sm text-slate-600" data-testid="product-tagline">{product.tagline}</p>
          <p className="text-base text-slate-700" data-testid="product-description">{product.description_long}</p>
        </div>

        <Card className="p-6 space-y-4" data-testid="product-input-card">
          <h2 className="text-sm font-semibold text-slate-900">Configure pricing</h2>
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
          {priceSummary}
          {requiresStripePrice && (
            <div
              className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-700"
              data-testid="product-stripe-warning"
            >
              Subscription checkout is unavailable until a Stripe price ID is configured by admin.
            </div>
          )}
          {pricing?.requires_checkout && (
            <Button
              className="w-full bg-slate-900 hover:bg-slate-800"
              onClick={handleAddToCart}
              disabled={requiresStripePrice}
              data-testid="product-add-to-cart"
            >
              <Plus size={16} className="mr-2" /> Add to cart
            </Button>
          )}
          {pricing?.is_scope_request && (
            <Button
              className="w-full bg-blue-600 hover:bg-blue-700"
              onClick={handleAddToCart}
              data-testid="product-scope-request"
            >
              Request scope
            </Button>
          )}
          {product.pricing_type === "external" && (
            <Button
              className="w-full bg-slate-900 hover:bg-slate-800"
              asChild
              data-testid="product-external-link"
            >
              <a href={product.pricing_rules.external_url} target="_blank" rel="noreferrer">
                Continue to migration checkout
                <ExternalLink className="ml-2" size={16} />
              </a>
            </Button>
          )}
          {product.pricing_type === "inquiry" && (
            <Button
              className="w-full bg-slate-900 hover:bg-slate-800"
              asChild
              data-testid="product-inquiry-link"
            >
              <a href="mailto:hello@automateaccounts.com">Contact sales</a>
            </Button>
          )}
        </Card>
      </div>

      <div className="space-y-6">
        <Card className="p-6 space-y-3">
          <h3 className="text-sm font-semibold text-slate-900">What's included</h3>
          <ul className="text-sm text-slate-600 space-y-2" data-testid="product-included">
            {product.bullets_included?.map((item: string) => (
              <li key={item}>• {item}</li>
            ))}
          </ul>
        </Card>
        <Card className="p-6 space-y-3">
          <h3 className="text-sm font-semibold text-slate-900">Not included</h3>
          <ul className="text-sm text-slate-600 space-y-2" data-testid="product-excluded">
            {product.bullets_excluded?.map((item: string) => (
              <li key={item}>• {item}</li>
            ))}
          </ul>
        </Card>
        <Card className="p-6 space-y-3">
          <h3 className="text-sm font-semibold text-slate-900">What we need from you</h3>
          <ul className="text-sm text-slate-600 space-y-2" data-testid="product-needed">
            {product.bullets_needed?.map((item: string) => (
              <li key={item}>• {item}</li>
            ))}
          </ul>
        </Card>
        <Card className="p-6 space-y-3">
          <h3 className="text-sm font-semibold text-slate-900">Next steps</h3>
          <ol className="text-sm text-slate-600 space-y-2" data-testid="product-next-steps">
            {product.next_steps?.map((item: string, index: number) => (
              <li key={item}>{index + 1}. {item}</li>
            ))}
          </ol>
        </Card>
        <Card className="p-6 space-y-3">
          <h3 className="text-sm font-semibold text-slate-900">FAQs</h3>
          <ul className="text-sm text-slate-600 space-y-2" data-testid="product-faqs">
            {product.faqs?.map((item: string) => (
              <li key={item}>• {item}</li>
            ))}
          </ul>
        </Card>
        <Link to="/store" className="text-sm text-blue-600" data-testid="product-back-link">
          Back to store
        </Link>
      </div>
    </div>
  );
}
