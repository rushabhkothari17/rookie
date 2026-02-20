import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { toast } from "@/components/ui/sonner";
import api from "@/lib/api";

export default function CheckoutSuccess() {
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get("session_id");
  const [status, setStatus] = useState("pending");
  const [paymentStatus, setPaymentStatus] = useState("pending");
  const [orderNumber, setOrderNumber] = useState<string | null>(null);

  const pollStatus = async () => {
    if (!sessionId) return;
    const response = await api.get(`/checkout/status/${sessionId}`);
    setStatus(response.data.status);
    setPaymentStatus(response.data.payment_status);
    setOrderNumber(response.data.metadata?.order_number || null);
    if (response.data.payment_status === "paid") {
      toast.success("Payment confirmed");
    }
  };

  useEffect(() => {
    pollStatus();
    const interval = setInterval(pollStatus, 2500);
    return () => clearInterval(interval);
  }, [sessionId]);

  const displayMessage = useMemo(() => {
    if (paymentStatus === "paid") return "Payment successful.";
    if (status === "expired") return "Session expired.";
    return "Checking payment status...";
  }, [status, paymentStatus]);

  return (
    <div className="space-y-6" data-testid="checkout-success">
      <h1 className="text-2xl font-semibold text-slate-900">Checkout status</h1>
      <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-600" data-testid="checkout-status-message">
        {displayMessage}
        {orderNumber && (
          <div className="mt-3 text-xs text-slate-500" data-testid="checkout-order-number">
            Order number: {orderNumber}
          </div>
        )}
      </div>
      <div className="rounded-xl border border-slate-200 bg-white p-6" data-testid="checkout-next-steps">
        <div className="text-sm font-semibold text-slate-900">Next steps</div>
        <ul className="mt-2 text-xs text-slate-500 space-y-1">
          <li data-testid="checkout-next-steps-1">Well send a confirmation email with intake instructions.</li>
          <li data-testid="checkout-next-steps-2">A delivery lead will schedule your kickoff within 2 business days.</li>
          <li data-testid="checkout-next-steps-3">You can track status and invoices in the customer portal.</li>
        </ul>
      </div>
      <Link to="/portal" className="text-sm text-blue-600" data-testid="checkout-portal-link">
        Go to customer portal
      </Link>
    </div>
  );
}
