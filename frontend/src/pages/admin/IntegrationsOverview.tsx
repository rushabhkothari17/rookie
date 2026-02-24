import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  CreditCard,
  Landmark,
  Mail,
  Users,
  Receipt,
  Cloud,
  Calculator,
  Check,
  X,
  Loader2,
  Power,
  Trash2,
  Settings,
  ChevronRight,
  AlertCircle,
  CheckCircle2,
  Clock,
} from "lucide-react";
import api from "@/lib/api";

interface Field {
  key: string;
  label: string;
  hint?: string;
  secret?: boolean;
  required?: boolean;
}

interface Setting {
  key: string;
  label: string;
  default?: string;
}

interface Integration {
  id: string;
  name: string;
  category: string;
  description: string;
  icon: string;
  is_zoho: boolean;
  is_coming_soon: boolean;
  fields: Field[];
  settings: Setting[];
  status: string;
  is_validated: boolean;
  is_active: boolean;
  data_center?: string;
  stored_settings: Record<string, string>;
  connected_at?: string;
  validated_at?: string;
  error_message?: string;
}

interface DataCenter {
  id: string;
  name: string;
}

const CATEGORY_CONFIG: Record<string, { title: string; icon: any; color: string }> = {
  payments: { title: "Payment Providers", icon: CreditCard, color: "emerald" },
  email: { title: "Email Providers", icon: Mail, color: "blue" },
  crm: { title: "CRM", icon: Users, color: "purple" },
  accounting: { title: "Accounting", icon: Receipt, color: "amber" },
};

const ICON_MAP: Record<string, any> = {
  "credit-card": CreditCard,
  landmark: Landmark,
  mail: Mail,
  users: Users,
  receipt: Receipt,
  cloud: Cloud,
  calculator: Calculator,
};

