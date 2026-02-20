import { Button } from "@/components/ui/button";

export default function StickyPurchaseSummary({
  pricing,
  cta,
  disabled,
  warning,
}: {
  pricing: { subtotal: number; fee: number; total: number };
  cta: { label: string; onClick?: () => void; href?: string };
  disabled?: boolean;
  warning?: string;
}) {
  return (
    <div
      className="sticky top-28 rounded-3xl bg-white/90 p-6 shadow-[0_24px_60px_rgba(15,23,42,0.12)] backdrop-blur"
      data-testid="sticky-purchase-summary"
    >
      <div className="space-y-3">
        <div className="flex items-center justify-between text-sm text-slate-500">
          <span data-testid="summary-subtotal-label">Subtotal</span>
          <span data-testid="summary-subtotal">${pricing.subtotal.toFixed(2)}</span>
        </div>
        <div className="flex items-center justify-between text-sm text-slate-500">
          <span data-testid="summary-fee-label">Processing fee (5%)</span>
          <span data-testid="summary-fee">${pricing.fee.toFixed(2)}</span>
        </div>
        <div className="flex items-center justify-between text-base font-semibold text-slate-900">
          <span data-testid="summary-total-label">Total</span>
          <span data-testid="summary-total">${pricing.total.toFixed(2)}</span>
        </div>
      </div>
      {cta.href ? (
        <Button
          asChild
          className="mt-6 w-full rounded-full bg-slate-900 text-white hover:bg-slate-800"
          data-testid="summary-cta-link"
        >
          <a href={cta.href} target="_blank" rel="noreferrer">
            {cta.label}
          </a>
        </Button>
      ) : (
        <Button
          className="mt-6 w-full rounded-full bg-slate-900 text-white hover:bg-slate-800"
          onClick={cta.onClick}
          disabled={disabled}
          data-testid="summary-cta-button"
        >
          {cta.label}
        </Button>
      )}
      <div className="mt-4 text-xs text-slate-500" data-testid="summary-currency-note">
        Currency confirmed at checkout.
      </div>
      <div className="mt-4 space-y-2 text-xs text-slate-500" data-testid="summary-policies">
        <div>No refunds for delivered services.</div>
        <div>Subscriptions cancel at end of billing month.</div>
        <div>Secure payment via Stripe.</div>
      </div>
    </div>
  );
}
