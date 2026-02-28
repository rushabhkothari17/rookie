import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { RefreshCw } from "lucide-react";

const STATUS_COLORS: Record<string, string> = {
  paid: "bg-emerald-100 text-emerald-700",
  unpaid: "bg-amber-100 text-amber-700",
  pending: "bg-blue-100 text-blue-700",
  cancelled: "bg-slate-100 text-slate-500",
  refunded: "bg-purple-100 text-purple-700",
};

const STATUSES = ["pending", "unpaid", "paid", "cancelled", "refunded"];

type PartnerOrder = {
  id: string;
  order_number: string;
  description: string;
  amount: number;
  currency: string;
  status: string;
  payment_method: string;
  invoice_date?: string;
  due_date?: string;
  paid_at?: string;
  plan_name?: string;
  payment_url?: string;
  created_at: string;
};

export function MyOrdersTab() {
  const [orders, setOrders] = useState<PartnerOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const LIMIT = 20;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), limit: String(LIMIT) });
      if (search) params.set("search", search);
      if (status && status !== "all") params.set("status", status);
      const { data } = await api.get(`/partner/my-orders?${params}`);
      setOrders(data.orders || []);
      setTotal(data.total || 0);
    } catch { toast.error("Failed to load orders"); }
    finally { setLoading(false); }
  }, [page, search, status]);

  useEffect(() => { load(); }, [load]);

  const fmtAmt = (amount: number, currency: string) =>
    new Intl.NumberFormat("en-GB", { style: "currency", currency }).format(amount);

  return (
    <div className="space-y-4" data-testid="my-orders-tab">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">My Orders</h2>
        <p className="text-sm text-slate-500">Invoices raised by the platform for your organisation.</p>
      </div>

      <div className="flex gap-2 flex-wrap">
        <Input
          placeholder="Search orders…"
          value={search}
          onChange={e => { setSearch(e.target.value); setPage(1); }}
          className="w-48"
          data-testid="my-orders-search"
        />
        <Select value={status} onValueChange={v => { setStatus(v); setPage(1); }}>
          <SelectTrigger className="w-36"><SelectValue placeholder="All statuses" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            {STATUSES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
          </SelectContent>
        </Select>
        <Button size="sm" variant="outline" onClick={load}><RefreshCw className="h-4 w-4" /></Button>
      </div>

      <div className="rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-sm" data-testid="my-orders-table">
          <thead className="bg-slate-50 text-xs text-slate-500 uppercase">
            <tr>
              <th className="text-left px-4 py-3">Order #</th>
              <th className="text-left px-4 py-3">Description</th>
              <th className="text-left px-4 py-3">Plan</th>
              <th className="text-left px-4 py-3">Amount</th>
              <th className="text-left px-4 py-3">Status</th>
              <th className="text-left px-4 py-3">Due</th>
              <th className="text-left px-4 py-3">Paid</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} className="text-center py-8 text-slate-400">Loading…</td></tr>
            ) : orders.length === 0 ? (
              <tr><td colSpan={7} className="text-center py-8 text-slate-400">No orders found.</td></tr>
            ) : orders.map(o => (
              <tr key={o.id} className="border-t border-slate-100 hover:bg-slate-50">
                <td className="px-4 py-3 font-mono text-xs text-slate-600">{o.order_number}</td>
                <td className="px-4 py-3">{o.description}</td>
                <td className="px-4 py-3 text-slate-500 text-xs">{o.plan_name || "—"}</td>
                <td className="px-4 py-3 font-semibold">{fmtAmt(o.amount, o.currency)}</td>
                <td className="px-4 py-3">
                  <Badge className={`text-[11px] ${STATUS_COLORS[o.status] || ""}`}>{o.status}</Badge>
                </td>
                <td className="px-4 py-3 text-slate-500 text-xs">{o.due_date ? new Date(o.due_date).toLocaleDateString() : "—"}</td>
                <td className="px-4 py-3 text-slate-500 text-xs">{o.paid_at ? new Date(o.paid_at).toLocaleDateString() : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {total > LIMIT && (
        <div className="flex justify-end gap-2">
          <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Prev</Button>
          <span className="text-sm text-slate-500 py-1.5">Page {page} of {Math.ceil(total / LIMIT)}</span>
          <Button size="sm" variant="outline" disabled={page >= Math.ceil(total / LIMIT)} onClick={() => setPage(p => p + 1)}>Next</Button>
        </div>
      )}
    </div>
  );
}
