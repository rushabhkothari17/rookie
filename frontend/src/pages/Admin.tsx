import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/contexts/AuthContext";
import { useSearchParams } from "react-router-dom";
import { CustomersTab } from "./admin/CustomersTab";
import { SubscriptionsTab } from "./admin/SubscriptionsTab";
import { OrdersTab } from "./admin/OrdersTab";
import { PromoCodesTab } from "./admin/PromoCodesTab";
import { TermsTab } from "./admin/TermsTab";
import { UsersTab } from "./admin/UsersTab";
import { ProductsTab } from "./admin/ProductsTab";
import { CategoriesTab } from "./admin/CategoriesTab";
import { QuoteRequestsTab } from "./admin/QuoteRequestsTab";
import { BankTransactionsTab } from "./admin/BankTransactionsTab";
import { OverrideCodesTab } from "./admin/OverrideCodesTab";
import { ArticlesTab } from "./admin/ArticlesTab";
import WebsiteTab from "./admin/WebsiteTab";
import { LogsTab } from "./admin/LogsTab";

const TAB_CLASS =
  "w-full justify-start text-left text-sm px-3 py-2 h-auto rounded-none rounded-l-lg " +
  "data-[state=active]:bg-slate-900 data-[state=active]:text-white data-[state=active]:shadow-none " +
  "data-[state=inactive]:text-slate-500 hover:text-slate-700 hover:bg-slate-50 transition-colors";

export default function Admin() {
  const { user: authUser } = useAuth();
  const isSuperAdmin = authUser?.role === "super_admin";
  const [searchParams] = useSearchParams();
  const editArticleId = searchParams.get("editArticle");
  const defaultTab = editArticleId ? "articles" : "customers";

  return (
    <div className="space-y-6" data-testid="admin-page">
      {/* Hero Banner — matches store homepage style */}
      <section className="relative overflow-hidden rounded-3xl bg-[#0f172a] px-10 py-10 shadow-[0_30px_70px_rgba(15,23,42,0.15)]">
        <div className="pointer-events-none absolute -right-24 -top-24 h-80 w-80 rounded-full bg-red-600/10 blur-3xl" />
        <div className="pointer-events-none absolute bottom-0 left-0 h-56 w-56 rounded-full bg-red-600/5 blur-2xl" />
        <div className="relative space-y-3">
          <div className="flex items-center gap-2.5">
            <div className="h-0.5 w-8 rounded-full bg-red-500" />
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Administration</p>
          </div>
          <h1 className="text-3xl font-bold text-white">Admin Control Centre</h1>
          <p className="max-w-xl text-sm text-slate-300">Manage customers, orders, products, and website content from one place.</p>
        </div>
      </section>

      <Tabs defaultValue="customers" className="flex gap-0" data-testid="admin-tabs">
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
            <TabsTrigger value="subscriptions" data-testid="admin-tab-subscriptions" className={TAB_CLASS}>Subscriptions</TabsTrigger>
            <TabsTrigger value="orders" data-testid="admin-tab-orders" className={TAB_CLASS}>Orders</TabsTrigger>
            <TabsTrigger value="promo" data-testid="admin-tab-promo" className={TAB_CLASS}>Promo Codes</TabsTrigger>
            <TabsTrigger value="quotes" data-testid="admin-tab-quotes" className={TAB_CLASS}>Quote Requests</TabsTrigger>
            <TabsTrigger value="bank-transactions" data-testid="admin-tab-bank-transactions" className={TAB_CLASS}>Bank Transactions</TabsTrigger>

            {/* Content */}
            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider px-3 pt-4 pb-1">Content</p>
            <TabsTrigger value="articles" data-testid="admin-tab-articles" className={TAB_CLASS}>Articles</TabsTrigger>
            <TabsTrigger value="override-codes" data-testid="admin-tab-override-codes" className={TAB_CLASS}>Override Codes</TabsTrigger>
            <TabsTrigger value="categories" data-testid="admin-tab-categories" className={TAB_CLASS}>Categories</TabsTrigger>
            <TabsTrigger value="catalog" data-testid="admin-tab-catalog" className={TAB_CLASS}>Catalog</TabsTrigger>
            <TabsTrigger value="terms" data-testid="admin-tab-terms" className={TAB_CLASS}>Terms</TabsTrigger>

            {/* Website */}
            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider px-3 pt-4 pb-1">Website</p>
            <TabsTrigger value="website" data-testid="admin-tab-website" className={TAB_CLASS}>Website Content</TabsTrigger>
            <TabsTrigger value="sync" data-testid="admin-tab-sync" className={TAB_CLASS}>Logs</TabsTrigger>
          </TabsList>
        </div>

        {/* Content Area */}
        <div className="flex-1 min-w-0">
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
          <TabsContent value="bank-transactions" className="space-y-4">
            <BankTransactionsTab />
          </TabsContent>
          <TabsContent value="articles" className="space-y-4">
            <ArticlesTab />
          </TabsContent>
          <TabsContent value="categories" className="space-y-4">
            <CategoriesTab />
          </TabsContent>
          <TabsContent value="catalog" className="space-y-4">
            <ProductsTab />
          </TabsContent>
          <TabsContent value="terms" className="space-y-4">
            <TermsTab />
          </TabsContent>
          <TabsContent value="website" className="space-y-4">
            <WebsiteTab />
          </TabsContent>
          <TabsContent value="override-codes" className="space-y-4">
            <OverrideCodesTab />
          </TabsContent>
          <TabsContent value="promo" className="space-y-4">
            <PromoCodesTab />
          </TabsContent>
          <TabsContent value="sync" className="space-y-4">
            <LogsTab />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
