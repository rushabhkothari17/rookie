import { useCallback, useEffect, useState } from "react";
import { ImportModal } from "@/components/admin/ImportModal";
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
import { SubscriptionsStats } from "./shared/DashboardStats";
import { AdminPagination } from "./shared/AdminPagination";
import { AuditLogDialog } from "@/components/AuditLogDialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Bell, Download, ExternalLink, Upload} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { ISO_CURRENCIES } from "@/lib/constants";
import { useSupportedCurrencies } from "@/hooks/useSupportedCurrencies";
import { ColHeader } from "@/components/shared/ColHeader";

/** Small reusable button that sends a test renewal reminder for a subscription. */
function TestReminderButton({ subId, endpoint }: { subId: string; endpoint: "subscriptions" | "partner-subscriptions" }) {
  const [sending, setSending] = useState(false);
  const handle = async () => {
    setSending(true);
    try {
      const res = await api.post(`/admin/${endpoint}/${subId}/send-reminder`);
      toast.success(res.data.message || "Reminder sent!");
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to send reminder");
    } finally { setSending(false); }
  };
  return (
    <Button variant="outline" size="sm" onClick={handle} disabled={sending} title="Send test renewal reminder email now" data-testid="send-test-reminder-btn">
      <Bell className="h-4 w-4 mr-1.5" />
      {sending ? "Sending…" : "Test Reminder"}
    </Button>
  );
}

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

const SUB_STATUSES_FALLBACK = ["active", "unpaid", "paused", "canceled_pending", "cancelled", "pending_direct_debit_setup", "offline_manual"];
const PAYMENT_METHODS_FALLBACK = ["card", "bank_transfer", "offline", "manual"];

