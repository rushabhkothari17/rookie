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
  Pencil,
  Link,
  CheckCircle2,
  Clock,
  AlertCircle,
  LayoutGrid,
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

type CategoryFilter = "all" | "payments" | "email" | "crm" | "accounting";

const CATEGORY_CONFIG: Record<string, { label: string; icon: any; color: string; bgColor: string }> = {
  all: { label: "All Integrations", icon: LayoutGrid, color: "text-slate-600", bgColor: "bg-slate-100" },
  payments: { label: "Payments", icon: CreditCard, color: "text-emerald-600", bgColor: "bg-emerald-100" },
  email: { label: "Email", icon: Mail, color: "text-blue-600", bgColor: "bg-blue-100" },
  crm: { label: "CRM", icon: Users, color: "text-purple-600", bgColor: "bg-purple-100" },
  accounting: { label: "Accounting", icon: Receipt, color: "text-amber-600", bgColor: "bg-amber-100" },
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
  const [activeCategory, setActiveCategory] = useState<CategoryFilter>("all");
  
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

  const handleValidate = async (providerId: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
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

  const handleActivate = async (providerId: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    try {
      await api.post(`/oauth/${providerId}/activate`);
      toast.success("Provider activated");
      loadIntegrations();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to activate");
    }
  };

  const handleDeactivate = async (providerId: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    try {
      await api.post(`/oauth/${providerId}/deactivate`);
      toast.success("Provider deactivated");
      loadIntegrations();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to deactivate");
    }
  };

  const handleDisconnect = async (providerId: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
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

  const filteredIntegrations = activeCategory === "all" 
    ? integrations 
    : integrations.filter(i => i.category === activeCategory);

  const getCategoryCounts = () => {
    const counts: Record<string, number> = { all: integrations.length };
    integrations.forEach(i => {
      counts[i.category] = (counts[i.category] || 0) + 1;
    });
    return counts;
  };

  const counts = getCategoryCounts();

  if (loading) {
    return <div className="flex items-center justify-center py-12"><Loader2 className="animate-spin text-slate-400" /></div>;
  }

  return (
    <div className="flex gap-6" data-testid="integrations-overview">
      {/* Sidebar */}
      <div className="w-48 shrink-0">
        <div className="sticky top-4 space-y-1">
          {(["all", "payments", "email", "crm", "accounting"] as CategoryFilter[]).map(cat => {
            const config = CATEGORY_CONFIG[cat];
            const Icon = config.icon;
            const isActive = activeCategory === cat;
            
            return (
              <button
                key={cat}
                onClick={() => setActiveCategory(cat)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-all ${
                  isActive 
                    ? `${config.bgColor} ${config.color} font-medium`
                    : "text-slate-600 hover:bg-slate-50"
                }`}
                data-testid={`category-${cat}`}
              >
                <Icon size={18} className={isActive ? config.color : "text-slate-400"} />
                <span className="text-sm flex-1">{config.label}</span>
                <span className={`text-xs px-1.5 py-0.5 rounded ${isActive ? "bg-white/50" : "bg-slate-100"}`}>
                  {counts[cat] || 0}
                </span>
              </button>
            );
          })}
        </div>
        
        {/* Active Email Provider Status */}
        {activeEmailProvider && (
          <div className="mt-6 p-3 bg-emerald-50 border border-emerald-200 rounded-lg">
            <div className="flex items-center gap-2 mb-1">
              <CheckCircle2 size={14} className="text-emerald-600" />
              <span className="text-xs font-medium text-emerald-700">Active Email</span>
            </div>
            <p className="text-xs text-emerald-600">
              {integrations.find(i => i.id === activeEmailProvider)?.name}
            </p>
          </div>
        )}
      </div>

      {/* Main Content - Tile Grid */}
      <div className="flex-1">
        {/* Header */}
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-slate-800">
            {CATEGORY_CONFIG[activeCategory].label}
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            {activeCategory === "all" 
              ? "Manage all your third-party integrations"
              : activeCategory === "email"
              ? "Only one email provider can be active at a time"
              : `Configure your ${activeCategory} integrations`
            }
          </p>
        </div>

        {/* No Email Provider Warning */}
        {!activeEmailProvider && (activeCategory === "all" || activeCategory === "email") && (
          <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-xl flex items-center gap-3">
            <AlertCircle size={18} className="text-amber-600 shrink-0" />
            <div>
              <p className="text-sm font-medium text-amber-800">No email provider active</p>
              <p className="text-xs text-amber-600">Emails will be stored but not sent. Connect and activate an email provider.</p>
            </div>
          </div>
        )}

        {/* Tiles Grid */}
        <div className="grid grid-cols-2 xl:grid-cols-3 gap-4">
          {filteredIntegrations.map(integration => {
            const Icon = ICON_MAP[integration.icon] || CreditCard;
            const catConfig = CATEGORY_CONFIG[integration.category];
            const isConfigured = integration.status !== "not_connected";
            const canValidate = integration.status === "pending" || integration.status === "failed";
            
            return (
              <div
                key={integration.id}
                className={`relative rounded-xl border-2 p-5 transition-all ${
                  integration.is_coming_soon 
                    ? "bg-slate-50 border-slate-200 opacity-60"
                    : integration.is_validated && integration.is_active
                    ? "bg-gradient-to-br from-emerald-50 to-white border-emerald-300 shadow-sm"
                    : integration.is_validated
                    ? "bg-gradient-to-br from-blue-50 to-white border-blue-200"
                    : isConfigured
                    ? "bg-white border-slate-200 hover:border-slate-300"
                    : "bg-white border-slate-200 hover:border-slate-300 hover:shadow-sm"
                }`}
                data-testid={`tile-${integration.id}`}
              >
                {/* Status Badge - Top Right */}
                <div className="absolute top-3 right-3">
                  {integration.is_coming_soon ? (
                    <span className="text-[10px] px-2 py-1 rounded-full bg-slate-200 text-slate-600 font-medium">
                      COMING SOON
                    </span>
                  ) : integration.is_validated && integration.is_active ? (
                    <span className="text-[10px] px-2 py-1 rounded-full bg-emerald-500 text-white font-medium flex items-center gap-1">
                      <Check size={10} /> ACTIVE
                    </span>
                  ) : integration.is_validated ? (
                    <span className="text-[10px] px-2 py-1 rounded-full bg-blue-500 text-white font-medium flex items-center gap-1">
                      <Check size={10} /> VALIDATED
                    </span>
                  ) : integration.status === "pending" ? (
                    <span className="text-[10px] px-2 py-1 rounded-full bg-amber-100 text-amber-700 font-medium flex items-center gap-1">
                      <Clock size={10} /> PENDING
                    </span>
                  ) : integration.status === "failed" ? (
                    <span className="text-[10px] px-2 py-1 rounded-full bg-red-100 text-red-700 font-medium flex items-center gap-1">
                      <X size={10} /> FAILED
                    </span>
                  ) : null}
                </div>

                {/* Icon & Name */}
                <div className="flex items-start gap-3 mb-3">
                  <div className={`p-3 rounded-xl ${
                    integration.is_validated && integration.is_active
                      ? "bg-emerald-100"
                      : integration.is_validated
                      ? "bg-blue-100"
                      : catConfig.bgColor
                  }`}>
                    <Icon size={22} className={
                      integration.is_validated && integration.is_active
                        ? "text-emerald-600"
                        : integration.is_validated
                        ? "text-blue-600"
                        : catConfig.color
                    } />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-sm font-semibold text-slate-800 truncate">{integration.name}</h3>
                    <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{integration.description}</p>
                  </div>
                </div>

                {/* Data Center Badge for Zoho */}
                {integration.is_zoho && integration.data_center && (
                  <div className="mb-3">
                    <span className="text-[10px] px-2 py-0.5 rounded bg-slate-100 text-slate-500 font-medium">
                      DC: {integration.data_center.toUpperCase()}
                    </span>
                  </div>
                )}

                {/* Error Message */}
                {integration.error_message && (
                  <div className="mb-3 p-2 bg-red-50 rounded-lg">
                    <p className="text-[11px] text-red-600 flex items-start gap-1">
                      <AlertCircle size={12} className="shrink-0 mt-0.5" />
                      <span className="line-clamp-2">{integration.error_message}</span>
                    </p>
                  </div>
                )}

                {/* Actions */}
                <div className="flex items-center gap-2 mt-4 pt-4 border-t border-slate-100">
                  {integration.is_coming_soon ? (
                    <span className="text-xs text-slate-400 italic">Coming Soon</span>
                  ) : !isConfigured ? (
                    <Button
                      size="sm"
                      className="w-full"
                      onClick={() => openConfigDialog(integration)}
                      data-testid={`connect-${integration.id}`}
                    >
                      <Link size={14} className="mr-1.5" /> Connect
                    </Button>
                  ) : (
                    <div className="flex items-center gap-1.5 w-full">
                      {/* Validate / Cancel */}
                      {canValidate && (
                        <>
                          <Button
                            size="sm"
                            variant="outline"
                            className="flex-1"
                            onClick={(e) => handleValidate(integration.id, e)}
                            disabled={validating === integration.id}
                            data-testid={`validate-${integration.id}`}
                          >
                            {validating === integration.id ? (
                              <Loader2 size={14} className="animate-spin" />
                            ) : (
                              <>
                                <Check size={14} className="mr-1" /> Validate
                              </>
                            )}
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-slate-400 hover:text-red-500 px-2"
                            onClick={(e) => handleDisconnect(integration.id, e)}
                            data-testid={`cancel-${integration.id}`}
                            title="Cancel / Disconnect"
                          >
                            <X size={16} />
                          </Button>
                        </>
                      )}
                      
                      {/* Activate / Deactivate for validated email providers */}
                      {integration.is_validated && integration.category === "email" && (
                        integration.is_active ? (
                          <Button
                            size="sm"
                            variant="outline"
                            className="flex-1 text-amber-600 border-amber-200 hover:bg-amber-50"
                            onClick={(e) => handleDeactivate(integration.id, e)}
                            data-testid={`deactivate-${integration.id}`}
                          >
                            <Power size={14} className="mr-1" /> Deactivate
                          </Button>
                        ) : (
                          <Button
                            size="sm"
                            className="flex-1 bg-emerald-600 hover:bg-emerald-700"
                            onClick={(e) => handleActivate(integration.id, e)}
                            data-testid={`activate-${integration.id}`}
                          >
                            <Power size={14} className="mr-1" /> Activate
                          </Button>
                        )
                      )}
                      
                      {/* Edit Button */}
                      {integration.is_validated && (
                        <>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-slate-400 hover:text-slate-600 px-2"
                            onClick={() => openConfigDialog(integration)}
                            data-testid={`edit-${integration.id}`}
                            title="Edit credentials"
                          >
                            <Pencil size={14} />
                          </Button>
                          
                          {/* Settings Button */}
                          {integration.settings.length > 0 && (
                            <Button
                              size="sm"
                              variant="ghost"
                              className="text-slate-400 hover:text-slate-600 px-2"
                              onClick={() => openSettingsDialog(integration)}
                              data-testid={`settings-${integration.id}`}
                              title="Settings"
                            >
                              <Settings size={14} />
                            </Button>
                          )}
                          
                          {/* Disconnect Button */}
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-slate-400 hover:text-red-500 px-2"
                            onClick={(e) => handleDisconnect(integration.id, e)}
                            data-testid={`disconnect-${integration.id}`}
                            title="Disconnect"
                          >
                            <Trash2 size={14} />
                          </Button>
                        </>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Configure Dialog */}
      <Dialog open={showConfigDialog} onOpenChange={setShowConfigDialog}>
        <DialogContent className="max-w-md" data-testid="config-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {selectedIntegration?.status !== "not_connected" ? "Edit" : "Configure"} {selectedIntegration?.name}
            </DialogTitle>
          </DialogHeader>
          
          {selectedIntegration && (
            <div className="space-y-4 py-2 max-h-[60vh] overflow-y-auto">
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
              
              {/* Settings Fields */}
              {selectedIntegration.settings.length > 0 && (
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
              )}
              
              <div className="flex justify-end gap-2 pt-2 sticky bottom-0 bg-white">
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
