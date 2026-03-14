import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { useWebsite } from "@/contexts/WebsiteContext";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { UniversalFormRenderer } from "@/components/UniversalFormRenderer";
import type { FormField } from "@/components/FormSchemaBuilder";
import { CheckCircle, Clock, AlertCircle, ChevronRight, Download, RefreshCw } from "lucide-react";

const STATUS_META: Record<string, { label: string; icon: React.ReactNode; color: string; desc: string }> = {
  pending:      { label: "Not Started",    icon: <AlertCircle size={16} />, color: "text-slate-400",  desc: "Please complete this form." },
  submitted:    { label: "Under Review",   icon: <Clock size={16} />,       color: "text-amber-500",  desc: "Submitted — waiting for admin review." },
  under_review: { label: "Under Review",   icon: <Clock size={16} />,       color: "text-amber-500",  desc: "Being reviewed by our team." },
  approved:     { label: "Approved",       icon: <CheckCircle size={16} />, color: "text-emerald-500",desc: "Completed and approved." },
  rejected:     { label: "Action Required",icon: <AlertCircle size={16} />, color: "text-red-500",    desc: "Please review and re-submit." },
};

interface IntakeEntry {
  form: { id: string; name: string; description: string; schema: string; auto_approve: boolean };
  record?: {
    id: string; status: string; version: number; responses: Record<string, any>;
    signature_data_url?: string; signature_name?: string; rejection_reason?: string;
    submitted_at?: string;
  };
}

