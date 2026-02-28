import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { ChevronDown, ChevronRight, Plus, Trash2, RefreshCw, Send, Eye, Copy, RotateCcw, Zap, CheckCircle2, XCircle, Clock, AlertTriangle } from "lucide-react";
import { FieldTip } from "./shared/FieldTip";

// ─── Types ────────────────────────────────────────────────────────────────────

interface EventField { [fieldKey: string]: string }
interface EventInfo { label: string; category: string; fields: EventField }
interface EventCatalog { [eventKey: string]: EventInfo }

interface Subscription { event: string; fields: string[] }
interface Webhook {
  id: string; name: string; url: string; is_active: boolean;
  subscriptions: Subscription[]; created_at: string; updated_at: string;
}
interface Delivery {
  id: string; event: string; status: "success" | "failed" | "pending";
  attempts: number; response_status: number | null; response_body: string | null;
  error: string | null; created_at: string; last_attempt_at: string | null; delivered_at: string | null;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const CATEGORY_COLORS: Record<string, string> = {
  Orders: "bg-blue-100 text-blue-800",
  Subscriptions: "bg-purple-100 text-purple-800",
  Customers: "bg-green-100 text-green-800",
  Payments: "bg-amber-100 text-amber-800",
  "Quote Requests": "bg-slate-100 text-slate-700",
};

function StatusIcon({ status }: { status: string }) {
  if (status === "success") return <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />;
  if (status === "failed") return <XCircle className="h-3.5 w-3.5 text-red-500" />;
  return <Clock className="h-3.5 w-3.5 text-amber-500 animate-pulse" />;
}

// ─── Field Picker (per event) ─────────────────────────────────────────────────

function FieldPicker({ event, info, fields, onChange }: {
  event: string; info: EventInfo; fields: string[]; onChange: (f: string[]) => void;
}) {
  const allFields = Object.keys(info.fields);
  const allSelected = allFields.every(f => fields.includes(f));

  const toggle = (f: string) => {
    onChange(fields.includes(f) ? fields.filter(x => x !== f) : [...fields, f]);
  };

  return (
    <div className="mt-1 pl-7 pb-2">
      <div className="flex items-center gap-3 mb-2">
        <button
          type="button"
          onClick={() => onChange(allSelected ? [] : allFields)}
          className="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
        >
          {allSelected ? "Deselect all" : "Select all"}
        </button>
        <span className="text-xs text-slate-400">{fields.length}/{allFields.length} fields</span>
      </div>
      <div className="grid grid-cols-2 gap-1">
        {allFields.map(f => (
          <label key={f} className="flex items-center gap-1.5 cursor-pointer group">
            <Checkbox
              checked={fields.includes(f)}
              onCheckedChange={() => toggle(f)}
              className="h-3.5 w-3.5"
              data-testid={`field-check-${event}-${f}`}
            />
            <span className="text-xs text-slate-600 group-hover:text-slate-900 truncate" title={info.fields[f]}>
              {info.fields[f]}
            </span>
          </label>
        ))}
      </div>
    </div>
  );
}

// ─── Event Subscription Builder ───────────────────────────────────────────────

function EventBuilder({ catalog, subscriptions, onChange }: {
  catalog: EventCatalog; subscriptions: Subscription[]; onChange: (s: Subscription[]) => void;
}) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const subMap = Object.fromEntries(subscriptions.map(s => [s.event, s.fields]));

  const categories = Array.from(new Set(Object.values(catalog).map(v => v.category)));

  const toggleEvent = (event: string) => {
    if (event in subMap) {
      onChange(subscriptions.filter(s => s.event !== event));
    } else {
      const allFields = Object.keys(catalog[event].fields);
      onChange([...subscriptions, { event, fields: allFields }]);
      setExpanded(prev => new Set([...Array.from(prev), event]));
    }
  };

  const updateFields = (event: string, fields: string[]) => {
    onChange(subscriptions.map(s => s.event === event ? { ...s, fields } : s));
  };

  const toggleExpand = (event: string) => {
    setExpanded(prev => {
      const next = new Set(Array.from(prev));
      next.has(event) ? next.delete(event) : next.add(event);
      return next;
    });
  };

