import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { CheckCircle, XCircle, RefreshCw, X, Info, ExternalLink, Database, Pencil, DollarSign, ArrowRight, Plus, Trash2, Power, Clock } from "lucide-react";

interface FinanceStatus {
  zoho_books: {
    is_configured: boolean;
    is_validated: boolean;
    datacenter: string | null;
    organization_id: string | null;
    validated_at: string | null;
  };
  quickbooks: {
    is_configured: boolean;
    is_validated: boolean;
    status: string;
  };
}

interface AccountMapping {
  id: string;
  webapp_entity: string;
  zoho_module: string;
  field_mappings: Array<{ webapp_field: string; zoho_field: string }>;
  sync_enabled: boolean;
}

function ProviderTile({
  name,
  description,
  icon: Icon,
  iconBgClass,
  iconClass,
  isConnected,
  isComingSoon,
  datacenter,
  onClick
}: {
  name: string;
  description: string;
  icon: any;
  iconBgClass: string;
  iconClass: string;
  isConnected: boolean;
  isComingSoon?: boolean;
  datacenter?: string | null;
  onClick: () => void;
}) {
  if (isComingSoon) {
    return (
      <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/50 p-4 flex items-center justify-between opacity-60">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-slate-100">
            <Icon size={18} className="text-slate-400" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-500">{name}</p>
            <p className="text-xs text-slate-400 mt-0.5">{description}</p>
          </div>
        </div>
        <Badge variant="outline" className="text-slate-400">Coming Soon</Badge>
      </div>
    );
  }

  return (
    <div
      className={`rounded-xl border p-4 flex items-center justify-between cursor-pointer hover:border-slate-300 transition-colors ${isConnected ? "border-emerald-300 bg-emerald-50/50" : "border-slate-200 bg-white"}`}
      onClick={onClick}
      data-testid={`finance-provider-tile-${name.toLowerCase().replace(/\s/g, '-')}`}
    >
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded-lg ${iconBgClass}`}>
          <Icon size={18} className={iconClass} />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium text-slate-800">{name}</p>
            {isConnected && <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-100 px-1.5 py-0.5 rounded">CONNECTED</span>}
          </div>
          <p className="text-xs text-slate-400 mt-0.5">{description}</p>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <span className={`text-xs px-2 py-0.5 rounded-full ${isConnected ? "text-emerald-700 bg-emerald-50" : "text-slate-500 bg-slate-100"}`}>
          {isConnected ? `Connected${datacenter ? ` (${datacenter})` : ''}` : "Not Connected"}
        </span>
        <Pencil size={14} className="text-slate-400" />
      </div>
    </div>
  );
}

export function FinanceTab() {
  const [status, setStatus] = useState<FinanceStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [zohoBooksOpen, setZohoBooksOpen] = useState(false);
  
  // Zoho Books form state
  const [datacenter, setDatacenter] = useState("US");
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [accessToken, setAccessToken] = useState("");
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  
  // Mappings
  const [mappings, setMappings] = useState<AccountMapping[]>([]);
  const [showMappings, setShowMappings] = useState(false);
  
  // Sync history
  const [syncHistory, setSyncHistory] = useState<any[]>([]);

  useEffect(() => {
    loadStatus();
  }, []);

  const loadStatus = async () => {
    setLoading(true);
    try {
      const res = await api.get("/admin/finance/status");
      setStatus(res.data);
      if (res.data.zoho_books?.datacenter) {
        setDatacenter(res.data.zoho_books.datacenter);
      }
    } catch {
      // Ignore
    } finally {
      setLoading(false);
    }
  };

  const loadMappings = async () => {
    try {
      const res = await api.get("/admin/finance/zoho-books/account-mappings");
      setMappings(res.data.mappings || []);
    } catch {
      // Ignore
    }
  };

  const loadSyncHistory = async () => {
    try {
      const res = await api.get("/admin/finance/sync-history");
      setSyncHistory(res.data.jobs || []);
    } catch {
      // Ignore
    }
  };

  const saveCredentials = async () => {
    if (!clientId || !clientSecret) {
      toast.error("Client ID and Secret are required");
      return;
    }
    setSaving(true);
    try {
      await api.post("/admin/finance/zoho-books/save-credentials", {
        client_id: clientId,
        client_secret: clientSecret,
        datacenter
      });
      toast.success("Credentials saved");
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const validateConnection = async () => {
    if (!accessToken) {
      toast.error("Access token required");
      return;
    }
    setValidating(true);
    try {
      const res = await api.post("/admin/finance/zoho-books/validate", {
        access_token: accessToken,
        datacenter
      });
      if (res.data.success) {
        toast.success(`Connected to ${res.data.organization?.name}`);
        loadStatus();
      } else {
        toast.error(res.data.message || "Validation failed");
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Validation failed");
    } finally {
      setValidating(false);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const res = await api.post("/admin/finance/zoho-books/refresh");
      if (res.data.success) {
        toast.success("Connection refreshed");
        loadStatus();
      } else {
        toast.error(res.data.message);
      }
    } catch {
      toast.error("Refresh failed");
    } finally {
      setRefreshing(false);
    }
  };

  const triggerSync = async () => {
    try {
      const res = await api.post("/admin/finance/zoho-books/sync-now");
      toast.success(res.data.message);
      loadSyncHistory();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Sync failed");
    }
  };

  useEffect(() => {
    if (zohoBooksOpen && status?.zoho_books?.is_validated) {
      loadMappings();
      loadSyncHistory();
    }
  }, [zohoBooksOpen, status?.zoho_books?.is_validated]);

  if (loading) {
    return <div className="text-slate-400 text-sm">Loading...</div>;
  }

  return (
    <div data-testid="finance-tab" className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-lg font-bold text-slate-800">Finance Integrations</h2>
        <p className="text-sm text-slate-500 mt-0.5">
          Connect your accounting software to sync invoices, payments, and financial data.
        </p>
      </div>

      {/* Provider Tiles */}
      <div className="space-y-2">
        <ProviderTile
          name="Zoho Books"
          description="Sync invoices, payments, and customers with Zoho Books"
          icon={DollarSign}
          iconBgClass={status?.zoho_books?.is_validated ? "bg-emerald-100" : "bg-green-100"}
          iconClass={status?.zoho_books?.is_validated ? "text-emerald-600" : "text-green-600"}
          isConnected={status?.zoho_books?.is_validated || false}
          datacenter={status?.zoho_books?.datacenter}
          onClick={() => setZohoBooksOpen(true)}
        />
        
        <ProviderTile
          name="QuickBooks"
          description="Sync with QuickBooks Online"
          icon={Database}
          iconBgClass="bg-slate-100"
          iconClass="text-slate-400"
          isConnected={false}
          isComingSoon={true}
          onClick={() => {}}
        />
      </div>

      {/* Zoho Books Slide Panel */}
      {zohoBooksOpen && (
        <div className="fixed inset-0 z-50 flex justify-end" data-testid="zoho-books-slide-panel">
          <div className="absolute inset-0 bg-black/30" onClick={() => setZohoBooksOpen(false)} />
          <div className="relative z-10 w-full max-w-lg bg-white shadow-xl flex flex-col h-full">
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">Zoho Books Integration</h3>
                <p className="text-xs text-slate-400 mt-0.5">Sync financial data with Zoho Books</p>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="sm" onClick={handleRefresh} disabled={refreshing} title="Refresh">
                  <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} />
                </Button>
                <button onClick={() => setZohoBooksOpen(false)} className="text-slate-400 hover:text-slate-600 p-1">
                  <X size={16} />
                </button>
              </div>
            </div>
            
            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              {/* Setup Guide */}
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                <div className="flex items-start gap-2">
                  <Info size={14} className="text-blue-500 mt-0.5 shrink-0" />
                  <div className="text-xs text-blue-700">
                    <p className="font-medium mb-1">Setup Guide</p>
                    <ol className="list-decimal list-inside space-y-0.5 text-blue-600">
                      <li>Go to <a href="https://api-console.zoho.com/" target="_blank" rel="noopener" className="underline inline-flex items-center gap-0.5">api-console.zoho.com <ExternalLink size={10} /></a></li>
                      <li>Create a Server-based Application</li>
                      <li>Add scopes: ZohoBooks.fullaccess.all</li>
                      <li>Copy Client ID and Secret below</li>
                      <li>Complete OAuth to get access token</li>
                    </ol>
                  </div>
                </div>
              </div>

              {/* Connection Status */}
              <div className="flex items-center justify-between py-3 border-b border-slate-100">
                <div>
                  <p className="text-sm font-medium text-slate-700">Connection Status</p>
                  <p className="text-xs text-slate-400">
                    {status?.zoho_books?.is_validated 
                      ? `Connected to ${status.zoho_books.datacenter} datacenter` 
                      : "Not connected"}
                  </p>
                </div>
                <Badge variant={status?.zoho_books?.is_validated ? "default" : "secondary"}>
                  {status?.zoho_books?.is_validated ? (
                    <><CheckCircle className="w-3 h-3 mr-1" /> Connected</>
                  ) : (
                    "Not Connected"
                  )}
                </Badge>
              </div>

              {/* Datacenter */}
              <div>
                <label className="text-xs font-medium text-slate-700">Datacenter</label>
                <Select value={datacenter} onValueChange={setDatacenter}>
                  <SelectTrigger className="mt-1">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="US">United States (zoho.com)</SelectItem>
                    <SelectItem value="CA">Canada (zohocloud.ca)</SelectItem>
                    <SelectItem value="EU">Europe (zoho.eu)</SelectItem>
                    <SelectItem value="IN">India (zoho.in)</SelectItem>
                    <SelectItem value="AU">Australia (zoho.com.au)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Credentials */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-slate-700">Client ID</label>
                  <Input
                    value={clientId}
                    onChange={(e) => setClientId(e.target.value)}
                    placeholder="Enter Client ID"
                    className="mt-1"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-700">Client Secret</label>
                  <Input
                    type="password"
                    value={clientSecret}
                    onChange={(e) => setClientSecret(e.target.value)}
                    placeholder="Enter Client Secret"
                    className="mt-1"
                  />
                </div>
              </div>

              <Button onClick={saveCredentials} disabled={saving} size="sm" className="w-full">
                {saving ? "Saving..." : "Save Credentials"}
              </Button>

              <div className="border-t border-slate-100 pt-4">
                <label className="text-xs font-medium text-slate-700">Access Token</label>
                <Input
                  value={accessToken}
                  onChange={(e) => setAccessToken(e.target.value)}
                  placeholder="Paste access token from OAuth flow"
                  className="mt-1"
                />
                <p className="text-[11px] text-slate-400 mt-1">
                  Get this from Zoho API Console after completing OAuth authorization
                </p>
              </div>

              <Button
                variant="outline"
                onClick={validateConnection}
                disabled={validating || !accessToken}
                size="sm"
                className="w-full"
              >
                {validating ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <CheckCircle className="w-4 h-4 mr-2" />}
                Validate Connection
              </Button>

              {/* Account Mappings - Only show when connected */}
              {status?.zoho_books?.is_validated && (
                <div className="border-t border-slate-100 pt-4">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <p className="text-xs font-medium text-slate-700">Account Mappings</p>
                      <p className="text-[10px] text-slate-400">Map webapp entities to Zoho Books modules</p>
                    </div>
                    <Badge variant="secondary">{mappings.length}</Badge>
                  </div>
                  
                  {mappings.length === 0 ? (
                    <p className="text-xs text-slate-400 text-center py-4 bg-slate-50 rounded-lg">
                      No mappings configured. Sync will use default field mappings.
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {mappings.map((m) => (
                        <div key={m.id} className="flex items-center justify-between p-2 bg-slate-50 rounded-lg text-xs">
                          <div className="flex items-center gap-2">
                            <span className="font-medium">{m.webapp_entity}</span>
                            <ArrowRight size={12} className="text-slate-400" />
                            <span>{m.zoho_module}</span>
                          </div>
                          <Badge variant={m.sync_enabled ? "default" : "secondary"} className="text-[10px]">
                            {m.sync_enabled ? "Active" : "Disabled"}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Sync Actions */}
              {status?.zoho_books?.is_validated && (
                <div className="border-t border-slate-100 pt-4">
                  <Button onClick={triggerSync} variant="outline" size="sm" className="w-full">
                    <RefreshCw size={14} className="mr-2" />
                    Sync Now
                  </Button>
                  
                  {syncHistory.length > 0 && (
                    <div className="mt-3">
                      <p className="text-xs font-medium text-slate-700 mb-2">Recent Syncs</p>
                      <div className="space-y-1">
                        {syncHistory.slice(0, 3).map((job) => (
                          <div key={job.id} className="flex items-center justify-between text-[10px] bg-slate-50 rounded px-2 py-1.5">
                            <div className="flex items-center gap-2">
                              <Clock size={10} className="text-slate-400" />
                              <span>{job.entity}</span>
                            </div>
                            <Badge variant={job.status === "completed" ? "default" : "secondary"} className="text-[9px]">
                              {job.status}
                            </Badge>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
