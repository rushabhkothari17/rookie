import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { displayCategory } from "@/lib/categories";

const formatTag = (product: any) => {
  if (product.card_tag) return product.card_tag;
  if (product.is_subscription) return "Subscription";
  if (product.pricing_type === "fixed" || product.pricing_type === "tiered") {
    return "Project based";
  }
  return "Project based";
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
            {product.card_title || product.name}
          </h3>
          <p
            className="text-sm text-slate-600"
            data-testid={`offering-tagline-${product.id}`}
          >
            {product.card_description || product.tagline}
          </p>
        </div>
      </div>
      <ul className="mt-4 space-y-2 text-sm text-slate-500" data-testid={`offering-bullets-${product.id}`}>
        {(product.card_bullets || product.bullets_included || []).slice(0, 3).map((item: string) => (
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
