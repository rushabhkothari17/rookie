import { useState, useEffect } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import axios from "axios";
import { useAuth } from "@/contexts/AuthContext";
import { applyPartnerBranding } from "@/contexts/WebsiteContext";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle, ArrowRight, ChevronLeft, Layers } from "lucide-react";

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

  // On mount — restore from localStorage if code already stored
  useEffect(() => {
    const stored = localStorage.getItem("aa_partner_code");
    if (stored) {
      validateAndProceed(stored, true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function validateAndProceed(code: string, silent = false) {
    if (!silent) setCodeLoading(true);
    setCodeError("");
    try {
      const res = await axios.get(
        `${API}/api/tenant-info?code=${encodeURIComponent(code.trim().toLowerCase())}`
      );
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
      if (!silent) {
        setCodeError(
          err.response?.data?.detail || "Partner code not found. Please check and try again."
        );
      } else {
        localStorage.removeItem("aa_partner_code");
      }
    } finally {
      if (!silent) setCodeLoading(false);
    }
  }

  async function handleCodeSubmit(e: React.FormEvent) {
    e.preventDefault();
    await validateAndProceed(codeInput);
  }

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoginError("");
    setLoginLoading(true);
    try {
      const result = await login(email, password, partnerInfo!.code);
      const dest = redirect || (result?.is_admin ? "/admin" : "/portal");
      navigate(dest);
    } catch (err: any) {
      setLoginError(err.message || "Invalid email or password.");
    } finally {
      setLoginLoading(false);
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
      <div
        className="min-h-screen bg-white flex"
        data-testid="auth-gateway"
      >
        {/* Left decorative panel */}
        <div className="hidden lg:flex w-[420px] xl:w-[480px] shrink-0 flex-col justify-between bg-slate-50 border-r border-slate-100 p-12">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-slate-900 flex items-center justify-center">
              <Layers size={16} className="text-white" />
            </div>
            <span className="font-semibold text-slate-800 text-sm tracking-tight">Partner Portal</span>
          </div>

          <div className="space-y-6">
            <div className="space-y-3">
              <h2 className="text-3xl font-bold text-slate-900 leading-tight">
                Access your<br />organization's portal
              </h2>
              <p className="text-slate-500 text-sm leading-relaxed">
                Enter the partner code provided by your service organization to sign in, create an account, or manage your subscriptions.
              </p>
            </div>
            <div className="space-y-3">
              {[
                "Manage subscriptions & invoices",
                "Track orders in real time",
                "Access exclusive resources",
              ].map(item => (
                <div key={item} className="flex items-center gap-2.5">
                  <div className="h-1.5 w-1.5 rounded-full bg-slate-400 shrink-0" />
                  <span className="text-sm text-slate-500">{item}</span>
                </div>
              ))}
            </div>
          </div>

          <p className="text-xs text-slate-400">Secure multi-tenant portal access</p>
        </div>

        {/* Right form panel */}
        <div className="flex-1 flex items-center justify-center px-6 py-12">
          <div className="w-full max-w-sm space-y-8">

            <div className="space-y-1.5">
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Welcome</h1>
              <p className="text-sm text-slate-500">Enter your partner code to get started.</p>
            </div>

            {codeError && (
              <Alert variant="destructive" data-testid="gateway-error">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{codeError}</AlertDescription>
              </Alert>
            )}

            <form onSubmit={handleCodeSubmit} className="space-y-4" data-testid="partner-code-form">
              <div className="space-y-2">
                <Label htmlFor="partner-code" className="text-sm font-medium text-slate-700">
                  Partner Code
                </Label>
                <Input
                  id="partner-code"
                  placeholder="e.g. automate-accounts"
                  value={codeInput}
                  onChange={e => setCodeInput(e.target.value)}
                  required
                  autoFocus
                  className="h-11 border-slate-200 focus:border-slate-400 bg-white"
                  data-testid="partner-code-input"
                />
                <p className="text-xs text-slate-400">Provided by your service organization</p>
              </div>

              <Button
                type="submit"
                className="w-full h-11 bg-slate-900 hover:bg-slate-800 text-white font-medium"
                disabled={codeLoading || !codeInput.trim()}
                data-testid="partner-code-submit"
              >
                {codeLoading ? (
                  <span className="flex items-center gap-2">
                    <span className="h-4 w-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                    Verifying…
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    Continue <ArrowRight size={16} />
                  </span>
                )}
              </Button>
            </form>

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-slate-100" />
              </div>
              <div className="relative flex justify-center">
                <span className="bg-white px-3 text-xs text-slate-400">or</span>
              </div>
            </div>

            <div className="text-center">
              <Link
                to="/signup?type=partner"
                className="text-sm text-slate-500 hover:text-slate-800 transition-colors underline-offset-4 hover:underline"
                data-testid="register-partner-link"
              >
                Register as a partner organization
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── Auth screen ───────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-white flex" data-testid="login-page">

      {/* Left partner branding panel */}
      <div
        className="hidden lg:flex w-[420px] xl:w-[480px] shrink-0 flex-col justify-between p-12"
        style={{ backgroundColor: primary }}
      >
        <div className="flex items-center gap-3">
          {partnerInfo?.logo_url ? (
            <img src={partnerInfo.logo_url} alt={partnerInfo.name} className="h-8 object-contain" />
          ) : (
            <div className="h-9 w-9 rounded-xl bg-white/15 flex items-center justify-center text-white font-bold text-base">
              {partnerInfo?.name?.[0] || "P"}
            </div>
          )}
          <span className="text-white font-semibold text-sm">{partnerInfo?.name}</span>
        </div>

        <div className="space-y-4">
          <h2 className="text-3xl font-bold text-white leading-snug">
            Welcome back
          </h2>
          <p className="text-white/60 text-sm leading-relaxed">
            Sign in to access your orders, invoices, and subscription management.
          </p>
        </div>

        <p className="text-white/30 text-xs">Powered by Partner Portal</p>
      </div>

      {/* Right form panel */}
      <div className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm space-y-8">

          {/* Mobile partner header */}
          <div className="lg:hidden flex items-center gap-3 mb-2">
            {partnerInfo?.logo_url ? (
              <img src={partnerInfo.logo_url} alt={partnerInfo.name} className="h-7 object-contain" />
            ) : (
              <div
                className="h-8 w-8 rounded-lg flex items-center justify-center text-white text-sm font-bold"
                style={{ backgroundColor: primary }}
              >
                {partnerInfo?.name?.[0] || "P"}
              </div>
            )}
            <span className="font-semibold text-slate-800 text-sm">{partnerInfo?.name}</span>
          </div>

          <div className="space-y-1.5">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Sign in</h1>
            <p className="text-sm text-slate-500">Enter your email and password to continue.</p>
          </div>

          {loginError && (
            <Alert variant="destructive" data-testid="login-error">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{loginError}</AlertDescription>
            </Alert>
          )}

          <form onSubmit={handleLogin} className="space-y-4" data-testid="login-form">
            <div className="space-y-2">
              <Label htmlFor="email" className="text-sm font-medium text-slate-700">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                autoFocus
                className="h-11 border-slate-200 focus:border-slate-400 bg-white"
                data-testid="login-email-input"
              />
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="password" className="text-sm font-medium text-slate-700">Password</Label>
                <Link
                  to={`/forgot-password${redirect ? `?redirect=${encodeURIComponent(redirect)}` : ""}`}
                  className="text-xs hover:underline underline-offset-4 transition-colors"
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
                className="h-11 border-slate-200 focus:border-slate-400 bg-white"
                data-testid="login-password-input"
              />
            </div>

            <Button
              type="submit"
              className="w-full h-11 text-white font-medium"
              style={{ backgroundColor: primary }}
              disabled={loginLoading}
              data-testid="login-submit-button"
            >
              {loginLoading ? (
                <span className="flex items-center gap-2">
                  <span className="h-4 w-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                  Signing in…
                </span>
              ) : "Sign In"}
            </Button>
          </form>

          <div className="space-y-3">
            <div className="text-center text-sm text-slate-500">
              New customer?{" "}
              <Link
                to={`/signup${redirect ? `?redirect=${encodeURIComponent(redirect)}` : ""}`}
                className="font-medium hover:underline underline-offset-4"
                style={{ color: accent }}
                data-testid="register-customer-link"
              >
                Create an account
              </Link>
            </div>

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-slate-100" />
              </div>
              <div className="relative flex justify-center">
                <span className="bg-white px-3 text-xs text-slate-400">organization</span>
              </div>
            </div>

            <div className="text-center">
              <button
                onClick={handleChangePartner}
                className="text-xs text-slate-400 hover:text-slate-600 transition-colors inline-flex items-center gap-1"
                data-testid="change-partner-btn"
              >
                <ChevronLeft size={12} />
                Using the wrong partner code? ({partnerInfo?.code})
              </button>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
