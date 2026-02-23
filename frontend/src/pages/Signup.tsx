import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useAuth } from "@/contexts/AuthContext";
import { useWebsite } from "@/contexts/WebsiteContext";
import { parseSchema, type FormField } from "@/components/FormSchemaBuilder";
import api from "@/lib/api";

const STANDARD_KEYS = ["full_name", "email", "password", "company_name", "job_title", "phone", "country"];

const countries = [
  { value: "Canada", label: "Canada" },
  { value: "USA", label: "United States" },
  { value: "Other", label: "Other" },
];

export default function Signup() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const isPartnerMode = searchParams.get("type") === "partner";
  const { register } = useAuth();
  const ws = useWebsite();

  // Partner org signup state
  const [partnerOrg, setPartnerOrg] = useState({ name: "", code: "", admin_name: "", admin_email: "", admin_password: "" });
  const [partnerLoading, setPartnerLoading] = useState(false);

  // Customer signup state
  const [partnerCode, setPartnerCode] = useState("");
  const [form, setForm] = useState({
    full_name: "", job_title: "", company_name: "",
    email: "", phone: "", password: "",
    line1: "", line2: "", city: "", region: "", postal: "", country: "Canada",
  });
  const [extraFields, setExtraFields] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [verificationCode, setVerificationCode] = useState("");

  const handleChange = (key: string, value: string) => setForm(prev => ({ ...prev, [key]: value }));

  // Parse schema: show locked fields always, show others only if enabled
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
      toast.success("Verification code sent (mocked). Proceed to verify.");
      navigate("/verify");
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Signup failed");
    } finally { setLoading(false); }
  };

  const handlePartnerSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setPartnerLoading(true);
    try {
      await api.post("/auth/register-partner", partnerOrg);
      toast.success("Partner organization created! You can now log in.");
      navigate(`/login?partner_code=${partnerOrg.code}`);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Partner registration failed");
    } finally {
      setPartnerLoading(false);
    }
  };

  // Partner Org Registration Mode
  if (isPartnerMode) {
    return (
      <div className="min-h-screen aa-bg flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-md space-y-6">
          <div className="text-center">
            <h1 className="text-2xl font-bold text-slate-900">Register as Partner</h1>
            <p className="text-sm text-slate-500 mt-1">Create a new partner organization</p>
          </div>
          <form onSubmit={handlePartnerSignup} className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-4" data-testid="partner-signup-form">
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">Organization Name</label>
              <Input placeholder="Acme Accounting" value={partnerOrg.name} onChange={e => setPartnerOrg(p => ({ ...p, name: e.target.value }))} required data-testid="partner-org-name" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">Partner Code (login slug)</label>
              <Input placeholder="acme-accounting" value={partnerOrg.code}
                onChange={e => setPartnerOrg(p => ({ ...p, code: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-") }))}
                required data-testid="partner-org-code" />
              <p className="text-xs text-slate-400">Unique code used at login. Lowercase letters, numbers, hyphens only.</p>
            </div>
            <div className="border-t border-slate-100 pt-3 space-y-1">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Super Admin Account</p>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">Admin Full Name</label>
              <Input placeholder="Jane Smith" value={partnerOrg.admin_name} onChange={e => setPartnerOrg(p => ({ ...p, admin_name: e.target.value }))} required data-testid="partner-admin-name" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">Admin Email</label>
              <Input type="email" placeholder="admin@acme.com" value={partnerOrg.admin_email} onChange={e => setPartnerOrg(p => ({ ...p, admin_email: e.target.value }))} required data-testid="partner-admin-email" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">Password</label>
              <Input type="password" placeholder="••••••••" value={partnerOrg.admin_password} onChange={e => setPartnerOrg(p => ({ ...p, admin_password: e.target.value }))} required data-testid="partner-admin-password" />
            </div>
            <Button type="submit" className="w-full" disabled={partnerLoading} data-testid="partner-signup-submit">
              {partnerLoading ? "Creating…" : "Create Partner Organization"}
            </Button>
            <p className="text-center text-sm text-slate-500">
              Already have an account?{" "}
              <Link to="/login" className="font-medium hover:underline" style={{ color: "var(--aa-accent)" }}>Sign in</Link>
            </p>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen grid place-items-center bg-slate-50 grid-rhythm" data-testid="signup-page">
      <div className="glass-card w-full max-w-3xl rounded-2xl p-8">
        <div className="space-y-2">
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Account setup</p>
          <h1 className="text-3xl font-semibold text-slate-900" data-testid="register-title">
            {ws.register_title || "Create your portal access"}
          </h1>
          {(ws.register_subtitle) && (
            <p className="text-sm text-slate-500" data-testid="register-subtitle">{ws.register_subtitle}</p>
          )}
        </div>
        <form className="mt-6 grid gap-4 sm:grid-cols-2" onSubmit={handleSubmit}>
          {/* Partner Code */}
          <div className="space-y-2 sm:col-span-2">
            <label className="text-sm text-slate-600 font-medium">Partner Code</label>
            <Input placeholder="e.g. automate-accounts" value={partnerCode} onChange={e => setPartnerCode(e.target.value)} required data-testid="signup-partner-code-input" />
            <p className="text-xs text-slate-400">Your service provider's partner code</p>
          </div>
          {/* Full Name - always shown (locked) */}
          <div className="space-y-2">
            <label className="text-sm text-slate-600">{(getFieldProp("full_name", "label") as string) || "Full name"}</label>
            <Input value={form.full_name} onChange={e => handleChange("full_name", e.target.value)} data-testid="signup-fullname-input" required />
          </div>

          {/* Job Title */}
          {isFieldVisible("job_title") && (
            <div className="space-y-2">
              <label className="text-sm text-slate-600">{(getFieldProp("job_title", "label") as string) || "Job title"}</label>
              <Input value={form.job_title} onChange={e => handleChange("job_title", e.target.value)} data-testid="signup-jobtitle-input" required={getFieldProp("job_title", "required") as boolean} />
            </div>
          )}

          {/* Company Name */}
          {isFieldVisible("company_name") && (
            <div className="space-y-2">
              <label className="text-sm text-slate-600">{(getFieldProp("company_name", "label") as string) || "Company name"}</label>
              <Input value={form.company_name} onChange={e => handleChange("company_name", e.target.value)} data-testid="signup-company-input" required={getFieldProp("company_name", "required") as boolean} />
            </div>
          )}

          {/* Email - always shown (locked) */}
          <div className="space-y-2">
            <label className="text-sm text-slate-600">Email</label>
            <Input type="email" value={form.email} onChange={e => handleChange("email", e.target.value)} data-testid="signup-email-input" required />
          </div>

          {/* Phone */}
          {isFieldVisible("phone") && (
            <div className="space-y-2">
              <label className="text-sm text-slate-600">{(getFieldProp("phone", "label") as string) || "Phone"}</label>
              <Input value={form.phone} onChange={e => handleChange("phone", e.target.value)} data-testid="signup-phone-input" required={getFieldProp("phone", "required") as boolean} />
            </div>
          )}

          {/* Password - always shown (locked) */}
          <div className="space-y-2">
            <label className="text-sm text-slate-600">Password</label>
            <Input type="password" value={form.password} onChange={e => handleChange("password", e.target.value)} data-testid="signup-password-input" required />
          </div>

          {/* Custom extra fields from schema */}
          {customFields.map(field => (
            <div key={field.id} className={`space-y-2 ${field.type === "textarea" ? "sm:col-span-2" : ""}`}>
              <label className="text-sm text-slate-600">{field.label}{field.required && " *"}</label>
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
            </div>
          ))}

          {/* Address section */}
          <div className="space-y-2 sm:col-span-2">
            <label className="text-sm text-slate-600">Street address</label>
            <Input value={form.line1} onChange={e => handleChange("line1", e.target.value)} data-testid="signup-line1-input" required />
          </div>
          <div className="space-y-2 sm:col-span-2">
            <label className="text-sm text-slate-600">Address line 2</label>
            <Input value={form.line2} onChange={e => handleChange("line2", e.target.value)} data-testid="signup-line2-input" />
          </div>
          <div className="space-y-2">
            <label className="text-sm text-slate-600">City</label>
            <Input value={form.city} onChange={e => handleChange("city", e.target.value)} data-testid="signup-city-input" required />
          </div>
          <div className="space-y-2">
            <label className="text-sm text-slate-600">State / Province</label>
            <Input value={form.region} onChange={e => handleChange("region", e.target.value)} data-testid="signup-region-input" required />
          </div>
          <div className="space-y-2">
            <label className="text-sm text-slate-600">Postal / ZIP</label>
            <Input value={form.postal} onChange={e => handleChange("postal", e.target.value)} data-testid="signup-postal-input" required />
          </div>

          {/* Country - always shown (locked) */}
          <div className="space-y-2">
            <label className="text-sm text-slate-600">Country</label>
            <Select value={form.country} onValueChange={v => handleChange("country", v)}>
              <SelectTrigger data-testid="signup-country-select"><SelectValue placeholder="Select country" /></SelectTrigger>
              <SelectContent>
                {countries.map(c => (
                  <SelectItem key={c.value} value={c.value} data-testid={`signup-country-${c.value.toLowerCase()}`}>{c.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="sm:col-span-2">
            <Button type="submit" className="w-full bg-slate-900 hover:bg-slate-800" disabled={loading} data-testid="signup-submit-button">
              {loading ? "Creating account..." : "Create account"}
            </Button>
          </div>
        </form>
        {verificationCode && (
          <div className="mt-4 text-xs text-slate-500" data-testid="signup-verification-code">
            Mocked verification code: {verificationCode}
          </div>
        )}
        <div className="mt-6 space-y-1 text-sm text-slate-500">
          <div>Already have access?{" "}
            <Link to="/login" className="font-medium hover:underline" style={{ color: "var(--aa-accent)" }} data-testid="signup-login-link">Sign in</Link>
          </div>
          <div>Registering a new organization?{" "}
            <Link to="/signup?type=partner" className="font-medium hover:underline" style={{ color: "var(--aa-accent)" }} data-testid="partner-signup-link">Sign up as a partner</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
