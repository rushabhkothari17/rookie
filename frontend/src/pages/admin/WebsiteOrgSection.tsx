import { useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Upload, RotateCcw, Zap } from "lucide-react";
import { BrandingData, WebsiteData, BaseCurrencyWidget, ColorInput, Field, OrgAddressSection } from "./websiteTabShared";

export const DEFAULT_BRAND_COLORS: Partial<BrandingData> = {
  primary_color:    "#0f172a",
  accent_color:     "#1e40af",
  background_color: "#f8fafc",
  card_color:       "#ffffff",
  surface_color:    "#f1f5f9",
  text_color:       "#0f172a",
  border_color:     "#e2e8f0",
  danger_color:     "#dc2626",
  success_color:    "#16a34a",
  warning_color:    "#d97706",
  muted_color:      "#64748b",
};

// ── Theme Presets ─────────────────────────────────────────────
const THEME_PRESETS: { name: string; desc: string; swatches: string[]; colors: Partial<BrandingData> }[] = [
  {
    name: "Midnight Tech",
    desc: "Dark · Electric blue · Futuristic",
    swatches: ["#161b22", "#58a6ff", "#0d1117", "#21262d"],
    colors: {
      primary_color:    "#161b22",   // hero bg — distinctly above page bg
      accent_color:     "#58a6ff",   // GitHub-dark bright blue
      background_color: "#0d1117",   // page bg — deepest layer
      card_color:       "#0d1117",   // cards same plane as page (flat look)
      surface_color:    "#21262d",   // elevated rows, table headers
      text_color:       "#e6edf3",   // near-white readable text
      border_color:     "#30363d",   // visible but subtle borders
      danger_color:     "#f85149",
      success_color:    "#3fb950",
      warning_color:    "#d29922",
      muted_color:      "#8b949e",
    },
  },
  {
    name: "Slate Pro",
    desc: "Light · Navy · Professional",
    swatches: ["#0f172a", "#2563eb", "#ffffff", "#f8fafc"],
    colors: { ...DEFAULT_BRAND_COLORS, accent_color: "#2563eb" },
  },
  {
    name: "Ocean Deep",
    desc: "Dark · Teal · Modern",
    swatches: ["#1a3d50", "#06b6d4", "#0c2233", "#1a3d50"],
    colors: {
      primary_color:    "#1a3d50",   // hero bg — teal-navy elevated
      accent_color:     "#06b6d4",   // cyan/teal accent
      background_color: "#0c2233",   // page bg — dark ocean blue
      card_color:       "#0c2233",   // cards flat to page
      surface_color:    "#1a3d50",   // elevated surfaces
      text_color:       "#cae6f0",   // light blue-white text
      border_color:     "#1e5070",   // visible teal-dark borders
      danger_color:     "#fb7185",
      success_color:    "#34d399",
      warning_color:    "#fbbf24",
      muted_color:      "#67a3b5",
    },
  },
];

interface Props {
  ws: WebsiteData;
  branding: BrandingData;
  s: (key: keyof WebsiteData) => (v: string) => void;
  b: (key: keyof BrandingData) => (v: string) => void;
  onResetColors: () => void;
  onApplyPreset: (colors: Partial<BrandingData>) => void;
  save: () => void;
  saving: boolean;
  forcedSection?: boolean;
  uploadingLogo: boolean;
  handleLogoUpload: (e: React.ChangeEvent<HTMLInputElement>) => void;
  handleRemoveLogo: () => void;
  fileRef: React.RefObject<HTMLInputElement>;
}

