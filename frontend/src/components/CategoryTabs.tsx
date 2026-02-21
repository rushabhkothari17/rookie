import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { CATEGORY_ORDER, displayCategory, slugFromCategory } from "@/lib/categories";
import api from "@/lib/api";

export default function CategoryTabs({
  activeCategory,
}: {
  activeCategory?: string | null;
}) {
  const [categories, setCategories] = useState<string[]>(CATEGORY_ORDER);
  const activeLabel = displayCategory(activeCategory || categories[0] || CATEGORY_ORDER[0]);

  useEffect(() => {
    api.get("/categories").then((res) => {
      const apiCats: string[] = res.data.categories || [];
      if (apiCats.length === 0) return;
      // CATEGORY_ORDER items first (that exist in products), then any new custom ones
      const ordered = CATEGORY_ORDER.filter((c) => apiCats.includes(c));
      const newOnes = apiCats.filter((c) => !CATEGORY_ORDER.includes(c));
      setCategories([...ordered, ...newOnes]);
    }).catch(() => {});
  }, []);

  return (
    <div
      className="aa-no-scrollbar flex w-full gap-3 overflow-x-auto py-4"
      data-testid="category-tabs"
    >
      {categories.map((category) => {
        const label = displayCategory(category);
        const isActive = label === activeLabel;
        return (
          <Link
            key={category}
            to={`/store?category=${slugFromCategory(category)}`}
            className={`whitespace-nowrap rounded-full px-5 py-2 text-sm font-medium transition-colors ${
              isActive
                ? "bg-slate-900 text-white shadow-sm"
                : "bg-white/80 text-slate-600 ring-1 ring-slate-200 hover:text-slate-900"
            }`}
            data-testid={`category-tab-${slugFromCategory(category)}`}
          >
            {label}
          </Link>
        );
      })}
    </div>
  );
}
