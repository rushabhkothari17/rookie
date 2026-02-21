import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { ChevronDown, RefreshCw, X } from "lucide-react";

const SEVERITY_COLORS: Record<string, string> = {
  info: "bg-blue-50 text-blue-700",
  warn: "bg-amber-50 text-amber-700",
  error: "bg-red-50 text-red-700",
};

const SOURCES = ["admin_ui", "customer_ui", "api", "webhook", "cron"];
const ENTITY_TYPES = [
  "Order", "Subscription", "Customer", "Product", "Article",
  "Setting", "Payment", "User", "OverrideCode", "PromoCode",
];
const SUCCESS_OPTS = [
  { label: "All", value: "" },
  { label: "Success", value: "true" },
  { label: "Failure", value: "false" },
];

function FilterInput({
  label, value, onChange, placeholder,
}: { label: string; value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <div className="space-y-0.5">
      <label className="text-[10px] uppercase tracking-wide font-medium text-slate-500">{label}</label>
      <div className="relative">
        <Input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder || label}
          className="h-8 text-sm pr-6"
        />
        {value && (
          <button className="absolute right-1.5 top-1.5 text-slate-400 hover:text-slate-600" onClick={() => onChange("")}>
            <X size={12} />
          </button>
        )}
      </div>
    </div>
  );
}

