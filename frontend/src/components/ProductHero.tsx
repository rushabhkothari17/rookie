import { displayCategory } from "@/lib/categories";

export default function ProductHero({ product }: { product: any }) {
  const categoryLabel = displayCategory(product.category);

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

          {(product.description_long || product.tagline || product.short_description) && (
            <p
              className="mt-5 max-w-2xl text-base leading-relaxed text-slate-300"
              data-testid="product-hero-description"
            >
              {product.description_long || product.tagline || product.short_description}
            </p>
          )}

          {(product.bullets || []).length > 0 && (
            <ul className="mt-5 space-y-1.5" data-testid="product-hero-bullets">
              {(product.bullets as string[]).map((b, i) => (
                <li key={i} className="flex items-start gap-2.5 text-sm text-slate-300">
                  <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full" style={{ backgroundColor: "var(--aa-accent)" }} />
                  {b}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
