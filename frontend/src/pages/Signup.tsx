import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useAuth } from "@/contexts/AuthContext";

const countries = [
  { value: "Canada", label: "Canada" },
  { value: "USA", label: "United States" },
  { value: "Other", label: "Other" },
];

export default function Signup() {
  const navigate = useNavigate();
  const { register } = useAuth();
  const [form, setForm] = useState({
    full_name: "",
    job_title: "",
    company_name: "",
    email: "",
    phone: "",
    password: "",
    line1: "",
    line2: "",
    city: "",
    region: "",
    postal: "",
    country: "Canada",
  });
  const [loading, setLoading] = useState(false);
  const [verificationCode, setVerificationCode] = useState("");

  const handleChange = (key: string, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    try {
      const response = await register({
        full_name: form.full_name,
        job_title: form.job_title,
        company_name: form.company_name,
        email: form.email,
        phone: form.phone,
        password: form.password,
        address: {
          line1: form.line1,
          line2: form.line2,
          city: form.city,
          region: form.region,
          postal: form.postal,
          country: form.country,
        },
      });
      setVerificationCode(response.verification_code || "");
      localStorage.setItem("aa_signup_email", form.email);
      toast.success("Verification code sent (mocked). Proceed to verify.");
      navigate("/verify");
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Signup failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid place-items-center bg-slate-50 grid-rhythm" data-testid="signup-page">
      <div className="glass-card w-full max-w-3xl rounded-2xl p-8">
        <div className="space-y-2">
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Account setup</p>
          <h1 className="text-3xl font-semibold text-slate-900">Create your portal access</h1>
          <p className="text-sm text-slate-500">We'll use this info to configure pricing and currency.</p>
        </div>
        <form className="mt-6 grid gap-4 sm:grid-cols-2" onSubmit={handleSubmit}>
          <div className="space-y-2">
            <label className="text-sm text-slate-600">Full name</label>
            <Input value={form.full_name} onChange={(e) => handleChange("full_name", e.target.value)} data-testid="signup-fullname-input" required />
          </div>
          <div className="space-y-2">
            <label className="text-sm text-slate-600">Job title</label>
            <Input value={form.job_title} onChange={(e) => handleChange("job_title", e.target.value)} data-testid="signup-jobtitle-input" required />
          </div>
          <div className="space-y-2">
            <label className="text-sm text-slate-600">Company name</label>
            <Input value={form.company_name} onChange={(e) => handleChange("company_name", e.target.value)} data-testid="signup-company-input" required />
          </div>
          <div className="space-y-2">
            <label className="text-sm text-slate-600">Email</label>
            <Input type="email" value={form.email} onChange={(e) => handleChange("email", e.target.value)} data-testid="signup-email-input" required />
          </div>
          <div className="space-y-2">
            <label className="text-sm text-slate-600">Phone</label>
            <Input value={form.phone} onChange={(e) => handleChange("phone", e.target.value)} data-testid="signup-phone-input" required />
          </div>
          <div className="space-y-2">
            <label className="text-sm text-slate-600">Password</label>
            <Input type="password" value={form.password} onChange={(e) => handleChange("password", e.target.value)} data-testid="signup-password-input" required />
          </div>
          <div className="space-y-2 sm:col-span-2">
            <label className="text-sm text-slate-600">Street address</label>
            <Input value={form.line1} onChange={(e) => handleChange("line1", e.target.value)} data-testid="signup-line1-input" required />
          </div>
          <div className="space-y-2 sm:col-span-2">
            <label className="text-sm text-slate-600">Address line 2</label>
            <Input value={form.line2} onChange={(e) => handleChange("line2", e.target.value)} data-testid="signup-line2-input" />
          </div>
          <div className="space-y-2">
            <label className="text-sm text-slate-600">City</label>
            <Input value={form.city} onChange={(e) => handleChange("city", e.target.value)} data-testid="signup-city-input" required />
          </div>
          <div className="space-y-2">
            <label className="text-sm text-slate-600">State / Province</label>
            <Input value={form.region} onChange={(e) => handleChange("region", e.target.value)} data-testid="signup-region-input" required />
          </div>
          <div className="space-y-2">
            <label className="text-sm text-slate-600">Postal / ZIP</label>
            <Input value={form.postal} onChange={(e) => handleChange("postal", e.target.value)} data-testid="signup-postal-input" required />
          </div>
          <div className="space-y-2">
            <label className="text-sm text-slate-600">Country</label>
            <Select value={form.country} onValueChange={(value) => handleChange("country", value)}>
              <SelectTrigger data-testid="signup-country-select">
                <SelectValue placeholder="Select country" />
              </SelectTrigger>
              <SelectContent>
                {countries.map((country) => (
                  <SelectItem key={country.value} value={country.value} data-testid={`signup-country-${country.value.toLowerCase()}`}>
                    {country.label}
                  </SelectItem>
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
          <Link to="/login" className="text-blue-600" data-testid="signup-login-link">
            Sign in
          </Link>
        </div>
      </div>
    </div>
  );
}
