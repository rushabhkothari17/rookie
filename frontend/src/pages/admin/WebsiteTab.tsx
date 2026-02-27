import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/sonner";
import api from "@/lib/api";
import { Section, WebsiteData, BrandingData, AuthSlide, WEB_DEFAULTS } from "./websiteTabShared";
import { OrgInfoSection } from "./WebsiteOrgSection";
import { AuthPagesSection } from "./WebsiteAuthSection";
import { FormsSection } from "./WebsiteFormsSection";
import { SysConfigSection } from "./WebsiteSysSection";

// ─── Sidebar ──────────────────────────────────────────────────────────────────

const SIDEBAR: { group: string; items: { key: Section; label: string }[] }[] = [
  { group: "Brand", items: [{ key: "branding", label: "Organization Info" }] },
  { group: "Content", items: [
    { key: "auth", label: "Auth & Pages" },
    { key: "forms", label: "Forms" },
  ]},
  { group: "Configuration", items: [
    { key: "sysconfig", label: "System Config" },
  ]},
];

// ─── Main component ───────────────────────────────────────────────────────────

export default function WebsiteTab({ defaultSection, forcedSection }: { defaultSection?: Section; forcedSection?: Section }) {
  const [activeSection, setActiveSection] = useState<Section>(defaultSection ?? "branding");
  const displaySection = forcedSection ?? activeSection;
  const [ws, setWs] = useState<WebsiteData>(WEB_DEFAULTS);
  const [branding, setBranding] = useState<BrandingData>({
    store_name: "", primary_color: "", accent_color: "",
    danger_color: "", success_color: "", warning_color: "",
    background_color: "", text_color: "", border_color: "", muted_color: "",
    logo_url: "",
  });
  const [structured, setStructured] = useState<Record<string, any[]>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [slideSaving, setSlideSaving] = useState(false);
  const [authSlide, setAuthSlide] = useState<AuthSlide | null>(null);
  const [formSlide, setFormSlide] = useState<"quote" | "scope" | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (defaultSection && !forcedSection) setActiveSection(defaultSection);
  }, [defaultSection, forcedSection]);

  const load = async () => {
    setLoading(true);
    try {
      const [webRes, appRes, structRes] = await Promise.all([
        api.get("/admin/website-settings"),
        api.get("/admin/settings"),
        api.get("/admin/settings/structured"),
      ]);
      setWs({ ...WEB_DEFAULTS, ...webRes.data.settings });
      const app_ = appRes.data.settings || {};
      setBranding({
        store_name: app_.store_name || "",
        primary_color: app_.primary_color || "",
        accent_color: app_.accent_color || "",
        danger_color: app_.danger_color || "",
        success_color: app_.success_color || "",
        warning_color: app_.warning_color || "",
        background_color: app_.background_color || "",
        text_color: app_.text_color || "",
        border_color: app_.border_color || "",
        muted_color: app_.muted_color || "",
        logo_url: app_.logo_url || "",
      });
      setStructured(structRes.data.settings || {});
    } catch { toast.error("Failed to load settings"); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const s = (key: keyof WebsiteData) => (v: string) => setWs(prev => ({ ...prev, [key]: v }));
  const b = (key: keyof BrandingData) => (v: string) => setBranding(prev => ({ ...prev, [key]: v }));

  const save = async () => {
    setSaving(true);
    try {
      await Promise.all([
        api.put("/admin/website-settings", ws),
        api.put("/admin/settings", branding),
      ]);
      toast.success("Settings saved");
    } catch { toast.error("Failed to save settings"); }
    finally { setSaving(false); }
  };

  const saveSection = async (onDone?: () => void) => {
    setSlideSaving(true);
    try {
      await api.put("/admin/website-settings", ws);
      toast.success("Saved");
      onDone?.();
    } catch { toast.error("Save failed"); }
    finally { setSlideSaving(false); }
  };

  const handleLogoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingLogo(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await api.post("/admin/upload-logo", formData, { headers: { "Content-Type": "multipart/form-data" } });
      setBranding(prev => ({ ...prev, logo_url: res.data.logo_url }));
      toast.success("Logo uploaded");
    } catch { toast.error("Logo upload failed"); }
    finally { setUploadingLogo(false); if (fileRef.current) fileRef.current.value = ""; }
  };

  const handleRemoveLogo = async () => {
    try {
      await api.put("/admin/settings", { logo_url: "" });
      setBranding(prev => ({ ...prev, logo_url: "" }));
      toast.success("Logo removed");
    } catch { toast.error("Failed to remove logo"); }
  };

  const onStructuredSaved = (key: string, newVal: any) => {
    setStructured(prev => {
      const next = { ...prev };
      Object.keys(next).forEach(cat => {
        next[cat] = next[cat].map(item => item.key === key ? { ...item, value_json: newVal } : item);
      });
      return next;
    });
  };

  if (loading) return <div className="p-8 text-slate-400 text-sm">Loading…</div>;

  return (
    <div data-testid="admin-website-tab">
      {!forcedSection && (
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-bold text-slate-900">Website Settings</h2>
            <p className="text-sm text-slate-500 mt-0.5">Manage all content, branding, forms, and integrations.</p>
          </div>
          <Button onClick={save} disabled={saving} data-testid="website-save-btn">
            {saving ? "Saving…" : "Save Changes"}
          </Button>
        </div>
      )}

      <div className="flex gap-6">
        {/* Sidebar - only shown in standalone mode */}
        {!forcedSection && (
          <div className="w-48 shrink-0 space-y-4">
            {SIDEBAR.map(group => (
              <div key={group.group}>
                <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider px-3 pb-1">{group.group}</p>
                <div className="space-y-0.5">
                  {group.items.map(item => (
                    <button key={item.key} type="button" onClick={() => setActiveSection(item.key)}
                      className={`w-full text-left px-3 py-2 text-sm rounded transition-colors ${activeSection === item.key ? "bg-slate-900 text-white font-medium" : "text-slate-600 hover:bg-slate-100"}`}
                      data-testid={`website-section-${item.key}`}>
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Content panel */}
        <div className="flex-1 min-w-0 border border-slate-100 rounded-xl p-6 bg-white space-y-5">
          {displaySection === "branding" && (
            <OrgInfoSection
              ws={ws} branding={branding} s={s} b={b}
              save={save} saving={saving} forcedSection={!!forcedSection}
              uploadingLogo={uploadingLogo} handleLogoUpload={handleLogoUpload}
              handleRemoveLogo={handleRemoveLogo} fileRef={fileRef}
            />
          )}

          {displaySection === "auth" && (
            <AuthPagesSection
              ws={ws} s={s}
              authSlide={authSlide} setAuthSlide={setAuthSlide}
              saveSection={saveSection} slideSaving={slideSaving}
              setActiveSection={setActiveSection}
            />
          )}

          {displaySection === "forms" && (
            <FormsSection
              ws={ws} s={s}
              formSlide={formSlide} setFormSlide={setFormSlide}
              saveSection={saveSection} slideSaving={slideSaving}
              setActiveSection={setActiveSection}
            />
          )}

          {displaySection === "sysconfig" && (
            <SysConfigSection
              structured={structured}
              onStructuredSaved={onStructuredSaved}
            />
          )}
        </div>
      </div>
    </div>
  );
}
