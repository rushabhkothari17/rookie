import { useState, useEffect, useCallback, useRef } from "react";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  ArrowUp, ArrowDown, CheckCircle, Clock, Loader2, RefreshCw, Star, CreditCard,
  XCircle, AlertCircle, Zap, Tag, Gift,
} from "lucide-react";
import { UsageDashboard } from "./UsageDashboard";

interface Plan {
  id: string;
  name: string;
  description?: string;
  monthly_price: number;
  currency?: string;
  display_price?: number;
  display_currency?: string;
  max_users?: number;
  max_customers_per_month?: number;
  max_orders_per_month?: number;
  max_subscriptions_per_month?: number;
  is_default?: boolean;
}

interface Rate {
  id: string;
  module_key: string;
  label: string;
  price_per_record: number;
  currency: string;
}

interface PlanData {
  current_plan: Plan | null;
  license: any;
  subscription: any;
  available_plans: Plan[];
  base_currency: string;
  current_price_in_base: number;
}

interface CouponResult {
  valid: boolean;
  coupon_id: string;
  code: string;
  discount_type: string;
  discount_value: number;
  discount_amount: number;
  final_amount: number;
}

type PaymentStatus =
  | { type: "loading"; sessionId: string; flow: "ongoing" | "onetime" }
  | { type: "success"; planName: string; flow: "ongoing" | "onetime" }
  | { type: "cancelled"; flow: "ongoing" | "onetime" }
  | { type: "timeout"; flow: "ongoing" | "onetime" }
  | { type: "error"; flow: "ongoing" | "onetime" };

function LimitBadge({ label, value }: { label: string; value?: number }) {
  if (value == null) return null;
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 text-xs">
      {label}: {value < 0 ? "Unlimited" : value}
    </span>
  );
}

const PLAN_LIMIT_LABELS: Record<string, string> = {
  max_users: "Users",
  max_customers_per_month: "Customers/mo",
  max_orders_per_month: "Orders/mo",
  max_subscriptions_per_month: "Subscriptions/mo",
};

// ─── Coupon apply block ───────────────────────────────────────────────────────
function CouponBlock({
  couponCode,
  onCouponChange,
  couponResult,
  onApply,
  applying,
  baseAmount,
  currency,
}: {
  couponCode: string;
  onCouponChange: (v: string) => void;
  couponResult: CouponResult | null;
  onApply: () => void;
  applying: boolean;
  baseAmount: number;
  currency: string;
}) {
  return (
    <div className="space-y-2">
      <Label className="text-xs font-medium text-slate-600">Coupon Code (optional)</Label>
      <div className="flex gap-2">
        <Input
          placeholder="Enter coupon code"
          value={couponCode}
          onChange={e => onCouponChange(e.target.value.toUpperCase())}
          className="h-8 text-sm font-mono"
          data-testid="coupon-code-input"
        />
        <Button
          size="sm" variant="outline" onClick={onApply}
          disabled={applying || !couponCode.trim()}
          data-testid="apply-coupon-btn"
          className="shrink-0"
        >
          {applying ? <Loader2 size={12} className="animate-spin" /> : <Tag size={12} />}
          <span className="ml-1">{applying ? "Checking…" : "Apply"}</span>
        </Button>
      </div>
      {couponResult && (
        <div className="flex items-center justify-between rounded-md bg-emerald-50 border border-emerald-200 px-3 py-2 text-xs" data-testid="coupon-result">
          <span className="text-emerald-700 font-medium">
            <Gift size={11} className="inline mr-1" />
            {couponResult.discount_type === "percentage"
              ? `${couponResult.discount_value}% off`
              : `${currency} ${couponResult.discount_value.toFixed(2)} off`}
            {" "}— saves {currency} {couponResult.discount_amount.toFixed(2)}
          </span>
          <span className="font-semibold text-emerald-800">Final: {currency} {couponResult.final_amount.toFixed(2)}</span>
        </div>
      )}
    </div>
  );
}