export function LogsTab() {
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const cursorStack = useRef<string[]>([]);
  const [selectedLog, setSelectedLog] = useState<any>(null);

  const [filters, setFilters] = useState({
    actor: "",
    source: "",
    entity_type: "",
    entity_id: "",
    action: "",
    success: "",
    severity: "",
    date_from: "",
    date_to: "",
    q: "",
  });

  const buildParams = useCallback((cursor?: string) => {
    const p: Record<string, string> = {};
    if (filters.actor) p.actor = filters.actor;
    if (filters.source) p.source = filters.source;
    if (filters.entity_type) p.entity_type = filters.entity_type;
    if (filters.entity_id) p.entity_id = filters.entity_id;
    if (filters.action) p.action = filters.action;
    if (filters.success) p.success = filters.success;
    if (filters.severity) p.severity = filters.severity;
    if (filters.date_from) p.date_from = filters.date_from;
    if (filters.date_to) p.date_to = filters.date_to;
    if (filters.q) p.q = filters.q;
    if (cursor) p.cursor = cursor;
    p.limit = "50";
    return p;
  }, [filters]);

  const load = useCallback(async (cursor?: string, append = false) => {
    setLoading(true);
    try {
      const res = await api.get("/admin/audit-logs", { params: buildParams(cursor) });
      if (append) {
        setLogs((prev) => [...prev, ...(res.data.logs || [])]);
      } else {
        setLogs(res.data.logs || []);
      }
      setNextCursor(res.data.next_cursor || null);
    } catch {
      toast.error("Failed to load logs");
    } finally {
      setLoading(false);
    }
  }, [buildParams]);

  // Re-fetch from scratch when filters change
  const handleApply = () => {
    cursorStack.current = [];
    load(undefined, false);
  };

  useEffect(() => {
    load(undefined, false);
  }, []);  // initial load

  const handleLoadMore = () => {
    if (!nextCursor) return;
    cursorStack.current.push(nextCursor);
    load(nextCursor, true);
  };

  const handleReset = () => {
    setFilters({ actor: "", source: "", entity_type: "", entity_id: "", action: "", success: "", severity: "", date_from: "", date_to: "", q: "" });
    cursorStack.current = [];
    setTimeout(() => load(undefined, false), 50);
  };

  const setF = (k: keyof typeof filters) => (v: string) => setFilters((f) => ({ ...f, [k]: v }));

  return (
    <div className="space-y-4" data-testid="admin-logs-tab">
      {/* Filters */}
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-700">Filters</h3>
          <Button variant="ghost" size="sm" onClick={handleReset} className="text-xs h-7 gap-1">
            <X size={12} /> Reset
          </Button>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          <FilterInput label="Actor (name/email)" value={filters.actor} onChange={setF("actor")} />
          <div className="space-y-0.5">
            <label className="text-[10px] uppercase tracking-wide font-medium text-slate-500">Source</label>
            <Select value={filters.source || "__all__"} onValueChange={(v) => setF("source")(v === "__all__" ? "" : v)}>
              <SelectTrigger className="h-8 text-sm"><SelectValue placeholder="All sources" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All sources</SelectItem>
                {SOURCES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-0.5">
            <label className="text-[10px] uppercase tracking-wide font-medium text-slate-500">Entity type</label>
            <Select value={filters.entity_type || "__all__"} onValueChange={(v) => setF("entity_type")(v === "__all__" ? "" : v)}>
              <SelectTrigger className="h-8 text-sm"><SelectValue placeholder="All types" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All types</SelectItem>
                {ENTITY_TYPES.map((e) => <SelectItem key={e} value={e}>{e}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <FilterInput label="Entity ID" value={filters.entity_id} onChange={setF("entity_id")} />
          <FilterInput label="Action" value={filters.action} onChange={setF("action")} placeholder="e.g. ORDER_PAID" />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          <div className="space-y-0.5">
            <label className="text-[10px] uppercase tracking-wide font-medium text-slate-500">Success</label>
            <Select value={filters.success} onValueChange={setF("success")}>
              <SelectTrigger className="h-8 text-sm"><SelectValue placeholder="All" /></SelectTrigger>
              <SelectContent>
                {SUCCESS_OPTS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-0.5">
            <label className="text-[10px] uppercase tracking-wide font-medium text-slate-500">Severity</label>
            <Select value={filters.severity} onValueChange={setF("severity")}>
              <SelectTrigger className="h-8 text-sm"><SelectValue placeholder="All" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="">All</SelectItem>
                <SelectItem value="info">Info</SelectItem>
                <SelectItem value="warn">Warn</SelectItem>
                <SelectItem value="error">Error</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-0.5">
            <label className="text-[10px] uppercase tracking-wide font-medium text-slate-500">Date from</label>
            <Input type="date" value={filters.date_from} onChange={(e) => setF("date_from")(e.target.value)} className="h-8 text-sm" />
          </div>
          <div className="space-y-0.5">
            <label className="text-[10px] uppercase tracking-wide font-medium text-slate-500">Date to</label>
            <Input type="date" value={filters.date_to} onChange={(e) => setF("date_to")(e.target.value)} className="h-8 text-sm" />
          </div>
          <FilterInput label="Search description" value={filters.q} onChange={setF("q")} placeholder="contains…" />
        </div>
        <div className="flex gap-2 pt-1">
          <Button onClick={handleApply} size="sm" className="gap-1" data-testid="logs-apply-btn">
            <RefreshCw size={12} /> Apply Filters
          </Button>
        </div>
      </div>

      {/* Table */}
      <div className="text-xs text-slate-500">{logs.length} record(s) loaded</div>
      <div className="rounded-xl border border-slate-200 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-slate-50">
              <TableHead className="text-xs w-36">When</TableHead>
              <TableHead className="text-xs">Action</TableHead>
              <TableHead className="text-xs max-w-xs">Description</TableHead>
              <TableHead className="text-xs">Actor</TableHead>
              <TableHead className="text-xs">Source</TableHead>
              <TableHead className="text-xs">Entity</TableHead>
              <TableHead className="text-xs">Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && logs.length === 0 ? (
              <TableRow><TableCell colSpan={7} className="text-center text-slate-400 py-8 text-sm">Loading…</TableCell></TableRow>
            ) : logs.length === 0 ? (
              <TableRow><TableCell colSpan={7} className="text-center text-slate-400 py-8 text-sm" data-testid="logs-empty">No audit logs yet.</TableCell></TableRow>
            ) : (
              logs.map((log) => (
                <TableRow
                  key={log.id}
                  className="cursor-pointer hover:bg-slate-50 transition-colors"
                  onClick={() => setSelectedLog(log)}
                  data-testid={`log-row-${log.id}`}
                >
                  <TableCell className="text-xs text-slate-500 whitespace-nowrap">
                    {log.occurred_at ? new Date(log.occurred_at).toLocaleString() : "—"}
                  </TableCell>
                  <TableCell className="font-mono text-xs text-slate-800">{log.action}</TableCell>
                  <TableCell className="text-xs text-slate-700 max-w-xs truncate">{log.description}</TableCell>
                  <TableCell className="text-xs text-slate-600">{log.actor_email || log.actor_id || log.actor_type || "—"}</TableCell>
                  <TableCell className="text-xs text-slate-500">{log.source || "—"}</TableCell>
                  <TableCell className="text-xs text-slate-600">
                    {log.entity_type && <span className="font-medium">{log.entity_type}</span>}
                    {log.entity_id && <div className="text-slate-400 font-mono">{log.entity_id?.slice(0, 8)}</div>}
                  </TableCell>
                  <TableCell>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                      log.success === false ? "bg-red-100 text-red-700" : "bg-green-100 text-green-700"
                    }`}>
                      {log.success === false ? "FAIL" : "OK"}
                    </span>
                    {log.severity && log.severity !== "info" && (
                      <span className={`ml-1 text-[10px] px-1.5 py-0.5 rounded ${SEVERITY_COLORS[log.severity] || ""}`}>
                        {log.severity}
                      </span>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {nextCursor && (
        <Button
          variant="outline"
          size="sm"
          className="w-full gap-1"
          onClick={handleLoadMore}
          disabled={loading}
          data-testid="logs-load-more"
        >
          <ChevronDown size={14} /> Load more {loading && "…"}
        </Button>
      )}

      {/* Detail Drawer */}
      <Dialog open={!!selectedLog} onOpenChange={(o) => { if (!o) setSelectedLog(null); }}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="log-detail-dialog">
          <DialogHeader>
            <DialogTitle className="font-mono text-base">{selectedLog?.action}</DialogTitle>
          </DialogHeader>
          {selectedLog && (
            <div className="space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-3 text-sm">
                {[
                  ["When", selectedLog.occurred_at ? new Date(selectedLog.occurred_at).toLocaleString() : "—"],
                  ["Actor", `${selectedLog.actor_email || selectedLog.actor_id || "—"} (${selectedLog.actor_type || "?"}, ${selectedLog.actor_role || "—"})`],
                  ["Source", selectedLog.source || "—"],
                  ["Entity", `${selectedLog.entity_type || "—"} / ${selectedLog.entity_id || "—"}`],
                  ["Request ID", selectedLog.request_id || "—"],
                  ["IP", selectedLog.ip_address || "—"],
                  ["Status", selectedLog.success === false ? "FAILED" : "OK"],
                  ["Severity", selectedLog.severity || "info"],
                ].map(([k, v]) => (
                  <div key={k as string}>
                    <p className="text-[10px] uppercase tracking-wide font-medium text-slate-500 mb-0.5">{k}</p>
                    <p className="text-slate-800 break-all">{v}</p>
                  </div>
                ))}
              </div>

              <div>
                <p className="text-[10px] uppercase tracking-wide font-medium text-slate-500 mb-1">Description</p>
                <p className="text-slate-800">{selectedLog.description}</p>
              </div>

              {selectedLog.error_message && (
                <div>
                  <p className="text-[10px] uppercase tracking-wide font-medium text-red-500 mb-1">Error</p>
                  <pre className="text-xs bg-red-50 text-red-800 p-2 rounded overflow-x-auto whitespace-pre-wrap">{selectedLog.error_message}</pre>
                </div>
              )}

              {selectedLog.before_json && (
                <div>
                  <p className="text-[10px] uppercase tracking-wide font-medium text-slate-500 mb-1">Before</p>
                  <pre className="text-xs bg-slate-50 border border-slate-200 rounded p-2 overflow-x-auto max-h-48">
                    {JSON.stringify(selectedLog.before_json, null, 2)}
                  </pre>
                </div>
              )}

              {selectedLog.after_json && (
                <div>
                  <p className="text-[10px] uppercase tracking-wide font-medium text-slate-500 mb-1">After</p>
                  <pre className="text-xs bg-slate-50 border border-slate-200 rounded p-2 overflow-x-auto max-h-48">
                    {JSON.stringify(selectedLog.after_json, null, 2)}
                  </pre>
                </div>
              )}

              {selectedLog.meta_json && (
                <div>
                  <p className="text-[10px] uppercase tracking-wide font-medium text-slate-500 mb-1">Meta / Context</p>
                  <pre className="text-xs bg-slate-50 border border-slate-200 rounded p-2 overflow-x-auto max-h-48">
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
