import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { RequiredLabel } from "@/components/shared/RequiredLabel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { AdminPageHeader } from "./shared/AdminPageHeader";
import { AdminPagination } from "./shared/AdminPagination";
import { AuditLogDialog } from "@/components/AuditLogDialog";
import { useAuth } from "@/contexts/AuthContext";
import { Plus, ShieldCheck, Eye, Pencil, PowerOff, Power, ScrollText, Lock, Users, Zap, ChevronsUpDown, Check, AlertTriangle } from "lucide-react";
import { ColHeader } from "@/components/shared/ColHeader";
import { FieldTip } from "./shared/FieldTip";
import { cn } from "@/lib/utils";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ModuleInfo { key: string; name: string; description: string; }
interface PresetRole { key: string; name: string; description: string; module_permissions: Record<string, "read" | "write">; }
type ModulePerm = Record<string, "read" | "write" | "none">;

const PARTNER_ROLES = new Set(["partner_super_admin", "partner_admin"]);

// ── Module Permission Editor ───────────────────────────────────────────────────

function ModulePermEditor({ modules, value, onChange }: { modules: ModuleInfo[]; value: ModulePerm; onChange: (mp: ModulePerm) => void; }) {
  if (!modules.length) return null;
  return (
    <div className="border border-slate-200 rounded-lg overflow-hidden">
      <div className="bg-slate-50 px-3 py-2 border-b border-slate-200">
        <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Module Permissions</p>
      </div>
      <div className="max-h-56 overflow-y-auto divide-y divide-slate-100">
        {modules.map(mod => (
          <div key={mod.key} className="flex items-center justify-between px-3 py-2 hover:bg-slate-50">
            <div>
              <p className="text-xs font-medium text-slate-700">{mod.name}</p>
              <p className="text-[10px] text-slate-400">{mod.description}</p>
            </div>
            <Select value={value[mod.key] || "none"} onValueChange={v => onChange({ ...value, [mod.key]: v as "read" | "write" | "none" })}>
              <SelectTrigger className="w-36 h-7 text-xs" data-testid={`perm-${mod.key}`}><SelectValue /></SelectTrigger>
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
  );
}

// ── Searchable Org Picker ──────────────────────────────────────────────────────

function OrgPicker({ value, onChange, partners }: { value: string; onChange: (id: string) => void; partners: { id: string; name: string }[] }) {
  const [open, setOpen] = useState(false);
  const selected = partners.find(p => p.id === value);
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" role="combobox" className="w-full justify-between h-9 text-sm font-normal" data-testid="new-user-org-picker">
          {selected ? selected.name : "Select partner org…"}
          <ChevronsUpDown className="ml-2 h-3 w-3 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-72 p-0" align="start">
        <Command>
          <CommandInput placeholder="Search org…" className="h-9" />
          <CommandList>
            <CommandEmpty>No org found.</CommandEmpty>
            <CommandGroup>
              {partners.map(p => (
                <CommandItem key={p.id} value={p.name} onSelect={() => { onChange(p.id); setOpen(false); }}>
                  <Check className={cn("mr-2 h-3 w-3", value === p.id ? "opacity-100" : "opacity-0")} />
                  {p.name}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function toModulePerm(mp: Record<string, string> | undefined): ModulePerm {
  const out: ModulePerm = {};
  if (!mp) return out;
  for (const [k, v] of Object.entries(mp)) {
    if (v === "read" || v === "write") out[k] = v;
  }
  return out;
}

function toApiPerm(mp: ModulePerm): Record<string, "read" | "write"> {
  return Object.fromEntries(Object.entries(mp).filter(([, v]) => v !== "none")) as Record<string, "read" | "write">;
}

function roleLabel(role: string): string {
  const map: Record<string, string> = {
    platform_super_admin: "Platform Super Admin",
    platform_admin: "Platform Admin",
    partner_super_admin: "Partner Super Admin",
    partner_admin: "Partner Admin",
    admin: "Admin",
    super_admin: "Super Admin",
  };
  return map[role] ?? role;
}

function roleBadgeColor(role: string) {
  if (role === "platform_super_admin") return "bg-violet-100 text-violet-700 border-violet-200";
  if (role === "platform_admin") return "bg-blue-100 text-blue-700 border-blue-200";
  if (role === "partner_super_admin") return "bg-emerald-100 text-emerald-700 border-emerald-200";
  if (role === "partner_admin") return "bg-amber-100 text-amber-700 border-amber-200";
  return "bg-slate-100 text-slate-600 border-slate-200";
}

// ── Presets Sub-tab ─────────────────────────────────────────────────────────

function PresetsSubTab({ modules, presetRoles }: { modules: ModuleInfo[]; presetRoles: PresetRole[] }) {
  return (
    <div className="space-y-4" data-testid="presets-subtab">
      <div>
        <h2 className="text-base font-semibold text-slate-900">Quick Presets</h2>
        <p className="text-sm text-slate-500 mt-0.5">
          Built-in permission templates. Apply these when creating or editing a user via the "Quick Preset" dropdown.
        </p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {presetRoles.map(preset => {
          const entries = Object.entries(preset.module_permissions || {});
          const writeCount = entries.filter(([, v]) => v === "write").length;
          const readCount = entries.filter(([, v]) => v === "read").length;
          return (
            <div key={preset.key} className="rounded-xl border border-slate-200 bg-white p-5 space-y-3" data-testid={`preset-card-${preset.key}`}>
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-slate-100"><Zap size={14} className="text-slate-500" /></div>
                <div>
                  <h4 className="text-sm font-semibold text-slate-900">{preset.name}</h4>
                  <span className="text-[10px] text-slate-400">Built-in preset</span>
                </div>
              </div>
              {preset.description && <p className="text-xs text-slate-500">{preset.description}</p>}
              <div className="flex flex-wrap gap-1.5">
                {entries.map(([key, val]) => {
                  const mod = modules.find(m => m.key === key);
                  return (
                    <span key={key} className={`inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded border font-medium ${val === "write" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-amber-50 text-amber-700 border-amber-200"}`}>
                      {val === "write" ? <ShieldCheck size={9} /> : <Eye size={9} />}
                      {mod?.name || key}
                    </span>
                  );
                })}
              </div>
              <p className="text-[10px] text-slate-400 pt-1 border-t border-slate-100">{writeCount} read &amp; write · {readCount} read only</p>
            </div>
          );
        })}
      </div>
      {presetRoles.length === 0 && <p className="text-sm text-slate-400 italic">No presets available.</p>}
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

export function UsersTab() {
  const { user: authUser } = useAuth();
  const isPlatformSuperAdmin = authUser?.role === "platform_super_admin";
  const isPartnerSuperAdmin = authUser?.role === "partner_super_admin";
  const isSuperAdmin = isPlatformSuperAdmin || isPartnerSuperAdmin || authUser?.role === "super_admin";
  const isPlatformAdmin = authUser?.role === "platform_admin" || authUser?.role === "platform_super_admin";

  const [adminUsers, setAdminUsers] = useState<any[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const PER_PAGE = 20;
  const [searchFilter, setSearchFilter] = useState("");
  const [partnerFilter, setPartnerFilter] = useState("all");
  const [partners, setPartners] = useState<{ id: string; name: string }[]>([]);
  const [colSort, setColSort] = useState<{ col: string; dir: "asc" | "desc" } | null>(null);
  const [colFilters, setColFilters] = useState({
    names: [] as string[], roles: [] as string[], orgNames: [] as string[], statuses: [] as string[],
    partnerCodes: [] as string[], modules: [] as string[],
  });
  const setCF = (key: keyof typeof colFilters, val: any) => setColFilters(f => ({ ...f, [key]: val }));

  const displayUsers = useMemo(() => {
    let r = [...adminUsers];
    if (colFilters.names.length) r = r.filter(u => colFilters.names.includes(u.full_name || u.email));
    if (colFilters.roles.length) r = r.filter(u => colFilters.roles.includes(u.role));
    if (colFilters.orgNames.length) r = r.filter(u => colFilters.orgNames.includes(u.tenant_name || u.org_name || u.partner_name || ""));
    if (colFilters.statuses.length) r = r.filter(u => colFilters.statuses.includes(u.is_active !== false ? "active" : "inactive"));
    if (colFilters.partnerCodes.length) r = r.filter(u => colFilters.partnerCodes.includes(u.tenant_code || ""));
    if (colFilters.modules.length) r = r.filter(u => {
      const mp = u.module_permissions || {};
      return colFilters.modules.some(mod => mp[mod] && mp[mod] !== "none");
    });
    if (colSort) {
      r.sort((a, b) => {
        let av: any = "", bv: any = "";
        if (colSort.col === "name") { av = (a.full_name || a.email || "").toLowerCase(); bv = (b.full_name || b.email || "").toLowerCase(); }
        else if (colSort.col === "role") { av = a.role; bv = b.role; }
        else if (colSort.col === "partner") { av = a.org_name || ""; bv = b.org_name || ""; }
        else if (colSort.col === "partnerCode") { av = a.tenant_code || ""; bv = b.tenant_code || ""; }
        else if (colSort.col === "modules") { av = Object.keys(a.module_permissions || {}).filter(k => a.module_permissions[k] !== "none").length; bv = Object.keys(b.module_permissions || {}).filter(k => b.module_permissions[k] !== "none").length; }
        else if (colSort.col === "status") { av = a.is_active ? 1 : 0; bv = b.is_active ? 1 : 0; }
        if (av < bv) return colSort.dir === "asc" ? -1 : 1;
        if (av > bv) return colSort.dir === "asc" ? 1 : -1;
        return 0;
      });
    }
    return r;
  }, [adminUsers, colFilters, colSort]);
  const nameOpts = useMemo(() => Array.from(new Set(adminUsers.map(u => u.full_name || u.email).filter((v): v is string => !!v))).sort().map(v => [v, v] as [string, string]), [adminUsers]);
  const roleOpts = useMemo(() => Array.from(new Set(adminUsers.map(u => u.role).filter((v): v is string => !!v))).sort().map(v => [v, v] as [string, string]), [adminUsers]);
  const orgOpts = useMemo(() => Array.from(new Set(adminUsers.map(u => u.tenant_name || u.org_name || u.partner_name || "").filter((v): v is string => !!v))).sort().map(v => [v, v] as [string, string]), [adminUsers]);
  const partnerCodeOpts = useMemo(() => Array.from(new Set(adminUsers.map(u => u.tenant_code).filter((v): v is string => !!v))).sort().map(v => [v, v] as [string, string]), [adminUsers]);

  // All modules and partner module keys (for role-scoped filtering)
  const [allModules, setAllModules] = useState<ModuleInfo[]>([]);
  const [partnerModuleKeys, setPartnerModuleKeys] = useState<string[]>([]);
  const [presetRoles, setPresetRoles] = useState<PresetRole[]>([]);

  const moduleOpts = useMemo(() => Array.from(new Set(adminUsers.flatMap(u => Object.keys(u.module_permissions || {}).filter(k => u.module_permissions[k] !== "none")))).sort().map(k => {
    const mod = allModules.find(m => m.key === k);
    return [k, mod?.name || k] as [string, string];
  }), [adminUsers, allModules]);

  // Create dialog
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [newUser, setNewUser] = useState({ email: "", full_name: "", password: "", role: "", target_tenant_id: "" });
  const [newUserPerms, setNewUserPerms] = useState<ModulePerm>({});
  const [orgHasSuperAdmin, setOrgHasSuperAdmin] = useState(false);

  // Edit dialog
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [editUser, setEditUser] = useState<any>(null);
  const [editForm, setEditForm] = useState({ full_name: "", role: "" });
  const [editPerms, setEditPerms] = useState<ModulePerm>({});

  // Misc
  const [logsUrl, setLogsUrl] = useState("");
  const [deactivateUserId, setDeactivateUserId] = useState<string | null>(null);

  // Roles the caller can create
  const creatableRoles = isPlatformSuperAdmin
    ? [
        { value: "platform_admin", label: "Platform Admin" },
        { value: "partner_super_admin", label: "Partner Super Admin" },
        { value: "partner_admin", label: "Partner Admin" },
      ]
    : isPartnerSuperAdmin
    ? [
        { value: "partner_admin", label: "Partner Admin" },
      ]
    : [];

  // Modules to show based on selected role
  const modulesForRole = (role: string): ModuleInfo[] => {
    if (!role || role === "platform_admin") return allModules;
    if (PARTNER_ROLES.has(role)) return allModules.filter(m => partnerModuleKeys.includes(m.key));
    return allModules;
  };

  const load = useCallback(async (p = 1) => {
    try {
      const params: any = { page: p, per_page: PER_PAGE };
      if (searchFilter) params.search = searchFilter;
      if (partnerFilter !== "all") params.partner_id = partnerFilter;
      const r = await api.get("/admin/users", { params });
      setAdminUsers(r.data.users || []);
      setTotalPages(r.data.total_pages || 1);
      setTotal(r.data.total || 0);
      setPage(p);
    } catch {
      toast.error("Failed to load users");
    }
  }, [searchFilter, partnerFilter]);

  const loadMeta = useCallback(async () => {
    try {
      const r = await api.get("/admin/permissions/modules");
      setAllModules(r.data.modules || []);
      setPartnerModuleKeys(r.data.partner_module_keys || []);
      setPresetRoles(r.data.preset_roles || []);
    } catch { /* ignore */ }
    if (isPlatformAdmin) {
      try {
        const r = await api.get("/admin/tenants");
        setPartners((r.data.tenants || []).map((t: any) => ({ id: t.id, name: t.name })));
      } catch { /* ignore */ }
    }
  }, [isPlatformAdmin]);

  useEffect(() => { load(); loadMeta(); }, []); // eslint-disable-line
  useEffect(() => { const t = setTimeout(() => load(1), 300); return () => clearTimeout(t); }, [searchFilter, partnerFilter]); // eslint-disable-line

  // Check if selected org already has a super admin
  const checkOrgSuperAdmin = async (orgId: string) => {
    if (!orgId) { setOrgHasSuperAdmin(false); return; }
    try {
      const r = await api.get(`/admin/tenants/${orgId}/users`);
      const hasSA = (r.data.users || []).some((u: any) => u.role === "partner_super_admin" && u.is_active);
      setOrgHasSuperAdmin(hasSA);
    } catch { setOrgHasSuperAdmin(false); }
  };

  // ── Create ──────────────────────────────────────────────────────────────────

  const [saving, setSaving] = useState(false);

  const handleCreate = async () => {
    if (!newUser.email || !newUser.password || !newUser.role || !newUser.full_name.trim()) { toast.error("Email, full name, password and role are required"); return; }
    if (PARTNER_ROLES.has(newUser.role) && isPlatformSuperAdmin && !newUser.target_tenant_id) {
      toast.error("Please select a partner org for this user"); return;
    }
    setSaving(true);
    try {
      await api.post("/admin/users", {
        email: newUser.email,
        full_name: newUser.full_name,
        password: newUser.password,
        role: newUser.role,
        target_tenant_id: newUser.target_tenant_id || undefined,
        module_permissions: toApiPerm(newUserPerms),
      });
      toast.success(`User ${newUser.email} created`);
      setShowCreateDialog(false);
      setNewUser({ email: "", full_name: "", password: "", role: "", target_tenant_id: "" });
      setNewUserPerms({});
      setOrgHasSuperAdmin(false);
      load(1);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to create user");
    } finally { setSaving(false); }
  };

  const applyPreset = (presetKey: string, setPerms: (mp: ModulePerm) => void) => {
    const preset = presetRoles.find(r => r.key === presetKey);
    if (preset?.module_permissions) setPerms(toModulePerm(preset.module_permissions));
  };

  // ── Edit ────────────────────────────────────────────────────────────────────

  const openEdit = (u: any) => {
    setEditUser(u);
    setEditForm({ full_name: u.full_name || "", role: u.role || "" });
    setEditPerms(toModulePerm(u.module_permissions));
    setShowEditDialog(true);
  };

  const handleEdit = async () => {
    if (!editUser) return;
    if (!editForm.full_name.trim()) { toast.error("Full name is required"); return; }
    setSaving(true);
    try {
      const body: any = { full_name: editForm.full_name };
      if (editForm.role && editForm.role !== editUser.role) body.role = editForm.role;
      if (!["platform_super_admin", "partner_super_admin"].includes(editUser.role) && editForm.role !== "partner_super_admin") {
        body.module_permissions = toApiPerm(editPerms);
      }
      await api.put(`/admin/users/${editUser.id}`, body);
      toast.success("User updated");
      setShowEditDialog(false);
      setEditUser(null);
      load(page);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to update user");
    } finally { setSaving(false); }
  };

  // ── Deactivate ───────────────────────────────────────────────────────────────

  const handleDeactivate = async (userId: string) => {
    try {
      await api.patch(`/admin/users/${userId}/active`, null, { params: { active: false } });
      toast.success("User deactivated"); load(page);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to deactivate user");
    } finally { setDeactivateUserId(null); }
  };

  const handleReactivate = async (userId: string) => {
    try {
      await api.patch(`/admin/users/${userId}/active`, null, { params: { active: true } });
      toast.success("User reactivated"); load(page);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to reactivate user");
    }
  };

  const isPlatformSuperAdminUser = (u: any) => u.role === "platform_super_admin";
  const isSuperAdminUser = (u: any) => u.role === "platform_super_admin" || u.role === "partner_super_admin";

  // Edit role options (excludes super admin roles + filters based on caller)
  const editableRoles = (currentRole: string) => {
    const base = isPlatformSuperAdmin
      ? ["platform_admin", "partner_super_admin", "partner_admin"]
      : isPartnerSuperAdmin
      ? ["partner_admin"]
      : [];
    return base.filter(r => r !== "platform_super_admin");
  };

  return (
    <div data-testid="users-tab">
      <Tabs defaultValue="list">
        <TabsList className="mb-4">
          <TabsTrigger value="list" data-testid="users-subtab-list"><Users size={13} className="mr-1.5" />Users</TabsTrigger>
          <TabsTrigger value="presets" data-testid="users-subtab-presets"><Zap size={13} className="mr-1.5" />Quick Presets</TabsTrigger>
        </TabsList>

        <TabsContent value="presets">
          <PresetsSubTab modules={allModules} presetRoles={presetRoles} />
        </TabsContent>

        <TabsContent value="list">
          <AdminPageHeader
            title="Admin Users"
            subtitle={`${total} admin user${total !== 1 ? "s" : ""}`}
            actions={isSuperAdmin ? (
              <Button size="sm" onClick={() => setShowCreateDialog(true)} data-testid="create-user-btn">
                <Plus size={14} className="mr-1.5" />Add User
              </Button>
            ) : undefined}
          />

          {/* Filters removed — use column headers below */}

          {/* Table */}
          <div className="rounded-lg border border-slate-200 overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="bg-slate-50">
                  <ColHeader label="Name / Email" colKey="name" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={colFilters.names} onFilter={v => setCF("names", v)} onClearFilter={() => setCF("names", [])} statusOptions={nameOpts} />
                  <ColHeader label="Role" colKey="role" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={colFilters.roles} onFilter={v => setCF("roles", v)} onClearFilter={() => setCF("roles", [])} statusOptions={roleOpts} />
                  {isPlatformAdmin && <ColHeader label="Partner Org" colKey="partner" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={colFilters.orgNames} onFilter={v => setCF("orgNames", v)} onClearFilter={() => setCF("orgNames", [])} statusOptions={orgOpts} />}
                  {isPlatformAdmin && <ColHeader label="Partner Code" colKey="partnerCode" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={colFilters.partnerCodes} onFilter={v => setCF("partnerCodes", v)} onClearFilter={() => setCF("partnerCodes", [])} statusOptions={partnerCodeOpts} />}
                  <ColHeader label="Modules" colKey="modules" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={colFilters.modules} onFilter={v => setCF("modules", v)} onClearFilter={() => setCF("modules", [])} statusOptions={moduleOpts} />
                  <ColHeader label="Status" colKey="status" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={colFilters.statuses} onFilter={v => setCF("statuses", v)} onClearFilter={() => setCF("statuses", [])} statusOptions={[["active","Active"],["inactive","Inactive"]]} />
                  <th className="px-4 py-3 text-right text-xs font-medium uppercase text-slate-500">Actions</th>
                </TableRow>
              </TableHeader>
              <TableBody>
                {displayUsers.map(u => {
                  const isImmutable = isPlatformSuperAdminUser(u);
                  const isSA = isSuperAdminUser(u);
                  const mpKeys = Object.keys(u.module_permissions || {}).filter(k => u.module_permissions[k] !== "none");
                  return (
                    <TableRow key={u.id} data-testid={`user-row-${u.id}`} className={!u.is_active ? "opacity-50" : ""}>
                      <TableCell>
                        <p className="text-sm font-medium">{u.full_name || "—"}</p>
                        <p className="text-xs text-slate-400">{u.email}</p>
                      </TableCell>
                      <TableCell>
                        <span className={`inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full border ${roleBadgeColor(u.role)}`}>
                          {isImmutable && <Lock size={9} />}
                          {roleLabel(u.role)}
                        </span>
                      </TableCell>
                      {isPlatformAdmin && (
                        <TableCell>
                          <span className="text-xs text-slate-500">{u.tenant_name || (u.tenant_id === "automate-accounts" || !u.tenant_id ? "Platform" : u.tenant_id?.slice(0, 8))}</span>
                        </TableCell>
                      )}
                      {isPlatformAdmin && (
                        <TableCell>
                          {u.tenant_code ? (
                            <code className="text-xs bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded">{u.tenant_code}</code>
                          ) : (
                            <span className="text-xs text-slate-300">—</span>
                          )}
                        </TableCell>
                      )}
                      <TableCell>
                        {isSA ? (
                          <span className="text-xs text-slate-400 italic">Full access</span>
                        ) : mpKeys.length === 0 ? (
                          <span className="text-xs text-slate-400 italic">No access</span>
                        ) : (
                          <span className="text-xs text-slate-500">{mpKeys.length} module{mpKeys.length !== 1 ? "s" : ""}</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <span className={`inline-block text-[10px] font-medium px-2 py-0.5 rounded-full ${u.is_active ? "bg-emerald-50 text-emerald-600" : "bg-red-50 text-red-600"}`}>
                          {u.is_active ? "Active" : "Inactive"}
                        </span>
                      </TableCell>
                      <TableCell className="text-right">
                        {isImmutable ? (
                          <span className="text-xs text-slate-400 italic flex items-center justify-end gap-1"><Lock size={11} /> Protected</span>
                        ) : isSuperAdmin ? (
                          <div className="flex gap-1.5 justify-end">
                            <Button size="sm" variant="ghost" className="h-7 px-2" onClick={() => openEdit(u)} data-testid={`edit-user-${u.id}`}><Pencil size={13} /></Button>
                            <Button size="sm" variant="ghost" className={`h-7 px-2 ${u.is_active ? "text-red-500 hover:text-red-600" : "text-emerald-500 hover:text-emerald-600"}`}
                              onClick={() => u.is_active ? setDeactivateUserId(u.id) : handleReactivate(u.id)} data-testid={`toggle-active-${u.id}`}>
                              {u.is_active ? <PowerOff size={13} /> : <Power size={13} />}
                            </Button>
                            <Button size="sm" variant="ghost" className="h-7 px-2" onClick={() => setLogsUrl(`/admin/audit-logs?entity_type=user&entity_id=${u.id}`)} data-testid={`logs-user-${u.id}`}><ScrollText size={13} /></Button>
                          </div>
                        ) : null}
                      </TableCell>
                    </TableRow>
                  );
                })}
                {adminUsers.length === 0 && (
                  <TableRow><TableCell colSpan={isPlatformAdmin ? 6 : 5} className="text-center text-sm text-slate-400 py-8">No admin users found</TableCell></TableRow>
                )}
              </TableBody>
            </Table>
          </div>

          <AdminPagination page={page} totalPages={totalPages} total={total} perPage={PER_PAGE} onPage={p => load(p)} />
        </TabsContent>
      </Tabs>

      {/* ── Create Dialog ─────────────────────────────────────────────────── */}
      <Dialog open={showCreateDialog} onOpenChange={open => { setShowCreateDialog(open); if (!open) { setNewUser({ email: "", full_name: "", password: "", role: "", target_tenant_id: "" }); setNewUserPerms({}); setOrgHasSuperAdmin(false); } }}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="create-user-dialog">
          <DialogHeader><DialogTitle>Add Admin User</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <RequiredLabel className="text-slate-500 font-normal">Full Name</RequiredLabel>
                <Input value={newUser.full_name} onChange={e => setNewUser(p => ({ ...p, full_name: e.target.value }))} placeholder="Jane Smith" data-testid="new-user-name" />
              </div>
              <div className="space-y-1">
                <RequiredLabel className="text-slate-500 font-normal">Role</RequiredLabel>
                <Select value={newUser.role} onValueChange={v => { setNewUser(p => ({ ...p, role: v, target_tenant_id: "" })); setNewUserPerms({}); setOrgHasSuperAdmin(false); }}>
                  <SelectTrigger data-testid="new-user-role"><SelectValue placeholder="Select role…" /></SelectTrigger>
                  <SelectContent>
                    {creatableRoles.map(r => <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>)}
                  </SelectContent>
                </Select>
                {newUser.role === "platform_super_admin" && (
                  <p className="text-[10px] text-amber-600 flex items-center gap-1 mt-1"><AlertTriangle size={10} />Only 1 platform super admin allowed. Cannot create another.</p>
                )}
              </div>
            </div>

            {/* Partner org picker — only for partner roles created by platform admin */}
            {PARTNER_ROLES.has(newUser.role) && isPlatformSuperAdmin && (
              <div className="space-y-1">
                <RequiredLabel className="text-slate-500 font-normal">Partner Org</RequiredLabel>
                <OrgPicker
                  value={newUser.target_tenant_id}
                  onChange={id => { setNewUser(p => ({ ...p, target_tenant_id: id })); checkOrgSuperAdmin(id); }}
                  partners={partners}
                />
                {orgHasSuperAdmin && newUser.role === "partner_super_admin" && (
                  <div className="flex items-start gap-2 p-2 rounded-lg bg-amber-50 border border-amber-200 mt-1">
                    <AlertTriangle size={13} className="text-amber-600 mt-0.5 shrink-0" />
                    <p className="text-[11px] text-amber-700">
                      This org already has a partner super admin. Create as <strong>Partner Admin</strong> and use <strong>Transfer Super Admin</strong> in Partner Orgs to promote them.
                    </p>
                  </div>
                )}
              </div>
            )}

            <div className="space-y-1">
              <RequiredLabel className="text-slate-500 font-normal">Email</RequiredLabel>
              <Input type="email" value={newUser.email} onChange={e => setNewUser(p => ({ ...p, email: e.target.value }))} placeholder="jane@company.com" data-testid="new-user-email" />
            </div>
            <div className="space-y-1">
              <RequiredLabel className="text-slate-500 font-normal">Temporary Password</RequiredLabel>
              <Input type="password" value={newUser.password} onChange={e => setNewUser(p => ({ ...p, password: e.target.value }))} placeholder="Min 10 chars, upper, lower, digit, symbol" data-testid="new-user-password" />
            </div>

            {/* Preset quick-fill — not for super admin roles */}
            {presetRoles.length > 0 && !["partner_super_admin", "platform_super_admin"].includes(newUser.role) && (
              <div className="space-y-1">
                <label className="text-xs text-slate-500 flex items-center gap-1">Quick Preset <FieldTip tip="Auto-fills module permissions below." /></label>
                <Select onValueChange={v => applyPreset(v, setNewUserPerms)}>
                  <SelectTrigger data-testid="new-user-preset"><SelectValue placeholder="Apply a preset (optional)…" /></SelectTrigger>
                  <SelectContent>
                    {presetRoles.map(r => <SelectItem key={r.key} value={r.key}>{r.name} — {r.description}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            )}

            {/* Per-module permissions — scoped to selected role; hidden for super admin */}
            {newUser.role && !["partner_super_admin", "platform_super_admin"].includes(newUser.role) && (
              <ModulePermEditor modules={modulesForRole(newUser.role)} value={newUserPerms} onChange={setNewUserPerms} />
            )}
            {newUser.role === "partner_super_admin" && (
              <div className="flex items-center gap-2 p-3 rounded-lg bg-emerald-50 border border-emerald-200">
                <ShieldCheck size={14} className="text-emerald-600" />
                <p className="text-xs text-emerald-700">Partner super admin has full access to all partner modules — no module restrictions needed.</p>
              </div>
            )}

            <Button onClick={handleCreate} disabled={saving} className="w-full" data-testid="create-user-submit">{saving ? "Creating…" : "Create User"}</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── Edit Dialog ───────────────────────────────────────────────────── */}
      <Dialog open={showEditDialog} onOpenChange={open => { setShowEditDialog(open); if (!open) setEditUser(null); }}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="admin-edit-user-dialog">
          <DialogHeader><DialogTitle>Edit User: {editUser?.email}</DialogTitle></DialogHeader>
          {editUser && (
            <div className="space-y-3">
              <div className="space-y-1">
                <RequiredLabel className="text-slate-500 font-normal">Full Name</RequiredLabel>
                <Input value={editForm.full_name} onChange={e => setEditForm(p => ({ ...p, full_name: e.target.value }))} data-testid="admin-edit-user-name" />
              </div>

              {/* Role change — not for super admins */}
              {!isSuperAdminUser(editUser) && (
                <div className="space-y-1">
                  <label className="text-xs text-slate-500 flex items-center gap-1">Role <FieldTip tip="Cannot promote to partner super admin here — use 'Transfer Super Admin' in Partner Orgs. Cannot assign platform super admin." /></label>
                  <Select value={editForm.role} onValueChange={v => setEditForm(p => ({ ...p, role: v }))}>
                    <SelectTrigger data-testid="admin-edit-user-role"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {editableRoles(editUser.role).map(r => (
                        <SelectItem key={r} value={r}>{roleLabel(r)}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {/* Module permissions — not for super admins */}
              {isSuperAdminUser(editUser) ? (
                <div className="flex items-center gap-2 p-3 rounded-lg bg-emerald-50 border border-emerald-200">
                  <ShieldCheck size={14} className="text-emerald-600" />
                  <p className="text-xs text-emerald-700">This user is a super admin with full access. Module restrictions don't apply.</p>
                </div>
              ) : (
                <>
                  {presetRoles.length > 0 && (
                    <div className="space-y-1">
                      <label className="text-xs text-slate-500 flex items-center gap-1">Quick Preset <FieldTip tip="Overwrites module permissions below." /></label>
                      <Select onValueChange={v => applyPreset(v, setEditPerms)}>
                        <SelectTrigger data-testid="admin-edit-user-preset"><SelectValue placeholder="Apply a preset…" /></SelectTrigger>
                        <SelectContent>
                          {presetRoles.map(r => <SelectItem key={r.key} value={r.key}>{r.name}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </div>
                  )}
                  <ModulePermEditor
                    modules={modulesForRole(editForm.role || editUser?.role)}
                    value={editPerms}
                    onChange={setEditPerms}
                  />
                </>
              )}

              <Button onClick={handleEdit} disabled={saving} className="w-full" data-testid="admin-edit-user-save">{saving ? "Saving…" : "Save Changes"}</Button>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* ── Deactivate Confirm ───────────────────────────────────────────── */}
      <AlertDialog open={!!deactivateUserId} onOpenChange={open => { if (!open) setDeactivateUserId(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Deactivate User?</AlertDialogTitle>
            <AlertDialogDescription>This user will lose access immediately. You can reactivate them later.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => deactivateUserId && handleDeactivate(deactivateUserId)} className="bg-red-600 hover:bg-red-700">Deactivate</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Audit Logs */}
      {logsUrl && (
        <AuditLogDialog open={!!logsUrl} onOpenChange={open => { if (!open) setLogsUrl(""); }} title="User Audit Logs" logsUrl={logsUrl} />
      )}
    </div>
  );
}
