import { useState, useEffect } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import axios from "axios";
import { useAuth } from "@/contexts/AuthContext";
import { applyPartnerBranding } from "@/contexts/WebsiteContext";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { AlertCircle, ArrowRight, ChevronLeft } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

interface PartnerInfo {
  name: string;
  code: string;
  logo_url?: string;
  primary_color?: string;
  accent_color?: string;
}

export default function Login() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const redirect = searchParams.get("redirect") || "";
  const { login } = useAuth();

  const [step, setStep] = useState<"gateway" | "auth">("gateway");
  const [partnerInfo, setPartnerInfo] = useState<PartnerInfo | null>(null);

  const [codeInput, setCodeInput] = useState("");
  const [codeLoading, setCodeLoading] = useState(false);
  const [codeError, setCodeError] = useState("");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState("");

  useEffect(() => {
    const stored = localStorage.getItem("aa_partner_code");
    if (stored) validateAndProceed(stored, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function validateAndProceed(code: string, silent = false) {
    if (!silent) setCodeLoading(true);
    setCodeError("");
    try {
      const res = await axios.get(`${API}/api/tenant-info?code=${encodeURIComponent(code.trim().toLowerCase())}`);
      const tenant = res.data.tenant;
      const branding = await applyPartnerBranding(code.trim().toLowerCase());
      localStorage.setItem("aa_partner_code", code.trim().toLowerCase());
      setPartnerInfo({
        name: tenant.name,
        code: tenant.code,
        logo_url: branding.logo_url,
        primary_color: branding.primary_color,
        accent_color: branding.accent_color,
      });
      setStep("auth");
    } catch (err: any) {
      if (!silent) setCodeError(err.response?.data?.detail || "Partner code not found.");
      else localStorage.removeItem("aa_partner_code");
    } finally {
      if (!silent) setCodeLoading(false);
    }
  }

  function handleChangePartner() {
    localStorage.removeItem("aa_partner_code");
    setStep("gateway");
    setPartnerInfo(null);
    setCodeInput("");
    setCodeError("");
    setLoginError("");
    setEmail("");
    setPassword("");
  }

  const primary = partnerInfo?.primary_color || "#0f172a";
  const accent = partnerInfo?.accent_color || primary;

  // ── Gateway ──────────────────────────────────────────────────────────────────
  if (step === "gateway") {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center px-4" data-testid="auth-gateway">
        <div className="w-full max-w-[360px] space-y-6">

          <div className="space-y-1">
            <h1 className="text-2xl font-semibold text-slate-900 tracking-tight">Sign in</h1>
            <p className="text-sm text-slate-400">Enter your partner code to continue.</p>
          </div>

          <form
            onSubmit={async (e) => { e.preventDefault(); await validateAndProceed(codeInput); }}
            className="space-y-3"
            data-testid="partner-code-form"
          >
            <div className="space-y-1.5">
              <Label htmlFor="partner-code" className="text-sm text-slate-600">Partner Code</Label>
              <Input
                id="partner-code"
                placeholder="e.g. automate-accounts"
                value={codeInput}
                onChange={e => { setCodeInput(e.target.value); setCodeError(""); }}
                required
                autoFocus
                className={`h-11 transition-colors ${codeError ? "border-red-400 focus:border-red-400" : "border-slate-200 focus:border-slate-400"}`}
                data-testid="partner-code-input"
              />
              {codeError && (
                <p className="flex items-center gap-1.5 text-xs text-red-500" data-testid="gateway-error">
                  <AlertCircle size={12} /> {codeError}
                </p>
              )}
            </div>

            <Button
              type="submit"
              className="w-full h-11 bg-slate-900 hover:bg-slate-700 text-white transition-colors"
              disabled={codeLoading || !codeInput.trim()}
              data-testid="partner-code-submit"
            >
              {codeLoading ? (
                <span className="flex items-center gap-2">
                  <span className="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Verifying…
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  Continue <ArrowRight size={15} />
                </span>
              )}
            </Button>
          </form>

          <p className="text-center text-sm text-slate-400">
            <Link
              to="/signup?type=partner"
              className="text-slate-500 hover:text-slate-800 transition-colors underline-offset-4 hover:underline"
              data-testid="register-partner-link"
            >
              Register as a partner
            </Link>
          </p>

        </div>
      </div>
    );
  }

  // ── Auth screen ───────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-white flex" data-testid="login-page">

      {/* Left brand strip */}
      <div
        className="hidden lg:flex w-72 xl:w-80 shrink-0 flex-col justify-between p-10"
        style={{ backgroundColor: primary }}
      >
        <div className="flex items-center gap-2.5">
          {partnerInfo?.logo_url ? (
            <img src={partnerInfo.logo_url} alt={partnerInfo.name} className="h-7 object-contain" />
          ) : (
            <div className="h-8 w-8 rounded-lg bg-white/15 flex items-center justify-center text-white font-semibold text-sm">
              {partnerInfo?.name?.[0] || "P"}
            </div>
          )}
          <span className="text-white/90 font-medium text-sm">{partnerInfo?.name}</span>
        </div>
        <span className="text-white/20 text-xs">{partnerInfo?.code}</span>
      </div>

      {/* Right form */}
      <div className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-[360px] space-y-6">

          {/* Mobile partner label */}
          <div className="lg:hidden flex items-center gap-2 mb-2">
            {partnerInfo?.logo_url ? (
              <img src={partnerInfo.logo_url} alt={partnerInfo.name} className="h-6 object-contain" />
            ) : (
              <div
                className="h-6 w-6 rounded flex items-center justify-center text-white text-xs font-bold"
                style={{ backgroundColor: primary }}
              >
                {partnerInfo?.name?.[0]}
              </div>
            )}
            <span className="text-sm text-slate-500">{partnerInfo?.name}</span>
          </div>

          <div className="space-y-1">
            <h1 className="text-2xl font-semibold text-slate-900 tracking-tight">Welcome back</h1>
            <p className="text-sm text-slate-400">Sign in to your account.</p>
          </div>

          {loginError && (
            <p className="flex items-center gap-1.5 text-xs text-red-500" data-testid="login-error">
              <AlertCircle size={12} /> {loginError}
            </p>
          )}

          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setLoginError("");
              setLoginLoading(true);
              try {
                const result = await login(email, password, partnerInfo!.code);
                navigate(redirect || (result?.is_admin ? "/admin" : "/portal"));
              } catch (err: any) {
                setLoginError(err.message || "Invalid email or password.");
              } finally {
                setLoginLoading(false);
              }
            }}
            className="space-y-3"
            data-testid="login-form"
          >
            <div className="space-y-1.5">
              <Label htmlFor="email" className="text-sm text-slate-600">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                autoFocus
                className="h-11 border-slate-200 focus:border-slate-400 transition-colors"
                data-testid="login-email-input"
              />
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label htmlFor="password" className="text-sm text-slate-600">Password</Label>
                <Link
                  to={`/forgot-password${redirect ? `?redirect=${encodeURIComponent(redirect)}` : ""}`}
                  className="text-xs transition-colors hover:underline underline-offset-4"
                  style={{ color: accent }}
                  data-testid="forgot-password-link"
                >
                  Forgot password?
                </Link>
              </div>
              <Input
                id="password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                className="h-11 border-slate-200 focus:border-slate-400 transition-colors"
                data-testid="login-password-input"
              />
            </div>

            <Button
              type="submit"
              className="w-full h-11 text-white transition-opacity hover:opacity-90"
              style={{ backgroundColor: primary }}
              disabled={loginLoading}
              data-testid="login-submit-button"
            >
              {loginLoading ? (
                <span className="flex items-center gap-2">
                  <span className="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Signing in…
                </span>
              ) : "Sign In"}
            </Button>
          </form>

          <div className="space-y-3 pt-1">
            <p className="text-center text-sm text-slate-400">
              New here?{" "}
              <Link
                to={`/signup${redirect ? `?redirect=${encodeURIComponent(redirect)}` : ""}`}
                className="font-medium hover:underline underline-offset-4 transition-colors"
                style={{ color: accent }}
                data-testid="register-customer-link"
              >
                Create an account
              </Link>
            </p>

            <p className="text-center">
              <button
                onClick={handleChangePartner}
                className="text-xs text-slate-300 hover:text-slate-500 transition-colors inline-flex items-center gap-1"
                data-testid="change-partner-btn"
              >
                <ChevronLeft size={11} />
                {partnerInfo?.code}
              </button>
            </p>
          </div>

        </div>
      </div>
    </div>
  );
}
