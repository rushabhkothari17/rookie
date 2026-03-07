import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { X, ArrowUpDown, Search } from "lucide-react";
import api from "@/lib/api";
import AppShell from "@/components/AppShell";
import OfferingCard from "@/components/OfferingCard";
import { categoryFromSlug, displayCategory } from "@/lib/categories";
import { useWebsite, usePartnerCode } from "@/contexts/WebsiteContext";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

type StoreFilterOpt = { label: string; value: string };
type StoreFilter = {
  id: string;
  name: string;
  filter_type: string;
  options: StoreFilterOpt[];
  is_active: boolean;
  show_count: boolean;
};

type SortOption = "default" | "name_asc" | "name_desc" | "price_asc" | "price_desc";

function matchesFilter(product: any, filterType: string, value: string): boolean {
  if (filterType === "category") {
    return displayCategory(product.category).toLowerCase() === value.toLowerCase()
      || (product.category || "").toLowerCase().includes(value.toLowerCase());
  }
  if (filterType === "tag" || filterType === "custom") {
    const tags: string[] = product.tags || [];
    return tags.some(t => t.toLowerCase() === value.toLowerCase());
  }
  if (filterType === "price_range") {
    const [rangePart, currencyPart] = value.split(":");
    const parts = rangePart.split("-");
    const min = parseFloat(parts[0] ?? "0");
    const max = parseFloat(parts[1] ?? "999999");
    const price = product.base_price ?? product.amount ?? 0;
    const inRange = price >= min && (isNaN(max) ? true : price <= max);
    if (currencyPart && currencyPart !== "ALL") {
      return inRange && (product.currency || "").toUpperCase() === currencyPart.toUpperCase();
    }
    return inRange;
  }
  if (filterType === "checkout_type") {
    const pt = (product.pricing_type || "internal").toLowerCase();
    if (value === "internal") return pt === "internal";
    if (value === "enquiry") return pt === "enquiry" || pt === "scope_request" || pt === "inquiry";
    if (value === "external") return pt === "external";
    return false;
  }
  if (filterType === "billing_type") {
    if (value === "subscription") return product.is_subscription === true;
    if (value === "one_off") return !product.is_subscription;
    return false;
  }
  if (filterType === "intake_field") {
    // value format: "fieldkey:optionvalue"
    const colonIdx = value.indexOf(":");
    if (colonIdx === -1) return false;
    const fieldKey = value.slice(0, colonIdx).toLowerCase();
    const optionVal = value.slice(colonIdx + 1).toLowerCase();
    // Intake schema uses schema.questions[].key (not schema.groups[].fields[])
    const questions: any[] = product.intake_schema_json?.questions || [];
    for (const q of questions) {
      const qKey = (q.key || q.label || "").toLowerCase();
      if (qKey === fieldKey) {
        const opts: any[] = q.options || [];
        return opts.some((o: any) => {
          const v = typeof o === "string" ? o : (o.value ?? o.label ?? "");
          return String(v).toLowerCase() === optionVal;
        });
      }
    }
    return false;
  }
  return false;
}

// Auto-generated options for filter types that don't need admin-defined options
const AUTO_OPTIONS: Record<string, { label: string; value: string }[]> = {
  checkout_type: [
    { label: "Internal Checkout", value: "internal" },
    { label: "Enquiry Only",      value: "enquiry" },
    { label: "External Link",     value: "external" },
  ],
  billing_type: [
    { label: "One-off",      value: "one_off" },
    { label: "Subscription", value: "subscription" },
  ],
};

const SORT_LABELS: Record<SortOption, string> = {
  default: "Default",
  name_asc: "Name: A → Z",
  name_desc: "Name: Z → A",
  price_asc: "Price: Low → High",
  price_desc: "Price: High → Low",
};

