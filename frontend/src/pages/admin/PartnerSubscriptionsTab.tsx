import { useState, useEffect, useCallback, useMemo } from "react";
import { AdminPageHeader } from "./shared/AdminPageHeader";
import { RequiredLabel } from "@/components/shared/RequiredLabel";
import { StickyTableScroll } from "@/components/shared/StickyTableScroll";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { AuditLogDialog } from "@/components/AuditLogDialog";
import { Bell, Plus, Pencil, XCircle, ExternalLink, ScrollText, RefreshCw, Copy } from "lucide-react";
import { SearchableSelect } from "@/components/ui/searchable-select";
import { ISO_CURRENCIES } from "@/lib/constants";
import { useSupportedCurrencies } from "@/hooks/useSupportedCurrencies";
import { ColHeader } from "@/components/shared/ColHeader";

// Maps common country names to ISO 2-letter codes (for tax table matching)
const COUNTRY_NAME_TO_ISO: Record<string, string> = {
  "canada": "CA", "united kingdom": "GB", "england": "GB", "scotland": "GB",
  "wales": "GB", "northern ireland": "GB", "united states": "US",
  "united states of america": "US", "usa": "US", "australia": "AU",
  "new zealand": "NZ", "ireland": "IE", "germany": "DE", "france": "FR",
  "spain": "ES", "italy": "IT", "netherlands": "NL", "belgium": "BE",
  "sweden": "SE", "norway": "NO", "denmark": "DK", "finland": "FI",
  "switzerland": "CH", "austria": "AT", "portugal": "PT", "poland": "PL",
  "india": "IN", "japan": "JP", "china": "CN", "south africa": "ZA",
  "singapore": "SG", "brazil": "BR", "mexico": "MX",
};
function resolveCountryCode(country?: string): string {
  if (!country) return "";
  const trimmed = country.trim();
  if (trimmed.length === 2) return trimmed.toUpperCase();
  return COUNTRY_NAME_TO_ISO[trimmed.toLowerCase()] || trimmed.toUpperCase();
}

/** Small reusable button that sends a test renewal reminder for a partner subscription. */
function TestReminderButton({ subId }: { subId: string }) {
  const [sending, setSending] = useState(false);
  const handle = async () => {
    setSending(true);
    try {
      const res = await api.post(`/admin/partner-subscriptions/${subId}/send-reminder`);
      toast.success(res.data.message || "Reminder sent!");
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to send reminder");
    } finally { setSending(false); }
  };
  return (
    <Button variant="outline" size="sm" onClick={handle} disabled={sending} title="Send test renewal reminder email now" data-testid="send-partner-test-reminder-btn">
      <Bell className="h-4 w-4 mr-1.5" />
      {sending ? "Sending…" : "Test Reminder"}
    </Button>
  );
}

type Tenant = { id: string; name: string; address?: { country?: string; region?: string } };
type Plan = { id: string; name: string; is_active: boolean };
type TaxEntry = { country_code: string; state_code?: string; label: string; rate: number };

type PartnerSubscription = {
  id: string;
  subscription_number: string;
  partner_id: string;
  partner_name: string;
  plan_id?: string;
  plan_name?: string;
  description?: string;
  amount: number;
  currency: string;
  billing_interval: string;
  status: string;
  payment_method: string;
  processor_id?: string;
  stripe_subscription_id?: string;
  start_date?: string;
  next_billing_date?: string;
  cancelled_at?: string;
  internal_note?: string;
  payment_url?: string;
  term_months?: number;
  auto_cancel_on_termination?: boolean;
  contract_end_date?: string;
  created_at: string;
  tax_name?: string;
  tax_rate?: number;
  tax_amount?: number;
};

type Stats = {
  total: number;
  active: number;
  new_this_month: number;
  by_status: Record<string, number>;
  by_interval: Record<string, number>;
  mrr: Record<string, number>;
  arr: Record<string, number>;
};

const STATUS_COLORS: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-700",
  pending: "bg-blue-100 text-blue-900 border-blue-300",
  unpaid: "bg-amber-100 text-amber-700",
  paused: "bg-orange-100 text-orange-700",
  cancelled: "bg-slate-100 text-slate-500",
};

const STATUSES = ["pending", "active", "unpaid", "paused", "cancelled"];
const PAYMENT_METHODS = ["manual", "bank_transfer", "card"];
const BILLING_INTERVALS = ["monthly", "quarterly", "annual"];

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      <p className="text-2xl font-bold text-slate-900">{value}</p>
      {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
    </div>
  );
}

type SubFormData = {
  partner_id: string; plan_id: string; description: string; amount: string;
  currency: string; billing_interval: string; status: string; payment_method: string;
  processor_id: string; start_date: string; next_billing_date: string; internal_note: string;
  term_months: string; auto_cancel_on_termination: boolean; reminder_days: string;
  contract_end_date: string; tax_name: string; tax_rate: string;
};

