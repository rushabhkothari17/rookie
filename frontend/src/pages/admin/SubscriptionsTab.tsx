import { useCallback, useEffect, useState } from "react";
import { ImportModal } from "@/components/admin/ImportModal";
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
import { Download, ExternalLink, Upload} from "lucide-react";

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

export function SubscriptionsTab() {
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
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState("");
  const [payment, setPayment] = useState("");
  const [subNumberFilter, setSubNumberFilter] = useState("");
  const [processorIdFilter, setProcessorIdFilter] = useState("");
  const [planFilter, setPlanFilter] = useState("");
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
  const [subLogs, setSubLogs] = useState<any[]>([]);
  const [showLogsDialog, setShowLogsDialog] = useState(false);
  const [showNotesDialog, setShowNotesDialog] = useState(false);
  const [subNotes, setSubNotes] = useState<any[]>([]);
  const [subNotesJson, setSubNotesJson] = useState<any>(null);
  const [showManualDialog, setShowManualDialog] = useState(false);
  const [products, setProducts] = useState<any[]>([]);
  const [manualSub, setManualSub] = useState({ customer_email: "", product_id: "", quantity: 1, amount: 0, renewal_date: "", status: "active", internal_note: "" });

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
      if (email) params.append("email", email);
      if (status) params.append("status", status);
      if (payment) params.append("payment", payment);
      if (subNumberFilter) params.append("sub_number", subNumberFilter);
      if (processorIdFilter) params.append("processor_id_filter", processorIdFilter);
      if (planFilter) params.append("plan_name_filter", planFilter);
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
  }, [email, status, payment, subNumberFilter, processorIdFilter, planFilter, renewalFrom, renewalTo, createdFrom, createdTo, startFrom, startTo, contractEndFrom, contractEndTo, sortField, sortOrder]);

  useEffect(() => {
    api.get("/admin/filter-options").then(r => {
      if (r.data.subscription_statuses) setSubStatuses(r.data.subscription_statuses);
      if (r.data.payment_methods) setPaymentMethods(r.data.payment_methods);
    }).catch(() => {});
    load(1);
    api.get("/admin/products-all?per_page=500").then(r => setProducts(r.data.products || [])).catch(() => {});
    api.get("/admin/customers?per_page=1000").then(r => { setCustomers(r.data.customers || []); setCustUsers(r.data.users || []); }).catch(() => {});
  }, [email, status, payment, subNumberFilter, processorIdFilter, planFilter, renewalFrom, renewalTo, createdFrom, createdTo, startFrom, startTo, contractEndFrom, contractEndTo, sortField, sortOrder]);

  const sortHeader = (field: string, label: string) => (
    <TableHead className="cursor-pointer select-none whitespace-nowrap" onClick={() => { if (sortField === field) setSortOrder(o => o === "desc" ? "asc" : "desc"); else { setSortField(field); setSortOrder("desc"); } }}>
      {label} {sortField === field ? (sortOrder === "desc" ? "↓" : "↑") : ""}
    </TableHead>
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
      });
      toast.success("Subscription updated"); setShowEditDialog(false); load(page);
    } catch (e: any) { toast.error(e.response?.data?.detail || "Failed to update"); }
  };

  const handleCancel = async (subId: string) => {
    if (!confirm("Cancel this subscription?")) return;
    try { await api.post(`/admin/subscriptions/${subId}/cancel`); toast.success("Cancellation scheduled"); load(page); }
    catch (e: any) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const handleRenew = async (subId: string) => {
    try { await api.post(`/admin/subscriptions/${subId}/renew-now`); toast.success("Renewal order created"); load(page); }
    catch (e: any) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const handleCreateManual = async () => {
    try { await api.post("/admin/subscriptions/manual", manualSub); toast.success("Subscription created"); setShowManualDialog(false); load(1); }
    catch (e: any) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const clearFilters = () => {
    setEmail(""); setStatus(""); setPayment("");
    setSubNumberFilter(""); setProcessorIdFilter(""); setPlanFilter("");
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

      {/* Filters */}
      <div className="rounded-xl border border-slate-200 bg-white p-3">
        <div className="flex flex-wrap gap-2 items-end">
          <Input placeholder="Customer email" value={email} onChange={e => setEmail(e.target.value)} className="h-8 text-xs w-44" data-testid="admin-sub-filter-email" />
          <Input placeholder="Sub # (SUB-...)" value={subNumberFilter} onChange={e => setSubNumberFilter(e.target.value)} className="h-8 text-xs w-32" data-testid="admin-sub-filter-sub-number" />
          <Input placeholder="Processor ID" value={processorIdFilter} onChange={e => setProcessorIdFilter(e.target.value)} className="h-8 text-xs w-32" data-testid="admin-sub-filter-processor-id" />
          <Input placeholder="Plan name" value={planFilter} onChange={e => setPlanFilter(e.target.value)} className="h-8 text-xs w-36" data-testid="admin-sub-filter-plan" />
          <select value={status} onChange={e => setStatus(e.target.value)} className="h-8 text-xs border border-slate-200 rounded px-2 bg-white" data-testid="admin-sub-filter-status">
            <option value="">All Statuses</option>
            {subStatuses.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <select value={payment} onChange={e => setPayment(e.target.value)} className="h-8 text-xs border border-slate-200 rounded px-2 bg-white" data-testid="admin-sub-filter-payment">
            <option value="">All Methods</option>
            {paymentMethods.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
          <div className="flex items-center gap-1">
            <span className="text-xs text-slate-400">Renewal</span>
            <Input type="date" value={renewalFrom} onChange={e => setRenewalFrom(e.target.value)} className="h-8 text-xs w-32" data-testid="admin-sub-filter-renewal-from" />
            <span className="text-xs text-slate-400">–</span>
            <Input type="date" value={renewalTo} onChange={e => setRenewalTo(e.target.value)} className="h-8 text-xs w-32" data-testid="admin-sub-filter-renewal-to" />
          </div>
          <div className="flex items-center gap-1">
            <span className="text-xs text-slate-400">Created</span>
            <Input type="date" value={createdFrom} onChange={e => setCreatedFrom(e.target.value)} className="h-8 text-xs w-32" />
            <span className="text-xs text-slate-400">–</span>
            <Input type="date" value={createdTo} onChange={e => setCreatedTo(e.target.value)} className="h-8 text-xs w-32" />
          </div>
          <div className="flex items-center gap-1">
            <span className="text-xs text-slate-400">Start</span>
            <Input type="date" value={startFrom} onChange={e => setStartFrom(e.target.value)} className="h-8 text-xs w-32" />
            <span className="text-xs text-slate-400">–</span>
            <Input type="date" value={startTo} onChange={e => setStartTo(e.target.value)} className="h-8 text-xs w-32" />
          </div>
          <div className="flex items-center gap-1">
            <span className="text-xs text-slate-400">Contract End</span>
            <Input type="date" value={contractEndFrom} onChange={e => setContractEndFrom(e.target.value)} className="h-8 text-xs w-32" />
            <span className="text-xs text-slate-400">–</span>
            <Input type="date" value={contractEndTo} onChange={e => setContractEndTo(e.target.value)} className="h-8 text-xs w-32" />
          </div>
          <Button size="sm" variant="outline" onClick={clearFilters} className="h-8 text-xs">Clear</Button>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
        <Table className="min-w-[900px] text-sm" data-testid="admin-subs-table">
          <TableHeader>
            <TableRow className="bg-slate-50">
              {sortHeader("created_at", "Created")}
              <TableHead>Sub #</TableHead>
              <TableHead>Processor ID</TableHead>
              <TableHead>Customer Email</TableHead>
              <TableHead>Plan</TableHead>
              <TableHead>Amount</TableHead>
              {sortHeader("renewal_date", "Renewal")}
              {sortHeader("start_date", "Start")}
              {sortHeader("contract_end_date", "Contract End")}
              <TableHead>Payment</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Actions</TableHead>
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
                <TableCell>${sub.amount?.toFixed(2)}</TableCell>
                <TableCell className="whitespace-nowrap">{sub.renewal_date?.slice(0, 10) || "—"}</TableCell>
                <TableCell className="whitespace-nowrap">{sub.start_date?.slice(0, 10) || "—"}</TableCell>
                <TableCell className="whitespace-nowrap">{sub.contract_end_date?.slice(0, 10) || "—"}</TableCell>
                <TableCell><span className="px-1.5 py-0.5 rounded text-[10px] bg-blue-100 text-blue-700">{sub.payment_method || "—"}</span></TableCell>
                <TableCell><span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${statusColor(sub.status)}`}>{sub.status}</span></TableCell>
                <TableCell>
                  <div className="flex gap-1 flex-nowrap">
                    <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px]" onClick={async () => { const r = await api.get(`/admin/subscriptions/${sub.id}/logs`); setSubLogs(r.data.logs || []); setShowLogsDialog(true); }}>Logs</Button>
                    <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px]" onClick={() => { setSubNotes(sub.notes || []); setSubNotesJson(sub.notes_json || null); setShowNotesDialog(true); }}>Notes</Button>
                    <Button variant="outline" size="sm" className="h-6 px-2 text-[11px]" onClick={() => { setSelectedSub(sub); setShowEditDialog(true); }} data-testid={`admin-sub-edit-${sub.id}`}>Edit</Button>
                    <Button variant="outline" size="sm" className="h-6 px-2 text-[11px]" onClick={() => handleRenew(sub.id)}>Renew</Button>
                    {sub.status === "active" && <Button variant="destructive" size="sm" className="h-6 px-2 text-[11px]" onClick={() => handleCancel(sub.id)}>Cancel</Button>}
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
                  <select value={selectedSub.status} onChange={e => setSelectedSub({ ...selectedSub, status: e.target.value })} className="w-full h-9 text-sm border border-slate-200 rounded px-2" data-testid="admin-sub-status-select">
                    {subStatuses.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-600 uppercase tracking-wide">Payment Method</label>
                  <select value={selectedSub.payment_method} onChange={e => setSelectedSub({ ...selectedSub, payment_method: e.target.value })} className="w-full h-9 text-sm border border-slate-200 rounded px-2" data-testid="admin-sub-payment-select">
                    {paymentMethods.map(m => <option key={m} value={m}>{m}</option>)}
                  </select>
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
              <Button onClick={handleEdit} className="w-full" data-testid="admin-sub-edit-save">Save Changes</Button>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Logs Dialog */}
      <Dialog open={showLogsDialog} onOpenChange={setShowLogsDialog}>
        <DialogContent><DialogHeader><DialogTitle>Subscription Logs</DialogTitle></DialogHeader>
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {subLogs.map((l: any, i: number) => <div key={i} className="text-xs bg-slate-50 rounded p-2"><span className="text-slate-400">{l.timestamp?.slice(0, 10)}</span> {l.action} {l.new_status && `→ ${l.new_status}`}</div>)}
          </div>
        </DialogContent>
      </Dialog>

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
            <div className="space-y-1"><label className="text-xs text-slate-500">Customer Email</label><Input placeholder="customer@example.com" value={manualSub.customer_email} onChange={e => setManualSub({ ...manualSub, customer_email: e.target.value })} /></div>
            <div className="space-y-1"><label className="text-xs text-slate-500">Product</label>
              <select value={manualSub.product_id} onChange={e => setManualSub({ ...manualSub, product_id: e.target.value })} className="w-full h-9 text-sm border border-slate-200 rounded px-2">
                <option value="">Select product</option>
                {products.map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1"><label className="text-xs text-slate-500">Amount</label><Input type="number" step="0.01" value={manualSub.amount} onChange={e => setManualSub({ ...manualSub, amount: parseFloat(e.target.value) || 0 })} /></div>
              <div className="space-y-1"><label className="text-xs text-slate-500">Renewal Date</label><Input type="date" value={manualSub.renewal_date} onChange={e => setManualSub({ ...manualSub, renewal_date: e.target.value })} /></div>
            </div>
            <Button onClick={handleCreateManual} className="w-full">Create Subscription</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
      <ImportModal
        entity="subscriptions"
        entityLabel="Subscriptions"
        open={showImport}
        onClose={() => setShowImport(false)}
        onSuccess={load}
      />
  );
}
