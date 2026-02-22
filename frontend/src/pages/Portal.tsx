import { useEffect, useMemo, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/contexts/AuthContext";
import api from "@/lib/api";
import { Search, ChevronLeft, ChevronRight, Package, RefreshCw } from "lucide-react";

const ORDERS_PER_PAGE = 8;
const SUBS_PER_PAGE = 5;

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    paid: "bg-green-100 text-green-700",
    active: "bg-green-100 text-green-700",
    completed: "bg-blue-100 text-blue-700",
    unpaid: "bg-red-100 text-red-700",
    pending: "bg-amber-100 text-amber-700",
    pending_payment: "bg-amber-100 text-amber-700",
    awaiting_bank_transfer: "bg-amber-100 text-amber-700",
    canceled_pending: "bg-orange-100 text-orange-700",
    cancelled: "bg-slate-100 text-slate-500",
    paused: "bg-slate-100 text-slate-500",
    pending_direct_debit_setup: "bg-blue-100 text-blue-600",
  };
  const label: Record<string, string> = {
    paid: "Paid",
    active: "Active",
    completed: "Completed",
    unpaid: "Unpaid",
    pending: "Pending",
    pending_payment: "Pending Payment",
    awaiting_bank_transfer: "Awaiting Bank Transfer",
    canceled_pending: "Cancellation Pending",
    cancelled: "Cancelled",
    paused: "Paused",
    pending_direct_debit_setup: "Setting Up Direct Debit",
  };
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${map[status] || "bg-slate-100 text-slate-500"}`}>
      {label[status] || status}
    </span>
  );
}

function Paginator({ page, total, perPage, onChange }: { page: number; total: number; perPage: number; onChange: (p: number) => void }) {
  const totalPages = Math.max(1, Math.ceil(total / perPage));
  if (totalPages <= 1) return null;
  return (
    <div className="flex items-center justify-between pt-3 border-t border-slate-100">
      <span className="text-xs text-slate-400">{(page - 1) * perPage + 1}–{Math.min(page * perPage, total)} of {total}</span>
      <div className="flex items-center gap-1">
        <Button variant="ghost" size="sm" className="h-7 w-7 p-0" disabled={page <= 1} onClick={() => onChange(page - 1)}>
          <ChevronLeft size={14} />
        </Button>
        {Array.from({ length: totalPages }, (_, i) => i + 1).map(p => (
          <Button key={p} variant={p === page ? "default" : "ghost"} size="sm" className="h-7 w-7 p-0 text-xs" onClick={() => onChange(p)}>
            {p}
          </Button>
        ))}
        <Button variant="ghost" size="sm" className="h-7 w-7 p-0" disabled={page >= totalPages} onClick={() => onChange(page + 1)}>
          <ChevronRight size={14} />
        </Button>
      </div>
    </div>
  );
}

export default function Portal() {
  const { user } = useAuth();
  const [orders, setOrders] = useState<any[]>([]);
  const [items, setItems] = useState<any[]>([]);
  const [subscriptions, setSubscriptions] = useState<any[]>([]);
  const [productMap, setProductMap] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);

  // Orders filters + pagination
  const [orderSearch, setOrderSearch] = useState("");
  const [orderStatusFilter, setOrderStatusFilter] = useState("");
  const [orderSort, setOrderSort] = useState<"desc" | "asc">("desc");
  const [orderPage, setOrderPage] = useState(1);

  // Subscriptions filters + pagination
  const [subSearch, setSubSearch] = useState("");
  const [subStatusFilter, setSubStatusFilter] = useState("");
  const [subSort, setSubSort] = useState<"desc" | "asc">("desc");
  const [subPage, setSubPage] = useState(1);

  const load = async () => {
    setLoading(true);
    try {
      const [ordersRes, subsRes, productsRes] = await Promise.all([
        api.get("/orders"),
        api.get("/subscriptions"),
        api.get("/products"),
      ]);
      setOrders(ordersRes.data.orders || []);
      setItems(ordersRes.data.items || []);
      setSubscriptions(subsRes.data.subscriptions || []);
      const map: Record<string, any> = {};
      (productsRes.data.products || []).forEach((p: any) => { map[p.id] = p; });
      setProductMap(map);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const orderItems = (orderId: string) => items.filter((i) => i.order_id === orderId);

  // ── Orders ──────────────────────────────────────────────
  const oneTimeOrders = useMemo(() => orders.filter((o) => o.type !== "subscription_start"), [orders]);

  const filteredOrders = useMemo(() => {
    let list = orders.filter((o) => o.type !== "subscription_start");
    const q = orderSearch.toLowerCase();
    if (q) {
      list = list.filter(o => {
        const prods = items.filter(i => i.order_id === o.id).map(i => productMap[i.product_id]?.name || "").join(" ").toLowerCase();
        return o.order_number?.toLowerCase().includes(q) || prods.includes(q);
      });
    }
    if (orderStatusFilter) list = list.filter(o => o.status === orderStatusFilter);
    list = [...list].sort((a, b) => {
      const da = a.created_at || "", db = b.created_at || "";
      return orderSort === "desc" ? db.localeCompare(da) : da.localeCompare(db);
    });
    return list;
  }, [orders, items, orderSearch, orderStatusFilter, orderSort, productMap]);

  const orderUniqueStatuses = useMemo(() => Array.from(new Set(oneTimeOrders.map(o => o.status).filter(Boolean))), [oneTimeOrders]);
  const paginatedOrders = filteredOrders.slice((orderPage - 1) * ORDERS_PER_PAGE, orderPage * ORDERS_PER_PAGE);

  // ── Subscriptions ────────────────────────────────────────
  const filteredSubs = useMemo(() => {
    let list = subscriptions;
    const q = subSearch.toLowerCase();
    if (q) list = list.filter(s => s.plan_name?.toLowerCase().includes(q) || s.subscription_number?.toLowerCase().includes(q));
    if (subStatusFilter) list = list.filter(s => s.status === subStatusFilter);
    return list;
  }, [subscriptions, subSearch, subStatusFilter]);

  const subUniqueStatuses = useMemo(() => Array.from(new Set(subscriptions.map(s => s.status).filter(Boolean))), [subscriptions]);
  const paginatedSubs = filteredSubs.slice((subPage - 1) * SUBS_PER_PAGE, subPage * SUBS_PER_PAGE);

  // Reset pages on filter change
  useEffect(() => { setOrderPage(1); }, [orderSearch, orderStatusFilter]);
  useEffect(() => { setSubPage(1); }, [subSearch, subStatusFilter]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-slate-400" data-testid="portal-loading">
        <RefreshCw size={18} className="animate-spin mr-2" /> Loading your account…
      </div>
    );
  }

  return (
    <div className="space-y-10 max-w-6xl mx-auto" data-testid="portal-page">
      {/* Header */}
      <div>
        <p className="text-sm text-slate-500" data-testid="portal-welcome">Welcome, {user?.full_name || "Customer"}</p>
        <h1 className="text-2xl font-semibold text-slate-900">Customer portal</h1>
        <p className="text-sm text-slate-400">Track your orders and subscriptions in one place.</p>
      </div>

      {/* ── One-time orders ──────────────────────────────── */}
      <section className="space-y-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
            <Package size={16} className="text-slate-400" /> One-time orders
            <span className="text-xs font-normal text-slate-400 bg-slate-100 px-2 py-0.5 rounded-full">{filteredOrders.length}</span>
          </h2>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <Input
                placeholder="Search order # or product…"
                value={orderSearch}
                onChange={e => setOrderSearch(e.target.value)}
                className="h-8 pl-7 text-xs w-52"
                data-testid="portal-orders-search"
              />
            </div>
            <select
              value={orderStatusFilter}
              onChange={e => setOrderStatusFilter(e.target.value)}
              className="h-8 text-xs border border-slate-200 rounded px-2 bg-white"
              data-testid="portal-orders-status-filter"
            >
              <option value="">All statuses</option>
              {orderUniqueStatuses.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        </div>

        {paginatedOrders.length === 0 ? (
          <div className="rounded-xl border border-slate-100 bg-slate-50 py-10 text-center text-sm text-slate-400" data-testid="portal-orders-empty">
            {orderSearch || orderStatusFilter ? "No orders match your search." : "No one-time orders found."}
          </div>
        ) : (
          <>
            <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
              <Table data-testid="portal-orders-table">
                <TableHeader>
                  <TableRow className="bg-slate-50">
                    <TableHead className="text-xs">Order</TableHead>
                    <TableHead className="text-xs">Date</TableHead>
                    <TableHead className="text-xs">Products</TableHead>
                    <TableHead className="text-xs">Subtotal</TableHead>
                    <TableHead className="text-xs">Fee</TableHead>
                    <TableHead className="text-xs">Total</TableHead>
                    <TableHead className="text-xs">Payment</TableHead>
                    <TableHead className="text-xs">Status</TableHead>
                    <TableHead className="text-xs"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {paginatedOrders.map((order) => (
                    <TableRow key={order.id} data-testid={`portal-order-row-${order.id}`} className="hover:bg-slate-50/50">
                      <TableCell className="font-mono text-xs font-medium" data-testid={`portal-order-number-${order.id}`}>{order.order_number}</TableCell>
                      <TableCell className="text-xs text-slate-500" data-testid={`portal-order-date-${order.id}`}>{order.created_at?.slice(0, 10)}</TableCell>
                      <TableCell className="text-xs max-w-[180px] truncate" data-testid={`portal-order-products-${order.id}`}>
                        {orderItems(order.id).map(i => productMap[i.product_id]?.name || i.product_id).join(", ") || "—"}
                      </TableCell>
                      <TableCell className="text-xs" data-testid={`portal-order-subtotal-${order.id}`}>${(order.subtotal || 0).toFixed(2)}</TableCell>
                      <TableCell className="text-xs text-slate-400" data-testid={`portal-order-fee-${order.id}`}>${(order.fee || 0).toFixed(2)}</TableCell>
                      <TableCell className="text-xs font-semibold" data-testid={`portal-order-total-${order.id}`}>${(order.total || 0).toFixed(2)}</TableCell>
                      <TableCell className="text-xs" data-testid={`portal-order-payment-${order.id}`}>
                        {order.payment_method === "bank_transfer" ? "Bank Transfer" : order.payment_method === "card" ? "Card" : order.payment_method || "—"}
                      </TableCell>
                      <TableCell data-testid={`portal-order-status-${order.id}`}>
                        <StatusBadge status={order.status} />
                      </TableCell>
                      <TableCell>
                        <Dialog>
                          <DialogTrigger asChild>
                            <Button variant="ghost" size="sm" className="h-7 text-xs" data-testid={`order-view-${order.id}`}>View</Button>
                          </DialogTrigger>
                          <DialogContent>
                            <DialogHeader>
                              <DialogTitle>Order {order.order_number}</DialogTitle>
                            </DialogHeader>
                            <div className="space-y-2 text-sm" data-testid={`order-details-${order.id}`}>
                              <div className="flex justify-between text-xs text-slate-400 pb-2 border-b">
                                <span>Date: {order.created_at?.slice(0, 10)}</span>
                                <StatusBadge status={order.status} />
                              </div>
                              {orderItems(order.id).map(item => (
                                <div key={item.id} className="flex justify-between text-sm" data-testid={`order-item-${item.id}`}>
                                  <span>{productMap[item.product_id]?.name || item.product_id}</span>
                                  <span className="font-medium">${(item.line_total || 0).toFixed(2)}</span>
                                </div>
                              ))}
                              <div className="flex justify-between pt-2 border-t font-semibold">
                                <span>Total</span>
                                <span>${(order.total || 0).toFixed(2)}</span>
                              </div>
                            </div>
                          </DialogContent>
                        </Dialog>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            <Paginator page={orderPage} total={filteredOrders.length} perPage={ORDERS_PER_PAGE} onChange={setOrderPage} />
          </>
        )}
      </section>

      {/* ── Subscriptions ────────────────────────────────── */}
      <section className="space-y-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
            <RefreshCw size={16} className="text-slate-400" /> Subscriptions
            <span className="text-xs font-normal text-slate-400 bg-slate-100 px-2 py-0.5 rounded-full">{filteredSubs.length}</span>
          </h2>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <Input
                placeholder="Search plan or sub #…"
                value={subSearch}
                onChange={e => setSubSearch(e.target.value)}
                className="h-8 pl-7 text-xs w-48"
                data-testid="portal-subs-search"
              />
            </div>
            <select
              value={subStatusFilter}
              onChange={e => setSubStatusFilter(e.target.value)}
              className="h-8 text-xs border border-slate-200 rounded px-2 bg-white"
              data-testid="portal-subs-status-filter"
            >
              <option value="">All statuses</option>
              {subUniqueStatuses.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        </div>

        {paginatedSubs.length === 0 ? (
          <div className="rounded-xl border border-slate-100 bg-slate-50 py-10 text-center text-sm text-slate-400" data-testid="portal-subs-empty">
            {subSearch || subStatusFilter ? "No subscriptions match your search." : "No active subscriptions."}
          </div>
        ) : (
          <>
            <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
              <Table data-testid="portal-subscriptions-table">
                <TableHeader>
                  <TableRow className="bg-slate-50">
                    <TableHead className="text-xs">Sub #</TableHead>
                    <TableHead className="text-xs">Plan</TableHead>
                    <TableHead className="text-xs">Start Date</TableHead>
                    <TableHead className="text-xs">Renewal</TableHead>
                    <TableHead className="text-xs">Status</TableHead>
                    <TableHead className="text-xs">Amount</TableHead>
                    <TableHead className="text-xs">Cancellation</TableHead>
                    <TableHead className="text-xs">Manage</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {paginatedSubs.map((sub) => {
                    const startDate = sub.start_date?.slice(0, 10) || sub.current_period_start?.slice(0, 10) || "—";
                    const cancelDate = sub.cancel_at_period_end
                      ? (sub.current_period_end?.slice(0, 10) || sub.canceled_at?.slice(0, 10) || "—")
                      : (sub.canceled_at?.slice(0, 10) || "—");
                    const contractEnd = sub.contract_end_date ? new Date(sub.contract_end_date) : null;
                    const contractExpired = !contractEnd || contractEnd < new Date();
                    return (
                      <TableRow key={sub.id} data-testid={`portal-subscription-row-${sub.id}`} className="hover:bg-slate-50/50">
                        <TableCell className="font-mono text-xs font-medium" data-testid={`portal-subscription-id-${sub.id}`}>{sub.subscription_number || sub.id?.slice(0, 8)}</TableCell>
                        <TableCell className="text-sm" data-testid={`portal-subscription-plan-${sub.id}`}>{sub.plan_name}</TableCell>
                        <TableCell className="text-xs text-slate-500" data-testid={`portal-subscription-start-${sub.id}`}>{startDate}</TableCell>
                        <TableCell className="text-xs text-slate-500" data-testid={`portal-subscription-renewal-${sub.id}`}>{sub.renewal_date?.slice(0, 10) || sub.current_period_end?.slice(0, 10) || "—"}</TableCell>
                        <TableCell data-testid={`portal-subscription-status-${sub.id}`}>
                          <StatusBadge status={sub.status} />
                        </TableCell>
                        <TableCell className="text-xs font-semibold" data-testid={`portal-subscription-amount-${sub.id}`}>${(sub.amount || 0).toFixed(2)}</TableCell>
                        <TableCell className="text-xs text-slate-400" data-testid={`portal-subscription-cancel-date-${sub.id}`}>{cancelDate}</TableCell>
                        <TableCell>
                          {sub.status !== "cancelled" && sub.status !== "canceled_pending" && contractExpired && (
                            <Button variant="ghost" size="sm" className="h-7 text-xs text-red-500 hover:text-red-700 hover:bg-red-50"
                              onClick={() => api.post(`/subscriptions/${sub.id}/cancel`, {}).then(load)}
                              data-testid={`subscription-cancel-${sub.id}`}>
                              Cancel
                            </Button>
                          )}
                          {sub.status !== "cancelled" && sub.status !== "canceled_pending" && !contractExpired && (
                            <span className="text-xs text-slate-400" data-testid={`subscription-contract-active-${sub.id}`}>
                              Contract until {sub.contract_end_date?.slice(0, 10)}
                            </span>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
            <Paginator page={subPage} total={filteredSubs.length} perPage={SUBS_PER_PAGE} onChange={setSubPage} />
          </>
        )}
      </section>
    </div>
  );
}
