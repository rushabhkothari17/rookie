import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Shield, ShieldCheck, Eye, Plus, Pencil, Trash2, Lock } from "lucide-react";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { AdminPageHeader } from "./shared/AdminPageHeader";

interface Module {
  key: string;
  name: string;
  description: string;
}

interface Role {
  id: string;
  key: string | null;
  name: string;
  description: string;
  access_level: string;
  modules: string[];
  is_preset: boolean;
}

const BLANK_ROLE = { name: "", description: "", access_level: "read_only", modules: [] as string[] };

export function RolesTab() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [modules, setModules] = useState<Module[]>([]);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [editRole, setEditRole] = useState<Role | null>(null);
  const [form, setForm] = useState(BLANK_ROLE);
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<Role | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get("/admin/roles");
      setRoles(res.data.roles || []);
      setModules(res.data.modules || []);
    } catch {
      toast.error("Failed to load roles");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const openCreate = () => {
    setEditRole(null);
    setForm(BLANK_ROLE);
    setShowDialog(true);
  };

  const openEdit = (role: Role) => {
    setEditRole(role);
    setForm({ name: role.name, description: role.description, access_level: role.access_level, modules: [...role.modules] });
    setShowDialog(true);
  };

  const toggleModule = (key: string) => {
    setForm(prev => ({
      ...prev,
      modules: prev.modules.includes(key) ? prev.modules.filter(m => m !== key) : [...prev.modules, key],
    }));
  };

  const selectAll = () => setForm(prev => ({ ...prev, modules: modules.map(m => m.key) }));
  const clearAll = () => setForm(prev => ({ ...prev, modules: [] }));

  const handleSave = async () => {
    if (!form.name.trim()) { toast.error("Role name is required"); return; }
    setSaving(true);
    try {
      if (editRole && !editRole.is_preset) {
        await api.put(`/admin/roles/${editRole.id}`, form);
        toast.success("Role updated");
      } else {
        await api.post("/admin/roles", form);
        toast.success("Role created");
      }
      setShowDialog(false);
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to save role");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!confirmDelete) return;
    try {
      await api.delete(`/admin/roles/${confirmDelete.id}`);
      toast.success("Role deleted");
      setConfirmDelete(null);
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to delete role");
    }
  };

  const getAccessBadge = (level: string) => level === "full_access"
    ? { label: "Full Access", cls: "bg-emerald-50 text-emerald-700 border-emerald-200" }
    : { label: "Read Only", cls: "bg-amber-50 text-amber-700 border-amber-200" };

  if (loading) return <div className="p-8 text-slate-400 text-sm">Loading roles…</div>;

  return (
    <div className="space-y-4" data-testid="roles-tab">
      <AdminPageHeader
        title="Roles & Permissions"
        subtitle="Manage role definitions and module access. Built-in roles are templates; create custom roles for your team."
        actions={
          <Button size="sm" onClick={openCreate} data-testid="create-role-btn">
            <Plus size={14} className="mr-1" /> Create Role
          </Button>
        }
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4" data-testid="roles-grid">
        {roles.map(role => {
          const badge = getAccessBadge(role.access_level);
          return (
            <div
              key={role.id}
              className="rounded-xl border border-slate-200 bg-white p-5 flex flex-col gap-3 hover:border-slate-300 transition-colors"
              data-testid={`role-card-${role.id}`}
            >
              {/* Header */}
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className={`p-2 rounded-lg shrink-0 ${role.is_preset ? "bg-slate-100" : "bg-blue-50"}`}>
                    {role.is_preset ? <Lock size={15} className="text-slate-500" /> : <Shield size={15} className="text-blue-500" />}
                  </div>
                  <div className="min-w-0">
                    <h4 className="text-sm font-semibold text-slate-900 truncate">{role.name}</h4>
                    {role.is_preset && (
                      <span className="text-[10px] font-medium text-slate-400 uppercase tracking-wide">Built-in</span>
                    )}
                  </div>
                </div>
                <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border shrink-0 ${badge.cls}`}>
                  {badge.label}
                </span>
              </div>

              {/* Description */}
              {role.description && (
                <p className="text-xs text-slate-500 leading-relaxed">{role.description}</p>
              )}

              {/* Modules */}
              <div className="flex flex-wrap gap-1">
                {role.modules.length === 0 ? (
                  <span className="text-xs text-slate-400 italic">No modules assigned</span>
                ) : role.modules.length > 5 ? (
                  <>
                    {role.modules.slice(0, 4).map(m => (
                      <span key={m} className="text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">
                        {modules.find(mod => mod.key === m)?.name || m}
                      </span>
                    ))}
                    <span className="text-[10px] bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded">
                      +{role.modules.length - 4} more
                    </span>
                  </>
                ) : role.modules.map(m => (
                  <span key={m} className="text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">
                    {modules.find(mod => mod.key === m)?.name || m}
                  </span>
                ))}
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2 pt-1 border-t border-slate-100">
                {role.is_preset ? (
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 px-2 text-xs gap-1"
                    onClick={() => openEdit(role)}
                    data-testid={`role-view-${role.id}`}
                  >
                    <Eye size={12} /> View
                  </Button>
                ) : (
                  <>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 px-2 text-xs gap-1"
                      onClick={() => openEdit(role)}
                      data-testid={`role-edit-${role.id}`}
                    >
                      <Pencil size={12} /> Edit
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 px-2 text-xs gap-1 text-red-500 hover:text-red-700 hover:bg-red-50"
                      onClick={() => setConfirmDelete(role)}
                      data-testid={`role-delete-${role.id}`}
                    >
                      <Trash2 size={12} /> Delete
                    </Button>
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Create / Edit Dialog */}
      <Dialog open={showDialog} onOpenChange={(v) => { setShowDialog(v); if (!v) setEditRole(null); }}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="role-dialog">
          <DialogHeader>
            <DialogTitle>
              {editRole ? (editRole.is_preset ? `View: ${editRole.name}` : `Edit: ${editRole.name}`) : "Create Custom Role"}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Role Name *</label>
              <Input
                value={form.name}
                onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
                placeholder="e.g. Billing Manager"
                disabled={editRole?.is_preset}
                data-testid="role-form-name"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Description</label>
              <Textarea
                value={form.description}
                onChange={e => setForm(p => ({ ...p, description: e.target.value }))}
                placeholder="Brief description of this role's responsibilities"
                rows={2}
                disabled={editRole?.is_preset}
                data-testid="role-form-description"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Access Level</label>
              <Select
                value={form.access_level}
                onValueChange={v => setForm(p => ({ ...p, access_level: v }))}
                disabled={editRole?.is_preset}
              >
                <SelectTrigger data-testid="role-form-access">
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
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium text-slate-600">
                  Module Access ({form.modules.length}/{modules.length} selected)
                </label>
                {!editRole?.is_preset && (
                  <div className="flex gap-2">
                    <button onClick={selectAll} className="text-[11px] text-blue-600 hover:underline">All</button>
                    <button onClick={clearAll} className="text-[11px] text-slate-400 hover:underline">None</button>
                  </div>
                )}
              </div>
              <div className="border border-slate-200 rounded-lg p-2 max-h-52 overflow-y-auto space-y-1" data-testid="role-form-modules">
                {modules.map(mod => (
                  <label
                    key={mod.key}
                    className={`flex items-start gap-2.5 py-1.5 px-1 rounded cursor-pointer hover:bg-slate-50 ${editRole?.is_preset ? "cursor-default opacity-80" : ""}`}
                  >
                    <Checkbox
                      checked={form.modules.includes(mod.key)}
                      onCheckedChange={() => !editRole?.is_preset && toggleModule(mod.key)}
                      disabled={editRole?.is_preset}
                      data-testid={`role-module-${mod.key}`}
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-slate-700">{mod.name}</p>
                      <p className="text-[11px] text-slate-400">{mod.description}</p>
                    </div>
                  </label>
                ))}
              </div>
            </div>
            {!editRole?.is_preset && (
              <Button onClick={handleSave} disabled={saving} className="w-full" data-testid="role-form-save">
                {saving ? "Saving…" : editRole ? "Save Changes" : "Create Role"}
              </Button>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={!!confirmDelete} onOpenChange={(v) => !v && setConfirmDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Role</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete the <strong>{confirmDelete?.name}</strong> role?
              Users assigned this role will need to be reassigned.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700"
              onClick={handleDelete}
              data-testid="confirm-delete-role"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
