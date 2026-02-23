import { useCallback, useEffect, useState } from "react";
import { ImportModal } from "@/components/admin/ImportModal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { AdminPageHeader } from "./shared/AdminPageHeader";
import { AdminPagination } from "./shared/AdminPagination";
import { Download, Plus } from "lucide-react";

const INITIAL_PROMO = { code: "", discount_type: "percent", discount_value: 10, applies_to: "both", applies_to_products: "all", product_ids: [] as string[], expiry_date: "", max_uses: "", one_time_code: false, enabled: true };

export function PromoCodesTab() {
  const [promoCodes, setPromoCodes] = useState<any[]>([]);
  const [showImport, setShowImport] = useState(false);
  const [products, setProducts] = useState<any[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const PER_PAGE = 20;

  // Filters
  const [codeFilter, setCodeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [appliesToFilter, setAppliesToFilter] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [expiryFrom, setExpiryFrom] = useState("");
  const [expiryTo, setExpiryTo] = useState("");

  // Dialogs
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [editPromo, setEditPromo] = useState<any>(null);
  const [newPromo, setNewPromo] = useState(INITIAL_PROMO);
  const [editForm, setEditForm] = useState({ code: "", discount_type: "percent", discount_value: 10, applies_to: "both", applies_to_products: "all", product_ids: [] as string[], expiry_date: "", max_uses: "", one_time_code: false, enabled: true });
  const [entityLogs, setEntityLogs] = useState<any[]>([]);
  const [showEntityLogs, setShowEntityLogs] = useState(false);

  const load = useCallback(async (p = 1) => {
    try {
      const params = new URLSearchParams({ page: String(p), per_page: String(PER_PAGE) });
      if (codeFilter) params.append("search", codeFilter);
      if (appliesToFilter) params.append("applies_to", appliesToFilter);
      if (statusFilter) params.append("status", statusFilter);
      if (startDate) params.append("created_from", startDate);
      if (endDate) params.append("created_to", endDate);
      const [promoRes, prodRes] = await Promise.all([
        api.get(`/admin/promo-codes?${params}`),
        products.length ? Promise.resolve({ data: { products } }) : api.get("/admin/products-all?per_page=500"),
      ]);
      setPromoCodes(promoRes.data.promo_codes || []);
      setTotal(promoRes.data.total || 0);
      setTotalPages(promoRes.data.total_pages || 1);
      setPage(p);
      if (!products.length) setProducts(prodRes.data.products || []);
    } catch { toast.error("Failed to load promo codes"); }
  }, [codeFilter, appliesToFilter, statusFilter, startDate, endDate]);

  useEffect(() => { load(1); }, [codeFilter, appliesToFilter, statusFilter, startDate, endDate]);

  // Filter by expiry client-side (backend doesn't support this filter)
  const filtered = promoCodes.filter(p => {
    if (!expiryFrom && !expiryTo) return true;
    const exp = p.expiry_date?.slice(0, 10) || "";
    if (expiryFrom && exp && exp < expiryFrom) return false;
    if (expiryTo && exp && exp > expiryTo) return false;
    return true;
  });

  const handleCreate = async () => {
    try {
      await api.post("/admin/promo-codes", { ...newPromo, expiry_date: newPromo.expiry_date || null, max_uses: newPromo.max_uses ? parseInt(newPromo.max_uses) : null });
      toast.success("Promo code created");
      setShowCreateDialog(false);
      setNewPromo(INITIAL_PROMO);
      load(1);
    } catch (e: any) { toast.error(e.response?.data?.detail || "Failed to create promo code"); }
  };

  const openEdit = (p: any) => { setEditPromo(p); setEditForm({ code: p.code, discount_type: p.discount_type, discount_value: p.discount_value, applies_to: p.applies_to, applies_to_products: p.applies_to_products || "all", product_ids: p.product_ids || [], expiry_date: p.expiry_date?.slice(0, 10) || "", max_uses: p.max_uses ? String(p.max_uses) : "", one_time_code: p.one_time_code || false, enabled: p.enabled !== false }); setShowEditDialog(true); };

  const handleEdit = async () => {
    if (!editPromo) return;
    try {
      await api.put(`/admin/promo-codes/${editPromo.id}`, { ...editForm, expiry_date: editForm.expiry_date || null, max_uses: editForm.max_uses ? parseInt(editForm.max_uses) : null });
      toast.success("Promo code updated");
      setShowEditDialog(false);
      setEditPromo(null);
      load(page);
    } catch (e: any) { toast.error(e.response?.data?.detail || "Update failed"); }
  };

  const handleToggle = async (promoId: string, enabled: boolean) => {
    try { await api.put(`/admin/promo-codes/${promoId}`, { enabled }); toast.success("Updated"); load(page); }
    catch (e: any) { toast.error("Update failed"); }
  };

  const downloadCsv = () => {
    const token = localStorage.getItem("aa_token");
    const base = process.env.REACT_APP_BACKEND_URL || "";
    const params = new URLSearchParams();
    if (codeFilter) params.append("search", codeFilter);
    if (appliesToFilter) params.append("applies_to", appliesToFilter);
    if (statusFilter) params.append("status", statusFilter);
    fetch(`${base}/api/admin/export/promo-codes?${params}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.blob()).then(b => { const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = `promo-codes-${new Date().toISOString().slice(0, 10)}.csv`; a.click(); })
      .catch(() => toast.error("Export failed"));
  };

  const PromoForm = ({ form, setF, products: prods }: { form: any, setF: (v: any) => void, products: any[] }) => (
    <div className="space-y-3">
      <div className="space-y-1"><label className="text-xs text-slate-500">Code</label><Input value={form.code} onChange={e => setF({ ...form, code: e.target.value.toUpperCase() })} /></div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1"><label className="text-xs text-slate-500">Discount Type</label>
          <select value={form.discount_type} onChange={e => setF({ ...form, discount_type: e.target.value })} className="w-full h-9 text-sm border border-slate-200 rounded px-2">
            <option value="percent">Percent (%)</option><option value="fixed">Fixed ($)</option>
          </select>
        </div>
        <div className="space-y-1"><label className="text-xs text-slate-500">Value</label><Input type="number" value={form.discount_value} onChange={e => setF({ ...form, discount_value: parseFloat(e.target.value) })} /></div>
      </div>
      <div className="space-y-1"><label className="text-xs text-slate-500">Applies To</label>
        <select value={form.applies_to} onChange={e => setF({ ...form, applies_to: e.target.value })} className="w-full h-9 text-sm border border-slate-200 rounded px-2">
          <option value="both">Both</option><option value="one-time">One-time only</option><option value="subscription">Subscription only</option>
        </select>
      </div>
      <div className="space-y-1"><label className="text-xs text-slate-500">Product Eligibility</label>
        <select value={form.applies_to_products} onChange={e => setF({ ...form, applies_to_products: e.target.value, product_ids: e.target.value === "all" ? [] : form.product_ids })} className="w-full h-9 text-sm border border-slate-200 rounded px-2">
          <option value="all">All Products</option><option value="selected">Selected Products</option>
        </select>
      </div>
      {form.applies_to_products === "selected" && (
        <div className="space-y-1"><label className="text-xs text-slate-500">Select Products</label>
          <div className="max-h-40 overflow-y-auto border border-slate-200 rounded p-2 space-y-1">
            {prods.map((p: any) => <div key={p.id} className="flex items-center gap-2"><input type="checkbox" checked={form.product_ids.includes(p.id)} onChange={e => setF({ ...form, product_ids: e.target.checked ? [...form.product_ids, p.id] : form.product_ids.filter((id: string) => id !== p.id) })} /><label className="text-xs">{p.name}</label></div>)}
          </div>
        </div>
      )}
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1"><label className="text-xs text-slate-500">Expiry Date</label><Input type="date" value={form.expiry_date} onChange={e => setF({ ...form, expiry_date: e.target.value })} /></div>
        <div className="space-y-1"><label className="text-xs text-slate-500">Max Uses</label><Input type="number" value={form.max_uses} onChange={e => setF({ ...form, max_uses: e.target.value })} /></div>
      </div>
      <div className="flex items-center gap-4">
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.one_time_code} onChange={e => setF({ ...form, one_time_code: e.target.checked })} />One-time per customer</label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.enabled} onChange={e => setF({ ...form, enabled: e.target.checked })} />Enabled</label>
      </div>
    </div>
  );

  return (
    <div className="space-y-4" data-testid="promo-codes-tab">
      <AdminPageHeader title="Promo Codes" subtitle={`${total} codes`} actions={
        <>
          <Button size="sm" variant="outline" onClick={downloadCsv} data-testid="admin-promo-export-csv"><Download size={14} className="mr-1" />Export CSV</Button>
          <Button size="sm" variant="outline" onClick={() => setShowImport(true)} data-testid="admin-promo-import-csv"><Upload size={14} className="mr-1" />Import CSV</Button>
          <Button size="sm" onClick={() => setShowCreateDialog(true)} data-testid="admin-promo-create"><Plus size={14} className="mr-1" />Create Promo Code</Button>
        </>
      } />

      {/* Filters */}
      <div className="rounded-xl border border-slate-200 bg-white p-3">
        <div className="flex flex-wrap gap-2 items-end">
          <Input placeholder="Filter by code…" value={codeFilter} onChange={e => setCodeFilter(e.target.value)} className="h-8 text-xs w-36" data-testid="admin-promo-code-filter" />
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="h-8 text-xs border border-slate-200 rounded px-2 bg-white" data-testid="admin-promo-status-filter">
            <option value="">All Statuses</option><option value="Active">Active</option><option value="Inactive">Inactive</option><option value="Expired">Expired</option>
          </select>
          <select value={appliesToFilter} onChange={e => setAppliesToFilter(e.target.value)} className="h-8 text-xs border border-slate-200 rounded px-2 bg-white" data-testid="admin-promo-applies-filter">
            <option value="">All Types</option><option value="both">Both</option><option value="one-time">One-time</option><option value="subscription">Subscription</option>
          </select>
          <div className="flex items-center gap-1">
            <span className="text-xs text-slate-400">Created</span>
            <Input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} className="h-8 text-xs w-32" />
            <span className="text-xs text-slate-400">–</span>
            <Input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} className="h-8 text-xs w-32" />
          </div>
          <div className="flex items-center gap-1">
            <span className="text-xs text-slate-400">Expiry</span>
            <Input type="date" value={expiryFrom} onChange={e => setExpiryFrom(e.target.value)} className="h-8 text-xs w-32" />
            <span className="text-xs text-slate-400">–</span>
            <Input type="date" value={expiryTo} onChange={e => setExpiryTo(e.target.value)} className="h-8 text-xs w-32" />
          </div>
          <Button size="sm" variant="outline" onClick={() => { setCodeFilter(""); setStatusFilter(""); setAppliesToFilter(""); setStartDate(""); setEndDate(""); setExpiryFrom(""); setExpiryTo(""); }} className="h-8 text-xs" data-testid="admin-promo-clear-filters">Clear</Button>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
        <Table data-testid="admin-promo-table">
          <TableHeader>
            <TableRow className="bg-slate-50">
              <TableHead>Code</TableHead>
              <TableHead>Discount</TableHead>
              <TableHead>Applies To</TableHead>
              <TableHead>Expiry</TableHead>
              <TableHead>Usage</TableHead>
              <TableHead>Created</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Enabled</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((promo) => (
              <TableRow key={promo.id} data-testid={`admin-promo-row-${promo.id}`} className="border-b border-slate-100">
                <TableCell className="font-mono font-semibold">{promo.code}</TableCell>
                <TableCell>{promo.discount_type === "percent" ? `${promo.discount_value}%` : `$${promo.discount_value}`}</TableCell>
                <TableCell className="capitalize">{promo.applies_to}</TableCell>
                <TableCell>{promo.expiry_date?.slice(0, 10) || "—"}</TableCell>
                <TableCell>{promo.usage_count}{promo.max_uses ? ` / ${promo.max_uses}` : ""}</TableCell>
                <TableCell>{promo.created_at ? new Date(promo.created_at).toLocaleDateString("en-AU") : "—"}</TableCell>
                <TableCell><span className={`px-2 py-0.5 rounded ${promo.status === "Active" ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-600"}`}>{promo.status}</span></TableCell>
                <TableCell>
                  <button onClick={() => handleToggle(promo.id, !promo.enabled)} className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${promo.enabled ? "bg-slate-900" : "bg-slate-200"}`} data-testid={`admin-promo-toggle-${promo.id}`}>
                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${promo.enabled ? "translate-x-4" : "translate-x-0.5"}`} />
                  </button>
                </TableCell>
                <TableCell>
                  <Button variant="outline" size="sm" className="h-6 px-2 text-[11px]" onClick={() => openEdit(promo)} data-testid={`admin-promo-edit-${promo.id}`}>Edit</Button>
                  <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px]" onClick={async () => { const r = await api.get(`/admin/promo-codes/${promo.id}/logs`); setEntityLogs(r.data.logs || []); setShowEntityLogs(true); }} data-testid={`admin-promo-logs-${promo.id}`}>Logs</Button>
                </TableCell>
              </TableRow>
            ))}
            {filtered.length === 0 && <TableRow><TableCell colSpan={9} className="text-center text-slate-400 py-6">No promo codes found.</TableCell></TableRow>}
          </TableBody>
        </Table>
      </div>
      <AdminPagination page={page} totalPages={totalPages} total={total} perPage={PER_PAGE} onPage={(p) => load(p)} />

      {/* Create Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent data-testid="admin-promo-dialog"><DialogHeader><DialogTitle>Create Promo Code</DialogTitle></DialogHeader>
          <PromoForm form={newPromo} setF={setNewPromo} products={products} />
          <Button onClick={handleCreate} className="w-full mt-4" data-testid="admin-promo-submit">Create</Button>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={showEditDialog} onOpenChange={(open) => { setShowEditDialog(open); if (!open) setEditPromo(null); }}>
        <DialogContent data-testid="admin-promo-edit-dialog"><DialogHeader><DialogTitle>Edit Promo Code: {editPromo?.code}</DialogTitle></DialogHeader>
          <PromoForm form={editForm} setF={setEditForm} products={products} />
          <Button onClick={handleEdit} className="w-full mt-4" data-testid="admin-promo-edit-save">Save Changes</Button>
        </DialogContent>
      </Dialog>

      <Dialog open={showEntityLogs} onOpenChange={setShowEntityLogs}>
        <DialogContent className="max-w-2xl"><DialogHeader><DialogTitle>Promo Code Audit Logs</DialogTitle></DialogHeader>
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
    </div>
  );
}
