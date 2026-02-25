import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/contexts/AuthContext";
import { useWebsite } from "@/contexts/WebsiteContext";
import api from "@/lib/api";

export default function VerifyEmail() {
  const navigate = useNavigate();
  const { verifyEmail } = useAuth();
  const ws = useWebsite();
  const partnerCode = localStorage.getItem("aa_partner_code") || "";
  const [email, setEmail] = useState(localStorage.getItem("aa_signup_email") || "");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    try {
      await verifyEmail(email, code, partnerCode || undefined);
      toast.success("Email verified. Please sign in.");
      navigate("/login");
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Verification failed");
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    if (!email) { toast.error("Please enter your email address first"); return; }
    setResending(true);
    try {
      const res = await api.post("/auth/resend-verification-email", { email, partner_code: partnerCode || undefined });
      const code = res.data?.verification_code;
      toast.success("Verification code resent.");
      if (code) setCode(code);
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to resend code");
    } finally {
      setResending(false);
    }
  };

  return (
    <div className="min-h-screen grid place-items-center bg-slate-50 grid-rhythm" data-testid="verify-page">
      <div className="glass-card w-full max-w-md rounded-2xl p-8">
        <div className="space-y-2">
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">{ws.verify_email_label}</p>
          <h1 className="text-3xl font-semibold text-slate-900">{ws.verify_email_title}</h1>
          <p className="text-sm text-slate-500">{ws.verify_email_subtitle}</p>
        </div>
        <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
          <div className="space-y-2">
            <label className="text-sm text-slate-600">Email</label>
            <Input value={email} onChange={(e) => setEmail(e.target.value)} data-testid="verify-email-input" required />
          </div>
          <div className="space-y-2">
            <label className="text-sm text-slate-600">Verification code</label>
            <Input value={code} onChange={(e) => setCode(e.target.value)} data-testid="verify-code-input" required />
          </div>
          <Button type="submit" className="w-full bg-slate-900 hover:bg-slate-800" disabled={loading} data-testid="verify-submit-button">
            {loading ? "Verifying..." : "Verify"}
          </Button>
        </form>
        <div className="mt-4 text-center">
          <button
            type="button"
            onClick={handleResend}
            disabled={resending}
            className="text-sm text-slate-500 hover:text-slate-800 underline transition-colors"
            data-testid="resend-verification-btn"
          >
            {resending ? "Sending..." : "Resend verification code"}
          </button>
        </div>
      </div>
    </div>
  );
}