// ISO_CURRENCIES imported from @/lib/constants
const BILLING_INTERVALS = [
  { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" },
  { value: "quarterly", label: "Quarterly (3 mo)" },
  { value: "biannual", label: "Bi-annual (6 mo)" },
  { value: "annual", label: "Annual (12 mo)" },
];

function computeNextBillingDate(startDate: string, interval: string): string {
  if (!startDate) return "";
  const d = new Date(startDate + "T00:00:00");
  if (interval === "weekly") d.setDate(d.getDate() + 7);
  else if (interval === "monthly") d.setMonth(d.getMonth() + 1);
  else if (interval === "quarterly") d.setMonth(d.getMonth() + 3);
  else if (interval === "biannual") d.setMonth(d.getMonth() + 6);
  else if (interval === "annual") d.setFullYear(d.getFullYear() + 1);
  else d.setMonth(d.getMonth() + 1);
  return d.toISOString().slice(0, 10);
}

function computeExpiryDate(startDate: string, termMonths: string | number): string {
  const months = parseInt(String(termMonths) || "0");
  if (!startDate || !months || months <= 0) return "";
  const d = new Date(startDate + "T00:00:00");
  d.setMonth(d.getMonth() + months);
  return d.toISOString().slice(0, 10);
}

export function SubscriptionsTab() {
  const { user: authUser } = useAuth();
  const isPlatformAdmin = authUser?.role === "platform_admin";
  const { currencies: supportedCurrencies } = useSupportedCurrencies();
  const [subs, setSubs] = useState<any[]>([]);
  const [showImport, setShowImport] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const PER_PAGE = 20;

  // Filter options from backend (single source of truth)
  const [subStatuses, setSubStatuses] = useState<string[]>(SUB_STATUSES_FALLBACK);
  const [paymentMethods, setPaymentMethods] = useState<string[]>(PAYMENT_METHODS_FALLBACK);

  // Filters
  const [emailFilter, setEmailFilter] = useState<string[]>([]);
  const [statusFilter, setStatusFilter] = useState<string[]>([]);
  const [paymentFilter, setPaymentFilter] = useState<string[]>([]);
  const [subNumberFilter, setSubNumberFilter] = useState<string[]>([]);
  const [processorIdFilter, setProcessorIdFilter] = useState<string[]>([]);
  const [planFilter, setPlanFilter] = useState<string[]>([]);
  const [currencyFilter, setCurrencyFilter] = useState<string[]>([]);
  const [amountRange, setAmountRange] = useState<{ min?: string; max?: string; currency?: string }>({});
  const [taxRange, setTaxRange] = useState<{ min?: string; max?: string; currency?: string }>({});
  const [renewalFrom, setRenewalFrom] = useState("");
  const [renewalTo, setRenewalTo] = useState("");
  const [createdFrom, setCreatedFrom] = useState("");
  const [createdTo, setCreatedTo] = useState("");
  const [startFrom, setStartFrom] = useState("");
  const [startTo, setStartTo] = useState("");
  const [contractEndFrom, setContractEndFrom] = useState("");
  const [contractEndTo, setContractEndTo] = useState("");
  const [sortField, setSortField] = useState("created_at");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");

  // Dialogs
  const [selectedSub, setSelectedSub] = useState<any>(null);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [logsUrl, setLogsUrl] = useState("");
  const [showAuditLogs, setShowAuditLogs] = useState(false);
  const [showNotesDialog, setShowNotesDialog] = useState(false);
  const [subNotes, setSubNotes] = useState<any[]>([]);
  const [subNotesJson, setSubNotesJson] = useState<any>(null);
  const [showManualDialog, setShowManualDialog] = useState(false);
  const [products, setProducts] = useState<any[]>([]);
  const today = new Date().toISOString().slice(0, 10);
  const [manualSub, setManualSub] = useState({
    customer_email: "", product_id: "", quantity: 1, amount: 0, currency: "GBP",
    start_date: today,
    billing_interval: "monthly",
    renewal_date: computeNextBillingDate(today, "monthly"),
    status: "active", internal_note: "",
    term_months: "" as string | number,
    auto_cancel_on_termination: false,
    reminder_days: "" as string | number,
  });
  const [confirmCancelId, setConfirmCancelId] = useState<string | null>(null);
  const [confirmRenewId, setConfirmRenewId] = useState<string | null>(null);

  // Customer email lookup (loaded with each page)
  const [customerEmails, setCustomerEmails] = useState<Record<string, string>>({});

  // Customer list for edit dialog typeahead
  const [customers, setCustomers] = useState<any[]>([]);
  const [custUsers, setCustUsers] = useState<any[]>([]);
  const [custSearch, setCustSearch] = useState("");

  const custUserMap: Record<string, any> = {};
  custUsers.forEach(u => { custUserMap[u.id] = u; });
  const filteredCusts = customers.filter(c => {
    const u = custUserMap[c.user_id];
    const q = custSearch.toLowerCase();
    return !q || u?.email?.toLowerCase().includes(q) || c.company_name?.toLowerCase().includes(q);
  }).slice(0, 10);

  const load = useCallback(async (p = 1) => {
    try {
      const params = new URLSearchParams({
        page: String(p), per_page: String(PER_PAGE),
        sort_by: sortField, sort_order: sortOrder,
      });
      if (emailFilter.length > 0) params.append("email", emailFilter.join(","));
      if (statusFilter.length > 0) params.append("status", statusFilter.join(","));
      if (paymentFilter.length > 0) params.append("payment", paymentFilter.join(","));
      if (subNumberFilter.length > 0) params.append("sub_number", subNumberFilter.join(","));
      if (processorIdFilter.length > 0) params.append("processor_id_filter", processorIdFilter.join(","));
      if (planFilter.length > 0) params.append("plan_name_filter", planFilter.join(","));
      if (currencyFilter.length > 0) params.append("currency", currencyFilter.join(","));
      if (amountRange.min) params.append("amount_min", amountRange.min);
      if (amountRange.max) params.append("amount_max", amountRange.max);
      if (amountRange.currency) params.append("amount_currency", amountRange.currency);
      if (taxRange.min) params.append("tax_min", taxRange.min);
      if (taxRange.max) params.append("tax_max", taxRange.max);
      if (taxRange.currency) params.append("tax_currency", taxRange.currency);
      if (renewalFrom) params.append("renewal_from", renewalFrom);
      if (renewalTo) params.append("renewal_to", renewalTo);
      if (createdFrom) params.append("created_from", createdFrom);
      if (createdTo) params.append("created_to", createdTo);
      if (startFrom) params.append("start_from", startFrom);
      if (startTo) params.append("start_to", startTo);
      if (contractEndFrom) params.append("contract_end_from", contractEndFrom);
      if (contractEndTo) params.append("contract_end_to", contractEndTo);
      const [subRes, custRes] = await Promise.all([
        api.get(`/admin/subscriptions?${params}`),
        api.get("/admin/customers?per_page=1000").catch(() => ({ data: { customers: [], users: [] } })),
      ]);
      setSubs(subRes.data.subscriptions || []);
      setTotalPages(subRes.data.total_pages || 1);
      setTotal(subRes.data.total || 0);
      setPage(p);
      // Build customer email map
      const custs: any[] = custRes.data.customers || [];
      const usrs: any[] = custRes.data.users || [];
      const um: Record<string, string> = {};
      usrs.forEach((u: any) => { um[u.id] = u.email || u.full_name || ""; });
      const em: Record<string, string> = {};
      custs.forEach((c: any) => { em[c.id] = um[c.user_id] || c.id; });
      setCustomerEmails(em);
    } catch { toast.error("Failed to load subscriptions"); }
  }, [emailFilter, statusFilter, paymentFilter, subNumberFilter, processorIdFilter, planFilter, currencyFilter, amountRange, taxRange, renewalFrom, renewalTo, createdFrom, createdTo, startFrom, startTo, contractEndFrom, contractEndTo, sortField, sortOrder]);

  // Build unique options for dropdown filters
  const uniqueSubNumbers = subs.map(s => s.subscription_number || s.id?.slice(0, 8)).filter(Boolean);
  const uniqueProcessorIds = subs.map(s => s.processor_id || s.stripe_subscription_id || s.gocardless_mandate_id).filter(Boolean);
  const uniqueEmails = Object.values(customerEmails).filter(Boolean);
  const uniquePlans = Array.from(new Set(subs.map(s => s.plan_name).filter(Boolean)));
  const uniqueCurrencies = Array.from(new Set(subs.map(s => s.currency || "USD")));

  useEffect(() => {
    api.get("/admin/filter-options").then(r => {
      if (r.data.subscription_statuses) setSubStatuses(r.data.subscription_statuses);
      if (r.data.payment_methods) setPaymentMethods(r.data.payment_methods);
    }).catch(() => {});
    load(1);
    api.get("/admin/products-all?per_page=500").then(r => setProducts(r.data.products || [])).catch(() => {});
    api.get("/admin/customers?per_page=1000").then(r => { setCustomers(r.data.customers || []); setCustUsers(r.data.users || []); }).catch(() => {});
  }, [emailFilter, statusFilter, paymentFilter, subNumberFilter, processorIdFilter, planFilter, currencyFilter, amountRange, taxRange, renewalFrom, renewalTo, createdFrom, createdTo, startFrom, startTo, contractEndFrom, contractEndTo, sortField, sortOrder]);

  const sortColHeader = (field: string, label: string, filterType: "text" | "date-range" | "status" | "number-range" | "none", filterProps: any = {}) => (
    <ColHeader
      label={label} colKey={field}
      sortCol={sortField} sortDir={sortOrder}
      onSort={(c, d) => { setSortField(c); setSortOrder(d); }}
      onClearSort={() => { setSortField("created_at"); setSortOrder("desc"); }}
      filterType={filterType}
      {...filterProps}
    />
  );

  const handleEdit = async () => {
    if (!selectedSub) return;
    try {
      await api.put(`/admin/subscriptions/${selectedSub.id}`, {
        renewal_date: selectedSub.renewal_date, start_date: selectedSub.start_date,
        contract_end_date: selectedSub.contract_end_date, amount: selectedSub.amount,
        plan_name: selectedSub.plan_name, customer_id: selectedSub.customer_id,
        status: selectedSub.status, payment_method: selectedSub.payment_method,
        processor_id: selectedSub.processor_id !== undefined ? selectedSub.processor_id : undefined,
        new_note: selectedSub.new_note || undefined,
        term_months: selectedSub.term_months !== undefined ? (Number(selectedSub.term_months) || -1) : undefined,
        auto_cancel_on_termination: selectedSub.auto_cancel_on_termination,
        reminder_days: selectedSub.reminder_days !== undefined && selectedSub.reminder_days !== "" ? (Number(selectedSub.reminder_days) || -1) : -1,
      });
      toast.success("Subscription updated"); setShowEditDialog(false); load(page);
    } catch (e: any) { toast.error(e.response?.data?.detail || "Failed to update"); }
  };

  const handleCancel = async (subId: string) => {
    try { await api.post(`/admin/subscriptions/${subId}/cancel`); toast.success("Cancellation scheduled"); load(page); }
    catch (e: any) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const handleRenew = async (subId: string) => {
    try { await api.post(`/admin/subscriptions/${subId}/renew-now`); toast.success("Renewal order created"); load(page); }
    catch (e: any) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const handleCreateManual = async () => {
    try {
      const payload = {
        ...manualSub,
        term_months: manualSub.term_months ? parseInt(String(manualSub.term_months)) : null,
        reminder_days: manualSub.reminder_days !== "" ? parseInt(String(manualSub.reminder_days)) : null,
      };
      await api.post("/admin/subscriptions/manual", payload);
      toast.success("Subscription created");
      setShowManualDialog(false);
      load(1);
    }
    catch (e: any) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const clearFilters = () => {
    setEmailFilter([]); setStatusFilter([]); setPaymentFilter([]);
    setSubNumberFilter([]); setProcessorIdFilter([]); setPlanFilter([]);
    setCurrencyFilter([]); setAmountRange({}); setTaxRange({});
    setRenewalFrom(""); setRenewalTo("");
    setCreatedFrom(""); setCreatedTo(""); setStartFrom(""); setStartTo(""); setContractEndFrom(""); setContractEndTo("");
  };

  const downloadCsv = () => {
    const token = localStorage.getItem("aa_token");
    const baseUrl = process.env.REACT_APP_BACKEND_URL || "";
    fetch(`${baseUrl}/api/admin/export/subscriptions`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.blob()).then(b => { const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = `subscriptions-${new Date().toISOString().slice(0,10)}.csv`; a.click(); })
      .catch(() => toast.error("Export failed"));
  };

  const statusColor = (s: string) => s === "active" ? "bg-green-100 text-green-700" : s === "unpaid" ? "bg-red-100 text-red-700" : s.includes("cancel") ? "bg-slate-100 text-slate-500" : "bg-amber-100 text-amber-700";

  return (
    <div className="space-y-4" data-testid="subscriptions-tab">
      <AdminPageHeader
        title="Subscriptions"
        subtitle={`${total} records`}
        actions={
          <>
            <Button size="sm" variant="outline" onClick={downloadCsv} data-testid="admin-subs-export-csv"><Download size={14} className="mr-1" />Export CSV</Button>
            <Button size="sm" variant="outline" onClick={() => setShowImport(true)} data-testid="admin-subs-import-csv"><Upload size={14} className="mr-1" />Import CSV</Button>
            <Button size="sm" onClick={() => setShowManualDialog(true)} data-testid="admin-create-sub-btn">Create Manual</Button>
          </>
        }
      />

      {/* Stats Dashboard */}
      <SubscriptionsStats />

      {/* Filters removed — use column headers */}

      {/* Table */}
      <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
        <Table className="min-w-[900px] text-sm" data-testid="admin-subs-table">
          <TableHeader>
            <TableRow className="bg-slate-50">
              {sortColHeader("created_at", "Created", "date-range", { filterValue: { from: createdFrom, to: createdTo }, onFilter: (v: any) => { setCreatedFrom(v.from || ""); setCreatedTo(v.to || ""); }, onClearFilter: () => { setCreatedFrom(""); setCreatedTo(""); } })}
              <ColHeader label="Sub #" colKey="sub_number" sortCol={sortField} sortDir={sortOrder} onSort={(c, d) => { setSortField(c); setSortOrder(d); }} onClearSort={() => { setSortField("created_at"); setSortOrder("desc"); }} filterType="dropdown" filterValue={subNumberFilter} onFilter={setSubNumberFilter} onClearFilter={() => setSubNumberFilter([])} statusOptions={uniqueSubNumbers.map(s => [s, s] as [string, string])} />
              <ColHeader label="Processor ID" colKey="processor_id" sortCol={sortField} sortDir={sortOrder} onSort={(c, d) => { setSortField(c); setSortOrder(d); }} onClearSort={() => { setSortField("created_at"); setSortOrder("desc"); }} filterType="dropdown" filterValue={processorIdFilter} onFilter={setProcessorIdFilter} onClearFilter={() => setProcessorIdFilter([])} statusOptions={uniqueProcessorIds.map(s => [s, s.slice(0, 14) + "…"] as [string, string])} />
              <ColHeader label="Customer Email" colKey="email" sortCol={sortField} sortDir={sortOrder} onSort={(c, d) => { setSortField(c); setSortOrder(d); }} onClearSort={() => { setSortField("created_at"); setSortOrder("desc"); }} filterType="dropdown" filterValue={emailFilter} onFilter={setEmailFilter} onClearFilter={() => setEmailFilter([])} statusOptions={uniqueEmails.map(e => [e, e] as [string, string])} />
              <ColHeader label="Plan" colKey="plan" sortCol={sortField} sortDir={sortOrder} onSort={(c, d) => { setSortField(c); setSortOrder(d); }} onClearSort={() => { setSortField("created_at"); setSortOrder("desc"); }} filterType="dropdown" filterValue={planFilter} onFilter={setPlanFilter} onClearFilter={() => setPlanFilter([])} statusOptions={uniquePlans.map(p => [p, p] as [string, string])} />
              <ColHeader label="Amount" colKey="amount" sortCol={sortField} sortDir={sortOrder} onSort={(c, d) => { setSortField(c); setSortOrder(d); }} onClearSort={() => { setSortField("created_at"); setSortOrder("desc"); }} filterType="number-range" filterValue={amountRange} onFilter={setAmountRange} onClearFilter={() => setAmountRange({})} currencyOptions={supportedCurrencies.map(c => [c, c] as [string, string])} />
              <ColHeader label="Tax" colKey="tax" sortCol={sortField} sortDir={sortOrder} onSort={(c, d) => { setSortField(c); setSortOrder(d); }} onClearSort={() => { setSortField("created_at"); setSortOrder("desc"); }} filterType="number-range" filterValue={taxRange} onFilter={setTaxRange} onClearFilter={() => setTaxRange({})} currencyOptions={supportedCurrencies.map(c => [c, c] as [string, string])} />
              <ColHeader label="Currency" colKey="currency" sortCol={sortField} sortDir={sortOrder} onSort={(c, d) => { setSortField(c); setSortOrder(d); }} onClearSort={() => { setSortField("created_at"); setSortOrder("desc"); }} filterType="dropdown" filterValue={currencyFilter} onFilter={setCurrencyFilter} onClearFilter={() => setCurrencyFilter([])} statusOptions={uniqueCurrencies.map(c => [c, c] as [string, string])} />
              {sortColHeader("renewal_date", "Renewal", "date-range", { filterValue: { from: renewalFrom, to: renewalTo }, onFilter: (v: any) => { setRenewalFrom(v.from || ""); setRenewalTo(v.to || ""); }, onClearFilter: () => { setRenewalFrom(""); setRenewalTo(""); } })}
              {sortColHeader("start_date", "Start", "date-range", { filterValue: { from: startFrom, to: startTo }, onFilter: (v: any) => { setStartFrom(v.from || ""); setStartTo(v.to || ""); }, onClearFilter: () => { setStartFrom(""); setStartTo(""); } })}
              {sortColHeader("contract_end_date", "Contract End", "date-range", { filterValue: { from: contractEndFrom, to: contractEndTo }, onFilter: (v: any) => { setContractEndFrom(v.from || ""); setContractEndTo(v.to || ""); }, onClearFilter: () => { setContractEndFrom(""); setContractEndTo(""); } })}
              <ColHeader label="Payment" colKey="payment" sortCol={sortField} sortDir={sortOrder} onSort={(c, d) => { setSortField(c); setSortOrder(d); }} onClearSort={() => { setSortField("created_at"); setSortOrder("desc"); }} filterType="dropdown" filterValue={paymentFilter} onFilter={setPaymentFilter} onClearFilter={() => setPaymentFilter([])} statusOptions={paymentMethods.map(m => [m, m] as [string, string])} />
              <ColHeader label="Status" colKey="status" sortCol={sortField} sortDir={sortOrder} onSort={(c, d) => { setSortField(c); setSortOrder(d); }} onClearSort={() => { setSortField("created_at"); setSortOrder("desc"); }} filterType="dropdown" filterValue={statusFilter} onFilter={setStatusFilter} onClearFilter={() => setStatusFilter([])} statusOptions={subStatuses.map(s => [s, s] as [string, string])} />
              {isPlatformAdmin && <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500">Partner</th>}
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500">Actions</th>
            </TableRow>
          </TableHeader>
          <TableBody>
            {subs.map((sub) => (
              <TableRow key={sub.id} data-testid={`admin-sub-row-${sub.id}`}>
                <TableCell className="whitespace-nowrap">{sub.created_at?.slice(0, 10)}</TableCell>
                <TableCell className="font-mono">{sub.subscription_number || sub.id?.slice(0, 8)}</TableCell>
                <TableCell className="font-mono text-[10px]" data-testid={`admin-sub-processor-${sub.id}`}>
                  {(() => {
                    const pid = sub.processor_id || sub.stripe_subscription_id || sub.gocardless_mandate_id;
                    if (!pid) return "—";
                    const link = getProcessorLink(pid);
                    return link ? (
                      <a href={link} target="_blank" rel="noopener noreferrer" title={pid} className="inline-flex items-center gap-0.5 px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded hover:bg-blue-100 transition-colors">
                        {pid.slice(0, 14)}… <ExternalLink size={10} />
                      </a>
                    ) : (
                      <span title={pid} className="px-1.5 py-0.5 bg-slate-100 rounded">{pid.slice(0, 14)}…</span>
                    );
                  })()}
                </TableCell>
                <TableCell className="max-w-[160px] truncate">{customerEmails[sub.customer_id] || sub.customer_id?.slice(0, 8)}</TableCell>
                <TableCell className="max-w-[120px] truncate">{sub.plan_name || "—"}</TableCell>
                <TableCell>{sub.currency || "USD"} {sub.amount?.toFixed(2)}</TableCell>
                <TableCell>
                  {sub.tax_amount > 0 ? (
                    <span className="px-1.5 py-0.5 rounded text-[10px] bg-blue-50 text-blue-700" title={sub.tax_name || "Tax"}>
                      {sub.currency || "USD"} {sub.tax_amount?.toFixed(2)}
                    </span>
                  ) : <span className="text-slate-300 text-xs">—</span>}
                </TableCell>
                <TableCell><span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">{sub.currency || "USD"}</span></TableCell>
                <TableCell className="whitespace-nowrap">{sub.renewal_date?.slice(0, 10) || "—"}</TableCell>
                <TableCell className="whitespace-nowrap">{sub.start_date?.slice(0, 10) || "—"}</TableCell>
                <TableCell className="whitespace-nowrap">{sub.contract_end_date?.slice(0, 10) || "—"}</TableCell>
                <TableCell><span className="px-1.5 py-0.5 rounded text-[10px] bg-blue-100 text-blue-700">{sub.payment_method || "—"}</span></TableCell>
                <TableCell><span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${statusColor(sub.status)}`}>{sub.status}</span></TableCell>
                {isPlatformAdmin && <TableCell className="text-xs text-slate-500" data-testid={`admin-sub-partner-${sub.id}`}>{sub.partner_code || "—"}</TableCell>}
                <TableCell>
                  <div className="flex gap-1 flex-nowrap">
                    <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px]" onClick={() => { setLogsUrl(`/admin/subscriptions/${sub.id}/logs`); setShowAuditLogs(true); }} data-testid={`admin-subs-logs-${sub.id}`}>Logs</Button>
                    <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px]" onClick={() => { setSubNotes(sub.notes || []); setSubNotesJson(sub.notes_json || null); setShowNotesDialog(true); }}>Notes</Button>
                    <Button variant="outline" size="sm" className="h-6 px-2 text-[11px]" onClick={() => { setSelectedSub(sub); setShowEditDialog(true); }} data-testid={`admin-sub-edit-${sub.id}`}>Edit</Button>
                    <Button variant="outline" size="sm" className="h-6 px-2 text-[11px]" onClick={() => setConfirmRenewId(sub.id)}>Renew</Button>
                    {sub.status === "active" && <Button variant="destructive" size="sm" className="h-6 px-2 text-[11px]" onClick={() => setConfirmCancelId(sub.id)}>Cancel</Button>}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <AdminPagination page={page} totalPages={totalPages} total={total} perPage={PER_PAGE} onPage={(p) => load(p)} />

      {/* Edit Dialog */}
      <Dialog open={showEditDialog} onOpenChange={(open) => { setShowEditDialog(open); if (!open) { setSelectedSub(null); setCustSearch(""); } }}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="admin-sub-edit-dialog">
          <DialogHeader><DialogTitle>Edit Subscription</DialogTitle></DialogHeader>
          {selectedSub && (
            <div className="space-y-3 py-2">
              {/* Customer selector */}
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-600 uppercase tracking-wide">Customer (search by email)</label>
                <Input placeholder="Type email to search…" value={custSearch} onChange={e => setCustSearch(e.target.value)} className="h-9" data-testid="admin-sub-customer-search" />
                {custSearch && filteredCusts.length > 0 && (
                  <div className="border border-slate-200 rounded bg-white shadow-md max-h-36 overflow-y-auto">
                    {filteredCusts.map((c: any) => {
                      const u = custUserMap[c.user_id];
                      return <div key={c.id} onClick={() => { setSelectedSub({ ...selectedSub, customer_id: c.id }); setCustSearch(u?.email || ""); }} className="px-3 py-2 hover:bg-slate-50 cursor-pointer text-sm">{u?.email} {c.company_name ? `— ${c.company_name}` : ""}</div>;
                    })}
                  </div>
                )}
                {selectedSub.customer_id && (
                  <p className="text-xs text-green-600">Current: {customerEmails[selectedSub.customer_id] || selectedSub.customer_id?.slice(0, 8)}</p>
                )}
              </div>
              <div className="grid grid-cols-2 gap-3">
                {[["Renewal Date", "renewal_date", "date"], ["Start Date", "start_date", "date"], ["Contract End", "contract_end_date", "date"]].map(([label, key, type]) => (
                  <div key={key as string} className="space-y-1">
                    <label className="text-xs font-medium text-slate-600 uppercase tracking-wide">{label as string}</label>
                    <Input type={type as string} value={(selectedSub[key as string] || "").slice(0, 10)} onChange={e => setSelectedSub({ ...selectedSub, [key as string]: e.target.value })} />
                  </div>
                ))}
                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-600 uppercase tracking-wide">Amount ($)</label>
                  <Input type="number" step="0.01" value={selectedSub.amount ?? ""} onChange={e => setSelectedSub({ ...selectedSub, amount: parseFloat(e.target.value) || 0 })} />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-600 uppercase tracking-wide">Plan Name</label>
                  <Input value={selectedSub.plan_name || ""} onChange={e => setSelectedSub({ ...selectedSub, plan_name: e.target.value })} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-600 uppercase tracking-wide">Status</label>
                  <Select value={selectedSub.status} onValueChange={v => setSelectedSub({ ...selectedSub, status: v })} data-testid="admin-sub-status-select">
                    <SelectTrigger className="w-full bg-white"><SelectValue /></SelectTrigger>
                    <SelectContent>{subStatuses.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-600 uppercase tracking-wide">Payment Method</label>
                  <Select value={selectedSub.payment_method} onValueChange={v => setSelectedSub({ ...selectedSub, payment_method: v })} data-testid="admin-sub-payment-select">
                    <SelectTrigger className="w-full bg-white"><SelectValue /></SelectTrigger>
                    <SelectContent>{paymentMethods.map(m => <SelectItem key={m} value={m}>{m}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
              </div>
              {/* Processor ID */}
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-600 uppercase tracking-wide">Processor ID</label>
                <div className="flex items-center gap-1">
                  <Input value={selectedSub.processor_id || ""} onChange={e => setSelectedSub({ ...selectedSub, processor_id: e.target.value })} placeholder="e.g. sub_xxx or PM01xxx or MD01xxx" data-testid="admin-sub-processor-input" className="flex-1" />
                  {selectedSub.processor_id && getProcessorLink(selectedSub.processor_id) && (
                    <a href={getProcessorLink(selectedSub.processor_id)!} target="_blank" rel="noopener noreferrer" className="flex items-center justify-center h-9 w-9 border border-slate-200 rounded hover:bg-slate-50 transition-colors" title="Open in payment dashboard">
                      <ExternalLink size={14} className="text-blue-600" />
                    </a>
                  )}
                </div>
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-600 uppercase tracking-wide">Add Note</label>
                <Textarea placeholder="Add a note…" value={selectedSub.new_note || ""} onChange={e => setSelectedSub({ ...selectedSub, new_note: e.target.value })} rows={2} />
              </div>
              {/* Term fields */}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-600 uppercase tracking-wide">Contract Term (months)</label>
                  <Input type="number" min={0} max={999} placeholder="0 = cancel anytime" value={selectedSub.term_months ?? ""} onChange={e => setSelectedSub({ ...selectedSub, term_months: e.target.value })} data-testid="edit-sub-term-months" />
                </div>
                <div className="flex items-center gap-2 pt-5">
                  <input type="checkbox" id="edit_auto_cancel" checked={!!selectedSub.auto_cancel_on_termination} onChange={e => setSelectedSub({ ...selectedSub, auto_cancel_on_termination: e.target.checked })} />
                  <label htmlFor="edit_auto_cancel" className="text-xs text-slate-600">Auto-cancel on term end</label>
                </div>
              </div>
              {/* Reminder days */}
              <div className="space-y-1">
                <div className="flex items-center gap-1.5">
                  <label className="text-xs font-medium text-slate-600 uppercase tracking-wide">Renewal Reminder (days before)</label>
                  <span className="group relative cursor-help">
                    <span className="text-slate-400 text-xs border border-slate-300 rounded-full w-4 h-4 inline-flex items-center justify-center">?</span>
                    <span className="absolute left-5 top-0 z-10 hidden group-hover:block w-64 rounded bg-slate-800 text-white text-xs px-2.5 py-2 shadow-lg">
                      Number of days before renewal to send a reminder email. Leave blank to disable renewal notifications for this subscription.
                    </span>
                  </span>
                </div>
                <Input type="number" min={1} max={365} placeholder="blank = no reminders" value={selectedSub.reminder_days ?? ""} onChange={e => setSelectedSub({ ...selectedSub, reminder_days: e.target.value })} data-testid="edit-sub-reminder-days" />
              </div>
              <div className="flex gap-2">
                <Button onClick={handleEdit} className="flex-1" data-testid="admin-sub-edit-save">Save Changes</Button>
                <TestReminderButton subId={selectedSub.id} endpoint="subscriptions" />
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Logs Dialog */}
      <AuditLogDialog open={showAuditLogs} onOpenChange={setShowAuditLogs} title="Subscription Audit Logs" logsUrl={logsUrl} />

      {/* Cancel Confirmation */}
      <AlertDialog open={!!confirmCancelId} onOpenChange={(open) => !open && setConfirmCancelId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancel Subscription</AlertDialogTitle>
            <AlertDialogDescription>Are you sure you want to cancel this subscription? This will schedule a cancellation at the end of the billing period.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep Active</AlertDialogCancel>
            <AlertDialogAction className="bg-red-600 hover:bg-red-700" onClick={() => { handleCancel(confirmCancelId!); setConfirmCancelId(null); }} data-testid="confirm-cancel-sub">
              Yes, Cancel
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Renew Confirmation */}
      <AlertDialog open={!!confirmRenewId} onOpenChange={(open) => !open && setConfirmRenewId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Renew Subscription</AlertDialogTitle>
            <AlertDialogDescription>Are you sure you want to manually renew this subscription now? A new renewal order will be created immediately.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => { handleRenew(confirmRenewId!); setConfirmRenewId(null); }} data-testid="confirm-renew-sub">
              Yes, Renew Now
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Notes Dialog */}
      <Dialog open={showNotesDialog} onOpenChange={setShowNotesDialog}>
        <DialogContent className="max-w-2xl"><DialogHeader><DialogTitle>Subscription Notes</DialogTitle></DialogHeader>
          <div className="space-y-3 max-h-80 overflow-y-auto">
            {subNotesJson && <div><p className="text-xs font-medium text-slate-600 mb-1">Intake Data</p><pre className="text-xs bg-slate-50 rounded p-2 overflow-x-auto">{JSON.stringify(subNotesJson, null, 2)}</pre></div>}
            {subNotes.map((n: any, i: number) => <div key={i} className="text-xs bg-slate-50 rounded p-2">{n}</div>)}
          </div>
        </DialogContent>
      </Dialog>

      {/* Manual Create Dialog */}
      <Dialog open={showManualDialog} onOpenChange={setShowManualDialog}>
        <DialogContent><DialogHeader><DialogTitle>Create Manual Subscription</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-xs text-slate-500">Customer Email</label>
              <input
                list="manual-sub-customers"
                placeholder="customer@example.com"
                value={manualSub.customer_email}
                onChange={e => setManualSub({ ...manualSub, customer_email: e.target.value })}
                className="w-full h-9 text-sm border border-slate-200 rounded px-3 bg-white"
                data-testid="manual-sub-customer-email"
              />
              <datalist id="manual-sub-customers">
                {custUsers.map((u: any) => (
                  <option key={u.id} value={u.email}>{u.full_name ? `${u.full_name} (${u.email})` : u.email}</option>
                ))}
              </datalist>
            </div>
            <div className="space-y-1"><label className="text-xs text-slate-500">Product</label>
              <SearchableSelect
                value={manualSub.product_id || undefined}
                onValueChange={v => {
                  const p = products.find((p: any) => p.id === v);
                  setManualSub({ ...manualSub, product_id: v, currency: p?.currency || "GBP", term_months: p?.default_term_months ? String(p.default_term_months) : "", billing_interval: p?.billing_interval || manualSub.billing_interval, renewal_date: computeNextBillingDate(manualSub.start_date, p?.billing_interval || manualSub.billing_interval) });
                }}
                options={products.map((p: any) => ({ value: p.id, label: p.name }))}
                placeholder="Select product"
                searchPlaceholder="Search products..."
                data-testid="manual-sub-product-select"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Start Date</label>
                <Input type="date" value={manualSub.start_date}
                  onChange={e => setManualSub({ ...manualSub, start_date: e.target.value, renewal_date: computeNextBillingDate(e.target.value, manualSub.billing_interval) })}
                  data-testid="manual-sub-start-date" />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Billing Interval</label>
                <Select value={manualSub.billing_interval} onValueChange={v => setManualSub({ ...manualSub, billing_interval: v, renewal_date: computeNextBillingDate(manualSub.start_date, v) })}>
                  <SelectTrigger data-testid="manual-sub-billing-interval"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {BILLING_INTERVALS.map(b => <SelectItem key={b.value} value={b.value}>{b.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1"><label className="text-xs text-slate-500">Amount</label><Input type="number" step="0.01" value={manualSub.amount} onChange={e => setManualSub({ ...manualSub, amount: parseFloat(e.target.value) || 0 })} /></div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Currency</label>
                <Select value={manualSub.currency} onValueChange={v => setManualSub({ ...manualSub, currency: v })}>
                  <SelectTrigger className="w-full bg-white" data-testid="manual-sub-currency-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {(supportedCurrencies.length ? supportedCurrencies : ISO_CURRENCIES).map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Next Billing Date</label>
                <Input type="date" value={manualSub.renewal_date}
                  onChange={e => setManualSub({ ...manualSub, renewal_date: e.target.value })}
                  data-testid="manual-sub-renewal-date" />
                <p className="text-[10px] text-slate-400">Auto-computed from start date + interval</p>
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Contract Term (months)</label>
                <Input type="number" min={0} max={999} placeholder="0 = cancel anytime" value={manualSub.term_months as string}
                  onChange={e => setManualSub({ ...manualSub, term_months: e.target.value })}
                  data-testid="manual-sub-term-months" />
                {computeExpiryDate(manualSub.start_date, manualSub.term_months) && (
                  <p className="text-[10px] text-slate-400">Expires: {computeExpiryDate(manualSub.start_date, manualSub.term_months)}</p>
                )}
              </div>
              <div className="flex items-center gap-2 pt-4">
                <input type="checkbox" id="auto_cancel" checked={manualSub.auto_cancel_on_termination} onChange={e => setManualSub({ ...manualSub, auto_cancel_on_termination: e.target.checked })} />
                <label htmlFor="auto_cancel" className="text-xs text-slate-600">Auto-cancel on term end</label>
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-1.5">
                  <label className="text-xs text-slate-500">Renewal Reminder (days before)</label>
                  <span className="group relative cursor-help">
                    <span className="text-slate-400 text-xs border border-slate-300 rounded-full w-4 h-4 inline-flex items-center justify-center">?</span>
                    <span className="absolute left-5 top-0 z-10 hidden group-hover:block w-64 rounded bg-slate-800 text-white text-xs px-2.5 py-2 shadow-lg">
                      Number of days before renewal to send a reminder email. Leave blank to disable renewal notifications for this subscription.
                    </span>
                  </span>
                </div>
                <Input type="number" min={1} max={365} placeholder="blank = no reminders" value={manualSub.reminder_days as string} onChange={e => setManualSub({ ...manualSub, reminder_days: e.target.value })} data-testid="manual-sub-reminder-days" />
              </div>
            </div>
            <Button onClick={handleCreateManual} className="w-full">Create Subscription</Button>
          </div>
        </DialogContent>
      </Dialog>
      <ImportModal
        entity="subscriptions"
        entityLabel="Subscriptions"
        open={showImport}
        onClose={() => setShowImport(false)}
        onSuccess={load}
      />
    </div>
  );
}
