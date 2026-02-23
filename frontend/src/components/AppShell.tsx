import { ReactNode } from "react";
import TopNav from "@/components/TopNav";
import CategoryTabs from "@/components/CategoryTabs";
import AppFooter from "@/components/AppFooter";

export default function AppShell({
  activeCategory,
  children,
  showCategoryTabs = true,
}: {
  activeCategory?: string | null;
  children: ReactNode;
  showCategoryTabs?: boolean;
}) {
  return (
    <div className="min-h-screen aa-bg flex flex-col" data-testid="app-shell">
      <TopNav />
      {showCategoryTabs && (
        <div
          className="sticky top-[72px] z-30 border-b border-slate-200/60 bg-white/80 backdrop-blur"
          data-testid="category-tabs-wrapper"
        >
          <div className="aa-container">
            <CategoryTabs activeCategory={activeCategory} />
          </div>
        </div>
      )}
      <main className="aa-container py-10 flex-1" data-testid="app-shell-main">
        {children}
      </main>
      <AppFooter />
    </div>
  );
}
