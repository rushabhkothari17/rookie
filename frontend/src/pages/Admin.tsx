import { useAuth } from "@/contexts/AuthContext";
import { useSearchParams } from "react-router-dom";
import { useWebsite } from "@/contexts/WebsiteContext";
import React, { useState, useEffect, useRef, useCallback } from "react";
import { Menu, X, ChevronDown, ChevronLeft, ChevronRight, Search,
  Users, UserRound, ShoppingBag, Package, RefreshCw, MessageSquare,
  BookOpen, FolderOpen, ClipboardList, Building, Percent, Lock,
  LayoutTemplate, Mail, Link2, Globe, Puzzle, Code2, Zap, Activity,
  Store, SlidersHorizontal, Wallet, CreditCard, Building2, LayoutGrid,
  Receipt, Coins, ArrowRightLeft, Repeat2, FileText, Server, Moon, Sun,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { CommandPalette } from "@/components/admin/CommandPalette";
import { CustomersTab } from "./admin/CustomersTab";
import { SubscriptionsTab } from "./admin/SubscriptionsTab";
import { OrdersTab } from "./admin/OrdersTab";
import { UsersTab } from "./admin/UsersTab";
import { ProductsTab } from "./admin/ProductsTab";
import { CategoriesTab } from "./admin/CategoriesTab";
import { EnquiriesTab } from "./admin/EnquiriesTab";
import { ResourcesTab } from "./admin/ResourcesTab";
import { AdminDocumentsTab } from "./admin/AdminDocumentsTab";
import { AdminIntakeFormsTab } from "./admin/AdminIntakeFormsTab";
import WebsiteTab from "./admin/WebsiteTab";
import { LogsTab } from "./admin/LogsTab";
import { TenantsTab } from "./admin/TenantsTab";
import { SetupChecklistWidget } from "@/components/admin/SetupChecklistWidget";
import { ApiTab } from "./admin/ApiTab";
import { WebhooksTab } from "./admin/WebhooksTab";
import { IntegrationsOverview } from "./admin/IntegrationsOverview";
import { EmailTemplatesTab } from "./admin/EmailTemplatesTab";
import { ReferencesTab } from "./admin/ReferencesTab";
import { CustomDomainsTab } from "./admin/CustomDomainsTab";
import { TaxesTab } from "./admin/TaxesTab";
import { FormsManagementTab } from "./admin/FormsManagementTab";
import { IntegrationRequestsTab } from "./admin/tabs/IntegrationRequestsTab";
import { UsageDashboard } from "./admin/UsageDashboard";
import { PlansTab } from "./admin/PlansTab";
import { PartnerOrdersTab } from "./admin/PartnerOrdersTab";
import { PartnerSubscriptionsTab } from "./admin/PartnerSubscriptionsTab";
import { MyOrdersTab } from "./admin/MyOrdersTab";
import { MySubscriptionsTab } from "./admin/MySubscriptionsTab";
import { FiltersTab } from "./admin/FiltersTab";
import { PlanBillingTab } from "./admin/PlanBillingTab";
import { MySubmissionsTab } from "./admin/MySubmissionsTab";
import { PartnerSubmissionsTab } from "./admin/PartnerSubmissionsTab";
import { BillingSettingsTab } from "./admin/BillingSettingsTab";
import { CurrenciesTab } from "./admin/CurrenciesTab";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

/** Icon map for every tab value */
const TAB_ICONS: Record<string, React.ElementType> = {
  tenants: Building2, plans: LayoutGrid,
  "partner-subscriptions": RefreshCw, "partner-orders": Package,
  "partner-submissions": FileText, "billing-settings": Receipt,
  currencies: Coins, "plan-billing": Wallet,
  "my-subscriptions": Repeat2, "my-orders": Package,
  "my-submissions": ClipboardList,
  users: Users, customers: UserRound,
  catalog: Store, filters: SlidersHorizontal,
  subscriptions: Repeat2, orders: ShoppingBag,
  enquiries: MessageSquare,
  resources: BookOpen, documents: FolderOpen,
  "intake-forms": ClipboardList,
  "org-info": Building, taxes: Percent,
  "auth-pages": Lock, "forms-tab": LayoutTemplate,
  "email-templates": Mail, references: Link2,
  domains: Globe, integrations: Puzzle,
  "integration-requests": ArrowRightLeft,
  api: Code2, webhooks: Zap, sync: Activity,
};

/** Icon map for each section */
const SECTION_ICONS: Record<string, React.ElementType> = {
  platform: Server, "my-billing": CreditCard,
  people: Users, commerce: ShoppingBag,
  content: BookOpen, settings: LayoutTemplate,
  integrations: Puzzle,
};

const TAB_CLASS =
  "w-full justify-start text-left text-sm px-3 py-2 h-auto rounded-none rounded-l-lg aa-tab-trigger " +
  "data-[state=inactive]:text-[var(--aa-muted)] hover:text-[var(--aa-text)] hover:translate-x-0.5 hover:bg-[var(--aa-surface)] " +
  "transition-all duration-150 data-[state=active]:shadow-none";

/** Context to share active tab + setter — avoids prop drilling through 32 usages */
const ActiveTabCtx = React.createContext<string>("");
const SetTabCtx = React.createContext<(v: string) => void>(() => {});
const CollapsedCtx = React.createContext<boolean>(false);

/** Sidebar tab — plain button for full CSS control, no shadcn style conflicts */
const SideTab = ({ value, label, testId }: { value: string; label: string; testId?: string }) => {
  const activeTab = React.useContext(ActiveTabCtx);
  const setTab = React.useContext(SetTabCtx);
  const collapsed = React.useContext(CollapsedCtx);
  const isActive = activeTab === value;
  const Icon = TAB_ICONS[value] || LayoutGrid;

  return (
    <button
      type="button"
      onClick={() => setTab(value)}
      title={collapsed ? label : undefined}
      className={`aa-nav-item ${isActive ? "active" : ""} ${collapsed ? "justify-center !px-0" : ""}`}
      data-testid={testId || `tab-${value}`}
      aria-selected={isActive}
    >
      <Icon size={15} className="aa-nav-icon" />
      {!collapsed && <span className="truncate">{label}</span>}
    </button>
  );
};

/** Accordion section header with section icon */
const SectionHeader = ({
  label, sectionId, expanded, onToggle,
}: { label: string; sectionId: string; expanded: boolean; onToggle: (id: string) => void }) => {
  const collapsed = React.useContext(CollapsedCtx);
  const SectionIcon = SECTION_ICONS[sectionId] || LayoutGrid;

  if (collapsed) {
    return (
      <div className="px-2 pt-3 pb-1 flex justify-center">
        <div className="w-full h-px" style={{ background: "color-mix(in srgb, var(--aa-border) 50%, transparent)" }} />
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={() => onToggle(sectionId)}
      className="aa-section-header w-full"
      aria-expanded={expanded}
      data-testid={`admin-section-${sectionId}`}
    >
      <SectionIcon size={11} style={{ opacity: 0.5, flexShrink: 0 }} />
      <span className="flex-1 text-left">{label}</span>
      <ChevronDown size={11} className={`transition-transform duration-200 ${expanded ? "" : "-rotate-90"}`} style={{ opacity: 0.5 }} />
    </button>
  );
};
const TAB_SECTIONS: Record<string, string> = {
  tenants: "platform", plans: "platform", "partner-subscriptions": "platform",
  "partner-orders": "platform", "partner-submissions": "platform",
  "billing-settings": "platform", currencies: "platform",
  "plan-billing": "my-billing", "my-subscriptions": "my-billing",
  "my-orders": "my-billing", "my-submissions": "my-billing",
  users: "people", customers: "people",
  catalog: "commerce", filters: "commerce", subscriptions: "commerce",
  orders: "commerce", enquiries: "commerce",
  resources: "content", documents: "content", "intake-forms": "content",
  "org-info": "settings", taxes: "settings", "auth-pages": "settings",
  "forms-tab": "settings", "email-templates": "settings",
  references: "settings", domains: "settings",
  integrations: "integrations", "integration-requests": "integrations",
  api: "integrations", webhooks: "integrations", sync: "integrations",
};

/** Accordion section header for the admin sidebar — new version defined above */

export default function Admin() {
  const { user: authUser, permissions } = useAuth();
  const ws = useWebsite();
  const isSuperAdmin = authUser?.role === "platform_super_admin" || authUser?.role === "partner_super_admin" || authUser?.role === "super_admin";
  const isPlatformAdmin = authUser?.role === "platform_admin" || authUser?.role === "platform_super_admin";
  const isPlatformSuperAdmin = authUser?.role === "platform_super_admin";

  // Permissions helpers
  const hasModule = (module: string): boolean => {
    if (isSuperAdmin || isPlatformAdmin) return true;
    const mp = permissions?.module_permissions;
    if (mp && Object.keys(mp).length > 0) return !!mp[module];
    return permissions?.modules?.includes(module) ?? false;
  };

  const hasWrite = (module: string): boolean => {
    if (isSuperAdmin || isPlatformAdmin) return true;
    const mp = permissions?.module_permissions;
    if (mp) return mp[module] === "write";
    return false;
  };

  const showPartnerOrgs = isPlatformAdmin;
  const isPartnerAdmin = (authUser?.role === "partner_admin" || authUser?.role === "partner_super_admin") && !isPlatformAdmin;
  const showChecklist = !isPlatformAdmin;

  const [searchParams] = useSearchParams();
  const editResourceId = searchParams.get("editArticle") || searchParams.get("editResource");
  const defaultTab = editResourceId ? "resources" : "customers";
  const adminBadge = ws.admin_page_badge || "ADMIN";
  const adminTitle = ws.admin_page_title || "Control Panel";
  const adminSubtitle = ws.admin_page_subtitle || "";

  // Tab navigation ref for programmatic switching (used by checklist widget)
  const tabsRef = useRef<HTMLDivElement>(null);
  const [activeTab, setActiveTab] = useState(() => {
    const urlTab = searchParams.get("tab");
    if (urlTab) return urlTab;
    if (searchParams.get("editArticle") || searchParams.get("editResource")) return "resources";
    try { return localStorage.getItem("admin_active_tab") || "customers"; } catch { return "customers"; }
  });
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try { return localStorage.getItem("admin_sidebar_collapsed") === "true"; } catch { return false; }
  });
  const [cmdOpen, setCmdOpen] = useState(false);
  const [darkMode, setDarkMode] = useState(() => {
    try { return localStorage.getItem("aa_dark_mode") === "true"; } catch { return false; }
  });

  // Apply / remove .aa-dark on <html> whenever darkMode changes
  useEffect(() => {
    const html = document.documentElement;
    if (darkMode) {
      html.classList.add("aa-dark");
    } else {
      html.classList.remove("aa-dark");
    }
    try { localStorage.setItem("aa_dark_mode", String(darkMode)); } catch {}
  }, [darkMode]);
  const toggleCollapsed = () => {
    setSidebarCollapsed(prev => {
      const next = !prev;
      try { localStorage.setItem("admin_sidebar_collapsed", String(next)); } catch {}
      return next;
    });
  };

  // Accordion: expand the section that contains the active tab; only one open at a time
  const [expandedSection, setExpandedSection] = useState<string>(() => {
    const tab = (() => { try { return localStorage.getItem("admin_active_tab") || "customers"; } catch { return "customers"; } })();
    return TAB_SECTIONS[tab] || "people";
  });
  useEffect(() => {
    const s = TAB_SECTIONS[activeTab];
    if (s) setExpandedSection(s);
  }, [activeTab]);
  const toggleSection = (id: string) => setExpandedSection(prev => prev === id ? "" : id);

  useEffect(() => {
    try { localStorage.setItem("admin_active_tab", activeTab); } catch {}
  }, [activeTab]);

  const handleChecklistNavigate = (tab: string, section?: string) => {
    if (tab === "website") {
      setActiveTab(section === "auth" ? "auth-pages" : section === "forms" ? "forms-tab" : "org-info");
      return;
    }
    setActiveTab(tab);
    setSidebarOpen(false);
  };

  // ⌘K / Ctrl+K global shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCmdOpen(prev => !prev);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return (
    <>
    <CommandPalette open={cmdOpen} onClose={() => setCmdOpen(false)} onNavigate={(tab) => { setActiveTab(tab); setSidebarOpen(false); }} />
    <div className="space-y-6" data-testid="admin-page">
      {/* Hero Banner */}
      <section className="relative overflow-hidden rounded-3xl px-6 md:px-10 py-8 md:py-10 shadow-[0_30px_70px_rgba(15,23,42,0.15)] aa-grid-texture" style={{ backgroundColor: "var(--aa-primary)" }}>
        <div className="pointer-events-none absolute -right-24 -top-24 h-80 w-80 rounded-full blur-3xl" style={{ backgroundColor: "color-mix(in srgb, var(--aa-accent) 10%, transparent)" }} />
        <div className="pointer-events-none absolute bottom-0 left-0 h-56 w-56 rounded-full blur-2xl" style={{ backgroundColor: "color-mix(in srgb, var(--aa-accent) 5%, transparent)" }} />
        <div className="relative flex items-start justify-between gap-4">
          <div className="space-y-3">
            <div className="flex items-center gap-2.5">
              <div className="h-0.5 w-8 rounded-full" style={{ backgroundColor: "var(--aa-accent)" }} />
              <p className="text-xs font-semibold uppercase tracking-[0.3em]" style={{ color: "var(--aa-primary-fg)", opacity: 0.6 }}>{adminBadge}</p>
            </div>
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight" style={{ color: "var(--aa-primary-fg)" }}>{adminTitle}</h1>
            <p className="max-w-xl text-sm" style={{ color: "var(--aa-primary-fg)", opacity: 0.7 }}>{adminSubtitle}</p>
          </div>
          {/* ⌘K hint */}
          <button
            onClick={() => setCmdOpen(true)}
            className="hidden md:flex items-center gap-2 px-3 py-2 rounded-xl text-sm transition-all duration-150 hover:scale-105"
            style={{ background: "rgba(255,255,255,0.1)", border: "1px solid rgba(255,255,255,0.15)", color: "var(--aa-primary-fg)", backdropFilter: "blur(8px)" }}
            data-testid="cmd-open-btn"
          >
            <Search size={14} />
            <span style={{ opacity: 0.8 }}>Quick search</span>
            <span className="aa-kbd" style={{ background: "rgba(255,255,255,0.12)", border: "1px solid rgba(255,255,255,0.2)", color: "var(--aa-primary-fg)" }}>⌘K</span>
          </button>
        </div>
      </section>

      <Tabs value={activeTab} onValueChange={(t) => { setActiveTab(t); setSidebarOpen(false); }} className="flex gap-0 relative" data-testid="admin-tabs" ref={tabsRef}>

        {/* Mobile sidebar overlay backdrop */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 z-30 bg-black/30 md:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Mobile sidebar toggle button */}
        <div className="md:hidden flex items-center gap-2 mb-2">
          <Button
            variant="outline"
            size="sm"
            className="gap-2"
            style={{ color: "var(--aa-text)", borderColor: "var(--aa-border)" }}
            onClick={() => setSidebarOpen(v => !v)}
            data-testid="admin-sidebar-toggle"
          >
            <Menu size={15} />
            <span className="capitalize">{activeTab.replace(/-/g, " ")}</span>
          </Button>
        </div>

        {/* Left Sidebar Navigation */}
        <div className={`
          fixed md:relative inset-y-0 left-0 z-40 md:z-auto
          shrink-0 aa-sidebar
          shadow-xl md:shadow-none
          transform transition-all duration-200 ease-in-out
          ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}
          md:translate-x-0 md:block
          overflow-y-auto overflow-x-hidden
          min-h-screen md:min-h-[60vh]
          flex flex-col mr-4
        `}
        style={{
          width: sidebarCollapsed ? "64px" : "210px",
          transition: "width 0.2s cubic-bezier(0.16,1,0.3,1)",
          borderColor: "color-mix(in srgb, var(--aa-border) 70%, transparent)",
        }}>
          {/* Mobile close button */}
          <div className="md:hidden flex items-center justify-between px-4 py-3" style={{ borderBottom: "1px solid var(--aa-border)" }}>
            <span className="text-sm font-semibold" style={{ color: "var(--aa-text)" }}>Navigation</span>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setSidebarOpen(false)}>
              <X size={16} />
            </Button>
          </div>

          {/* ⌘K search trigger (expanded only) */}
          {!sidebarCollapsed && (
            <button
              className="aa-search-trigger mx-1 mt-2"
              onClick={() => setCmdOpen(true)}
              data-testid="sidebar-search-trigger"
            >
              <Search size={12} />
              <span className="flex-1 text-left text-xs truncate">Search…</span>
              <span className="aa-kbd">⌘K</span>
            </button>
          )}
          {sidebarCollapsed && (
            <button
              className="flex items-center justify-center py-3 w-full hover:opacity-80 transition-opacity"
              onClick={() => setCmdOpen(true)}
              data-testid="sidebar-search-icon"
            >
              <Search size={14} style={{ color: "var(--aa-muted)" }} />
            </button>
          )}

          <ActiveTabCtx.Provider value={activeTab}>
          <CollapsedCtx.Provider value={sidebarCollapsed}>
          <SetTabCtx.Provider value={(v) => { setActiveTab(v); setSidebarOpen(false); try { localStorage.setItem("admin_active_tab", v); } catch {} }}>
          <div className="flex flex-col gap-0.5 w-full px-1 pb-1 flex-1">
            {/* ── PLATFORM section (platform_admin only, not viewing as tenant) ── */}
            {showPartnerOrgs && (
              <>
                <SectionHeader label="Platform" sectionId="platform" expanded={expandedSection === "platform"} onToggle={toggleSection} />
                {expandedSection === "platform" && (
                  <>
                    <SideTab value="tenants" testId="admin-tab-tenants" label="Partner Orgs" />
                    <SideTab value="plans" testId="admin-tab-plans" label="Plans" />
                    <SideTab value="partner-subscriptions" testId="admin-tab-partner-subscriptions" label="Partner Subscriptions" />
                    <SideTab value="partner-orders" testId="admin-tab-partner-orders" label="Partner Orders" />
                    <SideTab value="partner-submissions" testId="admin-tab-partner-submissions" label="Partner Submissions" />
                    <SideTab value="billing-settings" testId="admin-tab-billing-settings" label="Billing Settings" />
                    {authUser?.role === "platform_super_admin" && (
                      <SideTab value="currencies" testId="admin-tab-currencies" label="Supported Currencies" />
                    )}
                  </>
                )}
              </>
            )}

            {/* ── MY BILLING section (partner admins only) ── */}
            {isPartnerAdmin && (
              <>
                <SectionHeader label="My Billing" sectionId="my-billing" expanded={expandedSection === "my-billing"} onToggle={toggleSection} />
                {expandedSection === "my-billing" && (
                  <>
                    <SideTab value="plan-billing" testId="admin-tab-plan-billing" label="Plan &amp; Billing" />
                    <SideTab value="my-subscriptions" testId="admin-tab-my-subscriptions" label="My Subscriptions" />
                    <SideTab value="my-orders" testId="admin-tab-my-orders" label="My Orders" />
                    <SideTab value="my-submissions" testId="admin-tab-my-submissions" label="My Submissions" />
                  </>
                )}
              </>
            )}

            {/* ── PEOPLE section ── */}
            {(isSuperAdmin || hasModule("users") || hasModule("customers")) && (
              <>
                <SectionHeader label="People" sectionId="people" expanded={expandedSection === "people"} onToggle={toggleSection} />
                {expandedSection === "people" && (
                  <>
                    {(isSuperAdmin || hasModule("users")) && (
                      <SideTab value="users" testId="admin-tab-users" label="Users" />
                    )}
                    {hasModule("customers") && <SideTab value="customers" testId="admin-tab-customers" label="Customers" />}
                  </>
                )}
              </>
            )}

            {/* ── COMMERCE section ── */}
            {(hasModule("orders") || hasModule("subscriptions") || hasModule("products")) && (
              <>
                <SectionHeader label="Commerce" sectionId="commerce" expanded={expandedSection === "commerce"} onToggle={toggleSection} />
                {expandedSection === "commerce" && (
                  <>
                    {hasModule("products") && <SideTab value="catalog" testId="admin-tab-catalog" label="Products" />}
                    {hasModule("products") && <SideTab value="filters" testId="admin-tab-filters" label="Filters" />}
                    {hasModule("subscriptions") && <SideTab value="subscriptions" testId="admin-tab-subscriptions" label="Subscriptions" />}
                    {hasModule("orders") && <SideTab value="orders" testId="admin-tab-orders" label="Orders" />}
                    {hasModule("customers") && <SideTab value="enquiries" testId="admin-tab-enquiries" label="Enquiries" />}
                  </>
                )}
              </>
            )}

            {/* ── CONTENT section ── */}
            {hasModule("content") && (
              <>
                <SectionHeader label="Content" sectionId="content" expanded={expandedSection === "content"} onToggle={toggleSection} />
                {expandedSection === "content" && (
                  <>
                    <SideTab value="resources" testId="admin-tab-resources" label="Resources" />
                    <SideTab value="documents" testId="admin-tab-documents" label="Documents" />
                    <SideTab value="intake-forms" testId="admin-tab-intake-forms" label="Intake Forms" />
                  </>
                )}
              </>
            )}

            {/* ── SETTINGS section ── */}
            {hasModule("settings") && (
              <>
                <SectionHeader label="Settings" sectionId="settings" expanded={expandedSection === "settings"} onToggle={toggleSection} />
                {expandedSection === "settings" && (
                  <>
                    <SideTab value="org-info" testId="admin-tab-org-info" label="Organization Info" />
                    <SideTab value="taxes" testId="admin-tab-taxes" label="Taxes" />
                    <SideTab value="auth-pages" testId="admin-tab-auth-pages" label="Auth &amp; Pages" />
                    <SideTab value="forms-tab" testId="admin-tab-forms" label="Forms" />
                    <SideTab value="email-templates" testId="admin-tab-email-templates" label="Email Templates" />
                    <SideTab value="references" testId="admin-tab-references" label="References" />
                    <SideTab value="domains" testId="admin-tab-domains" label="Custom Domains" />
                  </>
                )}
              </>
            )}

            {/* ── INTEGRATIONS section ── */}
            {hasModule("integrations") && (
              <>
                <SectionHeader label="Integrations" sectionId="integrations" expanded={expandedSection === "integrations"} onToggle={toggleSection} />
                {expandedSection === "integrations" && (
                  <>
                    <SideTab value="integrations" testId="admin-tab-integrations" label="Connect Services" />
                    {isPlatformAdmin && (
                      <SideTab value="integration-requests" testId="admin-tab-integration-requests" label="Integration Requests" />
                    )}
                    <SideTab value="api" testId="admin-tab-api" label="API" />
                    {hasModule("webhooks") && <SideTab value="webhooks" testId="admin-tab-webhooks" label="Webhooks" />}
                    {hasModule("logs") && <SideTab value="sync" testId="admin-tab-sync" label="Logs" />}
                  </>
                )}
              </>
            )}

          </div>
          </SetTabCtx.Provider>
          </CollapsedCtx.Provider>
          </ActiveTabCtx.Provider>

          {/* Dark mode toggle */}
          <button
            type="button"
            onClick={() => setDarkMode(d => !d)}
            className="aa-collapse-btn hidden md:flex"
            data-testid="dark-mode-toggle"
            title={darkMode ? "Switch to light mode" : "Switch to dark mode"}
          >
            {darkMode
              ? <><Sun size={14} />{!sidebarCollapsed && <span>Light Mode</span>}</>
              : <><Moon size={14} />{!sidebarCollapsed && <span>Dark Mode</span>}</>
            }
          </button>

          {/* Collapse toggle */}
          <button
            type="button"
            onClick={toggleCollapsed}
            className="aa-collapse-btn hidden md:flex"
            data-testid="sidebar-collapse-btn"
            title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {sidebarCollapsed
              ? <ChevronRight size={14} />
              : <><ChevronLeft size={14} /><span>Collapse</span></>
            }
          </button>
        </div>

        {/* Content Area */}
        <div className="flex-1 min-w-0 overflow-x-auto"  style={{ minWidth: 0 }}>
          {showChecklist && (
            <SetupChecklistWidget onNavigate={handleChecklistNavigate} />
          )}
          {(isSuperAdmin || hasModule("users")) && (
            <TabsContent value="users" className="space-y-4">
              <UsersTab />
            </TabsContent>
          )}
          <TabsContent value="customers" className="space-y-4">
            <CustomersTab />
          </TabsContent>
          <TabsContent value="subscriptions" className="space-y-4">
            <SubscriptionsTab />
          </TabsContent>
          <TabsContent value="orders" className="space-y-4">
            <OrdersTab />
          </TabsContent>
          <TabsContent value="enquiries" className="space-y-4">
            <EnquiriesTab />
          </TabsContent>
          <TabsContent value="taxes" className="space-y-4">
            <TaxesTab />
          </TabsContent>
          <TabsContent value="resources" className="space-y-4">
            <ResourcesTab editResourceId={editResourceId || undefined} />
          </TabsContent>
          <TabsContent value="documents" className="space-y-4">
            <AdminDocumentsTab onNavigateToTab={setActiveTab} />
          </TabsContent>
          <TabsContent value="intake-forms" className="space-y-4">
            <AdminIntakeFormsTab />
          </TabsContent>
          <TabsContent value="categories" className="space-y-4">
            <CategoriesTab />
          </TabsContent>
          <TabsContent value="catalog" className="space-y-4">
            <ProductsTab />
          </TabsContent>
          <TabsContent value="filters" className="space-y-4">
            <FiltersTab />
          </TabsContent>
          <TabsContent value="email-templates" className="space-y-4">
            <EmailTemplatesTab />
          </TabsContent>
          <TabsContent value="references" className="space-y-4">
            <ReferencesTab />
          </TabsContent>
          <TabsContent value="org-info" className="space-y-4">
            <WebsiteTab forcedSection="branding" />
          </TabsContent>
          <TabsContent value="auth-pages" className="space-y-4">
            <WebsiteTab forcedSection="auth" />
          </TabsContent>
          <TabsContent value="forms-tab" className="space-y-4">
            <FormsManagementTab />
          </TabsContent>
          <TabsContent value="domains" className="space-y-4">
            <CustomDomainsTab />
          </TabsContent>
          <TabsContent value="integrations" className="space-y-4">
            <IntegrationsOverview />
          </TabsContent>
          {isPlatformAdmin && (
            <TabsContent value="integration-requests" className="space-y-4">
              <IntegrationRequestsTab />
            </TabsContent>
          )}
          <TabsContent value="api" className="space-y-4">
            <ApiTab />
          </TabsContent>
          <TabsContent value="webhooks" className="space-y-4">
            <WebhooksTab />
          </TabsContent>
          <TabsContent value="sync" className="space-y-4">
            <LogsTab />
          </TabsContent>
          {showPartnerOrgs && (
            <TabsContent value="tenants" className="space-y-4">
              <TenantsTab />
            </TabsContent>
          )}
          {showPartnerOrgs && (
            <TabsContent value="plans" className="space-y-4">
              <PlansTab />
            </TabsContent>
          )}
          {showPartnerOrgs && (
            <TabsContent value="partner-subscriptions" className="space-y-4">
              <PartnerSubscriptionsTab />
            </TabsContent>
          )}
          {showPartnerOrgs && (
            <TabsContent value="partner-orders" className="space-y-4">
              <PartnerOrdersTab />
            </TabsContent>
          )}
          {showPartnerOrgs && (
            <TabsContent value="partner-submissions" className="space-y-4">
              <PartnerSubmissionsTab />
            </TabsContent>
          )}
          {showPartnerOrgs && (
            <TabsContent value="billing-settings" className="space-y-4">
              <BillingSettingsTab />
            </TabsContent>
          )}
          {showPartnerOrgs && authUser?.role === "platform_super_admin" && (
            <TabsContent value="currencies" className="space-y-4">
              <CurrenciesTab />
            </TabsContent>
          )}
          {isPlatformAdmin && (
            <TabsContent value="usage" className="space-y-4">
              <UsageDashboard />
            </TabsContent>
          )}
          {isPartnerAdmin && (
            <TabsContent value="plan-billing" className="space-y-4">
              <PlanBillingTab />
            </TabsContent>
          )}
          {isPartnerAdmin && (
            <TabsContent value="my-subscriptions" className="space-y-4">
              <MySubscriptionsTab />
            </TabsContent>
          )}
          {isPartnerAdmin && (
            <TabsContent value="my-orders" className="space-y-4">
              <MyOrdersTab />
            </TabsContent>
          )}
          {isPartnerAdmin && (
            <TabsContent value="my-submissions" className="space-y-4">
              <MySubmissionsTab />
            </TabsContent>
          )}
        </div>
      </Tabs>
    </div>
    </>
  );
}
