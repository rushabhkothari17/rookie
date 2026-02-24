import { useCallback, useEffect, useState } from "react";
import { ImportModal } from "@/components/admin/ImportModal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { AdminPageHeader } from "./shared/AdminPageHeader";
import { AdminPagination } from "./shared/AdminPagination";
import { Download, Upload} from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export function CategoriesTab() {
  const [categories, setCategories] = useState<any[]>([]);
  const [showImport, setShowImport] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const PER_PAGE = 20;

  // Filters
  const [searchFilter, setSearchFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  // Dialog
  const [showDialog, setShowDialog] = useState(false);
  const [editCat, setEditCat] = useState<any>(null);
  const [form, setForm] = useState({ name: "", description: "", is_active: true });
  const [saving, setSaving] = useState(false);
  const [entityLogs, setEntityLogs] = useState<any[]>([]);
  const [showEntityLogs, setShowEntityLogs] = useState(false);
  const [confirmToggleCat, setConfirmToggleCat] = useState<any>(null);
  const [confirmDeleteCat, setConfirmDeleteCat] = useState<any>(null);

  const load = useCallback(async (p = 1) => {
    try {
      const params = new URLSearchParams({ page: String(p), per_page: String(PER_PAGE) });
      if (searchFilter) params.append("search", searchFilter);
      if (statusFilter) params.append("status", statusFilter);
      const res = await api.get(`/admin/categories?${params}`);
      setCategories(res.data.categories || []);
      setTotal(res.data.total || 0);
      setTotalPages(res.data.total_pages || 1);
      setPage(p);
    } catch { toast.error("Failed to load categories"); }
  }, [searchFilter, statusFilter]);

  useEffect(() => { load(1); }, [searchFilter, statusFilter]);

  const openCreate = () => { setEditCat(null); setForm({ name: "", description: "", is_active: true }); setShowDialog(true); };
  const openEdit = (cat: any) => { setEditCat(cat); setForm({ name: cat.name, description: cat.description || "", is_active: cat.is_active }); setShowDialog(true); };

  const handleSave = async () => {
    if (!form.name.trim()) { toast.error("Category name is required"); return; }
    setSaving(true);
    try {
      if (editCat) { await api.put(`/admin/categories/${editCat.id}`, form); toast.success("Category updated"); }
      else { await api.post("/admin/categories", form); toast.success("Category created"); }
      setShowDialog(false); load(page);
    } catch (e: any) { toast.error(e?.response?.data?.detail || "Failed to save category"); }
    finally { setSaving(false); }
  };

  const handleToggle = async (cat: any) => {
    try { await api.put(`/admin/categories/${cat.id}`, { is_active: !cat.is_active }); toast.success("Category updated"); load(page); }
    catch { toast.error("Failed to update category"); }
  };

  const handleDelete = async (cat: any) => {
    if ((cat.product_count ?? 0) > 0) { toast.error(`Cannot delete: ${cat.product_count} product(s) linked. Reassign first.`); return; }
    try { await api.delete(`/admin/categories/${cat.id}`); toast.success("Category deleted"); load(page); }
    catch (e: any) { toast.error(e?.response?.data?.detail || "Failed to delete"); }
  };

  const downloadCsv = () => {
    const token = localStorage.getItem("aa_token");
    const base = process.env.REACT_APP_BACKEND_URL || "";
    const params = new URLSearchParams();
    if (searchFilter) params.append("search", searchFilter);
    if (statusFilter) params.append("status", statusFilter);
    fetch(`${base}/api/admin/export/categories?${params}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.blob()).then(b => { const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = `categories-${new Date().toISOString().slice(0, 10)}.csv`; a.click(); })
      .catch(() => toast.error("Export failed"));
  };

  return (
    <div className="space-y-4" data-testid="categories-tab">
      <AdminPageHeader title="Product Categories" subtitle={`${total} categories`} actions={
        <>
          <Button size="sm" variant="outline" onClick={downloadCsv} data-testid="admin-categories-export-csv"><Download size={14} className="mr-1" />Export CSV</Button>
          <Button size="sm" variant="outline" onClick={() => setShowImport(true)} data-testid="admin-categories-import-csv"><Upload size={14} className="mr-1" />Import CSV</Button>
          <Button size="sm" onClick={openCreate} data-testid="admin-create-category-btn">+ New Category</Button>
        </>
      } />

      {/* Filters */}
      <div className="rounded-xl border border-slate-200 bg-white p-3">
        <div className="flex gap-2 items-center">
          <Input placeholder="Search by name…" value={searchFilter} onChange={e => setSearchFilter(e.target.value)} className="h-8 text-xs w-44" data-testid="admin-categories-search" />
          <Select value={statusFilter || "all"} onValueChange={v => setStatusFilter(v === "all" ? "" : v)}>
            <SelectTrigger className="h-8 text-xs w-32 bg-white" data-testid="admin-categories-status-filter"><SelectValue placeholder="All Statuses" /></SelectTrigger>
            <SelectContent><SelectItem value="all">All Statuses</SelectItem><SelectItem value="active">Active</SelectItem><SelectItem value="inactive">Inactive</SelectItem></SelectContent>
          </Select>
          <Button size="sm" variant="outline" onClick={() => { setSearchFilter(""); setStatusFilter(""); }} className="h-8 text-xs" data-testid="admin-categories-clear-filters">Clear</Button>
        </div>
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
            {categories.map((cat) => (
              <TableRow key={cat.id} data-testid={`admin-category-row-${cat.id}`}>
                <TableCell className="font-medium">{cat.name}</TableCell>
                <TableCell className="text-sm text-slate-500 max-w-xs"><span className="line-clamp-2">{cat.description || "—"}</span></TableCell>
                <TableCell><span className="text-sm font-medium">{cat.product_count ?? 0}</span></TableCell>
                <TableCell><span className={`text-xs px-2 py-1 rounded font-medium ${cat.is_active ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>{cat.is_active ? "Active" : "Inactive"}</span></TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => openEdit(cat)} data-testid={`admin-edit-cat-${cat.id}`}>Edit</Button>
                    <Button variant={cat.is_active ? "destructive" : "outline"} size="sm" onClick={() => handleToggle(cat)} data-testid={`admin-toggle-cat-${cat.id}`}>{cat.is_active ? "Deactivate" : "Activate"}</Button>
                    <Button variant="ghost" size="sm" className={`${(cat.product_count ?? 0) > 0 ? "text-slate-300 cursor-not-allowed" : "text-red-500 hover:text-red-700"}`} onClick={() => handleDelete(cat)} data-testid={`admin-delete-cat-${cat.id}`}>Delete</Button>
                    <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px]" onClick={async () => { const r = await api.get(`/admin/categories/${cat.id}/logs`); setEntityLogs(r.data.logs || []); setShowEntityLogs(true); }} data-testid={`admin-cat-logs-${cat.id}`}>Logs</Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
            {categories.length === 0 && <TableRow><TableCell colSpan={5} className="text-center text-slate-400 py-8">No categories found.</TableCell></TableRow>}
          </TableBody>
        </Table>
      </div>
      <AdminPagination page={page} totalPages={totalPages} total={total} perPage={PER_PAGE} onPage={(p) => load(p)} />

      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent data-testid="admin-category-dialog">
          <DialogHeader><DialogTitle>{editCat ? "Edit Category" : "New Category"}</DialogTitle></DialogHeader>
          <div className="space-y-4 pt-2">
            <div><label className="text-sm font-medium text-slate-700">Name *</label><Input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} className="mt-1" data-testid="admin-category-name-input" /></div>
            <div><label className="text-sm font-medium text-slate-700">Description</label><Textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} rows={2} className="mt-1" data-testid="admin-category-desc-input" /></div>
            <label className="flex items-center gap-3 cursor-pointer"><input type="checkbox" checked={form.is_active} onChange={e => setForm({ ...form, is_active: e.target.checked })} className="w-4 h-4" data-testid="admin-category-active-switch" /><span className="text-sm">Active (visible on storefront)</span></label>
            <div className="flex gap-2 justify-end">
              <Button variant="outline" onClick={() => setShowDialog(false)}>Cancel</Button>
              <Button onClick={handleSave} disabled={saving} data-testid="admin-category-save-btn">{saving ? "Saving…" : "Save"}</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={showEntityLogs} onOpenChange={setShowEntityLogs}>
        <DialogContent className="max-w-2xl"><DialogHeader><DialogTitle>Category Audit Logs</DialogTitle></DialogHeader>
          <div className="max-h-[60vh] overflow-y-auto space-y-2">
            {entityLogs.length === 0 && <p className="text-sm text-slate-500 text-center py-4">No logs found</p>}
            {entityLogs.map((log: any, i: number) => (
              <div key={log.id || i} className="border border-slate-200 rounded p-3">
                <div className="flex justify-between items-start mb-1"><span className="text-sm font-semibold text-slate-900">{log.action}</span><span className="text-xs text-slate-500">{new Date(log.created_at).toLocaleString()}</span></div>
                <div className="text-xs text-slate-600">Actor: {log.actor}</div>
                {log.details && Object.keys(log.details).length > 0 && <pre className="text-xs text-slate-500 mt-1 bg-slate-50 p-2 rounded overflow-x-auto">{JSON.stringify(log.details, null, 2)}</pre>}
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
      <ImportModal
        entity="categories"
        entityLabel="Categories"
        open={showImport}
        onClose={() => setShowImport(false)}
        onSuccess={load}
      />
    </div>
  );
}
