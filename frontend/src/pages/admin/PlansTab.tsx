import { useState, useEffect } from "react";
import React from "react";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Plus, Pencil, Trash2, Power, PowerOff, ScrollText, ChevronDown, ChevronUp } from "lucide-react";

type Plan = {
  id: string;
  name: string;
  description?: string;
  is_active: boolean;
  is_public: boolean;
  warning_threshold_pct: number;
  tenant_count?: number;
  max_users: number | null;
  max_storage_mb: number | null;
  max_user_roles: number | null;
  max_product_categories: number | null;
  max_product_terms: number | null;
  max_enquiries: number | null;
  max_resources: number | null;
  max_templates: number | null;
  max_email_templates: number | null;
  max_categories: number | null;
  max_forms: number | null;
  max_references: number | null;
  max_orders_per_month: number | null;
  max_customers_per_month: number | null;
  max_subscriptions_per_month: number | null;
  created_at: string;
  updated_at: string;
};

type AuditLog = {
  id: string;
  entity_type: string;
  entity_id: string;
  action: string;
  actor: string;
  timestamp?: string;
  created_at?: string;
  details?: Record<string, any>;
};

const LIMIT_FIELDS = [
  { key: "max_users", label: "Users (total)" },
  { key: "max_storage_mb", label: "Storage (MB)" },
  { key: "max_user_roles", label: "User Roles" },
  { key: "max_product_categories", label: "Product Categories" },
  { key: "max_product_terms", label: "Product Terms" },
  { key: "max_enquiries", label: "Enquiries" },
  { key: "max_resources", label: "Resources" },
  { key: "max_templates", label: "Templates" },
  { key: "max_email_templates", label: "Email Templates" },
  { key: "max_categories", label: "Resource Categories" },
  { key: "max_forms", label: "Forms" },
  { key: "max_references", label: "References" },
  { key: "max_orders_per_month", label: "Orders / month" },
  { key: "max_customers_per_month", label: "Customers / month" },
  { key: "max_subscriptions_per_month", label: "Subscriptions / month" },
];

type FormState = Record<string, string>;

const defaultForm = (): FormState => ({
  name: "",
  description: "",
  warning_threshold_pct: "80",
  is_public: "false",
  ...Object.fromEntries(LIMIT_FIELDS.map(f => [f.key, ""])),
});

function planToForm(plan: Plan): FormState {
  return {
    name: plan.name,
    description: plan.description || "",
    warning_threshold_pct: String(plan.warning_threshold_pct ?? 80),
    is_public: plan.is_public ? "true" : "false",
    ...Object.fromEntries(
      LIMIT_FIELDS.map(f => [f.key, plan[f.key as keyof Plan] !== null && plan[f.key as keyof Plan] !== undefined ? String(plan[f.key as keyof Plan]) : ""])
    ),
  };
}

function formToPayload(form: FormState) {
  const payload: Record<string, any> = {
    name: form.name.trim(),
    description: form.description.trim(),
    warning_threshold_pct: parseInt(form.warning_threshold_pct) || 80,
    is_public: form.is_public === "true",
  };
  LIMIT_FIELDS.forEach(({ key }) => {
    payload[key] = form[key] !== "" ? parseInt(form[key]) : null;
  });
  return payload;
}

