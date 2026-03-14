import { AuditLogDialog } from "@/components/AuditLogDialog";
import { useCallback, useEffect, useMemo, useState } from "react";
import { RequiredLabel } from "@/components/shared/RequiredLabel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { Plus, Trash2, Clock } from "lucide-react";
import { ColHeader } from "@/components/shared/ColHeader";
import { RichHtmlEditor } from "@/components/ui/RichHtmlEditor";

function EmailBodyEditor({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <RichHtmlEditor value={value} onChange={onChange} minHeight="200px" placeholder="Write the email body here…" />
  );
}

interface EmailTemplate { id: string; name: string; subject: string; html_body: string; description: string; created_at: string; }

export function ResourceEmailTemplatesTab() {
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [colSort, setColSort] = useState<{ col: string; dir: "asc" | "desc" } | null>(null);
  const [nameFilter, setNameFilter] = useState<string[]>([]);

  // Build unique options for dropdowns
  const uniqueNames = useMemo(() => templates.map(t => t.name).filter(Boolean), [templates]);

  const displayTemplates = useMemo(() => {
    let r = [...templates];
    if (nameFilter.length > 0) r = r.filter(t => nameFilter.includes(t.name));
    if (colSort) {
      r.sort((a, b) => {
        let av: any = "", bv: any = "";
        if (colSort.col === "name") { av = a.name; bv = b.name; }
        else if (colSort.col === "subject") { av = a.subject || ""; bv = b.subject || ""; }
        if (av < bv) return colSort.dir === "asc" ? -1 : 1;
        if (av > bv) return colSort.dir === "asc" ? 1 : -1;
        return 0;
      });
    }
    return r;
  }, [templates, nameFilter, colSort]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<EmailTemplate | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", subject: "", html_body: "" });
  const [confirmDeleteTpl, setConfirmDeleteTpl] = useState<string | null>(null);
  const [logsUrl, setLogsUrl] = useState("");
  const [showAuditLogs, setShowAuditLogs] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get("/resource-email-templates");
      setTemplates(res.data.templates || []);
    } catch { toast.error("Failed to load email templates"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const openCreate = () => {
    setEditing(null);
    setForm({ name: "", description: "", subject: "", html_body: "" });
    setShowForm(true);
  };

  const openEdit = (tpl: EmailTemplate) => {
    setEditing(tpl);
    setForm({ name: tpl.name, description: tpl.description, subject: tpl.subject, html_body: tpl.html_body });
    setShowForm(true);
  };

  const handleSave = async () => {
    if (!form.name.trim()) { toast.error("Template name is required"); return; }
    if (!form.subject.trim()) { toast.error("Subject is required"); return; }
    if (!form.description.trim()) { toast.error("Description is required"); return; }
    if (!form.html_body || !form.html_body.replace(/<[^>]*>/g, "").trim()) { toast.error("Email body is required"); return; }
    setSaving(true);
    try {
      if (editing) {
        await api.put(`/resource-email-templates/${editing.id}`, form);
        toast.success("Email template updated");
      } else {
        await api.post("/resource-email-templates", form);
        toast.success("Email template created");
      }
      setShowForm(false);
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to save");
    } finally { setSaving(false); }
  };

  const handleDelete = async (id: string) => {
    setDeleting(id);
    try {
      await api.delete(`/resource-email-templates/${id}`);
      toast.success("Deleted");
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Delete failed");
    } finally { setDeleting(null); }
  };

  return (
    <div className="space-y-4" data-testid="resource-email-templates-tab">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">Email Templates</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            {templates.length} template{templates.length !== 1 ? "s" : ""} — reuse when composing resource emails
          </p>
        </div>
        <Button size="sm" onClick={openCreate} className="gap-1.5" data-testid="email-template-create-btn">
          <Plus size={14} /> New Email Template
        </Button>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="bg-slate-50">
              <ColHeader label="Name" colKey="name" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={nameFilter} onFilter={v => setNameFilter(v)} onClearFilter={() => setNameFilter([])} statusOptions={uniqueNames.map(n => [n, n] as [string, string])} />
              <ColHeader label="Subject" colKey="subject" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="none" />
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500">Actions</th>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow><TableCell colSpan={3} className="text-center text-slate-400 py-8 text-sm">Loading…</TableCell></TableRow>
            ) : displayTemplates.length === 0 ? (
              <TableRow><TableCell colSpan={3} className="text-center text-slate-400 py-8 text-sm">No email templates found.</TableCell></TableRow>
            ) : displayTemplates.map((tpl) => (
              <TableRow key={tpl.id} data-testid={`email-template-row-${tpl.id}`}>
                <TableCell>
                  <div className="text-sm font-medium text-slate-900">{tpl.name}</div>
                  {tpl.description && <div className="text-xs text-slate-400 mt-0.5">{tpl.description}</div>}
                </TableCell>
                <TableCell className="text-xs text-slate-600 max-w-xs truncate">{tpl.subject}</TableCell>
                <TableCell>
                  <div className="flex gap-1">
                    <Button variant="ghost" size="sm" className="h-7 px-2 text-[11px]" onClick={() => openEdit(tpl)} data-testid={`email-template-edit-${tpl.id}`}>Edit</Button>
                    <Button variant="ghost" size="sm" className="h-7 px-2 text-[11px]" onClick={() => { setLogsUrl(`/resource-email-templates/${tpl.id}/logs`); setShowAuditLogs(true); }} data-testid={`email-template-logs-${tpl.id}`}><Clock size={11} /></Button>
                    <Button variant="ghost" size="sm" className="h-7 px-2 text-[11px] text-red-500 hover:text-red-700" onClick={() => setConfirmDeleteTpl(tpl.id)} disabled={deleting === tpl.id} data-testid={`email-template-delete-${tpl.id}`}>
                      <Trash2 size={11} />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <Dialog open={showForm} onOpenChange={(o) => { setShowForm(o); if (!o) setEditing(null); }}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="email-template-form-dialog">
          <DialogHeader>
            <DialogTitle>{editing ? `Edit: ${editing.name}` : "New Email Template"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <RequiredLabel>Template Name</RequiredLabel>
                  {form.name.length > 0 && <span className={`text-[11px] font-mono tabular-nums ${form.name.length > 475 ? "text-red-500" : form.name.length > 400 ? "text-amber-500" : "text-slate-400"}`}>{form.name.length}/500</span>}
                </div>
                <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} maxLength={500} placeholder="e.g. Scope Delivery" data-testid="email-template-name-input" />
              </div>
              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <RequiredLabel>Description</RequiredLabel>
                  {form.description.length > 0 && <span className={`text-[11px] font-mono tabular-nums ${form.description.length > 4750 ? "text-red-500" : form.description.length > 4000 ? "text-amber-500" : "text-slate-400"}`}>{form.description.length}/5000</span>}
                </div>
                <Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} maxLength={5000} placeholder="Brief description" data-testid="email-template-desc-input" />
              </div>
            </div>
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <RequiredLabel>Subject</RequiredLabel>
                {form.subject.length > 0 && <span className={`text-[11px] font-mono tabular-nums ${form.subject.length > 190 ? "text-red-500" : form.subject.length > 160 ? "text-amber-500" : "text-slate-400"}`}>{form.subject.length}/200</span>}
              </div>
              <Input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} maxLength={200} placeholder="Email subject line" data-testid="email-template-subject-input" />
            </div>
            <div className="space-y-1">
              <RequiredLabel>Email Body</RequiredLabel>
              <EmailBodyEditor value={form.html_body} onChange={(v) => setForm({ ...form, html_body: v })} />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
              <Button onClick={handleSave} disabled={saving} data-testid="email-template-save-btn">
                {saving ? "Saving…" : editing ? "Update Template" : "Create Template"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Logs Dialog */}
      <AuditLogDialog open={showAuditLogs} onOpenChange={setShowAuditLogs} title="Email Template Logs" logsUrl={logsUrl} />

      {/* Delete Confirmation */}
      <AlertDialog open={!!confirmDeleteTpl} onOpenChange={(open) => !open && setConfirmDeleteTpl(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Email Template</AlertDialogTitle>
            <AlertDialogDescription>Are you sure you want to delete this email template? This cannot be undone.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction className="bg-red-600 hover:bg-red-700" onClick={() => { handleDelete(confirmDeleteTpl!); setConfirmDeleteTpl(null); }} data-testid="confirm-email-tpl-delete">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