// ─── Ongoing Upgrade Dialog ───────────────────────────────────────────────────
function OngoingUpgradeDialog({
  plan,
  currentPriceInBase,
  baseCurrency,
  onClose,
  onSuccess,
}: {
  plan: Plan;
  currentPriceInBase: number;
  baseCurrency: string;
  onClose: () => void;
  onSuccess: (result: any) => void;
}) {
  const displayPrice = plan.display_price ?? plan.monthly_price ?? 0;
  const currency = plan.display_currency || baseCurrency;
  const flatDiff = Math.max(0, displayPrice - currentPriceInBase);
  const [couponCode, setCouponCode] = useState("");
  const [couponResult, setCouponResult] = useState<CouponResult | null>(null);
  const [applying, setApplying] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleApplyCoupon = async () => {
    if (!couponCode.trim()) return;
    setApplying(true);
    setCouponResult(null);
    try {
      const { data } = await api.post("/partner/coupons/validate", {
        code: couponCode.trim(),
        upgrade_type: "ongoing",
        plan_id: plan.id,
        base_amount: flatDiff,
      });
      setCouponResult(data);
      toast.success("Coupon applied!");
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Invalid coupon");
    } finally {
      setApplying(false);
    }
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const { data } = await api.post("/partner/upgrade-plan-ongoing", {
        plan_id: plan.id,
        coupon_code: couponCode.trim(),
      });
      onSuccess(data);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Upgrade failed");
      setSubmitting(false);
    }
  };

  const finalAmount = couponResult ? couponResult.final_amount : flatDiff;

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-md" data-testid="ongoing-upgrade-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ArrowUp size={16} className="text-emerald-500" />
            Upgrade to {plan.name}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-1">
          <div className="rounded-lg border border-slate-100 bg-slate-50 p-4 space-y-1.5 text-sm">
            <div className="flex justify-between text-slate-600">
              <span>New monthly rate</span>
              <span className="font-medium">{currency} {displayPrice.toFixed(2)}/mo</span>
            </div>
            <div className="flex justify-between text-slate-600">
              <span>Due now (flat difference)</span>
              <span className="font-semibold text-slate-900">{currency} {flatDiff.toFixed(2)}</span>
            </div>
            <p className="text-xs text-slate-400 pt-1">
              Your subscription updates to the new rate from the next billing cycle.
            </p>
          </div>

          <CouponBlock
            couponCode={couponCode}
            onCouponChange={v => { setCouponCode(v); setCouponResult(null); }}
            couponResult={couponResult}
            onApply={handleApplyCoupon}
            applying={applying}
            baseAmount={flatDiff}
            currency={currency}
          />

          <div className="flex items-center justify-between rounded-lg bg-emerald-50 border border-emerald-200 px-4 py-3">
            <span className="text-sm font-medium text-emerald-800">Total due now</span>
            <span className="text-xl font-bold text-emerald-900">{currency} {finalAmount.toFixed(2)}</span>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button
            onClick={handleSubmit}
            disabled={submitting}
            data-testid="confirm-ongoing-upgrade-btn"
            className="bg-emerald-600 hover:bg-emerald-700"
          >
            {submitting
              ? <><Loader2 size={13} className="mr-1.5 animate-spin" />Processing…</>
              : <><CreditCard size={13} className="mr-1.5" />{finalAmount > 0 ? "Pay & Upgrade" : "Upgrade"}</>}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─── One-Time Upgrade Modal ───────────────────────────────────────────────────
