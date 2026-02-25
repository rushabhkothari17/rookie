import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import axios from "axios";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { AlertCircle, CheckCircle, ArrowLeft, ChevronLeft } from "lucide-react";
import { applyPartnerBranding } from "@/contexts/WebsiteContext";

const API = process.env.REACT_APP_BACKEND_URL;

export default function ForgotPassword() {
  const navigate = useNavigate();

  const [partnerCode] = useState<string>(() => localStorage.getItem("aa_partner_code") || "");
  const [partnerName, setPartnerName] = useState("");
  const [partnerLogoUrl, setPartnerLogoUrl] = useState("");
  const [partnerPrimaryColor, setPartnerPrimaryColor] = useState("");

  const [email, setEmail] = useState("");
  const [step, setStep] = useState<"request" | "reset" | "done">("request");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  // Require partner code — redirect to login if missing
  useEffect(() => {
    if (!partnerCode) {
      navigate("/login");
      return;
    }
    applyPartnerBranding(partnerCode).then(s => {
      setPartnerName(s.store_name || "");
      setPartnerLogoUrl(s.logo_url || "");
      setPartnerPrimaryColor(s.primary_color || "");
    }).catch(() => {});
  }, [partnerCode, navigate]);

  async function handleRequestCode(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await axios.post(`${API}/api/auth/forgot-password`, {
        email: email.trim().toLowerCase(),
        partner_code: partnerCode.trim(),
      });
      setStep("reset");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  async function handleResetPassword(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (newPassword !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    setLoading(true);
    try {
      await axios.post(`${API}/api/auth/reset-password`, {
        email: email.trim().toLowerCase(),
        partner_code: partnerCode.trim(),
        code: code.trim(),
        new_password: newPassword,
      });
      setStep("done");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to reset password. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  const primaryColor = partnerPrimaryColor || "var(--aa-primary)";

  return (
    <div className="min-h-screen bg-white flex items-center justify-center px-6 py-12" data-testid="forgot-password-page">
      <div className="w-full max-w-sm space-y-8">

        {/* Partner brand header */}
        <div className="flex items-center gap-2.5">
          {partnerLogoUrl ? (
            <img src={partnerLogoUrl} alt={partnerName} className="h-7 object-contain" />
          ) : (
            <div
              className="h-7 w-7 rounded-lg flex items-center justify-center text-white text-xs font-semibold"
              style={{ backgroundColor: primaryColor }}
            >
              {(partnerName || partnerCode)[0]?.toUpperCase() || "P"}
            </div>
          )}
          {partnerName && <span className="text-sm text-slate-500">{partnerName}</span>}
        </div>

        <div className="space-y-1">
          <h1 className="text-2xl font-semibold text-slate-900 tracking-tight">
            {step === "done" ? "Password reset" : "Forgot password?"}
          </h1>
          <p className="text-sm text-slate-400">
            {step === "request" && "We'll send a reset code to your email."}
            {step === "reset" && "Check your email for the 6-digit code."}
            {step === "done" && "Your password has been updated."}
          </p>
        </div>

        {error && (
          <p className="flex items-center gap-1.5 text-xs text-red-500" data-testid="forgot-password-error">
            <AlertCircle className="h-3 w-3" /> {error}
          </p>
        )}

        {/* Step 1: Request code */}
        {step === "request" && (
          <form
            onSubmit={handleRequestCode}
            className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-4"
            data-testid="forgot-password-form"
          >
            <div className="space-y-2">
              <Label htmlFor="email">Email address</Label>
              <Input
                id="email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
                data-testid="forgot-email-input"
              />
            </div>
            <Button
              type="submit"
              className="w-full text-white"
              style={{ backgroundColor: primaryColor }}
              disabled={loading}
              data-testid="forgot-password-submit"
            >
              {loading ? "Sending…" : "Send Reset Code"}
            </Button>
            <div className="text-center">
              <Link
                to="/login"
                className="text-sm text-slate-500 hover:text-slate-700 inline-flex items-center gap-1"
                data-testid="back-to-login-link"
              >
                <ArrowLeft className="h-3 w-3" /> Back to sign in
              </Link>
            </div>
          </form>
        )}

        {/* Step 2: Enter code + new password */}
        {step === "reset" && (
          <form
            onSubmit={handleResetPassword}
            className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-4"
            data-testid="reset-password-form"
          >
            <Alert className="border-blue-200 bg-blue-50">
              <AlertDescription className="text-blue-800 text-sm">
                A reset code was sent to <strong>{email}</strong>. Enter it below along with your new password.
              </AlertDescription>
            </Alert>
            <div className="space-y-2">
              <Label htmlFor="code">Reset Code</Label>
              <Input
                id="code"
                placeholder="6-digit code"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                required
                maxLength={6}
                className="font-mono tracking-widest text-center text-lg"
                data-testid="reset-code-input"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="new-password">New Password</Label>
              <Input
                id="new-password"
                type="password"
                placeholder="Min 10 chars, upper, lower, number, symbol"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                data-testid="new-password-input"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm-password">Confirm Password</Label>
              <Input
                id="confirm-password"
                type="password"
                placeholder="Re-enter new password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                data-testid="confirm-password-input"
              />
            </div>
            <Button
              type="submit"
              className="w-full text-white"
              style={{ backgroundColor: primaryColor }}
              disabled={loading}
              data-testid="reset-password-submit"
            >
              {loading ? "Resetting…" : "Reset Password"}
            </Button>
            <div className="text-center">
              <button
                type="button"
                onClick={() => { setStep("request"); setError(""); setCode(""); }}
                className="text-xs text-slate-400 hover:text-slate-600"
              >
                Didn't receive the code? Send again
              </button>
            </div>
          </form>
        )}

        {/* Step 3: Done */}
        {step === "done" && (
          <div
            className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-4 text-center"
            data-testid="reset-password-success"
          >
            <div className="flex justify-center">
              <CheckCircle className="h-12 w-12 text-green-500" />
            </div>
            <p className="text-slate-600 text-sm">
              Your password has been reset. You can now sign in with your new password.
            </p>
            <Button
              className="w-full text-white"
              style={{ backgroundColor: primaryColor }}
              onClick={() => navigate("/login")}
              data-testid="goto-login-btn"
            >
              Sign In
            </Button>
          </div>
        )}

        {/* Change partner footer */}
        {partnerCode && step !== "done" && (
          <div className="text-center">
            <Link
              to="/login"
              onClick={() => localStorage.removeItem("aa_partner_code")}
              className="inline-flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600 transition-colors"
              data-testid="change-partner-from-forgot"
            >
              <ChevronLeft size={12} />
              Wrong partner? ({partnerCode})
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
