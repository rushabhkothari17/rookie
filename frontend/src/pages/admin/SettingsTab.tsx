import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";

export function ReminderNotificationSection() {
  const [reminderDays, setReminderDays] = useState<string>("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/admin/tenants/my").then(r => {
      const val = r.data.tenant?.default_reminder_days;
      setReminderDays(val != null ? String(val) : "");
    }).catch(() => {});
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      const days = reminderDays !== "" ? parseInt(reminderDays) : null;
      await api.put("/admin/tenant-settings", { default_reminder_days: days ?? -1 });
      toast.success("Notification settings saved");
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to save");
    } finally { setSaving(false); }
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4" data-testid="reminder-notification-section">
      <h3 className="text-sm font-semibold text-slate-900">Subscription Notifications</h3>
      <p className="text-xs text-slate-400">
        Set a default number of days before renewal to send reminder emails. Individual subscriptions can override this setting.
      </p>
      <div className="space-y-1">
        <div className="flex items-center gap-1.5">
          <label className="text-xs font-medium text-slate-700">Default Renewal Reminder (days before)</label>
          <span className="group relative cursor-help">
            <span className="text-slate-400 text-xs border border-slate-300 rounded-full w-4 h-4 inline-flex items-center justify-center">?</span>
            <span className="absolute left-5 top-0 z-10 hidden group-hover:block w-72 rounded bg-slate-800 text-white text-xs px-2.5 py-2 shadow-lg">
              Number of days before renewal to send a reminder email. Leave blank to disable renewal notifications for all subscriptions in this organisation (unless overridden at the subscription level).
            </span>
          </span>
        </div>
        <Input
          type="number"
          min={1}
          max={365}
          placeholder="blank = no reminders"
          value={reminderDays}
          onChange={e => setReminderDays(e.target.value)}
          className="w-40"
          data-testid="default-reminder-days-input"
        />
      </div>
      <Button size="sm" onClick={save} disabled={saving} data-testid="save-reminder-days-btn">
        {saving ? "Saving…" : "Save"}
      </Button>
    </div>
  );
}
