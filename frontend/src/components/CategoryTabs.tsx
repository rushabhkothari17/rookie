import { Link } from "react-router-dom";
import { CATEGORY_ORDER, displayCategory, slugFromCategory } from "@/lib/categories";

export default function CategoryTabs({
  activeCategory,
}: {
  activeCategory?: string | null;
}) {
  const activeLabel = displayCategory(activeCategory || CATEGORY_ORDER[0]);

  return (
    <div
      className="aa-no-scrollbar flex w-full gap-3 overflow-x-auto py-4"
      data-testid="category-tabs"
    >
      {CATEGORY_ORDER.map((category) => {
        const isActive = displayCategory(category) === activeLabel;
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
            {displayCategory(category)}
          </Link>
        );
      })}
    </div>
  );
}
