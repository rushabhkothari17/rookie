import { useCallback, useEffect, useMemo, useState } from "react";
import { ImportModal } from "@/components/admin/ImportModal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "@/components/ui/sonner";
import api from "@/lib/api";
import { AdminPageHeader } from "./shared/AdminPageHeader";
import { AdminPagination } from "./shared/AdminPagination";
import { Download } from "lucide-react";
import { useWebsite } from "@/contexts/WebsiteContext";

const DEFAULT_SOURCES = ["manual", "bank_transfer", "stripe", "gocardless"];
const DEFAULT_TYPES = ["payment", "refund", "chargeback", "credit", "debit", "fee"];
const DEFAULT_STATUSES = ["pending", "completed", "matched", "failed", "refunded"];
const EMPTY_FORM = { date: new Date().toISOString().slice(0, 10), source: "manual", transaction_id: "", type: "payment", amount: "", fees: "0", currency: "USD", status: "completed", description: "", linked_order_id: "", internal_notes: "" };

export function BankTransactionsTab() {
  const ws = useWebsite();
  const SOURCES = useMemo(() => ws.bank_transaction_sources ? ws.bank_transaction_sources.split("\n").map(s => s.trim()).filter(Boolean) : DEFAULT_SOURCES, [ws.bank_transaction_sources]);
  const TYPES = useMemo(() => ws.bank_transaction_types ? ws.bank_transaction_types.split("\n").map(s => s.trim()).filter(Boolean) : DEFAULT_TYPES, [ws.bank_transaction_types]);
  const STATUSES = useMemo(() => ws.bank_transaction_statuses ? ws.bank_transaction_statuses.split("\n").map(s => s.trim()).filter(Boolean) : DEFAULT_STATUSES, [ws.bank_transaction_statuses]);
  const [transactions, setTransactions] = useState<any[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const PER_PAGE = 20;
  const [filterSource, setFilterSource] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterType, setFilterType] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editTxn, setEditTxn] = useState<any>(null);
  const [form, setForm] = useState<any>(EMPTY_FORM);
  const [showLogs, setShowLogs] = useState(false);
  const [logsData, setLogsData] = useState<any[]>([]);
  const [logsTitle, setLogsTitle] = useState("");
  const [showNotesModal, setShowNotesModal] = useState(false);
  const [notesContent, setNotesContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [btStatuses, setBtStatuses] = useState<string[]>(STATUSES);

  const load = useCallback(async (p = 1) => {
    const params = new URLSearchParams({ page: String(p), per_page: String(PER_PAGE) });
    if (filterSource) params.set("source", filterSource);
    if (filterStatus) params.set("status", filterStatus);
    if (filterType) params.set("type", filterType);
    if (startDate) params.set("date_from", startDate);
    if (endDate) params.set("date_to", endDate);
    const res = await api.get(`/admin/bank-transactions?${params}`);
    setTransactions(res.data.transactions || []);
    setTotal(res.data.total || 0);
    setTotalPages(res.data.total_pages || 1);
    setPage(p);
  }, [filterSource, filterStatus, filterType, startDate, endDate]);

  useEffect(() => {
    api.get("/admin/filter-options").then(r => {
      if (r.data.bank_transaction_statuses) setBtStatuses(r.data.bank_transaction_statuses);
    }).catch(() => {});
    load(1);
  }, [filterSource, filterStatus, filterType, startDate, endDate]);

  const openCreate = () => { setEditTxn(null); setForm(EMPTY_FORM); setShowForm(true); };
  const openEdit = (txn: any) => { setEditTxn(txn); setForm({ date: txn.date || "", source: txn.source || "manual", transaction_id: txn.transaction_id || "", type: txn.type || "payment", amount: String(txn.amount || ""), fees: String(txn.fees || "0"), currency: txn.currency || "USD", status: txn.status || "completed", description: txn.description || "", linked_order_id: txn.linked_order_id || "", internal_notes: txn.internal_notes || "" }); setShowForm(true); };

  const handleSave = async () => {
    if (!form.date || !form.amount) { toast.error("Date and amount are required"); return; }
    setSaving(true);
    try {
      const payload = { ...form, amount: parseFloat(form.amount), fees: parseFloat(form.fees || "0") };
      if (editTxn) { await api.put(`/admin/bank-transactions/${editTxn.id}`, payload); toast.success("Transaction updated"); }
      else { await api.post("/admin/bank-transactions", payload); toast.success("Transaction created"); }
      setShowForm(false); load(page);
    } catch (e: any) { toast.error(e.response?.data?.detail || "Save failed"); }
    finally { setSaving(false); }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this transaction?")) return;
    await api.delete(`/admin/bank-transactions/${id}`);
    toast.success("Deleted"); load(page);
  };

  const openLogs = async (txn: any) => {
    const res = await api.get(`/admin/bank-transactions/${txn.id}/logs`);
    setLogsData(res.data.logs || []); setLogsTitle(`Logs: ${txn.description || txn.id.slice(0, 8)}`); setShowLogs(true);
  };

  const openNotes = (txn: any) => { setNotesContent(txn.internal_notes || "No notes"); setShowNotesModal(true); };

  const clearFilters = () => { setFilterSource(""); setFilterStatus(""); setFilterType(""); setStartDate(""); setEndDate(""); };

  const downloadCsv = () => {
    const token = localStorage.getItem("aa_token");
    const base = process.env.REACT_APP_BACKEND_URL || "";
    const params = new URLSearchParams();
    if (filterSource) params.set("source", filterSource);
    if (filterStatus) params.set("status", filterStatus);
    if (filterType) params.set("type", filterType);
    fetch(`${base}/api/admin/export/bank-transactions?${params}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.blob()).then(b => { const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = `bank-transactions-${new Date().toISOString().slice(0, 10)}.csv`; a.click(); })
      .catch(() => toast.error("Export failed"));
  };

  const net = (txn: any) => (txn.net_amount ?? (txn.amount - (txn.fees || 0))).toFixed(2);
  const statusBadge = (s: string) => {
    const m: Record<string, string> = { completed: "bg-green-100 text-green-700", pending: "bg-yellow-100 text-yellow-700", failed: "bg-red-100 text-red-700", refunded: "bg-slate-100 text-slate-600" };
    return m[s] || "bg-slate-100 text-slate-600";
  };

  return (
    <div className="space-y-4" data-testid="bank-transactions-tab">
      <AdminPageHeader title="Bank Transactions" subtitle={`${total} records`} actions={
        <>
          <Button size="sm" variant="outline" onClick={downloadCsv} data-testid="bt-export"><Download size={14} className="mr-1" />Export CSV</Button>
          <Button size="sm" onClick={openCreate} data-testid="bt-add">+ Add Transaction</Button>
        </>
      } />

      {/* Filters */}
      <div className="rounded-xl border border-slate-200 bg-white p-3">
        <div className="flex flex-wrap gap-2 items-end">
          <Select value={filterSource || "__all__"} onValueChange={v => setFilterSource(v === "__all__" ? "" : v)}>
            <SelectTrigger className="w-32 h-8 text-xs" data-testid="bt-filter-source"><SelectValue placeholder="Source" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All Sources</SelectItem>
              {SOURCES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={filterStatus || "__all__"} onValueChange={v => setFilterStatus(v === "__all__" ? "" : v)}>
            <SelectTrigger className="w-32 h-8 text-xs" data-testid="bt-filter-status"><SelectValue placeholder="Status" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All Statuses</SelectItem>
              {btStatuses.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={filterType || "__all__"} onValueChange={v => setFilterType(v === "__all__" ? "" : v)}>
            <SelectTrigger className="w-32 h-8 text-xs" data-testid="bt-filter-type"><SelectValue placeholder="Type" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All Types</SelectItem>
              {TYPES.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}
            </SelectContent>
          </Select>
          <div className="flex items-center gap-1">
            <span className="text-xs text-slate-400">From</span>
            <Input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} className="h-8 text-xs w-32" data-testid="bt-start-date" />
            <span className="text-xs text-slate-400">–</span>
            <Input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} className="h-8 text-xs w-32" data-testid="bt-end-date" />
          </div>
          <Button size="sm" variant="outline" onClick={clearFilters} className="h-8 text-xs" data-testid="bt-clear-filters">Clear</Button>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-200 bg-white overflow-auto">
        <Table data-testid="bt-table" className="min-w-[900px]">
          <TableHeader>
            <TableRow className="bg-slate-50">
              <TableHead>Date</TableHead>
              <TableHead>Source</TableHead>
              <TableHead>Txn ID</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Amount</TableHead>
              <TableHead>Fees</TableHead>
              <TableHead>Net</TableHead>
              <TableHead>Currency</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Description</TableHead>
              <TableHead>Linked Order</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {transactions.length === 0 && <TableRow><TableCell colSpan={12} className="text-center text-slate-400 py-8">No transactions found</TableCell></TableRow>}
            {transactions.map(txn => (
              <TableRow key={txn.id} data-testid={`bt-row-${txn.id}`}>
                <TableCell className="font-mono whitespace-nowrap">{txn.date}</TableCell>
                <TableCell className="capitalize">{txn.source}</TableCell>
                <TableCell className="font-mono max-w-[100px] truncate">{txn.transaction_id || "—"}</TableCell>
                <TableCell className="capitalize">{txn.type}</TableCell>
                <TableCell className="font-semibold">${parseFloat(txn.amount).toFixed(2)}</TableCell>
                <TableCell>${parseFloat(txn.fees || 0).toFixed(2)}</TableCell>
                <TableCell className="font-semibold">${net(txn)}</TableCell>
                <TableCell>{txn.currency}</TableCell>
                <TableCell><span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${statusBadge(txn.status)}`}>{txn.status}</span></TableCell>
                <TableCell className="max-w-[140px] truncate">{txn.description || "—"}</TableCell>
                <TableCell className="font-mono">{txn.linked_order_id || "—"}</TableCell>
                <TableCell>
                  <div className="flex gap-1 flex-nowrap">
                    <Button size="sm" variant="outline" className="h-6 px-2 text-[11px]" onClick={() => openEdit(txn)} data-testid={`bt-edit-${txn.id}`}>Edit</Button>
                    {txn.internal_notes && <Button size="sm" variant="outline" className="h-6 px-2 text-[11px]" onClick={() => openNotes(txn)} data-testid={`bt-notes-${txn.id}`}>Notes</Button>}
                    <Button size="sm" variant="outline" className="h-6 px-2 text-[11px]" onClick={() => openLogs(txn)} data-testid={`bt-logs-${txn.id}`}>Logs</Button>
                    <Button size="sm" variant="destructive" className="h-6 px-2 text-[11px]" onClick={() => handleDelete(txn.id)} data-testid={`bt-delete-${txn.id}`}>Delete</Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <AdminPagination page={page} totalPages={totalPages} total={total} perPage={PER_PAGE} onPage={(p) => load(p)} />

      {/* Notes Modal */}
      <Dialog open={showNotesModal} onOpenChange={setShowNotesModal}>
        <DialogContent><DialogHeader><DialogTitle>Transaction Notes</DialogTitle></DialogHeader>
          <p className="text-sm text-slate-700 whitespace-pre-wrap">{notesContent}</p>
        </DialogContent>
      </Dialog>

      {/* Create/Edit Modal */}
      <Dialog open={showForm} onOpenChange={setShowForm}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>{editTxn ? "Edit Transaction" : "Add Transaction"}</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-4 py-2">
            {[["Date *", <Input key="d" type="date" value={form.date} onChange={e => setForm({...form, date: e.target.value})} data-testid="bt-form-date" />],
              ["Source *", <Select key="s" value={form.source} onValueChange={v => setForm({...form, source: v})}><SelectTrigger data-testid="bt-form-source"><SelectValue /></SelectTrigger><SelectContent>{SOURCES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent></Select>],
              ["Transaction ID", <Input key="ti" value={form.transaction_id} onChange={e => setForm({...form, transaction_id: e.target.value})} data-testid="bt-form-txnid" />],
              ["Type *", <Select key="ty" value={form.type} onValueChange={v => setForm({...form, type: v})}><SelectTrigger data-testid="bt-form-type"><SelectValue /></SelectTrigger><SelectContent>{TYPES.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent></Select>],
              ["Amount *", <Input key="am" type="number" step="0.01" value={form.amount} onChange={e => setForm({...form, amount: e.target.value})} data-testid="bt-form-amount" />],
              ["Fees", <Input key="fe" type="number" step="0.01" value={form.fees} onChange={e => setForm({...form, fees: e.target.value})} data-testid="bt-form-fees" />],
              ["Currency", <Input key="cu" value={form.currency} onChange={e => setForm({...form, currency: e.target.value.toUpperCase()})} maxLength={3} data-testid="bt-form-currency" />],
              ["Status *", <Select key="st" value={form.status} onValueChange={v => setForm({...form, status: v})}><SelectTrigger data-testid="bt-form-status"><SelectValue /></SelectTrigger><SelectContent>{btStatuses.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent></Select>]
            ].map(([label, child]: any) => (
              <div key={String(label)} className="space-y-1"><label className="text-xs font-semibold text-slate-500 uppercase tracking-wide">{label}</label>{child}</div>
            ))}
            <div className="col-span-2 space-y-1"><label className="text-xs font-semibold text-slate-500 uppercase">Description</label><Input value={form.description} onChange={e => setForm({...form, description: e.target.value})} data-testid="bt-form-description" /></div>
            <div className="col-span-2 space-y-1"><label className="text-xs font-semibold text-slate-500 uppercase">Linked Order ID</label><Input value={form.linked_order_id} onChange={e => setForm({...form, linked_order_id: e.target.value})} data-testid="bt-form-linked-order" /></div>
            <div className="col-span-2 space-y-1"><label className="text-xs font-semibold text-slate-500 uppercase">Internal Notes</label><textarea className="w-full rounded-md border border-slate-200 p-2 text-sm resize-none h-20" value={form.internal_notes} onChange={e => setForm({...form, internal_notes: e.target.value})} data-testid="bt-form-notes" /></div>
          </div>
          {form.amount && <div className="rounded-lg bg-slate-50 p-3 text-sm text-slate-600">Net: <strong>${(parseFloat(form.amount||"0")-parseFloat(form.fees||"0")).toFixed(2)}</strong></div>}
          <div className="flex gap-2 pt-2">
            <Button onClick={handleSave} disabled={saving} data-testid="bt-form-save">{saving ? "Saving..." : editTxn ? "Update" : "Create"}</Button>
            <Button variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Logs Modal */}
      <Dialog open={showLogs} onOpenChange={setShowLogs}>
        <DialogContent className="max-w-xl max-h-[80vh] overflow-y-auto"><DialogHeader><DialogTitle>{logsTitle}</DialogTitle></DialogHeader>
          <div className="space-y-2 py-2">
            {logsData.length === 0 && <p className="text-sm text-slate-400">No logs yet</p>}
            {logsData.map((log, i) => (
              <div key={i} className="rounded-lg border border-slate-100 bg-slate-50 p-3 text-xs">
                <div className="flex justify-between mb-1"><span className="font-semibold capitalize">{log.action}</span><span className="text-slate-400">{log.timestamp?.slice(0,19).replace("T"," ")}</span></div>
                <div className="text-slate-500">by {log.actor}</div>
                {Object.keys(log.details||{}).length > 0 && <pre className="mt-1 text-xs text-slate-500 whitespace-pre-wrap">{JSON.stringify(log.details,null,2)}</pre>}
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
