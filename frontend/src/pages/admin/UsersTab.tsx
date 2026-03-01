import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { AdminPageHeader } from "./shared/AdminPageHeader";
import { AdminPagination } from "./shared/AdminPagination";
import { AuditLogDialog } from "@/components/AuditLogDialog";
import { useAuth } from "@/contexts/AuthContext";
import { Plus, Shield, ShieldCheck, Eye, Pencil, PowerOff, Power, ScrollText, Lock, Users, Zap } from "lucide-react";
import { FieldTip } from "./shared/FieldTip";

// ── Types ─────────────────────────────────────────────────────────────────────

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

type ModulePerm = Record<string, "read" | "write" | "none">;

// ── Module Permission Editor ───────────────────────────────────────────────────

function ModulePermEditor({
  modules,
  value,
  onChange,
}: {
  modules: ModuleInfo[];
  value: ModulePerm;
  onChange: (mp: ModulePerm) => void;
}) {
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
            <Select
              value={value[mod.key] || "none"}
              onValueChange={v => onChange({ ...value, [mod.key]: v as "read" | "write" | "none" })}
            >
              <SelectTrigger className="w-36 h-7 text-xs" data-testid={`perm-${mod.key}`}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">
                  <span className="text-slate-400">No Access</span>
                </SelectItem>
                <SelectItem value="read">
                  <span className="flex items-center gap-1.5"><Eye size={11} className="text-amber-500" />Read</span>
                </SelectItem>
                <SelectItem value="write">
                  <span className="flex items-center gap-1.5"><ShieldCheck size={11} className="text-emerald-500" />Read &amp; Write</span>
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
        ))}
      </div>
    </div>
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

/** Strip "none" entries before sending to API */
function toApiPerm(mp: ModulePerm): Record<string, "read" | "write"> {
  return Object.fromEntries(Object.entries(mp).filter(([, v]) => v !== "none")) as Record<string, "read" | "write">;
}

