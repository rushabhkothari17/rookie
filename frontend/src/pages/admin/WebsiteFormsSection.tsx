import SlideOver from "@/components/admin/SlideOver";
import FormSchemaBuilder from "@/components/FormSchemaBuilder";
import { WebsiteData, FormTile, Field, Section } from "./websiteTabShared";

interface Props {
  ws: WebsiteData;
  s: (key: keyof WebsiteData) => (v: string) => void;
  formSlide: "quote" | "scope" | null;
  setFormSlide: (slide: "quote" | "scope" | null) => void;
  saveSection: (onDone?: () => void) => void;
  slideSaving: boolean;
  setActiveSection: (section: Section) => void;
}

function getFieldCount(schema: string): number {
  try { return JSON.parse(schema || "[]").length; } catch { return 0; }
}

export function FormsSection({ ws, s, formSlide, setFormSlide, saveSection, slideSaving, setActiveSection }: Props) {
  return (
    <>
      <h3 className="text-sm font-semibold text-slate-700 mb-1">Forms</h3>
      <p className="text-xs text-slate-400 mb-4">Click to edit the enquiry form — used across all product enquiry flows.</p>
      <div className="space-y-3">
        <FormTile
          title="Enquiry Form"
          description="Shown when a customer requests a quote or submits an enquiry"
          fieldCount={getFieldCount(ws.scope_form_schema)}
          onEdit={() => setFormSlide("scope")}
          testId="ws-tile-enquiry"
        />
      </div>
      <p className="text-xs text-slate-400 mt-3">
        The customer Sign-up form is managed in{" "}
        <button onClick={() => setActiveSection("auth")} className="text-slate-600 underline">
          Auth &amp; Pages → Sign Up
        </button>.
      </p>

      <SlideOver
        open={formSlide !== null}
        onClose={() => setFormSlide(null)}
        title="Enquiry Form"
        description="Shown across all product enquiry flows — quote requests and scope requests."
        onSave={() => saveSection(() => setFormSlide(null))}
        saving={slideSaving}
      >
        {formSlide === "scope" && (
          <div className="space-y-4">
            <Field label="Form title" value={ws.scope_form_title} onChange={s("scope_form_title")} testId="ws-scope-title" />
            <Field label="Subtitle" value={ws.scope_form_subtitle} onChange={s("scope_form_subtitle")} multiline testId="ws-scope-subtitle" />
            <div className="border-t border-slate-100 pt-3">
              <FormSchemaBuilder title="Form fields" value={ws.scope_form_schema} onChange={s("scope_form_schema")} />
            </div>
          </div>
        )}
      </SlideOver>
    </>
  );
}
