import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import {
  RefreshCw, X, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight,
  Activity, AlertTriangle, Zap, Users, Shield, Clock,
} from "lucide-react";

// ── Constants ────────────────────────────────────────────────────────────────

const SOURCES = ["admin_ui", "customer_ui", "api", "webhook", "cron", "system"];

const ENTITY_TYPES = [
  // Commerce
  "Order", "Subscription", "Customer", "Product", "PromoCode",
  // Finance / Tax
  "TaxSettings", "TaxOverrideRule", "TaxTable", "InvoiceSettings", "InvoiceTemplate",
  // Users / Auth
  "User", "Tenant",
  // Files / Documents
  "Document", "FileUpload",
  // Integrations
  "IntegrationRequest", "SyncLog",
  // Zoho (lowercase as stored)
  "customers", "orders", "subscriptions",
  // Content
  "Article", "Category", "Terms", "Setting", "QuoteRequest",
];

const ACTOR_TYPES = [
  { value: "admin",   label: "Admin",   color: "bg-indigo-100 text-indigo-700" },
  { value: "user",    label: "User",    color: "bg-emerald-100 text-emerald-700" },
  { value: "system",  label: "System",  color: "bg-slate-100 text-slate-600" },
  { value: "webhook", label: "Webhook", color: "bg-violet-100 text-violet-700" },
];

const PER_PAGE_OPTIONS = [25, 50, 100];

const ENTITY_COLORS: Record<string, string> = {
  Order: "bg-blue-50 text-blue-700",
  Subscription: "bg-teal-50 text-teal-700",
  Customer: "bg-orange-50 text-orange-700", customers: "bg-orange-50 text-orange-700",
  Product: "bg-cyan-50 text-cyan-700",
  User: "bg-indigo-50 text-indigo-700",
  TaxSettings: "bg-amber-50 text-amber-700", TaxOverrideRule: "bg-amber-50 text-amber-700",
  TaxTable: "bg-amber-50 text-amber-700", InvoiceSettings: "bg-amber-50 text-amber-700",
  InvoiceTemplate: "bg-amber-50 text-amber-700",
  Document: "bg-rose-50 text-rose-700", FileUpload: "bg-rose-50 text-rose-700",
  IntegrationRequest: "bg-violet-50 text-violet-700",
  Tenant: "bg-sky-50 text-sky-700",
};

// ── Helpers ──────────────────────────────────────────────────────────────────

