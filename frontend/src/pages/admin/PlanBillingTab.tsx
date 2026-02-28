import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ArrowUp, ArrowDown, CheckCircle, Clock, Loader2, RefreshCw, Star } from "lucide-react";

interface Plan {
  id: string;
  name: string;
  description?: string;
  monthly_price: number;
  currency?: string;
  max_users?: number;
  max_customers?: number;
  max_products?: number;
  max_subscriptions?: number;
  is_default?: boolean;
}

interface PlanData {
  current_plan: Plan | null;
  license: any;
  subscription: any;
  available_plans: Plan[];
}

const PLAN_LIMIT_LABELS: Record<string, string> = {
  max_users: "Users",
  max_customers: "Customers",
  max_products: "Products",
  max_subscriptions: "Subscriptions",
};

function LimitBadge({ label, value }: { label: string; value?: number }) {
  if (value == null) return null;
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 text-xs">
      {label}: {value < 0 ? "Unlimited" : value}
    </span>
  );
}

export function PlanBillingTab() {
  const [data, setData] = useState<PlanData | null>(null);
  const [loading, setLoading] = useState(true);
  const [upgrading, setUpgrading] = useState<string | null>(null);
  const [showDowngradeDialog, setShowDowngradeDialog] = useState(false);
  const [selectedDowngradePlan, setSelectedDowngradePlan] = useState("");
  const [downgradeMessage, setDowngradeMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get("/partner/my-plan");
      setData(r.data);
    } catch {
      toast.error("Failed to load plan information");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleUpgrade = async (planId: string) => {
    setUpgrading(planId);
    try {
      const r = await api.post("/partner/upgrade-plan", { plan_id: planId });
      toast.success(r.data.message || "Plan upgraded successfully");
      if (r.data.prorata_amount > 0) {
        toast.info(`Pro-rata charge: ${data?.subscription?.currency || "GBP"} ${r.data.prorata_amount.toFixed(2)} (${r.data.orders_created?.[0] || "order created"})`);
      }
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Upgrade failed");
    } finally {
      setUpgrading(null);
    }
  };

  const handleDowngradeSubmit = async () => {
    if (!selectedDowngradePlan) {
      toast.error("Please select a plan to downgrade to");
      return;
    }
    setSubmitting(true);
    try {
      await api.post("/partner/submissions", {
        type: "plan_downgrade",
        requested_plan_id: selectedDowngradePlan,
        message: downgradeMessage,
      });
      toast.success("Downgrade request submitted. Your platform admin will review it.");
      setShowDowngradeDialog(false);
      setSelectedDowngradePlan("");
      setDowngradeMessage("");
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to submit request");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="animate-spin text-slate-400" size={24} />
      </div>
    );
  }

  const current = data?.current_plan;
  const available = data?.available_plans || [];
  const sub = data?.subscription;
  const currentPrice = current?.monthly_price ?? 0;

  // Split available into upgrades (higher price) and downgrades (lower price)
  const upgrades = available.filter(p => (p.monthly_price ?? 0) > currentPrice);
  const downgrades = available.filter(p => (p.monthly_price ?? 0) < currentPrice);

  return (
    <div className="space-y-8" data-testid="plan-billing-tab">
      {/* Current Plan Card */}
      <div>
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-3">Current Plan</h2>
        {current ? (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="current-plan-card">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-lg font-bold text-slate-900" data-testid="current-plan-name">{current.name}</h3>
                  {current.is_default && (
                    <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 text-xs font-medium">Free Trial</span>
                  )}
                  {sub && (
                    <Badge variant={sub.status === "active" ? "default" : "secondary"} data-testid="current-sub-status">
                      {sub.status}
                    </Badge>
                  )}
                </div>
                {current.description && <p className="text-sm text-slate-500 mt-1">{current.description}</p>}
                <div className="flex flex-wrap gap-2 mt-3">
                  {Object.entries(PLAN_LIMIT_LABELS).map(([key, label]) => (
                    <LimitBadge key={key} label={label} value={(current as any)[key]} />
                  ))}
                </div>
              </div>
              <div className="text-right shrink-0">
                <p className="text-3xl font-bold text-slate-900" data-testid="current-plan-price">
                  {current.currency || "GBP"} {currentPrice.toFixed(2)}
                </p>
                <p className="text-xs text-slate-400 mt-0.5">per month</p>
                {sub?.next_billing_date && (
                  <p className="text-xs text-slate-500 mt-1.5">
                    Next billing: {sub.next_billing_date.slice(0, 10)}
                  </p>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-200 p-6 text-center text-sm text-slate-400" data-testid="no-plan-card">
            No plan assigned. Contact your platform administrator.
          </div>
        )}
      </div>

      {/* Available Upgrades */}
      {upgrades.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-2">
            <ArrowUp size={14} className="text-emerald-500" /> Available Upgrades
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {upgrades.map(plan => {
              const diff = (plan.monthly_price ?? 0) - currentPrice;
              return (
                <div key={plan.id} className="rounded-2xl border border-emerald-100 bg-emerald-50/40 p-5 flex flex-col gap-3" data-testid={`upgrade-plan-card-${plan.id}`}>
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="font-semibold text-slate-900">{plan.name}</p>
                      {plan.description && <p className="text-xs text-slate-500 mt-0.5">{plan.description}</p>}
                    </div>
                    <div className="text-right">
                      <p className="font-bold text-slate-900 text-lg">{plan.currency || "GBP"} {(plan.monthly_price ?? 0).toFixed(2)}</p>
                      <p className="text-xs text-emerald-600">+{(plan.currency || "GBP")} {diff.toFixed(2)}/mo</p>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(PLAN_LIMIT_LABELS).map(([key, label]) => (
                      <LimitBadge key={key} label={label} value={(plan as any)[key]} />
                    ))}
                  </div>
                  <Button
                    size="sm"
                    className="w-full mt-auto"
                    disabled={upgrading === plan.id}
                    onClick={() => handleUpgrade(plan.id)}
                    data-testid={`upgrade-btn-${plan.id}`}
                  >
                    {upgrading === plan.id ? (
                      <><Loader2 size={13} className="mr-1.5 animate-spin" />Upgrading...</>
                    ) : (
                      <><ArrowUp size={13} className="mr-1.5" />Upgrade Now</>
                    )}
                  </Button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Downgrade Request Section */}
      {downgrades.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-2">
            <ArrowDown size={14} className="text-amber-500" /> Request a Downgrade
          </h2>
          <div className="rounded-2xl border border-amber-100 bg-amber-50/30 p-5">
            <p className="text-sm text-slate-600 mb-4">
              Downgrade requests are reviewed by your platform administrator. Approved downgrades take effect on the next renewal date.
            </p>
            <Button
              variant="outline"
              onClick={() => setShowDowngradeDialog(true)}
              data-testid="request-downgrade-btn"
              className="border-amber-300 text-amber-700 hover:bg-amber-50"
            >
              <ArrowDown size={14} className="mr-1.5" />Request Downgrade
            </Button>
          </div>
        </div>
      )}

      {available.length === 0 && !loading && (
        <div className="rounded-2xl border border-dashed border-slate-200 p-8 text-center" data-testid="no-available-plans">
          <Star size={24} className="text-slate-300 mx-auto mb-2" />
          <p className="text-sm text-slate-500">You are on the best available plan.</p>
        </div>
      )}

      {/* Downgrade Dialog */}
      <Dialog open={showDowngradeDialog} onOpenChange={setShowDowngradeDialog}>
        <DialogContent data-testid="downgrade-dialog">
          <DialogHeader>
            <DialogTitle>Request Plan Downgrade</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label>Downgrade to</Label>
              <Select value={selectedDowngradePlan} onValueChange={setSelectedDowngradePlan} data-testid="downgrade-plan-select">
                <SelectTrigger className="mt-1">
                  <SelectValue placeholder="Select a plan..." />
                </SelectTrigger>
                <SelectContent>
                  {downgrades.map(p => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name} — {p.currency || "GBP"} {(p.monthly_price ?? 0).toFixed(2)}/mo
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Reason (optional)</Label>
              <Textarea
                className="mt-1"
                placeholder="Tell us why you'd like to downgrade..."
                value={downgradeMessage}
                onChange={e => setDowngradeMessage(e.target.value)}
                data-testid="downgrade-message-input"
                rows={3}
              />
            </div>
            <p className="text-xs text-slate-400">
              Effective date will be the 1st of the following month once approved.
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDowngradeDialog(false)}>Cancel</Button>
            <Button onClick={handleDowngradeSubmit} disabled={submitting} data-testid="downgrade-submit-btn">
              {submitting ? <><Loader2 size={13} className="mr-1.5 animate-spin" />Submitting...</> : "Submit Request"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
