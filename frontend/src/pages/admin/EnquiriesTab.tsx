import { useCallback, useEffect, useMemo, useState } from "react";
import { RequiredLabel } from "@/components/shared/RequiredLabel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Textarea } from "@/components/ui/textarea";
import { Check, ChevronsUpDown, Download, Plus } from "lucide-react";
import { cn } from "@/lib/utils";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { AdminPageHeader } from "./shared/AdminPageHeader";
import { AdminPagination } from "./shared/AdminPagination";
import { useAuth } from "@/contexts/AuthContext";
import { ColHeader } from "@/components/shared/ColHeader";

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
  const isPlatformAdmin = authUser?.role === "platform_admin" || authUser?.role === "platform_super_admin";

  const [enquiries, setEnquiries] = useState<any[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const PER_PAGE = 20;

  // Filters
  const [orderFilter, setOrderFilter] = useState<string[]>([]);
  const [customerFilter, setCustomerFilter] = useState<string[]>([]);
  const [partnerFilter, setPartnerFilter] = useState<string[]>([]);
  const [productsFilter, setProductsFilter] = useState<string[]>([]);
  const [statusFilter, setStatusFilter] = useState<string[]>([]);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [colSort, setColSort] = useState<{ col: string; dir: "asc" | "desc" } | null>(null);

  // Build unique options for filters
  const uniqueOrderNumbers = useMemo(() => Array.from(new Set(enquiries.map(e => e.order_number).filter(Boolean))), [enquiries]);
  const uniqueCustomers = useMemo(() => Array.from(new Set(enquiries.map(e => e.customer_name || e.customer_email).filter(Boolean))), [enquiries]);
  const uniquePartners = useMemo(() => Array.from(new Set(enquiries.map(e => e.partner_code).filter(Boolean))), [enquiries]);
  const uniqueProducts = useMemo(() => {
    const prods = new Set<string>();
    enquiries.forEach(e => (e.products || []).forEach((p: string) => prods.add(p)));
    return Array.from(prods);
  }, [enquiries]);

  const displayEnquiries = useMemo(() => {
    let r = [...enquiries];
    // Apply local multi-select filters
    if (orderFilter.length > 0) r = r.filter(e => orderFilter.includes(e.order_number));
    if (customerFilter.length > 0) r = r.filter(e => customerFilter.includes(e.customer_name) || customerFilter.includes(e.customer_email));
    if (partnerFilter.length > 0) r = r.filter(e => partnerFilter.includes(e.partner_code));
    if (productsFilter.length > 0) r = r.filter(e => (e.products || []).some((p: string) => productsFilter.includes(p)));
    if (statusFilter.length > 0) r = r.filter(e => statusFilter.includes(e.status));
    if (colSort) {
      r.sort((a, b) => {
        let av: any = "", bv: any = "";
        if (colSort.col === "date") { av = a.created_at || ""; bv = b.created_at || ""; }
        else if (colSort.col === "order") { av = a.order_number || ""; bv = b.order_number || ""; }
        else if (colSort.col === "customer") { av = a.customer_name || a.customer_email || ""; bv = b.customer_name || b.customer_email || ""; }
        else if (colSort.col === "status") { av = a.status; bv = b.status; }
        if (av < bv) return colSort.dir === "asc" ? -1 : 1;
        if (av > bv) return colSort.dir === "asc" ? 1 : -1;
        return 0;
      });
    }
    return r;
  }, [enquiries, orderFilter, customerFilter, partnerFilter, productsFilter, statusFilter, colSort]);

  // Dialog
  const [viewEnquiry, setViewEnquiry] = useState<any>(null);
  const [confirmDelete, setConfirmDelete] = useState<any>(null);
  const [updatingStatus, setUpdatingStatus] = useState<string | null>(null);

  const load = useCallback(async (p = 1) => {
    try {
      const params = new URLSearchParams({ page: String(p), per_page: String(500) });
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
  }, [startDate, endDate]);

  useEffect(() => { load(1); }, [startDate, endDate]);

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

  const handleDownloadPdf = async (enquiry: any) => {
    try {
      const API_URL = process.env.REACT_APP_BACKEND_URL || "";
      const token = localStorage.getItem("token") || sessionStorage.getItem("token") || "";
      const resp = await fetch(`${API_URL}/api/admin/enquiries/${enquiry.id}/pdf`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) throw new Error("Failed to download");
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `enquiry-${enquiry.order_number || enquiry.id}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("Failed to download PDF");
    }
  };

  // Manual create enquiry
  const [showCreate, setShowCreate] = useState(false);
  const [products, setProducts] = useState<any[]>([]);
  const [customers, setCustomers] = useState<any[]>([]);
  const [forms, setForms] = useState<any[]>([]);
  const [newEnquiry, setNewEnquiry] = useState({ customer_id: "", product_id: "", form_id: "", notes: "" });
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [creating, setCreating] = useState(false);
  const [customerComboOpen, setCustomerComboOpen] = useState(false);
  const [productComboOpen, setProductComboOpen] = useState(false);

  // Derived: selected form's schema fields
  const selectedFormFields = useMemo(() => {
    if (!newEnquiry.form_id) return [];
    const f = forms.find((f: any) => f.id === newEnquiry.form_id);
    if (!f?.schema) return [];
    try {
      const parsed = JSON.parse(f.schema);
      if (Array.isArray(parsed)) return parsed.filter((field: any) => field.enabled !== false);
    } catch {}
    return [];
  }, [newEnquiry.form_id, forms]);

  const loadDropdownData = useCallback((_tenantId?: string) => {
    api.get("/admin/products-all?per_page=200").then(r => setProducts(r.data.products || [])).catch(() => {});
    api.get("/admin/customers?per_page=200").then(r => {
      const custs = r.data.customers || [];
      const users = r.data.users || [];
      const userMap: Record<string, any> = {};
      users.forEach((u: any) => { userMap[u.id] = u; });
      const merged = custs.map((c: any) => ({
        ...c,
        email: userMap[c.user_id]?.email || "",
        full_name: userMap[c.user_id]?.full_name || c.company_name || "",
      }));
      setCustomers(merged);
    }).catch(() => {});
    api.get("/admin/forms").then(r => setForms(r.data.forms || [])).catch(() => {});
  }, []);

  useEffect(() => {
    loadDropdownData();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const resetCreate = () => {
    setNewEnquiry({ customer_id: "", product_id: "", form_id: "", notes: "" });
    setFormData({});
  };

  const handleCreateEnquiry = async () => {
    if (!newEnquiry.customer_id) { toast.error("Please select a customer"); return; }
    for (const field of selectedFormFields) {
      if (field.required && !formData[field.key]?.trim()) {
        toast.error(`"${field.label}" is required`);
        return;
      }
    }
    setCreating(true);
    try {
      const res = await api.post("/admin/enquiries/manual", {
        customer_id: newEnquiry.customer_id,
        product_id: newEnquiry.product_id || null,
        form_id: newEnquiry.form_id || null,
        form_data: Object.keys(formData).length > 0 ? formData : null,
        notes: newEnquiry.notes || null,
      });
      toast.success(`Enquiry ${res.data.order_number} created`);
      setShowCreate(false);
      resetCreate();
      load(1);
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to create enquiry");
    } finally {
      setCreating(false);
    }
  };

  const clearFilters = () => {
    setOrderFilter([]);
    setCustomerFilter([]);
    setPartnerFilter([]);
    setProductsFilter([]);
    setStatusFilter([]);
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
        actions={
          <Button size="sm" onClick={() => setShowCreate(true)} data-testid="create-enquiry-btn">
            <Plus className="w-4 h-4 mr-1" /> Create Enquiry
          </Button>
        }
      />

      {/* Create Enquiry Dialog */}
      <Dialog open={showCreate} onOpenChange={(open) => { setShowCreate(open); if (!open) resetCreate(); }}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Create Manual Enquiry</DialogTitle></DialogHeader>
          <div className="space-y-4 pt-2">

            {/* Customer combobox with search */}
            <div>
              <RequiredLabel className="text-slate-600">Customer</RequiredLabel>
              <Popover open={customerComboOpen} onOpenChange={setCustomerComboOpen}>
                <PopoverTrigger asChild>
                  <Button variant="outline" role="combobox" className="w-full justify-between font-normal mt-1 h-10 text-sm" data-testid="enquiry-customer-select">
                    {newEnquiry.customer_id
                      ? (() => { const c = customers.find(x => x.id === newEnquiry.customer_id); return c ? `${c.full_name || c.company_name}${c.email ? ` (${c.email})` : ""}` : "Select customer"; })()
                      : <span className="text-slate-400">Select customer...</span>}
                    <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="p-0 z-[200]" style={{ width: "var(--radix-popover-trigger-width)" }} align="start">
                  <Command>
                    <CommandInput placeholder="Search by name or email..." />
                    <CommandList className="max-h-52">
                      <CommandEmpty>No customer found.</CommandEmpty>
                      <CommandGroup>
                        {customers.map((c: any) => (
                          <CommandItem key={c.id} value={`${c.full_name} ${c.email} ${c.company_name}`} onSelect={() => {
                            setNewEnquiry(p => ({ ...p, customer_id: c.id }));
                            setCustomerComboOpen(false);
                          }}>
                            <Check className={cn("mr-2 h-4 w-4", newEnquiry.customer_id === c.id ? "opacity-100" : "opacity-0")} />
                            <span>{c.full_name || c.company_name}</span>
                            {c.email && <span className="text-slate-400 text-xs ml-1.5">({c.email})</span>}
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
            </div>

            {/* Product combobox with search */}
            <div>
              <label className="text-xs font-medium text-slate-600">Product <span className="text-slate-400">(optional)</span></label>
              <Popover open={productComboOpen} onOpenChange={setProductComboOpen}>
                <PopoverTrigger asChild>
                  <Button variant="outline" role="combobox" className="w-full justify-between font-normal mt-1 h-10 text-sm" data-testid="enquiry-product-select">
                    {newEnquiry.product_id
                      ? (products.find(p => p.id === newEnquiry.product_id)?.name || "Select product")
                      : <span className="text-slate-400">None (optional)</span>}
                    <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="p-0 z-[200]" style={{ width: "var(--radix-popover-trigger-width)" }} align="start">
                  <Command>
                    <CommandInput placeholder="Search products..." />
                    <CommandList className="max-h-52">
                      <CommandEmpty>No product found.</CommandEmpty>
                      <CommandGroup>
                        <CommandItem value="__none__" onSelect={() => { setNewEnquiry(p => ({ ...p, product_id: "" })); setProductComboOpen(false); }}>
                          <Check className={cn("mr-2 h-4 w-4", !newEnquiry.product_id ? "opacity-100" : "opacity-0")} />
                          None
                        </CommandItem>
                        {products.map((prod: any) => (
                          <CommandItem key={prod.id} value={prod.name} onSelect={() => {
                            setNewEnquiry(p => ({ ...p, product_id: prod.id }));
                            setProductComboOpen(false);
                          }}>
                            <Check className={cn("mr-2 h-4 w-4", newEnquiry.product_id === prod.id ? "opacity-100" : "opacity-0")} />
                            {prod.name}
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
            </div>

            {/* Form select */}
            <div>
              <label className="text-xs font-medium text-slate-600">Form <span className="text-slate-400">(optional)</span></label>
              <Select value={newEnquiry.form_id || "__none__"} onValueChange={v => {
                setNewEnquiry(p => ({ ...p, form_id: v === "__none__" ? "" : v }));
                setFormData({});
              }}>
                <SelectTrigger className="mt-1" data-testid="enquiry-form-select">
                  <SelectValue placeholder="Select form" />
                </SelectTrigger>
                <SelectContent position="popper">
                  <SelectItem value="__none__">None</SelectItem>
                  {forms.map((f: any) => <SelectItem key={f.id} value={f.id}>{f.name}</SelectItem>)}
                </SelectContent>
              </Select>
              {forms.length === 0 && <p className="text-xs text-slate-400 mt-1">No forms configured for this partner yet.</p>}
            </div>

            {/* Dynamic form fields from selected form's schema */}
            {selectedFormFields.length > 0 && (
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Form Fields</p>
                {selectedFormFields.map((field: any) => (
                  <div key={field.key}>
                    <label className="text-xs font-medium text-slate-600">
                      {field.label}{field.required && <span className="text-red-500 ml-0.5">*</span>}
                    </label>
                    {field.type === "textarea" ? (
                      <Textarea
                        className="mt-1 min-h-[70px] text-sm"
                        placeholder={field.placeholder || ""}
                        value={formData[field.key] || ""}
                        onChange={e => setFormData(prev => ({ ...prev, [field.key]: e.target.value }))}
                        data-testid={`enquiry-form-field-${field.key}`}
                      />
                    ) : field.type === "select" && field.options?.length > 0 ? (
                      <Select value={formData[field.key] || "__none__"} onValueChange={v => setFormData(prev => ({ ...prev, [field.key]: v === "__none__" ? "" : v }))}>
                        <SelectTrigger className="mt-1" data-testid={`enquiry-form-field-${field.key}`}>
                          <SelectValue placeholder={field.placeholder || "Select…"} />
                        </SelectTrigger>
                        <SelectContent position="popper">
                          <SelectItem value="__none__">— Select —</SelectItem>
                          {field.options.map((opt: string) => (
                            <SelectItem key={opt} value={opt}>{opt}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    ) : (
                      <Input
                        className="mt-1 text-sm"
                        type={field.type === "email" ? "email" : field.type === "tel" ? "tel" : field.type === "number" ? "number" : field.type === "date" ? "date" : "text"}
                        placeholder={field.placeholder || ""}
                        value={formData[field.key] || ""}
                        onChange={e => setFormData(prev => ({ ...prev, [field.key]: e.target.value }))}
                        data-testid={`enquiry-form-field-${field.key}`}
                      />
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Notes */}
            <div>
              <label className="text-xs font-medium text-slate-600">Notes <span className="text-slate-400">(optional)</span></label>
              <Textarea className="mt-1 min-h-[70px] text-sm" placeholder="Additional notes…" value={newEnquiry.notes} onChange={e => setNewEnquiry(p => ({ ...p, notes: e.target.value }))} data-testid="enquiry-notes" />
            </div>

            <div className="flex gap-2 justify-end pt-2">
              <Button variant="outline" onClick={() => { setShowCreate(false); resetCreate(); }}>Cancel</Button>
              <Button onClick={handleCreateEnquiry} disabled={creating} data-testid="enquiry-submit-btn">
                {creating ? "Creating…" : "Create Enquiry"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Filters removed — use column headers */}

      {/* Table */}
      <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
        <Table data-testid="enquiries-table">
          <TableHeader>
            <TableRow className="bg-slate-50">
              <ColHeader label="Date" colKey="date" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="date-range" filterValue={{ from: startDate, to: endDate }} onFilter={v => { setStartDate(v.from || ""); setEndDate(v.to || ""); setPage(1); }} onClearFilter={() => { setStartDate(""); setEndDate(""); setPage(1); }} />
              <ColHeader label="Order #" colKey="order" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={orderFilter} onFilter={v => { setOrderFilter(v); setPage(1); }} onClearFilter={() => { setOrderFilter([]); setPage(1); }} statusOptions={uniqueOrderNumbers.map(o => [o, o] as [string, string])} />
              <ColHeader label="Customer" colKey="customer" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={customerFilter} onFilter={v => { setCustomerFilter(v); setPage(1); }} onClearFilter={() => { setCustomerFilter([]); setPage(1); }} statusOptions={uniqueCustomers.map(c => [c, c] as [string, string])} />
              {isPlatformAdmin && <ColHeader label="Partner" colKey="partner" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={partnerFilter} onFilter={v => { setPartnerFilter(v); setPage(1); }} onClearFilter={() => { setPartnerFilter([]); setPage(1); }} statusOptions={uniquePartners.map(p => [p, p] as [string, string])} />}
              <ColHeader label="Products" colKey="products" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={productsFilter} onFilter={v => { setProductsFilter(v); setPage(1); }} onClearFilter={() => { setProductsFilter([]); setPage(1); }} statusOptions={uniqueProducts.map(p => [p, p] as [string, string])} />
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500">Summary</th>
              <ColHeader label="Status" colKey="status" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={statusFilter} onFilter={v => { setStatusFilter(v); setPage(1); }} onClearFilter={() => { setStatusFilter([]); setPage(1); }} statusOptions={[["scope_pending", "Pending"], ["scope_requested", "Requested"], ["responded", "Responded"], ["closed", "Closed"]]} />
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500">Actions</th>
            </TableRow>
          </TableHeader>
          <TableBody>
            {displayEnquiries.length === 0 && (
              <TableRow>
                <TableCell colSpan={isPlatformAdmin ? 8 : 7} className="text-center text-slate-400 py-8">
                  No enquiries found.
                </TableCell>
              </TableRow>
            )}
            {displayEnquiries.map((e) => (
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
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleDownloadPdf(viewEnquiry)}
                    data-testid="enquiry-download-pdf"
                  >
                    <Download size={13} className="mr-1.5" /> Download PDF
                  </Button>
                  <Button variant="outline" onClick={() => setViewEnquiry(null)}>Close</Button>
                </div>
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
