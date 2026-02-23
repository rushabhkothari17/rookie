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
  const { register } = useAuth();
  const ws = useWebsite();
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
      });
      setVerificationCode(response.verification_code || "");
      localStorage.setItem("aa_signup_email", form.email);
      toast.success("Verification code sent (mocked). Proceed to verify.");
      navigate("/verify");
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Signup failed");
    } finally { setLoading(false); }
  };

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
        <div className="mt-6 text-sm text-slate-500">
          Already have access?{" "}
          <Link to="/login" className="text-blue-600" data-testid="signup-login-link">Sign in</Link>
        </div>
      </div>
    </div>
  );
}
