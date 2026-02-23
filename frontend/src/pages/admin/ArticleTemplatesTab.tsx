import { useCallback, useEffect, useRef, useState } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import ImageExt from "@tiptap/extension-image";
import LinkExt from "@tiptap/extension-link";
import Placeholder from "@tiptap/extension-placeholder";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { Bold, Italic, List, ListOrdered, Link2, Image, Heading1, Heading2, Heading3, Plus, Trash2 } from "lucide-react";

const ARTICLE_CATEGORIES = [
  "Scope - Draft", "Scope - Final Lost", "Scope - Final Won",
  "Blog", "Help", "Guide", "SOP", "Other",
];

function TemplateToolbar({ editor }: { editor: any }) {
  const imgRef = useRef<HTMLInputElement>(null);
  const handleImg = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]; if (!f || !editor) return;
    const r = new FileReader();
    r.onload = () => editor.chain().focus().setImage({ src: r.result as string }).run();
    r.readAsDataURL(f); e.target.value = "";
  };
  if (!editor) return null;
  const btn = (active: boolean, onClick: () => void, icon: React.ReactNode, title: string) => (
    <button type="button" title={title} onClick={onClick}
      className={`p-1.5 rounded hover:bg-slate-100 transition-colors ${active ? "bg-slate-200 text-slate-900" : "text-slate-500"}`}>
      {icon}
    </button>
  );
  return (
    <div className="flex flex-wrap gap-0.5 p-2 border-b border-slate-200 bg-slate-50 rounded-t-lg">
      {btn(editor.isActive("bold"), () => editor.chain().focus().toggleBold().run(), <Bold size={14} />, "Bold")}
      {btn(editor.isActive("italic"), () => editor.chain().focus().toggleItalic().run(), <Italic size={14} />, "Italic")}
      <div className="w-px bg-slate-200 mx-1" />
      {btn(editor.isActive("heading", { level: 1 }), () => editor.chain().focus().toggleHeading({ level: 1 }).run(), <Heading1 size={14} />, "H1")}
      {btn(editor.isActive("heading", { level: 2 }), () => editor.chain().focus().toggleHeading({ level: 2 }).run(), <Heading2 size={14} />, "H2")}
      {btn(editor.isActive("heading", { level: 3 }), () => editor.chain().focus().toggleHeading({ level: 3 }).run(), <Heading3 size={14} />, "H3")}
      <div className="w-px bg-slate-200 mx-1" />
      {btn(editor.isActive("bulletList"), () => editor.chain().focus().toggleBulletList().run(), <List size={14} />, "Bullet list")}
      {btn(editor.isActive("orderedList"), () => editor.chain().focus().toggleOrderedList().run(), <ListOrdered size={14} />, "Numbered list")}
      <div className="w-px bg-slate-200 mx-1" />
      <button type="button" title="Insert link"
        onClick={() => { const url = prompt("Enter URL"); if (url) editor.chain().focus().setLink({ href: url }).run(); }}
        className={`p-1.5 rounded hover:bg-slate-100 transition-colors ${editor.isActive("link") ? "bg-slate-200 text-slate-900" : "text-slate-500"}`}>
        <Link2 size={14} />
      </button>
      <button type="button" title="Insert image" onClick={() => imgRef.current?.click()}
        className="p-1.5 rounded hover:bg-slate-100 transition-colors text-slate-500">
        <Image size={14} />
      </button>
      <input ref={imgRef} type="file" accept="image/*" className="hidden" onChange={handleImg} />
    </div>
  );
}

function TemplateEditor({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      ImageExt,
      LinkExt.configure({ openOnClick: false }),
      Placeholder.configure({ placeholder: "Write your template content here…" }),
    ],
    content: value,
    onUpdate({ editor }) { onChange(editor.getHTML()); },
  });
  return (
    <div className="border border-slate-200 rounded-lg overflow-hidden">
      <TemplateToolbar editor={editor} />
      <EditorContent editor={editor}
        className="prose prose-sm max-w-none p-4 min-h-[300px] focus:outline-none [&_.tiptap]:outline-none [&_.tiptap]:min-h-[280px]" />
    </div>
  );
}

interface Template { id: string; name: string; description: string; category: string; content: string; is_default: boolean; created_at: string; }

export function ArticleTemplatesTab() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Template | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", category: "", content: "" });

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
        <Button size="sm" onClick={openCreate} className="gap-1.5" data-testid="template-create-btn">
          <Plus size={14} /> New Template
        </Button>
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
                    {ARTICLE_CATEGORIES.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
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
              <TemplateEditor value={form.content} onChange={(v) => setForm({ ...form, content: v })} />
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
    </div>
  );
}