function PlanFormModal({
  plan,
  onClose,
  onSaved,
}: {
  plan: Plan | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = !!plan;
  const [form, setForm] = useState<FormState>(plan ? planToForm(plan) : defaultForm());
  const [saving, setSaving] = useState(false);

  const set = (key: string, val: string) => setForm(f => ({ ...f, [key]: val }));

  const handleSave = async () => {
    if (!form.name.trim()) { toast.error("Plan name is required"); return; }
    setSaving(true);
    try {
      if (isEdit) {
        const { data } = await api.put(`/admin/plans/${plan.id}`, formToPayload(form));
        toast.success(`Plan updated — ${data.tenants_propagated} org(s) updated`);
      } else {
        await api.post("/admin/plans", formToPayload(form));
        toast.success("Plan created");
      }
      onSaved();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? `Edit Plan — ${plan.name}` : "New Plan"}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 mt-2">
          {/* Read-only DB ID (edit mode only) */}
          {isEdit && (
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-500">Plan ID (read-only)</label>
              <div className="bg-slate-50 border border-slate-200 rounded px-3 py-2 text-xs font-mono text-slate-500 select-all" data-testid="plan-db-id">
                {plan.id}
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Plan Name *</label>
              <Input
                value={form.name}
                onChange={e => set("name", e.target.value)}
                placeholder="e.g. Starter, Growth, Enterprise"
                data-testid="plan-name-input"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Warning threshold (%)</label>
              <Input
                type="number" min={1} max={100}
                value={form.warning_threshold_pct}
                onChange={e => set("warning_threshold_pct", e.target.value)}
                placeholder="80"
                data-testid="plan-threshold-input"
              />
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-600">Description</label>
            <Textarea
              rows={2}
              value={form.description}
              onChange={e => set("description", e.target.value)}
              placeholder="Short description of this plan…"
              data-testid="plan-description-input"
            />
          </div>

          <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5">
            <input
              id="plan-is-public"
              type="checkbox"
              className="h-4 w-4 rounded border-slate-300"
              checked={form.is_public === "true"}
              onChange={e => set("is_public", e.target.checked ? "true" : "false")}
              data-testid="plan-is-public-checkbox"
            />
            <div>
              <label htmlFor="plan-is-public" className="text-xs font-medium text-slate-700 cursor-pointer">
                Visible to partners for self-service upgrade
              </label>
              <p className="text-xs text-slate-400">When enabled, partners can see and select this plan from their billing portal.</p>
            </div>
          </div>

          <p className="text-xs text-slate-400">Leave any limit blank for unlimited.</p>

          <div className="rounded-lg border border-slate-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-xs text-slate-500 uppercase">
                <tr>
                  <th className="text-left px-3 py-2">Resource</th>
                  <th className="text-left px-3 py-2 w-36">Limit (blank = unlimited)</th>
                </tr>
              </thead>
              <tbody>
                {LIMIT_FIELDS.map(({ key, label }) => (
                  <tr key={key} className="border-t border-slate-100">
                    <td className="px-3 py-2 text-slate-700">{label}</td>
                    <td className="px-3 py-2">
                      <Input
                        type="number" min={0}
                        className="h-7 text-xs w-28"
                        value={form[key] ?? ""}
                        onChange={e => set(key, e.target.value)}
                        placeholder="∞"
                        data-testid={`plan-limit-${key}`}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <DialogFooter className="mt-4">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSave} disabled={saving} data-testid="save-plan-btn">
            {saving ? "Saving…" : isEdit ? "Save Changes" : "Create Plan"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function PlanLogsDrawer({ plan, onClose }: { plan: Plan; onClose: () => void }) {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(`/admin/plans/${plan.id}/logs`)
      .then(({ data }) => setLogs(data.logs || []))
      .catch(() => toast.error("Failed to load logs"))
      .finally(() => setLoading(false));
  }, [plan.id]);

  const fmt = (iso: string) => {
    try { return new Date(iso).toLocaleString(); } catch { return iso; }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ScrollText className="h-4 w-4" />
            Logs — {plan.name}
          </DialogTitle>
        </DialogHeader>
        {loading ? (
          <p className="py-6 text-center text-sm text-slate-400">Loading…</p>
        ) : logs.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-400">No logs yet.</p>
        ) : (
          <div className="space-y-2 mt-2">
            {logs.map(log => (
              <div key={log.id || log.timestamp} className="border border-slate-100 rounded-lg p-3">
                <div className="flex items-center justify-between gap-2">
                  <Badge variant="outline" className="text-[10px]">{log.action}</Badge>
                  <span className="text-xs text-slate-400">{fmt(log.created_at || log.timestamp)}</span>
                </div>
                <p className="text-xs text-slate-600 mt-1">by <strong>{log.actor}</strong></p>
                {log.details && Object.keys(log.details).length > 0 && (
                  <pre className="text-[10px] text-slate-500 mt-1 bg-slate-50 p-1.5 rounded overflow-x-auto">
                    {JSON.stringify(log.details, null, 2)}
                  </pre>
                )}
              </div>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function PlansTab() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [editPlan, setEditPlan] = useState<Plan | null>(null);
  const [logsPlan, setLogsPlan] = useState<Plan | null>(null);
  const [deletePlan, setDeletePlan] = useState<Plan | null>(null);
  const [deleteError, setDeleteError] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/admin/plans");
      setPlans(data.plans || []);
    } catch {
      toast.error("Failed to load plans");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleToggleStatus = async (plan: Plan) => {
    try {
      const { data } = await api.patch(`/admin/plans/${plan.id}/status`);
      toast.success(data.is_active ? "Plan activated" : "Plan deactivated");
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to update status");
    }
  };

  const handleDelete = async () => {
    if (!deletePlan) return;
    setDeleteError("");
    try {
      await api.delete(`/admin/plans/${deletePlan.id}`);
      toast.success("Plan deleted");
      setDeletePlan(null);
      load();
    } catch (e: any) {
      setDeleteError(e.response?.data?.detail || "Failed to delete plan");
    }
  };

  const fmt = (iso: string) => {
    try { return new Date(iso).toLocaleDateString(); } catch { return iso; }
  };

  if (loading) return <div className="p-4 text-slate-500 text-sm">Loading plans…</div>;

  return (
    <div className="space-y-4" data-testid="plans-tab">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">License Plans</h2>
          <p className="text-sm text-slate-500">Define reusable resource limit templates for partner organisations.</p>
        </div>
        <Button onClick={() => setShowCreate(true)} data-testid="create-plan-btn">
          <Plus className="h-4 w-4 mr-1" /> New Plan
        </Button>
      </div>

      {plans.length === 0 ? (
        <div className="border border-dashed border-slate-200 rounded-xl p-12 text-center text-slate-400 text-sm">
          No plans yet. Create your first plan to start assigning limits to partner organisations.
        </div>
      ) : (
        <div className="rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full text-sm" data-testid="plans-table">
            <thead className="bg-slate-50 text-xs text-slate-500 uppercase">
              <tr>
                <th className="text-left px-4 py-3">Plan</th>
                <th className="text-left px-4 py-3">Orgs</th>
                <th className="text-left px-4 py-3">Status</th>
                <th className="text-left px-4 py-3">Created</th>
                <th className="text-right px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {plans.map(plan => (
                <React.Fragment key={plan.id}>
                  <tr className="border-t border-slate-100 hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-800">{plan.name}</div>
                      {plan.description && <div className="text-xs text-slate-400 mt-0.5">{plan.description}</div>}
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-slate-600">{plan.tenant_count ?? 0}</span>
                    </td>
                    <td className="px-4 py-3">
                      {plan.is_active ? (
                        <Badge className="bg-emerald-100 text-emerald-700 hover:bg-emerald-100 text-[11px]">Active</Badge>
                      ) : (
                        <Badge className="bg-slate-100 text-slate-500 hover:bg-slate-100 text-[11px]">Inactive</Badge>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-500 text-xs">{fmt(plan.created_at)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          size="sm" variant="ghost"
                          onClick={() => setExpanded(expanded === plan.id ? null : plan.id)}
                          data-testid={`expand-plan-${plan.id}`}
                          title="View limits"
                        >
                          {expanded === plan.id ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                        </Button>
                        <Button
                          size="sm" variant="ghost"
                          onClick={() => setLogsPlan(plan)}
                          data-testid={`logs-plan-${plan.id}`}
                          title="Audit logs"
                        >
                          <ScrollText className="h-4 w-4" />
                        </Button>
                        <Button
                          size="sm" variant="ghost"
                          onClick={() => setEditPlan(plan)}
                          data-testid={`edit-plan-${plan.id}`}
                          title="Edit plan"
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          size="sm" variant="ghost"
                          onClick={() => handleToggleStatus(plan)}
                          data-testid={`toggle-plan-${plan.id}`}
                          title={plan.is_active ? "Deactivate" : "Activate"}
                        >
                          {plan.is_active ? <PowerOff className="h-4 w-4 text-slate-400" /> : <Power className="h-4 w-4 text-emerald-500" />}
                        </Button>
                        <Button
                          size="sm" variant="ghost"
                          onClick={() => { setDeleteError(""); setDeletePlan(plan); }}
                          data-testid={`delete-plan-${plan.id}`}
                          title="Delete plan"
                          className="text-red-400 hover:text-red-600"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                  {/* Expandable limits row */}
                  {expanded === plan.id && (
                    <tr className="border-t border-slate-100 bg-slate-50">
                      <td colSpan={5} className="px-4 py-3">
                        <div className="grid grid-cols-3 gap-x-6 gap-y-1 text-xs">
                          {LIMIT_FIELDS.map(({ key, label }) => {
                            const val = plan[key as keyof Plan];
                            return (
                              <div key={key} className="flex justify-between">
                                <span className="text-slate-500">{label}</span>
                                <span className="font-medium text-slate-700">
                                  {val !== null && val !== undefined ? String(val) : "∞"}
                                </span>
                              </div>
                            );
                          })}
                        </div>
                        <div className="mt-2 text-[10px] font-mono text-slate-400">ID: {plan.id}</div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create Modal */}
      {showCreate && (
        <PlanFormModal plan={null} onClose={() => setShowCreate(false)} onSaved={() => { setShowCreate(false); load(); }} />
      )}

      {/* Edit Modal */}
      {editPlan && (
        <PlanFormModal plan={editPlan} onClose={() => setEditPlan(null)} onSaved={() => { setEditPlan(null); load(); }} />
      )}

      {/* Logs Modal */}
      {logsPlan && (
        <PlanLogsDrawer plan={logsPlan} onClose={() => setLogsPlan(null)} />
      )}

      {/* Delete Confirmation */}
      {deletePlan && (
        <AlertDialog open onOpenChange={() => setDeletePlan(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete "{deletePlan.name}"?</AlertDialogTitle>
              <AlertDialogDescription>
                This will permanently delete the plan. It cannot be undone.
                {(deletePlan.tenant_count ?? 0) > 0 && (
                  <span className="text-red-600 block mt-1">
                    This plan has {deletePlan.tenant_count} org(s) assigned. Deletion will be blocked.
                  </span>
                )}
              </AlertDialogDescription>
            </AlertDialogHeader>
            {deleteError && (
              <p className="text-sm text-red-600 px-1">{deleteError}</p>
            )}
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                className="bg-red-600 hover:bg-red-700"
                onClick={handleDelete}
                data-testid="confirm-delete-plan-btn"
              >
                Delete
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}
    </div>
  );
}
