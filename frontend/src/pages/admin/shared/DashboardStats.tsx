/**
 * Reusable stats dashboard row for Orders / Subscriptions / Customers tabs.
 * Fetches its own data on mount; renders compact KPI cards + a dynamic
 * "by …" breakdown bar (payment method, status, mode).
 */
import { useEffect, useState } from "react";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import api from "@/lib/api";

// ── Helpers ──────────────────────────────────────────────────────────────────

const currencyFmt = (value: number, currency: string) =>
  new Intl.NumberFormat("en-GB", { style: "currency", currency, maximumFractionDigits: 0 }).format(value);

const numFmt = (n: number) => n.toLocaleString();

function Trend({ current, previous }: { current: number; previous: number }) {
  if (previous === 0 && current === 0) return null;
  if (previous === 0) return <span className="text-[10px] text-emerald-600 font-medium flex items-center gap-0.5"><TrendingUp size={10} /> New</span>;
  const pct = Math.round(((current - previous) / previous) * 100);
  if (pct === 0) return <span className="text-[10px] text-slate-400 flex items-center gap-0.5"><Minus size={10} /> 0%</span>;
  const up = pct > 0;
  return (
    <span className={`text-[10px] font-medium flex items-center gap-0.5 ${up ? "text-emerald-600" : "text-red-500"}`}>
      {up ? <TrendingUp size={10} /> : <TrendingDown size={10} />} {up ? "+" : ""}{pct}% vs last month
    </span>
  );
}

function KpiCard({ label, value, sub, color, testid }: {
  label: string; value: string; sub?: React.ReactNode; color: string; testid?: string;
}) {
  return (
    <div className={`rounded-xl border px-4 py-3 ${color}`} data-testid={testid}>
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500 mb-1">{label}</p>
      <p className="text-2xl font-bold text-slate-800 leading-none">{value}</p>
      {sub && <div className="mt-1">{sub}</div>}
    </div>
  );
}

