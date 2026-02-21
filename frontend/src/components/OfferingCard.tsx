import { ArrowUpRight } from "lucide-react";
import { Link } from "react-router-dom";
import { displayCategory } from "@/lib/categories";

const formatTag = (product: any) => {
  if (product.card_tag) return product.card_tag;
  if (product.is_subscription) return "Subscription";
  return "Project based";
};

export default function OfferingCard({ product }: { product: any }) {
  return (
    <Link
      to={`/product/${product.id}`}
      className="group block rounded-2xl border border-slate-100 bg-white p-6 shadow-sm transition-all hover:shadow-md hover:border-slate-200"
      data-testid={`offering-card-${product.id}`}
    >
      <div className="flex items-center justify-between">
        <span
          className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600"
          data-testid={`offering-tag-${product.id}`}
        >
          {formatTag(product)}
        </span>
        <ArrowUpRight
          className="text-slate-300 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-red-500"
          size={16}
        />
      </div>

      <div className="mt-4">
        <div
          className="text-xs font-medium uppercase tracking-[0.2em] text-slate-400"
          data-testid={`offering-category-${product.id}`}
        >
          {displayCategory(product.category)}
        </div>
        <h3
          className="mt-2 text-lg font-bold text-slate-900"
          data-testid={`offering-name-${product.id}`}
        >
          {product.card_title || product.name}
        </h3>
        <p
          className="mt-1 text-sm leading-relaxed text-slate-500"
          data-testid={`offering-tagline-${product.id}`}
        >
          {product.card_description || product.tagline}
        </p>
      </div>

      <ul className="mt-4 space-y-1.5 text-sm text-slate-500" data-testid={`offering-bullets-${product.id}`}>
        {(product.card_bullets || product.bullets || product.bullets_included || []).slice(0, 3).map((item: string) => (
          <li key={item} className="flex items-start gap-2">
            <span className="mt-1.5 h-1 w-1 flex-shrink-0 rounded-full bg-red-400" />
            {item}
          </li>
        ))}
      </ul>

      <div
        className="mt-5 flex items-center gap-1.5 text-sm font-semibold text-slate-700"
        data-testid={`offering-cta-${product.id}`}
      >
        View details
        <ArrowUpRight size={14} />
      </div>
    </Link>
  );
}
