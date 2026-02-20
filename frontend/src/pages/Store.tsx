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
      const categorySet = new Set(
        productsData.map((p: any) => displayCategory(p.category)),
      );
      const categoryList = Array.from(categorySet);
      const ordered = CATEGORY_ORDER.filter((category) =>
        categoryList.includes(category),
      );
      const finalList = ordered.length ? ordered : categoryList;
      setCategories(finalList);
      setActiveCategory(
        categoryFromSlug(searchParams.get("category"), finalList),
      );
    };
    load();
  }, [searchParams]);

  const filteredProducts = useMemo(() => {
    if (!activeCategory) return products;
    return products.filter(
      (product) => displayCategory(product.category) === activeCategory,
    );
  }, [products, activeCategory]);

  return (
    <AppShell activeCategory={activeCategory}>
      <div className="space-y-10" data-testid="store-page">
      <section
        className="rounded-3xl bg-white/80 p-10 shadow-[0_30px_70px_rgba(15,23,42,0.08)] backdrop-blur"
        data-testid="store-hero"
      >

        <div className="space-y-4">
          <p className="text-xs uppercase tracking-[0.3em] text-slate-400">
            Automate Accounts Storefront
          </p>
          <h1 className="text-4xl font-semibold text-slate-900">
            Premium Zoho delivery, scoped and priced for clarity.
          </h1>
          <p className="text-base text-slate-600">
            Choose a service tier, configure the scope, and move to a kickoff-ready plan in minutes.
          </p>
        </div>
      </section>

      <section className="space-y-6" data-testid="category-section">
        <div
          className="flex flex-wrap items-end justify-between gap-4"
          data-testid="category-header"
        >
          <div>
            <div className="text-xs uppercase tracking-[0.25em] text-slate-400">
              Category
            </div>
            <h2 className="text-3xl font-semibold text-slate-900">{activeCategory}</h2>
            <p className="text-sm text-slate-500" data-testid="category-blurb">
              {CATEGORY_BLURBS[activeCategory || ""] ||
                "Curated offerings designed for fast, measurable delivery."}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-sm text-slate-500" data-testid="store-product-count">
              {filteredProducts.length} offerings
            </div>
            <button
              className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm text-slate-600"
              data-testid="store-compare-button"
            >
              Compare
            </button>
          </div>
        </div>
        <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
          {filteredProducts.map((product) => (
            <OfferingCard key={product.id} product={product} />
          ))}
        </div>
      </section>
    </div>
    </AppShell>
  );
}
