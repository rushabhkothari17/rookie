import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/contexts/AuthContext";
import { CustomersTab } from "./admin/CustomersTab";
import { SubscriptionsTab } from "./admin/SubscriptionsTab";
import { OrdersTab } from "./admin/OrdersTab";
import { PromoCodesTab } from "./admin/PromoCodesTab";
import { TermsTab } from "./admin/TermsTab";
import { UsersTab } from "./admin/UsersTab";
import { ProductsTab } from "./admin/ProductsTab";
import { CategoriesTab } from "./admin/CategoriesTab";
import { SettingsTab } from "./admin/SettingsTab";
import { QuoteRequestsTab } from "./admin/QuoteRequestsTab";
import { BankTransactionsTab } from "./admin/BankTransactionsTab";
import { OverrideCodesTab } from "./admin/OverrideCodesTab";
import { ArticlesTab } from "./admin/ArticlesTab";
import WebsiteTab from "./admin/WebsiteTab";

const TAB_CLASS =
  "w-full justify-start text-left text-sm px-3 py-2 h-auto rounded-none rounded-l-lg " +
  "data-[state=active]:bg-slate-100 data-[state=active]:text-slate-900 data-[state=active]:shadow-none " +
  "data-[state=inactive]:text-slate-500 hover:text-slate-700 hover:bg-slate-50 transition-colors";

export default function Admin() {
  const { user: authUser } = useAuth();
  const isSuperAdmin = authUser?.role === "super_admin";

  return (
    <div className="space-y-6" data-testid="admin-page">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Admin control center</h1>
        <p className="text-sm text-slate-500">Manage customers, orders, promo codes, and catalog content.</p>
      </div>

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
            <TabsTrigger value="quotes" data-testid="admin-tab-quotes" className={TAB_CLASS}>Quote Requests</TabsTrigger>
            <TabsTrigger value="bank-transactions" data-testid="admin-tab-bank-transactions" className={TAB_CLASS}>Bank Transactions</TabsTrigger>

            {/* Content */}
            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider px-3 pt-4 pb-1">Content</p>
            <TabsTrigger value="articles" data-testid="admin-tab-articles" className={TAB_CLASS}>Articles</TabsTrigger>
            <TabsTrigger value="categories" data-testid="admin-tab-categories" className={TAB_CLASS}>Categories</TabsTrigger>
            <TabsTrigger value="catalog" data-testid="admin-tab-catalog" className={TAB_CLASS}>Catalog</TabsTrigger>
            <TabsTrigger value="terms" data-testid="admin-tab-terms" className={TAB_CLASS}>Terms</TabsTrigger>

            {/* Settings */}
            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider px-3 pt-4 pb-1">Settings</p>
            <TabsTrigger value="override-codes" data-testid="admin-tab-override-codes" className={TAB_CLASS}>Override Codes</TabsTrigger>
            <TabsTrigger value="promo" data-testid="admin-tab-promo" className={TAB_CLASS}>Promo Codes</TabsTrigger>
            <TabsTrigger value="settings" data-testid="admin-tab-settings" className={TAB_CLASS}>Settings</TabsTrigger>
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
          <TabsContent value="override-codes" className="space-y-4">
            <OverrideCodesTab />
          </TabsContent>
          <TabsContent value="promo" className="space-y-4">
            <PromoCodesTab />
          </TabsContent>
          <TabsContent value="settings" className="space-y-4">
            <SettingsTab />
          </TabsContent>
          <TabsContent value="sync" className="space-y-4">
            <LogsTab />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
