import { useState, useEffect } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import axios from "axios";
import { useAuth } from "@/contexts/AuthContext";
import { applyPartnerBranding } from "@/contexts/WebsiteContext";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { AlertCircle, ArrowRight, ChevronLeft, Loader2 } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

interface PartnerInfo {
  name: string;
  code: string;
  logo_url?: string;
  primary_color?: string;
  accent_color?: string;
  is_platform?: boolean;
}

/** Simple luminance check — returns true if text should be dark on this bg */
function isLightColor(hex?: string): boolean {
  if (!hex) return false;
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return false;
  const r = parseInt(m[1].slice(0, 2), 16);
  const g = parseInt(m[1].slice(2, 4), 16);
  const b = parseInt(m[1].slice(4, 6), 16);
  return (r * 299 + g * 587 + b * 114) / 1000 > 155;
}

const css = `
  @keyframes slideUpFade {
    from { opacity: 0; transform: translateY(16px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  @keyframes scaleIn {
    from { opacity: 0; transform: scale(0.96); }
    to   { opacity: 1; transform: scale(1); }
  }
  .anim-slide-up   { animation: slideUpFade 0.45s cubic-bezier(.16,1,.3,1) both; }
  .anim-scale-in   { animation: scaleIn 0.35s cubic-bezier(.16,1,.3,1) both; }
  .delay-100 { animation-delay: 100ms; }
  .delay-200 { animation-delay: 200ms; }
  .delay-300 { animation-delay: 300ms; }
  .delay-400 { animation-delay: 400ms; }
  .auth-input {
    transition: border-color 0.2s, box-shadow 0.2s;
  }
  .auth-input:focus {
    border-color: #0f172a;
    box-shadow: 0 0 0 3px rgba(15,23,42,0.08);
    outline: none;
  }
  .auth-input.error {
    border-color: #ef4444;
    box-shadow: 0 0 0 3px rgba(239,68,68,0.08);
  }
  .btn-primary {
    transition: background-color 0.15s, transform 0.1s, box-shadow 0.15s;
  }
  .btn-primary:hover:not(:disabled) {
    box-shadow: 0 4px 14px rgba(0,0,0,0.18);
  }
  .btn-primary:active:not(:disabled) {
    transform: scale(0.98);
  }
  .partner-pill {
    transition: background-color 0.15s, color 0.15s;
  }
  .partner-pill:hover {
    background-color: #e2e8f0;
  }
`;

