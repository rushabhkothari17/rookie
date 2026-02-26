import { useCallback, useEffect, useMemo, useState } from "react";
import { ImportModal } from "@/components/admin/ImportModal";
import { useWebsite } from "@/contexts/WebsiteContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { useAuth } from "@/contexts/AuthContext";
import { AdminPageHeader } from "./shared/AdminPageHeader";
import { AdminPagination } from "./shared/AdminPagination";
import { AuditLogDialog } from "@/components/AuditLogDialog";
import { Download, Plus, Upload} from "lucide-react";
import { SearchableSelect } from "@/components/ui/searchable-select";

const PARTNER_MAP_OPTIONS = [
  { value: "", label: "Not set" },
  { value: "Yes - Pending Verification", label: "Yes - Pending Verification" },
  { value: "Pre-existing Customer - Pending Verification", label: "Pre-existing - Pending" },
  { value: "Not yet - Pending Verification", label: "Not yet - Pending" },
  { value: "Yes", label: "Yes (Verified)" },
  { value: "Pre-existing Customer", label: "Pre-existing (Verified)" },
  { value: "Not yet", label: "Not yet (Verified)" },
];

const pmColor = (pm: string | undefined) =>
  !pm ? "bg-slate-100 text-slate-500"
  : pm.includes("Pending") ? "bg-amber-100 text-amber-700"
  : pm === "Yes" || pm === "Pre-existing Customer" ? "bg-green-100 text-green-700"
  : "bg-red-100 text-red-700";