export function OrgInfoSection({ ws, branding, b, onResetColors, onApplyPreset, save, saving, forcedSection, uploadingLogo, handleLogoUpload, handleRemoveLogo, fileRef }: Props) {
  return (
    <>
      <h3 className="text-sm font-semibold text-slate-700">Store Information</h3>
      <Field label="Store Name" value={branding.store_name} onChange={b("store_name")} testId="ws-store-name" />
      <BaseCurrencyWidget />
      <OrgAddressSection />
      <div className="border-t border-slate-100 pt-4">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Logo</h3>
        {branding.logo_url ? (
          <div className="flex items-center gap-4">
            <img src={branding.logo_url} alt="Logo" className="h-14 w-auto object-contain border border-slate-200 rounded-lg p-2 bg-slate-50" data-testid="ws-logo-preview" />
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()} disabled={uploadingLogo}>Replace</Button>
              <Button variant="ghost" size="sm" className="text-red-500" onClick={handleRemoveLogo}>Remove</Button>
            </div>
          </div>
        ) : (
          <div className="border-2 border-dashed border-slate-200 rounded-xl p-8 text-center cursor-pointer hover:border-slate-400 transition-colors" onClick={() => fileRef.current?.click()} data-testid="ws-logo-dropzone">
            <Upload size={24} className="mx-auto text-slate-400 mb-2" />
            <p className="text-sm text-slate-500">Click to upload logo</p>
            <p className="text-xs text-slate-400 mt-1">PNG, JPG, SVG — max 2MB</p>
          </div>
        )}
        <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handleLogoUpload} data-testid="ws-logo-input" />
      </div>
      <div className="border-t border-slate-100 pt-4">
        <div className="flex items-center justify-between mb-1">
          <h3 className="text-sm font-semibold text-slate-700">Brand Colors</h3>
          <Button
            variant="ghost"
            size="sm"
            className="text-xs text-slate-500 h-7 px-2 gap-1.5"
            onClick={onResetColors}
            data-testid="ws-reset-colors-btn"
          >
            <RotateCcw size={11} />
            Reset to default
          </Button>
        </div>
        <p className="text-xs text-slate-400 mb-4">Changes apply live as you edit. Click Save to persist.</p>

        {/* ── Theme Presets ── */}
        <div className="mb-4">
          <p className="text-[11px] text-slate-400 mb-2 font-medium uppercase tracking-wide flex items-center gap-1.5">
            <Zap size={10} />
            Quick Themes
          </p>
          <div className="grid grid-cols-3 gap-2" data-testid="theme-presets">
            {THEME_PRESETS.map((preset) => (
              <button
                key={preset.name}
                type="button"
                onClick={() => onApplyPreset(preset.colors)}
                className="group relative flex flex-col gap-1.5 p-2.5 rounded-lg border border-slate-200 hover:border-slate-400 bg-white hover:bg-slate-50 transition-all text-left"
                data-testid={`theme-preset-${preset.name.toLowerCase().replace(/\s+/g, "-")}`}
              >
                {/* Color swatches */}
                <div className="flex gap-1">
                  {preset.swatches.map((color, i) => (
                    <div
                      key={i}
                      className="h-3.5 w-3.5 rounded-full border border-white shadow-sm flex-shrink-0"
                      style={{ backgroundColor: color }}
                    />
                  ))}
                </div>
                <div>
                  <div className="text-[11px] font-semibold text-slate-700 leading-tight">{preset.name}</div>
                  <div className="text-[10px] text-slate-400 leading-tight mt-0.5">{preset.desc}</div>
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-4">
            <ColorInput label="Primary — Hero banners, sidebar, buttons" value={branding.primary_color} onChange={b("primary_color")} testId="ws-primary-color" />
            <ColorInput label="Accent — Bullets, active states, links" value={branding.accent_color} onChange={b("accent_color")} testId="ws-accent-color" />
          </div>
          <div className="border-t border-slate-50 pt-2">
            <p className="text-[11px] text-slate-400 mb-2 font-medium uppercase tracking-wide">System / State Colors</p>
            <div className="grid grid-cols-3 gap-3">
              <ColorInput label="Danger — Errors, destructive actions" value={branding.danger_color} onChange={b("danger_color")} testId="ws-danger-color" />
              <ColorInput label="Success — Confirmations, success states" value={branding.success_color} onChange={b("success_color")} testId="ws-success-color" />
              <ColorInput label="Warning — Cautions, pending states" value={branding.warning_color} onChange={b("warning_color")} testId="ws-warning-color" />
            </div>
          </div>
          <div className="border-t border-slate-50 pt-2">
            <p className="text-[11px] text-slate-400 mb-2 font-medium uppercase tracking-wide">Surface Colors</p>
            <div className="grid grid-cols-2 gap-3">
              <ColorInput label="Page Background" value={branding.background_color} onChange={b("background_color")} testId="ws-background-color" />
              <ColorInput label="Card Background" value={branding.card_color} onChange={b("card_color")} testId="ws-card-color" />
              <ColorInput label="Surface — Elevated panels, rows" value={branding.surface_color} onChange={b("surface_color")} testId="ws-surface-color" />
              <ColorInput label="Text — Body text, headings" value={branding.text_color} onChange={b("text_color")} testId="ws-text-color" />
              <ColorInput label="Border — Dividers, input borders" value={branding.border_color} onChange={b("border_color")} testId="ws-border-color" />
              <ColorInput label="Muted — Placeholder, subtle text" value={branding.muted_color} onChange={b("muted_color")} testId="ws-muted-color" />
            </div>
          </div>
        </div>
      </div>
      {forcedSection && (
        <div className="border-t border-slate-100 pt-4 flex justify-end">
          <Button onClick={save} disabled={saving} data-testid="org-info-save-btn">
            {saving ? "Saving…" : "Save Changes"}
          </Button>
        </div>
      )}
    </>
  );
}
