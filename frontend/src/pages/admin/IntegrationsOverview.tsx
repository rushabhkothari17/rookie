import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { OAuthIntegrationTile } from "@/components/admin/OAuthIntegrationTile";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { 
  DollarSign, Database, Mail, CreditCard, Building2, Info, Key
} from "lucide-react";

interface Integration {
  id: string;
  name: string;
  status: "connected" | "connecting" | "not_connected" | "failed" | "expired";
  connected_at?: string;
  last_refresh?: string;
  expires_at?: string;
  error_message?: string;
  has_credentials: boolean;
  can_connect: boolean;
}

// Icons for each provider
const providerIcons: Record<string, React.ReactNode> = {
  zoho_crm: <Database size={18} className="text-red-500" />,
  zoho_books: <DollarSign size={18} className="text-green-600" />,
  zoho_mail: <Mail size={18} className="text-blue-500" />,
  stripe: <CreditCard size={18} className="text-purple-600" />,
  stripe_test: <CreditCard size={18} className="text-purple-400" />,
  gocardless: <Building2 size={18} className="text-emerald-600" />,
  gocardless_sandbox: <Building2 size={18} className="text-emerald-400" />,
};

const providerDescriptions: Record<string, string> = {
  zoho_crm: "Sync customers, orders, and subscriptions with Zoho CRM",
  zoho_books: "Sync invoices, payments, and financial data with Zoho Books",
  zoho_mail: "Send transactional emails via Zoho Mail",
  stripe: "Process payments via Stripe (Live Mode)",
  stripe_test: "Test payments via Stripe (Test Mode)",
  gocardless: "Process Direct Debit payments via GoCardless",
  gocardless_sandbox: "Test Direct Debit payments in GoCardless Sandbox",
};

const providerCategories: Record<string, string[]> = {
  "CRM": ["zoho_crm"],
  "Accounting": ["zoho_books"],
  "Payments": ["stripe", "stripe_test", "gocardless", "gocardless_sandbox"],
  "Email": ["zoho_mail"],
};

export function IntegrationsOverview() {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [loading, setLoading] = useState(true);
  
  // Resend API key (non-OAuth)
  const [resendKey, setResendKey] = useState("");
  const [savingResend, setSavingResend] = useState(false);

  useEffect(() => {
    loadIntegrations();
    
    // Check URL for OAuth callback results
    const params = new URLSearchParams(window.location.search);
    if (params.get("oauth_success")) {
      toast.success(`${params.get("provider") || "Integration"} connected successfully!`);
      // Clean URL
      window.history.replaceState({}, "", window.location.pathname);
    } else if (params.get("oauth_error")) {
      toast.error(`OAuth error: ${params.get("oauth_error")}`);
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, []);

  const loadIntegrations = async () => {
    setLoading(true);
    try {
      const res = await api.get("/oauth/integrations");
      setIntegrations(res.data.integrations || []);
    } catch {
      toast.error("Failed to load integrations");
    } finally {
      setLoading(false);
    }
  };

  const saveResendKey = async () => {
    setSavingResend(true);
    try {
      await api.post("/admin/settings/resend_api_key", { value: resendKey });
      toast.success("Resend API key saved");
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to save");
    } finally {
      setSavingResend(false);
    }
  };

  if (loading) {
    return <div className="text-slate-400 py-8 text-center">Loading integrations...</div>;
  }

  return (
    <div className="space-y-6" data-testid="integrations-overview">
      {/* Header */}
      <div>
        <h2 className="text-lg font-semibold text-slate-800">Integrations</h2>
        <p className="text-xs text-slate-400">Connect your favorite services with a single click</p>
      </div>

      {/* Info Banner */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 flex gap-2">
        <Info size={14} className="text-blue-500 mt-0.5 shrink-0" />
        <div className="text-xs text-blue-700">
          <p className="font-medium">One-Click OAuth Connection</p>
          <p>Click "Connect" to authorize access. You'll be redirected to the service's login page, then back here once authorized.</p>
        </div>
      </div>

      {/* OAuth Integrations by Category */}
      {Object.entries(providerCategories).map(([category, providerIds]) => {
        const categoryIntegrations = integrations.filter(i => providerIds.includes(i.id));
        if (categoryIntegrations.length === 0) return null;
        
        return (
          <div key={category}>
            <h3 className="text-sm font-medium text-slate-700 mb-2">{category}</h3>
            <div className="space-y-2">
              {categoryIntegrations.map(integration => (
                <OAuthIntegrationTile
                  key={integration.id}
                  provider={integration.id}
                  name={integration.name}
                  description={providerDescriptions[integration.id] || ""}
                  icon={providerIcons[integration.id] || <Database size={18} />}
                  status={integration.status as any}
                  connectedAt={integration.connected_at}
                  lastRefresh={integration.last_refresh}
                  expiresAt={integration.expires_at}
                  errorMessage={integration.error_message}
                  canConnect={integration.can_connect}
                  onStatusChange={loadIntegrations}
                />
              ))}
            </div>
          </div>
        );
      })}

      {/* Resend (API Key based - not OAuth) */}
      <div>
        <h3 className="text-sm font-medium text-slate-700 mb-2">Email (API Key)</h3>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="flex items-start gap-3">
            <div className="p-2 rounded-lg bg-orange-100">
              <Mail size={18} className="text-orange-600" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <p className="font-medium text-slate-800">Resend</p>
                <span className="text-[10px] bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded">API Key</span>
              </div>
              <p className="text-xs text-slate-500 mb-3">Send transactional emails via Resend. Requires API key from resend.com</p>
              <div className="flex gap-2">
                <Input
                  type="password"
                  value={resendKey}
                  onChange={e => setResendKey(e.target.value)}
                  placeholder="re_xxxxxxxxxxxx"
                  className="flex-1 h-8 text-xs"
                  data-testid="resend-api-key-input"
                />
                <Button
                  size="sm"
                  className="h-8"
                  onClick={saveResendKey}
                  disabled={savingResend || !resendKey}
                  data-testid="resend-save-btn"
                >
                  <Key size={12} className="mr-1" />
                  {savingResend ? "Saving..." : "Save Key"}
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Future: Gmail & Outlook */}
      <div>
        <h3 className="text-sm font-medium text-slate-700 mb-2">Coming Soon</h3>
        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 opacity-60">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-red-100">
                <Mail size={18} className="text-red-500" />
              </div>
              <div>
                <p className="font-medium text-slate-800">Gmail</p>
                <p className="text-xs text-slate-400">Send emails via Gmail API</p>
              </div>
            </div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 opacity-60">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-blue-100">
                <Mail size={18} className="text-blue-600" />
              </div>
              <div>
                <p className="font-medium text-slate-800">Outlook</p>
                <p className="text-xs text-slate-400">Send emails via Microsoft Graph</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
