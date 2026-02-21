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

export default function Admin() {
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

  const load = async () => {
    const [custRes, orderRes, subRes, productRes, logRes, promoRes, termsRes] = await Promise.all([
      api.get("/admin/customers"),
      api.get("/admin/orders"),
      api.get("/admin/subscriptions"),
      api.get("/products"),
      api.get("/admin/sync-logs"),
      api.get("/admin/promo-codes").catch(() => ({ data: { promo_codes: [] } })),
      api.get("/terms").catch(() => ({ data: { terms: [] } })),
    ]);
    setCustomers(custRes.data.customers || []);
    setAddresses(custRes.data.addresses || []);
    setUsers(custRes.data.users || []);
    setOrders(orderRes.data.orders || []);
    setOrderItems(orderRes.data.items || []);
    setSubscriptions(subRes.data.subscriptions || []);
    setProducts(productRes.data.products || []);
    setLogs(logRes.data.logs || []);
    setPromoCodes(promoRes.data.promo_codes || []);
    setTerms(termsRes.data.terms || []);
  };

  useEffect(() => {
    load();
  }, []);

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

  const handleOrderSave = async () => {
    if (!selectedOrder) return;
    try {
      await api.put(`/admin/orders/${selectedOrder.id}`, {
        manual_status: selectedOrder.manual_status || "",
        internal_note: selectedOrder.internal_note || "",
      });
      toast.success("Order updated");
      load();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Order update failed");
    }
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

  const getCustomerAddress = (customerId: string) => addresses.find(a => a.customer_id === customerId);
  const getCustomerUser = (customerId: string) => {
    const customer = customers.find(c => c.id === customerId);
    return users.find(u => u.id === customer?.user_id);
  };
  const getProductName = (productId: string) => products.find(p => p.id === productId)?.name || productId;

  // Filter orders
  const filteredOrders = orders.filter(order => {
    const user = getCustomerUser(order.customer_id);
    if (orderFilters.email && !user?.email?.toLowerCase().includes(orderFilters.email.toLowerCase())) return false;
    if (orderFilters.startDate && order.created_at < orderFilters.startDate) return false;
    if (orderFilters.endDate && order.created_at > orderFilters.endDate + "T23:59:59") return false;
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
            <h3 className="text-sm font-semibold text-slate-900 mb-4">Customers</h3>
            <Table data-testid="admin-customer-table">
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>State/Province</TableHead>
                  <TableHead>Country</TableHead>
                  <TableHead>Bank Transfer</TableHead>
                  <TableHead>Card Payment</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {customers.map((customer) => {
                  const user = users.find((u) => u.id === customer.user_id);
                  const address = getCustomerAddress(customer.id);
                  return (
                    <TableRow key={customer.id} data-testid={`admin-customer-row-${customer.id}`}>
                      <TableCell data-testid={`admin-customer-name-${customer.id}`}>{user?.full_name || customer.company_name}</TableCell>
                      <TableCell data-testid={`admin-customer-email-${customer.id}`}>{user?.email || "—"}</TableCell>
                      <TableCell data-testid={`admin-customer-region-${customer.id}`}>{address?.region || "—"}</TableCell>
                      <TableCell data-testid={`admin-customer-country-${customer.id}`}>{address?.country || "—"}</TableCell>
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
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

        <TabsContent value="orders" className="space-y-4">
          <div className="flex justify-end mb-3">
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
                <Input type="date" value={orderFilters.startDate} onChange={(e) => setOrderFilters({ ...orderFilters, startDate: e.target.value })} data-testid="admin-orders-start-date" className="w-40" />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">End Date</label>
                <Input type="date" value={orderFilters.endDate} onChange={(e) => setOrderFilters({ ...orderFilters, endDate: e.target.value })} data-testid="admin-orders-end-date" className="w-40" />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-500">Customer Email</label>
                <Input placeholder="Filter by email" value={orderFilters.email} onChange={(e) => setOrderFilters({ ...orderFilters, email: e.target.value })} data-testid="admin-orders-email-filter" className="w-48" />
              </div>
              <Button variant="outline" onClick={() => setOrderFilters({ email: "", product: "", startDate: "", endDate: "" })} data-testid="admin-orders-clear-filters">Clear</Button>
            </div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
            <Table data-testid="admin-orders-table">
              <TableHeader>
                <TableRow className="bg-slate-50">
                  <TableHead>Date</TableHead>
                  <TableHead>Order #</TableHead>
                  <TableHead>Customer Name</TableHead>
                  <TableHead>Customer Email</TableHead>
                  <TableHead>Product(s)</TableHead>
                  <TableHead>Subscription #</TableHead>
                  <TableHead>Subtotal</TableHead>
                  <TableHead>Fee</TableHead>
                  <TableHead>Total</TableHead>
                  <TableHead>Payment</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredOrders.map((order) => {
                  const user = getCustomerUser(order.customer_id);
                  const items = orderItems.filter(i => i.order_id === order.id);
                  const productNames = items.map(i => getProductName(i.product_id)).join(", ") || "—";
                  return (
                    <TableRow key={order.id} data-testid={`admin-order-row-${order.id}`} className="border-b border-slate-100">
                      <TableCell className="text-xs">{order.created_at?.slice(0, 10)}</TableCell>
                      <TableCell className="font-mono text-xs">{order.order_number}</TableCell>
                      <TableCell>{user?.full_name || "—"}</TableCell>
                      <TableCell className="text-xs">{user?.email || "—"}</TableCell>
                      <TableCell className="max-w-[200px] truncate text-xs" title={productNames}>{productNames}</TableCell>
                      <TableCell className="font-mono text-xs">{order.subscription_number || order.subscription_id || "—"}</TableCell>
                      <TableCell>${order.subtotal?.toFixed(2)}</TableCell>
                      <TableCell>${order.fee?.toFixed(2)}</TableCell>
                      <TableCell className="font-semibold">${order.total?.toFixed(2)}</TableCell>
                      <TableCell><span className={`text-xs px-2 py-1 rounded ${order.payment_method === "bank_transfer" ? "bg-blue-100 text-blue-700" : order.payment_method === "offline" ? "bg-gray-100 text-gray-700" : "bg-green-100 text-green-700"}`}>{order.payment_method === "bank_transfer" ? "Bank" : order.payment_method === "offline" ? "Manual" : "Card"}</span></TableCell>
                      <TableCell><span className={`text-xs px-2 py-1 rounded ${order.status === "paid" ? "bg-green-100 text-green-700" : order.status === "unpaid" ? "bg-red-100 text-red-700" : order.status === "awaiting_bank_transfer" ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-600"}`}>{order.status}</span></TableCell>
                      <TableCell>
                        <div className="flex gap-2">
                          <Button variant="ghost" size="sm" onClick={() => handleViewOrderLogs(order.id)}>View Logs</Button>
                          <Dialog open={selectedOrder?.id === order.id} onOpenChange={(open) => { if (!open) setSelectedOrder(null); }}>
                            <DialogTrigger asChild>
                              <Button variant="outline" size="sm" onClick={() => setSelectedOrder(order)} data-testid={`admin-order-edit-${order.id}`}>Edit</Button>
                            </DialogTrigger>
                            {selectedOrder && selectedOrder.id === order.id && (
                              <DialogContent data-testid="admin-order-dialog">
                                <DialogHeader><DialogTitle>Update order {order.order_number}</DialogTitle></DialogHeader>
                                <div className="space-y-3">
                                  <Input placeholder="Manual status" value={selectedOrder.manual_status || ""} onChange={(e) => setSelectedOrder({ ...selectedOrder, manual_status: e.target.value })} data-testid="admin-order-status-input" />
                                  <Textarea placeholder="Internal note" value={selectedOrder.internal_note || ""} onChange={(e) => setSelectedOrder({ ...selectedOrder, internal_note: e.target.value })} data-testid="admin-order-note-input" />
                                  <Button onClick={handleOrderSave} data-testid="admin-order-save">Save update</Button>
                                </div>
                              </DialogContent>
                            )}
                          </Dialog>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

        <TabsContent value="subscriptions" className="space-y-4">
          <div className="flex justify-end mb-3">
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
          <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
            <Table data-testid="admin-subscriptions-table">
              <TableHeader>
                <TableRow className="bg-slate-50">
                  <TableHead>Customer</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Plan</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Renewal Date</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Payment</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {subscriptions.map((sub) => {
                  const user = getCustomerUser(sub.customer_id);
                  return (
                    <TableRow key={sub.id} data-testid={`admin-subscription-${sub.id}`} className="border-b border-slate-100">
                      <TableCell>{user?.full_name || "—"}</TableCell>
                      <TableCell className="text-xs">{user?.email || "—"}</TableCell>
                      <TableCell>{sub.plan_name}</TableCell>
                      <TableCell><span className={`text-xs px-2 py-1 rounded ${sub.status === "active" ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-600"}`}>{sub.status}</span></TableCell>
                      <TableCell className="text-xs">{sub.renewal_date?.slice(0, 10) || sub.current_period_end?.slice(0, 10) || "—"}</TableCell>
                      <TableCell>${sub.amount?.toFixed(2) || "—"}</TableCell>
                      <TableCell>{sub.payment_method || "card"}</TableCell>
                      <TableCell>
                        <div className="flex gap-2">
                          {sub.is_manual && <Button size="sm" variant="outline" onClick={() => handleRenewNow(sub.id)}>Renew Now</Button>}
                          <Button size="sm" variant="ghost" onClick={() => handleViewSubLogs(sub.id)}>View Logs</Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

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
                      <Select value={product.terms_id || ""} onValueChange={(v) => handleAssignTermsToProduct(product.id, v || null)}>
                        <SelectTrigger className="w-48">
                          <SelectValue placeholder="Default T&C" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="">Default T&C</SelectItem>
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
                ))}
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
      </Tabs>

      {/* Logs Dialog */}
      <Dialog open={showLogsDialog} onOpenChange={setShowLogsDialog}>
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
    </div>
  );
}
