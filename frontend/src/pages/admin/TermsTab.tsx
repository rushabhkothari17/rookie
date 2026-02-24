import { useCallback, useEffect, useState } from "react";
import { ImportModal } from "@/components/admin/ImportModal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { AdminPageHeader } from "./shared/AdminPageHeader";
import { AdminPagination } from "./shared/AdminPagination";
import { Download, Plus, Upload} from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { RichHtmlEditor } from "@/components/ui/RichHtmlEditor";

export function TermsTab() {
  const [terms, setTerms] = useState<any[]>([]);
  const [showImport, setShowImport] = useState(false);
  const [products, setProducts] = useState<any[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const PER_PAGE = 20;

  // Filters
  const [searchFilter, setSearchFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  // Dialogs
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [editTerm, setEditTerm] = useState<any>(null);
  const [createForm, setCreateForm] = useState({ title: "", content: "", is_default: false, status: "active" });
  const [editForm, setEditForm] = useState({ title: "", content: "", status: "active" });
  const [entityLogs, setEntityLogs] = useState<any[]>([]);
  const [showEntityLogs, setShowEntityLogs] = useState(false);
  const [confirmDeleteTerm, setConfirmDeleteTerm] = useState<any>(null);

  const load = useCallback(async (p = 1) => {
    try {
      const params = new URLSearchParams({ page: String(p), per_page: String(PER_PAGE) });
      if (searchFilter) params.append("search", searchFilter);
      if (statusFilter) params.append("status", statusFilter);
      if (startDate) params.append("created_from", startDate);
      if (endDate) params.append("created_to", endDate);
      const [termsRes, prodRes] = await Promise.all([
        api.get(`/admin/terms?${params}`),
        api.get("/admin/products-all?per_page=500"),
      ]);
      setTerms(termsRes.data.terms || []);
      setTotal(termsRes.data.total || 0);
      setTotalPages(termsRes.data.total_pages || 1);
      setPage(p);
      setProducts(prodRes.data.products || []);
    } catch { toast.error("Failed to load terms"); }
  }, [searchFilter, statusFilter, startDate, endDate]);

  useEffect(() => { load(1); }, [searchFilter, statusFilter, startDate, endDate]);

  const handleCreate = async () => {
    try {
      await api.post("/admin/terms", createForm);
      toast.success("Terms created");
      setShowCreateDialog(false);
      setCreateForm({ title: "", content: "", is_default: false, status: "active" });
      load(1);
    } catch (e: any) { toast.error(e.response?.data?.detail || "Failed to create terms"); }
  };

  const openEdit = (t: any) => { setEditTerm(t); setEditForm({ title: t.title, content: t.content, status: t.status }); setShowEditDialog(true); };

  const handleEdit = async () => {
    if (!editTerm) return;
    try {
      await api.put(`/admin/terms/${editTerm.id}`, editForm);
      toast.success("Terms updated");
      setShowEditDialog(false);
      setEditTerm(null);
      load(page);
    } catch (e: any) { toast.error(e.response?.data?.detail || "Failed to update terms"); }
  };

  const handleDelete = async (termId: string) => {
    try { await api.delete(`/admin/terms/${termId}`); toast.success("Terms deleted"); load(page); }
    catch (e: any) { toast.error(e.response?.data?.detail || "Failed to delete"); }
  };

  const downloadCsv = () => {
    const token = localStorage.getItem("aa_token");
    const base = process.env.REACT_APP_BACKEND_URL || "";
    const params = new URLSearchParams();
    if (searchFilter) params.append("search", searchFilter);
    if (statusFilter) params.append("status", statusFilter);
    fetch(`${base}/api/admin/export/terms?${params}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.blob()).then(b => { const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = `terms-${new Date().toISOString().slice(0, 10)}.csv`; a.click(); })
      .catch(() => toast.error("Export failed"));
  };

  return (
    <div className="space-y-4" data-testid="terms-tab">
      <AdminPageHeader
        title="Terms & Conditions"
        subtitle={`${total} documents`}
        actions={
          <>
            <Button size="sm" variant="outline" onClick={downloadCsv} data-testid="admin-terms-export-csv"><Download size={14} className="mr-1" />Export CSV</Button>
            <Button size="sm" variant="outline" onClick={() => setShowImport(true)} data-testid="admin-terms-import-csv"><Upload size={14} className="mr-1" />Import CSV</Button>
            <Button size="sm" onClick={() => setShowCreateDialog(true)} data-testid="admin-terms-create-btn"><Plus size={14} className="mr-1" />Create Terms</Button>
          </>
        }
      />

      {/* Filters */}
      <div className="rounded-xl border border-slate-200 bg-white p-3">
        <div className="flex flex-wrap gap-2 items-end">
          <Input placeholder="Search title…" value={searchFilter} onChange={e => setSearchFilter(e.target.value)} className="h-8 text-xs w-44" data-testid="admin-terms-search-filter" />
          <Select value={statusFilter || "all"} onValueChange={v => setStatusFilter(v === "all" ? "" : v)}>
            <SelectTrigger className="h-8 text-xs w-32 bg-white" data-testid="admin-terms-status-filter"><SelectValue placeholder="All Statuses" /></SelectTrigger>
            <SelectContent><SelectItem value="all">All Statuses</SelectItem><SelectItem value="active">Active</SelectItem><SelectItem value="inactive">Inactive</SelectItem></SelectContent>
          </Select>
          <div className="flex items-center gap-1">
            <span className="text-xs text-slate-400">Created</span>
            <Input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} className="h-8 text-xs w-32" />
            <span className="text-xs text-slate-400">–</span>
            <Input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} className="h-8 text-xs w-32" />
          </div>
          <Button size="sm" variant="outline" onClick={() => { setSearchFilter(""); setStatusFilter(""); setStartDate(""); setEndDate(""); }} className="h-8 text-xs" data-testid="admin-terms-clear-filters">Clear</Button>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
        <Table data-testid="admin-terms-table">
          <TableHeader>
            <TableRow className="bg-slate-50">
              <TableHead>Title</TableHead>
              <TableHead>Preview</TableHead>
              <TableHead>Products Linked</TableHead>
              <TableHead>Default</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Created</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {terms.map((t: any) => {
              const linked = products.filter((p: any) => p.terms_id === t.id);
              return (
                <TableRow key={t.id} data-testid={`admin-terms-row-${t.id}`} className="border-b border-slate-100">
                  <TableCell className="font-semibold">{t.title}</TableCell>
                  <TableCell className="text-xs text-slate-500 max-w-xs truncate">{t.content?.slice(0, 80)}</TableCell>
                  <TableCell>
                    {linked.length === 0 ? <span className="text-xs text-slate-400">None</span> : (
                      <div className="space-y-0.5">
                        {linked.slice(0, 3).map((p: any) => <div key={p.id} className="text-xs text-slate-600">{p.name}</div>)}
                        {linked.length > 3 && <div className="text-xs text-slate-400">+{linked.length - 3} more</div>}
                      </div>
                    )}
                  </TableCell>
                  <TableCell>{t.is_default ? <span className="text-xs px-2 py-1 rounded bg-blue-100 text-blue-700">Default</span> : "—"}</TableCell>
                  <TableCell><span className={`text-xs px-2 py-1 rounded ${t.status === "active" ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-600"}`}>{t.status}</span></TableCell>
                  <TableCell className="text-xs">{t.created_at ? new Date(t.created_at).toLocaleDateString() : "—"}</TableCell>
                  <TableCell>
                    <Button variant="outline" size="sm" className="h-6 px-2 text-[11px]" onClick={() => openEdit(t)} data-testid={`admin-terms-edit-${t.id}`}>Edit</Button>
                    <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px]" onClick={async () => { const r = await api.get(`/admin/terms/${t.id}/logs`); setEntityLogs(r.data.logs || []); setShowEntityLogs(true); }} data-testid={`admin-terms-logs-${t.id}`}>Logs</Button>
                    <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px] text-red-500 hover:text-red-700" onClick={() => setConfirmDeleteTerm(t)} data-testid={`admin-terms-delete-${t.id}`}>Delete</Button>
                  </TableCell>
                </TableRow>
              );
            })}
            {terms.length === 0 && <TableRow><TableCell colSpan={7} className="text-center text-slate-400 py-6">No terms found.</TableCell></TableRow>}
          </TableBody>
        </Table>
      </div>
      <AdminPagination page={page} totalPages={totalPages} total={total} perPage={PER_PAGE} onPage={(p) => load(p)} />

      {/* Create Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="admin-terms-dialog">
          <DialogHeader><DialogTitle>Create Terms & Conditions</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1"><label className="text-xs text-slate-500">Title</label><Input value={createForm.title} onChange={e => setCreateForm({ ...createForm, title: e.target.value })} data-testid="admin-terms-title-input" /></div>
            <div className="space-y-1">
              <label className="text-xs text-slate-500">Content (supports tags)</label>
              <RichHtmlEditor value={createForm.content} onChange={(v) => setCreateForm({ ...createForm, content: v })} minHeight="200px" placeholder="Enter terms content… Tags: {product_name}, {user_name}, {company_name}" />
              <p className="text-xs text-slate-400">Tags: {'{product_name}'}, {'{user_name}'}, {'{company_name}'}, {'{user_email}'}, {'{user_address_line1}'}</p>
            </div>
            <div className="flex items-center gap-2"><input type="checkbox" checked={createForm.is_default} onChange={e => setCreateForm({ ...createForm, is_default: e.target.checked })} /><label className="text-sm">Set as default T&C</label></div>
            <Button onClick={handleCreate} className="w-full" data-testid="admin-terms-submit">Create</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={showEditDialog} onOpenChange={(open) => { setShowEditDialog(open); if (!open) setEditTerm(null); }}>
        <DialogContent className="max-w-2xl" data-testid="admin-terms-edit-dialog">
          <DialogHeader><DialogTitle>Edit Terms: {editTerm?.title}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1"><label className="text-xs text-slate-500">Title</label><Input value={editForm.title} onChange={e => setEditForm({ ...editForm, title: e.target.value })} data-testid="admin-terms-edit-title" /></div>
            <div className="space-y-1"><label className="text-xs text-slate-500">Content</label><RichHtmlEditor value={editForm.content} onChange={(v) => setEditForm({ ...editForm, content: v })} minHeight="200px" placeholder="Enter terms content…" /></div>
            <div className="space-y-1">
              <label className="text-xs text-slate-500">Status</label>
              <Select value={editForm.status} onValueChange={v => setEditForm({ ...editForm, status: v })}>
                <SelectTrigger className="w-full bg-white"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="active">Active</SelectItem><SelectItem value="inactive">Inactive</SelectItem></SelectContent>
              </Select>
            </div>
            <Button onClick={handleEdit} className="w-full" data-testid="admin-terms-edit-save">Save Changes</Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={showEntityLogs} onOpenChange={setShowEntityLogs}>
        <DialogContent className="max-w-2xl"><DialogHeader><DialogTitle>Terms Audit Logs</DialogTitle></DialogHeader>
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
        entity="terms"
        entityLabel="Terms"
        open={showImport}
        onClose={() => setShowImport(false)}
        onSuccess={load}
      />

      {/* Delete Terms Confirmation */}
      <AlertDialog open={!!confirmDeleteTerm} onOpenChange={(open) => !open && setConfirmDeleteTerm(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Terms</AlertDialogTitle>
            <AlertDialogDescription>Are you sure you want to delete "{confirmDeleteTerm?.title}"? This cannot be undone.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction className="bg-red-600 hover:bg-red-700" onClick={() => { handleDelete(confirmDeleteTerm.id); setConfirmDeleteTerm(null); }} data-testid="confirm-terms-delete">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
