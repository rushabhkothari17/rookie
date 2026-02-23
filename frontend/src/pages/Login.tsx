import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle } from "lucide-react";

export default function Login() {
  const navigate = useNavigate();
  const { login } = useAuth();

  const [partnerCode, setPartnerCode] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      // Unified login — backend auto-detects role and routes accordingly
      const result = await login(email, password, partnerCode);
      // AuthContext sets user; redirect based on role
      navigate(result?.is_admin ? "/admin" : "/portal");
    } catch (err: any) {
      setError(err.message || "Invalid credentials. Check your partner code, email, and password.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen aa-bg flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm space-y-6">
        {/* Logo / Brand */}
        <div className="text-center space-y-2">
          <div className="flex justify-center">
            <div className="h-12 w-12 rounded-xl flex items-center justify-center text-white text-xl font-bold" style={{ backgroundColor: "var(--aa-primary)" }}>
              A
            </div>
          </div>
          <h1 className="text-2xl font-bold text-slate-900">Welcome back</h1>
          <p className="text-sm text-slate-500">Sign in to your account</p>
        </div>

        {error && (
          <Alert variant="destructive" data-testid="login-error">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <form onSubmit={handleSubmit} className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-4" data-testid="login-form">
          <div className="space-y-2">
            <Label htmlFor="partner-code">Partner Code</Label>
            <Input
              id="partner-code"
              placeholder="e.g. automate-accounts"
              value={partnerCode}
              onChange={e => setPartnerCode(e.target.value)}
              required
              data-testid="partner-code-input"
            />
            <p className="text-xs text-slate-400">Your organization's unique partner code</p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              data-testid="login-email-input"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
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

          <Button type="submit" className="w-full" disabled={loading} data-testid="login-submit-button">
            {loading ? "Signing in…" : "Sign In"}
          </Button>

          <div className="pt-2 border-t border-slate-100 space-y-2 text-center text-sm text-slate-500">
            <div>
              New customer?{" "}
              <Link to="/register" className="font-medium hover:underline" style={{ color: "var(--aa-accent)" }} data-testid="register-customer-link">
                Register as a customer
              </Link>
            </div>
            <div>
              New partner org?{" "}
              <Link to="/register?type=partner" className="font-medium hover:underline" style={{ color: "var(--aa-accent)" }} data-testid="register-partner-link">
                Sign up as a partner
              </Link>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
