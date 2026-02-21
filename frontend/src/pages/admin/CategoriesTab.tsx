import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";

interface Category {
  id: string;
  name: string;
  description?: string;
  is_active: boolean;
  product_count?: number;
  created_at?: string;
}

export function CategoriesTab() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [editCat, setEditCat] = useState<Category | null>(null);
  const [form, setForm] = useState({ name: "", description: "", is_active: true });
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get("/admin/categories");
      setCategories(res.data.categories || []);
    } catch {
      toast.error("Failed to load categories");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const openCreate = () => {
    setEditCat(null);
    setForm({ name: "", description: "", is_active: true });
    setShowDialog(true);
  };

  const openEdit = (cat: Category) => {
    setEditCat(cat);
    setForm({ name: cat.name, description: cat.description || "", is_active: cat.is_active });
    setShowDialog(true);
  };

  const handleSave = async () => {
    if (!form.name.trim()) { toast.error("Category name is required"); return; }
    setSaving(true);
    try {
      if (editCat) {
        await api.put(`/admin/categories/${editCat.id}`, form);
        toast.success("Category updated");
      } else {
        await api.post("/admin/categories", form);
        toast.success("Category created");
      }
      setShowDialog(false);
      load();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to save category");
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async (cat: Category) => {
    try {
      await api.put(`/admin/categories/${cat.id}`, { is_active: !cat.is_active });
      toast.success(`Category ${cat.is_active ? "deactivated" : "activated"}`);
      load();
    } catch {
      toast.error("Failed to update category");
    }
  };

  const handleDelete = async (cat: Category) => {
    if ((cat.product_count ?? 0) > 0) {
      toast.error(`Cannot delete: ${cat.product_count} product(s) linked to this category. Reassign products first.`);
      return;
    }
    if (!window.confirm(`Delete category "${cat.name}"? This cannot be undone.`)) return;
    try {
      await api.delete(`/admin/categories/${cat.id}`);
      toast.success("Category deleted");
      load();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to delete category");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-900">Product Categories</h3>
        <Button size="sm" onClick={openCreate} data-testid="admin-create-category-btn">+ New Category</Button>
      </div>
      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
        <Table data-testid="admin-categories-table">
          <TableHeader>
            <TableRow className="bg-slate-50">
              <TableHead>Name</TableHead>
              <TableHead>Description</TableHead>
              <TableHead>Products</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && (
              <TableRow><TableCell colSpan={5} className="text-center text-slate-400">Loading…</TableCell></TableRow>
            )}
            {!loading && categories.length === 0 && (
              <TableRow><TableCell colSpan={5} className="text-center text-slate-400">No categories yet.</TableCell></TableRow>
            )}
            {categories.map((cat) => (
              <TableRow key={cat.id} data-testid={`admin-category-row-${cat.id}`}>
                <TableCell className="font-medium">{cat.name}</TableCell>
                <TableCell className="text-sm text-slate-500 max-w-xs">
                  <span className="line-clamp-2">{cat.description || "—"}</span>
                </TableCell>
                <TableCell>
                  <span className="text-sm font-medium">{cat.product_count ?? 0}</span>
                </TableCell>
                <TableCell>
                  <span className={`text-xs px-2 py-1 rounded font-medium ${cat.is_active ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                    {cat.is_active ? "Active" : "Inactive"}
                  </span>
                </TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => openEdit(cat)} data-testid={`admin-edit-cat-${cat.id}`}>Edit</Button>
                    <Button
                      variant={cat.is_active ? "destructive" : "outline"}
                      size="sm"
                      onClick={() => handleToggle(cat)}
                      data-testid={`admin-toggle-cat-${cat.id}`}
                    >
                      {cat.is_active ? "Deactivate" : "Activate"}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className={`${(cat.product_count ?? 0) > 0 ? "text-slate-300 cursor-not-allowed" : "text-red-500 hover:text-red-700"}`}
                      onClick={() => handleDelete(cat)}
                      data-testid={`admin-delete-cat-${cat.id}`}
                      title={(cat.product_count ?? 0) > 0 ? `${cat.product_count} products linked — reassign first` : "Delete"}
                    >
                      Delete
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent data-testid="admin-category-dialog">
          <DialogHeader>
            <DialogTitle>{editCat ? "Edit Category" : "New Category"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 pt-2">
            <div>
              <label className="text-sm font-medium text-slate-700">Name *</label>
              <Input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. Zoho Express Setup"
                className="mt-1"
                data-testid="admin-category-name-input"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700">Description</label>
              <Textarea
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Short blurb shown on the storefront under this category"
                rows={2}
                className="mt-1"
                data-testid="admin-category-desc-input"
              />
            </div>
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                className="w-4 h-4 rounded"
                data-testid="admin-category-active-switch"
              />
              <span className="text-sm text-slate-700">Active (visible on storefront)</span>
            </label>
            <div className="flex gap-2 justify-end">
              <Button variant="outline" onClick={() => setShowDialog(false)}>Cancel</Button>
              <Button onClick={handleSave} disabled={saving} data-testid="admin-category-save-btn">
                {saving ? "Saving…" : "Save"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
