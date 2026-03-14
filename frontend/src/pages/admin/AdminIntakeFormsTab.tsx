import { useState, useEffect, useCallback } from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import FormSchemaBuilder from "@/components/FormSchemaBuilder";
import type { FormField } from "@/components/FormSchemaBuilder";
import { ColHeader } from "@/components/shared/ColHeader";
import type { SortDirection } from "@/components/shared/ColHeader";
import api from "@/lib/api";
import { toast } from "sonner";
import { useAuth } from "@/contexts/AuthContext";
import { useWebsite } from "@/contexts/WebsiteContext";
import { ProductConditionBuilder, ProductVisRuleSet } from "@/pages/admin/ProductForm";
import {
  Plus, Pencil, Trash2, Eye, Download, FileText, StickyNote, History, ChevronDown, ChevronUp, Settings2, ToggleLeft, ToggleRight, X, Check, Clock, AlertCircle
} from "lucide-react";

// ── Types ────────────────────────────────────────────────────────────────────

interface VisibilityRule { field: string; operator: string; value: string; }

interface IntakeForm {
  id: string; tenant_id: string; name: string; description: string;
  schema: string; is_enabled: boolean; auto_approve: boolean;
  allow_skip_signature: boolean; visibility_rules: VisibilityRule[];
  customer_ids: string[]; created_at: string; partner_code?: string;
}

interface IntakeRecord {
  id: string; tenant_id: string; intake_form_id: string; intake_form_name: string;
  customer_id: string; customer_name: string; customer_email: string;
  responses: Record<string, any>; signature_data_url?: string; signature_name?: string;
  status: string; version: number; admin_created: boolean; signature_skipped: boolean;
  submitted_at?: string; reviewed_at?: string; reviewed_by?: string;
  rejection_reason?: string; notes: NoteEntry[]; created_at: string; partner_code?: string;
}

interface NoteEntry { id: string; text: string; author: string; created_at: string; updated_at: string; }
interface VersionEntry { version: number; responses: Record<string, any>; signature_data_url?: string; signature_name?: string; status: string; submitted_at?: string; archived_at: string; }

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-slate-100 text-slate-600",
  submitted: "bg-blue-50 text-blue-700",
  under_review: "bg-amber-50 text-amber-700",
  approved: "bg-emerald-50 text-emerald-700",
  rejected: "bg-red-50 text-red-700",
};

const STATUS_LABELS: Record<string, string> = {
  pending: "Pending", submitted: "Submitted", under_review: "Under Review",
  approved: "Approved", rejected: "Rejected",
};

// ── System locked fields that appear in every intake form record ──────────────
const SYSTEM_LOCKED_FIELDS: FormField[] = [
  { id: "sys_customer_name", key: "customer_name", label: "Customer Name", type: "text", required: true, placeholder: "", options: [], locked: true, enabled: true, order: -4 },
  { id: "sys_customer_email", key: "customer_email", label: "Customer Email", type: "email", required: true, placeholder: "", options: [], locked: true, enabled: true, order: -3 },
  { id: "sys_submission_date", key: "submitted_at", label: "Submission Date", type: "date", required: false, placeholder: "", options: [], locked: true, enabled: true, order: -2 },
  { id: "sys_status", key: "status", label: "Status", type: "text", required: false, placeholder: "", options: [], locked: true, enabled: true, order: -1 },
];

// ── Form Builder sub-tab ──────────────────────────────────────────────────────

