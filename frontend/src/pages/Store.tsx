import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import api from "@/lib/api";
import AppShell from "@/components/AppShell";
import OfferingCard from "@/components/OfferingCard";
import { categoryFromSlug, displayCategory } from "@/lib/categories";
import { useWebsite } from "@/contexts/WebsiteContext";

type StoreFilterOpt = { label: string; value: string };
type StoreFilter = {
  id: string;
  name: string;
  filter_type: string;
  options: StoreFilterOpt[];
  is_active: boolean;
  show_count: boolean;
};

function matchesFilter(product: any, filterType: string, value: string): boolean {
  if (filterType === "category" || filterType === "custom") {
    return displayCategory(product.category).toLowerCase() === value.toLowerCase()
      || (product.category || "").toLowerCase().includes(value.toLowerCase());
  }
  if (filterType === "tag") {
    const tags: string[] = product.tags || [];
    return tags.some(t => t.toLowerCase() === value.toLowerCase());
  }
  if (filterType === "price_range") {
    const [minStr, maxStr] = value.split("-");
    const min = parseFloat(minStr ?? "0");
    const max = parseFloat(maxStr ?? "999999");
    const price = product.base_price ?? product.amount ?? 0;
    return price >= min && price <= max;
  }
  return false;
}

export default function Store() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [products, setProducts] = useState<any[]>([]);
  const [categories, setCategories] = useState<{ name: string; blurb: string }[]>([]);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [configuredFilters, setConfiguredFilters] = useState<StoreFilter[]>([]);
  const [activeFilters, setActiveFilters] = useState<Record<string, string | null>>({});
  const ws = useWebsite();

  useEffect(() => {
    const load = async () => {
      const [prodRes, catRes, filterRes] = await Promise.all([
        api.get("/products"),
        api.get("/categories"),
        api.get("/store/filters").catch(() => ({ data: { filters: [] } })),
      ]);
      const prods: any[] = prodRes.data.products || [];
      setProducts(prods);
      setConfiguredFilters(filterRes.data.filters || []);

      const catMap: Record<string, string> = catRes.data.category_blurbs || {};
      const catCounts: Record<string, number> = {};
      prods.forEach(p => {
        const cat = displayCategory(p.category);
        catCounts[cat] = (catCounts[cat] || 0) + 1;
      });

      const apiCats: { name: string; blurb: string }[] = (catRes.data.categories || [])
        .filter((c: any) => c.is_active && catCounts[c.name])
        .map((c: any) => ({ name: c.name, blurb: catMap[c.name] || c.blurb || "" }));

      Object.keys(catCounts).forEach(name => {
        if (name && name.trim() && !apiCats.find(c => c.name === name)) {
          apiCats.push({ name, blurb: catMap[name] || "" });
        }
      });

      setCategories(apiCats);
      const fromUrl = categoryFromSlug(searchParams.get("category"), apiCats.map(c => c.name));
      setActiveCategory(fromUrl || (apiCats[0]?.name ?? null));
    };
    load();
  }, []);

  const filteredProducts = useMemo(() => {
    let result = activeCategory
      ? products.filter(p => displayCategory(p.category) === activeCategory)
      : products;

    // Apply configured filters
    for (const [filterId, value] of Object.entries(activeFilters)) {
      if (!value) continue;
      const filter = configuredFilters.find(f => f.id === filterId);
      if (!filter) continue;
      result = result.filter(p => matchesFilter(p, filter.filter_type, value));
    }

    return result;
  }, [products, activeCategory, activeFilters, configuredFilters]);

  const handleCategoryChange = (cat: string | null) => {
    setActiveCategory(cat);
    if (cat) setSearchParams({ category: cat.toLowerCase().replace(/\s+/g, "-") });
    else setSearchParams({});
  };

  const toggleFilter = (filterId: string, value: string) => {
    setActiveFilters(prev => ({
      ...prev,
      [filterId]: prev[filterId] === value ? null : value,
    }));
  };

  const hasActiveFilters = Object.values(activeFilters).some(Boolean);

  const activeBlurb = categories.find(c => c.name === activeCategory)?.blurb || "";
  const countFor = (name: string) => products.filter(p => displayCategory(p.category) === name).length;
  const countForOpt = (filter: StoreFilter, value: string) =>
    (activeCategory ? products.filter(p => displayCategory(p.category) === activeCategory) : products)
      .filter(p => matchesFilter(p, filter.filter_type, value)).length;

  return (
    <AppShell showCategoryTabs={false}>
      <div className="space-y-8" data-testid="store-page">

        {/* Hero Banner */}
        <section
          className="relative overflow-hidden rounded-3xl px-10 py-12 shadow-[0_30px_70px_rgba(15,23,42,0.15)]"
          style={{ backgroundColor: "var(--aa-primary)" }}
          data-testid="store-hero"
        >
          <div className="pointer-events-none absolute -right-24 -top-24 h-80 w-80 rounded-full blur-3xl" style={{ backgroundColor: "color-mix(in srgb, var(--aa-accent) 10%, transparent)" }} />
          <div className="pointer-events-none absolute bottom-0 left-0 h-56 w-56 rounded-full blur-2xl" style={{ backgroundColor: "color-mix(in srgb, var(--aa-accent) 5%, transparent)" }} />
          <div className="relative space-y-4">
            <div className="flex items-center gap-2.5">
              <div className="h-0.5 w-8 rounded-full" style={{ backgroundColor: "var(--aa-accent)" }} />
              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
                {ws.hero_label || "Storefront"}
              </p>
            </div>
            <h1 className="text-4xl font-bold text-white" data-testid="store-hero-title">
              {ws.hero_title || "Welcome"}
            </h1>
            {ws.hero_subtitle && (
              <p className="max-w-xl text-base text-slate-300" data-testid="store-hero-subtitle">
                {ws.hero_subtitle}
              </p>
            )}
          </div>
        </section>

        {/* Category Sidebar + Products */}
        <div className="flex gap-8" data-testid="store-layout">

          {/* Left: Category + Configured Filters Sidebar */}
          <aside className="w-52 shrink-0" data-testid="category-sidebar">
            <div className="sticky top-28 space-y-6">
              {/* Category nav */}
              <div>
                <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-3 px-2">Browse</p>
                <nav className="space-y-0.5">
                  {categories.map(cat => (
                    <button
                      key={cat.name}
                      type="button"
                      onClick={() => handleCategoryChange(cat.name)}
                      data-testid={`category-btn-${cat.name}`}
                      className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm transition-all text-left ${
                        activeCategory === cat.name
                          ? "text-white font-semibold"
                          : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                      }`}
                      style={activeCategory === cat.name ? { backgroundColor: "var(--aa-primary)" } : undefined}
                    >
                      <span className="truncate">{cat.name}</span>
                      <span className={`text-xs shrink-0 ml-2 ${activeCategory === cat.name ? "text-slate-300" : "text-slate-400"}`}>
                        {countFor(cat.name)}
                      </span>
                    </button>
                  ))}
                </nav>
              </div>

              {/* Configured Filters */}
              {configuredFilters.length > 0 && (
                <>
                  {hasActiveFilters && (
                    <button
                      type="button"
                      onClick={() => setActiveFilters({})}
                      className="text-xs text-slate-400 hover:text-slate-600 flex items-center gap-1 px-2"
                      data-testid="clear-filters-btn"
                    >
                      ✕ Clear filters
                    </button>
                  )}
                  {configuredFilters.map(filter => (
                    <div key={filter.id} data-testid={`storefront-filter-${filter.id}`}>
                      <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-2 px-2">
                        {filter.name}
                      </p>
                      <div className="space-y-0.5">
                        {filter.filter_type === "category"
                          ? categories.map(cat => (
                              <button
                                key={cat.name}
                                type="button"
                                onClick={() => toggleFilter(filter.id, cat.name)}
                                className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-all text-left ${
                                  activeFilters[filter.id] === cat.name
                                    ? "font-semibold"
                                    : "text-slate-600 hover:bg-slate-100"
                                }`}
                                style={activeFilters[filter.id] === cat.name ? { color: "var(--aa-primary)" } : undefined}
                              >
                                <span className="truncate">{cat.name}</span>
                                {filter.show_count && <span className="text-xs text-slate-400 ml-1">{countFor(cat.name)}</span>}
                              </button>
                            ))
                          : filter.options.map(opt => (
                              <button
                                key={opt.value}
                                type="button"
                                onClick={() => toggleFilter(filter.id, opt.value)}
                                className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-all text-left ${
                                  activeFilters[filter.id] === opt.value
                                    ? "font-semibold"
                                    : "text-slate-600 hover:bg-slate-100"
                                }`}
                                style={activeFilters[filter.id] === opt.value ? { color: "var(--aa-primary)" } : undefined}
                              >
                                <span className="truncate">{opt.label}</span>
                                {filter.show_count && (
                                  <span className="text-xs text-slate-400 ml-1">
                                    {countForOpt(filter, opt.value)}
                                  </span>
                                )}
                              </button>
                            ))
                        }
                      </div>
                    </div>
                  ))}
                </>
              )}
            </div>
          </aside>

          {/* Right: Products */}
          <div className="flex-1 min-w-0" data-testid="products-area">
            {activeCategory && (
              <div className="mb-6">
                <h2 className="text-2xl font-bold text-slate-900" data-testid="active-category-title">
                  {activeCategory}
                </h2>
                {activeBlurb && (
                  <p className="text-sm text-slate-500 mt-1" data-testid="category-blurb">
                    {activeBlurb}
                  </p>
                )}
                <p className="text-xs text-slate-400 mt-1" data-testid="store-product-count">
                  {filteredProducts.length} offering{filteredProducts.length !== 1 ? "s" : ""}
                </p>
              </div>
            )}
            {filteredProducts.length === 0 ? (
              <p className="text-slate-400 text-sm py-12 text-center">No products match the selected filters.</p>
            ) : (
              <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3" data-testid="products-grid">
                {filteredProducts.map(product => (
                  <OfferingCard key={product.id} product={product} />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
