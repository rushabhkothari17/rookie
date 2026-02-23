import { useEffect, useState } from "react";
import api from "@/lib/api";
import { CheckCircle, Circle, X, ChevronRight } from "lucide-react";
import { useNavigate } from "react-router-dom";

interface ChecklistData {
  checklist: {
    brand_customized: boolean;
    first_product: boolean;
    payment_configured: boolean;
    first_customer: boolean;
    first_article: boolean;
  };
  completed: number;
  total: number;
}

const ITEMS = [
  { key: "brand_customized", label: "Customize your brand", desc: "Add a logo and store name", tab: "website" },
  { key: "first_product", label: "Add your first product", desc: "Create a product in your catalog", tab: "catalog" },
  { key: "payment_configured", label: "Configure payment", desc: "Set up Stripe or GoCardless", tab: "website" },
  { key: "first_customer", label: "Invite a customer", desc: "Add your first customer", tab: "customers" },
  { key: "first_article", label: "Create an article", desc: "Write your first guide or scope", tab: "articles" },
] as const;

interface Props {
  onNavigate: (tab: string) => void;
}

export function SetupChecklistWidget({ onNavigate }: Props) {
  const [data, setData] = useState<ChecklistData | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    const isDismissed = sessionStorage.getItem("aa_checklist_dismissed") === "1";
    if (isDismissed) { setDismissed(true); return; }
    api.get("/admin/setup-checklist")
      .then(res => setData(res.data))
      .catch(() => {});
  }, []);

  if (!data || dismissed) return null;
  if (data.completed === data.total) return null;

  const handleDismiss = () => {
    sessionStorage.setItem("aa_checklist_dismissed", "1");
    setDismissed(true);
  };

  const pct = Math.round((data.completed / data.total) * 100);

  return (
    <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden mb-6" data-testid="setup-checklist-widget">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-full bg-slate-900 flex items-center justify-center">
            <span className="text-xs font-bold text-white">{pct}%</span>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-900">Setup Checklist</h3>
            <p className="text-xs text-slate-500">{data.completed} of {data.total} steps completed</p>
          </div>
        </div>
        <button
          onClick={handleDismiss}
          className="text-slate-400 hover:text-slate-600 transition-colors p-1 rounded"
          data-testid="checklist-dismiss-btn"
          title="Dismiss checklist"
        >
          <X size={14} />
        </button>
      </div>

      {/* Progress bar */}
      <div className="h-1 bg-slate-100">
        <div
          className="h-1 bg-slate-900 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Items */}
      <div className="divide-y divide-slate-100">
        {ITEMS.map(item => {
          const done = data.checklist[item.key];
          return (
            <button
              key={item.key}
              onClick={() => !done && onNavigate(item.tab)}
              className={`w-full flex items-center gap-3 px-5 py-3 text-left transition-colors ${done ? "opacity-60 cursor-default" : "hover:bg-slate-50 cursor-pointer"}`}
              data-testid={`checklist-item-${item.key}`}
            >
              {done ? (
                <CheckCircle size={16} className="text-green-500 shrink-0" />
              ) : (
                <Circle size={16} className="text-slate-300 shrink-0" />
              )}
              <div className="flex-1 min-w-0">
                <p className={`text-sm font-medium ${done ? "line-through text-slate-400" : "text-slate-800"}`}>
                  {item.label}
                </p>
                <p className="text-xs text-slate-400">{item.desc}</p>
              </div>
              {!done && <ChevronRight size={14} className="text-slate-300 shrink-0" />}
            </button>
          );
        })}
      </div>
    </div>
  );
}
