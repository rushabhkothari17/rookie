import { useEffect, useState, useCallback } from "react";
import {
  Users, UserRound, ShoppingBag, Package, RefreshCw, MessageSquare,
  BookOpen, FolderOpen, ClipboardList, Building, Percent, Lock,
  LayoutTemplate, Mail, Link2, Globe, Puzzle, Code2, Zap, Activity,
  Store, SlidersHorizontal, Wallet, CreditCard, Building2, LayoutGrid,
  Receipt, Coins, ArrowRightLeft, Search, X, Repeat2, FileText,
} from "lucide-react";

const NAV_ITEMS = [
  // People
  { label: "Users", value: "users", section: "People", icon: Users },
  { label: "Customers", value: "customers", section: "People", icon: UserRound },
  // Commerce
  { label: "Products", value: "catalog", section: "Commerce", icon: Store },
  { label: "Filters", value: "filters", section: "Commerce", icon: SlidersHorizontal },
  { label: "Subscriptions", value: "subscriptions", section: "Commerce", icon: Repeat2 },
  { label: "Orders", value: "orders", section: "Commerce", icon: ShoppingBag },
  { label: "Enquiries", value: "enquiries", section: "Commerce", icon: MessageSquare },
  // Content
  { label: "Resources", value: "resources", section: "Content", icon: BookOpen },
  { label: "Documents", value: "documents", section: "Content", icon: FolderOpen },
  { label: "Intake Forms", value: "intake-forms", section: "Content", icon: ClipboardList },
  // Settings
  { label: "Organization Info", value: "org-info", section: "Settings", icon: Building },
  { label: "Taxes", value: "taxes", section: "Settings", icon: Percent },
  { label: "Auth & Pages", value: "auth-pages", section: "Settings", icon: Lock },
  { label: "Forms", value: "forms-tab", section: "Settings", icon: LayoutTemplate },
  { label: "Email Templates", value: "email-templates", section: "Settings", icon: Mail },
  { label: "References", value: "references", section: "Settings", icon: Link2 },
  { label: "Custom Domains", value: "domains", section: "Settings", icon: Globe },
  // Integrations
  { label: "Connect Services", value: "integrations", section: "Integrations", icon: Puzzle },
  { label: "API", value: "api", section: "Integrations", icon: Code2 },
  { label: "Webhooks", value: "webhooks", section: "Integrations", icon: Zap },
  { label: "Logs", value: "sync", section: "Integrations", icon: Activity },
  // Platform
  { label: "Partner Orgs", value: "tenants", section: "Platform", icon: Building2 },
  { label: "Plans", value: "plans", section: "Platform", icon: LayoutGrid },
  { label: "Partner Subscriptions", value: "partner-subscriptions", section: "Platform", icon: RefreshCw },
  { label: "Partner Orders", value: "partner-orders", section: "Platform", icon: Package },
  { label: "Partner Submissions", value: "partner-submissions", section: "Platform", icon: FileText },
  { label: "Billing Settings", value: "billing-settings", section: "Platform", icon: Receipt },
  { label: "Currencies", value: "currencies", section: "Platform", icon: Coins },
  // My Billing
  { label: "Plan & Billing", value: "plan-billing", section: "My Billing", icon: Wallet },
  { label: "My Subscriptions", value: "my-subscriptions", section: "My Billing", icon: Repeat2 },
  { label: "My Orders", value: "my-orders", section: "My Billing", icon: Package },
  { label: "My Submissions", value: "my-submissions", section: "My Billing", icon: ClipboardList },
];

interface CommandPaletteProps {
  onNavigate: (tab: string) => void;
  open: boolean;
  onClose: () => void;
}

export function CommandPalette({ onNavigate, open, onClose }: CommandPaletteProps) {
  const [query, setQuery] = useState("");

  const handleSelect = useCallback((value: string) => {
    onNavigate(value);
    onClose();
    setQuery("");
  }, [onNavigate, onClose]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  // Reset query when closed
  useEffect(() => { if (!open) setQuery(""); }, [open]);

  if (!open) return null;

  const filtered = query.trim()
    ? NAV_ITEMS.filter(i =>
        i.label.toLowerCase().includes(query.toLowerCase()) ||
        i.section.toLowerCase().includes(query.toLowerCase())
      )
    : NAV_ITEMS;

  const sections = Array.from(new Set(filtered.map(i => i.section)));

  return (
    <div className="aa-cmd-backdrop" onClick={onClose} data-testid="command-palette-backdrop">
      <div className="aa-cmd-panel" onClick={e => e.stopPropagation()} data-testid="command-palette">
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b" style={{ borderColor: "color-mix(in srgb, var(--aa-border) 60%, transparent)" }}>
          <Search size={16} style={{ color: "var(--aa-muted)", flexShrink: 0 }} />
          <input
            autoFocus
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search pages, settings…"
            className="flex-1 bg-transparent text-sm outline-none placeholder:text-[var(--aa-muted)]"
            style={{ color: "var(--aa-text)", fontFamily: "Space Grotesk, sans-serif" }}
            data-testid="command-palette-input"
          />
          <div className="flex items-center gap-1">
            {query && (
              <button onClick={() => setQuery("")} className="p-1 rounded hover:opacity-70 transition-opacity">
                <X size={12} style={{ color: "var(--aa-muted)" }} />
              </button>
            )}
            <span className="aa-kbd">esc</span>
          </div>
        </div>

        {/* Results */}
        <div className="overflow-y-auto" style={{ maxHeight: "380px" }}>
          {filtered.length === 0 ? (
            <div className="py-12 text-center">
              <p className="text-sm" style={{ color: "var(--aa-muted)" }}>No results for "{query}"</p>
            </div>
          ) : (
            sections.map(section => {
              const items = filtered.filter(i => i.section === section);
              return (
                <div key={section}>
                  <p className="px-4 pt-3 pb-1 text-[10px] font-bold uppercase tracking-widest" style={{ color: "var(--aa-muted)", opacity: 0.6 }}>
                    {section}
                  </p>
                  {items.map(item => {
                    const Icon = item.icon;
                    return (
                      <button
                        key={item.value}
                        onClick={() => handleSelect(item.value)}
                        className="w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors text-left hover:bg-[var(--aa-surface)]"
                        style={{ color: "var(--aa-text)" }}
                        data-testid={`cmd-item-${item.value}`}
                      >
                        <div className="flex items-center justify-center w-7 h-7 rounded-lg flex-shrink-0"
                          style={{ background: "color-mix(in srgb, var(--aa-accent) 10%, transparent)", color: "var(--aa-accent)" }}>
                          <Icon size={14} />
                        </div>
                        <span className="font-medium">{item.label}</span>
                        <span className="ml-auto text-xs" style={{ color: "var(--aa-muted)", opacity: 0.6 }}>{section}</span>
                      </button>
                    );
                  })}
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-2.5 border-t" style={{ borderColor: "color-mix(in srgb, var(--aa-border) 60%, transparent)" }}>
          <div className="flex items-center gap-3 text-[10px]" style={{ color: "var(--aa-muted)" }}>
            <span><span className="aa-kbd">↑↓</span> navigate</span>
            <span><span className="aa-kbd">↵</span> open</span>
          </div>
          <span className="text-[10px]" style={{ color: "var(--aa-muted)", opacity: 0.5 }}>{filtered.length} results</span>
        </div>
      </div>
    </div>
  );
}
