import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { 
  Link2, Link2Off, RefreshCw, CheckCircle, XCircle, Clock, Loader2, AlertCircle, 
  Power, PowerOff, Info, Mail, CreditCard, Building2, Database, DollarSign, Key,
  Globe, Shield, AlertTriangle
} from "lucide-react";

interface Integration {
  id: string;
  name: string;
  category: string;
  description: string;
  status: "connected" | "connecting" | "not_connected" | "failed" | "expired";
  is_active: boolean;
  connected_at?: string;
  last_refresh?: string;
  expires_at?: string;
  error_message?: string;
  has_credentials: boolean;
  can_connect: boolean;
  is_api_key: boolean;
  is_zoho: boolean;
  data_center?: string;
  api_key_label?: string;
  api_key_hint?: string;
}

interface DataCenter {
  id: string;
  name: string;
}

interface HealthReport {
  provider: string;
  name: string;
  status: "healthy" | "warning" | "expiring_soon" | "expired";
  message: string;
  needs_refresh: boolean;
  expires_at?: string;
}

const categoryIcons: Record<string, React.ReactNode> = {
  crm: <Database size={18} className="text-red-500" />,
  accounting: <DollarSign size={18} className="text-green-600" />,
  email: <Mail size={18} className="text-blue-500" />,
  payments: <CreditCard size={18} className="text-purple-600" />,
};

const providerIcons: Record<string, React.ReactNode> = {
  zoho_crm: <Database size={18} className="text-red-500" />,
  zoho_books: <DollarSign size={18} className="text-green-600" />,
  zoho_mail: <Mail size={18} className="text-yellow-600" />,
  stripe: <CreditCard size={18} className="text-purple-600" />,
  gocardless: <Building2 size={18} className="text-teal-600" />,
  gocardless_sandbox: <Building2 size={18} className="text-teal-400" />,
  resend: <Mail size={18} className="text-orange-500" />,
};

const statusConfig: Record<string, { icon: any; color: string; bg: string; border: string; label: string }> = {
  connected: { icon: CheckCircle, color: "text-emerald-500", bg: "bg-emerald-50", border: "border-emerald-200", label: "Connected" },
  connecting: { icon: Loader2, color: "text-blue-500", bg: "bg-blue-50", border: "border-blue-200", label: "Connecting..." },
  not_connected: { icon: Link2Off, color: "text-slate-400", bg: "bg-slate-50", border: "border-slate-200", label: "Not Connected" },
  failed: { icon: XCircle, color: "text-red-500", bg: "bg-red-50", border: "border-red-200", label: "Failed" },
  expired: { icon: AlertCircle, color: "text-amber-500", bg: "bg-amber-50", border: "border-amber-200", label: "Expired" },
};

const categoryLabels: Record<string, string> = {
  payments: "Payment Providers",
  email: "Email Providers",
  crm: "CRM",
  accounting: "Accounting",
};

