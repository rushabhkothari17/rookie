import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { toast } from "@/components/ui/sonner";
import api from "@/lib/api";
import { useWebsite } from "@/contexts/WebsiteContext";

export default function CheckoutSuccess() {
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get("session_id");
  const [status, setStatus] = useState("pending");
  const [paymentStatus, setPaymentStatus] = useState("pending");
  const [orderNumber, setOrderNumber] = useState<string | null>(null);
  const ws = useWebsite();

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
    if (paymentStatus === "paid") return ws.checkout_success_paid_msg;
    if (status === "expired") return ws.checkout_success_expired_msg;
    return ws.checkout_success_pending_msg;
  }, [status, paymentStatus, ws]);

  return (
    <div className="space-y-6" data-testid="checkout-success">
      <h1 className="text-2xl font-semibold text-slate-900">{ws.checkout_success_title}</h1>
      <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-600" data-testid="checkout-status-message">
        {displayMessage}
        {orderNumber && (
          <div className="mt-3 text-xs text-slate-500" data-testid="checkout-order-number">
            Order number: {orderNumber}
          </div>
        )}
      </div>
      <div className="rounded-xl border border-slate-200 bg-white p-6" data-testid="checkout-next-steps">
        <div className="text-sm font-semibold text-slate-900">{ws.checkout_success_next_steps_title}</div>
        <ul className="mt-2 text-xs text-slate-500 space-y-1">
          {ws.checkout_success_step_1 && <li data-testid="checkout-next-steps-1">{ws.checkout_success_step_1}</li>}
          {ws.checkout_success_step_2 && <li data-testid="checkout-next-steps-2">{ws.checkout_success_step_2}</li>}
          {ws.checkout_success_step_3 && <li data-testid="checkout-next-steps-3">{ws.checkout_success_step_3}</li>}
        </ul>
      </div>
      <Link to="/portal" className="text-sm text-blue-600" data-testid="checkout-portal-link">
        {ws.checkout_portal_link_text}
      </Link>
    </div>
  );
}
