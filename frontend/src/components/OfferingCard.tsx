import { ArrowUpRight } from "lucide-react";
import { Link } from "react-router-dom";
import { displayCategory } from "@/lib/categories";

const formatTag = (product: any) => {
  if (product.tag) return product.tag;
  if (product.card_tag) return product.card_tag;
  if (product.is_subscription) return "Subscription";
  return "Project based";
};

const formatPrice = (product: any) => {
  const price = product.base_price;
  if (!price && price !== 0) return null;
  if (price === 0) return "Contact us";
  const formatted = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(price);
  return product.is_subscription ? `${formatted}/mo` : `from ${formatted}`;
};

export default function OfferingCard({ product }: { product: any }) {
  const bullets = product.card_bullets || product.bullets || product.bullets_included || [];
  const description = product.short_description || product.card_description || product.tagline;
  const priceLabel = formatPrice(product);

  return (
    <Link
      to={`/product/${product.id}`}
      className="group flex flex-col rounded-2xl border border-slate-100 bg-white p-6 shadow-sm transition-all hover:shadow-md hover:border-slate-200"
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
          className="text-slate-300 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-slate-600"
          size={16}
        />
      </div>

      <div className="mt-4 flex-1">
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
        {description && (
          <p
            className="mt-1 text-sm leading-relaxed text-slate-500"
            data-testid={`offering-description-${product.id}`}
          >
            {description}
          </p>
        )}
      </div>

      {bullets.length > 0 && (
        <ul className="mt-4 space-y-1.5 text-sm text-slate-500" data-testid={`offering-bullets-${product.id}`}>
          {bullets.map((item: string, idx: number) => (
            <li key={idx} className="flex items-start gap-2">
              <span className="mt-1.5 h-1 w-1 flex-shrink-0 rounded-full" style={{ backgroundColor: "var(--aa-accent)" }} />
              {item}
            </li>
          ))}
        </ul>
      )}

      {/* Pricing + CTA row */}
      <div className="mt-5 flex items-center justify-between border-t border-slate-100 pt-4">
        {priceLabel ? (
          <div data-testid={`offering-price-${product.id}`}>
            <span className="text-lg font-bold text-slate-900">{priceLabel}</span>
          </div>
        ) : (
          <div />
        )}
        <div
          className="flex items-center gap-1.5 text-sm font-semibold text-slate-700"
          data-testid={`offering-cta-${product.id}`}
        >
          View details
          <ArrowUpRight size={14} />
        </div>
      </div>
    </Link>
  );
}
