import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { RefreshCw, XCircle } from "lucide-react";

const STATUS_COLORS: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-700",
  pending: "bg-blue-100 text-blue-700",
  unpaid: "bg-amber-100 text-amber-700",
  paused: "bg-orange-100 text-orange-700",
  cancelled: "bg-slate-100 text-slate-500",
};

const STATUSES = ["pending", "active", "unpaid", "paused", "cancelled"];

type PartnerSub = {
  id: string;
  subscription_number: string;
  plan_name?: string;
  description?: string;
  amount: number;
  currency: string;
  billing_interval: string;
  status: string;
  payment_method: string;
  start_date?: string;
  next_billing_date?: string;
  term_months?: number;
  auto_cancel_on_termination?: boolean;
  contract_end_date?: string;
  cancelled_at?: string;
  created_at: string;
};

function termLockInfo(sub: PartnerSub): { locked: boolean; endDate: string } {
  if (!sub.term_months || sub.term_months <= 0 || !sub.contract_end_date) {
    return { locked: false, endDate: "" };
  }
  const endDt = new Date(sub.contract_end_date);
  const now = new Date();
  if (now < endDt) {
    return { locked: true, endDate: endDt.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }) };
  }
  return { locked: false, endDate: endDt.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }) };
}

export function MySubscriptionsTab() {
  const [subs, setSubs] = useState<PartnerSub[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [cancelSub, setCancelSub] = useState<PartnerSub | null>(null);
  const LIMIT = 20;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), limit: String(LIMIT) });
      if (search) params.set("search", search);
      if (status && status !== "all") params.set("status", status);
      const { data } = await api.get(`/partner/my-subscriptions?${params}`);
      setSubs(data.subscriptions || []);
      setTotal(data.total || 0);
    } catch { toast.error("Failed to load subscriptions"); }
    finally { setLoading(false); }
  }, [page, search, status]);

  useEffect(() => { load(); }, [load]);

  const handleCancel = async () => {
    if (!cancelSub) return;
    try {
      await api.post(`/partner/my-subscriptions/${cancelSub.id}/cancel`);
      toast.success("Subscription cancelled");
      setCancelSub(null);
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Cancel failed");
      setCancelSub(null);
    }
  };

  const fmtAmt = (amount: number, currency: string) =>
    new Intl.NumberFormat("en-GB", { style: "currency", currency }).format(amount);

  return (
    <div className="space-y-4" data-testid="my-subscriptions-tab">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">My Subscriptions</h2>
        <p className="text-sm text-slate-500">Your active platform subscriptions.</p>
      </div>

      <div className="flex gap-2 flex-wrap">
        <Input
          placeholder="Search subscriptions…"
          value={search}
          onChange={e => { setSearch(e.target.value); setPage(1); }}
          className="w-48"
          data-testid="my-subs-search"
        />
        <Select value={status} onValueChange={v => { setStatus(v); setPage(1); }}>
          <SelectTrigger className="w-36"><SelectValue placeholder="All statuses" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            {STATUSES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
          </SelectContent>
        </Select>
        <Button size="sm" variant="outline" onClick={load}><RefreshCw className="h-4 w-4" /></Button>
      </div>

      <div className="rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-sm" data-testid="my-subscriptions-table">
          <thead className="bg-slate-50 text-xs text-slate-500 uppercase">
            <tr>
              <th className="text-left px-4 py-3">Sub #</th>
              <th className="text-left px-4 py-3">Plan</th>
              <th className="text-left px-4 py-3">Amount</th>
              <th className="text-left px-4 py-3">Interval</th>
              <th className="text-left px-4 py-3">Status</th>
              <th className="text-left px-4 py-3">Contract End</th>
              <th className="text-left px-4 py-3">Next Billing</th>
              <th className="text-right px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} className="text-center py-8 text-slate-400">Loading…</td></tr>
            ) : subs.length === 0 ? (
              <tr><td colSpan={8} className="text-center py-8 text-slate-400">No subscriptions found.</td></tr>
            ) : subs.map(sub => {
              const { locked, endDate } = termLockInfo(sub);
              return (
                <tr key={sub.id} className="border-t border-slate-100 hover:bg-slate-50" data-testid={`my-sub-row-${sub.id}`}>
                  <td className="px-4 py-3 font-mono text-xs text-slate-600">{sub.subscription_number}</td>
                  <td className="px-4 py-3 font-medium">{sub.plan_name || sub.description || "—"}</td>
                  <td className="px-4 py-3 font-semibold">{fmtAmt(sub.amount, sub.currency)}</td>
                  <td className="px-4 py-3 text-slate-500 capitalize">{sub.billing_interval}</td>
                  <td className="px-4 py-3">
                    <Badge className={`text-[11px] ${STATUS_COLORS[sub.status] || ""}`}>{sub.status}</Badge>
                  </td>
                  <td className="px-4 py-3 text-slate-500 text-xs">
                    {sub.term_months ? (
                      <span className={locked ? "text-orange-600 font-medium" : "text-slate-500"}>
                        {endDate} {locked ? "🔒" : ""}
                      </span>
                    ) : "No lock-in"}
                  </td>
                  <td className="px-4 py-3 text-slate-500 text-xs">
                    {sub.next_billing_date ? new Date(sub.next_billing_date).toLocaleDateString() : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end">
                      {sub.status !== "cancelled" && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className={locked ? "text-slate-300 cursor-not-allowed" : "text-red-400 hover:text-red-600"}
                          title={locked ? `Locked until ${endDate}` : "Cancel subscription"}
                          onClick={() => !locked && setCancelSub(sub)}
                          disabled={locked}
                          data-testid={`cancel-my-sub-${sub.id}`}
                        >
                          <XCircle className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {total > LIMIT && (
        <div className="flex justify-end gap-2">
          <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Prev</Button>
          <span className="text-sm text-slate-500 py-1.5">Page {page} of {Math.ceil(total / LIMIT)}</span>
          <Button size="sm" variant="outline" disabled={page >= Math.ceil(total / LIMIT)} onClick={() => setPage(p => p + 1)}>Next</Button>
        </div>
      )}

      {cancelSub && (
        <AlertDialog open onOpenChange={() => setCancelSub(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Cancel subscription {cancelSub.subscription_number}?</AlertDialogTitle>
              <AlertDialogDescription>
                This will cancel your <strong>{cancelSub.plan_name || "subscription"}</strong>.
                This action cannot be undone.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Keep Active</AlertDialogCancel>
              <AlertDialogAction className="bg-red-600 hover:bg-red-700" onClick={handleCancel} data-testid="confirm-cancel-my-sub">
                Yes, Cancel
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}
    </div>
  );
}
