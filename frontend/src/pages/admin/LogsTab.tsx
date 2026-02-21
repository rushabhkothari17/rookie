import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { RefreshCw, X, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, Activity } from "lucide-react";

const SOURCES = ["admin_ui", "customer_ui", "api", "webhook", "cron", "system"];
const ENTITY_TYPES = [
  "Order", "Subscription", "Customer", "Product", "Article", "Setting",
  "Payment", "User", "OverrideCode", "PromoCode", "BankTransaction",
  "QuoteRequest", "Category", "Terms",
];
const ACTOR_TYPES = [
  { value: "admin", label: "Admin", color: "bg-indigo-100 text-indigo-700" },
  { value: "user", label: "User", color: "bg-emerald-100 text-emerald-700" },
  { value: "system", label: "System", color: "bg-slate-100 text-slate-600" },
  { value: "webhook", label: "Webhook", color: "bg-violet-100 text-violet-700" },
];
const PER_PAGE_OPTIONS = [25, 50, 100];

const actorTypeBadge = (type: string) => {
  const cfg = ACTOR_TYPES.find((a) => a.value === type);
  return cfg
    ? <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold ${cfg.color}`}>{cfg.label}</span>
    : <span className="text-[10px] text-slate-400">{type || "—"}</span>;
};

const entityBadge = (type: string) => {
  const colors: Record<string, string> = {
    Order: "bg-blue-50 text-blue-700",
    Subscription: "bg-teal-50 text-teal-700",
    Customer: "bg-orange-50 text-orange-700",
    Product: "bg-cyan-50 text-cyan-700",
    Article: "bg-pink-50 text-pink-700",
    User: "bg-indigo-50 text-indigo-700",
    BankTransaction: "bg-amber-50 text-amber-700",
    Setting: "bg-slate-100 text-slate-600",
  };
  const cls = colors[type] || "bg-slate-100 text-slate-600";
  return <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${cls}`}>{type}</span>;
};

