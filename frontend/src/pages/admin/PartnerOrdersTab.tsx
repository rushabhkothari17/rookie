import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Plus, Pencil, Trash2, ExternalLink, ScrollText, RefreshCw, Copy, Download } from "lucide-react";

type Tenant = { id: string; name: string };
type Plan = { id: string; name: string; is_active: boolean };

type PartnerOrder = {
  id: string;
  order_number: string;
  partner_id: string;
  partner_name: string;
  plan_name?: string;
  description: string;
  amount: number;
  currency: string;
  status: string;
  payment_method: string;
  processor_id?: string;
  invoice_date?: string;
  due_date?: string;
  paid_at?: string;
  internal_note?: string;
  payment_url?: string;
  created_at: string;
};

type Stats = {
  total: number;
  this_month: number;
  by_status: Record<string, number>;
  by_method: Record<string, number>;
  revenue_paid: Record<string, number>;
};

const STATUS_COLORS: Record<string, string> = {
  paid: "bg-emerald-100 text-emerald-700",
  unpaid: "bg-amber-100 text-amber-700",
  pending: "bg-blue-100 text-blue-700",
  cancelled: "bg-slate-100 text-slate-500",
  refunded: "bg-purple-100 text-purple-700",
};

const STATUSES = ["pending", "unpaid", "paid", "cancelled", "refunded"];
const PAYMENT_METHODS = ["manual", "offline", "bank_transfer", "card"];

