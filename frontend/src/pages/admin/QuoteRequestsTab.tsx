import { useCallback, useEffect, useState } from "react";
import { ImportModal } from "@/components/admin/ImportModal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { AdminPageHeader } from "./shared/AdminPageHeader";
import { AdminPagination } from "./shared/AdminPagination";
import { AuditLogDialog } from "@/components/AuditLogDialog";
import { Download, Upload} from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SearchableSelect } from "@/components/ui/searchable-select";

const STATUS_OPTIONS = ["pending", "responded", "closed"];
const BLANK_FORM = { product_id: "", product_name: "", name: "", email: "", company: "", phone: "", message: "", user_id: "", status: "pending" };

export function QuoteRequestsTab() {
  const [quotes, setQuotes] = useState<any[]>([]);
  const [showImport, setShowImport] = useState(false);
  const [products, setProducts] = useState<any[]>([]);
  const [customers, setCustomers] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const PER_PAGE = 20;

  // Filters
  const [emailFilter, setEmailFilter] = useState("");
  const [productFilter, setProductFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [sortOrder, setSortOrder] = useState<"desc" | "asc">("desc");

  // Dialog
  const [showDialog, setShowDialog] = useState(false);
  const [editQuote, setEditQuote] = useState<any>(null);
  const [form, setForm] = useState({ ...BLANK_FORM });
  const [customerSearch, setCustomerSearch] = useState("");
  const [logsUrl, setLogsUrl] = useState("");
  const [showAuditLogs, setShowAuditLogs] = useState(false);
  const [confirmDeleteQuote, setConfirmDeleteQuote] = useState<any>(null);

  const userMap: Record<string, any> = {};
  users.forEach((u) => { userMap[u.id] = u; });

  const load = useCallback(async (p = 1) => {
    try {
      const params = new URLSearchParams({ page: String(p), per_page: String(PER_PAGE) });
      if (emailFilter) params.append("email", emailFilter);
      if (productFilter) params.append("product", productFilter);
      if (statusFilter) params.append("status", statusFilter);
      if (startDate) params.append("date_from", startDate);
      if (endDate) params.append("date_to", endDate);
      const res = await api.get(`/admin/quote-requests?${params}`);
      let qs = res.data.quotes || [];
      if (sortOrder === "asc") qs = [...qs].reverse();
      setQuotes(qs);
      setTotal(res.data.total || 0);
      setTotalPages(res.data.total_pages || 1);
      setPage(p);
    } catch { toast.error("Failed to load quote requests"); }
  }, [emailFilter, productFilter, statusFilter, startDate, endDate, sortOrder]);

  useEffect(() => {
    Promise.all([
      api.get("/admin/products-all").catch(() => ({ data: { products: [] } })),
      api.get("/admin/customers?per_page=1000").catch(() => ({ data: { customers: [], users: [] } })),
    ]).then(([pRes, cRes]) => {
      setProducts(pRes.data.products || []);
      setCustomers(cRes.data.customers || []);
      setUsers(cRes.data.users || []);
    });
  }, []);

  useEffect(() => { load(1); }, [emailFilter, productFilter, statusFilter, startDate, endDate]);

  const openCreate = () => { setEditQuote(null); setForm({ ...BLANK_FORM }); setCustomerSearch(""); setShowDialog(true); };
  const openEdit = (q: any) => { setEditQuote(q); setForm({ product_id: q.product_id || "", product_name: q.product_name || "", name: q.name || "", email: q.email || "", company: q.company || "", phone: q.phone || "", message: q.message || "", user_id: q.user_id || "", status: q.status || "pending" }); setCustomerSearch(""); setShowDialog(true); };

  const handleCustomerSelect = (cust: any) => {
    const u = userMap[cust.user_id];
    setForm(f => ({ ...f, user_id: cust.user_id || "", email: u?.email || f.email, name: cust.company_name || u?.full_name || f.name, company: cust.company_name || f.company }));
    setCustomerSearch(u?.email || "");
  };

  const handleSave = async () => {
    if (!form.name.trim() || !form.email.trim()) { toast.error("Name and email are required"); return; }
    try {
      if (editQuote) { await api.put(`/admin/quote-requests/${editQuote.id}`, form); toast.success("Quote request updated"); }
      else { await api.post("/admin/quote-requests", form); toast.success("Quote request created"); }
      setShowDialog(false); load(page);
    } catch (e: any) { toast.error(e?.response?.data?.detail || "Failed to save"); }
  };

  const handleDelete = async (quoteId: string) => {
    try { await api.delete(`/admin/quote-requests/${quoteId}`); toast.success("Quote request deleted"); load(page); }
    catch (e: any) { toast.error(e.response?.data?.detail || "Failed to delete"); }
  };

  const clearFilters = () => { setEmailFilter(""); setProductFilter(""); setStatusFilter(""); setStartDate(""); setEndDate(""); };

  const downloadCsv = () => {
    const token = localStorage.getItem("aa_token");
    const base = process.env.REACT_APP_BACKEND_URL || "";
    const params = new URLSearchParams();
    if (emailFilter) params.append("email", emailFilter);
    if (productFilter) params.append("product", productFilter);
    if (statusFilter) params.append("status", statusFilter);
    if (startDate) params.append("date_from", startDate);
    if (endDate) params.append("date_to", endDate);
    fetch(`${base}/api/admin/export/quote-requests?${params}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.blob()).then(b => { const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = `quote-requests-${new Date().toISOString().slice(0, 10)}.csv`; a.click(); })
      .catch(() => toast.error("Export failed"));
  };

  const filteredCustomers = customers.filter(c => {
    const u = userMap[c.user_id];
    const q = customerSearch.toLowerCase();
    return !q || u?.email?.toLowerCase().includes(q) || c.company_name?.toLowerCase().includes(q);
  }).slice(0, 10);

  const statusBadge = (s: string) => {
    const map: Record<string, string> = { pending: "bg-yellow-100 text-yellow-700", responded: "bg-green-100 text-green-700", closed: "bg-slate-100 text-slate-500" };
    return <span className={`text-xs px-2 py-0.5 rounded font-medium ${map[s] || "bg-slate-100 text-slate-500"}`}>{s}</span>;
  };

  return (
    <div className="space-y-4" data-testid="quote-requests-tab">
      <AdminPageHeader
        title="Requests"
        subtitle={`${total} records`}
        actions={
          <>
            <Button size="sm" variant="outline" onClick={downloadCsv} data-testid="admin-quotes-export-csv"><Download size={14} className="mr-1" />Export CSV</Button>
            <Button size="sm" variant="outline" onClick={() => setShowImport(true)} data-testid="admin-quotes-import-csv"><Upload size={14} className="mr-1" />Import CSV</Button>
            <Button size="sm" onClick={openCreate} data-testid="admin-create-quote-btn">+ New Request</Button>
          </>
        }
      />

      {/* Filters */}
      <div className="rounded-xl border border-slate-200 bg-white p-3">
        <div className="flex flex-wrap gap-2 items-end">
          <Input placeholder="Contact email…" value={emailFilter} onChange={e => setEmailFilter(e.target.value)} className="h-8 text-xs w-44" data-testid="admin-quotes-email-filter" />
          <Input placeholder="Product name…" value={productFilter} onChange={e => setProductFilter(e.target.value)} className="h-8 text-xs w-36" data-testid="admin-quotes-product-filter" />
          <Select value={statusFilter || "all"} onValueChange={v => setStatusFilter(v === "all" ? "" : v)}>
            <SelectTrigger className="h-8 text-xs w-36 bg-white" data-testid="admin-quotes-status-filter"><SelectValue placeholder="All Statuses" /></SelectTrigger>
            <SelectContent><SelectItem value="all">All Statuses</SelectItem>{STATUS_OPTIONS.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
          </Select>
          <div className="flex items-center gap-1">
            <span className="text-xs text-slate-400">From</span>
            <Input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} className="h-8 text-xs w-32" data-testid="admin-quotes-start-date" />
            <span className="text-xs text-slate-400">–</span>
            <Input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} className="h-8 text-xs w-32" data-testid="admin-quotes-end-date" />
          </div>
          <Button size="sm" variant="outline" onClick={clearFilters} className="h-8 text-xs" data-testid="admin-quotes-clear-filters">Clear</Button>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
        <Table data-testid="admin-quotes-table">
          <TableHeader>
            <TableRow className="bg-slate-50">
              <TableHead className="cursor-pointer select-none" onClick={() => setSortOrder(o => o === "desc" ? "asc" : "desc")}>
                Date {sortOrder === "desc" ? "↓" : "↑"}
              </TableHead>
              <TableHead>Product</TableHead>
              <TableHead>Contact</TableHead>
              <TableHead>Company</TableHead>
              <TableHead>Phone</TableHead>
              <TableHead>Message</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {quotes.length === 0 && <TableRow><TableCell colSpan={8} className="text-center text-slate-400 py-8">No quote requests found.</TableCell></TableRow>}
            {quotes.map((q) => (
              <TableRow key={q.id} data-testid={`admin-quote-row-${q.id}`}>
                <TableCell className="whitespace-nowrap">{q.created_at?.slice(0, 10)}</TableCell>
                <TableCell className="font-medium max-w-[140px] truncate">{q.product_name || "—"}</TableCell>
                <TableCell><div className="font-medium">{q.name}</div><div className="text-slate-400">{q.email}</div></TableCell>
                <TableCell>{q.company || "—"}</TableCell>
                <TableCell>{q.phone || "—"}</TableCell>
                <TableCell className="max-w-[180px]"><span className="line-clamp-2">{q.message || "—"}</span></TableCell>
                <TableCell>{statusBadge(q.status)}</TableCell>
                <TableCell>
                  <div className="flex gap-1">
                    <Button variant="outline" size="sm" className="h-6 px-2 text-[11px]" onClick={() => openEdit(q)} data-testid={`admin-edit-quote-${q.id}`}>Edit</Button>
                    <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px]" onClick={() => { setLogsUrl(`/admin/quote-requests/${q.id}/logs`); setShowAuditLogs(true); }} data-testid={`admin-quote-logs-${q.id}`}>Logs</Button>
                    <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px] text-red-500 hover:text-red-700" onClick={() => setConfirmDeleteQuote(q)} data-testid={`admin-quote-delete-${q.id}`}>Delete</Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <AdminPagination page={page} totalPages={totalPages} total={total} perPage={PER_PAGE} onPage={(p) => load(p)} />

      {/* Edit/Create Dialog */}
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="max-w-lg" data-testid="admin-quote-dialog">
          <DialogHeader><DialogTitle>{editQuote ? "Edit Request" : "New Request"}</DialogTitle></DialogHeader>
          <div className="space-y-3 py-2">
            {/* Product */}
            <div className="space-y-1">
              <label className="text-xs text-slate-500">Product</label>
              <SearchableSelect
                value={form.product_id || undefined}
                onValueChange={v => { const p = products.find((x: any) => x.id === v); setForm(f => ({ ...f, product_id: v, product_name: p?.name || "" })); }}
                options={products.map((p: any) => ({ value: p.id, label: p.name }))}
                placeholder="Select product…"
                searchPlaceholder="Search products..."
                data-testid="admin-quote-product"
              />
            </div>
            {/* Customer email search/typeahead */}
            <div className="space-y-1">
              <label className="text-xs text-slate-500">Customer (search by email — auto-fills contact below)</label>
              <Input placeholder="Search customer email…" value={customerSearch} onChange={e => setCustomerSearch(e.target.value)} className="h-8 text-xs" data-testid="admin-quote-customer-search" />
              {customerSearch && filteredCustomers.length > 0 && (
                <div className="border border-slate-200 rounded bg-white shadow-md z-10 max-h-40 overflow-y-auto">
                  {filteredCustomers.map((c: any) => {
                    const u = userMap[c.user_id];
                    return (
                      <div key={c.id} onClick={() => handleCustomerSelect(c)} className="px-3 py-2 hover:bg-slate-50 cursor-pointer text-xs">
                        <span className="font-medium">{u?.email}</span> {c.company_name ? `— ${c.company_name}` : ""}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1"><label className="text-xs text-slate-500">Name *</label><Input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} data-testid="admin-quote-name" /></div>
              <div className="space-y-1"><label className="text-xs text-slate-500">Email *</label><Input type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} data-testid="admin-quote-email" /></div>
              <div className="space-y-1"><label className="text-xs text-slate-500">Company</label><Input value={form.company} onChange={e => setForm({ ...form, company: e.target.value })} data-testid="admin-quote-company" /></div>
              <div className="space-y-1"><label className="text-xs text-slate-500">Phone</label><Input value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} data-testid="admin-quote-phone" /></div>
            </div>
            <div className="space-y-1"><label className="text-xs text-slate-500">Message</label><Textarea value={form.message} onChange={e => setForm({ ...form, message: e.target.value })} rows={3} data-testid="admin-quote-message" /></div>
            <div className="space-y-1">
              <label className="text-xs text-slate-500">Status</label>
              <Select value={form.status} onValueChange={v => setForm({ ...form, status: v })}>
                <SelectTrigger className="w-full bg-white" data-testid="admin-quote-status"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="pending">Pending</SelectItem><SelectItem value="responded">Responded</SelectItem><SelectItem value="closed">Closed</SelectItem></SelectContent>
              </Select>
            </div>
            <div className="flex gap-2 justify-end pt-1">
              <Button variant="outline" onClick={() => setShowDialog(false)}>Cancel</Button>
              <Button onClick={handleSave} data-testid="admin-quote-save-btn">Save</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <AuditLogDialog open={showAuditLogs} onOpenChange={setShowAuditLogs} title="Request Audit Logs" logsUrl={logsUrl} />
      <ImportModal
        entity="quote-requests"
        entityLabel="Requests"
        open={showImport}
        onClose={() => setShowImport(false)}
        onSuccess={load}
      />

      {/* Delete Quote Request Confirmation */}
      <AlertDialog open={!!confirmDeleteQuote} onOpenChange={(open) => !open && setConfirmDeleteQuote(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Quote Request</AlertDialogTitle>
            <AlertDialogDescription>Are you sure you want to delete the quote request from "{confirmDeleteQuote?.name}" for "{confirmDeleteQuote?.product_name}"? This cannot be undone.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction className="bg-red-600 hover:bg-red-700" onClick={() => { handleDelete(confirmDeleteQuote.id); setConfirmDeleteQuote(null); }} data-testid="confirm-quote-delete">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
