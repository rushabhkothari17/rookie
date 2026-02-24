import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { AdminPageHeader } from "./shared/AdminPageHeader";
import { AdminPagination } from "./shared/AdminPagination";
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
  const [entityLogs, setEntityLogs] = useState<any[]>([]);
  const [showEntityLogs, setShowEntityLogs] = useState(false);

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
    if (!confirm(`${newState ? "Activate" : "Deactivate"} this user?`)) return;
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
              <TableHead>Status</TableHead>
              <TableHead>Created</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {adminUsers.map((u: any) => {
              const isActive = u.is_active !== false;
              return (
                <TableRow key={u.id} data-testid={`admin-user-row-${u.id}`}>
                  <TableCell>{u.full_name}</TableCell>
                  <TableCell>{u.email}</TableCell>
                  <TableCell><span className={`px-2 py-0.5 rounded text-xs ${u.role === "platform_admin" ? "bg-amber-100 text-amber-700" : u.role === "super_admin" ? "bg-purple-100 text-purple-700" : "bg-blue-100 text-blue-700"}`}>{u.role}</span></TableCell>
                  <TableCell><span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${isActive ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`} data-testid={`admin-user-status-${u.id}`}>{isActive ? "Active" : "Inactive"}</span></TableCell>
                  <TableCell>{u.created_at?.slice(0, 10) || "—"}</TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button variant="outline" size="sm" className="h-6 px-2 text-[11px]" onClick={() => openEdit(u)} data-testid={`admin-user-edit-${u.id}`}>Edit</Button>
                      <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px]" onClick={async () => { const r = await api.get(`/admin/users/${u.id}/logs`); setEntityLogs(r.data.logs || []); setShowEntityLogs(true); }} data-testid={`admin-user-logs-${u.id}`}>Logs</Button>
                      {u.id !== authUser?.id && (
                        <Button variant={isActive ? "destructive" : "outline"} size="sm" className="h-6 px-2 text-[11px]" onClick={() => handleToggleActive(u.id, isActive)} data-testid={`admin-user-toggle-${u.id}`}>{isActive ? "Deactivate" : "Activate"}</Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
            {adminUsers.length === 0 && <TableRow><TableCell colSpan={6} className="text-center text-slate-400 py-4">No admin users found.</TableCell></TableRow>}
          </TableBody>
        </Table>
      </div>
      <AdminPagination page={page} totalPages={totalPages} total={total} perPage={PER_PAGE} onPage={(p) => load(p)} />

      {/* Create Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="max-w-lg" data-testid="admin-create-user-dialog">
          <DialogHeader><DialogTitle>Create Admin User</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1"><label className="text-xs text-slate-500">Full Name *</label><Input value={newUser.full_name} onChange={e => setNewUser({ ...newUser, full_name: e.target.value })} data-testid="admin-new-user-name" /></div>
              <div className="space-y-1"><label className="text-xs text-slate-500">Email *</label><Input type="email" value={newUser.email} onChange={e => setNewUser({ ...newUser, email: e.target.value })} data-testid="admin-new-user-email" /></div>
              <div className="space-y-1"><label className="text-xs text-slate-500">Password *</label><Input type="password" value={newUser.password} onChange={e => setNewUser({ ...newUser, password: e.target.value })} data-testid="admin-new-user-password" /></div>
              <div className="space-y-1"><label className="text-xs text-slate-500">Role</label>
                <select value={newUser.role} onChange={e => setNewUser({ ...newUser, role: e.target.value })} className="w-full h-9 text-sm border border-slate-200 rounded px-2" data-testid="admin-new-user-role">
                  <option value="admin">Admin</option><option value="super_admin">Super Admin</option>
                </select>
              </div>
            </div>
            <p className="text-xs text-amber-600">User will be required to change password on first login.</p>
            <Button onClick={handleCreate} className="w-full" data-testid="admin-new-user-submit">Create Admin User</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={showEditDialog} onOpenChange={(open) => { setShowEditDialog(open); if (!open) setEditUser(null); }}>
        <DialogContent className="max-w-lg" data-testid="admin-edit-user-dialog">
          <DialogHeader><DialogTitle>Edit User: {editUser?.email}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1"><label className="text-xs text-slate-500">Full Name</label><Input value={editForm.full_name} onChange={e => setEditForm({ ...editForm, full_name: e.target.value })} data-testid="admin-edit-user-name" /></div>
              <div className="space-y-1"><label className="text-xs text-slate-500">Email</label><Input type="email" value={editForm.email} onChange={e => setEditForm({ ...editForm, email: e.target.value })} data-testid="admin-edit-user-email" /></div>
              <div className="space-y-1"><label className="text-xs text-slate-500">Role</label>
                <select value={editForm.role} onChange={e => setEditForm({ ...editForm, role: e.target.value })} className="w-full h-9 text-sm border border-slate-200 rounded px-2" data-testid="admin-edit-user-role">
                  <option value="admin">Admin</option><option value="super_admin">Super Admin</option>
                </select>
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
    </div>
  );
}
