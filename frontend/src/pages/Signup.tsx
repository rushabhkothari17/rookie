import { useState, useEffect } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/contexts/AuthContext";
import { useWebsite, applyPartnerBranding } from "@/contexts/WebsiteContext";
import { parseSchema, getAddressConfig, type FormField } from "@/components/FormSchemaBuilder";
import { CustomerSignupFields } from "@/components/CustomerSignupFields";
import { useCountries } from "@/hooks/useCountries";
import { useSupportedCurrencies } from "@/hooks/useSupportedCurrencies";
import { PartnerOrgForm, PartnerOrgFormValue, EMPTY_PARTNER_ORG } from "@/components/admin/PartnerOrgForm";
import api from "@/lib/api";
import { ChevronRight, CheckCircle2, ChevronLeft, Copy, Check, DollarSign } from "lucide-react";

export default function Signup() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const isPartnerMode = searchParams.get("type") === "partner";
  const { register } = useAuth();
  const ws = useWebsite();

  const [partnerCode, setPartnerCode] = useState<string>(() => localStorage.getItem("aa_partner_code") || "");
  const [partnerName, setPartnerName] = useState<string>("");
  const [partnerLogoUrl, setPartnerLogoUrl] = useState<string>("");
  const [partnerPrimaryColor, setPartnerPrimaryColor] = useState<string>("");

  // Countries/provinces from taxes module
  const countries = useCountries(partnerCode || undefined);
  const { currencies: supportedCurrencies } = useSupportedCurrencies();
  const [partnerOrg, setPartnerOrg] = useState<PartnerOrgFormValue>(EMPTY_PARTNER_ORG);
  const [partnerLoading, setPartnerLoading] = useState(false);
  const [generatedCode, setGeneratedCode] = useState("");
  const [codeCopied, setCodeCopied] = useState(false);

  // Fetch provinces/states for customer signup when country changes
  const [provinces, setProvinces] = useState<{ value: string; label: string }[]>([]);
  const [form, setForm] = useState({
    full_name: "", job_title: "", company_name: "",
    email: "", phone: "", password: "",
    line1: "", line2: "", city: "", region: "", postal: "", country: "",
  });
  const [extraFields, setExtraFields] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [verificationCode, setVerificationCode] = useState("");

  // On mount: require partner code for customer signup
  useEffect(() => {
    if (isPartnerMode) return;
    const stored = localStorage.getItem("aa_partner_code");
    if (!stored) {
      navigate("/login");
      return;
    }
    setPartnerCode(stored);
    // Load partner branding
    applyPartnerBranding(stored).then(s => {
      setPartnerName(s.store_name || "");
      setPartnerLogoUrl(s.logo_url || "");
      setPartnerPrimaryColor(s.primary_color || "");
    }).catch(() => {});
  }, [isPartnerMode, navigate]);

  // Fetch provinces/states when country changes (customer signup)
  useEffect(() => {
    const country = form.country;
    if (country) {
      api.get(`/utils/provinces?country_code=${encodeURIComponent(country)}`).then(r => {
        setProvinces(r.data.regions || []);
        if (r.data.regions && !r.data.regions.find((p: any) => p.value === form.region || p.label === form.region)) {
          handleFieldChange("region", "");
        }
      }).catch(() => setProvinces([]));
    } else {
      setProvinces([]);
    }
  }, [form.country]);

  const schema: FormField[] = parseSchema(ws.signup_form_schema);

  const STD_KEYS = ["full_name", "email", "password", "company_name", "job_title", "phone", "line1", "line2", "city", "region", "postal", "country"];

  const handleFieldChange = (key: string, value: string) => {
    if (STD_KEYS.includes(key)) {
      if (key === "country") {
        setForm(prev => ({ ...prev, country: value, region: "" }));
      } else {
        setForm(prev => ({ ...prev, [key]: value }));
      }
    } else {
      setExtraFields(prev => ({ ...prev, [key]: value }));
    }
  };

  // Combined values for the shared field component
  const allValues: Record<string, string> = { ...form, ...extraFields };

  const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
  const PHONE_REGEX = /^[+\d][\d\s\-(). ]{3,49}$/;
  const FIELD_MAX: Record<string, number> = { email: 50, company_name: 50, job_title: 50, phone: 50, full_name: 50 };

  const validateSignupForm = (): string[] => {
    const errors: string[] = [];
    if (!form.email.trim()) errors.push("Email");
    else if (!EMAIL_REGEX.test(form.email.trim())) errors.push("Email (invalid format)");
    else if (form.email.trim().length > 50) errors.push("Email (max 50 characters)");
    if (!form.password.trim()) errors.push("Password");
    for (const field of schema.filter(f => f.enabled !== false)) {
      if (field.type === "address") {
        const cfg = getAddressConfig(field);
        const checks: Array<{ cfgKey: "line1"|"line2"|"city"|"state"|"postal"|"country"; formKey: keyof typeof form; label: string }> = [
          { cfgKey: "line1",   formKey: "line1",    label: "Address Line 1"   },
          { cfgKey: "line2",   formKey: "line2",    label: "Address Line 2"   },
          { cfgKey: "city",    formKey: "city",     label: "City"             },
          { cfgKey: "state",   formKey: "region",   label: "State / Province" },
          { cfgKey: "postal",  formKey: "postal",   label: "Postal Code"      },
          { cfgKey: "country", formKey: "country",  label: "Country"          },
        ];
        for (const { cfgKey, formKey, label } of checks) {
          if (cfg[cfgKey].required && !form[formKey]?.trim()) errors.push(label);
        }
      } else if (field.required) {
        if (STD_KEYS.includes(field.key)) {
          const val = form[field.key as keyof typeof form];
          if (!val || !val.trim()) errors.push(field.label || field.key);
          else if (FIELD_MAX[field.key] && val.trim().length > FIELD_MAX[field.key]) errors.push(`${field.label || field.key} (max ${FIELD_MAX[field.key]} characters)`);
          else if (field.key === "phone" && val.trim() && !PHONE_REGEX.test(val.trim())) errors.push("Phone (invalid format — digits, spaces, +, - only)");
        } else {
          if (!extraFields[field.key]?.trim()) errors.push(field.label || field.key);
        }
      }
    }
    return errors;
  };

  const validatePartnerForm = (): string[] => {
    const errors: string[] = [];
    if (!partnerOrg.name.trim()) errors.push("Organization Name");
    if (!partnerOrg.admin_name.trim()) errors.push("Admin Full Name");
    if (!partnerOrg.admin_email.trim()) errors.push("Admin Email");
    if (!partnerOrg.admin_password.trim()) errors.push("Password");
    return errors;
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const errors = validateSignupForm();
    if (errors.length > 0) {
      toast.error(`Please fill in: ${errors.join(", ")}`);
      return;
    }
    setLoading(true);
    try {
      const profile_meta = Object.keys(extraFields).length ? extraFields : undefined;
      const response = await register({
        full_name: form.full_name,
        job_title: form.job_title,
        company_name: form.company_name,
        email: form.email,
        phone: form.phone,
        password: form.password,
        address: { line1: form.line1, line2: form.line2, city: form.city, region: form.region, postal: form.postal, country: form.country },
        ...(profile_meta ? { profile_meta } : {}),
      }, partnerCode || undefined);
      setVerificationCode(response.verification_code || "");
      localStorage.setItem("aa_signup_email", form.email);
      toast.success("Verification email sent! Please check your inbox.");
      navigate("/verify");
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Signup failed");
    } finally {
      setLoading(false);
    }
  };

  const handlePartnerSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errors = validatePartnerForm();
    if (errors.length > 0) {
      toast.error(`Please fill in: ${errors.join(", ")}`);
      return;
    }
    setPartnerLoading(true);
    try {
      const res = await api.post("/auth/register-partner", partnerOrg);
      setGeneratedCode(res.data.partner_code || "");
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Registration failed");
    } finally {
      setPartnerLoading(false);
    }
  };

  const handleCopyCode = () => {
    navigator.clipboard.writeText(generatedCode);
    setCodeCopied(true);
    setTimeout(() => setCodeCopied(false), 2000);
  };

  const storeName = ws.store_name || "Portal";

  // Partner mode
  if (isPartnerMode) {
    // ── Success screen ────────────────────────────────────────────────────────
    if (generatedCode) {
      return (
        <div className="min-h-screen bg-white flex items-center justify-center p-4" data-testid="partner-signup-success">
          <div className="w-full max-w-md text-center space-y-6">
            <div className="flex justify-center">
              <div className="h-14 w-14 rounded-full bg-green-50 flex items-center justify-center">
                <CheckCircle2 size={28} className="text-green-500" strokeWidth={2} />
              </div>
            </div>

            <div className="space-y-1">
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Organization created!</h1>
              <p className="text-sm text-slate-400">Save your partner code — you'll need it to sign in.</p>
            </div>

            {/* Partner code display */}
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-6 space-y-3">
              <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">Your Partner Code</p>
              <div className="flex items-center gap-2">
                <code
                  className="flex-1 text-2xl font-bold tracking-tight text-slate-900 bg-white border border-slate-200 rounded-xl px-4 py-3 font-mono text-center"
                  data-testid="generated-partner-code"
                >
                  {generatedCode}
                </code>
                <button
                  onClick={handleCopyCode}
                  className="h-12 w-12 shrink-0 rounded-xl border border-slate-200 bg-white flex items-center justify-center text-slate-500 hover:border-slate-400 hover:text-slate-800 transition-colors"
                  data-testid="copy-code-btn"
                  title="Copy partner code"
                >
                  {codeCopied ? <Check size={16} className="text-green-500" /> : <Copy size={16} />}
                </button>
              </div>
              <p className="text-xs text-slate-400">
                Share this code with your customers so they can sign in and register through your portal.
              </p>
            </div>

            <button
              onClick={() => {
                localStorage.setItem("aa_partner_code", generatedCode);
                navigate("/login");
              }}
              className="w-full h-11 rounded-lg bg-slate-900 text-white text-sm font-semibold hover:bg-slate-700 transition-colors"
              data-testid="goto-login-after-register"
            >
              Sign in to your organization
            </button>

            <Link to="/login" onClick={() => localStorage.removeItem("aa_partner_code")} className="block text-sm text-slate-400 hover:text-slate-600 transition-colors">
              Go to login gateway
            </Link>
          </div>
        </div>
      );
    }

    // ── Registration form ─────────────────────────────────────────────────────
    return (
      <div className="min-h-screen bg-white flex items-center justify-center p-4" data-testid="partner-signup-page">
        <div className="w-full max-w-md space-y-6">
          <div className="space-y-1">
            <Link to="/login" className="inline-flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600 transition-colors mb-4">
              <ChevronLeft size={12} /> Back
            </Link>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Create your organization</h1>
            <p className="text-sm text-slate-400">Set up your partner workspace to get started.</p>
          </div>

          <form className="space-y-3" onSubmit={handlePartnerSubmit}>
            <PartnerOrgForm
              value={partnerOrg}
              onChange={setPartnerOrg}
              currencies={supportedCurrencies.length ? supportedCurrencies : ["USD", "CAD", "EUR", "GBP", "AUD", "INR", "MXN"]}
              schema={ws.partner_signup_form_schema}
              compact
              testIdPrefix="partner"
            />
            <p className="text-xs text-slate-400"><span className="text-red-500">*</span> Required field</p>
            <Button
              type="submit"
              className="w-full h-11 font-semibold bg-slate-900 hover:bg-slate-700 text-white"
              disabled={partnerLoading}
              data-testid="partner-signup-submit"
            >
              {partnerLoading ? "Creating…" : "Create organization"}
            </Button>
          </form>

          <p className="text-center text-sm text-slate-400">
            Already have an account?{" "}
            <Link to="/login" className="font-semibold text-slate-700 hover:underline">Sign in</Link>
          </p>
        </div>
      </div>
    );
  }

  // Customer signup
  const primaryColor = partnerPrimaryColor || "var(--aa-primary)";
  return (
    <div className="min-h-screen flex" data-testid="signup-page">
      {/* Left branding panel */}
      <div
        className="hidden lg:flex w-80 xl:w-96 flex-col justify-between p-10 shrink-0"
        style={{ backgroundColor: partnerPrimaryColor || "var(--aa-primary, #1e293b)" }}
      >
        <div>
          <div className="flex items-center gap-2.5 mb-10">
            {(partnerLogoUrl || ws.logo_url) ? (
              <img src={partnerLogoUrl || ws.logo_url} alt={partnerName || storeName} className="h-8 object-contain" />
            ) : (
              <div className="h-8 w-8 rounded-lg bg-white/20 flex items-center justify-center">
                <span className="text-white font-bold text-sm">{(partnerName || storeName)[0]}</span>
              </div>
            )}
            <span className="text-white font-bold text-lg">{partnerName || storeName}</span>
          </div>

          <div className="space-y-2">
            <h2 className="text-white text-2xl font-bold leading-snug">
              {ws.register_title || "Create your client portal"}
            </h2>
            {ws.register_subtitle && (
              <p className="text-white/60 text-sm leading-relaxed">{ws.register_subtitle}</p>
            )}
          </div>

          <div className="mt-10 space-y-4">
            {[
              ws.signup_bullet_1 || "Access your orders and subscriptions",
              ws.signup_bullet_2 || "Download invoices and documents",
              ws.signup_bullet_3 || "Track project progress in real time",
            ].filter(Boolean).map((item, i) => (
              <div key={i} className="flex items-start gap-3">
                <CheckCircle2 size={16} className="text-white/50 mt-0.5 shrink-0" />
                <span className="text-white/70 text-sm">{item}</span>
              </div>
            ))}
            {(ws.signup_cta || "Get started in minutes") && (
              <div className="mt-6 pt-5 border-t border-white/10">
                <p className="text-white font-semibold text-sm">{ws.signup_cta || "Get started in minutes"}</p>
              </div>
            )}
          </div>
        </div>

        <p className="text-white/30 text-xs">© {new Date().getFullYear()} {storeName}</p>
      </div>

      {/* Right form panel */}
      <div className="flex-1 bg-white flex items-start justify-center py-10 px-4 overflow-y-auto">
        <div className="w-full max-w-2xl">
          {/* Mobile header */}
          <div className="lg:hidden mb-6 text-center">
            <h1 className="text-2xl font-bold text-slate-900">{storeName}</h1>
            <p className="text-sm text-slate-500 mt-1">{ws.register_title || "Create your portal access"}</p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white shadow-sm p-8">
            {/* Back to sign in */}
            <div className="mb-4">
              <Link to="/login" className="inline-flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600 transition-colors" data-testid="signup-back-link">
                <ChevronLeft size={13} /> Back to sign in
              </Link>
            </div>
            <div className="mb-6">
              <h2 className="text-xl font-bold text-slate-900">{ws.signup_form_title || "Create an account"}</h2>
              {ws.signup_form_subtitle && (
                <p className="text-sm text-slate-500 mt-1">{ws.signup_form_subtitle}</p>
              )}
              <p className="text-sm text-slate-500 mt-1">Already have access?{" "}
                <Link to="/login" className="font-semibold hover:underline" style={{ color: "var(--aa-accent)" }} data-testid="signup-login-link">Sign in</Link>
              </p>
              {/* Partner badge */}
              {partnerCode && (
                <div className="mt-3 flex items-center justify-between rounded-lg bg-slate-50 border border-slate-200 px-3 py-2">
                  <span className="text-xs text-slate-500">
                    Partner: <span className="font-semibold text-slate-700">{partnerName || partnerCode}</span>
                  </span>
                  <Link
                    to="/login"
                    onClick={() => localStorage.removeItem("aa_partner_code")}
                    className="text-xs text-slate-400 hover:text-slate-600 flex items-center gap-1"
                    data-testid="change-partner-from-signup"
                  >
                    <ChevronLeft size={11} /> Change
                  </Link>
                </div>
              )}
            </div>

            <form className="space-y-6" onSubmit={handleSubmit}>
              <CustomerSignupFields
                schema={schema}
                values={allValues}
                onChange={handleFieldChange}
                provinces={provinces}
                countries={countries}
                showPassword={true}
                compact={false}
              />

              <Button
                type="submit"
                className="w-full h-11 font-semibold text-white text-sm rounded-xl transition-all hover:opacity-90 active:scale-[0.98]"
                disabled={loading}
                data-testid="signup-submit-button"
                style={{ backgroundColor: "var(--aa-primary)" }}
              >
                {loading ? "Creating account…" : "Create account"}
              </Button>

              <p className="text-center text-xs text-slate-400">
                Registering a new organization?{" "}
                <Link to="/signup?type=partner" className="font-semibold hover:underline" style={{ color: "var(--aa-accent)" }} data-testid="partner-signup-link">Sign up as a partner</Link>
              </p>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
