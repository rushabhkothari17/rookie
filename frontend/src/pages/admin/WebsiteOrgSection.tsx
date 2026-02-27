import { useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Upload } from "lucide-react";
import { BrandingData, WebsiteData, BaseCurrencyWidget, ColorInput, Field, OrgAddressSection } from "./websiteTabShared";

interface Props {
  ws: WebsiteData;
  branding: BrandingData;
  s: (key: keyof WebsiteData) => (v: string) => void;
  b: (key: keyof BrandingData) => (v: string) => void;
  save: () => void;
  saving: boolean;
  forcedSection?: boolean;
  uploadingLogo: boolean;
  handleLogoUpload: (e: React.ChangeEvent<HTMLInputElement>) => void;
  handleRemoveLogo: () => void;
  fileRef: React.RefObject<HTMLInputElement>;
}

export function OrgInfoSection({ ws, branding, b, save, saving, forcedSection, uploadingLogo, handleLogoUpload, handleRemoveLogo, fileRef }: Props) {
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
        <h3 className="text-sm font-semibold text-slate-700 mb-1">Brand Colors</h3>
        <p className="text-xs text-slate-400 mb-3">Changes apply across the storefront on next page load.</p>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-4">
            <ColorInput label="Primary — Hero banners, sidebar, buttons" value={branding.primary_color} onChange={b("primary_color")} testId="ws-primary-color" />
            <ColorInput label="Accent — Bullet dots, card accents, hover line" value={branding.accent_color} onChange={b("accent_color")} testId="ws-accent-color" />
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
              <ColorInput label="Background — Page background" value={branding.background_color} onChange={b("background_color")} testId="ws-background-color" />
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
