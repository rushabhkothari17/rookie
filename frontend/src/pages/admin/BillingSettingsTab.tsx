import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, Save, Info } from "lucide-react";

export function BillingSettingsTab() {
  const [settings, setSettings] = useState({ overdue_grace_days: 7, overdue_warning_days: 3 });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get("/admin/platform-billing-settings");
      setSettings(r.data);
    } catch {
      toast.error("Failed to load billing settings");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSave = async () => {
    if (settings.overdue_warning_days >= settings.overdue_grace_days) {
      toast.error("Warning days must be less than grace days");
      return;
    }
    setSaving(true);
    try {
      const r = await api.put("/admin/platform-billing-settings", settings);
      setSettings(r.data);
      toast.success("Billing settings saved");
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="flex justify-center py-16"><Loader2 className="animate-spin text-slate-400" size={22} /></div>;
  }

  return (
    <div className="space-y-6 max-w-lg" data-testid="billing-settings-tab">
      <div>
        <h2 className="text-base font-semibold text-slate-900">Billing Settings</h2>
        <p className="text-sm text-slate-500 mt-1">Configure automatic overdue subscription cancellation for partner organisations.</p>
      </div>

      {/* Overdue Cancellation */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-5">
        <div className="flex items-start gap-2.5">
          <Info size={15} className="text-slate-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-slate-800">Overdue Payment Cancellation</p>
            <p className="text-xs text-slate-500 mt-0.5">
              When a partner's invoice remains unpaid, a warning email is sent after
              <strong> (grace days − warning days)</strong> days.
              If still unpaid after <strong>grace days</strong>, the subscription is automatically cancelled
              and the partner is reverted to the Free Trial plan.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Grace Days</Label>
            <p className="text-xs text-slate-400 mb-1.5">Days before auto-cancellation</p>
            <Input
              type="number" min={1} max={90}
              value={settings.overdue_grace_days}
              onChange={e => setSettings(s => ({ ...s, overdue_grace_days: parseInt(e.target.value) || 7 }))}
              data-testid="overdue-grace-days-input"
            />
          </div>
          <div>
            <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Warning Days Before</Label>
            <p className="text-xs text-slate-400 mb-1.5">Days before grace to send warning</p>
            <Input
              type="number" min={0} max={60}
              value={settings.overdue_warning_days}
              onChange={e => setSettings(s => ({ ...s, overdue_warning_days: parseInt(e.target.value) || 3 }))}
              data-testid="overdue-warning-days-input"
            />
          </div>
        </div>

        <div className="rounded-lg bg-slate-50 border border-slate-100 px-4 py-3 text-xs text-slate-600 space-y-1">
          <p>
            Warning email sent: day <strong>{Math.max(0, settings.overdue_grace_days - settings.overdue_warning_days)}</strong> of overdue
          </p>
          <p>
            Auto-cancellation: day <strong>{settings.overdue_grace_days}</strong> of overdue
          </p>
        </div>
      </div>

      <Button onClick={handleSave} disabled={saving} data-testid="billing-settings-save-btn">
        {saving ? <Loader2 size={14} className="mr-1.5 animate-spin" /> : <Save size={14} className="mr-1.5" />}
        Save Settings
      </Button>
    </div>
  );
}
