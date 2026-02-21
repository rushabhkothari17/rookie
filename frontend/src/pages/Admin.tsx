import { useEffect, useState } from "react";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { useAuth } from "@/contexts/AuthContext";

export default function Admin() {
  const { user: authUser } = useAuth();
  const isSuperAdmin = authUser?.role === "super_admin";
  
  const [customers, setCustomers] = useState<any[]>([]);
  const [addresses, setAddresses] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [orders, setOrders] = useState<any[]>([]);
  const [orderItems, setOrderItems] = useState<any[]>([]);
  const [subscriptions, setSubscriptions] = useState<any[]>([]);
  const [products, setProducts] = useState<any[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [promoCodes, setPromoCodes] = useState<any[]>([]);
  const [terms, setTerms] = useState<any[]>([]);
  const [currencyOverride, setCurrencyOverride] = useState({ email: "", currency: "USD" });
  const [selectedProduct, setSelectedProduct] = useState<any>(null);
  const [selectedOrder, setSelectedOrder] = useState<any>(null);
  const [orderFilters, setOrderFilters] = useState({ email: "", product: "", startDate: "", endDate: "" });
  const [catalogFilter, setCatalogFilter] = useState<string>("all");
  const [newPromo, setNewPromo] = useState<{
    code: string;
    discount_type: string;
    discount_value: number;
    applies_to: string;
    applies_to_products: string;
    product_ids: string[];
    expiry_date: string;
    max_uses: string;
    one_time_code: boolean;
    enabled: boolean;
  }>({
    code: "",
    discount_type: "percent",
    discount_value: 10,
    applies_to: "both",
    applies_to_products: "all",
    product_ids: [],
    expiry_date: "",
    max_uses: "",
    one_time_code: false,
    enabled: true,
  });
  const [newTerms, setNewTerms] = useState({
    title: "",
    content: "",
    is_default: false,
    status: "active",
  });
  const [manualOrder, setManualOrder] = useState({
    customer_email: "",
    product_id: "",
    quantity: 1,
    inputs: {},
    subtotal: 0,
    discount: 0,
    fee: 0,
    status: "paid",
    internal_note: "",
  });
  const [manualSubscription, setManualSubscription] = useState({
    customer_email: "",
    product_id: "",
    quantity: 1,
    amount: 0,
    renewal_date: "",
    status: "active",
    internal_note: "",
  });
  const [showPromoDialog, setShowPromoDialog] = useState(false);
  const [showTermsDialog, setShowTermsDialog] = useState(false);
  const [showManualOrderDialog, setShowManualOrderDialog] = useState(false);
  const [showManualSubDialog, setShowManualSubDialog] = useState(false);
  const [selectedOrderLogs, setSelectedOrderLogs] = useState<any[]>([]);
  const [selectedSubLogs, setSelectedSubLogs] = useState<any[]>([]);
  const [showLogsDialog, setShowLogsDialog] = useState(false);
  const [selectedCustomer, setSelectedCustomer] = useState<any>(null);
  const [selectedSubscription, setSelectedSubscription] = useState<any>(null);
  const [showCustomerDialog, setShowCustomerDialog] = useState(false);
  const [showSubEditDialog, setShowSubEditDialog] = useState(false);
  const [showOrderEditDialog, setShowOrderEditDialog] = useState(false);
  const [orderPage, setOrderPage] = useState(1);
  const [orderTotalPages, setOrderTotalPages] = useState(1);
  const [productFilter, setProductFilter] = useState("");
  const [includeDeleted, setIncludeDeleted] = useState(false);
  const [orderSortOrder, setOrderSortOrder] = useState<"desc" | "asc">("desc");
  const [orderNumberFilter, setOrderNumberFilter] = useState("");
  const [orderStatusFilter, setOrderStatusFilter] = useState("");
  const [showNotesDialog, setShowNotesDialog] = useState(false);
  const [selectedOrderNotes, setSelectedOrderNotes] = useState<any[]>([]);
  const [subFilters, setSubFilters] = useState({ customer: "", email: "", plan: "", status: "", payment: "", renewalFrom: "", renewalTo: "" });
  const [subSortField, setSubSortField] = useState<"created_at" | "renewal_date">("created_at");
  const [subSortOrder, setSubSortOrder] = useState<"desc" | "asc">("desc");
  const [subCreatedFrom, setSubCreatedFrom] = useState("");
  const [subCreatedTo, setSubCreatedTo] = useState("");
  const [showSubNotesDialog, setShowSubNotesDialog] = useState(false);
  const [selectedSubNotes, setSelectedSubNotes] = useState<any[]>([]);
  const [adminUsers, setAdminUsers] = useState<any[]>([]);
  const [showCreateAdminDialog, setShowCreateAdminDialog] = useState(false);
  const [newAdminUser, setNewAdminUser] = useState({ email: "", full_name: "", company_name: "", phone: "", password: "", role: "admin" });
  const [showCreateCustomerDialog, setShowCreateCustomerDialog] = useState(false);
  const [newCustomer, setNewCustomer] = useState({ full_name: "", company_name: "", job_title: "", email: "", phone: "", password: "", line1: "", line2: "", city: "", region: "", postal: "", country: "GB", mark_verified: true });

  const loadOrders = async (page = 1) => {
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        per_page: "20",
        sort_by: "created_at",
        sort_order: orderSortOrder,
        include_deleted: includeDeleted.toString(),
      });
      if (productFilter) params.append("product_filter", productFilter);
      if (orderNumberFilter) params.append("order_number_filter", orderNumberFilter);
      if (orderStatusFilter) params.append("status_filter", orderStatusFilter);
      
      const res = await api.get(`/admin/orders?${params.toString()}`);
      setOrders(res.data.orders || []);
      setOrderItems(res.data.items || []);
      setOrderPage(res.data.page || 1);
      setOrderTotalPages(res.data.total_pages || 1);
    } catch (error: any) {
      toast.error("Failed to load orders");
    }
  };

  const loadSubscriptions = async () => {
    try {
      const params = new URLSearchParams({
        sort_by: subSortField,
        sort_order: subSortOrder,
      });
      if (subCreatedFrom) params.append("created_from", subCreatedFrom);
      if (subCreatedTo) params.append("created_to", subCreatedTo);
      const res = await api.get(`/admin/subscriptions?${params.toString()}`);
      setSubscriptions(res.data.subscriptions || []);
    } catch {
      toast.error("Failed to load subscriptions");
    }
  };

  const load = async () => {
    const [custRes, productRes, logRes, promoRes, termsRes] = await Promise.all([
      api.get("/admin/customers"),
      api.get("/products"),
      api.get("/admin/sync-logs"),
      api.get("/admin/promo-codes").catch(() => ({ data: { promo_codes: [] } })),
      api.get("/terms").catch(() => ({ data: { terms: [] } })),
    ]);
    setCustomers(custRes.data.customers || []);
    setAddresses(custRes.data.addresses || []);
    setUsers(custRes.data.users || []);
    setProducts(productRes.data.products || []);
    setLogs(logRes.data.logs || []);
    setPromoCodes(promoRes.data.promo_codes || []);
    setTerms(termsRes.data.terms || []);
    
    await Promise.all([loadOrders(1), loadSubscriptions()]);
  };

  const loadAdminUsers = async () => {
    try {
      const res = await api.get("/admin/users");
      setAdminUsers(res.data.users || []);
    } catch {
      toast.error("Failed to load admin users (super admin required)");
    }
  };

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    loadOrders(1);
    setOrderPage(1);
  }, [productFilter, includeDeleted, orderSortOrder, orderNumberFilter, orderStatusFilter]);

  useEffect(() => {
    loadSubscriptions();
  }, [subSortField, subSortOrder, subCreatedFrom, subCreatedTo]);

  const handleCurrencyOverride = async () => {
    try {
      await api.post("/admin/currency-override", {
        customer_email: currencyOverride.email,
        currency: currencyOverride.currency,
      });
      toast.success("Currency overridden");
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Override failed");
    }
  };

  const handlePaymentMethodToggle = async (customerId: string, field: string, value: boolean) => {
    try {
      const customer = customers.find(c => c.id === customerId);
      await api.put(`/admin/customers/${customerId}/payment-methods`, {
        allow_bank_transfer: field === "allow_bank_transfer" ? value : customer?.allow_bank_transfer ?? true,
        allow_card_payment: field === "allow_card_payment" ? value : customer?.allow_card_payment ?? false,
      });
      toast.success("Payment method updated");
      load();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Update failed");
    }
  };

  const handleProductSave = async () => {
    try {
      await api.put(`/admin/products/${selectedProduct.id}`, {
        name: selectedProduct.name,
        tagline: selectedProduct.tagline,
        description_long: selectedProduct.description_long,
        bullets_included: selectedProduct.bullets_included || [],
        bullets_excluded: selectedProduct.bullets_excluded || [],
        bullets_needed: selectedProduct.bullets_needed || [],
        next_steps: selectedProduct.next_steps || [],
        faqs: selectedProduct.faqs || [],
        pricing_rules: selectedProduct.pricing_rules || {},
        stripe_price_id: selectedProduct.stripe_price_id || null,
        is_active: selectedProduct.is_active ?? true,
      });
      toast.success("Catalog updated");
      load();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Update failed");
    }
  };

  const handleTabChange = () => {
    setSelectedProduct(null);
    setSelectedOrder(null);
  };

  const handleCreatePromo = async () => {
    try {
      await api.post("/admin/promo-codes", {
        code: newPromo.code,
        discount_type: newPromo.discount_type,
        discount_value: newPromo.discount_value,
        applies_to: newPromo.applies_to,
        applies_to_products: newPromo.applies_to_products,
        product_ids: newPromo.product_ids,
        expiry_date: newPromo.expiry_date || null,
        max_uses: newPromo.max_uses ? parseInt(newPromo.max_uses) : null,
        one_time_code: newPromo.one_time_code,
        enabled: newPromo.enabled,
      });
      toast.success("Promo code created");
      setShowPromoDialog(false);
      setNewPromo({
        code: "",
        discount_type: "percent",
        discount_value: 10,
        applies_to: "both",
        applies_to_products: "all",
        product_ids: [],
        expiry_date: "",
        max_uses: "",
        one_time_code: false,
        enabled: true,
      });
      load();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to create promo code");
    }
  };

  const handleTogglePromo = async (promoId: string, enabled: boolean) => {
    try {
      await api.put(`/admin/promo-codes/${promoId}`, { enabled });
      toast.success("Promo code updated");
      load();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Update failed");
    }
  };

  const handleCreateTerms = async () => {
    try {
      await api.post("/admin/terms", newTerms);
      toast.success("Terms created");
      setShowTermsDialog(false);
      setNewTerms({ title: "", content: "", is_default: false, status: "active" });
      load();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to create terms");
    }
  };

  const handleCreateManualOrder = async () => {
    try {
      await api.post("/admin/orders/manual", manualOrder);
      toast.success("Manual order created");
      setShowManualOrderDialog(false);
      setManualOrder({
        customer_email: "",
        product_id: "",
        quantity: 1,
        inputs: {},
        subtotal: 0,
        discount: 0,
        fee: 0,
        status: "paid",
        internal_note: "",
      });
      load();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to create manual order");
    }
  };

  const handleCreateManualSubscription = async () => {
    try {
      await api.post("/admin/subscriptions/manual", manualSubscription);
      toast.success("Manual subscription created");
      setShowManualSubDialog(false);
      setManualSubscription({
        customer_email: "",
        product_id: "",
        quantity: 1,
        amount: 0,
        renewal_date: "",
        status: "active",
        internal_note: "",
      });
      load();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to create manual subscription");
    }
  };

  const handleRenewNow = async (subscriptionId: string) => {
    try {
      await api.post(`/subscriptions/${subscriptionId}/renew-now`);
      toast.success("Renewal order created");
      load();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to renew");
    }
  };

  const handleViewOrderLogs = async (orderId: string) => {
    try {
      const response = await api.get(`/admin/orders/${orderId}/logs`);
      setSelectedOrderLogs(response.data.logs || []);
      setShowLogsDialog(true);
    } catch (error: any) {
      toast.error("Failed to load logs");
    }
  };

  const handleViewSubLogs = async (subId: string) => {
    try {
      const response = await api.get(`/admin/subscriptions/${subId}/logs`);
      setSelectedSubLogs(response.data.logs || []);
      setShowLogsDialog(true);
    } catch (error: any) {
      toast.error("Failed to load logs");
    }
  };

  const handleAssignTermsToProduct = async (productId: string, termsId: string | null) => {
    try {
      await api.put(`/admin/products/${productId}/terms`, null, { params: { terms_id: termsId } });
      toast.success("Terms assignment updated");
      load();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to assign terms");
    }
  };

  const handleCustomerEdit = async () => {
    if (!selectedCustomer) return;
    try {
      await api.put(`/admin/customers/${selectedCustomer.id}`, {
        customer_data: {
          full_name: selectedCustomer.full_name,
          company_name: selectedCustomer.company_name,
          job_title: selectedCustomer.job_title,
          phone: selectedCustomer.phone,
        },
        address_data: {
          line1: selectedCustomer.line1 || "",
          line2: selectedCustomer.line2 || "",
          city: selectedCustomer.city || "",
          region: selectedCustomer.region || "",
          postal: selectedCustomer.postal || "",
        }
      });
      toast.success("Customer updated");
      setShowCustomerDialog(false);
      load();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to update customer");
    }
  };

  const handleOrderEdit = async () => {
    if (!selectedOrder) return;
    try {
      await api.put(`/admin/orders/${selectedOrder.id}`, {
        customer_id: selectedOrder.customer_id,
        status: selectedOrder.status,
        payment_method: selectedOrder.payment_method,
        order_date: selectedOrder.order_date_edit || undefined,
        payment_date: selectedOrder.payment_date || undefined,
        internal_note: selectedOrder.internal_note,
        new_note: selectedOrder.new_note || undefined,
      });
      toast.success("Order updated");
      setShowOrderEditDialog(false);
      setSelectedOrder(null);
      loadOrders(orderPage);
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to update order");
    }
  };

  const handleOrderDelete = async (orderId: string) => {
    if (!confirm("Are you sure you want to delete this order?")) return;
    try {
      await api.delete(`/admin/orders/${orderId}`, { data: { reason: "Deleted by admin" } });
      toast.success("Order deleted");
      loadOrders(orderPage);
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to delete order");
    }
  };

  const handleAutoCharge = async (orderId: string) => {
    try {
      const res = await api.post(`/admin/orders/${orderId}/auto-charge`);
      if (res.data.success) {
        toast.success(res.data.message);
      } else {
        toast.error(res.data.message);
      }
      loadOrders(orderPage);
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Auto-charge failed");
    }
  };

  const handleSubscriptionEdit = async () => {
    if (!selectedSubscription) return;
    try {
      await api.put(`/admin/subscriptions/${selectedSubscription.id}`, {
        renewal_date: selectedSubscription.renewal_date,
        start_date: selectedSubscription.start_date,
        amount: selectedSubscription.amount,
        plan_name: selectedSubscription.plan_name,
        customer_id: selectedSubscription.customer_id,
        status: selectedSubscription.status,
        payment_method: selectedSubscription.payment_method,
        new_note: selectedSubscription.new_note || undefined,
      });
      toast.success("Subscription updated");
      setShowSubEditDialog(false);
      loadSubscriptions();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to update subscription");
    }
  };

  const handleViewSubNotes = (sub: any) => {
    setSelectedSubNotes(sub.notes || []);
    setShowSubNotesDialog(true);
  };

  const handleViewOrderNotes = (order: any) => {
    setSelectedOrderNotes(order.notes || []);
    setShowNotesDialog(true);
  };

  const handleAdminCancelSubscription = async (subId: string) => {
    if (!confirm("Cancel this subscription? Status will be set to 'canceled_pending'.")) return;
    try {
      await api.post(`/admin/subscriptions/${subId}/cancel`);
      toast.success("Subscription cancellation scheduled");
      loadSubscriptions();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Cancellation failed");
    }
  };

  const handleCreateAdminUser = async () => {
    try {
      await api.post("/admin/users", newAdminUser);
      toast.success(`Admin user ${newAdminUser.email} created`);
      setShowCreateAdminDialog(false);
      setNewAdminUser({ email: "", full_name: "", company_name: "", phone: "", password: "", role: "admin" });
      loadAdminUsers();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to create admin user");
    }
  };

  const handleCreateCustomer = async () => {
    try {
      await api.post("/admin/customers/create", newCustomer);
      toast.success(`Customer ${newCustomer.email} created`);
      setShowCreateCustomerDialog(false);
      setNewCustomer({ full_name: "", company_name: "", job_title: "", email: "", phone: "", password: "", line1: "", line2: "", city: "", region: "", postal: "", country: "GB", mark_verified: true });
      load();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to create customer");
    }
  };

  const handleToggleUserActive = async (userId: string, currentActive: boolean) => {
    const newState = !currentActive;
    if (!confirm(`${newState ? "Activate" : "Deactivate"} this user? ${newState ? "" : "They will be unable to login."}`)) return;
    try {
      await api.patch(`/admin/users/${userId}/active?active=${newState}`);
      toast.success(`User ${newState ? "activated" : "deactivated"}`);
      loadAdminUsers();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to update user status");
    }
  };

  const handleToggleCustomerActive = async (customerId: string, currentActive: boolean) => {
    const newState = !currentActive;
    if (!confirm(`${newState ? "Activate" : "Deactivate"} this customer? ${newState ? "" : "Their account will be unable to login."}`)) return;
    try {
      await api.patch(`/admin/customers/${customerId}/active?active=${newState}`);
      toast.success(`Customer ${newState ? "activated" : "deactivated"}`);
      load();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to update customer status");
    }
  };

  const downloadCsv = async (endpoint: string, filename: string) => {
    try {
      const token = localStorage.getItem("aa_token");
      const baseUrl = process.env.REACT_APP_BACKEND_URL || "";
      const resp = await fetch(`${baseUrl}${endpoint}`, { headers: { Authorization: `Bearer ${token}` } });
      if (!resp.ok) throw new Error("Export failed");
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("CSV export failed");
    }
  };

  const getCustomerAddress = (customerId: string) => addresses.find(a => a.customer_id === customerId);
  const getCustomerUser = (customerId: string) => {
    const customer = customers.find(c => c.id === customerId);
    return users.find(u => u.id === customer?.user_id);
  };
  const getProductName = (productId: string) => products.find(p => p.id === productId)?.name || productId;

  // Filter orders (email is client-side; order# / status / product are server-side)
  const filteredOrders = orders.filter(order => {
    const user = getCustomerUser(order.customer_id);
    if (orderFilters.email && !user?.email?.toLowerCase().includes(orderFilters.email.toLowerCase())) return false;
    if (orderFilters.startDate && order.created_at < orderFilters.startDate) return false;
    if (orderFilters.endDate && order.created_at > orderFilters.endDate + "T23:59:59") return false;
    return true;
  });

  // Filter subscriptions (client-side)
  const filteredSubscriptions = subscriptions.filter(sub => {
    const user = getCustomerUser(sub.customer_id);
    if (subFilters.customer && !user?.full_name?.toLowerCase().includes(subFilters.customer.toLowerCase()) && !user?.company_name?.toLowerCase().includes(subFilters.customer.toLowerCase())) return false;
    if (subFilters.email && !user?.email?.toLowerCase().includes(subFilters.email.toLowerCase())) return false;
    if (subFilters.plan && !sub.plan_name?.toLowerCase().includes(subFilters.plan.toLowerCase())) return false;
    if (subFilters.status && sub.status !== subFilters.status) return false;
    if (subFilters.payment && sub.payment_method !== subFilters.payment) return false;
    if (subFilters.renewalFrom && (sub.renewal_date || "") < subFilters.renewalFrom) return false;
    if (subFilters.renewalTo && (sub.renewal_date || "") > subFilters.renewalTo) return false;
    return true;
  });

  // Filter products
  const filteredProducts = products.filter(product => {
    if (catalogFilter === "all") return true;
    if (catalogFilter === "subscription") return product.is_subscription;
    if (catalogFilter === "one-time") return !product.is_subscription;
    return true;
  });

  return (
    <div className="space-y-6" data-testid="admin-page">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Admin control center</h1>
        <p className="text-sm text-slate-500">Manage customers, orders, promo codes, and catalog content.</p>
      </div>

      <Tabs defaultValue="customers" className="space-y-4" data-testid="admin-tabs" onValueChange={handleTabChange}>
        <TabsList>
          <TabsTrigger value="customers" data-testid="admin-tab-customers">Customers</TabsTrigger>
          <TabsTrigger value="orders" data-testid="admin-tab-orders">Orders</TabsTrigger>
          <TabsTrigger value="subscriptions" data-testid="admin-tab-subscriptions">Subscriptions</TabsTrigger>
          <TabsTrigger value="promo" data-testid="admin-tab-promo">Promo Codes</TabsTrigger>
          <TabsTrigger value="terms" data-testid="admin-tab-terms">Terms</TabsTrigger>
          <TabsTrigger value="catalog" data-testid="admin-tab-catalog">Catalog</TabsTrigger>
          <TabsTrigger value="sync" data-testid="admin-tab-sync">Zoho sync logs</TabsTrigger>
          {isSuperAdmin && <TabsTrigger value="users" data-testid="admin-tab-users" onClick={loadAdminUsers}>Users</TabsTrigger>}
        </TabsList>

        <TabsContent value="customers" className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="text-sm font-semibold text-slate-900">Currency override</h3>
            <div className="mt-3 grid gap-3 md:grid-cols-3">
              <Input placeholder="Customer email" value={currencyOverride.email} onChange={(e) => setCurrencyOverride({ ...currencyOverride, email: e.target.value })} data-testid="admin-currency-email" />
              <Input placeholder="Currency (USD/CAD)" value={currencyOverride.currency} onChange={(e) => setCurrencyOverride({ ...currencyOverride, currency: e.target.value })} data-testid="admin-currency-value" />
              <Button onClick={handleCurrencyOverride} data-testid="admin-currency-submit">Override</Button>
            </div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-sm font-semibold text-slate-900">Customers</h3>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => downloadCsv("/api/admin/export/customers", `customers_${new Date().toISOString().slice(0,10)}.csv`)} data-testid="admin-customers-export-csv">Export CSV</Button>
                <Button size="sm" onClick={() => setShowCreateCustomerDialog(true)} data-testid="admin-create-customer-btn">+ Create Customer</Button>
              </div>
            </div>
            <Table data-testid="admin-customer-table">
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>State/Province</TableHead>
                  <TableHead>Country</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Bank Transfer</TableHead>
                  <TableHead>Card Payment</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {customers.map((customer) => {
                  const user = users.find((u) => u.id === customer.user_id);
                  const address = getCustomerAddress(customer.id);
                  const isActive = user?.is_active !== false; // default true
                  return (
                    <TableRow key={customer.id} data-testid={`admin-customer-row-${customer.id}`}>
                      <TableCell data-testid={`admin-customer-name-${customer.id}`}>{user?.full_name || customer.company_name}</TableCell>
                      <TableCell data-testid={`admin-customer-email-${customer.id}`}>{user?.email || "—"}</TableCell>
                      <TableCell data-testid={`admin-customer-region-${customer.id}`}>{address?.region || "—"}</TableCell>
                      <TableCell data-testid={`admin-customer-country-${customer.id}`}>{address?.country || "—"}</TableCell>
                      <TableCell>
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${isActive ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`} data-testid={`admin-customer-status-${customer.id}`}>
                          {isActive ? "Active" : "Inactive"}
                        </span>
                      </TableCell>
                      <TableCell>
                        <button onClick={() => handlePaymentMethodToggle(customer.id, "allow_bank_transfer", !(customer.allow_bank_transfer ?? true))} className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${(customer.allow_bank_transfer ?? true) ? "bg-slate-900" : "bg-slate-200"}`} data-testid={`admin-customer-bank-toggle-${customer.id}`}>
                          <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${(customer.allow_bank_transfer ?? true) ? "translate-x-4" : "translate-x-0.5"}`} />
                        </button>
                      </TableCell>
                      <TableCell>
                        <button onClick={() => handlePaymentMethodToggle(customer.id, "allow_card_payment", !(customer.allow_card_payment ?? false))} className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${(customer.allow_card_payment ?? false) ? "bg-slate-900" : "bg-slate-200"}`} data-testid={`admin-customer-card-toggle-${customer.id}`}>
                          <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${(customer.allow_card_payment ?? false) ? "translate-x-4" : "translate-x-0.5"}`} />
                        </button>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              const u = getCustomerUser(customer.id);
                              const address = getCustomerAddress(customer.id);
                              setSelectedCustomer({ ...customer, ...u, ...address });
                              setShowCustomerDialog(true);
                            }}
                            data-testid={`admin-customer-edit-${customer.id}`}
                          >Edit</Button>
                          <Button
                            variant={isActive ? "destructive" : "outline"}
                            size="sm"
                            onClick={() => handleToggleCustomerActive(customer.id, isActive)}
                            data-testid={`admin-customer-toggle-active-${customer.id}`}
                          >{isActive ? "Deactivate" : "Activate"}</Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
          
          {/* Customer Edit Dialog */}
          <Dialog open={showCustomerDialog} onOpenChange={setShowCustomerDialog}>
            <DialogContent className="max-w-2xl">
              <DialogHeader><DialogTitle>Edit Customer</DialogTitle></DialogHeader>
              {selectedCustomer && (
                <div className="space-y-3 max-h-[60vh] overflow-y-auto">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <label className="text-xs text-slate-500">Full Name</label>
                      <Input value={selectedCustomer.full_name || ""} onChange={(e) => setSelectedCustomer({...selectedCustomer, full_name: e.target.value})} />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs text-slate-500">Company Name</label>
                      <Input value={selectedCustomer.company_name || ""} onChange={(e) => setSelectedCustomer({...selectedCustomer, company_name: e.target.value})} />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <label className="text-xs text-slate-500">Job Title</label>
                      <Input value={selectedCustomer.job_title || ""} onChange={(e) => setSelectedCustomer({...selectedCustomer, job_title: e.target.value})} />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs text-slate-500">Phone</label>
                      <Input value={selectedCustomer.phone || ""} onChange={(e) => setSelectedCustomer({...selectedCustomer, phone: e.target.value})} />
                    </div>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-slate-500">Email (Read-only)</label>
                    <Input value={selectedCustomer.email || ""} disabled className="bg-slate-100" />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-slate-500">Address Line 1</label>
                    <Input value={selectedCustomer.line1 || ""} onChange={(e) => setSelectedCustomer({...selectedCustomer, line1: e.target.value})} />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-slate-500">Address Line 2</label>
                    <Input value={selectedCustomer.line2 || ""} onChange={(e) => setSelectedCustomer({...selectedCustomer, line2: e.target.value})} />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <label className="text-xs text-slate-500">City</label>
                      <Input value={selectedCustomer.city || ""} onChange={(e) => setSelectedCustomer({...selectedCustomer, city: e.target.value})} />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs text-slate-500">State/Province</label>
                      <Input value={selectedCustomer.region || ""} onChange={(e) => setSelectedCustomer({...selectedCustomer, region: e.target.value})} />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <label className="text-xs text-slate-500">Postal Code</label>
                      <Input value={selectedCustomer.postal || ""} onChange={(e) => setSelectedCustomer({...selectedCustomer, postal: e.target.value})} />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs text-slate-500">Country (Locked)</label>
                      <Input value={selectedCustomer.country || ""} disabled className="bg-slate-100" />
                    </div>
                  </div>
                  <Button onClick={handleCustomerEdit} className="w-full">Save Changes</Button>
                </div>
              )}
            </DialogContent>
          </Dialog>
        </TabsContent>

        <TabsContent value="orders" className="space-y-4">
          <div className="flex justify-end mb-3 gap-2">
            <Button variant="outline" size="sm" onClick={() => {
              const params = new URLSearchParams({ sort_order: orderSortOrder, include_deleted: includeDeleted.toString() });
              if (orderNumberFilter) params.append("order_number_filter", orderNumberFilter);
              if (orderStatusFilter) params.append("status_filter", orderStatusFilter);
              if (productFilter) params.append("product_filter", productFilter);
              downloadCsv(`/api/admin/export/orders?${params.toString()}`, `orders_${new Date().toISOString().slice(0,10)}.csv`);
            }} data-testid="admin-orders-export-csv">Export CSV</Button>
            <Dialog open={showManualOrderDialog} onOpenChange={setShowManualOrderDialog}>
              <DialogTrigger asChild>
                <Button>Create Manual Order</Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader><DialogTitle>Create Manual/Offline Order</DialogTitle></DialogHeader>
                <div className="space-y-3">
                  <div className="space-y-1">
                    <label className="text-xs text-slate-500">Customer Email</label>
                    <Input placeholder="customer@example.com" value={manualOrder.customer_email} onChange={(e) => setManualOrder({ ...manualOrder, customer_email: e.target.value })} />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-slate-500">Product</label>
                    <Select value={manualOrder.product_id} onValueChange={(v) => setManualOrder({ ...manualOrder, product_id: v })}>
                      <SelectTrigger><SelectValue placeholder="Select product" /></SelectTrigger>
                      <SelectContent>
                        {products.map((p: any) => (
                          <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <label className="text-xs text-slate-500">Quantity</label>
                      <Input type="number" min="1" value={manualOrder.quantity} onChange={(e) => setManualOrder({ ...manualOrder, quantity: parseInt(e.target.value) || 1 })} />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs text-slate-500">Subtotal</label>
                      <Input type="number" step="0.01" value={manualOrder.subtotal} onChange={(e) => setManualOrder({ ...manualOrder, subtotal: parseFloat(e.target.value) || 0 })} />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <label className="text-xs text-slate-500">Discount</label>
                      <Input type="number" step="0.01" value={manualOrder.discount} onChange={(e) => setManualOrder({ ...manualOrder, discount: parseFloat(e.target.value) || 0 })} />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs text-slate-500">Fee</label>
                      <Input type="number" step="0.01" value={manualOrder.fee} onChange={(e) => setManualOrder({ ...manualOrder, fee: parseFloat(e.target.value) || 0 })} />
                    </div>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-slate-500">Status</label>
                    <Select value={manualOrder.status} onValueChange={(v) => setManualOrder({ ...manualOrder, status: v })}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="paid">Paid (Manual)</SelectItem>
                        <SelectItem value="unpaid">Unpaid (Manual)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-slate-500">Internal Note</label>
                    <Textarea placeholder="Optional internal note" value={manualOrder.internal_note} onChange={(e) => setManualOrder({ ...manualOrder, internal_note: e.target.value })} rows={3} />
                  </div>
                  <Button onClick={handleCreateManualOrder} className="w-full">Create Order</Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="text-sm font-semibold text-slate-900 mb-3">Filters</h3>
            <div className="flex flex-wrap items-end gap-3">
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Start Date</label>
                <Input type="date" value={orderFilters.startDate} onChange={(e) => setOrderFilters({ ...orderFilters, startDate: e.target.value })} data-testid="admin-orders-start-date" className="w-36" />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">End Date</label>
                <Input type="date" value={orderFilters.endDate} onChange={(e) => setOrderFilters({ ...orderFilters, endDate: e.target.value })} data-testid="admin-orders-end-date" className="w-36" />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Customer Email</label>
                <Input placeholder="Filter by email" value={orderFilters.email} onChange={(e) => setOrderFilters({ ...orderFilters, email: e.target.value })} data-testid="admin-orders-email-filter" className="w-44" />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Order #</label>
                <Input placeholder="AA-..." value={orderNumberFilter} onChange={(e) => setOrderNumberFilter(e.target.value)} data-testid="admin-orders-number-filter" className="w-32" />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Status</label>
                <Select value={orderStatusFilter || "all"} onValueChange={(v) => setOrderStatusFilter(v === "all" ? "" : v)}>
                  <SelectTrigger className="w-40" data-testid="admin-orders-status-filter"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Statuses</SelectItem>
                    <SelectItem value="paid">Paid</SelectItem>
                    <SelectItem value="unpaid">Unpaid</SelectItem>
                    <SelectItem value="pending">Pending</SelectItem>
                    <SelectItem value="awaiting_bank_transfer">Awaiting Bank Transfer</SelectItem>
                    <SelectItem value="completed">Completed</SelectItem>
                    <SelectItem value="cancelled">Cancelled</SelectItem>
                    <SelectItem value="refunded">Refunded</SelectItem>
                    <SelectItem value="disputed">Disputed</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Product</label>
                <Input placeholder="Product name" value={productFilter} onChange={(e) => setProductFilter(e.target.value)} data-testid="admin-orders-product-filter" className="w-40" />
              </div>
              <Button variant="outline" onClick={() => {
                setOrderFilters({ email: "", product: "", startDate: "", endDate: "" });
                setOrderNumberFilter("");
                setOrderStatusFilter("");
                setProductFilter("");
              }} data-testid="admin-orders-clear-filters">Clear</Button>
            </div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
            <Table data-testid="admin-orders-table" className="text-xs min-w-[1100px]">
              <TableHeader>
                <TableRow className="bg-slate-50">
                  <TableHead className="w-28 cursor-pointer select-none" onClick={() => setOrderSortOrder(o => o === "desc" ? "asc" : "desc")}>
                    Date {orderSortOrder === "desc" ? "↓" : "↑"}
                  </TableHead>
                  <TableHead className="w-28">Order #</TableHead>
                  <TableHead className="w-36">Customer</TableHead>
                  <TableHead className="w-40">Email</TableHead>
                  <TableHead className="w-40">Product(s)</TableHead>
                  <TableHead className="w-24">Sub #</TableHead>
                  <TableHead className="w-20">Subtotal</TableHead>
                  <TableHead className="w-16">Fee</TableHead>
                  <TableHead className="w-20">Total</TableHead>
                  <TableHead className="w-24">Pay Date</TableHead>
                  <TableHead className="w-20">Method</TableHead>
                  <TableHead className="w-28">Status</TableHead>
                  <TableHead className="w-48">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredOrders.map((order) => {
                  const user = getCustomerUser(order.customer_id);
                  const items = orderItems.filter(i => i.order_id === order.id);
                  const productNames = items.map(i => getProductName(i.product_id)).join(", ") || "—";
                  return (
                    <TableRow key={order.id} data-testid={`admin-order-row-${order.id}`} className="border-b border-slate-100">
                      <TableCell className="whitespace-nowrap">{order.created_at?.slice(0, 10)}</TableCell>
                      <TableCell className="font-mono">{order.order_number}</TableCell>
                      <TableCell className="max-w-[144px] truncate" title={user?.full_name}>{user?.full_name || "—"}</TableCell>
                      <TableCell className="max-w-[160px] truncate" title={user?.email}>{user?.email || "—"}</TableCell>
                      <TableCell className="max-w-[160px] truncate" title={productNames}>{productNames}</TableCell>
                      <TableCell className="font-mono">{order.subscription_number || order.subscription_id?.slice(0, 8) || "—"}</TableCell>
                      <TableCell>${order.subtotal?.toFixed(2)}</TableCell>
                      <TableCell>${order.fee?.toFixed(2)}</TableCell>
                      <TableCell className="font-semibold">${order.total?.toFixed(2)}</TableCell>
                      <TableCell className="whitespace-nowrap">{order.payment_date?.slice(0, 10) || "—"}</TableCell>
                      <TableCell><span className={`px-1.5 py-0.5 rounded text-[10px] ${order.payment_method === "bank_transfer" ? "bg-blue-100 text-blue-700" : order.payment_method === "offline" ? "bg-gray-100 text-gray-700" : "bg-green-100 text-green-700"}`}>{order.payment_method === "bank_transfer" ? "Bank" : order.payment_method === "offline" ? "Manual" : "Card"}</span></TableCell>
                      <TableCell><span className={`px-1.5 py-0.5 rounded text-[10px] ${order.status === "paid" || order.status === "completed" ? "bg-green-100 text-green-700" : order.status === "unpaid" ? "bg-red-100 text-red-700" : order.status === "awaiting_bank_transfer" ? "bg-amber-100 text-amber-700" : order.status === "cancelled" || order.status === "refunded" ? "bg-slate-100 text-slate-500" : "bg-slate-100 text-slate-600"}`}>{order.status}</span></TableCell>
                      <TableCell>
                        <div className="flex gap-1 flex-nowrap items-center">
                          <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px]" onClick={() => handleViewOrderLogs(order.id)} data-testid={`admin-order-logs-${order.id}`}>Logs</Button>
                          <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px]" onClick={() => handleViewOrderNotes(order)} data-testid={`admin-order-notes-${order.id}`}>Notes{order.notes?.length ? ` (${order.notes.length})` : ""}</Button>
                          <Button variant="outline" size="sm" className="h-6 px-2 text-[11px]" onClick={() => { setSelectedOrder({ ...order, order_date_edit: order.created_at?.slice(0, 10) }); setShowOrderEditDialog(true); }} data-testid={`admin-order-edit-${order.id}`}>Edit</Button>
                          {order.status === "unpaid" && (
                            <Button size="sm" variant="secondary" className="h-6 px-2 text-[11px]" onClick={() => handleAutoCharge(order.id)} data-testid={`admin-order-charge-${order.id}`}>Charge</Button>
                          )}
                          <Button size="sm" variant="destructive" className="h-6 px-2 text-[11px]" onClick={() => handleOrderDelete(order.id)} data-testid={`admin-order-delete-${order.id}`}>Del</Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between pt-2">
            <p className="text-xs text-slate-500">Page {orderPage} of {orderTotalPages}</p>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={orderPage <= 1} onClick={() => { setOrderPage(p => p - 1); loadOrders(orderPage - 1); }} data-testid="admin-orders-prev">Previous</Button>
              <Button variant="outline" size="sm" disabled={orderPage >= orderTotalPages} onClick={() => { setOrderPage(p => p + 1); loadOrders(orderPage + 1); }} data-testid="admin-orders-next">Next</Button>
            </div>
          </div>
        </TabsContent>

        {/* Order Edit Dialog (outside table to avoid nesting issues) */}
        <Dialog open={showOrderEditDialog} onOpenChange={(open) => { setShowOrderEditDialog(open); if (!open) setSelectedOrder(null); }}>
          <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="admin-order-edit-dialog">
            <DialogHeader><DialogTitle>Edit Order {selectedOrder?.order_number}</DialogTitle></DialogHeader>
            {selectedOrder && (
              <div className="space-y-3">
                <div className="space-y-1">
                  <label className="text-xs text-slate-500">Customer</label>
                  <Select value={selectedOrder.customer_id || ""} onValueChange={(v) => setSelectedOrder({ ...selectedOrder, customer_id: v })}>
                    <SelectTrigger data-testid="admin-order-customer-select"><SelectValue placeholder="Select customer" /></SelectTrigger>
                    <SelectContent>
                      {customers.map((c: any) => {
                        const u = users.find((u: any) => u.id === c.user_id);
                        return <SelectItem key={c.id} value={c.id}>{u?.full_name || c.id} ({u?.email})</SelectItem>;
                      })}
                    </SelectContent>
                  </Select>
                  {selectedOrder.customer_id && (
                    <p className="text-xs text-slate-400 mt-1">Email: {users.find((u: any) => u.id === customers.find((c: any) => c.id === selectedOrder.customer_id)?.user_id)?.email || "—"}</p>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-xs text-slate-500">Order Date</label>
                    <Input type="date" value={selectedOrder.order_date_edit || ""} onChange={(e) => setSelectedOrder({ ...selectedOrder, order_date_edit: e.target.value })} data-testid="admin-order-date-input" />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-slate-500">Payment Date</label>
                    <Input type="date" value={selectedOrder.payment_date?.slice(0, 10) || ""} onChange={(e) => setSelectedOrder({ ...selectedOrder, payment_date: e.target.value })} data-testid="admin-order-payment-date" />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-xs text-slate-500">Status</label>
                    <Select value={selectedOrder.status || ""} onValueChange={(v) => setSelectedOrder({ ...selectedOrder, status: v })}>
                      <SelectTrigger data-testid="admin-order-status-select"><SelectValue placeholder="Select status" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="paid">Paid</SelectItem>
                        <SelectItem value="unpaid">Unpaid</SelectItem>
                        <SelectItem value="completed">Completed</SelectItem>
                        <SelectItem value="pending">Pending</SelectItem>
                        <SelectItem value="pending_payment">Pending Payment</SelectItem>
                        <SelectItem value="awaiting_bank_transfer">Awaiting Bank Transfer</SelectItem>
                        <SelectItem value="cancelled">Cancelled</SelectItem>
                        <SelectItem value="refunded">Refunded</SelectItem>
                        <SelectItem value="disputed">Disputed</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-slate-500">Payment Method</label>
                    <Select value={selectedOrder.payment_method || ""} onValueChange={(v) => setSelectedOrder({ ...selectedOrder, payment_method: v })}>
                      <SelectTrigger data-testid="admin-order-payment-select"><SelectValue placeholder="Select method" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="card">Card</SelectItem>
                        <SelectItem value="bank_transfer">Bank Transfer</SelectItem>
                        <SelectItem value="offline">Offline / Manual</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-slate-500">Add Note (appended to history)</label>
                  <Textarea placeholder="Add a note..." value={selectedOrder.new_note || ""} onChange={(e) => setSelectedOrder({ ...selectedOrder, new_note: e.target.value })} data-testid="admin-order-note-input" rows={2} />
                </div>
                <Button onClick={handleOrderEdit} className="w-full" data-testid="admin-order-save">Save Changes</Button>
              </div>
            )}
          </DialogContent>
        </Dialog>

        <TabsContent value="subscriptions" className="space-y-4">
          {/* Subscription Filters */}
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="text-sm font-semibold text-slate-900 mb-3">Filters & Sorting</h3>
            <div className="flex flex-wrap items-end gap-3">
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Customer Name</label>
                <Input placeholder="Name / Company" value={subFilters.customer} onChange={(e) => setSubFilters({ ...subFilters, customer: e.target.value })} className="w-36" data-testid="admin-sub-filter-customer" />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Email</label>
                <Input placeholder="Email" value={subFilters.email} onChange={(e) => setSubFilters({ ...subFilters, email: e.target.value })} className="w-44" data-testid="admin-sub-filter-email" />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Plan</label>
                <Input placeholder="Plan name" value={subFilters.plan} onChange={(e) => setSubFilters({ ...subFilters, plan: e.target.value })} className="w-36" data-testid="admin-sub-filter-plan" />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Status</label>
                <Select value={subFilters.status || "all"} onValueChange={(v) => setSubFilters({ ...subFilters, status: v === "all" ? "" : v })}>
                  <SelectTrigger className="w-36" data-testid="admin-sub-filter-status"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All</SelectItem>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="unpaid">Unpaid</SelectItem>
                    <SelectItem value="offline_manual">Offline / Manual</SelectItem>
                    <SelectItem value="canceled_pending">Canceled Pending</SelectItem>
                    <SelectItem value="cancelled">Cancelled</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Payment</label>
                <Select value={subFilters.payment || "all"} onValueChange={(v) => setSubFilters({ ...subFilters, payment: v === "all" ? "" : v })}>
                  <SelectTrigger className="w-32" data-testid="admin-sub-filter-payment"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All</SelectItem>
                    <SelectItem value="card">Card</SelectItem>
                    <SelectItem value="bank_transfer">Bank Transfer</SelectItem>
                    <SelectItem value="offline">Offline</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Renewal From</label>
                <Input type="date" value={subFilters.renewalFrom} onChange={(e) => setSubFilters({ ...subFilters, renewalFrom: e.target.value })} className="w-36" />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Renewal To</label>
                <Input type="date" value={subFilters.renewalTo} onChange={(e) => setSubFilters({ ...subFilters, renewalTo: e.target.value })} className="w-36" />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Created From</label>
                <Input type="date" value={subCreatedFrom} onChange={(e) => setSubCreatedFrom(e.target.value)} className="w-36" data-testid="admin-sub-created-from" />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Created To</label>
                <Input type="date" value={subCreatedTo} onChange={(e) => setSubCreatedTo(e.target.value)} className="w-36" data-testid="admin-sub-created-to" />
              </div>
            </div>
            <div className="flex flex-wrap items-end gap-3 mt-3">
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Sort By</label>
                <Select value={subSortField} onValueChange={(v: any) => setSubSortField(v)}>
                  <SelectTrigger className="w-36" data-testid="admin-sub-sort-field"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="created_at">Created Date</SelectItem>
                    <SelectItem value="renewal_date">Renewal Date</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Direction</label>
                <Select value={subSortOrder} onValueChange={(v: any) => setSubSortOrder(v)}>
                  <SelectTrigger className="w-28" data-testid="admin-sub-sort-order"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="desc">Newest First</SelectItem>
                    <SelectItem value="asc">Oldest First</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button variant="outline" onClick={() => { setSubFilters({ customer: "", email: "", plan: "", status: "", payment: "", renewalFrom: "", renewalTo: "" }); setSubCreatedFrom(""); setSubCreatedTo(""); }} data-testid="admin-sub-clear-filters">Clear All</Button>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => {
              const params = new URLSearchParams({ sort_by: subSortField, sort_order: subSortOrder });
              if (subCreatedFrom) params.append("created_from", subCreatedFrom);
              if (subCreatedTo) params.append("created_to", subCreatedTo);
              downloadCsv(`/api/admin/export/subscriptions?${params.toString()}`, `subscriptions_${new Date().toISOString().slice(0,10)}.csv`);
            }} data-testid="admin-subscriptions-export-csv">Export CSV</Button>
            <Dialog open={showManualSubDialog} onOpenChange={setShowManualSubDialog}>
              <DialogTrigger asChild>
                <Button>Create Manual Subscription</Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader><DialogTitle>Create Manual Subscription</DialogTitle></DialogHeader>
                <div className="space-y-3">
                  <div className="space-y-1">
                    <label className="text-xs text-slate-500">Customer Email</label>
                    <Input placeholder="customer@example.com" value={manualSubscription.customer_email} onChange={(e) => setManualSubscription({ ...manualSubscription, customer_email: e.target.value })} />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-slate-500">Product</label>
                    <Select value={manualSubscription.product_id} onValueChange={(v) => setManualSubscription({ ...manualSubscription, product_id: v })}>
                      <SelectTrigger><SelectValue placeholder="Select product" /></SelectTrigger>
                      <SelectContent>
                        {products.filter((p: any) => p.billing_type === "subscription").map((p: any) => (
                          <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <label className="text-xs text-slate-500">Amount</label>
                      <Input type="number" step="0.01" value={manualSubscription.amount} onChange={(e) => setManualSubscription({ ...manualSubscription, amount: parseFloat(e.target.value) || 0 })} />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs text-slate-500">Renewal Date</label>
                      <Input type="date" value={manualSubscription.renewal_date} onChange={(e) => setManualSubscription({ ...manualSubscription, renewal_date: e.target.value })} />
                    </div>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-slate-500">Status</label>
                    <Select value={manualSubscription.status} onValueChange={(v) => setManualSubscription({ ...manualSubscription, status: v })}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="active">Active</SelectItem>
                        <SelectItem value="unpaid">Unpaid</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-slate-500">Internal Note</label>
                    <Textarea placeholder="Optional internal note" value={manualSubscription.internal_note} onChange={(e) => setManualSubscription({ ...manualSubscription, internal_note: e.target.value })} rows={3} />
                  </div>
                  <Button onClick={handleCreateManualSubscription} className="w-full">Create Subscription</Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
            <Table data-testid="admin-subscriptions-table" className="text-xs min-w-[1400px]">
              <TableHeader>
                <TableRow className="bg-slate-50">
                  <TableHead className="w-28">Sub ID</TableHead>
                  <TableHead className="w-32">Customer</TableHead>
                  <TableHead className="w-36">Email</TableHead>
                  <TableHead className="w-36">Plan</TableHead>
                  <TableHead className="w-28">Status</TableHead>
                  <TableHead className="w-24">Start Date</TableHead>
                  <TableHead className="w-24">Created</TableHead>
                  <TableHead className="w-24">Renewal</TableHead>
                  <TableHead className="w-24">Cancel Date</TableHead>
                  <TableHead className="w-20">Amount</TableHead>
                  <TableHead className="w-20">Payment</TableHead>
                  <TableHead className="w-56">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredSubscriptions.map((sub) => {
                  const user = getCustomerUser(sub.customer_id);
                  const cancelDate = sub.cancel_at_period_end
                    ? (sub.current_period_end?.slice(0, 10) || sub.canceled_at?.slice(0, 10) || "—")
                    : (sub.canceled_at?.slice(0, 10) || "—");
                  const startDate = sub.start_date?.slice(0, 10) || sub.current_period_start?.slice(0, 10) || sub.created_at?.slice(0, 10) || "—";
                  return (
                    <TableRow key={sub.id} data-testid={`admin-subscription-${sub.id}`} className="border-b border-slate-100">
                      <TableCell className="font-mono text-[10px]">{sub.subscription_number || sub.id?.slice(0, 8)}</TableCell>
                      <TableCell className="max-w-[128px] truncate" title={user?.full_name}>{user?.full_name || "—"}</TableCell>
                      <TableCell className="max-w-[144px] truncate" title={user?.email}>{user?.email || "—"}</TableCell>
                      <TableCell className="max-w-[144px] truncate" title={sub.plan_name}>{sub.plan_name}</TableCell>
                      <TableCell>
                        <span className={`px-1.5 py-0.5 rounded text-[10px] ${sub.status === "active" ? "bg-green-100 text-green-700" : sub.status === "canceled_pending" ? "bg-amber-100 text-amber-700" : sub.status === "offline_manual" ? "bg-blue-100 text-blue-700" : "bg-slate-100 text-slate-600"}`}>
                          {sub.status === "offline_manual" ? "Offline/Manual" : sub.status}
                        </span>
                      </TableCell>
                      <TableCell className="whitespace-nowrap">{startDate}</TableCell>
                      <TableCell className="whitespace-nowrap">{sub.created_at?.slice(0, 10) || "—"}</TableCell>
                      <TableCell className="whitespace-nowrap">{sub.renewal_date?.slice(0, 10) || sub.current_period_end?.slice(0, 10) || "—"}</TableCell>
                      <TableCell className="whitespace-nowrap text-amber-600">{cancelDate}</TableCell>
                      <TableCell>${sub.amount?.toFixed(2) || "—"}</TableCell>
                      <TableCell>{sub.payment_method || "card"}</TableCell>
                      <TableCell>
                        <div className="flex gap-1 flex-nowrap">
                          {sub.is_manual && (
                            <Button
                              size="sm" variant="outline" className="h-6 px-2 text-[11px]"
                              disabled={sub.status === "canceled_pending"}
                              title={sub.status === "canceled_pending" ? "Renew disabled while cancellation is pending" : undefined}
                              onClick={() => handleRenewNow(sub.id)}
                              data-testid={`admin-sub-renew-${sub.id}`}
                            >Renew</Button>
                          )}
                          <Button size="sm" variant="outline" className="h-6 px-2 text-[11px]" onClick={() => { setSelectedSubscription({ ...sub, new_note: "" }); setShowSubEditDialog(true); }} data-testid={`admin-sub-edit-${sub.id}`}>Edit</Button>
                          <Button size="sm" variant="ghost" className="h-6 px-2 text-[11px]" onClick={() => handleViewSubNotes(sub)} data-testid={`admin-sub-notes-${sub.id}`}>Notes{sub.notes?.length ? ` (${sub.notes.length})` : ""}</Button>
                          {sub.status !== "canceled_pending" && sub.status !== "cancelled" && (
                            <Button size="sm" variant="destructive" className="h-6 px-2 text-[11px]" onClick={() => handleAdminCancelSubscription(sub.id)} data-testid={`admin-sub-cancel-${sub.id}`}>Cancel</Button>
                          )}
                          <Button size="sm" variant="ghost" className="h-6 px-2 text-[11px]" onClick={() => handleViewSubLogs(sub.id)} data-testid={`admin-sub-logs-${sub.id}`}>Logs</Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

        {/* Subscription Edit Dialog */}
        <Dialog open={showSubEditDialog} onOpenChange={(open) => { setShowSubEditDialog(open); if (!open) setSelectedSubscription(null); }}>
          <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="admin-sub-edit-dialog">
            <DialogHeader><DialogTitle>Edit Subscription</DialogTitle></DialogHeader>
            {selectedSubscription && (
              <div className="space-y-3">
                <div className="space-y-1">
                  <label className="text-xs text-slate-500">Customer</label>
                  <Select value={selectedSubscription.customer_id || ""} onValueChange={(v) => setSelectedSubscription({ ...selectedSubscription, customer_id: v })}>
                    <SelectTrigger data-testid="admin-sub-customer-select"><SelectValue placeholder="Select customer" /></SelectTrigger>
                    <SelectContent>
                      {customers.map((c: any) => {
                        const u = users.find((u: any) => u.id === c.user_id);
                        return <SelectItem key={c.id} value={c.id}>{u?.full_name || c.id} ({u?.email})</SelectItem>;
                      })}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-slate-500">Plan Name</label>
                  <Input value={selectedSubscription.plan_name || ""} onChange={(e) => setSelectedSubscription({ ...selectedSubscription, plan_name: e.target.value })} data-testid="admin-sub-plan-input" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-xs text-slate-500">Amount</label>
                    <Input type="number" step="0.01" value={selectedSubscription.amount || ""} onChange={(e) => setSelectedSubscription({ ...selectedSubscription, amount: parseFloat(e.target.value) || 0 })} data-testid="admin-sub-amount-input" />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-slate-500">Renewal Date</label>
                    <Input type="date" value={selectedSubscription.renewal_date?.slice(0, 10) || ""} onChange={(e) => setSelectedSubscription({ ...selectedSubscription, renewal_date: e.target.value })} data-testid="admin-sub-renewal-input" />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-xs text-slate-500">Start Date (editable)</label>
                    <Input type="date" value={selectedSubscription.start_date?.slice(0, 10) || ""} onChange={(e) => setSelectedSubscription({ ...selectedSubscription, start_date: e.target.value })} data-testid="admin-sub-start-input" />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-slate-500">Created Date (read-only)</label>
                    <Input type="date" value={selectedSubscription.created_at?.slice(0, 10) || ""} readOnly disabled className="bg-slate-50 cursor-not-allowed" data-testid="admin-sub-created-display" />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-xs text-slate-500">Status</label>
                    <Select value={selectedSubscription.status || ""} onValueChange={(v) => setSelectedSubscription({ ...selectedSubscription, status: v })}>
                      <SelectTrigger data-testid="admin-sub-status-select"><SelectValue placeholder="Status" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="active">Active</SelectItem>
                        <SelectItem value="unpaid">Unpaid</SelectItem>
                        <SelectItem value="offline_manual">Offline / Manual</SelectItem>
                        <SelectItem value="canceled_pending">Canceled Pending</SelectItem>
                        <SelectItem value="cancelled">Cancelled</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-slate-500">Payment Method</label>
                    <Select value={selectedSubscription.payment_method || "card"} onValueChange={(v) => setSelectedSubscription({ ...selectedSubscription, payment_method: v })}>
                      <SelectTrigger data-testid="admin-sub-payment-select"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="card">Card</SelectItem>
                        <SelectItem value="bank_transfer">Bank Transfer</SelectItem>
                        <SelectItem value="offline">Offline / Manual</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-slate-500">Add Note (logged with timestamp)</label>
                  <Textarea placeholder="Add a note..." value={selectedSubscription.new_note || ""} onChange={(e) => setSelectedSubscription({ ...selectedSubscription, new_note: e.target.value })} rows={2} data-testid="admin-sub-note-input" />
                </div>
                <Button onClick={handleSubscriptionEdit} className="w-full" data-testid="admin-sub-save">Save Changes</Button>
              </div>
            )}
          </DialogContent>
        </Dialog>

        <TabsContent value="promo" className="space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-sm font-semibold text-slate-900">Promo Codes</h3>
            <Dialog open={showPromoDialog} onOpenChange={setShowPromoDialog}>
              <DialogTrigger asChild>
                <Button data-testid="admin-promo-create">Create Promo Code</Button>
              </DialogTrigger>
              <DialogContent data-testid="admin-promo-dialog">
                <DialogHeader><DialogTitle>Create Promo Code</DialogTitle></DialogHeader>
                <div className="space-y-3">
                  <div className="space-y-1">
                    <label className="text-xs text-slate-500">Code</label>
                    <Input placeholder="SUMMER20" value={newPromo.code} onChange={(e) => setNewPromo({ ...newPromo, code: e.target.value.toUpperCase() })} data-testid="admin-promo-code-input" />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <label className="text-xs text-slate-500">Discount Type</label>
                      <Select value={newPromo.discount_type} onValueChange={(v) => setNewPromo({ ...newPromo, discount_type: v })}>
                        <SelectTrigger data-testid="admin-promo-type-select"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="percent">Percent (%)</SelectItem>
                          <SelectItem value="fixed">Fixed ($)</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs text-slate-500">Value</label>
                      <Input type="number" value={newPromo.discount_value} onChange={(e) => setNewPromo({ ...newPromo, discount_value: parseFloat(e.target.value) })} data-testid="admin-promo-value-input" />
                    </div>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-slate-500">Applies To</label>
                    <Select value={newPromo.applies_to} onValueChange={(v) => setNewPromo({ ...newPromo, applies_to: v })}>
                      <SelectTrigger data-testid="admin-promo-applies-select"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="both">Both</SelectItem>
                        <SelectItem value="one-time">One-time only</SelectItem>
                        <SelectItem value="subscription">Subscription only</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-slate-500">Product Eligibility</label>
                    <Select value={newPromo.applies_to_products} onValueChange={(v) => setNewPromo({ ...newPromo, applies_to_products: v, product_ids: v === "all" ? [] : newPromo.product_ids })}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Products (default)</SelectItem>
                        <SelectItem value="selected">Selected Products Only</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  {newPromo.applies_to_products === "selected" && (
                    <div className="space-y-1">
                      <label className="text-xs text-slate-500">Select Products</label>
                      <div className="max-h-40 overflow-y-auto border border-slate-200 rounded p-2 space-y-1">
                        {products.map((p: any) => (
                          <div key={p.id} className="flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={newPromo.product_ids.includes(p.id)}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setNewPromo({ ...newPromo, product_ids: [...newPromo.product_ids, p.id] });
                                } else {
                                  setNewPromo({ ...newPromo, product_ids: newPromo.product_ids.filter((id: string) => id !== p.id) });
                                }
                              }}
                            />
                            <label className="text-xs">{p.name}</label>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <label className="text-xs text-slate-500">Expiry Date (optional)</label>
                      <Input type="date" value={newPromo.expiry_date} onChange={(e) => setNewPromo({ ...newPromo, expiry_date: e.target.value })} data-testid="admin-promo-expiry-input" />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs text-slate-500">Max Uses (optional)</label>
                      <Input type="number" value={newPromo.max_uses} onChange={(e) => setNewPromo({ ...newPromo, max_uses: e.target.value })} data-testid="admin-promo-maxuses-input" />
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <input type="checkbox" checked={newPromo.one_time_code} onChange={(e) => setNewPromo({ ...newPromo, one_time_code: e.target.checked })} data-testid="admin-promo-onetime-check" />
                    <label className="text-sm">One-time per customer</label>
                  </div>
                  <Button onClick={handleCreatePromo} className="w-full" data-testid="admin-promo-submit">Create</Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
            <Table data-testid="admin-promo-table">
              <TableHeader>
                <TableRow className="bg-slate-50">
                  <TableHead>Code</TableHead>
                  <TableHead>Discount</TableHead>
                  <TableHead>Applies To</TableHead>
                  <TableHead>Expiry</TableHead>
                  <TableHead>Usage</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Enabled</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {promoCodes.map((promo) => (
                  <TableRow key={promo.id} data-testid={`admin-promo-row-${promo.id}`} className="border-b border-slate-100">
                    <TableCell className="font-mono font-semibold">{promo.code}</TableCell>
                    <TableCell>{promo.discount_type === "percent" ? `${promo.discount_value}%` : `$${promo.discount_value}`}</TableCell>
                    <TableCell className="capitalize">{promo.applies_to}</TableCell>
                    <TableCell className="text-xs">{promo.expiry_date?.slice(0, 10) || "—"}</TableCell>
                    <TableCell>{promo.usage_count}{promo.max_uses ? ` / ${promo.max_uses}` : ""}</TableCell>
                    <TableCell><span className={`text-xs px-2 py-1 rounded ${promo.status === "Active" ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-600"}`}>{promo.status}</span></TableCell>
                    <TableCell>
                      <button onClick={() => handleTogglePromo(promo.id, !promo.enabled)} className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${promo.enabled ? "bg-slate-900" : "bg-slate-200"}`} data-testid={`admin-promo-toggle-${promo.id}`}>
                        <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${promo.enabled ? "translate-x-4" : "translate-x-0.5"}`} />
                      </button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

        <TabsContent value="terms" className="space-y-4">
          <div className="flex justify-end">
            <Dialog open={showTermsDialog} onOpenChange={setShowTermsDialog}>
              <DialogTrigger asChild>
                <Button>Create Terms & Conditions</Button>
              </DialogTrigger>
              <DialogContent className="max-w-2xl">
                <DialogHeader><DialogTitle>Create Terms & Conditions</DialogTitle></DialogHeader>
                <div className="space-y-3">
                  <div className="space-y-1">
                    <label className="text-xs text-slate-500">Title</label>
                    <Input placeholder="Default Terms & Conditions" value={newTerms.title} onChange={(e) => setNewTerms({ ...newTerms, title: e.target.value })} />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-slate-500">Content (supports dynamic tags)</label>
                    <Textarea placeholder="{company_name} {product_name} - TEST" value={newTerms.content} onChange={(e) => setNewTerms({ ...newTerms, content: e.target.value })} rows={8} />
                    <p className="text-xs text-slate-400">Available tags: {'{product_name}'}, {'{user_name}'}, {'{company_name}'}, {'{user_job_title}'}, {'{user_email}'}, {'{user_phone}'}, {'{user_address_line1}'}, {'{user_city}'}, {'{user_state}'}, {'{user_postal}'}, {'{user_country}'}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <input type="checkbox" checked={newTerms.is_default} onChange={(e) => setNewTerms({ ...newTerms, is_default: e.target.checked })} />
                    <label className="text-sm">Set as default T&C</label>
                  </div>
                  <Button onClick={handleCreateTerms} className="w-full">Create</Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="bg-slate-50">
                  <TableHead>Title</TableHead>
                  <TableHead>Preview</TableHead>
                  <TableHead>Default</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {terms.map((t: any) => (
                  <TableRow key={t.id} className="border-b border-slate-100">
                    <TableCell className="font-semibold">{t.title}</TableCell>
                    <TableCell className="text-xs text-slate-500 max-w-xs truncate">{t.content}</TableCell>
                    <TableCell>{t.is_default ? <span className="text-xs px-2 py-1 rounded bg-blue-100 text-blue-700">Default</span> : "—"}</TableCell>
                    <TableCell><span className={`text-xs px-2 py-1 rounded ${t.status === "active" ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-600"}`}>{t.status}</span></TableCell>
                    <TableCell className="text-xs">{new Date(t.created_at).toLocaleDateString()}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

        <TabsContent value="catalog" className="space-y-4">
          <div className="flex items-center gap-3">
            <label className="text-sm text-slate-500">Filter:</label>
            <Select value={catalogFilter} onValueChange={setCatalogFilter}>
              <SelectTrigger className="w-40" data-testid="admin-catalog-filter"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Products</SelectItem>
                <SelectItem value="subscription">Subscriptions</SelectItem>
                <SelectItem value="one-time">One-time</SelectItem>
              </SelectContent>
            </Select>
            <div className="ml-auto">
              <Button variant="outline" size="sm" onClick={() => downloadCsv("/api/admin/export/catalog", `catalog_${new Date().toISOString().slice(0,10)}.csv`)} data-testid="admin-catalog-export-csv">Export CSV</Button>
            </div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
            <Table data-testid="admin-catalog-table">
              <TableHeader>
                <TableRow className="bg-slate-50">
                  <TableHead>Name</TableHead>
                  <TableHead>SKU</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Billing Type</TableHead>
                  <TableHead>Terms Assigned</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredProducts.map((product) => {
                  const assignedTerms = terms.find((t: any) => t.id === product.terms_id);
                  return (
                    <TableRow key={product.id} className="border-b border-slate-100">
                      <TableCell className="font-semibold">{product.name}</TableCell>
                      <TableCell className="font-mono text-xs">{product.sku}</TableCell>
                      <TableCell className="text-xs">{product.category}</TableCell>
                      <TableCell>
                        <span className={`text-xs px-2 py-1 rounded ${product.is_subscription ? "bg-purple-100 text-purple-700" : "bg-blue-100 text-blue-700"}`}>
                          {product.is_subscription ? "Subscription" : "One-time"}
                        </span>
                      </TableCell>
                      <TableCell>
                        <Select 
                          value={product.terms_id || "default"} 
                          onValueChange={(v) => handleAssignTermsToProduct(product.id, v === "default" ? null : v)}
                        >
                          <SelectTrigger className="w-48">
                            <SelectValue placeholder="Default T&C" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="default">Default T&C</SelectItem>
                            {terms.filter((t: any) => t.status === "active").map((t: any) => (
                              <SelectItem key={t.id} value={t.id}>{t.title}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </TableCell>
                      <TableCell>
                        <Dialog open={selectedProduct?.id === product.id} onOpenChange={(open) => { if (!open) setSelectedProduct(null); }}>
                          <DialogTrigger asChild>
                            <Button variant="outline" size="sm" onClick={() => setSelectedProduct(product)} data-testid={`admin-edit-${product.id}`}>Edit</Button>
                          </DialogTrigger>
                          {selectedProduct && selectedProduct.id === product.id && (
                            <DialogContent className="max-h-[80vh] overflow-y-auto" data-testid="admin-product-dialog">
                              <DialogHeader><DialogTitle>Edit {product.name}</DialogTitle></DialogHeader>
                              <div className="space-y-3">
                                <Input placeholder="Name" value={selectedProduct.name || ""} onChange={(e) => setSelectedProduct({ ...selectedProduct, name: e.target.value })} data-testid="admin-product-name" />
                                <Input placeholder="Tagline" value={selectedProduct.tagline || ""} onChange={(e) => setSelectedProduct({ ...selectedProduct, tagline: e.target.value })} data-testid="admin-product-tagline" />
                                <Textarea placeholder="Description" value={selectedProduct.description_long || ""} onChange={(e) => setSelectedProduct({ ...selectedProduct, description_long: e.target.value })} data-testid="admin-product-description" />
                                <Input placeholder="Stripe Price ID" value={selectedProduct.stripe_price_id || ""} onChange={(e) => setSelectedProduct({ ...selectedProduct, stripe_price_id: e.target.value })} data-testid="admin-product-stripe" />
                                <Button onClick={handleProductSave} data-testid="admin-product-save">Save changes</Button>
                              </div>
                            </DialogContent>
                          )}
                        </Dialog>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

        <TabsContent value="sync" className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600" data-testid="admin-sync-list">
            {logs.length === 0 && <p>No sync logs yet.</p>}
            {logs.map((log) => (
              <div key={log.id} className="flex justify-between border-b border-slate-100 py-2" data-testid={`admin-log-${log.id}`}>
                <div>
                  <span className="font-mono text-xs">{log.entity_type}</span>
                  <span className="ml-2 text-xs text-slate-400">{log.created_at?.slice(0, 10)}</span>
                </div>
                <span className={`text-xs px-2 py-1 rounded ${log.status === "Sent" ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"}`}>{log.status}</span>
              </div>
            ))}
          </div>
        </TabsContent>

        {/* Users Tab (super_admin only) */}
        {isSuperAdmin && (
          <TabsContent value="users" className="space-y-4">
            <div className="flex justify-between items-center">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">Admin Users</h3>
                <p className="text-xs text-slate-500 mt-1">Only super admins can create admin users.</p>
              </div>
              <Button size="sm" onClick={() => setShowCreateAdminDialog(true)} data-testid="admin-create-user-btn">+ Create Admin User</Button>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white">
              <Table data-testid="admin-users-table" className="text-sm">
                <TableHeader>
                  <TableRow className="bg-slate-50">
                    <TableHead>Name</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead>Must Change PW</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {adminUsers.map((u: any) => {
                    const isActive = u.is_active !== false;
                    return (
                      <TableRow key={u.id} data-testid={`admin-user-row-${u.id}`}>
                        <TableCell>{u.full_name}</TableCell>
                        <TableCell>{u.email}</TableCell>
                        <TableCell>
                          <span className={`px-2 py-0.5 rounded text-xs ${u.role === "super_admin" ? "bg-purple-100 text-purple-700" : "bg-blue-100 text-blue-700"}`}>{u.role}</span>
                        </TableCell>
                        <TableCell>
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${isActive ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`} data-testid={`admin-user-status-${u.id}`}>
                            {isActive ? "Active" : "Inactive"}
                          </span>
                        </TableCell>
                        <TableCell>{u.created_at?.slice(0, 10) || "—"}</TableCell>
                        <TableCell>{u.must_change_password ? "Yes" : "No"}</TableCell>
                        <TableCell>
                          {u.id !== authUser?.id && (
                            <Button
                              variant={isActive ? "destructive" : "outline"}
                              size="sm"
                              className="h-6 px-2 text-[11px]"
                              onClick={() => handleToggleUserActive(u.id, isActive)}
                              data-testid={`admin-user-toggle-active-${u.id}`}
                            >{isActive ? "Deactivate" : "Activate"}</Button>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                  {adminUsers.length === 0 && (
                    <TableRow><TableCell colSpan={7} className="text-center text-slate-400 py-4">No admin users loaded. Click the Users tab again to load.</TableCell></TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          </TabsContent>
        )}
      </Tabs>

      {/* Sub Notes Dialog */}
      <Dialog open={showSubNotesDialog} onOpenChange={setShowSubNotesDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle>Subscription Notes</DialogTitle></DialogHeader>
          <div className="max-h-[50vh] overflow-y-auto space-y-2">
            {selectedSubNotes.length === 0 ? (
              <p className="text-sm text-slate-500 text-center py-4">No notes yet. Add one via Edit Subscription.</p>
            ) : (
              selectedSubNotes.map((note: any, i: number) => (
                <div key={i} className="border border-slate-200 rounded p-3">
                  <div className="flex justify-between items-start mb-1">
                    <span className="text-xs text-slate-500 font-medium">{note.actor}</span>
                    <span className="text-xs text-slate-400">{new Date(note.timestamp).toLocaleString()}</span>
                  </div>
                  <p className="text-sm text-slate-800">{note.text}</p>
                </div>
              ))
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Notes Dialog */}
      <Dialog open={showNotesDialog} onOpenChange={setShowNotesDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle>Order Notes</DialogTitle></DialogHeader>
          <div className="max-h-[50vh] overflow-y-auto space-y-2">
            {selectedOrderNotes.length === 0 ? (
              <p className="text-sm text-slate-500 text-center py-4">No notes yet. Add one via Edit Order.</p>
            ) : (
              selectedOrderNotes.map((note: any, i: number) => (
                <div key={i} className="border border-slate-200 rounded p-3">
                  <div className="flex justify-between items-start mb-1">
                    <span className="text-xs text-slate-500 font-medium">{note.actor}</span>
                    <span className="text-xs text-slate-400">{new Date(note.timestamp).toLocaleString()}</span>
                  </div>
                  <p className="text-sm text-slate-800">{note.text}</p>
                </div>
              ))
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Logs Dialog */}
      <Dialog open={showLogsDialog} onOpenChange={(open) => { setShowLogsDialog(open); if (!open) { setSelectedOrderLogs([]); setSelectedSubLogs([]); } }}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>Audit Logs</DialogTitle></DialogHeader>
          <div className="max-h-[60vh] overflow-y-auto space-y-2">
            {(selectedOrderLogs.length > 0 ? selectedOrderLogs : selectedSubLogs).map((log: any) => (
              <div key={log.id} className="border border-slate-200 rounded p-3">
                <div className="flex justify-between items-start mb-2">
                  <span className="text-sm font-semibold text-slate-900">{log.action}</span>
                  <span className="text-xs text-slate-500">{new Date(log.created_at).toLocaleString()}</span>
                </div>
                <div className="text-xs text-slate-600">Actor: {log.actor}</div>
                {log.details && Object.keys(log.details).length > 0 && (
                  <pre className="text-xs text-slate-500 mt-2 bg-slate-50 p-2 rounded overflow-x-auto">
                    {JSON.stringify(log.details, null, 2)}
                  </pre>
                )}
              </div>
            ))}
            {(selectedOrderLogs.length === 0 && selectedSubLogs.length === 0) && (
              <p className="text-sm text-slate-500 text-center py-4">No logs found</p>
            )}
          </div>
        </DialogContent>
      </Dialog>
      {/* Create Admin User Dialog (super_admin only) */}
      <Dialog open={showCreateAdminDialog} onOpenChange={setShowCreateAdminDialog}>
        <DialogContent className="max-w-lg" data-testid="admin-create-user-dialog">
          <DialogHeader><DialogTitle>Create Admin User</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Full Name *</label>
                <Input value={newAdminUser.full_name} onChange={(e) => setNewAdminUser({ ...newAdminUser, full_name: e.target.value })} data-testid="admin-new-user-name" />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Email *</label>
                <Input type="email" value={newAdminUser.email} onChange={(e) => setNewAdminUser({ ...newAdminUser, email: e.target.value })} data-testid="admin-new-user-email" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Password *</label>
                <Input type="password" value={newAdminUser.password} onChange={(e) => setNewAdminUser({ ...newAdminUser, password: e.target.value })} data-testid="admin-new-user-password" />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Role</label>
                <Select value={newAdminUser.role} onValueChange={(v) => setNewAdminUser({ ...newAdminUser, role: v })}>
                  <SelectTrigger data-testid="admin-new-user-role"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="admin">Admin</SelectItem>
                    <SelectItem value="super_admin">Super Admin</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <p className="text-xs text-amber-600">User will be required to change password on first login.</p>
            <Button onClick={handleCreateAdminUser} className="w-full" data-testid="admin-new-user-submit">Create Admin User</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Create Customer Dialog */}
      <Dialog open={showCreateCustomerDialog} onOpenChange={setShowCreateCustomerDialog}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="admin-create-customer-dialog">
          <DialogHeader><DialogTitle>Create Customer</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Full Name *</label>
                <Input value={newCustomer.full_name} onChange={(e) => setNewCustomer({ ...newCustomer, full_name: e.target.value })} data-testid="admin-new-customer-name" />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Company Name</label>
                <Input value={newCustomer.company_name} onChange={(e) => setNewCustomer({ ...newCustomer, company_name: e.target.value })} data-testid="admin-new-customer-company" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Email *</label>
                <Input type="email" value={newCustomer.email} onChange={(e) => setNewCustomer({ ...newCustomer, email: e.target.value })} data-testid="admin-new-customer-email" />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Job Title</label>
                <Input value={newCustomer.job_title} onChange={(e) => setNewCustomer({ ...newCustomer, job_title: e.target.value })} data-testid="admin-new-customer-job" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Phone</label>
                <Input value={newCustomer.phone} onChange={(e) => setNewCustomer({ ...newCustomer, phone: e.target.value })} data-testid="admin-new-customer-phone" />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Password * (user must change on login)</label>
                <Input type="password" value={newCustomer.password} onChange={(e) => setNewCustomer({ ...newCustomer, password: e.target.value })} data-testid="admin-new-customer-password" />
              </div>
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-500">Address Line 1 *</label>
              <Input value={newCustomer.line1} onChange={(e) => setNewCustomer({ ...newCustomer, line1: e.target.value })} data-testid="admin-new-customer-line1" />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-500">Address Line 2</label>
              <Input value={newCustomer.line2} onChange={(e) => setNewCustomer({ ...newCustomer, line2: e.target.value })} data-testid="admin-new-customer-line2" />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1">
                <label className="text-xs text-slate-500">City *</label>
                <Input value={newCustomer.city} onChange={(e) => setNewCustomer({ ...newCustomer, city: e.target.value })} data-testid="admin-new-customer-city" />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">State/Province *</label>
                <Input value={newCustomer.region} onChange={(e) => setNewCustomer({ ...newCustomer, region: e.target.value })} data-testid="admin-new-customer-region" />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Postal Code *</label>
                <Input value={newCustomer.postal} onChange={(e) => setNewCustomer({ ...newCustomer, postal: e.target.value })} data-testid="admin-new-customer-postal" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Country * (locked after creation)</label>
                <Input value={newCustomer.country} onChange={(e) => setNewCustomer({ ...newCustomer, country: e.target.value.toUpperCase() })} placeholder="GB / US / CA" maxLength={2} data-testid="admin-new-customer-country" />
              </div>
              <div className="flex items-end gap-2 pb-1">
                <input type="checkbox" checked={newCustomer.mark_verified} onChange={(e) => setNewCustomer({ ...newCustomer, mark_verified: e.target.checked })} id="markVerified" data-testid="admin-new-customer-verified" />
                <label htmlFor="markVerified" className="text-xs text-slate-600">Mark email as verified</label>
              </div>
            </div>
            <Button onClick={handleCreateCustomer} className="w-full" data-testid="admin-new-customer-submit">Create Customer</Button>
          </div>
        </DialogContent>
      </Dialog>

    </div>
  );
}
