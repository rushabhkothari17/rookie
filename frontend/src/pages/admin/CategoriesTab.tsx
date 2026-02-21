import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";

import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";

interface Category {
  id: string;
  name: string;
  is_active: boolean;
  created_at?: string;
}

export function CategoriesTab() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [editCat, setEditCat] = useState<Category | null>(null);
  const [form, setForm] = useState({ name: "", is_active: true });
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
    setForm({ name: "", is_active: true });
    setShowDialog(true);
  };

  const openEdit = (cat: Category) => {
    setEditCat(cat);
    setForm({ name: cat.name, is_active: cat.is_active });
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
              <TableHead>Status</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && (
              <TableRow><TableCell colSpan={3} className="text-center text-slate-400">Loading…</TableCell></TableRow>
            )}
            {!loading && categories.length === 0 && (
              <TableRow><TableCell colSpan={3} className="text-center text-slate-400">No categories yet. Create one above.</TableCell></TableRow>
            )}
            {categories.map((cat) => (
              <TableRow key={cat.id} data-testid={`admin-category-row-${cat.id}`}>
                <TableCell className="font-medium">{cat.name}</TableCell>
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
                    <Button variant="ghost" size="sm" className="text-red-500" onClick={() => handleDelete(cat)} data-testid={`admin-delete-cat-${cat.id}`}>Delete</Button>
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
              <Label>Name</label>
              <Input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. Zoho Express Setup"
                data-testid="admin-category-name-input"
              />
            </div>
            <div className="flex items-center gap-3">
              <Switch
                checked={form.is_active}
                onCheckedChange={(v) => setForm({ ...form, is_active: v })}
                data-testid="admin-category-active-switch"
              />
              <Label>Active (visible on storefront)</label>
            </div>
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
