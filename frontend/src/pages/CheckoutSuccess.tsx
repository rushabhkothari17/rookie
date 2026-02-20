import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { toast } from "@/components/ui/sonner";
import api from "@/lib/api";

export default function CheckoutSuccess() {
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get("session_id");
  const [status, setStatus] = useState("pending");
  const [paymentStatus, setPaymentStatus] = useState("pending");

  const pollStatus = async () => {
    if (!sessionId) return;
    const response = await api.get(`/checkout/status/${sessionId}`);
    setStatus(response.data.status);
    setPaymentStatus(response.data.payment_status);
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
      </div>
      <Link to="/portal" className="text-sm text-blue-600" data-testid="checkout-portal-link">
        Go to customer portal
      </Link>
    </div>
  );
}
