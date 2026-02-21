import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { AdminPageHeader } from "./shared/AdminPageHeader";
import { Plus } from "lucide-react";

const INITIAL_PROMO = {
  code: "", discount_type: "percent", discount_value: 10,
  applies_to: "both", applies_to_products: "all", product_ids: [] as string[],
  expiry_date: "", max_uses: "", one_time_code: false, enabled: true,
};

export function PromoCodesTab() {
  const [promoCodes, setPromoCodes] = useState<any[]>([]);
  const [products, setProducts] = useState<any[]>([]);
  const [codeFilter, setCodeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [newPromo, setNewPromo] = useState(INITIAL_PROMO);

  const load = async () => {
    try {
      const [promoRes, prodRes] = await Promise.all([
        api.get("/admin/promo-codes"),
        api.get("/products"),
      ]);
      setPromoCodes(promoRes.data.promo_codes || []);
      setProducts(prodRes.data.products || []);
    } catch { toast.error("Failed to load promo codes"); }
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async () => {
    try {
      await api.post("/admin/promo-codes", {
        ...newPromo,
        expiry_date: newPromo.expiry_date || null,
        max_uses: newPromo.max_uses ? parseInt(newPromo.max_uses) : null,
      });
      toast.success("Promo code created");
      setShowCreateDialog(false);
      setNewPromo(INITIAL_PROMO);
      load();
    } catch (e: any) { toast.error(e.response?.data?.detail || "Failed to create promo code"); }
  };

  const handleToggle = async (promoId: string, enabled: boolean) => {
    try {
      await api.put(`/admin/promo-codes/${promoId}`, { enabled });
      toast.success("Promo code updated");
      load();
    } catch (e: any) { toast.error(e.response?.data?.detail || "Update failed"); }
  };

  const filtered = promoCodes.filter((p) => {
    if (codeFilter && !p.code?.toLowerCase().includes(codeFilter.toLowerCase())) return false;
    if (statusFilter !== "all" && p.status !== statusFilter) return false;
    return true;
  });

  return (
    <div className="space-y-4" data-testid="promo-codes-tab">
      <AdminPageHeader
        title="Promo Codes"
        subtitle={`${promoCodes.length} codes`}
        actions={
          <Button size="sm" onClick={() => setShowCreateDialog(true)} data-testid="admin-promo-create"><Plus size={14} className="mr-1" />Create Promo Code</Button>
        }
      />

      {/* Filters */}
      <div className="rounded-xl border border-slate-200 bg-white p-3">
        <div className="flex flex-wrap gap-2 items-center">
          <Input placeholder="Filter by code…" value={codeFilter} onChange={e => setCodeFilter(e.target.value)} className="h-8 text-xs w-44" data-testid="admin-promo-code-filter" />
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="h-8 text-xs border border-slate-200 rounded px-2 bg-white" data-testid="admin-promo-status-filter">
            <option value="all">All Statuses</option>
            <option value="Active">Active</option>
            <option value="Expired">Expired</option>
            <option value="Exhausted">Exhausted</option>
          </select>
          <Button size="sm" variant="outline" onClick={() => { setCodeFilter(""); setStatusFilter("all"); }} className="h-8 text-xs">Clear</Button>
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
              <TableHead>Date Created</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Enabled</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((promo) => (
              <TableRow key={promo.id} data-testid={`admin-promo-row-${promo.id}`} className="border-b border-slate-100">
                <TableCell className="font-mono font-semibold">{promo.code}</TableCell>
                <TableCell>{promo.discount_type === "percent" ? `${promo.discount_value}%` : `$${promo.discount_value}`}</TableCell>
                <TableCell className="capitalize">{promo.applies_to}</TableCell>
                <TableCell className="text-xs">{promo.expiry_date?.slice(0, 10) || "—"}</TableCell>
                <TableCell>{promo.usage_count}{promo.max_uses ? ` / ${promo.max_uses}` : ""}</TableCell>
                <TableCell className="text-xs">{promo.created_at ? new Date(promo.created_at).toLocaleDateString("en-AU") : "—"}</TableCell>
                <TableCell>
                  <span className={`text-xs px-2 py-1 rounded ${promo.status === "Active" ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-600"}`}>{promo.status}</span>
                </TableCell>
                <TableCell>
                  <button onClick={() => handleToggle(promo.id, !promo.enabled)} className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${promo.enabled ? "bg-slate-900" : "bg-slate-200"}`} data-testid={`admin-promo-toggle-${promo.id}`}>
                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${promo.enabled ? "translate-x-4" : "translate-x-0.5"}`} />
                  </button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Create Promo Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent data-testid="admin-promo-dialog">
          <DialogHeader><DialogTitle>Create Promo Code</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-xs text-slate-500">Code</label>
              <Input placeholder="SUMMER20" value={newPromo.code} onChange={e => setNewPromo({ ...newPromo, code: e.target.value.toUpperCase() })} data-testid="admin-promo-code-input" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Discount Type</label>
                <select value={newPromo.discount_type} onChange={e => setNewPromo({ ...newPromo, discount_type: e.target.value })} className="w-full h-9 text-sm border border-slate-200 rounded px-2" data-testid="admin-promo-type-select">
                  <option value="percent">Percent (%)</option>
                  <option value="fixed">Fixed ($)</option>
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Value</label>
                <Input type="number" value={newPromo.discount_value} onChange={e => setNewPromo({ ...newPromo, discount_value: parseFloat(e.target.value) })} data-testid="admin-promo-value-input" />
              </div>
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-500">Applies To</label>
              <select value={newPromo.applies_to} onChange={e => setNewPromo({ ...newPromo, applies_to: e.target.value })} className="w-full h-9 text-sm border border-slate-200 rounded px-2" data-testid="admin-promo-applies-select">
                <option value="both">Both</option>
                <option value="one-time">One-time only</option>
                <option value="subscription">Subscription only</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-500">Product Eligibility</label>
              <select value={newPromo.applies_to_products} onChange={e => setNewPromo({ ...newPromo, applies_to_products: e.target.value, product_ids: e.target.value === "all" ? [] : newPromo.product_ids })} className="w-full h-9 text-sm border border-slate-200 rounded px-2">
                <option value="all">All Products</option>
                <option value="selected">Selected Products Only</option>
              </select>
            </div>
            {newPromo.applies_to_products === "selected" && (
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Select Products</label>
                <div className="max-h-40 overflow-y-auto border border-slate-200 rounded p-2 space-y-1">
                  {products.map((p: any) => (
                    <div key={p.id} className="flex items-center gap-2">
                      <input type="checkbox" checked={newPromo.product_ids.includes(p.id)}
                        onChange={e => setNewPromo({ ...newPromo, product_ids: e.target.checked ? [...newPromo.product_ids, p.id] : newPromo.product_ids.filter(id => id !== p.id) })} />
                      <label className="text-xs">{p.name}</label>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Expiry Date (optional)</label>
                <Input type="date" value={newPromo.expiry_date} onChange={e => setNewPromo({ ...newPromo, expiry_date: e.target.value })} data-testid="admin-promo-expiry-input" />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Max Uses (optional)</label>
                <Input type="number" value={newPromo.max_uses} onChange={e => setNewPromo({ ...newPromo, max_uses: e.target.value })} data-testid="admin-promo-maxuses-input" />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <input type="checkbox" checked={newPromo.one_time_code} onChange={e => setNewPromo({ ...newPromo, one_time_code: e.target.checked })} data-testid="admin-promo-onetime-check" />
              <label className="text-sm">One-time per customer</label>
            </div>
            <Button onClick={handleCreate} className="w-full" data-testid="admin-promo-submit">Create</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