export default function Login() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const redirect = searchParams.get("redirect") || "";
  const { login } = useAuth();

  const [step, setStep] = useState<"gateway" | "auth">("gateway");
  const [partnerInfo, setPartnerInfo] = useState<PartnerInfo | null>(null);
  const [authKey, setAuthKey] = useState(0); // force re-mount for animation replay

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
        is_platform: tenant.is_platform ?? false,
      });
      setAuthKey(k => k + 1);
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
  const lightBg = isLightColor(primary);
  const panelText = lightBg ? "#0f172a" : "#ffffff";
  const panelMuted = lightBg ? "rgba(0,0,0,0.4)" : "rgba(255,255,255,0.45)";

  // ── Gateway ──────────────────────────────────────────────────────────────────
  if (step === "gateway") {
    return (
      <>
        <style>{css}</style>
        <div
          className="min-h-screen bg-white flex items-center justify-center px-4"
          data-testid="auth-gateway"
        >
          <div className="w-full max-w-[400px]">

            {/* Logo mark */}
            <div className="anim-slide-up flex justify-center mb-10">
              <div className="h-11 w-11 rounded-xl bg-slate-900 flex items-center justify-center shadow-lg">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                  <rect x="3" y="3" width="8" height="8" rx="1.5" fill="white" fillOpacity="0.9"/>
                  <rect x="13" y="3" width="8" height="8" rx="1.5" fill="white" fillOpacity="0.5"/>
                  <rect x="3" y="13" width="8" height="8" rx="1.5" fill="white" fillOpacity="0.5"/>
                  <rect x="13" y="13" width="8" height="8" rx="1.5" fill="white" fillOpacity="0.9"/>
                </svg>
              </div>
            </div>

            {/* Heading */}
            <div className="anim-slide-up delay-100 text-center mb-8">
              <h1 className="text-[2rem] font-bold text-slate-900 tracking-tight leading-tight">
                Welcome
              </h1>
              <p className="text-slate-400 text-sm mt-1.5">Enter your partner code to sign in.</p>
            </div>

            {/* Form */}
            <div className="anim-slide-up delay-200 space-y-3">
              <div className="relative">
                <input
                  placeholder="Partner code"
                  value={codeInput}
                  onChange={e => { setCodeInput(e.target.value); setCodeError(""); }}
                  onKeyDown={e => e.key === "Enter" && codeInput.trim() && validateAndProceed(codeInput)}
                  required
                  autoFocus
                  className={`auth-input w-full h-12 px-4 rounded-xl border text-sm text-slate-800 placeholder:text-slate-300 bg-white ${codeError ? "error" : "border-slate-200"}`}
                  data-testid="partner-code-input"
                />
                {codeError && (
                  <p
                    className="flex items-center gap-1.5 mt-2 text-xs text-red-500 pl-1"
                    data-testid="gateway-error"
                  >
                    <AlertCircle size={11} strokeWidth={2.5} /> {codeError}
                  </p>
                )}
              </div>

              <button
                onClick={() => codeInput.trim() && validateAndProceed(codeInput)}
                disabled={codeLoading || !codeInput.trim()}
                className="btn-primary w-full h-12 rounded-xl bg-slate-900 text-white text-sm font-semibold flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed shadow-sm"
                data-testid="partner-code-submit"
              >
                {codeLoading ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <>Continue <ArrowRight size={15} strokeWidth={2.5} /></>
                )}
              </button>
            </div>

            {/* Divider + register */}
            <div className="anim-slide-up delay-300 mt-8 text-center">
              <Link
                to="/signup?type=partner"
                className="text-sm text-slate-400 hover:text-slate-700 transition-colors"
                data-testid="register-partner-link"
              >
                Register as a partner
              </Link>
            </div>

          </div>
        </div>
      </>
    );
  }

  // ── Auth screen ───────────────────────────────────────────────────────────────
  return (
    <>
      <style>{css}</style>
      <div className="min-h-screen bg-white flex" data-testid="login-page" key={authKey}>

        {/* Left brand panel */}
        <div
          className="hidden lg:flex w-[340px] xl:w-[400px] shrink-0 flex-col justify-between p-10 relative overflow-hidden"
          style={{ backgroundColor: primary }}
        >
          {/* Decorative circles */}
          <div
            className="absolute -bottom-16 -right-16 w-64 h-64 rounded-full"
            style={{ background: lightBg ? "rgba(0,0,0,0.06)" : "rgba(255,255,255,0.06)" }}
          />
          <div
            className="absolute -top-10 -left-10 w-40 h-40 rounded-full"
            style={{ background: lightBg ? "rgba(0,0,0,0.04)" : "rgba(255,255,255,0.04)" }}
          />

          {/* Partner identity */}
          <div className="relative z-10 flex items-center gap-2.5">
            {partnerInfo?.is_platform ? (
              <div
                className="h-8 w-8 rounded-lg flex items-center justify-center"
                style={{ background: lightBg ? "rgba(0,0,0,0.12)" : "rgba(255,255,255,0.2)" }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                  <rect x="3" y="3" width="8" height="8" rx="1.5" fill={panelText} fillOpacity="0.9"/>
                  <rect x="13" y="3" width="8" height="8" rx="1.5" fill={panelText} fillOpacity="0.5"/>
                  <rect x="3" y="13" width="8" height="8" rx="1.5" fill={panelText} fillOpacity="0.5"/>
                  <rect x="13" y="13" width="8" height="8" rx="1.5" fill={panelText} fillOpacity="0.9"/>
                </svg>
              </div>
            ) : partnerInfo?.logo_url ? (
              <img src={partnerInfo.logo_url} alt={partnerInfo.name} className="h-7 object-contain" />
            ) : (
              <div
                className="h-8 w-8 rounded-lg flex items-center justify-center text-sm font-bold"
                style={{ background: lightBg ? "rgba(0,0,0,0.12)" : "rgba(255,255,255,0.2)", color: panelText }}
              >
                {partnerInfo?.name?.[0] || "P"}
              </div>
            )}
            <span className="text-sm font-semibold" style={{ color: panelText }}>
              {partnerInfo?.is_platform ? "Platform Administration" : partnerInfo?.name}
            </span>
          </div>

          {/* Large decorative initial */}
          <div
            className="relative z-10 text-[7rem] font-black leading-none select-none"
            style={{ color: lightBg ? "rgba(0,0,0,0.07)" : "rgba(255,255,255,0.08)" }}
          >
            {partnerInfo?.is_platform ? "⌘" : (partnerInfo?.name?.[0] || "P")}
          </div>

          {/* Code label at very bottom */}
          <span
            className="relative z-10 text-xs font-mono"
            style={{ color: panelMuted }}
          >
            {partnerInfo?.code}
          </span>
        </div>

        {/* Right form panel */}
        <div className="flex-1 flex items-center justify-center px-6 py-12 relative">
          <div className="w-full max-w-[360px] space-y-7" key={authKey}>

            {/* Mobile partner badge */}
            <div className="lg:hidden anim-slide-up flex items-center gap-2">
              {partnerInfo?.logo_url ? (
                <img src={partnerInfo.logo_url} alt={partnerInfo.name} className="h-6 object-contain" />
              ) : (
                <div
                  className="h-6 w-6 rounded text-xs font-bold text-white flex items-center justify-center"
                  style={{ backgroundColor: primary }}
                >
                  {partnerInfo?.name?.[0]}
                </div>
              )}
              <span className="text-sm text-slate-500">{partnerInfo?.name}</span>
            </div>

            {/* Heading */}
            <div className="anim-slide-up">
              <h1 className="text-[1.75rem] font-bold text-slate-900 tracking-tight">Sign in</h1>
              <p className="text-slate-400 text-sm mt-1">Welcome back. Enter your credentials to continue.</p>
            </div>

            {/* Error */}
            {loginError && (
              <p className="anim-scale-in flex items-center gap-1.5 text-xs text-red-500" data-testid="login-error">
                <AlertCircle size={12} strokeWidth={2.5} /> {loginError}
              </p>
            )}

            {/* Form */}
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
              className="space-y-4"
              data-testid="login-form"
            >
              <div className="anim-slide-up delay-100 space-y-1.5">
                <Label htmlFor="email" className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Email
                </Label>
                <input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  required
                  autoFocus
                  className="auth-input w-full h-11 px-3.5 rounded-lg border border-slate-200 text-sm text-slate-800 placeholder:text-slate-300 bg-white"
                  data-testid="login-email-input"
                />
              </div>

              <div className="anim-slide-up delay-200 space-y-1.5">
                <div className="flex items-center justify-between">
                  <Label htmlFor="password" className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Password
                  </Label>
                  <Link
                    to={`/forgot-password${redirect ? `?redirect=${encodeURIComponent(redirect)}` : ""}`}
                    className="text-xs font-medium transition-colors hover:opacity-70"
                    style={{ color: accent }}
                    data-testid="forgot-password-link"
                  >
                    Forgot password?
                  </Link>
                </div>
                <input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                  className="auth-input w-full h-11 px-3.5 rounded-lg border border-slate-200 text-sm text-slate-800 placeholder:text-slate-300 bg-white"
                  data-testid="login-password-input"
                />
              </div>

              <div className="anim-slide-up delay-300 pt-1">
                <button
                  type="submit"
                  disabled={loginLoading}
                  className="btn-primary w-full h-11 rounded-lg text-white text-sm font-semibold flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
                  style={{ backgroundColor: primary }}
                  data-testid="login-submit-button"
                >
                  {loginLoading ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : "Sign In"}
                </button>
              </div>
            </form>

            {/* Footer links — hidden for platform portal */}
            {!partnerInfo?.is_platform && (
              <div className="anim-slide-up delay-400 text-center text-sm text-slate-400">
                New here?{" "}
                <Link
                  to={`/signup${redirect ? `?redirect=${encodeURIComponent(redirect)}` : ""}`}
                  className="font-semibold transition-colors hover:opacity-70"
                  style={{ color: accent }}
                  data-testid="register-customer-link"
                >
                  Create an account
                </Link>
              </div>
            )}

          </div>

          {/* Floating partner pill — bottom right */}
          <button
            onClick={handleChangePartner}
            className="partner-pill absolute bottom-6 right-6 flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 rounded-full text-xs font-medium text-slate-500"
            data-testid="change-partner-btn"
          >
            <ChevronLeft size={11} strokeWidth={2.5} />
            {partnerInfo?.code}
          </button>

        </div>
      </div>
    </>
  );
}