export function CustomersTab() {
  const { user: authUser } = useAuth();
  const isPlatformAdmin = authUser?.role === "platform_admin";
  const [customers, setCustomers] = useState<any[]>([]);
  const [showImport, setShowImport] = useState(false);
  const [users, setUsers] = useState<any[]>([]);
  const [addresses, setAddresses] = useState<any[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const PER_PAGE = 10;

  const ws = useWebsite();

  // Dynamic payment mode filter options — only show globally-enabled providers
  const paymentFilterOptions = useMemo(() => {
    const opts: { value: string; label: string }[] = [{ value: "all_modes", label: "All Payment Modes" }];
    if (ws.gocardless_enabled) opts.push({ value: "gocardless", label: "GoCardless" });
    if (ws.stripe_enabled) opts.push({ value: "stripe", label: "Stripe" });
    if (ws.gocardless_enabled && ws.stripe_enabled) opts.push({ value: "both", label: "Both (GC + Stripe)" });
    opts.push({ value: "none", label: "None assigned" });
    return opts;
  }, [ws.gocardless_enabled, ws.stripe_enabled]);
  const [search, setSearch] = useState("");
  const [countryFilter, setCountryFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [paymentModeFilter, setPaymentModeFilter] = useState("");
  const [partnerMapFilter, setPartnerMapFilter] = useState("all");

  // Dialogs
  const [selectedCustomer, setSelectedCustomer] = useState<any>(null);
  const [viewNotesCustomer, setViewNotesCustomer] = useState<any>(null);
  const [customerNotes, setCustomerNotes] = useState<any[]>([]);
  const [editingPartnerMap, setEditingPartnerMap] = useState<{ customerId: string; value: string } | null>(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [newCustomer, setNewCustomer] = useState({ full_name: "", company_name: "", job_title: "", email: "", phone: "", password: "", line1: "", line2: "", city: "", region: "", postal: "", country: "", mark_verified: true });
  const [logsUrl, setLogsUrl] = useState("");
  const [showAuditLogs, setShowAuditLogs] = useState(false);
  const [confirmToggleCustomer, setConfirmToggleCustomer] = useState<{id: string, active: boolean} | null>(null);

  const userMap: Record<string, any> = {};
  users.forEach((u) => { userMap[u.id] = u; });
  const addrMap: Record<string, any> = {};
  addresses.forEach((a) => { addrMap[a.customer_id] = a; });

  const load = useCallback(async (p = page) => {
    try {
      const params = new URLSearchParams({ page: String(p), per_page: String(PER_PAGE) });
      if (search) params.append("search", search);
      if (countryFilter) params.append("country", countryFilter);
      if (statusFilter) params.append("status", statusFilter);
      if (paymentModeFilter) params.append("payment_mode", paymentModeFilter);
      const res = await api.get(`/admin/customers?${params}`);
      let custs = res.data.customers || [];
      if (partnerMapFilter !== "all") {
        custs = custs.filter((c: any) => partnerMapFilter === "none" ? !c.partner_map : c.partner_map === partnerMapFilter);
      }
      setCustomers(custs);
      setUsers(res.data.users || []);
      setAddresses(res.data.addresses || []);
      setTotalPages(res.data.total_pages || 1);
      setTotal(res.data.total || 0);
      setPage(p);
    } catch { toast.error("Failed to load customers"); }
  }, [search, countryFilter, statusFilter, paymentModeFilter, partnerMapFilter, page]);

  useEffect(() => { load(1); }, [search, countryFilter, statusFilter, paymentModeFilter, partnerMapFilter]);

  const downloadCsv = () => {
    const token = localStorage.getItem("aa_token");
    const baseUrl = process.env.REACT_APP_BACKEND_URL || "";
    fetch(`${baseUrl}/api/admin/export/customers`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.blob()).then(b => { const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = `customers-${new Date().toISOString().slice(0,10)}.csv`; a.click(); })
      .catch(() => toast.error("Export failed"));
  };


  const handleCustomerEdit = async () => {
    if (!selectedCustomer) return;
    try {
      await api.put(`/admin/customers/${selectedCustomer.id}`, {
        customer_data: { full_name: selectedCustomer.full_name, company_name: selectedCustomer.company_name, job_title: selectedCustomer.job_title, phone: selectedCustomer.phone },
        address_data: { line1: selectedCustomer.line1 || "", line2: selectedCustomer.line2 || "", city: selectedCustomer.city || "", region: selectedCustomer.region || "", postal: selectedCustomer.postal || "", country: selectedCustomer.country || "" },
      });
      // Save payment modes if they were set
      if (selectedCustomer._payment_modes_changed) {
        await api.put(`/admin/customers/${selectedCustomer.id}/payment-methods`, {
          allowed_payment_modes: selectedCustomer.allowed_payment_modes || [],
        });
      }
      toast.success("Customer updated"); setSelectedCustomer(null); load(page);
    } catch (e: any) { toast.error(e.response?.data?.detail || "Failed to update"); }
  };

  const handleToggleActive = async (customerId: string, currentActive: boolean) => {
    try {
      await api.patch(`/admin/customers/${customerId}/active?active=${!currentActive}`);
      toast.success(`Customer ${!currentActive ? "activated" : "deactivated"}`); load(page);
    } catch (e: any) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const handleCreateCustomer = async () => {
    try {
      await api.post("/admin/customers/create", newCustomer);
      toast.success("Customer created"); setShowCreateDialog(false);
      setNewCustomer({ full_name: "", company_name: "", job_title: "", email: "", phone: "", password: "", line1: "", line2: "", city: "", region: "", postal: "", country: "", mark_verified: true });
      load(1);
    } catch (e: any) { toast.error(e.response?.data?.detail || "Failed to create customer"); }
  };

  const clearFilters = () => { setSearch(""); setCountryFilter(""); setStatusFilter(""); setPaymentModeFilter(""); setPartnerMapFilter("all"); };

  return (
    <div className="space-y-4" data-testid="customers-tab">
      <AdminPageHeader
        title="Customers"
        subtitle={`${total} customers`}
        actions={
          <>
            <Button size="sm" variant="outline" onClick={downloadCsv} data-testid="admin-customers-export-csv"><Download size={14} className="mr-1" />Export CSV</Button>
            <Button size="sm" variant="outline" onClick={() => setShowImport(true)} data-testid="admin-customers-import-csv"><Upload size={14} className="mr-1" />Import CSV</Button>
            <Button size="sm" onClick={() => setShowCreateDialog(true)} data-testid="admin-create-customer-btn"><Plus size={14} className="mr-1" />Create Customer</Button>
          </>
        }
      />

      {/* Filters */}
      <div className="rounded-xl border border-slate-200 bg-white p-3">
        <div className="flex flex-wrap gap-2 items-end">
          <Input placeholder="Search name / email / company" value={search} onChange={(e) => setSearch(e.target.value)} className="h-8 text-xs w-52" data-testid="admin-customers-search" />
          <Select value={countryFilter || "all"} onValueChange={v => setCountryFilter(v === "all" ? "" : v)}>
            <SelectTrigger className="h-8 text-xs w-36 bg-white" data-testid="admin-customers-country-filter"><SelectValue placeholder="All Countries" /></SelectTrigger>
            <SelectContent><SelectItem value="all">All Countries</SelectItem><SelectItem value="GB">UK</SelectItem><SelectItem value="AU">Australia</SelectItem><SelectItem value="NZ">New Zealand</SelectItem><SelectItem value="CA">Canada</SelectItem><SelectItem value="USA">USA</SelectItem></SelectContent>
          </Select>
          <Select value={statusFilter || "all"} onValueChange={v => setStatusFilter(v === "all" ? "" : v)}>
            <SelectTrigger className="h-8 text-xs w-32 bg-white" data-testid="admin-customers-status-filter"><SelectValue placeholder="All Statuses" /></SelectTrigger>
            <SelectContent><SelectItem value="all">All Statuses</SelectItem><SelectItem value="active">Active</SelectItem><SelectItem value="inactive">Inactive</SelectItem></SelectContent>
          </Select>
          <Select value={paymentModeFilter || "all_modes"} onValueChange={v => setPaymentModeFilter(v === "all_modes" ? "" : v)}>
            <SelectTrigger className="h-8 text-xs w-40 bg-white" data-testid="admin-customers-payment-filter"><SelectValue placeholder="All Methods" /></SelectTrigger>
            <SelectContent>{paymentFilterOptions.map(opt => <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>)}</SelectContent>
          </Select>
          <Select value={partnerMapFilter} onValueChange={setPartnerMapFilter}>
            <SelectTrigger className="h-8 text-xs w-40 bg-white" data-testid="admin-customer-partner-map-filter"><SelectValue placeholder="All Partner Maps" /></SelectTrigger>
            <SelectContent><SelectItem value="all">All Partner Maps</SelectItem><SelectItem value="none">Not set</SelectItem>{PARTNER_MAP_OPTIONS.filter(o => o.value).map(o => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
          </Select>
          <Button size="sm" variant="outline" onClick={clearFilters} className="h-8 text-xs" data-testid="admin-customers-clear">Clear</Button>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
        <Table data-testid="admin-customer-table" className="text-sm min-w-[1000px]">
          <TableHeader>
            <TableRow className="bg-slate-50">
              <TableHead>Name</TableHead><TableHead>Email</TableHead><TableHead>State/Province</TableHead>
              <TableHead>Country</TableHead><TableHead>Status</TableHead>
              <TableHead>Payment Methods</TableHead><TableHead>Partner Map</TableHead>
              {isPlatformAdmin && <TableHead>Partner</TableHead>}
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {customers.map((customer) => {
              const user = userMap[customer.user_id] || {};
              const address = addrMap[customer.id] || {};
              const isActive = user.is_active !== false;
              const pm = customer.partner_map;
              const modes: string[] | undefined = customer.allowed_payment_modes;
              const hasGC = modes ? modes.includes("gocardless") : (customer.allow_bank_transfer ?? true);
              const hasStripe = modes ? modes.includes("stripe") : (customer.allow_card_payment ?? false);
              return (
                <TableRow key={customer.id} data-testid={`admin-customer-row-${customer.id}`}>
                  <TableCell data-testid={`admin-customer-name-${customer.id}`}>{user.full_name || customer.company_name}</TableCell>
                  <TableCell data-testid={`admin-customer-email-${customer.id}`}>{user.email || "—"}</TableCell>
                  <TableCell data-testid={`admin-customer-region-${customer.id}`}>{address.region || "—"}</TableCell>
                  <TableCell data-testid={`admin-customer-country-${customer.id}`}>{address.country || "—"}</TableCell>
                  <TableCell>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${isActive ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`} data-testid={`admin-customer-status-${customer.id}`}>{isActive ? "Active" : "Inactive"}</span>
                  </TableCell>
                  <TableCell data-testid={`admin-customer-payment-modes-${customer.id}`}>
                    <div className="flex flex-wrap gap-1">
                      {hasGC && <span className="text-[10px] px-1.5 py-0.5 rounded font-medium bg-blue-50 text-blue-700">GoCardless</span>}
                      {hasStripe && <span className="text-[10px] px-1.5 py-0.5 rounded font-medium bg-purple-50 text-purple-700">Stripe</span>}
                      {!hasGC && !hasStripe && <span className="text-[10px] text-slate-400 italic">None</span>}
                    </div>
                  </TableCell>
                  <TableCell data-testid={`admin-customer-partner-map-${customer.id}`}>
                    {editingPartnerMap?.customerId === customer.id ? (
                      <div className="flex gap-1 items-center">
                        <Select value={editingPartnerMap.value || "__none__"} onValueChange={v => setEditingPartnerMap({ customerId: customer.id, value: v === "__none__" ? "" : v })}>
                          <SelectTrigger className="h-7 text-xs w-36 bg-white"><SelectValue /></SelectTrigger>
                          <SelectContent>{PARTNER_MAP_OPTIONS.map(o => <SelectItem key={o.value || "__none__"} value={o.value || "__none__"}>{o.label}</SelectItem>)}</SelectContent>
                        </Select>
                        <button onClick={async () => {
                          try {
                            await api.put(`/admin/customers/${customer.id}/partner-map`, { partner_map: editingPartnerMap.value });
                            setCustomers(prev => prev.map(c => c.id === customer.id ? { ...c, partner_map: editingPartnerMap.value } : c));
                            toast.success("Partner Map updated");
                          } catch (e: any) { toast.error(e?.response?.data?.detail || "Failed"); }
                          setEditingPartnerMap(null);
                        }} className="text-green-600 text-xs font-medium hover:text-green-800" data-testid={`admin-partner-map-save-${customer.id}`}>Save</button>
                        <button onClick={() => setEditingPartnerMap(null)} className="text-slate-400 text-xs hover:text-slate-600">✕</button>
                      </div>
                    ) : (
                      <div className="flex gap-1 items-center">
                        <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${pmColor(pm)}`}>{pm || "Not set"}</span>
                        <button onClick={() => setEditingPartnerMap({ customerId: customer.id, value: pm || "" })} className="text-[10px] text-slate-400 hover:text-slate-700 underline" data-testid={`admin-partner-map-edit-${customer.id}`}>edit</button>
                      </div>
                    )}
                  </TableCell>
                  {isPlatformAdmin && <TableCell className="text-xs text-slate-500" data-testid={`admin-customer-partner-${customer.id}`}>{customer.partner_code || "—"}</TableCell>}
                  <TableCell>
                    <div className="flex gap-1 items-center flex-nowrap">
                      <Button variant="outline" size="sm" className="h-6 px-2 text-[11px]" onClick={() => { setSelectedCustomer({ ...customer, ...user, ...address, id: customer.id }); }} data-testid={`admin-customer-edit-${customer.id}`}>Edit</Button>
                      <Button variant="outline" size="sm" className="h-6 px-2 text-[11px]" onClick={async () => { const res = await api.get(`/admin/customers/${customer.id}/notes`); setCustomerNotes(res.data.notes || []); setViewNotesCustomer(customer); }} data-testid={`admin-customer-notes-${customer.id}`}>Notes</Button>
                      <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px]" onClick={() => { setLogsUrl(`/admin/customers/${customer.id}/logs`); setShowAuditLogs(true); }} data-testid={`admin-customer-logs-${customer.id}`}>Logs</Button>
                      {user.id !== authUser?.id && (
                        <Button variant={isActive ? "destructive" : "outline"} size="sm" className="h-6 px-2 text-[11px]" onClick={() => setConfirmToggleCustomer({id: customer.id, active: isActive})} data-testid={`admin-customer-toggle-active-${customer.id}`}>{isActive ? "Deactivate" : "Activate"}</Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
      <AdminPagination page={page} totalPages={totalPages} total={total} perPage={PER_PAGE} onPage={(p) => load(p)} />

      {/* Edit Customer Dialog */}
      <Dialog open={!!selectedCustomer} onOpenChange={(open) => !open && setSelectedCustomer(null)}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="admin-customer-edit-dialog">
          <DialogHeader><DialogTitle>Edit Customer</DialogTitle></DialogHeader>
          {selectedCustomer && (
            <div className="space-y-3">
              {[["Full Name", "full_name"], ["Company", "company_name"], ["Job Title", "job_title"], ["Phone", "phone"]].map(([label, key]) => (
                <div key={key} className="space-y-1">
                  <label className="text-xs text-slate-500">{label}</label>
                  <Input value={selectedCustomer[key] || ""} onChange={(e) => setSelectedCustomer({ ...selectedCustomer, [key]: e.target.value })} />
                </div>
              ))}
              <hr />
              {[["Address Line 1", "line1"], ["Line 2", "line2"], ["City", "city"], ["Region / Province", "region"], ["Postal Code", "postal"]].map(([label, key]) => (
                <div key={key} className="space-y-1">
                  <label className="text-xs text-slate-500">{label}</label>
                  <Input value={selectedCustomer[key] || ""} onChange={(e) => setSelectedCustomer({ ...selectedCustomer, [key]: e.target.value })} />
                </div>
              ))}
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Country</label>
                <SearchableSelect
                  value={selectedCustomer.country || undefined}
                  onValueChange={v => setSelectedCustomer({ ...selectedCustomer, country: v })}
                  options={[{value:"AU",label:"Australia"},{value:"CA",label:"Canada"},{value:"GB",label:"United Kingdom"},{value:"US",label:"United States"},{value:"NZ",label:"New Zealand"},{value:"IN",label:"India"},{value:"SG",label:"Singapore"},{value:"ZA",label:"South Africa"},{value:"OTHER",label:"Other"}]}
                  placeholder="Select country…"
                  searchPlaceholder="Search country..."
                  data-testid="admin-customer-country-select"
                />
              </div>
              <hr />
              <div>
                <label className="text-xs font-medium text-slate-700 block mb-2">Allowed Payment Methods</label>
                <div className="space-y-2">
                  {[
                    { id: "gocardless", label: "GoCardless (Bank Transfer / Direct Debit)", defaultOn: true },
                    { id: "stripe", label: "Stripe (Credit / Debit Card)", defaultOn: false },
                  ].map(mode => {
                    const modes: string[] | undefined = selectedCustomer.allowed_payment_modes;
                    const isEnabled = modes
                      ? modes.includes(mode.id)
                      : mode.id === "gocardless"
                        ? selectedCustomer.allow_bank_transfer ?? true
                        : selectedCustomer.allow_card_payment ?? false;
                    const toggleMode = (checked: boolean) => {
                      const current: string[] = selectedCustomer.allowed_payment_modes
                        ?? ([] as string[])
                          .concat(selectedCustomer.allow_bank_transfer !== false ? ["gocardless"] : [])
                          .concat(selectedCustomer.allow_card_payment ? ["stripe"] : []);
                      const next = checked
                        ? current.concat(mode.id).filter((m: string, i: number, a: string[]) => a.indexOf(m) === i)
                        : current.filter((m: string) => m !== mode.id);
                      setSelectedCustomer({ ...selectedCustomer, allowed_payment_modes: next, _payment_modes_changed: true });
                    };
                    return (
                      <label key={mode.id} className="flex items-center gap-2.5 text-sm cursor-pointer select-none">
                        <input type="checkbox" checked={isEnabled} onChange={e => toggleMode(e.target.checked)}
                          className="h-4 w-4 rounded border-slate-300 accent-slate-900"
                          data-testid={`edit-payment-mode-${mode.id}`} />
                        <span className={isEnabled ? "text-slate-800" : "text-slate-400"}>{mode.label}</span>
                      </label>
                    );
                  })}
                </div>
              </div>
              <Button onClick={handleCustomerEdit} className="w-full" data-testid="admin-customer-save-btn">Save Changes</Button>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Notes Dialog */}
      <Dialog open={!!viewNotesCustomer} onOpenChange={(open) => !open && setViewNotesCustomer(null)}>
        <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto"><DialogHeader><DialogTitle>Notes — {viewNotesCustomer?.company_name || "Customer"}</DialogTitle></DialogHeader>
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {customerNotes.length === 0 ? <p className="text-xs text-slate-400">No notes</p> : customerNotes.map((n: any, i: number) => (
              <div key={i} className="text-xs bg-slate-50 rounded p-2"><span className="text-slate-400">{n.timestamp?.slice(0, 10)}</span> <span>{n.text || n.note || String(n)}</span></div>
            ))}
          </div>
        </DialogContent>
      </Dialog>

      {/* Create Customer Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto"><DialogHeader><DialogTitle>Create Customer</DialogTitle></DialogHeader>
          <div className="space-y-3 max-h-[60vh] overflow-y-auto">
            {[["Full Name", "full_name"], ["Email", "email"], ["Password", "password"], ["Company", "company_name"], ["Job Title", "job_title"], ["Phone", "phone"], ["Address Line 1", "line1"], ["City", "city"], ["Region", "region"], ["Postal", "postal"]].map(([label, key]) => (
              <div key={key} className="space-y-1"><label className="text-xs text-slate-500">{label}</label><Input value={(newCustomer as any)[key]} onChange={(e) => setNewCustomer({ ...newCustomer, [key]: e.target.value })} /></div>
            ))}
            <SearchableSelect
              value={newCustomer.country || undefined}
              onValueChange={v => setNewCustomer({ ...newCustomer, country: v })}
              options={[{value:"GB",label:"United Kingdom"},{value:"AU",label:"Australia"},{value:"NZ",label:"New Zealand"},{value:"CA",label:"Canada"},{value:"US",label:"United States"}]}
              placeholder="Select country…"
              searchPlaceholder="Search country..."
            />
            <Button onClick={handleCreateCustomer} className="w-full" data-testid="admin-create-customer-save-btn">Create</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Customer Audit Logs Dialog */}
      <AuditLogDialog open={showAuditLogs} onOpenChange={setShowAuditLogs} title="Customer Audit Logs" logsUrl={logsUrl} />
      <ImportModal
        entity="customers"
        entityLabel="Customers"
        open={showImport}
        onClose={() => setShowImport(false)}
        onSuccess={load}
      />

      {/* Deactivate/Activate Customer Confirmation */}
      <AlertDialog open={!!confirmToggleCustomer} onOpenChange={(open) => !open && setConfirmToggleCustomer(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{confirmToggleCustomer?.active ? "Deactivate Customer" : "Activate Customer"}</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to {confirmToggleCustomer?.active ? "deactivate" : "activate"} this customer?
              {confirmToggleCustomer?.active && " They will no longer be able to log in."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className={confirmToggleCustomer?.active ? "bg-red-600 hover:bg-red-700" : ""}
              onClick={() => { handleToggleActive(confirmToggleCustomer!.id, confirmToggleCustomer!.active); setConfirmToggleCustomer(null); }}
              data-testid="confirm-customer-toggle"
            >
              {confirmToggleCustomer?.active ? "Deactivate" : "Activate"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

