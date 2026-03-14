import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ImportModal } from "@/components/admin/ImportModal";
import { RequiredLabel } from "@/components/shared/RequiredLabel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Table, TableBody, TableCell, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { AdminPageHeader } from "./shared/AdminPageHeader";
import { AdminPagination } from "./shared/AdminPagination";
import { AuditLogDialog } from "@/components/AuditLogDialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Download, Upload } from "lucide-react";
import { Tooltip, TooltipContent as _TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { ColHeader } from "@/components/shared/ColHeader";
function TooltipContent({ side, children }: { side?: "top" | "bottom" | "left" | "right"; children?: React.ReactNode }) {
  const TC = _TooltipContent as any;
  return <TC side={side}>{children}</TC>;
}

export function CategoriesTab() {
  const [categories, setCategories] = useState<any[]>([]);
  const [showImport, setShowImport] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const PER_PAGE = 20;

  // Filters
  const [nameFilter, setNameFilter] = useState<string[]>([]);
  const [descSearch, setDescSearch] = useState("");
  const [productsFilter, setProductsFilter] = useState<string[]>([]);
  const [statusFilter, setStatusFilter] = useState<string[]>([]);
  const [colSort, setColSort] = useState<{ col: string; dir: "asc" | "desc" } | null>(null);

  // Build unique options for dropdowns
  const uniqueNames = useMemo(() => {
    return Array.from(new Set(categories.map(c => c.name).filter(Boolean))).sort().map(n => [n, n] as [string, string]);
  }, [categories]);

  const uniqueProductCounts = useMemo(() => {
    const counts = new Set(categories.map(c => String(c.product_count ?? 0)));
    return Array.from(counts).sort((a, b) => parseInt(a) - parseInt(b)).map(n => [n, n] as [string, string]);
  }, [categories]);

  const displayCategories = useMemo(() => {
    let r = [...categories];
    // Apply local filters
    if (nameFilter.length > 0) r = r.filter(c => nameFilter.includes(c.name));
    if (descSearch) r = r.filter(c => (c.description || "").toLowerCase().includes(descSearch.toLowerCase()));
    if (productsFilter.length > 0) r = r.filter(c => productsFilter.includes(String(c.product_count ?? 0)));
    if (statusFilter.length > 0) r = r.filter(c => statusFilter.some(s => (s === "active" && c.is_active) || (s === "inactive" && !c.is_active)));
    if (colSort) {
      r.sort((a, b) => {
        let av: any = "", bv: any = "";
        if (colSort.col === "name") { av = a.name; bv = b.name; }
        else if (colSort.col === "description") { av = a.description || ""; bv = b.description || ""; }
        else if (colSort.col === "products") { av = a.product_count ?? 0; bv = b.product_count ?? 0; }
        else if (colSort.col === "status") { av = a.is_active ? 1 : 0; bv = b.is_active ? 1 : 0; }
        if (av < bv) return colSort.dir === "asc" ? -1 : 1;
        if (av > bv) return colSort.dir === "asc" ? 1 : -1;
        return 0;
      });
    }
    return r;
  }, [categories, nameFilter, descSearch, productsFilter, statusFilter, colSort]);

  // Dialog
  const [showDialog, setShowDialog] = useState(false);
  const [editCat, setEditCat] = useState<any>(null);
  const [form, setForm] = useState({ name: "", description: "", is_active: true });
  const [saving, setSaving] = useState(false);
  const [logsUrl, setLogsUrl] = useState("");
  const [showAuditLogs, setShowAuditLogs] = useState(false);
  const [confirmToggleCat, setConfirmToggleCat] = useState<any>(null);
  const [confirmDeleteCat, setConfirmDeleteCat] = useState<any>(null);

  const load = useCallback(async (p = 1) => {
    try {
      const params = new URLSearchParams({ page: String(p), per_page: String(500) });
      const res = await api.get(`/admin/categories?${params}`);
      setCategories(res.data.categories || []);
      setTotal(res.data.total || 0);
      setTotalPages(res.data.total_pages || 1);
      setPage(p);
    } catch { toast.error("Failed to load categories"); }
  }, []);

  useEffect(() => { load(1); }, [load]);

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
    fetch(`${base}/api/admin/export/categories`, { headers: { Authorization: `Bearer ${token}` } })
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

      {/* Filters removed — use column headers */}

      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
        <Table data-testid="admin-categories-table">
          <TableHeader>
            <TableRow className="bg-slate-50">
              <ColHeader label="Name" colKey="name" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={nameFilter} onFilter={v => { setNameFilter(v); setPage(1); }} onClearFilter={() => { setNameFilter([]); setPage(1); }} statusOptions={uniqueNames} />
              <ColHeader label="Description" colKey="description" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="text" filterValue={descSearch} onFilter={v => { setDescSearch(v); setPage(1); }} onClearFilter={() => { setDescSearch(""); setPage(1); }} />
              <ColHeader label="Products" colKey="products" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={productsFilter} onFilter={v => { setProductsFilter(v); setPage(1); }} onClearFilter={() => { setProductsFilter([]); setPage(1); }} statusOptions={uniqueProductCounts} />
              <ColHeader label="Status" colKey="status" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={statusFilter} onFilter={v => { setStatusFilter(v); setPage(1); }} onClearFilter={() => { setStatusFilter([]); setPage(1); }} statusOptions={[["active", "Active"], ["inactive", "Inactive"]]} />
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500">Actions</th>
            </TableRow>
          </TableHeader>
          <TableBody>
            {displayCategories.map((cat) => (
              <TableRow key={cat.id} data-testid={`admin-category-row-${cat.id}`}>
                <TableCell className="font-medium">{cat.name}</TableCell>
                <TableCell className="text-sm text-slate-500 max-w-xs"><span className="line-clamp-2">{cat.description || "—"}</span></TableCell>
                <TableCell><span className="text-sm font-medium">{cat.product_count ?? 0}</span></TableCell>
                <TableCell><span className={`text-xs px-2 py-1 rounded font-medium ${cat.is_active ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>{cat.is_active ? "Active" : "Inactive"}</span></TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => openEdit(cat)} data-testid={`admin-edit-cat-${cat.id}`}>Edit</Button>
                    <Button variant={cat.is_active ? "destructive" : "outline"} size="sm" onClick={() => setConfirmToggleCat(cat)} data-testid={`admin-toggle-cat-${cat.id}`}>{cat.is_active ? "Deactivate" : "Activate"}</Button>
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span>
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={(cat.product_count ?? 0) > 0}
                              className={(cat.product_count ?? 0) > 0 ? "text-slate-300 cursor-not-allowed pointer-events-none" : "text-red-500 hover:text-red-700"}
                              onClick={() => setConfirmDeleteCat(cat)}
                              data-testid={`admin-delete-cat-${cat.id}`}
                            >
                              Delete
                            </Button>
                          </span>
                        </TooltipTrigger>
                        {(cat.product_count ?? 0) > 0 && (
                          <TooltipContent side="top">
                            <p>{cat.product_count} product(s) linked — reassign them first</p>
                          </TooltipContent>
                        )}
                      </Tooltip>
                    </TooltipProvider>
                    <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px]" onClick={() => { setLogsUrl(`/admin/categories/${cat.id}/logs`); setShowAuditLogs(true); }} data-testid={`admin-cat-logs-${cat.id}`}>Logs</Button>
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
            <div>
              <div className="flex items-center justify-between mb-1">
                <RequiredLabel className="text-sm">Name</RequiredLabel>
                {form.name.length > 0 && <span className={`text-[11px] font-mono tabular-nums ${form.name.length > 475 ? "text-red-500" : form.name.length > 400 ? "text-amber-500" : "text-slate-400"}`}>{form.name.length}/500</span>}
              </div>
              <Input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} maxLength={500} data-testid="admin-category-name-input" />
            </div>
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-sm font-medium text-slate-700">Description</label>
                {form.description.length > 0 && <span className={`text-[11px] font-mono tabular-nums ${form.description.length > 4750 ? "text-red-500" : form.description.length > 4000 ? "text-amber-500" : "text-slate-400"}`}>{form.description.length}/5000</span>}
              </div>
              <Textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} maxLength={5000} rows={2} data-testid="admin-category-desc-input" />
            </div>
            <label className="flex items-center gap-3 cursor-pointer"><input type="checkbox" checked={form.is_active} onChange={e => setForm({ ...form, is_active: e.target.checked })} className="w-4 h-4" data-testid="admin-category-active-switch" /><span className="text-sm">Active (visible on storefront)</span></label>
            <div className="flex gap-2 justify-end">
              <Button variant="outline" onClick={() => setShowDialog(false)}>Cancel</Button>
              <Button onClick={handleSave} disabled={saving} data-testid="admin-category-save-btn">{saving ? "Saving…" : "Save"}</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <AuditLogDialog open={showAuditLogs} onOpenChange={setShowAuditLogs} title="Category Audit Logs" logsUrl={logsUrl} />
      <ImportModal
        entity="categories"
        entityLabel="Categories"
        open={showImport}
        onClose={() => setShowImport(false)}
        onSuccess={load}
      />

      {/* Toggle Category Confirmation */}
      <AlertDialog open={!!confirmToggleCat} onOpenChange={(open) => !open && setConfirmToggleCat(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{confirmToggleCat?.is_active ? "Deactivate Category" : "Activate Category"}</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to {confirmToggleCat?.is_active ? "deactivate" : "activate"} "{confirmToggleCat?.name}"?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className={confirmToggleCat?.is_active ? "bg-red-600 hover:bg-red-700" : ""}
              onClick={() => { handleToggle(confirmToggleCat); setConfirmToggleCat(null); }}
              data-testid="confirm-cat-toggle"
            >
              {confirmToggleCat?.is_active ? "Deactivate" : "Activate"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Delete Category Confirmation */}
      <AlertDialog open={!!confirmDeleteCat} onOpenChange={(open) => !open && setConfirmDeleteCat(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Category</AlertDialogTitle>
            <AlertDialogDescription>Are you sure you want to delete "{confirmDeleteCat?.name}"? This cannot be undone.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction className="bg-red-600 hover:bg-red-700" onClick={() => { handleDelete(confirmDeleteCat); setConfirmDeleteCat(null); }} data-testid="confirm-cat-delete">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
