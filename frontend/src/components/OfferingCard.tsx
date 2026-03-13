import { motion } from "framer-motion";
import { ArrowUpRight, ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";
import { displayCategory } from "@/lib/categories";

const formatTag = (product: any) => {
  if (product.card_tag) return product.card_tag;
  if (product.is_subscription) return "Subscription";
  return "Project based";
};

const fmtPrice = (amount: number, currency = "USD") =>
  new Intl.NumberFormat("en-US", { style: "currency", currency, minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(amount);

/** Derive a minimum starting price from intake questions for data-driven pricing. */
const getStartingPrice = (product: any): number | null => {
  const base = parseFloat(product.base_price) || 0;
  const schema = product.intake_schema_json;
  if (!schema) {
    let starting = base > 0 ? base : null;
    if (starting !== null && product.price_rounding) {
      const nearest: Record<string, number> = {"25": 25, "50": 50, "100": 100};
      const n = nearest[String(product.price_rounding)];
      if (n) starting = Math.ceil(starting / n) * n;
    }
    return starting;
  }

  const questions = Array.isArray(schema.questions)
    ? schema.questions
    : Object.values(schema.questions || {}).flat();

  let minAdd = 0;
  let hasPricedRequired = false;

  for (const q of questions as any[]) {
    if (!q.enabled && q.enabled !== undefined) continue;
    if (q.type === "number" && parseFloat(q.price_per_unit) > 0 && q.required) {
      hasPricedRequired = true;
      minAdd += (parseFloat(q.min) || 0) * parseFloat(q.price_per_unit);
    } else if ((q.type === "dropdown" || q.type === "multiselect") && q.affects_price && q.required) {
      if ((q.price_mode || "add") !== "multiply") {
        const prices = (q.options || []).map((o: any) => parseFloat(o.price_value) || 0).filter((p: number) => p > 0);
        if (prices.length > 0) { hasPricedRequired = true; minAdd += Math.min(...prices); }
      }
    }
  }

  if (base > 0 || hasPricedRequired) {
    let starting = base + minAdd;
    if (product.price_rounding) {
      const nearest: Record<string, number> = {"25": 25, "50": 50, "100": 100};
      const n = nearest[String(product.price_rounding)];
      if (n) starting = Math.ceil(starting / n) * n;
    }
    return starting;
  }
  return null;
};

const formatPrice = (product: any): { label: string; prefix?: string } => {
  const type = product.pricing_type;
  const currency = product.currency || "USD";

  if (type === "external") return { label: "Visit site", prefix: "" };
  if (type === "enquiry") return { label: "Get in touch", prefix: "" };

  const starting = getStartingPrice(product);
  if (starting !== null && starting > 0) {
    const hasIntake = Array.isArray(product.intake_schema_json?.questions)
      ? product.intake_schema_json.questions.some((q: any) => q.enabled !== false && (q.price_per_unit > 0 || q.affects_price))
      : false;
    const prefix = (hasIntake || !product.base_price) ? "From" : "";
    return { label: fmtPrice(starting, currency), prefix };
  }
  if (starting === 0 && product.base_price === 0) return { label: "Free", prefix: "" };

  if (type === "scope_request" || type === "inquiry") return { label: "Get in touch", prefix: "" };

  return { label: "Contact us", prefix: "" };
};

export default function OfferingCard({ product, index = 0 }: { product: any; index?: number }) {
  const description = product.card_description;
  const bullets = product.card_bullets?.length > 0 ? product.card_bullets : [];
  const priceInfo = formatPrice(product);
  const isExternal = product.pricing_type === "external";

  const content = (
    <>
      <div className="flex items-center justify-between">
        <span
          className="aa-badge aa-badge-muted transition-colors"
          data-testid={`offering-tag-${product.id}`}
        >
          {formatTag(product)}
        </span>
        {isExternal
          ? <ExternalLink className="transition-colors" size={16} style={{ color: "var(--aa-muted)" }} />
          : <ArrowUpRight
              className="transition-all duration-200 group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
              size={16}
              style={{ color: "var(--aa-muted)" }}
            />
        }
      </div>

      <div className="mt-4 flex-1">
        <div className="text-xs font-medium uppercase tracking-[0.2em] aa-mono" style={{ color: "var(--aa-muted)" }} data-testid={`offering-category-${product.id}`}>
          {displayCategory(product.category)}
        </div>
        <h3 className="mt-2 text-lg font-bold line-clamp-2 break-words" style={{ color: "var(--aa-text)" }} data-testid={`offering-name-${product.id}`}>
          {product.name}
        </h3>
        {description && (
          <p className="mt-1 text-sm leading-relaxed" style={{ color: "var(--aa-muted)" }} data-testid={`offering-description-${product.id}`}>
            {description}
          </p>
        )}
      </div>

      {bullets.length > 0 && (
        <ul className="mt-4 space-y-1.5 text-sm" style={{ color: "var(--aa-muted)" }} data-testid={`offering-bullets-${product.id}`}>
          {bullets.map((item: string, idx: number) => (
            <li key={idx} className="flex items-start gap-2">
              <span className="mt-1.5 h-1 w-1 flex-shrink-0 rounded-full" style={{ backgroundColor: "var(--aa-accent)" }} />
              {item}
            </li>
          ))}
        </ul>
      )}

      <div className="mt-5 flex items-center justify-between pt-4" style={{ borderTop: "1px solid var(--aa-border)" }}>
        <div data-testid={`offering-price-${product.id}`}>
          {priceInfo.prefix && <span className="text-xs font-medium mr-1 aa-mono" style={{ color: "var(--aa-muted)" }}>{priceInfo.prefix} </span>}
          <span className="text-lg font-bold aa-mono" style={{ color: "var(--aa-text)" }}>{priceInfo.label}</span>
        </div>
        <div className="flex items-center gap-1.5 text-sm font-semibold transition-colors aa-btn-ripple px-3 py-1.5 rounded-lg" style={{ color: "var(--aa-primary)", backgroundColor: "color-mix(in srgb, var(--aa-primary) 10%, transparent)" }} data-testid={`offering-cta-${product.id}`}>
          {isExternal ? "Visit site" : "View details"}
          {isExternal ? <ExternalLink size={14} /> : <ArrowUpRight size={14} />}
        </div>
      </div>
    </>
  );

  const cardClass = "flex flex-col rounded-2xl p-6 h-full transition-all duration-300 aa-card aa-card-glow";

  return (
    <motion.div
      className="group"
      data-testid={`offering-card-${product.id}`}
      initial={{ opacity: 0, y: 28 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -7, transition: { type: "spring", stiffness: 380, damping: 26 } }}
      transition={{
        duration: 0.42,
        delay: Math.min(index * 0.07, 0.42),
        ease: [0.16, 1, 0.3, 1],
      }}
    >
      {isExternal && product.external_url ? (
        <a
          href={product.external_url}
          target="_blank"
          rel="noopener noreferrer"
          className={cardClass}
        >
          {content}
        </a>
      ) : (
        <Link
          to={`/product/${product.id}`}
          className={cardClass}
        >
          {content}
        </Link>
      )}
    </motion.div>
  );
}
