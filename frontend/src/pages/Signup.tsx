import { useState, useEffect } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useAuth } from "@/contexts/AuthContext";
import { useWebsite, applyPartnerBranding } from "@/contexts/WebsiteContext";
import { parseSchema, type FormField } from "@/components/FormSchemaBuilder";
import api from "@/lib/api";
import { User, Building2, Mail, Lock, Phone, Briefcase, MapPin, ChevronRight, CheckCircle2, ChevronLeft, Copy, Check, DollarSign } from "lucide-react";

const STANDARD_KEYS = ["full_name", "email", "password", "company_name", "job_title", "phone", "country"];

const countries = [
  { value: "Canada", label: "Canada" },
  { value: "USA", label: "United States" },
  { value: "Other", label: "Other" },
];

function FieldWrapper({ label, icon: Icon, children, fullWidth = false, required = false }: {
  label: string; icon?: any; children: React.ReactNode; fullWidth?: boolean; required?: boolean;
}) {
  return (
    <div className={`space-y-1.5 ${fullWidth ? "sm:col-span-2" : ""}`}>
      <label className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
        {Icon && <Icon size={12} className="text-slate-400" />}
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      {children}
    </div>
  );
}

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

  const [partnerOrg, setPartnerOrg] = useState({
    name: "", admin_name: "", admin_email: "", admin_password: "", base_currency: "USD",
    address: { line1: "", line2: "", city: "", region: "", postal: "", country: "Canada" }
  });
  const [partnerLoading, setPartnerLoading] = useState(false);
  const [generatedCode, setGeneratedCode] = useState("");
  const [codeCopied, setCodeCopied] = useState(false);
  const [partnerProvinces, setPartnerProvinces] = useState<{ value: string; label: string }[]>([]);

  // Fetch provinces for partner signup address
  useEffect(() => {
    const c = partnerOrg.address.country;
    if (c === "Canada" || c === "USA") {
      api.get(`/utils/provinces?country_code=${c}`).then(r => setPartnerProvinces(r.data.regions || [])).catch(() => setPartnerProvinces([]));
    } else {
      setPartnerProvinces([]);
    }
  }, [partnerOrg.address.country]);

  const [form, setForm] = useState({
    full_name: "", job_title: "", company_name: "",
    email: "", phone: "", password: "",
    line1: "", line2: "", city: "", region: "", postal: "", country: "Canada",
  });
  const [extraFields, setExtraFields] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [provinces, setProvinces] = useState<{ value: string; label: string }[]>([]);
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

  // Fetch provinces/states when country changes
  useEffect(() => {
    const country = form.country;
    if (country === "Canada" || country === "USA") {
      api.get(`/utils/provinces?country_code=${country}`).then(r => {
        setProvinces(r.data.regions || []);
        // Clear region if current value is not in the new list
        if (r.data.regions && !r.data.regions.find((p: any) => p.value === form.region || p.label === form.region)) {
          handleChange("region", "");
        }
      }).catch(() => setProvinces([]));
    } else {
      setProvinces([]);
    }
  }, [form.country]);

  const handleChange = (key: string, value: string) => setForm(prev => ({ ...prev, [key]: value }));

  const schema: FormField[] = parseSchema(ws.signup_form_schema);
  const customFields = schema.filter(f => !STANDARD_KEYS.includes(f.key) && f.enabled !== false);

  const getFieldProp = (key: string, prop: "required" | "label" | "placeholder" | "enabled") => {
    const f = schema.find(f => f.key === key);
    if (!f) return prop === "required" ? false : prop === "enabled" ? true : "";
    return f[prop];
  };

  const isFieldVisible = (key: string, defaultEnabled = true): boolean => {
    if (schema.length === 0) return defaultEnabled;
    const f = schema.find(f => f.key === key);
    if (!f) return false;
    return f.enabled !== false;
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
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
            <div className="relative">
              <Building2 className="absolute left-3 top-2.5 h-4 w-4 text-slate-400 pointer-events-none" />
              <Input className="pl-9" placeholder="Organization name *" value={partnerOrg.name} onChange={e => setPartnerOrg(p => ({ ...p, name: e.target.value }))} required data-testid="partner-org-name" />
            </div>
            <div className="relative">
              <User className="absolute left-3 top-2.5 h-4 w-4 text-slate-400 pointer-events-none" />
              <Input className="pl-9" placeholder="Your full name *" value={partnerOrg.admin_name} onChange={e => setPartnerOrg(p => ({ ...p, admin_name: e.target.value }))} required data-testid="partner-admin-name" />
            </div>
            <div className="relative">
              <Mail className="absolute left-3 top-2.5 h-4 w-4 text-slate-400 pointer-events-none" />
              <Input className="pl-9" type="email" placeholder="Admin email address *" value={partnerOrg.admin_email} onChange={e => setPartnerOrg(p => ({ ...p, admin_email: e.target.value }))} required data-testid="partner-admin-email" />
            </div>
            <div className="relative">
              <Lock className="absolute left-3 top-2.5 h-4 w-4 text-slate-400 pointer-events-none" />
              <Input className="pl-9" type="password" placeholder="Password * (min 10 chars, upper, lower, number, symbol)" value={partnerOrg.admin_password} onChange={e => setPartnerOrg(p => ({ ...p, admin_password: e.target.value }))} required data-testid="partner-admin-password" />
            </div>
            <p className="text-xs text-slate-400"><span className="text-red-500">*</span> Required field</p>
            <Select value={partnerOrg.base_currency} onValueChange={v => setPartnerOrg(p => ({ ...p, base_currency: v }))}>
              <SelectTrigger className="w-full" data-testid="partner-base-currency">
                <SelectValue placeholder="Select base currency" />
              </SelectTrigger>
              <SelectContent>
                {["USD — US Dollar", "CAD — Canadian Dollar", "EUR — Euro", "AUD — Australian Dollar", "GBP — British Pound", "INR — Indian Rupee", "MXN — Mexican Peso"].map(opt => {
                  const code = opt.split(" — ")[0];
                  return <SelectItem key={code} value={code}>{opt}</SelectItem>;
                })}
              </SelectContent>
            </Select>

            {/* Organization Address */}
            <div className="pt-2 space-y-1">
              <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Organization Address</p>
              <Input placeholder="Line 1 *" value={partnerOrg.address.line1} onChange={e => setPartnerOrg(p => ({ ...p, address: { ...p.address, line1: e.target.value } }))} required data-testid="partner-addr-line1" />
              <Input placeholder="Line 2 (optional)" value={partnerOrg.address.line2} onChange={e => setPartnerOrg(p => ({ ...p, address: { ...p.address, line2: e.target.value } }))} data-testid="partner-addr-line2" />
              <div className="grid grid-cols-2 gap-1">
                <Input placeholder="City *" value={partnerOrg.address.city} onChange={e => setPartnerOrg(p => ({ ...p, address: { ...p.address, city: e.target.value } }))} required data-testid="partner-addr-city" />
                <Input placeholder="Postal Code *" value={partnerOrg.address.postal} onChange={e => setPartnerOrg(p => ({ ...p, address: { ...p.address, postal: e.target.value } }))} required data-testid="partner-addr-postal" />
              </div>
              <Select value={partnerOrg.address.country} onValueChange={v => setPartnerOrg(p => ({ ...p, address: { ...p.address, country: v, region: "" } }))}>
                <SelectTrigger data-testid="partner-addr-country"><SelectValue placeholder="Country *" /></SelectTrigger>
                <SelectContent>
                  {[{v:"Canada",l:"Canada"},{v:"USA",l:"United States"},{v:"UK",l:"United Kingdom"},{v:"Australia",l:"Australia"},{v:"India",l:"India"},{v:"Germany",l:"Germany"},{v:"France",l:"France"},{v:"Netherlands",l:"Netherlands"},{v:"Singapore",l:"Singapore"},{v:"New Zealand",l:"New Zealand"}].map(c => <SelectItem key={c.v} value={c.v}>{c.l}</SelectItem>)}
                </SelectContent>
              </Select>
              {partnerProvinces.length > 0 ? (
                <Select value={partnerOrg.address.region} onValueChange={v => setPartnerOrg(p => ({ ...p, address: { ...p.address, region: v } }))}>
                  <SelectTrigger data-testid="partner-addr-region-select"><SelectValue placeholder="Province / State *" /></SelectTrigger>
                  <SelectContent>{partnerProvinces.map(p => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}</SelectContent>
                </Select>
              ) : (
                <Input placeholder="State / Province *" value={partnerOrg.address.region} onChange={e => setPartnerOrg(p => ({ ...p, address: { ...p.address, region: e.target.value } }))} required data-testid="partner-addr-region-input" />
              )}
            </div>

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
              "Access your orders and subscriptions",
              "Download invoices and documents",
              "Track project progress in real time",
            ].map((item, i) => (
              <div key={i} className="flex items-start gap-3">
                <CheckCircle2 size={16} className="text-white/50 mt-0.5 shrink-0" />
                <span className="text-white/70 text-sm">{item}</span>
              </div>
            ))}
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
            <div className="mb-6">
              <h2 className="text-xl font-bold text-slate-900">Create an account</h2>
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
              {/* Section: Personal Info */}
              <div>
                <div className="flex items-center gap-3 mb-4">
                  <div className="h-px flex-1 bg-slate-100" />
                  <span className="text-xs font-bold uppercase tracking-widest text-slate-400">Personal info</span>
                  <div className="h-px flex-1 bg-slate-100" />
                </div>
              {/* Required field note */}
              <p className="text-xs text-slate-400"><span className="text-red-500">*</span> Required field</p>

              <div className="grid gap-4 sm:grid-cols-2">
                <FieldWrapper label={(getFieldProp("full_name", "label") as string) || "Full name"} icon={User} required>
                  <Input value={form.full_name} onChange={e => handleChange("full_name", e.target.value)} data-testid="signup-fullname-input" required />
                </FieldWrapper>
                {isFieldVisible("job_title") && (
                  <FieldWrapper label={(getFieldProp("job_title", "label") as string) || "Job title"} icon={Briefcase} required={getFieldProp("job_title", "required") as boolean}>
                    <Input value={form.job_title} onChange={e => handleChange("job_title", e.target.value)} data-testid="signup-jobtitle-input" required={getFieldProp("job_title", "required") as boolean} />
                  </FieldWrapper>
                )}
                {isFieldVisible("company_name") && (
                  <FieldWrapper label={(getFieldProp("company_name", "label") as string) || "Company name"} icon={Building2} required={getFieldProp("company_name", "required") as boolean}>
                    <Input value={form.company_name} onChange={e => handleChange("company_name", e.target.value)} data-testid="signup-company-input" required={getFieldProp("company_name", "required") as boolean} />
                  </FieldWrapper>
                )}
                {isFieldVisible("phone") && (
                  <FieldWrapper label={(getFieldProp("phone", "label") as string) || "Phone"} icon={Phone} required={getFieldProp("phone", "required") as boolean}>
                    <Input value={form.phone} onChange={e => handleChange("phone", e.target.value)} data-testid="signup-phone-input" required={getFieldProp("phone", "required") as boolean} />
                  </FieldWrapper>
                )}
              </div>
              </div>

              {/* Section: Account Details */}
              <div>
                <div className="flex items-center gap-3 mb-4">
                  <div className="h-px flex-1 bg-slate-100" />
                  <span className="text-xs font-bold uppercase tracking-widest text-slate-400">Account details</span>
                  <div className="h-px flex-1 bg-slate-100" />
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <FieldWrapper label="Email address" icon={Mail} required>
                    <Input type="email" value={form.email} onChange={e => handleChange("email", e.target.value)} data-testid="signup-email-input" required />
                  </FieldWrapper>
                  <FieldWrapper label="Password" icon={Lock} required>
                    <Input type="password" value={form.password} onChange={e => handleChange("password", e.target.value)} data-testid="signup-password-input" required />
                  </FieldWrapper>
                </div>
              </div>

              {/* Custom extra fields */}
              {customFields.length > 0 && (
                <div>
                  <div className="flex items-center gap-3 mb-4">
                    <div className="h-px flex-1 bg-slate-100" />
                    <span className="text-xs font-bold uppercase tracking-widest text-slate-400">Additional details</span>
                    <div className="h-px flex-1 bg-slate-100" />
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2">
                    {customFields.map(field => (
                      <FieldWrapper key={field.id} label={`${field.label}${field.required ? " *" : ""}`} fullWidth={field.type === "textarea"}>
                        {field.type === "textarea" ? (
                          <Textarea value={extraFields[field.key] || ""} onChange={e => setExtraFields(p => ({ ...p, [field.key]: e.target.value }))} placeholder={field.placeholder} required={field.required} data-testid={`signup-extra-${field.key}`} />
                        ) : field.type === "select" ? (
                          <Select value={extraFields[field.key] || ""} onValueChange={v => setExtraFields(p => ({ ...p, [field.key]: v }))}>
                            <SelectTrigger data-testid={`signup-extra-${field.key}`}><SelectValue placeholder="Select…" /></SelectTrigger>
                            <SelectContent>
                              {(field.options || []).map(opt => {
                                const [label, val] = opt.includes("|") ? opt.split("|") : [opt, opt];
                                return <SelectItem key={val} value={val}>{label}</SelectItem>;
                              })}
                            </SelectContent>
                          </Select>
                        ) : (
                          <Input type={field.type} value={extraFields[field.key] || ""} onChange={e => setExtraFields(p => ({ ...p, [field.key]: e.target.value }))} placeholder={field.placeholder} required={field.required} data-testid={`signup-extra-${field.key}`} />
                        )}
                      </FieldWrapper>
                    ))}
                  </div>
                </div>
              )}

              {/* Section: Address */}
              <div>
                <div className="flex items-center gap-3 mb-4">
                  <div className="h-px flex-1 bg-slate-100" />
                  <span className="text-xs font-bold uppercase tracking-widest text-slate-400 flex items-center gap-1.5"><MapPin size={11} />Address</span>
                  <div className="h-px flex-1 bg-slate-100" />
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <FieldWrapper label="Street address" fullWidth>
                    <Input value={form.line1} onChange={e => handleChange("line1", e.target.value)} data-testid="signup-line1-input" required />
                  </FieldWrapper>
                  <FieldWrapper label="Address line 2 (optional)" fullWidth>
                    <Input value={form.line2} onChange={e => handleChange("line2", e.target.value)} data-testid="signup-line2-input" />
                  </FieldWrapper>
                  <FieldWrapper label="City">
                    <Input value={form.city} onChange={e => handleChange("city", e.target.value)} data-testid="signup-city-input" required />
                  </FieldWrapper>
                  <FieldWrapper label="State / Province">
                    {provinces.length > 0 ? (
                      <Select value={form.region} onValueChange={v => handleChange("region", v)}>
                        <SelectTrigger data-testid="signup-region-select"><SelectValue placeholder="Select province / state" /></SelectTrigger>
                        <SelectContent>
                          {provinces.map(p => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    ) : (
                      <Input value={form.region} onChange={e => handleChange("region", e.target.value)} data-testid="signup-region-input" required />
                    )}
                  </FieldWrapper>
                  <FieldWrapper label="Postal / ZIP">
                    <Input value={form.postal} onChange={e => handleChange("postal", e.target.value)} data-testid="signup-postal-input" required />
                  </FieldWrapper>
                  <FieldWrapper label="Country">
                    <Select value={form.country} onValueChange={v => handleChange("country", v)}>
                      <SelectTrigger data-testid="signup-country-select"><SelectValue placeholder="Select country" /></SelectTrigger>
                      <SelectContent>
                        {countries.map(c => (
                          <SelectItem key={c.value} value={c.value} data-testid={`signup-country-${c.value.toLowerCase()}`}>{c.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </FieldWrapper>
                </div>
              </div>

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
