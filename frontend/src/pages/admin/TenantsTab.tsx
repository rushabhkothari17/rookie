import { useState, useEffect } from "react";
import { RequiredLabel } from "@/components/shared/RequiredLabel";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/components/ui/sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Check, Copy, Plus, Building2, Users, Power, PowerOff, RefreshCw, ChevronDown, ChevronUp, MapPin, ShieldCheck, Eye, StickyNote, ScrollText, MoreHorizontal, Pencil } from "lucide-react";
import { FieldTip } from "./shared/FieldTip";
import { AuditLogDialog } from "@/components/AuditLogDialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useCountries, useProvinces } from "@/hooks/useCountries";
import { TenantLicenseModal } from "./TenantLicenseModal";
import { TenantNotesModal } from "./TenantNotesModal";
import { useSupportedCurrencies } from "@/hooks/useSupportedCurrencies";
import { PartnerOrgForm, PartnerOrgFormValue, EMPTY_PARTNER_ORG } from "@/components/admin/PartnerOrgForm";
import { useWebsite } from "@/contexts/WebsiteContext";

type TenantAddress = {
  line1?: string; line2?: string; city?: string; region?: string; postal?: string; country?: string;
};

type Tenant = {
  id: string;
  name: string;
  code: string;
  status: "active" | "inactive";
  store_name?: string;
  created_at: string;
  address?: TenantAddress;
  base_currency?: string;
};

type TenantUser = {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
};

interface ModuleInfo {
  key: string;
  name: string;
  description: string;
}

interface PresetRole {
  key: string;
  name: string;
  description: string;
  module_permissions: Record<string, "read" | "write">;
}

