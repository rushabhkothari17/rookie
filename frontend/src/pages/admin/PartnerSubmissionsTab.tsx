import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Loader2, RefreshCw, CheckCircle, XCircle, Clock, Search } from "lucide-react";

interface Submission {
  id: string;
  partner_id: string;
  partner_name: string;
  type: string;
  current_plan_name: string;
  requested_plan_name: string;
  message: string;
  status: "pending" | "approved" | "rejected";
  effective_date: string;
  created_at: string;
  resolved_at?: string;
  resolved_by?: string;
  resolution_note?: string;
}

const STATUS_MAP: Record<string, { color: string; label: string }> = {
  pending:  { color: "bg-amber-100 text-amber-700",     label: "Pending" },
  approved: { color: "bg-emerald-100 text-emerald-700", label: "Approved" },
  rejected: { color: "bg-red-100 text-red-700",         label: "Rejected" },
};

const TYPE_LABELS: Record<string, string> = {
  plan_downgrade: "Plan Downgrade",
  support: "Support Request",
};

export function PartnerSubmissionsTab() {
  const [items, setItems] = useState<Submission[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("pending");
  const [search, setSearch] = useState("");

  // Resolve dialog state
  const [selected, setSelected] = useState<Submission | null>(null);
  const [resolveAction, setResolveAction] = useState<"approve" | "reject">("approve");
  const [resolutionNote, setResolutionNote] = useState("");
  const [resolving, setResolving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = { per_page: 50 };
      if (statusFilter && statusFilter !== "all") params.status = statusFilter;
      const r = await api.get("/admin/partner-submissions", { params });
      setItems(r.data.submissions || []);
    } catch {
      toast.error("Failed to load submissions");
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { load(); }, [load]);

  const filtered = items.filter(i => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      i.partner_name?.toLowerCase().includes(q) ||
      i.current_plan_name?.toLowerCase().includes(q) ||
      i.requested_plan_name?.toLowerCase().includes(q)
    );
  });

  const openResolve = (item: Submission, action: "approve" | "reject") => {
    setSelected(item);
    setResolveAction(action);
    setResolutionNote("");
  };

  const handleResolve = async () => {
    if (!selected) return;
    setResolving(true);
    try {
      await api.put(`/admin/partner-submissions/${selected.id}`, {
        action: resolveAction,
        resolution_note: resolutionNote,
      });
      toast.success(`Submission ${resolveAction === "approve" ? "approved" : "rejected"}`);
      setSelected(null);
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to resolve");
    } finally {
      setResolving(false);
    }
  };

  return (
    <div className="space-y-4" data-testid="partner-submissions-tab">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h2 className="text-base font-semibold text-slate-900">Partner Submissions</h2>
          <p className="text-sm text-slate-500 mt-0.5">Review and approve or reject partner plan change requests.</p>
        </div>
        <Button variant="outline" size="sm" onClick={load} data-testid="submissions-admin-refresh-btn">
          <RefreshCw size={13} className="mr-1.5" />Refresh
        </Button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[180px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input
            className="pl-8 h-9 text-sm"
            placeholder="Search partner, plan..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            data-testid="submissions-search"
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter} data-testid="submissions-status-filter">
          <SelectTrigger className="w-36 h-9 text-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="approved">Approved</SelectItem>
            <SelectItem value="rejected">Rejected</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="animate-spin text-slate-400" size={24} />
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-200 p-10 text-center text-sm text-slate-400" data-testid="submissions-admin-empty">
          No submissions found.
        </div>
      ) : (
        <div className="rounded-2xl border border-slate-200 overflow-hidden">
          <Table data-testid="submissions-admin-table">
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead className="text-xs font-semibold text-slate-500">Partner</TableHead>
                <TableHead className="text-xs font-semibold text-slate-500">Type</TableHead>
                <TableHead className="text-xs font-semibold text-slate-500">From → To</TableHead>
                <TableHead className="text-xs font-semibold text-slate-500">Effective</TableHead>
                <TableHead className="text-xs font-semibold text-slate-500">Submitted</TableHead>
                <TableHead className="text-xs font-semibold text-slate-500">Status</TableHead>
                <TableHead className="text-xs font-semibold text-slate-500 text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map(item => {
                const s = STATUS_MAP[item.status] || STATUS_MAP.pending;
                return (
                  <TableRow key={item.id} className="hover:bg-slate-50/50" data-testid={`submission-row-${item.id}`}>
                    <TableCell className="font-medium text-sm" data-testid={`submission-partner-${item.id}`}>{item.partner_name}</TableCell>
                    <TableCell className="text-xs text-slate-500">{TYPE_LABELS[item.type] || item.type}</TableCell>
                    <TableCell className="text-xs">
                      <span className="text-slate-500">{item.current_plan_name}</span>
                      {item.requested_plan_name && (
                        <><span className="mx-1 text-slate-300">→</span><span className="font-medium text-slate-800">{item.requested_plan_name}</span></>
                      )}
                    </TableCell>
                    <TableCell className="text-xs text-slate-500">{item.effective_date?.slice(0, 10) || "—"}</TableCell>
                    <TableCell className="text-xs text-slate-500">{item.created_at.slice(0, 10)}</TableCell>
                    <TableCell>
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${s.color}`} data-testid={`submission-status-badge-${item.id}`}>
                        {s.label}
                      </span>
                      {item.resolution_note && (
                        <p className="text-xs text-slate-400 mt-0.5 max-w-[140px] truncate" title={item.resolution_note}>{item.resolution_note}</p>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      {item.status === "pending" ? (
                        <div className="flex items-center justify-end gap-1.5">
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-7 text-xs border-emerald-300 text-emerald-700 hover:bg-emerald-50"
                            onClick={() => openResolve(item, "approve")}
                            data-testid={`approve-btn-${item.id}`}
                          >
                            <CheckCircle size={11} className="mr-1" />Approve
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-7 text-xs border-red-200 text-red-600 hover:bg-red-50"
                            onClick={() => openResolve(item, "reject")}
                            data-testid={`reject-btn-${item.id}`}
                          >
                            <XCircle size={11} className="mr-1" />Reject
                          </Button>
                        </div>
                      ) : (
                        <span className="text-xs text-slate-400">{item.resolved_by || "—"}</span>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Resolve Dialog */}
      <Dialog open={!!selected} onOpenChange={v => { if (!v) setSelected(null); }}>
        <DialogContent data-testid="resolve-submission-dialog">
          <DialogHeader>
            <DialogTitle>
              {resolveAction === "approve" ? "Approve" : "Reject"} Submission
            </DialogTitle>
          </DialogHeader>
          {selected && (
            <div className="space-y-4 py-2">
              <div className="rounded-xl bg-slate-50 p-4 text-sm space-y-1">
                <p><span className="text-slate-500">Partner:</span> <span className="font-medium">{selected.partner_name}</span></p>
                <p><span className="text-slate-500">Request:</span> {TYPE_LABELS[selected.type] || selected.type}</p>
                {selected.type === "plan_downgrade" && (
                  <p><span className="text-slate-500">Downgrade to:</span> <span className="font-medium">{selected.requested_plan_name}</span></p>
                )}
                {selected.message && <p className="text-slate-500 italic">"{selected.message}"</p>}
              </div>
              <div>
                <Label>Resolution Note (optional)</Label>
                <Textarea
                  className="mt-1"
                  placeholder="Leave a note for the partner..."
                  value={resolutionNote}
                  onChange={e => setResolutionNote(e.target.value)}
                  data-testid="resolution-note-input"
                  rows={3}
                />
              </div>
              {resolveAction === "approve" && selected.type === "plan_downgrade" && (
                <p className="text-xs text-emerald-700 bg-emerald-50 rounded-lg px-3 py-2">
                  Approving will immediately apply the plan change to {selected.partner_name}.
                </p>
              )}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setSelected(null)}>Cancel</Button>
            <Button
              variant={resolveAction === "approve" ? "default" : "destructive"}
              onClick={handleResolve}
              disabled={resolving}
              data-testid="confirm-resolve-btn"
            >
              {resolving ? <Loader2 size={13} className="mr-1.5 animate-spin" /> : null}
              {resolveAction === "approve" ? "Approve" : "Reject"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
