import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { displayCategory, slugFromCategory } from "@/lib/categories";
import api from "@/lib/api";

export default function CategoryTabs({
  activeCategory,
}: {
  activeCategory?: string | null;
}) {
  const [categories, setCategories] = useState<string[]>([]);
  const activeLabel = displayCategory(activeCategory || categories[0] || "");

  useEffect(() => {
    api.get("/categories").then((res) => {
      // Use the order returned by the API (admin-defined order)
      const apiCats: string[] = res.data.categories || [];
      setCategories(apiCats);
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
                : "bg-white text-slate-600 ring-1 ring-slate-200 hover:text-slate-900 hover:ring-slate-300"
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
