import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { AdminPageHeader } from "./shared/AdminPageHeader";
import { AuditLogDialog } from "@/components/AuditLogDialog";
import { useAuth } from "@/contexts/AuthContext";
import { Plus, Shield, ShieldCheck, Eye } from "lucide-react";

interface ModuleInfo {
  key: string;
  name: string;
  description: string;
}

interface PresetRole {
  key: string;
  name: string;
  description: string;
  access_level: string;
  modules: string[];
}

export function UsersTab() {
  const { user: authUser } = useAuth();
  const [adminUsers, setAdminUsers] = useState<any[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const PER_PAGE = 20;
  const [searchFilter, setSearchFilter] = useState("");

  // Permission system data
  const [modules, setModules] = useState<ModuleInfo[]>([]);
  const [presetRoles, setPresetRoles] = useState<PresetRole[]>([]);

  // Dialogs
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [editUser, setEditUser] = useState<any>(null);
  const [newUser, setNewUser] = useState({ 
    email: "", full_name: "", password: "", 
    preset_role: "", access_level: "read_only", modules: [] as string[]
  });
  const [editForm, setEditForm] = useState({ 
    full_name: "", email: "", 
    access_level: "read_only", modules: [] as string[]
  });
  const [logsUrl, setLogsUrl] = useState("");
  const [showAuditLogs, setShowAuditLogs] = useState(false);
  const [confirmToggleUser, setConfirmToggleUser] = useState<{id: string, active: boolean} | null>(null);

  const load = useCallback(async (p = 1) => {
    try {
      const params = new URLSearchParams({ page: String(p), per_page: String(PER_PAGE) });
      if (searchFilter) params.append("search", searchFilter);
      const res = await api.get(`/admin/users?${params}`);
      setAdminUsers(res.data.users || []);
      setTotal(res.data.total || 0);
      setTotalPages(res.data.total_pages || 1);
      setPage(p);
    } catch { toast.error("Failed to load admin users"); }
  }, [searchFilter]);

  const loadPermissionsData = async () => {
    try {
      const res = await api.get("/admin/permissions/modules");
      setModules(res.data.modules || []);
      setPresetRoles(res.data.preset_roles || []);
    } catch { /* ignore */ }
  };

  useEffect(() => { load(1); loadPermissionsData(); }, [searchFilter]);

  const handleCreate = async () => {
    try {
      const payload: any = {
        email: newUser.email,
        password: newUser.password,
        full_name: newUser.full_name
      };
      if (newUser.preset_role) {
        payload.preset_role = newUser.preset_role;
      } else {
        payload.access_level = newUser.access_level;
        payload.modules = newUser.modules;
      }
      await api.post("/admin/users", payload);
      toast.success(`Admin user ${newUser.email} created`);
      setShowCreateDialog(false);
      setNewUser({ email: "", full_name: "", password: "", preset_role: "", access_level: "read_only", modules: [] });
      load(1);
    } catch (e: any) { toast.error(e.response?.data?.detail || "Failed to create user"); }
  };

  const openEdit = (u: any) => { 
    setEditUser(u); 
    setEditForm({ 
      full_name: u.full_name || "", 
      email: u.email || "", 
      access_level: u.access_level || "full_access",
      modules: u.permissions?.modules || []
    }); 
    setShowEditDialog(true); 
  };

  const handleEdit = async () => {
    if (!editUser) return;
    try {
      await api.put(`/admin/users/${editUser.id}`, {
        full_name: editForm.full_name,
        access_level: editForm.access_level,
        modules: editForm.modules
      });
      toast.success("User updated");
      setShowEditDialog(false);
      setEditUser(null);
      load(page);
    } catch (e: any) { toast.error(e.response?.data?.detail || "Failed to update user"); }
  };

  const handleToggleActive = async (userId: string, currentActive: boolean) => {
    const newState = !currentActive;
    try {
      if (newState) {
        await api.post(`/admin/users/${userId}/reactivate`);
      } else {
        await api.delete(`/admin/users/${userId}`);
      }
      toast.success(`User ${newState ? "activated" : "deactivated"}`);
      load(page);
    } catch (e: any) { toast.error(e.response?.data?.detail || "Failed to update"); }
  };

  const applyPresetRole = (roleKey: string) => {
    if (roleKey === "custom") {
      setNewUser(prev => ({ ...prev, preset_role: "" }));
      return;
    }
    const preset = presetRoles.find(r => r.key === roleKey);
    if (preset) {
      setNewUser(prev => ({
        ...prev,
        preset_role: roleKey,
        access_level: preset.access_level,
        modules: preset.modules
      }));
    }
  };

  const toggleModule = (key: string, isCreate: boolean) => {
    if (isCreate) {
      setNewUser(prev => ({
        ...prev,
        preset_role: "",
        modules: prev.modules.includes(key) 
          ? prev.modules.filter(m => m !== key)
          : [...prev.modules, key]
      }));
    } else {
      setEditForm(prev => ({
        ...prev,
        modules: prev.modules.includes(key)
          ? prev.modules.filter(m => m !== key)
          : [...prev.modules, key]
      }));
    }
  };

  const getRoleDisplay = (u: any) => {
    if (u.role === "platform_super_admin" || u.role === "partner_super_admin" || u.role === "super_admin") {
      return { label: "Super Admin", color: "bg-purple-100 text-purple-700" };
    }
    const preset = presetRoles.find(r => r.key === u.role);
    if (preset) return { label: preset.name, color: "bg-blue-100 text-blue-700" };
    return { label: "Custom", color: "bg-slate-100 text-slate-700" };
  };

  return (
    <div className="space-y-4" data-testid="users-tab">
      <AdminPageHeader title="Admin Users" subtitle="Only super admins can manage admin users" actions={
        <Button size="sm" onClick={() => setShowCreateDialog(true)} data-testid="admin-create-user-btn"><Plus size={14} className="mr-1" />Create Admin User</Button>
      } />

      {/* Filter */}
      <div className="rounded-xl border border-slate-200 bg-white p-3">
        <div className="flex gap-2 items-center">
          <Input placeholder="Search email or name…" value={searchFilter} onChange={e => setSearchFilter(e.target.value)} className="h-8 text-xs w-52" data-testid="admin-users-search" />
          <Button size="sm" variant="outline" onClick={() => setSearchFilter("")} className="h-8 text-xs">Clear</Button>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white">
        <Table data-testid="admin-users-table" className="text-sm">
          <TableHeader>
            <TableRow className="bg-slate-50">
              <TableHead>Name</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Access</TableHead>
              <TableHead>Modules</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {adminUsers.map((u: any) => {
              const isActive = u.is_active !== false;
              const roleDisplay = getRoleDisplay(u);
              const moduleCount = u.permissions?.modules?.length || 0;
              return (
                <TableRow key={u.id} data-testid={`admin-user-row-${u.id}`}>
                  <TableCell>{u.full_name}</TableCell>
                  <TableCell className="text-xs">{u.email}</TableCell>
                  <TableCell><span className={`px-2 py-0.5 rounded text-xs ${roleDisplay.color}`}>{roleDisplay.label}</span></TableCell>
                  <TableCell>
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] ${
                      u.access_level === "full_access" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
                    }`}>
                      {u.access_level === "full_access" ? <ShieldCheck size={10} /> : <Eye size={10} />}
                      {u.access_level === "full_access" ? "Full" : "Read"}
                    </span>
                  </TableCell>
                  <TableCell>
                    <span className="text-xs text-slate-500">{moduleCount > 0 ? `${moduleCount} modules` : "All"}</span>
                  </TableCell>
                  <TableCell><span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${isActive ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`} data-testid={`admin-user-status-${u.id}`}>{isActive ? "Active" : "Inactive"}</span></TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button variant="outline" size="sm" className="h-6 px-2 text-[11px]" onClick={() => openEdit(u)} data-testid={`admin-user-edit-${u.id}`}>Edit</Button>
                      <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px]" onClick={() => { setLogsUrl(`/admin/users/${u.id}/logs`); setShowAuditLogs(true); }} data-testid={`admin-user-logs-${u.id}`}>Logs</Button>
                      {u.id !== authUser?.id && (
                        <Button variant={isActive ? "destructive" : "outline"} size="sm" className="h-6 px-2 text-[11px]" onClick={() => setConfirmToggleUser({id: u.id, active: isActive})} data-testid={`admin-user-toggle-${u.id}`}>{isActive ? "Deactivate" : "Activate"}</Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
            {adminUsers.length === 0 && <TableRow><TableCell colSpan={7} className="text-center text-slate-400 py-4">No admin users found.</TableCell></TableRow>}
          </TableBody>
        </Table>
      </div>
      <AdminPagination page={page} totalPages={totalPages} total={total} perPage={PER_PAGE} onPage={(p) => load(p)} />

      {/* Create Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="admin-create-user-dialog">
          <DialogHeader><DialogTitle>Create Admin User</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1"><label className="text-xs text-slate-500">Full Name *</label><Input value={newUser.full_name} onChange={e => setNewUser({ ...newUser, full_name: e.target.value })} data-testid="admin-new-user-name" /></div>
              <div className="space-y-1"><label className="text-xs text-slate-500">Email *</label><Input type="email" value={newUser.email} onChange={e => setNewUser({ ...newUser, email: e.target.value })} data-testid="admin-new-user-email" /></div>
              <div className="space-y-1 col-span-2"><label className="text-xs text-slate-500">Password *</label><Input type="password" value={newUser.password} onChange={e => setNewUser({ ...newUser, password: e.target.value })} data-testid="admin-new-user-password" /></div>
            </div>

            <div className="space-y-1">
              <label className="text-xs text-slate-500">Role Template</label>
              <Select value={newUser.preset_role || "custom"} onValueChange={applyPresetRole}>
                <SelectTrigger data-testid="admin-new-user-preset">
                  <SelectValue placeholder="Select a preset role" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="custom">Custom (configure below)</SelectItem>
                  {presetRoles.map(role => (
                    <SelectItem key={role.key} value={role.key}>{role.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <label className="text-xs text-slate-500">Access Level</label>
              <Select value={newUser.access_level} onValueChange={v => setNewUser({ ...newUser, access_level: v, preset_role: "" })}>
                <SelectTrigger data-testid="admin-new-user-access">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="full_access">
                    <div className="flex items-center gap-2"><ShieldCheck size={14} className="text-emerald-500" /> Full Access</div>
                  </SelectItem>
                  <SelectItem value="read_only">
                    <div className="flex items-center gap-2"><Eye size={14} className="text-amber-500" /> Read Only</div>
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <label className="text-xs text-slate-500">Module Access ({newUser.modules.length} selected)</label>
              <div className="border border-slate-200 rounded-lg p-2 max-h-40 overflow-y-auto space-y-1">
                {modules.map(mod => (
                  <label key={mod.key} className="flex items-center gap-2 py-1 cursor-pointer hover:bg-slate-50 rounded px-1">
                    <Checkbox
                      checked={newUser.modules.includes(mod.key)}
                      onCheckedChange={() => toggleModule(mod.key, true)}
                    />
                    <span className="text-xs text-slate-700">{mod.name}</span>
                  </label>
                ))}
              </div>
            </div>

            <Button onClick={handleCreate} className="w-full" data-testid="admin-new-user-submit">Create Admin User</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={showEditDialog} onOpenChange={(open) => { setShowEditDialog(open); if (!open) setEditUser(null); }}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="admin-edit-user-dialog">
          <DialogHeader><DialogTitle>Edit User: {editUser?.email}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-xs text-slate-500">Full Name</label>
              <Input value={editForm.full_name} onChange={e => setEditForm({ ...editForm, full_name: e.target.value })} data-testid="admin-edit-user-name" />
            </div>

            <div className="space-y-1">
              <label className="text-xs text-slate-500">Access Level</label>
              <Select value={editForm.access_level} onValueChange={v => setEditForm({ ...editForm, access_level: v })}>
                <SelectTrigger data-testid="admin-edit-user-access">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="full_access">
                    <div className="flex items-center gap-2"><ShieldCheck size={14} className="text-emerald-500" /> Full Access</div>
                  </SelectItem>
                  <SelectItem value="read_only">
                    <div className="flex items-center gap-2"><Eye size={14} className="text-amber-500" /> Read Only</div>
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <label className="text-xs text-slate-500">Module Access ({editForm.modules.length} selected)</label>
              <div className="border border-slate-200 rounded-lg p-2 max-h-40 overflow-y-auto space-y-1">
                {modules.map(mod => (
                  <label key={mod.key} className="flex items-center gap-2 py-1 cursor-pointer hover:bg-slate-50 rounded px-1">
                    <Checkbox
                      checked={editForm.modules.includes(mod.key)}
                      onCheckedChange={() => toggleModule(mod.key, false)}
                    />
                    <span className="text-xs text-slate-700">{mod.name}</span>
                  </label>
                ))}
              </div>
            </div>

            <Button onClick={handleEdit} className="w-full" data-testid="admin-edit-user-save">Save Changes</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* User Audit Logs Dialog */}
      <Dialog open={showEntityLogs} onOpenChange={setShowEntityLogs}>
        <DialogContent className="max-w-2xl"><DialogHeader><DialogTitle>User Audit Logs</DialogTitle></DialogHeader>
          <div className="max-h-[60vh] overflow-y-auto space-y-2">
            {entityLogs.length === 0 && <p className="text-sm text-slate-500 text-center py-4">No logs found</p>}
            {entityLogs.map((log: any, i: number) => (
              <div key={log.id || i} className="border border-slate-200 rounded p-3">
                <div className="flex justify-between items-start mb-1">
                  <span className="text-sm font-semibold text-slate-900">{log.action}</span>
                  <span className="text-xs text-slate-500">{new Date(log.created_at).toLocaleString()}</span>
                </div>
                <div className="text-xs text-slate-600">Actor: {log.actor}</div>
                {log.details && Object.keys(log.details).length > 0 && (
                  <pre className="text-xs text-slate-500 mt-1 bg-slate-50 p-2 rounded overflow-x-auto">{JSON.stringify(log.details, null, 2)}</pre>
                )}
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>

      {/* Deactivate/Activate User Confirmation */}
      <AlertDialog open={!!confirmToggleUser} onOpenChange={(open) => !open && setConfirmToggleUser(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{confirmToggleUser?.active ? "Deactivate User" : "Activate User"}</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to {confirmToggleUser?.active ? "deactivate" : "activate"} this user?
              {confirmToggleUser?.active && " They will no longer be able to log in."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className={confirmToggleUser?.active ? "bg-red-600 hover:bg-red-700" : ""}
              onClick={() => { handleToggleActive(confirmToggleUser!.id, confirmToggleUser!.active); setConfirmToggleUser(null); }}
              data-testid="confirm-user-toggle"
            >
              {confirmToggleUser?.active ? "Deactivate" : "Activate"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
