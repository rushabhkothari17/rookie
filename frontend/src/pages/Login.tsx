import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle, Building2, UserCircle } from "lucide-react";

export default function Login() {
  const navigate = useNavigate();
  const { login } = useAuth();

  // Partner Login state
  const [partnerCode, setPartnerCode] = useState("");
  const [partnerEmail, setPartnerEmail] = useState("");
  const [partnerPassword, setPartnerPassword] = useState("");

  // Customer Login state
  const [custPartnerCode, setCustPartnerCode] = useState("");
  const [custEmail, setCustEmail] = useState("");
  const [custPassword, setCustPassword] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handlePartnerLogin(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(partnerEmail, partnerPassword, partnerCode, "partner");
      navigate("/admin");
    } catch (err: any) {
      setError(err.message || "Login failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleCustomerLogin(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(custEmail, custPassword, custPartnerCode, "customer");
      navigate("/portal");
    } catch (err: any) {
      setError(err.message || "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen aa-bg flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md space-y-6">
        {/* Header */}
        <div className="text-center space-y-2">
          <div className="flex justify-center">
            <div className="h-12 w-12 rounded-xl flex items-center justify-center" style={{ backgroundColor: "var(--aa-primary)" }}>
              <span className="text-white text-xl font-bold">A</span>
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

        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
          <Tabs defaultValue="partner">
            <TabsList className="grid grid-cols-2 w-full mb-6">
              <TabsTrigger value="partner" className="gap-2" data-testid="partner-login-tab">
                <Building2 className="h-4 w-4" />
                Partner Login
              </TabsTrigger>
              <TabsTrigger value="customer" className="gap-2" data-testid="customer-login-tab">
                <UserCircle className="h-4 w-4" />
                Customer Login
              </TabsTrigger>
            </TabsList>

            {/* Partner Login */}
            <TabsContent value="partner">
              <form onSubmit={handlePartnerLogin} className="space-y-4" data-testid="partner-login-form">
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
                  <p className="text-xs text-slate-400">Enter your organization's partner code</p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="partner-email">Email</Label>
                  <Input
                    id="partner-email"
                    type="email"
                    placeholder="admin@example.com"
                    value={partnerEmail}
                    onChange={e => setPartnerEmail(e.target.value)}
                    required
                    data-testid="partner-email-input"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="partner-password">Password</Label>
                  <Input
                    id="partner-password"
                    type="password"
                    placeholder="••••••••"
                    value={partnerPassword}
                    onChange={e => setPartnerPassword(e.target.value)}
                    required
                    data-testid="partner-password-input"
                  />
                </div>
                <Button type="submit" className="w-full" disabled={loading} data-testid="partner-login-submit">
                  {loading ? "Signing in…" : "Sign In as Partner"}
                </Button>
              </form>
            </TabsContent>

            {/* Customer Login */}
            <TabsContent value="customer">
              <form onSubmit={handleCustomerLogin} className="space-y-4" data-testid="customer-login-form">
                <div className="space-y-2">
                  <Label htmlFor="cust-partner-code">Partner Code</Label>
                  <Input
                    id="cust-partner-code"
                    placeholder="e.g. automate-accounts"
                    value={custPartnerCode}
                    onChange={e => setCustPartnerCode(e.target.value)}
                    required
                    data-testid="customer-partner-code-input"
                  />
                  <p className="text-xs text-slate-400">Ask your service provider for the partner code</p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="cust-email">Email</Label>
                  <Input
                    id="cust-email"
                    type="email"
                    placeholder="you@example.com"
                    value={custEmail}
                    onChange={e => setCustEmail(e.target.value)}
                    required
                    data-testid="customer-email-input"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="cust-password">Password</Label>
                  <Input
                    id="cust-password"
                    type="password"
                    placeholder="••••••••"
                    value={custPassword}
                    onChange={e => setCustPassword(e.target.value)}
                    required
                    data-testid="customer-password-input"
                  />
                </div>
                <Button type="submit" className="w-full" disabled={loading} data-testid="customer-login-submit">
                  {loading ? "Signing in…" : "Sign In as Customer"}
                </Button>
              </form>
              <div className="mt-4 text-center text-sm text-slate-500">
                Don't have an account?{" "}
                <Link to="/register" className="font-medium hover:underline" style={{ color: "var(--aa-accent)" }}>
                  Register
                </Link>
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
}
