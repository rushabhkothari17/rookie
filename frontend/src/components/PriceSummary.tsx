import { Separator } from "@/components/ui/separator";

export default function PriceSummary({
  subtotal,
  fee,
  total,
  currency,
}: {
  subtotal: number;
  fee: number;
  total: number;
  currency?: string;
}) {
  const cur = currency || "USD";
  const fmt = (n: number) =>
    new Intl.NumberFormat("en-US", { style: "currency", currency: cur, minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n);

  return (
    <div
      className="space-y-3 rounded-xl border border-slate-200 bg-white p-6"
      data-testid="price-summary"
    >
      <div className="flex items-center justify-between text-sm text-slate-600">
        <span data-testid="price-summary-subtotal-label">Subtotal</span>
        <span data-testid="price-summary-subtotal">{fmt(subtotal)}</span>
      </div>
      <div className="flex items-center justify-between text-sm text-slate-600">
        <span data-testid="price-summary-fee-label">Processing fee (5%)</span>
        <span data-testid="price-summary-fee">{fmt(fee)}</span>
      </div>
      <Separator />
      <div className="flex items-center justify-between text-base font-semibold text-slate-900">
        <span data-testid="price-summary-total-label">Total</span>
        <span data-testid="price-summary-total">{fmt(total)}</span>
      </div>
    </div>
  );
}
