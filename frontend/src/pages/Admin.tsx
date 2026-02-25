import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/contexts/AuthContext";
import { useSearchParams } from "react-router-dom";
import { useWebsite } from "@/contexts/WebsiteContext";
import { useState, useEffect, useRef } from "react";
import { getViewAsTenantId, subscribeToTenantSwitch } from "@/components/TenantSwitcher";
import { CustomersTab } from "./admin/CustomersTab";
import { SubscriptionsTab } from "./admin/SubscriptionsTab";
import { OrdersTab } from "./admin/OrdersTab";
import { UsersTab } from "./admin/UsersTab";
import { ProductsTab } from "./admin/ProductsTab";
import { CategoriesTab } from "./admin/CategoriesTab";
import { QuoteRequestsTab } from "./admin/QuoteRequestsTab";
import { ArticlesTab } from "./admin/ArticlesTab";
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

const TAB_CLASS =
  "w-full justify-start text-left text-sm px-3 py-2 h-auto rounded-none rounded-l-lg aa-tab-trigger " +
  "data-[state=inactive]:text-slate-500 hover:text-slate-700 hover:bg-slate-50 transition-colors data-[state=active]:shadow-none data-[state=active]:text-white";

export default function Admin() {
  const { user: authUser } = useAuth();
  const ws = useWebsite();
  const isSuperAdmin = authUser?.role === "super_admin" || authUser?.role === "platform_admin" || authUser?.role === "partner_super_admin";
  const isPlatformAdmin = authUser?.role === "platform_admin";

  // Reactively track whether platform admin is viewing as another tenant
  const [viewingAsTenant, setViewingAsTenant] = useState(() => !!getViewAsTenantId());
  useEffect(() => {
    return subscribeToTenantSwitch(() => setViewingAsTenant(!!getViewAsTenantId()));
  }, []);

  const showPartnerOrgs = isPlatformAdmin && !viewingAsTenant;
  // Show checklist for tenant admins OR platform admin viewing as a tenant
  const showChecklist = !isPlatformAdmin || viewingAsTenant;

  const [searchParams] = useSearchParams();
  const editArticleId = searchParams.get("editArticle");
  const defaultTab = editArticleId ? "articles" : "customers";
  const adminBadge = ws.admin_page_badge || "ADMIN";
  const adminTitle = ws.admin_page_title || "Control Panel";
  const adminSubtitle = ws.admin_page_subtitle || "";

  // Tab navigation ref for programmatic switching (used by checklist widget)
  const tabsRef = useRef<HTMLDivElement>(null);
  const [activeTab, setActiveTab] = useState(defaultTab);
  const [websiteSection, setWebsiteSection] = useState<string | undefined>(undefined);

  const handleChecklistNavigate = (tab: string, section?: string) => {
    setActiveTab(tab);
    if (tab === "website" && section) setWebsiteSection(section);
  };

  return (
    <div className="space-y-6" data-testid="admin-page">
      {/* Hero Banner */}
      <section className="relative overflow-hidden rounded-3xl px-10 py-10 shadow-[0_30px_70px_rgba(15,23,42,0.15)]" style={{ backgroundColor: "var(--aa-primary)" }}>
        <div className="pointer-events-none absolute -right-24 -top-24 h-80 w-80 rounded-full blur-3xl" style={{ backgroundColor: "color-mix(in srgb, var(--aa-accent) 10%, transparent)" }} />
        <div className="pointer-events-none absolute bottom-0 left-0 h-56 w-56 rounded-full blur-2xl" style={{ backgroundColor: "color-mix(in srgb, var(--aa-accent) 5%, transparent)" }} />
        <div className="relative space-y-3">
          <div className="flex items-center gap-2.5">
            <div className="h-0.5 w-8 rounded-full" style={{ backgroundColor: "var(--aa-accent)" }} />
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">{adminBadge}</p>
          </div>
          <h1 className="text-3xl font-bold text-white">{adminTitle}</h1>
          <p className="max-w-xl text-sm text-slate-300">{adminSubtitle}</p>
        </div>
      </section>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex gap-0" data-testid="admin-tabs" ref={tabsRef}>
        {/* Left Sidebar Navigation */}
        <div className="w-52 shrink-0 border-r border-slate-200 pr-0 mr-6 min-h-[60vh]">
          <TabsList className="flex flex-col h-auto items-stretch bg-transparent p-0 gap-0 w-full">
            {/* People */}
            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider px-3 pt-4 pb-1">People</p>
            {isSuperAdmin && (
              <TabsTrigger value="users" data-testid="admin-tab-users" className={TAB_CLASS}>Users</TabsTrigger>
            )}
            <TabsTrigger value="customers" data-testid="admin-tab-customers" className={TAB_CLASS}>Customers</TabsTrigger>

            {/* Commerce */}
            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider px-3 pt-4 pb-1">Commerce</p>
            <TabsTrigger value="catalog" data-testid="admin-tab-catalog" className={TAB_CLASS}>Products</TabsTrigger>
            <TabsTrigger value="subscriptions" data-testid="admin-tab-subscriptions" className={TAB_CLASS}>Subscriptions</TabsTrigger>
            <TabsTrigger value="orders" data-testid="admin-tab-orders" className={TAB_CLASS}>Orders</TabsTrigger>
            <TabsTrigger value="quotes" data-testid="admin-tab-quotes" className={TAB_CLASS}>Requests</TabsTrigger>

            {/* Content */}
            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider px-3 pt-4 pb-1">Content</p>
            <TabsTrigger value="articles" data-testid="admin-tab-articles" className={TAB_CLASS}>Articles</TabsTrigger>
            <TabsTrigger value="email-templates" data-testid="admin-tab-email-templates" className={TAB_CLASS}>Email Templates</TabsTrigger>
            <TabsTrigger value="references" data-testid="admin-tab-references" className={TAB_CLASS}>References</TabsTrigger>

            {/* Website & Settings */}
            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider px-3 pt-4 pb-1">Settings</p>
            <TabsTrigger value="website" data-testid="admin-tab-website" className={TAB_CLASS}>Website Content</TabsTrigger>
            <TabsTrigger value="domains" data-testid="admin-tab-domains" className={TAB_CLASS}>Custom Domains</TabsTrigger>

            {/* Integrations */}
            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider px-3 pt-4 pb-1">Integrations</p>
            <TabsTrigger value="integrations" data-testid="admin-tab-integrations" className={TAB_CLASS}>Connect Services</TabsTrigger>
            <TabsTrigger value="api" data-testid="admin-tab-api" className={TAB_CLASS}>API</TabsTrigger>
            <TabsTrigger value="webhooks" data-testid="admin-tab-webhooks" className={TAB_CLASS}>Webhooks</TabsTrigger>
            <TabsTrigger value="sync" data-testid="admin-tab-sync" className={TAB_CLASS}>Logs</TabsTrigger>

            {/* Platform — only for platform_admin when NOT viewing as a tenant */}
            {showPartnerOrgs && (
              <>
                <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider px-3 pt-4 pb-1">Platform</p>
                <TabsTrigger value="tenants" data-testid="admin-tab-tenants" className={TAB_CLASS}>Partner Orgs</TabsTrigger>
              </>
            )}
          </TabsList>
        </div>

        {/* Content Area */}
        <div className="flex-1 min-w-0">
          {showChecklist && (
            <SetupChecklistWidget onNavigate={handleChecklistNavigate} />
          )}
          {isSuperAdmin && (
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
          <TabsContent value="quotes" className="space-y-4">
            <QuoteRequestsTab />
          </TabsContent>
          <TabsContent value="articles" className="space-y-4">
            <ArticlesTab editArticleId={editArticleId || undefined} />
          </TabsContent>
          <TabsContent value="categories" className="space-y-4">
            <CategoriesTab />
          </TabsContent>
          <TabsContent value="catalog" className="space-y-4">
            <ProductsTab />
          </TabsContent>
          <TabsContent value="email-templates" className="space-y-4">
            <EmailTemplatesTab />
          </TabsContent>
          <TabsContent value="references" className="space-y-4">
            <ReferencesTab />
          </TabsContent>
          <TabsContent value="website" className="space-y-4">
            <WebsiteTab defaultSection={websiteSection as any} />
          </TabsContent>
          <TabsContent value="domains" className="space-y-4">
            <CustomDomainsTab />
          </TabsContent>
          <TabsContent value="integrations" className="space-y-4">
            <IntegrationsOverview />
          </TabsContent>
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
        </div>
      </Tabs>
    </div>
  );
}
