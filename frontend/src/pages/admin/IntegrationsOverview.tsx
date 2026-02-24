import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/sonner";
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
  ExternalLink,
  ChevronRight,
  Info,
  Copy,
  Plus,
  RefreshCw,
  ArrowRightLeft,
  ChevronDown,
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

interface ZohoModule {
  api_name: string;
  plural_label: string;
  singular_label?: string;
}

interface FieldMapping {
  webapp_field: string;
  crm_field: string;
}

interface CrmMapping {
  id: string;
  webapp_module: string;
  crm_module: string;
  provider?: string;
  field_mappings: FieldMapping[];
  is_active: boolean;
  sync_on_create: boolean;
  sync_on_update: boolean;
}

interface WebappModule {
  name: string;
  label: string;
  fields: string[];
}

interface MappingFormState {
  id?: string;
  webapp_module: string;
  crm_module: string;
  field_mappings: FieldMapping[];
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

// Setup guides for each integration
const SETUP_GUIDES: Record<string, { steps: string[]; links: { label: string; url: string }[]; tips?: string[] }> = {
  stripe: {
    steps: [
      "Log in to your Stripe Dashboard",
      "Go to Developers → API Keys",
      "Copy your Secret Key (starts with sk_live_ or sk_test_)",
      "Optionally copy your Publishable Key for frontend use",
    ],
    links: [
      { label: "Stripe Dashboard", url: "https://dashboard.stripe.com/apikeys" },
      { label: "Stripe Docs", url: "https://stripe.com/docs/keys" },
    ],
    tips: ["Use test keys (sk_test_) for development", "Never expose your secret key in frontend code"],
  },
  gocardless: {
    steps: [
      "Log in to your GoCardless Dashboard",
      "Go to Developers → Create → Access Token",
      "Select 'Read-write access' scope",
      "Copy the generated access token",
    ],
    links: [
      { label: "GoCardless Dashboard", url: "https://manage.gocardless.com/developers/access-tokens" },
      { label: "GoCardless Docs", url: "https://developer.gocardless.com/getting-started" },
    ],
  },
  gocardless_sandbox: {
    steps: [
      "Log in to GoCardless Sandbox",
      "Go to Developers → Create → Access Token",
      "Copy the sandbox access token",
    ],
    links: [
      { label: "GoCardless Sandbox", url: "https://manage-sandbox.gocardless.com/developers/access-tokens" },
    ],
  },
  resend: {
    steps: [
      "Sign up or log in at resend.com",
      "Go to API Keys section",
      "Click 'Create API Key'",
      "Give it a name and select permissions",
      "Copy the generated API key",
    ],
    links: [
      { label: "Resend API Keys", url: "https://resend.com/api-keys" },
      { label: "Resend Docs", url: "https://resend.com/docs" },
    ],
    tips: ["Add and verify your domain for production emails", "Use onboarding@resend.dev for testing"],
  },
  zoho_mail: {
    steps: [
      "Go to Zoho API Console and click 'Self Client' → CREATE",
      "Note your Client ID and Client Secret from the app details",
      "In the 'Generate Code' tab, enter scopes: ZohoMail.messages.CREATE,ZohoMail.accounts.READ",
      "Set Time Duration to 3 minutes, then click CREATE",
      "Copy the Authorization Code shown — paste it in the field below",
      "Click Save & Continue — we'll exchange it for a refresh token automatically",
    ],
    links: [
      { label: "Zoho API Console", url: "https://api-console.zoho.com/" },
      { label: "Zoho Mail API Docs", url: "https://www.zoho.com/mail/help/api/" },
    ],
    tips: [
      "Use 'Self Client' type — not 'Server-based Application'",
      "The Authorization Code expires in minutes — paste and save immediately",
      "Account ID is fetched automatically during validation",
    ],
  },
  zoho_crm: {
    steps: [
      "Go to Zoho API Console and click 'Self Client' → CREATE",
      "Note your Client ID and Client Secret from the app details",
      "In the 'Generate Code' tab, enter scopes: ZohoCRM.modules.ALL,ZohoCRM.settings.ALL",
      "Set Time Duration to 3 minutes, then click CREATE",
      "Copy the Authorization Code shown — paste it in the field below",
      "Click Save & Continue — we'll exchange it for a refresh token automatically",
    ],
    links: [
      { label: "Zoho API Console", url: "https://api-console.zoho.com/" },
      { label: "Zoho CRM API Docs", url: "https://www.zoho.com/crm/developer/docs/api/v3/" },
    ],
    tips: [
      "Use 'Self Client' type — not 'Server-based Application'",
      "Each service (CRM, Mail, Books) needs its OWN authorization code with its own scopes",
      "The Authorization Code expires in minutes — paste and save immediately",
      "Scope mismatch? Re-generate the code with the exact scopes above",
    ],
  },
  zoho_books: {
    steps: [
      "Go to Zoho API Console and click 'Self Client' → CREATE",
      "Note your Client ID and Client Secret from the app details",
      "In the 'Generate Code' tab, enter scopes: ZohoBooks.fullaccess.all",
      "Set Time Duration to 3 minutes, then click CREATE",
      "Copy the Authorization Code shown — paste it in the field below",
      "Click Save & Continue — we'll exchange it for a refresh token automatically",
      "Find your Organization ID: Zoho Books → Settings → Organization Profile",
    ],
    links: [
      { label: "Zoho API Console", url: "https://api-console.zoho.com/" },
      { label: "Zoho Books API Docs", url: "https://www.zoho.com/books/api/v3/" },
    ],
    tips: [
      "Use 'Self Client' type — not 'Server-based Application'",
      "The Authorization Code expires in minutes — paste and save immediately",
      "Organization ID is numeric, e.g. 20098XXXXXXX",
    ],
  },
};

export function IntegrationsOverview() {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [dataCenters, setDataCenters] = useState<DataCenter[]>([]);
  const [activeEmailProvider, setActiveEmailProvider] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeCategory, setActiveCategory] = useState<CategoryFilter>("all");
  
