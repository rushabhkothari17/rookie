import { Link, useSearchParams } from "react-router-dom";
import { CheckCircle, ArrowRight } from "lucide-react";
import { useWebsite } from "@/contexts/WebsiteContext";

export default function BankTransferSuccess() {
  const [searchParams] = useSearchParams();
  const orderNumber = searchParams.get("order");
  const ws = useWebsite();

  return (
    <div className="space-y-6" data-testid="bank-transfer-success">
      <div className="rounded-xl border border-slate-200 bg-white p-8 text-center">
        <div className="mb-4 flex justify-center">
          <div className="rounded-full bg-green-100 p-3">
            <CheckCircle className="h-8 w-8 text-green-600" />
          </div>
        </div>
        <h1 className="text-2xl font-semibold text-slate-900" data-testid="bank-transfer-title">
          {ws.bank_success_title}
        </h1>
        {orderNumber && (
          <p className="mt-2 text-sm text-slate-500" data-testid="bank-transfer-order-number">
            Order #{orderNumber}
          </p>
        )}
        <p className="mt-4 text-sm text-slate-600" data-testid="bank-transfer-message">
          {ws.bank_success_message}
        </p>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-6" data-testid="bank-transfer-instructions">
        <h2 className="text-sm font-semibold text-slate-900">{ws.bank_instructions_title}</h2>
        <ul className="mt-3 space-y-2 text-xs text-slate-600">
          {ws.bank_instruction_1 && (
            <li className="flex items-start gap-2" data-testid="bank-instruction-1">
              <span className="mt-0.5 h-1.5 w-1.5 rounded-full bg-slate-400 shrink-0" />
              <span>{ws.bank_instruction_1}</span>
            </li>
          )}
          {ws.bank_instruction_2 && (
            <li className="flex items-start gap-2" data-testid="bank-instruction-2">
              <span className="mt-0.5 h-1.5 w-1.5 rounded-full bg-slate-400 shrink-0" />
              <span>{ws.bank_instruction_2}</span>
            </li>
          )}
          {ws.bank_instruction_3 && (
            <li className="flex items-start gap-2" data-testid="bank-instruction-3">
              <span className="mt-0.5 h-1.5 w-1.5 rounded-full bg-slate-400 shrink-0" />
              <span>{ws.bank_instruction_3}</span>
            </li>
          )}
        </ul>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-6" data-testid="bank-transfer-next-steps">
        <h2 className="text-sm font-semibold text-slate-900">{ws.bank_next_steps_title}</h2>
        <ul className="mt-3 space-y-2 text-xs text-slate-600">
          {ws.bank_next_step_1 && <li data-testid="bank-next-step-1">{ws.bank_next_step_1}</li>}
          {ws.bank_next_step_2 && <li data-testid="bank-next-step-2">{ws.bank_next_step_2}</li>}
          {ws.bank_next_step_3 && <li data-testid="bank-next-step-3">{ws.bank_next_step_3}</li>}
        </ul>
      </div>

      <Link
        to="/portal"
        className="inline-flex items-center gap-2 text-sm font-medium text-blue-600 hover:text-blue-700 transition-colors"
        data-testid="bank-transfer-portal-link"
      >
        {ws.checkout_portal_link_text}
        <ArrowRight className="h-4 w-4" />
      </Link>
    </div>
  );
}
