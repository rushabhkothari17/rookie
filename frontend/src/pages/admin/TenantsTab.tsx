import { useState, useEffect } from "react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/components/ui/sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Plus, Building2, Users, Power, PowerOff, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";

type Tenant = {
  id: string;
  name: string;
  code: string;
  status: "active" | "inactive";
  created_at: string;
};

type TenantUser = {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
};

export function TenantsTab() {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedTenant, setExpandedTenant] = useState<string | null>(null);
  const [tenantUsers, setTenantUsers] = useState<Record<string, TenantUser[]>>({});

  // Create tenant dialog
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newTenant, setNewTenant] = useState({ name: "", code: "" });

  // Create partner admin dialog
  const [showCreateAdmin, setShowCreateAdmin] = useState<string | null>(null);
  const [newAdmin, setNewAdmin] = useState({ email: "", full_name: "", password: "", role: "partner_super_admin" });
  const [creatingAdmin, setCreatingAdmin] = useState(false);

  const load = async () => {
    try {
      const { data } = await api.get("/admin/tenants");
      setTenants(data.tenants || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

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
      await api.post("/admin/tenants", {
        name: newTenant.name,
        code: newTenant.code.toLowerCase().replace(/[^a-z0-9-]/g, "-"),
        status: "active",
      });
      toast.success("Partner organization created");
      setShowCreate(false);
      setNewTenant({ name: "", code: "" });
      load();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to create tenant");
    } finally {
      setCreating(false);
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
      await api.post(`/admin/tenants/${showCreateAdmin}/create-admin`, {
        tenant_id: showCreateAdmin,
        ...newAdmin,
      });
      toast.success("Admin user created");
      setShowCreateAdmin(null);
      setNewAdmin({ email: "", full_name: "", password: "", role: "partner_super_admin" });
      loadUsers(showCreateAdmin);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to create admin");
    } finally {
      setCreatingAdmin(false);
    }
  };

  if (loading) return <div className="p-4 text-slate-500 text-sm">Loading tenants…</div>;

  return (
    <div className="space-y-4" data-testid="tenants-tab">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Partner Organizations</h2>
          <p className="text-sm text-slate-500">{tenants.length} organization{tenants.length !== 1 ? "s" : ""}</p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={load} data-testid="refresh-tenants-btn">
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button size="sm" onClick={() => setShowCreate(true)} data-testid="create-tenant-btn">
            <Plus className="h-4 w-4 mr-1" />
            New Partner Org
          </Button>
        </div>
      </div>

      <div className="space-y-3">
        {tenants.map(tenant => (
          <div key={tenant.id} className="bg-white border border-slate-200 rounded-xl overflow-hidden" data-testid={`tenant-card-${tenant.code}`}>
            <div className="flex items-center gap-4 p-4">
              <div className="h-10 w-10 rounded-lg flex items-center justify-center" style={{ backgroundColor: "color-mix(in srgb, var(--aa-primary) 10%, transparent)" }}>
                <Building2 className="h-5 w-5" style={{ color: "var(--aa-primary)" }} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-slate-900">{tenant.name}</h3>
                  <Badge variant={tenant.status === "active" ? "default" : "secondary"} className="text-xs">
                    {tenant.status}
                  </Badge>
                  {tenant.code === "automate-accounts" && (
                    <Badge variant="outline" className="text-xs border-amber-300 text-amber-700">Platform Default</Badge>
                  )}
                </div>
                <p className="text-xs text-slate-400 font-mono mt-0.5">code: {tenant.code}</p>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setShowCreateAdmin(tenant.id)}
                  data-testid={`add-admin-${tenant.code}`}
                >
                  <Users className="h-3.5 w-3.5 mr-1" />
                  Add Admin
                </Button>
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
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent data-testid="create-tenant-dialog">
          <DialogHeader>
            <DialogTitle>New Partner Organization</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4 mt-2">
            <div className="space-y-2">
              <label className="text-sm font-medium">Organization Name</label>
              <Input placeholder="Acme Accounting" value={newTenant.name} onChange={e => setNewTenant(p => ({ ...p, name: e.target.value }))} required data-testid="new-tenant-name" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Partner Code (login slug)</label>
              <Input placeholder="acme-accounting" value={newTenant.code}
                onChange={e => setNewTenant(p => ({ ...p, code: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-") }))}
                required data-testid="new-tenant-code" />
              <p className="text-xs text-slate-400">Used by users at login. Unique, lowercase.</p>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
              <Button type="submit" disabled={creating} data-testid="confirm-create-tenant">
                {creating ? "Creating…" : "Create Organization"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Create Admin Dialog */}
      <Dialog open={!!showCreateAdmin} onOpenChange={() => setShowCreateAdmin(null)}>
        <DialogContent data-testid="create-admin-dialog">
          <DialogHeader>
            <DialogTitle>Add Admin User</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreateAdmin} className="space-y-4 mt-2">
            <div className="space-y-2">
              <label className="text-sm font-medium">Full Name</label>
              <Input placeholder="Jane Smith" value={newAdmin.full_name} onChange={e => setNewAdmin(p => ({ ...p, full_name: e.target.value }))} required data-testid="new-admin-name" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Email</label>
              <Input type="email" placeholder="admin@example.com" value={newAdmin.email} onChange={e => setNewAdmin(p => ({ ...p, email: e.target.value }))} required data-testid="new-admin-email" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Password</label>
              <Input type="password" placeholder="••••••••" value={newAdmin.password} onChange={e => setNewAdmin(p => ({ ...p, password: e.target.value }))} required data-testid="new-admin-password" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Role</label>
              <select value={newAdmin.role} onChange={e => setNewAdmin(p => ({ ...p, role: e.target.value }))}
                className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm" data-testid="new-admin-role">
                <option value="partner_super_admin">Partner Super Admin</option>
                <option value="partner_admin">Partner Admin</option>
                <option value="partner_staff">Partner Staff</option>
              </select>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setShowCreateAdmin(null)}>Cancel</Button>
              <Button type="submit" disabled={creatingAdmin} data-testid="confirm-create-admin">
                {creatingAdmin ? "Creating…" : "Create Admin"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
