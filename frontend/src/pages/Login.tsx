import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import axios from "axios";
import { useAuth } from "@/contexts/AuthContext";
import { applyPartnerBranding } from "@/contexts/WebsiteContext";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle, Building2, ArrowRight, ChevronLeft } from "lucide-react";

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
  const { login } = useAuth();

  // step: "gateway" | "auth"
  const [step, setStep] = useState<"gateway" | "auth">("gateway");
  const [partnerInfo, setPartnerInfo] = useState<PartnerInfo | null>(null);

  const [codeInput, setCodeInput] = useState("");
  const [codeLoading, setCodeLoading] = useState(false);
  const [codeError, setCodeError] = useState("");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState("");

  // On mount — if partner code already stored, skip gateway
  useEffect(() => {
    const stored = localStorage.getItem("aa_partner_code");
    if (stored) {
      // Re-validate and re-load branding
      validateAndProceed(stored, true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function validateAndProceed(code: string, silent = false) {
    if (!silent) setCodeLoading(true);
    setCodeError("");
    try {
      // 1. Validate partner code
      const res = await axios.get(`${API}/api/tenant-info?code=${encodeURIComponent(code.trim().toLowerCase())}`);
      const tenant = res.data.tenant;

      // 2. Fetch + apply partner branding
      const branding = await applyPartnerBranding(code.trim().toLowerCase());

      // 3. Persist
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
        setCodeError(err.response?.data?.detail || "Partner code not found. Please check and try again.");
      } else {
        // Stored code became invalid — clear it
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
      navigate(result?.is_admin ? "/admin" : "/portal");
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

  // ── Gateway Screen ──────────────────────────────────────────────────────────
  if (step === "gateway") {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center px-4 py-16" data-testid="auth-gateway">
        {/* Minimal platform badge */}
        <div className="mb-10 text-center space-y-2">
          <div className="inline-flex items-center justify-center h-14 w-14 rounded-2xl bg-white/10 border border-white/10 mb-4">
            <Building2 className="text-white/80" size={24} />
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Welcome</h1>
          <p className="text-slate-400 text-sm max-w-xs">
            Enter your organization's partner code to access the portal.
          </p>
        </div>

        <div className="w-full max-w-sm space-y-4">
          {codeError && (
            <Alert variant="destructive" data-testid="gateway-error">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{codeError}</AlertDescription>
            </Alert>
          )}

          <form
            onSubmit={handleCodeSubmit}
            className="bg-white/5 border border-white/10 rounded-2xl p-6 space-y-4 backdrop-blur-sm"
            data-testid="partner-code-form"
          >
            <div className="space-y-2">
              <Label htmlFor="partner-code" className="text-slate-300 text-sm">Partner Code</Label>
              <Input
                id="partner-code"
                placeholder="e.g. automate-accounts"
                value={codeInput}
                onChange={e => setCodeInput(e.target.value)}
                required
                autoFocus
                className="bg-white/10 border-white/20 text-white placeholder:text-slate-500 focus:border-white/40"
                data-testid="partner-code-input"
              />
              <p className="text-xs text-slate-500">Provided by your service organization</p>
            </div>

            <Button
              type="submit"
              className="w-full h-11 font-semibold bg-white text-slate-900 hover:bg-slate-100 transition-all"
              disabled={codeLoading || !codeInput.trim()}
              data-testid="partner-code-submit"
            >
              {codeLoading ? (
                <span className="flex items-center gap-2">
                  <span className="h-4 w-4 border-2 border-slate-400 border-t-transparent rounded-full animate-spin" />
                  Verifying…
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  Continue <ArrowRight size={16} />
                </span>
              )}
            </Button>
          </form>

          <div className="relative flex items-center gap-3">
            <div className="flex-1 h-px bg-white/10" />
            <span className="text-xs text-slate-600">or</span>
            <div className="flex-1 h-px bg-white/10" />
          </div>

          <div className="text-center">
            <Link
              to="/signup?type=partner"
              className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-white transition-colors"
              data-testid="register-partner-link"
            >
              <Building2 size={14} />
              Register as a partner organization
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // ── Auth Screen (post-validation) ───────────────────────────────────────────
  const primaryColor = partnerInfo?.primary_color || "var(--aa-primary)";
  const accentColor = partnerInfo?.accent_color || "var(--aa-accent)";

  return (
    <div className="min-h-screen aa-bg flex items-center justify-center px-4 py-12" data-testid="login-page">
      <div className="w-full max-w-sm space-y-6">

        {/* Partner brand header */}
        <div className="text-center space-y-3">
          {partnerInfo?.logo_url ? (
            <div className="flex justify-center">
              <img src={partnerInfo.logo_url} alt={partnerInfo.name} className="h-12 object-contain" />
            </div>
          ) : (
            <div className="flex justify-center">
              <div
                className="h-12 w-12 rounded-xl flex items-center justify-center text-white text-xl font-bold"
                style={{ backgroundColor: primaryColor }}
              >
                {partnerInfo?.name?.[0] || "P"}
              </div>
            </div>
          )}
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-0.5">
              {partnerInfo?.name}
            </p>
            <h1 className="text-2xl font-bold text-slate-900">Welcome back</h1>
            <p className="text-sm text-slate-500">Sign in to your account</p>
          </div>
        </div>

        {loginError && (
          <Alert variant="destructive" data-testid="login-error">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{loginError}</AlertDescription>
          </Alert>
        )}

        <form
          onSubmit={handleLogin}
          className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-4"
          data-testid="login-form"
        >
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              autoFocus
              data-testid="login-email-input"
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="password">Password</Label>
              <Link
                to="/forgot-password"
                className="text-xs hover:underline"
                style={{ color: accentColor }}
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
              data-testid="login-password-input"
            />
          </div>

          <Button
            type="submit"
            className="w-full text-white"
            style={{ backgroundColor: primaryColor }}
            disabled={loginLoading}
            data-testid="login-submit-button"
          >
            {loginLoading ? "Signing in…" : "Sign In"}
          </Button>

          <div className="pt-2 border-t border-slate-100 text-center text-sm text-slate-500">
            New customer?{" "}
            <Link
              to="/signup"
              className="font-medium hover:underline"
              style={{ color: accentColor }}
              data-testid="register-customer-link"
            >
              Create an account
            </Link>
          </div>
        </form>

        {/* Change partner */}
        <div className="text-center">
          <button
            onClick={handleChangePartner}
            className="inline-flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600 transition-colors"
            data-testid="change-partner-btn"
          >
            <ChevronLeft size={12} />
            Using the wrong partner code? ({partnerInfo?.code})
          </button>
        </div>

      </div>
    </div>
  );
}