export function TenantsTab() {
  const { currencies: supportedCurrencies } = useSupportedCurrencies();
  const ws = useWebsite();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedTenant, setExpandedTenant] = useState<string | null>(null);
  const [tenantUsers, setTenantUsers] = useState<Record<string, TenantUser[]>>({});
  const [planFilter, setPlanFilter] = useState<string>("all");
  const [plans, setPlans] = useState<{ id: string; name: string }[]>([]);

  const [auditTenant, setAuditTenant] = useState<{ id: string; name: string } | null>(null);

  // Create tenant dialog
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [generatedCode, setGeneratedCode] = useState("");
  const [codeCopied, setCodeCopied] = useState(false);
  const [newPartner, setNewPartner] = useState<PartnerOrgFormValue>(EMPTY_PARTNER_ORG);

  // Edit org details dialog
  const [showEditDetails, setShowEditDetails] = useState<Tenant | null>(null);
  const [editDetailsForm, setEditDetailsForm] = useState({ name: "" });
  const [savingDetails, setSavingDetails] = useState(false);

  // Create partner admin dialog
  const [showCreateAdmin, setShowCreateAdmin] = useState<string | null>(null);
  const [newAdmin, setNewAdmin] = useState({ 
    email: "", full_name: "", password: "", role: "partner_admin",
  });
  const [newAdminPerms, setNewAdminPerms] = useState<Record<string, "read" | "write" | "none">>({});
  const [creatingAdmin, setCreatingAdmin] = useState(false);
  const [modules, setModules] = useState<ModuleInfo[]>([]);
  const [presetRoles, setPresetRoles] = useState<PresetRole[]>([]);

  useEffect(() => {
    api.get("/admin/permissions/modules").then(r => {
      setModules(r.data.modules || []);
      setPresetRoles(r.data.preset_roles || []);
    }).catch(() => {});
  }, []);

  // Address edit dialog
  const [showAddressEdit, setShowAddressEdit] = useState<string | null>(null);

  // License & Notes modals
  const [showLicense, setShowLicense] = useState<{ id: string; name: string } | null>(null);
  const [showNotes, setShowNotes] = useState<{ id: string; name: string } | null>(null);
  const [addrForm, setAddrForm] = useState<TenantAddress>({});
  const [addrSaving, setAddrSaving] = useState(false);

  const countries = useCountries();
  const addrProvinces = useProvinces(addrForm.country || "");

  const openAddressEdit = (tenant: Tenant) => {
    setAddrForm(tenant.address || {});
    setShowAddressEdit(tenant.id);
  };

  const saveAddress = async () => {
    if (!showAddressEdit) return;
    setAddrSaving(true);
    try {
      await api.put(`/admin/tenants/${showAddressEdit}/address`, { address: addrForm });
      toast.success("Address saved");
      setShowAddressEdit(null);
      await load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to save address");
    } finally {
      setAddrSaving(false); }
  };

  const load = async () => {
    try {
      const params = new URLSearchParams();
      if (planFilter && planFilter !== "all") params.set("plan_id", planFilter);
      const { data } = await api.get(`/admin/tenants?${params}`);
      setTenants(data.tenants || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [planFilter]);

  useEffect(() => {
    api.get("/admin/plans").then(r => setPlans(r.data.plans || [])).catch(() => {});
  }, []);

  const loadUsers = async (tenantId: string) => {
    try {
      const { data } = await api.get(`/admin/tenants/${tenantId}/users`);
      setTenantUsers(prev => ({ ...prev, [tenantId]: data.users || [] }));
    } catch {
      toast.error("Failed to load users");
    }
  };

  const toggleExpand = async (tenantId: string) => {
    if (expandedTenant === tenantId) {
      setExpandedTenant(null);
    } else {
      setExpandedTenant(tenantId);
      if (!tenantUsers[tenantId]) {
        await loadUsers(tenantId);
      }
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      const res = await api.post("/admin/tenants/create-partner", newPartner);
      setGeneratedCode(res.data.partner_code || "");
      load();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to create partner organization");
    } finally {
      setCreating(false);
    }
  };

  const applyPresetToAdmin = (roleKey: string) => {
    const preset = presetRoles.find((r: any) => r.key === roleKey);
    if (preset?.module_permissions) {
      setNewAdminPerms(preset.module_permissions);
    }
  };

  const handleCloseCreate = () => {
    setShowCreate(false);
    setGeneratedCode("");
    setCodeCopied(false);
    setNewPartner(EMPTY_PARTNER_ORG);
  };

  const openEditDetails = (tenant: Tenant) => {
    setShowEditDetails(tenant);
    setEditDetailsForm({ name: tenant.name });
  };

  const handleSaveDetails = async () => {
    if (!showEditDetails) return;
    setSavingDetails(true);
    try {
      await api.put(`/admin/tenants/${showEditDetails.id}`, {
        name: editDetailsForm.name || undefined,
      });
      toast.success("Organization details updated");
      setShowEditDetails(null);
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to save");
    } finally {
      setSavingDetails(false);
    }
  };

  const toggleStatus = async (tenant: Tenant) => {
    if (tenant.code === "automate-accounts") {
      toast.error("Cannot deactivate the default tenant");
      return;
    }
    const endpoint = tenant.status === "active"
      ? `/admin/tenants/${tenant.id}/deactivate`
      : `/admin/tenants/${tenant.id}/activate`;
    try {
      await api.post(endpoint);
      toast.success(`Tenant ${tenant.status === "active" ? "deactivated" : "activated"}`);
      load();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to update status");
    }
  };

  const handleCreateAdmin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!showCreateAdmin) return;
    setCreatingAdmin(true);
    try {
      const mp = Object.fromEntries(Object.entries(newAdminPerms).filter(([, v]) => v !== "none"));
      const payload = {
        tenant_id: showCreateAdmin,
        email: newAdmin.email,
        full_name: newAdmin.full_name,
        password: newAdmin.password,
        role: newAdmin.role,
        module_permissions: mp,
      };
      await api.post(`/admin/tenants/${showCreateAdmin}/create-admin`, payload);
      toast.success("Admin user created");
      setShowCreateAdmin(null);
      setNewAdmin({ email: "", full_name: "", password: "", role: "partner_admin" });
      setNewAdminPerms({});
      loadUsers(showCreateAdmin);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to create admin");
    } finally {
      setCreatingAdmin(false);
    }
  };

  return (
    <div data-testid="tenants-tab">
      <div className="flex flex-col gap-4" data-testid="tenants-tab-inner">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Partner Organizations</h2>
          <p className="text-sm text-slate-500">{tenants.length} organization{tenants.length !== 1 ? "s" : ""}</p>
        </div>
        <div className="flex gap-2 items-center">
          {plans.length > 0 && (
            <Select value={planFilter} onValueChange={v => setPlanFilter(v)}>
              <SelectTrigger className="h-8 text-xs w-40 bg-white" data-testid="tenants-plan-filter">
                <SelectValue placeholder="All Plans" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Plans</SelectItem>
                {plans.map(p => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}
              </SelectContent>
            </Select>
          )}
          <Button size="sm" variant="outline" onClick={load} data-testid="refresh-tenants-btn">
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button size="sm" onClick={() => setShowCreate(true)} data-testid="create-tenant-btn">
            <Plus className="h-4 w-4 mr-1" />
            New Partner Org
          </Button>
        </div>
      </div>

      {loading && <div className="p-4 text-slate-500 text-sm">Loading tenants…</div>}
      <div className="space-y-3">
        {tenants.map(tenant => (
          <div key={tenant.id} className="bg-white border border-slate-200 rounded-xl overflow-hidden" data-testid={`tenant-card-${tenant.code}`}>
            <div className="flex items-center gap-4 p-4">
              <div className="h-10 w-10 rounded-lg flex items-center justify-center" style={{ backgroundColor: "color-mix(in srgb, var(--aa-primary) 10%, transparent)" }}>
                <Building2 className="h-5 w-5" style={{ color: "var(--aa-primary)" }} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-slate-900">{tenant.store_name || tenant.name}</h3>
                  <Badge variant={tenant.status === "active" ? "default" : "secondary"} className="text-xs">
                    {tenant.status}
                  </Badge>
                  {tenant.code === "automate-accounts" && (
                    <Badge variant="outline" className="text-xs border-amber-300 text-amber-700">Platform Default</Badge>
                  )}
                </div>
                <p className="text-xs text-slate-400 font-mono mt-0.5">code: {tenant.code}</p>
              </div>
              <div className="flex items-center gap-1.5">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setShowLicense({ id: tenant.id, name: tenant.name })}
                  data-testid={`license-btn-${tenant.code}`}
                  className="text-xs"
                >
                  <ShieldCheck className="h-3.5 w-3.5 mr-1" />
                  License
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setShowCreateAdmin(tenant.id)}
                  data-testid={`add-admin-${tenant.code}`}
                  className="text-xs"
                >
                  <Users className="h-3.5 w-3.5 mr-1" />
                  Add Admin
                </Button>
                {/* More actions dropdown */}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button size="sm" variant="ghost" data-testid={`more-actions-${tenant.code}`}>
                      <MoreHorizontal className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-40">
                    <DropdownMenuItem
                      onClick={() => openAddressEdit(tenant)}
                      data-testid={`edit-address-${tenant.code}`}
                    >
                      <MapPin className="h-3.5 w-3.5 mr-2" /> Address
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => setShowNotes({ id: tenant.id, name: tenant.name })}
                      data-testid={`notes-btn-${tenant.code}`}
                    >
                      <StickyNote className="h-3.5 w-3.5 mr-2" /> Notes
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => openEditDetails(tenant)}
                      data-testid={`edit-details-btn-${tenant.code}`}
                    >
                      <Pencil className="h-3.5 w-3.5 mr-2" /> Edit Org Details
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => setAuditTenant({ id: tenant.id, name: tenant.name })}
                      data-testid={`logs-btn-${tenant.code}`}
                    >
                      <ScrollText className="h-3.5 w-3.5 mr-2" /> Audit Logs
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
                <Button
                  size="sm"
                  variant={tenant.status === "active" ? "outline" : "default"}
                  onClick={() => toggleStatus(tenant)}
                  disabled={tenant.code === "automate-accounts"}
                  data-testid={`toggle-tenant-${tenant.code}`}
                >
                  {tenant.status === "active" ? <PowerOff className="h-3.5 w-3.5" /> : <Power className="h-3.5 w-3.5" />}
                </Button>
                <Button size="sm" variant="ghost" onClick={() => toggleExpand(tenant.id)} data-testid={`expand-tenant-${tenant.code}`}>
                  {expandedTenant === tenant.id ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </Button>
              </div>
            </div>

            {expandedTenant === tenant.id && (
              <div className="border-t border-slate-100 p-4 bg-slate-50">
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Admin Users</p>
                {(tenantUsers[tenant.id] || []).filter(u => u.role !== "customer").length === 0 ? (
                  <p className="text-sm text-slate-400">No admin users yet. Click "Add Admin" to create one.</p>
                ) : (
                  <div className="space-y-2">
                    {(tenantUsers[tenant.id] || []).filter(u => u.role !== "customer").map(user => (
                      <div key={user.id} className="flex items-center gap-3 text-sm">
                        <div className="h-7 w-7 rounded-full bg-slate-200 flex items-center justify-center text-xs font-medium text-slate-600">
                          {user.full_name?.[0]?.toUpperCase() || "?"}
                        </div>
                        <div>
                          <span className="font-medium text-slate-700">{user.full_name}</span>
                          <span className="text-slate-400 ml-2">{user.email}</span>
                        </div>
                        <Badge variant="outline" className="text-xs ml-auto">{user.role}</Badge>
                        {/* Transfer super admin button — visible to platform admins, for non-super-admin users */}
                        {user.role !== "partner_super_admin" && (
                          <Button
                            size="sm" variant="ghost"
                            className="h-6 px-2 text-[10px] text-violet-600 hover:text-violet-700 hover:bg-violet-50"
                            onClick={async () => {
                              try {
                                await api.post(`/admin/tenants/${tenant.id}/transfer-super-admin`, { new_user_id: user.id });
                                toast.success(`${user.email} is now the partner super admin`);
                                // Reload users for this tenant
                                const r = await api.get(`/admin/tenants/${tenant.id}/users`);
                                setTenantUsers(prev => ({ ...prev, [tenant.id]: r.data.users || [] }));
                              } catch (e: any) {
                                toast.error(e.response?.data?.detail || "Failed to transfer super admin");
                              }
                            }}
                            data-testid={`transfer-super-admin-${user.id}`}
                          >
                            <ShieldCheck size={12} className="mr-1" />Make Super Admin
                          </Button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Create Tenant Dialog */}
      <Dialog open={showCreate} onOpenChange={open => { if (!open) handleCloseCreate(); }}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="create-tenant-dialog">
          <DialogHeader>
            <DialogTitle>New Partner Organization</DialogTitle>
          </DialogHeader>

          {generatedCode ? (
            <div className="py-4 space-y-5 text-center">
              <div className="h-12 w-12 rounded-full bg-green-50 flex items-center justify-center mx-auto">
                <ShieldCheck className="h-6 w-6 text-green-500" />
              </div>
              <div>
                <p className="font-semibold text-slate-900">Organization created!</p>
                <p className="text-xs text-slate-400 mt-1">Share the partner code below with the new partner so they can sign in.</p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-2">
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">Partner Code</p>
                <div className="flex items-center gap-2">
                  <code className="flex-1 text-xl font-bold tracking-tight text-slate-900 bg-white border border-slate-200 rounded-lg px-3 py-2 font-mono text-center" data-testid="admin-generated-partner-code">
                    {generatedCode}
                  </code>
                  <button
                    onClick={() => { navigator.clipboard.writeText(generatedCode); setCodeCopied(true); setTimeout(() => setCodeCopied(false), 2000); }}
                    className="h-10 w-10 shrink-0 rounded-lg border border-slate-200 bg-white flex items-center justify-center text-slate-500 hover:border-slate-400 transition-colors"
                    data-testid="admin-copy-partner-code"
                    title="Copy partner code"
                  >
                    {codeCopied ? <Check className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
                  </button>
                </div>
              </div>
              <Button className="w-full" onClick={handleCloseCreate} data-testid="close-create-tenant-success">Done</Button>
            </div>
          ) : (
            <form onSubmit={handleCreate} className="space-y-4 mt-2">
              <PartnerOrgForm
                value={newPartner}
                onChange={setNewPartner}
                currencies={supportedCurrencies}
                schema={ws.partner_signup_form_schema}
                testIdPrefix="new-partner"
              />
              <DialogFooter>
                <Button type="button" variant="outline" onClick={handleCloseCreate}>Cancel</Button>
                <Button type="submit" disabled={creating} data-testid="confirm-create-tenant">
                  {creating ? "Creating…" : "Create Organization"}
                </Button>
              </DialogFooter>
            </form>
          )}
        </DialogContent>
      </Dialog>

      {/* Create Admin Dialog */}
      <Dialog open={!!showCreateAdmin} onOpenChange={() => setShowCreateAdmin(null)}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="create-admin-dialog">
          <DialogHeader>
            <DialogTitle>Add Admin User</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreateAdmin} className="space-y-3 mt-2">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <RequiredLabel className="text-slate-500 font-normal">Full Name</RequiredLabel>
                <Input value={newAdmin.full_name} onChange={e => setNewAdmin(p => ({ ...p, full_name: e.target.value }))} required data-testid="new-admin-name" />
              </div>
              <div className="space-y-1">
                <RequiredLabel className="text-slate-500 font-normal">Email</RequiredLabel>
                <Input type="email" value={newAdmin.email} onChange={e => setNewAdmin(p => ({ ...p, email: e.target.value }))} required data-testid="new-admin-email" />
              </div>
              <div className="space-y-1 col-span-2">
                <RequiredLabel className="text-slate-500 font-normal">Password</RequiredLabel>
                <Input type="password" value={newAdmin.password} onChange={e => setNewAdmin(p => ({ ...p, password: e.target.value }))} required data-testid="new-admin-password" />
              </div>
              <div className="space-y-1 col-span-2">
                <label className="text-xs text-slate-500">Role</label>
                <Select value={newAdmin.role} onValueChange={v => setNewAdmin(p => ({ ...p, role: v }))}>
                  <SelectTrigger className="w-full bg-white" data-testid="new-admin-role"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="partner_admin">Partner Admin</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Preset quick-fill */}
            {presetRoles.length > 0 && (
              <div className="space-y-1 pt-2 border-t border-slate-100">
                <label className="text-xs text-slate-500 flex items-center gap-1">
                  Quick Preset <FieldTip tip="Selecting a preset auto-fills the module permissions below. You can still adjust them manually." />
                </label>
                <Select onValueChange={applyPresetToAdmin}>
                  <SelectTrigger data-testid="new-admin-preset"><SelectValue placeholder="Apply a preset (optional)…" /></SelectTrigger>
                  <SelectContent>
                    {presetRoles.map((role: any) => (
                      <SelectItem key={role.key} value={role.key}>{role.name} — {role.description}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {/* Per-module permissions */}
            {modules.length > 0 && (
              <div className="border border-slate-200 rounded-lg overflow-hidden">
                <div className="bg-slate-50 px-3 py-2 border-b border-slate-200">
                  <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Module Permissions</p>
                </div>
                <div className="max-h-48 overflow-y-auto divide-y divide-slate-100">
                  {modules.map((mod: any) => (
                    <div key={mod.key} className="flex items-center justify-between px-3 py-2 hover:bg-slate-50">
                      <div>
                        <p className="text-xs font-medium text-slate-700">{mod.name}</p>
                        <p className="text-[10px] text-slate-400">{mod.description}</p>
                      </div>
                      <Select
                        value={newAdminPerms[mod.key] || "none"}
                        onValueChange={v => setNewAdminPerms(prev => ({ ...prev, [mod.key]: v as "read" | "write" | "none" }))}
                      >
                        <SelectTrigger className="w-36 h-7 text-xs" data-testid={`admin-perm-${mod.key}`}><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none"><span className="text-slate-400">No Access</span></SelectItem>
                          <SelectItem value="read"><span className="flex items-center gap-1.5"><Eye size={11} className="text-amber-500" />Read</span></SelectItem>
                          <SelectItem value="write"><span className="flex items-center gap-1.5"><ShieldCheck size={11} className="text-emerald-500" />Read &amp; Write</span></SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <Button type="submit" disabled={creatingAdmin} className="w-full" data-testid="confirm-create-admin">
              {creatingAdmin ? "Creating…" : "Add Admin User"}
            </Button>
          </form>
        </DialogContent>
      </Dialog>

      {/* Edit Partner Address Dialog */}
      <Dialog open={!!showAddressEdit} onOpenChange={open => !open && setShowAddressEdit(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><MapPin size={16} /> Edit Organization Address</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2" data-testid="tenant-address-form">
            <Input placeholder="Line 1 *" value={addrForm.line1 || ""} onChange={e => setAddrForm(p => ({...p, line1: e.target.value}))} data-testid="tenant-addr-line1" />
            <Input placeholder="Line 2 (optional)" value={addrForm.line2 || ""} onChange={e => setAddrForm(p => ({...p, line2: e.target.value}))} data-testid="tenant-addr-line2" />
            <div className="grid grid-cols-2 gap-2">
              <Input placeholder="City *" value={addrForm.city || ""} onChange={e => setAddrForm(p => ({...p, city: e.target.value}))} data-testid="tenant-addr-city" />
              <Input placeholder="Postal Code *" value={addrForm.postal || ""} onChange={e => setAddrForm(p => ({...p, postal: e.target.value}))} data-testid="tenant-addr-postal" />
            </div>
            <Select value={addrForm.country || ""} onValueChange={v => { setAddrForm(p => ({...p, country: v, region: ""})); }}>
              <SelectTrigger data-testid="tenant-addr-country"><SelectValue placeholder="Country *" /></SelectTrigger>
              <SelectContent>{countries.map(c => <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>)}</SelectContent>
            </Select>
            {addrProvinces.length > 0 ? (
              <Select value={addrForm.region || ""} onValueChange={v => setAddrForm(p => ({...p, region: v}))}>
                <SelectTrigger data-testid="tenant-addr-region-select"><SelectValue placeholder="Province / State *" /></SelectTrigger>
                <SelectContent>{addrProvinces.map(p => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}</SelectContent>
              </Select>
            ) : (
              <Input placeholder="State / Province *" value={addrForm.region || ""} onChange={e => setAddrForm(p => ({...p, region: e.target.value}))} data-testid="tenant-addr-region-input" />
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAddressEdit(null)}>Cancel</Button>
            <Button onClick={saveAddress} disabled={addrSaving} data-testid="tenant-addr-save-btn">
              {addrSaving ? "Saving…" : "Save Address"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* License Modal */}
      {showLicense && (
        <TenantLicenseModal
          tenantId={showLicense.id}
          tenantName={showLicense.name}
          onClose={() => setShowLicense(null)}
        />
      )}

      {/* Notes Modal */}
      {showNotes && (
        <TenantNotesModal
          tenantId={showNotes.id}
          tenantName={showNotes.name}
          onClose={() => setShowNotes(null)}
        />
      )}

      {/* Edit Org Details Dialog */}
      <Dialog open={!!showEditDetails} onOpenChange={open => !open && setShowEditDetails(null)}>
        <DialogContent className="max-w-md" data-testid="edit-org-details-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><Pencil size={16} /> Edit Org Details — {showEditDetails?.name}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Organization Name</label>
              <Input value={editDetailsForm.name} onChange={e => setEditDetailsForm(p => ({ ...p, name: e.target.value }))} data-testid="edit-org-name" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEditDetails(null)}>Cancel</Button>
            <Button onClick={handleSaveDetails} disabled={savingDetails} data-testid="save-org-details-btn">
              {savingDetails ? "Saving…" : "Save Details"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Audit Logs dialog for a Partner Org */}
      {auditTenant && (
        <AuditLogDialog
          open={!!auditTenant}
          onOpenChange={open => { if (!open) setAuditTenant(null); }}
          title={`Audit Logs — ${auditTenant.name}`}
          logsUrl={`/admin/audit-logs?entity_type=tenant&entity_id=${auditTenant.id}`}
        />
      )}
    </div>
  </div>
  );
}
