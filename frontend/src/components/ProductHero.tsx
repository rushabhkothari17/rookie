import { displayCategory } from "@/lib/categories";

const outcomeCopy = (product: any) => {
  const items = [];
  const outcome = product.outcome || product.tagline;
  if (outcome) items.push({ title: "Outcome", body: outcome });
  if (product.automation_details) items.push({ title: "Automation", body: product.automation_details });
  if (product.support_details) items.push({ title: "Support", body: product.support_details });
  if (items.length === 0) {
    items.push({ title: "Outcome", body: product.tagline || "Clear delivery milestones aligned to your goals." });
    items.push({ title: "Automation", body: "Workflow credits and automation clarity baked in from day one." });
    items.push({ title: "Support", body: "Dedicated delivery lead with structured check-ins." });
  }
  return items;
};

export default function ProductHero({ product }: { product: any }) {
  const categoryLabel = displayCategory(product.category);
  const items = outcomeCopy(product);

  return (
    <div data-testid="product-hero">
      {/* Dark hero banner */}
      <div className="relative overflow-hidden rounded-3xl bg-[#0f172a] px-8 py-12 md:px-14 md:py-16">
        <div className="pointer-events-none absolute -right-24 -top-24 h-80 w-80 rounded-full bg-red-600/10 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-16 left-12 h-56 w-56 rounded-full bg-red-600/5 blur-2xl" />

        <div className="relative">
          <div className="mb-4 flex items-center gap-2.5">
            <div className="h-0.5 w-8 rounded-full bg-red-500" />
            <span className="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400">
              {categoryLabel}
            </span>
          </div>

          <h1
            className="text-4xl font-bold leading-tight text-white sm:text-5xl"
            data-testid="product-hero-title"
          >
            {product.name}
          </h1>

          {product.description_long && (
            <p
              className="mt-5 max-w-2xl text-base leading-relaxed text-slate-300"
              data-testid="product-hero-description"
            >
              {product.description_long}
            </p>
          )}
        </div>
      </div>

      {/* Outcome strip */}
      <div className="mt-4 grid gap-4 md:grid-cols-3" data-testid="product-outcome-strip">
        {items.map((item) => (
          <div
            key={item.title}
            className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm"
            data-testid={`product-outcome-${item.title.toLowerCase()}`}
          >
            <div className="mb-2 flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-red-500" />
              <span className="text-xs font-semibold uppercase tracking-widest text-slate-400">
                {item.title}
              </span>
            </div>
            <p className="text-sm leading-relaxed text-slate-700">{item.body}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