const relTime = (iso: string) => {
  const diff = Date.now() - new Date(iso).getTime();
  const s = Math.floor(diff / 1000);
  if (s < 60) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d}d ago`;
  return new Date(iso).toLocaleDateString();
};

const initFilters = {
  actor: "", actor_type: "", source: "", entity_type: "",
  entity_id: "", action: "", success: "", severity: "",
  date_from: "", date_to: "", q: "",
};

export function LogsTab() {
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(50);
  const [selectedLog, setSelectedLog] = useState<any>(null);
  const [filters, setFilters] = useState(initFilters);
  const [pendingFilters, setPendingFilters] = useState(initFilters);

  const buildParams = useCallback(
    (p: number, pp: number, f: typeof initFilters) => {
      const q: Record<string, string> = { page: String(p), limit: String(pp) };
      if (f.actor) q.actor = f.actor;
      if (f.actor_type) q.actor_type = f.actor_type;
      if (f.source) q.source = f.source;
      if (f.entity_type) q.entity_type = f.entity_type;
      if (f.entity_id) q.entity_id = f.entity_id;
      if (f.action) q.action = f.action;
      if (f.success) q.success = f.success;
      if (f.severity) q.severity = f.severity;
      if (f.date_from) q.date_from = f.date_from;
      if (f.date_to) q.date_to = f.date_to;
      if (f.q) q.q = f.q;
      return q;
    },
    []
  );

  const load = useCallback(
    async (p: number, pp: number, f: typeof initFilters) => {
      setLoading(true);
      try {
        const res = await api.get("/admin/audit-logs", { params: buildParams(p, pp, f) });
        setLogs(res.data.logs || []);
        setTotal(res.data.total || 0);
        setTotalPages(res.data.total_pages || 1);
      } catch {
        toast.error("Failed to load logs");
      } finally {
        setLoading(false);
      }
    },
    [buildParams]
  );

  useEffect(() => { load(1, perPage, initFilters); }, []);

  const handleApply = () => {
    setFilters(pendingFilters);
    setPage(1);
    load(1, perPage, pendingFilters);
  };

  const handleReset = () => {
    setPendingFilters(initFilters);
    setFilters(initFilters);
    setPage(1);
    load(1, perPage, initFilters);
  };

  const handlePageChange = (p: number) => {
    setPage(p);
    load(p, perPage, filters);
  };

  const handlePerPageChange = (pp: number) => {
    setPerPage(pp);
    setPage(1);
    load(1, pp, filters);
  };

  const setP = (k: keyof typeof initFilters) => (v: string) =>
    setPendingFilters((f) => ({ ...f, [k]: v }));

  const FilterSelect = ({ field, label, options, allLabel = "All" }: {
    field: keyof typeof initFilters; label: string; options: string[] | { value: string; label: string }[]; allLabel?: string;
  }) => (
    <div className="space-y-0.5">
      <label className="text-[10px] uppercase tracking-wide font-medium text-slate-500">{label}</label>
      <Select
        value={pendingFilters[field] || "__all__"}
        onValueChange={(v) => setP(field)(v === "__all__" ? "" : v)}
      >
        <SelectTrigger className="h-8 text-sm" data-testid={`logs-filter-${field}`}>
          <SelectValue placeholder={allLabel} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="__all__">{allLabel}</SelectItem>
          {(options as any[]).map((o) => (
            <SelectItem key={typeof o === "string" ? o : o.value} value={typeof o === "string" ? o : o.value}>
              {typeof o === "string" ? o : o.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );

  const FilterText = ({ field, label, placeholder }: { field: keyof typeof initFilters; label: string; placeholder?: string }) => (
    <div className="space-y-0.5">
      <label className="text-[10px] uppercase tracking-wide font-medium text-slate-500">{label}</label>
      <div className="relative">
        <Input
          value={pendingFilters[field]}
          onChange={(e) => setP(field)(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") handleApply(); }}
          placeholder={placeholder || label}
          className="h-8 text-sm pr-6"
          data-testid={`logs-filter-${field}-input`}
        />
        {pendingFilters[field] && (
          <button className="absolute right-1.5 top-1.5 text-slate-400 hover:text-slate-600" onClick={() => setP(field)("")}>
            <X size={12} />
          </button>
        )}
      </div>
    </div>
  );

  const startItem = (page - 1) * perPage + 1;
  const endItem = Math.min(page * perPage, total);

  return (
    <div className="space-y-4" data-testid="admin-logs-tab">

      {/* Header + Stats */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity size={16} className="text-slate-500" />
          <span className="text-sm font-semibold text-slate-700">Audit Trail</span>
          {!loading && (
            <span className="text-xs text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full font-mono">
              {total.toLocaleString()} events
            </span>
          )}
        </div>
        <Button
          variant="outline"
          size="sm"
          className="gap-1 h-8 text-xs"
          onClick={() => load(page, perPage, filters)}
          disabled={loading}
          data-testid="logs-refresh-btn"
        >
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
          Refresh
        </Button>
      </div>

      {/* Filters */}
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Filters</h3>
          <Button variant="ghost" size="sm" onClick={handleReset} className="text-xs h-7 gap-1 text-slate-500">
            <X size={11} /> Reset all
          </Button>
        </div>

        {/* Row 1 */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <FilterText field="q" label="Search" placeholder="action, desc, actor…" />
          <FilterText field="actor" label="Actor email" placeholder="email or ID" />
          <FilterSelect
            field="actor_type"
            label="Actor type"
            allLabel="All types"
            options={ACTOR_TYPES.map((a) => ({ value: a.value, label: a.label }))}
          />
          <FilterSelect field="entity_type" label="Entity type" options={ENTITY_TYPES} allLabel="All entities" />
          <FilterText field="action" label="Action" placeholder="e.g. ORDER_PAID" />
          <FilterText field="entity_id" label="Entity ID" placeholder="exact ID" />
        </div>

        {/* Row 2 */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <FilterSelect field="source" label="Source" options={SOURCES} allLabel="All sources" />
          <FilterSelect
            field="success"
            label="Status"
            allLabel="All"
            options={[{ value: "true", label: "Success" }, { value: "false", label: "Failure" }]}
          />
          <FilterSelect
            field="severity"
            label="Severity"
            allLabel="All"
            options={[{ value: "info", label: "Info" }, { value: "warn", label: "Warn" }, { value: "error", label: "Error" }]}
          />
          <div className="space-y-0.5">
            <label className="text-[10px] uppercase tracking-wide font-medium text-slate-500">Date from</label>
            <Input type="date" value={pendingFilters.date_from} onChange={(e) => setP("date_from")(e.target.value)} className="h-8 text-sm" />
          </div>
          <div className="space-y-0.5">
            <label className="text-[10px] uppercase tracking-wide font-medium text-slate-500">Date to</label>
            <Input type="date" value={pendingFilters.date_to} onChange={(e) => setP("date_to")(e.target.value)} className="h-8 text-sm" />
          </div>
          <div className="flex items-end">
            <Button onClick={handleApply} size="sm" className="gap-1 h-8 w-full" data-testid="logs-apply-btn">
              <RefreshCw size={12} /> Apply
            </Button>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-200 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-slate-50 border-b border-slate-200">
              <TableHead className="text-xs font-semibold text-slate-600 w-32">Time</TableHead>
              <TableHead className="text-xs font-semibold text-slate-600">Action</TableHead>
              <TableHead className="text-xs font-semibold text-slate-600 max-w-xs">Description</TableHead>
              <TableHead className="text-xs font-semibold text-slate-600 w-24">Actor Type</TableHead>
              <TableHead className="text-xs font-semibold text-slate-600">Actor</TableHead>
              <TableHead className="text-xs font-semibold text-slate-600 w-28">Entity</TableHead>
              <TableHead className="text-xs font-semibold text-slate-600 w-20">Source</TableHead>
              <TableHead className="text-xs font-semibold text-slate-600 w-16">Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && logs.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center text-slate-400 py-12 text-sm">
                  <RefreshCw size={16} className="animate-spin inline mr-2" />Loading…
                </TableCell>
              </TableRow>
            ) : logs.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center text-slate-400 py-12 text-sm" data-testid="logs-empty">
                  No audit logs matching these filters.
                </TableCell>
              </TableRow>
            ) : (
              logs.map((log) => (
                <TableRow
                  key={log.id}
                  className="cursor-pointer hover:bg-slate-50 transition-colors text-sm"
                  onClick={() => setSelectedLog(log)}
                  data-testid={`log-row-${log.id}`}
                >
                  <TableCell className="py-2">
                    <span
                      className="text-xs text-slate-600 whitespace-nowrap"
                      title={log.occurred_at ? new Date(log.occurred_at).toLocaleString() : ""}
                    >
                      {log.occurred_at ? relTime(log.occurred_at) : "—"}
                    </span>
                    <div className="text-[10px] text-slate-400 font-mono">
                      {log.occurred_at ? new Date(log.occurred_at).toLocaleTimeString() : ""}
                    </div>
                  </TableCell>
                  <TableCell className="py-2">
                    <span className="font-mono text-xs text-slate-800 font-medium">{log.action}</span>
                  </TableCell>
                  <TableCell className="py-2 max-w-xs">
                    <span className="text-xs text-slate-700 line-clamp-2 leading-relaxed">{log.description}</span>
                  </TableCell>
                  <TableCell className="py-2">{actorTypeBadge(log.actor_type)}</TableCell>
                  <TableCell className="py-2">
                    <span className="text-xs text-slate-700 truncate block max-w-[140px]">
                      {log.actor_email || log.actor_id || "—"}
                    </span>
                    {log.actor_role && (
                      <span className="text-[10px] text-slate-400">{log.actor_role}</span>
                    )}
                  </TableCell>
                  <TableCell className="py-2">
                    {log.entity_type && entityBadge(log.entity_type)}
                    {log.entity_id && (
                      <div className="text-[10px] text-slate-400 font-mono mt-0.5 truncate max-w-[100px]">
                        {log.entity_id.slice(0, 8)}…
                      </div>
                    )}
                  </TableCell>
                  <TableCell className="py-2">
                    <span className="text-[10px] text-slate-500">{log.source || "—"}</span>
                  </TableCell>
                  <TableCell className="py-2">
                    <span
                      className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                        log.success === false
                          ? "bg-red-100 text-red-700"
                          : "bg-green-100 text-green-700"
                      }`}
                    >
                      {log.success === false ? "FAIL" : "OK"}
                    </span>
                    {log.severity && log.severity !== "info" && (
                      <div className={`mt-0.5 text-[10px] font-medium ${
                        log.severity === "error" ? "text-red-600" : "text-amber-600"
                      }`}>
                        {log.severity.toUpperCase()}
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-2 text-slate-500 text-xs">
          {total > 0 && !loading && (
            <span>Showing {startItem}–{endItem} of {total.toLocaleString()}</span>
          )}
          <span className="text-slate-300">|</span>
          <span>Per page:</span>
          {PER_PAGE_OPTIONS.map((n) => (
            <button
              key={n}
              onClick={() => handlePerPageChange(n)}
              className={`px-2 py-0.5 rounded text-xs transition-colors ${
                perPage === n
                  ? "bg-slate-800 text-white font-semibold"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {n}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="icon"
            className="h-7 w-7"
            onClick={() => handlePageChange(1)}
            disabled={page === 1 || loading}
            data-testid="logs-page-first"
          >
            <ChevronsLeft size={14} />
          </Button>
          <Button
            variant="outline"
            size="icon"
            className="h-7 w-7"
            onClick={() => handlePageChange(page - 1)}
            disabled={page === 1 || loading}
            data-testid="logs-page-prev"
          >
            <ChevronLeft size={14} />
          </Button>

          {/* Page number pills */}
          {(() => {
            const pages: (number | "…")[] = [];
            const delta = 2;
            for (let i = 1; i <= totalPages; i++) {
              if (i === 1 || i === totalPages || (i >= page - delta && i <= page + delta)) {
                pages.push(i);
              } else if (pages[pages.length - 1] !== "…") {
                pages.push("…");
              }
            }
            return pages.map((p, idx) =>
              p === "…" ? (
                <span key={`ellipsis-${idx}`} className="px-1 text-slate-400 text-xs">…</span>
              ) : (
                <button
                  key={p}
                  onClick={() => handlePageChange(p as number)}
                  disabled={loading}
                  className={`h-7 min-w-[28px] px-1.5 rounded text-xs font-medium transition-colors ${
                    page === p
                      ? "bg-slate-800 text-white"
                      : "border border-slate-200 text-slate-600 hover:bg-slate-50"
                  }`}
                  data-testid={`logs-page-${p}`}
                >
                  {p}
                </button>
              )
            );
          })()}

          <Button
            variant="outline"
            size="icon"
            className="h-7 w-7"
            onClick={() => handlePageChange(page + 1)}
            disabled={page === totalPages || loading}
            data-testid="logs-page-next"
          >
            <ChevronRight size={14} />
          </Button>
          <Button
            variant="outline"
            size="icon"
            className="h-7 w-7"
            onClick={() => handlePageChange(totalPages)}
            disabled={page === totalPages || loading}
            data-testid="logs-page-last"
          >
            <ChevronsRight size={14} />
          </Button>
        </div>
      </div>

      {/* Detail Dialog */}
      <Dialog open={!!selectedLog} onOpenChange={(o) => { if (!o) setSelectedLog(null); }}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="log-detail-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <span className="font-mono text-sm">{selectedLog?.action}</span>
              {selectedLog && actorTypeBadge(selectedLog.actor_type)}
            </DialogTitle>
          </DialogHeader>
          {selectedLog && (
            <div className="space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-3">
                {[
                  ["When", selectedLog.occurred_at ? new Date(selectedLog.occurred_at).toLocaleString() : "—"],
                  ["Actor", `${selectedLog.actor_email || selectedLog.actor_id || "—"}`],
                  ["Actor Type / Role", `${selectedLog.actor_type || "—"} / ${selectedLog.actor_role || "—"}`],
                  ["Source", selectedLog.source || "—"],
                  ["Entity", `${selectedLog.entity_type || "—"} / ${selectedLog.entity_id || "—"}`],
                  ["Request ID", selectedLog.request_id || "—"],
                  ["IP Address", selectedLog.ip_address || "—"],
                  ["Status", selectedLog.success === false ? "FAILED" : "OK"],
                  ["Severity", selectedLog.severity || "info"],
                ].map(([k, v]) => (
                  <div key={k as string}>
                    <p className="text-[10px] uppercase tracking-wide font-medium text-slate-500 mb-0.5">{k}</p>
                    <p className="text-slate-800 break-all text-sm">{v as string}</p>
                  </div>
                ))}
              </div>

              <div>
                <p className="text-[10px] uppercase tracking-wide font-medium text-slate-500 mb-1">Description</p>
                <p className="text-slate-800 text-sm leading-relaxed">{selectedLog.description}</p>
              </div>

              {selectedLog.error_message && (
                <div>
                  <p className="text-[10px] uppercase tracking-wide font-medium text-red-500 mb-1">Error</p>
                  <pre className="text-xs bg-red-50 text-red-800 p-3 rounded overflow-x-auto whitespace-pre-wrap">
                    {selectedLog.error_message}
                  </pre>
                </div>
              )}

              {selectedLog.before_json && Object.keys(selectedLog.before_json).length > 0 && (
                <div>
                  <p className="text-[10px] uppercase tracking-wide font-medium text-slate-500 mb-1">Before</p>
                  <pre className="text-xs bg-slate-50 border border-slate-200 rounded p-3 overflow-x-auto max-h-48">
                    {JSON.stringify(selectedLog.before_json, null, 2)}
                  </pre>
                </div>
              )}

              {selectedLog.after_json && Object.keys(selectedLog.after_json).length > 0 && (
                <div>
                  <p className="text-[10px] uppercase tracking-wide font-medium text-slate-500 mb-1">After</p>
                  <pre className="text-xs bg-slate-50 border border-slate-200 rounded p-3 overflow-x-auto max-h-48">
                    {JSON.stringify(selectedLog.after_json, null, 2)}
                  </pre>
                </div>
              )}

              {selectedLog.meta_json && Object.keys(selectedLog.meta_json).length > 0 && (
                <div>
                  <p className="text-[10px] uppercase tracking-wide font-medium text-slate-500 mb-1">Meta / Context</p>
                  <pre className="text-xs bg-slate-50 border border-slate-200 rounded p-3 overflow-x-auto max-h-48">
                    {JSON.stringify(selectedLog.meta_json, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
