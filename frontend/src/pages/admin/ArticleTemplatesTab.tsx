import { ImportModal } from "@/components/admin/ImportModal";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { Plus, Trash2, Upload, Download, Clock } from "lucide-react";
import { RichHtmlEditor } from "@/components/ui/RichHtmlEditor";

const HARDCODED_CATEGORIES = [
  "Scope - Draft", "Scope - Final Lost", "Scope - Final Won",
  "Blog", "Help", "Guide", "SOP", "Other",
];

interface Template { id: string; name: string; description: string; category: string; content: string; is_default: boolean; created_at: string; }

export function ArticleTemplatesTab({ categories }: { categories?: any[] }) {
  const categoryNames = categories && categories.length > 0
    ? categories.map(c => c.name)
    : HARDCODED_CATEGORIES;
  const [showImport, setShowImport] = useState(false);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Template | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", category: "", content: "" });
  const [confirmDeleteTpl, setConfirmDeleteTpl] = useState<string | null>(null);
  const [entityLogs, setEntityLogs] = useState<any[]>([]);
  const [showLogsDialog, setShowLogsDialog] = useState(false);

  const downloadCsv = () => {
    const token = localStorage.getItem("aa_token") || "";
    const base = process.env.REACT_APP_BACKEND_URL || "";
    fetch(`${base}/api/admin/export/article-templates`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.blob()).then(b => { const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = `article-templates-${new Date().toISOString().slice(0,10)}.csv`; a.click(); })
      .catch(() => toast.error("Export failed"));
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get("/article-templates");
      setTemplates(res.data.templates || []);
    } catch { toast.error("Failed to load templates"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const openCreate = () => {
    setEditing(null);
    setForm({ name: "", description: "", category: "", content: "" });
    setShowForm(true);
  };

  const openEdit = (tpl: Template) => {
    setEditing(tpl);
    setForm({ name: tpl.name, description: tpl.description, category: tpl.category, content: tpl.content });
    setShowForm(true);
  };

  const handleSave = async () => {
    if (!form.name.trim()) { toast.error("Template name is required"); return; }
    setSaving(true);
    try {
      if (editing) {
        await api.put(`/article-templates/${editing.id}`, form);
        toast.success("Template updated");
      } else {
        await api.post("/article-templates", form);
        toast.success("Template created");
      }
      setShowForm(false);
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to save template");
    } finally { setSaving(false); }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this template? This cannot be undone.")) return;
    setDeleting(id);
    try {
      await api.delete(`/article-templates/${id}`);
      toast.success("Template deleted");
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Delete failed");
    } finally { setDeleting(null); }
  };

  return (
    <div className="space-y-4" data-testid="article-templates-tab">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">Article Templates</h3>
          <p className="text-xs text-slate-500 mt-0.5">{templates.length} template{templates.length !== 1 ? "s" : ""} — use these as starting points when creating articles</p>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="outline" onClick={downloadCsv} data-testid="article-templates-export-csv"><Download size={14} className="mr-1" />Export CSV</Button>
          <Button size="sm" variant="outline" onClick={() => setShowImport(true)} data-testid="article-templates-import-csv"><Upload size={14} className="mr-1" />Import CSV</Button>
          <Button size="sm" onClick={openCreate} className="gap-1.5" data-testid="template-create-btn">
            <Plus size={14} /> New Template
          </Button>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-slate-50">
              <TableHead className="text-xs">Name</TableHead>
              <TableHead className="text-xs">Category</TableHead>
              <TableHead className="text-xs">Type</TableHead>
              <TableHead className="text-xs">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow><TableCell colSpan={4} className="text-center text-slate-400 py-8 text-sm">Loading…</TableCell></TableRow>
            ) : templates.length === 0 ? (
              <TableRow><TableCell colSpan={4} className="text-center text-slate-400 py-8 text-sm">No templates yet.</TableCell></TableRow>
            ) : templates.map((tpl) => (
              <TableRow key={tpl.id} data-testid={`template-row-${tpl.id}`}>
                <TableCell>
                  <div className="text-sm font-medium text-slate-900">{tpl.name}</div>
                  {tpl.description && <div className="text-xs text-slate-400 mt-0.5">{tpl.description}</div>}
                </TableCell>
                <TableCell className="text-xs text-slate-600">{tpl.category || "—"}</TableCell>
                <TableCell>
                  {tpl.is_default
                    ? <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 font-medium">Default</span>
                    : <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-medium">Custom</span>}
                </TableCell>
                <TableCell>
                  <div className="flex gap-1">
                    <Button variant="ghost" size="sm" className="h-7 px-2 text-[11px]" onClick={() => openEdit(tpl)} data-testid={`template-edit-${tpl.id}`}>Edit</Button>
                    <Button variant="ghost" size="sm" className="h-7 px-2 text-[11px] text-red-500 hover:text-red-700" onClick={() => handleDelete(tpl.id)} disabled={deleting === tpl.id} data-testid={`template-delete-${tpl.id}`}>
                      <Trash2 size={11} />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Create/Edit Dialog */}
      <Dialog open={showForm} onOpenChange={(o) => { setShowForm(o); if (!o) setEditing(null); }}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto" data-testid="template-form-dialog">
          <DialogHeader>
            <DialogTitle>{editing ? `Edit: ${editing.name}` : "New Template"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-700">Template Name *</label>
                <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Weekly Update" data-testid="template-name-input" />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-700">Default Category</label>
                <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v })}>
                  <SelectTrigger data-testid="template-category-select"><SelectValue placeholder="Select category" /></SelectTrigger>
                  <SelectContent>
                    {categoryNames.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-700">Description</label>
              <Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Brief description of this template's purpose" data-testid="template-desc-input" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-700">Content</label>
              <RichHtmlEditor value={form.content} onChange={(v) => setForm({ ...form, content: v })} withImages minHeight="320px" placeholder="Write your template content here…" />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
              <Button onClick={handleSave} disabled={saving} data-testid="template-save-btn">
                {saving ? "Saving…" : editing ? "Update Template" : "Create Template"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
      <ImportModal
        entity="article-templates"
        entityLabel="Article Templates"
        open={showImport}
        onClose={() => setShowImport(false)}
        onSuccess={load}
      />
    </div>
  );
}
