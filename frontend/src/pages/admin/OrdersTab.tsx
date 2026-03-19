import { useCallback, useEffect, useState } from "react";
import { ImportModal } from "@/components/admin/ImportModal";
import { RequiredLabel } from "@/components/shared/RequiredLabel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Table, TableBody, TableCell, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SearchableSelect } from "@/components/ui/searchable-select";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { AdminPageHeader } from "./shared/AdminPageHeader";
import { OrdersStats } from "./shared/DashboardStats";
import { AdminPagination } from "./shared/AdminPagination";
import { AuditLogDialog } from "@/components/AuditLogDialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Download, ExternalLink, Upload} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { ColHeader } from "@/components/shared/ColHeader";
import { computeTax, TaxSubject, TaxEntry, OverrideRule } from "@/utils/taxUtils";
import { useSupportedCurrencies } from "@/hooks/useSupportedCurrencies";

const getProcessorLink = (id: string | undefined): string | null => {
  if (!id) return null;
  if (id.startsWith("pi_") || id.startsWith("ch_")) return `https://dashboard.stripe.com/payments/${id}`;
  if (id.startsWith("sub_")) return `https://dashboard.stripe.com/subscriptions/${id}`;
  if (id.startsWith("cus_")) return `https://dashboard.stripe.com/customers/${id}`;
  if (id.startsWith("in_")) return `https://dashboard.stripe.com/invoices/${id}`;
  if (id.startsWith("cs_")) return `https://dashboard.stripe.com/checkout/sessions/${id}`;
  if (id.startsWith("PM")) return `https://manage.gocardless.com/payments/${id}`;
  if (id.startsWith("MD")) return `https://manage.gocardless.com/mandates/${id}`;
  if (id.startsWith("SB")) return `https://manage.gocardless.com/subscriptions/${id}`;
  return null;
};

const ORDER_STATUSES_FALLBACK = ["paid", "unpaid", "completed", "pending", "pending_payment", "pending_direct_debit_setup", "awaiting_bank_transfer", "scope_requested", "scope_pending", "canceled_pending", "cancelled", "refunded", "disputed"];
const PAYMENT_METHODS_FALLBACK = ["card", "bank_transfer", "manual"];

