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
import { CustomersStats } from "./shared/DashboardStats";
import { AdminPagination } from "./shared/AdminPagination";
import { AuditLogDialog } from "@/components/AuditLogDialog";
import { Download, Plus, Upload} from "lucide-react";
import { ColHeader } from "@/components/shared/ColHeader";
import { FieldTip } from "./shared/FieldTip";
import { SearchableSelect } from "@/components/ui/searchable-select";
import { getAddressConfig, parseSchema } from "@/components/FormSchemaBuilder";
import { Textarea } from "@/components/ui/textarea";
import { CustomerSignupFields } from "@/components/CustomerSignupFields";
import { useCountries } from "@/hooks/useCountries";


export function CustomersTab() {
  const { user: authUser } = useAuth();
  const isPlatformAdmin = authUser?.role === "platform_admin" || authUser?.role === "platform_super_admin";
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
  const [nameFilter, setNameFilter] = useState<string[]>([]);
  const [emailSearch, setEmailSearch] = useState("");
  const [stateFilter, setStateFilter] = useState<string[]>([]);
  const [countryFilter, setCountryFilter] = useState<string[]>([]);
  const [statusFilter, setStatusFilter] = useState<string[]>([]);
  const [paymentModeFilter, setPaymentModeFilter] = useState<string[]>([]);
  const [partnerFilter, setPartnerFilter] = useState<string[]>([]);

  // Dialogs
  const [selectedCustomer, setSelectedCustomer] = useState<any>(null);
  const [viewNotesCustomer, setViewNotesCustomer] = useState<any>(null);
  const [customerNotes, setCustomerNotes] = useState<any[]>([]);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [newCustomer, setNewCustomer] = useState({ full_name: "", company_name: "", job_title: "", email: "", phone: "", password: "", line1: "", line2: "", city: "", region: "", postal: "", country: "", mark_verified: true });
  const [signupSchema, setSignupSchema] = useState<any[]>([]);
  const [newCustomerExtras, setNewCustomerExtras] = useState<Record<string, string>>({});
  const [provinces, setProvinces] = useState<{value:string;label:string}[]>([]);
  const countries = useCountries();

  const STD_CREATE_KEYS = ["full_name", "email", "password", "company_name", "job_title", "phone", "line1", "line2", "city", "region", "postal", "country"];

  const handleCreateFieldChange = (key: string, value: string) => {
    if (STD_CREATE_KEYS.includes(key)) {
      if (key === "country") {
        setNewCustomer(prev => ({ ...prev, country: value, region: "" }));
      } else {
        setNewCustomer(prev => ({ ...prev, [key]: value }));
      }
    } else {
      setNewCustomerExtras(prev => ({ ...prev, [key]: value }));
    }
  };

  const createValues: Record<string, string> = {
    ...Object.fromEntries(Object.entries(newCustomer).map(([k, v]) => [k, String(v)])),
    ...newCustomerExtras,
  };

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
      if (nameFilter.length > 0) params.append("name", nameFilter.join(","));
      if (emailSearch) params.append("email", emailSearch);
      if (stateFilter.length > 0) params.append("state", stateFilter.join(","));
      if (countryFilter.length > 0) params.append("country", countryFilter.join(","));
      if (statusFilter.length > 0) params.append("status", statusFilter.join(","));
      if (paymentModeFilter.length > 0) params.append("payment_mode", paymentModeFilter.join(","));
      if (partnerFilter.length > 0) params.append("partner", partnerFilter.join(","));
      const res = await api.get(`/admin/customers?${params}`);
      let custs = res.data.customers || [];
      setCustomers(custs);
      setUsers(res.data.users || []);
      setAddresses(res.data.addresses || []);
      setTotalPages(res.data.total_pages || 1);
      setTotal(res.data.total || 0);
      setPage(p);
    } catch { toast.error("Failed to load customers"); }
  }, [nameFilter, emailSearch, stateFilter, countryFilter, statusFilter, paymentModeFilter, partnerFilter, page]);

  useEffect(() => { load(1); }, [nameFilter, emailSearch, stateFilter, countryFilter, statusFilter, paymentModeFilter, partnerFilter]);

  // Fetch signup form schema whenever Create dialog opens (ensures fresh schema)
  useEffect(() => {
    if (!showCreateDialog) return;
    api.get("/admin/website-settings").then(r => {
      try { setSignupSchema(JSON.parse(r.data.settings?.signup_form_schema || "[]")); }
      catch { setSignupSchema([]); }
    }).catch(() => {});
  }, [showCreateDialog]);

  // Fetch provinces when country changes in create form
  useEffect(() => {
    const c = newCustomer.country;
    if (c) {
      api.get(`/utils/provinces?country_code=${encodeURIComponent(c)}`)
        .then(r => setProvinces(r.data.regions || []))
        .catch(() => setProvinces([]));
    } else { setProvinces([]); }
  }, [newCustomer.country]);

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
      // Save tax_exempt if changed
      if (selectedCustomer._tax_exempt_changed) {
        await api.patch(`/admin/customers/${selectedCustomer.id}/tax-exempt`, {
          tax_exempt: !!selectedCustomer.tax_exempt,
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
    const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
    const PHONE_REGEX = /^[+\d][\d\s\-(). ]{3,49}$/;
    const schemaField = (key: string) => signupSchema.find((f: any) => f.key === key);
    const errors: string[] = [];
    if (!newCustomer.full_name.trim()) errors.push("Full Name");
    else if (newCustomer.full_name.trim().length > 50) errors.push("Full Name (max 50 characters)");
    if (!newCustomer.email.trim()) errors.push("Email");
    else if (!EMAIL_REGEX.test(newCustomer.email.trim())) errors.push("Email (invalid format)");
    else if (newCustomer.email.trim().length > 50) errors.push("Email (max 50 characters)");
    if (!newCustomer.password.trim()) errors.push("Password");
    if (newCustomer.company_name && newCustomer.company_name.length > 50) errors.push("Company Name (max 50 characters)");
    if (newCustomer.job_title && newCustomer.job_title.length > 50) errors.push("Job Title (max 50 characters)");
    if (newCustomer.phone) {
      if (newCustomer.phone.length > 50) errors.push("Phone (max 50 characters)");
      else if (!PHONE_REGEX.test(newCustomer.phone.trim())) errors.push("Phone (invalid format — digits, +, -, spaces only)");
    }
    const addrField = schemaField("address");
    const addrEnabled = !addrField || addrField.enabled !== false;
    if (addrEnabled && addrField) {
      const addrCfg = getAddressConfig(addrField);
      if (addrCfg.line1.required && !newCustomer.line1.trim()) errors.push("Address Line 1");
      if (addrCfg.city.required && !newCustomer.city.trim()) errors.push("City");
      if (addrCfg.postal.required && !newCustomer.postal.trim()) errors.push("Postal Code");
      if (addrCfg.country.required && !newCustomer.country) errors.push("Country");
      if (addrCfg.state.required && !newCustomer.region) errors.push("State / Province");
    }
    ["company_name", "job_title", "phone"].forEach(key => {
      const f = schemaField(key);
      if (f?.required && !(newCustomer as any)[key]?.trim()) errors.push(f.label || key);
    });
    if (errors.length) { toast.error(`Required: ${errors.join(", ")}`); return; }
    try {
      const profile_meta = Object.keys(newCustomerExtras).length ? newCustomerExtras : undefined;
      await api.post("/admin/customers/create", { ...newCustomer, ...(profile_meta ? { profile_meta } : {}) });
      toast.success("Customer created"); setShowCreateDialog(false);
      setNewCustomer({ full_name: "", company_name: "", job_title: "", email: "", phone: "", password: "", line1: "", line2: "", city: "", region: "", postal: "", country: "", mark_verified: true });
      setNewCustomerExtras({});
      load(1);
    } catch (e: any) { toast.error(e.response?.data?.detail || "Failed to create customer"); }
  };

  const [colSort, setColSort] = useState<{ col: string; dir: "asc" | "desc" } | null>(null);

  // Build unique option lists for filters
  const uniqueNames = useMemo(() => {
    const names = new Set<string>();
    customers.forEach(c => {
      const u = userMap[c.user_id];
      if (u?.full_name) names.add(u.full_name);
      if (c.company_name) names.add(c.company_name);
    });
    return Array.from(names).sort().map(n => [n, n] as [string, string]);
  }, [customers, userMap]);

  const uniqueStates = useMemo(() => {
    const states = new Set<string>();
    addresses.forEach(a => { if (a.region) states.add(a.region); });
    return Array.from(states).sort().map(s => [s, s] as [string, string]);
  }, [addresses]);

  const uniquePartners = useMemo(() => {
    const partners = new Set<string>();
    customers.forEach(c => { if (c.partner_code) partners.add(c.partner_code); });
    return Array.from(partners).sort().map(p => [p, p] as [string, string]);
  }, [customers]);

  const displayCustomers = useMemo(() => {
    const r = [...customers];
    if (colSort) {
      r.sort((a, b) => {
        const um: Record<string, any> = {};
        users.forEach((u: any) => { um[u.id] = u; });
        let av: any = "", bv: any = "";
        if (colSort.col === "name") { av = (um[a.user_id]?.full_name || a.company_name || "").toLowerCase(); bv = (um[b.user_id]?.full_name || b.company_name || "").toLowerCase(); }
        else if (colSort.col === "email") { av = um[a.user_id]?.email || ""; bv = um[b.user_id]?.email || ""; }
        else if (colSort.col === "country") { av = a.country || ""; bv = b.country || ""; }
        else if (colSort.col === "status") { av = um[a.user_id]?.is_active ? 1 : 0; bv = um[b.user_id]?.is_active ? 1 : 0; }
        if (av < bv) return colSort.dir === "asc" ? -1 : 1;
        if (av > bv) return colSort.dir === "asc" ? 1 : -1;
        return 0;
      });
    }
    return r;
  }, [customers, users, colSort]);

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

      {/* Stats Dashboard */}
      <CustomersStats />

      {/* Filters removed — use column headers */}

      {/* Table */}
      <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
        <Table data-testid="admin-customer-table" className="text-sm min-w-[1000px]">
          <TableHeader>
            <TableRow className="bg-slate-50">
              <ColHeader label="Name" colKey="name" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={nameFilter} onFilter={v => setNameFilter(v)} onClearFilter={() => setNameFilter([])} statusOptions={uniqueNames} />
              <ColHeader label="Email" colKey="email" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="text" filterValue={emailSearch} onFilter={v => setEmailSearch(v)} onClearFilter={() => setEmailSearch("")} />
              <ColHeader label="State/Province" colKey="state" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={stateFilter} onFilter={v => setStateFilter(v)} onClearFilter={() => setStateFilter([])} statusOptions={uniqueStates} />
              <ColHeader label="Country" colKey="country" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={countryFilter} onFilter={v => setCountryFilter(v)} onClearFilter={() => setCountryFilter([])} statusOptions={countries.map(c => [c.value, c.label] as [string, string])} />
              <ColHeader label="Status" colKey="status" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={statusFilter} onFilter={v => setStatusFilter(v)} onClearFilter={() => setStatusFilter([])} statusOptions={[["active", "Active"], ["inactive", "Inactive"]]} />
              <ColHeader label="Payment Methods" colKey="payment" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={paymentModeFilter} onFilter={v => setPaymentModeFilter(v)} onClearFilter={() => setPaymentModeFilter([])} statusOptions={paymentFilterOptions.filter(o => o.value && o.value !== "all_modes").map(o => [o.value, o.label] as [string, string])} />
              {isPlatformAdmin && <ColHeader label="Partner" colKey="partner" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={partnerFilter} onFilter={v => setPartnerFilter(v)} onClearFilter={() => setPartnerFilter([])} statusOptions={uniquePartners} />}
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500">Actions</th>
            </TableRow>
          </TableHeader>
          <TableBody>
            {displayCustomers.map((customer) => {
              const user = userMap[customer.user_id] || {};
              const address = addrMap[customer.id] || {};
              const isActive = user.is_active !== false;
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
                  options={countries.length ? countries : [{value:"Canada",label:"Canada"},{value:"USA",label:"United States"}]}
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
              <hr />
              <div className="flex items-center justify-between py-1">
                <div>
                  <label className="text-sm font-medium text-slate-700">Tax Exempt</label>
                  <p className="text-xs text-slate-400">Customer will not be charged any tax at checkout.</p>
                </div>
                <input
                  type="checkbox"
                  checked={!!selectedCustomer.tax_exempt}
                  onChange={(e) => setSelectedCustomer({ ...selectedCustomer, tax_exempt: e.target.checked, _tax_exempt_changed: true })}
                  className="h-4 w-4 rounded border-slate-300 accent-slate-900"
                  data-testid="edit-customer-tax-exempt"
                />
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
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Create Customer</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <CustomerSignupFields
              schema={parseSchema(JSON.stringify(signupSchema))}
              values={createValues}
              onChange={handleCreateFieldChange}
              provinces={provinces}
              countries={countries.length ? countries : [{ value: "Canada", label: "Canada" }, { value: "USA", label: "United States" }]}
              showPassword={true}
              compact={true}
            />
            <Button onClick={handleCreateCustomer} className="w-full" data-testid="admin-create-customer-save-btn">Create Customer</Button>
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

