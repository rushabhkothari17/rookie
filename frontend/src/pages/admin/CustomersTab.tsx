import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { AdminPageHeader } from "./shared/AdminPageHeader";
import { AdminPagination } from "./shared/AdminPagination";
import { useAuth } from "@/contexts/AuthContext";
import { Download, Plus } from "lucide-react";

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
  const [customers, setCustomers] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [addresses, setAddresses] = useState<any[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const PER_PAGE = 20;

  // Filters
  const [search, setSearch] = useState("");
  const [countryFilter, setCountryFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [bankFilter, setBankFilter] = useState("");
  const [cardFilter, setCardFilter] = useState("");
  const [partnerMapFilter, setPartnerMapFilter] = useState("all");

  // Dialogs
  const [selectedCustomer, setSelectedCustomer] = useState<any>(null);
  const [viewNotesCustomer, setViewNotesCustomer] = useState<any>(null);
  const [customerNotes, setCustomerNotes] = useState<any[]>([]);
  const [editingPartnerMap, setEditingPartnerMap] = useState<{ customerId: string; value: string } | null>(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [newCustomer, setNewCustomer] = useState({ full_name: "", company_name: "", job_title: "", email: "", phone: "", password: "", line1: "", line2: "", city: "", region: "", postal: "", country: "GB", mark_verified: true });

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
      if (bankFilter) params.append("bank_transfer", bankFilter);
      if (cardFilter) params.append("card_payment", cardFilter);
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
  }, [search, countryFilter, statusFilter, bankFilter, cardFilter, partnerMapFilter, page]);

  useEffect(() => { load(1); }, [search, countryFilter, statusFilter, bankFilter, cardFilter, partnerMapFilter]);

  const downloadCsv = () => {
    const token = localStorage.getItem("aa_token");
    const baseUrl = process.env.REACT_APP_BACKEND_URL || "";
    fetch(`${baseUrl}/api/admin/export/customers`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.blob()).then(b => { const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = `customers-${new Date().toISOString().slice(0,10)}.csv`; a.click(); })
      .catch(() => toast.error("Export failed"));
  };

  const handlePaymentToggle = async (customerId: string, field: string, value: boolean) => {
    const customer = customers.find((c) => c.id === customerId);
    try {
      await api.put(`/admin/customers/${customerId}/payment-methods`, {
        allow_bank_transfer: field === "allow_bank_transfer" ? value : customer?.allow_bank_transfer ?? true,
        allow_card_payment: field === "allow_card_payment" ? value : customer?.allow_card_payment ?? false,
      });
      toast.success("Payment method updated");
      load(page);
    } catch (e: any) { toast.error(e.response?.data?.detail || "Update failed"); }
  };

  const handleCustomerEdit = async () => {
    if (!selectedCustomer) return;
    try {
      await api.put(`/admin/customers/${selectedCustomer.id}`, {
        customer_data: { full_name: selectedCustomer.full_name, company_name: selectedCustomer.company_name, job_title: selectedCustomer.job_title, phone: selectedCustomer.phone },
        address_data: { line1: selectedCustomer.line1 || "", line2: selectedCustomer.line2 || "", city: selectedCustomer.city || "", region: selectedCustomer.region || "", postal: selectedCustomer.postal || "" },
      });
      toast.success("Customer updated"); setSelectedCustomer(null); load(page);
    } catch (e: any) { toast.error(e.response?.data?.detail || "Failed to update"); }
  };

  const handleToggleActive = async (customerId: string, currentActive: boolean) => {
    if (!confirm(`${!currentActive ? "Activate" : "Deactivate"} this customer?`)) return;
    try {
      await api.patch(`/admin/customers/${customerId}/active?active=${!currentActive}`);
      toast.success(`Customer ${!currentActive ? "activated" : "deactivated"}`); load(page);
    } catch (e: any) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const handleCreateCustomer = async () => {
    try {
      await api.post("/admin/customers/create", newCustomer);
      toast.success("Customer created"); setShowCreateDialog(false);
      setNewCustomer({ full_name: "", company_name: "", job_title: "", email: "", phone: "", password: "", line1: "", line2: "", city: "", region: "", postal: "", country: "GB", mark_verified: true });
      load(1);
    } catch (e: any) { toast.error(e.response?.data?.detail || "Failed to create customer"); }
  };

  const clearFilters = () => { setSearch(""); setCountryFilter(""); setStatusFilter(""); setBankFilter(""); setCardFilter(""); setPartnerMapFilter("all"); };

  return (
    <div className="space-y-4" data-testid="customers-tab">
      <AdminPageHeader
        title="Customers"
        subtitle={`${total} customers`}
        actions={
          <>
            <Button size="sm" variant="outline" onClick={downloadCsv} data-testid="admin-customers-export-csv"><Download size={14} className="mr-1" />Export CSV</Button>
            <Button size="sm" onClick={() => setShowCreateDialog(true)} data-testid="admin-create-customer-btn"><Plus size={14} className="mr-1" />Create Customer</Button>
          </>
        }
      />

      {/* Currency Override */}
      <CurrencyOverrideWidget />

      {/* Filters */}
      <div className="rounded-xl border border-slate-200 bg-white p-3">
        <div className="flex flex-wrap gap-2 items-end">
          <Input placeholder="Search name / email / company" value={search} onChange={(e) => setSearch(e.target.value)} className="h-8 text-xs w-52" data-testid="admin-customers-search" />
          <select value={countryFilter} onChange={(e) => setCountryFilter(e.target.value)} className="h-8 text-xs border border-slate-200 rounded px-2 bg-white" data-testid="admin-customers-country-filter">
            <option value="">All Countries</option>
            <option value="GB">UK</option><option value="AU">Australia</option><option value="NZ">New Zealand</option><option value="CA">Canada</option><option value="USA">USA</option>
          </select>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="h-8 text-xs border border-slate-200 rounded px-2 bg-white" data-testid="admin-customers-status-filter">
            <option value="">All Statuses</option><option value="active">Active</option><option value="inactive">Inactive</option>
          </select>
          <select value={bankFilter} onChange={(e) => setBankFilter(e.target.value)} className="h-8 text-xs border border-slate-200 rounded px-2 bg-white">
            <option value="">Bank Transfer: All</option><option value="true">Enabled</option><option value="false">Disabled</option>
          </select>
          <select value={cardFilter} onChange={(e) => setCardFilter(e.target.value)} className="h-8 text-xs border border-slate-200 rounded px-2 bg-white">
            <option value="">Card Payment: All</option><option value="true">Enabled</option><option value="false">Disabled</option>
          </select>
          <select value={partnerMapFilter} onChange={(e) => setPartnerMapFilter(e.target.value)} className="h-8 text-xs border border-slate-200 rounded px-2 bg-white" data-testid="admin-customer-partner-map-filter">
            <option value="all">All Partner Maps</option><option value="none">Not set</option>
            {PARTNER_MAP_OPTIONS.filter(o => o.value).map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <Button size="sm" variant="outline" onClick={clearFilters} className="h-8 text-xs">Clear</Button>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
        <Table data-testid="admin-customer-table" className="text-xs min-w-[1000px]">
          <TableHeader>
            <TableRow className="bg-slate-50">
              <TableHead>Name</TableHead><TableHead>Email</TableHead><TableHead>State/Province</TableHead>
              <TableHead>Country</TableHead><TableHead>Status</TableHead><TableHead>Bank Transfer</TableHead>
              <TableHead>Card Payment</TableHead><TableHead>Partner Map</TableHead><TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {customers.map((customer) => {
              const user = userMap[customer.user_id] || {};
              const address = addrMap[customer.id] || {};
              const isActive = user.is_active !== false;
              const pm = customer.partner_map;
              return (
                <TableRow key={customer.id} data-testid={`admin-customer-row-${customer.id}`}>
                  <TableCell data-testid={`admin-customer-name-${customer.id}`}>{user.full_name || customer.company_name}</TableCell>
                  <TableCell data-testid={`admin-customer-email-${customer.id}`}>{user.email || "—"}</TableCell>
                  <TableCell data-testid={`admin-customer-region-${customer.id}`}>{address.region || "—"}</TableCell>
                  <TableCell data-testid={`admin-customer-country-${customer.id}`}>{address.country || "—"}</TableCell>
                  <TableCell>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${isActive ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`} data-testid={`admin-customer-status-${customer.id}`}>{isActive ? "Active" : "Inactive"}</span>
                  </TableCell>
                  <TableCell>
                    <button onClick={() => handlePaymentToggle(customer.id, "allow_bank_transfer", !(customer.allow_bank_transfer ?? true))} className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${(customer.allow_bank_transfer ?? true) ? "bg-slate-900" : "bg-slate-200"}`} data-testid={`admin-customer-bank-toggle-${customer.id}`}>
                      <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${(customer.allow_bank_transfer ?? true) ? "translate-x-4" : "translate-x-0.5"}`} />
                    </button>
                  </TableCell>
                  <TableCell>
                    <button onClick={() => handlePaymentToggle(customer.id, "allow_card_payment", !(customer.allow_card_payment ?? false))} className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${(customer.allow_card_payment ?? false) ? "bg-slate-900" : "bg-slate-200"}`} data-testid={`admin-customer-card-toggle-${customer.id}`}>
                      <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${(customer.allow_card_payment ?? false) ? "translate-x-4" : "translate-x-0.5"}`} />
                    </button>
                  </TableCell>
                  <TableCell data-testid={`admin-customer-partner-map-${customer.id}`}>
                    {editingPartnerMap?.customerId === customer.id ? (
                      <div className="flex gap-1 items-center">
                        <select value={editingPartnerMap.value} onChange={(e) => setEditingPartnerMap({ customerId: customer.id, value: e.target.value })} className="text-xs border border-slate-300 rounded px-1 py-0.5 bg-white" autoFocus>
                          {PARTNER_MAP_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                        </select>
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
                  <TableCell>
                    <div className="flex gap-1 items-center flex-nowrap">
                      <Button variant="outline" size="sm" className="h-6 px-2 text-[11px]" onClick={() => { setSelectedCustomer({ ...customer, ...user, ...address }); }} data-testid={`admin-customer-edit-${customer.id}`}>Edit</Button>
                      <Button variant="outline" size="sm" className="h-6 px-2 text-[11px]" onClick={async () => { const res = await api.get(`/admin/customers/${customer.id}/notes`); setCustomerNotes(res.data.notes || []); setViewNotesCustomer(customer); }} data-testid={`admin-customer-notes-${customer.id}`}>Notes</Button>
                      {user.id !== authUser?.id && (
                        <Button variant={isActive ? "destructive" : "outline"} size="sm" className="h-6 px-2 text-[11px]" onClick={() => handleToggleActive(customer.id, isActive)} data-testid={`admin-customer-toggle-active-${customer.id}`}>{isActive ? "Deactivate" : "Activate"}</Button>
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
        <DialogContent data-testid="admin-customer-edit-dialog">
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
              {[["Address Line 1", "line1"], ["Line 2", "line2"], ["City", "city"], ["Region", "region"], ["Postal", "postal"]].map(([label, key]) => (
                <div key={key} className="space-y-1">
                  <label className="text-xs text-slate-500">{label}</label>
                  <Input value={selectedCustomer[key] || ""} onChange={(e) => setSelectedCustomer({ ...selectedCustomer, [key]: e.target.value })} />
                </div>
              ))}
              <Button onClick={handleCustomerEdit} className="w-full" data-testid="admin-customer-save-btn">Save Changes</Button>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Notes Dialog */}
      <Dialog open={!!viewNotesCustomer} onOpenChange={(open) => !open && setViewNotesCustomer(null)}>
        <DialogContent><DialogHeader><DialogTitle>Notes — {viewNotesCustomer?.company_name || "Customer"}</DialogTitle></DialogHeader>
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {customerNotes.length === 0 ? <p className="text-xs text-slate-400">No notes</p> : customerNotes.map((n: any, i: number) => (
              <div key={i} className="text-xs bg-slate-50 rounded p-2"><span className="text-slate-400">{n.timestamp?.slice(0, 10)}</span> <span>{n.text || n.note || String(n)}</span></div>
            ))}
          </div>
        </DialogContent>
      </Dialog>

      {/* Create Customer Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent><DialogHeader><DialogTitle>Create Customer</DialogTitle></DialogHeader>
          <div className="space-y-3 max-h-[60vh] overflow-y-auto">
            {[["Full Name", "full_name"], ["Email", "email"], ["Password", "password"], ["Company", "company_name"], ["Job Title", "job_title"], ["Phone", "phone"], ["Address Line 1", "line1"], ["City", "city"], ["Region", "region"], ["Postal", "postal"]].map(([label, key]) => (
              <div key={key} className="space-y-1"><label className="text-xs text-slate-500">{label}</label><Input value={(newCustomer as any)[key]} onChange={(e) => setNewCustomer({ ...newCustomer, [key]: e.target.value })} /></div>
            ))}
            <select value={newCustomer.country} onChange={(e) => setNewCustomer({ ...newCustomer, country: e.target.value })} className="w-full h-9 text-sm border border-slate-200 rounded px-2 bg-white">
              <option value="GB">United Kingdom</option><option value="AU">Australia</option><option value="NZ">New Zealand</option><option value="CA">Canada</option><option value="USA">USA</option>
            </select>
            <Button onClick={handleCreateCustomer} className="w-full" data-testid="admin-create-customer-save-btn">Create</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function CurrencyOverrideWidget() {
  const [val, setVal] = useState({ email: "", currency: "USD" });
  const handle = async () => {
    try { await api.post("/admin/currency-override", { customer_email: val.email, currency: val.currency }); toast.success("Currency overridden"); }
    catch (e: any) { toast.error(e.response?.data?.detail || "Override failed"); }
  };
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <h3 className="text-sm font-semibold text-slate-900 mb-3">Currency override</h3>
      <div className="grid gap-3 md:grid-cols-3">
        <Input placeholder="Customer email" value={val.email} onChange={(e) => setVal({ ...val, email: e.target.value })} data-testid="admin-currency-email" />
        <Input placeholder="Currency (USD/CAD)" value={val.currency} onChange={(e) => setVal({ ...val, currency: e.target.value })} data-testid="admin-currency-value" />
        <Button onClick={handle} data-testid="admin-currency-submit">Override</Button>
      </div>
    </div>
  );
}