function downloadInvoice(orderId: string, orderNumber: string, endpoint: string) {
  const token = localStorage.getItem("aa_token") || "";
  const base = (window as any).__REACT_APP_BACKEND_URL__ || process.env.REACT_APP_BACKEND_URL || "";
  fetch(`${base}/api/${endpoint}/${orderId}/download-invoice`, {
    headers: { Authorization: `Bearer ${token}` },
  })
    .then(r => {
      if (!r.ok) throw new Error("Failed to generate invoice");
      return r.blob();
    })
    .then(blob => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `invoice-${orderNumber}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    })
    .catch(() => toast.error("Invoice generation failed"));
}

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      <p className="text-2xl font-bold text-slate-900">{value}</p>
      {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
    </div>
  );
}

type OrderFormData = {
  partner_id: string; plan_id: string; description: string; amount: string;
  currency: string; status: string; payment_method: string; processor_id: string;
  invoice_date: string; due_date: string; paid_at: string; internal_note: string;
};

const emptyForm = (): OrderFormData => ({
  partner_id: "", plan_id: "", description: "", amount: "",
  currency: "GBP", status: "unpaid", payment_method: "manual",
  processor_id: "", invoice_date: "", due_date: "", paid_at: "", internal_note: "",
});

function OrderFormModal({
  order, tenants, plans, onClose, onSaved,
}: {
  order: PartnerOrder | null;
  tenants: Tenant[];
  plans: Plan[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = !!order;
  const [form, setForm] = useState<OrderFormData>(
    order ? {
      partner_id: order.partner_id, plan_id: "", description: order.description,
      amount: String(order.amount), currency: order.currency, status: order.status,
      payment_method: order.payment_method, processor_id: order.processor_id || "",
      invoice_date: order.invoice_date || "", due_date: order.due_date || "",
      paid_at: order.paid_at || "", internal_note: order.internal_note || "",
    } : emptyForm()
  );
  const [saving, setSaving] = useState(false);
  const [generatingLink, setGeneratingLink] = useState(false);
  const [paymentUrl, setPaymentUrl] = useState(order?.payment_url || "");

  const set = (k: keyof OrderFormData, v: string) => setForm(f => ({ ...f, [k]: v }));

  const handleSave = async () => {
    if (!form.partner_id || !form.description || !form.amount) {
      toast.error("Partner, description and amount are required"); return;
    }
    setSaving(true);
    try {
      const payload: Record<string, any> = {
        ...form,
        amount: parseFloat(form.amount),
        plan_id: form.plan_id || null,
        processor_id: form.processor_id || null,
        invoice_date: form.invoice_date || null,
        due_date: form.due_date || null,
        paid_at: form.paid_at || null,
        internal_note: form.internal_note || "",
      };
      if (isEdit) {
        await api.put(`/admin/partner-orders/${order.id}`, payload);
        toast.success("Order updated");
      } else {
        await api.post("/admin/partner-orders", payload);
        toast.success("Order created");
      }
      onSaved();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleStripeCheckout = async () => {
    if (!order) return;
    setGeneratingLink(true);
    try {
      const { data } = await api.post("/admin/partner-billing/stripe-checkout", { partner_order_id: order.id });
      setPaymentUrl(data.url);
      toast.success("Payment link generated");
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to generate Stripe link");
    } finally {
      setGeneratingLink(false);
    }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? `Edit Order — ${order.order_number}` : "New Partner Order"}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 mt-2">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1 col-span-2">
              <label className="text-xs font-medium text-slate-600">Partner *</label>
              <Select value={form.partner_id} onValueChange={v => set("partner_id", v)}>
                <SelectTrigger data-testid="order-partner-select"><SelectValue placeholder="Select partner…" /></SelectTrigger>
                <SelectContent>
                  {tenants.map(t => <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Plan (optional)</label>
              <Select value={form.plan_id || "__none__"} onValueChange={v => set("plan_id", v === "__none__" ? "" : v)}>
                <SelectTrigger><SelectValue placeholder="No plan" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">— None —</SelectItem>
                  {plans.map(p => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Status</label>
              <Select value={form.status} onValueChange={v => set("status", v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{STATUSES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-600">Description *</label>
            <Input value={form.description} onChange={e => set("description", e.target.value)} placeholder="Platform access — March 2026" data-testid="order-description-input" />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1 col-span-2">
              <label className="text-xs font-medium text-slate-600">Amount *</label>
              <Input type="number" min={0} step="0.01" value={form.amount} onChange={e => set("amount", e.target.value)} data-testid="order-amount-input" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Currency</label>
              <Input value={form.currency} onChange={e => set("currency", e.target.value.toUpperCase())} maxLength={3} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Payment Method</label>
              <Select value={form.payment_method} onValueChange={v => set("payment_method", v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{PAYMENT_METHODS.map(m => <SelectItem key={m} value={m}>{m.replace("_", " ")}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Invoice Date</label>
              <Input type="date" value={form.invoice_date} onChange={e => set("invoice_date", e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Due Date</label>
              <Input type="date" value={form.due_date} onChange={e => set("due_date", e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Paid At</label>
              <Input type="date" value={form.paid_at ? form.paid_at.slice(0, 10) : ""} onChange={e => set("paid_at", e.target.value)} />
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-600">Processor ID (Stripe/GC reference)</label>
            <Input value={form.processor_id} onChange={e => set("processor_id", e.target.value)} placeholder="pi_xxx or PM-xxx" />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-600">Internal Note</label>
            <Textarea rows={2} value={form.internal_note} onChange={e => set("internal_note", e.target.value)} />
          </div>

          {/* Stripe checkout link (edit mode, card payment only) */}
          {isEdit && form.payment_method === "card" && (
            <div className="rounded-lg bg-blue-50 border border-blue-200 p-3 space-y-2">
              <p className="text-xs font-medium text-blue-700">Stripe Hosted Checkout</p>
              {paymentUrl ? (
                <div className="flex gap-2">
                  <Input readOnly value={paymentUrl} className="text-xs h-7" />
                  <Button size="sm" variant="outline" onClick={() => { navigator.clipboard.writeText(paymentUrl); toast.success("Copied!"); }}>
                    <Copy className="h-3.5 w-3.5" />
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => window.open(paymentUrl, "_blank")}>
                    <ExternalLink className="h-3.5 w-3.5" />
                  </Button>
                </div>
              ) : (
                <Button size="sm" onClick={handleStripeCheckout} disabled={generatingLink} data-testid="generate-stripe-link-btn">
                  {generatingLink ? "Generating…" : "Generate Payment Link"}
                </Button>
              )}
            </div>
          )}
        </div>
        <DialogFooter className="mt-4">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSave} disabled={saving} data-testid="save-partner-order-btn">
            {saving ? "Saving…" : isEdit ? "Save Changes" : "Create Order"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function PartnerOrdersTab() {
  const [orders, setOrders] = useState<PartnerOrder[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({ search: "", partner_id: "", status: "", payment_method: "", plan_id: "" });
  const [showCreate, setShowCreate] = useState(false);
  const [editOrder, setEditOrder] = useState<PartnerOrder | null>(null);
  const [deleteOrder, setDeleteOrder] = useState<PartnerOrder | null>(null);
  const LIMIT = 20;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), limit: String(LIMIT) });
      if (filters.search) params.set("search", filters.search);
      if (filters.partner_id) params.set("partner_id", filters.partner_id);
      if (filters.status && filters.status !== "all") params.set("status", filters.status);
      if (filters.payment_method && filters.payment_method !== "all") params.set("payment_method", filters.payment_method);
      if (filters.plan_id && filters.plan_id !== "all") params.set("plan_id", filters.plan_id);
      const [ordersRes, statsRes] = await Promise.all([
        api.get(`/admin/partner-orders?${params}`),
        api.get("/admin/partner-orders/stats"),
      ]);
      setOrders(ordersRes.data.orders || []);
      setTotal(ordersRes.data.total || 0);
      setStats(statsRes.data);
    } catch { toast.error("Failed to load orders"); }
    finally { setLoading(false); }
  }, [page, filters]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    Promise.all([
      api.get("/admin/tenants"),
      api.get("/admin/plans"),
    ]).then(([t, p]) => {
      setTenants((t.data.tenants || []).filter((x: any) => x.code !== "automate-accounts"));
      setPlans((p.data.plans || []).filter((x: Plan) => x.is_active));
    }).catch(() => {});
  }, []);

  const handleDelete = async () => {
    if (!deleteOrder) return;
    try {
      await api.delete(`/admin/partner-orders/${deleteOrder.id}`);
      toast.success("Order deleted");
      setDeleteOrder(null);
      load();
    } catch (e: any) { toast.error(e.response?.data?.detail || "Delete failed"); }
  };

  const fmtDate = (d?: string) => d ? new Date(d).toLocaleDateString() : "—";
  const fmtAmt = (amount: number, currency: string) =>
    new Intl.NumberFormat("en-GB", { style: "currency", currency }).format(amount);

  return (
    <div className="space-y-5" data-testid="partner-orders-tab">
      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard label="Total Orders" value={stats.total} />
          <StatCard label="This Month" value={stats.this_month} />
          <StatCard label="Paid" value={stats.by_status?.paid || 0} />
          <StatCard label="Unpaid / Pending" value={(stats.by_status?.unpaid || 0) + (stats.by_status?.pending || 0)} />
        </div>
      )}
      {stats?.revenue_paid && Object.keys(stats.revenue_paid).length > 0 && (
        <div className="flex gap-3 flex-wrap">
          {Object.entries(stats.revenue_paid).map(([currency, total]) => (
            <div key={currency} className="bg-emerald-50 border border-emerald-200 rounded-lg px-4 py-2 text-sm">
              <span className="text-slate-500 text-xs">Revenue (paid)</span>
              <p className="font-bold text-emerald-700">{fmtAmt(total, currency)}</p>
            </div>
          ))}
        </div>
      )}

      {/* Filters + Create */}
      <div className="flex items-center gap-2 flex-wrap">
        <Input
          placeholder="Search orders…"
          value={filters.search}
          onChange={e => { setFilters(f => ({ ...f, search: e.target.value })); setPage(1); }}
          className="w-48"
          data-testid="orders-search"
        />
        <Select value={filters.partner_id || "all"} onValueChange={v => { setFilters(f => ({ ...f, partner_id: v === "all" ? "" : v })); setPage(1); }}>
          <SelectTrigger className="w-44"><SelectValue placeholder="All partners" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All partners</SelectItem>
            {tenants.map(t => <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={filters.status || "all"} onValueChange={v => { setFilters(f => ({ ...f, status: v === "all" ? "" : v })); setPage(1); }}>
          <SelectTrigger className="w-36"><SelectValue placeholder="All statuses" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            {STATUSES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={filters.plan_id || "all"} onValueChange={v => { setFilters(f => ({ ...f, plan_id: v === "all" ? "" : v })); setPage(1); }}>
          <SelectTrigger className="w-36"><SelectValue placeholder="All plans" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All plans</SelectItem>
            {plans.map(p => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}
          </SelectContent>
        </Select>
        <Button size="sm" variant="outline" onClick={load}><RefreshCw className="h-4 w-4" /></Button>
        <div className="ml-auto">
          <Button onClick={() => setShowCreate(true)} data-testid="create-partner-order-btn">
            <Plus className="h-4 w-4 mr-1" /> New Order
          </Button>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-sm" data-testid="partner-orders-table">
          <thead className="bg-slate-50 text-xs text-slate-500 uppercase">
            <tr>
              <th className="text-left px-4 py-3">Order #</th>
              <th className="text-left px-4 py-3">Partner</th>
              <th className="text-left px-4 py-3">Description</th>
              <th className="text-left px-4 py-3">Amount</th>
              <th className="text-left px-4 py-3">Method</th>
              <th className="text-left px-4 py-3">Status</th>
              <th className="text-left px-4 py-3">Date</th>
              <th className="text-right px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} className="text-center py-8 text-slate-400">Loading…</td></tr>
            ) : orders.length === 0 ? (
              <tr><td colSpan={8} className="text-center py-8 text-slate-400">No orders found.</td></tr>
            ) : orders.map(order => (
              <tr key={order.id} className="border-t border-slate-100 hover:bg-slate-50">
                <td className="px-4 py-3 font-mono text-xs text-slate-600">{order.order_number}</td>
                <td className="px-4 py-3 font-medium">{order.partner_name}</td>
                <td className="px-4 py-3 text-slate-600 max-w-[200px] truncate">{order.description}</td>
                <td className="px-4 py-3 font-semibold">{fmtAmt(order.amount, order.currency)}</td>
                <td className="px-4 py-3 text-slate-500 capitalize">{order.payment_method.replace("_", " ")}</td>
                <td className="px-4 py-3">
                  <Badge className={`text-[11px] ${STATUS_COLORS[order.status] || "bg-slate-100"}`}>{order.status}</Badge>
                </td>
                <td className="px-4 py-3 text-slate-500 text-xs">{fmtDate(order.invoice_date)}</td>
                <td className="px-4 py-3">
                  <div className="flex justify-end gap-1">
                    <Button size="sm" variant="ghost" onClick={() => downloadInvoice(order.id, order.order_number, "admin/partner-orders")} title="Download Invoice" data-testid={`download-invoice-${order.id}`}><Download className="h-4 w-4 text-slate-500" /></Button>
                    <Button size="sm" variant="ghost" onClick={() => setEditOrder(order)} data-testid={`edit-order-${order.id}`}><Pencil className="h-4 w-4" /></Button>
                    <Button size="sm" variant="ghost" className="text-red-400 hover:text-red-600" onClick={() => setDeleteOrder(order)}><Trash2 className="h-4 w-4" /></Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {total > LIMIT && (
        <div className="flex justify-end gap-2">
          <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Prev</Button>
          <span className="text-sm text-slate-500 py-1.5">Page {page} of {Math.ceil(total / LIMIT)}</span>
          <Button size="sm" variant="outline" disabled={page >= Math.ceil(total / LIMIT)} onClick={() => setPage(p => p + 1)}>Next</Button>
        </div>
      )}

      {showCreate && <OrderFormModal order={null} tenants={tenants} plans={plans} onClose={() => setShowCreate(false)} onSaved={() => { setShowCreate(false); load(); }} />}
      {editOrder && <OrderFormModal order={editOrder} tenants={tenants} plans={plans} onClose={() => setEditOrder(null)} onSaved={() => { setEditOrder(null); load(); }} />}

      {deleteOrder && (
        <AlertDialog open onOpenChange={() => setDeleteOrder(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete order {deleteOrder.order_number}?</AlertDialogTitle>
              <AlertDialogDescription>This will soft-delete the order. This action cannot be undone.</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction className="bg-red-600 hover:bg-red-700" onClick={handleDelete}>Delete</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}
    </div>
  );
}