function IntakeFormBuilder({ isPlatformAdmin }: { isPlatformAdmin: boolean }) {
  const [forms, setForms] = useState<IntakeForm[]>([]);
  const [loading, setLoading] = useState(true);
  const [showEditor, setShowEditor] = useState(false);
  const [editingForm, setEditingForm] = useState<IntakeForm | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [allCustomers, setAllCustomers] = useState<any[]>([]);
  const [customerSearch, setCustSearch] = useState("");

  // Editor state
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [schema, setSchema] = useState<FormField[]>([]);
  const [isEnabled, setIsEnabled] = useState(true);
  const [autoApprove, setAutoApprove] = useState(false);
  const [allowSkipSig, setAllowSkipSig] = useState(false);
  const [visMode, setVisMode] = useState<"all" | "specific" | "conditional">("all");
  const [customerIds, setCustomerIds] = useState<string[]>([]);
  const [visibilityConditions, setVisibilityConditions] = useState<ProductVisRuleSet | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try { const r = await api.get("/admin/intake-forms"); setForms(r.data.forms); }
    catch { toast.error("Failed to load intake forms"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    api.get("/admin/customers?page=1&limit=500").then(r => setAllCustomers(r.data.customers || [])).catch(() => {});
  }, []);

  const resetEditor = () => {
    setName(""); setDescription(""); setSchema([]); setIsEnabled(true);
    setAutoApprove(false); setAllowSkipSig(false);
    setVisMode("all"); setCustomerIds([]); setVisibilityConditions(null); setCustSearch("");
  };

  const openNew = () => {
    setEditingForm(null); resetEditor(); setShowEditor(true);
  };

  const openEdit = (f: IntakeForm) => {
    setEditingForm(f); setName(f.name); setDescription(f.description || "");
    try { setSchema(JSON.parse(f.schema || "[]")); } catch { setSchema([]); }
    setIsEnabled(f.is_enabled); setAutoApprove(f.auto_approve); setAllowSkipSig(f.allow_skip_signature);
    const ids = f.customer_ids || [];
    const vc = (f as any).visibility_conditions || null;
    if (ids.length > 0) { setVisMode("specific"); setCustomerIds(ids); setVisibilityConditions(null); }
    else if (vc) { setVisMode("conditional"); setVisibilityConditions(vc); setCustomerIds([]); }
    else { setVisMode("all"); setCustomerIds([]); setVisibilityConditions(null); }
    setCustSearch("");
    setShowEditor(true);
  };

  const save = async () => {
    if (!name.trim()) { toast.error("Form name is required"); return; }
    setSaving(true);
    const payload: Record<string, any> = {
      name: name.trim(), description, form_schema: JSON.stringify(schema),
      is_enabled: isEnabled, auto_approve: autoApprove, allow_skip_signature: allowSkipSig,
      customer_ids: visMode === "specific" ? customerIds : [],
      visibility_conditions: visMode === "conditional" ? visibilityConditions : null,
    };
    try {
      if (editingForm) { await api.put(`/admin/intake-forms/${editingForm.id}`, payload); toast.success("Form updated"); }
      else { await api.post("/admin/intake-forms", payload); toast.success("Form created"); }
      setShowEditor(false); load();
    } catch { toast.error("Failed to save form"); }
    finally { setSaving(false); }
  };

  const toggleCustomerId = (id: string) => {
    setCustomerIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  };

  const filteredCustomers = customerSearch
    ? allCustomers.filter(c => `${c.full_name || ""} ${c.email || ""}`.toLowerCase().includes(customerSearch.toLowerCase()))
    : allCustomers;

  const toggleEnabled = async (f: IntakeForm) => {
    try { await api.put(`/admin/intake-forms/${f.id}`, { is_enabled: !f.is_enabled }); load(); }
    catch { toast.error("Failed to update"); }
  };

  const del = async (id: string) => {
    if (!confirm("Delete this intake form? Existing records will remain.")) return;
    try { await api.delete(`/admin/intake-forms/${id}`); toast.success("Deleted"); load(); }
    catch { toast.error("Failed to delete"); }
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <div>
          <p className="text-sm text-slate-500">Define the forms customers must complete before checkout.</p>
        </div>
        <Button size="sm" onClick={openNew} data-testid="intake-add-form-btn">
          <Plus size={14} className="mr-1.5" /> Add Form
        </Button>
      </div>

      <div className="mt-4">
        {loading ? (
        <div className="text-sm text-slate-400 py-8 text-center">Loading...</div>
      ) : forms.length === 0 ? (
        <div className="py-12 text-center border-2 border-dashed border-slate-200 rounded-2xl">
          <FileText size={28} className="mx-auto text-slate-300 mb-3" />
          <p className="text-sm text-slate-400">No intake forms yet. Add your first form.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {forms.map(f => (
            <div key={f.id} className="border border-slate-200 rounded-2xl overflow-hidden">
              <div className="flex items-center gap-3 px-4 py-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm text-slate-900 truncate" data-testid={`intake-form-name-${f.id}`}>{f.name}</span>
                    {f.auto_approve && <Badge className="bg-emerald-50 text-emerald-700 text-[10px] px-1.5">Auto-approve</Badge>}
                    {(f.customer_ids?.length ?? 0) > 0 && (
                      <Badge className="bg-blue-50 text-blue-700 text-[10px] px-1.5">{f.customer_ids!.length} customer{f.customer_ids!.length !== 1 ? "s" : ""}</Badge>
                    )}
                    {isPlatformAdmin && f.partner_code && <Badge variant="outline" className="text-[10px]">{f.partner_code}</Badge>}
                  </div>
                  {f.description && <p className="text-xs text-slate-400 mt-0.5 truncate">{f.description}</p>}
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex flex-col items-center gap-0.5">
                    <Switch checked={f.is_enabled} onCheckedChange={() => toggleEnabled(f)} data-testid={`intake-form-toggle-${f.id}`} />
                    <span className="text-[10px] text-slate-400">{f.is_enabled ? "On" : "Off"}</span>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => openEdit(f)} data-testid={`intake-form-edit-${f.id}`}><Pencil size={13} /></Button>
                  <Button variant="ghost" size="sm" className="text-red-400" onClick={() => del(f.id)} data-testid={`intake-form-delete-${f.id}`}><Trash2 size={13} /></Button>
                  <Button variant="ghost" size="sm" onClick={() => setExpandedId(expandedId === f.id ? null : f.id)}>
                    {expandedId === f.id ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                  </Button>
                </div>
              </div>
              {f.is_enabled && (
                <div className="px-4 pb-2">
                  <p className="text-[11px] text-amber-700 bg-amber-50 border border-amber-100 rounded-lg px-3 py-1.5">
                    When enabled, customers cannot checkout until this form is completed {f.auto_approve ? "(auto-approved on submission)" : "and approved by an admin"}.
                  </p>
                </div>
              )}
              {expandedId === f.id && (
                <div className="px-4 pb-4 border-t border-slate-100 mt-2 pt-3 space-y-2">
                  <p className="text-xs text-slate-500 font-medium">System-locked fields (always included):</p>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    {SYSTEM_LOCKED_FIELDS.map(sf => (
                      <div key={sf.id} className="text-[11px] bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 flex items-center gap-1.5">
                        <Settings2 size={10} className="text-slate-400 shrink-0" />
                        <span className="text-slate-600">{sf.label}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      </div>

      {/* Editor Dialog */}
      <Dialog open={showEditor} onOpenChange={setShowEditor}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingForm ? "Edit Intake Form" : "New Intake Form"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-5 pt-2">
            {/* System-locked fields banner */}
            <div className="bg-slate-50 border border-slate-200 rounded-xl p-3">
              <p className="text-xs font-medium text-slate-500 mb-2 flex items-center gap-1.5"><Settings2 size={12} /> System-locked fields (auto-included in every record)</p>
              <div className="flex flex-wrap gap-1.5">
                {SYSTEM_LOCKED_FIELDS.map(sf => (
                  <span key={sf.id} className="text-[11px] bg-white border border-slate-200 rounded-full px-2.5 py-0.5 text-slate-500">{sf.label}</span>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="sm:col-span-2">
                <label className="text-xs font-medium text-slate-600 block mb-1.5">Form Name *</label>
                <Input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Client Intake Questionnaire" data-testid="intake-form-name-input" />
              </div>
              <div className="sm:col-span-2">
                <label className="text-xs font-medium text-slate-600 block mb-1.5">Description</label>
                <Textarea value={description} onChange={e => setDescription(e.target.value)} rows={2} placeholder="Brief description shown to customers" data-testid="intake-form-desc-input" />
              </div>
            </div>

            {/* Form Settings */}
            <div className="border border-slate-200 rounded-xl p-4 space-y-3">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Form Settings</p>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-slate-700">Enable this form</p>
                    <p className="text-xs text-slate-400">When on, customers must complete this before checkout</p>
                  </div>
                  <Switch checked={isEnabled} onCheckedChange={setIsEnabled} data-testid="intake-form-enabled-switch" />
                </div>
                <div className="flex items-center justify-between pt-1">
                  <div>
                    <p className="text-sm font-medium text-slate-700">Auto-approve on submission</p>
                    <p className="text-xs text-slate-400">Customer can checkout immediately after submitting</p>
                  </div>
                  <Switch checked={autoApprove} onCheckedChange={setAutoApprove} data-testid="intake-form-auto-approve-switch" />
                </div>
                <div className="flex items-center justify-between pt-1">
                  <div>
                    <p className="text-sm font-medium text-slate-700">Allow admin to skip signature</p>
                    <p className="text-xs text-slate-400">Admin-created records can optionally skip the signature requirement</p>
                  </div>
                  <Switch checked={allowSkipSig} onCheckedChange={setAllowSkipSig} data-testid="intake-form-skip-sig-switch" />
                </div>
              </div>
            </div>

            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Form Fields</p>
              <FormSchemaBuilder
                value={JSON.stringify(schema)}
                onChange={(json) => { try { setSchema(JSON.parse(json)); } catch { setSchema([]); } }}
              />
            </div>

            {/* Customer Assignment */}
            <div className="border border-slate-200 rounded-xl p-4 space-y-3">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Customer Assignment</p>
              <div className="flex flex-col gap-2">
                {(["all", "specific", "conditional"] as const).map(mode => (
                  <label key={mode} className="flex items-start gap-2.5 cursor-pointer">
                    <input type="radio" checked={visMode === mode}
                      onChange={() => { setVisMode(mode); if (mode !== "specific") setCustomerIds([]); if (mode !== "conditional") setVisibilityConditions(null); }}
                      className="h-3.5 w-3.5 mt-0.5" data-testid={`intake-assign-${mode}-radio`} />
                    <div>
                      <p className="text-sm font-medium text-slate-700">
                        {mode === "all" ? "All customers" : mode === "specific" ? "Specific customers only" : "Conditional (profile-based)"}
                      </p>
                      <p className="text-xs text-slate-400">
                        {mode === "all" && "Every customer in your account must complete this form"}
                        {mode === "specific" && "Only selected customers will be required to complete this form"}
                        {mode === "conditional" && "Show only to customers matching profile conditions (country, plan, company type, etc.)"}
                      </p>
                    </div>
                  </label>
                ))}
              </div>

              {/* Specific customers picker */}
              {visMode === "specific" && (
                <div className="mt-2 space-y-2">
                  <Input className="h-7 text-xs" placeholder="Search customers…"
                    value={customerSearch} onChange={e => setCustSearch(e.target.value)} data-testid="intake-customer-search" />
                  {customerIds.length > 0 && (
                    <p className="text-[11px] text-blue-600 font-medium">{customerIds.length} customer{customerIds.length !== 1 ? "s" : ""} selected</p>
                  )}
                  <div className="max-h-44 overflow-y-auto border border-slate-200 rounded-lg divide-y divide-slate-100">
                    {filteredCustomers.length === 0 ? (
                      <p className="text-xs text-slate-400 px-3 py-2">No customers found</p>
                    ) : filteredCustomers.map((c: any) => {
                      const selected = customerIds.includes(c.id);
                      return (
                        <button key={c.id} type="button" onClick={() => toggleCustomerId(c.id)}
                          className={`w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-slate-50 transition-colors ${selected ? "bg-blue-50" : ""}`}
                          data-testid={`intake-customer-${c.id}`}>
                          <span className={`h-4 w-4 shrink-0 rounded border flex items-center justify-center ${selected ? "bg-blue-500 border-blue-500" : "border-slate-300"}`}>
                            {selected && <Check size={9} className="text-white" strokeWidth={3} />}
                          </span>
                          <div className="min-w-0">
                            <p className="text-xs font-medium text-slate-700 truncate">{c.full_name || c.name || "—"}</p>
                            <p className="text-[11px] text-slate-400 truncate">{c.email || ""}</p>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Profile-based condition builder */}
              {visMode === "conditional" && (
                <ProductConditionBuilder
                  value={visibilityConditions}
                  onChange={setVisibilityConditions}
                  customers={allCustomers}
                />
              )}
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setShowEditor(false)}>Cancel</Button>
              <Button onClick={save} disabled={saving} data-testid="intake-form-save-btn">
                {saving ? "Saving…" : "Save Form"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ── Records sub-tab ───────────────────────────────────────────────────────────

function IntakeFormRecords({ isPlatformAdmin }: { isPlatformAdmin: boolean }) {
  const ws = useWebsite();
  const [records, setRecords] = useState<IntakeRecord[]>([]);
  const [forms, setForms] = useState<IntakeForm[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);

  // Column filters & sort
  const [colSort, setColSort] = useState<{ col: string; dir: SortDirection } | null>(null);
  const [customerSearch, setCustomerSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [formFilter, setFormFilter] = useState("all");
  const [dateFilter, setDateFilter] = useState<{ from?: string; to?: string }>({});

  // Modals
  const [viewRecord, setViewRecord] = useState<IntakeRecord | null>(null);
  const [notesRecord, setNotesRecord] = useState<IntakeRecord | null>(null);
  const [versionsRecord, setVersionsRecord] = useState<IntakeRecord | null>(null);
  const [versions, setVersions] = useState<VersionEntry[]>([]);
  const [logsRecord, setLogsRecord] = useState<IntakeRecord | null>(null);
  const [logs, setLogs] = useState<any[]>([]);
  const [addNoteText, setAddNoteText] = useState("");
  const [editNoteId, setEditNoteId] = useState<string | null>(null);
  const [editNoteText, setEditNoteText] = useState("");

  // Rejection reason modal
  const [rejecting, setRejecting] = useState<IntakeRecord | null>(null);
  const [rejectionReason, setRejectionReason] = useState("");

  // Add New Record
  const [showAddRecord, setShowAddRecord] = useState(false);
  const [addCustomerId, setAddCustomerId] = useState("");
  const [addFormId, setAddFormId] = useState("");
  const [addSkipSig, setAddSkipSig] = useState(false);
  const [customers, setCustomers] = useState<any[]>([]);

  const LIMIT = 20;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = { page, limit: LIMIT };
      if (statusFilter && statusFilter !== "all") params.status = statusFilter;
      if (formFilter && formFilter !== "all") params.form_id = formFilter;
      if (customerSearch) params.search = customerSearch;
      if (dateFilter.from) params.date_from = dateFilter.from;
      if (dateFilter.to) params.date_to = dateFilter.to;
      if (colSort) { params.sort_by = colSort.col; params.sort_dir = colSort.dir; }
      const r = await api.get("/admin/intake-form-records", { params });
      setRecords(r.data.records); setTotal(r.data.total);
    } catch { toast.error("Failed to load records"); }
    finally { setLoading(false); }
  }, [page, statusFilter, formFilter, customerSearch, dateFilter, colSort]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    api.get("/admin/intake-forms").then(r => setForms(r.data.forms)).catch(() => {});
    api.get("/admin/customers?page=1&limit=500").then(r => setCustomers(r.data.customers || [])).catch(() => {});
  }, []);

  const updateStatus = async (record: IntakeRecord, newStatus: string, reason?: string) => {
    // Mandatory rejection reason
    if (newStatus === "rejected" && !reason) {
      setRejecting(record);
      setRejectionReason("");
      return;
    }
    try {
      await api.put(`/admin/intake-form-records/${record.id}/status`, { status: newStatus, rejection_reason: reason || null });
      toast.success(`Status updated to ${STATUS_LABELS[newStatus]}`); load();
    } catch { toast.error("Failed to update status"); }
  };

  const openVersions = async (r: IntakeRecord) => {
    setVersionsRecord(r);
    try { const res = await api.get(`/admin/intake-form-records/${r.id}/versions`); setVersions(res.data.versions || []); }
    catch { toast.error("Failed to load versions"); }
  };

  const openLogs = async (r: IntakeRecord) => {
    setLogsRecord(r);
    try { const res = await api.get(`/admin/intake-form-records/${r.id}/logs`); setLogs(res.data.logs || []); }
    catch { toast.error("Failed to load logs"); }
  };

  const addNote = async () => {
    if (!notesRecord || !addNoteText.trim()) return;
    try {
      await api.post(`/admin/intake-form-records/${notesRecord.id}/notes`, { text: addNoteText.trim() });
      setAddNoteText(""); load();
      // Refresh notes record
      const r = await api.get(`/admin/intake-form-records/${notesRecord.id}`);
      setNotesRecord(r.data.record);
      toast.success("Note added");
    } catch { toast.error("Failed to add note"); }
  };

  const deleteNote = async (noteId: string) => {
    if (!notesRecord) return;
    try {
      await api.delete(`/admin/intake-form-records/${notesRecord.id}/notes/${noteId}`);
      const r = await api.get(`/admin/intake-form-records/${notesRecord.id}`);
      setNotesRecord(r.data.record); toast.success("Note deleted");
    } catch { toast.error("Failed to delete note"); }
  };

  const saveEditNote = async () => {
    if (!notesRecord || !editNoteId || !editNoteText.trim()) return;
    try {
      await api.put(`/admin/intake-form-records/${notesRecord.id}/notes/${editNoteId}`, { text: editNoteText.trim() });
      setEditNoteId(null); setEditNoteText("");
      const r = await api.get(`/admin/intake-form-records/${notesRecord.id}`);
      setNotesRecord(r.data.record); toast.success("Note updated");
    } catch { toast.error("Failed to update note"); }
  };

  const createRecord = async () => {
    if (!addFormId || !addCustomerId) { toast.error("Select a form and customer"); return; }
    try {
      await api.post("/admin/intake-form-records", { intake_form_id: addFormId, customer_id: addCustomerId, skip_signature: addSkipSig });
      toast.success("Record created"); setShowAddRecord(false); load();
    } catch (e: any) { toast.error(e?.response?.data?.detail || "Failed to create record"); }
  };

  const downloadPDF = (record: IntakeRecord) => {
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
      doc.text(record.intake_form_name, M, 44);
      doc.setFont("helvetica", "normal"); doc.setFontSize(9); doc.setTextColor(100, 116, 139);
      doc.text(`Customer: ${record.customer_name} (${record.customer_email})`, M, 53);
      doc.text(`Status: ${STATUS_LABELS[record.status] || record.status}   ·   Version: v${record.version}   ·   Submitted: ${record.submitted_at ? new Date(record.submitted_at).toLocaleDateString() : "Pending"}`, M, 60);

      // Divider
      doc.setDrawColor(pr, pg, pb); doc.setLineWidth(0.5);
      doc.line(M, 65, PW - M, 65);

      // ── Responses ──
      let y = 74;
      doc.setFont("helvetica", "bold"); doc.setFontSize(11); doc.setTextColor(30, 41, 59);
      doc.text("Responses", M, y); y += 8;
      const responses = Object.entries(record.responses || {}).filter(([k]) => k !== "signature_data_url" && k !== "signature_name");
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
      if (record.signature_name || record.signature_data_url) {
        if (y > 240) { doc.addPage(); y = 16; }
        const boxH = record.signature_data_url ? 46 : 20;
        doc.setDrawColor(226, 232, 240); doc.setFillColor(248, 250, 252);
        doc.roundedRect(M, y, PW - M * 2, boxH, 2, 2, "FD");
        doc.setFont("helvetica", "bold"); doc.setFontSize(7.5); doc.setTextColor(100, 116, 139);
        doc.text("SIGNATURE", M + 4, y + 7);
        if (record.signature_data_url) { try { doc.addImage(record.signature_data_url, "PNG", M + 4, y + 10, 60, 25); } catch (_) {} }
        if (record.signature_name) {
          doc.setFont("helvetica", "italic"); doc.setFontSize(9); doc.setTextColor(71, 85, 105);
          doc.text(`Digitally signed by: ${record.signature_name}`, M + 4, record.signature_data_url ? y + 40 : y + 14);
        }
      }

      // ── Footer ──
      doc.setFont("helvetica", "normal"); doc.setFontSize(7.5); doc.setTextColor(148, 163, 184);
      doc.text(`Generated ${new Date().toLocaleString()} · ${ws.store_name || ""}`, M, PH - 10);

      doc.save(`intake-${record.customer_name.replace(/\s/g, "_")}-${record.intake_form_name.replace(/\s/g, "_")}.pdf`);
    }).catch(() => toast.error("PDF generation failed"));
  };

  return (
    <div className="space-y-4">
      {/* Action bar — just the Add New button */}
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setShowAddRecord(true)} data-testid="intake-add-record-btn">
          <Plus size={13} className="mr-1.5" /> Add New
        </Button>
      </div>

      {/* Table */}
      <div>
      {loading ? <div className="text-sm text-slate-400 py-8 text-center">Loading...</div> : records.length === 0 ? (        <div className="py-12 text-center border-2 border-dashed border-slate-200 rounded-2xl">
          <FileText size={28} className="mx-auto text-slate-300 mb-3" />
          <p className="text-sm text-slate-400">No intake form records yet.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100">
                <ColHeader label="Customer" colKey="customer_name"
                  sortCol={colSort?.col} sortDir={colSort?.dir}
                  onSort={(c, d) => { setColSort({ col: c, dir: d }); setPage(1); }}
                  onClearSort={() => setColSort(null)}
                  filterType="text"
                  filterValue={customerSearch}
                  onFilter={v => { setCustomerSearch(v); setPage(1); }}
                  onClearFilter={() => { setCustomerSearch(""); setPage(1); }}
                />
                <ColHeader label="Form" colKey="intake_form_name"
                  sortCol={colSort?.col} sortDir={colSort?.dir}
                  onSort={(c, d) => { setColSort({ col: c, dir: d }); setPage(1); }}
                  onClearSort={() => setColSort(null)}
                  filterType="status"
                  filterValue={formFilter}
                  onFilter={v => { setFormFilter(v); setPage(1); }}
                  onClearFilter={() => { setFormFilter("all"); setPage(1); }}
                  statusOptions={[["all", "All forms"], ...forms.map(f => [f.id, f.name] as [string, string])]}
                />
                <ColHeader label="Status" colKey="status"
                  sortCol={colSort?.col} sortDir={colSort?.dir}
                  onSort={(c, d) => { setColSort({ col: c, dir: d }); setPage(1); }}
                  onClearSort={() => setColSort(null)}
                  filterType="status"
                  filterValue={statusFilter}
                  onFilter={v => { setStatusFilter(v); setPage(1); }}
                  onClearFilter={() => { setStatusFilter("all"); setPage(1); }}
                  statusOptions={[["all", "All"], ...Object.entries(STATUS_LABELS) as [string, string][]]}
                />
                <ColHeader label="Submitted" colKey="submitted_at"
                  sortCol={colSort?.col} sortDir={colSort?.dir}
                  onSort={(c, d) => { setColSort({ col: c, dir: d }); setPage(1); }}
                  onClearSort={() => setColSort(null)}
                  filterType="date-range"
                  filterValue={dateFilter}
                  onFilter={v => { setDateFilter(v); setPage(1); }}
                  onClearFilter={() => { setDateFilter({}); setPage(1); }}
                />
                <ColHeader label="Ver." colKey="version"
                  sortCol={colSort?.col} sortDir={colSort?.dir}
                  onSort={(c, d) => { setColSort({ col: c, dir: d }); setPage(1); }}
                  onClearSort={() => setColSort(null)}
                  filterType="none"
                />
                {isPlatformAdmin && (
                  <ColHeader label="Partner" colKey="partner_code"
                    sortCol={colSort?.col} sortDir={colSort?.dir}
                    onSort={(c, d) => { setColSort({ col: c, dir: d }); setPage(1); }}
                    onClearSort={() => setColSort(null)}
                    filterType="none"
                  />
                )}
                <th className="px-4 py-3 text-right text-xs font-medium uppercase text-slate-500">Actions</th>
              </tr>
            </thead>
            <tbody>
              {records.map(rec => (
                <tr key={rec.id} className="border-b border-slate-50 hover:bg-slate-50/50 transition-colors" data-testid={`intake-record-row-${rec.id}`}>
                  <td className="py-2.5 px-3">
                    <div className="font-medium text-slate-900 text-sm truncate max-w-[140px]">{rec.customer_name}</div>
                    <div className="text-xs text-slate-400 truncate max-w-[140px]">{rec.customer_email}</div>
                  </td>
                  <td className="py-2.5 px-3 max-w-[150px]">
                    <span className="text-xs text-slate-600 truncate block">{rec.intake_form_name}</span>
                  </td>
                  <td className="py-2.5 px-3">
                    <Select value={rec.status} onValueChange={v => updateStatus(rec, v)}>
                      <SelectTrigger className={`h-6 text-xs border-0 rounded-full px-2 font-medium ${STATUS_COLORS[rec.status] || "bg-slate-50"}`}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {Object.entries(STATUS_LABELS).filter(([v]) => v !== "pending").map(([v, l]) => (
                          <SelectItem key={v} value={v}>{l}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </td>
                  <td className="py-2.5 px-3 text-xs text-slate-400">{rec.submitted_at ? new Date(rec.submitted_at).toLocaleDateString() : "—"}</td>
                  <td className="py-2.5 px-3 text-xs text-slate-500">v{rec.version}</td>
                  {isPlatformAdmin && <td className="py-2.5 px-3 text-xs text-slate-400">{rec.partner_code || "—"}</td>}
                  <td className="py-2.5 px-3">
                    <div className="flex justify-end gap-0.5">
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => setViewRecord(rec)} title="View" data-testid={`intake-view-btn-${rec.id}`}><Eye size={13} /></Button>
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => openVersions(rec)} title="Versions" data-testid={`intake-versions-btn-${rec.id}`}><History size={13} /></Button>
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => openLogs(rec)} title="Logs" data-testid={`intake-logs-btn-${rec.id}`}><FileText size={13} /></Button>
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => { setNotesRecord(rec); setAddNoteText(""); }} title="Notes" data-testid={`intake-notes-btn-${rec.id}`}><StickyNote size={13} /></Button>
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => downloadPDF(rec)} title="Download PDF" data-testid={`intake-pdf-btn-${rec.id}`}><Download size={13} /></Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {total > LIMIT && (
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(p => p - 1)}>Prev</Button>
          <span className="text-xs text-slate-500 self-center">Page {page} of {Math.ceil(total / LIMIT)}</span>
          <Button variant="outline" size="sm" disabled={page * LIMIT >= total} onClick={() => setPage(p => p + 1)}>Next</Button>
        </div>
      )}
      </div>

      {/* View Record Modal */}
      <Dialog open={!!viewRecord} onOpenChange={() => setViewRecord(null)}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Intake Form Record</DialogTitle></DialogHeader>
          {viewRecord && (
            <div className="space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-2">
                <div><p className="text-xs text-slate-400">Form</p><p className="font-medium">{viewRecord.intake_form_name}</p></div>
                <div><p className="text-xs text-slate-400">Customer</p><p className="font-medium">{viewRecord.customer_name}</p></div>
                <div><p className="text-xs text-slate-400">Status</p><Badge className={STATUS_COLORS[viewRecord.status]}>{STATUS_LABELS[viewRecord.status]}</Badge></div>
                <div><p className="text-xs text-slate-400">Version</p><p>v{viewRecord.version}</p></div>
                {viewRecord.submitted_at && <div className="col-span-2"><p className="text-xs text-slate-400">Submitted</p><p>{new Date(viewRecord.submitted_at).toLocaleString()}</p></div>}
                {viewRecord.rejection_reason && <div className="col-span-2 bg-red-50 border border-red-100 rounded-lg p-2"><p className="text-xs text-red-600 font-medium">Rejection Reason</p><p className="text-xs text-red-500">{viewRecord.rejection_reason}</p></div>}
              </div>
              <div>
                <p className="text-xs text-slate-400 font-medium mb-2">Responses</p>
                <div className="space-y-1.5 bg-slate-50 rounded-xl p-3">
                  {Object.entries(viewRecord.responses || {}).map(([k, v]) => (
                    <div key={k} className="flex gap-2"><span className="text-xs text-slate-400 w-32 shrink-0">{k}</span><span className="text-xs text-slate-700 break-all">{String(v)}</span></div>
                  ))}
                </div>
              </div>
              {viewRecord.signature_name && <div><p className="text-xs text-slate-400 mb-1">Signed by</p><p className="font-medium italic">{viewRecord.signature_name}</p></div>}
              {viewRecord.signature_data_url && (
                <div><p className="text-xs text-slate-400 mb-2">Signature</p><img src={viewRecord.signature_data_url} alt="Signature" className="border rounded-xl max-h-24 bg-white" /></div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Versions Modal */}
      <Dialog open={!!versionsRecord} onOpenChange={() => { setVersionsRecord(null); setVersions([]); }}>
        <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Record Versions</DialogTitle></DialogHeader>
          {versions.length === 0 ? <p className="text-sm text-slate-400 py-4 text-center">No previous versions.</p> : (
            <div className="space-y-3">
              {versions.map((v, i) => (
                <div key={i} className="border border-slate-200 rounded-xl p-3 space-y-2">
                  <div className="flex justify-between text-xs"><span className="font-semibold">Version {v.version}</span><span className="text-slate-400">{new Date(v.archived_at).toLocaleString()}</span></div>
                  <Badge className={`text-[10px] ${STATUS_COLORS[v.status] || ""}`}>{STATUS_LABELS[v.status] || v.status}</Badge>
                  <div className="space-y-1">
                    {Object.entries(v.responses || {}).map(([k, val]) => (
                      <div key={k} className="flex gap-2 text-xs"><span className="text-slate-400 w-24 shrink-0">{k}</span><span className="text-slate-600 break-all">{String(val)}</span></div>
                    ))}
                  </div>
                  {v.signature_name && <p className="text-xs italic text-slate-500">Signed by: {v.signature_name}</p>}
                  {v.signature_data_url && <img src={v.signature_data_url} alt="Signature" className="max-h-16 border rounded-lg bg-white" />}
                </div>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Logs Modal */}
      <Dialog open={!!logsRecord} onOpenChange={() => { setLogsRecord(null); setLogs([]); }}>
        <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Record Logs</DialogTitle></DialogHeader>
          {logs.length === 0 ? <p className="text-sm text-slate-400 py-4 text-center">No logs yet.</p> : (
            <div className="space-y-2">
              {logs.map((log, i) => (
                <div key={i} className="flex gap-3 py-2 border-b border-slate-50 text-xs">
                  <div className="w-32 shrink-0 text-slate-400">{new Date(log.timestamp).toLocaleString()}</div>
                  <div><span className="font-medium text-slate-700">{log.actor}</span><span className="text-slate-400 mx-1">—</span><span className="text-slate-600">{log.action.replace(/_/g, " ")}</span></div>
                </div>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Notes Modal */}
      <Dialog open={!!notesRecord} onOpenChange={() => { setNotesRecord(null); setEditNoteId(null); }}>
        <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Notes — {notesRecord?.customer_name}</DialogTitle></DialogHeader>
          {notesRecord && (
            <div className="space-y-4">
              {(notesRecord.notes || []).length === 0 && <p className="text-xs text-slate-400 text-center py-4">No notes yet.</p>}
              <div className="space-y-2">
                {(notesRecord.notes || []).map(note => (
                  <div key={note.id} className="bg-slate-50 border border-slate-200 rounded-xl p-3">
                    {editNoteId === note.id ? (
                      <div className="space-y-2">
                        <Textarea value={editNoteText} onChange={e => setEditNoteText(e.target.value)} rows={2} className="text-sm" />
                        <div className="flex gap-2">
                          <Button size="sm" onClick={saveEditNote}><Check size={12} className="mr-1" />Save</Button>
                          <Button size="sm" variant="ghost" onClick={() => setEditNoteId(null)}><X size={12} /></Button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex justify-between gap-2">
                        <div>
                          <p className="text-xs text-slate-700">{note.text}</p>
                          <p className="text-[10px] text-slate-400 mt-1">{note.author} · {new Date(note.created_at).toLocaleString()}</p>
                        </div>
                        <div className="flex gap-1 shrink-0">
                          <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={() => { setEditNoteId(note.id); setEditNoteText(note.text); }}><Pencil size={11} /></Button>
                          <Button variant="ghost" size="sm" className="h-6 w-6 p-0 text-red-400" onClick={() => deleteNote(note.id)}><Trash2 size={11} /></Button>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
              <div className="border-t border-slate-100 pt-3 space-y-2">
                <Textarea value={addNoteText} onChange={e => setAddNoteText(e.target.value)} rows={2} placeholder="Add a note..." className="text-sm" data-testid="intake-add-note-input" />
                <Button size="sm" onClick={addNote} disabled={!addNoteText.trim()} data-testid="intake-add-note-btn">
                  <Plus size={12} className="mr-1" /> Add Note
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Add New Record */}
      <Dialog open={showAddRecord} onOpenChange={setShowAddRecord}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle>Create Intake Form Record</DialogTitle></DialogHeader>
          <div className="space-y-4 pt-2">
            <div>
              <label className="text-xs font-medium text-slate-600 block mb-1.5">Select Form *</label>
              <Select value={addFormId} onValueChange={setAddFormId}>
                <SelectTrigger className="h-9 text-sm"><SelectValue placeholder="Choose a form..." /></SelectTrigger>
                <SelectContent>{forms.map(f => <SelectItem key={f.id} value={f.id}>{f.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-xs font-medium text-slate-600 block mb-1.5">Select Customer *</label>
              <Select value={addCustomerId} onValueChange={setAddCustomerId}>
                <SelectTrigger className="h-9 text-sm"><SelectValue placeholder="Choose a customer..." /></SelectTrigger>
                <SelectContent>{customers.map((c: any) => <SelectItem key={c.id} value={c.id}>{c.full_name || c.name || c.email}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            {addFormId && forms.find(f => f.id === addFormId)?.allow_skip_signature && (
              <div className="flex items-center justify-between rounded-xl border border-slate-200 p-3">
                <div>
                  <p className="text-sm font-medium text-slate-700">Skip signature requirement</p>
                  <p className="text-xs text-slate-400">Admin-created — signature will not be required</p>
                </div>
                <Switch checked={addSkipSig} onCheckedChange={setAddSkipSig} data-testid="intake-skip-sig-switch" />
              </div>
            )}
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowAddRecord(false)}>Cancel</Button>
              <Button onClick={createRecord} data-testid="intake-create-record-btn">Create Record</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Rejection Reason Dialog */}
      <Dialog open={rejecting !== null} onOpenChange={open => { if (!open) { setRejecting(null); setRejectionReason(""); } }}>
        <DialogContent className="max-w-sm" data-testid="intake-reject-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertCircle size={16} className="text-red-500" /> Reject Submission
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3 pt-1">
            <p className="text-sm text-slate-600">
              Provide a reason for rejection. This will be included in the email notification sent to <strong>{rejecting?.customer_name}</strong>.
            </p>
            <div>
              <label className="text-xs font-medium text-slate-600 block mb-1.5">Reason *</label>
              <Textarea
                value={rejectionReason}
                onChange={e => setRejectionReason(e.target.value)}
                rows={3}
                placeholder="e.g. Missing supporting documents, please re-submit with ID proof..."
                className="text-sm"
                data-testid="intake-rejection-reason-input"
              />
              {rejectionReason.trim() === "" && (
                <p className="text-[11px] text-red-500 mt-1">A reason is required before rejecting.</p>
              )}
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" size="sm" onClick={() => { setRejecting(null); setRejectionReason(""); }}>Cancel</Button>
            <Button
              size="sm"
              variant="destructive"
              disabled={!rejectionReason.trim()}
              onClick={async () => {
                if (rejecting) {
                  const rec = rejecting; const reason = rejectionReason;
                  setRejecting(null); setRejectionReason("");
                  await updateStatus(rec, "rejected", reason);
                }
              }}
              data-testid="intake-reject-confirm-btn"
            >
              Reject Submission
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ── Main Tab ──────────────────────────────────────────────────────────────────

export function AdminIntakeFormsTab() {
  const { user } = useAuth();
  const isPlatformAdmin = user?.role === "platform_admin" || user?.role === "platform_super_admin";

  return (
    <div className="space-y-4" data-testid="admin-intake-forms-tab">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">Intake Forms</h2>
        <p className="text-sm text-slate-500 mt-0.5">Manage intake questionnaires that customers must complete before checkout.</p>
      </div>
      <Tabs defaultValue="records">
        <TabsList className="mb-4">
          <TabsTrigger value="records" data-testid="intake-tab-records">Intake Form Records</TabsTrigger>
          <TabsTrigger value="builder" data-testid="intake-tab-builder">Intake Form Builder</TabsTrigger>
        </TabsList>
        <TabsContent value="records"><IntakeFormRecords isPlatformAdmin={isPlatformAdmin} /></TabsContent>
        <TabsContent value="builder"><IntakeFormBuilder isPlatformAdmin={isPlatformAdmin} /></TabsContent>
      </Tabs>
    </div>
  );
}
