import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { AdminPageHeader } from "./shared/AdminPageHeader";
import { useAuth } from "@/contexts/AuthContext";
import { Plus } from "lucide-react";

export function UsersTab() {
  const { user: authUser } = useAuth();
  const [adminUsers, setAdminUsers] = useState<any[]>([]);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [newUser, setNewUser] = useState({ email: "", full_name: "", company_name: "", phone: "", password: "", role: "admin" });

  const load = async () => {
    try {
      const res = await api.get("/admin/users");
      setAdminUsers(res.data.users || []);
    } catch { toast.error("Failed to load admin users"); }
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async () => {
    try {
      await api.post("/admin/users", newUser);
      toast.success(`Admin user ${newUser.email} created`);
      setShowCreateDialog(false);
      setNewUser({ email: "", full_name: "", company_name: "", phone: "", password: "", role: "admin" });
      load();
    } catch (e: any) { toast.error(e.response?.data?.detail || "Failed to create user"); }
  };

  const handleToggleActive = async (userId: string, currentActive: boolean) => {
    const newState = !currentActive;
    if (!confirm(`${newState ? "Activate" : "Deactivate"} this user?${!newState ? " They will be unable to login." : ""}`)) return;
    try {
      await api.patch(`/admin/users/${userId}/active?active=${newState}`);
      toast.success(`User ${newState ? "activated" : "deactivated"}`);
      load();
    } catch (e: any) { toast.error(e.response?.data?.detail || "Failed to update user status"); }
  };

  return (
    <div className="space-y-4" data-testid="users-tab">
      <AdminPageHeader
        title="Admin Users"
        subtitle="Only super admins can create admin users"
        actions={
          <Button size="sm" onClick={() => setShowCreateDialog(true)} data-testid="admin-create-user-btn"><Plus size={14} className="mr-1" />Create Admin User</Button>
        }
      />

      <div className="rounded-xl border border-slate-200 bg-white">
        <Table data-testid="admin-users-table" className="text-sm">
          <TableHeader>
            <TableRow className="bg-slate-50">
              <TableHead>Name</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Created</TableHead>
              <TableHead>Must Change PW</TableHead>
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
                  <TableCell>
                    <span className={`px-2 py-0.5 rounded text-xs ${u.role === "super_admin" ? "bg-purple-100 text-purple-700" : "bg-blue-100 text-blue-700"}`}>{u.role}</span>
                  </TableCell>
                  <TableCell>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${isActive ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`} data-testid={`admin-user-status-${u.id}`}>
                      {isActive ? "Active" : "Inactive"}
                    </span>
                  </TableCell>
                  <TableCell>{u.created_at?.slice(0, 10) || "—"}</TableCell>
                  <TableCell>{u.must_change_password ? "Yes" : "No"}</TableCell>
                  <TableCell>
                    {u.id !== authUser?.id && (
                      <Button
                        variant={isActive ? "destructive" : "outline"}
                        size="sm" className="h-6 px-2 text-[11px]"
                        onClick={() => handleToggleActive(u.id, isActive)}
                        data-testid={`admin-user-toggle-active-${u.id}`}
                      >{isActive ? "Deactivate" : "Activate"}</Button>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
            {adminUsers.length === 0 && (
              <TableRow><TableCell colSpan={7} className="text-center text-slate-400 py-4">No admin users found.</TableCell></TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Create Admin User Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="max-w-lg" data-testid="admin-create-user-dialog">
          <DialogHeader><DialogTitle>Create Admin User</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Full Name *</label>
                <Input value={newUser.full_name} onChange={e => setNewUser({ ...newUser, full_name: e.target.value })} data-testid="admin-new-user-name" />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Email *</label>
                <Input type="email" value={newUser.email} onChange={e => setNewUser({ ...newUser, email: e.target.value })} data-testid="admin-new-user-email" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Password *</label>
                <Input type="password" value={newUser.password} onChange={e => setNewUser({ ...newUser, password: e.target.value })} data-testid="admin-new-user-password" />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Role</label>
                <select value={newUser.role} onChange={e => setNewUser({ ...newUser, role: e.target.value })} className="w-full h-9 text-sm border border-slate-200 rounded px-2" data-testid="admin-new-user-role">
                  <option value="admin">Admin</option>
                  <option value="super_admin">Super Admin</option>
                </select>
              </div>
            </div>
            <p className="text-xs text-amber-600">User will be required to change password on first login.</p>
            <Button onClick={handleCreate} className="w-full" data-testid="admin-new-user-submit">Create Admin User</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
