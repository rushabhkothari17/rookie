import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Loader2, RefreshCw, CheckCircle, XCircle, Clock, FileText } from "lucide-react";

interface Submission {
  id: string;
  type: string;
  current_plan_name: string;
  requested_plan_name: string;
  message: string;
  status: "pending" | "approved" | "rejected";
  effective_date: string;
  created_at: string;
  resolved_at?: string;
  resolution_note?: string;
}

const STATUS_MAP: Record<string, { color: string; icon: React.ElementType; label: string }> = {
  pending:  { color: "bg-amber-100 text-amber-700",  icon: Clock,         label: "Pending Review" },
  approved: { color: "bg-emerald-100 text-emerald-700", icon: CheckCircle, label: "Approved" },
  rejected: { color: "bg-red-100 text-red-700",       icon: XCircle,      label: "Rejected" },
};

const TYPE_LABELS: Record<string, string> = {
  plan_downgrade: "Plan Downgrade",
  support: "Support Request",
};

export function MySubmissionsTab() {
  const [items, setItems] = useState<Submission[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get("/partner/submissions");
      setItems(r.data.submissions || []);
    } catch {
      toast.error("Failed to load submissions");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="animate-spin text-slate-400" size={24} />
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="my-submissions-tab">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-slate-900">My Submissions</h2>
        <Button variant="outline" size="sm" onClick={load} data-testid="submissions-refresh-btn">
          <RefreshCw size={13} className="mr-1.5" />Refresh
        </Button>
      </div>

      {items.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-200 p-10 text-center" data-testid="submissions-empty">
          <FileText size={24} className="text-slate-300 mx-auto mb-2" />
          <p className="text-sm text-slate-500">No submissions yet.</p>
          <p className="text-xs text-slate-400 mt-1">Use the Plan & Billing tab to request a downgrade.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map(item => {
            const s = STATUS_MAP[item.status] || STATUS_MAP.pending;
            const Icon = s.icon;
            return (
              <div key={item.id} className="rounded-2xl border border-slate-200 bg-white p-5" data-testid={`submission-card-${item.id}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-slate-900 text-sm">{TYPE_LABELS[item.type] || item.type}</span>
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${s.color}`} data-testid={`submission-status-${item.id}`}>
                        <Icon size={11} />
                        {s.label}
                      </span>
                    </div>
                    {item.type === "plan_downgrade" && (
                      <p className="text-sm text-slate-500 mt-1">
                        {item.current_plan_name} → <span className="font-medium text-slate-700">{item.requested_plan_name}</span>
                      </p>
                    )}
                    {item.message && (
                      <p className="text-xs text-slate-400 mt-1 italic">"{item.message}"</p>
                    )}
                    {item.resolution_note && (
                      <p className="text-xs text-slate-600 mt-1 bg-slate-50 rounded-lg px-3 py-1.5">
                        Admin note: {item.resolution_note}
                      </p>
                    )}
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-xs text-slate-400">Submitted</p>
                    <p className="text-xs font-medium text-slate-600">{item.created_at.slice(0, 10)}</p>
                    {item.status === "pending" && (
                      <>
                        <p className="text-xs text-slate-400 mt-1.5">Effective</p>
                        <p className="text-xs font-medium text-slate-600">{item.effective_date?.slice(0, 10) || "—"}</p>
                      </>
                    )}
                    {item.resolved_at && (
                      <>
                        <p className="text-xs text-slate-400 mt-1.5">Resolved</p>
                        <p className="text-xs font-medium text-slate-600">{item.resolved_at.slice(0, 10)}</p>
                      </>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