  // Slide panel states
  const [selectedIntegration, setSelectedIntegration] = useState<Integration | null>(null);
  const [panelMode, setPanelMode] = useState<"config" | "settings" | null>(null);
  
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

  const openConfigPanel = (integration: Integration) => {
    setSelectedIntegration(integration);
    setCredentials({});
    setDataCenter(integration.data_center || "us");
    
    const settingsObj: Record<string, string> = {};
    integration.settings.forEach(s => {
      settingsObj[s.key] = integration.stored_settings[s.key] || s.default || "";
    });
    setSettings(settingsObj);
    setPanelMode("config");
  };

  const openSettingsPanel = (integration: Integration) => {
    setSelectedIntegration(integration);
    const settingsObj: Record<string, string> = {};
    integration.settings.forEach(s => {
      settingsObj[s.key] = integration.stored_settings[s.key] || s.default || "";
    });
    setSettings(settingsObj);
    setPanelMode("settings");
  };

  const closePanel = () => {
    setPanelMode(null);
    setSelectedIntegration(null);
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
      closePanel();
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
      closePanel();
      loadIntegrations();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success("Copied to clipboard");
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
  const guide = selectedIntegration ? SETUP_GUIDES[selectedIntegration.id] : null;

  if (loading) {
    return <div className="flex items-center justify-center py-12"><Loader2 className="animate-spin text-slate-400" /></div>;
  }

  return (
    <div className="flex gap-6 relative pb-20" data-testid="integrations-overview">
      {/* Category Sidebar */}
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

      {/* Main Content */}
      <div className="flex-1 min-w-0">
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-slate-800">
            {CATEGORY_CONFIG[activeCategory].label}
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            {activeCategory === "email" 
              ? "Only one email provider can be active at a time"
              : "Manage your third-party integrations"
            }
          </p>
        </div>

        {!activeEmailProvider && (activeCategory === "all" || activeCategory === "email") && (
          <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-xl flex items-center gap-3">
            <AlertCircle size={18} className="text-amber-600 shrink-0" />
            <div>
              <p className="text-sm font-medium text-amber-800">No email provider active</p>
              <p className="text-xs text-amber-600">Emails will be stored but not sent.</p>
            </div>
          </div>
        )}

        {/* Tiles Grid */}
        <div className={`grid gap-4 transition-all ${panelMode ? "grid-cols-1 xl:grid-cols-2" : "grid-cols-2 xl:grid-cols-3"}`}>
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
                    ? "bg-gradient-to-br from-emerald-50 to-white border-emerald-300"
                    : integration.is_validated
                    ? "bg-gradient-to-br from-blue-50 to-white border-blue-200"
                    : "bg-white border-slate-200 hover:border-slate-300"
                }`}
                data-testid={`tile-${integration.id}`}
              >
                {/* Status Badge */}
                <div className="absolute top-3 right-3">
                  {integration.is_coming_soon ? (
                    <span className="text-[10px] px-2 py-1 rounded-full bg-slate-200 text-slate-600 font-medium">COMING SOON</span>
                  ) : integration.is_validated && integration.is_active ? (
                    <span className="text-[10px] px-2 py-1 rounded-full bg-emerald-500 text-white font-medium flex items-center gap-1"><Check size={10} /> ACTIVE</span>
                  ) : integration.is_validated ? (
                    <span className="text-[10px] px-2 py-1 rounded-full bg-blue-500 text-white font-medium flex items-center gap-1"><Check size={10} /> VALIDATED</span>
                  ) : integration.status === "pending" ? (
                    <span className="text-[10px] px-2 py-1 rounded-full bg-amber-100 text-amber-700 font-medium flex items-center gap-1"><Clock size={10} /> PENDING</span>
                  ) : integration.status === "failed" ? (
                    <span className="text-[10px] px-2 py-1 rounded-full bg-red-100 text-red-700 font-medium flex items-center gap-1"><X size={10} /> FAILED</span>
                  ) : null}
                </div>

                {/* Icon & Name */}
                <div className="flex items-start gap-3 mb-3">
                  <div className={`p-3 rounded-xl ${
                    integration.is_validated && integration.is_active ? "bg-emerald-100"
                    : integration.is_validated ? "bg-blue-100"
                    : catConfig.bgColor
                  }`}>
                    <Icon size={22} className={
                      integration.is_validated && integration.is_active ? "text-emerald-600"
                      : integration.is_validated ? "text-blue-600"
                      : catConfig.color
                    } />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-sm font-semibold text-slate-800 truncate">{integration.name}</h3>
                    <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{integration.description}</p>
                  </div>
                </div>

                {integration.is_zoho && integration.data_center && (
                  <div className="mb-3">
                    <span className="text-[10px] px-2 py-0.5 rounded bg-slate-100 text-slate-500 font-medium">
                      DC: {integration.data_center.toUpperCase()}
                    </span>
                  </div>
                )}

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
                      onClick={() => openConfigPanel(integration)}
                      data-testid={`connect-${integration.id}`}
                    >
                      <Link size={14} className="mr-1.5" /> Connect
                    </Button>
                  ) : (
                    <div className="flex items-center gap-1.5 w-full">
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
                              <><Check size={14} className="mr-1" /> Validate</>
                            )}
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-slate-400 hover:text-slate-600 px-2"
                            onClick={() => openConfigPanel(integration)}
                            data-testid={`edit-pending-${integration.id}`}
                            title="Edit credentials"
                          >
                            <Pencil size={14} />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-slate-400 hover:text-red-500 px-2"
                            onClick={(e) => handleDisconnect(integration.id, e)}
                            data-testid={`cancel-${integration.id}`}
                            title="Disconnect"
                          >
                            <X size={16} />
                          </Button>
                        </>
                      )}
                      
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
                      
                      {integration.is_validated && (
                        <>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-slate-400 hover:text-slate-600 px-2"
                            onClick={() => openConfigPanel(integration)}
                            data-testid={`edit-${integration.id}`}
                          >
                            <Pencil size={14} />
                          </Button>
                          
                          {integration.settings.length > 0 && (
                            <Button
                              size="sm"
                              variant="ghost"
                              className="text-slate-400 hover:text-slate-600 px-2"
                              onClick={() => openSettingsPanel(integration)}
                              data-testid={`settings-${integration.id}`}
                            >
                              <Settings size={14} />
                            </Button>
                          )}
                          
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-slate-400 hover:text-red-500 px-2"
                            onClick={(e) => handleDisconnect(integration.id, e)}
                            data-testid={`disconnect-${integration.id}`}
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

      {/* Slide-in Panel */}
      {panelMode && selectedIntegration && (
        <>
          {/* Backdrop */}
          <div 
            className="fixed inset-0 bg-black/20 z-40" 
            onClick={closePanel}
          />
          
          {/* Panel */}
          <div className="fixed top-0 right-0 h-full w-[480px] bg-white shadow-2xl z-50 flex flex-col animate-in slide-in-from-right duration-300">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
              <div>
                <h3 className="text-base font-semibold text-slate-900">
                  {panelMode === "settings"
                    ? `${selectedIntegration.name} Settings`
                    : selectedIntegration.status !== "not_connected"
                    ? `Edit ${selectedIntegration.name}`
                    : `Connect ${selectedIntegration.name}`}
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">{selectedIntegration.description}</p>
              </div>
              <button 
                onClick={closePanel}
                className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
              >
                <X size={18} className="text-slate-400" />
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto">
              {panelMode === "config" && (
                <>
                  {/* Setup Guide */}
                  {guide && (
                    <div className="p-6 bg-gradient-to-b from-blue-50 to-white border-b border-slate-100">
                      <div className="flex items-center gap-2 mb-3">
                        <Info size={16} className="text-blue-600" />
                        <h4 className="text-sm font-semibold text-blue-900">Setup Guide</h4>
                      </div>
                      
                      <ol className="space-y-2 mb-4">
                        {guide.steps.map((step, i) => (
                          <li key={i} className="flex items-start gap-2 text-xs text-blue-800">
                            <span className="flex items-center justify-center w-5 h-5 rounded-full bg-blue-100 text-blue-600 font-medium shrink-0 text-[10px]">
                              {i + 1}
                            </span>
                            <span className="pt-0.5">{step}</span>
                          </li>
                        ))}
                      </ol>
                      
                      {/* Quick Links */}
                      <div className="flex flex-wrap gap-2 mb-3">
                        {guide.links.map((link, i) => (
                          <a
                            key={i}
                            href={link.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-blue-200 rounded-lg text-xs font-medium text-blue-700 hover:bg-blue-50 transition-colors"
                          >
                            {link.label}
                            <ExternalLink size={12} />
                          </a>
                        ))}
                      </div>
                      
                      {/* Tips */}
                      {guide.tips && guide.tips.length > 0 && (
                        <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                          <p className="text-[10px] font-semibold text-amber-700 uppercase tracking-wide mb-1">Tips</p>
                          <ul className="space-y-1">
                            {guide.tips.map((tip, i) => (
                              <li key={i} className="text-xs text-amber-700 flex items-start gap-1.5">
                                <ChevronRight size={12} className="shrink-0 mt-0.5" />
                                {tip}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Credentials Form */}
                  <div className="p-6 space-y-4">
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-semibold text-slate-700">Credentials</h4>
                      {selectedIntegration.status !== "not_connected" && (
                        <span className="text-[11px] text-slate-400 italic">Leave blank to keep existing values</span>
                      )}
                    </div>
                    
                    {/* Zoho Data Center */}
                    {selectedIntegration.is_zoho && (
                      <div>
                        <label className="text-xs font-medium text-slate-700 mb-1.5 block">
                          Data Center <span className="text-red-500">*</span>
                        </label>
                        <Select value={dataCenter} onValueChange={setDataCenter}>
                          <SelectTrigger data-testid="dc-select">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {dataCenters.map(dc => (
                              <SelectItem key={dc.id} value={dc.id}>
                                {dc.name} ({dc.id.toUpperCase()})
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <p className="text-[11px] text-slate-400 mt-1">
                          Select the data center where your Zoho account is hosted
                        </p>
                      </div>
                    )}
                    
                    {/* Credential Fields */}
                    {selectedIntegration.fields.map(field => (
                      <div key={field.key}>
                        <label className="text-xs font-medium text-slate-700 mb-1.5 block">
                          {field.label} {field.required && <span className="text-red-500">*</span>}
                        </label>
                        <div className="relative">
                          <Input
                            type={field.secret ? "password" : "text"}
                            value={credentials[field.key] || ""}
                            onChange={e => setCredentials(prev => ({ ...prev, [field.key]: e.target.value }))}
                            placeholder={field.hint}
                            className="pr-10"
                            data-testid={`field-${field.key}`}
                          />
                          {credentials[field.key] && (
                            <button
                              type="button"
                              onClick={() => copyToClipboard(credentials[field.key])}
                              className="absolute right-2 top-1/2 -translate-y-1/2 p-1 hover:bg-slate-100 rounded"
                            >
                              <Copy size={14} className="text-slate-400" />
                            </button>
                          )}
                        </div>
                        {field.hint && (
                          <p className="text-[11px] text-slate-400 mt-1">{field.hint}</p>
                        )}
                      </div>
                    ))}
                    
                    {/* Settings Fields */}
                    {selectedIntegration.settings.length > 0 && (
                      <div className="pt-4 border-t border-slate-100">
                        <h4 className="text-sm font-semibold text-slate-700 mb-3">Settings</h4>
                        {selectedIntegration.settings.map(setting => (
                          <div key={setting.key} className="mb-3">
                            <label className="text-xs font-medium text-slate-700 mb-1.5 block">
                              {setting.label}
                            </label>
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
                  </div>
                </>
              )}

              {panelMode === "settings" && (
                <div className="p-6 space-y-4">
                  {selectedIntegration.settings.map(setting => (
                    <div key={setting.key}>
                      <label className="text-xs font-medium text-slate-700 mb-1.5 block">
                        {setting.label}
                      </label>
                      <Input
                        value={settings[setting.key] || ""}
                        onChange={e => setSettings(prev => ({ ...prev, [setting.key]: e.target.value }))}
                        placeholder={setting.default || ""}
                        data-testid={`dialog-setting-${setting.key}`}
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="px-6 pt-4 pb-16 border-t border-slate-100 bg-slate-50 flex items-center justify-end gap-3">
              <Button variant="ghost" onClick={closePanel}>
                Cancel
              </Button>
              <Button 
                onClick={panelMode === "settings" ? handleSaveSettings : handleSaveCredentials} 
                disabled={saving}
                data-testid="save-btn"
              >
                {saving ? (
                  <><Loader2 size={14} className="mr-2 animate-spin" /> Saving...</>
                ) : (
                  "Save & Continue"
                )}
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
