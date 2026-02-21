import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";

interface QuoteRequest {
  id: string;
  product_id: string;
  product_name: string;
  name: string;
  email: string;
  company?: string;
  phone?: string;
  message?: string;
  user_id?: string;
  created_at: string;
  status: string;
}

const BLANK_FORM = {
  product_id: "", product_name: "", name: "", email: "",
  company: "", phone: "", message: "", user_id: "", status: "pending",
};

export function QuoteRequestsTab() {
  const [quotes, setQuotes] = useState<QuoteRequest[]>([]);
  const [products, setProducts] = useState<any[]>([]);
  const [customers, setCustomers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [editQuote, setEditQuote] = useState<QuoteRequest | null>(null);
  const [form, setForm] = useState({ ...BLANK_FORM });
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [qRes, pRes, cRes] = await Promise.all([
        api.get("/admin/quote-requests"),
        api.get("/admin/products-all").catch(() => ({ data: { products: [] } })),
        api.get("/admin/customers").catch(() => ({ data: { customers: [] } })),
      ]);
      setQuotes(qRes.data.quotes || []);
      setProducts(pRes.data.products || []);
      setCustomers(cRes.data.customers || []);
    } catch {
      toast.error("Failed to load quote requests");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const openCreate = () => {
    setEditQuote(null);
    setForm({ ...BLANK_FORM });
    setShowDialog(true);
  };

  const openEdit = (q: QuoteRequest) => {
    setEditQuote(q);
    setForm({
      product_id: q.product_id || "",
      product_name: q.product_name || "",
      name: q.name || "",
      email: q.email || "",
      company: q.company || "",
      phone: q.phone || "",
      message: q.message || "",
      user_id: q.user_id || "",
      status: q.status || "pending",
    });
    setShowDialog(true);
  };

  const handleProductChange = (id: string) => {
    const prod = products.find((p) => p.id === id);
    setForm((f) => ({ ...f, product_id: id, product_name: prod?.name || "" }));
  };

  const handleCustomerChange = (customerId: string) => {
    const cust = customers.find((c) => c.id === customerId);
    setForm((f) => ({
      ...f,
      user_id: cust?.user_id || "",
      name: cust?.company_name || f.name,
      company: cust?.company_name || f.company,
    }));
  };

  const handleSave = async () => {
    if (!form.name.trim() || !form.email.trim()) {
      toast.error("Name and email are required");
      return;
    }
    setSaving(true);
    try {
      if (editQuote) {
        await api.put(`/admin/quote-requests/${editQuote.id}`, form);
        toast.success("Quote request updated");
      } else {
        await api.post("/admin/quote-requests", form);
        toast.success("Quote request created");
      }
      setShowDialog(false);
      load();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const formatDate = (iso: string) => {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleString("en-AU", {
        day: "2-digit", month: "short", year: "numeric",
        hour: "2-digit", minute: "2-digit",
      });
    } catch { return iso; }
  };

  const statusBadge = (s: string) => {
    const map: Record<string, string> = {
      pending: "bg-yellow-100 text-yellow-700",
      responded: "bg-green-100 text-green-700",
      closed: "bg-slate-100 text-slate-500",
    };
    return (
      <span className={`text-xs px-2 py-0.5 rounded font-medium ${map[s] || "bg-slate-100 text-slate-500"}`}>
        {s}
      </span>
    );
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-900">Quote Requests</h3>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={load}>Refresh</Button>
          <Button size="sm" onClick={openCreate} data-testid="admin-create-quote-btn">+ New Quote Request</Button>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
        <Table data-testid="admin-quotes-table">
          <TableHeader>
            <TableRow className="bg-slate-50">
              <TableHead>Date</TableHead>
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
            {loading && (
              <TableRow><TableCell colSpan={8} className="text-center text-slate-400">Loading…</TableCell></TableRow>
            )}
            {!loading && quotes.length === 0 && (
              <TableRow><TableCell colSpan={8} className="text-center text-slate-400 py-8">No quote requests yet.</TableCell></TableRow>
            )}
            {quotes.map((q) => (
              <TableRow key={q.id} data-testid={`admin-quote-row-${q.id}`}>
                <TableCell className="text-xs text-slate-500 whitespace-nowrap">{formatDate(q.created_at)}</TableCell>
                <TableCell className="font-medium text-sm max-w-[140px]">
                  <span className="block truncate" title={q.product_name}>{q.product_name || "—"}</span>
                </TableCell>
                <TableCell>
                  <div className="text-sm font-medium">{q.name}</div>
                  <div className="text-xs text-slate-400">{q.email}</div>
                </TableCell>
                <TableCell className="text-sm">{q.company || "—"}</TableCell>
                <TableCell className="text-sm">{q.phone || "—"}</TableCell>
                <TableCell className="max-w-[180px]">
                  <span className="text-xs text-slate-600 line-clamp-2" title={q.message}>{q.message || "—"}</span>
                </TableCell>
                <TableCell>{statusBadge(q.status)}</TableCell>
                <TableCell>
                  <Button variant="outline" size="sm" onClick={() => openEdit(q)} data-testid={`admin-edit-quote-${q.id}`}>Edit</Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="max-w-lg" data-testid="admin-quote-dialog">
          <DialogHeader>
            <DialogTitle>{editQuote ? "Edit Quote Request" : "New Quote Request"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            {/* Product selector */}
            <div>
              <label className="text-sm font-medium text-slate-700">Product</label>
              <Select value={form.product_id} onValueChange={handleProductChange}>
                <SelectTrigger className="mt-1" data-testid="admin-quote-product"><SelectValue placeholder="Select product…" /></SelectTrigger>
                <SelectContent>
                  {products.map((p) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>

            {/* Customer picker */}
            <div>
              <label className="text-sm font-medium text-slate-700">Customer (optional — auto-fills contact)</label>
              <Select onValueChange={handleCustomerChange}>
                <SelectTrigger className="mt-1" data-testid="admin-quote-customer"><SelectValue placeholder="Select customer…" /></SelectTrigger>
                <SelectContent>
                  {customers.map((c) => <SelectItem key={c.id} value={c.id}>{c.company_name || c.id}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium text-slate-700">Name *</label>
                <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Full name" className="mt-1" data-testid="admin-quote-name" />
              </div>
              <div>
                <label className="text-sm font-medium text-slate-700">Email *</label>
                <Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="email@example.com" className="mt-1" data-testid="admin-quote-email" />
              </div>
              <div>
                <label className="text-sm font-medium text-slate-700">Company</label>
                <Input value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} placeholder="Company name" className="mt-1" data-testid="admin-quote-company" />
              </div>
              <div>
                <label className="text-sm font-medium text-slate-700">Phone</label>
                <Input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="+1 555 0000" className="mt-1" data-testid="admin-quote-phone" />
              </div>
            </div>

            <div>
              <label className="text-sm font-medium text-slate-700">Message</label>
              <Textarea value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} placeholder="Description of requirements…" rows={3} className="mt-1" data-testid="admin-quote-message" />
            </div>

            <div>
              <label className="text-sm font-medium text-slate-700">Status</label>
              <Select value={form.status} onValueChange={(v) => setForm({ ...form, status: v })}>
                <SelectTrigger className="mt-1" data-testid="admin-quote-status"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="pending">Pending</SelectItem>
                  <SelectItem value="responded">Responded</SelectItem>
                  <SelectItem value="closed">Closed</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="flex gap-2 justify-end pt-2">
              <Button variant="outline" onClick={() => setShowDialog(false)}>Cancel</Button>
              <Button onClick={handleSave} disabled={saving} data-testid="admin-quote-save-btn">
                {saving ? "Saving…" : "Save"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
