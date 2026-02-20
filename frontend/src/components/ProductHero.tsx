import { displayCategory } from "@/lib/categories";

const outcomeCopy = (product: any) => [
  {
    title: "Outcome",
    body: product.tagline || "Clear delivery milestones aligned to your goals.",
  },
  {
    title: "Automation",
    body: "Workflow credits and automation clarity baked in from day one.",
  },
  {
    title: "Support",
    body: "Dedicated delivery lead with structured check-ins.",
  },
];

export default function ProductHero({ product }: { product: any }) {
  const tags = [displayCategory(product.category)];
  if (product.card_tag) tags.push(product.card_tag);
  if (product.pricing_rules?.bundle_free_items?.length) {
    tags.push("Includes 1 month support");
  }

  return (
    <div className="space-y-6" data-testid="product-hero">
      <div className="flex flex-wrap gap-2">
        {tags.map((tag) => (
          <span
            key={tag}
            className="rounded-full bg-white/80 px-3 py-1 text-xs font-semibold text-slate-600 shadow-sm"
            data-testid={`product-hero-tag-${tag.replace(/\s+/g, "-").toLowerCase()}`}
          >
            {tag}
          </span>
        ))}
      </div>
      <div className="rounded-3xl bg-white/80 p-8 shadow-[0_24px_60px_rgba(15,23,42,0.12)] backdrop-blur">
        <h1 className="text-4xl font-semibold text-slate-900" data-testid="product-hero-title">
          {product.name}
        </h1>
        <p className="mt-3 text-base text-slate-600" data-testid="product-hero-description">
          {product.description_long}
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-3" data-testid="product-outcome-strip">
        {outcomeCopy(product).map((item) => (
          <div
            key={item.title}
            className="rounded-2xl bg-white/70 p-4 text-sm text-slate-600 shadow-[0_12px_30px_rgba(15,23,42,0.08)]"
            data-testid={`product-outcome-${item.title.toLowerCase()}`}
          >
            <div className="text-xs uppercase tracking-[0.2em] text-slate-400">
              {item.title}
            </div>
            <p className="mt-2 text-sm text-slate-700">{item.body}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
