import { ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { motion } from "framer-motion";
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
  const location = useLocation();
  return (
    <div className="min-h-screen flex flex-col" style={{ backgroundColor: "var(--aa-bg)" }} data-testid="app-shell">
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
        <motion.div
          key={location.pathname}
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
        >
          {children}
        </motion.div>
      </main>
      <AppFooter />
    </div>
  );
}
