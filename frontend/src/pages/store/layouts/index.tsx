/**
 * Product Detail Page Layouts
 * 
 * Layout types:
 * - standard (ClassicLayout): Two-column - info left, price right
 * - quick_buy (QuickBuyLayout): Compact, price-first, fast checkout
 * - wizard (WizardLayout): Guided step-by-step form with progress bar
 * - application (ApplicationLayout): Sidebar nav, sections, enterprise feel
 * - showcase (ShowcaseLayout): Hero section, live calculator
 */
import { lazy, Suspense } from "react";
import type { LayoutProps } from "./types";

// Lazy load layouts for better code splitting
const ClassicLayout = lazy(() => import("./ClassicLayout"));
const QuickBuyLayout = lazy(() => import("./QuickBuyLayout"));
const WizardLayout = lazy(() => import("./WizardLayout")); 
const ApplicationLayout = lazy(() => import("./ApplicationLayout"));
const ShowcaseLayout = lazy(() => import("./ShowcaseLayout"));

const LAYOUT_MAP: Record<string, React.LazyExoticComponent<React.ComponentType<LayoutProps>>> = {
  standard: ClassicLayout,
  quick_buy: QuickBuyLayout,
  wizard: WizardLayout,
  application: ApplicationLayout,
  showcase: ShowcaseLayout,
};

function LayoutLoadingFallback() {
  return (
    <div className="flex items-center justify-center py-20" data-testid="layout-loading">
      <div className="animate-pulse text-slate-400">Loading...</div>
    </div>
  );
}

export function ProductLayout({ layoutType, ...props }: LayoutProps & { layoutType: string }) {
  const LayoutComponent = LAYOUT_MAP[layoutType] || ClassicLayout;
  
  return (
    <Suspense fallback={<LayoutLoadingFallback />}>
      <LayoutComponent {...props} />
    </Suspense>
  );
}

export { ClassicLayout };
export * from "./types";
export * from "./utils";
