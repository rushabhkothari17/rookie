import { useEffect, useState } from "react";
import api from "@/lib/api";
import { CheckCircle, Circle, X, ChevronRight, ChevronDown, ChevronUp, Sparkles } from "lucide-react";

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
  { key: "brand_customized", label: "Customize your brand", desc: "Organization Info > Branding", tab: "org-info", section: undefined },
  { key: "first_product", label: "Add your first product", desc: "Catalog > Create product", tab: "catalog", section: undefined },
  { key: "payment_configured", label: "Configure payment", desc: "Connect Services > Payments", tab: "integrations", section: undefined },
  { key: "first_customer", label: "Invite a customer", desc: "Customers > Add customer", tab: "customers", section: undefined },
  { key: "first_article", label: "Create a resource", desc: "Resources > Write guide", tab: "resources", section: undefined },
] as const;

interface Props {
  onNavigate: (tab: string, section?: string) => void;
}

export function SetupChecklistWidget({ onNavigate }: Props) {
  const [data, setData] = useState<ChecklistData | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    // Check if permanently dismissed
    const isDismissed = localStorage.getItem("aa_checklist_dismissed") === "1";
    if (isDismissed) { setDismissed(true); return; }
    
    // Check if collapsed preference
    const isCollapsed = localStorage.getItem("aa_checklist_collapsed") === "1";
    setCollapsed(isCollapsed);
    
    api.get("/admin/setup-checklist")
      .then(res => setData(res.data))
      .catch(() => {});
  }, []);

  if (!data || dismissed) return null;
  if (data.completed === data.total) return null;

  const handleDismiss = () => {
    localStorage.setItem("aa_checklist_dismissed", "1");
    setDismissed(true);
  };

  const handleToggleCollapse = () => {
    const newState = !collapsed;
    setCollapsed(newState);
    localStorage.setItem("aa_checklist_collapsed", newState ? "1" : "0");
  };

  const pct = Math.round((data.completed / data.total) * 100);
  const remaining = data.total - data.completed;

  // Collapsed view - compact floating badge
  if (collapsed) {
    return (
      <button
        onClick={handleToggleCollapse}
        className="fixed bottom-20 right-4 z-40 flex items-center gap-2 bg-slate-900 text-white px-3 py-2 rounded-full shadow-lg hover:bg-slate-800 transition-all group"
        data-testid="setup-checklist-collapsed"
      >
        <Sparkles size={14} className="text-amber-400" />
        <span className="text-xs font-medium">{remaining} setup steps left</span>
        <ChevronUp size={14} className="opacity-60 group-hover:opacity-100" />
      </button>
    );
  }

  // Expanded view - compact card
  return (
    <div 
      className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden mb-4"
      data-testid="setup-checklist-widget"
    >
      {/* Compact Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-slate-50 to-white">
        <div className="flex items-center gap-3">
          <div className="h-7 w-7 rounded-full bg-slate-900 flex items-center justify-center">
            <span className="text-[10px] font-bold text-white">{pct}%</span>
          </div>
          <div>
            <h3 className="text-xs font-semibold text-slate-800">Quick Setup</h3>
            <p className="text-[10px] text-slate-500">{remaining} steps remaining</p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={handleToggleCollapse}
            className="text-slate-400 hover:text-slate-600 p-1 rounded hover:bg-slate-100 transition-colors"
            title="Minimize"
          >
            <ChevronDown size={14} />
          </button>
          <button
            onClick={handleDismiss}
            className="text-slate-400 hover:text-slate-600 p-1 rounded hover:bg-slate-100 transition-colors"
            data-testid="checklist-dismiss-btn"
            title="Don't show again"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-0.5 bg-slate-100">
        <div className="h-0.5 bg-emerald-500 transition-all duration-500" style={{ width: `${pct}%` }} />
      </div>

      {/* Compact Items - Show incomplete only */}
      <div className="divide-y divide-slate-50">
        {ITEMS.filter(item => !data.checklist[item.key]).slice(0, 3).map(item => (
          <button
            key={item.key}
            onClick={() => onNavigate(item.tab, item.section)}
            className="w-full flex items-center gap-2 px-4 py-2.5 text-left hover:bg-slate-50 transition-colors"
            data-testid={`checklist-item-${item.key}`}
          >
            <Circle size={12} className="text-slate-300 shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-slate-700 truncate">{item.label}</p>
              <p className="text-[10px] text-slate-400 truncate">{item.desc}</p>
            </div>
            <ChevronRight size={12} className="text-slate-300 shrink-0" />
          </button>
        ))}
        {ITEMS.filter(item => !data.checklist[item.key]).length > 3 && (
          <div className="px-4 py-2 text-[10px] text-slate-400 text-center">
            +{ITEMS.filter(item => !data.checklist[item.key]).length - 3} more steps
          </div>
        )}
      </div>
    </div>
  );
}
