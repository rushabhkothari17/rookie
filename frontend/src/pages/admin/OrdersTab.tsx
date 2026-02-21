import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { AdminPageHeader } from "./shared/AdminPageHeader";
import { AdminPagination } from "./shared/AdminPagination";
import { Download } from "lucide-react";

const ORDER_STATUSES = ["paid", "unpaid", "completed", "pending", "pending_payment", "awaiting_bank_transfer", "cancelled", "refunded", "disputed"];

export function OrdersTab() {
  const [orders, setOrders] = useState<any[]>([]);
  const [orderItems, setOrderItems] = useState<any[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const PER_PAGE = 20;

  // For table display + edit dialog
  const [customers, setCustomers] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [products, setProducts] = useState<any[]>([]);

  // Filters
  const [emailFilter, setEmailFilter] = useState("");
  const [orderNumberFilter, setOrderNumberFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [productFilter, setProductFilter] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [includeDeleted, setIncludeDeleted] = useState(false);
  const [sortOrder, setSortOrder] = useState<"desc" | "asc">("desc");

  // Dialogs
  const [selectedOrder, setSelectedOrder] = useState<any>(null);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [orderLogs, setOrderLogs] = useState<any[]>([]);
  const [showLogsDialog, setShowLogsDialog] = useState(false);
  const [showNotesDialog, setShowNotesDialog] = useState(false);
  const [noteData, setNoteData] = useState<{ notes: any[]; notes_json: any }>({ notes: [], notes_json: null });
  const [showManualDialog, setShowManualDialog] = useState(false);
  const [manualOrder, setManualOrder] = useState({
    customer_email: "", product_id: "", quantity: 1,
    subtotal: 0, discount: 0, fee: 0, status: "paid", internal_note: "",
  });

  // Build lookup maps
  const userMap: Record<string, any> = {};
  users.forEach((u) => { userMap[u.id] = u; });
  const custMap: Record<string, any> = {};
  customers.forEach((c) => { custMap[c.id] = c; });
  const productMap: Record<string, string> = {};
  products.forEach((p) => { productMap[p.id] = p.name; });

  const getCustomerUser = (customerId: string) => {
    const c = custMap[customerId];
    return c ? userMap[c.user_id] : null;
  };

  const load = useCallback(async (p = 1) => {
    try {
      const params = new URLSearchParams({
        page: String(p), per_page: String(PER_PAGE),
        sort_by: "created_at", sort_order: sortOrder,
        include_deleted: String(includeDeleted),
      });
      if (orderNumberFilter) params.append("order_number_filter", orderNumberFilter);
      if (statusFilter) params.append("status_filter", statusFilter);
      if (productFilter) params.append("product_filter", productFilter);
      const res = await api.get(`/admin/orders?${params}`);
      let ords = res.data.orders || [];
      // Client-side email filter
      if (emailFilter) {
        const custUserMap: Record<string, string> = {};
        customers.forEach((c) => { custUserMap[c.id] = userMap[c.user_id]?.email || ""; });
        ords = ords.filter((o: any) => custUserMap[o.customer_id]?.toLowerCase().includes(emailFilter.toLowerCase()));
      }
      // Client-side date filter
      if (startDate) ords = ords.filter((o: any) => o.created_at >= startDate);
      if (endDate) ords = ords.filter((o: any) => o.created_at <= endDate + "T23:59:59");
      setOrders(ords);
      setOrderItems(res.data.items || []);
      setTotalPages(res.data.total_pages || 1);
      setTotal(res.data.total || 0);
      setPage(p);
    } catch { toast.error("Failed to load orders"); }
  }, [sortOrder, includeDeleted, orderNumberFilter, statusFilter, productFilter, emailFilter, startDate, endDate, customers, users]);

  useEffect(() => {
    Promise.all([
      api.get("/admin/customers?per_page=1000").catch(() => ({ data: { customers: [], users: [] } })),
      api.get("/products").catch(() => ({ data: { products: [] } })),
    ]).then(([custRes, prodRes]) => {
      setCustomers(custRes.data.customers || []);
      setUsers(custRes.data.users || []);
      setProducts(prodRes.data.products || []);
    });
  }, []);

  useEffect(() => { load(1); }, [sortOrder, includeDeleted, orderNumberFilter, statusFilter, productFilter]);

  // customer search for edit dialog
  const [custSearch, setCustSearch] = useState("");
  const filteredCusts = customers.filter(c => {
    const u = userMap[c.user_id];
    const q = custSearch.toLowerCase();
    return !q || u?.email?.toLowerCase().includes(q) || c.company_name?.toLowerCase().includes(q);
  }).slice(0, 10);

  const handleEdit = async () => {
    if (!selectedOrder) return;
    try {
      await api.put(`/admin/orders/${selectedOrder.id}`, {
        customer_id: selectedOrder.customer_id,
        status: selectedOrder.status,
        payment_method: selectedOrder.payment_method,
        order_date: selectedOrder.order_date_edit || undefined,
        payment_date: selectedOrder.payment_date || undefined,
        internal_note: selectedOrder.internal_note,
        new_note: selectedOrder.new_note || undefined,
      });
      toast.success("Order updated");
      setShowEditDialog(false);
      setSelectedOrder(null);
      load(page);
    } catch (e: any) { toast.error(e.response?.data?.detail || "Failed to update order"); }
  };

  const handleDelete = async (orderId: string) => {
    if (!confirm("Are you sure you want to delete this order?")) return;
    try {
      await api.delete(`/admin/orders/${orderId}`, { data: { reason: "Deleted by admin" } });
      toast.success("Order deleted");
      load(page);
    } catch (e: any) { toast.error(e.response?.data?.detail || "Failed to delete order"); }
  };

  const handleAutoCharge = async (orderId: string) => {
    try {
      const res = await api.post(`/admin/orders/${orderId}/auto-charge`);
      if (res.data.success) toast.success(res.data.message); else toast.error(res.data.message);
      load(page);
    } catch (e: any) { toast.error(e.response?.data?.detail || "Auto-charge failed"); }
  };

  const handleCreateManual = async () => {
    try {
      await api.post("/admin/orders/manual", manualOrder);
      toast.success("Manual order created");
      setShowManualDialog(false);
      setManualOrder({ customer_email: "", product_id: "", quantity: 1, subtotal: 0, discount: 0, fee: 0, status: "paid", internal_note: "" });
      load(1);
    } catch (e: any) { toast.error(e.response?.data?.detail || "Failed to create order"); }
  };

  const clearFilters = () => {
    setEmailFilter(""); setOrderNumberFilter(""); setStatusFilter(""); setProductFilter("");
    setStartDate(""); setEndDate(""); setIncludeDeleted(false);
  };

  const downloadCsv = () => {
    const token = localStorage.getItem("aa_token");
    const baseUrl = process.env.REACT_APP_BACKEND_URL || "";
    const params = new URLSearchParams({ sort_order: sortOrder, include_deleted: String(includeDeleted) });
    if (orderNumberFilter) params.append("order_number_filter", orderNumberFilter);
    if (statusFilter) params.append("status_filter", statusFilter);
    if (productFilter) params.append("product_filter", productFilter);
    fetch(`${baseUrl}/api/admin/export/orders?${params}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.blob()).then(b => { const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = `orders-${new Date().toISOString().slice(0, 10)}.csv`; a.click(); })
      .catch(() => toast.error("Export failed"));
  };

  const statusColor = (s: string) => {
    if (s === "paid" || s === "completed") return "bg-green-100 text-green-700";
    if (s === "unpaid") return "bg-red-100 text-red-700";
    if (s === "awaiting_bank_transfer") return "bg-amber-100 text-amber-700";
    if (s === "cancelled" || s === "refunded") return "bg-slate-100 text-slate-500";
    return "bg-slate-100 text-slate-600";
  };

  return (
    <div className="space-y-4" data-testid="orders-tab">
      <AdminPageHeader
        title="Orders"
        subtitle={`${total} records`}
        actions={
          <>
            <Button size="sm" variant="outline" onClick={downloadCsv} data-testid="admin-orders-export-csv"><Download size={14} className="mr-1" />Export CSV</Button>
            <Button size="sm" onClick={() => setShowManualDialog(true)} data-testid="admin-create-order-btn">Create Manual Order</Button>
          </>
        }
      />

      {/* Filters */}
      <div className="rounded-xl border border-slate-200 bg-white p-3">
        <div className="flex flex-wrap gap-2 items-end">
          <Input placeholder="Customer email" value={emailFilter} onChange={e => setEmailFilter(e.target.value)} className="h-8 text-xs w-44" data-testid="admin-orders-email-filter" />
          <Input placeholder="Order # (AA-...)" value={orderNumberFilter} onChange={e => setOrderNumberFilter(e.target.value)} className="h-8 text-xs w-32" data-testid="admin-orders-number-filter" />
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="h-8 text-xs border border-slate-200 rounded px-2 bg-white" data-testid="admin-orders-status-filter">
            <option value="">All Statuses</option>
            {ORDER_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <Input placeholder="Product name" value={productFilter} onChange={e => setProductFilter(e.target.value)} className="h-8 text-xs w-36" data-testid="admin-orders-product-filter" />
          <div className="flex items-center gap-1">
            <span className="text-xs text-slate-400">From</span>
            <Input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} className="h-8 text-xs w-32" data-testid="admin-orders-start-date" />
            <span className="text-xs text-slate-400">–</span>
            <Input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} className="h-8 text-xs w-32" data-testid="admin-orders-end-date" />
          </div>
          <label className="flex items-center gap-1 text-xs text-slate-600 cursor-pointer">
            <input type="checkbox" checked={includeDeleted} onChange={e => setIncludeDeleted(e.target.checked)} />
            Show deleted
          </label>
          <Button size="sm" variant="outline" onClick={clearFilters} className="h-8 text-xs" data-testid="admin-orders-clear-filters">Clear</Button>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
        <Table data-testid="admin-orders-table" className="text-xs min-w-[1100px]">
          <TableHeader>
            <TableRow className="bg-slate-50">
              <TableHead className="cursor-pointer select-none whitespace-nowrap" onClick={() => setSortOrder(o => o === "desc" ? "asc" : "desc")}>
                Date {sortOrder === "desc" ? "↓" : "↑"}
              </TableHead>
              <TableHead>Order #</TableHead>
              <TableHead>Customer</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Product(s)</TableHead>
              <TableHead>Sub #</TableHead>
              <TableHead>Subtotal</TableHead>
              <TableHead>Fee</TableHead>
              <TableHead>Total</TableHead>
              <TableHead>Pay Date</TableHead>
              <TableHead>Method</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {orders.map((order) => {
              const user = getCustomerUser(order.customer_id);
              const items = orderItems.filter(i => i.order_id === order.id);
              const productNames = items.map(i => productMap[i.product_id] || i.product_id).join(", ") || "—";
              return (
                <TableRow key={order.id} data-testid={`admin-order-row-${order.id}`}>
                  <TableCell className="whitespace-nowrap">{order.created_at?.slice(0, 10)}</TableCell>
                  <TableCell className="font-mono">{order.order_number}</TableCell>
                  <TableCell className="max-w-[144px] truncate">{user?.full_name || "—"}</TableCell>
                  <TableCell className="max-w-[160px] truncate">{user?.email || "—"}</TableCell>
                  <TableCell className="max-w-[160px] truncate">{productNames}</TableCell>
                  <TableCell className="font-mono">{order.subscription_number || order.subscription_id?.slice(0, 8) || "—"}</TableCell>
                  <TableCell>${order.subtotal?.toFixed(2)}</TableCell>
                  <TableCell>
                    <span className="px-1.5 py-0.5 rounded text-[10px] bg-amber-100 text-amber-700">
                      fee: {order.fee > 0 ? `$${order.fee.toFixed(2)}` : "—"}
                    </span>
                  </TableCell>
                  <TableCell className="font-semibold">${order.total?.toFixed(2)}</TableCell>
                  <TableCell className="whitespace-nowrap">{order.payment_date?.slice(0, 10) || "—"}</TableCell>
                  <TableCell>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] ${order.payment_method === "bank_transfer" ? "bg-blue-100 text-blue-700" : order.payment_method === "offline" ? "bg-gray-100 text-gray-700" : "bg-green-100 text-green-700"}`}>
                      {order.payment_method === "bank_transfer" ? "Bank" : order.payment_method === "offline" ? "Manual" : "Card"}
                    </span>
                  </TableCell>
                  <TableCell>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] ${statusColor(order.status)}`}>{order.status}</span>
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1 flex-nowrap items-center">
                      <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px]" onClick={async () => { const r = await api.get(`/admin/orders/${order.id}/logs`); setOrderLogs(r.data.logs || []); setShowLogsDialog(true); }} data-testid={`admin-order-logs-${order.id}`}>Logs</Button>
                      <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px]" onClick={() => { setNoteData({ notes: order.notes || [], notes_json: order.notes_json || null }); setShowNotesDialog(true); }} data-testid={`admin-order-notes-${order.id}`}>Notes{order.notes?.length ? ` (${order.notes.length})` : ""}</Button>
                      <Button variant="outline" size="sm" className="h-6 px-2 text-[11px]" onClick={() => { setSelectedOrder({ ...order, order_date_edit: order.created_at?.slice(0, 10) }); setShowEditDialog(true); }} data-testid={`admin-order-edit-${order.id}`}>Edit</Button>
                      {order.status === "unpaid" && (
                        <Button size="sm" variant="secondary" className="h-6 px-2 text-[11px]" onClick={() => handleAutoCharge(order.id)} data-testid={`admin-order-charge-${order.id}`}>Charge</Button>
                      )}
                      <Button size="sm" variant="destructive" className="h-6 px-2 text-[11px]" onClick={() => handleDelete(order.id)} data-testid={`admin-order-delete-${order.id}`}>Delete</Button>
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
      <AdminPagination page={page} totalPages={totalPages} total={total} perPage={PER_PAGE} onPage={(p) => load(p)} />

      {/* Edit Order Dialog */}
      <Dialog open={showEditDialog} onOpenChange={(open) => { setShowEditDialog(open); if (!open) setSelectedOrder(null); }}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="admin-order-edit-dialog">
          <DialogHeader><DialogTitle>Edit Order {selectedOrder?.order_number}</DialogTitle></DialogHeader>
          {selectedOrder && (
            <div className="space-y-3">
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Customer</label>
                <select value={selectedOrder.customer_id || ""} onChange={e => setSelectedOrder({ ...selectedOrder, customer_id: e.target.value })} className="w-full h-9 text-sm border border-slate-200 rounded px-2 bg-white" data-testid="admin-order-customer-select">
                  <option value="">Select customer</option>
                  {customers.map((c: any) => {
                    const u = userMap[c.user_id];
                    return <option key={c.id} value={c.id}>{u?.full_name || c.id} ({u?.email})</option>;
                  })}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs text-slate-500">Order Date</label>
                  <Input type="date" value={selectedOrder.order_date_edit || ""} onChange={e => setSelectedOrder({ ...selectedOrder, order_date_edit: e.target.value })} data-testid="admin-order-date-input" />
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-slate-500">Payment Date</label>
                  <Input type="date" value={selectedOrder.payment_date?.slice(0, 10) || ""} onChange={e => setSelectedOrder({ ...selectedOrder, payment_date: e.target.value })} data-testid="admin-order-payment-date" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs text-slate-500">Status</label>
                  <select value={selectedOrder.status || ""} onChange={e => setSelectedOrder({ ...selectedOrder, status: e.target.value })} className="w-full h-9 text-sm border border-slate-200 rounded px-2" data-testid="admin-order-status-select">
                    {ORDER_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-slate-500">Payment Method</label>
                  <select value={selectedOrder.payment_method || ""} onChange={e => setSelectedOrder({ ...selectedOrder, payment_method: e.target.value })} className="w-full h-9 text-sm border border-slate-200 rounded px-2" data-testid="admin-order-payment-select">
                    <option value="card">Card</option>
                    <option value="bank_transfer">Bank Transfer</option>
                    <option value="offline">Offline / Manual</option>
                    <option value="gocardless">GoCardless</option>
                  </select>
                </div>
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Add Note</label>
                <Textarea placeholder="Add a note..." value={selectedOrder.new_note || ""} onChange={e => setSelectedOrder({ ...selectedOrder, new_note: e.target.value })} rows={2} data-testid="admin-order-note-input" />
              </div>
              <Button onClick={handleEdit} className="w-full" data-testid="admin-order-save">Save Changes</Button>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Notes Dialog */}
      <Dialog open={showNotesDialog} onOpenChange={setShowNotesDialog}>
        <DialogContent className="max-w-2xl"><DialogHeader><DialogTitle>Order Notes</DialogTitle></DialogHeader>
          <div className="max-h-[70vh] overflow-y-auto space-y-4">
            {noteData.notes_json && (
              <div><p className="text-xs font-semibold text-slate-700 uppercase tracking-wide">Intake Data (JSON)</p>
                <pre className="text-xs bg-slate-50 border border-slate-200 rounded p-3 overflow-x-auto whitespace-pre-wrap">{JSON.stringify(noteData.notes_json, null, 2)}</pre>
              </div>
            )}
            {noteData.notes.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-semibold text-slate-700 uppercase tracking-wide">Admin Notes</p>
                {noteData.notes.map((note: any, i: number) => (
                  <div key={i} className="border border-slate-200 rounded p-3">
                    <div className="flex justify-between items-start mb-1">
                      <span className="text-xs text-slate-500 font-medium">{note.actor}</span>
                      <span className="text-xs text-slate-400">{new Date(note.timestamp).toLocaleString()}</span>
                    </div>
                    <p className="text-sm text-slate-800">{note.text}</p>
                  </div>
                ))}
              </div>
            )}
            {!noteData.notes_json && noteData.notes.length === 0 && <p className="text-sm text-slate-500 text-center py-4">No notes yet.</p>}
          </div>
        </DialogContent>
      </Dialog>

      {/* Logs Dialog */}
      <Dialog open={showLogsDialog} onOpenChange={setShowLogsDialog}>
        <DialogContent className="max-w-2xl"><DialogHeader><DialogTitle>Order Audit Logs</DialogTitle></DialogHeader>
          <div className="max-h-[60vh] overflow-y-auto space-y-2">
            {orderLogs.length === 0 && <p className="text-sm text-slate-500 text-center py-4">No logs found</p>}
            {orderLogs.map((log: any) => (
              <div key={log.id} className="border border-slate-200 rounded p-3">
                <div className="flex justify-between items-start mb-2">
                  <span className="text-sm font-semibold text-slate-900">{log.action}</span>
                  <span className="text-xs text-slate-500">{new Date(log.created_at).toLocaleString()}</span>
                </div>
                <div className="text-xs text-slate-600">Actor: {log.actor}</div>
                {log.details && Object.keys(log.details).length > 0 && (
                  <pre className="text-xs text-slate-500 mt-2 bg-slate-50 p-2 rounded overflow-x-auto">{JSON.stringify(log.details, null, 2)}</pre>
                )}
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>

      {/* Manual Create Dialog */}
      <Dialog open={showManualDialog} onOpenChange={setShowManualDialog}>
        <DialogContent><DialogHeader><DialogTitle>Create Manual Order</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-xs text-slate-500">Customer Email</label>
              <Input placeholder="customer@example.com" value={manualOrder.customer_email} onChange={e => setManualOrder({ ...manualOrder, customer_email: e.target.value })} />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-500">Product</label>
              <select value={manualOrder.product_id} onChange={e => setManualOrder({ ...manualOrder, product_id: e.target.value })} className="w-full h-9 text-sm border border-slate-200 rounded px-2 bg-white">
                <option value="">Select product</option>
                {products.map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1"><label className="text-xs text-slate-500">Subtotal</label><Input type="number" step="0.01" value={manualOrder.subtotal} onChange={e => setManualOrder({ ...manualOrder, subtotal: parseFloat(e.target.value) || 0 })} /></div>
              <div className="space-y-1"><label className="text-xs text-slate-500">Discount</label><Input type="number" step="0.01" value={manualOrder.discount} onChange={e => setManualOrder({ ...manualOrder, discount: parseFloat(e.target.value) || 0 })} /></div>
              <div className="space-y-1"><label className="text-xs text-slate-500">Fee</label><Input type="number" step="0.01" value={manualOrder.fee} onChange={e => setManualOrder({ ...manualOrder, fee: parseFloat(e.target.value) || 0 })} /></div>
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-500">Status</label>
              <select value={manualOrder.status} onChange={e => setManualOrder({ ...manualOrder, status: e.target.value })} className="w-full h-9 text-sm border border-slate-200 rounded px-2">
                <option value="paid">Paid (Manual)</option><option value="unpaid">Unpaid (Manual)</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-500">Internal Note</label>
              <Textarea placeholder="Optional note" value={manualOrder.internal_note} onChange={e => setManualOrder({ ...manualOrder, internal_note: e.target.value })} rows={2} />
            </div>
            <Button onClick={handleCreateManual} className="w-full">Create Order</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
