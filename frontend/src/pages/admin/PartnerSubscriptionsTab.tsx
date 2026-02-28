import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { AuditLogDialog } from "@/components/AuditLogDialog";
import { Plus, Pencil, Trash2, ExternalLink, ScrollText, RefreshCw, Copy, XCircle } from "lucide-react";

type Tenant = { id: string; name: string };
type Plan = { id: string; name: string; is_active: boolean };

type PartnerSubscription = {
  id: string;
  subscription_number: string;
  partner_id: string;
  partner_name: string;
  plan_id?: string;
  plan_name?: string;
  description?: string;
  amount: number;
  currency: string;
  billing_interval: string;
  status: string;
  payment_method: string;
  processor_id?: string;
  stripe_subscription_id?: string;
  start_date?: string;
  next_billing_date?: string;
  cancelled_at?: string;
  internal_note?: string;
  payment_url?: string;
  created_at: string;
};

type Stats = {
  total: number;
  active: number;
  new_this_month: number;
  by_status: Record<string, number>;
  by_interval: Record<string, number>;
  mrr: Record<string, number>;
  arr: Record<string, number>;
};

const STATUS_COLORS: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-700",
  pending: "bg-blue-100 text-blue-700",
  unpaid: "bg-amber-100 text-amber-700",
  paused: "bg-orange-100 text-orange-700",
  cancelled: "bg-slate-100 text-slate-500",
};

const STATUSES = ["pending", "active", "unpaid", "paused", "cancelled"];
const PAYMENT_METHODS = ["manual", "offline", "bank_transfer", "card"];
const BILLING_INTERVALS = ["monthly", "quarterly", "annual"];

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      <p className="text-2xl font-bold text-slate-900">{value}</p>
      {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
    </div>
  );
}

type SubFormData = {
  partner_id: string; plan_id: string; description: string; amount: string;
  currency: string; billing_interval: string; status: string; payment_method: string;
  processor_id: string; start_date: string; next_billing_date: string; internal_note: string;
  term_months: string; auto_cancel_on_termination: boolean;
};

const emptyForm = (): SubFormData => ({
  partner_id: "", plan_id: "", description: "", amount: "",
  currency: "GBP", billing_interval: "monthly", status: "pending",
  payment_method: "manual", processor_id: "", start_date: "", next_billing_date: "", internal_note: "",
  term_months: "", auto_cancel_on_termination: false,
});