function roleLabel(role: string): string {
  const map: Record<string, string> = {
    platform_super_admin: "Platform Super Admin",
    platform_admin: "Platform Admin",
    partner_super_admin: "Partner Super Admin",
    partner_admin: "Partner Admin",
    partner_staff: "Partner Staff",
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

function PresetsSubTab({ modules }: { modules: ModuleInfo[] }) {
  const [presets, setPresets] = useState<PresetRole[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/admin/permissions/modules")
      .then(r => setPresets(r.data.preset_roles || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-sm text-slate-400 py-8">Loading presets…</div>;

  return (
    <div className="space-y-4" data-testid="presets-subtab">
      <div>
        <h2 className="text-base font-semibold text-slate-900">Quick Presets</h2>
        <p className="text-sm text-slate-500 mt-0.5">
          Built-in permission templates. Apply these when creating or editing a user via the "Quick Preset" dropdown.
        </p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {presets.map(preset => {
          const entries = Object.entries(preset.module_permissions || {});
          const writeCount = entries.filter(([, v]) => v === "write").length;
          const readCount = entries.filter(([, v]) => v === "read").length;
          return (
            <div
              key={preset.key}
              className="rounded-xl border border-slate-200 bg-white p-5 space-y-3"
              data-testid={`preset-card-${preset.key}`}
            >
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-slate-100">
                  <Zap size={14} className="text-slate-500" />
                </div>
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
                    <span
                      key={key}
                      className={`inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded border font-medium ${
                        val === "write"
                          ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                          : "bg-amber-50 text-amber-700 border-amber-200"
                      }`}
                    >
                      {val === "write" ? <ShieldCheck size={9} /> : <Eye size={9} />}
                      {mod?.name || key}
                    </span>
                  );
                })}
              </div>
              <p className="text-[10px] text-slate-400 pt-1 border-t border-slate-100">
                {writeCount} read &amp; write · {readCount} read only
              </p>
            </div>
          );
        })}
      </div>
      {presets.length === 0 && (
        <p className="text-sm text-slate-400 italic">No presets available.</p>
      )}
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

  // Permission system data (scoped to caller's context)
  const [modules, setModules] = useState<ModuleInfo[]>([]);
  const [presetRoles, setPresetRoles] = useState<PresetRole[]>([]);

  // Create dialog
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [newUser, setNewUser] = useState({
    email: "", full_name: "", password: "", role: "",
  });
  const [newUserPerms, setNewUserPerms] = useState<ModulePerm>({});

  // Edit dialog
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [editUser, setEditUser] = useState<any>(null);
  const [editForm, setEditForm] = useState({ full_name: "" });
  const [editPerms, setEditPerms] = useState<ModulePerm>({});

  // Misc
  const [logsUrl, setLogsUrl] = useState("");
  const [deactivateUserId, setDeactivateUserId] = useState<string | null>(null);

  // Which roles can the caller create?
  const creatableRoles = isPlatformSuperAdmin
    ? [
        { value: "platform_admin", label: "Platform Admin" },
        { value: "partner_admin", label: "Partner Admin" },
        { value: "partner_staff", label: "Partner Staff" },
      ]
    : isPartnerSuperAdmin
    ? [
        { value: "partner_admin", label: "Partner Admin" },
        { value: "partner_staff", label: "Partner Staff" },
      ]
    : [];

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
      setModules(r.data.modules || []);
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

  useEffect(() => {
    const t = setTimeout(() => load(1), 300);
    return () => clearTimeout(t);
  }, [searchFilter, partnerFilter]); // eslint-disable-line

  // ── Create ──────────────────────────────────────────────────────────────────

  const handleCreate = async () => {
    if (!newUser.email || !newUser.password || !newUser.role) {
      toast.error("Email, password and role are required");
      return;
    }
    try {
      await api.post("/admin/users", {
        email: newUser.email,
        full_name: newUser.full_name,
        password: newUser.password,
        role: newUser.role,
        module_permissions: toApiPerm(newUserPerms),
      });
      toast.success(`User ${newUser.email} created`);
      setShowCreateDialog(false);
      setNewUser({ email: "", full_name: "", password: "", role: "" });
      setNewUserPerms({});
      load(1);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to create user");
    }
  };

  const applyPreset = (presetKey: string, setPerms: (mp: ModulePerm) => void) => {
    const preset = presetRoles.find(r => r.key === presetKey);
    if (preset?.module_permissions) {
      setPerms(toModulePerm(preset.module_permissions));
    }
  };

  // ── Edit ────────────────────────────────────────────────────────────────────

  const openEdit = (u: any) => {
    setEditUser(u);
    setEditForm({ full_name: u.full_name || "" });
    setEditPerms(toModulePerm(u.module_permissions));
    setShowEditDialog(true);
  };

  const handleEdit = async () => {
    if (!editUser) return;
    try {
      await api.put(`/admin/users/${editUser.id}`, {
        full_name: editForm.full_name,
        module_permissions: toApiPerm(editPerms),
      });
      toast.success("User updated");
      setShowEditDialog(false);
      setEditUser(null);
      load(page);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to update user");
    }
  };

  // ── Deactivate ───────────────────────────────────────────────────────────────

  const handleDeactivate = async (userId: string) => {
    try {
      await api.patch(`/admin/users/${userId}/active`, null, { params: { active: false } });
      toast.success("User deactivated");
      load(page);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to deactivate user");
    } finally {
      setDeactivateUserId(null);
    }
  };

  const handleReactivate = async (userId: string) => {
    try {
      await api.patch(`/admin/users/${userId}/active`, null, { params: { active: true } });
      toast.success("User reactivated");
      load(page);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to reactivate user");
    }
  };

  const isPlatformSuperAdminUser = (u: any) => u.role === "platform_super_admin";

  return (
    <div data-testid="users-tab">
      <Tabs defaultValue="list">
        <TabsList className="mb-4">
          <TabsTrigger value="list" data-testid="users-subtab-list">
            <Users size={13} className="mr-1.5" />Users
          </TabsTrigger>
          <TabsTrigger value="presets" data-testid="users-subtab-presets">
            <Zap size={13} className="mr-1.5" />Quick Presets
          </TabsTrigger>
        </TabsList>

        <TabsContent value="presets">
          <PresetsSubTab modules={modules} />
        </TabsContent>

        <TabsContent value="list">
      <AdminPageHeader
        title="Admin Users"
        subtitle={`${total} admin user${total !== 1 ? "s" : ""}`}
        actions={
          isSuperAdmin ? (
            <Button size="sm" onClick={() => setShowCreateDialog(true)} data-testid="create-user-btn">
              <Plus size={14} className="mr-1.5" />Add User
            </Button>
          ) : undefined
        }
      />

      {/* Filters */}
      <div className="flex gap-2 mb-4 flex-wrap">
        <Input
          placeholder="Search by name or email…"
          value={searchFilter}
          onChange={e => setSearchFilter(e.target.value)}
          className="max-w-xs"
          data-testid="users-search"
        />
        {isPlatformAdmin && partners.length > 0 && (
          <Select value={partnerFilter} onValueChange={setPartnerFilter}>
            <SelectTrigger className="w-44" data-testid="users-partner-filter"><SelectValue placeholder="All Partners" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Partners</SelectItem>
              {partners.map(p => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}
            </SelectContent>
          </Select>
        )}
      </div>

      {/* Table */}
      <div className="rounded-lg border border-slate-200 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-slate-50">
              <TableHead className="text-xs">Name / Email</TableHead>
              <TableHead className="text-xs">Role</TableHead>
              <TableHead className="text-xs">Modules</TableHead>
              <TableHead className="text-xs">Status</TableHead>
              <TableHead className="text-xs text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {adminUsers.map(u => {
              const isImmutable = isPlatformSuperAdminUser(u);
              const mpKeys = Object.keys(u.module_permissions || {});
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
                  <TableCell>
                    {isImmutable || u.role === "partner_super_admin" ? (
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
                      <span className="text-xs text-slate-400 italic flex items-center justify-end gap-1">
                        <Lock size={11} /> Protected
                      </span>
                    ) : isSuperAdmin ? (
                      <div className="flex gap-1.5 justify-end">
                        <Button size="sm" variant="ghost" className="h-7 px-2" onClick={() => openEdit(u)} data-testid={`edit-user-${u.id}`}>
                          <Pencil size={13} />
                        </Button>
                        <Button
                          size="sm" variant="ghost"
                          className={`h-7 px-2 ${u.is_active ? "text-red-500 hover:text-red-600" : "text-emerald-500 hover:text-emerald-600"}`}
                          onClick={() => u.is_active ? setDeactivateUserId(u.id) : handleReactivate(u.id)}
                          data-testid={`toggle-active-${u.id}`}
                        >
                          {u.is_active ? <PowerOff size={13} /> : <Power size={13} />}
                        </Button>
                        <Button size="sm" variant="ghost" className="h-7 px-2" onClick={() => setLogsUrl(`/admin/audit-logs?entity_type=user&entity_id=${u.id}`)} data-testid={`logs-user-${u.id}`}>
                          <ScrollText size={13} />
                        </Button>
                      </div>
                    ) : null}
                  </TableCell>
                </TableRow>
              );
            })}
            {adminUsers.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-sm text-slate-400 py-8">No admin users found</TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <AdminPagination page={page} totalPages={totalPages} total={total} perPage={PER_PAGE} onPage={p => load(p)} />

      {/* ── Create Dialog ─────────────────────────────────────────────────── */}
      <Dialog open={showCreateDialog} onOpenChange={open => { setShowCreateDialog(open); if (!open) { setNewUser({ email: "", full_name: "", password: "", role: "" }); setNewUserPerms({}); } }}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="create-user-dialog">
          <DialogHeader><DialogTitle>Add Admin User</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Full Name</label>
                <Input value={newUser.full_name} onChange={e => setNewUser(p => ({ ...p, full_name: e.target.value }))} placeholder="Jane Smith" data-testid="new-user-name" />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Role <span className="text-red-400">*</span></label>
                <Select value={newUser.role} onValueChange={v => { setNewUser(p => ({ ...p, role: v })); setNewUserPerms({}); }}>
                  <SelectTrigger data-testid="new-user-role"><SelectValue placeholder="Select role…" /></SelectTrigger>
                  <SelectContent>
                    {creatableRoles.map(r => <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-xs text-slate-500">Email <span className="text-red-400">*</span></label>
              <Input type="email" value={newUser.email} onChange={e => setNewUser(p => ({ ...p, email: e.target.value }))} placeholder="jane@company.com" data-testid="new-user-email" />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-500">Temporary Password <span className="text-red-400">*</span></label>
              <Input type="password" value={newUser.password} onChange={e => setNewUser(p => ({ ...p, password: e.target.value }))} placeholder="Min 10 chars, upper, lower, digit, symbol" data-testid="new-user-password" />
            </div>

            {/* Preset quick-fill */}
            {presetRoles.length > 0 && (
              <div className="space-y-1">
                <label className="text-xs text-slate-500 flex items-center gap-1">
                  Quick Preset <FieldTip tip="Selecting a preset auto-fills the module permissions below. You can still adjust them manually." />
                </label>
                <Select onValueChange={v => applyPreset(v, setNewUserPerms)}>
                  <SelectTrigger data-testid="new-user-preset"><SelectValue placeholder="Apply a preset (optional)…" /></SelectTrigger>
                  <SelectContent>
                    {presetRoles.map(r => <SelectItem key={r.key} value={r.key}>{r.name} — {r.description}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            )}

            {/* Per-module permissions */}
            {modules.length > 0 && (
              <ModulePermEditor modules={modules} value={newUserPerms} onChange={setNewUserPerms} />
            )}

            <Button onClick={handleCreate} className="w-full" data-testid="create-user-submit">Create User</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── Edit Dialog ───────────────────────────────────────────────────── */}
      <Dialog open={showEditDialog} onOpenChange={open => { setShowEditDialog(open); if (!open) setEditUser(null); }}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="admin-edit-user-dialog">
          <DialogHeader><DialogTitle>Edit User: {editUser?.email}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-xs text-slate-500">Full Name</label>
              <Input value={editForm.full_name} onChange={e => setEditForm(p => ({ ...p, full_name: e.target.value }))} data-testid="admin-edit-user-name" />
            </div>

            {/* Preset quick-fill */}
            {presetRoles.length > 0 && (
              <div className="space-y-1">
                <label className="text-xs text-slate-500 flex items-center gap-1">
                  Quick Preset <FieldTip tip="Selecting a preset overwrites the module permissions below." />
                </label>
                <Select onValueChange={v => applyPreset(v, setEditPerms)}>
                  <SelectTrigger data-testid="admin-edit-user-preset"><SelectValue placeholder="Apply a preset…" /></SelectTrigger>
                  <SelectContent>
                    {presetRoles.map(r => <SelectItem key={r.key} value={r.key}>{r.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            )}

            {/* Per-module permissions */}
            {modules.length > 0 && (
              <ModulePermEditor modules={modules} value={editPerms} onChange={setEditPerms} />
            )}

            <Button onClick={handleEdit} className="w-full" data-testid="admin-edit-user-save">Save Changes</Button>
          </div>
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
            <AlertDialogAction onClick={() => deactivateUserId && handleDeactivate(deactivateUserId)} className="bg-red-600 hover:bg-red-700">
              Deactivate
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Audit Logs */}
      {logsUrl && (
        <AuditLogDialog
          open={!!logsUrl}
          onOpenChange={open => { if (!open) setLogsUrl(""); }}
          title="User Audit Logs"
          logsUrl={logsUrl}
        />
      )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
