import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { AdminPageHeader } from "./shared/AdminPageHeader";
import { AdminPagination } from "./shared/AdminPagination";
import { Download, Plus } from "lucide-react";

const STATUS_BADGE: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-700",
  inactive: "bg-slate-100 text-slate-500",
  expired: "bg-red-100 text-red-600",
};

export function OverrideCodesTab() {
  const [codes, setCodes] = useState<any[]>([]);
  const [customers, setCustomers] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const PER_PAGE = 20;

  // Filters
  const [emailFilter, setEmailFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [createdFrom, setCreatedFrom] = useState("");
  const [createdTo, setCreatedTo] = useState("");
  const [expiresFrom, setExpiresFrom] = useState("");
  const [expiresTo, setExpiresTo] = useState("");

  // Dialogs
  const [showCreate, setShowCreate] = useState(false);
  const [editingCode, setEditingCode] = useState<any>(null);
  const [createForm, setCreateForm] = useState({ code: "", customer_id: "", expires_at: "" });
  const [editForm, setEditForm] = useState({ code: "", customer_id: "", status: "", expires_at: "" });
  const [customerSearch, setCustomerSearch] = useState("");
  const [entityLogs, setEntityLogs] = useState<any[]>([]);
  const [showEntityLogs, setShowEntityLogs] = useState(false);

  const userMap: Record<string, any> = {};
  users.forEach(u => { userMap[u.id] = u; });

  const load = useCallback(async (p = 1) => {
    try {
      const params = new URLSearchParams({ page: String(p), per_page: String(PER_PAGE) });
      if (statusFilter) params.append("status", statusFilter);
      if (emailFilter) params.append("customer_email", emailFilter);
      if (createdFrom) params.append("created_from", createdFrom);
      if (createdTo) params.append("created_to", createdTo);
      if (expiresFrom) params.append("expires_from", expiresFrom);
      if (expiresTo) params.append("expires_to", expiresTo);
      const res = await api.get(`/admin/override-codes?${params}`);
      setCodes(res.data.override_codes || []);
      setTotal(res.data.total || 0);
      setTotalPages(res.data.total_pages || 1);
      setPage(p);
    } catch { toast.error("Failed to load override codes"); }
  }, [statusFilter, emailFilter, createdFrom, createdTo, expiresFrom, expiresTo]);

  useEffect(() => {
    api.get("/admin/customers?per_page=1000").then(r => {
      setCustomers(r.data.customers || []);
      setUsers(r.data.users || []);
    }).catch(() => {});
  }, []);

  useEffect(() => { load(1); }, [statusFilter, emailFilter, createdFrom, createdTo, expiresFrom, expiresTo]);

  const filteredCustomers = customers.filter(c => {
    const u = userMap[c.user_id];
    const q = customerSearch.toLowerCase();
    return !q || u?.email?.toLowerCase().includes(q) || c.company_name?.toLowerCase().includes(q);
  }).slice(0, 10);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createForm.code.trim() || !createForm.customer_id) { toast.error("Code and customer are required"); return; }
    try {
      await api.post("/admin/override-codes", { code: createForm.code.trim(), customer_id: createForm.customer_id, expires_at: createForm.expires_at ? new Date(createForm.expires_at).toISOString() : undefined });
      toast.success("Override code created");
      setCreateForm({ code: "", customer_id: "", expires_at: "" });
      setCustomerSearch("");
      setShowCreate(false);
      load(page);
    } catch (err: any) { toast.error(err?.response?.data?.detail || "Failed to create override code"); }
  };

  const openEdit = (oc: any) => { setEditingCode(oc); setEditForm({ code: oc.code, customer_id: oc.customer_id, status: oc.effective_status || oc.status, expires_at: oc.expires_at ? oc.expires_at.slice(0, 10) : "" }); setCustomerSearch(oc.customer_email || ""); };

  const handleEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingCode) return;
    try {
      await api.put(`/admin/override-codes/${editingCode.id}`, { code: editForm.code, customer_id: editForm.customer_id, status: editForm.status, expires_at: editForm.expires_at ? new Date(editForm.expires_at).toISOString() : null });
      toast.success("Override code updated");
      setEditingCode(null);
      setCustomerSearch("");
      load(page);
    } catch (err: any) { toast.error(err?.response?.data?.detail || "Failed to update override code"); }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this override code?")) return;
    try { await api.delete(`/admin/override-codes/${id}`); toast.success("Deleted"); load(page); }
    catch (err: any) { toast.error(err?.response?.data?.detail || "Failed to delete"); }
  };

  const downloadCsv = () => {
    const token = localStorage.getItem("aa_token");
    const base = process.env.REACT_APP_BACKEND_URL || "";
    const params = new URLSearchParams();
    if (statusFilter) params.append("status", statusFilter);
    if (emailFilter) params.append("customer_email", emailFilter);
    fetch(`${base}/api/admin/export/override-codes?${params}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.blob()).then(b => { const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = `override-codes-${new Date().toISOString().slice(0, 10)}.csv`; a.click(); })
      .catch(() => toast.error("Export failed"));
  };

  const clearFilters = () => { setEmailFilter(""); setStatusFilter(""); setCreatedFrom(""); setCreatedTo(""); setExpiresFrom(""); setExpiresTo(""); };

  return (
    <div className="space-y-4" data-testid="override-codes-tab">
      <AdminPageHeader title="Override Codes" subtitle={`${total} codes`} actions={
        <>
          <Button size="sm" variant="outline" onClick={downloadCsv} data-testid="admin-oc-export-csv"><Download size={14} className="mr-1" />Export CSV</Button>
          <Button size="sm" onClick={() => setShowCreate(true)} data-testid="admin-oc-create-btn"><Plus size={14} className="mr-1" />Create Override Code</Button>
        </>
      } />

      {/* Filters */}
      <div className="rounded-xl border border-slate-200 bg-white p-3">
        <div className="flex flex-wrap gap-2 items-end">
          <Input placeholder="Customer email…" value={emailFilter} onChange={e => setEmailFilter(e.target.value)} className="h-8 text-xs w-44" data-testid="admin-oc-email-filter" />
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="h-8 text-xs border border-slate-200 rounded px-2 bg-white" data-testid="admin-oc-status-filter">
            <option value="">All Statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="expired">Expired</option>
          </select>
          <div className="flex items-center gap-1">
            <span className="text-xs text-slate-400">Created</span>
            <Input type="date" value={createdFrom} onChange={e => setCreatedFrom(e.target.value)} className="h-8 text-xs w-32" />
            <span className="text-xs text-slate-400">–</span>
            <Input type="date" value={createdTo} onChange={e => setCreatedTo(e.target.value)} className="h-8 text-xs w-32" />
          </div>
          <div className="flex items-center gap-1">
            <span className="text-xs text-slate-400">Expires</span>
            <Input type="date" value={expiresFrom} onChange={e => setExpiresFrom(e.target.value)} className="h-8 text-xs w-32" />
            <span className="text-xs text-slate-400">–</span>
            <Input type="date" value={expiresTo} onChange={e => setExpiresTo(e.target.value)} className="h-8 text-xs w-32" />
          </div>
          <Button size="sm" variant="outline" onClick={clearFilters} className="h-8 text-xs" data-testid="admin-oc-clear-filters">Clear</Button>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
        <Table data-testid="admin-oc-table">
          <TableHeader>
            <TableRow className="bg-slate-50">
              <TableHead>Code</TableHead>
              <TableHead>Customer Email</TableHead>
              <TableHead>Customer Name</TableHead>
              <TableHead>Created</TableHead>
              <TableHead>Expires</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {codes.map((oc) => (
              <TableRow key={oc.id} data-testid={`admin-oc-row-${oc.id}`} className="border-b border-slate-100">
                <TableCell className="font-mono font-semibold">{oc.code}</TableCell>
                <TableCell>{oc.customer_email || oc.customer_id}</TableCell>
                <TableCell className="text-slate-500">{oc.customer_name || "—"}</TableCell>
                <TableCell className="text-xs">{oc.created_at?.slice(0, 10) || "—"}</TableCell>
                <TableCell className="text-xs">{oc.expires_at?.slice(0, 10) || "Never"}</TableCell>
                <TableCell><span className={`text-xs px-2 py-0.5 rounded font-semibold ${STATUS_BADGE[oc.effective_status] || "bg-slate-100 text-slate-600"}`}>{oc.effective_status || oc.status}</span></TableCell>
                <TableCell>
                  <div className="flex gap-1">
                    <Button variant="outline" size="sm" className="h-6 px-2 text-[11px]" onClick={() => openEdit(oc)} data-testid={`admin-oc-edit-${oc.id}`}>Edit</Button>
                    <Button variant="destructive" size="sm" className="h-6 px-2 text-[11px]" onClick={() => handleDelete(oc.id)} data-testid={`admin-oc-delete-${oc.id}`}>Delete</Button>
                    <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px]" onClick={async () => { const r = await api.get(`/admin/override-codes/${oc.id}/logs`); setEntityLogs(r.data.logs || []); setShowEntityLogs(true); }} data-testid={`admin-oc-logs-${oc.id}`}>Logs</Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
            {codes.length === 0 && <TableRow><TableCell colSpan={7} className="text-center text-slate-400 py-8">No override codes found.</TableCell></TableRow>}
          </TableBody>
        </Table>
      </div>
      <AdminPagination page={page} totalPages={totalPages} total={total} perPage={PER_PAGE} onPage={(p) => load(p)} />

      {/* Create Dialog */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent data-testid="admin-oc-create-dialog">
          <DialogHeader><DialogTitle>Create Override Code</DialogTitle></DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4 pt-2">
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-700">Code *</label>
              <Input value={createForm.code} onChange={e => setCreateForm({ ...createForm, code: e.target.value.toUpperCase() })} placeholder="e.g. SPECIAL123" data-testid="admin-oc-code-input" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-700">Customer (search by email) *</label>
              <Input placeholder="Type email to search…" value={customerSearch} onChange={e => setCustomerSearch(e.target.value)} />
              {customerSearch && filteredCustomers.length > 0 && (
                <div className="border border-slate-200 rounded bg-white shadow-sm max-h-40 overflow-y-auto">
                  {filteredCustomers.map((c: any) => { const u = userMap[c.user_id]; return (
                    <div key={c.id} onClick={() => { setCreateForm({ ...createForm, customer_id: c.id }); setCustomerSearch(u?.email || ""); }} className="px-3 py-2 hover:bg-slate-50 cursor-pointer text-xs">{u?.email} {c.company_name ? `— ${c.company_name}` : ""}</div>
                  ); })}
                </div>
              )}
              {createForm.customer_id && <p className="text-xs text-green-600">Customer selected</p>}
            </div>
            <div className="space-y-1"><label className="text-xs font-medium text-slate-700">Expires At (optional)</label><Input type="date" value={createForm.expires_at} onChange={e => setCreateForm({ ...createForm, expires_at: e.target.value })} /></div>
            <div className="flex gap-2 justify-end"><Button variant="outline" type="button" onClick={() => setShowCreate(false)}>Cancel</Button><Button type="submit" data-testid="admin-oc-create-submit">Create</Button></div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={!!editingCode} onOpenChange={(open) => { if (!open) { setEditingCode(null); setCustomerSearch(""); } }}>
        <DialogContent data-testid="admin-oc-edit-dialog">
          <DialogHeader><DialogTitle>Edit Override Code</DialogTitle></DialogHeader>
          {editingCode && (
            <form onSubmit={handleEdit} className="space-y-4 pt-2">
              <div className="space-y-1"><label className="text-xs font-medium text-slate-700">Code *</label><Input value={editForm.code} onChange={e => setEditForm({ ...editForm, code: e.target.value.toUpperCase() })} /></div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-700">Customer (search by email)</label>
                <Input placeholder="Type email to search…" value={customerSearch} onChange={e => setCustomerSearch(e.target.value)} />
                {customerSearch && filteredCustomers.length > 0 && (
                  <div className="border border-slate-200 rounded bg-white shadow-sm max-h-40 overflow-y-auto">
                    {filteredCustomers.map((c: any) => { const u = userMap[c.user_id]; return (
                      <div key={c.id} onClick={() => { setEditForm({ ...editForm, customer_id: c.id }); setCustomerSearch(u?.email || ""); }} className="px-3 py-2 hover:bg-slate-50 cursor-pointer text-xs">{u?.email} {c.company_name ? `— ${c.company_name}` : ""}</div>
                    ); })}
                  </div>
                )}
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-700">Status</label>
                <select value={editForm.status} onChange={e => setEditForm({ ...editForm, status: e.target.value })} className="w-full h-9 text-sm border border-slate-200 rounded px-2">
                  <option value="active">Active</option><option value="inactive">Inactive</option>
                </select>
              </div>
              <div className="space-y-1"><label className="text-xs font-medium text-slate-700">Expires At</label><Input type="date" value={editForm.expires_at} onChange={e => setEditForm({ ...editForm, expires_at: e.target.value })} /></div>
              <div className="flex gap-2 justify-end"><Button variant="outline" type="button" onClick={() => setEditingCode(null)}>Cancel</Button><Button type="submit">Save Changes</Button></div>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
