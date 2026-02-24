import { useState, useEffect, useCallback } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Button } from "./ui/button";
import { ChevronLeft, ChevronRight } from "lucide-react";
import api from "../lib/api";

export function AuditLogDialog({ open, onOpenChange, title, logsUrl }) {
  const [logs, setLogs] = useState([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  const fetchLogs = useCallback(async (p) => {
    if (!logsUrl) return;
    setLoading(true);
    try {
      const r = await api.get(logsUrl, { params: { page: p, limit: 20 } });
      setLogs(r.data.logs || []);
      setTotal(r.data.total ?? (r.data.logs || []).length);
      setPages(r.data.pages ?? 1);
    } catch {
      setLogs([]);
    } finally {
      setLoading(false);
    }
  }, [logsUrl]);

  useEffect(() => {
    if (open) {
      setPage(1);
      fetchLogs(1);
    }
  }, [open, logsUrl, fetchLogs]);

  const goTo = (p) => {
    setPage(p);
    fetchLogs(p);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <div className="max-h-[60vh] overflow-y-auto space-y-2">
          {loading && <p className="text-sm text-slate-500 text-center py-4">Loading...</p>}
          {!loading && logs.length === 0 && (
            <p className="text-sm text-slate-500 text-center py-4">No logs found</p>
          )}
          {!loading && logs.map((log, i) => (
            <div key={log.id || i} className="border border-slate-200 rounded p-3">
              <div className="flex justify-between items-start mb-1">
                <span className="text-sm font-semibold text-slate-900">{log.action}</span>
                <span className="text-xs text-slate-500">{new Date(log.created_at).toLocaleString()}</span>
              </div>
              {(log.actor || log.user) && (
                <div className="text-xs text-slate-600">Actor: {log.actor || log.user}</div>
              )}
              {log.details && Object.keys(log.details).length > 0 && (
                <pre className="text-xs text-slate-500 mt-2 bg-slate-50 p-2 rounded overflow-x-auto">
                  {JSON.stringify(log.details, null, 2)}
                </pre>
              )}
            </div>
          ))}
        </div>
        {pages > 1 && (
          <div className="flex items-center justify-between pt-3 border-t border-slate-100">
            <span className="text-xs text-slate-500">{total} total logs — Page {page} of {pages}</span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => goTo(page - 1)}
                data-testid="audit-log-prev"
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= pages}
                onClick={() => goTo(page + 1)}
                data-testid="audit-log-next"
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