const actorTypeBadge = (type: string) => {
  const cfg = ACTOR_TYPES.find((a) => a.value === type?.toLowerCase());
  return cfg
    ? <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold ${cfg.color}`}>{cfg.label}</span>
    : <span className="text-[10px] text-slate-400">{type || "—"}</span>;
};

const entityBadge = (type: string) => {
  const cls = ENTITY_COLORS[type] || "bg-slate-100 text-slate-600";
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

const toDateStr = (d: Date) => d.toISOString().slice(0, 10);
const today = () => toDateStr(new Date());
const daysAgo = (n: number) => toDateStr(new Date(Date.now() - n * 86400000));

// ── Types ────────────────────────────────────────────────────────────────────

interface Stats {
  total: number;
  errors: number;
  today: number;
  by_actor_type: Record<string, number>;
  top_actions: { action: string; count: number }[];
  top_entity_types: { entity_type: string; count: number }[];
}

const initFilters = {
  actor: "", actor_type: "", source: "", entity_type: "",
  entity_id: "", action: "", success: "", severity: "",
  date_from: daysAgo(30), date_to: "", q: "",
};

// ── Component ─────────────────────────────────────────────────────────────────

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
  const [stats, setStats] = useState<Stats | null>(null);
  const statsLoaded = useRef(false);

  // ── Data loaders ──────────────────────────────────────────────────────────

  const buildParams = useCallback((p: number, pp: number, f: typeof initFilters) => {
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
  }, []);

  const loadLogs = useCallback(async (p: number, pp: number, f: typeof initFilters) => {
    setLoading(true);
    try {
      const res = await api.get("/admin/audit-logs", { params: buildParams(p, pp, f) });
      setLogs(res.data.logs || []);
      setTotal(res.data.total || 0);
      setTotalPages(res.data.total_pages || 1);
    } catch {
      toast.error("Failed to load audit logs");
    } finally {
      setLoading(false);
    }
  }, [buildParams]);

  const loadStats = useCallback(async (f: typeof initFilters) => {
    try {
      const params: Record<string, string> = {};
      if (f.date_from) params.date_from = f.date_from;
      if (f.date_to) params.date_to = f.date_to;
      const res = await api.get("/admin/audit-logs/stats", { params });
      setStats(res.data);
    } catch { /* non-critical */ }
  }, []);

  useEffect(() => {
    if (!statsLoaded.current) {
      statsLoaded.current = true;
      loadLogs(1, 50, initFilters);
      loadStats(initFilters);
    }
  }, []);  // eslint-disable-line

  // ── Actions ───────────────────────────────────────────────────────────────

  const handleApply = () => {
    setFilters(pendingFilters);
    setPage(1);
    loadLogs(1, perPage, pendingFilters);
    loadStats(pendingFilters);
  };

  const handleReset = () => {
    setPendingFilters(initFilters);
    setFilters(initFilters);
    setPage(1);
    loadLogs(1, perPage, initFilters);
    loadStats(initFilters);
  };

  const handlePageChange = (p: number) => {
    setPage(p);
    loadLogs(p, perPage, filters);
  };

  const handlePerPageChange = (pp: number) => {
    setPerPage(pp);
    setPage(1);
    loadLogs(1, pp, filters);
  };

  const setP = (k: keyof typeof initFilters) => (v: string) =>
    setPendingFilters((f) => ({ ...f, [k]: v }));

  const applyQuickRange = (from: string, to: string = "") => {
    const next = { ...pendingFilters, date_from: from, date_to: to };
    setPendingFilters(next);
    setFilters(next);
    setPage(1);
    loadLogs(1, perPage, next);
    loadStats(next);
  };

  // ── Filter subcomponents ──────────────────────────────────────────────────

  const FilterSelect = ({ field, label, options, allLabel = "All" }: {
    field: keyof typeof initFilters; label: string;
    options: string[] | { value: string; label: string }[]; allLabel?: string;
  }) => (
    <div className="space-y-0.5">
      <label className="text-[10px] uppercase tracking-wide font-medium text-slate-500">{label}</label>
      <Select value={pendingFilters[field] || "__all__"} onValueChange={(v) => setP(field)(v === "__all__" ? "" : v)}>
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

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-5" data-testid="admin-logs-tab">

      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity size={16} className="text-slate-500" />
          <span className="text-sm font-semibold text-slate-700">Audit Trail</span>
          {!loading && total > 0 && (
            <span className="text-xs text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full font-mono">
              {total.toLocaleString()} events
            </span>
          )}
        </div>
        <Button
          variant="outline" size="sm" className="gap-1 h-8 text-xs"
          onClick={() => { loadLogs(page, perPage, filters); loadStats(filters); }}
          disabled={loading}
          data-testid="logs-refresh-btn"
        >
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
          Refresh
        </Button>
      </div>

      {/* ── Stats Cards ── */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="audit-stats-panel">
          <StatCard
            icon={<Activity size={15} className="text-blue-500" />}
            label="Total Events"
            value={stats.total.toLocaleString()}
            sub={`in period`}
            color="border-blue-200 bg-blue-50/40"
            testid="stat-total"
          />
          <StatCard
            icon={<AlertTriangle size={15} className="text-red-500" />}
            label="Failures"
            value={stats.errors.toLocaleString()}
            sub={stats.total > 0 ? `${((stats.errors / stats.total) * 100).toFixed(1)}% error rate` : "0% error rate"}
            color={stats.errors > 0 ? "border-red-200 bg-red-50/40" : "border-slate-200 bg-slate-50/40"}
            testid="stat-errors"
          />
          <StatCard
            icon={<Clock size={15} className="text-emerald-500" />}
            label="Today"
            value={stats.today.toLocaleString()}
            sub="events so far"
            color="border-emerald-200 bg-emerald-50/40"
            testid="stat-today"
          />
          <div className="rounded-xl border border-slate-200 bg-slate-50/40 px-4 py-3 space-y-2" data-testid="stat-by-actor">
            <div className="flex items-center gap-1.5 mb-1">
              <Users size={15} className="text-slate-500" />
              <span className="text-[11px] font-semibold text-slate-600 uppercase tracking-wide">By Actor</span>
            </div>
            {Object.entries(stats.by_actor_type).slice(0, 4).map(([type, count]) => {
              const pct = stats.total > 0 ? Math.round((count / stats.total) * 100) : 0;
              const cfg = ACTOR_TYPES.find((a) => a.value === type);
              return (
                <div key={type} className="flex items-center gap-2">
                  <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${cfg?.color || "bg-slate-100 text-slate-600"}`}>
                    {cfg?.label || type}
                  </span>
                  <div className="flex-1 h-1.5 rounded-full bg-slate-200 overflow-hidden">
                    <div className="h-full rounded-full bg-slate-500" style={{ width: `${pct}%` }} />
                  </div>
                  <span className="text-[10px] text-slate-500 font-mono w-8 text-right">{count.toLocaleString()}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Top Actions mini-chart ── */}
      {stats && stats.top_actions.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white px-4 py-3" data-testid="audit-top-actions">
          <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide mb-2">Top Actions in Period</p>
          <div className="flex flex-wrap gap-2">
            {stats.top_actions.map(({ action, count }) => (
              <button
                key={action}
                onClick={() => { const next = { ...pendingFilters, action }; setPendingFilters(next); setFilters(next); setPage(1); loadLogs(1, perPage, next); }}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-100 hover:bg-slate-200 transition-colors text-[11px] font-medium text-slate-700"
                data-testid={`top-action-${action}`}
                title="Click to filter"
              >
                <span className="font-mono">{action}</span>
                <span className="bg-slate-300 text-slate-600 px-1 rounded text-[10px] font-semibold">{count}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Filters ── */}
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Filters</h3>
          <div className="flex items-center gap-2">
            {/* Quick range buttons */}
            <div className="flex items-center gap-1 border border-slate-200 rounded-lg p-0.5 bg-white">
              {[
                { label: "Today", from: today(), to: "" },
                { label: "7d", from: daysAgo(7), to: "" },
                { label: "30d", from: daysAgo(30), to: "" },
                { label: "90d", from: daysAgo(90), to: "" },
                { label: "All", from: "", to: "" },
              ].map(({ label, from, to }) => {
                const active = pendingFilters.date_from === from && pendingFilters.date_to === to;
                return (
                  <button
                    key={label}
                    onClick={() => applyQuickRange(from, to)}
                    className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${active ? "bg-slate-800 text-white" : "text-slate-600 hover:bg-slate-100"}`}
                    data-testid={`quick-range-${label.toLowerCase()}`}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
            <Button variant="ghost" size="sm" onClick={handleReset} className="text-xs h-7 gap-1 text-slate-500">
              <X size={11} /> Reset all
            </Button>
          </div>
        </div>

        {/* Row 1 */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <FilterText field="q" label="Search" placeholder="action, desc, actor…" />
          <FilterText field="actor" label="Actor email" placeholder="email or ID" />
          <FilterSelect field="actor_type" label="Actor type" allLabel="All types" options={ACTOR_TYPES.map((a) => ({ value: a.value, label: a.label }))} />
          <FilterSelect field="entity_type" label="Entity type" options={ENTITY_TYPES} allLabel="All entities" />
          <FilterText field="action" label="Action" placeholder="e.g. ORDER_PAID" />
          <FilterText field="entity_id" label="Entity ID" placeholder="exact ID" />
        </div>

        {/* Row 2 */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <FilterSelect field="source" label="Source" options={SOURCES} allLabel="All sources" />
          <FilterSelect field="success" label="Status" allLabel="All"
            options={[{ value: "true", label: "Success" }, { value: "false", label: "Failure" }]}
          />
          <FilterSelect field="severity" label="Severity" allLabel="All"
            options={[{ value: "info", label: "Info" }, { value: "warn", label: "Warn" }, { value: "error", label: "Error" }]}
          />
          <div className="space-y-0.5">
            <label className="text-[10px] uppercase tracking-wide font-medium text-slate-500">Date from</label>
            <Input type="date" value={pendingFilters.date_from} onChange={(e) => setP("date_from")(e.target.value)} className="h-8 text-sm" data-testid="logs-filter-date-from" />
          </div>
          <div className="space-y-0.5">
            <label className="text-[10px] uppercase tracking-wide font-medium text-slate-500">Date to</label>
            <Input type="date" value={pendingFilters.date_to} onChange={(e) => setP("date_to")(e.target.value)} className="h-8 text-sm" data-testid="logs-filter-date-to" />
          </div>
          <div className="flex items-end">
            <Button onClick={handleApply} size="sm" className="gap-1 h-8 w-full" data-testid="logs-apply-btn">
              <RefreshCw size={12} /> Apply
            </Button>
          </div>
        </div>
      </div>

      {/* ── Table ── */}
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
                    <span className="text-xs text-slate-600 whitespace-nowrap" title={log.occurred_at ? new Date(log.occurred_at).toLocaleString() : ""}>
                      {log.occurred_at ? relTime(log.occurred_at) : "—"}
                    </span>
                    <div className="text-[10px] text-slate-400 font-mono">
                      {log.occurred_at ? new Date(log.occurred_at).toLocaleDateString() : ""}
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
                    {log.actor_role && <span className="text-[10px] text-slate-400">{log.actor_role}</span>}
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
                    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold ${log.success === false ? "bg-red-100 text-red-700" : "bg-green-100 text-green-700"}`}>
                      {log.success === false ? "FAIL" : "OK"}
                    </span>
                    {log.severity && log.severity !== "info" && (
                      <div className={`mt-0.5 text-[10px] font-medium ${log.severity === "error" ? "text-red-600" : "text-amber-600"}`}>
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

      {/* ── Pagination ── */}
      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-2 text-slate-500 text-xs">
          {total > 0 && !loading && <span>Showing {startItem}–{endItem} of {total.toLocaleString()}</span>}
          <span className="text-slate-300">|</span>
          <span>Per page:</span>
          {PER_PAGE_OPTIONS.map((n) => (
            <button
              key={n}
              onClick={() => handlePerPageChange(n)}
              className={`px-2 py-0.5 rounded text-xs transition-colors ${perPage === n ? "bg-slate-800 text-white font-semibold" : "text-slate-600 hover:bg-slate-100"}`}
            >{n}</button>
          ))}
        </div>

        <div className="flex items-center gap-1">
          <Button variant="outline" size="icon" className="h-7 w-7" onClick={() => handlePageChange(1)} disabled={page === 1 || loading} data-testid="logs-page-first"><ChevronsLeft size={14} /></Button>
          <Button variant="outline" size="icon" className="h-7 w-7" onClick={() => handlePageChange(page - 1)} disabled={page === 1 || loading} data-testid="logs-page-prev"><ChevronLeft size={14} /></Button>
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
                <span key={`e-${idx}`} className="px-1 text-slate-400 text-xs">…</span>
              ) : (
                <button
                  key={p}
                  onClick={() => handlePageChange(p as number)}
                  disabled={loading}
                  className={`h-7 min-w-[28px] px-1.5 rounded text-xs font-medium transition-colors ${page === p ? "bg-slate-800 text-white" : "border border-slate-200 text-slate-600 hover:bg-slate-50"}`}
                  data-testid={`logs-page-${p}`}
                >{p}</button>
              )
            );
          })()}
          <Button variant="outline" size="icon" className="h-7 w-7" onClick={() => handlePageChange(page + 1)} disabled={page === totalPages || loading} data-testid="logs-page-next"><ChevronRight size={14} /></Button>
          <Button variant="outline" size="icon" className="h-7 w-7" onClick={() => handlePageChange(totalPages)} disabled={page === totalPages || loading} data-testid="logs-page-last"><ChevronsRight size={14} /></Button>
        </div>
      </div>

      {/* ── Detail Dialog ── */}
      <Dialog open={!!selectedLog} onOpenChange={(o) => { if (!o) setSelectedLog(null); }}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="log-detail-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <span className="font-mono text-sm">{selectedLog?.action}</span>
              {selectedLog && actorTypeBadge(selectedLog.actor_type)}
              <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold ml-1 ${selectedLog?.success === false ? "bg-red-100 text-red-700" : "bg-green-100 text-green-700"}`}>
                {selectedLog?.success === false ? "FAILED" : "OK"}
              </span>
            </DialogTitle>
          </DialogHeader>
          {selectedLog && (
            <div className="space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-3">
                {[
                  ["When", selectedLog.occurred_at ? new Date(selectedLog.occurred_at).toLocaleString() : "—"],
                  ["Actor", selectedLog.actor_email || selectedLog.actor_id || "—"],
                  ["Actor Type / Role", `${selectedLog.actor_type || "—"} / ${selectedLog.actor_role || "—"}`],
                  ["Source", selectedLog.source || "—"],
                  ["Entity Type", selectedLog.entity_type || "—"],
                  ["Entity ID", selectedLog.entity_id || "—"],
                  ["Request ID", selectedLog.request_id || "—"],
                  ["IP Address", selectedLog.ip_address || "—"],
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
                  <pre className="text-xs bg-red-50 text-red-800 p-3 rounded overflow-x-auto whitespace-pre-wrap">{selectedLog.error_message}</pre>
                </div>
              )}
              {selectedLog.before_json && Object.keys(selectedLog.before_json).length > 0 && (
                <div>
                  <p className="text-[10px] uppercase tracking-wide font-medium text-slate-500 mb-1">Before</p>
                  <pre className="text-xs bg-slate-50 border border-slate-200 rounded p-3 overflow-x-auto max-h-48">{JSON.stringify(selectedLog.before_json, null, 2)}</pre>
                </div>
              )}
              {selectedLog.after_json && Object.keys(selectedLog.after_json).length > 0 && (
                <div>
                  <p className="text-[10px] uppercase tracking-wide font-medium text-slate-500 mb-1">After</p>
                  <pre className="text-xs bg-slate-50 border border-slate-200 rounded p-3 overflow-x-auto max-h-48">{JSON.stringify(selectedLog.after_json, null, 2)}</pre>
                </div>
              )}
              {selectedLog.meta_json && Object.keys(selectedLog.meta_json).length > 0 && (
                <div>
                  <p className="text-[10px] uppercase tracking-wide font-medium text-slate-500 mb-1">Meta / Context</p>
                  <pre className="text-xs bg-slate-50 border border-slate-200 rounded p-3 overflow-x-auto max-h-48">{JSON.stringify(selectedLog.meta_json, null, 2)}</pre>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ── Stat Card ────────────────────────────────────────────────────────────────

function StatCard({ icon, label, value, sub, color, testid }: {
  icon: React.ReactNode; label: string; value: string; sub: string; color: string; testid: string;
}) {
  return (
    <div className={`rounded-xl border px-4 py-3 ${color}`} data-testid={testid}>
      <div className="flex items-center gap-1.5 mb-1">
        {icon}
        <span className="text-[11px] font-semibold text-slate-600 uppercase tracking-wide">{label}</span>
      </div>
      <p className="text-2xl font-bold text-slate-800 leading-none">{value}</p>
      <p className="text-[11px] text-slate-500 mt-0.5">{sub}</p>
    </div>
  );
}
