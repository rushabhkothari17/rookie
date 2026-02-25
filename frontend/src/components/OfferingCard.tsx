import { ArrowUpRight } from "lucide-react";
import { Link } from "react-router-dom";
import { displayCategory } from "@/lib/categories";

const formatTag = (product: any) => {
  if (product.card_tag) return product.card_tag;
  if (product.tag) return product.tag;
  if (product.is_subscription) return "Subscription";
  return "Project based";
};

const fmt = (n: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(n);

/** Derive a minimum starting price from pricing_rules for complex pricing types. */
const getStartingPrice = (product: any): number | null => {
  const { pricing_type, pricing_rules = {} } = product;

  // New data-driven calculator: use price_inputs
  if (pricing_type === "calculator" && pricing_rules.price_inputs?.length > 0) {
    let starting = parseFloat(product.base_price) || 0;
    for (const pi of pricing_rules.price_inputs) {
      if (pi.type === "number" && pi.price_per_unit) {
        const val = parseFloat(pi.default ?? pi.min ?? 0);
        starting += val * pi.price_per_unit;
      }
    }
    return starting > 0 ? starting : null;
  }

  if (pricing_type === "tiered") {
    const prices = (pricing_rules.variants || [])
      .map((v: any) => parseFloat(v.price) || 0)
      .filter((p: number) => p > 0);
    return prices.length > 0 ? Math.min(...prices) : null;
  }

  if (pricing_type === "calculator") {
    const ct = pricing_rules.calc_type;
    if (ct === "health_check") return parseFloat(pricing_rules.base_price) || null;
    if (ct === "hours_pack") {
      const minHours = parseInt(pricing_rules.min_hours) || 10;
      const rate = parseFloat(pricing_rules.pay_now_rate) || 75;
      return minHours * rate;
    }
    if (ct === "bookkeeping") return 249;
    if (ct === "mailboxes") return parseFloat(pricing_rules.rate) || null;
    if (ct === "storage_blocks") return parseFloat(pricing_rules.rate) || null;
    if (ct === "crm_migration") return (parseFloat(pricing_rules.base_fee) || 499) + 250;
    if (ct === "forms_migration") return 100;
    if (ct === "desk_migration") return 499;
    if (ct === "sign_migration") return 99;
    if (ct === "people_migration") return parseFloat(pricing_rules.base_fee) || 999;
  }
  return null;
};

const formatPrice = (product: any): string | null => {
  // Try to derive a starting price first (covers tiered and calculator variants)
  const startingPrice = getStartingPrice(product);
  if (startingPrice !== null && startingPrice > 0) {
    return `Starts from ${fmt(startingPrice)}`;
  }

  // Has a direct base price > 0
  const price = product.base_price;
  if (price != null && price > 0) {
    return product.is_subscription ? `${fmt(price)}/mo` : `from ${fmt(price)}`;
  }

  // inquiry/scope_request or genuinely unpriced → Contact us
  return "Contact us";
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
