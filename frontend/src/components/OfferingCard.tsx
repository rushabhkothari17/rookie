import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { displayCategory } from "@/lib/categories";

const formatPriceLabel = (product: any) => {
  if (product.base_price) {
    return `$${product.base_price.toFixed(2)}`;
  }
  if (product.pricing_type === "tiered") {
    const prices = (product.pricing_rules?.variants || []).map((v: any) => v.price);
    if (prices.length) {
      return `From $${Math.min(...prices).toFixed(2)}`;
    }
  }
  return "Calculator";
};

const formatTag = (product: any) => {
  const parts: string[] = [];
  if (displayCategory(product.category) === "Zoho Express Setup") {
    parts.push("Express");
  }
  if (product.pricing_type === "calculator") {
    parts.push("Calculator");
  } else if (product.is_subscription) {
    parts.push("Subscription");
  } else {
    parts.push("One-time");
  }
  return parts.join(" • ");
};

export default function OfferingCard({ product }: { product: any }) {
  return (
    <div
      className="rounded-3xl bg-white/80 p-6 shadow-[0_18px_45px_rgba(15,23,42,0.08)] backdrop-blur"
      data-testid={`offering-card-${product.id}`}
    >
      <div className="flex items-center justify-between">
        <span
          className="rounded-full bg-slate-900/90 px-3 py-1 text-xs font-semibold text-white"
          data-testid={`offering-tag-${product.id}`}
        >
          {formatTag(product)}
        </span>
        <ArrowUpRight className="text-slate-300" size={16} />
      </div>
      <div className="mt-4 flex items-end justify-between">
        <div>
          <div
            className="text-xs uppercase tracking-[0.2em] text-slate-400"
            data-testid={`offering-category-${product.id}`}
          >
            {displayCategory(product.category)}
          </div>
          <h3
            className="mt-2 text-lg font-semibold text-slate-900"
            data-testid={`offering-name-${product.id}`}
          >
            {product.name}
          </h3>
          <p className="text-sm text-slate-600" data-testid={`offering-tagline-${product.id}`}>
            {product.tagline}
          </p>
        </div>
        <div
          className="text-base font-semibold text-slate-900"
          data-testid={`offering-price-${product.id}`}
        >
          {formatPriceLabel(product)}
        </div>
      </div>
      <ul className="mt-4 space-y-2 text-sm text-slate-500" data-testid={`offering-bullets-${product.id}`}>
        {(product.bullets_included || []).slice(0, 3).map((item: string) => (
          <li key={item}>• {item}</li>
        ))}
      </ul>
      <Button
        className="mt-5 w-full rounded-full bg-slate-900 text-white hover:bg-slate-800"
        asChild
        data-testid={`offering-cta-${product.id}`}
      >
        <Link to={`/product/${product.id}`}>View details</Link>
      </Button>
    </div>
  );
}
