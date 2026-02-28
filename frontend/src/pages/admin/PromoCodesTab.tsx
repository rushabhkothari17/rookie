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
import { AuditLogDialog } from "@/components/AuditLogDialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Download, Upload, Plus } from "lucide-react";
import { FieldTip } from "./shared/FieldTip";

const INITIAL_PROMO = { code: "", discount_type: "percent", discount_value: 10, applies_to: "both", applies_to_products: "all", product_ids: [] as string[], expiry_date: "", max_uses: "", one_time_code: false, enabled: true, promo_note: "" };

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
  const [editForm, setEditForm] = useState({ code: "", discount_type: "percent", discount_value: 10, applies_to: "both", applies_to_products: "all", product_ids: [] as string[], expiry_date: "", max_uses: "", one_time_code: false, enabled: true, promo_note: "" });
  const [logsUrl, setLogsUrl] = useState("");
  const [showAuditLogs, setShowAuditLogs] = useState(false);
  const [confirmDeletePromo, setConfirmDeletePromo] = useState<any>(null);

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

  const openEdit = (p: any) => { setEditPromo(p); setEditForm({ code: p.code, discount_type: p.discount_type, discount_value: p.discount_value, applies_to: p.applies_to, applies_to_products: p.applies_to_products || "all", product_ids: p.product_ids || [], expiry_date: p.expiry_date?.slice(0, 10) || "", max_uses: p.max_uses ? String(p.max_uses) : "", one_time_code: p.one_time_code || false, enabled: p.enabled !== false, promo_note: p.promo_note || "" }); setShowEditDialog(true); };

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

  const handleDelete = async (promoId: string) => {
    try { await api.delete(`/admin/promo-codes/${promoId}`); toast.success("Promo code deleted"); load(page); }
    catch (e: any) { toast.error(e.response?.data?.detail || "Failed to delete"); }
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
          <Select value={form.discount_type} onValueChange={v => setF({ ...form, discount_type: v })}>
            <SelectTrigger className="w-full bg-white"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="percent">Percent (%)</SelectItem><SelectItem value="fixed">Fixed ($)</SelectItem></SelectContent>
          </Select>
        </div>
        <div className="space-y-1"><label className="text-xs text-slate-500">Value</label><Input type="number" value={form.discount_value} onChange={e => setF({ ...form, discount_value: parseFloat(e.target.value) })} /></div>
      </div>
      <div className="space-y-1"><label className="text-xs text-slate-500">Applies To</label>
        <Select value={form.applies_to} onValueChange={v => setF({ ...form, applies_to: v })}>
          <SelectTrigger className="w-full bg-white"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="both">Both</SelectItem><SelectItem value="one-time">One-time only</SelectItem><SelectItem value="subscription">Subscription only</SelectItem></SelectContent>
        </Select>
      </div>
      <div className="space-y-1"><label className="text-xs text-slate-500">Product Eligibility</label>
        <Select value={form.applies_to_products} onValueChange={v => setF({ ...form, applies_to_products: v, product_ids: v === "all" ? [] : form.product_ids })}>
          <SelectTrigger className="w-full bg-white"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="all">All Products</SelectItem><SelectItem value="selected">Selected Products</SelectItem></SelectContent>
        </Select>
      </div>
      {form.applies_to_products === "selected" && (
        <div className="space-y-1"><label className="text-xs text-slate-500">Select Products</label>
          <div className="max-h-40 overflow-y-auto border border-slate-200 rounded p-2 space-y-1">
            {prods.map((p: any) => <div key={p.id} className="flex items-center gap-2"><input type="checkbox" checked={form.product_ids.includes(p.id)} onChange={e => setF({ ...form, product_ids: e.target.checked ? [...form.product_ids, p.id] : form.product_ids.filter((id: string) => id !== p.id) })} /><label className="text-xs">{p.name}</label></div>)}
          </div>
        </div>
      )}
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1"><label className="text-xs text-slate-500 flex items-center gap-1">Expiry Date <FieldTip tip="The code stops working after this date at midnight UTC. Leave blank for no expiry." /></label><Input type="date" value={form.expiry_date} onChange={e => setF({ ...form, expiry_date: e.target.value })} /></div>
        <div className="space-y-1"><label className="text-xs text-slate-500 flex items-center gap-1">Max Uses <FieldTip tip="Total number of redemptions allowed across all customers. Once reached, the code is automatically deactivated. Leave blank for unlimited uses." /></label><Input type="number" value={form.max_uses} onChange={e => setF({ ...form, max_uses: e.target.value })} /></div>
      </div>
      <div className="flex items-center gap-4">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={form.one_time_code} onChange={e => setF({ ...form, one_time_code: e.target.checked })} />
          One-time per customer
          <FieldTip tip="When enabled, each customer can only use this code once, even if the Max Uses total hasn't been reached." />
        </label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.enabled} onChange={e => setF({ ...form, enabled: e.target.checked })} />Enabled</label>
      </div>
      <div className="space-y-1">
        <label className="text-xs text-slate-500">Promo Note <span className="text-slate-400">(optional — shown to customer at checkout if filled)</span></label>
        <Textarea
          value={form.promo_note}
          onChange={e => setF({ ...form, promo_note: e.target.value })}
          placeholder="e.g. This code is part of the Zoho Partner Sponsorship Programme."
          className="text-xs resize-none"
          rows={2}
        />
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
          <Select value={statusFilter || "all"} onValueChange={v => setStatusFilter(v === "all" ? "" : v)}>
            <SelectTrigger className="h-8 text-xs w-32 bg-white" data-testid="admin-promo-status-filter"><SelectValue placeholder="All Statuses" /></SelectTrigger>
            <SelectContent><SelectItem value="all">All Statuses</SelectItem><SelectItem value="Active">Active</SelectItem><SelectItem value="Inactive">Inactive</SelectItem><SelectItem value="Expired">Expired</SelectItem></SelectContent>
          </Select>
          <Select value={appliesToFilter || "all"} onValueChange={v => setAppliesToFilter(v === "all" ? "" : v)}>
            <SelectTrigger className="h-8 text-xs w-32 bg-white" data-testid="admin-promo-applies-filter"><SelectValue placeholder="All Types" /></SelectTrigger>
            <SelectContent><SelectItem value="all">All Types</SelectItem><SelectItem value="both">Both</SelectItem><SelectItem value="one-time">One-time</SelectItem><SelectItem value="subscription">Subscription</SelectItem></SelectContent>
          </Select>
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
                  <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px]" onClick={() => { setLogsUrl(`/admin/promo-codes/${promo.id}/logs`); setShowAuditLogs(true); }} data-testid={`admin-promo-logs-${promo.id}`}>Logs</Button>
                  <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px] text-red-500 hover:text-red-700" onClick={() => setConfirmDeletePromo(promo)} data-testid={`admin-promo-delete-${promo.id}`}>Delete</Button>
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

      <AuditLogDialog open={showAuditLogs} onOpenChange={setShowAuditLogs} title="Promo Code Audit Logs" logsUrl={logsUrl} />
      <ImportModal
        entity="promo-codes"
        entityLabel="Promo Codes"
        open={showImport}
        onClose={() => setShowImport(false)}
        onSuccess={load}
      />

      {/* Delete Promo Code Confirmation */}
      <AlertDialog open={!!confirmDeletePromo} onOpenChange={(open) => !open && setConfirmDeletePromo(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Promo Code</AlertDialogTitle>
            <AlertDialogDescription>Are you sure you want to delete the promo code "{confirmDeletePromo?.code}"? This cannot be undone.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction className="bg-red-600 hover:bg-red-700" onClick={() => { handleDelete(confirmDeletePromo.id); setConfirmDeletePromo(null); }} data-testid="confirm-promo-delete">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
