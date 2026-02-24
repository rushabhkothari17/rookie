import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import axios from "axios";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle, CheckCircle, ArrowLeft } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

export default function ForgotPassword() {
  const navigate = useNavigate();

  // Step 1: request code
  const [partnerCode, setPartnerCode] = useState("");
  const [email, setEmail] = useState("");
  const [step, setStep] = useState<"request" | "reset" | "done">("request");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Step 2: enter code + new password
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

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

  return (
    <div className="min-h-screen aa-bg flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm space-y-6">
        {/* Brand */}
        <div className="text-center space-y-2">
          <div className="flex justify-center">
            <div
              className="h-12 w-12 rounded-xl flex items-center justify-center text-white text-xl font-bold"
              style={{ backgroundColor: "var(--aa-primary)" }}
            >
              A
            </div>
          </div>
          <h1 className="text-2xl font-bold text-slate-900">
            {step === "done" ? "Password reset!" : "Forgot password?"}
          </h1>
          <p className="text-sm text-slate-500">
            {step === "request" && "Enter your email and we'll send a reset code."}
            {step === "reset" && "Check your email for the 6-digit code."}
            {step === "done" && "Your password has been updated successfully."}
          </p>
        </div>

        {error && (
          <Alert variant="destructive" data-testid="forgot-password-error">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Step 1: Request code */}
        {step === "request" && (
          <form
            onSubmit={handleRequestCode}
            className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-4"
            data-testid="forgot-password-form"
          >
            <div className="space-y-2">
              <Label htmlFor="partner-code">Partner Code</Label>
              <Input
                id="partner-code"
                placeholder="e.g. automate-accounts"
                value={partnerCode}
                onChange={(e) => setPartnerCode(e.target.value)}
                required
                data-testid="forgot-partner-code-input"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email address</Label>
              <Input
                id="email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                data-testid="forgot-email-input"
              />
            </div>
            <Button
              type="submit"
              className="w-full"
              disabled={loading}
              data-testid="forgot-password-submit"
            >
              {loading ? "Sending…" : "Send Reset Code"}
            </Button>
            <div className="text-center">
              <Link
                to="/login"
                className="text-sm text-slate-500 hover:text-slate-700 inline-flex items-center gap-1"
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
              className="w-full"
              disabled={loading}
              data-testid="reset-password-submit"
            >
              {loading ? "Resetting…" : "Reset Password"}
            </Button>
            <div className="text-center space-y-1">
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
            <Button className="w-full" onClick={() => navigate("/login")} data-testid="goto-login-btn">
              Sign In
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
