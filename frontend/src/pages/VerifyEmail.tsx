import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/contexts/AuthContext";
import { useWebsite } from "@/contexts/WebsiteContext";

export default function VerifyEmail() {
  const navigate = useNavigate();
  const { verifyEmail } = useAuth();
  const ws = useWebsite();
  const [email, setEmail] = useState(localStorage.getItem("aa_signup_email") || "");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    try {
      await verifyEmail(email, code);
      toast.success("Email verified. Please sign in.");
      navigate("/login");
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Verification failed");
    } finally {
      setLoading(false);
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
      </div>
    </div>
  );
}

export default function VerifyEmail() {
  const navigate = useNavigate();
  const { verifyEmail } = useAuth();
  const [email, setEmail] = useState(localStorage.getItem("aa_signup_email") || "");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    try {
      await verifyEmail(email, code);
      toast.success("Email verified. Please sign in.");
      navigate("/login");
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Verification failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid place-items-center bg-slate-50 grid-rhythm" data-testid="verify-page">
      <div className="glass-card w-full max-w-md rounded-2xl p-8">
        <div className="space-y-2">
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Verify email</p>
          <h1 className="text-3xl font-semibold text-slate-900">Enter your code</h1>
          <p className="text-sm text-slate-500">We sent a 6-digit code to your email (mocked in this MVP).</p>
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
      </div>
    </div>
  );
}