export function OrdersTab() {
  const { user: authUser } = useAuth();
  const isPlatformAdmin = authUser?.role === "platform_admin" || authUser?.role === "platform_super_admin";
  const [orders, setOrders] = useState<any[]>([]);
  const [showImport, setShowImport] = useState(false);
  const [orderItems, setOrderItems] = useState<any[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const PER_PAGE = 20;

  // Filter options from backend (single source of truth)
  const [orderStatuses, setOrderStatuses] = useState<string[]>(ORDER_STATUSES_FALLBACK);
  const [paymentMethods, setPaymentMethods] = useState<string[]>(PAYMENT_METHODS_FALLBACK);

  // For table display + edit dialog
  const [customers, setCustomers] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [products, setProducts] = useState<any[]>([]);

  // Filters
  const [emailFilter, setEmailFilter] = useState<string[]>([]);
  const [customerFilter, setCustomerFilter] = useState<string[]>([]);
  const [orderNumberFilter, setOrderNumberFilter] = useState<string[]>([]);
  const [statusFilter, setStatusFilter] = useState<string[]>([]);
  const [productFilter, setProductFilter] = useState<string[]>([]);
  const [subNumberFilter, setSubNumberFilter] = useState<string[]>([]);
  const [processorIdFilter, setProcessorIdFilter] = useState<string[]>([]);
  const [payMethodFilter, setPayMethodFilter] = useState<string[]>([]);
  const [partnerFilter, setPartnerFilter] = useState<string[]>([]);
  const [payDateFrom, setPayDateFrom] = useState("");
  const [payDateTo, setPayDateTo] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [includeDeleted, setIncludeDeleted] = useState(false);
  const [colSort, setColSort] = useState<{ col: string; dir: "asc" | "desc" }>({ col: "date", dir: "desc" });

  // Dialogs
  const [selectedOrder, setSelectedOrder] = useState<any>(null);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [logsUrl, setLogsUrl] = useState("");
  const [showAuditLogs, setShowAuditLogs] = useState(false);
  const [showNotesDialog, setShowNotesDialog] = useState(false);
  const [noteData, setNoteData] = useState<{ notes: any[]; notes_json: any }>({ notes: [], notes_json: null });
  const [showManualDialog, setShowManualDialog] = useState(false);
  const [showRefundDialog, setShowRefundDialog] = useState(false);
  const [refundForm, setRefundForm] = useState({
    amount: "",
    reason: "requested_by_customer",
    provider: "manual",
    processViaProvider: true
  });
  const [processingRefund, setProcessingRefund] = useState(false);
  const [refundProviders, setRefundProviders] = useState<any[]>([]);
  const [loadingProviders, setLoadingProviders] = useState(false);
  const [manualOrder, setManualOrder] = useState({
    customer_email: "", product_id: "", quantity: 1,
    subtotal: 0, discount: 0, fee: 0, status: "paid", currency: "USD", internal_note: "",
    tax_rate: "" as string | number, tax_name: "", order_date: "", payment_date: "",
  });
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [confirmChargeId, setConfirmChargeId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [creatingOrder, setCreatingOrder] = useState(false);
  // Refund history
  const [showRefundHistoryDialog, setShowRefundHistoryDialog] = useState(false);
  const [refundHistory, setRefundHistory] = useState<any[]>([]);
  const [loadingRefundHistory, setLoadingRefundHistory] = useState(false);

  // Build lookup maps
  const userMap: Record<string, any> = {};
  users.forEach((u) => { userMap[u.id] = u; });
  const custMap: Record<string, any> = {};
  customers.forEach((c) => { custMap[c.id] = c; });
  const productMap: Record<string, string> = {};
  products.forEach((p) => { productMap[p.id] = p.name; });

  // Tax data for auto-population
  const [taxEnabled, setTaxEnabled] = useState(false);
  const [taxEntries, setTaxEntries] = useState<TaxEntry[]>([]);
  const [overrideRules, setOverrideRules] = useState<OverrideRule[]>([]);
  const [orgAddress, setOrgAddress] = useState<{ country?: string; region?: string }>({});
  // Supported currencies
  const { currencies: supportedCurrencies } = useSupportedCurrencies();

  const getCustomerUser = (customerId: string) => {
    const c = custMap[customerId];
    return c ? userMap[c.user_id] : null;
  };

  const load = useCallback(async (p = 1) => {
    try {
      const params = new URLSearchParams({
        page: String(p), per_page: String(PER_PAGE),
        sort_by: colSort.col,  // backend handles all colKey→field alias mapping
        sort_order: colSort.dir,
        include_deleted: String(includeDeleted),
      });
      if (orderNumberFilter.length > 0) params.append("order_number_filter", orderNumberFilter.join(","));
      if (statusFilter.length > 0) params.append("status_filter", statusFilter.join(","));
      if (productFilter.length > 0) params.append("product_filter", productFilter.join(","));
      if (subNumberFilter.length > 0) params.append("sub_number_filter", subNumberFilter.join(","));
      if (processorIdFilter.length > 0) params.append("processor_id_filter", processorIdFilter.join(","));
      if (payMethodFilter.length > 0) params.append("payment_method_filter", payMethodFilter.join(","));
      if (partnerFilter.length > 0) params.append("partner_filter", partnerFilter.join(","));
      if (payDateFrom) params.append("pay_date_from", payDateFrom);
      if (payDateTo) params.append("pay_date_to", payDateTo);
      // X-1: server-side creation date filter (was client-side, broken)
      if (startDate) params.append("created_from", startDate);
      if (endDate) params.append("created_to", endDate);
      // X-2: server-side email/customer-name filter (was client-side, broken)
      if (emailFilter.length > 0) params.append("email_filter", emailFilter.join(","));
      if (customerFilter.length > 0) params.append("customer_name_filter", customerFilter.join(","));
      const res = await api.get(`/admin/orders?${params}`);
      setOrders(res.data.orders || []);
      setOrderItems(res.data.items || []);
      setTotalPages(res.data.total_pages || 1);
      setTotal(res.data.total || 0);
      setPage(p);
    } catch { toast.error("Failed to load orders"); }
  }, [colSort, includeDeleted, orderNumberFilter, statusFilter, productFilter, subNumberFilter, processorIdFilter, payMethodFilter, partnerFilter, payDateFrom, payDateTo, emailFilter, customerFilter, startDate, endDate]);

  useEffect(() => {
    api.get("/admin/filter-options").then(r => {
      if (r.data.order_statuses) setOrderStatuses(r.data.order_statuses);
      if (r.data.payment_methods) setPaymentMethods(r.data.payment_methods);
    }).catch(() => {});
    Promise.all([
      api.get("/admin/customers?per_page=1000").catch(() => ({ data: { customers: [], users: [] } })),
      api.get("/admin/products-all?per_page=500").catch(() => ({ data: { products: [] } })),
      api.get("/admin/taxes/settings").catch(() => ({ data: {} })),
      api.get("/admin/taxes/tables").catch(() => ({ data: { entries: [] } })),
      api.get("/admin/taxes/overrides").catch(() => ({ data: { rules: [] } })),
      api.get("/admin/tenants/my").catch(() => ({ data: { tenant: {} } })),
    ]).then(([custRes, prodRes, tsRes, teRes, torRes, myTenantRes]) => {
      setCustomers(custRes.data.customers || []);
      setUsers(custRes.data.users || []);
      setProducts(prodRes.data.products || []);
      setTaxEnabled(tsRes.data?.tax_settings?.enabled === true);
      setTaxEntries(teRes.data?.entries || []);
      setOverrideRules(torRes.data?.rules || []);
      setOrgAddress(myTenantRes.data?.tenant?.address || {});
    });
  }, []);

  // Build unique dropdown options
  const uniqueOrderNumbers = orders.map(o => o.order_number).filter(Boolean);
  const uniqueEmails = Array.from(new Set(users.map(u => u.email).filter(Boolean)));
  const uniqueCustomerNames = Array.from(new Set(users.map(u => u.full_name).filter(Boolean)));
  const uniqueProductNames = Array.from(new Set(products.map((p: any) => p.name).filter(Boolean)));
  const uniqueSubNumbers = Array.from(new Set(orders.map(o => o.subscription_number || o.subscription_id?.slice(0, 8)).filter(Boolean)));
  const uniqueProcessorIds = orders.map(o => o.processor_id).filter(Boolean);
  const uniquePartners = Array.from(new Set(orders.map(o => o.partner_code).filter(Boolean)));

  useEffect(() => { load(1); }, [colSort, includeDeleted, orderNumberFilter, statusFilter, productFilter, subNumberFilter, processorIdFilter, payMethodFilter, partnerFilter, payDateFrom, payDateTo, emailFilter, customerFilter, startDate, endDate]);

  // customer search for edit dialog
  const [custSearch, setCustSearch] = useState("");
  const filteredCusts = customers.filter(c => {
    const u = userMap[c.user_id];
    const q = custSearch.toLowerCase();
    return !q || u?.email?.toLowerCase().includes(q) || c.company_name?.toLowerCase().includes(q);
  }).slice(0, 10);

  const handleEdit = async () => {
    if (!selectedOrder) return;
    // Validation #7: payment_date required when status = paid
    if (selectedOrder.status === "paid" && !selectedOrder.payment_date) {
      toast.error("Payment date is required when status is 'paid'"); return;
    }
    // Validation #8: total must not be negative
    if (selectedOrder.total < 0) {
      toast.error("Total cannot be negative"); return;
    }
    setSaving(true);
    try {
      await api.put(`/admin/orders/${selectedOrder.id}`, {
        customer_id: selectedOrder.customer_id,
        status: selectedOrder.status,
        payment_method: selectedOrder.payment_method,
        order_date: selectedOrder.order_date_edit || undefined,
        payment_date: selectedOrder.payment_date?.slice(0, 10) || undefined,
        subtotal: selectedOrder.subtotal,
        fee: selectedOrder.fee,
        total: selectedOrder.total,
        subscription_id: selectedOrder.subscription_id || undefined,
        product_id: selectedOrder.edit_product_id || undefined,
        internal_note: selectedOrder.internal_note,
        new_note: selectedOrder.new_note || undefined,
        processor_id: selectedOrder.processor_id !== undefined ? selectedOrder.processor_id : undefined,
      });
      toast.success("Order updated");
      setShowEditDialog(false);
      setSelectedOrder(null);
      load(page);
    } catch (e: any) { toast.error(e.response?.data?.detail || "Failed to update order"); }
    finally { setSaving(false); }
  };

  const handleDelete = async (orderId: string) => {
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
    if (!manualOrder.customer_email.trim()) { toast.error("Customer email is required"); return; }
    if (!manualOrder.product_id) { toast.error("Product is required"); return; }
    if (!manualOrder.currency) { toast.error("Currency is required"); return; }
    if (!manualOrder.status) { toast.error("Status is required"); return; }
    // Validation #6: subtotal must be ≥ 0
    if (manualOrder.subtotal < 0) { toast.error("Subtotal cannot be negative"); return; }
    // Validation #5: quantity must be ≥ 1
    if (manualOrder.quantity < 1) { toast.error("Quantity must be at least 1"); return; }
    // Validation #4: discount cannot exceed subtotal
    if (manualOrder.discount > manualOrder.subtotal) { toast.error("Discount cannot exceed subtotal"); return; }
    // Validation #3: payment_date required when status = paid
    if (manualOrder.status === "paid" && !manualOrder.payment_date) { toast.error("Payment date is required when status is 'paid'"); return; }
    setCreatingOrder(true);
    try {
      await api.post("/admin/orders/manual", manualOrder);
      toast.success("Manual order created");
      setShowManualDialog(false);
      setManualOrder({ customer_email: "", product_id: "", quantity: 1, subtotal: 0, discount: 0, fee: 0, status: "paid", currency: "USD", internal_note: "", tax_rate: "", tax_name: "", order_date: "", payment_date: "" });
      load(1);
    } catch (e: any) { toast.error(e.response?.data?.detail || "Failed to create order"); }
    finally { setCreatingOrder(false); }
  };

  const clearFilters = () => {
    setEmailFilter([]); setCustomerFilter([]); setOrderNumberFilter([]); setStatusFilter([]); setProductFilter([]);
    setSubNumberFilter([]); setProcessorIdFilter([]); setPayMethodFilter([]); setPartnerFilter([]);
    setPayDateFrom(""); setPayDateTo("");
    setStartDate(""); setEndDate(""); setIncludeDeleted(false);
  };

  const downloadCsv = () => {
    const token = localStorage.getItem("aa_token");
    const baseUrl = process.env.REACT_APP_BACKEND_URL || "";
    const params = new URLSearchParams({ sort_order: colSort.dir, include_deleted: String(includeDeleted) });
    if (orderNumberFilter.length > 0) params.append("order_number_filter", orderNumberFilter.join(","));
    if (statusFilter.length > 0) params.append("status_filter", statusFilter.join(","));
    if (productFilter.length > 0) params.append("product_filter", productFilter.join(","));
    fetch(`${baseUrl}/api/admin/export/orders?${params}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.blob()).then(b => { const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = `orders-${new Date().toISOString().slice(0, 10)}.csv`; a.click(); })
      .catch(() => toast.error("Export failed"));
  };

  const statusColor = (s: string) => {
    if (s === "paid" || s === "completed") return "aa-badge aa-badge-success";
    if (s === "unpaid") return "aa-badge aa-badge-danger";
    if (s === "awaiting_bank_transfer" || s === "pending" || s === "pending_payment" || s === "pending_direct_debit_setup") return "aa-badge aa-badge-warning";
    if (s === "partially_refunded") return "aa-badge aa-badge-warning";  // M-6
    if (s === "cancelled" || s === "refunded" || s === "canceled_pending") return "aa-badge aa-badge-muted";
    return "aa-badge aa-badge-muted";
  };

  return (
    <div className="flex flex-col gap-4" data-testid="orders-tab">
      <AdminPageHeader
        title="Orders"
        subtitle={`${total} records`}
        actions={
          <>
            <Button size="sm" variant="outline" onClick={downloadCsv} data-testid="admin-orders-export-csv"><Download size={14} className="mr-1" />Export CSV</Button>
            <Button size="sm" variant="outline" onClick={() => setShowImport(true)} data-testid="admin-orders-import-csv"><Upload size={14} className="mr-1" />Import CSV</Button>
            <Button size="sm" onClick={() => setShowManualDialog(true)} data-testid="admin-create-order-btn">Create Manual Order</Button>
          </>
        }
      />

      {/* Stats Dashboard */}
      <OrdersStats />

      {/* Filters removed — use column headers */}

      <div className="flex items-center gap-2 flex-wrap text-xs text-slate-500 mb-1 px-1">
        <label className="flex items-center gap-1 cursor-pointer">
          <input type="checkbox" checked={includeDeleted} onChange={e => setIncludeDeleted(e.target.checked)} className="h-3 w-3" />
          Show deleted
        </label>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
        <Table data-testid="admin-orders-table" className="min-w-[1100px]">
          <TableHeader>
            <TableRow className="bg-slate-50">
              <ColHeader label="Date" colKey="date" sortCol={colSort.col} sortDir={colSort.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort({ col: "date", dir: "desc" })} filterType="date-range" filterValue={{ from: startDate, to: endDate }} onFilter={v => { setStartDate(v.from || ""); setEndDate(v.to || ""); }} onClearFilter={() => { setStartDate(""); setEndDate(""); }} />
              <ColHeader label="Order #" colKey="order_number" sortCol={colSort.col} sortDir={colSort.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort({ col: "date", dir: "desc" })} filterType="dropdown" filterValue={orderNumberFilter} onFilter={v => setOrderNumberFilter(v)} onClearFilter={() => setOrderNumberFilter([])} statusOptions={uniqueOrderNumbers.map(o => [o, o] as [string, string])} />
              <ColHeader label="Customer" colKey="customer" sortCol={colSort.col} sortDir={colSort.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort({ col: "date", dir: "desc" })} filterType="dropdown" filterValue={customerFilter} onFilter={v => setCustomerFilter(v)} onClearFilter={() => setCustomerFilter([])} statusOptions={uniqueCustomerNames.map(c => [c, c] as [string, string])} />
              <ColHeader label="Email" colKey="email" sortCol={colSort.col} sortDir={colSort.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort({ col: "date", dir: "desc" })} filterType="dropdown" filterValue={emailFilter} onFilter={v => setEmailFilter(v)} onClearFilter={() => setEmailFilter([])} statusOptions={uniqueEmails.map(e => [e, e] as [string, string])} />
              <ColHeader label="Product(s)" colKey="product" sortCol={colSort.col} sortDir={colSort.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort({ col: "date", dir: "desc" })} filterType="dropdown" filterValue={productFilter} onFilter={v => setProductFilter(v)} onClearFilter={() => setProductFilter([])} statusOptions={uniqueProductNames.map(p => [p, p] as [string, string])} />
              <ColHeader label="Sub #" colKey="subscription_number" sortCol={colSort.col} sortDir={colSort.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort({ col: "date", dir: "desc" })} filterType="dropdown" filterValue={subNumberFilter} onFilter={v => setSubNumberFilter(v)} onClearFilter={() => setSubNumberFilter([])} statusOptions={uniqueSubNumbers.map(s => [s, s] as [string, string])} />
              <ColHeader label="Processor ID" colKey="processor_id" sortCol={colSort.col} sortDir={colSort.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort({ col: "date", dir: "desc" })} filterType="dropdown" filterValue={processorIdFilter} onFilter={v => setProcessorIdFilter(v)} onClearFilter={() => setProcessorIdFilter([])} statusOptions={uniqueProcessorIds.map(p => [p, p.slice(0, 14) + "…"] as [string, string])} />
              <ColHeader label="Subtotal" colKey="subtotal" sortCol={colSort.col} sortDir={colSort.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort({ col: "date", dir: "desc" })} filterType="none" />
              <ColHeader label="Fee" colKey="fee" sortCol={colSort.col} sortDir={colSort.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort({ col: "date", dir: "desc" })} filterType="none" />
              <ColHeader label="Tax" colKey="tax_amount" sortCol={colSort.col} sortDir={colSort.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort({ col: "date", dir: "desc" })} filterType="none" />
              <ColHeader label="Total" colKey="total" sortCol={colSort.col} sortDir={colSort.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort({ col: "date", dir: "desc" })} filterType="none" />
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500">Refunded</th>
              <ColHeader label="Currency" colKey="currency" sortCol={colSort.col} sortDir={colSort.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort({ col: "date", dir: "desc" })} filterType="none" />
              <ColHeader label="Pay Date" colKey="payment_date" sortCol={colSort.col} sortDir={colSort.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort({ col: "date", dir: "desc" })} filterType="date-range" filterValue={{ from: payDateFrom, to: payDateTo }} onFilter={v => { setPayDateFrom(v.from || ""); setPayDateTo(v.to || ""); }} onClearFilter={() => { setPayDateFrom(""); setPayDateTo(""); }} />
              <ColHeader label="Method" colKey="payment_method" sortCol={colSort.col} sortDir={colSort.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort({ col: "date", dir: "desc" })} filterType="dropdown" filterValue={payMethodFilter} onFilter={v => setPayMethodFilter(v)} onClearFilter={() => setPayMethodFilter([])} statusOptions={paymentMethods.map(m => [m, m] as [string, string])} />
              <ColHeader label="Status" colKey="status" sortCol={colSort.col} sortDir={colSort.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort({ col: "date", dir: "desc" })} filterType="dropdown" filterValue={statusFilter} onFilter={v => setStatusFilter(v)} onClearFilter={() => setStatusFilter([])} statusOptions={orderStatuses.map(s => [s, s] as [string, string])} />
              {isPlatformAdmin && <ColHeader label="Partner" colKey="partner_code" sortCol={colSort.col} sortDir={colSort.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort({ col: "date", dir: "desc" })} filterType="dropdown" filterValue={partnerFilter} onFilter={v => setPartnerFilter(v)} onClearFilter={() => setPartnerFilter([])} statusOptions={uniquePartners.map(p => [p, p] as [string, string])} />}
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500">Actions</th>
            </TableRow>
          </TableHeader>
          <TableBody>
            {orders.map((order) => {
              const user = getCustomerUser(order.customer_id);
              const items = orderItems.filter(i => i.order_id === order.id);
              const productNames = items.map(i => productMap[i.product_id] || i.product_id).join(", ") || "—";
              return (
                <TableRow key={order.id} data-testid={`admin-order-row-${order.id}`} className="aa-table-row">
                  <TableCell className="whitespace-nowrap">{order.created_at?.slice(0, 10)}</TableCell>
                  <TableCell className="font-mono">{order.order_number}</TableCell>
                  <TableCell className="max-w-[144px] truncate">{user?.full_name || "—"}</TableCell>
                  <TableCell className="max-w-[160px] truncate">{user?.email || "—"}</TableCell>
                  <TableCell className="max-w-[160px] truncate">{productNames}</TableCell>
                  <TableCell className="font-mono">{order.subscription_number || order.subscription_id?.slice(0, 8) || "—"}</TableCell>
                  <TableCell className="font-mono text-[10px]" data-testid={`admin-order-processor-${order.id}`}>
                    {order.processor_id ? (() => {
                      const link = getProcessorLink(order.processor_id);
                      return link ? (
                        <a href={link} target="_blank" rel="noopener noreferrer" title={order.processor_id} className="inline-flex items-center gap-0.5 px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded hover:bg-blue-100 transition-colors">
                          {order.processor_id.slice(0, 14)}… <ExternalLink size={10} />
                        </a>
                      ) : (
                        <span title={order.processor_id} className="px-1.5 py-0.5 bg-slate-100 rounded">{order.processor_id.slice(0, 14)}…</span>
                      );
                    })() : "—"}
                  </TableCell>
                  <TableCell>{order.currency || "USD"} {order.subtotal?.toFixed(2)}</TableCell>
                  <TableCell>
                    {order.fee > 0 && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-amber-100 text-amber-700">
                        fee: {order.currency || "USD"} {order.fee.toFixed(2)}
                      </span>
                    )}
                  </TableCell>
                  <TableCell>
                    {order.tax_amount > 0 && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-blue-50 text-blue-700" title={order.tax_name || "Tax"}>
                        {order.tax_name || "Tax"}: {order.currency || "USD"} {order.tax_amount?.toFixed(2)}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="font-semibold">{order.currency || "USD"} {order.total?.toFixed(2)}</TableCell>
                  <TableCell data-testid={`order-refunded-${order.id}`}>
                    {(order.refunded_amount || 0) > 0
                      ? <span className="text-purple-700 text-xs font-medium">{order.currency || "USD"} {((order.refunded_amount) / 100).toFixed(2)}</span>
                      : <span className="text-slate-300">—</span>}
                  </TableCell>
                  <TableCell><span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">{order.currency || "USD"}</span></TableCell>
                  <TableCell className="whitespace-nowrap">{order.payment_date?.slice(0, 10) || "—"}</TableCell>
                  <TableCell>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] ${order.payment_method === "bank_transfer" ? "bg-blue-100 text-blue-700" : order.payment_method === "manual" ? "bg-gray-100 text-gray-700" : "bg-green-100 text-green-700"}`}>
                      {order.payment_method === "bank_transfer" ? "Bank" : order.payment_method === "manual" ? "Manual" : "Card"}
                    </span>
                  </TableCell>
                  <TableCell>
                    <span className={statusColor(order.status)}>{order.status}</span>
                  </TableCell>
                  {isPlatformAdmin && <TableCell className="text-xs text-slate-500" data-testid={`admin-order-partner-${order.id}`}>{order.partner_code || "—"}</TableCell>}
                  <TableCell>
                    <div className="flex gap-1 flex-nowrap items-center">
                      <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px]" onClick={() => { setLogsUrl(`/admin/orders/${order.id}/logs`); setShowAuditLogs(true); }} data-testid={`admin-order-logs-${order.id}`}>Logs</Button>
                      <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px]" onClick={() => { setNoteData({ notes: order.notes || [], notes_json: order.notes_json || null }); setShowNotesDialog(true); }} data-testid={`admin-order-notes-${order.id}`}>Notes{order.notes?.length ? ` (${order.notes.length})` : ""}</Button>
                      <Button variant="outline" size="sm" className="h-6 px-2 text-[11px]" onClick={() => { setSelectedOrder({ ...order, order_date_edit: order.created_at?.slice(0, 10) }); setShowEditDialog(true); }} data-testid={`admin-order-edit-${order.id}`}>Edit</Button>
                      {order.status === "unpaid" && (
                        <Button size="sm" variant="secondary" className="h-6 px-2 text-[11px]" onClick={() => setConfirmChargeId(order.id)} data-testid={`admin-order-charge-${order.id}`}>Charge</Button>
                      )}
                      {(order.status === "refunded" || order.status === "partially_refunded") && (
                        <Button size="sm" variant="ghost" className="h-6 px-2 text-[11px] text-purple-600" onClick={async () => {
                          setSelectedOrder(order);
                          setLoadingRefundHistory(true);
                          setShowRefundHistoryDialog(true);
                          try {
                            const res = await api.get(`/admin/orders/${order.id}/refunds`);
                            setRefundHistory(res.data.refunds || []);
                          } catch { setRefundHistory([]); }
                          finally { setLoadingRefundHistory(false); }
                        }} data-testid={`admin-order-refund-history-${order.id}`}>Refunds</Button>
                      )}
                      {(order.status === "paid" || order.status === "partially_refunded") &&
                        (order.total - (order.refunded_amount || 0) / 100) > 0 && (
                        <Button size="sm" variant="outline" className="h-6 px-2 text-[11px] text-amber-600 border-amber-200 hover:bg-amber-50" onClick={async () => {
                          setSelectedOrder(order);
                          setLoadingProviders(true);
                          try {
                            const res = await api.get(`/admin/orders/${order.id}/refund-providers`);
                            setRefundProviders(res.data.providers || []);
                            // Default to original provider if available, else manual
                            const originalProvider = res.data.providers?.find((p: any) => p.is_original && p.available);
                            setRefundForm(prev => ({
                              ...prev,
                              provider: originalProvider?.id || "manual",
                              processViaProvider: originalProvider?.id !== "manual"
                            }));
                          } catch {
                            setRefundProviders([{ id: "manual", name: "Manual (Record Only)", available: true, is_original: true }]);
                          } finally {
                            setLoadingProviders(false);
                          }
                          setShowRefundDialog(true);
                        }} data-testid={`admin-order-refund-${order.id}`}>Refund</Button>
                      )}
                      <Button size="sm" variant="destructive" className="h-6 px-2 text-[11px]" onClick={() => setConfirmDeleteId(order.id)} data-testid={`admin-order-delete-${order.id}`}>Delete</Button>
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
      <Dialog open={showEditDialog} onOpenChange={(open) => { setShowEditDialog(open); if (!open) { setSelectedOrder(null); setCustSearch(""); } }}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="admin-order-edit-dialog">
          <DialogHeader><DialogTitle>Edit Order {selectedOrder?.order_number}</DialogTitle></DialogHeader>
          {selectedOrder && (
            <div className="space-y-4 py-2">
              {/* Customer selector — email typeahead */}
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-600 uppercase tracking-wide">Customer (search by email)</label>
                <Input placeholder="Type email to search…" value={custSearch} onChange={e => setCustSearch(e.target.value)} className="h-9 aa-admin-search" data-testid="admin-order-customer-search" />
                {custSearch && filteredCusts.length > 0 && (
                  <div className="border border-slate-200 rounded bg-white shadow-md max-h-36 overflow-y-auto z-10">
                    {filteredCusts.map((c: any) => {
                      const u = userMap[c.user_id];
                      return <div key={c.id} onClick={() => { setSelectedOrder({ ...selectedOrder, customer_id: c.id }); setCustSearch(u?.email || ""); }} className="px-3 py-2 hover:bg-slate-50 cursor-pointer text-sm">{u?.email} {c.company_name ? `— ${c.company_name}` : ""}</div>;
                    })}
                  </div>
                )}
                {selectedOrder.customer_id && (() => { const u = getCustomerUser(selectedOrder.customer_id); return u ? <p className="text-xs text-green-600">Selected: {u.email} — {u.full_name}</p> : null; })()}
              </div>

              <div className="grid grid-cols-2 gap-3">
                {/* Status */}
                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-600 uppercase tracking-wide">Status</label>
                  <Select value={selectedOrder.status || ""} onValueChange={v => {
                    const updated: any = { ...selectedOrder, status: v };
                    // Auto-clear payment_date when status changes away from paid (#17)
                    if (v !== "paid") updated.payment_date = "";
                    setSelectedOrder(updated);
                  }} data-testid="admin-order-status-select">
                    <SelectTrigger className="w-full bg-white"><SelectValue /></SelectTrigger>
                    <SelectContent>{orderStatuses.filter(s => s !== "refunded" && s !== "partially_refunded").map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                {/* Payment Method */}
                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-600 uppercase tracking-wide">Payment Method</label>
                  <Select value={selectedOrder.payment_method || ""} onValueChange={v => setSelectedOrder({ ...selectedOrder, payment_method: v })} data-testid="admin-order-payment-select">
                    <SelectTrigger className="w-full bg-white"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="card">Card</SelectItem>
                      <SelectItem value="bank_transfer">Bank Transfer</SelectItem>
                      <SelectItem value="manual">Manual</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {/* Order Date */}
                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-600 uppercase tracking-wide">Order Date</label>
                  <Input type="date" value={selectedOrder.order_date_edit || ""} onChange={e => setSelectedOrder({ ...selectedOrder, order_date_edit: e.target.value })} data-testid="admin-order-date-input" />
                </div>
                {/* Pay Date */}
                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-600 uppercase tracking-wide">Payment Date</label>
                  <Input type="date" value={selectedOrder.payment_date?.slice(0, 10) || ""} onChange={e => setSelectedOrder({ ...selectedOrder, payment_date: e.target.value })} data-testid="admin-order-payment-date" />
                </div>
                {/* Subtotal */}
                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-600 uppercase tracking-wide">Subtotal ({selectedOrder?.currency || "USD"})</label>
                  <Input type="number" step="0.01" value={selectedOrder.subtotal ?? ""} onChange={e => {
                    const sub = parseFloat(e.target.value) || 0;
                    const newTotal = Math.max(0, sub + (selectedOrder.fee || 0) + (selectedOrder.tax_amount || 0) - (selectedOrder.discount_amount || 0));
                    setSelectedOrder({ ...selectedOrder, subtotal: sub, total: Math.round(newTotal * 100) / 100 });
                  }} data-testid="admin-order-subtotal-input" />
                </div>
                {/* Fee */}
                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-600 uppercase tracking-wide">Fee ({selectedOrder?.currency || "USD"})</label>
                  <Input type="number" step="0.01" value={selectedOrder.fee ?? ""} onChange={e => {
                    const fee = parseFloat(e.target.value) || 0;
                    const newTotal = Math.max(0, (selectedOrder.subtotal || 0) + fee + (selectedOrder.tax_amount || 0) - (selectedOrder.discount_amount || 0));
                    setSelectedOrder({ ...selectedOrder, fee, total: Math.round(newTotal * 100) / 100 });
                  }} data-testid="admin-order-fee-input" />
                </div>
                {/* Total */}
                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-600 uppercase tracking-wide">Total ({selectedOrder?.currency || "USD"}) <span className="text-[10px] text-slate-400 normal-case">(auto-calculated)</span></label>
                  <Input type="number" step="0.01" value={selectedOrder.total ?? ""} onChange={e => setSelectedOrder({ ...selectedOrder, total: parseFloat(e.target.value) || 0 })} data-testid="admin-order-total-input" />
                </div>
                {/* Currency — M-8 */}
                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-600 uppercase tracking-wide">Currency</label>
                  <Select value={selectedOrder.currency || "USD"} onValueChange={v => setSelectedOrder({ ...selectedOrder, currency: v })} data-testid="admin-order-currency-edit-select">
                    <SelectTrigger className="w-full bg-white"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {(supportedCurrencies.length ? supportedCurrencies : ["USD", "CAD", "EUR", "AUD", "GBP", "INR", "MXN"]).map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                {/* Subscription ID */}
                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-600 uppercase tracking-wide">Subscription ID / #</label>
                  <Input value={selectedOrder.subscription_id || ""} onChange={e => setSelectedOrder({ ...selectedOrder, subscription_id: e.target.value })} placeholder="Leave blank to unlink" data-testid="admin-order-subscription-input" />
                </div>
                {/* Processor ID */}
                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-600 uppercase tracking-wide">Processor ID</label>
                  <div className="flex items-center gap-1">
                    <Input value={selectedOrder.processor_id || ""} onChange={e => setSelectedOrder({ ...selectedOrder, processor_id: e.target.value })} placeholder="e.g. pi_xxx or PM01xxx" data-testid="admin-order-processor-input" className="flex-1" />
                    {selectedOrder.processor_id && getProcessorLink(selectedOrder.processor_id) && (
                      <a href={getProcessorLink(selectedOrder.processor_id)!} target="_blank" rel="noopener noreferrer" className="flex items-center justify-center h-9 w-9 border border-slate-200 rounded hover:bg-slate-50 transition-colors" title="Open in payment dashboard">
                        <ExternalLink size={14} className="text-blue-600" />
                      </a>
                    )}
                  </div>
                </div>
              </div>

              {/* Product change */}
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-600 uppercase tracking-wide">Change Product (updates first line item)</label>
              <SearchableSelect
                value={selectedOrder.edit_product_id || undefined}
                onValueChange={v => setSelectedOrder({ ...selectedOrder, edit_product_id: v })}
                options={[{ value: "", label: "— Keep current product —" }, ...products.map((p: any) => ({ value: p.id, label: p.name }))]}
                placeholder="— Keep current product —"
                searchPlaceholder="Search products..."
                data-testid="admin-order-product-select"
              />
              </div>

              {/* Note */}
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-600 uppercase tracking-wide">Add Note</label>
                <Textarea placeholder="Add a note…" value={selectedOrder.new_note || ""} onChange={e => setSelectedOrder({ ...selectedOrder, new_note: e.target.value })} rows={2} data-testid="admin-order-note-input" />
              </div>
              <Button onClick={handleEdit} disabled={saving} className="w-full" data-testid="admin-order-save">{saving ? "Saving…" : "Save Changes"}</Button>
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
      <AuditLogDialog open={showAuditLogs} onOpenChange={setShowAuditLogs} title="Order Audit Logs" logsUrl={logsUrl} />

      {/* Manual Create Dialog */}
      <Dialog open={showManualDialog} onOpenChange={setShowManualDialog}>
        <DialogContent><DialogHeader><DialogTitle>Create Manual Order</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <RequiredLabel className="text-slate-500 font-normal">Customer Email</RequiredLabel>
              <SearchableSelect
                options={users.map((u: any) => ({
                  value: u.email,
                  label: u.full_name ? `${u.full_name} (${u.email})` : u.email,
                }))}
                value={manualOrder.customer_email || undefined}
                onValueChange={v => {
                  // Auto-populate tax when customer is selected
                  const selectedUser = users.find((u: any) => u.email === v);
                  const selectedCustomer = selectedUser
                    ? customers.find((c: any) => c.user_id === selectedUser.id)
                    : null;
                  let newTaxName = manualOrder.tax_name;
                  let newTaxRate = manualOrder.tax_rate;
                  if (!taxEnabled) {
                    newTaxName = "No tax";
                    newTaxRate = "0";
                  } else if (selectedCustomer?.tax_exempt) {
                    newTaxName = "No tax";
                    newTaxRate = "0";
                  } else {
                    const addr = selectedCustomer?.address?.country
                      ? selectedCustomer.address
                      : orgAddress;
                    const subject: TaxSubject = {
                      country: addr?.country,
                      region: addr?.region,
                      email: v,
                      company_name: selectedCustomer?.company_name,
                    };
                    const result = computeTax(subject, taxEntries, overrideRules);
                    newTaxName = result.tax_name;
                    newTaxRate = result.tax_rate;
                  }
                  setManualOrder({ ...manualOrder, customer_email: v, tax_name: newTaxName, tax_rate: newTaxRate });
                }}
                placeholder="Select or search customer..."
                searchPlaceholder="Search by name or email..."
                data-testid="manual-order-customer-email"
              />
            </div>
            <div className="space-y-1">
              <RequiredLabel className="text-slate-500 font-normal">Product</RequiredLabel>
              <SearchableSelect
                value={manualOrder.product_id || undefined}
                onValueChange={v => {
                  const p = products.find((p: any) => p.id === v);
                  setManualOrder({ ...manualOrder, product_id: v, currency: p?.currency || "USD" });
                }}
                options={products.map((p: any) => ({ value: p.id, label: p.name }))}
                placeholder="Select product"
                searchPlaceholder="Search products..."
                data-testid="manual-order-product-select"
              />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1"><RequiredLabel className="text-slate-500 font-normal">Subtotal</RequiredLabel><Input type="number" min={0} step="0.01" value={manualOrder.subtotal} onChange={e => setManualOrder({ ...manualOrder, subtotal: parseFloat(e.target.value) || 0 })} /></div>
              <div className="space-y-1"><RequiredLabel className="text-slate-500 font-normal">Discount</RequiredLabel><Input type="number" min={0} max={manualOrder.subtotal || undefined} step="0.01" value={manualOrder.discount} onChange={e => setManualOrder({ ...manualOrder, discount: parseFloat(e.target.value) || 0 })} /></div>
              <div className="space-y-1"><RequiredLabel className="text-slate-500 font-normal">Fee</RequiredLabel><Input type="number" min={0} step="0.01" value={manualOrder.fee} onChange={e => setManualOrder({ ...manualOrder, fee: parseFloat(e.target.value) || 0 })} /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <RequiredLabel className="text-slate-500 font-normal">Currency</RequiredLabel>
                <Select value={manualOrder.currency} onValueChange={v => setManualOrder({ ...manualOrder, currency: v })}>
                  <SelectTrigger className="w-full bg-white" data-testid="manual-order-currency-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {(supportedCurrencies.length ? supportedCurrencies : ["USD", "CAD", "EUR", "AUD", "GBP", "INR", "MXN"]).map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <RequiredLabel className="text-slate-500 font-normal">Status</RequiredLabel>
                <Select value={manualOrder.status} onValueChange={v => setManualOrder({ ...manualOrder, status: v })}>
                  <SelectTrigger className="w-full bg-white"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="paid">Paid (Manual)</SelectItem>
                    <SelectItem value="unpaid">Unpaid (Manual)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            {/* Tax fields */}
            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1 col-span-2">
                <label className="text-xs text-slate-500">Tax Name</label>
                <Input value={manualOrder.tax_name} onChange={e => setManualOrder({ ...manualOrder, tax_name: e.target.value })} placeholder="e.g. GST, HST, VAT" />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Tax Rate (%)</label>
                <Input type="number" min={0} max={100} step="0.01" value={manualOrder.tax_rate} onChange={e => setManualOrder({ ...manualOrder, tax_rate: e.target.value })} placeholder="e.g. 13" />
              </div>
              {(() => {
                const taxAmt = manualOrder.subtotal > 0 && Number(manualOrder.tax_rate) > 0
                  ? manualOrder.subtotal * Number(manualOrder.tax_rate) / 100 : 0;
                const orderTotal = Math.max(0, manualOrder.subtotal - manualOrder.discount + manualOrder.fee + taxAmt);
                return (
                  <div className="col-span-3 flex items-center justify-between rounded bg-slate-50 border border-slate-200 px-3 py-2 text-xs text-slate-600">
                    <span>{taxAmt > 0 ? `Tax (${manualOrder.tax_rate}%): ${manualOrder.currency} ${taxAmt.toFixed(2)}` : "No tax"}</span>
                    <span className="font-semibold text-slate-800">Total: {manualOrder.currency} {orderTotal.toFixed(2)}</span>
                  </div>
                );
              })()}
            </div>
            {/* Dates */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Order Date</label>
                <Input type="date" value={manualOrder.order_date || ""} onChange={e => setManualOrder({ ...manualOrder, order_date: e.target.value })} data-testid="manual-order-order-date" />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Payment Date</label>
                <Input type="date" value={manualOrder.payment_date || ""} onChange={e => setManualOrder({ ...manualOrder, payment_date: e.target.value })} data-testid="manual-order-payment-date" />
              </div>
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-500">Internal Note</label>
              <Textarea placeholder="Optional note" value={manualOrder.internal_note} onChange={e => setManualOrder({ ...manualOrder, internal_note: e.target.value })} rows={2} />
            </div>
            <Button onClick={handleCreateManual} disabled={creatingOrder} className="w-full">{creatingOrder ? "Creating…" : "Create Order"}</Button>
          </div>
        </DialogContent>
      </Dialog>
      <ImportModal
        entity="orders"
        entityLabel="Orders"
        open={showImport}
        onClose={() => setShowImport(false)}
        onSuccess={load}
      />

      {/* Refund Dialog */}
      <Dialog open={showRefundDialog} onOpenChange={(open) => { setShowRefundDialog(open); if (!open) { setSelectedOrder(null); setRefundForm({ amount: "", reason: "requested_by_customer", provider: "manual", processViaProvider: true }); } }}>
        <DialogContent className="max-w-md" data-testid="admin-order-refund-dialog">
          <DialogHeader><DialogTitle>Process Refund</DialogTitle></DialogHeader>
          {selectedOrder && (
            <div className="space-y-4 py-2">
              <div className="bg-slate-50 rounded-lg p-3 text-sm">
                <div className="flex justify-between mb-1">
                  <span className="text-slate-500">Order</span>
                  <span className="font-mono font-medium">{selectedOrder.order_number}</span>
                </div>
                <div className="flex justify-between mb-1">
                  <span className="text-slate-500">Order Total</span>
                  <span className="font-medium">{selectedOrder.currency || "USD"} {selectedOrder.total?.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Already Refunded</span>
                  <span className="font-medium text-amber-600">{selectedOrder.currency || "USD"} {((selectedOrder.refunded_amount || 0) / 100).toFixed(2)}</span>
                </div>
                <div className="flex justify-between border-t border-slate-200 pt-2 mt-2">
                  <span className="text-slate-700 font-medium">Available to Refund</span>
                  <span className="font-bold text-emerald-600">
                    {selectedOrder.currency || "USD"} {(selectedOrder.total - (selectedOrder.refunded_amount || 0) / 100).toFixed(2)}
                  </span>
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-600">Refund Amount</label>
                <Input
                  type="number"
                  step="0.01"
                  min={0}
                  max={selectedOrder.total - (selectedOrder.refunded_amount || 0) / 100}
                  placeholder={`Max: ${selectedOrder.currency || "USD"} ${(selectedOrder.total - (selectedOrder.refunded_amount || 0) / 100).toFixed(2)}`}
                  value={refundForm.amount}
                  onChange={(e) => setRefundForm({ ...refundForm, amount: e.target.value })}
                  data-testid="admin-refund-amount-input"
                />
                <p className="text-[10px] text-slate-400">Leave empty for full refund of available balance</p>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-600">Reason</label>
                <Select value={refundForm.reason} onValueChange={(v) => setRefundForm({ ...refundForm, reason: v })}>
                  <SelectTrigger data-testid="admin-refund-reason-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="requested_by_customer">Requested by Customer</SelectItem>
                    <SelectItem value="duplicate">Duplicate Payment</SelectItem>
                    <SelectItem value="fraudulent">Fraudulent</SelectItem>
                    <SelectItem value="other">Other</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-600">Refund Method</label>
                {loadingProviders ? (
                  <div className="text-xs text-slate-400 py-2">Loading payment providers...</div>
                ) : (
                  <Select value={refundForm.provider} onValueChange={(v) => {
                    const provider = refundProviders.find(p => p.id === v);
                    setRefundForm({ ...refundForm, provider: v, processViaProvider: v !== "manual" && provider?.available });
                  }}>
                    <SelectTrigger data-testid="admin-refund-provider-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {refundProviders.map((p) => (
                        <SelectItem key={p.id} value={p.id} disabled={!p.available && p.id !== "manual"}>
                          <div className="flex items-center gap-2">
                            <span>{p.name}</span>
                            {p.is_original && <span className="text-[9px] bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">Original</span>}
                            {!p.available && p.id !== "manual" && <span className="text-[9px] bg-red-100 text-red-700 px-1.5 py-0.5 rounded">Disabled</span>}
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
                {refundForm.provider !== "manual" && refundProviders.find(p => p.id === refundForm.provider)?.description && (
                  <p className="text-[10px] text-slate-400">{refundProviders.find(p => p.id === refundForm.provider)?.description}</p>
                )}
              </div>

              {refundForm.provider !== "manual" && refundProviders.find(p => p.id === refundForm.provider)?.available && (
                <label className="flex items-center gap-2 text-xs text-slate-600 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={refundForm.processViaProvider}
                    onChange={(e) => setRefundForm({ ...refundForm, processViaProvider: e.target.checked })}
                  />
                  Process refund via {refundForm.provider === "stripe" ? "Stripe" : refundForm.provider === "gocardless" ? "GoCardless" : refundForm.provider} API
                </label>
              )}

              <Button
                onClick={async () => {
                  if (!selectedOrder) return;
                  const available = selectedOrder.total - (selectedOrder.refunded_amount || 0) / 100;
                  if (refundForm.amount) {
                    const amt = parseFloat(refundForm.amount);
                    if (isNaN(amt) || amt <= 0) { toast.error("Enter a valid refund amount"); return; }
                    if (amt > available) {
                      toast.error(`Refund cannot exceed available balance of ${selectedOrder.currency || "USD"} ${available.toFixed(2)}`);
                      return;
                    }
                  }
                  setProcessingRefund(true);
                  try {
                    const res = await api.post(`/admin/orders/${selectedOrder.id}/refund`, {
                      amount: refundForm.amount ? parseFloat(refundForm.amount) : null,
                      reason: refundForm.reason,
                      provider: refundForm.provider,
                      process_via_provider: refundForm.provider !== "manual" && refundForm.processViaProvider
                    });
                    // Show detailed success message with provider response
                    const providerMsg = res.data.provider_response?.message;
                    const cur = selectedOrder?.currency || "USD";
                    if (providerMsg) {
                      toast.success(`Refund of ${cur} ${res.data.amount?.toFixed(2)} processed. ${providerMsg}`);
                    } else {
                      toast.success(`Refund of ${cur} ${res.data.amount?.toFixed(2)} processed successfully`);
                    }
                    setShowRefundDialog(false);
                    setSelectedOrder(null);
                    setRefundForm({ amount: "", reason: "requested_by_customer", provider: "manual", processViaProvider: true });
                    setRefundProviders([]);
                    load(page);
                  } catch (e: any) {
                    toast.error(e.response?.data?.detail || "Failed to process refund");
                  } finally {
                    setProcessingRefund(false);
                  }
                }}
                className="w-full"
                disabled={processingRefund || loadingProviders}
                data-testid="admin-refund-submit-btn"
              >
                {processingRefund ? "Processing..." : "Process Refund"}
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Refund History Dialog */}
      <Dialog open={showRefundHistoryDialog} onOpenChange={(open) => { setShowRefundHistoryDialog(open); if (!open) { setRefundHistory([]); setSelectedOrder(null); } }}>
        <DialogContent className="max-w-lg" data-testid="refund-history-dialog">
          <DialogHeader><DialogTitle>Refund History — {selectedOrder?.order_number}</DialogTitle></DialogHeader>
          {loadingRefundHistory ? (
            <p className="text-sm text-slate-400 py-4 text-center">Loading refunds…</p>
          ) : refundHistory.length === 0 ? (
            <p className="text-sm text-slate-400 py-4 text-center">No refunds recorded.</p>
          ) : (
            <div className="space-y-3 max-h-[60vh] overflow-y-auto">
              {refundHistory.map((r: any) => (
                <div key={r.id} className="rounded-lg border border-slate-200 p-3 text-sm">
                  <div className="flex justify-between mb-1">
                    <span className="font-semibold text-slate-800">{selectedOrder?.currency || "USD"} {(r.amount / 100).toFixed(2)}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${r.status === "completed" ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-600"}`}>{r.status}</span>
                  </div>
                  <div className="text-slate-500 text-xs flex justify-between">
                    <span>{r.reason?.replace(/_/g, " ")} · via {r.provider}</span>
                    <span>{r.created_at?.slice(0, 10)}</span>
                  </div>
                  {r.provider_refund_id && <div className="text-[10px] text-slate-400 font-mono mt-1">{r.provider_refund_id}</div>}
                </div>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Delete Order Confirmation */}
      <AlertDialog open={!!confirmDeleteId} onOpenChange={(open) => !open && setConfirmDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Order</AlertDialogTitle>
            <AlertDialogDescription>Are you sure you want to delete this order? This action cannot be undone.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction className="bg-red-600 hover:bg-red-700" onClick={() => { handleDelete(confirmDeleteId!); setConfirmDeleteId(null); }} data-testid="confirm-order-delete">
              Delete Order
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Charge Order Confirmation */}
      <AlertDialog open={!!confirmChargeId} onOpenChange={(open) => !open && setConfirmChargeId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Charge Order</AlertDialogTitle>
            <AlertDialogDescription>Are you sure you want to manually charge this order now? This will attempt to collect payment immediately.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => { handleAutoCharge(confirmChargeId!); setConfirmChargeId(null); }} data-testid="confirm-order-charge">
              Yes, Charge Now
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
