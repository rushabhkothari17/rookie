import { Separator } from "@/components/ui/separator";

export default function PriceSummary({
  subtotal,
  fee,
  total,
}: {
  subtotal: number;
  fee: number;
  total: number;
}) {
  return (
    <div
      className="space-y-3 rounded-xl border border-slate-200 bg-white p-6"
      data-testid="price-summary"
    >
      <div className="flex items-center justify-between text-sm text-slate-600">
        <span data-testid="price-summary-subtotal-label">Subtotal</span>
        <span data-testid="price-summary-subtotal">${subtotal.toFixed(2)}</span>
      </div>
      <div className="flex items-center justify-between text-sm text-slate-600">
        <span data-testid="price-summary-fee-label">Processing fee (5%)</span>
        <span data-testid="price-summary-fee">${fee.toFixed(2)}</span>
      </div>
      <Separator />
      <div className="flex items-center justify-between text-base font-semibold text-slate-900">
        <span data-testid="price-summary-total-label">Total</span>
        <span data-testid="price-summary-total">${total.toFixed(2)}</span>
      </div>
    </div>
  );
}
