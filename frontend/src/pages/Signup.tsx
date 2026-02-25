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
import { User, Building2, Mail, Lock, Phone, Briefcase, MapPin, ChevronRight, CheckCircle2, ChevronLeft } from "lucide-react";

const STANDARD_KEYS = ["full_name", "email", "password", "company_name", "job_title", "phone", "country"];

const countries = [
  { value: "Canada", label: "Canada" },
  { value: "USA", label: "United States" },
  { value: "Other", label: "Other" },
];

function FieldWrapper({ label, icon: Icon, children, fullWidth = false }: {
  label: string; icon?: any; children: React.ReactNode; fullWidth?: boolean;
}) {
  return (
    <div className={`space-y-1.5 ${fullWidth ? "sm:col-span-2" : ""}`}>
      <label className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
        {Icon && <Icon size={12} className="text-slate-400" />}
        {label}
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

  const [partnerOrg, setPartnerOrg] = useState({ name: "", code: "", admin_name: "", admin_email: "", admin_password: "" });
  const [partnerLoading, setPartnerLoading] = useState(false);

  const [form, setForm] = useState({
    full_name: "", job_title: "", company_name: "",
    email: "", phone: "", password: "",
    line1: "", line2: "", city: "", region: "", postal: "", country: "Canada",
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
      await api.post("/auth/register-partner", partnerOrg);
      toast.success("Organization created! You can now log in.");
      navigate("/login");
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Registration failed");
    } finally {
      setPartnerLoading(false);
    }
  };

  const storeName = ws.store_name || "Portal";

  // Partner mode
  if (isPartnerMode) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4" data-testid="partner-signup-page">
        <div className="w-full max-w-md">
          <div className="rounded-2xl border border-slate-200 bg-white shadow-sm p-8">
            <div className="mb-6">
              <p className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">Partner registration</p>
              <h1 className="text-2xl font-bold text-slate-900">Create your organization</h1>
              <p className="text-sm text-slate-500 mt-1">Set up your partner workspace to get started.</p>
            </div>
            <form className="space-y-4" onSubmit={handlePartnerSubmit}>
              <FieldWrapper label="Organization name" icon={Building2}>
                <Input placeholder="Acme Corp" value={partnerOrg.name} onChange={e => setPartnerOrg(p => ({ ...p, name: e.target.value }))} required data-testid="partner-org-name" />
              </FieldWrapper>
              <FieldWrapper label="Partner code" icon={ChevronRight}>
                <Input placeholder="acme-corp" value={partnerOrg.code} onChange={e => setPartnerOrg(p => ({ ...p, code: e.target.value }))} required data-testid="partner-org-code" />
                <p className="text-xs text-slate-400">Lowercase letters and hyphens only</p>
              </FieldWrapper>
              <FieldWrapper label="Admin name" icon={User}>
                <Input placeholder="Jane Smith" value={partnerOrg.admin_name} onChange={e => setPartnerOrg(p => ({ ...p, admin_name: e.target.value }))} required data-testid="partner-admin-name" />
              </FieldWrapper>
              <FieldWrapper label="Admin email" icon={Mail}>
                <Input type="email" placeholder="jane@acmecorp.com" value={partnerOrg.admin_email} onChange={e => setPartnerOrg(p => ({ ...p, admin_email: e.target.value }))} required data-testid="partner-admin-email" />
              </FieldWrapper>
              <FieldWrapper label="Admin password" icon={Lock}>
                <Input type="password" value={partnerOrg.admin_password} onChange={e => setPartnerOrg(p => ({ ...p, admin_password: e.target.value }))} required data-testid="partner-admin-password" />
              </FieldWrapper>
              <Button type="submit" className="w-full h-11 font-semibold" disabled={partnerLoading} data-testid="partner-signup-submit" style={{ backgroundColor: "var(--aa-primary)" }}>
                {partnerLoading ? "Creating…" : "Create organization"}
              </Button>
            </form>
            <p className="mt-5 text-center text-sm text-slate-500">
              Already have an account?{" "}
              <Link to="/login" className="font-semibold hover:underline" style={{ color: "var(--aa-accent)" }}>Sign in</Link>
            </p>
          </div>
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
      <div className="flex-1 bg-slate-50 flex items-start justify-center py-10 px-4 overflow-y-auto">
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
                <div className="grid gap-4 sm:grid-cols-2">
                  <FieldWrapper label={(getFieldProp("full_name", "label") as string) || "Full name"} icon={User}>
                    <Input value={form.full_name} onChange={e => handleChange("full_name", e.target.value)} data-testid="signup-fullname-input" required />
                  </FieldWrapper>
                  {isFieldVisible("job_title") && (
                    <FieldWrapper label={(getFieldProp("job_title", "label") as string) || "Job title"} icon={Briefcase}>
                      <Input value={form.job_title} onChange={e => handleChange("job_title", e.target.value)} data-testid="signup-jobtitle-input" required={getFieldProp("job_title", "required") as boolean} />
                    </FieldWrapper>
                  )}
                  {isFieldVisible("company_name") && (
                    <FieldWrapper label={(getFieldProp("company_name", "label") as string) || "Company name"} icon={Building2}>
                      <Input value={form.company_name} onChange={e => handleChange("company_name", e.target.value)} data-testid="signup-company-input" required={getFieldProp("company_name", "required") as boolean} />
                    </FieldWrapper>
                  )}
                  {isFieldVisible("phone") && (
                    <FieldWrapper label={(getFieldProp("phone", "label") as string) || "Phone"} icon={Phone}>
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
                  <FieldWrapper label="Email address" icon={Mail}>
                    <Input type="email" value={form.email} onChange={e => handleChange("email", e.target.value)} data-testid="signup-email-input" required />
                  </FieldWrapper>
                  <FieldWrapper label="Password" icon={Lock}>
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
                    <Input value={form.region} onChange={e => handleChange("region", e.target.value)} data-testid="signup-region-input" required />
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
