import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { ImportModal } from "@/components/admin/ImportModal";
import { RequiredLabel } from "@/components/shared/RequiredLabel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHeader, TableRow } from "@/components/ui/table";
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
import { ColHeader } from "@/components/shared/ColHeader";

const INITIAL_PROMO = { code: "", discount_type: "percent", discount_value: 10, applies_to: "both", applies_to_products: "all", product_ids: [] as string[], expiry_date: "", max_uses: "", one_time_code: false, enabled: true, promo_note: "" };

const getPromoStatus = (promo: any): string => {
  if (promo.expiry_date && new Date(promo.expiry_date) < new Date()) return "Expired";
  if (promo.max_uses && (promo.usage_count || 0) >= promo.max_uses) return "Inactive";
  if (!promo.enabled) return "Inactive";
  return "Active";
};

// Defined OUTSIDE PromoCodesTab to prevent remount on every keystroke
function PromoForm({ form, setF, products: prods }: { form: any, setF: (v: any) => void, products: any[] }) {
  const isPercent = form.discount_type === "percent" || form.discount_type === "percentage";
  const valError = form.discount_value < 0
    ? "Discount value cannot be negative"
    : isPercent && form.discount_value > 100
    ? "Percentage discount cannot exceed 100%"
    : null;

  return (
    <div className="space-y-3">
      <div className="space-y-1"><RequiredLabel className="text-slate-500 font-normal">Code</RequiredLabel><Input value={form.code} onChange={e => setF({ ...form, code: e.target.value.toUpperCase().slice(0, 100) })} maxLength={100} /></div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1"><RequiredLabel className="text-slate-500 font-normal">Discount Type</RequiredLabel>
          <Select value={form.discount_type} onValueChange={v => setF({ ...form, discount_type: v })}>
            <SelectTrigger className="w-full bg-white"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="percent">Percent (%)</SelectItem><SelectItem value="fixed">Fixed ($)</SelectItem></SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <RequiredLabel className="text-slate-500 font-normal">Value {isPercent && <span className="text-slate-400 font-normal">(0–100)</span>}</RequiredLabel>
          <Input
            type="number"
            value={form.discount_value}
            onChange={e => setF({ ...form, discount_value: parseFloat(e.target.value) })}
            min={0}
            max={isPercent ? 100 : undefined}
            step="0.01"
            className={valError ? "border-red-400 focus-visible:ring-red-300" : ""}
          />
          {valError && <p className="text-xs text-red-500 mt-0.5">{valError}</p>}
        </div>
      </div>
      <div className="space-y-1"><RequiredLabel className="text-slate-500 font-normal">Applies To</RequiredLabel>
        <Select value={form.applies_to} onValueChange={v => setF({ ...form, applies_to: v })}>
          <SelectTrigger className="w-full bg-white"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="both">Both</SelectItem><SelectItem value="one-time">One-time only</SelectItem><SelectItem value="subscription">Subscription only</SelectItem></SelectContent>
        </Select>
      </div>
      <div className="space-y-1"><RequiredLabel className="text-slate-500 font-normal">Product Eligibility</RequiredLabel>
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
        <div className="space-y-1"><RequiredLabel className="text-slate-500 font-normal flex items-center gap-1" trailing={<FieldTip tip="The code stops working after this date at midnight UTC. Leave blank for no expiry." />}>Expiry Date</RequiredLabel><Input type="date" value={form.expiry_date} onChange={e => setF({ ...form, expiry_date: e.target.value })} /></div>
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
          maxLength={5000}
          placeholder="e.g. This code is part of the Zoho Partner Sponsorship Programme."
          className="text-xs resize-none"
          rows={2}
        />
      </div>
    </div>
  );
}

