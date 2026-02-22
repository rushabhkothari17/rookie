import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { useWebsite } from "@/contexts/WebsiteContext";

export default function GoCardlessCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<"processing" | "success" | "error">("processing");
  const ws = useWebsite();

  useEffect(() => {
    const completeFlow = async () => {
      const redirectFlowId = searchParams.get("redirect_flow_id");
      const orderId = searchParams.get("order_id");
      const subscriptionId = searchParams.get("subscription_id");
      const sessionToken = searchParams.get("session_token");

      if (!redirectFlowId) {
        setStatus("error");
        setLoading(false);
        toast.error("Invalid redirect flow");
        return;
      }

      try {
        await api.post("/gocardless/complete-redirect", {
          redirect_flow_id: redirectFlowId,
          session_token: sessionToken,
          order_id: orderId,
          subscription_id: subscriptionId,
        });

        setStatus("success");
        toast.success("Direct Debit setup completed and payment initiated!");
        
        setTimeout(() => {
          if (orderId) {
            navigate("/checkout/success");
          } else {
            navigate("/portal");
          }
        }, 2000);
      } catch (error: any) {
        setStatus("error");
        
        let errorMsg = "Failed to complete Direct Debit setup. Please try again.";
        
        if (error.response?.data) {
          const data = error.response.data;
          if (typeof data.detail === 'string') {
            errorMsg = data.detail;
          } else if (Array.isArray(data.detail)) {
            const messages = data.detail.map((err: any) => {
              if (typeof err === 'string') return err;
              if (err.msg) return `${err.loc?.join('.') || 'Field'}: ${err.msg}`;
              return 'Validation error';
            });
            errorMsg = messages.join('; ');
          } else if (typeof data.detail === 'object') {
            errorMsg = data.detail.message || 'GoCardless setup failed';
          }
        }
        
        toast.error(errorMsg);
      } finally {
        setLoading(false);
      }
    };

    completeFlow();
  }, [searchParams, navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-slate-50 to-white p-4">
      <div className="max-w-md w-full bg-white rounded-xl shadow-lg p-8 text-center">
        {loading && (
          <>
            <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-slate-900 mx-auto mb-4"></div>
            <h2 className="text-xl font-semibold text-slate-900 mb-2">{ws.gocardless_processing_title}</h2>
            <p className="text-sm text-slate-600">{ws.gocardless_processing_subtitle}</p>
          </>
        )}

        {status === "success" && !loading && (
          <>
            <div className="text-green-600 text-5xl mb-4">✓</div>
            <h2 className="text-xl font-semibold text-slate-900 mb-2">{ws.gocardless_success_title}</h2>
            <p className="text-sm text-slate-600 mb-4">{ws.gocardless_success_message}</p>
            <p className="text-xs text-slate-500">Redirecting to confirmation page...</p>
          </>
        )}

        {status === "error" && !loading && (
          <>
            <div className="text-red-600 text-5xl mb-4">✗</div>
            <h2 className="text-xl font-semibold text-slate-900 mb-2">{ws.gocardless_error_title}</h2>
            <p className="text-sm text-slate-600 mb-6">{ws.gocardless_error_message}</p>
            <Button onClick={() => navigate("/store")} className="w-full">{ws.gocardless_return_btn_text}</Button>
          </>
        )}
      </div>
    </div>
  );
}