export default function Store() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [products, setProducts] = useState<any[]>([]);
  const [categories, setCategories] = useState<{ name: string; blurb: string }[]>([]);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [configuredFilters, setConfiguredFilters] = useState<StoreFilter[]>([]);
  const [activeFilters, setActiveFilters] = useState<Record<string, string | null>>({});
  const [priceInputs, setPriceInputs] = useState<Record<string, { min: string; max: string; currency: string }>>({});
  const [sortBy, setSortBy] = useState<SortOption>("default");
  const [fxRates, setFxRates] = useState<Record<string, number>>({});
  const [searchQuery, setSearchQuery] = useState("");
  const ws = useWebsite();
  const partnerCode = usePartnerCode();

  useEffect(() => {
    const load = async () => {
      const filterUrl = partnerCode
        ? `/store/filters?tenant_code=${encodeURIComponent(partnerCode)}`
        : "/store/filters";
      const productsUrl = partnerCode
        ? `/products?partner_code=${encodeURIComponent(partnerCode)}`
        : "/products";
      const [prodRes, catRes, filterRes, fxRes] = await Promise.all([
        api.get(productsUrl),
        api.get("/categories"),
        api.get(filterUrl).catch(() => ({ data: { filters: [] } })),
        api.get("/store/fx-rates?base=USD").catch(() => ({ data: { rates: {} } })),
      ]);
      const prods: any[] = prodRes.data.products || [];
      setProducts(prods);
      setConfiguredFilters(filterRes.data.filters || []);
      setFxRates(fxRes.data.rates || {});

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
      setActiveCategory(fromUrl || null);
    };
    load();
  }, [partnerCode]);

  const filteredProducts = useMemo(() => {
    let result = activeCategory
      ? products.filter(p => displayCategory(p.category) === activeCategory)
      : products;

    // Search filter
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(p =>
        (p.name || "").toLowerCase().includes(q) ||
        (p.description_long || "").toLowerCase().includes(q)
      );
    }

    for (const [filterId, value] of Object.entries(activeFilters)) {
      if (!value) continue;
      const filter = configuredFilters.find(f => f.id === filterId);
      if (!filter) continue;
      result = result.filter(p => matchesFilter(p, filter.filter_type, value));
    }

    // Sort — normalise to USD before comparing prices
    result = [...result];
    const toUSD = (p: any) => {
      const price = p.base_price ?? p.amount ?? 0;
      const cur = (p.currency || "USD").toUpperCase();
      const rate = fxRates[cur] ?? 1;
      return price * rate;
    };
    if (sortBy === "name_asc") result.sort((a, b) => (a.name || "").localeCompare(b.name || ""));
    else if (sortBy === "name_desc") result.sort((a, b) => (b.name || "").localeCompare(a.name || ""));
    else if (sortBy === "price_asc") result.sort((a, b) => toUSD(a) - toUSD(b));
    else if (sortBy === "price_desc") result.sort((a, b) => toUSD(b) - toUSD(a));

    return result;
  }, [products, activeCategory, activeFilters, configuredFilters, sortBy, fxRates, searchQuery]);

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

  const applyPriceFilter = (filterId: string) => {
    const { min, max, currency } = priceInputs[filterId] || { min: "", max: "", currency: "ALL" };
    if (!min && !max && (!currency || currency === "ALL")) {
      setActiveFilters(prev => ({ ...prev, [filterId]: null }));
      return;
    }
    const minVal = min || "0";
    const maxVal = max || "999999";
    const currencyPart = currency && currency !== "ALL" ? `:${currency}` : "";
    setActiveFilters(prev => ({ ...prev, [filterId]: `${minVal}-${maxVal}${currencyPart}` }));
  };

  const clearPriceFilter = (filterId: string) => {
    setPriceInputs(prev => ({ ...prev, [filterId]: { min: "", max: "", currency: "ALL" } }));
    setActiveFilters(prev => ({ ...prev, [filterId]: null }));
  };

  const clearAllFilters = () => {
    setActiveFilters({});
    setPriceInputs({});
    setActiveCategory(null);
    setSearchQuery("");
    setSearchParams({});
  };

  const productCurrencies = useMemo(() => {
    const seen = new Set<string>();
    products.forEach(p => { if (p.currency) seen.add(p.currency.toUpperCase()); });
    return Array.from(seen).sort();
  }, [products]);

  // Auto-discover intake field options from products when filter has no manual options
  const derivedFilterOptions = useMemo(() => {
    const result: Record<string, { label: string; value: string }[]> = {};
    configuredFilters.forEach(filter => {
      if (filter.filter_type !== "intake_field" || filter.options.length > 0) return;
      const filterKey = filter.name.toLowerCase().replace(/\s+/g, "_");
      const seen = new Map<string, string>(); // encoded-value → display label
      products.forEach(product => {
        const questions: any[] = product.intake_schema_json?.questions || [];
        questions.forEach(q => {
          const qKey = (q.key || "").toLowerCase();
          const qLabel = (q.label || "").toLowerCase();
          if (qKey === filterKey || qLabel === filterKey || qKey === filter.name.toLowerCase()) {
            (q.options || []).forEach((opt: any) => {
              const v = typeof opt === "string" ? opt : (opt.value ?? opt.label ?? "");
              const l = typeof opt === "string" ? opt : (opt.label ?? opt.value ?? "");
              const encodedValue = `${qKey}:${String(v).toLowerCase()}`;
              if (!seen.has(encodedValue)) seen.set(encodedValue, l);
            });
          }
        });
      });
      result[filter.id] = Array.from(seen.entries()).map(([value, label]) => ({ label, value }));
    });
    return result;
  }, [configuredFilters, products]);

  const hasActiveFilters = Object.values(activeFilters).some(Boolean) || activeCategory !== null || searchQuery.trim() !== "";
  const countFor = (name: string) => products.filter(p => displayCategory(p.category) === name).length;
  const countForOpt = (filter: StoreFilter, value: string) =>
    (activeCategory ? products.filter(p => displayCategory(p.category) === activeCategory) : products)
      .filter(p => matchesFilter(p, filter.filter_type, value)).length;

  // Active filter pills
  const activeFilterPills: { label: string; onRemove: () => void }[] = [];
  if (searchQuery.trim()) {
    activeFilterPills.push({ label: `"${searchQuery}"`, onRemove: () => setSearchQuery("") });
  }
  if (activeCategory) {
    activeFilterPills.push({ label: activeCategory, onRemove: () => handleCategoryChange(null) });
  }
  configuredFilters.forEach(f => {
    const val = activeFilters[f.id];
    if (!val) return;
    if (f.filter_type === "price_range") {
      const [range, cur] = val.split(":");
      const [mn, mx] = range.split("-");
      const label = `${f.name}: ${mn !== "0" ? mn : "0"}–${mx !== "999999" ? mx : "∞"}${cur && cur !== "ALL" ? ` (${cur})` : ""}`;
      activeFilterPills.push({ label, onRemove: () => clearPriceFilter(f.id) });
    } else {
      // For auto-option types, look up label from AUTO_OPTIONS first
      const autoOpts = AUTO_OPTIONS[f.filter_type] || [];
      const derivedOpts = derivedFilterOptions[f.id] || [];
      const optLabel =
        autoOpts.find(o => o.value === val)?.label ||
        derivedOpts.find(o => o.value === val)?.label ||
        f.options.find(o => o.value === val)?.label ||
        val;
      activeFilterPills.push({ label: `${f.name}: ${optLabel}`, onRemove: () => toggleFilter(f.id, val) });
    }
  });

  const displayTitle = activeCategory || "All Services";
  const activeBlurb = categories.find(c => c.name === activeCategory)?.blurb || "";

  return (
    <AppShell showCategoryTabs={false}>
      <div className="space-y-8" data-testid="store-page">

        {/* Hero Banner */}
        <section
          className="relative overflow-hidden rounded-3xl px-10 py-12 shadow-[0_30px_70px_rgba(15,23,42,0.15)]"
          style={{ backgroundColor: "var(--aa-primary)" }}
          data-testid="store-hero"
        >
          <div className="hero-blob-1 pointer-events-none absolute -right-24 -top-24 h-80 w-80 rounded-full blur-3xl" style={{ backgroundColor: "color-mix(in srgb, var(--aa-accent) 10%, transparent)" }} />
          <div className="hero-blob-2 pointer-events-none absolute bottom-0 left-0 h-56 w-56 rounded-full blur-2xl" style={{ backgroundColor: "color-mix(in srgb, var(--aa-accent) 5%, transparent)" }} />
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

        {/* Sidebar + Products */}
        <div className="flex gap-8" data-testid="store-layout">

          {/* ── Left Sidebar ── */}
          <aside className="w-64 shrink-0" data-testid="category-sidebar">
            <div className="sticky top-28 space-y-7">

              {/* Browse / Categories */}
              <div>
                <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-3">Browse</p>
                <nav className="space-y-0.5" role="navigation" aria-label="Product categories">
                  {/* All */}
                  <button
                    type="button"
                    onClick={() => handleCategoryChange(null)}
                    data-testid="category-btn-all"
                    className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm transition-all duration-150 text-left group ${
                      activeCategory === null
                        ? "font-semibold text-slate-900 bg-slate-100"
                        : "text-slate-500 hover:bg-slate-50 hover:text-slate-900"
                    }`}
                  >
                    <span className="flex items-center gap-2">
                      {activeCategory === null && (
                        <span className="w-1 h-4 rounded-full shrink-0" style={{ backgroundColor: "var(--aa-primary)" }} />
                      )}
                      <span>All</span>
                    </span>
                    <span className={`text-[11px] font-mono px-1.5 py-0.5 rounded ${
                      activeCategory === null
                        ? "bg-white text-slate-700 shadow-sm"
                        : "bg-slate-100 text-slate-400 group-hover:bg-white group-hover:text-slate-700"
                    }`}>
                      {products.length}
                    </span>
                  </button>

                  {categories.map(cat => (
                    <button
                      key={cat.name}
                      type="button"
                      onClick={() => handleCategoryChange(cat.name)}
                      data-testid={`category-btn-${cat.name}`}
                      className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm transition-all duration-150 text-left group ${
                        activeCategory === cat.name
                          ? "font-semibold text-slate-900 bg-slate-100"
                          : "text-slate-500 hover:bg-slate-50 hover:text-slate-900"
                      }`}
                    >
                      <span className="flex items-center gap-2 min-w-0">
                        {activeCategory === cat.name && (
                          <span className="w-1 h-4 rounded-full shrink-0" style={{ backgroundColor: "var(--aa-primary)" }} />
                        )}
                        <span className="truncate">{cat.name}</span>
                      </span>
                      <span className={`text-[11px] font-mono px-1.5 py-0.5 rounded shrink-0 ml-2 ${
                        activeCategory === cat.name
                          ? "bg-white text-slate-700 shadow-sm"
                          : "bg-slate-100 text-slate-400 group-hover:bg-white group-hover:text-slate-700"
                      }`}>
                        {countFor(cat.name)}
                      </span>
                    </button>
                  ))}
                </nav>
              </div>

              {/* Configured Filters */}
              {configuredFilters.length > 0 && configuredFilters.map(filter => (
                <div key={filter.id} data-testid={`storefront-filter-${filter.id}`}>
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">
                      {filter.name}
                    </p>
                    {activeFilters[filter.id] && filter.filter_type !== "price_range" && (
                      <button
                        type="button"
                        onClick={() => toggleFilter(filter.id, activeFilters[filter.id]!)}
                        className="text-[10px] text-slate-400 hover:text-slate-700 transition-colors"
                        aria-label="Clear filter"
                      >
                        Clear
                      </button>
                    )}
                  </div>

                  {/* Price Range */}
                  {filter.filter_type === "price_range" ? (
                    <div className="space-y-2.5" data-testid={`price-range-filter-${filter.id}`}>
                      {productCurrencies.length > 1 && (
                        <Select
                          value={priceInputs[filter.id]?.currency || "ALL"}
                          onValueChange={val => setPriceInputs(prev => ({
                            ...prev,
                            [filter.id]: { ...prev[filter.id], currency: val }
                          }))}
                        >
                          <SelectTrigger
                            className="h-8 text-xs bg-white border-slate-200 focus:border-slate-900 focus:ring-1 focus:ring-slate-900/20"
                            data-testid={`price-currency-select-${filter.id}`}
                          >
                            <SelectValue placeholder="Currency" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="ALL" className="text-xs">All currencies</SelectItem>
                            {productCurrencies.map(c => (
                              <SelectItem key={c} value={c} className="text-xs">{c}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      )}
                      <div className="grid grid-cols-2 gap-2">
                        <div className="relative">
                          <input
                            type="number"
                            min="0"
                            placeholder="Min"
                            value={priceInputs[filter.id]?.min || ""}
                            onChange={e => setPriceInputs(prev => ({
                              ...prev,
                              [filter.id]: { ...prev[filter.id], min: e.target.value }
                            }))}
                            onKeyDown={e => e.key === "Enter" && applyPriceFilter(filter.id)}
                            className="w-full h-8 rounded-md border border-slate-200 px-3 text-sm outline-none focus:border-slate-900 focus:ring-1 focus:ring-slate-900/20 transition-all bg-white placeholder:text-slate-400"
                            data-testid={`price-min-input-${filter.id}`}
                          />
                        </div>
                        <div className="relative">
                          <input
                            type="number"
                            min="0"
                            placeholder="Max"
                            value={priceInputs[filter.id]?.max || ""}
                            onChange={e => setPriceInputs(prev => ({
                              ...prev,
                              [filter.id]: { ...prev[filter.id], max: e.target.value }
                            }))}
                            onKeyDown={e => e.key === "Enter" && applyPriceFilter(filter.id)}
                            className="w-full h-8 rounded-md border border-slate-200 px-3 text-sm outline-none focus:border-slate-900 focus:ring-1 focus:ring-slate-900/20 transition-all bg-white placeholder:text-slate-400"
                            data-testid={`price-max-input-${filter.id}`}
                          />
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => applyPriceFilter(filter.id)}
                          className="flex-1 h-8 rounded-md text-xs font-semibold text-white transition-all hover:opacity-90"
                          style={{ backgroundColor: "var(--aa-primary)" }}
                          data-testid={`price-apply-btn-${filter.id}`}
                        >
                          Apply
                        </button>
                        {activeFilters[filter.id] && (
                          <button
                            type="button"
                            onClick={() => clearPriceFilter(filter.id)}
                            className="h-8 px-3 rounded-md text-xs text-slate-500 hover:text-slate-900 border border-slate-200 hover:border-slate-300 transition-all bg-white"
                            data-testid={`price-clear-btn-${filter.id}`}
                          >
                            Clear
                          </button>
                        )}
                      </div>
                    </div>

                  ) : filter.filter_type === "category" ? (
                    /* Category filter options */
                    <div className="space-y-0.5">
                      {categories.map(cat => (
                        <FilterOptionButton
                          key={cat.name}
                          label={cat.name}
                          count={filter.show_count ? countFor(cat.name) : undefined}
                          active={activeFilters[filter.id] === cat.name}
                          onClick={() => toggleFilter(filter.id, cat.name)}
                        />
                      ))}
                    </div>
                  ) : (
                    /* Custom / Tag / Intake / Checkout / Billing filter options */
                    <div className="space-y-0.5">
                      {(AUTO_OPTIONS[filter.filter_type] || derivedFilterOptions[filter.id] || filter.options).map(opt => (
                        <FilterOptionButton
                          key={opt.value}
                          label={opt.label}
                          count={filter.show_count ? countForOpt(filter, opt.value) : undefined}
                          active={activeFilters[filter.id] === opt.value}
                          onClick={() => toggleFilter(filter.id, opt.value)}
                        />
                      ))}
                    </div>
                  )}
                </div>
              ))}

              {/* Clear all */}
              {hasActiveFilters && (
                <button
                  type="button"
                  onClick={clearAllFilters}
                  className="w-full text-xs text-slate-400 hover:text-slate-700 flex items-center justify-center gap-1.5 py-2 rounded-lg border border-slate-200 hover:border-slate-300 transition-all bg-white"
                  data-testid="clear-filters-btn"
                >
                  <X className="h-3 w-3" />
                  Clear all filters
                </button>
              )}
            </div>
          </aside>

          {/* ── Right: Products ── */}
          <div className="flex-1 min-w-0" data-testid="products-area">

            {/* Header row: title + active pills + sort */}
            <div className="mb-6 space-y-3">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-xl font-bold text-slate-900" data-testid="active-category-title">
                    {displayTitle}
                  </h2>
                  {activeBlurb && (
                    <p className="text-sm text-slate-500 mt-0.5" data-testid="category-blurb">
                      {activeBlurb}
                    </p>
                  )}
                  <p className="text-xs text-slate-400 mt-0.5" data-testid="store-product-count">
                    {filteredProducts.length} offering{filteredProducts.length !== 1 ? "s" : ""}
                  </p>
                </div>

                {/* Search + Sort row */}
                <div className="flex items-center gap-2 shrink-0">
                  {/* Search pill */}
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400 pointer-events-none" />
                    <input
                      type="text"
                      value={searchQuery}
                      onChange={e => setSearchQuery(e.target.value)}
                      placeholder="Search products…"
                      className="h-9 w-48 rounded-full border border-slate-200 bg-white pl-8 pr-8 text-sm outline-none focus:border-slate-400 focus:ring-1 focus:ring-slate-400/20 placeholder:text-slate-400 transition-all"
                      data-testid="store-search-input"
                    />
                    {searchQuery && (
                      <button
                        type="button"
                        onClick={() => setSearchQuery("")}
                        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-300 hover:text-slate-500 transition-colors"
                        aria-label="Clear search"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>

                  {/* Sort dropdown */}
                  <Select value={sortBy} onValueChange={val => setSortBy(val as SortOption)}>
                    <SelectTrigger
                      className="h-9 min-w-[175px] bg-white border-slate-200 hover:bg-slate-50 text-slate-700 text-sm"
                      data-testid="sort-select"
                    >
                      <span className="flex items-center gap-1.5">
                        <ArrowUpDown className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                        <SelectValue />
                      </span>
                    </SelectTrigger>
                    <SelectContent>
                      {(Object.keys(SORT_LABELS) as SortOption[]).map(key => (
                        <SelectItem key={key} value={key} className="text-sm">
                          {SORT_LABELS[key]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Active filter pills */}
              {activeFilterPills.length > 0 && (
                <div className="flex flex-wrap gap-1.5" data-testid="active-filter-pills">
                  {activeFilterPills.map((pill, i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={pill.onRemove}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200 hover:bg-slate-200 transition-colors"
                    >
                      {pill.label}
                      <X className="h-3 w-3" />
                    </button>
                  ))}
                </div>
              )}
            </div>

            {filteredProducts.length === 0 ? (
              <p className="text-slate-400 text-sm py-12 text-center">No products match the selected filters.</p>
            ) : (
              <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3" data-testid="products-grid">
                {filteredProducts.map((product, i) => (
                  <OfferingCard key={product.id} product={product} index={i} />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}

// ── Shared small component for filter option buttons ─────────────────────────
function FilterOptionButton({
  label, count, active, onClick,
}: {
  label: string;
  count?: number;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-all duration-150 text-left group ${
        active
          ? "bg-slate-100 font-semibold text-slate-900"
          : "text-slate-500 hover:bg-slate-50 hover:text-slate-900"
      }`}
    >
      <span className="flex items-center gap-2 min-w-0">
        {active && <span className="w-1 h-3.5 rounded-full shrink-0" style={{ backgroundColor: "var(--aa-primary)" }} />}
        <span className="truncate">{label}</span>
      </span>
      {count !== undefined && (
        <span className={`text-[11px] font-mono px-1.5 py-0.5 rounded shrink-0 ml-2 ${
          active
            ? "bg-white text-slate-700 shadow-sm"
            : "bg-slate-100 text-slate-400 group-hover:bg-white group-hover:text-slate-700"
        }`}>
          {count}
        </span>
      )}
    </button>
  );
}
