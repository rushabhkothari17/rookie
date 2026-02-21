import { useEffect, useState } from "react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";

interface QuoteRequest {
  id: string;
  product_name: string;
  name: string;
  email: string;
  company?: string;
  phone?: string;
  message?: string;
  created_at: string;
  status: string;
}

export function QuoteRequestsTab() {
  const [quotes, setQuotes] = useState<QuoteRequest[]>([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get("/admin/quote-requests");
      setQuotes(res.data.quotes || []);
    } catch {
      toast.error("Failed to load quote requests");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const formatDate = (iso: string) => {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleString("en-AU", {
        day: "2-digit", month: "short", year: "numeric",
        hour: "2-digit", minute: "2-digit",
      });
    } catch {
      return iso;
    }
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
        <Button variant="outline" size="sm" onClick={load}>Refresh</Button>
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
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-slate-400">Loading…</TableCell>
              </TableRow>
            )}
            {!loading && quotes.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-slate-400 py-8">
                  No quote requests yet.
                </TableCell>
              </TableRow>
            )}
            {quotes.map((q) => (
              <TableRow key={q.id} data-testid={`admin-quote-row-${q.id}`}>
                <TableCell className="text-xs text-slate-500 whitespace-nowrap">
                  {formatDate(q.created_at)}
                </TableCell>
                <TableCell className="font-medium text-sm max-w-[160px]">
                  <span className="block truncate" title={q.product_name}>{q.product_name}</span>
                </TableCell>
                <TableCell>
                  <div className="text-sm font-medium">{q.name}</div>
                  <div className="text-xs text-slate-400">{q.email}</div>
                </TableCell>
                <TableCell className="text-sm">{q.company || "—"}</TableCell>
                <TableCell className="text-sm">{q.phone || "—"}</TableCell>
                <TableCell className="max-w-[200px]">
                  <span className="text-xs text-slate-600 line-clamp-2" title={q.message}>
                    {q.message || "—"}
                  </span>
                </TableCell>
                <TableCell>{statusBadge(q.status)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
