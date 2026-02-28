import { useState, useEffect } from "react";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { RefreshCw, ShieldCheck } from "lucide-react";

type UsageEntry = {
  current: number;
  limit: number | null;
  pct: number;
  warning: boolean;
  blocked: boolean;
};

type Snapshot = {
  period: string;
  license: Record<string, any>;
  usage: Record<string, UsageEntry>;
};

type Props = {
  tenantId: string;
  tenantName: string;
  onClose: () => void;
};

const LIMIT_FIELDS: { key: string; label: string; licenseKey: string }[] = [
  { key: "users", label: "Users (total)", licenseKey: "max_users" },
  { key: "storage_mb", label: "Storage (MB)", licenseKey: "max_storage_mb" },
  { key: "user_roles", label: "User Roles", licenseKey: "max_user_roles" },
  { key: "product_categories", label: "Product Categories", licenseKey: "max_product_categories" },
  { key: "product_terms", label: "Product Terms", licenseKey: "max_product_terms" },
  { key: "enquiries", label: "Enquiries", licenseKey: "max_enquiries" },
  { key: "resources", label: "Resources", licenseKey: "max_resources" },
  { key: "templates", label: "Templates", licenseKey: "max_templates" },
  { key: "email_templates", label: "Email Templates", licenseKey: "max_email_templates" },
  { key: "categories", label: "Resource Categories", licenseKey: "max_categories" },
  { key: "forms", label: "Forms", licenseKey: "max_forms" },
  { key: "references", label: "References", licenseKey: "max_references" },
  { key: "orders_this_month", label: "Orders / month", licenseKey: "max_orders_per_month" },
  { key: "customers_this_month", label: "Customers / month", licenseKey: "max_customers_per_month" },
  { key: "subscriptions_this_month", label: "Subscriptions / month", licenseKey: "max_subscriptions_per_month" },
];

export function TenantLicenseModal({ tenantId, tenantName, onClose }: Props) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [form, setForm] = useState<Record<string, string>>({});

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get(`/admin/tenants/${tenantId}/license`);
      setSnapshot(data);
      // Pre-fill form with existing limits (empty string = unlimited)
      const initial: Record<string, string> = {
        plan: data.license?.plan || "starter",
        warning_threshold_pct: String(data.license?.warning_threshold_pct ?? 80),
      };
      LIMIT_FIELDS.forEach(({ licenseKey }) => {
        const val = data.license?.[licenseKey];
        initial[licenseKey] = val !== null && val !== undefined ? String(val) : "";
      });
      setForm(initial);
    } catch {
      toast.error("Failed to load license data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [tenantId]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload: Record<string, any> = {
        plan: form.plan || "starter",
        warning_threshold_pct: parseInt(form.warning_threshold_pct) || 80,
      };
      LIMIT_FIELDS.forEach(({ licenseKey }) => {
        const v = form[licenseKey];
        payload[licenseKey] = v !== "" && v !== undefined ? parseInt(v) : null;
      });
      await api.put(`/admin/tenants/${tenantId}/license`, payload);
      toast.success("License updated");
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to save license");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    setResetting(true);
    try {
      await api.post(`/admin/tenants/${tenantId}/usage/reset`);
      toast.success("Monthly usage counters reset");
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to reset usage");
    } finally {
      setResetting(false);
    }
  };

  const pctColor = (pct: number, blocked: boolean) => {
    if (blocked) return "bg-red-500";
    if (pct >= 80) return "bg-amber-500";
    return "bg-emerald-500";
  };

  return (
    <Dialog open onOpenChange={() => onClose()}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-blue-600" />
            License — {tenantName}
          </DialogTitle>
        </DialogHeader>

        {loading ? (
          <div className="py-12 text-center text-sm text-slate-500">Loading…</div>
        ) : (
          <div className="space-y-6 mt-2">
            {/* Plan & Threshold */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-600">Plan Name</label>
                <Input
                  value={form.plan || ""}
                  onChange={e => setForm(p => ({ ...p, plan: e.target.value }))}
                  placeholder="starter"
                  data-testid="license-plan-input"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-600">Warning threshold (%)</label>
                <Input
                  type="number" min={1} max={100}
                  value={form.warning_threshold_pct || ""}
                  onChange={e => setForm(p => ({ ...p, warning_threshold_pct: e.target.value }))}
                  placeholder="80"
                  data-testid="license-threshold-input"
                />
              </div>
            </div>

            <p className="text-xs text-slate-400">Leave any limit blank for unlimited.</p>

            {/* Limits + live usage */}
            <div className="rounded-lg border border-slate-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-xs text-slate-500 uppercase">
                  <tr>
                    <th className="text-left px-3 py-2">Resource</th>
                    <th className="text-left px-3 py-2 w-28">Limit</th>
                    <th className="text-left px-3 py-2">Current Usage</th>
                  </tr>
                </thead>
                <tbody>
                  {LIMIT_FIELDS.map(({ key, label, licenseKey }) => {
                    const entry = snapshot?.usage?.[key];
                    const current = entry?.current ?? 0;
                    const limit = entry?.limit;
                    const pct = entry?.pct ?? 0;
                    const blocked = entry?.blocked ?? false;
                    return (
                      <tr key={key} className="border-t border-slate-100">
                        <td className="px-3 py-2 text-slate-700">{label}</td>
                        <td className="px-3 py-2">
                          <Input
                            type="number" min={0}
                            className="h-7 text-xs w-24"
                            value={form[licenseKey] ?? ""}
                            onChange={e => setForm(p => ({ ...p, [licenseKey]: e.target.value }))}
                            placeholder="∞"
                            data-testid={`limit-input-${licenseKey}`}
                          />
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-slate-600 w-16">
                              {current}{limit !== null && limit !== undefined ? `/${limit}` : ""}
                            </span>
                            {limit !== null && limit !== undefined && (
                              <div className="flex-1 max-w-24">
                                <div className="h-1.5 rounded-full bg-slate-200 overflow-hidden">
                                  <div
                                    className={`h-full rounded-full transition-all ${pctColor(pct, blocked)}`}
                                    style={{ width: `${Math.min(pct, 100)}%` }}
                                  />
                                </div>
                              </div>
                            )}
                            {blocked && <Badge variant="destructive" className="text-[10px] px-1 py-0">Blocked</Badge>}
                            {!blocked && entry?.warning && <Badge className="text-[10px] px-1 py-0 bg-amber-100 text-amber-700 hover:bg-amber-100">Warning</Badge>}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Period info */}
            {snapshot?.period && (
              <div className="flex items-center justify-between text-xs text-slate-500 bg-slate-50 rounded px-3 py-2">
                <span>Monthly period: <strong>{snapshot.period}</strong> (EST)</span>
                <Button size="sm" variant="outline" onClick={handleReset} disabled={resetting} data-testid="reset-usage-btn">
                  <RefreshCw className={`h-3.5 w-3.5 mr-1 ${resetting ? "animate-spin" : ""}`} />
                  Reset Monthly Counters
                </Button>
              </div>
            )}
          </div>
        )}

        <DialogFooter className="mt-4">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSave} disabled={saving || loading} data-testid="save-license-btn">
            {saving ? "Saving…" : "Save License"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
