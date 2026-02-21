import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { Eye, EyeOff, Upload } from "lucide-react";

interface Settings {
  stripe_public_key?: string;
  stripe_secret_key?: string;
  gocardless_token?: string;
  resend_api_key?: string;
  primary_color?: string;
  secondary_color?: string;
  accent_color?: string;
  logo_url?: string;
  store_name?: string;
}

function SecretInput({ label, value, onChange, placeholder, testId }: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string; testId?: string;
}) {
  const [show, setShow] = useState(false);
  return (
    <div>
      <label className="text-xs text-slate-600">{label}</label>
      <div className="relative mt-1">
        <Input
          type={show ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder || "Enter value…"}
          data-testid={testId}
          className="pr-10"
        />
        <button
          type="button"
          onClick={() => setShow(!show)}
          className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700"
        >
          {show ? <EyeOff size={16} /> : <Eye size={16} />}
        </button>
      </div>
    </div>
  );
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
        <p className="text-xs text-slate-400">These are stored for reference. Apply them to the storefront theme.</p>
        <div className="grid grid-cols-3 gap-4">
          <ColorInput label="Primary" value={settings.primary_color || ""} onChange={set("primary_color")} testId="admin-settings-primary-color" />
          <ColorInput label="Secondary" value={settings.secondary_color || ""} onChange={set("secondary_color")} testId="admin-settings-secondary-color" />
          <ColorInput label="Accent" value={settings.accent_color || ""} onChange={set("accent_color")} testId="admin-settings-accent-color" />
        </div>
      </div>

      {/* API Keys */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
        <h3 className="text-sm font-semibold text-slate-900">API Keys</h3>
        <p className="text-xs text-slate-400">Secrets are masked after saving. To update, type a new value.</p>
        <div className="grid gap-4">
          <div>
            <label className="text-xs text-slate-600">Stripe Public Key</label>
            <Input
              value={settings.stripe_public_key || ""}
              onChange={(e) => set("stripe_public_key")(e.target.value)}
              placeholder="pk_live_…"
              className="mt-1 font-mono text-sm"
              data-testid="admin-settings-stripe-pk"
            />
          </div>
          <SecretInput
            label="Stripe Secret Key"
            value={settings.stripe_secret_key || ""}
            onChange={set("stripe_secret_key")}
            placeholder="sk_live_…"
            testId="admin-settings-stripe-sk"
          />
          <SecretInput
            label="GoCardless Access Token"
            value={settings.gocardless_token || ""}
            onChange={set("gocardless_token")}
            placeholder="live_…"
            testId="admin-settings-gocardless"
          />
          <SecretInput
            label="Resend API Key"
            value={settings.resend_api_key || ""}
            onChange={set("resend_api_key")}
            placeholder="re_…"
            testId="admin-settings-resend"
          />
        </div>
      </div>

      <Button onClick={handleSave} disabled={saving} data-testid="admin-settings-save-btn">
        {saving ? "Saving…" : "Save Settings"}
      </Button>
    </div>
  );
}