function SubFormModal({
  sub, tenants, plans, onClose, onSaved,
}: {
  sub: PartnerSubscription | null;
  tenants: Tenant[];
  plans: Plan[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = !!sub;
  const [form, setForm] = useState<SubFormData>(
    sub ? {
      partner_id: sub.partner_id, plan_id: sub.plan_id || "", description: sub.description || "",
      amount: String(sub.amount), currency: sub.currency, billing_interval: sub.billing_interval,
      status: sub.status, payment_method: sub.payment_method, processor_id: sub.processor_id || "",
      start_date: sub.start_date ? sub.start_date.slice(0, 10) : "",
      next_billing_date: sub.next_billing_date ? sub.next_billing_date.slice(0, 10) : "",
      internal_note: sub.internal_note || "",
      term_months: sub.term_months != null ? String(sub.term_months) : "",
      auto_cancel_on_termination: sub.auto_cancel_on_termination || false,
    } : emptyForm()
  );
  const [saving, setSaving] = useState(false);
  const [generatingLink, setGeneratingLink] = useState(false);
  const [paymentUrl, setPaymentUrl] = useState(sub?.payment_url || "");

  const set = (k: keyof SubFormData, v: string) => setForm(f => ({ ...f, [k]: v }));

  const handleSave = async () => {
    if (!form.partner_id || !form.amount) {
      toast.error("Partner and amount are required"); return;
    }
    setSaving(true);
    try {
      const payload: Record<string, any> = {
        ...form,
        amount: parseFloat(form.amount),
        plan_id: form.plan_id || null,
        processor_id: form.processor_id || null,
        start_date: form.start_date || null,
        next_billing_date: form.next_billing_date || null,
        internal_note: form.internal_note || "",
        term_months: form.term_months ? parseInt(form.term_months) : null,
        auto_cancel_on_termination: form.auto_cancel_on_termination,
      };
      if (isEdit) {
        await api.put(`/admin/partner-subscriptions/${sub.id}`, payload);
        toast.success("Subscription updated");
      } else {
        await api.post("/admin/partner-subscriptions", payload);
        toast.success("Subscription created");
      }
      onSaved();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleStripeCheckout = async () => {
    if (!sub) return;
    setGeneratingLink(true);
    try {
      const { data } = await api.post("/admin/partner-billing/stripe-checkout", { partner_subscription_id: sub.id });
      setPaymentUrl(data.url);
      toast.success("Payment link generated");
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to generate Stripe link");
    } finally {
      setGeneratingLink(false);
    }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? `Edit Subscription — ${sub.subscription_number}` : "New Partner Subscription"}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 mt-2">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1 col-span-2">
              <label className="text-xs font-medium text-slate-600">Partner *</label>
              <Select value={form.partner_id} onValueChange={v => set("partner_id", v)}>
                <SelectTrigger data-testid="sub-partner-select"><SelectValue placeholder="Select partner…" /></SelectTrigger>
                <SelectContent>
                  {tenants.map(t => <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Plan (optional)</label>
              <Select value={form.plan_id || "__none__"} onValueChange={v => set("plan_id", v === "__none__" ? "" : v)}>
                <SelectTrigger><SelectValue placeholder="No plan" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">— None —</SelectItem>
                  {plans.map(p => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Status</label>
              <Select value={form.status} onValueChange={v => set("status", v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{STATUSES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-600">Description</label>
            <Input value={form.description} onChange={e => set("description", e.target.value)} placeholder="Monthly platform access" data-testid="sub-description-input" />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1 col-span-2">
              <label className="text-xs font-medium text-slate-600">Amount *</label>
              <Input type="number" min={0} step="0.01" value={form.amount} onChange={e => set("amount", e.target.value)} data-testid="sub-amount-input" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Currency</label>
              <Input value={form.currency} onChange={e => set("currency", e.target.value.toUpperCase())} maxLength={3} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Billing Interval</label>
              <Select value={form.billing_interval} onValueChange={v => set("billing_interval", v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{BILLING_INTERVALS.map(i => <SelectItem key={i} value={i}>{i}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Payment Method</label>
              <Select value={form.payment_method} onValueChange={v => set("payment_method", v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{PAYMENT_METHODS.map(m => <SelectItem key={m} value={m}>{m.replace("_", " ")}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Start Date</label>
              <Input type="date" value={form.start_date} onChange={e => set("start_date", e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Next Billing Date</label>
              <Input type="date" value={form.next_billing_date} onChange={e => set("next_billing_date", e.target.value)} />
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-600">Processor ID (Stripe/GC reference)</label>
            <Input value={form.processor_id} onChange={e => set("processor_id", e.target.value)} placeholder="sub_xxx or PM-xxx" />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-600">Internal Note</label>
            <Textarea rows={2} value={form.internal_note} onChange={e => set("internal_note", e.target.value)} />
          </div>

          {/* Stripe checkout link (edit mode, card payment, monthly/annual only) */}
          {isEdit && form.payment_method === "card" && form.billing_interval !== "quarterly" && (
            <div className="rounded-lg bg-blue-50 border border-blue-200 p-3 space-y-2">
              <p className="text-xs font-medium text-blue-700">Stripe Hosted Checkout (Recurring)</p>
              {paymentUrl ? (
                <div className="flex gap-2">
                  <Input readOnly value={paymentUrl} className="text-xs h-7" />
                  <Button size="sm" variant="outline" onClick={() => { navigator.clipboard.writeText(paymentUrl); toast.success("Copied!"); }}>
                    <Copy className="h-3.5 w-3.5" />
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => window.open(paymentUrl, "_blank")}>
                    <ExternalLink className="h-3.5 w-3.5" />
                  </Button>
                </div>
              ) : (
                <Button size="sm" onClick={handleStripeCheckout} disabled={generatingLink} data-testid="generate-stripe-sub-link-btn">
                  {generatingLink ? "Generating…" : "Generate Checkout Link"}
                </Button>
              )}
            </div>
          )}
        </div>
        <DialogFooter className="mt-4">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSave} disabled={saving} data-testid="save-partner-sub-btn">
            {saving ? "Saving…" : isEdit ? "Save Changes" : "Create Subscription"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function PartnerSubscriptionsTab() {
  const [subs, setSubs] = useState<PartnerSubscription[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({ search: "", partner_id: "", status: "", payment_method: "", plan_id: "", billing_interval: "" });
  const [showCreate, setShowCreate] = useState(false);
  const [editSub, setEditSub] = useState<PartnerSubscription | null>(null);
  const [cancelSub, setCancelSub] = useState<PartnerSubscription | null>(null);
  const [logsUrl, setLogsUrl] = useState("");
  const [showAuditLogs, setShowAuditLogs] = useState(false);
  const LIMIT = 20;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), limit: String(LIMIT) });
      if (filters.search) params.set("search", filters.search);
      if (filters.partner_id) params.set("partner_id", filters.partner_id);
      if (filters.status && filters.status !== "all") params.set("status", filters.status);
      if (filters.payment_method && filters.payment_method !== "all") params.set("payment_method", filters.payment_method);
      if (filters.plan_id && filters.plan_id !== "all") params.set("plan_id", filters.plan_id);
      if (filters.billing_interval && filters.billing_interval !== "all") params.set("billing_interval", filters.billing_interval);
      const [subsRes, statsRes] = await Promise.all([
        api.get(`/admin/partner-subscriptions?${params}`),
        api.get("/admin/partner-subscriptions/stats"),
      ]);
      setSubs(subsRes.data.subscriptions || []);
      setTotal(subsRes.data.total || 0);
      setStats(statsRes.data);
    } catch { toast.error("Failed to load subscriptions"); }
    finally { setLoading(false); }
  }, [page, filters]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    Promise.all([
      api.get("/admin/tenants"),
      api.get("/admin/plans"),
    ]).then(([t, p]) => {
      setTenants((t.data.tenants || []).filter((x: any) => x.code !== "automate-accounts"));
      setPlans((p.data.plans || []).filter((x: Plan) => x.is_active));
    }).catch(() => {});
  }, []);

  const handleCancel = async () => {
    if (!cancelSub) return;
    try {
      await api.patch(`/admin/partner-subscriptions/${cancelSub.id}/cancel`);
      toast.success("Subscription cancelled");
      setCancelSub(null);
      load();
    } catch (e: any) { toast.error(e.response?.data?.detail || "Cancel failed"); }
  };

  const fmtDate = (d?: string) => d ? new Date(d).toLocaleDateString() : "—";
  const fmtAmt = (amount: number, currency: string) =>
    new Intl.NumberFormat("en-GB", { style: "currency", currency }).format(amount);

  return (
    <div className="space-y-5" data-testid="partner-subscriptions-tab">
      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard label="Total Subscriptions" value={stats.total} />
          <StatCard label="Active" value={stats.active} />
          <StatCard label="New This Month" value={stats.new_this_month} />
          <StatCard label="Cancelled" value={stats.by_status?.cancelled || 0} />
        </div>
      )}

      {/* MRR / ARR revenue blocks */}
      {stats && (Object.keys(stats.mrr || {}).length > 0 || Object.keys(stats.arr || {}).length > 0) && (
        <div className="flex gap-3 flex-wrap">
          {Object.entries(stats.mrr || {}).map(([currency, val]) => (
            <div key={`mrr-${currency}`} className="bg-emerald-50 border border-emerald-200 rounded-lg px-4 py-2 text-sm">
              <span className="text-slate-500 text-xs">MRR</span>
              <p className="font-bold text-emerald-700">{fmtAmt(val, currency)}</p>
            </div>
          ))}
          {Object.entries(stats.arr || {}).map(([currency, val]) => (
            <div key={`arr-${currency}`} className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-2 text-sm">
              <span className="text-slate-500 text-xs">ARR</span>
              <p className="font-bold text-blue-700">{fmtAmt(val, currency)}</p>
            </div>
          ))}
        </div>
      )}

      {/* Filters + Create */}
      <div className="flex items-center gap-2 flex-wrap">
        <Input
          placeholder="Search subscriptions…"
          value={filters.search}
          onChange={e => { setFilters(f => ({ ...f, search: e.target.value })); setPage(1); }}
          className="w-48"
          data-testid="subs-search"
        />
        <Select value={filters.partner_id || "all"} onValueChange={v => { setFilters(f => ({ ...f, partner_id: v === "all" ? "" : v })); setPage(1); }}>
          <SelectTrigger className="w-44"><SelectValue placeholder="All partners" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All partners</SelectItem>
            {tenants.map(t => <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={filters.status || "all"} onValueChange={v => { setFilters(f => ({ ...f, status: v === "all" ? "" : v })); setPage(1); }}>
          <SelectTrigger className="w-36"><SelectValue placeholder="All statuses" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            {STATUSES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={filters.plan_id || "all"} onValueChange={v => { setFilters(f => ({ ...f, plan_id: v === "all" ? "" : v })); setPage(1); }}>
          <SelectTrigger className="w-36"><SelectValue placeholder="All plans" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All plans</SelectItem>
            {plans.map(p => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={filters.billing_interval || "all"} onValueChange={v => { setFilters(f => ({ ...f, billing_interval: v === "all" ? "" : v })); setPage(1); }}>
          <SelectTrigger className="w-32"><SelectValue placeholder="All intervals" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All intervals</SelectItem>
            {BILLING_INTERVALS.map(i => <SelectItem key={i} value={i}>{i}</SelectItem>)}
          </SelectContent>
        </Select>
        <Button size="sm" variant="outline" onClick={load}><RefreshCw className="h-4 w-4" /></Button>
        <div className="ml-auto">
          <Button onClick={() => setShowCreate(true)} data-testid="create-partner-sub-btn">
            <Plus className="h-4 w-4 mr-1" /> New Subscription
          </Button>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-sm" data-testid="partner-subscriptions-table">
          <thead className="bg-slate-50 text-xs text-slate-500 uppercase">
            <tr>
              <th className="text-left px-4 py-3">Sub #</th>
              <th className="text-left px-4 py-3">Partner</th>
              <th className="text-left px-4 py-3">Plan</th>
              <th className="text-left px-4 py-3">Amount</th>
              <th className="text-left px-4 py-3">Interval</th>
              <th className="text-left px-4 py-3">Method</th>
              <th className="text-left px-4 py-3">Status</th>
              <th className="text-left px-4 py-3">Next Billing</th>
              <th className="text-right px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={9} className="text-center py-8 text-slate-400">Loading…</td></tr>
            ) : subs.length === 0 ? (
              <tr><td colSpan={9} className="text-center py-8 text-slate-400">No subscriptions found.</td></tr>
            ) : subs.map(sub => (
              <tr key={sub.id} className="border-t border-slate-100 hover:bg-slate-50" data-testid={`sub-row-${sub.id}`}>
                <td className="px-4 py-3 font-mono text-xs text-slate-600">{sub.subscription_number}</td>
                <td className="px-4 py-3 font-medium">{sub.partner_name}</td>
                <td className="px-4 py-3 text-slate-500 text-xs">{sub.plan_name || "—"}</td>
                <td className="px-4 py-3 font-semibold">{fmtAmt(sub.amount, sub.currency)}</td>
                <td className="px-4 py-3 text-slate-500 capitalize">{sub.billing_interval}</td>
                <td className="px-4 py-3 text-slate-500 capitalize">{sub.payment_method.replace("_", " ")}</td>
                <td className="px-4 py-3">
                  <Badge className={`text-[11px] ${STATUS_COLORS[sub.status] || "bg-slate-100"}`}>{sub.status}</Badge>
                </td>
                <td className="px-4 py-3 text-slate-500 text-xs">{fmtDate(sub.next_billing_date)}</td>
                <td className="px-4 py-3">
                  <div className="flex justify-end gap-1">
                    <Button size="sm" variant="ghost" title="Audit Logs" onClick={() => { setLogsUrl(`/admin/partner-subscriptions/${sub.id}`); setShowAuditLogs(true); }} data-testid={`sub-logs-${sub.id}`}>
                      <ScrollText className="h-4 w-4" />
                    </Button>
                    <Button size="sm" variant="ghost" title="Edit" onClick={() => setEditSub(sub)} data-testid={`edit-sub-${sub.id}`}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    {sub.status !== "cancelled" && (
                      <Button size="sm" variant="ghost" className="text-red-400 hover:text-red-600" title="Cancel" onClick={() => setCancelSub(sub)} data-testid={`cancel-sub-${sub.id}`}>
                        <XCircle className="h-4 w-4" />
                      </Button>
                    )}
                    {sub.payment_url && (
                      <Button size="sm" variant="ghost" title="Open payment link" onClick={() => window.open(sub.payment_url, "_blank")} data-testid={`sub-paylink-${sub.id}`}>
                        <ExternalLink className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {total > LIMIT && (
        <div className="flex justify-end gap-2">
          <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Prev</Button>
          <span className="text-sm text-slate-500 py-1.5">Page {page} of {Math.ceil(total / LIMIT)}</span>
          <Button size="sm" variant="outline" disabled={page >= Math.ceil(total / LIMIT)} onClick={() => setPage(p => p + 1)}>Next</Button>
        </div>
      )}

      {/* Modals */}
      {showCreate && <SubFormModal sub={null} tenants={tenants} plans={plans} onClose={() => setShowCreate(false)} onSaved={() => { setShowCreate(false); load(); }} />}
      {editSub && <SubFormModal sub={editSub} tenants={tenants} plans={plans} onClose={() => setEditSub(null)} onSaved={() => { setEditSub(null); load(); }} />}

      {/* Cancel Confirmation */}
      {cancelSub && (
        <AlertDialog open onOpenChange={() => setCancelSub(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Cancel subscription {cancelSub.subscription_number}?</AlertDialogTitle>
              <AlertDialogDescription>
                This will cancel the subscription for <strong>{cancelSub.partner_name}</strong>.
                If linked to Stripe, it will be set to cancel at period end.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Keep Active</AlertDialogCancel>
              <AlertDialogAction className="bg-red-600 hover:bg-red-700" onClick={handleCancel} data-testid="confirm-cancel-partner-sub">
                Yes, Cancel
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}

      {/* Audit Logs Dialog */}
      <AuditLogDialog
        open={showAuditLogs}
        onOpenChange={setShowAuditLogs}
        title="Partner Subscription Audit Logs"
        logsUrl={logsUrl}
      />
    </div>
  );
}
