import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { AdminPageHeader } from "./shared/AdminPageHeader";
import { AdminPagination } from "./shared/AdminPagination";
import { useAuth } from "@/contexts/AuthContext";

const STATUS_OPTIONS = ["scope_pending", "scope_requested", "responded", "closed"];

const statusBadge = (s: string) => {
  const map: Record<string, string> = {
    scope_pending: "bg-yellow-100 text-yellow-700",
    scope_requested: "bg-blue-100 text-blue-700",
    responded: "bg-green-100 text-green-700",
    closed: "bg-slate-100 text-slate-500",
  };
  const labels: Record<string, string> = {
    scope_pending: "Pending",
    scope_requested: "Requested",
    responded: "Responded",
    closed: "Closed",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded font-medium ${map[s] || "bg-slate-100 text-slate-500"}`}>
      {labels[s] || s}
    </span>
  );
};

export function EnquiriesTab() {
  const { user: authUser } = useAuth();
  const isPlatformAdmin = authUser?.role === "platform_admin";

  const [enquiries, setEnquiries] = useState<any[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const PER_PAGE = 20;

  // Filters
  const [emailFilter, setEmailFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  // Dialog
  const [viewEnquiry, setViewEnquiry] = useState<any>(null);
  const [confirmDelete, setConfirmDelete] = useState<any>(null);
  const [updatingStatus, setUpdatingStatus] = useState<string | null>(null);

  const load = useCallback(async (p = 1) => {
    try {
      const params = new URLSearchParams({ page: String(p), per_page: String(PER_PAGE) });
      if (emailFilter) params.append("email_filter", emailFilter);
      if (statusFilter) params.append("status_filter", statusFilter);
      if (startDate) params.append("date_from", startDate);
      if (endDate) params.append("date_to", endDate);
      const res = await api.get(`/admin/enquiries?${params}`);
      setEnquiries(res.data.enquiries || []);
      setTotal(res.data.total || 0);
      setTotalPages(res.data.total_pages || 1);
      setPage(p);
    } catch {
      toast.error("Failed to load enquiries");
    }
  }, [emailFilter, statusFilter, startDate, endDate]);

  useEffect(() => { load(1); }, [emailFilter, statusFilter, startDate, endDate]);

  const handleStatusChange = async (enquiry: any, newStatus: string) => {
    setUpdatingStatus(enquiry.id);
    try {
      await api.patch(`/admin/enquiries/${enquiry.id}/status`, { status: newStatus });
      toast.success("Status updated");
      load(page);
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to update status");
    } finally {
      setUpdatingStatus(null);
    }
  };

  const handleDelete = async (enquiry: any) => {
    try {
      await api.delete(`/admin/enquiries/${enquiry.id}`);
      toast.success("Enquiry deleted");
      load(page);
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to delete");
    }
  };

  const clearFilters = () => {
    setEmailFilter("");
    setStatusFilter("");
    setStartDate("");
    setEndDate("");
  };

  const getSummary = (e: any) => {
    const fd = e.scope_form_data || {};
    return fd.project_summary || fd.message || fd.additional_notes || "—";
  };

  return (
    <div className="space-y-4" data-testid="enquiries-tab">
      <AdminPageHeader
        title="Enquiries"
        subtitle={`${total} records`}
        actions={null}
      />

      {/* Filters */}
      <div className="rounded-xl border border-slate-200 bg-white p-3">
        <div className="flex flex-wrap gap-2 items-end">
          <Input
            placeholder="Customer email…"
            value={emailFilter}
            onChange={e => setEmailFilter(e.target.value)}
            className="h-8 text-xs w-44"
            data-testid="enquiries-email-filter"
          />
          <Select value={statusFilter || "all"} onValueChange={v => setStatusFilter(v === "all" ? "" : v)}>
            <SelectTrigger className="h-8 text-xs w-36 bg-white" data-testid="enquiries-status-filter">
              <SelectValue placeholder="All Statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Statuses</SelectItem>
              {STATUS_OPTIONS.map(s => (
                <SelectItem key={s} value={s}>{s}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="flex items-center gap-1">
            <span className="text-xs text-slate-400">From</span>
            <Input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} className="h-8 text-xs w-32" data-testid="enquiries-start-date" />
            <span className="text-xs text-slate-400">–</span>
            <Input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} className="h-8 text-xs w-32" data-testid="enquiries-end-date" />
          </div>
          <Button size="sm" variant="outline" onClick={clearFilters} className="h-8 text-xs" data-testid="enquiries-clear-filters">
            Clear
          </Button>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
        <Table data-testid="enquiries-table">
          <TableHeader>
            <TableRow className="bg-slate-50">
              <TableHead>Date</TableHead>
              <TableHead>Order #</TableHead>
              <TableHead>Customer</TableHead>
              {isPlatformAdmin && <TableHead>Partner</TableHead>}
              <TableHead>Products</TableHead>
              <TableHead>Summary</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {enquiries.length === 0 && (
              <TableRow>
                <TableCell colSpan={isPlatformAdmin ? 8 : 7} className="text-center text-slate-400 py-8">
                  No enquiries found.
                </TableCell>
              </TableRow>
            )}
            {enquiries.map((e) => (
              <TableRow key={e.id} data-testid={`enquiry-row-${e.id}`}>
                <TableCell className="whitespace-nowrap text-xs">{e.created_at?.slice(0, 10)}</TableCell>
                <TableCell className="font-mono text-xs">{e.order_number}</TableCell>
                <TableCell>
                  <div className="font-medium text-sm">{e.customer_name || "—"}</div>
                  <div className="text-xs text-slate-400">{e.customer_email}</div>
                </TableCell>
                {isPlatformAdmin && (
                  <TableCell className="text-xs text-slate-500">{e.partner_code || "—"}</TableCell>
                )}
                <TableCell className="text-xs max-w-[140px]">
                  <span className="line-clamp-2">{(e.products || []).join(", ") || "—"}</span>
                </TableCell>
                <TableCell className="max-w-[200px]">
                  <span className="text-xs line-clamp-2 text-slate-600">{getSummary(e)}</span>
                </TableCell>
                <TableCell>
                  <Select
                    value={e.status}
                    onValueChange={v => handleStatusChange(e, v)}
                    disabled={updatingStatus === e.id}
                  >
                    <SelectTrigger className="h-7 text-xs w-32 bg-white" data-testid={`enquiry-status-${e.id}`}>
                      <SelectValue>{statusBadge(e.status)}</SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                      {STATUS_OPTIONS.map(s => (
                        <SelectItem key={s} value={s}>{s}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </TableCell>
                <TableCell>
                  <div className="flex gap-1">
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-6 px-2 text-[11px]"
                      onClick={() => setViewEnquiry(e)}
                      data-testid={`enquiry-view-${e.id}`}
                    >
                      View
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 px-2 text-[11px] text-red-500 hover:text-red-700"
                      onClick={() => setConfirmDelete(e)}
                      data-testid={`enquiry-delete-${e.id}`}
                    >
                      Delete
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <AdminPagination page={page} totalPages={totalPages} total={total} perPage={PER_PAGE} onPage={(p) => load(p)} />

      {/* View Details Dialog */}
      <Dialog open={!!viewEnquiry} onOpenChange={(open) => !open && setViewEnquiry(null)}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="enquiry-detail-dialog">
          <DialogHeader>
            <DialogTitle>Enquiry — {viewEnquiry?.order_number}</DialogTitle>
          </DialogHeader>
          {viewEnquiry && (
            <div className="space-y-4 py-2 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-xs text-slate-400 uppercase tracking-wide mb-1">Customer</p>
                  <p className="font-medium">{viewEnquiry.customer_name || "—"}</p>
                  <p className="text-slate-500">{viewEnquiry.customer_email}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-400 uppercase tracking-wide mb-1">Products</p>
                  <p className="font-medium">{(viewEnquiry.products || []).join(", ") || "—"}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-400 uppercase tracking-wide mb-1">Date</p>
                  <p>{viewEnquiry.created_at?.slice(0, 16).replace("T", " ")}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-400 uppercase tracking-wide mb-1">Status</p>
                  {statusBadge(viewEnquiry.status)}
                </div>
              </div>
              <hr className="border-slate-100" />
              {/* Scope form fields */}
              {(() => {
                const fd = viewEnquiry.scope_form_data || {};
                const rows = [
                  { label: "Name", value: fd.name },
                  { label: "Email", value: fd.email },
                  { label: "Company", value: fd.company },
                  { label: "Phone", value: fd.phone },
                  { label: "Message", value: fd.message },
                  { label: "Project Summary", value: fd.project_summary },
                  { label: "Desired Outcomes", value: fd.desired_outcomes },
                  { label: "Apps Involved", value: fd.apps_involved },
                  { label: "Timeline / Urgency", value: fd.timeline_urgency },
                  { label: "Budget Range", value: fd.budget_range },
                  { label: "Additional Notes", value: fd.additional_notes },
                ].filter(r => r.value);
                return rows.map(r => (
                  <div key={r.label}>
                    <p className="text-xs text-slate-400 uppercase tracking-wide mb-0.5">{r.label}</p>
                    <p className="text-slate-700 whitespace-pre-wrap">{r.value}</p>
                  </div>
                ));
              })()}
              {/* Extra / custom form fields */}
              {viewEnquiry.scope_form_data?.extra_fields && Object.keys(viewEnquiry.scope_form_data.extra_fields).length > 0 && (
                <>
                  <hr className="border-slate-100" />
                  <p className="text-xs text-slate-400 uppercase tracking-wide">Additional Fields</p>
                  {Object.entries(viewEnquiry.scope_form_data.extra_fields).map(([k, v]) => (
                    <div key={k}>
                      <p className="text-xs text-slate-400 capitalize">{k.replace(/_/g, " ")}</p>
                      <p className="text-slate-700">{String(v)}</p>
                    </div>
                  ))}
                </>
              )}
              <div className="flex justify-between items-center pt-2">
                <Select
                  value={viewEnquiry.status}
                  onValueChange={v => { handleStatusChange(viewEnquiry, v); setViewEnquiry({ ...viewEnquiry, status: v }); }}
                >
                  <SelectTrigger className="h-8 text-xs w-40 bg-white" data-testid="enquiry-detail-status">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {STATUS_OPTIONS.map(s => (
                      <SelectItem key={s} value={s}>{s}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button variant="outline" onClick={() => setViewEnquiry(null)}>Close</Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={!!confirmDelete} onOpenChange={(open) => !open && setConfirmDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Enquiry</AlertDialogTitle>
            <AlertDialogDescription>
              Delete enquiry {confirmDelete?.order_number} from {confirmDelete?.customer_email}? This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700"
              onClick={() => { handleDelete(confirmDelete); setConfirmDelete(null); }}
              data-testid="confirm-enquiry-delete"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