function BreakdownBar({ label, data, colors }: {
  label: string;
  data: Record<string, number>;
  colors?: Record<string, string>;
}) {
  const total = Object.values(data).reduce((a, b) => a + b, 0);
  if (total === 0) return null;

  const defaultColors = [
    "bg-indigo-400", "bg-teal-400", "bg-amber-400", "bg-rose-400",
    "bg-sky-400", "bg-violet-400", "bg-orange-400", "bg-lime-400",
  ];

  const entries = Object.entries(data).sort(([, a], [, b]) => b - a);

  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3" data-testid={`breakdown-${label.toLowerCase().replace(/\s/g, "-")}`}>
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500 mb-2">{label}</p>
      {/* Stacked bar */}
      <div className="flex h-2 rounded-full overflow-hidden gap-px mb-2">
        {entries.map(([key, count], i) => (
          <div
            key={key}
            className={colors?.[key] || defaultColors[i % defaultColors.length]}
            style={{ width: `${(count / total) * 100}%` }}
            title={`${key}: ${count}`}
          />
        ))}
      </div>
      {/* Legend */}
      <div className="flex flex-wrap gap-x-3 gap-y-1">
        {entries.map(([key, count], i) => (
          <span key={key} className="flex items-center gap-1 text-[10px] text-slate-600">
            <span className={`w-2 h-2 rounded-sm inline-block ${colors?.[key] || defaultColors[i % defaultColors.length]}`} />
            <span className="font-medium capitalize">{key || "unknown"}</span>
            <span className="text-slate-400">{count.toLocaleString()}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

// ── Orders Stats ──────────────────────────────────────────────────────────────

export function OrdersStats() {
  const [stats, setStats] = useState<any>(null);
  useEffect(() => { api.get("/admin/orders/stats").then(r => setStats(r.data)).catch(() => {}); }, []);
  if (!stats) return null;

  const { total, this_month, last_month, base_currency, revenue_base, this_month_revenue_base, by_status, by_payment_method } = stats;

  const statusColors: Record<string, string> = {
    paid: "bg-emerald-400", completed: "bg-teal-400",
    pending: "bg-amber-400", cancelled: "bg-slate-300",
    refunded: "bg-red-300", awaiting_bank_transfer: "bg-sky-400",
    scope_pending: "bg-indigo-300",
  };

  return (
    <div className="space-y-3" data-testid="orders-stats-dashboard">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard label="Total Orders" value={numFmt(total)} color="border-slate-200 bg-slate-50/40" testid="orders-stat-total" />
        <KpiCard
          label="This Month"
          value={numFmt(this_month)}
          sub={<Trend current={this_month} previous={last_month} />}
          color="border-blue-100 bg-blue-50/40"
          testid="orders-stat-this-month"
        />
        <KpiCard
          label="Total Revenue"
          value={currencyFmt(revenue_base, base_currency)}
          sub={<span className="text-[10px] text-slate-400">in {base_currency}</span>}
          color="border-emerald-100 bg-emerald-50/40"
          testid="orders-stat-revenue"
        />
        <KpiCard
          label="Revenue This Month"
          value={currencyFmt(this_month_revenue_base, base_currency)}
          sub={<span className="text-[10px] text-slate-400">in {base_currency}</span>}
          color="border-teal-100 bg-teal-50/40"
          testid="orders-stat-revenue-month"
        />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <BreakdownBar label="By Status" data={by_status} colors={statusColors} />
        <BreakdownBar label="By Payment Method" data={by_payment_method} />
      </div>
    </div>
  );
}

// ── Subscriptions Stats ───────────────────────────────────────────────────────

export function SubscriptionsStats() {
  const [stats, setStats] = useState<any>(null);
  useEffect(() => { api.get("/admin/subscriptions/stats").then(r => setStats(r.data)).catch(() => {}); }, []);
  if (!stats) return null;

  const { total, active, new_this_month, churned_this_month, base_currency, mrr_base, by_status, by_payment_method } = stats;

  const statusColors: Record<string, string> = {
    active: "bg-emerald-400", cancelled: "bg-slate-300", canceled: "bg-slate-300",
    paused: "bg-amber-400", past_due: "bg-red-400", unpaid: "bg-red-300",
    pending: "bg-sky-400",
  };

  return (
    <div className="space-y-3" data-testid="subscriptions-stats-dashboard">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard label="Active Subs" value={numFmt(active)}
          sub={<span className="text-[10px] text-slate-400">{numFmt(total)} total</span>}
          color="border-emerald-100 bg-emerald-50/40" testid="subs-stat-active" />
        <KpiCard label="MRR" value={currencyFmt(mrr_base, base_currency)}
          sub={<span className="text-[10px] text-slate-400">in {base_currency}</span>}
          color="border-indigo-100 bg-indigo-50/40" testid="subs-stat-mrr" />
        <KpiCard label="New This Month" value={numFmt(new_this_month)}
          color="border-blue-100 bg-blue-50/40" testid="subs-stat-new" />
        <KpiCard label="Churned This Month" value={numFmt(churned_this_month)}
          color={churned_this_month > 0 ? "border-red-100 bg-red-50/40" : "border-slate-200 bg-slate-50/40"}
          testid="subs-stat-churned" />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <BreakdownBar label="By Status" data={by_status} colors={statusColors} />
        <BreakdownBar label="By Payment Method" data={by_payment_method} />
      </div>
    </div>
  );
}

// ── Customers Stats ───────────────────────────────────────────────────────────

export function CustomersStats() {
  const [stats, setStats] = useState<any>(null);
  useEffect(() => { api.get("/admin/customers/stats").then(r => setStats(r.data)).catch(() => {}); }, []);
  if (!stats) return null;

  const { total, active, new_this_month, by_payment_mode } = stats;

  return (
    <div className="space-y-3" data-testid="customers-stats-dashboard">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <KpiCard label="Total Customers" value={numFmt(total)}
          color="border-slate-200 bg-slate-50/40" testid="customers-stat-total" />
        <KpiCard label="Active" value={numFmt(active)}
          sub={total > 0 ? <span className="text-[10px] text-slate-400">{Math.round((active / total) * 100)}% of total</span> : undefined}
          color="border-emerald-100 bg-emerald-50/40" testid="customers-stat-active" />
        <KpiCard label="New This Month" value={numFmt(new_this_month)}
          color="border-blue-100 bg-blue-50/40" testid="customers-stat-new" />
      </div>
      {Object.keys(by_payment_mode).length > 0 && (
        <BreakdownBar label="By Payment Mode" data={by_payment_mode} />
      )}
    </div>
  );
}
