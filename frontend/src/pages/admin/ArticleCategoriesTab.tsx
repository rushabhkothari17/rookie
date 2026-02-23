import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { Plus, Pencil, Trash2, Tag } from "lucide-react";

const PRESET_COLORS = [
  "#0f172a", "#1e40af", "#7c3aed", "#be185d", "#dc2626",
  "#d97706", "#16a34a", "#0891b2", "#6b7280", "#a16207",
];

interface Category {
  id: string;
  name: string;
  slug: string;
  description: string;
  color: string;
  is_scope_final: boolean;
  created_at: string;
}

const EMPTY_FORM = { name: "", description: "", color: "", is_scope_final: false };

export function ArticleCategoriesTab() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Category | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get("/article-categories");
      setCategories(res.data.categories || []);
    } catch { toast.error("Failed to load categories"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const openCreate = () => {
    setEditing(null);
    setForm(EMPTY_FORM);
    setShowForm(true);
  };

  const openEdit = (cat: Category) => {
    setEditing(cat);
    setForm({ name: cat.name, description: cat.description, color: cat.color, is_scope_final: cat.is_scope_final });
    setShowForm(true);
  };

  const handleSave = async () => {
    if (!form.name.trim()) { toast.error("Category name is required"); return; }
    setSaving(true);
    try {
      if (editing) {
        await api.put(`/article-categories/${editing.id}`, form);
        toast.success("Category updated");
      } else {
        await api.post("/article-categories", form);
        toast.success("Category created");
      }
      setShowForm(false);
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to save category");
    } finally { setSaving(false); }
  };

  const handleDelete = async (cat: Category) => {
    if (!confirm(`Delete category "${cat.name}"? Articles using this category will need to be reassigned.`)) return;
    setDeleting(cat.id);
    try {
      await api.delete(`/article-categories/${cat.id}`);
      toast.success("Category deleted");
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Delete failed");
    } finally { setDeleting(null); }
  };

  return (
    <div className="space-y-4" data-testid="article-categories-tab">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">Article Categories</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            {categories.length} categor{categories.length !== 1 ? "ies" : "y"} — used to organise articles on the store
          </p>
        </div>
        <Button size="sm" onClick={openCreate} className="gap-1.5" data-testid="category-create-btn">
          <Plus size={14} /> Add Category
        </Button>
      </div>

      <div className="rounded-xl border border-slate-200 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-slate-50">
              <TableHead className="text-xs w-[40%]">Name</TableHead>
              <TableHead className="text-xs w-[35%]">Description</TableHead>
              <TableHead className="text-xs w-[15%]">Scope Final</TableHead>
              <TableHead className="text-xs w-[10%]">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow><TableCell colSpan={4} className="text-center text-slate-400 py-8 text-sm">Loading…</TableCell></TableRow>
            ) : categories.length === 0 ? (
              <TableRow><TableCell colSpan={4} className="text-center text-slate-400 py-8 text-sm">No categories yet. Create one to organise your articles.</TableCell></TableRow>
            ) : categories.map((cat) => (
              <TableRow key={cat.id} data-testid={`category-row-${cat.id}`}>
                <TableCell>
                  <div className="flex items-center gap-2">
                    {cat.color ? (
                      <span className="inline-block w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: cat.color }} />
                    ) : (
                      <Tag size={12} className="text-slate-300 flex-shrink-0" />
                    )}
                    <span className="text-sm font-medium text-slate-900">{cat.name}</span>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-0.5 ml-5">{cat.slug}</p>
                </TableCell>
                <TableCell className="text-xs text-slate-500 max-w-xs">{cat.description || <span className="text-slate-300">—</span>}</TableCell>
                <TableCell>
                  {cat.is_scope_final ? (
                    <span className="inline-flex items-center gap-1 bg-amber-50 text-amber-700 text-[11px] font-medium px-2 py-0.5 rounded-full border border-amber-200">Yes</span>
                  ) : (
                    <span className="text-slate-300 text-xs">No</span>
                  )}
                </TableCell>
                <TableCell>
                  <div className="flex gap-1">
                    <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => openEdit(cat)} data-testid={`category-edit-${cat.id}`}>
                      <Pencil size={12} />
                    </Button>
                    <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-red-400 hover:text-red-600 hover:bg-red-50" onClick={() => handleDelete(cat)} disabled={deleting === cat.id} data-testid={`category-delete-${cat.id}`}>
                      <Trash2 size={12} />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Create / Edit Dialog */}
      <Dialog open={showForm} onOpenChange={(o) => { setShowForm(o); if (!o) setEditing(null); }}>
        <DialogContent className="max-w-md" data-testid="category-form-dialog">
          <DialogHeader>
            <DialogTitle>{editing ? `Edit: ${editing.name}` : "New Category"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-1">
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-700">Name *</label>
              <Input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. Setup Guides"
                data-testid="category-name-input"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-700">Description</label>
              <Input
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Brief description of this category"
                data-testid="category-desc-input"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-700">Colour Badge</label>
              <div className="flex flex-wrap gap-2 items-center">
                {PRESET_COLORS.map((c) => (
                  <button
                    key={c}
                    type="button"
                    onClick={() => setForm({ ...form, color: form.color === c ? "" : c })}
                    className={`w-7 h-7 rounded-full border-2 transition-all ${form.color === c ? "border-slate-900 scale-110" : "border-transparent hover:border-slate-300"}`}
                    style={{ backgroundColor: c }}
                    title={c}
                    data-testid={`category-color-${c}`}
                  />
                ))}
                <div className="flex items-center gap-1 ml-1">
                  <Input
                    type="color"
                    value={form.color || "#6b7280"}
                    onChange={(e) => setForm({ ...form, color: e.target.value })}
                    className="h-7 w-14 p-0.5 border-slate-200 cursor-pointer"
                    data-testid="category-color-custom"
                  />
                  {form.color && (
                    <button
                      type="button"
                      onClick={() => setForm({ ...form, color: "" })}
                      className="text-[11px] text-slate-400 hover:text-slate-600 underline"
                    >
                      Clear
                    </button>
                  )}
                </div>
              </div>
              {form.color && (
                <div className="flex items-center gap-2 mt-1">
                  <span className="w-4 h-4 rounded-full" style={{ backgroundColor: form.color }} />
                  <span className="text-xs text-slate-500">Preview: {form.color}</span>
                </div>
              )}
            </div>
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={form.is_scope_final}
                onChange={(e) => setForm({ ...form, is_scope_final: e.target.checked })}
                className="rounded border-slate-300"
                data-testid="category-scope-final-checkbox"
              />
              <div>
                <span className="text-sm text-slate-700 font-medium">Scope Final category</span>
                <p className="text-[11px] text-slate-400">Articles in this category require a price to be set</p>
              </div>
            </label>
            <div className="flex justify-end gap-2 pt-1">
              <Button variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
              <Button onClick={handleSave} disabled={saving} data-testid="category-save-btn">
                {saving ? "Saving…" : editing ? "Update Category" : "Create Category"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