const emptyForm = (): SubFormData => ({
  partner_id: "", plan_id: "", description: "", amount: "",
  currency: "GBP", billing_interval: "monthly", status: "pending",
  payment_method: "manual", processor_id: "", start_date: "", next_billing_date: "", internal_note: "",
  term_months: "", auto_cancel_on_termination: false, reminder_days: "", contract_end_date: "",
  tax_name: "No tax", tax_rate: "0",
});



/** Add N months to a date string, always returning the 1st of the resulting month */
function addMonthsFirstOfMonth(dateStr: string, months: number): string {
  const d = new Date(dateStr + "T00:00:00Z");
  let m = d.getUTCMonth() + months;
  let y = d.getUTCFullYear() + Math.floor(m / 12);
  m = m % 12;
  return `${y}-${String(m + 1).padStart(2, "0")}-01`;
}

/** Add N months to a date string, preserving the day (for expiry) */
function addMonthsPreserveDay(dateStr: string, months: number): string {
  const d = new Date(dateStr + "T00:00:00Z");
  const y = d.getUTCFullYear() + Math.floor((d.getUTCMonth() + months) / 12);
  const m = (d.getUTCMonth() + months) % 12;
  const day = Math.min(d.getUTCDate(), new Date(y, m + 1, 0).getDate());
  return `${y}-${String(m + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

const INTERVAL_MONTHS: Record<string, number> = { monthly: 1, quarterly: 3, annual: 12 };

function SubFormModal({
  sub, tenants, plans, taxEntries, taxEnabled, onClose, onSaved,
}: {
  sub: PartnerSubscription | null;
  tenants: Tenant[];
  plans: Plan[];
  taxEntries: TaxEntry[];
  taxEnabled: boolean;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = !!sub;
  const { currencies: supportedCurrencies } = useSupportedCurrencies();
  const [form, setForm] = useState<SubFormData>(
    sub ? {
      partner_id: sub.partner_id, plan_id: sub.plan_id || "", description: sub.description || "",
      amount: String(sub.amount), currency: sub.currency, billing_interval: sub.billing_interval,
      status: sub.status, payment_method: sub.payment_method, processor_id: sub.processor_id || "",
      start_date: sub.start_date ? sub.start_date.slice(0, 10) : "",
      next_billing_date: sub.next_billing_date ? sub.next_billing_date.slice(0, 10) : "",
      internal_note: sub.internal_note || "",
      term_months: sub.term_months != null ? String(sub.term_months) : "",
      auto_cancel_on_termination: sub.auto_cancel_on_termination || false,
      reminder_days: (sub as any).reminder_days != null ? String((sub as any).reminder_days) : "",
      contract_end_date: sub.contract_end_date ? sub.contract_end_date.slice(0, 10) : "",
      tax_name: (sub as any).tax_name || "", tax_rate: (sub as any).tax_rate != null ? String((sub as any).tax_rate) : "",
    } : emptyForm()
  );
  const [saving, setSaving] = useState(false);
  const [generatingLink, setGeneratingLink] = useState(false);
  const [paymentUrl, setPaymentUrl] = useState(sub?.payment_url || "");
  // track if user manually edited these fields
  const [nbtManual, setNbtManual] = useState(isEdit && !!sub?.next_billing_date);
  const [expManual, setExpManual] = useState(isEdit && !!sub?.contract_end_date);

  // Derive filtered tax options for the selected partner
  const selectedTenant = tenants.find(t => t.id === form.partner_id);
  const partnerCountry = resolveCountryCode(selectedTenant?.address?.country);
  const partnerRegion = selectedTenant?.address?.region?.toUpperCase();
  const filteredTaxOptions = useMemo(() => {
    if (!partnerCountry || !taxEntries.length) return [];
    return taxEntries.filter(e =>
      e.country_code.toUpperCase() === partnerCountry &&
      (!e.state_code || !partnerRegion || e.state_code.toUpperCase() === partnerRegion)
    );
  }, [partnerCountry, partnerRegion, taxEntries]);

  const handleTaxSelect = (value: string) => {
    if (!value) return;
    const parts = value.split("|");
    if (parts.length >= 4) {
      setForm(f => ({ ...f, tax_name: parts[2], tax_rate: parts[3] }));
    }
  };

  const set = (k: keyof SubFormData, v: string) => setForm(f => ({ ...f, [k]: v }));

  // Default to "No tax" / 0 when tax collection is disabled
  useEffect(() => {
    if (!taxEnabled && !isEdit && !form.tax_name) {
      setForm(f => ({ ...f, tax_name: "No tax", tax_rate: "0" }));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taxEnabled]);

  // Auto-calculate Next Billing Date when start_date or billing_interval changes
  useEffect(() => {
    if (nbtManual) return;
    if (!form.start_date) return;
    const months = INTERVAL_MONTHS[form.billing_interval] || 1;
    setForm(f => ({ ...f, next_billing_date: addMonthsFirstOfMonth(form.start_date, months) }));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.start_date, form.billing_interval]);

  // Auto-calculate Expiry Date when start_date or term_months changes
  useEffect(() => {
    if (expManual) return;
    if (!form.start_date || !form.term_months || parseInt(form.term_months) <= 0) {
      if (!form.term_months) setForm(f => ({ ...f, contract_end_date: "" }));
      return;
    }
    setForm(f => ({ ...f, contract_end_date: addMonthsPreserveDay(form.start_date, parseInt(form.term_months)) }));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.start_date, form.term_months]);

  const handleSave = async () => {
    if (!form.partner_id) { toast.error("Partner is required"); return; }
    if (!form.plan_id) { toast.error("Plan is required"); return; }
    if (!form.amount) { toast.error("Amount is required"); return; }
    const amt = parseFloat(form.amount);
    if (isNaN(amt) || amt < 0) { toast.error("Amount must be a positive number"); return; }

    setSaving(true);
    try {
    const payload: Record<string, any> = {
        ...form,
        description: form.description.trim(),
        amount: amt,
        plan_id: form.plan_id || null,
        processor_id: form.processor_id || null,
        start_date: form.start_date || null,
        next_billing_date: form.next_billing_date || null,
        internal_note: form.internal_note || "",
        term_months: form.term_months ? parseInt(form.term_months) : null,
        auto_cancel_on_termination: form.auto_cancel_on_termination,
        reminder_days: form.reminder_days !== "" ? parseInt(form.reminder_days) : null,
        contract_end_date: form.contract_end_date || null,
        tax_name: form.tax_name.trim() || null,
        tax_rate: form.tax_rate ? parseFloat(form.tax_rate) : null,
        tax_amount: (form.tax_rate && amt) ? parseFloat((amt * parseFloat(form.tax_rate) / 100).toFixed(2)) : null,
      };
      if (isEdit) {
        await api.put(`/admin/partner-subscriptions/${sub.id}`, payload);
        toast.success("Subscription updated");
      } else {
        await api.post("/admin/partner-subscriptions", payload);
        toast.success("Subscription created");
      }
      onSaved();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleStripeCheckout = async () => {
    if (!sub) return;
    setGeneratingLink(true);
    try {
      const { data } = await api.post("/admin/partner-billing/stripe-checkout", { partner_subscription_id: sub.id });
      setPaymentUrl(data.url);
      toast.success("Payment link generated");
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to generate Stripe link");
    } finally {
      setGeneratingLink(false);
    }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? `Edit Subscription — ${sub.subscription_number}` : "New Partner Subscription"}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 mt-2">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1 col-span-2">
              <RequiredLabel className="text-slate-600">Partner</RequiredLabel>
              <SearchableSelect
                value={form.partner_id || undefined}
                onValueChange={v => {
                  if (!taxEnabled) {
                    setForm(f => ({ ...f, partner_id: v, tax_name: "No tax", tax_rate: "0" }));
                    return;
                  }
                  set("partner_id", v);
                  const tenant = tenants.find(t => t.id === v);
                  const country = resolveCountryCode(tenant?.address?.country);
                  const region = tenant?.address?.region?.toUpperCase();
                  if (country) {
                    const matches = taxEntries.filter(e =>
                      e.country_code.toUpperCase() === country &&
                      (!e.state_code || !region || e.state_code.toUpperCase() === region)
                    );
                    if (matches.length >= 1) {
                      const best = matches.find(m => m.state_code && region && m.state_code.toUpperCase() === region) || matches[0];
                      const ratePercent = best.rate < 1 ? parseFloat((best.rate * 100).toFixed(4)) : best.rate;
                      setForm(f => ({ ...f, partner_id: v, tax_name: best.label, tax_rate: String(ratePercent) }));
                    } else {
                      setForm(f => ({ ...f, partner_id: v, tax_name: "No tax", tax_rate: "0" }));
                    }
                  } else {
                    setForm(f => ({ ...f, partner_id: v, tax_name: "No tax", tax_rate: "0" }));
                  }
                }}
                options={tenants.map(t => ({ value: t.id, label: t.name }))}
                placeholder="Select partner…"
                searchPlaceholder="Search partners…"
                data-testid="sub-partner-select"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-700">Plan <span className="text-red-500">*</span></label>
              <SearchableSelect
                value={form.plan_id || undefined}
                onValueChange={v => set("plan_id", v)}
                options={plans.filter(p => p.is_active).map(p => ({ value: p.id, label: p.name }))}
                placeholder="Select plan…"
                searchPlaceholder="Search plans…"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Status</label>
              <Select value={form.status} onValueChange={v => set("status", v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{STATUSES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <label className="text-xs font-medium text-slate-600">Description</label>
              {form.description.length > 0 && <span className={`text-[11px] font-mono tabular-nums ${form.description.length > 4750 ? "text-red-500" : form.description.length > 4000 ? "text-amber-500" : "text-slate-400"}`}>{form.description.length}/5000</span>}
            </div>
            <Input value={form.description} onChange={e => set("description", e.target.value)} maxLength={5000} placeholder="Monthly platform access" data-testid="sub-description-input" />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1 col-span-2">
              <RequiredLabel className="text-slate-600">Amount</RequiredLabel>
              <Input type="number" min={0} step="0.01" value={form.amount} onChange={e => set("amount", e.target.value)} data-testid="sub-amount-input" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Currency</label>
              <Select value={form.currency} onValueChange={v => set("currency", v)}>
                <SelectTrigger data-testid="sub-currency-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {(supportedCurrencies.length ? supportedCurrencies : ISO_CURRENCIES).map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Billing Interval</label>
              <Select value={form.billing_interval} onValueChange={v => { set("billing_interval", v); }}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{BILLING_INTERVALS.map(i => <SelectItem key={i} value={i}>{i}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Payment Method</label>
              <Select value={form.payment_method} onValueChange={v => set("payment_method", v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{PAYMENT_METHODS.map(m => <SelectItem key={m} value={m}>{m.replace("_", " ")}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Start Date</label>
              <Input type="date" value={form.start_date} onChange={e => { setNbtManual(false); setExpManual(false); set("start_date", e.target.value); }} />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600 flex items-center gap-1.5">
                Next Billing Date
                {!nbtManual && form.next_billing_date && (
                  <span className="text-[10px] bg-blue-100 text-blue-600 rounded px-1">auto</span>
                )}
              </label>
              <Input type="date" value={form.next_billing_date} onChange={e => { setNbtManual(true); set("next_billing_date", e.target.value); }} />
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-600">Processor ID (Stripe/GC reference)</label>
            <Input value={form.processor_id} onChange={e => set("processor_id", e.target.value)} maxLength={100} placeholder="sub_xxx or PM-xxx" />
          </div>
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <label className="text-xs font-medium text-slate-600">Internal Note</label>
              {form.internal_note.length > 0 && <span className={`text-[11px] font-mono tabular-nums ${form.internal_note.length > 4750 ? "text-red-500" : form.internal_note.length > 4000 ? "text-amber-500" : "text-slate-400"}`}>{form.internal_note.length}/5000</span>}
            </div>
            <Textarea rows={2} value={form.internal_note} onChange={e => set("internal_note", e.target.value)} maxLength={5000} />
          </div>
          {/* Tax fields */}
          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1 col-span-2">
              <label className="text-xs font-medium text-slate-600">Tax Name</label>
              <Input value={form.tax_name} onChange={e => set("tax_name", e.target.value)} placeholder="e.g. GST, HST, VAT" data-testid="sub-tax-name-input" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Tax Rate (%)</label>
              <Input type="number" min={0} max={100} step="0.01" value={form.tax_rate} onChange={e => set("tax_rate", e.target.value)} placeholder="e.g. 13" data-testid="sub-tax-rate-input" />
            </div>
            {form.tax_rate && form.amount && (
              <div className="col-span-3 text-xs text-slate-500">
                Tax Amount: <span className="font-semibold text-slate-700">{form.currency} {(parseFloat(form.amount || "0") * parseFloat(form.tax_rate) / 100).toFixed(2)}</span>
                &nbsp;· Total incl. tax: <span className="font-semibold text-slate-700">{form.currency} {(parseFloat(form.amount || "0") * (1 + parseFloat(form.tax_rate) / 100)).toFixed(2)}</span>
              </div>
            )}
          </div>
          {/* Contract term */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Contract Term (months)</label>
              <Input type="number" min={0} max={999} placeholder="0 = cancel anytime" value={form.term_months} onChange={e => { setExpManual(false); set("term_months", e.target.value); }} data-testid="partner-sub-term-months" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600 flex items-center gap-1.5">
                Expiry Date
                {!expManual && form.contract_end_date && (
                  <span className="text-[10px] bg-blue-100 text-blue-600 rounded px-1">auto</span>
                )}
              </label>
              <Input type="date" value={form.contract_end_date} onChange={e => { setExpManual(true); set("contract_end_date", e.target.value); }} data-testid="partner-sub-expiry-date" />
            </div>
            <div className="flex items-center gap-2 pt-1">
              <input type="checkbox" id="ps_auto_cancel" data-testid="partner-sub-auto-cancel" checked={form.auto_cancel_on_termination} onChange={e => setForm(f => ({ ...f, auto_cancel_on_termination: e.target.checked }))} />
              <label htmlFor="ps_auto_cancel" className="text-xs text-slate-600">Auto-cancel on term end (as per Expiry Date)</label>
            </div>
          </div>
          {/* Renewal reminder */}
          <div className="space-y-1">
            <div className="flex items-center gap-1.5">
              <label className="text-xs font-medium text-slate-600">Renewal Reminder (days before)</label>
              <span className="group relative cursor-help">
                <span className="text-slate-400 text-xs border border-slate-300 rounded-full w-4 h-4 inline-flex items-center justify-center">?</span>
                <span className="absolute left-5 top-0 z-10 hidden group-hover:block w-64 rounded bg-slate-800 text-white text-xs px-2.5 py-2 shadow-lg">
                  Number of days before renewal to send a reminder email. Leave blank to disable renewal notifications for this subscription.
                </span>
              </span>
            </div>
            <Input type="number" min={1} max={365} placeholder="blank = no reminders" value={form.reminder_days} onChange={e => set("reminder_days", e.target.value)} data-testid="partner-sub-reminder-days" />
          </div>

          {/* Stripe checkout link (edit mode, card payment, monthly/annual only) */}
          {isEdit && form.payment_method === "card" && form.billing_interval !== "quarterly" && (
            <div className="rounded-lg bg-blue-50 border border-blue-200 p-3 space-y-2">
              <p className="text-xs font-medium text-blue-700">Stripe Hosted Checkout (Recurring)</p>
              {paymentUrl ? (
                <div className="flex gap-2">
                  <Input readOnly value={paymentUrl} className="text-xs h-7" />
                  <Button size="sm" variant="outline" onClick={() => { navigator.clipboard.writeText(paymentUrl); toast.success("Copied!"); }}>
                    <Copy className="h-3.5 w-3.5" />
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => window.open(paymentUrl, "_blank")}>
                    <ExternalLink className="h-3.5 w-3.5" />
                  </Button>
                </div>
              ) : (
                <Button size="sm" onClick={handleStripeCheckout} disabled={generatingLink} data-testid="generate-stripe-sub-link-btn">
                  {generatingLink ? "Generating…" : "Generate Checkout Link"}
                </Button>
              )}
            </div>
          )}
        </div>
        <DialogFooter className="mt-4">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          {isEdit && sub && (
            <TestReminderButton subId={sub.id} />
          )}
          <Button onClick={handleSave} disabled={saving} data-testid="save-partner-sub-btn">
            {saving ? "Saving…" : isEdit ? "Save Changes" : "Create Subscription"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function PartnerSubscriptionsTab() {
  const { currencies: supportedCurrencies } = useSupportedCurrencies();
  const [subs, setSubs] = useState<PartnerSubscription[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [taxEntries, setTaxEntries] = useState<TaxEntry[]>([]);
  const [taxEnabled, setTaxEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({ partner_id: "", plan_id: "" });
  const [colSort, setColSort] = useState<{ col: string; dir: "asc" | "desc" } | null>(null);
  const [colFilters, setColFilters] = useState({
    subNumbers: [] as string[], partnerNames: [] as string[], planNames: [] as string[],
    intervals: [] as string[], methods: [] as string[], statuses: [] as string[],
    amount: { min: "", max: "", currency: "" }, nextBilling: { from: "", to: "" }, expiry: { from: "", to: "" },
  });
  const setCF = (key: keyof typeof colFilters, val: any) => setColFilters(f => ({ ...f, [key]: val }));

  const displaySubs = useMemo(() => {
    let r = [...subs];
    if (colFilters.subNumbers.length) r = r.filter(s => colFilters.subNumbers.includes(s.subscription_number));
    if (colFilters.partnerNames.length) r = r.filter(s => colFilters.partnerNames.includes(s.partner_name));
    if (colFilters.planNames.length) r = r.filter(s => s.plan_name && colFilters.planNames.includes(s.plan_name));
    if (colFilters.intervals.length) r = r.filter(s => colFilters.intervals.includes(s.billing_interval));
    if (colFilters.methods.length) r = r.filter(s => colFilters.methods.includes(s.payment_method));
    if (colFilters.statuses.length) r = r.filter(s => colFilters.statuses.includes(s.status));
    if (colFilters.amount.min) r = r.filter(s => s.amount >= parseFloat(colFilters.amount.min));
    if (colFilters.amount.max) r = r.filter(s => s.amount <= parseFloat(colFilters.amount.max));
    if (colFilters.amount.currency) r = r.filter(s => s.currency === colFilters.amount.currency);
    if (colFilters.nextBilling.from) r = r.filter(s => s.next_billing_date && s.next_billing_date >= colFilters.nextBilling.from);
    if (colFilters.nextBilling.to) r = r.filter(s => s.next_billing_date && s.next_billing_date <= colFilters.nextBilling.to);
    if (colFilters.expiry.from) r = r.filter(s => s.contract_end_date && s.contract_end_date >= colFilters.expiry.from);
    if (colFilters.expiry.to) r = r.filter(s => s.contract_end_date && s.contract_end_date <= colFilters.expiry.to);
    if (colSort) {
      r.sort((a, b) => {
        let av: any = "", bv: any = "";
        if (colSort.col === "sub_number") { av = a.subscription_number || ""; bv = b.subscription_number || ""; }
        else if (colSort.col === "partner") { av = a.partner_name || ""; bv = b.partner_name || ""; }
        else if (colSort.col === "plan") { av = a.plan_name || ""; bv = b.plan_name || ""; }
        else if (colSort.col === "amount") { av = a.amount; bv = b.amount; }
        else if (colSort.col === "interval") { av = a.billing_interval; bv = b.billing_interval; }
        else if (colSort.col === "method") { av = a.payment_method; bv = b.payment_method; }
        else if (colSort.col === "status") { av = a.status; bv = b.status; }
        else if (colSort.col === "next_billing") { av = a.next_billing_date || ""; bv = b.next_billing_date || ""; }
        else if (colSort.col === "expiry") { av = a.contract_end_date || ""; bv = b.contract_end_date || ""; }
        if (av < bv) return colSort.dir === "asc" ? -1 : 1;
        if (av > bv) return colSort.dir === "asc" ? 1 : -1;
        return 0;
      });
    }
    return r;
  }, [subs, colFilters, colSort]);
  const subNumOpts = useMemo(() => Array.from(new Set(subs.map(s => s.subscription_number).filter((v): v is string => !!v))).sort().map(v => [v, v] as [string, string]), [subs]);
  const partnerOpts = useMemo(() => Array.from(new Set(subs.map(s => s.partner_name).filter((v): v is string => !!v))).sort().map(v => [v, v] as [string, string]), [subs]);
  const planOpts = useMemo(() => Array.from(new Set(subs.map(s => s.plan_name).filter((v): v is string => !!v))).sort().map(v => [v, v] as [string, string]), [subs]);
  const [showCreate, setShowCreate] = useState(false);
  const [editSub, setEditSub] = useState<PartnerSubscription | null>(null);
  const [cancelSub, setCancelSub] = useState<PartnerSubscription | null>(null);
  const [logsUrl, setLogsUrl] = useState("");
  const [showAuditLogs, setShowAuditLogs] = useState(false);
  const LIMIT = 20;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), limit: String(LIMIT) });
      if (filters.partner_id) params.set("partner_id", filters.partner_id);
      if (filters.plan_id && filters.plan_id !== "all") params.set("plan_id", filters.plan_id);
      const [subsRes, statsRes] = await Promise.all([
        api.get(`/admin/partner-subscriptions?${params}`),
        api.get("/admin/partner-subscriptions/stats"),
      ]);
      setSubs(subsRes.data.subscriptions || []);
      setTotal(subsRes.data.total || 0);
      setStats(statsRes.data);
    } catch { toast.error("Failed to load subscriptions"); }
    finally { setLoading(false); }
  }, [page, filters]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    Promise.all([
      api.get("/admin/tenants"),
      api.get("/admin/plans"),
      api.get("/admin/taxes/settings").catch(() => ({ data: { enabled: false } })),
      api.get("/admin/taxes/tables").catch(() => ({ data: { entries: [] } })),
    ]).then(([t, p, ts, te]) => {
      setTenants((t.data.tenants || []).filter((x: any) => x.code !== "automate-accounts"));
      setPlans((p.data.plans || []).filter((x: Plan) => x.is_active));
      setTaxEnabled(ts.data?.tax_settings?.enabled === true);
      setTaxEntries(te.data?.entries || []);
    }).catch(() => {});
  }, []);

  const handleCancel = async () => {
    if (!cancelSub) return;
    try {
      await api.patch(`/admin/partner-subscriptions/${cancelSub.id}/cancel`);
      toast.success("Subscription cancelled");
      setCancelSub(null);
      load();
    } catch (e: any) { toast.error(e.response?.data?.detail || "Cancel failed"); }
  };

  const fmtDate = (d?: string) => d ? new Date(d).toLocaleDateString() : "—";
  const fmtAmt = (amount: number, currency: string) =>
    new Intl.NumberFormat("en-GB", { style: "currency", currency }).format(amount);

  return (
    <div className="flex flex-col gap-5" data-testid="partner-subscriptions-tab">
      <AdminPageHeader
        title="Partner Subscriptions"
        subtitle={`${total} subscription${total !== 1 ? "s" : ""}`}
        actions={
          <>
            <Button size="sm" variant="outline" onClick={load} data-testid="refresh-partner-subs-btn">
              <RefreshCw className="h-4 w-4" />
            </Button>
            <Button size="sm" onClick={() => setShowCreate(true)} data-testid="create-partner-sub-btn">
              <Plus size={14} className="mr-1" />New Subscription
            </Button>
          </>
        }
      />

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard label="Total Subscriptions" value={stats.total} />
          <StatCard label="Active" value={stats.active} />
          <StatCard label="New This Month" value={stats.new_this_month} />
          <StatCard label="Cancelled" value={stats.by_status?.cancelled || 0} />
        </div>
      )}

      {/* MRR / ARR revenue blocks */}
      {stats && (Object.keys(stats.mrr || {}).length > 0 || Object.keys(stats.arr || {}).length > 0) && (
        <div className="flex gap-3 flex-wrap">
          {Object.entries(stats.mrr || {}).map(([currency, val]) => (
            <div key={`mrr-${currency}`} className="bg-emerald-50 border border-emerald-200 rounded-lg px-4 py-2 text-sm">
              <span className="text-slate-500 text-xs">MRR</span>
              <p className="font-bold text-emerald-700">{fmtAmt(val, currency)}</p>
            </div>
          ))}
          {Object.entries(stats.arr || {}).map(([currency, val]) => (
            <div key={`arr-${currency}`} className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-2 text-sm">
              <span className="text-slate-500 text-xs">ARR</span>
              <p className="font-bold text-blue-700">{fmtAmt(val, currency)}</p>
            </div>
          ))}
        </div>
      )}

      {/* Table */}
      <StickyTableScroll className="rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-sm" data-testid="partner-subscriptions-table">
          <thead className="bg-slate-50">
            <tr>
              <ColHeader compact label="Sub #" colKey="sub_number" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={colFilters.subNumbers} onFilter={v => setCF("subNumbers", v)} onClearFilter={() => setCF("subNumbers", [])} statusOptions={subNumOpts} />
              <ColHeader compact label="Partner" colKey="partner" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={colFilters.partnerNames} onFilter={v => setCF("partnerNames", v)} onClearFilter={() => setCF("partnerNames", [])} statusOptions={partnerOpts} />
              <ColHeader compact label="Plan" colKey="plan" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={colFilters.planNames} onFilter={v => setCF("planNames", v)} onClearFilter={() => setCF("planNames", [])} statusOptions={planOpts} />
              <ColHeader compact label="Amount" colKey="amount" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="number-range" filterValue={colFilters.amount} onFilter={v => setCF("amount", v)} onClearFilter={() => setCF("amount", { min: "", max: "", currency: "" })} currencyOptions={supportedCurrencies.map(c => [c, c] as [string, string])} />
              <ColHeader compact label="Interval" colKey="interval" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={colFilters.intervals} onFilter={v => setCF("intervals", v)} onClearFilter={() => setCF("intervals", [])} statusOptions={[["monthly", "Monthly"], ["quarterly", "Quarterly"], ["annual", "Annual"]]} />
              <ColHeader compact label="Method" colKey="method" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={colFilters.methods} onFilter={v => setCF("methods", v)} onClearFilter={() => setCF("methods", [])} statusOptions={[["manual", "Manual"], ["bank_transfer", "Bank Transfer"], ["card", "Card"]]} />
              <ColHeader compact label="Status" colKey="status" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={colFilters.statuses} onFilter={v => setCF("statuses", v)} onClearFilter={() => setCF("statuses", [])} statusOptions={[["pending", "Pending"], ["active", "Active"], ["unpaid", "Unpaid"], ["paused", "Paused"], ["cancelled", "Cancelled"]]} />
              <ColHeader compact label="Next Billing" colKey="next_billing" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="date-range" filterValue={colFilters.nextBilling} onFilter={v => setCF("nextBilling", v)} onClearFilter={() => setCF("nextBilling", { from: "", to: "" })} />
              <ColHeader compact label="Expiry" colKey="expiry" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="date-range" filterValue={colFilters.expiry} onFilter={v => setCF("expiry", v)} onClearFilter={() => setCF("expiry", { from: "", to: "" })} />
              <th className="text-right px-3 py-2 text-xs font-medium uppercase text-slate-500 whitespace-nowrap">Tax Amt</th>
              <th className="text-right px-3 py-2 text-xs font-medium uppercase text-slate-500">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={11} className="text-center py-8 text-slate-400">Loading…</td></tr>
            ) : displaySubs.length === 0 ? (
              <tr><td colSpan={11} className="text-center py-8 text-slate-400">No subscriptions found.</td></tr>
            ) : displaySubs.map(sub => (
              <tr key={sub.id} className="border-t border-slate-100 hover:bg-slate-50" data-testid={`sub-row-${sub.id}`}>
                <td className="px-3 py-2 font-mono text-xs text-slate-600">{sub.subscription_number}</td>
                <td className="px-3 py-2 font-medium">{sub.partner_name}</td>
                <td className="px-3 py-2 text-slate-500 text-xs">{sub.plan_name || "—"}</td>
                <td className="px-3 py-2 font-semibold">{fmtAmt(sub.amount, sub.currency)}</td>
                <td className="px-3 py-2 text-slate-500 capitalize">{sub.billing_interval}</td>
                <td className="px-3 py-2 text-slate-500 capitalize">{sub.payment_method.replace("_", " ")}</td>
                <td className="px-3 py-2">
                  <Badge className={`text-[11px] ${STATUS_COLORS[sub.status] || "bg-slate-100"}`}>{sub.status}</Badge>
                </td>
                <td className="px-3 py-2 text-slate-500 text-xs">{fmtDate(sub.next_billing_date)}</td>
                <td className="px-3 py-2 text-slate-500 text-xs">{fmtDate(sub.contract_end_date)}</td>
                <td className="px-3 py-2 text-slate-500 text-xs text-right">
                  {sub.tax_rate != null && sub.tax_rate > 0
                    ? fmtAmt(sub.tax_amount ?? sub.amount * sub.tax_rate / 100, sub.currency)
                    : sub.tax_name === "No tax" ? <span className="text-xs text-slate-400">No tax</span> : "—"}
                </td>
                <td className="px-3 py-2">
                  <div className="flex justify-end gap-1">
                    <Button size="sm" variant="ghost" title="Audit Logs" onClick={() => { setLogsUrl(`/admin/partner-subscriptions/${sub.id}`); setShowAuditLogs(true); }} data-testid={`sub-logs-${sub.id}`}>
                      <ScrollText className="h-4 w-4" />
                    </Button>
                    <Button size="sm" variant="ghost" title="Edit" onClick={() => setEditSub(sub)} data-testid={`edit-sub-${sub.id}`}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    {sub.status !== "cancelled" && (
                      <Button size="sm" variant="ghost" className="text-red-400 hover:text-red-600" title="Cancel" onClick={() => setCancelSub(sub)} data-testid={`cancel-sub-${sub.id}`}>
                        <XCircle className="h-4 w-4" />
                      </Button>
                    )}
                    {sub.payment_url && (
                      <Button size="sm" variant="ghost" title="Open payment link" onClick={() => window.open(sub.payment_url, "_blank")} data-testid={`sub-paylink-${sub.id}`}>
                        <ExternalLink className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </StickyTableScroll>
      {total > LIMIT && (
        <div className="flex justify-end gap-2">
          <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Prev</Button>
          <span className="text-sm text-slate-500 py-1.5">Page {page} of {Math.ceil(total / LIMIT)}</span>
          <Button size="sm" variant="outline" disabled={page >= Math.ceil(total / LIMIT)} onClick={() => setPage(p => p + 1)}>Next</Button>
        </div>
      )}

      {/* Modals */}
      {showCreate && <SubFormModal sub={null} tenants={tenants} plans={plans} taxEntries={taxEntries} taxEnabled={taxEnabled} onClose={() => setShowCreate(false)} onSaved={() => { setShowCreate(false); load(); }} />}
      {editSub && <SubFormModal sub={editSub} tenants={tenants} plans={plans} taxEntries={taxEntries} taxEnabled={taxEnabled} onClose={() => setEditSub(null)} onSaved={() => { setEditSub(null); load(); }} />}

      {/* Cancel Confirmation */}
      {cancelSub && (
        <AlertDialog open onOpenChange={() => setCancelSub(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Cancel subscription {cancelSub.subscription_number}?</AlertDialogTitle>
              <AlertDialogDescription>
                This will cancel the subscription for <strong>{cancelSub.partner_name}</strong>.
                If linked to Stripe, it will be set to cancel at period end.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Keep Active</AlertDialogCancel>
              <AlertDialogAction className="bg-red-600 hover:bg-red-700" onClick={handleCancel} data-testid="confirm-cancel-partner-sub">
                Yes, Cancel
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}

      {/* Audit Logs Dialog */}
      <AuditLogDialog
        open={showAuditLogs}
        onOpenChange={setShowAuditLogs}
        title="Partner Subscription Audit Logs"
        logsUrl={logsUrl}
      />
    </div>
  );
}