export function IntegrationsOverview() {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [dataCenters, setDataCenters] = useState<DataCenter[]>([]);
  const [activeEmailProvider, setActiveEmailProvider] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  
  // Dialog states
  const [selectedIntegration, setSelectedIntegration] = useState<Integration | null>(null);
  const [showConfigDialog, setShowConfigDialog] = useState(false);
  const [showSettingsDialog, setShowSettingsDialog] = useState(false);
  
  // Form states
  const [credentials, setCredentials] = useState<Record<string, string>>({});
  const [settings, setSettings] = useState<Record<string, string>>({});
  const [dataCenter, setDataCenter] = useState("us");
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState<string | null>(null);

  const loadIntegrations = async () => {
    try {
      const res = await api.get("/oauth/integrations");
      setIntegrations(res.data.integrations || []);
      setDataCenters(res.data.zoho_data_centers || []);
      setActiveEmailProvider(res.data.active_email_provider);
    } catch {
      toast.error("Failed to load integrations");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadIntegrations(); }, []);

  const openConfigDialog = (integration: Integration) => {
    setSelectedIntegration(integration);
    setCredentials({});
    setSettings({});
    setDataCenter(integration.data_center || "us");
    
    // Pre-fill settings with stored values or defaults
    const settingsObj: Record<string, string> = {};
    integration.settings.forEach(s => {
      settingsObj[s.key] = integration.stored_settings[s.key] || s.default || "";
    });
    setSettings(settingsObj);
    
    setShowConfigDialog(true);
  };

  const openSettingsDialog = (integration: Integration) => {
    setSelectedIntegration(integration);
    const settingsObj: Record<string, string> = {};
    integration.settings.forEach(s => {
      settingsObj[s.key] = integration.stored_settings[s.key] || s.default || "";
    });
    setSettings(settingsObj);
    setShowSettingsDialog(true);
  };

  const handleSaveCredentials = async () => {
    if (!selectedIntegration) return;
    
    setSaving(true);
    try {
      await api.post(`/oauth/${selectedIntegration.id}/save-credentials`, {
        credentials,
        data_center: dataCenter,
        settings,
      });
      toast.success("Credentials saved. Now validate the connection.");
      setShowConfigDialog(false);
      loadIntegrations();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const handleValidate = async (providerId: string) => {
    setValidating(providerId);
    try {
      const res = await api.post(`/oauth/${providerId}/validate`);
      if (res.data.success) {
        toast.success(res.data.message);
      } else {
        toast.error(res.data.message);
      }
      loadIntegrations();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Validation failed");
    } finally {
      setValidating(null);
    }
  };

  const handleActivate = async (providerId: string) => {
    try {
      await api.post(`/oauth/${providerId}/activate`);
      toast.success("Provider activated");
      loadIntegrations();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to activate");
    }
  };

  const handleDeactivate = async (providerId: string) => {
    try {
      await api.post(`/oauth/${providerId}/deactivate`);
      toast.success("Provider deactivated");
      loadIntegrations();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to deactivate");
    }
  };

  const handleDisconnect = async (providerId: string) => {
    if (!confirm("Are you sure you want to disconnect this integration?")) return;
    
    try {
      await api.delete(`/oauth/${providerId}/disconnect`);
      toast.success("Disconnected");
      loadIntegrations();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to disconnect");
    }
  };

  const handleSaveSettings = async () => {
    if (!selectedIntegration) return;
    
    setSaving(true);
    try {
      await api.post(`/oauth/${selectedIntegration.id}/update-settings`, { settings });
      toast.success("Settings saved");
      setShowSettingsDialog(false);
      loadIntegrations();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  const getStatusBadge = (integration: Integration) => {
    if (integration.is_coming_soon) {
      return <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 font-medium">COMING SOON</span>;
    }
    if (integration.is_validated && integration.is_active) {
      return <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 font-medium flex items-center gap-1"><CheckCircle2 size={10} /> ACTIVE</span>;
    }
    if (integration.is_validated) {
      return <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 font-medium flex items-center gap-1"><Check size={10} /> VALIDATED</span>;
    }
    if (integration.status === "pending") {
      return <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-medium flex items-center gap-1"><Clock size={10} /> PENDING</span>;
    }
    if (integration.status === "failed") {
      return <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-100 text-red-700 font-medium flex items-center gap-1"><X size={10} /> FAILED</span>;
    }
    return <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 font-medium">NOT CONNECTED</span>;
  };

  if (loading) {
    return <div className="flex items-center justify-center py-12"><Loader2 className="animate-spin text-slate-400" /></div>;
  }

  // Group by category
  const grouped = integrations.reduce((acc, int) => {
    if (!acc[int.category]) acc[int.category] = [];
    acc[int.category].push(int);
    return acc;
  }, {} as Record<string, Integration[]>);

  const categoryOrder = ["payments", "email", "crm", "accounting"];

  return (
    <div className="space-y-8" data-testid="integrations-overview">
      {/* Active Email Provider Banner */}
      {activeEmailProvider ? (
        <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-100 rounded-lg">
              <Mail size={18} className="text-emerald-600" />
            </div>
            <div>
              <p className="text-sm font-medium text-emerald-800">
                {integrations.find(i => i.id === activeEmailProvider)?.name} is your active email provider
              </p>
              <p className="text-xs text-emerald-600">All transactional emails will be sent through this service</p>
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex items-center gap-3">
          <AlertCircle size={18} className="text-amber-600" />
          <div>
            <p className="text-sm font-medium text-amber-800">No email provider active</p>
            <p className="text-xs text-amber-600">Emails will be stored but not sent. Connect and activate a provider below.</p>
          </div>
        </div>
      )}

      {/* Integration Categories */}
      {categoryOrder.map(category => {
        const items = grouped[category];
        if (!items?.length) return null;
        
        const config = CATEGORY_CONFIG[category];
        const CategoryIcon = config.icon;
        
        return (
          <div key={category} className="space-y-3">
            <div className="flex items-center gap-2 pb-2 border-b border-slate-100">
              <CategoryIcon size={16} className="text-slate-400" />
              <h3 className="text-sm font-semibold text-slate-700">{config.title}</h3>
              {category === "email" && (
                <span className="text-[10px] text-slate-400 ml-2">(Only one can be active)</span>
              )}
            </div>
            
            <div className="grid gap-3">
              {items.map(integration => {
                const Icon = ICON_MAP[integration.icon] || CreditCard;
                const isConfigured = integration.status !== "not_connected";
                const canValidate = integration.status === "pending" || integration.status === "failed";
                
                return (
                  <div
                    key={integration.id}
                    className={`rounded-xl border p-4 transition-all ${
                      integration.is_coming_soon 
                        ? "bg-slate-50 border-slate-200 opacity-60"
                        : integration.is_validated && integration.is_active
                        ? "bg-emerald-50/50 border-emerald-200"
                        : integration.is_validated
                        ? "bg-blue-50/30 border-blue-200"
                        : "bg-white border-slate-200 hover:border-slate-300"
                    }`}
                    data-testid={`integration-${integration.id}`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className={`p-2.5 rounded-lg ${
                          integration.is_validated && integration.is_active
                            ? "bg-emerald-100"
                            : integration.is_validated
                            ? "bg-blue-100"
                            : "bg-slate-100"
                        }`}>
                          <Icon size={18} className={
                            integration.is_validated && integration.is_active
                              ? "text-emerald-600"
                              : integration.is_validated
                              ? "text-blue-600"
                              : "text-slate-500"
                          } />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <p className="text-sm font-semibold text-slate-800">{integration.name}</p>
                            {getStatusBadge(integration)}
                            {integration.is_zoho && integration.data_center && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">
                                {integration.data_center.toUpperCase()}
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-slate-500 mt-0.5">{integration.description}</p>
                          {integration.error_message && (
                            <p className="text-xs text-red-500 mt-1 flex items-center gap-1">
                              <AlertCircle size={10} /> {integration.error_message}
                            </p>
                          )}
                        </div>
                      </div>
                      
                      {/* Actions */}
                      <div className="flex items-center gap-2">
                        {integration.is_coming_soon ? (
                          <span className="text-xs text-slate-400">Coming Soon</span>
                        ) : !isConfigured ? (
                          <Button
                            size="sm"
                            onClick={() => openConfigDialog(integration)}
                            data-testid={`configure-${integration.id}`}
                          >
                            Configure <ChevronRight size={14} className="ml-1" />
                          </Button>
                        ) : (
                          <>
                            {canValidate && (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleValidate(integration.id)}
                                disabled={validating === integration.id}
                                data-testid={`validate-${integration.id}`}
                              >
                                {validating === integration.id ? (
                                  <><Loader2 size={12} className="mr-1 animate-spin" /> Validating</>
                                ) : (
                                  <>Validate</>
                                )}
                              </Button>
                            )}
                            
                            {integration.is_validated && integration.category === "email" && (
                              integration.is_active ? (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => handleDeactivate(integration.id)}
                                  className="text-amber-600 border-amber-200 hover:bg-amber-50"
                                  data-testid={`deactivate-${integration.id}`}
                                >
                                  <Power size={12} className="mr-1" /> Deactivate
                                </Button>
                              ) : (
                                <Button
                                  size="sm"
                                  onClick={() => handleActivate(integration.id)}
                                  className="bg-emerald-600 hover:bg-emerald-700"
                                  data-testid={`activate-${integration.id}`}
                                >
                                  <Power size={12} className="mr-1" /> Activate
                                </Button>
                              )
                            )}
                            
                            {integration.settings.length > 0 && integration.is_validated && (
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => openSettingsDialog(integration)}
                                data-testid={`settings-${integration.id}`}
                              >
                                <Settings size={14} />
                              </Button>
                            )}
                            
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => openConfigDialog(integration)}
                              className="text-slate-500"
                              data-testid={`edit-${integration.id}`}
                            >
                              Edit
                            </Button>
                            
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleDisconnect(integration.id)}
                              className="text-red-500 hover:text-red-600 hover:bg-red-50"
                              data-testid={`disconnect-${integration.id}`}
                            >
                              <Trash2 size={14} />
                            </Button>
                          </>
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

      {/* Configure Dialog */}
      <Dialog open={showConfigDialog} onOpenChange={setShowConfigDialog}>
        <DialogContent className="max-w-md" data-testid="config-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              Configure {selectedIntegration?.name}
            </DialogTitle>
          </DialogHeader>
          
          {selectedIntegration && (
            <div className="space-y-4 py-2">
              {/* Zoho Data Center Selection */}
              {selectedIntegration.is_zoho && (
                <div>
                  <label className="text-xs font-medium text-slate-700 mb-1.5 block">Data Center</label>
                  <Select value={dataCenter} onValueChange={setDataCenter}>
                    <SelectTrigger data-testid="dc-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {dataCenters.map(dc => (
                        <SelectItem key={dc.id} value={dc.id}>{dc.name} ({dc.id.toUpperCase()})</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-[11px] text-slate-400 mt-1">Select the data center where your Zoho account is hosted</p>
                </div>
              )}
              
              {/* Credential Fields */}
              {selectedIntegration.fields.map(field => (
                <div key={field.key}>
                  <label className="text-xs font-medium text-slate-700 mb-1.5 block">
                    {field.label} {field.required && <span className="text-red-500">*</span>}
                  </label>
                  <Input
                    type={field.secret ? "password" : "text"}
                    value={credentials[field.key] || ""}
                    onChange={e => setCredentials(prev => ({ ...prev, [field.key]: e.target.value }))}
                    placeholder={field.hint}
                    data-testid={`field-${field.key}`}
                  />
                  {field.hint && <p className="text-[11px] text-slate-400 mt-1">{field.hint}</p>}
                </div>
              ))}
              
              {/* Settings Fields (shown during initial config) */}
              {selectedIntegration.settings.length > 0 && (
                <>
                  <div className="border-t border-slate-100 pt-4 mt-4">
                    <p className="text-xs font-semibold text-slate-600 mb-3">Settings</p>
                    {selectedIntegration.settings.map(setting => (
                      <div key={setting.key} className="mb-3">
                        <label className="text-xs font-medium text-slate-700 mb-1.5 block">{setting.label}</label>
                        <Input
                          value={settings[setting.key] || ""}
                          onChange={e => setSettings(prev => ({ ...prev, [setting.key]: e.target.value }))}
                          placeholder={setting.default || ""}
                          data-testid={`setting-${setting.key}`}
                        />
                      </div>
                    ))}
                  </div>
                </>
              )}
              
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="ghost" onClick={() => setShowConfigDialog(false)}>Cancel</Button>
                <Button onClick={handleSaveCredentials} disabled={saving} data-testid="save-credentials">
                  {saving ? <><Loader2 size={14} className="mr-1 animate-spin" /> Saving</> : "Save & Continue"}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Settings Dialog */}
      <Dialog open={showSettingsDialog} onOpenChange={setShowSettingsDialog}>
        <DialogContent className="max-w-md" data-testid="settings-dialog">
          <DialogHeader>
            <DialogTitle>{selectedIntegration?.name} Settings</DialogTitle>
          </DialogHeader>
          
          {selectedIntegration && (
            <div className="space-y-4 py-2">
              {selectedIntegration.settings.map(setting => (
                <div key={setting.key}>
                  <label className="text-xs font-medium text-slate-700 mb-1.5 block">{setting.label}</label>
                  <Input
                    value={settings[setting.key] || ""}
                    onChange={e => setSettings(prev => ({ ...prev, [setting.key]: e.target.value }))}
                    placeholder={setting.default || ""}
                    data-testid={`dialog-setting-${setting.key}`}
                  />
                </div>
              ))}
              
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="ghost" onClick={() => setShowSettingsDialog(false)}>Cancel</Button>
                <Button onClick={handleSaveSettings} disabled={saving} data-testid="save-settings">
                  {saving ? <><Loader2 size={14} className="mr-1 animate-spin" /> Saving</> : "Save Settings"}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
