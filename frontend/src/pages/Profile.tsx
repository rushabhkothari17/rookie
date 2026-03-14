import { useEffect, useState, useMemo } from "react";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/contexts/AuthContext";
import { useWebsite } from "@/contexts/WebsiteContext";
import api from "@/lib/api";
import { parseSchema } from "@/components/FormSchemaBuilder";
import { UniversalFormRenderer } from "@/components/UniversalFormRenderer";
import { Download, Lock, Trash2, AlertTriangle } from "lucide-react";

// Auth-only fields — never shown as editable in profile
const AUTH_KEYS = new Set(["email", "password"]);
// Address flat keys
const ADDR_KEYS = new Set(["line1", "line2", "city", "region", "postal", "country"]);
// Core user-model keys saved directly to the user record
const CORE_USER_KEYS = new Set(["full_name", "company_name", "phone", "job_title"]);

export default function Profile() {
  const { user, customer, address, refresh } = useAuth();
  const ws = useWebsite();
  const [form, setForm] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteReason, setDeleteReason] = useState("");
  const [deleting, setDeleting] = useState(false);

  // Parse schema; exclude auth-only fields
  const allSchemaFields = useMemo(() =>
    parseSchema(ws.signup_form_schema)
      .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
      .filter(f => f.enabled !== false && !AUTH_KEYS.has(f.key)),
    [ws.signup_form_schema]
  );

  // Initialise form from ALL schema fields using user / customer / address data
  useEffect(() => {
    if (!user) return;
    const init: Record<string, string> = {};
    for (const field of allSchemaFields) {
      if (field.type === "address") {
        init.line1   = address?.line1   || "";
        init.line2   = address?.line2   || "";
        init.city    = address?.city    || "";
        init.region  = address?.region  || "";
        init.postal  = address?.postal  || "";
        init.country = address?.country || "";
      } else {
        const v = (user as any)[field.key]
          ?? (customer as any)?.[field.key]
          ?? customer?.profile_meta?.[field.key]
          ?? "";
        init[field.key] = v === null ? "" : String(v);
      }
    }
    setForm(init);
  }, [user, customer, address, allSchemaFields]);

  const handleChange = (key: string, value: string) => {
    setForm(prev => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const corePayload: Record<string, string> = {};
      const extraMeta: Record<string, string> = {};
      for (const [k, v] of Object.entries(form)) {
        if (ADDR_KEYS.has(k)) continue;
        if (CORE_USER_KEYS.has(k)) corePayload[k] = v;
        else extraMeta[k] = v;
      }
      await api.put("/me", {
        ...corePayload,
        address: {
          line1: form.line1 || "", line2: form.line2 || "",
          city: form.city || "", region: form.region || "",
          postal: form.postal || "", country: form.country || "",
        },
        ...(Object.keys(extraMeta).length ? { profile_meta: extraMeta } : {}),
      });
      await refresh();
      toast.success("Profile updated");
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Update failed");
    } finally {
      setLoading(false);
    }
  };

  const handleExportData = async () => {
    setExporting(true);
    try {
      const response = await api.get("/me/data-export/download", { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", "my_data_export.zip");
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success("Data export downloaded");
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Export failed");
    } finally {
      setExporting(false);
    }
  };

  const handleDeleteAccount = async () => {
    setDeleting(true);
    try {
      await api.post("/me/request-deletion", { reason: deleteReason, confirm: true });
      toast.success("Account deleted. You will be logged out.");
      setTimeout(() => { window.location.href = "/login"; }, 2000);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Deletion failed");
      setDeleting(false);
    }
  };

  return (
    <div className="space-y-6" data-testid="profile-page">
      <div>
        <p className="text-xs uppercase tracking-[0.3em] text-slate-400">{ws.profile_label}</p>
        <h1 className="mt-2 text-3xl font-semibold text-slate-900">{ws.profile_title}</h1>
        <p className="text-sm text-slate-500">{ws.profile_subtitle}</p>
      </div>

      <form
        onSubmit={handleSubmit}
        noValidate
        className="rounded-3xl bg-white/80 p-8 shadow-[0_20px_50px_rgba(15,23,42,0.08)] backdrop-blur"
        data-testid="profile-form"
      >
        {/* Fixed read-only identity fields — always shown, not in schema */}
        <div className="grid gap-4 md:grid-cols-2 mb-6">
          <div className="space-y-2">
            <div className="flex items-center gap-1.5">
              <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-[0.1em]">Email address</label>
              <Lock size={10} className="text-slate-300" />
            </div>
            <Input
              value={user?.email || ""}
              readOnly
              className="bg-slate-50 cursor-not-allowed text-slate-400 border-dashed"
              data-testid="profile-email-input"
            />
            <p className="text-xs text-slate-400 px-1">Email can only be changed by an admin.</p>
          </div>
          <div className="space-y-2">
            <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-[0.1em]">Partner / Tenant Code</label>
            <div className="flex items-center gap-2">
              <Input
                value={user?.partner_code || "—"}
                readOnly
                className="bg-slate-50 cursor-not-allowed font-mono text-sm border-dashed"
                data-testid="profile-partner-code"
              />
              <span className="text-xs text-slate-400 whitespace-nowrap shrink-0">Read-only</span>
            </div>
          </div>
        </div>

        {/* Schema-driven editable fields — all rendered via UniversalFormRenderer */}
        {allSchemaFields.length > 0 && (
          <UniversalFormRenderer
            fields={allSchemaFields}
            values={form}
            onChange={handleChange}
            compact={false}
            partnerCode={user?.partner_code || undefined}
          />
        )}

        <div className="mt-6 flex items-center justify-end">
          <Button
            type="submit"
            className="rounded-full bg-slate-900 text-white hover:bg-slate-800"
            disabled={loading}
            data-testid="profile-save-button"
          >
            {loading ? "Saving..." : "Save changes"}
          </Button>
        </div>
      </form>

      {/* GDPR / Data Privacy */}
      <details className="mt-8 border-t border-slate-200 pt-6 group">
        <summary className="cursor-pointer text-xs text-slate-400 hover:text-slate-600 transition-colors list-none flex items-center gap-2">
          <span className="text-[10px] uppercase tracking-wider">Advanced Settings</span>
          <svg className="w-3 h-3 transition-transform group-open:rotate-90" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </summary>

        <div className="mt-4">
          <details className="group/gdpr">
            <summary className="cursor-pointer text-xs text-slate-400 hover:text-slate-600 transition-colors list-none flex items-center gap-2">
              <span className="text-[10px] uppercase tracking-wider">Data Privacy (GDPR)</span>
              <svg className="w-3 h-3 transition-transform group-open/gdpr:rotate-90" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </summary>
            <div className="mt-4 space-y-4">
              <p className="text-xs text-slate-500">Manage your personal data. You can export all your data or request account deletion.</p>
              <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg border border-slate-200">
                <div>
                  <p className="text-sm font-medium text-slate-700">Export my data</p>
                  <p className="text-xs text-slate-500">Download all your personal data in a ZIP file</p>
                </div>
                <Button variant="outline" size="sm" onClick={handleExportData} disabled={exporting} data-testid="gdpr-export-btn">
                  <Download className="w-4 h-4 mr-2" />
                  {exporting ? "Exporting..." : "Export Data"}
                </Button>
              </div>
              <div className="p-4 bg-red-50 rounded-lg border border-red-200">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-red-700">Delete my account</p>
                    <p className="text-xs text-red-600">Permanently anonymize all your data. This cannot be undone.</p>
                  </div>
                  <Button variant="destructive" size="sm" onClick={() => setShowDeleteConfirm(true)} data-testid="gdpr-delete-btn">
                    <Trash2 className="w-4 h-4 mr-2" />
                    Delete Account
                  </Button>
                </div>
                {showDeleteConfirm && (
                  <div className="mt-4 p-4 bg-white rounded-lg border border-red-300">
                    <div className="flex items-start gap-3 mb-3">
                      <AlertTriangle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
                      <div>
                        <p className="text-sm font-medium text-red-700">Are you sure?</p>
                        <p className="text-xs text-red-600 mt-1">This will permanently anonymize your account. You will be logged out and cannot recover it.</p>
                      </div>
                    </div>
                    <div className="mb-3">
                      <label className="text-xs font-medium text-slate-600">Reason (optional)</label>
                      <Input value={deleteReason} onChange={e => setDeleteReason(e.target.value)} maxLength={1000} placeholder="Why are you leaving?" className="mt-1" data-testid="gdpr-delete-reason" />
                    </div>
                    <div className="flex gap-2">
                      <Button variant="destructive" size="sm" onClick={handleDeleteAccount} disabled={deleting} data-testid="gdpr-delete-confirm-btn">
                        {deleting ? "Deleting..." : "Yes, delete my account"}
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => setShowDeleteConfirm(false)}>Cancel</Button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </details>
        </div>
      </details>
    </div>
  );
}
