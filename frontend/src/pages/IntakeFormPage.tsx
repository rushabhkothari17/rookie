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
import { CheckCircle, Clock, AlertCircle, ChevronRight, Download, RefreshCw, AlertTriangle } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

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
  const isAdmin = user?.is_admin || ["platform_admin", "platform_super_admin", "partner_admin", "partner_super_admin"].includes(user?.role ?? "");
  const ws = useWebsite();
  const navigate = useNavigate();

  const [entries, setEntries] = useState<IntakeEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeFormId, setActiveFormId] = useState<string | null>(null);
  const [formValues, setFormValues] = useState<Record<string, any>>({});
  const [submitting, setSubmitting] = useState(false);
  // Gap 5: warn before re-editing an approved form
  const [reEditConfirm, setReEditConfirm] = useState<IntakeEntry | null>(null);

  useEffect(() => {
    if (!isAuthenticated) { navigate("/login", { state: { from: "/intake-form" } }); return; }
    if (isAdmin) return; // admins don't load customer intake forms
    load();
  }, [isAuthenticated, isAdmin]); // eslint-disable-line react-hooks/exhaustive-deps

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get("/portal/intake-forms");
      setEntries(r.data.intake_forms || []);
    } catch { toast.error("Failed to load intake forms"); }
    finally { setLoading(false); }
  }, []);

  const openForm = (entry: IntakeEntry, confirmed = false) => {
    // Gap 5: warn before re-editing an already-approved form
    if (entry.record?.status === "approved" && !confirmed) {
      setReEditConfirm(entry);
      return;
    }
    const pre: Record<string, any> = { ...(entry.record?.responses || {}) };
    // Gap 1: always clear signature on re-edit so the customer must sign fresh
    delete pre["signature_data_url"];
    delete pre["signature_name"];
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
    import("jspdf").then(async ({ jsPDF }) => {
      const doc = new jsPDF();
      const PW = doc.internal.pageSize.getWidth();
      const PH = doc.internal.pageSize.getHeight();
      const M = 14;

      const hexToRgb = (hex: string): [number, number, number] => {
        const r = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex || "");
        return r ? [parseInt(r[1], 16), parseInt(r[2], 16), parseInt(r[3], 16)] : [30, 41, 59];
      };
      const [pr, pg, pb] = hexToRgb(ws.primary_color || "#1e293b");

      // Load logo
      let logoB64: string | null = null;
      if (ws.logo_url) {
        try {
          const res = await fetch(ws.logo_url);
          const blob = await res.blob();
          logoB64 = await new Promise<string>(resolve => { const rd = new FileReader(); rd.onload = () => resolve(rd.result as string); rd.readAsDataURL(blob); });
        } catch (_) {}
      }

      // ── Header band ──
      doc.setFillColor(pr, pg, pb);
      doc.rect(0, 0, PW, 30, "F");
      let hx = M;
      if (logoB64) { try { doc.addImage(logoB64, "JPEG", M, 5, 20, 20); hx = M + 24; } catch (_) {} }
      doc.setTextColor(255, 255, 255);
      doc.setFontSize(13); doc.setFont("helvetica", "bold");
      doc.text(ws.store_name || "Intake Form", hx, 19);

      // ── Form title ──
      doc.setTextColor(30, 41, 59); doc.setFont("helvetica", "bold"); doc.setFontSize(16);
      doc.text(entry.form.name, M, 44);
      doc.setFont("helvetica", "normal"); doc.setFontSize(9); doc.setTextColor(100, 116, 139);
      doc.text(`Customer: ${user?.full_name || ""}`, M, 53);
      doc.text(`Status: ${STATUS_META[rec.status]?.label || rec.status}   ·   Version: v${rec.version}   ·   Submitted: ${rec.submitted_at ? new Date(rec.submitted_at).toLocaleDateString() : "—"}`, M, 60);

      // Divider
      doc.setDrawColor(pr, pg, pb); doc.setLineWidth(0.5);
      doc.line(M, 65, PW - M, 65);

      // ── Responses ──
      let y = 74;
      doc.setFont("helvetica", "bold"); doc.setFontSize(11); doc.setTextColor(30, 41, 59);
      doc.text("Responses", M, y); y += 8;
      const responses = Object.entries(rec.responses || {}).filter(([k]) => k !== "signature_data_url" && k !== "signature_name");
      for (const [k, v] of responses) {
        doc.setFont("helvetica", "bold"); doc.setFontSize(9); doc.setTextColor(71, 85, 105);
        const qLines = doc.splitTextToSize(k, PW - M * 2);
        qLines.forEach((l: string) => { doc.text(l, M, y); y += 5.5; if (y > 265) { doc.addPage(); y = 16; } });
        doc.setFont("helvetica", "normal"); doc.setTextColor(30, 41, 59);
        const aLines = doc.splitTextToSize(String(v ?? "—"), PW - M * 2 - 4);
        aLines.forEach((l: string) => { doc.text(l, M + 4, y); y += 5.5; if (y > 265) { doc.addPage(); y = 16; } });
        y += 2;
      }

      // ── Signature box ──
      if (rec.signature_name || rec.signature_data_url) {
        if (y > 240) { doc.addPage(); y = 16; }
        const boxH = rec.signature_data_url ? 46 : 20;
        doc.setDrawColor(226, 232, 240); doc.setFillColor(248, 250, 252);
        doc.roundedRect(M, y, PW - M * 2, boxH, 2, 2, "FD");
        doc.setFont("helvetica", "bold"); doc.setFontSize(7.5); doc.setTextColor(100, 116, 139);
        doc.text("SIGNATURE", M + 4, y + 7);
        if (rec.signature_data_url) { try { doc.addImage(rec.signature_data_url, "PNG", M + 4, y + 10, 60, 25); } catch (_) {} }
        if (rec.signature_name) {
          doc.setFont("helvetica", "italic"); doc.setFontSize(9); doc.setTextColor(71, 85, 105);
          doc.text(`Digitally signed by: ${rec.signature_name}`, M + 4, rec.signature_data_url ? y + 40 : y + 14);
        }
      }

      // ── Footer ──
      doc.setFont("helvetica", "normal"); doc.setFontSize(7.5); doc.setTextColor(148, 163, 184);
      doc.text(`Generated ${new Date().toLocaleString()} · ${ws.store_name || ""}`, M, PH - 10);

      doc.save(`intake-form-${entry.form.name.replace(/\s/g, "_")}.pdf`);
    }).catch(() => toast.error("PDF generation failed"));
  };

  if (isAdmin) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: "var(--aa-bg)" }}>
        <div className="max-w-md w-full mx-auto px-6 text-center">
          <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
            <AlertTriangle className="h-10 w-10 text-amber-500 mx-auto mb-4" />
            <h2 className="text-lg font-semibold text-slate-900 mb-2">Admin Account Detected</h2>
            <p className="text-sm text-slate-500 mb-6">
              This page is for customer use only. To manage intake forms, visit the Admin Panel.
            </p>
            <Button onClick={() => navigate("/admin?tab=intake-forms")} className="w-full">
              Go to Admin Panel
            </Button>
          </div>
        </div>
      </div>
    );
  }

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
    <>
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

    {/* Gap 5: Re-edit approved form warning dialog */}
    <Dialog open={reEditConfirm !== null} onOpenChange={open => { if (!open) setReEditConfirm(null); }}>
      <DialogContent className="max-w-sm" data-testid="intake-reedit-confirm-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-amber-700">
            <AlertTriangle size={18} className="text-amber-500" />
            Edit Approved Form?
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-1">
          <p className="text-sm text-slate-600">
            This form has already been <strong>approved</strong>. Editing it will:
          </p>
          <ul className="text-sm text-slate-600 space-y-1 list-disc list-inside pl-1">
            <li>Create a <strong>new version</strong> of your submission</li>
            <li>Reset your approval status to <strong>pending review</strong></li>
            <li>Require you to <strong>re-sign</strong> the form</li>
          </ul>
          <p className="text-sm text-slate-500">You will not be able to checkout until the new version is reviewed and approved.</p>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" size="sm" onClick={() => setReEditConfirm(null)}>Cancel</Button>
          <Button
            size="sm"
            className="bg-amber-500 hover:bg-amber-600 text-white"
            onClick={() => { const e = reEditConfirm!; setReEditConfirm(null); openForm(e, true); }}
            data-testid="intake-reedit-confirm-btn"
          >
            Yes, Edit Anyway
          </Button>
        </div>
      </DialogContent>
    </Dialog>
    </>
  );
}
