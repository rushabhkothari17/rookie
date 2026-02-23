import { useCallback, useEffect, useState } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import LinkExt from "@tiptap/extension-link";
import Placeholder from "@tiptap/extension-placeholder";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { Bold, Italic, List, ListOrdered, Link2, Plus, Trash2 } from "lucide-react";

function EmailBodyEditor({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      LinkExt.configure({ openOnClick: false }),
      Placeholder.configure({ placeholder: "Write the email body here…" }),
    ],
    content: value,
    onUpdate({ editor }) { onChange(editor.getHTML()); },
  });

  if (!editor) return null;
  const btn = (active: boolean, onClick: () => void, icon: React.ReactNode, title: string) => (
    <button type="button" title={title} onClick={onClick}
      className={`p-1.5 rounded hover:bg-slate-100 transition-colors ${active ? "bg-slate-200 text-slate-900" : "text-slate-500"}`}>
      {icon}
    </button>
  );

  return (
    <div className="border border-slate-200 rounded-lg overflow-hidden">
      <div className="flex flex-wrap gap-0.5 p-2 border-b border-slate-200 bg-slate-50">
        {btn(editor.isActive("bold"), () => editor.chain().focus().toggleBold().run(), <Bold size={14} />, "Bold")}
        {btn(editor.isActive("italic"), () => editor.chain().focus().toggleItalic().run(), <Italic size={14} />, "Italic")}
        <div className="w-px bg-slate-200 mx-1" />
        {btn(editor.isActive("bulletList"), () => editor.chain().focus().toggleBulletList().run(), <List size={14} />, "Bullet list")}
        {btn(editor.isActive("orderedList"), () => editor.chain().focus().toggleOrderedList().run(), <ListOrdered size={14} />, "Numbered list")}
        <div className="w-px bg-slate-200 mx-1" />
        <button type="button" title="Insert link"
          onClick={() => { const url = prompt("Enter URL"); if (url) editor.chain().focus().setLink({ href: url }).run(); }}
          className={`p-1.5 rounded hover:bg-slate-100 transition-colors ${editor.isActive("link") ? "bg-slate-200 text-slate-900" : "text-slate-500"}`}>
          <Link2 size={14} />
        </button>
      </div>
      <EditorContent editor={editor}
        className="prose prose-sm max-w-none p-4 min-h-[200px] focus:outline-none [&_.tiptap]:outline-none [&_.tiptap]:min-h-[180px]" />
    </div>
  );
}

interface EmailTemplate { id: string; name: string; subject: string; html_body: string; description: string; created_at: string; }

export function ArticleEmailTemplatesTab() {
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<EmailTemplate | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", subject: "", html_body: "" });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get("/article-email-templates");
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
    setSaving(true);
    try {
      if (editing) {
        await api.put(`/article-email-templates/${editing.id}`, form);
        toast.success("Email template updated");
      } else {
        await api.post("/article-email-templates", form);
        toast.success("Email template created");
      }
      setShowForm(false);
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to save");
    } finally { setSaving(false); }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this email template?")) return;
    setDeleting(id);
    try {
      await api.delete(`/article-email-templates/${id}`);
      toast.success("Deleted");
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Delete failed");
    } finally { setDeleting(null); }
  };

  return (
    <div className="space-y-4" data-testid="article-email-templates-tab">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">Email Templates</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            {templates.length} template{templates.length !== 1 ? "s" : ""} — reuse when composing article emails
          </p>
        </div>
        <Button size="sm" onClick={openCreate} className="gap-1.5" data-testid="email-template-create-btn">
          <Plus size={14} /> New Email Template
        </Button>
      </div>

      <div className="rounded-xl border border-slate-200 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-slate-50">
              <TableHead className="text-xs">Name</TableHead>
              <TableHead className="text-xs">Subject</TableHead>
              <TableHead className="text-xs">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow><TableCell colSpan={3} className="text-center text-slate-400 py-8 text-sm">Loading…</TableCell></TableRow>
            ) : templates.length === 0 ? (
              <TableRow><TableCell colSpan={3} className="text-center text-slate-400 py-8 text-sm">No email templates yet. Create one to speed up article sharing.</TableCell></TableRow>
            ) : templates.map((tpl) => (
              <TableRow key={tpl.id} data-testid={`email-template-row-${tpl.id}`}>
                <TableCell>
                  <div className="text-sm font-medium text-slate-900">{tpl.name}</div>
                  {tpl.description && <div className="text-xs text-slate-400 mt-0.5">{tpl.description}</div>}
                </TableCell>
                <TableCell className="text-xs text-slate-600 max-w-xs truncate">{tpl.subject}</TableCell>
                <TableCell>
                  <div className="flex gap-1">
                    <Button variant="ghost" size="sm" className="h-7 px-2 text-[11px]" onClick={() => openEdit(tpl)} data-testid={`email-template-edit-${tpl.id}`}>Edit</Button>
                    <Button variant="ghost" size="sm" className="h-7 px-2 text-[11px] text-red-500 hover:text-red-700" onClick={() => handleDelete(tpl.id)} disabled={deleting === tpl.id} data-testid={`email-template-delete-${tpl.id}`}>
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
                <label className="text-xs font-medium text-slate-700">Template Name *</label>
                <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Scope Delivery" data-testid="email-template-name-input" />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-700">Description</label>
                <Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Brief description" data-testid="email-template-desc-input" />
              </div>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-700">Subject *</label>
              <Input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} placeholder="Email subject line" data-testid="email-template-subject-input" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-700">Email Body</label>
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
    </div>
  );
}