function OneTimeUpgradeModal({
  rates,
  currency,
  nextBillingDate,
  onClose,
  onSuccess,
}: {
  rates: Rate[];
  currency: string;
  nextBillingDate?: string;
  onClose: () => void;
  onSuccess: (result: any) => void;
}) {
  const [quantities, setQuantities] = useState<Record<string, string>>({});
  const [couponCode, setCouponCode] = useState("");
  const [couponResult, setCouponResult] = useState<CouponResult | null>(null);
  const [applying, setApplying] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const subtotal = rates.reduce((sum, r) => {
    const qty = parseInt(quantities[r.module_key] || "0") || 0;
    return sum + qty * r.price_per_record;
  }, 0);
  const finalAmount = couponResult ? couponResult.final_amount : subtotal;

  const hasItems = Object.values(quantities).some(q => parseInt(q || "0") > 0);

  const handleApplyCoupon = async () => {
    if (!couponCode.trim() || subtotal <= 0) return;
    setApplying(true);
    setCouponResult(null);
    try {
      const { data } = await api.post("/partner/coupons/validate", {
        code: couponCode.trim(),
        upgrade_type: "one_time",
        base_amount: subtotal,
      });
      setCouponResult(data);
      toast.success("Coupon applied!");
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Invalid coupon");
    } finally {
      setApplying(false);
    }
  };

  const handleSubmit = async () => {
    const upgrades = rates
      .filter(r => parseInt(quantities[r.module_key] || "0") > 0)
      .map(r => ({ module_key: r.module_key, quantity: parseInt(quantities[r.module_key]) }));

    if (upgrades.length === 0) {
      toast.error("Please enter at least one quantity");
      return;
    }
    setSubmitting(true);
    try {
      const { data } = await api.post("/partner/one-time-upgrade", {
        upgrades,
        coupon_code: couponCode.trim(),
      });
      onSuccess(data);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Purchase failed");
      setSubmitting(false);
    }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto" data-testid="one-time-upgrade-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Zap size={16} className="text-amber-500" />
            Buy Extra Limits (This Billing Cycle)
          </DialogTitle>
          {nextBillingDate && (
            <p className="text-xs text-slate-400 mt-0.5">
              These limits reset on your next renewal: {nextBillingDate.slice(0, 10)}
            </p>
          )}
        </DialogHeader>

        <div className="space-y-4 py-1">
          <div className="rounded-lg border border-slate-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-xs text-slate-500 uppercase">
                <tr>
                  <th className="text-left px-3 py-2">Module</th>
                  <th className="text-right px-3 py-2">Price/Unit</th>
                  <th className="text-right px-3 py-2 w-28">Quantity</th>
                  <th className="text-right px-3 py-2">Total</th>
                </tr>
              </thead>
              <tbody>
                {rates.map(r => {
                  const qty = parseInt(quantities[r.module_key] || "0") || 0;
                  const lineTotal = qty * r.price_per_record;
                  return (
                    <tr key={r.module_key} className="border-t border-slate-100">
                      <td className="px-3 py-2.5 text-slate-700 font-medium">{r.label}</td>
                      <td className="px-3 py-2.5 text-right text-slate-500 text-xs">{r.currency} {r.price_per_record.toFixed(2)}</td>
                      <td className="px-3 py-2.5 text-right">
                        <Input
                          type="number" min={0}
                          className="h-7 text-xs w-24 text-right ml-auto"
                          placeholder="0"
                          value={quantities[r.module_key] || ""}
                          onChange={e => {
                            setQuantities(q => ({ ...q, [r.module_key]: e.target.value }));
                            setCouponResult(null);
                          }}
                          data-testid={`qty-${r.module_key}`}
                        />
                      </td>
                      <td className="px-3 py-2.5 text-right font-medium text-slate-800">
                        {qty > 0 ? `${r.currency} ${lineTotal.toFixed(2)}` : <span className="text-slate-300">—</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {hasItems && (
            <>
              <CouponBlock
                couponCode={couponCode}
                onCouponChange={v => { setCouponCode(v); setCouponResult(null); }}
                couponResult={couponResult}
                onApply={handleApplyCoupon}
                applying={applying}
                baseAmount={subtotal}
                currency={currency}
              />
              <div className="flex items-center justify-between rounded-lg bg-amber-50 border border-amber-200 px-4 py-3">
                <span className="text-sm font-medium text-amber-800">Total</span>
                <span className="text-xl font-bold text-amber-900">{currency} {finalAmount.toFixed(2)}</span>
              </div>
            </>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button
            onClick={handleSubmit}
            disabled={submitting || !hasItems}
            data-testid="confirm-one-time-upgrade-btn"
            className="bg-amber-600 hover:bg-amber-700"
          >
            {submitting
              ? <><Loader2 size={13} className="mr-1.5 animate-spin" />Processing…</>
              : <><Zap size={13} className="mr-1.5" />{finalAmount > 0 ? "Pay & Activate" : "Activate"}</>}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─── Upgrade Plans Modal ─────────────────────────────────────────────────────
function UpgradePlansModal({
  plans,
  currentPriceInBase,
  baseCurrency,
  onSelect,
  onClose,
}: {
  plans: Plan[];
  currentPriceInBase: number;
  baseCurrency: string;
  onSelect: (plan: Plan) => void;
  onClose: () => void;
}) {
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-xl max-h-[80vh] overflow-y-auto" data-testid="upgrade-plans-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ArrowUp size={16} className="text-emerald-500" />
            Choose an Upgrade Plan
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">
          {plans.map(plan => {
            const displayPrice = plan.display_price ?? plan.monthly_price ?? 0;
            const currency = plan.display_currency || baseCurrency;
            const diff = Math.max(0, displayPrice - currentPriceInBase);
            return (
              <div key={plan.id} className="rounded-xl border border-slate-200 p-4 flex items-center justify-between gap-4 hover:border-emerald-300 hover:bg-emerald-50/30 transition-colors" data-testid={`upgrade-option-${plan.id}`}>
                <div className="flex-1">
                  <p className="font-semibold text-slate-900">{plan.name}</p>
                  {plan.description && <p className="text-xs text-slate-500 mt-0.5">{plan.description}</p>}
                  <p className="text-xs text-slate-400 mt-1">
                    {currency} {displayPrice.toFixed(2)}/mo &nbsp;·&nbsp; Due now: {currency} {diff.toFixed(2)}
                  </p>
                </div>
                <Button
                  size="sm"
                  className="bg-emerald-600 hover:bg-emerald-700 shrink-0"
                  onClick={() => { onClose(); onSelect(plan); }}
                  data-testid={`select-upgrade-${plan.id}`}
                >
                  <ArrowUp size={13} className="mr-1.5" />Select
                </Button>
              </div>
            );
          })}
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────
export function PlanBillingTab() {
  const [data, setData] = useState<PlanData | null>(null);
  const [rates, setRates] = useState<Rate[]>([]);
  const [loading, setLoading] = useState(true);
  const [paymentStatus, setPaymentStatus] = useState<PaymentStatus | null>(null);
  const [ongoingDialog, setOngoingDialog] = useState<Plan | null>(null);
  const [showOneTimeModal, setShowOneTimeModal] = useState(false);
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);
  const [showDowngradeDialog, setShowDowngradeDialog] = useState(false);
  const [selectedDowngradePlan, setSelectedDowngradePlan] = useState("");
  const [downgradeMessage, setDowngradeMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [planRes, ratesRes] = await Promise.all([
        api.get("/partner/my-plan"),
        api.get("/partner/one-time-rates").catch(() => ({ data: { rates: [] } })),
      ]);
      setData(planRes.data);
      setRates(ratesRes.data.rates || []);
    } catch {
      toast.error("Failed to load plan information");
    } finally {
      setLoading(false);
    }
  }, []);

  const pollStatus = useCallback((sessionId: string, flow: "ongoing" | "onetime") => {
    let attempts = 0;
    const endpoint = flow === "ongoing"
      ? `/partner/upgrade-plan-status?session_id=${sessionId}`
      : `/partner/one-time-upgrade-status?session_id=${sessionId}`;
    pollRef.current = setInterval(async () => {
      attempts++;
      try {
        const r = await api.get(endpoint);
        const isPaid = flow === "ongoing" ? r.data.status === "paid" : r.data.status === "active";
        if (isPaid) {
          clearInterval(pollRef.current!);
          setPaymentStatus({ type: "success", planName: r.data.plan_name || "Limits activated", flow });
          load();
        } else if (attempts >= 12) {
          clearInterval(pollRef.current!);
          setPaymentStatus({ type: "timeout", flow });
        }
      } catch {
        if (attempts >= 12) {
          clearInterval(pollRef.current!);
          setPaymentStatus({ type: "error", flow });
        }
      }
    }, 2500);
  }, [load]);

  useEffect(() => {
    load();
    const params = new URLSearchParams(window.location.search);
    const upgradeStatus = params.get("upgrade_status");
    const otStatus = params.get("onetimeupgrade_status");
    const sessionId = params.get("session_id");

    if (upgradeStatus === "success" && sessionId) {
      setPaymentStatus({ type: "loading", sessionId, flow: "ongoing" });
      window.history.replaceState({}, "", "/admin?tab=plan-billing");
      pollStatus(sessionId, "ongoing");
    } else if (upgradeStatus === "cancelled") {
      setPaymentStatus({ type: "cancelled", flow: "ongoing" });
      window.history.replaceState({}, "", "/admin?tab=plan-billing");
    } else if (otStatus === "success" && sessionId) {
      setPaymentStatus({ type: "loading", sessionId, flow: "onetime" });
      window.history.replaceState({}, "", "/admin?tab=plan-billing");
      pollStatus(sessionId, "onetime");
    } else if (otStatus === "cancelled") {
      setPaymentStatus({ type: "cancelled", flow: "onetime" });
      window.history.replaceState({}, "", "/admin?tab=plan-billing");
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [load, pollStatus]);

  const handleOngoingUpgradeSuccess = (result: any) => {
    if (result.checkout_url) {
      toast.info("Redirecting to secure payment…");
      window.location.href = result.checkout_url;
      return;
    }
    toast.success(result.message || "Plan upgraded successfully");
    setOngoingDialog(null);
    load();
  };

  const handleOneTimeUpgradeSuccess = (result: any) => {
    if (result.checkout_url) {
      toast.info("Redirecting to secure payment…");
      window.location.href = result.checkout_url;
      return;
    }
    toast.success(result.message || "Extra limits activated");
    setShowOneTimeModal(false);
    load();
  };

  const handleDowngradeSubmit = async () => {
    if (!selectedDowngradePlan) { toast.error("Please select a plan"); return; }
    setSubmitting(true);
    try {
      await api.post("/partner/submissions", {
        type: "plan_downgrade",
        requested_plan_id: selectedDowngradePlan,
        message: downgradeMessage,
      });
      toast.success("Downgrade request submitted — your admin will review it.");
      setShowDowngradeDialog(false);
      setSelectedDowngradePlan(""); setDowngradeMessage("");
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
  const license = data?.license || {};
  const baseCurrency = data?.base_currency || sub?.currency || current?.currency || "GBP";
  const currentPriceInBase = data?.current_price_in_base ?? (current?.monthly_price ?? 0);
  const upgrades = available.filter(p => (p.display_price ?? p.monthly_price ?? 0) > currentPriceInBase);
  const downgrades = available.filter(p => (p.display_price ?? p.monthly_price ?? 0) < currentPriceInBase);
  const boosts: Record<string, number> = license.one_time_boosts || {};
  const boostsExpire: string | null = license.one_time_boosts_expire_at || null;

  const bannerStyle = (status: PaymentStatus) => {
    if (status.type === "success") return "bg-emerald-50 border-emerald-200 text-emerald-800";
    if (status.type === "cancelled") return "bg-amber-50 border-amber-200 text-amber-800";
    if (status.type === "loading") return "bg-blue-50 border-blue-200 text-blue-800";
    return "bg-red-50 border-red-200 text-red-800";
  };

  const bannerMsg = (status: PaymentStatus) => {
    const isOngoing = status.flow === "ongoing";
    if (status.type === "loading") return isOngoing ? "Confirming plan upgrade payment with Stripe…" : "Confirming limit purchase with Stripe…";
    if (status.type === "success") return isOngoing ? `Plan upgraded to ${status.planName}.` : "Extra limits activated successfully.";
    if (status.type === "cancelled") return isOngoing ? "Payment cancelled — your plan has not changed." : "Payment cancelled — no limits were added.";
    if (status.type === "timeout") return "Payment confirmation is taking longer than expected. Refresh in a few minutes.";
    return "Could not confirm payment status. Contact support if changes were not applied.";
  };

  return (
    <div className="space-y-8" data-testid="plan-billing-tab">

      {/* Payment status banner */}
      {paymentStatus && (
        <div className={`flex items-start gap-3 rounded-xl p-4 border ${bannerStyle(paymentStatus)}`} data-testid="payment-status-banner">
          {paymentStatus.type === "loading" && <Loader2 size={18} className="animate-spin mt-0.5 shrink-0" />}
          {paymentStatus.type === "success" && <CheckCircle size={18} className="mt-0.5 shrink-0" />}
          {paymentStatus.type === "cancelled" && <XCircle size={18} className="mt-0.5 shrink-0" />}
          {(paymentStatus.type === "timeout" || paymentStatus.type === "error") && <AlertCircle size={18} className="mt-0.5 shrink-0" />}
          <div className="flex-1 text-sm">{bannerMsg(paymentStatus)}</div>
          <button onClick={() => setPaymentStatus(null)} className="text-current opacity-60 hover:opacity-100 text-lg leading-none">&times;</button>
        </div>
      )}

      {/* Current Plan */}
      <div>
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-3">Current Plan</h2>
        {current ? (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="current-plan-card">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="text-lg font-bold text-slate-900" data-testid="current-plan-name">{current.name}</h3>
                  {current.is_default && (
                    <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 text-xs font-medium">Free Trial</span>
                  )}
                  {sub && (
                    <Badge variant={sub.status === "active" ? "default" : sub.status === "unpaid" ? "destructive" : "secondary"} data-testid="current-sub-status">
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

                {/* Active one-time boosts */}
                {Object.keys(boosts).length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2 items-center">
                    <span className="text-xs text-amber-700 font-medium flex items-center gap-1">
                      <Zap size={11} />Extra limits active{boostsExpire ? ` until ${boostsExpire.slice(0, 10)}` : ""}:
                    </span>
                    {Object.entries(boosts).map(([key, qty]) => {
                      const rate = rates.find(r => r.module_key === key);
                      return (
                        <span key={key} className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 text-xs font-medium" data-testid={`boost-badge-${key}`}>
                          +{qty} {rate?.label || key}
                        </span>
                      );
                    })}
                  </div>
                )}
              </div>
              <div className="text-right shrink-0">
                <p className="text-3xl font-bold text-slate-900" data-testid="current-plan-price">
                  {baseCurrency} {currentPriceInBase.toFixed(2)}
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

      {/* Action Buttons */}
      {(upgrades.length > 0 || rates.length > 0 || downgrades.length > 0) && (
        <div className="flex flex-wrap gap-3" data-testid="plan-action-buttons">
          {upgrades.length > 0 && (
            <Button
              onClick={() => setShowUpgradeModal(true)}
              className="bg-emerald-600 hover:bg-emerald-700"
              data-testid="open-upgrade-plan-btn"
            >
              <ArrowUp size={14} className="mr-1.5" />Upgrade Plan
            </Button>
          )}
          {rates.length > 0 && (
            <Button
              variant="outline"
              onClick={() => setShowOneTimeModal(true)}
              className="border-amber-300 text-amber-700 hover:bg-amber-50"
              data-testid="open-one-time-modal-btn"
            >
              <Zap size={14} className="mr-1.5" />Buy Extra Limits
            </Button>
          )}
          {downgrades.length > 0 && (
            <Button
              variant="outline"
              onClick={() => setShowDowngradeDialog(true)}
              className="text-slate-500 border-slate-200"
              data-testid="request-downgrade-btn"
            >
              <ArrowDown size={13} className="mr-1.5" />Request Downgrade
            </Button>
          )}
        </div>
      )}

      {/* Usage */}
      <div className="border-t border-slate-200 pt-6">
        <UsageDashboard />
      </div>

      {/* Ongoing Upgrade Dialog */}
      {ongoingDialog && (
        <OngoingUpgradeDialog
          plan={ongoingDialog}
          currentPrice={currentPrice}
          currency={currency}
          onClose={() => setOngoingDialog(null)}
          onSuccess={handleOngoingUpgradeSuccess}
        />
      )}

      {/* One-Time Upgrade Modal */}
      {showOneTimeModal && (
        <OneTimeUpgradeModal
          rates={rates}
          currency={currency}
          nextBillingDate={sub?.next_billing_date}
          onClose={() => setShowOneTimeModal(false)}
          onSuccess={handleOneTimeUpgradeSuccess}
        />
      )}

      {/* Downgrade Dialog */}
      <Dialog open={showDowngradeDialog} onOpenChange={setShowDowngradeDialog}>
        <DialogContent data-testid="downgrade-dialog">
          <DialogHeader><DialogTitle>Request Plan Downgrade</DialogTitle></DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label>Downgrade to</Label>
              <Select value={selectedDowngradePlan} onValueChange={setSelectedDowngradePlan}>
                <SelectTrigger className="mt-1" data-testid="downgrade-plan-select">
                  <SelectValue placeholder="Select a plan…" />
                </SelectTrigger>
                <SelectContent>
                  {downgrades.map(p => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name} — {p.currency || currency} {(p.monthly_price ?? 0).toFixed(2)}/mo
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Reason (optional)</Label>
              <Textarea
                className="mt-1" rows={3}
                placeholder="Tell us why you'd like to downgrade…"
                value={downgradeMessage}
                onChange={e => setDowngradeMessage(e.target.value)}
                data-testid="downgrade-message-input"
              />
            </div>
            <p className="text-xs text-slate-400">Effective date: 1st of the following month once approved.</p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDowngradeDialog(false)}>Cancel</Button>
            <Button onClick={handleDowngradeSubmit} disabled={submitting} data-testid="downgrade-submit-btn">
              {submitting ? <><Loader2 size={13} className="mr-1.5 animate-spin" />Submitting…</> : "Submit Request"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