export function PromoCodesTab() {
  const { user: authUser } = useAuth();
  const isPlatformAdmin = authUser?.role === "platform_admin" || authUser?.role === "platform_super_admin";
  const [promoCodes, setPromoCodes] = useState<any[]>([]);
  const [showImport, setShowImport] = useState(false);
  const [products, setProducts] = useState<any[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const PER_PAGE = 20;

  // Filters
  const [codeFilter, setCodeFilter] = useState<string[]>([]);
  const [discountFilter, setDiscountFilter] = useState<string[]>([]);
  const [appliesToFilter, setAppliesToFilter] = useState<string[]>([]);
  const [usageFilter, setUsageFilter] = useState<string[]>([]);
  const [statusFilter, setStatusFilter] = useState<string[]>([]);
  const [partnerFilter, setPartnerFilter] = useState<string[]>([]);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [expiryFrom, setExpiryFrom] = useState("");
  const [expiryTo, setExpiryTo] = useState("");
  const [colSort, setColSort] = useState<{ col: string; dir: "asc" | "desc" } | null>(null);

  // Build unique options for dropdowns
  const uniqueCodes = useMemo(() => {
    return Array.from(new Set(promoCodes.map(p => p.code).filter(Boolean))).sort().map(c => [c, c] as [string, string]);
  }, [promoCodes]);

  const uniquePartners = useMemo(() => {
    return Array.from(new Set(promoCodes.map(p => p.partner_code).filter(Boolean))).sort().map(c => [c, c] as [string, string]);
  }, [promoCodes]);

  const uniqueDiscounts = useMemo(() => {
    const discounts = new Set(promoCodes.map(p => p.discount_type === "percent" ? `${p.discount_value}%` : `$${p.discount_value}`));
    return Array.from(discounts).sort().map(d => [d, d] as [string, string]);
  }, [promoCodes]);

  const uniqueUsages = useMemo(() => {
    const usages = new Set(promoCodes.map(p => `${p.usage_count || 0}${p.max_uses ? ` / ${p.max_uses}` : ""}`));
    return Array.from(usages).sort().map(u => [u, u] as [string, string]);
  }, [promoCodes]);

  const displayPromos = useMemo(() => {
    let r = [...promoCodes];
    // Apply local multi-select filters
    if (codeFilter.length > 0) r = r.filter(p => codeFilter.includes(p.code));
    if (partnerFilter.length > 0) r = r.filter(p => partnerFilter.includes(p.partner_code));
    if (discountFilter.length > 0) r = r.filter(p => {
      const disc = p.discount_type === "percent" ? `${p.discount_value}%` : `$${p.discount_value}`;
      return discountFilter.includes(disc);
    });
    if (appliesToFilter.length > 0) r = r.filter(p => appliesToFilter.includes(p.applies_to));
    if (usageFilter.length > 0) r = r.filter(p => {
      const usage = `${p.usage_count || 0}${p.max_uses ? ` / ${p.max_uses}` : ""}`;
      return usageFilter.includes(usage);
    });
    if (statusFilter.length > 0) r = r.filter(p => statusFilter.includes(getPromoStatus(p)));
    // Date range filters
    if (expiryFrom || expiryTo) {
      r = r.filter(p => {
        const exp = p.expiry_date?.slice(0, 10) || "";
        if (expiryFrom && exp && exp < expiryFrom) return false;
        if (expiryTo && exp && exp > expiryTo) return false;
        return true;
      });
    }
    if (colSort) {
      r.sort((a, b) => {
        let av: any = "", bv: any = "";
        if (colSort.col === "code") { av = a.code; bv = b.code; }
        else if (colSort.col === "discount") { av = a.discount_value; bv = b.discount_value; }
        else if (colSort.col === "applies_to") { av = a.applies_to; bv = b.applies_to; }
        else if (colSort.col === "partner") { av = a.partner_code || ""; bv = b.partner_code || ""; }
        else if (colSort.col === "expiry") { av = a.expiry_date || ""; bv = b.expiry_date || ""; }
        else if (colSort.col === "max_uses") { av = a.max_uses ?? 0; bv = b.max_uses ?? 0; }
        else if (colSort.col === "uses") { av = a.use_count ?? 0; bv = b.use_count ?? 0; }
        else if (colSort.col === "status") { av = a.enabled ? 1 : 0; bv = b.enabled ? 1 : 0; }
        else if (colSort.col === "created") { av = a.created_at || ""; bv = b.created_at || ""; }
        if (av < bv) return colSort.dir === "asc" ? -1 : 1;
        if (av > bv) return colSort.dir === "asc" ? 1 : -1;
        return 0;
      });
    }
    return r;
  }, [promoCodes, codeFilter, discountFilter, appliesToFilter, usageFilter, statusFilter, expiryFrom, expiryTo, colSort]);

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
      const params = new URLSearchParams({ page: String(p), per_page: String(500) });
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
  }, [startDate, endDate]);

  useEffect(() => { load(1); }, [startDate, endDate]);

  const [saving, setSaving] = useState(false);

  const handleCreate = async () => {
    if (!newPromo.code.trim()) { toast.error("Promo code is required"); return; }
    if (!newPromo.discount_type) { toast.error("Discount type is required"); return; }
    if (newPromo.discount_value == null || newPromo.discount_value === undefined) { toast.error("Discount value is required"); return; }
    if (newPromo.discount_value < 0) { toast.error("Discount value cannot be negative"); return; }
    const isPercent = newPromo.discount_type === "percent" || newPromo.discount_type === "percentage";
    if (isPercent && newPromo.discount_value > 100) { toast.error("Percentage discount cannot exceed 100%"); return; }
    if (!newPromo.applies_to) { toast.error("Applies to is required"); return; }
    if (!newPromo.applies_to_products) { toast.error("Product eligibility is required"); return; }
    // expiry_date is optional — no expiry means the code never expires
    setSaving(true);
    try {
      await api.post("/admin/promo-codes", { ...newPromo, expiry_date: newPromo.expiry_date || null, max_uses: newPromo.max_uses ? parseInt(newPromo.max_uses) : null });
      toast.success("Promo code created");
      setShowCreateDialog(false);
      setNewPromo(INITIAL_PROMO);
      load(1);
    } catch (e: any) { toast.error(e.response?.data?.detail || "Failed to create promo code"); }
    finally { setSaving(false); }
  };

  const openEdit = (p: any) => { setEditPromo(p); setEditForm({ code: p.code, discount_type: p.discount_type, discount_value: p.discount_value, applies_to: p.applies_to, applies_to_products: p.applies_to_products || "all", product_ids: p.product_ids || [], expiry_date: p.expiry_date?.slice(0, 10) || "", max_uses: p.max_uses ? String(p.max_uses) : "", one_time_code: p.one_time_code || false, enabled: p.enabled !== false, promo_note: p.promo_note || "" }); setShowEditDialog(true); };

  const handleEdit = async () => {
    if (!editPromo) return;
    if (!editForm.code?.trim()) { toast.error("Promo code is required"); return; }
    if (editForm.discount_value < 0) { toast.error("Discount value cannot be negative"); return; }
    const isEditPercent = editForm.discount_type === "percent" || editForm.discount_type === "percentage";
    if (isEditPercent && editForm.discount_value > 100) { toast.error("Percentage discount cannot exceed 100%"); return; }
    if (!editForm.expiry_date) { toast.error("Expiry date is required"); return; }
    setSaving(true);
    try {
      await api.put(`/admin/promo-codes/${editPromo.id}`, { ...editForm, expiry_date: editForm.expiry_date || null, max_uses: editForm.max_uses ? parseInt(editForm.max_uses) : null });
      toast.success("Promo code updated");
      setShowEditDialog(false);
      setEditPromo(null);
      load(page);
    } catch (e: any) { toast.error(e.response?.data?.detail || "Update failed"); }
    finally { setSaving(false); }
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
    if (codeFilter.length > 0) params.append("search", codeFilter.join(","));
    if (appliesToFilter.length > 0) params.append("applies_to", appliesToFilter.join(","));
    if (statusFilter.length > 0) params.append("status", statusFilter.join(","));
    fetch(`${base}/api/admin/export/promo-codes?${params}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.blob()).then(b => { const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = `promo-codes-${new Date().toISOString().slice(0, 10)}.csv`; a.click(); })
      .catch(() => toast.error("Export failed"));
  };

  return (
    <div className="flex flex-col gap-4" data-testid="promo-codes-tab">
      <AdminPageHeader title="Promo Codes" subtitle={`${total} codes`} actions={
        <>
          <Button size="sm" variant="outline" onClick={downloadCsv} data-testid="admin-promo-export-csv"><Download size={14} className="mr-1" />Export CSV</Button>
          <Button size="sm" variant="outline" onClick={() => setShowImport(true)} data-testid="admin-promo-import-csv"><Upload size={14} className="mr-1" />Import CSV</Button>
          <Button size="sm" onClick={() => setShowCreateDialog(true)} data-testid="admin-promo-create"><Plus size={14} className="mr-1" />Create Promo Code</Button>
        </>
      } />

      {/* Filters removed — use column headers */}

      {/* Table */}
      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
        <Table data-testid="admin-promo-table">
          <TableHeader>
            <TableRow className="bg-slate-50">
              <ColHeader label="Code" colKey="code" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={codeFilter} onFilter={v => { setCodeFilter(v); setPage(1); }} onClearFilter={() => { setCodeFilter([]); setPage(1); }} statusOptions={uniqueCodes} />
              {isPlatformAdmin && <ColHeader label="Partner" colKey="partner" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={partnerFilter} onFilter={v => { setPartnerFilter(v); setPage(1); }} onClearFilter={() => { setPartnerFilter([]); setPage(1); }} statusOptions={uniquePartners} />}
              <ColHeader label="Discount" colKey="discount" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={discountFilter} onFilter={v => { setDiscountFilter(v); setPage(1); }} onClearFilter={() => { setDiscountFilter([]); setPage(1); }} statusOptions={uniqueDiscounts} />
              <ColHeader label="Applies To" colKey="applies_to" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={appliesToFilter} onFilter={v => { setAppliesToFilter(v); setPage(1); }} onClearFilter={() => { setAppliesToFilter([]); setPage(1); }} statusOptions={[["both", "Both"], ["one-time", "One-time"], ["subscription", "Subscription"]]} />
              <ColHeader label="Expiry" colKey="expiry" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="date-range" filterValue={{ from: expiryFrom, to: expiryTo }} onFilter={v => { setExpiryFrom(v.from || ""); setExpiryTo(v.to || ""); }} onClearFilter={() => { setExpiryFrom(""); setExpiryTo(""); }} />
              <ColHeader label="Usage" colKey="uses" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={usageFilter} onFilter={v => { setUsageFilter(v); setPage(1); }} onClearFilter={() => { setUsageFilter([]); setPage(1); }} statusOptions={uniqueUsages} />
              <ColHeader label="Created" colKey="created" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="date-range" filterValue={{ from: startDate, to: endDate }} onFilter={v => { setStartDate(v.from || ""); setEndDate(v.to || ""); setPage(1); }} onClearFilter={() => { setStartDate(""); setEndDate(""); setPage(1); }} />
              <ColHeader label="Status" colKey="status" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={statusFilter} onFilter={v => { setStatusFilter(v); setPage(1); }} onClearFilter={() => { setStatusFilter([]); setPage(1); }} statusOptions={[["Active", "Active"], ["Inactive", "Inactive"], ["Expired", "Expired"]]} />
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500">Enabled</th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500">Actions</th>
            </TableRow>
          </TableHeader>
          <TableBody>
            {displayPromos.map((promo) => (
              <TableRow key={promo.id} data-testid={`admin-promo-row-${promo.id}`} className="border-b border-slate-100">
                <TableCell className="font-mono font-semibold">{promo.code}</TableCell>
                {isPlatformAdmin && <TableCell className="text-xs text-slate-500" data-testid={`admin-promo-partner-${promo.id}`}>{promo.partner_code || "—"}</TableCell>}
                <TableCell>{promo.discount_type === "percent" ? `${promo.discount_value}%` : `$${promo.discount_value}`}</TableCell>
                <TableCell className="capitalize">{promo.applies_to}</TableCell>
                <TableCell>{promo.expiry_date?.slice(0, 10) || "—"}</TableCell>
                <TableCell>{promo.usage_count}{promo.max_uses ? ` / ${promo.max_uses}` : ""}</TableCell>
                <TableCell>{promo.created_at ? new Date(promo.created_at).toLocaleDateString("en-AU") : "—"}</TableCell>
                <TableCell><span className={`px-2 py-0.5 rounded ${getPromoStatus(promo) === "Active" ? "bg-green-100 text-green-700" : getPromoStatus(promo) === "Expired" ? "bg-orange-100 text-orange-700" : "bg-slate-100 text-slate-600"}`}>{getPromoStatus(promo)}</span></TableCell>
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
            {displayPromos.length === 0 && <TableRow><TableCell colSpan={9} className="text-center text-slate-400 py-6">No promo codes found.</TableCell></TableRow>}
          </TableBody>
        </Table>
      </div>
      <AdminPagination page={page} totalPages={totalPages} total={total} perPage={PER_PAGE} onPage={(p) => load(p)} />

      {/* Create Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent data-testid="admin-promo-dialog"><DialogHeader><DialogTitle>Create Promo Code</DialogTitle></DialogHeader>
          <PromoForm form={newPromo} setF={setNewPromo} products={products} />
          <Button onClick={handleCreate} disabled={saving} className="w-full mt-4" data-testid="admin-promo-submit">{saving ? "Creating…" : "Create"}</Button>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={showEditDialog} onOpenChange={(open) => { setShowEditDialog(open); if (!open) setEditPromo(null); }}>
        <DialogContent data-testid="admin-promo-edit-dialog"><DialogHeader><DialogTitle>Edit Promo Code: {editPromo?.code}</DialogTitle></DialogHeader>
          <PromoForm form={editForm} setF={setEditForm} products={products} />
          <Button onClick={handleEdit} disabled={saving} className="w-full mt-4" data-testid="admin-promo-edit-save">{saving ? "Saving…" : "Save Changes"}</Button>
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
