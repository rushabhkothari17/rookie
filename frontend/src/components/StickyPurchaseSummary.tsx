import { Button } from "@/components/ui/button";
import { ShieldCheck, RefreshCcw, CreditCard } from "lucide-react";

export default function StickyPurchaseSummary({
  pricing,
  cta,
  disabled,
  warning,
  currency,
  isRFQ,
}: {
  pricing: { subtotal: number; fee: number; total: number; line_items?: { label: string; amount: number }[] };
  cta: { label: string; onClick?: () => void; href?: string };
  disabled?: boolean;
  warning?: string;
  currency?: string;
  isRFQ?: boolean;
}) {
  const lineItems = pricing?.line_items;
  const hasBreakdown = !isRFQ && lineItems && lineItems.length > 1;
  const cur = currency || "USD";
  const fmtAmt = (n: number) =>
    new Intl.NumberFormat("en-US", { style: "currency", currency: cur, minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(n);

  return (
    <div
      className="sticky top-28 rounded-3xl border border-slate-100 bg-white p-6 shadow-[0_24px_60px_rgba(15,23,42,0.08)]"
      data-testid="sticky-purchase-summary"
    >
      {/* Price Display */}
      <div className="mb-1 text-xs font-semibold uppercase tracking-widest text-slate-400">
        {isRFQ ? "Pricing" : "Total"}
      </div>
      <div
        className="text-4xl font-bold tracking-tight text-slate-900"
        data-testid="summary-total"
      >
        {isRFQ ? <span className="text-2xl text-slate-400 font-medium">Price on request</span> : fmtAmt(pricing.total)}
      </div>

      {/* Price breakdown */}
      {hasBreakdown && (
        <div className="mt-3 space-y-1 border-t border-slate-100 pt-3" data-testid="summary-line-items">
          {lineItems!.map((item, i) => (
            <div key={i} className="flex justify-between text-xs text-slate-500">
              <span className="flex-1 truncate pr-2">{item.label}</span>
              <span className={`font-mono shrink-0 ${item.amount < 0 ? "text-green-600" : ""}`}>
                {item.amount >= 0 ? "+" : ""}{fmtAmt(item.amount)}
              </span>
            </div>
          ))}
        </div>
      )}

      {warning && (
        <div
          className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-700"
          data-testid="summary-warning"
        >
          {warning}
        </div>
      )}

      {cta.href ? (
        <Button
          asChild
          className="mt-6 w-full rounded-full bg-slate-900 text-white hover:bg-slate-800 active:bg-slate-700 h-12 text-sm font-semibold"
          data-testid="summary-cta-link"
        >
          <a href={cta.href} target="_blank" rel="noreferrer">
            {cta.label}
          </a>
        </Button>
      ) : (
        <Button
          className="mt-6 w-full rounded-full bg-slate-900 text-white hover:bg-slate-800 active:bg-slate-700 h-12 text-sm font-semibold"
          onClick={cta.onClick}
          disabled={disabled}
          data-testid="summary-cta-button"
        >
          {cta.label}
        </Button>
      )}

      <p className="mt-3 text-center text-xs text-slate-400" data-testid="summary-currency-note">
        {currency ? `All prices in ${currency}` : "Confirmed at checkout"}
      </p>

      <div className="mt-5 space-y-2.5 border-t border-slate-100 pt-5" data-testid="summary-policies">
        <div className="flex items-start gap-2.5 text-xs text-slate-500">
          <ShieldCheck size={14} className="mt-0.5 flex-shrink-0 text-slate-400" />
          <span>No refunds for delivered services.</span>
        </div>
        <div className="flex items-start gap-2.5 text-xs text-slate-500">
          <RefreshCcw size={14} className="mt-0.5 flex-shrink-0 text-slate-400" />
          <span>Subscriptions cancel at end of billing month.</span>
        </div>
        <div className="flex items-start gap-2.5 text-xs text-slate-500">
          <CreditCard size={14} className="mt-0.5 flex-shrink-0 text-slate-400" />
          <span>Secure payment via our payment provider.</span>
        </div>
      </div>
    </div>
  );
}
