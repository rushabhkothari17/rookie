import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import api from "@/lib/api";
import AppShell from "@/components/AppShell";
import OfferingCard from "@/components/OfferingCard";
import { CATEGORY_ORDER, categoryFromSlug, displayCategory } from "@/lib/categories";

const CATEGORY_BLURBS: Record<string, string> = {
  "Zoho Express Setup": "Fast-track your Zoho setup with expert-led implementation.",
  "Audit & Optimize": "Identify friction, optimize usage, and unlock measurable gains.",
  "Build & Automate": "Flexible delivery packs for automation builds and iterations.",
  "Accounting on Zoho": "Monthly finance operations tailored to your transaction volume.",
  "Ongoing Plans": "Retainers that keep support and delivery moving predictably.",
  Migrations: "Structured migrations with clear pricing and next steps.",
};


export default function Store() {
  const [searchParams] = useSearchParams();
  const [products, setProducts] = useState<any[]>([]);
  const [categories, setCategories] = useState<string[]>(CATEGORY_ORDER);
  const [activeCategory, setActiveCategory] = useState<string | null>(
    CATEGORY_ORDER[0],
  );

  useEffect(() => {
    const load = async () => {
      const response = await api.get("/products");
      const productsData = response.data.products || [];
      setProducts(productsData);
      const categorySet = new Set<string>(
        productsData.map((p: any) => p.category),
      );
      const list = Array.from(categorySet);
      setCategories(list);
      const categoryQuery = searchParams.get("category");
      setActiveCategory(categoryQuery || list[0]);
    };
    load();
  }, [searchParams]);

  const filteredProducts = useMemo(() => {
    if (!activeCategory) return products;
    return products.filter((product) => product.category === activeCategory);
  }, [products, activeCategory]);

  return (
    <div className="space-y-12" data-testid="store-page">
      <section
        className="relative overflow-hidden rounded-3xl border border-slate-200 bg-slate-900 px-10 py-14 text-white"
        data-testid="store-hero"
      >
        <div
          className="absolute inset-0 opacity-20"
          style={{
            backgroundImage:
              "url(https://images.unsplash.com/photo-1642097972624-6ed84e4fe099?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA4Mzl8MHwxfHNlYXJjaHwzfHx0ZWNobm9sb2d5JTIwbmV0d29yayUyMGJhY2tncm91bmQlMjBibHVlJTIwd2hpdGV8ZW58MHx8fHwxNzcxNTU1Nzg1fDA&ixlib=rb-4.1.0&q=85)",
            backgroundSize: "cover",
            backgroundPosition: "center",
          }}
        />
        <div className="relative z-10 max-w-2xl space-y-4">
          <p className="text-xs uppercase tracking-[0.3em] text-blue-200">Automate Accounts Storefront</p>
          <h1 className="text-4xl font-semibold leading-tight">
            Choose the exact Zoho service you need — with pricing clarity from day one.
          </h1>
          <p className="text-sm text-blue-100">
            Every offering is structured for fast deployment, transparent scope, and measurable outcomes.
          </p>
        </div>
      </section>

      <section className="grid gap-8 lg:grid-cols-[240px_1fr]">
        <div className="space-y-4">
          <div className="text-xs uppercase tracking-[0.25em] text-slate-400">Categories</div>
          <div className="space-y-2">
            {categories.map((category) => (
              <button
                key={category}
                onClick={() => setActiveCategory(category)}
                className={`w-full rounded-md px-4 py-2 text-left text-sm transition-colors ${
                  activeCategory === category
                    ? "bg-slate-900 text-white"
                    : "bg-white text-slate-600 hover:bg-slate-100"
                }`}
                data-testid={`store-category-${category.replace(/\s+/g, "-").toLowerCase()}`}
              >
                {category}
              </button>
            ))}
          </div>
        </div>
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-semibold text-slate-900">{activeCategory}</h2>
            <div className="text-sm text-slate-500" data-testid="store-product-count">
              {filteredProducts.length} offerings
            </div>
          </div>
          <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
            {filteredProducts.map((product) => (
              <ProductCard key={product.id} product={product} />
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
