import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { CheckCircle, XCircle, RefreshCw, Plus, Trash2, ArrowRight, X, Info, ExternalLink, Database, Power, Pencil, Link2 } from "lucide-react";

interface FieldMapping {
  webapp_field: string;
  crm_field: string;
}

interface CRMMapping {
  id?: string;
  webapp_module: string;
  crm_module: string;
  field_mappings: FieldMapping[];
  sync_on_create: boolean;
  sync_on_update: boolean;
  is_active: boolean;
}

interface CRMModule {
  api_name: string;
  module_name: string;
  singular_label: string;
  plural_label: string;
}

interface CRMField {
  api_name: string;
  field_label: string;
  data_type: string;
  required: boolean;
  read_only: boolean;
}

interface WebappModule {
  name: string;
  label: string;
  fields: string[];
}

// Tile component for CRM providers
function CRMProviderTile({ 
  name, 
  description, 
  icon: Icon, 
  iconBgClass,
  iconClass,
  isConnected, 
  datacenter,
  onClick 
}: {
  name: string;
  description: string;
  icon: any;
  iconBgClass: string;
  iconClass: string;
  isConnected: boolean;
  datacenter?: string;
  onClick: () => void;
}) {
  return (
    <div
      className={`rounded-xl border p-4 flex items-center justify-between cursor-pointer hover:border-slate-300 transition-colors ${isConnected ? "border-emerald-300 bg-emerald-50/50" : "border-slate-200 bg-white"}`}
      onClick={onClick}
      data-testid={`crm-provider-tile-${name.toLowerCase().replace(/\s/g, '-')}`}
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

export function CRMTab() {
  const [loading, setLoading] = useState(false);
  const [validating, setValidating] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  
  // Zoho CRM panel state
  const [zohoOpen, setZohoOpen] = useState(false);
  const [datacenter, setDatacenter] = useState("US");
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [accessToken, setAccessToken] = useState("");
  const [connectionStatus, setConnectionStatus] = useState<"connected" | "not_configured" | "error">("not_configured");
  
  // Modules and fields
  const [crmModules, setCrmModules] = useState<CRMModule[]>([]);
  const [crmFields, setCrmFields] = useState<Record<string, CRMField[]>>({});
  const [webappModules, setWebappModules] = useState<WebappModule[]>([]);
  
  // Mappings
  const [mappings, setMappings] = useState<CRMMapping[]>([]);
  const [editingMapping, setEditingMapping] = useState<CRMMapping | null>(null);
  const [selectedCrmModule, setSelectedCrmModule] = useState("");
  const [showMappings, setShowMappings] = useState(false);

  useEffect(() => {
    loadStatus();
    loadMappings();
  }, []);

  const loadStatus = async () => {
    try {
      const res = await api.get("/admin/integrations/status");
      const zoho = res.data.integrations?.zoho_crm;
      if (zoho?.status === "connected" || zoho?.is_validated) {
        setConnectionStatus("connected");
        setDatacenter(zoho.datacenter || "US");
      }
    } catch {
      // Ignore
    }
  };

  const loadMappings = async () => {
    try {
      const res = await api.get("/admin/integrations/crm-mappings");
      setMappings(res.data.mappings || []);
      setWebappModules(res.data.webapp_modules || []);
    } catch {
      // toast.error("Failed to load CRM mappings");
    }
  };

  const saveCredentials = async () => {
    if (!clientId || !clientSecret) {
      toast.error("Client ID and Secret are required");
      return;
    }
    setLoading(true);
    try {
      await api.post("/admin/integrations/zoho-crm/save-credentials", {
        client_id: clientId,
        client_secret: clientSecret,
        datacenter
      });
      toast.success("Credentials saved");
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to save credentials");
    } finally {
      setLoading(false);
    }
  };

  const validateConnection = async () => {
    if (!accessToken) {
      toast.error("Access token is required for validation");
      return;
    }
    setValidating(true);
    try {
      const res = await api.post("/admin/integrations/zoho-crm/validate", {
        access_token: accessToken,
        datacenter
      });
      if (res.data.success) {
        setConnectionStatus("connected");
        setCrmModules(res.data.modules || []);
        toast.success(`Connected! Found ${res.data.modules_count} modules`);
      } else {
        setConnectionStatus("error");
        toast.error(res.data.message || "Validation failed");
      }
    } catch (err: any) {
      setConnectionStatus("error");
      toast.error(err.response?.data?.detail || "Validation failed");
    } finally {
      setValidating(false);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadStatus();
    setRefreshing(false);
  };

  const loadModuleFields = async (moduleName: string) => {
    if (!accessToken || crmFields[moduleName]) return;
    try {
      const res = await api.get(`/admin/integrations/zoho-crm/modules/${moduleName}/fields`, {
        params: { access_token: accessToken, datacenter }
      });
      setCrmFields(prev => ({ ...prev, [moduleName]: res.data.fields || [] }));
    } catch {
      toast.error(`Failed to load fields for ${moduleName}`);
    }
  };

  const handleCrmModuleSelect = async (moduleName: string) => {
    setSelectedCrmModule(moduleName);
    await loadModuleFields(moduleName);
  };

  const startNewMapping = () => {
    setEditingMapping({
      webapp_module: "",
      crm_module: "",
      field_mappings: [],
      sync_on_create: true,
      sync_on_update: true,
      is_active: true
    });
  };

  const addFieldMapping = () => {
    if (!editingMapping) return;
    setEditingMapping({
      ...editingMapping,
      field_mappings: [...editingMapping.field_mappings, { webapp_field: "", crm_field: "" }]
    });
  };

  const updateFieldMapping = (index: number, field: "webapp_field" | "crm_field", value: string) => {
    if (!editingMapping) return;
    const updated = [...editingMapping.field_mappings];
    updated[index] = { ...updated[index], [field]: value };
    setEditingMapping({ ...editingMapping, field_mappings: updated });
  };

  const removeFieldMapping = (index: number) => {
    if (!editingMapping) return;
    const updated = editingMapping.field_mappings.filter((_, i) => i !== index);
    setEditingMapping({ ...editingMapping, field_mappings: updated });
  };

  const saveMapping = async () => {
    if (!editingMapping) return;
    if (!editingMapping.webapp_module || !editingMapping.crm_module) {
      toast.error("Please select both modules");
      return;
    }
    if (editingMapping.field_mappings.length === 0) {
      toast.error("Add at least one field mapping");
      return;
    }
    
    setLoading(true);
    try {
      if (editingMapping.id) {
        await api.put(`/admin/integrations/crm-mappings/${editingMapping.id}`, editingMapping);
        toast.success("Mapping updated");
      } else {
        await api.post("/admin/integrations/crm-mappings", editingMapping);
        toast.success("Mapping created");
      }
      setEditingMapping(null);
      loadMappings();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to save mapping");
    } finally {
      setLoading(false);
    }
  };

  const deleteMapping = async (id: string) => {
    if (!confirm("Delete this mapping?")) return;
    try {
      await api.delete(`/admin/integrations/crm-mappings/${id}`);
      toast.success("Mapping deleted");
      loadMappings();
    } catch {
      toast.error("Failed to delete mapping");
    }
  };

  const toggleMappingActive = async (mapping: CRMMapping) => {
    try {
      await api.put(`/admin/integrations/crm-mappings/${mapping.id}`, {
        ...mapping,
        is_active: !mapping.is_active
      });
      loadMappings();
      toast.success(mapping.is_active ? "Mapping disabled" : "Mapping enabled");
    } catch {
      toast.error("Failed to toggle mapping");
    }
  };

  const selectedWebappModule = webappModules.find(m => m.name === editingMapping?.webapp_module);
  const selectedCrmModuleFields = crmFields[editingMapping?.crm_module || ""] || [];

  return (
    <div data-testid="crm-tab" className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-lg font-bold text-slate-800">CRM Integrations</h2>
        <p className="text-sm text-slate-500 mt-0.5">
          Connect your CRM to sync customer data, orders, and more. Click on a provider tile to configure.
        </p>
      </div>

      {/* CRM Provider Tiles */}
      <div className="space-y-2">
        <CRMProviderTile
          name="Zoho CRM"
          description="Sync customers, orders, and subscriptions with Zoho CRM"
          icon={Database}
          iconBgClass={connectionStatus === "connected" ? "bg-emerald-100" : "bg-red-100"}
          iconClass={connectionStatus === "connected" ? "text-emerald-600" : "text-red-600"}
          isConnected={connectionStatus === "connected"}
          datacenter={datacenter}
          onClick={() => setZohoOpen(true)}
        />
        
        {/* Future CRM placeholder tiles */}
        <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/50 p-4 flex items-center justify-between opacity-60">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-slate-100">
              <Database size={18} className="text-slate-400" />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-500">Salesforce</p>
              <p className="text-xs text-slate-400 mt-0.5">Coming soon</p>
            </div>
          </div>
          <Badge variant="outline" className="text-slate-400">Soon</Badge>
        </div>
        
        <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/50 p-4 flex items-center justify-between opacity-60">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-slate-100">
              <Database size={18} className="text-slate-400" />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-500">HubSpot</p>
              <p className="text-xs text-slate-400 mt-0.5">Coming soon</p>
            </div>
          </div>
          <Badge variant="outline" className="text-slate-400">Soon</Badge>
        </div>
      </div>

      {/* Field Mappings Section - Only shown when connected */}
      {connectionStatus === "connected" && (
        <div className="border border-slate-200 rounded-xl overflow-hidden">
          <button 
            onClick={() => setShowMappings(!showMappings)}
            className="w-full flex items-center justify-between px-5 py-4 bg-slate-50 hover:bg-slate-100 transition-colors"
          >
            <div className="flex items-center gap-2">
              <Link2 size={16} className="text-slate-500" />
              <span className="text-sm font-medium text-slate-700">Field Mappings</span>
              <Badge variant="secondary" className="ml-2">{mappings.length}</Badge>
            </div>
            <span className="text-xs text-slate-400">{showMappings ? "Hide" : "Show"}</span>
          </button>
          
          {showMappings && (
            <div className="p-4 space-y-3 border-t border-slate-100">
              {mappings.length === 0 ? (
                <div className="text-center py-6">
                  <p className="text-sm text-slate-500 mb-3">No field mappings configured yet</p>
                  <Button size="sm" onClick={startNewMapping}>
                    <Plus size={14} className="mr-1" /> Create First Mapping
                  </Button>
                </div>
              ) : (
                <>
                  {mappings.map((m) => (
                    <div key={m.id} className={`flex items-center justify-between p-3 rounded-lg border ${m.is_active ? "border-slate-200 bg-white" : "border-slate-100 bg-slate-50 opacity-60"}`}>
                      <div className="flex items-center gap-3">
                        <div className="flex items-center gap-2 text-sm">
                          <Badge variant="outline">{webappModules.find(w => w.name === m.webapp_module)?.label || m.webapp_module}</Badge>
                          <ArrowRight size={14} className="text-slate-400" />
                          <Badge variant="outline">{m.crm_module}</Badge>
                        </div>
                        <span className="text-xs text-slate-400">{m.field_mappings.length} fields</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Button variant="ghost" size="sm" onClick={() => setEditingMapping(m)}>
                          <Pencil size={12} />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => toggleMappingActive(m)}>
                          <Power size={12} className={m.is_active ? "text-emerald-500" : "text-slate-400"} />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => deleteMapping(m.id!)}>
                          <Trash2 size={12} className="text-red-400" />
                        </Button>
                      </div>
                    </div>
                  ))}
                  <Button variant="outline" size="sm" onClick={startNewMapping} className="w-full">
                    <Plus size={14} className="mr-1" /> Add Mapping
                  </Button>
                </>
              )}
            </div>
          )}
        </div>
      )}

      {/* Zoho CRM Slide Panel */}
      {zohoOpen && (
        <div className="fixed inset-0 z-50 flex justify-end" data-testid="zoho-crm-slide-panel">
          <div className="absolute inset-0 bg-black/30" onClick={() => setZohoOpen(false)} />
          <div className="relative z-10 w-full max-w-lg bg-white shadow-xl flex flex-col h-full">
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">Zoho CRM Integration</h3>
                <p className="text-xs text-slate-400 mt-0.5">Connect and sync data with Zoho CRM</p>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="sm" onClick={handleRefresh} disabled={refreshing} title="Refresh status">
                  <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} />
                </Button>
                <button onClick={() => setZohoOpen(false)} className="text-slate-400 hover:text-slate-600 p-1">
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
                      <li>Add scopes: ZohoCRM.modules.ALL, ZohoCRM.settings.ALL</li>
                      <li>Copy Client ID and Secret below</li>
                      <li>Complete OAuth flow to get access token</li>
                    </ol>
                  </div>
                </div>
              </div>

              {/* Connection Status */}
              <div className="flex items-center justify-between py-3 border-b border-slate-100">
                <div>
                  <p className="text-sm font-medium text-slate-700">Connection Status</p>
                  <p className="text-xs text-slate-400">
                    {connectionStatus === "connected" ? `Connected to ${datacenter} datacenter` : "Not connected"}
                  </p>
                </div>
                <Badge variant={connectionStatus === "connected" ? "default" : "secondary"}>
                  {connectionStatus === "connected" ? (
                    <><CheckCircle className="w-3 h-3 mr-1" /> Connected</>
                  ) : connectionStatus === "error" ? (
                    <><XCircle className="w-3 h-3 mr-1" /> Error</>
                  ) : (
                    "Not Connected"
                  )}
                </Badge>
              </div>

              {/* Datacenter */}
              <div>
                <label className="text-xs font-medium text-slate-700">Datacenter</label>
                <Select value={datacenter} onValueChange={setDatacenter}>
                  <SelectTrigger className="mt-1" data-testid="crm-datacenter-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="US">United States (zoho.com)</SelectItem>
                    <SelectItem value="CA">Canada (zohocloud.ca)</SelectItem>
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
                    data-testid="crm-client-id-input"
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
                    data-testid="crm-client-secret-input"
                  />
                </div>
              </div>

              <Button onClick={saveCredentials} disabled={loading} size="sm" className="w-full">
                {loading ? "Saving..." : "Save Credentials"}
              </Button>

              <div className="border-t border-slate-100 pt-4">
                <label className="text-xs font-medium text-slate-700">Access Token</label>
                <Input
                  value={accessToken}
                  onChange={(e) => setAccessToken(e.target.value)}
                  placeholder="Paste access token from OAuth flow"
                  className="mt-1"
                  data-testid="crm-access-token-input"
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
                data-testid="crm-validate-btn"
              >
                {validating ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <CheckCircle className="w-4 h-4 mr-2" />}
                Validate Connection
              </Button>

              {/* Available Modules */}
              {crmModules.length > 0 && (
                <div className="border-t border-slate-100 pt-4">
                  <p className="text-xs font-medium text-slate-700 mb-2">Available CRM Modules ({crmModules.length})</p>
                  <div className="flex flex-wrap gap-1.5">
                    {crmModules.slice(0, 12).map((m) => (
                      <Badge key={m.api_name} variant="outline" className="text-[10px]">
                        {m.plural_label || m.module_name}
                      </Badge>
                    ))}
                    {crmModules.length > 12 && (
                      <Badge variant="secondary" className="text-[10px]">+{crmModules.length - 12} more</Badge>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Mapping Editor Modal */}
      {editingMapping && (
        <div className="fixed inset-0 z-50 flex items-center justify-center" data-testid="mapping-editor-modal">
          <div className="absolute inset-0 bg-black/30" onClick={() => setEditingMapping(null)} />
          <div className="relative z-10 w-full max-w-2xl bg-white rounded-xl shadow-xl max-h-[80vh] overflow-hidden flex flex-col">
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
              <h3 className="text-sm font-semibold text-slate-900">
                {editingMapping.id ? "Edit" : "New"} Field Mapping
              </h3>
              <button onClick={() => setEditingMapping(null)} className="text-slate-400 hover:text-slate-600 p-1">
                <X size={16} />
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              {/* Module Selection */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-medium text-slate-700">Webapp Module</label>
                  <Select 
                    value={editingMapping.webapp_module} 
                    onValueChange={(v) => setEditingMapping({ ...editingMapping, webapp_module: v })}
                  >
                    <SelectTrigger className="mt-1" data-testid="mapping-webapp-module-select">
                      <SelectValue placeholder="Select module" />
                    </SelectTrigger>
                    <SelectContent>
                      {webappModules.map((m) => (
                        <SelectItem key={m.name} value={m.name}>{m.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-700">CRM Module</label>
                  <Select 
                    value={editingMapping.crm_module} 
                    onValueChange={(v) => { 
                      setEditingMapping({ ...editingMapping, crm_module: v });
                      handleCrmModuleSelect(v);
                    }}
                  >
                    <SelectTrigger className="mt-1" data-testid="mapping-crm-module-select">
                      <SelectValue placeholder="Select CRM module" />
                    </SelectTrigger>
                    <SelectContent>
                      {crmModules.map((m) => (
                        <SelectItem key={m.api_name} value={m.api_name}>{m.plural_label || m.module_name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Sync Options */}
              <div className="flex gap-4">
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input
                    type="checkbox"
                    checked={editingMapping.sync_on_create}
                    onChange={(e) => setEditingMapping({ ...editingMapping, sync_on_create: e.target.checked })}
                    className="rounded"
                  />
                  <span className="text-slate-600">Sync on create</span>
                </label>
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input
                    type="checkbox"
                    checked={editingMapping.sync_on_update}
                    onChange={(e) => setEditingMapping({ ...editingMapping, sync_on_update: e.target.checked })}
                    className="rounded"
                  />
                  <span className="text-slate-600">Sync on update</span>
                </label>
              </div>

              {/* Field Mappings */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-xs font-medium text-slate-700">Field Mappings</label>
                  <Button variant="outline" size="sm" onClick={addFieldMapping}>
                    <Plus size={12} className="mr-1" /> Add Field
                  </Button>
                </div>
                
                {editingMapping.field_mappings.length === 0 ? (
                  <p className="text-xs text-slate-400 text-center py-4 border border-dashed border-slate-200 rounded-lg">
                    No field mappings yet. Click "Add Field" to start mapping fields.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {editingMapping.field_mappings.map((fm, idx) => (
                      <div key={idx} className="flex items-center gap-2 p-2 bg-slate-50 rounded-lg">
                        <Select 
                          value={fm.webapp_field} 
                          onValueChange={(v) => updateFieldMapping(idx, "webapp_field", v)}
                        >
                          <SelectTrigger className="flex-1 h-8 text-xs">
                            <SelectValue placeholder="Webapp field" />
                          </SelectTrigger>
                          <SelectContent>
                            {selectedWebappModule?.fields.map((f) => (
                              <SelectItem key={f} value={f}>{f}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <ArrowRight size={14} className="text-slate-400 shrink-0" />
                        <Select 
                          value={fm.crm_field} 
                          onValueChange={(v) => updateFieldMapping(idx, "crm_field", v)}
                        >
                          <SelectTrigger className="flex-1 h-8 text-xs">
                            <SelectValue placeholder="CRM field" />
                          </SelectTrigger>
                          <SelectContent>
                            {selectedCrmModuleFields.map((f) => (
                              <SelectItem key={f.api_name} value={f.api_name}>
                                {f.field_label} {f.required && <span className="text-red-500">*</span>}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <Button variant="ghost" size="sm" onClick={() => removeFieldMapping(idx)} className="h-8 w-8 p-0">
                          <Trash2 size={12} className="text-red-400" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-slate-100">
              <Button variant="outline" size="sm" onClick={() => setEditingMapping(null)}>Cancel</Button>
              <Button size="sm" onClick={saveMapping} disabled={loading}>
                {loading ? "Saving..." : "Save Mapping"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