export function IntegrationsOverview() {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [dataCenters, setDataCenters] = useState<DataCenter[]>([]);
  const [loading, setLoading] = useState(true);
  const [healthReport, setHealthReport] = useState<HealthReport[]>([]);
  
  // Action states
  const [connecting, setConnecting] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState<string | null>(null);
  const [disconnecting, setDisconnecting] = useState<string | null>(null);
  const [activating, setActivating] = useState<string | null>(null);
  
  // Dialog states
  const [showZohoDialog, setShowZohoDialog] = useState(false);
  const [zohoProvider, setZohoProvider] = useState<string | null>(null);
  const [selectedDC, setSelectedDC] = useState("us");
  
  const [showApiKeyDialog, setShowApiKeyDialog] = useState(false);
  const [apiKeyProvider, setApiKeyProvider] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [savingApiKey, setSavingApiKey] = useState(false);

  useEffect(() => {
    loadIntegrations();
    loadHealth();
    
    // Check URL for OAuth callback results
    const params = new URLSearchParams(window.location.search);
    if (params.get("oauth_success")) {
      toast.success(`${params.get("provider") || "Integration"} connected successfully!`);
      window.history.replaceState({}, "", window.location.pathname);
      loadIntegrations();
    } else if (params.get("oauth_error")) {
      const error = params.get("oauth_error");
      const desc = params.get("error_desc");
      toast.error(`Connection failed: ${desc || error}`);
      window.history.replaceState({}, "", window.location.pathname);
      loadIntegrations();
    }
  }, []);

  const loadIntegrations = async () => {
    setLoading(true);
    try {
      const res = await api.get("/oauth/integrations");
      setIntegrations(res.data.integrations || []);
      setDataCenters(res.data.zoho_data_centers || []);
    } catch {
      toast.error("Failed to load integrations");
    } finally {
      setLoading(false);
    }
  };

  const loadHealth = async () => {
    try {
      const res = await api.get("/oauth/health");
      setHealthReport(res.data.connections || []);
    } catch {
      // Ignore
    }
  };

  const handleConnect = async (provider: string, isZoho: boolean) => {
    if (isZoho) {
      setZohoProvider(provider);
      setSelectedDC("us");
      setShowZohoDialog(true);
      return;
    }
    
    setConnecting(provider);
    try {
      const res = await api.post(`/oauth/${provider}/connect`, {});
      const { authorization_url } = res.data;
      
      // Open OAuth popup
      const width = 600;
      const height = 700;
      const left = window.screenX + (window.outerWidth - width) / 2;
      const top = window.screenY + (window.outerHeight - height) / 2;
      
      window.open(
        authorization_url,
        `oauth_${provider}`,
        `width=${width},height=${height},left=${left},top=${top},popup=1`
      );
      
      // Poll for completion
      const pollInterval = setInterval(() => {
        loadIntegrations().then(() => {
          const int = integrations.find(i => i.id === provider);
          if (int && int.status !== "connecting") {
            clearInterval(pollInterval);
            setConnecting(null);
          }
        });
      }, 2000);
      
      // Timeout after 2 minutes
      setTimeout(() => {
        clearInterval(pollInterval);
        setConnecting(null);
        loadIntegrations();
      }, 120000);
      
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to start connection");
      setConnecting(null);
    }
  };

  const handleZohoConnect = async () => {
    if (!zohoProvider) return;
    
    setShowZohoDialog(false);
    setConnecting(zohoProvider);
    
    try {
      const res = await api.post(`/oauth/${zohoProvider}/connect`, { data_center: selectedDC });
      const { authorization_url } = res.data;
      
      const width = 600;
      const height = 700;
      const left = window.screenX + (window.outerWidth - width) / 2;
      const top = window.screenY + (window.outerHeight - height) / 2;
      
      window.open(
        authorization_url,
        `oauth_${zohoProvider}`,
        `width=${width},height=${height},left=${left},top=${top},popup=1`
      );
      
      // Poll for completion
      const pollInterval = setInterval(() => {
        loadIntegrations();
      }, 2000);
      
      setTimeout(() => {
        clearInterval(pollInterval);
        setConnecting(null);
        loadIntegrations();
      }, 120000);
      
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to start connection");
      setConnecting(null);
    }
    
    setZohoProvider(null);
  };

  const handleCancel = async (provider: string) => {
    try {
      await api.post(`/oauth/${provider}/cancel`);
      toast.success("Connection cancelled");
      setConnecting(null);
      loadIntegrations();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to cancel");
    }
  };

  const handleApiKeyConnect = (provider: string) => {
    setApiKeyProvider(provider);
    setApiKey("");
    setShowApiKeyDialog(true);
  };

  const handleSaveApiKey = async () => {
    if (!apiKeyProvider || !apiKey.trim()) return;
    
    setSavingApiKey(true);
    try {
      await api.post(`/oauth/${apiKeyProvider}/api-key`, { api_key: apiKey.trim() });
      toast.success("API key saved");
      setShowApiKeyDialog(false);
      setApiKeyProvider(null);
      setApiKey("");
      loadIntegrations();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to save API key");
    } finally {
      setSavingApiKey(false);
    }
  };

  const handleRefresh = async (provider: string) => {
    setRefreshing(provider);
    try {
      await api.post(`/oauth/${provider}/refresh`);
      toast.success("Connection refreshed");
      loadIntegrations();
      loadHealth();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to refresh");
    } finally {
      setRefreshing(null);
    }
  };

  const handleDisconnect = async (provider: string, name: string) => {
    if (!confirm(`Disconnect ${name}? This will remove the integration and disable it.`)) return;
    
    setDisconnecting(provider);
    try {
      await api.delete(`/oauth/${provider}/disconnect`);
      toast.success(`${name} disconnected`);
      loadIntegrations();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to disconnect");
    } finally {
      setDisconnecting(null);
    }
  };

  const handleActivate = async (provider: string) => {
    setActivating(provider);
    try {
      await api.post(`/oauth/${provider}/activate`);
      toast.success("Provider activated");
      loadIntegrations();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to activate");
    } finally {
      setActivating(null);
    }
  };

  const handleDeactivate = async (provider: string) => {
    setActivating(provider);
    try {
      await api.post(`/oauth/${provider}/deactivate`);
      toast.success("Provider deactivated");
      loadIntegrations();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to deactivate");
    } finally {
      setActivating(null);
    }
  };

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return null;
    try {
      return new Date(dateStr).toLocaleDateString("en-GB", { 
        day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" 
      });
    } catch {
      return dateStr;
    }
  };

  // Group integrations by category
  const groupedIntegrations = integrations.reduce((acc, int) => {
    if (!acc[int.category]) acc[int.category] = [];
    acc[int.category].push(int);
    return acc;
  }, {} as Record<string, Integration[]>);

  // Category order
  const categoryOrder = ["payments", "email", "crm", "accounting"];

  if (loading) {
    return <div className="text-slate-400 py-8 text-center">Loading integrations...</div>;
  }

  // Health alerts
  const healthAlerts = healthReport.filter(h => h.status !== "healthy");

  return (
    <div className="space-y-6" data-testid="integrations-overview">
      {/* Header */}
      <div>
        <h2 className="text-lg font-semibold text-slate-800">Connected Services</h2>
        <p className="text-xs text-slate-400">Manage all your integrations in one place</p>
      </div>

      {/* Health Alerts */}
      {healthAlerts.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
          <div className="flex items-start gap-2">
            <AlertTriangle size={16} className="text-amber-500 mt-0.5 shrink-0" />
            <div>
              <p className="text-sm font-medium text-amber-800">Connection Health Alerts</p>
              <div className="text-xs text-amber-700 mt-1 space-y-1">
                {healthAlerts.map(alert => (
                  <div key={alert.provider} className="flex items-center justify-between">
                    <span>{alert.name}: {alert.message}</span>
                    {alert.needs_refresh && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 px-2 text-xs text-amber-700"
                        onClick={() => handleRefresh(alert.provider)}
                        disabled={refreshing === alert.provider}
                      >
                        <RefreshCw size={12} className={`mr-1 ${refreshing === alert.provider ? "animate-spin" : ""}`} />
                        Refresh
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Info Banner */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 flex gap-2">
        <Info size={14} className="text-blue-500 mt-0.5 shrink-0" />
        <div className="text-xs text-blue-700">
          <p className="font-medium">One-Click Connection</p>
          <p>Click "Connect" to authorize access. For Zoho services, select your data center first.</p>
          <p className="mt-1 text-blue-600">
            <strong>OAuth Callback URL:</strong>{" "}
            <code className="bg-blue-100 px-1 py-0.5 rounded text-[11px]">
              {window.location.origin}/api/oauth/callback
            </code>
            <span className="text-blue-500 ml-1">(Configure this in your provider's developer console)</span>
          </p>
        </div>
      </div>

      {/* Integrations by Category */}
      {categoryOrder.map(category => {
        const categoryIntegrations = groupedIntegrations[category];
        if (!categoryIntegrations || categoryIntegrations.length === 0) return null;
        
        return (
          <div key={category}>
            <div className="flex items-center gap-2 mb-2">
              {categoryIcons[category]}
              <h3 className="text-sm font-medium text-slate-700">{categoryLabels[category] || category}</h3>
            </div>
            <div className="space-y-2">
              {categoryIntegrations.map(integration => {
                const config = statusConfig[integration.status] || statusConfig.not_connected;
                const StatusIcon = config.icon;
                const isConnecting = connecting === integration.id;
                const isRefreshing = refreshing === integration.id;
                const isDisconnecting = disconnecting === integration.id;
                const isActivating = activating === integration.id;
                const healthInfo = healthReport.find(h => h.provider === integration.id);
                
                return (
                  <div
                    key={integration.id}
                    className={`rounded-xl border p-4 ${config.bg} ${config.border}`}
                    data-testid={`integration-${integration.id}`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-3">
                        <div className="p-2 rounded-lg bg-white border border-slate-200 shadow-sm">
                          {providerIcons[integration.id] || categoryIcons[integration.category]}
                        </div>
                        <div>
                          <div className="flex items-center gap-2 flex-wrap">
                            <p className="font-medium text-slate-800">{integration.name}</p>
                            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${config.color} bg-white border ${config.border}`}>
                              <StatusIcon size={10} className={isConnecting ? "animate-spin" : ""} />
                              {isConnecting ? "Connecting..." : config.label}
                            </span>
                            {integration.is_active && integration.status === "connected" && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium text-emerald-600 bg-emerald-100 border border-emerald-200">
                                <Power size={10} /> Active
                              </span>
                            )}
                            {integration.is_zoho && integration.data_center && (
                              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] text-slate-500 bg-slate-100">
                                <Globe size={9} /> {integration.data_center.toUpperCase()}
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-slate-500 mt-0.5">{integration.description}</p>
                          
                          {/* Connection details */}
                          {integration.status === "connected" && (
                            <div className="text-[10px] text-slate-400 mt-2 space-y-0.5">
                              {integration.connected_at && <div>Connected: {formatDate(integration.connected_at)}</div>}
                              {healthInfo && healthInfo.status !== "healthy" && (
                                <div className={`${healthInfo.status === "expired" ? "text-red-500" : "text-amber-500"}`}>
                                  {healthInfo.message}
                                </div>
                              )}
                            </div>
                          )}
                          
                          {/* Error message */}
                          {integration.error_message && (
                            <div className="text-[10px] text-red-500 mt-2">
                              Error: {integration.error_message}
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        {integration.status === "connected" || integration.status === "expired" ? (
                          <>
                            {/* Activate/Deactivate for email and payments */}
                            {(integration.category === "email" || integration.category === "payments") && (
                              integration.is_active ? (
                                <Button
                                  variant="outline"
                                  size="sm"
                                  className="h-8 px-2 text-xs text-slate-500"
                                  onClick={() => handleDeactivate(integration.id)}
                                  disabled={isActivating}
                                  data-testid={`deactivate-${integration.id}`}
                                >
                                  <PowerOff size={12} className="mr-1" />
                                  Deactivate
                                </Button>
                              ) : (
                                <Button
                                  variant="outline"
                                  size="sm"
                                  className="h-8 px-2 text-xs text-emerald-600"
                                  onClick={() => handleActivate(integration.id)}
                                  disabled={isActivating}
                                  data-testid={`activate-${integration.id}`}
                                >
                                  <Power size={12} className="mr-1" />
                                  Activate
                                </Button>
                              )
                            )}
                            {!integration.is_api_key && (
                              <Button
                                variant="outline"
                                size="sm"
                                className="h-8 px-2 text-xs"
                                onClick={() => handleRefresh(integration.id)}
                                disabled={isRefreshing}
                                data-testid={`refresh-${integration.id}`}
                              >
                                <RefreshCw size={12} className={`mr-1 ${isRefreshing ? "animate-spin" : ""}`} />
                                Refresh
                              </Button>
                            )}
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 px-2 text-xs text-red-500 hover:text-red-600 hover:bg-red-50"
                              onClick={() => handleDisconnect(integration.id, integration.name)}
                              disabled={isDisconnecting}
                              data-testid={`disconnect-${integration.id}`}
                            >
                              <Link2Off size={12} className="mr-1" />
                              Disconnect
                            </Button>
                          </>
                        ) : integration.status === "connecting" ? (
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-8 px-2 text-xs text-slate-500"
                            onClick={() => handleCancel(integration.id)}
                            data-testid={`cancel-${integration.id}`}
                          >
                            <XCircle size={12} className="mr-1" />
                            Cancel
                          </Button>
                        ) : (
                          <Button
                            variant="default"
                            size="sm"
                            className="h-8 px-3 text-xs"
                            onClick={() => integration.is_api_key 
                              ? handleApiKeyConnect(integration.id)
                              : handleConnect(integration.id, integration.is_zoho)
                            }
                            disabled={!integration.can_connect || isConnecting}
                            data-testid={`connect-${integration.id}`}
                          >
                            {isConnecting ? (
                              <><Loader2 size={12} className="mr-1 animate-spin" /> Connecting...</>
                            ) : integration.is_api_key ? (
                              <><Key size={12} className="mr-1" /> Enter API Key</>
                            ) : (
                              <><Link2 size={12} className="mr-1" /> Connect</>
                            )}
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}

      {/* Zoho Data Center Dialog */}
      <Dialog open={showZohoDialog} onOpenChange={setShowZohoDialog}>
        <DialogContent className="max-w-sm" data-testid="zoho-dc-dialog">
          <DialogHeader>
            <DialogTitle>Select Zoho Data Center</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <p className="text-xs text-slate-500">
              Choose the data center where your Zoho account is hosted. This is usually based on your region when you signed up for Zoho.
            </p>
            <Select value={selectedDC} onValueChange={setSelectedDC}>
              <SelectTrigger data-testid="zoho-dc-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {dataCenters.map(dc => (
                  <SelectItem key={dc.id} value={dc.id}>
                    <div className="flex items-center gap-2">
                      <Globe size={14} />
                      {dc.name} ({dc.id.toUpperCase()})
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setShowZohoDialog(false)}>Cancel</Button>
              <Button onClick={handleZohoConnect} data-testid="zoho-dc-confirm">
                <Link2 size={14} className="mr-1" /> Connect
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* API Key Dialog */}
      <Dialog open={showApiKeyDialog} onOpenChange={setShowApiKeyDialog}>
        <DialogContent className="max-w-sm" data-testid="api-key-dialog">
          <DialogHeader>
            <DialogTitle>Enter API Key</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <p className="text-xs text-slate-500">
              Enter your API key from the provider's dashboard. This will be securely stored.
            </p>
            <Input
              type="password"
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              placeholder="Enter API key..."
              data-testid="api-key-input"
            />
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setShowApiKeyDialog(false)}>Cancel</Button>
              <Button onClick={handleSaveApiKey} disabled={savingApiKey || !apiKey.trim()} data-testid="api-key-save">
                {savingApiKey ? "Saving..." : "Save API Key"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
