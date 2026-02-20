import { Link, useSearchParams } from "react-router-dom";
import { CheckCircle, ArrowRight } from "lucide-react";

export default function BankTransferSuccess() {
  const [searchParams] = useSearchParams();
  const orderNumber = searchParams.get("order");

  return (
    <div className="space-y-6" data-testid="bank-transfer-success">
      <div className="rounded-xl border border-slate-200 bg-white p-8 text-center">
        <div className="mb-4 flex justify-center">
          <div className="rounded-full bg-green-100 p-3">
            <CheckCircle className="h-8 w-8 text-green-600" />
          </div>
        </div>
        <h1 className="text-2xl font-semibold text-slate-900" data-testid="bank-transfer-title">
          Order Created
        </h1>
        {orderNumber && (
          <p className="mt-2 text-sm text-slate-500" data-testid="bank-transfer-order-number">
            Order #{orderNumber}
          </p>
        )}
        <p className="mt-4 text-sm text-slate-600" data-testid="bank-transfer-message">
          Your order has been created and is awaiting bank transfer payment.
        </p>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-6" data-testid="bank-transfer-instructions">
        <h2 className="text-sm font-semibold text-slate-900">Payment Instructions</h2>
        <ul className="mt-3 space-y-2 text-xs text-slate-600">
          <li className="flex items-start gap-2" data-testid="bank-instruction-1">
            <span className="mt-0.5 h-1.5 w-1.5 rounded-full bg-slate-400 shrink-0" />
            <span>You will receive an email with bank transfer details and instructions.</span>
          </li>
          <li className="flex items-start gap-2" data-testid="bank-instruction-2">
            <span className="mt-0.5 h-1.5 w-1.5 rounded-full bg-slate-400 shrink-0" />
            <span>Please complete the transfer within 7 business days.</span>
          </li>
          <li className="flex items-start gap-2" data-testid="bank-instruction-3">
            <span className="mt-0.5 h-1.5 w-1.5 rounded-full bg-slate-400 shrink-0" />
            <span>Once payment is confirmed, your order will be processed and a team member will reach out.</span>
          </li>
        </ul>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-6" data-testid="bank-transfer-next-steps">
        <h2 className="text-sm font-semibold text-slate-900">What Happens Next</h2>
        <ul className="mt-3 space-y-2 text-xs text-slate-600">
          <li data-testid="bank-next-step-1">1. Check your email for transfer instructions</li>
          <li data-testid="bank-next-step-2">2. Complete the bank transfer</li>
          <li data-testid="bank-next-step-3">3. We'll confirm receipt and begin processing your order</li>
        </ul>
      </div>

      <Link
        to="/portal"
        className="inline-flex items-center gap-2 text-sm font-medium text-blue-600 hover:text-blue-700 transition-colors"
        data-testid="bank-transfer-portal-link"
      >
        Go to customer portal
        <ArrowRight className="h-4 w-4" />
      </Link>
    </div>
  );
}
