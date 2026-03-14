import { useEffect, useState, useCallback, useRef } from "react";
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
  const [activeIndex, setActiveIndex] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const filtered = query.trim()
    ? NAV_ITEMS.filter(i =>
        i.label.toLowerCase().includes(query.toLowerCase()) ||
        i.section.toLowerCase().includes(query.toLowerCase())
      )
    : NAV_ITEMS;

  // Always-current refs — handler reads from these, never stale
  const filteredRef = useRef(filtered);
  filteredRef.current = filtered;
  const activeIndexRef = useRef(activeIndex);
  activeIndexRef.current = activeIndex;

  const handleSelect = useCallback((value: string) => {
    onNavigate(value);
    onClose();
    setQuery("");
    setActiveIndex(0);
  }, [onNavigate, onClose]);

  // Reset active index to 0 when query changes
  useEffect(() => { setActiveIndex(0); }, [query]);

  // Scroll active item into view
  useEffect(() => {
    if (!listRef.current) return;
    const active = listRef.current.querySelector('[data-cmd-active="true"]') as HTMLElement;
    if (active) active.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [activeIndex]);

  // Stable keyboard handler — uses refs so it never needs to be re-registered on query/index changes
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") { onClose(); return; }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIndex(i => {
          const next = Math.min(i + 1, filteredRef.current.length - 1);
          return next;
        });
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIndex(i => Math.max(i - 1, 0));
        return;
      }
      if (e.key === "Enter") {
        e.preventDefault();
        const item = filteredRef.current[activeIndexRef.current];
        if (item) handleSelect(item.value);
        return;
      }
    };
    window.addEventListener("keydown", handler, true); // capture phase — fires before input handles it
    return () => window.removeEventListener("keydown", handler, true);
  }, [open, onClose, handleSelect]); // NO filtered/activeIndex in deps

  // Reset when palette closes
  useEffect(() => {
    if (!open) { setQuery(""); setActiveIndex(0); }
  }, [open]);

  // Re-focus input after arrow key navigation
  useEffect(() => {
    if (open && inputRef.current) inputRef.current.focus();
  }, [activeIndex, open]);

  if (!open) return null;

  const sections = Array.from(new Set(filtered.map(i => i.section)));
  let globalItemIndex = 0;

  return (
    <div className="aa-cmd-backdrop" onClick={onClose} data-testid="command-palette-backdrop">
      <div className="aa-cmd-panel" onClick={e => e.stopPropagation()} data-testid="command-palette">
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b" style={{ borderColor: "color-mix(in srgb, var(--aa-border) 60%, transparent)" }}>
          <Search size={16} style={{ color: "var(--aa-muted)", flexShrink: 0 }} />
          <input
            ref={inputRef}
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
              <button onClick={() => { setQuery(""); inputRef.current?.focus(); }} className="p-1 rounded hover:opacity-70 transition-opacity">
                <X size={12} style={{ color: "var(--aa-muted)" }} />
              </button>
            )}
            <span className="aa-kbd">esc</span>
          </div>
        </div>

        {/* Results */}
        <div ref={listRef} className="overflow-y-auto" style={{ maxHeight: "380px" }}>
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
                    const itemIdx = globalItemIndex++;
                    const isActive = itemIdx === activeIndex;
                    return (
                      <button
                        key={item.value}
                        onClick={() => handleSelect(item.value)}
                        data-cmd-active={isActive ? "true" : "false"}
                        className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-left transition-colors"
                        style={{
                          color: "var(--aa-text)",
                          backgroundColor: isActive
                            ? "color-mix(in srgb, var(--aa-accent) 8%, var(--aa-surface))"
                            : "transparent",
                          borderLeft: isActive ? "2px solid var(--aa-accent)" : "2px solid transparent",
                        }}
                        data-testid={`cmd-item-${item.value}`}
                      >
                        <div
                          className="flex items-center justify-center w-7 h-7 rounded-lg flex-shrink-0 transition-all"
                          style={{
                            background: isActive
                              ? `color-mix(in srgb, var(--aa-accent) 20%, transparent)`
                              : `color-mix(in srgb, var(--aa-accent) 10%, transparent)`,
                            color: "var(--aa-accent)",
                          }}
                        >
                          <Icon size={14} />
                        </div>
                        <span className="font-medium flex-1">{item.label}</span>
                        {isActive ? (
                          <span className="aa-kbd shrink-0">↵</span>
                        ) : (
                          <span className="text-xs shrink-0" style={{ color: "var(--aa-muted)", opacity: 0.5 }}>{section}</span>
                        )}
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
            <span><span className="aa-kbd">esc</span> close</span>
          </div>
          <span className="text-[10px]" style={{ color: "var(--aa-muted)", opacity: 0.5 }}>{filtered.length} result{filtered.length !== 1 ? "s" : ""}</span>
        </div>
      </div>
    </div>
  );
}
