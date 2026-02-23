import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { CheckCircle, XCircle, RefreshCw, Plus, Trash2, ArrowRight, Settings, Link2 } from "lucide-react";

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

export function CRMTab() {
  const [activeTab, setActiveTab] = useState("connection");
  const [loading, setLoading] = useState(false);
  const [validating, setValidating] = useState(false);
  
  // Connection settings
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

  useEffect(() => {
    loadStatus();
    loadMappings();
  }, []);

  const loadStatus = async () => {
    try {
      const res = await api.get("/admin/integrations/status");
      const zoho = res.data.integrations?.zoho_crm;
      if (zoho?.status === "connected") {
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
      toast.error("Failed to load CRM mappings");
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

  const loadModules = async () => {
    if (!accessToken) return;
    setLoading(true);
    try {
      const res = await api.get("/admin/integrations/zoho-crm/modules", {
        params: { access_token: accessToken, datacenter }
      });
      setCrmModules(res.data.modules || []);
    } catch {
      toast.error("Failed to load CRM modules");
    } finally {
      setLoading(false);
    }
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
    setEditingMapping({
      ...editingMapping,
      field_mappings: editingMapping.field_mappings.filter((_, i) => i !== index)
    });
  };

  const saveMapping = async () => {
    if (!editingMapping?.webapp_module || !editingMapping?.crm_module) {
      toast.error("Select both webapp and CRM modules");
      return;
    }
    setLoading(true);
    try {
      await api.post("/admin/integrations/crm-mappings", editingMapping);
      toast.success("Mapping saved");
      setEditingMapping(null);
      loadMappings();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to save mapping");
    } finally {
      setLoading(false);
    }
  };

  const deleteMapping = async (mappingId: string) => {
    if (!confirm("Delete this mapping?")) return;
    try {
      await api.delete(`/admin/integrations/crm-mappings/${mappingId}`);
      toast.success("Mapping deleted");
      loadMappings();
    } catch {
      toast.error("Failed to delete mapping");
    }
  };

  const getWebappModuleFields = (moduleName: string): string[] => {
    return webappModules.find(m => m.name === moduleName)?.fields || [];
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Zoho CRM Integration</h2>
          <p className="text-sm text-slate-500">Connect your Zoho CRM and map fields to sync data automatically</p>
        </div>
        <Badge variant={connectionStatus === "connected" ? "default" : "secondary"}>
          {connectionStatus === "connected" ? (
            <><CheckCircle className="w-3 h-3 mr-1" /> Connected ({datacenter})</>
          ) : connectionStatus === "error" ? (
            <><XCircle className="w-3 h-3 mr-1" /> Error</>
          ) : (
            "Not Connected"
          )}
        </Badge>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="connection" data-testid="crm-connection-tab">
            <Settings className="w-4 h-4 mr-2" /> Connection
          </TabsTrigger>
          <TabsTrigger value="mappings" data-testid="crm-mappings-tab">
            <Link2 className="w-4 h-4 mr-2" /> Field Mappings
          </TabsTrigger>
        </TabsList>

        <TabsContent value="connection" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">OAuth Credentials</CardTitle>
              <CardDescription>
                Enter your Zoho CRM OAuth credentials from the Zoho API Console
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium">Datacenter</label>
                  <Select value={datacenter} onValueChange={setDatacenter}>
                    <SelectTrigger data-testid="crm-datacenter-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="US">United States (zoho.com)</SelectItem>
                      <SelectItem value="CA">Canada (zohocloud.ca)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium">Client ID</label>
                  <Input
                    value={clientId}
                    onChange={(e) => setClientId(e.target.value)}
                    placeholder="Enter Zoho Client ID"
                    data-testid="crm-client-id-input"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">Client Secret</label>
                  <Input
                    type="password"
                    value={clientSecret}
                    onChange={(e) => setClientSecret(e.target.value)}
                    placeholder="Enter Zoho Client Secret"
                    data-testid="crm-client-secret-input"
                  />
                </div>
              </div>

              <div>
                <label className="text-sm font-medium">Access Token</label>
                <Input
                  value={accessToken}
                  onChange={(e) => setAccessToken(e.target.value)}
                  placeholder="Paste your access token after OAuth flow"
                  data-testid="crm-access-token-input"
                />
                <p className="text-xs text-slate-500 mt-1">
                  Get this from the Zoho OAuth flow or API Console
                </p>
              </div>

              <div className="flex gap-2">
                <Button onClick={saveCredentials} disabled={loading} data-testid="crm-save-credentials-btn">
                  Save Credentials
                </Button>
                <Button 
                  variant="outline" 
                  onClick={validateConnection} 
                  disabled={validating || !accessToken}
                  data-testid="crm-validate-btn"
                >
                  {validating ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <CheckCircle className="w-4 h-4 mr-2" />}
                  Validate Connection
                </Button>
              </div>
            </CardContent>
          </Card>

          {crmModules.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Available CRM Modules</CardTitle>
                <CardDescription>{crmModules.length} modules found</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {crmModules.map((m) => (
                    <Badge key={m.api_name} variant="outline">
                      {m.plural_label || m.module_name}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="mappings" className="space-y-4">
          {connectionStatus !== "connected" ? (
            <Card>
              <CardContent className="py-8 text-center">
                <p className="text-slate-500">Connect to Zoho CRM first to configure field mappings</p>
                <Button variant="outline" className="mt-4" onClick={() => setActiveTab("connection")}>
                  Go to Connection Settings
                </Button>
              </CardContent>
            </Card>
          ) : editingMapping ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">
                  {editingMapping.id ? "Edit" : "New"} Field Mapping
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium">Webapp Module</label>
                    <Select 
                      value={editingMapping.webapp_module} 
                      onValueChange={(v) => setEditingMapping({ ...editingMapping, webapp_module: v })}
                    >
                      <SelectTrigger data-testid="mapping-webapp-module-select">
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
                    <label className="text-sm font-medium">Zoho CRM Module</label>
                    <Select 
                      value={editingMapping.crm_module} 
                      onValueChange={(v) => {
                        setEditingMapping({ ...editingMapping, crm_module: v });
                        handleCrmModuleSelect(v);
                      }}
                    >
                      <SelectTrigger data-testid="mapping-crm-module-select">
                        <SelectValue placeholder="Select CRM module" />
                      </SelectTrigger>
                      <SelectContent>
                        {crmModules.map((m) => (
                          <SelectItem key={m.api_name} value={m.api_name}>
                            {m.plural_label || m.module_name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="border rounded-lg p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-medium">Field Mappings</h4>
                    <Button size="sm" variant="outline" onClick={addFieldMapping}>
                      <Plus className="w-3 h-3 mr-1" /> Add Field
                    </Button>
                  </div>
                  
                  {editingMapping.field_mappings.length === 0 ? (
                    <p className="text-sm text-slate-500 text-center py-4">
                      No field mappings yet. Click "Add Field" to start.
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {editingMapping.field_mappings.map((fm, idx) => (
                        <div key={idx} className="flex items-center gap-2">
                          <Select 
                            value={fm.webapp_field}
                            onValueChange={(v) => updateFieldMapping(idx, "webapp_field", v)}
                          >
                            <SelectTrigger className="flex-1">
                              <SelectValue placeholder="Webapp field" />
                            </SelectTrigger>
                            <SelectContent>
                              {getWebappModuleFields(editingMapping.webapp_module).map((f) => (
                                <SelectItem key={f} value={f}>{f}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          <ArrowRight className="w-4 h-4 text-slate-400" />
                          <Select 
                            value={fm.crm_field}
                            onValueChange={(v) => updateFieldMapping(idx, "crm_field", v)}
                          >
                            <SelectTrigger className="flex-1">
                              <SelectValue placeholder="CRM field" />
                            </SelectTrigger>
                            <SelectContent>
                              {(crmFields[editingMapping.crm_module] || []).map((f) => (
                                <SelectItem key={f.api_name} value={f.api_name}>
                                  {f.field_label} ({f.data_type})
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          <Button size="icon" variant="ghost" onClick={() => removeFieldMapping(idx)}>
                            <Trash2 className="w-4 h-4 text-red-500" />
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-4">
                  <label className="flex items-center gap-2 text-sm">
                    <input 
                      type="checkbox" 
                      checked={editingMapping.sync_on_create}
                      onChange={(e) => setEditingMapping({ ...editingMapping, sync_on_create: e.target.checked })}
                    />
                    Sync on create
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input 
                      type="checkbox" 
                      checked={editingMapping.sync_on_update}
                      onChange={(e) => setEditingMapping({ ...editingMapping, sync_on_update: e.target.checked })}
                    />
                    Sync on update
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input 
                      type="checkbox" 
                      checked={editingMapping.is_active}
                      onChange={(e) => setEditingMapping({ ...editingMapping, is_active: e.target.checked })}
                    />
                    Active
                  </label>
                </div>

                <div className="flex gap-2">
                  <Button onClick={saveMapping} disabled={loading} data-testid="save-mapping-btn">
                    Save Mapping
                  </Button>
                  <Button variant="outline" onClick={() => setEditingMapping(null)}>
                    Cancel
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : (
            <>
              <div className="flex justify-end">
                <Button onClick={startNewMapping} data-testid="new-mapping-btn">
                  <Plus className="w-4 h-4 mr-2" /> New Mapping
                </Button>
              </div>

              {mappings.length === 0 ? (
                <Card>
                  <CardContent className="py-8 text-center">
                    <p className="text-slate-500">No field mappings configured yet</p>
                  </CardContent>
                </Card>
              ) : (
                <div className="space-y-3">
                  {mappings.map((mapping) => (
                    <Card key={mapping.id}>
                      <CardContent className="py-4">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-4">
                            <div>
                              <span className="font-medium">{mapping.webapp_module}</span>
                              <span className="text-slate-400 mx-2">→</span>
                              <span className="font-medium">{mapping.crm_module}</span>
                            </div>
                            <Badge variant={mapping.is_active ? "default" : "secondary"}>
                              {mapping.is_active ? "Active" : "Inactive"}
                            </Badge>
                            <span className="text-sm text-slate-500">
                              {mapping.field_mappings.length} field(s)
                            </span>
                          </div>
                          <div className="flex gap-2">
                            <Button 
                              size="sm" 
                              variant="outline"
                              onClick={() => setEditingMapping(mapping)}
                            >
                              Edit
                            </Button>
                            <Button 
                              size="sm" 
                              variant="ghost"
                              onClick={() => mapping.id && deleteMapping(mapping.id)}
                            >
                              <Trash2 className="w-4 h-4 text-red-500" />
                            </Button>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