  return (
    <div className="space-y-4" data-testid="event-builder">
      {categories.map(cat => {
        const events = Object.entries(catalog).filter(([, v]) => v.category === cat);
        return (
          <div key={cat}>
            <p className={`text-[10px] font-semibold uppercase tracking-wider px-2 py-1 rounded mb-1 inline-block ${CATEGORY_COLORS[cat] || "bg-slate-100 text-slate-600"}`}>
              {cat}
            </p>
            <div className="space-y-1 border border-slate-100 rounded-lg overflow-hidden">
              {events.map(([eventKey, info]) => {
                const isSubscribed = eventKey in subMap;
                const isExpanded = expanded.has(eventKey);
                return (
                  <div key={eventKey} className={`border-b last:border-b-0 border-slate-100 ${isSubscribed ? "bg-indigo-50/40" : "bg-white"}`}>
                    <div className="flex items-center gap-2 px-3 py-2">
                      <Checkbox
                        checked={isSubscribed}
                        onCheckedChange={() => toggleEvent(eventKey)}
                        data-testid={`event-check-${eventKey}`}
                      />
                      <span className="flex-1 text-sm font-medium text-slate-800">{info.label}</span>
                      <span className="text-[10px] font-mono text-slate-400">{eventKey}</span>
                      {isSubscribed && (
                        <button
                          type="button"
                          onClick={() => toggleExpand(eventKey)}
                          className="text-indigo-500 hover:text-indigo-700 p-0.5"
                          data-testid={`expand-fields-${eventKey}`}
                        >
                          {isExpanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                        </button>
                      )}
                    </div>
                    {isSubscribed && isExpanded && (
                      <FieldPicker
                        event={eventKey}
                        info={info}
                        fields={subMap[eventKey] || []}
                        onChange={fields => updateFields(eventKey, fields)}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── Create / Edit Modal ──────────────────────────────────────────────────────

function WebhookModal({ open, onClose, catalog, existing, onSaved }: {
  open: boolean; onClose: () => void; catalog: EventCatalog;
  existing?: Webhook | null; onSaved: () => void;
}) {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [secret, setSecret] = useState("");
  const [showSecret, setShowSecret] = useState(false);
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [saving, setSaving] = useState(false);
  const isEdit = !!existing;

  useEffect(() => {
    if (existing) {
      setName(existing.name);
      setUrl(existing.url);
      setSecret("");
      setSubscriptions(existing.subscriptions || []);
    } else {
      setName(""); setUrl(""); setSecret(""); setSubscriptions([]);
    }
  }, [existing, open]);

  const handleSave = async () => {
    if (!url.trim()) return toast.error("URL is required");
    if (!url.startsWith("http")) return toast.error("URL must start with http:// or https://");
    if (subscriptions.length === 0) return toast.error("Subscribe to at least one event");
    const hasEmpty = subscriptions.some(s => s.fields.length === 0);
    if (hasEmpty) return toast.error("Each subscribed event must have at least one field selected");

    setSaving(true);
    try {
      const payload: any = { name, url: url.trim(), subscriptions };
      if (secret.trim()) payload.secret = secret.trim();
      if (isEdit) {
        await api.put(`/admin/webhooks/${existing!.id}`, payload);
        toast.success("Webhook updated");
      } else {
        const { data } = await api.post("/admin/webhooks", payload);
        toast.success("Webhook created!");
        if (data.secret) {
          await navigator.clipboard.writeText(data.secret).catch(() => {});
          toast.info("Secret copied to clipboard — save it now, it won't be shown again.");
        }
      }
      onSaved();
      onClose();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to save webhook");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={v => !v && onClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="webhook-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-indigo-500" />
            {isEdit ? "Edit Webhook" : "Create Webhook"}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-5 pt-2">
          {/* Name + URL */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-semibold text-slate-600 mb-1 block">Name</label>
              <Input
                value={name} onChange={e => setName(e.target.value)}
                placeholder="e.g. CRM Sync" data-testid="webhook-name-input"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-600 mb-1 block">Endpoint URL *</label>
              <Input
                value={url} onChange={e => setUrl(e.target.value)}
                placeholder="https://your-server.com/webhook" data-testid="webhook-url-input"
              />
            </div>
          </div>

          {/* Secret */}
          <div>
            <label className="text-xs font-semibold text-slate-600 mb-1 block">
              {isEdit ? "New Secret (leave blank to keep current)" : "Signing Secret (auto-generated if blank)"}
              <FieldTip tip="A secret string used to sign every webhook payload. Your server should verify the X-Webhook-Signature header matches to confirm the request is genuine and not tampered with." side="right" />
            </label>
            <div className="flex gap-2">
              <Input
                type={showSecret ? "text" : "password"}
                value={secret} onChange={e => setSecret(e.target.value)}
                placeholder={isEdit ? "Leave blank to keep current" : "Auto-generated whsec_..."}
                className="font-mono text-xs" data-testid="webhook-secret-input"
              />
              <Button variant="outline" size="sm" onClick={() => setShowSecret(p => !p)} type="button">
                <Eye className="h-3.5 w-3.5" />
              </Button>
            </div>
            <p className="text-[11px] text-slate-400 mt-1">
              Used to verify the <code className="bg-slate-100 px-1 rounded">X-Webhook-Signature: sha256=...</code> header on your server.
            </p>
          </div>

          {/* Events */}
          <div>
            <label className="text-xs font-semibold text-slate-600 mb-2 block">
              Event Subscriptions * <span className="font-normal text-slate-400">({subscriptions.length} selected)</span>
            </label>
            <EventBuilder catalog={catalog} subscriptions={subscriptions} onChange={setSubscriptions} />
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-2 pt-2 border-t">
            <Button variant="outline" onClick={onClose} type="button">Cancel</Button>
            <Button onClick={handleSave} disabled={saving} data-testid="webhook-save-btn">
              {saving ? "Saving..." : isEdit ? "Save Changes" : "Create Webhook"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ─── Delivery Stats Dashboard ─────────────────────────────────────────────────

function DeliveryStatsDashboard() {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/admin/webhooks/delivery-stats");
      setStats(data);
    } catch {
      // Ignore
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="grid grid-cols-4 gap-3 animate-pulse">
        {[1, 2, 3, 4].map(i => (
          <div key={i} className="bg-slate-100 rounded-xl h-20" />
        ))}
      </div>
    );
  }

  if (!stats) return null;

  return (
    <div className="space-y-4">
      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <p className="text-xs text-slate-500 font-medium">Total Deliveries</p>
          <p className="text-2xl font-bold text-slate-800 mt-1">{stats.total_deliveries}</p>
        </div>
        <div className="bg-white border border-emerald-200 rounded-xl p-4">
          <p className="text-xs text-emerald-600 font-medium">Successful</p>
          <p className="text-2xl font-bold text-emerald-700 mt-1">{stats.success_count}</p>
        </div>
        <div className="bg-white border border-red-200 rounded-xl p-4">
          <p className="text-xs text-red-600 font-medium">Failed</p>
          <p className="text-2xl font-bold text-red-700 mt-1">{stats.failed_count}</p>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <p className="text-xs text-slate-500 font-medium">Success Rate</p>
          <p className="text-2xl font-bold text-slate-800 mt-1">{stats.success_rate}%</p>
        </div>
      </div>

      {/* Recent Failures */}
      {stats.recent_failures && stats.recent_failures.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="h-4 w-4 text-red-500" />
            <p className="text-sm font-semibold text-red-700">Recent Failures</p>
          </div>
          <div className="space-y-2">
            {stats.recent_failures.slice(0, 5).map((f: any) => (
              <div key={f.id} className="flex items-center justify-between text-xs bg-white rounded-lg px-3 py-2 border border-red-100">
                <div className="flex items-center gap-3">
                  <span className="font-medium text-slate-700">{f.webhook_name}</span>
                  <span className="font-mono text-slate-500">{f.event}</span>
                </div>
                <div className="flex items-center gap-2">
                  {f.response_status && (
                    <span className="bg-red-100 text-red-700 px-1.5 py-0.5 rounded font-mono">{f.response_status}</span>
                  )}
                  <span className="text-slate-400">{new Date(f.created_at).toLocaleString()}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Delivery Logs Panel ──────────────────────────────────────────────────────

function DeliveryLogs({ webhook, onClose }: { webhook: Webhook; onClose: () => void }) {
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<Delivery | null>(null);
  const [detail, setDetail] = useState<any>(null);
  const [replaying, setReplaying] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get(`/admin/webhooks/${webhook.id}/deliveries`, { params: { page, per_page: 25 } });
      setDeliveries(data.deliveries);
      setTotal(data.total);
    } finally { setLoading(false); }
  }, [webhook.id, page]);

  useEffect(() => { load(); }, [load]);

  const viewDetail = async (d: Delivery) => {
    setSelected(d);
    try {
      const { data } = await api.get(`/admin/webhooks/${webhook.id}/deliveries/${d.id}`);
      setDetail(data);
    } catch { setDetail(null); }
  };

  const replayDelivery = async (deliveryId: string) => {
    setReplaying(deliveryId);
    try {
      const { data } = await api.post(`/admin/webhooks/${webhook.id}/deliveries/${deliveryId}/replay`);
      if (data.success) {
        toast.success(`Replay successful (HTTP ${data.status_code})`);
      } else {
        toast.error(data.message || "Replay failed");
      }
      load(); // Refresh the list
      if (selected?.id === deliveryId) {
        viewDetail({ ...selected, status: data.success ? "success" : "failed" } as Delivery);
      }
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Replay failed");
    } finally {
      setReplaying(null);
    }
  };

  return (
    <Dialog open onOpenChange={v => !v && onClose()}>
      <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto" data-testid="delivery-logs-panel">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <RefreshCw className="h-4 w-4 text-indigo-500" />
            Delivery Logs — <span className="font-normal text-slate-600">{webhook.name}</span>
          </DialogTitle>
        </DialogHeader>

        {selected && detail ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Button variant="ghost" size="sm" onClick={() => { setSelected(null); setDetail(null); }}>
                ← Back to list
              </Button>
              {detail.status === "failed" && (
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={() => replayDelivery(detail.id)}
                  disabled={replaying === detail.id}
                  data-testid="replay-delivery-btn"
                >
                  <RotateCcw className={`h-3.5 w-3.5 mr-1 ${replaying === detail.id ? "animate-spin" : ""}`} />
                  {replaying === detail.id ? "Replaying..." : "Replay Delivery"}
                </Button>
              )}
            </div>
            <div className="grid grid-cols-3 gap-2 text-xs">
              <div className="bg-slate-50 rounded p-2">
                <p className="text-slate-400 font-medium mb-0.5">Event</p>
                <p className="font-mono font-semibold">{detail.event}</p>
              </div>
              <div className="bg-slate-50 rounded p-2">
                <p className="text-slate-400 font-medium mb-0.5">Status</p>
                <div className="flex items-center gap-1"><StatusIcon status={detail.status} /><span className="capitalize">{detail.status}</span></div>
              </div>
              <div className="bg-slate-50 rounded p-2">
                <p className="text-slate-400 font-medium mb-0.5">Response</p>
                <p className="font-mono">{detail.response_status ?? "—"}</p>
              </div>
            </div>
            {detail.error && (
              <div className="bg-red-50 border border-red-200 rounded p-2 text-xs text-red-700 font-mono">{detail.error}</div>
            )}
            <div>
              <p className="text-xs font-semibold text-slate-500 mb-1">Payload Sent</p>
              <pre className="bg-slate-900 text-green-300 text-[11px] rounded p-3 overflow-auto max-h-48 font-mono">
                {JSON.stringify(detail.payload, null, 2)}
              </pre>
            </div>
            {detail.response_body && (
              <div>
                <p className="text-xs font-semibold text-slate-500 mb-1">Response Body</p>
                <pre className="bg-slate-100 text-slate-700 text-[11px] rounded p-3 overflow-auto max-h-24 font-mono">{detail.response_body}</pre>
              </div>
            )}
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs text-slate-500">{total} total deliveries</p>
              <Button variant="ghost" size="sm" onClick={load} data-testid="refresh-deliveries-btn">
                <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
              </Button>
            </div>
            {deliveries.length === 0 ? (
              <div className="text-center py-12 text-slate-400">
                <Clock className="h-8 w-8 mx-auto mb-2 opacity-30" />
                <p className="text-sm">No deliveries yet</p>
                <p className="text-xs mt-1">Deliveries appear here when events are triggered</p>
              </div>
            ) : (
              <div className="divide-y divide-slate-100">
                {deliveries.map(d => (
                  <div
                    key={d.id}
                    className="flex items-center gap-3 py-2 px-1 hover:bg-slate-50 cursor-pointer rounded transition-colors"
                    onClick={() => viewDetail(d)}
                    data-testid={`delivery-row-${d.id}`}
                  >
                    <StatusIcon status={d.status} />
                    <span className="text-xs font-mono text-slate-600 flex-1 truncate">{d.event}</span>
                    <span className="text-xs text-slate-400">attempt {d.attempts}</span>
                    <span className={`text-xs font-mono px-1.5 py-0.5 rounded ${d.response_status && d.response_status >= 200 && d.response_status < 300 ? "bg-green-100 text-green-700" : d.response_status ? "bg-red-100 text-red-700" : "bg-slate-100 text-slate-500"}`}>
                      {d.response_status ?? "—"}
                    </span>
                    {d.status === "failed" && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 w-6 p-0"
                        onClick={(e) => { e.stopPropagation(); replayDelivery(d.id); }}
                        disabled={replaying === d.id}
                        title="Replay this delivery"
                      >
                        <RotateCcw className={`h-3 w-3 ${replaying === d.id ? "animate-spin" : ""}`} />
                      </Button>
                    )}
                    <span className="text-[10px] text-slate-300 w-32 text-right truncate">{d.created_at?.slice(0, 16).replace("T", " ")}</span>
                    <ChevronRight className="h-3 w-3 text-slate-300" />
                  </div>
                ))}
              </div>
            )}
            {total > 25 && (
              <div className="flex justify-between items-center pt-2">
                <Button variant="ghost" size="sm" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>Prev</Button>
                <span className="text-xs text-slate-400">Page {page}</span>
                <Button variant="ghost" size="sm" onClick={() => setPage(p => p + 1)} disabled={deliveries.length < 25}>Next</Button>
              </div>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ─── Webhook Card ──────────────────────────────────────────────────────────────

function WebhookCard({ webhook, catalog, onEdit, onDelete, onViewLogs, onRefresh }: {
  webhook: Webhook; catalog: EventCatalog;
  onEdit: () => void; onDelete: () => void; onViewLogs: () => void; onRefresh: () => void;
}) {
  const [testing, setTesting] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [rotatingSecret, setRotatingSecret] = useState(false);
  const [newSecret, setNewSecret] = useState<string | null>(null);

  const toggleActive = async () => {
    setToggling(true);
    try {
      await api.put(`/admin/webhooks/${webhook.id}`, { is_active: !webhook.is_active });
      toast.success(`Webhook ${webhook.is_active ? "paused" : "activated"}`);
      onRefresh();
    } finally { setToggling(false); }
  };

  const testWebhook = async () => {
    const testEvent = webhook.subscriptions[0]?.event || "order.created";
    setTesting(true);
    try {
      const { data } = await api.post(`/admin/webhooks/${webhook.id}/test`, { event: testEvent });
      if (data.success) {
        toast.success(`Test delivery succeeded (HTTP ${data.status_code})`);
      } else {
        toast.error(`Test failed: ${data.status_code ? `HTTP ${data.status_code}` : data.body}`);
      }
    } catch { toast.error("Test delivery failed"); }
    finally { setTesting(false); }
  };

  const rotateSecret = async () => {
    if (!confirm("Rotate the signing secret? You'll need to update your server.")) return;
    setRotatingSecret(true);
    try {
      const { data } = await api.post(`/admin/webhooks/${webhook.id}/rotate-secret`);
      setNewSecret(data.secret);
      await navigator.clipboard.writeText(data.secret).catch(() => {});
      toast.success("Secret rotated and copied to clipboard");
    } finally { setRotatingSecret(false); }
  };

  const deleteWebhook = async () => {
    if (!confirm(`Delete webhook "${webhook.name}"? This cannot be undone.`)) return;
    onDelete();
  };

  const categories = Array.from(new Set(webhook.subscriptions.map(s => catalog[s.event]?.category).filter(Boolean)));

  return (
    <div className={`border rounded-xl p-4 space-y-3 transition-all ${webhook.is_active ? "border-slate-200 bg-white shadow-sm" : "border-slate-100 bg-slate-50 opacity-70"}`}
      data-testid={`webhook-card-${webhook.id}`}>
      {/* Header */}
      <div className="flex items-start gap-3">
        <div className={`h-8 w-8 rounded-lg flex items-center justify-center shrink-0 ${webhook.is_active ? "bg-indigo-100" : "bg-slate-200"}`}>
          <Zap className={`h-4 w-4 ${webhook.is_active ? "text-indigo-600" : "text-slate-400"}`} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-semibold text-slate-800 text-sm" data-testid="webhook-name">{webhook.name}</h3>
            <Badge variant={webhook.is_active ? "default" : "secondary"} className="text-[10px] px-1.5 py-0">
              {webhook.is_active ? "Active" : "Paused"}
            </Badge>
          </div>
          <p className="text-xs text-slate-400 font-mono truncate mt-0.5" title={webhook.url}>{webhook.url}</p>
        </div>
        <div
          onClick={() => !toggling && toggleActive()}
          className={`relative inline-flex h-5 w-9 cursor-pointer items-center rounded-full transition-colors ${webhook.is_active ? "bg-indigo-500" : "bg-slate-300"} ${toggling ? "opacity-50 pointer-events-none" : ""}`}
          data-testid="webhook-toggle"
          role="switch"
          aria-checked={webhook.is_active}
        >
          <span className={`block h-4 w-4 rounded-full bg-white shadow transition-transform ${webhook.is_active ? "translate-x-4" : "translate-x-0.5"}`} />
        </div>
      </div>

      {/* Event + category badges */}
      <div className="flex flex-wrap gap-1">
        {categories.map(cat => (
          <span key={cat} className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${CATEGORY_COLORS[cat] || "bg-slate-100 text-slate-500"}`}>{cat}</span>
        ))}
        <span className="text-[10px] text-slate-400 px-1 py-0.5">{webhook.subscriptions.length} event{webhook.subscriptions.length !== 1 ? "s" : ""}</span>
      </div>

      {/* Subscribed events summary */}
      <div className="flex flex-wrap gap-1">
        {webhook.subscriptions.map(s => (
          <span key={s.event} className="text-[10px] font-mono bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">
            {s.event} <span className="text-slate-400">({s.fields.length}f)</span>
          </span>
        ))}
      </div>

      {/* Rotated secret display */}
      {newSecret && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-2 flex items-center gap-2">
          <AlertTriangle className="h-3.5 w-3.5 text-amber-500 shrink-0" />
          <code className="text-[11px] font-mono text-amber-800 flex-1 truncate">{newSecret}</code>
          <button onClick={() => navigator.clipboard.writeText(newSecret)} className="text-amber-600 hover:text-amber-800">
            <Copy className="h-3.5 w-3.5" />
          </button>
          <button onClick={() => setNewSecret(null)} className="text-amber-400 hover:text-amber-600 text-xs">✕</button>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-1.5 pt-1 border-t border-slate-100">
        <Button variant="outline" size="sm" onClick={onEdit} className="text-xs" data-testid="webhook-edit-btn">Edit</Button>
        <Button variant="outline" size="sm" onClick={testWebhook} disabled={testing} className="text-xs gap-1" data-testid="webhook-test-btn">
          <Send className={`h-3 w-3 ${testing ? "animate-pulse" : ""}`} /> Test
        </Button>
        <Button variant="outline" size="sm" onClick={onViewLogs} className="text-xs gap-1" data-testid="webhook-logs-btn">
          <Eye className="h-3 w-3" /> Logs
        </Button>
        <Button variant="ghost" size="sm" onClick={rotateSecret} disabled={rotatingSecret} className="text-xs gap-1 text-slate-400 hover:text-slate-700">
          <RotateCcw className={`h-3 w-3 ${rotatingSecret ? "animate-spin" : ""}`} />
        </Button>
        <Button variant="ghost" size="sm" onClick={deleteWebhook} className="text-xs text-red-400 hover:text-red-700 hover:bg-red-50 ml-auto" data-testid="webhook-delete-btn">
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
}

// ─── Main Tab ─────────────────────────────────────────────────────────────────

export function WebhooksTab() {
  const [webhooks, setWebhooks] = useState<Webhook[]>([]);
  const [catalog, setCatalog] = useState<EventCatalog>({});
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [editWebhook, setEditWebhook] = useState<Webhook | null>(null);
  const [logsWebhook, setLogsWebhook] = useState<Webhook | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [wRes, eRes] = await Promise.all([
        api.get("/admin/webhooks"),
        api.get("/admin/webhooks/events"),
      ]);
      setWebhooks(wRes.data.webhooks);
      setCatalog(eRes.data.events);
    } catch { toast.error("Failed to load webhooks"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const deleteWebhook = async (id: string) => {
    try {
      await api.delete(`/admin/webhooks/${id}`);
      toast.success("Webhook deleted");
      load();
    } catch { toast.error("Failed to delete webhook"); }
  };

  return (
    <div className="space-y-6" data-testid="webhooks-tab">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-slate-800">Webhooks</h2>
          <p className="text-sm text-slate-500 mt-0.5">Send real-time event data to your own endpoints.</p>
        </div>
        <Button onClick={() => setShowCreate(true)} className="gap-2" data-testid="create-webhook-btn">
          <Plus className="h-4 w-4" /> New Webhook
        </Button>
      </div>

      {/* Delivery Status Dashboard */}
      <DeliveryStatsDashboard />

      {/* How it works */}
      <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-4 text-sm text-indigo-800">
        <div className="flex gap-2">
          <Zap className="h-4 w-4 shrink-0 mt-0.5 text-indigo-500" />
          <div>
            <p className="font-semibold mb-1">How webhooks work</p>
            <p className="text-xs text-indigo-600 leading-relaxed">
              When an event occurs, we send an HTTPS POST to your URL with a JSON payload.
              Verify authenticity using the <code className="bg-indigo-100 px-1 rounded font-mono">X-Webhook-Signature: sha256=...</code> header (HMAC-SHA256).
              Respond with HTTP 2xx within 15 seconds. Failed deliveries are retried up to 3 times (5s → 30s → 2min).
            </p>
          </div>
        </div>
      </div>

      {/* Webhook list */}
      {loading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {[1, 2].map(i => (
            <div key={i} className="border border-slate-200 rounded-xl p-4 animate-pulse space-y-2">
              <div className="h-4 bg-slate-200 rounded w-1/2" />
              <div className="h-3 bg-slate-100 rounded w-3/4" />
              <div className="h-3 bg-slate-100 rounded w-1/4" />
            </div>
          ))}
        </div>
      ) : webhooks.length === 0 ? (
        <div className="border-2 border-dashed border-slate-200 rounded-2xl text-center py-16 px-8">
          <Zap className="h-10 w-10 mx-auto text-slate-300 mb-3" />
          <h3 className="text-base font-semibold text-slate-700 mb-1">No webhooks yet</h3>
          <p className="text-sm text-slate-400 mb-5 max-w-xs mx-auto">
            Connect your platform with any external service by creating a webhook endpoint.
          </p>
          <Button onClick={() => setShowCreate(true)} className="gap-2" data-testid="create-first-webhook-btn">
            <Plus className="h-4 w-4" /> Create First Webhook
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {webhooks.map(wh => (
            <WebhookCard
              key={wh.id}
              webhook={wh}
              catalog={catalog}
              onEdit={() => setEditWebhook(wh)}
              onDelete={() => deleteWebhook(wh.id)}
              onViewLogs={() => setLogsWebhook(wh)}
              onRefresh={load}
            />
          ))}
        </div>
      )}

      {/* Modals */}
      {Object.keys(catalog).length > 0 && (
        <>
          <WebhookModal
            open={showCreate}
            onClose={() => setShowCreate(false)}
            catalog={catalog}
            onSaved={load}
          />
          {editWebhook && (
            <WebhookModal
              open={!!editWebhook}
              onClose={() => setEditWebhook(null)}
              catalog={catalog}
              existing={editWebhook}
              onSaved={load}
            />
          )}
        </>
      )}
      {logsWebhook && (
        <DeliveryLogs webhook={logsWebhook} onClose={() => setLogsWebhook(null)} />
      )}
    </div>
  );
}
