import { useState, useEffect } from "react";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { RefreshCw, TrendingUp, Users, Package, FileText, ShoppingCart } from "lucide-react";
import { Button } from "@/components/ui/button";

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

const USAGE_SECTIONS = [
  {
    title: "Monthly (resets 1st of month)",
    icon: TrendingUp,
    items: [
      { key: "orders_this_month", label: "Orders" },
      { key: "customers_this_month", label: "New Customers" },
      { key: "subscriptions_this_month", label: "Subscriptions" },
    ],
  },
  {
    title: "People & Roles",
    icon: Users,
    items: [
      { key: "users", label: "Admin Users" },
      { key: "user_roles", label: "Custom Roles" },
    ],
  },
  {
    title: "Content & Commerce",
    icon: Package,
    items: [
      { key: "product_categories", label: "Product Categories" },
      { key: "product_terms", label: "Terms Documents" },
      { key: "enquiries", label: "Enquiries" },
    ],
  },
  {
    title: "Resources & Templates",
    icon: FileText,
    items: [
      { key: "resources", label: "Resources" },
      { key: "templates", label: "Resource Templates" },
      { key: "email_templates", label: "Resource Email Templates" },
      { key: "categories", label: "Resource Categories" },
    ],
  },
  {
    title: "Forms & Settings",
    icon: ShoppingCart,
    items: [
      { key: "forms", label: "Custom Forms" },
      { key: "references", label: "References" },
      { key: "storage_mb", label: "Storage (MB)" },
    ],
  },
];

function UsageBar({ entry, label }: { entry: UsageEntry | undefined; label: string }) {
  if (!entry) return null;
  const { current, limit, pct, warning, blocked } = entry;
  const isUnlimited = limit === null || limit === undefined;

  const barColor = blocked
    ? "bg-red-500"
    : warning
    ? "bg-amber-500"
    : "bg-emerald-500";

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className="text-slate-700">{label}</span>
        <span className={`text-xs font-medium ${blocked ? "text-red-600" : warning ? "text-amber-600" : "text-slate-500"}`}>
          {isUnlimited ? (
            <span className="text-emerald-600">Unlimited</span>
          ) : (
            `${current} / ${limit}`
          )}
        </span>
      </div>
      {!isUnlimited && (
        <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${barColor}`}
            style={{ width: `${Math.min(pct, 100)}%` }}
          />
        </div>
      )}
      {blocked && (
        <p className="text-xs text-red-600 font-medium">Limit reached — contact your administrator to upgrade.</p>
      )}
      {!blocked && warning && !isUnlimited && (
        <p className="text-xs text-amber-600">Approaching limit ({pct}% used).</p>
      )}
    </div>
  );
}

export function UsageDashboard() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/admin/usage");
      setSnapshot(data);
    } catch {
      toast.error("Failed to load usage data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  if (loading) {
    return <div className="p-6 text-slate-500 text-sm">Loading usage data…</div>;
  }

  if (!snapshot) return null;

  const anyWarning = Object.values(snapshot.usage || {}).some(e => e.warning);
  const anyBlocked = Object.values(snapshot.usage || {}).some(e => e.blocked);

  return (
    <div className="space-y-6" data-testid="usage-dashboard">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Usage & Limits</h2>
          <p className="text-sm text-slate-500">
            Plan: <strong>{snapshot.license?.plan || "Unlimited"}</strong>
            {snapshot.period && <> · Period: <strong>{snapshot.period}</strong> (EST)</>}
          </p>
        </div>
        <Button size="sm" variant="outline" onClick={load} data-testid="refresh-usage-btn">
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      {anyBlocked && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
          <strong>One or more limits have been reached.</strong> Some actions may be blocked. Please contact your platform administrator to upgrade your plan.
        </div>
      )}
      {!anyBlocked && anyWarning && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-sm text-amber-700">
          You are approaching one or more resource limits. Consider contacting your administrator.
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {USAGE_SECTIONS.map(({ title, icon: Icon, items }) => (
          <div key={title} className="bg-white rounded-xl border border-slate-200 p-5">
            <div className="flex items-center gap-2 mb-4">
              <Icon className="h-4 w-4 text-slate-500" />
              <h3 className="text-sm font-semibold text-slate-700">{title}</h3>
            </div>
            <div className="space-y-4">
              {items.map(({ key, label }) => (
                <UsageBar
                  key={key}
                  entry={snapshot.usage?.[key]}
                  label={label}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
