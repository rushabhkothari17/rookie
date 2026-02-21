import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "@/components/ui/sonner";
import api from "@/lib/api";

const SOURCES = ["manual", "stripe", "gocardless"];
const TYPES = ["payment", "refund", "chargeback", "credit", "debit", "fee"];
const STATUSES = ["pending", "completed", "failed", "refunded"];

const EMPTY_FORM = {
  date: new Date().toISOString().slice(0, 10),
  source: "manual",
  transaction_id: "",
  type: "payment",
  amount: "",
  fees: "0",
  currency: "USD",
  status: "completed",
  description: "",
  linked_order_id: "",
  internal_notes: "",
};

export function BankTransactionsTab() {
  const [transactions, setTransactions] = useState<any[]>([]);
  const [filterSource, setFilterSource] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterType, setFilterType] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editTxn, setEditTxn] = useState<any>(null);
  const [form, setForm] = useState<any>(EMPTY_FORM);
  const [showLogs, setShowLogs] = useState(false);
  const [logsData, setLogsData] = useState<any[]>([]);
  const [logsTitle, setLogsTitle] = useState("");
  const [saving, setSaving] = useState(false);

  const loadTransactions = async () => {
    const params = new URLSearchParams();
    if (filterSource) params.set("source", filterSource);
    if (filterStatus) params.set("status", filterStatus);
    if (filterType) params.set("type", filterType);
    const res = await api.get(`/admin/bank-transactions?${params.toString()}`);
    setTransactions(res.data.transactions || []);
  };

  useEffect(() => { loadTransactions(); }, [filterSource, filterStatus, filterType]);

  const openCreate = () => {
    setEditTxn(null);
    setForm(EMPTY_FORM);
    setShowForm(true);
  };

  const openEdit = (txn: any) => {
    setEditTxn(txn);
    setForm({
      date: txn.date || "",
      source: txn.source || "manual",
      transaction_id: txn.transaction_id || "",
      type: txn.type || "payment",
      amount: String(txn.amount || ""),
      fees: String(txn.fees || "0"),
      currency: txn.currency || "USD",
      status: txn.status || "completed",
      description: txn.description || "",
      linked_order_id: txn.linked_order_id || "",
      internal_notes: txn.internal_notes || "",
    });
    setShowForm(true);
  };

  const handleSave = async () => {
    if (!form.date || !form.amount) { toast.error("Date and amount are required"); return; }
    setSaving(true);
    try {
      const payload = {
        ...form,
        amount: parseFloat(form.amount),
        fees: parseFloat(form.fees || "0"),
      };
      if (editTxn) {
        await api.put(`/admin/bank-transactions/${editTxn.id}`, payload);
        toast.success("Transaction updated");
      } else {
        await api.post("/admin/bank-transactions", payload);
        toast.success("Transaction created");
      }
      setShowForm(false);
      loadTransactions();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this transaction?")) return;
    await api.delete(`/admin/bank-transactions/${id}`);
    toast.success("Deleted");
    loadTransactions();
  };

  const openLogs = async (txn: any) => {
    const res = await api.get(`/admin/bank-transactions/${txn.id}/logs`);
    setLogsData(res.data.logs || []);
    setLogsTitle(`Logs: ${txn.description || txn.id.slice(0, 8)}`);
    setShowLogs(true);
  };

  const handleExport = () => {
    const apiUrl = process.env.REACT_APP_BACKEND_URL || "";
    window.open(`${apiUrl}/api/admin/export/bank-transactions`, "_blank");
  };

  const net = (txn: any) => {
    const n = txn.net_amount ?? (txn.amount - (txn.fees || 0));
    return n.toFixed(2);
  };

  const statusBadge = (s: string) => {
    const map: Record<string, string> = {
      completed: "bg-green-100 text-green-700",
      pending: "bg-yellow-100 text-yellow-700",
      failed: "bg-red-100 text-red-700",
      refunded: "bg-slate-100 text-slate-600",
    };
    return map[s] || "bg-slate-100 text-slate-600";
  };

  const field = (label: string, child: React.ReactNode) => (
    <div className="space-y-1">
      <label className="text-xs font-semibold text-slate-500 uppercase tracking-wide">{label}</label>
      {child}
    </div>
  );

  return (
    <div className="space-y-4" data-testid="bank-transactions-tab">
      {/* Header + filters */}
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <h3 className="text-sm font-semibold text-slate-900">Bank Transactions</h3>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={handleExport} data-testid="bt-export">Export CSV</Button>
            <Button size="sm" onClick={openCreate} data-testid="bt-add">+ Add Transaction</Button>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Select value={filterSource || "all"} onValueChange={v => setFilterSource(v === "all" ? "" : v)}>
            <SelectTrigger className="w-36 text-xs" data-testid="bt-filter-source"><SelectValue placeholder="Source" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Sources</SelectItem>
              {SOURCES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={filterStatus || "all"} onValueChange={v => setFilterStatus(v === "all" ? "" : v)}>
            <SelectTrigger className="w-36 text-xs" data-testid="bt-filter-status"><SelectValue placeholder="Status" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Statuses</SelectItem>
              {STATUSES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={filterType || "all"} onValueChange={v => setFilterType(v === "all" ? "" : v)}>
            <SelectTrigger className="w-36 text-xs" data-testid="bt-filter-type"><SelectValue placeholder="Type" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Types</SelectItem>
              {TYPES.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-200 bg-white overflow-auto">
        <Table data-testid="bt-table">
          <TableHeader>
            <TableRow>
              <TableHead className="text-xs">Date</TableHead>
              <TableHead className="text-xs">Source</TableHead>
              <TableHead className="text-xs">Txn ID</TableHead>
              <TableHead className="text-xs">Type</TableHead>
              <TableHead className="text-xs">Amount</TableHead>
              <TableHead className="text-xs">Fees</TableHead>
              <TableHead className="text-xs">Net</TableHead>
              <TableHead className="text-xs">Currency</TableHead>
              <TableHead className="text-xs">Status</TableHead>
              <TableHead className="text-xs">Description</TableHead>
              <TableHead className="text-xs">Linked Order</TableHead>
              <TableHead className="text-xs">Notes</TableHead>
              <TableHead className="text-xs">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {transactions.length === 0 && (
              <TableRow><TableCell colSpan={13} className="text-center text-slate-400 py-8 text-sm">No transactions found</TableCell></TableRow>
            )}
            {transactions.map(txn => (
              <TableRow key={txn.id} data-testid={`bt-row-${txn.id}`}>
                <TableCell className="text-xs font-mono">{txn.date}</TableCell>
                <TableCell className="text-xs capitalize">{txn.source}</TableCell>
                <TableCell className="text-xs font-mono max-w-[100px] truncate">{txn.transaction_id || "—"}</TableCell>
                <TableCell className="text-xs capitalize">{txn.type}</TableCell>
                <TableCell className="text-xs font-semibold">${parseFloat(txn.amount).toFixed(2)}</TableCell>
                <TableCell className="text-xs">${parseFloat(txn.fees || 0).toFixed(2)}</TableCell>
                <TableCell className="text-xs font-semibold">${net(txn)}</TableCell>
                <TableCell className="text-xs">{txn.currency}</TableCell>
                <TableCell>
                  <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${statusBadge(txn.status)}`}>
                    {txn.status}
                  </span>
                </TableCell>
                <TableCell className="text-xs max-w-[140px] truncate">{txn.description || "—"}</TableCell>
                <TableCell className="text-xs font-mono">{txn.linked_order_id || "—"}</TableCell>
                <TableCell className="text-xs max-w-[100px] truncate">{txn.internal_notes || "—"}</TableCell>
                <TableCell>
                  <div className="flex gap-1">
                    <Button size="sm" variant="outline" className="text-xs h-7 px-2" onClick={() => openEdit(txn)} data-testid={`bt-edit-${txn.id}`}>Edit</Button>
                    <Button size="sm" variant="outline" className="text-xs h-7 px-2" onClick={() => openLogs(txn)} data-testid={`bt-logs-${txn.id}`}>Logs</Button>
                    <Button size="sm" variant="outline" className="text-xs h-7 px-2 text-red-600" onClick={() => handleDelete(txn.id)} data-testid={`bt-delete-${txn.id}`}>Del</Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Create/Edit Modal */}
      <Dialog open={showForm} onOpenChange={setShowForm}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editTxn ? "Edit Transaction" : "Add Transaction"}</DialogTitle>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-4 py-2">
            {field("Date *", <Input type="date" value={form.date} onChange={e => setForm({...form, date: e.target.value})} data-testid="bt-form-date" />)}
            {field("Source *", (
              <Select value={form.source} onValueChange={v => setForm({...form, source: v})}>
                <SelectTrigger data-testid="bt-form-source"><SelectValue /></SelectTrigger>
                <SelectContent>{SOURCES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
              </Select>
            ))}
            {field("Transaction ID", <Input value={form.transaction_id} onChange={e => setForm({...form, transaction_id: e.target.value})} placeholder="External ID" data-testid="bt-form-txnid" />)}
            {field("Type *", (
              <Select value={form.type} onValueChange={v => setForm({...form, type: v})}>
                <SelectTrigger data-testid="bt-form-type"><SelectValue /></SelectTrigger>
                <SelectContent>{TYPES.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
              </Select>
            ))}
            {field("Amount *", <Input type="number" step="0.01" value={form.amount} onChange={e => setForm({...form, amount: e.target.value})} placeholder="0.00" data-testid="bt-form-amount" />)}
            {field("Fees", <Input type="number" step="0.01" value={form.fees} onChange={e => setForm({...form, fees: e.target.value})} placeholder="0.00" data-testid="bt-form-fees" />)}
            {field("Currency", <Input value={form.currency} onChange={e => setForm({...form, currency: e.target.value.toUpperCase()})} maxLength={3} data-testid="bt-form-currency" />)}
            {field("Status *", (
              <Select value={form.status} onValueChange={v => setForm({...form, status: v})}>
                <SelectTrigger data-testid="bt-form-status"><SelectValue /></SelectTrigger>
                <SelectContent>{STATUSES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
              </Select>
            ))}
            <div className="col-span-2">
              {field("Description", <Input value={form.description} onChange={e => setForm({...form, description: e.target.value})} placeholder="Payment description" data-testid="bt-form-description" />)}
            </div>
            <div className="col-span-2">
              {field("Linked Order ID", <Input value={form.linked_order_id} onChange={e => setForm({...form, linked_order_id: e.target.value})} placeholder="Order ID (optional)" data-testid="bt-form-linked-order" />)}
            </div>
            <div className="col-span-2">
              {field("Internal Notes", (
                <textarea
                  className="w-full rounded-md border border-slate-200 p-2 text-sm resize-none h-20 focus:outline-none focus:ring-1 focus:ring-slate-300"
                  value={form.internal_notes}
                  onChange={e => setForm({...form, internal_notes: e.target.value})}
                  placeholder="Internal notes for this transaction"
                  data-testid="bt-form-notes"
                />
              ))}
            </div>
          </div>
          {form.amount && (
            <div className="rounded-lg bg-slate-50 p-3 text-sm text-slate-600">
              Net amount: <strong>${(parseFloat(form.amount || "0") - parseFloat(form.fees || "0")).toFixed(2)}</strong>
            </div>
          )}
          <div className="flex gap-2 pt-2">
            <Button onClick={handleSave} disabled={saving} className="bg-slate-900 text-white hover:bg-slate-800" data-testid="bt-form-save">
              {saving ? "Saving..." : editTxn ? "Update" : "Create"}
            </Button>
            <Button variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Logs Modal */}
      <Dialog open={showLogs} onOpenChange={setShowLogs}>
        <DialogContent className="max-w-xl max-h-[80vh] overflow-y-auto">
          <DialogHeader><DialogTitle>{logsTitle}</DialogTitle></DialogHeader>
          <div className="space-y-2 py-2">
            {logsData.length === 0 && <p className="text-sm text-slate-400">No logs yet</p>}
            {logsData.map((log, i) => (
              <div key={i} className="rounded-lg border border-slate-100 bg-slate-50 p-3 text-xs">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-slate-700 capitalize">{log.action}</span>
                  <span className="text-slate-400">{log.timestamp?.slice(0, 19).replace("T", " ")}</span>
                </div>
                <div className="text-slate-500">by {log.actor}</div>
                {Object.keys(log.details || {}).length > 0 && (
                  <pre className="mt-1 text-xs text-slate-500 whitespace-pre-wrap">{JSON.stringify(log.details, null, 2)}</pre>
                )}
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
