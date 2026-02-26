import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { Eye, EyeOff, Upload, Save, X } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

const COUNTRIES = [
  {v:"Canada",l:"Canada"},{v:"USA",l:"United States"},{v:"UK",l:"United Kingdom"},
  {v:"Australia",l:"Australia"},{v:"India",l:"India"},{v:"Germany",l:"Germany"},
  {v:"France",l:"France"},{v:"Netherlands",l:"Netherlands"},{v:"Singapore",l:"Singapore"},
  {v:"New Zealand",l:"New Zealand"},
];

function OrgAddressSection() {
  const { user } = useAuth();
  const [tenantId, setTenantId] = useState("");
  const [addr, setAddr] = useState({ line1:"", line2:"", city:"", region:"", postal:"", country:"Canada" });
  const [provinces, setProvinces] = useState<{value:string;label:string}[]>([]);
  const [saving, setSaving] = useState(false);
  const isPlatformAdmin = user?.role && ["platform_admin", "admin"].includes(user.role);
  // Don't show for platform admins (no org address for the platform tenant)
  if (isPlatformAdmin) return null;

  useEffect(() => {
    api.get("/admin/tenants/my").then(r => {
      setTenantId(r.data.tenant?.id || "");
      const a = r.data.tenant?.address || {};
      setAddr({ line1: a.line1||"", line2: a.line2||"", city: a.city||"", region: a.region||"", postal: a.postal||"", country: a.country||"Canada" });
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (addr.country === "Canada" || addr.country === "USA") {
      api.get(`/utils/provinces?country_code=${addr.country}`).then(r => setProvinces(r.data.regions || [])).catch(() => setProvinces([]));
    } else { setProvinces([]); }
  }, [addr.country]);

  const save = async () => {
    if (!tenantId) return;
    setSaving(true);
    try {
      await api.put(`/admin/tenants/${tenantId}/address`, { address: addr });
      toast.success("Organization address saved");
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to save address");
    } finally { setSaving(false); }
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4" data-testid="org-address-section">
      <h3 className="text-sm font-semibold text-slate-900">Organization Address</h3>
      <p className="text-xs text-slate-400">Your organization's registered address. Used on invoices and tax documents.</p>
      <div className="space-y-2">
        <Input placeholder="Line 1 *" value={addr.line1} onChange={e => setAddr(p=>({...p,line1:e.target.value}))} required data-testid="org-addr-line1" />
        <Input placeholder="Line 2 (optional)" value={addr.line2} onChange={e => setAddr(p=>({...p,line2:e.target.value}))} data-testid="org-addr-line2" />
        <div className="grid grid-cols-2 gap-2">
          <Input placeholder="City *" value={addr.city} onChange={e => setAddr(p=>({...p,city:e.target.value}))} required data-testid="org-addr-city" />
          <Input placeholder="Postal Code *" value={addr.postal} onChange={e => setAddr(p=>({...p,postal:e.target.value}))} required data-testid="org-addr-postal" />
        </div>
        <Select value={addr.country} onValueChange={v => setAddr(p=>({...p,country:v,region:""}))}>
          <SelectTrigger data-testid="org-addr-country"><SelectValue placeholder="Country *" /></SelectTrigger>
          <SelectContent>{COUNTRIES.map(c=><SelectItem key={c.v} value={c.v}>{c.l}</SelectItem>)}</SelectContent>
        </Select>
        {provinces.length > 0 ? (
          <Select value={addr.region} onValueChange={v => setAddr(p=>({...p,region:v}))}>
            <SelectTrigger data-testid="org-addr-region-select"><SelectValue placeholder="Province / State *" /></SelectTrigger>
            <SelectContent>{provinces.map(p=><SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}</SelectContent>
          </Select>
        ) : (
          <Input placeholder="State / Province *" value={addr.region} onChange={e => setAddr(p=>({...p,region:e.target.value}))} required data-testid="org-addr-region-input" />
        )}
      </div>
      <Button onClick={save} disabled={saving} size="sm" data-testid="org-addr-save-btn">
        {saving ? "Saving…" : "Save Address"}
      </Button>
    </div>
  );
}


interface Settings {
  primary_color?: string;
  accent_color?: string;
  logo_url?: string;
  store_name?: string;
}

function ColorInput({ label, value, onChange, testId }: {
  label: string; value: string; onChange: (v: string) => void; testId?: string;
}) {
  return (
    <div>
      <label className="text-xs text-slate-600">{label}</label>
      <div className="flex items-center gap-2 mt-1">
        <input
          type="color"
          value={value || "#000000"}
          onChange={(e) => onChange(e.target.value)}
          className="w-10 h-10 rounded cursor-pointer border border-slate-200"
          data-testid={testId}
        />
        <Input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="#000000"
          className="w-32 font-mono text-sm"
        />
      </div>
    </div>
  );
}

function SettingRow({ item, onSaved }: { item: any; onSaved: (key: string, newVal: any) => void }) {
  const [editVal, setEditVal] = useState<string>("");
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showSecret, setShowSecret] = useState(false);

  const isBool = item.value_type === "bool";
  const isNumber = item.value_type === "number";
  const isSecret = item.is_secret || item.value_type === "secret";

  const displayVal = String(item.value_json ?? "");

  const startEdit = () => {
    setEditVal(displayVal);
    setIsEditing(true);
  };
  const cancelEdit = () => { setIsEditing(false); setShowSecret(false); };

  const handleSave = async () => {
    setSaving(true);
    try {
      let valueToSave: any = editVal;
      if (isBool) valueToSave = editVal === "true";
      if (isNumber) valueToSave = parseFloat(editVal);
      await api.put(`/admin/settings/key/${item.key}`, { value: valueToSave });
      toast.success(`'${item.key}' saved`);
      onSaved(item.key, valueToSave);
      setIsEditing(false);
      setShowSecret(false);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleBoolToggle = async (checked: boolean) => {
    setSaving(true);
    try {
      await api.put(`/admin/settings/key/${item.key}`, { value: checked });
      toast.success(`'${item.key}' updated`);
      onSaved(item.key, checked);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex items-start gap-3 py-2 border-b border-slate-100 last:border-0">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-xs font-mono font-medium text-slate-700">{item.key}</span>
          {isSecret && <span className="text-[10px] text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded">secret</span>}
          {isNumber && <span className="text-[10px] text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">number</span>}
        </div>
        {item.description && <p className="text-xs text-slate-400 mb-1">{item.description}</p>}

        {isBool ? (
          <div className="flex items-center gap-2">
            <button
              role="switch"
              aria-checked={item.value_json === true || item.value_json === "true"}
              onClick={() => handleBoolToggle(!(item.value_json === true || item.value_json === "true"))}
              disabled={saving}
              data-testid={`setting-toggle-${item.key}`}
              className={`relative inline-flex h-5 w-9 items-center rounded-full border-2 border-transparent transition-colors focus:outline-none disabled:opacity-50 ${
                (item.value_json === true || item.value_json === "true") ? "bg-primary" : "bg-input"
              }`}
            >
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                (item.value_json === true || item.value_json === "true") ? "translate-x-4" : "translate-x-0"
              }`} />
            </button>
            <span className="text-xs text-slate-500">{(item.value_json === true || item.value_json === "true") ? "Enabled" : "Disabled"}</span>
          </div>
        ) : isEditing ? (
          <div className="flex items-center gap-2">
            <div className="relative">
              <Input
                type={isSecret && !showSecret ? "password" : isNumber ? "number" : "text"}
                value={editVal}
                onChange={(e) => setEditVal(e.target.value)}
                className="h-7 text-xs font-mono w-72 pr-7"
                autoFocus
                data-testid={`setting-input-${item.key}`}
              />
              {isSecret && (
                <button
                  type="button"
                  onClick={() => setShowSecret(!showSecret)}
                  className="absolute right-2 top-1.5 text-slate-400 hover:text-slate-600"
                >
                  {showSecret ? <EyeOff size={12} /> : <Eye size={12} />}
                </button>
              )}
            </div>
            <Button size="sm" className="h-7 px-2 text-xs gap-1" onClick={handleSave} disabled={saving} data-testid={`setting-save-${item.key}`}>
              <Save size={10} /> {saving ? "…" : "Save"}
            </Button>
            <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={cancelEdit} disabled={saving}>
              <X size={10} />
            </Button>
          </div>
        ) : (
          <button
            onClick={startEdit}
            className="text-left text-xs font-mono text-slate-600 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded px-2 py-1 max-w-md w-full truncate transition-colors"
            data-testid={`setting-display-${item.key}`}
          >
            {isSecret ? "••••••••" : displayVal || <span className="text-slate-300 italic">not set</span>}
          </button>
        )}
      </div>
    </div>
  );
}

function SystemConfigSection() {
  const [grouped, setGrouped] = useState<Record<string, any[]>>({});
  const [loading, setLoading] = useState(true);

  const loadSettings = () => {
    setLoading(true);
    api.get("/admin/settings/structured").then((res) => {
      setGrouped(res.data.settings || {});
    }).catch(() => toast.error("Failed to load system config")).finally(() => setLoading(false));
  };

  useEffect(() => { loadSettings(); }, []);

  const handleSaved = (key: string, newVal: any) => {
    setGrouped((prev) => {
      const next = { ...prev };
      Object.keys(next).forEach((cat) => {
        next[cat] = next[cat].map((item) =>
          item.key === key ? { ...item, value_json: newVal } : item
        );
      });
      return next;
    });
  };

  if (loading) return <div className="text-xs text-slate-400 py-4">Loading system config…</div>;
  if (!Object.keys(grouped).length) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold text-slate-900">System Configuration</h3>
        <span className="text-xs text-slate-400 bg-slate-100 px-2 py-0.5 rounded">DB-backed · click a value to edit</span>
      </div>
      {Object.entries(grouped).map(([category, items]) => (
        <div key={category} className="rounded-xl border border-slate-200 bg-white p-5">
          <h4 className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-3">{category}</h4>
          <div>
            {items.map((item: any) => (
              <SettingRow key={item.key} item={item} onSaved={handleSaved} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export function SettingsTab() {
  const [settings, setSettings] = useState<Settings>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get("/admin/settings");
      setSettings(res.data.settings || {});
    } catch {
      toast.error("Failed to load settings");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const set = (key: keyof Settings) => (v: string) => setSettings((s) => ({ ...s, [key]: v }));

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put("/admin/settings", settings);
      toast.success("Settings saved");
      load();
    } catch {
      toast.error("Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  const handleLogoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingLogo(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await api.post("/admin/upload-logo", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setSettings((s) => ({ ...s, logo_url: res.data.logo_url }));
      toast.success("Logo uploaded");
    } catch {
      toast.error("Logo upload failed");
    } finally {
      setUploadingLogo(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const handleRemoveLogo = async () => {
    try {
      await api.put("/admin/settings", { logo_url: "" });
      setSettings((s) => ({ ...s, logo_url: "" }));
      toast.success("Logo removed");
    } catch {
      toast.error("Failed to remove logo");
    }
  };

  if (loading) return <div className="text-slate-400 p-4">Loading settings…</div>;

  return (
    <div className="space-y-6 max-w-2xl" data-testid="admin-settings-panel">

      {/* Store Info */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
        <h3 className="text-sm font-semibold text-slate-900">Store Information</h3>
        <div>
          <label className="text-xs text-slate-600">Store Name</label>
          <Input
            value={settings.store_name || ""}
            onChange={(e) => set("store_name")(e.target.value)}
            placeholder="Automate Accounts"
            className="mt-1"
            data-testid="admin-settings-store-name"
          />
        </div>
      </div>

      {/* Logo */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
        <h3 className="text-sm font-semibold text-slate-900">Logo</h3>
        {settings.logo_url ? (
          <div className="flex items-center gap-4">
            <img
              src={settings.logo_url}
              alt="Store logo"
              className="h-14 w-auto object-contain border border-slate-200 rounded-lg p-2 bg-slate-50"
              data-testid="admin-settings-logo-preview"
            />
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()} disabled={uploadingLogo}>
                Replace
              </Button>
              <Button variant="ghost" size="sm" className="text-red-500" onClick={handleRemoveLogo}>
                Remove
              </Button>
            </div>
          </div>
        ) : (
          <div
            className="border-2 border-dashed border-slate-200 rounded-xl p-8 text-center cursor-pointer hover:border-slate-400 transition-colors"
            onClick={() => fileRef.current?.click()}
            data-testid="admin-settings-logo-dropzone"
          >
            <Upload size={24} className="mx-auto text-slate-400 mb-2" />
            <p className="text-sm text-slate-500">Click to upload logo</p>
            <p className="text-xs text-slate-400 mt-1">PNG, JPG, SVG — max 2MB</p>
          </div>
        )}
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={handleLogoUpload}
          data-testid="admin-settings-logo-input"
        />
      </div>

      {/* Brand Colors */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
        <h3 className="text-sm font-semibold text-slate-900">Brand Colors</h3>
        <p className="text-xs text-slate-400">Applied to the storefront in real-time. Primary = navbars/headings. Accent = CTA buttons &amp; highlights.</p>
        <div className="grid grid-cols-2 gap-4">
          <ColorInput label="Primary" value={settings.primary_color || ""} onChange={set("primary_color")} testId="admin-settings-primary-color" />
          <ColorInput label="Accent" value={settings.accent_color || ""} onChange={set("accent_color")} testId="admin-settings-accent-color" />
        </div>
      </div>

      <Button onClick={handleSave} disabled={saving} data-testid="admin-settings-save-btn">
        {saving ? "Saving…" : "Save Settings"}
      </Button>

      {/* Organization Address (partner admins only) */}
      <OrgAddressSection />

      {/* System Configuration (DB-backed, categorized) */}
      <div className="border-t border-slate-200 pt-6">
        <SystemConfigSection />
      </div>
    </div>
  );
}