export default function IntakeFormPage() {
  const { user } = useAuth();
  const isAuthenticated = user !== null;
  const ws = useWebsite();
  const navigate = useNavigate();

  const [entries, setEntries] = useState<IntakeEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeFormId, setActiveFormId] = useState<string | null>(null);
  const [formValues, setFormValues] = useState<Record<string, any>>({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!isAuthenticated) { navigate("/login", { state: { from: "/intake-form" } }); return; }
    load();
  }, [isAuthenticated]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get("/portal/intake-forms");
      setEntries(r.data.intake_forms || []);
    } catch { toast.error("Failed to load intake forms"); }
    finally { setLoading(false); }
  }, []);

  const openForm = (entry: IntakeEntry) => {
    const pre: Record<string, any> = { ...(entry.record?.responses || {}) };
    setFormValues(pre);
    setActiveFormId(entry.form.id);
  };

  const submitForm = async (entry: IntakeEntry) => {
    const fields: FormField[] = (() => { try { return JSON.parse(entry.form.schema || "[]"); } catch { return []; } })();

    // Validate required fields
    for (const f of fields) {
      if (!f.enabled || !f.required) continue;
      if (f.type === "signature") {
        if (!formValues["signature_data_url"] && !formValues["signature_name"]) {
          toast.error("Please draw your signature and type your name."); return;
        }
        if (!formValues["signature_name"]) { toast.error("Please type your full name to confirm the signature."); return; }
        if (!formValues["signature_data_url"]) { toast.error("Please draw your signature."); return; }
        continue;
      }
      if (f.type === "terms_conditions") continue;
      const val = formValues[f.key];
      if (!val || (typeof val === "string" && !val.trim())) {
        toast.error(`"${f.label}" is required.`); return;
      }
    }

    setSubmitting(true);
    try {
      await api.post(`/portal/intake-forms/${entry.form.id}/submit`, {
        responses: { ...formValues },
        signature_data_url: formValues["signature_data_url"] || null,
        signature_name: formValues["signature_name"] || null,
      });
      toast.success(entry.form.auto_approve ? "Form submitted and approved!" : "Form submitted — pending review.");
      setActiveFormId(null);
      setFormValues({});
      load();
    } catch (e: any) { toast.error(e?.response?.data?.detail || "Failed to submit form"); }
    finally { setSubmitting(false); }
  };

  const downloadPDF = (entry: IntakeEntry) => {
    const rec = entry.record;
    if (!rec) { toast.error("No record to download"); return; }
    import("jspdf").then(({ jsPDF }) => {
      const doc = new jsPDF();
      doc.setFontSize(20); doc.text(ws.store_name || "Intake Form", 14, 18);
      doc.setFontSize(14); doc.text(entry.form.name, 14, 28);
      doc.setFontSize(10); doc.setTextColor(100);
      doc.text(`Customer: ${user?.full_name || ""}`, 14, 38);
      doc.text(`Status: ${STATUS_META[rec.status]?.label || rec.status}`, 14, 46);
      doc.text(`Submitted: ${rec.submitted_at ? new Date(rec.submitted_at).toLocaleDateString() : "—"}`, 14, 54);
      doc.text(`Version: v${rec.version}`, 14, 62);
      let y = 74;
      doc.setTextColor(0); doc.setFontSize(12); doc.text("Responses", 14, y); y += 8;
      doc.setFontSize(9);
      Object.entries(rec.responses || {}).filter(([k]) => k !== "signature_data_url" && k !== "signature_name").forEach(([k, v]) => {
        const lines = doc.splitTextToSize(`${k}: ${String(v)}`, 180);
        lines.forEach((l: string) => { doc.text(l, 14, y); y += 6; if (y > 270) { doc.addPage(); y = 20; } });
      });
      if (rec.signature_name) { y += 6; doc.setFontSize(10); doc.text(`Digitally signed by: ${rec.signature_name}`, 14, y); y += 8; }
      if (rec.signature_data_url) {
        try { doc.addImage(rec.signature_data_url, "PNG", 14, y, 60, 25); } catch (_) {}
      }
      doc.save(`intake-form-${entry.form.name.replace(/\s/g, "_")}.pdf`);
    }).catch(() => toast.error("PDF generation failed"));
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-current border-t-transparent rounded-full animate-spin" style={{ color: "var(--aa-primary)" }} />
      </div>
    );
  }

  const activeEntry = entries.find(e => e.form.id === activeFormId);

  if (activeEntry) {
    const fields: FormField[] = (() => { try { return JSON.parse(activeEntry.form.schema || "[]"); } catch { return []; } })();
    const rec = activeEntry.record;
    const isRejected = rec?.status === "rejected";

    return (
      <div className="min-h-screen" style={{ backgroundColor: "var(--aa-bg)" }}>
        <div className="max-w-2xl mx-auto px-4 py-8">
          <button
            className="text-xs text-slate-400 hover:text-slate-600 mb-6 flex items-center gap-1 transition-colors"
            onClick={() => { setActiveFormId(null); setFormValues({}); }}
          >
            ← Back to forms
          </button>
          <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm" style={{ backgroundColor: "var(--aa-card)" }}>
            <h1 className="text-xl font-semibold text-slate-900 mb-1" style={{ color: "var(--aa-text)" }}>{activeEntry.form.name}</h1>
            {activeEntry.form.description && <p className="text-sm text-slate-500 mb-6">{activeEntry.form.description}</p>}
            {isRejected && rec?.rejection_reason && (
              <div className="mb-6 bg-red-50 border border-red-200 rounded-xl p-4">
                <p className="text-sm font-medium text-red-700">Your previous submission was rejected</p>
                <p className="text-xs text-red-600 mt-1">{rec.rejection_reason}</p>
                <p className="text-xs text-slate-500 mt-2">Please update your responses and re-submit.</p>
              </div>
            )}
            <UniversalFormRenderer
              fields={fields}
              values={formValues}
              onChange={(k, v) => setFormValues(prev => ({ ...prev, [k]: v }))}
            />
            <div className="mt-8 flex gap-3 justify-end">
              <Button variant="outline" onClick={() => { setActiveFormId(null); setFormValues({}); }}>Cancel</Button>
              <Button
                onClick={() => submitForm(activeEntry)}
                disabled={submitting}
                data-testid="intake-submit-btn"
              >
                {submitting ? "Submitting…" : isRejected ? "Re-submit" : "Submit Form"}
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen" style={{ backgroundColor: "var(--aa-bg)" }}>
      <div className="max-w-2xl mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold" style={{ color: "var(--aa-text)" }}>
            {ws.intake_form_page_title || "Intake Form"}
          </h1>
          <p className="text-sm mt-2" style={{ color: "var(--aa-muted)" }}>
            {ws.intake_form_page_subtitle || "Please complete the following forms before making a purchase."}
          </p>
        </div>

        {entries.length === 0 ? (
          <div className="text-center py-16 border-2 border-dashed border-slate-200 rounded-3xl">
            <CheckCircle size={36} className="mx-auto text-emerald-400 mb-3" />
            <p className="text-sm text-slate-500">No intake forms required at this time.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {entries.map(entry => {
              const rec = entry.record;
              const status = rec?.status || "pending";
              const meta = STATUS_META[status] || STATUS_META["pending"];
              const canFill = status === "pending" || status === "rejected";
              const canReEdit = status === "approved" || status === "submitted" || status === "under_review";

              return (
                <div
                  key={entry.form.id}
                  className="rounded-2xl border border-slate-200 bg-white p-5 flex items-start gap-4 shadow-sm"
                  style={{ backgroundColor: "var(--aa-card)" }}
                  data-testid={`intake-entry-${entry.form.id}`}
                >
                  <div className={`mt-0.5 ${meta.color} shrink-0`}>{meta.icon}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="font-medium text-sm" style={{ color: "var(--aa-text)" }}>{entry.form.name}</p>
                      <Badge className={`text-[10px] px-1.5 ${status === "approved" ? "bg-emerald-50 text-emerald-700" : status === "rejected" ? "bg-red-50 text-red-700" : status === "pending" ? "bg-slate-100 text-slate-600" : "bg-amber-50 text-amber-700"}`}>
                        {meta.label}
                      </Badge>
                      {entry.form.auto_approve && status !== "approved" && (
                        <Badge className="bg-blue-50 text-blue-600 text-[10px] px-1.5">Auto-approved</Badge>
                      )}
                    </div>
                    {entry.form.description && <p className="text-xs text-slate-400 mt-0.5 truncate">{entry.form.description}</p>}
                    <p className="text-xs mt-1" style={{ color: "var(--aa-muted)" }}>{meta.desc}</p>
                    {rec?.rejection_reason && <p className="text-xs text-red-500 mt-1">Reason: {rec.rejection_reason}</p>}
                    {rec?.submitted_at && <p className="text-[11px] text-slate-400 mt-1">Submitted: {new Date(rec.submitted_at).toLocaleDateString()}</p>}
                  </div>
                  <div className="flex flex-col gap-2 shrink-0">
                    {(canFill || canReEdit) && (
                      <Button
                        size="sm"
                        variant={canFill ? "default" : "outline"}
                        onClick={() => openForm(entry)}
                        data-testid={`intake-open-btn-${entry.form.id}`}
                      >
                        {canFill ? (status === "rejected" ? "Update" : "Start") : <><RefreshCw size={12} className="mr-1" />Edit</>}
                        <ChevronRight size={13} className="ml-1" />
                      </Button>
                    )}
                    {rec && status !== "pending" && (
                      <Button size="sm" variant="ghost" onClick={() => downloadPDF(entry)} data-testid={`intake-download-btn-${entry.form.id}`}>
                        <Download size={12} className="mr-1" /> PDF
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {entries.every(e => (e.record?.status === "approved")) && entries.length > 0 && (
          <div className="mt-6 text-center">
            <div className="inline-flex items-center gap-2 bg-emerald-50 border border-emerald-200 rounded-full px-5 py-2.5">
              <CheckCircle size={16} className="text-emerald-500" />
              <span className="text-sm text-emerald-700 font-medium">All forms completed — you're ready to checkout!</span>
            </div>
            <div className="mt-4">
              <Button onClick={() => navigate("/store")} variant="outline">Browse Services</Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
